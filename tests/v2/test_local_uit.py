"""Offline checks on tools/differential/local_uit.py, the uit-vinames
local corpus of Vietnamese full names, and on how local_agreement.py
scores it.

Every name here is invented: the dataset's names are real people's, so
they stay in the cache. What these pin is the convention a record's
parts are derived by, what a fetch keeps (one record per distinct name,
its gender, its parts), and the fetch's refusals: a zip other than the
pinned one, a member of another header or row count, a row that is not
a name and a gender, and a corpus split by another version. The network
is a stub answering the pinned URL.
"""
import csv
import hashlib
import importlib
import io
import time
import urllib.error
import urllib.request
import zipfile

import pytest

from nameparser import FAMILY_FIRST_GIVEN_LAST, Parser, Policy

from ._differential_fixtures import _Response, load_tool, own_cache

local = load_tool("local_corpora")
agreement = load_tool("local_agreement")
# The module the fetch reads its constants from, by name (test_local_corpora.py).
uit = importlib.import_module("local_uit")

_UIT = uit.UIT


@pytest.fixture(autouse=True)
def _own_cache(monkeypatch: pytest.MonkeyPatch, tmp_path_factory: pytest.TempPathFactory) -> None:
    own_cache(monkeypatch, tmp_path_factory)


#: A name twice under one gender (once padded), a name under both
#: genders, a two-word name, a one-word name: 7 rows, 4 records.
_ROWS = [["Phạm Minh Châu", "1"], [" Phạm  Minh Châu ", "1"], ["Lưu Thị Ngân Hà", "0"],
         ["Lưu Thị Ngân Hà", "1"], ["Võ Khoa", "1"], ["Trịnh Bảo", "0"], ["Hiền", "0"]]


def _zip(rows: list[list[str]], *, header: tuple[str, ...] = uit.UIT_COLUMNS) -> bytes:
    out = io.StringIO(newline="")
    csv.writer(out, lineterminator="\r\n").writerows([list(header), *rows])
    archive = io.BytesIO()
    # A fixed timestamp, so the zip, a parameter below whose bytes name its
    # test, is the same in every worker process.
    with zipfile.ZipFile(archive, "w") as z:
        z.writestr(zipfile.ZipInfo(uit.UIT_MEMBER, (2020, 10, 27, 5, 52, 0)),
                   out.getvalue().encode("utf-8"))
        z.writestr(zipfile.ZipInfo("UIT-ViNames/Readme.docx", (2020, 10, 27, 7, 42, 0)), b"")
    return archive.getvalue()


def _serve(monkeypatch: pytest.MonkeyPatch, body: bytes, *, pin: bytes | None = None,
           rows: int | None = None) -> list[str]:
    """Answer the pinned URL with `body`, the pins being `pin`'s sha256
    (`body`'s unless given) and `rows` (the fixture's count unless
    given); the URLs asked."""
    monkeypatch.setattr(uit, "UIT_SHA256", hashlib.sha256(pin or body).hexdigest())
    monkeypatch.setattr(uit, "UIT_ROWS", len(_ROWS) if rows is None else rows)
    asked: list[str] = []

    def urlopen(request: urllib.request.Request, timeout: int) -> _Response:
        asked.append(request.full_url)
        if request.full_url != uit.UIT_URL:
            raise urllib.error.HTTPError(request.full_url, 404, "Not Found", {}, None)  # type: ignore[arg-type]
        return _Response(body)
    monkeypatch.setattr(urllib.request, "urlopen", urlopen)
    monkeypatch.setattr(time, "sleep", lambda seconds: None)
    return asked


@pytest.mark.parametrize(("name", "parts"), [
    ("Võ Khoa", {"family": "Võ", "middle": "", "given": "Khoa"}),
    ("Phạm Minh Châu", {"family": "Phạm", "middle": "Minh", "given": "Châu"}),
    ("Lưu Thị Ngân Hà", {"family": "Lưu", "middle": "Thị Ngân", "given": "Hà"}),
])
def test_the_convention_reads_the_first_word_as_the_family_and_the_last_as_the_given(
        name: str, parts: dict[str, str]) -> None:
    assert uit.split(name) == parts


def test_a_one_word_name_has_no_parts_the_convention_tells_apart() -> None:
    with pytest.raises(ValueError, match="no parts"):
        uit.split("Hiền")


def test_a_fetch_keeps_each_distinct_name_once_with_its_gender_and_parts(
        monkeypatch: pytest.MonkeyPatch) -> None:
    asked = _serve(monkeypatch, _zip(_ROWS))
    corpus = local.fetch(_UIT)
    assert asked == [uit.UIT_URL]
    assert corpus.records == [
        {"name": "Lưu Thị Ngân Hà", "gender": "both", "family": "Lưu", "middle": "Thị Ngân",
         "given": "Hà"},
        {"name": "Phạm Minh Châu", "gender": "male", "family": "Phạm", "middle": "Minh",
         "given": "Châu"},
        {"name": "Trịnh Bảo", "gender": "female", "family": "Trịnh", "given": "Bảo"},
        {"name": "Võ Khoa", "gender": "male", "family": "Võ", "given": "Khoa"}]
    assert corpus.meta["data_date"] == uit.UIT_DATE
    assert corpus.meta["detail"] == {
        "commit": uit.UIT_COMMIT, "rows": len(_ROWS), "read_version": uit.UIT_READ_VERSION,
        "split_version": uit.SPLIT_VERSION, "rows_of_one_word": 1, "names_both": 1, "names_male": 2, "names_female": 1}
    assert corpus.header().endswith("4 names (local corpus uit-vinames)")


def test_a_zip_other_than_the_pinned_one_is_retried_then_refused(
        monkeypatch: pytest.MonkeyPatch) -> None:
    asked = _serve(monkeypatch, _zip(_ROWS), pin=b"another zip")
    with pytest.raises(ValueError, match="not the pinned"):
        local.fetch(_UIT)
    assert asked.count(uit.UIT_URL) == importlib.import_module("local_core").RETRIES
    assert local.load(_UIT) is None


@pytest.mark.parametrize(("body", "rows", "match"), [
    (_zip(_ROWS, header=("Name", "Gender")), None, "is not the 7 rows of Full_Name, Gender"),
    (_zip(_ROWS), len(_ROWS) + 1, "is not the 8 rows"),
    (_zip([*_ROWS, ["Đỗ Hải", "2"]]), len(_ROWS) + 1, "not a name and a gender 0/1"),
    (_zip([*_ROWS, ["Đỗ Hải", "1", "x"]]), len(_ROWS) + 1, "not a name and a gender 0/1: 3 fields"),
])
def test_a_member_of_another_shape_is_refused(monkeypatch: pytest.MonkeyPatch, body: bytes,
                                              rows: int | None, match: str) -> None:
    _serve(monkeypatch, body, rows=rows)
    with pytest.raises(ValueError, match=match):
        local.fetch(_UIT)


@pytest.mark.parametrize(("constant", "match"), [
    ("UIT_READ_VERSION", "read by version 1 of _uit_read.*version 99"),
    ("SPLIT_VERSION", "split by version 1 of split.*version 99"),
])
def test_a_corpus_read_or_split_by_another_version_is_refused_on_load(
        monkeypatch: pytest.MonkeyPatch, constant: str, match: str) -> None:
    _serve(monkeypatch, _zip(_ROWS))
    local.fetch(_UIT)
    assert local.load(_UIT) is not None  # the control
    monkeypatch.setattr(uit, constant, 99)
    with pytest.raises(ValueError, match=f"{match}.*fetch {_UIT} --refresh"):
        local.load(_UIT)


def test_the_score_compares_each_part_with_the_convention_s(
        monkeypatch: pytest.MonkeyPatch) -> None:
    # The convention is family first, so the default reading (given first)
    # misses both ends and a family-first one agrees: the control.
    _serve(monkeypatch, _zip(_ROWS))
    records = local.fetch(_UIT).records
    fielded = agreement.FIELDED[_UIT]
    family_first = Parser(policy=Policy(name_order=FAMILY_FIRST_GIVEN_LAST))
    assert agreement.score(records, fielded, family_first).agreed == {"Male": 2, "Female": 1,
                                                                     "Both": 1}
    default = agreement.score(records, fielded, Parser())
    assert sum(default.agreed.values()) == 0
    assert set(default.entries) == {agreement.key(r) for r in records}


def test_the_middle_name_is_scored_apart_from_the_given_name() -> None:
    # A record whose middle name the convention reads otherwise than the
    # parse: the middle alone misses, which ORCID's given-names box,
    # holding both, could not tell.
    record = {"name": "Phạm Minh Đức Châu", "gender": "male", "family": "Phạm",
              "middle": "Minh", "given": "Đức Châu"}
    family_first = Parser(policy=Policy(name_order=FAMILY_FIRST_GIVEN_LAST))
    result = agreement.score([record], agreement.FIELDED[_UIT], family_first)
    assert result.misses == {"Male": {"middle": 1, "given": 1}}
    assert result.shapes == {"middle 1->2, given 2->1": 1}
