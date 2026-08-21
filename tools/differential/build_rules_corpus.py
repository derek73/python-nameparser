"""Regenerate corpus_rules.jsonl from the examples in docs/design/rules.md.

The fourth corpus, with the fourth provenance (#414). The other three
each have a blind spot the others cover, and this one closes a blind
spot none of them was built to have:

- corpus.jsonl comes from v1's own test suite at a pinned git ref, so
  it is structurally blind to anything 2.0 added.
- corpus_issues.jsonl comes from what users reported, which is the
  adversarial half.
- corpus_cjk.jsonl comes from the CJK rows of the case table, because
  neither of the above can carry an unspaced CJK name.
- this file comes from the NORMATIVE RULES -- the names the project
  has written down as defining its behavior.

Why the rules doc needs a corpus when its examples are already tests.
`test_rules_doc.py` executes every example, which pins them harder
than corpus membership pins anything -- but it pins them against an
expectation stored beside them. Change behavior deliberately and the
expected value is edited in the same commit; the test goes green and
says nothing. A doc example cannot warn about the change that edited
it.

The differential run answers the other question. It parses these names
with a RELEASED baseline, which no commit can edit, so a moved name
arrives unexplained and has to be classified in a ledger in writing.
#409 is the worked example: it changed M2's

    "Jane de la née Jones"      →  family="de la née Jones"

to family="de la". The doc test followed the edit, the name was in no
corpus, and nothing independent observed the movement. Twelve names
this corpus CONTRIBUTED moved during the 2.2 cycle the same way --
thirteen of its names move in total, the thirteenth having already
been in corpus.jsonl.

Selection is every distinct example `text`, through the doc's own
parser rather than a second regex -- the same argument that has
build_cjk_corpus.py select through the shipped script table. A rule
gaining an example enters the corpus by being written down where it
already gets reviewed.

Policy annotations are deliberately ignored. The corpus carries name
STRINGS and the differential run parses them with the default facade,
so a family-first-scoped example is simply one more name to diff --
build_cjk_corpus.py makes the same call for its zh-scoped rows.

The one example form that carries no name is skipped. A `[subject]`
example names a policy or locale rather than a name string, so its
`text` is empty -- rules.md has three, and without the filter all
three collapse into a single "" that the doc never wrote. Skipping
them is also why the promise above is honest: an example enters the
corpus by being written down, and a form with nothing to enter is
better excluded than folded into a shared empty string.

Boundary strings ("(", ".,", "Anna () Smith") are kept, on the
over-collection principle build_corpus.py and build_issues_corpus.py
state: a name that parses to nothing costs one parse and produces no
diff. They are more
concentrated here than elsewhere because the doc argues its edges
explicitly, which is a reason to keep them rather than to drop them.

Regenerate after editing rules.md examples:

    uv run python tools/differential/build_rules_corpus.py

tests/v2/test_ledger_guards.py pins the checked-in file against this
module's selection, so a stale corpus fails the suite rather than
silently narrowing the differential gate.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(ROOT))

from tests.v2.rules_doc import parse_rules_doc  # noqa: E402

OUT = HERE / "corpus_rules.jsonl"
RULES_DOC = ROOT / "docs" / "design" / "rules.md"


def selected_names() -> list[str]:
    """Every distinct example text in the rules doc, sorted for a
    deterministic file."""
    rules = parse_rules_doc(RULES_DOC.read_text(encoding="utf-8"))
    return sorted({example.text
                   for rule in rules
                   for example in rule.examples
                   if example.text})


def main() -> None:
    names = selected_names()
    with OUT.open("w", encoding="utf-8") as fh:
        for name in names:
            fh.write(json.dumps(name, ensure_ascii=False) + "\n")
    print(f"wrote {len(names)} names to {OUT.name}")


if __name__ == "__main__":
    main()
