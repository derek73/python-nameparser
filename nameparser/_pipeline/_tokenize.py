"""Stage: tokenize.

Consumes: original, masked (regions to skip), extracted (regions that
tokenize with a pre-set role).
Produces: tokens (span-sorted WorkTokens; text always == original
slice), comma_offsets (segmentation points; never tokens),
interpunct_offsets (间隔号 transcription markers, #298; never tokens).
Reads: Policy.strip_emoji, Policy.strip_bidi.

Implements rules T1, T2 and T3 of docs/design/rules.md, cited at
their code below. There is NO text-rewriting normalize stage: all
three are character-classification rules, so spans always index the
original exactly as given (v1 contrast: decisions.md#T1).
"""
from __future__ import annotations

import bisect
import dataclasses
import re

from nameparser._pipeline._state import (
    COMMA_CHARS, ParseState, WorkToken,
)
from nameparser._policy import Policy, _SCRIPT_RANGES, _script_matcher
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

# rules.md#T2: "the katakana middle dot and its halfwidth twin divide
# a name like whitespace, always." They record no offset: the
# nakaguro also divides kanji roster pairs (高橋・一郎, read
# family-first by the script license, #272), so it is not a
# transcription marker; only the Chinese 间隔号 is (#298).
_NAME_DOT_SEPARATORS = frozenset({"\u30FB", "\uFF65"})

_INTERPUNCT = "\u00B7"
# rules.md#T3: "the interpunct divides a name only between two
# characters of a classified East Asian script; anywhere else it is
# part of the word" (history: decisions.md#T3). Per-CHAR classifier
# for the flank guard: a one-char string is wholly-classified iff the
# character is. Context-sensitivity is why this lives in
# _tokenize_region (where the index exists) and not in _ignorable.
_classified_char = _script_matcher(*_SCRIPT_RANGES, whole=True)


def _is_emoji(ch: str) -> bool:
    cp = ord(ch)
    return any(lo <= cp <= hi for lo, hi in _EMOJI_RANGES)


# rules.md#T1: "an ignorable character separates its neighbors and
# never joins them" (v1 contrast: decisions.md#T1)
def _stripped(ch: str, policy: Policy) -> bool:
    """True when the strip policy removes `ch` from the token stream.
    The ONE definition of that set, shared by _ignorable and _flank: a
    character that vanishes from tokens must not occupy a flank
    position either, so a new strip class added here stays transparent
    to the interpunct guard by construction."""
    if policy.strip_bidi and _BIDI.match(ch):
        return True
    return bool(policy.strip_emoji and _is_emoji(ch))


def _flank(text: str, indices: range, policy: Policy) -> str | None:
    """The nearest flank character the strip policy would keep, or
    None if the range exhausts. Stripped invisibles are TRANSPARENT
    here: an RTL document quoting a transcription puts U+200F beside
    the dot in visually identical text. Whitespace and the other
    separators stay guard-defeating: a dot beside a space is not
    between characters."""
    for i in indices:
        ch = text[i]
        if not _stripped(ch, policy):
            return ch
    return None


def _ignorable(ch: str, state: ParseState) -> bool:
    if ch.isspace():
        return True
    if ch.isascii():
        # both strip classes and the name-dot separators are entirely
        # non-ASCII (bidi >= U+061C, emoji >= U+2600, dots >= U+30FB):
        # skip the checks below for every ASCII letter
        return False
    # unconditional, like whitespace -- not policy-gated, so this sits
    # ahead of the policy check rather than in _tokenize_region beside
    # COMMA_CHARS (commas RECORD an offset; these dots must not --
    # only the 间隔号 marks a transcription and records, #298, see
    # _NAME_DOT_SEPARATORS above). The only load-bearing constraint is
    # "after the isascii fast path" (both dots are non-ASCII).
    if ch in _NAME_DOT_SEPARATORS:
        return True
    return _stripped(ch, state.policy)


def _tokenize_region(state: ParseState, start: int, end: int,
                     role: Role | None, record_offsets: bool,
                     tokens: list[WorkToken], commas: list[int],
                     interpuncts: list[int]) -> None:
    text = state.original
    tok_start: int | None = None
    for i in range(start, end):
        ch = text[i]
        is_separator = ch in COMMA_CHARS or _ignorable(ch, state)
        if ch == _INTERPUNCT:
            # Region-local flanks: a B7 at a region edge stays token
            # text, and the bound also stops a custom delimiter's
            # classified edge character from acting as a flank across
            # a mask seam. The scan reads raw text like segmentation
            # matching does (#272's stance): NFD hangul degrades to
            # no-split, never wrong-split -- classification
            # NFC-normalizes but the guard does not.
            left = _flank(text, range(i - 1, start - 1, -1),
                          state.policy)
            if left is not None and _classified_char(left):
                right = _flank(text, range(i + 1, end), state.policy)
                is_separator = (right is not None
                                and _classified_char(right))
        if is_separator:
            if tok_start is not None:
                tokens.append(WorkToken(text[tok_start:i],
                                        Span(tok_start, i), role=role))
                tok_start = None
            if record_offsets:
                if ch in COMMA_CHARS:
                    commas.append(i)
                elif ch == _INTERPUNCT:
                    interpuncts.append(i)
            continue
        if tok_start is None:
            tok_start = i
    if tok_start is not None:
        tokens.append(WorkToken(text[tok_start:end],
                                Span(tok_start, end), role=role))


def tokenize(state: ParseState) -> ParseState:
    tokens: list[WorkToken] = []
    commas: list[int] = []
    interpuncts: list[int] = []
    # main stream: everything outside masked regions
    boundaries = [0]
    for m in state.masked:
        boundaries.extend((m.start, m.end))
    boundaries.append(len(state.original))
    for start, end in zip(boundaries[::2], boundaries[1::2]):
        _tokenize_region(state, start, end, None, True, tokens, commas,
                         interpuncts)
    # extracted regions: pre-set role, commas and interpuncts are mere
    # separators
    for role, inner in state.extracted:
        _tokenize_region(state, inner.start, inner.end, role, False,
                         tokens, commas, interpuncts)
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
                               interpunct_offsets=tuple(sorted(interpuncts)),
                               ambiguities=ambiguities)
