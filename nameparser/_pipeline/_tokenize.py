"""Stage: tokenize.

Consumes: original, masked (regions to skip), extracted (regions that
tokenize with a pre-set role).
Produces: tokens (span-sorted WorkTokens; text always == original
slice), comma_offsets (segmentation points; never tokens).
Reads: Policy.strip_emoji, Policy.strip_bidi.

There is NO text-rewriting normalize stage: whitespace collapsing,
emoji/bidi stripping, and the katakana name-dot split are all
character-classification rules here -- ignorable characters act as
separators and never enter a token, so spans always index the
original exactly as given. Whitespace and the name-dot are
unconditional; emoji/bidi stripping alone is policy-gated
(Policy.strip_emoji/strip_bidi).

v1's squash_emoji/squash_bidi REMOVED the char and joined neighbors
('A\U0001f600B' -> 'AB'); here an ignorable char is a SEPARATOR
('A\U0001f600B' -> 'A', 'B') -- the unavoidable consequence of spans
indexing the original exactly.
"""
from __future__ import annotations

import bisect
import dataclasses
import re

from nameparser._pipeline._state import (
    COMMA_CHARS, ParseState, WorkToken,
)
from nameparser._types import Role, Span

# Ported from v1 (nameparser/config/regexes.py, "emoji" and "bidi") --
# layering forbids importing the config package here, so the tables are
# duplicated by design with this provenance note. When editing, keep
# both copies in sync (regexes.py builds its public re_emoji from the
# SAME codepoint pairs). Integer ranges, not a regex character class:
# the per-char test needs no regex, and CodeQL's py/overly-large-range
# false-positives on literal astral ranges (surrogate decomposition).
_EMOJI_RANGES = ((0x1F300, 0x1F64F), (0x1F680, 0x1F6FF),
                 (0x2600, 0x26FF), (0x2700, 0x27BF))
_BIDI = re.compile('[\u061C\u200E\u200F\u202A-\u202E\u2066-\u2069]+')

# The katakana middle dot and its halfwidth twin divide the parts of
# a foreign name transcribed into katakana (マイケル・ジャクソン) --
# native names never contain them, so they separate unconditionally,
# like whitespace (amendment 2026-07-29 section 1b). U+00B7 is
# deliberately NOT here: it is also the Catalan punt volat, interior
# to real names (Gal·la) -- a follow-up issue owns that decision.
_NAME_DOT_SEPARATORS = frozenset({"\u30FB", "\uFF65"})


def _ignorable(ch: str, state: ParseState) -> bool:
    if ch.isspace():
        return True
    if ch.isascii():
        # both strip classes and the name-dot separators are entirely
        # non-ASCII (bidi >= U+061C, emoji >= U+2600, dots >= U+30FB):
        # skip the checks below for every ASCII letter
        return False
    # unconditional, like whitespace -- not policy-gated, so this sits
    # ahead of the policy checks rather than in _tokenize_region beside
    # COMMA_CHARS (commas RECORD an offset; these dots must not). The
    # only load-bearing constraint is "after the isascii fast path"
    # (both dots are non-ASCII); being ahead of the bidi/emoji checks
    # below is NOT load-bearing -- the three sets are disjoint, so a
    # future edit is free to reorder them.
    if ch in _NAME_DOT_SEPARATORS:
        return True
    if state.policy.strip_bidi and _BIDI.match(ch):
        return True
    if state.policy.strip_emoji:
        cp = ord(ch)
        return any(lo <= cp <= hi for lo, hi in _EMOJI_RANGES)
    return False


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
    # extract_delimited runs before tokens exist, so its ambiguities
    # carry a character offset instead of an index. Resolve them now
    # that the stray character has landed in a token ('"Nick', 'Smith)')
    # -- without this the ambiguity is locatable only by parsing the
    # offset back out of its detail string. An offset inside a masked
    # region belongs to no token; those keep an empty tuple, which the
    # kind's contract already allows.
    # Bisect rather than rescan: the closer sweep can emit one
    # ambiguity per delimiter character, so a linear scan per ambiguity
    # is quadratic on pathological input (') ' * 1600 spent 180ms here,
    # against 9ms before the sweep existed). Spans are non-overlapping
    # and sorted just above, so the candidate is the last token whose
    # start is <= the offset.
    # Nothing to resolve on the overwhelmingly common no-ambiguity
    # parse, and building starts + the closure is not free.
    ambiguities = state.ambiguities
    if any(a.origin is not None for a in ambiguities):
        starts = [t.span.start for t in tokens]

        def _containing(offset: int) -> tuple[int, ...]:
            i = bisect.bisect_right(starts, offset) - 1
            if i >= 0 and offset < tokens[i].span.end:
                return (i,)
            return ()

        ambiguities = tuple(
            a if a.origin is None
            else dataclasses.replace(a, indices=_containing(a.origin))
            for a in ambiguities)
    return dataclasses.replace(state, tokens=tuple(tokens),
                               comma_offsets=tuple(sorted(commas)),
                               ambiguities=ambiguities)
