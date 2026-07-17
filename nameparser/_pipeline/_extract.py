"""Stage: extract_delimited.

Consumes: ParseState.original.
Produces: extracted (role + inner span per delimited region), masked
(full regions incl. delimiter chars, skipped by tokenize),
UNBALANCED_DELIMITER ambiguities for opens with no close.
Reads: Policy.nickname_delimiters, Policy.maiden_delimiters.

Matching rules (the #273 mechanism): pairs scan the original text left
to right, no nesting. For pairs whose open == close (quotes), the open
must sit at a word boundary (start of text or after whitespace) and the
close before one (end, whitespace, or a comma char) -- this is what
keeps the apostrophe in O'Connor literal. maiden_delimiters are scanned
before nickname_delimiters, so routing a pair to maiden (#274) wins if
a pair appears in both sets. Empty enclosures are masked (removed from
the token stream) but extract nothing. Overlapping candidate regions
resolve by scan order (maiden pairs, then nickname pairs, sorted within
each): the first match masks the region, and any delimiter chars inside
an extracted span stay literal.
"""
from __future__ import annotations

import dataclasses

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


def extract_delimited(state: ParseState) -> ParseState:
    text = state.original
    extracted: list[tuple[Role, Span]] = []
    masked: list[Span] = []
    ambiguities: list[PendingAmbiguity] = []
    # nickname first (v1 parse_nicknames order): when the same
    # delimiter pair sits in BOTH buckets, the nickname reading wins;
    # the documented bucket-move idiom removes it from nickname, so
    # maiden still gets it after a move
    for role, pairs in (
        (Role.NICKNAME, state.policy.nickname_delimiters),
        (Role.MAIDEN, state.policy.maiden_delimiters),
    ):
        for open_, close in sorted(pairs):
            pos = 0
            while (i := text.find(open_, pos)) != -1:
                if open_ == close and not _open_ok(text, i):
                    pos = i + 1
                    continue
                j = text.find(close, i + len(open_))
                while (open_ == close and j != -1
                       and not _close_ok(text, j, len(close))):
                    j = text.find(close, j + 1)
                if j == -1:
                    ambiguities.append(PendingAmbiguity(
                        AmbiguityKind.UNBALANCED_DELIMITER,
                        f"unmatched {open_!r} at offset {i}; treated as "
                        f"literal text",
                    ))
                    if open_ == close:
                        # _close_ok is open-independent, so a failed
                        # close-walk means NO boundary-valid close
                        # exists anywhere to the right: every remaining
                        # boundary-valid open is unmatched too. Record
                        # each in one forward pass without re-walking
                        # closes (keeps adversarial input linear).
                        scan = i + len(open_)
                        while (k := text.find(open_, scan)) != -1:
                            if _open_ok(text, k):
                                ambiguities.append(PendingAmbiguity(
                                    AmbiguityKind.UNBALANCED_DELIMITER,
                                    f"unmatched {open_!r} at offset {k}; "
                                    f"treated as literal text",
                                ))
                            scan = k + 1
                        break
                    pos = i + len(open_)
                    continue
                full = Span(i, j + len(close))
                if not _overlaps(full, masked):
                    inner = Span(i + len(open_), j)
                    if inner.start < inner.end and _suffix_shaped(
                            text[inner.start:inner.end], state.lexicon):
                        # v1 parse_nicknames: suffix-shaped delimited
                        # content is left IN PLACE (undelimited) for
                        # normal downstream parsing -- 'Andrew Perkins
                        # (MBA)' keeps MBA a suffix, not a nickname.
                        # Spans index the original (anti-#100), so the
                        # v2 spelling masks only the two delimiter
                        # spans and lets the inner content join the
                        # main token stream.
                        masked.append(Span(i, i + len(open_)))
                        masked.append(Span(j, j + len(close)))
                    else:
                        if inner.start < inner.end:
                            extracted.append((role, inner))
                        masked.append(full)
                pos = j + len(close)
    extracted.sort(key=lambda pair: pair[1])
    masked.sort()
    return dataclasses.replace(
        state, extracted=tuple(extracted), masked=tuple(masked),
        ambiguities=state.ambiguities + tuple(ambiguities))
