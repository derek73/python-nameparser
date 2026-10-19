"""Holds every rule to its recorded size (tests/v2/rules_budget.py)."""
from __future__ import annotations

from tests.v2 import rules_budget
from tests.v2.design_docs import read_rules_text


def test_every_rule_matches_its_recorded_size() -> None:
    found = rules_budget.changes(rules_budget.read_record(),
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
