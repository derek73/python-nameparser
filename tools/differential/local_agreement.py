"""Where the parser's reading of a local corpus disagrees with the fields its filers typed.

The SCORE job (mechanisms.md#NAME-DATA-JOBS ("the job decides where its data lives"))
for a local corpus whose records carry the name's fields beside it:
each record's display name is parsed with the tree,
and each field is compared with the box the filer typed it into
(`psc-individuals`' title, forename, middle name and surname boxes;
`orcid-researchers`' given-names box, holding the middle names too, and
family-name box, typed by the holder; `cz-candidates`' title before the
name, given names, surname and title after it). What
cldr_agreement.py does for the committed fields files, over names that
are never committed -- so no CI run and no reviewer sees this score,
and its record lives in the cache beside the corpus, where a re-run
reports what moved since it was recorded:

    uv run python tools/differential/local_agreement.py psc-individuals --base ../master-checkout

--base PATH scores the base checkout from a record kept under
agreements/ beside the corpus, keyed like snapshot.py's baselines by
the fetch, a hash of the base's nameparser/ files, the interpreter's
minor version and the scorer's fingerprint, and scored in a child
process where none is kept; it never reads or writes the shared record,
which whoever last recorded decides. The records are scored in a worker
process per CPU (--jobs N), the base's child too. Without --base a check compares
against that shared record:

    uv run python tools/differential/local_agreement.py psc-individuals --record --tree ../master-checkout
    uv run python tools/differential/local_agreement.py psc-individuals

--locale cs scores the parser of a locale pack (parser_for(locales.CS))
instead of the default one, against a record of its own
(agreement.cs.jsonl, and kept records keyed by the locale too), so the
default's record and a pack's never stand for each other.

The report prints counts and shapes, never a record: agreement overall
and by the group a source states (a nationality, a country), the misses per field,
the commonest disagreement shapes, a shape being each disagreeing
field's word count as filed and as parsed (`middle 0->1, family 2->1` is
a two-word surname whose first word was read as a middle name), and the
set-aside title boxes at least TITLE_FLOOR records share (a word that
many filers typed is no one person's name, though it may be a name).
`--list N` prints up to N moved records of each kind, names and all, for
reading at one's own terminal.

What counts:

- Each field is compared case-folded, with periods dropped, commas read
  as spaces and runs of spaces read as one. The display name is the
  boxes joined, so the parser sees the filer's own spelling, and the
  fold only keeps a box's case, periods, commas or spacing from reading
  as a miss: a suffix typed into the surname box after a comma
  (`Smith, Jr.`) is the parser's family and suffix rejoined.
- Where a source has no suffix box, a suffix the parser peels (`Jr`,
  `OBE`) stood last in the display name, so it was typed into the last
  filled box, normally the surname: the parser's family is compared
  with its suffix appended, and the report counts the agreements that
  needed it. Where it has one (`cz-candidates`' title after the name),
  the suffix is compared with that box alone.
- Where a source has a title box, a filed title the parser does not read as the title, holding a word
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
import os
import shutil
import subprocess
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
#: The parser's roles a Fielded box may name, held to nameparser's Role
#: by test_local_agreement (nameparser is imported only once --tree runs).
ROLES = frozenset({"title", "given", "middle", "family", "suffix", "nickname", "maiden"})


@dataclass(frozen=True)
class Fielded:
    """How a local corpus states its fields: record key -> the parser's
    role it is compared with, in the order the display name joins them,
    and the record key the report groups by. A box holding more than one
    role names them joined by "+", and is compared with those roles'
    values joined by a space in that order: ORCID's given-names box holds
    the middle names too. A source with no title box sets nothing aside.
    The group is title-cased for the report unless `group_cased` says
    it is written as it should print (a country code). `sets_aside`
    turns off the title set-aside (read) for a source whose title box
    holds what the law asks filed there: the Czech register's holds the
    candidate's degrees, most of which the default vocabulary does not
    list (`Bc.`, `Ing.`). The set-aside took 1,059 of its records on
    2026-10-30, every one a degree or a military rank the candidate
    filed and none a job: 756 whose box after the name holds `dis`
    (re.search(r"\bdis\b", box.replace(".", "").casefold()); `Bc. Jan
    Novák, DiS.` read with title `Bc. DiS.`), 179 of the rest whose
    title box holds `et` (re.search(r"\bet\b", box); `Ing. et Ing.`
    read as given names; 182 by that test alone, 3 holding both), and
    124 others."""
    fields: dict[str, str]
    group: str
    group_cased: bool = False
    sets_aside: bool = True

    def __post_init__(self) -> None:
        # A misspelled role would find no box (_box), and a misspelled
        # title would quietly turn the set-aside off.
        unknown = {r for role in self.fields.values() for r in role.split("+")} - ROLES
        if unknown or "family" not in "+".join(self.fields.values()).split("+"):
            raise ValueError(f"Fielded({self.fields}) names {sorted(unknown) or 'no family'}:"
                             f" each box names roles of {sorted(ROLES)}, a family among them")


FIELDED = {local_corpora.PSC: Fielded(
    {"title": "title", "forename": "given", "middle_name": "middle",
     "surname": "family"}, group="nationality"),
           local_corpora.ORCID: Fielded(
    {"given": "given+middle", "family": "family"}, group="country",
    group_cased=True),
           local_corpora.PV: Fielded(
    {"given": "given+middle", "family": "family"}, group="country",
    group_cased=True),
           local_corpora.VOLBY: Fielded(
    {"titulpred": "title", "jmeno": "given+middle", "prijmeni": "family",
     "titulza": "suffix"}, group="election", group_cased=True, sets_aside=False)}
#: The fewest records sharing a set-aside title for the report to print
#: it: a word typed into the title box by this many filers is no one
#: person's name.
TITLE_FLOOR = 100
#: The fewest records of a group for the report to give it a row.
GROUP_FLOOR = 1_000


def fold(text: str) -> str:
    return " ".join(text.replace(".", "").replace(",", " ").casefold().split())


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
    got = {role: " ".join(v for r in role.split("+") if (v := getattr(name, r)))
           for role in fielded.fields.values()}
    by_suffix = False
    if name.suffix and not _box(fielded, "suffix"):
        family = fielded.fields[_box(fielded, "family")]
        with_suffix = f"{got[family]} {name.suffix}".strip()
        by_suffix = fold(with_suffix) == fold(record.get(_box(fielded, "family"), ""))
        got[family] = with_suffix
    wrong = {role: got[role] for box, role in fielded.fields.items()
             if fold(record.get(box, "")) != fold(got[role])}
    title = record.get(_box(fielded, "title"), "")
    if fielded.sets_aside and title and "title" in wrong and unlisted(title, listed):
        return Reading(wrong, set_aside=True)
    return Reading(wrong, by_suffix=by_suffix and not wrong)


def _box(fielded: Fielded, role: str) -> str:
    """The box `role` is compared with, or "" where none holds it."""
    return next((box for box, r in fielded.fields.items() if role in r.split("+")), "")


def shape(record: dict[str, str], fielded: Fielded, got: dict[str, str]) -> str:
    """Each disagreeing field's word count as filed and as parsed."""
    return ", ".join(f"{role} {len(record.get(box, '').split())}->{len(got[role].split())}"
                     for box, role in fielded.fields.items() if role in got)


def key(record: dict[str, str]) -> str:
    return corpus_build.jsonl_line(record, sort_keys=True)


def group_of(record: dict[str, str], fielded: Fielded) -> str:
    group = " ".join(record.get(fielded.group, "").split())
    return (group if fielded.group_cased else group.title()) or "(none)"


def records(local: local_corpora.Local) -> Iterator[dict[str, str]]:
    """raw.jsonl's records, every one read and checked before the first
    is handed out (local_corpora.read_records), each nothing but
    strings: CorpusDamaged before any caller reports or records what it
    read."""
    return iter(local_corpora.read_records(local.source, local.meta, text_only=True))


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
          parser: Parser, *, jobs: int = 1, locale: str = "") -> Score:
    """Every record read (read) and counted. With `jobs` above 1 the
    records are read in that many worker processes (snapshot.parallel),
    each building the parser of its own that `locale` names (parser_of),
    so `parser` must be that one: a configured parser cannot be sent to
    a worker by its name."""
    rows = list(rows)
    if jobs > 1 and parser != parser_of(locale):
        raise ValueError(f"score() reads in workers with parser_of({locale!r}); "
                         f"pass jobs=1 to score with another parser")
    if jobs > 1:
        from snapshot import parallel
        source = next(s for s, f in FIELDED.items() if f == fielded)
        readings = parallel(_read_chunk, rows, jobs, source, locale,
                            module="local_agreement")
    else:
        listed = _title_words(parser.lexicon)
        readings = [read(record, fielded, parser, listed) for record in rows]
    result = Score(Counter(), Counter(), {}, Counter(), Counter(), 0, {})
    for record, reading in zip(rows, readings, strict=True):
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


def _read_chunk(rows: list[dict[str, str]], source: str, locale: str = ""
                ) -> tuple[str, list[Reading]]:
    """The nameparser this process imported, and its reading of every
    record of `source`: score()'s unit of work in a worker."""
    import nameparser
    parser = parser_of(locale)
    listed = _title_words(parser.lexicon)
    return nameparser.__file__, [read(r, FIELDED[source], parser, listed) for r in rows]


def parser_of(locale: str) -> Parser:
    """The parser a score reads with: Parser() for no locale, else
    parser_for the pack `locale` names (`cs` for locales.CS)."""
    import nameparser
    import nameparser.locales
    if not locale:
        return nameparser.Parser()
    return nameparser.parser_for(getattr(nameparser.locales, locale.upper()))


def _pct(n: int, of: int) -> str:
    return f"{100 * n / of:5.1f}%" if of else "   n/a"


def report(result: Score, fielded: Fielded, top: int) -> list[str]:
    roles = list(fielded.fields.values())
    total, agreed = sum(result.scored.values()), sum(result.agreed.values())
    misses: Counter[str] = sum(result.misses.values(), Counter())
    out = [f"scored {total:,}; set aside {sum(result.set_aside.values()):,} "
           f"(a title box the parser read otherwise, holding an unlisted word)"
           if fielded.sets_aside else f"scored {total:,}; none set aside",
           f"every field agrees: {agreed:,} of {total:,} ({_pct(agreed, total).strip()})"
           + ("" if _box(fielded, "suffix") else
              f"; {result.by_suffix:,} of them with the parser's suffix in the surname box"),
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
    if fielded.sets_aside:
        out += ["", f"set-aside title boxes written by at least {TITLE_FLOOR} records:"]
        out += [f"  {n:>9,}  {t}" for t, n in result.set_aside.most_common()
                if n >= TITLE_FLOOR][:top]
    return out


def record_path(source: str, locale: str = "") -> Path:
    """The shared record, one per locale: agreement.jsonl for the
    default parser, agreement.cs.jsonl for locales.CS."""
    name = RECORD.replace(".jsonl", f".{locale}.jsonl") if locale else RECORD
    return local_corpora.directory(source, create=False) / name


def write_record(path: Path, local: local_corpora.Local, entries: dict[str, dict[str, Any]],
                 tree: str, locale: str = "") -> None:
    header = {"raw_sha256": local.meta["sha256"], "scorer": scorer_fingerprint(local.source),
              "data_date": local.meta["data_date"], "tree": tree,
              "entries": len(entries), "locale": locale}
    lines = [corpus_build.jsonl_line(header)]
    lines += [corpus_build.jsonl_line({"key": k, **v}) for k, v in sorted(entries.items())]
    corpus_build.write_atomic(path, ("\n".join(lines) + "\n").encode())


def read_record(path: Path, local: local_corpora.Local, locale: str = ""
                ) -> dict[str, dict[str, Any]]:
    """The recorded entries, or SystemExit naming the record command
    where there is no record, one that is not a record this tool wrote,
    one recorded from another fetch of the corpus, which would report
    the records the source gained and lost as moves, one recorded by
    another version of the scorer, which would report its own change as
    the parser's, or one scored under another locale than `locale`
    (a record written before the header named one was the default's)."""
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
    # A record written before the header counted its entries passes; a
    # count that disagrees is a write cut short on a line boundary.
    if (count := recorded.get("entries", len(entries))) != len(entries):
        raise SystemExit(f"{path} holds {len(entries):,} entries where its header "
                         f"counts {count!r}. {again}")
    if recorded.get("scorer") != scorer_fingerprint(local.source):
        raise SystemExit(f"{path} was recorded by another version of this scorer, "
                         f"so its moves would be the scorer's. {again}")
    if (held := recorded.get("locale", "")) != locale:
        raise SystemExit(f"{path} was scored under the locale {held or '(default)'!r}, "
                         f"not {locale or '(default)'!r}. {again}")
    return entries


#: What decides a record's reading, besides the parser: scorer_fingerprint
#: hashes them, as local_corpora.fold_fingerprint hashes the word fold.
_SCORER_CODE = ("fold", "_title_words", "unlisted", "read", "_box", "Reading",
                "key", "score", "_read_chunk", "parser_of")


def scorer_fingerprint(source: str) -> str:
    """local_corpora.code_fingerprint of the code that turns a parse into
    a record's entry and decides which records get one (_SCORER_CODE, a
    class by its methods), of corpus_build.jsonl_line, which writes an
    entry's key, and of `source`'s own FIELDED entry, so a source added or
    changed leaves the others' records standing."""
    module = globals()
    functions: list[Callable[..., object]] = []
    for name in _SCORER_CODE:
        target = module[name]
        functions += ([v for v in vars(target).values() if isinstance(v, types.FunctionType)]
                      if isinstance(target, type) else [target])
    return local_corpora.code_fingerprint(
        [*functions, corpus_build.jsonl_line],
        [repr((source, FIELDED[source]))])


#: Where --base's kept records live, beside the shared one.
KEPT = "agreements"


def kept_path(source: str, local: local_corpora.Local, digest: str,
              locale: str = "") -> Path:
    """Where a record of `local`'s fetch scored by a package of `digest`
    is kept: keyed by everything a record depends on besides the parser
    (the fetch, the interpreter's minor version, the scorer, the
    locale), so a key that matches is a record of this base."""
    py = f"py{sys.version_info[0]}{sys.version_info[1]}"
    return (record_path(source).parent / KEPT
            / f"{local.meta['sha256'][:12]}-{digest[:16]}-{py}"
            f"-{scorer_fingerprint(source)[:12]}{f'-{locale}' if locale else ''}.jsonl")


def _score_base(root: Path, source: str, out: Path, jobs: int = 1,
                locale: str = "") -> None:
    """`root` scored into `out` in a child process (one process imports
    one nameparser), which refuses a package other than `root`'s."""
    import snapshot
    command = [sys.executable, str(HERE / "local_agreement.py"), source,
               "--record", "--tree", str(root), "--out", str(out),
               "--jobs", str(jobs), *(["--locale", locale] if locale else [])]
    done = subprocess.run(command, env=snapshot.child_env(), capture_output=True,
                          text=True)
    if done.returncode:
        raise SystemExit(f"scoring the base {root} failed:\n{done.stdout}{done.stderr}")


def base_entries(root: Path, local: local_corpora.Local, jobs: int = 1,
                 locale: str = "") -> dict[str, dict[str, Any]]:
    """The base checkout's record, kept for its package's digest or
    scored into one now, and a line saying which base was read. Never
    the shared record: a sibling session's would pass for this base."""
    import snapshot
    digest = snapshot._source_digest(root)
    path = kept_path(local.source, local, digest, locale)
    how = f"reused the kept record {path.name}"
    if path.exists():
        try:
            entries = read_record(path, local, locale)
        except SystemExit as exc:
            print(f"deleted the kept record {path.name}: {exc}; scoring the base\n")
            path.unlink(missing_ok=True)
        else:
            try:
                os.utime(path)
            except FileNotFoundError:  # another run pruned it meanwhile
                pass
            print(f"base: {root}, nameparser/ {digest[:16]}; {how}\n")
            return entries
    # Scored into a folder of this run's own and renamed into place only
    # once the digest, taken again, says the base did not change under
    # the child: a record published under the key it was scored for.
    at = snapshot.scratch(path.parent)
    try:
        _score_base(root, local.source, at / path.name, jobs, locale)
        entries = read_record(at / path.name, local, locale)
        if snapshot._source_digest(root) != digest:
            raise SystemExit(f"{root / 'nameparser'} changed while it was scored, "
                             f"so its record may be half old and half new; run again")
        os.replace(at / path.name, path)
    finally:
        shutil.rmtree(at, ignore_errors=True)
    snapshot._prune(path.parent, "*.jsonl")
    print(f"base: {root}, nameparser/ {digest[:16]}; scored it now\n")
    return entries


def _record_command(source: str) -> str:
    return (f"local_agreement.py {source} --record --tree <base checkout>; or, "
            f"where another session may be measuring, check against a base you "
            f"name instead: local_agreement.py {source} --base <base checkout>")


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
    ap.add_argument("--base", metavar="PATH",
                    help="compare against this checkout's score, kept by its "
                         "package's digest, instead of the shared record")
    ap.add_argument("--out", type=Path, metavar="PATH",
                    help="where --record writes (default: the shared record)")
    ap.add_argument("--top", type=int, default=15, metavar="N")
    ap.add_argument("--list", type=int, default=0, metavar="N",
                    help="print up to N moved records of each kind, names and all")
    ap.add_argument("--jobs", type=int, metavar="N", default=os.cpu_count() or 1,
                    help="score in N worker processes (default: every CPU)")
    ap.add_argument("--locale", metavar="CODE", default="",
                    help="score the parser of this locale pack (cs: locales.CS) "
                         "instead of the default, against a record of its own")
    args = ap.parse_args(argv)
    locale = args.locale.lower()
    if args.base and (args.record or args.out):
        ap.error("--base compares and records nothing but its kept record; "
                 "drop --record and --out")
    if args.out and not args.record:
        ap.error("--out names where --record writes")
    local = local_corpora.require(args.source)
    root = Path(args.tree).resolve() if args.tree else HERE.parents[1]
    if args.tree:
        sys.path.insert(0, str(root))
    import nameparser
    import nameparser.locales
    from snapshot import check_source
    at = check_source(nameparser.__file__, root)
    # Before any record is read or base scored, whose refusals would
    # otherwise stand in for this one ("no record", "scoring the base failed").
    if locale and locale not in nameparser.locales.available():
        ap.error(f"--locale {args.locale}: no such pack; the packs are "
                 + ", ".join(nameparser.locales.available()))
    if args.base:
        from snapshot import base_root
        old = base_entries(base_root(args.base, root), local, args.jobs, locale)
    elif not args.record:
        old = read_record(record_path(args.source, locale), local, locale)
    fielded = FIELDED[args.source]
    print(local.header())
    if locale:
        print(f"under parser_for(locales.{locale.upper()})")
    try:
        result = score(records(local), fielded, parser_of(locale), jobs=args.jobs,
                       locale=locale)
    except local_corpora.CorpusDamaged as exc:
        raise SystemExit(str(exc)) from None
    print("\n".join(report(result, fielded, args.top)))
    if args.record:
        out = args.out or record_path(args.source, locale)
        write_record(out, local, result.entries, str(at.parent), locale)
        print(f"\nrecorded {len(result.entries):,} records that did not wholly "
              f"agree to {out}")
        return 0
    found = moves(old, result.entries)
    print()
    if args.base:
        from snapshot import head_line
        print(head_line(root, Path(args.base).resolve()))
    print("\n".join(summarize(found, old, result.entries))
          or ("matches the base" if args.base else "matches the record"))
    for kind, keys in found.items():
        for k in keys[:args.list]:
            print(f"  {kind}: {k}  recorded {old.get(k)}  now {result.entries.get(k)}")
    return 1 if any(found.values()) else 0


if __name__ == "__main__":
    sys.exit(main())
