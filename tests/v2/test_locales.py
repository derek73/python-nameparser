"""The locale pack layer (locales spec §2-3): lazy access, the two
2.0.0 packs, composition, and the non-interference gate."""
import json
from collections.abc import Callable, Iterable
from pathlib import Path

import pytest

from nameparser import Locale, Parser, locales, parse, parser_for
from nameparser._lexicon import Lexicon
from nameparser._policy import PatronymicRule
from nameparser.locales import ru as _ru
from nameparser.locales import tr_az as _tr_az

_CORPUS = [
    json.loads(line)
    for line in (Path(__file__).parents[2] / "tools" / "differential"
                 / "corpus.jsonl").read_text().splitlines()
    if line.strip()
]


def test_locales_module_attribute_access() -> None:
    from nameparser import locales
    assert isinstance(locales.RU, Locale)
    assert locales.RU.code == "ru"
    assert locales.RU is locales.RU          # cached, not rebuilt


def test_locales_get_and_available() -> None:
    from nameparser import locales
    assert locales.get("ru") is locales.RU
    assert set(locales.available()) == {"ru", "tr_az"}
    with pytest.raises(KeyError, match="ru, tr_az"):
        locales.get("xx")


def test_tr_az_pack_contents() -> None:
    from nameparser import locales

    assert locales.TR_AZ.code == "tr_az"
    assert locales.TR_AZ.policy.patronymic_rules == frozenset(
        {PatronymicRule.TURKIC})
    assert locales.TR_AZ.lexicon == Lexicon.empty()


def test_pack_marker_regexes_stay_in_sync_with_post_rules() -> None:
    # ru.py/tr_az.py hand-copy their DEVIATES marker regexes from
    # _pipeline._post_rules (layering forbids a pack importing the
    # pipeline -- see each pack's module docstring). Assert pattern
    # equality mechanically so drift fails here, not at the L6
    # non-interference gate.
    from nameparser._pipeline import _post_rules
    from nameparser.locales import ru, tr_az

    for pack_regex, rule_regex in (
        (ru._EAST_SLAVIC, _post_rules._EAST_SLAVIC),
        (ru._EAST_SLAVIC_CYR, _post_rules._EAST_SLAVIC_CYR),
        (tr_az._TURKIC, _post_rules._TURKIC),
        (tr_az._TURKIC_CYR, _post_rules._TURKIC_CYR),
    ):
        assert pack_regex.pattern == rule_regex.pattern
        assert pack_regex.flags == rule_regex.flags


def test_ru_deviates_scans_per_token() -> None:
    # Regression: the rule rotates on the family-POSITION token, so a
    # whole-string search missed a patronymic ending followed by a
    # suffix -- under-declaration, the unsafe direction for the
    # non-interference gate. The pack rotates this name; DEVIATES must
    # say so.
    from nameparser.locales import ru

    assert ru.DEVIATES("Ivan Petr Sidorovich Jr.")
    # Over-declaration is the accepted safe direction: the ending
    # matches a token although the rule's 1 given + 1 middle +
    # 1 family shape never fires on a two-token name.
    assert ru.DEVIATES("Sidorovich Anna")
    assert not ru.DEVIATES("John Smith")


def test_tr_az_deviates_scans_per_token() -> None:
    # Mirror of the RU regression above: the Turkic marker regexes are
    # fullmatch-shaped (^...$), so anything but a per-token scan would
    # miss a marker followed by a suffix (under-declaration) -- and a
    # whole-string match would never fire at all on multi-token names.
    from nameparser.locales import tr_az

    assert tr_az.DEVIATES("Mammadova Aygun Ali kizi Jr.")
    # over-declaration stays the safe direction: a bare marker-shaped
    # token declares even where the rule won't rewrite anything
    assert tr_az.DEVIATES("Kizi Anna")
    assert not tr_az.DEVIATES("John Smith")
    # markers are whole-token: a name merely CONTAINING one must not
    # declare ("Ogluev" is not a marker)
    assert not tr_az.DEVIATES("Ogluev Ivan")


def test_locales_unknown_attribute() -> None:
    from nameparser import locales
    with pytest.raises(AttributeError, match="XX"):
        locales.XX


def test_ru_plus_tr_az_unions_patronymic_rules() -> None:
    from nameparser import locales, parser_for
    from nameparser._policy import PatronymicRule

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
    from nameparser import Lexicon, Parser, locales, parser_for

    base = Parser(lexicon=Lexicon.default().add(titles={"zqxcustom"}))
    p = parser_for(locales.RU, base=base)
    n = p.parse("Zqxcustom Иван Петрович")
    assert n.title == "Zqxcustom"       # base lexicon survives the fold


def test_pack_preserves_custom_base_policy() -> None:
    # the lexicon-survival twin above has a policy counterpart: a
    # policy-only pack must ADD its patronymic rule without resetting
    # unrelated policy fields the base customized
    from nameparser import Parser, locales, parser_for
    from nameparser._policy import Policy

    base = Parser(policy=Policy(strip_emoji=False))
    p = parser_for(locales.RU, base=base)
    assert p.policy.strip_emoji is False
    assert p.policy.patronymic_rules == frozenset(
        {PatronymicRule.EAST_SLAVIC})


def test_parser_for_results_chain_as_bases() -> None:
    # parser_for's result is itself a valid base= -- packs applied in
    # two steps accumulate exactly like one call with both packs
    from nameparser import locales, parser_for

    chained = parser_for(locales.TR_AZ, base=parser_for(locales.RU))
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
    default = Parser()
    declared = 0
    for name in corpus:
        base = default.parse(name).as_dict()
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


# Synthetic rotator names: one per alternation branch of each pack's
# marker regexes (both scripts), in the shape that makes the rule fire
# (RU: family-first, patronymic last, plain middle; TR_AZ: a standalone
# marker token). They serve the gate's POSITIVE side -- without them the
# shared corpus exercises TR_AZ with a single name, leaving the gate
# nearly vacuous (review finding, 2026-07-17). Branch named per row so a
# regex edit that orphans a branch is visible here.
_RU_ROTATORS = [
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
_TR_AZ_ROTATORS = [
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


@pytest.mark.parametrize("name", _RU_ROTATORS)
def test_ru_rotator_deviates_and_declares(name: str) -> None:
    # every branch of the pack's marker regexes both FIRES (packed parse
    # differs from default) and is DECLARED (DEVIATES says so) -- the
    # per-name proof behind the gate's declared-count floor below
    packed = parser_for(locales.RU)
    assert packed.parse(name).as_dict() != Parser().parse(name).as_dict()
    assert _ru.DEVIATES(name)


@pytest.mark.parametrize("name", _TR_AZ_ROTATORS)
def test_tr_az_rotator_deviates_and_declares(name: str) -> None:
    packed = parser_for(locales.TR_AZ)
    assert packed.parse(name).as_dict() != Parser().parse(name).as_dict()
    assert _tr_az.DEVIATES(name)


def test_non_interference_ru() -> None:
    corpus = _default_corpus() + _RU_ROTATORS
    declared = _assert_non_interference(
        parser_for(locales.RU), _ru.DEVIATES, corpus)
    # the positive side: every synthetic rotator (plus the corpus's own
    # east-slavic names) must actually flow through the declared branch
    assert declared >= len(_RU_ROTATORS)


def test_non_interference_tr_az() -> None:
    corpus = _default_corpus() + _TR_AZ_ROTATORS
    declared = _assert_non_interference(
        parser_for(locales.TR_AZ), _tr_az.DEVIATES, corpus)
    assert declared >= len(_TR_AZ_ROTATORS)


def test_non_interference_combined() -> None:
    corpus = _default_corpus() + _RU_ROTATORS + _TR_AZ_ROTATORS
    declared = _assert_non_interference(
        parser_for(locales.RU, locales.TR_AZ),
        lambda n: _ru.DEVIATES(n) or _tr_az.DEVIATES(n),
        corpus)
    assert declared >= len(_RU_ROTATORS) + len(_TR_AZ_ROTATORS)


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
    # Cyrillic conjunction "и": v1's issue #11 carve-out treats a bare
    # single-alphabetic-character conjunction in a short name as more
    # likely an initial (group._group_segment), so a 3-piece chain
    # ("проф и акад Іван Франко") does NOT join -- "и" reads as a given
    # name instead. The chain only joins once the segment has enough
    # rootname pieces (total >= 4); pinned against that actual behavior
    # with a 5-piece name instead of the shorter guess.
    ("проф и акад Тарас Григорович Шевченко", "title", "проф и акад"),
    ("проф та акад Іван Франко", "title", "проф та акад"),
    # Ukrainian "і" is single-character like "и", so the same #11
    # initial carve-out applies: pinned with a 5-piece name.
    ("проф і акад Тарас Григорович Шевченко", "title", "проф і акад"),
    # Greek titles + conjunction (και has 3 letters, so the single-char
    # initial carve-out above never applies to it). Bare κ is NOT
    # shipped -- it collides with the initial+surname shape (see the
    # regression test below).
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
    # Hebrew patronymic prefixes: same non-leading chain-onto-family
    # behavior.
    ("דוד בן גוריון", "family", "בן גוריון"),
    ("שרה בת אברהם", "family", "בת אברהם"),
    # Hebrew "מר" title (plain title, not FIRST_NAME_TITLES -- like
    # 'mr', the following name reads as family).
    ("מר דוד לוי", "title", "מר"),
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


def test_269_bare_greek_kappa_not_a_title() -> None:
    # Regression for the deferred bare 'κ' entry: were it in TITLES,
    # _normalize's edge-period strip would make the abbreviated-initial
    # 'Κ.' match it, degrading the very common initial+surname shape to
    # title='Κ.' with an EMPTY given. Pin the correct reading.
    n = parse("Κ. Παπαδόπουλος")
    assert n.title == ""
    assert n.given == "Κ."
    assert n.family == "Παπαδόπουλος"
