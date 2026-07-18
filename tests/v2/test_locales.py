"""The locale pack layer (locales spec §2-3): lazy access, the two
2.0.0 packs, composition, and the non-interference gate."""
import pytest

from nameparser import Locale
from nameparser._lexicon import Lexicon
from nameparser._policy import PatronymicRule


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


def test_locales_unknown_attribute() -> None:
    from nameparser import locales
    with pytest.raises(AttributeError, match="XX"):
        locales.XX


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
