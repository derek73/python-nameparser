"""The tree's readings of every corpus name match the committed snapshot
(tools/differential/snapshot.py, #664). A failure lists the moved names
grouped by which fields changed; re-record if the moves are intended,
and the diff of snapshot.jsonl is then the review's list of moves."""
from ._differential_fixtures import load_tool

snapshot = load_tool("snapshot")


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


def test_a_name_leaving_the_corpus_is_reported() -> None:
    # A truncated corpus must not pass for a clean run.
    rows = snapshot.read([("John Smith", None), ("Jane Doe", None)])
    assert snapshot.grouped({snapshot.key(r): r for r in rows},
                            {snapshot.key(rows[0]): rows[0]}) \
        == ["(removed from corpus): 1", "    Jane Doe"]


def test_a_name_only_cldr_holds_is_counted_out() -> None:
    # A release figure counts CLDR's fictional renderings out (AGENTS.md,
    # Release-log claims); a name another corpus also holds stays in.
    # One of #653's movers, a CLDR rendering; 'Jane (Janey, Jo) Smith'
    # moved with it and is a rules example only. 'マイケル' is in CLDR
    # AND the CJK corpus, which is the half the subtraction decides.
    cldr_name = "Macáková, Alexandra Zuzana (pani, PhD)"
    shared = "マイケル"
    assert snapshot.only_in(snapshot.CLDR_CORPUS, {shared}) == set()
    assert shared in {n for n, _ in snapshot.corpus_entries(
        [snapshot.CLDR_CORPUS])}, "pick another name CLDR shares"
    cldr = snapshot.only_in(snapshot.CLDR_CORPUS,
                            {cldr_name, "Jane (Janey, Jo) Smith", shared})
    assert cldr == {cldr_name}
