"""Unit tests for the differential gate's decision logic.

`tools/` is outside `testpaths`, and adding it would run
`--doctest-modules` over the corpus builders, so `compare.py` is
imported by path here -- the same way `test_regex_sync.py` already
imports `build_cjk_corpus`.

Only pure logic is covered: nothing here spawns `uv` or the network.
What is tested is what produces FALSE CONFIDENCE when it silently
misbehaves -- which surfaces get compared, which ledger gets consulted,
and above all whether a version tell is believed.
"""
import importlib.util
from pathlib import Path
from types import ModuleType

import pytest

_TOOLS = Path(__file__).parents[2] / "tools" / "differential"


def _load_compare() -> ModuleType:
    spec = importlib.util.spec_from_file_location(
        "differential_compare", _TOOLS / "compare.py")
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


compare = _load_compare()


def test_parse_version_pads_a_short_release_to_three_parts() -> None:
    """A requested '2.0' and a wheel reporting '2.0.0' are the same
    release; comparing the raw strings would call them unequal and
    abort a correct run as a tell mismatch."""
    assert compare._parse_version("2.0") == compare._parse_version("2.0.0")


def test_parse_version_orders_numerically_not_lexically() -> None:
    """The bug string comparison would introduce: '10.0.0' sorts BELOW
    '2.0.0' as text."""
    assert compare._parse_version("10.0.0") > compare._parse_version("2.0.0")


def test_parse_version_ignores_a_prerelease_segment() -> None:
    assert compare._parse_version("2.0.0rc1") == (2, 0, 0)


def test_parse_version_rejects_a_string_with_no_release_in_it() -> None:
    with pytest.raises(SystemExit, match="cannot parse a version"):
        compare._parse_version("not-a-version")


@pytest.mark.parametrize("version,expected", [
    ("1.4.0", {"facade"}),
    ("1.4", {"facade"}),
    ("1.9.9", {"facade"}),
    ("2.0.0", {"facade", "v2"}),
    ("2.0", {"facade", "v2"}),
    ("2.1.0", {"facade", "v2"}),
    # the row string comparison gets wrong: '10.0.0' < '2.0.0' as text
    ("10.0.0", {"facade", "v2"}),
])
def test_surfaces_are_derived_from_the_baseline(
        version: str, expected: set[str]) -> None:
    assert compare._surfaces_for(version) == expected


def test_allowlist_path_is_named_for_its_baseline() -> None:
    assert compare._allowlist_for("1.4.0").name == "expected_since_1.4.0.toml"


def test_allowlist_for_a_baseline_with_no_ledger_is_a_hard_error() -> None:
    """Not an empty rule set. An empty set classifies nothing, so every
    diff reports as unexplained -- which reads as a catastrophic
    regression rather than as a missing file, and sends the reader
    hunting the parser instead of the ledger."""
    with pytest.raises(SystemExit, match="no allowlist for baseline"):
        compare._allowlist_for("9.9.9")


def test_name_regex_rules_sort_ahead_of_fields_only_rules() -> None:
    """Most-specific-first, so file order stops being load-bearing."""
    rules = [{"issue": "broad", "fields": ["first"]},
             {"issue": "specific", "name_regex": "Smith"}]
    assert [r["issue"] for r in compare._sorted_rules(rules)] \
        == ["specific", "broad"]


def test_rule_sort_is_stable_within_a_tier() -> None:
    rules = [{"issue": "a", "name_regex": "A"},
             {"issue": "b", "name_regex": "B"}]
    assert [r["issue"] for r in compare._sorted_rules(rules)] == ["a", "b"]


def test_classify_returns_none_when_no_rule_matches() -> None:
    rules = [{"issue": "x", "name_regex": "Zzz"}]
    assert compare.classify("John Smith", {"first"}, rules) is None


def test_classify_takes_the_first_matching_rule() -> None:
    rules = [{"issue": "specific", "name_regex": "Smith"},
             {"issue": "broad", "fields": ["first"]}]
    assert compare.classify("John Smith", {"first"}, rules) == "specific"


def test_worker_source_carries_the_requested_pin() -> None:
    src = compare._worker_source("2.0.0", want_v2=True)
    assert 'dependencies = ["nameparser==2.0.0"]' in src


def test_worker_source_always_emits_a_version_tell() -> None:
    """The tell is the whole defence against a worker that silently
    resolved to the checkout, so it is not conditional on anything."""
    for want_v2 in (True, False):
        src = compare._worker_source("1.4.0", want_v2=want_v2)
        assert "__version__" in src and "__file__" in src


def test_worker_source_gates_the_v2_import_on_the_baseline() -> None:
    """1.4 has no nameparser.parse to import; asking for it would make
    the worker die on import rather than report a clean facade diff."""
    assert "WANT_V2 = False" in compare._worker_source("1.4.0", want_v2=False)
    assert "WANT_V2 = True" in compare._worker_source("2.0.0", want_v2=True)
