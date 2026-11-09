"""How each rule in docs/design/rules/ grew or shrank since a base commit.

A rule grows one sound clause at a time, every review passing, until it
has to be split by hand (S2 by #682, C1 by #728). This report puts that
growth in front of a reviewer:

    uv run python -m tests.v2.rules_size --since origin/master

measures every rule in the working tree and at the merge-base of
``--since`` and HEAD, and prints one line per rule that moved, for axis
12 (docs/design/AGENTS.md) to ask what the new words read. It prints
and exits 0; nothing here fails the suite. Through 2026-11-09 the sizes
were a committed record the suite held the tree to, retired because
every rules PR rewrote that one file and branches editing neighbouring
rules conflicted in it (decisions/rules-size-record).

Seven measures, read from the rule's parsed fields (rules_skeleton.py)
rather than counted over prose, the word counts off
rules_skeleton.skeleton_parts, the list a citation quotes: ``words``
(every quotable field but the Accepted bullets: When, Tolerated, Then
and its bullets, Because, Except and Precedence), ``then_words`` (Then
and its bullets), ``because_sentences``, ``except``, ``precedence`` and
``accepted`` (bullet counts) and ``accepted_words`` (the Accepted
bullets' words). The footer, the fences and the labels are not counted.
"""
from __future__ import annotations

import argparse
import subprocess
import tempfile
from collections.abc import Callable
from pathlib import Path

from tests.v2 import rules_skeleton
from tests.v2.design_docs import RULES_DIR, read_rules_text
from tests.v2.rules_doc import Rule, parse_rules_doc
from tests.v2.rules_skeleton import count_sentences

ROOT = RULES_DIR.parents[2]
RULES_PATH = RULES_DIR.relative_to(ROOT).as_posix()
DEFAULT_SINCE = "origin/master"
MEASURES = ("words", "then_words", "because_sentences", "except",
            "precedence", "accepted", "accepted_words")

Sizes = dict[str, dict[str, int]]


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


def measure(text: str) -> Sizes:
    """Each rule's measures, keyed by rule ID, in ID order. The text is
    parsed first, so a rules text the doc tests reject raises here
    rather than being measured."""
    out = {r.rule_id: _row(r) for r in parse_rules_doc(text)}
    return dict(sorted(out.items(),
                       key=lambda kv: (kv[0][0], int(kv[0][1:]))))


def _git(root: Path, *args: str) -> str:
    return subprocess.run(["git", "-C", str(root), *args], check=True,
                          capture_output=True, text=True).stdout.strip()


def rules_text_at(since: str,
                  root: Path | None = None) -> tuple[str, str]:
    """The merge-base of ``since`` and HEAD, and the rules text as that
    commit holds it, read through design_docs.read_rules_text from an
    export of the rules folder, so the index decides the order as it
    does for the tree."""
    root = root or ROOT
    base = _git(root, "merge-base", since, "HEAD")
    with tempfile.TemporaryDirectory() as tmp:
        archive = subprocess.run(
            ["git", "-C", str(root), "archive", base, RULES_PATH],
            check=True, capture_output=True).stdout
        subprocess.run(["tar", "-x", "-C", tmp], input=archive, check=True)
        return base, read_rules_text(Path(tmp) / RULES_PATH)


def changes(before: Sizes, now: Sizes) -> list[str]:
    """One line per rule that moved: each measure that changed, a rule
    the base lacks, a rule the tree no longer has."""
    out = []
    for rid in sorted(set(before) | set(now),
                      key=lambda r: (r[0], int(r[1:]))):
        if rid not in before:
            out.append(f"{rid}: new, {now[rid]['words']} words")
        elif rid not in now:
            out.append(f"{rid}: no longer a rule")
        else:
            moved = [f"{key} {before[rid][key]} -> {now[rid][key]}"
                     for key in MEASURES
                     if before[rid].get(key) != now[rid][key]]
            if moved:
                out.append(f"{rid}: " + ", ".join(moved))
    return out


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--since", default=DEFAULT_SINCE, metavar="REF",
                    help="compare against the merge-base of REF and HEAD "
                         f"(default {DEFAULT_SINCE})")
    args = ap.parse_args(argv)
    base, text = rules_text_at(args.since)
    found = changes(measure(text), measure(read_rules_text()))
    print(f"rules against {args.since} (merge-base {base[:10]}):")
    print("\n".join(found) or "no rule moved")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
