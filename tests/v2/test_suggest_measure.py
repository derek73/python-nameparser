"""Offline checks on tools/differential/suggest_measure.py.

The populations are planted in a cache of the test's own, never the
developer's: a Czech, a British and a Vietnamese one, each a handful of
names, and two parliament lists. What is pinned is the tool's own
logic: a row per population, written order and base order; a planted
family-first population read 100% right under both bases; the harness's
proof that it can report a difference (with `_MIN_VOTES` set past any
group, nothing is decided, so every group written against its base
reads 0%); a source not fetched left out with a note; and the parliament
tables printed.
"""
from __future__ import annotations

import json
import re
from pathlib import Path
from types import ModuleType

import pytest

from tests.checkout import needs_checkout

from ._differential_fixtures import load_tool, own_cache

tool: ModuleType = load_tool("suggest_measure")

_ROW = re.compile(r"^(\S+)\s+(GF|FF)\s+(GF|FF)\s+((?:\s*(?:\d+%|-))+)\s+\d+")

_VI = [{"family": f, "middle": m, "given": g, "name": f"{f} {m} {g}"}
       for f in ("Nguyen", "Tran", "Pham", "Bui")
       for m, g in (("Van", "Thanh"), ("Thi", "Huong"), ("Minh", "Tuan"))]
_CZ = [{"jmeno": g, "prijmeni": f, "name": f"{g} {f}"}
       for g in ("Jan", "Petr", "Marie", "Eva", "Jana")
       for f in ("Novák", "Svoboda", "Veselá")]
_PSC = [{"forename": g, "surname": f, "nationality": "British",
         "name": f"{g} {f}"}
        for g in ("Mary", "Sarah", "Emma", "Peter", "Anna")
        for f in ("Jones", "Wilson", "Davies")]
_PARLIAMENTS = [
    {"dataset": "az_parliament", "form": "name", "script": "Latin", "name": n}
    for n in ("NƏBİYEV Rizvan Novruz oğlu", "HƏSƏNOVA Afət Əbil qızı",
              "AĞAZADƏ Əminə Həmid qızı", "MİKAYILOVA Sevil Əlirazı qızı",
              "QULİYEV Elman Rasim oğlu", "BÜLBÜLOĞLU Polad")] + [
    {"dataset": "ua_rada", "form": "name", "script": "Cyrillic", "name": n}
    for n in ("Гунько Анатолій Григорович", "Аксьонов Андрій Анатолійович",
              "Бакулін Євген Миколайович", "Швачко Антон Олексійович")] + [
    {"dataset": "ua_rada", "form": "alias", "script": "Latin",
     "name": "Hunko Anatolii"}]


@pytest.fixture(autouse=True)
def _cache(monkeypatch: pytest.MonkeyPatch,
           tmp_path_factory: pytest.TempPathFactory) -> Path:
    cache = own_cache(monkeypatch, tmp_path_factory)
    for source, rows in (("uit-vinames", _VI), ("cz-candidates", _CZ),
                         ("psc-individuals", _PSC),
                         ("opensanctions-parliaments", _PARLIAMENTS)):
        folder = cache / "local" / source
        folder.mkdir(parents=True)
        (folder / "raw.jsonl").write_text(
            "".join(json.dumps(r, ensure_ascii=False) + "\n" for r in rows),
            encoding="utf-8")
    return cache


def _rows(out: str) -> dict[tuple[str, str, str], list[str]]:
    rows = {}
    for line in out.splitlines():
        if m := _ROW.match(line):
            rows[m[1], m[2], m[3]] = m[4].split()
    return rows


def _run(capsys: pytest.CaptureFixture[str], *args: str) -> str:
    assert tool.main(["--sizes", "5,10", "--trials", "20", "--jobs", "1",
                      *args]) == 0
    return capsys.readouterr().out


@needs_checkout
def test_a_row_per_population_written_order_and_base(
        capsys: pytest.CaptureFixture[str]) -> None:
    rows = _rows(_run(capsys))
    assert set(rows) == {(p, w, b) for p in ("cz", "psc-British", "vi")
                         for w in ("GF", "FF") for b in ("GF", "FF")}
    assert all(len(cells) == 2 for cells in rows.values())


@needs_checkout
def test_a_family_first_population_reads_right_under_both_bases(
        capsys: pytest.CaptureFixture[str]) -> None:
    rows = _rows(_run(capsys))
    assert rows["vi", "FF", "GF"] == ["100%", "100%"]
    assert rows["vi", "FF", "FF"] == ["100%", "100%"]


@needs_checkout
def test_deciding_nothing_reads_every_group_against_its_base_wrong(
        capsys: pytest.CaptureFixture[str]) -> None:
    out = _run(capsys, "--set", "_MIN_VOTES=1000000")
    assert "thresholds overridden: _MIN_VOTES=1000000" in out
    rows = _rows(out)
    for (_, written, base), cells in rows.items():
        expected = "100%" if written == base else "0%"
        assert cells == [expected, expected]


@needs_checkout
def test_a_source_not_fetched_is_left_out_with_a_note(
        capsys: pytest.CaptureFixture[str]) -> None:
    out = _run(capsys)
    assert "patentsview-inventors: not fetched" in out
    assert not any(p.startswith("pv-") for p, _, _ in _rows(out))


@needs_checkout
def test_the_parliament_tables_are_printed(
        capsys: pytest.CaptureFixture[str]) -> None:
    out = _run(capsys)
    turkic = next(line for line in out.splitlines()
                  if line.startswith("az_parliament ") and "/" in line
                  and "base" not in line)
    # six names, five with a Turkic marker; {T}+FF reads all six right
    assert turkic.split()[3] == "6/6"
    assert re.search(r"^ua_rada\s+Cyrillic base FF n=4 .*rules east-slavic\s+rule$",
                     out, re.M)
    # an alias row is not a name row
    assert "ua_rada                  Latin" not in out


def test_set_refuses_a_name_it_does_not_know() -> None:
    with pytest.raises(SystemExit, match="_MIN_VOTES"):
        tool.main(["--set", "_MAX_VOTES=3"])


@needs_checkout
def test_an_override_is_undone_after_a_run_in_this_process(
        capsys: pytest.CaptureFixture[str]) -> None:
    from nameparser import _suggest
    before = (_suggest._MIN_VOTES, _suggest._MIN_SHARE,
              _suggest._MIN_PATRONYMIC_SHARE)
    _run(capsys, "--set", "_MIN_VOTES=1000000", "--set", "_MIN_SHARE=0.9")
    assert (_suggest._MIN_VOTES, _suggest._MIN_SHARE,
            _suggest._MIN_PATRONYMIC_SHARE) == before


def test_the_groups_are_drawn_apart_from_the_reservoir() -> None:
    # seeded alike, the groups were runs of the slots the reservoir had
    # just filled, consecutive records of a sorted file
    pool, groups = tool.pool_rng(1, "vi"), tool.group_rng(1, "vi")
    assert [pool.random() for _ in range(5)] != [
        groups.random() for _ in range(5)]
    keep = tool._Reservoir(1)
    for i in range(40):
        keep.add("vi", f"Given{i}", f"Family{i}")
    drawn = tool.group_rng(1, "vi").sample(range(40), 5)
    assert drawn != tool.pool_rng(1, "vi").sample(range(40), 5)


@needs_checkout
def test_checks_prints_every_deferred_count(
        capsys: pytest.CaptureFixture[str]) -> None:
    out = _run(capsys, "--checks")
    for start in ("-- deferred checks", "surname votes, East Asian",
                  "wrong surname votes from", "a name ending in a bare letter",
                  "folding ø and ł", "patronymic share without"):
        assert any(line.startswith(start) for line in out.splitlines()), start
    assert "groups suggested right" not in out
