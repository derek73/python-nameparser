"""Every corpus name's current reading, committed -- a snapshot.

snapshot.jsonl holds one line per (name, order) across every
corpus*.jsonl beside this script: the seven role fields, the reported
ambiguity kinds and initials() on the 2.0 surface, plus the facade's
v1 fields wherever they say something the 2.0 row does not.
tests/v2/test_snapshot.py fails when the tree's readings stop matching
it. A change that moves readings re-records, and the PR diff of
snapshot.jsonl is the list of names it moved -- one line per name, so
the review reads it directly and nothing has to be classified (#664).

    uv run python tools/differential/snapshot.py              # check, grouped
    uv run python tools/differential/snapshot.py --record     # re-record
    uv run python tools/differential/snapshot.py --since v2.5.0   # vs a ref

--since REF compares the tree against the snapshot as committed at a
git ref, which is how a release asks what moved since the last tag.
--tree PATH reads with the nameparser package of another checkout
(the corpus is always this one's), for comparing two trees.

A corpus that loses names shows them as removed, so a truncated file
cannot pass for a clean run. compare.py builds its baseline rows with
row() too, so a released wheel's readings and the tree's are compared
in one shape.
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
V1_FIELDS = ("title", "first", "middle", "last", "suffix", "nickname",
             "maiden")
#: The facade's v1 field each 2.0 field corresponds to.
V1_FOR = dict(zip(V2_FIELDS, V1_FIELDS))
#: The keys a corpus line may carry. A misspelled key is refused rather
#: than ignored: ignoring it would drop the shape the line declares and
#: read the name under the default order with nothing saying so.
_CORPUS_KEYS = frozenset({"name", "tests", "shape"})

Entry = tuple[str, "str | None"]


def load_shapes() -> dict[int, Any]:
    """SHAPES from shapes.py, loaded by path: tools/ is not a package."""
    spec = importlib.util.spec_from_file_location("_shapes", HERE / "shapes.py")
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.SHAPES  # type: ignore[no-any-return]


def _corpus_line(path: Path, line: str, orders: dict[int, str | None]) -> Entry:
    raw = json.loads(line)
    if isinstance(raw, str):
        return raw, None
    if not (isinstance(raw, dict) and isinstance(raw.get("name"), str)):
        raise SystemExit(f"{path.name}: corpus line is neither a JSON string "
                         f"nor an object with a string 'name': {line!r}")
    if unknown := sorted(set(raw) - _CORPUS_KEYS):
        raise SystemExit(f"{path.name}: a corpus line has unknown key(s) "
                         f"{unknown}; expected only {sorted(_CORPUS_KEYS)}: "
                         f"{line!r}")
    tests = raw.get("tests")
    if tests is not None and not (isinstance(tests, list)
                                  and all(isinstance(t, str) for t in tests)):
        raise SystemExit(f"{path.name}: a corpus line's 'tests' must be a "
                         f"list of strings, not {tests!r}: {line!r}")
    shape = raw.get("shape")
    if shape is None:
        return raw["name"], None
    # bool is an int subclass and hash(True) == hash(1): unexcluded,
    # {"shape": true} would read the name under shape 1's order.
    if isinstance(shape, bool) or shape not in orders:
        raise SystemExit(f"{path.name}: a corpus line's 'shape' must name a "
                         f"shapes.py entry {sorted(orders)}, not {shape!r}: "
                         f"{line!r}")
    return raw["name"], orders[shape]


def corpus_entries(paths: list[Path] | None = None) -> list[Entry]:
    """Every distinct (name, order) in the corpora -- every
    corpus*.jsonl beside this file, or `paths` -- sorted. The same
    string tagged with two shapes is two entries, one per order."""
    orders = {k: s.order for k, s in load_shapes().items()}
    paths = paths or sorted(HERE.glob("corpus*.jsonl"))
    if not paths:
        raise SystemExit(f"no corpus files found in {HERE}")
    found: set[Entry] = set()
    for path in paths:
        lines = [ln for ln in path.read_text(encoding="utf-8").splitlines()
                 if ln.strip()]
        if not lines:
            raise SystemExit(f"{path.name} is empty")
        found.update(_corpus_line(path, ln, orders) for ln in lines)
    return sorted(found, key=lambda e: (e[0], e[1] or ""))


def row(name: str, order: str | None, v2: dict[str, Any] | None,
        facade: dict[str, str] | None) -> dict[str, Any]:
    """One snapshot line from one name's readings.

    `v2` is the 2.0 surface as {role: value, "_ambiguities": [...],
    "_initials": ...}; `facade` is HumanName's as {v1 field: value,
    "_initials": ...}, or None where it is not read (an order-bearing
    entry, whose facade is never consulted). Empty values are left
    out, so a reading that gains a field shows as one added key. With
    no v2 surface (a 1.4 baseline) the facade's reading IS the row,
    under role names; otherwise the facade is recorded only where it
    differs."""
    out: dict[str, Any] = {"name": name}
    if order:
        out["order"] = order
    if v2 is None:
        assert facade is not None
        out.update({f: v for f in V2_FIELDS if (v := facade[V1_FOR[f]])})
        if facade["_initials"]:
            out["initials"] = facade["_initials"]
        return out
    out.update({f: v for f in V2_FIELDS if (v := v2[f])})
    if v2["_ambiguities"]:
        out["ambiguities"] = list(v2["_ambiguities"])
    if v2["_initials"]:
        out["initials"] = v2["_initials"]
    if facade is not None:
        differs = {f: facade[V1_FOR[f]] for f in V2_FIELDS
                   if facade[V1_FOR[f]] != v2[f]}
        if facade["_initials"] != v2["_initials"]:
            differs["initials"] = facade["_initials"]
        if differs:
            out["facade"] = differs
    return out


def facade_view(r: dict[str, Any]) -> dict[str, Any]:
    """A row as the facade alone reads it, for comparing against a
    baseline that has no 2.0 surface."""
    facade = r.get("facade", {})
    out = {k: r[k] for k in ("name", "order") if k in r}
    for f in (*V2_FIELDS, "initials"):
        if v := facade.get(f, r.get(f, "")):
            out[f] = v
    return out


def read(entries: list[Entry]) -> list[dict[str, Any]]:
    """The tree's row for every entry."""
    import nameparser
    from nameparser import HumanName, Parser, Policy

    parsers: dict[str | None, Any] = {None: Parser()}
    rows = []
    for name, order in entries:
        if order not in parsers:
            parsers[order] = Parser(policy=Policy(name_order=getattr(nameparser, order)))
        p = parsers[order].parse(name)
        v2 = {f: getattr(p, f) or "" for f in V2_FIELDS}
        v2["_ambiguities"] = sorted({a.kind.name for a in p.ambiguities})
        v2["_initials"] = p.initials() or ""
        facade = None
        if order is None:
            hn = HumanName(name)
            facade = {k: v or "" for k, v in hn.as_dict().items() if k in V1_FIELDS}
            facade["_initials"] = hn.initials() or ""
        rows.append(row(name, order, v2, facade))
    return rows


def key(r: dict[str, Any]) -> tuple[str, str]:
    return r["name"], r.get("order", "")


def dump(rows: list[dict[str, Any]]) -> str:
    return "".join(json.dumps(r, ensure_ascii=False) + "\n" for r in rows)


def load(text: str) -> dict[tuple[str, str], dict[str, Any]]:
    return {key(r): r for r in map(json.loads, text.splitlines()) if r}


def _flat(r: dict[str, Any]) -> dict[str, str]:
    out = {k: ("|".join(v) if isinstance(v, list) else v)
           for k, v in r.items() if k not in ("name", "order", "facade")}
    out.update({f"facade.{k}": v for k, v in r.get("facade", {}).items()})
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
