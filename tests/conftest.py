from collections.abc import Generator

import pytest

from tests.checkout import HAS_CHECKOUT


def pytest_collection_modifyitems(config: pytest.Config, items: list[pytest.Item]) -> None:
    """Deselect the ``serial`` tests in a parallel run's workers.

    The clock-timed tests in tests/v2/test_benchmark.py (the scaling
    ratios and the thousand-names backstop) mostly bound a ratio of two
    timings, and the other workers' load stretches the
    larger input's more than the smaller's: under -n auto the
    maiden_clause row read 6.4x against its 6.0 bound on a tree that
    passes serially (measured 2026-10-23, on the wall clock they read
    then). They run in their own -n0 pass instead, which CI makes and
    the summary line below asks for. They read CPU time now, which still
    moves under contention (decisions/parse-cost, 2026-11-11), so they
    keep that pass. The frame, call and shift counts
    in the same module are not marked and run here, since a count does
    not move with load.
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
        "serial tests (the clock-timed ones in tests/v2/test_benchmark.py) do "
        "not run in parallel; run them with: uv run pytest -n0 -m serial",
        yellow=True)



# How the differential harness fails outside a checkout, each a prefix
# that survives pytest's truncation of a long message: check_source,
# refusing a nameparser imported from elsewhere; the --base check,
# refusing a checkout with no package in it; and reading or recording a
# base copied from the checkout's nameparser/, which is not there.
_HARNESS_REFUSALS = ("imported nameparser from", "no nameparser package at",
                     "reading the base ", "recording the base ")


@pytest.hookimpl(wrapper=True)
def pytest_runtest_makereport(
        item: pytest.Item, call: pytest.CallInfo[None],
) -> Generator[None, pytest.TestReport, pytest.TestReport]:
    """Name the missing mark when a harness test fails outside a checkout.

    Run against the installed package (tests/checkout.py), a test that
    goes through the differential harness fails on its refusal, a
    message about PYTHONPATH and editable installs that is right for a
    developer and wrong here: the test needs @needs_checkout."""
    report: pytest.TestReport = yield
    if (report.failed and not HAS_CHECKOUT
            and any(r in str(report.longrepr) for r in _HARNESS_REFUSALS)):
        report.sections.append((
            "installed-package layout",
            "This test goes through the differential harness, which refuses "
            "a nameparser imported from outside the checkout. Mark it "
            "@needs_checkout (tests/checkout.py)."))
    return report
