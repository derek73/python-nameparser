"""Holds every rule to its recorded size (tests/v2/rules_budget.py)."""
from __future__ import annotations

from pathlib import Path

import pytest

from tests.v2 import rules_budget
from tests.v2.design_docs import read_rules_text
from tests.v2.rules_doc import parse_rules_doc


def test_every_rule_matches_its_recorded_size() -> None:
    record = rules_budget.read_record()
    # Not vacuous: an empty record compared with an empty measure would
    # pass, so the record must hold every rule the doc parses.
    assert set(record) == {
        r.rule_id for r in parse_rules_doc(read_rules_text())}
    found = rules_budget.changes(record,
                                 rules_budget.measure(read_rules_text()))
    assert not found, "\n".join([
        *found,
        "A rule's size moved against tests/v2/rules_budget.json. The "
        "record is not a cap: if the change is intended, re-record with "
        f"`{rules_budget.RECORD_COMMAND}` and say so in the PR -- for "
        "growth, name what each new clause reads (docs/design/AGENTS.md, "
        "axis 12); a clause reading a signal the rule did not already "
        "read is a new rule."])


_DOC = """\
X1. Rationale: a reason.
    The statement, unless it is not.
      "a b"  →  family="b"
    Accepted: a cost, except here.
      "a"  →  given="a"  · boundary
    Accepted, and a second spelling: two.
    Accepted rather than repaired: still the second clause.
    Signal: a count: these words are not counted
    implemented: nameparser/_parser.py
X2. Two words.
    no-boundary: not counted
    implemented: nameparser/_parser.py

## A section (X)

Background: a section's words are not a rule's.
"""


def test_the_measure_reads_the_statement_alone() -> None:
    assert rules_budget.measure(_DOC) == {
        "X1": {"words": 9, "exceptions": 1, "accepted": 2,
               "accepted_words": 5 + 14},
        "X2": {"words": 2, "exceptions": 0, "accepted": 0,
               "accepted_words": 0},
    }


def test_changes_name_each_move_and_each_unmatched_id() -> None:
    record = {"X1": {"words": 8, "exceptions": 1, "accepted": 1,
                     "accepted_words": 3},
              "X3": {"words": 1, "exceptions": 0, "accepted": 0,
                     "accepted_words": 0}}
    now = {"X1": {"words": 9, "exceptions": 0, "accepted": 1,
                  "accepted_words": 3},
           "X2": {"words": 2, "exceptions": 0, "accepted": 0,
                  "accepted_words": 0}}
    assert rules_budget.changes(record, now) == [
        "X1: words grew, 8 -> 9",
        "X1: exceptions shrank, 1 -> 0",
        "X2: no record -- a new rule is recorded too",
        "X3: recorded, but no rule has that ID",
    ]
    assert rules_budget.changes(now, now) == []


def test_measure_orders_rules_by_number() -> None:
    doc = ('X10. Ten.\n    implemented: x.py\n'
           'X2. Two.\n    implemented: x.py\n')
    assert list(rules_budget.measure(doc)) == ["X2", "X10"]


def test_measure_refuses_text_the_doc_tests_reject() -> None:
    with pytest.raises(ValueError, match="Signal"):
        rules_budget.measure("X1. S.\n    signal: lowercase\n")


def test_changes_report_a_measure_the_record_lacks_or_no_longer_has() -> None:
    now = {"X1": {"words": 1, "exceptions": 0, "accepted": 0,
                  "accepted_words": 0}}
    assert rules_budget.changes({"X1": {"words": 1}}, now) == [
        "X1: exceptions grew, None -> 0",
        "X1: accepted grew, None -> 0",
        "X1: accepted_words grew, None -> 0",
    ]
    stale = {"X1": {**now["X1"], "clauses": 3}}
    assert rules_budget.changes(stale, now) == [
        "X1: recorded 'clauses', which is no longer measured"]


@pytest.mark.parametrize("text, match", [
    ('{"X1": {"words": 1}, "X1": {"words": 2}}', "twice"),
    ('{"X1": {"words": "2"}}', "not counts"),
    ('{"X1": {"words": true}}', "not counts"),
    ('{"X1": 3}', "not counts"),
])
def test_a_record_that_would_compare_wrongly_is_refused(
        tmp_path: Path, text: str, match: str) -> None:
    path = tmp_path / "record.json"
    path.write_text(text, encoding="utf-8")
    with pytest.raises(ValueError, match=match):
        rules_budget.read_record(path)


def test_the_command_the_failure_message_offers_runs(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    # The failure message hands the reader RECORD_COMMAND, so the code
    # behind it is exercised end to end against a scratch record.
    record = tmp_path / "rules_budget.json"
    monkeypatch.setattr(rules_budget, "RECORD", record)
    assert rules_budget.main([]) == 1                  # no record yet
    assert rules_budget.main(["--record"]) == 0
    assert set(rules_budget.read_record(record)) == {
        r.rule_id for r in parse_rules_doc(read_rules_text())}
    assert rules_budget.main([]) == 0
    record.write_text(record.read_text().replace(
        '"words": ', '"words": 1', 1))
    assert rules_budget.main([]) == 1
