"""Every corpus name's current reading, committed -- a snapshot.

snapshot.jsonl holds one line per (name, order) across every
corpus*.jsonl beside this script: the seven role fields, the reported
ambiguity kinds, initials() and the two case-repair views on the 2.0
surface, plus the facade's v1 fields wherever they say something the
2.0 row does not. The case views are recorded only where they move
something: `capitalized` where capitalized() renders other than the
name as parsed, `capitalized_force` where capitalized(force=True)
renders other than capitalized() does (#826).
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

    uv run python tools/differential/snapshot.py --local ctgov-officials --base ../master-checkout

--base PATH reads the base checkout's readings from a kept baseline
(below), recording one in a child process where none is kept, and
compares this tree against them; it never reads or writes the shared
snapshot beside the corpus, so a session measuring while another
records cannot be handed that session's readings as its base. Without
--base a check compares against that shared snapshot, which whoever
last recorded decides:

    uv run python tools/differential/snapshot.py --local ctgov-officials --record --tree ../master-checkout
    uv run python tools/differential/snapshot.py --local ctgov-officials

A local snapshot does not read the facade: v1 compatibility is the
committed corpora's question, and the facade's parse was about half the
cost of a local reading (measured 2026-10-23, tools/differential/
README.md's "Local corpora"). --sample N reads a fixed 1-in-N sample of
a local corpus, chosen by a hash of the name so a sample recorded from
one tree and checked from another holds the same names, into a
snapshot of its own (snapshot.sample-N.jsonl). A local recording is
also kept, gzipped, under baselines/ beside the snapshot, keyed by the
corpus fetch, a hash of the files in the read tree's nameparser/, the
interpreter's minor version and the code that writes a row
(snapshot.py, corpus_build.py, shapes.py), so recording the same base
again copies it instead of parsing.

Any reading of PARALLEL_FLOOR entries or more, committed or local,
parses in --jobs worker processes (default: every CPU).

A corpus that loses names shows them as removed, so a truncated file
cannot pass for a clean run. compare.py builds its baseline rows with
row() too, so a released wheel's readings and the tree's are compared
in one shape.
"""
from __future__ import annotations

import argparse
import gzip
import hashlib
import importlib
import importlib.util
import json
import multiprocessing
import os
import shutil
import subprocess
import sys
import tempfile
import time
import warnings
import zlib
from collections import defaultdict
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path
from collections.abc import Callable, Sequence
from typing import TYPE_CHECKING, Any, TypeVar

if TYPE_CHECKING:
    from nameparser import ParsedName

HERE = Path(__file__).resolve().parent
# The shared corpus helpers, found as the corpus builders find them (see
# corpus_build's docstring for why the directory is appended).
if str(HERE) not in sys.path:
    sys.path.append(str(HERE))
from corpus_build import jsonl_line, jsonl_lines  # noqa: E402
REPO_ROOT = HERE.parents[1]
T = TypeVar("T")
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
        lines = jsonl_lines(path.read_text(encoding="utf-8"))
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
                for ln in jsonl_lines(p.read_text(encoding="utf-8"))}
    others = set().union(*(held(p) for p in sorted(HERE.glob("corpus*.jsonl"))
                           if p != path))
    return (names & held(path)) - others


def row(name: str, order: str | None, v2: dict[str, Any] | None,
        facade: dict[str, str] | None) -> dict[str, Any]:
    """One snapshot line from one name's readings.

    `v2` is the 2.0 surface as {role: value, "_ambiguities": [...],
    "_initials": ..., "_capitalized": ..., "_capitalized_force": ...},
    the case views as case_views() gives them; `facade` is HumanName's as {v1 field: value,
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
    if v2.get("_alternatives"):
        out["alternatives"] = list(v2["_alternatives"])
    if v2["_initials"]:
        out["initials"] = v2["_initials"]
    for view in CASE_VIEWS:
        if v2[f"_{view}"]:
            out[view] = v2[f"_{view}"]
    if facade is not None:
        differs = {f: facade[V1_FOR[f]] for f in V2_FIELDS
                   if facade[V1_FOR[f]] != v2[f]}
        if facade["_initials"] != v2["_initials"]:
            differs["initials"] = facade["_initials"]
        if differs:
            out["facade"] = differs
    return out


#: The case-repair views a row records, in the order case_views()
#: gives them. The facade's capitalize() is not read: it renders
#: through the same repair, so it differs only where its fields do.
CASE_VIEWS = ("capitalized", "capitalized_force")


def case_views(rendered: str, plain: str, forced: str) -> dict[str, str]:
    """The case views as a row records them: each only where it moves
    something -- capitalized() against the name as parsed, and
    capitalized(force=True) against capitalized() -- so a name the
    repair leaves alone records nothing. A view is the whole repaired
    name, so in a name repair does change, a role move that changes the
    rendering moves the view too, with no word changing case."""
    return {"_capitalized": plain if plain != rendered else "",
            "_capitalized_force": forced if forced != plain else ""}


def alternatives(p: ParsedName) -> list[str]:
    """The reading each of a parse's reports did not take (#752 phase
    2m, `Ambiguity.alternative`): its kind, the reading's kind, the
    field it names and its source, one string per report that carries
    one, in report order, so a report losing its alternative beside an
    identical one still moves the row (`DOE, JOHN MA JD` holds two);
    none from a tree before 2.7, which `--base` reads through this too.
    compare.py's worker holds a copy."""
    return [f"{a.kind.name}: {alt.kind.value} as {alt.role.value} "
            f"({alt.source.value})"
            for a in p.ambiguities
            if (alt := getattr(a, "alternative", None)) is not None]


#: The keys a row came to record after the snapshot existed, each with
#: the change that added it: a snapshot recorded before it carries none
#: of them, so a comparison against it leaves them out.
RECORDED_LATER = ((CASE_VIEWS, "#826"), (("alternatives",), "#752 phase 2m"))

#: The key of a snapshot's first line since #752 phase 2m, naming the
#: `RECORDED_LATER` keys the tree that recorded it could record, so a
#: comparison asks the snapshot what it recorded rather than inferring
#: it from whether a row happens to hold one: a 2.7 snapshot of names
#: no report reaches holds no alternative and still records them.
HEADER = "recorded"


def recorded_keys() -> tuple[str, ...]:
    """The `RECORDED_LATER` keys the imported nameparser records: the
    case views, which every 2.x tree renders, and the alternatives where
    its Ambiguity has the field (2.7)."""
    import dataclasses

    import nameparser
    fields = {f.name for f in dataclasses.fields(nameparser.Ambiguity)}
    return CASE_VIEWS + (("alternatives",) if "alternative" in fields
                         else ())


def recorded(text: str) -> frozenset[str] | None:
    """The keys a snapshot's header says it records, or None for a
    snapshot recorded before the header existed."""
    first = text.split("\n", 1)[0]
    if not first.strip():
        return None
    r = json.loads(first)
    return frozenset(r[HEADER]) if HEADER in r and "name" not in r else None


def unrecorded_views(old_recorded: frozenset[str] | None,
                     new_recorded: frozenset[str],
                     old: dict[tuple[str, str], dict[str, Any]],
                     new: dict[tuple[str, str], dict[str, Any]]
                     ) -> tuple[str, ...]:
    """The `RECORDED_LATER` keys one side did not record, dropped from
    both sides' rows in place, so a snapshot recorded before the change
    that added them (v2.5.0's for the case views, v2.6.0's for the
    alternatives, or a local snapshot) does not report every name they
    reach as moved: 910 of the 961 entries `--since v2.5.0` reported on
    2026-10-22 were the case views' keys appearing, not moves.

    `old_recorded` is the old snapshot's header (`recorded`). A
    snapshot with none predates the header, so it records no
    alternatives, and its case views are read off its rows: exact for
    those frozen files, v2.5.0's and earlier recording none, and
    v2.6.0's and every local snapshot since #826 recording each where
    it moves something, which some corpus name does."""
    dropped: tuple[str, ...] = ()
    for keys, _ in RECORDED_LATER:
        if old_recorded is not None:
            had = set(keys) <= old_recorded
        elif keys == CASE_VIEWS:
            had = any(v in r for r in old.values() for v in keys)
        else:
            had = False
        if had and set(keys) <= new_recorded:
            continue
        for rows in (old, new):
            for r in rows.values():
                for v in keys:
                    r.pop(v, None)
        dropped += keys
    return dropped


def facade_view(r: dict[str, Any]) -> dict[str, Any]:
    """A row as the facade alone reads it, for comparing against a
    baseline that has no 2.0 surface."""
    facade = r.get("facade", {})
    out = {k: r[k] for k in ("name", "order") if k in r}
    for f in (*V2_FIELDS, "initials"):
        if v := facade.get(f, r.get(f, "")):
            out[f] = v
    return out


#: Below this many items parallel() reads in-process even when given
#: jobs: a worker costs an interpreter start and a nameparser import.
PARALLEL_FLOOR = 5000


def read(entries: list[Entry], *, facade: bool = True,
         jobs: int = 1) -> list[dict[str, Any]]:
    """The tree's row for every entry, in the entries' order, read in
    `jobs` worker processes where there are enough (parallel). With
    `facade` false the v1 facade is not read and no row carries a
    `facade` key."""
    return parallel(_read_chunk, entries, jobs, facade, module="snapshot")


def parallel(chunk: Callable[..., tuple[str, list[T]]], items: Sequence[Any],
             jobs: int, *args: object, module: str) -> list[T]:
    """chunk(part, *args)'s results for every item, in the items' order.

    `chunk` is a module-level function returning the nameparser file its
    process imported beside its results. With `jobs` above 1 and at
    least PARALLEL_FLOOR items, contiguous chunks are handed to that many
    spawned worker processes, which inherit this process's sys.path (so
    a --tree checkout comes first there too), and a worker that imported
    nameparser from anywhere but where this process did aborts the run:
    the check_source trap in a place check_source cannot see. A worker
    unpickles `chunk` by the bare name of its `module`, which resolves
    there because HERE is on the inherited sys.path, as it does for a
    test that loaded the module by path under another name."""
    if jobs <= 1 or len(items) < PARALLEL_FLOOR:
        return chunk(items, *args)[1]
    import nameparser
    here = Path(nameparser.__file__).resolve()
    by_name = getattr(importlib.import_module(module), chunk.__name__)
    size = -(-len(items) // (jobs * 4))
    chunks = [items[i:i + size] for i in range(0, len(items), size)]
    results: list[T] = []
    with ProcessPoolExecutor(jobs, mp_context=multiprocessing.get_context("spawn")) as pool:
        for at, part in pool.map(by_name, chunks, *([a] * len(chunks) for a in args)):
            if Path(at).resolve() != here:
                raise SystemExit(
                    f"a worker imported nameparser from {at}, not {here}, "
                    f"so its results would be another tree's readings. Aborted.")
            results.extend(part)
    return results


def _read_chunk(entries: Sequence[Entry], facade: bool
                ) -> tuple[str, list[dict[str, Any]]]:
    """The nameparser this process imported, and its row for every
    entry; read()'s unit of work in a worker and out of one."""
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
        v2["_alternatives"] = alternatives(p)
        v2["_initials"] = p.initials() or ""
        v2.update(case_views(str(p), str(parsers[order].capitalized(p)),
                             str(parsers[order].capitalized(p, force=True))))
        v1 = None
        if facade and order is None:
            with warnings.catch_warnings():
                # the facade is read on purpose; 2.8's removal warning
                # (by message, so any other warning still surfaces)
                warnings.filterwarnings(
                    "ignore", message="HumanName is deprecated",
                    category=DeprecationWarning)
                hn = HumanName(name)
            v1 = {k: v or "" for k, v in hn.as_dict().items() if k in V1_FIELDS}
            v1["_initials"] = hn.initials() or ""
        rows.append(row(name, order, v2, v1))
    return nameparser.__file__, rows


def key(r: dict[str, Any]) -> tuple[str, str]:
    return r["name"], r.get("order", "")


def dump(rows: list[dict[str, Any]], keys: tuple[str, ...]) -> str:
    """The snapshot of `rows`, headed by the `RECORDED_LATER` keys the
    tree that read them records (`recorded_keys`)."""
    return jsonl_line({HEADER: list(keys)}) + "\n" + "".join(
        jsonl_line(r) + "\n" for r in rows)


def load(text: str) -> dict[tuple[str, str], dict[str, Any]]:
    return {key(r): r for r in map(json.loads, jsonl_lines(text))
            if r and "name" in r}


def row_count(text: str) -> int:
    """How many rows a snapshot's text holds, its header not one."""
    return text.count("\n") - (recorded(text) is not None)


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
        # A line break inside a name would put the rest of it flush left,
        # where measure.py's summary keeps lines; escaped, it stays here.
        label = (k[0].replace("\n", "\\n").replace("\r", "\\r")
                 + (f"  [{k[1]}]" if k[1] else ""))
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


def _local(source: str, sample: int | None
           ) -> tuple[Path, list[Path], dict[str, Any]]:
    """A local corpus's snapshot path (a sample's own, for --sample),
    its corpus file (checked by local_corpora.load against its sha256),
    and what names this fetch of it and the sample, with its attribution
    printed: a report on it carries its source and date."""
    import local_corpora
    corpus = local_corpora.require(source)
    print(corpus.header())
    fetch: dict[str, Any] = {"data_date": corpus.meta["data_date"],
                             "corpus_sha256": corpus.meta["corpus_sha256"]}
    snapshot = local_corpora.directory(source) / local_corpora.SNAPSHOT
    if sample is not None:
        fetch["sample"] = sample
        snapshot = snapshot.with_name(f"{snapshot.stem}.sample-{sample}{snapshot.suffix}")
    return snapshot, [local_corpora.corpus_path(source)], fetch


def sampled(entries: list[Entry], every: int) -> list[Entry]:
    """The entries a 1-in-`every` sample keeps, chosen by a hash of the
    name rather than at random: a sample recorded from one tree and
    checked from another holds the same names, and a name read under
    two orders stays whole."""
    return [e for e in entries
            if int.from_bytes(hashlib.blake2b(
                e[0].encode("utf-8", "surrogatepass"), digest_size=8).digest(),
                "big") % every == 0]


#: How many recorded baselines a local corpus keeps, whole or sampled
#: alike, the least recently recorded or reused dropped first. Sized for
#: four sessions measuring at once, each keeping a base and a head with
#: room for one more: at 4 (before --base) parallel sessions evicted
#: each other's bases (2026-10-25). The largest is FEC's, 249 MB plain
#: and 41.7 MB gzipped (2026-10-25), so ten cost about 420 MB for it and
#: about 1.2 GB across the eight local corpora (122 MB a reading).
BASELINES_KEPT = 10
#: A partial baseline older than this is a crashed write's, not a
#: running one's, and is deleted when a baseline is kept.
_PARTIAL_STALE_SECONDS = 86400


def _source_digest(root: Path) -> str:
    """A hash of every file under `root`'s nameparser/ as it is on disk,
    __pycache__ aside: what the import reads, so an uncommitted edit, a
    gitignored file, a sourceless module or a copy outside any checkout
    keys as itself. git's view of the tree was the first key and could
    name the wrong one: an ignored copy inside a checkout (build/lib)
    took the checkout's tree, and status shows neither ignored nor
    assume-unchanged files (#859's review)."""
    h = hashlib.sha256()
    package = root / "nameparser"
    files = []
    # os.walk follows a symlinked subpackage, as the import does;
    # Path.rglob does not descend into one.
    for at, dirs, names in os.walk(package, followlinks=True):
        dirs[:] = [d for d in dirs if d != "__pycache__"]
        files.extend(Path(at) / n for n in names)
    for path in sorted(files):
        if path.is_file():
            h.update(path.relative_to(package).as_posix().encode() + b"\0")
            h.update(path.read_bytes() + b"\0")
    return h.hexdigest()


def _baseline(snapshot: Path, fetch: dict[str, Any], digest: str) -> Path:
    """Where a recording of `fetch` from a package of `digest` is kept.
    The key holds what a reading depends on besides the names: the
    package's files, the interpreter's minor version (unicodedata moves
    between Python versions), and the code that decides what a row
    records and how its line is written."""
    tool = hashlib.sha256(b"".join(
        (HERE / f).read_bytes()
        for f in ("snapshot.py", "corpus_build.py", "shapes.py"))).hexdigest()[:12]
    sample = f"-sample-{fetch['sample']}" if "sample" in fetch else ""
    py = f"py{sys.version_info[0]}{sys.version_info[1]}"
    return (snapshot.parent / "baselines"
            / f"{fetch['corpus_sha256'][:12]}-{digest[:16]}-{py}-{tool}{sample}.jsonl.gz")


def _reused(baseline: Path, entries: int) -> str | None:
    """A kept baseline's text, or None where there is none to reuse. A
    damaged one -- unreadable, or holding another number of rows than
    the corpus has entries, as a write cut short would -- is deleted
    with a note, and the names are read instead."""
    try:
        with gzip.open(baseline, "rt", encoding="utf-8") as f:
            text = f.read()
    except FileNotFoundError:  # none kept, or another run pruned it
        return None
    except (OSError, EOFError, zlib.error, UnicodeDecodeError) as e:
        why = f"unreadable ({e})"
    else:
        if (rows := row_count(text)) == entries:
            return text
        why = f"{rows} rows for {entries} entries"
    print(f"deleted the kept baseline {baseline.name}: {why}; reading the names\n")
    baseline.unlink(missing_ok=True)  # another run may have found it too
    return None


def _keep_baseline(path: Path, text: str) -> None:
    """Keep `text` at `path`, written whole and synced before it takes
    the name, then drop the least recently used baselines and stale
    partial writes. A failure is reported, not raised: the snapshot it
    would have saved recording again is already written."""
    try:
        path.parent.mkdir(exist_ok=True)
        partial = path.with_name(f"{path.name}.{os.getpid()}.partial")
        with open(partial, "wb") as raw:
            # No file name or time in the header: the partial's name is
            # not the baseline's, and identical readings give equal bytes.
            with gzip.GzipFile(filename="", fileobj=raw, mode="wb",
                               compresslevel=1, mtime=0) as f:
                f.write(text.encode("utf-8"))
            raw.flush()
            os.fsync(raw.fileno())
        partial.replace(path)
    except OSError as e:
        print(f"the snapshot is recorded, but its baseline was not kept: {e}")
        return
    _prune(path.parent)


def _mtime(path: Path) -> float | None:
    try:
        return path.stat().st_mtime
    except FileNotFoundError:  # another run pruned it meanwhile
        return None


def _prune(folder: Path, pattern: str = "*.jsonl.gz") -> None:
    """Drop all but the BASELINES_KEPT most recently used `pattern`
    files, and partial writes old enough to be a crashed run's, a base's
    scratch folder (scratch()) among them. A file another run removed
    first is skipped, not reported."""
    stale = time.time() - _PARTIAL_STALE_SECONDS
    kept = sorted((m, p) for p in folder.glob(pattern)
                  if (m := _mtime(p)) is not None)
    old = [p for _, p in kept[:-BASELINES_KEPT]]
    old += [p for glob in ("*.partial", "*.part") for p in folder.glob(glob)
            if (m := _mtime(p)) is not None and m < stale]
    for p in old:
        if p.is_dir():
            shutil.rmtree(p, ignore_errors=True)
        else:
            p.unlink(missing_ok=True)


def scratch(folder: Path) -> Path:
    """A folder of this run's own for a child's recording, inside the
    kept records' `folder`: unique, so two sessions recording the same
    base at once never share a file, and named as a partial write, so
    _prune sweeps one a killed run left behind."""
    folder.mkdir(parents=True, exist_ok=True)
    return Path(tempfile.mkdtemp(prefix=".base-", suffix=".partial", dir=folder))


def _fetch_record(snapshot: Path) -> Path:
    """Beside a local snapshot: the fetch of the corpus it was recorded
    from. A corpus fetched again holds other names, and compared with a
    snapshot of the old fetch every name the registry gained or lost
    would read as a move of the parser's."""
    return snapshot.with_name(snapshot.name + ".source.json")


def _check_fetch(snapshot: Path, fetch: dict[str, Any], source: str) -> None:
    """Refuse a local snapshot recorded from another fetch of its corpus,
    or with no readable record of its fetch, before reading anything."""
    try:
        recorded = json.loads(_fetch_record(snapshot).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        recorded = {}
    if not isinstance(recorded, dict):
        recorded = {}
    if recorded.get("corpus_sha256") != fetch["corpus_sha256"]:
        raise SystemExit(
            f"{snapshot} was recorded from another fetch of {source} (data "
            f"as of {recorded.get('data_date', 'unknown')}; the corpus now "
            f"is {fetch['data_date']}), so it would report the names the "
            f"source gained and lost as moves. Record it again from the "
            f"base checkout: snapshot.py --local {source} --record "
            f"--tree <base checkout>; or, where another session may be "
            f"measuring, check against a base you name instead: "
            f"snapshot.py --local {source} --base <base checkout>")
    if recorded.get("sample") != fetch.get("sample"):
        raise SystemExit(
            f"{snapshot} was recorded from "
            f"{_describe_sample(recorded.get('sample'))} of {source}, and "
            f"this run reads {_describe_sample(fetch.get('sample'))}: every "
            f"name in one and not the other would read as a move")


def _describe_sample(sample: object) -> str:
    return "the whole corpus" if sample is None else f"a 1-in-{sample} sample"


def base_root(path: str, head: Path) -> Path:
    """--base's checkout, resolved: refused where it holds no nameparser
    package, whose digest would key an empty tree, or where it is the
    tree being read, which would compare a tree with itself and report
    no moves whatever the change."""
    root = Path(path).resolve()
    if not (root / "nameparser" / "__init__.py").is_file():
        raise SystemExit(f"--base {path}: no nameparser package at "
                         f"{root / 'nameparser'}; name a checkout")
    if root == head:
        raise SystemExit(f"--base {path} is the tree being read ({head}): a "
                         f"tree compared with itself reports no moves. Name "
                         f"the base checkout, or pass --tree for the other side")
    return root


def head_line(root: Path, base: Path) -> str:
    """Which tree was read against the base, by its package's digest,
    taken after the read so that it covers what the import saw. Two
    equal digests are said outright: a check that cannot move is a
    clean run's look-alike."""
    head = _source_digest(root)
    if head == _source_digest(base):
        return (f"head: {root} holds a nameparser/ byte-identical to the "
                f"base's ({head[:16]}), so no reading can move\n")
    return f"head: {root}, nameparser/ {head[:16]}\n"


def child_env() -> dict[str, str]:
    """A child's environment with the import-path overrides stripped, as
    compare.py's worker has it: a PYTHONPATH entry would outrank the
    --tree the child is handed (check_source then aborts it)."""
    return {k: v for k, v in os.environ.items()
            if k not in ("PYTHONPATH", "PYTHONHOME")}


def _record_base(root: Path, source: str, sample: int | None, jobs: int,
                 out: Path) -> None:
    """`root`'s readings of `source` recorded to `out` in a child process
    (one process imports one nameparser), which keeps them as a baseline
    and refuses a package other than `root`'s, as --record --tree does."""
    command = [sys.executable, str(HERE / "snapshot.py"), "--local", source,
               "--record", "--tree", str(root), "--out", str(out),
               "--jobs", str(jobs)]
    if sample is not None:
        command += ["--sample", str(sample)]
    done = subprocess.run(command, env=child_env(), capture_output=True, text=True)
    if done.returncode:
        raise SystemExit(f"recording the base {root} failed:\n{done.stdout}{done.stderr}")


def _base_text(root: Path, snapshot: Path, fetch: dict[str, Any], source: str,
               sample: int | None, entries: int, jobs: int) -> str:
    """The base checkout's readings, from the baseline kept for its
    package's digest, or recorded into one now, and a line saying which
    base was read. Never the shared snapshot: that is whoever recorded
    last, and a sibling session's record would pass for this base."""
    digest = _source_digest(root)
    baseline = _baseline(snapshot, fetch, digest)
    if (text := _reused(baseline, entries)) is not None:
        try:
            os.utime(baseline)
        except FileNotFoundError:  # another run pruned it meanwhile
            pass
        how = f"reused the kept baseline {baseline.name}"
    else:
        at = scratch(baseline.parent)
        try:
            _record_base(root, source, sample, jobs, at / "base.jsonl")
            text = (at / "base.jsonl").read_text(encoding="utf-8")
        finally:
            shutil.rmtree(at, ignore_errors=True)
        if _source_digest(root) != digest:
            raise SystemExit(f"{root / 'nameparser'} changed while it was read, "
                             f"so its readings may be half old and half new; "
                             f"run again")
        how = "recorded it now"
    print(f"base: {root}, nameparser/ {digest[:16]}; {how}\n")
    return text


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--record", action="store_true", help="rewrite the snapshot")
    ap.add_argument("--since", metavar="REF",
                    help="compare against the snapshot committed at a git ref")
    ap.add_argument("--tree", metavar="PATH", help="read with another checkout")
    ap.add_argument("--base", metavar="PATH",
                    help="with --local: compare against the readings of this "
                         "checkout, kept by its package's digest, instead of "
                         "the shared snapshot")
    ap.add_argument("--out", type=Path,
                    help="where --record writes (default: snapshot.jsonl, "
                         "or the local corpus's own snapshot)")
    ap.add_argument("--local", metavar="SOURCE",
                    help="read a local corpus from the cache instead of the "
                         "committed corpora (local_corpora.py)")
    ap.add_argument("--sample", type=int, metavar="N",
                    help="with --local: read a fixed 1-in-N sample of the "
                         "corpus, against a snapshot of the same sample")
    ap.add_argument("--jobs", type=int, metavar="N", default=os.cpu_count() or 1,
                    help="parse in N worker processes (default: every CPU)")
    args = ap.parse_args(argv)
    if args.local and args.since:
        ap.error("--since reads a committed snapshot; a local corpus has none")
    if args.sample is not None and not args.local:
        ap.error("--sample reads a local corpus; the committed snapshot is whole")
    if args.sample is not None and args.sample < 2:
        ap.error("--sample N keeps 1 name in N, so N must be 2 or more")
    if args.base and not args.local:
        ap.error("--base reads a local corpus; for the committed corpora, "
                 "--since compares against a ref")
    if args.base and (args.record or args.out):
        ap.error("--base compares and records nothing but its kept baseline; "
                 "drop --record and --out")
    snapshot, corpora, fetch = SNAPSHOT, None, None
    if args.local:
        snapshot, corpora, fetch = _local(args.local, args.sample)
    out = args.out or snapshot
    root = Path(args.tree).resolve() if args.tree else REPO_ROOT
    base = base_root(args.base, root) if args.base else None
    if not (args.record or args.since or base or snapshot.exists()):
        raise SystemExit(f"no snapshot at {snapshot}: record one first, "
                         f"with --record (and --tree for another checkout)")
    if fetch is not None and not (args.record or base):
        _check_fetch(snapshot, fetch, args.local)
    entries = corpus_entries(corpora)
    if args.sample is not None:
        whole, entries = len(entries), sampled(entries, args.sample)
        print(f"a 1-in-{args.sample} sample: {len(entries)} of {whole} entries\n")
    baseline = digest = None
    if fetch is not None and args.record:
        digest = _source_digest(root)
        baseline = _baseline(snapshot, fetch, digest)
        if (text := _reused(baseline, len(entries))) is not None:
            out.write_text(text, encoding="utf-8")
            _fetch_record(out).write_text(json.dumps(fetch), encoding="utf-8")
            try:
                os.utime(baseline)
            except FileNotFoundError:  # another run pruned it meanwhile
                pass
            print(f"recorded {len(entries)} readings to {out}, copied from "
                  f"{baseline.name}: this nameparser/ was read from this "
                  f"fetch before")
            return 0
    if args.tree:
        sys.path.insert(0, str(root))
    based = None
    if base is not None:
        assert fetch is not None
        based = _base_text(base, snapshot, fetch, args.local, args.sample,
                           len(entries), args.jobs)
    rows = read(entries, facade=not args.local, jobs=args.jobs)
    import nameparser
    check_source(nameparser.__file__, root)
    if base is not None:
        print(head_line(root, base))
    if args.record:
        text = dump(rows, recorded_keys())
        out.write_text(text, encoding="utf-8")
        if fetch is not None:
            _fetch_record(out).write_text(json.dumps(fetch), encoding="utf-8")
            # Keyed before the read: a package that changed during it
            # may have been read half old and half new, so it keeps none.
            if baseline is not None and _source_digest(root) == digest:
                _keep_baseline(baseline, text)
            elif baseline is not None:
                print(f"{root / 'nameparser'} changed while it was read, so "
                      f"no baseline was kept; record again")
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
    elif based is not None:
        text = based
    else:
        text = snapshot.read_text(encoding="utf-8")
    old, new = load(text), {key(r): r for r in rows}
    if args.local and any("facade" in r for r in old.values()):
        for r in old.values():
            r.pop("facade", None)
        print("not compared: facade -- the snapshot read against was "
              "recorded when a local reading still read the facade\n")
    if dropped := unrecorded_views(recorded(text),
                                   frozenset(recorded_keys()), old, new):
        print(f"not compared: {', '.join(dropped)} -- one side of the "
              f"comparison predates "
              f"{' and '.join(c for k, c in RECORDED_LATER if k[0] in dropped)}"
              # a release records the case views from 2.6.0, so compare.py
              # can read them for an older tag; none records the
              # alternatives until 2.7 ships
              + ("; compare.py --baseline compares the case views"
                 if CASE_VIEWS[0] in dropped else "") + "\n")
    moves = grouped(old, new)
    print("\n".join(moves) or ("matches the base" if base else "matches the snapshot"))
    if not moves:
        return 0
    moved = {k for k in set(old) | set(new) if old.get(k) != new.get(k)}
    if base is not None:
        print(f"\n{len(moved)} entries differ from the base {base}")
        return 1
    if args.local:
        print(f"\n{len(moved)} entries differ from the snapshot recorded "
              f"from this fetch, which whoever recorded last chose. To make "
              f"another tree the baseline: snapshot.py --local {args.local} "
              f"--record --tree <checkout>; to check against a base you "
              f"name instead: snapshot.py --local {args.local} --base <checkout>")
        return 1
    cldr = only_in(CLDR_CORPUS, {name for name, _ in moved})
    print(f"\n{len(moved)} entries differ, {len(cldr)} of their names "
          f"held only by {CLDR_CORPUS.name}")
    if not args.since:
        print(f"\nif these moves are intended: {RECORD_COMMAND}")
    return 1


if __name__ == "__main__":
    sys.exit(main())
