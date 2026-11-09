"""Offline checks on tools/differential/match_diff.py (#1278).

What these pin is the tool's own logic: which pairs it reads out of a
test module and out of each source (planted in a cache of the test's
own), that a source present but unreadable stops the run, what it names
as moved between two rows, the key-guarantee check, the source check
in a child, and runs through main() against copies of the package -- an
unchanged copy reporting no moves through the parallel path (its kept
results reused the second time, and read again once the base's files
change), a base changing while it is read refused, a head-only run, a
sample, and a copy with the family chain's particles-aside step taken
out reporting the pairs that step decided, with exit status 1. The pairs
of the main() runs are fixed here, so none reads a corpus.
"""
from __future__ import annotations

import importlib
import json
import shutil
import sys
import zipfile
from pathlib import Path
from types import ModuleType

import pytest

from tests.checkout import needs_checkout

from ._differential_fixtures import load_tool, own_cache

tool: ModuleType = load_tool("match_diff")
_PACKAGE = Path(__file__).parents[2] / "nameparser"


@pytest.fixture(autouse=True)
def _cache(monkeypatch: pytest.MonkeyPatch,
           tmp_path_factory: pytest.TempPathFactory) -> Path:
    return own_cache(monkeypatch, tmp_path_factory)


def test_a_test_modules_pairs_are_its_tuples_of_two_names(tmp_path: Path) -> None:
    module = tmp_path / "test_x.py"
    module.write_text(
        'ROWS = [("J. Smith", "John Smith"), ("Smith, J", "x"),\n'
        '        ("given", "same"), ("J. Smith", "John Smith"),\n'
        '        (1, "a b"), ("Bill Smith", "William Smith", "familiar")]\n',
        encoding="utf-8")
    assert tool.test_pairs(module) == [
        ("J. Smith", "John Smith"), ("Smith, J", "x"),
        ("Bill Smith", "William Smith")]


def test_a_corpus_not_fetched_is_left_out_with_a_note(tmp_path: Path) -> None:
    module = tmp_path / "test_x.py"
    module.write_text('ROWS = [("J. Smith", "John Smith")]\n', encoding="utf-8")
    pairs, notes = tool.draw_pairs(module)
    assert {source for source, _, _ in pairs} == {
        "tests, as written", "tests, paired"}
    assert [n.split(":")[0] for n in notes] == [
        "jrc-names", "tse-donors", "patentsview"]
    assert all("not present" in n for n in notes)


def _plant(cache: Path, source: str, rows: list[dict[str, str]]) -> None:
    folder = cache / "local" / source
    folder.mkdir(parents=True)
    (folder / "raw.jsonl").write_text(
        "".join(json.dumps(r) + "\n" for r in rows), encoding="utf-8")


def test_each_source_draws_its_pairs_the_same_every_time(
        tmp_path: Path, _cache: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _plant(_cache, "jrc-names", [
        {"entity": "1", "name": "John Smith", "script": "Latin"},
        {"entity": "1", "name": "J. Smith", "script": "Latin"},
        {"entity": "1", "name": "Джон Смит", "script": "Cyrillic"},
        {"entity": "2", "name": "Jane Smith", "script": "Latin"}])
    _plant(_cache, "tse-donors", [
        {"name": "Ana Silva", "registry": "Ana da Silva"},
        {"name": "Ana Silva", "registry": "Ana da Silva"},
        {"name": "Rui Lopes", "registry": "Rui Lopes"}])
    rows = ("inventor_id\traw_inventor_name_first\traw_inventor_name_last\n"
            "a\tJohn\tSmith\na\tJ.\tSmith\nb\tAnn\tLee\nc\t\t\n")
    archive = _cache / tool.PATENTSVIEW_RAW
    archive.parent.mkdir()
    with zipfile.ZipFile(archive, "w") as z:
        z.writestr("readme.txt", "not the table")
        z.writestr(tool.PATENTSVIEW_MEMBER, rows)
    pv = importlib.import_module("local_patentsview")
    monkeypatch.setitem(pv.PV_FILES, pv.PV_RAW,
                        (archive.stat().st_size, "", ""))
    module = tmp_path / "test_x.py"
    module.write_text("ROWS = []\n", encoding="utf-8")
    pairs, notes = tool.draw_pairs(module)
    assert notes == []
    by_source: dict[str, set[frozenset[str]]] = {}
    for source, a, b in pairs:
        by_source.setdefault(source, set()).add(frozenset((a, b)))
    # Latin spellings of one entity; the last-word draw pairs entities;
    # tse keeps one of its repeated rows and none of an unchanged name;
    # PatentsView reads its member by name, an empty name left out
    last_word = by_source.pop("jrc-names, one last word")
    assert last_word and last_word <= {
        frozenset(p) for p in (("John Smith", "J. Smith"),
                               ("John Smith", "Jane Smith"),
                               ("J. Smith", "Jane Smith"))}
    assert by_source == {
        "jrc-names, one entity": {frozenset(("John Smith", "J. Smith"))},
        "tse-donors": {frozenset(("Ana Silva", "Ana da Silva"))},
        "PatentsView, one inventor": {frozenset(("John Smith", "J. Smith"))},
    }
    assert len([p for p in pairs if p[0] == "tse-donors"]) == 1
    assert tool.draw_pairs(module) == (pairs, notes)


def test_a_source_present_but_unreadable_stops_the_run(
        tmp_path: Path, _cache: Path) -> None:
    _plant(_cache, "jrc-names", [{"id": "1", "name": "John Smith",
                                  "script": "Latin"}])
    module = tmp_path / "test_x.py"
    module.write_text("ROWS = []\n", encoding="utf-8")
    with pytest.raises(SystemExit, match="jrc-names: present but unreadable"):
        tool.draw_pairs(module)


def test_a_patentsview_table_of_another_size_stops_the_run(
        tmp_path: Path, _cache: Path) -> None:
    archive = _cache / tool.PATENTSVIEW_RAW
    archive.parent.mkdir()
    with zipfile.ZipFile(archive, "w") as z:
        z.writestr(tool.PATENTSVIEW_MEMBER, "inventor_id\n")
    module = tmp_path / "test_x.py"
    module.write_text("ROWS = []\n", encoding="utf-8")
    with pytest.raises(SystemExit, match="not the pinned release"):
        tool.draw_pairs(module)


def _row(**changes: object) -> dict[str, object]:
    row: dict[str, object] = {
        "setting": "default", "pair": 0, "consistent": True,
        "roles": [["given", "same", "J", "J", "neither"],
                  ["family", "same", "Smith", "Smith", "neither"]],
        "across": [], "alternatives": [None, None],
        "keys": [["smith;j"], ["smith;j"]]}
    row.update(changes)
    return row


def test_what_moved_names_each_part_of_a_row_that_differs() -> None:
    old = _row()
    assert tool.what_moved(old, _row()) == []
    new = _row(consistent=False,
               roles=[["given", "same", "J", "J", "left"],
                      ["family", "conflict", "Smith", "Smyth", "neither"]],
               across=[["middle", "given", "same", "J", "J"]],
               alternatives=[["particle-or-given", "x"], None],
               keys=[["smith;j"], []])
    assert tool.what_moved(old, new) == [
        "verdict True -> False", "given: texts or side",
        "family: same -> conflict", "across-roles matches", "reading used",
        "keys"]
    # a role added or dropped is named, and so is a part no heading names
    more_roles = _row(roles=[*_row()["roles"],  # type: ignore[misc]
                             ["middle", "one-side", "", "A", "right"]])
    assert tool.what_moved(old, more_roles) == ["roles listed"]
    assert tool.what_moved(old, _row(pair=7)) == ["other"]


def test_a_consistent_pair_sharing_no_key_is_a_miss() -> None:
    lines = [json.dumps(_row()),
             json.dumps(_row(keys=[["smith;j"], ["smyth;j"]])),
             json.dumps(_row(consistent=False, keys=[["a"], ["b"]]))]
    assert [r["keys"] for r in tool.key_misses(lines)] == [
        [["smith;j"], ["smyth;j"]]]


def test_a_base_of_other_rows_is_refused(capsys: pytest.CaptureFixture[str]) -> None:
    pairs = [("tests", "a b", "a c")]
    with pytest.raises(SystemExit, match="not the same pairs"):
        tool.report(pairs, [json.dumps(_row())], [])


# -- through main(), against copies of the package --------------------------

_PAIRS = [("tests", "John de la Vega", "John Vega"),
          ("tests", "J. Smith", "John Smith"),
          ("tests", "Bill Smith", "William Smith")]


def _copy(tmp_path: Path, name: str) -> Path:
    root = tmp_path / name
    shutil.copytree(_PACKAGE, root / "nameparser",
                    ignore=shutil.ignore_patterns("__pycache__"))
    return root


@pytest.fixture
def fixed_pairs(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(tool, "draw_pairs", lambda tests: (list(_PAIRS), []))


@needs_checkout
@pytest.mark.usefixtures("fixed_pairs")
def test_an_unchanged_package_moves_nothing_and_its_base_is_kept(
        tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    base = _copy(tmp_path, "base")
    head = _copy(tmp_path, "head")
    # the parallel path, which a real run takes, in the order it read
    argv = ["--base", str(base), "--tree", str(head), "--jobs", "2"]
    assert tool.main(argv) == 0
    out = capsys.readouterr().out
    assert "read it now" in out
    assert f"0 of {len(_PAIRS) * len(tool.SETTINGS)} rows moved" in out
    assert "0 consistent pairs share no key" in out
    assert tool.main(argv) == 0
    assert "reused its kept results" in capsys.readouterr().out
    # a base whose files change is read again, not reused
    init = base / "nameparser" / "__init__.py"
    init.write_text(init.read_text(encoding="utf-8") + "# edited\n",
                    encoding="utf-8")
    assert tool.main(argv) == 0
    assert "read it now" in capsys.readouterr().out


@needs_checkout
@pytest.mark.usefixtures("fixed_pairs")
def test_a_head_only_run_and_a_sample(
        tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    head = _copy(tmp_path, "head")
    assert tool.main(["--tree", str(head), "--jobs", "1", "--sample", "2"]) == 0
    out = capsys.readouterr().out
    assert f"2 pairs (tests 2) x {len(tool.SETTINGS)} settings" in out
    assert "0 consistent pairs share no key" in out
    assert "rows moved" not in out


@needs_checkout
@pytest.mark.usefixtures("fixed_pairs")
def test_a_base_changing_while_it_is_read_is_refused(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    base = _copy(tmp_path, "base")
    head = _copy(tmp_path, "head")
    digests = iter(["a" * 64, "b" * 64])
    monkeypatch.setattr(tool.snapshot, "_source_digest",
                        lambda root: next(digests))
    with pytest.raises(SystemExit, match="changed while it was read"):
        tool.main(["--base", str(base), "--tree", str(head), "--jobs", "1"])


def test_a_child_refuses_a_tree_whose_package_it_did_not_import(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    # nameparser is imported already, from the checkout: a tree that is
    # not where it came from is refused before anything is read
    import nameparser  # noqa: F401
    monkeypatch.setattr(sys, "path", list(sys.path))
    (tmp_path / "nameparser").mkdir()
    with pytest.raises(SystemExit, match="not from the source package"):
        tool.worker(tmp_path, tmp_path / "pairs.jsonl",
                    tmp_path / "out.jsonl", 1)


@needs_checkout
@pytest.mark.usefixtures("fixed_pairs")
def test_a_mutated_package_reports_the_pairs_it_moves(
        tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    base = _copy(tmp_path, "base")
    mutant = _copy(tmp_path, "mutant")
    match = mutant / "nameparser" / "_match.py"
    step = ("    if bases[0] and _fold(bases[0]) == _fold(bases[1]):\n"
            "        return Outcome.PARTICLES_ASIDE\n")
    text = match.read_text(encoding="utf-8")
    assert text.count(step) == 1
    match.write_text(text.replace(step, ""), encoding="utf-8")
    argv = ["--base", str(base), "--tree", str(mutant), "--jobs", "1"]
    assert tool.main(argv) == 1
    out = capsys.readouterr().out
    assert "family: particles-aside -> part-of-other" in out
    assert "'John de la Vega' / 'John Vega'" in out
    # taking particles-aside out of accept stops refusing the pair
    assert "verdict False -> True" in out
