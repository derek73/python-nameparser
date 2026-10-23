"""Where the parser's reading of a local corpus disagrees with the fields its filers typed.

The SCORE job (mechanisms.md#NAME-DATA-JOBS ("the job decides where its data lives"))
for a local corpus whose records carry the name's fields beside it:
each record's display name is parsed with the tree,
and each field is compared with the box the filer typed it into. What
cldr_agreement.py does for the committed fields files, over names that
are never committed -- so no CI run and no reviewer sees this score,
and its record lives in the cache beside the corpus, where a re-run
reports what moved since it was recorded:

    uv run python tools/differential/local_agreement.py psc-individuals --record --tree ../master-checkout
    uv run python tools/differential/local_agreement.py psc-individuals

The report prints counts and shapes, never a record: agreement overall
and by the group a source states (a nationality), the misses per field,
the commonest disagreement shapes, a shape being each disagreeing
field's word count as filed and as parsed (`middle 0->1, family 2->1` is
a two-word surname whose first word was read as a middle name), and the
set-aside title boxes at least TITLE_FLOOR records share (a word that
many filers typed is no one person's name, though it may be a name).
`--list N` prints up to N moved records of each kind, names and all, for
reading at one's own terminal.

What counts:

- Each field is compared case-folded, with periods dropped and runs of
  spaces read as one. The display name is the boxes joined, so the
  parser sees the filer's own spelling, and the fold only keeps a box's
  case, periods or spacing from reading as a miss.
- There is no suffix box. A suffix the parser peels (`Jr`, `OBE`) stood
  last in the display name, so it was typed into the last filled box,
  normally the surname: the parser's family is compared with its suffix appended,
  and the report counts the agreements that needed it.
- A filed title the parser does not read as the title, holding a word
  the vocabulary lists in neither its titles nor its connectives, is
  set aside rather than scored: a job (`Managing Partner`) or a name
  typed into the title box is the filer's error, and it can move the
  parse's other fields too. The set-aside titles are printed with their
  counts where at least TITLE_FLOOR records share one (the --top
  commonest), as leads for the vocabulary (a title nobody listed lands
  there as well).

The record is keyed to the corpus's records and to the scorer's own
code (scorer_fingerprint), so a refetch, or a change to how a field is
compared, is refused rather than reported as the parser's moves.
"""
from __future__ import annotations

import argparse
import json
import sys
import types
from collections import Counter
from collections.abc import Callable, Iterator
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Any

HERE = Path(__file__).resolve().parent
# The shared helpers and the local corpora, found as the corpus builders
# find corpus_build (see its docstring for why the directory is appended).
if str(HERE) not in sys.path:
    sys.path.append(str(HERE))
import corpus_build  # noqa: E402
import local_corpora  # noqa: E402

if TYPE_CHECKING:
    # Imported at run time only once --tree has put the tree on sys.path.
    from nameparser import Lexicon, Parser

RECORD = "agreement.jsonl"


@dataclass(frozen=True)
class Fielded:
    """How a local corpus states its fields: record key -> the parser's
    role it is compared with, in the order the display name joins them,
    and the record key the report groups by."""
    fields: dict[str, str]
    group: str


FIELDED = {local_corpora.PSC: Fielded(
    {"title": "title", "forename": "given", "middle_name": "middle",
     "surname": "family"}, group="nationality")}
#: The fewest records sharing a set-aside title for the report to print
#: it: a word typed into the title box by this many filers is no one
#: person's name.
TITLE_FLOOR = 100
#: The fewest records of a group for the report to give it a row.
GROUP_FLOOR = 1_000


def fold(text: str) -> str:
    return " ".join(text.replace(".", "").casefold().split())


def _title_words(lexicon: Lexicon) -> frozenset[str]:
    return frozenset(lexicon.titles) | frozenset(lexicon.conjunctions)


def unlisted(title: str, listed: frozenset[str]) -> bool:
    """Whether a filed title holds a word the vocabulary lists in
    neither its titles nor its connectives (`listed`)."""
    return any(word.strip(".").casefold() not in listed for word in title.split())


@dataclass(frozen=True)
class Reading:
    """One record's reading: each field as parsed where it disagrees
    with the box, whether the record was set aside, and whether the
    family agreed only with the parser's suffix appended."""
    got: dict[str, str]
    set_aside: bool = False
    by_suffix: bool = False

    def entry(self) -> dict[str, Any]:
        return {"got": self.got, **({"set_aside": True} if self.set_aside else {})}


def read(record: dict[str, str], fielded: Fielded, parser: Parser,
         listed: frozenset[str]) -> Reading:
    """`record` parsed and compared box by box (see the module docstring)."""
    name = parser.parse(record["name"])
    got = {role: getattr(name, role) for role in fielded.fields.values()}
    by_suffix = False
    if name.suffix:
        with_suffix = f"{got['family']} {name.suffix}".strip()
        by_suffix = fold(with_suffix) == fold(record.get(_box(fielded, "family"), ""))
        got["family"] = with_suffix
    wrong = {role: got[role] for box, role in fielded.fields.items()
             if fold(record.get(box, "")) != fold(got[role])}
    title = record.get(_box(fielded, "title"), "")
    if "title" in wrong and title and unlisted(title, listed):
        return Reading(wrong, set_aside=True)
    return Reading(wrong, by_suffix=by_suffix and not wrong)


def _box(fielded: Fielded, role: str) -> str:
    return next(box for box, r in fielded.fields.items() if r == role)


def shape(record: dict[str, str], fielded: Fielded, got: dict[str, str]) -> str:
    """Each disagreeing field's word count as filed and as parsed."""
    return ", ".join(f"{role} {len(record.get(box, '').split())}->{len(got[role].split())}"
                     for box, role in fielded.fields.items() if role in got)


def key(record: dict[str, str]) -> str:
    return corpus_build.jsonl_line(record, sort_keys=True)


def group_of(record: dict[str, str], fielded: Fielded) -> str:
    return " ".join(record.get(fielded.group, "").split()).title() or "(none)"


def records(local: local_corpora.Local) -> Iterator[dict[str, str]]:
    """raw.jsonl's records, streamed and checked (local_corpora.
    iter_records), each nothing but strings: CorpusDamaged before any
    caller reports or records what it read."""
    return local_corpora.iter_records(local.source, local.meta, text_only=True)


@dataclass
class Score:
    """What one run read: per group, the records scored and agreeing and
    the misses per field; the set-aside titles; the shapes; and every
    record that did not wholly agree, by key."""
    scored: Counter[str]
    agreed: Counter[str]
    misses: dict[str, Counter[str]]
    set_aside: Counter[str]
    shapes: Counter[str]
    by_suffix: int
    entries: dict[str, dict[str, Any]]


def score(rows: Iterator[dict[str, str]] | list[dict[str, str]], fielded: Fielded,
          parser: Parser) -> Score:
    listed = _title_words(parser.lexicon)
    result = Score(Counter(), Counter(), {}, Counter(), Counter(), 0, {})
    for record in rows:
        reading = read(record, fielded, parser, listed)
        if reading.got:
            result.entries[key(record)] = reading.entry()
        if reading.set_aside:
            result.set_aside[record.get(_box(fielded, "title"), "")] += 1
            continue
        group = group_of(record, fielded)
        result.scored[group] += 1
        if not reading.got:
            result.agreed[group] += 1
            result.by_suffix += reading.by_suffix
            continue
        result.misses.setdefault(group, Counter()).update(reading.got.keys())
        result.shapes[shape(record, fielded, reading.got)] += 1
    return result


def _pct(n: int, of: int) -> str:
    return f"{100 * n / of:5.1f}%" if of else "   n/a"


def report(result: Score, fielded: Fielded, top: int) -> list[str]:
    roles = list(fielded.fields.values())
    total, agreed = sum(result.scored.values()), sum(result.agreed.values())
    misses: Counter[str] = sum(result.misses.values(), Counter())
    out = [f"scored {total:,}; set aside {sum(result.set_aside.values()):,} "
           f"(a title box the parser read otherwise, holding an unlisted word)",
           f"every field agrees: {agreed:,} of {total:,} ({_pct(agreed, total).strip()}); "
           f"{result.by_suffix:,} of them with the parser's suffix in the surname box",
           "misses per field: " + ", ".join(f"{r} {misses[r]:,}" for r in roles), "",
           f"by {fielded.group} (at least {GROUP_FLOOR:,} records), misses per field:",
           f"  {fielded.group:<24} {'records':>10} {'agree':>7}  "
           + " ".join(f"{r:>8}" for r in roles)]
    for group, n in result.scored.most_common():
        if n < GROUP_FLOOR:
            break
        row = result.misses.get(group, Counter())
        out.append(f"  {group[:24]:<24} {n:>10,} {_pct(result.agreed[group], n)}  "
                   + " ".join(f"{row[r]:>8,}" for r in roles))
    out += ["", f"the {top} commonest disagreement shapes (field: words filed->parsed):"]
    out += [f"  {n:>9,}  {s}" for s, n in result.shapes.most_common(top)]
    out += ["", f"set-aside title boxes written by at least {TITLE_FLOOR} records:"]
    out += [f"  {n:>9,}  {t}" for t, n in result.set_aside.most_common()
            if n >= TITLE_FLOOR][:top]
    return out


def record_path(source: str) -> Path:
    return local_corpora.directory(source, create=False) / RECORD


def write_record(path: Path, local: local_corpora.Local, entries: dict[str, dict[str, Any]],
                 tree: str) -> None:
    header = {"raw_sha256": local.meta["sha256"], "scorer": scorer_fingerprint(),
              "data_date": local.meta["data_date"], "tree": tree}
    lines = [corpus_build.jsonl_line(header)]
    lines += [corpus_build.jsonl_line({"key": k, **v}) for k, v in sorted(entries.items())]
    corpus_build.write_atomic(path, ("\n".join(lines) + "\n").encode())


def read_record(path: Path, local: local_corpora.Local) -> dict[str, dict[str, Any]]:
    """The recorded entries, or SystemExit naming the record command
    where there is no record, one that is not a record this tool wrote,
    one recorded from another fetch of the corpus, which would report
    the records the source gained and lost as moves, or one recorded by
    another version of the scorer, which would report its own change as
    the parser's."""
    again = f"Record it again from the base checkout: {_record_command(local.source)}"
    if not path.exists():
        raise SystemExit(f"no record at {path}: record one first, from the base "
                         f"checkout: {_record_command(local.source)}")
    try:
        header, *rows = corpus_build.jsonl_lines(path.read_text(encoding="utf-8"))
        recorded = json.loads(header)
        entries = {row["key"]: {k: v for k, v in row.items() if k != "key"}
                   for row in map(json.loads, rows)}
        if not isinstance(recorded, dict):
            raise TypeError("its header is not an object")
    except (OSError, ValueError, KeyError, TypeError, AttributeError) as exc:
        raise SystemExit(f"{path} is not a record this tool wrote ({exc}). {again}"
                         ) from None
    if recorded.get("raw_sha256") != local.meta["sha256"]:
        raise SystemExit(
            f"{path} was recorded from another fetch of {local.source} (data as "
            f"of {recorded.get('data_date', 'unknown')}; the corpus now is "
            f"{local.meta['data_date']}). {again}")
    if recorded.get("scorer") != scorer_fingerprint():
        raise SystemExit(f"{path} was recorded by another version of this scorer, "
                         f"so its moves would be the scorer's. {again}")
    return entries


#: What decides a record's reading, besides the parser: scorer_fingerprint
#: hashes them, as local_corpora.fold_fingerprint hashes the word fold.
_SCORER_CODE = ("fold", "_title_words", "unlisted", "read", "_box", "Reading",
                "key", "score")


def scorer_fingerprint() -> str:
    """local_corpora.code_fingerprint of the code that turns a parse into
    a record's entry and decides which records get one (_SCORER_CODE, a
    class by its methods), of corpus_build.jsonl_line, which writes an
    entry's key, and of FIELDED."""
    module = globals()
    functions: list[Callable[..., object]] = []
    for name in _SCORER_CODE:
        target = module[name]
        functions += ([v for v in vars(target).values() if isinstance(v, types.FunctionType)]
                      if isinstance(target, type) else [target])
    return local_corpora.code_fingerprint(
        [*functions, corpus_build.jsonl_line],
        [repr(sorted((k, repr(v)) for k, v in FIELDED.items()))])


def _record_command(source: str) -> str:
    return (f"local_agreement.py {source} --record --tree <base checkout>")


def moves(old: dict[str, dict[str, Any]], new: dict[str, dict[str, Any]],
          ) -> dict[str, list[str]]:
    """Each record whose reading moved, by kind: `regression` (it agreed
    and now does not), `progress` (it disagreed and now agrees),
    `changed` (it disagrees, or is set aside, differently). Both sides
    read the same fetch, so no record is gained or lost."""
    found: dict[str, list[str]] = {"regression": [], "progress": [], "changed": []}
    for k in sorted(set(old) | set(new)):
        if k not in old:
            found["regression"].append(k)
        elif k not in new:
            found["progress"].append(k)
        elif old[k] != new[k]:
            found["changed"].append(k)
    return found


def summarize(found: dict[str, list[str]], old: dict[str, dict[str, Any]],
              new: dict[str, dict[str, Any]]) -> list[str]:
    """One line per kind of move, with the fields it moved: a field
    counts where the record disagrees on it on either side."""
    out = []
    for kind, keys in found.items():
        if not keys:
            continue
        fields: Counter[str] = Counter()
        for k in keys:
            fields.update(set(old.get(k, {}).get("got", {})) | set(new.get(k, {}).get("got", {})))
        out.append(f"{kind}: {len(keys):,} records ("
                   + ", ".join(f"{f} {n:,}" for f, n in fields.most_common()) + ")")
    return out


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("source", choices=sorted(FIELDED))
    ap.add_argument("--record", action="store_true",
                    help="rewrite the record kept beside the corpus")
    ap.add_argument("--tree", metavar="PATH", help="read with another checkout")
    ap.add_argument("--top", type=int, default=15, metavar="N")
    ap.add_argument("--list", type=int, default=0, metavar="N",
                    help="print up to N moved records of each kind, names and all")
    args = ap.parse_args(argv)
    local = local_corpora.require(args.source)
    if not args.record:
        old = read_record(record_path(args.source), local)
    root = Path(args.tree).resolve() if args.tree else HERE.parents[1]
    if args.tree:
        sys.path.insert(0, str(root))
    import nameparser
    from snapshot import check_source
    at = check_source(nameparser.__file__, root)
    fielded = FIELDED[args.source]
    print(local.header())
    try:
        result = score(records(local), fielded, nameparser.Parser())
    except local_corpora.CorpusDamaged as exc:
        raise SystemExit(str(exc)) from None
    print("\n".join(report(result, fielded, args.top)))
    if args.record:
        write_record(record_path(args.source), local, result.entries, str(at.parent))
        print(f"\nrecorded {len(result.entries):,} records that did not wholly "
              f"agree to {record_path(args.source)}")
        return 0
    found = moves(old, result.entries)
    print()
    print("\n".join(summarize(found, old, result.entries)) or "matches the record")
    for kind, keys in found.items():
        for k in keys[:args.list]:
            print(f"  {kind}: {k}  recorded {old.get(k)}  now {result.entries.get(k)}")
    return 1 if any(found.values()) else 0


if __name__ == "__main__":
    sys.exit(main())
