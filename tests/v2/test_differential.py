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


def test_a_rule_with_fields_and_no_regex_is_rejected() -> None:
    """The shape #451 retired, closed so it cannot return.

    A rule with no `name_regex` claims every name whose diff fits its
    `fields`, and _CORPUS_CLAIMS records its reach as the whole corpus
    -- already at maximum, so arrivals never move it. The one rule with
    this shape grew from 4 explained names to 14 across six behavior
    families with every guard green.
    """
    with pytest.raises(SystemExit, match="no 'name_regex'"):
        compare.validate_rules(
            [{"issue": "fix(x) a rule with no name narrowing",
              "fields": ["given", "family", "suffix"]}],
            "test_ledger.toml")


def test_dormant_does_not_buy_an_exemption_from_the_ban() -> None:
    """`dormant` says a rule explains nothing; it does not say the rule
    may be unbounded.

    The two are independent, and conflating them is the plausible
    future edit: "it is declared idle, so its reach cannot matter."
    It can. `dormant` is a claim about TODAY's corpus, and #372's
    lesson is that a rule's reach is what it will claim tomorrow --
    the retired catch-all explained four names when it was written.
    A regexless rule declared dormant would sit at the whole corpus
    the moment one diffing name arrived, and its `dormant` reason
    would then be false as well as its bound missing.

    Pinned because check ORDER is what makes this hold: the dormancy
    check runs before the #451 one, so a malformed `dormant` still
    reports its own message, and a well-formed one falls through to
    the ban. Nothing else asserts that a valid `dormant` does not
    short-circuit it (#453 review).
    """
    with pytest.raises(SystemExit, match="no 'name_regex'"):
        compare.validate_rules(
            [{"issue": "fix(x) idle and unbounded",
              "fields": ["given", "family"],
              "dormant": "a reason nobody could fault"}],
            "test_ledger.toml")
    # the other order still holds: a malformed `dormant` reports its
    # own defect rather than the ban's, because it is checked first
    with pytest.raises(SystemExit, match="'dormant' that is not a"):
        compare.validate_rules(
            [{"issue": "fix(x) idle and unbounded",
              "fields": ["given", "family"], "dormant": ""}],
            "test_ledger.toml")


def test_a_rule_with_a_regex_and_no_fields_or_both_stays_legal() -> None:
    """The neighbouring shapes #451 did NOT retire. `name_regex` alone
    still narrows by name; `name_regex` plus `fields` narrows by both.
    Only the fields-only shape -- no name narrowing at all -- is new
    to reject."""
    compare.validate_rules(
        [{"issue": "x", "name_regex": "Smith"}], "test_ledger.toml")
    compare.validate_rules(
        [{"issue": "x", "name_regex": "Smith", "fields": ["given"]}],
        "test_ledger.toml")


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
    # whole vocabulary, so it claims every diff. name_regex is along
    # for the ride so this pins the roles check, not the #451 one.
    ({"issue": "x", "name_regex": "Smith",
      "fields": ["title", "given", "middle", "family",
                 "suffix", "nickname", "maiden"]},
     "all seven roles"),
    # uncompilable: without this it raises mid-run, after the worker
    ({"issue": "x", "name_regex": "Smith("}, "invalid 'name_regex'"),
    ({"issue": "x", "name_regex": "Smith", "fields": []}, "empty 'fields'"),
    ({"issue": "x", "name_regex": "Smith", "fields": ["famly"]},
     "not roles"),
    # facade vocabulary is not role vocabulary; it would never match
    ({"issue": "x", "name_regex": "Smith", "fields": ["first"]},
     "not roles"),
    ({"issue": "x", "name_regex": "Smith",
      "fields": ["title", "given", "middle", "family",
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
        [{"issue": "x", "name_regex": "Smith", "fields": ["_ambiguities"]}],
        "ledger.toml")


#: What _run_worker was asked for, so a test can prove main forwarded
#: the baseline and the corpus rather than defaults of its own.
_WORKER_CALL: dict = {}


def _run_main(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, ledger_body: str,
              baseline_facade: dict,
              extra: list[tuple[str, dict]] | None = None,
              baseline: str = "1.4.0",
              baseline_v2: dict | None = None,
              floor: int | None = 1) -> tuple[int, str]:
    """Drive main() end to end with a faked baseline worker.

    No uv, no network. The helper exists because every unit test above
    proves a helper WORKS while none proves main() calls it -- and in a
    gate, the composition is the part that can go silently permissive.

    `baseline` defaults to 1.4.0 (facade only). Pass 2.0.0 with
    `baseline_v2` to exercise the v2 surface, including the
    ambiguity-only diff that is the stated reason to compare it.

    `extra` appends more (name, baseline_facade) pairs to the corpus,
    in order, alongside the fixture's own 'John Smith'. It exists so a
    test can mix a diffing and a non-diffing name -- the single-name
    corpus below is structurally incapable of that.
    """
    import json
    import sys
    corpus = tmp_path / "corpus_x.jsonl"
    names = ["John Smith"] + [n for n, _ in (extra or ())]
    corpus.write_text(
        "\n".join(json.dumps(n) for n in names) + "\n", encoding="utf-8")
    (tmp_path / f"expected_since_{baseline}.toml").write_text(
        ledger_body, encoding="utf-8")
    rows: list[dict] = [{"facade": baseline_facade}]
    if baseline_v2 is not None:
        rows[0]["v2"] = baseline_v2
    for _, facade in (extra or ()):
        rows.append({"facade": facade})
    _WORKER_CALL.clear()

    def _fake(v: str, w: bool, n: list[str]) -> tuple[dict, list[dict]]:
        _WORKER_CALL.update(version=v, want_v2=w, names=list(n))
        return ({"__version__": v,
                 "__file__": "/wheel/nameparser/__init__.py"}, rows)

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
        '[[change]]\nissue = "claimed"\nname_regex = "Smith"\n'
        'fields = ["family"]\n', _DIFFERS)
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


def test_main_rejects_a_broad_fields_only_rule_before_running_anything(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """This used to pin main's _sorted_rules call: a broad fields-only
    rule written FIRST could not claim a diff a specific name_regex
    rule below it owned, because _sorted_rules puts every name_regex
    rule ahead of every fields-only one. That scenario is retired by
    #451 -- a fields-only rule is rejected at validate_rules, so main()
    never reaches _sorted_rules with one. What is left to pin here is
    that main() still validates before running, for this shape too,
    the same composition fact test_main_validates_the_ledger_before_
    running_anything covers for a different malformed shape. The
    tier-sort mechanism itself stays pinned directly by
    test_name_regex_rules_sort_ahead_of_fields_only_rules and
    test_rule_sort_is_stable_within_a_tier, which call _sorted_rules
    without going through validate_rules.
    """
    with pytest.raises(SystemExit, match="no 'name_regex'"):
        _run_main(
            tmp_path, monkeypatch,
            '[[change]]\nissue = "broad"\nfields = ["family"]\n'
            '[[change]]\nissue = "specific"\nname_regex = "Smith"\n',
            _DIFFERS)


def test_main_exits_1_and_names_a_rule_that_explained_nothing(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """The #372 gate. `idle` matches no diffing name, so it explains
    nothing and is not declared dormant -- the run must say so and fail,
    even though every diff here IS explained.

    Nothing else pins this: dropping the dormancy terms from main's
    return, or deleting the report loop, leaves every other test green.
    """
    code, out = _run_main(
        tmp_path, monkeypatch,
        '[[change]]\nissue = "explains-it"\nname_regex = "Smith"\n'
        'fields = ["family"]\n'
        '[[change]]\nissue = "idle"\nname_regex = "ZZNOSUCHNAME"\n'
        'fields = ["family"]\n', _DIFFERS)
    assert code == 1
    assert "EXPLAINED NOTHING 'idle'" in out
    assert "may have been reverted" in out
    # the diff itself was explained; this failure is only about the rule
    assert "unexplained: 0" in out


def test_main_exits_1_and_names_an_over_declared_rule(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """The #452 gate. `wide` explains the only diff here and declares
    two roles it never moves -- the run must say so and fail, even
    though every diff IS explained and no rule is idle.

    Nothing else pins this, which is the same gap _run_main's own
    docstring names for the dormancy check: five unit tests prove
    over_declared_rules WORKS and none proved main() calls it.
    Measured on mutants built outside the repo -- deleting the
    `roles_by_issue` accumulator, deleting this report loop, or
    dropping `or overwide` from main's return each leaves the whole
    suite green (#455 review).
    """
    code, out = _run_main(
        tmp_path, monkeypatch,
        '[[change]]\nissue = "wide"\nname_regex = "Smith"\n'
        'fields = ["family", "given", "suffix"]\n', _DIFFERS)
    assert code == 1
    # the ledger is named before the issue: this rule's correct
    # `fields` differ per baseline, so the file is part of the finding
    assert "OVER-DECLARED" in out and "'wide'" in out
    assert out.count(".toml: 'wide'") == 1
    assert "['given', 'suffix']" in out      # the roles nothing moves
    assert "['family']" in out               # the repair
    # the diff itself was explained; this failure is only about the rule
    assert "unexplained: 0" in out


def test_main_accepts_a_rule_declaring_exactly_what_it_moves(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """The other direction, so the #452 check cannot pass by being
    unconditional. `exact` declares the one role the one diff moves,
    and the run is silent and exits 0.

    Its partner above would still pass if over_declared_rules reported
    every rule; this is what makes that impossible.
    """
    code, out = _run_main(
        tmp_path, monkeypatch,
        '[[change]]\nissue = "exact"\nname_regex = "Smith"\n'
        'fields = ["family"]\n', _DIFFERS)
    assert code == 0
    assert "OVER-DECLARED" not in out


def test_main_only_feeds_diffing_names_to_the_dormancy_check(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """If a non-diffing name reached `diffing`, a rule matching only
    that name would appear to match a name in the diff set -- and
    since it is the only rule that matches it, dormant_rules would
    classify it via that same rule and diagnose it as its own
    shadower ("shadowed by 'idle'"), instead of the correct
    'reverted' diagnosis for a rule that matches no diffing name.

    'Alice Jones' is added via `extra` with a baseline facade equal to
    what the tree parses it as -- it does not diff -- alongside the
    fixture's own diffing 'John Smith'. `idle`'s regex matches only
    'Alice Jones', so it must be reported reverted, never shadowed.
    """
    code, out = _run_main(
        tmp_path, monkeypatch,
        '[[change]]\nissue = "explains-it"\nname_regex = "Smith"\n'
        'fields = ["family"]\n'
        '[[change]]\nissue = "idle"\nname_regex = "Jones"\n'
        'fields = ["family"]\n', _DIFFERS,
        extra=[("Alice Jones",
                {"title": "", "first": "Alice", "middle": "",
                 "last": "Jones", "suffix": "", "nickname": "",
                 "maiden": ""})])
    assert code == 1
    assert "EXPLAINED NOTHING 'idle'" in out
    assert "may have been reverted" in out
    assert "shadowed by 'idle'" not in out
    # the diffing name's diff was explained; this failure is only
    # about the rule that matched no diffing name
    assert "unexplained: 0" in out


def test_main_exits_1_when_a_declared_dormant_rule_wakes_up(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """The other direction. A `dormant` reason that stopped being true is
    a false statement in the ledger, so it fails the run too."""
    code, out = _run_main(
        tmp_path, monkeypatch,
        '[[change]]\nissue = "awake"\nname_regex = "Smith"\n'
        'fields = ["family"]\n'
        'dormant = "claims to be idle, but explains the only diff here"\n',
        _DIFFERS)
    assert code == 1
    assert "NO LONGER DORMANT 'awake'" in out


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
        '[[change]]\nissue = "seg"\nname_regex = "Smith"\n'
        'fields = ["_ambiguities"]\n',
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
    many rules would otherwise claim it. Two did, for the shape this
    was built for -- fix(comma-family) on file order, and the
    fields-only fix(suffix-routing) which had no name_regex at all and
    so reached every name. #451 deleted that second one, and no ledger
    has a fields-only rule now; the fixture below keeps one because
    the behaviour it pins is compare.classify's, not any ledger's."""
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
        [{"issue": "x", "name_regex": "ZZNOSUCHNAME", "fields": ["given"],
          "dormant": "no corpus name"}],
        "expected_since_1.4.0.toml")


def test_dormant_rules_reports_a_rule_whose_behavior_vanished() -> None:
    """The #372 case: a rule matching no diffing name at all. Its fix
    was probably reverted, and today the run exits 0 regardless."""
    rules = [{"issue": "fix(a)", "name_regex": "Smith", "fields": ["given"]},
             {"issue": "fix(b)", "name_regex": "Jones", "fields": ["given"]}]
    report = compare.dormant_rules(
        rules, {"fix(a)"}, [("John Smith", {"given"})])
    assert report.awake == ()
    assert [d.issue for d in report.undeclared] == ["fix(b)"]
    assert report.undeclared[0].kind == "reverted"


def test_dormant_rules_names_the_rule_that_shadows_one() -> None:
    """A rule can explain nothing because a broader rule written ahead
    of it in the same tier claimed every diff it would have claimed.
    That is a different diagnosis with a different fix, so it gets
    different words."""
    rules = [{"issue": "fix(broad)", "name_regex": "Smith",
              "fields": ["given", "family"]},
             {"issue": "fix(narrow)", "name_regex": "John Smith",
              "fields": ["given"]}]
    report = compare.dormant_rules(
        rules, {"fix(broad)"}, [("John Smith", {"given"})])
    assert [d.issue for d in report.undeclared] == ["fix(narrow)"]
    assert report.undeclared[0].kind == "shadowed"
    assert report.undeclared[0].detail == "fix(broad)"


def test_dormant_rules_distinguishes_an_excluded_shape() -> None:
    """Third diagnosis: the rule matches a diffing name, but a [[never]]
    entry refuses it, so no rule claims it. Reporting that as `reverted`
    would send someone hunting for a fix that was never undone."""
    rules = [{"issue": "fix(a)", "name_regex": "Smith", "fields": ["given"]}]
    never = [{"why": "protected", "name_regex": "Smith"}]
    report = compare.dormant_rules(
        rules, set(), [("John Smith", {"given"})], never)
    assert [d.issue for d in report.undeclared] == ["fix(a)"]
    assert report.undeclared[0].kind == "excluded"


def test_dormant_rules_is_silent_about_a_declared_rule() -> None:
    rules = [{"issue": "fix(a)", "name_regex": "Smith", "fields": ["given"],
              "dormant": "no corpus name reaches it"}]
    report = compare.dormant_rules(rules, set(), [])
    assert report.undeclared == () and report.awake == ()


def test_dormant_rules_reports_a_declared_rule_that_woke_up() -> None:
    """The other direction. A `dormant` declaration that stopped being
    true is a false statement in the ledger, and the roster pattern in
    this tree checks both directions or it checks nothing."""
    rules = [{"issue": "fix(a)", "fields": ["given"], "dormant": "was idle"}]
    report = compare.dormant_rules(
        rules, {"fix(a)"}, [("John Smith", {"given"})])
    assert report.awake == ("fix(a)",)
    assert report.undeclared == ()


def test_dormant_rules_names_the_shadower_that_does_the_shadowing() -> None:
    """Which rule to go and look at. Picking the alphabetically first
    claimant would send someone to the rule that took one name while
    another took the rest."""
    rules = [{"issue": "fix(a)", "name_regex": "Alpha", "fields": ["given"]},
             {"issue": "fix(z)", "name_regex": "Zeta", "fields": ["given"]},
             {"issue": "fix(idle)", "name_regex": "Alpha|Zeta",
              "fields": ["given"]}]
    report = compare.dormant_rules(
        rules, {"fix(a)", "fix(z)"},
        [("Alpha One", {"given"}), ("Zeta One", {"given"}),
         ("Zeta Two", {"given"}), ("Zeta Three", {"given"})])
    assert [d.issue for d in report.undeclared] == ["fix(idle)"]
    assert report.undeclared[0].detail == "fix(z)"


def test_dormant_rules_sorts_before_diagnosing() -> None:
    """classify() must be asked in the order main() asks it. These rules
    are written broad-first, but _sorted_rules puts the name_regex rule
    ahead of the fields-only one, so 'specific' is what actually claims
    'John Smith' -- which makes 'broad' the dormant one, shadowed by it.

    Without the internal sort this returns the diagnosis backwards,
    naming 'specific' as dormant and shadowed by 'broad'. Nothing else
    pins that line: main() always pre-sorts before calling this.
    """
    rules = [{"issue": "broad", "fields": ["given"]},
             {"issue": "specific", "name_regex": "Smith",
              "fields": ["given"]}]
    report = compare.dormant_rules(
        rules, {"specific"}, [("John Smith", {"given"})])
    assert [d.issue for d in report.undeclared] == ["broad"]
    assert report.undeclared[0].detail == "specific"


def test_over_declared_rules_flags_a_role_nothing_explains() -> None:
    """The #452 shape: `fields` wider than every diff beneath it.

    classify() admits a rule when the diff is a SUBSET of `fields`, so
    the excess is not inert -- it lets the rule keep claiming a name
    whose diff shrank out of the declared role, which is what #410
    found on fix(#424) with no run saying so.
    """
    rules = [{"issue": "fix(x) wide", "name_regex": "Smith",
              "fields": ["given", "family", "suffix"]}]
    found = compare.over_declared_rules(
        rules, {"fix(x) wide": {"family", "suffix"}})
    assert len(found) == 1
    assert found[0].issue == "fix(x) wide"
    assert found[0].unused == ("given",)
    assert found[0].observed == ("family", "suffix")


def test_over_declared_rules_accepts_exactly_exercised_fields() -> None:
    """Equality, not superset: `fields` may name every role its diffs
    move and no more."""
    rules = [{"issue": "fix(x) exact", "name_regex": "Smith",
              "fields": ["family", "suffix"]}]
    assert compare.over_declared_rules(
        rules, {"fix(x) exact": {"family", "suffix"}}) == ()


def test_over_declared_rules_skips_a_dormant_rule() -> None:
    """A `dormant` rule is this check's business never, even when it
    HAS explained something.

    The input matters, and the obvious one is vacuous: passing an empty
    `roles_by_issue` is caught by the `if not moved` guard whether or
    not the dormant clause exists, so the test would pass on its
    deletion -- mutation-tested, and the reason this row is written the
    way it is (#452 review). The separating input is a dormant rule
    that DID explain a diff, which is also the only interesting one: it
    is exactly the state dormant_rules reports as NO LONGER DORMANT.
    That is one defect with one remedy -- remove the `dormant` key --
    and reporting it here as well would demand a second, contradictory
    one: narrow `fields` on a rule whose real problem is that its
    dormancy claim went false.
    """
    rules = [{"issue": "fix(x) idle", "name_regex": "Smith",
              "fields": ["given", "family"], "dormant": "no corpus name"}]
    assert compare.over_declared_rules(
        rules, {"fix(x) idle": {"family"}}) == ()


def test_over_declared_rules_skips_a_rule_with_no_fields() -> None:
    """A regex-only rule declares no roles, so it has nothing to
    over-declare. (`fields` with no name_regex cannot exist since
    #451.)"""
    rules = [{"issue": "fix(x) regex only", "name_regex": "Smith"}]
    assert compare.over_declared_rules(
        rules, {"fix(x) regex only": {"family"}}) == ()


def test_over_declared_rules_skips_a_rule_that_explained_nothing() -> None:
    """Explaining nothing is dormancy's finding, not this one. Reporting
    it here too would make one defect fail twice with two different
    remedies."""
    rules = [{"issue": "fix(x) silent", "name_regex": "Smith",
              "fields": ["given", "family"]}]
    assert compare.over_declared_rules(rules, {}) == ()


def test_validate_rules_rejects_two_rules_sharing_an_issue() -> None:
    """The dormancy check identifies a rule by its `issue`, so a
    duplicate lets one rule hide behind the other -- it can explain
    nothing and never be reported. Measured before this check existed:
    dormant_rules returned undeclared=() awake=() for a rule that
    genuinely explained nothing."""
    with pytest.raises(SystemExit, match="sharing the issue"):
        compare.validate_rules(
            [{"issue": "dup", "name_regex": "Smith", "fields": ["given"]},
             {"issue": "dup", "name_regex": "Jones", "fields": ["given"]}],
            "expected_since_1.4.0.toml")


harvester = load_tool("build_issues_corpus")


def test_a_backticked_name_is_harvested() -> None:
    """This tracker writes names in backticks, because issues are
    markdown. Matching only quoted names left the corpus whose whole
    purpose is "what users reported" blind to how this project reports
    (#413).
    """
    assert harvester._harvest(
        "the tussenvoegsel in `Beethoven, Ludwig van` is filed behind "
        "the given name") == {"Beethoven, Ludwig van"}


def test_a_call_inside_backticks_yields_the_name_not_the_call() -> None:
    """The reason backticks are a SECOND PASS rather than a third
    alternative in one pattern.

    A reporter writes the failing input as a call inside a code span.
    Regex scanning takes the leftmost match, so a backtick alternative
    starts one character before the HumanName branch can and swallows
    the whole span -- harvesting the call and losing the name inside
    it. This is the bug the two-pass structure exists to prevent, and
    it is reachable from a single string.
    """
    got = harvester._harvest('reported as `HumanName("John  Q  Doe")`')
    assert got == {"John  Q  Doe"}

    # ... and a call anywhere in the span, not only at its start
    assert not any("HumanName(" in n for n in
                   harvester._harvest('see `Foo HumanName("Jane Roe")`'))


def test_a_sentence_is_not_a_name() -> None:
    """Prose is quoted and backticked as often as names are, and a
    capitalized phrase is well-formed enough that the character screen
    cannot see it.
    """
    for text in ("`What this gate does not cover` is the section",
                 "the note said `Takes everything` about it",
                 "`C is CONSTANTS` in that example",
                 "wrote `NO Latin twins on purpose` there",
                 "raised `TypeError: a bytes-like object is required`"):
        assert harvester._harvest(text) == set(), text


def test_the_sentence_screen_keeps_its_hands_off_names() -> None:
    """The screen matches a function word only where it is written
    LOWERCASE, which is what keeps it off names: a name capitalizes its
    words and a sentence's function words do not.

    Every name here contains a word that is in the stop list, and every
    one is a real naming convention -- Burmese, Norwegian, Estonian,
    Cantonese, Luhya, Dutch, Lakota. Without the case test the screen
    drops all of them, silently, from the one corpus meant to catch
    what users report.
    """
    for name in ("U Than Shwe", "Sven Are Olsen", "Kertu Must",
                 "Chan On Kei", "Wafula Were", "John Does",
                 "Marie Takes War Bonnet", "Rob And Beth Edmunds",
                 "Duke of Wellington", "Anh Do", "Will De Groot"):
        assert harvester._harvest(f"reported `{name}` today") == {name}, name
