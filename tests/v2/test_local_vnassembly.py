"""Offline checks on tools/differential/local_vnassembly.py, the
vn-assembly local corpus of Vietnam's National Assembly deputies, and on
how local_agreement.py scores it.

Every name here is invented: the deputies are real people, so their
records stay in the cache. What these pin is how a title is read off an
education, how a record's name is composed, and the fetch's refusals: an
index listing no file, a file of another size or checksum, a file
holding another number of deputies than the index counts, too few
titled, and a corpus derived by another version. The network is a stub
answering by URL.
"""
import hashlib
import importlib
import json
import time
import urllib.error
import urllib.request

import pytest

from nameparser import FAMILY_FIRST_GIVEN_LAST, Parser, Policy

from ._differential_fixtures import _Response, load_tool, own_cache

local = load_tool("local_corpora")
agreement = load_tool("local_agreement")
vn = importlib.import_module("local_vnassembly")

_VN = vn.VN
_FILE = "https://data.example/artifacts/vn_national_assembly/v1/entities.ftm.json"


@pytest.fixture(autouse=True)
def _own_cache(monkeypatch: pytest.MonkeyPatch, tmp_path_factory: pytest.TempPathFactory) -> None:
    own_cache(monkeypatch, tmp_path_factory)


def _person(name: str, education: str = "", **extra: list[str]) -> dict[str, object]:
    return {"id": name, "schema": "Person",
            "properties": {"name": [name], "gender": ["female"], "ethnicity": ["Kinh"],
                           **({"education": [education]} if education else {}), **extra}}


#: A professor, a doctor, a master, an untitled deputy with an alias,
#: and an entity of another schema, which is read past.
_ENTITIES: list[dict[str, object]] = [
    _person("Hồ Thanh Vân", "Đại học chuyên ngành luật; Phó Giáo sư, Tiến sĩ chuyên ngành luật"),
    _person("Đoàn  Minh Khôi", "Tiến sĩ chuyên ngành kinh tế"),
    _person("Lạc Ngọc Bích", "Đại học chuyên ngành y; Thạc sĩ chuyên ngành y tế"),
    _person("Tạ Long", "Đại học chuyên ngành nông nghiệp", alias=["Thượng tọa Thích Minh Tâm"]),
    {"id": "p", "schema": "Position", "properties": {"name": ["Đại biểu Quốc hội"]}},
]


def _ftm(entities: list[dict[str, object]]) -> bytes:
    return "".join(json.dumps(e, ensure_ascii=False) + "\n" for e in entities).encode()


def _serve(monkeypatch: pytest.MonkeyPatch, body: bytes, *, targets: int = 4,
           stated: bytes | None = None, resources: list[dict[str, object]] | None = None
           ) -> list[str]:
    """Answer the index and the FtM file, the index stating `stated`'s
    size and sha1 (`body`'s unless given) and `targets` deputies."""
    stated = body if stated is None else stated
    index = {"updated_at": "2026-11-04T19:43:06", "version": "v1", "target_count": targets,
             "resources": resources if resources is not None else [
                 {"name": "names.txt", "url": "x", "checksum": "y", "size": 1},
                 {"name": vn.VN_RESOURCE, "url": _FILE,
                  "checksum": hashlib.sha1(stated).hexdigest(), "size": len(stated)}]}
    answers = {vn.VN_INDEX: json.dumps(index).encode(), _FILE: body}
    asked: list[str] = []

    def urlopen(request: urllib.request.Request, timeout: int) -> _Response:
        asked.append(request.full_url)
        if request.full_url not in answers:
            raise urllib.error.HTTPError(request.full_url, 404, "Not Found", {}, None)  # type: ignore[arg-type]
        return _Response(answers[request.full_url])
    monkeypatch.setattr(urllib.request, "urlopen", urlopen)
    monkeypatch.setattr(time, "sleep", lambda seconds: None)
    return asked


@pytest.mark.parametrize(("education", "title"), [
    ("Phó Giáo sư, Tiến sĩ chuyên ngành vật lý", "PGS.TS."),
    ("Đại học chuyên ngành y; Tiến sĩ chuyên ngành y khoa - Giáo sư", "GS.TS."),
    ("Phó Giáo sư-Tiến sĩ chuyên ngành kỹ thuật", "PGS.TS."),
    ("Thạc sĩ chuyên ngành luật; Tiến sĩ chuyên ngành luật", "TS."),
    ("Đại học chuyên ngành kinh tế; Thạc sĩ  chuyên ngành kinh tế", "ThS."),
    ("Tiến sĩ khoa học máy tính", "TS."),
    ("Bác sĩ chuyên khoa II; Cử nhân chính trị", ""),
    ("", ""),
])
def test_a_title_is_the_highest_rank_and_degree_the_education_states(
        education: str, title: str) -> None:
    assert vn.title_of(education) == title


def test_a_fetch_composes_each_deputy_s_name_with_the_title_and_keeps_the_official_one(
        monkeypatch: pytest.MonkeyPatch) -> None:
    asked = _serve(monkeypatch, _ftm(_ENTITIES))
    corpus = local.fetch(_VN)
    assert asked == [vn.VN_INDEX, _FILE]
    common = {"gender": "female", "ethnicity": "Kinh"}
    # In the official name's code point order, which puts Đ after Z.
    assert corpus.records == [
        {"name": "PGS.TS. Hồ Thanh Vân", "official": "Hồ Thanh Vân", "title": "PGS.TS.",
         "family": "Hồ", "middle": "Thanh", "given": "Vân", **common},
        {"name": "ThS. Lạc Ngọc Bích", "official": "Lạc Ngọc Bích", "title": "ThS.",
         "family": "Lạc", "middle": "Ngọc", "given": "Bích", **common},
        {"name": "Tạ Long", "official": "Tạ Long", "alias": "Thượng tọa Thích Minh Tâm",
         "family": "Tạ", "given": "Long", **common},
        {"name": "TS. Đoàn Minh Khôi", "official": "Đoàn Minh Khôi", "title": "TS.",
         "family": "Đoàn", "middle": "Minh", "given": "Khôi", **common}]
    assert corpus.meta["data_date"] == "2026-11-04T19:43:06"
    assert corpus.meta["detail"] == {
        "version": "v1", "title_version": vn.TITLE_VERSION, "titled": 3,
        "title PGS.TS.": 1, "title TS.": 1, "title ThS.": 1, "title (none)": 1}
    # Both names are corpus names, an untitled deputy's once.
    assert corpus.meta["names"] == 7


def test_an_index_listing_no_file_is_refused(monkeypatch: pytest.MonkeyPatch) -> None:
    _serve(monkeypatch, _ftm(_ENTITIES), resources=[{"name": vn.VN_RESOURCE, "url": _FILE}])
    with pytest.raises(ValueError, match="lists no entities.ftm.json"):
        local.fetch(_VN)


def test_a_file_of_another_checksum_is_retried_then_refused(
        monkeypatch: pytest.MonkeyPatch) -> None:
    body = _ftm(_ENTITIES)
    asked = _serve(monkeypatch, body, stated=body[:-1] + b" ")
    with pytest.raises(ValueError, match="not the .* the index states"):
        local.fetch(_VN)
    assert asked.count(_FILE) == importlib.import_module("local_core").RETRIES
    assert local.load(_VN) is None


@pytest.mark.parametrize(("entities", "targets", "match"), [
    (_ENTITIES, 5, "holds 4 deputies where the index counts 5"),
    (_ENTITIES[1:], 4, "holds 3 deputies where the index counts 4"),
    ([*_ENTITIES[3:], _person("Mạc Hùng"), _person("Lý An")], 3, "0 of 3 deputies' education"),
    ([*_ENTITIES, _person("Khánh")], 5, "a single word"),
])
def test_a_file_of_another_shape_is_refused(monkeypatch: pytest.MonkeyPatch,
                                            entities: list[dict[str, object]], targets: int,
                                            match: str) -> None:
    _serve(monkeypatch, _ftm(entities), targets=targets)
    with pytest.raises(ValueError, match=match):
        local.fetch(_VN)


def test_a_corpus_derived_by_another_version_is_refused_on_load(
        monkeypatch: pytest.MonkeyPatch) -> None:
    _serve(monkeypatch, _ftm(_ENTITIES))
    local.fetch(_VN)
    assert local.load(_VN) is not None  # the control
    monkeypatch.setattr(vn, "TITLE_VERSION", 99)
    with pytest.raises(ValueError, match=f"derived by version 1 of title_of.*version 99"
                                         f".*fetch {_VN} --refresh"):
        local.load(_VN)


def test_the_score_compares_the_title_and_the_parts(monkeypatch: pytest.MonkeyPatch) -> None:
    # A family-first parser with the default vocabulary reads `TS.` and
    # `ThS.` as titles by their shape (rules/H2) but not the glued
    # `PGS.TS.`, which it reads as the family, moving every part; the
    # title box is scored, never set aside, unlisted words and all.
    _serve(monkeypatch, _ftm(_ENTITIES))
    records = local.fetch(_VN).records
    family_first = Parser(policy=Policy(name_order=FAMILY_FIRST_GIVEN_LAST))
    result = agreement.score(records, agreement.FIELDED[_VN], family_first)
    assert result.scored == {"Kinh": 4} and result.agreed == {"Kinh": 3}
    assert result.misses == {"Kinh": {"title": 1, "family": 1, "middle": 1}}
    assert not result.set_aside
