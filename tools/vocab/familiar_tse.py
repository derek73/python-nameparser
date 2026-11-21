"""Draw candidate Brazilian Portuguese familiar forms from Brazil's election candidates, for a review.

WHY THIS IS IN THE TREE. ORCID's holders (tools/vocab/familiar_candidates.py)
and Wikidata's people (tools/vocab/familiar_wikidata.py) evidence few
Brazilian Portuguese familiar forms (#1495). A candidate in a Brazilian
election registers the name they want printed on the ballot beside
their civil name, and the ballot name is very often the familiar form
they go by (`Paulinho` for Paulo, `Cida` for Aparecida, `Tião` for
Sebastião). This tool reads the two names of every candidate of every
election, counts the people who wrote each pair, and writes the pairs
at a bar of people for the same two-reader review. It reads no list of
familiar forms: the pairs and their counts are the project's own
measurement (decisions/shipped-data-licences, 2026-11-12 #1370 FACTS
WE MEASURE).

THE SOURCE AND ITS LICENCE. The Superior Electoral Court (Tribunal
Superior Eleitoral, TSE) publishes each election's candidates as
`consulta_cand_<year>.zip` (ELECTIONS) on its open-data portal,
dadosabertos.tse.jus.br, whose own record of every one of these
datasets, 1994 to 2024, states the licence `cc-by`, Creative Commons
Attribution, chosen from a list that offers CC0, CC BY-SA and a
non-commercial licence too; and whose FAQ says its open data are
published "sob licença aberta que permita sua livre utilização,
consumo ou cruzamento, limitando-se a creditar a autoria ou a fonte".
The portal has no terms-of-use page of its own (checked 2026-11-20;
decisions/shipped-data-licences, 2026-11-20 #1495). README.rst's
License section credits the court.

THE PAIR. For each candidate, the ballot name (NM_URNA_CANDIDATO) and
the civil name (NM_CANDIDATO): x is the ballot name's first word that
is no title of the default lexicon's, not on STOP (`júnior`,
`juninho`, the epithets), no particle, and in no form in the civil
name; y is the civil name's word it most plausibly stands for, tried
in order: the same first letter and x's last three letters inside it;
the same first letter; x's last three letters inside it; the civil
name's first word. Each word is a name word (familiar_candidates.
is_name_word); the two differ under the name match's fold. A person is
counted once a pair, across every election they stood in, by a key
the tool hashes before keeping it (the voter-registration number where
the file gives one, else the CPF, the tax number, else the year's
candidate number); spellings the match folds alike are one pair. Every
pair goes under `pt-BR`, nothing held measuring Portugal.

    uv run python tools/vocab/familiar_tse.py fetch            # every election, cached
    uv run python tools/vocab/familiar_tse.py pairs --min 10   # write the candidates

`fetch` keeps each election's zip in $NAMEPARSER_TOOLS_CACHE (or
~/.cache/nameparser-tools) under FETCH_DIR, and beside it the two
names and the hashed person key of each candidate, nothing else;
`pairs` reads those alone and writes CANDIDATES_FILE beside them. The
requests name no person or project (USER_AGENT). The candidates hold
given names and counts, no person: nothing from the files is committed
but the reviewed pairs, name against name at a bar of people.
"""
from __future__ import annotations

import argparse
import collections
import csv
import hashlib
import io
import json
import re
import sys
import tempfile
import urllib.request
import zipfile
from collections.abc import Iterable, Iterator, Mapping
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parents[1]))
sys.path.insert(0, str(Path(__file__).parents[1] / "differential"))
sys.path.insert(0, str(Path(__file__).parent))
import build  # noqa: E402  (a sibling script, not a package)
import corpus_build  # noqa: E402
import familiar_candidates as fc  # noqa: E402
import name_usage  # noqa: E402

from nameparser._match import _fold as _match_fold  # noqa: E402

URL = "https://cdn.tse.jus.br/estatistica/sead/odsele/consulta_cand/consulta_cand_{year}.zip"
MEMBER = "consulta_cand_{year}_BRASIL.csv"
#: Every general and municipal election the court publishes.
ELECTIONS = tuple(str(y) for y in range(1994, 2025, 2))
#: A generic client name: the requests carry no person's or project's
#: details.
USER_AGENT = "familiar-forms-research/0.1 (python-urllib)"

FETCH_DIR = "familiar-tse"
CANDIDATES_FILE = "familiar-tse-candidates.tsv"
SOURCE = "tse"
TAG = "pt-BR"

CIVIL, BALLOT = "NM_CANDIDATO", "NM_URNA_CANDIDATO"
CPF, VOTER, SEQ = "NR_CPF_CANDIDATO", "NR_TITULO_ELEITORAL_CANDIDATO", "SQ_CANDIDATO"
#: The share of rows a member may hold of another width, or folded into
#: another row's field, before it is refused as cut or changed.
MAX_BAD = 1 / 10_000

#: Ballot words that are no familiar form of a civil name: a generation
#: (`júnior`, `juninho`) and the epithets a ballot writes beside a name.
STOP = frozenset({"junior", "júnior", "jr", "juninho", "nego", "negão",
                  "carioca", "amigo", "filho", "neto", "sobrinho"})

#: The cp1252 letters the court's latin-1 files hold in 0x80-0x9F.
_CP1252 = {b: bytes([b]).decode("cp1252") for b in range(0x80, 0xA0)
           if b not in (0x81, 0x8D, 0x8F, 0x90, 0x9D)}
_EDGE = "\"'“”„«»()[],.;:!?-"


# -- fetching ---------------------------------------------------------------

def fetch_dir() -> Path:
    path = name_usage.cache_dir() / FETCH_DIR
    path.mkdir(parents=True, exist_ok=True)
    return path


def _download(url: str, path: Path, member: str) -> None:
    """Fetch a zip into `path` under a temporary name of its own, kept
    only once it is a zip holding `member` whose CRC checks."""
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(request, timeout=300) as response:
        data = response.read()
    try:
        with zipfile.ZipFile(io.BytesIO(data)) as archive:
            with archive.open(member) as part:
                while part.read(1 << 20):  # a CRC mismatch raises
                    pass
    except (zipfile.BadZipFile, KeyError) as exc:
        raise ValueError(f"{url} did not give a whole zip holding {member} "
                         f"({exc})") from exc
    with tempfile.NamedTemporaryFile(dir=path.parent, prefix=path.name,
                                     suffix=".part", delete=False) as tmp:
        tmp.write(data)
    Path(tmp.name).replace(path)


def person_key(row: Mapping[str, str], year: str) -> tuple[str, str]:
    """The person a row is, hashed, and which number named them: the
    voter-registration number where the file gives one, the number every
    election from 1998 states and 2024's the only one (its CPF masked),
    else the CPF, else the year's candidate number (1994 and 1996 state
    neither, so a person of those years is counted once a candidacy)."""
    for column, kind in ((VOTER, "voter"), (CPF, "cpf")):
        digits = re.sub(r"\D", "", row.get(column, ""))
        if len(digits) >= 8 and len(set(digits)) > 1:
            return hashlib.sha256(f"{kind}:{digits}".encode()).hexdigest()[:20], kind
    return hashlib.sha256(f"seq:{year}:{row.get(SEQ, '')}".encode()
                          ).hexdigest()[:20], "seq"


def read_member(text: Iterable[str], year: str) -> tuple[list[dict[str, str]],
                                                         collections.Counter[str]]:
    """One election's candidates as (civil, ballot, person) records, one
    per person, and counts of what was read. Raises ValueError where the
    header lacks a name column, too many rows are of another width or
    folded into a field, or the last row is short: Python's csv returns
    a body cut inside a row as a short last row without raising."""
    rows = csv.reader(text, delimiter=";")
    header = next(rows, [])
    missing = [c for c in (CIVIL, BALLOT, SEQ) if c not in header]
    if missing:
        raise ValueError(f"{MEMBER.format(year=year)} lacks {', '.join(missing)}: "
                         f"the file's layout has changed")
    width = len(header)
    counts: collections.Counter[str] = collections.Counter()
    out: dict[str, dict[str, str]] = {}
    last: list[str] = []
    for row in rows:
        counts["rows"] += 1
        last = row
        if len(row) != width:
            counts["malformed"] += 1
            continue
        r = dict(zip(header, row))
        civil = r[CIVIL].translate(_CP1252).strip()
        ballot = r[BALLOT].translate(_CP1252).strip()
        if not civil or not ballot or civil.startswith("#") or ballot.startswith("#"):
            counts["nameless"] += 1
            continue
        key, kind = person_key(r, year)
        counts[f"key_{kind}"] += 1
        out[key] = {"civil": civil, "ballot": ballot, "person": key}
    folded = rows.line_num - 1 - counts["rows"]
    if last and len(last) < width:
        raise ValueError(f"{MEMBER.format(year=year)}'s last row is short: the "
                         f"file is cut")
    for count, what in ((counts["malformed"], f"rows not {width} columns"),
                        (folded, "lines folded into another row's field")):
        if count > max(1, counts["rows"] * MAX_BAD):
            raise ValueError(f"{MEMBER.format(year=year)} holds {count:,} {what} "
                             f"in {counts['rows']:,} rows: the layout has changed")
    counts["people"] = len(out)
    return list(out.values()), counts


def fetch(year: str, folder: Path | None = None,
          offline: bool = False) -> list[dict[str, str]]:
    """One election's candidates, kept as JSONL in `folder`, its zip
    fetched first if missing, unless `offline`, which raises naming it."""
    folder = folder or fetch_dir()
    kept = folder / f"candidates_{year}.jsonl"
    if kept.exists():
        return [json.loads(line)
                for line in corpus_build.jsonl_lines(kept.read_text("utf-8"))]
    if offline:
        raise SystemExit(f"{kept} is not fetched; run `uv run python "
                         f"tools/vocab/familiar_tse.py fetch`")
    archive_path = folder / f"consulta_cand_{year}.zip"
    member = MEMBER.format(year=year)
    if not archive_path.exists():
        _download(URL.format(year=year), archive_path, member)
    with zipfile.ZipFile(archive_path) as archive, archive.open(member) as binary:
        text = io.TextIOWrapper(binary, encoding="latin-1", newline="")
        records, counts = read_member(text, year)
    body = "".join(corpus_build.jsonl_line(r) + "\n" for r in records)
    with tempfile.NamedTemporaryFile("w", encoding="utf-8", dir=folder,
                                     prefix=kept.name, suffix=".part",
                                     delete=False) as tmp:
        tmp.write(body)
    Path(tmp.name).replace(kept)
    print(f"{year}: " + ", ".join(f"{k} {v:,}" for k, v in sorted(counts.items())),
          file=sys.stderr)
    return records


# -- the pairs --------------------------------------------------------------

def _key(word: str) -> str:
    return fc.fold(word)


#: STOP as `_key` folds a word.
_STOP_KEYS = frozenset(fc.fold(w) for w in STOP)


def _name_word(word: str) -> bool:
    """A name word, read title-cased: the files write every name in
    capitals, and familiar_candidates.is_name_word reads two or three
    capitals as initials (`BIU`, a familiar form of Severino)."""
    return fc.is_name_word(word.capitalize())


def words(text: str) -> list[str]:
    return [w for w in (w.strip(_EDGE) for w in text.split()) if w]


def pair_of(civil: str, ballot: str, titles: frozenset[str],
            particles: frozenset[str]) -> tuple[str, str] | None:
    """The pair one candidate's two names evidence (THE PAIR above), each
    word normalized as the vocabulary writes it, or None."""
    civil_words = [w for w in words(civil) if _name_word(w)]
    if not civil_words:
        return None
    civil_keys = {_key(w) for w in civil_words}
    x = None
    for w in words(ballot):
        k = _key(w)
        if (k in civil_keys or k in _STOP_KEYS or fc._is_title(w, titles)
                or build._normalize(w) in particles):
            continue
        x = w
        break
    if x is None or not _name_word(x):
        return None
    fx = _key(x)
    given = [w for w in civil_words if build._normalize(w) not in particles]
    tail = fx[-3:]
    rules = (lambda w: _key(w)[:1] == fx[:1] and tail in _key(w),
             lambda w: _key(w)[:1] == fx[:1],
             lambda w: tail in _key(w))
    y = next((w for rule in rules for w in given if rule(w)), civil_words[0])
    if _match_fold(x) == _match_fold(y):
        return None
    a, b = sorted((build._normalize(x), build._normalize(y)))
    return a, b


def mine(records: Iterable[Mapping[str, str]], titles: frozenset[str],
         particles: frozenset[str]) -> dict[frozenset[str], dict[tuple[str, str], set[str]]]:
    """Each pair as the match reads it (its two names folded) -> each
    spelling written -> the people who wrote it."""
    out: dict[frozenset[str], dict[tuple[str, str], set[str]]] = {}
    for r in records:
        pair = pair_of(r["civil"], r["ballot"], titles, particles)
        if pair is None:
            continue
        key = frozenset(_match_fold(w) for w in pair)
        out.setdefault(key, {}).setdefault(pair, set()).add(r["person"])
    return out


HEADER = ["a", "b", "source", "holders", "shape", "languages", "spellings"]


def rows(found: Mapping[frozenset[str], Mapping[tuple[str, str], set[str]]],
         minimum: int, known: set[frozenset[str]]) -> list[list[str]]:
    """The candidate rows: a pair at `minimum` people or more, its
    spellings together, not yet reviewed in any spelling the match folds
    alike, written as its most attested spelling; most people first."""
    seen = {frozenset(_match_fold(w) for w in p) for p in known if len(p) == 2}
    out = []
    for key, spelled in found.items():
        if key in seen:
            continue
        people = set().union(*spelled.values())
        if len(people) < minimum:
            continue
        (a, b), _ = min(spelled.items(), key=lambda kv: (-len(kv[1]), kv[0]))
        out.append([a, b, SOURCE, str(len(people)), fc.shape(a, b), TAG,
                    str(len(spelled))])
    out.sort(key=lambda r: (-int(r[3]), r[0], r[1]))
    return out


def write_tsv(rows_: list[list[str]]) -> str:
    out = io.StringIO()
    writer = csv.writer(out, delimiter="\t", lineterminator="\n")
    writer.writerow(HEADER)
    writer.writerows(rows_)
    return out.getvalue()


def all_records(years: Iterable[str], offline: bool) -> Iterator[dict[str, str]]:
    folder = fetch_dir()
    for year in years:
        yield from fetch(year, folder, offline=offline)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    sub = parser.add_subparsers(dest="command", required=True)
    f = sub.add_parser("fetch", help="download and read every election, cached")
    f.add_argument("--year", action="append", choices=ELECTIONS)
    p = sub.add_parser("pairs", help="write the candidates from the cache")
    p.add_argument("--min", type=int, default=10,
                   help="the fewest people a pair needs (default 10)")
    args = parser.parse_args(argv)
    if args.command == "fetch":
        for year in args.year or ELECTIONS:
            fetch(year)
        return 0
    from nameparser import Lexicon
    titles = fc.default_titles()
    particles = frozenset(Lexicon.default().words(kind="particle"))
    found = mine(all_records(ELECTIONS, offline=True), titles, particles)
    out = rows(found, args.min, fc.known_pairs())
    path = name_usage.cache_dir() / CANDIDATES_FILE
    path.write_text(write_tsv(out), encoding="utf-8")
    print(f"{len(found):,} pairs, {len(out):,} candidates at {args.min}+ "
          f"people not yet reviewed; wrote {path}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
