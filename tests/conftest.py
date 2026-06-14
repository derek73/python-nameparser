from collections.abc import Iterator

import pytest

from nameparser.config import CONSTANTS

# Scalar (non-collection) config attributes that individual tests mutate on the
# global CONSTANTS singleton. Several tests change these without restoring them;
# the original suite only survived because unittest happens to run methods in
# alphabetical order, so a later test reset the value. pytest runs in definition
# order, so we snapshot and restore these around every test to keep tests
# isolated regardless of order.
_SCALAR_CONFIG_ATTRS = (
    "empty_attribute_default",
    "string_format",
    "initials_format",
    "initials_delimiter",
    "capitalize_name",
    "force_mixed_case_capitalization",
)


@pytest.fixture(autouse=True, params=['', None], ids=['default', 'none'])
def empty_attribute_default(request: pytest.FixtureRequest) -> Iterator[str | None]:
    """Run every test under both empty_attribute_default settings, isolating global config.

    Reproduces the original tests.py __main__ block, which ran the whole suite
    twice — once with the default ('') and once with None — as a regression
    check that the three parsing code paths agree. The surrounding snapshot of
    the scalar CONSTANTS attributes restores any global config a test mutates,
    so tests do not leak state into one another (the original relied on
    unittest's alphabetical method ordering to mask such leaks).
    """
    snapshot = {attr: getattr(CONSTANTS, attr) for attr in _SCALAR_CONFIG_ATTRS}
    CONSTANTS.empty_attribute_default = request.param
    yield request.param
    for attr, value in snapshot.items():
        setattr(CONSTANTS, attr, value)
