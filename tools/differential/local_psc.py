"""The psc-individuals local corpus: Companies House's people with significant control.

psc-individuals -- the people with significant control of UK companies,
and the beneficial owners of overseas entities, from Companies House's
daily snapshot: each person's display name, the four boxes the filer
typed it into (title, forename, middle name, surname) and the stated
nationality, and nothing else. A local corpus whose names carry their
fields (local_agreement.FIELDED), so local_agreement.py scores the
parser against them. A record is a distinct filed name, and the corpus
keeps one in PSC_SAMPLE of them (1,040,708 of 8,322,939 on 2026-10-22).
The snapshot comes in parts (33 on 2026-10-22), whose extracts are
cached beside the corpus (renew_psc says why), and `fetch --refresh`
downloads the day's snapshot again. Companies House sets no terms on the
register's use; the names are personal data, which the credit line says.
"""
from __future__ import annotations

import gzip
import hashlib
import json
import os
import re
import shutil
import urllib.error
import urllib.parse
import zipfile
import zlib
from collections import Counter
from pathlib import Path

import corpus_build
from local_core import (Fetched, _again, _download, _pinned, _refuse_past, _retried,
                        directory)


PSC = "psc-individuals"
PSC_PAGE = "https://download.companieshouse.gov.uk/en_pscdata.html"
#: A part of the day's snapshot as the page links it: its file, date,
#: number, and how many parts there are.
PSC_PART = re.compile(r'href="(psc-snapshot-(\d{4}-\d{2}-\d{2})_(\d+)of(\d+)\.zip)"')
#: The two kinds of record that name a person: a company's PSC, and an
#: overseas entity's registrable beneficial owner, filed in the same boxes
#: (70 of part 1's 461,778 individuals on 2026-10-22). The corporate,
#: legal-person and super-secure kinds name no person or none at all.
PSC_KINDS = ("individual-person-with-significant-control",
             "individual-beneficial-owner")
#: The four name boxes, in the order the display name joins them.
PSC_ELEMENTS = ("title", "forename", "middle_name", "surname")
#: What a record keeps: the display name, the boxes and the nationality.
PSC_KEPT = ("name", *PSC_ELEMENTS, "nationality")
#: The share of individuals (of lines, for a line not JSON) a fetch skips
#: before it refuses the snapshot. Of part 1's 461,778 individuals on
#: 2026-10-22 none had no name_elements and every display name was its
#: boxes joined; 2 of the whole snapshot's 14,025,738 were not.
PSC_MAX_BAD = 1 / 10_000
#: The least share of lines that are PSC_KINDS records before a fetch
#: refuses the snapshot: 14,025,738 of 16,071,681 (87%) on 2026-10-22.
#: A kind renamed by Companies House is counted as another kind, and
#: without this floor the corpus would shrink to whatever kind is left.
PSC_MIN_INDIVIDUALS = 1 / 2
#: The cached extracts, one per part, beside the corpus.
PSC_PARTS = "parts"
#: The extract format, in each extract's file name: a change to what
#: _psc_extract keeps or refuses bumps it, so an extract written by
#: another version is neither resumed from nor read.
PSC_EXTRACT_VERSION = 1
_PSC_EXTRACT = re.compile(r"psc-snapshot-(\d{4}-\d{2}-\d{2})_(\d+)of(\d+)\.v(\d+)\.jsonl\.gz")
#: The corpus keeps one filed name in PSC_SAMPLE, chosen by a hash of the
#: record (psc_sampled). The whole snapshot held 8,322,939 distinct filed
#: names on 2026-10-22, 1.09 GB as JSON lines, and a local corpus is held
#: in memory whole (Local.records), and snapshot.py --local reads every
#: name with both APIs. A record's hash does not move with the snapshot,
#: so a refetch keeps or drops the same record as before, and no
#: nationality or shape is favoured.
PSC_SAMPLE = 8


def psc_sampled(line: str) -> bool:
    """Whether the corpus keeps the record written as this line."""
    return int(hashlib.sha256(line.encode()).hexdigest()[:8], 16) % PSC_SAMPLE == 0


def _extract_name(file: str) -> str:
    """The extract cached for a part's zip."""
    return file.replace(".zip", f".v{PSC_EXTRACT_VERSION}.jsonl.gz")


def _psc_extract(path: Path, member: str) -> bytes:
    """One downloaded part, read down to what the corpus keeps: gzipped
    JSON lines, a header naming the part and holding its counts, and then
    its distinct records, each its PSC_KEPT values with the empty ones
    left out. A record that is not one of PSC_KINDS is counted
    (records_of_other_kinds) and dropped, as is an individual whose
    name_elements are missing or not strings, or whose display name is
    not its boxes joined by spaces: the score compares the boxes with a
    parse of that name. Everything else in a record (address, date of
    birth, company number, natures of control) is read past."""
    counts: Counter[str] = Counter()
    lines: set[str] = set()
    with zipfile.ZipFile(path) as archive:
        if member not in archive.namelist():
            raise ValueError(f"{path} holds no {member}")
        with archive.open(member) as source:
            for line in source:
                counts["lines"] += 1
                try:
                    record = json.loads(line)
                except ValueError:
                    counts["lines_not_json"] += 1
                    continue
                data = record.get("data") if isinstance(record, dict) else None
                kind = data.get("kind") if isinstance(data, dict) else None
                if not isinstance(data, dict) or kind not in PSC_KINDS:
                    counts["records_of_other_kinds"] += 1
                    continue
                counts[kind] += 1
                name, elements = data.get("name"), data.get("name_elements")
                if (not isinstance(name, str) or not isinstance(elements, dict)
                        or not all(isinstance(elements.get(f, ""), str)
                                   for f in PSC_ELEMENTS)):
                    counts["individuals_without_name_elements"] += 1
                    continue
                if " ".join(v for f in PSC_ELEMENTS if (v := elements.get(f))) != name:
                    counts["names_not_their_boxes_joined"] += 1
                    continue
                nationality = data.get("nationality")
                if not isinstance(nationality, str) or not nationality:
                    counts["individuals_without_a_nationality"] += 1
                    nationality = ""
                kept = {"name": name, "nationality": nationality,
                        **{f: elements.get(f, "") for f in PSC_ELEMENTS}}
                lines.add(corpus_build.jsonl_line(
                    {k: v for k, v in kept.items() if v}, sort_keys=True))
    header = corpus_build.jsonl_line({"part": member, "counts": dict(counts)})
    return gzip.compress("".join(f"{line}\n" for line in [header, *sorted(lines)]).encode())


def _one_snapshot(dates: set[str], totals: set[int], numbers: list[int]) -> bool:
    """Whether parts `numbers`, dated `dates` and each one of `totals`,
    are every part of one snapshot."""
    return (len(dates) == 1 and len(totals) == 1
            and sorted(numbers) == list(range(1, max(totals) + 1)))


def _psc_listing() -> tuple[str, list[tuple[int, str]]]:
    """The day's snapshot as the download page lists it: its date and
    each part's number and file, or ValueError where the page links no
    parts, or parts of more than one snapshot, or not every part. A part
    linked twice is one part."""
    page = _retried(PSC_PAGE, lambda body: body, 0)
    links = PSC_PART.findall(page.decode("utf-8", "replace"))
    if not links:
        raise ValueError(f"{PSC_PAGE} links no snapshot parts: the page has changed")
    dates, totals = {d for _, d, _, _ in links}, {int(m) for *_, m in links}
    numbers = sorted(int(n) for _, _, n, _ in set(links))
    if not _one_snapshot(dates, totals, numbers):
        raise ValueError(f"{PSC_PAGE} links parts {numbers} of {sorted(totals)} "
                         f"dated {sorted(dates)}, not every part of one snapshot; "
                         f"fetch again")
    return dates.pop(), sorted({(int(n), f) for f, _, n, _ in links})


def renew_psc() -> None:
    """Download every part of the day's snapshot and keep its extract
    (_psc_extract) in parts.new/, then swap parts.new/ in for parts/.

    Parts, not the single zip, and extracts, not zips: the 33 parts of
    2026-10-22 were 2.4 GB, as the single zip was (2,443,088,441 bytes),
    and their extracts 168 MB (part 1's 5.6 MB of its 78.6 MB). A
    download that fails costs one part, and a refresh run again resumes:
    the extracts of the same date and version already in parts.new/ are
    kept, and anything else there is removed. The page's files are
    overwritten each morning, so a part that is gone mid-fetch most
    likely means the snapshot was replaced; the next run lists the new
    one."""
    date, parts = _psc_listing()
    root = directory(PSC)
    staging, target, old = (root / f"{PSC_PARTS}{end}" for end in (".new", "", ".old"))
    staging.mkdir(exist_ok=True)
    keep = {_extract_name(file) for _, file in parts}
    for stale in staging.iterdir():
        if stale.name not in keep:
            stale.unlink()
    for _, file in parts:
        out = staging / _extract_name(file)
        if out.exists():
            continue
        path, url = staging / file, urllib.parse.urljoin(PSC_PAGE, file)
        try:
            _download(url, path)
            body = _psc_extract(path, file.replace(".zip", ".txt"))
        except urllib.error.HTTPError as exc:
            if exc.code != 404:
                raise
            exc.close()
            raise ValueError(f"{url} is gone (404): the {date} snapshot was most "
                             f"likely replaced during the fetch; fetch again") from None
        except (zipfile.BadZipFile, zlib.error) as exc:
            raise ValueError(f"{file} is not a readable zip ({exc}); fetch again"
                             ) from None
        finally:
            path.unlink(missing_ok=True)
        corpus_build.write_atomic(out, body)
    shutil.rmtree(old, ignore_errors=True)
    if target.exists():
        os.replace(target, old)
    os.replace(staging, target)
    shutil.rmtree(old, ignore_errors=True)


def _psc_part(path: Path) -> tuple[dict[str, int], list[str]]:
    """One extract's counts and record lines, or ValueError naming the
    refresh where it is not an extract _psc_extract wrote for its name."""
    member = re.sub(r"\.v\d+\.jsonl\.gz$", ".txt", path.name)
    try:
        header, *records = corpus_build.jsonl_lines(
            gzip.decompress(path.read_bytes()).decode())
        head = json.loads(header)
        counts = head["counts"]
        if (head["part"] != member or not isinstance(counts, dict)
                or not all(type(n) is int for n in counts.values())):
            raise ValueError("its header does not describe it")
    except (OSError, EOFError, ValueError, KeyError, TypeError, zlib.error) as exc:
        raise ValueError(f"{path} is not an extract this tool wrote ({exc})"
                         f"{_again(PSC)}") from None
    return counts, records


def _psc_read(parts: Path) -> Fetched:
    """The corpus from the cached extracts: every part of one snapshot,
    checked by name before any is read, or ValueError naming the
    refresh. A record is a distinct filed name -- the display name, its
    four boxes and the nationality -- however many companies file it,
    one in PSC_SAMPLE of them kept; a sampled name with every box empty
    is counted and dropped. Past PSC_MAX_BAD of the individuals skipped
    for either reason _psc_extract skips one, or of the lines not JSON,
    or with fewer than PSC_MIN_INDIVIDUALS of the lines individuals, the
    snapshot is refused rather than read as a smaller corpus."""
    found: dict[int, Path] = {}
    dates, totals = set(), set()
    for path in sorted(parts.glob("*.jsonl.gz")):
        named = _PSC_EXTRACT.fullmatch(path.name)
        if not named or int(named[4]) != PSC_EXTRACT_VERSION:
            raise ValueError(f"{path} is not an extract of version "
                             f"{PSC_EXTRACT_VERSION}{_again(PSC)}")
        number = int(named[2])
        if number in found:
            raise ValueError(f"{parts} holds part {number} twice{_again(PSC)}")
        found[number] = path
        dates.add(named[1])
        totals.add(int(named[3]))
    if not _one_snapshot(dates, totals, list(found)):
        raise ValueError(f"{parts} holds parts {sorted(found)} of {sorted(totals)} "
                         f"dated {sorted(dates)}, not every part of one snapshot"
                         f"{_again(PSC)}")
    counts: Counter[str] = Counter()
    lines: set[str] = set()
    for number in sorted(found):
        part_counts, records = _psc_part(found[number])
        counts.update(part_counts)
        lines.update(line for line in records if psc_sampled(line))
    individuals = sum(counts[kind] for kind in PSC_KINDS)
    if individuals < counts["lines"] * PSC_MIN_INDIVIDUALS:
        raise ValueError(f"{individuals:,} of {counts['lines']:,} lines are "
                         f"{' or '.join(PSC_KINDS)} records: a kind has been "
                         f"renamed or moved under PSC_KINDS")
    _refuse_past([(counts["lines_not_json"], counts["lines"], PSC_MAX_BAD,
                   "lines are not JSON"),
                  (counts["individuals_without_name_elements"], individuals, PSC_MAX_BAD,
                   "individuals have no name_elements"),
                  (counts["names_not_their_boxes_joined"], individuals, PSC_MAX_BAD,
                   "individuals' display names are not their four boxes joined")],
                 "the snapshot's layout has changed under PSC_ELEMENTS")
    records = [json.loads(line) for line in sorted(lines)]
    named_records = [record for record in records if "name" in record]
    if len(named_records) < len(records):
        counts["sampled_names_that_are_empty"] = len(records) - len(named_records)
    return Fetched(named_records, dates.pop(), {
        "parts": max(totals), "sample": f"1 in {PSC_SAMPLE}",
        **{key: counts[key] for key in sorted(counts)}})


def fetch_psc() -> Fetched:
    """One in PSC_SAMPLE of the snapshot's distinct filed names
    (_psc_read), read from the extracts cached beside the corpus
    (downloaded when missing, and again by `fetch --refresh`). The data
    date is the date the part files are named by; the snapshot holds
    what was filed up to the end of the day before."""
    parts = directory(PSC) / PSC_PARTS
    if not parts.is_dir():
        renew_psc()
    return _psc_read(parts)


check_psc = _pinned("sample", lambda: f"1 in {PSC_SAMPLE}",
                    "keeps {held} filed names, and this tool keeps {wanted}")
