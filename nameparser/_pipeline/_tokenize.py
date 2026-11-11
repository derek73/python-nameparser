"""Stage: tokenize.

Consumes: original, masked (regions to skip), extracted (regions that
tokenize with a pre-set role).
Produces: tokens (span-sorted WorkTokens; text always == original
slice), comma_offsets (segmentation points of the main stream; a comma
there is never a token, one inside an extracted region is word text),
interpunct_offsets (间隔号 transcription markers, #298; never tokens).
Reads: Policy.strip_emoji, Policy.strip_bidi.

Implements rules T1, T2, T3 and T6 of docs/design/rules/, cited at
their code below. There is NO text-rewriting normalize stage: all
four are character-classification rules, so spans always index the
original exactly as given (v1 contrast: decisions/T1).

Beside the stage function, `_ignorable` is shared: extract asks it
where a listed particle's word ends (rules/N2, #1241), so the two
stages cannot disagree about which characters separate a word.
"""
from __future__ import annotations

import bisect
import re

from nameparser._pipeline._state import (
    COMMA_CHARS, ParseState, WorkToken, copy_with,
)
from nameparser._policy import Policy, _classified_char
from nameparser._types import Role, Span

# Ported from v1's "emoji" and "bidi" patterns (the 1.x and 2.x
# nameparser.config.regexes, removed in 3.0, #1008); this is now the
# only copy. Integer ranges, not a regex character class:
# the per-char test needs no regex, and CodeQL's py/overly-large-range
# false-positives on literal astral ranges (surrogate decomposition).
_EMOJI_RANGES = ((0x1F300, 0x1F64F), (0x1F680, 0x1F6FF),
                 (0x2600, 0x26FF), (0x2700, 0x27BF))
_BIDI = re.compile('[\u061C\u200E\u200F\u202A-\u202E\u2066-\u2069]+')

# rules/T2: "the katakana middle dot, its halfwidth twin and the
# Ethiopic wordspace divide a name like whitespace, always." They
# record no offset: the nakaguro also divides kanji roster pairs
# (高橋・一郎, read family-first by the script license, #272), so it is
# not a transcription marker; only the Chinese 间隔号 is (#298). The
# Ethiopic wordspace U+1361 joined them (decisions/T2, #1202).
_NAME_DOT_SEPARATORS = frozenset({"\u30FB", "\uFF65", "\u1361"})

# rules/T6: "a narrow no-break space between two Mongolian letters
# joins them into one word" -- the whole rule, T1's Except: anywhere
# else U+202F is whitespace and divides (decisions/T6, #1236).
_NARROW_NBSP = "\u202F"
_MONGOLIAN_BLOCK = (0x1800, 0x18AF)

# rules/T1: "a zero-width space, an invisible separator and a
# byte-order mark have no such opt-out" -- the Except clause: they
# separate under every policy, carrying nothing a caller would keep.
# Not here: U+200C and U+200D, which decide how the letters around
# them join, the word joiner U+2060, which means no break, the soft
# hyphen U+00AD, which marks a break inside one word, the invisible
# math operators U+2061, U+2062 and U+2064, and the Mongolian vowel
# separator U+180E, which shapes the letters beside it
# (decisions/T1, #851).
_INVISIBLE_SEPARATORS = frozenset({"\u200B", "\u2063", "\uFEFF"})

_INTERPUNCT = "\u00B7"
# The fullwidth full stop is the same transcription dot where Taiwan's
# writers type it between two Han names (`台邦．撒沙勒`, #1312), and the
# same plain full stop everywhere else, so it takes the interpunct's
# flank guard whole: it divides, and records, only between two characters
# of a classified script. The ideographic full stop U+3002 is not one:
# it is the sentence stop (decisions/T3, #1312).
_TRANSCRIPTION_DOTS = frozenset({_INTERPUNCT, "\uFF0E"})
# rules/T3: "the interpunct divides a name only between two
# characters of a classified East Asian script; anywhere else it is
# part of the word" (history: decisions/T3). The flank guard asks
# _policy._classified_char per CHAR: a one-char string is
# wholly-classified iff the character is. Context-sensitivity is why the
# guard lives in _tokenize_region (where the index exists) and not in
# _ignorable.


def _mongolian_letter(ch: str) -> bool:
    """A character of the Mongolian block that is not its punctuation
    (U+1800-U+180A) or a digit (U+1810-U+1819): its letters, free
    variation selectors and vowel separator, each of which stands
    inside a written word, and the block's unassigned codepoints."""
    cp = ord(ch)
    return (_MONGOLIAN_BLOCK[0] <= cp <= _MONGOLIAN_BLOCK[1]
            and not 0x1800 <= cp <= 0x180A and not 0x1810 <= cp <= 0x1819)


def _is_emoji(ch: str) -> bool:
    cp = ord(ch)
    return any(lo <= cp <= hi for lo, hi in _EMOJI_RANGES)


# rules/T1: "an ignorable character separates its neighbors and
# never joins them" (v1 contrast: decisions/T1)
def _stripped(ch: str, policy: Policy) -> bool:
    """True when the strip policy removes `ch` from the token stream.
    The ONE definition of that set, shared by _ignorable and _flank: a
    character the strip policy removes must not occupy a flank
    position either, so a new strip class added here stays transparent
    to the interpunct guard by construction. The separators (whitespace,
    the name dots and _INVISIBLE_SEPARATORS) are not in this set and do
    occupy one."""
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
        # both strip classes and the unconditional separators are
        # entirely non-ASCII (bidi >= U+061C, emoji >= U+2600, the
        # invisibles >= U+200B, dividers >= U+1361): skip the checks below
        # for every ASCII letter
        return False
    # unconditional, like whitespace -- not policy-gated, so this sits
    # ahead of the policy check rather than in _tokenize_region beside
    # COMMA_CHARS (commas RECORD an offset; these must not -- only the
    # 间隔号 marks a transcription and records, #298, see
    # _NAME_DOT_SEPARATORS above). The only load-bearing constraint is
    # "after the isascii fast path" (every member of both sets is
    # non-ASCII).
    if ch in _NAME_DOT_SEPARATORS or ch in _INVISIBLE_SEPARATORS:
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
        # rules/N1: "a comma inside the clause is kept as written: the
        # comma divides nothing there" -- the Then bullet on a comma: a
        # comma separates only where it records a segmentation offset,
        # the main stream; inside an extracted region it is the clause's
        # text, like ';' (decisions/N1, #653)
        is_separator = ((record_offsets and ch in COMMA_CHARS)
                        or _ignorable(ch, state))
        if (ch == _NARROW_NBSP and start < i < end - 1
                and _mongolian_letter(text[i - 1])
                and _mongolian_letter(text[i + 1])):
            is_separator = False
        if ch in _TRANSCRIPTION_DOTS:
            # Region-local flanks: a B7 at a region edge stays token
            # text, and the bound also stops a custom delimiter's
            # classified edge character from acting as a flank across
            # a mask seam. The scan reads raw characters, not the NFC
            # copy classification reads; the script table holds the
            # conjoining jamo a decomposed syllable is written in, so
            # decomposed hangul flanks as composed hangul does
            # (decisions/nfd-shapes, #1087).
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
                elif ch in _TRANSCRIPTION_DOTS:
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
    # extracted regions: pre-set role; a comma is word text there and an
    # interpunct a mere separator, neither recording an offset
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
            else copy_with(a, indices=_containing(a.origin))
            for a in ambiguities)
    return copy_with(state, tokens=tuple(tokens),
                     comma_offsets=tuple(sorted(commas)),
                     interpunct_offsets=tuple(sorted(interpuncts)),
                     ambiguities=ambiguities)
