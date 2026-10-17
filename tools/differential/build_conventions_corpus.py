"""Regenerate corpus_conventions.jsonl from conventions.py's table (#686).

The table holds invented names patterned on naming conventions the other
corpora barely cover; conventions.py says where the conventions come
from and why each row's expected reading is a note rather than a pin.
A row read under a non-default order is written with the shapes.py id
for that order, so the snapshot reads it under that order.

Regenerate after editing the table:

    uv run python tools/differential/build_conventions_corpus.py

tests/v2/test_corpora.py pins the checked-in file against this module's
selection, so a row added without regenerating fails the suite.
"""
from __future__ import annotations

import importlib.util
import json
from pathlib import Path
from types import ModuleType

HERE = Path(__file__).resolve().parent
OUT = HERE / "corpus_conventions.jsonl"


def _load(stem: str) -> ModuleType:
    """A sibling module, loaded by path as snapshot.load_shapes does:
    tools/ is not a package, and putting tools/differential/ on sys.path
    would let its modules shadow bare imports for the rest of a test run."""
    spec = importlib.util.spec_from_file_location(f"_{stem}", HERE / f"{stem}.py")
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


CONVENTIONS = _load("conventions").CONVENTIONS
SHAPES = _load("shapes").SHAPES


def _shape_for(order: str) -> int:
    """The one shapes.py id that is an input shape for `order`."""
    ids = [k for k, shape in SHAPES.items() if shape.order == order]
    if len(ids) != 1:
        raise ValueError(f"conventions.py names order {order!r}, which "
                         f"{len(ids)} shapes.py shapes declare; use one of "
                         f"{sorted({s.order for s in SHAPES.values() if s.order})}")
    return ids[0]


def selected() -> list[object]:
    """The corpus lines, in table order: a bare name under the default
    order, else the name with its order's shape."""
    seen: set[tuple[str, str | None]] = set()
    lines: list[object] = []
    for row in CONVENTIONS:
        if (row.name, row.order) in seen:
            raise ValueError(f"conventions.py lists {row.name!r} under "
                             f"{row.order or 'the default order'} twice")
        seen.add((row.name, row.order))
        lines.append(row.name if row.order is None
                     else {"name": row.name, "shape": _shape_for(row.order)})
    return lines


def main() -> None:
    lines = selected()
    with OUT.open("w", encoding="utf-8") as fh:
        for line in lines:
            fh.write(json.dumps(line, ensure_ascii=False) + "\n")
    print(f"wrote {len(lines)} names to {OUT.name}")


if __name__ == "__main__":
    main()
