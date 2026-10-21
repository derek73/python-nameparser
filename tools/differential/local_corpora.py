"""Local corpora: whole names fetched into the cache, never committed.

A local corpus is the Survey job in mechanisms.md's NAME-DATA-JOBS: real
names as people type them, read with the snapshot's machinery, kept out
of the repository because the names are real people's and nobody vetted
them for publication. It can do every job a committed corpus does except
gate CI, since no reviewer and no CI run can see it. What reaches the
repository is what a contributor cites: counts, and shapes written with
made-up names.

    uv run python tools/differential/local_corpora.py fetch ctgov-officials
    uv run python tools/differential/local_corpora.py tally ctgov-officials
    uv run python tools/differential/snapshot.py --local ctgov-officials

Each source writes three files into local/<source>/ under
$NAMEPARSER_TOOLS_CACHE (default ~/.cache/nameparser-tools):

- raw.jsonl -- one record per name as the source gave it, with where it
  came from. The counts are counted from here.
- corpus.jsonl -- the distinct names, in the corpus line format
  snapshot.py and compare.py --corpus read.
- meta.json -- the source's own date for the data, what was fetched, and
  raw.jsonl's sha256, checked on every load: a truncated file would
  otherwise read as a run of false zeros.

A live source has no fixed snapshot to pin, so the cached copy IS the
pin: a count quoted from it names the data date the header prints, and
a later fetch may differ. A new source is a SOURCES row: a fetch
function returning the records and the source's data date.

ctgov-officials -- every study official on ClinicalTrials.gov (the
overall officials: principal investigators, study directors and chairs),
the name as the sponsor's staff typed it into a free-text field, with
credentials, job titles and typos left in. Fetched from API v2 (NLM).
ClinicalTrials.gov's terms ask anyone redistributing the data to credit
it, show NLM's processing date and say what was changed; every report
here opens with both, and the names are kept unchanged.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import sys
import time
import urllib.error
import urllib.parse
from collections import Counter
from collections.abc import Callable, Iterator
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
META_VERSION = 1


@dataclass(frozen=True)
class Fetched:
    """What a source's fetch returns: one record per name, each holding
    at least "name", and the source's own date for the data."""
    records: list[dict[str, str]]
    data_date: str
    #: Anything else the header should show (API version, counts).
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


# -- ClinicalTrials.gov ------------------------------------------------------

CTGOV_API = "https://clinicaltrials.gov/api/v2"
CTGOV_PAGE = 1000  # the API's largest page
CTGOV_FIELDS = "NCTId,OverallOfficialName,OverallOfficialRole"
CTGOV_RETRIES = 4


def _get_json(url: str) -> dict[str, Any]:
    """`url`'s JSON object, retried with a backoff: a five-minute run of
    600 requests meets the odd 5xx or timeout, and starting over would
    cost the whole run. A 4xx is the request's fault and is raised."""
    for attempt in range(CTGOV_RETRIES):
        try:
            body = corpus_build.fetch_bytes(url, user_agent=USER_AGENT,
                                            timeout=60, delay=0.1)
            break
        except (urllib.error.URLError, TimeoutError) as exc:
            if (isinstance(exc, urllib.error.HTTPError) and exc.code < 500
                    or attempt == CTGOV_RETRIES - 1):
                raise
            if isinstance(exc, urllib.error.HTTPError):
                exc.close()  # an HTTPError holds the response open
            time.sleep(2 ** attempt)
    data = corpus_build.parse_json(body, url)
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
    refused. And the studies paged must number the totalCount the first
    page states, so a fetch cut short cannot pass for the registry."""
    before, api = _ctgov_version()
    records: list[dict[str, str]] = []
    total: int | None = None
    studies = 0
    for number, page in enumerate(_ctgov_pages(), 1):
        if total is None:
            total = int(page["totalCount"])
        if number % 50 == 0:  # some 600 pages, five minutes or more
            print(f"  {studies:,} of {total:,} studies", file=sys.stderr)
        for study in page["studies"]:
            studies += 1
            section = study["protocolSection"]
            nct = section["identificationModule"]["nctId"]
            for official in section.get("contactsLocationsModule", {}).get(
                    "overallOfficials", []):
                if official.get("name"):
                    records.append({"name": official["name"], "study": nct,
                                    "role": official.get("role", "")})
    after, _ = _ctgov_version()
    if after != before:
        raise ValueError(f"ClinicalTrials.gov refreshed during the fetch "
                         f"({before} -> {after}); fetch again")
    if studies != total:
        raise ValueError(f"paged {studies:,} studies of the {total:,} the "
                         f"API counted; the fetch was cut short, fetch again")
    return Fetched(records, before, {"api_version": api, "studies": studies})


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


def fetch(source: str) -> Local:
    """Fetch `source` and write its three files, meta.json last. A run
    that dies between the writes leaves a raw.jsonl the old meta.json's
    sha256 does not match, which load() refuses."""
    fetched = SOURCES[source].fetch()
    if not fetched.records:
        raise ValueError(f"{source}: the fetch found no names")
    path = directory(source)
    raw = "".join(json.dumps(r, ensure_ascii=False, sort_keys=True) + "\n"
                  for r in fetched.records).encode()
    _write(path / RAW, raw)
    corpus = corpus_build.corpus_lines(
        {"text": r["name"], "shape": None} for r in fetched.records)
    _write(path / CORPUS, ("\n".join(corpus) + "\n").encode())
    meta = {"version": META_VERSION, "source": source,
            "data_date": fetched.data_date,
            "fetched": time.strftime("%Y-%m-%d"),
            "records": len(fetched.records), "names": len(corpus),
            "sha256": hashlib.sha256(raw).hexdigest(), **fetched.detail}
    _write(path / META, json.dumps(meta, indent=2).encode())
    return Local(source, fetched.records, meta)


def _write(path: Path, body: bytes) -> None:
    partial = path.with_name(path.name + ".part")
    partial.write_bytes(body)
    os.replace(partial, path)


def load(source: str) -> Local | None:
    """The cached corpus, or None when it was never fetched. A raw.jsonl
    that does not match meta.json's sha256 or count raises ValueError
    naming the way out: a truncated file must not read as a smaller
    corpus."""
    path = directory(source)
    if not (path / META).exists():
        return None
    meta = json.loads((path / META).read_text(encoding="utf-8"))
    if meta.get("version") != META_VERSION:
        raise ValueError(f"{path / META} was written by another version of "
                         f"this tool; fetch {source} again")
    raw = (path / RAW).read_bytes() if (path / RAW).exists() else b""
    if hashlib.sha256(raw).hexdigest() != meta["sha256"]:
        raise ValueError(f"{path / RAW} does not match the sha256 in "
                         f"{META}; fetch {source} again")
    records = [json.loads(line) for line in raw.decode().splitlines()]
    if len(records) != meta["records"]:
        raise ValueError(f"{path / RAW} holds {len(records):,} records, "
                         f"{META} says {meta['records']:,}")
    return Local(source, records, meta)


def corpus_path(source: str) -> Path:
    return directory(source) / CORPUS


# -- views -------------------------------------------------------------------

def after_commas(name: str) -> list[str]:
    """Each part of `name` after a comma, as written, stripped of the
    spaces around it: 'Ann Lee, MD, PhD' gives ['MD', 'PhD'].
    'MBBS,FCPS' is two parts, which is how the parser splits it too."""
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


_TOKEN_SPLIT = re.compile(r"[\s,]+")


def word_key(word: str) -> str:
    """A word as the lookup matches it: periods and edge brackets or
    quotes dropped and case folded, as the parser matches an acronym, so
    'M.D.' finds 'MD' and '(Psychiatry)' finds 'psychiatry'."""
    return word.replace(".", "").strip("()[]\"").casefold()


@dataclass(frozen=True)
class WordIndex:
    """Per word key: the records writing it anywhere, those writing it
    after a comma, and its spellings as written with their records."""
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
        for text, bucket in ((head, seen), (tail, seen_after)):
            for token in _TOKEN_SPLIT.split(text):
                key = word_key(token)
                if key:
                    bucket.add(key)
                    spellings.setdefault(key, Counter())[token] += 1
        anywhere.update(seen | seen_after)
        after.update(seen_after)
    return WordIndex(anywhere, after, spellings)


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
        local = None if args.refresh else load(args.source)
        if local is None:
            local = fetch(args.source)
            print(f"fetched into {directory(args.source)}")
        else:
            print(f"cached in {directory(args.source)}; --refresh fetches again")
        print(local.header())
        print(f"{local.meta['names']:,} distinct names in {corpus_path(args.source)}")
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
