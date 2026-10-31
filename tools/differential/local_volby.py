"""The cz-candidates local corpus: the Czech election candidate registers.

cz-candidates -- every candidate on the registers the Czech Statistical
Office (ČSÚ) publishes for an election on volby.gov.cz, one CSV per
election, each candidate's name in the four boxes it was filed in: the
title before the name (TITULPRED), the given names (JMENO), the
surname (PRIJMENI) and the title after it (TITULZA). A local corpus
whose names carry their fields (local_agreement.FIELDED), so
local_agreement.py scores the parser against them, by election. It is
the corpora's one large population of titled names with the title
stated: of the 197,506 candidates of the 2022 municipal elections,
30.9% filed a title before the name and 3.8% one after it (2026-10-30),
nearly all academic degrees (Ing., Mgr., Bc., MUDr.; Ph.D., DiS.,
MBA), with no courtesy titles or offices.

A record's name is COMPOSED, not written by anyone: the boxes joined in
the Czech convention, `TITULPRED JMENO PRIJMENI, TITULZA` (`Ing. Jan
Novák, Ph.D.`), so it holds no case, spacing or punctuation of its own
beyond what the boxes hold. The register's terms
(https://csu.gov.cz/podminky_pro_vyuzivani_a_dalsi_zverejnovani_statistickych_udaju_csu,
which the open-data index links, read 2026-10-30) license ČSÚ's
statistical information under CC BY 4.0, and ask that whoever spreads
the data state the licence, best by a link to that page, and mark
modified or derived data as such, never as unchanged official
statistics; the composed names are derived, which the credit line
says. The names are personal data, published by law, and are cached,
never committed.
"""
from __future__ import annotations

import csv
import io
import re
import sys
import urllib.parse
import zipfile
from collections import Counter
from typing import Any

from local_core import Fetched, _refuse_past, _retried


VOLBY = "cz-candidates"
VOLBY_SITE = "https://volby.gov.cz/opendata/"
#: Each election read, by the code volby.gov.cz files it under: the
#: register's member in the zip, and the candidates it held on
#: 2026-10-30. An election is over and its register final, so a
#: register holding another number is a changed file (a register
#: trimmed to the elected, or a revision), refused until it is measured
#: and the pin moved by hand. The index lists kv2002 to kv2026 and
#: ps2002 to ps2025 too; adding one is a row here, measured first.
VOLBY_ELECTIONS: dict[str, tuple[str, int]] = {
    "kv2022": ("csv_od/kvrk.csv", 197_506),
    "ps2025": ("csv_od/psrk.csv", 4_475),
}
#: The four name boxes, by column, and the record key each is kept
#: under, in the order the composed name joins them (compose).
VOLBY_BOXES = {"TITULPRED": "titulpred", "JMENO": "jmeno", "PRIJMENI": "prijmeni",
               "TITULZA": "titulza"}
#: How a record's name is built from its boxes (compose), in meta.json's
#: detail: a change to compose bumps it, and a corpus composed by
#: another version is refused on load (check_volby), since the sha256
#: checks prove the files are the ones fetched, not that today's code
#: would compose them so.
VOLBY_READ_VERSION = 1
#: The share of an election's rows a fetch skips before refusing the
#: register: rows that are not the header's width, and candidates with
#: no given name or no surname (none of either in 202,000 rows on
#: 2026-10-30).
VOLBY_MAX_BAD = 1 / 10_000
#: The least share of an election's candidates filing a title before or
#: after the name: 32.2% of kv2022 and 45.6% of ps2025 did on
#: 2026-10-30. A title column emptied or renamed would otherwise read
#: as a register of untitled names, the shape this corpus is for.
VOLBY_MIN_TITLED = 1 / 5


def _zip_link(election: str) -> re.Pattern[str]:
    """The register's CSV zip as the election's index page links it:
    named by the election and a date stamp (KV2022reg20260328_csv.zip,
    KV2018_reg_20230224_csv.zip), which is read off the page, since a
    guessed stamp answers an HTML 404 page."""
    return re.compile(rf'href="({re.escape(election)}_?reg_?(\d{{8}})_csv\.zip)"',
                      re.IGNORECASE)


def index_url(election: str) -> str:
    return f"{VOLBY_SITE}{election}/{election}_opendata.htm"


def _register_zip(election: str) -> tuple[str, str]:
    """The newest register zip the index page links, and its stamp as a
    date: ps2021's lists a revision beside the first register."""
    url = index_url(election)
    page = _retried(url, lambda body: body, 0).decode("utf-8", "replace")
    links = _zip_link(election).findall(page)
    if not links:
        raise ValueError(f"{url} links no register CSV zip: the page has changed")
    file, stamp = max(links, key=lambda link: link[1])
    return urllib.parse.urljoin(url, file), f"{stamp[:4]}-{stamp[4:6]}-{stamp[6:]}"


def _a_zip(body: bytes) -> bytes:
    """`body` where it is a zip, else ValueError, which _retried takes
    for a body cut short in transit."""
    if not zipfile.is_zipfile(io.BytesIO(body)):
        raise ValueError(f"the answer is not a zip ({body[:15]!r}...)")
    return body


def compose(boxes: dict[str, str]) -> str:
    """A record's name: its boxes joined in the Czech convention,
    `TITULPRED JMENO PRIJMENI, TITULZA`, an empty box left out with its
    separator."""
    name = " ".join(v for k in ("titulpred", "jmeno", "prijmeni") if (v := boxes.get(k)))
    return f"{name}, {boxes['titulza']}" if boxes.get("titulza") else name


def _volby_rows(text: str, election: str) -> tuple[set[str], dict[str, int]]:
    """One election's register read down to what the corpus keeps: each
    distinct candidate's four boxes, stripped, keyed by the composed
    name, and the counts. Columns are read by name, since the elections'
    registers differ in every other column, and a register missing a
    box's column, or whose last row is cut short, is refused."""
    rows = list(csv.reader(io.StringIO(text, newline="")))
    header = rows[0] if rows else []
    missing = [c for c in VOLBY_BOXES if c not in header]
    if missing:
        raise ValueError(f"the {election} register has no column {', '.join(missing)}: "
                         f"its layout has changed under VOLBY_BOXES")
    # csv returns a body cut inside its last row as a short last row
    # (AGENTS.md's Gotchas): a cut only shortens a row, so a long last
    # row is left to the malformed share.
    if not text.endswith("\n") or len(rows) < 2 or len(rows[-1]) < len(header):
        raise ValueError(f"the {election} register's last row is cut short or "
                         f"blank; fetch again")
    at = {key: header.index(column) for column, key in VOLBY_BOXES.items()}
    counts: Counter[str] = Counter()
    kept: set[str] = set()
    for row in rows[1:]:
        counts["candidates"] += 1
        if len(row) != len(header):
            counts["rows_not_the_header_s_width"] += 1
            continue
        boxes = {key: " ".join(row[i].split()) for key, i in at.items()}
        if not boxes["jmeno"] or not boxes["prijmeni"]:
            counts["candidates_without_a_given_name_or_surname"] += 1
            continue
        counts["titled"] += bool(boxes["titulpred"] or boxes["titulza"])
        kept.add("\t".join(boxes[k] for k in VOLBY_BOXES.values()))
    return kept, dict(counts)


def _volby_read(election: str, body: bytes) -> tuple[list[dict[str, str]], dict[str, int]]:
    """One election's records from its zip, or ValueError where the
    register is not the one this reads: no member, not UTF-8, another
    number of candidates than VOLBY_ELECTIONS pins, past VOLBY_MAX_BAD
    of its rows skipped, or under VOLBY_MIN_TITLED of them titled."""
    member, pinned = VOLBY_ELECTIONS[election]
    try:
        with zipfile.ZipFile(io.BytesIO(body)) as archive:
            if member not in archive.namelist():
                raise ValueError(f"the {election} zip holds no {member}")
            raw = archive.read(member)
    except zipfile.BadZipFile as exc:
        raise ValueError(f"the {election} zip cannot be read ({exc}); fetch again"
                         ) from None
    try:
        text = raw.decode("utf-8-sig")
    except UnicodeDecodeError as exc:
        raise ValueError(f"the {election} register is not UTF-8 ({exc})") from None
    try:
        kept, counts = _volby_rows(text, election)
    except csv.Error as exc:
        raise ValueError(f"the {election} register is not CSV this reads ({exc})"
                         ) from None
    candidates = counts["candidates"]
    if candidates != pinned:
        raise ValueError(f"the {election} register holds {candidates:,} candidates "
                         f"where VOLBY_ELECTIONS pins {pinned:,}: a changed register; "
                         f"measure it and move the pin")
    are = f"of the {election} register's rows are"
    _refuse_past([(counts.get("rows_not_the_header_s_width", 0), candidates, VOLBY_MAX_BAD,
                   f"{are} not the header's width"),
                  (counts.get("candidates_without_a_given_name_or_surname", 0), candidates,
                   VOLBY_MAX_BAD, f"{are} a candidate with no given name or surname")],
                 "the register is not the one this reads")
    if counts.get("titled", 0) < candidates * VOLBY_MIN_TITLED:
        raise ValueError(f"{counts.get('titled', 0):,} of the {election} register's "
                         f"{candidates:,} candidates filed a title: a title column "
                         f"emptied or moved")
    records = []
    for line in sorted(kept):
        boxes = dict(zip(VOLBY_BOXES.values(), line.split("\t"), strict=True))
        records.append({"name": compose(boxes), "election": election,
                        **{k: v for k, v in boxes.items() if v}})
    return records, {**counts, "records": len(records)}


def fetch_volby() -> Fetched:
    """The distinct candidates of every election in VOLBY_ELECTIONS, one
    record per election and distinct four boxes: the composed name
    (compose), the election and the boxes filled. A candidate who stood
    twice in one election under the same boxes, or two who share them,
    are one record; the age, occupation, municipality and party columns
    are read past. The data date names each election's register stamp,
    the date the zip's file name carries."""
    records: list[dict[str, str]] = []
    detail: dict[str, Any] = {"elections": " ".join(VOLBY_ELECTIONS),
                              "read_version": VOLBY_READ_VERSION}
    stamps = []
    for election in VOLBY_ELECTIONS:
        url, stamp = _register_zip(election)
        print(f"downloading {url} ...", file=sys.stderr)
        body = _retried(url, _a_zip, 0, timeout=300)
        read, counts = _volby_read(election, body)
        records += read
        stamps.append(f"{election} {stamp}")
        detail[election] = {"zip": url.rsplit("/", 1)[1], **counts}
    return Fetched(records, ", ".join(stamps), detail)


def check_volby(meta: dict[str, Any]) -> str:
    """Why a corpus fetched for other elections than VOLBY_ELECTIONS,
    or composed by another VOLBY_READ_VERSION, is refused, or ""."""
    detail = meta["detail"]
    if detail.get("elections") != " ".join(VOLBY_ELECTIONS):
        return (f"the corpus holds the elections {detail.get('elections')}, and this "
                f"tool reads {' '.join(VOLBY_ELECTIONS)}")
    if detail.get("read_version") != VOLBY_READ_VERSION:
        return (f"the corpus was composed by version {detail.get('read_version')} of "
                f"compose, and this tool is version {VOLBY_READ_VERSION}")
    return ""
