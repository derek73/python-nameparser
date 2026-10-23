"""Offline checks on tools/differential/local_corpora.py.

A local corpus is fetched once from a live source and then trusted as
the pin, so what these pin is the fetch's refusals (a fetch straddling
the source's daily refresh, a fetch cut short or paging a study twice,
a fetch with no names), the load's refusal of anything fetch() did not
write, the retries a long run needs, and the views' counting. The
failure that matters is a SMALLER corpus passing for the whole one: its
counts read as real zeros. The network is a stub answering by URL.
"""
import csv
import email.message
import hashlib
import http.client
import io
import json
import re
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

from ._differential_fixtures import _Response, load_tool

local = load_tool("local_corpora")
snapshot = load_tool("snapshot")

_SOURCE = "ctgov-officials"
_DATE = "2026-10-21T09:00:05"


@pytest.fixture(autouse=True)
def _own_cache(monkeypatch: pytest.MonkeyPatch, tmp_path_factory: pytest.TempPathFactory) -> Path:
    """Every test's cache is its own: a test that forgets to set one, or a
    guard that stops keeping a test's corpus out of the cache, writes
    into a scratch folder rather than the developer's real cache."""
    path = tmp_path_factory.mktemp("cache")
    monkeypatch.setenv("NAMEPARSER_TOOLS_CACHE", str(path))
    return path


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
    assert sum("studies" in u for u in fetched) == local.CTGOV_RETRIES


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
    monkeypatch.setattr(local, "FEC_CHUNK", 64)  # several reads, not one
    return tmp_path / "local" / _FEC / local.FEC_ZIP


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
    monkeypatch.setattr(local, "FEC_MAX_BAD", 1)  # a fixture of 7 lines
    corpus = local.fetch(_FEC)
    assert corpus.records == [{"name": "LEE, ANN"}, {"name": "PEÑA, JOSÉ"},
                              {"name": "ROE JR, BOB MR"}]
    assert corpus.meta["data_date"] == "2026-10-18T16:17:00"
    assert corpus.meta["detail"] == {
        "cycle": local.FEC_CYCLE, "file": f"{local.FEC_ZIP}/itcont.txt",
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
    monkeypatch.setattr(local, "FEC_MAX_BAD", 1)
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
    monkeypatch.setattr(local, "FEC_MAX_BAD", 1)
    _fec_zip(path)
    newer = _fec_zip(tmp_path / "newer.zip", _fec_body([_fec_row("IND", "WU, BO")]),
                     date=(2026, 10, 25, 9, 0, 0))
    asked = _serve_fec(monkeypatch, _Download(newer, len(newer)))
    assert local.main(["fetch", _FEC]) == 0
    assert asked == []
    assert local.main(["fetch", _FEC, "--refresh"]) == 0
    assert asked == [local.FEC_URL]
    corpus = local.load(_FEC)
    assert corpus is not None and corpus.records == [{"name": "WU, BO"}]
    assert corpus.meta["data_date"] == "2026-10-25T09:00:00"


def test_a_failed_fec_refresh_keeps_the_zip_and_the_corpus_it_had(
        monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    path = _fec_cache(monkeypatch, tmp_path)
    monkeypatch.setattr(local, "FEC_MAX_BAD", 1)
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
    monkeypatch.setattr(local, "FEC_MAX_BAD", 1)
    local.fetch(_FEC)
    monkeypatch.setattr(local, "FEC_CYCLE", "2028")
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


_PF = local.TSE_INDIVIDUALS
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


def _tse_zip(year: str, member: bytes | None = None,
             name: str | None = None) -> bytes:
    """A candidates' zip holding the national member and a state member
    whose one donor the national member lacks: a fetch reading the state
    member would gain a name."""
    member = _tse_csv(_TSE_ROWS[year]) if member is None else member
    out = io.BytesIO()
    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as archive:
        archive.writestr(zipfile.ZipInfo(f"receitas_candidatos_{year}_BA.csv",
                                         _TSE_STAMPS[year]),
                         _tse_csv([_tse_row(_PF, "SO NO ESTADO", "")]))
        archive.writestr(zipfile.ZipInfo(name or f"receitas_candidatos_{year}_BRASIL.csv",
                                         _TSE_STAMPS[year]), member)
    return out.getvalue()


def _url(year: str) -> str:
    return str(local.TSE_URL.format(year=year))


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
    """The CDN: HEAD states each zip's length, ETag and byte ranges, and
    a Range request with a matching If-Range is answered in part with
    its Content-Range, any other whole, as a server answers for a file
    replaced since the HEAD."""

    def __init__(self, zips: dict[str, bytes]) -> None:
        self.zips = {_url(y): body for y, body in zips.items()}
        self.etag = '"v1"'
        self.head: dict[str, str] | None = None  # headers replacing HEAD's
        self.head_etag: str | None = None  # the ETag HEAD states, "" for none
        self.last_modified = ""  # the Last-Modified HEAD states, if any
        self.head_failures: list[Exception] = []  # raised by the next HEADs
        self.failures: list[Exception] = []  # raised by the next range requests
        self.short = 0  # range answers to cut a byte short
        self.long = False  # range answers to send a byte past the range
        self.content_range: str | None = None  # a Content-Range replacing the true one
        self.replace_after: int | None = None  # range requests before a new ETag
        self.ranges = 0

    def urlopen(self, request: urllib.request.Request, timeout: int) -> _Answer:
        body = self.zips[request.full_url]
        if request.get_method() == "HEAD":
            if self.head_failures:
                raise self.head_failures.pop(0)
            if self.head is not None:
                return _Answer(200, b"", self.head)
            etag = self.etag if self.head_etag is None else self.head_etag
            return _Answer(200, b"", {"Content-Length": str(len(body)),
                                      "Accept-Ranges": "bytes",
                                      **({"ETag": etag} if etag else {}),
                                      **({"Last-Modified": self.last_modified}
                                         if self.last_modified else {})})
        self.ranges += 1
        if self.replace_after is not None and self.ranges > self.replace_after:
            self.etag = '"v2"'
        if self.failures:
            raise self.failures.pop(0)
        if request.get_header("If-range") != self.etag:
            return _Answer(200, body, {})
        start, end = map(int, str(request.get_header("Range"))[len("bytes="):].split("-"))
        part = body[start:end + 1]
        if self.short:
            self.short -= 1
            part = part[:-1]
        if self.long:
            part += b"!"
        return _Answer(206, part, {"Content-Range": self.content_range
                                   or f"bytes {start}-{end}/{len(body)}"})


@pytest.fixture
def cdn(monkeypatch: pytest.MonkeyPatch) -> _Cdn:
    served = _Cdn({year: _tse_zip(year) for year in local.TSE_ELECTIONS})
    monkeypatch.setattr(urllib.request, "urlopen", served.urlopen)
    monkeypatch.setattr(local, "TSE_BLOCK", 256)  # many ranges, not one
    # A fixture of 15 rows holds more of each kind of damage than the
    # real file may: the tests of each limit set it back.
    monkeypatch.setattr(local, "TSE_MAX_BAD", 1)
    monkeypatch.setattr(local, "TSE_MAX_MISSING", 1)
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
        "2022_rows": 7, "2022_rows_from_individuals": 5, "2022_new_records": 3,
        "2022_rows_not_60_columns": 1, "2022_lines_folded_into_a_field": 0,
        "2022_individuals_without_a_name": 1,
        "2022_individuals_without_a_registry_name": 0,
        "2022_individuals_whose_name_holds_a_number": 0, "2022_rows_read_as_cp1252": 1,
        "2024_rows": 8, "2024_rows_from_individuals": 8, "2024_new_records": 3,
        "2024_rows_not_60_columns": 0, "2024_lines_folded_into_a_field": 0,
        "2024_individuals_without_a_name": 1,
        "2024_individuals_without_a_registry_name": 1,
        "2024_individuals_whose_name_holds_a_number": 3, "2024_rows_read_as_cp1252": 1,
        "records_whose_name_differs_from_the_registry": 5}
    assert corpus.header().startswith("TSE (Tribunal Superior Eleitoral)")
    assert corpus.header().endswith("6 name pairs (local corpus tse-donors)")
    assert cdn.ranges > 4  # read in ranges, not in one answer


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
    for year in local.TSE_ELECTIONS:
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
    with pytest.raises(ValueError, match="each in fewer than 10 rows") as raised:
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
    monkeypatch.setattr(local, "TSE_MIN_INDIVIDUALS", 0.11)  # 1 of 10 falls short
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
    monkeypatch.setattr(local, "TSE_MAX_MISSING", 1 / 100)
    _serve_member(cdn, "2022", _tse_csv([_tse_row(_PF, "ANA SOUZA", "ANA SOUZA")]))
    _serve_member(cdn, "2024", _tse_csv([_tse_row(_PF, name, registry)]))
    with pytest.raises(ValueError, match=f"1 of 1 individuals' rows .* {match}"):
        local.fetch(_TSE)


@pytest.mark.parametrize(("member", "match"), [
    (_tse_csv(_TSE_ROWS["2022"]), "1 rows not 60 columns in 7 rows"),
    # A field holding a line break: two lines, one row.
    (_tse_csv([_tse_row(_PF, "ANA\r\nSOUZA", "ANA SOUZA"), _tse_row(_PF, "BO", "BO")]),
     "1 lines folded into another row's field in 2 rows"),
], ids=["a row not 60 columns", "a line folded into a field"])
def test_a_tse_file_with_too_many_malformed_lines_is_refused(
        cdn: _Cdn, monkeypatch: pytest.MonkeyPatch, member: bytes, match: str) -> None:
    monkeypatch.setattr(local, "TSE_MAX_BAD", 1 / 10)
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


@pytest.mark.parametrize("after", [0, 6], ids=["at the start", "inside the member"])
def test_a_tse_zip_replaced_during_the_read_is_refused(cdn: _Cdn, after: int) -> None:
    cdn.zips[_url("2022")] = _tse_zip("2022", _tse_csv(_TSE_ROWS["2022"] * 20))
    cdn.replace_after = after
    with pytest.raises(ValueError, match="2022.zip answered a range request whole "
                                         r"\(HTTP 200\)"):
        local.fetch(_TSE)
    assert local.load(_TSE) is None


@pytest.mark.parametrize(("content_range", "long"), [
    ("bytes 0-9/10", False), (None, True)], ids=["another range", "a byte too many"])
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
], ids=["no length", "no validator", "a weak ETag alone", "no byte ranges"])
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
    monkeypatch.setattr(local, "CTGOV_RETRIES", 5)  # four failures on one range
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


def test_a_tse_corpus_of_other_elections_is_refused_on_load(
        cdn: _Cdn, monkeypatch: pytest.MonkeyPatch) -> None:
    local.fetch(_TSE)
    monkeypatch.setattr(local, "TSE_ELECTIONS", ("2022", "2024", "2026"))
    with pytest.raises(ValueError, match=f"holds the elections 2022 2024.*reads "
                                         f"2022 2024 2026.*fetch {_TSE} --refresh"):
        local.load(_TSE)


# -- load ----------------------------------------------------------------------

def _fetched(monkeypatch: pytest.MonkeyPatch, tmp_path: Path,
             *names: str, date: str = _DATE) -> Path:
    """A corpus of `names` fetched into tmp_path's cache, with no network
    behind it; its folder."""
    monkeypatch.setenv("NAMEPARSER_TOOLS_CACHE", str(tmp_path))
    records = [{"name": n} for n in names or ("Ann Lee, MD", "Bo Wu, PhD")]
    monkeypatch.setitem(local.SOURCES, _SOURCE, local.Source(
        local.SOURCES[_SOURCE].credit, "officials",
        lambda: local.Fetched(records, date, {})))
    local.fetch(_SOURCE)
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


def test_a_change_to_how_raw_jsonl_is_cut_into_records_changes_the_key(
        monkeypatch: pytest.MonkeyPatch) -> None:
    before = local.fold_fingerprint()
    monkeypatch.setattr(local.corpus_build, "jsonl_lines", lambda text: [])
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


def test_a_record_without_a_name_fails_when_the_records_are_read(
        monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    folder = _fetched(monkeypatch, tmp_path)
    raw = b'{"nom": "Ann Lee, MD"}\n'
    (folder / "raw.jsonl").write_bytes(raw)
    _rewrite_meta(folder, sha256=hashlib.sha256(raw).hexdigest())
    loaded = local.load(_SOURCE)
    assert loaded is not None
    with pytest.raises(ValueError, match="record without a name"):
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


# -- snapshot.py --local -----------------------------------------------------------

def test_snapshot_reads_a_local_corpus_against_its_own_snapshot(
        monkeypatch: pytest.MonkeyPatch, tmp_path: Path,
        capsys: pytest.CaptureFixture[str]) -> None:
    _fetched(monkeypatch, tmp_path)
    with pytest.raises(SystemExit, match="no snapshot"):
        snapshot.main(["--local", _SOURCE])
    assert snapshot.main(["--local", _SOURCE, "--record"]) == 0
    recorded = _folder(tmp_path) / "snapshot.jsonl"
    assert len(recorded.read_text().splitlines()) == 2
    assert snapshot.main(["--local", _SOURCE]) == 0
    assert "matches the snapshot" in capsys.readouterr().out

    # A reading that moved, as a change to the parser would move it.
    rows = recorded.read_text().splitlines()
    row = json.loads(rows[0])
    row["family"] = "Moved"
    recorded.write_text("\n".join([json.dumps(row)] + rows[1:]) + "\n")
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
    assert len(out.read_text().splitlines()) == 2
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
