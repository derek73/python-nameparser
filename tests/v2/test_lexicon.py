import copy
import dataclasses
import pickle
import re
import subprocess
import sys
import unicodedata
import warnings
from collections.abc import Callable
from pathlib import Path
from types import MappingProxyType

import pytest

from tests.checkout import HAS_DOCS, needs_docs

from nameparser import Locale, LexiconReading, Parser, locales, parser_for
from nameparser._lexicon import (
    Lexicon, _ADDED_IN, _KIND_FIELDS, _LIST_FIELDS, _MaskValueError,
    _LAYOUT_3_0_LOADED, _SET_FIELDS, _VOCAB_FIELDS, _default_lexicon,
    _fields_of, _normalize, _title_key,
)
from nameparser._policy import _HANGUL_SYLLABLES
from nameparser.config._compiled import SUFFIX_ACRONYMS, SUFFIX_WORDS


def _quiet(lexicon: Callable[[], Lexicon]) -> Lexicon:
    """A lexicon built where the title warning would fire, the warning
    being no part of what the test asks."""
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", UserWarning)
        return lexicon()


# -- construction and normalization ----------------------------------------

def test_words_are_normalized_as_they_are_stored() -> None:
    lex = Lexicon.empty().add("Dr.", "MR", kind="title")
    assert lex._sets.titles == frozenset({"dr", "mr"})
    assert [r.text for r in lex.readings_of("DR.")] == ["dr"]


def test_default_sources_v1_vocabulary() -> None:
    sets = Lexicon.default()._sets
    assert "dr" in sets.titles
    assert "van" in sets.particles
    assert "phd" in sets.suffix_acronyms
    # flipped model: 'dos' is never-given in v1, so NOT ambiguous here
    assert "dos" in sets.particles and "dos" not in sets.particles_ambiguous
    assert "van" in sets.particles_ambiguous
    # the policy is 'e' and not 'y' (decisions/P8): a bare E initial is
    # common, where 'y' between two surnames is the commonest Hispanic compound
    assert "e" in sets.conjunctions_ambiguous
    assert "y" not in sets.conjunctions_ambiguous
    # CAPITALIZATION_EXCEPTIONS maps 'phd' -> 'PhD', a case mask since
    # #459 (verbatim, not normalized -- only keys are lowercased and
    # period-stripped at construction; values pass through unchanged).
    assert Lexicon.default().capitalization_exceptions_map["phd"] == "PhD"
    # maiden markers source from the same data-module pattern (#274),
    # both ё/е spellings listed because case normalization does not
    # fold them
    assert "geborene" in sets.maiden_markers
    assert {"урожденная", "урождённая"} <= sets.maiden_markers
    # #269 fidelity: entries whose spelling casefold() would mutate must
    # arrive exactly as authored (final sigma intact, ß intact)
    assert "κος" in sets.titles and "κοσ" not in sets.titles
    assert "großfürst" in sets.titles and "grossfürst" not in sets.titles


def test_default_is_cached_single_instance() -> None:
    assert Lexicon.default() is Lexicon.default()



def test_capitalization_exceptions_canonical_and_no_aliasing() -> None:
    exceptions = {"phd": "PhD", "ii": "II"}
    lex = Lexicon.empty()
    lex2 = dataclasses.replace(lex, capitalization_exceptions=exceptions)  # type: ignore[arg-type]
    exceptions["iii"] = "III"  # mutate caller's dict afterwards
    assert "iii" not in lex2.capitalization_exceptions_map
    # canonical: insertion order does not affect equality/hash
    lex3 = dataclasses.replace(lex, capitalization_exceptions=(("ii", "II"), ("phd", "PhD")))
    assert lex2 == lex3 and hash(lex2) == hash(lex3)




def test_capitalization_exceptions_rejects_non_iterable() -> None:
    with pytest.raises(TypeError, match="capitalization_exceptions"):
        Lexicon(capitalization_exceptions=5)  # type: ignore[arg-type]



def test_colliding_exception_keys_dedupe_last_wins() -> None:
    # 'Phd.' and 'phd' collide under edge-period normalization
    lex = Lexicon(capitalization_exceptions=(("Phd.", "PHD"),
                                             ("phd", "PhD")))
    assert lex.capitalization_exceptions == (("phd", "PhD"),)
    rebuilt = Lexicon(capitalization_exceptions=lex.capitalization_exceptions_map)  # type: ignore[arg-type]
    assert rebuilt == lex and hash(rebuilt) == hash(lex)


def test_lexicon_rejects_non_str_exception_values() -> None:
    with pytest.raises(TypeError, match="str -> str"):
        Lexicon(capitalization_exceptions={"phd": 42})  # type: ignore[dict-item, arg-type]


def _unpickled_with(value: object) -> Lexicon:
    state = Lexicon.default().__getstate__()
    state["capitalization_exceptions"] = value
    restored = Lexicon.__new__(Lexicon)
    restored.__setstate__(state)
    return restored


# Every entry point that builds the pair field, because a check on one
# member of a family belongs on all of it (AGENTS.md): construction,
# replace(), the right-biased union, and unpickling.
_MASK_ENTRY_POINTS: list[Callable[[object], object]] = [
    lambda v: Lexicon(capitalization_exceptions=v),  # type: ignore[arg-type]
    lambda v: dataclasses.replace(Lexicon.default(),
                                  capitalization_exceptions=v),  # type: ignore[arg-type]
    lambda v: Lexicon.default() | Lexicon(capitalization_exceptions=v),  # type: ignore[arg-type]
    _unpickled_with,
]


@pytest.mark.parametrize("build", _MASK_ENTRY_POINTS)
@pytest.mark.parametrize("key, value", [
    ("jr", "Junior"), ("phd", "PhDs"), ("phd", ""), ("md", "MB"),
    ("phd", "D.Ph."), ("2nd", "3ND"),
])
def test_an_exception_value_that_does_not_spell_its_key_raises(
        build: Callable[[object], object], key: str, value: str) -> None:
    """#459: a capitalization_exceptions value is a case MASK, the
    key's own letters recased. Case repair lays it over the word as
    written, so a value spelling anything else -- a replacement
    ('Junior'), a letter too many or too few, the right letters in
    the wrong order, a DIGIT changed ('2nd' -> '3ND') -- has no
    reading, and raises where it is built."""
    with pytest.raises(ValueError,
                       match="does not spell the key's letters") as caught:
        build(((key, value),))
    assert repr(key) in str(caught.value)
    assert repr(value) in str(caught.value)


def test_a_mask_may_recase_a_digit_key_unchanged() -> None:
    """#459 review: the mask compares ALPHANUMERICS (_lexicon._alnum),
    not letters alone, so a digit is part of what a value must spell
    -- '2nd' accepts '2ND' ('2' unchanged, letters recased) and
    rejects '3ND' above."""
    lex = Lexicon(capitalization_exceptions=(("2nd", "2ND"),))
    assert lex.capitalization_exceptions_map["2nd"] == "2ND"


def test_a_decomposed_value_is_compared_and_stored_nfc_composed() -> None:
    """A decomposed value is accepted against a composed key, the
    check folding both sides through _normalize, and is STORED
    composed, so both spellings of one value construct alike
    (test_render's decomposed-mask test shows why that matters)."""
    composed = unicodedata.normalize("NFC", "CAFÉ")
    decomposed = unicodedata.normalize("NFD", "CAFÉ")
    assert decomposed != composed  # the draw actually decomposed something
    lex = Lexicon(capitalization_exceptions=(("café", decomposed),))
    assert lex.capitalization_exceptions_map["café"] == composed


@pytest.mark.parametrize("key, value", [
    ("phd", "Ph.D."), ("md", "M.D."), ("hc", "h.c"), ("ph.d", "PhD"),
    ("phd", "P.H.D."), ("md", "M. D."), ("dphil", "DPhil"),
])
def test_a_value_may_carry_punctuation_that_marks_its_joins(
        key: str, value: str) -> None:
    """#459 review: a value's punctuation is not ignored -- it marks
    which of the key's letters are JOINED (one run) versus split, and
    _apply_mask's initial rule reads that structure -- but it is never
    WRITTEN into the word. Every one of these is warning-free at
    construction, where a construction diagnostic could be raised."""
    with warnings.catch_warnings():
        warnings.simplefilter("error")
        lex = Lexicon(capitalization_exceptions=((key, value),))
    assert tuple(lex.capitalization_exceptions_map.values()) == (value,)


def test_the_mask_error_offers_a_spelling_that_works_and_type_checks(
) -> None:
    """The message hands the reader code to paste, so the code has to
    run and to type-check. The field is annotated with what it STORES,
    a tuple of pairs, so a dict literal there is an arg-type error --
    AGENTS.md's rule for actionable messages. The offered spelling is
    the offending KEY recased upper, not a fixed example, so the two
    constructions below use the spelling the 'jr' key's own error
    offers, verbatim; mypy checks this file."""
    offered = "capitalization_exceptions=(('jr', 'JR'),)"
    with pytest.raises(ValueError) as caught:
        Lexicon(capitalization_exceptions=(("jr", "Junior"),))
    assert offered in str(caught.value)
    assert Lexicon(capitalization_exceptions=(('jr', 'JR'),)) \
        .capitalization_exceptions_map == {"jr": "JR"}


def test_the_mask_error_falls_back_when_upper_would_not_itself_validate(
) -> None:
    """#459 review: .upper() can change a letter's COUNT --
    'straße'.upper() is 'STRASSE', ß growing to two letters -- so
    offering it verbatim would raise if pasted. The offer falls back
    to the key unchanged (an identity mask, always legal) whenever
    upper() would not itself spell the key's own letters."""
    with pytest.raises(ValueError) as caught:
        Lexicon(capitalization_exceptions=(("straße", "STRASSE"),))
    offered = "capitalization_exceptions=(('straße', 'straße'),)"
    assert offered in str(caught.value)
    # pasted, the offered spelling constructs
    assert Lexicon(capitalization_exceptions=(('straße', 'straße'),)) \
        .capitalization_exceptions_map == {"straße": "straße"}


def test_the_mask_error_echoes_the_callers_own_spelling_not_the_composed_one(
) -> None:
    """#459 review: the value used to be captured AFTER NFC
    normalization, so the message (and _MaskValueError.value) showed
    the composed spelling even when the caller wrote a decomposed one.
    A decomposed 'e' + a combining acute and its NFC-composed 'é' look
    identical printed, but are different str objects -- repr() shows
    it (different escaping), and here it also changes len()."""
    decomposed = "PhéD"  # 'PhéD', 'e' + U+0301 COMBINING ACUTE
    composed = unicodedata.normalize("NFC", decomposed)
    assert repr(decomposed) != repr(composed)
    with pytest.raises(_MaskValueError) as caught:
        Lexicon(capitalization_exceptions=(("phed", decomposed),))
    assert caught.value.value == decomposed
    assert repr(decomposed) in str(caught.value)
    assert repr(composed) not in str(caught.value)


def test_mask_value_error_survives_pickle_and_copy() -> None:
    """The inherited __reduce__ would re-call __init__ with self.args,
    the message alone, and __init__ needs `key`, `normalized_key` and
    `value` too -- so without the override a ProcessPoolExecutor
    worker raising it would surface as BrokenProcessPool rather than
    this ValueError."""
    try:
        Lexicon(capitalization_exceptions=(("jr", "Junior"),))
    except _MaskValueError as caught:
        original = caught
    else:
        raise AssertionError("expected _MaskValueError")
    original.add_note("seen in worker 3")
    for restored in (pickle.loads(pickle.dumps(original)),
                     copy.copy(original)):
        assert isinstance(restored, ValueError)
        assert isinstance(restored, _MaskValueError)
        assert restored.key == original.key == "jr"
        assert restored.offered == original.offered
        assert str(restored) == str(original)
        # __reduce__'s third element (self.__dict__) is what carries a
        # note added after construction -- reconstructing from the
        # three __init__ fields alone would drop it.
        assert restored.__notes__ == ["seen in worker 3"]



def test_capitalization_exceptions_rejects_malformed_shapes() -> None:
    with pytest.raises(TypeError, match="bare string"):
        Lexicon(capitalization_exceptions="ab")  # type: ignore[arg-type]
    with pytest.raises(TypeError, match="pairs"):
        Lexicon(capitalization_exceptions=(("a", "b", "c"),))  # type: ignore[arg-type]
    with pytest.raises(TypeError, match="pairs"):
        # a 2-char string entry would unpack into two chars and silently
        # store {"a": "b"} -- reject str entries outright
        Lexicon(capitalization_exceptions=("ab",))  # type: ignore[arg-type]



def test_multiword_capitalization_key_warns() -> None:
    with pytest.warns(UserWarning, match="matched one word at a time"):
        dataclasses.replace(
            Lexicon.empty(),
            capitalization_exceptions=(("zqx zqy", "ZqXZqY"),))


def test_a_multiword_key_skips_the_mask_check_entirely() -> None:
    """#459 review: the mask check ran before the multi-word-key
    warning, so a key that can never match -- 'ph d' has no word in
    capitalized()'s per-word lookup -- still raised over a value that
    does not spell it (AGENTS.md: an invariant guards harm, and an
    unreachable entry does none). Reordered so a multi-word key only
    warns, storing its value verbatim regardless of the mask
    question."""
    with pytest.warns(UserWarning, match="matched one word at a time"):
        lex = dataclasses.replace(
            Lexicon.empty(),
            capitalization_exceptions=(("ph d", "Doctor"),))
    assert lex.capitalization_exceptions_map == {"ph d": "Doctor"}



def test_default_lexicon_builds_warning_free() -> None:
    # Would have caught the eight dead entries the previous commit
    # repaired.
    _default_lexicon.cache_clear()
    try:
        with warnings.catch_warnings():
            warnings.simplefilter("error")
            Lexicon.default()
    finally:
        _default_lexicon.cache_clear()


def test_default_lexicon_ships_korean_surnames_only() -> None:
    lex = Lexicon.default()
    assert "김" in lex.surnames and "남궁" in lex.surnames
    # Han surnames are locales.ZH's cargo (segmentation opt-in), so
    # the DEFAULT set is wholly hangul -- structural check, not
    # content-pinning. The span comes from the shared table rather than
    # a hand-copy, and is the syllables alone: HANGUL holds the
    # conjoining jamo too since #1087, and a surname written in jamo
    # would match no composed name.
    lo, hi = _HANGUL_SYLLABLES
    assert all(all(lo <= ord(c) <= hi for c in s)
               and 1 <= len(s) <= 2 for s in lex.surnames)



@pytest.mark.parametrize("entry", ["lt .", "lt . col", ". col", ". ."])
def test_given_name_titles_fold_is_a_fixed_point(entry: str) -> None:
    # Storage re-runs the fold on unpickle and on every
    # dataclasses.replace, so a value that changes under a second pass
    # is one Lexicon later rejects as "not written by this version".
    once = _title_key(entry.split())
    assert _title_key(once.split()) == once
    assert once == once.strip() and "  " not in once


@pytest.mark.parametrize("word", [
    "dr.", " Dr. ", ". a .", ".  .", "..x..", "  .b.  ",
    # the three non-ASCII full stops (#322), alone and mixed with
    # the ASCII one, and around whitespace like the rows above
    "씨．", "씨。", "씨｡", "．씨。", " 。씨 ", "。 씨 .",
    # NFD input: the fold composes, and composing twice is a no-op
    unicodedata.normalize("NFD", "씨."),
    unicodedata.normalize("NFD", "Müller."),
    # a case-mapping that produces a combining mark: lower() then NFC
    # has to land somewhere a second pass leaves alone
    "İ.",
])
def test_normalize_reaches_a_fixed_point(word: str) -> None:
    # strip() then strip(".") leaves periods-around-whitespace half
    # done: '. a .' -> ' a ' -> 'a'. Anything that stores a normalized
    # value and later re-normalizes it (unpickling, a second add) then
    # sees the value change under it, so the fold has to converge.
    once = _normalize(word)
    assert _normalize(once) == once


def test_normalize_folds_every_full_stop_and_composes_nfd() -> None:
    # #322: the vocabulary is stored NFC with edge stops removed, so a
    # lookup written with a fullwidth or ideographic stop, or in NFD,
    # has to fold to the same key. Edge stops only: 'J.R.' keeps its
    # interior period exactly as before.
    assert _normalize("씨．") == "씨"
    assert _normalize("씨。") == "씨"
    assert _normalize("씨｡") == "씨"
    # the fold is script-agnostic, so the reach is not CJK-only: a
    # LATIN word wearing an ideographic stop folds to its entry too,
    # and 'Dr。' consequently reads as a title where before it read as
    # a name word. Pinned here because it is the shape the tests
    # elsewhere in this bundle deliberately leave in ASCII.
    assert _normalize("Dr。") == "dr"
    assert _normalize(unicodedata.normalize("NFD", "씨.")) == "씨"
    assert _normalize("J.R.") == "j.r"
    assert _normalize("김.민준") == "김.민준"
    # an INTERIOR ideographic stop survives too: the fold composes NFC,
    # which leaves U+3002 exactly where it is, so this pins the
    # interior survival the ASCII row above pins for '.'
    assert _normalize("김。민준") == "김。민준"
    # NFC, NOT NFKC, and this is the row that separates them. NFKC
    # folds every fullwidth character to its ASCII compatibility form,
    # so it would give 'm.b.a' here -- whose period-free form is 'mba',
    # a shipped suffix acronym (_vocab.suffix_as_written strips
    # periods for the acronym test alone). Folding widths at the
    # lookup would therefore make a fullwidth-written credential match
    # the ASCII vocabulary, which is a decision this bundle did not
    # take: the stop set was widened, the letters were not.
    assert _normalize("Ｍ．Ｂ．Ａ．") == "ｍ．ｂ．ａ"



def test_normalization_preserves_spellings_casefold_would_mutate() -> None:
    # lower(), not casefold(): casefold's caseless-matching folds would
    # rewrite stored vocabulary -- Greek final sigma flattens ('κος' ->
    # the misspelling 'κοσ') and German ß expands ('großfürst' ->
    # 'grossfürst'). lower() follows Unicode SpecialCasing contextually
    # ('ΚΟΣ' -> 'κος') and keeps entries as authored, matching v1's lc().
    lex = Lexicon.empty().add("ΚΟΣ", "Großfürst", "Ph.D", kind="title")
    # and an interior period survives: 'J.R.' must not collapse to 'jr'
    assert lex._sets.titles == frozenset({"κος", "großfürst", "ph.d"})


def test_a_word_that_normalizes_to_empty_raises() -> None:
    # "." or "" is a data bug (a stray split, an empty CSV cell), for a
    # word as for a mask key
    for word in (" ", ".", "。", ". ."):
        with pytest.raises(ValueError, match="normalizes to empty"):
            Lexicon.empty().add(word, kind="title")
    with pytest.raises(ValueError, match="normalizes to empty"):
        Lexicon(capitalization_exceptions=(("...", "X"), ("phd", "PhD")))


@pytest.mark.parametrize("word", [42, {"dr"}, ["dr"], None])
def test_each_word_is_its_own_string_argument(word: object) -> None:
    # a collection passed as one word is the 2.x habit (`titles={"dr"}`
    # moved to the front); the message says to unpack it
    with pytest.raises(TypeError, match=r"unpack a collection: add\(\*words"):
        Lexicon.empty().add(word, kind="title")  # type: ignore[arg-type]


@pytest.mark.parametrize("value", [b"dr", bytearray(b"dr"), memoryview(b"dr")])
@pytest.mark.parametrize("build", [
    lambda v: Lexicon.empty().add(v, kind="title"),
    lambda v: Lexicon.empty().remove(v),
    lambda v: Lexicon.default().readings_of(v),
    lambda v: Lexicon(surnames=v),
    lambda v: Lexicon(capitalization_exceptions=v),
])
def test_every_lexicon_entry_point_rejects_a_buffer_with_a_decode_hint(
        build: Callable[[object], object], value: object) -> None:
    # Binary sequences iterate to INTS, so the generic entry check
    # reported "entries must be strings, got 100" -- the byte value of
    # 'd', naming neither the cause nor the fix. v1 shipped a decode
    # hint for exactly this (#238). Every entry point, a guard on one
    # member of a family belonging on all of it (AGENTS.md).
    with pytest.raises(TypeError, match="decode"):
        build(value)


@pytest.mark.parametrize("field", _LIST_FIELDS)
def test_a_list_rejects_a_bare_string_a_mapping_and_a_non_string(
        field: str) -> None:
    with pytest.raises(TypeError, match="bare string"):
        Lexicon(**{field: "kim"})  # type: ignore[arg-type]
    with pytest.raises(TypeError, match="mapping"):
        Lexicon(**{field: {"kim": "x"}})  # type: ignore[arg-type]
    with pytest.raises(TypeError, match="entries must be strings"):
        Lexicon(**{field: {"kim", 42}})  # type: ignore[arg-type]
    with pytest.raises(TypeError, match=f"{field}.*iterable"):
        Lexicon(**{field: 5})  # type: ignore[arg-type]


@pytest.mark.parametrize("field", _LIST_FIELDS)
def test_a_multi_word_list_entry_warns_at_the_callers_line(field: str) -> None:
    # a list is matched one word at a time, so a phrase can never match
    with warnings.catch_warnings(record=True) as w:
        warnings.simplefilter("always")
        Lexicon(**{field: {"zqx zqy"}})  # type: ignore[arg-type]
    assert [x.filename for x in w] == [__file__]
    assert "matched one word at a time" in str(w[0].message)


def test_an_nfd_authored_entry_is_stored_composed() -> None:
    # the storage fold composes NFC (#322), so a caller who authors a
    # surname in NFD gets the NFC entry -- and raw NFD input, which
    # segmentation matches without folding, then finds no entry and
    # goes unsplit (decisions/W1's 2026-07-29 NFD bullet: NFD degrades
    # to no-split, never to a wrong split)
    nfd = unicodedata.normalize("NFD", "김")
    lex = Lexicon(surnames=frozenset({nfd}))
    assert lex.surnames == frozenset({"김"})
    assert nfd not in lex.surnames


def test_every_shipped_entry_is_already_nfc() -> None:
    # NFC at storage changes no shipped entry, so the vocabulary a caller
    # reads back is the vocabulary that was authored
    lex = Lexicon.default()
    for field, words in _fields_of(lex._sets).items():
        for word in words:
            assert unicodedata.normalize("NFC", word) == word, (field, word)
    for pair in lex.capitalization_exceptions:
        for word in pair:
            assert unicodedata.normalize("NFC", word) == word, pair


def test_the_lists_stay_fields() -> None:
    lex = Lexicon(surnames=frozenset({"毛", "欧阳"}))
    assert lex.surnames == frozenset({"毛", "欧阳"})
    merged = Lexicon(surnames=frozenset({"김"})) | Lexicon(surnames=frozenset({"박"}))
    assert merged.surnames == frozenset({"김", "박"})
    assert dataclasses.replace(merged, surnames={"김"}).surnames == {"김"}  # type: ignore[arg-type]
    assert (Lexicon.default() | Lexicon(given_names={"Luis", "José"})
            ).given_names == frozenset({"luis", "josé"})


# -- configuring by reading: add and remove ----------------------------------

def test_add_and_remove_return_new_lexicons() -> None:
    base = Lexicon.default()
    lex = base.add("zqtitle", kind="title").remove("esquire")
    assert "zqtitle" in lex._sets.titles and "zqtitle" not in base._sets.titles
    # precondition, or the removal passes vacuously
    assert "esquire" in base._sets.suffix_words
    assert "esquire" not in lex._sets.suffix_words
    assert lex.readings_of("esquire") == ()


def test_remove_takes_a_kind_or_a_category() -> None:
    # dean holds an office reading and the given and family readings
    lex = Lexicon.default()
    assert {r.kind for r in lex.readings_of("dean")} == {
        "office", "given", "family"}
    assert {r.kind for r in lex.remove("dean", kind="office")
            .readings_of("dean")} == {"given", "family"}
    # a category matches every kind of it: `title` is both
    assert {r.kind for r in lex.remove("dean", kind="title")
            .readings_of("dean")} == {"given", "family"}
    assert {r.kind for r in lex.remove("dean", kind="name")
            .readings_of("dean")} == {"office"}


def _kinds_and_categories() -> list[str]:
    import nameparser._reading_index as ri
    return list(ri.CATEGORY) + sorted(
        set(ri.CATEGORY.values()) - set(ri.CATEGORY))


#: The kinds and categories a whole-kind remove cannot take out of the
#: default: the build's checks 9 and 11 refuse a bound given particle
#: with no given reading and an agnomen with no name reading, naming
#: the word, as they refuse the same remove written word by word.
_REFUSED_WHOLE = {"given", "family", "name"}


@pytest.mark.parametrize("kind", _kinds_and_categories())
def test_remove_of_a_kind_with_no_words_takes_out_every_word(kind: str) -> None:
    lex = Lexicon.default()
    held = lex.words(kind=kind)
    assert held  # precondition, or the removal passes vacuously
    if kind in _REFUSED_WHOLE:
        with pytest.raises(ValueError, match="no given reading|no name "
                                             "reading"):
            lex.remove(kind=kind, every=True)._sets
        return
    lean = lex.remove(kind=kind, every=True)
    assert lean.words(kind=kind) == ()
    # the same lexicon as the words removed one by one, set for set
    by_word = lex.remove(*held, kind=kind)
    for name in _SET_FIELDS + _KIND_FIELDS:
        assert getattr(lean._sets, name) == getattr(by_word._sets, name), name
    # nothing else goes: every other kind keeps its words
    for other in _kinds_and_categories():
        if other == kind or other in _REFUSED_WHOLE:
            continue
        kept = set(lex.words(kind=other)) - set(held)
        assert kept <= set(lean.words(kind=other)), other


def test_remove_of_a_kind_reaches_readings_a_later_choice_turns_on() -> None:
    # `maestra` is Spanish's academic title, off by default and turned on
    # by the choice; the caller's edits apply after the choice
    from nameparser import locales
    assert "maestra" not in Lexicon.default().words(kind="academic")
    es = parser_for(locales.ES)
    assert "maestra" in es.lexicon.words(kind="academic")
    assert es.parse("Maestra Ana Ruiz").title == "Maestra"
    lean = parser_for(locales.ES, base=Parser(
        lexicon=Lexicon.default().remove(kind="academic", every=True)))
    assert lean.lexicon.words(kind="academic") == ()
    assert lean.parse("Maestra Ana Ruiz").title == ""


def test_a_whole_kind_remove_takes_readings_written_off_as_a_word_remove_does() -> None:
    # `maestra`'s academic reading is es.toml's, off by default: an add of
    # the kind turns it on, naming its file, unless a remove took it out
    # first, word by word or whole, leaving the caller's own reading
    lex = Lexicon.default()
    assert "maestra" not in lex.words(kind="academic")
    assert lex.add("maestra", kind="academic").readings_of("maestra")[
        0].languages == ("es",)
    for removed in (lex.remove("maestra", kind="academic"),
                    lex.remove(kind="academic", every=True)):
        (reading,) = removed.add("maestra", kind="academic").readings_of(
            "maestra")
        assert reading.languages == ()


def test_a_whole_kind_remove_is_logged_apart_and_round_trips() -> None:
    lex = Lexicon.default().remove("dean", kind="title").remove(
        kind="title", every=True).add("zqtitle", kind="salutation")
    assert lex.words(kind="title") == ("zqtitle",)
    assert pickle.loads(pickle.dumps(lex)) == lex
    assert pickle.loads(pickle.dumps(lex)).words(kind="title") == ("zqtitle",)
    # the two removes stay two calls: a whole-kind remove joined to the
    # word before it would name only `dean`
    from nameparser._lexicon import _rendered
    assert _rendered(lex._edits) == [
        ".remove('dean', kind='title')", ".remove(kind='title', every=True)",
        ".add('zqtitle', kind='salutation')"]


def test_a_clash_message_renders_edits_as_a_caller_writes_them() -> None:
    # _built's clash message renders the caller's edits through
    # _rendered: consecutive edits of one kind join into one call, a
    # long list is cut at six words, and a removed property shows its
    # unwritten value. The 2.x translation's refusals reached these
    # paths until 3.1 deleted it (#1003).
    from nameparser._lexicon import _rendered
    lex = (Lexicon.empty().add("zzb", kind="title").add("zzc", kind="title")
           .add("zzt", kind="office", attaches=list("abcdefg"))
           .add("zzt", kind="office", addresses=None))
    assert _rendered(lex._edits) == [
        ".add('zzb', 'zzc', kind='title')",
        ".add('zzt', kind='office', attaches=['a', 'b', 'c', 'd', 'e', 'f', "
        "... 1 more])",
        ".add('zzt', kind='office', addresses='family')"]


@pytest.mark.parametrize("kind", _kinds_and_categories())
def test_words_lists_exactly_the_words_holding_a_reading_of_the_kind(
        kind: str) -> None:
    lex = Lexicon.default().add("zqword", kind="salutation")
    listed = lex.words(kind=kind)
    assert list(listed) == sorted(set(listed))
    held = {w for w in lex._pool() if any(
        r.kind == kind or r.category == kind
        for r in lex.readings_of(w))}
    assert set(listed) == held


def test_words_narrows_by_properties_as_add_spells_them() -> None:
    lex = Lexicon.empty().add("zqsir", kind="nobility", addresses="given") \
        .add("zqlord", kind="nobility").add("zqmrs", kind="salutation",
                                            after_given=True)
    assert lex.words(kind="nobility") == ("zqlord", "zqsir")
    assert lex.words(kind="nobility", addresses="given") == ("zqsir",)
    # the unwritten value selects the readings that do not write it
    assert lex.words(kind="nobility", addresses="family") == ("zqlord",)
    assert lex.words(kind="salutation", after_given=True) == ("zqmrs",)
    assert lex.words(kind="salutation", after_given=False) == ()
    assert Lexicon.empty().words(kind="title") == ()
    # `title` is a kind and a category: as a category it reaches every
    # title kind, and as a kind it takes the title reading's properties
    assert lex.words(kind="title", addresses="given") == ("zqsir",)


def test_words_compares_a_property_in_each_readings_own_kind() -> None:
    # `suffix` is a kind and a category, and `acronym` is unwritten-true
    # on a credential, false on a suffix word: asked of the category,
    # each reading answers in its own kind
    lex = Lexicon.empty().add("zqc", kind="credential").add(
        "zqw", kind="credential", acronym=False).add("zqg", kind="generation")
    assert lex.words(kind="suffix", acronym=True) == ("zqc",)
    assert lex.words(kind="suffix", acronym=False) == ("zqg", "zqw")
    default = Lexicon.default()
    acronyms = set(default.words(kind="suffix", acronym=True))
    words = set(default.words(kind="suffix", acronym=False))
    assert "md" in acronyms and "jr" in words
    assert acronyms.isdisjoint(words)
    assert acronyms | words == set(default.words(kind="suffix"))


def test_every_shipped_reading_holds_its_properties_canonical() -> None:
    # what `words` compares a reading's properties as: held as add would
    # write them, an unwritten value never (a written `acronym = true` on
    # a credential would match no `words(..., acronym=True)`)
    from nameparser._lexicon import _prop_value
    behavioral = ("abbreviation", "acronym", "addresses", "after_given", "attached",
                  "attaches", "may_be_initial", "same_as")
    held = [(w, r.kind, p, v) for w, rs in Lexicon.default()._pool().items()
            for r in rs for p, v in r.props.items() if p in behavioral]
    assert held  # precondition: the default writes some
    assert [h for h in held if _prop_value(h[1], h[2], h[3]) != h[3]] == []


def test_words_matches_a_list_property_whatever_its_order() -> None:
    # `chief`'s nobility reading attaches to military and office titles;
    # the asked list is folded and sorted as add folds it
    lex = Lexicon.default()
    held = lex.words(kind="nobility", attaches=["military", "office"])
    assert "chief" in held
    assert lex.words(kind="nobility", attaches=["Office", "military"]) == held


@pytest.mark.parametrize(("call", "error", "match"), [
    (lambda: Lexicon.empty().words(kind="titel"), ValueError, "or a category, on words"),
    (lambda: Lexicon.empty().words(kind=None), TypeError, "kind as a string"),  # type: ignore[arg-type]
    (lambda: Lexicon.empty().words(kind="name", same_as="x"), ValueError, "takes properties with a kind, not the category 'name'"),
    (lambda: Lexicon.empty().words(kind="nobility", acronym=True), ValueError, "a nobility reading takes"),
    (lambda: Lexicon.empty().words("title"), TypeError, "positional"),  # type: ignore[misc]
    (lambda: Lexicon.empty().remove(), TypeError, re.escape("remove(kind='title', every=True)")),
    # an empty splat is the call with no words: it raises, as in 2.x,
    # rather than take out the whole kind
    (lambda: Lexicon.default().remove(*[], kind="title"), TypeError, "at least one word"),
    (lambda: Lexicon.empty().remove("dean", kind="title", every=True), TypeError, "words or every=True, not both"),
    (lambda: Lexicon.empty().remove(every=True), TypeError, "takes a kind"),
    (lambda: Lexicon.empty().remove(kind="title", every=1), TypeError, "every as True or False"),  # type: ignore[arg-type]
])
def test_words_and_a_whole_kind_remove_refuse_with_the_fix(
        call: Callable[[], object], error: type[Exception], match: str) -> None:
    with pytest.raises(error, match=match):
        call()


def test_add_of_a_held_kind_updates_it_in_every_file() -> None:
    # `e`'s conjunction is Italian and Portuguese, one-case fork and all
    lex = Lexicon.default()
    assert lex.readings_of("e")[0].languages == ("it", "pt")
    settled = lex.add("e", kind="conjunction", may_be_initial=False)
    (reading,) = settled.readings_of("e")
    assert (reading.properties, reading.languages) == ((), ("it", "pt"))
    assert "e" not in settled._sets.conjunctions_ambiguous
    assert Parser(lexicon=settled).parse("ANA SILVA E SOUZA").family == (
        "SILVA E SOUZA")


def test_add_of_a_held_kind_turns_a_reading_written_off_on() -> None:
    # st's generation reading is cs, hr, sk and sl's, off by default;
    # an add of that kind turns it on in each file, beside its name
    # reading, so it is a suffix word gated by the count
    lex = Lexicon.default()
    assert "st" not in lex._sets.suffix_words
    on = lex.add("st", kind="generation")
    (generation,) = [r for r in on.readings_of("st") if r.kind == "generation"]
    assert generation.languages == ("cs", "hr", "sk", "sl")
    assert "st" in on._sets.suffix_words_ambiguous
    assert "st" in on._sets.generation_words


def test_a_callers_own_reading_names_no_file() -> None:
    lex = Lexicon.default().add("leed", "ap", kind="credential")
    assert lex.readings_of("leed") == (
        LexiconReading("leed", "credential", "suffix"),)
    assert Parser(lexicon=lex).parse("John Smith LEED AP").suffix == "LEED AP"


def test_a_property_given_its_unwritten_value_is_removed() -> None:
    lex = Lexicon.empty().add("sir", kind="nobility", addresses="given")
    assert lex.readings_of("sir")[0].properties == (("addresses", "given"),)
    for unwritten in ("family", None):
        cleared = lex.add("sir", kind="nobility", addresses=unwritten)
        assert cleared.readings_of("sir")[0].properties == ()
    # acronym is unwritten-true on a credential alone
    worded = Lexicon.empty().add("kc", kind="credential", acronym=False)
    assert "kc" in worded._sets.suffix_words
    assert "kc" in worded._sets.credential_words
    assert worded.readings_of("kc")[0].properties == (("acronym", False),)


def test_a_derived_marker_follows_from_the_readings() -> None:
    # a given reading beside a credential gates it, as the build derives
    # it from a file: `dc` becomes an ambiguous acronym
    lex = Lexicon.default().add("dc", kind="given")
    assert "dc" in lex._sets.suffix_acronyms_ambiguous
    assert "dc" not in Lexicon.default()._sets.suffix_acronyms_ambiguous


@pytest.mark.parametrize(("call", "error", "match"), [
    (lambda: Lexicon.empty().add("x"), TypeError, "missing required keyword argument 'kind'"),  # type: ignore[call-arg]
    (lambda: Lexicon.empty().add(kind="title"), TypeError, "at least one word"),
    (lambda: Lexicon.empty().remove(), TypeError, "at least one word"),
    (lambda: Lexicon.empty().add("x", kind="titel"), ValueError, "unknown reading kind 'titel'"),
    (lambda: Lexicon.empty().add("x", kind=3), TypeError, "kind as a string"),  # type: ignore[arg-type]
    # a category with no kind of its name names its kinds
    (lambda: Lexicon.empty().add("x", kind="name"), ValueError, "kinds: given, family"),
    (lambda: Lexicon.empty().add("x", kind="relation"), ValueError, "kinds: birth_marker"),
    (lambda: Lexicon.empty().remove("x", kind="titel"), ValueError, "or a category, on remove"),
    (lambda: Lexicon.empty().add("x", kind="title", default=False), ValueError, "a caller's reading is on"),
    (lambda: Lexicon.empty().add("x", kind="title", cased="X"), ValueError, "capitalization_exceptions"),
    (lambda: Lexicon.empty().add("x", kind="title", acronym=True), ValueError, "a title reading takes abbreviation, addresses, after_given, attached, attaches"),
    (lambda: Lexicon.empty().add("x", kind="family", after_particle=True), ValueError, "after_particle names a given name"),
    (lambda: Lexicon.empty().add("x", kind="family", after_particle=True), ValueError, "only a given reading takes it"),
    (lambda: Lexicon.empty().add("x", kind="title", after_given="yes"), TypeError, "after_given must be True or False"),
    (lambda: Lexicon.empty().add("x", kind="title", abbreviation="yes"), TypeError, "abbreviation must be True or False"),
    (lambda: Lexicon.empty().add("x", kind="title", addresses="first"), ValueError, "addresses must be 'given' or 'family'"),
    (lambda: Lexicon.empty().add("x", kind="title", attaches="military"), TypeError, "attaches must be an iterable"),
    (lambda: Lexicon.empty().add("x", kind="honorific", attached="before"), ValueError, "reading must be 'after'"),
    (lambda: Lexicon.empty().add("x y", kind="salutation", addresses="given", attached="before"), ValueError, "marks a one-word title"),
    (lambda: Lexicon.empty().add("x", kind="given", same_as=""), TypeError, "same_as must be the word this one is a spelling of"),
    # the build's check 8: a phrase matches only as a marker or a run of
    # titles addressing the given name
    (lambda: Lexicon.empty().add("chief justice", kind="title"), ValueError, "a phrase, which can never match as a title"),
    # rules/P8's marker reads a single cased letter alone
    (lambda: Lexicon.empty().add("and", kind="conjunction", may_be_initial=True), ValueError, "not one"),
    # the build's check 4: one suffix kind per word, naming the fix
    (lambda: Lexicon.default().add("dc", kind="generation"), ValueError, re.escape(".remove('dc', kind='credential')")),
    # check 11: an agnomen is gated by a name reading beside it
    (lambda: Lexicon.default().add("bisneto", kind="agnomen"), ValueError, re.escape(".add('bisneto', kind='family')")),
    (lambda: Lexicon.default().remove("neto", kind="name"), ValueError, "agnomen with no name reading"),
    # check 9: a bound given name that is a particle may be given
    (lambda: Lexicon.empty().add("dos", kind="particle").add("dos", kind="bound_given"), ValueError, re.escape(".add('dos', kind='given')")),
])
def test_add_and_remove_refuse_with_the_fix(
        call: Callable[[], object], error: type[Exception], match: str) -> None:
    with pytest.raises(error, match=match):
        call()


def test_a_phrase_reading_is_stored_folded_per_word() -> None:
    lex = Lexicon.empty().add("Z. Domu", kind="birth_marker").add(
        "Lt.  Col.", kind="title", addresses="given")
    assert lex._sets.maiden_markers == frozenset({"z domu"})
    assert lex._sets.given_name_titles == frozenset({"lt col"})
    assert lex.readings_of("z. domu")[0].kind == "birth_marker"


@pytest.mark.parametrize("spelling", ["lt. col", "lt col", "Lt.  Col."])
def test_a_given_title_run_folds_per_word_so_abbreviations_match(
        spelling: str) -> None:
    # The run's key is built per word and rejoined, so an abbreviated
    # phrase folds the way the parse folds the title run; it is the
    # whole-run arm that matches, `col` alone addressing the family
    lex = Lexicon.default().add(spelling, kind="title", addresses="given")
    assert "lt col" in lex._sets.given_name_titles
    assert "col" not in lex._sets.given_name_titles
    assert Parser(lexicon=lex).parse("Lt. Col. Smith").given == "Smith"


def test_the_shipped_given_name_titles_are_every_one_a_single_word() -> None:
    # what makes the whole-run arm dead for the shipped vocabulary: it
    # can only match a one-word run, which the last-word arm reads the
    # same way (#489)
    sets = Lexicon.default()._sets
    assert not any(" " in t for t in sets.given_name_titles)
    # and the last-word arm's premise: 'dr sir' is no entry, 'sir' is
    assert "dr sir" not in sets.given_name_titles
    assert "sir" in sets.given_name_titles


def test_the_shipped_suffix_sets_are_disjoint() -> None:
    # The two sets normalize differently -- the word test strips only
    # edge periods, the acronym test all of them -- so a word in both
    # is matched by two rules (decisions/suffix-acronym-collisions); a
    # compile from readings refuses two suffix kinds on a word, and one
    # kind is an acronym or a word
    assert SUFFIX_ACRONYMS & SUFFIX_WORDS == frozenset()
    sets = Lexicon.default()._sets
    assert sets.suffix_acronyms & sets.suffix_words == frozenset()


def test_default_lexicon_satisfies_the_bound_particle_invariant() -> None:
    d = Lexicon.default()._sets
    assert not (d.bound_given_names & d.particles) - d.particles_ambiguous


def test_removing_a_honorific_tails_attachment_is_the_peels_off_switch() -> None:
    # dropping `attached` leaves the glued name unsplit while the SPACED
    # spelling still reads the honorific, a suffix word either way
    lex = Lexicon.default().add("さん", kind="honorific", attached=None)
    assert "さん" not in lex._sets.honorific_tails
    p = Parser(lexicon=lex)
    glued = p.parse("田中さん")
    assert (glued.family, glued.suffix) == ("田中さん", "")
    spaced = p.parse("田中 さん")
    assert (spaced.family, spaced.suffix) == ("田中", "さん")
    on = Parser().parse("田中さん")
    assert (on.family, on.suffix) == ("田中", "さん")


def test_removing_a_glued_titles_attachment_is_the_front_peels_off_switch(
        ) -> None:
    # dropping `attached` leaves the glued name whole while the SPACED
    # spelling still reads the title (rules/W6, #317)
    lex = Lexicon.default().add("นาย", kind="salutation", attached=None)
    assert "นาย" not in lex._sets.glued_titles
    p = Parser(lexicon=lex)
    assert (p.parse("นายสมชาย ใจดี").title,
            p.parse("นาย สมชาย ใจดี").title) == ("", "นาย")
    assert Parser().parse("นายสมชาย ใจดี").title == "นาย"


def test_a_callers_glued_title_reaches_the_front_peel() -> None:
    # attached="before" on a caller's title peels as a file's does
    p = Parser(lexicon=Lexicon.default().add(
        "คุณ", kind="salutation", attached="before"))
    name = p.parse("คุณสมชาย ใจดี")
    assert (name.title, name.given) == ("คุณ", "สมชาย")
    assert Parser().parse("คุณสมชาย ใจดี").given == "คุณสมชาย"


def test_a_glued_title_that_may_be_a_given_name_never_peels() -> None:
    # a title only in a phrase (rules/H9) is left out of the peel set,
    # so its given name is not cut with no title read (#317's review)
    lex = (Lexicon.default().add("คุณ", kind="salutation", attached="before")
           .add("คุณ", kind="given"))
    assert "คุณ" not in lex._sets.glued_titles
    name = Parser(lexicon=lex).parse("คุณสมชาย ใจดี")
    assert (name.title, name.given) == ("", "คุณสมชาย")


def test_a_peeled_title_keeps_the_writing_and_names_its_file() -> None:
    # the pieces join as written (rules/R1) and the title's reading is
    # the vocabulary's, in th
    name = Parser().parse("นายสมชาย ใจดี")
    reading = name.tokens[0].reading
    assert str(name) == "นายสมชาย ใจดี"
    assert reading is not None
    assert (reading.source, reading.languages) == ("vocabulary", ("th",))


def test_a_word_lowered_to_another_length_is_no_peel_site() -> None:
    # a letter that lowercases into two moves every offset after it, so
    # the peel declines the word rather than cut it at the wrong place
    p = Parser(lexicon=Lexicon.default().add(
        "mr", kind="salutation", attached="before"))
    assert p.parse("Mrİsmith ใจดี").title == ""
    assert p.parse("Mrsmith ใจดี").title == "Mr"


def test_every_shipped_glued_title_is_reachable() -> None:
    # each marked title glued to a given name splits off it (rules/W6),
    # so a word another reading claims first shows up as silently inert
    # a modifier is a title only before a head title (rules/H9), so it
    # is probed before one ('ว่าที่ร.ท.สมชาย', #1319)
    p = Parser()
    mods = p.lexicon._sets.title_modifiers
    unreached = [w for w in sorted(p.lexicon._sets.glued_titles)
                 if not p.parse(f"{w}ร.ท.สมชาย ใจดี" if w in mods
                                else f"{w}สมชาย ใจดี").title.startswith(w)]
    assert p.lexicon._sets.glued_titles and not unreached, unreached


def test_removing_after_given_is_rule_h8s_off_switch() -> None:
    # the bare salutation is a middle name after a family comma, while
    # the period-marked spelling reads as the title by H5's shape
    lex = Lexicon.default().add("mrs", kind="salutation", after_given=False)
    p = Parser(lexicon=lex)
    assert (p.parse("Doe, Jane Mrs").title,
            p.parse("Doe, Jane Mrs").middle) == ("", "Mrs")
    assert p.parse("Doe, Jane Mrs.").title == "Mrs."
    assert Parser().parse("Doe, Jane Mrs").title == "Mrs"
    # and with the title reading gone there is nothing to read after
    # the given name
    gone = Parser(lexicon=Lexicon.default().remove("mrs", kind="title"))
    assert (gone.parse("Doe, Jane Mrs").title,
            gone.parse("Doe, Jane Mrs").middle) == ("", "Mrs")


def test_dotted_is_rule_h10s_switch_both_ways() -> None:
    # a caller's dotted=True reaches the parse as a file's does, and
    # dotted=False turns a shipped one off (rules/H10, #490)
    ceo = Parser(lexicon=Lexicon.default().add("ceo", kind="office",
                                               dotted=True))
    assert ceo.parse("C.E.O. Prof. Jane Smith").title == "C.E.O. Prof."
    assert Parser().parse("C.E.O. Prof. Jane Smith").title == ""
    off = Parser(lexicon=Lexicon.default().add("us", kind="modifier",
                                               dotted=False))
    # a name, which rules/T7 parts into its initials (#1296)
    assert off.parse("U.S. Senator John Smith").given == "U."
    assert Parser().parse("U.S. Senator John Smith").title == "U.S. Senator"


def test_a_dotted_title_reads_as_listed_in_its_language() -> None:
    # assemble counts classify's dotted tag as a listed title's
    # (rules/H10), so the reading names the vocabulary and its file
    us = Parser().parse("U.S. Senator John Smith").tokens[0].reading
    pd = Parser().parse("P.D. Dr. Hans Meier").tokens[0].reading
    assert us is not None and pd is not None
    assert (us.source, us.languages) == ("vocabulary", ("en",))
    assert (pd.source, pd.languages) == ("vocabulary", ("de",))


def test_every_shipped_dotted_title_is_reachable() -> None:
    # each marked title, spelled with a stop after each letter, reads as
    # the title before another (rules/H10), so a word another reading
    # claims first shows up as silently inert
    p = Parser()
    unreached = [w for w in sorted(p.lexicon._sets.dotted_titles)
                 if p.parse(f"{'.'.join(w.upper())}. Senator Jane Smith"
                            ).title != f"{'.'.join(w.upper())}. Senator"]
    assert p.lexicon._sets.dotted_titles and not unreached, unreached


def test_every_shipped_after_given_title_is_reachable() -> None:
    # each entry must reach rules/H8 at the slot it is listed for, so a
    # member another reading claims first shows up as silently inert
    p = Parser()
    unreached = [w for w in sorted(p.lexicon._sets.after_given_titles)
                 if p.parse(f"Doe, Jane {w.title()}").title != w.title()]
    assert not unreached, unreached


# -- the views read the lexicon's kinds (R8 and R9, #754 4i-b) -----------------

def test_the_suffix_views_read_the_kind_the_lexicon_states() -> None:
    # R8, the generation and credentials views: the kind of a listed
    # suffix word is the lexicon's, so a
    # word a caller lists as a generation reads as one (the 2.x spelling,
    # a suffix word with no kind, read credentials `Secundus`)
    name = "Marcus Tullius Secundus"
    generation = Parser(lexicon=Lexicon.default().add(
        "secundus", kind="generation")).parse(name)
    assert (generation.generation, generation.credentials) == ("Secundus", "")
    plain = Parser(lexicon=Lexicon.default().add(
        "secundus", kind="suffix")).parse(name)
    assert (plain.generation, plain.credentials) == ("", "Secundus")


def test_the_patronymic_view_reads_the_kind_the_lexicon_states() -> None:
    # R9, the patronymic view: `bin` read as a patronymic particle while
    # the lexicon
    # holds that kind, a plain particle once it holds another
    name = "Mahathir bin Mohamad"
    assert Parser().parse(name).patronymic == "bin Mohamad"
    plain = Lexicon.default().add("bin", kind="preposition").remove(
        "bin", kind="patronymic")
    parsed = Parser(lexicon=plain).parse(name)
    assert (parsed.family, parsed.patronymic) == ("bin Mohamad", "")


def test_the_default_kind_sets_are_the_shipped_index_s() -> None:
    # by the compile invariant: what the views read on the default is
    # what the shipped files say (the index lookup 4b and 4c read)
    from nameparser._reading_index import (
        HONORIFIC_KINDS, holds_kind, suffix_kind_of)
    sets = Lexicon.default()._sets
    for word in sets.suffix_words:
        kind = suffix_kind_of(word)
        assert (word in sets.generation_words) == (kind == "generation"), word
        assert (word in sets.credential_words) == (kind == "credential"), word
        assert (word in sets.honorific_words) == (
            kind in HONORIFIC_KINDS), word
    for word in sets.particles:
        assert (word in sets.patronymic_particles) == holds_kind(
            word, "patronymic"), word
        assert (word in sets.saint_particles) == holds_kind(
            word, "saint"), word
        assert (word in sets.capitalized_particles) == (
            holds_kind(word, "saint") or holds_kind(word, "rank")), word


# -- the 2.x spellings, refused ----------------------

#: (name, 3.0 spelling): the recipes the RFC's table carries
#: (docs/design/vocabulary-model-rfc.md, item 1), each moving the parse
#: it names.
_RECIPES = [
    ("Dean Smith", lambda L: L.remove("dean", kind="given")),
    ("John Smith LEED AP", lambda L: L.add("leed", "ap", kind="credential")),
    ("Professor Plum", lambda L: L.remove("professor", kind="title")),
    ("Guru Prasad Sharma", lambda L: L.add("guru", kind="given")),
    ("Ram Bahadur DC", lambda L: L.remove("dc", kind="credential")),
    ("Van Johnson", lambda L: L.remove("van", kind="given")),
    ("ANA SILVA E SOUZA",
     lambda L: L.add("e", kind="conjunction", may_be_initial=False)),
    ("Mohamad Ali Khan", lambda L: L.add("mohamad", kind="bound_given")),
    ("Jane Smith formerly Jones",
     lambda L: L.add("formerly", kind="birth_marker")),
    ("山田さん", lambda L: L.add("さん", kind="honorific", attached=None)),
]


@pytest.mark.parametrize(("text", "spell"), _RECIPES,
                         ids=[r[0] for r in _RECIPES])
def test_each_recipe_moves_the_parse_it_names(
        text: str, spell: Callable[[Lexicon], Lexicon]) -> None:
    # the recipe's own negative control: the default reads it otherwise
    configured = Parser(lexicon=spell(Lexicon.default())).parse(text)
    assert configured.as_dict() != Parser().parse(text).as_dict()


@pytest.mark.parametrize("field", _SET_FIELDS)
def test_every_2x_set_field_is_refused_at_all_four_sites(field: str) -> None:
    for call in (lambda: Lexicon.empty().add(**{field: {"zzq"}}),  # type: ignore[arg-type]
                 lambda: Lexicon.empty().remove(**{field: {"zzq"}}),  # type: ignore[arg-type]
                 lambda: Lexicon(**{field: {"zzq"}}),  # type: ignore[arg-type]
                 lambda: dataclasses.replace(Lexicon.empty(),
                                             **{field: {"zzq"}})):  # type: ignore[arg-type]
        with pytest.raises(TypeError, match=f"takes no {field} since 3.0"):
            call()
    with pytest.raises(AttributeError, match=re.escape(
            f"Lexicon.{field} is internal since 3.0")) as raised:
        getattr(Lexicon.default(), field)
    assert "readings_of" in str(raised.value)
    assert "Token.reading" in str(raised.value)


def test_a_list_or_the_masks_through_add_is_refused_with_its_spelling() -> None:
    # the offered code names the caller's own words and RUNS as pasted
    # (root AGENTS.md: a message's code must type-check and run)
    for call, expected in (
            (lambda: Lexicon.default().add(surnames={"김민"}),  # type: ignore[call-arg]
             "lexicon | Lexicon(surnames={'김민'})"),
            (lambda: Lexicon.default().remove(given_names={"luis"}),
             "dataclasses.replace(lexicon, given_names=lexicon.given_names"
             " - {'luis'})")):
        with pytest.raises(TypeError, match=re.escape(expected)) as raised:
            call()
        code = str(raised.value).rsplit("write ", 1)[1]
        pasted = eval(code, {"dataclasses": dataclasses,  # noqa: S307
                             "Lexicon": Lexicon, "lexicon": Lexicon.default()})
        assert isinstance(pasted, Lexicon)
    with pytest.raises(TypeError, match="unexpected keyword argument 'prefixes'"):
        Lexicon.default().remove(prefixes={"van"})  # a v1 name
    with pytest.raises(TypeError, match="unexpected keyword argument 'zq'"):
        Lexicon(zq=1)


def test_add_capitalization_exceptions_raises_pointing_at_replace() -> None:
    # The offered spelling is a tuple, not a dict: the field is
    # annotated as one, so a pasted dict fails mypy (AGENTS.md). And
    # it must RUN as pasted: the value is a case mask of its key, so
    # ('key', 'Value') type-checks and then raises (2.4 release sweep).
    offered = re.escape(
        "dataclasses.replace(lexicon, capitalization_exceptions="
        "(*lexicon.capitalization_exceptions, ('key', 'KEY')))")
    with pytest.raises(TypeError, match=offered) as raised:
        Lexicon.default().add(capitalization_exceptions={"x": "X"})  # type: ignore[call-arg]
    code = re.search(r"dataclasses\.replace\(.*?\)\)\)",
                     str(raised.value))
    assert code is not None
    pasted = eval(code[0], {"dataclasses": dataclasses,  # noqa: S307
                            "lexicon": Lexicon.default()})
    assert pasted.capitalization_exceptions_map["key"] == "KEY"


# -- the title warning (decisions/vocabulary-model, 2026-11-01) -------------

def _warned(build: Callable[[], object]) -> list[warnings.WarningMessage]:
    with warnings.catch_warnings(record=True) as w:
        warnings.simplefilter("always")
        build()
    return [x for x in w if "title only inside a title phrase" in str(x.message)]


@pytest.mark.parametrize(("build", "warns"), [
    # a title reading created on a word whose given reading keeps it a
    # title only inside a phrase: the 1.4 recipe's trap
    (lambda: Lexicon.default().add("dean", kind="title"), True),
    # the word's own kind re-added unchanged: the same trap
    (lambda: Lexicon.default().add("dean", kind="office"), True),
    # a property update of a held title reading is the caller's
    # intent, and the warning's fix would widen it
    (lambda: Lexicon.default().add("prince", kind="nobility",
                                   attaches=["military"]), False),
    # no given reading, so a title everywhere
    (lambda: Lexicon.default().add("zzq", kind="title"), False),
    (lambda: Lexicon.default().remove("dean", kind="given").add(
        "dean", kind="title"), False),
    # not a title reading
    (lambda: Lexicon.default().add("dean", kind="family"), False),
], ids=["created", "re-added", "property-update", "no-given-reading",
        "given-removed-first", "not-a-title"])
def test_the_title_warning_fires_where_the_add_changes_nothing_outside_a_phrase(
        build: Callable[[], object], warns: bool) -> None:
    assert bool(_warned(build)) is warns


def test_the_title_warning_names_the_fix_at_the_callers_line() -> None:
    (w,) = _warned(lambda: Lexicon.default().add("dean", kind="title"))
    assert w.filename == __file__
    assert ".remove('dean', kind='given')" in str(w.message)
    # and the add it warns about does read no name differently
    lex = _quiet(lambda: Lexicon.default().add("dean", kind="title"))
    assert Parser(lexicon=lex).parse("Dean Smith").as_dict() == \
        Parser().parse("Dean Smith").as_dict()


def test_nothing_but_add_warns() -> None:
    lex = _quiet(lambda: Lexicon.default().add("dean", kind="title"))
    with warnings.catch_warnings():
        warnings.simplefilter("error")
        dataclasses.replace(lex, surnames={"김"})  # type: ignore[arg-type]
        pickle.loads(pickle.dumps(lex))
        lex | Lexicon.empty()
        Lexicon.default().remove("dean", kind="given")


# -- readings_of and LexiconReading ----------------------------------------

def test_readings_of_answers_with_kind_category_and_files() -> None:
    lex = Lexicon.default()
    assert lex.readings_of("Dean") == (
        LexiconReading("dean", "office", "title", (), ("en",)),
        LexiconReading("dean", "given", "name", (), ("en",)),
        LexiconReading("dean", "family", "name", (), ("en",)))
    assert lex.readings_of("zzqnotaword") == ()
    assert any(r.category == "title" for r in lex.readings_of("Dr."))


def test_readings_of_answers_for_the_lexicon_not_the_shipped_files() -> None:
    lex = Lexicon.default().remove("dean", kind="given")
    assert {r.kind for r in lex.readings_of("dean")} == {"office", "family"}
    assert Lexicon.empty().readings_of("dean") == ()


def test_a_lexicon_reading_is_a_frozen_hashable_picklable_value() -> None:
    reading = Lexicon.default().readings_of("sir")[0]
    assert hash(reading) == hash(copy.copy(reading))
    assert pickle.loads(pickle.dumps(reading)) == reading
    with pytest.raises(dataclasses.FrozenInstanceError):
        reading.kind = "title"  # type: ignore[misc]
    with pytest.raises(ValueError, match="category is 'title'"):
        LexiconReading("sir", "nobility", "suffix")
    with pytest.raises(ValueError, match="unknown reading kind"):
        LexiconReading("sir", "knight", "title")
    with pytest.raises(TypeError, match="properties must be a tuple"):
        LexiconReading("sir", "nobility", "title", {})  # type: ignore[arg-type]
    state = reading.__getstate__()
    with pytest.raises(ValueError, match="unexpected fields: zq"):
        LexiconReading.__new__(LexiconReading).__setstate__({**state, "zq": 1})


# -- state: equality, the log, |, replace -----------------------------------

def test_lexicon_is_hashable() -> None:
    assert isinstance(hash(Lexicon.default()), int)
    assert isinstance(hash(Lexicon.default().add("x", kind="title")), int)


def test_two_lexicons_are_equal_when_their_logs_are_as_written() -> None:
    a = Lexicon.default().add("leed", kind="credential")
    assert a == Lexicon.default().add("leed", kind="credential")
    assert hash(a) == hash(Lexicon.default().add("leed", kind="credential"))
    # structural, not "the same compiled readings": a log that undoes
    # itself compiles alike and is not equal (the decided cost)
    undone = a.remove("leed", kind="credential")
    assert _fields_of(undone._sets) == _fields_of(Lexicon.default()._sets)
    assert undone != Lexicon.default()
    # and the order is part of it
    one = Lexicon.empty().add("x", kind="title").add("y", kind="title")
    two = Lexicon.empty().add("y", kind="title").add("x", kind="title")
    assert one != two and one._sets.titles == two._sets.titles
    # the base is: an edit does not make a default-based lexicon empty
    assert Lexicon.default().add("x", kind="title") != \
        Lexicon.empty().add("x", kind="title")


def test_a_later_edit_reads_after_an_earlier_one() -> None:
    lex = Lexicon.empty()
    assert lex.add("x", kind="title").remove("x")._sets.titles == frozenset()
    assert lex.remove("x").add("x", kind="title")._sets.titles == {"x"}


def test_replace_carries_the_base_and_the_log() -> None:
    lex = Lexicon.default().add("leed", kind="credential")
    kept = dataclasses.replace(lex, surnames={"김"})  # type: ignore[arg-type]
    assert kept._edits == lex._edits and kept._base == "default"
    assert "leed" in kept._sets.suffix_acronyms
    if sys.version_info >= (3, 13):
        assert copy.replace(lex, given_names={"luis"})._edits == lex._edits  # type: ignore[attr-defined]


def test_an_edit_log_not_written_by_add_or_remove_is_refused() -> None:
    lex = Lexicon.empty().add("dr", kind="title")
    for bad in ((("add", ("DR",), "title", ()),),
                (("add", ("dr",), "titel", ()),),
                (("rename", ("dr",), "title", ()),),
                ("add",)):
        with pytest.raises((TypeError, ValueError)):
            dataclasses.replace(lex, _edits=bad)  # type: ignore[arg-type]


def test_union_joins_the_logs_in_order_and_the_lists() -> None:
    a = dataclasses.replace(Lexicon.empty().add("dr", kind="title"),
                            capitalization_exceptions=(("phd", "PhD"),))
    b = dataclasses.replace(Lexicon.empty().add("mr", kind="title"),
                            capitalization_exceptions=(("phd", "Ph.D."),),
                            surnames={"김"})  # type: ignore[arg-type]
    u = a | b
    assert u._sets.titles == frozenset({"dr", "mr"})
    assert u._edits == a._edits + b._edits
    assert u.surnames == frozenset({"김"})
    assert u.capitalization_exceptions_map["phd"] == "Ph.D."  # right wins
    # later wins: b's removal applies after a's add
    assert (a | Lexicon.empty().remove("dr"))._sets.titles == frozenset()
    # the base that is not empty
    assert (Lexicon.empty() | Lexicon.default())._base == "default"
    assert (Lexicon.default() | Lexicon(surnames={"김"}))._base == "default"


def test_union_refuses_two_different_bases() -> None:
    from nameparser.config._index import READINGS
    older = Lexicon(_base=READINGS[1:])
    assert older._base != "default"
    with pytest.raises(ValueError, match="different bases"):
        Lexicon.default() | older


# -- the choice (decisions/vocabulary-model, 2026-11-02 #754, items 3
# and 4) --------------------------------------------------------------------

def test_the_choice_travels_with_replace_union_and_pickle() -> None:
    chosen = dataclasses.replace(Lexicon.default(), _languages=frozenset({"pt-br"}))
    assert chosen.languages == {"pt-BR"} and chosen.strict is False
    assert chosen != Lexicon.default()
    added = chosen.add("zzq", kind="title")
    assert added.languages == {"pt-BR"}
    assert (added | Lexicon(surnames={"김"})).languages == {"pt-BR"}
    assert (Lexicon.empty() | added).languages == {"pt-BR"}
    strict = dataclasses.replace(Lexicon.default(), _languages=frozenset({"vi"}),
                                 _strict=True)
    for lex in (chosen, added, strict):
        loaded = pickle.loads(pickle.dumps(lex))
        assert loaded == lex and hash(loaded) == hash(lex)
        assert (loaded.languages, loaded.strict) == (lex.languages, lex.strict)


#: What the parsers pickled in tests/v2/data/parsers_4ib.pickle read
#: on the tree that wrote them, db7e8fc4 (4i-b), where a choice was 3b's
#: delta written into the lexicon's log
_READ_BY_4IB = [
    ("pt", "ANA SILVA E SOUZA", "family", "SILVA E SOUZA"),
    ("pt", "John Smith DO", "family", "DO"),
    ("cs_strict", "Jiří Dienstbier st.", "suffix", "st."),
    ("cs_strict", "Jan Novák, MUDr", "title", "MUDr"),
    ("cs_strict", "Kim Min Jun, MD", "given", "MD"),
]


def test_a_pickle_written_before_the_choice_fields_loads_choosing_nothing(
        ) -> None:
    # a 4i-b pickle, from no release, holds no choice fields; its log
    # already holds what the choice changed, so it loads choosing
    # nothing and reads as it did (the fields are marked _ADDED_IN;
    # found by review of 4i-c)
    with open(Path(__file__).parent / "data" / "parsers_4ib.pickle",
              "rb") as f:
        parsers = pickle.load(f)  # noqa: S301 -- our own fixture
    for key in ("pt", "cs_strict"):
        assert parsers[key].languages == frozenset(), key
        assert parsers[key].strict is False, key
    for key, text, field_name, value in _READ_BY_4IB:
        assert getattr(parsers[key].parse(text), field_name) == value, text


@pytest.mark.parametrize("left,right", [
    ({"_languages": {"pt"}}, {"_languages": {"en"}}),
    ({"_languages": {"ko"}}, {"_languages": {"ko"}, "_strict": True}),
])
def test_union_refuses_two_different_choices_naming_parser_for(
        left: dict[str, object], right: dict[str, object]) -> None:
    a = dataclasses.replace(Lexicon.default(), **left)  # type: ignore[arg-type]
    b = dataclasses.replace(Lexicon.default(), **right)  # type: ignore[arg-type]
    with pytest.raises(ValueError, match="different choices.*parser_for"):
        a | b
    assert (a | a).languages == a.languages


@pytest.mark.parametrize("kwargs,error,match", [
    ({"_languages": "pt"}, TypeError, "_languages must be a set"),
    ({"_languages": {"pt": 1}}, TypeError, "_languages must be a set"),
    ({"_languages": {5}}, TypeError, "entries must be str"),
    ({"_languages": {"pt"}, "_strict": 1}, TypeError,
     "_strict must be True or False"),
    ({"_strict": True}, ValueError, "chooses none"),
    ({"_languages": {"xx"}}, ValueError, "no vocabulary file holds"),
    ({"_languages": {"mul"}}, ValueError, "not a language to choose"),
    # a file holding no reading is a strict choice only, as at parser_for
    ({"_languages": {"hu"}}, ValueError, "strict=True"),
    ({"_languages": {"mt"}}, ValueError, "strict=True"),
    ({"_languages": {"sq"}}, ValueError, "strict=True"),
])
def test_the_choice_is_validated_as_parser_for_validates_one(
        kwargs: dict[str, object], error: type[Exception], match: str) -> None:
    with pytest.raises(error, match=match):
        Lexicon(**kwargs)  # type: ignore[arg-type]


def test_a_choice_filters_the_base_and_the_log_applies_after_it() -> None:
    # en prefers its credential of `do` over pt's particle; a removal
    # written before the choice was made still applies after it
    # (the RFC's item 4 example)
    removed = Lexicon.default().remove("do", kind="credential")
    chosen = dataclasses.replace(removed, _languages=frozenset({"en"}))
    assert [r.category for r in chosen.readings_of("do")] == ["name", "name"]
    assert [r.kind for r in dataclasses.replace(
        Lexicon.default(), _languages=frozenset({"pt"})).readings_of("do")
        if r.category != "name"] == ["preposition"]


def test_the_repr_shows_the_choice_and_counts_against_it() -> None:
    chosen = dataclasses.replace(Lexicon.default(), _languages=frozenset({"pt"}))
    assert repr(chosen) == "Lexicon(default, languages pt)"
    assert (repr(chosen.add("zzq", kind="title"))
            == "Lexicon(default + title: +1, languages pt)")
    # the masks a strict choice drops are parser_for's to move, and the
    # repr counts against the named lexicon with them moved
    vi = Locale(code="vi", lexicon=Lexicon.empty(), languages=frozenset({"vi"}))
    strict = parser_for(vi, strict=True).lexicon
    assert repr(strict) == "Lexicon(default, languages vi, strict)"
    many = dataclasses.replace(Lexicon.default(),
                               _languages=frozenset({"pt", "en", "es", "de"}))
    assert repr(many) == "Lexicon(default, languages: 4)"


def test_the_internal_sets_hold_each_field_under_its_own_name() -> None:
    # the roster pinned so that a field added to one and not the other
    # fails at once; the kinds the views read follow the 2.x sets (4i-b)
    from nameparser._lexicon import _LexiconSets
    assert [f.name for f in dataclasses.fields(_LexiconSets)] == list(
        _VOCAB_FIELDS + _KIND_FIELDS)
    for lexicon in (Lexicon.default(), Lexicon(surnames={"김"})):
        for name in _LIST_FIELDS:
            assert getattr(lexicon._sets, name) is getattr(lexicon, name), name


def test_the_default_never_loads_the_reading_index() -> None:
    # decisions/vocabulary-model, 2026-11-02 #754, item 4: the default's
    # base is held by reference and its sets read from _compiled.py, so
    # a parse that reads no word from the vocabulary loads no index; the
    # first readings_of does
    code = ("import sys, nameparser\n"
            "nameparser.Lexicon.default()\n"
            "nameparser.parse('John Smith')\n"
            "before = 'nameparser.config._index' in sys.modules\n"
            "nameparser.Lexicon.default().readings_of('dean')\n"
            "print(before, 'nameparser.config._index' in sys.modules)\n")
    out = subprocess.run([sys.executable, "-c", code], capture_output=True,
                         text=True, check=True).stdout
    assert out.split() == ["False", "True"]


def test_lexicon_marks_an_added_field_with_the_shared_key() -> None:
    # one key for every guard: a Lexicon field marked with the key the
    # other types read, and the other way round
    from nameparser import _types
    assert _ADDED_IN == _types.ADDED_IN



# -- pickle (decisions/vocabulary-model, 2026-11-02 #754, item 5) ----------

def test_pickle_round_trip_preserves_equality_and_cap_map() -> None:
    # _cap_map holds a MappingProxyType, which pickle rejects; Lexicon
    # must round-trip anyway because a Parser holds one
    for lex in (Lexicon.default(), Lexicon.empty(),
                Lexicon.empty().add("Dr.", kind="title"),
                _quiet(lambda: Lexicon.default().add("dean", kind="title")
                       .remove("van", kind="given")),
                Lexicon(surnames={"김"}, given_names={"luis"},
                        capitalization_exceptions={"phd": "PhD"})):
        loaded = pickle.loads(pickle.dumps(lex))
        assert loaded == lex
        assert hash(loaded) == hash(lex)
        assert (loaded.capitalization_exceptions_map
                == lex.capitalization_exceptions_map)


def test_the_default_pickles_its_rows_and_loads_by_reference() -> None:
    # a pickle carries the base's rows, so it parses as it did where it
    # was written; rows equal to the running release's become the
    # by-reference base again, so a round trip within a release is equal
    from nameparser.config._index import READINGS
    state = Lexicon.default().__getstate__()
    assert state["_base"] == READINGS
    assert pickle.loads(pickle.dumps(Lexicon.default()))._base == "default"


def test_another_releases_rows_stay_a_snapshot_and_parse_by_it() -> None:
    from nameparser.config._index import READINGS
    state = Lexicon.default().__getstate__()
    # a release whose index lacked `dr`
    state["_base"] = tuple(e for e in READINGS if e[0] != "dr")
    older = Lexicon.__new__(Lexicon)
    older.__setstate__(state)
    assert older._base != "default" and older != Lexicon.default()
    assert "dr" not in older._sets.titles
    # bare: written `Dr.`, H2's shape reads a title whatever is listed
    assert Parser(lexicon=older).parse("Dr John Smith").title == ""
    assert pickle.loads(pickle.dumps(older)) == older


def test_a_snapshot_of_a_kind_this_release_does_not_know_is_refused() -> None:
    state = Lexicon.default().__getstate__()
    state["_base"] = (("zzq", (("en", "regnal", ()),)),)
    with pytest.raises(ValueError, match="kind 'regnal'"):
        Lexicon.__new__(Lexicon).__setstate__(state)


_UNSET = object()


def _mark(monkeypatch: pytest.MonkeyPatch, name: str,
          default: object = _UNSET) -> None:
    """Give a shipped Lexicon field the `_ADDED_IN` marker, as a field
    added in a later release would carry, and optionally another
    default. Patches the Field object `dataclasses.fields` returns, so
    only the pickle guard sees it."""
    f = Lexicon.__dataclass_fields__[name]
    monkeypatch.setattr(f, "metadata",
                        MappingProxyType({**f.metadata, _ADDED_IN: "9.9"}))
    if default is not _UNSET:
        monkeypatch.setattr(f, "default", default)


def _lexicon_state(*without: str, **renamed: str) -> dict[str, object]:
    state = Lexicon.default().__getstate__()
    for name in without:
        del state[name]
    for old, new in renamed.items():
        state[new] = state.pop(old)
    return state


#: (field marked, what loads in its place, the refusal the same state
#: meets with the field unmarked). The third column is the negative
#: control: the guard before it learned the marker refused exactly
#: this, so a widening that stopped working fails the admitted half.
_ADMITTED = [
    ("given_names", frozenset(),
     "missing fields: given_names; unexpected fields: none"),
    ("capitalization_exceptions", (),
     "missing fields: capitalization_exceptions; unexpected fields: none"),
]


@pytest.mark.parametrize("name,loaded,unmarked", _ADMITTED,
                         ids=[row[0] for row in _ADMITTED])
def test_setstate_admits_a_marked_field_missing_from_an_older_pickle(
        monkeypatch: pytest.MonkeyPatch, name: str, loaded: object,
        unmarked: str) -> None:
    state = _lexicon_state(name)
    with pytest.raises(ValueError, match=re.escape(unmarked)):
        Lexicon.__new__(Lexicon).__setstate__(dict(state))
    _mark(monkeypatch, name)
    restored = Lexicon.__new__(Lexicon)
    restored.__setstate__(dict(state))
    assert getattr(restored, name) == loaded
    assert restored == dataclasses.replace(Lexicon.default(), **{name: loaded})  # type: ignore[arg-type]
    assert restored.capitalization_exceptions_map == dict(
        restored.capitalization_exceptions)


#: (marks, state, refusal): every skew the guard refused before it
#: learned the marker, still refused beside a marked field, the rows of
#: tests/v2/test_types.py's _REFUSED_SKEWS for the shared guard.
_LEXICON_REFUSED = [
    pytest.param({"given_names": _UNSET}, lambda: _lexicon_state("surnames"),
                 "missing fields: surnames; unexpected fields: none",
                 id="missing-unmarked-field"),
    pytest.param({"given_names": _UNSET},
                 lambda: _lexicon_state("surnames", "given_names"),
                 "missing fields: surnames; unexpected fields: none",
                 id="missing-unmarked-field-beside-a-missing-marked-one"),
    pytest.param({"given_names": _UNSET},
                 lambda: {**_lexicon_state(), "zq_future": frozenset()},
                 "missing fields: none; unexpected fields: zq_future",
                 id="unexpected-field"),
    pytest.param({"given_names": _UNSET},
                 lambda: {**_lexicon_state("given_names"),
                          "zq_future": frozenset()},
                 "missing fields: none; unexpected fields: zq_future",
                 id="unexpected-field-beside-a-missing-marked-one"),
    pytest.param({"given_names": _UNSET},
                 lambda: _lexicon_state(_edits="edits"),
                 "missing fields: _edits; unexpected fields: edits",
                 id="renamed-field"),
    pytest.param({"given_names": _UNSET},
                 lambda: _lexicon_state(given_names="given_name"),
                 "missing fields: none; unexpected fields: given_name",
                 id="renamed-marked-field"),
    # a marker with no default to load is no license: the field is
    # still required, as in the shared guard
    pytest.param({"given_names": dataclasses.MISSING},
                 lambda: _lexicon_state("given_names"),
                 "missing fields: given_names; unexpected fields: none",
                 id="marked-field-without-a-default"),
    # the default is validated like a value the pickle held: one that
    # does not survive normalization is refused, not silently rewritten
    pytest.param({"surnames": frozenset({"DR."})},
                 lambda: _lexicon_state("surnames"),
                 "default is not normalized (surnames: DR.)",
                 id="marked-field-whose-default-is-not-normalized"),
]


@pytest.mark.parametrize("marks,state,match", _LEXICON_REFUSED)
def test_setstate_still_refuses_every_skew_beside_a_marked_field(
        monkeypatch: pytest.MonkeyPatch, marks: dict[str, object],
        state: Callable[[], dict[str, object]], match: str) -> None:
    for name, default in marks.items():
        _mark(monkeypatch, name, default)
    with pytest.raises(ValueError, match=re.escape(match)):
        Lexicon.__new__(Lexicon).__setstate__(state())


def test_unpickling_rejects_unnormalized_entries() -> None:
    # a genuine pickle always holds normalized entries, so state that
    # does not is foreign: say so, at the site that can name the entry
    state = Lexicon(surnames={"kim"}).__getstate__()
    state["surnames"] = {"Kim ", "LEE."}
    with pytest.raises(ValueError, match="not normalized"):
        Lexicon.__new__(Lexicon).__setstate__(state)
    state = Lexicon(capitalization_exceptions=(("phd", "PhD"),)).__getstate__()
    state["capitalization_exceptions"] = ((" PhD. ", "Ph.D."), ("aa", "AA"))
    with pytest.raises(ValueError, match="not normalized"):
        Lexicon.__new__(Lexicon).__setstate__(state)
    state = Lexicon.empty().add("dr", kind="title").__getstate__()
    state["_edits"] = (("add", ("DR.",), "title", ()),)
    with pytest.raises(ValueError, match="canonical"):
        Lexicon.__new__(Lexicon).__setstate__(state)


#: The refusals of a 2.x Lexicon state, each remedy matched in full:
#: a layout 3.0 loaded (2.7's and 2.8's), and an older one.
_REFUSED_2X = re.escape(
    "this Lexicon was pickled by nameparser 2.7 or 2.8, which 3.1 no "
    "longer loads: load the pickle under 3.0 and pickle the loaded object "
    "(the Lexicon, or the Parser or locale pack holding it) again; if 3.0 "
    "refuses the pickle too, build the object again")


def _refused_older(missing: str, unexpected: str = "none") -> str:
    """The refusal of a 2.x layout 3.0 never loaded, naming its keys."""
    return re.escape(
        f"this Lexicon was pickled by nameparser 2.x in a layout no 3.x "
        f"release loads (missing: {missing}; unexpected: {unexpected}), as "
        f"2.6 and earlier wrote: build the object (the Lexicon, or the "
        f"Parser or locale pack holding it) again")

#: The fields a 2.6.0 Lexicon state lacks against 2.8's, read off the
#: ValueError 3.0.1 raised loading `Lexicon.default()` pickled by the
#: 2.6.0 wheel (2026-11-08), sorted as the refusal lists them.
_NOT_IN_2_6 = ("agnomens", "given_name_abbreviations",
               "suffix_words_ambiguous", "title_modifiers", "title_phrases",
               "title_styles", "titles_ambiguous")


def _state_2_8() -> dict[str, object]:
    """A bare 2.8 Lexicon state: the layout 3.0 loaded, as recorded."""
    state: dict[str, object] = {f: frozenset() for f in _LAYOUT_3_0_LOADED}
    state["capitalization_exceptions"] = ()
    return state


def test_a_lexicon_parser_and_locale_pickled_by_2_8_0_are_refused() -> None:
    """tests/v2/data/lexicon_v28.pickle is a dict of
    `Lexicon.empty().add(titles={"dean"})`, a `Parser` holding it and
    `locales.RU`, pickled (protocol 4) by the released 2.8.0 wheel.
    Made 2026-10-30 with `PYTHONSAFEPATH=1 uv run --isolated
    --no-project --with 'nameparser==2.8.0'` from a directory outside
    the checkout, version and module path asserted (AGENTS.md's v1
    comparison trap). pickle.load is safe here: a repo-controlled
    fixture.

    3.0 translated a 2.x state's compiled sets onto readings and
    warned; 3.1 refuses it, naming the remedy (decisions/
    vocabulary-model, 2026-11-08 #1003). A Parser and a Locale load
    their Lexicon through the same __setstate__, so the dict is refused
    at the first one it reaches."""
    data = (Path(__file__).parent / "data" / "lexicon_v28.pickle").read_bytes()
    with pytest.raises(ValueError, match=_REFUSED_2X):
        pickle.loads(data)  # noqa: S301 -- our own fixture
    # a 2.x state alone, and one holding given_names, which 3.0 admitted
    for state in (_state_2_8(), {**_state_2_8(), "given_names": frozenset()}):
        with pytest.raises(ValueError, match=_REFUSED_2X):
            Lexicon.__new__(Lexicon).__setstate__(state)


def test_a_2_8_pickle_is_still_told_to_re_pickle_after_a_field_joins(
        monkeypatch: pytest.MonkeyPatch) -> None:
    # the 2.7/2.8 layout is a record, not the current roster: a field a
    # later release adds to _VOCAB_FIELDS is one no 2.8 pickle holds
    from nameparser import _lexicon
    monkeypatch.setattr(_lexicon, "_VOCAB_FIELDS",
                        (*_lexicon._VOCAB_FIELDS, "later_words"))
    data = (Path(__file__).parent / "data" / "lexicon_v28.pickle").read_bytes()
    with pytest.raises(ValueError, match=_REFUSED_2X):
        pickle.loads(data)  # noqa: S301 -- our own fixture
    with pytest.raises(ValueError, match=_REFUSED_2X):
        Lexicon.__new__(Lexicon).__setstate__(_state_2_8())


def test_a_lexicon_pickled_by_2_6_0_is_told_to_rebuild() -> None:
    """tests/v2/data/lexicon_v26.pickle is `Lexicon.empty()` pickled
    (protocol 4) by the released 2.6.0 wheel, made 2026-11-08 as
    lexicon_v28.pickle was, version and module path asserted. 3.0
    refused it, so re-pickling under 3.0 cannot help: the refusal says
    to build the object again and names the keys that differ."""
    data = (Path(__file__).parent / "data" / "lexicon_v26.pickle").read_bytes()
    with pytest.raises(ValueError,
                       match=_refused_older(", ".join(_NOT_IN_2_6))):
        pickle.loads(data)  # noqa: S301 -- our own fixture


def test_a_layout_off_by_one_key_is_named_by_that_key() -> None:
    # neither 2.7's nor 2.8's layout: named by what differs, never
    # credited to a release
    for drop, add, missing, unexpected in [
            ("titles_ambiguous", None, "titles_ambiguous", "none"),
            (None, "no_such_field", "none", "no_such_field")]:
        state = _state_2_8()
        if drop:
            del state[drop]
        if add:
            state[add] = frozenset()
        with pytest.raises(ValueError,
                           match=_refused_older(missing, unexpected)):
            Lexicon.__new__(Lexicon).__setstate__(state)


@pytest.mark.parametrize("obj", [
    Lexicon.default().remove("dean", kind="given"),
    Parser(lexicon=Lexicon.default().add("leed", kind="credential")),
    locales.RU,
], ids=["lexicon", "parser", "locale"])
def test_a_3x_pickle_is_not_mistaken_for_a_2x_one(obj: object) -> None:
    # the 2.x check (`"titles" in state`) reads a key no 3.x state
    # holds: an object pickled by this release loads, equal and with no
    # warning
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        again = pickle.loads(pickle.dumps(obj))  # noqa: S301
    assert caught == []
    assert again == obj


def test_a_pickle_written_by_3_0_does_not_warn() -> None:
    with open(Path(__file__).parent / "data" / "parsers_4ib.pickle",
              "rb") as f, warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        pickle.load(f)  # noqa: S301 -- our own fixture
    built = Lexicon.default().remove("dean", kind="given")
    with warnings.catch_warnings(record=True) as also:
        warnings.simplefilter("always")
        pickle.loads(pickle.dumps(Parser(lexicon=built)))
    assert caught == also == []


# -- the refusals no other test reaches ----------------

@pytest.mark.parametrize(("call", "error", "match"), [
    (lambda: Lexicon(surnames={"."}), ValueError, "normalizes to empty"),
    (lambda: Lexicon.empty().add("x", kind="office", attaches=5), TypeError, "attaches must be an iterable"),
    (lambda: Lexicon.empty().add("x", kind="office", attaches=["a", 5]), TypeError, "attaches entries must be strings"),
    (lambda: Lexicon(_edits=(("add", "x", "title", ()),)), TypeError, "words are a tuple"),  # type: ignore[arg-type]
    (lambda: Lexicon(_edits=(("remove", ("x",), "title", (("a", 1),)),)), ValueError, "remove\\(\\) takes no properties"),  # type: ignore[arg-type]
    (lambda: Lexicon(_edits=(("add", ("x",), "title", 5),)), TypeError, "properties are pairs"),  # type: ignore[arg-type]
    (lambda: Lexicon(_edits=5), TypeError, "_edits must be a tuple"),  # type: ignore[arg-type]
    (lambda: Lexicon(_base=5), TypeError, "base is 'default', 'empty'"),
    (lambda: Lexicon(_base=(("x", ("bad",)),)), TypeError, "snapshot is \\(word, rows\\)"),
    (lambda: Lexicon(_base=(("x", (("en", ["title"], ()),)),)), TypeError, "the tag and the kind strings"),
    (lambda: Lexicon(_base=(("x", ((3, "title", ()),)),)), TypeError, "the tag and the kind strings"),
    (lambda: Lexicon(_base=(("x", (("en", "title", (("attaches", ["a"]),)),)),)), TypeError, "a value is a string"),
    (lambda: Lexicon(_base=(("x", (("en", "title", (("nonsense", 1),)),)),)), ValueError, "the property 'nonsense'"),
    (lambda: Lexicon(_base=(("x", (("en", "given", (("addresses", "given"),)),)),)), ValueError, "the property 'addresses'"),
    (lambda: Lexicon(_base=(("x", (("en", "title", ("bad",)),)),)), TypeError, "has the row"),
    (lambda: LexiconReading(5, "title", "title"), TypeError, "text must be a string"),  # type: ignore[arg-type]
    (lambda: Lexicon.default().readings_of(5), TypeError, "takes a word"),  # type: ignore[arg-type]
])
def test_a_malformed_argument_is_refused_by_name(
        call: Callable[[], object], error: type[Exception], match: str) -> None:
    with pytest.raises(error, match=match):
        call()


def test_union_with_a_non_lexicon_is_not_implemented() -> None:
    assert Lexicon.empty().__or__(5) is NotImplemented  # type: ignore[operator]


def test_a_2x_spelling_with_a_malformed_value_still_says_since_3_0() -> None:
    with pytest.raises(TypeError, match="since 3.0"):
        Lexicon.default().add(titles=5)  # type: ignore[call-arg]


def _migrate_constant_rows() -> list[tuple[str, str]]:
    """docs/migrate.rst's "Vocabulary constants → Lexicon.words" rows
    whose replacement is code: (constant, expression); none outside a
    layout without the user docs, where the test is skipped."""
    if not HAS_DOCS:
        return []
    text = (Path(__file__).parents[2] / "docs" / "migrate.rst").read_text()
    section = text.split("Vocabulary constants → Lexicon.words\n", 1)[1]
    section = section.split("\n.. doctest::", 1)[0]
    rows = re.findall(r"   \* - ``([A-Z_]+)``\n     - ``(.+?)``\n", section)
    return rows


@needs_docs
@pytest.mark.parametrize(("constant", "expression"), _migrate_constant_rows())
def test_migrate_s_words_call_reproduces_each_2x_constant(
        constant: str, expression: str) -> None:
    # #1007: the migration table's code is run, so a row that stops
    # matching the compiled set it replaces fails here, not in a caller's
    # upgrade. KOREAN_SURNAMES, nameparser.config.surnames' through 2.x
    # (2.8.2 warning of the move), is the one not compiled
    from nameparser.config import _compiled, _ko_surnames
    d = Lexicon.default()
    got = eval(expression, {"d": d})  # noqa: S307
    expected = (_ko_surnames.KOREAN_SURNAMES if constant == "KOREAN_SURNAMES"
                else getattr(_compiled, constant))
    if isinstance(expected, dict):
        assert got == expected
    else:
        assert set(got) == set(expected)


@needs_docs
def test_migrate_s_table_has_a_row_for_every_refused_field() -> None:
    # a 2.x set field's refusal points at this table and names no call,
    # so the row is the whole remedy: a field without one is refused
    # with nowhere to go (#1003)
    text = (Path(__file__).parents[2] / "docs" / "migrate.rst").read_text()
    section = text.split("Lexicon fields → readings\n", 1)[1]
    end = "\nA ``Lexicon`` pickled by 2.x"
    assert end in section  # else the slice runs on to every later table
    section = section.split(end, 1)[0]
    rows = set(re.findall(r"^   \* - ``([a-z_]+)``$", section, re.M))
    assert set(_SET_FIELDS) <= rows, set(_SET_FIELDS) - rows


@needs_docs
def test_migrate_s_table_covers_every_compiled_constant() -> None:
    # every public 2.x constant has a row, code or prose: the private
    # sets 3.0 added (GENERATION_WORDS, ..., TITLE_CASE_NAME_WORDS) were
    # never public
    text = (Path(__file__).parents[2] / "docs" / "migrate.rst").read_text()
    section = text.split("Vocabulary constants → Lexicon.words\n", 1)[1]
    section = section.split("\n.. doctest::", 1)[0]
    # a row per constant, its own first cell: the two-constant row alone
    # once let TITLES pass with no answer of its own
    named = {c for c, _ in _migrate_constant_rows()} | {
        "TITLE_PHRASES", "CAPITALIZATION_EXCEPTIONS"} & set(
            re.findall(r"   \* - ``([A-Z_]+)``\n", section))
    from nameparser.config import _compiled
    public_in_2x = {n for n in vars(_compiled) if n.isupper()} - {
        "GENERATION_WORDS", "CREDENTIAL_WORDS", "HONORIFIC_WORDS",
        "PATRONYMIC_PARTICLES", "TITLE_ABBREVIATIONS", "TITLE_CASE_NAME_WORDS",
        "SHARED_NAMES", "PARTICLE_GIVEN_NAMES", "SAINT_PARTICLES",
        "CAPITALIZED_PARTICLES", "CAPITAL_OPENING_PARTICLES", "DOTTED_TITLES",
        "GLUED_TITLES",
        "BOUND_PHRASES", "SAME_AS", "SAME_AS_NAMED", "FAMILIAR"}
    assert public_in_2x <= named
    assert len(_migrate_constant_rows()) >= 20  # the rows with code
    # the one row naming two constants, which the row pattern skips
    assert '``TITLES`` and ``TITLES_AMBIGUOUS``, together\n     - ``d.words(kind="title")``' in section
    assert set(Lexicon.default().words(kind="title")) == (
        _compiled.TITLES | _compiled.TITLES_AMBIGUOUS)


@pytest.mark.parametrize(("edit", "text", "field", "value"), [
    # a caller marks another title that may be a given name written
    # short, and H5's chain takes it with its period, as it takes 'Maj.'
    (lambda d: d.add("dean", kind="office", abbreviation=True),
     "John Smith Dean.", "title", "Dean."),
    (lambda d: d.add("dean", kind="office", abbreviation=True),
     "Smith, abdul Dean.", "title", "Dean."),
    # and turns the shipped mark off, the word ending the name a name
    # word again, as a title that may be a given name is (rules/H9)
    (lambda d: d.add("maj", kind="military", abbreviation=False),
     "John Smith Maj.", "family", "Maj."),
])
def test_abbreviation_is_a_callers_switch_on_the_trailing_title(
        edit: Callable[[Lexicon], Lexicon], text: str, field: str,
        value: str) -> None:
    # rules/H5's written-short clause, reached by a caller's reading
    # (#999); the default reads each the other way
    lexicon = edit(Lexicon.default())
    assert getattr(Parser(lexicon=lexicon).parse(text), field) == value
    assert getattr(Parser().parse(text), field) != value
    loaded = pickle.loads(pickle.dumps(lexicon))
    assert getattr(Parser(lexicon=loaded).parse(text), field) == value


def test_a_generation_word_that_is_a_name_leans_by_case_only_when_told() -> None:
    # #1039: a gated generation word's writing says nothing unless its
    # reading is written title_case_is_name, as `fils`'s is: then Title
    # case is the name and lower case the suffix (rules/S6, S11)
    plain = Lexicon.default().add("zzgen", kind="family").add(
        "zzgen", kind="generation")
    cued = Lexicon.default().add("zzgen", kind="family").add(
        "zzgen", kind="generation", title_case_is_name=True)
    assert Parser(lexicon=plain).parse("John Smith Zzgen").suffix == "Zzgen"
    assert Parser(lexicon=cued).parse("John Smith Zzgen").family == "Zzgen"
    assert Parser(lexicon=cued).parse("John Smith zzgen").suffix == "zzgen"
    with pytest.raises(TypeError, match="title_case_is_name must be True or False"):
        Lexicon.default().add("zzgen", kind="generation",
                              title_case_is_name="yes")


def test_same_as_compiles_for_every_kind() -> None:
    lex = Lexicon.default()
    assert lex._headwords("junior", "suffix") & lex._headwords("jr", "suffix")
    assert lex._headwords("wm", "given") == {"wm", "william"}
    assert lex._headwords("Wm.", "given") == {"wm", "william"}
    assert lex._headwords("capt", "title") & lex._headwords("captain", "title")
    assert lex._headwords("smith", "family") == {"smith"}


def test_same_as_is_read_in_the_group_of_its_readings_kind() -> None:
    # a given name's listed spelling is not a surname's, nor a
    # generation's a given name's
    lex = Lexicon.default()
    assert lex._headwords("ma", "given") == {"ma", "maría"}
    assert lex._headwords("ma", "family") == {"ma"}
    assert lex._headwords("junior", "given") == {"junior"}


def test_every_same_as_a_word_carries_in_a_group_is_kept() -> None:
    # Spanish and Portuguese both list Sr as a salutation, each under its
    # own full form, and the default keeps both
    assert Lexicon.default()._headwords("sr", "title") == {
        "sr", "señor", "senhor"}


@pytest.mark.parametrize("strict", [False, True])
def test_same_as_follows_a_choice_of_languages(strict: bool) -> None:
    # a choice keeps its own file's full form
    from nameparser import locales
    pt = parser_for(locales.PT, strict=strict).lexicon
    es = parser_for(locales.ES, strict=strict).lexicon
    assert pt._headwords("Sr.", "title") == {"sr", "senhor"}
    assert es._headwords("Sr.", "title") == {"sr", "señor"}


def test_an_unedited_lexicons_built_same_as_is_the_defaults() -> None:
    from nameparser._lexicon import _built, _default_compiled
    built = _built("default", (), frozenset(), False)[2]
    assert dict(built) == dict(_default_compiled()[1]) == dict(
        Lexicon.default()._same_as)


def test_a_callers_same_as_on_a_title_reaches_the_map() -> None:
    lex = Lexicon.default().add("brgdr", kind="military", same_as="brigadier")
    assert lex._headwords("Brgdr.", "title") == {"brgdr", "brigadier"}
    assert lex._headwords("brgdr", "given") == {"brgdr"}
    assert Lexicon.default()._headwords("brgdr", "title") == {"brgdr"}


def test_a_same_as_loop_in_a_callers_edits_reaches_every_word_in_it() -> None:
    lex = (Lexicon.empty().add("aa", kind="military", same_as="bb")
           .add("bb", kind="military", same_as="aa"))
    assert lex._headwords("aa", "title") == lex._headwords("bb", "title") == {
        "aa", "bb"}


def test_the_lexicon_and_the_compiler_name_the_same_groups() -> None:
    import nameparser._reading_index as ri
    from nameparser._lexicon import _SAME_AS_GROUPS
    assert _SAME_AS_GROUPS == set(ri.SAME_AS_GROUPS.values())
    assert set(Lexicon.default()._same_as) == set(Lexicon.empty()._same_as) == (
        _SAME_AS_GROUPS)


def test_headwords_refuses_an_unknown_group() -> None:
    with pytest.raises(ValueError, match="group"):
        Lexicon.default()._headwords("wm", "name")


def test_same_as_does_not_move_which_set_a_word_compiles_into() -> None:
    lex = Lexicon.default().add("brgdr", kind="military", same_as="brigadier")
    assert "brgdr" in lex._sets.titles
    assert "wm" in lex._sets.given_name_abbreviations
    assert "capt" not in lex._sets.given_name_abbreviations
    assert "junior" not in lex._sets.given_name_abbreviations
