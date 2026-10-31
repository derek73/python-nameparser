"""The govuk-people local corpus: the people pages of GOV.UK.

govuk-people -- the distinct display names of every person GOV.UK has a
page for (ministers, senior civil servants, ambassadors, military chiefs,
past prime ministers), from the site's search API filtered to the person
format. A name is the department's own display form, as written, with
the British title run in front (The Rt Hon, Dr, Professor, Sir, Lord,
Baroness, Dame, military ranks) and post-nominals behind (MP, KC, CBE,
OBE, CMG, KCB, academic degrees): of its 6,021 names, held by 6,125
people, on 2026-10-30, parse() read a title in 1,293 and a suffix in
1,261, one or both in 2,093 (34.8%). A few hold a comma (83: a peerage,
`Name, 2nd Earl Grey`, or post-nominals after one), a job title glued in
front of the name, or two people in one page (`... and ... (job
share)`). So it is a small population for English titles, honorifics
and post-nominals as an office writes them, and blind to case (one
title is a lone post-nominal in capitals), to the family-comma shape and
to names outside UK government. The counts are dated by the day they were
fetched; the data date the fetch stamps, its own start in UTC, was
2026-10-31T01:49:34Z.

GOV.UK's terms (https://www.gov.uk/help/terms-conditions, last updated
3 September 2024, read 2026-10-30): "Most content on GOV.UK is subject
to Crown copyright protection and is published under the Open Government
Licence ( OGL ), which also sets out which content is exempt." The OGL
v3 (https://www.nationalarchives.gov.uk/doc/open-government-licence/version/3/,
read 2026-10-30), under Exemptions: "This licence does not cover:
personal data in the Information". The names are personal data, so they
stay in the cache and are never committed, the caution the name-sources
survey of 2026-10-27 recorded for the UK Parliament's MNIS; the credit
line says so. Only the title field is asked for, and the page path
beside it is read to tell two people of one name apart and dropped.
"""
from __future__ import annotations

import sys
import time
import urllib.parse
from collections import Counter
from typing import Any

from local_core import Fetched, _get_json, _refuse_past


GOVUK_API = "https://www.gov.uk/api/search.json"
GOVUK_PAGE = 1000  # the search API's largest page
#: Paged unordered, the search returned one person twice and another not
#: at all across 6,125 results (2026-10-30); ordered by title it returned
#: each once. Title ties are broken by the index, which kept them in
#: place across pages that day, and a fetch where it did not is refused
#: as a person paged twice.
GOVUK_ORDER = "title"
GOVUK_FORMAT = "person"
#: The share of results a fetch reads past before refusing: results of
#: another document type, which the filter asks the search to leave out,
#: and results with no title (none of 6,125 was either on 2026-10-30).
GOVUK_MAX_BAD = 1 / 1000


def page_url(start: int) -> str:
    """The search's page of people from `start`."""
    return f"{GOVUK_API}?" + urllib.parse.urlencode([
        ("filter_format", GOVUK_FORMAT), ("count", str(GOVUK_PAGE)),
        ("start", str(start)), ("order", GOVUK_ORDER), ("fields", "title")])


def _total(page: dict[str, Any], url: str) -> int:
    total = page.get("total")
    if not isinstance(total, int) or isinstance(total, bool):
        raise ValueError(f"{url} states no total")
    return total


def fetch_govuk() -> Fetched:
    """The distinct display names of every person page, one record per
    name; a record is a NAME, as a ukec-individuals record is, and the
    people behind each are counted into the detail.

    Every page states the search's total, and each must state the first
    page's, so a site that gained or lost a person during the fetch is
    refused. The results paged must number that total, each person (its
    page path) once, so a short page, a fetch cut short or pages that
    shifted under it cannot pass for the whole set. A result of another
    document type or with no title is counted and skipped, and past
    GOVUK_MAX_BAD of either the fetch is refused. The search states no
    date for its data, so the data date is when the fetch began, in UTC."""
    when = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    people: dict[str, str] = {}
    kinds: Counter[str] = Counter()
    count = untitled = 0
    total: int | None = None
    start = 0
    while total is None or start < total:
        url = page_url(start)
        page = _get_json(url)
        stated = _total(page, url)
        if total is None:
            total = stated
            print(f"paging {total:,} people from {GOVUK_API} ...", file=sys.stderr)
        elif stated != total:
            raise ValueError(f"the search's total changed during the fetch "
                             f"({total:,} -> {stated:,}); fetch again")
        results = page.get("results")
        if not isinstance(results, list):
            raise ValueError(f"{url} holds no results list")
        if not results:
            break
        for result in results:
            count += 1
            path = str(result.get("_id", ""))
            if not path:
                raise ValueError(f"a result on {url} has no _id; fetch again")
            if path in people:
                raise ValueError(f"{path} was paged twice: the pages shifted "
                                 f"under the fetch; fetch again")
            kind = str(result.get("document_type", ""))
            kinds[kind] += 1
            people[path] = ""
            if kind != GOVUK_FORMAT:
                continue
            title = result.get("title")
            if isinstance(title, str) and title.strip():
                people[path] = title.strip()
            else:
                untitled += 1
        start += len(results)
    if count != total:
        raise ValueError(f"paged {count:,} people of the {total:,} the search "
                         f"counted; fetch again")
    other = count - kinds[GOVUK_FORMAT]
    _refuse_past([(other, count, GOVUK_MAX_BAD,
                   f"results are not of the type {GOVUK_FORMAT!r}"),
                  (untitled, count, GOVUK_MAX_BAD, "results have no title")],
                 "the search is not the one this reads")
    names = Counter(name for name in people.values() if name)
    return Fetched([{"name": name} for name in sorted(names)], when, {
        "people": count, "names_held_by_several": sum(n > 1 for n in names.values()),
        "results_not_person": other, "results_without_a_title": untitled})
