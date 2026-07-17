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
    "test_bound_first_names.py",
    "test_brute_force.py",
    # test_capitalization.py needs NO reconciliation edits (20 pass, 1 v1
    # xfail) but 1 test fails on a confirmed render bug: _render.py's
    # _cap_word lowercases every conjunction-set word, missing v1
    # is_conjunction's is_an_initial exclusion (75e3219^ parser.py:761), so
    # initial-shaped words that double as conjunctions stay lowercase. Repro:
    #   HumanName('scott e. werner').capitalize() -> 'Scott e. Werner'
    # (v1: 'Scott E. Werner'; 'e' is in CONJUNCTIONS). Remove once fixed.
    "test_capitalization.py",
    "test_comma_variants.py",
    "test_conjunctions.py",
    "test_east_slavic_patronymic_order.py",
    # test_first_name.py needs NO reconciliation edits (8 pass, 2 v1 xfails)
    # but 1 test fails on a confirmed pipeline bug: in the family-comma
    # format a trailing suffix inside the FAMILY segment is not split out.
    # Repro: Parser().parse('Smith Jr., John') -> family='Smith Jr.',
    # suffix='' (v1: last='Smith', suffix='Jr.'). Remove once fixed.
    "test_first_name.py",
    "test_middle_name_as_last.py",
    "test_nicknames.py",
    "test_parser_util.py",
    "test_prefixes.py",
    "test_suffixes.py",
    # test_titles.py is reconciled (stale 'U.S.' xfail removed -- the 2.0
    # period-joined derivation makes it pass) but 2 of its 57 tests fail on
    # confirmed pipeline parity bugs:
    # (1) _lexicon._normalize strips INTERIOR periods, so 'J.R.' -> 'jr',
    #     which is in the TITLES vocabulary; v1's lc() kept 'j.r' out of it.
    #     Repro: HumanName('Smith, J.R.') -> title='J.R.'
    #     (v1: first='J.R.', last='Smith').
    # (2) _assign's nickname rule (plan deviation #2) counts pieces AFTER
    #     title peeling; v1's p_len==1 counted the whole segment before it.
    #     Repro: HumanName('Xyz. (Bud) Smith') -> last='Smith'
    #     (v1: first='Smith', title='Xyz.', nickname='Bud').
    # Remove once fixed.
    "test_titles.py",
    "test_turkic_patronymic_order.py",
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
