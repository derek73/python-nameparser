"""Offline checks on tools/differential/local_patentsview.py, the
patentsview-inventors local corpus.

Every name here is invented, and no reading of a real inventor may
reach the repository: the inventors are living people, which is why
the corpus is local. No test reaches the portal or needs its key: the
server is a stub, and the key is a file in the test's own home. What
these pin is where the key goes, the refusal of another release or of
bytes that are not the pinned ones, the join of the two inventor tables
and its people count, the checks a read makes, and the cap.
"""
import csv
import email.message
import gzip
import hashlib
import importlib
import io
import json
import urllib.error
import urllib.request
import zipfile
from collections.abc import Callable, Sequence
from pathlib import Path

import pytest

from ._differential_fixtures import load_tool, own_cache

local = load_tool("local_corpora")
# The module the fetch reads its constants from, by name (test_local_corpora.py).
pv = importlib.import_module("local_patentsview")

_PV = "patentsview-inventors"


@pytest.fixture(autouse=True)
def _own_cache(monkeypatch: pytest.MonkeyPatch, tmp_path_factory: pytest.TempPathFactory) -> Path:
    return own_cache(monkeypatch, tmp_path_factory)


@pytest.fixture
def key(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> Path:
    path = tmp_path / "uspto-odp-key"
    path.write_text("test-key-not-real\n")
    monkeypatch.setattr(pv, "PV_KEY", path)
    return path


def _table(header: list[str], rows: list[list[str]]) -> bytes:
    """A table as PatentsView ships one: a zip of one TSV, every field quoted."""
    text = io.StringIO()
    writer = csv.writer(text, delimiter="\t", quoting=csv.QUOTE_ALL, lineterminator="\n")
    writer.writerow(header)
    writer.writerows(rows)
    raw = io.BytesIO()
    with zipfile.ZipFile(raw, "w") as archive:
        archive.writestr("table.tsv", text.getvalue())
    return raw.getvalue()


_RAW_HEAD = ["patent_id", "inventor_sequence", "inventor_id", "raw_inventor_name_first",
             "raw_inventor_name_last", "deceased_flag", "rawlocation_id"]
_DIS_HEAD = ["patent_id", "inventor_sequence", "inventor_id", "disambig_inventor_name_first",
             "disambig_inventor_name_last", "gender_code", "location_id"]
_LOC_HEAD = ["location_id", "disambig_city", "disambig_state", "disambig_country",
             "latitude", "longitude", "county", "state_fips", "county_fips"]

#: (patent, sequence, inventor id, first, last, location). Ann Lee holds
#: two patents (one person), a second Ann Lee is another person, and Bo
#: Wu files in Japan, Cy Doe's location names no country, and Eve Ng
#: holds four patents in Japan: 9 of the 10 rows name a country, which
#: is PV_MIN_COUNTRY's shipped floor exactly.
_INVENTORS = [("1", "0", "i1", "Ann", "Lee", "l1"), ("2", "0", "i1", "Ann", "Lee", "l1"),
              ("2", "1", "i2", "Ann", "Lee", "l1"), ("3", "0", "i3", "Bo", "Wu", "l2"),
              ("4", "0", "i4", "Cy  Q.", "Doe", "l3"), ("5", "0", "i5", "Di", "Fox", "l2"),
              *((str(n), "0", "i6", "Eve", "Ng", "l2") for n in range(6, 10))]
_LOCATIONS = [["l1", "X", "", "US", "0", "0", "", "", ""],
              ["l2", "Y", "", "JP", "0", "0", "", "", ""],
              ["l3", "Z", "", "", "0", "0", "", "", ""]]


def _files(inventors: Sequence[tuple[str, ...]] = _INVENTORS, *,
           dis: Sequence[tuple[str, ...]] | None = None,
           raw_extra: Sequence[list[str]] = ()) -> dict[str, bytes]:
    raw_rows = [[p, s, i, f, last, "False", "r"] for p, s, i, f, last, _ in inventors]
    dis_rows = [[p, s, i, f, last, "U", loc] for p, s, i, f, last, loc in (dis or inventors)]
    return {pv.PV_RAW: _table(_RAW_HEAD, raw_rows + list(raw_extra)),
            pv.PV_INVENTORS: _table(_DIS_HEAD, dis_rows),
            pv.PV_LOCATIONS: _table(_LOC_HEAD, _LOCATIONS)}


class _Body(io.BytesIO):
    def __enter__(self) -> "_Body":
        return self


def _serve(monkeypatch: pytest.MonkeyPatch, files: dict[str, bytes], *,
           listed: dict[str, tuple[int, str]] | None = None, rows: int | None = None) -> list[str]:
    """`files` as the pinned release, their sizes and sha256 pinned and
    the rows the raw table holds; the URLs asked."""
    monkeypatch.setattr(pv, "PV_FILES", {
        name: (len(body), "2026-03-12 22:26:59", hashlib.sha256(body).hexdigest())
        for name, body in files.items()})
    monkeypatch.setattr(pv, "PV_ROWS", rows if rows is not None else len(_INVENTORS))
    asked: list[str] = []
    stated = listed or {name: (len(body), "2026-03-12 22:26:59") for name, body in files.items()}

    def opened(url: str) -> _Body:
        asked.append(url)
        if "includeFiles" in url:
            return _Body(json.dumps({"bulkDataProductBag": [{"productFileBag": {"fileDataBag": [
                {"fileName": n, "fileSize": size, "fileLastModifiedDateTime": when,
                 "fileDownloadURI": f"{pv.PV_API}/files/{pv.PV_PRODUCT}/{n}"}
                for n, (size, when) in stated.items()]}}]}).encode())
        return _Body(files[url.rsplit("/", 1)[-1]])

    monkeypatch.setattr(pv, "_open", opened)
    return asked


# -- the key ------------------------------------------------------------------

@pytest.mark.parametrize("held", [None, "", "two words\n"])
def test_a_missing_or_malformed_key_is_refused_saying_how_to_get_one(
        monkeypatch: pytest.MonkeyPatch, tmp_path: Path, held: str | None) -> None:
    path = tmp_path / "uspto-odp-key"
    if held is not None:
        path.write_text(held)
    monkeypatch.setattr(pv, "PV_KEY", path)
    with pytest.raises(ValueError, match="ID.me.*My ODP.*chmod 600"):
        pv._key()


def test_the_key_goes_to_an_https_uspto_host_only(
        monkeypatch: pytest.MonkeyPatch, key: Path) -> None:
    sent: list[urllib.request.Request] = []

    class Opener:
        def open(self, request: urllib.request.Request, timeout: int) -> None:
            sent.append(request)

    monkeypatch.setattr(pv.urllib.request, "build_opener", lambda *handlers: Opener())
    pv._open(f"{pv.PV_API}/{pv.PV_PRODUCT}")
    assert sent[0].get_header("X-api-key") == "test-key-not-real"
    for elsewhere in ("http://api.uspto.gov/x", "https://uspto.gov.example.com/x",
                      "https://example.com/x"):
        with pytest.raises(ValueError, match="the key goes nowhere else"):
            pv._open(elsewhere)
    assert len(sent) == 1


@pytest.mark.parametrize(("to", "keeps"), [
    ("https://data.uspto.gov/file.zip", True),
    ("https://bucket.s3.amazonaws.com/file.zip", False)])
def test_a_redirect_off_uspto_drops_the_key(to: str, keeps: bool) -> None:
    request = urllib.request.Request("https://api.uspto.gov/f", headers={"X-API-KEY": "k"})
    new = pv._KeyStaysHome().redirect_request(request, None, 302, "Found", {}, to)
    assert new is not None and (new.get_header("X-api-key") == "k") is keeps


# -- the release --------------------------------------------------------------

@pytest.mark.parametrize("listed", [
    {pv.PV_RAW: (1, "2026-03-12 22:26:59")},
    "size", "date"])
def test_a_listing_of_another_release_is_refused(
        monkeypatch: pytest.MonkeyPatch, key: Path,
        listed: dict[str, tuple[int, str]] | str) -> None:
    files = _files()
    if listed == "size":
        listed = {n: (len(b) + 1, "2026-03-12 22:26:59") for n, b in files.items()}
    elif listed == "date":
        listed = {n: (len(b), "2026-06-11 00:00:00") for n, b in files.items()}
    assert isinstance(listed, dict)
    _serve(monkeypatch, files, listed=listed)
    with pytest.raises(ValueError, match="another release, measured and pinned by hand"):
        pv.renew_pv()


def test_bytes_that_are_not_the_pinned_sha256_are_refused_and_not_kept(
        monkeypatch: pytest.MonkeyPatch, key: Path) -> None:
    files = _files()
    _serve(monkeypatch, files)
    name = pv.PV_LOCATIONS
    size, when, _ = pv.PV_FILES[name]
    monkeypatch.setitem(pv.PV_FILES, name, (size, when, "0" * 64))
    with pytest.raises(ValueError, match="sha256"):
        pv.renew_pv()
    assert not pv.extract_path().exists()
    # The files that arrived whole stay for the next run; nothing partial does.
    assert sorted(p.name for p in pv.extract_path().parent.rglob("*") if p.is_file()) == [
        pv.PV_INVENTORS, pv.PV_RAW]


def test_a_run_after_a_failed_one_downloads_only_what_was_not_whole(
        monkeypatch: pytest.MonkeyPatch, key: Path) -> None:
    files = _files()
    asked = _serve(monkeypatch, files)
    size, when, sha = pv.PV_FILES[pv.PV_LOCATIONS]
    monkeypatch.setitem(pv.PV_FILES, pv.PV_LOCATIONS, (size, when, "0" * 64))
    with pytest.raises(ValueError, match="sha256"):
        pv.renew_pv()
    monkeypatch.setitem(pv.PV_FILES, pv.PV_LOCATIONS, (size, when, sha))
    asked.clear()
    pv.renew_pv()
    assert [url.rsplit("/", 1)[-1] for url in asked if "includeFiles" not in url] == [
        pv.PV_LOCATIONS]
    assert not (pv.extract_path().parent / "downloads").exists()


def test_a_download_dropped_mid_file_is_tried_again(
        monkeypatch: pytest.MonkeyPatch, key: Path) -> None:
    files = _files()
    _serve(monkeypatch, files)
    served: Callable[[str], _Body] = pv._open
    drops = [pv.PV_RAW]
    monkeypatch.setattr(importlib.import_module("local_core").time, "sleep", lambda _s: None)

    def dropping(url: str) -> _Body:
        if drops and url.endswith(drops[0]):
            drops.pop()
            raise ConnectionResetError("reset by peer")
        return served(url)

    monkeypatch.setattr(pv, "_open", dropping)
    pv.renew_pv()
    assert pv.extract_path().exists() and not drops


@pytest.mark.parametrize("code", [401, 403])
def test_a_key_the_portal_refuses_is_reported_as_the_keys(
        monkeypatch: pytest.MonkeyPatch, key: Path, code: int) -> None:
    class Opener:
        def open(self, request: urllib.request.Request, timeout: int) -> None:
            raise urllib.error.HTTPError(request.full_url, code, "Unauthorized",
                                         email.message.Message(), io.BytesIO())

    monkeypatch.setattr(pv.urllib.request, "build_opener", lambda *handlers: Opener())
    with pytest.raises(ValueError, match=f"refused the key in .*uspto-odp-key \\({code}\\).*ID.me"):
        pv._listed()


# -- the fetch ------------------------------------------------------------------

def test_a_fetch_counts_people_not_patents_and_keeps_the_country(
        monkeypatch: pytest.MonkeyPatch, key: Path) -> None:
    _serve(monkeypatch, _files())
    corpus = local.fetch(_PV)
    assert sorted(corpus.records, key=lambda r: r["name"]) == [
        {"country": "US", "family": "Lee", "given": "Ann", "name": "Ann Lee", "people": "2"},
        {"country": "JP", "family": "Wu", "given": "Bo", "name": "Bo Wu", "people": "1"},
        {"family": "Doe", "given": "Cy Q.", "name": "Cy Q. Doe", "people": "1"},
        {"country": "JP", "family": "Fox", "given": "Di", "name": "Di Fox", "people": "1"},
        {"country": "JP", "family": "Ng", "given": "Eve", "name": "Eve Ng", "people": "1"}]
    detail = corpus.meta["detail"]
    assert (detail["rows"], detail["names"], detail["people_by_name"],
            detail["rows_with_a_country"], detail["countries"]) == (10, 5, 6, 9, 2)
    # The zips are gone; only the extract and the corpus files stay.
    assert not (pv.extract_path().parent / "downloads").exists()


def test_the_extract_keeps_every_name_with_its_people_as_a_number(
        monkeypatch: pytest.MonkeyPatch, key: Path) -> None:
    _serve(monkeypatch, _files())
    local.fetch(_PV)
    with gzip.open(pv.extract_path(), "rt", encoding="utf-8") as lines:
        header, *names = lines.read().splitlines()
    assert json.loads(header)["release"] == pv.PV_RELEASE
    assert json.loads(names[0]) == {"country": "US", "family": "Lee", "given": "Ann",
                                    "people": 2}


def test_the_two_inventor_tables_out_of_step_are_refused(
        monkeypatch: pytest.MonkeyPatch, key: Path) -> None:
    shuffled = _INVENTORS[2:] + _INVENTORS[:2]
    _serve(monkeypatch, _files(dis=shuffled))
    with pytest.raises(ValueError, match="not row for row the same inventors"):
        pv.renew_pv()
    _serve(monkeypatch, _files(dis=_INVENTORS + [("9", "0", "i9", "Ed", "Ng", "l1")]))
    with pytest.raises(ValueError, match="holds more rows than"):
        pv.renew_pv()


def test_a_table_read_in_part_is_refused_and_the_extract_kept(
        monkeypatch: pytest.MonkeyPatch, key: Path) -> None:
    _serve(monkeypatch, _files())
    pv.renew_pv()
    before = pv.extract_path().read_bytes()
    _serve(monkeypatch, _files(), rows=len(_INVENTORS) + 1)
    with pytest.raises(ValueError, match="a table was read in part"):
        pv.renew_pv()
    assert pv.extract_path().read_bytes() == before
    # Nothing staged or partial stays beside it (the whole zips may, for the next run).
    assert sorted(p.name for p in pv.extract_path().parent.iterdir() if p.is_file()) == [
        pv.extract_path().name]


def test_a_row_not_the_headers_width_is_counted_and_past_the_share_refused(
        monkeypatch: pytest.MonkeyPatch, key: Path) -> None:
    files = _files(raw_extra=[["6", "0", "i6", "Ed"]])
    _serve(monkeypatch, files)
    with pytest.raises(ValueError, match="1 of 10 g_inventor_not_disambiguated.tsv.zip: "
                                         "rows not 7 fields"):
        pv.renew_pv()
    monkeypatch.setattr(pv, "PV_MAX_BAD", 1 / 5)
    assert local.fetch(_PV).meta["detail"][f"{pv.PV_RAW}: rows not 7 fields"] == 1


@pytest.mark.parametrize(("inventors", "says"), [
    ([(p, s, i, f, last, "l3") for p, s, i, f, last, _ in _INVENTORS],
     "only 0 of 10 rows name a country"),
    ([(p, s, i, f, "", loc) for p, s, i, f, _, loc in _INVENTORS],
     "only 0 of 10 rows fill both boxes")])
def test_tables_whose_columns_moved_under_the_reader_are_refused(
        monkeypatch: pytest.MonkeyPatch, key: Path, inventors: Sequence[tuple[str, ...]],
        says: str) -> None:
    _serve(monkeypatch, _files(inventors))
    with pytest.raises(ValueError, match=says):
        pv.renew_pv()


def test_a_header_without_a_column_read_is_refused(
        monkeypatch: pytest.MonkeyPatch, key: Path) -> None:
    files = _files()
    files[pv.PV_LOCATIONS] = _table(["location_id", "country_name"], [["l1", "US"]])
    _serve(monkeypatch, files)
    with pytest.raises(ValueError, match="header holds no disambig_country"):
        pv.renew_pv()


def test_a_file_that_is_not_an_extract_is_refused_naming_the_refresh() -> None:
    path = pv.extract_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(gzip.compress(b'{"release": "2024-12-31", "files": {}, "counts": {}}\n',
                                   mtime=0))
    with pytest.raises(ValueError, match="not an extract this tool wrote.*--refresh"):
        pv._pv_read(path)


def test_a_corpus_kept_under_another_cap_is_refused_on_load(
        monkeypatch: pytest.MonkeyPatch, key: Path) -> None:
    _serve(monkeypatch, _files())
    local.fetch(_PV)
    assert local.load(_PV) is not None
    monkeypatch.setattr(pv, "PV_CAP", 7)
    with pytest.raises(local.CorpusDamaged, match="at most 7 names a country"):
        local.load(_PV)


def test_the_cap_samples_a_large_country_and_keeps_the_same_names_whatever_the_order() -> None:
    people = [{"name": f"Ann Lee{i}", "country": "US", "people": "1"} for i in range(30)]
    kept = pv.pv_kept(iter(people + [{"name": "Bo Wu", "country": "JP", "people": "1"}]), 10)
    assert sum(r["country"] == "US" for r in kept) == 10
    again = pv.pv_kept(iter(people[::-1]), 10)
    assert sorted(map(str, again)) == sorted(map(str, (r for r in kept if r["country"] == "US")))


def test_the_corpus_scores_with_its_boxes(monkeypatch: pytest.MonkeyPatch, key: Path) -> None:
    agreement = load_tool("local_agreement")
    _serve(monkeypatch, _files())
    corpus = local.fetch(_PV)
    from nameparser import Parser
    parser = Parser()
    listed = agreement._title_words(parser.lexicon)
    fielded = agreement.FIELDED[_PV]
    assert all(not agreement.read(r, fielded, parser, listed).got for r in corpus.records)
