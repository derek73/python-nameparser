"""The 1.x vocabulary names, served from their 2.2 homes (#293).

The alias table here is written out literally rather than imported from
the shim modules. Importing their table would make every assertion
below a tautology -- it would prove the bridge is self-consistent, not
that it points where the migration guide says it does.
"""
from __future__ import annotations

import importlib
import inspect
import pathlib
import sys
import warnings
from typing import NamedTuple

import pytest

import nameparser


class _Alias(NamedTuple):
    """One retired 1.x vocabulary name and the 2.2 name serving it.

    Four same-typed strings whose order carries all the meaning, which
    is what makes a bare tuple the wrong shape here: ``for m, n, _, _ in
    ALIASES`` appeared six times below and reads correctly only if you
    remember which end is which. Named after ``_LatinCopy`` in
    ``test_ledger_guards.py`` (#356).
    """
    old_module: str
    old_name: str
    new_module: str
    new_name: str


def _id(alias: _Alias) -> str:
    return f"{alias.old_module.rsplit('.', 1)[-1]}.{alias.old_name}"


#: One row per alias.
ALIASES = [
    _Alias("nameparser.config.prefixes", "PREFIXES",
           "nameparser.config.particles", "PARTICLES"),
    _Alias("nameparser.config.prefixes", "NON_FIRST_NAME_PREFIXES",
           "nameparser.config.particles", "NON_GIVEN_NAME_PARTICLES"),
    _Alias("nameparser.config.bound_first_names", "BOUND_FIRST_NAMES",
           "nameparser.config.bound_given_names", "BOUND_GIVEN_NAMES"),
    _Alias("nameparser.config.titles", "FIRST_NAME_TITLES",
           "nameparser.config.titles", "GIVEN_NAME_TITLES"),
    _Alias("nameparser.config.suffixes", "SUFFIX_NOT_ACRONYMS",
           "nameparser.config.suffixes", "SUFFIX_WORDS"),
]

#: Old module paths, one per shim, for the per-module parametrizations.
OLD_MODULES = sorted({a.old_module for a in ALIASES})


@pytest.mark.parametrize(
    ("old_module", "old_name", "new_module", "new_name"),
    ALIASES,
    ids=[_id(a) for a in ALIASES],
)
def test_old_name_warns_and_resolves_to_the_new_constant(
    old_module: str, old_name: str, new_module: str, new_name: str,
) -> None:
    expected = getattr(importlib.import_module(new_module), new_name)
    with pytest.warns(DeprecationWarning) as record:
        value = getattr(importlib.import_module(old_module), old_name)
    assert value is expected
    message = str(record[0].message)
    # both paths: naming only the destination would let the message
    # misidentify which name the caller actually has to edit
    assert f"{old_module}.{old_name}" in message, message
    assert f"{new_module}.{new_name}" in message, message
    assert "3.0" in message, message


def test_warning_points_at_the_line_that_read_the_name() -> None:
    """A message nobody can trace back to their own code is advice that
    cannot be acted on -- #337's scar is exactly this regressing
    unnoticed, since a wrong ``stacklevel`` is invisible from inside the
    warning call. Only the recorded frame shows it."""
    module = importlib.import_module("nameparser.config.prefixes")
    frame = inspect.currentframe()
    assert frame is not None
    with pytest.warns(DeprecationWarning) as record:
        expected_lineno = frame.f_lineno + 1
        module.PREFIXES  # noqa: B018
    assert (record[0].filename, record[0].lineno) == (__file__, expected_lineno)


@pytest.mark.parametrize(
    ("old_module", "old_name"),
    [(a.old_module, a.old_name) for a in ALIASES],
    ids=[_id(a) for a in ALIASES],
)
def test_from_import_is_attributed_to_the_importing_module(
    old_module: str, old_name: str,
) -> None:
    """The form the ``stacklevel`` comment singles out, and the one most
    callers use. ``from x import Y`` resolves the alias while the
    importing module's frame is on top, so the report names the file
    holding the import -- the line that has to be edited.

    Every alias, not the one ``prefixes`` row this covered until #356.
    The two that KEPT their module are a structurally different shape:
    their table sits at the bottom of a module that is mid-execution
    during its own import, so a regression could reach those two and not
    the moved ones.
    """
    code = compile(f"from {old_module} import {old_name}\n",
                   "caller_module.py", "exec")
    with pytest.warns(DeprecationWarning) as record:
        exec(code, {"__name__": "caller_module"})
    assert (record[0].filename, record[0].lineno) == ("caller_module.py", 1)


@pytest.mark.parametrize(
    ("old_module", "old_name"),
    [(a.old_module, a.old_name) for a in ALIASES],
    ids=[_id(a) for a in ALIASES],
)
def test_old_name_warns_once_per_read_location(
    old_module: str, old_name: str,
) -> None:
    """Every line that has to be edited is told, and told once.

    The bridge deliberately does not cache the resolved value back into
    the shim module, so the suppression is ``__warningregistry__``'s:
    keyed on (text, category, lineno) in the READING module's globals,
    it silences a repeat from the same line and lets a new line through.
    A write-back would instead hand the single warning to whoever read
    first, which in a real program is usually a dependency.

    The filter action is load-bearing, and this test is vacuous under
    the wrong one. ``pytest.warns`` installs ``always``, and the suite's
    own ``filterwarnings = ["error"]`` raises before recording -- under
    either, nothing is ever written to the registry, so all three reads
    below report and the assertion measures nothing. ``default`` is the
    action that records what it has already shown. Entering and leaving
    ``catch_warnings`` bumps the filter version, which invalidates any
    registry this file left behind, so each parametrization starts cold
    without anyone clearing it.
    """
    module = importlib.import_module(old_module)
    frame = inspect.currentframe()
    assert frame is not None
    with warnings.catch_warnings(record=True) as record:
        warnings.simplefilter("default")
        repeated_lineno = frame.f_lineno + 2
        for _ in range(2):
            first = getattr(module, old_name)
        fresh_lineno = frame.f_lineno + 1
        second = getattr(module, old_name)

    assert first is second
    assert [w.lineno for w in record] == [repeated_lineno, fresh_lineno]


@pytest.mark.parametrize(
    "old_module", OLD_MODULES)
def test_unknown_attribute_still_raises(old_module: str) -> None:
    module = importlib.import_module(old_module)
    with pytest.raises(AttributeError, match="NOT_A_CONSTANT"):
        module.NOT_A_CONSTANT  # noqa: B018


@pytest.mark.parametrize(
    ("old_module", "old_name"),
    [(a.old_module, a.old_name) for a in ALIASES],
    ids=[_id(a) for a in ALIASES],
)
def test_dir_advertises_the_old_names(old_module: str, old_name: str) -> None:
    assert old_name in dir(importlib.import_module(old_module))


@pytest.mark.parametrize("old_module", OLD_MODULES)
def test_dir_survives_the_module_being_dropped_from_sys_modules(
    old_module: str, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """``dir()`` may raise ``AttributeError``; it may not raise ``KeyError``.

    The override reads the module back out of ``sys.modules`` to reach
    the live names, and a subscript there made ``dir(module)`` raise
    ``KeyError`` for anyone holding a reference to a module that had
    been dropped -- a package reload, a plugin teardown. The aliases
    live in the closure and are still nameable, so they are what a
    degraded listing can honestly offer (#356).
    """
    module = importlib.import_module(old_module)
    retired = {a.old_name for a in ALIASES if a.old_module == old_module}
    monkeypatch.delitem(sys.modules, old_module)
    assert set(dir(module)) == retired


def test_dir_lists_the_live_names_as_well_as_the_retired_ones() -> None:
    """The other half of what these four ``__dir__`` overrides owe.

    A module ``__dir__`` REPLACES the default listing, so an override
    that returns only the alias table takes every live constant out of
    REPL completion, out of ``inspect.getmembers``, and out of autodoc's
    module member scan -- which walks ``dir()`` and would then document
    nothing from ``suffixes``/``titles``. The retired-name assertion
    above is satisfied by exactly that override, so it has to be said
    separately.

    Stated over the whole of ``vars()`` rather than the vocabulary
    alone: the union is what the override actually promises, and it
    cannot go vacuous the way an empty vocabulary filter can on the two
    data-free shim modules.
    """
    live_seen = []
    dropped = {}
    for old_module in OLD_MODULES:
        module = importlib.import_module(old_module)
        missing = set(vars(module)) - set(dir(module))
        if missing:
            dropped[old_module] = sorted(missing)
        live_seen += [name for name, value in vars(module).items()
                      if name.isupper() and isinstance(value, frozenset)]
    # checked first: the sweep below is equally happy with four modules
    # holding no vocabulary at all, which is the shape that would make
    # it prove nothing
    assert live_seen, (
        "no live vocabulary constant found in any alias-bearing module "
        "-- the sweep below would be measuring only dunders")
    assert not dropped, (
        f"__dir__ returned less than the module's own globals: {dropped}"
        f" -- an override that does not union them hides the live "
        f"constants from every getattr-free member scan")


@pytest.mark.parametrize(
    "old_module", OLD_MODULES)
def test_every_alias_table_row_reaches_star_import(old_module: str) -> None:
    """The direction the star-import test cannot see.

    ``__all__`` is hand-written per module and the alias table is a
    second hand-written list. An ``__all__`` entry with no table row
    fails loudly (the name resolves to nothing). A table row missing
    from ``__all__`` is the silent one: ``from x import *`` reads
    ``__all__`` and never the module ``__getattr__``, so the row is
    simply dropped -- no warning, no ``AttributeError`` -- which is
    verbatim the failure fc46a9b added ``__all__`` to eliminate. The
    star-import test derives its expected set from this file's
    ``ALIASES``, so it agrees with a truncated ``__all__`` and stays
    green.

    ``ALIASES`` itself is checked against the module's table for the
    same reason: a row added there and not here would leave every other
    assertion in this file blind to the new alias.
    """
    module = importlib.import_module(old_module)
    table = module.__getattr__.deprecated_aliases  # type: ignore[attr-defined]
    exported = set(module.__all__)
    assert set(table) <= exported, (
        f"{old_module} serves {sorted(set(table) - exported)} through "
        f"__getattr__ but omits it from __all__, so `from {old_module} "
        f"import *` drops the name silently")
    assert set(table) == {a.old_name for a in ALIASES if a.old_module == old_module}, (
        f"{old_module}'s alias table and this file's ALIASES disagree; "
        f"the literal table here is what proves the bridge points where "
        f"the migration guide says, so it has to cover every row")


@pytest.mark.parametrize(
    "old_module", OLD_MODULES)
def test_star_import_binds_exactly_the_live_and_retired_names(
    old_module: str,
) -> None:
    """``from x import *`` consults ``__all__`` and nothing else.

    A module ``__getattr__`` is invisible to it, so before ``__all__``
    landed this was the one 1.x import form the bridge did not cover,
    and it failed in the mode the bridge exists to prevent: no warning,
    no ``AttributeError``, just a ``NameError`` further down at a line
    with nothing to do with the rename -- and ``alias_getattr`` bound
    into the caller's namespace in place of the vocabulary.

    The expected set is DERIVED from the module rather than listed, so a
    constant added to ``suffixes``/``titles`` without a matching
    ``__all__`` entry fails here. A hand-written list would have to be
    kept in step by the same person who forgot ``__all__``.
    """
    module = importlib.import_module(old_module)
    retired = {a.old_name for a in ALIASES if a.old_module == old_module}
    # A retired name is served by __getattr__ and never written into the
    # module, so vars() holds the live constants -- plus whatever else
    # the file imported. The type test is what separates the two:
    # `TYPE_CHECKING`, imported to hide the __getattr__ assignment from
    # mypy, has the name shape of a constant and is not vocabulary.
    # Every live constant in these four modules is a frozenset (the 2.2
    # freeze), so a new one still has to reach __all__ or fail here.
    live = {n for n, v in vars(module).items()
            if n.isupper() and not n.startswith("_")
            and isinstance(v, frozenset)}

    namespace: dict[str, object] = {}
    with pytest.warns(DeprecationWarning) as record:
        exec(f"from {old_module} import *", namespace)  # noqa: S102

    bound = {n for n in namespace if not n.startswith("__")}
    assert bound == live | retired
    # NAMES alone would pass with an __all__ entry routed to the wrong
    # constant -- the set is the same either way. Each retired name is
    # checked against its destination and each live one against the
    # module, so a mis-wired row fails here rather than in whatever
    # parses differently three releases later (#356).
    for alias in (a for a in ALIASES if a.old_module == old_module):
        destination = getattr(
            importlib.import_module(alias.new_module), alias.new_name)
        assert namespace[alias.old_name] is destination, (
            f"`from {old_module} import *` bound {alias.old_name} to "
            f"something other than {alias.new_module}.{alias.new_name}")
    for name in live:
        assert namespace[name] is vars(module)[name], (
            f"`from {old_module} import *` bound {name} to something "
            f"other than the module's own constant")
    # the helper the bridge is built from is not vocabulary; before
    # __all__ it was the only thing a star import bound here
    assert "alias_getattr" not in bound
    # one warning per retired name, each naming where to go
    assert len(record) == len(retired)
    for warning in record:
        message = str(warning.message)
        assert old_module in message, message
        assert "3.0" in message, message
    assert {n for n in retired
            if any(f"{old_module}.{n} " in str(w.message) for w in record)
            } == retired


#: Serving a 1.x name is an alias table's whole job, so the file
#: holding that table may spell it. Nothing else in the package may,
#: including the bridge machinery itself. One row per retired name,
#: mapped to the package-relative files it is allowed to appear in --
#: relative paths rather than bare filenames, so a future
#: ``locales/titles.py`` does not inherit ``config/titles.py``'s
#: exemption.
#:
#: The match below is ``name in source``: raw text, not a token, so a
#: mention in a comment or a docstring counts too. That is the intent --
#: prose naming a retired constant goes stale exactly the way code does
#: -- but it admits two hits that are not stale references, neither of
#: which can hide a real one:
#:
#: * ``NON_FIRST_NAME_PREFIXES`` contains ``PREFIXES``, so a file
#:   holding only the longer name trips both rows. It costs a duplicate
#:   line in the report; every row is still checked against the file.
#: * an unrelated identifier may simply contain a retired name --
#:   ``TITLE_PREFIXES`` reports as ``PREFIXES``. Renaming is the wrong
#:   advice there, so the failure message offers this allow-list as the
#:   other remedy.
#: DERIVED from ``ALIASES``, not listed again: the allow-listed file is
#: always the module that serves the name -- for the three that moved
#: because that is where the alias table sits, and for the two that kept
#: their module because the table sits at the bottom of the file whose
#: constant it renames. A second hand-written copy of the same five
#: names in the same file is drift surface: a sixth alias added to one
#: list and not the other would silently exempt that name from the scan
#: below rather than failing (#356).
_RETIRED_NAMES = {
    a.old_name: (
        a.old_module.removeprefix("nameparser.").replace(".", "/") + ".py",)
    for a in ALIASES
}


def test_no_internal_code_reads_a_retired_vocabulary_name() -> None:
    """The bridge exists for callers, not for us.

    An internal read of a 1.x name would warn on a path the suite may
    never take, so ``filterwarnings = ["error"]`` alone does not pin
    this. It would also aim the bridge at the wrong reader: the warning
    is attributed to the line that did the read, so a library-internal
    one reports a file inside nameparser and hands the caller advice
    about code they cannot edit.
    """
    package = pathlib.Path(nameparser.__file__).parent
    seen = set()
    offenders = []
    for path in sorted(package.rglob("*.py")):
        source = path.read_text(encoding="utf-8")
        relative = path.relative_to(package).as_posix()
        for name, allowed in _RETIRED_NAMES.items():
            if name not in source:
                continue
            seen.add(name)
            if relative not in allowed:
                offenders.append(f"{relative}: {name}")
    # every retired name is spelled in its own allow-listed file, so a
    # name the scan never saw at all means the scan is broken rather
    # than the tree clean -- the failure mode where this test passes
    # while measuring nothing
    assert seen == set(_RETIRED_NAMES), (
        f"scanned {package} and never saw "
        f"{sorted(set(_RETIRED_NAMES) - seen)}; the alias tables spell "
        f"every retired name, so the scan itself is broken")
    assert not offenders, (
        "retired 1.x vocabulary names used inside the package; move them "
        "to their 2.2 names (#293) -- or, where a hit is an unrelated "
        "identifier that merely contains a retired name, add its path to "
        f"that row's _RETIRED_NAMES allow-list: {offenders}")
