"""Offline checks on tools/differential/local_govuk.py, the govuk-people
local corpus.

Every name here is invented: GOV.UK's names are personal data, which the
Open Government Licence does not cover, so not one of them may reach the
repository. What these pin is the fetch's refusals (a total that moves
between pages, a person paged twice, a fetch cut short, a page with no
total, results the filter should have left out past their share) and
what it keeps and counts. The network is a stub answering by URL.
"""
import email.message
import importlib
import json
import time
import urllib.error
import urllib.parse
import urllib.request
from collections.abc import Callable
from pathlib import Path
from typing import Any

import pytest

from ._differential_fixtures import _Response, load_tool, own_cache

local = load_tool("local_corpora")
# The modules the fetch reads its constants from, by name: a patch set on
# a second load by path would reach nothing (test_local_corpora.py).
core = importlib.import_module("local_core")
govuk = importlib.import_module("local_govuk")

_GOVUK = "govuk-people"


@pytest.fixture(autouse=True)
def _own_cache(monkeypatch: pytest.MonkeyPatch, tmp_path_factory: pytest.TempPathFactory) -> Path:
    return own_cache(monkeypatch, tmp_path_factory)


def _person(slug: str, title: object, kind: str = "person") -> dict[str, Any]:
    return {"title": title, "_id": f"/government/people/{slug}",
            "document_type": kind, "index": "govuk"}


#: Two people of one name, a titled name with post-nominals, one padded
#: with spaces, and a peerage written after a comma: 5 people, 4 names.
_PEOPLE = [
    _person("ann-lee", "Ann Lee"), _person("ann-lee-2", "Ann Lee"),
    _person("bo-wu", "The Rt Hon Bo Wu KC"), _person("cy-roe", " Dr Cy Roe CBE "),
    _person("dee-fox", "Dee Fox, 2nd Earl of Nowhere"),
]


def _serve(monkeypatch: pytest.MonkeyPatch, people: list[dict[str, Any]] = _PEOPLE, *,
           page: int = 2, totals: Callable[[int], int] | None = None,
           answer: Callable[[int], object] | None = None) -> list[int]:
    """Answer the search from `people`, `page` to a page, each page stating
    `totals(start)` (len(people) by default); `answer` may replace a
    page's body. Returns the starts asked, in order."""
    monkeypatch.setattr(govuk, "GOVUK_PAGE", page)
    monkeypatch.setattr(time, "sleep", lambda seconds: None)
    asked: list[int] = []

    def urlopen(request: urllib.request.Request, timeout: int) -> _Response:
        query = dict(urllib.parse.parse_qsl(urllib.parse.urlsplit(request.full_url).query))
        start = int(query["start"])
        assert request.full_url == govuk.page_url(start)
        asked.append(start)
        body = answer(start) if answer else None
        if body is None:
            body = {"results": people[start:start + page], "start": start,
                    "total": totals(start) if totals else len(people)}
        return _Response(json.dumps(body).encode())
    monkeypatch.setattr(urllib.request, "urlopen", urlopen)
    return asked


def test_the_page_asks_for_people_by_title_and_their_title_alone() -> None:
    # Unordered, the search paged one person twice and skipped another
    # (2026-10-30), so the order is part of what makes the fetch whole.
    query = urllib.parse.parse_qs(urllib.parse.urlsplit(govuk.page_url(2000)).query)
    assert query == {"filter_format": ["person"], "count": [str(govuk.GOVUK_PAGE)],
                     "start": ["2000"], "order": ["title"], "fields": ["title"]}


def test_a_govuk_fetch_keeps_each_name_once_and_counts_the_people(
        monkeypatch: pytest.MonkeyPatch) -> None:
    asked = _serve(monkeypatch)
    monkeypatch.setattr(time, "gmtime", lambda *seconds: time.struct_time(
        (2026, 10, 30, 9, 0, 5, 4, 303, 0)))
    corpus = local.fetch(_GOVUK)
    assert asked == [0, 2, 4]
    assert corpus.records == [{"name": "Ann Lee"}, {"name": "Dee Fox, 2nd Earl of Nowhere"},
                              {"name": "Dr Cy Roe CBE"}, {"name": "The Rt Hon Bo Wu KC"}]
    assert corpus.meta["data_date"] == "2026-10-30T09:00:05Z"
    assert corpus.meta["detail"] == {"people": 5, "names_held_by_several": 1,
                                     "results_not_person": 0, "results_without_a_title": 0}
    assert corpus.header().endswith("4 names (local corpus govuk-people)")


def test_a_govuk_page_failing_once_is_retried(monkeypatch: pytest.MonkeyPatch) -> None:
    failed: list[int] = []
    headers = email.message.Message()

    def answer(start: int) -> object:
        if start == 2 and not failed:
            failed.append(start)
            raise urllib.error.HTTPError("u", 503, "x", headers, None)
        return None
    _serve(monkeypatch, answer=answer)
    assert len(local.fetch(_GOVUK).records) == 4
    assert failed == [2]


@pytest.mark.parametrize(("people", "totals", "answer", "match"), [
    (_PEOPLE, lambda start: 6 if start else 5, None,
     r"total changed during the fetch \(5 -> 6\)"),
    (_PEOPLE[:2] + _PEOPLE[1:4], None, None, "ann-lee-2 was paged twice"),
    (_PEOPLE, lambda start: 7, None, "paged 5 people of the 7 the search counted"),
    (_PEOPLE, None, lambda start: {"results": [], "total": 5} if start == 2 else None,
     "paged 2 people of the 5"),
    (_PEOPLE, None, lambda start: {"results": _PEOPLE[:2]}, "states no total"),
    (_PEOPLE, None, lambda start: {"results": _PEOPLE[:2], "total": True}, "states no total"),
    (_PEOPLE, None, lambda start: {"total": 5}, "holds no results list"),
    ([{**_PEOPLE[0], "_id": ""}, *_PEOPLE[1:]], None, None, "has no _id"),
], ids=["a total that grew", "a person paged twice", "a fetch cut short",
        "an empty page before the total",
        "a page with no total", "a total that is not a number", "a page with no results",
        "a result with no path"])
def test_a_govuk_fetch_that_is_not_the_whole_set_is_refused(
        monkeypatch: pytest.MonkeyPatch, people: list[dict[str, Any]],
        totals: Callable[[int], int] | None, answer: Callable[[int], object] | None,
        match: str) -> None:
    _serve(monkeypatch, people, totals=totals, answer=answer)
    with pytest.raises(ValueError, match=match):
        local.fetch(_GOVUK)
    assert local.load(_GOVUK) is None


#: Results enough that GOVUK_MAX_BAD's real share (1 in 1,000) is one.
_MANY = 1000


@pytest.mark.parametrize(("bad", "kind", "match"), [
    (lambda i: _person(f"org-{i}", "Acme Office", kind="organisation"), "results_not_person",
     "not of the type 'person'"),
    (lambda i: _person(f"blank-{i}", " "), "results_without_a_title", "have no title"),
    (lambda i: _person(f"none-{i}", None), "results_without_a_title", "have no title"),
], ids=["another document type", "a blank title", "no title"])
@pytest.mark.parametrize("skipped", [1, 2])
def test_a_govuk_fetch_is_refused_past_its_real_share_of_skipped_results(
        monkeypatch: pytest.MonkeyPatch, bad: Callable[[int], dict[str, Any]], kind: str,
        match: str, skipped: int) -> None:
    # One skipped result in 1,000 passes and two are refused, at the
    # shipped GOVUK_MAX_BAD, unpatched; each arm alone.
    people = [bad(i) for i in range(skipped)] + [
        _person(f"p-{i}", f"Bo Wu {i}") for i in range(_MANY - skipped)]
    _serve(monkeypatch, people, page=_MANY)
    if skipped == 1:
        corpus = local.fetch(_GOVUK)
        assert corpus.meta["detail"][kind] == 1
        assert len(corpus.records) == _MANY - 1
    else:
        with pytest.raises(ValueError, match=f"2 of 1,000 results .*{match}"):
            local.fetch(_GOVUK)
