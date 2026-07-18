"""The locale pack layer (locales spec §2-3): lazy access, the two
2.0.0 packs, composition, and the non-interference gate."""
import pytest

from nameparser import Locale


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
