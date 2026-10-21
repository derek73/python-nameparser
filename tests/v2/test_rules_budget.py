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


def _row(**moved: int) -> dict[str, int]:
    row = dict.fromkeys(rules_budget.MEASURES, 0)
    return {**row, **moved}


def test_changes_name_each_move_and_each_unmatched_id() -> None:
    record = {"X1": _row(words=8, accepted=1),
              "X3": _row(words=1)}
    now = {"X1": _row(words=9),
           "X2": _row(words=2)}
    assert rules_budget.changes(record, now) == [
        "X1: words grew, 8 -> 9",
        "X1: accepted shrank, 1 -> 0",
        "X2: no record -- a new rule is recorded too",
        "X3: recorded, but no rule has that ID",
    ]
    assert rules_budget.changes(now, now) == []


def test_measure_orders_rules_by_number() -> None:
    doc = (_SKELETON_DOC.replace("# X1 —", "# X10 —")
           + "\n" + _SKELETON_DOC.replace("# X1 —", "# X2 —"))
    assert list(rules_budget.measure(doc)) == ["X2", "X10"]


def test_measure_refuses_text_the_doc_tests_reject() -> None:
    with pytest.raises(ValueError, match="X1"):
        rules_budget.measure(_SKELETON_DOC.replace("**Because:**",
                                                   "Because:"))


def test_changes_report_a_measure_the_record_lacks_or_no_longer_has() -> None:
    now = {"X1": _row(words=1)}
    assert rules_budget.changes({"X1": {"words": 1}}, now) == [
        f"X1: {key} grew, None -> 0" for key in rules_budget.MEASURES
        if key != "words"]
    # a measure the record holds and the tree no longer takes (a
    # block-format row's `exceptions`, #761) is named, never ignored
    stale = {"X1": {**now["X1"], "exceptions": 3}}
    assert rules_budget.changes(stale, now) == [
        "X1: recorded 'exceptions', which is no longer measured"]


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


_SKELETON_DOC = """\
# X1 — one

**When:** a name ends in a thing.

**Then:** one two three four five six.

- seven eight nine ten.

**Because:** Because one. Because two.

```
"John Smith III"  →  suffix="III"
```

**Except:**

- **First.**
  ```
  "John V"  →  family="V"  · boundary
  ```
- **Second.**
  ```
  "John W"  →  family="W"  · boundary
  ```

**Precedence:**

- **Before a comma**: C1 decides.

**Accepted:**

- one two three four five.

---

**Signal:** a shape
**history:** decisions/P2 · **implemented:** nameparser/_parser.py
"""


def test_the_measure_reads_a_skeleton_rule() -> None:
    assert rules_budget.measure(_SKELETON_DOC) == {
        "X1": {"words": 27, "then_words": 10, "because_sentences": 2,
               "except": 2, "precedence": 1, "accepted": 1,
               "accepted_words": 5}}


@pytest.mark.parametrize("old, new", [
    ("- **First.**", "- **First.** And three more words."),
    ("**When:** a name ends in a thing.",
     "**When:** a name ends in a thing, written so."),
    ("**Because:** Because one.", "**Because:** Because one more."),
    ("- **Before a comma**: C1 decides.",
     "- **Before a comma**: C1 decides it."),
    ("**Then:**", "**Tolerated:** no convention writes it.\n\n**Then:**"),
])
def test_words_added_to_any_quotable_field_move_the_row(
        old: str, new: str) -> None:
    assert old in _SKELETON_DOC
    before = rules_budget.measure(_SKELETON_DOC)
    after = rules_budget.measure(_SKELETON_DOC.replace(old, new, 1))
    assert rules_budget.changes(before, after)
    assert after["X1"]["words"] > before["X1"]["words"]


def test_a_field_added_to_the_quotable_parts_moves_words(
        monkeypatch: pytest.MonkeyPatch) -> None:
    # words is read off rules_skeleton.skeleton_parts, the one list
    # skeleton_prose quotes from, so a field added there is counted
    # without a second edit here (#768)
    from tests.v2 import rules_skeleton
    before = rules_budget.measure(_SKELETON_DOC)["X1"]
    parts = rules_skeleton.skeleton_parts
    monkeypatch.setattr(rules_skeleton, "skeleton_parts", lambda sk: [
        *parts(sk), ("Extra", "one two three")])
    after = rules_budget.measure(_SKELETON_DOC)["X1"]
    assert after["words"] == before["words"] + 3
    assert after["accepted_words"] == before["accepted_words"]
