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
--local SOURCE reads a local corpus (local_corpora.py) instead of the
committed ones, against a snapshot kept beside it in the cache, so a
change can be read against real names that are never committed:

    uv run python tools/differential/snapshot.py --local ctgov-officials --record --tree ../master-checkout
    uv run python tools/differential/snapshot.py --local ctgov-officials

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
REPO_ROOT = HERE.parents[1]
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


#: The corpus a release figure counts out (AGENTS.md, Release-log
#: claims): fictional CLDR renderings, not names anyone reported.
CLDR_CORPUS = HERE / "corpus_cldr.jsonl"


def only_in(path: Path, names: set[str]) -> set[str]:
    """The `names` that `path` holds and no other corpus beside it does."""
    orders = {k: s.order for k, s in load_shapes().items()}
    def held(p: Path) -> set[str]:
        return {_corpus_line(p, ln, orders)[0]
                for ln in p.read_text(encoding="utf-8").splitlines() if ln.strip()}
    others = set().union(*(held(p) for p in sorted(HERE.glob("corpus*.jsonl"))
                           if p != path))
    return (names & held(path)) - others


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


def check_source(module_file: str, root: Path = REPO_ROOT) -> Path:
    """Abort unless `module_file` is inside `root`'s source package.

    Run as a script, sys.path[0] is tools/differential/, which holds no
    nameparser, so a PYTHONPATH entry outranks the editable install and
    the tree side reads a released wheel while believing it read the
    checkout -- and a comparison of two wheels, or of a wheel with the
    snapshot it wrote, reports no moves. The test is "is this the
    SOURCE PACKAGE", not "is this under the root": the root also holds
    .venv/, build/lib/ and dist/, any of which can hold a wheel, and an
    ancestor of the checkout passes the weaker test while the import
    falls through to the checkout itself."""
    at = Path(module_file).resolve()
    source = (root / "nameparser").resolve()
    if not at.is_relative_to(source):
        raise SystemExit(
            f"imported nameparser from {at}, not from the source package "
            f"{source} -- so this run would read that module instead of "
            f"the tree it names. Unset PYTHONPATH; uninstall a "
            f"non-editable nameparser from the active environment; or, in "
            f"a git worktree, check that the editable install points at "
            f"THIS worktree rather than the main checkout. Aborted.")
    return at


def _local(source: str) -> tuple[Path, list[Path]]:
    """A local corpus's snapshot path and corpus file, with its
    attribution printed: a report on it carries its source and date."""
    if str(HERE) not in sys.path:
        sys.path.append(str(HERE))
    import local_corpora
    corpus = local_corpora.load(source)
    if corpus is None:
        raise SystemExit(f"{source} is not fetched: "
                         f"local_corpora.py fetch {source}")
    print(corpus.header())
    return (local_corpora.directory(source) / local_corpora.SNAPSHOT,
            [local_corpora.corpus_path(source)])


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--record", action="store_true", help="rewrite the snapshot")
    ap.add_argument("--since", metavar="REF",
                    help="compare against the snapshot committed at a git ref")
    ap.add_argument("--tree", metavar="PATH", help="read with another checkout")
    ap.add_argument("--out", type=Path,
                    help="where --record writes (default: snapshot.jsonl, "
                         "or the local corpus's own snapshot)")
    ap.add_argument("--local", metavar="SOURCE",
                    help="read a local corpus from the cache instead of the "
                         "committed corpora (local_corpora.py)")
    args = ap.parse_args(argv)
    if args.local and args.since:
        ap.error("--since reads a committed snapshot; a local corpus has none")
    snapshot, corpora = SNAPSHOT, None
    if args.local:
        snapshot, corpora = _local(args.local)
    out = args.out or snapshot
    root = Path(args.tree).resolve() if args.tree else REPO_ROOT
    if args.tree:
        sys.path.insert(0, str(root))
    rows = read(corpus_entries(corpora))
    import nameparser
    check_source(nameparser.__file__, root)
    if args.record:
        out.write_text(dump(rows), encoding="utf-8")
        print(f"recorded {len(rows)} readings to {out}")
        return 0
    if args.since:
        rel = SNAPSHOT.relative_to(Path(subprocess.check_output(
            ["git", "rev-parse", "--show-toplevel"], cwd=HERE, text=True).strip()))
        try:
            text = subprocess.check_output(
                ["git", "show", f"{args.since}:{rel}"], cwd=HERE, text=True)
        except subprocess.CalledProcessError:
            raise SystemExit(
                f"no {rel} at {args.since}: an unknown ref, or one from "
                f"before the snapshot existed. For a release tagged "
                f"before it, use `compare.py --baseline <version>`") from None
    elif not snapshot.exists():
        raise SystemExit(f"no snapshot at {snapshot}: record one first, "
                         f"with --record (and --tree for another checkout)")
    else:
        text = snapshot.read_text(encoding="utf-8")
    old, new = load(text), {key(r): r for r in rows}
    moves = grouped(old, new)
    print("\n".join(moves) or "matches the snapshot")
    if moves and args.local:
        moved = {k for k in set(old) | set(new) if old.get(k) != new.get(k)}
        print(f"\n{len(moved)} entries differ")
        return 1
    if moves:
        moved = {k for k in set(old) | set(new) if old.get(k) != new.get(k)}
        cldr = only_in(CLDR_CORPUS, {name for name, _ in moved})
        print(f"\n{len(moved)} entries differ, {len(cldr)} of their names "
              f"held only by {CLDR_CORPUS.name}")
    if moves and not args.since:
        print(f"\nif these moves are intended: {RECORD_COMMAND}")
    return 1 if moves else 0


if __name__ == "__main__":
    sys.exit(main())
