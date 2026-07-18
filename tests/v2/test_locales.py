"""The locale pack layer (locales spec §2-3): lazy access, the two
2.0.0 packs, composition, and the non-interference gate."""
import json
from collections.abc import Callable, Iterable
from pathlib import Path

import pytest

from nameparser import Locale, Parser, locales, parser_for
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


def test_locales_import_is_lazy() -> None:
    # importing the package must not import any pack module; PEP 562
    # loads them on first attribute access (spec §2: "importing
    # nameparser never pays for pack data")
    import importlib
    import sys

    for mod in list(sys.modules):
        if mod.startswith("nameparser.locales"):
            del sys.modules[mod]
    import nameparser.locales
    assert "nameparser.locales.ru" not in sys.modules
    nameparser.locales.RU
    assert "nameparser.locales.ru" in sys.modules
    importlib.reload(nameparser.locales)


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


def test_non_interference_ru() -> None:
    corpus = _default_corpus()
    declared = _assert_non_interference(
        parser_for(locales.RU), _ru.DEVIATES, corpus)
    # the positive side: the gate must be exercising something -- the
    # corpus contains east-slavic bank names that DO rotate
    assert declared > 0


def test_non_interference_tr_az() -> None:
    _assert_non_interference(
        parser_for(locales.TR_AZ), _tr_az.DEVIATES, _default_corpus())


def test_non_interference_combined() -> None:
    _assert_non_interference(
        parser_for(locales.RU, locales.TR_AZ),
        lambda n: _ru.DEVIATES(n) or _tr_az.DEVIATES(n),
        _default_corpus())
