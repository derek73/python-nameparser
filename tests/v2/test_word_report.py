"""Offline checks on tools/vocab/word_report.py.

The report reads each tree in a child process and counts the local
corpora without quoting them, so what these pin is the grid's coverage
(every shape, case and order), the child's refusal of a package from
outside its tree, a base comparison that can report a difference, the
corpus counts' positions and readings, and that no corpus name reaches
the output. The corpus names are invented, and each carries a word no
grid shape holds, so that one in the output is a quoted name.
"""
import importlib.util
import sys
from collections import Counter
from pathlib import Path
from types import ModuleType
from typing import Any

import pytest

from ._differential_fixtures import checkout_copy, own_cache, plant_corpus

_PATH = Path(__file__).parents[2] / "tools" / "vocab" / "word_report.py"


def _load() -> ModuleType:
    spec = importlib.util.spec_from_file_location("vocab_word_report", _PATH)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


report = _load()
corpora = report.local_corpora
_ROOT = report.ROOT


@pytest.fixture(autouse=True)
def _own_cache(monkeypatch: pytest.MonkeyPatch, tmp_path_factory: pytest.TempPathFactory) -> Path:
    return own_cache(monkeypatch, tmp_path_factory)


@pytest.fixture(autouse=True)
def _no_usage(monkeypatch: pytest.MonkeyPatch) -> None:
    """name_usage.py reads caches of its own; its rows are stubbed."""
    monkeypatch.setattr(report, "usage", lambda words: {
        w: [{"source": "stub", "status": "ok", "given": 7, "note": ""}] for w in words})


#: Invented names: Zyx and Qwv are in no grid shape.
_NAMES = ["Queen Zyx", "Queen Zyx", "Mr Queen Qwv", "Zyx, Queen", "QUEEN, ANN",
          "Ann Queen", "Queenie Zyx", "Deacon Zyx"]


def _plant(monkeypatch: pytest.MonkeyPatch, names: list[str] = _NAMES) -> None:
    plant_corpus(monkeypatch, corpora, "ctgov-officials",
                 [{"name": n, "nct": str(i)} for i, n in enumerate(names)],
                 "2026-10-21T09:00:05", "officials")


def test_the_grid_spells_every_shape_three_ways_under_every_order() -> None:
    items = report.grid_items("queen")
    texts = list(dict.fromkeys(t for t, _ in items))
    assert len(items) == 3 * len(texts) == 3 * 3 * len(report.SHAPES)
    assert {o for _, o in items} == set(report.ORDERS)
    assert {"Queen Lau", "QUEEN LAU", "queen lau", "Lau, Queen", "LAU, QUEEN", ", Queen",
            "John Smith, Jr., Queen", "Mr. and Mrs. Queen Lau"} <= set(texts)


def test_a_grid_folds_the_orders_that_agree_and_with_a_base_prints_only_moves() -> None:
    items = [("Lau, Queen", o) for o in report.ORDERS] + [("Ana Queen", o) for o in report.ORDERS]
    same = {"fields": {"title": "Queen"}, "ambiguities": []}
    rows = [same] * 3 + [{"fields": {"family": "Queen"}, "ambiguities": []},
                         *[{"fields": {"given": "Queen"}, "ambiguities": ["X"]}] * 2]
    lines = report.format_grid(items, rows)
    assert lines[0].split() == ["'Lau,", "Queen'", "all", "title='Queen'"]
    assert len(lines) == 4 and "GF" in lines[1] and "[X]" in lines[2]
    base = list(rows)
    base[4] = same
    moved = report.format_grid(items, rows, base)
    assert len(moved) == 2 and "base title='Queen'" in moved[0] and "head given" in moved[1]


@pytest.mark.parametrize(("name", "found"), [
    ("Queen Zyx", [("queen", "opens")]),
    ("QUEEN. ZYX", [("queen", "opens")]),
    ("Zyx, Queen Ann", [("queen", "after a comma")]),
    ("Queen, Queen", [("queen", "opens"), ("queen", "after a comma")]),
    ("Queenie Zyx", []),
    ("Ann Queen", []),
    ("Zyx, Ann Queen", []),
])
def test_a_corpus_name_holds_the_word_where_it_opens_the_name_or_the_comma_part(
        name: str, found: list[tuple[str, str]]) -> None:
    assert report.positions(name, frozenset({"queen"})) == found


@pytest.mark.parametrize(("fields", "reading"), [
    ({"title": "Queen", "given": "Zyx"}, "title"),
    ({"title": "Mr Queen", "given": "Zyx"}, "title"),
    ({"title": "Queen"}, "title"),
    ({"given": "Queen", "family": "Zyx"}, "given"),
    ({"given": "Ann", "family": "Queen"}, "other"),
    # The registers the ranking is for write in capitals.
    ({"title": "QUEEN", "given": "ZYX"}, "title"),
    ({"given": "QUEEN", "family": "ZYX"}, "given"),
])
def test_a_reading_is_classed_by_where_the_word_went(fields: dict[str, str],
                                                     reading: str) -> None:
    assert report.classify("queen", "opens", {"fields": fields, "ambiguities": []}) == reading


def test_the_ranking_puts_the_words_filed_most_as_forenames_first() -> None:
    # The forename box's count orders: a word three filers typed as a
    # forename (every one of its filings) ranks below one 164 did among
    # 165, since a count cannot be rebuilt from a share. A word filed
    # only as a title is the cost of a move; unfiled words come last, by
    # titles: a register's LAU, BARON loses its given name as Baron Lau.
    head: Any = {"a": {"x": {"opens": Counter(title=1, given=9)},
                       "y": {"opens": Counter(title=50)},
                       "w": {"after a comma": Counter(title=6)},
                       "v": {"opens": Counter(title=2)},
                       "u": {"opens": Counter(title=1)}},
                 "b": {"x": {"opens": Counter(title=1), "after a comma": Counter(title=2)}}}
    scanned: Any = {"a": {"found": {}, "boxes": {"y": Counter(title=40),
                                                  "v": Counter(forename=3),
                                                  "u": Counter(title=1, forename=164)}},
                    "b": {"found": {}, "boxes": {"x": Counter(title=1, forename=3)}}}
    ranked = report.ranking(["x", "y", "w", "v", "u", "z"], head, scanned)
    # v and x tie on 3 forenames: the higher share first.
    assert [k for k, _ in ranked] == ["u", "v", "x", "y", "w", "z"]
    lines = report.format_ranking(ranked)
    assert lines[1].split() == ["u", "1", "1", "0", "0", "1", "164", "1", "164/165"]
    assert lines[2].split()[-3:] == ["3", "0", "3/3"]
    assert lines[3].split()[-3:] == ["3", "1", "3/4"]
    assert lines[4].split()[-3:] == ["0", "40", "0/40"]
    assert lines[5].split() == ["w", "0", "0", "6", "6", "6", "0", "0", "-"]


def test_the_report_counts_the_corpora_and_quotes_no_name(
        monkeypatch: pytest.MonkeyPatch) -> None:
    _plant(monkeypatch)
    out = "\n".join(report.report(["queen", "deacon"], _ROOT, None, rank_only=False, jobs=1))
    assert "Zyx" not in out and "Qwv" not in out
    # Queen Zyx, twice, reads the title; QUEEN, ANN opens with the word
    # as a surname; Zyx, Queen holds it after the comma; Mr Queen Qwv
    # opens with another word, and Queenie is another word.
    assert "ctgov-officials, opens: 3 (title 2, other 1)" in out
    assert "ctgov-officials, after a comma: 1 (title 1)" in out
    assert "fec-individuals: not fetched" in out
    assert "stub: given 7" in out
    ranked = out.split("ranking:")[1].splitlines()
    assert ranked[1].strip() == f"(read 1 of {len(corpora.SOURCES)} local corpora; not fetched: " \
        + ", ".join(s for s in sorted(corpora.SOURCES) if s != "ctgov-officials") + ")"
    assert ranked[3].split() == ["queen", "3", "2", "1", "1", "3", "0", "0", "-"]
    assert ranked[4].split() == ["deacon", "1", "1", "0", "0", "1", "0", "0", "-"]


def test_the_ranking_alone_reads_no_grid(monkeypatch: pytest.MonkeyPatch) -> None:
    _plant(monkeypatch)
    out = report.report(["queen"], _ROOT, None, rank_only=True, jobs=1)
    assert not any(line.startswith(("grid", "== ")) for line in out)
    assert out[-1].split() == ["queen", "3", "2", "1", "1", "3", "0", "0", "-"]


def test_a_base_check_reports_a_planted_change_and_none_across_a_copy(
        monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    # The harness must be able to report a difference: a base read with
    # the head's tree by mistake would show no move across a planted one.
    _plant(monkeypatch)
    planted = checkout_copy(tmp_path / "planted", planted=True)
    out = report.report(["queen"], _ROOT, planted, rank_only=False, jobs=2)
    text = "\n".join(out)
    assert "Zyx" not in text and "Qwv" not in text
    assert sum(" base " in line for line in out) > len(report.SHAPES)
    assert "->" in text.split("\ncorpora (")[1]
    copy = checkout_copy(tmp_path / "copy")
    out = report.report(["queen"], _ROOT, copy, rank_only=False, jobs=2)
    assert "byte-identical" in out[2]
    assert out[out.index(next(line for line in out if line.startswith("grid"))) + 1] == "  (none)"
    assert "->" not in "\n".join(out).split("\ncorpora (")[1].split("usage")[0]


def test_a_child_refuses_a_package_from_outside_its_tree(tmp_path: Path) -> None:
    # tmp_path holds no nameparser, so the child's import falls through
    # to the installed package, which check_source refuses.
    with pytest.raises(SystemExit, match="(?s)reading with .* failed.*not from the source package"):
        report.read_trees([tmp_path], [("Queen Lau", None)], 1)
    # The control: this checkout is the package its child imports.
    [rows] = report.read_trees([_ROOT], [("Queen Lau", None)], 1)
    assert rows[0]["fields"]["title"] == "Queen"


def test_a_local_corpus_s_credit_is_trimmed_from_its_usage_note() -> None:
    rows = [{"source": "ctgov-officials (local corpus)", "status": "ok", "given": None,
             "note": "Some registry; terms, data as of 2026-10-21; 10 of 5 officials write it"},
            {"source": "US SSA", "status": "missing", "note": "not cached"}]
    assert report.format_usage(rows) == [
        "  ctgov-officials (local corpus): -; 10 of 5 officials write it",
        "  US SSA: -; missing: not cached"]


def test_the_command_refuses_a_rank_against_a_base_and_no_words(
        capsys: pytest.CaptureFixture[str]) -> None:
    for argv in (["--rank", "queen", "--base", "."], []):
        with pytest.raises(SystemExit) as raised:
            report.main(argv)
        assert raised.value.code == 2
    capsys.readouterr()


def test_a_ranking_over_no_fetched_corpus_says_its_counts_are_empty() -> None:
    # Unread corpora counted as zeros are a clean run's look-alike.
    out = report.report(["queen"], _ROOT, None, rank_only=True, jobs=1)
    assert any("read no local corpus" in line for line in out)
    assert out[-1].split() == ["queen", "0", "0", "0", "0", "0", "0", "0", "-"]


def test_a_damaged_corpus_ends_the_report(monkeypatch: pytest.MonkeyPatch) -> None:
    _plant(monkeypatch)
    raw = Path(str(corpora.directory("ctgov-officials", create=False))) / corpora.RAW
    raw.write_text(raw.read_text() + "\n")
    with pytest.raises(SystemExit, match="ctgov-officials: damaged"):
        report.report(["queen"], _ROOT, None, rank_only=True, jobs=1)


def test_a_failed_usage_lookup_is_reported_not_raised(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.undo()  # the real usage(), with its subprocess faked
    import subprocess
    answers = [subprocess.CompletedProcess([], 1, "", "Traceback\nOSError: boom\n"),
               subprocess.CompletedProcess([], 1, "", ""),
               subprocess.CompletedProcess([], 0, "not json", "")]
    monkeypatch.setattr(report.subprocess, "run", lambda *a, **k: answers.pop(0))
    notes = [report.format_usage(report.usage(["queen"])["queen"]) for _ in range(3)]
    assert notes[0] == ["  name_usage.py: -; failed: OSError: boom"]
    assert notes[1] == ["  name_usage.py: -; failed: exit 1"]
    assert notes[2][0].startswith("  name_usage.py: -; failed: its output is not JSON")


def test_the_child_s_worker_path_reads_as_it_reads_in_process(
        monkeypatch: pytest.MonkeyPatch) -> None:
    # A child takes the worker path only past PARALLEL_FLOOR texts, which
    # no test reaches in a child; the same call, run in this process.
    import importlib
    items = report.grid_items("queen")
    serial = report._parse_chunk(items)[1]
    monkeypatch.setattr(importlib.import_module("snapshot"), "PARALLEL_FLOOR", 1)
    assert report.snapshot.parallel(report._parse_chunk, items, 2, module="word_report") == serial


#: Invented PSC filings: the boxes as Companies House keeps them, a box
#: only where the filer filled it.
_FILED = [{"title": "Queen", "forename": "Zyx", "surname": "Qwv"},
          {"title": "Queen", "forename": "Ann", "surname": "Zyx"},
          {"forename": "Queen", "surname": "Zyx"},
          {"title": "Dr", "forename": "Queen", "surname": "Qwv"},
          {"forename": "Queenie", "surname": "Zyx"}]


def test_a_corpus_of_filed_boxes_splits_the_names_by_the_box_the_word_was_typed_in(
        monkeypatch: pytest.MonkeyPatch) -> None:
    import importlib
    psc = corpora.PSC
    records = [{"name": " ".join(r.get(b, "") for b in ("title", "forename", "surname")
                                 ).strip(), "nationality": "British", **r} for r in _FILED]
    plant_corpus(monkeypatch, corpora, psc, records, "2026-10-22", "filed names",
                 {"sample": f"1 in {importlib.import_module('local_psc').PSC_SAMPLE}"})
    out = report.report(["queen"], _ROOT, None, rank_only=False, jobs=1)
    text = "\n".join(out)
    assert "Zyx" not in text and "Qwv" not in text
    # Dr Queen Qwv opens with another word, so only three are boxed.
    assert f"{psc}, opens: 3 (" in text and "filed in the title box 2, forename box 1" in text
    assert out[-1].split() == ["queen", "3", "3", "0", "0", "3", "1", "2", "1/3"]


def _cases(shape: str) -> list[str]:
    return [shape, shape.upper(), shape.lower()]


def _row(**fields: str) -> dict[str, Any]:
    return {"fields": fields, "ambiguities": []}


def test_a_base_grid_folds_cases_and_orders_and_keeps_an_order_specific_move() -> None:
    items = [(t, o) for t in _cases("Lau, Queen") + _cases("Ana Queen") for o in report.ORDERS]
    titled = [_row(title=t.split(", ")[1]) for t in _cases("Lau, Queen") for _ in report.ORDERS]
    given = [_row(given=t.split()[1], family=t.split()[0]) for t in _cases("Ana Queen")
             for _ in report.ORDERS]
    base = titled + given
    # Every case and order of the first shape moves alike: one block.
    head = [_row(given=r["fields"]["title"]) for r in titled] + list(given)
    # The second moves under FAMILY_FIRST alone: a block for that order.
    head[9 + 1] = head[12 + 1] = head[15 + 1] = _row(title="Queen")
    moved = report.format_grid(items, head, base)
    assert len(moved) == 4, moved
    assert moved[0].split()[:5] == ["'Lau,", "Queen'", "(3", "cases)", "all"]
    assert moved[2].split()[:8] == ["'Ana", "Queen'", "(3", "cases)", "FF", "base",
                                    "given='Queen'", "family='Ana'"]
    # Spelled differently once lowercased, cases stay apart.
    head[12 + 1] = _row(title="QUEEN ANA")
    assert len(report.format_grid(items, head, base)) == 2 + 3 * 2


def test_a_grid_without_a_base_folds_the_cases_too() -> None:
    items = [(t, o) for t in _cases("Lau, Queen") for o in report.ORDERS]
    rows = [_row(title=t.split(", ")[1]) for t in _cases("Lau, Queen") for _ in report.ORDERS]
    [line] = report.format_grid(items, rows)
    assert line.split() == ["'Lau,", "Queen'", "(3", "cases)", "all", "title='Queen'"]
