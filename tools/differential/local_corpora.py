"""Local corpora: whole names fetched into the cache, never committed.

A local corpus does the SURVEY job of the five in
mechanisms.md#NAME-DATA-JOBS ("the job decides where its data lives"):
real names as people type them, read with the snapshot's machinery, kept out
of the repository because the names are real people's and nobody vetted
them for publication. It also does WATCH outside CI (snapshot.py --local),
and, for a source whose records carry the fields their filers typed,
SCORE outside CI (local_agreement.py): no reviewer and no CI run can see
either. What reaches the repository is what a contributor cites: counts,
and shapes written with made-up names.

    uv run python tools/differential/local_corpora.py fetch ctgov-officials
    uv run python tools/differential/local_corpora.py tally ctgov-officials
    uv run python tools/differential/local_corpora.py pairs tse-donors
    uv run python tools/differential/local_corpora.py groups jrc-names
    uv run python tools/differential/local_corpora.py alike jrc-names --base ../master-checkout
    uv run python tools/differential/snapshot.py --local ctgov-officials

`pairs --agreement`, `groups` and `alike` parse each distinct name once,
in a worker process per CPU (`--jobs N`). `alike` counts the persons
(or the pairs, for a source of pairs) whose spellings read alike in a source that pairs them (ALIKE_SOURCES),
and with `--base` the ones that now read alike and now apart: the base's
flags are kept under alike/ beside the corpus, keyed like snapshot.py's
baselines by the fetch, a hash of the base's nameparser/ files, the
interpreter's minor version and the view's code (alike_fingerprint),
and read in a child process where none is kept. `alike --languages ne`
reads the tree under a choice of languages (Locale.languages) and counts
the persons it moves against the default's flags, the tree's own or
--base's, as snapshot.py --languages does.

`fetch` writes three files into local/<source>/ under
$NAMEPARSER_TOOLS_CACHE (default ~/.cache/nameparser-tools), and
`snapshot.py --local --record` keeps its snapshot beside them:

- raw.jsonl -- one record per name as the source gave it, with where it
  came from where the source says: a ClinicalTrials.gov official, with
  the study and role; one distinct FEC, Taiwan or UK donor name, alone;
  one distinct pair of a TSE donor's filed name and the tax registry's
  name for the same donor; one distinct PSC filed name, with its four
  boxes and nationality; one distinct spelling of a JRC-Names person,
  with its entity and script; one distinct pair of a Nepali
  candidate's romanized name and the Devanagari one; one distinct ORCID
  record's two boxes joined, with the boxes, the credit name and the
  country with where it came from; one distinct PatentsView inventor
  name in a country, its two boxes joined, with the boxes, the country
  and how many people filed under it. The counts are counted from here.
- corpus.jsonl -- the distinct names, in the corpus line format
  snapshot.py and compare.py --corpus read: each record's "name", and
  for nepal-candidates its Devanagari name too, and for
  orcid-researchers the credit name (Source.corpus_keys).
- meta.json -- the source's own date for the data, what was fetched, and
  the sha256 of both files, checked on every load: a truncated file
  would otherwise read as a run of false zeros.
- snapshot.jsonl, and snapshot.jsonl.source.json naming the corpus it
  was recorded from, so a snapshot is never compared with a corpus
  fetched after it; snapshot.sample-N.jsonl and its .source.json for a
  --sample N reading; and baselines/, the recordings snapshot.py reuses.
- wordindex.json -- the word index tools/name_usage.py looks words up
  in, written on first use and keyed to the records, the fold and the
  record keys it reads (cached_index), so a single-word lookup parses neither raw.jsonl's
  records nor the names (load() still reads both files for their
  sha256).
- boxindex.json.gz -- for a source whose extract holds every record's
  boxes and country (orcid-researchers, patentsview-inventors), its
  words counted by box and country over the whole extract, uncapped,
  for tools/name_usage.py's per-country rows; written on first use and
  keyed to the extract's bytes and the code that counts them
  (cached_box_index).

A live source has no fixed snapshot to pin, so the cached copy IS the
pin: a count quoted from it names the data date the header prints, and
a later fetch may differ. A new source is a module of its own,
local_<source>.py, built on local_core.py's shared machinery, and a
SOURCES row: a fetch function returning the records and the source's
data date, and for a source whose fetch depends on a cached input or a
pinned setting, the hooks that renew it on a refresh and refuse a corpus
read from another version of it (tw-donors needs neither: each zip it caches is named by the version
the listing gives). What each source is, what it is the population for
and what its terms allow is its module's docstring: local_ctgov.py
(ctgov-officials), local_fec.py (fec-individuals), local_tse.py
(tse-donors), local_tw.py (tw-donors), local_ukec.py (ukec-individuals),
local_psc.py (psc-individuals), local_jrc.py (jrc-names),
local_nepal.py (nepal-candidates), local_orcid.py
(orcid-researchers) and local_patentsview.py (patentsview-inventors).
"""
from __future__ import annotations

import argparse
import functools
import dataclasses
import difflib
import gzip
import hashlib
import inspect
import json
import os
import re
import sys
import time
import types
import unicodedata
import zlib
from collections import Counter
from collections.abc import Callable, Iterable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Literal, NamedTuple

# The shared fetch and cache helpers (corpus_build.py, local_core.py) and
# the source modules (local_<source>.py), found by putting this directory
# on sys.path, which the source modules rely on rather than doing it
# themselves: see corpus_build's docstring for why.
_HERE = str(Path(__file__).resolve().parent)
if _HERE not in sys.path:
    sys.path.append(_HERE)

import corpus_build  # noqa: E402
import local_core  # noqa: E402
from local_core import Fetched as Fetched, Source, _again, fetch_command  # noqa: E402
from local_ctgov import fetch_ctgov  # noqa: E402
import local_fec  # noqa: E402
import local_tse  # noqa: E402
from local_fec import check_fec, fetch_fec, renew_fec  # noqa: E402
from local_jrc import JRC, check_jrc, fetch_jrc, renew_jrc  # noqa: E402
from local_nepal import check_nepal, fetch_nepal  # noqa: E402
from local_orcid import (ORCID, check_orcid, extract_path as orcid_extract,  # noqa: E402
                         fetch_orcid, orcid_boxes, renew_orcid)
from local_patentsview import (PV, check_pv, extract_path as pv_extract,  # noqa: E402
                               fetch_pv, pv_boxes, renew_pv)
from local_psc import PSC, check_psc, fetch_psc, renew_psc  # noqa: E402
from local_tse import check_tse, fetch_tse  # noqa: E402
from local_tw import fetch_tw  # noqa: E402
from local_ukec import fetch_ukec  # noqa: E402

RAW, CORPUS, META, SNAPSHOT = "raw.jsonl", "corpus.jsonl", "meta.json", "snapshot.jsonl"
INDEX = "wordindex.json"
BOX_INDEX = "boxindex.json.gz"
META_VERSION = 2  # 2: corpus.jsonl's sha256, and the source's detail nested
#: The keys load() needs in meta.json, with their types.
_META_KEYS = {"version": int, "source": str, "data_date": str, "records": int,
              "names": int, "sha256": str, "corpus_sha256": str, "detail": dict}


class CorpusDamaged(ValueError):
    """A cached corpus that is not what fetch() wrote: its message names
    the fetch that replaces it. A ValueError, which every caller already
    catches, but a class of its own, so that a caller guarding a lookup
    catches the corpus's damage and not a bug of its own."""


@dataclass(frozen=True)
class Local:
    """A local corpus as loaded: meta.json, and its records, read from
    raw.jsonl on first use: a lookup answered from the cached word index
    needs none of them (1,893,964 FEC records took 1.1s to parse on
    2026-10-22). Two loads of one fetch compare equal, the meta.json a
    fetch writes holding the sha256 of the records."""
    source: str
    meta: dict[str, Any]
    #: The records when they are already in hand (a fetch, a test).
    preloaded: list[dict[str, str]] | None = field(default=None, compare=False,
                                                   repr=False)

    # No slots=True: the cached properties write the instance __dict__.
    @functools.cached_property
    def records(self) -> list[dict[str, str]]:
        if self.preloaded is not None:
            return self.preloaded
        return read_records(self.source, self.meta)

    @property
    def size(self) -> int:
        """How many records, without reading them where meta.json says."""
        return self.meta["records"] if "records" in self.meta else len(self.records)

    @property
    def credit(self) -> str:
        """The source's credit and its data date, which ClinicalTrials.gov's
        terms ask every report to carry, as the FEC's use restriction is
        carried in its credit."""
        return f"{SOURCES[self.source].credit}, data as of {self.meta['data_date']}"

    def header(self) -> str:
        """The attribution every report opens with."""
        return (f"{self.credit}; {self.size:,} "
                f"{SOURCES[self.source].unit} (local corpus {self.source})")

    @property
    def corpus_keys(self) -> tuple[str, ...]:
        """The record keys whose names the corpus and the word index read
        (Source.corpus_keys), or "name" alone for a source not in SOURCES."""
        source = SOURCES.get(self.source)
        return source.corpus_keys if source else ("name",)

    @functools.cached_property
    def index(self) -> WordIndex:
        """The word index, read from its cache beside the corpus or built
        and cached there (cached_index)."""
        return cached_index(self)


SOURCES: dict[str, Source] = {
    "ctgov-officials": Source(
        credit="ClinicalTrials.gov (NLM) study officials", unit="officials",
        fetch=fetch_ctgov),
    "fec-individuals": Source(
        credit=f"FEC individual contributions, {local_fec.FEC_CYCLE} cycle "
               f"(52 U.S.C. 30111(a)(4): not for soliciting or commercial use)",
        unit="names", fetch=fetch_fec, renew=renew_fec, check=check_fec),
    "tse-donors": Source(
        credit=f"TSE (Tribunal Superior Eleitoral) candidates' receipts from "
               f"individuals, {' and '.join(local_tse.TSE_ELECTIONS)} elections "
               f"(dadosabertos.tse.jus.br, CC BY)",
        unit="name pairs", fetch=fetch_tse, check=check_tse),
    "tw-donors": Source(
        credit="Control Yuan political donation reports (ardata.cy.gov.tw), "
               "Open Government Data License, version 1.0 (Taiwan) "
               "(the platform's terms: not for profit, credit investigation "
               "or other improper use)",
        unit="names", fetch=fetch_tw),
    "ukec-individuals": Source(
        credit="UK Electoral Commission register of donations, individual "
               "donors (reuse terms for the register not stated)",
        unit="names", fetch=fetch_ukec),
    "nepal-candidates": Source(
        credit="Election Commission, Nepal: candidates of the 2079 BS (2022) "
               "local elections (result.election.gov.np; no licence stated)",
        unit="name pairs", fetch=fetch_nepal, check=check_nepal,
        corpus_keys=("name", "devanagari")),

    PSC: Source(
        credit="Companies House people with significant control, individuals "
               "(a public register: Companies House sets no terms on its use, "
               "and data protection law applies to the names)",
        unit="filed names", fetch=fetch_psc, renew=renew_psc, check=check_psc),
    JRC: Source(
        credit="JRC-Names (European Commission Joint Research Centre), person "
               "entities (licensed under the JRC-Names EULA: personal use, no "
               "redistribution or derivative works)",
        unit="spellings", fetch=fetch_jrc, renew=renew_jrc, check=check_jrc),
    ORCID: Source(
        credit="ORCID Public Data File 2025, public names and countries "
               "(CC0 1.0; ORCID asks for credit and respect for the privacy "
               "of the people in it)",
        unit="records", fetch=fetch_orcid, renew=renew_orcid, check=check_orcid,
        corpus_keys=("name", "credit"), extract=orcid_extract, boxes=orcid_boxes),
    PV: Source(
        credit="PatentsView granted-patent inventors, 1976-2025, from the USPTO "
               "Open Data Portal (CC BY 4.0; credit PatentsView)",
        unit="names", fetch=fetch_pv, renew=renew_pv, check=check_pv,
        extract=pv_extract, boxes=pv_boxes),
}


# -- the cache ---------------------------------------------------------------

def directory(source: str, *, create: bool = True) -> Path:
    if source not in SOURCES:
        raise ValueError(f"no local corpus {source!r}; the sources are "
                         + ", ".join(sorted(SOURCES)))
    return local_core.directory(source, create=create)


def fetch(source: str) -> Local:
    """Fetch `source` and write raw.jsonl, corpus.jsonl and meta.json, in
    that order. A run that dies between the writes leaves files the old
    meta.json's sha256s do not match, which load() refuses."""
    path = directory(source)
    fetched = SOURCES[source].fetch()
    if not fetched.records:
        raise ValueError(f"{source}: the fetch found no names")
    if any(not isinstance(r.get("name"), str) or not r["name"].strip()
           for r in fetched.records):
        raise ValueError(f"{source}: a fetched record has no name")
    keys = SOURCES[source].corpus_keys
    for key in keys[1:]:
        if any(not isinstance(r.get(key, ""), str) for r in fetched.records):
            raise ValueError(f"{source}: a fetched record's {key!r} is not text")
        if not any(r.get(key, "").strip() for r in fetched.records):
            raise ValueError(f"{source}: no fetched record holds the corpus key "
                             f"{key!r}: a key misspelled, or a column emptied")
    raw = "".join(corpus_build.jsonl_line(r, sort_keys=True) + "\n"
                  for r in fetched.records).encode()
    lines = corpus_build.corpus_lines(
        {"text": r[key], "shape": None} for r in fetched.records
        for key in keys if r.get(key, "").strip())
    corpus = ("\n".join(lines) + "\n").encode()
    corpus_build.write_atomic(path / RAW, raw)
    corpus_build.write_atomic(path / CORPUS, corpus)
    meta = {"version": META_VERSION, "source": source,
            "data_date": fetched.data_date,
            "fetched": time.strftime("%Y-%m-%d"),
            "records": len(fetched.records), "names": len(lines),
            "corpus_keys": list(keys),
            "sha256": hashlib.sha256(raw).hexdigest(),
            "corpus_sha256": hashlib.sha256(corpus).hexdigest(),
            "detail": fetched.detail}
    corpus_build.write_atomic(path / META, json.dumps(meta, indent=2).encode())
    return Local(source, meta, fetched.records)


def load(source: str) -> Local | None:
    """The cached corpus, or None when it was never fetched. Anything
    else that is not the corpus fetch() wrote -- a meta.json of another
    version or shape, a raw.jsonl or corpus.jsonl its sha256 does not
    match -- raises CorpusDamaged naming the way out: a damaged file must
    not read as a smaller corpus. The records are read on first use, and
    a record without a name raises there (read_records)."""
    path = directory(source, create=False)
    if not (path / META).exists():
        return None
    again = _again(source)
    try:
        meta = json.loads((path / META).read_text(encoding="utf-8"))
    except ValueError as exc:
        raise CorpusDamaged(f"{path / META} is not JSON ({exc}){again}") from None
    if not isinstance(meta, dict) or meta.get("version") != META_VERSION:
        raise CorpusDamaged(f"{path / META} was not written by this version of "
                         f"this tool{again}")
    for key, kind in _META_KEYS.items():
        value = meta.get(key)
        if not isinstance(value, kind) or isinstance(value, bool):
            raise CorpusDamaged(f"{path / META} has no {kind.__name__} {key!r}{again}")
    if (check := SOURCES[source].check) and (why := check(meta)):
        raise CorpusDamaged(f"{path / META} {why}{again}")
    # A meta.json written before corpus_keys were recorded holds "name"'s
    # corpus, as every source's then was.
    keys = list(SOURCES[source].corpus_keys)
    if meta.get("corpus_keys", ["name"]) != keys:
        raise CorpusDamaged(f"{path / META} holds a corpus of the record keys "
                            f"{meta.get('corpus_keys', ['name'])}, and this tool "
                            f"reads {keys}{again}")

    _verified(source, RAW, meta["sha256"])
    _verified(source, CORPUS, meta["corpus_sha256"])
    return Local(source, meta)



def _verified(source: str, name: str, sha256: str) -> bytes:
    """`source`'s file `name`, or ValueError naming the way out unless
    it matches the sha256 meta.json gives it."""
    path = directory(source, create=False) / name
    body = path.read_bytes() if path.exists() else b""
    if hashlib.sha256(body).hexdigest() != sha256:
        raise CorpusDamaged(f"{path} does not match the sha256 in {META}{_again(source)}")
    return body


def read_records(source: str, meta: dict[str, Any], *,
                 text_only: bool = False) -> list[dict[str, str]]:
    """raw.jsonl's records, the file checked against its sha256 first
    (load() checked it, but the file is read later and may have changed)
    and cut by corpus_build.jsonl_lines, each holding a name, and with
    `text_only` nothing but strings; CorpusDamaged naming the way out
    otherwise. Read whole: streaming the lines cost more than holding
    them (1.99s against 1.15s for fec-individuals, 2026-10-23)."""
    path = directory(source, create=False) / RAW
    raw = _verified(source, RAW, meta["sha256"])
    try:
        records = [json.loads(line) for line in corpus_build.jsonl_lines(raw.decode())]
    except ValueError:
        raise CorpusDamaged(f"{path} holds a line that is not JSON{_again(source)}") from None
    if any(not isinstance(r, dict) or not isinstance(r.get("name"), str) for r in records):
        raise CorpusDamaged(f"{path} holds a record without a name{_again(source)}")
    if text_only and any(not isinstance(v, str) for r in records for v in r.values()):
        raise CorpusDamaged(f"{path} holds a record with a value that is not "
                            f"text{_again(source)}")
    return records


def require(source: str) -> Local:
    """The cached corpus for a command that cannot go on without it:
    exits naming the fetch where it is missing or damaged. Damage to the
    records shows only once they are read, which main's tally catches
    the same way."""
    try:
        local = load(source)
    except ValueError as exc:
        raise SystemExit(str(exc)) from None
    if local is None:
        raise SystemExit(f"{source} is not fetched: {fetch_command(source)}")
    return local


def corpus_path(source: str) -> Path:
    return directory(source, create=False) / CORPUS


# -- views -------------------------------------------------------------------

def after_commas(name: str) -> list[str]:
    """Each part of `name` after a comma, as written, stripped of the
    spaces around it: 'Ann Lee, MD, PhD' gives ['MD', 'PhD'], and
    'MBBS,FCPS' is two parts, as the parser splits it. Unlike the parser,
    it does not first set aside a comma inside parentheses or quotes:
    'Ann (Lee, Jr) Roe, MD' gives ['Jr) Roe', 'MD']."""
    return [part.strip() for part in name.split(",")[1:]]


def tally(local: Local) -> tuple[Counter[str], int]:
    """Each after-comma part, counted by the records writing it (each
    once however often its name repeats it), and how many records hold
    a comma at all."""
    parts: Counter[str] = Counter()
    with_comma = 0
    for record in local.records:
        found = after_commas(record["name"])
        if found:
            with_comma += 1
            parts.update(set(found))
    return parts, with_comma


#: How a filed name departs from the reference name beside it (a
#: record's "registry"), in the order pair_shape asks: a pair takes the
#: first that fits.
PAIR_SHAPES = (
    "the same", "no reference name", "no filed name", "case only",
    "accents only", "case and accents", "punctuation or spacing only",
    "the same words reordered",
    "words left out", "words added", "words shortened", "words misspelled",
    "words left out and shortened", "mostly the same words",
    "few words in common")
#: A word of a pair: what a space, period, comma, apostrophe or hyphen
#: does not cut.
_PAIR_WORD = re.compile(r"[^\s.,'’-]+")
#: How alike two words must be (difflib's ratio) to read as one word
#: misspelled: JUNIIOR for JUNIOR is 0.92, SOUSA for SOUZA 0.8.
PAIR_MISSPELLED = 0.75


def _unmarked(name: str) -> str:
    """`name` with its combining marks dropped (accents; a letter that
    does not decompose, ø or ł, stays)."""
    return "".join(c for c in unicodedata.normalize("NFD", name)
                   if not unicodedata.combining(c))


def _bare(name: str) -> str:
    """`name` in capitals with its accents dropped."""
    return _unmarked(name.upper())


def _pair_words(name: str) -> list[str]:
    return _PAIR_WORD.findall(_bare(name))


def _in_order(short: list[str], long: list[str]) -> bool:
    """Whether every word of `short` stands in `long`, in order."""
    rest = iter(long)
    return all(word in rest for word in short)


def pair_shape(filed: str, reference: str) -> str:
    """The first of PAIR_SHAPES that `filed` and `reference` fit: 'ANA
    SILVA' beside 'ANA DA SILVA' is words left out, 'ANA M SILVA' beside
    'ANA MARIA SILVA' words shortened, 'JOSE' beside 'JOSÉ' accents only."""
    if filed == reference:
        return "the same"
    if not reference:
        return "no reference name"
    a, b = _pair_words(filed), _pair_words(reference)
    if not a:
        return "no filed name"
    if filed.upper() == reference.upper():
        return "case only"
    if _unmarked(filed) == _unmarked(reference):
        return "accents only"
    if _bare(filed) == _bare(reference):
        return "case and accents"
    if "".join(a) == "".join(b):
        return "punctuation or spacing only"
    if sorted(a) == sorted(b):
        return "the same words reordered"
    if _in_order(a, b):
        return "words left out"
    if _in_order(b, a):
        return "words added"
    if len(a) == len(b):
        changed = [(x, y) for x, y in zip(a, b) if x != y]
        if all(y.startswith(x) for x, y in changed):
            return "words shortened"
        if len(changed) <= 2 and all(
                difflib.SequenceMatcher(None, x, y).ratio() >= PAIR_MISSPELLED
                for x, y in changed):
            return "words misspelled"
    rest = iter(b)
    if all(any(y.startswith(x) for y in rest) for x in a):
        return "words left out and shortened"
    if len(set(a) & set(b)) >= max(1, min(len(a), len(b)) - 1):
        return "mostly the same words"
    return "few words in common"


#: The least pairs a word must be left out of, or added to, to be
#: listed (each pair counting a word once): a word in fewer could be
#: part of one person's name. The same floor holds for the accents-only
#: disagreements, listed by the two spellings' last words.
PAIR_WORD_FLOOR = 10


def format_pairs(found: PairCounts, top: int) -> str:
    """The report `pairs` prints: each shape's pairs and share of the
    pairs that differ, the surname agreement where it was counted, and
    the words most often left out and added, counts and words only."""
    same = found.shapes["the same"]
    differ = found.total - same
    lines = [f"{found.total:,} pairs; {same:,} the same, {differ:,} differing:"]
    for shape in PAIR_SHAPES[1:]:
        n = found.shapes[shape]
        if not n:
            continue
        line = f"  {n:>9,}  {n / differ:6.1%}  {shape}"
        if found.agreement is not None and shape in found.agreement:
            agree, parsed = found.agreement[shape]
            line += f"  (one surname in {agree / parsed:.0%})"
        lines.append(line)
    for words, what in ((found.left_out, "words most often left out"),
                        (found.added, "words most often added"),
                        (found.accent_splits, "accents-only pairs read with two "
                                              "surnames, by their last words")):
        listed = [(w, n) for w, n in words.most_common(top) if n >= PAIR_WORD_FLOOR]
        if listed:
            lines.append(f"{what}: " + ", ".join(f"{w} {n:,}" for w, n in listed))
    return "\n".join(lines)


@dataclass(frozen=True)
class PairCounts:
    """What pair_counts finds: the pairs of each shape, the reference
    name's words a filed name leaves out and the words it adds (in the
    pairs of those two shapes), and, where asked, how many pairs of each
    shape parse() reads with one surname, and the accents-only pairs it
    reads with two, keyed by the two spellings' last words ("JÚNIOR /
    JUNIOR"). Each pair counts a word once."""
    shapes: Counter[str]
    left_out: Counter[str]
    added: Counter[str]
    #: shape -> (pairs whose surnames agree, pairs parsed)
    agreement: dict[str, tuple[int, int]] | None = None
    accent_splits: Counter[str] = field(default_factory=Counter)

    @property
    def total(self) -> int:
        return sum(self.shapes.values())


@functools.cache
def _parse(languages: tuple[str, ...]) -> Callable[[str], Any]:
    """The parse a view reads with: parse() itself, or a parser under the
    choice of `languages` (Locale.languages), built once per process."""
    from nameparser import Lexicon, Locale, parse, parser_for
    if not languages:
        return parse
    return parser_for(Locale(code="choice", lexicon=Lexicon.empty(),
                             languages=frozenset(languages))).parse


def surname(name: str, languages: tuple[str, ...] = ()) -> str:
    """The last word of the family name parse() reads in `name`, in
    capitals without accents, or "" where it reads none: the word two
    spellings of one person should share unless the last surname itself
    is what one leaves out (a particle or a middle name left out, a
    middle name shortened, accents or case changed). Two readings with no
    surname do not share one."""
    family = _pair_words(_parse(languages)(name).family)
    return family[-1] if family else ""


def _surnames(names: list[str], languages: tuple[str, ...] = ()
              ) -> tuple[str, list[str]]:
    """The nameparser this process imported, and surname() of each name:
    a unit of work for _parsed."""
    import nameparser
    return nameparser.__file__, [surname(n, languages) for n in names]


def _parsed(chunk: Callable[..., tuple[str, list[Any]]], names: Iterable[str],
            jobs: int, *args: object) -> dict[str, Any]:
    """chunk(part, *args)'s answer for each distinct name, read in `jobs`
    worker processes where there are enough (snapshot.parallel)."""
    from snapshot import parallel
    distinct = list(dict.fromkeys(names))
    return dict(zip(distinct, parallel(chunk, distinct, jobs, *args,
                                       module="local_corpora"), strict=True))


def pair_counts(local: Local, *, agreement: bool = False, jobs: int = 1) -> PairCounts:
    """Each record's pair_shape. A source whose records carry no
    reference name raises ValueError. With `agreement`, every pair with a
    reference name that differs is parsed both ways and its two surnames
    compared, agreeing only where both read one, which
    parses each distinct name once, in `jobs` worker processes
    (snapshot.parallel)."""
    if not local.records:
        raise ValueError(f"{local.source} holds no records")
    if any("registry" not in r for r in local.records):
        raise ValueError(f"{local.source}'s records carry no reference name "
                         f"to pair a filed name with")
    shapes: Counter[str] = Counter()
    left_out: Counter[str] = Counter()
    added: Counter[str] = Counter()
    tally_agree: dict[str, list[int]] = {}
    accent_splits: Counter[str] = Counter()
    seen: dict[str, str] = {}
    if agreement:
        seen = _parsed(_surnames, [n for r in local.records
                                   if pair_shape(r["name"], r["registry"])
                                   not in ("the same", "no reference name")
                                   for n in (r["name"], r["registry"])], jobs)
    for record in local.records:
        filed, reference = record["name"], record["registry"]
        shape = pair_shape(filed, reference)
        shapes[shape] += 1
        if shape in ("words left out", "words added"):
            a, b = Counter(_pair_words(filed)), Counter(_pair_words(reference))
            if shape == "words left out":
                left_out.update((b - a).keys())
            else:
                added.update((a - b).keys())
        if agreement and shape not in ("the same", "no reference name"):
            counts = tally_agree.setdefault(shape, [0, 0])
            one = seen[filed] == seen[reference] != ""
            counts[0] += one
            counts[1] += 1
            if shape == "accents only" and not one:
                accent_splits[f"{filed.split()[-1].upper()} / "
                              f"{reference.split()[-1].upper()}"] += 1
    return PairCounts(shapes, left_out, added,
                      {s: (n[0], n[1]) for s, n in tally_agree.items()}
                      if agreement else None, accent_splits)


#: Where reading places the family, as Reading.family_at.
FamilyAt = Literal["first", "last", "whole", "inner", "none"]


class Reading(NamedTuple):
    """The structure parse() gives one spelling (reading): counts and
    positions, never the words, so spellings in two scripts compare."""
    title: bool
    suffix: bool
    given: bool
    family: bool
    family_words: int
    #: Where the family stands among the given, middle and family words.
    family_at: FamilyAt


#: What the groups view compares between two spellings of one person,
#: in the order it reports them: Reading's fields, as the report names
#: them.
GROUP_FIELDS = tuple(name.replace("_", " ") for name in Reading._fields)
#: The name-bearing roles, among which reading places the family.
_NAME_ROLES = frozenset({"given", "middle", "family"})
#: What group_counts counts, beside GROUP_FIELDS, for two scripts whose
#: spellings read alike in no one pair, though every field has a value
#: in common across them: a combination of fields reads apart.
NO_ONE_FIELD = "no one field"


class _Read(NamedTuple):
    """reading(name), and the title and the suffix parse() reads."""
    reading: Reading
    title: str
    suffix: str


def _read(name: str, languages: tuple[str, ...] = ()) -> _Read:
    parsed = _parse(languages)(name)
    roles = [str(t.role) for t in parsed.tokens if str(t.role) in _NAME_ROLES]
    family = [i for i, role in enumerate(roles) if role == "family"]
    at: FamilyAt
    if not family:
        at = "none"
    elif len(family) == len(roles):
        at = "whole"
    elif family == list(range(len(family))):
        at = "first"
    elif family == list(range(len(roles) - len(family), len(roles))):
        at = "last"
    else:
        at = "inner"
    return _Read(Reading(bool(parsed.title), bool(parsed.suffix), bool(parsed.given),
                         bool(parsed.family), len(parsed.family.split()), at),
                 parsed.title, parsed.suffix)


def reading(name: str) -> Reading:
    """The structure parse() gives `name`, one value per GROUP_FIELDS:
    title read, suffix read, given found, family found, the family's
    words, and where the family stands among the given, middle and
    family words (titles, suffixes, nicknames and maiden names left
    out): "first" or "last" where it is one run at that edge, "whole"
    where it is all of them, "none" where there is none, and "inner"
    otherwise, a run inside or a family split in two: rare (1 of the
    1,315,051 distinct jrc-names spellings on 2026-10-24), and kept so
    that such a family is not labelled an edge."""
    return _read(name).reading


def _differing(one: set[Reading], other: set[Reading] | None = None) -> set[str]:
    """The GROUP_FIELDS in which the readings `one` disagree among
    themselves (more than one value), or, given `other`, in which no
    reading of `one` agrees with any of `other` (no value in common): two
    Latin spellings that differ between themselves do not make the
    Latin and the Cyrillic spellings differ where a Cyrillic one reads
    as either Latin one does."""
    if other is None:
        return {f for i, f in enumerate(GROUP_FIELDS) if len({r[i] for r in one}) > 1}
    return {f for i, f in enumerate(GROUP_FIELDS)
            if {r[i] for r in one}.isdisjoint({r[i] for r in other})}


class Ungroupable(ValueError):
    """A corpus group_counts cannot read: no records, or records with no
    entity and script. A class of its own, as CorpusDamaged is, so that
    the command catches these and not a ValueError from the parser."""


@dataclass(frozen=True)
class GroupCounts:
    """What group_counts finds, every count a count of PERSONS, not of
    spellings or of pairs, so that a person spelled 600 ways weighs what
    one spelled twice does. Keyed by a pair of scripts ("Cyrillic /
    Latin", "Latin / Latin"), and by "any" for all of a person's
    spellings taken together; a script() label that is no script
    ("mixed", "none") keys a pair like one."""
    #: The persons with two or more spellings, and those spellings.
    persons: int
    spellings: int
    #: pair -> the persons with two spellings in those scripts ("any":
    #: every person, so groups["any"] == persons).
    groups: Counter[str]
    #: pair -> those whose spellings read alike: within one script, all
    #: of them read one way; across two, some spelling in one reads, in
    #: every field, as some spelling in the other does.
    agree: Counter[str]
    #: (pair, a GROUP_FIELDS member) -> those whose spellings disagree in
    #: the field (_differing): within one script's for "Latin / Latin",
    #: between the two scripts' for "Cyrillic / Latin". (pair,
    #: NO_ONE_FIELD) -> those across two scripts that read alike in no
    #: pair of spellings yet in no one field apart, so that a pair's
    #: persons are each alike, apart in a field, or here.
    differ: Counter[tuple[str, str]]
    #: The words of the titles, and of the suffixes, of a person some of
    #: whose spellings read one and others none, folded by word_key,
    #: counted once a person: two spellings reading two titles (Dr.,
    #: Doctor) with no untitled spelling beside them add nothing.
    titles: Counter[str]
    suffixes: Counter[str]


def _by_entity(local: Local) -> dict[str, list[tuple[str, str]]]:
    """Each entity's (script, spelling) pairs, from a source whose
    records carry an "entity" and a "script"; Ungroupable otherwise."""
    if not local.records:
        raise Ungroupable(f"{local.source} holds no records")
    if any("entity" not in r or "script" not in r for r in local.records):
        raise Ungroupable(f"{local.source}'s records carry no entity and script "
                          f"to group spellings by")
    by_entity: dict[str, list[tuple[str, str]]] = {}
    for record in local.records:
        by_entity.setdefault(record["entity"], []).append((record["script"], record["name"]))
    return by_entity


def _reads(names: list[str], languages: tuple[str, ...] = ()
           ) -> tuple[str, list[_Read]]:
    """The nameparser this process imported, and _read of each name: a
    unit of work for _parsed."""
    import nameparser
    return nameparser.__file__, [_read(n, languages) for n in names]


def group_counts(local: Local, *, jobs: int = 1) -> GroupCounts:
    """Each person with two or more spellings, from a source whose
    records carry an "entity" and a "script": every spelling's reading
    compared by the pair of scripts the spellings are written in, as
    _differing says. A distinct name is parsed once, in `jobs` worker
    processes (snapshot.parallel). A source without entities raises
    Ungroupable."""
    by_entity = _by_entity(local)
    read: dict[str, _Read] = _parsed(
        _reads, (name for variants in by_entity.values() if len(variants) > 1
                 for _, name in variants), jobs)
    groups: Counter[str] = Counter()
    agree: Counter[str] = Counter()
    differ: Counter[tuple[str, str]] = Counter()
    titles: Counter[str] = Counter()
    suffixes: Counter[str] = Counter()
    persons = spellings = 0
    for variants in by_entity.values():
        if len(variants) < 2:
            continue
        persons += 1
        spellings += len(variants)
        by_script: dict[str, set[Reading]] = {}
        written: Counter[str] = Counter()
        for script, name in variants:
            by_script.setdefault(script, set()).add(read[name].reading)
            written[script] += 1
        everything = set().union(*by_script.values())
        # pair -> (the fields read apart, whether the spellings read alike)
        compared = {"any": (_differing(everything), len(everything) == 1)}
        scripts = sorted(by_script)
        for i, first in enumerate(scripts):
            for second in scripts[i:]:
                one = by_script[first]
                if first != second:
                    compared[f"{first} / {second}"] = (
                        _differing(one, by_script[second]),
                        not one.isdisjoint(by_script[second]))
                elif written[first] > 1:
                    compared[f"{first} / {first}"] = (_differing(one), len(one) == 1)
        for pair, (fields, alike) in compared.items():
            groups[pair] += 1
            if alike:
                agree[pair] += 1
            elif not fields:
                differ[(pair, NO_ONE_FIELD)] += 1
            differ.update((pair, f) for f in fields)
        for counter, mark in ((titles, "title"), (suffixes, "suffix")):
            if len({getattr(r, mark) for r in everything}) > 1:
                counter.update({key for _, name in variants if getattr(read[name].reading, mark)
                                for key in words(getattr(read[name], mark))})
    return GroupCounts(persons, spellings, groups, agree, differ, titles, suffixes)


def format_groups(found: GroupCounts, top: int) -> str:
    """The report `groups` prints: per pair of scripts, the persons with
    two spellings in them, the share whose spellings read alike
    (GroupCounts.agree), and the share whose spellings read each field
    apart (_differing), then NO_ONE_FIELD's; then the title and suffix
    words read in some of a person's spellings and in none of the
    others, listed only where PAIR_WORD_FLOOR persons share one. The
    `top` largest pairs are listed, and the `top` commonest words.
    Counts and words only."""
    lines = [f"{found.persons:,} persons with two or more spellings "
             f"({found.spellings:,} spellings); by the scripts of two of them:"]
    pairs = ["any", *sorted((p for p in found.groups if p != "any"),
                            key=lambda p: (-found.groups[p], p))[:top]]
    for pair in pairs:
        n = found.groups[pair]
        if not n:
            continue
        shares = ", ".join(f"{field} {found.differ[(pair, field)] / n:.1%}"
                           for field in (*GROUP_FIELDS, NO_ONE_FIELD)
                           if found.differ[(pair, field)])
        lines.append(f"  {n:>9,}  {found.agree[pair] / n:6.1%} alike  {pair}"
                     + (f"; differ in {shares}" if shares else ""))
    for counted, what in ((found.titles, "title words read in some spellings only"),
                          (found.suffixes, "suffix words read in some spellings only")):
        listed = [(w, n) for w, n in counted.most_common(top) if n >= PAIR_WORD_FLOOR]
        if listed:
            lines.append(f"{what} ({PAIR_WORD_FLOOR} persons or more): "
                         + ", ".join(f"{w} {n:,}" for w, n in listed))
    return "\n".join(lines)


# -- alike: the spelling views against a base ----------------------------------

#: What the alike view counts in each source whose records hold two
#: spellings of one person, and the noun for one of them.
ALIKE_UNITS = {"entity": "persons", "devanagari": "pairs", "registry": "pairs"}
#: The sources whose records pair spellings: the ones the alike view
#: reads, and measure.py runs it for.
ALIKE_SOURCES = (JRC, "nepal-candidates", "tse-donors")


def alike_kind(local: Local) -> str:
    """Which spellings `local`'s records pair: "entity" (a person's
    spellings, grouped as group_counts groups them), "devanagari" (a
    romanized name and the Devanagari one) or "registry" (a filed name
    and the reference name); Ungroupable for a source that pairs none."""
    if not local.records:
        raise Ungroupable(f"{local.source} holds no records")
    for kind in ALIKE_UNITS:
        if all(kind in r for r in local.records):
            return kind
    raise Ungroupable(f"{local.source}'s records pair no two spellings of one person")


def alike_flags(local: Local, *, jobs: int = 1,
                languages: tuple[str, ...] = ()) -> dict[str, bool]:
    """Whether each person's spellings read alike, keyed by the entity or
    by the record's place in raw.jsonl, so that a key names no one. A
    person spelled two or more ways (alike_kind "entity") reads alike
    where every spelling's reading() is one; a romanized and Devanagari
    pair where the two readings are one; a filed and reference pair whose
    spellings differ where both read one surname, the same (surname(), as
    pair_counts' agreement counts it). Each distinct name is parsed once,
    in `jobs` worker processes, under the choice of `languages` where
    one is given."""
    kind = alike_kind(local)
    if kind == "entity":
        groups = {e: [n for _, n in v] for e, v in _by_entity(local).items() if len(v) > 1}
        read = _parsed(_reads, (n for names in groups.values() for n in names), jobs,
                       languages)
        return {e: len({read[n].reading for n in names}) == 1 for e, names in groups.items()}
    if kind == "devanagari":
        pairs = {str(i): (r["name"], r["devanagari"]) for i, r in enumerate(local.records)
                 if r["devanagari"].strip()}
        read = _parsed(_reads, (n for pair in pairs.values() for n in pair), jobs,
                       languages)
        return {i: read[a].reading == read[b].reading for i, (a, b) in pairs.items()}
    pairs = {str(i): (r["name"], r["registry"]) for i, r in enumerate(local.records)
             if pair_shape(r["name"], r["registry"]) not in ("the same", "no reference name")}
    family = _parsed(_surnames, (n for pair in pairs.values() for n in pair), jobs,
                     languages)
    return {i: family[a] == family[b] != "" for i, (a, b) in pairs.items()}


#: What decides a flag besides the parser: alike_fingerprint hashes them,
#: with _ALIKE_CONSTANTS, the record cut (read_records and
#: corpus_build.jsonl_lines, which place a record at its index) and the
#: fields of the readings compared.
_ALIKE_CODE = ("alike_kind", "alike_flags", "_by_entity", "_reads", "_read", "_parse", "reading",
               "_surnames", "_parsed", "surname", "_pair_words", "_bare", "_unmarked",
               "pair_shape", "_in_order")
_ALIKE_CONSTANTS = ("ALIKE_UNITS", "PAIR_MISSPELLED", "_PAIR_WORD", "_NAME_ROLES")
#: Where the alike view keeps a base's flags, beside the corpus.
ALIKE_KEPT = "alike"


def alike_fingerprint() -> str:
    """code_fingerprint of what turns the records into flags (_ALIKE_CODE)."""
    module = globals()
    return code_fingerprint(
        [*(module[name] for name in _ALIKE_CODE), read_records, corpus_build.jsonl_lines],
        [*(_stable(module[name]) for name in _ALIKE_CONSTANTS),
         repr(Reading._fields), repr(_Read._fields)])


def alike_path(local: Local, digest: str) -> Path:
    """Where `local`'s flags read by a package of `digest` are kept: keyed
    by everything they depend on besides the parser (the fetch, the
    interpreter's minor version, the code), so a key that matches is a
    reading of this base."""
    py = f"py{sys.version_info[0]}{sys.version_info[1]}"
    return (directory(local.source, create=False) / ALIKE_KEPT
            / f"{local.meta['sha256'][:12]}-{digest[:16]}-{py}-{alike_fingerprint()[:12]}.json")


def write_flags(path: Path, local: Local, flags: dict[str, bool]) -> None:
    body = {"raw_sha256": local.meta["sha256"], "code": alike_fingerprint(),
            "count": len(flags), "flags": flags}
    corpus_build.write_atomic(path, json.dumps(body, sort_keys=True).encode())


def read_flags(path: Path, local: Local) -> dict[str, bool]:
    """Flags write_flags wrote for this fetch and this code; ValueError
    for anything else (a file cut short, another fetch's, another
    version's)."""
    try:
        body = json.loads(path.read_text(encoding="utf-8"))
        flags = body["flags"]
        ok = (isinstance(flags, dict) and body["count"] == len(flags)
              and all(isinstance(v, bool) for v in flags.values()))
    except (OSError, ValueError, KeyError, TypeError) as exc:
        raise ValueError(f"{path} is not a reading this tool kept ({exc})") from None
    if not ok:
        raise ValueError(f"{path} holds another number of flags than it counts")
    if body.get("raw_sha256") != local.meta["sha256"] or body.get("code") != alike_fingerprint():
        raise ValueError(f"{path} was read from another fetch or by another version "
                         f"of this view")
    return flags


def _alike_base(root: Path, local: Local, out: Path, jobs: int) -> None:
    """`root`'s flags written to `out` in a child process (one process
    imports one nameparser), which refuses a package other than
    `root`'s."""
    import subprocess

    import snapshot
    command = [sys.executable, str(Path(_HERE) / "local_corpora.py"), "alike",
               local.source, "--tree", str(root), "--out", str(out), "--jobs", str(jobs)]
    done = subprocess.run(command, env=snapshot.child_env(), capture_output=True, text=True)
    if done.returncode:
        raise SystemExit(f"reading the base {root} failed:\n{done.stdout}{done.stderr}")


def base_flags(root: Path, local: Local, jobs: int) -> dict[str, bool]:
    """The base checkout's flags, kept for its package's digest or read
    into a kept file now, and a line saying which. Read into a folder of
    this run's own and renamed into place only once the digest, taken
    again, says the base did not change under the child (AGENTS.md's
    cache-key gotcha: publish a kept reading only once it is whole)."""
    import shutil

    import snapshot
    digest = snapshot._source_digest(root)
    path = alike_path(local, digest)
    if path.exists():
        try:
            flags = read_flags(path, local)
        except ValueError as exc:
            print(f"deleted the kept flags {path.name}: {exc}; reading the base\n")
            path.unlink(missing_ok=True)
        else:
            try:
                os.utime(path)
            except FileNotFoundError:  # another run pruned it meanwhile
                pass
            print(f"base: {root}, nameparser/ {digest[:16]}; reused the kept "
                  f"flags {path.name}\n")
            return flags
    at = snapshot.scratch(path.parent)
    try:
        _alike_base(root, local, at / path.name, jobs)
        flags = read_flags(at / path.name, local)
        if snapshot._source_digest(root) != digest:
            raise SystemExit(f"{root / 'nameparser'} changed while it was read, "
                             f"so its flags may be half old and half new; run again")
        os.replace(at / path.name, path)
    finally:
        shutil.rmtree(at, ignore_errors=True)
    snapshot._prune(path.parent, "*.json")
    print(f"base: {root}, nameparser/ {digest[:16]}; read it now\n")
    return flags


def format_alike(local: Local, flags: dict[str, bool],
                 base: dict[str, bool] | None = None) -> list[str]:
    """The lines `alike` prints: how many read alike, and against a base
    how many now read alike and how many now apart. Counts only."""
    unit = ALIKE_UNITS[alike_kind(local)]
    alike = sum(flags.values())
    line = f"{alike:,} of {len(flags):,} {unit} read alike"
    if base is None:
        return [line]
    if base.keys() != flags.keys():
        raise SystemExit("the base's flags and the tree's name other persons, "
                         "though both read the same fetch")
    now_alike = sum(flags[k] and not base[k] for k in flags)
    now_apart = sum(base[k] and not flags[k] for k in flags)
    return [f"{line} ({sum(base.values()):,} in the base)",
            f"{now_alike:,} {unit} now alike, {now_apart:,} now apart"]


#: Where a name is cut into words: spaces, commas, semicolons, slashes.
#: A hyphen stays inside a word (FNP-C), and a period inside a token
#: (M.D.) is folded away by word_key.
_TOKEN_SPLIT = re.compile(r"[\s,;/]+")
#: Kept at a word's edge though punctuation: what marks a particle
#: written to join the next word (d', al-), which the vocabulary lists
#: and this lookup is asked about.
_JOINERS = frozenset("'\u2019-")


def _strippable(char: str) -> bool:
    return unicodedata.category(char)[0] in "PS" and char not in _JOINERS


@functools.cache
def word_key(word: str) -> str:
    """One word as the lookup matches it: composed (NFC), periods dropped,
    other punctuation and symbols at its edges stripped, apostrophes and
    hyphens kept, and case folded with casefold(). 'M.D.', 'MD;' and
    '(MD)' all find 'md', while d' stays d' and never finds the initial
    D. A combining mark is part of its letter, not punctuation, so a
    final vowel sign or haraka stays. Close to the parser's acronym match
    (which drops periods and lowers case) but not the same fold:
    casefold() also folds 'ß' to 'ss'. Cached: a corpus repeats its
    words (1.88 million tokens, 169,208 distinct, on 2026-10-21)."""
    word = unicodedata.normalize("NFC", word).replace(".", "")
    start, end = 0, len(word)
    while start < end and _strippable(word[start]):
        start += 1
    while end > start and _strippable(word[end - 1]):
        end -= 1
    return word[start:end].casefold()


def _keyed(text: str) -> list[tuple[str, str]]:
    """`text` cut into words, each as (its key, the token as written),
    words that fold to nothing dropped."""
    return [(key, token) for token in _TOKEN_SPLIT.split(text)
            if (key := word_key(token))]


def words(text: str) -> list[str]:
    """`text` as the lookup's words: cut where the index cuts a name,
    each folded by word_key, empty words dropped."""
    return [key for key, _ in _keyed(text)]


@dataclass(frozen=True)
class WordIndex:
    """Per word key: the records writing it anywhere, those writing it
    after a comma, and its spellings as written, each counted by the
    records writing it (once a record, however often it repeats one).
    Plain dicts, built or read back from the cache alike, so a missing
    key reads the same from either: read them with .get(key, 0). Not
    Counters, so that a cached index needs none rebuilt over it (0.37s of
    the 0.61s a cached FEC index took to load with them, measured
    2026-10-22)."""
    anywhere: dict[str, int]
    after_comma: dict[str, int]
    spellings: dict[str, dict[str, int]]


def _names(local: Local) -> Counter[tuple[str, ...]]:
    """Each distinct tuple of a record's names (its distinct non-empty
    values under the source's corpus_keys, as the corpus reads them),
    with the records writing it: a name repeats across a source's
    records (536,981 officials, 352,104 names on 2026-10-21). Reading
    every key lets a lookup of a Devanagari word in nepal-candidates find
    the records whose Devanagari name holds it; keeping a record's names
    together counts a word both of them write once."""
    keys = local.corpus_keys
    return Counter(tuple(dict.fromkeys(record[key] for key in keys if record.get(key)))
                   for record in local.records)


def word_index(local: Local) -> WordIndex:
    anywhere: Counter[str] = Counter()
    after: Counter[str] = Counter()
    spellings: dict[str, Counter[str]] = {}
    for names, n in _names(local).items():
        before: list[tuple[str, str]] = []
        behind: list[tuple[str, str]] = []
        for name in names:
            head, _, tail = name.partition(",")
            before += _keyed(head)
            behind += _keyed(tail)
        after_keys = {key for key, _ in behind}
        for key in {key for key, _ in before} | after_keys:
            anywhere[key] += n
        for key in after_keys:
            after[key] += n
        for key, token in set(before + behind):
            spellings.setdefault(key, Counter())[token] += n
    return WordIndex(anywhere=dict(anywhere), after_comma=dict(after),
                     spellings={key: dict(seen) for key, seen in spellings.items()})


#: The functions that decide an index's contents from the records, and
#: the constants they read: a change to any makes a cached index stale,
#: so fold_fingerprint hashes them rather than trusting a version number
#: to be bumped. tests/v2/test_local_corpora.py holds these lists to what
#: the functions call and read.
_FOLD_CODE = ("word_key", "_strippable", "_keyed", "_names", "word_index")
_FOLD_CONSTANTS = ("_TOKEN_SPLIT", "_JOINERS")


def _stable(value: object) -> str:
    """repr(), with sets sorted: a frozenset's order moves with the
    process's string hashing."""
    if isinstance(value, (set, frozenset)):
        return "{" + ", ".join(sorted(_stable(v) for v in value)) + "}"
    if isinstance(value, tuple):
        return "(" + ", ".join(_stable(v) for v in value) + ")"
    if isinstance(value, re.Pattern):
        return f"re({value.pattern!r}, {value.flags})"
    return repr(value)


def _code_digest(code: types.CodeType) -> list[str]:
    """What a function does, as the interpreter will run it: its
    bytecode, the names and constants it reads, and its nested code,
    without line numbers, so moving it does not count as a change."""
    parts = [code.co_code.hex(), repr(code.co_names), repr(code.co_varnames)]
    for const in code.co_consts:
        parts += (_code_digest(const) if isinstance(const, types.CodeType)
                  else [_stable(const)])
    return parts


def code_fingerprint(functions: Iterable[Callable[..., object]],
                     extra: Iterable[str] = ()) -> str:
    """A hash of `functions` as the interpreter will run them, read from
    the running code rather than the source on disk, which may have been
    edited since; of `extra`; and of the Unicode database that
    casefold(), NFC and the category tests read and the interpreter whose
    bytecode it is, which a new Python may move: the key for a result
    cached from what that code made."""
    parts = [part for fn in functions for part in _code_digest(inspect.unwrap(fn).__code__)]
    parts += [*extra, unicodedata.unidata_version, sys.version]
    return hashlib.sha256("\0".join(parts).encode()).hexdigest()


def fold_fingerprint() -> str:
    """code_fingerprint of what turns the records into an index:
    _FOLD_CODE's functions, read_records and corpus_build.jsonl_lines
    (which read raw.jsonl into the records Local.records holds, where
    _names takes them), _FOLD_CONSTANTS and WordIndex's fields."""
    module = globals()
    return code_fingerprint(
        [*(module[name] for name in _FOLD_CODE), read_records, corpus_build.jsonl_lines],
        [*(_stable(module[name]) for name in _FOLD_CONSTANTS),
         repr([f.name for f in dataclasses.fields(WordIndex)])])


def _is_counts(value: object) -> bool:
    return isinstance(value, dict) and all(
        type(n) is int for n in value.values())


def cached_index(local: Local) -> WordIndex:
    """`local`'s word index, read from wordindex.json beside the corpus
    where its key matches and its counts are counts, else built and
    written there. The key is the records' sha256, fold_fingerprint()
    and the corpus_keys read, so a refetch, or a change to how a word is
    cut or folded or to which of a record's names are read, rebuilds it
    rather than answering from a stale index. A Local with no sha256 (a
    test's) is built and not cached. An index file that is not an index,
    or not this one, is built over, with a line on stderr: it is derived
    from the corpus, never the corpus itself."""
    sha = local.meta.get("sha256")
    if not isinstance(sha, str):
        return word_index(local)
    path = directory(local.source, create=False) / INDEX
    key = f"{sha}:{fold_fingerprint()}:{','.join(local.corpus_keys)}"
    if path.exists():
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            if (isinstance(data, dict) and data.get("key") == key
                    and _is_counts(data.get("anywhere"))
                    and _is_counts(data.get("after_comma"))
                    and isinstance(data.get("spellings"), dict)
                    and all(_is_counts(seen) for seen in data["spellings"].values())):
                return WordIndex(anywhere=data["anywhere"],
                                 after_comma=data["after_comma"],
                                 spellings=data["spellings"])
            why = "built from other records or by another fold, or not an index"
        except (OSError, ValueError) as exc:
            why = str(exc)
        print(f"rebuilding the word index at {path}: {why}", file=sys.stderr)
    index = word_index(local)
    body = json.dumps({"key": key, **dataclasses.asdict(index)}, ensure_ascii=False)
    try:
        corpus_build.write_atomic(path, body.encode())
    except OSError as exc:
        print(f"could not cache the word index at {path}: {exc}", file=sys.stderr)
    return index


@dataclass(frozen=True)
class BoxIndex:
    """A fielded source's words by box and country, counted over its
    whole extract rather than the capped corpus: per country the weight
    of every record ("" for none), and per word key and country the
    weight of the records whose given box, or family box, writes it (once
    a record, however often the box repeats it). The weight is the people
    a record stands for (Source.boxes): one ORCID holder, or the inventors
    PatentsView counts under a name."""
    totals: dict[str, int]
    given: dict[str, dict[str, int]]
    family: dict[str, dict[str, int]]


def box_index(rows: Iterable[tuple[str, str, str, int]]) -> BoxIndex:
    """The BoxIndex of `rows`, (given, family, country, weight) as a
    Source.boxes reader yields them, each box cut and folded into words
    as the word index cuts and folds a name (words)."""
    totals: Counter[str] = Counter()
    boxes: tuple[dict[str, Counter[str]], dict[str, Counter[str]]] = ({}, {})
    for given, family, country, weight in rows:
        totals[country] += weight
        for box, text in zip(boxes, (given, family)):
            for key in set(words(text)):
                box.setdefault(key, Counter())[country] += weight
    return BoxIndex(totals=dict(totals),
                    given={k: dict(v) for k, v in boxes[0].items()},
                    family={k: dict(v) for k, v in boxes[1].items()})


def box_fingerprint(source: str) -> str:
    """code_fingerprint of what turns `source`'s extract into its
    BoxIndex: its Source.boxes reader, box_index and the fold the word
    index shares (words, word_key, _strippable, _keyed, _FOLD_CONSTANTS),
    and BoxIndex's fields."""
    reader = SOURCES[source].boxes
    assert reader is not None
    module = globals()
    return code_fingerprint(
        [reader, box_index, words, word_key, _strippable, _keyed],
        [*(_stable(module[name]) for name in _FOLD_CONSTANTS),
         repr([f.name for f in dataclasses.fields(BoxIndex)])])


def _file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as held:
        while chunk := held.read(local_core.CHUNK):
            digest.update(chunk)
    return digest.hexdigest()


def cached_box_index(source: str) -> BoxIndex:
    """`source`'s BoxIndex, read from boxindex.json.gz beside the corpus
    where its key matches, else built from the cached extract and written
    there. The key is the extract's sha256, taken from the bytes on disk
    as they are read, and box_fingerprint(source), so a refetch or a
    change to how a word is cut, folded or counted rebuilds it. A file
    that is not an index, or not this one, is built over, with a line on
    stderr: it is derived from the extract, never the extract itself.
    ValueError naming the refresh where the extract is missing or cannot
    be read."""
    found = SOURCES[source]
    if found.extract is None or found.boxes is None:
        raise ValueError(f"{source} keeps no extract with its names' boxes")
    extract = found.extract()
    if not extract.exists():
        raise ValueError(f"{extract} is missing{_again(source)}")
    path = directory(source, create=False) / BOX_INDEX
    key = f"{_file_sha256(extract)}:{box_fingerprint(source)}"
    if path.exists():
        try:
            data = json.loads(gzip.decompress(path.read_bytes()))
            if (isinstance(data, dict) and data.get("key") == key
                    and _is_counts(data.get("totals"))
                    and all(isinstance(data.get(box), dict)
                            and all(_is_counts(v) for v in data[box].values())
                            for box in ("given", "family"))):
                return BoxIndex(totals=data["totals"], given=data["given"],
                                family=data["family"])
            why = "built from another extract or by another fold, or not an index"
        except (OSError, ValueError, EOFError, zlib.error) as exc:
            why = str(exc)
        print(f"rebuilding the box index at {path}: {why}", file=sys.stderr)
    else:
        print(f"building the box index of {source} from {extract.name} ...", file=sys.stderr)
    try:
        index = box_index(found.boxes(extract))
    except (EOFError, zlib.error, KeyError, AttributeError, TypeError, RuntimeError,
            ValueError) as exc:
        # A truncated or damaged extract raises any of these from gzip,
        # json or the reader (an empty one, StopIteration from inside a
        # generator, as RuntimeError); one row fails, not the run.
        raise ValueError(f"{extract} could not be read ({type(exc).__name__}: {exc})"
                         f"{_again(source)}") from None
    if _file_sha256(extract) != key.split(":", 1)[0]:
        raise ValueError(f"{extract} changed while it was read{_again(source)}")
    body = json.dumps({"key": key, **dataclasses.asdict(index)}, ensure_ascii=False)
    try:
        corpus_build.write_atomic(path, gzip.compress(body.encode(), 6, mtime=0))
    except OSError as exc:
        print(f"could not cache the box index at {path}: {exc}", file=sys.stderr)
    return index


def phrase_counts(local: Local, keys: list[str]) -> tuple[int, int]:
    """The records writing the words `keys` in a row (a spaced query,
    'Ph. D.' as ['ph', 'd']), and those where such a run starts after
    the first comma. The separators between the words are not compared:
    'MD/PhD' finds 'MD, PhD' and 'Smith MD, PhD' too. Scans the names,
    since a phrase is no key of the index; none is scanned when one of
    its words is written nowhere."""
    if any(not local.index.anywhere.get(key, 0) for key in keys):
        return 0, 0
    n = len(keys)
    anywhere = after = 0
    for names, count in _names(local).items():
        found = found_after = False
        for name in names:
            head, _, tail = name.partition(",")
            first = words(head)
            got = first + words(tail)
            starts = [i for i in range(len(got) - n + 1) if got[i:i + n] == keys]
            found = found or bool(starts)
            found_after = found_after or any(i >= len(first) for i in starts)
        anywhere += count * found
        after += count * found_after
    return anywhere, after


@dataclass(frozen=True)
class Lookup:
    """One word's answer: the records writing it anywhere and after a
    comma; for a single word its spellings, for a spaced one the records
    writing its words joined into one."""
    anywhere: int
    after_comma: int
    spellings: Counter[str]
    joined: int | None


def lookup(local: Local, word: str) -> Lookup | None:
    """`word` looked up in `local`, or None when nothing is left of it
    once folded (words). A spaced word is matched as its words in a row."""
    keys = words(word)
    if not keys:
        return None
    index = local.index
    if len(keys) == 1:
        return Lookup(index.anywhere.get(keys[0], 0), index.after_comma.get(keys[0], 0),
                      Counter(index.spellings.get(keys[0], {})), None)
    anywhere, after = phrase_counts(local, keys)
    return Lookup(anywhere, after, Counter(), index.anywhere.get("".join(keys), 0))


# -- the command line ----------------------------------------------------------

def _positive(text: str) -> int:
    """An argparse type: a whole number of 1 or more."""
    value = int(text)
    if value < 1:
        raise argparse.ArgumentTypeError(f"{text} is not 1 or more")
    return value


def _alike_command(local: Local, args: argparse.Namespace) -> int:
    """`alike`: the tree's flags (this checkout's, or --tree's, checked
    to be the package imported), against --base's where one is named;
    under --languages, the tree's flags under that choice, against the
    default's (--base's, or the tree's own); exits 1 where a person
    moved, as the other base checks do."""
    import snapshot
    root = Path(args.tree).resolve() if args.tree else snapshot.REPO_ROOT
    languages = args.languages
    base = snapshot.base_root(args.base, root, bool(languages)) if args.base else None
    try:
        alike_kind(local)
        old = base_flags(base, local, args.jobs) if base is not None else None
    except (CorpusDamaged, Ungroupable) as exc:
        raise SystemExit(str(exc)) from None
    if args.tree:
        sys.path.insert(0, str(root))
    import nameparser
    snapshot.check_source(nameparser.__file__, root)
    if languages and old is None:
        old = alike_flags(local, jobs=args.jobs)
    flags = alike_flags(local, jobs=args.jobs, languages=languages)
    snapshot.check_source(nameparser.__file__, root)
    if args.out:
        write_flags(args.out, local, flags)
        return 0
    print(local.header())
    if base is not None:
        print(snapshot.head_line(root, base, languages))
    if languages:
        print(f"under the choice {', '.join(languages)}, against the default's "
              f"flags\n")
    print("\n".join(format_alike(local, flags, old)))
    return int(old is not None and any(flags[k] != old[k] for k in flags))


def _tags(value: str) -> tuple[str, ...]:
    """--languages' comma-separated tags, at least one."""
    tags = tuple(t.strip() for t in value.split(",") if t.strip())
    if not tags:
        raise argparse.ArgumentTypeError("needs at least one tag")
    return tags


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = ap.add_subparsers(dest="command", required=True)
    get = sub.add_parser("fetch", help="fetch a source into the cache")
    get.add_argument("source", choices=sorted(SOURCES))
    get.add_argument("--refresh", action="store_true",
                     help="fetch again although a copy is cached")
    show = sub.add_parser("tally", help="count the text after each comma")
    show.add_argument("source", choices=sorted(SOURCES))
    show.add_argument("--top", type=int, default=50, metavar="N")
    pair = sub.add_parser("pairs", help="sort each filed name by how it departs "
                                        "from the reference name beside it")
    pair.add_argument("source", choices=sorted(SOURCES))
    pair.add_argument("--top", type=int, default=15, metavar="N",
                      help="words left out or added to list (default 15)")
    pair.add_argument("--agreement", action="store_true",
                      help="also parse each pair that differs and count the "
                           "pairs whose two spellings share a surname")
    group = sub.add_parser("groups", help="compare the readings of each person's "
                                          "spellings, by the scripts they are in")
    group.add_argument("source", choices=sorted(SOURCES))
    group.add_argument("--top", type=_positive, default=20, metavar="N",
                       help="pairs of scripts, and titles and suffixes, to list "
                            "(default 20)")
    alike = sub.add_parser("alike", help="count the persons whose spellings read "
                                         "alike, and against --base the ones that "
                                         "moved")
    alike.add_argument("source", choices=sorted(ALIKE_SOURCES))
    alike.add_argument("--base", metavar="PATH",
                       help="compare with this checkout's flags, kept by its "
                            "package's digest")
    alike.add_argument("--tree", metavar="PATH", help="read with another checkout")
    alike.add_argument("--out", type=Path, metavar="PATH",
                       help="write the tree's flags here (what --base's child does)")
    alike.add_argument("--languages", type=_tags, default=(), metavar="TAGS",
                       help="read under a choice of languages, comma-separated "
                            "BCP 47 tags (ne,hi), and count the persons it moves "
                            "against the default's flags")
    for command in (pair, group, alike):
        command.add_argument("--jobs", type=_positive, metavar="N",
                             default=os.cpu_count() or 1,
                             help="parse in N worker processes (default: every CPU)")
    args = ap.parse_args(argv)
    if args.command == "alike" and args.base and args.out:
        ap.error("--base compares; --out writes the tree's flags, for a child")
    if args.command == "alike" and args.languages and args.out:
        ap.error("--languages reads a choice against the default's flags; "
                 "--out writes the default's, for a child")
    if args.command == "fetch":
        local = None
        if not args.refresh:
            try:
                local = load(args.source)
            except ValueError as exc:  # a damaged copy: fetch over it
                print(f"the cached copy is unusable, fetching again: {exc}",
                      file=sys.stderr)
        if local is None:
            if args.refresh and (renew := SOURCES[args.source].renew):
                renew()
            local = fetch(args.source)
            where = f"fetched into {directory(args.source)}"
        else:
            where = f"cached in {directory(args.source)}; --refresh fetches again"
        print(local.header())
        print(where)
        print(f"{local.meta['names']:,} distinct names in {corpus_path(args.source)}")
        if local.meta["detail"]:
            print(", ".join(f"{k} {v:,}" if isinstance(v, int) else f"{k} {v}"
                            for k, v in sorted(local.meta["detail"].items())))
        return 0
    local = require(args.source)
    if args.command == "alike":
        return _alike_command(local, args)
    if args.command == "pairs":
        try:
            found = pair_counts(local, agreement=args.agreement, jobs=args.jobs)
        except ValueError as exc:  # CorpusDamaged included: the records, read here first
            raise SystemExit(str(exc)) from None
        print(local.header())
        print(format_pairs(found, args.top))
        return 0
    if args.command == "groups":
        try:
            grouped = group_counts(local, jobs=args.jobs)
        except (CorpusDamaged, Ungroupable) as exc:  # the records, read here first
            raise SystemExit(str(exc)) from None
        print(local.header())
        print(format_groups(grouped, args.top))
        return 0
    try:
        parts, with_comma = tally(local)
    except CorpusDamaged as exc:  # the records, read here first
        raise SystemExit(str(exc)) from None
    print(local.header())
    print(f"{with_comma:,} hold a comma; the text after each comma, by "
          f"{SOURCES[args.source].unit} writing it:")
    for text, n in parts.most_common(args.top):
        print(f"  {n:>9,}  {text}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
