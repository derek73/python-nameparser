"""The tree's readings of every corpus name match the committed snapshot
(tools/differential/snapshot.py). A failure lists the moved names
grouped by which fields changed; re-record if the moves are intended,
and the diff of snapshot.jsonl is then the review's list of moves."""
from __future__ import annotations

import importlib.util
from pathlib import Path

_PATH = Path(__file__).resolve().parents[2] / "tools" / "differential" / "snapshot.py"
_spec = importlib.util.spec_from_file_location("_snapshot", _PATH)
assert _spec and _spec.loader
snapshot = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(snapshot)


def test_readings_match_the_snapshot() -> None:
    recorded = snapshot.load(snapshot.SNAPSHOT.read_text(encoding="utf-8"))
    current = {snapshot.key(r): r for r in snapshot.read(snapshot.corpus_entries())}
    moves = snapshot.grouped(recorded, current)
    assert not moves, ("\n".join(moves)
                       + f"\n\nif these moves are intended: {snapshot.RECORD_COMMAND}")


def test_the_snapshot_can_report_a_move() -> None:
    # A clean run and a broken comparison print the same thing; prove
    # this one can see a difference.
    rows = snapshot.read([("John Smith", None)])
    moved = [{**rows[0], "family": "Smyth"}]
    assert snapshot.grouped({snapshot.key(r): r for r in rows},
                            {snapshot.key(r): r for r in moved})
