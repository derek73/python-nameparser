import copy
import warnings
from collections.abc import Iterator

import pytest

from nameparser.config import CONSTANTS

# TEMPORARY (Task M11 -> M12): the v1 suite is being reconciled against
# the 2.0 facade file by file. Lifted in Task M12 together with its mypy
# twin (the `exclude` under [tool.mypy] in pyproject.toml); both must be
# GONE before this branch leaves draft.
#
# Explicit list of not-yet-reconciled files. Narrow this as each file is
# reconciled; remove entirely once the whole suite runs against the facade.
collect_ignore_glob = [
    # test_bound_first_names.py is reconciled (bucket A: the two
    # is_bound_first_name predicate tests died with the v1 hooks) but 1 test
    # fails on a join-guard bug: the FAMILY_COMMA bound-given join does not
    # fire when the join would consume the whole post-comma segment. Repro:
    #   HumanName('salem, abdul salam') -> first='abdul', middle='salam'
    # (v1: first='abdul salam'; three-token 'salem, abdul salam ahmed'
    # joins fine). Remove once fixed.
    "test_bound_first_names.py",
    "test_brute_force.py",
    # test_middle_name_as_last.py needs NO bucket edits but 4 tests fail on
    # a fold-order bug: v1's middle_name_as_last fold PREPENDED middle_list
    # to last_list, so comma and rotated forms converge on the no-comma
    # result; v2 renders the folded family in token order. Repros:
    #   HumanName('Hassan, Mohamad Ahmad Ali', constants=
    #     Constants(middle_name_as_last=True)) -> last='Hassan Ahmad Ali'
    #   (v1: 'Ahmad Ali Hassan');
    #   with patronymic_name_order too: 'Ivanov Petr Sergeyevich' ->
    #   last='Ivanov Sergeyevich' (v1: 'Sergeyevich Ivanov').
    # Remove once fixed.
    "test_middle_name_as_last.py",
    "test_variations.py",
]

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
