"""Regenerate corpus_conventions.jsonl and conventions_fields.jsonl from
conventions.py's table (#686).

The table holds invented names patterned on naming conventions the other
corpora barely cover; conventions.py says where the conventions come
from and why each row's expected reading is a note rather than a pin.
A row read under a non-default order is written with the shapes.py id
for that order, so the snapshot reads it under that order. A row with
`fields` is also written to conventions_fields.jsonl, in the row format
cldr_agreement.py compares, keyed by the name and its order.

Regenerate after editing the table:

    uv run python tools/differential/build_conventions_corpus.py

tests/v2/test_corpora.py pins both checked-in files against this
module's selection, so a row added without regenerating fails the suite.
"""
from __future__ import annotations

import importlib.util
import json
from pathlib import Path
from types import ModuleType

HERE = Path(__file__).resolve().parent
OUT = HERE / "corpus_conventions.jsonl"
FIELDS_OUT = HERE / "conventions_fields.jsonl"


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


def fields_rows() -> list[dict[str, object]]:
    """The fields file's rows, for the table's rows that state fields."""
    selected()  # the same row checks as the corpus
    return [{"fields": row.fields, "file": "conventions", "label": row.name,
             "order": row.order or "default",
             "shape": None if row.order is None else _shape_for(row.order),
             "text": row.name}
            for row in CONVENTIONS if row.fields is not None]


def _write(path: Path, lines: list[object]) -> None:
    with path.open("w", encoding="utf-8") as fh:
        for line in lines:
            fh.write(json.dumps(line, ensure_ascii=False, sort_keys=True) + "\n")
    print(f"wrote {len(lines)} lines to {path.name}")


def main() -> None:
    _write(OUT, selected())
    _write(FIELDS_OUT, list(fields_rows()))


if __name__ == "__main__":
    main()
