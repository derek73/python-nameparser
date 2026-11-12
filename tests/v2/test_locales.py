"""The locale pack layer (mechanisms.md#LOCALE-PACKS-PURE-DATA):
lazy access, the shipped
packs, composition, and the non-interference gate."""
import dataclasses
import functools
import importlib.util
import re
import sys
import types
import unicodedata
import warnings
from collections.abc import Callable, Iterable
from pathlib import Path
from types import ModuleType

import pytest

from nameparser import (
    Locale, ParsedName, Parser, locales, parse, parser_for,
)
from nameparser import _reading_index as _ri
from nameparser._lexicon import _VOCAB_FIELDS, Lexicon
from nameparser._policy import (
    FAMILY_FIRST, FAMILY_FIRST_GIVEN_LAST, UNSET, PatronymicRule, Policy,
    PolicyPatch, Script, _SCRIPT_RANGES,
)
from nameparser._types import AmbiguityKind, Role
from nameparser.locales import ja as _ja
from nameparser.locales import ru as _ru
from nameparser.locales import tr_az as _tr_az
from nameparser.locales import zh as _zh

from .conftest import differential_corpus

_CORPUS = differential_corpus()

# The registry is the pack contract (design note 2026-07-18, option C):
# the DEVIATES requirement, the rotator lists, and the non-interference
# gate below all iterate the registered packs, so adding a pack is one
# registry entry plus one rotator list -- the contract meta-test fails
# until both exist, instead of a human remembering to extend N tests.
def _pack_modules() -> dict[str, ModuleType]:
    out: dict[str, ModuleType] = {}
    for modname, attr in locales._REGISTRY.values():
        module = importlib.import_module(modname)
        out[getattr(module, attr).code] = module
    return out


_PACKS = _pack_modules()


def _is_vocabulary_pack(pack: Locale) -> bool:
    """Whether `pack` is nothing but its choice of languages, so that its
    deviation surface is derived (mechanisms.md#LOCALE-PACKS-PURE-DATA)."""
    return (bool(pack.languages) and pack.lexicon == Lexicon.empty()
            and pack.policy == PolicyPatch())



# ja is the one pack whose behavior is not pack data: it activates
# segmentation and supplies nothing to segment WITH, so every parse
# through it needs the optional nameparser[ja] segmenter. Probed once
# here; without the extra the ja code has no _PACKED entry, so every
# test that PARSES through the pack with a segmenter skips -- its
# segmentation rotator rows and its non-interference run included. What
# still runs either way is what needs no segmenter: the registry
# contract (DEVIATES and a rotator list exist), the range pin, the
# pack's contents, the inertness test below (the unsegmented pack's
# behavior on segmentation shapes) and the tests of its choice of 君.
_JA_AVAILABLE = importlib.util.find_spec("namedivider") is not None
_needs_ja = pytest.mark.skipif(not _JA_AVAILABLE, reason="needs nameparser[ja]")

# shared across the gate and rotator tests: the default-parser baseline
# is identical everywhere (only the packed side varies per test), so
# parse each name once for the whole module instead of once per test
_DEFAULT_PARSER = Parser()


def _packed_parsers() -> dict[str, Parser]:
    out: dict[str, Parser] = {}
    for code in _PACKS:
        if code != "ja":
            out[code] = parser_for(locales.get(code))
        elif _JA_AVAILABLE:
            out[code] = parser_for(
                locales.JA, segmenter=locales.ja_segmenter())
    return out


_PACKED = _packed_parsers()


def _require_packed(code: str) -> Parser:
    """The pack's parser, skipping the test when it needs an optional
    extra that is not installed (ja only, today)."""
    parser = _PACKED.get(code)
    if parser is None:
        pytest.skip(f"the {code!r} pack needs nameparser[{code}], "
                    f"which is not installed")
    return parser


@functools.cache
def _default_parse(name: str) -> dict:
    """Default-parser components for `name` (treat as read-only -- the
    dict is cached and shared across callers)."""
    return _DEFAULT_PARSER.parse(name).as_dict()


def test_locales_module_attribute_access() -> None:
    assert isinstance(locales.RU, Locale)
    assert locales.RU.code == "ru"
    assert locales.RU is locales.RU          # cached, not rebuilt


def test_locales_get_and_available() -> None:
    assert locales.get("ru") is locales.RU
    assert set(locales.available()) == {
        "bn", "cs", "es", "es_ar", "ga", "gd", "hi", "hr", "ja", "mn", "ne", "pt",
        "pt_br", "ru", "sk", "sl", "tr_az", "vi", "zh"}
    with pytest.raises(
            KeyError,
            match="bn, cs, es, es_ar, ga, gd, hi, hr, ja, mn, ne, pt, pt_br, ru, sk, sl, tr_az, vi, zh"):
        locales.get("xx")
    # the segmenter FACTORY is not a locale: it is an ordinary function
    # on the package, so it must not appear among the codes
    assert "ja_segmenter" not in locales.available()
    assert callable(locales.ja_segmenter)


def test_tr_az_pack_contents() -> None:
    assert locales.TR_AZ.code == "tr_az"
    assert locales.TR_AZ.policy.patronymic_rules == frozenset(
        {PatronymicRule.TURKIC})
    assert locales.TR_AZ.lexicon == Lexicon.empty()


def test_ne_pack_contents() -> None:
    # 3d: the first vocabulary pack; what the choice changes is exactly
    # the three given readings ne.toml writes `default = false`, each
    # also a title in another file. Since #1254 its [rules] turn
    # initials_as_family on (rules/O8)
    from nameparser._reading_index import changed_words, selected
    assert locales.NE == Locale(code="ne", lexicon=Lexicon.empty(),
                                policy=PolicyPatch(initials_as_family=True),
                                languages=frozenset({"ne"}))
    assert changed_words(selected(locales.NE.languages)) == {
        "guru", "गुरु", "श्री"}


@pytest.mark.parametrize("text", [
    "Ram Bahadur B K", "Ram Bahadur B. K.", "Anjana K C(Maharjan)",
    "Kalpana K C(Sunuwar)", "Bimala Kumari Singh (B. K.)", "Ram B K,Jr",
    "Ram B\u200bK", "Ram B\ufeffK", "Ram B\u2063K", "Ram B\u30fbK",
    "Ram B\u1361K", "Ram B\uff65K", "Ram E\u0301. K."])
def test_ne_declares_every_name_its_letters_rule_moves(text: str) -> None:
    # the #1347 review: words read by str.split() missed a name whose
    # letters the parse divides at a bracket, a glued comma, a
    # zero-width character or a word separator of another script
    from nameparser.locales import ne as _ne
    assert parser_for(locales.NE).parse(text).as_dict() != parse(
        text).as_dict()
    assert _ne.DEVIATES(text)


def test_ne_declares_no_name_without_two_single_letters_in_a_row() -> None:
    from nameparser.locales import ne as _ne
    assert not any(map(_ne.DEVIATES, (
        "Ram Bahadur Thapa", "Ram Bahadur BK", "Durga Kumari", "",
        # a vowel sign stays in its letter's run: read as a divider,
        # र and म would be two runs of one letter each
        "राम बहादुर थापा")))


def test_ne_reads_the_word_as_given_at_the_head_and_title_in_a_phrase() -> None:
    ne = _require_packed("ne")
    assert parse("श्री कृष्ण श्रेष्ठ").title == "श्री"
    assert (ne.parse("श्री कृष्ण श्रेष्ठ").given,
            ne.parse("श्री कृष्ण श्रेष्ठ").title) == ("श्री", "")
    # behind a listed title the word no longer joins the title run
    assert ne.parse("Mr. Guru Sharma").as_dict() == parse(
        "Mr. Guru Sharma").as_dict() | {
        "title": "Mr.", "given": "Guru", "family": "Sharma"}
    # the title reading stands: inside a title phrase (rules/H9) and
    # written with its period at the head (rules/H2's shape), still a title
    assert ne.parse("His Holiness Guru Prasad").title == "His Holiness Guru"
    assert ne.parse("Guru. Prasad Sharma").title == "Guru."


def test_hi_and_bn_pack_contents() -> None:
    # 3e: two vocabulary packs, nothing but their choices; what each
    # changes is exactly the romanized titles its file writes
    # `default = false`, words with no reading the default compiles
    from nameparser._reading_index import changed_words, selected
    assert locales.HI == Locale(code="hi", lexicon=Lexicon.empty(),
                                languages=frozenset({"hi"}))
    assert locales.BN == Locale(code="bn", lexicon=Lexicon.empty(),
                                languages=frozenset({"bn"}))
    assert changed_words(selected(locales.HI.languages)) == {
        "shrimati", "shriyut", "smt", "sushri"}
    assert changed_words(selected(locales.BN.languages)) == {
        "adhyapak", "shrimati", "smt"}


def test_hi_and_bn_read_the_romanized_salutation_as_the_title() -> None:
    hi, bn = _require_packed("hi"), _require_packed("bn")
    assert (parse("Smt Nirmala Sitharaman").title,
            parse("Smt Nirmala Sitharaman").given) == ("", "Smt")
    for packed in (hi, bn):
        name = packed.parse("Smt Nirmala Sitharaman")
        assert (name.title, name.given, name.family) == (
            "Smt", "Nirmala", "Sitharaman")
        assert packed.parse("Dr. Shrimati Indira Gandhi").title == (
            "Dr. Shrimati")
        # after a family comma, a salutation ending the given part is the
        # title (rules/H8), as its Devanagari spelling is
        assert packed.parse("Sitharaman, Nirmala Smt").title == "Smt"
        # shri is left out (decisions/vocabulary-model, phase 3e): the
        # given names written in two words that open with it keep it
        assert packed.parse("Shri Kant Tripathi").as_dict() == parse(
            "Shri Kant Tripathi").as_dict()
        assert packed.parse("Sushri Sangita Behera").given == "Sushri"
    # adhyapak is a title only at the head and only under bn; the Marathi
    # family name ending a name keeps its place
    assert bn.parse("Adhyapak Anisuzzaman Khan").title == "Adhyapak"
    assert bn.parse("Anoop Adhyapak").family == "Adhyapak"
    assert hi.parse("Adhyapak Anisuzzaman Khan").title == ""
    assert hi.parse("Shriyut Ram Prasad").title == "Shriyut"
    assert bn.parse("Shriyut Ram Prasad").title == ""


def test_sushri_is_the_title_only_under_a_strict_hindi_choice() -> None:
    # #345: hi.toml's sushri salutation is off by default and or.toml
    # declares the Odia given name, so the plain choice gates it (a title
    # only inside a title phrase, rules/H9) and a strict one, reading no
    # or.toml, reads it as the title
    plain = _require_packed("hi")
    strict = parser_for(locales.HI, strict=True)
    for text in ("Sushri Sangita Behera", "Behera, Sushri Sangita",
                 "Dr. Sushri Sangita Behera"):
        assert plain.parse(text).as_dict() == parse(text).as_dict(), text
        assert strict.parse(text).given == "Sangita", text
        assert "Sushri" in strict.parse(text).title, text
    assert plain.parse("Her Excellency Sushri Sangita Behera").title == (
        "Her Excellency Sushri")


@pytest.mark.parametrize("text, middle", [
    ("Maria de Fátima Costa", "de Fátima"),
    ("MARIA DE FATIMA COSTA", "DE FATIMA"),
    ("Maria do Socorro Silva", "do Socorro"),
    ("Maria de Lourdes Costa", "de Lourdes"),
    ("Ana de Maria Costa", "de Maria"),
])
def test_a_strict_portuguese_choice_reads_the_given_names_es_also_marks(
        text: str, middle: str) -> None:
    # #1122: pt.toml holds its own reading of the five words es.toml
    # marks that pass on Portuguese names under the strict choice
    # (fátima, fatima, socorro, lourdes, maria), so a strict choice
    # reading no es.toml keeps the default's middle name; the others
    # (carmen, pilar, rosario, ...) it leaves to the family
    assert parse(text).middle == middle
    for pack in (locales.PT, locales.PT_BR):
        assert parser_for(pack, strict=True).parse(text).middle == middle, pack


def test_es_and_pt_pack_contents() -> None:
    # 3g: es is its choice plus the Spanish given-name list as a lexicon
    # fragment (read by rules/O6 alone); pt is nothing but its choice
    from nameparser._reading_index import changed_words, selected
    from nameparser.locales import es as _es
    from nameparser.locales._es_given_names import GIVEN_NAMES
    assert locales.ES == Locale(code="es",
                                lexicon=Lexicon(given_names=GIVEN_NAMES),
                                policy=PolicyPatch(two_family_names=True),
                                languages=frozenset({"es"}))
    assert locales.PT == Locale(code="pt", lexicon=Lexicon.empty(),
                                languages=frozenset({"pt"}))
    # the titles with no name bearer are read by default since #1115, so
    # the choice changes only the words a collision keeps off
    assert changed_words(selected(locales.ES.languages)) == {
        "doña", "lady", "maestra"}
    # the given name a particle completes that changes too few names to
    # score, kept for pt's choice (#1118, #1122)
    assert changed_words(selected(locales.PT.languages)) == {
        "do", "e", "piedade"}
    # sr keeps es's and pt's generation beside the salutation, so the
    # choice leaves it a dual position decides, as the default reads it
    for packed in (_require_packed("es"), _require_packed("pt"),
                   _require_packed("pt_br")):
        for text in ("Gary Holloway Sr", "Sr. Juan Pérez", "J. Smith Sr."):
            assert packed.parse(text).as_dict() == parse(text).as_dict()
    # the patch's and the fragment's declaration: rules/O6's three name
    # words, each a run of letters whatever separates it
    assert _es.DEVIATES("José Luis Pérez") and _es.DEVIATES("Pérez, José Luis")
    assert _es.DEVIATES("Mary-\u200bJane Smith") and _es.DEVIATES("马丁·路德·金")
    assert not _es.DEVIATES("Pérez García")


def test_vi_pack_contents() -> None:
    # a choice of vi, its file's [rules] order, and a fragment that only
    # removes (decisions/vocabulary-model, the 2026-11-05 #1108 entry)
    from nameparser.locales import vi as _vi
    assert locales.VI.languages == {"vi"}
    assert locales.VI.policy.name_order is FAMILY_FIRST_GIVEN_LAST
    # ths and the office đbqh are read by default since #1115, its title
    # phrases with chief and deputy with it; gs, pgs and ts, written as
    # initials too, stay the choice's
    assert _ri.changed_words(_ri.selected(locales.VI.languages)) == {
        "gs", "pgs", "ts"}
    sets = _require_packed("vi").lexicon._sets
    # the fragment takes out the readings it names and nothing else
    assert not {"van", "le", "do", "du", "di", "la", "tho", "da", "san"} & (
        sets.particles)
    assert not {"the", "y"} & sets.conjunctions
    assert not {"do", "ba", "chi"} & sets.suffix_acronyms
    # mac stays (decisions/vocabulary-model, 2026-11-05 #1108)
    assert {"de", "von", "bin", "mac"} <= sets.particles
    # ma keeps its credential (decisions/vocabulary-model, 2026-11-05 #1108)
    assert "and" in sets.conjunctions and {"md", "bs", "ma"} <= sets.suffix_acronyms
    assert _vi.DEVIATES("Anh") and not _vi.DEVIATES(", ")


#: Each reading the VI fragment removes, with a name its removal alone
#: moves: a particle or connective standing between two name words,
#: which its reading would chain or join to its neighbours, and a
#: credential ending a name written in one case, which its reading
#: would take as the suffix
_VI_REMOVALS = [
    ("van", "particle", "Nguyen Van Anh"),
    ("le", "particle", "Nguyen Le Anh"),
    ("do", "particle", "Nguyen Do Anh"),
    ("du", "particle", "Nguyen Du Anh"),
    ("di", "particle", "Le Di Anh"),
    ("la", "particle", "Nguyen La Anh"),
    ("da", "particle", "Tran Da Anh"),
    ("tho", "particle", "Nguyen Tho Anh"),
    ("san", "particle", "Nguyen San Anh"),
    ("the", "conjunction", "Nguyen The Tuan"),
    ("y", "conjunction", "NGUYEN THI Y NHI"),
    ("do", "credential", "NGUYEN VAN DO"),
    ("ba", "credential", "NGUYEN THI BA"),
    ("chi", "credential", "NGUYEN LINH CHI"),
]


def test_each_vi_removal_moves_its_own_row() -> None:
    # the negative control for the fragment: with one removal put back,
    # the row that witnesses it reads otherwise, so every removal is
    # held by a reading and not only by the set assertions above
    from nameparser.locales import vi as _vi
    lists = {"particle": _vi._PARTICLES, "conjunction": _vi._CONJUNCTIONS,
             "credential": _vi._CREDENTIALS}
    assert sorted((w, k) for w, k, _ in _VI_REMOVALS) == sorted(
        (w, k) for k, words in lists.items() for w in words)
    vi = _require_packed("vi")

    def put_back(removal: tuple[str, str] | None) -> Parser:
        lexicon = Lexicon.empty()
        for k, words in lists.items():
            lexicon = lexicon.remove(
                *[w for w in words if (w, k) != removal], kind=k)
        return parser_for(dataclasses.replace(locales.VI, lexicon=lexicon))

    # the positive control: rebuilt with nothing put back, the pack
    # reads every row as VI does, so a difference below is the removal's
    rebuilt = put_back(None)
    for word, kind, text in _VI_REMOVALS:
        assert rebuilt.parse(text).as_dict() == vi.parse(text).as_dict(), text
        without = put_back((word, kind))
        assert without.parse(text).as_dict() != vi.parse(text).as_dict(), (
            word, kind, text)


@pytest.mark.parametrize("text, title, family, middle, given, suffix", [
    # the spelling sweep: unaccented, with diacritics, in one case
    ("Nguyen Van Anh", "", "Nguyen", "Van", "Anh", ""),
    ("Nguyễn Văn Anh", "", "Nguyễn", "Văn", "Anh", ""),
    ("NGUYỄN VĂN ANH", "", "NGUYỄN", "VĂN", "ANH", ""),
    ("nguyen van anh", "", "nguyen", "van", "anh", ""),
    # the order, with a syllable other files read as a particle at the
    # head, which the order reads alike without the fragment (Le Van Anh
    # moves by van's removal, its Le by the order)
    ("Le Van Anh", "", "Le", "Van", "Anh", ""),
    ("Lê Văn Anh", "", "Lê", "Văn", "Anh", ""),
    ("Do Thi Lan", "", "Do", "Thi", "Lan", ""),
    ("Đỗ Thị Lan", "", "Đỗ", "Thị", "Lan", ""),
    # the connective at the head, which chains without the fragment
    ("the Thi Lan", "", "the", "Thi", "Lan", ""),
    # each removal, the syllable between two name words (_VI_REMOVALS)
    ("Nguyen Le Anh", "", "Nguyen", "Le", "Anh", ""),
    ("Nguyen Do Anh", "", "Nguyen", "Do", "Anh", ""),
    ("Nguyen Du Anh", "", "Nguyen", "Du", "Anh", ""),
    ("Le Di Anh", "", "Le", "Di", "Anh", ""),
    ("Nguyen La Anh", "", "Nguyen", "La", "Anh", ""),
    ("Tran Da Anh", "", "Tran", "Da", "Anh", ""),
    ("Nguyen Tho Anh", "", "Nguyen", "Tho", "Anh", ""),
    ("Tran Thi San Ha", "", "Tran", "Thi San", "Ha", ""),
    ("Tran Van Le", "", "Tran", "Van", "Le", ""),
    ("Tran The Tuan", "", "Tran", "The", "Tuan", ""),
    ("Nguyen Thi y Nhi", "", "Nguyen", "Thi y", "Nhi", ""),
    ("NGUYEN THI Y NHI", "", "NGUYEN", "THI Y", "NHI", ""),
    # a capital Y in a mixed-case name is an initial by rules/P8 with or
    # without the fragment
    ("Nguyen Y Anh", "", "Nguyen", "Y", "Anh", ""),
    # the credentials, ending a name in one case, and in mixed case
    ("NGUYEN VAN DO", "", "NGUYEN", "VAN", "DO", ""),
    ("NGUYEN LINH CHI", "", "NGUYEN", "LINH", "CHI", ""),
    ("NGUYEN THI BA", "", "NGUYEN", "THI", "BA", ""),
    ("nguyen van do", "", "nguyen", "van", "do", ""),
    ("NGUYEN VAN DO, MD", "", "NGUYEN", "VAN", "DO", "MD"),
    ("Nguyen Linh Chi", "", "Nguyen", "Linh", "Chi", ""),
    ("Nguyen Van Do", "", "Nguyen", "Van", "Do", ""),
    # ma keeps its credential, so a name ending in it stays a known gap
    ("TRAN THI MA", "", "TRAN", "", "THI", "MA"),
    ("Nguyen Van Anh, MA", "", "Nguyen", "Van", "Anh", "MA"),
    # the accepted cost: DO or BA written as a credential after a
    # Vietnamese name for English-language readers reads as a name word,
    # with a comma or without, dotted, in brackets or behind another
    # credential, unless past a second comma; CHI only without a comma
    ("Nguyen Van Anh, DO", "", "Nguyen Van Anh", "", "DO", ""),
    ("Nguyen Van Anh DO", "", "Nguyen", "Van Anh", "DO", ""),
    # and dotted, rules/T7 parts it as the initials it is written as
    ("Nguyen Van Anh D.O.", "", "Nguyen", "Van Anh D.", "O.", ""),
    ("Nguyen Van Anh MD, DO", "", "Nguyen Van Anh", "", "DO", "MD"),
    ("Nguyen, Van Anh DO", "", "Nguyen", "Anh DO", "Van", ""),
    ("Nguyen, Van Anh, DO", "", "Nguyen", "Anh", "Van", "DO"),
    ("Nguyen Van Anh, BA", "", "Nguyen Van Anh", "", "BA", ""),
    # after a comma the capitals shape (rules/C6) keeps a three-letter
    # word in capitals a suffix, CHI's readings or none
    ("Nguyen Van Anh, CHI", "", "Nguyen", "Van", "Anh", "CHI"),
    # and the removals act after a family comma, where the order reads
    # nothing differently: a particle or a credential there is a name word
    ("Beethoven, Ludwig van", "", "Beethoven", "van", "Ludwig", ""),
    ("Smith, John Do", "", "Smith", "Do", "John", ""),
    # the titles at the head, bare, dotted and stacked
    ("Ts Nguyen Van Anh", "Ts", "Nguyen", "Van", "Anh", ""),
    ("TS NGUYEN VAN ANH", "TS", "NGUYEN", "VAN", "ANH", ""),
    ("ThS Nguyen Van Anh", "ThS", "Nguyen", "Van", "Anh", ""),
    ("PGS.TS. Nguyễn Văn Anh", "PGS.TS.", "Nguyễn", "Văn", "Anh", ""),
    ("GS.TS. Nguyen Van Anh", "GS.TS.", "Nguyen", "Van", "Anh", ""),
    ("PGS. TS. Nguyen Van Anh", "PGS. TS.", "Nguyen", "Van", "Anh", ""),
    ("PGS.TS.BS. Nguyen Van Anh", "PGS.TS.BS.", "Nguyen", "Van", "Anh", ""),
    ("ĐBQH Nguyễn Văn Anh", "ĐBQH", "Nguyễn", "Văn", "Anh", ""),
    ("đbqh Nguyen Van Anh", "đbqh", "Nguyen", "Van", "Anh", ""),
    ("DBQH Nguyen Van Anh", "DBQH", "Nguyen", "Van", "Anh", ""),
    # a stacked title ending a name is the title: rules/H5's chain takes
    # a word written with a period inside it (#1116), where the default
    # reads suffix 'PGS.TS.' by rules/S3's unlisted dotted suffix
    ("Nguyen Van Anh PGS.TS.", "PGS.TS.", "Nguyen", "Van", "Anh", ""),
    # bs has no title reading in vi.toml, so en's credential stays and a
    # dotted BS. opening a name is a title by shape (rules/H2)
    ("BS. Nguyen Van An", "BS.", "Nguyen", "Van", "An", ""),
    ("Smith, John BS", "", "Smith", "", "John", "BS"),
    # the comma shapes: a suffix comma, a family comma, a full name and
    # a title before one, an empty head, nothing after the comma
    ("Nguyen Van Anh, PhD", "", "Nguyen", "Van", "Anh", "PhD"),
    ("Nguyen Van Anh, Ts", "Ts", "Nguyen", "Van", "Anh", ""),
    ("Nguyen Van Anh, PGS.TS.", "PGS.TS.", "Nguyen", "Van", "Anh", ""),
    ("Nguyen, Van Anh", "", "Nguyen", "Anh", "Van", ""),
    ("Nguyen, Van Anh, Jr.", "", "Nguyen", "Anh", "Van", "Jr."),
    ("Nguyen, Ts Van Anh", "Ts", "Nguyen", "Anh", "Van", ""),
    ("Nguyen Van, Anh", "", "Nguyen Van", "", "Anh", ""),
    ("Ts Nguyen, Van Anh", "Ts", "Nguyen", "Anh", "Van", ""),
    ("ĐBQH Nguyen, Van Anh", "ĐBQH", "Nguyen", "Anh", "Van", ""),
    (", Van Anh", "", "", "Anh", "Van", ""),
    (", Ts Van Anh", "Ts", "", "Anh", "Van", ""),
    # a title and one name word read the word as the family (rules/H1)
    (", PGS.TS. Anh", "PGS.TS.", "Anh", "", "", ""),
    # a one-word name reads as Policy.lone_name_word names, given by
    # default, whatever the order (rules/O5, #1111)
    ("Van,", "", "", "", "Van", ""),
    ("Anh", "", "", "", "Anh", ""),
])
def test_vi_reads_a_vietnamese_name_family_first_with_its_syllables(
        text: str, title: str, family: str, middle: str, given: str,
        suffix: str) -> None:
    got = _require_packed("vi").parse(text)
    assert (got.title, got.family, got.middle, got.given, got.suffix) == (
        title, family, middle, given, suffix)


def test_vi_reads_a_mixed_case_credential_syllable_as_a_name_unreported() -> None:
    # in mixed case the credential removal moves only the report: the
    # name word is read alike, and the suffix-or-name fork is gone
    from nameparser.locales import vi as _vi
    vi = _require_packed("vi")
    kept = parser_for(dataclasses.replace(locales.VI, lexicon=(
        Lexicon.empty().remove(*_vi._PARTICLES, kind="particle")
        .remove(*_vi._CONJUNCTIONS, kind="conjunction"))))
    for text in ("Nguyen Linh Chi", "Nguyen Van Do", "Nguyen Thi Ba"):
        assert not vi.parse(text).ambiguities, text
        assert vi.parse(text).as_dict() == kept.parse(text).as_dict(), text
        assert {a.kind for a in kept.parse(text).ambiguities} == {
            AmbiguityKind.SUFFIX_OR_NAME}, text


def test_vi_differs_from_the_default_where_the_default_reads_given_first() -> None:
    # the plain-vs-default contrast: a plain vi choice, no strict mode
    vi = _require_packed("vi")
    for text in ("Nguyen Van Anh", "Lê Văn Anh", "Tran The Tuan"):
        assert vi.parse(text).as_dict() != _default_parse(text)
    assert parse("Nguyen Van Anh").given == "Nguyen"
    assert parse("Tran The Tuan").given == "Tran The Tuan"
    # a family comma fixes the family name, so it reads alike
    for text in ("Nguyen, Van Anh", "Smith, John"):
        assert vi.parse(text).as_dict() == _default_parse(text)


def test_mn_pack_contents() -> None:
    # a choice of mn and a Cyrillic script order, nothing else: the
    # order is keyed to the script, so a romanized name keeps the
    # caller's (decisions/vocabulary-model, the 2026-11-12 #1237 entry)
    from nameparser.locales import mn as _mn
    assert locales.MN == Locale(
        code="mn", lexicon=Lexicon.empty(),
        policy=PolicyPatch(
            script_orders=((Script.CYRILLIC, FAMILY_FIRST_GIVEN_LAST),)),
        languages=frozenset({"mn"}))
    assert _mn.DEVIATES("Сүхээ") and _mn.DEVIATES("Dr. Сүхээ")
    assert not _mn.DEVIATES("Bataagiin Suhee") and not _mn.DEVIATES(", ")


#: The father's name is the family under the pack (#1253's first
#: statement), in each form a Cyrillic name is written in; the default
#: reads each given-first. (text, family, middle, given)
_MN_READINGS = [
    ("Батын Сүхээ", "Батын", "", "Сүхээ"),
    ("Бат Сүхээ", "Бат", "", "Сүхээ"),
    ("БАТЫН СҮХЭЭ", "БАТЫН", "", "СҮХЭЭ"),
    ("Дорждэрэмийн Ганбаатар", "Дорждэрэмийн", "", "Ганбаатар"),
    ("Б. Сүхээ", "Б.", "", "Сүхээ"),
    ("Ц.Сандаг-Очир", "Ц.", "", "Сандаг-Очир"),   # glued (#1306), rules/T8
    # a hyphen or an apostrophe inside a Cyrillic word keeps it Cyrillic
    ("Цэрэн Оюун-Эрдэнэ", "Цэрэн", "", "Оюун-Эрдэнэ"),
    ("Оюун-Эрдэнэ Цэрэн", "Оюун-Эрдэнэ", "", "Цэрэн"),
    ("Мар'яна Сидоренко", "Мар'яна", "", "Сидоренко"),
    # a word before the father's name (a clan name, not read as one,
    # #1237) leaves the given name last
    ("Боржигин Батын Сүхээ", "Боржигин", "Батын", "Сүхээ"),
    ("Батын Дорж Сүхээ Болд", "Батын", "Дорж Сүхээ", "Болд"),
    # titles and suffixes stand aside, in either script: the name words
    # decide the script
    ("Др. Батын Сүхээ", "Батын", "", "Сүхээ"),
    ("Dr. Батын Сүхээ", "Батын", "", "Сүхээ"),
    ("Lama Батын Сүхээ", "Батын", "", "Сүхээ"),   # mn.toml's title
    ("Батын Сүхээ Jr.", "Батын", "", "Сүхээ"),
    ("Батын Сүхээ, PhD", "Батын", "", "Сүхээ"),
    # the given name and the father's initial written given first read
    # backwards in Cyrillic, an accepted cost (decisions/vocabulary-model)
    ("Сүхээ Б.", "Сүхээ", "", "Б."),
    # CLDR's sample title Ноён is no listed title
    ("Ноён Азжаргал Төмөр", "Ноён", "Азжаргал", "Төмөр"),
]


@pytest.mark.parametrize("text, family, middle, given", _MN_READINGS)
def test_mn_reads_the_fathers_name_as_the_family(
        text: str, family: str, middle: str, given: str) -> None:
    got = _require_packed("mn").parse(text)
    assert (got.family, got.middle, got.given) == (family, middle, given)
    assert parse(text).family != family


_MN_DECOMPOSED = [
    (unicodedata.normalize("NFD", t), unicodedata.normalize("NFD", f),
     m, unicodedata.normalize("NFD", g))
    for t, f, m, g in _MN_READINGS if t != unicodedata.normalize("NFD", t)]


def test_mn_decomposed_rows_exist() -> None:
    # an empty parametrize skips rather than fails
    assert len(_MN_DECOMPOSED) >= 1


@pytest.mark.parametrize("text, family, middle, given", _MN_DECOMPOSED)
def test_mn_reads_a_decomposed_name_alike(
        text: str, family: str, middle: str, given: str) -> None:
    # Cyrillic ү and ө have no decomposition, so the row written with й
    # is the one NFD reaches: the classified copy is composed first
    got = _require_packed("mn").parse(text)
    assert (got.family, got.middle, got.given) == (family, middle, given)


@pytest.mark.parametrize("text", [
    "Батын, Сүхээ",       # a family comma fixes the family name
    "Сүхээ, Батын",       # whichever word stands before it
    ", Сүхээ",            # nothing before the comma
    "Сүхээ",              # one word: given, the caller's setting (rules/O5)
    "Батын, Сүхээ Болд",
    "Батын, Др. Сүхээ",
    "Батын Сүхээ, Болд",  # a full name before the comma, one word after
    "Батын, Сүхээ, Jr.",
    "Др. Сүхээ",
    "Сүхээ Jr.",
    "Батын,",
    # a name not wholly Cyrillic keeps the caller's order: romanized,
    # mixed, or in the traditional script (whose default order
    # decisions/T6 leaves open)
    "Batyn Sükhee",
    # a joiner at an edge is no word-inner joiner: the word is no
    # Cyrillic word (#1237)
    "-Батын Сүхээ",
    "'Батын Сүхээ",
    "Батын- Сүхээ",
    "Батын' Сүхээ",
    # a non-ASCII Latin word with a hyphen is no Cyrillic word
    "Jürgen Müller-Lüdenscheid",
    "BATAAGIIN SUHEE",
    "Bataagiin Suhee, PhD",
    "Uyanga B.",
    "Батын Sükhee",
    "ᠪᠠᠲᠤ\u202fᠶᠢᠨ ᠰᠦᠬᠡ",
    # Han, Hangul and kana keep their own entries
    "山田 太郎",
    "김 민준",
])
def test_mn_reads_as_the_default_where_its_order_does_not_reach(
        text: str) -> None:
    assert _require_packed("mn").parse(text).as_dict() == _default_parse(text)


def test_mn_lone_word_follows_the_callers_switch() -> None:
    # the pack's order is a declaration, not a script that settles the
    # order (rules/W4), so a lone word is rules/O5's: given and
    # reported by default, family where the caller says so
    lone = _require_packed("mn").parse("Сүхээ")
    assert lone.given == "Сүхээ"
    assert [a.kind for a in lone.ambiguities] == [AmbiguityKind.GIVEN_OR_FAMILY]
    family_lone = parser_for(locales.MN, base=Parser(
        policy=Policy(lone_name_word=Role.FAMILY)))
    assert family_lone.parse("Сүхээ").family == "Сүхээ"
    assert family_lone.parse("Батын Сүхээ").family == "Батын"


def test_mn_order_composes_with_the_callers_script_orders() -> None:
    # the pack adds its Cyrillic entry and keeps the caller's own table:
    # an opt-out of the East Asian entries stands
    opted_out = parser_for(locales.MN, base=Parser(policy=Policy(script_orders=())))
    assert dict(opted_out.policy.script_orders) == {
        Script.CYRILLIC: FAMILY_FIRST_GIVEN_LAST}
    assert opted_out.parse("山田 太郎").given == "山田"
    assert opted_out.parse("Батын Сүхээ").family == "Батын"
    # and a declared family-first order still reaches a romanized name
    family_first = parser_for(locales.MN, base=Parser(
        policy=Policy(name_order=FAMILY_FIRST)))
    assert family_first.parse("Batyn Sükhee").family == "Batyn"


def test_mn_strict_reads_its_file_and_the_shared_vocabulary() -> None:
    # the choice is what a strict parser reads: mn.toml's lama stays a
    # title, en.toml's Sir is no title (so it is a Latin name word and
    # the name is no longer wholly Cyrillic), and the order still holds
    strict = parser_for(locales.MN, strict=True)
    assert strict.parse("Lama Батын Сүхээ").title == "Lama"
    assert strict.parse("Sir Батын Сүхээ").title == ""
    assert _require_packed("mn").parse("Sir Батын Сүхээ").title == "Sir"
    assert strict.parse("Батын Сүхээ").family == "Батын"


def test_mn_fills_no_patronymic() -> None:
    # the genitive is not read (#1237): the father's name is the family,
    # and the patronymic view stays rules/R9's
    for text, *_ in _MN_READINGS:
        assert _require_packed("mn").parse(text).patronymic == "", text


def test_cs_and_sk_pack_contents() -> None:
    # 3f, amended 2026-10-30: cs and sk are their choice plus rules/O6's
    # patch, no fragment; sl and hr stay nothing but their choice
    from nameparser._locale import deviates_by_two_family_names
    from nameparser.locales import cs as _cs, es as _es, sk as _sk
    for code, pack in (("cs", locales.CS), ("sk", locales.SK)):
        assert pack == Locale(code=code, lexicon=Lexicon.empty(),
                              policy=PolicyPatch(two_family_names=True),
                              languages=frozenset({code})), code
    for code in ("sl", "hr"):
        assert _is_vocabulary_pack(locales.get(code)), code
    # the patch's declaration is rules/O6's, one predicate for the three
    # packs that turn O6 on, so their declarations cannot drift apart
    for module in (_cs, _sk, _es):
        for name in ("Alena Pešová Řehořová", "Novák, Petr Pavel",
                     "Mária-\u200bJana Kováčová", "Jan Novák", "Novák"):
            assert module.DEVIATES(name) == deviates_by_two_family_names(name)
    assert _cs.DEVIATES("Petr Pavel Novák") and not _cs.DEVIATES("Pešová Řehořová")
    # a word the tokenizer splits beside a word of no letter is three
    # name words (the #973 review: these moved undeclared under all three)
    for name in ("김민준 1", "Jan\u200bPavel -"):
        assert deviates_by_two_family_names(name), name


# rules/O6's declaration counts a run opening with a classified character twice
# (_locale._letter_runs), and since #1087 "classified" is the script
# table's, the one W1 divides by. Each row: the name, its declaration,
# and the declaration under the two definitions it replaced, recorded
# 2026-11-05 and re-taken live below -- the character-name test the
# function used before #1087, and the table with HANGUL at the
# precomposed syllables alone, which would have cost the decomposed
# names their declaration (the gate's unsafe direction).
_TWICE_COUNTED = [
    (unicodedata.normalize("NFD", "김. 민준"), True, True, False),
    (unicodedata.normalize("NFD", "김 민준"), True, True, False),
    ("ﾔﾏﾀﾞ ﾀﾛｳ", True, False, True),
    ("ﾀﾅｶ. John", True, False, True),
    ("ﾀﾛｳ·ﾔﾏﾀﾞ", True, False, True),
    ("김 민준", True, True, True),
    ("ꥠᅡ Kim", True, True, False),    # Extended-A
    ("ힰ Kim", True, True, False),      # Extended-B
    ("Pérez García", False, False, False),
    ("Ли Ли", False, False, False),     # Cyrillic, in the table since #1237, is no run

    # the narrowing: compatibility jamo and the katakana phonetic
    # extensions were counted twice by name and are counted once now,
    # being in no range W1 divides (the test below shows the packs
    # read them as the default does)
    ("ㄱㄴ ㄷㄹ", False, True, False),
    ("ㇰㇱ ㇲ", False, True, False),
]


def _by_character_name(ch: str) -> bool:
    return unicodedata.name(ch, "").startswith(
        ("CJK", "HANGUL", "HIRAGANA", "KATAKANA"))


@pytest.mark.parametrize(("name", "declared", "by_name", "by_syllables"),
                         _TWICE_COUNTED)
def test_the_two_family_names_declaration_counts_by_the_script_table(
        monkeypatch: pytest.MonkeyPatch, name: str, declared: bool,
        by_name: bool, by_syllables: bool) -> None:
    from nameparser import _locale, _policy
    assert _locale.deviates_by_two_family_names(name) is declared
    monkeypatch.setattr(_locale, "_classified_char", _by_character_name)
    assert _locale.deviates_by_two_family_names(name) is by_name
    # the table before #1087, built by the shipped factory
    monkeypatch.setitem(_policy._SCRIPT_RANGES, Script.HANGUL,
                        (_policy._HANGUL_SYLLABLES,))
    monkeypatch.setattr(_locale, "_classified_char", _policy._script_matcher(
        *_policy._EAST_ASIAN_SCRIPTS, whole=True))
    assert _locale.deviates_by_two_family_names(name) is by_syllables


def test_the_twice_counted_controls_each_move_a_row() -> None:
    assert any(row[1] != row[2] for row in _TWICE_COUNTED)
    assert any(row[1] != row[3] for row in _TWICE_COUNTED)
    assert _NARROWED  # an empty parametrize would skip the parity test


_NARROWED = [name for name, declared, by_name, _ in _TWICE_COUNTED
             if by_name and not declared]


@pytest.mark.parametrize("name", _NARROWED)
@pytest.mark.parametrize("code", ["es", "es_ar", "cs", "sk"])
def test_a_name_the_declaration_stopped_counting_twice_reads_as_the_default(
        code: str, name: str) -> None:
    assert _require_packed(code).parse(name).as_dict() == _default_parse(name)


def test_es_and_pt_read_a_leading_title_and_leave_don_a_given_name() -> None:
    es, pt = _require_packed("es"), _require_packed("pt")
    # doña stays the choice's; lic, licenciada and mtro are read by
    # default since #1115, so the default reads them as the pack does
    assert parse("Doña María Pérez").title == ""
    assert es.parse("Doña María Pérez").title == "Doña"
    for text, title in (("Lic Juan Pérez", "Lic"), ("LIC JUAN PEREZ", "LIC"),
                        ("Pérez, Licenciada Ana", "Licenciada"),
                        ("Mtro. Pérez, Edgar", "Mtro.")):
        assert parse(text).title == es.parse(text).title == title
    assert es.parse("Ana López Maestra.").as_dict() == parse(
        "Ana López Maestra.").as_dict() | {
        "title": "Maestra.", "middle": "", "family": "López"}
    assert pt.parse("Fernanda Lucchese, Doutora").as_dict() == parse(
        "Fernanda Lucchese, Doutora").as_dict()
    assert parse("Fernanda Lucchese, Doutora").title == "Doutora"
    # don, dona and dom are excluded: names open with them as given names
    for packed, text in ((es, "Don Juan Pérez"), (pt, "Dona Maria Souza"),
                         (pt, "Dom Pedro Alves")):
        assert packed.parse(text).as_dict() == parse(text).as_dict()
    # no title-run connective (decisions/vocabulary-model, phase 3g): a
    # particle behind the title starts the family, as by default
    assert es.parse("Doctora de la Vega").family == "de la Vega"
    # the pack reads two family names, its list keeping a listed given
    # name out of the family (rules/O6); a compound given name stays opt-in
    assert es.parse("Gabriel García Márquez").family == "García Márquez"
    assert parse("Gabriel García Márquez").family == "Márquez"
    assert es.parse("José Luis Pérez").as_dict() == parse(
        "José Luis Pérez").as_dict()
    assert es.parse("Juan Carlos Pérez García").as_dict() == parse(
        "Juan Carlos Pérez García").as_dict() | {
        "middle": "Carlos", "family": "Pérez García"}
    assert pt.parse("João Pedro Silva Santos").as_dict() == parse(
        "João Pedro Silva Santos").as_dict()


def test_zh_pack_contents() -> None:
    assert locales.ZH.code == "zh"
    # the pack activates Han segmentation and ships vocabulary --
    # and does NOT touch order: script_orders already reads Han
    # family-first by default (amendment 2026-07-27)
    assert locales.ZH.policy.segment_scripts == frozenset({Script.HAN})
    assert locales.ZH.policy.name_order is UNSET
    assert locales.ZH.policy.script_orders is UNSET
    assert "王" in locales.ZH.lexicon.surnames
    assert "欧阳" in locales.ZH.lexicon.surnames       # compound
    assert "歐陽" in locales.ZH.lexicon.surnames       # traditional
    assert _zh.DEVIATES("毛泽东")
    assert _zh.DEVIATES("𠮷田")   # astral Han declared
    assert not _zh.DEVIATES("John Smith")
    assert not _zh.DEVIATES("김민준")   # HAN alone, not a wider union


def test_zh_surname_entries_are_wellformed() -> None:
    # structural integrity, not content-pinning: 1-2 chars each,
    # every char in the stage's own Han ranges (catches a stray
    # Latin char, a pasted full name, or a hangul entry)
    ranges = _SCRIPT_RANGES[Script.HAN]
    for entry in locales.ZH.lexicon.surnames:
        assert 1 <= len(entry) <= 2, entry
        assert all(any(lo <= ord(c) <= hi for lo, hi in ranges)
                   for c in entry), entry


def test_zh_parses_unspaced_names() -> None:
    p = _PACKED["zh"]
    n = p.parse("毛泽东")
    assert (n.family, n.given) == ("毛", "泽东")
    n = p.parse("欧阳修")                      # compound + 1-char given
    assert (n.family, n.given) == ("欧阳", "修")
    n = p.parse("司马相如")                    # compound + 2-char given
    assert (n.family, n.given) == ("司马", "相如")
    # the 肖/萧 census merger ships both simplified spellings
    n = p.parse("萧红")
    assert (n.family, n.given) == ("萧", "红")


def test_zh_longest_match_prefers_compound_over_single_surname() -> None:
    # The longest-first tie-break, exercised by the PACK's own data
    # rather than by the synthetic lexicon the stage tests use. Most
    # compounds here begin with a character that is not itself a listed
    # surname (欧, 司, 诸 are all outside the top-100), so they would
    # split the same way under shortest-first and prove nothing. 夏侯 is
    # one of only three compounds that would not -- 夏 is rank 65 -- so
    # this is the pair that shows the shipped data actually reaches the
    # tie-break.
    p = _PACKED["zh"]
    n = p.parse("夏侯惇")
    assert (n.family, n.given) == ("夏侯", "惇")
    n = p.parse("夏雨")                        # the single-surname foil
    assert (n.family, n.given) == ("夏", "雨")
    # ...and the ambiguity contract on that same data: a decided fork
    # is REPORTED (first Han coverage of the SEGMENTATION emitter --
    # the stage tests reach it through a synthetic lexicon, and the
    # default lexicon can only reach it through hangul), while the
    # foil, where only one split was ever possible, stays silent.
    assert [a.kind for a in p.parse("夏侯惇").ambiguities] == [
        AmbiguityKind.SEGMENTATION]
    assert p.parse("夏雨").ambiguities == ()


# 毛泽东/欧阳修/夏侯惇/萧红 appear in _ROTATORS["zh"] below, and 毛泽东/
# 夏侯惇 in cases.py's zh rows, as well. Not deduplicated in either
# direction, on purpose: the rotator tests assert only THAT the packed
# parse differs from the default and that DEVIATES declares it -- they
# never look at a field value -- and the case rows reach the same
# packed parser only through the shared-table runners
# (test_cases.py). These tests are where the zh
# readings are pinned at unit level, against the stage directly.


def test_zh_composes_with_korean_defaults() -> None:
    # the pack only ADDS (vocabulary + one union field): Korean
    # segmentation keeps working through a zh parser
    n = _PACKED["zh"].parse("김민준")
    assert (n.family, n.given) == ("김", "민준")


def test_honorific_spellings_agree_where_the_vocabulary_divides() -> None:
    # east-asian.rst says a SPACED honorific is how you keep a family name
    # whole. That holds only where a SEGMENTER divides it -- the ja
    # tests below pin that half -- because the segmenter's precondition
    # counts any neighbour and a spaced honorific is one. The
    # VOCABULARY has no such precondition: the peel (#308) hands it the
    # same remainder whichever way the honorific was written, so the
    # two spellings agree exactly. Pinned in both scripts because the
    # reader's escape hatch differs -- the zh pack can be declined,
    # hangul segmentation is a DEFAULT and cannot, so a Korean-data
    # reader has no lever at all here.
    ko = _DEFAULT_PARSER.parse("김민준 씨")
    assert (ko.family, ko.given, ko.suffix) == ("김", "민준", "씨")
    assert _DEFAULT_PARSER.parse("김민준씨").as_dict() == ko.as_dict()
    zh = _PACKED["zh"].parse("王小明 先生")
    assert (zh.family, zh.given, zh.suffix) == ("王", "小明", "先生")
    assert _PACKED["zh"].parse("王小明先生").as_dict() == zh.as_dict()


def test_ja_pack_contents() -> None:
    assert locales.JA.code == "ja"
    assert locales.JA.languages == frozenset({"ja"})
    # segmentation activation plus the choice of ja (君): no vocabulary
    # of its own (no list settles a kanji name) and no order (the kana license already reads
    # Japanese family-first by default, decisions/W4)
    assert locales.JA.policy.segment_scripts == frozenset(
        {Script.HAN, Script.HIRAGANA})
    assert locales.JA.policy.name_order is UNSET
    assert locales.JA.policy.script_orders is UNSET
    assert locales.JA.lexicon == Lexicon.empty()
    assert _ja.DEVIATES("山田太郎")
    assert _ja.DEVIATES("𠮷田")   # astral Han declared
    # katakana declared (see the pack's repertoire note)
    assert _ja.DEVIATES("マイケル")
    assert _ja.DEVIATES("みなみ")   # hiragana declared
    assert not _ja.DEVIATES("John Smith")
    assert not _ja.DEVIATES("김민준")   # the three JA scripts, not a wider union


def test_ja_choice_reads_kun_as_an_honorific_and_the_default_does_not() -> None:
    # #1194: 君 is the Diet's honorific, but 王君 is a complete Chinese
    # name, so only a Japanese choice reads it; くん ships everywhere
    with pytest.warns(UserWarning, match="ja_segmenter"):
        ja = parser_for(locales.JA)
    for text in ("逢沢　一郎君", "逢沢　一郎　君"):
        n = ja.parse(text)
        assert (n.family, n.given, n.middle, n.suffix) == (
            "逢沢", "一郎", "", "君"), text
        assert parse(text).suffix == "", text
    assert parse("王君").family == "王君"
    assert parse("山田　太郎くん").suffix == "くん"
    # the accepted cost: a Chinese name ending in it loses it under JA
    assert (ja.parse("陳怡君").family, ja.parse("陳怡君").suffix) == ("陳怡", "君")
    # a 君 that is not final stays in the name
    assert ja.parse("山田　君子").given == "君子"


def test_ja_strict_choice_keeps_only_japanese_and_shared_vocabulary() -> None:
    # #1194: JA chooses a language, so strict=True builds where it used
    # to raise "chooses none", and drops the Latin vocabulary
    with pytest.warns(UserWarning, match="ja_segmenter"):
        strict = parser_for(locales.JA, strict=True)
    assert strict.parse("逢沢　一郎君").suffix == "君"
    assert parse("Sir John Smith").title == "Sir"
    assert strict.parse("Sir John Smith").title == ""


def test_ja_segmenter_without_extra_raises_helpfully() -> None:
    if _JA_AVAILABLE:
        pytest.skip("namedivider installed; the error path is untestable")
    with pytest.raises(ImportError, match=r"nameparser\[ja\]"):
        locales.ja_segmenter()


class _FakeDivided:
    """The shape of namedivider's DividedName, minus namedivider —
    lets the adapter's guard stack run in the plain (no-extra) suite,
    including the two defensive branches the real 0.4.x library can
    never reach (reconstruction failure, an empty side)."""

    def __init__(self, family: str, given: str, score: float) -> None:
        self.family, self.given, self.score = family, given, score


def _fake_namedivider(monkeypatch: pytest.MonkeyPatch,
                      divide: "Callable[[str], _FakeDivided]") -> list[str]:
    """Install a stub namedivider module and return the gbdt-call log
    (empty unless GBDTNameDivider was constructed)."""
    constructed: list[str] = []

    class _Basic:
        def __init__(self) -> None:
            constructed.append("basic")

        def divide_name(self, text: str) -> _FakeDivided:
            return divide(text)

    class _GBDT(_Basic):
        def __init__(self) -> None:
            constructed.append("gbdt")

    stub = types.ModuleType("namedivider")
    stub.BasicNameDivider = _Basic  # type: ignore[attr-defined]
    stub.GBDTNameDivider = _GBDT  # type: ignore[attr-defined]
    monkeypatch.setitem(sys.modules, "namedivider", stub)
    return constructed


def test_ja_adapter_guard_stack_against_a_stub(
        monkeypatch: pytest.MonkeyPatch) -> None:
    # The adapter's whole contract without the extra: this is what the
    # coverage-bearing CI job sees, so the guards are pinned here and
    # not only behind the nameparser[ja] integration tests.
    divide = _fake_namedivider(
        monkeypatch, lambda text: _FakeDivided(text[:2], text[2:], 0.5))
    seg = locales.ja_segmenter()
    assert divide == ["basic"]
    answer = seg("山田太郎")
    assert answer is not None
    assert answer.splits == (2,) and answer.confidence == 0.5
    assert seg("김민준") is None            # outside the repertoire
    # contains JA chars but is not WHOLLY JA
    assert seg("Yamada太郎") is None
    assert seg("林") is None                # namedivider raises below 2
    # halfwidth kana is katakana, so a Han+halfwidth token is wholly
    # Japanese and reaches the divider (#594)
    assert seg("山田ﾀﾛｳ") is not None


def test_ja_adapter_declines_shime_tokens(
        monkeypatch: pytest.MonkeyPatch) -> None:
    # Since U+3006 classifies as Han, 〆木太郎 is wholly Japanese and
    # reaches the adapter, but the divider is never consulted for 〆
    # tokens -- see the decline comment in ja.py for the measured
    # mis-cut it prevents.
    calls: list[str] = []

    def divide(text: str) -> _FakeDivided:
        calls.append(text)
        return _FakeDivided(text[:1], text[1:], 1.0)

    _fake_namedivider(monkeypatch, divide)
    assert locales.ja_segmenter()("〆木太郎") is None
    assert calls == []          # the decline sits before divide_name


@pytest.mark.parametrize("text", ["あいさわいちろう", "なかやめぐ", "さくらエミ"])
def test_ja_adapter_declines_a_token_with_no_kanji(
        monkeypatch: pytest.MonkeyPatch, text: str) -> None:
    # #1193: namedivider reads kanji statistics, and a token with none
    # comes back cut after its first character, so the adapter declines
    # before divide_name; a token holding a kanji still reaches it
    calls: list[str] = []

    def divide(name: str) -> _FakeDivided:
        calls.append(name)
        return _FakeDivided(name[:1], name[1:], 0.2)

    _fake_namedivider(monkeypatch, divide)
    seg = locales.ja_segmenter()
    assert seg(text) is None
    assert calls == []
    assert seg("山田たろう") is not None
    assert calls == ["山田たろう"]


def test_ja_adapter_defensive_branches_against_a_stub(
        monkeypatch: pytest.MonkeyPatch) -> None:
    # reconstruction failure -> decline; an empty side -> the stated
    # "confidently undivided" opinion; a score a hair over 1 -> clamped,
    # so Segmentation's [0, 1] validation cannot raise mid-parse
    _fake_namedivider(
        monkeypatch, lambda text: _FakeDivided("外", "れ", 0.5))
    assert locales.ja_segmenter()("山田太郎") is None
    _fake_namedivider(
        monkeypatch, lambda text: _FakeDivided(text, "", 1.0000001))
    whole = locales.ja_segmenter()("山田太郎")
    assert whole is not None
    assert whole.splits == () and whole.confidence == 1.0


def test_ja_adapter_declines_a_garbage_score(
        monkeypatch: pytest.MonkeyPatch) -> None:
    # The other half of the score handling, and the half the old
    # unconditional clamp got wrong: float noise at the edge of a
    # softmax is arithmetic around a real answer and clamps (above),
    # but 87.0 is not noise -- a divider scoring that is broken, and
    # its DIVISION is worth no more than its score. Clamping mapped it
    # to 1.0, i.e. "certain", which silenced the SEGMENTATION report at
    # exactly the point of maximum brokenness. Declining leaves the
    # token whole: safe, and observable by the report's absence.
    _fake_namedivider(
        monkeypatch, lambda text: _FakeDivided(text[:2], text[2:], 87.0))
    assert locales.ja_segmenter()("山田太郎") is None
    _fake_namedivider(
        monkeypatch, lambda text: _FakeDivided(text[:2], text[2:], -0.5))
    assert locales.ja_segmenter()("山田太郎") is None


def test_ja_adapter_declines_a_nan_score(
        monkeypatch: pytest.MonkeyPatch) -> None:
    # NaN takes the garbage-score exit for free rather than needing one
    # of its own: every comparison against NaN is False, so it fails
    # BOTH bounds of the epsilon band. Worth a test precisely because
    # it is a property of the comparison rather than a written branch
    # -- under the old clamp, min/max propagated it straight into
    # Segmentation, whose own range check would then have raised
    # mid-parse.
    _fake_namedivider(
        monkeypatch,
        lambda text: _FakeDivided(text[:2], text[2:], float("nan")))
    assert locales.ja_segmenter()("山田太郎") is None


def test_ja_adapter_gbdt_flag_selects_the_gbdt_divider(
        monkeypatch: pytest.MonkeyPatch) -> None:
    divide = _fake_namedivider(
        monkeypatch, lambda text: _FakeDivided(text[:1], text[1:], 1.0))
    locales.ja_segmenter(gbdt=True)
    assert divide == ["gbdt"]


def test_ja_pack_alone_is_inert() -> None:
    # The pack's own claim, and the reason it is safe to register
    # without the extra: activating segmentation while shipping nothing
    # to segment WITH changes no parse of a segmentation shape. Pure pack data, so this
    # runs whether or not nameparser[ja] is installed -- and the choice
    # rows (君) are the pack's one other observable behavior.
    # construction now SAYS the pack alone cannot divide anything --
    # the segmenterless-activation warning is the loud half of this
    # test's claim, and the inert parses below are the quiet half
    with pytest.warns(UserWarning, match="ja_segmenter"):
        p = parser_for(locales.JA)
    for name in _JA_SEGMENTATION_ROTATORS:
        assert p.parse(name).as_dict() == _default_parse(name), name


@_needs_ja
def test_ja_end_to_end() -> None:
    p = _PACKED["ja"]
    n = p.parse("山田太郎")
    assert (n.family, n.given) == ("山田", "太郎")
    # the case a zh surname list corrupts (高 + 橋一郎), done right
    n = p.parse("高橋一郎")
    assert (n.family, n.given) == ("高橋", "一郎")
    # kana-licensed composite: gated in through the HIRAGANA entry
    n = p.parse("高橋みなみ")
    assert (n.family, n.given) == ("高橋", "みなみ")
    # the iteration mark 々 gates in as Han (Script=Han under UAX #24,
    # but outside the ideograph blocks the classifier spans, so it
    # rides in on a singleton range entry) and namedivider reads the
    # repeated character correctly -- verified against 0.4.1 rather
    # than assumed, since a divider could plausibly have choked on it
    # or cut beside it
    n = p.parse("佐々木健")
    assert (n.family, n.given) == ("佐々木", "健")


@_needs_ja
def test_ja_keeps_a_transcribed_name_in_its_source_order() -> None:
    # pure katakana is excluded from the pack's activation by design
    # (rule W4's boundary: katakana is how Japanese writes FOREIGN
    # names), so
    # the nakaguro form divides on the dot and keeps its given-first
    # source order instead of being read family-first
    n = _PACKED["ja"].parse("マイケル・ジャクソン")
    assert (n.given, n.family) == ("マイケル", "ジャクソン")


@_needs_ja
def test_ja_composes_with_zh() -> None:
    # vocabulary first, segmenter on decline (rule W1)
    p = parser_for(locales.ZH, locales.JA, segmenter=locales.ja_segmenter())
    assert p.parse("毛泽东").family == "毛"      # zh surname wins
    assert p.parse("山田太郎").family == "山田"   # zh declines, segmenter
    # ...and a Korean name still splits on the default vocabulary,
    # never reaching the segmenter (which would decline it anyway)
    assert p.parse("김민준").family == "김"


@_needs_ja
def test_ja_segmenter_declines_what_it_cannot_read() -> None:
    # The adapter's repertoire guard, which only a token that actually
    # REACHES the adapter can pin: a listed Korean surname is split by
    # the vocabulary first (the second case below), so this hangul
    # deliberately opens with a syllable no surname list carries. It
    # gates in on script, declines vocabulary, and reaches the adapter,
    # which must decline it rather than let namedivider divide Korean
    # -- without the guard it comes back as family 쿄 carrying a bogus
    # SEGMENTATION report.
    p = _PACKED["ja"]
    n = p.parse("쿄쿄쿄")
    assert (n.family, n.given) == ("쿄쿄쿄", "")
    assert n.ambiguities == ()
    # ...and the vocabulary-wins case, which never reaches the adapter
    assert p.parse("김민준").family == "김"


@_needs_ja
def test_ja_segmenter_declines_a_lone_character() -> None:
    # namedivider RAISES below two characters, and a segmenter's
    # exceptions propagate by contract, so the adapter's length guard
    # is what keeps this parse total. It takes a LONE token to reach:
    # in "林 太郎" the stage's precondition stops the segmenter first.
    p = _PACKED["ja"]
    n = p.parse("林")
    assert (n.family, n.given) == ("林", "")
    assert n.ambiguities == ()


@_needs_ja
@pytest.mark.parametrize(("text", "family", "given"), [
    ("あいさわいちろう", "あいさわいちろう", ""),
    ("なかやめぐ", "なかやめぐ", ""),
    ("山田たろう", "山田", "たろう"),
    ("あいさわ　いちろう", "あいさわ", "いちろう"),
])
def test_ja_leaves_a_name_with_no_kanji_whole(
        text: str, family: str, given: str) -> None:
    # #1193, through the real divider: a hiragana name stays whole, as
    # it does with the pack and no segmenter, where namedivider cut it
    # after its first character with a SEGMENTATION report; a kanji
    # still reaches the divider, and a written space still divides
    n = _PACKED["ja"].parse(text)
    assert (n.family, n.given) == (family, given)
    assert n.ambiguities == ()


@_needs_ja
def test_ja_leaves_spaced_names_to_the_default_order() -> None:
    # the segmenter's precondition (see test_parser.py): a spaced name
    # is already divided, and the kana/Han family-first defaults read
    # it correctly with no segmenter involved. Without this the pack
    # would wreck the commonest written form -- 山田 + 太郎 divided
    # again into 山 + 田 + 太郎.
    p = _PACKED["ja"]
    for name in ("山田 太郎", "高橋 みなみ", "高橋 エミ", "山田 太郎 Jr.",
                 "山田 太郎 様"):
        assert p.parse(name).as_dict() == _default_parse(name), name
    assert p.parse("山田 太郎").family == "山田"


@_needs_ja
def test_ja_divides_a_glued_name_carrying_an_honorific() -> None:
    # #308 end to end, with the real divider: the honorific peels off
    # first, so namedivider is handed 山田太郎 rather than 山田太郎様
    # -- which it would have divided somewhere wrong, answering for
    # any string it is given. GLUED only: the writer of 山田太郎様 drew
    # no boundary anywhere, so the tail the peel manufactured is none
    # either and the consult goes ahead.
    p = _PACKED["ja"]
    n = p.parse("山田太郎様")
    assert (n.family, n.given, n.suffix) == ("山田", "太郎", "様")
    # the kana-licensed composite too, whose division is rule-based
    n = p.parse("高橋みなみ様")
    assert (n.family, n.given, n.suffix) == ("高橋", "みなみ", "様")
    # and the spaced spelling is left alone, honorific and all: its
    # writer wrote 山田太郎 as a unit, which the pack respects the way
    # it respects "山田 太郎"
    n = p.parse("山田太郎 様")
    assert (n.family, n.given, n.suffix) == ("山田太郎", "", "様")


@_needs_ja
def test_ja_does_not_divide_a_spaced_surname_under_an_honorific() -> None:
    # A spaced honorific is a neighbour, and the segmenter is asked
    # only where an UNDIVIDED name divides, so it is never consulted
    # here. Only a tail this stage MANUFACTURED is exempt -- a glued
    # honorific means no boundary was typed anywhere, a spaced one
    # means one was, and by position a spaced honorific cannot be told
    # apart from a spaced name element besides.
    # The bare control is what makes any of that load-bearing: without
    # it the assertions pass vacuously, for any reason at all that the
    # segmenter went unconsulted. Each family name here DOES divide
    # standing alone, so the honorific is what stopped it -- and these
    # four are the measured price of counting spaced honorifics, paid
    # to decline the one division 山田太郎 様 (the test above).
    p = _PACKED["ja"]
    for name, family, divided in (("佐藤 氏", "佐藤", ("佐", "藤")),
                                  ("田中 様", "田中", ("田", "中")),
                                  ("鈴木 先生", "鈴木", ("鈴", "木")),
                                  ("中村 教授", "中村", ("中", "村"))):
        n = p.parse(name)
        assert (n.family, n.given) == (family, ""), name
        bare = p.parse(family)
        assert (bare.family, bare.given) == divided, family


@_needs_ja
def test_ja_divides_a_two_character_name_under_a_glued_honorific() -> None:
    # The consequence of the rule above on the commonest addressed
    # form, pinned so it is a recorded decision rather than a side
    # effect: with the peeled tail not blocking the consult, a
    # two-character remainder reaches namedivider, which divides it
    # one character each way BY RULE (score 1.0, so no SEGMENTATION
    # report). That is the same presumption locales/ja.py already
    # documents and test_ja_reports_statistical_divisions... pins for
    # 原恵 -- 田中さん is simply the shortest route to it. A caller
    # who wants 田中 kept whole is asking not to have unspaced names
    # divided, which is what declining the pack means -- or can write
    # the honorific spaced, which the test above pins.
    n = _PACKED["ja"].parse("田中さん")
    assert (n.family, n.given, n.suffix) == ("田", "中", "さん")
    assert n.ambiguities == ()      # rule-based, so nothing to report
    # the spaced twin, for the contrast in one place
    n = _PACKED["ja"].parse("田中 さん")
    assert (n.family, n.given, n.suffix) == ("田中", "", "さん")


@_needs_ja
def test_ja_reports_statistical_divisions_and_not_rule_based_ones() -> None:
    # the confidence floor's measured consequence (_script_segment.py's
    # constant): namedivider scores a rule-based division 1.0 and a
    # kanji-statistics division far below the floor, so the ambiguity
    # report separates exactly those two epistemic states
    p = _PACKED["ja"]
    assert [a.kind for a in p.parse("山田太郎").ambiguities] == [
        AmbiguityKind.SEGMENTATION]
    assert p.parse("高橋みなみ").ambiguities == ()     # kana boundary rule
    assert p.parse("原恵").ambiguities == ()          # two-character rule


@_needs_ja
def test_ja_leaves_a_lone_hiragana_token_whole() -> None:
    # The whole-name presumption no longer reaches hiragana: until #1193
    # the stage gated みなみ in and namedivider cut it み + なみ with a
    # SEGMENTATION report, wrong where the writer meant the given name
    # alone. A token with no kanji now declines at the adapter, so it
    # reads as the pack with no segmenter reads it, the lone name word
    # a family. The kanji version of the presumption (田中 -> 田 + 中)
    # still stands, namedivider having kanji to read there.
    n = _PACKED["ja"].parse("みなみ")
    assert (n.family, n.given) == ("みなみ", "")
    assert n.ambiguities == ()


@_needs_ja
def test_ja_divides_an_astral_kanji_name() -> None:
    # 𠮷 (U+20BB7, the "tsuchiyoshi" 吉) is a real surname character in
    # the supplementary plane -- the reason _SCRIPT_RANGES carries the
    # astral Han span at all. It has to survive the whole chain as one
    # character and not two: the script gate, the adapter's repertoire
    # guard, namedivider itself, and the offset arithmetic that turns
    # the answer into spans (Python indexes by codepoint, so an offset
    # of 2 here spans four UTF-16 units -- a surrogate-pair bug would
    # land the split in the middle of the character).
    n = _PACKED["ja"].parse("𠮷田太郎")
    assert (n.family, n.given) == ("𠮷田", "太郎")
    assert [a.kind for a in n.ambiguities] == [AmbiguityKind.SEGMENTATION]


@_needs_ja
def test_namedivider_still_miscuts_shime_names() -> None:
    # The canary behind the adapter's 〆 decline: when this fails,
    # namedivider learned the mark -- revisit the decline in ja.py
    # rather than deleting this test.
    import namedivider
    result = namedivider.BasicNameDivider().divide_name("〆木太郎")
    assert (result.family, result.given) == ("〆", "木太郎")
    assert float(result.score) == 1.0


@_needs_ja
def test_ja_stacked_on_zh_pays_the_zh_packs_documented_cost() -> None:
    # Stacking composes MECHANICALLY (the test above) but not for free,
    # and this pins the cost so it stays a documented trade rather than
    # a bug report. Vocabulary runs first, so a Japanese kanji name
    # opening on a listed CHINESE surname never reaches the segmenter:
    # 高 is a common Chinese surname, so 高橋一郎 splits 高 + 橋一郎
    # under ZH+JA exactly as it does under ZH alone -- the same reading
    # cases.py's zh_japanese_kanji_tradeoff row records, and the reason
    # the docs call the two packs corpus alternatives and qualify the
    # stack (see _script_segment.py's module docstring, east-asian.rst and
    # the release log). JA alone reads it correctly (test_ja_end_to_end).
    p = parser_for(locales.ZH, locales.JA, segmenter=locales.ja_segmenter())
    n = p.parse("高橋一郎")
    assert (n.family, n.given) == ("高", "橋一郎")
    # and silently: one vocabulary match is not a fork, so nothing here
    # flags the mis-split -- the pack choice is what has to be right
    assert n.ambiguities == ()


def test_pack_vocabulary_entries_are_single_words() -> None:
    # The shipped-vocabulary guard (test_lexicon.py's
    # test_default_lexicon_builds_warning_free), extended to the OTHER
    # vocabulary source: a locale pack's compiled sets (`_sets`) are
    # matched one word at a time same as Lexicon.default()'s, so a
    # multi-word entry in any set but given_name_titles would be dead.
    # Checked directly against the sets' contents (not by capturing the
    # construction-time warning) because a pack module is imported --
    # and its Locale built -- at most once per process; a later test in
    # this file may already have forced the import, which would make a
    # warning-capture version of this test pass even on a regression.
    # Iterates every registered pack, not just ru/tr_az by name, so a
    # future pack is covered automatically. zh is the pack that gives
    # the field loop something to chew on (ru/tr_az build on
    # Lexicon.empty()); the registry-non-empty assert below keeps the
    # test from passing vacuously if that ever stops being true.
    assert locales.available()
    for code in locales.available():
        lexicon = locales.get(code).lexicon
        for field in _VOCAB_FIELDS:
            if field == "given_name_titles":
                continue
            for entry in getattr(lexicon._sets, field):
                assert entry == "".join(entry.split()), (
                    f"{code}: {field} entry {entry!r} contains "
                    f"whitespace and can never match")


def test_rules_packs_equal_their_hand_written_patches() -> None:
    # 4f (#754): RU's and TR_AZ's patches are compiled from ru.toml's
    # and tr.toml's [rules]; they must be the Locales written by hand
    # before, value for value and enum member for enum member, so a
    # pickle of either loads as the other
    from nameparser._policy import PolicyPatch

    assert locales.RU == Locale(code="ru", lexicon=Lexicon.empty(), policy=PolicyPatch(
        patronymic_rules=frozenset({PatronymicRule.EAST_SLAVIC})))
    assert locales.TR_AZ == Locale(code="tr_az", lexicon=Lexicon.empty(), policy=PolicyPatch(
        patronymic_rules=frozenset({PatronymicRule.TURKIC})))
    for pack in (locales.RU, locales.TR_AZ):
        assert pack.languages == frozenset()
        rules = pack.policy.patronymic_rules
        assert rules is not UNSET
        assert all(type(r) is PatronymicRule for r in rules)


def test_a_packs_marker_regexes_are_the_rules_its_patch_turns_on() -> None:
    # ru.py/tr_az.py hand-copy their DEVIATES marker regexes from
    # _pipeline._vocab (layering forbids a pack importing the
    # pipeline -- see each pack's module docstring). Which rules a pack
    # turns on is its compiled policy patch (4f), so the copies a pack
    # must hold are derived from it: a rule added to a file's [rules]
    # fails here until DEVIATES declares its surface, and drift in a
    # copy fails here, not at the L6 non-interference gate.
    from nameparser._pipeline import _vocab

    rule_patterns = {
        PatronymicRule.EAST_SLAVIC: (_vocab._EAST_SLAVIC, _vocab._EAST_SLAVIC_CYR),
        PatronymicRule.TURKIC: (_vocab._TURKIC, _vocab._TURKIC_CYR),
    }
    assert set(rule_patterns) == set(PatronymicRule)
    for code, module in _PACKS.items():
        rules = locales.get(code).policy.patronymic_rules
        want = set() if rules is UNSET else {
            (p.pattern, p.flags) for r in rules for p in rule_patterns[r]}
        got = {(p.pattern, p.flags) for p in _marker_regexes(module)}
        assert got == want, code


def test_ru_deviates_scans_per_token() -> None:
    # Regression: the rule rotates on the family-POSITION token, so a
    # whole-string search missed a patronymic ending followed by a
    # suffix -- under-declaration, the unsafe direction for the
    # non-interference gate. The pack rotates this name; DEVIATES must
    # say so.
    assert _ru.DEVIATES("Ivan Petr Sidorovich Jr.")
    # Over-declaration is the accepted safe direction: the ending
    # matches a token although the rule's 1 given + 1 middle +
    # 1 family shape never fires on a two-token name.
    assert _ru.DEVIATES("Sidorovich Anna")
    assert not _ru.DEVIATES("John Smith")


def test_tr_az_deviates_scans_per_token() -> None:
    # Mirror of the RU regression above: the Turkic marker regexes are
    # fullmatch-shaped (^...$), so anything but a per-token scan would
    # miss a marker followed by a suffix (under-declaration) -- and a
    # whole-string match would never fire at all on multi-token names.
    assert _tr_az.DEVIATES("Mammadova Aygun Ali kizi Jr.")
    # over-declaration stays the safe direction: a bare marker-shaped
    # token declares even where the rule won't rewrite anything
    assert _tr_az.DEVIATES("Kizi Anna")
    assert not _tr_az.DEVIATES("John Smith")
    # markers are whole-token: a name merely CONTAINING one must not
    # declare ("Ogluev" is not a marker)
    assert not _tr_az.DEVIATES("Ogluev Ivan")


def test_tr_az_deviates_reads_a_decomposed_marker() -> None:
    """#1316: DEVIATES declares the surface the pack's rule rewrites,
    and the rule reads a marker NFC-composed, so a ğ or ў written as base
    plus combining mark must declare too, or the non-interference gate
    misses an undeclared deviation."""
    for name in ("Aliyev Rashad Vali oğlu", "Aliyev Rashad Vali OĞLU",
                 "Каримов Алишер Вали ўғли"):
        decomposed = unicodedata.normalize("NFD", name)
        assert decomposed != name
        assert _tr_az.DEVIATES(decomposed), name


def test_locales_unknown_attribute() -> None:
    with pytest.raises(AttributeError, match="XX"):
        locales.XX


def test_ru_plus_tr_az_unions_patronymic_rules() -> None:
    p = parser_for(locales.RU, locales.TR_AZ)
    assert p.policy.patronymic_rules == frozenset(
        {PatronymicRule.EAST_SLAVIC, PatronymicRule.TURKIC})
    # both rules live: one name from each pack's case segment
    ru = p.parse("Сидоров Иван Петрович")
    assert ru.given == "Иван"
    tr = p.parse("Mammadova Aygun Ali kizi")
    assert (tr.given, tr.middle, tr.family) == (
        "Aygun", "Ali kizi", "Mammadova")


def test_pack_over_custom_base() -> None:
    base = Parser(lexicon=Lexicon.default().add("zqxcustom", kind="title"))
    p = parser_for(locales.RU, base=base)
    n = p.parse("Zqxcustom Иван Петрович")
    assert n.title == "Zqxcustom"       # base lexicon survives the fold


def test_pack_preserves_custom_base_policy() -> None:
    # the lexicon-survival twin above has a policy counterpart: a
    # policy-only pack must ADD its patronymic rule without resetting
    # unrelated policy fields the base customized
    base = Parser(policy=Policy(strip_emoji=False))
    p = parser_for(locales.RU, base=base)
    assert p.policy.strip_emoji is False
    assert p.policy.patronymic_rules == frozenset(
        {PatronymicRule.EAST_SLAVIC})


def test_parser_for_results_chain_as_bases() -> None:
    # parser_for's result is itself a valid base= -- packs applied in
    # two steps accumulate exactly like one call with both packs
    chained = parser_for(locales.TR_AZ, base=_PACKED["ru"])
    assert chained.policy.patronymic_rules == frozenset(
        {PatronymicRule.EAST_SLAVIC, PatronymicRule.TURKIC})
    assert chained.parse("Сидоров Иван Петрович").given == "Иван"
    assert chained.parse("Mammadova Aygun Ali kizi").family == "Mammadova"


def test_the_rotation_stands_down_under_a_declared_family_first_order(
        ) -> None:
    """#384 option 1: O1's rotation is the DEFAULT order's work.

    It exists to RESTORE the given-first reading from a family-first
    listing, so a caller who has DECLARED FAMILY_FIRST has already
    supplied what it would have inferred and position decides
    instead. That scoping is a GATE, not a property of the shape:
    the rotation reads the word in the FAMILY position for a
    patronymic ending, and under FAMILY_FIRST that slot holds the
    name's FIRST word.

    'Мицкевич Адам Юзеф' is the input that makes the difference
    visible -- a patronymic-DERIVED surname written first. Without
    the gate the rotation fires on it and reports family 'Адам';
    with the gate it reads exactly as plain FAMILY_FIRST does.

    The other two are one measurement of the accepted divergence.
    The family-first listing reads the same either way, and the
    natural-order name reads as the caller declared it -- family
    'Иван' -- which is what #384 measured, Accepted in
    docs/design/decisions/O1 rather than treated as a defect.
    rules/O1 states it in prose because an example line there
    takes ONE annotation, a pack or an order, never both.
    """
    ff = parser_for(locales.RU,
                    base=Parser(policy=Policy(name_order=FAMILY_FIRST)))
    # the firing control: without the gate this reads family 'Адам'
    derived = ff.parse("Мицкевич Адам Юзеф")
    assert (derived.family, derived.given, derived.middle) == (
        "Мицкевич", "Адам", "Юзеф")
    plain = Parser(policy=Policy(name_order=FAMILY_FIRST)).parse(
        "Мицкевич Адам Юзеф")
    assert (derived.family, derived.given, derived.middle) == (
        plain.family, plain.given, plain.middle)
    listing = ff.parse("Сидоров Иван Петрович")
    assert (listing.family, listing.given, listing.middle) == (
        "Сидоров", "Иван", "Петрович")
    natural = ff.parse("Иван Петрович Сидоров")
    assert (natural.family, natural.given, natural.middle) == (
        "Иван", "Петрович", "Сидоров")


def test_the_turkic_marker_lands_in_a_name_field_under_both_orders(
        ) -> None:
    """Pins the prose decisions/O1's 2026-09-07 entry states for O2.

    Gate-independent: `Ali Ahmad Vali oglu` is natural-order input,
    so the rotation would not fire on it under the default order
    either. What the two readings show is O2's own 2026-07-02
    Accepted consequence reached by a second route -- a declared
    family-first order leaves the marker standing in a name field.
    Under FAMILY_FIRST that costs nothing visible, the family being
    the word the rotation would have chosen anyway; under
    FAMILY_FIRST_GIVEN_LAST the marker becomes the GIVEN name, which
    is the reading rules/O2 carries as Accepted.
    """
    ff = parser_for(locales.TR_AZ, base=Parser(
        policy=Policy(name_order=FAMILY_FIRST)))
    n = ff.parse("Ali Ahmad Vali oglu")
    assert (n.family, n.given, n.middle) == ("Ali", "Ahmad", "Vali oglu")
    ffgl = parser_for(locales.TR_AZ, base=Parser(
        policy=Policy(name_order=FAMILY_FIRST_GIVEN_LAST)))
    n = ffgl.parse("Ali Ahmad Vali oglu")
    assert (n.family, n.given, n.middle) == ("Ali", "oglu", "Ahmad Vali")


def test_locales_import_is_lazy(monkeypatch: pytest.MonkeyPatch) -> None:
    # importing the package must not import any pack module; PEP 562
    # loads them on first attribute access (the lazy-access contract:
    # "importing
    # nameparser never pays for pack data"). monkeypatch snapshots
    # sys.modules AND the parent package attribute (the fresh import
    # below rebinds nameparser.locales), so everything rolls back even
    # if an assert fails mid-test (manual del + reload left other tests
    # running against a half-restored module cache on failure).
    import sys

    import nameparser as _np

    monkeypatch.setattr(_np, "locales", _np.locales)
    for mod in list(sys.modules):
        if mod.startswith("nameparser.locales"):
            monkeypatch.delitem(sys.modules, mod)
    import nameparser.locales
    assert "nameparser.locales.ru" not in sys.modules
    nameparser.locales.RU
    assert "nameparser.locales.ru" in sys.modules


def _assert_non_interference(
    packed: Parser, deviates: Callable[[str], bool], corpus: Iterable[str],
) -> int:
    """Return the number of DECLARED deviations seen; fail on any
    undeclared one (the pack-acceptance rejection rule)."""
    declared = 0
    for name in corpus:
        base = _default_parse(name)
        got = packed.parse(name).as_dict()
        if got != base:
            assert deviates(name), (
                f"UNDECLARED deviation: {name!r}\n"
                f"  default: {base}\n  packed:  {got}")
            declared += 1
    return declared


def _default_corpus() -> list[str]:
    from .cases import CASES

    return list(_CORPUS) + [c.text for c in CASES
                             if c.locale is None and c.policy is None]


# Synthetic rotator names, keyed by pack code: one per alternation
# branch of each pack's marker regexes (both scripts), in the shape that
# makes the rule fire (RU: family-first, patronymic last, plain middle;
# TR_AZ: a standalone marker token). They serve the gate's POSITIVE side
# -- without them the shared corpus exercises TR_AZ with a single name,
# leaving the gate nearly vacuous (review finding, 2026-07-17). Branch
# named per row, enforced by the branch-coverage test below.
_ROTATORS: dict[str, list[str]] = {}
_ROTATORS["ru"] = [
    "Sidorov Ivan Petrovich",        # ovich
    "Sidorova Anna Petrovna",        # ovna
    "Karpov Oleg Sergeevich",        # evich
    "Karpova Olga Sergeevna",        # evna
    "Petrova Maria Nikitichna",      # ichna
    "Ulyanov Vladimir Ilyich",       # ilyich
    "Bulgakov Ivan Kuzmich",         # kuzmich
    "Titov Pyotr Lukich",            # lukich
    "Orlov Semyon Fomich",           # fomich
    "Zaitsev Andrei Fokich",         # fokich
    "Pronin Ivan Nikitich",          # nikitich
    "Mamontov Ivan Savvich",         # savvich
    "Сидоров Иван Петрович",         # ович
    "Сидорова Анна Петровна",        # овна
    "Карпов Олег Сергеевич",         # евич
    "Карпова Ольга Сергеевна",       # евна
    "Петрова Мария Никитична",       # ична
    "Ульянов Владимир Ильич",        # ильич
    "Булгаков Иван Кузьмич",         # кузьмич
    "Титов Пётр Лукич",              # лукич
    "Орлов Семён Фомич",             # фомич
    "Зайцев Андрей Фокич",           # фокич
    "Пронин Иван Никитич",           # никитич
    "Мамонтов Иван Саввич",          # саввич
]
_ROTATORS["tr_az"] = [
    "Aliyev Ali Vali oglu",              # oglu
    "Aliyev Rashad Vali oğlu",           # oğlu
    "Mammadov Elchin Hasan ogly",        # ogly
    "Karimov Aziz Vali ogli",            # ogli
    "Karimov Alisher Vali o'g'li",       # the o'g'li branch, ASCII '
    "Yusupov Botir Vali o’g’li",         # the o'g'li branch, typographic ’
    "Yusupov Botir Vali o‘g‘li",         # the o'g'li branch, smart quote ‘ (#1186)
    "Yusupov Botir Vali oʼgʼli",         # the o'g'li branch, modifier ʼ (#1186)
    "Yusupov Botir Vali o`g`li",         # the o'g'li branch, backtick (#1186)
    "Mammadova Aygun Hasan qizi",        # qizi
    "Aliyeva Leyla Vali qızı",           # qızı
    "Mammadova Sevinj Ali kizi",         # kizi
    "Asanova Aigul Bolot kyzy",          # kyzy
    "Guliyeva Nigar Vali gyzy",          # gyzy
    "Nazarbayev Nursultan Abish uly",    # uly
    "Zheenbekov Sooronbay Sharip uulu",  # uulu
    "Алиев Али Вали оглу",               # оглу
    "Мамедов Эльчин Гасан оглы",         # оглы
    "Алиев Рашад Вали оғлу",             # оғлу
    "Каримов Алишер Вали ўғли",          # ўғли
    "Юсупов Ботир Вали угли",            # угли
    "Мамедова Айгюн Гасан кызы",         # кызы
    "Алиева Лейла Вали гызы",            # гызы
    "Назарбаева Дарига Нурсултан қызы",  # қызы
    "Каримова Лола Вали қизи",           # қизи
    "Назарбаев Нурсултан Абиш улы",      # улы
    "Токаев Касым Кемел ұлы",            # ұлы
    "Жээнбеков Сооронбай Шарип уулу",    # уулу
]
# zh has no marker regexes to rotate through: its rotators cover the
# SEGMENTATION shapes instead (single/compound surname, simplified/
# traditional, 1- and 2-character given names). No spaced entry --
# spaced Han already parses family-first by default, so a spaced name
# would not deviate from the default parser at all.
_ROTATORS["zh"] = [
    "毛泽东",        # 1-char surname, unspaced
    "张伟",          # 2-char name: 1-char surname + 1-char given
    "欧阳修",        # compound surname (欧 is NOT itself listed)
    "夏侯惇",        # compound beats single: 夏 IS listed too
    "司马相如",      # compound + 2-char given
    "王力宏",        # 1-char surname + 2-char given
    "諸葛亮",        # traditional-script compound
    "萧红",          # the 肖/萧 merger's second simplified spelling
]
# ne is a vocabulary pack: its rotators cover each word it turns on, in
# each script it is written in, at the head of the name, behind a
# listed title and after a family comma -- the positions where the
# default reads the word as a title and the pack as the given name.
_ROTATORS["ne"] = [
    "श्री कृष्ण श्रेष्ठ",    # श्री at the head
    "श्रेष्ठ, श्री कृष्ण",   # श्री after a family comma
    "गुरु प्रसाद शर्मा",     # गुरु at the head
    "Guru Prasad Sharma",   # guru at the head
    "Mr. Guru Sharma",      # guru behind a listed title
    "Sharma, Guru Prasad",  # guru after a family comma
]
# ja has no marker regexes and no vocabulary of its own: its
# segmentation rotators cover the shapes only the pack PLUS its
# segmenter changes. Every one of THESE rows is UNSPACED on purpose -- a spaced kana-licensed name (高橋 みなみ) now
# reads family-first by DEFAULT (decisions/W4), so it would
# not deviate and would fail the must-deviate assertion below.
_ROTATORS["ja"] = [
    "山田太郎",      # 2-kanji family + 2-kanji given, the common shape
    "高橋一郎",      # the name a zh surname list corrupts (高 + 橋一郎)
    "田中花子",      # ditto (田 is a listed zh surname)
    "原辰徳",        # 1-kanji family + 2-kanji given: the other fork
    "高橋みなみ",    # kanji + hiragana: the kana license's carrier case
    "山田エミ",      # kanji + katakana: licensed as a MIXED token, where
                     # pure katakana (マイケル) is deliberately not
    "佐々木健",      # the iteration mark 々 inside a top-20 surname
]
# ja's choice of the language (#1194) turns on 君, the Diet's honorific:
# glued, spaced and behind the fullwidth comma, where the default reads it
# into the given name or as a middle name. Segmentation-free on purpose,
# so the segmenterless pack's inert test reads only the rows above.
_JA_CHOICE_ROTATORS = [
    "逢沢　一郎君",    # glued, the Diet's own writing
    "逢沢　一郎　君",  # spaced
    "逢沢，一郎君",    # behind the fullwidth comma
]
_JA_SEGMENTATION_ROTATORS = list(_ROTATORS["ja"])
_ROTATORS["ja"] = _JA_SEGMENTATION_ROTATORS + _JA_CHOICE_ROTATORS

# The choice packs (3f): one name per word of the derived surface, each
# in a shape the default reads differently, so the gate's positive side
# reaches every word the choice changes (held by
# test_choice_rotators_cover_every_changed_word below). cs and sk carry
# rules/O6's patch too, so each word's rotator is a name the patch alone
# leaves as the default reads it -- two name words, or a marker run in
# brackets -- (held by test_a_choice_word_rotator_is_moved_by_the_choice_alone),
# and the patch has rotators of its own.
_ROTATORS["cs"] = [
    "BcA Krejčí",                    # bca
    "MgA Malá",                      # mga
    "Mjr Novák",                     # mjr, three initials elsewhere (#1129)
    "Chief Mjr Novák",               # chief mjr, the phrase chief makes
    "Jan Novák, DrSc",               # drsc, a credential after a comma
    "Pan Novák",                     # pan
    "Jana Nováková (roz. Svobodová)",  # roz, the birth marker, bracketed
    "Dienstbier ml.",                # ml
    "Jiří Dienstbier st.",           # st
    "Alena Pešová Řehořová",         # rules/O6, the patch
    "Ing. Alena Pešová Řehořová",    # rules/O6 behind a title
    "김민준 1",                       # rules/O6 over a segmented name and a word of no letter
    "Jan\u200bPavel -",               # rules/O6 over a zero-width split and a lone mark
]
_ROTATORS["sk"] = [
    "Jozef Mrkva, ArtD.",            # artd, a credential after a comma
    "Jozef Mrkva, DrSc",             # drsc
    "Mrkva ml.",                     # ml
    "Ján Mrkva st.",                 # st
    "Mária Nováková Kováčová",       # rules/O6, the patch
    "김민준 1",                       # rules/O6 over a segmented name and a word of no letter
    "Jan\u200bPavel -",               # rules/O6 over a zero-width split and a lone mark
]
_ROTATORS["sl"] = [
    "Janez Novak ml.",               # ml
    "Janez Novak st.",               # st
]
_ROTATORS["hr"] = [
    "Ivan Horvat ml.",               # ml
    "Ivan Horvat st.",               # st
]
# hi and bn: each romanized title at the head, in each case, behind a
# listed title, after a family comma and before one (rules/H6); a dotted
# one where it ends the given part after a family comma (rules/H8) or
# ends the name (rules/H5), rules/H2's shape already reading it as a
# title at the head by default.
_ROTATORS["hi"] = [
    "Shrimati Indira Gandhi",        # shrimati at the head
    "SHRIMATI INDIRA GANDHI",        # shrimati, in one case
    "Dr. Shrimati Indira Gandhi",    # shrimati behind a listed title
    "Gandhi, Shrimati Indira",       # shrimati after a family comma
    "Gandhi, Indira Shrimati.",      # shrimati, dotted, ending the given part
    "Smt Nirmala Sitharaman",        # smt
    "smt nirmala sitharaman",        # smt, in one case
    "Sitharaman, Smt Nirmala",       # smt after a family comma
    "Sitharaman, Nirmala Smt.",      # smt, dotted, ending the given part
    "Shriyut Ram Prasad",            # shriyut
    "Mr. Shriyut Ram Prasad",        # shriyut behind a listed title
    "Prasad, Ram Shriyut",           # shriyut ending the given part
    "Indira Gandhi Shrimati.",       # shrimati, dotted, ending the name (H5)
    "Shrimati Gandhi, Indira",       # shrimati before a family comma (H6)
    "Smt. Sitharaman, Nirmala",      # smt, dotted, before a family comma
    ", Nirmala Smt.",                # smt, dotted, after an empty head
    # sushri: or.toml's Odia given name gates it under the plain choice,
    # so it is a title only inside a title phrase, a style's partner
    # (rules/H9); at the head, behind Dr. and after a family comma it
    # reads as the default reads it, and only a strict choice reads it
    # as the title there
    "Her Excellency Sushri Sangita Behera",
]
# vi: the order and the fragment move every name a family comma does
# not fix, so each title's rotator stands behind a family comma, where
# only the choice moves it (test_a_choice_word_rotator_is_moved_by_the_choice_alone).
# The order's rows (Lê Văn Anh, Le Thi Mai) read the same with the
# fragment or without it; each fragment row is _VI_REMOVALS' witness for
# its removal (test_each_vi_removal_moves_its_own_row).
_ROTATORS["vi"] = [
    "Lê Văn Anh",                    # the order, written with diacritics
    "Le Thi Mai",                    # the order, le at the head
    "NGUYEN VAN ANH",                # the order and van, in one case
    "Nguyen Van Anh",                # van, the Dutch particle removed
    "Nguyen Le Anh",                 # le, the French article
    "Nguyen Do Anh",                 # do, the Portuguese particle
    "Nguyen Du Anh",                 # du
    "Le Di Anh",                     # di
    "Nguyen La Anh",                 # la
    "Tran Da Anh",                   # da
    "Nguyen Tho Anh",                # tho
    "Tran Thi San Ha",               # san, the saint particle
    "Nguyen The Tuan",               # the, the English connective
    "NGUYEN THI Y NHI",              # y, the Spanish connective, in one case
    "NGUYEN LINH CHI",               # chi, the credential, in one case
    "NGUYEN VAN DO",                 # do's credential
    "NGUYEN THI BA",                 # ba
    "Nguyen, Ts Van Anh",            # ts after a family comma
    "Nguyen, Gs Van Anh",            # gs
    "Nguyen, Pgs Van Anh",           # pgs
    "Nguyen, PGS.TS. An",            # the stacked form
]
# mn: the Cyrillic script order alone (its choice changes no word), in
# each form the father's name is written in, with a word before it and
# with a Latin title beside it; a romanized name does not deviate
_ROTATORS["mn"] = [
    "Батын Сүхээ",                   # the genitive, Cyrillic
    "Бат Сүхээ",                     # the nominative, as passports write it
    "Б. Сүхээ",                      # the father's name as its initial
    "Цэрэн Оюун-Эрдэнэ",             # a hyphenated given name
    "Боржигин Батын Сүхээ",          # a word before the father's name
    "Dr. Батын Сүхээ",               # a Latin title beside a Cyrillic name
]
_ROTATORS["bn"] = [
    "Shrimati Mamata Banerjee",      # shrimati at the head
    "Banerjee, Mamata Shrimati",     # shrimati ending the given part
    "SMT MAMATA BANERJEE",           # smt, in one case
    "Dr. Smt Mamata Banerjee",       # smt behind a listed title
    "Banerjee, Mamata Smt.",         # smt, dotted, ending the given part
    "Adhyapak Anisuzzaman Khan",     # adhyapak at the head
    "adhyapak anisuzzaman khan",     # adhyapak, in one case
    "Dr. Adhyapak Anisuzzaman",      # adhyapak behind a listed title
    "Khan, Adhyapak Anisuzzaman",    # adhyapak after a family comma
    "Anoop Adhyapak.",               # adhyapak, dotted, ending the name (H5)
    "Adhyapak Kumar, Anoop",         # adhyapak before a family comma (H6)
]


#: Packs whose choice of languages changes no compiled reading: the
#: chosen file's readings are all on by default and clash with none
#: other's, so the choice is recorded (a strict parser reads that file)
#: and its derived surface is empty. mn: mn.toml held `lama` and
#: an exclusion when locales.MN shipped (#1237). A choice that comes to
#: change a word fails test_an_inert_choice_changes_no_word until its
#: pack leaves this set and its rotators name the word, and
#: docs/locales.rst's line that mn's choice turns on nothing changes.
_INERT_CHOICES = frozenset({"mn"})


@pytest.mark.parametrize("code", sorted(c for c in _PACKS
                                        if locales.get(c).languages
                                        and c not in _INERT_CHOICES))
def test_choice_rotators_cover_every_changed_word(code: str) -> None:
    # the choice packs' counterpart of the marker-branch sweep below:
    # a word joining a choice's surface fails here until a rotator
    # name holds it, so the gate's positive side cannot thin out
    surface = _ri.changed_words(_ri.selected(locales.get(code).languages))
    missing = sorted(w for w in surface if not any(
        _surface_deviates(frozenset({w}))(name) for name in _ROTATORS[code]))
    assert surface and missing == []


@pytest.mark.parametrize("code", sorted(_INERT_CHOICES))
def test_an_inert_choice_changes_no_word(code: str) -> None:
    assert locales.get(code).languages
    assert _ri.changed_words(_ri.selected(locales.get(code).languages)) == set()


@pytest.mark.parametrize("code", sorted(
    c for c in _PACKS if locales.get(c).languages
    and not _is_vocabulary_pack(locales.get(c)) and c not in _INERT_CHOICES))
def test_a_choice_word_rotator_is_moved_by_the_choice_alone(code: str) -> None:
    # a pack with a choice beside a fragment or a patch (es): a rotator
    # holding a word the choice changes is that word's witness only if
    # the choice moves it and the rest of the pack alone does not, or a
    # title's rotator would pass on the patch's move (the #964 review:
    # six of es's first title rotators were moved by rules/O6 alone)
    pack = locales.get(code)
    surface = _ri.changed_words(_ri.selected(pack.languages))
    holds = _surface_deviates(surface)
    choice = parser_for(Locale(code="choice", lexicon=Lexicon.empty(),
                               languages=pack.languages))
    with warnings.catch_warnings():
        # ja's patch alone activates segmentation with nothing to divide by
        warnings.filterwarnings("ignore", message=".*ja_segmenter")
        rest = parser_for(Locale(code="rest", lexicon=pack.lexicon,
                                 policy=pack.policy))
    witnesses = [n for n in _ROTATORS[code] if holds(n)]
    assert witnesses
    for name in witnesses:
        assert choice.parse(name).as_dict() != _default_parse(name), name
        assert rest.parse(name).as_dict() == _default_parse(name), name


# The vocabulary packs' rotators: a name in each shape a reading the pack
# turns on or prefers changes, read one way by default and another under
# the pack (the pinned rows below say how). ga: each clan particle
# mid-name; gd: `nic`; both: the clan `mc` preferred over the credential;
# pt_br: `sb` behind name words, bare and dotted, in each case, and the
# words pt's choice prefers.
_ROTATORS["ga"] = [
    "Máire Nic Gabhann",             # nic
    "Máire Mhic Gabhann",            # mhic
    "Máire Uí Bhriain",              # uí
    "Pádraig Mic Cárthaigh",         # mic
    "John Smith MC",                 # mc, the clan particle, not MC
]
_ROTATORS["gd"] = [
    "Màiri Nic Leòid",               # nic
    "Gabhann, Màiri Nic",            # nic ending the given part
    "John Smith MC",                 # mc, the clan particle, not MC
]
# es: the patch's rules/O6; each title the choice turns on, in a name the
# patch and the list alone leave as the default reads it (held below), at
# the head, in each case, after a
# family comma, before one (rules/H6) and dotted ending the name (rules/H5);
# pt: its titles likewise, and the words its choice prefers.
_ROTATORS["es"] = [
    "Lady Heidenreich",              # lady, a given name (H9)
    "Maestra Ruiz",                  # maestra
    "López Maestra.",                # maestra, dotted, ending the name
    "Doña María Pérez",              # doña
    "Gabriel García Márquez",        # rules/O6, the patch
    "María José García López",       # rules/O6 behind a two-word given part
    "김민준 1",                       # rules/O6 over a segmented name and a word of no letter
    "Jan\u200bPavel -",               # rules/O6 over a zero-width split and a lone mark
]
# es_ar: es's choice and patch, so es's rows, but for the zero-width
# split, whose `pavel` the AR list vetoes; the list's own words read as
# the default does, so they are no rotators (held in the contents test)
_ROTATORS["es_ar"] = [
    *(n for n in _ROTATORS["es"] if n != "Jan\u200bPavel -"),
    "Ana\u200bGarcía -",              # rules/O6 over a zero-width split and a lone mark
]
# rules/P10's given name the default does not read, which pt's choice
# turns on, so the phrase reads as the middle name (#1118, #1122)
_PT_PARTICLE_GIVEN = [
    "Maria da Piedade Costa",        # piedade
]
_ROTATORS["pt"] = [
    *_PT_PARTICLE_GIVEN,
    "John Smith DO",                 # do, pt's particle, not DO
    "ANA SILVA E SOUZA",             # e, pt's connective
]
_ROTATORS["pt_br"] = [
    "JOSE CARLOS SILVA SB",          # sb
    "Jose Carlos Silva Sb.",         # sb, dotted
    "JOSE SILVA SB",                 # sb, one word to spare
    *_PT_PARTICLE_GIVEN,             # pt's given names P10 completes
    "John Smith DO",                 # do, pt's particle, not DO
    "ANA SILVA E SOUZA",             # e, pt's connective
]


# #1115 turned these titles on by default, so no choice moves them: the
# rows that witnessed each as a choice word now witness that the default
# reads it as the pack does, a title in each place the rotator put it
# (decisions/vocabulary-model, the 2026-11-06 #1115 entry).
_READ_BY_DEFAULT_SINCE_1115: dict[str, list[str]] = {
    "cs": [
        "Jan Novák, JUDr",               # judr, bare after a comma
        "MDDr Dvořáková",                # mddr
        "MUDr Novák",                    # mudr
        "MVDr Svoboda",                  # mvdr
        "PaedDr Králová",                # paeddr
        "PharmDr Králová",               # pharmdr
        "Novák PhDr.",                   # phdr, dotted at the end
        "Novák, RNDr",                   # rndr, after a one-word head
        "ThDr Hus",                      # thdr
    ],
    "sk": [
        "Jozef Mrkva, JUDr",             # judr
        "MDDr Kováčová",                 # mddr
        "MUDr Mrkva",                    # mudr
        "MVDr Horváth",                  # mvdr
        "PaedDr Kováčová",               # paeddr
        "PharmDr Kováčová",              # pharmdr
        "Mrkva PhDr.",                   # phdr
        "Mrkva, RNDr",                   # rndr
        "ThDr Chryzostom",               # thdr
    ],
    "vi": [
        "Nguyen, Ths Van Anh",           # ths
        "Nguyen, ĐBQH Van Anh",          # đbqh, the office
        "Nguyen, DBQH Van Anh",          # dbqh, its ASCII spelling
        "Nguyen, Chief ĐBQH Anh",        # chief, in a phrase with đbqh
        "Nguyen, Deputy DBQH Anh",       # deputy, in a phrase with dbqh
        "Nguyen, Chief DBQH Anh",        # chief dbqh
        "Nguyen, Deputy ĐBQH Anh",       # deputy đbqh
    ],
    "es": [
        "Lic Juan Pérez",                # lic
        "LIC JUAN PEREZ",                # lic, in one case
        "Pérez Lic.",                    # lic, dotted, ending the name (H5)
        "Licenciado Sánchez",            # licenciado
        "Lcdo Ricardo García",           # lcdo
        "Pérez, Licenciada Ana",         # licenciada after a family comma
        "Lcda Sánchez",                  # lcda
        "Ingeniero Juan Pérez",          # ingeniero
        "ingeniera ana ruiz",            # ingeniera, in one case
        "Arq Julia Romero",              # arq
        "Mtro. Pérez, Edgar",            # mtro, dotted, before a family comma (H6)
        "Mtra Ana Ruiz",                 # mtra
        "Doctora Montilla",              # doctora
    ],
    "pt": [
        "Doutor João Silva",             # doutor
        "Silva, Doutor João",            # doutor after a family comma
        "Fernanda Lucchese, Doutora",    # doutora after the comma
        "Professora Rosária Lima",       # professora
        "Profa Maria Souza",             # profa
    ],
    "pt_br": [
        "Doutor João Silva",             # doutor, pt's title
        "Fernanda Lucchese, Doutora",    # doutora, pt's title
        "Professora Rosária Lima",       # professora, pt's title
        "Profa Maria Souza",             # profa, pt's title
    ],
}


def _marker_regexes(module: ModuleType) -> list[re.Pattern]:
    return [v for v in vars(module).values() if isinstance(v, re.Pattern)]


# Packs whose DEVIATES surface is defined by marker REGEXES -- derived,
# never listed, same rule as the registry itself: a pack qualifies by
# having any module-level re.Pattern, so zh and ja (which declare by
# codepoint range, derived from the shared table via _script_matcher,
# so they hold no pattern of their own) drop out on their own and a
# future marker-regex pack cannot silently miss branch coverage.
_MARKER_REGEX_PACKS = tuple(code for code in sorted(_PACKS)
                            if _marker_regexes(_PACKS[code]))


def test_range_declaring_packs_stay_out_of_marker_classification() -> None:
    # Load-bearing since the packs derive from the shared table: zh/ja
    # hold no module-level re.Pattern because _script_matcher's closure
    # hides the compiled class. A pack author who "simplifies" one back
    # to a module-level pattern flips its classification into the
    # rotator branch-coverage sweep, which a codepoint-range predicate
    # cannot satisfy.
    assert "zh" not in _MARKER_REGEX_PACKS
    assert "ja" not in _MARKER_REGEX_PACKS


def test_registry_is_the_pack_contract() -> None:
    # the declared-deviations authoring requirement
    # (mechanisms.md#LOCALE-PACKS-PURE-DATA), enforced structurally
    # (design
    # note 2026-07-18, option C): every registered pack module must
    # declare its deviation surface, and every pack must feed the gate's
    # positive side -- a new pack fails HERE until it ships both, rather
    # than a reviewer remembering to extend the gate by hand.
    assert set(_PACKS) == set(locales.available())
    for code, module in _PACKS.items():
        # a choice's surface is derived (_deviates ors it in), so a pack
        # that is nothing but its choice declares nothing, while a
        # fragment or a patch beside a choice deviates where no derived
        # word stands and declares that part, and only that part
        pack = locales.get(code)
        if _is_vocabulary_pack(pack):
            assert not hasattr(module, "DEVIATES"), (
                f"vocabulary pack {code!r} declares DEVIATES by hand; its "
                f"surface is derived from its choice")
            # an empty surface would make its gate pass by parsing
            # nothing differently
            assert _ri.changed_words(_ri.selected(pack.languages)), (
                f"vocabulary pack {code!r} changes no word")
            continue
        assert callable(getattr(module, "DEVIATES", None)), (
            f"pack {code!r} does not declare DEVIATES")
        # _MARKER_REGEX_PACKS selects on module-level patterns, so a
        # pack that declares by regex but keeps its patterns inside a
        # function would drop out of the branch-coverage sweep in
        # silence. Importing `re` is the tell. The tradeoff is
        # deliberate: a range-declaring pack that imports re for some
        # unrelated reason trips this loudly, which beats a silent
        # coverage gap -- and the fix is to expose the pattern.
        if "re" in vars(module):
            assert _marker_regexes(module), (
                f"pack {code!r} imports re but exposes no module-level "
                f"pattern")
    assert set(_ROTATORS) == set(_PACKS), (
        "every pack needs a rotator list (and only registered packs)")
    # the derivation is code, not a list, so an empty result would make
    # the branch-coverage test vanish into zero parametrizations rather
    # than fail. Assert it found something.
    assert _MARKER_REGEX_PACKS, "no pack declares marker regexes"


def _alternation_branches(pattern: str) -> list[str]:
    """Split a marker regex of the shape '(a|b|...)$' / '^(a|b|...)$'
    into its alternatives. The packs' character classes contain no '|',
    so a flat split is safe (and the shape assert guards the day one
    stops being true)."""
    inner = pattern.removeprefix("^").removesuffix("$")
    assert inner.startswith("(") and inner.endswith(")") and "|" not in (
        pattern.replace(inner, ""))
    return inner[1:-1].split("|")


@pytest.mark.parametrize("code", _MARKER_REGEX_PACKS)
def test_rotators_cover_every_marker_branch(code: str) -> None:
    # The rotator lists' per-row branch comments are a human convention;
    # this enforces them mechanically: every alternation branch of every
    # marker regex a pack defines (any module-level re.Pattern) must be
    # hit by some rotator token, so a regex edit that adds a branch
    # (kept in sync with _vocab by the pattern-equality test above)
    # fails HERE until a rotator name covers it. Anchoring follows the
    # pattern's own shape: '^(...)$' = whole-token marker, '(...)$' =
    # token ending.
    tokens = [tok for name in _ROTATORS[code] for tok in name.split()]
    # non-empty by construction: having marker regexes is what put this
    # pack in _MARKER_REGEX_PACKS in the first place
    for regex in _marker_regexes(_PACKS[code]):
        for branch in _alternation_branches(regex.pattern):
            anchored = regex.pattern.startswith("^")
            branch_re = re.compile(
                f"^({branch})$" if anchored else f"({branch})$", re.I)
            assert any(branch_re.search(tok) for tok in tokens), (
                f"no {code!r} rotator exercises marker branch {branch!r}")


@pytest.mark.parametrize("code, name", [
    (code, name) for code in sorted(_ROTATORS)
    for name in _ROTATORS[code]])
def test_rotator_deviates_and_declares(code: str, name: str) -> None:
    # every branch of the pack's marker regexes both FIRES (packed parse
    # differs from default) and is DECLARED (DEVIATES says so) -- the
    # per-name proof behind the gate's declared-count floor below
    packed = _require_packed(code)
    assert packed.parse(name).as_dict() != _default_parse(name)
    assert _deviates(code)(name)


@pytest.mark.parametrize("code, name", [
    (code, name) for code in sorted(_READ_BY_DEFAULT_SINCE_1115)
    for name in _READ_BY_DEFAULT_SINCE_1115[code]])
def test_a_title_read_by_default_since_1115_reads_as_its_pack_reads_it(
        code: str, name: str) -> None:
    default = _default_parse(name)
    assert _require_packed(code).parse(name).as_dict() == default
    assert default["title"], name


@pytest.mark.parametrize("code", sorted(_PACKS))
def test_non_interference_each_pack(code: str) -> None:
    packed = _require_packed(code)
    corpus = _default_corpus() + _ROTATORS[code]
    declared = _assert_non_interference(
        packed, _deviates(code), corpus)
    # the positive side: every synthetic rotator (plus the corpus's own
    # in-scope names) must actually flow through the declared branch
    assert declared >= len(_ROTATORS[code])


def test_non_interference_all_packs_combined() -> None:
    # Every pack is applied whether or not its extra is installed (the
    # ja pack's policy patch is pure data); only the ROTATORS of a pack
    # that cannot act are dropped, since the count assertion below
    # requires each listed name to actually deviate.
    all_rotators = [n for code in sorted(_ROTATORS) if code in _PACKED
                    for n in _ROTATORS[code]]
    corpus = _default_corpus() + all_rotators
    # cs, es and sk each set two_family_names to the same value, which
    # agrees and warns nothing (test_parser.py pins both sides)
    if _JA_AVAILABLE:
        packed = parser_for(
            *(locales.get(code) for code in sorted(_PACKS)),
            segmenter=locales.ja_segmenter())
    else:
        # without the extra, the stack's hiragana activation is
        # unservable -- which construction now SAYS (the segmenterless
        # warning, pinned in test_parser.py); expected noise here, the
        # gate below is what this test is about
        with pytest.warns(UserWarning, match="ja_segmenter"):
            packed = parser_for(
                *(locales.get(code) for code in sorted(_PACKS)))
    # the packs' languages union into ONE choice, whose surface is
    # derived from the union rather than from each pack's own; every
    # hand DEVIATES is or'd in whatever the pack, since a pack with a
    # choice beside a fragment or a patch carries both
    chosen = frozenset().union(*(locales.get(c).languages for c in _PACKS))
    choice_deviates = _surface_deviates(
        _ri.changed_words(_ri.selected(chosen)))
    hand = [m.DEVIATES for m in _PACKS.values() if hasattr(m, "DEVIATES")]
    declared = _assert_non_interference(
        packed,
        lambda n: choice_deviates(n) or any(d(n) for d in hand),
        corpus)
    assert declared >= len(all_rotators)


# -- a choice of languages (Locale.languages, phase 3b) --
#
# A vocabulary choice's deviation surface is DERIVED, not declared:
# _reading_index.changed_words gives the words whose compiled readings
# the choice changes, and a name holding none of them must parse as the
# default does (the RFC's "Measuring a pack"). The shipped vocabulary
# packs (NE, since 3d) run through the registry's gate above, its
# surface derived by _deviates; this gate runs over choices of the shipped files' tags
# that move something, each standing for a kind of effect: pt prefer
# and the shape clash of `e`, en prefer over several languages, cs and
# de turning a reading on (de's `i`, against ca's and pl's conjunction,
# mul's generation staying), and two languages chosen together.
# Measured 2026-10-29: about 1 s a choice on one worker (5 s for the
# five, the first paying the default parses the module caches).
_CHOICES = [("pt",), ("en",), ("cs",), ("de",), ("pt", "en")]


def _surface_deviates(surface: frozenset[str]) -> Callable[[str], bool]:
    """A name holding a surface word, over-declared as the gate allows:
    each comma- or space-separated piece normalized whole, with every
    period removed (an acronym's match), and cut at every non-word
    character (`st.john`, `AE-RA`); two pieces side by side, a title
    phrase's two words (`Chief DBQH`, #1108); an elided particle opening
    a piece (`d'Artagnan`, `al-Rashid`); a word outside ASCII anywhere
    in the name (a glued honorific), the name NFC-folded as the
    vocabulary is."""
    import unicodedata

    from nameparser._lexicon import _normalize
    wide = [w for w in surface if not w.isascii()]
    elided = tuple(w for w in surface if w[-1:] in ("'", "’", "-"))

    def deviates(name: str) -> bool:
        words: set[str] = set()
        folded = unicodedata.normalize("NFC", name).casefold()
        pieces = [p for p in re.split(r"[\s,]+", folded) if p]
        normalized = [_normalize(p) for p in pieces]
        words |= set(normalized)
        words |= {f"{a} {b}" for a, b in zip(normalized, normalized[1:])}
        for piece in pieces:
            words.add(piece.replace(".", ""))
            words |= set(re.split(r"[^\w]+", piece))
            if elided and piece.startswith(elided):
                return True
        return bool(words & surface) or any(w in folded for w in wide)
    return deviates


@functools.cache
def _deviates(code: str) -> Callable[[str], bool]:
    """The registered pack `code`'s deviation predicate: the surface
    derived from its choice of languages, where it makes one, or'd with
    its DEVIATES, which declares only what the rest of the pack (its
    fragment, its patch) changes, so no pack restates the choice's words
    by hand."""
    return _pack_deviates(locales.get(code), _PACKS[code])


def _pack_deviates(pack: Locale, module: ModuleType) -> Callable[[str], bool]:
    """_deviates for `pack`, whose module is `module`."""
    from nameparser._reading_index import changed_words, selected
    parts: list[Callable[[str], bool]] = []
    if pack.languages:
        parts.append(_surface_deviates(changed_words(selected(pack.languages))))
    hand = getattr(module, "DEVIATES", None)
    if hand is not None:
        parts.append(hand)
    return lambda name: any(part(name) for part in parts)


def test_a_pack_with_a_choice_and_a_patch_declares_only_the_patch() -> None:
    # the hand DEVIATES of a pack that also chooses languages covers
    # only what its patch changes: the choice's words are or'd in, so
    # the hand copy 3b removed is no longer needed
    mixed = Locale(code="mixed", lexicon=Lexicon.empty(),
                   policy=PolicyPatch(patronymic_rules=frozenset(
                       {PatronymicRule.EAST_SLAVIC})),
                   languages=frozenset({"ne"}))
    module = types.SimpleNamespace(DEVIATES=_ru.DEVIATES)
    deviates = _pack_deviates(mixed, module)  # type: ignore[arg-type]
    assert deviates("Guru Prasad Sharma")        # the choice's, derived
    assert deviates("Sidorov Ivan Petrovich")    # the patch's, declared
    assert not deviates("John Smith")
    assert not _is_vocabulary_pack(mixed)
    assert _is_vocabulary_pack(locales.HI)
    # NE was the example until #1254 gave it a patch (rules/O8)
    assert not _is_vocabulary_pack(locales.NE)


@pytest.mark.parametrize("tags", _CHOICES, ids="+".join)
def test_non_interference_each_choice(tags: tuple[str, ...]) -> None:
    from nameparser._reading_index import changed_words, selected
    surface = changed_words(selected(tags))
    choice = Locale(code="choice", lexicon=Lexicon.empty(),
                    languages=frozenset(tags))
    declared = _assert_non_interference(
        parser_for(choice), _surface_deviates(surface), _default_corpus())
    # the positive side: each choice here moves a corpus name, so the
    # gate is not passing by parsing nothing differently
    assert surface and declared


def test_the_choice_gate_fails_when_its_surface_misses_a_word() -> None:
    # the negative control: the derived surface is what the gate passes
    # on, so the same run with `e` taken out of pt's must find the
    # one-case names it moves (`ANA SILVA E SOUZA`) undeclared
    from nameparser._reading_index import changed_words, selected
    surface = changed_words(selected(["pt"]))
    choice = Locale(code="choice", lexicon=Lexicon.empty(),
                    languages=frozenset({"pt"}))
    with pytest.raises(AssertionError, match="UNDECLARED deviation"):
        _assert_non_interference(parser_for(choice),
                                 _surface_deviates(surface - {"e"}),
                                 _default_corpus())


# -- 3c: the pack-shaped exclusions as readings off by default --
#
# A generation word whose collision is with OTHER languages written in
# the same script (cs/hr/sk/sl `ml` and `st`) is a reading
# written `default = false` in its own file, read by no default and
# read once its language is chosen (decisions/vocabulary-model's
# 2026-10-29 #753, phase 3c entry). The sweep is every such
# reading in the index, so a later one joins it unlisted; a one-letter
# word (es `h`, de `i`) is left out, the initial veto
# (`_vocab.is_suffix_strict`) taking it written with its period:
# `Anna Novak h.` reads family `h.` under es, a bare `h` suffix `h`.
_OFF_GENERATIONS = sorted(
    (r.text, r.tag) for r in _ri.index()
    if r.kind == "generation" and not r.on_by_default and len(r.text) > 1)


def test_the_off_generation_sweep_reaches_the_converted_words() -> None:
    # an empty parametrize is a skip, not a failure
    slavic = {"cs", "hr", "sk", "sl"}
    assert ({("ml", t) for t in slavic}
            | {("st", t) for t in slavic}) <= set(_OFF_GENERATIONS)


@pytest.mark.parametrize("text, tag", _OFF_GENERATIONS,
                         ids=lambda v: str(v))
@pytest.mark.parametrize("spelling", ["{}.", "{}"])
def test_a_chosen_language_reads_its_off_generation_and_the_default_does_not(
        text: str, tag: str, spelling: str) -> None:
    word = spelling.format(text)
    name = f"Anna Novak {word}"
    chosen = parser_for(Locale(code="choice", lexicon=Lexicon.empty(),
                               languages=frozenset({tag})))
    assert parse(name).suffix == ""
    assert (chosen.parse(name).suffix, chosen.parse(name).family) == (
        word, "Novak")


def _fields(name: ParsedName) -> tuple[object, ...]:
    return (name.given, name.middle, name.family, name.suffix,
            tuple(a.kind.name for a in name.ambiguities))


# Today's readings of the comma and initial-pair shapes, pinned (given,
# middle, family, suffix, ambiguity kinds), default first. `ml` has no
# name reading, so under a choice it is an ungated suffix word and its
# comma readings take it with nothing reported (`Novak, ML` suffix
# 'ML', where the default reads given 'ML'), a question recorded for
# 3f in decisions/vocabulary-model's 2026-10-29 #753, phase 3c entry.
@pytest.mark.parametrize("tag, name, default, chosen", [
    ("cs", "Novak, ML", ("ML", "", "Novak", "", ()),
     ("", "", "Novak", "ML", ())),
    ("cs", "Novak, Anna ml.", ("Anna", "ml.", "Novak", "", ()),
     ("Anna", "", "Novak", "ml.", ())),
    ("cs", "Novak ml., Anna", ("Anna", "", "Novak ml.", "", ()),
     ("Anna", "", "Novak", "ml.", ())),
    ("cs", "Anna M. L. Novak", ("Anna", "M. L.", "Novak", "", ()),
     ("Anna", "M. L.", "Novak", "", ())),
    ("cs", "Anna ML Novak", ("Anna", "ML", "Novak", "", ()),
     ("Anna", "ML", "Novak", "", ())),
])
def test_an_off_generations_readings_in_other_shapes_are_pinned(
        tag: str, name: str, default: tuple[object, ...],
        chosen: tuple[object, ...]) -> None:
    choice = parser_for(Locale(code="choice", lexicon=Lexicon.empty(),
                               languages=frozenset({tag})))
    assert (_fields(parse(name)), _fields(choice.parse(name))) == (
        default, chosen)


@pytest.mark.xfail(strict=True, reason=(
    "a one-letter generation turned on stays inert written with its "
    "period: the initial veto takes it before the suffix set is read, "
    "so the choice changes nothing for it (3c's one-letter gap)"))
@pytest.mark.parametrize("tag, name, suffix", [
    ("es", "Juan Pérez H.", "H."),
    ("de", "Wilhelm Karl I.", "I."),
])
def test_a_chosen_one_letter_generation_reads_with_its_period(
        tag: str, name: str, suffix: str) -> None:
    choice = parser_for(Locale(code="choice", lexicon=Lexicon.empty(),
                               languages=frozenset({tag})))
    assert choice.parse(name).suffix == suffix


def test_no_exclusion_is_pack_shaped_any_more() -> None:
    # after 3c an exclusion means wrong everywhere until a pack's PR
    # converts its own (the RFC's Phase 3 table): a reason opening
    # "pack-shaped" is a reading a pack turns on, so it is written as
    # one. The recompute is decisions/vocabulary-model's grep.
    vocab = Path(__file__).resolve().parents[2] / "nameparser" / "vocab"
    found = [f.name for f in sorted(vocab.glob("*.toml"))
             if "pack-shaped" in f.read_text(encoding="utf-8")]
    assert vocab.is_dir() and found == []


# -- 3f: the Czech, Slovak, Slovenian and Croatian packs --
#
# Each row: a pack (or a choice of tags joined by +), an order, a name,
# then (title, given, middle, family, suffix, maiden, ambiguity kinds)
# under the default and under the pack. Every row but the last two
# groups is a case the default refuses and the pack reads; those two
# pin what choosing the language costs, and what it leaves alone
# (decisions/vocabulary-model's 2026-10-30 #753, phase 3f entry).
_ORDERS = {None: Policy(), "FAMILY_FIRST": Policy(name_order=FAMILY_FIRST),
           "FAMILY_FIRST_GIVEN_LAST": Policy(
               name_order=FAMILY_FIRST_GIVEN_LAST)}


@pytest.mark.parametrize("tags, order, name, default, packed", [
    # an academic title written bare, in each comma shape and order,
    # read by default since #1115 as the pack reads it; its dotted
    # spelling at the head was a title by its shape in both before
    ("cs", None, "MUDr Jan Novák",
     ("MUDr", "Jan", "", "Novák", "", "", ()),
     ("MUDr", "Jan", "", "Novák", "", "", ())),
    ("cs", None, "Jan Novák, MUDr",
     ("MUDr", "Jan", "", "Novák", "", "", ()),
     ("MUDr", "Jan", "", "Novák", "", "", ())),
    ("cs", None, "Novák, MUDr",
     ("MUDr", "", "", "Novák", "", "", ()),
     ("MUDr", "", "", "Novák", "", "", ())),
    ("cs", None, ", MUDr Jan",
     ("MUDr", "", "", "Jan", "", "", ()),
     ("MUDr", "", "", "Jan", "", "", ())),
    ("cs", "FAMILY_FIRST", "MUDr Novák Jan",
     ("MUDr", "Jan", "", "Novák", "", "", ()),
     ("MUDr", "Jan", "", "Novák", "", "", ())),
    ("sk", None, "PhDr Jozef Mrkva",
     ("PhDr", "Jozef", "", "Mrkva", "", "", ()),
     ("PhDr", "Jozef", "", "Mrkva", "", "", ())),
    # dotted at the end, a listed title there (rules/H5), in mixed case
    # and in one case
    ("cs", None, "Jan Novák MUDr.",
     ("MUDr.", "Jan", "", "Novák", "", "", ()),
     ("MUDr.", "Jan", "", "Novák", "", "", ())),
    ("cs", None, "JAN NOVÁK MUDR.",
     ("MUDR.", "JAN", "", "NOVÁK", "", "", ()),
     ("MUDR.", "JAN", "", "NOVÁK", "", "", ())),
    # MgA, a title only the pack reads (#1115 kept it the choice's, MGA
    # being initials too), in the shapes the doctorates' rows walk
    ("cs", None, "MgA Jana Malá",
     ("", "MgA", "Jana", "Malá", "", "", ()),
     ("MgA", "Jana", "", "Malá", "", "", ())),
    ("cs", None, "Jana Malá, MgA",
     ("", "MgA", "", "Jana Malá", "", "", ()),
     ("MgA", "Jana", "", "Malá", "", "", ())),
    ("cs", None, "Malá, MgA",
     ("", "MgA", "", "Malá", "", "", ()),
     ("MgA", "", "", "Malá", "", "", ())),
    ("cs", None, ", MgA Jana",
     ("", "MgA", "Jana", "", "", "", ()),
     ("MgA", "", "", "Jana", "", "", ())),
    ("cs", "FAMILY_FIRST", "MgA Malá Jana",
     ("", "Malá", "Jana", "MgA", "", "", ()),
     ("MgA", "Jana", "", "Malá", "", "", ())),
    ("cs", None, "Jana Malá MgA.",
     ("", "Jana", "Malá", "MgA.", "", "", ()),
     ("MgA.", "Jana", "", "Malá", "", "", ())),
    ("cs", None, "JANA MALÁ MGA.",
     ("", "JANA", "MALÁ", "MGA.", "", "", ()),
     ("MGA.", "JANA", "", "MALÁ", "", "", ())),
    # the post-nominals: a credential after a comma, where the default
    # reverses the bare one and takes the dotted one for a title
    ("cs", None, "Jan Novák, DrSc",
     ("", "DrSc", "", "Jan Novák", "", "", ()),
     ("", "Jan", "", "Novák", "DrSc", "", ())),
    ("cs", None, "prof. MUDr. Jan Novák, DrSc.",
     ("prof. MUDr. DrSc.", "Jan", "", "Novák", "", "", ()),
     ("prof. MUDr.", "Jan", "", "Novák", "DrSc.", "", ())),
    ("sk", None, "Jozef Mrkva, ArtD.",
     ("ArtD.", "Jozef", "", "Mrkva", "", "", ()),
     ("", "Jozef", "", "Mrkva", "ArtD.", "", ())),
    # the salutation and the birth marker, each converted from an
    # exclusion; pl's pan with cs's
    ("cs", None, "Pan Jan Novák",
     ("", "Pan", "Jan", "Novák", "", "", ()),
     ("Pan", "Jan", "", "Novák", "", "", ())),
    ("pl", None, "Pan Jan Kowalski",
     ("", "Pan", "Jan", "Kowalski", "", "", ()),
     ("Pan", "Jan", "", "Kowalski", "", "", ())),
    ("cs", None, "Jana Nováková roz. Svobodová",
     ("", "Jana", "Nováková roz.", "Svobodová", "", "", ()),
     ("", "Jana", "", "Nováková", "", "Svobodová", ())),
    # the generations 3c wrote, turned on by each language's pack; the
    # gated st reports the fork, the ungated ml does not
    ("sl", None, "Janez Novak st.",
     ("st.", "Janez", "", "Novak", "", "", ()),
     ("", "Janez", "", "Novak", "st.", "", ("SUFFIX_OR_NAME",))),
    ("hr", None, "Ivan Horvat ml.",
     ("", "Ivan", "Horvat", "ml.", "", "", ()),
     ("", "Ivan", "", "Horvat", "ml.", "", ())),
    # behind a title-particle head after a family comma, the trailing
    # peel takes ml.; the gated st. stays in the given part unreported,
    # as the default reads fils there (Dumas, Freiherr von Berg fils)
    ("cs", None, "Novák, Freiherr von Berg ml.",
     ("Freiherr", "von Berg ml.", "", "Novák", "", "", ()),
     ("Freiherr", "von Berg", "", "Novák", "ml.", "", ())),
    # one word before a family comma: the dotted st. is a title by H2's
    # shape, reported suffix-or-name as the default reports Dumas, fils.;
    # the ungated ml. is the suffix
    ("cs", None, "Novák, st.",
     ("st.", "", "", "Novák", "", "", ()),
     ("st.", "", "", "Novák", "", "", ("SUFFIX_OR_NAME",))),
    ("cs", None, "Novák, ml.",
     ("ml.", "", "", "Novák", "", "", ()),
     ("", "", "", "Novák", "ml.", "", ())),
    ("cs", None, "Novák, Freiherr von Berg st.",
     ("Freiherr", "von Berg", "", "st. Novák", "", "",
      ("PARTICLE_OR_GIVEN",)),
     ("Freiherr", "von Berg st.", "", "Novák", "", "", ())),
    # the costs: Pan the surname, Roz the given name, and the Saint
    # readings of st, which a choice of fr keeps
    ("cs", None, "Smith, Pan",
     ("", "Pan", "", "Smith", "", "", ()),
     ("Pan", "", "", "Smith", "", "", ())),
    ("cs", None, "Pan Wei",
     ("", "Pan", "", "Wei", "", "", ()),
     ("Pan", "", "", "Wei", "", "", ())),
    ("cs", None, "Rosalind Roz Smith",
     ("", "Rosalind", "Roz", "Smith", "", "", ()),
     ("", "", "", "Rosalind", "", "Smith", ())),
    ("cs", None, "St Clair Smith",
     ("St", "Clair", "", "Smith", "", "", ()),
     ("", "St", "", "Clair Smith", "", "", ())),
    ("cs+fr", None, "St Clair Smith",
     ("St", "Clair", "", "Smith", "", "", ()),
     ("St", "Clair", "", "Smith", "", "", ())),
    # the patch, two family names (rules/O6): a married double
    # surname written without a hyphen stays whole, behind a title
    # too and under a family-first order, and the cost, two given
    # names, pays for it; a family comma, where O6 stands down,
    # keeps both as the default reads them
    # (decisions/vocabulary-model's 2026-10-30 phase 3f amended entry)
    ("cs", None, "Alena Pešová Řehořová",
     ("", "Alena", "Pešová", "Řehořová", "", "", ()),
     ("", "Alena", "", "Pešová Řehořová", "", "", ())),
    ("cs", None, "Ing. Alena Pešová Řehořová",
     ("Ing.", "Alena", "Pešová", "Řehořová", "", "", ()),
     ("Ing.", "Alena", "", "Pešová Řehořová", "", "", ())),
    ("cs", "FAMILY_FIRST", "Pešová Řehořová Alena",
     ("", "Řehořová", "Alena", "Pešová", "", "", ()),
     ("", "Alena", "", "Pešová Řehořová", "", "", ())),
    ("sk", None, "Mária Nováková Kováčová",
     ("", "Mária", "Nováková", "Kováčová", "", "", ()),
     ("", "Mária", "", "Nováková Kováčová", "", "", ())),
    ("cs", None, "Petr Pavel Novák",
     ("", "Petr", "Pavel", "Novák", "", "", ()),
     ("", "Petr", "", "Pavel Novák", "", "", ())),
    ("sk", None, "Ján Peter Mrkva",
     ("", "Ján", "Peter", "Mrkva", "", "", ()),
     ("", "Ján", "", "Peter Mrkva", "", "", ())),
    ("cs", None, "Pešová Řehořová, Alena",
     ("", "Alena", "", "Pešová Řehořová", "", "", ()),
     ("", "Alena", "", "Pešová Řehořová", "", "", ())),
    ("cs", None, "Novák, Petr Pavel",
     ("", "Petr", "Pavel", "Novák", "", "", ()),
     ("", "Petr", "Pavel", "Novák", "", "", ())),
    # left alone: a bare title ending the given part is a name word
    # (rules/H5), the title Mgr was one already, and BC, excluded for
    # the US credential it spells, stays one (cs.toml's bc)
    ("cs", "FAMILY_FIRST_GIVEN_LAST", "Novák, Jan MUDr",
     ("", "Jan", "MUDr", "Novák", "", "", ()),
     ("", "Jan", "MUDr", "Novák", "", "", ())),
    ("cs", None, "Mgr Jana Nováková",
     ("Mgr", "Jana", "", "Nováková", "", "", ()),
     ("Mgr", "Jana", "", "Nováková", "", "", ())),
    # PMHNP, listed since #993, no longer reports a comma structure of
    # its own; BC's remains
    ("cs", None, "Lora L. Beebe, PhD, PMHNP, BC",
     ("", "Lora", "L.", "Beebe", "PhD, PMHNP, BC", "",
      ("COMMA_STRUCTURE",)),
     ("", "Lora", "L.", "Beebe", "PhD, PMHNP, BC", "",
      ("COMMA_STRUCTURE",))),
])
def test_the_west_and_south_slavic_packs_read_what_the_default_refuses(
        tags: str, order: str | None, name: str,
        default: tuple[object, ...], packed: tuple[object, ...]) -> None:
    base = Parser(policy=_ORDERS[order])
    chosen = frozenset(tags.split("+"))
    # a shipped pack where one is registered; pl, and two tags, as a
    # choice of languages of the same shape
    pack = (locales.get(tags) if tags in locales.available() else
            Locale(code="choice", lexicon=Lexicon.empty(), languages=chosen))
    assert pack.languages == chosen

    def fields(n: ParsedName) -> tuple[object, ...]:
        return (n.title, n.given, n.middle, n.family, n.suffix, n.maiden,
                tuple(a.kind.name for a in n.ambiguities))
    assert (fields(base.parse(name)),
            fields(parser_for(pack, base=base).parse(name))) == (
        default, packed)


def test_the_west_and_south_slavic_packs_repair_their_titles_case() -> None:
    # the readings' cased masks join with them, so capitalized() writes
    # the title as Czech does under the pack, and since #1115 by default
    # for a title the default reads; one only the pack reads (MgA) is
    # left to the default's repair otherwise
    cs = parser_for(locales.CS)
    assert str(cs.capitalized(cs.parse("mudr. jan novák"))) == (
        "MUDr. Jan Novák")
    assert str(parse("mudr. jan novák").capitalized()) == "MUDr. Jan Novák"
    assert str(cs.capitalized(cs.parse("mga. jan novák"))) == (
        "MgA. Jan Novák")
    assert str(parse("mga. jan novák").capitalized()) == "Mga. Jan Novák"


# -- 3h: the Irish, Scottish Gaelic and Brazilian Portuguese packs --
#
# Each row is a name in a shape the sweeps reach (comma shapes, one
# case, dotted and bare, a leading word, a family-comma head), read by
# the default and then under the pack, as (given, middle, family,
# suffix, ambiguity kinds). The default's reading is the refusal the
# pack lifts, so a row that moved by default fails here as well as in
# the snapshot (decisions/vocabulary-model's 2026-10-30 phase 3h entry).
_GA_NIC = ("Máire", "", "Nic Gabhann", "", ())
_3H_ROWS = [
    # the clan particles mid-name: middle by default, the surname's
    # first word under the pack, as `ní` and `ó` read in both
    ("GA", "Máire Nic Gabhann", ("Máire", "Nic", "Gabhann", "", ()), _GA_NIC),
    ("GA", "Máire Mhic Gabhann",
     ("Máire", "Mhic", "Gabhann", "", ()), ("Máire", "", "Mhic Gabhann", "", ())),
    ("GA", "Máire Uí Bhriain",
     ("Máire", "Uí", "Bhriain", "", ()), ("Máire", "", "Uí Bhriain", "", ())),
    ("GA", "MÁIRE UÍ BHRIAIN",
     ("MÁIRE", "UÍ", "BHRIAIN", "", ()), ("MÁIRE", "", "UÍ BHRIAIN", "", ())),
    ("GA", "Pádraig Mic Cárthaigh",
     ("Pádraig", "Mic", "Cárthaigh", "", ()),
     ("Pádraig", "", "Mic Cárthaigh", "", ())),
    ("GD", "Màiri Nic Leòid",
     ("Màiri", "Nic", "Leòid", "", ()), ("Màiri", "", "Nic Leòid", "", ())),
    # a never-given particle opening the name starts the family (rules/P1)
    ("GA", "Uí Bhriain", ("Uí", "", "Bhriain", "", ()), ("", "", "Uí Bhriain", "", ())),
    # Nic and Mic are given names too: a leading one stays given, reported
    ("GA", "Nic Cage",
     ("Nic", "", "Cage", "", ()), ("Nic", "", "Cage", "", ("PARTICLE_OR_GIVEN",))),
    ("GD", "Nic Cage",
     ("Nic", "", "Cage", "", ()), ("Nic", "", "Cage", "", ("PARTICLE_OR_GIVEN",))),
    ("GA", "Mic Jagger",
     ("Mic", "", "Jagger", "", ()), ("Mic", "", "Jagger", "", ("PARTICLE_OR_GIVEN",))),
    # the comma shapes: a full surname before the comma is unchanged;
    # one ending the given part joins the surname as `Ní` does by default
    ("GA", "Nic Gabhann, Máire", _GA_NIC, _GA_NIC),
    ("GA", "Gabhann, Máire Nic",
     ("Máire", "Nic", "Gabhann", "", ()),
     ("Máire", "", "Nic Gabhann", "", ("PARTICLE_OR_GIVEN",))),
    ("GA", "Gabhann, Máire Ní", _GA_NIC[:2] + ("Ní Gabhann", "", ()),
     _GA_NIC[:2] + ("Ní Gabhann", "", ())),
    ("GA", ", Máire Uí Bhriain",
     ("Máire", "Uí Bhriain", "", "", ()), ("Máire", "Uí Bhriain", "", "", ())),
    # a surname that is the word alone keeps it
    ("GA", "Ioana Mic", ("Ioana", "", "Mic", "", ()), ("Ioana", "", "Mic", "", ())),
    # SB: the family name by default, gated by the count under the
    # pack as sobrinho is (rules/S11)
    ("PT_BR", "JOSE CARLOS SILVA SB",
     ("JOSE", "CARLOS SILVA", "SB", "", ()),
     ("JOSE", "CARLOS", "SILVA", "SB", ("SUFFIX_OR_NAME",))),
    ("PT_BR", "José Silva Sb.",
     ("José", "Silva", "Sb.", "", ()),
     ("José", "", "Silva", "Sb.", ("SUFFIX_OR_NAME",))),
    ("PT_BR", "SILVA, JOSE CARLOS SB",
     ("JOSE", "CARLOS SB", "SILVA", "", ()),
     ("JOSE", "CARLOS", "SILVA", "SB", ("SUFFIX_OR_NAME",))),
    ("PT_BR", ", JOSE SILVA SB",
     ("JOSE", "SILVA SB", "", "", ()), ("JOSE", "SILVA", "", "SB", ("SUFFIX_OR_NAME",))),
    # with no words to spare it keeps the family, reported
    ("PT_BR", "Ana SB", ("Ana", "", "SB", "", ()), ("Ana", "", "SB", "", ("SUFFIX_OR_NAME",))),
    # an agnomen before a family comma stays in the surname, as FILHO does
    ("PT_BR", "SILVA SB, JOSE CARLOS",
     ("JOSE", "CARLOS", "SILVA SB", "", ()), ("JOSE", "CARLOS", "SILVA SB", "", ())),
    # the dotted S.B. after a comma is paired initials either way (rules/C5)
    ("PT_BR", "John Smith, S.B.",
     ("S.", "B.", "John Smith", "", ("SUFFIX_OR_NAME",)),
     ("S.", "B.", "John Smith", "", ("SUFFIX_OR_NAME",))),
    # F and N, written as an initial is, are excluded, the pack included
    # (pt-BR.toml): the family name they spell, by default and under it
    ("PT_BR", "JOSE CARLOS SILVA F",
     ("JOSE", "CARLOS SILVA", "F", "", ()), ("JOSE", "CARLOS SILVA", "F", "", ())),
    ("PT_BR", "Pedro Alves N.",
     ("Pedro", "Alves", "N.", "", ()), ("Pedro", "Alves", "N.", "", ())),
    # the letter as an initial: before the surname, or leading, unchanged
    ("PT_BR", "JOHN F KENNEDY",
     ("JOHN", "F", "KENNEDY", "", ()), ("JOHN", "F", "KENNEDY", "", ())),
    ("PT_BR", "F. Silva", ("F.", "", "Silva", "", ()), ("F.", "", "Silva", "", ())),
    # a family comma with a title-particle head: the given part's walk
    # keeps it a name word under the pack too
    ("PT_BR", "Smith, Freiherr von Berg SB",
     ("von Berg SB", "", "Smith", "", ()), ("von Berg SB", "", "Smith", "", ())),
]


@pytest.mark.parametrize("code, name, default, packed", _3H_ROWS,
                         ids=[f"{r[0]}:{r[1]}" for r in _3H_ROWS])
def test_the_3h_packs_lift_the_defaults_refusal(
        code: str, name: str, default: tuple[object, ...],
        packed: tuple[object, ...]) -> None:
    assert (_fields(parse(name)),
            _fields(parser_for(locales.get(code)).parse(name))) == (
        default, packed)


@pytest.mark.parametrize("order", [FAMILY_FIRST, FAMILY_FIRST_GIVEN_LAST])
@pytest.mark.parametrize("code, name, default, packed", [
    # a never-given particle opening the name takes one name unit under a
    # family-first order (rules/P1), where the default reads the
    # particle alone as the family name
    ("GA", "Uí Bhriain Máire", ("Uí", ""), ("Uí Bhriain", "")),
    # a possibly-given one is left to position, by default and under
    # the pack alike
    ("GD", "Nic Leòid Màiri", ("Nic", ""), ("Nic", "")),
    # the agnomen ends the name under either order (family, suffix)
    ("PT_BR", "SILVA JOSE CARLOS SB", ("SILVA", ""), ("SILVA", "SB")),
])
def test_the_3h_packs_under_a_family_first_order(
        order: object, code: str, name: str, default: tuple[str, str],
        packed: tuple[str, str]) -> None:
    policy = Policy(name_order=order)  # type: ignore[arg-type]
    by_default = Parser(policy=policy).parse(name)
    by_pack = parser_for(locales.get(code), base=Parser(policy=policy)).parse(name)
    assert ((by_default.family, by_default.suffix),
            (by_pack.family, by_pack.suffix)) == (default, packed)


@pytest.mark.parametrize("force", [False, True])
@pytest.mark.parametrize("code, text, repaired", [
    ("GA", "MÁIRE NIC GIOLLA PHÁDRAIG", "Máire Nic Giolla Phádraig"),
    ("GD", "MÁIRE NIC GIOLLA PHÁDRAIG", "Máire Nic Giolla Phádraig"),
    ("GA", "MÁIRE MHIC GABHANN", "Máire Mhic Gabhann"),
    ("GA", "SEÁN MIC GABHANN", "Seán Mic Gabhann"),
    ("GA", "MÁIRE UÍ BHRIAIN", "Máire Uí Bhriain"),
    ("GA", "máire nic gabhann", "Máire Nic Gabhann"),
])
def test_the_irish_particles_keep_their_capital_under_their_pack(
        code: str, text: str, repaired: str, force: bool) -> None:
    # Irish writes these capitalized, as the default's repair does; a
    # particle reading without a mask is lowercased by case repair
    # (rules/R4), so each turned-on reading carries its own `cased`
    packed = parser_for(locales.get(code))
    assert str(parse(text).capitalized(force=force)) == repaired
    assert str(packed.capitalized(packed.parse(text), force=force)) == repaired


def test_the_pt_br_pack_selects_pt_too() -> None:
    # pt-BR selects its ancestor's file (decisions/vocabulary-model's 3b
    # entry, item 6): Portuguese `e` is a connective in a one-case name
    packed = parser_for(locales.PT_BR)
    assert parse("ANA SILVA E SOUZA").family == "SOUZA"
    assert packed.parse("ANA SILVA E SOUZA").family == "SILVA E SOUZA"


def test_the_sb_mask_keeps_the_degrees_capitals_under_pt_br() -> None:
    # SB listed as an agnomen was recased to Sb by force (pt-BR.toml's
    # note); the reading's mask keeps it SB, and only under the pack
    packed = parser_for(locales.PT_BR)
    name = packed.parse("jose carlos silva sb")
    assert str(packed.capitalized(name, force=True)) == "Jose Carlos Silva SB"
    assert str(parse("jane doe sb").capitalized(force=True)) == "Jane Doe Sb"


# -- #269: non-Latin default vocabulary (Cyrillic, Greek, Arabic,
# Hebrew, Devanagari, Bengali) --
#
# This is DEFAULT vocabulary (nameparser/vocab/*.toml, which file a
# word is in by its language), not a locale pack -- it lives here
# because it's the non-Latin counterpart to the pack tests above. Every
# row was verified live against a runtime-augmented Lexicon.default()
# before the data landed (2026-07-17), so these pin actual observed
# behavior, not guesses -- see the per-script comments below for the
# rows that came out differently than a first guess would suggest.
# The Devanagari block grew and a Bengali one opened on 2026-09-06
# with the Indic honorific bundle (#346/#344/#343); those rows were confirmed the
# same way, live against a runtime-augmented Lexicon.default() before
# the data landed. See decisions/indic-honorifics.
@pytest.mark.parametrize("name, field, expected", [
    # Cyrillic (ru/uk) titles.
    ("г-н Иван Петров", "title", "г-н"),
    ("г-жа Мария Иванова", "title", "г-жа"),
    ("д-р Мария Иванова", "title", "д-р"),
    ("проф Петро Шевченко", "title", "проф"),
    ("акад Іван Франко", "title", "акад"),
    ("пан Тарас Шевченко", "title", "пан"),
    ("пані Марія Іванова", "title", "пані"),
    # Cyrillic conjunction "и": v1's single-letter carve-out (Google
    # Code issue 11, the "john e smith" bug) treats a bare
    # single-alphabetic-character conjunction in a short name as more
    # likely an initial (group._group_segment), so a 3-piece chain
    # ("проф и акад Іван Франко") does NOT join -- "и" reads as a given
    # name instead. The chain only joins once the segment has enough
    # rootname pieces (total >= 4); pinned against that actual behavior
    # with a 5-piece name instead of the shorter guess.
    ("проф и акад Тарас Григорович Шевченко", "title", "проф и акад"),
    ("проф та акад Іван Франко", "title", "проф та акад"),
    # Ukrainian "і" is single-character like "и", so the same
    # single-letter carve-out applies: pinned with a 5-piece name.
    ("проф і акад Тарас Григорович Шевченко", "title", "проф і акад"),
    # Ukrainian "й" is the euphonic alternate of "і" (the two swap by
    # surrounding vowel/consonant, so real data carries both) -- same
    # single-letter carve-out, pinned with the same 5-piece shape.
    ("проф й акад Тарас Григорович Шевченко", "title", "проф й акад"),
    # ...and joining two given names, the shape #267's reporter raised:
    # a bare Cyrillic letter between given names reads as the
    # conjunction, not an initial (Cyrillic typography writes initials
    # with periods -- see
    # test_267_dotted_cyrillic_initial_wins_over_conjunction).
    ("Олесь й Олена Коваленки", "given", "Олесь й Олена"),
    # Greek titles + conjunction (και has 3 letters, so the single-char
    # initial carve-out above never applies to it). Bare κ is NOT
    # shipped -- it collides with the initial+surname shape (see the
    # regression test below).
    # Match-time contract of the lower()-not-casefold() normalization
    # (review 2026-07-19): case variants that lower() folds still
    # match; the ASCII-SS spelling of ß does NOT (v1-parity -- casefold
    # would have matched it, at the cost of mutating stored spellings).
    ("ΚΟΣ Γιώργος Παπαδόπουλος", "title", "ΚΟΣ"),
    ("GROẞFÜRST Otto Schmidt", "title", "GROẞFÜRST"),
    ("GROSSFÜRST Otto Schmidt", "title", ""),
    ("δρ Νίκος Παπαδόπουλος", "title", "δρ"),
    ("κος Γιώργος Παπαδόπουλος", "title", "κος"),
    ("κα Μαρία Παπαδοπούλου", "title", "κα"),
    ("καθ και δρ Νίκος Παπαδόπουλος", "title", "καθ και δρ"),
    # Arabic patronymic/clan prefixes: non-leading "بن"/"بنت" chain onto
    # the family, mirroring the Latin "von"/"bin" prefix-chain rule.
    ("محمد بن سلمان", "family", "بن سلمان"),
    ("فاطمة بنت محمد", "family", "بنت محمد"),
    # "ابن" (alternate spelling) and the clan prefix "آل" are
    # never-given: non-leading they chain onto the family, and a
    # LEADING "آل" consumes the whole name as family (no given), like
    # "de Mesnil".
    ("محمد ابن رشد", "family", "ابن رشد"),
    ("محمد آل سعود", "family", "آل سعود"),
    ("آل سعود", "family", "آل سعود"),
    ("آل سعود", "given", ""),
    # Persian writes yeh and kaf with letters of their own (U+06CC,
    # U+06A9), so ar.toml's titles are listed again in them as
    # same_as spellings (#1151).
    ("الدکتور محمد علی", "title", "الدکتور"),
    ("الشیخ محمد علی", "given", "محمد"),
    ("دکتور محمد رضایی", "title", "دکتور"),
    # Persian's own titles (fa.toml) are plain titles, addressing the
    # family name as "Dr. Smith" does: ar.toml's, the given name.
    ("دکتر محمد رضایی", "title", "دکتر"),
    ("دکتر رضایی", "family", "رضایی"),
    # Persian typed on an Arabic keyboard writes ي and ك: listed too.
    ("دكتر محمد رضایی", "title", "دكتر"),
    ("آقاي رضایی", "title", "آقاي"),
    ("سرلشكر قاسم سلیمانی", "title", "سرلشكر"),
    ("آقای دکتر علی رضایی", "title", "آقای دکتر"),
    ("آیت‌الله جناب آقای حسن رضایی", "title", "آیت‌الله جناب آقای"),
    ("حجت‌الاسلام حسن رضایی", "title", "حجت‌الاسلام"),
    ("حجةالاسلام حسن رضایی", "title", "حجةالاسلام"),
    ("سرلشکر علی رضایی", "title", "سرلشکر"),
    ("خانم زهرا احمدی", "title", "خانم"),
    # خانم after the name is Khanum, a name word: only the front claims.
    ("زهرا خانم", "family", "خانم"),
    # The words that open real Persian family names stay out (#1151).
    ("شیخ احمدی، حسن", "family", "شیخ احمدی"),
    # The Arabic tatweel only stretches a word: it is the same title.
    ("الدكتــور خالد سالم", "title", "الدكتــور"),
    # The hamza-less spelling "ال" standing alone is the same clan
    # prefix (#1150): 15 of JRC-Names' 28 standalone ones, none the
    # article split from its word.
    ("سارة علي ال ناصر", "family", "ال ناصر"),
    ("سارة علي ال ناصر", "middle", "علي"),
    ("حسن علي محمد ال يحيى", "family", "ال يحيى"),
    ("ال الشيخ", "family", "ال الشيخ"),
    ("ال الشيخ", "given", ""),
    # The kunya "أبو"/"ابو" is AMBIGUOUS (it can begin a standalone
    # byname): leading it reads as the given name -- the "Van Johnson"
    # rule -- while non-leading it chains onto the family like any
    # particle.
    ("أبو مازن", "given", "أبو"),
    ("أحمد أبو خليل", "family", "أبو خليل"),
    ("علي ابو خالد", "family", "ابو خالد"),
    # "الشيخ" is a given-name title: a single following name reads as
    # given, not family. Its transliteration 'sheikh' is a title only
    # inside a title phrase since #752 phase 2j, so 'Sheikh Mohammed'
    # reads given 'Sheikh'; the article form is no given name.
    ("الشيخ محمد", "given", "محمد"),
    # Arabic honorifics precede the GIVEN name, so all ship in
    # given_name_titles like الشيخ: article forms (never given names)
    # and the bare doctor/professor/engineer forms (not used as given
    # names). Deferred with the same collision rule as мл/ст: bare
    # سيد/شيخ/أمير/سلطان (common given names) and the 'د.'
    # abbreviation (bare 'د' would swallow initials, the bare-κ trap).
    ("الدكتور أحمد", "given", "أحمد"),
    ("الدكتور أحمد", "title", "الدكتور"),
    ("الدكتورة منى السيد", "title", "الدكتورة"),
    ("الدكتورة منى السيد", "family", "السيد"),
    ("دكتور أحمد", "given", "أحمد"),
    ("دكتورة منى", "given", "منى"),
    ("الأستاذ محمود", "given", "محمود"),
    ("أستاذ محمود", "given", "محمود"),
    ("أستاذة سلمى", "given", "سلمى"),
    ("الأستاذة سلمى", "given", "سلمى"),
    ("مهندس حسن", "given", "حسن"),
    ("الشيخة موزة", "given", "موزة"),
    ("الحاجة فاطمة", "given", "فاطمة"),
    # compound with the bound given name: title + bound join + family
    ("الحاج عبد الرحمن السيد", "title", "الحاج"),
    ("الحاج عبد الرحمن السيد", "given", "عبد الرحمن"),
    ("الحاج عبد الرحمن السيد", "family", "السيد"),
    # a given-name title plus the bound pair ALONE: the licence
    # (rules/P5, #369) lifts the family reserve, so the pair is the
    # given name and, as for "Sir John", there is no family. Thirteen
    # of the given-name titles are this script's, so this is where
    # the licence mostly fires.
    ("الشيخ عبد الله", "title", "الشيخ"),
    ("الشيخ عبد الله", "given", "عبد الله"),
    ("الشيخ عبد الله", "family", ""),
    # "و" ("and") joins title chains like Cyrillic "и"; single-char
    # conjunctions need the same single-letter carve-out headroom (enough
    # rootname pieces), so pinned with the 6-piece shape the и row uses
    ("الأستاذ و الدكتور طارق حسن السيد", "title", "الأستاذ و الدكتور"),
    # Hebrew patronymic prefixes: same non-leading chain-onto-family
    # behavior.
    ("דוד בן גוריון", "family", "בן גוריון"),
    ("שרה בת אברהם", "family", "בת אברהם"),
    # Hebrew "מר" title (plain title, not GIVEN_NAME_TITLES -- like
    # 'mr', the following name reads as family).
    ("מר דוד לוי", "title", "מר"),
    # Hebrew title/suffix sweep (#269 follow-up): plain titles (Israeli
    # convention: family follows, the מר precedent); both geresh/
    # gershayim spellings ship where an abbreviation carries one.
    ("גברת רות כהן", "title", "גברת"),
    ("פרופ' דוד לוי", "title", "פרופ'"),
    ("פרופ׳ דוד לוי", "title", "פרופ׳"),
    ("פרופסור רות כהן", "title", "פרופסור"),
    ('עו"ד דוד לוי', "title", 'עו"ד'),
    ("עו״ד דוד לוי", "title", "עו״ד"),
    ("הרב עובדיה יוסף", "title", "הרב"),
    # post-nominal Hebrew suffixes: ז"ל ("of blessed memory") and
    # שליט"א (honorific for living rabbis) -- suffix words, exact
    # token incl. the mid-word gershayim (inert in extraction, like
    # the ד"ר title)
    ('משה כהן ז"ל', "suffix", 'ז"ל'),
    ("משה כהן ז״ל", "suffix", "ז״ל"),
    ('הרב משה פיינשטיין שליט"א', "suffix", 'שליט"א'),
    ("הרב משה פיינשטיין שליט״א", "title", "הרב"),
    # Devanagari (hi/mr) titles -- a new #269 script: श्री/श्रीमती are
    # the Mr./Mrs. analogs, डॉ the Dr. abbreviation (edge-period
    # normalization makes "डॉ." match too). NO Latin twins on purpose:
    # transliterated sri/shri collide with real given names (Sri
    # Mulyani); the native script cannot.
    ("श्री राम शर्मा", "title", "श्री"),
    ("श्रीमती सीता शर्मा", "title", "श्रीमती"),
    ("डॉ राम शर्मा", "title", "डॉ"),
    ("डॉ. राम शर्मा", "title", "डॉ."),
    # Geresh/gershayim gate (#269 step 2): probed live against
    # extract_delimited's _open_ok/_close_ok boundary rules. Both the
    # ASCII-quote spelling and the typographic Unicode spelling of
    # "doctor"/"Mrs." survive extraction untouched -- the quote sits
    # mid-word (no preceding whitespace before '"', and for the
    # trailing "'" no following word boundary), so it never satisfies
    # the boundary-valid open/close test and is left as literal text.
    # Both spellings are shipped; see their notes in nameparser/vocab/he.toml.
    ('ד"ר דוד לוי', "title", 'ד"ר'),
    ("גב' דוד לוי", "title", "גב'"),
    ("ד״ר דוד לוי", "title", "ד״ר"),
    ("גב׳ דוד לוי", "title", "גב׳"),
    # Indic trailing honorifics (#344/#343) -- SUFFIX_WORDS, spaced
    # only. These rows need none of the Devanagari/Bengali title
    # vocabulary; the trailing path reads the suffix set alone.
    ("नरेन्द्र मोदी जी", "suffix", "जी"),
    ("नरेन्द्र मोदी जी", "family", "मोदी"),
    # The glued prohibition, both shapes. जी is deliberately NOT a
    # honorific_tails entry: Banerjee/Mukherjee/Chatterjee end in the
    # substring and a glued peel strands a fragment on a bare virama
    # (बनर् + जी). गांधीजी staying unpeeled is the accepted cost.
    ("अमित बनर्जी", "family", "बनर्जी"),
    ("अमित बनर्जी", "suffix", ""),
    ("बनर्जी", "given", "बनर्जी"),
    ("बनर्जी", "suffix", ""),
    ("गांधीजी", "given", "गांधीजी"),
    ("गांधीजी", "suffix", ""),
    # Bengali trailing honorific. One name word plus a suffix reads
    # GIVEN, not family -- H1 never fires, there being no title.
    ("রহমান সাহেব", "suffix", "সাহেব"),
    ("রহমান সাহেব", "given", "রহমান"),
    ("রহমান সাহেব", "family", ""),
    # বাবু is TRAILING in Bengali where Devanagari बाबू is LEADING.
    # Different codepoints, so the two cannot interact -- and a sweep
    # "harmonizing" them changes four parses and, without these rows,
    # reddens nothing (decisions/indic-honorifics).
    ("অমল বাবু", "suffix", "বাবু"),
    ("অমল বাবু", "given", "অমল"),
    ("बाबू अमल", "title", "बाबू"),
    ("बाबू अमल", "family", "अमल"),
    # Devanagari honorifics (#344). The renunciate set folds like the
    # Latin one: स्वामी/गुरु/बाबा/संत are given-name titles, so one
    # following name is a GIVEN name and the family is empty.
    ("स्वामी विवेकानंद", "title", "स्वामी"),
    ("स्वामी विवेकानंद", "given", "विवेकानंद"),
    ("स्वामी विवेकानंद", "family", ""),
    # Two name words: H1's fold needs exactly one, so the family
    # survives. This is the boundary the ledger's probes also pin.
    ("स्वामी शिवानंद सरस्वती", "given", "शिवानंद"),
    ("स्वामी शिवानंद सरस्वती", "family", "सरस्वती"),
    # संत ships and Latin Sant deliberately does not (Sant Singh is a
    # Punjabi given name) -- the script asymmetry, executable.
    ("संत कबीर", "title", "संत"),
    ("संत कबीर", "given", "कबीर"),
    ("Sant Kabir", "given", "Sant"),
    ("Sant Kabir", "family", "Kabir"),
    # The civil control: a TITLES-only Devanagari honorific families
    # the one name word, exactly as श्री/डॉ have since 2.0.0.
    ("डॉक्टर शर्मा", "title", "डॉक्टर"),
    ("डॉक्टर शर्मा", "family", "शर्मा"),
    # Bengali honorifics (#343) -- a new #269 script. The renunciate
    # set folds as it does in Devanagari and Latin.
    ("স্বামী বিবেকানন্দ", "title", "স্বামী"),
    ("স্বামী বিবেকানন্দ", "given", "বিবেকানন্দ"),
    ("স্বামী বিবেকানন্দ", "family", ""),
    # শ্রীল is renunciate and folds the same way; unprefixed শ্রী is
    # civil, so it families the one name word instead.
    ("শ্রীল প্রভুপাদ", "given", "প্রভুপাদ"),
    ("শ্রীল প্রভুপাদ", "family", ""),
    ("শ্রী সেন", "title", "শ্রী"),
    ("শ্রী সেন", "family", "সেন"),
    # Vocabulary beats the initial reading: 'ড.' is is_initial-shaped
    # and the title entry wins, which is the fork #343 asked about.
    ("ড. মুহাম্মদ ইউনূস", "title", "ড."),
    ("ড. মুহাম্মদ ইউনূস", "given", "মুহাম্মদ"),
    ("ড. মুহাম্মদ ইউনূস", "family", "ইউনূস"),
    # ... and real Bengali initials are untouched, because no entry
    # matches them. The negative control for the row above.
    ("র. কে. নারায়ণ", "given", "র."),
    ("র. কে. নারায়ণ", "middle", "কে."),
    ("র. কে. নারায়ণ", "family", "নারায়ণ"),
    # These mirrored Latin md until #853 made a leading Md the given
    # name (cases.py's audit_md_leading_is_the_given_name); the Bengali
    # spellings stay titles, no filed data reaching them. Both
    # spellings of the abbreviation ship: the visarga form মোঃ (the visarga ঃ (U+0983) is a spacing
    # combining mark, and the lookup fold strips only edge periods and
    # whitespace, so it reaches the lexicon intact) and the period
    # form মো., which matches the bare stem মো through the edge-period
    # normalization.
    ("মোঃ আবদুল করিম", "title", "মোঃ"),
    ("মোঃ আবদুল করিম", "given", "আবদুল"),
    ("মোঃ আবদুল করিম", "family", "করিম"),
    ("মো. আবদুল করিম", "title", "মো."),
    ("মো. আবদুল করিম", "given", "আবদুল"),
    ("মো. আবদুল করিম", "family", "করিম"),
    # the women's form, period spelling; the visarga form rides the same entry pattern
    ("মোসা. ফাতেমা বেগম", "title", "মোসা."),
    ("মোসা. ফাতেমা বেগম", "given", "ফাতেমা"),
    ("মি. রহমান", "title", "মি."),
    ("মি. রহমান", "family", "রহমান"),
    # The exclusion holds: ঠাকুর is Tagore, a surname, and is
    # deliberately not a title (its `excluded` entry in
    # nameparser/vocab/bn.toml).
    # LEADING position is where the exclusion is load-bearing --
    # TITLES is leading-only, so the trailing spelling reads the same
    # whether or not the word ships and cannot guard anything.
    ("রবীন্দ্রনাথ ঠাকুর", "family", "ঠাকুর"),
    ("ঠাকুর রবীন্দ্রনাথ", "given", "ঠাকুর"),
    ("ঠাকুর রবীন্দ্রনাথ", "title", ""),
])
def test_269_nonlatin_vocabulary_parses(
        name: str, field: str, expected: str) -> None:
    assert getattr(parse(name), field) == expected


def test_a_choice_of_fa_reads_a_persian_engineer_as_a_title_for_the_family() -> None:
    """#1151: مهندس is one word in Arabic and Persian. ar.toml's reading
    addresses the given name (Egyptian usage) and the default keeps it;
    fa.toml's, written default = false, addresses the family name, and
    a choice of fa takes it over ar.toml's."""
    fa = parser_for(Locale(code="fa", lexicon=Lexicon.empty(),
                           languages=frozenset({"fa"})))
    assert parse("مهندس رضایی").given == "رضایی"
    assert fa.parse("مهندس رضایی").family == "رضایی"
    assert fa.parse("مهندس رضایی").title == "مهندس"


def test_269_vocabulary_one_row_per_script_and_category() -> None:
    # one row per script, then one per vocabulary category the
    # 2026-07-19 batches added: bound given name, Hebrew post-nominal
    # suffix, Devanagari title (ported from the 2.x facade's twin)
    assert parse("г-н Иван Петров").title == "г-н"
    assert parse("κος Γιώργος Παπαδόπουλος").title == "κος"
    assert parse("محمد بن سلمان").family == "بن سلمان"
    assert parse('ד"ר דוד לוי').title == 'ד"ר'
    assert parse("عبد الرحمن محمد").given == "عبد الرحمن"
    assert parse('משה כהן ז"ל').suffix == 'ז"ל'
    assert parse("डॉ. राम शर्मा").title == "डॉ."


def test_269_bare_greek_kappa_not_a_title() -> None:
    # Regression for the deferred bare 'κ' entry: were it in TITLES,
    # _normalize's edge-period strip would make the abbreviated-initial
    # 'Κ.' match it, degrading the very common initial+surname shape to
    # title='Κ.' with an EMPTY given. Pin the correct reading.
    n = parse("Κ. Παπαδόπουλος")
    assert n.title == ""
    assert n.given == "Κ."
    assert n.family == "Παπαδόπουλος"


def test_267_dotted_cyrillic_initial_wins_over_conjunction() -> None:
    # Blast-radius guard for the single-letter Cyrillic conjunctions
    # (и/і/й): each is also the first letter of real given names
    # (Игорь, Ірина, Йосип), so the shipped entries would be a trap if
    # membership could outrank a punctuated initial. It cannot -- the
    # initial regex's dotted branch is Unicode-aware -- and #267 settled
    # the BARE letter in the conjunction's favor precisely because
    # Cyrillic typography writes initials with the period.
    for dotted, family in (("И.", "Иванов"), ("І.", "Франко"),
                           ("Й.", "Сліпий")):
        n = parse(f"{dotted} {family}")
        assert n.given == dotted
        assert n.family == family


@pytest.mark.parametrize(("pack", "name", "repaired"), [
    (locales.GD, "RONALD MACDONALD", "Ronald MacDonald"),
    (locales.GA, "JOHN MACCARTHY", "John MacCarthy"),
])
@pytest.mark.parametrize("strict", [False, True])
def test_a_gaelic_pack_keeps_the_mac_masks(
        pack: Locale, name: str, repaired: str, strict: bool) -> None:
    # #1014: the Mac masks stand in en.toml and again in gd.toml and
    # ga.toml, so a strict Gaelic choice, which compiles no en.toml
    # reading, still writes the inner capital
    parser = parser_for(pack, strict=strict)
    assert str(parser.capitalized(parser.parse(name))) == repaired


def test_the_es_ar_pack_is_es_with_a_longer_given_name_list() -> None:
    # decisions/O6, 2026-11-04: es's choice (es-AR selects es.toml, no
    # file of its own) and es's [rules], with a list that holds es's
    from nameparser._reading_index import selected
    from nameparser.locales import es_ar as _es_ar
    from nameparser.locales._es_ar_given_names import GIVEN_NAMES as AR
    from nameparser.locales._es_given_names import GIVEN_NAMES as ES
    assert locales.ES_AR == Locale(code="es_ar", lexicon=Lexicon(given_names=AR),
                                   policy=locales.ES.policy,
                                   languages=frozenset({"es-AR"}))
    assert selected(locales.ES_AR.languages) == selected(locales.ES.languages)
    assert ES < AR
    ar, es = _require_packed("es_ar"), _require_packed("es")
    # a word Spain bears mostly as a surname and Argentina as a given name
    assert es.parse("Pablo Sebastián Rosales").family == "Sebastián Rosales"
    assert ar.parse("Pablo Sebastián Rosales").family == "Rosales"
    # two family names still read as two; a word in neither list is taken
    assert ar.parse("Ana García López").family == "García López"
    assert ar.parse("Juan Martín Gómez").family == "Martín Gómez"
    # stacked on es, the union of the lists is es_ar's, and the patches agree
    stacked = parser_for(locales.ES, locales.ES_AR)
    for text in _ROTATORS["es_ar"] + _ROTATORS["es"]:
        assert stacked.parse(text).as_dict() == ar.parse(text).as_dict(), text
    assert _es_ar.DEVIATES("Pablo Sebastián Rosales")
    assert not _es_ar.DEVIATES("Pablo Rosales")


def test_a_strict_choice_keeps_only_the_mac_masks_its_files_hold() -> None:
    # #1014, decisions/R4: ga.toml holds the four Irish masks alone, so
    # a strict Irish choice title-cases a Scottish Mac name, and a strict
    # choice holding none of en, gd and ga keeps no mask at all
    for pack in (locales.GA, locales.ES):
        parser = parser_for(pack, strict=True)
        assert str(parser.capitalized(parser.parse("RONALD MACDONALD"))) == "Ronald Macdonald"
    plain = parser_for(locales.ES)
    assert str(plain.capitalized(plain.parse("RONALD MACDONALD"))) == "Ronald MacDonald"
