"""The machinery the local corpora's sources share: what a fetch returns,
the retry policy, the gate on what a reader reads past, downloads, and
the cache folder.

local_corpora.py holds the SOURCES registry, the cache's own files, the
views (tally, pairs, the word index) and the command line; each
local_<source>.py holds one source's fetch. A
source module imports this one and never local_corpora, which imports
the source modules to build SOURCES.
"""
from __future__ import annotations

import http.client
import os
import sys
import time
import urllib.error
import urllib.request
import zipfile
from collections.abc import Callable, Iterable, Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any, TypeVar

import corpus_build


USER_AGENT = ("python-nameparser local_corpora "
              "(https://github.com/derek73/python-nameparser)")


@dataclass(frozen=True)
class Fetched:
    """What a source's fetch returns: one record per name, each holding
    at least "name", and the source's own date for the data."""
    records: list[dict[str, str]]
    data_date: str
    #: Anything else worth keeping (API version, counts), stored in
    #: meta.json under "detail", where it cannot replace a key local_corpora.load() checks.
    detail: dict[str, Any]


@dataclass(frozen=True)
class Source:
    credit: str
    #: What one record is, for counts: "officials", "names".
    unit: str
    fetch: Callable[[], Fetched]
    #: What `fetch --refresh` runs first, for a source whose fetch reads
    #: an input cached beside the corpus: fetches that input anew,
    #: replacing the cached copy only once the new one is whole.
    renew: Callable[[], None] | None = None
    #: Why local_corpora.load() should refuse a meta.json this version of the source
    #: did not write (another FEC cycle), or "" to accept it.
    check: Callable[[dict[str, Any]], str] | None = None
    #: The record keys whose values the corpus and the word index hold as
    #: names, an empty value skipped: "name", and for a source whose
    #: records carry the name in a second script, that script's key
    #: (nepal-candidates' "devanagari"). meta.json records them, and a
    #: corpus written under other keys is refused on load.
    corpus_keys: tuple[str, ...] = ("name",)


#: Attempts per request, for every source that retries.
RETRIES = 4
#: How much of a streamed download is read at a time.
CHUNK = 1 << 20
#: What a long run of requests meets and a retry survives: a refused or
#: dropped connection or a timeout (OSError, which URLError and HTTPError
#: are), a body cut short in the read (http.client's IncompleteRead), a
#: 5xx or a 429; and, caught apart from these, a body that arrived but
#: does not parse.
_TRANSIENT = (OSError, http.client.HTTPException)


_T = TypeVar("_T")


class _Unparsed(ValueError):
    """A response body that is not JSON: cut short in transit."""


def _get_json(url: str) -> dict[str, Any]:
    """`url`'s JSON object, fetched by _retried: a long paged run
    (ClinicalTrials.gov's 608 pages on 2026-10-21) should not start over
    for one failed page."""
    data = _retried(url, lambda body: corpus_build.parse_json(body, url), 0.1)
    if not isinstance(data, dict):
        raise ValueError(f"{url} answered {type(data).__name__}, not an object")
    return data


def _zip_stamp(info: zipfile.ZipInfo) -> str:
    """A zip member's own timestamp, as a data date: the sources that
    ship a zip state no other date for what is in it."""
    return "{:04d}-{:02d}-{:02d}T{:02d}:{:02d}:{:02d}".format(*info.date_time)


def _pinned(key: str, wanted: Callable[[], str], says: str
            ) -> Callable[[dict[str, Any]], str]:
    """A Source.check refusing a corpus whose meta.json detail `key` is
    not `wanted()` now, read at check time so that a change to the
    constant behind it refuses corpora fetched before; `says` words the
    refusal, with {held} and {wanted}."""
    def check(meta: dict[str, Any]) -> str:
        held, now = meta["detail"].get(key), wanted()
        return "" if held == now else says.format(held=held, wanted=now)
    return check


def _refuse_past(rows: Iterable[tuple[int, int, float, str]], why: str) -> None:
    """The gate every source puts on what it reads past: for each
    (count, of, share, what), refuse with "count of `of` what: why" once
    count is more than `share` of `of`. A file whose layout moved under
    a reader would otherwise read as a smaller corpus."""
    for count, of, share, what in rows:
        if count > of * share:
            raise ValueError(f"{count:,} of {of:,} {what}: {why}")


def _backed_off(exc: Exception, attempt: int, url: str, retries: int | None = None) -> bool:
    """The retry policy every source shares, after `exc` on try `attempt`
    of `url`: False where the caller should raise it (a 4xx other than
    429 is the request's fault, and the last of `retries` attempts'
    error is the fetch's; RETRIES unless a caller whose attempt is cheap
    beside what giving up loses asks for more), else True once a backoff
    of 2**attempt seconds up to a minute, or the Retry-After a server
    asks for up to a minute, has been slept, with a line on stderr."""
    if (isinstance(exc, urllib.error.HTTPError) and exc.code < 500
            and exc.code != 429 or attempt == (RETRIES if retries is None else retries) - 1):
        return False
    wait = min(2 ** attempt, 60)
    if isinstance(exc, urllib.error.HTTPError):
        after = exc.headers.get("Retry-After", "") if exc.headers else ""
        if after.isdigit():
            wait = max(wait, min(int(after), 60))
        exc.close()  # an HTTPError holds the response open
    print(f"  retrying in {wait}s after {type(exc).__name__}: {url}", file=sys.stderr)
    time.sleep(wait)
    return True


def _retried(url: str, read: Callable[[bytes], _T], delay: float, *,
             timeout: int = 60, headers: Mapping[str, str] | None = None) -> _T:
    """`url`'s body as `read` reads it, under _backed_off's policy; any
    ValueError from `read` is retried as a body cut short in transit, and
    `delay` seconds of sleep follow each request. `headers` go with each
    request, a User-Agent among them replacing USER_AGENT."""
    for attempt in range(RETRIES):
        try:
            body = corpus_build.fetch_bytes(url, user_agent=USER_AGENT,
                                            timeout=timeout, delay=delay,
                                            headers=headers)
            try:
                return read(body)
            except ValueError as exc:
                raise _Unparsed(f"{url}: {exc}") from None
        except (*_TRANSIENT, _Unparsed) as exc:
            if not _backed_off(exc, attempt, url):
                raise
    raise AssertionError("unreachable: the last attempt raises")


def _download(url: str, path: Path) -> None:
    """Download `url` to `path` through a .part file, refusing a body
    whose length differs from the stated Content-Length, or with no
    Content-Length at all: a cut zip would otherwise fail later as a
    BadZipFile that says nothing about the download. `path` is replaced
    only once the new file is whole, and a failed download leaves no
    .part behind."""
    print(f"downloading {url} ...", file=sys.stderr)
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    partial = path.with_name(path.name + ".part")
    try:
        got = 0
        with urllib.request.urlopen(request, timeout=60) as response, \
                partial.open("wb") as out:
            stated = response.headers.get("Content-Length", "")
            while chunk := response.read(CHUNK):
                out.write(chunk)
                got += len(chunk)
        if not stated.isdigit() or int(stated) != got:
            raise ValueError(f"{url} sent {got:,} bytes where it stated "
                             f"{stated or 'no length'}; fetch again")
    except BaseException:
        partial.unlink(missing_ok=True)
        raise
    os.replace(partial, path)


def fetch_command(source: str, *, refresh: bool = False) -> str:
    """The command that fetches `source`, for messages that name it."""
    return (f"tools/differential/local_corpora.py fetch {source}"
            + (" --refresh" if refresh else ""))


def _again(source: str) -> str:
    return f"; fetch it again: {fetch_command(source, refresh=True)}"


def directory(source: str, *, create: bool = True) -> Path:
    """`source`'s folder in the cache, unchecked: a source module names
    its own corpus. local_corpora.directory is the checked one."""
    return corpus_build.cache_dir(f"local/{source}", create=create)
