"""Locale packs: named (lexicon fragment, PolicyPatch) deltas folded in
by parser_for (mechanisms.md#LOCALE-PACKS-PURE-DATA). Packs are
pure data with no
privileged capabilities; they dissolve at parser construction.

Loaded lazily (PEP 562): importing nameparser.locales never imports a
pack module; ``locales.RU`` triggers ``nameparser.locales.ru`` on
first access and caches the Locale here.

Layering: this package imports pack modules, which import _locale/
_lexicon/_policy only (enforced by tests/v2/test_layering.py).
"""
from __future__ import annotations

import importlib
from typing import TYPE_CHECKING

from nameparser._locale import Locale

if TYPE_CHECKING:
    from nameparser._types import Segmenter

#: attribute name -> (module name, module attribute). Codes are the
#: lowercase module names; attribute constants are uppercase.
_REGISTRY = {
    "JA": ("nameparser.locales.ja", "JA"),
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


def ja_segmenter(*, gbdt: bool = False) -> Segmenter:
    """The Japanese segmenter factory (#272), needing the optional
    ``pip install nameparser[ja]``; see :mod:`nameparser.locales.ja` for
    what it wraps, what it declines, and its licensing.

    A real function rather than a _REGISTRY entry, because the registry
    resolves LOCALES: __getattr__ is annotated to return one, so routing
    a callable through it would type every pack access as "Locale or
    Segmenter" for no gain. Laziness is preserved here instead -- the
    pack module (and with it the optional dependency) loads on the
    call, not on importing this package."""
    from nameparser.locales.ja import ja_segmenter as factory

    return factory(gbdt=gbdt)


def get(code: str) -> Locale:
    """Dynamic lookup by code ('ru'); raises KeyError listing the
    available codes."""
    attr = code.upper() if isinstance(code, str) else code
    if not isinstance(code, str) or attr not in _REGISTRY:
        raise KeyError(
            f"unknown locale code {code!r}; available: "
            f"{', '.join(available())}"
        )
    return __getattr__(attr)
