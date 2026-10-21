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

Seven measures, read from the rule's parsed fields (rules_skeleton.py)
rather than counted over prose, the word counts off
rules_skeleton.skeleton_parts, the list a citation quotes: ``words``
(every quotable field but the Accepted bullets: When, Tolerated, Then
and its bullets, Because, Except and Precedence, so a word added
anywhere in them moves the record), ``then_words`` (Then and its
bullets), ``because_sentences``, ``except``, ``precedence`` and
``accepted`` (bullet counts) and ``accepted_words`` (the Accepted
bullets' words). The footer, the fences and the labels are not counted.
"""
from __future__ import annotations

import argparse
import json
from collections.abc import Callable
from pathlib import Path

from tests.v2 import rules_skeleton
from tests.v2.design_docs import read_rules_text
from tests.v2.rules_doc import Rule, parse_rules_doc
from tests.v2.rules_skeleton import count_sentences

RECORD = Path(__file__).with_name("rules_budget.json")
RECORD_COMMAND = "uv run python -m tests.v2.rules_budget --record"
MEASURES = ("words", "then_words", "because_sentences", "except",
            "precedence", "accepted", "accepted_words")

def _row(rule: Rule) -> dict[str, int]:
    sk = rule.skeleton
    assert sk is not None
    parts = rules_skeleton.skeleton_parts(sk)

    def words(keep: Callable[[str], bool]) -> int:
        return len(" ".join(t for f, t in parts if keep(f)).split())

    return {
        "words": words(lambda f: f != "Accepted"),
        "then_words": words(lambda f: f in ("Then", "Then bullet")),
        "because_sentences": count_sentences(sk.because),
        "except": len(sk.excepts),
        "precedence": len(sk.precedence),
        "accepted": len(sk.accepted),
        "accepted_words": sum(len(b.text.split()) for b in sk.accepted),
    }


def measure(text: str) -> dict[str, dict[str, int]]:
    """Each rule's measures, keyed by rule ID, in ID order. The text is
    parsed first, so a rules text the doc tests reject raises here
    rather than being measured."""
    out = {r.rule_id: _row(r) for r in parse_rules_doc(text)}
    return dict(sorted(out.items(),
                       key=lambda kv: (kv[0][0], int(kv[0][1:]))))


def _unique(pairs: list[tuple[str, object]]) -> dict[str, object]:
    seen: dict[str, object] = {}
    for key, value in pairs:
        if key in seen:
            raise ValueError(
                f"{RECORD.name} holds {key!r} twice -- a merge kept both "
                f"lines; json would keep the last and never compare the "
                f"first. Re-record with `{RECORD_COMMAND}`")
        seen[key] = value
    return seen


def read_record(path: Path | None = None) -> dict[str, dict[str, int]]:
    """The record, refusing a duplicated key or a value that is not a
    measure's count, either of which would make the comparison lie."""
    data = json.loads((path or RECORD).read_text(encoding="utf-8"),
                      object_pairs_hook=_unique)
    for rid, row in data.items():
        if not (isinstance(row, dict) and all(
                isinstance(v, int) and not isinstance(v, bool)
                for v in row.values())):
            raise ValueError(
                f"{RECORD.name}: {rid}'s row is not counts by measure: "
                f"{row!r}. Re-record with `{RECORD_COMMAND}`")
    return data  # type: ignore[no-any-return]


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
        old_row, new_row = record[rid], now[rid]
        for key in MEASURES:
            old, new = old_row.get(key), new_row[key]
            if old != new:
                way = "grew" if old is None or new > old else "shrank"
                out.append(f"{rid}: {key} {way}, {old} -> {new}")
        for key in sorted(set(old_row) - set(MEASURES)):
            out.append(f"{rid}: recorded {key!r}, which is no longer "
                       f"measured")
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
    if not now:
        print("no rules found; refusing to compare or record nothing")
        return 1
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
