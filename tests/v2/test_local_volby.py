"""Offline checks on tools/differential/local_volby.py, the cz-candidates
local corpus of the Czech election candidate registers.

Every name here is invented: the registers' names are real people's,
so they stay in the cache. What these pin is how a record's name is
composed from its boxes, which register zip is read off an election's
index page, and the fetch's refusals: an answer that is not a zip, a
register missing a box's column, cut inside its last row, holding
another number of candidates than its pin, with too many rows skipped
or too few titled, and a corpus of other elections or another version
of the composition. The network is a stub answering by URL.
"""
import csv
import importlib
import io
import time
import urllib.error
import urllib.request
import zipfile

import pytest

from ._differential_fixtures import _Response, load_tool, own_cache

local = load_tool("local_corpora")
# The module the fetch reads its constants from, by name: a patch set on
# a second load by path would reach nothing (test_local_corpora.py).
volby = importlib.import_module("local_volby")

_VOLBY = volby.VOLBY


@pytest.fixture(autouse=True)
def _own_cache(monkeypatch: pytest.MonkeyPatch, tmp_path_factory: pytest.TempPathFactory) -> None:
    own_cache(monkeypatch, tmp_path_factory)


#: The municipal register's layout, cut to the columns read and two
#: beside them, and the Chamber register's, in another column order:
#: the boxes are read by name.
_KV_HEADER = ["DATUMVOLEB", "OKRES", "JMENO", "PRIJMENI", "TITULPRED", "TITULZA", "VEK"]
_PS_HEADER = ["VOLKRAJ", "PORCISLO", "JMENO", "PRIJMENI", "TITULZA", "TITULPRED", "VEK"]


def _kv(given: str, family: str, before: str = "", after: str = "") -> list[str]:
    return ["20220923", "7204", given, family, before, after, "50"]


def _ps(given: str, family: str, before: str = "", after: str = "") -> list[str]:
    return ["1", "1", given, family, after, before, "40"]


#: A titled candidate standing twice under the same boxes (one padded), a
#: candidate with a title after the name only, one with both, and one
#: untitled: 5 rows, 4 records.
_KV_ROWS = [_kv("Jan", "Novák", "Ing."), _kv(" Jan ", "Novák ", "Ing."),
            _kv("Eva", "Malá", after="DiS."), _kv("Petr Pavel", "Veselý", "doc. MUDr.", "CSc."),
            _kv("Ida", "Krátká")]
_PS_ROWS = [_ps("Jan", "Novák", "Ing."), _ps("Bo", "Dvořák Malá", "Mgr. et Mgr.")]


def _register(header: list[str], rows: list[list[str]], *, end: str = "\r\n") -> bytes:
    out = io.StringIO(newline="")
    writer = csv.writer(out, lineterminator="\r\n", quoting=csv.QUOTE_NONNUMERIC)
    writer.writerow(header)
    writer.writerows(rows)
    text = out.getvalue()
    return (text[:-2] + end if end != "\r\n" else text).encode()


def _zip(member: str, body: bytes) -> bytes:
    out = io.BytesIO()
    with zipfile.ZipFile(out, "w") as archive:
        archive.writestr(member, body)
        archive.writestr(member.replace(".csv", ".json"), b"{}")
    return out.getvalue()


def _index(*files: str) -> bytes:
    links = "".join(f'<a href="{f}">CSV</a>\n' for f in files)
    return f"<html><body>{links}<a href='KV2022regPopis.pdf'>popis</a></body></html>".encode()


_KV_ZIP = "KV2022reg20260328_csv.zip"
_PS_ZIP = "PS2025reg20251005_csv.zip"


def _serve(monkeypatch: pytest.MonkeyPatch, *, kv: bytes | None = None, ps: bytes | None = None,
           kv_index: bytes | None = None) -> list[str]:
    """Answer each election's index page and register zip, the fixture's
    unless given; the URLs asked. The pins are the fixture's counts."""
    monkeypatch.setattr(volby, "VOLBY_ELECTIONS", {
        "kv2022": ("csv_od/kvrk.csv", len(_KV_ROWS)), "ps2025": ("csv_od/psrk.csv", len(_PS_ROWS))})
    answers = {
        volby.index_url("kv2022"): kv_index or _index(_KV_ZIP.replace("_csv", "_xml"), _KV_ZIP),
        volby.index_url("ps2025"): _index(_PS_ZIP),
        f"{volby.VOLBY_SITE}kv2022/{_KV_ZIP}":
            kv if kv is not None else _zip("csv_od/kvrk.csv", _register(_KV_HEADER, _KV_ROWS)),
        f"{volby.VOLBY_SITE}ps2025/{_PS_ZIP}":
            ps if ps is not None else _zip("csv_od/psrk.csv", _register(_PS_HEADER, _PS_ROWS)),
    }
    asked: list[str] = []

    def urlopen(request: urllib.request.Request, timeout: int) -> _Response:
        asked.append(request.full_url)
        if request.full_url not in answers:
            raise urllib.error.HTTPError(request.full_url, 404, "Not Found", {}, None)  # type: ignore[arg-type]
        return _Response(answers[request.full_url])
    monkeypatch.setattr(urllib.request, "urlopen", urlopen)
    monkeypatch.setattr(time, "sleep", lambda seconds: None)
    return asked


def test_a_fetch_keeps_each_candidate_s_boxes_once_with_the_composed_name(
        monkeypatch: pytest.MonkeyPatch) -> None:
    asked = _serve(monkeypatch)
    corpus = local.fetch(_VOLBY)
    assert asked == [volby.index_url("kv2022"), f"{volby.VOLBY_SITE}kv2022/{_KV_ZIP}",
                     volby.index_url("ps2025"), f"{volby.VOLBY_SITE}ps2025/{_PS_ZIP}"]
    assert corpus.records == [
        {"name": "Eva Malá, DiS.", "election": "kv2022", "jmeno": "Eva", "prijmeni": "Malá",
         "titulza": "DiS."},
        {"name": "Ida Krátká", "election": "kv2022", "jmeno": "Ida", "prijmeni": "Krátká"},
        {"name": "Ing. Jan Novák", "election": "kv2022", "jmeno": "Jan", "prijmeni": "Novák",
         "titulpred": "Ing."},
        {"name": "doc. MUDr. Petr Pavel Veselý, CSc.", "election": "kv2022",
         "jmeno": "Petr Pavel", "prijmeni": "Veselý", "titulpred": "doc. MUDr.",
         "titulza": "CSc."},
        {"name": "Ing. Jan Novák", "election": "ps2025", "jmeno": "Jan", "prijmeni": "Novák",
         "titulpred": "Ing."},
        {"name": "Mgr. et Mgr. Bo Dvořák Malá", "election": "ps2025", "jmeno": "Bo",
         "prijmeni": "Dvořák Malá", "titulpred": "Mgr. et Mgr."}]
    assert corpus.meta["data_date"] == "kv2022 2026-03-28, ps2025 2025-10-05"
    assert corpus.meta["detail"] == {
        "elections": "kv2022 ps2025", "read_version": volby.VOLBY_READ_VERSION,
        "kv2022": {"zip": _KV_ZIP, "candidates": 5, "titled": 4, "records": 4},
        "ps2025": {"zip": _PS_ZIP, "candidates": 2, "titled": 2, "records": 2}}
    # One composed name in two elections is one corpus name.
    assert corpus.meta["names"] == 5
    assert corpus.header().endswith("6 candidates (local corpus cz-candidates)")


@pytest.mark.parametrize(("boxes", "name"), [
    ({"jmeno": "Jan", "prijmeni": "Novák"}, "Jan Novák"),
    ({"titulpred": "Ing.", "jmeno": "Jan", "prijmeni": "Novák", "titulza": "Ph.D."},
     "Ing. Jan Novák, Ph.D."),
    ({"jmeno": "Jan", "prijmeni": "Novák", "titulza": "Ph.D., MBA"}, "Jan Novák, Ph.D., MBA"),
    ({"titulpred": "Bc.", "jmeno": "Jan", "prijmeni": "Novák", "titulza": ""}, "Bc. Jan Novák"),
])
def test_a_name_is_composed_in_the_czech_convention(boxes: dict[str, str], name: str) -> None:
    assert volby.compose(boxes) == name


def test_the_newest_register_the_index_links_is_read(monkeypatch: pytest.MonkeyPatch) -> None:
    # ps2021's index links a revision beside the first register; a stamp
    # older than the newest is a superseded file.
    older = "KV2022reg20221010_csv.zip"
    _serve(monkeypatch, kv_index=_index(older, _KV_ZIP, "KV2022reg20260328_xlsx.zip"))
    assert local.fetch(_VOLBY).meta["detail"]["kv2022"]["zip"] == _KV_ZIP
    # The older stamp's zip would be asked for, and answered 404, were
    # it the one picked: the control.
    assert max(volby._zip_link("kv2022").findall(_index(older).decode()))[0] == older


def test_a_register_named_with_underscores_is_found(monkeypatch: pytest.MonkeyPatch) -> None:
    # kv2018's index names it KV2018_reg_20230224_csv.zip.
    page = _index("KV2018_reg_20230224_xml.zip", "KV2018_reg_20230224_csv.zip").decode()
    assert volby._zip_link("kv2018").findall(page) == [("KV2018_reg_20230224_csv.zip",
                                                         "20230224")]


def test_an_index_linking_no_register_is_refused(monkeypatch: pytest.MonkeyPatch) -> None:
    _serve(monkeypatch, kv_index=_index("KV2022regPopis.pdf"))
    with pytest.raises(ValueError, match="links no register CSV zip"):
        local.fetch(_VOLBY)
    assert local.load(_VOLBY) is None


def test_an_answer_that_is_not_a_zip_is_retried_then_refused(
        monkeypatch: pytest.MonkeyPatch) -> None:
    # A guessed stamp answers an HTML page under a .zip name; read as a
    # body cut short, it is asked for again, and then refused.
    asked = _serve(monkeypatch, kv=b"<html>404 Not Found</html>")
    with pytest.raises(ValueError, match="not a zip"):
        local.fetch(_VOLBY)
    core = importlib.import_module("local_core")
    assert asked.count(f"{volby.VOLBY_SITE}kv2022/{_KV_ZIP}") == core.RETRIES


@pytest.mark.parametrize("missing", list(volby.VOLBY_BOXES))
def test_a_register_missing_a_box_s_column_is_refused(
        monkeypatch: pytest.MonkeyPatch, missing: str) -> None:
    header = [c if c != missing else f"{c}_X" for c in _KV_HEADER]
    _serve(monkeypatch, kv=_zip("csv_od/kvrk.csv", _register(header, _KV_ROWS)))
    with pytest.raises(ValueError, match=f"no column {missing}: its layout has changed"):
        local.fetch(_VOLBY)


def test_a_register_without_its_member_is_refused(monkeypatch: pytest.MonkeyPatch) -> None:
    _serve(monkeypatch, kv=_zip("csv/kvrk.csv", _register(_KV_HEADER, _KV_ROWS)))
    with pytest.raises(ValueError, match="holds no csv_od/kvrk.csv"):
        local.fetch(_VOLBY)


#: The fixture with its last candidate's surname box holding a line
#: break, as a free-text box can: a cut just after the break ends the
#: body with one, so only the short last row tells it from a whole one.
_BROKEN = _register(_KV_HEADER, [*_KV_ROWS[:-1], _kv("Ida", "Krátká\r\nDlouhá", "Ing.")])


@pytest.mark.parametrize("body", [
    _BROKEN[:_BROKEN.index("Dlouhá".encode())],
    _register(_KV_HEADER, _KV_ROWS)[:-2],
], ids=["at a line break inside a quoted field", "before the last line break"])
def test_a_register_cut_short_is_refused(monkeypatch: pytest.MonkeyPatch, body: bytes) -> None:
    rows = list(csv.reader(io.StringIO(body.decode(), newline="")))
    assert len(rows) == len(_KV_ROWS) + 1  # the cut passes the row count
    _serve(monkeypatch, kv=_zip("csv_od/kvrk.csv", body))
    with pytest.raises(ValueError, match="last row is cut short"):
        local.fetch(_VOLBY)
    # The control: the whole body, its box's line break read as a space.
    _serve(monkeypatch, kv=_zip("csv_od/kvrk.csv", _BROKEN))
    assert {"jmeno": "Ida", "prijmeni": "Krátká Dlouhá"}.items() <= next(
        r for r in local.fetch(_VOLBY).records if r["jmeno"] == "Ida").items()


def test_a_register_holding_another_number_of_candidates_is_refused(
        monkeypatch: pytest.MonkeyPatch) -> None:
    _serve(monkeypatch, kv=_zip("csv_od/kvrk.csv", _register(_KV_HEADER, _KV_ROWS[:-1])))
    with pytest.raises(ValueError, match="holds 4 candidates where VOLBY_ELECTIONS pins 5"):
        local.fetch(_VOLBY)


@pytest.mark.parametrize(("row", "match"), [
    (_kv("Jan", "Novák") + ["extra"], "not the header's width"),
    (_kv("", "Novák", "Ing."), "no given name or surname"),
    (_kv("Jan", " ", "Ing."), "no given name or surname"),
], ids=["a row too wide", "no given name", "a blank surname"])
def test_a_register_skipping_past_its_share_is_refused(
        monkeypatch: pytest.MonkeyPatch, row: list[str], match: str) -> None:
    rows = [*_KV_ROWS[:-1], row]
    _serve(monkeypatch, kv=_zip("csv_od/kvrk.csv", _register(_KV_HEADER, rows)))
    with pytest.raises(ValueError, match=f"1 of 5 of the kv2022 register's rows are.*{match}"):
        local.fetch(_VOLBY)
    # The control: under a share one row may pass, it is counted, not kept.
    monkeypatch.setattr(volby, "VOLBY_MAX_BAD", 1 / 5)
    detail = local.fetch(_VOLBY).meta["detail"]["kv2022"]
    assert detail["records"] == 3 and len(detail) == 5


def test_a_register_with_its_titles_emptied_is_refused(monkeypatch: pytest.MonkeyPatch) -> None:
    rows = [_kv("Jan", "Novák")] * 4 + [_kv("Eva", "Malá")]
    _serve(monkeypatch, kv=_zip("csv_od/kvrk.csv", _register(_KV_HEADER, rows)))
    with pytest.raises(ValueError, match="0 of the kv2022 register's 5 candidates filed a title"):
        local.fetch(_VOLBY)
    # The control: one titled candidate in five is at the floor.
    rows[-1] = _kv("Eva", "Malá", "Ing.")
    _serve(monkeypatch, kv=_zip("csv_od/kvrk.csv", _register(_KV_HEADER, rows)))
    assert local.fetch(_VOLBY).records


def test_a_register_not_utf8_is_refused(monkeypatch: pytest.MonkeyPatch) -> None:
    # The csv/ folder's copy is in windows-1250, which csv_od/'s is not.
    body = _register(_KV_HEADER, _KV_ROWS).decode().encode("cp1250")
    _serve(monkeypatch, kv=_zip("csv_od/kvrk.csv", body))
    with pytest.raises(ValueError, match="is not UTF-8"):
        local.fetch(_VOLBY)


@pytest.mark.parametrize(("constant", "value", "match"), [
    ("VOLBY_ELECTIONS", {"kv2022": ("csv_od/kvrk.csv", 5)},
     "holds the elections kv2022 ps2025.*reads kv2022"),
    ("VOLBY_READ_VERSION", 99, "composed by version 1 of compose.*version 99"),
])
def test_a_corpus_of_other_elections_or_another_composition_is_refused_on_load(
        monkeypatch: pytest.MonkeyPatch, constant: str, value: object, match: str) -> None:
    _serve(monkeypatch)
    local.fetch(_VOLBY)
    assert local.load(_VOLBY) is not None  # the control
    monkeypatch.setattr(volby, constant, value)
    with pytest.raises(ValueError, match=f"{match}.*fetch {_VOLBY} --refresh"):
        local.load(_VOLBY)
