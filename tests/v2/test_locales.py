"""The locale pack layer (locales spec §2-3): lazy access, the shipped
packs, composition, and the non-interference gate."""
import functools
import importlib.util
import re
from collections.abc import Callable, Iterable
from types import ModuleType

import pytest

from nameparser import Locale, Parser, locales, parse, parser_for
from nameparser._lexicon import _VOCAB_FIELDS, Lexicon
from nameparser._pipeline._vocab import _SCRIPT_RANGES
from nameparser._policy import UNSET, PatronymicRule, Policy, Script
from nameparser._types import AmbiguityKind
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

# ja is the one pack whose behavior is not pack data: it activates
# segmentation and supplies nothing to segment WITH, so every parse
# through it needs the optional nameparser[ja] segmenter. Probed once
# here; without the extra the ja code has no _PACKED entry, so every
# test that PARSES through the pack skips -- its rotator rows and its
# non-interference run included. What still runs either way is what
# needs no parse: the registry contract (DEVIATES and a rotator list
# exist), the range pin, the pack's contents, and the inertness test
# below, which is the unsegmented pack's whole observable behavior.
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
    assert set(locales.available()) == {"ja", "ru", "tr_az", "zh"}
    with pytest.raises(KeyError, match="ja, ru, tr_az, zh"):
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
# (test_cases.py/test_facade_cases.py). These tests are where the zh
# readings are pinned at unit level, against the stage directly.


def test_zh_composes_with_korean_defaults() -> None:
    # the pack only ADDS (vocabulary + one union field): Korean
    # segmentation keeps working through a zh parser
    n = _PACKED["zh"].parse("김민준")
    assert (n.family, n.given) == ("김", "민준")


def test_zh_han_ranges_stay_in_sync_with_vocab() -> None:
    # zh.py hand-copies the Han spans from _pipeline/_vocab.py for its
    # DEVIATES predicate (layering forbids a pack importing the
    # pipeline -- see the module docstring); pin the equality here, the
    # codepoint-range twin of the marker-regex sync test above.
    assert _zh._HAN_RANGES == _SCRIPT_RANGES[Script.HAN]


def test_ja_pack_contents() -> None:
    assert locales.JA.code == "ja"
    # segmentation activation ONLY: no vocabulary (no list settles a
    # kanji name) and no order (the kana license already reads
    # Japanese family-first by default, amendment 2026-07-29 §1)
    assert locales.JA.policy.segment_scripts == frozenset(
        {Script.HAN, Script.HIRAGANA})
    assert locales.JA.policy.name_order is UNSET
    assert locales.JA.policy.script_orders is UNSET
    assert locales.JA.lexicon == Lexicon.empty()


def test_ja_segmenter_without_extra_raises_helpfully() -> None:
    if _JA_AVAILABLE:
        pytest.skip("namedivider installed; the error path is untestable")
    with pytest.raises(ImportError, match=r"nameparser\[ja\]"):
        locales.ja_segmenter()


def test_ja_ranges_stay_in_sync_with_vocab() -> None:
    # the twin of the zh pin above: ja.py hand-copies the three
    # Japanese-repertoire scripts' spans for DEVIATES and for the
    # adapter's own repertoire check
    assert set(_ja._JA_RANGES) == {
        span for script in (Script.HAN, Script.HIRAGANA, Script.KATAKANA)
        for span in _SCRIPT_RANGES[script]}


def test_ja_pack_alone_is_inert() -> None:
    # The pack's own claim, and the reason it is safe to register
    # without the extra: activating segmentation while shipping nothing
    # to segment WITH changes no parse at all. Pure pack data, so this
    # runs whether or not nameparser[ja] is installed -- and it is the
    # unsegmented pack's entire observable behavior.
    p = parser_for(locales.JA)
    for name in _ROTATORS["ja"]:
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


@_needs_ja
def test_ja_keeps_a_transcribed_name_in_its_source_order() -> None:
    # pure katakana is excluded from the pack's activation by design
    # (amendment §1: katakana is how Japanese writes FOREIGN names), so
    # the nakaguro form divides on the dot and keeps its given-first
    # source order instead of being read family-first
    n = _PACKED["ja"].parse("マイケル・ジャクソン")
    assert (n.given, n.family) == ("マイケル", "ジャクソン")


@_needs_ja
def test_ja_composes_with_zh() -> None:
    # vocabulary first, segmenter on decline (amendment §2)
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
def test_ja_leaves_spaced_names_to_the_default_order() -> None:
    # the segmenter's precondition (see test_parser.py): a spaced name
    # is already divided, and the kana/Han family-first defaults read
    # it correctly with no segmenter involved. Without this the pack
    # would wreck the commonest written form -- 山田 + 太郎 divided
    # again into 山 + 田 + 太郎.
    p = _PACKED["ja"]
    for name in ("山田 太郎", "高橋 みなみ", "高橋 エミ", "山田 太郎 Jr."):
        assert p.parse(name).as_dict() == _default_parse(name), name
    assert p.parse("山田 太郎").family == "山田"


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


def test_pack_vocabulary_entries_are_single_words() -> None:
    # The shipped-vocabulary guard (test_lexicon.py's
    # test_default_lexicon_builds_warning_free), extended to the OTHER
    # vocabulary source: a locale pack's lexicon fields are matched one
    # word at a time same as Lexicon.default()'s, so a multi-word entry
    # in any field but given_name_titles would be dead. Checked
    # directly against field contents (not by capturing the
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
            for entry in getattr(lexicon, field):
                assert entry == "".join(entry.split()), (
                    f"{code}: {field} entry {entry!r} contains "
                    f"whitespace and can never match")


def test_pack_marker_regexes_stay_in_sync_with_post_rules() -> None:
    # ru.py/tr_az.py hand-copy their DEVIATES marker regexes from
    # _pipeline._post_rules (layering forbids a pack importing the
    # pipeline -- see each pack's module docstring). Assert pattern
    # equality mechanically so drift fails here, not at the L6
    # non-interference gate.
    from nameparser._pipeline import _post_rules

    for pack_regex, rule_regex in (
        (_ru._EAST_SLAVIC, _post_rules._EAST_SLAVIC),
        (_ru._EAST_SLAVIC_CYR, _post_rules._EAST_SLAVIC_CYR),
        (_tr_az._TURKIC, _post_rules._TURKIC),
        (_tr_az._TURKIC_CYR, _post_rules._TURKIC_CYR),
    ):
        assert pack_regex.pattern == rule_regex.pattern
        assert pack_regex.flags == rule_regex.flags


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
    base = Parser(lexicon=Lexicon.default().add(titles={"zqxcustom"}))
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


def test_locales_import_is_lazy(monkeypatch: pytest.MonkeyPatch) -> None:
    # importing the package must not import any pack module; PEP 562
    # loads them on first attribute access (spec §2: "importing
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
    undeclared one (spec §5.2 = the pack-acceptance rejection rule)."""
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
]
_ROTATORS["tr_az"] = [
    "Aliyev Ali Vali oglu",              # oglu
    "Aliyev Rashad Vali oğlu",           # oğlu
    "Mammadov Elchin Hasan ogly",        # ogly
    "Karimov Aziz Vali ogli",            # ogli
    "Karimov Alisher Vali o'g'li",       # o['’ʻ]g['’ʻ]li, ASCII '
    "Yusupov Botir Vali o’g’li",         # o['’ʻ]g['’ʻ]li, typographic ’
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
# ja has no marker regexes and no vocabulary either: its rotators cover
# the shapes only the pack PLUS its segmenter changes. Every row is
# UNSPACED on purpose -- a spaced kana-licensed name (高橋 みなみ) now
# reads family-first by DEFAULT (amendment 2026-07-29 §1), so it would
# not deviate and would fail the must-deviate assertion below.
_ROTATORS["ja"] = [
    "山田太郎",      # 2-kanji family + 2-kanji given, the common shape
    "高橋一郎",      # the name a zh surname list corrupts (高 + 橋一郎)
    "田中花子",      # ditto (田 is a listed zh surname)
    "原辰徳",        # 1-kanji family + 2-kanji given: the other fork
    "高橋みなみ",    # kanji + hiragana: the kana license's carrier case
    "山田エミ",      # kanji + katakana: licensed as a MIXED token, where
                     # pure katakana (マイケル) is deliberately not
]


def _marker_regexes(module: ModuleType) -> list[re.Pattern]:
    return [v for v in vars(module).values() if isinstance(v, re.Pattern)]


# Packs whose DEVIATES surface is defined by marker REGEXES -- derived,
# never listed, same rule as the registry itself: a pack qualifies by
# having any module-level re.Pattern, so zh (which declares by Han
# codepoint range, pinned by its own sync test) drops out on its own
# and a future marker-regex pack cannot silently miss branch coverage.
_MARKER_REGEX_PACKS = tuple(code for code in sorted(_PACKS)
                            if _marker_regexes(_PACKS[code]))


def test_registry_is_the_pack_contract() -> None:
    # spec §2 authoring requirement 3, enforced structurally (design
    # note 2026-07-18, option C): every registered pack module must
    # declare its deviation surface, and every pack must feed the gate's
    # positive side -- a new pack fails HERE until it ships both, rather
    # than a reviewer remembering to extend the gate by hand.
    assert set(_PACKS) == set(locales.available())
    for code, module in _PACKS.items():
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
    # (kept in sync with _post_rules by the pattern-equality test above)
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
    assert _PACKS[code].DEVIATES(name)


@pytest.mark.parametrize("code", sorted(_PACKS))
def test_non_interference_each_pack(code: str) -> None:
    packed = _require_packed(code)
    corpus = _default_corpus() + _ROTATORS[code]
    declared = _assert_non_interference(
        packed, _PACKS[code].DEVIATES, corpus)
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
    packed = parser_for(
        *(locales.get(code) for code in sorted(_PACKS)),
        segmenter=locales.ja_segmenter() if _JA_AVAILABLE else None)
    declared = _assert_non_interference(
        packed,
        lambda n: any(m.DEVIATES(n) for m in _PACKS.values()),
        corpus)
    assert declared >= len(all_rotators)


# -- #269: non-Latin default vocabulary (Cyrillic, Greek, Arabic, Hebrew) --
#
# This is DEFAULT vocabulary (nameparser/config/titles.py,
# conjunctions.py, prefixes.py), not a locale pack -- it lives here
# because it's the non-Latin counterpart to the pack tests above. Every
# row was verified live against a runtime-augmented Lexicon.default()
# before the data landed (2026-07-17), so these pin actual observed
# behavior, not guesses -- see the per-script comments below for the
# rows that came out differently than a first guess would suggest.
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
    # The kunya "أبو"/"ابو" is AMBIGUOUS (it can begin a standalone
    # byname): leading it reads as the given name -- the "Van Johnson"
    # rule -- while non-leading it chains onto the family like any
    # particle.
    ("أبو مازن", "given", "أبو"),
    ("أحمد أبو خليل", "family", "أبو خليل"),
    ("علي ابو خالد", "family", "ابو خالد"),
    # "الشيخ" carries the FIRST_NAME_TITLES semantics of its
    # transliterated cousin 'sheikh': a single following name reads as
    # given, not family.
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
    # "و" ("and") joins title chains like Cyrillic "и"; single-char
    # conjunctions need the same single-letter carve-out headroom (enough
    # rootname pieces), so pinned with the 6-piece shape the и row uses
    ("الأستاذ و الدكتور طارق حسن السيد", "title", "الأستاذ و الدكتور"),
    # Hebrew patronymic prefixes: same non-leading chain-onto-family
    # behavior.
    ("דוד בן גוריון", "family", "בן גוריון"),
    ("שרה בת אברהם", "family", "בת אברהם"),
    # Hebrew "מר" title (plain title, not FIRST_NAME_TITLES -- like
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
    # Both spellings are shipped; see the titles.py comment.
    ('ד"ר דוד לוי', "title", 'ד"ר'),
    ("גב' דוד לוי", "title", "גב'"),
    ("ד״ר דוד לוי", "title", "ד״ר"),
    ("גב׳ דוד לוי", "title", "גב׳"),
])
def test_269_nonlatin_vocabulary_parses(
        name: str, field: str, expected: str) -> None:
    assert getattr(parse(name), field) == expected


def test_269_vocabulary_reaches_the_v1_facade() -> None:
    # one row per script through HumanName: the facade resolves its
    # lexicon from the CONSTANTS shim snapshot, a different path from
    # parse()'s Lexicon.default() -- proves the #269 data modules feed
    # both surfaces
    from nameparser import HumanName

    assert HumanName("г-н Иван Петров").title == "г-н"
    assert HumanName("κος Γιώργος Παπαδόπουλος").title == "κος"
    assert HumanName("محمد بن سلمان").last == "بن سلمان"
    assert HumanName('ד"ר דוד לוי').title == 'ד"ר'
    # one row per NEW vocabulary category (2026-07-19 batches): bound
    # given name, Hebrew post-nominal suffix, Devanagari title
    assert HumanName("عبد الرحمن محمد").first == "عبد الرحمن"
    assert HumanName('משה כהן ז"ל').suffix == 'ז"ל'
    assert HumanName("डॉ. राम शर्मा").title == "डॉ."


def test_269_bare_greek_kappa_not_a_title() -> None:
    # Regression for the deferred bare 'κ' entry: were it in TITLES,
    # _normalize's edge-period strip would make the abbreviated-initial
    # 'Κ.' match it, degrading the very common initial+surname shape to
    # title='Κ.' with an EMPTY given. Pin the correct reading.
    n = parse("Κ. Παπαδόπουλος")
    assert n.title == ""
    assert n.given == "Κ."
    assert n.family == "Παπαδόπουλος"
