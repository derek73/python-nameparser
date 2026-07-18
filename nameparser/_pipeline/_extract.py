"""Stage: extract_delimited.

Consumes: ParseState.original.
Produces: extracted (role + inner span per delimited region), masked
(full regions incl. delimiter chars, skipped by tokenize),
UNBALANCED_DELIMITER ambiguities for opens with no close.
Reads: Policy.nickname_delimiters, Policy.maiden_delimiters.

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


def _overlaps(span: Span, taken: list[Span]) -> bool:
    return any(span.start < t.end and t.start < span.end for t in taken)


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
    ambiguities = tuple(
        a for offset, a in unbalanced
        if not _overlaps(Span(offset, offset + 1), masked))
    return dataclasses.replace(
        state, extracted=tuple(extracted), masked=tuple(masked),
        ambiguities=state.ambiguities + ambiguities)
