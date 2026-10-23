"""The ukec-individuals local corpus: the UK Electoral Commission's donors.

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
titled British names, and blind to the family-comma shape. The
counts are dated by the day they were fetched; the data date the
fetch stamps, the search's own time in UTC, was 2026-10-23T03:13:19Z. The Commission
publishes its documents under the Open Government Licence v3.0, but
the register states no reuse terms of its own, which the credit line
says; only the DonorName column is kept.
"""
from __future__ import annotations

import csv
import dataclasses
import io
import re
import sys
import time
import urllib.parse
from collections import Counter

import corpus_build
from local_core import Fetched, _refuse_past, _retried


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
    data = _retried(UKEC_COUNT_URL,
                    lambda body: corpus_build.parse_json(body, UKEC_COUNT_URL), 0)
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
    # which the count below would take for a whole one. A cut only
    # shortens a row, so a long last row is left to the malformed share;
    # the export ended with a line break on 2026-10-22.
    if not text.endswith("\n") or len(rows[-1]) < len(UKEC_COLUMNS):
        raise ValueError("the export's last row is cut short or blank; "
                         "fetch again")
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
    are = "rows of the export are"
    _refuse_past([(malformed, count, UKEC_MAX_BAD, f"{are} not {len(UKEC_COLUMNS)} fields"),
                  (other, count, UKEC_MAX_BAD,
                   f"{are} from a donor that is not {UKEC_INDIVIDUAL!r}"),
                  (nameless, count, UKEC_MAX_NAMELESS, f"{are} from an individual with no name")],
                 "the export is not the one this reads")
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
    body = _retried(UKEC_CSV_URL, lambda body: body, 0, timeout=300)
    after, _ = _ukec_total()
    if after != before:
        raise ValueError(f"the register changed during the fetch ({before:,} -> "
                         f"{after:,} donations); fetch again")
    return dataclasses.replace(_ukec_read(body, before), data_date=when)
