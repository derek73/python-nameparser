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

from ._differential_fixtures import (
    _LEDGERS, _TOOLS, _claimed, _rules, load_tool)

compare = load_tool("compare")
shapes = load_tool("shapes")


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


def test_worker_source_emits_initials_on_both_surfaces() -> None:
    """#484: initials() is a derived view the seven-field diff cannot
    see. The facade has had initials() since 1.x, so the facade row
    carries it at EVERY baseline; the v2 row carries it wherever the
    v2 surface is compared at all.

    A text check, and the two asserts do not buy the same thing.
    `_v2_row` is defined unconditionally in the template body, which
    is version-independent -- so its assert at want_v2=False pins
    template TEXT, not behavior. The facade line is the one whose
    BEHAVIOR depends on the installed wheel -- 1.4.0's
    `HumanName.initials()` has to exist and answer -- which no text
    check can see, and is why the sibling below RUNS the template
    instead of reading it:
    test_the_worker_reads_a_default_order_line_as_the_tree_does."""
    for version, want_v2 in (("1.4.0", False), ("2.0.0", True)):
        src = compare._worker_source(version, want_v2=want_v2)
        assert 'row["facade"]["_initials"] = hn.initials() or ""' in src
        assert 'row["_initials"] = p.initials() or ""' in src


def test_every_shape_orders_resolve_and_bound_sanely() -> None:
    """The inventory's two contracts: an `order` is a public constant
    name on the installed tree that Policy actually accepts as a
    name_order -- hasattr alone would admit "HumanName" or any other
    real attribute, failing only at runtime inside the worker -- and a
    shape with an order cannot claim a pre-2.0 baseline -- Policy
    shipped in 2.0.0, so an earlier min_baseline would send an order
    to a worker with no Policy to apply it.

    `_parse_version(shape.min_baseline)` is called for EVERY shape,
    not just ordered ones, so a typo'd min on shapes 1-3 (whose order
    is None and so skips the >= (2, 0, 0) check) is still caught --
    an unparsable string raises SystemExit on its own.
    """
    import nameparser
    from nameparser import Policy
    for sid, shape in shapes.SHAPES.items():
        parsed_min = compare._parse_version(shape.min_baseline)
        if shape.order is not None:
            assert hasattr(nameparser, shape.order), (sid, shape.order)
            Policy(name_order=getattr(nameparser, shape.order))
            assert parsed_min >= (2, 0, 0), sid


def test_worker_reads_entry_objects_and_applies_an_order() -> None:
    """The template must parse {"name","order"} lines and build the
    order's parser; rendering is checked textually the way
    test_worker_source_carries_the_requested_pin does."""
    src = compare._worker_source("2.2.0", want_v2=True)
    assert '"order"' in src and "getattr(nameparser, order)" in src


def test_entries_below_their_shapes_min_baseline_are_skipped(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """A 1.4 worker must never see an order it cannot honor; the
    skip is printed so a shrunken comparison is never silent."""
    import contextlib
    import io
    import json as _json
    import sys
    corpus = tmp_path / "corpus_x.jsonl"
    corpus.write_text(
        _json.dumps({"name": "Ménil Christophe du", "shape": 4},
                    ensure_ascii=False) + "\n"
        + _json.dumps("John Smith") + "\n", encoding="utf-8")
    (tmp_path / "expected_since_1.4.0.toml").write_text("", encoding="utf-8")
    monkeypatch.setitem(compare._CORPUS_FLOORS, corpus.name, 1)
    monkeypatch.setitem(compare._CORPUS_TIERS, corpus.name, "contract")
    monkeypatch.setattr(compare, "HERE", tmp_path)
    sent: dict = {}

    def _fake(v: str, w: bool,
              entries: list[dict[str, object]]) -> tuple[dict, list[dict]]:
        sent["entries"] = list(entries)
        return ({"__version__": v,
                 "__file__": "/wheel/nameparser/__init__.py"},
                [{"facade": {"title": "", "first": "John", "middle": "",
                             "last": "Smith", "suffix": "", "nickname": "",
                             "maiden": "",
                             # the tree's own initials for this name.
                             # This test is about the skip decision, so
                             # the fake baseline agrees by construction
                             # on the #484 pseudo-field too.
                             "_initials": "J. S."}}])

    monkeypatch.setattr(compare, "_run_worker", _fake)
    monkeypatch.setattr(sys, "argv", ["compare.py", "--baseline", "1.4.0",
                                      "--corpus", str(corpus)])
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        code = compare.main()
    assert code == 0
    assert [e["name"] for e in sent["entries"]] == ["John Smith"]
    out = buf.getvalue()
    assert ("skipped 1 name tagged shape(s) [4]: baseline 1.4.0 predates "
            "their minimum (2.0.0)") in out
    assert "corpus_x.jsonl (2, 1 skipped)" in out


def test_an_order_none_shapes_later_minimum_does_not_skip_the_entry(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """The companion to test_entries_below_their_shapes_min_baseline_
    are_skipped, pinning the other half of the same branch: shape 6's
    min_baseline (2.1.0) is DOCUMENTARY, not a skip trigger, because
    `order` is None -- the default policy already exists at 1.4.0, so
    there is no order for that baseline's worker to fail to honor.
    Without the `shapes_by_id[shape].order is not None` gate in
    compare.py's skip loop, this entry would be silently dropped the
    same way an order-bearing one correctly is above -- this proves
    the gate actually distinguishes the two rather than reverting to
    shape-blind or, worse, always-skip behavior."""
    import contextlib
    import io
    import json as _json
    import sys
    from nameparser import HumanName
    name = "김민준"
    corpus = tmp_path / "corpus_x.jsonl"
    corpus.write_text(
        _json.dumps({"name": name, "shape": 6}, ensure_ascii=False) + "\n",
        encoding="utf-8")
    (tmp_path / "expected_since_1.4.0.toml").write_text("", encoding="utf-8")
    monkeypatch.setitem(compare._CORPUS_FLOORS, corpus.name, 1)
    monkeypatch.setitem(compare._CORPUS_TIERS, corpus.name, "contract")
    monkeypatch.setattr(compare, "HERE", tmp_path)
    # The tree's own facade reading, used as the "1.4.0" side too --
    # this test is about the skip decision, not about what the parse
    # produces, so an old/new facade that agree by construction keeps
    # a real diff from muddying the assertion.
    old_facade = {k: (v or "") for k, v in HumanName(name).as_dict().items()}
    old_facade["_initials"] = HumanName(name).initials() or ""
    sent: dict = {}

    def _fake(v: str, w: bool,
              entries: list[dict[str, object]]) -> tuple[dict, list[dict]]:
        sent["entries"] = list(entries)
        return ({"__version__": v,
                 "__file__": "/wheel/nameparser/__init__.py"},
                [{"facade": old_facade}])

    monkeypatch.setattr(compare, "_run_worker", _fake)
    monkeypatch.setattr(sys, "argv", ["compare.py", "--baseline", "1.4.0",
                                      "--corpus", str(corpus)])
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        code = compare.main()
    assert code == 0
    assert [e["name"] for e in sent["entries"]] == [name]
    out = buf.getvalue()
    assert "skipped" not in out
    assert "corpus_x.jsonl (1)" in out


def _tree_v2_row(name: str, order: str | None) -> dict:
    """The tree's own v2 reading of `name` under `order`, built the
    same way main()'s tree side and the worker template's _v2_row both
    build it. Used to fabricate a baseline row that agrees (or, with a
    field mutated, disagrees) with the tree, without needing a real
    baseline wheel.

    `order` is None for the DEFAULT order -- the comparison that
    declares no name_order at all, so it reads through `parse()`
    rather than a Policy-bearing Parser. One builder covering both
    branches rather than two hand copies, for the reason the three
    row-building copies in compare.py carry a comment about: a
    duplicate drifts the moment a field is added, and #484 added one.
    """
    if order is None:
        from nameparser import parse
        p = parse(name)
    else:
        from nameparser import Parser, Policy
        import nameparser as _np
        p = Parser(policy=Policy(name_order=getattr(_np, order))).parse(name)
    row = {f: (getattr(p, f, "") or "") for f in compare.V2_FIELDS}
    row["_ambiguities"] = sorted(
        {a.kind.name for a in getattr(p, "ambiguities", ())})
    row["_initials"] = p.initials() or ""
    return row


def test_order_bearing_entry_reaches_the_worker_and_compares_on_v2_alone(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Mutating the shape resolution to always leave e["order"] = None
    must not leave this suite green: a shape-4 entry must reach the
    worker with order == "FAMILY_FIRST" (not None), and a baseline row
    that carries no "facade" key at all -- exactly what an
    order-bearing worker row looks like -- must diff against nothing
    but the v2 fields, proving the branch that skips the facade
    comparison for these rows actually runs rather than crashing or
    silently defaulting to the facade path."""
    import contextlib
    import io
    import json as _json
    import sys
    name = "Ménil Christophe du"
    corpus = tmp_path / "corpus_x.jsonl"
    corpus.write_text(
        _json.dumps({"name": name, "shape": 4}, ensure_ascii=False) + "\n",
        encoding="utf-8")
    (tmp_path / "expected_since_2.0.0.toml").write_text("", encoding="utf-8")
    monkeypatch.setitem(compare._CORPUS_FLOORS, corpus.name, 1)
    monkeypatch.setitem(compare._CORPUS_TIERS, corpus.name, "contract")
    monkeypatch.setattr(compare, "HERE", tmp_path)
    v2_row = _tree_v2_row(name, "FAMILY_FIRST")
    sent: dict = {}

    def _fake(v: str, w: bool,
              entries: list[dict[str, object]]) -> tuple[dict, list[dict]]:
        sent["entries"] = list(entries)
        return ({"__version__": v,
                 "__file__": "/wheel/nameparser/__init__.py"},
                [{"v2": v2_row}])

    monkeypatch.setattr(compare, "_run_worker", _fake)
    monkeypatch.setattr(sys, "argv", ["compare.py", "--baseline", "2.0.0",
                                      "--corpus", str(corpus)])
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        code = compare.main()
    assert sent["entries"][0]["order"] == "FAMILY_FIRST"
    assert code == 0
    assert "UNEXPLAINED" not in buf.getvalue()


@pytest.mark.parametrize("tier,header,want_code", [
    ("contract", "UNEXPLAINED", 1),
    # radar tier: same order tag, but never fatal (#468) -- exit 0
    ("radar", "UNCLASSIFIED (radar)", 0),
])
def test_order_bearing_diff_row_tags_its_order_and_hides_v2_only(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
        tier: str, header: str, want_code: int) -> None:
    """Both the UNEXPLAINED and UNCLASSIFIED (radar) headers must say
    which order produced a diff -- a family-first regression and a
    default-order regression on the same name are otherwise
    indistinguishable in the report. Both draw the tag from the same
    _order_tag helper, so this parametrization pins BOTH call sites:
    a test covering one header alone says nothing about the other.
    And "[v2 surface only]"
    means "the facade was compared and agreed", which is false for an
    order-bearing row: its facade was never consulted, so the tag must
    not appear on either header."""
    import contextlib
    import io
    import json as _json
    import sys
    name = "Ménil Christophe du"
    corpus = tmp_path / "corpus_x.jsonl"
    corpus.write_text(
        _json.dumps({"name": name, "shape": 4}, ensure_ascii=False) + "\n",
        encoding="utf-8")
    (tmp_path / "expected_since_2.0.0.toml").write_text("", encoding="utf-8")
    monkeypatch.setitem(compare._CORPUS_FLOORS, corpus.name, 1)
    monkeypatch.setitem(compare._CORPUS_TIERS, corpus.name, tier)
    monkeypatch.setattr(compare, "HERE", tmp_path)
    v2_row = _tree_v2_row(name, "FAMILY_FIRST")
    v2_row["family"] = v2_row["family"] + "X"  # force a diff on `family`

    def _fake(v: str, w: bool,
              entries: list[dict[str, object]]) -> tuple[dict, list[dict]]:
        return ({"__version__": v,
                 "__file__": "/wheel/nameparser/__init__.py"},
                [{"v2": v2_row}])

    monkeypatch.setattr(compare, "_run_worker", _fake)
    monkeypatch.setattr(sys, "argv", ["compare.py", "--baseline", "2.0.0",
                                      "--corpus", str(corpus)])
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        code = compare.main()
    assert code == want_code
    out = buf.getvalue()
    assert f"{header} {name!r}" in out and "[order: FAMILY_FIRST]" in out
    assert "[v2 surface only]" not in out


def test_classified_order_bearing_diff_tags_its_order(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """The `## issue` block carries the order tag too. Without it, one
    string compared under two orders lists twice under the same issue
    with nothing telling the two lines apart -- and the release note
    written from that block would claim a default-order change the
    run never made."""
    import contextlib
    import io
    import json as _json
    import sys
    name = "Ménil Christophe du"
    corpus = tmp_path / "corpus_x.jsonl"
    corpus.write_text(
        _json.dumps({"name": name, "shape": 4}, ensure_ascii=False) + "\n",
        encoding="utf-8")
    (tmp_path / "expected_since_2.0.0.toml").write_text(
        '[[change]]\nissue = "claimed"\nname_regex = "Ménil"\n'
        'fields = ["family"]\n', encoding="utf-8")
    monkeypatch.setitem(compare._CORPUS_FLOORS, corpus.name, 1)
    monkeypatch.setitem(compare._CORPUS_TIERS, corpus.name, "contract")
    monkeypatch.setattr(compare, "HERE", tmp_path)
    v2_row = _tree_v2_row(name, "FAMILY_FIRST")
    v2_row["family"] = v2_row["family"] + "X"  # force a diff on `family`

    def _fake(v: str, w: bool,
              entries: list[dict[str, object]]) -> tuple[dict, list[dict]]:
        return ({"__version__": v,
                 "__file__": "/wheel/nameparser/__init__.py"},
                [{"v2": v2_row}])

    monkeypatch.setattr(compare, "_run_worker", _fake)
    monkeypatch.setattr(sys, "argv", ["compare.py", "--baseline", "2.0.0",
                                      "--corpus", str(corpus)])
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        code = compare.main()
    out = buf.getvalue()
    assert code == 0
    assert "## claimed (1)" in out
    assert f"  {name!r}   [order: FAMILY_FIRST]" in out


def _order_bearing_run(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
        ledger_body: str) -> tuple[int, str]:
    """One shape-4 (FAMILY_FIRST) entry whose v2 reading disagrees on
    `family`, run against `ledger_body`. The order-bearing sibling of
    _run_main, which can only build default-order comparisons."""
    import contextlib
    import io
    import json as _json
    import sys
    name = "Ménil Christophe du"
    corpus = tmp_path / "corpus_x.jsonl"
    corpus.write_text(
        _json.dumps({"name": name, "shape": 4}, ensure_ascii=False) + "\n",
        encoding="utf-8")
    (tmp_path / "expected_since_2.0.0.toml").write_text(
        ledger_body, encoding="utf-8")
    monkeypatch.setitem(compare._CORPUS_FLOORS, corpus.name, 1)
    monkeypatch.setitem(compare._CORPUS_TIERS, corpus.name, "contract")
    monkeypatch.setattr(compare, "HERE", tmp_path)
    v2_row = _tree_v2_row(name, "FAMILY_FIRST")
    v2_row["family"] = v2_row["family"] + "X"  # force a diff on `family`

    def _fake(v: str, w: bool,
              entries: list[dict[str, object]]) -> tuple[dict, list[dict]]:
        return ({"__version__": v,
                 "__file__": "/wheel/nameparser/__init__.py"},
                [{"v2": v2_row}])

    monkeypatch.setattr(compare, "_run_worker", _fake)
    monkeypatch.setattr(sys, "argv", ["compare.py", "--baseline", "2.0.0",
                                      "--corpus", str(corpus)])
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        code = compare.main()
    return code, buf.getvalue()


def _order_bearing_initials_run(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
        ledger_body: str) -> tuple[int, str]:
    """_order_bearing_run's `_initials` twin: the same shape-4 entry,
    with the CORE's initials moved and every role left alone.

    A second helper rather than a parameter on the first, because the
    two differ in what they are about: that one builds a role diff, and
    this one builds the diff main() only ever forms when no role moved
    at all."""
    import contextlib
    import io
    import json as _json
    import sys
    name = "Ménil Christophe du"
    corpus = tmp_path / "corpus_x.jsonl"
    corpus.write_text(
        _json.dumps({"name": name, "shape": 4}, ensure_ascii=False) + "\n",
        encoding="utf-8")
    (tmp_path / "expected_since_2.0.0.toml").write_text(
        ledger_body, encoding="utf-8")
    monkeypatch.setitem(compare._CORPUS_FLOORS, corpus.name, 1)
    monkeypatch.setitem(compare._CORPUS_TIERS, corpus.name, "contract")
    monkeypatch.setattr(compare, "HERE", tmp_path)
    v2_row = _tree_v2_row(name, "FAMILY_FIRST")
    v2_row["_initials"] = "M. X."  # the view moved; the roles did not

    def _fake(v: str, w: bool,
              entries: list[dict[str, object]]) -> tuple[dict, list[dict]]:
        return ({"__version__": v,
                 "__file__": "/wheel/nameparser/__init__.py"},
                [{"v2": v2_row}])

    monkeypatch.setattr(compare, "_run_worker", _fake)
    monkeypatch.setattr(sys, "argv", ["compare.py", "--baseline", "2.0.0",
                                      "--corpus", str(corpus)])
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        code = compare.main()
    return code, buf.getvalue()


def test_an_order_bearing_initials_only_diff_reports_without_a_surface_tag(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """An order-bearing entry never consults the facade -- main()
    leaves `new` empty for it -- so the facade pair is ('', ''),
    `facade_moved` is False, and the v2 `_initials` line falls to the
    ORDER-AWARE branch, which suppresses the tag. A "[v2 surface only]"
    here would be a lie: no facade reading was compared to be `only`
    different from.

    This is also the one path on which an `_initials` diff can reach
    the report at all under a declared order, which is why every
    `_initials` ledger rule carries orders = ["DEFAULT"]: such a diff
    is the CORE's, and no rule whose prose says "facade" may absorb
    it."""
    code, out = _order_bearing_initials_run(
        tmp_path, monkeypatch,
        '[[change]]\nissue = "unrelated"\nname_regex = "ZZZ"\n'
        'fields = ["family"]\n')
    assert code == 1
    assert "UNEXPLAINED 'Ménil Christophe du'   [order: FAMILY_FIRST]" in out
    # 'C. M.' and not 'M. C. d.': the tree side is read under
    # FAMILY_FIRST, where 'Ménil' is the family and 'du' its particle
    assert "_initials: 'M. X.' -> 'C. M.'" in out
    assert "[v2 surface" not in out


def test_an_order_blind_rule_absorbing_an_order_bearing_diff_is_reported(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """The leak this notice makes visible runs the OTHER way from the
    one `orders` was added for: a legacy rule carries no `orders`, so
    it claims a family-first diff its author never considered, and an
    order-only regression there reports as an intentional change. The
    notice is informational -- order-blind rules stay legal, and a
    ledger full of them is what every baseline before shape tags
    has -- so it must NOT move the exit code."""
    code, out = _order_bearing_run(
        tmp_path, monkeypatch,
        '[[change]]\nissue = "blind"\nname_regex = "Ménil"\n'
        'fields = ["family"]\n')
    assert code == 0
    assert "ORDER-BLIND" in out
    assert "'blind'" in out and "FAMILY_FIRST" in out


def test_one_string_tagged_with_two_shapes_is_two_comparisons(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """The dedup key is (name, order), not name. Regressing it to the
    name alone drops the second reading silently: the run compares one
    of the two orders, prints a corpus count one smaller, and exits 0
    -- and nothing above this pins it, because every other order test
    uses a single-shape corpus where the two keys agree."""
    import contextlib
    import io
    import json as _json
    import sys
    name = "Ménil Christophe du"
    corpus = tmp_path / "corpus_x.jsonl"
    corpus.write_text("".join(
        _json.dumps({"name": name, "shape": s}, ensure_ascii=False) + "\n"
        for s in (4, 5)), encoding="utf-8")
    (tmp_path / "expected_since_2.0.0.toml").write_text("", encoding="utf-8")
    monkeypatch.setitem(compare._CORPUS_FLOORS, corpus.name, 1)
    monkeypatch.setitem(compare._CORPUS_TIERS, corpus.name, "contract")
    monkeypatch.setattr(compare, "HERE", tmp_path)
    sent: dict = {}

    def _fake(v: str, w: bool,
              entries: list[dict[str, object]]) -> tuple[dict, list[dict]]:
        sent["entries"] = list(entries)
        return ({"__version__": v,
                 "__file__": "/wheel/nameparser/__init__.py"},
                [{"v2": _tree_v2_row(name, str(e["order"]))}
                 for e in entries])

    monkeypatch.setattr(compare, "_run_worker", _fake)
    monkeypatch.setattr(sys, "argv", ["compare.py", "--baseline", "2.0.0",
                                      "--corpus", str(corpus)])
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        code = compare.main()
    assert code == 0
    assert [e["name"] for e in sent["entries"]] == [name, name]
    assert [e["order"] for e in sent["entries"]] == [
        "FAMILY_FIRST", "FAMILY_FIRST_GIVEN_LAST"]
    assert "corpus: 2 names" in buf.getvalue()


def test_every_order_scoped_rule_declines_the_default_order() -> None:
    """Swept over the shipped ledgers rather than pinned per rule: a
    rule whose `orders` omits "DEFAULT" is saying its diffs come from
    declared orders alone, and the whole value of that statement is
    that the default-order reading of the same string stays somebody
    else's business -- unclaimed, and so still able to report
    UNEXPLAINED.

    Asked over the names the rule's own regex reaches, so it is the
    rule's real population and not a fixture's. Both directions, since
    a narrowing that declined everything would pass the first half."""
    checked = 0
    for ledger in _LEDGERS:
        for rule in _rules(ledger):
            orders = rule.get("orders")
            if not isinstance(orders, list) or "DEFAULT" in orders:
                continue
            fields = set(rule["fields"])
            examples = _claimed(rule["name_regex"])
            assert examples, (
                f"{ledger.name}: {rule['issue']!r} is order-scoped but its "
                f"regex reaches no corpus name, so this sweep would check "
                f"it vacuously")
            for example in examples:
                assert not compare._entry_matches(
                    rule, example, fields, None), (
                    f"{ledger.name}: {rule['issue']!r} scopes to {orders} "
                    f"yet claims the DEFAULT-order diff on {example!r}")
                assert any(compare._entry_matches(rule, example, fields, o)
                           for o in orders), (
                    f"{ledger.name}: {rule['issue']!r} claims nothing under "
                    f"any order it lists, on {example!r}")
            checked += 1
    assert checked >= 4, (
        f"only {checked} order-scoped rules were swept; the shipped 2.x "
        f"ledgers carry four each, so this pin is passing vacuously")


def test_the_worker_reads_an_order_bearing_line_as_the_tree_does() -> None:
    """The generated worker's order branch, RUN rather than compiled.
    test_worker_source_compiles proves it parses and
    test_run_worker_sends_the_name_and_resolved_order_on_the_wire
    proves what goes in; between them the branch that resolves an order
    constant, builds a Parser for it and emits a v2-only row was
    covered by nothing that executes it.

    exec'd in-process on purpose: the template's `import nameparser`
    then resolves to this checkout, so the row it emits is the tree's
    own reading and can be compared against the tree's own Parser.
    That is exactly the equality a real run depends on -- the worker
    and main()'s tree side must build the same row from the same parse
    -- and it is what makes a diff mean a behavior change rather than
    a protocol one."""
    import contextlib
    import io
    import json as _json
    import sys
    import nameparser
    name = "Ménil Christophe du"
    source = compare._worker_source(nameparser.__version__, want_v2=True)
    stdin = io.StringIO(_json.dumps(
        {"name": name, "order": "FAMILY_FIRST"}, ensure_ascii=False) + "\n")
    real_stdin, buf = sys.stdin, io.StringIO()
    try:
        sys.stdin = stdin
        with contextlib.redirect_stdout(buf):
            exec(compile(source, "baseline_worker.py", "exec"), {})
    finally:
        sys.stdin = real_stdin
    lines = buf.getvalue().splitlines()
    # the version tell is the first line, always -- a reader that
    # forgets it compares the tell against a parse and sees nothing
    tell, row = (_json.loads(line) for line in lines)
    assert tell["__version__"] == nameparser.__version__
    assert row == {"v2": _tree_v2_row(name, "FAMILY_FIRST")}
    # the facade is never consulted for an order-bearing entry, so the
    # key must be absent rather than empty: main() branches on it
    assert "facade" not in row


def test_the_worker_reads_a_default_order_line_as_the_tree_does() -> None:
    """The worker's FACADE row, RUN rather than compiled -- the third
    copy of the row-building code, pinned behaviorally.

    The other two copies (main()'s tree side, the template's _v2_row)
    are exercised by every main() test; this one crosses a process
    boundary in a real run and so is reachable only by executing the
    template. test_worker_source_emits_initials_on_both_surfaces
    pins its TEXT, which cannot see a row that builds the right keys
    from the wrong parse -- and #484 added a key to exactly this row.

    The name is chosen to tell the two SURFACES apart. `Ph. D., John`
    is the one corpus name whose facade and core initials differ today
    -- 'J. P D.' against 'J. P. D.', the phd-merge element grouped one
    way by HumanName and another by parse() -- so the facade assertion
    below can no longer pass by reading the core's value into the
    facade row. Under a name the two surfaces agree on (this test used
    `Ménil Christophe du`, 'M. C. d.' both ways) that swap is
    invisible.

    exec'd in-process for the same reason as its order-bearing
    sibling: `import nameparser` then resolves to this checkout, so
    the row is the tree's own reading and can be compared against the
    tree's own HumanName and parse()."""
    import contextlib
    import io
    import json as _json
    import sys
    import nameparser
    from nameparser import HumanName
    name = "Ph. D., John"
    source = compare._worker_source(nameparser.__version__, want_v2=True)
    stdin = io.StringIO(_json.dumps(
        {"name": name, "order": None}, ensure_ascii=False) + "\n")
    real_stdin, buf = sys.stdin, io.StringIO()
    try:
        sys.stdin = stdin
        with contextlib.redirect_stdout(buf):
            exec(compile(source, "baseline_worker.py", "exec"), {})
    finally:
        sys.stdin = real_stdin
    tell, row = (_json.loads(line) for line in buf.getvalue().splitlines())
    assert tell["__version__"] == nameparser.__version__
    assert row["facade"] == {
        **{k: v or "" for k, v in HumanName(name).as_dict().items()
           if k in compare.FIELDS},
        "_initials": HumanName(name).initials() or ""}
    assert row["v2"] == _tree_v2_row(name, None)


def test_dormancy_diagnoses_a_reverted_scoped_rule_as_reverted() -> None:
    """An order-scoped rule that stops explaining anything has had its
    behavior reverted, and must say so even when another rule explains
    the SAME NAME under the default order. Read order-blind, the scoped
    rule matches that default-order diff, sees the other rule win it
    and reports `shadowed` -- which sends someone to delete a rule that
    is not redundant, while the family-first behavior it described
    stays gone."""
    rules = [{"issue": "fix(default)", "name_regex": "^de la Cruz$",
              "fields": ["family"], "orders": ["DEFAULT"]},
             {"issue": "feat(scoped)", "name_regex": "^de la Cruz$",
              "fields": ["family"], "orders": ["FAMILY_FIRST"]}]
    # only the default-order comparison diffs: the family-first one the
    # scoped rule describes has been reverted
    report = compare.dormant_rules(
        rules, {"fix(default)"}, [("de la Cruz", {"family"}, None)])
    assert [d.issue for d in report.undeclared] == ["feat(scoped)"]
    assert report.undeclared[0].kind == "reverted"
    assert report.undeclared[0].detail == ""


def test_a_scoped_rule_absorbing_its_own_order_is_not_reported(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Scoping is the fix the notice asks for, so a scoped rule must
    print nothing -- otherwise the block is noise on every ledger that
    took the advice, and a reader stops reading it."""
    code, out = _order_bearing_run(
        tmp_path, monkeypatch,
        '[[change]]\nissue = "scoped"\nname_regex = "Ménil"\n'
        'fields = ["family"]\norders = ["FAMILY_FIRST"]\n')
    assert code == 0
    assert "## scoped (1)" in out
    assert "ORDER-BLIND" not in out


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


def test_a_rule_with_a_regex_and_no_fields_is_rejected() -> None:
    """#451's ban in mirror image (#456).

    A rule with no `fields` narrows by name and by nothing else, so on
    any name its regex reaches it claims every diff shape there is --
    measured, every one of the 256 shapes the seven roles,
    `_ambiguities` and the standalone `_initials` allow at a 2.x
    baseline. #452 made that worse than it looks by giving
    the shape a second job: over_declared_rules skips a rule with no
    `fields`, correctly, since one declaring no roles cannot
    over-declare them. So deleting the `fields` line is the response to
    an OVER-DECLARED failure that takes the least thought, and it both
    silences the check and makes the rule maximally permissive.

    Free to enforce, on the same terms as #451's: no rule in any
    shipped ledger has the shape, so the ban costs no migration.

    This assertion is an INVERSION. Its other half pinned the
    regex-only shape as LEGAL when #451 landed -- "the neighbouring
    shapes #451 did NOT retire" -- and #456 retired it. Inverted rather
    than deleted, so the change of status is visible to a `git log -L`
    on the assertion rather than vanishing with the test.
    """
    with pytest.raises(SystemExit, match="no 'fields'"):
        compare.validate_rules(
            [{"issue": "fix(x) a rule with no role narrowing",
              "name_regex": "Smith"}],
            "test_ledger.toml")
    # `dormant` buys no exemption here either, for the reason it buys
    # none from #451's ban: it is a claim about today's corpus, not a
    # bound on reach, and a regex-only rule sits at every diff shape
    # the moment one matching name arrives -- at which point its
    # dormancy claim is false too. Pinned because disabling the check
    # otherwise fails exactly one test (#457 review).
    with pytest.raises(SystemExit, match="no 'fields'"):
        compare.validate_rules(
            [{"issue": "fix(x) idle and unbounded",
              "name_regex": "Smith", "dormant": "a reason nobody faults"}],
            "test_ledger.toml")


def test_a_rule_carrying_both_keys_is_the_only_legal_shape() -> None:
    """What is left after the three bans, and there is exactly one.

    `validate_rules` rejects neither key (it would match every diff),
    `fields` without `name_regex` (#451, no name narrowing), and
    `name_regex` without `fields` (#456, no role narrowing). One
    shape survives all three, and this is it.
    """
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


def test_classify_scopes_a_rule_to_the_orders_it_declares() -> None:
    """`orders` is the third narrowing, and the one a name compared
    twice needs: the SAME string and the SAME moved roles mean
    different things under a declared family-first order (the #395
    fold, intended) and under the default order (that fold leaking
    where it must not). Order-blind, one rule claims both and the
    leak reports as an intentional change.

    Both directions are pinned. A rule with `orders` must decline the
    default-order diff -- comparison order None is never a member,
    since the members are constant NAMES -- and must still claim the
    diff under each order it lists. A rule without the key stays
    order-blind, which is what every rule written before shape-tagged
    entries existed relies on."""
    scoped = [{"issue": "family-first only", "name_regex": "Cruz",
               "fields": ["family"],
               "orders": ["FAMILY_FIRST", "FAMILY_FIRST_GIVEN_LAST"]}]
    assert compare.classify("de la Cruz", {"family"}, scoped) is None
    assert compare.classify("de la Cruz", {"family"}, scoped,
                            order="FAMILY_FIRST") == "family-first only"
    assert compare.classify(
        "de la Cruz", {"family"}, scoped,
        order="FAMILY_FIRST_GIVEN_LAST") == "family-first only"
    blind = [{"issue": "any order", "name_regex": "Cruz",
              "fields": ["family"]}]
    assert compare.classify("de la Cruz", {"family"}, blind) == "any order"
    assert compare.classify("de la Cruz", {"family"}, blind,
                            order="FAMILY_FIRST") == "any order"


def test_the_default_order_sentinel_scopes_a_rule_to_the_default_order(
        ) -> None:
    """"DEFAULT" is a sentinel and not an order constant: no shape
    declares it, because it names the absence of a declared order. It
    exists because TOML has no null inside an array, so a rule that
    explains only default-order diffs had no way to say so and had to
    stay order-blind -- which is the leak running the other way from
    the one `orders` was added for."""
    scoped = [{"issue": "default only", "name_regex": "Cruz",
               "fields": ["family"], "orders": ["DEFAULT"]}]
    assert compare.classify("de la Cruz", {"family"},
                            scoped) == "default only"
    assert compare.classify("de la Cruz", {"family"}, scoped,
                            order="FAMILY_FIRST") is None
    both = [{"issue": "default and one order", "name_regex": "Cruz",
             "fields": ["family"], "orders": ["DEFAULT", "FAMILY_FIRST"]}]
    assert compare.classify("de la Cruz", {"family"},
                            both) == "default and one order"
    assert compare.classify("de la Cruz", {"family"}, both,
                            order="FAMILY_FIRST") == "default and one order"
    assert compare.classify("de la Cruz", {"family"}, both,
                            order="FAMILY_FIRST_GIVEN_LAST") is None


@pytest.mark.parametrize("orders,message", [
    (["NO_SUCH_ORDER"], "shapes.py declares for no shape"),
    ([], "empty 'orders'"),
    ("FAMILY_FIRST", "not a list of strings"),
    ([1], "not a list of strings"),
])
def test_validate_rules_rejects_a_bad_orders_narrowing(
        orders: object, message: str) -> None:
    """Each way an `orders` can stop meaning what its author wrote.
    The two type failures are the dangerous direction -- _entry_matches
    ignores a non-list, so a mistyped key silently returns the rule to
    claiming every order, which is the scoping it was added to undo --
    and the other two can only ever match nothing, which is loud but
    reads as a dormant rule rather than as a typo."""
    with pytest.raises(SystemExit, match=message):
        compare.validate_rules(
            [{"issue": "fix(x) scoped", "name_regex": "Smith",
              "fields": ["given"], "orders": orders}],
            "test_ledger.toml")


def test_order_contests_reads_the_orders_narrowing_classify_reads() -> None:
    """`orders` is the third narrowing, so the contest predicate has to
    read it too: two rules scoped to DISJOINT orders can never claim
    the same comparison, whatever their `fields` and regexes say, so
    file order decides nothing between them and there is no hazard to
    justify.

    The first pair below is the demonstration. fix(b)'s `fields` are a
    strict subset of fix(a)'s and both regexes reach 'John Smith', so
    the fields-and-reach half of the predicate holds -- and classify()
    still routes each order to its own rule, because neither rule is
    reachable under the order the other declares. Reporting it would
    demand a written exemption for a contest that cannot occur, which
    is the detector-disagrees-with-the-predicate failure
    docs/design/AGENTS.md axis 2 is about.

    An order-blind rule keeps contesting everything, which is the
    second pair: omitting `orders` means claiming every order, so it
    overlaps whatever the other rule declares. That is the direction
    that must NOT be quietly narrowed away -- every rule in every
    shipped ledger is order-blind today, and a skip that swallowed
    those would empty the roster while looking like a fix.
    """
    names = ["John Smith"]
    disjoint = [
        {"issue": "fix(a) x", "name_regex": "Smith",
         "fields": ["given", "family"], "orders": ["DEFAULT"]},
        {"issue": "fix(b) y", "name_regex": "Smith",
         "fields": ["family"], "orders": ["FAMILY_FIRST"]}]
    assert compare.order_contests(disjoint, names) == []
    assert compare.classify("John Smith", {"family"}, disjoint) == "fix(a) x"
    assert compare.classify("John Smith", {"family"}, disjoint,
                            order="FAMILY_FIRST") == "fix(b) y"

    # ... and the same pair overlapping in one order IS a contest,
    # which keeps the skip above from passing for the wrong reason
    overlapping = [dict(disjoint[0]),
                   {**disjoint[1], "orders": ["DEFAULT", "FAMILY_FIRST"]}]
    assert [c.earlier for c in compare.order_contests(overlapping, names)] \
        == ["fix(a) x"]

    blind = [dict(disjoint[0]), {k: v for k, v in disjoint[1].items()
                                 if k != "orders"}]
    assert [(c.earlier, c.later, c.names)
            for c in compare.order_contests(blind, names)] \
        == [("fix(a) x", "fix(b) y", ("John Smith",))]


def test_validate_rules_takes_the_order_names_from_the_shape_inventory(
        ) -> None:
    """The legal set is BORROWED, not hand-copied: every order any
    shape declares is legal and nothing else is, so an order added to
    shapes.py is usable in a rule the same day, and one removed stops
    validating without anyone remembering a second list. An order no
    shape declares is an order no comparison runs under, so a rule
    naming it could only ever be dormant.

    "DEFAULT" is the one member shapes.py does not supply, and cannot:
    it names the absence of a declared order, which is not a shape."""
    assert compare._legal_orders() == {
        shape.order for shape in shapes.SHAPES.values()
        if shape.order is not None} | {"DEFAULT"}
    for order in compare._legal_orders():
        compare.validate_rules(
            [{"issue": "fix(x) scoped", "name_regex": "Smith",
              "fields": ["given"], "orders": [order]}],
            "test_ledger.toml")


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
    # all seven roles: the roles are the only names that ever co-occur
    # in one diff -- _ambiguities cannot appear below baseline 2.0 and
    # _initials only ever appears alone -- so listing all seven is
    # already the widest a rule can be, and it claims every role diff.
    # name_regex is along for the ride so this pins the roles check,
    # not the #451 one.
    ({"issue": "x", "name_regex": "Smith",
      "fields": ["title", "given", "middle", "family",
                 "suffix", "nickname", "maiden"]},
     "all seven roles"),
    # uncompilable: without this it raises mid-run, after the worker
    ({"issue": "x", "name_regex": "Smith("}, "invalid 'name_regex'"),
    ({"issue": "x", "name_regex": "Smith", "fields": []}, "empty 'fields'"),
    # a repeated name is a copy-paste slip the set-based subset test
    # would swallow; refused so it cannot masquerade as a narrowing
    ({"issue": "x", "name_regex": "Smith", "fields": ["family", "family"]},
     "repeats"),
    ({"issue": "x", "name_regex": "Smith",
      "fields": ["_initials", "_initials"]}, "repeats"),
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
    # #382's shape failures. The key is an array-of-tables, so every
    # other shape is a rule that reads as an exemption and declares
    # none: [] says nothing, a bare table is the single-bracket
    # [change.precedes_narrower] slip, and a list of strings is the
    # reason written where the table belongs.
    ({"issue": "x", "name_regex": "Smith", "fields": ["given"],
      "precedes_narrower": []}, "not a non-empty list of tables"),
    ({"issue": "x", "name_regex": "Smith", "fields": ["given"],
      "precedes_narrower": {"issue": "y", "why": "r"}},
     "not a non-empty list of tables"),
    ({"issue": "x", "name_regex": "Smith", "fields": ["given"],
      "precedes_narrower": ["y"]}, "not a non-empty list of tables"),
    # an entry naming no rule exempts nothing, and 'entry with' is
    # load-bearing in the match: a bare "no string 'issue'" would also
    # match the RULE-level message and pin nothing here
    ({"issue": "x", "name_regex": "Smith", "fields": ["given"],
      "precedes_narrower": [{"why": "r"}]}, "entry with no string 'issue'"),
    # the reason is the whole safeguard, absent as well as blank
    ({"issue": "x", "name_regex": "Smith", "fields": ["given"],
      "precedes_narrower": [{"issue": "y"}]}, "with no 'why'"),
    ({"issue": "x", "name_regex": "Smith", "fields": ["given"],
      "precedes_narrower": [{"issue": "y", "why": 3}]}, "with no 'why'"),
    # a rule cannot outrank itself; reported as itself rather than as
    # the backwards-pointing case, which would tell the reader the rule
    # sits earlier in the file than itself
    ({"issue": "x", "name_regex": "Smith", "fields": ["given"],
      "precedes_narrower": [{"issue": "x", "why": "r"}]},
     "precedence over ITSELF"),
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


def test_initials_is_a_legal_field_name_alone() -> None:
    """#484: the derived-view pseudo-field, legal by itself."""
    compare.validate_rules(
        [{"issue": "x", "name_regex": "Smith", "fields": ["_initials"]}],
        "ledger.toml")
    compare.validate_exclusions(
        [{"why": "x", "name_regex": "Smith", "examples": ["John Smith"],
          "fields": ["_initials"]}], "ledger.toml")


@pytest.mark.parametrize("fields", [
    ["_initials", "family"],
    ["family", "_initials"],
    ["_initials", "_ambiguities"],
])
def test_initials_mixed_with_another_field_is_rejected(
        fields: list[str]) -> None:
    """main() adds `_initials` to a diff only when nothing else moved,
    so a rule declaring it beside a role can never match on it: the
    half is dead, and dead rule text is the shape every other check in
    validate_rules exists to refuse."""
    with pytest.raises(SystemExit, match="silently dead"):
        compare.validate_rules(
            [{"issue": "x", "name_regex": "Smith", "fields": fields}],
            "ledger.toml")
    with pytest.raises(SystemExit, match="silently dead"):
        compare.validate_exclusions(
            [{"why": "x", "name_regex": "Smith", "examples": ["John Smith"],
              "fields": fields}], "ledger.toml")


def _rule(issue: str, **extra: object) -> dict[str, object]:
    """A minimal well-formed ledger rule, for the checks below."""
    return {"issue": issue, "name_regex": "x", "fields": ["given"], **extra}


def test_an_exemption_naming_an_unknown_rule_is_rejected() -> None:
    with pytest.raises(SystemExit, match="names no rule in this ledger"):
        compare.validate_rules(
            [_rule("fix(a) first", precedes_narrower=[
                {"issue": "fix(ghost) not in this file", "why": "because"}])],
            "test_ledger.toml")


def test_an_exemption_pointing_backwards_is_rejected() -> None:
    """An exemption names the rule it OUTRANKS, which sits later.

    Pointing at an earlier rule describes a pair where the declaring
    rule is already the loser, so it protects nothing -- and the
    likeliest way to write one is a copy-paste of the wrong issue
    string, which would otherwise sit in the file reading as a
    justification.
    """
    with pytest.raises(SystemExit, match="sits EARLIER"):
        compare.validate_rules(
            [_rule("fix(a) first"),
             _rule("fix(b) second", precedes_narrower=[
                 {"issue": "fix(a) first", "why": "because"}])],
            "test_ledger.toml")


def test_an_exemption_without_a_reason_is_rejected() -> None:
    """`dormant`'s precedent: the reason is the whole safeguard."""
    with pytest.raises(SystemExit, match="'why'"):
        compare.validate_rules(
            [_rule("fix(a) first", precedes_narrower=[
                {"issue": "fix(b) second", "why": "   "}]),
             _rule("fix(b) second")],
            "test_ledger.toml")


def test_a_rule_key_misplaced_into_an_exemption_is_rejected() -> None:
    """The trap the TOML shape carries.

    `precedes_narrower` is a nested array-of-tables, so once its block
    opens EVERY later bare `key = value` in the rule binds to the
    exemption instead of the rule. An author appending `orders` after
    an exemption silently deletes that rule's order narrowing -- and
    the unknown-key check on the rule cannot see it, because the key
    never lands in the rule dict at all. This is the same quiet
    widening #451 and #456 close, arriving through new syntax rather
    than through a misspelling.
    """
    with pytest.raises(SystemExit, match="belongs to the RULE"):
        compare.validate_rules(
            [_rule("fix(a) first", precedes_narrower=[
                {"issue": "fix(b) second", "why": "because",
                 "orders": ["FAMILY_FIRST"]}]),
             _rule("fix(b) second")],
            "test_ledger.toml")


def test_the_same_rule_exempted_twice_is_rejected() -> None:
    """Two reasons for one pair, and no way to tell which is stale.

    A row in the table above cannot carry this: a repeat only reaches
    the check once both entries name a rule that exists, which takes a
    second rule in the ledger.
    """
    with pytest.raises(SystemExit, match="more than once"):
        compare.validate_rules(
            [_rule("fix(a) first", precedes_narrower=[
                {"issue": "fix(b) second", "why": "a is the compound rule"},
                {"issue": "fix(b) second", "why": "b was reverted"}]),
             _rule("fix(b) second")],
            "test_ledger.toml")


def test_a_well_formed_exemption_is_accepted() -> None:
    """The positive control: the four refusals above must not be
    refusing every exemption for some unrelated reason."""
    compare.validate_rules(
        [_rule("fix(a) first", precedes_narrower=[
            {"issue": "fix(b) second", "why": "a is the compound rule"}]),
         _rule("fix(b) second")],
        "test_ledger.toml")


#: What _run_worker was asked for, so a test can prove main forwarded
#: the baseline and the corpus rather than defaults of its own.
_WORKER_CALL: dict = {}


def _run_main(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, ledger_body: str,
              baseline_facade: dict,
              extra: list[tuple[str, dict]] | None = None,
              baseline: str = "1.4.0",
              baseline_v2: dict | None = None,
              floor: int | None = 1,
              tier: str | None = "contract") -> tuple[int, str]:
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
    # Copies, not the caller's dicts: the `_initials` default below
    # writes into every row, and the fixtures are module-level
    # constants (_SAME_FACADE, _DIFFERS, _SAME_V2). Mutating them in
    # place would leak one test's baseline into the next.
    rows: list[dict] = [{"facade": dict(baseline_facade)}]
    if baseline_v2 is not None:
        rows[0]["v2"] = dict(baseline_v2)
    for _, facade in (extra or ()):
        rows.append({"facade": dict(facade)})
    # #484: the tree emits `_initials` on every row and compares it
    # whenever the roles agree. A fixture row that omitted the key
    # would read as an initials diff against the tree's own initials,
    # so an omitted key means "same as the tree"; a test that wants an
    # initials diff writes the key explicitly.
    #
    # Which makes a MISSPELLED key the dangerous one, and the reason
    # for the refusal below: `{**_SAME_FACADE, "_initals": "J. X."}`
    # is a row main() never reads the stray key from, so the real
    # `_initials` defaults to the tree's own answer, the surfaces
    # agree, and the test passes while pinning nothing. Refuse the row
    # instead. Checked BEFORE the setdefault so the message can name
    # the key the caller wrote rather than the one the helper added.
    _facade_keys = set(compare.FIELDS) | {"_initials"}
    _v2_keys = set(compare.V2_FIELDS) | {"_ambiguities", "_initials"}
    for n, row in zip(names, rows):
        for which, legal in (("facade", _facade_keys), ("v2", _v2_keys)):
            if which not in row:
                continue
            stray = sorted(set(row[which]) - legal)
            if stray:
                raise AssertionError(
                    f"fixture row for {n!r} ({which}) carries "
                    f"{stray}, which main() never reads. The row would "
                    f"silently agree with the tree on every field it "
                    f"does read -- a misspelled '_initials' defaults to "
                    f"the tree's own initials -- so the test would pass "
                    f"having pinned nothing. Expected keys: "
                    f"{sorted(legal)}")
    from nameparser import HumanName as _HN
    for n, row in zip(names, rows):
        row["facade"].setdefault("_initials", _HN(n).initials() or "")
        if "v2" in row:
            from nameparser import parse as _parse
            row["v2"].setdefault("_initials", _parse(n).initials() or "")
    _WORKER_CALL.clear()

    def _fake(v: str, w: bool, n: list[dict]) -> tuple[dict, list[dict]]:
        _WORKER_CALL.update(version=v, want_v2=w, names=[e["name"] for e in n])
        return ({"__version__": v,
                 "__file__": "/wheel/nameparser/__init__.py"}, rows)

    # The fixture corpus needs a floor like any other. `floor=None`
    # leaves it unregistered, for the test that pins what happens when
    # a corpus arrives without one.
    if floor is not None:
        monkeypatch.setitem(compare._CORPUS_FLOORS, corpus.name, floor)
    # The fixture corpus needs a tier like any other. `tier=None`
    # leaves it unregistered, for the test that pins the fail-closed
    # roster.
    if tier is not None:
        monkeypatch.setitem(compare._CORPUS_TIERS, corpus.name, tier)
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
        '[[change]]\nissue = "unrelated"\nname_regex = "ZZZ"\nfields = ["family"]\n', _DIFFERS)
    assert code == 1
    assert "UNEXPLAINED 'John Smith'" in out


def test_main_reports_the_unexplained_field_under_its_role_name(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """The block exists to be copy-pasted into a ledger rule, so the
    label it prints must be the label a rule needs. The facade calls
    this role `last`; a rule saying `last` never matches."""
    _, out = _run_main(
        tmp_path, monkeypatch,
        '[[change]]\nissue = "unrelated"\nname_regex = "ZZZ"\nfields = ["family"]\n', _DIFFERS)
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


def test_radar_diff_with_no_rule_exits_0_and_is_reported(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """The tier split's entire point (#468): a harvested name's diff
    is shown, not owed a ledger rule. The heading is pinned because it
    is what a release reader greps for.

    An empty ledger, not the usual 'unrelated'/ZZZ decoy rule: that
    decoy matches no diffing name in a single-name corpus and so is
    itself EXPLAINED NOTHING (dormant_rules' "reverted" case) --
    orthogonal to the tier split and would fail this run for a reason
    that has nothing to do with what it is pinning."""
    code, out = _run_main(tmp_path, monkeypatch, "", _DIFFERS, tier="radar")
    assert code == 0
    assert "UNCLASSIFIED (radar) 'John Smith'" in out
    assert "family:" in out
    assert "UNEXPLAINED" not in out


def test_radar_initials_only_diff_prints_its_pseudo_field_line(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """The radar block forwards `initials_only` too. Every other
    `_initials` print test goes through the UNEXPLAINED block, and the
    two blocks call _print_field_diffs from separate call sites -- so
    passing `initials_only=False` at the radar one leaves a
    `UNCLASSIFIED (radar)` header with NO field lines under it, which
    is a report nobody can act on and which no other test here sees.

    An empty ledger for the same reason as the sibling above: a
    ZZZ decoy rule would be dormant in a one-name corpus and exit 1
    for a reason that has nothing to do with the pseudo-field."""
    code, out = _run_main(
        tmp_path, monkeypatch, "", _INITIALS_MOVED, tier="radar")
    assert code == 0
    assert "UNCLASSIFIED (radar) 'John Smith'" in out
    assert "_initials: 'J. X.' -> 'J. S.'" in out


def test_radar_diff_matching_a_rule_still_classifies(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Radar names keep feeding the release-note grouping, and a rule
    explaining only radar diffs is NOT dormant -- exit 0 with no
    EXPLAINED NOTHING block is the pin for both at once."""
    code, out = _run_main(
        tmp_path, monkeypatch,
        '[[change]]\nissue = "claimed"\nname_regex = "Smith"\nfields = ["family"]\n',
        _DIFFERS, tier="radar")
    assert code == 0
    assert "## claimed (1)" in out
    assert "EXPLAINED NOTHING" not in out


def test_contract_diff_still_fails_under_the_tier_roster(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """The split must not loosen the tier that keeps the old promise."""
    code, out = _run_main(
        tmp_path, monkeypatch,
        '[[change]]\nissue = "unrelated"\nname_regex = "ZZZ"\nfields = ["family"]\n',
        _DIFFERS, tier="contract")
    assert code == 1
    assert "UNEXPLAINED 'John Smith'" in out


def test_radar_name_refused_by_an_exclusion_still_fails(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """A [[never]] entry is chosen -- someone wrote its `why` and its
    `examples` -- so it belongs to the contract even when the name it
    refuses sits in a radar file. classify() returns None for both
    'no rule matched' and 'an exclusion refused this', and only the
    first is the tier split's business: an excluded shape must stay
    UNEXPLAINED and exit 1 on every tier, matching what
    validate_exclusions' docstring and every 1.4.0 `why` promise."""
    code, out = _run_main(
        tmp_path, monkeypatch,
        '[[never]]\nwhy = "test exclusion"\nname_regex = "Smith"\n'
        'examples = ["John Smith"]\n',
        _DIFFERS, tier="radar")
    assert code == 1
    assert "UNEXPLAINED 'John Smith'" in out
    assert "UNCLASSIFIED" not in out


def test_a_corpus_without_a_tier_is_a_hard_error(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Fail-closed like _CORPUS_FLOORS: a new corpus must choose."""
    with pytest.raises(SystemExit, match="_CORPUS_TIERS"):
        _run_main(tmp_path, monkeypatch, "", _DIFFERS, tier=None)


def test_object_corpus_lines_are_read_and_labels_printed(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """A corpus line may be {"name": ..., "tests": [...]} -- the
    label-bearing format corpus.jsonl ships in (both shapes are legal
    on any corpus file). The name is compared and the labels ride into
    the radar report, which is what they are for."""
    import json as _json
    corpus = tmp_path / "corpus_x.jsonl"
    corpus.write_text(_json.dumps(
        {"name": "John Smith", "tests": ["test_two_word_name"]}) + "\n",
        encoding="utf-8")
    (tmp_path / "expected_since_1.4.0.toml").write_text("", encoding="utf-8")
    monkeypatch.setitem(compare._CORPUS_FLOORS, corpus.name, 1)
    monkeypatch.setitem(compare._CORPUS_TIERS, corpus.name, "radar")
    monkeypatch.setattr(compare, "HERE", tmp_path)
    monkeypatch.setattr(
        compare, "_run_worker",
        lambda v, w, entries: ({"__version__": v,
                                "__file__": "/wheel/nameparser/__init__.py"},
                               [{"facade": _DIFFERS}]))
    import contextlib
    import io
    import sys
    monkeypatch.setattr(sys, "argv", ["compare.py", "--baseline", "1.4.0",
                                      "--corpus", str(corpus)])
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        code = compare.main()
    assert code == 0
    assert "test_two_word_name" in buf.getvalue()


def test_a_malformed_tests_label_is_a_hard_error(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Caught at load time, not report time: a 'tests' label is read
    only when printing the radar block, after the multi-minute worker
    pass, so a bad one left unchecked would crash there instead --
    the failure mode validate_rules' compile-at-startup paragraph
    exists to avoid."""
    import json as _json
    corpus = tmp_path / "corpus_x.jsonl"
    corpus.write_text(_json.dumps(
        {"name": "John Smith", "tests": "not_a_list"}) + "\n",
        encoding="utf-8")
    with pytest.raises(SystemExit, match="'tests' must be a list"):
        compare._load_entries(corpus)


def test_a_misspelled_corpus_key_is_a_hard_error(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """'shpae' is not 'shape', and an ignored key is a narrowing that
    silently did not happen: the line compares under the default order
    while its author believes they declared a family-first one. The
    message names the FILE, like every other loader error here, because
    five corpora are read in one run."""
    import json as _json
    corpus = tmp_path / "corpus_x.jsonl"
    corpus.write_text(_json.dumps(
        {"name": "John Smith", "shpae": 4}) + "\n", encoding="utf-8")
    with pytest.raises(SystemExit, match=r"corpus_x\.jsonl.*'shpae'"):
        compare._load_entries(corpus)


def test_a_corpus_line_writing_a_computed_key_is_a_hard_error(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """'order' is the key the WIRE protocol documents, so it is the one
    a corpus author is likeliest to write by hand -- and main() computes
    it from `shape` and overwrites whatever the line said. Rejected
    rather than obeyed: honoring it would let a corpus line name an
    order no shape declares, which is the check `orders` rules get."""
    import json as _json
    corpus = tmp_path / "corpus_x.jsonl"
    corpus.write_text(_json.dumps(
        {"name": "John Smith", "order": "FAMILY_FIRST"}) + "\n",
        encoding="utf-8")
    with pytest.raises(SystemExit, match=r"corpus_x\.jsonl.*'order'"):
        compare._load_entries(corpus)


@pytest.mark.parametrize("shape", [True, "4"])
def test_a_malformed_shape_id_is_a_hard_error(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
        shape: object) -> None:
    """`true` is the dangerous one: bool is an int subclass and
    hash(True) == hash(1), so an unchecked {"shape": true} resolves
    against shapes.py's entry 1 and the line is compared under THAT
    shape's order -- a wrong comparison that reports as a passing one.
    The string spelling is the honest typo beside it."""
    import json as _json
    corpus = tmp_path / "corpus_x.jsonl"
    corpus.write_text(_json.dumps(
        {"name": "John Smith", "shape": shape}) + "\n", encoding="utf-8")
    with pytest.raises(SystemExit, match="'shape' must be an int"):
        compare._load_entries(corpus)


def test_a_corpus_line_that_is_neither_shape_is_a_hard_error(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """A bare number, or an object with no string 'name', carries no
    name to compare. Skipping it would shrink the comparison by one
    name and print a summary that reads exactly like a full run."""
    import json as _json
    corpus = tmp_path / "corpus_x.jsonl"
    corpus.write_text(_json.dumps({"nmae": "John Smith"}) + "\n",
                      encoding="utf-8")
    with pytest.raises(SystemExit, match="neither a JSON string"):
        compare._load_entries(corpus)


def test_a_shape_id_shapes_py_does_not_define_is_a_hard_error(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """_load_entries checks the TYPE; only main() has shapes.py loaded,
    so resolvability is its check. Unchecked, the entry would compare
    under whatever `.get` returned rather than the order it declared."""
    import json as _json
    import sys
    corpus = tmp_path / "corpus_x.jsonl"
    corpus.write_text(_json.dumps(
        {"name": "John Smith", "shape": 9999}) + "\n", encoding="utf-8")
    (tmp_path / "expected_since_2.0.0.toml").write_text("", encoding="utf-8")
    monkeypatch.setitem(compare._CORPUS_FLOORS, corpus.name, 1)
    monkeypatch.setitem(compare._CORPUS_TIERS, corpus.name, "contract")
    monkeypatch.setattr(compare, "HERE", tmp_path)
    monkeypatch.setattr(sys, "argv", ["compare.py", "--baseline", "2.0.0",
                                      "--corpus", str(corpus)])
    with pytest.raises(SystemExit, match="shapes.py does not define"):
        compare.main()


def test_cross_tier_dedup_keeps_the_contract_reading(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """'John Smith' really does sit in both corpus.jsonl (radar) and
    corpus_rules.jsonl (contract). Nothing above the dedup itself
    would catch a regression here, so this is the one guard that pins
    contract-first loading rather than just describing it: an
    unmatched diff on the shared name must still be UNEXPLAINED and
    fail the run, whichever way the sort key is written."""
    import json as _json
    radar_file = tmp_path / "corpus.jsonl"
    contract_file = tmp_path / "corpus_rules.jsonl"
    radar_file.write_text(_json.dumps("John Smith") + "\n", encoding="utf-8")
    contract_file.write_text(
        _json.dumps("John Smith") + "\n", encoding="utf-8")
    (tmp_path / "expected_since_1.4.0.toml").write_text("", encoding="utf-8")
    monkeypatch.setitem(compare._CORPUS_FLOORS, radar_file.name, 1)
    monkeypatch.setitem(compare._CORPUS_FLOORS, contract_file.name, 1)
    monkeypatch.setattr(compare, "HERE", tmp_path)
    monkeypatch.setattr(
        compare, "_run_worker",
        lambda v, w, entries: ({"__version__": v,
                                "__file__": "/wheel/nameparser/__init__.py"},
                               [{"facade": _DIFFERS}]))
    import contextlib
    import io
    import sys
    monkeypatch.setattr(sys, "argv", ["compare.py", "--baseline", "1.4.0",
                                      "--corpus", str(radar_file),
                                      "--corpus", str(contract_file)])
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        code = compare.main()
    out = buf.getvalue()
    assert code == 1
    assert "UNEXPLAINED 'John Smith'" in out


def test_main_validates_the_ledger_before_running_anything(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """validate_rules has its own tests; this pins that main CALLS it.
    Deleting the call leaves those tests passing while a match-anything
    rule shadows the ledger."""
    with pytest.raises(SystemExit, match="matches every one of"):
        _run_main(tmp_path, monkeypatch,
                  '[[change]]\nissue = "wide"\nname_regex = ""\nfields = ["family"]\n', _DIFFERS)


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
            '[[change]]\nissue = "specific"\nname_regex = "Smith"\nfields = ["family"]\n',
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
                  '[[change]]\nissue = "x"\nname_regex = "ZZZ"\nfields = ["family"]\n', _DIFFERS)


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
    compare._run_worker("1.4.0", False, [{"name": "John Smith"}])
    env = _FakePopen.last["env"]
    assert "PYTHONPATH" not in env and "PYTHONHOME" not in env


def test_run_worker_aborts_on_a_nonzero_exit(
        monkeypatch: pytest.MonkeyPatch) -> None:
    _fake_popen(monkeypatch, "", rc=3)
    with pytest.raises(SystemExit, match="exited 3"):
        compare._run_worker("1.4.0", False, [{"name": "John Smith"}])


def test_run_worker_aborts_on_empty_output(
        monkeypatch: pytest.MonkeyPatch) -> None:
    _fake_popen(monkeypatch, "")
    with pytest.raises(SystemExit, match="not even a version tell"):
        compare._run_worker("1.4.0", False, [{"name": "John Smith"}])


def test_run_worker_aborts_when_fewer_results_than_names(
        monkeypatch: pytest.MonkeyPatch) -> None:
    """The guard behind main's zip(), which truncates silently. This is
    the comparing-fewer-names-than-you-think failure."""
    _fake_popen(monkeypatch, f"{_TELL}\n{_ROW}\n")
    with pytest.raises(SystemExit, match="1 results for 2 corpus entries"):
        compare._run_worker("1.4.0", False,
                            [{"name": "John Smith"}, {"name": "Jane Doe"}])


def test_run_worker_checks_the_tell_before_returning_results(
        monkeypatch: pytest.MonkeyPatch) -> None:
    wrong = ('{"__version__": "9.9.9", '
             '"__file__": "/wheel/nameparser/__init__.py"}')
    _fake_popen(monkeypatch, f"{wrong}\n{_ROW}\n")
    with pytest.raises(SystemExit, match="not the requested"):
        compare._run_worker("1.4.0", False, [{"name": "John Smith"}])


def test_run_worker_sends_the_name_and_resolved_order_on_the_wire(
        monkeypatch: pytest.MonkeyPatch) -> None:
    """The wire format is the whole contract between compare.py and the
    generated worker; nothing else pins it, so a resolution bug -- e.g.
    forgetting to set e["order"] before calling this -- would leave
    every other test in this file green while the worker silently
    received the wrong order for every name. _FakePopen.communicate
    already records the payload it was given; this reads it back."""
    _fake_popen(monkeypatch, f"{_TELL}\n{_ROW}\n{_ROW}\n")
    compare._run_worker(
        "1.4.0", False,
        [{"name": "John Smith", "order": None},
         {"name": "Ménil Christophe du", "order": "FAMILY_FIRST"}])
    lines = _FakePopen.last["stdin"].splitlines()
    assert lines[0] == '{"name": "John Smith", "order": null}'
    assert lines[1] == \
        '{"name": "Ménil Christophe du", "order": "FAMILY_FIRST"}'


@pytest.mark.parametrize("want_v2", [True, False])
def test_worker_source_compiles(want_v2: bool) -> None:
    """A syntax error in the rendered template currently surfaces only
    as 'worker exited 1' after a multi-minute uv install; this catches
    it at test time instead, for both renderings (WANT_V2 gates a
    def-inside-if that is easy to misindent)."""
    compile(compare._worker_source("2.2.0", want_v2=want_v2),
            "<worker>", "exec")


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

#: 'John Smith' with every role identical and only the facade's
#: initials moved: the render-layer drift #484 exists to see.
_INITIALS_MOVED = {**_SAME_FACADE, "_initials": "J. X."}


def test_main_reports_an_initials_only_diff_under_the_pseudo_field(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """#484: a name whose seven roles agree on both surfaces and whose
    initials do not is a diff, reported under `_initials` so the block
    can be pasted into a rule."""
    code, out = _run_main(
        tmp_path, monkeypatch,
        '[[change]]\nissue = "unrelated"\nname_regex = "ZZZ"\n'
        'fields = ["family"]\n', _INITIALS_MOVED)
    assert code == 1
    assert "UNEXPLAINED 'John Smith'" in out
    assert "_initials: 'J. X.' -> 'J. S.'" in out


def test_main_classifies_an_initials_only_diff_by_an_initials_rule(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    code, out = _run_main(
        tmp_path, monkeypatch,
        '[[change]]\nissue = "render-drift"\nname_regex = "Smith"\n'
        'fields = ["_initials"]\n', _INITIALS_MOVED)
    assert code == 0
    assert "## render-drift (1)" in out


def test_main_drops_initials_from_a_diff_where_a_role_moved(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """The roles-identical guard, pinned as the exact condition. The
    rule below declares `family` only; if `_initials` entered the diff
    beside the moved role, the subset test would decline it and the
    run would exit 1. Delete `not diff and` from the guard and this
    is the test that fails."""
    code, out = _run_main(
        tmp_path, monkeypatch,
        '[[change]]\nissue = "role-only"\nname_regex = "Smith"\n'
        'fields = ["family"]\n', {**_DIFFERS, "_initials": "J. X."})
    assert code == 0
    assert "## role-only (1)" in out
    assert "_initials" not in out


def test_main_does_not_print_initials_beside_a_moved_role(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """The print half of the guard. An UNEXPLAINED block exists to be
    pasted into a rule, and a rule listing `_initials` beside a role
    is refused by validate_rules -- so the block must never show the
    pair. Pass `initials_only=True` unconditionally (or delete the
    `if initials_only:`) in _print_field_diffs and this fails while
    the classification test above still passes."""
    code, out = _run_main(
        tmp_path, monkeypatch,
        '[[change]]\nissue = "unrelated"\nname_regex = "ZZZ"\n'
        'fields = ["family"]\n', {**_DIFFERS, "_initials": "J. X."})
    assert code == 1
    assert "family: 'SMYTHE' -> 'Smith'" in out
    assert "_initials" not in out


def test_main_reports_a_v2_only_initials_diff_with_the_surface_tag(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """The v2 half of the pseudo-field: the facade agrees and the core
    view moved, which is the shape #408 had for a whole minor."""
    code, out = _run_main(
        tmp_path, monkeypatch,
        '[[change]]\nissue = "unrelated"\nname_regex = "ZZZ"\n'
        'fields = ["family"]\n',
        _SAME_FACADE, baseline="2.0.0",
        baseline_v2={**_SAME_V2, "_initials": "J. X."})
    assert code == 1
    assert "_initials: 'J. X.' -> 'J. S.'   [v2 surface only]" in out


def test_main_prints_both_initials_lines_when_the_surfaces_moved_differently(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """The facade's and the core's initials() are independent
    implementations, so unlike a role they can move to different
    strings; a block that showed only the facade's movement would
    have a rule written for it in the belief the core agreed."""
    code, out = _run_main(
        tmp_path, monkeypatch,
        '[[change]]\nissue = "unrelated"\nname_regex = "ZZZ"\n'
        'fields = ["family"]\n',
        {**_SAME_FACADE, "_initials": "J. X."}, baseline="2.0.0",
        baseline_v2={**_SAME_V2, "_initials": "J. Y."})
    assert code == 1
    assert "_initials: 'J. X.' -> 'J. S.'" in out
    assert "_initials: 'J. Y.' -> 'J. S.'   [v2 surface]" in out
    assert out.count("_initials:") == 2


def test_main_prints_one_initials_line_when_both_surfaces_moved_alike(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """The print-once convention, kept for the case it was written
    for: two surfaces moving to the SAME pair are one movement and one
    rule, so the facade line stands for both and carries no surface
    tag.

    The mutant this kills is replacing the WHOLE
    `(not facade_moved or v2_pair != facade_pair)` guard with a bare
    `if v2_moved:` -- then the v2 line prints here too, while the
    sibling above still sees its two lines and passes. Deleting only
    the pair comparison is the SIBLING's mutant, not this one: it
    leaves `v2_moved and not facade_moved`, which is False here, so
    this case still prints once and this test cannot see it."""
    code, out = _run_main(
        tmp_path, monkeypatch,
        '[[change]]\nissue = "unrelated"\nname_regex = "ZZZ"\n'
        'fields = ["family"]\n',
        {**_SAME_FACADE, "_initials": "J. X."}, baseline="2.0.0",
        baseline_v2={**_SAME_V2, "_initials": "J. X."})
    assert code == 1
    assert "_initials: 'J. X.' -> 'J. S.'" in out
    assert out.count("_initials:") == 1
    assert "[v2 surface" not in out


def test_main_keeps_initials_out_of_a_diff_a_V2_role_moved(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """The v2 half of the roles-identical guard. Its facade half is
    pinned above (test_main_drops_initials_from_a_diff_where_a_role_
    moved); this one moves the role on the CORE surface only, where the
    guard reads a different dict. The rule declares `family` alone, so
    an `_initials` that leaked into the diff beside it would fail the
    subset test and exit 1."""
    code, out = _run_main(
        tmp_path, monkeypatch,
        '[[change]]\nissue = "role-only"\nname_regex = "Smith"\n'
        'fields = ["family"]\n',
        _SAME_FACADE, baseline="2.0.0",
        baseline_v2={**_SAME_V2, "family": "SMYTHE", "_initials": "J. X."})
    assert code == 0
    assert "## role-only (1)" in out
    assert "_initials" not in out


def test_main_prints_one_initials_line_when_only_the_facade_moved(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """The facade moved and the core, compared, AGREED -- the reading
    the docstring of _print_field_diffs warns a bare facade line does
    NOT license, and the case that makes the warning necessary. Both
    surfaces were consulted here; the v2 line is suppressed because
    the core did not move, not because it was never asked.

    Distinct from test_main_reports_an_initials_only_diff_under_the_
    pseudo_field, which runs at 1.4.0 where there is no core surface
    to agree."""
    code, out = _run_main(
        tmp_path, monkeypatch,
        '[[change]]\nissue = "unrelated"\nname_regex = "ZZZ"\n'
        'fields = ["family"]\n',
        {**_SAME_FACADE, "_initials": "J. X."}, baseline="2.0.0",
        baseline_v2=dict(_SAME_V2))
    assert code == 1
    assert "_initials: 'J. X.' -> 'J. S.'" in out
    assert out.count("_initials:") == 1
    assert "[v2 surface" not in out


def test_run_main_refuses_a_fixture_row_with_an_unknown_key(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """The fixture's own guard, and the reason it exists: main() reads
    `_initials` off the row and the helper defaults a MISSING one to
    the tree's own answer, so a misspelled key is not a loud failure
    but a silent agreement -- the test passes having compared the tree
    against itself. Refuse the row instead of letting it pass."""
    with pytest.raises(AssertionError, match="_initals"):
        _run_main(
            tmp_path, monkeypatch,
            '[[change]]\nissue = "unrelated"\nname_regex = "ZZZ"\n'
            'fields = ["family"]\n',
            {**_SAME_FACADE, "_initals": "J. X."})


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
        # `_ambiguities`, not `family`: this test's diff IS the
        # ambiguity-only one, and a `family` declaration refuses that
        # shape -- which left the rule inert even with name narrowing
        # disabled, costing this test the mutation it was written to
        # catch (#457 review). Declare the role the diff moves.
        '[[change]]\nissue = "unrelated"\nname_regex = "ZZZ"\n'
        'fields = ["_ambiguities"]\n',
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
        '[[change]]\nissue = "unrelated"\nname_regex = "ZZZ"\nfields = ["family"]\n',
        {**_SAME_FACADE, "last": "SMYTHE"}, baseline="2.0.0",
        baseline_v2={**_SAME_V2, "family": "SMYTHE"})
    assert out.count("family:") == 1


def test_main_forwards_the_baseline_and_corpus_to_the_worker(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Otherwise main could read the 2.0 ledger while comparing against
    1.4, or compare a truncated corpus, and every other test would pass."""
    _run_main(tmp_path, monkeypatch,
              '[[change]]\nissue = "x"\nname_regex = "ZZZ"\nfields = ["family"]\n',
              _SAME_FACADE, baseline="2.0.0", baseline_v2=_SAME_V2)
    assert _WORKER_CALL == {"version": "2.0.0", "want_v2": True,
                            "names": ["John Smith"]}


def test_main_asks_for_the_facade_alone_below_2_0(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _run_main(tmp_path, monkeypatch,
              '[[change]]\nissue = "x"\nname_regex = "ZZZ"\nfields = ["family"]\n', _SAME_FACADE)
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


def test_every_corpus_with_a_floor_also_has_a_tier() -> None:
    """The two rosters are meant to name the same files. A corpus in
    one but not the other reopens the vanished-file hole the floors
    were added to close: main() only checks _CORPUS_FLOORS' keys
    against the files on disk (see the 'missing' check above the
    loading loop), so a file present in _CORPUS_TIERS alone, or in
    _CORPUS_FLOORS alone, would not be caught there."""
    assert set(compare._CORPUS_TIERS) == set(compare._CORPUS_FLOORS)


def test_main_aborts_on_a_truncated_corpus(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """A corpus below its floor must stop the run, not shrink it."""
    with pytest.raises(SystemExit, match="below its floor"):
        _run_main(tmp_path, monkeypatch,
                  '[[change]]\nissue = "x"\nname_regex = "ZZZ"\nfields = ["family"]\n',
                  _SAME_FACADE, floor=50)


def test_main_aborts_on_a_corpus_with_no_floor(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Adding a corpus without a floor must be a decision, not a
    silent default -- the same force-a-decision shape the Script
    tables use."""
    with pytest.raises(SystemExit, match="no entry in _CORPUS_FLOORS"):
        _run_main(tmp_path, monkeypatch,
                  '[[change]]\nissue = "x"\nname_regex = "ZZZ"\nfields = ["family"]\n',
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
    ({"why": "x", "name_regex": "a", "examples": ["a"],
      "fields": ["_initials", "_initials"]}, "repeats"),
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
        rules, {"fix(a)"}, [("John Smith", {"given"}, None)])
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
        rules, {"fix(broad)"}, [("John Smith", {"given"}, None)])
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
        rules, set(), [("John Smith", {"given"}, None)], never)
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
        rules, {"fix(a)"}, [("John Smith", {"given"}, None)])
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
        [("Alpha One", {"given"}, None), ("Zeta One", {"given"}, None),
         ("Zeta Two", {"given"}, None), ("Zeta Three", {"given"}, None)])
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
        rules, {"specific"}, [("John Smith", {"given"}, None)])
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
