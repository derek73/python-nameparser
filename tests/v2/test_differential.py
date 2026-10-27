"""Unit tests for compare.py, the released-wheel comparison.

`tools/` is outside `testpaths`, and adding it would run
`--doctest-modules` over the corpus builders, so `compare.py` is
imported by path through `_differential_fixtures.load_tool`.

Nothing here spawns `uv` or the network. What is tested is what
produces FALSE CONFIDENCE when it silently misbehaves: a version tell
believed when the wrong library answered, a tree side that is not the
checkout, a worker that reads a name differently from the tree, and a
comparison that cannot report a difference at all.
"""
import contextlib
import io
import json
import sys
from collections.abc import Callable
from pathlib import Path
from typing import Any

import pytest

from ._differential_fixtures import _TOOLS, load_tool

compare = load_tool("compare")
shapes = load_tool("shapes")
snapshot = load_tool("snapshot")


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


@pytest.mark.parametrize("want_v2", [True, False])
def test_worker_source_compiles(want_v2: bool) -> None:
    """A syntax error in the rendered template surfaces only as the
    opaque 'worker exited 1', and by then the temp dir holding the
    rendered source is gone; this catches it at test time, for both
    renderings (WANT_V2 gates a def-inside-if that is easy to
    misindent)."""
    compile(compare._worker_source("2.2.0", want_v2=want_v2),
            "<worker>", "exec")


def test_every_shape_orders_resolve_and_bound_sanely() -> None:
    """An `order` is a public constant name that Policy accepts as a
    name_order -- hasattr alone would admit any real attribute, failing
    only inside the worker -- and a shape with an order cannot claim a
    pre-2.0 baseline, since Policy shipped in 2.0.0. Every shape's
    min_baseline must parse, ordered or not."""
    import nameparser
    from nameparser import Policy
    for sid, shape in shapes.SHAPES.items():
        parsed_min = compare._parse_version(shape.min_baseline)
        if shape.order is not None:
            assert hasattr(nameparser, shape.order), (sid, shape.order)
            Policy(name_order=getattr(nameparser, shape.order))
            assert parsed_min >= (2, 0, 0), sid


def test_v2_fields_matches_the_Role_enum() -> None:
    """The seven roles are 'defined once and derived everywhere'. The
    snapshot cannot import Role into the WORKER (that runs under the
    old wheel), but its copy reads the tree's ParsedName and must track
    Role: a role missing here is invisible to every comparison."""
    from nameparser import Role
    assert snapshot.V2_FIELDS == tuple(str(r) for r in Role)


def _run_template(line: dict[str, Any]) -> tuple[dict[str, Any], dict[str, Any]]:
    """The generated worker, exec'd in-process on one input line. Its
    `import nameparser` then resolves to this checkout, so what it
    emits is the tree's own reading, comparable with snapshot.read's."""
    import nameparser
    source = compare._worker_source(nameparser.__version__, want_v2=True)
    real_stdin, buf = sys.stdin, io.StringIO()
    try:
        sys.stdin = io.StringIO(json.dumps(line, ensure_ascii=False) + "\n")
        with contextlib.redirect_stdout(buf):
            exec(compile(source, "baseline_worker.py", "exec"), {})
    finally:
        sys.stdin = real_stdin
    tell, row = (json.loads(x) for x in buf.getvalue().splitlines())
    assert tell["__version__"] == nameparser.__version__
    return tell, row


_BOTH = frozenset({"capitalized", "capitalized_force"})


@pytest.mark.parametrize("name,order,views", [
    # The one corpus name whose facade and core initials differ
    # ('J. P D.' against 'J. P. D.'), so a row that read the core's
    # value into the facade's slot cannot pass.
    ("Ph. D., John", None, frozenset()),
    ("Ménil Christophe du", "FAMILY_FIRST", frozenset()),
    # The case views (#826), one row per arm of the worker's copy of
    # snapshot.case_views: both views (the plain repair keeps the
    # mixed-case 'EdD', the forced one does not); the plain one alone,
    # order-bearing; the forced one alone. With only the first, a
    # worker comparing plain against forced, or forced against the
    # parse, passed every row (measured 2026-10-22, PR #837's review).
    ("john smith EdD", None, _BOTH),
    ("ménil christophe du", "FAMILY_FIRST", frozenset({"capitalized"})),
    ("John Smith EdD", None, frozenset({"capitalized_force"})),
    # a report's alternative (#752 phase 2m), which the worker records
    # in its own copy of snapshot.alternatives()
    ("Jack", None, frozenset()),
])
def test_the_worker_reads_a_line_as_the_tree_does(
        name: str, order: str | None, views: frozenset[str]) -> None:
    """The worker's row and snapshot.read's are separate code on two
    sides of a process boundary; a comparison means a behavior change
    only while both turn the same parse into the same snapshot row."""
    _, raw = _run_template({"name": name, "order": order})
    if order is not None:
        # the facade is never consulted for an order-bearing entry
        assert "facade" not in raw
    tree = snapshot.read([(name, order)])[0]
    # the row still reaches the arm it is here for
    assert set(snapshot.CASE_VIEWS) & set(tree) == views
    assert snapshot.row(name, order, raw.get("v2"), raw.get("facade")) == tree
    if name == "Jack":
        assert tree["alternatives"] == [
            "GIVEN_OR_FAMILY: name as family (position)"]


def test_a_baseline_without_alternatives_is_not_compared_on_them() -> None:
    # A wheel before 2.7 reports no alternative, so every name the tree
    # reports one for would read as moved: 867 of the 1,088 entries
    # --baseline 2.6.0 reported on 2026-10-26 (#902's review).
    tell, _ = _run_template({"name": "Jack", "order": None})
    assert tell["alternatives"] is True
    assert compare.unrecorded(tell) == ()
    assert compare.unrecorded({**tell, "alternatives": False}) == (
        "alternatives",)
    assert compare.unrecorded({"__version__": "2.6.0"}) == ("alternatives",)


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
    and only the path gives it away."""
    checkout = _TOOLS.parents[1] / "nameparser" / "__init__.py"
    with pytest.raises(SystemExit, match="CHECKOUT"):
        compare._check_tell(
            {"__version__": "2.0.0", "__file__": str(checkout)}, "2.0.0")


def test_tell_rejects_an_empty_tell() -> None:
    with pytest.raises(SystemExit):
        compare._check_tell({}, "2.0.0")


def test_check_tree_accepts_the_checkout_and_rejects_anything_else(
        tmp_path: Path) -> None:
    inside = _TOOLS.parents[1] / "nameparser" / "__init__.py"
    assert compare._check_tree(str(inside)) == inside.resolve()
    with pytest.raises(SystemExit, match="not from the source package"):
        compare._check_tree(str(tmp_path / "nameparser" / "__init__.py"))


@pytest.mark.parametrize("rel", [
    ".venv/lib/python3.11/site-packages/nameparser/__init__.py",
    "build/lib/nameparser/__init__.py",
    "dist/unpacked/nameparser/__init__.py",
])
def test_check_tree_rejects_a_wheel_sitting_inside_the_checkout(
        rel: str) -> None:
    """The repo contains .venv/, build/ and dist/, any of which can hold
    a released wheel, so "under the repo" is not "the source package"."""
    with pytest.raises(SystemExit, match="not from the source package"):
        compare._check_tree(str(compare.REPO_ROOT / rel))


def test_check_tree_resolves_before_comparing() -> None:
    """Without .resolve(), a path escaping via .. reads as inside."""
    escaped = compare.REPO_ROOT / "nameparser" / ".." / ".." / "x" \
        / "nameparser" / "__init__.py"
    with pytest.raises(SystemExit, match="not from the source package"):
        compare._check_tree(str(escaped))


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


def _fake_popen(monkeypatch: pytest.MonkeyPatch, out: str, rc: int = 0) -> None:
    _FakePopen.out, _FakePopen.rc = out, rc
    monkeypatch.setattr(compare.subprocess, "Popen", _FakePopen)


_TELL = ('{"__version__": "1.4.0", '
         '"__file__": "/wheel/nameparser/__init__.py"}')
_ROW = '{"facade": {"first": "John"}}'


def test_run_worker_strips_the_import_path_overrides_from_the_child(
        monkeypatch: pytest.MonkeyPatch) -> None:
    """_worker_env has its own test; this pins that _run_worker USES it."""
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
    """The guard behind compare()'s zip(), which truncates silently."""
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


def test_run_worker_sends_the_name_and_order_on_the_wire(
        monkeypatch: pytest.MonkeyPatch) -> None:
    """The wire format is the whole contract between compare.py and the
    generated worker."""
    _fake_popen(monkeypatch, f"{_TELL}\n{_ROW}\n{_ROW}\n")
    compare._run_worker(
        "1.4.0", False,
        [{"name": "John Smith", "order": None},
         {"name": "Ménil Christophe du", "order": "FAMILY_FIRST"}])
    lines = _FakePopen.last["stdin"].splitlines()
    assert lines[0] == '{"name": "John Smith", "order": null}'
    assert lines[1] == \
        '{"name": "Ménil Christophe du", "order": "FAMILY_FIRST"}'


_ENTRIES = [("John Smith", None), ("Ménil Christophe du", "FAMILY_FIRST")]


def _tree_results(entries: list[tuple[str, str | None]], want_v2: bool
                  ) -> list[dict[str, Any]]:
    """What a worker would emit if the baseline read every entry as
    the tree does -- built by running the template on each line."""
    out = []
    for name, order in entries:
        _, raw = _run_template({"name": name, "order": order})
        if not want_v2:
            raw.pop("v2", None)
        out.append(raw)
    return out


def _fake_compare(monkeypatch: pytest.MonkeyPatch, baseline: str,
                  alter: "Callable[[list[dict[str, Any]]], None] | None" = None,
                  entries: list[tuple[str, str | None]] = _ENTRIES,
                  ) -> tuple[Any, list[dict[str, Any]]]:
    """compare() over _ENTRIES with the worker replaced by the tree's
    own readings, optionally altered by `alter(results)`; also returns
    the entries the worker was sent."""
    monkeypatch.setattr(snapshot, "corpus_entries", lambda paths=None: list(entries))
    monkeypatch.setattr(compare, "_load_snapshot", lambda: snapshot)
    sent: list[list[dict[str, Any]]] = []

    def fake_run(version: str, want_v2: bool, entries: list[dict[str, Any]]
                 ) -> tuple[dict[str, str], list[dict[str, Any]]]:
        sent.append(entries)
        results = _tree_results([(e["name"], e["order"]) for e in entries], want_v2)
        if alter:
            alter(results)
        return {}, results
    monkeypatch.setattr(compare, "_run_worker", fake_run)
    return compare.compare(baseline), sent[0]


def test_compare_reports_no_move_when_the_baseline_reads_like_the_tree(
        monkeypatch: pytest.MonkeyPatch) -> None:
    result, sent = _fake_compare(monkeypatch, "2.4.0")
    assert (result.moves, result.moved, result.compared, result.skipped) \
        == ([], 0, 2, 0)
    # The boundary: an order shipped in 2.0.0, so 2.0.0 itself sends it.
    _, sent = _fake_compare(monkeypatch, "2.0.0")
    assert [e["order"] for e in sent] == [None, "FAMILY_FIRST"]


def test_compare_reports_a_move(monkeypatch: pytest.MonkeyPatch) -> None:
    """A clean run and a broken comparison print the same thing; this
    is the control that the comparison can see a difference."""
    def alter(results: list[dict[str, Any]]) -> None:
        results[0]["v2"]["family"] = "Smyth"
        results[0]["facade"]["last"] = "Smyth"
    r, _ = _fake_compare(monkeypatch, "2.4.0", alter)
    moves, moved, latin = r.moves, r.moved, r.latin
    assert (moved, latin, r.cldr) == (1, 1, 0)
    assert moves[0] == "family: 1"
    assert "'Smyth' -> 'Smith'" in moves[1]


def test_compare_counts_a_moved_name_only_cldr_holds(
        monkeypatch: pytest.MonkeyPatch) -> None:
    """A release figure counts CLDR's fictional renderings out, so the
    report says how many moved names only corpus_cldr.jsonl holds."""
    cldr_name = "Macáková, Alexandra Zuzana (pani, PhD)"
    def alter(results: list[dict[str, Any]]) -> None:
        results[0]["v2"]["nickname"] = "pani PhD"
        results[0]["facade"]["nickname"] = "pani PhD"
    r, _ = _fake_compare(monkeypatch, "2.4.0", alter,
                         entries=[(cldr_name, None)])
    assert (r.moved, r.cldr) == (1, 1)


def test_compare_reads_the_facade_alone_below_2_0(
        monkeypatch: pytest.MonkeyPatch) -> None:
    """1.4 has no 2.0 surface, so the tree's facade reading is what it
    is compared with: a facade move shows, and nothing order-bearing is
    sent, since no order existed before 2.0."""
    def alter(results: list[dict[str, Any]]) -> None:
        results[0]["facade"]["last"] = "Smyth"
    r, sent = _fake_compare(monkeypatch, "1.4.0", alter)
    assert r.moved == 1 and r.moves[0] == "family: 1"
    # The order-bearing entry is skipped, and COUNTED as skipped: a
    # figure quoted from this run has a stated population.
    assert [e["order"] for e in sent] == [None]
    assert (r.compared, r.skipped) == (1, 1)


def test_compare_checks_that_the_tree_side_is_the_checkout(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Pins that compare() CALLS the tree check: run as a script,
    sys.path[0] is tools/differential/, so a PYTHONPATH wheel outranks
    the editable install and two wheels would agree on everything.
    REPO_ROOT is moved, which reproduces the trap's effect."""
    monkeypatch.setattr(compare, "REPO_ROOT", tmp_path)
    with pytest.raises(SystemExit, match="not from the source package"):
        _fake_compare(monkeypatch, "2.4.0")


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


def test_snapshot_checks_that_it_read_the_checkout(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """snapshot.py has compare.py's exposure: run as a script, a
    PYTHONPATH wheel outranks the editable install, and --record would
    write the wheel's readings while --since reported parity. Moving
    REPO_ROOT reproduces the trap's effect."""
    monkeypatch.setattr(snapshot, "corpus_entries", lambda paths=None: [])
    monkeypatch.setattr(snapshot, "REPO_ROOT", tmp_path)
    with pytest.raises(SystemExit, match="not from the source package"):
        snapshot.main([])


def test_snapshot_tree_must_hold_its_own_source_package(
        monkeypatch: pytest.MonkeyPatch) -> None:
    """An ancestor of this checkout holds no nameparser/ of its own, so
    the import falls through to this checkout; "under the root" would
    pass it and compare the tree with its own snapshot."""
    monkeypatch.setattr(snapshot, "corpus_entries", lambda paths=None: [])
    monkeypatch.setattr(sys, "path", list(sys.path))
    with pytest.raises(SystemExit, match="not from the source package"):
        snapshot.main(["--tree", str(_TOOLS.parents[2])])
