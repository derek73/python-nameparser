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


def test_the_snapshot_can_report_a_case_only_move() -> None:
    # Case views reach grouped() only because _flat passes every key
    # through; a view changing value and a view appearing are both moves.
    rows = snapshot.read([("john smith EdD", None)])
    old = {snapshot.key(r): r for r in rows}
    recased = {**rows[0], "capitalized_force": "John Smith EdD"}
    assert snapshot.grouped(old, {snapshot.key(recased): recased})[0] \
        == "capitalized_force: 1"
    gone = {k: v for k, v in rows[0].items() if k != "capitalized"}
    assert snapshot.grouped(old, {snapshot.key(gone): gone})[0] \
        == "capitalized: 1"


def test_a_case_view_is_recorded_only_where_it_moves_something() -> None:
    plain_only, untouched, forced_only = snapshot.read(
        [("john smith", None), ("John Smith", None), ("John Smith EdD", None)])
    assert plain_only["capitalized"] == "John Smith"
    assert "capitalized_force" not in plain_only
    assert not set(snapshot.CASE_VIEWS) & set(untouched)
    assert "capitalized" not in forced_only
    # A role move in a name repair leaves alone moves no case view...
    reordered = snapshot.read([("John Smith", "FAMILY_FIRST")])[0]
    assert reordered["family"] != untouched["family"]
    assert not set(snapshot.CASE_VIEWS) & set(reordered)
    # ...but the view is the whole repaired name, so in a name it does
    # repair, a role move that changes the rendering moves the view
    # with no word changing case: the echo the initials column has.
    caps, caps_reordered = snapshot.read(
        [("JOHN SMITH", None), ("JOHN SMITH", "FAMILY_FIRST")])
    assert (caps["capitalized"], caps_reordered["capitalized"]) \
        == ("John Smith", "Smith John")


def test_a_snapshot_predating_the_case_views_is_not_compared_on_them() -> None:
    # --since v2.5.0 reported 961 entries on 2026-10-22, 910 of them the
    # keys appearing; against a snapshot that records a view anywhere,
    # the views stay compared.
    rows = snapshot.read([("john smith", None), ("John Smith EdD", None)])
    new = {snapshot.key(r): dict(r) for r in rows}
    old = {k: {f: v for f, v in r.items() if f not in snapshot.CASE_VIEWS}
           for k, r in new.items()}
    assert snapshot.unrecorded_views(old, new) == snapshot.CASE_VIEWS
    assert not snapshot.grouped(old, new)
    # A snapshot that records a view on one row, or only the plain
    # view, still compares both: a name repair leaves alone records none.
    rows = snapshot.read([("john smith", None), ("John Smith", None)])
    new = {snapshot.key(r): dict(r) for r in rows}
    current = {k: dict(r) for k, r in new.items()}
    assert snapshot.unrecorded_views(current, new) == ()
    assert new == current
    assert not any("capitalized_force" in r for r in current.values())


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
