"""The orcid-researchers local corpus: the names ORCID's holders gave their own records.

orcid-researchers -- the people holding an ORCID iD, from ORCID's
yearly Public Data File: each record's public name as its holder typed
it into the registry's two boxes (given names, family name), the
published name ("credit name") the holder typed beside them, and a
country. A local corpus whose names carry their fields
(local_agreement.FIELDED), so local_agreement.py scores the parser
against them; the person split the name, not a clerk or a filer's
software. The name the parser reads is the two boxes joined, given
first, as the registry displays it; the credit name is a corpus key of
its own, the same person's name as typed for publication. Most holders
are researchers, and they come from every country: from 217 countries
in the probe of the file's first GiB (2026-10-27).

The country is the holder's own public address where there is one, else
the first employment that names one, else the first education that
does: of
605,872 records in that probe, 10.9%, 26.7% and 3.2%, and none for the
other 59.1%; where a record gave both an address and an employment the
two agreed in 92%. A country is where a holder works or lives, not
where the name comes from. The corpus keeps at most ORCID_CAP records
per country (records with none count as one more country), chosen by a
hash of the record, so a country with few holders is kept whole and one
with many is sampled; the corpus therefore shows what each country
holds, never how often anything occurs across them.

The fetch streams the one file it needs, the summaries (46.3 GB for the
2025 release), through ranged requests that resume where a dropped
connection left off, and parses its records in a worker process per CPU
(renew_orcid), reading the extract back through every check a load
makes before it replaces the cached one. Only the extract is cached, never the tar: one line per
record with a public name, every country kept, so a change to the cap
reads the extract again rather than the file. The file is pinned by its
figshare id, size, MD5 and count of summaries (ORCID_URL, ORCID_SIZE,
ORCID_MD5, ORCID_SUMMARIES); a new year's release is measured and the
pin moved by hand, and the floors below catch a release whose layout
moved under the reader. ORCID releases the
file under CC0 1.0; its use policy asks that ORCID be credited and that
the privacy of the people in it be respected, which keeping it out of
the repository does.
"""
from __future__ import annotations

import collections
import contextlib
import email.utils
import gzip
import hashlib
import heapq
import http.client
import importlib
import io
import json
import multiprocessing
import os
import re
import sys
import tarfile
import urllib.request
import xml.etree.ElementTree as ET
import zlib
from collections import Counter
from collections.abc import Callable, Iterator
from concurrent.futures import Future, ProcessPoolExecutor
from pathlib import Path
from typing import Any

import corpus_build
import local_core
from local_core import Fetched, _again, _backed_off, _pinned, _refuse_past, directory


ORCID = "orcid-researchers"
#: The pinned release: the 2025 Public Data File's summaries
#: (figshare article 30375589, DOI 10.23640/07243.30375589.v1),
#: as figshare's API described it on 2026-10-27.
ORCID_FILE = "ORCID_2025_10_summaries.tar.gz"
ORCID_URL = "https://ndownloader.figshare.com/files/58834837"
ORCID_SIZE = 46_328_319_190
ORCID_MD5 = "210edf71f4a2bb44dd33aaa3037b3f17"
#: The summaries the pinned file holds, read whole on 2026-10-27: tarfile
#: ends a stream at a damaged header without raising, so a count short of
#: this is a tar read only in part, which its MD5 cannot show.
ORCID_SUMMARIES = 26_078_951
#: A record in the tar: one XML file per iD, under its iD's last three
#: characters, the check character (a digit or X) among them.
_SUMMARY = re.compile(r"ORCID_\d{4}_\d{2}_summaries/\d{2}[\dX]/\d{4}-\d{4}-\d{4}-\d{3}[\dX]\.xml")
#: The extract format, in the extract's file name: a change to what
#: _summary keeps or refuses bumps it, so an extract written by another
#: version is not read.
ORCID_EXTRACT_VERSION = 1
#: The most records a country keeps (orcid_kept).
ORCID_CAP = 20_000
#: The share of summaries a read of the extract (and so a fetch) skips
#: as not XML, or as XML declaring a DTD or an entity, the share of the
#: tar's files that are not summaries at all, and the share of the
#: countries kept that are not two capital letters, before it refuses
#: the file: the whole file met none of the four (2026-10-27).
ORCID_MAX_BAD = 1 / 10_000
#: The least share of summaries that give a record, of records with a
#: family name, and of records with a country, before a read refuses the
#: file as one whose layout moved under the reader (an element renamed,
#: a namespace moved): 95.8%, 94.8% and 42.8% on 2026-10-27.
ORCID_MIN_RECORDS = 1 / 2
ORCID_MIN_FAMILY = 1 / 2
ORCID_MIN_COUNTRY = 1 / 5
#: Attempts at each read of the stream: a reopen costs a request, and
#: giving up costs the 46 GB, so it rides out minutes of outage
#: (local_core._backed_off's nine waits, capped at a minute: 243 s, each
#: attempt's own 60 s timeout on top).
ORCID_RETRIES = 10
#: Summaries handed to a worker at a time.
_BATCH = 2_000

_ADDRESS = "{http://www.orcid.org/ns/address}address"
_EMPLOYMENT = "{http://www.orcid.org/ns/employment}employment-summary"
_EDUCATION = "{http://www.orcid.org/ns/education}education-summary"
_LOCALE = "{http://www.orcid.org/ns/preferences}locale"
#: What a worker hands back: a batch's extract lines and counts.
_Batch = tuple[list[str], dict[str, int]]
#: Where a record's country is read from, in order of preference.
COUNTRY_FROM = ("address", "employment", "education")
_COUNTRY = re.compile(r"[A-Z]{2}")


def extract_path() -> Path:
    """The extract cached for the pinned file."""
    stem = ORCID_FILE.removesuffix(".tar.gz")
    return directory(ORCID) / f"{stem}.v{ORCID_EXTRACT_VERSION}.jsonl.gz"


def _local(tag: str) -> str:
    return tag.rsplit("}", 1)[-1]


def _text(element: ET.Element) -> str:
    return " ".join((element.text or "").split())


def _summary(body: bytes) -> tuple[str, dict[str, Any] | None]:
    """One summary's outcome and the record it gives: ("record", the
    record) for a public name, else a count's key and None. The record
    holds the boxes, the credit name, the other names, the country with
    where it came from and the locale the holder set for ORCID's own
    pages (a language, kept for a later view), the empty ones left out. A summary that
    declares a DTD is refused unread ("dtd_refused"): ORCID's never
    does, and one that did could define entities. The standard library's
    parser expands no external entity, and the Expat it ships bounds
    entity amplification; refusing the declaration keeps a parse from
    depending on either."""
    if b"<!DOCTYPE" in body or b"<!ENTITY" in body:
        return "dtd_refused", None
    try:
        root = ET.fromstring(body)
    except ET.ParseError:
        return "not_xml", None
    boxes = {"given": "", "family": "", "credit": ""}
    other: list[str] = []
    countries: dict[str, str] = {}
    public = False
    locale = ""
    for element in root.iter():
        tag = _local(element.tag)
        if element.tag == _LOCALE:
            locale = _text(element)
        elif tag == "person":
            for name in element:
                if _local(name.tag) != "name":
                    continue
                public = True
                for box in name:
                    key = {"given-names": "given", "family-name": "family",
                           "credit-name": "credit"}.get(_local(box.tag))
                    if key:
                        boxes[key] = _text(box)
        elif tag == "other-name":
            other += [t for c in element if _local(c.tag) == "content" and (t := _text(c))]
        elif element.tag in (_ADDRESS, _EMPLOYMENT, _EDUCATION):
            where = {_ADDRESS: "address", _EMPLOYMENT: "employment",
                     _EDUCATION: "education"}[element.tag]
            if where not in countries:
                found = next((t for c in element.iter()
                              if _local(c.tag) == "country" and (t := _text(c))), "")
                if found:
                    countries[where] = found.upper()
    if not public:
        return "name_private", None
    if not boxes["given"] and not boxes["family"]:
        return "name_empty", None
    record: dict[str, Any] = {k: v for k, v in boxes.items() if v}
    if other:
        record["other"] = other
    where = next((w for w in COUNTRY_FROM if w in countries), "")
    if where:
        record["country"], record["country_from"] = countries[where], where
    if locale:
        record["locale"] = locale
    return "record", record


def _summaries(bodies: list[bytes]) -> tuple[list[str], dict[str, int]]:
    """A batch of summaries read (_summary): each record as an extract
    line, and the counts of the rest. A worker's unit of work."""
    lines, counts = [], Counter[str]()
    for body in bodies:
        outcome, record = _summary(body)
        counts[outcome] += 1
        if record is not None:
            lines.append(corpus_build.jsonl_line(record, sort_keys=True))
    return lines, dict(counts)


class _RangeStream(io.RawIOBase):
    """`url`'s body, `size` bytes, read through ranged requests: a
    connection dropped or timed out mid-body is opened again from the
    byte reached, under local_core's retry policy with ORCID_RETRIES
    attempts, so an outage of a few minutes costs no byte already read.
    Each response must be a 206 saying it is the range asked of a body of
    `size` bytes, last modified when the first one was (which must say
    when), or the file was replaced and the stream refuses it.
    finish() checks the bytes read against `size` and `md5`."""

    def __init__(self, url: str, size: int, md5: str) -> None:
        self.url, self.size, self.md5 = url, size, md5
        self.pos = 0
        self.modified = ""
        self._digest = hashlib.md5()
        self._response: http.client.HTTPResponse | None = None

    def readable(self) -> bool:
        return True

    def _open(self) -> http.client.HTTPResponse:
        request = urllib.request.Request(self.url, headers={
            "User-Agent": local_core.USER_AGENT, "Range": f"bytes={self.pos}-"})
        response = urllib.request.urlopen(request, timeout=60)
        stated = response.headers.get("Content-Range", "")
        modified = response.headers.get("Last-Modified", "")
        wanted = f"bytes {self.pos}-{self.size - 1}/{self.size}"
        if response.status != 206 or stated != wanted or not modified or (
                self.modified and modified != self.modified):
            response.close()
            raise ValueError(
                f"{self.url} answered {response.status} {stated or 'no range'}"
                f" (last modified {modified or 'not stated'}) where {wanted}"
                f"{' of the file last modified ' + self.modified if self.modified else ''}"
                f" was asked: the file is not the pinned one")
        self.modified = modified
        return response

    def readinto(self, buffer: memoryview | bytearray) -> int:  # type: ignore[override]
        if self.pos >= self.size:
            return 0
        for attempt in range(ORCID_RETRIES):
            try:
                if self._response is None:
                    self._response = self._open()
                got = self._response.readinto(buffer)
                if not got:
                    raise http.client.IncompleteRead(b"", self.size - self.pos)
            except local_core._TRANSIENT as exc:
                self._drop()
                if not _backed_off(exc, attempt, self.url, ORCID_RETRIES):
                    raise
                continue
            self._digest.update(memoryview(buffer)[:got])
            self.pos += got
            return got
        raise AssertionError("unreachable: the last attempt raises")

    def _drop(self) -> None:
        if self._response is not None:
            self._response.close()
            self._response = None

    def close(self) -> None:
        self._drop()
        super().close()

    def finish(self) -> None:
        """ValueError naming the refresh unless every byte was read and
        their MD5 is the pinned one."""
        if self.pos != self.size or self._digest.hexdigest() != self.md5:
            raise ValueError(f"{self.url}: read {self.pos:,} of {self.size:,} bytes "
                             f"with MD5 {self._digest.hexdigest()}, where {self.md5} "
                             f"is pinned{_again(ORCID)}")


class _Inline:
    """An executor that runs each call as it is submitted: one job."""

    def submit(self, fn: Callable[[list[bytes]], _Batch],
               batch: list[bytes]) -> Future[_Batch]:
        done: Future[_Batch] = Future()
        done.set_result(fn(batch))
        return done


def _drain(pending: collections.deque[Future[_Batch]],
           out: io.TextIOBase, counts: Counter[str], keep: int) -> None:
    """Write the oldest batches' lines until at most `keep` are pending."""
    while len(pending) > keep:
        lines, batch_counts = pending.popleft().result()
        counts.update(batch_counts)
        out.writelines(f"{line}\n" for line in lines)


def _extract(raw: io.RawIOBase, out: io.TextIOBase, jobs: int) -> Counter[str]:
    """Every summary of the tar.gz read from `raw`, parsed `jobs` at a
    time (_summaries), its records written to `out` as they come; the
    counts. The gzip stream is read to its end, past the tar's own end,
    so that its CRC is checked."""
    counts: Counter[str] = Counter()
    unzipped = gzip.GzipFile(fileobj=io.BufferedReader(raw, local_core.CHUNK))
    batch: list[bytes] = []
    pending: collections.deque[Future[_Batch]] = (
        collections.deque())
    # A worker unpickles the function by its module's bare name, which
    # resolves there because this directory is on the inherited sys.path
    # (snapshot.parallel says why).
    read = getattr(importlib.import_module("local_orcid"), "_summaries")
    with (ProcessPoolExecutor(jobs, mp_context=multiprocessing.get_context("spawn"))
          if jobs > 1 else contextlib.nullcontext(_Inline())) as pool:
        with tarfile.open(fileobj=unzipped, mode="r|") as tar:
            for member in tar:
                # A TarFile keeps every member it has read, even read as
                # a stream: 26M of them would hold the whole file's
                # headers in memory (2.3 GB a GiB in, measured 2026-10-27).
                tar.members = []
                if not member.isfile():
                    continue
                if not _SUMMARY.fullmatch(member.name):
                    counts["members_not_summaries"] += 1
                    continue
                file = tar.extractfile(member)
                assert file is not None, "a regular member has a body"
                batch.append(file.read())
                if len(batch) == _BATCH:
                    pending.append(pool.submit(read, batch))
                    batch = []
                    _drain(pending, out, counts, 2 * jobs)
        if batch:
            pending.append(pool.submit(read, batch))
        _drain(pending, out, counts, 0)
    while unzipped.read(local_core.CHUNK):
        pass
    return counts


def renew_orcid(jobs: int | None = None) -> None:
    """Stream the pinned summaries file (_RangeStream) and keep its
    extract: a header naming the file, its data date (the file's
    Last-Modified) and the counts, then one line per record with a
    public name, in the tar's order. Written beside its final name and
    renamed into place only once the whole file was read, its MD5
    checked and the extract read back through every check a load makes
    (_orcid_read), so a fetch that dies or is refused leaves the old
    extract, or none. The
    header is a gzip member of its own ahead of the records' (gzip reads
    the members as one stream), since the counts are known only at the
    end and the records are not compressed twice."""
    target = extract_path()
    body, staged = (target.with_name(target.name + end) for end in (".part", ".new"))
    stream = _RangeStream(ORCID_URL, ORCID_SIZE, ORCID_MD5)
    print(f"streaming {ORCID_FILE} ({ORCID_SIZE / 1e9:.1f} GB) from {ORCID_URL} ...",
          file=sys.stderr)
    try:
        with gzip.open(body, "wt", encoding="utf-8") as out:
            counts = _extract(stream, out, jobs or os.cpu_count() or 1)
        stream.finish()
        header = corpus_build.jsonl_line({"file": ORCID_FILE,
                                          "data_date": _iso(stream.modified),
                                          "counts": dict(counts)})
        with staged.open("wb") as joined, body.open("rb") as records:
            joined.write(gzip.compress(f"{header}\n".encode()))
            while chunk := records.read(local_core.CHUNK):
                joined.write(chunk)
        _orcid_read(staged)
        os.replace(staged, target)
    finally:
        stream.close()
        body.unlink(missing_ok=True)
        staged.unlink(missing_ok=True)


def _iso(http_date: str) -> str:
    """An HTTP date as the corpora's data dates are written."""
    if not http_date:
        raise ValueError(f"{ORCID_URL} stated no Last-Modified to date the data by")
    return email.utils.parsedate_to_datetime(http_date).strftime("%Y-%m-%dT%H:%M:%S")


def orcid_record(line: dict[str, Any]) -> dict[str, str]:
    """An extract line as a corpus record: the boxes joined given first
    as "name", the boxes, the credit name and the country with where it
    came from. The other names stay in the extract: a list, where a
    record holds text."""
    record = {k: line[k] for k in ("given", "family", "credit", "country",
                                   "country_from") if line.get(k)}
    record["name"] = " ".join(v for v in (line.get("given"), line.get("family")) if v)
    return record


def orcid_kept(records: Iterator[dict[str, str]], cap: int) -> list[dict[str, str]]:
    """The distinct records, at most `cap` per country (no country is a
    country of its own): those whose line hashes lowest, so a country
    under the cap is kept whole and the same record is kept whatever
    else the file holds."""
    heaps: dict[str, list[tuple[int, str]]] = collections.defaultdict(list)
    seen: dict[str, set[int]] = collections.defaultdict(set)
    for record in records:
        line = corpus_build.jsonl_line(record, sort_keys=True)
        rank = -int(hashlib.sha256(line.encode()).hexdigest()[:16], 16)
        country = record.get("country", "")
        heap, held = heaps[country], seen[country]
        if rank in held:
            continue
        if len(heap) < cap:
            heapq.heappush(heap, (rank, line))
            held.add(rank)
        elif rank > heap[0][0]:
            held.discard(heapq.heapreplace(heap, (rank, line))[0])
            held.add(rank)
    return [json.loads(line) for heap in heaps.values() for _, line in sorted(heap)]


def _orcid_read(path: Path) -> Fetched:
    """The corpus from the cached extract (orcid_record, orcid_kept), or
    ValueError naming the refresh where it is not an extract of the
    pinned file, where it holds another number of summaries than
    ORCID_SUMMARIES or another number of records than its header counts,
    where past ORCID_MAX_BAD of its summaries were not XML or declared a
    DTD, of the tar's files were not summaries (a layout that moved
    under _SUMMARY) or of its countries are not two capital letters, or
    where fewer than the ORCID_MIN_ shares of its summaries gave a record
    or of its records hold a family name or a country (an element the
    reader looks for, renamed). The extract is cut at "\n" only, as
    corpus_build.jsonl_lines cuts, and streamed rather than read whole."""
    seen: Counter[str] = Counter()

    def read(lines: Iterator[str]) -> Iterator[dict[str, str]]:
        for line in lines:
            record = orcid_record(json.loads(line))
            seen["records"] += 1
            seen["family"] += "family" in record
            if country := record.get("country"):
                seen["country"] += 1
                seen["country_malformed"] += not _COUNTRY.fullmatch(country)
            yield record

    try:
        with gzip.open(path, "rt", encoding="utf-8", newline="\n") as lines:
            head = json.loads(next(lines))
            counts, data_date = head["counts"], head["data_date"]
            if (head.get("file") != ORCID_FILE or not isinstance(counts, dict)
                    or not all(type(n) is int for n in counts.values())
                    or not isinstance(data_date, str)):
                raise ValueError("its header does not describe the pinned file")
            records = orcid_kept(read(lines), ORCID_CAP)
    except (OSError, EOFError, StopIteration, ValueError, KeyError, TypeError,
            zlib.error) as exc:
        raise ValueError(f"{path} is not an extract this tool wrote ({exc})"
                         f"{_again(ORCID)}") from None
    summaries = sum(n for key, n in counts.items() if key != "members_not_summaries")
    if summaries != ORCID_SUMMARIES or seen["records"] != counts.get("record", 0):
        raise ValueError(
            f"{path} holds {seen['records']:,} records of {summaries:,} summaries, where its "
            f"header counts {counts.get('record', 0):,} records and {ORCID_SUMMARIES:,} "
            f"summaries are pinned: the tar was read in part{_again(ORCID)}")
    why = "the file is not the Public Data File this tool reads"
    _refuse_past([(counts.get("not_xml", 0), summaries, ORCID_MAX_BAD,
                   "summaries are not XML"),
                  (counts.get("dtd_refused", 0), summaries, ORCID_MAX_BAD,
                   "summaries declare a DTD or an entity"),
                  (counts.get("members_not_summaries", 0),
                   summaries + counts.get("members_not_summaries", 0), ORCID_MAX_BAD,
                   "files in the tar are not summaries"),
                  (seen["country_malformed"], seen["country"], ORCID_MAX_BAD,
                   "countries are not two capital letters")], why)
    for count, of, least, what in (
            (seen["records"], summaries, ORCID_MIN_RECORDS, "summaries give a record"),
            (seen["family"], seen["records"], ORCID_MIN_FAMILY, "records hold a family name"),
            (seen["country"], seen["records"], ORCID_MIN_COUNTRY, "records hold a country")):
        if count < of * least:
            raise ValueError(f"only {count:,} of {of:,} {what}: {why}")
    by_country = Counter(r["country"] for r in records if "country" in r)
    return Fetched(records, data_date, {
        "kept": _kept(), "summaries": summaries,
        **{key: counts[key] for key in sorted(counts)},
        "countries": len(by_country),
        "countries_at_the_cap": sum(n == ORCID_CAP for n in by_country.values())})


def orcid_boxes(path: Path) -> Iterator[tuple[str, str, str, int]]:
    """Every record of the extract at `path` as (given, family, country,
    1): one holder each, uncapped, for local_corpora.box_index. The
    extract was checked when it was fetched (_orcid_read); a file whose
    header names another release is refused."""
    with gzip.open(path, "rt", encoding="utf-8", newline="\n") as lines:
        if json.loads(next(lines)).get("file") != ORCID_FILE:
            raise ValueError(f"{path} is not an extract of {ORCID_FILE}{_again(ORCID)}")
        for line in lines:
            record = json.loads(line)
            yield (record.get("given", ""), record.get("family", ""),
                   record.get("country", ""), 1)


def _kept() -> str:
    return f"{ORCID_FILE}, at most {ORCID_CAP:,} records a country"


def fetch_orcid() -> Fetched:
    """The corpus (_orcid_read), read from the extract cached beside it,
    streamed from the pinned file when missing and again by
    `fetch --refresh`."""
    if not extract_path().exists():
        renew_orcid()
    return _orcid_read(extract_path())


check_orcid = _pinned("kept", _kept, "keeps {held}, and this tool keeps {wanted}")
