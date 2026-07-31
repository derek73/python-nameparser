"""Regenerate corpus_cjk.jsonl from the CJK rows of the case table.

The third corpus, with the third provenance (#295): corpus.jsonl
regenerates from v1's test banks at an immutable ref and
corpus_issues.jsonl harvests the issue tracker, but neither can carry
an unspaced CJK name -- v1's authors had no reason to test one, and
build_issues_corpus.py requires an internal space, which is exactly
the shape #271 classifies. This file derives from the reviewed case
table instead: every distinct `text` in tests/v2/cases.py containing
a character the script table classifies, regardless of the row's
policy/locale context -- the corpus carries name STRINGS and the
differential run parses them with the default facade, so a name from
a zh-scoped row is simply one more CJK name to diff.

Selection is by the shipped table (nameparser._policy._SCRIPT_RANGES,
through the same _script_matcher the parser uses), so a script added
to the table widens the harvest on the next regeneration, and a case
row added for new CJK work enters the corpus by being written down in
the table everyone already reviews (#298's 间隔号 forms arrived
exactly this way).

Regenerate after editing CJK case rows:

    uv run python tools/differential/build_cjk_corpus.py

tests/v2/test_regex_sync.py pins the checked-in file against this
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

from nameparser._policy import _SCRIPT_RANGES, _script_matcher  # noqa: E402
from tests.v2.cases import CASES  # noqa: E402

OUT = HERE / "corpus_cjk.jsonl"

_has_cjk = _script_matcher(*_SCRIPT_RANGES)


def selected_names() -> list[str]:
    """Every distinct case-table text bearing a classified codepoint,
    sorted for a deterministic file."""
    return sorted({case.text for case in CASES if _has_cjk(case.text)})


def main() -> None:
    names = selected_names()
    with OUT.open("w", encoding="utf-8") as fh:
        for name in names:
            fh.write(json.dumps(name, ensure_ascii=False) + "\n")
    print(f"wrote {len(names)} names to {OUT.name}")


if __name__ == "__main__":
    main()
