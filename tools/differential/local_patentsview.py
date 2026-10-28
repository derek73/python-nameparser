"""The patentsview-inventors local corpus: US patents' inventors, as their filings name them.

patentsview-inventors -- the inventor of every patent the USPTO granted
from 1976 to 2025, from PatentsView's granted-patent tables on the
USPTO Open Data Portal: each inventor's name as the filing gives it, in
its two boxes (first name, last name), and the country of the
inventor's address. A local corpus whose names carry their fields
(local_agreement.FIELDED), so local_agreement.py scores the parser
against them. A filing is written by the applicant's attorney, so the
split is a professional filer's, not the inventor's own as in
orcid-researchers: the two read together tell how a name is written
from how its bearer types it. The name the parser reads is the two
boxes joined, first name first, as a filing writes it.

A record is a distinct name in a country, with the number of people who
filed under it ("people", counted by PatentsView's disambiguated
inventor id): 24,037,380 inventor rows, one per inventor per patent,
held 5,319,206 such names of 4,294,034 inventors on 2026-10-28,
filed under 5,508,446 pairs of a name and an inventor. The
count is what lets a pack ask how common a word is in a country's names
(a frequency ORCID's capped corpus cannot give); it counts people, not
patents, so a prolific inventor weighs once. The extract keeps every
name; the corpus keeps at most PV_CAP a country, chosen by a hash of the
record as orcid-researchers chooses, for the tools that hold a corpus
in memory.

The fetch downloads three of the product's files (PV_FILES) and reads
them without unpacking: the raw inventor table for the names as filed,
the disambiguated one, row for row the same inventors, for the inventor
id and location, and the disambiguated locations for the country. The
portal needs an API key, sent as X-API-KEY: a USPTO.gov account verified
through ID.me gets one (data.uspto.gov, My ODP), saved alone in PV_KEY,
read there and sent to https uspto.gov hosts only. The release is
pinned by each file's size, date and sha256 and the rows it holds; a
new quarter's is measured and the pin moved by hand. The zips are
deleted once the extract is built and read back, a failed run keeping
those already whole for the next; `fetch --refresh` downloads them
again. PatentsView licenses its data under CC BY 4.0 and
asks for credit; the inventors are living people, which keeps their
names in the cache.
"""
from __future__ import annotations

import collections
import csv
import email.message
import gzip
import hashlib
import heapq
import io
import json
import os
import shutil
import sys
import urllib.error
import urllib.parse
import urllib.request
import zipfile
from collections import Counter
from collections.abc import Iterator
from pathlib import Path
from typing import IO, Any, cast

import corpus_build
import local_core
from local_core import Fetched, _again, _backed_off, _pinned, _refuse_past, directory


PV = "patentsview-inventors"
PV_PRODUCT = "PVGPATDIS"
PV_API = "https://api.uspto.gov/api/v1/datasets/products"
#: The pinned release, as the portal listed it on 2026-10-28: grants to
#: this date, and for each file its size, its last modification as the
#: listing states it, and the sha256 of the bytes downloaded that day.
PV_RELEASE = "2025-12-31"
PV_RAW = "g_inventor_not_disambiguated.tsv.zip"
PV_INVENTORS = "g_inventor_disambiguated.tsv.zip"
PV_LOCATIONS = "g_location_disambiguated.tsv.zip"
PV_FILES = {
    PV_RAW: (1_035_476_374, "2026-03-12 22:26:59",
             "18bcef31301b216012a292242ea64393a5c88083ccb648972634df4492017c7b"),
    PV_INVENTORS: (707_503_691, "2026-03-12 22:26:35",
                   "f1148d8c57e2c7d28062b4f572d9a9060eb537c4c62f54d69c63a047b7944385"),
    PV_LOCATIONS: (2_697_159, "2026-03-12 22:27:08",
                   "526023908343f28491ebe6ea9d0568dfae219418f9c128d8a0c4f49e0ce9d6d9"),
}
#: The inventor rows the pinned release holds, each table the same: every
#: field is quoted, so a stray quote cannot fold rows together, and a
#: count short of this is a table read in part.
PV_ROWS = 24_037_380
#: The columns read, by name: the tables state them in a header.
PV_COLUMNS = {
    PV_RAW: ("patent_id", "inventor_sequence", "raw_inventor_name_first",
             "raw_inventor_name_last"),
    PV_INVENTORS: ("patent_id", "inventor_sequence", "inventor_id", "location_id"),
    PV_LOCATIONS: ("location_id", "disambig_country"),
}
PV_KEY = Path.home() / ".config" / "nameparser-tools" / "uspto-odp-key"
#: The extract format, in the extract's file name.
PV_EXTRACT_VERSION = 1
#: The most names a country keeps in the corpus.
PV_CAP = 20_000
#: The share of rows a read skips as not the header's width before it
#: refuses the file (none of 24,037,380 on 2026-10-28), and the least
#: share whose location names a country (99.3%) and whose boxes are both
#: filled (all but 676).
PV_MAX_BAD = 1 / 10_000
PV_MIN_COUNTRY = 0.9
PV_MIN_BOTH = 0.9
_CHUNK = 1 << 20


def extract_path() -> Path:
    """The extract cached for the pinned release."""
    return directory(PV) / f"inventors_{PV_RELEASE}.v{PV_EXTRACT_VERSION}.jsonl.gz"


def _get_a_key() -> str:
    return ("sign in at data.uspto.gov with a USPTO.gov account verified through ID.me, "
            f"copy the key under My ODP, and save it alone in {PV_KEY}, readable by you "
            "only (chmod 600)")


def _key() -> str:
    try:
        key = PV_KEY.read_text(encoding="utf-8").strip()
    except FileNotFoundError:
        key = ""
    if not key or any(c.isspace() for c in key):
        raise ValueError(f"{PV} needs a USPTO Open Data Portal API key: {_get_a_key()}")
    return key


def _uspto(url: str) -> bool:
    parts = urllib.parse.urlsplit(url)
    host = parts.hostname or ""
    return parts.scheme == "https" and (host == "uspto.gov" or host.endswith(".uspto.gov"))


class _KeyStaysHome(urllib.request.HTTPRedirectHandler):
    """A redirect off an https uspto.gov host goes without the key."""

    def redirect_request(self, req: urllib.request.Request, fp: IO[bytes], code: int, msg: str,
                         headers: email.message.Message, newurl: str
                         ) -> urllib.request.Request | None:
        new = super().redirect_request(req, fp, code, msg, headers, newurl)
        if new is not None and not _uspto(newurl):
            new.remove_header("X-api-key")
        return new


def _open(url: str) -> IO[bytes]:
    if not _uspto(url):
        raise ValueError(f"{url} is not an https uspto.gov address: the key goes nowhere else")
    request = urllib.request.Request(url, headers={
        "X-API-KEY": _key(), "User-Agent": local_core.USER_AGENT})
    try:
        return cast(IO[bytes],
                    urllib.request.build_opener(_KeyStaysHome).open(request, timeout=120))
    except urllib.error.HTTPError as exc:
        if exc.code not in (401, 403):
            raise
        exc.close()
        raise ValueError(f"the portal refused the key in {PV_KEY} ({exc.code}): it may "
                         f"have expired or been revoked; for a new one, {_get_a_key()}"
                         ) from None


def _listed() -> dict[str, dict[str, Any]]:
    """The product's files as the portal lists them, refused where a
    pinned file is missing or not the size and date pinned: another
    quarter's release, whose pin is moved by hand."""
    with _open(f"{PV_API}/{PV_PRODUCT}?includeFiles=true") as response:
        data = corpus_build.parse_json(response.read(), PV_API)
    found: dict[str, dict[str, Any]] = {}

    def walk(node: object) -> None:
        if isinstance(node, dict):
            if isinstance(node.get("fileName"), str):
                found[node["fileName"]] = node
            for value in node.values():
                walk(value)
        elif isinstance(node, list):
            for value in node:
                walk(value)
    walk(data)
    for name, (size, modified, _) in PV_FILES.items():
        entry = found.get(name)
        if entry is None or (entry.get("fileSize"), entry.get("fileLastModifiedDateTime")) != (
                size, modified):
            held = entry and (entry.get("fileSize"), entry.get("fileLastModifiedDateTime"))
            raise ValueError(f"{PV_PRODUCT} lists {name} as {held or 'missing'} where "
                             f"{(size, modified)} is pinned: another release, measured "
                             f"and pinned by hand in local_patentsview.PV_FILES")
    return found


def _whole(path: Path, name: str) -> bool:
    """Whether `path` is already the pinned file `name`, size and sha256."""
    size, _, sha = PV_FILES[name]
    if not path.exists() or path.stat().st_size != size:
        return False
    digest = hashlib.sha256()
    with path.open("rb") as held:
        while chunk := held.read(_CHUNK):
            digest.update(chunk)
    return digest.hexdigest() == sha


def _download(entry: dict[str, Any], path: Path) -> None:
    """One pinned file into `path` through a .part file, refused unless
    it is the size and sha256 pinned; kept where a run before left it
    whole, and tried again under local_core's retry policy where a
    connection drops, each try from the start."""
    name = entry["fileName"]
    if _whole(path, name):
        return
    size, _, sha = PV_FILES[name]
    url = entry.get("fileDownloadURI") or f"{PV_API}/files/{PV_PRODUCT}/{name}"
    partial = path.with_name(path.name + ".part")
    for attempt in range(local_core.RETRIES):
        print(f"downloading {name} ({size / 1e6:,.0f} MB) ...", file=sys.stderr)
        digest, got = hashlib.sha256(), 0
        try:
            with _open(url) as response, partial.open("wb") as out:
                while chunk := response.read(_CHUNK):
                    out.write(chunk)
                    digest.update(chunk)
                    got += len(chunk)
        except local_core._TRANSIENT as exc:
            partial.unlink(missing_ok=True)
            if not _backed_off(exc, attempt, url):
                raise
            continue
        except BaseException:
            partial.unlink(missing_ok=True)
            raise
        if (got, digest.hexdigest()) != (size, sha):
            partial.unlink(missing_ok=True)
            raise ValueError(f"{name} arrived as {got:,} bytes with sha256 "
                             f"{digest.hexdigest()}, where {size:,} and {sha} are pinned")
        os.replace(partial, path)
        return
    raise AssertionError("unreachable: the last attempt raises")


def _rows(path: Path, name: str, counts: Counter[str]) -> Iterator[dict[str, str]]:
    """A table's rows by the columns PV_COLUMNS names, read without
    unpacking; a row not the header's width is counted and skipped."""
    with zipfile.ZipFile(path) as archive:
        members = archive.namelist()
        if len(members) != 1:
            raise ValueError(f"{name} holds {len(members)} members where one is expected")
        with archive.open(members[0]) as raw:
            table = csv.reader(io.TextIOWrapper(raw, encoding="utf-8", newline=""),
                               delimiter="\t")
            header = next(table)
            missing = [c for c in PV_COLUMNS[name] if c not in header]
            if missing:
                raise ValueError(f"{name}'s header holds no {', '.join(missing)}")
            at = [header.index(c) for c in PV_COLUMNS[name]]
            for row in table:
                if len(row) != len(header):
                    counts[f"{name}: rows not {len(header)} fields"] += 1
                    continue
                yield {c: row[i] for c, i in zip(PV_COLUMNS[name], at)}


def _extract(folder: Path, out: IO[str]) -> Counter[str]:
    """Every distinct (first, last, country) of the raw table, with the
    distinct inventors who filed under it, written to `out` as extract
    lines; the counts. The raw and disambiguated tables are read in
    step, row for row, and a pair of rows naming different inventor
    slots is refused rather than joined."""
    counts: Counter[str] = Counter()
    country_of = {r["location_id"]: r["disambig_country"]
                  for r in _rows(folder / PV_LOCATIONS, PV_LOCATIONS, counts)}
    inventors = _rows(folder / PV_INVENTORS, PV_INVENTORS, counts)
    people: dict[tuple[str, str, str], int] = {}
    seen: set[int] = set()
    for raw in _rows(folder / PV_RAW, PV_RAW, counts):
        row = next(inventors, None)
        slot = (raw["patent_id"], raw["inventor_sequence"])
        if row is None or (row["patent_id"], row["inventor_sequence"]) != slot:
            raise ValueError(f"{PV_RAW} and {PV_INVENTORS} part at row {counts['rows'] + 1:,}:"
                             f" the two tables are not row for row the same inventors")
        counts["rows"] += 1
        first = " ".join(raw["raw_inventor_name_first"].split())
        last = " ".join(raw["raw_inventor_name_last"].split())
        country = country_of.get(row["location_id"], "").strip().upper()
        counts["rows_with_a_country"] += bool(country)
        if not first or not last:
            counts["rows_without_both_boxes"] += 1
            if not first and not last:
                continue
        key = (first, last, country)
        # One inventor counts once under a name, however many patents.
        filed = hash((key, row["inventor_id"]))
        if filed not in seen:
            seen.add(filed)
            people[key] = people.get(key, 0) + 1
    if next(inventors, None) is not None:
        raise ValueError(f"{PV_INVENTORS} holds more rows than {PV_RAW}")
    for (first, last, country), n in people.items():
        out.write(corpus_build.jsonl_line(
            {k: v for k, v in (("given", first), ("family", last), ("country", country)) if v}
            | {"people": n}, sort_keys=True) + "\n")
    counts["names"] = len(people)
    counts["people_by_name"] = sum(people.values())
    return counts


def renew_pv() -> None:
    """Download the pinned files (_download), build the extract
    (_extract) and read it back through every check a load makes
    (_pv_read) before it replaces the cached one. The zips are deleted
    once it is in place; a run that fails keeps those already whole, so
    the next downloads only the rest. The extract opens with a header of
    the release, the files' sha256 and the counts."""
    target = extract_path()
    folder = target.parent / "downloads"
    body, staged = (target.with_name(target.name + end) for end in (".part", ".new"))
    folder.mkdir(parents=True, exist_ok=True)
    try:
        listed = _listed()
        for name in PV_FILES:
            _download(listed[name], folder / name)
        with gzip.open(body, "wt", encoding="utf-8", newline="\n") as out:
            counts = _extract(folder, out)
        header = corpus_build.jsonl_line({
            "release": PV_RELEASE, "files": {n: sha for n, (_, _, sha) in PV_FILES.items()},
            "counts": dict(counts)})
        # The header is a gzip member of its own ahead of the names', as
        # orcid-researchers' is: the counts are known only at the end.
        with staged.open("wb") as joined, body.open("rb") as names:
            joined.write(gzip.compress(f"{header}\n".encode()))
            shutil.copyfileobj(names, joined, _CHUNK)
        _pv_read(staged)
        os.replace(staged, target)
        shutil.rmtree(folder, ignore_errors=True)
    finally:
        body.unlink(missing_ok=True)
        staged.unlink(missing_ok=True)


def pv_record(line: dict[str, Any]) -> dict[str, str]:
    """An extract line as a corpus record: the boxes joined first name
    first as "name", the boxes, the country and the people, written as
    text since a corpus record holds only text (local_corpora.read_records);
    the extract keeps the number."""
    record = {k: line[k] for k in ("given", "family", "country") if line.get(k)}
    record["name"] = " ".join(v for v in (line.get("given"), line.get("family")) if v)
    record["people"] = str(line["people"])
    return record


def pv_kept(records: Iterator[dict[str, str]], cap: int) -> list[dict[str, str]]:
    """At most `cap` records a country (none is a country of its own):
    those whose line hashes lowest, so a country under the cap is kept
    whole and the same names are kept whatever else the file holds."""
    heaps: dict[str, list[tuple[int, str]]] = collections.defaultdict(list)
    for record in records:
        line = corpus_build.jsonl_line(record, sort_keys=True)
        rank = -int(hashlib.sha256(line.encode()).hexdigest()[:16], 16)
        heap = heaps[record.get("country", "")]
        if len(heap) < cap:
            heapq.heappush(heap, (rank, line))
        elif rank > heap[0][0]:
            heapq.heapreplace(heap, (rank, line))
    return [json.loads(line) for heap in heaps.values() for _, line in sorted(heap)]


def _pv_read(path: Path) -> Fetched:
    """The corpus from the cached extract (pv_record, pv_kept), or
    ValueError naming the refresh where it is not an extract of the
    pinned release, where it holds another number of names than its
    header counts, where its rows are not PV_ROWS, or past PV_MAX_BAD
    of them were malformed, or fewer than PV_MIN_COUNTRY named a country
    or PV_MIN_BOTH filled both boxes. The extract is cut at "\\n" only,
    as corpus_build.jsonl_lines cuts, and streamed rather than read
    whole."""
    lines_read = 0

    def read(lines: Iterator[str]) -> Iterator[dict[str, str]]:
        nonlocal lines_read
        for line in lines:
            lines_read += 1
            yield pv_record(json.loads(line))

    try:
        with gzip.open(path, "rt", encoding="utf-8", newline="\n") as lines:
            head = json.loads(next(lines))
            counts = head["counts"]
            if (head.get("release") != PV_RELEASE
                    or head.get("files") != {n: sha for n, (_, _, sha) in PV_FILES.items()}
                    or not isinstance(counts, dict)
                    or not all(type(n) is int for n in counts.values())):
                raise ValueError("its header does not describe the pinned release")
            records = pv_kept(read(lines), PV_CAP)
    except (OSError, EOFError, StopIteration, ValueError, KeyError, TypeError) as exc:
        raise ValueError(f"{path} is not an extract this tool wrote ({exc}){_again(PV)}"
                         ) from None
    rows = counts.get("rows", 0)
    if rows != PV_ROWS or lines_read != counts.get("names", -1):
        raise ValueError(f"{path} holds {lines_read:,} names of {rows:,} rows, where its "
                         f"header counts {counts.get('names', 0):,} names and {PV_ROWS:,} "
                         f"rows are pinned: a table was read in part{_again(PV)}")
    why = "the files are not the PatentsView tables this tool reads"
    _refuse_past([(n, rows, PV_MAX_BAD, what) for what, n in counts.items()
                  if what.endswith("fields")], why)
    for count, least, what in ((counts.get("rows_with_a_country", 0), PV_MIN_COUNTRY,
                                "rows name a country"),
                               (rows - counts.get("rows_without_both_boxes", 0), PV_MIN_BOTH,
                                "rows fill both boxes")):
        if count < rows * least:
            raise ValueError(f"only {count:,} of {rows:,} {what}: {why}")
    by_country = Counter(r["country"] for r in records if "country" in r)
    return Fetched(records, PV_RELEASE, {
        "kept": _kept(), **{key: counts[key] for key in sorted(counts)},
        "countries": len(by_country),
        "countries_at_the_cap": sum(n == PV_CAP for n in by_country.values())})


def pv_boxes(path: Path) -> Iterator[tuple[str, str, str, int]]:
    """Every name of the extract at `path` as (given, family, country,
    people), uncapped, for local_corpora.box_index. The extract was
    checked when it was fetched (_pv_read); a file whose header names
    another release is refused."""
    with gzip.open(path, "rt", encoding="utf-8", newline="\n") as lines:
        if json.loads(next(lines)).get("release") != PV_RELEASE:
            raise ValueError(f"{path} is not an extract of the {PV_RELEASE} release{_again(PV)}")
        for line in lines:
            record = json.loads(line)
            yield (record.get("given", ""), record.get("family", ""),
                   record.get("country", ""), record["people"])


def _kept() -> str:
    return f"release {PV_RELEASE}, at most {PV_CAP:,} names a country"


def fetch_pv() -> Fetched:
    """The corpus (_pv_read), read from the extract cached beside it,
    downloaded and built when missing and again by `fetch --refresh`."""
    if not extract_path().exists():
        renew_pv()
    return _pv_read(extract_path())


check_pv = _pinned("kept", _kept, "keeps {held}, and this tool keeps {wanted}")
