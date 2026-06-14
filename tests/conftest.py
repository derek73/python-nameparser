from collections.abc import Iterator

import pytest

from nameparser.config import CONSTANTS


@pytest.fixture(autouse=True, params=['', None], ids=['default', 'none'])
def empty_attribute_default(request: pytest.FixtureRequest) -> Iterator[str | None]:
    """Run every test under both empty_attribute_default settings.

    Reproduces the original tests.py __main__ block, which ran the whole suite
    twice — once with the default ('') and once with None — as a regression
    check that the three parsing code paths agree. Restoring after each test
    also isolates the global-state mutation that previously leaked between runs.
    """
    original = CONSTANTS.empty_attribute_default
    CONSTANTS.empty_attribute_default = request.param
    yield request.param
    CONSTANTS.empty_attribute_default = original
