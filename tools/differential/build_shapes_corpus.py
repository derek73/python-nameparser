"""Regenerate corpus_shapes.jsonl from the shape-tagged rows of the
case table and the arrangements of tools/differential/shapes.py.

Every entry here was CHOSEN (#468) -- a row someone wrote with
reviewed expected values -- and the shape id records, once, at
admission, what the name is for. The corpus_cjk pattern generalized:
same source of truth (cases.py), same pinned projection
(tests/v2/test_corpora.py holds the checked-in file equal to this
module's selection), different predicate -- explicit tags instead of
codepoint content.

snapshot.py resolves each entry's shape to its name_order through
tools/differential/shapes.py and reads family-first entries under
that order, on the v2 surface; compare.py skips them below the
shape's minimum baseline.

Regenerate after tagging or editing tagged case rows:

    uv run python tools/differential/build_shapes_corpus.py

Pass --coverage to print names-per-shape instead of writing, which is
the "which shapes, how many names deep" answer #468 asked for.
"""
from __future__ import annotations

import argparse
import importlib.util
import json
import sys
from collections import Counter
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(ROOT))

from tests.v2.cases import CASES  # noqa: E402

OUT = HERE / "corpus_shapes.jsonl"


def _pairs() -> list[tuple[int, str]]:
    """Every distinct (shape, text) pair from tagged rows and from
    shapes.py's ARRANGEMENTS (the inventory per order, 4h), sorted for
    a deterministic file. A text tagged with TWO shapes (the
    family-first divergence pairs) is two pairs: two orders are two
    comparisons."""
    tagged = {(case.shape, case.text) for case in CASES
              if case.shape is not None}
    return sorted(tagged | {(a.shape, a.text) for a in _arrangements()})


def _arrangements() -> tuple[Any, ...]:
    """shapes.py's ARRANGEMENTS, loaded by path as snapshot.py loads
    SHAPES: tools/ is not a package."""
    spec = importlib.util.spec_from_file_location("_shapes", HERE / "shapes.py")
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.ARRANGEMENTS  # type: ignore[no-any-return]


def selected() -> list[dict[str, object]]:
    """The corpus lines, in file order."""
    return [{"name": text, "shape": shape} for shape, text in _pairs()]


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--coverage", action="store_true",
                    help="print names-per-shape and exit")
    args = ap.parse_args()
    if args.coverage:
        by_shape = Counter(shape for shape, _ in _pairs())
        for shape in sorted(by_shape):
            print(f"shape {shape}: {by_shape[shape]} names")
        return
    rows = selected()
    with OUT.open("w", encoding="utf-8") as fh:
        for row in rows:
            fh.write(json.dumps(row, ensure_ascii=False) + "\n")
    print(f"wrote {len(rows)} entries to {OUT.name}")


if __name__ == "__main__":
    main()
