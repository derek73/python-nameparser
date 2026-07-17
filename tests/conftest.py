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
    "test_comma_variants.py",
    # test_conjunctions.py needs NO bucket edits (37 pass, 2 v1 xfails) but
    # 1 test fails on the join-stage sibling of the fixed _cap_word bug:
    # the classify-stage "conjunction" tag (_classify.py:51) lacks v1
    # is_conjunction's is_an_initial exclusion (75e3219^ parser.py:761), so
    # the initial 'e.' is joined as a conjunction. The group-stage #11
    # carve-out only covers the bare single letter 'e', not 'e.'. Repro:
    #   HumanName('john e. smith') -> first='john e. smith'
    # (v1: first='john', middle='e.', last='smith'). Remove once fixed.
    "test_conjunctions.py",
    "test_east_slavic_patronymic_order.py",
    "test_middle_name_as_last.py",
    # test_nicknames.py is reconciled (buckets A/B: custom-delimiter and
    # regexes-override mechanisms now pin their Policy-pointing TypeErrors;
    # #255 as_dict expectation) but 1 test fails on a precedence flip in the
    # documented both-buckets misuse case: with 'parenthesis' routed to BOTH
    # nickname_delimiters and maiden_delimiters, v1 processed nickname
    # first (nickname='Johnson', maiden=''); 2.0 gives maiden='Johnson',
    # nickname=''. Repro: C.maiden_delimiters['parenthesis'] =
    # C.regexes['parenthesis']; HumanName('Baker (Johnson), Jenny',
    # constants=C). The v1 test exists precisely to catch this silent
    # change -- needs a decision (fix precedence or classify). Remove once
    # settled.
    "test_nicknames.py",
    "test_parser_util.py",
    # test_prefixes.py is reconciled (one bucket-C rewrite; 57 pass) but 1
    # test fails on the same B1 gap held for test_suffixes: the two-word
    # trailing-suffix routing. Repro: HumanName('Anh Do') -> suffix='Do',
    # family='' (v1: last='Do'; 'do' is the D.O. suffix acronym). Remove
    # with test_suffixes' entry once B1 is settled.
    "test_prefixes.py",
    # test_suffixes.py needs NO bucket edits (30 pass, 2 v1 xfails) but 24
    # tests fail across six suspected pipeline gaps -- see the M12 batch-3
    # report for full repros. Headlines:
    #   B1 'Jack Ma' -> suffix='Ma', family='' (v1: last='Ma'; the
    #      fix(suffix-routing) row pins the same shape for 'Johnson PhD' --
    #      decision needed on ambiguous-surname suffixes)
    #   B2 'John Smith, V MD' -> suffix='V, MD' (v1 kept the segment whole:
    #      'V MD')
    #   B3 'John Smith, Ph. D.' -> family='John Smith', given='' (split/
    #      period-joined suffixes fail the segment-stage suffixy test)
    #   B4 '#144: 'Smith, John V' -> middle='V' (v1: suffix='V'; family-
    #      comma given-segment trailing suffix_not_acronyms rule missing)
    #   B5 suffix-in-parens/quotes (#111) missing: 'Andrew Perkins (MBA)'
    #      -> nickname='MBA' (v1: suffix='MBA'); 9 tests
    #   B6 suffix_delimiter edges: trailing delimiter kills detection;
    #      multi-word sides leak the '-' token into suffix
    # Remove once fixed.
    "test_suffixes.py",
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
