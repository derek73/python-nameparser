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
from dataclasses import dataclass, field
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


#: The civil name's given words a pair may name: the first two that are
#: no particle, a Brazilian civil name writing its given names first.
GIVEN_WORDS = 2
#: A byname: a ballot word paired with BYNAME_PARTNERS civil given
#: names or more, each at BYNAME_PEOPLE people, a form of address, a
#: kinship, religious or occupational word or an epithet (`irmão`,
#: `dona`, `enfermeira`) beside whatever given name the person had.
BYNAME_PARTNERS = 4
BYNAME_PEOPLE = 10
#: A byname's pair kept all the same where its lift is this or more: the
#: share of the ballot word's people whose civil word is this one, over
#: that civil word's share of every person. A byname pairs with names
#: about as often as they are borne (`irmão` / `josé` 1.2, `dona` /
#: `maria` 3.7, `dona` naming women alone); a familiar form of several
#: names concentrates on each (`zé` / `josé` 9.7, `beto` / `roberto`
#: 13.5); measured 2026-11-20, decisions/name-matching 2026-11-20 #1495.
MIN_LIFT = 5.0
#: The people a byname's pair kept by its lift needs: a byname beside a
#: rarer name clears MIN_LIFT too (`dona` / `tereza` 5.3, 32 people), and
#: a higher lift would lose `zé` / `josé` (9.7) before the rescue was
#: small enough to read, so the rescue is held to more people instead.
RESCUE_PEOPLE = 50


def _given(civil: str, particles: frozenset[str]) -> list[str]:
    """The civil name's name words that are no particle."""
    return [w for w in words(civil) if _name_word(w)
            and build._normalize(w) not in particles]


def pair_of(civil: str, ballot: str, titles: frozenset[str],
            particles: frozenset[str]) -> tuple[str, str] | None:
    """The pair one candidate's two names evidence (THE PAIR above) as
    (the ballot word, the civil given word), each normalized as the
    vocabulary writes it, or None, as where the civil word chosen is not
    among the civil name's first GIVEN_WORDS given words (a surname,
    `castr` / `castro`)."""
    civil_words = [w for w in words(civil) if _name_word(w)]
    given = _given(civil, particles)
    if not civil_words or not given:
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
    tail = fx[-3:]
    rules = (lambda w: _key(w)[:1] == fx[:1] and tail in _key(w),
             lambda w: _key(w)[:1] == fx[:1],
             lambda w: tail in _key(w))
    y = next((w for rule in rules for w in given if rule(w)), given[0])
    if _key(y) not in {_key(w) for w in given[:GIVEN_WORDS]}:
        return None
    if _match_fold(x) == _match_fold(y):
        return None
    return build._normalize(x), build._normalize(y)


@dataclass
class Mined:
    """What the records evidence: each (ballot word, civil word) pair,
    both folded as the match folds them, with each spelling written and
    its people; each ballot word's people; each civil word's people
    among every person's first GIVEN_WORDS given words; every person."""

    pairs: dict[tuple[str, str], dict[tuple[str, str], set[str]]] = field(
        default_factory=dict)
    ballot: dict[str, set[str]] = field(default_factory=dict)
    civil: collections.Counter[str] = field(default_factory=collections.Counter)
    people: set[str] = field(default_factory=set)

    def lift(self, x: str, y: str) -> float:
        """The pair's people over the ballot word's, against the civil
        word's share of every person."""
        share = len(set().union(*self.pairs[x, y].values())) / len(self.ballot[x])
        return share / (self.civil[y] / len(self.people))


def mine(records: Iterable[Mapping[str, str]], titles: frozenset[str],
         particles: frozenset[str]) -> Mined:
    """Every pair the records evidence, a person counted once a pair."""
    out = Mined()
    for r in records:
        if r["person"] not in out.people:
            out.people.add(r["person"])
            for w in {_match_fold(build._normalize(w))
                      for w in _given(r["civil"], particles)[:GIVEN_WORDS]}:
                out.civil[w] += 1
        pair = pair_of(r["civil"], r["ballot"], titles, particles)
        if pair is None:
            continue
        key = (_match_fold(pair[0]), _match_fold(pair[1]))
        out.pairs.setdefault(key, {}).setdefault(pair, set()).add(r["person"])
        out.ballot.setdefault(key[0], set()).add(r["person"])
    return out


def bynames(mined: Mined) -> frozenset[str]:
    """The ballot words paired with BYNAME_PARTNERS civil words or more,
    each at BYNAME_PEOPLE people."""
    partners: collections.Counter[str] = collections.Counter()
    for (x, _), spelled in mined.pairs.items():
        if len(set().union(*spelled.values())) >= BYNAME_PEOPLE:
            partners[x] += 1
    return frozenset(x for x, n in partners.items() if n >= BYNAME_PARTNERS)


HEADER = ["a", "b", "source", "holders", "shape", "languages", "spellings",
          "lift"]


def rows(mined: Mined, minimum: int, known: set[frozenset[str]]
         ) -> list[list[str]]:
    """The candidate rows: each pair as the match reads it, both ways
    and every spelling together, written as its most attested spelling,
    at `minimum` people or more and not yet reviewed in any spelling the
    match folds alike, less a byname's pairs whose lift is under
    MIN_LIFT or whose people are under RESCUE_PEOPLE (the lift column is a
    byname pair's, empty for another);
    most people first."""
    seen = {frozenset(_match_fold(w) for w in p) for p in known if len(p) == 2}
    names = bynames(mined)
    merged: dict[frozenset[str], list[tuple[tuple[str, str], dict[tuple[str, str], set[str]]]]] = {}
    for key, spelled in mined.pairs.items():
        merged.setdefault(frozenset(key), []).append((key, spelled))
    out = []
    for unordered, parts in merged.items():
        if unordered in seen:
            continue
        people = set().union(*(p for _, sp in parts for p in sp.values()))
        if len(people) < minimum:
            continue
        lifts = [mined.lift(*key) for key, _ in parts if key[0] in names]
        if lifts and (max(lifts) < MIN_LIFT or len(people) < RESCUE_PEOPLE):
            continue
        counts: collections.Counter[tuple[str, str]] = collections.Counter()
        for _, sp in parts:
            for pair, who in sp.items():
                counts[tuple(sorted(pair))] += len(who)  # type: ignore[index]
        (a, b), _ = min(counts.items(), key=lambda kv: (-kv[1], kv[0]))
        out.append([a, b, SOURCE, str(len(people)), fc.shape(a, b), TAG,
                    str(len(counts)), f"{max(lifts):.1f}" if lifts else ""])
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
    p.add_argument("--min", type=int, default=20,
                   help="the fewest people a pair needs (default 20, the "
                        "bar #1495's review read)")
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
    print(f"{len(found.pairs):,} pairs, {len(out):,} candidates at {args.min}+ "
          f"people not yet reviewed; wrote {path}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
