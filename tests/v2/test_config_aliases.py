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
from collections.abc import Iterator

import pytest

import nameparser

#: (old module, old name, new module, new name), one row per alias.
ALIASES = [
    ("nameparser.config.prefixes", "PREFIXES",
     "nameparser.config.particles", "PARTICLES"),
    ("nameparser.config.prefixes", "NON_FIRST_NAME_PREFIXES",
     "nameparser.config.particles", "NON_GIVEN_NAME_PARTICLES"),
    ("nameparser.config.bound_first_names", "BOUND_FIRST_NAMES",
     "nameparser.config.bound_given_names", "BOUND_GIVEN_NAMES"),
    ("nameparser.config.titles", "FIRST_NAME_TITLES",
     "nameparser.config.titles", "GIVEN_NAME_TITLES"),
    ("nameparser.config.suffixes", "SUFFIX_NOT_ACRONYMS",
     "nameparser.config.suffixes", "SUFFIX_WORDS"),
]


def _uncache(module: str, name: str) -> None:
    """Drop a resolved alias from the shim module's globals."""
    importlib.import_module(module).__dict__.pop(name, None)


@pytest.fixture(autouse=True)
def _cold_aliases() -> Iterator[None]:
    """Serve every test in this file a cold bridge.

    The bridge caches each resolved alias into the shim module's
    globals, so the DeprecationWarning fires once per name per process
    -- which is the contract, and which makes any test of that warning
    order-dependent by construction: whoever touches the name first
    consumes the only warning. Clearing before AND after means this
    file neither inherits a warmed cache from an earlier test nor
    leaves one behind for the rest of the suite.
    """
    for module, name, _, _ in ALIASES:
        _uncache(module, name)
    yield
    for module, name, _, _ in ALIASES:
        _uncache(module, name)


@pytest.mark.parametrize(
    ("old_module", "old_name", "new_module", "new_name"),
    ALIASES,
    ids=[f"{m.rsplit('.', 1)[-1]}.{n}" for m, n, _, _ in ALIASES],
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


def test_from_import_is_attributed_to_the_importing_module() -> None:
    """The form the ``stacklevel`` comment singles out, and the one most
    callers use. ``from x import Y`` resolves the alias while the
    importing module's frame is on top, so the report names the file
    holding the import -- the line that has to be edited."""
    code = compile("from nameparser.config.prefixes import PREFIXES\n",
                   "caller_module.py", "exec")
    with pytest.warns(DeprecationWarning) as record:
        exec(code, {"__name__": "caller_module"})
    assert (record[0].filename, record[0].lineno) == ("caller_module.py", 1)


@pytest.mark.parametrize(
    ("old_module", "old_name"),
    [(m, n) for m, n, _, _ in ALIASES],
    ids=[f"{m.rsplit('.', 1)[-1]}.{n}" for m, n, _, _ in ALIASES],
)
def test_old_name_warns_once_then_becomes_a_plain_global(
    old_module: str, old_name: str,
) -> None:
    module = importlib.import_module(old_module)
    with pytest.warns(DeprecationWarning):
        first = getattr(module, old_name)
    # the suite runs under filterwarnings=error, so a second warning
    # here would raise rather than merely be recorded
    second = getattr(module, old_name)
    assert first is second


@pytest.mark.parametrize(
    "old_module", sorted({m for m, _, _, _ in ALIASES}))
def test_unknown_attribute_still_raises(old_module: str) -> None:
    module = importlib.import_module(old_module)
    with pytest.raises(AttributeError, match="NOT_A_CONSTANT"):
        module.NOT_A_CONSTANT  # noqa: B018


@pytest.mark.parametrize(
    ("old_module", "old_name"),
    [(m, n) for m, n, _, _ in ALIASES],
    ids=[f"{m.rsplit('.', 1)[-1]}.{n}" for m, n, _, _ in ALIASES],
)
def test_dir_advertises_the_old_names(old_module: str, old_name: str) -> None:
    assert old_name in dir(importlib.import_module(old_module))


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
_RETIRED_NAMES = {
    "PREFIXES": ("config/prefixes.py",),
    "NON_FIRST_NAME_PREFIXES": ("config/prefixes.py",),
    "BOUND_FIRST_NAMES": ("config/bound_first_names.py",),
    # these two kept their module; the exemption is for the alias table
    # at the bottom of the file, which names them as strings
    "FIRST_NAME_TITLES": ("config/titles.py",),
    "SUFFIX_NOT_ACRONYMS": ("config/suffixes.py",),
}


def test_no_internal_code_reads_a_retired_vocabulary_name() -> None:
    """The bridge exists for callers, not for us.

    An internal read of a 1.x name would warn on a path the suite may
    never take, so ``filterwarnings = ["error"]`` alone does not pin
    this. A stale internal reference also rots the bridge in the worst
    way: the write-back cache means the FIRST reader consumes the only
    warning, so a real caller downstream could be told nothing at all.
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
