import pytest


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

