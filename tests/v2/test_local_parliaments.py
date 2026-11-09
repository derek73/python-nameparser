"""Offline checks on tools/differential/local_parliaments.py, the
opensanctions-parliaments local corpus of national parliaments' members.

Every name here is invented: the members are real people, so their
records stay in the cache. What these pin is how a row's name and
aliases become spellings, the filter to people, the record's shape (the
member, the script, the dataset as its group, the form), the groups
view pairing a member's spellings, and the fetch's refusals: an index
stating no targets or no date, an index listing no file, a file of
another size or checksum, another row count than the index's, a file
ending inside a row, a missing column, a malformed row, no people or too
few, a name missing, an id empty or repeated, a cell joined by another
separator, and a corpus fetched over another dataset list, read by
another version or labelled under another script() or Unicode version.
The network is a stub answering by URL.
"""
import hashlib
import importlib
import json
import time
import unicodedata
import urllib.error
import urllib.request

import pytest

from ._differential_fixtures import _Response, load_tool, own_cache

local = load_tool("local_corpora")
parl = importlib.import_module("local_parliaments")
core = importlib.import_module("local_core")

_SOURCE = parl.PARLIAMENTS
_HEADER = ("id,schema,name,aliases,birth_date,countries,addresses,identifiers,sanctions,"
           "phones,emails,program_ids,dataset,first_seen,last_seen,last_change")


@pytest.fixture(autouse=True)
def _own_cache(monkeypatch: pytest.MonkeyPatch, tmp_path_factory: pytest.TempPathFactory) -> None:
    own_cache(monkeypatch, tmp_path_factory)


def _row(id_: str, name: str, aliases: str = "", schema: str = "Person") -> str:
    cells = [id_, schema, name, aliases, *[""] * 12]
    return ",".join(f'"{c}"' for c in cells)


def _csv(*rows: str) -> bytes:
    return ("\n".join([_HEADER, *rows]) + "\n").encode()


#: A Kazakh member with the Kazakh Cyrillic form as an alias, an Indian
#: member with two titled aliases (one repeating the name), and a
#: Portuguese member with a short parliamentary name.
_FILES = {
    "kz_mazhilis": _csv(_row("Q1", "Тилектес Серикбайулы АДАМБЕКОВ",
                             "Тілектес Серікбайұлы АДАМБЕКОВ")),
    "in_sansad": _csv(_row("in-1", "Asha  Devi", "Shrimati Asha Devi;Asha Devi;Smt Asha Devi")),
    "pt_parliament": _csv(_row("pt-1", "Rui Manuel Sá da Costa", "Rui Costa")),
}


def _url(dataset: str) -> str:
    return f"https://data.example/artifacts/{dataset}/v1/targets.simple.csv"


def _serve(monkeypatch: pytest.MonkeyPatch, files: dict[str, bytes], *,
           targets: dict[str, int] | None = None, stated: dict[str, bytes] | None = None,
           resources: list[dict[str, object]] | None = None,
           index_extra: dict[str, object] | None = None) -> list[str]:
    """Answer each dataset's index and its CSV, the index stating the
    file's size and sha1 (`stated`'s instead where given) and its row
    count as the targets (`targets`' instead where given), with
    `index_extra`'s keys laid over every index (None deleting one)."""
    monkeypatch.setattr(parl, "DATASETS", tuple(files))
    answers: dict[str, bytes] = {}
    for i, (dataset, body) in enumerate(files.items()):
        held = (stated or {}).get(dataset, body)
        index = {"updated_at": f"2026-11-0{i + 1}T10:00:00", "version": f"v{i}",
                 "target_count": (targets or {}).get(dataset, body.count(b"\n") - 1),
                 "resources": resources if resources is not None else [
                     {"name": "names.txt", "url": "x", "checksum": "y", "size": 1},
                     {"name": parl.RESOURCE, "url": _url(dataset),
                      "checksum": hashlib.sha1(held).hexdigest(), "size": len(held)}]}
        for key, value in (index_extra or {}).items():
            if value is None:
                index.pop(key)
            else:
                index[key] = value
        answers[parl.INDEX_URL.format(dataset=dataset)] = json.dumps(index).encode()
        answers[_url(dataset)] = body
    asked: list[str] = []

    def urlopen(request: urllib.request.Request, timeout: int) -> _Response:
        asked.append(request.full_url)
        if request.full_url not in answers:
            raise urllib.error.HTTPError(request.full_url, 404, "Not Found", {}, None)  # type: ignore[arg-type]
        return _Response(answers[request.full_url])
    monkeypatch.setattr(urllib.request, "urlopen", urlopen)
    monkeypatch.setattr(time, "sleep", lambda seconds: None)
    return asked


@pytest.mark.parametrize(("values", "spelled"), [
    (("A  B",), ["A B"]),
    (("A B", "A B;C D"), ["A B", "C D"]),
    (("A B; ;C D;",), ["A B", "C D"]),
    (("",), []),
])
def test_a_column_splits_into_its_distinct_spellings(values: tuple[str, ...],
                                                     spelled: list[str]) -> None:
    assert parl.spellings(*values) == spelled


def test_a_fetch_keeps_each_member_s_spellings_with_the_member_script_and_dataset(
        monkeypatch: pytest.MonkeyPatch) -> None:
    asked = _serve(monkeypatch, _FILES)
    corpus = local.fetch(_SOURCE)
    assert asked == [u for d in _FILES for u in (parl.INDEX_URL.format(dataset=d), _url(d))]

    def rec(name: str, entity: str, script: str, form: str) -> dict[str, str]:
        return {"name": name, "entity": entity, "script": script,
                "dataset": entity.partition(":")[0], "form": form}
    assert corpus.records == [
        rec("Тилектес Серикбайулы АДАМБЕКОВ", "kz_mazhilis:Q1", "Cyrillic", "name"),
        rec("Тілектес Серікбайұлы АДАМБЕКОВ", "kz_mazhilis:Q1", "Cyrillic", "alias"),
        # The alias repeating the name is the name, kept once.
        rec("Asha Devi", "in_sansad:in-1", "Latin", "name"),
        rec("Shrimati Asha Devi", "in_sansad:in-1", "Latin", "alias"),
        rec("Smt Asha Devi", "in_sansad:in-1", "Latin", "alias"),
        rec("Rui Manuel Sá da Costa", "pt_parliament:pt-1", "Latin", "name"),
        rec("Rui Costa", "pt_parliament:pt-1", "Latin", "alias")]
    assert corpus.meta["data_date"] == "2026-11-03T10:00:00"  # the newest dataset's
    detail = corpus.meta["detail"]
    assert detail["datasets"] == list(_FILES) and detail["read_version"] == parl.READ_VERSION
    assert detail["per_dataset"]["in_sansad"] == {
        "version": "v1", "updated_at": "2026-11-02T10:00:00", "persons": 1, "name": 1,
        "alias": 2}
    assert corpus.meta["names"] == 7


def test_rows_of_another_schema_are_counted_and_read_past(
        monkeypatch: pytest.MonkeyPatch) -> None:
    files = {"ua_rada": _csv(_row("u1", "Іван Петренко"), _row("u2", "Іван Петренко"),
                             _row("o1", "Verkhovna Rada", schema="Organization"))}
    _serve(monkeypatch, files)
    corpus = local.fetch(_SOURCE)
    # Two members of one spelling are two entities, and the corpus holds
    # the spelling once.
    assert [r["entity"] for r in corpus.records] == ["ua_rada:u1", "ua_rada:u2"]
    assert corpus.meta["detail"]["per_dataset"]["ua_rada"]["other schema"] == 1
    assert corpus.meta["names"] == 1


def test_the_groups_view_pairs_a_member_s_spellings_by_script(
        monkeypatch: pytest.MonkeyPatch) -> None:
    _serve(monkeypatch, _FILES)
    grouped = local.group_counts(local.fetch(_SOURCE))
    assert grouped.persons == 3
    assert grouped.groups["Cyrillic / Cyrillic"] == 1
    assert grouped.groups["Latin / Latin"] == 2


@pytest.mark.parametrize("resource", [
    {"name": parl.RESOURCE, "url": "x"},
    {"name": parl.RESOURCE, "url": "x", "checksum": "0" * 40, "size": True},
], ids=["no checksum or size", "a size of true"])
def test_an_index_listing_no_file_is_refused(monkeypatch: pytest.MonkeyPatch,
                                             resource: dict[str, object]) -> None:
    _serve(monkeypatch, _FILES, resources=[resource])
    with pytest.raises(ValueError, match="lists no targets.simple.csv"):
        local.fetch(_SOURCE)


def test_a_file_of_another_checksum_is_retried_then_refused(
        monkeypatch: pytest.MonkeyPatch) -> None:
    body = _FILES["pt_parliament"]
    asked = _serve(monkeypatch, _FILES, stated={"pt_parliament": body[:-2] + b" \n"})
    with pytest.raises(ValueError, match="not the .* the index states"):
        local.fetch(_SOURCE)
    assert asked.count(_url("pt_parliament")) == core.RETRIES
    assert local.load(_SOURCE) is None


_TWO = _csv(_row("a", "Ana Lima"), _row("b", "Bo Dias"))
#: A file of 201 rows cut just after a line break inside the last row's
#: quoted name: the body still ends with a line break, and csv reads the
#: cut row as a short one, which the short-last-row arm alone refuses
#: (one malformed row in 201 is under MAX_BAD).
_WHOLE = _csv(*[_row(f"r{i}", f"Ana Lima{i}") for i in range(200)], _row("z", "Bo\nDias"))
_CUT_AT_A_BREAK = _WHOLE[:_WHOLE.index(b"Bo\n") + 3]


@pytest.mark.parametrize(("body", "targets", "match"), [
    (_TWO, 3, "holds 2 rows where its index counts 3"),
    (_CUT_AT_A_BREAK, 201, "ends inside a row"),
    # Cut with no final line break, which the endswith arm refuses.
    (_TWO[:-20], 2, "ends inside a row"),
    (_TWO[:-1], 2, "ends inside a row"),
    (b"id,schema,name\n" + _TWO.split(b"\n", 1)[1], 2, "has no aliases column"),
    (_csv(_row("a", "Ana Lima"), _row("o", "X", schema="Organization"),
          _row("p", "Y", schema="Organization")), 3, "1 of 3 rows .* are a Person"),
    (_csv(_row("a", "Ana Lima"), _row("b", " ")), 2, "1 of 2 people .* have no name"),
    (_csv(_row("a", "Ana Lima"), _row("", "Bo Dias")), 2, "an empty or repeated id ''"),
    (_csv(_row("a", "Ana Lima"), _row("a", "Bo Dias")), 2, "an empty or repeated id 'a'"),
    (_csv(_row("a", "Ana Lima"), _row("b", "Bo Dias", "Bo D|B. Dias")), 2,
     "1 of 2 people .* separator other than ';'"),
    (_csv(_row("a", "Ana Lima"), _row("b", "Bo Dias\tB. Dias")), 2,
     "1 of 2 people .* separator other than ';'"),
    # A short row before the last is malformed, not cut.
    (_csv('"b","Person","Bo Dias"', _row("a", "Ana Lima")), 2, "1 of 2 rows .* not 16 fields"),
], ids=["another count", "cut at a break inside a row", "cut inside a row",
        "no final line break", "a column missing", "too few people", "a name missing",
        "an empty id", "a repeated id", "a pipe separator", "a tab separator",
        "a malformed row"])
def test_a_file_of_another_shape_is_refused(monkeypatch: pytest.MonkeyPatch, body: bytes,
                                            targets: int, match: str) -> None:
    _serve(monkeypatch, {"hr_sabor": body}, targets={"hr_sabor": targets})
    with pytest.raises(ValueError, match=match):
        local.fetch(_SOURCE)


def test_a_dataset_of_no_people_is_refused_beside_a_whole_one(
        monkeypatch: pytest.MonkeyPatch) -> None:
    # A file emptied to its header, its index counting no targets, would
    # otherwise pass as a parliament of nobody.
    _serve(monkeypatch, {"hr_sabor": _csv(), "pt_parliament": _FILES["pt_parliament"]})
    with pytest.raises(ValueError, match="hr_sabor's .* holds no Person of its 0 rows"):
        local.fetch(_SOURCE)


@pytest.mark.parametrize(("extra", "match"), [
    ({"target_count": True}, "states no target_count"),
    ({"target_count": "1"}, "states no target_count"),
    ({"target_count": None}, "states no target_count"),
    ({"updated_at": None}, "states no updated_at"),
    ({"updated_at": ""}, "states no updated_at"),
], ids=["targets true", "targets text", "no targets", "no date", "an empty date"])
def test_an_index_stating_no_count_or_date_is_refused(
        monkeypatch: pytest.MonkeyPatch, extra: dict[str, object], match: str) -> None:
    _serve(monkeypatch, _FILES, index_extra=extra)
    with pytest.raises(ValueError, match=match):
        local.fetch(_SOURCE)


def test_a_name_cell_holding_two_names_gives_two_and_is_counted(
        monkeypatch: pytest.MonkeyPatch) -> None:
    _serve(monkeypatch, {"in_sansad": _csv(_row("i", "Ana Lima; Bo Dias", "Smt Ana Lima"))})
    corpus = local.fetch(_SOURCE)
    assert [(r["name"], r["form"]) for r in corpus.records] == [
        ("Ana Lima", "name"), ("Bo Dias", "name"), ("Smt Ana Lima", "alias")]
    assert corpus.meta["detail"]["per_dataset"]["in_sansad"]["name cells split"] == 1


def test_half_the_rows_people_is_enough(monkeypatch: pytest.MonkeyPatch) -> None:
    body = _csv(_row("a", "Ana Lima"), _row("o", "X", schema="Organization"))
    _serve(monkeypatch, {"hr_sabor": body})
    assert local.fetch(_SOURCE).meta["detail"]["per_dataset"]["hr_sabor"]["persons"] == 1


@pytest.mark.parametrize(("module", "constant", "value", "match"), [
    (parl, "DATASETS", ("kz_mazhilis",), "fetched from the datasets"),
    (parl, "READ_VERSION", 99, "read by read version 1.*version 99"),
    (importlib.import_module("local_jrc"), "JRC_READ_VERSION", 99,
     "labelled by version 2 of local_jrc.script.*version 99"),
    (unicodedata, "unidata_version", "0.0.0", "labelled under Unicode .* reads Unicode 0.0.0"),
], ids=["datasets", "read version", "script version", "unicode"])
def test_a_corpus_fetched_another_way_is_refused_on_load(
        monkeypatch: pytest.MonkeyPatch, module: object, constant: str, value: object,
        match: str) -> None:
    _serve(monkeypatch, _FILES)
    local.fetch(_SOURCE)
    assert local.load(_SOURCE) is not None  # the control
    monkeypatch.setattr(module, constant, value)
    with pytest.raises(ValueError, match=f"{match}.*fetch {_SOURCE} --refresh"):
        local.load(_SOURCE)


def test_the_source_pairs_spellings_and_names_its_group() -> None:
    assert _SOURCE in local.ALIKE_SOURCES
    assert local.SOURCES[_SOURCE].group == "dataset"
    assert len(parl.DATASETS) == len(set(parl.DATASETS)) == 23
