"""Offline checks on tools/differential/match_diff.py (#1278).

What these pin is the tool's own logic: which pairs it reads out of a
test module, what it names as moved between two rows, the key-guarantee
check, and two runs through main() against a copy of the package -- an
unchanged copy reporting no moves (and its kept results reused the second
time), and a copy with the family chain's particles-aside step taken out
reporting the pairs that step decided, with exit status 1. The pairs of
those runs are fixed here, so no run reads a corpus.
"""
from __future__ import annotations

import json
import shutil
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
    argv = ["--base", str(base), "--tree", str(head), "--jobs", "1"]
    assert tool.main(argv) == 0
    out = capsys.readouterr().out
    assert "read it now" in out
    assert f"0 of {len(_PAIRS) * len(tool.SETTINGS)} rows moved" in out
    assert "0 consistent pairs share no key" in out
    assert tool.main(argv) == 0
    assert "reused its kept results" in capsys.readouterr().out


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
