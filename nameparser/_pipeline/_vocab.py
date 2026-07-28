"""Shared vocabulary predicates for pipeline stages.

Text-level tests used by more than one stage; token/piece-level
predicates live with their stage. All take normalized-or-raw text
explicitly -- no state.

Layering: imports _lexicon, _types, and _policy only.
"""
from __future__ import annotations

import re

from nameparser._lexicon import Lexicon, _normalize
from nameparser._policy import Script

# Ported verbatim from v1 (nameparser/config/regexes.py "initial") minus
# its empty-string alternative -- WorkToken text is never empty. Kept in
# sync by hand; layering forbids importing the config package here.
_INITIAL = re.compile(r"^(\w\.|[A-Z])$")

# Ported verbatim from v1 (nameparser/config/regexes.py
# "period_not_at_end") -- layering forbids the config import; keep in
# sync by hand.
_PERIOD_NOT_AT_END = re.compile(r".*\..+$", re.I)

# The fix_phd credential pair ('Ph.' + 'D.' as adjacent tokens), shared
# by segment's suffix-comma detection and group's merge (v1 extracted
# the credential pre-parse; the two stages must agree on the pattern).
PH = re.compile(r"^ph\.?$", re.IGNORECASE)
D = re.compile(r"^d\.?$", re.IGNORECASE)

# Codepoint ranges per Script (#271): integer ranges following the
# _EMOJI_RANGES precedent in _tokenize.py -- the per-char test needs
# no regex. HAN: the URO plus Extension A, the compatibility block,
# and the supplementary-plane block (Ext B-I + CJK Compat Ideographs
# Supplement, 0x20000-0x323AF) -- rare surnames are the biggest real
# source of supplementary-plane hanzi in personal names (e.g. 𠮷田's
# 𠮷, U+20BB7), so leaving them out silently mis-orders those names;
# unassigned gaps inside the span are harmless, since no real name
# contains an unassigned codepoint. HANGUL: precomposed syllables
# only -- modern Korean text never writes names as bare jamo. Kana is
# DELIBERATELY absent: a kana token identifies Japanese, whose
# conventions are #272's segmenter, not this table's. The ranges
# below must stay mutually disjoint: single_script returns the FIRST
# covering entry (dict iteration order), so an overlapping future
# script (e.g. a ja entry that also covers Han) would make the result
# order-dependent instead of well-defined.
_SCRIPT_RANGES: dict[Script, tuple[tuple[int, int], ...]] = {
    Script.HAN: ((0x3400, 0x4DBF), (0x4E00, 0x9FFF), (0xF900, 0xFAFF),
                 (0x20000, 0x323AF)),
    Script.HANGUL: ((0xAC00, 0xD7A3),),
}


def is_initial(text: str) -> bool:
    """'A.' / 'j.' / bare capital -- v1's is_an_initial."""
    return bool(_INITIAL.fullmatch(text))


def suffix_as_written(n: str, text: str, lexicon: Lexicon) -> bool:
    """Counts as a suffix as written, with NO initial veto (the veto
    differs by caller): unambiguous suffix vocabulary, or an ambiguous
    acronym written with periods ('M.A.' yes, 'Ma' no). `n` is
    _normalize(text), passed in so callers normalize once.

    Single source for classify's "vocab:suffix" tag and the segment/
    assign predicates. The ambiguous subset is EXCLUDED from the plain
    membership test: in the real data suffix_acronyms_ambiguous is a
    subset of suffix_acronyms, and without the exclusion the period
    gate is dead code (bare 'Ed'/'Jd' would silently become suffixes).
    """
    # acronyms may be written with periods ('M.B.A.'): the ACRONYM
    # membership alone uses the period-free form (v1's is_suffix
    # removed periods only for the suffix_acronyms test); suffix WORDS
    # match on the plain normalized form
    a = n.replace(".", "")
    if "." in text and a in lexicon.suffix_acronyms_ambiguous:
        return True
    return (a in lexicon.suffix_acronyms
            and a not in lexicon.suffix_acronyms_ambiguous) \
        or n in lexicon.suffix_words


def _is_suffix_strict_n(n: str, text: str, lexicon: Lexicon) -> bool:
    if is_initial(text):
        # period-written ambiguous acronyms are exempt from the veto
        return "." in text and \
            n.replace(".", "") in lexicon.suffix_acronyms_ambiguous
    return suffix_as_written(n, text, lexicon)


def is_suffix_strict(text: str, lexicon: Lexicon) -> bool:
    """v1's is_suffix: suffix_as_written with the initial veto ('V.' in
    'John V. Smith' is a middle initial, not roman five)."""
    return _is_suffix_strict_n(_normalize(text), text, lexicon)


def is_suffix_lenient(text: str, lexicon: Lexicon) -> bool:
    """v1's is_suffix_lenient: suffix_words accepted unconditionally,
    bypassing the initial veto -- only safe in unambiguous positions
    (after a comma)."""
    n = _normalize(text)
    return n in lexicon.suffix_words \
        or _is_suffix_strict_n(n, text, lexicon)


def delimiter_cores(policy_delimiters: frozenset[str]) -> frozenset[str]:
    """Configured suffix delimiters with surrounding whitespace
    stripped: ' - ' -> '-'. Whitespace-padded delimiters surface as
    standalone tokens; the stripped core is what tokenize produced."""
    return frozenset(d.strip() for d in policy_delimiters if d.strip())


def splits_into_suffixes(text: str, cores: frozenset[str],
                         lexicon: Lexicon) -> bool:
    """v1 expand_suffix_delimiter parity for delimiters WITHOUT
    whitespace ('RN/CRNA' with '/'): the token counts as a suffix when
    some core splits it into >=2 non-empty parts that are all suffixes.
    The token text is never rewritten (anti-#100): it takes Role.SUFFIX
    whole, which renders 'RN/CRNA' where v1 rendered 'RN, CRNA' -- the
    documented divergence, release-log classified."""
    for core in cores:
        if core in text:
            parts = [part for part in text.split(core) if part]
            if len(parts) >= 2 and all(
                    is_suffix_lenient(part, lexicon) for part in parts):
                return True
    return False



def period_joined_vocab(text: str, lexicon: Lexicon) -> str | None:
    """v1's parse_pieces derivation for interior-period tokens
    ('Lt.Gov.', 'Msc.Ed.', and by the ANY rule 'Mr.Smith'): ANY title
    chunk makes the token a title (checked first, v1's continue); else
    ANY suffix chunk makes it a suffix. Chunk-level suffix membership
    is v1's is_suffix: bare ambiguous acronyms COUNT ('Msc.Ed.'
    derives via 'ed') -- the ambiguous period-gate applies to whole
    tokens only. Returns "title", "suffix", or None."""
    if not _PERIOD_NOT_AT_END.match(text):
        return None
    chunks = [_normalize(c) for c in text.split(".") if c]
    if any(c in lexicon.titles for c in chunks):
        return "title"
    if any(c in lexicon.suffix_acronyms or c in lexicon.suffix_words
           for c in chunks):
        return "suffix"
    return None


def single_script(text: str) -> Script | None:
    """The one Script whose ranges cover EVERY char of `text`, else
    None (mixed-script text has no well-defined convention to apply;
    the caller falls back to the positional default)."""
    for script, ranges in _SCRIPT_RANGES.items():
        if all(any(lo <= ord(c) <= hi for lo, hi in ranges)
               for c in text):
            return script
    return None
