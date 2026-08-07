"""Stage: extract_delimited.

Consumes: ParseState.original.
Produces: extracted (role + inner span per delimited region), masked
(full regions incl. delimiter chars, skipped by tokenize),
UNBALANCED_DELIMITER ambiguities for opens with no close.
A Role.MAIDEN region is the WHOLE inner span, marker word included --
nothing here strips one. classify tags a marker inside it like any
other token, and group drops it from a multi-token clause (#329).
Reads: Policy.nickname_delimiters, Policy.maiden_delimiters, and
Lexicon.suffix_words / suffix_acronyms / suffix_acronyms_ambiguous
through _suffix_shaped, which lets a clause's CONTENT overrule the
delimiter's verdict: 'Andrew Perkins (MBA)' is not a nickname, so
only the two delimiter spans are masked and the content rejoins the
token stream.

Matching rules (the #273 mechanism): one left-to-right scan over the
original text, no nesting. At each position the LEFTMOST boundary-valid
opener among ALL configured pairs wins -- position order, never pair
order, decides between conventions that share a character in opposite
roles ('“' closes „…“ but opens “…”; '»' closes «…» but opens »…«), so
"Hans „Erster“ und “Zweiter” Müller" extracts both names. For pairs
whose open == close (quotes), the open must sit at a word boundary
(start of text or after whitespace) and the close before one (end,
whitespace, or a comma char) -- this is what keeps the apostrophe in
O'Connor literal. Empty enclosures are masked (removed from the token
stream) but extract nothing; delimiter characters inside a matched
region are literal content for every other pair.

Bucket precedence is NOT decided here: Policy canonicalizes overlap
away before parsing (a pair listed in maiden_delimiters is dropped
from the effective nickname set -- maiden wins; the v1 facade restores
v1's nickname-wins reading via a pre-subtraction in _config_shim), so
the two buckets are always disjoint by the time this stage runs. The
nickname-before-maiden candidate order below is only a same-position
tie-break for exotic configs where two pairs share an OPEN character.
"""
from __future__ import annotations

import bisect
import dataclasses
import functools

from nameparser._lexicon import Lexicon, _normalize
from nameparser._pipeline._state import (
    COMMA_CHARS, ParseState, PendingAmbiguity,
)
from nameparser._types import AmbiguityKind, Role, Span


def _suffix_shaped(content: str, lexicon: Lexicon) -> bool:
    """v1 parse_nicknames' escape (parser.py:1125-1141): an unambiguous
    suffix_words member (edge-normalized), an unambiguous acronym
    (period-free form), or anything ending in a period. No initial
    veto -- v1 deliberately skipped it here."""
    stripped = _normalize(content)
    acronym = stripped.replace(".", "")
    return (stripped in lexicon.suffix_words
            or (acronym in lexicon.suffix_acronyms
                and acronym not in lexicon.suffix_acronyms_ambiguous)
            or content.endswith("."))


def _open_ok(text: str, i: int) -> bool:
    return i == 0 or text[i - 1].isspace()


def _close_ok(text: str, j: int, width: int) -> bool:
    k = j + width
    return k >= len(text) or text[k].isspace() or text[k] in COMMA_CHARS


# Delimiters that also occur INSIDE and at the end of real name parts,
# so a dangling one is literal rather than unbalanced. Only the straight
# apostrophe qualifies: quotes do not appear inside names, so the same
# position with a quote genuinely is ambiguous. #273 dropped the curly
# apostrophe from the defaults outright for this reason; the straight
# one has to stay a delimiter (v1's quoted_word), so it is carved out
# here instead. Deliberately not widened to a configured delimiter set.
WORD_INTERNAL_DELIMITERS = frozenset({"'"})


def _word_internal(text: str, j: int, close: str) -> bool:
    """A word-internal delimiter directly after a word character is part
    of the word, not a dangling close -- "Mari' Aube'", "Ali Baba'"."""
    return (close in WORD_INTERNAL_DELIMITERS and j > 0
            and (text[j - 1].isalnum() or text[j - 1] == "."))


def _overlaps(span: Span, taken: list[Span], starts: list[int]) -> bool:
    """`taken` sorted and non-overlapping (both hold by construction),
    `starts` its start offsets. Bisect rather than scan: the closer
    sweep tests one span per delimiter character found, so a linear
    probe is quadratic in the number of matched pairs (400 pairs spent
    5.4ms here, against 2.5ms before the sweep existed). Same idiom, and
    the same reason, as the origin resolution in _tokenize."""
    i = bisect.bisect_right(starts, span.start) - 1
    # the only candidates are the last span starting at or before us and
    # its successor -- anything earlier ends before it, anything later
    # starts after us
    for k in (i, i + 1):
        if 0 <= k < len(taken) and span.start < taken[k].end and (
                taken[k].start < span.end):
            return True
    return False


@functools.lru_cache(maxsize=128)
def _delimiter_chars(
    nickname_pairs: frozenset[tuple[str, str]],
    maiden_pairs: frozenset[tuple[str, str]],
) -> frozenset[str]:
    """Every character appearing in any configured delimiter, cached on
    the (hashable) policy frozensets: the common no-delimiter name pays
    one isdisjoint() instead of a per-pair scan."""
    return frozenset(
        ch
        for pairs in (nickname_pairs, maiden_pairs)
        for pair in pairs
        for part in pair
        for ch in part
    )


def _unmatched(open_: str, offset: int) -> tuple[int, PendingAmbiguity]:
    return (offset, PendingAmbiguity(
        AmbiguityKind.UNBALANCED_DELIMITER,
        f"unmatched {open_!r} at offset {offset}; treated as literal text",
        origin=offset,
    ))


def extract_delimited(state: ParseState) -> ParseState:
    text = state.original
    policy = state.policy
    if _delimiter_chars(policy.nickname_delimiters,
                        policy.maiden_delimiters).isdisjoint(text):
        return state
    # Candidate order matters only as a same-position tie-break (see
    # module docstring); the scan itself is position-driven.
    order = tuple(
        (role, open_, close)
        for role, pairs in ((Role.NICKNAME, policy.nickname_delimiters),
                            (Role.MAIDEN, policy.maiden_delimiters))
        for open_, close in sorted(pairs)
    )
    extracted: list[tuple[Role, Span]] = []
    masked: list[Span] = []
    # candidates, not final: each carries the offset of the unmatched
    # open so ones consumed by a later match can be filtered at the end
    unbalanced: list[tuple[int, PendingAmbiguity]] = []
    # per-candidate cursor cache: next boundary-valid open at or after
    # the position it was computed for. find() calls only ever move
    # forward, keeping the whole scan linear in len(text) per pair.
    cursors: dict[tuple[Role, str, str], int] = {}
    exhausted: set[tuple[Role, str, str]] = set()
    pos = 0
    while pos < len(text):
        best: tuple[int, Role, str, str] | None = None
        for key in order:
            if key in exhausted:
                continue
            _, open_, close = key
            i = cursors.get(key, -2)
            if i != -1 and i < pos:
                i = text.find(open_, pos)
                while (i != -1 and open_ == close
                       and not _open_ok(text, i)):
                    i = text.find(open_, i + 1)
                cursors[key] = i
            if i != -1 and (best is None or i < best[0]):
                best = (i, *key)
        if best is None:
            break
        i, role, open_, close = best
        j = text.find(close, i + len(open_))
        while (open_ == close and j != -1
               and not _close_ok(text, j, len(close))):
            j = text.find(close, j + 1)
        if j == -1:
            # No (boundary-valid) close exists anywhere to the right --
            # the walk above ran to end of text -- so every remaining
            # open of this pair is unmatched too. Record them all in
            # one forward pass and retire the pair; other pairs keep
            # scanning from the same position.
            unbalanced.append(_unmatched(open_, i))
            scan = i + len(open_)
            while (k := text.find(open_, scan)) != -1:
                if open_ != close or _open_ok(text, k):
                    unbalanced.append(_unmatched(open_, k))
                scan = k + 1
            exhausted.add((role, open_, close))
            continue
        inner = Span(i + len(open_), j)
        if inner.start < inner.end and _suffix_shaped(
                text[inner.start:inner.end], state.lexicon):
            # v1 parse_nicknames: suffix-shaped delimited content is
            # left IN PLACE (undelimited) for normal downstream parsing
            # -- 'Andrew Perkins (MBA)' keeps MBA a suffix, not a
            # nickname. Spans index the original (anti-#100), so the v2
            # spelling masks only the two delimiter spans and lets the
            # inner content join the main token stream.
            masked.append(Span(i, i + len(open_)))
            masked.append(Span(j, j + len(close)))
        else:
            if inner.start < inner.end:
                extracted.append((role, inner))
            masked.append(Span(i, j + len(close)))
        # position-driven scanning makes overlapping matches
        # impossible by construction: every later open is found at or
        # after this match's end
        pos = j + len(close)
    extracted.sort(key=lambda pair: pair[1])
    masked.sort()
    # An unmatched-open candidate whose character was consumed by a
    # later successful match (the bulk pass above runs ahead of the
    # main scan) is literal content there, not a dangling delimiter.
    # offsets already claimed as unbalanced, by an open above or by a
    # close in the sweep below -- either way, do not report one twice
    reported = {offset for offset, _ in unbalanced}
    mask_starts = [s.start for s in masked]
    ambiguities = [
        a for offset, a in unbalanced
        if not _overlaps(Span(offset, offset + 1), masked, mask_starts)]
    # The scan above is opener-driven: it searches for an open and then
    # looks rightward for its close, so a close with no open to its
    # LEFT is never in its search space. Sweep for those separately --
    # they signal the same malformed input, and the kind's contract has
    # always covered them ("opened without closing, or closed without
    # opening"). Same boundary test as the matched path, which is what
    # keeps the apostrophe in "O'connor" out of it.
    # Distinct closes only: the defaults list '”' twice (from both
    # ('“','”') and ('”','”')), and a repeat can only rediscover
    # offsets the first pass already handled.
    for close in sorted({c for _, _, c in order}):
        start = 0
        while (j := text.find(close, start)) != -1:
            start = j + 1
            if (j in reported
                    or not _close_ok(text, j, len(close))
                    or _word_internal(text, j, close)
                    or _overlaps(Span(j, j + len(close)), masked,
                                 mask_starts)):
                continue
            reported.add(j)
            ambiguities.append(_unmatched(close, j)[1])
    return dataclasses.replace(
        state, extracted=tuple(extracted), masked=tuple(masked),
        ambiguities=state.ambiguities + tuple(ambiguities))
