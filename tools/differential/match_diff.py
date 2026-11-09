"""List every name pair a change moves in name matching, against a base checkout.

Parsing has snapshot.jsonl to say which names a change moves; matching
(`Parser.matching()`) had nothing, so each change to `_match.py` wrote
a throwaway script to show `check` and `keys` did not move (#1278). This
is that script kept: one fixed draw of name pairs, one sweep of
settings, and every pair whose result or keys differ between two trees.

    uv run python tools/differential/match_diff.py --base <base checkout>
    uv run python tools/differential/match_diff.py --base <base> --sample 10
    uv run python tools/differential/match_diff.py            # head alone

THE PAIRS, drawn once by the parent from its own checkout and handed to
both sides, so the base and the head read the same pairs whatever their
tests hold: every pair of names a row of tests/v2/test_match.py writes,
a seeded draw of pairings of those names, and from $NAMEPARSER_TOOLS_CACHE
(~/.cache/nameparser-tools) where present: jrc-names spellings of one
entity and of different entities sharing a last word (mostly different
people, where a key-guarantee miss would show), tse-donors' filed and
registry names (both local corpora, `local_corpora.py fetch`), and
PatentsView inventors' spellings of themselves, read from the raw table
PatentsView publishes (PATENTSVIEW_RAW), which the patentsview-inventors
fetch reads and does not keep. A source not present is left out with a
note saying how to get it; one present but unreadable stops the run. Each
source draws with a generator of its own seeded by SEED and its name, so
for the same sources present the pairs are the same, and the report
counts them by source.

THE SETTINGS (SETTINGS): the default accept set, each opt-in added
alone, every opt-in, each default outcome but `same` taken out, the
other-readings switch on with the default and with every opt-in, and the
default and every opt-in under `locales.ES`.

THE REPORT: for each pair and setting, the `MatchResult` and each
side's keys. With --base, every pair that moved, grouped by what moved
(a role's outcome, the verdict, the cross-role matches, the reading
used, the keys), with examples; a refactor expects none, and the exit
status is 1 where any moved. Either way, every pair the head reads
consistent that shares no key, the guarantee `keys` gives.

A base's results are kept in the cache under a hash of its package's
files, the pairs, the interpreter's minor version and this tool's code
with the snapshot.py and corpus_build.py it reads (snapshot.py's kept
baselines), so a
second run reads only the head. Nothing here is committed: the corpora
are cache-only, and jrc-names' licence keeps even a reading out of the
tree.
"""
from __future__ import annotations

import argparse
import ast
import csv
import hashlib
import io
import json
import os
import random
import shutil
import subprocess
import sys
import zipfile
from collections import Counter, defaultdict
from collections.abc import Iterator, Sequence
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from nameparser import Matching, MatchResult

HERE = Path(__file__).resolve().parent
if str(HERE) not in sys.path:
    sys.path.append(str(HERE))
import snapshot  # noqa: E402
from corpus_build import jsonl_line, jsonl_lines  # noqa: E402

REPO_ROOT = HERE.parents[1]
#: The seed of every draw, each source's generator seeded by it and the
#: source's name.
SEED = 1278
#: How many pairs each draw takes at most.
GRID_PAIRS = 15_000
CORPUS_PAIRS = 4_000
#: PatentsView's raw rows read, of its 24 million: 400,000 held 27,594
#: inventors with two spellings or more on 2026-11-08.
PATENTSVIEW_LINES = 400_000
#: Where PatentsView's raw table is read from: the file
#: `local_patentsview.PV_RAW` of its pinned release, put there by hand
#: (the fetch of patentsview-inventors downloads it, reads it, and keeps
#: only its extract, which holds no inventor's id), and checked against
#: the size `local_patentsview.PV_FILES` pins.
PATENTSVIEW_RAW = Path("patentsview-probe") / "g_inventor_not_disambiguated.tsv.zip"
PATENTSVIEW_MEMBER = "g_inventor_not_disambiguated.tsv"
OPT_INS = ("familiar-form", "family-initial", "given-one-side",
           "hyphenated-part", "across-roles")
Setting = tuple[str, tuple[str, ...], tuple[str, ...], bool, "str | None"]
#: Each setting: its label, the outcomes added to and taken from the
#: default, whether other readings are searched, and the locale pack.
SETTINGS: tuple[Setting, ...] = (
    ("default", (), (), False, None),
    *((f"+{o}", (o,), (), False, None) for o in OPT_INS),
    ("all", OPT_INS, (), False, None),
    *((f"-{o}", (), (o,), False, None) for o in (
        "folded", "listed-spelling", "particles-aside", "part-of-other",
        "initial", "initials-agree", "one-side", "generation-one-side",
        "noted")),
    ("default+other", (), (), True, None),
    ("all+other", OPT_INS, (), True, None),
    ("es", (), (), False, "ES"),
    ("es+all", OPT_INS, (), False, "ES"),
)


def cache_dir() -> Path:
    return Path(os.environ.get(
        "NAMEPARSER_TOOLS_CACHE", Path.home() / ".cache" / "nameparser-tools"))


# -- the pairs ---------------------------------------------------------------

def test_pairs(path: Path) -> list[tuple[str, str]]:
    """The pairs of names a test module writes: every tuple whose first
    two members are strings, one of them holding a space or a comma (a
    name, not an outcome or a role), in source order, each once."""
    pairs = []
    for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
        if not isinstance(node, ast.Tuple) or len(node.elts) < 2:
            continue
        a, b = node.elts[:2]
        if not (isinstance(a, ast.Constant) and isinstance(a.value, str)
                and isinstance(b, ast.Constant) and isinstance(b.value, str)):
            continue
        if any(" " in s or "," in s for s in (a.value, b.value)):
            pairs.append((a.value, b.value))
    return list(dict.fromkeys(pairs))


def _jrc(rng: random.Random) -> Iterator[tuple[str, str, str]]:
    path = cache_dir() / "local" / "jrc-names" / "raw.jsonl"
    entities: dict[str, list[str]] = {}
    for line in jsonl_lines(path.read_text(encoding="utf-8")):
        row = json.loads(line)
        if row.get("script") == "Latin":
            names = entities.setdefault(str(row["entity"]), [])
            if row["name"] not in names:
                names.append(row["name"])
    multi = sorted((e for e in entities if len(entities[e]) > 1), key=int)
    for _ in range(min(CORPUS_PAIRS, len(multi))):
        a, b = rng.sample(entities[rng.choice(multi)], 2)
        yield ("jrc-names, one entity", a, b)
    by_last: dict[str, list[str]] = {}
    for e in sorted(entities, key=int):
        for n in entities[e]:
            if n.split():
                by_last.setdefault(n.split()[-1].casefold(), []).append(n)
    lasts = sorted(k for k, v in by_last.items() if len(v) > 1)
    for _ in range(min(CORPUS_PAIRS, len(lasts))):
        a, b = rng.sample(by_last[rng.choice(lasts)], 2)
        yield ("jrc-names, one last word", a, b)


def _tse(rng: random.Random) -> Iterator[tuple[str, str, str]]:
    path = cache_dir() / "local" / "tse-donors" / "raw.jsonl"
    seen: set[tuple[str, str]] = set()
    for line in jsonl_lines(path.read_text(encoding="utf-8")):
        row = json.loads(line)
        pair = (row["name"], row["registry"])
        if pair[0] != pair[1] and pair not in seen:
            seen.add(pair)
            yield ("tse-donors", *pair)
            if len(seen) >= CORPUS_PAIRS:
                return


def _patentsview(rng: random.Random) -> Iterator[tuple[str, str, str]]:
    import local_patentsview
    path = cache_dir() / PATENTSVIEW_RAW
    size = local_patentsview.PV_FILES[local_patentsview.PV_RAW][0]
    if (got := path.stat().st_size) != size:
        raise ValueError(f"{path} is {got:,} bytes, not the pinned release's "
                         f"{size:,}")
    spellings: dict[str, set[str]] = {}
    with zipfile.ZipFile(path) as z:
        with z.open(PATENTSVIEW_MEMBER) as raw:
            text = io.TextIOWrapper(raw, encoding="utf-8", newline="")
            reader = csv.DictReader(text, delimiter="\t")
            for n, row in enumerate(reader):
                if n >= PATENTSVIEW_LINES:
                    break
                if None in row.values() or None in row:
                    raise ValueError(f"{path} row {n + 2} is not as wide as "
                                     f"its header: {row!r}")
                name = " ".join(filter(None, (
                    row["raw_inventor_name_first"].strip(),
                    row["raw_inventor_name_last"].strip())))
                if name:
                    spellings.setdefault(row["inventor_id"], set()).add(name)
    ids = sorted(i for i in spellings if len(spellings[i]) > 1)
    for i in rng.sample(ids, min(CORPUS_PAIRS, len(ids))):
        a, b = sorted(spellings[i])[:2]
        yield ("PatentsView, one inventor", a, b)


#: Each source, its draw and how to get it where it is not present.
CORPORA = (
    ("jrc-names", _jrc,
     "uv run python tools/differential/local_corpora.py fetch jrc-names"),
    ("tse-donors", _tse,
     "uv run python tools/differential/local_corpora.py fetch tse-donors"),
    ("patentsview", _patentsview,
     f"put PatentsView's {PATENTSVIEW_RAW.name} (release "
     f"2025-12-31, the USPTO Open Data Portal's PVGPATDIS product) at "
     f"$NAMEPARSER_TOOLS_CACHE/{PATENTSVIEW_RAW}"),
)


def draw_pairs(tests: Path) -> tuple[list[tuple[str, str, str]], list[str]]:
    """Every pair, each with its source, and a note for each source not
    present. Each draw has a generator of its own, seeded by SEED and
    its name, so a source absent moves no other source's pairs. Raises
    SystemExit naming the source where one present cannot be read: a
    source that changed its columns or was cut is a broken measurement,
    not a missing one."""
    written = test_pairs(tests)
    pairs = [("tests, as written", a, b) for a, b in written]
    names = sorted({n for p in written for n in p if len(n) < 60})
    grid = [(a, b) for a in names for b in names if a != b]
    random.Random(f"{SEED}-tests").shuffle(grid)
    pairs += [("tests, paired", a, b) for a, b in grid[:GRID_PAIRS]]
    notes = []
    for name, draw, how in CORPORA:
        try:
            pairs += list(draw(random.Random(f"{SEED}-{name}")))
        except FileNotFoundError as e:
            notes.append(f"{name}: not present ({e.filename}); {how}")
        except (OSError, KeyError, ValueError, zipfile.BadZipFile) as e:
            raise SystemExit(f"{name}: present but unreadable "
                             f"({type(e).__name__}: {e}); fetch it again "
                             f"({how}) or move it aside") from e
    return pairs, notes


# -- one side's results ------------------------------------------------------

def _matcher(setting: Setting) -> Matching:
    from nameparser import Parser, locales, parser_for
    _, added, removed, other, pack = setting
    parser = Parser() if pack is None else parser_for(getattr(locales, pack))
    accept = (parser.matching().accept | set(added)) - set(removed)
    return parser.matching(accept, other_readings=other)


def _result(r: MatchResult) -> dict[str, Any]:
    return {
        "consistent": r.consistent,
        "roles": [[m.role.value, m.outcome.value, m.left, m.right, m.more.value]
                  for m in r.roles],
        "across": [[c.left_role.value, c.right_role.value, c.outcome.value,
                    c.left, c.right] for c in r.across],
        "alternatives": [None if a is None else [a.kind.value, a.detail]
                         for a in (r.left_alternative, r.right_alternative)],
    }


def _read_setting(job: tuple[int, list[tuple[str, str]]]) -> list[str]:
    index, pairs = job
    setting = SETTINGS[index]
    m = _matcher(setting)
    return [jsonl_line({
        "setting": setting[0], "pair": i, **_result(m.check(a, b)),
        "keys": [sorted(m.keys(a)), sorted(m.keys(b))]})
        for i, (a, b) in enumerate(pairs)]


def read_side(pairs: list[tuple[str, str]], jobs: int) -> list[str]:
    """Every setting's lines over `pairs`, in SETTINGS order."""
    work = [(i, pairs) for i in range(len(SETTINGS))]
    if jobs <= 1:
        return [line for job in work for line in _read_setting(job)]
    with ProcessPoolExecutor(jobs) as pool:
        return [line for lines in pool.map(_read_setting, work)
                for line in lines]


def worker(tree: Path, pairs_file: Path, out: Path, jobs: int) -> None:
    """A child's side: `tree`'s nameparser, checked to be what was
    imported, over the pairs the parent wrote."""
    sys.path.insert(0, str(tree))
    import nameparser
    snapshot.check_source(nameparser.__file__, tree)
    pairs = [(row[1], row[2]) for row in map(json.loads, jsonl_lines(
        pairs_file.read_text(encoding="utf-8")))]
    lines = read_side(pairs, jobs)
    out.write_text("".join(f"{line}\n" for line in lines), encoding="utf-8")


def _run_side(tree: Path, pairs_file: Path, out: Path, jobs: int) -> str:
    command = [sys.executable, str(Path(__file__).resolve()), "--worker",
               "--tree", str(tree), "--pairs", str(pairs_file),
               "--out", str(out), "--jobs", str(jobs)]
    done = subprocess.run(command, env=snapshot.child_env(),
                          capture_output=True, text=True)
    if done.returncode:
        raise SystemExit(f"reading {tree} failed:\n{done.stdout}{done.stderr}")
    return out.read_text(encoding="utf-8")


def _kept_path(pairs_text: str, digest: str) -> Path:
    """Where a base's results are kept: keyed by its package's files, the
    pairs, the interpreter's minor version, and the code that writes a
    row (this tool, snapshot.py and corpus_build.py)."""
    tool = hashlib.sha256(b"".join(
        (HERE / f).read_bytes()
        for f in ("match_diff.py", "snapshot.py", "corpus_build.py"))
    ).hexdigest()[:12]
    pairs = hashlib.sha256(pairs_text.encode("utf-8")).hexdigest()[:12]
    py = f"py{sys.version_info[0]}{sys.version_info[1]}"
    return (cache_dir() / "match-diff"
            / f"{pairs}-{digest[:16]}-{py}-{tool}.jsonl.gz")


def base_side(root: Path, pairs_file: Path, pairs_text: str, rows: int,
              jobs: int) -> str:
    """The base's lines, reused from the results kept for its package's
    digest, or read now in a child and kept; refused where its package
    changed while it was read."""
    digest = snapshot._source_digest(root)
    kept = _kept_path(pairs_text, digest)
    if (text := snapshot._reused(kept, rows)) is not None:
        try:
            os.utime(kept)
        except FileNotFoundError:  # another run pruned it meanwhile
            pass
        print(f"base: {root}, nameparser/ {digest[:16]}; reused its kept results")
        return text
    at = snapshot.scratch(kept.parent)
    try:
        text = _run_side(root, pairs_file, at / "base.jsonl", jobs)
    finally:
        shutil.rmtree(at, ignore_errors=True)
    if snapshot._source_digest(root) != digest:
        raise SystemExit(f"{root / 'nameparser'} changed while it was read; "
                         f"run again")
    snapshot._keep_baseline(kept, text)
    print(f"base: {root}, nameparser/ {digest[:16]}; read it now")
    return text


# -- the report --------------------------------------------------------------

def what_moved(old: dict[str, Any], new: dict[str, Any]) -> list[str]:
    """What differs between two rows of one pair and setting, never
    nothing where the rows differ."""
    moved = []
    if old["consistent"] != new["consistent"]:
        moved.append(f"verdict {old['consistent']} -> {new['consistent']}")
    if [r[0] for r in old["roles"]] != [r[0] for r in new["roles"]]:
        moved.append("roles listed")
    else:
        for (role, o, *rest), (_, n, *rest2) in zip(old["roles"], new["roles"]):
            if o != n:
                moved.append(f"{role}: {o} -> {n}")
            elif rest != rest2:
                moved.append(f"{role}: texts or side")
    if old["across"] != new["across"]:
        moved.append("across-roles matches")
    if old["alternatives"] != new["alternatives"]:
        moved.append("reading used")
    if old["keys"] != new["keys"]:
        moved.append("keys")
    if not moved and old != new:
        # a part this function does not name: never a move under no heading
        moved.append("other")
    return moved


def key_misses(lines: Sequence[str]) -> list[dict[str, Any]]:
    """The rows read consistent whose two names share no key."""
    rows = (json.loads(line) for line in lines)
    return [r for r in rows
            if r["consistent"] and not set(r["keys"][0]) & set(r["keys"][1])]


def report(pairs: Sequence[tuple[str, str, str]], head: Sequence[str],
           base: Sequence[str] | None, examples: int = 5) -> int:
    """Print the key misses and, given a base, the moves; return the
    number of rows that moved."""
    def show(r: dict[str, Any]) -> str:
        _, a, b = pairs[r["pair"]]
        return f"    [{r['setting']}] {a!r} / {b!r}"

    misses = key_misses(head)
    print(f"\nkey guarantee: {len(misses)} consistent pairs share no key"
          + (":" if misses else ""))
    for r in misses[:examples]:
        print(show(r))
    if base is None:
        return 0
    if len(base) != len(head):
        raise SystemExit(f"the base holds {len(base)} rows and the head "
                         f"{len(head)}: not the same pairs and settings")
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    moved = 0
    by_setting: Counter[str] = Counter()
    for old_line, new_line in zip(base, head):
        if old_line == new_line:
            continue
        old, new = json.loads(old_line), json.loads(new_line)
        moved += 1
        by_setting[new["setting"]] += 1
        for what in what_moved(old, new):
            grouped[what].append(new)
    print(f"\n{moved} of {len(head)} rows moved"
          + (", by setting: " + ", ".join(
              f"{s} {n}" for s, n in sorted(by_setting.items()))
             if moved else ""))
    for what, rows in sorted(grouped.items(), key=lambda kv: (-len(kv[1]), kv[0])):
        print(f"\n  {what}: {len(rows)}")
        for r in rows[:examples]:
            print(show(r))
    return moved


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--base", metavar="PATH",
                    help="compare against the results of this checkout")
    ap.add_argument("--tree", metavar="PATH",
                    help="read with another checkout (the head)")
    ap.add_argument("--sample", type=int, metavar="N",
                    help="read every Nth pair, for a quick run")
    ap.add_argument("--jobs", type=int, default=os.cpu_count() or 1)
    ap.add_argument("--examples", type=int, default=5,
                    help="pairs shown for each kind of move")
    ap.add_argument("--worker", action="store_true", help=argparse.SUPPRESS)
    ap.add_argument("--pairs", type=Path, help=argparse.SUPPRESS)
    ap.add_argument("--out", type=Path, help=argparse.SUPPRESS)
    args = ap.parse_args(argv)
    head_root = Path(args.tree).resolve() if args.tree else REPO_ROOT
    if args.worker:
        worker(head_root, args.pairs, args.out, args.jobs)
        return 0
    base_root = (snapshot.base_root(args.base, head_root)
                 if args.base else None)
    pairs, notes = draw_pairs(REPO_ROOT / "tests" / "v2" / "test_match.py")
    if args.sample:
        pairs = pairs[::args.sample]
    for note in notes:
        print(note)
    sources = ", ".join(f"{s} {n}" for s, n in Counter(p[0] for p in pairs).items())
    print(f"{len(pairs)} pairs ({sources}) x {len(SETTINGS)} settings")
    pairs_text = "".join(f"{jsonl_line(list(p))}\n" for p in pairs)
    work = snapshot.scratch(cache_dir() / "match-diff")
    try:
        pairs_file = work / "pairs.jsonl"
        pairs_file.write_text(pairs_text, encoding="utf-8")
        rows = len(pairs) * len(SETTINGS)
        base = (base_side(base_root, pairs_file, pairs_text, rows, args.jobs)
                if base_root else None)
        before = snapshot._source_digest(head_root)
        head = _run_side(head_root, pairs_file, work / "head.jsonl", args.jobs)
        if snapshot._source_digest(head_root) != before:
            raise SystemExit(f"{head_root / 'nameparser'} changed while it "
                             f"was read; run again")
        if (got := len(jsonl_lines(head))) != rows:
            raise SystemExit(f"the head wrote {got} rows, not the {rows} "
                             f"its pairs and settings make")
    finally:
        shutil.rmtree(work, ignore_errors=True)
    print(snapshot.head_line(head_root, base_root) if base_root
          else f"head: {head_root}")
    moved = report(pairs, jsonl_lines(head),
                   jsonl_lines(base) if base is not None else None,
                   args.examples)
    return 1 if moved else 0


if __name__ == "__main__":
    sys.exit(main())
