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
import unicodedata
from collections.abc import Callable, Iterable, Sequence, Set
from typing import Literal

from nameparser._lexicon import (
    FULL_STOPS, Lexicon, _VOCAB_FIELDS, _normalize, _spells_an_initial,
)
from nameparser._policy import (CapsSuffixes, Policy, Script, _JA_SCRIPTS, _NO_INITIALS,
                                _SCRIPT_RANGES, _script_matcher)
from nameparser._pipeline._state import (
    AGNOMEN_TAG, AMBIGUOUS_ACRONYM_TAG, AMBIGUOUS_WORD_TAG, COMMA_CHARS,
    Deferred,
    GIVEN_ABBREVIATION_TAG, SHAPE_ACRONYM_TAG, TITLE_AMBIGUOUS_TAG,
    PendingReading, ReadingKind, ReadingSource, Role, WorkToken,
    comma_bucket,
)

# Ported verbatim from v1 (nameparser/config/regexes.py "initial") minus
# its empty-string alternative -- WorkToken text is never empty. Kept in
# sync by hand; layering forbids importing the config package here.
# "Verbatim" is a promise about the PATTERN, not about the predicate:
# since #320 is_initial is this SHAPE test ANDed with a repertoire test
# (in_initialless_script, below), so _INITIAL.fullmatch(text) and
# is_initial(text) are no longer the same question -- '씨.' answers yes
# to the first and no to the second. Call is_initial; the bare pattern
# is not the thing to ask. The narrowing lives in the predicate
# precisely so this copy can stay exactly as verbatim as it ever was
# -- REGEXES["initial"] is public v1 API and cannot narrow, and the
# only difference between the two remains the empty alternative noted
# above (config's `?`), which test_regex_sync splices back in.
_INITIAL = re.compile(r"^(\w\.|[A-Z])$")

# Ported verbatim from v1 (nameparser/config/regexes.py
# "period_not_at_end") -- layering forbids the config import; keep in
# sync by hand.
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

# The repertoire half of is_initial (_policy._NO_INITIALS), kept apart
# from _INITIAL's SHAPE half so the pattern itself stays v1-verbatim
# and its three copies stay pinned by tests/v2/test_regex_sync.py.
# contains-any, not whole=True: the shape half has already admitted the
# trailing period, so the text reaching here is '씨.' rather than '씨'
# and a wholly-of match would be False for every case this exists for.
# The second caller, is_title_shaped below, admits two or more
# characters, so contains-any there means one CJK character anywhere
# vetoes the whole word -- 'Kim김.' is refused as a title along with
# '田中.' -- and that is deliberate: a word carrying a script with no
# abbreviations is not wearing an abbreviation's period.
_has_initialless_char = _script_matcher(*_NO_INITIALS, whole=False)


def in_initialless_script(text: str) -> bool:
    """Whether TEXT holds a character of a script that writes no
    initials (#320), asked of the composed spelling: a decomposed
    hangul syllable is conjoining jamo, which no _NO_INITIALS range
    holds, so '씨.' typed decomposed escaped the veto every shape test
    beside it reads composed (#665). ASCII answers without the
    matcher's frame, as the callers' own `isascii()` gates do."""
    return (not text.isascii()
            and _has_initialless_char(unicodedata.normalize("NFC", text)))


# H2's own shape, text-level: an unlisted period-marked abbreviation,
# two or more letters, one trailing period. Moved here from _pieces
# (#289/#516, quality-review finding) so _vocab.name_word_count can
# ask the SAME question _pieces.is_leading_title asks -- measured
# divergence before the move: 'Dr. Smith, Ed' (LISTED title 'Dr.') and
# 'Xyz. Smith, Ed' (UNLISTED, H2-shaped) both read family 'Dr.
# Smith'/'Xyz. Smith', given 'Ed' at the peel (since #701 the listed
# 'Dr.' then peels into the title, rules/H6), because is_leading_title
# reads H2's shape and a bare `folded in lexicon.titles` lookup does
# not -- but name_word_count's OWN count disagreed: 'Xyz.' counted as
# a name word where 'Dr.' did not, so 'Xyz. Smith, Ed' alone flipped
# the comma structure to a credential run
# (mechanisms.md#ONE-PREDICATE-PER-QUESTION).
#
# The shape shared with config's "period_abbreviation" (layering
# forbids the config import; keep in sync by hand -- the pattern TEXT
# is what tests/v2/test_regex_sync.py compares, reaching this object
# through `_pieces._PERIOD_ABBREV`, an IMPORT of this one, not a second
# definition -- the sync test's target name did not move). It is
# composed from `_LETTER` below, so the text is v1's plus the marks.

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


# rules/H2: "an abbreviation opening the part of the name that
# carries the given name — the whole name, or the part after a
# family comma — reads as a title even when unlisted"
# (history: decisions/H2)
def is_title_shaped(text: str, lexicon: Lexicon) -> bool:
    """Whether TEXT reads as a title by H2's shape -- the LISTED half
    being a separate lookup at each caller's own site
    (is_title_piece/lexicon.titles), and the one vocabulary read here
    the given name written short, which outranks the shape (rules/H2,
    #789: 'Chas.' is no title). `name_word_count` and `title_readings`
    below are its callers; `_pieces.is_leading_title` asks the same question
    but keeps this body inline, its path being hot (every leading
    piece of every parse) where this one is cold (comma names only)
    -- the measured figure lives at that inline copy and is not
    restated here, two homes for one measurement being how they come
    to disagree. Touch one, touch both:
    `test_pieces.test_is_title_shaped_and_is_leading_title_agree`
    runs both over the union of the two example tables, so the
    agreement is checked rather than asserted in prose
    (mechanisms.md#ONE-PREDICATE-PER-QUESTION).

    The shape reads a Latin convention: a period marks an
    abbreviation. Scripts with no initials have no period
    abbreviations either (_policy._NO_INITIALS, the #320 veto
    is_initial carries), so a CJK word wearing a period is a name
    word, not a title -- a lone '田中.' is the family name (#323).
    `_PERIOD_ABBREV` stays ASCII-period only: a word wearing '。' never
    matches it, and the veto is what makes the ASCII spelling agree.
    ASCII text can carry no _NO_INITIALS character (every range sits
    above U+3000), so the C-level test declines before the regex
    search runs -- four frames per unlisted-abbreviation opener per
    parse, this running four times per piece.
    """
    return (bool(_PERIOD_ABBREV.match(text))
            and (text.isascii() or not in_initialless_script(text))
            and _normalize(text) not in lexicon.given_name_abbreviations)


def is_initial_shaped(text: str) -> bool:
    """v1's is_an_initial verbatim: the SHAPE half alone -- one word
    character plus a period, or a bare ASCII capital.

    Callers asking whether a token is STRUCTURALLY part of an initial
    run want this; callers asking whether it can really stand in for a
    name want is_initial (#320). The two answers differ only inside
    _NO_INITIALS scripts, where '씨.' is initial-SHAPED but is not an
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


# v1 regexes.py "roman_numeral", pinned by tests/v2/test_regex_sync.py.
_ROMAN = re.compile(r'^(X|IX|IV|V?I{0,3})$', re.I)
#: The same pattern, shared rather than copied: `_comma` filters on
#: it before asking `reads_as_generation` (rules/C12).
ROMAN = _ROMAN


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
    joined = " ".join(texts)
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
#: an acronym's capitals are the credential, a suffix word's lower
#: case is the suffix, and an agnomen's writing says nothing.
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
    also a name ("word", 'fils') leans the other way at one end: its
    lower case in a mixed-case name is the suffix ("credential", the
    suffix reading), its capitals say nothing (a surname is often
    written so), and Title case leans to the name as an acronym's
    does. An agnomen ("none", 'Neto') is written in the case of the
    name around it, so its writing never leans.
    """
    if one_case or cue == "none":
        return None
    if text.upper() == text.lower():     # caseless: no contrast to read
        return None
    if text.isupper():
        return "credential" if cue == "acronym" else None
    if text.islower():
        return "credential" if cue == "word" else None
    return "name"


def lexicon_cue(n: str, lexicon: Lexicon) -> Cue:
    """The `ambiguous_lean` cue of the folded member `n`, read off the
    lexicon by a caller that has no tags to read (`is_wholly_suffix`);
    `_pieces.listed_lean` reads the same answer off classify's tags."""
    if n in lexicon.suffix_words_ambiguous:
        return "none" if n in lexicon.agnomens else "word"
    return "acronym"


_DOTTED = re.compile(r"(?:" + _LETTER + r"\.)+")
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
    case -- v1's fix_phd, merged as an unambiguous suffix wherever it
    stands but the head of the string (decisions/phd-merge).

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
        return "suffix"
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
            or in_initialless_script(first + second)):
        return None
    fold = _normalize(a + b)
    if (fold in lexicon.suffix_acronyms_ambiguous
            or not (fold in lexicon.suffix_acronyms
                    or fold in lexicon.suffix_words)):
        return None
    na, nb = _normalize(a), _normalize(b)
    if ((na in lexicon.suffix_acronyms or na in lexicon.suffix_words)
            and (nb in lexicon.suffix_acronyms
                 or nb in lexicon.suffix_words)):
        return None
    # a particle or a connective joins name words, which is what it is
    # doing beside one ('DE A JUNIOR', the A a surname written short);
    # written with its period a letter is an initial, not the connective
    # it spells ('SAM E.', rules/T5)
    for written, n in ((first, na), (second, nb)):
        if not written.endswith(".") and (n in lexicon.particles
                                          or n in lexicon.conjunctions):
            return None
    return "split"


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
    if a in lexicon.suffix_acronyms_ambiguous and _dotted(text):
        return True
    if ((a in lexicon.suffix_acronyms
            and a not in lexicon.suffix_acronyms_ambiguous)
            or (n in lexicon.suffix_words
                and n not in lexicon.suffix_words_ambiguous)):
        return True
    # the joiners asked in C first, so a word holding neither pays no
    # frame
    return ("-" in n or "/" in n) and _joined_credential(text, lexicon)


#: What joins the chunks of a joined credential ('MD/PhD', 'MD-PhD').
_JOINERS = re.compile(r"[-/]")


# rules/S3: "a word whose chunks are joined by a hyphen or a slash
# reads as a suffix when every chunk counts as a suffix as written" --
# the stricter test, every chunk rather than any, because a hyphen also
# joins names (decisions/S3 (#752))
def _joined_credential(text: str, lexicon: Lexicon) -> bool:
    """Whether TEXT is two or more chunks joined by '-' or '/', each
    non-empty and each counting as a suffix as written: listed, and
    not a bare member of the ambiguous class, and not every one a
    single ASCII character, and -- joined by a hyphen -- not
    written as a hyphenated name is ('MD/PhD', 'M.A.-Ph.D.', 'PhD-Md',
    'md-phd', but not 'MA/PhD', 'Smith-Jones', 'I-V', 'Ae-Ra', 'Ae-ra'
    or 'MD/'). A chunk holds no joiner,
    so the recursion is one level deep. A loop rather than `all()` over
    a generator, which would cost a frame per chunk: a hyphenated name
    ('Smith-Jones') stops at its first chunk."""
    # the caller found a joiner, so there are two chunks at least
    chunks = _JOINERS.split(text)
    whole = False  # a chunk that is not a single ASCII character
    # every chunk so far written as a name's; a slash joins no name, so
    # a word holding one takes no cue
    named = "/" not in text
    for k, c in enumerate(chunks):
        if not (c and suffix_as_written(_normalize(c), c, lexicon)):
            return False
        # its periods are not the chunk's ('I.' is 'i'), as in a word
        # split at its periods
        bare = c.replace(".", "")
        whole = whole or len(bare) > 1 or not bare.isascii()
        # the first chunk in Title case, a later one in Title case or
        # lower case ('Ae-Ra', 'Ae-ra')
        named = named and (
            len(bare) > 1 and bare[0].isupper() and bare[1:].islower()
            or k > 0 and bare.islower())
    # rules/S3: "Every chunk the vocabulary matches is a single ASCII
    # character" -- the numerals and the digit, which are about
    # generations, make no joined word a suffix either ('Jack I-V');
    # rules/S3: "a word joined by a hyphen and written the way a
    # hyphenated name is, its first chunk in Title case and every other
    # in Title case or lower case, is a name word" -- where a
    # credential's chunks are not (decisions/S3 (#752))
    return whole and not named


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
            n.replace(".", "") in lexicon.suffix_acronyms_ambiguous
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
    return (n in lexicon.suffix_words
            and n not in lexicon.suffix_words_ambiguous) \
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
# any of its period-separated chunks is suffix vocabulary" --
# "every chunk the vocabulary matches is a single ASCII character,
# the roman numerals and the lone digit the vocabulary lists, which
# are about generations rather than credentials". The chunk rule and
# its single-character exception (decisions/S3).
def period_joined_vocab(
        text: str, lexicon: Lexicon,
) -> Literal["title", "suffix", "shape"] | None:
    """v1's parse_pieces derivation for interior-period tokens
    ('Lt.Gov.', 'Msc.Ed.', and by the ANY rule 'Mr.Smith'): ANY title
    chunk makes the token a title (checked first, v1's continue); else
    ANY suffix chunk makes it a suffix. Chunk-level suffix membership
    is v1's is_suffix: bare ambiguous acronyms COUNT ('Msc.Ed.'
    derives via 'ed') -- the ambiguous period-gate applies to whole
    tokens only -- while a suffix word that is also a name does not
    ('M.Filho', rules/S11). Returns "title", "suffix", "shape", or None.

    "shape" is the third verdict and it is the absence of a claim
    worth acting on (#516): two or more chunks, EVERY one of them
    alphabetic, and nothing the vocabulary matches except -- possibly
    -- chunks that are a SINGLE ASCII CHARACTER. That exception is the
    roman-numeral accident retired narrowly: measured 2026-09-15 the
    one-character suffix vocabulary is {'2', 'i', 'v'} plus the glued
    CJK honorific tails, so 'John Smith R.A.I.' was reading as a
    generational suffix off the chunk 'i'. CHARACTER rather than
    LETTER because '2' is a digit and is in the set; ASCII because
    '씨' is the single character that must KEEP its claim ('J.씨'). A
    multi-character match still reads as it always did, so 'Msc.Ed.',
    'JD.CPA' and 'Lt.Gov.' are untouched -- the WIDE retirement, where
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

    The INITIALLESS-SCRIPT guard is a second, independent narrowing of
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
    chunks = [_normalize(c) for c in text.split(".") if c]
    if any(c in lexicon.titles for c in chunks):
        return "title"
    # rules/S11: "the word is part of that one word and is weighed only
    # by the shape the joined word wears" -- no chunk claim for a
    # suffix word that is also a name ('M.Filho')
    matched = [c for c in chunks
               if c in lexicon.suffix_acronyms
               or (c in lexicon.suffix_words
                   and c not in lexicon.suffix_words_ambiguous)]
    if matched and not all(len(c) == 1 and c.isascii() for c in matched):
        return "suffix"
    if (len(chunks) >= 2 and all(c.isalpha() for c in chunks)
            and (text.isascii() or not in_initialless_script(text))):
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
    return (n in lexicon.suffix_acronyms_ambiguous
            or n in lexicon.suffix_words_ambiguous)


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
    `Lexicon.default().add(surnames={"dupont"})` still read
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


def composed_len(text: str) -> int:
    """The length of TEXT in letters as the writer sees them: code
    points once NFC-composed. A caps word admitted decomposed (#652)
    is longer than its composed twin, and the two-letter pair test
    (`John Smith, MÁ`) counts letters."""
    return len(text if text.isascii() else unicodedata.normalize("NFC", text))


def in_any_wordlist(n: str, lexicon: Lexicon) -> bool:
    """Whether the folded word `n` is in ANY of the lexicon's wordlists
    (`_lexicon._VOCAB_FIELDS`, the whole roster but two): the caps
    shape's "unlisted" (`caps_shape_candidate`), where a word a caller
    listed even as a SURNAME must never become a credential.

    The three left out: `title_phrases`, whose entries are two words and
    so never one; `titles_ambiguous`, a title that may be a given
    name, which outside a title phrase is read as the unlisted word it
    is there (rules/H9: "and elsewhere a name word") -- a phrase is two
    words and a comma part read by this shape is one; and
    `given_name_abbreviations`, a given name written short (#789),
    whose one reader is H2's shape, so anywhere else its word reads as
    the unlisted word it is ('John Smith, JAS' keeps suffix 'JAS')."""
    for field in _LISTED_FIELDS:
        if n in getattr(lexicon, field):
            return True
    return False


_LISTED_FIELDS = tuple(f for f in _VOCAB_FIELDS
                       if f not in ("title_phrases", "titles_ambiguous",
                                    "given_name_abbreviations"))


#: The wordlists that claim a word as something OTHER than name text.
#: `surnames` and `bound_given_names` are left out: they say a word IS
#: a name word ('Kim', 'Abdul'), the opposite claim; and so is
#: `titles_ambiguous`, a title that may be a given name (rules/H9), with
#: `title_phrases`, whose two-word entries never match one word; and so
#: is `given_name_abbreviations`, a given name written short (#789), left
#: out of `_LISTED_FIELDS` above.
_NON_NAME_FIELDS = tuple(f for f in _LISTED_FIELDS
                         if f not in ("surnames", "bound_given_names"))


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
    for field in _NON_NAME_FIELDS:
        if n in getattr(lexicon, field):
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
        return (n not in lexicon.suffix_acronyms_ambiguous
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
#: particle starts a surname unit, and a suffix word stops it. A word
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
        "." in text and n not in lexicon.titles
        and period_joined_vocab(text, lexicon) == "suffix")
    particle = n in lexicon.particles and not (
        (leading and n in lexicon.titles) or _spells_an_initial(n, text))
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


# rules/H9: "a word no listed phrase holds is a title only behind a
# style or a modifier, or before `of`" -- whether the word heads a title
# of itself, asked of the phrases `attaches` compiled rather than of a
# property of its own
def in_a_title_phrase(text: str, lexicon: Lexicon) -> bool:
    """Whether a phrase of `lexicon.title_phrases` that classify can
    read holds `text`."""
    return _normalize(text) in _phrase_words(
        lexicon.title_phrases, lexicon.titles, lexicon.titles_ambiguous)


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
    before it; or 'of', or a title it stands in front of in
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
    or in the object of 'of' or 'the' there (decision 10 of
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
    contested = lexicon.titles_ambiguous
    modifiers = lexicon.title_modifiers
    titles = lexicon.titles
    # a word in titles is a title wherever it stands, whatever else it
    # is listed as; one of titles_ambiguous alone is listed as a title
    # to its neighbours and read by its phrase
    reading = [n in titles or n in contested for n in folded]
    if titled is not None:
        reading = [r or t for r, t in zip(reading, titled)]
    listed = list(reading)
    phrases = lexicon.title_phrases
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
             and (prev in modifiers or prev in lexicon.title_styles
                  or f"{prev} {n}" in phrases))
            or (nxt is not None
                and ((nxt in _PHRASE_LINKS and nxt in lexicon.conjunctions)
                     or (listed[i + 1] and f"{n} {nxt}" in phrases))))
    # left to right, whether the run so far has passed 'of' or 'the': a
    # modifier after it is in the object of a phrase ('President of the
    # United States', 'the Queen's Bench'), which no head need follow. A
    # coordinating connective opens no object: 'Mr. and Mrs. Wing Lau'
    # is two salutations and a given name
    linked = [False] * len(folded)
    conjunctions = lexicon.conjunctions
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
                and folded[i + 1] in conjunctions)
            behind = reading[i]
        elif reading[i] or (head and is_title_shaped(texts[i], lexicon)):
            behind = True
        elif n not in conjunctions:
            behind = False
    return reading


def name_word_count(texts: Sequence[str], lexicon: Lexicon,
                    policy: Policy, letters_one_case: bool | None = None,
                    ) -> int:
    """How many of these texts are NAME words -- not suffix
    vocabulary, not title vocabulary.

    rules/C4's count for the ambiguous class, and it is of names
    rather than of words because 'Smith Jr., MA' is two tokens and one
    name: counting tokens there flips the structure and hands the
    family to `given`, which no reading of that string wants
    (decisions/S6). The suffix half asks the POLICY-selected
    predicate, the same one is_wholly_suffix asks, so the two agree
    about what a suffix word is; the title half asks BOTH the listed
    lookup and H2's shape test (`is_title_shaped`) -- a bare
    `lexicon.titles` lookup here read 'Xyz.' as a name word where the
    leading peel reads it as a title, and that divergence is recorded
    once, at `is_title_shaped` itself
    (mechanisms.md#ONE-PREDICATE-PER-QUESTION).

    It counts UNITS holding a name word, not tokens (#575,
    mechanisms.md#UNIT-PARTITION): a particle chain (P2) builds one
    family name, so 'De La Cruz' is one name word and 'De La Cruz, Ed'
    reads as 'Royce, Ed' does. Why the other two joins are not read
    here: `SURNAME_UNIT_TAGS`.

    `letters_one_case` is `is_wholly_suffix`'s, for the same reason.
    """
    lenient = policy.lenient_comma_suffixes

    # One pass: each token's name-word verdict, and whether any token
    # is a particle. With none, every token is a unit of its own and
    # the count is a sum, so the commonest comma names never build the
    # units -- and pay no frame the token loop did not already pay.
    names: list[bool] = []
    has_particle = False
    # map, not a comprehension, which is a frame of its own on 3.11
    folded = list(map(_normalize, texts))
    # rules/H9: "the word is a title only inside a title phrase" -- the
    # part before the comma is the head of the name, read as classify
    # reads it
    titled = (None if lexicon.titles_ambiguous.isdisjoint(folded)
              and lexicon.title_modifiers.isdisjoint(folded)
              else title_readings(texts, folded, lexicon, head=True))
    for i, n in enumerate(folded):
        text = texts[i]
        title = n in lexicon.titles if titled is None else titled[i]
        if n in lexicon.particles:
            has_particle = True
        suffix = (is_suffix_lenient(text, lexicon) if lenient
                  else is_suffix_strict(text, lexicon, letters_one_case))
        names.append(not (suffix or title or is_title_shaped(text, lexicon)))
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
    alone). The scripts this classifies -- every _SCRIPT_RANGES entry,
    which today coincide with _policy._NO_INITIALS (#320), a
    coincidence _policy says a new member must not inherit -- have no
    initials and no period abbreviations, so a stop on such a token
    carries no information about the word; ASCII text is stripped too,
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
    can hand a pure-katakana token the kana license by accident; NFD
    also decomposes Hangul syllables onto bare jamo (U+1100-U+11FF),
    entirely outside the HANGUL range, so raw NFD Korean input misses
    the shipped family-first order rule rather than merely misfiring.
    Normalizing first fixes both.

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
    both public classifiers so each of them normalizes exactly once."""
    for script, matcher in _SCRIPT_MATCHERS.items():
        if matcher(normalized):
            return script
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
    katakana by the table (#594), so 山田ﾀﾛｳ is licensed too."""
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
    unless listed, another listed post-nominal word as a suffix, and
    otherwise a credential, listed or shaped."""
    tags = token.tags
    if AGNOMEN_TAG in tags:
        return PendingReading(ReadingKind.AGNOMEN, ReadingSource.VOCABULARY,
                              Role.SUFFIX)
    if AMBIGUOUS_WORD_TAG in tags:
        return PendingReading(ReadingKind.GENERATION,
                              ReadingSource.VOCABULARY, Role.SUFFIX)
    if _ROMAN.match(token.text.rstrip(".")) is not None:
        listed = "vocab:suffix" in tags or "vocab:suffix-word" in tags
        return PendingReading(
            ReadingKind.GENERATION,
            ReadingSource.VOCABULARY if listed else ReadingSource.SHAPE,
            Role.SUFFIX)
    if "vocab:suffix-word" in tags:
        return PendingReading(ReadingKind.POST_NOMINAL, ReadingSource.VOCABULARY,
                              Role.SUFFIX)
    return PendingReading(
        ReadingKind.CREDENTIAL,
        ReadingSource.SHAPE if SHAPE_ACRONYM_TAG in tags
        else ReadingSource.VOCABULARY,
        Role.SUFFIX)


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
    # classify writes the ambiguous class's tag on a word admitted by
    # its shape too, so the shape tag says no list declared it
    declared = (not token.tags.isdisjoint(_DECLARED_NAME_TAGS)
                and SHAPE_ACRONYM_TAG not in token.tags)
    return PendingReading(
        ReadingKind.NAME,
        ReadingSource.DECLARED if declared else ReadingSource.POSITION,
        role)


#: The particle reading of a word read as a name: a particle joins the
#: words after it, the last group reading as the family (rules/P2).
PARTICLE_READING = PendingReading(ReadingKind.PARTICLE,
                                  ReadingSource.VOCABULARY, Role.FAMILY)
#: The title reading of a word read as a name.
TITLE_READING = PendingReading(ReadingKind.TITLE, ReadingSource.VOCABULARY,
                               Role.TITLE)
