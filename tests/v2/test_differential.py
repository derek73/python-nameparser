"""Unit tests for the differential gate's decision logic.

`tools/` is outside `testpaths`, and adding it would run
`--doctest-modules` over the corpus builders, so `compare.py` is
imported by path -- through `_differential_fixtures.load_compare`,
shared with `test_ledger_guards.py` so the loader exists once.

Only pure logic is covered: nothing here spawns `uv` or the network.
What is tested is what produces FALSE CONFIDENCE when it silently
misbehaves -- which surfaces get compared, which ledger gets consulted,
and above all whether a version tell is believed.
"""
from pathlib import Path

import pytest

from ._differential_fixtures import _TOOLS, load_tool

compare = load_tool("compare")


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
    """Most-specific-first BETWEEN tiers. Within a tier the stable
    sort leaves file order deciding, which the 2.0 ledger relies on."""
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
    """A rule written in facade vocabulary parses, and validate_rules
    now rejects it at startup ("not roles"). Before that guard it
    validated and then silently never matched -- the ledger growing an
    entry that did nothing. This keeps a sharper message than the
    generic role check, and sweeps every ledger, so a new baseline's
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


# The malformed-rule family. Most rows are a way a rule can silently
# match MORE than its author meant, which is how a real regression
# becomes a classified diff and a green run. Three rows are the
# opposite -- an empty `fields`, a non-role name, a facade name -- and
# make a rule that can never match; those fail loudly (the diff
# surfaces as UNEXPLAINED) so their rows buy a precise message rather
# than safety. Parametrized rather than written one-by-one because a
# guard added to one member of this family belongs on all of it.
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
    ({"issue": "x", "name_regex": ""}, "matches every one of"),
    ({"issue": "x", "name_regex": "(?:)"}, "matches every one of"),
    # the shapes the empty-string probe let through: each declines ""
    # and still matches every name in every corpus
    ({"issue": "x", "name_regex": "."}, "matches every one of"),
    ({"issue": "x", "name_regex": ".+"}, "matches every one of"),
    ({"issue": "x", "name_regex": r"\b"}, "matches every one of"),
    ({"issue": "x", "name_regex": r"[\s\S]"}, "matches every one of"),
    # seven roles without _ambiguities: below baseline 2.0 that IS the
    # whole vocabulary, so it claims every diff
    ({"issue": "x", "fields": ["title", "given", "middle", "family",
                               "suffix", "nickname", "maiden"]},
     "all seven roles"),
    # uncompilable: without this it raises mid-run, after the worker
    ({"issue": "x", "name_regex": "Smith("}, "invalid 'name_regex'"),
    ({"issue": "x", "fields": []}, "empty 'fields'"),
    ({"issue": "x", "fields": ["famly"]}, "not roles"),
    # facade vocabulary is not role vocabulary; it would never match
    ({"issue": "x", "fields": ["first"]}, "not roles"),
    ({"issue": "x", "fields": ["title", "given", "middle", "family",
                               "suffix", "nickname", "maiden",
                               "_ambiguities"]}, "all seven roles"),
    ({"issue": "x", "fields": ["given"], "dormant": ""}, "not a non-empty"),
    ({"issue": "x", "fields": ["given"], "dormant": True}, "not a non-empty"),
    # widening _RULE_KEYS is exactly the edit that could let a near-miss
    # through, and a silently-ignored `dormnat` would mean the rule is
    # checked for dormancy while its author believes it is exempt
    ({"issue": "x", "fields": ["given"], "dormnat": "typo"}, "unknown key"),
    # a dormant declaration is not a pass for the rest of the checks
    ({"issue": "x", "dormant": "reason"}, "neither 'name_regex' nor 'fields'"),
])
def test_validate_rules_rejects_a_rule_that_would_silently_widen(
        rule: dict, expect: str) -> None:
    with pytest.raises(SystemExit, match=expect):
        compare.validate_rules([rule], "expected_since_2.0.0.toml")


def test_default_baseline_has_a_ledger_and_nothing_else_in_it() -> None:
    """Two facts about the OPEN cycle's ledger, which the carve-out
    below leans on and neither of us should have to derive.

    It must exist: _allowlist_for treats a missing ledger as a hard
    error, so a DEFAULT_BASELINE with no file makes a bare compare.py
    run abort -- and it would also make the carve-out inert, since it
    would name a file nothing iterates over.

    And it must define nothing at the top level except `change` and
    `never`, the two keys anything reads. This is the one ledger allowed
    to be empty, so a mistyped table header -- `[[changes]]`, `[[rules]]`,
    `[[nevr]]` -- reads as a legitimately empty open cycle everywhere
    instead of as a broken file: every sweep gets zero rules and passes,
    while the author believes they shipped a rule. The other ledgers are
    protected by having to be non-empty; this one needs saying out loud.
    """
    import tomllib
    open_cycle = _TOOLS / f"expected_since_{compare.DEFAULT_BASELINE}.toml"
    assert open_cycle.exists(), (
        f"DEFAULT_BASELINE is {compare.DEFAULT_BASELINE!r} but "
        f"{open_cycle.name} does not exist; a bare compare.py run would "
        f"hard-error, and the empty-ledger carve-out would be inert")
    keys = set(tomllib.loads(open_cycle.read_text(encoding="utf-8")))
    assert keys <= {"change", "never"}, (
        f"{open_cycle.name} defines {sorted(keys - {'change', 'never'})} at "
        f"the top level. Only `change` and `never` are read, so anything "
        f"else is a typo that would read as an empty ledger rather than as "
        f"a broken one")


def test_validate_rules_accepts_the_shipped_ledgers() -> None:
    """The guards above must not be so strict they reject real rules.

    Every ledger but one must carry rules. The exception is the OPEN
    cycle's -- the one DEFAULT_BASELINE names -- which is created the day
    its baseline is released and is legitimately empty until that
    cycle's first behavior change lands. An older ledger is history, and
    history is not empty, so emptying one is still a mistake this
    catches.
    """
    import tomllib
    open_cycle = f"expected_since_{compare.DEFAULT_BASELINE}.toml"
    ledgers = sorted(_TOOLS.glob("expected_since_*.toml"))
    assert ledgers, "no ledgers found; this test would pass vacuously"
    for ledger in ledgers:
        rules = tomllib.loads(
            ledger.read_text(encoding="utf-8")).get("change", [])
        assert rules or ledger.name == open_cycle, (
            f"{ledger.name} has no [[change]] rules, and it is not the "
            f"open cycle's ledger ({open_cycle})")
        compare.validate_rules(rules, ledger.name)


def test_ambiguities_is_a_legal_field_name() -> None:
    """A SEGMENTATION-only diff is facade-identical by construction, so
    this pseudo-field is the only name that can classify it -- and the
    2.0 ledger's first rule depends on it."""
    compare.validate_rules(
        [{"issue": "x", "fields": ["_ambiguities"]}], "ledger.toml")


#: What _run_worker was asked for, so a test can prove main forwarded
#: the baseline and the corpus rather than defaults of its own.
_WORKER_CALL: dict = {}


def _run_main(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, ledger_body: str,
              baseline_facade: dict, baseline: str = "1.4.0",
              baseline_v2: dict | None = None,
              floor: int | None = 1) -> tuple[int, str]:
    """Drive main() end to end with a faked baseline worker.

    No uv, no network. The helper exists because every unit test above
    proves a helper WORKS while none proves main() calls it -- and in a
    gate, the composition is the part that can go silently permissive.

    `baseline` defaults to 1.4.0 (facade only). Pass 2.0.0 with
    `baseline_v2` to exercise the v2 surface, including the
    ambiguity-only diff that is the stated reason to compare it.
    """
    import sys
    corpus = tmp_path / "corpus_x.jsonl"
    corpus.write_text('"John Smith"\n', encoding="utf-8")
    (tmp_path / f"expected_since_{baseline}.toml").write_text(
        ledger_body, encoding="utf-8")
    row: dict = {"facade": baseline_facade}
    if baseline_v2 is not None:
        row["v2"] = baseline_v2
    _WORKER_CALL.clear()

    def _fake(v: str, w: bool, n: list[str]) -> tuple[dict, list[dict]]:
        _WORKER_CALL.update(version=v, want_v2=w, names=list(n))
        return ({"__version__": v,
                 "__file__": "/wheel/nameparser/__init__.py"}, [row])

    # The fixture corpus needs a floor like any other. `floor=None`
    # leaves it unregistered, for the test that pins what happens when
    # a corpus arrives without one.
    if floor is not None:
        monkeypatch.setitem(compare._CORPUS_FLOORS, corpus.name, floor)
    monkeypatch.setattr(compare, "HERE", tmp_path)
    monkeypatch.setattr(compare, "_run_worker", _fake)
    monkeypatch.setattr(sys, "argv", ["compare.py", "--baseline", baseline,
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
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
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
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """The block exists to be copy-pasted into a ledger rule, so the
    label it prints must be the label a rule needs. The facade calls
    this role `last`; a rule saying `last` never matches."""
    _, out = _run_main(
        tmp_path, monkeypatch,
        '[[change]]\nissue = "unrelated"\nname_regex = "ZZZ"\n', _DIFFERS)
    assert "family:" in out and "last:" not in out


def test_main_exits_0_when_every_diff_is_claimed(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    code, out = _run_main(
        tmp_path, monkeypatch,
        '[[change]]\nissue = "claimed"\nfields = ["family"]\n', _DIFFERS)
    assert code == 0
    assert "UNEXPLAINED" not in out
    assert "## claimed (1)" in out


def test_main_validates_the_ledger_before_running_anything(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """validate_rules has its own tests; this pins that main CALLS it.
    Deleting the call leaves those tests passing while a match-anything
    rule shadows the ledger."""
    with pytest.raises(SystemExit, match="matches every one of"):
        _run_main(tmp_path, monkeypatch,
                  '[[change]]\nissue = "wide"\nname_regex = ""\n', _DIFFERS)


def test_main_sorts_a_name_regex_rule_ahead_of_a_fields_only_one(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """A broad fields-only rule written FIRST must not claim a diff the
    specific name_regex rule below it owns. Deleting main's
    _sorted_rules call leaves _sorted_rules' own test passing."""
    _, out = _run_main(
        tmp_path, monkeypatch,
        '[[change]]\nissue = "broad"\nfields = ["family"]\n'
        '[[change]]\nissue = "specific"\nname_regex = "Smith"\n', _DIFFERS)
    assert "## specific (1)" in out and "broad" not in out


def test_check_tree_accepts_the_checkout_and_rejects_anything_else(
        tmp_path: Path) -> None:
    """The tree side is the half that had no proof at all: the baseline
    gets a pinned wheel, a temp dir and a version tell, while the tree
    was a bare import trusted on sight."""
    inside = _TOOLS.parents[1] / "nameparser" / "__init__.py"
    assert compare._check_tree(str(inside)) == inside.resolve()
    with pytest.raises(SystemExit, match="not from this checkout's source"):
        compare._check_tree(str(tmp_path / "nameparser" / "__init__.py"))


def test_main_aborts_when_the_tree_side_is_not_the_checkout(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
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
    with pytest.raises(SystemExit, match="not from this checkout's source"):
        _run_main(tmp_path, monkeypatch,
                  '[[change]]\nissue = "x"\nname_regex = "ZZZ"\n', _DIFFERS)


def test_worker_env_strips_the_import_path_overrides(
        monkeypatch: pytest.MonkeyPatch) -> None:
    """PEP 723 isolation does not survive PYTHONPATH -- it precedes
    site-packages, so a directory named there shadows the pinned wheel
    inside uv's own environment."""
    monkeypatch.setenv("PYTHONPATH", "/somewhere/else")
    monkeypatch.setenv("PYTHONHOME", "/elsewhere")
    monkeypatch.setenv("PATH", "/usr/bin")
    env = compare._worker_env()
    assert "PYTHONPATH" not in env and "PYTHONHOME" not in env
    assert env["PATH"] == "/usr/bin", "the rest of the env must survive"


class _FakePopen:
    """Records how _run_worker spawned the child, and replays a canned
    stdout. Lets the subprocess-facing guards be tested without uv."""

    last: dict = {}
    out: str = ""
    rc: int = 0

    def __init__(self, argv: list[str], **kw: object) -> None:
        _FakePopen.last = {"argv": argv, **kw}
        self.returncode = _FakePopen.rc

    def communicate(self, payload: str) -> tuple[str, str]:
        _FakePopen.last["stdin"] = payload
        return _FakePopen.out, ""


def _fake_popen(monkeypatch: pytest.MonkeyPatch, out: str,
                rc: int = 0) -> type[_FakePopen]:
    _FakePopen.out, _FakePopen.rc = out, rc
    monkeypatch.setattr(compare.subprocess, "Popen", _FakePopen)
    return _FakePopen


_TELL = ('{"__version__": "1.4.0", '
         '"__file__": "/wheel/nameparser/__init__.py"}')
_ROW = '{"facade": {"first": "John"}}'


def test_run_worker_strips_the_import_path_overrides_from_the_child(
        monkeypatch: pytest.MonkeyPatch) -> None:
    """_worker_env has its own test; this pins that _run_worker USES
    it. Deleting `env=_worker_env()` left all 61 tests green -- the
    same shape as the bug the previous review found, a proved helper
    with an unproved call site."""
    monkeypatch.setenv("PYTHONPATH", "/shadow")
    _fake_popen(monkeypatch, f"{_TELL}\n{_ROW}\n")
    compare._run_worker("1.4.0", False, ["John Smith"])
    env = _FakePopen.last["env"]
    assert "PYTHONPATH" not in env and "PYTHONHOME" not in env


def test_run_worker_aborts_on_a_nonzero_exit(
        monkeypatch: pytest.MonkeyPatch) -> None:
    _fake_popen(monkeypatch, "", rc=3)
    with pytest.raises(SystemExit, match="exited 3"):
        compare._run_worker("1.4.0", False, ["John Smith"])


def test_run_worker_aborts_on_empty_output(
        monkeypatch: pytest.MonkeyPatch) -> None:
    _fake_popen(monkeypatch, "")
    with pytest.raises(SystemExit, match="not even a version tell"):
        compare._run_worker("1.4.0", False, ["John Smith"])


def test_run_worker_aborts_when_fewer_results_than_names(
        monkeypatch: pytest.MonkeyPatch) -> None:
    """The guard behind main's zip(), which truncates silently. This is
    the comparing-fewer-names-than-you-think failure."""
    _fake_popen(monkeypatch, f"{_TELL}\n{_ROW}\n")
    with pytest.raises(SystemExit, match="1 results for 2 corpus names"):
        compare._run_worker("1.4.0", False, ["John Smith", "Jane Doe"])


def test_run_worker_checks_the_tell_before_returning_results(
        monkeypatch: pytest.MonkeyPatch) -> None:
    wrong = ('{"__version__": "9.9.9", '
             '"__file__": "/wheel/nameparser/__init__.py"}')
    _fake_popen(monkeypatch, f"{wrong}\n{_ROW}\n")
    with pytest.raises(SystemExit, match="not the requested"):
        compare._run_worker("1.4.0", False, ["John Smith"])


@pytest.mark.parametrize("rel", [
    ".venv/lib/python3.11/site-packages/nameparser/__init__.py",
    "build/lib/nameparser/__init__.py",
    "dist/unpacked/nameparser/__init__.py",
])
def test_check_tree_rejects_a_wheel_sitting_inside_the_checkout(
        rel: str) -> None:
    """The hole in the first version of this guard. It asked "is this
    under the repo", but the repo contains .venv/, build/ and dist/,
    any of which can hold a released wheel -- so
    PYTHONPATH=<repo>/build/lib was the same trap one directory to the
    left, and uv never touches build/ to self-heal it."""
    with pytest.raises(SystemExit, match="not from this checkout's source"):
        compare._check_tree(str(compare.REPO_ROOT / rel))


def test_check_tree_resolves_before_comparing() -> None:
    """Without .resolve(), a path escaping via .. reads as inside."""
    escaped = compare.REPO_ROOT / "nameparser" / ".." / ".." / "x" \
        / "nameparser" / "__init__.py"
    with pytest.raises(SystemExit, match="not from this checkout's source"):
        compare._check_tree(str(escaped))


#: The tree's own reading of the fixture name, on both surfaces. A fake
#: baseline row built from these differs from the tree in exactly the
#: one field a test chooses to alter.
_SAME_FACADE = {"title": "", "first": "John", "middle": "", "last": "Smith",
                "suffix": "", "nickname": "", "maiden": ""}
_SAME_V2 = {"title": "", "given": "John", "middle": "", "family": "Smith",
            "suffix": "", "nickname": "", "maiden": "", "_ambiguities": []}


def test_main_compares_the_v2_surface_from_baseline_2_0(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """A SEGMENTATION-only diff is facade-identical by construction, so
    it is invisible unless main actually unions the v2 surface into the
    diff set. That diff shape is the whole stated reason _surfaces_for
    compares v2 from 2.0 on -- and every mutation that disabled it
    (want_v2 forced False, the v2 union deleted, `|=` changed to `=`)
    passed the suite before this test existed.
    """
    v2 = {**_SAME_V2, "_ambiguities": ["SEGMENTATION"]}
    code, out = _run_main(
        tmp_path, monkeypatch,
        '[[change]]\nissue = "unrelated"\nname_regex = "ZZZ"\n',
        _SAME_FACADE, baseline="2.0.0", baseline_v2=v2)
    assert code == 1, "an ambiguity-only regression must not exit 0"
    assert "UNEXPLAINED 'John Smith'" in out
    assert "_ambiguities:" in out
    assert "[v2 surface only]" in out, (
        "the tag distinguishes an ambiguity-kind change from a field "
        "change; without it the row reads as a field diff")


def test_main_claims_an_ambiguity_only_diff_when_a_rule_names_it(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    v2 = {**_SAME_V2, "_ambiguities": ["SEGMENTATION"]}
    code, out = _run_main(
        tmp_path, monkeypatch,
        '[[change]]\nissue = "seg"\nfields = ["_ambiguities"]\n',
        _SAME_FACADE, baseline="2.0.0", baseline_v2=v2)
    assert code == 0 and "## seg (1)" in out


def test_main_reports_a_role_once_when_both_surfaces_moved(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """The `seen` set. Both surfaces name the same role, so a family
    change shows on each; printing it twice would read as two findings."""
    _, out = _run_main(
        tmp_path, monkeypatch,
        '[[change]]\nissue = "unrelated"\nname_regex = "ZZZ"\n',
        {**_SAME_FACADE, "last": "SMYTHE"}, baseline="2.0.0",
        baseline_v2={**_SAME_V2, "family": "SMYTHE"})
    assert out.count("family:") == 1


def test_main_forwards_the_baseline_and_corpus_to_the_worker(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Otherwise main could read the 2.0 ledger while comparing against
    1.4, or compare a truncated corpus, and every other test would pass."""
    _run_main(tmp_path, monkeypatch,
              '[[change]]\nissue = "x"\nname_regex = "ZZZ"\n',
              _SAME_FACADE, baseline="2.0.0", baseline_v2=_SAME_V2)
    assert _WORKER_CALL == {"version": "2.0.0", "want_v2": True,
                            "names": ["John Smith"]}


def test_main_asks_for_the_facade_alone_below_2_0(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _run_main(tmp_path, monkeypatch,
              '[[change]]\nissue = "x"\nname_regex = "ZZZ"\n', _SAME_FACADE)
    assert _WORKER_CALL["want_v2"] is False


def test_every_shipped_corpus_has_a_floor_and_clears_it() -> None:
    """Two bindings, so neither half can rot alone: every corpus file
    on disk must have a floor, and must be at or above it.

    The floor exists because the empty-file guard only catches a corpus
    that lost EVERY name. One truncated to a handful passes that guard,
    and the run exits 0 having compared a fraction of what its summary
    line reports -- the harness's own stated nightmare, reached by a
    file that is merely short rather than absent.
    """
    import json
    corpora = sorted(_TOOLS.glob("corpus*.jsonl"))
    assert corpora, "no corpora found; this test would pass vacuously"
    for path in corpora:
        names = [json.loads(line) for line
                 in path.read_text(encoding="utf-8").splitlines()
                 if line.strip()]
        floor = compare._CORPUS_FLOORS.get(path.name)
        assert floor is not None, (
            f"{path.name} has no _CORPUS_FLOORS entry; add one a little "
            f"under its {len(names)} names")
        assert len(names) >= floor, (
            f"{path.name} holds {len(names)}, below its floor {floor}")


def test_a_floor_names_a_corpus_that_exists() -> None:
    """The other direction: a floor for a file nobody ships is a guard
    that can never fire, and reads as coverage that is not there."""
    on_disk = {p.name for p in _TOOLS.glob("corpus*.jsonl")}
    assert set(compare._CORPUS_FLOORS) <= on_disk


def test_main_aborts_on_a_truncated_corpus(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """A corpus below its floor must stop the run, not shrink it."""
    with pytest.raises(SystemExit, match="below its floor"):
        _run_main(tmp_path, monkeypatch,
                  '[[change]]\nissue = "x"\nname_regex = "ZZZ"\n',
                  _SAME_FACADE, floor=50)


def test_main_aborts_on_a_corpus_with_no_floor(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Adding a corpus without a floor must be a decision, not a
    silent default -- the same force-a-decision shape the Script
    tables use."""
    with pytest.raises(SystemExit, match="no entry in _CORPUS_FLOORS"):
        _run_main(tmp_path, monkeypatch,
                  '[[change]]\nissue = "x"\nname_regex = "ZZZ"\n',
                  _SAME_FACADE, floor=None)


# The exclusion grammar. Every row is a way a [[never]] entry can look
# correct and protect nothing -- the same failure the rules' own
# validator exists for, pointed at the section that DISABLES
# classification instead of the one that performs it.
@pytest.mark.parametrize("entry,expect", [
    ({}, "no string 'why'"),
    ({"why": ""}, "no string 'why'"),
    ({"why": "x"}, "no string 'name_regex'"),
    ({"why": "x", "name_regex": "Smith("}, "invalid 'name_regex'"),
    ({"why": "x", "name_regex": "a"}, "no 'examples'"),
    ({"why": "x", "name_regex": "a", "examples": []}, "no 'examples'"),
    ({"why": "x", "name_regex": "a", "examples": "b"}, "not a list of strings"),
    ({"why": "x", "name_regex": "a", "examples": ["a", 1]},
     "not a list of strings"),
    # an example the entry does not actually protect
    ({"why": "x", "name_regex": "zzz", "examples": ["John Smith"]},
     "does not match its own"),
    # a misspelled key deletes half the declaration, exactly as for rules
    ({"why": "x", "name_regex": "a", "examples": ["a"], "reason": "b"},
     "unknown key"),
    # would silence the entire ledger
    ({"why": "x", "name_regex": ".", "examples": ["a"]},
     "matches every one of"),
])
def test_validate_exclusions_rejects_an_entry_that_protects_nothing(
        entry: dict, expect: str) -> None:
    with pytest.raises(SystemExit, match=expect):
        compare.validate_exclusions([entry], "expected_since_1.4.0.toml")


def test_validate_exclusions_accepts_the_shipped_entries() -> None:
    """The guards above must not be so strict they reject real entries."""
    import tomllib
    for ledger in sorted(_TOOLS.glob("expected_since_*.toml")):
        parsed = tomllib.loads(ledger.read_text(encoding="utf-8"))
        compare.validate_exclusions(parsed.get("never", []), ledger.name)


def test_classify_refuses_an_excluded_shape() -> None:
    """The whole point: an excluded name reports UNEXPLAINED however
    many rules would otherwise claim it. Two do, for the shape this
    was built for -- fix(comma-family) on file order, and the
    fields-only fix(suffix-routing) which has no name_regex at all and
    so reaches every name."""
    rules = [{"issue": "broad", "name_regex": ","},
             {"issue": "broader", "fields": ["given", "suffix"]}]
    never = [{"why": "parity", "name_regex": r"(?i)\bph\.\s*d\.\s*$",
              "examples": ["John Smith, Ph. D."]}]
    assert compare.classify("John Smith, Ph. D.", {"suffix"}, rules) == "broad"
    assert compare.classify(
        "John Smith, Ph. D.", {"suffix"}, rules, never) is None
    # a name the exclusion does not cover is unaffected
    assert compare.classify("Smith, Dr.", {"suffix"}, rules, never) == "broad"


@pytest.mark.parametrize("entry,expect", [
    ({"why": "x", "name_regex": "a", "examples": ["a"], "fields": "given"},
     "not a list of strings"),
    ({"why": "x", "name_regex": "a", "examples": ["a"], "fields": []},
     "empty 'fields'"),
    ({"why": "x", "name_regex": "a", "examples": ["a"], "fields": ["nope"]},
     "not roles"),
    # the facade's vocabulary is not the role vocabulary
    ({"why": "x", "name_regex": "a", "examples": ["a"], "fields": ["first"]},
     "not roles"),
    # all seven means "any diff", which is what omitting the key does
    ({"why": "x", "name_regex": "a", "examples": ["a"],
      "fields": ["title", "given", "middle", "family", "suffix",
                 "nickname", "maiden"]}, "omit 'fields'"),
])
def test_validate_exclusions_rejects_a_bad_fields_narrowing(
        entry: dict, expect: str) -> None:
    with pytest.raises(SystemExit, match=expect):
        compare.validate_exclusions([entry], "expected_since_1.4.0.toml")


def test_an_excluded_shape_stays_classifiable_on_other_roles() -> None:
    """The reason `fields` exists. ASCII parens mark nicknames, maiden
    names, suffixes and credentials alike, so an exclusion that names
    the nickname reading must not silence a suffix diff on the same
    name. Such a diff would not be hidden -- an excluded name reports
    UNEXPLAINED and exits non-zero -- but it could never be classified
    as intended either, leaving an area under active development
    permanently unexplainable."""
    rules = [{"issue": "catch-all", "fields": ["given", "suffix",
                                               "nickname", "middle"]}]
    never = [{"why": "ascii pairs were already handled in 1.4",
              "name_regex": r"\w\s+\([^)]+\)\s+\w",
              "fields": ["nickname", "middle"],
              "examples": ["John (Jack) Kennedy"]}]
    name = "Lon (Jr.) Williams"
    # the reading the exclusion names is refused
    assert compare.classify(name, {"nickname"}, rules, never) is None
    assert compare.classify(name, {"middle"}, rules, never) is None
    # a different reading of the same name is still classifiable
    assert compare.classify(name, {"suffix"}, rules, never) == "catch-all"
    # and a mixed diff is not a subset of the exclusion, so it survives
    assert compare.classify(
        name, {"nickname", "suffix"}, rules, never) == "catch-all"


def test_entry_matches_is_the_question_classify_asks() -> None:
    """classify() and the dormancy check must agree on what a rule
    would claim. They share this predicate so they cannot drift."""
    rule = {"issue": "x", "name_regex": "Smith", "fields": ["given"]}
    assert compare._entry_matches(rule, "John Smith", {"given"})
    # regex misses
    assert not compare._entry_matches(rule, "John Jones", {"given"})
    # fields is a SUBSET test, not an intersection
    assert not compare._entry_matches(rule, "John Smith", {"given", "family"})
    # a rule with neither key admits everything validate_rules lets exist
    assert compare._entry_matches({"issue": "x"}, "anyone", {"suffix"})
    # the ignore-don't-reject contract the docstring rests on: validate_*
    # already rejected these at startup, so re-judging them here would put
    # the two in a position to disagree
    assert compare._entry_matches({"issue": "x", "name_regex": 5}, "anyone", {"suffix"})
    assert compare._entry_matches({"issue": "x", "fields": "given"}, "anyone", {"given"})
    # an exclusion entry narrows on the same two keys and carries no `issue`
    assert compare._entry_matches(
        {"why": "x", "name_regex": "Smith", "examples": ["John Smith"]},
        "John Smith", {"given"})


def test_validate_rules_accepts_a_declared_dormant_rule() -> None:
    """`dormant` is a legal key, so a rule that declares one is not
    rejected as a misspelling."""
    compare.validate_rules(
        [{"issue": "x", "fields": ["given"], "dormant": "no corpus name"}],
        "expected_since_1.4.0.toml")
