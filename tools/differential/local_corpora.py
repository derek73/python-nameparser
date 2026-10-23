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
  came from where the source says: a ClinicalTrials.gov official, with
  the study and role; one distinct FEC name, alone. The counts are
  counted from here.
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
a later fetch may differ. A new source is a SOURCES row: a fetch
function returning the records and the source's data date, and for a
source that caches its own input, the hooks that renew it on a
refresh and refuse a corpus read from another version of it.

ctgov-officials -- every overall official of every study on
ClinicalTrials.gov, whatever the role (principal investigators, study
directors and chairs, and a few sub-investigators and officials with no
role), the name as the sponsor's staff typed it into a free-text field,
with credentials, job titles and typos left in. Fetched from API v2
(NLM). ClinicalTrials.gov's terms ask anyone redistributing the data to
credit it, show NLM's processing date and say what was changed: every
report here and the tools/name_usage.py row carry the credit and the
date, and the names are kept unchanged.

fec-individuals -- the distinct names of every individual contributor
in the FEC's bulk file of itemized contributions by individuals for the
cycle (indiv26.zip, 2.3 GB on 2026-10-18, downloaded into the cache once
and read without unpacking; `fetch --refresh` downloads it again).
Itemized contributions only: a committee need itemize only a donor
whose gifts to it pass $200, so a smaller donor is there only where a
committee itemized the gift anyway. Mostly a filer's software writing a form's fields in a fixed
order, family, comma, given, in capitals -- every one of the 1,893,964
names on 2026-10-18 was in capitals and all but three held a comma --
with hand-typed text inside the fields: 3,306 held a second comma, for
a credential run or a suffix in a part of its own. So it is the
population for the one-case family-comma shape, and blind to case and
to names written in their spoken order. The FEC's terms (52 U.S.C.
30111(a)(4)) bar using the names to solicit contributions or for any
commercial purpose, which the credit line every report opens with
repeats; only the NAME column is kept.

ukec-individuals -- the distinct names of the individual donors in the
UK Electoral Commission's register of donations, to parties, their
members, third parties, permitted participants and regulated donees,
from the search's CSV export under the site's own default filter (9.5
MB on 2026-10-22, fetched whole on every fetch). That default leaves
out donations reported only before a poll: 374 rows and 21 names on
2026-10-22. The export's accepted dates ran from 2001 to 2026. A name as
the donee's return gave it, so mostly in its spoken order, mixed case,
with the title the donor used: of its 15,214 names on 2026-10-22,
parse() read a title in 8,219 and a suffix in 320 (MP, OBE, CBE, QC),
9 were in capitals and 2 held a comma. So it is the population for
titled British names, and blind to the family-comma shape. The Commission
publishes its documents under the Open Government Licence v3.0, but
the register states no reuse terms of its own, which the credit line
says; only the DonorName column is kept.
"""
from __future__ import annotations

import argparse
import csv
import functools
import dataclasses
import hashlib
import http.client
import inspect
import io
import json
import os
import re
import sys
import time
import types
import unicodedata
import urllib.error
import urllib.parse
import urllib.request
import zipfile
from collections import Counter
from collections.abc import Callable, Iterator
from dataclasses import dataclass, field
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
    #: What one record is, for counts: "officials", "names".
    unit: str
    fetch: Callable[[], Fetched]
    #: What `fetch --refresh` runs first, for a source whose fetch reads
    #: an input cached beside the corpus: fetches that input anew,
    #: replacing the cached copy only once the new one is whole.
    renew: Callable[[], None] | None = None
    #: Why load() should refuse a meta.json this version of the source
    #: did not write (another FEC cycle), or "" to accept it.
    check: Callable[[dict[str, Any]], str] | None = None


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
            if (isinstance(exc, urllib.error.HTTPError) and exc.code < 500
                    and exc.code != 429 or attempt == CTGOV_RETRIES - 1):
                raise
            wait = 2 ** attempt
            if isinstance(exc, urllib.error.HTTPError):
                after = exc.headers.get("Retry-After", "") if exc.headers else ""
                if after.isdigit():
                    wait = max(wait, min(int(after), 60))
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


# -- FEC individual contributions --------------------------------------------

FEC_CYCLE = "2026"
FEC_ZIP = f"indiv{FEC_CYCLE[2:]}.zip"
FEC_URL = f"https://www.fec.gov/files/bulk-downloads/{FEC_CYCLE}/{FEC_ZIP}"
#: The whole cycle in one file; the zip's by_date/ members repeat it in slices.
FEC_MEMBER = "itcont.txt"
#: The file's columns (the FEC's contributions-by-individuals file
#: description): 21, pipe-separated, ENTITY_TP the 7th and NAME the 8th.
FEC_COLUMNS, FEC_ENTITY, FEC_NAME = 21, 6, 7
FEC_CHUNK = 1 << 20
#: The file has no header row to check the columns against, so a fetch
#: refuses one that no longer looks like the file the constants above
#: were written for: more than this share of its lines malformed or not
#: UTF-8 (none were, of 34,264,742 lines in the file dated 2026-10-18),
#: or fewer than FEC_MIN_COMMA of its names holding a comma (1,893,961
#: of 1,893,964 did), which is what a column moved under NAME would show.
FEC_MAX_BAD = 1 / 10_000
FEC_MIN_COMMA = 0.9


def _fec_download(path: Path) -> None:
    """Download FEC_URL to `path` through a .part file, refusing a body
    whose length differs from the stated Content-Length, or with no
    Content-Length at all: a cut zip would otherwise fail later as a
    BadZipFile that says nothing about the download. The cached zip is
    replaced only once the new one is whole, a failed download leaves no
    .part behind, and a zip of another cycle is removed once this one
    has arrived."""
    print(f"downloading {FEC_URL} ...", file=sys.stderr)
    request = urllib.request.Request(FEC_URL, headers={"User-Agent": USER_AGENT})
    partial = path.with_name(path.name + ".part")
    try:
        got = 0
        with urllib.request.urlopen(request, timeout=60) as response, \
                partial.open("wb") as out:
            stated = response.headers.get("Content-Length", "")
            while chunk := response.read(FEC_CHUNK):
                out.write(chunk)
                got += len(chunk)
        if not stated.isdigit() or int(stated) != got:
            raise ValueError(f"{FEC_URL} sent {got:,} bytes where it stated "
                             f"{stated or 'no length'}; fetch again")
    except BaseException:
        partial.unlink(missing_ok=True)
        raise
    os.replace(partial, path)
    for stale in path.parent.glob("indiv*.zip"):
        if stale != path:
            stale.unlink()


def _fec_read(path: Path) -> Fetched:
    names: set[str] = set()
    entities: Counter[str] = Counter()
    rows = malformed = latin1 = nameless = 0
    with zipfile.ZipFile(path) as archive:
        if FEC_MEMBER not in archive.namelist():
            raise ValueError(f"{path} holds no {FEC_MEMBER}")
        member = archive.getinfo(FEC_MEMBER)
        stamp = "{:04d}-{:02d}-{:02d}T{:02d}:{:02d}:{:02d}".format(*member.date_time)
        with archive.open(member) as lines:
            for line in lines:
                rows += 1
                try:
                    text = line.decode("utf-8")
                except UnicodeDecodeError:
                    latin1 += 1
                    text = line.decode("latin-1")
                cols = text.rstrip("\r\n").split("|")
                if len(cols) != FEC_COLUMNS:
                    malformed += 1
                    continue
                entities[cols[FEC_ENTITY]] += 1
                if cols[FEC_ENTITY] != "IND":
                    continue
                if name := cols[FEC_NAME].strip():
                    names.add(name)
                else:
                    nameless += 1
    for count, what in ((malformed, f"not {FEC_COLUMNS} columns"),
                        (latin1, "not UTF-8")):
        if count > rows * FEC_MAX_BAD:
            raise ValueError(f"{count:,} of {rows:,} lines of {path} are {what}: "
                             f"the file's layout has changed under FEC_COLUMNS")
    with_comma = sum("," in name for name in names)
    if names and with_comma < len(names) * FEC_MIN_COMMA:
        raise ValueError(f"{with_comma:,} of {len(names):,} names hold a comma: "
                         f"column {FEC_NAME + 1} of {path} no longer holds NAME")
    return Fetched([{"name": name} for name in sorted(names)], stamp, {
        "cycle": FEC_CYCLE, "file": f"{FEC_ZIP}/{FEC_MEMBER}", "rows": rows,
        "individual_contributions": entities["IND"],
        "rows_from_other_entities": sum(entities.values()) - entities["IND"],
        "individuals_without_a_name": nameless,
        "lines_not_21_columns": malformed, "lines_not_utf8": latin1})


def fetch_fec() -> Fetched:
    """The distinct names of every individual contributor in the cycle's
    file, one record per name, read from the zip cached beside the
    corpus (downloaded when missing, and again by `fetch --refresh`).

    A record is a NAME, not a contribution or a contributor: one donor
    gives many times (34,264,742 rows held 1,893,964 names in the file
    dated 2026-10-18), and a contribution count would weight a shape by
    how often its bearers give. Only the name is kept, stripped of the
    spaces around it; the address, employer and amount columns are read
    past. The data date is the member's own timestamp, which carries no
    time zone. A line that is not 21 columns is counted and skipped, a
    line that is not UTF-8 is counted and read as Latin-1, and a row from
    an entity that is not a person and a person with no name are
    counted; past FEC_MAX_BAD, or with too few names holding a comma, the
    file is refused rather than read as a smaller or a different corpus."""
    path = directory("fec-individuals") / FEC_ZIP
    if not path.exists():
        _fec_download(path)
    try:
        return _fec_read(path)
    except zipfile.BadZipFile as exc:
        raise ValueError(f"{path} is not a readable zip ({exc}); download it "
                         f"again: {fetch_command('fec-individuals', refresh=True)}"
                         ) from None


def renew_fec() -> None:
    """Download the current file over the cached zip."""
    _fec_download(directory("fec-individuals") / FEC_ZIP)


def check_fec(meta: dict[str, Any]) -> str:
    cycle = meta["detail"].get("cycle")
    return "" if cycle == FEC_CYCLE else (
        f"holds the {cycle} cycle, and this tool reads the {FEC_CYCLE} cycle")


# -- UK Electoral Commission donations -----------------------------------------

#: The register's search, filtered to donations from individuals, with
#: the search page's other defaults (prePoll=false among them, which
#: leaves out the donations reported only before a poll). The CSV export ignores `rows`
#: (rows=10 returned all 42,355 on 2026-10-22), and the JSON search
#: answering the same filter states the register's total, which is how a
#: capped or cut export is told from the whole register.
UKEC_API = "https://search.electoralcommission.org.uk/api"
UKEC_QUERY: list[tuple[str, str]] = [
    ("start", "0"), ("rows", "1000000"), ("query", ""), ("sort", "AcceptedDate"),
    ("order", "desc"), *(("et", et) for et in ("pp", "ppm", "tp", "perpar", "rd")),
    ("date", "Reported"), ("from", ""), ("to", ""), ("rptPd", ""),
    ("prePoll", "false"), ("postPoll", "true"), ("donorStatus", "individual"),
    ("isIrishSourceYes", "true"), ("isIrishSourceNo", "true")]
UKEC_CSV_URL = f"{UKEC_API}/csv/Donations?{urllib.parse.urlencode(UKEC_QUERY)}"
UKEC_COUNT_URL = f"{UKEC_API}/search/Donations?" + urllib.parse.urlencode(
    [(k, "1" if k == "rows" else v) for k, v in UKEC_QUERY])
#: The export's header on 2026-10-22, which a fetch requires exactly: the
#: names are read by column name, but a renamed or added column is a
#: changed export whose meaning nobody has checked.
UKEC_COLUMNS = (
    "ECRef", "RegulatedEntityName", "RegulatedEntityType", "Value", "AcceptedDate",
    "AccountingUnitName", "DonorName", "AccountingUnitsAsCentralParty",
    "IsSponsorship", "DonorStatus", "RegulatedDoneeType",
    "CompanyRegistrationNumber", "Postcode", "DonationType", "NatureOfDonation",
    "PurposeOfVisit", "DonationAction", "ReceivedDate", "ReportedDate",
    "IsReportedPrePoll", "ReportingPeriodName", "IsBequest", "IsAggregation",
    "RegulatedEntityId", "AccountingUnitId", "DonorId", "CampaigningName",
    "RegisterName", "IsIrishSource")
UKEC_INDIVIDUAL = "Individual"
#: The share of rows a fetch skips before refusing the export: rows that
#: are not 29 fields, and rows from a donor that is not an individual,
#: which the filter asks the server to leave out (none of 42,355 rows
#: was either on 2026-10-22).
UKEC_MAX_BAD = 1 / 10_000
#: The share of individuals with no name a fetch accepts: 4 of 42,355
#: rows on 2026-10-22, so a tenth of a percent leaves room for the
#: register's own blanks and refuses a column emptied wholesale.
UKEC_MAX_NAMELESS = 1 / 1000


def _ukec_total() -> tuple[int, str]:
    """The register's total for the filter, and the time the search
    answered, from the JSON search."""
    body = corpus_build.fetch_bytes(UKEC_COUNT_URL, user_agent=USER_AGENT,
                                    timeout=60)
    data = corpus_build.parse_json(body, UKEC_COUNT_URL)
    if not isinstance(data, dict):
        raise ValueError(f"{UKEC_COUNT_URL} states no Total")
    total = data.get("Total")
    if not isinstance(total, int) or isinstance(total, bool):
        raise ValueError(f"{UKEC_COUNT_URL} states no Total")
    stamp = re.fullmatch(r"/Date\((\d+)\)/", str(data.get("Generated", "")))
    if not stamp:
        raise ValueError(f"{UKEC_COUNT_URL} states no Generated time")
    when = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(int(stamp[1]) / 1000))
    return total, when


def _ukec_read(body: bytes, total: int) -> Fetched:
    try:
        text = body.decode("utf-8-sig")
    except UnicodeDecodeError as exc:
        raise ValueError(f"the export is not UTF-8 ({exc}); fetch again") from None
    try:
        return _ukec_rows(list(csv.reader(io.StringIO(text, newline=""))),
                          text, total)
    except csv.Error as exc:
        raise ValueError(f"the export is not CSV this reads ({exc}); "
                         f"fetch again") from None


def _ukec_rows(rows: list[list[str]], text: str, total: int) -> Fetched:
    header = tuple(rows[0]) if rows else ()
    if header != UKEC_COLUMNS:
        raise ValueError(f"the export's header is not the {len(UKEC_COLUMNS)} "
                         f"columns UKEC_COLUMNS names: {', '.join(header)}")
    # csv returns a body cut inside its last row as a short last row,
    # which the count below would take for a whole one.
    if not text.endswith("\n") or len(rows[-1]) != len(UKEC_COLUMNS):
        raise ValueError("the export's last row is cut short; fetch again")
    status, name_at, donor_at = (UKEC_COLUMNS.index(c) for c in (
        "DonorStatus", "DonorName", "DonorId"))
    names: set[str] = set()
    donor_ids: set[str] = set()
    statuses: Counter[str] = Counter()
    count = malformed = nameless = 0
    for row in rows[1:]:
        count += 1
        if len(row) != len(UKEC_COLUMNS):
            malformed += 1
            continue
        statuses[row[status]] += 1
        if row[status] != UKEC_INDIVIDUAL:
            continue
        if row[donor_at]:
            donor_ids.add(row[donor_at])
        if name := row[name_at].strip():
            names.add(name)
        else:
            nameless += 1
    other = count - malformed - statuses[UKEC_INDIVIDUAL]
    if count != total:
        raise ValueError(f"the export held {count:,} donations where the search "
                         f"counts {total:,}: a capped or cut export; fetch again")
    for skipped, share, what in (
            (malformed, UKEC_MAX_BAD, f"not {len(UKEC_COLUMNS)} fields"),
            (other, UKEC_MAX_BAD, f"from a donor that is not {UKEC_INDIVIDUAL!r}"),
            (nameless, UKEC_MAX_NAMELESS, "from an individual with no name")):
        if skipped > count * share:
            raise ValueError(f"{skipped:,} of {count:,} rows of the export are "
                             f"{what}: the export is not the one this reads")
    return Fetched([{"name": name} for name in sorted(names)], "", {
        "donations": count, "donor_ids": len(donor_ids),
        "individuals_without_a_name": nameless,
        "rows_not_29_fields": malformed, "rows_not_individual": other})


def fetch_ukec() -> Fetched:
    """The distinct names of every individual donor in the register, one
    record per name, from the export's DonorName column; the other
    columns are read past.

    A record is a NAME, not a donation or a DonorId: one name often
    holds several IDs, which seem to come with reports rather than with
    people (15,214 names held 24,473 IDs on 2026-10-22, and 2,663 names
    held several IDs at one donee alone, though some of those may be
    two people of one name), so a count of IDs would weight a name by
    how often it was reported. The register's total is read before and
    after the export, which must hold exactly that many rows and end
    with a whole row, so a register that changed during the fetch, or an
    export cut or capped, is refused. The data date is when the first
    search answered: the register states no date of its own, so it is
    the fetch's time, in UTC. A row that is not 29 fields, or from a
    donor that is not an individual, is counted and skipped, as is an
    individual with no name; past UKEC_MAX_BAD of either of the first
    two, or UKEC_MAX_NAMELESS of the third, the export is refused."""
    before, when = _ukec_total()
    print(f"downloading {before:,} donations from {UKEC_API} ...", file=sys.stderr)
    body = corpus_build.fetch_bytes(UKEC_CSV_URL, user_agent=USER_AGENT, timeout=300)
    after, _ = _ukec_total()
    if after != before:
        raise ValueError(f"the register changed during the fetch ({before:,} -> "
                         f"{after:,} donations); fetch again")
    return dataclasses.replace(_ukec_read(body, before), data_date=when)


SOURCES: dict[str, Source] = {
    "ctgov-officials": Source(
        credit="ClinicalTrials.gov (NLM) study officials", unit="officials",
        fetch=fetch_ctgov),
    "fec-individuals": Source(
        credit=f"FEC individual contributions, {FEC_CYCLE} cycle "
               f"(52 U.S.C. 30111(a)(4): not for soliciting or commercial use)",
        unit="names", fetch=fetch_fec, renew=renew_fec, check=check_fec),
    "ukec-individuals": Source(
        credit="UK Electoral Commission register of donations, individual "
               "donors (reuse terms for the register not stated)",
        unit="names", fetch=fetch_ukec),
}


# -- the cache ---------------------------------------------------------------

def directory(source: str, *, create: bool = True) -> Path:
    if source not in SOURCES:
        raise ValueError(f"no local corpus {source!r}; the sources are "
                         + ", ".join(sorted(SOURCES)))
    return corpus_build.cache_dir(f"local/{source}", create=create)


def fetch_command(source: str, *, refresh: bool = False) -> str:
    """The command that fetches `source`, for messages that name it."""
    return (f"tools/differential/local_corpora.py fetch {source}"
            + (" --refresh" if refresh else ""))


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


def _again(source: str) -> str:
    return f"; fetch it again: {fetch_command(source, refresh=True)}"


def _verified(source: str, name: str, sha256: str) -> bytes:
    """`source`'s file `name`, or ValueError naming the way out unless
    it matches the sha256 meta.json gives it."""
    path = directory(source, create=False) / name
    body = path.read_bytes() if path.exists() else b""
    if hashlib.sha256(body).hexdigest() != sha256:
        raise CorpusDamaged(f"{path} does not match the sha256 in {META}{_again(source)}")
    return body


def read_records(source: str, meta: dict[str, Any]) -> list[dict[str, str]]:
    """raw.jsonl's records, checked against its sha256 again (load()
    checked it, but the file is read later and may have changed), each
    holding a name, or CorpusDamaged naming the way out."""
    raw = _verified(source, RAW, meta["sha256"])
    records = [json.loads(line) for line in corpus_build.jsonl_lines(raw.decode())]
    if any(not isinstance(r, dict) or not isinstance(r.get("name"), str)
           for r in records):
        raise CorpusDamaged(f"{directory(source, create=False) / RAW} holds a record "
                         f"without a name{_again(source)}")
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


def fold_fingerprint() -> str:
    """A hash of what turns the records into an index, read from the code
    that is running rather than the source on disk, which may have been
    edited since: _FOLD_CODE's functions and corpus_build.jsonl_lines
    (which cuts raw.jsonl into records), _FOLD_CONSTANTS, WordIndex's
    fields, and the Unicode database that casefold(), NFC and the
    category test read, which a new Python may move. The bytecode is the
    interpreter's own, so a new Python rebuilds the index too."""
    module = globals()
    functions = [module[name] for name in _FOLD_CODE] + [corpus_build.jsonl_lines]
    parts = [part for fn in functions for part in _code_digest(inspect.unwrap(fn).__code__)]
    parts += [_stable(module[name]) for name in _FOLD_CONSTANTS]
    parts += [repr([f.name for f in dataclasses.fields(WordIndex)]),
              unicodedata.unidata_version, sys.version]
    return hashlib.sha256("\0".join(parts).encode()).hexdigest()


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
