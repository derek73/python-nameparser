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
_SCALAR_CONFIG_ATTRS = (
    "empty_attribute_default",
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
    "regexes",
    "nickname_delimiters",
    "maiden_delimiters",
)


@pytest.fixture(autouse=True, params=['', None], ids=['default', 'none'])
def empty_attribute_default(request: pytest.FixtureRequest) -> Iterator[str | None]:
    """Run every test under both empty_attribute_default settings, isolating global config.

    Reproduces the original tests.py __main__ block, which ran the whole suite
    twice — once with the default ('') and once with None — as a regression
    check that the three parsing code paths agree. The surrounding snapshot of
    both the scalar and the collection CONSTANTS attributes restores any global
    config a test mutates, so tests do not leak state into one another (the
    original relied on unittest's alphabetical method ordering to mask such
    leaks).
    """
    scalar_snapshot = {attr: getattr(CONSTANTS, attr) for attr in _SCALAR_CONFIG_ATTRS}
    collection_snapshot = {
        attr: copy.deepcopy(getattr(CONSTANTS, attr))
        for attr in _COLLECTION_CONFIG_ATTRS
    }
    # empty_attribute_default assignment is deprecated (#255); this fixture's
    # own systematic exercise of both settings across the whole suite is
    # infrastructure, not a test of the deprecation itself, so it's silenced
    # here (narrowly, around just the assignment) rather than at every one of
    # its ~1500 call sites. Must not wrap `yield` -- that would suppress
    # DeprecationWarning for the test body itself, hiding real ones.
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", DeprecationWarning)
        CONSTANTS.empty_attribute_default = request.param
    yield request.param
    for attr, value in scalar_snapshot.items():
        if attr == "empty_attribute_default":
            with warnings.catch_warnings():
                warnings.simplefilter("ignore", DeprecationWarning)
                setattr(CONSTANTS, attr, value)
        else:
            setattr(CONSTANTS, attr, value)
    for attr, value in collection_snapshot.items():
        setattr(CONSTANTS, attr, value)
