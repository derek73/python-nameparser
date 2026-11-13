"""Shared vocabulary predicates for pipeline stages.

Text-level tests used by more than one stage; piece-level ones live
in _pieces, the sibling layer over tokens-plus-tags. All take
normalized-or-raw text explicitly and no state, with the departures
named below.

is_wholly_suffix departs from that shape twice, deliberately. It is
RUN-level rather than text-level, because the question it answers is
genuinely about a run: the Ph./D. merge spans two tokens, so no
per-token predicate composed with all() can express it. And it takes
the Policy OBJECT, where delimiter_cores takes a pre-extracted
frozenset so its caller hands in one field rather than the config --
is_wholly_suffix needs TWO policy fields (lenient_comma_suffixes and
extra_suffix_delimiters), and threading both past every caller costs
more than the config parameter saves. Still no state: Policy is frozen
config, not pipeline state.

maiden_marker_run is run-level for the first of those reasons and not
the second: a maiden marker may be a PHRASE ('z domu'), so how far one
reaches is a question about a run of words that no per-word membership
test can answer, and the vocabulary reaches it as a plain frozenset
field like every other predicate here.

tag_marker_runs is the third departure, and the reason this module also
imports _state (WorkToken, comma_bucket): deciding which tokens open a
maiden-marker RUN needs each token's role and span, not its text alone,
because a run must not cross a role change or a comma. It moved here
from classify (#289/#516) so _pieces.own_words -- which may import
only _state and _vocab (tests/v2/test_layering.py) -- can call the
SAME function classify does rather than approximating it with a
text-only walk. Two callers building a map from the same tokens with
the same function cannot disagree, which a from-scratch approximation
could (measured: 'ANNA z Nowak, MD' flips the one-case verdict when
the approximation and the real run-completion test disagree on
whether 'z' opens a run that completes).

suffix_reading, name_reading and the two reading constants are the
fourth: they answer no question about a word but BUILD the reading a
report did not take (#752 phase 2m), from a token's text and tags,
which is why they import _state's PendingReading and the public enums
it re-exports. They sit here because every stage that reports a fork
builds one, and the tags they read are this module's vocabulary.

Layering: imports _lexicon, _policy, and _pipeline._state (WorkToken,
comma_bucket, PendingReading -- read-only, never a whole ParseState).
"""
from __future__ import annotations

import functools
import re
import string
import unicodedata
from collections.abc import Callable, Iterable, Sequence, Set
from typing import Literal

from nameparser._lexicon import (
    FULL_STOPS, Lexicon, _VOCAB_FIELDS, _normalize, _spells_an_initial,
)
from nameparser._policy import (
    CapsSuffixes, Policy, Script, _CASELESS_LETTERS, _EAST_ASIAN_SCRIPTS,
    _JA_SCRIPTS, _NO_ABBREVIATION_RANGES, _NO_INITIAL_RANGES, _SCRIPT_RANGES,
    _SPELLED_INITIAL_RANGES, _ranges_matcher, _ranges_pattern, _script_matcher,
)
from nameparser._pipeline._state import (
    AGNOMEN_TAG, AMBIGUOUS_ACRONYM_TAG, AMBIGUOUS_WORD_TAG, CAPITALS_FAMILY_TAG,
    COMMA_CHARS, COMMA_STRIP,
    CREDENTIAL_WORD_TAG, Deferred, GENERATION_WORD_TAG,
    GIVEN_ABBREVIATION_TAG, HONORIFIC_WORD_TAG, PATRONYMIC_TAG, SHAPE_ACRONYM_TAG,
    TITLE_AMBIGUOUS_TAG, PendingReading, ReadingKind, ReadingSource, Role, WorkToken,
    comma_bucket,
)

# Ported verbatim from v1's "initial" pattern (the 1.x and 2.x
# nameparser.config.regexes, removed in 3.0, #1008) minus its
# empty-string alternative -- WorkToken text is never empty. _render
# holds a hand copy, pinned to this one by tests/v2/test_regex_sync.py.
# "Verbatim" is a promise about the PATTERN, not about the predicate:
# since #320 is_initial is this SHAPE test ANDed with a repertoire test
# (in_initialless_script, below), so _INITIAL.fullmatch(text) and
# is_initial(text) are no longer the same question -- '씨.' answers yes
# to the first and no to the second. Call is_initial; the bare pattern
# is not the thing to ask. The narrowing lives in the predicate
# precisely so this copy can stay exactly as verbatim as it ever was,
# the pattern _render's copy must equal.
_INITIAL = re.compile(r"^(\w\.|[A-Z])$")

# Ported verbatim from v1's "period_not_at_end" pattern (the 1.x and
# 2.x nameparser.config.regexes, removed in 3.0, #1008).
_PERIOD_NOT_AT_END = re.compile(r".*\..+$", re.I)

# The fix_phd credential pair ('Ph.' + 'D.' as adjacent tokens),
# `split_pair`'s first answer, below.
_PH = re.compile(r"^ph\.?$", re.IGNORECASE)
_D = re.compile(r"^d\.?$", re.IGNORECASE)
#: `split_pair`'s necessary half on its FIRST word for the Ph./D.
#: answer alone, asked C-level by `is_wholly_suffix` ahead of the
#: call, the one caller that asks only that answer and has no tags to
#: read. The same compiled object the predicate asks, so the two
#: cannot drift.
SPLIT_PAIR_OPENS = _PH


# The codepoint table lives in _policy beside Script -- one copy
# importable from the pipeline and the locale packs alike; everything
# here DERIVES from it. (single_script's sweep was first written
# per-char on the _EMOJI_RANGES precedent in _tokenize.py, on the
# theory that a range test needs no regex; measured at token scale the
# compiled regex wins by 3-9x, and by roughly 70x on long tokens.)
# Derived, never hand-written -- even the class construction goes
# through the shared factory: one wholly-of predicate per script, in
# the table's key order -- the FIRST-covering-entry rule _classify
# documents.
_SCRIPT_MATCHERS: dict[Script, Callable[[str], bool]] = {
    script: _script_matcher(script, whole=True)
    for script in _SCRIPT_RANGES
}
#: The East Asian matchers _classify tries in turn, and the characters a
#: Cyrillic word can open with: a token opening with none of them is no
#: Cyrillic, which a C-level membership test says without the matcher's
#: frame, so a non-ASCII Latin word pays nothing for Cyrillic (#1237)
_EAST_ASIAN_MATCHERS = tuple((script, _SCRIPT_MATCHERS[script])
                             for script in _EAST_ASIAN_SCRIPTS)
_CYRILLIC_LETTERS = frozenset(chr(c) for lo, hi in _SCRIPT_RANGES[Script.CYRILLIC]
                              for c in range(lo, hi + 1))

#: The joiners a Cyrillic name word is written with inside it, hyphens
#: and the apostrophes Ukrainian and Belarusian write (`Оюун-Эрдэнэ`,
#: `Мар'яна`), deleted from the classified copy of a word that neither
#: opens nor ends with one,
#: so a hyphenated Cyrillic word keys a declared Cyrillic order as a
#: plain one does (#1237); the shared table stays letters only, since
#: the East Asian readers of it never see these.
_CYRILLIC_JOINERS = "-\u2010\u2011'\u2019\u02bc"
_DROP_CYRILLIC_JOINERS = str.maketrans("", "", _CYRILLIC_JOINERS)

# The whole-token matcher over _policy's _JA_SCRIPTS union, backing
# effective_script's kana license.
_wholly_ja = _script_matcher(*_JA_SCRIPTS, whole=True)

# The four kana voicing marks U+3099-U+309C (#596). None belongs to
# either syllabary -- each voices the kana it follows -- but the script
# table classifies by block and all four sit in the HIRAGANA one, so a
# mark NFC cannot compose (ア + U+3099) made a katakana token read as
# katakana plus hiragana and took the kana license.
# _normalized_for_script drops every mark standing after a KANA, so the
# mark takes its base's script. After anything else -- hangul, Han,
# Latin, or nothing at all -- the mark is not voicing a kana and keeps
# the table's answer: deleting it there would hand 김゙민준 a script the
# surname site then divides on the RAW text, cutting the mark off its
# base and leaving it to open the given name.
_VOICING_MARKS = frozenset("\u3099\u309a\u309b\u309c")

# Whole-text kana test for one character: the base a voicing mark may
# be dropped after.
_is_kana = _script_matcher(Script.HIRAGANA, Script.KATAKANA, whole=True)


def _drop_kana_voicing_marks(text: str) -> str:
    """`text` without the voicing marks that follow a kana (a run of
    them included); every other mark kept. Called only on text holding
    a mark, so names without one never pay for the walk."""
    kept: list[str] = []
    after_kana = False
    for ch in text:
        if ch in _VOICING_MARKS:
            if after_kana:
                continue
        else:
            after_kana = _is_kana(ch)
        kept.append(ch)
    return "".join(kept)

# The repertoire half of is_initial (_policy._SCRIPT_PROPERTIES'
# writes_initials), kept apart
# from _INITIAL's SHAPE half so the pattern itself stays v1-verbatim
# and _render's copy stays pinned to it by tests/v2/test_regex_sync.py.
# contains-any, not whole=True: the shape half has already admitted the
# trailing period, so the text reaching here is '씨.' rather than '씨'
# and a wholly-of match would be False for every case this exists for.
_has_initialless_char = _ranges_matcher(_NO_INITIAL_RANGES, whole=False)
# The H2 shape's repertoire veto (_SCRIPT_PROPERTIES'
# period_abbreviations). is_title_shaped admits two or more
# characters, so contains-any there means one CJK character anywhere
# vetoes the whole word -- 'Kim김.' is refused as a title along with
# '田中.' -- and that is deliberate: a word carrying a script with no
# abbreviations is not wearing an abbreviation's period.
_has_unabbreviating_char = _ranges_matcher(_NO_ABBREVIATION_RANGES,
                                           whole=False)


def in_initialless_script(text: str) -> bool:
    """Whether TEXT holds a character of a script that writes no
    initials (#320), asked of the composed spelling, the one every
    shape test beside it reads, so the veto and the shape read one
    spelling (decisions/nfd-shapes, #665, #1087). ASCII answers without the
    matcher's frame, as the callers' own `isascii()` gates do."""
    return (not text.isascii()
            and _has_initialless_char(unicodedata.normalize("NFC", text)))


def in_unabbreviating_script(text: str) -> bool:
    """Whether TEXT holds a character of a script that writes no period
    abbreviation (rules/H2, #323), asked of the composed spelling as
    `in_initialless_script` is, the two being separate questions that
    the four East Asian rows answer alike (#1256)."""
    return (not text.isascii()
            and _has_unabbreviating_char(unicodedata.normalize("NFC", text)))


# H2's own shape, text-level: an unlisted period-marked abbreviation,
# two or more letters, one trailing period. Moved here from _pieces
# (#289/#516, quality-review finding) so _vocab.name_word_count can
# ask the SAME question _pieces.is_leading_title asks -- measured
# divergence before the move: 'Dr. Smith, Ed' (LISTED title 'Dr.') and
# 'Xyz. Smith, Ed' (UNLISTED, H2-shaped) both read family 'Dr.
# Smith'/'Xyz. Smith', given 'Ed' at the peel (since #701 the listed
# 'Dr.' then peels into the title, rules/H6), because is_leading_title
# reads H2's shape and a bare `folded in lexicon._sets.titles` lookup does
# not -- but name_word_count's OWN count disagreed: 'Xyz.' counted as
# a name word where 'Dr.' did not, so 'Xyz. Smith, Ed' alone flipped
# the comma structure to a credential run
# (mechanisms.md#ONE-PREDICATE-PER-QUESTION).
#
# v1's "period_abbreviation" shape, composed from `_LETTER` below, so
# the text is v1's plus the marks. This is the only definition:
# `_pieces._PERIOD_ABBREV` is an import of it, which
# tests/v2/test_regex_sync.py declares as such.

# `_LETTER` is the letter every shape regex in this module spells
# (`_PERIOD_ABBREV`, `_DOTTED`, `_CHUNKED`, `_PAIRED_INITIALS`): one
# letter (a word character that is not a digit or underscore) plus the
# combining marks written after it (#652). `inž.` typed as i, n, z,
# U+030C, '.' is the same word as the composed one, and `\w` alone ends
# it at the z. `_MARKS` is the general combining blocks -- what NFD of
# a Latin, Greek or Cyrillic letter produces -- and not the marks that
# only some scripts write (Indic vowel signs, Arabic and Hebrew
# points); rules/H2's Accepted bullet "The shape is only recognizable
# as an unbroken run of letters" owns that limit (decisions/H2).
_MARKS = '[\u0300-\u036f\u1ab0-\u1aff\u1dc0-\u1dff\u20d0-\u20ff\ufe20-\ufe2f]'
_LETTER = r'[^\W\d_]' + _MARKS + '*'
_PERIOD_ABBREV = re.compile(r'^(?:' + _LETTER + r'){2,}\.$')

# rules/H2: "A word in one of the ten Brahmic scripts from Devanagari
# to Sinhala" "never reads as a title by shape, even where it is a run
# of letters" -- the rows of _policy._SCRIPT_PROPERTIES whose
# spells_initials holds, U+0900 to U+0DFF. A vowel sign
# already breaks `_LETTER`'s run, but a spelled initial written with
# none (एम. for M., এম., ਐਮ.) is a run of two letters, and the shape
# read it as a title; these scripts write initials, so the veto is the
# title shape's alone and not `is_initial`'s (decisions/H2, #1191).
# Searched on the raw text: a nukta letter decomposes inside the range.
_SPELLED_INITIAL = _ranges_pattern(_SPELLED_INITIAL_RANGES)

# rules/H2: "A transliteration digraph" "never reads as a title by
# shape" -- the digraphs that Except names, lowercase and periodless,
# so the test is a C-level membership of the word less its period;
# the Except itself names the digraphs it leaves out (Ts, Ch, Sh) --
# decisions/H2 (#1136).
_DIGRAPH_INITIALS = frozenset({"yu", "ya", "ye", "yo", "zh", "kh",
                               "shch", "dzh"})

#: The hyphens and the dashes that join two family names in one written
#: word (rules/O6), and the parts of an abbreviation written hyphenated
#: (rules/H5, 'Dipl.‐Ing.' as a word processor writes it): hyphen-minus,
#: hyphen, non-breaking hyphen, figure dash, en dash, minus sign (a word
#: processor's substitute), and the small and fullwidth hyphen-minus.
#: The em dashes are punctuation between words, not joiners, and are
#: left out. Hyphen-minus first, so it is literal inside a class.
_HYPHEN_CHARS = "-\u2010\u2011\u2012\u2013\u2212\ufe63\uff0d"
_HYPHENS = re.compile("[" + _HYPHEN_CHARS + "]")

# rules/H5: "A word that ends in a period and is written with a
# period or a hyphen inside it wears the abbreviation shape too" --
# the trailing chain's shape, _PERIOD_ABBREV widened to 'Priv.-Doz.',
# 'Dipl.Ing.' and 'Lt.Col.'. It opens and closes on a letter and ends
# in one period, so every _PERIOD_ABBREV match is one of its matches;
# the front slot's H2 shape stays _PERIOD_ABBREV (decisions/H5, #1116).
_TRAILING_TITLE_SHAPE = re.compile(
    r'^' + _LETTER + r'(?:' + _LETTER + r'|[' + _HYPHEN_CHARS + r'.])*'
    + _LETTER + r'\.$')

# rules/H5: "a title the vocabulary lists whole with a period inside
# it chains without a final one" -- the letters of such a listing
# joined by periods and hyphens ('dott.ssa', 'priv.-doz'), read by
# classify on the normalized word, which has no edge periods, ANDed
# there with a period test, since the pattern alone admits a word a
# hyphen alone joins ('co-founder'); a digit keeps a rank written with
# a period (a caller's 'cwo.3') out (decisions/H5, #1104).
_JOINED_WORD = re.compile(
    r'^(?:' + _LETTER + r')+(?:[' + _HYPHEN_CHARS + r'.]+(?:'
    + _LETTER + r')+)+$')


# rules/H2: "an abbreviation opening the part of the name that
# carries the given name — the whole name, or the part after a
# family comma — reads as a title even when unlisted"
# (history: decisions/H2)
def is_title_shaped(text: str, lexicon: Lexicon) -> bool:
    """Whether TEXT reads as a title by H2's shape -- the LISTED half
    being a separate lookup at each caller's own site
    (is_title_piece/lexicon._sets.titles), and the one vocabulary read here
    the given name written short, which outranks the shape (rules/H2,
    #789: 'Chas.' is no title). `name_word_count`, `title_readings`
    (classify's rules/H9 phrase test) and `_assemble`'s source of a
    title no vocabulary tags are its callers; `_pieces.is_leading_title`
    asks the same question but keeps this body inline, its path being
    hot (every leading piece of every parse) where these run only on a
    comma name, a name holding a contested title or modifier, or an
    untagged title token
    -- the measured figure lives at that inline copy and is not
    restated here, two homes for one measurement being how they come
    to disagree. Touch one, touch both:
    `test_pieces.test_is_title_shaped_and_is_leading_title_agree`
    runs both over the union of the two example tables, so the
    agreement is checked rather than asserted in prose
    (mechanisms.md#ONE-PREDICATE-PER-QUESTION).

    The shape reads a Latin convention: a period marks an
    abbreviation, and a script that writes no period abbreviations
    (_policy._SCRIPT_PROPERTIES' period_abbreviations) has nothing for
    one to mark, so a CJK word wearing a period is a name word, not a
    title -- a lone '田中.' is the family name (#323). The four East
    Asian rows write no initials either; Thai writes no initials but
    writes its titles short, so the two are separate columns (#1256).
    `_PERIOD_ABBREV` stays ASCII-period only: a word wearing '。' never
    matches it, and the veto is what makes the ASCII spelling agree.
    ASCII text can carry no such character (every range sits
    above U+3000), so the C-level test declines before the regex
    search runs -- four frames per unlisted-abbreviation opener per
    parse, this running four times per piece.

    A word holding a letter of the ten Brahmic scripts from Devanagari
    to Sinhala is refused too (`_SPELLED_INITIAL`, rules/H2's Except,
    #1191): those scripts write initials, and spell a Latin one out by
    its sound with no vowel sign (एम. for M.), a run of letters the
    shape would misread. Its search is C-level, so it costs no frame.

    A transliteration digraph (`Yu.`, `Zh.`, `Kh.`, `_DIGRAPH_INITIALS`)
    declines the shape too, being the initial of one Cyrillic letter
    (rules/H2's transliteration-digraph Except, #1136).
    """
    return (bool(_PERIOD_ABBREV.match(text))
            and (text.isascii() or not (_SPELLED_INITIAL.search(text)
                                        or in_unabbreviating_script(text)))
            and text[:-1].lower() not in _DIGRAPH_INITIALS
            and _normalize(text) not in lexicon._sets.given_name_abbreviations)


def is_initial_shaped(text: str) -> bool:
    """v1's is_an_initial verbatim: the SHAPE half alone -- one word
    character plus a period, or a bare ASCII capital.

    Callers asking whether a token is STRUCTURALLY part of an initial
    run want this; callers asking whether it can really stand in for a
    name want is_initial (#320). The two answers differ only inside
    scripts that write no initials, where '씨.' is initial-SHAPED but is not an
    initial -- see assign's roman-numeral fork, the shape caller, for
    what picking the wrong one costs.

    Asked of the composed spelling, as `_render` asks it (#542): `\\w`
    does not match a combining mark, so a decomposed 'É.' is three
    characters to the pattern and no initial (#665). Composing rather
    than widening keeps the pattern v1-verbatim, and both calls are
    C-level, so the predicate costs no frame it did not before."""
    if not text.isascii():
        text = unicodedata.normalize("NFC", text)
    return bool(_INITIAL.fullmatch(text))


# v1's "roman_numeral" pattern; _render's hand copy is pinned to this
# one by tests/v2/test_regex_sync.py.
_ROMAN = re.compile(r'^(X|IX|IV|V?I{0,3})$', re.I)
#: The same pattern, shared rather than copied: `_comma` filters on
#: it before asking `reads_as_generation` (rules/C12).
ROMAN = _ROMAN


# Ported verbatim from v1's patterns (the 1.x and 2.x
# nameparser.config.regexes, removed in 3.0, #1008), the RU and TR_AZ
# packs' copies pinned to these by tests/v2/test_locales.py: the East
# Slavic patronymic endings and the standalone Turkic patronymic
# markers, which rules/O1's and O2's rotations and rules/R9's reading
# ask through the two predicates below.
_EAST_SLAVIC = re.compile(
    r"(ovich|ovna|evich|evna|ichna|ilyich|kuzmich|lukich|fomich|fokich|nikitich|savvich)$",
    re.I)
_EAST_SLAVIC_CYR = re.compile(
    r"(ович|овна|евич|евна|ична|ильич|кузьмич|лукич|фомич|фокич|никитич|саввич)$",
    re.I)
_TURKIC = re.compile(
    r"^(oglu|oğlu|ogly|ogli|o['’ʻ‘ʼ`]g['’ʻ‘ʼ`]li"
    r"|qizi|qızı|kizi|kyzy|gyzy|uly|uulu)$", re.I)
_TURKIC_CYR = re.compile(
    r"^(оглу|оглы|оғлу|ўғли|угли|кызы|гызы|қызы|қизи|улы|ұлы|уулу)$", re.I)


def has_patronymic_ending(text: str) -> bool:
    """Whether `text` ends in an East Slavic patronymic ending, Latin or
    Cyrillic ("Ivanovich", "Петрович"): rules/O1's test and, under
    `PatronymicRule.EAST_SLAVIC`, rules/R9's."""
    return bool(_EAST_SLAVIC.search(text) or _EAST_SLAVIC_CYR.search(text))


def is_patronymic_marker(text: str) -> bool:
    """Whether `text` is a standalone Turkic patronymic marker ("oglu",
    "кызы"): rules/O2's test and, under `PatronymicRule.TURKIC`,
    rules/R9's. Asked of the word NFC-composed (#1316): `oğlu` written
    with a combining breve is the same marker, the vocabulary path's fold
    applied to a shape test; the fold is inline behind `isascii()` so a
    plain word costs no frame."""
    if not text.isascii():
        text = unicodedata.normalize("NFC", text)
    return bool(_TURKIC.match(text) or _TURKIC_CYR.match(text))


# rules/O1: "whose last name word carries a patronymic ending and whose
# middle name word does not reads as family-first" -- the word test of
# the rotation, shared with the group suggester (nameparser/_suggest.py),
# which counts a patronymic vote where this rule can read one
# (decisions/group-suggestion)
def east_slavic_rotates(middle: str, last: str) -> bool:
    """Whether the middle and last of three name words have rules/O1's
    family-first shape: the ending on the last word and not on the
    middle one. The word count and the initials beside it are the
    caller's."""
    return has_patronymic_ending(last) and not has_patronymic_ending(middle)


# rules/S10: "the numeral reads as the generation: the numerals the
# vocabulary lists, and those up to X it does not, by their shape
# alone" -- its Then clause, the `_ROMAN` test; and rules/S10's Except
# bullet "An initial in front makes it a name word too", the two
# is_initial_shaped tests on `preceding`. The words-to-spare count,
# rules/S10's Except bullet "A numeral of one letter needs words to
# spare", is the callers'. decisions/S10 (#718, #721)
# mechanisms.md#ONE-PREDICATE-PER-QUESTION ("exactly one predicate answers it and every other site calls that one")
# -- the numeral's predicate, which every numeral rule asks
# (decisions/vocabulary-model, #752; #784, #774, #819)
def reads_as_generation(text: str, tags: Set[str], preceding: str | None,
                        one_case: bool | None) -> bool:
    """Whether a word reads as the generation: S10's roman-numeral
    fork, asked by every rule that weighs a numeral (#752). For a
    one-letter numeral a necessary condition only: the words-to-spare
    count is the caller's, which alone knows where the name's words
    are (rules/S10, #718).

    A numeral is I to X by shape, written with its periods or without
    ('VI.', the German ordinal), save that a single letter written
    with its period is an initial (rules/T5). The vocabulary's own
    numerals of two or more letters ('ii' to 'iv', `tags` carrying
    `vocab:suffix`) are the generation whatever stands around them,
    the vocabulary settling them; the rest ('vi' to 'x', and the
    one-letter 'i' and 'v') are weighed:

    - an initial in front makes the numeral a name word: `preceding`
      is the first token of the piece in front, read for layout, and
      None where the slot never asks (the given part after a family
      comma, where 'Chang, Andy C I' reads suffix 'I', v1's reading);
    - a Title-case numeral in a name of mixed case leans to the name,
      as a Title-case member of the ambiguous class does
      (`numeral_leans_to_the_name`).

    In the given part after a family comma (`preceding` None) a
    one-letter numeral is the generation only where the vocabulary
    lists it, rules/C9's "one-character suffix word": no count is
    asked there (S5), and an unlisted letter is the middle initial
    ('SMITH, JOHN X').

    is_initial_shaped, not is_initial: this asks whether the preceding
    piece looks like part of an initial run, which is a question
    about layout, and #320 narrowed the tag to initials that can
    really stand in for a name. Reading the tag here made '씨.' stop
    suppressing the fork and cost 'John 씨. V' its family name.

    `one_case` is ParseState.one_case: in a name written in one case
    the word in front is read as its capital would be, so a bare 'j'
    is initial-shaped as 'J' is (rules/S10, #721's review: 'john j v'
    reads as 'JOHN J V'), while 'é', 'ж' or an uncased word, whose
    capitals are not, stay as they were. None (the maiden take's
    superset view passes it) asks neither case question, which admits
    more and so stays a superset."""
    stem = text.rstrip(".")
    if not stem or _ROMAN.match(stem) is None:
        return False
    if len(stem) == 1:
        # rules/T5: "A one-letter word written with its period is an
        # initial"
        if len(text) > 1:
            return False
        if preceding is None:
            return "vocab:suffix" in tags
    elif "vocab:suffix" in tags:
        return True
    elif one_case is False and stem.istitle():
        return False
    return (preceding is None
            or not (is_initial_shaped(preceding)
                    or one_case and is_initial_shaped(preceding.upper())))


# rules/C3: "a numeral ending the part, or standing before the listed
# suffix words it ends with, that the trailing fork reads as the generation is
# no name word" -- asked of the shape-only numerals,
# the listed ones being suffix words to every count that asks it already;
# decisions/C3 (#893)
def ends_in_a_generation(texts: Sequence[str], one_case: bool | None,
                         ) -> bool:
    """Whether the second of `texts`, two words of a name, is a
    numeral of two or more letters that the trailing fork reads as the
    generation behind the first. It reads no tags, so a listed numeral
    ('III') answers True too: each caller passes only a word it has not
    already read as a suffix, which leaves the unlisted VI to IX, and
    finds the two words itself, the numeral ending the name words past
    any suffix words behind it."""
    last = texts[-1]
    return (len(last.rstrip(".")) >= 2
            and reads_as_generation(last, frozenset(), texts[-2], one_case))


#: What a word of a clause S1 sets apart is: a title, a suffix, or a
#: word that is both, its place in the name choosing (rules/S1).
SetApartKind = Literal["title", "suffix", "dual"]


# rules/S13: "Written with a period inside it, whatever case the name is
# in" -- the writing that settles a member, asked of its text since a
# clause word carries no shape tag (decisions/S13, #810, #1088)
def dotted_member(word: str, lexicon: Lexicon) -> bool:
    """Whether a word of a delimited clause is a member of the
    ambiguous class (S4) written with a period inside it ('M.A',
    'M.A.'), a comma the clause keeps on it left off (rules/N1). A
    period ending the clause is extract's escape, not this."""
    bare = word.strip(COMMA_STRIP)
    return ("." in bare.strip(".")
            and _normalize(bare).replace(".", "")
            in lexicon._sets.suffix_acronyms_ambiguous)


# rules/S1: "a clause wholly of words the vocabulary reads as no name
# is set apart from the name" -- the word's half; `set_apart` is the
# clause's. Its suffix half is `suffix_as_written`'s, so a credential
# joined by a slash or a hyphen is one here as it is bare; a word its
# periods join is asked first, then a dotted member, and a joined word
# holding a member after the suffix test, each member left to S13's
# position test (decisions/S1, #792, #1088; decisions/S3, #1131, #1138)
def set_apart_kind(word: str, lexicon: Lexicon,
                   ) -> SetApartKind | Literal["member"] | None:
    """What a word in a delimited clause is to S1's set-apart reading:
    a title, a suffix (a word `suffix_as_written` reads, joined
    credentials included, or one its periods join,
    `period_joined_credential`), both, a member of the ambiguous class
    written with a period inside it (`dotted_member`), a joined word
    holding one (`joined_member`, 'MA/PhD') or a word its periods join
    holding one ('Msc.Ed'), which S13 settles after the name only, or
    None where the vocabulary reads it as a name or not at
    all. A comma the clause keeps on its word is no part of it
    (rules/N1)."""
    bare = word.strip(COMMA_STRIP)
    folded = _normalize(bare)
    acronym = folded.replace(".", "")
    sets = lexicon._sets
    # rules/S1: "one joined by a slash, a hyphen or a period (S3) too,
    # every chunk counting" -- a word with interior periods read here as
    # at the end of a name ('(Msc.Ed)', '(Lt.Gov)'; not '(Bob.PhD)'),
    # the period test asked at C level first (decisions/S3, #1131)
    joined = ("." in folded and folded not in sets.titles
              and acronym not in sets.suffix_acronyms)
    title = folded in sets.titles or joined and period_joined_title(
        bare, lexicon)
    if joined and not title and period_joined_credential(bare, lexicon):
        # rules/S3: "a joined word holding a member is a member itself"
        # -- 'Msc.Ed' as 'MA/PhD', settled by S13's position (#1138)
        return "member" if _holds_a_member(bare, lexicon) else "suffix"
    # a member of the ambiguous class, the set asked inline as the
    # necessary half of `dotted_member`, so no other word pays its
    # frame: `suffix_as_written` would read a dotted member as a suffix
    # wherever it stands, and reads no other member as one
    if acronym in sets.suffix_acronyms_ambiguous:
        if title:
            return "title"
        return "member" if "." in bare and dotted_member(
            bare, lexicon) else None
    # the sets and the joiners asked first, at C level, the necessary
    # half of `suffix_as_written`, so a word it could never read (a
    # nickname) pays no frame
    suffix = ((acronym in sets.suffix_acronyms or folded in sets.suffix_words
               or "-" in folded or "/" in folded)
              and suffix_as_written(folded, bare, lexicon))
    # rules/S3: "a joined word holding a member is a member itself" --
    # settled after the name only, as S13 settles one written alone
    # (decisions/S3, #1138)
    if suffix and not title and joined_member(bare, lexicon):
        return "member"
    if title:
        return "dual" if suffix else "title"
    return "suffix" if suffix else None


#: Single letters each followed by a period ('R.A.'), the writing that
#: makes a word that is a title too a set of initials (rules/S1).
_DOTTED_INITIALS = re.compile(r"(?:[^\W\d_]\.)+")

#: A word written as initials: one or two letters, with or without a
#: period, or single letters each followed by a period ('JP', 'Md',
#: 'MD.', 'A.M.', 'R.E.S.').
_INITIALS_SHAPE = re.compile(r"[^\W\d_]{1,2}\.?|" + _DOTTED_INITIALS.pattern)


# rules/S1: "A credential written as initials before a name word stays
# the nickname, and so does any word of its clause" -- asked of each
# chunk of a credential joined by a slash or a hyphen, so it reads
# before a name word as its split spelling does (decisions/S1, #792,
# #1088)
def reads_as_initials(word: str, kind: SetApartKind,
                      one_case: bool | None, lexicon: Lexicon) -> bool:
    """Whether a word of a clause S1 would set apart counts, before a
    name word of its comma part, as the initials the person goes by: a
    credential written in their shape that is no generation word, and a
    word that is a title too only written with a period after each
    letter ('R.A.') or in capitals in a name of mixed case ('RA'),
    Title case reading as the title it also is and capitals in a name
    written in one case saying nothing (S6); a title alone never. A
    member of the ambiguous class counts as the credential it is
    settled as. `one_case` is ParseState.one_case. A joined credential
    counts where any of its chunks would ('JP/MD', 'MD/PhD'), as its
    words written apart do, and one the vocabulary lists whole never
    ('NP-C'), a run of its chunks listed whole being one chunk
    ('PhD/NP-C' is 'PhD', 'NP-C', as `_joined_chunks` cuts it). A
    chunk is asked as the word it is, with no further cut by this
    function, so its loop is one level deep."""
    bare = word.strip(COMMA_STRIP)
    # a credential the vocabulary lists whole ('NP-C', 'SHRM-CP') is one
    # word, not two S3 joins, and has no other spelling written apart
    if kind == "suffix" and ("/" in bare or "-" in bare) and not (
            _listed_whole(bare, lexicon)):
        # a word with no cut S3 admits has no chunk to ask; unreached by
        # a parse, where a joined word not listed whole is a suffix only
        # through a cut
        for chunk in _joined_chunks(bare, lexicon) or ():
            if _shaped_as_initials(chunk, set_apart_kind(chunk, lexicon),
                                   one_case, lexicon):
                return True
        return False
    # rules/S1: "a credential S3 reads through chunks joined by a slash,
    # a hyphen or a period counts where any of its chunks would" -- a
    # period-joined word's chunks asked as a slash's are ('JP.MD' as
    # 'JP/MD'), one listed whole ('M.D.', 'MD.PhD') never (#1131)
    if (kind == "suffix" and "." in bare.strip(".")
            and _normalize(bare).replace(".", "")
            not in lexicon._sets.suffix_acronyms
            and period_joined_credential(bare, lexicon)):
        # a single letter before a glued honorific is the initial it is
        # written as ('J.씨', the one chunk the every-chunk test lets
        # count as nothing)
        return any(len(chunk) == 1 and chunk.isalpha()
                   or _shaped_as_initials(chunk, set_apart_kind(chunk, lexicon),
                                          one_case, lexicon)
                   for chunk in _period_chunks(bare) or ())
    return _shaped_as_initials(bare, kind, one_case, lexicon)


def _shaped_as_initials(bare: str,
                        kind: SetApartKind | Literal["member"] | None,
                        one_case: bool | None, lexicon: Lexicon) -> bool:
    """`reads_as_initials` for one word, or one listed run of a joined
    word, its kind as `set_apart_kind` gives it; a run holding a joiner
    never matches the initials shape."""
    return ((kind == "suffix" or kind == "member" or kind == "dual" and (
                _DOTTED_INITIALS.fullmatch(bare) is not None
                or one_case is False and bare.isupper()))
            and _INITIALS_SHAPE.fullmatch(bare) is not None
            and _normalize(bare) not in lexicon._sets.suffix_words)


def set_apart(words: Sequence[str],
              kinds: Sequence[SetApartKind],
              behind_a_credential: bool, lexicon: Lexicon) -> bool:
    """rules/S1's clause tests over the words of a delimited clause,
    each already found to be no name by `set_apart_kind` (or, after
    the name, a member its writing settles, rules/S13): a clause of
    nothing but title modifiers and styles is no title ('(UK)',
    '(Hon)'), a lone title of address may be the name the person goes
    by ('(Sir)', '(Mr)': a title addressing the given name, or a
    salutation that may end the given part, rules/H8), and a clause
    of titles alone straight behind a credential qualifies that
    credential ('FRCS (SN)'). `behind_a_credential` is whether the
    word in front of the clause was read as a suffix, which extract,
    running before any word is read, passes as False."""
    sets = lexicon._sets
    folded = [_normalize(w.strip(COMMA_STRIP)) for w in words]
    if all(f in sets.title_modifiers or f in sets.title_styles
           for f in folded):
        return False
    if len(folded) == 1 and (folded[0] in sets.given_name_titles
                             or folded[0] in sets.after_given_titles):
        return False
    return not (behind_a_credential and "suffix" not in kinds
                and "dual" not in kinds)


# rules/S10: "a Title-case numeral in a name of mixed case leans to the
# name" -- the fork weighed it and the writing declined it, so it is
# reported as a declined member of the ambiguous class is (#752)
def numeral_leans_to_the_name(text: str, tags: Set[str],
                              preceding: str | None,
                              one_case: bool | None) -> bool:
    """Whether `reads_as_generation` declined a numeral for its Title
    case alone: two or more letters, unlisted, in a name of mixed case,
    and no initial in front (which makes it a name word unweighed)."""
    return (one_case is False and text.rstrip(".").istitle()
            and len(text.rstrip(".")) >= 2 and "vocab:suffix" not in tags
            and reads_as_generation(text, tags, preceding, None))


def is_listed_numeral(text: str, tags: Set[str]) -> bool:
    """A numeral the vocabulary lists in two or more letters ('III'):
    not in question, so its reading is never reported (rules/S10)."""
    stem = text.rstrip(".")
    return (len(stem) >= 2 and "vocab:suffix" in tags
            and _ROMAN.match(stem) is not None)


# rules/S10: "a numeral written in lower case in a name of mixed case is
# the generation and reports nothing" -- the one writing that settles
# the fork, since nobody writes an initial in lower case beside
# capitals. Asked by the walk, which takes such a numeral as any suffix
# word and records no call, and by the report on a numeral before a
# credential (`reads_as_a_reported_numeral`).
def numeral_settled_by_case(text: str, one_case: bool | None) -> bool:
    """Whether a numeral the trailing fork reads is lower case in a
    name written in more than one case. `one_case` is
    ParseState.one_case; None (nobody asked) settles nothing."""
    return one_case is False and text.islower()


# rules/S10: "either reading is reported" -- the one question the two
# reports on a numeral a post-nominal follows ask (assign's, and the
# maiden take's for a numeral its clause keeps): the fork would read
# this numeral, and its writing does not settle it (#721)
def reads_as_a_reported_numeral(text: str, tags: Set[str],
                                preceding: str,
                                one_case: bool | None) -> bool:
    """Whether a numeral the walk left a name word, with `preceding`
    in front of it, is one the fork would weigh and so reports: one it
    reads as the generation, or declines for its Title case."""
    return ((reads_as_generation(text, tags, preceding, one_case)
             or numeral_leans_to_the_name(text, tags, preceding, one_case))
            and not numeral_settled_by_case(text, one_case))


# #544: a single-letter roman numeral ('V', 'v', 'I.'), in any case,
# is excluded for its SHAPE -- one letter is how a middle initial is
# written, and rules/S3 retires single-character matches for the
# same reason -- not for being a generation: a multi-letter suffix
# word ('III', 'Jr') anchors and runs like any other. So it neither
# anchors an ambiguous member behind it nor counts toward C4's
# multi-word credential run. It still peels exactly as before; this
# answers only those two questions.
def is_single_letter_numeral(text: str) -> bool:
    """One letter, optionally followed by periods, that is a roman
    numeral ('V', 'v', 'I.', 'X')."""
    letters = text.rstrip(".")
    return len(letters) == 1 and _ROMAN.match(letters) is not None


# rules/T5: "A one-letter word written with its period is an initial,
# in a script that writes initials, and so is a bare unaccented Latin
# capital, A to Z"
def is_initial(text: str) -> bool:
    """'A.' / 'j.' / bare capital -- v1's is_an_initial, narrowed to
    scripts that HAVE initials (#320). v1's \\w is Unicode-aware and
    matched CJK too, which made period-written CJK honorifics ('씨.')
    fail is_suffix_strict -- the veto in _is_suffix_strict_n, NOT the
    vocabulary: suffix_as_written has no veto, so classify tagged '씨.'
    'vocab:suffix' either way, and is_suffix_lenient took it either way
    too. Downstream of that one strict-test No, the glued honorific in
    a name carrying such a token went unpeeled ('田中さん 様.')."""
    return is_initial_shaped(text) and not in_initialless_script(text)


def is_one_case(texts: Sequence[str]) -> bool:
    """Whether a name is written wholly in ONE case -- all upper or all
    lower alike -- and so carries no case EVIDENCE about any letter in
    it (rules/P8, #383/#479). The caller passes the name's OWN
    words: a maiden marker's clause and any delimited (nickname)
    content are not among them, and appending one must not flip the
    reading of words that did not change.

    Mirrors the SHAPE of the comparison the R5 gate in
    `_render.capitalized` makes, not its SPAN: R5 joins every token but
    the suffixes, nickname and maiden content included, while
    classify's caller hands in only the name's own words (rules/P3's
    own-words doctrine, see above) -- so a clause-bearing name can be
    one-case to this function and mixed to R5 (measured:
    `'JUAN GARCIA Y LOPEZ née Jones'` is one case here, mixed there),
    and a name with a cased suffix mixed here and one-case there
    (`'john e jones III'`). Not shared by import today -- render is a
    layer this module does not reach into -- and #492 left the two
    spans apart by decision (decisions/R5, "THE R5 / PARSER SPLIT").

    `Sequence`, not `Iterable`: the caller passes a list it already
    built rather than a fresh generator, so `is_one_case` costs one
    profiler frame per parse rather than one per token (#475).

    A CASELESS script answers True, harmlessly: `'محمد و علي'.upper()`
    is the string itself, so the comparison holds. Its callers are
    classify, segment (only where C2's flag on a tail part asks) and
    script_segment's `_one_case`; the first two record the answer as
    `ParseState.one_case`, and script_segment does not; the decisions
    that read it each also require the token they judge to be CASED:
    classify's connective-or-initial fork asks for a token whose own
    `upper()` and `lower()` differ, `ambiguous_lean` -- which the
    suffix readers in `_pieces`, `_group` and `_assign` reach through
    `listed_lean` -- returns no lean for a caseless token, and
    `caps_shape_candidate` requires
    `isupper()`. A caseless letter is none of those, so a caseless
    name never reaches a decision this gates, and "one case" is the
    honest verdict for text that has only one.
    """
    joined = " ".join(texts).translate(_CASELESS_LETTERS)
    return joined in (joined.upper(), joined.lower())


#: Which way the WRITING leans for a member of the ambiguous
#: credential class; None is no lean at all. Named so the two
#: predicates that answer it -- `ambiguous_lean` here and
#: `_pieces.listed_lean`, which wraps it -- carry the same three-value
#: type rather than a bare `str`. Under mypy's `strict_equality` that
#: makes a misspelled comparison (`== "credentail"`) an error at the
#: two call sites that branch on the answer, where a `str` return
#: leaves it silently False forever -- which is what the value is FOR:
#: `_pieces.peel_trailing` peels or declines on it.
#: `period_joined_vocab`'s own verdict is spelled inline for the same
#: reason; it has one caller shape and no wrapper to keep in step.
Lean = Literal["credential", "name"]

#: How a member's writing leans, by what the member is (rules/S11):
#: an acronym's capitals are the credential, the lower case of a suffix
#: word written `title_case_is_name` is the suffix, and any other suffix
#: word's writing (an agnomen's, `Junior`'s) says nothing (#1039).
Cue = Literal["acronym", "word", "none"]


# #289's credential lean, rules/S6: "Written case is evidence beside
# the count (S4), and it speaks only in a name written in more than
# one case" -- the WRITING evidence that decides ahead of the
# words-to-spare count (history: decisions/S6).
def ambiguous_lean(text: str, one_case: bool,
                   cue: Cue = "acronym") -> Lean | None:
    """Which way the WRITING leans for a member of the ambiguous
    credential set: "credential", "name", or None for no lean at all.

    None is the fall-through to rules/S4's count, and it is the
    answer for three inputs. A name written wholly in one case says
    nothing about any word in it. A member written wholly in lower
    case says nothing either -- lower is how most of a mixed-case
    name is written, so it is not a contrast. And a CASELESS token
    ('씨', '毛') can be written against nothing, so neither test
    fires and the count decides, which is what keeps this rule out of
    a caseless script by construction.

    `one_case` is the recorded fact (ParseState.one_case), taken over
    the name's OWN words -- handed in rather than recomputed, because
    three sites read this and a fact two of them derived apart is the
    bug the field exists to prevent
    (mechanisms.md#ONE-PREDICATE-PER-QUESTION).

    The caller decides MEMBERSHIP: this answers only about the
    writing. Periods do not disturb either test, '.' having no case,
    so 'MA.' leans as 'MA' does -- the lean reads CASE, not periods,
    and the dotted spelling is the vocabulary's own question
    (suffix_as_written).

    `cue` is what the member is (rules/S11). A suffix WORD that is
    also a name and whose Title case is its writing as a name ("word",
    'fils', 'kc', written `title_case_is_name`) leans the other way at
    one end: its lower case in a mixed-case name is the suffix
    ("credential", the suffix reading), its capitals say nothing (a
    surname is often written so), and Title case leans to the name as
    an acronym's does. Any other ("none": an agnomen, 'Neto', written
    in the case of the name around it; 'Junior', whose Title case is
    the generation's writing too) never leans (#1039).
    """
    if one_case or cue == "none":
        return None
    if (cased := text.translate(_CASELESS_LETTERS)).upper() == cased.lower():
        return None                      # caseless: no contrast to read
    if text.isupper():
        return "credential" if cue == "acronym" else None
    if text.islower():
        return "credential" if cue == "word" else None
    return "name"


def lexicon_cue(n: str, lexicon: Lexicon) -> Cue:
    """The `ambiguous_lean` cue of the folded member `n`, read off the
    lexicon by a caller that has no tags to read (`is_wholly_suffix`);
    `_pieces.listed_lean` reads the same answer off classify's tags."""
    if n in lexicon._sets.suffix_words_ambiguous:
        return ("word" if n in lexicon._sets.title_case_name_words
                else "none")
    return "acronym"


_DOTTED = re.compile(r"(?:" + _LETTER + r"\.)+")
# rules/T7: "a run of single letters joined by full stops" -- two or
# more letters, each closed by a stop but the last, whose stop is
# optional ('E.T.', 'J.R.R', #1296), and the same run rules/H10 reads as
# a title ('U.S.', 'U.S', the closing stop optional as
# `period_joined_vocab`'s shape verdict lets it be); _RUN_LETTER is one letter of it
# with its stop. _render holds a copy of each (tests/v2/test_regex_sync.py)
_LETTER_RUN = re.compile(r"(?:" + _LETTER + r"\.)+" + _LETTER + r"\.?")


_RUN_LETTER = re.compile(_LETTER + r"\.?")


def is_letter_run(text: str) -> bool:
    """Two or more single letters joined by full stops ('J.P.', 'J.R.R'),
    the way a person's initials are written run together: rules/T7's
    run, and the shape rules/C16 reads as a name after the comma behind
    one name word whatever it spells (#1238)."""
    return _LETTER_RUN.fullmatch(text) is not None


# #544: the CHUNKED spelling -- two or more runs of letters, each
# closed by a period ('M.Eng.', 'L.Ac.'). Both callers compare the
# period-free letters against the listed member, so the chunks must
# spell it; one chunk ('Ma.', 'Ed.') is the single trailing period and
# stays outside the gate.
_CHUNKED = re.compile(r"(?:(?:" + _LETTER + r")+\.){2,}")


def _dotted(text: str) -> bool:
    """Written with its periods: one after each letter ('M.A.',
    'J.D.'), the acronym's own spelling, or -- since #544 -- two or
    more letter chunks each closed by a period ('M.Eng.', 'L.Ac.'), the
    spelling a member with a lower-case tail is written in. A single
    trailing period ('Ma.', 'Ed.', 'Ms.') is the abbreviation shape any
    word can wear -- the honorific's, a name's -- and is not the gate's
    "written with periods" (rules/S3). Until #296's review the gate
    was "any period", and 'Smith, Ms.' passed it as the degree."""
    return (_DOTTED.fullmatch(text) is not None
            or _CHUNKED.fullmatch(text) is not None)


# rules/T8: "glued to the next at its full stop" -- the shapes
# `glued_cuts` reads (decisions/T8 (#1230, #1235)): one chunk of letters
# closed by a stop with something after it
_GLUED_CHUNK = re.compile(r"((?:" + _LETTER + r")+)\.(?=\S)")
# a run of two or more single letters closed by stops, a letter after
# it (the name is `glued_cuts`' to find)
_GLUED_RUN = re.compile(r"(?:" + _LETTER + r"\.){2,}(?=[^\W\d_])")
#: a letter (its marks with it, so NFD text passes), a full stop and a
#: letter: the C-level test `_script_segment` asks before `glued_cuts`
GLUED_SHAPE = re.compile(_LETTER + r"\.[^\W\d_]")
# the Thai vowel and tone marks (Mn), which `_LETTER` does not count:
# nearly every Thai name writes one ('สุดา', 'ใจดี'), so without them the
# name after a Thai title's stop is never found (#1166)
_THAI_MARKS = "[\u0e31\u0e34-\u0e3a\u0e47-\u0e4e]"
# one word of letters, apostrophes and hyphens: what can follow a chunk
# and be a name
_GLUED_WORD = re.compile(
    r"(?:" + _LETTER + r")(?:" + _LETTER + "|" + _THAI_MARKS + r"|['’\-])*")


def _is_cased_letter(chunk: str) -> bool:
    """One letter in a script with case: the initial T8 reads alone
    (rules/T8); a single letter in a script without case is read alone
    only where it is listed, as a title or a given name written short."""
    return len(chunk) == 1 and chunk.upper() != chunk.lower()


def _reads_alone(chunk: str, lexicon: Lexicon) -> bool:
    """A chunk the parser reads on its own before a full stop: one
    letter in a script with case, a transliteration digraph rules/H2
    names, a listed title that is no saint particle, or a listed given
    name written short (decisions/period-joined-words, #1255). A single
    letter in a script without case is read alone only where it is
    listed (Thai 'ศ.', #1166); a run of them is T7's run in any script."""
    chunk = unicodedata.normalize("NFC", chunk)
    if _is_cased_letter(chunk):
        return True
    n = _normalize(chunk)
    sets = lexicon._sets
    if n in _DIGRAPH_INITIALS or n in sets.given_name_abbreviations:
        return True
    return is_title_chunk(chunk, lexicon)


def glued_cuts(text: str, lexicon: Lexicon) -> tuple[int, ...]:
    """Where a word glued to the next at a full stop divides (T8,
    #1230, #1235): the offset after each stop at which a chunk the
    parser reads alone (`_reads_alone`) meets a name, so the word reads
    as it does with a space there ('Dr.John' as 'Dr. John',
    'Ц.Сандаг-Очир' as 'Ц. Сандаг-Очир', 'Yu.A.Chibrikova' as 'Yu. A.
    Chibrikova'). A run of single letters stays one chunk before the name
    ('J.R.Smith' as 'J.R. Smith', rules/T7), while titles glued to each
    other divide at each stop, as they read written apart ('Lt.Gov.John'
    as 'Lt. Gov. John'). Empty where the vocabulary reads the word whole
    (a suffix spelled without its stops, 'M.Sc', 'M.Sc.'; a title listed
    whole), and wherever the
    word does not divide through to its end: at a word in lower case
    ('Dr.med', 'G.ppe'), at one closed by its own stop or followed by
    another chunk ('Dr.Med.', 'J.Smith.', 'Dr.John.Smith'), and at an
    unambiguous title or credential after the stop ('Dr.MD')."""
    sets = lexicon._sets
    n = _normalize(text)
    bare = n.replace(".", "")
    # a title listed whole is read whole, as a suffix spelled without its
    # stops is: with its stops, or without them where no initial ends it
    # ('Dr.Ma' where a caller lists 'drma'; 'Dr.A.' divides, 'dra' being
    # the title and the initial T8 reads behind one)
    if (bare in sets.suffix_acronyms or n in sets.titles
            or bare in sets.titles and len(unicodedata.normalize(
                "NFC", n.rsplit(".", 1)[-1])) > 1):
        return ()
    low = text.lower()
    dotted = _dotted_titles(sets.titles)
    if len(low) != len(text):
        # offsets in `low` would not be the text's
        dotted = ()
    cuts: list[int] = []
    at = 0
    titled = False
    # the cuts stand only where the word divides through to its end: a
    # name closing it ('Yu.A.Chibrikova'), or initials closing one a
    # title opens ('Dr.J.', 'Dr.J.R.'); never initials alone ('Kim
    # Yu.A.', the surname-first initials #1254 asks about), an initial
    # opening a chunk that stays whole ('Q.R.ST.'), nor a word holding a
    # delimiter or a digit, which no chunk or name matches ('M.D./Ph.D.')
    while True:
        if _LETTER_RUN.fullmatch(text, at):
            return tuple(cuts) if titled else ()
        d = (dotted_title_end(low, at, dotted)
             if dotted and low.startswith(dotted, at) else None)
        if d is not None and (
                (run := _GLUED_RUN.match(text, at)) is not None
                and run.end() > d):
            # a run of single letters running past the title is T7's
            # run of initials ('พ.ต.ส.สมชาย')
            d = None
        if d is not None:
            # a title listed with its stops is one chunk, read alone
            # (#1319: 'พล.ต.ต.สุรศักดิ์', 'พ.อ.หญิงวาสนา')
            titled = titled or not cuts
            if d == len(text):
                return tuple(cuts)
            nxt = _GLUED_CHUNK.match(text, d)
            if (low.startswith(dotted, d)
                    and dotted_title_end(low, d, dotted) is not None) or (
                    nxt is not None and is_title_chunk(nxt.group(1), lexicon)):
                cuts.append(d)
                at = d
                continue
            end, letter = d, False
        elif (run := _GLUED_RUN.match(text, at)) is not None:
            # a run of initials before the name stays one word (T7)
            end, letter = run.end(), True
        else:
            m = _GLUED_CHUNK.match(text, at)
            if m is None or not _reads_alone(m.group(1), lexicon):
                return ()
            end = m.end()
            letter = _is_cased_letter(
                unicodedata.normalize("NFC", m.group(1)))
            if not letter and is_title_chunk(m.group(1), lexicon):
                titled = titled or not cuts
                nxt = _GLUED_CHUNK.match(text, end)
                if nxt is not None and is_title_chunk(nxt.group(1), lexicon):
                    # titles glued to each other divide at each stop, as
                    # the titles written apart read ('Lt.Gov.John',
                    # 'Maj.Gen.John', a phrase H9 reads)
                    cuts.append(end)
                    at = end
                    continue
        word = _GLUED_WORD.match(text, end)
        # its first letter with case, so a modifier letter opening it
        # ('m.ʿali') does not hide a word in lower case; a script with
        # no case gives none, and divides
        if word is None or next(
                (c.islower() for c in word.group() if c.upper() != c.lower()),
                False):
            return ()
        initial = len(unicodedata.normalize("NFC", word.group())) == 1
        tail = text[word.end():]
        # a word closed by its own stop is a field or a name closed by
        # one ('Dr.Med.', 'J.Smith.'), save an initial behind a title
        # ('Dr.J.'); one followed by another chunk stays whole
        # ('Dr.John.Smith'), save an initial opening the next division
        # ('Yu.A.Chibrikova')
        if tail == "." and not (initial and not letter):
            return ()
        if len(tail) > 1 and not initial:
            return ()
        w = _normalize(word.group())
        if w in sets.titles or (
                w in sets.suffix_acronyms
                and w not in sets.suffix_acronyms_ambiguous) or (
                (w in sets.suffix_words or w in sets.credential_words)
                and w not in sets.suffix_words_ambiguous):
            return ()
        cuts.append(end)
        at = end
        if word.end() == len(text) or tail == ".":
            return tuple(cuts) if titled or not initial else ()


@functools.lru_cache(maxsize=16)
def _dotted_titles(titles: frozenset[str]) -> tuple[str, ...]:
    """The titles of a script without case listed with a full stop
    inside ('พ.ต.อ', 'พ.อ.หญิง'), longest first: one tuple per
    vocabulary, so a word opening with none of them is told by a C-level
    `startswith` alone. A cased title written with its stops ('dr.c',
    'mgr.a') is left out: glued, it keeps the reading decisions/T8's
    #1305 entry decided, a title and the initial behind it
    ('Dr.C.Meera'), where a caseless script writes no initials."""
    return tuple(sorted((t for t in titles if "." in t and t == t.upper()),
                        key=len, reverse=True))


@functools.lru_cache(maxsize=16)
def title_prefixes(titles: frozenset[str]) -> tuple[str, ...]:
    """Every listed title, a tuple for a C-level `startswith`: what may
    stand behind a title only in a phrase glued in front (rules/W6)."""
    return tuple(titles)


def dotted_title_end(low: str, at: int,
                     dotted: tuple[str, ...]) -> int | None:
    """Where a title listed with its stops, opening `low` at `at`, ends
    as a word of its own: past its own full stop, or, where its last
    chunk is more than one letter ('พ.อ.หญิง'), right before a letter
    of a script without case. A last chunk of one letter needs its
    stop, being the initial it spells otherwise ('น.สมชาย' is no
    'น.ส' + 'มชาย', 'พ.ต.อนุชา' no 'พ.ต.อ' + 'นุชา'), and a letter with
    case after a longer chunk goes on the word ('Lt.Colin', not 'Lt.Col'
    + 'in'); None where none does (#1319)."""
    for t in dotted:
        if not low.startswith(t, at):
            continue
        end = at + len(t)
        if end == len(low):
            return end
        if low[end] == ".":
            return end + 1
        c = low[end]
        last = t.rsplit(".", 1)[-1]
        if len(unicodedata.normalize("NFC", last)) > 1 and c.isalpha() and (
                c.upper() == c.lower()):
            return end
    return None


def glued_saint_cut(text: str, lexicon: Lexicon) -> int | None:
    """The offset after the stop where a listed saint particle is glued
    to the name it opens ('Sta.Ana', 'St.John', 'STE.MARIE'): the
    particle, one full stop and one name word whose first letter with
    case is a capital, nothing after it; None for any other word
    (rules/T8, #1071). The word is one name word wherever it stands,
    and divides here only as the last word of a part (`_script_segment`
    asks that)."""
    m = _GLUED_CHUNK.match(text)
    if m is None or _normalize(m.group(1)) not in lexicon._sets.saint_particles:
        return None
    word = _GLUED_WORD.fullmatch(text, m.end())
    if word is None or next(
            (c.islower() for c in word.group() if c.upper() != c.lower()),
            True):
        return None
    # an unambiguous title or suffix word after the stop is no name
    # ('St.MD', 'St.Jr')
    sets = lexicon._sets
    w = _normalize(word.group())
    if w in sets.titles or (
            w in sets.suffix_acronyms
            and w not in sets.suffix_acronyms_ambiguous) or (
            (w in sets.suffix_words or w in sets.credential_words)
            and w not in sets.suffix_words_ambiguous):
        return None
    return m.end()


def is_initial_chunk(chunk: str) -> bool:
    """Initials before a full stop, as T8's report asks of the chunks it
    cut (rules/T8): one letter in a script with case, a run of them
    ('J.R'), or a transliteration digraph rules/H2 names ('Yu'), and no
    title or given name written short."""
    parts = chunk.split(".")
    if len(parts) == 1 and _normalize(chunk) in _DIGRAPH_INITIALS:
        return True
    for part in parts:
        part = unicodedata.normalize("NFC", part)
        if len(part) != 1 or part.upper() == part.lower():
            return False
    return True


def is_title_chunk(chunk: str, lexicon: Lexicon) -> bool:
    """A listed title that is no saint particle, read as a chunk before
    a full stop (rules/T8; a saint particle glued to a name is one name
    word, `glued_saint_cut`)."""
    sets = lexicon._sets
    n = _normalize(chunk)
    return n not in sets.saint_particles and (
        n in sets.titles or n in sets.titles_ambiguous
        or n in sets.title_modifiers or n in sets.title_styles)


def is_dotted_title(text: str, n: str, lexicon: Lexicon) -> bool:
    """A run of single letters joined by full stops ('U.S.', 'P.D.')
    whose spelling without them is a title written `dotted`
    (`Lexicon.dotted_titles`, rules/H10, #490); `n` is the folded
    text, which both callers already have."""
    return (n.replace(".", "") in lexicon._sets.dotted_titles
            and _LETTER_RUN.fullmatch(text) is not None)


# #563: exactly two single letters, each closed by a period -- the way
# a given and a middle initial are written run together ('M.J.',
# 'G.J.'). The trailing period is optional, as `period_joined_vocab`'s
# shape verdict lets it be.
_PAIRED_INITIALS = re.compile(_LETTER + r"\." + _LETTER + r"\.?")


def is_paired_initials(text: str) -> bool:
    """Two single letters run together with periods ('M.J.'): the one
    unlisted dotted shape a person's own initials take, so after a
    comma it is a name until something in front of it, or another
    dotted word beside it, says it is a credential (rules/C5).
    Three or more letters ('X.Y.Z.') and any longer chunk ('B.Tech.')
    are outside it."""
    return _PAIRED_INITIALS.fullmatch(text) is not None


# rules/S3: "Paired initials are the exception, as C5 defines them, in a
# script that writes capitals" -- the script half of that clause, which
# classify asked inline until #752 (decisions/S3 (#864),
# decisions/vocabulary-model (#752)). C5's comma reading asks the bare
# `is_paired_initials`: after a comma a caseless pair reads as a name
# too ('John Smith, พ.บ.' given 'พ.บ.'), and moving it here would change
# that reading.
def is_cased_paired_initials(text: str) -> bool:
    """Paired initials (`is_paired_initials`) in a script that writes
    capitals: a text with a case mapping, so 'M.J.' and 'm.j.' but not
    Thai 'พ.บ.', which is how that script writes an abbreviation.
    The same compiled pattern as `is_paired_initials`, asked here
    rather than through it so a dotted token pays one frame, not
    two."""
    return (_PAIRED_INITIALS.fullmatch(text) is not None
            and text.upper() != text.lower())


# rules/S12: "a credential written split across a space reads as one
# word" -- one chunk of up to five letters, with or without its period
# ('Pharm.', 'D', 'Sc.'), the shape both words of a split credential
# take. The C-level half classify asks of every adjacent pair before
# the fold is looked up.
SPLIT_CHUNK = re.compile(r"(?:" + _LETTER + r"){1,5}\.?")


# mechanisms.md#ONE-PREDICATE-PER-QUESTION ("exactly one predicate answers it and every other site calls that one")
# -- the split credential's one test, asked by classify, which tags
# the pair for group's merge and `_comma._pieces`, and by
# `is_wholly_suffix` for the Ph./D. answer. decisions/phd-merge,
# decisions/vocabulary-model (#752)
def split_pair(first: str, second: str, lexicon: Lexicon) -> str | None:
    """Whether two adjacent words are one credential written split
    across a space, and so read as one unit -- answered with the PIECE
    TAG the merged pair carries, or None.

    "suffix": 'Ph.' then 'D.', with or without their periods, in any
    case, where the lexicon lists `phd` as unambiguous suffix
    vocabulary (a credential, or a suffix word) -- v1's fix_phd,
    merged as an unambiguous suffix wherever it stands but the head
    of the string (decisions/phd-merge); under a lexicon that does
    not, None, the pair being the two words it is written as.

    "split": any other pair of short chunks (`SPLIT_CHUNK`) whose
    period-free concatenation is unambiguous suffix vocabulary while
    the two are not both suffix vocabulary on their own ('Pharm. D.',
    'Pharm D', 'MB ChB' where 'chb' is unlisted) and neither is a
    particle or a connective, which join name words. The merged piece is
    a member of the ambiguous class, which the count decides (rules/S4,
    rules/C4). Its first chunk has two or more letters: a single
    letter opening the pair is a middle initial far more often (FEC
    writes 'SMITH, JOHN G. MR.', and 'G. MR.' folds to the listed
    'gmr'), so 'M. Sc.' and 'M. D.' stay two words. Two dotted single
    letters are the one opening letter asked further, and asked of
    #872's predicate rather than a copy: in a script with capitals
    they are paired initials (`is_cased_paired_initials`), the reading
    rules/S3 gives them joined, so only a caseless script's pair can
    merge, and not one in a script that writes no abbreviations (Han,
    hangul, kana: '博. 士.' is no dotted '博士'), which leaves no
    default entry such a fold.

    Where the merge may happen (never at the head of the string,
    rules/S2; a member pair only in a main segment and in the part
    after a comma) is the caller's question, not this one's."""
    if _PH.fullmatch(first) is not None and _D.fullmatch(second) is not None:
        # rules/S12: "is a credential only where the lexicon lists `phd`"
        # -- as unambiguous suffix vocabulary of either kind, as the
        # joined spelling reads it; elsewhere the two words, the fold
        # below being `phd` itself, which an ambiguous suffix word would
        # admit as a member. decisions/phd-merge (#1000)
        sets = lexicon._sets
        return ("suffix" if "phd" in sets.suffix_acronyms
                and "phd" not in sets.suffix_acronyms_ambiguous
                or "phd" in sets.suffix_words
                and "phd" not in sets.suffix_words_ambiguous else None)
    if (SPLIT_CHUNK.fullmatch(first) is None
            or SPLIT_CHUNK.fullmatch(second) is None):
        return None
    a, b = first.rstrip("."), second.rstrip(".")
    if composed_len(a) < 2 and (
            composed_len(b) != 1 or not first.endswith(".")
            or not second.endswith(".")
            or is_cased_paired_initials(first + second)
            # a script that writes no abbreviations is not wearing an
            # abbreviation's periods, as rules/S3 reads it joined
            or in_unabbreviating_script(first + second)):
        return None
    fold = _normalize(a + b)
    if (fold in lexicon._sets.suffix_acronyms_ambiguous
            or not (fold in lexicon._sets.suffix_acronyms
                    or fold in lexicon._sets.suffix_words)):
        return None
    na, nb = _normalize(a), _normalize(b)
    if ((na in lexicon._sets.suffix_acronyms or na in lexicon._sets.suffix_words)
            and (nb in lexicon._sets.suffix_acronyms
                 or nb in lexicon._sets.suffix_words)):
        return None
    # a particle or a connective joins name words, which is what it is
    # doing beside one ('DE A JUNIOR', the A a surname written short);
    # written with its period a letter is an initial, not the connective
    # it spells ('SAM E.', rules/T5)
    for written, n in ((first, na), (second, nb)):
        if not written.endswith(".") and (n in lexicon._sets.particles
                                          or n in lexicon._sets.conjunctions):
            return None
    return "split"


def suffix_as_written(n: str, text: str, lexicon: Lexicon) -> bool:
    """Counts as a suffix as written, with NO initial veto (the veto
    differs by caller): unambiguous suffix vocabulary, an ambiguous
    acronym written with periods ('M.A.' yes, 'Ma' no), or a credential
    joined by '-' or '/' (`_joined_credential`, 'MD/PhD'). `n` is
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
    if a in lexicon._sets.suffix_acronyms_ambiguous and _dotted(text):
        return True
    if ((a in lexicon._sets.suffix_acronyms
            and a not in lexicon._sets.suffix_acronyms_ambiguous)
            or (n in lexicon._sets.suffix_words
                and n not in lexicon._sets.suffix_words_ambiguous)):
        return True
    # the joiners asked in C first, so a word holding neither pays no
    # frame
    return ("-" in n or "/" in n) and _joined_credential(text, lexicon)


#: What joins the letter chunks of the caps shape's joined spelling
#: ('PU-PH', `_joined_capitals`); a joined credential is cut by
#: `_JOINER_SPLIT`, which keeps the joiners.
_JOINERS = re.compile(r"[-/]")


def _member(chunk: str, lexicon: Lexicon) -> bool:
    """Whether CHUNK is a member of the ambiguous class (S4), however
    written ('MA', 'Ma', 'M.A', 'M.A.'): an acronym once its periods are
    removed, or a suffix word, that is a name too."""
    folded = _normalize(chunk)
    return (folded.replace(".", "") in lexicon._sets.suffix_acronyms_ambiguous
            or folded in lexicon._sets.suffix_words_ambiguous)


def _settles(chunk: str, lexicon: Lexicon) -> bool:
    """Whether CHUNK, one word or one listed run of a joined word's cut,
    settles a member beside it: a credential that is no name
    (`settles_a_member`), or a member written with a period inside it
    ('M.A')."""
    return (settles_a_member(chunk, lexicon)
            or "." in chunk and dotted_member(chunk, lexicon))


# rules/S1: "a credential that is no name, or a member its periods
# settle, says which" -- the credential half, asked of a clause word
# and of a joined word's chunk alike: a generation, a numeral, an
# honorific or a word that is a title too says nothing of the kind,
# 'Ed Jr' being a name a person goes by (decisions/S1, #1138)
def settles_a_member(word: str, lexicon: Lexicon) -> bool:
    """Whether WORD, a comma it is written against left off (rules/N1),
    is a credential that is no name: it counts as a suffix as written
    (a member its periods settle, 'M.A.', included) and is no
    generation, no honorific and no title. A joined word not listed
    whole is one where a chunk of its cut is ('PhD/Jr', not 'Jr/Sr')."""
    bare = word.strip(COMMA_STRIP)
    if ("/" in bare or "-" in bare) and not _listed_whole(bare, lexicon):
        return any(_settles(c, lexicon)
                   for c in _joined_chunks(bare, lexicon) or ())
    folded = _normalize(bare)
    sets = lexicon._sets
    return (suffix_as_written(folded, bare, lexicon)
            and folded not in sets.generation_words
            and folded not in sets.honorific_words
            and folded not in sets.titles)


def joined_member(word: str, lexicon: Lexicon) -> bool:
    """Whether WORD, joined by '/' or '-' and not listed whole ('NP-C'),
    cuts (`_joined_chunks`) into pieces one of which is a member of the
    ambiguous class that does not count as a suffix as written
    ('MA/PhD', 'M.A/PhD', 'MA/MBA'; not 'M.A./PhD'). `set_apart_kind`
    asks it of a word `suffix_as_written` reads, making that word a
    member S13 settles by its position; `_report_delimited_members`
    asks it of any joined nickname, so a joined word of members alone
    reports as its words written apart do."""
    if not ("/" in word or "-" in word) or _listed_whole(word, lexicon):
        return False
    return any(_member(c, lexicon)
               and not suffix_as_written(_normalize(c), c, lexicon)
               for c in _joined_chunks(word, lexicon) or ())


def member_word(word: str, lexicon: Lexicon) -> bool:
    """Whether a word of a delimited clause, a comma the clause keeps
    on it left off (rules/N1), is a member of the ambiguous class (S4),
    however written."""
    return _member(word.strip(COMMA_STRIP), lexicon)


def _listed_whole(word: str, lexicon: Lexicon) -> bool:
    """Whether the suffix vocabulary lists WORD whole, its joiners
    included ('NP-C', 'OTR/L'): as a suffix word, or as an acronym once
    its periods are removed. A member of an ambiguous class counts as
    listed."""
    folded = _normalize(word)
    return (folded in lexicon._sets.suffix_words
            or folded.replace(".", "") in lexicon._sets.suffix_acronyms)


#: The joiners of a joined credential, kept: 'MS/OTR/L' splits to
#: 'MS', '/', 'OTR', '/', 'L', the chunks at the even places.
_JOINER_SPLIT = re.compile(r"([-/])")


# bounded as `_longest_marker` is, for the reason given there: a set
# per lexicon, so 16 bounds many-lexicon churn without evicting in
# normal use
@functools.lru_cache(maxsize=16)
def _joined_span(words: frozenset[str]) -> int:
    """How many chunks the most-joined of WORDS holds: the longest run a
    listed word can be. Cached per set, which hashes once."""
    return max((w.count("/") + w.count("-") for w in words), default=0) + 1


# rules/S3: "a run of chunks the vocabulary lists whole, its slash or
# hyphen included, is one credential" -- the joiner inside 'NP-C' or
# 'OTR/L' is how that credential is spelled, not a joiner between two
# (decisions/S3, #1103)
def _joined_chunks(text: str, lexicon: Lexicon) -> list[str] | None:
    """A cut of TEXT at some of its joiners into pieces that each count
    as a suffix as written or are a member of the ambiguous class
    however written ('MA', 'M.A'), a run of chunks the vocabulary lists
    whole among them, with the fewest pieces ('MS/OTR/L' is 'MS', 'OTR/L';
    'CCC/SLP/L' is 'CCC', 'SLP/L'; 'APRN-FNP-C' is 'APRN', 'FNP-C';
    'MD-PhD' is 'MD', 'PhD'), or None where no cut gives such pieces
    ('MD-Jones', 'MD/'). No piece is the whole of TEXT: each caller has
    asked TEXT whole already, and a word listed whole that it refused
    (one that is a name too) would otherwise be asked again for ever.
    A piece is no longer than the most-joined listed word, so a long
    chain of joiners costs linear time."""
    parts = _JOINER_SPLIT.split(text)
    n = (len(parts) + 1) // 2  # the chunks
    span = max(_joined_span(lexicon._sets.suffix_words),
               _joined_span(lexicon._sets.suffix_acronyms))
    # pieces[k]: the fewest pieces cutting the first k chunks (0 where
    # none does, past the start); start[k]: where the last of them starts
    pieces = [0] * (n + 1)
    start = [0] * (n + 1)
    for i in range(n):
        if i and not pieces[i]:
            continue
        for j in range(i + 1, min(n - (i == 0), i + span) + 1):
            piece = "".join(parts[2 * i:2 * j - 1])
            # a run must be listed whole, which a chunk alone need not be
            if not piece or j > i + 1 and not _listed_whole(piece, lexicon):
                continue
            # a member is a chunk however written; `_joined_credential`
            # asks that a chunk beside it settles it (#1138)
            if ((not pieces[j] or pieces[i] + 1 < pieces[j])
                    and (suffix_as_written(_normalize(piece), piece, lexicon)
                         or _member(piece, lexicon))):
                pieces[j] = pieces[i] + 1
                start[j] = i
    if not pieces[n]:
        return None
    cut: list[str] = []
    j = n
    while j:
        i = start[j]
        cut.append("".join(parts[2 * i:2 * j - 1]))
        j = i
    cut.reverse()
    return cut


# rules/S3: "a word whose chunks are joined by a hyphen or a slash
# reads as a suffix when every chunk counts as a suffix as written" --
# the stricter test, every chunk rather than any, because a hyphen also
# joins names (decisions/S3 (#752)); a chunk is a run the vocabulary
# lists whole where one is (#1103)
def _joined_credential(text: str, lexicon: Lexicon) -> bool:
    """Whether TEXT is two or more chunks joined by '-' or '/', cut so
    that each is non-empty and counts as a suffix as written (listed,
    and not a bare member of the ambiguous class, a run listed whole
    counting as one chunk) or is a member of that class however
    written, where one chunk at least settles every such member
    (`_settles`), and not every chunk a single ASCII character, and --
    joined by a hyphen -- not written as a hyphenated name is ('MD/PhD', 'M.A.-Ph.D.', 'MA/PhD',
    'M.A/PhD', 'PhD-Md', 'md-phd', 'PhD/NP-C', but not 'MA/MBA',
    'MA/Jones', 'Smith-Jones', 'I-V', 'Ae-Ra', 'Ae-ra' or 'MD/'). The
    writing is read first, so a hyphenated name ('Smith-Jones') is
    never cut."""
    # a slash joins no name, so a word holding one takes no cue
    if "/" not in text:
        # rules/S3: "a word joined by a hyphen and written the way a
        # hyphenated name is, its first chunk in Title case and every
        # other in Title case or lower case, is a name word" -- where a
        # credential's chunks are not (decisions/S3 (#752)); its periods
        # are not the chunk's ('I.' is 'i'), as in a word split at its
        # periods
        named = True
        for k, c in enumerate(text.split("-")):
            bare = c.replace(".", "")
            named = (len(bare) > 1 and bare[0].isupper() and bare[1:].islower()
                     or k > 0 and bare.islower())
            if not named:
                break
        if named:
            return False
    chunks = _joined_chunks(text, lexicon)
    if chunks is None:
        return False
    # rules/S3: "a member of the ambiguous class (S4) is a chunk too,
    # however it is written, where the word holds a chunk that settles
    # it" -- a credential that is no name, or a member its periods
    # settle; a word of bare members alone has nothing to settle it
    # (decisions/S3, #1138)
    unsettled = any(_member(c, lexicon)
                    and not suffix_as_written(_normalize(c), c, lexicon)
                    for c in chunks)
    if unsettled and not any(_settles(c, lexicon) for c in chunks):
        return False
    # rules/S3: "Every chunk the vocabulary matches is a single ASCII
    # character" -- the numerals and the digit, which are about
    # generations, make no joined word a suffix either ('Jack I-V')
    for c in chunks:
        bare = c.replace(".", "")
        if len(bare) > 1 or not bare.isascii():
            return True
    return False


# rules/S3: "a word with interior periods reads as a suffix when
# every one of its period-separated chunks counts as a suffix as
# written" -- the joined words' every chunk, the periods being the one
# sign the word is joined at all (decisions/S3, #1131)
def period_joined_credential(text: str, lexicon: Lexicon) -> bool:
    """Whether TEXT, cut at its periods (`_period_chunks`), is chunks
    that each count as a suffix as written or are a member of the ambiguous
    class, one chunk at least settling every such member (`_settles`),
    and not every chunk the vocabulary matches a single ASCII character
    ('Msc.Ed', 'JD.CPA'; not 'Bob.PhD', 'Ma.Ed' or 'X.Y.I.'). A word
    whose last chunk is a glued honorific ('J.씨') reads as one too:
    the honorific is the suffix there and the chunk before it the
    initial it is written as (rules/W2). The chunks are two or more,
    save one where the word's periods all stand at its edge beside an
    ampersand or a semicolon ('MD.&', as 'MD.& PhD' writes it)."""
    chunks = _period_chunks(text)
    if chunks is None:
        return False
    sets = lexicon._sets
    if _normalize(chunks[-1]) in sets.honorific_tails:
        return True
    unsettled = False
    for c in chunks:
        folded = _normalize(c)
        if suffix_as_written(folded, c, lexicon):
            continue
        # rules/S11: "the word is part of that one word and is weighed
        # only by the shape the joined word wears" -- no chunk claim
        # for a suffix word that is also a name ('MD.Filho', whose Filho
        # MD would otherwise settle as a member)
        if folded in sets.suffix_words_ambiguous or not _member(c, lexicon):
            return False
        unsettled = True
    if unsettled and not any(_settles(c, lexicon) for c in chunks):
        return False
    # rules/S3: "Every chunk the vocabulary matches is a single ASCII
    # character" -- a numeral or the digit says nothing of a credential
    return not all(len(c) == 1 and c.isascii() for c in chunks)


def _period_chunks(text: str) -> list[str] | None:
    """TEXT cut at its periods, or None where it holds none inside it
    (one chunk where every period stands at the word's edge and an '&'
    or ';' there keeps one off the outer end: 'MD.&', ';.MD').
    ASCII punctuation beside an interior period is no part of the chunk
    ('MD.&PhD'); at the word's outer edges only its periods, a glued
    semicolon (rules/C10, 'Jr.;') and an ampersand joining the next
    credential ('MD.& PhD') are, so a word wearing any other there
    is no period-joined word at all, as a single word or a slash word
    wearing it is a name word ('Msc.Ed!', 'Msc.Ed.]', '[Msc.Ed]' as
    'MD!', 'MD/PhD]'). A chunk of nothing but punctuation is no
    chunk."""
    if "." not in text.strip("."):
        return None
    i, j = 0, len(text)
    while i < j and text[i] in string.punctuation:
        i += 1
    while j > i and text[j - 1] in string.punctuation:
        j -= 1
    if any(c not in ".;&" for c in text[:i] + text[j:]):
        return None
    chunks = [b for c in text[i:j].split(".")
              if (b := c.strip(string.punctuation))]
    return chunks or None


def _holds_a_member(text: str, lexicon: Lexicon) -> bool:
    """Whether a chunk of TEXT cut at its periods (`_period_chunks`) is
    a member of the ambiguous class that does not count as a suffix as
    written ('Ed' in 'Msc.Ed')."""
    return any(_member(c, lexicon)
               and not suffix_as_written(_normalize(c), c, lexicon)
               for c in _period_chunks(text) or ())


def period_member(word: str, lexicon: Lexicon) -> bool:
    """Whether WORD, a word with interior periods that is no acronym
    listed once its periods are removed, is
    a period-joined credential (`period_joined_credential`) holding a
    member of the ambiguous class ('Msc.Ed'): `joined_member`'s
    question for a word the periods join (rules/S3, #1131)."""
    bare = word.strip(COMMA_STRIP)
    folded = _normalize(bare)
    return ("." in folded
            and folded.replace(".", "") not in lexicon._sets.suffix_acronyms
            and period_joined_credential(bare, lexicon)
            and _holds_a_member(bare, lexicon))


# rules/H5: "a word with interior periods every one of whose chunks is
# a title chains without a final period" -- 'Lt.Gov', where the
# periods join nothing but titles (decisions/H5, #1131)
def period_joined_title(text: str, lexicon: Lexicon) -> bool:
    """Whether TEXT, cut at its periods, is two or more chunks every
    one of which is title vocabulary ('Lt.Gov', 'Lt.Col'; not
    'Dr.PhD' or 'St.John')."""
    chunks = [_normalize(c) for c in text.split(".") if c]
    return len(chunks) >= 2 and all(
        c in lexicon._sets.titles for c in chunks)


def _is_suffix_strict_n(n: str, text: str, lexicon: Lexicon,
                        one_case: bool | None = None) -> bool:
    # rules/T4: "in a name written wholly in one case, which says
    # nothing about any letter in it, a bare letter is an initial
    # wherever its capital would be" -- so the veto takes 'v' where it
    # takes 'V' (#727). Lower case first, at C level: a capital is
    # is_initial's already, and only a caller with the fact passes it
    if is_initial(text) or (
            one_case and len(text) == 1 and text.islower()
            and _INITIAL.fullmatch(text.upper()) is not None):
        # period-written ambiguous acronyms are exempt from the veto
        return _dotted(text) and \
            n.replace(".", "") in lexicon._sets.suffix_acronyms_ambiguous
    return suffix_as_written(n, text, lexicon)


def is_suffix_strict(text: str, lexicon: Lexicon,
                     one_case: bool | None = None) -> bool:
    """v1's is_suffix: suffix_as_written with the initial veto ('V.' in
    'John V. Smith' is a middle initial, not roman five).

    `one_case` is whether the name's own words are written in one
    case (ParseState.one_case): where they are, a bare lowercase
    letter is the initial its capital is (rules/T4) and is vetoed as
    its capital is. None or False is the veto by the writing alone,
    which is v1's."""
    return _is_suffix_strict_n(_normalize(text), text, lexicon, one_case)


def is_suffix_lenient(text: str, lexicon: Lexicon) -> bool:
    """v1's is_suffix_lenient: suffix_words accepted unconditionally,
    bypassing the initial veto -- only safe in unambiguous positions
    (after a comma)."""
    n = _normalize(text)
    return (n in lexicon._sets.suffix_words
            and n not in lexicon._sets.suffix_words_ambiguous) \
        or _is_suffix_strict_n(n, text, lexicon)


#: The suffix delimiters every policy has, beside the comma. rules/C10:
#: "The semicolon, the hyphen and the slash are delimiters by default"
#: -- "no policy removes them, as none removes the comma", so a
#: policy's extra_suffix_delimiters add to them. decisions/C10 (D15,
#: #889).
BUILTIN_SUFFIX_DELIMITERS = frozenset({";", "-", "/"})

#: The built-in delimiters read glued to a word or inside one. rules/C10:
#: "a built-in hyphen or slash parts only standing alone" -- glued, it
#: is the word's own ('al-', 'MD/PhD'). decisions/C10 (#889).
BUILTIN_GLUED_DELIMITERS = frozenset({";"})


def delimiter_cores(policy_delimiters: frozenset[str]) -> frozenset[str]:
    """The built-in suffix delimiters with the configured ones,
    surrounding whitespace stripped: ' - ' -> '-', the cores that part
    a trailing suffix part STANDING ALONE. Whitespace-padded
    delimiters surface as standalone tokens; the stripped core is what
    tokenize produced."""
    if not policy_delimiters:
        return BUILTIN_SUFFIX_DELIMITERS
    return BUILTIN_SUFFIX_DELIMITERS | frozenset(
        d.strip() for d in policy_delimiters if d.strip())


def glued_cores(policy_delimiters: frozenset[str]) -> frozenset[str]:
    """The cores read glued to one end of a word or inside one: the
    semicolon and every configured core, never a built-in hyphen or
    slash that the caller did not declare (BUILTIN_GLUED_DELIMITERS).
    A configured core that is itself a word (' and ') is in the set:
    `glued_stem`'s callers ask `glues` before reading it glued, while
    `is_wholly_suffix`'s in-word split does not ('MDandPhD')."""
    if not policy_delimiters:
        return BUILTIN_GLUED_DELIMITERS
    return BUILTIN_GLUED_DELIMITERS | frozenset(
        d.strip() for d in policy_delimiters if d.strip())


# rules/C10: "the word keeps the delimiter in its text and reads as it
# would without it" -- the word, for every site that reads one: the
# tags classify writes, the comma decision's shape tests, C2's flag
# and the run test below (decisions/C10).
def glued_stem(text: str, cores: frozenset[str]) -> str | None:
    """The word a delimiter core glued to ONE end of `text` leaves
    ('MD;' -> 'MD', ';PhD' -> 'PhD', 'MD-PhD;' -> 'MD-PhD' under '-'),
    or None: no core at an end of the text, a core standing alone, one
    inside a word only ('MD;PhD', which splits_into_suffixes reads), or
    a core that is itself a word (see glues). Every core is tried, in
    sorted order, so the answer never depends on a set's iteration
    order (the second review of #871: 'MD/PhD; MBA' under '/' read two
    ways by hash seed). Callers test `core in text` inline first, so a
    word with no core pays no frame."""
    for core in sorted(cores):
        if (core in text and glues(core) and text.count(core) == 1
                and len(text) > len(core)):
            if text.endswith(core):
                return text[:-len(core)]
            if text.startswith(core):
                return text[len(core):]
    return None


def glues(core: str) -> bool:
    """Whether a delimiter core can be GLUED to a word: one written
    without a letter or digit (';', '/', '-'). A core that is a word
    (' and ' under a declared policy) is found inside other words by
    the substring test ('Stand'), so it parts only standing alone
    (rules/C10's glued bullet)."""
    return not any(ch.isalnum() for ch in core)


def splits_into_suffixes(text: str, cores: frozenset[str],
                         lexicon: Lexicon) -> bool:
    """v1 expand_suffix_delimiter parity for delimiters WITHOUT
    whitespace ('RN/CRNA' with '/'): the token counts as a suffix when
    some core splits it into >=2 non-empty parts that are all suffixes.
    A core glued to ONE word ('MD;') is is_wholly_suffix's to read, by
    the test it gives that word alone (D15). The token text is never
    rewritten (anti-#100): it takes Role.SUFFIX whole, which renders
    'RN/CRNA' where v1 rendered 'RN, CRNA' -- the documented
    divergence, release-log classified."""
    for core in cores:
        if core in text:
            parts = [part for part in text.split(core) if part]
            if len(parts) >= 2 and all(
                    is_suffix_lenient(part, lexicon) for part in parts):
                return True
    return False


# rules/S3: "a word with interior periods reads as a suffix when
# every one of its period-separated chunks counts as a suffix as
# written" -- "every chunk the vocabulary matches is a single ASCII
# character, the roman numerals and the lone digit the vocabulary
# lists, which are about generations rather than credentials". The
# chunk rule and its single-character exception (decisions/S3,
# #1131).
def period_joined_vocab(
        text: str, lexicon: Lexicon,
) -> Literal["title", "suffix", "shape"] | None:
    """v1's parse_pieces derivation for interior-period tokens
    ('Lt.Gov.', 'Msc.Ed.', and by the ANY rule 'Mr.Smith'): ANY title
    chunk makes the token a title (checked first, v1's continue); else
    the token is a suffix where EVERY chunk counts
    (`period_joined_credential`, #1131: 'Msc.Ed.', whose member 'ed'
    'msc' settles, but not 'Bob.PhD', which the shape verdict below
    reads by position). A suffix word that is also a name is a member
    there, settled by a credential beside it ('M.Filho' is no suffix,
    rules/S11). Returns "title", "suffix", "shape", or None.

    "shape" is the third verdict and it is the absence of a claim
    worth acting on (#516): two or more chunks, EVERY one of them
    alphabetic, that the every-chunk test does not read as a suffix
    ('Bob.PhD', 'BM.BS', #1131), chunks that are a SINGLE ASCII
    CHARACTER among them. That single-character exception is the
    roman-numeral accident retired narrowly: measured 2026-09-15 the
    one-character suffix vocabulary is {'2', 'i', 'v'} plus the glued
    CJK honorific tails, so 'John Smith R.A.I.' was reading as a
    generational suffix off the chunk 'i'. CHARACTER rather than
    LETTER because '2' is a digit and is in the set; ASCII because
    '씨' is the single character that must KEEP its claim ('J.씨'). A
    word whose every chunk counts still reads as a suffix, so 'Msc.Ed.'
    and 'JD.CPA' are untouched -- the WIDE retirement, where
    any chunk match yields to the shape, was measured and rejected: it
    costs 'Doe, John Msc.Ed.' a real credential and re-routes the
    honorific peel of '김민준씨, J.씨' for nothing this design wants
    (decisions/S3).

    The ALPHABETIC requirement is a SEPARATE, narrower gate on the
    shape verdict alone (#516 review round, decided by the
    orchestrator): a bare digit chunk is not an acronym letter by any
    reading, so 'Smith, 1.4' and 'John Smith 1.4' do not join the
    class by shape -- the only PROTECTED digit control this design
    had was the delimited 'Bridge (1.4)', and 'Smith, 1.4' and its
    no-comma twin were the gap that control did not cover, since
    delimited content is excluded by a different mechanism (extract's
    escape) and digits reach THIS detector, never that one.
    '.isalpha()' is asked of EVERY chunk, not just the matched ones,
    so a mixed token like 'X.Y.2.' is not shape-admitted either -- one
    non-letter chunk is enough to say the writing is not spelling an
    acronym. Chunks the vocabulary itself matches are already
    alphabetic in the shipped lexicon, so this narrows only the
    previously-unclaimed "shape" answer, never the "suffix" one.

    The UNABBREVIATING-SCRIPT guard (the script-property table's
    period_abbreviations, #1256) is a second, independent narrowing of
    the same verdict, on the same reasoning `is_title_shaped` already
    gives its own period-abbreviation inference (#323): a script with
    no period abbreviations at all has nothing for interior periods to
    ABBREVIATE, so a CJK word glued into period-separated single
    characters is not spelling an acronym either -- 'John Smith
    田.中.' and '김 민준 이.박.' stayed family at every release before
    this gate existed, and would otherwise have joined the ambiguous
    class by shape for the first time (measured regression, #516
    review round).

    What a "shape" verdict MEANS is the caller's question, not this
    one's: classify writes the tag, and Policy.unlisted_dotted_suffixes
    decides whether it is class membership.
    """
    if not _PERIOD_NOT_AT_END.match(text):
        return None
    # rules/T8: "a saint particle glued to a name is one name word" --
    # no title chunk claims it and no dotted shape reads it
    # (decisions/T8 (#1071))
    if glued_saint_cut(text, lexicon) is not None:
        return None
    chunks = [_normalize(c) for c in text.split(".") if c]
    if any(c in lexicon._sets.titles for c in chunks):
        return "title"
    if period_joined_credential(text, lexicon):
        return "suffix"
    if (len(chunks) >= 2 and all(c.isalpha() for c in chunks)
            and (text.isascii() or not in_unabbreviating_script(text))):
        return "shape"
    return None


def ambiguous_class_member(text: str, lexicon: Lexicon) -> bool:
    """Whether TEXT is a member of the LISTED ambiguous credential
    class, ignoring case and policy entirely (#289/#516).

    The case-INDEPENDENT half of the comma form's own candidate test
    (`ambiguous_class_candidate`, below, which ALSO admits a by-shape
    member where Policy allows it) and of `is_wholly_suffix`'s
    credential-lean disjunct: membership by vocabulary never needs the
    case fact, only the lean does. That split is what lets the comma
    form's lazy gate ask membership FIRST and pay for `one_case` only
    where this says yes (measured regression, #289/#516: forcing the
    fact first ran `own_words` -> `tag_marker_runs` for every
    single-token-after-the-comma name, none of them able to reach the
    class at all).

    Membership is the listed set, bare: a whole-token vocabulary match
    is not in this class at all, being settled ('M.A.', 'Ph.D.',
    'A.B.C.').

    Cheaper than `suffix_as_written(n, text, lexicon) or ...` would be
    here, and provably the same answer for UNDOTTED text: the Lexicon
    invariant that an ambiguous acronym is never also a suffix WORD
    (`__post_init__`'s gate_bypassed check) and is never counted
    without periods once it IS one (`suffix_as_written`'s own
    exclusion) together kill that predicate's two disjuncts once text
    is known to hold no period. One frame (`_normalize`) on the common
    path that never reaches the class, where the general predicate
    cost at least two (mechanisms.md#ONE-PREDICATE-PER-QUESTION's cost
    clause).

    The '.' gate here is DELIBERATELY STRICTER than S2's own
    dotted-form test (`_dotted`, a period after EACH letter or after
    each of two or more letter chunks): '.'
    anywhere excludes membership, so a single TRAILING period ('MA.',
    'Ed.') is excluded here even though the LEAN still reads it as
    the bare acronym's case ('Smith, MA.' -> suffix 'MA.', measured).
    Not a contradiction: the two questions this answers -- the
    comma-form CANDIDATE test below and the credential-lean disjunct
    -- are never asked of those shapes, the TAG path
    (`vocab:suffix-ambiguous`, read directly by the trailing peel and
    the post-comma slot) and H2's leading-title shape test already
    carrying them where they need to go.
    """
    if "." in text:
        return False
    n = _normalize(text)
    return (n in lexicon._sets.suffix_acronyms_ambiguous
            or n in lexicon._sets.suffix_words_ambiguous)


# #516's all-caps half, ONE PREDICATE for the shape test and its
# WHOLE-VOCABULARY exclusion, shared by the three sites that each
# needed the identical question answered (classify's tag emission,
# the comma decision's caps test -- `_segment.py`'s run test until #613
# moved the decision to `_comma.decide` -- and this module's own unit
# tests), where it had been spelled three times over (quality-review
# finding). The usual objection to sharing -- a call costing every
# default-policy parse a frame it cannot use -- does not apply: the
# trailing position is behind `CapsSuffixes.EVERYWHERE` (classify's
# first conjunct), and the comma decision, which IS on by default,
# asks C-level `isalpha()`/`isupper()` and the suffix tag first, so a
# comma name with no unlisted all-caps word never reaches it.
def caps_shape_candidate(text: str, lexicon: Lexicon, policy: Policy,
                         one_case: bool | None) -> bool:
    """Whether TEXT is an UNLISTED all-caps credential candidate: two
    or more alphabetic characters, or letter chunks joined by '-' or
    '/' (`_joined_capitals`, #752), no period (a period fails
    `isalpha()` and the joined pattern outright, which is what excludes
    the dotted spelling here for free -- no separate '.' test needed),
    written in a name
    `one_case` says is mixed (`one_case is False`; `None`, "not
    established", declines exactly as if the name were one case).

    UNLISTED means in NO wordlist at all, not merely "no whole-token
    suffix vocabulary", and the roster is `_lexicon._VOCAB_FIELDS`
    itself rather than a list written out here -- checked directly
    against the lexicon rather than through a caller's tags (classify
    is deciding the very tag a caller would read, and `_comma.decide`
    asks of words classify left untagged). A hand-written roster is a second place to remember,
    and it had already gone wrong: it named eleven of the thirteen
    fields, leaving `surnames` and `honorific_tails` out, so
    a `Lexicon` whose `surnames` listed "dupont" still read
    `Jean Pierre DUPONT` as suffix `DUPONT` -- a caller listing a word
    as a SURNAME and getting it read as a credential is this switch's
    own worst failure, arriving through the one wordlist that says
    "this is a family name" (review round, #289/#516;
    `honorific_tails` was already excluded transitively, being a
    subset of `suffix_words` by Lexicon invariant, and joins the
    roster for completeness rather than for a behavior change).
    Measured, #516 review rounds: particles, ambiguous particles,
    conjunctions, bound-given heads, a maiden marker ('NEE'/'GEB') and
    a title all join the shape by capitalization alone if their field
    is left unchecked.

    `suffix_acronyms_ambiguous` is in the roster, which also makes
    this predicate stand in for `ambiguous_class_member` wherever a
    caller needs "and not already a LISTED member" (undotted text's
    only path into that function is the identical membership test);
    its callers still test the listed set first, in C (classify's
    `n not in suffix_acronyms_ambiguous`, `_comma.decide`'s
    AMBIGUOUS_ACRONYM_TAG test), so a listed member never pays for
    the call.
    """
    if (policy.unlisted_caps_suffixes is CapsSuffixes.OFF
            or one_case is not False):
        return False
    if not text.isascii():
        text = unicodedata.normalize("NFC", text)
    if not (len(text) >= 2 and text.isalpha() and text.isupper()
            or _joined_capitals(text)):
        return False
    return not in_any_wordlist(_normalize(text), lexicon)


#: A word of letter chunks joined by '-' or '/' ('PU-PH', 'MD/MBA').
_JOINED_LETTERS = re.compile(
    r'(?:' + _LETTER + r')+(?:[-/](?:' + _LETTER + r')+)+')


# rules/S9: "an unlisted word of capitals whose letter chunks are joined
# by a hyphen or a slash, one of them of two or more letters, is that
# shape too" -- the caps shape's joined spelling (decisions/S9 (#752))
def _joined_capitals(text: str) -> bool:
    """Whether TEXT is capitals in letter chunks joined by '-' or '/',
    one chunk of two or more letters ('PU-PH', 'MS-OMPT', not 'A-B',
    'MD/' or 'PU-PH2'). Its callers test `isupper()` and a joiner in C
    first, so a word holding neither pays no frame."""
    if not (text.isupper() and _JOINED_LETTERS.fullmatch(text)):
        return False
    for chunk in _JOINERS.split(text):
        if composed_len(chunk) >= 2:
            return True
    return False


def is_caps_word(text: str) -> bool:
    """Whether TEXT is alphabetic capitals once NFC-composed: `isalpha()`
    is False for a combining mark, so the decomposed spelling of
    'ŽŠČ' would otherwise not be a caps word (#652). Callers test the
    text as written inline first, in C, and call this only for text
    that is not NFC (`unicodedata.is_normalized`, also C), so composed
    text pays no frame."""
    composed = unicodedata.normalize("NFC", text)
    return composed.isalpha() and composed.isupper()


def composed(text: str) -> str:
    """TEXT NFC-composed where it is not ASCII, so a letter typed as its
    base and a combining mark is one letter, as the vocabulary lookup
    reads it (#665). The per-token predicates (`is_initial_shaped`,
    `composed_len`) fold inline instead, a call per token being the
    frame budget's scaling cost."""
    return text if text.isascii() else unicodedata.normalize("NFC", text)


def composed_len(text: str) -> int:
    """The length of TEXT in letters as the writer sees them: code
    points once NFC-composed. A caps word admitted decomposed (#652)
    is longer than its composed twin, and the two-letter pair test
    (`John Smith, MÁ`) counts letters."""
    return len(text if text.isascii() else unicodedata.normalize("NFC", text))


#: The marks a given-name key keeps: the tilde on n and the cedilla on
#: c, which spell other letters in Spanish and Catalan (Peña, Llorenç),
#: where an acute or grave accent or a diaeresis is how the same name
#: is spelled with or without them (José, Jose).
_KEPT_MARKS = frozenset({("n", "\u0303"), ("c", "\u0327")})


def given_name_key(text: str) -> str:
    """`text` folded as `Lexicon.given_names` is matched: the
    `_normalize` fold, with the accents and the diaeresis dropped and
    the tilde on n and the cedilla on c kept. tools/es_given_names.py
    writes the list with this same fold."""
    out: list[str] = []
    for ch in unicodedata.normalize("NFD", _normalize(text)):
        if unicodedata.combining(ch) and not (
                out and (out[-1], ch) in _KEPT_MARKS):
            continue
        out.append(ch)
    return unicodedata.normalize("NFC", "".join(out))


def is_listed_given_name(text: str, lexicon: Lexicon) -> bool:
    """Whether `text` is in `lexicon.given_names`, as written or by
    `given_name_key`, so a caller's entry "José" matches as written
    and a list written without accents matches "José" too (rules/O6's
    veto, #959)."""
    names = lexicon._sets.given_names
    return bool(names) and (_normalize(text) in names
                            or given_name_key(text) in names)


def in_any_wordlist(n: str, lexicon: Lexicon) -> bool:
    """Whether the folded word `n` is in ANY of the lexicon's wordlists
    (`_lexicon._VOCAB_FIELDS`, the whole roster but four): the caps
    shape's "unlisted" (`caps_shape_candidate`), where a word a caller
    listed even as a SURNAME must never become a credential.

    The four left out: `title_phrases`, whose entries are two words and
    so never one; `titles_ambiguous`, a title that may be a given
    name, which outside a title phrase is read as the unlisted word it
    is there (rules/H9: "and elsewhere a name word") -- a phrase is two
    words and a comma part read by this shape is one; and
    `given_name_abbreviations`, a given name written short (#789),
    whose one reader is H2's shape, so anywhere else its word reads as
    the unlisted word it is ('John Smith, JAS' keeps suffix 'JAS');
    and `given_names`, whose one reader is O6 (#959), for the same
    reason ('Ana Pérez, LUIS' reads as with the list empty)."""
    sets = lexicon._sets
    for field in _LISTED_FIELDS:
        if n in getattr(sets, field):
            return True
    return False


_LISTED_FIELDS = tuple(f for f in _VOCAB_FIELDS
                       if f not in ("title_phrases", "titles_ambiguous",
                                    "given_name_abbreviations",
                                    "given_names"))


#: The wordlists that claim a word as something OTHER than name text.
#: `surnames` and `bound_given_names` are left out: they say a word IS
#: a name word ('Kim', 'Abdul'), the opposite claim; and so is
#: `titles_ambiguous`, a title that may be a given name (rules/H9), with
#: `title_phrases`, whose two-word entries never match one word; and so
#: is `given_name_abbreviations`, a given name written short (#789), left
#: out of `_LISTED_FIELDS` above, with `given_names` (#959).
_NON_NAME_FIELDS = tuple(f for f in _LISTED_FIELDS
                         if f not in ("surnames", "bound_given_names"))


#: What a word written in capitals may hold besides its letters: the
#: apostrophes and hyphens a surname writes inside it (`O'BRIEN`,
#: `ALLIOT-MARIE`). Anything else -- a full stop, a slash, a digit, a
#: bracket or quotation mark -- says the word is no name written in
#: capitals (`DR.`, `N/A`, `GS.TS.`), rules/O9.
_CAPITALS_JOINERS = frozenset("'’ʼ-‐‑")


def is_capitals_word(text: str) -> bool:
    """Whether TEXT is a name written in capitals, as rules/O9 reads
    one: two or more letters in capitals ending the word, after any
    lowercase prefix glued in front (`DUPONT`, `O'BRIEN`, `McDONALD`,
    `d'ESTAING`), with nothing in it but letters, their combining marks
    and `_CAPITALS_JOINERS`. Single letters joined by a hyphen are
    initials (`J-P`), and a word whose capitals are one letter is a
    name in mixed case (`PhD`, `McD`). A combining mark is passed over
    in the letter's run, so a capital typed as its base and an accent
    (NFD) reads as its composed spelling does (#652). A
    lowercase letter whose capital is not one character (`ß`) counts as
    written in capitals, as `written_as_a_name` reads it."""
    word = text
    # a joiner at either end is a quotation mark or a dash, not a name
    # written with one inside it ('MBA', -AB)
    if not word or word[0] in _CAPITALS_JOINERS or word[-1] in _CAPITALS_JOINERS:
        return False
    capitals = 0
    chunk = longest = 0
    i = len(word)
    while i:
        i -= 1
        ch = word[i]
        if ch.isupper() or ch.islower() and len(ch.upper()) != 1:
            capitals += 1
            chunk += 1
            continue
        if ch.islower():
            break  # the prefix glued in front: McDONALD, d'ESTAING
        if ch in _CAPITALS_JOINERS:
            longest = max(longest, chunk)
            chunk = 0
            continue
        if unicodedata.category(ch) in ("Mn", "Mc", "Me"):
            continue
        return False  # a full stop, slash, digit, bracket or caseless letter
    else:
        i = -1
    if i >= 0 and not all(c.isalpha() or c in _CAPITALS_JOINERS
                          or unicodedata.category(c) in ("Mn", "Mc", "Me")
                          for c in word[:i]):
        return False
    longest = max(longest, chunk)
    return capitals >= 2 and longest >= 2


def written_as_a_name(text: str) -> bool:
    """Whether TEXT is written the way a name is written in mixed case:
    it holds a capital (or titlecase letter) and its last LETTER is
    lowercase -- #564's test for the name's case contrast (Derek).
    'Smith', 'DiCaprio', 'IJzerman', 'al-Rashid', "d'Estaing",
    'McDonald', 'ǅokić' pass. A surname written in capitals fails
    whatever is glued in front of it ("d'ESTAING", 'al-ASSAD',
    'McDONALD', 'FitzGERALD', 'DeVITO', 'St-PIERRE'), and so do a lone
    capital and a lowercase-only word.

    The letter read is the last one that carries case evidence, not the
    last character. The word is composed first (NFC), so a name typed
    with decomposed accents reads as its composed spelling ('André'
    ends in 'é', not in the combining accent). Passed over, as no
    evidence of case: every non-letter ("Jones'", 'Smith2', 'Smith)'),
    every caseless letter ("Jonesʼ" with U+02BC, 'Wafāʾ', 'Smith李'),
    and a lowercase letter whose capital is not a single character
    ('ß' -> 'SS', 'ĸ' with none): 'WEIß' and 'KAĸ' are written in
    capitals, 'Weiß' is not. One call and no generator, so a word costs
    one frame."""
    word = unicodedata.normalize("NFC", text)
    i = len(word)
    while i:
        i -= 1
        ch = word[i]
        if not (ch.isupper() or ch.islower() or ch.istitle()):
            continue  # a non-letter or a caseless letter
        upper = ch.upper()
        if ch.islower() and (upper == ch or len(upper) != 1):
            continue
        # the capital is asked here, of the word that has a letter to
        # read; one with none falls through below ('李', '2', 'ß')
        return ch.islower() and text != text.lower()
    return False


def claimed_as_non_name(n: str, lexicon: Lexicon) -> bool:
    """Whether a wordlist claims the folded word `n` as a title,
    particle, connective, credential, generation, maiden marker or
    honorific -- not name text. #564's `_comma._name_contrast`
    asks it: such a word does not supply the name's case contrast. A
    different question from `in_any_wordlist`'s, which a surname list
    must also answer yes to."""
    sets = lexicon._sets
    for field in _NON_NAME_FIELDS:
        if n in getattr(sets, field):
            return True
    return False


# The candidate test for a comma part read before classify
# (rules/C4, decisions/S9): segment's C2 flag on a tail part.
def ambiguous_class_candidate(text: str, lexicon: Lexicon,
                              policy: Policy) -> bool:
    """Whether TEXT is a CANDIDATE for the ambiguous credential class
    as segment's C2 flag asks it of a part past the second comma,
    before classify has tagged anything (`_segment.py`'s `class_run`;
    the comma's own decision, `_comma.decide`, reads classify's tags
    instead, #613): the LISTED half (`ambiguous_class_member`, case-free) OR, where Policy
    admits it, the SHAPE an unlisted dotted token wears
    (`period_joined_vocab`'s third verdict, #516).

    Case-free throughout, and the CAPS half of the class is
    deliberately not here: its real site is `_comma.decide`, which
    calls `caps_shape_candidate` directly because the caps shape needs
    the name's contrast. A second route through here existed briefly,
    behind an optional `one_case` parameter no production caller ever
    passed -- segment had nothing to hand in at the single-token
    test it then made -- so the branch
    answered False for every name the library parsed and only the
    unit tests reached it (review-round finding, #289/#516). A dead
    second route is a place for the two to disagree, not a
    convenience.

    A period anywhere is the gate for even ASKING the shape question,
    checked before the shape's own two calls: `period_joined_vocab`
    already declines a period-free text, but a Python-level call is
    not free and a comma name's post-comma part usually has no period
    ("Smith, John") -- measured regression, #516 review round, fixed
    by hoisting the same cheap substring test `ambiguous_class_member`
    already makes for its own reason. Where a period IS present,
    `suffix_as_written` runs only after `period_joined_vocab` says
    "shape": a dotted whole-token match with no single-chunk
    vocabulary hit of its own ('A.B.C.', via 'abc') would otherwise
    read "shape" from this function's chunk-level view alone,
    oblivious to the WHOLE-token match `suffix_as_written` already
    settled -- the same precedence classify's own tag order gives it
    (`vocab:suffix` is set before `period_joined_vocab` is even
    consulted).

    A LISTED member spelled with its periods is excluded from the
    shape branch by the same test classify's own shape branch makes:
    a caller who puts a dotted entry in `suffix_acronyms_ambiguous`
    has said the word is a listed member of this class, and reading
    it by shape instead loses the case lean the listing asks for
    (review-round finding, #289/#516 -- `Jack A.B.` with 'a.b' listed).
    It cannot change the answer for the shipped vocabulary, whose
    ambiguous entries carry no period at all.

    This function and classify's tag emission (`_tags_for`'s
    `derived == "shape"` branch) still ask the SAME question twice, of
    necessity: segment's C2 flag runs before `classify` and has no
    tags to read yet, so the two stages cannot share the call. Kept from
    drifting by
    `test_classify.test_ambiguous_class_candidate_agrees_with_the_tag`,
    which asks both of the same texts, rather than by a sentence
    alone.
    """
    if ambiguous_class_member(text, lexicon):
        return True
    if "." in text:
        # `_normalize` stays behind the shape verdict, where it always
        # was: it is a call, and a dotted post-comma token that is not
        # acronym-shaped at all ('Jr.') must not pay for it.
        if not (policy.unlisted_dotted_suffixes
                and period_joined_vocab(text, lexicon) == "shape"):
            return False
        n = _normalize(text)
        return (n not in lexicon._sets.suffix_acronyms_ambiguous
                and not suffix_as_written(n, text, lexicon))
    return False


# mechanisms.md#UNIT-PARTITION: "A rule that counts name words counts
# those units, and takes each whole or not at all" -- C3's count before
# a comma being the stated exception (`SURNAME_UNIT_TAGS`). The walk is shared
# by readers that hold the facts in different forms: post_rules and
# `_comma._whole_name` read classify's TAGS, while `name_word_count`
# builds the same tag names from the vocabulary
# (`surname_unit_tags`). One walk over tag sets, so the two cannot
# disagree about where a unit ends (mechanisms.md#ONE-PREDICATE-PER-
# QUESTION) -- only, at worst, about a token's facts, which
# test_classify's agreement test pins.
def unit_ends(tags: Sequence[Set[str]], chain: bool = True) -> list[int]:
    """The END (one past the last index) of each unit of `tags`, in
    order, partitioning `range(len(tags))`: one name word each, except
    where another rule has already made several words one name -- a
    particle and the words it chains (P2), a conjunction-joined run
    (P3), and a bound given-name word with the word it completes (P5).
    Each element is the tag set of one token, read for "particle",
    "conjunction", "vocab:bound-given" and "vocab:suffix".

    `chain` picks how far a particle reaches. True is P2's chain: the
    particle run and every word after it up to the next stop ("van der
    Berg Smith" is one unit). False is P1's fold reach: the particle
    run and the ONE unit it attaches to, so "de Mesnil Jean" is two --
    the count rules/C3 needs before a comma, where under a
    family-first order that part is family 'de Mesnil', given 'Jean'
    (#575).

    RECURSIVE, and that is the whole point: what a conjunction or a
    bound given-name word joins is the next UNIT, not the next word.
    Absorbing a single index instead strands a particle at the end of
    the unit, severed from the words it chains -- "de la Vega y la
    Vega" cut between `la` and `Vega`, reporting family
    "de la Vega y la", which is the same defect as a bare particle
    opening the given name, mirrored."""
    n = len(tags)

    def end_of(i: int) -> int:
        if "particle" in tags[i] and not chain:
            j = i + 1
            while j < n and "particle" in tags[j]:
                j += 1
            end = (end_of(j) if j < n and "conjunction" not in tags[j]
                   and "vocab:suffix" not in tags[j] else j)
        elif "particle" in tags[i]:
            j = i
            while j + 1 < n and "particle" in tags[j + 1]:
                j += 1
            # ... then the words it joins, stopping where the next
            # particle starts a group of its own, at a suffix word (the
            # stop _group's chain uses), or at a conjunction, which the
            # shared loop below joins to the whole unit after it rather
            # than to the one word after it.
            while (j + 1 < n
                   and "particle" not in tags[j + 1]
                   and "conjunction" not in tags[j + 1]
                   and "vocab:suffix" not in tags[j + 1]):
                j += 1
            end = j + 1
        else:
            end = i + 1
            if "vocab:bound-given" in tags[i] and end < n:
                end = end_of(end)
        while end + 1 < n and "conjunction" in tags[end]:
            end = end_of(end + 1)
        return end

    ends: list[int] = []
    i = 0
    while i < n:
        i = end_of(i)
        ends.append(i)
    return ends


#: The facts rules/C3's count before a comma reads (#575): a
#: particle starts a surname unit, and a suffix word stops it -- any
#: suffix word, a wider stop than group's particle chain makes, which
#: a suffix word ends only where a suffix run would start at it
#: (decisions/P2, #1177); #1259 left this count as it was. A word
#: that is ALSO title vocabulary ('Freiherr', 'St') LEADING the part is
#: not a particle here: in front of a name it reads as the title it
#: also is (rules/H1), so 'Freiherr von Berg, PhD' keeps its title,
#: while inside a surname it chains as P1 and P2 chain it ('de St
#: Pierre' is one surname). A bound given-name head that is also a
#: particle ('Abu') stays a particle: 'Abu Bakar, Ed' is a surname
#: before the comma, as 2.0 through 2.3 read it. Neither of the other
#: two joins `unit_ends` knows is read. A bound
#: given-name pair builds a GIVEN name, and P5 gives up a family word
#: where the name has no other ('abdul Salam' alone is given 'abdul',
#: family 'Salam'), so before a comma it is not one surname. Whether
#: P3 joins a single-letter connective depends on the words of the
#: whole name -- 'Carod i Rovira, Josep' joins as four words where
#: 'Ortega y Gasset' alone, three words, does not -- and the count is
#: part of deciding what the whole name is, so a count taken before
#: group could reach P3's answer only by copying P3. script_segment
#: and `name_word_count` build these facts from the vocabulary
#: (`surname_unit_tags`); `_comma._whole_name` derives them from
#: classify's tags (`surname_unit_facts`), so the counts read one set
#: of facts.
SURNAME_UNIT_TAGS = frozenset({"particle", "vocab:suffix"})
_PARTICLE_ONLY = frozenset({"particle"})
_SUFFIX_ONLY = frozenset({"vocab:suffix"})
_NO_TAGS: frozenset[str] = frozenset()
def surname_unit_facts(tags: Set[str], leading: bool) -> frozenset[str]:
    """`SURNAME_UNIT_TAGS` for one token, from classify's tags: the
    reading `_comma._whole_name`'s count before a comma takes.
    `leading` is whether
    the token opens the part."""
    particle = ("particle" in tags
                and not (leading and "vocab:title" in tags))
    if "vocab:suffix" in tags:
        return SURNAME_UNIT_TAGS if particle else _SUFFIX_ONLY
    return _PARTICLE_ONLY if particle else _NO_TAGS


def surname_unit_tags(text: str, lexicon: Lexicon,
                      leading: bool) -> frozenset[str]:
    """`surname_unit_facts` for one token from the vocabulary alone --
    the vocabulary's view of classify's tags, for a count taken before
    classify runs (script_segment's) or without its tags
    (`name_word_count`), with
    classify's own tests: particle and title membership,
    `suffix_as_written`, and the period-joined derivation.
    Kept from drifting by
    test_classify.test_surname_unit_tags_agree_with_classify."""
    n = _normalize(text)
    # classify's whole-token test, then its period-joined derivation
    # for a token no whole-token title or suffix claimed ('JD.CPA'),
    # asked only of a token with a period, which it needs
    suffix = suffix_as_written(n, text, lexicon) or (
        "." in text and n not in lexicon._sets.titles
        and period_joined_vocab(text, lexicon) == "suffix")
    particle = n in lexicon._sets.particles and not (
        (leading and n in lexicon._sets.titles) or _spells_an_initial(n, text))
    if suffix:
        return SURNAME_UNIT_TAGS if particle else _SUFFIX_ONLY
    return _PARTICLE_ONLY if particle else _NO_TAGS


#: The connective after a title that may be a given name which makes
#: the two a title phrase, 'Dean of Students' (rules/H9). Coordinating
#: connectives are not: 'Dean and Mary Smith' is two people.
_PHRASE_LINKS = frozenset({"of"})
#: The connectives whose object a modifier after them is in, 'of the
#: United States', 'The Grand Master'; 'and' joins two titles instead.
_OBJECT_LINKS = frozenset({"of", "the"})

#: The article that is the phrase partner of a style that may be a
#: given name, written short (rules/H9, #999): `The Hon`.
_STYLE_ARTICLES = frozenset({"the"})


# rules/H9: "a word no listed phrase holds is a title only behind a
# style or a modifier, or before `of`" -- whether the word heads a title
# of itself, asked of the phrases `attaches` compiled rather than of a
# property of its own
def in_a_title_phrase(text: str, lexicon: Lexicon) -> bool:
    """Whether a phrase of `lexicon._sets.title_phrases` that classify can
    read holds `text`."""
    return _normalize(text) in _phrase_words(
        lexicon._sets.title_phrases, lexicon._sets.titles, lexicon._sets.titles_ambiguous)


@functools.lru_cache(maxsize=16)
def _phrase_words(phrases: frozenset[str], titles: frozenset[str],
                  contested: frozenset[str]) -> frozenset[str]:
    """The words of the phrases classify can read: two words, each a
    title or a title that may be a given name, as its pair test asks.
    A phrase it never consults makes no word report."""
    listed = titles | contested
    pairs = (p.split(" ") for p in phrases)
    return frozenset(w for ws in pairs
                     if len(ws) == 2 and all(w in listed for w in ws)
                     for w in ws)


# rules/H9: "the word is a title only inside a title phrase, and
# elsewhere a name word" -- both halves, the partners of a title that may
# be a given name and of a modifier at the head of the name, each its
# bullet's (decisions/H9 #752)
def title_readings(texts: Sequence[str], folded: Sequence[str],
                   lexicon: Lexicon, *, head: bool,
                   titled: Sequence[bool] | None = None) -> list[bool]:
    """Which of these words, one part of the name in order, read as
    title words. Where none of them is a title that may be a given name
    or a modifier, the listed titles answer alone, which every caller
    asks first, in C, so that a name with neither pays no frame.

    A word of `titles_ambiguous` that is not also in `titles` (where a
    caller listing it makes it a title everywhere) is a title only
    beside a partner: a
    modifier, a style, or a title it stands behind in `title_phrases`,
    before it, and for a style of `title_abbreviations` the article
    'the' before it ('The Hon' under a Chinese choice); or 'of', or a title it stands in front of in
    `title_phrases`, after it. A salutation is never one, nor any other
    title before it ('Mr Dean Smith'), nor a title after it that it
    does not attach to ('SMITH, DEAN MR.', a given name and the
    salutation a donor list writes after it). Its neighbours are asked
    as LISTED, so 'Vice Dean' reads 'Vice' as the partner of 'Dean'
    whatever the modifier test below makes of 'Vice', save a word before
    it that is itself a title that may be a given name, which is a
    partner only where its own phrase made it a title ('Grace Dean
    Smith' reads 'Grace' as the given name, and 'Dean' with it).

    Where `head` is true -- the part before the first comma -- a word
    of `title_modifiers` is a title only with a head title behind it in
    its run of titles: any title that is not a modifier, or a word H2's
    shape reads as one, before 'of' ('Mother Superior of the Convent'),
    behind a title that attaches to it in `title_phrases` ('Princess
    Royal', #913), or in the object of 'of' or 'the' there (decision 10 of
    decisions/vocabulary-model). Only the leading run is the head: a
    modifier outside it is read as listed, one ending the name being
    H5's. A
    word in both sets takes the modifier test in every part, that run
    being its phrase ('Lau, Wing Kai' reads 'Wing' as the given name).
    After a comma any other modifier is read as listed: a part there
    that is a lone title word is the person's role ('John Smith,
    Resident'), and reading it as a name would reverse the name
    (decisions/H9).

    `texts` are the words as written, for the shape test; `folded`
    their `_normalize`d forms; `titled` which of them a caller already
    reads as titles, where that is more than `titles` lists (classify's
    period-joined `Lt.Gov.`), else membership in `titles`. Only a word
    of the two sets is ever read out of the title."""
    contested = lexicon._sets.titles_ambiguous
    modifiers = lexicon._sets.title_modifiers
    titles = lexicon._sets.titles
    # a word in titles is a title wherever it stands, whatever else it
    # is listed as; one of titles_ambiguous alone is listed as a title
    # to its neighbours and read by its phrase
    reading = [n in titles or n in contested for n in folded]
    if titled is not None:
        reading = [r or t for r, t in zip(reading, titled)]
    listed = list(reading)
    phrases = lexicon._sets.title_phrases
    last = len(folded) - 1
    for i, n in enumerate(folded):
        if n in titles or n not in contested or n in modifiers:
            continue
        prev = folded[i - 1] if i else None
        nxt = folded[i + 1] if i < last else None
        reading[i] = bool(
            # the word before as it was READ, left to right: a title that
            # may be a given name and stands in no phrase is no partner
            # ('Grace Dean Smith')
            (prev is not None and reading[i - 1]
             and (prev in modifiers or prev in lexicon._sets.title_styles
                  or f"{prev} {n}" in phrases))
            # rules/H9: "a style that may be a given name, written short,
            # has its phrase partner in the article before it" -- 'The
            # Hon' under a Chinese choice (decisions/H9, #999)
            or (prev in _STYLE_ARTICLES and n in lexicon._sets.title_styles
                and n in lexicon._sets.title_abbreviations
                and prev in lexicon._sets.conjunctions)
            or (nxt is not None
                and ((nxt in _PHRASE_LINKS and nxt in lexicon._sets.conjunctions)
                     or (listed[i + 1] and f"{n} {nxt}" in phrases))))
    # left to right, whether the run so far has passed 'of' or 'the': a
    # modifier after it is in the object of a phrase ('President of the
    # United States', 'the Queen's Bench'), which no head need follow. A
    # coordinating connective opens no object: 'Mr. and Mrs. Wing Lau'
    # is two salutations and a given name
    linked = [False] * len(folded)
    conjunctions = lexicon._sets.conjunctions
    for i in range(1, len(folded)):
        if reading[i - 1] or folded[i - 1] in conjunctions:
            linked[i] = linked[i - 1] or folded[i - 1] in _OBJECT_LINKS
    # the head of the name is its LEADING run of titles and connectives:
    # a modifier ending the name is H5's trailing run, read as listed,
    # save one that may be a given name, which the loop below reads
    # wherever it stands
    lead = 0
    if head:
        while lead < len(folded) and (reading[lead] or folded[lead] in conjunctions
                                      or is_title_shaped(texts[lead], lexicon)):
            lead += 1
    # right to left, so each modifier knows whether a head title stands
    # behind it before the run is broken; a connective carries the run
    behind = False
    for i in range(last, -1, -1):
        n = folded[i]
        if (n in modifiers and reading[i]
                and ((head and i < lead) or (n in contested and n not in titles))):
            reading[i] = behind or linked[i] or (
                i < last and folded[i + 1] in _PHRASE_LINKS
                and folded[i + 1] in conjunctions) or (
                # a title before it that attaches to it ('Princess Royal')
                i > 0 and reading[i - 1]
                and f"{folded[i - 1]} {n}" in phrases)
            behind = reading[i]
        elif reading[i] or (head and is_title_shaped(texts[i], lexicon)):
            behind = True
        elif n not in conjunctions:
            behind = False
    return reading


def name_word_count(texts: Sequence[str], lexicon: Lexicon,
                    policy: Policy, letters_one_case: bool | None = None,
                    members: Set[int] = frozenset()) -> int:
    """How many of these texts are NAME words -- not suffix
    vocabulary, not title vocabulary, nor a numeral the trailing fork
    reads as the generation ending the name words (rules/C3).

    rules/C4's count for the ambiguous class, and it is of names
    rather than of words because 'Smith Jr., MA' is two tokens and one
    name: counting tokens there flips the structure and hands the
    family to `given`, which no reading of that string wants
    (decisions/S6). The suffix half asks the POLICY-selected
    predicate, the same one is_wholly_suffix asks, so the two agree
    about what a suffix word is; the title half asks BOTH the listed
    lookup and H2's shape test (`is_title_shaped`) -- a bare
    `lexicon._sets.titles` lookup here read 'Xyz.' as a name word where the
    leading peel reads it as a title, and that divergence is recorded
    once, at `is_title_shaped` itself
    (mechanisms.md#ONE-PREDICATE-PER-QUESTION).

    It counts UNITS holding a name word, not tokens (#575,
    mechanisms.md#UNIT-PARTITION): a particle chain (P2) builds one
    family name, so 'De La Cruz' is one name word and 'De La Cruz, Ed'
    reads as 'Royce, Ed' does. Why the other two joins are not read
    here: `SURNAME_UNIT_TAGS`.

    `letters_one_case` is `is_wholly_suffix`'s, for the same reason,
    and the case fact the generation fork reads (`ParseState.one_case`).
    `members` holds the positions of split credentials' members
    (classify's tag), each half a credential rather than a name, so
    one opening the part stays no name word, as `_comma._whole_name`
    reads it.
    """
    lenient = policy.lenient_comma_suffixes

    # One pass: each token's name-word verdict, and whether any token
    # is a particle. With none, every token is a unit of its own and
    # the count is a sum, so the commonest comma names never build the
    # units -- and pay no frame the token loop did not already pay.
    names: list[bool] = []
    suffixes: list[bool] = []
    has_particle = False
    lead: int | None = None
    lead_suffix = False
    # map, not a comprehension, which is a frame of its own on 3.11
    folded = list(map(_normalize, texts))
    # rules/H10: "the run reads as that title where a title the run
    # keeps stands behind it" -- the run read as the title it spells, so
    # the title test and H9's phrase test below see it. Unlike classify's
    # fold, which runs only where the name already holds a word H9
    # reads, this one always runs, so a run alone brings the phrase test
    # in. The set test first, C-level, so a dotted word that spells no
    # marked title pays no frame
    dotted: set[int] = set()
    for i, n in enumerate(folded):
        if ("." in n and n.replace(".", "") in lexicon._sets.dotted_titles
                and is_dotted_title(texts[i], n, lexicon)):
            folded[i] = n.replace(".", "")
            dotted.add(i)
    # rules/H9: "the word is a title only inside a title phrase" -- the
    # part before the comma is the head of the name, read as classify
    # reads it
    titled = (None if lexicon._sets.titles_ambiguous.isdisjoint(folded)
              and lexicon._sets.title_modifiers.isdisjoint(folded)
              else title_readings(texts, folded, lexicon, head=True))
    for i, n in enumerate(folded):
        text = texts[i]
        title = n in lexicon._sets.titles if titled is None else titled[i]
        if title and i in dotted:
            # a title only opening the part (behind any titles), and only
            # with a title, listed or by H2's shape, behind it and a word
            # of any kind behind that: H6 leaves the part's last word to
            # the family, so a title ending the part is not kept and the
            # run is given back ('U.S. Senator, Ed'); H3's floor is not
            # modelled here (decisions/H10)
            nxt = i + 1
            title = (lead is None and nxt < len(folded)
                     and ((folded[nxt] in lexicon._sets.titles
                           if titled is None else titled[nxt])
                          or is_title_shaped(texts[nxt], lexicon))
                     and nxt + 1 < len(folded))
        if n in lexicon._sets.particles:
            has_particle = True
        suffix = (is_suffix_lenient(text, lexicon) if lenient
                  else is_suffix_strict(text, lexicon, letters_one_case))
        name = not (suffix or title or is_title_shaped(text, lexicon))
        # the opening word behind any titles; the shape test asked again
        # only of a suffix word there, so a run of them pays no frame
        if lead is None and (name or suffix and not title
                             and not is_title_shaped(text, lexicon)):
            lead = i
            lead_suffix = not name and i not in members
        names.append(name)
        suffixes.append(suffix)
    # rules/C3: "A suffix word opening the part is a name word to the
    # count where a name word follows it" -- opening it behind its
    # titles, which stay no name word, this count being of names
    # (rules/C4)
    if lead_suffix and lead is not None and any(names[lead + 1:]):
        names[lead] = True
    # rules/C3: "a numeral ending the part, or standing before the
    # listed suffix words it ends with, that the trailing fork reads as the
    # generation is no name word", as a listed one is not
    # -- the suffix words stepped over as `_comma._whole_name` steps
    # over them, a dual of the title and suffix vocabulary included,
    # and a title that is no suffix word stopping both
    e = len(texts) - 1
    while e > 0 and suffixes[e]:
        e -= 1
    # the numeral's shape asked in C first, as group's count asks it, so
    # a part ending in a plain word pays no frame
    if (e > 0 and names[e]
            and _ROMAN.match(texts[e].rstrip(".")) is not None
            and ends_in_a_generation(texts[e - 1:e + 1], letters_one_case)):
        names[e] = False
    if not has_particle:
        return sum(names)
    count = 0
    start = 0
    for end in unit_ends([surname_unit_tags(t, lexicon, i == 0)
                          for i, t in enumerate(texts)],
                         chain=False):
        if any(names[start:end]):
            count += 1
        start = end
    return count


def is_wholly_suffix(texts: Sequence[str], lexicon: Lexicon,
                     policy: Policy, one_case: bool | None = None,
                     letters_one_case: bool | None = None,
                     strict: bool = False) -> bool:
    """Every token in a RUN counts as a suffix -- C1's suffix test of
    a run, shared by `_comma.decide`, segment's C2 flag on a tail part
    and the peel (#319).

    NOT the plural of _script_segment._is_post_nominal, which asks
    is_suffix_strict per token. This asks the POLICY-selected predicate
    (lenient by default), plus period_joined_vocab, delimiter
    transparency and the Ph./D. merge. 'V.' is the input that tells
    them apart: it satisfies this predicate but is not a post-nominal
    -- and reading one for the other IS the #319 bug.

    An EMPTY run is False, not vacuously True: v1's suffix-comma
    detection fails on an empty parts[1] ('John Smith,, MD' is a
    family-comma parse). The 'wholly' idiom agrees -- _script_matcher's
    whole=True requires non-empty too -- which is why the name is that
    one rather than all_suffixes, where Python's all([]) would promise
    the opposite.

    An adjacent Ph./D. pair counts as ONE unit (v1's fix_phd extracted
    the credential pre-parse, so 'Smith, Ph. D.' read as suffix-comma):
    `split_pair`'s "suffix" answer, which group's merge and
    `_comma._pieces` read too. Its "split" answer ('Pharm D') does not
    count here: that pair is a member of the ambiguous class, which no
    run test takes by itself, as it takes no bare 'Ma' (rules/C4's
    count reads it instead).

    `one_case` is ParseState.one_case, and it admits the LEAN: a bare
    ambiguous acronym written in capitals inside a mixed-case name is
    a credential here, so 'Steven Hardman, MD, DO, DDS' reads its
    third segment as the credential run it is (#289). None -- the
    default, and what every caller with no state to ask has -- reads
    as no lean and is this predicate's behavior in every release
    before 2.4.

    `letters_one_case` is the same fact asked a different question,
    and the two are kept apart because a caller that wants no lean
    still wants the letters read by T4: under
    `lenient_comma_suffixes=False` the strict test vetoes an
    initial, and in a name written in one case a bare lowercase
    letter is one ('john smith, v' reads as 'JOHN SMITH, V', #727).
    The lenient test takes a suffix word whatever its shape, so the
    default never reads it.

    Neither Policy.unlisted_dotted_suffixes NOR
    Policy.unlisted_caps_suffixes reaches this predicate: admitting a
    by-shape member here unconditionally (an earlier version of this
    docstring described exactly that, for the dotted half alone)
    bypassed both the lean AND the NAME-word count, and combined with
    C1's then TOKEN-count disjunct in segment (deleted in #613, when
    the decision moved to `_comma.decide`) it flipped
    'Smith Jr., A.B.' to given 'Smith', suffix 'Jr., A.B.' with a
    self-contradicting report ("holds 1 name words, so it is read as
    a credential run") -- proved by mutation testing to be otherwise
    unreached: nothing but this predicate's own two unit tests
    depended on it, and 'John Smith, X.Y.Z.' flipped correctly through
    the NAME-word count alone (#516 review round). Neither by-shape
    class, dotted or caps, reaches the comma form through this
    predicate at all -- only through classify's shape tags and
    `_comma.decide`'s caps test (#613).

    A delimiter core glued to one word ('MD;', ';PhD') leaves the word
    read by the test it would get without the core (D15, rules/C10),
    so 'MD;' counts where 'MD' does. `strict` asks the strict token
    test whatever the policy says: `_comma.decide` passes it behind a
    head that is not a whole name, where C8 reads 'Smith, V MD' with
    the initial veto, so that 'Smith, V; MD' reads as its space twin.
    """
    if not texts:
        return False
    lenient = policy.lenient_comma_suffixes and not strict
    # v1 expand_suffix_delimiter parity (#206): a configured delimiter
    # is TRANSPARENT in the all-suffix tests -- v1 split the part string
    # on the delimiter before checking, so the delimiter never counted;
    # the built-in cores are transparent the same way (rules/C10)
    cores = delimiter_cores(policy.extra_suffix_delimiters)
    inner = glued_cores(policy.extra_suffix_delimiters)

    def counts_as_suffix(text: str) -> bool:
        if (one_case is not None
                and ambiguous_class_member(text, lexicon)
                and ambiguous_lean(text, one_case, lexicon_cue(
                    _normalize(text), lexicon)) == "credential"):
            return True
        if ((is_suffix_lenient(text, lexicon) if lenient
             else is_suffix_strict(text, lexicon, letters_one_case))
                or period_joined_vocab(text, lexicon) == "suffix"):
            return True
        # the split only where a core stands in the word: the built-in
        # ';' makes `inner` non-empty for every policy, and a call per
        # word would be a frame on every name word a run test asks
        for core in inner:
            if core in text:
                stem = glued_stem(text, inner)
                if stem is not None:
                    return counts_as_suffix(stem)
                return splits_into_suffixes(text, inner, lexicon)
        return False

    merged = list(texts)
    k = 0
    while k < len(merged) - 1:
        if (SPLIT_PAIR_OPENS.fullmatch(merged[k])
                and split_pair(merged[k], merged[k + 1], lexicon)
                == "suffix"):
            merged[k:k + 2] = ["phd"]
        else:
            k += 1
    return all(t in cores or counts_as_suffix(t) for t in merged)


# The two derived views of a marker vocabulary, cached per-vocabulary
# on _script_segment._longest_entry's precedent -- same function shape
# (a scalar derived from a vocabulary frozenset), same key space, and
# its reasoning for maxsize=16 carries over verbatim: a process holds
# the default vocabulary plus one per constructed pack parser, so 16
# bounds many-lexicon churn without ever evicting in normal use.
# (NOT _extract._delimiter_chars' precedent, which these once cited:
# that one is consulted once per parse, so it says nothing about a
# lookup on the per-token path.) Keying on the frozenset costs a
# cached hash, not a sweep of its contents.
@functools.lru_cache(maxsize=16)
def _longest_marker(markers: frozenset[str]) -> int:
    """How many words the longest entry of `markers` spans -- the
    lookahead bound, computed from the vocabulary rather than fixed at a
    literal so a caller's four-word entry works and an all-single-word
    set leaves the common path at one lookup. Entries are stored
    space-joined with single separators, so the space count IS the word
    count."""
    return max((entry.count(" ") + 1 for entry in markers), default=0)


@functools.lru_cache(maxsize=16)
def _marker_heads(markers: frozenset[str]) -> frozenset[str]:
    """The first word of every entry -- the set a run can possibly open
    with. Entries are already stored per-word folded, so an entry's
    first word is the same fold the lookup builds."""
    return frozenset(entry.split(" ", 1)[0] for entry in markers)


def maiden_marker_head(n: str, markers: frozenset[str]) -> bool:
    """Could a maiden marker run START here? `n` is _normalize(word),
    passed in so callers fold once -- suffix_as_written's shape exactly
    ("`n` is `_normalize(text)`, passed in so callers normalize once"),
    and with no raw-text sibling for the same reason it has none: every
    caller is on the per-token path and has the fold in hand already.

    A SUPERSET test. True means only that some entry opens with this
    word, never that a run matches -- maiden_marker_run is the answer,
    and it calls this function, so the two cannot drift. Exported
    because a caller scanning a whole token stream needs to know
    whether assembling a candidate sequence is worth doing at all, and
    for almost every token it is not: _classify's pass would otherwise
    walk structural boundaries once per token to build a lookahead the
    predicate discards on this very test.
    """
    return n in _marker_heads(markers)


def maiden_marker_run(words: Sequence[str], markers: frozenset[str]) -> int:
    """How many of `words` a maiden marker claims, longest first; 0 for
    none.

    Phrases are stored space-joined and per-word normalized (_title_key's
    storage rule), so the key is rebuilt the same way here -- normalizing
    the joined phrase instead would leave interior periods.

    `words` must be words that stand TOGETHER -- one clause's, or one
    segment's. This answers only what the vocabulary says about the
    sequence it is handed; whether a sequence is a sequence is the
    caller's, and classify's contiguity rule is where that is decided
    for the token stream.

    Longest first, so a caller configuring both 'geb' and 'geb von' gets
    the phrase where it matches and the bare word everywhere else. The
    one answer to "does a marker start here, and where does it end": the
    stages that can call it do (classify over token texts, extract over
    a clause's whitespace words), and the stage that runs after classify
    reads the tags classify recorded instead
    (mechanisms.md#ONE-PREDICATE-PER-QUESTION).
    """
    # Fast path first: no entry opens with this word, so no length can
    # match. It cannot hide a match -- every key the loop builds opens
    # with _normalize(words[0]) unless that word folds away, and a
    # folded-away first word fails the n-word test below for every
    # n > 1 and is not a stored entry for n == 1.
    if not words:
        return 0
    head = _normalize(words[0])
    if not maiden_marker_head(head, markers):
        return 0
    cap = min(len(words), _longest_marker(markers))
    # Fold each word ONCE, then key from a prefix. _title_key(words[:n])
    # per candidate length re-folds the whole prefix every time, which
    # is quadratic in cap and makes a one-word hit cost more than a
    # two-word one -- the longest key is always built and discarded
    # first, and all but one shipped entry is a single word. The join
    # below IS _title_key's body over pre-folded words (per-word fold,
    # empties dropped, space-joined); test_vocab pins that the two
    # agree, since this is a copy of a fold whose definition lives in
    # _lexicon.
    folded = [head] + [_normalize(w) for w in words[1:cap]]
    for n in range(cap, 0, -1):
        key = " ".join(filter(None, folded[:n]))
        # a word that folds away is DROPPED from the key, so 'née'
        # followed by a lone '.' would key as 'née' and a one-word
        # marker would claim the period as part of its run. n words in,
        # n words out: anything else is not this key's n-word phrase.
        if key.count(" ") == n - 1 and key in markers:
            return n
    return 0



# rules/M3: "a marker followed by a comma is no marker"
def comma_follows_marker(word: str) -> bool:
    """Whether `word`, the one standing after a marker run inside a
    delimited clause, opens with a comma -- standing alone (' , ') or
    glued to the name after it (' ,Jones'). A comma glued to the marker
    itself ('née,') needs no test: that word is no marker to begin with,
    the vocabulary storing no comma. The one predicate for extract's M3
    test over whitespace words and group's M1 drop over tokens, which
    since #653 hold the same comma
    (mechanisms.md#ONE-PREDICATE-PER-QUESTION).

    The comma need not be the word's first character, only the first
    that is a comma or a letter or digit. A whitespace word can open
    with what the tokenizer drops or divides at -- a bidi mark, an
    emoji, a nakaguro -- so '\u200f, Jones' is a comma-led WORD only
    past its mark, while the token group asks about is ',' already;
    reading past the rest makes the two sites agree by construction
    (#653's second review)."""
    for ch in word:
        if ch in COMMA_CHARS:
            return True
        if ch.isalnum():
            return False
    return False


def tag_marker_runs(tokens: Sequence[WorkToken], comma_offsets: Sequence[int],
                    markers: frozenset[str],
                    folded: Sequence[str] | None = None) -> dict[int, str]:
    """Which tokens are maiden marker runs: index -> "vocab:maiden-marker"
    for a run's head, "vocab:maiden-marker-cont" for the rest.

    Returns the decision rather than rewriting the tokens: a caller
    that writes tags into the one pass that builds them (classify)
    consults this map rather than deciding a run twice, so a marker
    token is never replaced twice; a caller that never writes tags at
    all (own_words) reads the same map for its span instead.

    Moved here from classify (#289/#516) so a caller outside classify
    -- _pieces.own_words, when it has no marker map yet -- can build
    the SAME map classify would, rather than approximating it with a
    text-only head test. `_pieces.py` may import only _state and
    _vocab (tests/v2/test_layering.py), so the one shared function
    both sites call has to live here, in the layer both can reach.

    `folded` is _normalize per token; classify has already built it
    for the vocabulary-tag pass and hands it over so this pass costs
    no second fold, and a caller with only tokens (own_words' self-
    built path) omits it and pays the fold here instead -- paid only
    on that path, never on classify's, so the reference name's frame
    count is unchanged (#289/#516).

    The one sequence pass in this stage, and it has to be one: a marker
    entry may be a PHRASE whose words are not markers individually
    ('z', 'domu'), so no per-token membership test can find it.
    Left to right, longest first at each position, then skip past what
    the run claimed -- a second marker cannot start inside the first.

    This is where the tag is DECIDED for the stages that read it
    afterwards. group runs later and asks its questions of these tags
    rather than re-deriving the run (the recorded-answer half of
    mechanisms.md#ONE-PREDICATE-PER-QUESTION); extract runs EARLIER,
    before tokens exist, so it calls the predicate itself over the
    clause's whitespace words.

    A tagged run is structurally contiguous, and the test is
    one-directional: a role change IS a clause edge, so no run spans
    one, but not every clause edge is a role change -- two ADJACENT
    clauses of the same role are indistinguishable here, and
    'Jane (z) (domu) Jones' does tag a run across them. Both consumers
    refuse that run for reasons of their own (the piece walk never sees
    role-bearing tokens at all; the clause drop is scoped to one
    clause's span), so no reading depends on it today, and the claim
    this pass can honestly make is the weaker one. What it does
    guarantee is what _group._marker_run_pieces needs: a run inside the
    MAIN stream stays inside one segment. Without it this pass walked
    the whole span-sorted stream while group walked one segment --
    _segment keeps only role-less tokens and buckets them by the commas
    before them -- so a run half inside a bracketed clause was tagged
    whole and consumed as a proper PREFIX of itself, and
    'Anna z (domu) Nowak' read family 'Anna', maiden 'Nowak': the bare
    preposition eating the name, which is the exact damage the phrase
    entry exists to prevent. Refusing to tag such a run is the fix;
    truncating it instead would hand M2 the same wrong prefix one word
    shorter.
    """
    # the lookahead the vocabulary actually needs; 0 for an empty set,
    # which skips the pass entirely
    cap = _longest_marker(markers)
    if not cap:
        return {}
    if folded is None:
        folded = [_normalize(t.text) for t in tokens]
    n_tokens = len(tokens)
    # Deferred, not computed up front: only the contiguity walk reads
    # it, only a phrase vocabulary runs that walk, and only at a token
    # that opens an entry -- so a single-word vocabulary, and a
    # phrase vocabulary over a name holding no marker, never pay the
    # sweep at all.
    buckets: list[int] | None = None
    tags: dict[int, str] = {}
    i = 0
    while i < n_tokens:
        # The predicate's own head test first, over the fold the caller
        # already has: almost no token opens any entry, and for those
        # there is nothing to assemble. Same function maiden_marker_run
        # consults, so a token skipped here is one it would refuse.
        if not maiden_marker_head(folded[i], markers):
            i += 1
            continue
        # Bound the lookahead at the first structural boundary, so the
        # predicate is asked over the words that could form one run and
        # answers longest-first WITHIN them -- a two-word entry refused
        # at a clause edge still leaves a one-word entry starting there
        # free to match.
        limit = 1
        if cap > 1:
            if buckets is None:
                buckets = [comma_bucket(t.span.start, comma_offsets)
                           for t in tokens]
            role, bucket = tokens[i].role, buckets[i]
            while (limit < cap and i + limit < n_tokens
                   and tokens[i + limit].role is role
                   and buckets[i + limit] == bucket):
                limit += 1
        run = maiden_marker_run(
            [tokens[k].text for k in range(i, i + limit)], markers)
        if not run:
            i += 1
            continue
        tags[i] = "vocab:maiden-marker"
        for k in range(i + 1, i + run):
            tags[k] = "vocab:maiden-marker-cont"
        i += run
    return tags


def _normalized_for_script(text: str) -> str | None:
    """The guard AND the two normalizations single_script and
    effective_script's license path both need, single-sourced so they
    cannot drift: trailing full stops are dropped (FULL_STOPS, #323),
    then None for the two shapes neither ever classifies (nothing
    left, and the common all-ASCII Latin token -- skipped before
    normalizing, since ASCII is already NFC and every _SCRIPT_RANGES
    entry is non-ASCII regardless), else an NFC-normalized copy.

    Trailing stops, not raw: a period glued to a script-written token
    ('양.', '太郎.') is not a character of any script, so classifying
    raw text handed the token no script at all, and three readers
    spent that None -- the surname site stepped past the family name
    onto the given name ('양. 지훈' cut 지훈 in half), the order rule
    fell back to positional ('양 지훈.' lost family-first), and the
    segmenter's neighbour precondition missed a writer-drawn boundary
    ('山田太郎 田中.' consulted the segmenter on 山田太郎 as if it stood
    alone). The East Asian scripts this classifies (_policy's
    _EAST_ASIAN_SCRIPTS, the four that write no initials, #320) have no
    initials and no period abbreviations, so a stop on such a token
    carries no information about the word; on a Cyrillic word it is an
    initial's stop (`Б.`), dropped all the same, deliberately: the
    classification keys only a declared Cyrillic order (#1237), under
    which an initial is a word of the name in its script; ASCII text is stripped too,
    but the guard below returns None for it regardless, so 'Smith.'
    never classifies. TRAILING only, matching the surname site's own
    rstrip in _script_segment (the same arithmetic, not a shared
    gate -- this fold decides only whether the surname site, the order
    rule and the segmenter ever see the token): a leading stop is not
    a shape any script writes before a name word, and HIDING such a
    token from those three readers -- no script, so no surname site,
    which is what the tree before #323 did -- is safer than admitting
    it. Admitted, '.김민준' classifies as hangul, becomes a surname
    site, is declined by the head match (which rstrips) and falls
    through to a configured segmenter, which answering offset 1
    divides it into the stop and the name. The peel is not gated by
    this fold; its own rstrip carries a leading-stop token, see
    _script_segment. The vocabulary fold alone reads BOTH edges
    (_lexicon._normalize): '.씨' is still the honorific, and a lookup
    divides nothing.

    NFC, not raw: NFD input decomposes precomposed katakana onto a
    base character plus a COMBINING mark (U+3099/U+309A, which sit in
    the HIRAGANA block, not katakana's), so classifying raw NFD text
    can hand a pure-katakana token the kana license by accident.
    Decomposed hangul is conjoining jamo, which HANGUL holds, so the
    fold no longer decides a hangul token (decisions/nfd-shapes,
    #1087).

    Voicing marks, last: NFC composes a mark only where a precomposed
    kana exists (カ + U+3099 is ガ), so ア + U+3099, ン + U+3099 and
    every spacing mark (U+309B/U+309C) survive it, and all four marks
    sit in the HIRAGANA block. A mark voices the kana it follows and
    belongs to neither syllabary, so each one standing after a kana is
    deleted from the copy (_drop_kana_voicing_marks) and the token
    takes its base's script: ア゙イ is katakana, not kana-licensed
    Japanese (#596). A mark after anything else stays, and stays in
    the hiragana block, as it always has. Classification-only and
    read-only, like the rest: the
    returned copy is never what gets tokenized, so token text and
    spans stay exactly what the caller wrote.

    Vocabulary MATCHING composes NFC too, since #322
    (_lexicon._normalize folds every lookup and every stored entry the
    same way), so an NFD suffix word reaches its NFC entry. What stays
    raw is SEGMENTATION -- the surname site's direct membership test
    and the peel's tail slice index the token's own text -- where NFD
    degrades to no-split, never to a wrong split (decisions/W1,
    the 2026-07-29 ja amendment).
    """
    text = text.rstrip(FULL_STOPS)
    if not text or text.isascii():
        return None
    composed = unicodedata.normalize("NFC", text)
    if _VOICING_MARKS.isdisjoint(composed):
        return composed
    return _drop_kana_voicing_marks(composed)


def _classify(normalized: str) -> Script | None:
    """The FIRST _SCRIPT_MATCHERS entry covering all of `normalized`
    (already NFC, via _normalized_for_script), else None. Shared by
    both public classifiers so each of them normalizes exactly once.
    The East Asian scripts first, then CYRILLIC, asked only of a word
    that opens with a Cyrillic letter."""
    for script, matcher in _EAST_ASIAN_MATCHERS:
        if matcher(normalized):
            return script
    if (normalized[0] in _CYRILLIC_LETTERS
            and _SCRIPT_MATCHERS[Script.CYRILLIC](normalized)):
        return Script.CYRILLIC
    return None


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
    return _classify(normalized)


def effective_script(text: str) -> Script | None:
    """single_script, extended by the kana license (#272 amendment):
    a MIXED token wholly within Han∪hiragana∪katakana is Japanese --
    it necessarily contains kana (pure Han is not mixed), cannot be
    Chinese, and is not a foreign transcription (those are
    katakana-only: マイケル has no kanji, but さくらエミ -- hiragana
    plus katakana -- is kana-only AND licensed) -- and resolves to the
    HIRAGANA carrier entry. Pure-katakana stays KATAKANA
    (single_script's answer): a lone katakana token may be a
    transcribed foreign name or a Japanese reading, and the script
    cannot say which, so nothing defaults on it. Halfwidth kana is
    katakana by the table (#594), so 山田ﾀﾛｳ is licensed too. Last, a
    Cyrillic word with a hyphen or an apostrophe inside it is CYRILLIC
    (#1237), which only a declared Cyrillic order reads."""
    # None for both shapes _wholly_ja could never match anyway (empty
    # text, or all-ASCII text): real work, not a leftover "if text"
    # guard, since the ASCII case is one a bare emptiness check would
    # let through. The single normalized copy then serves both the
    # single-script answer and the license below.
    normalized = _normalized_for_script(text)
    if normalized is None:
        return None
    script = _classify(normalized)
    if script is not None:
        return script
    if _wholly_ja(normalized):
        return Script.HIRAGANA
    # a Cyrillic word with a hyphen or an apostrophe inside it (#1237);
    # translate is C-level, so a token with no joiner costs no frame
    joined = normalized.translate(_DROP_CYRILLIC_JOINERS)
    if (joined != normalized and normalized[0] in _CYRILLIC_LETTERS
            and normalized[-1] not in _CYRILLIC_JOINERS
            and _SCRIPT_MATCHERS[Script.CYRILLIC](joined)):
        return Script.CYRILLIC
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
    if found.issubset(_JA_SCRIPTS):
        return Script.HIRAGANA
    return None


# -- the reading a decision did not take (Ambiguity.alternative, #752
# phase 2m). Each report names it from what its own site knows: the
# word's tags say which reading the vocabulary or a shape gave it, and
# the emitter says which field (decisions/vocabulary-model, 2026-10-26)

#: Tags that say the vocabulary declares the word a name as well as a
#: word of another category: the derived markers (decisions/
#: vocabulary-model, 2026-10-25), and a given name written short. The
#: ambiguous class's tag is also written by SHAPE (rules/S9), which
#: `name_reading` reads off the shape tag beside it.
_DECLARED_NAME_TAGS = frozenset({
    AMBIGUOUS_ACRONYM_TAG, AMBIGUOUS_WORD_TAG, "vocab:particle-ambiguous",
    TITLE_AMBIGUOUS_TAG, GIVEN_ABBREVIATION_TAG})


def suffix_reading(token: WorkToken) -> PendingReading:
    """The suffix reading of a word a decision read as a name: a
    generation or agnomen by its listed word, a numeral by its shape
    unless listed, another listed suffix word by its vocabulary kind,
    and otherwise a credential, listed or shaped."""
    kind, source = suffix_kind(token.text, token.tags)
    return PendingReading(kind, source, Role.SUFFIX)


def suffix_kind(text: str,
                tags: Set[str]) -> tuple[ReadingKind, ReadingSource]:
    """`suffix_reading`'s kind and source, which assemble also asks of
    a word the parse read as a suffix (`Token.reading`), so the
    reading taken and the reading not taken are named by one
    predicate."""
    if AGNOMEN_TAG in tags:
        return ReadingKind.AGNOMEN, ReadingSource.VOCABULARY
    if CREDENTIAL_WORD_TAG in tags:
        return ReadingKind.CREDENTIAL, ReadingSource.VOCABULARY
    if AMBIGUOUS_WORD_TAG in tags or GENERATION_WORD_TAG in tags:
        return ReadingKind.GENERATION, ReadingSource.VOCABULARY
    if _ROMAN.match(text.rstrip(".")) is not None:
        listed = "vocab:suffix" in tags or "vocab:suffix-word" in tags
        return (ReadingKind.GENERATION,
                ReadingSource.VOCABULARY if listed else ReadingSource.SHAPE)
    if "vocab:suffix-word" in tags:
        return (ReadingKind.HONORIFIC if HONORIFIC_WORD_TAG in tags
                else ReadingKind.POST_NOMINAL), ReadingSource.VOCABULARY
    return (ReadingKind.CREDENTIAL,
            ReadingSource.SHAPE if SHAPE_ACRONYM_TAG in tags
            else ReadingSource.VOCABULARY)


def name_reading(token: WorkToken, role: Role | Deferred) -> PendingReading:
    """The name reading of a word a decision read as something else,
    landing in `role`: an initial where the word is one letter or
    initial-shaped, otherwise a name word, declared by the vocabulary
    where a derived marker says so and standing by position where
    nothing does."""
    text = token.text
    # C-level for an ASCII word, so a report pays no frame for the test
    if (len(text.rstrip(".")) == 1 or _INITIAL.fullmatch(text)
            if text.isascii()
            else composed_len(text.rstrip(".")) == 1
            or is_initial_shaped(text)):
        return PendingReading(ReadingKind.INITIAL, ReadingSource.SHAPE, role)
    return PendingReading(ReadingKind.NAME, name_source(token.tags), role)


def name_source(tags: Set[str]) -> ReadingSource:
    """Why a word reads as a name word: declared by the vocabulary
    where a derived marker says so, and by position where nothing
    does. `name_reading`'s source, which assemble also asks of a word
    the parse read as a name (`Token.reading`)."""
    # rules/O9: "the capitals settle the field" -- read by the word's
    # shape, the reading taken being the family its capitals named
    if CAPITALS_FAMILY_TAG in tags:
        return ReadingSource.SHAPE
    # classify writes the ambiguous class's tag on a word admitted by
    # its shape too, so the shape tag says no list declared it
    if (not tags.isdisjoint(_DECLARED_NAME_TAGS)
            and SHAPE_ACRONYM_TAG not in tags):
        return ReadingSource.DECLARED
    return ReadingSource.POSITION


#: The particle reading of a word read as a name: a particle joins the
#: words after it, the last group reading as the family (rules/P2).
PARTICLE_READING = PendingReading(ReadingKind.PARTICLE,
                                  ReadingSource.VOCABULARY, Role.FAMILY)
#: The same for a patronymic particle (rules/R9): its particle reading
#: is a patronymic, joining the parent's name after it.
PATRONYMIC_READING = PendingReading(ReadingKind.PATRONYMIC,
                                    ReadingSource.VOCABULARY, Role.FAMILY)


def particle_reading(tags: frozenset[str]) -> PendingReading:
    """The particle reading of a word read as something else, by the
    kind classify tagged it with: a patronymic particle's is
    `PATRONYMIC_READING`, any other's `PARTICLE_READING`."""
    return PATRONYMIC_READING if PATRONYMIC_TAG in tags else PARTICLE_READING


#: The title reading of a word read as a name.
TITLE_READING = PendingReading(ReadingKind.TITLE, ReadingSource.VOCABULARY,
                               Role.TITLE)
