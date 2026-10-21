"""Offline checks on tools/differential/local_corpora.py.

A local corpus is fetched once from a live source and then trusted as
the pin, so what these pin is the fetch's refusals (a fetch straddling
the source's daily refresh, a fetch cut short), the load's refusal of a
file that no longer matches its sha256, and the views' counting. The
failure that matters is a SMALLER corpus passing for the whole one: its
counts read as real zeros. The network is a stub answering by URL.
"""
import json
import time
import urllib.error
import urllib.parse
import urllib.request
from collections.abc import Callable
from pathlib import Path
from typing import Any

import pytest

from ._differential_fixtures import _Response, load_tool

local = load_tool("local_corpora")
snapshot = load_tool("snapshot")


def _study(nct: str, *officials: str) -> dict[str, Any]:
    return {"protocolSection": {
        "identificationModule": {"nctId": nct},
        "contactsLocationsModule": {"overallOfficials": [
            {"name": name, "role": "PRINCIPAL_INVESTIGATOR"} for name in officials]}}}


#: Two pages of three studies, one without officials.
_PAGES: list[dict[str, Any]] = [
    {"totalCount": 3, "nextPageToken": "t2",
     "studies": [_study("NCT1", "Ann Lee, MD, PhD", "BOB ROE MD"),
                 {"protocolSection": {"identificationModule": {"nctId": "NCT2"}}}]},
    {"studies": [_study("NCT3", "Ann Lee, MD, PhD", "Cy Doe,M.D.")]},
]


def _serve(monkeypatch: pytest.MonkeyPatch, tmp_path: Path, *,
           dates: tuple[str, ...] = ("2026-10-21T09:00:05",) * 2,
           pages: list[dict[str, Any]] = _PAGES,
           fail: Callable[[str], Exception | None] = lambda url: None) -> list[str]:
    """Answer the API from `pages` by pageToken and /version from
    `dates` in turn; `fail` may raise instead for a URL. Returns the
    URLs fetched."""
    monkeypatch.setenv("NAMEPARSER_TOOLS_CACHE", str(tmp_path))
    monkeypatch.setattr(time, "sleep", lambda s: None)
    fetched: list[str] = []
    versions = iter(dates)

    def urlopen(request: urllib.request.Request, timeout: int) -> _Response:
        url = request.full_url
        fetched.append(url)
        error = fail(url)
        if error is not None:
            raise error
        if url.endswith("/version"):
            body: object = {"apiVersion": "2.0.5", "dataTimestamp": next(versions)}
        else:
            token = urllib.parse.parse_qs(urllib.parse.urlsplit(url).query).get(
                "pageToken", [""])[0]
            body = pages[0] if not token else pages[int(token[1:]) - 1]
        return _Response(json.dumps(body).encode())
    monkeypatch.setattr(urllib.request, "urlopen", urlopen)
    return fetched


def test_a_fetch_pages_through_and_writes_the_three_files(
        monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    fetched = _serve(monkeypatch, tmp_path)
    corpus = local.fetch("ctgov-officials")
    assert [u.rsplit("/", 1)[-1].split("?")[0] for u in fetched] == [
        "version", "studies", "studies", "version"]
    assert [r["name"] for r in corpus.records] == [
        "Ann Lee, MD, PhD", "BOB ROE MD", "Ann Lee, MD, PhD", "Cy Doe,M.D."]
    assert corpus.records[0] == {"name": "Ann Lee, MD, PhD", "study": "NCT1",
                                 "role": "PRINCIPAL_INVESTIGATOR"}
    folder = tmp_path / "local" / "ctgov-officials"
    assert [json.loads(line) for line in (folder / "corpus.jsonl").read_text().splitlines()] == [
        "Ann Lee, MD, PhD", "BOB ROE MD", "Cy Doe,M.D."]
    meta = json.loads((folder / "meta.json").read_text())
    assert (meta["data_date"], meta["records"], meta["names"], meta["studies"]) == (
        "2026-10-21T09:00:05", 4, 3, 3)
    assert local.load("ctgov-officials") == corpus
    assert corpus.header().startswith(
        "ClinicalTrials.gov (NLM) study officials, data as of 2026-10-21T09:00:05; 4 officials")


def test_a_fetch_straddling_a_refresh_is_refused(
        monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    _serve(monkeypatch, tmp_path, dates=("2026-10-21T09:00:05", "2026-10-22T09:00:04"))
    with pytest.raises(ValueError, match="refreshed during the fetch"):
        local.fetch("ctgov-officials")
    assert local.load("ctgov-officials") is None


def test_a_fetch_cut_short_is_refused(
        monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    # The second page lost: the API stops handing out tokens early.
    first = {**_PAGES[0]}
    del first["nextPageToken"]
    _serve(monkeypatch, tmp_path, pages=[first])
    with pytest.raises(ValueError, match="paged 2 studies of the 3"):
        local.fetch("ctgov-officials")
    assert local.load("ctgov-officials") is None


def test_a_server_error_is_retried_and_a_client_error_is_not(
        monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    failures = [urllib.error.HTTPError("u", 503, "busy", {}, None)]  # type: ignore[arg-type]
    fetched = _serve(monkeypatch, tmp_path, fail=lambda url: failures.pop()
                     if "pageToken" in url and failures else None)
    local.fetch("ctgov-officials")
    assert sum("pageToken" in u for u in fetched) == 2

    fetched = _serve(monkeypatch, tmp_path, fail=lambda url: urllib.error.HTTPError(
        url, 400, "bad", {}, None) if "studies" in url else None)  # type: ignore[arg-type]
    with pytest.raises(urllib.error.HTTPError) as raised:
        local.fetch("ctgov-officials")
    raised.value.close()
    assert sum("studies" in u for u in fetched) == 1


def test_a_corpus_that_no_longer_matches_its_sha256_is_refused(
        monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    _serve(monkeypatch, tmp_path)
    local.fetch("ctgov-officials")
    raw = tmp_path / "local" / "ctgov-officials" / "raw.jsonl"
    raw.write_text("".join(raw.read_text().splitlines(keepends=True)[:-1]))
    with pytest.raises(ValueError, match="does not match the sha256"):
        local.load("ctgov-officials")


def test_an_unknown_source_names_the_known_ones() -> None:
    with pytest.raises(ValueError, match="ctgov-officials"):
        local.directory("nppes")


def _corpus(*names: str) -> object:
    return local.Local("ctgov-officials", [{"name": n} for n in names],
                       {"data_date": "2026-10-21"})


def test_the_tally_counts_each_part_after_a_comma_once_per_record() -> None:
    parts, with_comma = local.tally(_corpus(
        "Ann Lee, MD, PhD", "Bo Wu,MD", "Cy Doe MD", "Di Fox, MD, MD"))
    assert with_comma == 3
    assert parts == {"MD": 3, "PhD": 1}


def test_a_word_is_counted_anywhere_and_after_a_comma_ignoring_case_and_periods() -> None:
    index = local.word_index(_corpus(
        "Ann Lee, M.D.", "MD Bo Wu", "Cy Doe, md, MD", "Dr. Ma Li, (Psychiatry)"))
    assert (index.anywhere["md"], index.after_comma["md"]) == (3, 2)
    assert index.spellings["md"] == {"M.D.": 1, "MD": 2, "md": 1}
    assert (index.anywhere["psychiatry"], index.after_comma["psychiatry"]) == (1, 1)
    assert (index.anywhere["ma"], index.after_comma["ma"]) == (1, 0)


# -- snapshot.py --local -------------------------------------------------------

def test_snapshot_reads_a_local_corpus_against_its_own_snapshot(
        monkeypatch: pytest.MonkeyPatch, tmp_path: Path,
        capsys: pytest.CaptureFixture[str]) -> None:
    _serve(monkeypatch, tmp_path)
    local.fetch("ctgov-officials")
    with pytest.raises(SystemExit, match="no snapshot"):
        snapshot.main(["--local", "ctgov-officials"])
    assert snapshot.main(["--local", "ctgov-officials", "--record"]) == 0
    recorded = tmp_path / "local" / "ctgov-officials" / "snapshot.jsonl"
    assert len(recorded.read_text().splitlines()) == 3
    assert snapshot.main(["--local", "ctgov-officials"]) == 0
    assert "matches the snapshot" in capsys.readouterr().out

    # A reading that moved, as a change to the parser would move it.
    rows = recorded.read_text().splitlines()
    row = json.loads(rows[0])
    row["family"] = "Moved"
    recorded.write_text("\n".join([json.dumps(row)] + rows[1:]) + "\n")
    assert snapshot.main(["--local", "ctgov-officials"]) == 1
    out = capsys.readouterr().out
    assert out.startswith("ClinicalTrials.gov (NLM) study officials, data as of")
    assert "Moved" in out and "1 entries differ" in out


def test_snapshot_refuses_a_local_corpus_not_fetched_and_since_with_local(
        monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setenv("NAMEPARSER_TOOLS_CACHE", str(tmp_path))
    with pytest.raises(SystemExit, match="not fetched"):
        snapshot.main(["--local", "ctgov-officials"])
    with pytest.raises(SystemExit):
        snapshot.main(["--local", "ctgov-officials", "--since", "v2.5.0"])
