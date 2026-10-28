"""What a vocabulary word does: a shape grid, its incidence in the local corpora, its usage counts.

The per-word measurements a title that is also a given name needs
before it moves to the title phrase (rules/H9, #752 phase 2j, #913),
which each batch used to write as throwaway probes:

    uv run python tools/vocab/word_report.py queen deacon --base ../master-checkout
    uv run python tools/vocab/word_report.py --rank marquis queen deacon bishop

Each word gets three sections, and a ranking closes the report:

- **grid** -- the word in each of SHAPES (made-up names around it:
  a head, behind a title or a family comma, after a full name and a
  comma, past a second comma, trailing with a period, inside a title
  phrase), each spelled three ways (CASES: as written, upper case, lower
  case) and read under all three name orders: the fields and the
  ambiguity kinds, folded: a shape's three case spellings into one
  block where they read alike once lowercased, a text's orders into one
  `all` line where they read alike. With --base only what the two trees
  read differently is printed, base and head, folded the same way, so
  an order-specific move prints for its order alone.
- **corpora** -- in every fetched local corpus (local_corpora.py), the
  names that open with the word and the names whose part after the
  first comma does, each counted by how the tree reads the word there:
  `title`, `given` or `other` (a family name, a middle name, a suffix).
  With --base a count the two trees read differently is printed as
  base -> head. In a corpus that keeps the filer's boxes, the names
  opening with the word are also counted by the box it was typed into. Counts only: a local corpus is never quoted. The report
  says which corpora it read and which are not fetched, and a damaged
  one ends the run, so that nothing unread passes for a zero. A name
  holding the word at both positions (`Queen Lau, Queen`) is classed
  once for both, by its title.
- **usage** -- tools/name_usage.py's row for the word, offline
  (--no-wikidata).

The ranking separates what a move to the title phrase would give back
from what it would cost. For each word it counts the corpus names that
read it as the title where it stands in a given name's place, opening
the name or opening the part after the name's first comma (a
register's LAU, BARON, though any comma counts): `Baron Davis` reads
title 'Baron' and no given name, `Sir Lau` title 'Sir', given 'Lau'.
That count holds real titles too (Sir, Lady), so beside it stand the
names opening with the word in a corpus that keeps the filer's boxes
(psc-individuals), by the box the word was typed into: the title box,
a real title, which the move would cost, and the forename box, a given
name the title reading takes, which the move would give back (#912's
13 sheikh filings in the title box were the 13 agreement records it
moved away from agreeing), the forename box printed beside their sum
(`28/34`). The words are ordered by the forename box's count, what a
move gives back, with the title box beside it as the cost, then by
the forename box's share and by titles; a share alone would put a word
three filers typed as a forename above one 164 did, and a count cannot
be rebuilt from a share. That is the triage #913 asks for. It needs no change in the tree, so it
runs before a batch is cut; --rank prints it alone.

Each tree is read in a child process of its own, which refuses a
nameparser imported from anywhere but that tree's source package
(snapshot.check_source): one process imports one nameparser, and a
comparison of a tree with itself reports no moves.
"""
from __future__ import annotations

import argparse
import json
import multiprocessing
import os
import re
import subprocess
import sys
from collections import Counter
from collections.abc import Sequence
from concurrent.futures import ProcessPoolExecutor, ThreadPoolExecutor
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
DIFFERENTIAL = ROOT / "tools" / "differential"
# The differential tools (snapshot's child and tree checks, the local
# corpora), and this folder for a worker unpickling a function by its
# module's bare name; appended, as corpus_build's docstring says why.
for _folder in (str(DIFFERENTIAL), str(HERE)):
    if _folder not in sys.path:
        sys.path.append(_folder)
import local_corpora  # noqa: E402
import snapshot  # noqa: E402

#: The H9 shape grid: `{W}` is the word. Each says what it tests.
SHAPES = (
    "{W} Lau",                          # the head, before a surname
    "{W}",                              # alone
    "{W}. Lau",                         # the head with a period (H2's shape)
    "{W} Lau Jr.",                      # the head, before a suffix
    "{W} Lau, MD",                      # the head, before a credential
    "{W} and Mary Lau",                 # the head of a joined pair
    "Mr {W} Lau",                       # behind a title
    "Mr. and Mrs. {W} Lau",             # behind a joined title pair
    "Dr {W} Lau",                       # behind a professional title
    "His Royal Highness {W} Ali",       # behind a style
    "Vice {W} Lau",                     # behind a modifier
    "{W} of Kuwait Ali",                # the word's own title phrase
    "Ana {W}",                          # the surname slot
    "Ana Maria {W}",                    # the surname behind two given names
    "John Smith {W}.",                  # trailing, with a period (H5)
    "Lau, {W}",                         # after a family comma
    "Lau, Mr {W}",                      # behind a title after a family comma
    "Lau, {W} Mr",                      # before a trailing salutation (H8)
    "Smith, John {W}",                  # ending the given part
    ", {W}",                            # nothing before the comma (C15)
    "(Bob), {W}",                       # a nickname alone before the comma
    "John Smith, {W}",                  # after a full name and a comma
    "John Smith, Jr., {W}",             # past a second comma (C2)
    "Muhammad Ahmad, the {W}",          # the epithet with its article
    "{W} Commander Lau",                # before a title word
)
#: How each shape is spelled: the whole text as written, upper-cased
#: (a register's LAU, KING) and lower-cased.
CASES = {"as written": str, "upper": str.upper, "lower": str.lower}
#: The name orders each spelling is read under: None is the default.
ORDERS = (None, "FAMILY_FIRST", "FAMILY_FIRST_GIVEN_LAST")
_ORDER_LABEL = {None: "GF", "FAMILY_FIRST": "FF", "FAMILY_FIRST_GIVEN_LAST": "FG"}
#: Where a corpus name holds the word: opening the name, or opening the
#: part after its first comma (a register's LAU, KING).
POSITIONS = ("opens", "after a comma")
#: How the tree reads the word at that position, in report order.
READINGS = ("title", "given", "other")
#: The reading the ranking counts.
RANKED = "title"
#: The filer's boxes a name opening with the word may have typed it
#: into, where a source keeps them (psc-individuals): a word filed as
#: a forename is a given name the title reading takes, a word filed as
#: a title is a title, which a move to the title phrase would cost.
BOXES = ("title", "forename")
#: scan()'s note for a corpus that was never fetched; any other note is
#: damage, which ends the run rather than counting as nothing.
NOT_FETCHED = "not fetched"

Item = tuple[str, "str | None"]


# -- reading, in a child process per tree ----------------------------------------

def _parse_chunk(items: Sequence[Item]) -> tuple[str, list[dict[str, Any]]]:
    """The nameparser this process imported, and each item's reading: the
    fields that hold something, and the ambiguity kinds."""
    import nameparser
    from nameparser import Parser, Policy

    parsers: dict[str | None, Any] = {None: Parser()}
    rows = []
    for text, order in items:
        if order not in parsers:
            parsers[order] = Parser(policy=Policy(name_order=getattr(nameparser, order)))
        parsed = parsers[order].parse(text)
        rows.append({"fields": {k: v for k, v in parsed.as_dict().items() if v},
                     "ambiguities": sorted({a.kind.name for a in parsed.ambiguities})})
    return nameparser.__file__, rows


def _child(tree: str, jobs: int) -> int:
    """The child's side: items as JSON on stdin, readings as JSON on
    stdout, read with `tree`'s package, which check_source holds the
    import to."""
    root = Path(tree).resolve()
    sys.path.insert(0, str(root))
    import nameparser
    snapshot.check_source(nameparser.__file__, root)
    items = [(text, order) for text, order in json.load(sys.stdin)]
    rows = snapshot.parallel(_parse_chunk, items, jobs, module="word_report")
    json.dump({"file": nameparser.__file__, "rows": rows}, sys.stdout)
    return 0


def read_trees(roots: Sequence[Path], items: Sequence[Item], jobs: int,
               ) -> list[list[dict[str, Any]]]:
    """Each tree's reading of every item, in a child process per tree,
    run at once. A child that fails, or that reports a nameparser from
    outside its tree's source package, ends the run: its readings would
    be another tree's."""
    body = json.dumps(list(items))
    share = max(1, jobs // len(roots))
    children = [subprocess.Popen(
        [sys.executable, str(HERE / "word_report.py"), "--child", str(root),
         "--jobs", str(share)], stdin=subprocess.PIPE, stdout=subprocess.PIPE,
        stderr=subprocess.PIPE, text=True, env=snapshot.child_env())
        for root in roots]
    # Each child is fed and drained from a thread of its own: fed in turn,
    # the second would wait on its stdin until the first had finished.
    with ThreadPoolExecutor(len(children)) as feed:
        answers = list(feed.map(lambda child: child.communicate(body), children))
    results = []
    for root, child, (out, err) in zip(roots, children, answers, strict=True):
        if child.returncode:
            raise SystemExit(f"reading with {root} failed:\n{err}")
        answer = json.loads(out)
        snapshot.check_source(answer["file"], root)
        if len(answer["rows"]) != len(items):
            raise SystemExit(f"{root}'s child read {len(answer['rows'])} of "
                             f"{len(items)} texts")
        results.append(answer["rows"])
    return results


# -- the grid ----------------------------------------------------------------------

def grid_items(word: str) -> list[Item]:
    """Every distinct spelling of every shape, under every order, the
    word written with a capital as a name is."""
    written = word[:1].upper() + word[1:]
    texts = dict.fromkeys(spell(shape.format(W=written))
                          for shape in SHAPES for spell in CASES.values())
    return [(text, order) for text in texts for order in ORDERS]


def render(row: dict[str, Any]) -> str:
    fields = " ".join(f"{k}={v!r}" for k, v in row["fields"].items())
    kinds = f" [{', '.join(row['ambiguities'])}]" if row["ambiguities"] else ""
    return (fields or "(empty)") + kinds


def format_grid(items: Sequence[Item], head: Sequence[dict[str, Any]],
                base: Sequence[dict[str, Any]] | None = None) -> list[str]:
    """The grid, folded twice. A shape's case spellings fold into one
    block, labelled by the first and `(3 cases)`, where every order reads
    them alike once lowercased (`QUEEN LAU` reads as `Queen Lau` does);
    and a text's orders fold into one line, labelled `all`, where every
    order reads it alike. With `base`, only what the trees read
    differently is printed, each as a base line and a head line, folded
    the same way: an order-specific move prints for its order alone."""
    rows: dict[str, list[tuple[str | None, dict[str, Any], dict[str, Any]]]] = {}
    for (text, order), now, was in zip(items, head, base or head, strict=True):
        rows.setdefault(text, []).append((order, now, was))
    shapes: dict[str, list[str]] = {}
    for text in rows:
        shapes.setdefault(text.lower(), []).append(text)

    def lowered(text: str) -> list[tuple[str, str]]:
        return [(render(now).lower(), render(was).lower()) for _, now, was in rows[text]]
    lines = []
    for texts in shapes.values():
        folded = all(lowered(t) == lowered(texts[0]) for t in texts)
        for text in texts[:1] if folded else texts:
            label = f"{text!r}" + (f" ({len(texts)} cases)" if folded and len(texts) > 1 else "")
            lines += _text_lines(label, rows[text], base is not None)
    return lines


def _text_lines(label: str, rows: list[tuple[str | None, dict[str, Any], dict[str, Any]]],
                compared: bool) -> list[str]:
    """One text's lines: one `all` line (or base and head pair) where
    every order reads it alike, else a line (or pair) per order; with
    `compared`, only the orders the trees read differently."""
    pad = f"  {'':<42} {'':<3}"
    if not compared:
        if all(now == rows[0][1] for _, now, _ in rows):
            return [f"  {label:<42} all {render(rows[0][1])}"]
        return [f"  {label:<42} {_ORDER_LABEL[o]:<3} {render(now)}" for o, now, _ in rows]
    moved = [(o, now, was) for o, now, was in rows if now != was]
    if not moved:
        return []
    if len(moved) == len(rows) and all((n, w) == moved[0][1:] for _, n, w in moved):
        return [f"  {label:<42} all base {render(moved[0][2])}",
                f"{pad} head {render(moved[0][1])}"]
    return [line for o, now, was in moved
            for line in (f"  {label:<42} {_ORDER_LABEL[o]:<3} base {render(was)}",
                         f"{pad} head {render(now)}")]


# -- the corpora -------------------------------------------------------------------

def positions(name: str, keys: frozenset[str]) -> list[tuple[str, str]]:
    """(the word's key, the position) for each of `keys` that opens
    `name` or opens the part after its first comma."""
    found = []
    first = name.split(None, 1)
    if first and (key := local_corpora.word_key(first[0])) in keys:
        found.append((key, POSITIONS[0]))
    if "," in name:
        after = name.split(",", 1)[1].split(None, 1)
        if after and (key := local_corpora.word_key(after[0])) in keys:
            found.append((key, POSITIONS[1]))
    return found


def filed_box(record: dict[str, str], key: str) -> str | None:
    """Which of BOXES the filer typed `key` into as the box's first word,
    for a record that carries its boxes (psc-individuals); None where
    neither box opens with it or the record has no boxes."""
    for box in BOXES:
        words = record.get(box, "").split(None, 1)
        if words and local_corpora.word_key(words[0]) == key:
            return box
    return None


def scan(source: str, keys: frozenset[str]) -> dict[str, Any]:
    """`source`'s names holding one of `keys` at a position, by key and
    position, and for a source whose records carry the filer's boxes,
    the box each name opening with a key was typed into, by key; or a
    note where the corpus is not fetched or is damaged. Names travel
    only between this tool's processes, never to a file."""
    try:
        local = local_corpora.load(source)
        if local is None:
            return {"note": NOT_FETCHED}
        found: dict[str, dict[str, list[str]]] = {}
        boxes: dict[str, Counter[str]] = {}
        for record in local.records:
            for key, at in positions(record["name"], keys):
                found.setdefault(key, {}).setdefault(at, []).append(record["name"])
                if at == POSITIONS[0] and (box := filed_box(record, key)):
                    boxes.setdefault(key, Counter())[box] += 1
    except local_corpora.CorpusDamaged as exc:
        return {"note": f"damaged: {exc}"}
    return {"found": found, "boxes": boxes, "records": local.size}


def coverage(scanned: dict[str, dict[str, Any]]) -> str:
    """Which local corpora the counts read, and which they could not: a
    corpus that is not fetched counts nothing, and a zero beside it is
    no zero at all."""
    read = [s for s, got in scanned.items() if "found" in got]
    missing = [s for s, got in scanned.items() if "found" not in got]
    if not read:
        return (f"read no local corpus: none of {len(scanned)} is fetched, so every "
                f"count below is empty, not zero (local_corpora.py fetch SOURCE)")
    return (f"read {len(read)} of {len(scanned)} local corpora"
            + (f"; not fetched: {', '.join(missing)}" if missing else ""))


def scan_all(keys: frozenset[str], jobs: int) -> dict[str, dict[str, Any]]:
    """scan() of every local corpus, one worker process each: reading a
    corpus's records is most of the time, and they are independent."""
    sources = sorted(local_corpora.SOURCES)
    if jobs <= 1:
        return {s: scan(s, keys) for s in sources}
    import importlib
    by_name = importlib.import_module("word_report").scan
    with ProcessPoolExecutor(min(jobs, len(sources)),
                             mp_context=multiprocessing.get_context("spawn")) as pool:
        return dict(zip(sources, pool.map(by_name, sources, [keys] * len(sources)),
                        strict=True))


def classify(key: str, at: str, row: dict[str, Any]) -> str:
    """How a reading took the word at `at`: as (part of) the title, as
    the given name's first word, or otherwise."""
    fields = row["fields"]
    if key in local_corpora.words(fields.get("title", "")):
        return "title"
    given = local_corpora.words(fields.get("given", ""))
    return "given" if given and given[0] == key else "other"


#: source -> key -> position -> reading -> count
Incidence = dict[str, dict[str, dict[str, Counter[str]]]]


def incidence(scanned: dict[str, dict[str, Any]], readings: dict[str, dict[str, Any]],
              ) -> Incidence:
    """Each scanned name's reading (`readings`, by name) classified."""
    out: Incidence = {}
    for source, got in scanned.items():
        for key, at_names in got.get("found", {}).items():
            for at, names in at_names.items():
                counts = out.setdefault(source, {}).setdefault(key, {}).setdefault(
                    at, Counter())
                counts.update(classify(key, at, readings[name]) for name in names)
    return out


def format_corpora(key: str, scanned: dict[str, dict[str, Any]], head: Incidence,
                   base: Incidence | None = None) -> list[str]:
    """Per corpus and position, the count of each reading: base -> head
    with a base. Counts only."""
    lines = []
    for source, got in scanned.items():
        if "note" in got:
            lines.append(f"  {source}: {got['note']}")
            continue
        for at in POSITIONS:
            now = head.get(source, {}).get(key, {}).get(at, Counter())
            if not now:
                continue
            was = (base or {}).get(source, {}).get(key, {}).get(at, Counter())
            cells = ", ".join(
                f"{r} {was[r]:,} -> {now[r]:,}" if base is not None and was[r] != now[r]
                else f"{r} {now[r]:,}" for r in READINGS if now[r] or was[r])
            filed = got.get("boxes", {}).get(key) if at == POSITIONS[0] else None
            boxed = ("; filed in the " + ", ".join(f"{b} box {filed[b]:,}" for b in BOXES)
                     if filed else "")
            lines.append(f"  {source}, {at}: {sum(now.values()):,} ({cells}{boxed})")
    return lines or ["  no fetched corpus holds it at either position"]


#: Per key: the counts per position, and the filed boxes ("boxes").
Ranked = list[tuple[str, dict[str, Counter[str]]]]


def forename_share(by: dict[str, Counter[str]]) -> float | None:
    """Of the filers who typed the word into the title or the forename
    box, the share who typed it as a forename; None where none did."""
    filed = by["boxes"]["title"] + by["boxes"]["forename"]
    return by["boxes"]["forename"] / filed if filed else None


def forename_fraction(by: dict[str, Counter[str]]) -> str:
    """The forename box over the two boxes, `28/34`, or `-` where no
    filer typed the word in either: counts, which a share would hide."""
    filed = by["boxes"]["title"] + by["boxes"]["forename"]
    return f"{by['boxes']['forename']:,}/{filed:,}" if filed else "-"


def ranking(keys: Sequence[str], head: Incidence,
            scanned: dict[str, dict[str, Any]]) -> Ranked:
    """Each key's counts per position summed over the corpora, with the
    boxes filers typed it into, ordered by the forename box's count
    (what a move gives back), then by forename_share (the ones never
    filed in either box last), then by the names reading the word as
    the title."""
    totals: dict[str, dict[str, Counter[str]]] = {}
    for k in keys:
        totals[k] = {at: sum((head.get(s, {}).get(k, {}).get(at, Counter()) for s in head),
                             Counter()) for at in POSITIONS}
        totals[k]["boxes"] = sum((got.get("boxes", {}).get(k, Counter())
                                  for got in scanned.values()), Counter())

    def order(kv: tuple[str, dict[str, Counter[str]]]) -> tuple[int, bool, float, int, str]:
        share = forename_share(kv[1])
        return (-kv[1]["boxes"]["forename"], share is None, -(share or 0.0),
                -sum(kv[1][at][RANKED] for at in POSITIONS), kv[0])
    return sorted(totals.items(), key=order)


def format_ranking(ranked: Ranked) -> list[str]:
    """Per position, the names holding the word and those reading it as
    the title, the two titles together; then the boxes filers typed it
    into, the forename box first (the order's key), and the forename
    box over the two."""
    head = " ".join(f"{a:>8} {RANKED:>6}" for a in ("opens", "comma"))
    lines = [f"  {'word':<16} {head} {'titles':>7} {'forename box':>12} {'title box':>9} "
             f"{'forename/both':>13}"]
    for k, by in ranked:
        cells = " ".join(f"{sum(by[a].values()):>8,} {by[a][RANKED]:>6,}" for a in POSITIONS)
        lines.append(f"  {k:<16} {cells} {sum(by[a][RANKED] for a in POSITIONS):>7,} "
                     f"{by['boxes']['forename']:>12,} {by['boxes']['title']:>9,} "
                     f"{forename_fraction(by):>13}")
    return lines


# -- usage -------------------------------------------------------------------------

def usage(words: Sequence[str]) -> dict[str, list[dict[str, Any]]]:
    """tools/name_usage.py's rows for `words`, offline."""
    done = subprocess.run(
        [sys.executable, str(ROOT / "tools" / "name_usage.py"), "--no-wikidata", "--json",
         *words], capture_output=True, text=True, env=snapshot.child_env())
    why = (done.stderr.strip().splitlines() or [f"exit {done.returncode}"])[-1]
    if not done.returncode:
        try:
            answer: dict[str, list[dict[str, Any]]] = json.loads(done.stdout)
        except ValueError as exc:
            why = f"its output is not JSON ({exc})"
        else:
            return answer
    return {w: [{"source": "name_usage.py", "status": "failed", "note": why}] for w in words}


_CREDIT = re.compile(r"^.*?, data as of [^;]*; ")


def format_usage(rows: list[dict[str, Any]]) -> list[str]:
    lines = []
    for row in rows:
        counts = ", ".join(f"{k} {row[k]:,}" for k in ("given", "family", "credential")
                           if isinstance(row.get(k), int))
        # A local corpus's note opens with its credit, which the report
        # needs once, not per word.
        note = _CREDIT.sub("", row.get("note") or "")
        if row.get("status") != "ok":
            note = f"{row.get('status')}: {note}"
        lines.append(f"  {row.get('source')}: {counts or '-'}" + (f"; {note}" if note else ""))
    return lines


# -- the command -------------------------------------------------------------------

def report(words: Sequence[str], root: Path, base: Path | None, *, rank_only: bool,
           jobs: int) -> list[str]:
    keys = list(dict.fromkeys(local_corpora.word_key(w) for w in words))
    roots = [root] if base is None else [root, base]
    scanned = scan_all(frozenset(keys), jobs)
    if damaged := {s: g["note"] for s, g in scanned.items()
                   if "note" in g and g["note"] != NOT_FETCHED}:
        raise SystemExit("\n".join(f"{s}: {note}" for s, note in damaged.items()))
    names = sorted({n for got in scanned.values() for at_names in got.get("found", {}).values()
                    for ns in at_names.values() for n in ns})
    grids = {} if rank_only else {w: grid_items(w) for w in words}
    items = [i for g in grids.values() for i in g] + [(n, None) for n in names]
    read = read_trees(roots, items, jobs)
    head_rows, base_rows = read[0], (read[1] if base is not None else None)
    split = sum(len(g) for g in grids.values())

    def corpora_of(rows: list[dict[str, Any]]) -> Incidence:
        return incidence(scanned, dict(zip(names, rows[split:], strict=True)))
    head = corpora_of(head_rows)
    was = corpora_of(base_rows) if base_rows is not None else None
    lines = [f"tree: {root}" + (f"; base: {base}" if base else ""), coverage(scanned)]
    if base is not None:
        lines.append(snapshot.head_line(root, base).rstrip())
    used = usage(words) if not rank_only else {}
    at = 0
    for word in words:
        if rank_only:
            break
        n = len(grids[word])
        lines += ["", f"== {word}", f"grid ({len(SHAPES)} shapes x {len(CASES)} cases x "
                  f"{len(ORDERS)} orders; GF given-first, FF family-first, "
                  f"FG family-first given-last, all: every order alike)"
                  + (": rows the trees read differently" if base else "")]
        lines += format_grid(grids[word], head_rows[at:at + n],
                             base_rows[at:at + n] if base_rows is not None else None
                             ) or ["  (none)"]
        at += n
        key = local_corpora.word_key(word)
        lines += ["corpora (names counted, never quoted)"]
        lines += format_corpora(key, scanned, head, was)
        lines += ["usage (name_usage.py --no-wikidata)"]
        lines += format_usage(used.get(word) or used.get(key) or [
            {"source": "name_usage.py", "status": "missing", "note": "it gave no row for the word"}])
    lines += ["", f"ranking: corpus names holding the word where it opens the name and "
                  f"where it opens the part after a comma, and those reading it as the "
                  f"title there (read by {root}); then, of the names opening with it in a "
                  f"corpus that keeps the filer's boxes, those typed into the title box "
                  f"(a real title: what a move would cost) and the forename box (a given "
                  f"name the title takes: what it would give back), ordered by the "
                  f"forename box's count; forename/both is the forename box over the "
                  f"two, '-' where no filer typed it in either"]
    lines += [f"  ({coverage(scanned)})"]
    lines += format_ranking(ranking(keys, head, scanned))
    return lines


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("words", nargs="*")
    ap.add_argument("--base", metavar="PATH",
                    help="print only the grid rows this checkout reads differently, "
                         "and each changed corpus count as base -> head")
    ap.add_argument("--tree", metavar="PATH", help="read with another checkout")
    ap.add_argument("--rank", action="store_true",
                    help="print the ranking alone: no grid and no usage")
    ap.add_argument("--jobs", type=int, metavar="N", default=os.cpu_count() or 1,
                    help="work in N processes (default: every CPU)")
    ap.add_argument("--child", metavar="TREE", help=argparse.SUPPRESS)
    args = ap.parse_args(argv)
    if args.child:
        return _child(args.child, args.jobs)
    if not args.words:
        ap.error("name at least one word")
    if args.rank and args.base:
        ap.error("--rank reads one tree; drop --base")
    root = Path(args.tree).resolve() if args.tree else ROOT
    base = snapshot.base_root(args.base, root) if args.base else None
    print("\n".join(report(args.words, root, base, rank_only=args.rank, jobs=args.jobs)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
