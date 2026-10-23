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
    uv run python tools/differential/snapshot.py --local ctgov-officials

`fetch` writes three files into local/<source>/ under
$NAMEPARSER_TOOLS_CACHE (default ~/.cache/nameparser-tools), and
`snapshot.py --local --record` keeps its snapshot beside them:

- raw.jsonl -- one record per name as the source gave it, with where it
  came from where the source says: a ClinicalTrials.gov official, with
  the study and role; one distinct FEC, Taiwan or UK donor name, alone;
  one distinct pair of a TSE donor's filed name and the tax registry's
  name for the same donor; one distinct PSC filed name, with its four
  boxes and nationality. The counts are counted from here.
- corpus.jsonl -- the distinct names, in the corpus line format
  snapshot.py and compare.py --corpus read.
- meta.json -- the source's own date for the data, what was fetched, and
  the sha256 of both files, checked on every load: a truncated file
  would otherwise read as a run of false zeros.
- snapshot.jsonl, and snapshot.jsonl.source.json naming the corpus it
  was recorded from, so a snapshot is never compared with a corpus
  fetched after it.
- wordindex.json -- the word index tools/name_usage.py looks words up
  in, written on first use and keyed to the records and the fold
  (cached_index), so a single-word lookup parses neither raw.jsonl's
  records nor the names (load() still reads both files for their
  sha256).

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
(tse-donors), local_tw.py (tw-donors), local_ukec.py (ukec-individuals)
and local_psc.py (psc-individuals).
"""
from __future__ import annotations

import argparse
import functools
import dataclasses
import difflib
import hashlib
import inspect
import json
import re
import sys
import time
import types
import unicodedata
from collections import Counter
from collections.abc import Callable, Iterable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

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
from local_psc import PSC, check_psc, fetch_psc, renew_psc  # noqa: E402
from local_tse import check_tse, fetch_tse  # noqa: E402
from local_tw import fetch_tw  # noqa: E402
from local_ukec import fetch_ukec  # noqa: E402

RAW, CORPUS, META, SNAPSHOT = "raw.jsonl", "corpus.jsonl", "meta.json", "snapshot.jsonl"
INDEX = "wordindex.json"
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

    PSC: Source(
        credit="Companies House people with significant control, individuals "
               "(a public register: Companies House sets no terms on its use, "
               "and data protection law applies to the names)",
        unit="filed names", fetch=fetch_psc, renew=renew_psc, check=check_psc),
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
    if any(not isinstance(r.get("name"), str) for r in fetched.records):
        raise ValueError(f"{source}: a fetched record has no name")
    raw = "".join(corpus_build.jsonl_line(r, sort_keys=True) + "\n"
                  for r in fetched.records).encode()
    lines = corpus_build.corpus_lines(
        {"text": r["name"], "shape": None} for r in fetched.records)
    corpus = ("\n".join(lines) + "\n").encode()
    corpus_build.write_atomic(path / RAW, raw)
    corpus_build.write_atomic(path / CORPUS, corpus)
    meta = {"version": META_VERSION, "source": source,
            "data_date": fetched.data_date,
            "fetched": time.strftime("%Y-%m-%d"),
            "records": len(fetched.records), "names": len(lines),
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


def surname(name: str) -> str:
    """The last word of the family name parse() reads in `name`, in
    capitals without accents, or "" where it reads none: the word two
    spellings of one person should share unless the last surname itself
    is what one leaves out (a particle or a middle name left out, a
    middle name shortened, accents or case changed). Two readings with no
    surname do not share one."""
    from nameparser import parse

    family = _pair_words(parse(name).family)
    return family[-1] if family else ""


def pair_counts(local: Local, *, agreement: bool = False) -> PairCounts:
    """Each record's pair_shape. A source whose records carry no
    reference name raises ValueError. With `agreement`, every pair with a
    reference name that differs is parsed both ways and its two surnames
    compared, agreeing only where both read one, which
    parses each distinct name once (39s for tse-donors on 2026-10-22)."""
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
            for name in (filed, reference):
                if name not in seen:
                    seen[name] = surname(name)
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


def _names(local: Local) -> Counter[str]:
    """Each distinct name with the records writing it: a name repeats
    across a source's records (536,981 officials, 352,104 names on
    2026-10-21)."""
    return Counter(record["name"] for record in local.records)


def word_index(local: Local) -> WordIndex:
    anywhere: Counter[str] = Counter()
    after: Counter[str] = Counter()
    spellings: dict[str, Counter[str]] = {}
    for name, n in _names(local).items():
        head, _, tail = name.partition(",")
        before, behind = _keyed(head), _keyed(tail)
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
    written there. The key is the records' sha256 and fold_fingerprint(),
    so a refetch, or a change to how a word is cut or folded, rebuilds it
    rather than answering from a stale index. A Local with no sha256 (a
    test's) is built and not cached. An index file that is not an index,
    or not this one, is built over, with a line on stderr: it is derived
    from the corpus, never the corpus itself."""
    sha = local.meta.get("sha256")
    if not isinstance(sha, str):
        return word_index(local)
    path = directory(local.source, create=False) / INDEX
    key = f"{sha}:{fold_fingerprint()}"
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
    for name, count in _names(local).items():
        head, _, tail = name.partition(",")
        first = words(head)
        got = first + words(tail)
        starts = [i for i in range(len(got) - n + 1) if got[i:i + n] == keys]
        if starts:
            anywhere += count
        if any(i >= len(first) for i in starts):
            after += count
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
    args = ap.parse_args(argv)
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
    if args.command == "pairs":
        try:
            found = pair_counts(local, agreement=args.agreement)
        except ValueError as exc:  # CorpusDamaged included: the records, read here first
            raise SystemExit(str(exc)) from None
        print(local.header())
        print(format_pairs(found, args.top))
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
