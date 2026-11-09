"""The rule-size report (tests/v2/rules_size.py)."""
from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

import pytest

from tests.v2 import rules_size
from tests.v2.design_docs import read_rules_text
from tests.v2.rules_doc import parse_rules_doc


def _row(**moved: int) -> dict[str, int]:
    row = dict.fromkeys(rules_size.MEASURES, 0)
    return {**row, **moved}


def test_the_tree_measures_every_rule_the_doc_parses() -> None:
    assert set(rules_size.measure(read_rules_text())) == {
        r.rule_id for r in parse_rules_doc(read_rules_text())}


def test_changes_name_each_move_and_each_unmatched_id() -> None:
    before = {"X1": _row(words=8, accepted=1),
              "X3": _row(words=1)}
    now = {"X1": _row(words=9),
           "X2": _row(words=2),
           "X10": _row(words=4)}
    assert rules_size.changes(before, now) == [
        "X1: words 8 -> 9, accepted 1 -> 0",
        "X2: new, 2 words",
        "X3: no longer a rule",
        "X10: new, 4 words",
    ]
    assert rules_size.changes(now, now) == []


def test_measure_orders_rules_by_number() -> None:
    doc = (_SKELETON_DOC.replace("# X1 —", "# X10 —")
           + "\n" + _SKELETON_DOC.replace("# X1 —", "# X2 —"))
    assert list(rules_size.measure(doc)) == ["X2", "X10"]


def test_measure_refuses_text_the_doc_tests_reject() -> None:
    with pytest.raises(ValueError, match="X1"):
        rules_size.measure(_SKELETON_DOC.replace("**Because:**",
                                                 "Because:"))


def _git(repo: Path, *args: str) -> None:
    subprocess.run(["git", "-C", str(repo), "-c", "user.name=t",
                    "-c", "user.email=t@t", *args],
                   check=True, capture_output=True)


@pytest.mark.skipif(shutil.which("git") is None, reason="needs git")
def test_the_base_is_read_at_the_merge_base_not_the_branch_tip(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture[str]) -> None:
    # A scratch repository, so the test reads no history of this one and
    # runs from an export with no .git: the base holds X1, a commit on
    # `main` after the branch point grows it, and the branch grows it
    # differently. Against `main` the report reads the branch point.
    rules = tmp_path / "docs" / "design" / "rules"
    rules.mkdir(parents=True)
    index = rules / "README.md"
    index.write_text("- [X1 — one](X1-one.md)\n", encoding="utf-8")
    rule = rules / "X1-one.md"
    rule.write_text(_SKELETON_DOC, encoding="utf-8")
    _git(tmp_path, "init", "-q", "-b", "main")
    _git(tmp_path, "add", ".")
    _git(tmp_path, "commit", "-qm", "base")
    _git(tmp_path, "switch", "-qc", "branch")
    rule.write_text(_SKELETON_DOC.replace(
        "a thing.", "a thing, written so."), encoding="utf-8")
    _git(tmp_path, "commit", "-qam", "branch grows X1")
    _git(tmp_path, "switch", "-q", "main")
    rule.write_text(_SKELETON_DOC.replace(
        "a thing.", "a thing, and more besides that."), encoding="utf-8")
    _git(tmp_path, "commit", "-qam", "main grows X1")
    _git(tmp_path, "switch", "-q", "branch")

    _, text = rules_size.rules_text_at("main", tmp_path)
    assert rules_size.measure(text) == rules_size.measure(_SKELETON_DOC)

    monkeypatch.setattr(rules_size, "ROOT", tmp_path)
    monkeypatch.setattr(rules_size, "read_rules_text",
                        lambda folder=rules: read_rules_text(folder))
    assert rules_size.main(["--since", "main"]) == 0
    out = capsys.readouterr().out
    assert "X1: words 27 -> 29\n" in out   # the branch's 2, not main's 5


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
    assert rules_size.measure(_SKELETON_DOC) == {
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
    before = rules_size.measure(_SKELETON_DOC)
    after = rules_size.measure(_SKELETON_DOC.replace(old, new, 1))
    assert rules_size.changes(before, after)
    assert after["X1"]["words"] > before["X1"]["words"]


def test_a_field_added_to_the_quotable_parts_moves_words(
        monkeypatch: pytest.MonkeyPatch) -> None:
    # words is read off rules_skeleton.skeleton_parts, the one list
    # skeleton_prose quotes from, so a field added there is counted
    # without a second edit here (#768)
    from tests.v2 import rules_skeleton
    before = rules_size.measure(_SKELETON_DOC)["X1"]
    parts = rules_skeleton.skeleton_parts
    monkeypatch.setattr(rules_skeleton, "skeleton_parts", lambda sk: [
        *parts(sk), ("Extra", "one two three")])
    after = rules_size.measure(_SKELETON_DOC)["X1"]
    assert after["words"] == before["words"] + 3
    assert after["accepted_words"] == before["accepted_words"]
