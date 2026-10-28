"""v1 import-path preservation (mechanisms.md#CONFIG-SHIM-SNAPSHOT):
the Constants shim
lives in nameparser._config_shim.

Two unrelated things share this package. The names re-exported below --
``Constants``, ``CONSTANTS``, ``SetManager``, ``TupleManager``,
``RegexTupleManager`` -- are v1 compatibility surface, and go with the
rest of the facade in 3.0. The vocabulary data modules beside them
(:mod:`~nameparser.config.titles`, :mod:`~nameparser.config.particles`,
...) are not compatibility surface at all: they are the word lists the
2.0 :class:`~nameparser.Lexicon` is built from, they are named for its
fields since 2.2 (#293), and its documentation cross-references them.
Since 2.6 the word lists (all but ``surnames.py``) re-export sets
compiled from the per-word TOML files in ``nameparser/vocab/`` (#737).

``RegexTupleManager`` is served from the shim purely for pickle
compatibility (through ``__getattr__`` since 2.8, so loading such a blob
warns here too): a v1.4 ``Constants`` blob's ``regexes`` field was
pickled as ``nameparser.config.RegexTupleManager(...)``, and unpickling
resolves and reconstructs that nested object before
``Constants.__setstate__`` ever runs. Without this name, loading such a
blob raises ``AttributeError`` looking up the class, not a clean
compatibility failure.
"""
# Maintainer note, deliberately outside the docstring: the vocabulary
# DATA modules keep this package as their home in 3.0 (decided
# 2026-10-28, decisions/3-0-reevaluations); only the five shim names
# below go. Constants and CONSTANTS are imported eagerly -- Constants
# warns at construction, the CONSTANTS singleton when mutated -- while
# the three managers resolve through __getattr__ so that each caller's
# read warns, at the caller's line, and nameparser's own reads (from
# _config_shim directly) stay quiet. The bridge follows
# config/_deprecated.py's alias_getattr: the hooks sit in the `else` of
# a TYPE_CHECKING guard, since a module __getattr__ mypy can see turns
# off its missing-attribute checking for the whole module, and __dir__
# lists the managers, or autodoc's member scan drops them.
import sys as _sys
import warnings as _warnings
from typing import TYPE_CHECKING

import nameparser._config_shim as _config_shim
from nameparser._config_shim import CONSTANTS as CONSTANTS
from nameparser._config_shim import Constants as Constants

if TYPE_CHECKING:
    from nameparser._config_shim import RegexTupleManager as RegexTupleManager
    from nameparser._config_shim import SetManager as SetManager
    from nameparser._config_shim import TupleManager as TupleManager
else:
    def __getattr__(name: str) -> object:
        # PEP 562. Per read, never cached into globals, so every
        # reading site warns (why _deprecated.py never caches either).
        # A v1.4 Constants pickle names nameparser.config.
        # RegexTupleManager and SetManager, so loading one warns here as
        # well as in Constants.__setstate__ -- correct, since 3.0
        # refuses that blob.
        message = _config_shim.MANAGER_DEPRECATIONS.get(name)
        if message is None:
            raise AttributeError(
                f"module {__name__!r} has no attribute {name!r}")
        # `from nameparser.config import SetManager` reads the name
        # twice: importlib's _handle_fromlist probes a PACKAGE's
        # fromlist with hasattr() first, then the import statement
        # reads it. Warning on the probe too would report one import
        # twice.
        if _sys._getframe(1).f_code.co_name != "_handle_fromlist":
            _warnings.warn(message, DeprecationWarning, stacklevel=2)
        return getattr(_config_shim, name)

    def __dir__() -> list[str]:
        # the union, as _deprecated.py's __dir__ explains
        return sorted(set(globals()) | set(_config_shim.MANAGER_DEPRECATIONS))

# a star import reads __all__ alone, so listing the managers routes
# each through __getattr__ and warns, rather than dropping them unwarned
__all__ = ["CONSTANTS", "Constants", "RegexTupleManager", "SetManager", "TupleManager"]
