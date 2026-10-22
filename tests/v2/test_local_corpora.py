"""Offline checks on tools/differential/local_corpora.py.

A local corpus is fetched once from a live source and then trusted as
the pin, so what these pin is the fetch's refusals (a fetch straddling
the source's daily refresh, a fetch cut short or paging a study twice,
a fetch with no names), the load's refusal of anything fetch() did not
write, the retries a long run needs, and the views' counting. The
failure that matters is a SMALLER corpus passing for the whole one: its
counts read as real zeros. The network is a stub answering by URL.
"""
import email.message
import http.client
import json
import time
import unicodedata
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

_SOURCE = "ctgov-officials"
_DATE = "2026-10-21T09:00:05"


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
    with pytest.raises(ValueError, match="paged 2 distinct studies of the 3"):
        local.fetch(_SOURCE)
    assert local.load(_SOURCE) is None


def test_a_fetch_paging_a_study_twice_and_missing_one_is_refused(
        monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    # Three studies paged, as many as totalCount, but NCT1 twice and NCT3
    # never: a count of the studies paged would pass it.
    _serve(monkeypatch, tmp_path, pages=[
        _PAGES[0], {"studies": [_study("NCT1", "Ann Lee, MD, PhD")]}])
    with pytest.raises(ValueError, match="paged 2 distinct studies of the 3"):
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


def test_an_unknown_source_names_the_known_ones() -> None:
    with pytest.raises(ValueError, match=_SOURCE):
        local.directory("nppes")
    with pytest.raises(ValueError, match=_SOURCE):
        local.fetch("nppes")


# -- load ----------------------------------------------------------------------

def _fetched(monkeypatch: pytest.MonkeyPatch, tmp_path: Path,
             *names: str) -> Path:
    """A corpus of `names` fetched into tmp_path's cache; its folder."""
    monkeypatch.setenv("NAMEPARSER_TOOLS_CACHE", str(tmp_path))
    records = [{"name": n} for n in names or ("Ann Lee, MD", "Bo Wu, PhD")]
    monkeypatch.setitem(local.SOURCES, _SOURCE, local.Source(
        local.SOURCES[_SOURCE].credit, "officials",
        lambda: local.Fetched(records, _DATE, {})))
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
], ids=["old version", "missing key", "wrong type"])
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


# -- views -------------------------------------------------------------------------

def _corpus(*names: str) -> object:
    return local.Local(_SOURCE, [{"name": n} for n in names], {"data_date": _DATE})


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
    assert (index.anywhere["md"], index.after_comma["md"]) == (3, 2)
    assert (index.anywhere["psychiatry"], index.after_comma["psychiatry"]) == (1, 1)
    assert (index.anywhere["ma"], index.after_comma["ma"]) == (1, 0)


@pytest.mark.parametrize("name", [
    "Bob Ray, MD/PhD", "Bob Ray, MD;", "Bob Ray, MD; PhD", "Bob Ray, (MD)",
    "Bob Ray, MD-", "Bob Ray, “MD”"])
def test_a_word_is_found_beside_any_punctuation(name: str) -> None:
    # Cut only at spaces and commas, 'MD/PhD' and 'MD;' were words of
    # their own, and a lookup of MD read zero: 3,698 officials' names
    # held a slash and 548 a semicolon on 2026-10-21.
    index = local.word_index(_corpus(name))
    assert (index.anywhere["md"], index.after_comma["md"]) == (1, 1)


def test_a_decomposed_letter_finds_its_composed_twin() -> None:
    index = local.word_index(_corpus(unicodedata.normalize("NFD", "Ana Žic, MD")))
    assert index.anywhere[local.word_key("Žic")] == 1


def test_spellings_are_counted_once_per_record() -> None:
    # Two records, one writing MD twice: a spelling count above the
    # record count read as more officials than wrote the word.
    index = local.word_index(_corpus("Di Fox, MD, MD", "Ed Ng, MD"))
    assert index.anywhere["md"] == 2
    assert index.spellings["md"] == {"MD": 2}


def test_a_spaced_word_is_matched_as_its_words_in_a_row() -> None:
    corpus = _corpus("Ann Lee, Ph. D.", "Bo Wu, Ph D, MD", "Ph D Cy", "Di Fox, PhD",
                     "Ed Ph, D")
    assert local.words("Ph. D.") == ["ph", "d"]
    assert local.phrase_counts(corpus, ["ph", "d"]) == (3, 2)


# -- snapshot.py --local -----------------------------------------------------------

def test_snapshot_reads_a_local_corpus_against_its_own_snapshot(
        monkeypatch: pytest.MonkeyPatch, tmp_path: Path,
        capsys: pytest.CaptureFixture[str]) -> None:
    _serve(monkeypatch, tmp_path)
    local.fetch(_SOURCE)
    with pytest.raises(SystemExit, match="no snapshot"):
        snapshot.main(["--local", _SOURCE])
    assert snapshot.main(["--local", _SOURCE, "--record"]) == 0
    recorded = _folder(tmp_path) / "snapshot.jsonl"
    assert len(recorded.read_text().splitlines()) == 3
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
    _serve(monkeypatch, tmp_path)
    local.fetch(_SOURCE)
    assert snapshot.main(["--local", _SOURCE, "--record"]) == 0
    _serve(monkeypatch, tmp_path, dates=("2026-10-22T09:00:04",) * 2, pages=[
        {"totalCount": 1, "studies": [_study("NCT9", "Eve Moe, DO")]}])
    local.fetch(_SOURCE)
    with pytest.raises(SystemExit, match="recorded from another fetch") as raised:
        snapshot.main(["--local", _SOURCE])
    assert _DATE in str(raised.value) and "2026-10-22T09:00:04" in str(raised.value)
    assert snapshot.main(["--local", _SOURCE, "--record"]) == 0
    assert snapshot.main(["--local", _SOURCE]) == 0


def test_snapshot_records_a_local_snapshot_where_out_says(
        monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    _serve(monkeypatch, tmp_path)
    local.fetch(_SOURCE)
    out = tmp_path / "elsewhere.jsonl"
    assert snapshot.main(["--local", _SOURCE, "--record", "--out", str(out)]) == 0
    assert len(out.read_text().splitlines()) == 3
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
    _serve(monkeypatch, tmp_path)
    local.fetch(_SOURCE)
    with pytest.raises(SystemExit) as raised:
        snapshot.main(["--local", _SOURCE, "--since", "v2.5.0"])
    assert raised.value.code == 2
    assert "--since reads a committed snapshot" in capsys.readouterr().err
