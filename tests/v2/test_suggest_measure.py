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
              "Бакулін Євген Миколайович", "Швачко Антон Олексійович",
              "Шевченко Тарас Григорович")] + [
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
    out = _run(capsys, "--set", "_MIN_VOTES=1000000",
               "--set", "_MIN_PATRONYMIC_VOTES=1000000")
    assert "_MIN_VOTES=1000000" in out
    assert "_MIN_PATRONYMIC_VOTES=1000000" in out
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
    assert re.search(r"^ua_rada\s+Cyrillic base FF n=5 .*rules east-slavic\s+rule$",
                     out, re.M)
    # an alias row is not a name row
    assert "ua_rada                  Latin" not in out


@needs_checkout
def test_the_default_sizes_start_at_two_names(
        capsys: pytest.CaptureFixture[str]) -> None:
    # groups of 2 to 4 are where a patronymic rule forced given-first
    # on a family-first base, so the default table measures them
    assert tool.main(["--trials", "5", "--jobs", "1"]) == 0
    out = capsys.readouterr().out
    header = next(line for line in out.splitlines()
                  if line.startswith("population"))
    assert header.split()[3:6] == ["2", "3", "4"]


def test_set_refuses_a_name_it_does_not_know() -> None:
    with pytest.raises(SystemExit, match="_MIN_VOTES"):
        tool.main(["--set", "_MAX_VOTES=3"])


@needs_checkout
def test_an_override_is_undone_after_a_run_in_this_process(
        capsys: pytest.CaptureFixture[str]) -> None:
    from nameparser import _suggest
    before = (_suggest._MIN_VOTES, _suggest._MIN_SHARE,
              _suggest._MIN_PATRONYMIC_SHARE, _suggest._MIN_PATRONYMIC_VOTES)
    _run(capsys, "--set", "_MIN_VOTES=1000000", "--set", "_MIN_SHARE=0.9",
         "--set", "_MIN_PATRONYMIC_VOTES=7")
    assert (_suggest._MIN_VOTES, _suggest._MIN_SHARE,
            _suggest._MIN_PATRONYMIC_SHARE,
            _suggest._MIN_PATRONYMIC_VOTES) == before


def test_a_threshold_the_tree_lacks_is_left_to_its_own_rule(
        monkeypatch: pytest.MonkeyPatch) -> None:
    # a base checkout older than a threshold has no such name: the run
    # there leaves it alone rather than raising (#1345's review)
    from nameparser import _suggest
    monkeypatch.delattr(_suggest, "_MIN_TRAILING_NAMES")
    with tool._thresholds({"_MIN_TRAILING_NAMES": 0, "_MIN_VOTES": 7}):
        assert _suggest._MIN_VOTES == 7
        assert not hasattr(_suggest, "_MIN_TRAILING_NAMES")
    assert _suggest._MIN_VOTES == 2


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
                  "patronymic share without"):
        assert any(line.startswith(start) for line in out.splitlines()), start
    assert "groups suggested right" not in out


# -- the review's fix wave (A6, A7) ------------------------------------------


def _plant_patentsview(cache: Path, lines: list[dict[str, object]]) -> None:
    import gzip
    import local_patentsview  # type: ignore[import-not-found]
    path = local_patentsview.extract_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    body = json.dumps({"release": local_patentsview.PV_RELEASE}) + "\n" + "".join(
        json.dumps(line, ensure_ascii=False) + "\n" for line in lines)
    path.write_bytes(gzip.compress(body.encode("utf-8")))


def test_patentsview_reads_the_country_whatever_the_key_order(
        _cache: Path) -> None:
    _plant_patentsview(_cache, [
        {"country": "JP", "family": "Tanaka", "given": "Hiroshi"},
        {"family": "Sato", "given": "Yuki", "country": "JP", "people": 2},
        {"given": "Kenji", "people": 1, "family": "Ito", "country": "JP"},
        {"country": "ZZ", "family": "Nobody", "given": "Anyone"}])
    keep = tool._Reservoir(1)
    tool._patentsview(keep)
    assert sorted(keep.pools["pv-JP"]) == [
        ("Hiroshi", "Tanaka"), ("Kenji", "Ito"), ("Yuki", "Sato")]


@needs_checkout
def test_orcid_bylines_keep_only_a_byline_the_boxes_confirm(
        _cache: Path) -> None:
    """The orcid-byline population's filter, and nothing past it: what
    the gate (decisions/group-suggestion, 2026-11-11 TRAILING INITIAL)
    does with the population is the tool's table, read by hand."""
    rows = [
        # kept: spaced, joined, dotted and capitals; a hyphen or a space
        # in the family box
        {"credit": "Huntley R P", "family": "Huntley", "given": "Rosa"},
        {"credit": "Hoy AM", "family": "Hoy", "given": "Anna"},
        {"credit": "Smith J.", "family": "smith", "given": "John"},
        {"credit": "Lopez-Diaz M.A.", "family": "Lopez Diaz",
         "given": "Maria"},
        # dropped: a box missing, one word, a word after the head that is
        # no initial, a head that is not the family box, a first initial
        # that is not the given box's first letter
        {"credit": "Jones R", "family": "Jones", "given": ""},
        {"credit": "Jones", "family": "Jones", "given": "Rita"},
        {"credit": "Jones Rita", "family": "Jones", "given": "Rita"},
        {"credit": "Rita J", "family": "Jones", "given": "Rita"},
        {"credit": "Jones K", "family": "Jones", "given": "Rita"},
    ]
    folder = _cache / "local" / "orcid-researchers"
    folder.mkdir(parents=True)
    (folder / "raw.jsonl").write_text(
        "".join(json.dumps(r) + "\n" for r in rows), encoding="utf-8")
    keep = tool._Reservoir(1)
    tool._orcid_bylines(keep)
    assert sorted(keep.pools["orcid-byline"]) == [
        ("AM", "Hoy"), ("J.", "Smith"), ("M.A.", "Lopez-Diaz"),
        ("R P", "Huntley")]


@needs_checkout
def test_an_orcid_file_holding_no_byline_gets_a_note(
        _cache: Path, capsys: pytest.CaptureFixture[str]) -> None:
    # an empty population is a note, never a silently empty row
    folder = _cache / "local" / "orcid-researchers"
    folder.mkdir(parents=True)
    (folder / "raw.jsonl").write_text(json.dumps(
        {"credit": "Rita Jones", "family": "Jones", "given": "Rita"}) + "\n",
        encoding="utf-8")
    out = _run(capsys)
    assert "orcid-researchers: present, but no names read" in out


@needs_checkout
def test_a_wanted_population_that_yields_no_names_gets_a_note(
        _cache: Path, capsys: pytest.CaptureFixture[str]) -> None:
    _plant_patentsview(_cache, [
        {"country": "JP", "family": "Tanaka", "given": "Hiroshi"}])
    out = _run(capsys)
    # patentsview is present but holds no US name, and the planted PSC
    # rows hold no Polish one
    assert "pv-US: no names" in out
    assert "psc-Polish: no names" in out
    assert "pv-JP: no names" not in out


@needs_checkout
def test_a_present_source_yielding_nothing_gets_a_note(
        _cache: Path, capsys: pytest.CaptureFixture[str]) -> None:
    (_cache / "local" / "cz-candidates" / "raw.jsonl").write_text(
        json.dumps({"jmeno": "", "prijmeni": ""}) + "\n", encoding="utf-8")
    out = _run(capsys)
    assert "cz-candidates: present, but no names" in out


@needs_checkout
def test_moved_compares_the_parliaments_and_the_east_slavic_counts() -> None:
    base = {"populations": [{"label": "vi", "cells": {"GF/GF": [1.0]},
                             "east_slavic": 0}],
            "parliaments": {"turkic": {"az_parliament": {"{T}": 3}},
                            "suggestions": [{"dataset": "ua_rada", "x": 1}]}}
    head = json.loads(json.dumps(base))
    assert tool.moved(base, head) == []
    head["populations"][0]["east_slavic"] = 4
    head["parliaments"]["turkic"]["az_parliament"]["{T}"] = 5
    head["parliaments"]["suggestions"][0]["x"] = 2
    out = "\n".join(tool.moved(base, head))
    assert "east_slavic" in out and "0 -> 4" in out
    assert "az_parliament" in out
    assert "ua_rada" in out


@needs_checkout
def test_checks_report_the_groups_a_contested_name_moves(
        _cache: Path, capsys: pytest.CaptureFixture[str]) -> None:
    # a positive control: five patronymic names and two whose only
    # evidence is a contested order. With the two in the denominator,
    # 5 of 7 is not more than four in five; without them, 5 of 5 is
    rows = [{"forename": "Ivan Petrovich", "surname": "Sidorov",
             "nationality": "British"}] * 5 + [
        {"forename": "Jason", "surname": "Kim J.",
         "nationality": "British"}] * 2
    (_cache / "local" / "psc-individuals" / "raw.jsonl").write_text(
        "".join(json.dumps(r) + "\n" for r in rows), encoding="utf-8")
    assert tool.main(["--sizes", "7", "--trials", "3", "--jobs", "1",
                      "--checks"]) == 0
    out = capsys.readouterr().out
    line = next(x for x in out.splitlines()
                if x.startswith("patronymic share without"))
    # six groups hold five patronymic names, so could decide a rule;
    # the three written given-first move, the family-first ones
    # (`Kim J. Jason`) being uncontested
    assert "3 of 6 groups that could decide a rule" in line, line


@pytest.mark.parametrize("dataset, name, truth", [
    # a three-word name ending in a marker: the father's name and the
    # marker are the family (rules/O2, #1187)
    ("kg_jogorku_kenesh", "Бекмырза Чолпонбай уулу", "Чолпонбай уулу"),
    # a family-last name with a surname keeps its last word
    ("kg_jogorku_kenesh", "Равшанбек Рысбаевич Рысбаев", "Рысбаев"),
    ("uz_legislative_chamber", "Odiljon Fotihjon o'g'li Tojiyev", "Tojiyev"),
    # four words ending in a marker in a family-first list: the first
    ("uz_senate", "Ziyo Azamat Hamid o‘g‘li", "Ziyo"),
])
def test_the_turkic_truth_reads_a_three_word_marker_name_whole(
        dataset: str, name: str, truth: str) -> None:
    assert tool._turkic_truth(dataset, name) == truth
