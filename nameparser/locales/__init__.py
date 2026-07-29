"""Locale packs: named (lexicon fragment, PolicyPatch) deltas folded in
by parser_for (locales spec §2). Packs are pure data with no
privileged capabilities; they dissolve at parser construction.

Loaded lazily (PEP 562): importing nameparser.locales never imports a
pack module; ``locales.RU`` triggers ``nameparser.locales.ru`` on
first access and caches the Locale here.

Layering: this package imports pack modules, which import _locale/
_lexicon/_policy only (enforced by tests/v2/test_layering.py).
"""
from __future__ import annotations

import importlib

from nameparser._locale import Locale

#: attribute name -> (module name, module attribute). Codes are the
#: lowercase module names; attribute constants are uppercase (spec §2).
_REGISTRY = {
    "RU": ("nameparser.locales.ru", "RU"),
    "TR_AZ": ("nameparser.locales.tr_az", "TR_AZ"),
    "ZH": ("nameparser.locales.zh", "ZH"),
}


def __getattr__(name: str) -> Locale:
    entry = _REGISTRY.get(name)
    if entry is None:
        raise AttributeError(
            f"module {__name__!r} has no locale {name!r}; available: "
            f"{', '.join(sorted(_REGISTRY))}"
        )
    module_name, attr = entry
    locale: Locale = getattr(importlib.import_module(module_name), attr)
    # cache: next access skips __getattr__. Benign race under free
    # threading: two threads racing here both import the same module
    # object (import machinery serializes/dedupes that) and assign the
    # same singleton Locale back to the same name, so the last write
    # wins with no observable difference.
    globals()[name] = locale
    return locale


def __dir__() -> list[str]:
    return sorted(set(globals()) | set(_REGISTRY))


def available() -> tuple[str, ...]:
    """The registered locale codes, lowercase, sorted."""
    return tuple(sorted(attr.lower() for attr in _REGISTRY))


def get(code: str) -> Locale:
    """Dynamic lookup by code ('ru'); raises KeyError listing the
    available codes (spec §2)."""
    attr = code.upper() if isinstance(code, str) else code
    if not isinstance(code, str) or attr not in _REGISTRY:
        raise KeyError(
            f"unknown locale code {code!r}; available: "
            f"{', '.join(available())}"
        )
    return __getattr__(attr)
