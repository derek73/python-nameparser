"""Local corpora: whole names fetched into the cache, never committed.

A local corpus does the SURVEY job of the five in
mechanisms.md#NAME-DATA-JOBS ("the job decides where its data lives"):
real names as people type them, read with the snapshot's machinery, kept out
of the repository because the names are real people's and nobody vetted
them for publication. It also does WATCH outside CI (snapshot.py --local),
but neither gates CI nor feeds SCORE, whose scorer reads only committed
fields files: no reviewer and no CI run can see it. What reaches the
repository is what a contributor cites: counts, and shapes written with
made-up names.

    uv run python tools/differential/local_corpora.py fetch ctgov-officials
    uv run python tools/differential/local_corpora.py tally ctgov-officials
    uv run python tools/differential/snapshot.py --local ctgov-officials

`fetch` writes three files into local/<source>/ under
$NAMEPARSER_TOOLS_CACHE (default ~/.cache/nameparser-tools), and
`snapshot.py --local --record` keeps its snapshot beside them:

- raw.jsonl -- one record per name as the source gave it, with where it
  came from. The counts are counted from here.
- corpus.jsonl -- the distinct names, in the corpus line format
  snapshot.py and compare.py --corpus read.
- meta.json -- the source's own date for the data, what was fetched, and
  the sha256 of both files, checked on every load: a truncated file
  would otherwise read as a run of false zeros.
- snapshot.jsonl, and snapshot.jsonl.source.json naming the corpus it
  was recorded from, so a snapshot is never compared with a corpus
  fetched after it.

A live source has no fixed snapshot to pin, so the cached copy IS the
pin: a count quoted from it names the data date the header prints, and
a later fetch may differ. A new source is a SOURCES row: a fetch
function returning the records and the source's data date.

ctgov-officials -- every overall official of every study on
ClinicalTrials.gov, whatever the role (principal investigators, study
directors and chairs, and a few sub-investigators and officials with no
role), the name as the sponsor's staff typed it into a free-text field,
with credentials, job titles and typos left in. Fetched from API v2
(NLM). ClinicalTrials.gov's terms ask anyone redistributing the data to
credit it, show NLM's processing date and say what was changed: every
report here and the tools/name_usage.py row carry the credit and the
date, and the names are kept unchanged.
"""
from __future__ import annotations

import argparse
import functools
import hashlib
import http.client
import json
import os
import re
import sys
import time
import unicodedata
import urllib.error
import urllib.parse
from collections import Counter
from collections.abc import Callable, Iterable, Iterator
from dataclasses import dataclass
from pathlib import Path
from typing import Any

# The shared fetch and cache helpers (corpus_build.py), found by putting
# this directory on sys.path: see corpus_build's docstring for why.
_HERE = str(Path(__file__).resolve().parent)
if _HERE not in sys.path:
    sys.path.append(_HERE)

import corpus_build  # noqa: E402

USER_AGENT = ("python-nameparser local_corpora "
              "(https://github.com/derek73/python-nameparser)")
RAW, CORPUS, META, SNAPSHOT = "raw.jsonl", "corpus.jsonl", "meta.json", "snapshot.jsonl"
META_VERSION = 2  # 2: corpus.jsonl's sha256, and the source's detail nested
#: The keys load() needs in meta.json, with their types.
_META_KEYS = {"version": int, "source": str, "data_date": str, "records": int,
              "names": int, "sha256": str, "corpus_sha256": str, "detail": dict}


@dataclass(frozen=True)
class Fetched:
    """What a source's fetch returns: one record per name, each holding
    at least "name", and the source's own date for the data."""
    records: list[dict[str, str]]
    data_date: str
    #: Anything else worth keeping (API version, counts), stored in
    #: meta.json under "detail", where it cannot replace a key load() checks.
    detail: dict[str, Any]


@dataclass(frozen=True)
class Source:
    credit: str
    #: What one record is, for counts: "officials".
    unit: str
    fetch: Callable[[], Fetched]


@dataclass(frozen=True)
class Local:
    """A local corpus as loaded: its records and meta.json."""
    source: str
    records: list[dict[str, str]]
    meta: dict[str, Any]

    def header(self) -> str:
        """The attribution every report opens with."""
        return (f"{SOURCES[self.source].credit}, data as of "
                f"{self.meta['data_date']}; {len(self.records):,} "
                f"{SOURCES[self.source].unit} (local corpus {self.source})")

    @functools.cached_property
    def index(self) -> WordIndex:
        """The word index, built on first use: a few seconds over the
        whole ClinicalTrials.gov corpus."""
        return word_index(self)


# -- ClinicalTrials.gov ------------------------------------------------------

CTGOV_API = "https://clinicaltrials.gov/api/v2"
CTGOV_PAGE = 1000  # the API's largest page
CTGOV_FIELDS = "NCTId,OverallOfficialName,OverallOfficialRole"
CTGOV_RETRIES = 4
#: What a long run of requests meets and a retry survives: a refused or
#: dropped connection or a timeout (OSError, which URLError and HTTPError
#: are), a body cut short in the read (http.client's IncompleteRead), a
#: 5xx or a 429; and, caught apart from these, a body that arrived but
#: does not parse.
_TRANSIENT = (OSError, http.client.HTTPException)


class _Unparsed(Exception):
    """A response body that is not JSON: cut short in transit."""


def _get_json(url: str) -> dict[str, Any]:
    """`url`'s JSON object, retried with a backoff and a line on stderr
    for each retry: one page per thousand studies (608 on 2026-10-21),
    and starting over would cost the whole run. Any other 4xx is the
    request's fault and is raised, as is the last attempt's error."""
    for attempt in range(CTGOV_RETRIES):
        try:
            body = corpus_build.fetch_bytes(url, user_agent=USER_AGENT,
                                            timeout=60, delay=0.1)
            try:
                data = corpus_build.parse_json(body, url)
            except ValueError as exc:
                raise _Unparsed(str(exc)) from None
            break
        except (*_TRANSIENT, _Unparsed) as exc:
            wait = 2 ** attempt
            if isinstance(exc, urllib.error.HTTPError):
                if exc.code < 500 and exc.code != 429:
                    raise
                after = exc.headers.get("Retry-After", "") if exc.headers else ""
                if after.isdigit():
                    wait = max(wait, min(int(after), 60))
            if attempt == CTGOV_RETRIES - 1:
                raise
            if isinstance(exc, urllib.error.HTTPError):
                exc.close()  # an HTTPError holds the response open
            print(f"  retrying in {wait}s after {type(exc).__name__}: {url}",
                  file=sys.stderr)
            time.sleep(wait)
    if not isinstance(data, dict):
        raise ValueError(f"{url} answered {type(data).__name__}, not an object")
    return data


def _ctgov_version() -> tuple[str, str]:
    data = _get_json(f"{CTGOV_API}/version")
    return str(data["dataTimestamp"]), str(data["apiVersion"])


def _ctgov_pages() -> Iterator[dict[str, Any]]:
    token = ""
    while True:
        query = {"pageSize": CTGOV_PAGE, "fields": CTGOV_FIELDS}
        if token:
            query["pageToken"] = token
        else:
            query["countTotal"] = "true"
        page = _get_json(f"{CTGOV_API}/studies?{urllib.parse.urlencode(query)}")
        yield page
        token = page.get("nextPageToken", "")
        if not token:
            return


def fetch_ctgov() -> Fetched:
    """Every study's overall officials, in the API's order.

    The registry is refreshed daily, so the data date is read before and
    after: a fetch that straddles a refresh mixes two days and is
    refused. A study paged twice is refused, since its officials would
    count twice, and the studies paged must number the totalCount the
    first page states, so a fetch cut short cannot pass for the
    registry. An official
    with no name is counted rather than dropped in silence, so a renamed
    field shows as a count in the header instead of a smaller registry."""
    before, api = _ctgov_version()
    records: list[dict[str, str]] = []
    total: int | None = None
    studies: set[str] = set()
    nameless = 0
    for number, page in enumerate(_ctgov_pages(), 1):
        if total is None:
            total = int(page["totalCount"])
        if number % 50 == 0:
            print(f"  {len(studies):,} of {total:,} studies", file=sys.stderr)
        for study in page["studies"]:
            section = study["protocolSection"]
            nct = section["identificationModule"]["nctId"]
            if nct in studies:
                raise ValueError(f"{nct} was paged twice: the pages shifted "
                                 f"under the fetch; fetch again")
            studies.add(nct)
            for official in section.get("contactsLocationsModule", {}).get(
                    "overallOfficials", []):
                if official.get("name"):
                    records.append({"name": official["name"], "study": nct,
                                    "role": official.get("role", "")})
                else:
                    nameless += 1
    after, _ = _ctgov_version()
    if after != before:
        raise ValueError(f"ClinicalTrials.gov refreshed during the fetch "
                         f"({before} -> {after}); fetch again")
    if len(studies) != total:
        raise ValueError(f"paged {len(studies):,} studies of the "
                         f"{total:,} the API counted; fetch again")
    return Fetched(records, before, {"api_version": api, "studies": total,
                                     "officials_without_a_name": nameless})


SOURCES: dict[str, Source] = {
    "ctgov-officials": Source(
        credit="ClinicalTrials.gov (NLM) study officials", unit="officials",
        fetch=fetch_ctgov),
}


# -- the cache ---------------------------------------------------------------

def directory(source: str) -> Path:
    if source not in SOURCES:
        raise ValueError(f"no local corpus {source!r}; the sources are "
                         + ", ".join(sorted(SOURCES)))
    return corpus_build.cache_dir(f"local/{source}")


def _lines(texts: Iterable[str]) -> bytes:
    """`texts` as lines of a JSONL file, escaped as corpus_build.LINE_BREAKS
    says."""
    return "".join(t.translate(corpus_build.LINE_BREAKS) + "\n" for t in texts).encode()


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
    raw = _lines(json.dumps(r, ensure_ascii=False, sort_keys=True)
                 for r in fetched.records)
    corpus = _lines(corpus_build.corpus_lines(
        {"text": r["name"], "shape": None} for r in fetched.records))
    _write(path / RAW, raw)
    _write(path / CORPUS, corpus)
    meta = {"version": META_VERSION, "source": source,
            "data_date": fetched.data_date,
            "fetched": time.strftime("%Y-%m-%d"),
            "records": len(fetched.records), "names": corpus.count(b"\n"),
            "sha256": hashlib.sha256(raw).hexdigest(),
            "corpus_sha256": hashlib.sha256(corpus).hexdigest(),
            "detail": fetched.detail}
    _write(path / META, json.dumps(meta, indent=2).encode())
    return Local(source, fetched.records, meta)


def _write(path: Path, body: bytes) -> None:
    partial = path.with_name(path.name + ".part")
    partial.write_bytes(body)
    os.replace(partial, path)


def load(source: str) -> Local | None:
    """The cached corpus, or None when it was never fetched. Anything
    else that is not the corpus fetch() wrote -- a meta.json of another
    version or shape, a raw.jsonl or corpus.jsonl its sha256 does not
    match, a record without a name -- raises ValueError naming the way
    out: a damaged file must not read as a smaller corpus."""
    path = directory(source)
    if not (path / META).exists():
        return None
    again = f"; fetch it again: local_corpora.py fetch {source} --refresh"
    try:
        meta = json.loads((path / META).read_text(encoding="utf-8"))
    except ValueError as exc:
        raise ValueError(f"{path / META} is not JSON ({exc}){again}") from None
    if not isinstance(meta, dict) or meta.get("version") != META_VERSION:
        raise ValueError(f"{path / META} was not written by this version of "
                         f"this tool{again}")
    for key, kind in _META_KEYS.items():
        value = meta.get(key)
        if not isinstance(value, kind) or isinstance(value, bool):
            raise ValueError(f"{path / META} has no {kind.__name__} {key!r}{again}")
    bodies = {}
    for name, key in ((RAW, "sha256"), (CORPUS, "corpus_sha256")):
        body = (path / name).read_bytes() if (path / name).exists() else b""
        if hashlib.sha256(body).hexdigest() != meta[key]:
            raise ValueError(f"{path / name} does not match the sha256 in "
                             f"{META}{again}")
        bodies[name] = body
    raw = bodies[RAW]
    # split, not splitlines: a record may hold a line break splitlines
    # would cut it at (written escaped since meta version 2, but a reader
    # should not depend on that).
    records = [json.loads(line) for line in raw.decode().split("\n") if line]
    if any(not isinstance(r, dict) or not isinstance(r.get("name"), str)
           for r in records):
        raise ValueError(f"{path / RAW} holds a record without a name{again}")
    return Local(source, records, meta)


def corpus_path(source: str) -> Path:
    return directory(source) / CORPUS


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


def word_key(word: str) -> str:
    """One word as the lookup matches it: composed (NFC), periods dropped,
    other punctuation and symbols at its edges stripped, apostrophes and
    hyphens kept, and case folded with casefold(). 'M.D.', 'MD;' and
    '(MD)' all find 'md', while d' stays d' and never finds the initial
    D. A combining mark is part of its letter, not punctuation, so a
    final vowel sign or haraka stays. Close to the parser's acronym match
    (which drops periods and lowers case) but not the same fold:
    casefold() also folds 'ß' to 'ss'."""
    word = unicodedata.normalize("NFC", word).replace(".", "")
    start, end = 0, len(word)
    while start < end and _strippable(word[start]):
        start += 1
    while end > start and _strippable(word[end - 1]):
        end -= 1
    return word[start:end].casefold()


def words(text: str) -> list[str]:
    """`text` as the lookup's words: cut where the index cuts a name,
    each folded by word_key, empty words dropped."""
    return [k for k in map(word_key, _TOKEN_SPLIT.split(text)) if k]


@dataclass(frozen=True)
class WordIndex:
    """Per word key: the records writing it anywhere, those writing it
    after a comma, and its spellings as written, each counted by the
    records writing it (once a record, however often it repeats one)."""
    anywhere: Counter[str]
    after_comma: Counter[str]
    spellings: dict[str, Counter[str]]


def word_index(local: Local) -> WordIndex:
    anywhere: Counter[str] = Counter()
    after: Counter[str] = Counter()
    spellings: dict[str, Counter[str]] = {}
    for record in local.records:
        head, _, tail = record["name"].partition(",")
        seen: set[str] = set()
        seen_after: set[str] = set()
        written: set[tuple[str, str]] = set()
        for text, bucket in ((head, seen), (tail, seen_after)):
            for token in _TOKEN_SPLIT.split(text):
                key = word_key(token)
                if key:
                    bucket.add(key)
                    written.add((key, token))
        anywhere.update(seen | seen_after)
        after.update(seen_after)
        for key, token in written:
            spellings.setdefault(key, Counter())[token] += 1
    return WordIndex(anywhere, after, spellings)


def phrase_counts(local: Local, keys: list[str]) -> tuple[int, int]:
    """The records writing the words `keys` in a row (a spaced query,
    'Ph. D.' as ['ph', 'd']), and those where such a run starts after
    the first comma. The separators between the words are not compared:
    'MD/PhD' finds 'MD, PhD' and 'Smith MD, PhD' too. Scans every record,
    since a phrase is no key of the index."""
    n = len(keys)
    anywhere = after = 0
    for record in local.records:
        head, _, tail = record["name"].partition(",")
        first = words(head)
        got = first + words(tail)
        starts = [i for i in range(len(got) - n + 1) if got[i:i + n] == keys]
        if starts:
            anywhere += 1
        if any(i >= len(first) for i in starts):
            after += 1
    return anywhere, after


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
    local = load(args.source)
    if local is None:
        raise SystemExit(f"{args.source} is not fetched: "
                         f"local_corpora.py fetch {args.source}")
    parts, with_comma = tally(local)
    print(local.header())
    print(f"{with_comma:,} hold a comma; the text after each comma, by "
          f"{SOURCES[args.source].unit} writing it:")
    for text, n in parts.most_common(args.top):
        print(f"  {n:>9,}  {text}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
