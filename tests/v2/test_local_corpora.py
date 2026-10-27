"""Offline checks on tools/differential/local_corpora.py and its source
modules (local_core.py and the local_<source>.py modules).

A local corpus is fetched once from a live source and then trusted as
the pin, so what these pin is the fetch's refusals (a fetch straddling
the source's daily refresh, a fetch cut short or paging a study twice,
a fetch with no names), the load's refusal of anything fetch() did not
write, the retries a long run needs, and the views' counting. The
failure that matters is a SMALLER corpus passing for the whole one: its
counts read as real zeros. The network is a stub answering by URL.
"""
import csv
import dataclasses
import email.message
import gzip
import hashlib
import http.client
import importlib
import io
import json
import os
import re
import shutil
import sys
import time
import types
import unicodedata
import urllib.error
import urllib.parse
import urllib.request
import zipfile
from collections.abc import Callable
from pathlib import Path
from typing import Any

import pytest

from ._differential_fixtures import (
    _Response,
    checkout_copy,
    load_tool,
    own_cache,
    plant_corpus,
)

local = load_tool("local_corpora")
snapshot = load_tool("snapshot")
# The modules local_corpora imports, by name: the objects whose globals
# the fetches read, so a patch reaches the code only when it is set on
# the module holding the name (local_core.RETRIES, local_fec.FEC_MAX_BAD).
# A second load by path (load_tool) would be a copy nothing reads.
core, ctgov, fec, tse, tw, ukec, psc, jrc, nepal = (
    importlib.import_module(f"local_{key}")
    for key in ("core", "ctgov", "fec", "tse", "tw", "ukec", "psc", "jrc", "nepal"))

_SOURCE = "ctgov-officials"
_DATE = "2026-10-21T09:00:05"


@pytest.fixture(autouse=True)
def _own_cache(monkeypatch: pytest.MonkeyPatch, tmp_path_factory: pytest.TempPathFactory) -> Path:
    return own_cache(monkeypatch, tmp_path_factory)


def _study(nct: str, *officials: str) -> dict[str, Any]:
    return {"protocolSection": {
        "identificationModule": {"nctId": nct},
        "contactsLocationsModule": {"overallOfficials": [
            {"name": name, "role": "PRINCIPAL_INVESTIGATOR"} for name in officials]}}}


#: Two pages holding three studies, one study without officials.
_PAGES: list[dict[str, Any]] = [
    {"totalCount": 3, "nextPageToken": "t2",
     "studies": [_study("NCT1", "Ann Lee, MD, PhD", "BOB ROE MD"),
                 {"protocolSection": {"identificationModule": {"nctId": "NCT2"}}}]},
    {"studies": [_study("NCT3", "Ann Lee, MD, PhD", "Cy Doe,M.D.")]},
]

Answer = Exception | bytes | None


def _serve(monkeypatch: pytest.MonkeyPatch, tmp_path: Path, *,
           dates: tuple[str, ...] = (_DATE,) * 2,
           pages: list[dict[str, Any]] = _PAGES,
           fail: Callable[[str], Answer] = lambda url: None,
           sleeps: list[float] | None = None) -> list[str]:
    """Answer the API from `pages` by pageToken and /version from
    `dates` in turn. `fail` may answer a URL instead: an exception to
    raise, or a body to return. Returns the URLs fetched; `sleeps`
    collects every sleep asked for."""
    monkeypatch.setenv("NAMEPARSER_TOOLS_CACHE", str(tmp_path))
    monkeypatch.setattr(time, "sleep", (sleeps if sleeps is not None else []).append)
    fetched: list[str] = []
    versions = iter(dates)

    def urlopen(request: urllib.request.Request, timeout: int) -> _Response:
        url = request.full_url
        fetched.append(url)
        answer = fail(url)
        if isinstance(answer, Exception):
            raise answer
        if isinstance(answer, bytes):
            return _Response(answer)
        if url.endswith("/version"):
            body: object = {"apiVersion": "2.0.5", "dataTimestamp": next(versions)}
        else:
            token = urllib.parse.parse_qs(urllib.parse.urlsplit(url).query).get(
                "pageToken", [""])[0]
            body = pages[0] if not token else pages[int(token[1:]) - 1]
        return _Response(json.dumps(body).encode())
    monkeypatch.setattr(urllib.request, "urlopen", urlopen)
    return fetched


def _folder(tmp_path: Path) -> Path:
    return tmp_path / "local" / _SOURCE


def _once(*answers: Answer) -> Callable[[str], Answer]:
    """Answer the second page's requests with `answers` in turn, then
    normally: a transient failure on one request of a long run."""
    queue = list(answers)
    return lambda url: queue.pop(0) if "pageToken" in url and queue else None


def _http_error(code: int, retry_after: str = "") -> urllib.error.HTTPError:
    headers = email.message.Message()
    if retry_after:
        headers["Retry-After"] = retry_after
    return urllib.error.HTTPError("u", code, "x", headers, None)


# -- fetch ---------------------------------------------------------------------

def test_a_fetch_pages_through_and_writes_the_three_files(
        monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    fetched = _serve(monkeypatch, tmp_path)
    corpus = local.fetch(_SOURCE)
    assert [u.rsplit("/", 1)[-1].split("?")[0] for u in fetched] == [
        "version", "studies", "studies", "version"]
    assert [r["name"] for r in corpus.records] == [
        "Ann Lee, MD, PhD", "BOB ROE MD", "Ann Lee, MD, PhD", "Cy Doe,M.D."]
    assert corpus.records[0] == {"name": "Ann Lee, MD, PhD", "study": "NCT1",
                                 "role": "PRINCIPAL_INVESTIGATOR"}
    assert [json.loads(line) for line in
            (_folder(tmp_path) / "corpus.jsonl").read_text().splitlines()] == [
        "Ann Lee, MD, PhD", "BOB ROE MD", "Cy Doe,M.D."]
    meta = json.loads((_folder(tmp_path) / "meta.json").read_text())
    assert (meta["data_date"], meta["records"], meta["names"]) == (_DATE, 4, 3)
    assert meta["detail"] == {"api_version": "2.0.5", "studies": 3,
                              "officials_without_a_name": 0}
    assert local.load(_SOURCE) == corpus
    assert corpus.header().startswith(
        f"ClinicalTrials.gov (NLM) study officials, data as of {_DATE}; 4 officials")


def test_a_fetch_straddling_a_refresh_is_refused(
        monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    _serve(monkeypatch, tmp_path, dates=(_DATE, "2026-10-22T09:00:04"))
    with pytest.raises(ValueError, match="refreshed during the fetch"):
        local.fetch(_SOURCE)
    assert local.load(_SOURCE) is None


def test_a_fetch_cut_short_is_refused(
        monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    # The second page lost: the API stops handing out tokens early.
    first = {**_PAGES[0]}
    del first["nextPageToken"]
    _serve(monkeypatch, tmp_path, pages=[first])
    with pytest.raises(ValueError, match="paged 2 studies of the 3"):
        local.fetch(_SOURCE)
    assert local.load(_SOURCE) is None


@pytest.mark.parametrize("total", [3, 2], ids=["and one missed", "and none missed"])
def test_a_fetch_paging_a_study_twice_is_refused(
        monkeypatch: pytest.MonkeyPatch, tmp_path: Path, total: int) -> None:
    # NCT1 paged twice. With NCT3 missed, a count of the studies paged
    # equals totalCount; with none missed, a count of the DISTINCT studies
    # does (the first fix's check, which let the repeat's officials count
    # twice). Both rows, so neither check can come back alone.
    first = {**_PAGES[0], "totalCount": total}
    _serve(monkeypatch, tmp_path, pages=[
        first, {"studies": [_study("NCT1", "Ann Lee, MD, PhD")]}])
    with pytest.raises(ValueError, match="NCT1 was paged twice"):
        local.fetch(_SOURCE)


@pytest.mark.parametrize("name", ["", " ", None, 3],
                         ids=["empty", "blank", "null", "a number"])
def test_a_fetched_record_whose_name_is_empty_or_not_text_is_refused(
        monkeypatch: pytest.MonkeyPatch, name: object) -> None:
    # The corpus skips a second key's empty value (Source.corpus_keys);
    # an empty "name" is a fetch's own fault, refused rather than skipped.
    monkeypatch.setitem(local.SOURCES, _SOURCE, local.Source(
        "credit", "names", lambda: local.Fetched([{"name": "Ann Lee"}, {"name": name}],
                                                 _DATE, {})))
    with pytest.raises(ValueError, match="a fetched record has no name"):
        local.fetch(_SOURCE)


def test_a_fetch_with_no_names_is_refused(
        monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    # Every official nameless, as a renamed field would leave them: the
    # study count passes, and an empty corpus would read 0 for every word.
    nameless = {"totalCount": 1, "studies": [{"protocolSection": {
        "identificationModule": {"nctId": "NCT1"},
        "contactsLocationsModule": {"overallOfficials": [{"role": "STUDY_CHAIR"}]}}}]}
    _serve(monkeypatch, tmp_path, pages=[nameless])
    with pytest.raises(ValueError, match="found no names"):
        local.fetch(_SOURCE)
    assert local.load(_SOURCE) is None


def test_an_official_without_a_name_is_counted_not_dropped_in_silence(
        monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    page = {"totalCount": 1, "studies": [{"protocolSection": {
        "identificationModule": {"nctId": "NCT1"},
        "contactsLocationsModule": {"overallOfficials": [
            {"role": "STUDY_CHAIR"}, {"name": "Ann Lee, MD"}]}}}]}
    _serve(monkeypatch, tmp_path, pages=[page])
    corpus = local.fetch(_SOURCE)
    assert [r["name"] for r in corpus.records] == ["Ann Lee, MD"]
    assert corpus.meta["detail"]["officials_without_a_name"] == 1


@pytest.mark.parametrize("answer", [
    _http_error(503),
    _http_error(429),
    http.client.RemoteDisconnected("closed"),
    ConnectionResetError("reset"),
    http.client.IncompleteRead(b'{"stud'),
    b'{"studies": [',  # a 200 whose body was cut short
], ids=["503", "429", "disconnected", "reset", "incomplete", "truncated body"])
def test_a_transient_failure_is_retried(
        monkeypatch: pytest.MonkeyPatch, tmp_path: Path, answer: Answer) -> None:
    fetched = _serve(monkeypatch, tmp_path, fail=_once(answer))
    local.fetch(_SOURCE)
    assert sum("pageToken" in u for u in fetched) == 2


def test_a_retry_says_so_on_stderr(
        monkeypatch: pytest.MonkeyPatch, tmp_path: Path,
        capsys: pytest.CaptureFixture[str]) -> None:
    _serve(monkeypatch, tmp_path, fail=_once(_http_error(503)))
    local.fetch(_SOURCE)
    assert "retrying in 1s after HTTPError" in capsys.readouterr().err


def test_an_error_that_is_not_the_network_is_not_retried(
        monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    # A bug, not a dropped connection: four attempts would hide it for
    # seconds and then raise it anyway.
    fetched = _serve(monkeypatch, tmp_path, fail=lambda url: ValueError("a bug")
                     if "studies" in url else None)
    with pytest.raises(ValueError, match="a bug"):
        local.fetch(_SOURCE)
    assert sum("studies" in u for u in fetched) == 1


def test_a_rate_limit_waits_as_long_as_the_server_asks(
        monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    sleeps: list[float] = []
    _serve(monkeypatch, tmp_path, fail=_once(_http_error(429, "30")), sleeps=sleeps)
    local.fetch(_SOURCE)
    assert 30 in sleeps


def test_a_client_error_is_raised_at_once(
        monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    fetched = _serve(monkeypatch, tmp_path, fail=lambda url: _http_error(400)
                     if "studies" in url else None)
    with pytest.raises(urllib.error.HTTPError) as raised:
        local.fetch(_SOURCE)
    raised.value.close()
    assert sum("studies" in u for u in fetched) == 1


def test_the_last_attempt_raises_its_own_error(
        monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    fetched = _serve(monkeypatch, tmp_path, fail=lambda url: _http_error(503)
                     if "studies" in url else None)
    with pytest.raises(urllib.error.HTTPError) as raised:
        local.fetch(_SOURCE)
    assert raised.value.code == 503
    raised.value.close()
    assert sum("studies" in u for u in fetched) == core.RETRIES


def test_a_source_detail_cannot_replace_what_load_checks(
        monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setenv("NAMEPARSER_TOOLS_CACHE", str(tmp_path))
    fetched = local.Fetched([{"name": "Ann Lee, MD"}], _DATE,
                            {"records": 99, "sha256": "x", "version": 0})
    monkeypatch.setitem(local.SOURCES, _SOURCE, local.Source(
        "credit", "officials", lambda: fetched))
    local.fetch(_SOURCE)
    loaded = local.load(_SOURCE)
    assert loaded is not None and loaded.meta["records"] == 1


def test_looking_for_a_corpus_creates_no_folder(
        monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    # name_usage.py looks on every run; a user who never fetched one
    # should not find empty folders in the cache.
    monkeypatch.setenv("NAMEPARSER_TOOLS_CACHE", str(tmp_path))
    assert local.load(_SOURCE) is None
    assert not (tmp_path / "local").exists()


def test_an_unknown_source_names_the_known_ones() -> None:
    with pytest.raises(ValueError, match=_SOURCE):
        local.directory("nppes")
    with pytest.raises(ValueError, match=_SOURCE):
        local.fetch("nppes")


# -- FEC individual contributions ------------------------------------------------

_FEC = "fec-individuals"
_FEC_DATE = (2026, 10, 18, 16, 17, 0)


def _fec_row(entity: str, name: str, columns: int = 21) -> str:
    cols = ["C00000001", "N", "Q3", "P2026", "1", "15", entity, name,
            "BRAINTREE", "MA", "02184", "SELF", "HOMEMAKER", "10132026",
            "100", "", "SA1", "1", "", "", "1"]
    return "|".join(cols[:columns])


#: Two people, one giving twice and once with the name padded, a
#: committee, a person with no name, a line cut short and a line in
#: Latin-1: 7 lines.
_FEC_LINES = [
    _fec_row("IND", "LEE, ANN"), _fec_row("IND", "ROE JR, BOB MR"),
    _fec_row("IND", " LEE, ANN "), _fec_row("PAC", "ACME PAC"),
    _fec_row("IND", " "), _fec_row("IND", "WU, BO", columns=20),
]
_FEC_LATIN1 = _fec_row("IND", "PE\xd1A, JOS\xc9").encode("latin-1")


def _fec_body(lines: list[str], *extra: bytes) -> bytes:
    return b"".join([*(line.encode() + b"\n" for line in lines),
                     *(line + b"\n" for line in extra)])


def _fec_zip(path: Path, body: bytes | None = None,
             date: tuple[int, int, int, int, int, int] = _FEC_DATE) -> bytes:
    """A cycle's zip at `path`, holding the whole file and a by_date
    slice holding only its first line, stamped alike: a fetch reading
    the slice instead would lose names; its bytes."""
    if body is None:
        body = _fec_body(_FEC_LINES, _FEC_LATIN1)
    path.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(path, "w") as archive:
        archive.writestr(zipfile.ZipInfo("itcont.txt", date), body)
        archive.writestr(zipfile.ZipInfo("by_date/itcont_2026_slice.txt", date),
                         body.split(b"\n", 1)[0] + b"\n")
    return path.read_bytes()


class _Download:
    """A streamed download: read(n) hands out `body` in pieces, the
    headers stating `length` (none when it is None), and raises `fail`
    once the first piece is out."""

    def __init__(self, body: bytes, length: int | None,
                 fail: Exception | None = None) -> None:
        self.body, self.fail = body, fail
        self.headers = {} if length is None else {"Content-Length": str(length)}
        self.sent = False

    def __enter__(self) -> "_Download":
        return self

    def __exit__(self, *exc: object) -> None:
        return None

    def read(self, n: int) -> bytes:
        if self.sent and self.fail:
            raise self.fail
        chunk, self.body = self.body[:n], self.body[n:]
        self.sent = True
        return chunk


def _fec_cache(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> Path:
    monkeypatch.setenv("NAMEPARSER_TOOLS_CACHE", str(tmp_path))
    monkeypatch.setattr(core, "CHUNK", 64)  # several reads, not one
    return tmp_path / "local" / _FEC / fec.FEC_ZIP


def _serve_fec(monkeypatch: pytest.MonkeyPatch, *responses: _Download) -> list[str]:
    """Answer each download with the next of `responses`; the URLs asked."""
    queue, asked = list(responses), []

    def urlopen(request: urllib.request.Request, timeout: int) -> _Download:
        asked.append(request.full_url)
        if not queue:
            pytest.fail(f"an unexpected download of {request.full_url}")
        return queue.pop(0)
    monkeypatch.setattr(urllib.request, "urlopen", urlopen)
    return asked


def test_a_fec_fetch_keeps_each_person_s_name_once_and_counts_the_rest(
        monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    _fec_zip(_fec_cache(monkeypatch, tmp_path))
    _serve_fec(monkeypatch)  # a cached zip is not downloaded again
    monkeypatch.setattr(fec, "FEC_MAX_BAD", 1)  # a fixture of 7 lines
    corpus = local.fetch(_FEC)
    assert corpus.records == [{"name": "LEE, ANN"}, {"name": "PEÑA, JOSÉ"},
                              {"name": "ROE JR, BOB MR"}]
    assert corpus.meta["data_date"] == "2026-10-18T16:17:00"
    assert corpus.meta["detail"] == {
        "cycle": fec.FEC_CYCLE, "file": f"{fec.FEC_ZIP}/itcont.txt",
        "rows": 7, "individual_contributions": 5, "rows_from_other_entities": 1,
        "individuals_without_a_name": 1, "lines_not_21_columns": 1,
        "lines_not_utf8": 1}
    assert corpus.header().endswith("3 names (local corpus fec-individuals)")


@pytest.mark.parametrize(("lines", "match"), [
    ([_fec_row("IND", "LEE, ANN") + "|X"] * 2 + [_fec_row("IND", "WU, BO")],
     "2 of 3 lines .* are not 21 columns"),
    # The 22nd column dropped and one inserted before NAME: 21 columns,
    # entity in place, and NAME now holding the city.
    (["|".join(_fec_row("IND", "x").split("|")[:7] + ["BRAINTREE", "LEE, ANN"]
               + _fec_row("IND", "x").split("|")[8:20])],
     "0 of 1 names hold a comma"),
], ids=["lines not 21 columns", "a column moved under NAME"])
def test_a_fec_file_whose_layout_has_changed_is_refused(
        monkeypatch: pytest.MonkeyPatch, tmp_path: Path,
        lines: list[str], match: str) -> None:
    _fec_zip(_fec_cache(monkeypatch, tmp_path), _fec_body(lines))
    with pytest.raises(ValueError, match=match):
        local.fetch(_FEC)
    assert local.load(_FEC) is None


def test_a_fec_file_mostly_not_utf8_is_refused(
        monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    _fec_zip(_fec_cache(monkeypatch, tmp_path),
             _fec_body([_fec_row("IND", "LEE, ANN")], _FEC_LATIN1))
    with pytest.raises(ValueError, match="1 of 2 lines .* are not UTF-8"):
        local.fetch(_FEC)


@pytest.mark.parametrize("damage", ["not a zip", "no itcont.txt"])
def test_a_fec_zip_that_cannot_be_read_names_the_way_out(
        monkeypatch: pytest.MonkeyPatch, tmp_path: Path, damage: str) -> None:
    path = _fec_cache(monkeypatch, tmp_path)
    path.parent.mkdir(parents=True)
    if damage == "not a zip":
        path.write_bytes(_fec_zip(tmp_path / "whole.zip")[:-40])
        match = "fetch fec-individuals --refresh"
    else:
        with zipfile.ZipFile(path, "w") as archive:
            archive.writestr("itcont_renamed.txt", b"")
        match = "holds no itcont.txt"
    with pytest.raises(ValueError, match=match):
        local.fetch(_FEC)


def test_a_fec_fetch_downloads_the_zip_when_it_is_missing(
        monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    path = _fec_cache(monkeypatch, tmp_path)
    monkeypatch.setattr(fec, "FEC_MAX_BAD", 1)
    body = _fec_zip(tmp_path / "elsewhere.zip")
    stale = path.with_name("indiv24.zip")
    stale.parent.mkdir(parents=True)
    stale.write_bytes(b"the last cycle's zip")
    assert _serve_fec(monkeypatch, _Download(body, len(body))) == []
    assert len(local.fetch(_FEC).records) == 3
    assert path.read_bytes() == body
    assert not stale.exists()


@pytest.mark.parametrize("stated", [10**6, -1, None],
                         ids=["cut short", "longer than stated", "no length"])
def test_a_fec_download_that_does_not_match_its_length_is_refused(
        monkeypatch: pytest.MonkeyPatch, tmp_path: Path, stated: int | None) -> None:
    path = _fec_cache(monkeypatch, tmp_path)
    body = _fec_zip(tmp_path / "elsewhere.zip")
    length = None if stated is None else len(body) - 1 if stated < 0 else stated
    _serve_fec(monkeypatch, _Download(body, length))
    with pytest.raises(ValueError, match="fetch again"):
        local.fetch(_FEC)
    assert not path.exists() and not path.with_name(path.name + ".part").exists()
    assert local.load(_FEC) is None


def test_a_fec_download_cut_off_mid_stream_leaves_no_part_file(
        monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    path = _fec_cache(monkeypatch, tmp_path)
    body = _fec_zip(tmp_path / "elsewhere.zip")
    _serve_fec(monkeypatch, _Download(body, len(body),
                                      http.client.IncompleteRead(b"")))
    with pytest.raises(http.client.IncompleteRead):
        local.fetch(_FEC)
    assert not path.exists() and not path.with_name(path.name + ".part").exists()


def test_a_fec_refresh_rebuilds_the_corpus_from_a_new_download(
        monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    # Re-reading the cached zip would reproduce the same file under a
    # refresh, with the same names and data date.
    path = _fec_cache(monkeypatch, tmp_path)
    monkeypatch.setattr(fec, "FEC_MAX_BAD", 1)
    _fec_zip(path)
    newer = _fec_zip(tmp_path / "newer.zip", _fec_body([_fec_row("IND", "WU, BO")]),
                     date=(2026, 10, 25, 9, 0, 0))
    asked = _serve_fec(monkeypatch, _Download(newer, len(newer)))
    assert local.main(["fetch", _FEC]) == 0
    assert asked == []
    assert local.main(["fetch", _FEC, "--refresh"]) == 0
    assert asked == [fec.FEC_URL]
    corpus = local.load(_FEC)
    assert corpus is not None and corpus.records == [{"name": "WU, BO"}]
    assert corpus.meta["data_date"] == "2026-10-25T09:00:00"


def test_a_failed_fec_refresh_keeps_the_zip_and_the_corpus_it_had(
        monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    path = _fec_cache(monkeypatch, tmp_path)
    monkeypatch.setattr(fec, "FEC_MAX_BAD", 1)
    cached = _fec_zip(path)
    _serve_fec(monkeypatch, _Download(cached[:100], len(cached)))
    before = local.fetch(_FEC)
    with pytest.raises(ValueError, match="fetch again"):
        local.main(["fetch", _FEC, "--refresh"])
    assert path.read_bytes() == cached
    assert not path.with_name(path.name + ".part").exists()
    assert local.load(_FEC) == before


def test_a_fec_corpus_of_another_cycle_is_refused_on_load(
        monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    # Bumping FEC_CYCLE would otherwise label the cached cycle's names
    # with the new cycle's credit.
    _fec_zip(_fec_cache(monkeypatch, tmp_path))
    monkeypatch.setattr(fec, "FEC_MAX_BAD", 1)
    local.fetch(_FEC)
    monkeypatch.setattr(fec, "FEC_CYCLE", "2028")
    with pytest.raises(ValueError, match=f"holds the 2026 cycle.*reads the 2028 cycle"
                                          f".*fetch {_FEC} --refresh"):
        local.load(_FEC)


# -- TSE campaign donations ------------------------------------------------------

_TSE = "tse-donors"
#: An invented CPF, which must reach no file the fetch writes, whether
#: in its own column or typed into a name.
_CPF = "52998224725"
_TSE_HEADER = (["DT_GERACAO", "AA_ELEICAO", "DS_ORIGEM_RECEITA", "NR_CPF_CNPJ_DOADOR",
                "NM_DOADOR", "NM_DOADOR_RFB"] + [f"COL_{i}" for i in range(54)])
_PARTY = "Recursos de partido político"


def _tse_row(origin: str, name: str, registry: str, columns: int = 60) -> list[str]:
    row = ["22/10/2026", "2022", origin, _CPF, name, registry] + ["x"] * 54
    return row[:columns]


def _tse_csv(rows: list[list[str]], header: list[str] = _TSE_HEADER,
             encoding: str = "cp1252") -> bytes:
    out = io.StringIO()
    writer = csv.writer(out, delimiter=";", quoting=csv.QUOTE_ALL, lineterminator="\r\n")
    writer.writerows([header, *rows])
    return out.getvalue().encode(encoding)


_PF = tse.TSE_INDIVIDUALS
#: 2022: one donor twice (once padded), a donor whose filed name is
#: not the registry's, a person with no name, a party, a row cut short
#: and a filed name holding cp1252's right quote. 2024: the first donor
#: again, the same filed name beside another registry name, a donor the
#: registry has no name for, a blank name, a registry name holding the
#: right quote, and three numbers typed into a name: the CPF bare, the
#: CPF formatted, and five digits in a registry name.
_TSE_ROWS = {
    "2022": [_tse_row(_PF, "ANA SOUZA", "ANA SOUZA"),
             _tse_row(_PF, " ANA SOUZA ", "ANA SOUZA"),
             _tse_row(_PF, "JOSE DA SILVA JR", "JOSÉ DA SILVA JUNIOR"),
             _tse_row(_PF, "#NULO", "#NULO"),
             _tse_row(_PARTY, "PARTIDO DO EXEMPLO", "PARTIDO DO EXEMPLO"),
             _tse_row(_PF, "RUI MOTA", "RUI MOTA", columns=59),
             _tse_row(_PF, "LIA D’AVILA", "LIA D AVILA")],
    "2024": [_tse_row(_PF, "ANA SOUZA", "ANA SOUZA"),
             _tse_row(_PF, "ANA SOUZA", "ANA MARIA SOUZA"),
             _tse_row(_PF, "BIA COSTA", "#NULO"),
             _tse_row(_PF, "   ", "EVA LOPES"),
             _tse_row(_PF, "RUI DELIA", "RUI D’ELIA"),
             _tse_row(_PF, f"DOADOR {_CPF}", "DOADOR"),
             _tse_row(_PF, "ANA 529.982.247-25", "ANA"),
             _tse_row(_PF, "CAIO REIS", "CAIO REIS 12345")],
}
_TSE_RECORDS = [
    {"name": "ANA SOUZA", "registry": "ANA MARIA SOUZA"},
    {"name": "ANA SOUZA", "registry": "ANA SOUZA"},
    {"name": "BIA COSTA", "registry": ""},
    {"name": "JOSE DA SILVA JR", "registry": "JOSÉ DA SILVA JUNIOR"},
    {"name": "LIA D’AVILA", "registry": "LIA D AVILA"},
    {"name": "RUI DELIA", "registry": "RUI D’ELIA"}]
_TSE_STAMPS = {"2022": (2026, 10, 18, 18, 10, 28), "2024": (2026, 10, 22, 2, 28, 38)}


#: The bytes of a member no fetch should read: a fetch reading the
#: whole zip would ask for them.
_TSE_FILLER = bytes(range(256)) * 200


def _tse_zip(year: str, member: bytes | None = None, name: str | None = None,
             stored: bool = False) -> bytes:
    """A candidates' zip holding the national member, deflated as the
    TSE's are (stored where a test needs its bytes to stay many), a state
    member whose one donor the national member lacks (a fetch reading it
    would gain a name), and a member of _TSE_FILLER."""
    member = _tse_csv(_TSE_ROWS[year]) if member is None else member
    out = io.BytesIO()
    with zipfile.ZipFile(out, "w") as archive:
        archive.writestr(zipfile.ZipInfo("leiame.pdf", _TSE_STAMPS[year]), _TSE_FILLER)
        archive.writestr(zipfile.ZipInfo(f"receitas_candidatos_{year}_BA.csv",
                                         _TSE_STAMPS[year]),
                         _tse_csv([_tse_row(_PF, "SO NO ESTADO", "")]),
                         compress_type=zipfile.ZIP_DEFLATED)
        archive.writestr(zipfile.ZipInfo(name or f"receitas_candidatos_{year}_BRASIL.csv",
                                         _TSE_STAMPS[year]), member,
                         compress_type=zipfile.ZIP_STORED if stored
                         else zipfile.ZIP_DEFLATED)
    return out.getvalue()


def _url(year: str) -> str:
    return str(tse.TSE_URL.format(year=year))


class _Answer:
    def __init__(self, status: int, body: bytes, headers: dict[str, str]) -> None:
        self.status, self.body, self.headers = status, body, headers

    def __enter__(self) -> "_Answer":
        return self

    def __exit__(self, *exc: object) -> None:
        return None

    def read(self, n: int = -1) -> bytes:
        return self.body if n < 0 else self.body[:n]


class _Cdn:
    """The CDN: HEAD states each zip's length, ETag (each zip its own)
    and byte ranges, and a Range request with a matching If-Range is
    answered in part with its Content-Range, any other whole, as a
    server answers for a file replaced since the HEAD."""

    def __init__(self, zips: dict[str, bytes]) -> None:
        self.zips = {_url(y): body for y, body in zips.items()}
        self.etag = '"v1"'
        self.head: dict[str, str] | None = None  # headers replacing HEAD's
        self.head_etag: str | None = None  # the ETag HEAD states, "" for none
        self.last_modified = ""  # the Last-Modified HEAD states, if any
        self.accept_ranges: str | None = "bytes"  # None states none
        self.head_failures: list[Exception] = []  # raised by the next HEADs
        self.failures: list[Exception] = []  # raised by the next range requests
        self.short = 0  # range answers to cut a byte short
        self.long = False  # range answers to send a byte past the range
        self.content_range: str | None = None  # replacing the true one; "" for none
        self.replace_after: int | None = None  # range requests before a new ETag
        self.replace_year = ""  # the one zip replaced, or any
        self.replaced: set[str] = set()
        self.ranges = self.served = 0

    def tag(self, url: str) -> str:
        """`url`'s validator: the zip's own ETag, or the shared date."""
        if not self.etag.startswith('"'):
            return self.etag
        return f'"{url[-8:-4]}-{self.etag[1:]}' + ("-new" if url in self.replaced else "")

    def urlopen(self, request: urllib.request.Request, timeout: int) -> _Answer:
        url = request.full_url
        body = self.zips[url]
        if request.get_method() == "HEAD":
            if self.head_failures:
                raise self.head_failures.pop(0)
            if self.head is not None:
                return _Answer(200, b"", self.head)
            etag = self.tag(url) if self.head_etag is None else self.head_etag
            return _Answer(200, b"", {"Content-Length": str(len(body)),
                                      **({"Accept-Ranges": self.accept_ranges}
                                         if self.accept_ranges else {}),
                                      **({"ETag": etag} if etag else {}),
                                      **({"Last-Modified": self.last_modified}
                                         if self.last_modified else {})})
        self.ranges += 1
        if (self.replace_after is not None and self.ranges > self.replace_after
                and self.replace_year in url):
            self.replaced.add(url)
        if self.failures:
            raise self.failures.pop(0)
        if request.get_header("If-range") != self.tag(url):
            return _Answer(200, body, {})
        start, end = map(int, str(request.get_header("Range"))[len("bytes="):].split("-"))
        part = body[start:end + 1]
        if self.short:
            self.short -= 1
            part = part[:-1]
        if self.long:
            part += b"!"
        self.served += len(part)
        stated = (f"bytes {start}-{end}/{len(body)}" if self.content_range is None
                  else self.content_range)
        return _Answer(206, part, {"Content-Range": stated} if stated else {})


@pytest.fixture
def cdn(monkeypatch: pytest.MonkeyPatch) -> _Cdn:
    served = _Cdn({year: _tse_zip(year) for year in tse.TSE_ELECTIONS})
    monkeypatch.setattr(urllib.request, "urlopen", served.urlopen)
    monkeypatch.setattr(tse, "TSE_BLOCK", 256)  # many ranges, not one
    # A fixture of 15 rows holds more of each kind of damage than the
    # real file may: the tests of each limit set it back.
    monkeypatch.setattr(tse, "TSE_MAX_BAD", 1)
    monkeypatch.setattr(tse, "TSE_MAX_MISSING", 1)
    monkeypatch.setattr(tse, "TSE_MAX_NUMBERED", 1)
    monkeypatch.setattr(time, "sleep", lambda s: None)
    return served


def _serve_member(cdn: _Cdn, year: str, member: bytes) -> None:
    cdn.zips[_url(year)] = _tse_zip(year, member)


def test_a_tse_fetch_keeps_each_donor_s_pair_once_and_counts_the_rest(cdn: _Cdn) -> None:
    corpus = local.fetch(_TSE)
    assert corpus.records == _TSE_RECORDS
    assert corpus.meta["names"] == 5  # corpus.jsonl holds each filed name once
    assert corpus.meta["data_date"] == "2026-10-18T18:10:28 (2022), 2026-10-22T02:28:38 (2024)"
    assert corpus.meta["detail"] == {
        "elections": "2022 2024",
        "2022_rows": 7, "2022_rows_from_individuals": 5, "2022_records": 3,
        "2022_new_records": 3,
        "2022_rows_not_60_columns": 1, "2022_lines_folded_into_a_field": 0,
        "2022_individuals_without_a_name": 1,
        "2022_individuals_without_a_registry_name": 0,
        "2022_individuals_whose_name_holds_a_number": 0, "2022_rows_read_as_cp1252": 1,
        "2024_rows": 8, "2024_rows_from_individuals": 8, "2024_records": 4,
        "2024_new_records": 3,
        "2024_rows_not_60_columns": 0, "2024_lines_folded_into_a_field": 0,
        "2024_individuals_without_a_name": 1,
        "2024_individuals_without_a_registry_name": 1,
        "2024_individuals_whose_name_holds_a_number": 3, "2024_rows_read_as_cp1252": 1,
        "records_whose_name_differs_from_the_registry": 5}
    assert corpus.header().startswith("TSE (Tribunal Superior Eleitoral)")
    assert corpus.header().endswith("6 name pairs (local corpus tse-donors)")
    assert cdn.ranges > 4  # read in ranges, not in one answer
    assert cdn.served < len(_TSE_FILLER)  # and only the ranges the member needs


def test_a_tse_fetch_writes_no_column_but_the_two_names(cdn: _Cdn) -> None:
    local.fetch(_TSE)
    folder = local.directory(_TSE)
    for path in folder.iterdir():
        text = path.read_text(encoding="utf-8")
        for leak in (_CPF, "529.982.247-25", "12345", "COL_", "x\""):
            assert leak not in text, (path.name, leak)
    corpus = local.load(_TSE)
    assert corpus is not None
    assert {key for r in corpus.records for key in r} == {"name", "registry"}


def test_a_tse_file_s_columns_are_found_by_name(cdn: _Cdn) -> None:
    # The registry before the name and the origin last: read by position,
    # the names would swap and every category would be unknown.
    order = [0, 1, 5, 4] + list(range(6, 60)) + [3, 2]
    for year in tse.TSE_ELECTIONS:
        _serve_member(cdn, year, _tse_csv([[row[i] for i in order] if len(row) == 60
                                           else row for row in _TSE_ROWS[year]],
                                          [_TSE_HEADER[i] for i in order]))
    assert local.fetch(_TSE).records == _TSE_RECORDS


@pytest.mark.parametrize(("header", "match"), [
    (_TSE_HEADER[:-1], "header is 59 columns, not 60"),
    ([c if c != "NM_DOADOR_RFB" else "NM_DOADOR_RECEITA" for c in _TSE_HEADER],
     "lacks NM_DOADOR_RFB"),
], ids=["a column dropped", "a column renamed"])
def test_a_tse_file_whose_header_has_changed_is_refused(
        cdn: _Cdn, header: list[str], match: str) -> None:
    _serve_member(cdn, "2024", _tse_csv(_TSE_ROWS["2024"], header))
    with pytest.raises(ValueError, match=match):
        local.fetch(_TSE)
    assert local.load(_TSE) is None


@pytest.mark.parametrize(("member", "match"), [
    # The individuals' category renamed: read as one more category, the
    # election would have no individual donors.
    (_tse_csv([_tse_row("Recursos de Pessoas Físicas", "ANA SOUZA", "ANA SOUZA")] * 10),
     "1 DS_ORIGEM_RECEITA value.*'Recursos de Pessoas Físicas'"),
    # The file written in UTF-8: físicas no longer spells the category.
    (_tse_csv([_tse_row(_PF, "ANA SOUZA", "ANA SOUZA")] * 10, encoding="utf-8"),
     "1 DS_ORIGEM_RECEITA value.*'Recursos de pessoas fÃ"),
], ids=["a category renamed", "the file in UTF-8"])
def test_a_tse_file_whose_categories_have_changed_is_refused(
        cdn: _Cdn, member: bytes, match: str) -> None:
    _serve_member(cdn, "2022", member)
    with pytest.raises(ValueError, match=match):
        local.fetch(_TSE)


def test_a_tse_category_held_by_a_few_rows_is_not_quoted(cdn: _Cdn) -> None:
    # A row misread into 60 columns can put a CPF where the origin was.
    _serve_member(cdn, "2022", _tse_csv(
        [_tse_row(_CPF, "ANA SOUZA", "ANA SOUZA")] * 9 + [_tse_row(_PF, "ANA", "ANA")]))
    with pytest.raises(ValueError, match="none held by enough rows") as raised:
        local.fetch(_TSE)
    assert _CPF not in str(raised.value)


@pytest.mark.parametrize(("rows", "match"), [
    ([], "0 of 0 rows .* are from individuals"),
    ([_tse_row("#NULO", "ANA SOUZA", "ANA SOUZA")] * 9 + [_tse_row(_PF, "ANA", "ANA")],
     "1 of 10 rows .* are from individuals"),
], ids=["the header alone", "the individuals moved to another category"])
def test_a_tse_election_with_too_few_individuals_is_refused(
        cdn: _Cdn, monkeypatch: pytest.MonkeyPatch,
        rows: list[list[str]], match: str) -> None:
    monkeypatch.setattr(tse, "TSE_MIN_INDIVIDUALS", 0.11)  # 1 of 10 falls short
    _serve_member(cdn, "2024", _tse_csv(rows))
    with pytest.raises(ValueError, match=match):
        local.fetch(_TSE)
    assert local.load(_TSE) is None


@pytest.mark.parametrize(("name", "registry", "match"), [
    ("#NULO", "ANA SOUZA", "carry no name"),
    ("ANA SOUZA", "", "carry no registry name"),
], ids=["names masked", "registry names masked"])
def test_a_tse_election_whose_names_are_masked_is_refused(
        cdn: _Cdn, monkeypatch: pytest.MonkeyPatch,
        name: str, registry: str, match: str) -> None:
    monkeypatch.setattr(tse, "TSE_MAX_MISSING", 1 / 100)
    _serve_member(cdn, "2022", _tse_csv([_tse_row(_PF, "ANA SOUZA", "ANA SOUZA")]))
    _serve_member(cdn, "2024", _tse_csv([_tse_row(_PF, name, registry)]))
    with pytest.raises(ValueError, match=f"1 of 1 individuals' rows .* {match}"):
        local.fetch(_TSE)


@pytest.mark.parametrize(("member", "match"), [
    (_tse_csv(_TSE_ROWS["2022"]), "1 rows not 60 columns in 7 rows"),
    (_tse_csv([_tse_row(_PF, "ANA", "ANA") + ["x"], _tse_row(_PF, "BO", "BO")]),
     "1 rows not 60 columns in 2 rows"),
    # A field holding a line break: two lines, one row.
    (_tse_csv([_tse_row(_PF, "ANA\r\nSOUZA", "ANA SOUZA"), _tse_row(_PF, "BO", "BO")]),
     "1 lines folded into another row's field in 2 rows"),
], ids=["a row short", "a row long", "a line folded into a field"])
def test_a_tse_file_with_too_many_malformed_lines_is_refused(
        cdn: _Cdn, monkeypatch: pytest.MonkeyPatch, member: bytes, match: str) -> None:
    monkeypatch.setattr(tse, "TSE_MAX_BAD", 1 / 10)
    _serve_member(cdn, "2022", member)
    with pytest.raises(ValueError, match=match):
        local.fetch(_TSE)


def test_a_tse_zip_without_the_national_member_is_refused(cdn: _Cdn) -> None:
    cdn.zips[_url("2022")] = _tse_zip("2022", name="receitas_candidatos_2022_BRASIL_v2.csv")
    with pytest.raises(ValueError, match="holds no receitas_candidatos_2022_BRASIL.csv"):
        local.fetch(_TSE)


def test_a_tse_answer_that_is_not_a_zip_names_the_way_out(cdn: _Cdn) -> None:
    cdn.zips[_url("2022")] = b"<html>" + b"x" * 494  # a CDN's error page
    with pytest.raises(ValueError, match="2022.zip is not a readable zip.*fetch again"):
        local.fetch(_TSE)


@pytest.mark.parametrize(("year", "after"), [("2022", 0), ("2022", 6), ("2024", 0)],
                         ids=["at the start", "inside the member", "the second zip"])
def test_a_tse_zip_replaced_during_the_read_is_refused(
        cdn: _Cdn, monkeypatch: pytest.MonkeyPatch, year: str, after: int) -> None:
    # The member stored and long, so that the seventh range falls inside
    # it, and its 20 repeats not refused for their few distinct names.
    monkeypatch.setattr(tse, "TSE_MIN_DISTINCT", 0)
    cdn.zips[_url("2022")] = _tse_zip("2022", _tse_csv(_TSE_ROWS["2022"] * 20),
                                      stored=True)
    cdn.replace_year, cdn.replace_after = year, after
    with pytest.raises(ValueError, match=f"{year}.zip answered a range request whole "
                                         r"\(HTTP 200\)"):
        local.fetch(_TSE)
    assert local.load(_TSE) is None


@pytest.mark.parametrize(("content_range", "long"), [
    ("bytes 0-9/10", False), ("", False), (None, True)],
    ids=["another range", "no Content-Range", "a byte too many"])
def test_a_tse_part_that_is_not_the_range_asked_for_is_refused(
        cdn: _Cdn, content_range: str | None, long: bool) -> None:
    cdn.content_range, cdn.long = content_range, long
    with pytest.raises(ValueError, match=r"answered bytes \d+-\d+ of .*fetch again"):
        local.fetch(_TSE)
    assert cdn.ranges == 1  # refused, not retried


@pytest.mark.parametrize("head", [
    {"ETag": '"v1"', "Accept-Ranges": "bytes"},
    {"Content-Length": "100", "Accept-Ranges": "bytes"},
    {"Content-Length": "100", "ETag": 'W/"v1"'},
    {"Content-Length": "100", "ETag": '"v1"', "Accept-Ranges": "none"},
], ids=["no length", "no validator", "a weak ETag alone", "ranges refused"])
def test_a_tse_zip_that_cannot_be_read_in_ranges_safely_is_refused(
        cdn: _Cdn, head: dict[str, str]) -> None:
    cdn.head = head
    with pytest.raises(ValueError, match="states no length, no strong ETag"):
        local.fetch(_TSE)


@pytest.mark.parametrize("etag", ["", 'W/"v1"'], ids=["no ETag", "a weak ETag"])
def test_a_tse_zip_with_a_last_modified_date_is_read_by_it(cdn: _Cdn, etag: str) -> None:
    cdn.etag = cdn.last_modified = "Tue, 18 Oct 2026 18:25:05 GMT"
    cdn.head_etag = etag
    assert local.fetch(_TSE).records == _TSE_RECORDS


def test_a_tse_strong_etag_is_preferred_to_the_last_modified_date(cdn: _Cdn) -> None:
    # The fake honours the ETag alone: If-Range sent with the date would
    # be answered whole.
    cdn.last_modified = "Tue, 18 Oct 2026 18:25:05 GMT"
    assert local.fetch(_TSE).records == _TSE_RECORDS


def test_a_tse_request_cut_short_or_dropped_is_retried(
        cdn: _Cdn, monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture[str]) -> None:
    monkeypatch.setattr(core, "RETRIES", 5)  # four failures on one range
    cdn.short = 1
    cdn.head_failures = [urllib.error.URLError("reset")]
    cdn.failures = [urllib.error.URLError("reset"), _http_error(503), _http_error(429)]
    assert local.fetch(_TSE).records == _TSE_RECORDS
    assert capsys.readouterr().err.count("retrying in") == 5


def test_a_tse_range_refused_by_the_server_is_raised_at_once(cdn: _Cdn) -> None:
    cdn.failures = [_http_error(403)]
    with pytest.raises(urllib.error.HTTPError) as raised:
        local.fetch(_TSE)
    raised.value.close()
    assert cdn.ranges == 1


def _letters(i: int) -> str:
    """An invented name word for row `i`, all letters: AAA, AAB, ..."""
    return "".join(chr(65 + i // 26 ** k % 26) for k in (2, 1, 0))


def _tse_names(n: int) -> list[list[str]]:
    """`n` donors, each a distinct invented name filed as registered."""
    return [_tse_row(_PF, f"ANA {_letters(i)}", f"ANA {_letters(i)}") for i in range(n)]


@pytest.mark.parametrize("column", ["name", "registry"])
@pytest.mark.parametrize("mask", ["#NE", "***", "-4", "#NULO#", _CPF])
def test_a_tse_column_masked_with_no_letter_is_refused(
        cdn: _Cdn, monkeypatch: pytest.MonkeyPatch, column: str, mask: str) -> None:
    monkeypatch.setattr(tse, "TSE_MAX_MISSING", 1 / 100)
    _serve_member(cdn, "2022", _tse_csv(_tse_names(4)))  # 2022 within the limits
    rows = [_tse_row(_PF, mask if column == "name" else f"ANA {_letters(i)}",
                     mask if column == "registry" else f"ANA {_letters(i)}")
            for i in range(20)]
    _serve_member(cdn, "2024", _tse_csv(rows))
    with pytest.raises(ValueError, match=f"20 of 20 individuals' rows .* carry no "
                                         f"{'name' if column == 'name' else 'registry'}"):
        local.fetch(_TSE)
    assert local.load(_TSE) is None


def test_a_tse_numeric_column_moved_under_a_name_is_refused(
        cdn: _Cdn, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(tse, "TSE_MAX_NUMBERED", 1 / 1000)
    _serve_member(cdn, "2022", _tse_csv(_tse_names(4)))
    _serve_member(cdn, "2024", _tse_csv(
        [_tse_row(_PF, f"ANA {_letters(i)}", f"CEP 401{i:05d}") for i in range(20)]))
    with pytest.raises(ValueError, match="20 of 20 individuals' rows .* a number in a name"):
        local.fetch(_TSE)


@pytest.mark.parametrize("column", ["NM_DOADOR", "NM_DOADOR_RFB"])
def test_a_tse_column_masked_with_one_word_is_refused(cdn: _Cdn, column: str) -> None:
    rows = [_tse_row(_PF, "XXXXX" if column == "NM_DOADOR" else f"ANA {_letters(i)}",
                     "XXXXX" if column == "NM_DOADOR_RFB" else f"ANA {_letters(i)}")
            for i in range(20)]
    _serve_member(cdn, "2024", _tse_csv(rows))
    with pytest.raises(ValueError, match=f"20 individuals' rows hold 1 distinct {column}$"
                                         "|hold 1 distinct " + column):
        local.fetch(_TSE)


def test_a_tse_election_at_each_limit_is_read(
        cdn: _Cdn, monkeypatch: pytest.MonkeyPatch) -> None:
    # 100 individuals' rows of 1,000: the floor exactly. One without a name
    # and one with a number: each ceiling exactly. 25 distinct names of
    # 100 rows: the distinct floor exactly. A registry name of 4 digits is
    # kept, a filed name of 5 is not.
    for name in ("TSE_MAX_MISSING", "TSE_MAX_NUMBERED"):
        monkeypatch.setattr(tse, name, 1 / 100)
    _serve_member(cdn, "2022", _tse_csv(_tse_names(4)))
    rows = ([_tse_row(_PARTY, "PARTIDO", "PARTIDO")] * 900
            + [_tse_row(_PF, f"ANA {_letters(i % 25)}", f"ANA {_letters(i % 25)}")
               for i in range(97)]
            + [_tse_row(_PF, "#NULO", "ANA"),
               _tse_row(_PF, "ANA 12345", "ANA"),
               _tse_row(_PF, "ANA AAA", "ANA AAA 1234")])
    _serve_member(cdn, "2024", _tse_csv(rows))
    corpus = local.fetch(_TSE)
    assert {"name": "ANA AAA", "registry": "ANA AAA 1234"} in corpus.records
    assert not any("12345" in r["name"] for r in corpus.records)
    assert corpus.meta["detail"]["2024_individuals_whose_name_holds_a_number"] == 1


@pytest.mark.parametrize(("rows", "shown"), [
    # A frequent donor's name, held by a tenth of the rows: not a category.
    ([_tse_row("ANA SOUZA", "ANA", "ANA")] * 10 + _tse_names(90), False),
    # A value holding digits, however many rows hold it.
    ([_tse_row(_CPF, "ANA", "ANA")] * 100, False),
    ([_tse_row("Recursos novos", "ANA", "ANA")] * 60 + _tse_names(40), True),
], ids=["a frequent name", "a number", "a category"])
def test_a_tse_unknown_value_is_quoted_only_when_it_reads_as_a_category(
        cdn: _Cdn, monkeypatch: pytest.MonkeyPatch,
        rows: list[list[str]], shown: bool) -> None:
    monkeypatch.setattr(tse, "TSE_QUOTED_SHARE", 1 / 2)
    _serve_member(cdn, "2022", _tse_csv(rows))
    with pytest.raises(ValueError, match="outside TSE_ORIGINS") as raised:
        local.fetch(_TSE)
    message = str(raised.value)
    assert ("Recursos novos" in message) is shown
    assert "ANA SOUZA" not in message and _CPF not in message


def test_a_tse_member_the_csv_reader_cannot_read_names_the_way_out(cdn: _Cdn) -> None:
    # A quote left open: the field runs past the csv module's limit.
    member = _tse_csv([]) + b'"x";"' + b"A" * 200_000
    _serve_member(cdn, "2022", member)
    with pytest.raises(ValueError, match="receitas_candidatos_2022_BRASIL.csv in .* "
                                         "cannot be read \\(Error: .*fetch again"):
        local.fetch(_TSE)


def test_a_tse_rate_limit_waits_as_long_as_the_server_asks(
        cdn: _Cdn, monkeypatch: pytest.MonkeyPatch) -> None:
    waits: list[float] = []
    monkeypatch.setattr(time, "sleep", waits.append)
    cdn.failures = [_http_error(429, retry_after="30")]
    assert local.fetch(_TSE).records == _TSE_RECORDS
    assert waits == [30]


def test_a_tse_range_failing_every_attempt_raises_the_last_error(cdn: _Cdn) -> None:
    cdn.failures = [_http_error(503) for _ in range(core.RETRIES)]
    with pytest.raises(urllib.error.HTTPError) as raised:
        local.fetch(_TSE)
    raised.value.close()
    assert cdn.ranges == core.RETRIES


def test_a_tse_server_that_states_no_accept_ranges_is_read(cdn: _Cdn) -> None:
    cdn.accept_ranges = None  # the header is optional; only "none" refuses
    assert local.fetch(_TSE).records == _TSE_RECORDS


def test_a_tse_range_file_refuses_a_seek_before_its_start(cdn: _Cdn) -> None:
    reader = tse._RangeFile(_url("2022"))
    with pytest.raises(OSError, match="cannot seek"):
        reader.seek(-1)
    assert reader.tell() == 0


def test_a_tse_corpus_of_other_elections_is_refused_on_load(
        cdn: _Cdn, monkeypatch: pytest.MonkeyPatch) -> None:
    local.fetch(_TSE)
    monkeypatch.setattr(tse, "TSE_ELECTIONS", ("2022", "2024", "2026"))
    with pytest.raises(ValueError, match=f"holds the elections 2022 2024.*reads "
                                         f"2022 2024 2026.*fetch {_TSE} --refresh"):
        local.load(_TSE)


# -- Taiwan political donations ------------------------------------------------

_TW = "tw-donors"
_TW_ELECTION, _TW_AREA = "109年立法委員選舉", "臺北市"
#: A masked ID, an address and a phone that must never reach the corpus.
_TW_PRIVATE = ("A12****789", "臺北市中正區某某路1號", "02-2****678")
#: An area's code in its zip's name, as the platform's names carry one.
_TW_AREA_CODES = {"臺北市": "63000", "新北市": "65000"}
_FIRST, _RESIDUAL = "首次申報", "第1次賸餘"


def _tw_row(category: str, donor: str, serial: str = _FIRST,
            columns: int = 25) -> list[str]:
    row = ["1", "候選人甲", _TW_ELECTION, serial, "1081201", category, donor,
           _TW_PRIVATE[0], "1000", "0", "現金", "1081202", "", "", "", _TW_PRIVATE[1],
           _TW_PRIVATE[2], "", "", "", "", "", "", "", ""]
    return row[:columns]


def _tw_csv(rows: list[list[str]], header: tuple[str, ...] | None = None) -> bytes:
    out = io.StringIO()
    writer = csv.writer(out, lineterminator="\r\n")
    writer.writerow(header or tw.TW_HEADER)
    writer.writerows(rows)
    return out.getvalue().encode("utf-8-sig")


def _tw_zip(incomes: bytes | None,
            date: tuple[int, int, int, int, int, int] = (2023, 9, 12, 14, 4, 54)) -> bytes:
    """A report zip holding `incomes` as incomes.csv (none when it is
    None) beside an expenditures.csv, deflated as the platform's zips
    are."""
    out = io.BytesIO()
    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as archive:
        if incomes is not None:
            archive.writestr(zipfile.ZipInfo("incomes.csv", date, ), incomes,
                             zipfile.ZIP_DEFLATED)
        archive.writestr(zipfile.ZipInfo("expenditures.csv", date), b"")
    return out.getvalue()


def _tw_report(serial: int = 1, election: str = _TW_ELECTION, area: str = _TW_AREA,
               version: str = "112091204") -> dict[str, Any]:
    return {"type": "Election", "yearOrSerial": float(serial), "electionName": election,
            "electionArea": area,
            "zipFileName": f"election-{version}-{serial}-{_TW_AREA_CODES[area]}.zip"}


def _tw_first(*rows: list[str]) -> dict[tuple[str, str, int], bytes]:
    """The zips of a listing of the first report alone, holding `rows`."""
    return {(_TW_ELECTION, _TW_AREA, 1): _tw_zip(_tw_csv(list(rows)))}


#: Two reports of one election: a donor in both, one padded with
#: spaces, a business, an anonymous gift, and donations naming no one.
#: The first report is the newer file, so the data date is not simply
#: the last report's.
_TW_ZIPS = {
    (_TW_ELECTION, _TW_AREA, 1): _tw_zip(_tw_csv([
        _tw_row("個人捐贈收入", "王小明"), _tw_row("個人捐贈收入", " 陳大文 "),
        _tw_row("營利事業捐贈收入", "某某股份有限公司"), _tw_row("匿名捐贈", "匿名"),
        _tw_row("個人捐贈收入", " ")]), date=(2024, 3, 1, 9, 0, 0)),
    (_TW_ELECTION, _TW_AREA, 2): _tw_zip(_tw_csv([
        _tw_row("個人捐贈收入", "王小明", _RESIDUAL), _tw_row("個人捐贈收入", "林一二", _RESIDUAL),
        _tw_row("個人捐贈收入", "匿名", _RESIDUAL), _tw_row("個人捐贈收入", "-", _RESIDUAL)])),
}
_TW_LISTING = [_tw_report(1), _tw_report(2)]

TwAnswer = Exception | bytes


def _serve_tw(monkeypatch: pytest.MonkeyPatch, *,
              listings: list[list[dict[str, Any]]] | None = None,
              zips: dict[tuple[str, str, int], bytes] | None = None,
              counted: int | None = None,
              fail: Callable[[str], TwAnswer | None] = lambda url: None) -> list[str]:
    """Answer the listing from `listings` in turn (the last one again
    once they run out), paged by page and pageSize and counted as
    `counted` (their length when None), and each download from `zips` by
    its election, area and serial. `fail` may answer a URL instead. The
    URLs asked."""
    monkeypatch.setattr(time, "sleep", lambda s: None)
    listings = listings or [_TW_LISTING]
    zips = _TW_ZIPS if zips is None else zips
    asked: list[str] = []
    turn = iter(listings)
    current: list[dict[str, Any]] = []

    def urlopen(request: urllib.request.Request, timeout: int) -> _Response:
        url = request.full_url
        asked.append(url)
        if (answer := fail(url)) is not None:
            if isinstance(answer, Exception):
                raise answer
            return _Response(answer)
        query = {k: v[0] for k, v in urllib.parse.parse_qs(
            urllib.parse.urlsplit(url).query, keep_blank_values=True).items()}
        if "/search/elections" in url:
            if query["page"] == "1":
                current[:] = next(turn, current)
            size, page = int(query["pageSize"]), int(query["page"])
            body: Any = {"paging": {"recordCount": len(current) if counted is None
                                    else counted},
                         "data": current[(page - 1) * size:page * size]}
            return _Response(json.dumps(body).encode())
        return _Response(zips[(query["ElectionName"], query["ElectionArea"],
                               int(query["YearOrSerial"]))])
    monkeypatch.setattr(urllib.request, "urlopen", urlopen)
    return asked


def _tw_downloads(monkeypatch: pytest.MonkeyPatch,
                  listings: list[list[dict[str, Any]]] | None = None,
                  zips: dict[tuple[str, str, int], bytes] | None = None) -> list[str]:
    """Fetch over _serve_tw; the serial of each report downloaded."""
    asked = _serve_tw(monkeypatch, listings=listings, zips=zips)
    local.fetch(_TW)
    return _tw_serials(asked)


def _tw_serials(asked: list[str]) -> list[str]:
    return [urllib.parse.parse_qs(urllib.parse.urlsplit(u).query)["YearOrSerial"][0]
            for u in asked if "/Search/download" in u]


def _tw_cache(tmp_path: Path) -> Path:
    return tmp_path / "local" / _TW / "reports"


@pytest.fixture
def _tw_home(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> Path:
    monkeypatch.setenv("NAMEPARSER_TOOLS_CACHE", str(tmp_path))
    return tmp_path


def test_a_tw_fetch_keeps_each_donor_s_name_once_and_counts_the_rest(
        monkeypatch: pytest.MonkeyPatch, _tw_home: Path) -> None:
    _serve_tw(monkeypatch)
    corpus = local.fetch(_TW)
    assert corpus.records == [{"name": "林一二"}, {"name": "王小明"}, {"name": "陳大文"}]
    assert corpus.meta["data_date"] == "2024-03-01T09:00:00"  # the newer file's
    assert corpus.meta["detail"] == {
        "reports": 2, "first_reports": 1, "elections": 1, "rows": 9,
        "individual_donations": 7, "rows_from_other_categories": 2,
        "donations_without_a_name": 3, "donations_naming_a_masked_donor": 0,
        "rows_of_a_report_with_no_income": 0, "records_cut_back_into_their_lines": 0,
        "rows_not_as_long_as_the_header": 0, "rows_without_a_category": 0,
        "rows_cut_by_a_stray_quote": 0}
    assert corpus.header().startswith("Control Yuan political donation reports")
    assert "Open Government Data License, version 1.0" in corpus.header()
    assert corpus.header().endswith("3 names (local corpus tw-donors)")


def test_a_tw_fetch_keeps_only_the_donor_column(
        monkeypatch: pytest.MonkeyPatch, _tw_home: Path) -> None:
    _serve_tw(monkeypatch)
    local.fetch(_TW)
    for name in ("raw.jsonl", "corpus.jsonl", "meta.json"):
        text = (_tw_home / "local" / _TW / name).read_text(encoding="utf-8")
        assert not [field for field in _TW_PRIVATE if field in text], name


def test_a_tw_fetch_asks_for_each_listed_report_s_zip(
        monkeypatch: pytest.MonkeyPatch, _tw_home: Path) -> None:
    asked = _serve_tw(monkeypatch)
    local.fetch(_TW)
    downloads = [urllib.parse.parse_qs(urllib.parse.urlsplit(u).query,
                                       keep_blank_values=True)
                 for u in asked if "/Search/download" in u]
    assert [(d["ElectionName"], d["ElectionArea"], d["YearOrSerial"], d["DownloadType"])
            for d in downloads] == [([_TW_ELECTION], [_TW_AREA], [s], ["3"])
                                    for s in ("1", "2")]


def test_a_tw_fetch_pauses_after_each_download(
        monkeypatch: pytest.MonkeyPatch, _tw_home: Path) -> None:
    sleeps: list[float] = []
    _serve_tw(monkeypatch)
    monkeypatch.setattr(time, "sleep", sleeps.append)
    local.fetch(_TW)
    assert sleeps.count(tw.TW_DELAY) == 2 and tw.TW_DELAY >= 1


def test_a_tw_listing_of_several_pages_is_read_whole(
        monkeypatch: pytest.MonkeyPatch, _tw_home: Path) -> None:
    monkeypatch.setattr(tw, "TW_PAGE", 1)
    _serve_tw(monkeypatch)
    assert local.fetch(_TW).meta["detail"]["reports"] == 2


@pytest.mark.timeout(30)  # a listing loop that never stops hangs, not fails
@pytest.mark.parametrize(("listing", "counted", "match"), [
    (_TW_LISTING[:1], 2, "listed 1 reports of the 2"),
    ([_TW_LISTING[0], _TW_LISTING[0]], None, "listed twice"),
    ([_TW_LISTING[0], {**_TW_LISTING[1], "zipFileName": _TW_LISTING[0]["zipFileName"]}],
     None, "zip name .* another report has"),
    ([{**_TW_LISTING[0], "type": "Party"}], None, "type 'Party'"),
    ([{**_TW_LISTING[0], "yearOrSerial": 7.0}], None, "serial 7.0"),
], ids=["cut short", "a report twice", "two reports one zip", "not an election's",
        "an unknown serial"])
def test_a_tw_listing_that_cannot_be_trusted_is_refused(
        monkeypatch: pytest.MonkeyPatch, _tw_home: Path,
        listing: list[dict[str, Any]], counted: int | None, match: str) -> None:
    _serve_tw(monkeypatch, listings=[listing], counted=counted)
    with pytest.raises(ValueError, match=match):
        local.fetch(_TW)
    assert local.load(_TW) is None


@pytest.mark.parametrize("changed", [
    [*_TW_LISTING, _tw_report(1, area="新北市")],
    [_TW_LISTING[0], _tw_report(2, version="113010100")],
    _TW_LISTING[:1],
], ids=["a report published", "a report replaced", "a report withdrawn"])
def test_a_tw_fetch_whose_listing_moves_under_it_is_refused(
        monkeypatch: pytest.MonkeyPatch, _tw_home: Path,
        changed: list[dict[str, Any]]) -> None:
    _serve_tw(monkeypatch, listings=[_TW_LISTING, changed])
    with pytest.raises(ValueError, match="published, replaced or withdrew a report"):
        local.fetch(_TW)
    assert local.load(_TW) is None


_TW_RENAMED = tuple("捐贈者" if c == "捐贈者／支出對象" else c for c in tw.TW_HEADER)
#: A column inserted before the category's, the last dropped: 25
#: columns, and the donor column now holding the category.
_TW_SHIFTED = (*tw.TW_HEADER[:5], "新欄位", *tw.TW_HEADER[5:24])
#: The category column named twice, in place of a column not read.
_TW_TWICE = tuple("收支科目" if c == "地址" else c for c in tw.TW_HEADER)


@pytest.mark.parametrize(("incomes", "match"), [
    (_tw_csv([_tw_row("個人捐贈收入", "王小明")], header=_TW_RENAMED), "has the header"),
    (_tw_csv([_tw_row("個人捐贈收入", "王小明")], header=_TW_SHIFTED), "has the header"),
    (_tw_csv([_tw_row("個人捐贈收入", "王小明")], header=_TW_TWICE), "has the header"),
    (_tw_csv([_tw_row("個人捐贈收入", "王小明")], header=tw.TW_HEADER[:5]),
     "has the header"),
    (_tw_csv([_tw_row("政治團體捐贈收入", "王小明")]), "the category '政治團體捐贈收入'"),
    (_tw_csv([_tw_row("個人捐贈收入", "王小明")]).decode("utf-8-sig").encode("big5"),
     "is not UTF-8"),
], ids=["a column renamed", "a column inserted", "a column twice",
        "a needed column missing", "an unknown category", "Big5"])
def test_a_tw_report_whose_layout_has_changed_is_refused(
        monkeypatch: pytest.MonkeyPatch, _tw_home: Path, incomes: bytes, match: str) -> None:
    _serve_tw(monkeypatch, listings=[_TW_LISTING[:1]],
              zips={(_TW_ELECTION, _TW_AREA, 1): _tw_zip(incomes)})
    with pytest.raises(ValueError, match=match):
        local.fetch(_TW)
    assert local.load(_TW) is None


@pytest.mark.parametrize("serial", [_FIRST, "第一次賸餘", _RESIDUAL])
def test_a_tw_zip_of_another_report_is_refused(
        monkeypatch: pytest.MonkeyPatch, _tw_home: Path, serial: str) -> None:
    # A server answering a residual report with the first report's zip,
    # or the reverse, would merge one report's donors into another's.
    listing = [_tw_report(3)]
    zips = {(_TW_ELECTION, _TW_AREA, 3): _tw_zip(_tw_csv([
        _tw_row("個人捐贈收入", "王小明", serial)]))}
    _serve_tw(monkeypatch, listings=[listing], zips=dict(zips))
    with pytest.raises(ValueError, match="the zip is another report's"):
        local.fetch(_TW)
    assert not _tw_cache(_tw_home).exists()  # so a later fetch asks again
    # Its own serial, in either numerals, is read.
    for version, own in (("113010101", "第2次賸餘"), ("113010102", "第二次賸餘")):
        zips[(_TW_ELECTION, _TW_AREA, 3)] = _tw_zip(_tw_csv([
            _tw_row("個人捐贈收入", "王小明", own)]))
        listing[0] = _tw_report(3, version=version)
        assert _tw_downloads(monkeypatch, listings=[listing], zips=zips) == ["3"], own


def test_a_tw_report_missing_a_column_it_does_not_read_is_read_by_name(
        monkeypatch: pytest.MonkeyPatch, _tw_home: Path) -> None:
    # A 2020 by-election's report had no 更正註記, which a check of the
    # header against all 25 columns found on 2026-10-22; the column
    # after it moved up one, so a reader indexing TW_HEADER reads the
    # wrong one. The test reverses the header to move every column.
    header = tuple(reversed([c for c in tw.TW_HEADER if c != "更正註記"]))
    row = dict(zip(tw.TW_HEADER, _tw_row("個人捐贈收入", "王小明")))
    zips = {(_TW_ELECTION, _TW_AREA, 1): _tw_zip(_tw_csv([[row[c] for c in header]],
                                                         header=header))}
    _serve_tw(monkeypatch, listings=[_TW_LISTING[:1]], zips=zips)
    assert local.fetch(_TW).records == [{"name": "王小明"}]


def test_a_tw_report_with_no_income_is_counted_and_read_past(
        monkeypatch: pytest.MonkeyPatch, _tw_home: Path) -> None:
    # Such a report writes one row, every column a dash but the
    # candidate's, as a by-election's report did on 2026-10-22.
    empty = ["-"] * 25
    empty[1] = "候選人乙"
    zips = {**_TW_ZIPS, (_TW_ELECTION, _TW_AREA, 2): _tw_zip(_tw_csv([empty]))}
    _serve_tw(monkeypatch, zips=zips)
    corpus = local.fetch(_TW)
    assert corpus.records == [{"name": "王小明"}, {"name": "陳大文"}]
    assert corpus.meta["detail"]["rows_of_a_report_with_no_income"] == 1
    assert corpus.meta["detail"]["rows"] == 6


def _dashed(**filled: str) -> list[str]:
    """A row of dashes but the candidate's column and `filled`."""
    row: dict[str, str] = {**dict.fromkeys(tw.TW_HEADER, "-"),
                           "擬參選人／政黨": "候選人乙", **filled}
    return [row[c] for c in tw.TW_HEADER]


@pytest.mark.parametrize("row", [
    _tw_row("-", "王小明"),
    _dashed(收入金額="1000"),
], ids=["a donor named", "an amount filled"])
def test_a_tw_dash_category_in_a_row_that_is_not_empty_is_refused(
        monkeypatch: pytest.MonkeyPatch, _tw_home: Path, row: list[str]) -> None:
    _serve_tw(monkeypatch, listings=[_TW_LISTING[:1]], zips=_tw_first(row))
    with pytest.raises(ValueError, match="the category '-'"):
        local.fetch(_TW)


@pytest.mark.parametrize(("bad", "key", "match"), [
    (_tw_row("個人捐贈收入", "王小明", columns=24), "rows_not_as_long_as_the_header",
     "1 of 2 rows are not as long as"),
    (_tw_row("", "王小明"), "rows_without_a_category", "1 of 2 rows are without a category"),
], ids=["short rows", "rows without a category"])
def test_a_tw_fetch_with_too_many_bad_rows_is_refused(
        monkeypatch: pytest.MonkeyPatch, _tw_home: Path,
        bad: list[str], key: str, match: str) -> None:
    # The share is the whole fetch's: one bad row of two is half, which
    # the share for one report lets through.
    _serve_tw(monkeypatch, listings=[_TW_LISTING[:1]],
              zips=_tw_first(bad, _tw_row("個人捐贈收入", "陳大文")))
    with pytest.raises(ValueError, match=match):
        local.fetch(_TW)
    monkeypatch.setattr(tw, "TW_MAX_BAD", 1)  # under the share: counted
    corpus = local.fetch(_TW)
    assert corpus.records == [{"name": "陳大文"}]
    assert corpus.meta["detail"][key] == 1


def test_a_small_tw_report_whose_rows_are_all_bad_is_refused(
        monkeypatch: pytest.MonkeyPatch, _tw_home: Path) -> None:
    # Over the whole fetch its rows are a sliver; alone they are all of
    # it, and a report whose donors all go must not pass for read.
    big = [_tw_row("個人捐贈收入", f"王小{n}") for n in range(30)]
    short = [_tw_row("個人捐贈收入", f"陳大{n}", _RESIDUAL, columns=24) for n in range(3)]
    zips = {(_TW_ELECTION, _TW_AREA, 1): _tw_zip(_tw_csv(big)),
            (_TW_ELECTION, _TW_AREA, 2): _tw_zip(_tw_csv(short))}
    monkeypatch.setattr(tw, "TW_MAX_BAD", 1)
    _serve_tw(monkeypatch, zips=zips)
    with pytest.raises(ValueError, match="3 of .* report 2's rows are read past"):
        local.fetch(_TW)


def _tw_incomes_text(lines: list[str]) -> bytes:
    return ("\r\n".join([",".join(tw.TW_HEADER), *lines]) + "\r\n").encode("utf-8-sig")


def _line(donor: str, address: str = "臺北市", phone: str = "02") -> str:
    row = _tw_row("個人捐贈收入", donor)
    row[15], row[16] = address, phone
    return ",".join(row)


def test_rows_a_stray_quote_takes_in_are_read_back(
        monkeypatch: pytest.MonkeyPatch, _tw_home: Path) -> None:
    # An address opening with a quote nothing closes until a later row:
    # the rows between, 169 in three reports on 2026-10-22, would go
    # into one field and their donors with them.
    lines = [_line("王小明", address='"臺北市'), _line("陳大文"), _line("林一二"),
             _line("趙六", phone='02"')]
    _serve_tw(monkeypatch, listings=[_TW_LISTING[:1]],
              zips={(_TW_ELECTION, _TW_AREA, 1): _tw_zip(_tw_incomes_text(lines))})
    corpus = local.fetch(_TW)  # every line whole with quotes taken literally
    assert len(corpus.records) == 4
    assert corpus.meta["detail"]["records_cut_back_into_their_lines"] == 1
    assert corpus.meta["detail"]["rows_cut_by_a_stray_quote"] == 0
    # A line between holding a quoted comma is no whole row read
    # literally: the lines are read alone as quoted, the opening line cut.
    lines[2] = _line("林一二", phone='"02,03"')
    for cached in _tw_cache(_tw_home).iterdir():
        cached.unlink()
    _serve_tw(monkeypatch, listings=[_TW_LISTING[:1]],
              zips={(_TW_ELECTION, _TW_AREA, 1): _tw_zip(_tw_incomes_text(lines))})
    monkeypatch.setattr(tw, "TW_MAX_BAD", 1)
    corpus = local.fetch(_TW)
    assert {"name": "陳大文"} in corpus.records and {"name": "林一二"} in corpus.records
    assert corpus.meta["detail"]["rows_cut_by_a_stray_quote"] >= 1
    monkeypatch.setattr(tw, "TW_MAX_BAD", 1 / 10_000)
    with pytest.raises(ValueError, match="rows are cut by a stray quote"):
        local.fetch(_TW)


def test_two_stray_quotes_one_row_after_another_lose_neither_row(
        monkeypatch: pytest.MonkeyPatch, _tw_home: Path) -> None:
    # The second quote closes the first: one record as wide as the
    # header out of two rows, which no line read alone as quoted shows.
    lines = [_line("王小明", address='"臺北市'), _line("陳大文", address='"臺南市'),
             _line("林一二")]
    _serve_tw(monkeypatch, listings=[_TW_LISTING[:1]],
              zips={(_TW_ELECTION, _TW_AREA, 1): _tw_zip(_tw_incomes_text(lines))})
    corpus = local.fetch(_TW)
    assert corpus.records == [{"name": "林一二"}, {"name": "王小明"}, {"name": "陳大文"}]
    assert corpus.meta["detail"]["records_cut_back_into_their_lines"] == 1


@pytest.mark.parametrize("ending", ["\r", "\r\n", "\n"], ids=["CR", "CRLF", "LF"])
def test_a_bare_cr_ends_a_line_as_csv_reads_one(
        monkeypatch: pytest.MonkeyPatch, _tw_home: Path, ending: str) -> None:
    # A stray CR in a cell cuts its row in two short rows, counted, as
    # csv.reader over a file opened with newline="" reads it, and a file
    # whose lines end in CR alone reads whole.
    text = ending.join([",".join(tw.TW_HEADER), _line("王小明"),
                        _line("陳大文", address="臺北\r市"), _line("林一二")]) + ending
    _serve_tw(monkeypatch, listings=[_TW_LISTING[:1]],
              zips={(_TW_ELECTION, _TW_AREA, 1): _tw_zip(text.encode("utf-8-sig"))})
    monkeypatch.setattr(tw, "TW_MAX_BAD", 1)
    corpus = local.fetch(_TW)
    assert corpus.records == [{"name": "林一二"}, {"name": "王小明"}]
    assert corpus.meta["detail"]["rows_not_as_long_as_the_header"] == 2


def test_a_tw_file_csv_cannot_read_is_refused_naming_the_report(
        monkeypatch: pytest.MonkeyPatch, _tw_home: Path) -> None:
    huge = _line("王小明", address='"' + "x" * 200_000)  # past csv's field limit
    text = f"{','.join(tw.TW_HEADER)}\r\n{huge}\r\n"
    _serve_tw(monkeypatch, listings=[_TW_LISTING[:1]],
              zips={(_TW_ELECTION, _TW_AREA, 1): _tw_zip(text.encode("utf-8-sig"))})
    with pytest.raises(ValueError, match="report 1's incomes.csv is not a CSV file"):
        local.fetch(_TW)


def test_a_quoted_field_spanning_two_lines_stays_one_row(
        monkeypatch: pytest.MonkeyPatch, _tw_home: Path) -> None:
    # A quoted field that truly spans lines, its second line no row
    # (none was found on 2026-10-22: all 12 multi-line records were
    # rows a stray quote joined).
    lines = [_line("王小明", phone='"02\r\n09"'), _line("陳大文")]
    _serve_tw(monkeypatch, listings=[_TW_LISTING[:1]],
              zips={(_TW_ELECTION, _TW_AREA, 1): _tw_zip(_tw_incomes_text(lines))})
    corpus = local.fetch(_TW)
    assert corpus.records == [{"name": "王小明"}, {"name": "陳大文"}]
    assert corpus.meta["detail"]["records_cut_back_into_their_lines"] == 0


def test_a_masked_donor_name_is_counted_and_refused_past_the_share(
        monkeypatch: pytest.MonkeyPatch, _tw_home: Path) -> None:
    # A platform that began masking names as it masks IDs would fill the
    # corpus with masked ones.
    _serve_tw(monkeypatch, listings=[_TW_LISTING[:1]], zips=_tw_first(
        _tw_row("個人捐贈收入", "王*明"), _tw_row("個人捐贈收入", "陳大文")))
    with pytest.raises(ValueError, match="1 of 2 individual donations name a "
                                         "masked donor"):
        local.fetch(_TW)
    monkeypatch.setattr(tw, "TW_MAX_BAD", 1)
    corpus = local.fetch(_TW)
    assert corpus.records == [{"name": "陳大文"}]
    assert corpus.meta["detail"]["donations_naming_a_masked_donor"] == 1


def test_a_tw_zip_with_no_incomes_file_is_refused_and_not_cached(
        monkeypatch: pytest.MonkeyPatch, _tw_home: Path) -> None:
    asked = _serve_tw(monkeypatch, listings=[_TW_LISTING[:1]],
                      zips={(_TW_ELECTION, _TW_AREA, 1): _tw_zip(None)})
    with pytest.raises(ValueError, match="holds no incomes.csv"):
        local.fetch(_TW)
    assert _tw_serials(asked) == ["1"]  # not retried
    assert not list(_tw_cache(_tw_home).glob("*.zip"))  # nor kept to refuse again


def _corrupt(body: bytes) -> bytes:
    """`body` with a byte of its deflated member flipped."""
    at = body.index(b"incomes.csv") + 40
    return body[:at] + bytes([body[at] ^ 0xFF]) + body[at + 1:]


@pytest.mark.parametrize("damage", [lambda b: b[:-30], _corrupt],
                         ids=["cut short", "a member that does not inflate"])
def test_a_damaged_tw_zip_is_fetched_again(
        monkeypatch: pytest.MonkeyPatch, _tw_home: Path,
        damage: Callable[[bytes], bytes]) -> None:
    bad = [damage(_TW_ZIPS[(_TW_ELECTION, _TW_AREA, 1)])]
    asked = _serve_tw(monkeypatch, fail=lambda url: bad.pop()
                      if "/Search/download" in url and bad else None)
    assert len(local.fetch(_TW).records) == 3
    assert _tw_serials(asked) == ["1", "1", "2"]


def test_a_listed_tw_report_that_keeps_failing_is_raised(
        monkeypatch: pytest.MonkeyPatch, _tw_home: Path) -> None:
    # The platform answers a fault with the 500 it gives a report that
    # does not exist; the listing says this one does, so it is no absence.
    asked = _serve_tw(monkeypatch, fail=lambda url: _http_error(500)
                      if "/Search/download" in url else None)
    with pytest.raises(urllib.error.HTTPError) as raised:
        local.fetch(_TW)
    raised.value.close()
    assert len(_tw_serials(asked)) == core.RETRIES
    assert local.load(_TW) is None


def test_a_tw_refetch_downloads_only_the_reports_rebuilt_since(
        monkeypatch: pytest.MonkeyPatch, _tw_home: Path) -> None:
    # A refresh would otherwise download every listed report again.
    assert _tw_downloads(monkeypatch) == ["1", "2"]
    assert _tw_downloads(monkeypatch) == []
    rebuilt = [_TW_LISTING[0], _tw_report(2, version="113010100")]
    zips = {**_TW_ZIPS, (_TW_ELECTION, _TW_AREA, 2): _tw_zip(_tw_csv([
        _tw_row("個人捐贈收入", "趙六", _RESIDUAL)]))}
    assert _tw_downloads(monkeypatch, listings=[rebuilt], zips=zips) == ["2"]
    assert sorted(p.name for p in _tw_cache(_tw_home).iterdir()) == [
        "election-112091204-1-63000.zip", "election-113010100-2-63000.zip"]
    corpus = local.load(_TW)
    assert corpus is not None and {"name": "趙六"} in corpus.records


def test_a_refused_tw_fetch_keeps_its_zips_and_goes_on_where_it_stopped(
        monkeypatch: pytest.MonkeyPatch, _tw_home: Path) -> None:
    stale = _tw_cache(_tw_home) / "election-100000000-1-63000.zip"
    stale.parent.mkdir(parents=True)
    stale.write_bytes(b"a report the listing no longer names")
    asked = _serve_tw(monkeypatch, fail=lambda url: _http_error(500)
                      if "YearOrSerial=2" in url else None)
    with pytest.raises(urllib.error.HTTPError) as raised:
        local.fetch(_TW)
    raised.value.close()
    assert stale.exists()  # deleted only by a fetch that passes its checks
    assert _tw_serials(asked)[0] == "1"
    assert _tw_downloads(monkeypatch) == ["2"]
    assert not stale.exists()


def test_a_tw_refresh_rebuilds_the_corpus_from_the_cached_zips(
        monkeypatch: pytest.MonkeyPatch, _tw_home: Path) -> None:
    asked = _serve_tw(monkeypatch)
    assert local.main(["fetch", _TW]) == 0
    first = (_tw_home / "local" / _TW / "meta.json").read_bytes()
    assert local.main(["fetch", _TW, "--refresh"]) == 0
    assert _tw_serials(asked) == ["1", "2"]  # each downloaded once
    assert sum("/search/elections" in u for u in asked) == 4  # listed again
    corpus = local.load(_TW)
    assert corpus is not None and len(corpus.records) == 3
    assert json.loads(first)["sha256"] == corpus.meta["sha256"]


def test_a_cached_tw_zip_cut_short_is_downloaded_again(
        monkeypatch: pytest.MonkeyPatch, _tw_home: Path,
        capsys: pytest.CaptureFixture[str]) -> None:
    _tw_downloads(monkeypatch)
    cached = _tw_cache(_tw_home) / "election-112091204-1-63000.zip"
    cached.write_bytes(cached.read_bytes()[:-30])
    assert _tw_downloads(monkeypatch) == ["1"]
    assert cached.read_bytes() == _TW_ZIPS[(_TW_ELECTION, _TW_AREA, 1)]
    assert "downloading again a cached zip that is not whole" in capsys.readouterr().err


@pytest.mark.parametrize("name", ["../meta.json", "a/b.zip", "", None])
def test_a_tw_zip_name_that_is_no_file_name_is_refused(
        monkeypatch: pytest.MonkeyPatch, _tw_home: Path, name: str | None) -> None:
    # The name is the platform's, and the cache writes a file under it.
    _serve_tw(monkeypatch, listings=[[{**_TW_LISTING[0], "zipFileName": name}]])
    with pytest.raises(ValueError, match="no file name this tool caches"):
        local.fetch(_TW)
    assert not _tw_cache(_tw_home).exists()


# -- UK Electoral Commission donations ---------------------------------------------

_UKEC = "ukec-individuals"
#: 2026-10-23T03:13:19Z, as the search states it.
_UKEC_GENERATED = "/Date(1792725199000)/"


def _ukec_row(name: str, status: str = "Individual", donor_id: str = "1",
              fields: int = 29) -> list[str]:
    row = [""] * max(fields, 29)
    row[ukec.UKEC_COLUMNS.index("DonorName")] = name
    row[ukec.UKEC_COLUMNS.index("DonorStatus")] = status
    row[ukec.UKEC_COLUMNS.index("DonorId")] = donor_id
    return row[:fields]


#: One person under two IDs and once with the name padded, a name holding
#: a comma, a company, an individual with no name, a row of 28 fields and
#: a person with no ID: 8 rows.
_UKEC_ROWS = [
    _ukec_row("Mr Bo Wu", donor_id="1"), _ukec_row("Mr Bo Wu", donor_id="2"),
    _ukec_row(" Mr Bo Wu ", donor_id="2"), _ukec_row("Lee, Ann", donor_id="3"),
    _ukec_row("Acme Ltd", status="Company", donor_id="4"),
    _ukec_row(" ", donor_id="5"), _ukec_row("Cy Roe", fields=28),
    _ukec_row("Dee Fox", donor_id=""),
]
#: 2026-10-23T09:00:00Z: a second search's answer, later than the first.
_UKEC_LATER = "/Date(1792746000000)/"


def _ukec_csv(rows: list[list[str]] = _UKEC_ROWS,
              header: tuple[str, ...] | None = None, bom: bytes = b"\xef\xbb\xbf") -> bytes:
    out = io.StringIO(newline="")
    writer = csv.writer(out, lineterminator="\r\n")
    writer.writerow(ukec.UKEC_COLUMNS if header is None else header)
    writer.writerows(rows)
    return bom + out.getvalue().encode()


def _serve_ukec(monkeypatch: pytest.MonkeyPatch, body: bytes,
                *totals: int) -> list[str]:
    """Answer the export with `body` and the search with each of `totals`
    in turn (the rows of `body` twice, by default), the first answer
    generated at _UKEC_GENERATED and the second at _UKEC_LATER; the URLs
    asked."""
    counts = iter(totals or (body.count(b"\r\n") - 1,) * 2)
    stamps = iter([_UKEC_GENERATED, _UKEC_LATER])
    asked: list[str] = []

    def urlopen(request: urllib.request.Request, timeout: int) -> _Response:
        asked.append(request.full_url)
        if request.full_url == ukec.UKEC_CSV_URL:
            return _Response(body)
        assert request.full_url == ukec.UKEC_COUNT_URL
        return _Response(json.dumps({"Total": next(counts),
                                     "Generated": next(stamps)}).encode())
    monkeypatch.setattr(urllib.request, "urlopen", urlopen)
    return asked


def _tolerate_a_small_fixture(monkeypatch: pytest.MonkeyPatch) -> None:
    """Let _UKEC_ROWS, whose 8 rows skip one of each kind, pass the shares."""
    monkeypatch.setattr(ukec, "UKEC_MAX_BAD", 1)
    monkeypatch.setattr(ukec, "UKEC_MAX_NAMELESS", 1)


def _failing_once(monkeypatch: pytest.MonkeyPatch, url: str) -> list[str]:
    """Make the stubbed urlopen raise a 503 the first time `url` is asked,
    with no sleep between attempts; the URLs that failed."""
    served: Callable[..., object] = urllib.request.urlopen
    failed: list[str] = []

    def flaky(request: urllib.request.Request, timeout: int) -> object:
        if request.full_url == url and not failed:
            failed.append(url)
            raise _http_error(503)
        return served(request, timeout)
    monkeypatch.setattr(urllib.request, "urlopen", flaky)
    monkeypatch.setattr(time, "sleep", lambda seconds: None)
    return failed


@pytest.mark.parametrize("which", ["UKEC_COUNT_URL", "UKEC_CSV_URL"])
def test_a_ukec_request_failing_once_is_retried(
        monkeypatch: pytest.MonkeyPatch, which: str) -> None:
    # The register's search and export once went out bare: one 503 in
    # either ended the fetch, where every other source retries.
    _tolerate_a_small_fixture(monkeypatch)
    _serve_ukec(monkeypatch, _ukec_csv())
    failed = _failing_once(monkeypatch, getattr(ukec, which))
    assert local.fetch(_UKEC).records
    assert failed == [getattr(ukec, which)]


def test_a_ukec_search_answering_no_json_is_refused_as_a_value_error(
        monkeypatch: pytest.MonkeyPatch) -> None:
    # An error page served with HTTP 200 is retried as a body cut short,
    # and once the retries run out the fetch must still fail as a
    # ValueError, as the other refusals do, not as the retry's own class.
    monkeypatch.setattr(time, "sleep", lambda seconds: None)
    asked: list[str] = []

    def urlopen(request: urllib.request.Request, timeout: int) -> _Response:
        asked.append(request.full_url)
        return _Response(b"<html>Service Unavailable</html>")
    monkeypatch.setattr(urllib.request, "urlopen", urlopen)
    with pytest.raises(ValueError, match="is not JSON"):
        local.fetch(_UKEC)
    assert asked == [ukec.UKEC_COUNT_URL] * core.RETRIES


def test_the_ukec_count_asks_the_export_s_own_filter() -> None:
    # A count under another filter would vouch for an export it did not count.
    def query(url: str) -> list[tuple[str, str]]:
        return urllib.parse.parse_qsl(urllib.parse.urlsplit(url).query,
                                      keep_blank_values=True)
    csv_query, count_query = query(ukec.UKEC_CSV_URL), query(ukec.UKEC_COUNT_URL)
    assert ("donorStatus", "individual") in csv_query
    assert [p for p in csv_query if p[0] != "rows"] == [
        p for p in count_query if p[0] != "rows"]


def test_a_ukec_fetch_keeps_each_person_s_name_once_and_counts_the_rest(
        monkeypatch: pytest.MonkeyPatch) -> None:
    _tolerate_a_small_fixture(monkeypatch)
    asked = _serve_ukec(monkeypatch, _ukec_csv())
    corpus = local.fetch(_UKEC)
    assert asked == [ukec.UKEC_COUNT_URL, ukec.UKEC_CSV_URL, ukec.UKEC_COUNT_URL]
    assert corpus.records == [{"name": "Dee Fox"}, {"name": "Lee, Ann"},
                              {"name": "Mr Bo Wu"}]
    # The first search's time, not the second's.
    assert corpus.meta["data_date"] == "2026-10-23T03:13:19Z"
    assert corpus.meta["detail"] == {
        "donations": 8, "donor_ids": 4, "individuals_without_a_name": 1,
        "rows_not_29_fields": 1, "rows_not_individual": 1}
    assert corpus.header().endswith("3 names (local corpus ukec-individuals)")


def test_a_ukec_export_without_a_bom_reads_the_same(
        monkeypatch: pytest.MonkeyPatch) -> None:
    _tolerate_a_small_fixture(monkeypatch)
    assert ukec._ukec_read(_ukec_csv(bom=b""), 8) == ukec._ukec_read(_ukec_csv(), 8)


@pytest.mark.parametrize("header", [
    tuple("DonorFullName" if c == "DonorName" else c for c in ukec.UKEC_COLUMNS),
    (*ukec.UKEC_COLUMNS, "DonorTitle"),
    ukec.UKEC_COLUMNS[:-1],
], ids=["a column renamed", "a column added", "a column dropped"])
def test_a_ukec_export_whose_header_has_changed_is_refused(
        monkeypatch: pytest.MonkeyPatch, header: tuple[str, ...]) -> None:
    _serve_ukec(monkeypatch, _ukec_csv([_ukec_row("Mr Bo Wu")], header=header))
    with pytest.raises(ValueError, match="header is not the 29 columns"):
        local.fetch(_UKEC)
    assert local.load(_UKEC) is None


@pytest.mark.parametrize(("totals", "match"), [
    ((9, 9), "held 8 donations where the search counts 9"),
    ((7, 7), "held 8 donations where the search counts 7"),
    ((8, 9), r"register changed during the fetch \(8 -> 9"),
], ids=["a capped or cut export", "an export holding more", "a register that grew"])
def test_a_ukec_export_that_is_not_the_whole_register_is_refused(
        monkeypatch: pytest.MonkeyPatch, totals: tuple[int, int], match: str) -> None:
    _tolerate_a_small_fixture(monkeypatch)
    _serve_ukec(monkeypatch, _ukec_csv(), *totals)
    with pytest.raises(ValueError, match=match):
        local.fetch(_UKEC)
    assert local.load(_UKEC) is None


@pytest.mark.parametrize(("rows", "match"), [
    ([_ukec_row("Acme Ltd", status="Company")] * 2 + [_ukec_row("Mr Bo Wu")],
     "2 of 3 rows .* from a donor that is not 'Individual'"),
    ([_ukec_row("Mr Bo Wu", fields=30)] * 2 + [_ukec_row("Cy Roe")],
     "2 of 3 rows .* not 29 fields"),
], ids=["the filter no longer applied", "rows not 29 fields"])
def test_a_ukec_export_holding_rows_it_cannot_read_is_refused(
        monkeypatch: pytest.MonkeyPatch, rows: list[list[str]], match: str) -> None:
    _serve_ukec(monkeypatch, _ukec_csv(rows))
    with pytest.raises(ValueError, match=match):
        local.fetch(_UKEC)
    assert local.load(_UKEC) is None


#: Rows enough that UKEC_MAX_BAD's real share (1 in 10,000) is a row.
_UKEC_MANY = 10_000


@pytest.mark.parametrize(("bad", "kind", "match"), [
    (_ukec_row("Cy Roe", fields=28), "rows_not_29_fields", "not 29 fields"),
    (_ukec_row("Acme Ltd", status="Company"), "rows_not_individual",
     "not 'Individual'"),
], ids=["rows not 29 fields", "rows not individual"])
@pytest.mark.parametrize("skipped", [1, 2])
def test_a_ukec_export_is_refused_past_its_real_share_of_skipped_rows(
        monkeypatch: pytest.MonkeyPatch, bad: list[str], kind: str, match: str,
        skipped: int) -> None:
    # One skipped row in 10,000 passes and two are refused, at the
    # shipped UKEC_MAX_BAD, unpatched; each arm alone.
    rows = [bad] * skipped + [_ukec_row(f"Bo Wu {i}") for i in range(_UKEC_MANY - skipped)]
    _serve_ukec(monkeypatch, _ukec_csv(rows))
    if skipped == 1:
        assert local.fetch(_UKEC).meta["detail"][kind] == 1
    else:
        with pytest.raises(ValueError, match=f"2 of 10,000 rows .* {match}"):
            local.fetch(_UKEC)


@pytest.mark.parametrize("nameless", [10, 11])
def test_a_ukec_export_is_refused_past_its_share_of_nameless_individuals(
        monkeypatch: pytest.MonkeyPatch, nameless: int) -> None:
    # A DonorName column emptied wholesale would otherwise read as a
    # register of a few names: 10 in 10,000 pass at UKEC_MAX_NAMELESS.
    rows = [_ukec_row(" ")] * nameless + [
        _ukec_row(f"Bo Wu {i}") for i in range(_UKEC_MANY - nameless)]
    _serve_ukec(monkeypatch, _ukec_csv(rows))
    if nameless == 10:
        assert local.fetch(_UKEC).meta["detail"]["individuals_without_a_name"] == 10
    else:
        with pytest.raises(ValueError, match="11 of 10,000 rows .* no name"):
            local.fetch(_UKEC)


@pytest.mark.parametrize("cut", [
    lambda body: body[:-5],
    lambda body: body[:body.rindex(b"Wu 9999") + 2],
    lambda body: body[:-2],
    lambda body: body[:body.rindex(b"Wu\n") + 3],
], ids=["inside the last row", "inside a quoted field", "before the last line break",
        "at a line break inside a quoted field"])
def test_a_ukec_export_cut_inside_its_last_row_is_refused(
        monkeypatch: pytest.MonkeyPatch, cut: Callable[[bytes], bytes]) -> None:
    # csv returns the cut row as a short last row, so the count matches
    # the search's and the row would pass as one of the few malformed
    # ones UKEC_MAX_BAD allows, losing its name: at the real share.
    rows = [_ukec_row(f"Bo Wu {i}") for i in range(_UKEC_MANY - 1)]
    # A field holding line breaks, which the export quotes, so that one
    # cut ends at a line break and still inside the row.
    rows.append(_ukec_row('Bo "Wu 9999"', donor_id="Bo\nWu\nId"))
    body = _ukec_csv(rows)
    _serve_ukec(monkeypatch, cut(body), _UKEC_MANY, _UKEC_MANY)
    with pytest.raises(ValueError, match="last row is cut short"):
        local.fetch(_UKEC)
    assert local.load(_UKEC) is None


def test_a_ukec_export_ending_in_a_long_row_is_not_taken_for_a_cut_one(
        monkeypatch: pytest.MonkeyPatch) -> None:
    # A cut only shortens a row, so a whole export whose last row is one
    # of the malformed few UKEC_MAX_BAD tolerates is read, not refused
    # as cut: a refetch would return the same export.
    rows = [_ukec_row(f"Bo Wu {i}") for i in range(_UKEC_MANY - 1)]
    rows.append(_ukec_row("Cy Roe", fields=30))
    _serve_ukec(monkeypatch, _ukec_csv(rows))
    assert local.fetch(_UKEC).meta["detail"]["rows_not_29_fields"] == 1


def test_a_ukec_export_ending_in_a_blank_line_is_refused(
        monkeypatch: pytest.MonkeyPatch) -> None:
    rows = [_ukec_row(f"Bo Wu {i}") for i in range(_UKEC_MANY)]
    _serve_ukec(monkeypatch, _ukec_csv(rows) + b"\r\n", _UKEC_MANY, _UKEC_MANY)
    with pytest.raises(ValueError, match="cut short or blank"):
        local.fetch(_UKEC)


def test_a_ukec_export_that_is_not_utf8_is_refused(
        monkeypatch: pytest.MonkeyPatch) -> None:
    body = _ukec_csv([_ukec_row("Mr Bo Wu")]).replace(b"Wu", b"W\xfc")
    _serve_ukec(monkeypatch, body)
    with pytest.raises(ValueError, match="not UTF-8"):
        local.fetch(_UKEC)
    assert local.load(_UKEC) is None


def test_a_ukec_export_csv_cannot_read_is_refused_as_a_value_error(
        monkeypatch: pytest.MonkeyPatch) -> None:
    # csv.Error is no ValueError, so the CLI would show a traceback.
    limit = csv.field_size_limit()
    csv.field_size_limit(20)
    try:
        _serve_ukec(monkeypatch, _ukec_csv([_ukec_row("Mr Bo Wu " * 5)]))
        with pytest.raises(ValueError, match="not CSV this reads"):
            local.fetch(_UKEC)
    finally:
        csv.field_size_limit(limit)


@pytest.mark.parametrize("answer", [
    {"Generated": _UKEC_GENERATED}, {"Total": "7", "Generated": _UKEC_GENERATED},
    {"Total": 7}, [], {"Total": True, "Generated": _UKEC_GENERATED},
], ids=["no Total", "a Total not a number", "no Generated", "not an object",
        "a Total that is a boolean"])
def test_a_ukec_search_that_states_no_count_is_refused(
        monkeypatch: pytest.MonkeyPatch, answer: object) -> None:
    def urlopen(request: urllib.request.Request, timeout: int) -> _Response:
        return _Response(json.dumps(answer).encode())
    monkeypatch.setattr(urllib.request, "urlopen", urlopen)
    with pytest.raises(ValueError, match="states no"):
        local.fetch(_UKEC)


# -- Nepal's local election candidates -------------------------------------------

_NEPAL = "nepal-candidates"
_NEPAL_TOKEN = "a" * 32


def _nepal_row(romanized: object, devanagari: object = "राम बहादुर", **extra: object
               ) -> dict[str, object]:
    """A candidate as a local body's file writes one, every name invented."""
    return {"CandidateName": devanagari, "CandidateNameEng": romanized,
            "Gender": "पुरुष", "Age": 40, "Ward": 1, "PostId": 6, "CandidateID": 1,
            "PartyID": 2, "SymbolID": 3, "TotalVoteReceived": 99, **extra}


#: Three bodies: a pair twice in one body (once padded) and again in
#: another, the same Devanagari under a second romanization, a candidate
#: with no Devanagari name, and an empty file.
_NEPAL_FILES: dict[int, object] = {
    101: [_nepal_row("Dil Maya B.K.", "दिल माया वि.क."),
          _nepal_row("Sita Kumari K.C.", "सीता कुमारी के.सी."),
          _nepal_row(" Dil Maya B.K. ", "दिल माया वि.क. "),
          _nepal_row("Hari Thapa", "")],
    102: [_nepal_row("Dil Maya B.K.", "दिल माया वि.क."),
          _nepal_row("Dil Maya BK", "दिल माया वि.क.")],
    103: [],
}


def _nepal_error(url: str, code: int) -> urllib.error.HTTPError:
    return urllib.error.HTTPError(url, code, "x", email.message.Message(), None)


class _Root(_Response):
    """The site's root page, setting `cookies`."""

    def __init__(self, *cookies: str) -> None:
        super().__init__(b"<html></html>")
        self.headers = email.message.Message()
        for cookie in cookies:
            self.headers["Set-Cookie"] = cookie


class _Site:
    """result.election.gov.np, offline. The root sets a token; the
    handler answers 403 to a request not echoing the current one, else
    the lookup from `files`' ids and each file from `files` (a list
    served as JSON, bytes as they are, an exception raised; a missing id
    is a 404). `expire` makes a token lapse after that many handler
    requests, as a session does."""

    def __init__(self, monkeypatch: pytest.MonkeyPatch, files: dict[int, object],
                 *, bom: bytes = b"\xef\xbb\xbf", listed: object = None) -> None:
        self.files, self.bom, self.listed = files, bom, listed
        self.requests: list[urllib.request.Request] = []
        self.tokens = 0
        self.expire: int | None = None
        self.used = 0
        monkeypatch.setattr(time, "sleep", lambda seconds: None)
        monkeypatch.setattr(nepal, "NEPAL_BODIES", len(files))
        # Pinned as if an empty file had held one candidate before it
        # was blanked: every real file did.
        monkeypatch.setattr(nepal, "NEPAL_CANDIDATES", sum(
            len(rows) or 1 for rows in files.values() if isinstance(rows, list)))
        monkeypatch.setattr(urllib.request, "urlopen", self.urlopen)

    @property
    def token(self) -> str:
        return f"{_NEPAL_TOKEN[:-1]}{self.tokens}"

    def handler(self, path: str) -> str:
        return nepal.NEPAL_HANDLER + path

    def urlopen(self, request: urllib.request.Request, timeout: int) -> _Response:
        url = request.full_url
        self.requests.append(request)
        if url == nepal.NEPAL_SITE:
            self.tokens += 1
            self.used = 0
            return _Root("ASP.NET_SessionId=s1; path=/; HttpOnly",
                         f"CsrfToken={self.token}; path=/")
        assert url.startswith(nepal.NEPAL_HANDLER)
        self.used += 1
        if (request.get_header("X-csrf-token") != self.token
                or f"CsrfToken={self.token}" not in (request.get_header("Cookie") or "")
                or self.expire is not None and self.used > self.expire):
            raise _nepal_error(url, 403)
        path = url[len(nepal.NEPAL_HANDLER):]
        if path == nepal.NEPAL_LOOKUP:
            listed = self.listed if self.listed is not None else [
                {"id": i, "name": "नगरपालिका", "parentId": 1} for i in self.files]
            return _Response(self.bom + json.dumps(listed).encode())
        body = int(path.rsplit("/", 1)[1].removesuffix(".json"))
        if body not in self.files:
            raise _nepal_error(url, 404)
        answer = self.files[body]
        if callable(answer):
            answer = answer()
        if isinstance(answer, Exception):
            raise answer
        if isinstance(answer, bytes):
            return _Response(answer)
        return _Response(self.bom + json.dumps(answer, ensure_ascii=False).encode())

    def asked(self) -> list[str]:
        return [r.full_url.removeprefix(nepal.NEPAL_HANDLER) for r in self.requests]


@pytest.fixture
def site(monkeypatch: pytest.MonkeyPatch) -> _Site:
    return _Site(monkeypatch, dict(_NEPAL_FILES))


def _tolerate_nepal_s_small_fixture(monkeypatch: pytest.MonkeyPatch) -> None:
    """Let _NEPAL_FILES, whose 6 candidates include one with no
    Devanagari name and whose 3 files one that is empty, pass
    NEPAL_MAX_NAMELESS, NEPAL_MAX_MISSING and NEPAL_MAX_SHORT."""
    monkeypatch.setattr(nepal, "NEPAL_MAX_NAMELESS", 1)
    monkeypatch.setattr(nepal, "NEPAL_MAX_MISSING", 1)
    monkeypatch.setattr(nepal, "NEPAL_MAX_SHORT", 1)


def test_a_nepal_fetch_keeps_each_pair_once_and_counts_the_rest(
        site: _Site, monkeypatch: pytest.MonkeyPatch) -> None:
    _tolerate_nepal_s_small_fixture(monkeypatch)
    corpus = local.fetch(_NEPAL)
    assert corpus.records == [
        {"name": "Dil Maya B.K.", "devanagari": "दिल माया वि.क."},
        {"name": "Dil Maya BK", "devanagari": "दिल माया वि.क."},
        {"name": "Hari Thapa", "devanagari": ""},
        {"name": "Sita Kumari K.C.", "devanagari": "सीता कुमारी के.सी."}]
    assert re.fullmatch(r"\d{4}-\d\d-\d\dT\d\d:\d\d:\d\dZ", corpus.meta["data_date"])
    assert corpus.meta["detail"] == {
        "election": "Election2079", "local_bodies": 3, "local_bodies_missing": "",
        "local_bodies_empty": "103", "files": 3, "candidates": 6,
        "without_the_name_keys": 0, "without_a_romanized_name": 0,
        "without_a_devanagari_name": 1, "devanagari_name_without_devanagari": 0,
        "romanized_name_not_latin": 0, "sessions_renewed": 0, "largest_file": 4}
    assert corpus.meta["corpus_keys"] == ["name", "devanagari"]
    assert corpus.header().endswith("4 name pairs (local corpus nepal-candidates)")
    assert site.asked() == [nepal.NEPAL_SITE, nepal.NEPAL_LOOKUP,
                            *(nepal.NEPAL_BODY.format(id=i) for i in (101, 102, 103))]


def test_a_nepal_fetch_writes_no_field_but_the_two_names(
        site: _Site, monkeypatch: pytest.MonkeyPatch, _own_cache: Path) -> None:
    # Gender, age, ward, votes and the ids stay in the site's files.
    _tolerate_nepal_s_small_fixture(monkeypatch)
    local.fetch(_NEPAL)
    raw = (_own_cache / "local" / _NEPAL / "raw.jsonl").read_text()
    assert {key for line in raw.splitlines() for key in json.loads(line)} == {
        "name", "devanagari"}
    assert "पुरुष" not in raw and "99" not in raw


def test_a_nepal_corpus_holds_both_scripts_names_for_the_snapshot(
        site: _Site, monkeypatch: pytest.MonkeyPatch, _own_cache: Path) -> None:
    # The romanized name is the record's "name"; the Devanagari one is
    # read too, so a snapshot watches both scripts, an empty one skipped.
    _tolerate_nepal_s_small_fixture(monkeypatch)
    local.fetch(_NEPAL)
    corpus = _own_cache / "local" / _NEPAL / "corpus.jsonl"
    texts = sorted(json.loads(line) for line in corpus.read_text().splitlines())
    assert texts == ["Dil Maya B.K.", "Dil Maya BK", "Hari Thapa", "Sita Kumari K.C.",
                     "दिल माया वि.क.", "सीता कुमारी के.सी."]
    assert local.load(_NEPAL).meta["names"] == 6
    assert snapshot.main(["--local", _NEPAL, "--record"]) == 0
    recorded = _own_cache / "local" / _NEPAL / "snapshot.jsonl"
    assert snapshot.row_count(recorded.read_text()) == 6


def test_a_nepal_name_keeps_its_vowel_signs_virama_and_joiners(
        monkeypatch: pytest.MonkeyPatch, _own_cache: Path) -> None:
    # What the corpus is for: the combining marks and the ZWJ/ZWNJ a
    # Devanagari name is written with reach the corpus as written.
    joined = "क्\u200dष्मा प्\u200cरसाद"
    _Site(monkeypatch, {7: [_nepal_row("Ksma Prasad", joined)]})
    local.fetch(_NEPAL)
    corpus = (_own_cache / "local" / _NEPAL / "corpus.jsonl").read_text()
    assert joined in {json.loads(line) for line in corpus.splitlines()}


def test_every_nepal_request_carries_the_site_s_own_check(
        site: _Site, monkeypatch: pytest.MonkeyPatch) -> None:
    # The site's double-submit check: its CsrfToken cookie echoed in a
    # header, with the Referer its pages send, and a User-Agent of a
    # browser's form, the site refusing one holding "python".
    _tolerate_nepal_s_small_fixture(monkeypatch)
    local.fetch(_NEPAL)
    for request in site.requests:
        agent = request.get_header("User-agent") or ""
        assert agent.startswith("Mozilla/5.0") and "python" not in agent.lower()
    for request in site.requests[1:]:
        assert request.get_header("X-csrf-token") == site.token
        assert request.get_header("Referer") == nepal.NEPAL_SITE
        assert request.get_header("Cookie") == f"ASP.NET_SessionId=s1; CsrfToken={site.token}"


def test_a_nepal_token_the_site_no_longer_holds_renews_the_session(
        site: _Site, monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture[str]) -> None:
    # A fetch can outlast a session: a 403 renews it, counted, and asks again.
    _tolerate_nepal_s_small_fixture(monkeypatch)
    site.expire = 2
    corpus = local.fetch(_NEPAL)
    assert len(corpus.records) == 4
    assert corpus.meta["detail"]["sessions_renewed"] == 1
    assert site.asked().count(nepal.NEPAL_SITE) == 2
    assert "renewing the session after a 403" in capsys.readouterr().err


def test_a_nepal_403_after_a_renewed_session_is_raised(
        site: _Site, monkeypatch: pytest.MonkeyPatch) -> None:
    # A file the site keeps refusing is no missing file: the fetch stops.
    site.files[102] = lambda: _nepal_error("u", 403)
    with pytest.raises(urllib.error.HTTPError, match="403") as raised:
        local.fetch(_NEPAL)
    raised.value.close()
    assert site.asked().count(nepal.NEPAL_BODY.format(id=102)) == 2
    assert local.load(_NEPAL) is None


def test_a_nepal_server_error_is_retried_and_its_last_raised(
        site: _Site, monkeypatch: pytest.MonkeyPatch) -> None:
    errors = iter([_nepal_error("u", 503)])
    site.files[102] = lambda: next(errors, _NEPAL_FILES[102])
    _tolerate_nepal_s_small_fixture(monkeypatch)
    assert len(local.fetch(_NEPAL).records) == 4
    site.files[102] = lambda: _nepal_error("u", 503)
    with pytest.raises(urllib.error.HTTPError, match="503") as raised:
        local.fetch(_NEPAL)
    raised.value.close()
    assert site.asked().count(nepal.NEPAL_BODY.format(id=102)) == 2 + core.RETRIES


_NEPAL_WHOLE = json.dumps(_NEPAL_FILES[101], ensure_ascii=False).encode()


@pytest.mark.parametrize("cut", [
    lambda body: body[:-1],
    lambda body: body[:body.rindex(b"}") + 1],
    lambda body: body[:body.rindex(b"},") + 2],
    lambda body: body[:body.rindex("माया".encode()) + 2],
    lambda body: b"",
], ids=["before the closing bracket", "after a whole candidate",
        "after a candidate's comma", "inside a letter", "empty"])
def test_a_nepal_file_cut_short_fails_to_parse_and_is_refused(
        site: _Site, cut: Callable[[bytes], bytes]) -> None:
    # A JSON array cut anywhere short of its end does not parse, so a cut
    # file is retried as one cut in transit and never read as a body
    # with fewer candidates.
    site.files[101] = cut(_NEPAL_WHOLE)
    with pytest.raises(ValueError, match="is not UTF-8 JSON"):
        local.fetch(_NEPAL)
    assert site.asked().count(nepal.NEPAL_BODY.format(id=101)) == core.RETRIES
    assert local.load(_NEPAL) is None


def test_a_nepal_file_cut_once_is_read_whole_on_the_retry(
        site: _Site, monkeypatch: pytest.MonkeyPatch) -> None:
    answers = iter([_NEPAL_WHOLE[:-1]])
    site.files[101] = lambda: next(answers, _NEPAL_WHOLE)
    _tolerate_nepal_s_small_fixture(monkeypatch)
    assert len(local.fetch(_NEPAL).records) == 4


def test_a_nepal_file_with_or_without_a_bom_reads_the_same(
        monkeypatch: pytest.MonkeyPatch) -> None:
    _tolerate_nepal_s_small_fixture(monkeypatch)
    _Site(monkeypatch, dict(_NEPAL_FILES))
    with_bom = local.fetch(_NEPAL).records
    _Site(monkeypatch, dict(_NEPAL_FILES), bom=b"")
    assert local.fetch(_NEPAL).records == with_bom


@pytest.mark.parametrize("answer", [b"{}", b"[1]", b"null", b'{"rows": []}'],
                         ids=["an object", "not candidates", "null", "a wrapped list"])
def test_a_nepal_file_that_is_not_a_list_of_candidates_is_refused(
        site: _Site, answer: bytes) -> None:
    site.files[101] = answer
    with pytest.raises(ValueError, match="is not a list of candidates"):
        local.fetch(_NEPAL)


@pytest.mark.parametrize(("listed", "match"), [
    ([{"id": 101}, {"id": 102}], "lists 2 local bodies .* not the 3"),
    ([{"id": 101}, {"id": 102}, {"id": 103}, {"id": 104}], "lists 4 local bodies"),
    ([{"id": 101}, {"id": 101}, {"id": 102}], r"\(2 distinct ids\)"),
    ([{"id": 101}, {"id": "102"}, {"id": 103}], "not a list of local bodies"),
    ([{"id": 101}, {"id": True}, {"id": 103}], "not a list of local bodies"),
    ({"bodies": []}, "not a list of local bodies"),
], ids=["one fewer", "one more", "an id twice", "an id as text", "an id a boolean",
        "not a list"])
def test_a_nepal_lookup_that_has_changed_is_refused(
        monkeypatch: pytest.MonkeyPatch, listed: object, match: str) -> None:
    _Site(monkeypatch, dict(_NEPAL_FILES), listed=listed)
    with pytest.raises(ValueError, match=match):
        local.fetch(_NEPAL)


def _nepal_bodies(n: int, missing: int = 0, empty: int = 0) -> dict[int, object]:
    """`n` bodies of one candidate each, the first `missing` of them
    answered as missing and the `empty` after those answered empty."""
    return {i: [] if i < missing + empty else
            [_nepal_row(f"Ram {_letters(i)}", f"राम {i}")] for i in range(missing, n)}


@pytest.mark.parametrize(("missing", "empty"), [(7, 0), (8, 0), (0, 7), (0, 8), (4, 3), (4, 4)])
def test_a_nepal_fetch_is_refused_past_its_real_share_of_missing_or_empty_files(
        monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str],
        missing: int, empty: int) -> None:
    # NEPAL_MAX_MISSING unpatched, and NEPAL_BODIES set back to its
    # shipped 753 (which the next test holds): 7 of 753 files missing or
    # empty pass, the ids of both kept, and 8 are refused. An empty file
    # counts as a missing one: a site that blanked its files would
    # otherwise read as a smaller election.
    site = _Site(monkeypatch, _nepal_bodies(753, missing, empty))
    monkeypatch.setattr(nepal, "NEPAL_BODIES", 753)
    monkeypatch.setattr(nepal, "NEPAL_CANDIDATES", 753)
    site.listed = [{"id": i, "name": "", "parentId": 1} for i in range(753)]
    if missing + empty == 7:
        detail = local.fetch(_NEPAL).meta["detail"]
        assert detail["local_bodies_missing"] == " ".join(map(str, range(missing)))
        assert detail["local_bodies_empty"] == " ".join(map(str, range(missing, 7)))
        assert detail["files"] == 753 - missing
        assert "750 of 753 local bodies" in capsys.readouterr().err
    else:
        with pytest.raises(ValueError, match="8 of 753 local bodies' files are missing"
                                             r" \(HTTP 404\) or empty"):
            local.fetch(_NEPAL)


def test_the_shipped_nepal_body_count_is_the_lookup_s() -> None:
    # The count the share above is taken at, as the lookup listed it.
    assert nepal.NEPAL_BODIES == 753


def test_the_nepal_user_agent_is_one_the_site_answers() -> None:
    # The site refuses a User-Agent holding "python" or "curl" with a 403
    # (2026-10-24), which would read as a lapsed token and then stop the fetch.
    agent = nepal.NEPAL_USER_AGENT.lower()
    assert "python" not in agent and "curl" not in agent


def _hundred(*bad: dict[str, object]) -> list[dict[str, object]]:
    """100 candidates: `bad`, then good ones."""
    good = [_nepal_row(f"Ram {_letters(i)}", f"राम {i}") for i in range(100 - len(bad))]
    return [*bad, *good]


@pytest.mark.parametrize(("bad", "key", "match"), [
    ({"CandidateID": 1}, "without_the_name_keys", "have no CandidateName or"),
    (_nepal_row("  "), "without_a_romanized_name", "have no romanized name"),
    (_nepal_row(None), "without_a_romanized_name", "have no romanized name"),
    (_nepal_row("- - -"), "without_a_romanized_name", "have no romanized name"),
    (_nepal_row("12 34"), "without_a_romanized_name", "have no romanized name"),
    (_nepal_row("Ram Zed", "१२३"), "without_a_devanagari_name", "have no Devanagari name"),
    (_nepal_row("Ram Zed", "| |"), "without_a_devanagari_name", "have no Devanagari name"),
    (_nepal_row("Ram Zed", ""), "without_a_devanagari_name", "have no Devanagari name"),
    (_nepal_row("Ram Zed", "राम ज़ेड", CandidateName=None), "without_a_devanagari_name",
     "have no Devanagari name"),
], ids=["no name keys", "a blank romanized name", "a null romanized name",
        "a placeholder for the romanized name", "digits for the romanized name",
        "digits for the Devanagari name", "a placeholder for the Devanagari name",
        "a blank Devanagari name", "a null Devanagari name"])
@pytest.mark.parametrize("count", [1, 2])
def test_a_nepal_fetch_is_refused_past_its_real_share_of_nameless_candidates(
        monkeypatch: pytest.MonkeyPatch, bad: dict[str, object], key: str, match: str,
        count: int) -> None:
    # At NEPAL_MAX_NAMELESS, unpatched: 1 of 100 passes and 2 are refused.
    _Site(monkeypatch, {1: _hundred(*[bad] * count)})
    if count == 1:
        assert local.fetch(_NEPAL).meta["detail"][key] == 1
    else:
        with pytest.raises(ValueError, match=f"2 of 100 (candidates |)?{match}"):
            local.fetch(_NEPAL)


@pytest.mark.parametrize(("bad", "key", "match"), [
    (_nepal_row("Ram Zed", "Ram Zed"), "devanagari_name_without_devanagari",
     "CandidateName values hold no Devanagari"),
    (_nepal_row("राम ज़ेड", "राम ज़ेड"), "romanized_name_not_latin",
     "CandidateNameEng values are not Latin"),
], ids=["Latin under Devanagari", "Devanagari under the romanized name"])
@pytest.mark.parametrize("count", [1, 2])
def test_a_nepal_fetch_is_refused_past_its_real_share_of_names_in_the_wrong_script(
        monkeypatch: pytest.MonkeyPatch, bad: dict[str, object], key: str, match: str,
        count: int) -> None:
    # Two columns swapped, or a romanization dropped, at
    # NEPAL_MAX_WRONG_SCRIPT, unpatched: 1 of 100 passes, 2 are refused.
    _Site(monkeypatch, {1: _hundred(*[bad] * count)})
    if count == 1:
        assert local.fetch(_NEPAL).meta["detail"][key] == 1
    else:
        with pytest.raises(ValueError, match=f"2 of 100 (candidates |)?{match}"):
            local.fetch(_NEPAL)


@pytest.mark.parametrize("word", ["Rām Śarmā", "Kṛṣṇa Ṭhākura", "Saʼadi"],
                         ids=["Latin Extended", "IAST's dotted letters", "a modifier letter"])
def test_a_nepal_romanized_name_in_any_latin_is_latin(
        monkeypatch: pytest.MonkeyPatch, word: str) -> None:
    # A romanization may write IAST's dotted letters (Latin Extended
    # Additional) or an apostrophe as a letter: 5 of 100 such names would
    # refuse the fetch were they read as another script.
    _Site(monkeypatch, {1: _hundred(*[_nepal_row(f"{word} {_letters(i)}")
                                      for i in range(5)])})
    assert local.fetch(_NEPAL).meta["detail"]["romanized_name_not_latin"] == 0


@pytest.mark.parametrize("column", ["CandidateNameEng", "CandidateName"])
def test_a_nepal_column_masked_with_one_word_is_refused(
        monkeypatch: pytest.MonkeyPatch, column: str) -> None:
    # Each pair stays distinct by the other column, so the pairs alone
    # would pass a masked column.
    masked = "Xxx" if column == "CandidateNameEng" else "राम"
    _Site(monkeypatch, {1: [{**row, column: masked} for row in _hundred()]})
    with pytest.raises(ValueError, match=f"hold 1 distinct {column}: the column may be masked"):
        local.fetch(_NEPAL)


@pytest.mark.parametrize("column", ["CandidateNameEng", "CandidateName"])
@pytest.mark.parametrize("distinct", [25, 24])
def test_a_nepal_column_is_refused_below_its_real_share_of_distinct_names(
        monkeypatch: pytest.MonkeyPatch, column: str, distinct: int) -> None:
    # At NEPAL_MIN_DISTINCT, unpatched: 25 distinct names in 100
    # candidates pass and 24 are refused, the other column distinct.
    def word(i: int) -> str:
        return f"Ram {_letters(i % distinct)}" if column == "CandidateNameEng" \
            else f"राम {i % distinct}"
    _Site(monkeypatch, {1: [{**row, column: word(i)} for i, row in enumerate(_hundred())]})
    if distinct == 25:
        assert local.fetch(_NEPAL).records
    else:
        with pytest.raises(ValueError, match=f"hold 24 distinct {column}"):
            local.fetch(_NEPAL)


def test_a_nepal_devanagari_word_is_looked_up_in_the_devanagari_names(
        site: _Site, monkeypatch: pytest.MonkeyPatch) -> None:
    # The word index reads every name the corpus holds, so a Devanagari
    # word is counted in the records whose Devanagari name writes it, not
    # read as a false zero; the romanized names are read as before.
    _tolerate_nepal_s_small_fixture(monkeypatch)
    local.fetch(_NEPAL)
    loaded = local.load(_NEPAL)
    assert loaded is not None
    assert local.lookup(loaded, "माया").anywhere == 2
    assert local.lookup(loaded, "Maya").anywhere == 2
    assert local.lookup(loaded, "B.K.").anywhere == 2  # BK folds alike
    # A phrase is read in each name, the Devanagari as the romanized.
    assert local.lookup(loaded, "दिल माया").anywhere == 2
    assert local.lookup(loaded, "सीता कुमारी").anywhere == 1


@pytest.mark.parametrize("word", ["Bishnu", "Bishnu Kumar"], ids=["a word", "a phrase"])
def test_a_word_both_of_a_record_s_names_write_counts_the_record_once(
        monkeypatch: pytest.MonkeyPatch, word: str) -> None:
    # A Devanagari name left partly in Latin shares words with the
    # romanization; the index counts records, not names, and a spelling
    # once a record.
    _Site(monkeypatch, {1: _hundred(_nepal_row("Bishnu Kumar Zed", "Bishnu Kumar राम"))})
    local.fetch(_NEPAL)
    loaded = local.load(_NEPAL)
    assert loaded is not None
    found = local.lookup(loaded, word)
    assert found.anywhere == 1
    if word == "Bishnu":
        assert found.spellings == {"Bishnu": 1}


def test_a_phrase_is_not_matched_across_a_record_s_two_names(
        monkeypatch: pytest.MonkeyPatch) -> None:
    # Each name is read alone: the romanization's last word and the
    # Devanagari name's first are not a phrase.
    _Site(monkeypatch, {1: _hundred(_nepal_row("Opal Zed", "Bishnu राम"))})
    local.fetch(_NEPAL)
    loaded = local.load(_NEPAL)
    assert loaded is not None
    assert local.lookup(loaded, "Zed").anywhere == 1
    assert local.lookup(loaded, "Zed Bishnu").anywhere == 0


def test_the_cached_index_is_keyed_to_the_names_it_reads(
        site: _Site, monkeypatch: pytest.MonkeyPatch) -> None:
    # A source that starts or stops reading a record's second name must
    # not answer from an index built over the other set, nor load a
    # corpus.jsonl built from it.
    _tolerate_nepal_s_small_fixture(monkeypatch)
    local.fetch(_NEPAL)
    loaded = local.load(_NEPAL)
    assert loaded is not None
    assert local.lookup(loaded, "माया").anywhere == 2
    monkeypatch.setitem(local.SOURCES, _NEPAL, dataclasses.replace(
        local.SOURCES[_NEPAL], corpus_keys=("name",)))
    with pytest.raises(local.CorpusDamaged, match=r"record keys \['name', 'devanagari'\]"):
        local.load(_NEPAL)
    # The index, read from the cache beside the same records, is rebuilt.
    assert local.lookup(local.Local(_NEPAL, loaded.meta), "माया").anywhere == 0


def test_a_corpus_fetched_before_its_keys_were_recorded_reads_as_name_alone(
        monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    # Every cached corpus fetched before corpus_keys were recorded was
    # built from "name": it loads for a source reading "name" alone.
    folder = _fetched(monkeypatch, tmp_path)
    _rewrite_meta(folder, corpus_keys=None)
    assert local.load(_SOURCE) is not None


def test_a_nepal_election_whose_files_hold_no_names_is_refused(
        monkeypatch: pytest.MonkeyPatch) -> None:
    # Past the nameless share's own refusal, which a wholly nameless
    # election would meet first, the empty corpus is still refused.
    monkeypatch.setattr(nepal, "NEPAL_MAX_NAMELESS", 1)
    _Site(monkeypatch, {1: [_nepal_row(""), _nepal_row(" ")]})
    with pytest.raises(ValueError, match="hold no candidate with a name"):
        local.fetch(_NEPAL)


@pytest.mark.parametrize("cookies", [[], ["CsrfToken=; path=/"]],
                         ids=["no cookie", "an empty token"])
def test_a_nepal_site_that_sets_no_token_is_refused(
        site: _Site, monkeypatch: pytest.MonkeyPatch, cookies: list[str]) -> None:
    monkeypatch.setattr(urllib.request, "urlopen", lambda request, timeout: _Root(*cookies))
    with pytest.raises(ValueError, match="set no CsrfToken cookie"):
        local.fetch(_NEPAL)


def test_a_nepal_root_failing_once_is_retried(
        site: _Site, monkeypatch: pytest.MonkeyPatch) -> None:
    _tolerate_nepal_s_small_fixture(monkeypatch)
    failed = _failing_once(monkeypatch, nepal.NEPAL_SITE)
    assert len(local.fetch(_NEPAL).records) == 4
    assert failed == [nepal.NEPAL_SITE]


def test_a_nepal_corpus_of_another_election_is_refused_on_load(
        site: _Site, monkeypatch: pytest.MonkeyPatch, _own_cache: Path) -> None:
    _tolerate_nepal_s_small_fixture(monkeypatch)
    local.fetch(_NEPAL)
    monkeypatch.setattr(nepal, "NEPAL_ELECTION", "Election2084")
    with pytest.raises(local.CorpusDamaged, match="holds the election Election2079"):
        local.load(_NEPAL)


def test_the_pairs_view_does_not_pair_two_scripts(
        site: _Site, monkeypatch: pytest.MonkeyPatch) -> None:
    # The pairs view compares the letters of two spellings, which a
    # Devanagari name and its romanization share none of; the Devanagari
    # is kept under its own key, not as a reference name.
    _tolerate_nepal_s_small_fixture(monkeypatch)
    local.fetch(_NEPAL)
    with pytest.raises(SystemExit, match="carry no reference name"):
        local.main(["pairs", _NEPAL])


def test_the_shipped_nepal_candidate_count_is_the_files_whole() -> None:
    # The count every whole fetch must read, as the 753 files held it.
    assert nepal.NEPAL_CANDIDATES == 152_960


@pytest.mark.parametrize("change", [-1, 1], ids=["one fewer", "one more"])
def test_a_nepal_election_of_another_size_with_every_file_whole_is_refused(
        site: _Site, monkeypatch: pytest.MonkeyPatch, change: int) -> None:
    # A site that trimmed its files (to the winners, or to one post), or
    # added to them, is refused however well formed what is left: with
    # every file read the count must be the pinned one, exactly.
    _tolerate_nepal_s_small_fixture(monkeypatch)
    del site.files[103]  # the empty one: every file whole
    monkeypatch.setattr(nepal, "NEPAL_BODIES", 2)
    monkeypatch.setattr(nepal, "NEPAL_CANDIDATES", 6 - change)
    with pytest.raises(ValueError, match="hold 6 candidates, 0 missing or empty"):
        local.fetch(_NEPAL)


@pytest.mark.parametrize(("pin", "refused"), [(7, False), (6, True), (5, True)],
                         ids=["one a lost file", "the pin itself", "over the pin"])
def test_a_nepal_election_with_a_file_lost_reads_at_most_the_pin_less_a_candidate_a_file(
        site: _Site, monkeypatch: pytest.MonkeyPatch, pin: int, refused: bool) -> None:
    # Every real file held a candidate, so with the empty file 103 the 6
    # read must be at most the pin less one: the count landing on the pin
    # with a file lost is the site's files grown by what it lost.
    _tolerate_nepal_s_small_fixture(monkeypatch)
    monkeypatch.setattr(nepal, "NEPAL_CANDIDATES", pin)
    if refused:
        with pytest.raises(ValueError, match="hold 6 candidates, 1 missing or empty"):
            local.fetch(_NEPAL)
    else:
        assert local.fetch(_NEPAL).meta["detail"]["local_bodies_empty"] == "103"


@pytest.mark.parametrize("held", [980, 979])
def test_a_nepal_election_with_a_file_missing_is_refused_past_its_real_shortfall(
        monkeypatch: pytest.MonkeyPatch, held: int) -> None:
    # With a file missing the count cannot be exact: at NEPAL_MAX_SHORT,
    # unpatched, 20 of 1,000 short pass and 21 are refused.
    _Site(monkeypatch, {2: [_nepal_row(f"Ram {_letters(i)}", f"राम {i}")
                            for i in range(held)]},
          listed=[{"id": i, "name": "", "parentId": 1} for i in (1, 2)])
    monkeypatch.setattr(nepal, "NEPAL_BODIES", 2)
    monkeypatch.setattr(nepal, "NEPAL_CANDIDATES", 1000)
    monkeypatch.setattr(nepal, "NEPAL_MAX_MISSING", 1)
    if held == 980:
        assert local.fetch(_NEPAL).meta["detail"]["local_bodies_missing"] == "1"
    else:
        with pytest.raises(ValueError, match="21 of 1,000 NEPAL_CANDIDATES are missing"):
            local.fetch(_NEPAL)


def test_a_nepal_site_answering_every_body_with_one_file_is_refused(
        monkeypatch: pytest.MonkeyPatch) -> None:
    # A cache serving one file under every id: every file whole and well
    # formed, the count matching, and the names four, read 40 times over.
    four = [_nepal_row(f"Ram {_letters(i)}", f"राम {i}") for i in range(4)]
    _Site(monkeypatch, {i: list(four) for i in range(40)})
    with pytest.raises(ValueError, match="distinct CandidateNameEng: the column may be masked"):
        local.fetch(_NEPAL)


@pytest.mark.parametrize("missing", ["CandidateName", "CandidateNameEng"])
@pytest.mark.parametrize("count", [1, 2])
def test_a_nepal_candidate_without_one_name_key_is_counted(
        monkeypatch: pytest.MonkeyPatch, missing: str, count: int) -> None:
    bad = {k: v for k, v in _nepal_row("Ram Zed", "राम ज़ेड").items() if k != missing}
    _Site(monkeypatch, {1: _hundred(*[bad] * count)})
    if count == 1:
        assert local.fetch(_NEPAL).meta["detail"]["without_the_name_keys"] == 1
    else:
        with pytest.raises(ValueError, match="2 of 100 candidates have no CandidateName or"):
            local.fetch(_NEPAL)


def test_a_nepal_lookup_answered_as_missing_is_raised_not_counted(
        site: _Site, monkeypatch: pytest.MonkeyPatch) -> None:
    # Only a body's file is counted as missing; without the lookup there
    # is no election to read.
    served = site.urlopen

    def urlopen(request: urllib.request.Request, timeout: int) -> object:
        if request.full_url == nepal.NEPAL_HANDLER + nepal.NEPAL_LOOKUP:
            site.requests.append(request)
            raise _nepal_error(request.full_url, 404)
        return served(request, timeout)
    monkeypatch.setattr(urllib.request, "urlopen", urlopen)
    with pytest.raises(urllib.error.HTTPError, match="404") as raised:
        local.fetch(_NEPAL)
    raised.value.close()
    assert site.asked().count(nepal.NEPAL_LOOKUP) == 1
    assert local.load(_NEPAL) is None


@pytest.mark.parametrize(("code", "asked"), [(503, None), (403, 1)],
                         ids=["a server error every time", "a refusal"])
def test_a_nepal_root_that_does_not_answer_is_raised(
        site: _Site, monkeypatch: pytest.MonkeyPatch, code: int, asked: int | None) -> None:
    # A 5xx at the root is retried and its last raised; a 403, what the
    # site answers a refused User-Agent, is raised at once, never read as
    # a site that sets no token.
    served = site.urlopen

    def urlopen(request: urllib.request.Request, timeout: int) -> object:
        if request.full_url == nepal.NEPAL_SITE:
            site.requests.append(request)
            raise _nepal_error(request.full_url, code)
        return served(request, timeout)
    monkeypatch.setattr(urllib.request, "urlopen", urlopen)
    with pytest.raises(urllib.error.HTTPError, match=str(code)) as raised:
        local.fetch(_NEPAL)
    raised.value.close()
    assert site.asked() == [nepal.NEPAL_SITE] * (asked or core.RETRIES)


@pytest.mark.parametrize(("cookies", "token", "header"), [
    (["CsrfToken=abc; path=/; Priority=High", "ASP.NET_SessionId=s1; HttpOnly"],
     "abc", "ASP.NET_SessionId=s1; CsrfToken=abc"),
    (['CsrfToken="a=b"; path=/'], '"a=b"', 'CsrfToken="a=b"'),
    (["CsrfToken=abc", "lang=ne np; path=/"], "abc", "CsrfToken=abc; lang=ne np"),
], ids=["an attribute the stdlib does not know", "a quoted value", "a value with a space"])
def test_a_nepal_cookie_is_sent_as_the_site_set_it(
        monkeypatch: pytest.MonkeyPatch, cookies: list[str], token: str, header: str) -> None:
    # An attribute is no cookie, a value is sent as written, and no
    # cookie the site set is left out.
    monkeypatch.setattr(urllib.request, "urlopen", lambda request, timeout: _Root(*cookies))
    assert nepal._session() == {"User-Agent": nepal.NEPAL_USER_AGENT,
                                "Referer": nepal.NEPAL_SITE, "X-CSRF-Token": token,
                                "Cookie": header}


@pytest.mark.parametrize("cookie", ["=abc; path=/", "Secure; path=/"],
                         ids=["no name", "no equals sign"])
def test_a_nepal_cookie_this_cannot_read_is_refused(
        monkeypatch: pytest.MonkeyPatch, cookie: str) -> None:
    # Read past, it would leave a cookie out of every request, and the
    # fetch die on a 403 that hides why.
    monkeypatch.setattr(urllib.request, "urlopen",
                        lambda request, timeout: _Root("CsrfToken=abc", cookie))
    with pytest.raises(ValueError, match="set a cookie with no name"):
        nepal._session()


@pytest.mark.parametrize(("records", "match"), [
    ([{"name": "Ann Lee", "devanagari": 3}], "'devanagari' is not text"),
    ([{"name": "Ann Lee", "devanagari": " "}],
     "no fetched record holds the corpus key 'devanagari'"),
    ([{"name": "Ann Lee", "devanagri": "राम"}],
     "no fetched record holds the corpus key 'devanagari'"),
], ids=["a value not text", "a value blank", "a key misspelled"])
def test_a_second_corpus_key_the_records_do_not_fill_is_refused(
        monkeypatch: pytest.MonkeyPatch, records: list[dict[str, object]], match: str) -> None:
    # Skipped in silence, its names would never reach the snapshot.
    monkeypatch.setitem(local.SOURCES, _NEPAL, dataclasses.replace(
        local.SOURCES[_NEPAL], fetch=lambda: local.Fetched(records, _DATE, {}), check=None))
    with pytest.raises(ValueError, match=match):
        local.fetch(_NEPAL)
    assert local.load(_NEPAL) is None


@pytest.mark.parametrize("source", sorted(set(local.SOURCES) - {_NEPAL}))
def test_every_other_source_s_corpus_and_index_read_the_name_alone(
        monkeypatch: pytest.MonkeyPatch, source: str) -> None:
    # A record's other keys (psc's boxes, tse's registry name) are no
    # names of the corpus or the word index.
    record = {"name": "Ann Lee", "given": "Bo Wu", "devanagari": "Cy Doe",
              "registry": "Dee Fox"}
    monkeypatch.setitem(local.SOURCES, source, dataclasses.replace(
        local.SOURCES[source], fetch=lambda: local.Fetched([record], _DATE, {}),
        check=None, renew=None))
    local.fetch(source)
    lines = local.corpus_path(source).read_text().splitlines()
    assert [json.loads(line) for line in lines] == ["Ann Lee"]
    loaded = local.load(source)
    assert loaded is not None
    assert local.lookup(loaded, "Lee").anywhere == 1
    assert [local.lookup(loaded, w).anywhere for w in ("Wu", "Cy", "Fox")] == [0, 0, 0]


# -- Companies House people with significant control ------------------------------

_PSC = "psc-individuals"
_PSC_DAY = "2026-10-22"
_PSC_PERSON = "individual-person-with-significant-control"


def _psc_person(name: str, nationality: str | None = "British",
                kind: str = _PSC_PERSON, **elements: str) -> dict[str, Any]:
    """A PSC record as the snapshot writes it, its boxes from `elements`
    (or split from `name`: forename, then surname), with the fields the
    corpus must not keep."""
    if not elements:
        forename, _, surname = name.partition(" ")
        elements = {"title": "Mr", "forename": forename, "surname": surname}
        name = f"Mr {name}"
    data: dict[str, Any] = {
        "kind": kind, "name": name, "name_elements": elements,
        "address": {"premises": "1 Invented Row", "postal_code": "ZZ1 1ZZ"},
        "date_of_birth": {"month": 4, "year": 1970}, "country_of_residence": "England",
        "natures_of_control": ["ownership-of-shares-75-to-100-percent"]}
    if nationality is not None:
        data["nationality"] = nationality
    return {"company_number": "00000001", "data": data}


def _psc_lines(*records: dict[str, Any] | str) -> bytes:
    return b"".join((r if isinstance(r, str) else json.dumps(r)).encode() + b"\n"
                    for r in records)


#: Part 1: a person, a person filed twice (two companies), a company, a
#: super-secure PSC with no name, a person with no nationality, and a
#: person whose name and boxes are all empty.
#: Part 2: the first person again, filed by another company, and an
#: overseas entity's beneficial owner.
_PSC_PARTS = {
    1: _psc_lines(_psc_person("Ann Lee"), _psc_person("Bo Wu"), _psc_person("Bo Wu"),
                  {"data": {"kind": "corporate-entity-person-with-significant-control",
                            "name": "Invented Holdings Ltd"}},
                  {"data": {"kind": "super-secure-person-with-significant-control"}},
                  _psc_person("Cy Doe", nationality=None),
                  _psc_person("", title="", forename="", surname="")),
    2: _psc_lines(_psc_person("Ann Lee"),
                  _psc_person("Dr Di Fox Roe", "Irish", "individual-beneficial-owner",
                              title="Dr", forename="Di", middle_name="Fox",
                              surname="Roe")),
}


def _psc_part(n: int, body: bytes, of: int = 2, day: str = _PSC_DAY,
              member: str | None = None) -> bytes:
    """Part `n` of `of` as the download serves it: a zip of one JSON-lines file."""
    out = io.BytesIO()
    with zipfile.ZipFile(out, "w") as archive:
        archive.writestr(member or f"psc-snapshot-{day}_{n}of{of}.txt", body)
    return out.getvalue()


def _psc_page(*files: str) -> bytes:
    return "".join(f'<a href="{f}">{f}</a> (74Mb)\n' for f in files).encode()


def _psc_files(of: int = 2, day: str = _PSC_DAY) -> list[str]:
    return [f"psc-snapshot-{day}_{n}of{of}.zip" for n in range(1, of + 1)]


def _serve_psc(monkeypatch: pytest.MonkeyPatch, tmp_path: Path,
               parts: dict[str, Answer], page: bytes | None = None) -> list[str]:
    """Answer the download page with `page` (every file in `parts`
    linked) and each part file with its answer: bytes to serve, or an
    exception to raise. Returns the file names downloaded."""
    monkeypatch.setenv("NAMEPARSER_TOOLS_CACHE", str(tmp_path))
    monkeypatch.setattr(core, "CHUNK", 64)  # several reads, not one
    monkeypatch.setattr(psc, "PSC_SAMPLE", 1)  # every record, unless a test samples
    page = _psc_page(*parts) if page is None else page
    asked: list[str] = []

    def urlopen(request: urllib.request.Request, timeout: int) -> _Response | _Download:
        url = request.full_url
        if url == psc.PSC_PAGE:
            return _Response(page)
        file = url.rsplit("/", 1)[1]
        asked.append(file)
        answer = parts.get(file)
        if isinstance(answer, Exception):
            raise answer
        if answer is None:
            pytest.fail(f"an unexpected download of {url}")
        return _Download(answer, len(answer))
    monkeypatch.setattr(urllib.request, "urlopen", urlopen)
    return asked


def _psc_snapshot(monkeypatch: pytest.MonkeyPatch, tmp_path: Path,
                  bodies: dict[int, bytes] = _PSC_PARTS, day: str = _PSC_DAY) -> list[str]:
    of = len(bodies)
    return _serve_psc(monkeypatch, tmp_path, {
        file: _psc_part(n, bodies[n], of, day)
        for n, file in enumerate(_psc_files(of, day), 1)})


def test_a_psc_listing_failing_once_is_retried(
        monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    _psc_snapshot(monkeypatch, tmp_path)
    failed = _failing_once(monkeypatch, psc.PSC_PAGE)
    day, parts = psc._psc_listing()
    assert (day, len(parts), failed) == (_PSC_DAY, len(_PSC_PARTS), [psc.PSC_PAGE])


def _gone(file: str) -> urllib.error.HTTPError:
    return urllib.error.HTTPError(f"{psc.PSC_PAGE}/{file}", 404, "Not Found",
                                  email.message.Message(), None)


def test_a_psc_fetch_keeps_each_filed_name_once_and_counts_the_rest(
        monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setattr(psc, "PSC_MAX_BAD", 1)  # a fixture of 9 lines
    asked = _psc_snapshot(monkeypatch, tmp_path)
    corpus = local.fetch(_PSC)
    assert asked == _psc_files()
    # In the order of their lines, whose keys are sorted: by forename.
    assert corpus.records == [
        {"name": "Mr Ann Lee", "title": "Mr", "forename": "Ann", "surname": "Lee",
         "nationality": "British"},
        {"name": "Mr Bo Wu", "title": "Mr", "forename": "Bo", "surname": "Wu",
         "nationality": "British"},
        {"name": "Mr Cy Doe", "title": "Mr", "forename": "Cy", "surname": "Doe"},
        {"name": "Dr Di Fox Roe", "title": "Dr", "forename": "Di", "middle_name": "Fox",
         "surname": "Roe", "nationality": "Irish"},
    ]
    assert corpus.meta["data_date"] == _PSC_DAY
    assert corpus.meta["detail"] == {
        "parts": 2, "sample": "1 in 1", "lines": 9, psc.PSC_KINDS[0]: 6, psc.PSC_KINDS[1]: 1,
        "records_of_other_kinds": 2, "individuals_without_a_nationality": 1,
        "sampled_names_that_are_empty": 1}
    assert corpus.header().endswith("4 filed names (local corpus psc-individuals)")


def test_a_psc_fetch_writes_no_field_but_the_name_its_boxes_and_the_nationality(
        monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    _psc_snapshot(monkeypatch, tmp_path)
    local.fetch(_PSC)
    folder = tmp_path / "local" / _PSC
    kept = set(psc.PSC_KEPT)
    for path in [folder / "raw.jsonl", *(folder / "parts").iterdir()]:
        text = (gzip.decompress(path.read_bytes()) if path.suffix == ".gz"
                else path.read_bytes()).decode()
        for leaked in ("Invented Row", "ZZ1", "1970", "England", "00000001",
                       "ownership", "Invented Holdings"):
            assert leaked not in text, (path.name, leaked)
        for line in text.splitlines():
            row = json.loads(line)
            assert "part" in row or set(row) <= kept, (path.name, row)


def test_a_psc_sample_keeps_the_same_records_whatever_part_files_them(
        monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    people = [_psc_person(f"Ann Lee{n}") for n in range(40)]
    _psc_snapshot(monkeypatch, tmp_path, {1: _psc_lines(*people[:25]),
                                          2: _psc_lines(*people[25:])})
    monkeypatch.setattr(psc, "PSC_SAMPLE", 4)
    corpus = local.fetch(_PSC)
    kept = corpus.records
    assert 0 < len(kept) < 20 and corpus.meta["detail"]["sample"] == "1 in 4"
    assert all(psc.psc_sampled(_extract_line(r)) for r in kept)
    # Filed by other parts, in another order, the same records are kept.
    _psc_snapshot(monkeypatch, tmp_path, {1: _psc_lines(*people[30:]),
                                          2: _psc_lines(*reversed(people[:30]))})
    monkeypatch.setattr(psc, "PSC_SAMPLE", 4)
    shutil.rmtree(tmp_path / "local" / _PSC / "parts")
    assert local.fetch(_PSC).records == kept
    # The control: with every record kept, all 40 are there.
    monkeypatch.setattr(psc, "PSC_SAMPLE", 1)
    assert len(local.fetch(_PSC).records) == 40


def _extract_line(record: dict[str, str]) -> str:
    """A record as its extract line, the text psc_sampled hashes."""
    return local.corpus_build.jsonl_line(record, sort_keys=True)


@pytest.mark.parametrize(("bad", "match"), [
    ({"data": {"kind": _PSC_PERSON, "name": "Mr Ann Lee"}},
     "1 of 2 individuals have no name_elements"),
    (_psc_person("Mr Ann  Lee", title="Mr", forename="Ann", surname="Lee"),
     "1 of 2 individuals' display names are not their four boxes joined"),
    ("{not json", "1 of 2 lines are not JSON"),
], ids=["no name_elements", "a name not its boxes joined", "a line not JSON"])
def test_a_psc_snapshot_whose_layout_has_changed_is_refused(
        monkeypatch: pytest.MonkeyPatch, tmp_path: Path,
        bad: dict[str, Any] | str, match: str) -> None:
    good = _psc_person("Bo Wu")
    _psc_snapshot(monkeypatch, tmp_path, {1: _psc_lines(bad, good)})
    with pytest.raises(ValueError, match=match):
        local.fetch(_PSC)
    assert local.load(_PSC) is None
    # The control: past the threshold the same snapshot is read, the bad
    # record counted and dropped, so the threshold is what refused it.
    monkeypatch.setattr(psc, "PSC_MAX_BAD", 1)
    assert [r["name"] for r in local.fetch(_PSC).records] == ["Mr Bo Wu"]


@pytest.mark.parametrize(("page", "match"), [
    (b"<p>The snapshot has moved.</p>", "links no snapshot parts"),
    (_psc_page(*_psc_files(3)[:2]), r"parts \[1, 2\] of \[3\]"),
    (_psc_page(_psc_files()[0], _psc_files(day="2026-10-23")[1]),
     r"dated \['2026-10-22', '2026-10-23'\]"),
], ids=["no parts", "a part missing", "parts of two days"])
def test_a_psc_page_that_lists_no_whole_snapshot_is_refused(
        monkeypatch: pytest.MonkeyPatch, tmp_path: Path, page: bytes, match: str) -> None:
    asked = _serve_psc(monkeypatch, tmp_path, {}, page)
    with pytest.raises(ValueError, match=match):
        local.fetch(_PSC)
    assert asked == []


def test_a_psc_part_gone_mid_fetch_is_refused_and_the_next_run_resumes(
        monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    files = _psc_files()
    parts: dict[str, Answer] = {files[0]: _psc_part(1, _PSC_PARTS[1]),
                                files[1]: _gone(files[1])}
    asked = _serve_psc(monkeypatch, tmp_path, parts)
    with pytest.raises(ValueError, match="replaced during the fetch; fetch again"):
        local.fetch(_PSC)
    folder = tmp_path / "local" / _PSC
    assert not (folder / "parts").exists()
    assert sorted(p.name for p in (folder / "parts.new").iterdir()) == [
        psc._extract_name(files[0])]
    parts[files[1]] = _psc_part(2, _PSC_PARTS[2])
    assert len(local.fetch(_PSC).records) == 4
    assert asked == [*files, files[1]]  # part 1 was not downloaded again
    assert not (folder / "parts.new").exists()


def test_a_resumed_psc_fetch_drops_what_another_day_left(
        monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    asked = _psc_snapshot(monkeypatch, tmp_path)
    staging = tmp_path / "local" / _PSC / "parts.new"
    staging.mkdir(parents=True)
    stale = staging / "psc-snapshot-2026-10-21_1of2.jsonl.gz"
    stale.write_bytes(gzip.compress(b'{"part": "yesterday", "counts": {}}\n'))
    (staging / "psc-snapshot-2026-10-22_2of2.zip.part").write_bytes(b"cut")
    assert len(local.fetch(_PSC).records) == 4
    assert asked == _psc_files()
    assert sorted(p.name for p in (tmp_path / "local" / _PSC / "parts").iterdir()) == [
        psc._extract_name(f) for f in _psc_files()]


def test_a_failed_psc_refresh_keeps_the_parts_and_the_corpus_it_had(
        monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    _psc_snapshot(monkeypatch, tmp_path)
    before = local.fetch(_PSC)
    newer = _psc_files(day="2026-10-23")
    cut = _psc_part(2, _PSC_PARTS[2], day="2026-10-23")
    _serve_psc(monkeypatch, tmp_path, {newer[0]: _psc_part(1, _PSC_PARTS[1], day="2026-10-23"),
                                       newer[1]: cut[:-10]})
    with pytest.raises(ValueError, match="fetch again"):
        local.main(["fetch", _PSC, "--refresh"])
    assert local.load(_PSC) == before
    assert sorted(p.name for p in (tmp_path / "local" / _PSC / "parts").iterdir()) == [
        psc._extract_name(f) for f in _psc_files()]
    # The control: the same refresh, whole, replaces both.
    _serve_psc(monkeypatch, tmp_path, {newer[0]: b"", newer[1]: cut})
    assert local.main(["fetch", _PSC, "--refresh"]) == 0
    after = local.load(_PSC)
    assert after is not None and after.meta["data_date"] == "2026-10-23"


def test_a_psc_cache_missing_a_part_is_refused_with_the_way_out(
        monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    _psc_snapshot(monkeypatch, tmp_path)
    local.fetch(_PSC)
    (tmp_path / "local" / _PSC / "parts" / psc._extract_name(_psc_files()[1])
     ).unlink()
    with pytest.raises(ValueError, match=r"holds parts \[1\] of \[2\].*--refresh"):
        local.fetch(_PSC)


@pytest.mark.parametrize(("body", "match"), [
    (b"not a zip at all", "is not a readable zip"),
    (_psc_part(1, _PSC_PARTS[1], of=1, member="renamed.txt"),
     "holds no psc-snapshot-2026-10-22_1of1.txt"),
], ids=["not a zip", "no member of its own name"])
def test_a_psc_part_that_cannot_be_read_is_refused(
        monkeypatch: pytest.MonkeyPatch, tmp_path: Path, body: bytes, match: str) -> None:
    _serve_psc(monkeypatch, tmp_path, {_psc_files(1)[0]: body})
    with pytest.raises(ValueError, match=match):
        local.fetch(_PSC)
    assert not list((tmp_path / "local" / _PSC / "parts.new").glob("*.zip*"))


def _plant(tmp_path: Path, day: str, bodies: dict[int, bytes] = _PSC_PARTS,
           folder: str = "parts") -> Path:
    """The extracts of a snapshot of `bodies` dated `day`, written into
    the cache's `folder` as renew_psc would write them; the folder."""
    where = tmp_path / "local" / _PSC / folder
    where.mkdir(parents=True, exist_ok=True)
    of = len(bodies)
    for n, file in enumerate(_psc_files(of, day), 1):
        zipped = tmp_path / file
        zipped.write_bytes(_psc_part(n, bodies[n], of, day))
        (where / psc._extract_name(file)).write_bytes(
            psc._psc_extract(zipped, file.replace(".zip", ".txt")))
    return where


def test_a_psc_cache_holding_parts_of_two_snapshots_is_refused_before_any_is_read(
        monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    _serve_psc(monkeypatch, tmp_path, {})  # no download is expected
    monkeypatch.setattr(psc, "PSC_MAX_BAD", 1)
    parts = _plant(tmp_path, _PSC_DAY)
    assert len(local.fetch(_PSC).records) == 4  # the control: one snapshot
    _plant(tmp_path, "2026-10-21")
    with pytest.raises(ValueError, match=r"holds part 1 twice.*--refresh"):
        local.fetch(_PSC)
    for path in parts.glob("*2026-10-21*"):
        path.unlink()
    (parts / psc._extract_name(_psc_files(day="2026-10-21")[1])).write_bytes(
        (parts / psc._extract_name(_psc_files()[1])).read_bytes())
    (parts / psc._extract_name(_psc_files()[1])).unlink()
    with pytest.raises(ValueError, match=r"dated \['2026-10-21', '2026-10-22'\]"):
        local.fetch(_PSC)


def test_a_psc_snapshot_whose_person_kind_was_renamed_is_refused(
        monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    people = [_psc_person(f"Ann Lee{n}", kind="individual-person-renamed") for n in range(9)]
    owner = _psc_person("Bo Wu", kind=psc.PSC_KINDS[1])
    _psc_snapshot(monkeypatch, tmp_path, {1: _psc_lines(*people, owner)})
    with pytest.raises(ValueError, match="1 of 10 lines are .* records: a kind"):
        local.fetch(_PSC)
    # The control: under the kind's own name, the same snapshot is read.
    monkeypatch.setattr(psc, "PSC_KINDS", ("individual-person-renamed", psc.PSC_KINDS[1]))
    shutil.rmtree(tmp_path / "local" / _PSC / "parts")
    assert len(local.fetch(_PSC).records) == 10


@pytest.mark.parametrize(("damage", "match"), [
    (lambda body: body[:-10], "is not an extract this tool wrote"),
    (lambda body: b"not gzip", "is not an extract this tool wrote"),
    (lambda body: gzip.compress(b"{not json\n"), "is not an extract this tool wrote"),
    (lambda body: gzip.compress(
        gzip.decompress(body).replace(b"_1of2.txt", b"_2of2.txt", 1)),
     "its header does not describe it"),
    (lambda body: gzip.compress(
        gzip.decompress(body).replace(b'"lines": 7', b'"lines": "7"', 1)),
     "its header does not describe it"),
], ids=["cut short", "not gzip", "header not JSON", "another part's header",
        "a count not a number"])
def test_a_damaged_psc_extract_is_refused_naming_the_refresh(
        monkeypatch: pytest.MonkeyPatch, tmp_path: Path,
        damage: Callable[[bytes], bytes], match: str) -> None:
    _serve_psc(monkeypatch, tmp_path, {})
    monkeypatch.setattr(psc, "PSC_MAX_BAD", 1)
    parts = _plant(tmp_path, _PSC_DAY)
    first = parts / psc._extract_name(_psc_files()[0])
    assert b'"lines": 7' in gzip.decompress(first.read_bytes())
    first.write_bytes(damage(first.read_bytes()))
    with pytest.raises(ValueError, match=f"{match}.*fetch {_PSC} --refresh"):
        local.fetch(_PSC)


def test_a_psc_extract_of_another_version_is_neither_read_nor_resumed(
        monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    asked = _psc_snapshot(monkeypatch, tmp_path)
    monkeypatch.setattr(psc, "PSC_EXTRACT_VERSION", 0)
    parts = _plant(tmp_path, _PSC_DAY)
    monkeypatch.setattr(psc, "PSC_EXTRACT_VERSION", 1)
    with pytest.raises(ValueError, match="is not an extract of version 1"):
        local.fetch(_PSC)
    # Staged for a resume, the old version's extracts are downloaded anew.
    os.replace(parts, parts.with_name("parts.new"))
    assert len(local.fetch(_PSC).records) == 4
    assert asked == _psc_files()


def test_a_psc_corpus_of_another_sample_is_refused_on_load(
        monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    _psc_snapshot(monkeypatch, tmp_path)
    local.fetch(_PSC)
    assert local.load(_PSC) is not None  # the control
    monkeypatch.setattr(psc, "PSC_SAMPLE", 8)
    with pytest.raises(ValueError, match=r"keeps 1 in 1 filed names.*keeps 1 in 8"
                                          f".*fetch {_PSC} --refresh"):
        local.load(_PSC)


def test_a_psc_page_linking_each_part_twice_is_one_snapshot(
        monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    files = _psc_files()
    _serve_psc(monkeypatch, tmp_path, {
        f: _psc_part(n, _PSC_PARTS[n]) for n, f in enumerate(files, 1)},
        page=_psc_page(*files, *files))
    assert len(local.fetch(_PSC).records) == 4


def test_a_psc_fetch_cut_off_between_its_two_renames_resumes_without_downloading(
        monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    asked = _serve_psc(monkeypatch, tmp_path, {}, _psc_page(*_psc_files()))  # any download fails
    _plant(tmp_path, "2026-10-21", folder="parts.old")
    _plant(tmp_path, _PSC_DAY, folder="parts.new")
    assert len(local.fetch(_PSC).records) == 4
    assert asked == []
    folder = tmp_path / "local" / _PSC
    assert sorted(p.name for p in folder.iterdir() if p.is_dir()) == ["parts"]


# -- load ----------------------------------------------------------------------

def _fetched(monkeypatch: pytest.MonkeyPatch, tmp_path: Path,
             *names: str, date: str = _DATE) -> Path:
    """A corpus of `names` fetched into tmp_path's cache, with no network
    behind it; its folder."""
    monkeypatch.setenv("NAMEPARSER_TOOLS_CACHE", str(tmp_path))
    records = [{"name": n} for n in names or ("Ann Lee, MD", "Bo Wu, PhD")]
    plant_corpus(monkeypatch, local, _SOURCE, records, date, "officials")
    return _folder(tmp_path)


def _rewrite_meta(folder: Path, **changes: object) -> None:
    meta = json.loads((folder / "meta.json").read_text())
    for key, value in changes.items():
        if value is None:
            del meta[key]
        else:
            meta[key] = value
    (folder / "meta.json").write_text(json.dumps(meta))


def test_a_raw_file_that_no_longer_matches_its_sha256_is_refused(
        monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    raw = _fetched(monkeypatch, tmp_path) / "raw.jsonl"
    raw.write_text("".join(raw.read_text().splitlines(keepends=True)[:-1]))
    with pytest.raises(ValueError, match="raw.jsonl does not match the sha256"):
        local.load(_SOURCE)


def test_a_corpus_file_that_no_longer_matches_its_sha256_is_refused(
        monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    # snapshot.py --local reads corpus.jsonl, not raw.jsonl: a truncated
    # one would record a smaller baseline that reads as a clean run.
    corpus = _fetched(monkeypatch, tmp_path) / "corpus.jsonl"
    corpus.write_text(corpus.read_text().splitlines(keepends=True)[0])
    with pytest.raises(ValueError, match="corpus.jsonl does not match the sha256"):
        local.load(_SOURCE)


@pytest.mark.parametrize(("changes", "match"), [
    ({"version": 1}, "not written by this version"),
    ({"sha256": None}, "no str 'sha256'"),
    ({"data_date": 3}, "no str 'data_date'"),
    ({"records": True}, "no int 'records'"),
], ids=["old version", "missing key", "wrong type", "bool for int"])
def test_a_meta_file_load_cannot_trust_is_refused_with_the_way_out(
        monkeypatch: pytest.MonkeyPatch, tmp_path: Path,
        changes: dict[str, object], match: str) -> None:
    _rewrite_meta(_fetched(monkeypatch, tmp_path), **changes)
    with pytest.raises(ValueError, match=match) as raised:
        local.load(_SOURCE)
    assert f"local_corpora.py fetch {_SOURCE} --refresh" in str(raised.value)


def test_a_meta_file_that_is_not_json_is_refused(
        monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    (_fetched(monkeypatch, tmp_path) / "meta.json").write_text("{")
    with pytest.raises(ValueError, match="is not JSON"):
        local.load(_SOURCE)


def test_a_name_holding_a_line_break_survives_the_round_trip(
        monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    # Pasted from a document: str.splitlines cuts at these, and written
    # raw they would make the corpus unloadable for good.
    names = ("Ann Lee, MD", "Bo Wu", "Cy\x85Doe, PhD", "Di Fox")
    folder = _fetched(monkeypatch, tmp_path, *names)
    loaded = local.load(_SOURCE)
    assert loaded is not None and [r["name"] for r in loaded.records] == list(names)
    lines = (folder / "corpus.jsonl").read_text(encoding="utf-8").splitlines()
    assert sorted(json.loads(line) for line in lines) == sorted(names)


# -- the command line ------------------------------------------------------------

def test_fetch_over_a_damaged_copy_fetches_again(
        monkeypatch: pytest.MonkeyPatch, tmp_path: Path,
        capsys: pytest.CaptureFixture[str]) -> None:
    # The way out every refusal names has to work: without this, a plain
    # `fetch` loaded the damaged copy first and raised the same refusal.
    _serve(monkeypatch, tmp_path, dates=(_DATE,) * 4)
    local.fetch(_SOURCE)
    (_folder(tmp_path) / "raw.jsonl").write_text("")
    assert local.main(["fetch", _SOURCE]) == 0
    captured = capsys.readouterr()
    assert "unusable, fetching again" in captured.err
    assert captured.out.startswith("ClinicalTrials.gov (NLM) study officials")
    assert local.load(_SOURCE) is not None


def test_fetch_uses_the_cached_copy_unless_asked_to_refresh(
        monkeypatch: pytest.MonkeyPatch, tmp_path: Path,
        capsys: pytest.CaptureFixture[str]) -> None:
    fetched = _serve(monkeypatch, tmp_path, dates=(_DATE,) * 4)
    assert local.main(["fetch", _SOURCE]) == 0
    assert local.main(["fetch", _SOURCE]) == 0
    assert "cached in" in capsys.readouterr().out
    assert len(fetched) == 4
    assert local.main(["fetch", _SOURCE, "--refresh"]) == 0
    assert len(fetched) == 8


def test_tally_reports_the_parts_after_commas_under_the_attribution(
        monkeypatch: pytest.MonkeyPatch, tmp_path: Path,
        capsys: pytest.CaptureFixture[str]) -> None:
    monkeypatch.setenv("NAMEPARSER_TOOLS_CACHE", str(tmp_path))
    with pytest.raises(SystemExit, match="is not fetched"):
        local.main(["tally", _SOURCE])
    _fetched(monkeypatch, tmp_path, "Ann Lee, MD", "Bo Wu, MD, PhD", "Cy Doe")
    assert local.main(["tally", _SOURCE, "--top", "1"]) == 0
    out = capsys.readouterr().out.splitlines()
    assert out[0].startswith(f"ClinicalTrials.gov (NLM) study officials, data as of {_DATE}")
    assert out[1].startswith("2 hold a comma")
    assert out[2:] == ["          2  MD"]


# -- the cached word index -------------------------------------------------------

def _looked_up(word: str = "MD") -> tuple[Any, Any]:
    """A fresh load of the corpus, and `word` looked up in it."""
    loaded = local.load(_SOURCE)
    assert loaded is not None
    return loaded, local.lookup(loaded, word)


def test_a_lookup_answered_from_the_cached_index_reads_no_records(
        monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    folder = _fetched(monkeypatch, tmp_path, "Ann Lee, MD", "Bo Wu, MD, PhD", "Cy Doe")
    first, built = _looked_up()
    assert "records" in vars(first) and (folder / local.INDEX).exists()
    again, cached = _looked_up()
    assert cached == built
    assert "records" not in vars(again)
    assert again.header() == first.header()


def test_the_cached_index_is_the_index_it_was_built_as(
        monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    _fetched(monkeypatch, tmp_path, "Ann Lee, M.D.", "MD Bo Wu", "Cy Doe, MD, PhD",
             "Pe\u00f1a, Jos\u00e9", "Ed Ng, md; MD")
    first, _ = _looked_up()
    built = local.word_index(first)
    again, _ = _looked_up()
    assert again.index == local.WordIndex(
        dict(built.anywhere), dict(built.after_comma),
        {k: dict(v) for k, v in built.spellings.items()})


def test_a_built_index_reads_a_missing_word_as_a_cached_one_does(
        monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    # A Counter answers 0 for a missing key where the cached dict raises:
    # a reader written against a built index would fail on a cached one.
    _fetched(monkeypatch, tmp_path, "Ann Lee, MD")
    built, _ = _looked_up()
    cached, _ = _looked_up()
    for index in (built.index, cached.index):
        with pytest.raises(KeyError):
            index.anywhere["absent"]  # noqa: B018
        with pytest.raises(KeyError):
            index.spellings["md"]["absent"]  # noqa: B018


def test_a_refetch_rebuilds_the_cached_index(
        monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    _fetched(monkeypatch, tmp_path, "Ann Lee, MD")
    _looked_up()
    _fetched(monkeypatch, tmp_path, "Ann Lee, MD", "Bo Wu, MD")
    _, found = _looked_up()
    assert found is not None and found.anywhere == 2


def test_the_cached_index_is_read_only_under_its_own_key(
        monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    # Doctored counts under the right key are served, which shows the
    # file is what answers; under another fold's key they are not.
    folder = _fetched(monkeypatch, tmp_path, "Ann Lee, MD")
    _looked_up()
    data = json.loads((folder / local.INDEX).read_text())
    data["anywhere"]["md"] = 99
    (folder / local.INDEX).write_text(json.dumps(data))
    _, found = _looked_up()
    assert found is not None and found.anywhere == 99
    monkeypatch.setattr(local, "fold_fingerprint", lambda: "another fold")
    _, found = _looked_up()
    assert found is not None and found.anywhere == 1


def _another(name: str) -> object:
    """A stand-in for one of the fold's functions or constants that
    differs from it."""
    value = getattr(local, name)
    if isinstance(value, re.Pattern):
        return re.compile(r"\s+")
    if isinstance(value, frozenset):
        return frozenset("'")
    return lambda *args: None


@pytest.mark.parametrize("change", [*local._FOLD_CODE, *local._FOLD_CONSTANTS])
def test_a_change_to_how_a_word_is_cut_or_folded_changes_the_key(
        monkeypatch: pytest.MonkeyPatch, change: str) -> None:
    before = local.fold_fingerprint()
    monkeypatch.setattr(local, change, _another(change))
    assert local.fold_fingerprint() != before


@pytest.mark.parametrize("reader", ["read_records", "corpus_build.jsonl_lines"])
def test_a_change_to_how_raw_jsonl_is_cut_into_records_changes_the_key(
        monkeypatch: pytest.MonkeyPatch, reader: str) -> None:
    # The index is built from Local.records, an attribute the fold's own
    # functions read without calling what fills it, so the walk in
    # test_the_fold_lists_everything_its_functions_call_and_read cannot
    # see these two; they are hashed by name.
    before = local.fold_fingerprint()
    owner = local.corpus_build if reader.startswith("corpus_build.") else local
    monkeypatch.setattr(owner, reader.rsplit(".", 1)[-1], lambda *args, **kwargs: [])
    assert local.fold_fingerprint() != before


def test_the_key_is_the_same_in_every_process() -> None:
    # A frozenset constant's iteration order moves with string hashing,
    # which differs per process: hashed unsorted, the key would too, and
    # no cache would ever be read twice.
    import subprocess
    import sys
    run = [sys.executable, "-c", "import sys; sys.path.insert(0, 'tools/differential'); "
           "import local_corpora; print(local_corpora.fold_fingerprint())"]
    keys = {subprocess.run(run, capture_output=True, text=True, check=True,
                           env={**__import__("os").environ, "PYTHONHASHSEED": seed},
                           cwd=Path(__file__).resolve().parents[2]).stdout
            for seed in ("1", "2", "3")}
    assert len(keys) == 1 and keys != {""}


def _globals_read(code: types.CodeType) -> set[str]:
    names = set(code.co_names)
    for const in code.co_consts:
        if isinstance(const, types.CodeType):
            names |= _globals_read(const)
    return names


def test_no_module_imports_a_sibling_constant() -> None:
    # A test patches a constant on the module that holds it (core.RETRIES,
    # tse.TSE_MAX_BAD), and every other reader reads it through that
    # module. A `from local_x import CONSTANT` would bind a second name a
    # patch on local_x cannot reach, and a test could pass with its guard
    # off. The modules are SOURCES' own, so a new source is covered. PSC and
    # JRC are sources' names, keys of SOURCES, and no fetch's setting.
    import ast
    sources = {source.fetch.__module__ for source in local.SOURCES.values()}
    assert sources == {m.__name__ for m in (ctgov, fec, tse, tw, ukec, psc, jrc, nepal)}
    siblings = {"local_corpora", "local_core", *sources}
    imported = {(path.stem, alias.name)
                for path in (Path(str(local.__file__)).parent / f"{s}.py"
                             for s in sorted(siblings))
                for node in ast.walk(ast.parse(path.read_text(encoding="utf-8")))
                if isinstance(node, ast.ImportFrom) and node.module in siblings
                for alias in node.names if alias.name.lstrip("_").isupper()}
    assert imported == {("local_corpora", "PSC"), ("local_corpora", "JRC")}


def test_the_fold_lists_everything_its_functions_call_and_read() -> None:
    # _FOLD_CODE is kept by hand: a helper the fold starts calling, or a
    # constant it starts reading, left off it, leaves the key unmoved by
    # a change to that helper.
    import inspect
    module = vars(local)
    read = set().union(*(_globals_read(inspect.unwrap(module[name]).__code__)
                         for name in local._FOLD_CODE))
    unlisted = set()
    for name in read & module.keys():
        value = module[name]
        if isinstance(value, types.ModuleType):
            continue
        if getattr(value, "__module__", None) != local.__name__ and not name.isupper() \
                and not name.startswith("_"):
            continue  # imported: Counter
        if name in (*local._FOLD_CODE, *local._FOLD_CONSTANTS, "WordIndex"):
            continue
        unlisted.add(name)
    assert unlisted == set()


@pytest.mark.parametrize("damage", ["{", "[]", '{"key": 1}'],
                         ids=["not JSON", "not an object", "no counts"])
def test_a_cached_index_that_cannot_be_read_is_built_over(
        monkeypatch: pytest.MonkeyPatch, tmp_path: Path, damage: str) -> None:
    folder = _fetched(monkeypatch, tmp_path, "Ann Lee, MD")
    (folder / local.INDEX).write_text(damage)
    _, found = _looked_up()
    assert found is not None and found.anywhere == 1
    assert json.loads((folder / local.INDEX).read_text())["anywhere"] == {
        "ann": 1, "lee": 1, "md": 1}


def test_a_corpus_not_read_from_the_cache_is_never_cached(_own_cache: Path) -> None:
    # A test's corpus has no sha256 to key an index on; cached under the
    # key "None", it would answer for the real corpus of that source. The
    # folder exists, as on a machine that fetched it, so a write would land.
    (_own_cache / "local" / _SOURCE).mkdir(parents=True)
    corpus: Any = _corpus("Ann Lee, MD")
    assert corpus.index.anywhere == {"ann": 1, "lee": 1, "md": 1}
    assert not list(_own_cache.rglob(local.INDEX))


def test_an_index_that_cannot_be_written_still_answers(
        monkeypatch: pytest.MonkeyPatch, tmp_path: Path,
        capsys: pytest.CaptureFixture[str]) -> None:
    _fetched(monkeypatch, tmp_path, "Ann Lee, MD")

    def refuse(path: Path, body: bytes) -> None:
        raise PermissionError(f"read-only: {path}")
    monkeypatch.setattr(local.corpus_build, "write_atomic", refuse)
    _, found = _looked_up()
    assert found is not None and found.anywhere == 1
    assert "could not cache the word index" in capsys.readouterr().err


def test_a_spaced_word_absent_from_the_cached_index_reads_no_records(
        monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    _fetched(monkeypatch, tmp_path, "Ann Lee, Ph. D.", "Bo Wu, PhD")
    _looked_up()
    loaded, found = _looked_up("Ph. Q.")
    assert found is not None and found.anywhere == 0
    assert "records" not in vars(loaded)
    loaded, found = _looked_up("Ph. D.")
    assert found is not None and (found.anywhere, found.joined) == (1, 1)


@pytest.mark.parametrize("damage", [
    {"anywhere": {"md": "1"}}, {"anywhere": {"md": True}}, {"anywhere": {"md": None}},
    {"after_comma": []}, {"spellings": {"md": 5}}, {"spellings": {"md": {"MD": "1"}}},
], ids=["a count as text", "a count as a bool", "no count", "counts as a list",
        "spellings as a number", "a spelling count as text"])
def test_an_index_under_its_own_key_with_counts_that_are_not_counts_is_built_over(
        monkeypatch: pytest.MonkeyPatch, tmp_path: Path,
        damage: dict[str, Any], capsys: pytest.CaptureFixture[str]) -> None:
    folder = _fetched(monkeypatch, tmp_path, "Ann Lee, MD")
    _looked_up()
    data = json.loads((folder / local.INDEX).read_text())
    (folder / local.INDEX).write_text(json.dumps({**data, **damage}))
    _, found = _looked_up()
    assert found is not None and (found.anywhere, found.spellings) == (1, {"MD": 1})
    assert "rebuilding the word index" in capsys.readouterr().err


def test_tally_over_damaged_records_exits_naming_the_fetch(
        monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    # load() no longer parses the records, so their damage first shows
    # in tally, which must exit as require() does, not with a traceback.
    folder = _fetched(monkeypatch, tmp_path)
    raw = b'{"nom": "Ann Lee, MD"}\n'
    (folder / "raw.jsonl").write_bytes(raw)
    _rewrite_meta(folder, sha256=hashlib.sha256(raw).hexdigest())
    with pytest.raises(SystemExit, match=f"record without a name.*fetch {_SOURCE} --refresh"):
        local.main(["tally", _SOURCE])


@pytest.mark.parametrize(("raw", "match"), [
    (b'{"nom": "Ann Lee, MD"}\n', "record without a name"),
    (b'{"name": "Ann Lee, MD"\n', "a line that is not JSON"),
], ids=["a record without a name", "a line that is not JSON"])
def test_a_damaged_record_fails_when_the_records_are_read(
        monkeypatch: pytest.MonkeyPatch, tmp_path: Path, raw: bytes, match: str) -> None:
    # With the sha256 rewritten to match, only the record checks see it,
    # and each must raise CorpusDamaged, which name_usage's per-row guard
    # catches, not the bare ValueError a JSON error is.
    folder = _fetched(monkeypatch, tmp_path)
    (folder / "raw.jsonl").write_bytes(raw)
    _rewrite_meta(folder, sha256=hashlib.sha256(raw).hexdigest())
    loaded = local.load(_SOURCE)
    assert loaded is not None
    with pytest.raises(local.CorpusDamaged, match=match):
        loaded.records  # noqa: B018


# -- views -------------------------------------------------------------------------

def _corpus(*names: str) -> object:
    return local.Local(_SOURCE, {"data_date": _DATE}, [{"name": n} for n in names])


def test_the_tally_counts_each_part_after_a_comma_once_per_record() -> None:
    parts, with_comma = local.tally(_corpus(
        "Ann Lee, MD, PhD", "Bo Wu,MD", "Cy Doe MD", "Di Fox, MD, MD"))
    assert with_comma == 3
    assert parts == {"MD": 3, "PhD": 1}


def test_a_comma_inside_parentheses_cuts_a_part_unlike_the_parser() -> None:
    # The docstring's stated limit: the parser sets the bracketed nickname
    # aside first, this view does not.
    assert local.after_commas("Ann (Lee, Jr) Roe, MD") == ["Jr) Roe", "MD"]


def test_a_word_is_counted_anywhere_and_after_a_comma_ignoring_case_and_periods() -> None:
    index = local.word_index(_corpus(
        "Ann Lee, M.D.", "MD Bo Wu", "Cy Doe, md, MD", "Dr. Ma Li, (Psychiatry)"))
    assert (index.anywhere.get("md", 0), index.after_comma.get("md", 0)) == (3, 2)
    assert (index.anywhere.get("psychiatry", 0), index.after_comma.get("psychiatry", 0)) == (1, 1)
    assert (index.anywhere.get("ma", 0), index.after_comma.get("ma", 0)) == (1, 0)


@pytest.mark.parametrize("name", [
    "Bob Ray, MD/PhD", "Bob Ray, MD;", "Bob Ray, MD; PhD", "Bob Ray, (MD)",
    "Bob Ray, “MD”", "Bob Ray, [MD]:"])
def test_a_word_is_found_beside_any_punctuation(name: str) -> None:
    # Cut only at spaces and commas, 'MD/PhD' and 'MD;' were words of
    # their own, and a lookup of MD read zero: 3,698 officials' names
    # held a slash and 548 a semicolon on 2026-10-21.
    index = local.word_index(_corpus(name))
    assert (index.anywhere.get("md", 0), index.after_comma.get("md", 0)) == (1, 1)


@pytest.mark.parametrize(("word", "other"), [
    ("d'", "D"), ("d’", "D"), ("al-", "Al"),
    ("शर्मा", "शर्म"), ("محمدٌ", "محمد")])
def test_a_word_keeps_what_tells_it_from_another(word: str, other: str) -> None:
    # The first edge fold stripped apostrophes, hyphens and combining
    # marks: d' answered as the initial D (5,954 officials, 2026-10-21),
    # al- as Al, and a final vowel sign or haraka was lost.
    assert local.word_key(word) != local.word_key(other)
    index = local.word_index(_corpus(f"Ann {other} Lee"))
    assert index.anywhere.get(local.word_key(word), 0) == 0


def test_a_decomposed_letter_finds_its_composed_twin() -> None:
    index = local.word_index(_corpus(unicodedata.normalize("NFD", "Ana Žic, MD")))
    assert index.anywhere.get(local.word_key("Žic"), 0) == 1


def test_spellings_are_counted_once_per_record() -> None:
    # Two records, one writing MD twice: a spelling count above the
    # record count read as more officials than wrote the word.
    index = local.word_index(_corpus("Di Fox, MD, MD", "Ed Ng, MD"))
    assert index.anywhere.get("md", 0) == 2
    assert index.spellings["md"] == {"MD": 2}


def test_a_spaced_word_is_matched_as_its_words_in_a_row() -> None:
    # 'Ed Ph, D' runs across the comma, starting before it: written, not
    # after a comma. 'Di Fox, PhD' is the joined spelling, not the phrase.
    # 'Fy Ph D, Ph D' writes it on both sides: after a comma too.
    corpus = _corpus("Ann Lee, Ph. D.", "Bo Wu, Ph D, MD", "Ph D Cy", "Di Fox, PhD",
                     "Ed Ph, D", "Fy Ph D, Ph D")
    assert local.words("Ph. D.") == ["ph", "d"]
    assert local.phrase_counts(corpus, ["ph", "d"]) == (5, 3)


def test_a_phrase_with_a_word_written_nowhere_scans_nothing(
        monkeypatch: pytest.MonkeyPatch) -> None:
    corpus: Any = _corpus("Ann Lee, MD")
    corpus.index  # noqa: B018 -- built before the scan is forbidden

    def scanned(local_: object) -> object:
        raise AssertionError("scanned every name for a word no name holds")
    monkeypatch.setattr(local, "_names", scanned)
    assert local.phrase_counts(corpus, ["md", "zz"]) == (0, 0)


# -- pairs -------------------------------------------------------------------------

#: One invented pair of each shape, in PAIR_SHAPES's order.
_PAIRS = [
    ("ANA SOUZA", "ANA SOUZA", "the same"),
    ("ANA SOUZA", "", "no reference name"),
    ("--", "ANA SOUZA", "no filed name"),
    ("Ana Souza", "ANA SOUZA", "case only"),
    ("JOSE LIMA", "JOSÉ LIMA", "accents only"),
    ("Jose Lima", "JOSÉ LIMA", "case and accents"),
    ("ANA  SOUZA-LIMA", "ANA SOUZA LIMA", "punctuation or spacing only"),
    ("SOUZA ANA", "ANA SOUZA", "the same words reordered"),
    ("ANA SILVA", "ANA DA SILVA", "words left out"),
    ("ANA DA SILVA", "ANA SILVA", "words added"),
    ("ANA M SILVA", "ANA MARIA SILVA", "words shortened"),
    ("ANA SOUSA", "ANA SOUZA", "words misspelled"),
    ("ANA M SOUZA", "ANA MARIA DA SOUZA", "words left out and shortened"),
    ("ANA SOUZA RIBEIRO", "ANA SOUZA CAMPOS", "mostly the same words"),
    ("BIA COSTA", "ANA SOUZA", "few words in common"),
]


def test_each_pair_shape_has_a_pair() -> None:
    assert [shape for _, _, shape in _PAIRS] == list(local.PAIR_SHAPES)


@pytest.mark.parametrize(("filed", "reference", "shape"), _PAIRS,
                         ids=[shape for _, _, shape in _PAIRS])
def test_a_pair_takes_the_first_shape_it_fits(filed: str, reference: str, shape: str) -> None:
    assert local.pair_shape(filed, reference) == shape


@pytest.mark.parametrize(("filed", "reference", "shape"), [
    # An accent and a word left out: not accents only.
    ("JOSE SILVA", "JOSÉ DA SILVA", "words left out"),
    # Two words misspelled is the most a misspelling takes.
    ("ANA SOUSA RIBERO", "ANA SOUZA RIBEIRO", "words misspelled"),
    # Three, and no word left in common.
    ("ANNA SOUSA RIBERO", "ANA SOUZA RIBEIRO", "few words in common"),
    # A word too unlike its counterpart is not a misspelling: 0.75 is,
    # 0.727 is not.
    ("ANA SOUZA", "ANA SANTOS", "mostly the same words"),
    ("ANA LIMA", "ANA LIMO", "words misspelled"),
    ("ANA ROCHA", "ANA ROSHAN", "mostly the same words"),
    # A word both shortened and alike enough to be misspelled: shortened.
    ("ANA SOUZ", "ANA SOUZA", "words shortened"),
    # Two words run together are spacing, not a word changed.
    ("ANA SOUZALIMA", "ANA SOUZA LIMA", "punctuation or spacing only"),
    # Mostly the same words: all but one of the shorter name's words,
    # and at least one word.
    ("ANA SOUZA", "ANA LIMA COSTA RIBEIRO", "mostly the same words"),
    ("ANA", "BIA", "few words in common"),
    # Left out and shortened keeps the order: out of order, mostly.
    ("SOUZA A", "ANA SOUZA", "mostly the same words"),
], ids=["accent and a word", "two misspelled", "three misspelled", "unlike",
        "alike at the limit", "alike under the limit", "shortened before misspelled",
        "run together", "mostly, the shorter name's words", "one word each",
        "shortened out of order"])
def test_a_pair_s_shape_at_its_edges(filed: str, reference: str, shape: str) -> None:
    assert local.pair_shape(filed, reference) == shape


def _paired(*pairs: tuple[str, str]) -> object:
    return local.Local("tse-donors", {"data_date": _DATE},
                       [{"name": a, "registry": b} for a, b in pairs])


def test_the_pairs_view_counts_shapes_and_the_words_left_out_and_added() -> None:
    # A pair leaving DE out twice counts DE once, and a pair leaving out
    # one of its two DEs counts it too.
    found = local.pair_counts(_paired(*[(a, b) for a, b, _ in _PAIRS],
                                      ("BO WU", "BO DE WU"), ("CY LIMA", "CY DA LIMA"),
                                      ("DI LUZ", "DI DE LUZ DE MELO"),
                                      ("EVA DE LUZ", "EVA DE LUZ DE MELO")))
    assert found.total == len(_PAIRS) + 4
    assert found.shapes["words left out"] == 5
    assert found.left_out == {"DA": 2, "DE": 3, "MELO": 2}
    assert found.added == {"DA": 1}
    assert found.agreement is None


def test_the_pairs_view_lists_only_words_many_pairs_share() -> None:
    # A word left out of nine pairs could be one family's: not listed.
    found = local.pair_counts(_paired(*[("ANA SILVA", "ANA DA SILVA")] * 10,
                                      *[("BO WU", "BO NOVAIS WU")] * 9,
                                      *[("CY DO LIMA", "CY LIMA")] * 10,
                                      ("EVA LIMA", "EVA LIMA")))
    report = local.format_pairs(found, top=15)
    assert "words most often left out: DA 10\n" in report + "\n"
    assert "NOVAIS" not in report
    assert "words most often added: DO 10" in report
    assert "30 pairs; 1 the same, 29 differing:" in report
    assert "         19   65.5%  words left out" in report  # a share of those differing


def test_the_pairs_view_lists_the_top_words_asked_for() -> None:
    found = local.pair_counts(_paired(*[("ANA SILVA", "ANA DA SILVA")] * 11,
                                      *[("BO WU", "BO DE WU")] * 10))
    assert "left out: DA 11\n" in local.format_pairs(found, top=1) + "\n"
    assert "left out: DA 11, DE 10" in local.format_pairs(found, top=2)


def test_the_pairs_view_counts_the_pairs_whose_spellings_share_a_surname() -> None:
    # Two readings with no surname (one word each) share none; a pair
    # with no reference name is not parsed.
    found = local.pair_counts(_paired(
        ("ANA SILVA", "ANA DA SILVA"), ("ANA M SILVA", "ANA MARIA SILVA"),
        ("PEDRO ALVES FH", "PEDRO ALVES FILHO"), ("ANA SOUZA", "ANA SOUZA"),
        ("ANA", "ANNA"), ("BO WU", "")),
        agreement=True)
    # FH is too unlike FILHO to be its misspelling, and both read as the
    # agnomen since #843 listed the abbreviation, so the pair shares ALVES.
    assert found.agreement == {"words left out": (1, 1), "words shortened": (1, 1),
                               "mostly the same words": (1, 1),
                               "words misspelled": (0, 1)}
    report = local.format_pairs(found, top=15)
    assert "(one surname in 0%)" in report
    assert "  no reference name\n" in report  # with no agreement beside it


def test_the_pairs_view_lists_the_accents_only_pairs_read_with_two_surnames() -> None:
    # RA is a credential and RÁ is not, so the readings part; JÚNIOR and
    # JUNIOR are both suffixes (#843), and the accent on JOSÉ moves
    # nothing. Fewer than ten: not listed.
    found = local.pair_counts(_paired(*[("ANA SILVA RÁ", "ANA SILVA RA")] * 10,
                                      *[("JOSE SILVA JÚNIOR", "JOSÉ SILVA JUNIOR")] * 10,
                                      *[("JOSE SILVA", "JOSÉ SILVA")] * 10,
                                      *[("JOSE SILVA MÁ", "JOSÉ SILVA MA")] * 9),
                              agreement=True)
    assert found.agreement == {"accents only": (20, 39)}
    assert found.accent_splits == {"RÁ / RA": 10, "MÁ / MA": 9}
    report = local.format_pairs(found, top=15)
    assert ("accents-only pairs read with two surnames, by their last words: "
            "RÁ / RA 10") in report
    assert "MÁ / MA" not in report


def test_the_pairs_view_refuses_a_source_with_no_reference_name(
        monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    _fetched(monkeypatch, tmp_path)
    with pytest.raises(SystemExit, match="carry no reference name"):
        local.main(["pairs", _SOURCE])


@pytest.mark.parametrize(("records", "match"), [
    ([], "holds no records"),
    ([{"name": "ANA", "registry": "ANA"}, {"name": "BO"}], "carry no reference name"),
], ids=["no records", "one record without"])
def test_the_pairs_view_refuses_records_it_cannot_pair(
        records: list[dict[str, str]], match: str) -> None:
    with pytest.raises(ValueError, match=match):
        local.pair_counts(local.Local("tse-donors", {"data_date": _DATE}, records))


def test_the_pairs_command_reports_a_fetched_corpus(
        cdn: _Cdn, capsys: pytest.CaptureFixture[str]) -> None:
    local.fetch(_TSE)
    capsys.readouterr()
    assert local.main(["pairs", _TSE]) == 0
    out = capsys.readouterr().out
    assert out.startswith("TSE (Tribunal Superior Eleitoral)")
    assert "6 pairs; 1 the same, 5 differing:" in out
    assert "one surname" not in out
    assert local.main(["pairs", _TSE, "--agreement"]) == 0
    assert "(one surname in" in capsys.readouterr().out


# -- snapshot.py --local -----------------------------------------------------------

def test_snapshot_reads_a_local_corpus_against_its_own_snapshot(
        monkeypatch: pytest.MonkeyPatch, tmp_path: Path,
        capsys: pytest.CaptureFixture[str]) -> None:
    _fetched(monkeypatch, tmp_path)
    with pytest.raises(SystemExit, match="no snapshot"):
        snapshot.main(["--local", _SOURCE])
    assert snapshot.main(["--local", _SOURCE, "--record"]) == 0
    recorded = _folder(tmp_path) / "snapshot.jsonl"
    assert snapshot.row_count(recorded.read_text()) == 2
    assert snapshot.main(["--local", _SOURCE]) == 0
    assert "matches the snapshot" in capsys.readouterr().out

    # A reading that moved, as a change to the parser would move it.
    header, *rows = recorded.read_text().splitlines()
    row = json.loads(rows[0])
    row["family"] = "Moved"
    recorded.write_text("\n".join([header, json.dumps(row)] + rows[1:]) + "\n")
    assert snapshot.main(["--local", _SOURCE]) == 1
    out = capsys.readouterr().out
    assert out.startswith("ClinicalTrials.gov (NLM) study officials, data as of")
    assert "Moved" in out and "1 entries differ" in out
    # The committed corpora's tail would tell the reader to re-record the
    # COMMITTED snapshot, from the committed corpora.
    assert f"--local {_SOURCE} --record --tree" in out
    assert snapshot.RECORD_COMMAND not in out and "corpus_cldr" not in out


def test_snapshot_refuses_a_corpus_fetched_after_its_snapshot(
        monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    # Fetched again, the registry has gained and lost names; compared
    # with the old snapshot they would read as the parser's moves.
    _fetched(monkeypatch, tmp_path)
    assert snapshot.main(["--local", _SOURCE, "--record"]) == 0
    _fetched(monkeypatch, tmp_path, "Eve Moe, DO", date="2026-10-22T09:00:04")
    with pytest.raises(SystemExit, match="recorded from another fetch") as raised:
        snapshot.main(["--local", _SOURCE])
    assert _DATE in str(raised.value) and "2026-10-22T09:00:04" in str(raised.value)
    assert snapshot.main(["--local", _SOURCE, "--record"]) == 0
    assert snapshot.main(["--local", _SOURCE]) == 0


def test_snapshot_records_a_local_snapshot_where_out_says(
        monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    _fetched(monkeypatch, tmp_path)
    out = tmp_path / "elsewhere.jsonl"
    assert snapshot.main(["--local", _SOURCE, "--record", "--out", str(out)]) == 0
    assert snapshot.row_count(out.read_text()) == 2
    assert json.loads((tmp_path / "elsewhere.jsonl.source.json").read_text())[
        "data_date"] == _DATE
    assert not (_folder(tmp_path) / "snapshot.jsonl").exists()


def test_snapshot_refuses_a_damaged_local_corpus_with_the_way_out(
        monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    (_fetched(monkeypatch, tmp_path) / "corpus.jsonl").write_text("")
    with pytest.raises(SystemExit, match="--refresh"):
        snapshot.main(["--local", _SOURCE, "--record"])


def test_snapshot_refuses_a_local_corpus_not_fetched(
        monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setenv("NAMEPARSER_TOOLS_CACHE", str(tmp_path))
    with pytest.raises(SystemExit, match="not fetched"):
        snapshot.main(["--local", _SOURCE])


def test_snapshot_refuses_since_with_local(
        monkeypatch: pytest.MonkeyPatch, tmp_path: Path,
        capsys: pytest.CaptureFixture[str]) -> None:
    # Fetched first: on an empty cache the not-fetched refusal answered
    # for this row, and the --since guard could go unnoticed.
    _fetched(monkeypatch, tmp_path)
    with pytest.raises(SystemExit) as raised:
        snapshot.main(["--local", _SOURCE, "--since", "v2.5.0"])
    assert raised.value.code == 2
    assert "--since reads a committed snapshot" in capsys.readouterr().err


def test_snapshot_reads_a_local_name_holding_a_line_break(
        monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    # The first fix escaped the cache's files; snapshot.py's own dump and
    # load still wrote the parsed name raw and cut it at the break.
    _fetched(monkeypatch, tmp_path, "Cy\x85Doe, PhD", "Ann\u2028Lee, MD", "Bo Wu")
    assert snapshot.main(["--local", _SOURCE, "--record"]) == 0
    assert snapshot.main(["--local", _SOURCE]) == 0


@pytest.mark.parametrize("sidecar", ["{", "[]", None], ids=["not json", "not a dict", "missing"])
def test_snapshot_refuses_a_snapshot_with_no_readable_fetch_before_reading_names(
        monkeypatch: pytest.MonkeyPatch, tmp_path: Path, sidecar: str | None) -> None:
    folder = _fetched(monkeypatch, tmp_path)
    assert snapshot.main(["--local", _SOURCE, "--record"]) == 0
    record = folder / "snapshot.jsonl.source.json"
    if sidecar is None:
        record.unlink()
    else:
        record.write_text(sidecar)

    def unread(entries: object) -> list[dict[str, Any]]:
        raise AssertionError("parsed every name before refusing")
    monkeypatch.setattr(snapshot, "read", unread)
    with pytest.raises(SystemExit, match="recorded from another fetch"):
        snapshot.main(["--local", _SOURCE])


def _unread(*args: object, **kwargs: object) -> list[dict[str, Any]]:
    raise AssertionError("parsed the names")


def test_snapshot_refuses_a_check_with_no_snapshot_before_reading_names(
        monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    _fetched(monkeypatch, tmp_path)
    monkeypatch.setattr(snapshot, "read", _unread)
    with pytest.raises(SystemExit, match="no snapshot"):
        snapshot.main(["--local", _SOURCE])


def test_a_local_snapshot_does_not_read_the_facade(
        monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    # A name the facade reads otherwise: the committed snapshot records
    # its facade, a local one does not.
    folder = _fetched(monkeypatch, tmp_path, "Ph. D., John")
    assert "facade" in snapshot.read([("Ph. D., John", None)])[0]
    assert snapshot.main(["--local", _SOURCE, "--record"]) == 0
    assert not any("facade" in r for r in snapshot.load(
        (folder / "snapshot.jsonl").read_text()).values())


def test_a_local_snapshot_recorded_with_the_facade_compares_without_it(
        monkeypatch: pytest.MonkeyPatch, tmp_path: Path,
        capsys: pytest.CaptureFixture[str]) -> None:
    folder = _fetched(monkeypatch, tmp_path)
    assert snapshot.main(["--local", _SOURCE, "--record"]) == 0
    recorded = folder / "snapshot.jsonl"
    rows = [json.loads(r) for r in recorded.read_text().splitlines()]
    rows[1]["facade"] = {"last": "Elsewhere"}  # rows[0] is the header
    recorded.write_text("".join(json.dumps(r) + "\n" for r in rows))
    capsys.readouterr()
    assert snapshot.main(["--local", _SOURCE]) == 0
    assert "not compared: facade" in capsys.readouterr().out


_MANY = tuple(f"Ann Lee{i}, MD" for i in range(40))


def test_a_sample_reads_against_a_snapshot_of_its_own(
        monkeypatch: pytest.MonkeyPatch, tmp_path: Path,
        capsys: pytest.CaptureFixture[str]) -> None:
    folder = _fetched(monkeypatch, tmp_path, *_MANY)
    assert snapshot.main(["--local", _SOURCE, "--record", "--sample", "3"]) == 0
    kept = snapshot.load((folder / "snapshot.sample-3.jsonl").read_text())
    assert 0 < len(kept) < len(_MANY)
    assert not (folder / "snapshot.jsonl").exists()
    capsys.readouterr()
    assert snapshot.main(["--local", _SOURCE, "--sample", "3"]) == 0
    assert f"a 1-in-3 sample: {len(kept)} of {len(_MANY)} entries" in capsys.readouterr().out
    with pytest.raises(SystemExit, match="no snapshot"):
        snapshot.main(["--local", _SOURCE])


def test_a_sample_is_never_compared_with_a_snapshot_of_another(
        monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    folder = _fetched(monkeypatch, tmp_path, *_MANY)
    whole = str(folder / "snapshot.jsonl")
    assert snapshot.main(["--local", _SOURCE, "--record", "--sample", "3", "--out", whole]) == 0
    with pytest.raises(SystemExit, match="recorded from a 1-in-3 sample"):
        snapshot.main(["--local", _SOURCE])


@pytest.mark.parametrize("argv", [["--sample", "3"], ["--local", _SOURCE, "--sample", "1"]],
                         ids=["without --local", "N below 2"])
def test_snapshot_refuses_a_sample_it_cannot_take(
        monkeypatch: pytest.MonkeyPatch, tmp_path: Path, argv: list[str]) -> None:
    _fetched(monkeypatch, tmp_path)
    with pytest.raises(SystemExit) as raised:
        snapshot.main(argv)
    assert raised.value.code == 2


def test_a_local_recording_and_check_run_in_workers(
        monkeypatch: pytest.MonkeyPatch, tmp_path: Path,
        capsys: pytest.CaptureFixture[str]) -> None:
    # The wiring only main assembles: spawned workers importing this
    # file by name, reading the names main gave them.
    folder = _fetched(monkeypatch, tmp_path, *_MANY)
    monkeypatch.setattr(snapshot, "PARALLEL_FLOOR", 1)
    assert snapshot.main(["--local", _SOURCE, "--record", "--jobs", "2"]) == 0
    serial = list(snapshot.load((folder / "snapshot.jsonl").read_text()).values())
    assert serial == snapshot.read([(n, None) for n in sorted(_MANY)], facade=False)
    capsys.readouterr()
    assert snapshot.main(["--local", _SOURCE, "--jobs", "2"]) == 0
    assert "matches the snapshot" in capsys.readouterr().out


def _digest(monkeypatch: pytest.MonkeyPatch, *values: str) -> None:
    """snapshot._source_digest answering `values` in turn, then the last."""
    answers = list(values)
    monkeypatch.setattr(snapshot, "_source_digest",
                        lambda root: answers.pop(0) if len(answers) > 1 else answers[0])


def _baselines(folder: Path) -> list[Path]:
    return sorted((folder / "baselines").glob("*.jsonl.gz"))


def test_a_recording_is_reused_for_the_same_package_and_fetch(
        monkeypatch: pytest.MonkeyPatch, tmp_path: Path,
        capsys: pytest.CaptureFixture[str]) -> None:
    folder = _fetched(monkeypatch, tmp_path)
    _digest(monkeypatch, "a" * 64)
    assert snapshot.main(["--local", _SOURCE, "--record"]) == 0
    recorded = (folder / "snapshot.jsonl").read_text()
    assert len(_baselines(folder)) == 1
    (folder / "snapshot.jsonl").unlink()
    (folder / "snapshot.jsonl.source.json").unlink()
    real_read = snapshot.read
    monkeypatch.setattr(snapshot, "read", _unread)
    capsys.readouterr()
    assert snapshot.main(["--local", _SOURCE, "--record"]) == 0
    assert "copied from" in capsys.readouterr().out
    assert (folder / "snapshot.jsonl").read_text() == recorded
    # The copy wrote its fetch record too, so a check can read against it.
    monkeypatch.setattr(snapshot, "read", real_read)
    assert snapshot.main(["--local", _SOURCE]) == 0


def test_a_recording_is_not_reused_for_another_package_sample_or_fetch(
        monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    _fetched(monkeypatch, tmp_path)
    _digest(monkeypatch, "a" * 64)
    assert snapshot.main(["--local", _SOURCE, "--record"]) == 0
    monkeypatch.setattr(snapshot, "read", _unread)
    _digest(monkeypatch, "b" * 64)
    with pytest.raises(AssertionError, match="parsed the names"):
        snapshot.main(["--local", _SOURCE, "--record"])
    _digest(monkeypatch, "a" * 64)
    with pytest.raises(AssertionError, match="parsed the names"):
        snapshot.main(["--local", _SOURCE, "--record", "--sample", "2"])
    _fetched(monkeypatch, tmp_path, "Eve Moe, DO")
    with pytest.raises(AssertionError, match="parsed the names"):
        snapshot.main(["--local", _SOURCE, "--record"])


def test_the_baseline_key_is_taken_from_the_tree_that_is_read(
        monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    # Keyed by the checkout running the tool instead of --tree's, a base
    # recorded after the branch would copy the branch's readings, and
    # the check would report no moves.
    _fetched(monkeypatch, tmp_path)
    base = (tmp_path / "base").resolve()
    asked: list[Path] = []

    def digest(root: Path) -> str:
        asked.append(root)
        return ("b" if root == base else "a") * 64
    monkeypatch.setattr(snapshot, "_source_digest", digest)
    assert snapshot.main(["--local", _SOURCE, "--record"]) == 0
    monkeypatch.setattr(snapshot, "read", _unread)
    with pytest.raises(AssertionError, match="parsed the names"):
        snapshot.main(["--local", _SOURCE, "--record", "--tree", str(base)])
    assert asked[-1] == base


def test_a_package_that_changes_during_the_read_keeps_no_baseline(
        monkeypatch: pytest.MonkeyPatch, tmp_path: Path,
        capsys: pytest.CaptureFixture[str]) -> None:
    folder = _fetched(monkeypatch, tmp_path)
    _digest(monkeypatch, "a" * 64, "b" * 64)
    assert snapshot.main(["--local", _SOURCE, "--record"]) == 0
    assert "changed while it was read" in capsys.readouterr().out
    assert (folder / "snapshot.jsonl").exists() and not _baselines(folder)


@pytest.mark.parametrize("damage", ["truncated", "corrupt", "short", "empty"])
def test_a_damaged_baseline_is_deleted_and_the_names_read(
        monkeypatch: pytest.MonkeyPatch, tmp_path: Path,
        capsys: pytest.CaptureFixture[str], damage: str) -> None:
    folder = _fetched(monkeypatch, tmp_path)
    _digest(monkeypatch, "a" * 64)
    assert snapshot.main(["--local", _SOURCE, "--record"]) == 0
    recorded = (folder / "snapshot.jsonl").read_text()
    [kept] = _baselines(folder)
    if damage == "truncated":
        kept.write_bytes(kept.read_bytes()[:-12])
    elif damage == "corrupt":
        # The first deflate byte, past the 10-byte header the keep
        # writes: a bad block header raises zlib.error, not an OSError.
        data = bytearray(kept.read_bytes())
        data[10] ^= 0xFF
        kept.write_bytes(bytes(data))
    else:
        with gzip.open(kept, "wt", encoding="utf-8") as f:
            f.write(recorded.splitlines(keepends=True)[0] if damage == "short" else "")
    capsys.readouterr()
    assert snapshot.main(["--local", _SOURCE, "--record"]) == 0
    out = capsys.readouterr().out
    assert "deleted the kept baseline" in out and "copied from" not in out
    assert (folder / "snapshot.jsonl").read_text() == recorded
    [rewritten] = _baselines(folder)
    with gzip.open(rewritten, "rt", encoding="utf-8") as f:
        assert f.read() == recorded


def test_a_baseline_that_cannot_be_kept_leaves_the_recording(
        monkeypatch: pytest.MonkeyPatch, tmp_path: Path,
        capsys: pytest.CaptureFixture[str]) -> None:
    folder = _fetched(monkeypatch, tmp_path)
    _digest(monkeypatch, "a" * 64)

    def full(fd: int) -> None:
        raise OSError(28, "No space left on device")
    monkeypatch.setattr(snapshot.os, "fsync", full)
    assert snapshot.main(["--local", _SOURCE, "--record"]) == 0
    out = capsys.readouterr().out
    assert "baseline was not kept" in out and "recorded 2 readings" in out
    assert (folder / "snapshot.jsonl").exists() and not _baselines(folder)


def test_the_least_recently_used_baselines_and_stale_partials_are_dropped(
        monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    folder = _fetched(monkeypatch, tmp_path)
    monkeypatch.setattr(snapshot, "BASELINES_KEPT", 2)
    (folder / "baselines").mkdir()
    stale = folder / "baselines" / "x.jsonl.gz.1.partial"
    fresh = folder / "baselines" / "y.jsonl.gz.2.partial"
    stale.write_text("")
    fresh.write_text("")
    os.utime(stale, (1_000_000, 1_000_000))
    for i, tree in enumerate("abc"):
        _digest(monkeypatch, tree * 64)
        assert snapshot.main(["--local", _SOURCE, "--record"]) == 0
        [new] = [p for p in _baselines(folder) if f"-{tree * 16}-" in p.name]
        os.utime(new, (2_000_000 + i, 2_000_000 + i))
    kept = [p.name for p in _baselines(folder)]
    assert len(kept) == 2 and not any(f"-{'a' * 16}-" in k for k in kept)
    assert not stale.exists() and fresh.exists()


def test_the_source_digest_is_the_package_as_it_is_on_disk(tmp_path: Path) -> None:
    import shutil as sh
    one, two = tmp_path / "one", tmp_path / "two"
    for root in (one, two):
        (root / "nameparser").mkdir(parents=True)
        (root / "nameparser" / "a.py").write_text("x = 1\n")
    assert snapshot._source_digest(one) == snapshot._source_digest(two)
    first = snapshot._source_digest(one)
    (one / "nameparser" / "__pycache__").mkdir()
    (one / "nameparser" / "__pycache__" / "a.cpython-311.pyc").write_bytes(b"x")
    assert snapshot._source_digest(one) == first  # bytecode caches aside
    for change in ("edited", "added", "renamed"):
        sh.rmtree(two)
        (two / "nameparser").mkdir(parents=True)
        files = {"edited": {"a.py": "x = 2\n"},
                 "added": {"a.py": "x = 1\n", "b.pyc": "sourceless"},
                 "renamed": {"b.py": "x = 1\n"}}[change]
        for name, body in files.items():
            (two / "nameparser" / name).write_text(body)
        assert snapshot._source_digest(two) != first, change


def test_the_source_digest_follows_a_symlinked_subpackage(tmp_path: Path) -> None:
    # The import follows the link, so the digest must read through it.
    digests: list[str] = []
    for target in ("x = 1\n", "x = 2\n"):
        root = tmp_path / f"tree{len(digests)}"
        (root / "real" / "sub").mkdir(parents=True)
        (root / "real" / "sub" / "m.py").write_text(target)
        (root / "nameparser").mkdir()
        (root / "nameparser" / "sub").symlink_to(root / "real" / "sub")
        digests.append(snapshot._source_digest(root))
    assert digests[0] != digests[1]


# -- snapshot.py --local --base -------------------------------------------------

def _shared(folder: Path) -> dict[str, tuple[int, bytes]]:
    """The shared snapshot's files beside a local corpus, as mtime and
    bytes, for a check that --base left them alone."""
    return {p.name: (p.stat().st_mtime_ns, p.read_bytes())
            for p in sorted(folder.glob("snapshot*"))}


def test_a_base_check_reports_a_change_planted_in_the_base_and_none_across_a_copy(
        monkeypatch: pytest.MonkeyPatch, tmp_path: Path,
        capsys: pytest.CaptureFixture[str]) -> None:
    # The harness must be able to report a difference: a base read from
    # the head's tree by mistake would show no move across a planted one.
    folder = _fetched(monkeypatch, tmp_path)
    planted = checkout_copy(tmp_path / "planted", planted=True)
    assert snapshot.main(["--local", _SOURCE, "--base", str(planted)]) == 1
    out = capsys.readouterr().out
    assert f"base: {planted.resolve()}, nameparser/ " in out and "recorded it now" in out
    assert "2 entries differ from the base" in out
    # The control: an unplanted copy is the head's package byte for byte.
    copy = checkout_copy(tmp_path / "copy")
    assert snapshot.main(["--local", _SOURCE, "--base", str(copy)]) == 0
    out = capsys.readouterr().out
    assert "matches the base" in out and "byte-identical" in out
    assert len(_baselines(folder)) == 2


def test_a_base_check_never_touches_the_shared_snapshot(
        monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    folder = _fetched(monkeypatch, tmp_path)
    base = checkout_copy(tmp_path / "base", planted=True)
    assert snapshot.main(["--local", _SOURCE, "--base", str(base)]) == 1
    assert not _shared(folder)  # none was there, and none was written
    assert snapshot.main(["--local", _SOURCE, "--record"]) == 0
    before = _shared(folder)
    assert set(before) == {"snapshot.jsonl", "snapshot.jsonl.source.json"}
    # A shared snapshot that would read as a move, ignored by --base.
    (folder / "snapshot.jsonl").write_text("")
    before = _shared(folder)
    copy = checkout_copy(tmp_path / "copy")
    assert snapshot.main(["--local", _SOURCE, "--base", str(copy)]) == 0
    assert snapshot.main(["--local", _SOURCE, "--base", str(copy), "--sample", "2"]) == 0
    assert _shared(folder) == before
    assert not list((folder / "baselines").glob(".base-*"))  # the child's scratch is gone


def test_a_kept_base_is_reused_without_reading_it_again(
        monkeypatch: pytest.MonkeyPatch, tmp_path: Path,
        capsys: pytest.CaptureFixture[str]) -> None:
    _fetched(monkeypatch, tmp_path)
    base = checkout_copy(tmp_path / "base", planted=True)
    assert snapshot.main(["--local", _SOURCE, "--base", str(base)]) == 1
    capsys.readouterr()

    def unrecorded(*args: object) -> None:
        raise AssertionError("recorded the base again")
    monkeypatch.setattr(snapshot, "_record_base", unrecorded)
    assert snapshot.main(["--local", _SOURCE, "--base", str(base)]) == 1
    out = capsys.readouterr().out
    assert "reused the kept baseline" in out and "2 entries differ" in out
    # An edit to the base keys it as another package, read again.
    (base / "nameparser" / "_edited.py").write_text("")
    with pytest.raises(AssertionError, match="recorded the base again"):
        snapshot.main(["--local", _SOURCE, "--base", str(base)])


def test_a_base_check_composes_with_a_sample(
        monkeypatch: pytest.MonkeyPatch, tmp_path: Path,
        capsys: pytest.CaptureFixture[str]) -> None:
    folder = _fetched(monkeypatch, tmp_path, *(f"Ann Lee{n}, MD" for n in range(12)))
    base = checkout_copy(tmp_path / "base", planted=True)
    assert snapshot.main(["--local", _SOURCE, "--base", str(base), "--sample", "2"]) == 1
    out = capsys.readouterr().out
    held = int(re.search(r"a 1-in-2 sample: (\d+) of 12 entries", out)[1])  # type: ignore[index]
    assert 0 < held < 12 and f"{held} entries differ from the base" in out
    [kept] = _baselines(folder)
    assert kept.name.endswith("-sample-2.jsonl.gz")


def test_a_base_that_is_the_tree_read_or_no_checkout_is_refused(
        monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    _fetched(monkeypatch, tmp_path)
    with pytest.raises(SystemExit, match="is the tree being read"):
        snapshot.main(["--local", _SOURCE, "--base", str(snapshot.REPO_ROOT)])
    other = checkout_copy(tmp_path / "other")
    with pytest.raises(SystemExit, match="is the tree being read"):
        snapshot.main(["--local", _SOURCE, "--base", str(other), "--tree", str(other)])
    with pytest.raises(SystemExit, match="no nameparser package"):
        snapshot.main(["--local", _SOURCE, "--base", str(tmp_path / "empty")])
    assert not _baselines(_folder(tmp_path))


def test_a_base_whose_import_fails_is_refused_with_the_childs_output(
        monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    _fetched(monkeypatch, tmp_path)
    base = checkout_copy(tmp_path / "base")
    with open(base / "nameparser" / "__init__.py", "a", encoding="utf-8") as f:
        f.write("\nraise ImportError('planted')\n")
    with pytest.raises(SystemExit, match="(?s)recording the base .* failed.*planted"):
        snapshot.main(["--local", _SOURCE, "--base", str(base)])
    assert not _baselines(_folder(tmp_path))


def test_a_base_child_is_started_without_the_import_path_overrides(
        monkeypatch: pytest.MonkeyPatch) -> None:
    # A unit check, not an end-to-end one: --tree's sys.path entry already
    # outranks a PYTHONPATH entry in the child, so no decoy can show the
    # strip; it is kept as compare.py's worker keeps it, against an
    # import made before the insert.
    monkeypatch.setenv("PYTHONPATH", "/decoy")
    monkeypatch.setenv("PYTHONHOME", "/decoy")
    env = snapshot.child_env()
    assert "PYTHONPATH" not in env and "PYTHONHOME" not in env and env


def test_a_kept_baseline_another_run_pruned_is_read_as_none_kept(
        monkeypatch: pytest.MonkeyPatch, tmp_path: Path,
        capsys: pytest.CaptureFixture[str]) -> None:
    # Pruned between a lookup and the open, it is not damage to delete:
    # read as damage, its unlink raised on the file already gone.
    kept = tmp_path / "gone.jsonl.gz"
    with gzip.open(kept, "wt", encoding="utf-8") as f:
        f.write("{}\n{}\n")
    real_open = gzip.open

    def pruned_first(path: Path, mode: str, encoding: str) -> object:
        Path(path).unlink()
        return real_open(path, mode, encoding=encoding)
    monkeypatch.setattr(snapshot.gzip, "open", pruned_first)
    assert snapshot._reused(kept, 2) is None
    assert "deleted the kept baseline" not in capsys.readouterr().out


def test_a_scratch_folder_a_killed_run_left_is_swept_once_stale(tmp_path: Path) -> None:
    stale, fresh = snapshot.scratch(tmp_path), snapshot.scratch(tmp_path)
    (stale / "base.jsonl").write_text("x\n")
    os.utime(stale, (1_000_000, 1_000_000))
    snapshot._prune(tmp_path)
    assert not stale.exists() and fresh.exists()


@pytest.mark.parametrize("extra", [["--record"], ["--out", "x.jsonl"]])
def test_a_base_check_refuses_to_record(
        monkeypatch: pytest.MonkeyPatch, tmp_path: Path,
        capsys: pytest.CaptureFixture[str], extra: list[str]) -> None:
    _fetched(monkeypatch, tmp_path)
    with pytest.raises(SystemExit) as raised:
        snapshot.main(["--local", _SOURCE, "--base", str(tmp_path), *extra])
    assert raised.value.code == 2 and "--base compares" in capsys.readouterr().err


def test_a_base_check_needs_a_local_corpus(capsys: pytest.CaptureFixture[str]) -> None:
    with pytest.raises(SystemExit) as raised:
        snapshot.main(["--base", "."])
    assert raised.value.code == 2 and "--base reads a local corpus" in capsys.readouterr().err


def test_a_baseline_another_run_pruned_is_not_reported_as_unkept(
        monkeypatch: pytest.MonkeyPatch, tmp_path: Path,
        capsys: pytest.CaptureFixture[str]) -> None:
    _fetched(monkeypatch, tmp_path)
    _digest(monkeypatch, "a" * 64)
    real_mtime = snapshot._mtime

    def vanished(path: Path) -> float | None:
        path.unlink()
        return real_mtime(path)
    monkeypatch.setattr(snapshot, "_mtime", vanished)
    assert snapshot.main(["--local", _SOURCE, "--record"]) == 0
    assert "not kept" not in capsys.readouterr().out


# -- the views in workers, and alike against a base ----------------------------------

#: Two pairs that read alike and one that does not (a title on one side).
_NEPAL_RECORDS = [{"name": "Ram Thapa", "devanagari": "राम थापा"},
                  {"name": "Sita Kumari Rai", "devanagari": "सीता कुमारी राई"},
                  {"name": "Dr Hari Shrestha", "devanagari": "हरि श्रेष्ठ"}]


def _spelled(*spellings: tuple[str, str]) -> object:
    """A jrc-names corpus holding each (entity, name) of `spellings`."""
    return local.Local(local.JRC, {}, [{"entity": e, "name": n, "script": "Latin"}
                                       for e, n in spellings])


def _by_name_snapshot() -> types.ModuleType:
    """The snapshot module local_corpora imports by its bare name, whose
    PARALLEL_FLOOR decides whether a view reads in workers."""
    return importlib.import_module("snapshot")


def _nepal(monkeypatch: pytest.MonkeyPatch, records: list[dict[str, str]] = _NEPAL_RECORDS
           ) -> None:
    # The election pinned as the real source pins it: a --base child
    # loads the corpus under the real Source and its check.
    plant_corpus(monkeypatch, local, _NEPAL, records, "2026-10-24", "name pairs",
                 {"election": importlib.import_module("local_nepal").NEPAL_ELECTION})


def test_each_source_that_pairs_spellings_has_an_alike_kind() -> None:
    entity = _spelled(("1", "Ann Lee"), ("1", "Анна Ли"))
    assert local.alike_kind(entity) == "entity"
    assert local.alike_kind(local.Local(_NEPAL, {}, _NEPAL_RECORDS)) == "devanagari"
    assert local.alike_kind(_paired(("ANA SILVA", "ANA DA SILVA"))) == "registry"
    with pytest.raises(local.Ungroupable, match="pair no two spellings"):
        local.alike_kind(local.Local(_SOURCE, {}, [{"name": "Ann Lee"}]))


def test_alike_reads_each_kind_of_pair() -> None:
    # A person read alike and one read apart, of each kind; a person
    # spelled once and a pair spelled the same are no one's to count.
    entity = local.alike_flags(_spelled(("1", "Ann Lee"), ("1", "Анна Ли"),
                                        ("2", "Dr. Bo Wu"), ("2", "Bo Wu"), ("3", "Cy Fox")))
    assert entity == {"1": True, "2": False}
    assert local.alike_flags(local.Local(_NEPAL, {}, _NEPAL_RECORDS)) == {
        "0": True, "1": True, "2": False}
    registry = local.alike_flags(_paired(("ANA SILVA", "ANA DA SILVA"),
                                         ("ANA SILVA", "ANA SOUZA"), ("BO WU", "BO WU"),
                                         ("CY FOX", "")))
    assert registry == {"0": True, "1": False}
    # A pair with no second spelling is no one's to count, either way.
    blank = local.alike_flags(local.Local(_NEPAL, {}, [*_NEPAL_RECORDS,
                                                       {"name": "Ram Rai", "devanagari": " "}]))
    assert set(blank) == {"0", "1", "2"}


def test_the_views_read_in_workers_as_they_read_in_process(
        monkeypatch: pytest.MonkeyPatch) -> None:
    grouped = _spelled(("1", "Ann Lee"), ("1", "Анна Ли"), ("2", "Dr. Bo Wu"), ("2", "Bo Wu"))
    paired = _paired(("ANA SILVA", "ANA DA SILVA"), ("ANA SILVA", "ANA SOUZA"),
                     ("JOSÉ SILVA RÁ", "JOSE SILVA RA"))
    nepal = local.Local(_NEPAL, {}, _NEPAL_RECORDS)
    serial = (local.group_counts(grouped), local.pair_counts(paired, agreement=True),
              local.alike_flags(grouped), local.alike_flags(paired), local.alike_flags(nepal))
    monkeypatch.setattr(_by_name_snapshot(), "PARALLEL_FLOOR", 1)
    assert (local.group_counts(grouped, jobs=2), local.pair_counts(paired, agreement=True, jobs=2),
            local.alike_flags(grouped, jobs=2), local.alike_flags(paired, jobs=2),
            local.alike_flags(nepal, jobs=2)) == serial


def test_a_view_whose_worker_read_another_nameparser_aborts(
        monkeypatch: pytest.MonkeyPatch) -> None:
    # The negative control for snapshot.parallel's check, through a view:
    # the workers import the real package, so a parent that believes it
    # imported another sees every chunk come back from elsewhere.
    import nameparser
    monkeypatch.setattr(_by_name_snapshot(), "PARALLEL_FLOOR", 1)
    monkeypatch.setattr(nameparser, "__file__", "/elsewhere/nameparser/__init__.py")
    with pytest.raises(SystemExit, match="a worker imported nameparser from"):
        local.alike_flags(local.Local(_NEPAL, {}, _NEPAL_RECORDS), jobs=2)


def _alike_kept(cache: Path) -> list[Path]:
    return sorted((cache / "local" / _NEPAL / local.ALIKE_KEPT).glob("*.json"))


def test_alike_against_a_planted_base_reports_moves_and_none_across_a_copy(
        monkeypatch: pytest.MonkeyPatch, _own_cache: Path, tmp_path: Path,
        capsys: pytest.CaptureFixture[str]) -> None:
    # The harness must be able to report a difference: a base read with
    # the head's tree by mistake would show no move across a planted one.
    _nepal(monkeypatch)
    planted = checkout_copy(tmp_path / "planted", planted=True)
    assert local.main(["alike", _NEPAL, "--base", str(planted)]) == 1
    out = capsys.readouterr().out
    assert f"base: {planted.resolve()}, nameparser/ " in out and "read it now" in out
    assert "2 of 3 pairs read alike" in out
    assert "0 pairs now alike, 0 now apart" not in out
    for record in _NEPAL_RECORDS:  # counts only
        assert record["name"] not in out and record["devanagari"] not in out
    copy = checkout_copy(tmp_path / "copy")
    assert local.main(["alike", _NEPAL, "--base", str(copy)]) == 0
    out = capsys.readouterr().out
    assert "0 pairs now alike, 0 now apart" in out and "byte-identical" in out
    assert len(_alike_kept(_own_cache)) == 2


def test_a_kept_base_is_reused_and_a_damaged_one_read_again(
        monkeypatch: pytest.MonkeyPatch, _own_cache: Path, tmp_path: Path,
        capsys: pytest.CaptureFixture[str]) -> None:
    _nepal(monkeypatch)
    base = checkout_copy(tmp_path / "base", planted=True)
    assert local.main(["alike", _NEPAL, "--base", str(base)]) == 1
    [kept] = _alike_kept(_own_cache)
    recorded = kept.read_bytes()
    capsys.readouterr()
    real = local._alike_base

    def unread(*args: object) -> None:
        raise AssertionError("read the base again")
    monkeypatch.setattr(local, "_alike_base", unread)
    assert local.main(["alike", _NEPAL, "--base", str(base)]) == 1
    assert "reused the kept flags" in capsys.readouterr().out
    body = json.loads(recorded)
    for damage in ("not json", json.dumps({**body, "count": body["count"] + 1}),
                   json.dumps({**body, "flags": {k: 1 for k in body["flags"]}}),
                   json.dumps({**body, "flags": list(body["flags"])}),
                   json.dumps({**body, "raw_sha256": "0" * 64}),
                   json.dumps({**body, "code": "another"})):
        kept.write_text(damage)
        with pytest.raises(AssertionError, match="read the base again"):
            local.main(["alike", _NEPAL, "--base", str(base)])
        assert "deleted the kept flags" in capsys.readouterr().out
        monkeypatch.setattr(local, "_alike_base", real)
        assert local.main(["alike", _NEPAL, "--base", str(base)]) == 1
        assert kept.read_bytes() == recorded
        assert not list(kept.parent.glob(".base-*"))  # the child's scratch is gone
        monkeypatch.setattr(local, "_alike_base", unread)


def test_a_base_that_changed_while_it_was_read_keeps_no_flags(
        monkeypatch: pytest.MonkeyPatch, _own_cache: Path, tmp_path: Path) -> None:
    _nepal(monkeypatch)
    base = checkout_copy(tmp_path / "base", planted=True)
    answers = ["a" * 64, "b" * 64]
    published: list[bool] = []

    def digest(root: Path) -> str:
        if not answers:
            return "c" * 64
        if len(answers) == 1:  # the check after the read: nothing kept yet
            published.append(bool(_alike_kept(_own_cache)))
        return answers.pop(0)
    monkeypatch.setattr(_by_name_snapshot(), "_source_digest", digest)
    with pytest.raises(SystemExit, match="changed while it was read"):
        local.main(["alike", _NEPAL, "--base", str(base)])
    assert published == [False]
    assert not _alike_kept(_own_cache)
    assert not list((_own_cache / "local" / _NEPAL / local.ALIKE_KEPT).glob(".base-*"))


def test_alike_refuses_a_tree_it_did_not_import_and_a_base_with_no_package(
        monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    _nepal(monkeypatch)
    monkeypatch.setattr(sys, "path", list(sys.path))  # --tree puts the tree on it
    with pytest.raises(SystemExit, match="not from the source package"):
        local.main(["alike", _NEPAL, "--tree", str(tmp_path)])
    with pytest.raises(SystemExit, match="no nameparser package"):
        local.main(["alike", _NEPAL, "--base", str(tmp_path)])


def test_an_alike_base_whose_import_fails_is_refused_with_the_childs_output(
        monkeypatch: pytest.MonkeyPatch, _own_cache: Path, tmp_path: Path) -> None:
    _nepal(monkeypatch)
    base = checkout_copy(tmp_path / "base")
    with open(base / "nameparser" / "__init__.py", "a", encoding="utf-8") as f:
        f.write("\nraise ImportError('planted')\n")
    with pytest.raises(SystemExit, match="(?s)reading the base .* failed.*planted"):
        local.main(["alike", _NEPAL, "--base", str(base)])
    assert not _alike_kept(_own_cache)




def test_the_alike_key_lists_everything_its_functions_call_and_read() -> None:
    # _ALIKE_CODE is kept by hand, as _FOLD_CODE is: a helper the view
    # starts calling left off it leaves a kept base's key unmoved by a
    # change to that helper, and the base reads as the old code read it.
    import inspect
    module = vars(local)
    read = set().union(*(_globals_read(inspect.unwrap(module[name]).__code__)
                         for name in local._ALIKE_CODE))
    unlisted = set()
    for name in read & module.keys():
        value = module[name]
        if isinstance(value, types.ModuleType) or name.startswith("__"):
            continue
        if getattr(value, "__module__", None) != local.__name__ and not name.isupper() \
                and not name.startswith("_"):
            continue  # imported: Counter
        if name in (*local._ALIKE_CODE, *local._ALIKE_CONSTANTS, "Reading", "_Read",
                    "Ungroupable"):
            continue
        unlisted.add(name)
    assert unlisted == set()


@pytest.mark.parametrize("change", [*local._ALIKE_CODE, *local._ALIKE_CONSTANTS])
def test_each_thing_the_alike_key_lists_moves_it(monkeypatch: pytest.MonkeyPatch,
                                                 change: str) -> None:
    before = local.alike_fingerprint()
    monkeypatch.setattr(local, change, _another(change))
    assert local.alike_fingerprint() != before


def test_alike_against_a_base_counts_each_direction_apart() -> None:
    nepal = local.Local(_NEPAL, {}, _NEPAL_RECORDS)
    assert local.format_alike(nepal, {"0": True, "1": True}, {"0": False, "1": True}) == [
        "2 of 2 pairs read alike (1 in the base)", "1 pairs now alike, 0 now apart"]
    assert local.format_alike(nepal, {"0": False, "1": True}, {"0": True, "1": True}) == [
        "1 of 2 pairs read alike (2 in the base)", "0 pairs now alike, 1 now apart"]
    assert local.format_alike(nepal, {"0": True}) == ["1 of 1 pairs read alike"]
    with pytest.raises(SystemExit, match="other persons"):
        local.format_alike(nepal, {"0": True, "1": True}, {"0": True})
