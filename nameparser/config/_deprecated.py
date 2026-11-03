"""The 1.x vocabulary names, served from their 2.2 homes.

The 2.0 API named its concepts for what they are -- particles, bound
given names, given-name titles, suffix words -- while the data modules
kept the 1.x names a little longer. #293 moved all four to match. A 1.x
name resolves to its 2.2 constant, warns at the line that read it, and
names the path to migrate to; the whole layer goes away in 3.0 with the
rest of the v1 facade.

Two of the four moved module and all: prefixes -> particles and
bound_first_names -> bound_given_names, whose old modules are now
data-free shims that are nothing but a docstring and an alias table.
The other two renamed a constant in place, so titles.py and suffixes.py
carry their alias table at the bottom of the file, beside their data.

Same PEP 562 hook as nameparser/locales/__init__.py, but deliberately
without that module's write-back: a retired name stays served by
``__getattr__`` for the life of the process, so every read reaches the
warning. Suppressing the repeats is the warnings module's own job, and
it does it per LOCATION -- ``__warningregistry__`` lives in the READING
module's globals and is keyed on (text, category, lineno). That is the
granularity the advice is written at: one line that reads a retired
name is told once however often it runs, and a second line, in that
file or another, is told for itself. Caching the resolved value into
the module globals instead would silence every reader after the first,
and the first is whoever imported earliest -- routinely a dependency,
whose author is not the person who has to edit anything.

PEP 562 defines the hook for attribute ACCESS and nothing else, which
is why every alias-bearing module also carries an ``__all__`` naming
its retired names: ``from x import *`` reads ``__all__``, or failing
that the module ``__dict__``, and consults ``__getattr__`` in neither
case. Without the list a star import binds no retired name and issues
no diagnostic. See the note at the ``__all__`` in prefixes.py.
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

#: 3.0's migration guide, which every 2.8.1 removal message points at:
#: Read the Docs' "latest" builds master, the 3.0 cycle.
MIGRATION_GUIDE = "https://nameparser.readthedocs.io/en/latest/migrate.html"

# 2.8.1: the live names of a module 3.0 deletes (#1007, #1008). Every
# message opens "nameparser.config.", names the removal and closes on
# the guide; pyproject's filterwarnings ignores the family by message,
# and tests/v2/test_removals_2_8_1.py asserts each one.
_REMOVED_MESSAGE = (
    "{module}.{name} is deprecated and will be removed in 3.0 ({issue}); "
    "{replacement}. See {guide}"
)


def words_of(args: str, which: str = "") -> str:
    """The replacement clause for a vocabulary constant: the 3.0 call
    listing its words (``Lexicon.words``, #1007), and where the call
    lists more than the set held, which of them it held."""
    held = f" ({which})" if which else ""
    return f"in 3.0, Lexicon.default().words({args}) lists them{held}"


def removal_message(module: str, name: str) -> str | None:
    """The 2.8.1 removal message for ``module.name``, or ``None`` where
    3.0 keeps the name. Reads the module's hook, so it warns nothing."""
    hook = vars(importlib.import_module(module)).get("__getattr__")
    removed: Mapping[str, str] = getattr(hook, "removed_messages", {})
    return removed.get(name)


def _quiet_value(module: str, name: str) -> Any:  # noqa: ANN401
    loaded = importlib.import_module(module)
    hook = vars(loaded).get("__getattr__")
    held: Mapping[str, Any] = getattr(hook, "removed_values", {})
    return held[name] if name in held else getattr(loaded, name)


def alias_getattr(
    module: str,
    aliases: Mapping[str, tuple[str, str]],
    removed: Mapping[str, str] | None = None,
    namespace: dict[str, Any] | None = None,
    issue: str = "#1007",
) -> tuple[Callable[[str], Any], Callable[[], list[str]]]:
    """Build the ``__getattr__``/``__dir__`` pair for a module carrying
    deprecated vocabulary names.

    ``aliases`` maps each old attribute name to the ``(module, name)``
    it now lives at. Assign the result at module level, in the ``else``
    of a ``TYPE_CHECKING`` guard that declares the same names::

        if TYPE_CHECKING:
            OLD_NAME: frozenset[str]   # 1.x alias, removed in 3.0 (#293)
        else:
            __getattr__, __dir__ = alias_getattr(__name__, {...})

    (a placeholder rather than a real retired name, for the reason the
    ``stacklevel`` comment below gives)

    The guard is load-bearing. mypy honors an assigned module
    ``__getattr__`` (PEP 484's convention for one) and thereafter
    answers EVERY missing attribute of that module from its return
    type, so a bare assignment turns off missing-attribute checking for
    the whole module. On titles.py and suffixes.py, which keep their
    live constants and are still imported from, that cost real
    checking: ``from nameparser.config.titles import TITLE`` type-
    checked clean. Keeping the assignment out of the type checker's
    view restores it, and the declarations in the other branch type
    each retired name as the ``frozenset[str]`` it is rather than
    ``Any``. The package ships ``py.typed``, so both reach callers.
    Runtime is untouched -- ``TYPE_CHECKING`` is False, so only the
    ``else`` ever runs -- and the two branches delete together in 3.0.

    Which leaves the ``Any`` return below typing nothing outside this
    module: mypy reads no module ``__getattr__`` for the alias-bearing
    modules any more, and does not analyze the ``else`` branch it is
    assigned in. It stays ``Any`` as what ``getattr`` itself returns.

    ``removed`` (2.8.1) maps each LIVE name 3.0 deletes to the clause
    naming its 3.0 replacement, and ``namespace`` is the module's
    ``globals()``: each such name is popped out of it into the hook, so
    the module keeps its assignment statement -- which is where autodoc
    finds the constant's documentation -- while every read reaches
    ``__getattr__`` and warns at the reader's line. The library reads
    these values from ``nameparser.config._compiled`` (and regexes.py's
    ``_REGEXES``), never through here, so only a caller's read warns.
    """
    removed = dict(removed or {})
    values: dict[str, Any] = {}
    if removed:
        if namespace is None:
            raise TypeError("alias_getattr: removed names need namespace=")
        values = {name: namespace.pop(name) for name in removed}
    messages = {
        name: _REMOVED_MESSAGE.format(
            module=module, name=name, issue=issue, replacement=replacement,
            guide=MIGRATION_GUIDE)
        for name, replacement in removed.items()}

    def __getattr__(name: str) -> Any:  # noqa: ANN401
        if name in values:
            # 2: the reading frame, as for an alias below
            warnings.warn(messages[name], DeprecationWarning, stacklevel=2)
            return values[name]
        target = aliases.get(name)
        if target is None:
            raise AttributeError(f"module {module!r} has no attribute {name!r}")
        new_module, new_name = target
        # resolved BEFORE warning, so a mistyped alias target fails as
        # a ModuleNotFoundError or an AttributeError from here rather
        # than first advising the reader to move to a path that does
        # not exist. Quietly: a target 3.0 removes too is held by its
        # module's hook, whose own warning would name this file.
        value = _quiet_value(new_module, new_name)
        message = _MESSAGE.format(
            module=module, old=name, new_module=new_module, new=new_name)
        # one warning saying so, rather than advice to move to a name
        # that warns in its turn
        also = removal_message(new_module, new_name)
        if also is not None:
            message += " That name is removed in 3.0 too: " + also
        warnings.warn(
            message,
            DeprecationWarning,
            # 2: the frame that touched the name -- for the
            # `from nameparser.config.prefixes import ...` form, the
            # importing module, which is the place that has to be
            # edited. Which name it imports does not matter here, and
            # spelling one out would put a retired name in a file that
            # serves no single vocabulary (tests/v2/test_config_aliases
            # ::test_no_internal_code_reads_a_retired_vocabulary_name)
            stacklevel=2,
        )
        return value

    def __dir__() -> list[str]:
        # UNION, not just the aliases: a module __dir__ REPLACES the
        # default listing rather than adding to it, so dropping the
        # module's own globals here would take the live constants out
        # of tab completion and every getattr-free member scan --
        # autodoc's included. Pinned by test_config_aliases
        # ::test_dir_lists_the_live_names_as_well_as_the_retired_ones.
        #
        # .get, not [...]: a module dropped from sys.modules -- a test
        # that reloads the package, a plugin teardown -- would otherwise
        # make dir() raise KeyError, which is not among the things dir()
        # may do to a caller. The aliases are held in the closure and
        # are still nameable, so they are what is left to list (#356).
        live = sys.modules.get(module)
        names = set(vars(live)) if live is not None else set()
        return sorted(names | set(aliases) | set(values))

    # The table itself, reachable without tripping a warning. __all__ is
    # hand-written per module (it must stay in SOURCE order for autodoc,
    # which this function cannot know), so the two lists are maintained
    # separately and a row added to only one of them is the failure
    # fc46a9b closed for the other direction: a table row missing from
    # __all__ is silently dropped by `from x import *` with no warning
    # and no AttributeError. test_config_aliases
    # ::test_every_alias_table_row_reaches_star_import cross-checks them.
    __getattr__.deprecated_aliases = dict(aliases)  # type: ignore[attr-defined]
    # the 2.8.1 removals, read by removal_message and _quiet_value
    __getattr__.removed_messages = messages  # type: ignore[attr-defined]
    __getattr__.removed_values = values  # type: ignore[attr-defined]

    return __getattr__, __dir__
