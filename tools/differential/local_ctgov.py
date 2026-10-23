"""The ctgov-officials local corpus: ClinicalTrials.gov's study officials.

ctgov-officials -- every overall official of every study on
ClinicalTrials.gov, whatever the role (principal investigators, study
directors and chairs, and a few sub-investigators and officials with no
role), the name as the sponsor's staff typed it into a free-text field,
with credentials, job titles and typos left in. Fetched from API v2
(NLM). ClinicalTrials.gov's terms ask anyone redistributing the data to
credit it, show NLM's processing date and say what was changed: every
report local_corpora.py prints and the tools/name_usage.py row carry the credit and the
date, and the names are kept unchanged.
"""
from __future__ import annotations

import sys
import urllib.parse
from collections.abc import Iterator
from typing import Any

from local_core import Fetched, _get_json


CTGOV_API = "https://clinicaltrials.gov/api/v2"
CTGOV_PAGE = 1000  # the API's largest page
CTGOV_FIELDS = "NCTId,OverallOfficialName,OverallOfficialRole"


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
