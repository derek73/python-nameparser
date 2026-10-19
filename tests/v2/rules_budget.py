"""The recorded size of every rule in docs/design/rules/.

A rule grows one sound clause at a time, every review passing, until it
has to be split by hand (S2 by #682, C1 by #728). This module measures
each rule and tests/v2/test_rules_budget.py holds the tree to the
measurement recorded in rules_budget.json beside it, so a rule that
grows fails the suite and its growth shows in the record's diff --
the reviewer's view of it (mechanisms.md#RECORDED-ROSTERS). The record
is not a cap: an author whose rule has to grow re-records with

    uv run python -m tests.v2.rules_budget --record

and says so in the PR, where axis 12 (docs/design/AGENTS.md) asks what
the new words read. A rule that shrinks fails too, so the record
follows it down and the words cannot come back unseen.

Four measures, all over the statement prose a citation may quote
(rules_doc.prose_blocks, so the Signal:, example, pointer and marker
lines are not counted):

- ``words``: the statement's words, the Rationale included and the
  Accepted: clauses not;
- ``exceptions``: the statement's ``except`` and ``unless`` -- a proxy
  for the clauses that carve a case out of the rule, which is the way
  the split rules grew;
- ``accepted``: the number of Accepted clauses (``Accepted:`` or
  ``Accepted, and ...:``, rules_doc.ACCEPTED_RE);
- ``accepted_words``: their words, so a sentence added inside an
  existing Accepted clause moves the record too.
"""
from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

from tests.v2.design_docs import read_rules_text
from tests.v2.rules_doc import prose_blocks, split_accepted

RECORD = Path(__file__).with_name("rules_budget.json")
RECORD_COMMAND = "uv run python -m tests.v2.rules_budget --record"
MEASURES = ("words", "exceptions", "accepted", "accepted_words")

_RULE_ID_RE = re.compile(r"[A-Z]\d+")
_EXCEPTION_RE = re.compile(r"\b(?:except|unless)\b", re.IGNORECASE)


def measure(text: str) -> dict[str, dict[str, int]]:
    """Each rule's measures, keyed by rule ID, in ID order."""
    out = {}
    for rid, lines in prose_blocks(text).items():
        if not _RULE_ID_RE.fullmatch(rid):
            continue                # a section's Background
        stmt_lines, clauses = split_accepted(lines)
        statement = " ".join(stmt_lines)
        out[rid] = {
            "words": len(statement.split()),
            "exceptions": len(_EXCEPTION_RE.findall(statement)),
            "accepted": len(clauses),
            "accepted_words": sum(len(" ".join(c).split()) for c in clauses),
        }
    return dict(sorted(out.items(),
                       key=lambda kv: (kv[0][0], int(kv[0][1:]))))


def read_record() -> dict[str, dict[str, int]]:
    data: dict[str, dict[str, int]] = json.loads(
        RECORD.read_text(encoding="utf-8"))
    return data


def changes(record: dict[str, dict[str, int]],
            now: dict[str, dict[str, int]]) -> list[str]:
    """Every difference between the record and the tree, one line each:
    a rule grown or shrunk past its record, a rule the record lacks, a
    record for no rule."""
    out = []
    for rid in sorted(set(record) | set(now)):
        if rid not in record:
            out.append(f"{rid}: no record -- a new rule is recorded too")
            continue
        if rid not in now:
            out.append(f"{rid}: recorded, but no rule has that ID")
            continue
        for key in MEASURES:
            old, new = record[rid].get(key), now[rid][key]
            if old != new:
                way = "grew" if old is None or new > old else "shrank"
                out.append(f"{rid}: {key} {way}, {old} -> {new}")
    return out


def _dump(record: dict[str, dict[str, int]]) -> str:
    """One rule per line, so a rule's move is a one-line diff."""
    rows = [f"  {json.dumps(rid)}: {json.dumps(row)}"
            for rid, row in record.items()]
    return "{\n" + ",\n".join(rows) + "\n}\n"


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--record", action="store_true",
                    help=f"rewrite {RECORD.name} from the tree")
    args = ap.parse_args(argv)
    now = measure(read_rules_text())
    if RECORD.exists():
        found = changes(read_record(), now)
        print("\n".join(found) or "every rule matches its record")
    else:
        found = [f"no {RECORD.name} yet"]
        print(found[0])
    if args.record:
        RECORD.write_text(_dump(now), encoding="utf-8")
        print(f"recorded {len(now)} rules in {RECORD.name}")
        return 0
    return 1 if found else 0


if __name__ == "__main__":
    raise SystemExit(main())
