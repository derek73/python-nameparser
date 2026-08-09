"""The 1.x vocabulary names, served from their 2.2 homes.

The 2.0 API named its concepts for what they are -- particles, bound
given names, given-name titles, suffix words -- while the data modules
kept the 1.x names a little longer. #293 moves the data layer to match,
one vocabulary at a time: the particle sets have moved, and each
remaining rename reuses this bridge as it lands. A 1.x name resolves to
its 2.2 constant, warns once, and names the path to migrate to. The
whole layer goes away in 3.0 with the rest of the v1 facade.

Same PEP 562 mechanism as nameparser/locales/__init__.py, and the same
write-back for the same reason -- one lookup, then the name is an
ordinary module global.
"""
from __future__ import annotations

import importlib
import sys
import warnings
from collections.abc import Callable, Mapping
from typing import Any

_MESSAGE = (
    "{module}.{old} is deprecated since 2.2 and will be removed in 3.0; "
    "use {new_module}.{new} instead."
)


def alias_getattr(
    module: str,
    aliases: Mapping[str, tuple[str, str]],
) -> tuple[Callable[[str], Any], Callable[[], list[str]]]:
    """Build the ``__getattr__``/``__dir__`` pair for a module carrying
    deprecated vocabulary names.

    ``aliases`` maps each old attribute name to the ``(module, name)``
    it now lives at. Assign the result at module level::

        __getattr__, __dir__ = alias_getattr(__name__, {...})

    Typed ``Any`` rather than ``object`` because mypy honors an assigned
    module ``__getattr__`` (PEP 484's convention for one): the package
    ships ``py.typed``, and a return of ``object`` would type every
    deprecated name as unusable for a caller still on the old path --
    a type error about ``object`` instead of a word about deprecation.
    """

    def __getattr__(name: str) -> Any:  # noqa: ANN401
        target = aliases.get(name)
        if target is None:
            raise AttributeError(f"module {module!r} has no attribute {name!r}")
        new_module, new_name = target
        warnings.warn(
            _MESSAGE.format(
                module=module, old=name, new_module=new_module, new=new_name),
            DeprecationWarning,
            # 2: the frame that touched the name, which for
            # `from nameparser.config.prefixes import PREFIXES` is the
            # importing module -- the place that has to be edited
            stacklevel=2,
        )
        value = getattr(importlib.import_module(new_module), new_name)
        # write back, so the name is an ordinary global from here on and
        # the warning fires once per name per process rather than once
        # per read. A caller who ignores the first warning is not told
        # again, which is the point: the message is advice to the
        # author, not a runtime signal to the program. Benign race under
        # free threading: two threads racing here resolve the same
        # constant and assign the same value to the same name, so the
        # last write wins and a duplicate warning is the only
        # observable difference.
        setattr(sys.modules[module], name, value)
        return value

    def __dir__() -> list[str]:
        return sorted(set(vars(sys.modules[module])) | set(aliases))

    return __getattr__, __dir__
