"""Every corpus name's current reading, committed -- a snapshot.

snapshot.jsonl holds one line per (name, order) across every
corpus*.jsonl beside this script: the seven role fields, the reported
ambiguity kinds and initials() on the 2.0 surface, plus the facade's
v1 fields wherever they say something the 2.0 row does not.
tests/v2/test_snapshot.py fails when the tree's readings stop matching
it. A change that moves readings re-records, and the PR diff of
snapshot.jsonl is the list of names it moved -- one line per name, so
the review reads it directly and nothing has to be classified.

    uv run python tools/differential/snapshot.py              # check, grouped
    uv run python tools/differential/snapshot.py --record     # re-record
    uv run python tools/differential/snapshot.py --since v2.5.0   # vs a ref

--since REF compares the tree against the snapshot as committed at a
git ref, which is how a release asks what moved since the last tag.
--tree PATH reads with the nameparser package of another checkout
(the corpus is always this one's), for comparing two trees.
"""
from __future__ import annotations

import argparse
import importlib.util
import json
import subprocess
import sys
from collections import defaultdict
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
SNAPSHOT = HERE / "snapshot.jsonl"
RECORD_COMMAND = "uv run python tools/differential/snapshot.py --record"
V2_FIELDS = ("title", "given", "middle", "family", "suffix", "nickname",
             "maiden")
#: The facade's v1 field each 2.0 field corresponds to.
V1_FOR = dict(zip(V2_FIELDS, ("title", "first", "middle", "last", "suffix",
                              "nickname", "maiden")))


def _shapes() -> dict[int, Any]:
    spec = importlib.util.spec_from_file_location("_shapes", HERE / "shapes.py")
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.SHAPES  # type: ignore[no-any-return]


def corpus_entries() -> list[tuple[str, str | None]]:
    """Every distinct (name, order) in the corpora, sorted."""
    orders = {k: s.order for k, s in _shapes().items()}
    found: set[tuple[str, str | None]] = set()
    for path in sorted(HERE.glob("corpus*.jsonl")):
        for line in path.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            entry = json.loads(line)
            if isinstance(entry, str):
                found.add((entry, None))
            else:
                found.add((entry["name"], orders.get(entry.get("shape"))))
    return sorted(found, key=lambda e: (e[0], e[1] or ""))


def read(entries: list[tuple[str, str | None]]) -> list[dict[str, Any]]:
    import nameparser
    from nameparser import HumanName, Parser, Policy

    parsers: dict[str | None, Any] = {None: Parser()}
    rows = []
    for name, order in entries:
        if order not in parsers:
            parsers[order] = Parser(policy=Policy(name_order=getattr(nameparser, order)))
        p = parsers[order].parse(name)
        row: dict[str, Any] = {"name": name}
        if order:
            row["order"] = order
        row.update({f: v for f in V2_FIELDS if (v := getattr(p, f) or "")})
        if kinds := sorted({a.kind.name for a in p.ambiguities}):
            row["ambiguities"] = kinds
        if initials := p.initials() or "":
            row["initials"] = initials
        if order is None:
            # The facade is a translation of the same parse; record it
            # only where it reads the name differently.
            hn = HumanName(name)
            v1 = hn.as_dict()
            facade = {f: v1[V1_FOR[f]] or "" for f in V2_FIELDS
                      if (v1[V1_FOR[f]] or "") != (getattr(p, f) or "")}
            if (hn.initials() or "") != initials:
                facade["initials"] = hn.initials() or ""
            if facade:
                row["facade"] = facade
        rows.append(row)
    return rows


def key(row: dict[str, Any]) -> tuple[str, str]:
    return row["name"], row.get("order", "")


def dump(rows: list[dict[str, Any]]) -> str:
    return "".join(json.dumps(r, ensure_ascii=False) + "\n" for r in rows)


def load(text: str) -> dict[tuple[str, str], dict[str, Any]]:
    return {key(r): r for r in map(json.loads, text.splitlines()) if r}


def _flat(row: dict[str, Any]) -> dict[str, str]:
    out = {k: ("|".join(v) if isinstance(v, list) else v)
           for k, v in row.items() if k not in ("name", "order", "facade")}
    out.update({f"facade.{k}": v for k, v in row.get("facade", {}).items()})
    return out


def grouped(old: dict[tuple[str, str], dict[str, Any]],
            new: dict[tuple[str, str], dict[str, Any]]) -> list[str]:
    """The moves, grouped by which fields changed, so a large move reads
    as a few kinds of change rather than a wall of names."""
    groups: dict[tuple[str, ...], list[str]] = defaultdict(list)
    for k in sorted(set(old) | set(new)):
        label = k[0] + (f"  [{k[1]}]" if k[1] else "")
        if k not in new:
            groups[("(removed from corpus)",)].append(label)
            continue
        if k not in old:
            groups[("(new to corpus)",)].append(label)
            continue
        a, b = _flat(old[k]), _flat(new[k])
        fields = tuple(sorted(f for f in set(a) | set(b) if a.get(f) != b.get(f)))
        if fields:
            groups[fields].append(f"{label}\n      " + "; ".join(
                f"{f}: {a.get(f, '')!r} -> {b.get(f, '')!r}" for f in fields))
    out = []
    for fields, names in sorted(groups.items(), key=lambda g: -len(g[1])):
        out.append(f"{', '.join(fields)}: {len(names)}")
        out.extend(f"    {n}" for n in names)
    return out


def _use_tree(path: str) -> None:
    root = Path(path).resolve()
    sys.path.insert(0, str(root))
    import nameparser
    got = Path(nameparser.__file__).resolve()
    if root not in got.parents:
        sys.exit(f"--tree {root}: imported nameparser from {got} instead")


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--record", action="store_true", help="rewrite the snapshot")
    ap.add_argument("--since", metavar="REF",
                    help="compare against the snapshot committed at a git ref")
    ap.add_argument("--tree", metavar="PATH", help="read with another checkout")
    ap.add_argument("--out", type=Path, default=SNAPSHOT,
                    help="where --record writes (default: snapshot.jsonl)")
    args = ap.parse_args(argv)
    if args.tree:
        _use_tree(args.tree)
    rows = read(corpus_entries())
    if args.record:
        args.out.write_text(dump(rows), encoding="utf-8")
        print(f"recorded {len(rows)} readings to {args.out}")
        return 0
    if args.since:
        rel = SNAPSHOT.relative_to(Path(subprocess.check_output(
            ["git", "rev-parse", "--show-toplevel"], cwd=HERE, text=True).strip()))
        text = subprocess.check_output(["git", "show", f"{args.since}:{rel}"],
                                       cwd=HERE, text=True)
    else:
        text = SNAPSHOT.read_text(encoding="utf-8")
    moves = grouped(load(text), {key(r): r for r in rows})
    print("\n".join(moves) or "matches the snapshot")
    if moves and not args.since:
        print(f"\nif these moves are intended: {RECORD_COMMAND}")
    return 1 if moves else 0


if __name__ == "__main__":
    sys.exit(main())
