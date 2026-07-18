"""Stage: tokenize.

Consumes: original, masked (regions to skip), extracted (regions that
tokenize with a pre-set role).
Produces: tokens (span-sorted WorkTokens; text always == original
slice), comma_offsets (segmentation points; never tokens).
Reads: Policy.strip_emoji, Policy.strip_bidi.

There is NO text-rewriting normalize stage (core spec §6): whitespace
collapsing and emoji/bidi stripping are character-classification rules
here -- ignorable characters act as separators and never enter a token,
so spans always index the original exactly as given.

v1's squash_emoji/squash_bidi REMOVED the char and joined neighbors
('A\U0001f600B' -> 'AB'); here an ignorable char is a SEPARATOR
('A\U0001f600B' -> 'A', 'B') -- the unavoidable consequence of spans
indexing the original exactly.
"""
from __future__ import annotations

import dataclasses
import re

from nameparser._pipeline._state import (
    COMMA_CHARS, ParseState, WorkToken,
)
from nameparser._types import Role, Span

# Ported verbatim from v1 (nameparser/config/regexes.py, "emoji" and
# "bidi") -- layering forbids importing the config package here, so the
# patterns are duplicated by design with this provenance note. When
# editing, keep both copies in sync.
_EMOJI = re.compile('['
    '\U0001F300-\U0001F64F'  # lgtm[py/overly-large-range]
    '\U0001F680-\U0001F6FF'
    '\u2600-\u26FF\u2700-\u27BF]+')
_BIDI = re.compile('[\u061C\u200E\u200F\u202A-\u202E\u2066-\u2069]+')


def _ignorable(ch: str, state: ParseState) -> bool:
    if ch.isspace():
        return True
    if ch.isascii():
        # both strip classes are entirely non-ASCII (bidi >= U+061C,
        # emoji >= U+2600): skip two failing regex calls per letter
        return False
    if state.policy.strip_bidi and _BIDI.match(ch):
        return True
    return bool(state.policy.strip_emoji and _EMOJI.match(ch))


def _tokenize_region(state: ParseState, start: int, end: int,
                     role: Role | None, record_commas: bool,
                     tokens: list[WorkToken], commas: list[int]) -> None:
    text = state.original
    tok_start: int | None = None
    for i in range(start, end):
        ch = text[i]
        if ch in COMMA_CHARS or _ignorable(ch, state):
            if tok_start is not None:
                tokens.append(WorkToken(text[tok_start:i],
                                        Span(tok_start, i), role=role))
                tok_start = None
            if ch in COMMA_CHARS and record_commas:
                commas.append(i)
            continue
        if tok_start is None:
            tok_start = i
    if tok_start is not None:
        tokens.append(WorkToken(text[tok_start:end],
                                Span(tok_start, end), role=role))


def tokenize(state: ParseState) -> ParseState:
    tokens: list[WorkToken] = []
    commas: list[int] = []
    # main stream: everything outside masked regions
    boundaries = [0]
    for m in state.masked:
        boundaries.extend((m.start, m.end))
    boundaries.append(len(state.original))
    for start, end in zip(boundaries[::2], boundaries[1::2]):
        _tokenize_region(state, start, end, None, True, tokens, commas)
    # extracted regions: pre-set role, commas are mere separators
    for role, inner in state.extracted:
        _tokenize_region(state, inner.start, inner.end, role, False,
                         tokens, commas)
    tokens.sort(key=lambda t: t.span)
    return dataclasses.replace(state, tokens=tuple(tokens),
                               comma_offsets=tuple(sorted(commas)))
