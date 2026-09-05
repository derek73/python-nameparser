"""Regenerate the two CJK corpora from the CJK rows of the case table.

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

That harvest is SPLIT in two by the row's `tolerated` flag (the
2026-09-01 CJK demotion): an unmarked text goes to
corpus_cjk.jsonl, which stays a CONTRACT corpus, and a text marked
tolerated on its rows goes to corpus_cjk_tolerated.jsonl, a RADAR one
(compare.py's _CORPUS_TIERS). Both files are written by one run over
one sweep, so the two halves cannot drift apart or double-count a
text. Nothing about the harvest predicate changed: a composed or
wrapped CJK form -- a comma listing, a Latin title or credential
around a CJK name, and since 2026-09-05 a trailing ASCII period on an
honorific -- is still compared at every baseline and still
classified against the ledger. What the flag moves is which of THESE
TWO FILES a text is written to, and nothing else: a text that another
CONTRACT corpus also holds keeps the contract tier until it leaves
there too, because compare.py loads contract files first and its
(name, order) dedup keeps the contract reading. That was live when
this split landed -- corpus_rules.jsonl carried five of these texts
as rules.md examples -- and the rules.md edits later the same day
removed all five: W3 marked tolerated, W2's two comma examples
swapped for pure ones, C1's two moved into W3. No text written here
is held contract anywhere today. The sentence stays because it is the
mechanism, not a note about those five: a demotion is complete only
when no contract corpus holds the text, and the next demotion has to
check that for itself.

The flag is read PER TEXT, not per row: the corpora carry name
strings, so a text on two rows (a default row and a policy/locale
fork of it) is one line in one file. A text marked tolerated on one
of its rows and unmarked on another is therefore a hard error rather
than a silent choice: neither half would select it -- contract takes
the texts whose flags are all False, tolerated the ones all True --
so the name would leave the harness entirely.

Regenerate after editing CJK case rows:

    uv run python tools/differential/build_cjk_corpus.py

tests/v2/test_ledger_guards.py pins both checked-in files against
this module's selection, so a stale corpus fails the suite rather
than silently narrowing the differential gate.
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
OUT_TOLERATED = HERE / "corpus_cjk_tolerated.jsonl"

_has_cjk = _script_matcher(*_SCRIPT_RANGES)


def _partition() -> tuple[list[str], list[str]]:
    """(contract, tolerated) texts, each sorted for a deterministic
    file. A text marked tolerated on ANY row while unmarked on
    another is a hard error, and note WHICH failure the raise
    prevents: the two selections below are `flags == {False}` and
    `flags == {True}`, so a split text matches NEITHER and would
    vanish from both files -- dropped from the harness, unwatched at
    every baseline, rather than landing on one tier or the other."""
    by_text: dict[str, set[bool]] = {}
    ids_by_text: dict[str, list[str]] = {}
    for case in CASES:
        if _has_cjk(case.text):
            by_text.setdefault(case.text, set()).add(case.tolerated)
            ids_by_text.setdefault(case.text, []).append(case.id)
    split = sorted(text for text, flags in by_text.items() if len(flags) > 1)
    if split:
        rows = "; ".join(
            f"{text!r} on {sorted(ids_by_text[text])}" for text in split)
        raise SystemExit(
            f"texts marked tolerated on one row and not another: {rows}. "
            f"A split text is selected by neither half, so it would be "
            f"dropped from both corpora and watched at no baseline. "
            f"Resolve it deliberately: every row of the text marked "
            f"demotes it to the radar file, every row clear keeps it "
            f"in the contract one")
    contract = sorted(t for t, flags in by_text.items() if flags == {False})
    tolerated = sorted(t for t, flags in by_text.items() if flags == {True})
    return contract, tolerated


def selected_names() -> list[str]:
    """The contract half: every distinct case-table text bearing a
    classified codepoint whose rows do not declare it tolerated."""
    return _partition()[0]


def tolerated_names() -> list[str]:
    """The radar half: the same harvest, for texts whose rows declare
    tolerated."""
    return _partition()[1]


def main() -> None:
    contract, tolerated = _partition()
    for path, names in ((OUT, contract), (OUT_TOLERATED, tolerated)):
        with path.open("w", encoding="utf-8") as fh:
            for name in names:
                fh.write(json.dumps(name, ensure_ascii=False) + "\n")
        print(f"wrote {len(names)} names to {path.name}")


if __name__ == "__main__":
    main()
