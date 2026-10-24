import copy
import warnings
from collections.abc import Iterator

import pytest

from nameparser.config import CONSTANTS


# Scalar (non-collection) config attributes that individual tests mutate on the
# global CONSTANTS singleton. Several tests change these without restoring them;
# the original suite only survived because unittest happens to run methods in
# alphabetical order, so a later test reset the value. pytest runs in definition
# order, so we snapshot and restore these around every test to keep tests
# isolated regardless of order.
#
# empty_attribute_default is gone from this list: it was removed in 2.0 (#255,
# see nameparser/_config_shim.py's Constants.__setattr__), so there is no
# longer a second parsing path to snapshot/restore or dual-run against. Empty
# attributes are always ''.
_SCALAR_CONFIG_ATTRS = (
    "string_format",
    "initials_format",
    "initials_delimiter",
    "initials_separator",
    "suffix_delimiter",
    "capitalize_name",
    "force_mixed_case_capitalization",
)

# Collection config attributes (the SetManager / TupleManager constants). Tests
# that customize the global CONSTANTS — e.g. adding or removing a title — mutate
# these in place, so a shallow snapshot of the reference would not protect later
# tests. We snapshot independent copies and restore them, making collection
# mutations order-independent too.
#
# regexes is gone from this list: it is a read-only _RegexesProxy in 2.0 (set
# once in Constants.__init__), and reassigning it raises TypeError, so it can
# neither be mutated by a test nor restored by this fixture.
_COLLECTION_CONFIG_ATTRS = (
    "prefixes",
    "suffix_acronyms",
    "suffix_not_acronyms",
    "titles",
    "first_name_titles",
    "conjunctions",
    "bound_first_names",
    "non_first_name_prefixes",
    "capitalization_exceptions",
    "nickname_delimiters",
    "maiden_delimiters",
)


def pytest_collection_modifyitems(config: pytest.Config, items: list[pytest.Item]) -> None:
    """Deselect the ``serial`` tests in a parallel run's workers.

    The clock-timed scaling guards in tests/v2/test_benchmark.py bound a
    ratio of two timings, and the other workers' load stretches the
    larger input's more than the smaller's: under -n auto the
    maiden_clause row read 6.4x against its 6.0 bound on a tree that
    passes serially (measured 2026-10-23). They run in their own -n0
    pass instead, which CI makes and the summary line below asks for.
    """
    if not hasattr(config, "workerinput"):
        return
    serial = [item for item in items if item.get_closest_marker("serial")]
    if serial:
        items[:] = [item for item in items if not item.get_closest_marker("serial")]
        config.hook.pytest_deselected(items=serial)


def pytest_terminal_summary(terminalreporter: pytest.TerminalReporter,
                            config: pytest.Config) -> None:
    # a deselection nobody is told about is a guard that stopped running
    if hasattr(config, "workerinput") or not getattr(config.option, "numprocesses", None):
        return
    terminalreporter.write_line(
        "serial tests (tests/v2/test_benchmark.py) do not run in parallel; "
        "run them with: uv run pytest -n0 -m serial", yellow=True)


@pytest.fixture(autouse=True)
def _isolate_constants() -> Iterator[None]:
    """Snapshot and restore the shared CONSTANTS singleton around every test.

    Formerly also drove a parametrized dual-run over empty_attribute_default
    settings (reproducing the original tests.py __main__ block, which ran the
    whole suite twice as a regression check that the three parsing code paths
    agreed). That setting no longer exists in 2.0 (#255: empty attributes are
    always ''), so only the isolation half of the original fixture remains.
    """
    scalar_snapshot = {attr: getattr(CONSTANTS, attr) for attr in _SCALAR_CONFIG_ATTRS}
    collection_snapshot = {
        attr: copy.deepcopy(getattr(CONSTANTS, attr))
        for attr in _COLLECTION_CONFIG_ATTRS
    }
    yield
    # Restoring through the shared singleton is itself a mutation and would
    # otherwise emit the shared-CONSTANTS DeprecationWarning (#262) on every
    # single test's teardown; this fixture is infrastructure; it is not
    # exercising that deprecation, so it's silenced narrowly here rather than
    # at every test.
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", DeprecationWarning)
        for attr, value in scalar_snapshot.items():
            setattr(CONSTANTS, attr, value)
        for attr, value in collection_snapshot.items():
            setattr(CONSTANTS, attr, value)
