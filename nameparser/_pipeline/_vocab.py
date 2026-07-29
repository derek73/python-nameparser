"""Shared vocabulary predicates for pipeline stages.

Text-level tests used by more than one stage; token/piece-level
predicates live with their stage. All take normalized-or-raw text
explicitly -- no state.

Layering: imports _lexicon, _types, and _policy only.
"""
from __future__ import annotations

import re
import unicodedata
from collections.abc import Iterable

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

# Codepoint ranges per Script (#271). This integer table is the single
# source of truth for what a script covers; _SCRIPT_PATTERNS below
# DERIVES the match engine from it. (The sweep here was first written
# per-char on the _EMOJI_RANGES precedent in _tokenize.py, on the
# theory that a range test needs no regex; measured at token scale the
# compiled regex wins by 3-9x, and by 89x on long tokens.)
# HAN: the URO plus Extension A, the compatibility block,
# and the supplementary-plane block (Ext B-I + CJK Compat Ideographs
# Supplement, 0x20000-0x323AF) -- rare surnames are the biggest real
# source of supplementary-plane hanzi in personal names (e.g. 𠮷田's
# 𠮷, U+20BB7), so leaving them out silently mis-orders those names;
# unassigned gaps inside the span are harmless, since no real name
# contains an unassigned codepoint. HANGUL: precomposed syllables
# only -- modern Korean text never writes names as bare jamo.
# HIRAGANA/KATAKANA (#272): the two kana blocks, each in full. There
# IS a supplementary-plane kana repertoire (Kana Supplement, Kana
# Extended-A/B, Small Kana Extension, U+1AFF0-U+1B16F, 311 assigned
# codepoints) but none of it is WORTH chasing the way Han's astral
# block is: those codepoints are hentaigana and other archaic/
# phonetic-extension forms no modern Japanese name uses, unlike
# supplementary Han, which real surnames genuinely need. The Katakana
# Phonetic Extensions block (U+31F0-U+31FF, 16 small katakana for Ainu
# transcription) is excluded for the same reason -- no modern Japanese
# personal name uses them. Halfwidth kana (U+FF65-U+FF9F, including
# the voiced/semi-voiced sound marks U+FF9E/U+FF9F) is likewise
# deliberately excluded -- legacy bank/CSV data uses it, but it is a
# separate normalization problem; Task 2b's separator handling only
# touches the halfwidth DOT (U+FF65), not the rest of that block.
# This table classifies by Unicode BLOCK, not the UAX #24 Script
# property: U+30A0, U+30FB (the middle dot), and U+30FC (the
# prolonged sound mark) all carry Script=Common under UAX #24, and the
# combining kana voicing marks U+3099-U+309C are Common/Inherited --
# yet every one of them is needed here, and block membership, not the
# Script property, is what puts them in range. The katakana block's
# upper end (U+30FF) including the middle dot U+30FB is load-bearing
# for effective_script's kana license below (see its docstring) --
# tokenize (#272 Task 2b) now turns U+30FB into a token separator
# before this classifier ever sees a split string, but effective_script
# is also called directly on whole strings (e.g. in tests), where the
# dot still classifies as ordinary katakana. The ranges below must stay
# mutually disjoint: single_script returns the FIRST covering entry
# (dict iteration order), so an overlapping future script would make
# the result order-dependent instead of well-defined.
_SCRIPT_RANGES: dict[Script, tuple[tuple[int, int], ...]] = {
    Script.HAN: ((0x3400, 0x4DBF), (0x4E00, 0x9FFF), (0xF900, 0xFAFF),
                 (0x20000, 0x323AF)),
    Script.HANGUL: ((0xAC00, 0xD7A3),),
    Script.HIRAGANA: ((0x3040, 0x309F),),
    Script.KATAKANA: ((0x30A0, 0x30FF),),
}

# Derived, never hand-written: one character class per script, in the
# table's own key order (so the FIRST-covering-entry rule above still
# describes what single_script does).
_SCRIPT_PATTERNS: dict[Script, re.Pattern[str]] = {
    script: re.compile(
        "[" + "".join(f"\\U{lo:08x}-\\U{hi:08x}" for lo, hi in ranges)
        + "]+")
    for script, ranges in _SCRIPT_RANGES.items()
}

#: The Japanese repertoire: the union effective_script's kana license
#: quantifies over -- HAN, HIRAGANA, KATAKANA (HANGUL simply omitted).
#: A frozenset, not the tuple this started as: resolve_script_set
#: below is the "later task that needs membership" the tuple's
#: original comment anticipated. Membership doesn't care about order,
#: and the pattern built below doesn't either (a regex character
#: class matches the same set regardless of the order its ranges are
#: written in).
_JA_SCRIPTS = frozenset({Script.HAN, Script.HIRAGANA, Script.KATAKANA})
_JA_PATTERN = re.compile(
    "["
    + "".join(f"\\U{lo:08x}-\\U{hi:08x}"
              for s in _JA_SCRIPTS
              for lo, hi in _SCRIPT_RANGES[s])
    + "]+")


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


def _normalized_for_script(text: str) -> str | None:
    """The guard AND the NFC normalization single_script and
    effective_script's license path both need, single-sourced so they
    cannot drift: None for the two shapes neither ever classifies
    (empty, and the common all-ASCII Latin token -- skipped before
    normalizing, since ASCII is already NFC and every _SCRIPT_RANGES
    entry is non-ASCII regardless), else an NFC-normalized copy.

    NFC, not raw: NFD input decomposes precomposed katakana onto a
    base character plus a COMBINING mark (U+3099/U+309A, which sit in
    the HIRAGANA block, not katakana's), so classifying raw NFD text
    can hand a pure-katakana token the kana license by accident; NFD
    also decomposes Hangul syllables onto bare jamo (U+1100-U+11FF),
    entirely outside the HANGUL range, so raw NFD Korean input misses
    the shipped family-first order rule rather than merely misfiring.
    Normalizing first fixes both. This is classification-only and
    read-only: the returned copy is never what gets tokenized, so
    token text and spans stay exactly what the caller wrote.

    MATCHING (is_initial, suffix lookups, etc.) deliberately stays on
    raw text elsewhere in this module -- unlike script classification,
    NFD only ever costs a match there (a suffix word written NFD fails
    to match its NFC vocabulary entry), never wrong-matches, so the
    asymmetry is safe: one direction needs a fix, the other doesn't.
    """
    if not text or text.isascii():
        return None
    return unicodedata.normalize("NFC", text)


def single_script(text: str) -> Script | None:
    """The one Script whose ranges cover EVERY char of `text`, else
    None (mixed-script text has no well-defined convention to apply;
    the caller falls back to the positional default). Classifies an
    NFC-normalized copy of `text` -- see _normalized_for_script.
    Callers wanting the kana-mixed license (a kanji+kana composite
    resolving to HIRAGANA) want effective_script, not this function."""
    normalized = _normalized_for_script(text)
    if normalized is None:
        return None
    for script, pattern in _SCRIPT_PATTERNS.items():
        if pattern.fullmatch(normalized):
            return script
    return None


def effective_script(text: str) -> Script | None:
    """single_script, extended by the kana license (#272 amendment):
    a MIXED token wholly within Han∪hiragana∪katakana is Japanese --
    it necessarily contains kana (pure Han is not mixed), cannot be
    Chinese, and is not a foreign transcription (those are
    katakana-only: マイケル has no kanji, but さくらエミ -- hiragana
    plus katakana -- is kana-only AND licensed) -- and resolves to the
    HIRAGANA carrier entry. Pure-katakana stays KATAKANA
    (single_script's answer): a lone katakana token is predominantly a
    transcribed foreign name, so nothing defaults on it."""
    script = single_script(text)
    if script is not None:
        return script
    # Renormalizes text that single_script (above) already normalized
    # once: deliberately NOT hoisted into a shared `_classify(normalized)`
    # helper. The second call only runs on the fall-through path (a
    # token single_script could not classify at all, i.e. genuinely
    # mixed-script or empty/ASCII), never on the common single-script
    # hit above, so it is a quick re-check on already-NFC text, not
    # measured work -- the per-char-vs-regex history in this module's
    # header is what a real cost here would look like, and this isn't
    # it.
    # normalized is None for both shapes _JA_PATTERN could never match
    # anyway (empty text, or the all-ASCII text single_script's fast
    # path already ruled out) -- real work, not a leftover "if text"
    # guard: unlike the pre-NFC version, None here also covers the
    # ASCII case, which single_script's own empty check alone would
    # not.
    normalized = _normalized_for_script(text)
    if normalized is not None and _JA_PATTERN.fullmatch(normalized):
        return Script.HIRAGANA
    return None


def resolve_script_set(scripts: Iterable[Script]) -> Script | None:
    """Generalizes effective_script's kana license from one token's
    CHARACTERS to a whole name's PIECES (#272): `scripts` is the
    effective_script of every name token, already resolved
    individually -- '高橋' (Han) and 'みなみ' (Hiragana) are two
    separately single-script pieces (split by a space, not mixed
    within one token), but together are exactly the repertoire
    effective_script licenses inside a single token (高橋みなみ). A
    single distinct script is returned as-is (the ordinary case,
    including a lone wholly-katakana name, which callers key with no
    table entry); more than one collapses to the HIRAGANA carrier
    when confined to Han/Hiragana/Katakana, the same set
    effective_script's license tests; any other mix (Han+Hangul, or
    no scripts at all -- an empty `scripts`) returns None -- the
    caller's cue to fall back to the positional default, exactly like
    effective_script's own None. A non-None result reports what was
    FOUND, not that a license fired: callers wanting to know whether
    the kana license specifically was the reason must compare the
    result against a specific Script (e.g. `is Script.HIRAGANA`), not
    just its truthiness -- a lone wholly-Han name also returns
    non-None here, licensing nothing."""
    found = frozenset(scripts)
    if len(found) <= 1:
        return next(iter(found), None)
    if found <= _JA_SCRIPTS:
        return Script.HIRAGANA
    return None
