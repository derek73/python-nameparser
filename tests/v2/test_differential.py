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


_WHEEL = "/Users/x/.cache/uv/environments-v2/w/lib/python3.11/" \
         "site-packages/nameparser/__init__.py"


def test_tell_accepts_a_matching_wheel() -> None:
    compare._check_tell({"__version__": "2.0.0", "__file__": _WHEEL}, "2.0.0")


def test_tell_accepts_an_equivalent_short_release() -> None:
    compare._check_tell({"__version__": "2.0.0", "__file__": _WHEEL}, "2.0")


def test_tell_rejects_a_version_mismatch() -> None:
    with pytest.raises(SystemExit, match="not the requested"):
        compare._check_tell(
            {"__version__": "2.1.0", "__file__": _WHEEL}, "2.0.0")


def test_tell_rejects_a_module_loaded_from_the_checkout() -> None:
    """The failure the whole design exists to make impossible. An
    editable install reports the TREE's version, so when the tree and
    the baseline share a version the version half of the tell agrees
    and only the path gives it away.
    """
    checkout = _TOOLS.parents[1] / "nameparser" / "__init__.py"
    with pytest.raises(SystemExit, match="CHECKOUT"):
        compare._check_tell(
            {"__version__": "2.0.0", "__file__": str(checkout)}, "2.0.0")


def test_tell_rejects_an_empty_tell() -> None:
    with pytest.raises(SystemExit):
        compare._check_tell({}, "2.0.0")


def test_facade_field_names_canonicalize_to_role_vocabulary() -> None:
    """Both surfaces name the same seven roles with different words,
    and Role's names win -- AGENTS.md already makes Role's declaration
    order canonical "defined once and derived everywhere", and the
    facade's vocabulary expires at 3.0."""
    assert compare._canonical_field("first") == "given"
    assert compare._canonical_field("last") == "family"
    assert compare._canonical_field("middle") == "middle"
    assert compare._canonical_field("_ambiguities") == "_ambiguities"


def test_canonical_field_is_idempotent_on_role_names() -> None:
    """Both surfaces' diffs pass through it, and the v2 surface's names
    are already canonical, so applying it must be a no-op there."""
    for role in compare.V2_FIELDS:
        assert compare._canonical_field(role) == role


def test_every_ledger_rule_names_roles_canonically() -> None:
    """The trap this guards: a rule written in facade vocabulary parses
    fine, validates fine, and simply never matches -- the ledger grows
    an entry that does nothing, classification silently loosens, and
    nothing anywhere says so. Sweeps every ledger, so a new baseline's
    file is covered the day it is added."""
    import tomllib
    ledgers = sorted(_TOOLS.glob("expected_since_*.toml"))
    assert ledgers, "no ledgers found; this test would pass vacuously"
    for ledger in ledgers:
        rules = tomllib.loads(
            ledger.read_text(encoding="utf-8")).get("change", [])
        for rule in rules:
            for field in rule.get("fields", []):
                assert field == compare._canonical_field(field), (
                    f"{ledger.name}: rule {rule['issue']!r} names "
                    f"{field!r}; use "
                    f"{compare._canonical_field(field)!r}")


@pytest.mark.parametrize("name,latin", [
    ("John Smith", True),
    ("Anna Müller", True),
    ("Jane Smith (née Jones)", True),
    ("田中さん", False),
    ("김민준", False),
    ("Хосе Сантос", False),
    ("威廉·莎士比亚", False),
])
def test_latin_only_partition(name: str, latin: bool) -> None:
    assert compare._is_latin_only(name) is latin


def test_malformed_rule_error_names_the_ledger_it_came_from() -> None:
    """There is one ledger per baseline now, so a hardcoded filename
    sends the reader to edit a rule that is not the broken one."""
    bad = [{"issue": "x"}]  # neither name_regex nor fields
    with pytest.raises(SystemExit, match="expected_since_2.0.0.toml"):
        compare.validate_rules(bad, "expected_since_2.0.0.toml")
    with pytest.raises(SystemExit, match="expected_since_1.4.0.toml"):
        compare.validate_rules([{}], "expected_since_1.4.0.toml")


def test_classify_declines_a_diff_touching_a_field_the_rule_omits() -> None:
    """The subset check is the tightness mechanism of every `fields`
    rule -- a rule claims a diff only when EVERY changed field is one it
    listed. Nothing else pinned it: a rule and a diff that name the same
    single field satisfy `<=`, `>=`, `==` and `&` alike, so the existing
    tests pass with the comparison flipped, and every deliberate field
    omission in both ledgers would quietly stop meaning anything."""
    rules = [{"issue": "given-only", "fields": ["given"]}]
    assert compare.classify("x", {"given"}, rules) == "given-only"
    assert compare.classify("x", {"given", "suffix"}, rules) is None


def test_v2_fields_matches_the_Role_enum() -> None:
    """AGENTS.md: the seven roles are 'defined once and derived
    everywhere'. compare.py cannot import Role into the WORKER (that
    runs under the old wheel), but this copy reads the working tree's
    ParsedName and must track Role. If a role were added and this tuple
    not updated, getattr never asks for it and every change in that role
    is invisible on the v2 surface -- silent under-coverage, exit 0."""
    from nameparser import Role
    assert compare.V2_FIELDS == tuple(str(r) for r in Role)


# The malformed-rule family. Every row is a way a rule can silently
# match MORE than its author meant, which is how a real regression
# becomes a classified diff and a green run. Parametrized rather than
# written one-by-one because a guard added to one member of this family
# belongs on all of it.
@pytest.mark.parametrize("rule,expect", [
    ({}, "no string 'issue'"),
    ({"issue": ""}, "no string 'issue'"),
    ({"issue": "x"}, "neither 'name_regex' nor 'fields'"),
    # a misspelled key is not ignored -- it deletes that half of the
    # narrowing and the rule matches on the other half alone
    ({"issue": "x", "name_regex": ",", "field": ["given"]}, "unknown key"),
    # wrong types: classify skips them, so the rule silently widens
    ({"issue": "x", "name_regex": ["a"], "fields": ["given"]},
     "non-string 'name_regex'"),
    ({"issue": "x", "name_regex": "a", "fields": "given"},
     "not a list of strings"),
    # an empty pattern matches every name, and name_regex rules sort
    # FIRST, so it would shadow the whole ledger
    ({"issue": "x", "name_regex": ""}, "matches the empty string"),
    ({"issue": "x", "name_regex": "(?:)"}, "matches the empty string"),
    # uncompilable: without this it raises mid-run, after the worker
    ({"issue": "x", "name_regex": "Smith("}, "invalid 'name_regex'"),
    ({"issue": "x", "fields": []}, "empty 'fields'"),
    ({"issue": "x", "fields": ["famly"]}, "not roles"),
    # facade vocabulary is not role vocabulary; it would never match
    ({"issue": "x", "fields": ["first"]}, "not roles"),
    ({"issue": "x", "fields": ["title", "given", "middle", "family",
                               "suffix", "nickname", "maiden",
                               "_ambiguities"]}, "every role"),
])
def test_validate_rules_rejects_a_rule_that_would_silently_widen(
        rule: dict, expect: str) -> None:
    with pytest.raises(SystemExit, match=expect):
        compare.validate_rules([rule], "expected_since_2.0.0.toml")


def test_validate_rules_accepts_the_shipped_ledgers() -> None:
    """The guards above must not be so strict they reject real rules."""
    import tomllib
    ledgers = sorted(_TOOLS.glob("expected_since_*.toml"))
    assert ledgers, "no ledgers found; this test would pass vacuously"
    for ledger in ledgers:
        rules = tomllib.loads(
            ledger.read_text(encoding="utf-8")).get("change", [])
        assert rules, f"{ledger.name} has no [[change]] rules"
        compare.validate_rules(rules, ledger.name)


def test_ambiguities_is_a_legal_field_name() -> None:
    """A SEGMENTATION-only diff is facade-identical by construction, so
    this pseudo-field is the only name that can classify it -- and the
    2.0 ledger's first rule depends on it."""
    compare.validate_rules(
        [{"issue": "x", "fields": ["_ambiguities"]}], "ledger.toml")


def _run_main(tmp_path, monkeypatch, ledger_body: str,
              baseline_facade: dict) -> tuple[int, str]:
    """Drive main() end to end with a faked baseline worker.

    No uv, no network. The helper exists because every unit test above
    proves a helper WORKS while none proves main() calls it -- and in a
    gate, the composition is the part that can go silently permissive.
    """
    import sys
    corpus = tmp_path / "corpus_x.jsonl"
    corpus.write_text('"John Smith"\n', encoding="utf-8")
    (tmp_path / "expected_since_1.4.0.toml").write_text(
        ledger_body, encoding="utf-8")
    monkeypatch.setattr(compare, "HERE", tmp_path)
    monkeypatch.setattr(
        compare, "_run_worker",
        lambda v, w, n: ({"__version__": v,
                          "__file__": "/wheel/nameparser/__init__.py"},
                         [{"facade": baseline_facade}]))
    monkeypatch.setattr(sys, "argv", ["compare.py", "--baseline", "1.4.0",
                                      "--corpus", str(corpus)])
    import io
    import contextlib
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        code = compare.main()
    return code, buf.getvalue()


#: 'John Smith' with the family name altered, so the tree disagrees on
#: exactly one role. The facade calls it `last`; the report and any rule
#: must call it `family`.
_DIFFERS = {"title": "", "first": "John", "middle": "", "last": "SMYTHE",
            "suffix": "", "nickname": "", "maiden": ""}


def test_main_exits_1_and_reports_an_unclassified_diff(
        tmp_path, monkeypatch) -> None:
    """The gate's entire verdict. Nothing else pins it: mutating the
    return to a bare 0 leaves every other test in this file passing,
    and the harness would report unexplained diffs on stdout while
    exiting 0 forever -- read by exit code, that is silence."""
    code, out = _run_main(
        tmp_path, monkeypatch,
        '[[change]]\nissue = "unrelated"\nname_regex = "ZZZ"\n', _DIFFERS)
    assert code == 1
    assert "UNEXPLAINED 'John Smith'" in out


def test_main_reports_the_unexplained_field_under_its_role_name(
        tmp_path, monkeypatch) -> None:
    """The block exists to be copy-pasted into a ledger rule, so the
    label it prints must be the label a rule needs. The facade calls
    this role `last`; a rule saying `last` never matches."""
    _, out = _run_main(
        tmp_path, monkeypatch,
        '[[change]]\nissue = "unrelated"\nname_regex = "ZZZ"\n', _DIFFERS)
    assert "family:" in out and "last:" not in out


def test_main_exits_0_when_every_diff_is_claimed(
        tmp_path, monkeypatch) -> None:
    code, out = _run_main(
        tmp_path, monkeypatch,
        '[[change]]\nissue = "claimed"\nfields = ["family"]\n', _DIFFERS)
    assert code == 0
    assert "UNEXPLAINED" not in out
    assert "## claimed (1)" in out


def test_main_validates_the_ledger_before_running_anything(
        tmp_path, monkeypatch) -> None:
    """validate_rules has its own tests; this pins that main CALLS it.
    Deleting the call leaves those tests passing while a match-anything
    rule shadows the ledger."""
    with pytest.raises(SystemExit, match="matches the empty string"):
        _run_main(tmp_path, monkeypatch,
                  '[[change]]\nissue = "wide"\nname_regex = ""\n', _DIFFERS)


def test_main_sorts_rules_so_file_order_is_not_load_bearing(
        tmp_path, monkeypatch) -> None:
    """A broad fields-only rule written FIRST must not claim a diff the
    specific name_regex rule below it owns. Deleting main's
    _sorted_rules call leaves _sorted_rules' own test passing."""
    _, out = _run_main(
        tmp_path, monkeypatch,
        '[[change]]\nissue = "broad"\nfields = ["family"]\n'
        '[[change]]\nissue = "specific"\nname_regex = "Smith"\n', _DIFFERS)
    assert "## specific (1)" in out and "broad" not in out


def test_check_tree_accepts_the_checkout_and_rejects_anything_else(
        tmp_path) -> None:
    """The tree side is the half that had no proof at all: the baseline
    gets a pinned wheel, a temp dir and a version tell, while the tree
    was a bare import trusted on sight."""
    inside = _TOOLS.parents[1] / "nameparser" / "__init__.py"
    assert compare._check_tree(str(inside)) == inside.resolve()
    with pytest.raises(SystemExit, match="outside this checkout"):
        compare._check_tree(str(tmp_path / "nameparser" / "__init__.py"))


def test_main_aborts_when_the_tree_side_is_not_the_checkout(
        tmp_path, monkeypatch) -> None:
    """Pins that main CALLS the tree check, not merely that the check
    works. Measured 2026-08-05: with a released 2.0.0 on PYTHONPATH,
    compare.py imported THAT and reported `intentional diffs: 0`,
    exit 0 -- both halves of the baseline tell passing. Run as a
    script, sys.path[0] is tools/differential/, which holds no
    nameparser, so PYTHONPATH outranks the editable install.

    REPO_ROOT is moved rather than the module, because relocating the
    import is what the trap does and this reproduces its EFFECT: the
    tree's nameparser is no longer under the root it must be under.
    """
    monkeypatch.setattr(compare, "REPO_ROOT", tmp_path)
    with pytest.raises(SystemExit, match="outside this checkout"):
        _run_main(tmp_path, monkeypatch,
                  '[[change]]\nissue = "x"\nname_regex = "ZZZ"\n', _DIFFERS)


def test_worker_env_strips_the_import_path_overrides(monkeypatch) -> None:
    """PEP 723 isolation does not survive PYTHONPATH -- it precedes
    site-packages, so a directory named there shadows the pinned wheel
    inside uv's own environment."""
    monkeypatch.setenv("PYTHONPATH", "/somewhere/else")
    monkeypatch.setenv("PYTHONHOME", "/elsewhere")
    monkeypatch.setenv("PATH", "/usr/bin")
    env = compare._worker_env()
    assert "PYTHONPATH" not in env and "PYTHONHOME" not in env
    assert env["PATH"] == "/usr/bin", "the rest of the env must survive"
