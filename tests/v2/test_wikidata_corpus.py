"""Offline checks on tools/differential/build_wikidata_corpus.py.

The build script is the only part of the Wikidata corpus that touches the
network, so the token alignment it applies to a person's written names is
pinned here on hand-written items in wbgetentities' shape. tools/ is not
a package, so the module is loaded by path, as _differential_fixtures.py
loads compare.py.
"""
import json
from collections import Counter
from pathlib import Path
from typing import Any

import pytest

from ._differential_fixtures import load_tool, serve

build = load_tool("build_wikidata_corpus")
agreement = load_tool("cldr_agreement")

_ES = build.Stratum("surname2-es", "Q29", "P1950", "es", 1)
_RU = build.Stratum("patronymic-ru", "Q159", "P5056", "ru", 1)
_IS = build.Stratum("patronymic-is", "Q189", "P5056", "is", 1)
_MY = build.Stratum("patronymic-my", "Q833", "P5056", "ms", 1)


def _claim(value: dict[str, str]) -> dict[str, Any]:
    return {"rank": "normal", "mainsnak": {"snaktype": "value",
                                           "datavalue": {"value": value}}}


def _person(label: str, language: str, native: str = "", female: bool = False,
            **parts: str | list[str]) -> dict[str, Any]:
    claims: dict[str, list[dict[str, Any]]] = {}
    for prop, ids in parts.items():
        claims[prop] = [_claim({"id": i}) for i in ([ids] if isinstance(ids, str) else ids)]
    if native:
        claims["P1559"] = [_claim({"text": native, "language": language})]
    if female:
        claims["P21"] = [_claim({"id": build.FEMALE})]
    return {"labels": {language: {"value": label}}, "claims": claims}


def _names(**labels: str) -> dict[str, Any]:
    """Part items, each labelled in `mul` only."""
    return {qid: {"labels": {"mul": {"value": text}}} for qid, text in labels.items()}


def _texts(rows: list[dict[str, Any]]) -> list[tuple[str, str]]:
    return [(row["order"], row["text"]) for row in rows]


_GGM = _names(Q1="Gabriel", Q2="García", Q3="Márquez")


def test_a_written_name_every_part_covers_gives_one_rendering() -> None:
    person = _person("Gabriel García Márquez", "es",
                     P735="Q1", P734="Q2", P1950="Q3")
    [row] = build.renderings("Q5878", person, _GGM, _ES)
    assert (row["order"], row["shape"], row["composed"]) == ("givenFirst", None, False)
    assert row["fields"] == {"given": "Gabriel", "surname": "García",
                             "surname2": "Márquez"}


def test_a_short_display_name_without_the_second_surname_is_left_out() -> None:
    # Every word is claimed, but the field the stratum exists for is not
    # written, so the name tests nothing about it.
    person = _person("Gabriel García", "es", P735="Q1", P734="Q2", P1950="Q3")
    assert build.renderings("Q5878", person, _GGM, _ES) == []


@pytest.mark.parametrize("label", [
    "Gabriel José García Márquez",       # a word no part claims
    "Gabriel García Márquez (escritor)",  # a disambiguator: no part claims it
    "Gabriel García Márquez García",     # a part found in two places
])
def test_a_name_not_covered_once_per_word_is_left_out(label: str) -> None:
    person = _person(label, "es", P735="Q1", P734="Q2", P1950="Q3")
    assert build.renderings("Q5878", person, _GGM, _ES) == []


def test_a_connective_joins_the_part_after_it() -> None:
    names = _names(Q1="Josep", Q2="Carreras", Q3="Coll")
    person = _person("Josep Carreras i Coll", "es", P735="Q1", P734="Q2", P1950="Q3")
    [row] = build.renderings("Q1", person, names, _ES)
    assert row["fields"]["surname2"] == "i Coll"
    names = _names(Q1="Mohamed", Q4="Hamzah")
    person = _person("Mohamed bin Hamzah", "ms", P735="Q1", P5056="Q4")
    [row] = build.renderings("Q2", person, names, _MY)
    assert row["fields"] == {"given": "Mohamed", "patronymic": "bin Hamzah"}


def test_a_given_name_and_for_a_second_surname_the_first_are_required() -> None:
    # Each is stated, but not written: the rendering would test a split
    # the source did not show.
    for label in ("Gabriel Márquez", "García Márquez"):
        person = _person(label, "es", P735="Q1", P734="Q2", P1950="Q3")
        assert build.renderings("Q5878", person, _GGM, _ES) == [], label


def test_one_rendering_per_order_and_the_native_name_wins() -> None:
    names = {**_GGM, **_names(Q4="José")}
    person = _person("Gabriel José García Márquez", "es",
                     native="Gabriel García Márquez",
                     P735=["Q1", "Q4"], P734="Q2", P1950="Q3")
    assert _texts(build.renderings("Q5878", person, names, _ES)) == [
        ("givenFirst", "Gabriel García Márquez")]


def test_the_widest_spelling_of_a_part_claims_its_words() -> None:
    # `María` and `María José` are both spellings of one given-name item;
    # the narrower match inside the wider one is not a second place.
    assert build.align("María José Pérez", [
        ("given", {"María", "María José"}), ("surname", {"Pérez"})]) == {
            "given": [0, 1], "surname": [2]}


def test_a_comma_may_only_end_a_part() -> None:
    assert build.align("Мария, Анна Иванова", [
        ("given", {"Мария Анна"}), ("surname", {"Иванова"})]) is None
    assert build.align("Иванова, Мария Анна", [
        ("given", {"Мария Анна"}), ("surname", {"Иванова"})]) == {
            "given": [1, 2], "surname": [0]}


def test_a_connective_carrying_a_comma_joins_nothing() -> None:
    assert build.align("Josep Carreras i, Coll", [
        ("given", {"Josep"}), ("surname", {"Carreras"}),
        ("surname2", {"Coll"})]) is None


def test_malay_connectives_may_be_capitalized() -> None:
    names = _names(Q1="Mohamed", Q4="Hamzah")
    person = _person("Mohamed Bin Hamzah", "ms", P735="Q1", P5056="Q4")
    [row] = build.renderings("Q2", person, names, _MY)
    assert row["fields"]["patronymic"] == "Bin Hamzah"


def test_a_capital_letter_is_not_a_connective() -> None:
    names = _names(Q1="Josep", Q2="Carreras", Q3="Coll")
    person = _person("Josep Carreras I Coll", "es", P735="Q1", P734="Q2", P1950="Q3")
    assert build.renderings("Q1", person, names, _ES) == []


def test_one_item_stated_as_two_parts_is_left_out() -> None:
    # A person whose P734 and P5056 are the same item, seen in Malaysian data.
    names = _names(Q1="Salma", Q2="Ismail")
    person = _person("Salma Ismail", "ms", P735="Q1", P734="Q2", P5056="Q2")
    assert build.renderings("Q1", person, names, _MY) == []


def test_a_womans_russian_surname_matches_the_feminine_form() -> None:
    names = _names(Q1="Елена", Q2="Лядов", Q3="Игоревна")
    person = _person("Елена Игоревна Лядова", "ru", female=True,
                     P735="Q1", P734="Q2", P5056="Q3")
    [row] = build.renderings("Q1", person, names, _RU)
    assert row["fields"]["surname"] == "Лядова"
    # ... for a woman only.
    man = _person("Елена Игоревна Лядова", "ru", P735="Q1", P734="Q2", P5056="Q3")
    assert build.renderings("Q1", man, names, _RU) == []


def test_a_womans_surname_with_no_masculine_ending_still_matches() -> None:
    # feminine() has nothing to offer here; an empty spelling must not be
    # added, or it would match everywhere and drop the name.
    names = _names(Q1="Анна", Q2="Пастернак", Q3="Ивановна")
    person = _person("Анна Ивановна Пастернак", "ru", female=True,
                     P735="Q1", P734="Q2", P5056="Q3")
    assert len(build.renderings("Q1", person, names, _RU)) == 1


@pytest.mark.parametrize(("male", "female"), [
    ("Достоевский", "Достоевская"), ("Трубецкой", "Трубецкая"),
    ("Белый", "Белая"), ("Иванов", "Иванова"), ("Лебедев", "Лебедева"),
    ("Горбачёв", "Горбачёва"), ("Пушкин", "Пушкина"), ("Лисицын", "Лисицына"),
    ("Высоцкий", "Высоцкая"), ("Пастернак", "")])
def test_feminine_forms(male: str, female: str) -> None:
    assert build.feminine(male) == female


def test_a_part_found_only_through_its_native_label() -> None:
    names = {"Q1": {"labels": {}, "claims": {"P1705": [_claim(
        {"text": "Юрий", "language": "ru"})]}}, **_names(Q2="Кушнарёв", Q3="Викторович")}
    person = _person("Юрий Викторович Кушнарёв", "ru", P735="Q1", P734="Q2", P5056="Q3")
    [row] = build.renderings("Q1", person, names, _RU)
    assert row["fields"]["given"] == "Юрий"


def test_a_sorting_label_and_a_native_name_are_two_renderings() -> None:
    names = _names(Q1="Юрий", Q2="Кушнарёв", Q3="Викторович")
    person = _person("Кушнарёв, Юрий Викторович", "ru",
                     native="Юрий Викторович Кушнарёв",
                     P735="Q1", P734="Q2", P5056="Q3")
    rows = build.renderings("Q1", person, names, _RU)
    assert _texts(rows) == [("givenFirst", "Юрий Викторович Кушнарёв"),
                            ("sorting", "Кушнарёв, Юрий Викторович")]
    assert rows[1]["fields"]["surname"] == "Кушнарёв"


def test_a_second_surname_written_first_is_family_first_too() -> None:
    assert build._order("Márquez García Gabriel",
                        {"surname2": [0], "surname": [1], "given": [2]}) == (
        "surnameFirst", build.FAMILY_FIRST_SHAPE)


def test_family_first_without_a_comma_carries_the_family_first_shape() -> None:
    names = _names(Q1="Юрий", Q2="Кушнарёв", Q3="Викторович")
    person = _person("Кушнарёв Юрий Викторович", "ru",
                     P735="Q1", P734="Q2", P5056="Q3")
    [row] = build.renderings("Q1", person, names, _RU)
    assert (row["order"], row["shape"]) == ("surnameFirst", build.FAMILY_FIRST_SHAPE)
    assert build.corpus_lines([row]) == [
        '{"name": "Кушнарёв Юрий Викторович", "shape": 4}']


def test_a_patronymic_expects_no_family_name() -> None:
    names = _names(Q1="Vigdís", Q2="Finnbogadóttir")
    person = _person("Vigdís Finnbogadóttir", "is", P735="Q1", P5056="Q2")
    [row] = build.renderings("Q1", person, names, _IS)
    assert agreement.expected_roles(row["fields"], row["text"])["family"] == ""


def test_every_field_occurs_in_its_rendering() -> None:
    # A field that did not occur would be expected EMPTY by the comparison,
    # a disagreement no parser fix could resolve; the glued comma of a
    # sorting form is the case to watch.
    names = _names(Q1="Юрий", Q2="Кушнарёв", Q3="Викторович")
    person = _person("Кушнарёв, Юрий Викторович", "ru",
                     P735="Q1", P734="Q2", P5056="Q3")
    for row in build.renderings("Q1", person, names, _RU):
        for value in row["fields"].values():
            assert agreement.occurs(value, row["text"]), (row["text"], value)


_ROWS = agreement.load_rows(agreement.WIKIDATA_FIELDS)


def test_every_committed_rendering_is_covered_by_its_fields() -> None:
    # The comparison reads a missing field as an EMPTY role. That is
    # sound here only because the fields claim every word of the text:
    # an absent P734 or P5056 means "not entered", and would otherwise
    # leave a word whose role the comparison wrongly expects empty.
    uncovered = [row["text"] for row in _ROWS
                 if not agreement.same(" ".join(row["fields"].values()),
                                       row["text"], row["text"])]
    assert not uncovered
    assert len(_ROWS) > 500, "the Wikidata fields file is missing or truncated"


def test_a_deprecated_or_valueless_statement_is_ignored() -> None:
    item = {"claims": {"P734": [
        {**_claim({"id": "Q1"}), "rank": "deprecated"},
        {"rank": "normal", "mainsnak": {"snaktype": "novalue"}},
        _claim({"id": "Q2"})]}}
    assert build.statements(item, "P734") == ["Q2"]


def test_a_duplicate_rendering_is_refused() -> None:
    row = {"file": "Q1", "label": "x", "order": "sorting", "text": "A, B"}
    with pytest.raises(ValueError, match="duplicate rendering Q1/x/sorting"):
        build.fields_lines([row, dict(row)])


def test_every_stratum_has_a_distinct_label() -> None:
    labels = [stratum.label for stratum in build.STRATA]
    assert len(labels) == len(set(labels))


# -- the build ----------------------------------------------------------------

def _stub_build(monkeypatch: pytest.MonkeyPatch, strata: tuple[Any, ...],
                pooled: dict[str, list[str]]) -> None:
    people = {q: _person("Gabriel García Márquez", "es", P735="Q1", P734="Q2",
                         P1950="Q3") for qs in pooled.values() for q in qs}
    monkeypatch.setattr(build, "STRATA", strata)
    monkeypatch.setattr(build, "pool", lambda stratum, refresh: pooled[stratum.label])
    monkeypatch.setattr(build, "entities", lambda ids, props, refresh:
                        {**{q: people[q] for q in ids if q in people},
                         **{q: _GGM[q] for q in ids if q in _GGM}})


def test_build_takes_each_person_once_up_to_the_quota(
        monkeypatch: pytest.MonkeyPatch) -> None:
    first = build.Stratum("first", "Q29", "P1950", "es", 2)
    second = build.Stratum("second", "Q96", "P1950", "es", 2)
    _stub_build(monkeypatch, (first, second),
                {"first": ["Q10", "Q11", "Q12"], "second": ["Q11", "Q13", "Q14"]})
    taken = {lab: [r["file"] for r in build.build(refresh=False) if r["label"] == lab]
             for lab in ("first", "second")}
    assert taken == {"first": ["Q10", "Q11"], "second": ["Q13", "Q14"]}


def test_build_stops_before_writing_when_a_stratum_falls_short(
        monkeypatch: pytest.MonkeyPatch) -> None:
    thin = build.Stratum("thin", "Q833", "P1950", "es", 5, least=3)
    _stub_build(monkeypatch, (thin,), {"thin": ["Q10", "Q11"]})
    with pytest.raises(ValueError, match="thin 2/3"):
        build.build(refresh=False)


def test_a_query_takes_as_many_people_as_the_pool_check_expects() -> None:
    # endswith: "LIMIT 6" is also a prefix of "LIMIT 60"
    assert build.query(_RU).endswith(f"LIMIT {_RU.size}")


# -- the network and the cache ------------------------------------------------

def _results(n: int) -> bytes:
    return json.dumps({"results": {"bindings": [
        {"item": {"value": f"http://www.wikidata.org/entity/Q{7747 + i}"}}
        for i in range(n)]}}).encode()


# a pool the size of _RU's (quota 1, six times that)
_RESULTS = _results(build.POOL_FACTOR)


def test_a_query_is_posted_as_json_and_the_fetch_waits_after_it(
        monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    requests: list[Any] = []
    sleeps: list[float] = []
    serve(monkeypatch, tmp_path, _RESULTS, requests=requests, sleeps=sleeps)
    build.pool(_RU, refresh=False)
    [request] = requests
    assert request.get_method() == "POST" and b"query=" in request.data
    assert request.get_header("Accept") == "application/json"
    assert request.get_header("User-agent") == build.USER_AGENT
    assert sleeps == [1]


def test_a_cached_response_is_read_without_fetching(
        monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    fetched = serve(monkeypatch, tmp_path, _RESULTS)
    assert build.pool(_RU, refresh=False)[0] == "Q7747"
    assert len(build.pool(_RU, refresh=False)) == build.POOL_FACTOR
    assert len(fetched) == 1
    build.pool(_RU, refresh=True)
    assert len(fetched) == 2
    assert not list((tmp_path / "wikidata").glob("*.part"))


@pytest.mark.parametrize("body", [
    b'{"error": {"code": "maxlag", "info": "Waiting for a database server"}}',
    b'<html>Query timeout</html>'])
def test_a_response_that_is_not_what_was_asked_for_is_not_cached(
        monkeypatch: pytest.MonkeyPatch, tmp_path: Path, body: bytes) -> None:
    serve(monkeypatch, tmp_path, body)
    with pytest.raises(ValueError, match="not JSON|has no 'entities'.*maxlag"):
        build.entities(["Q1"], "labels", refresh=False)
    assert not list((tmp_path / "wikidata").iterdir())


def test_a_damaged_cache_file_is_named(
        monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    serve(monkeypatch, tmp_path, _RESULTS)
    build.pool(_RU, refresh=False)
    [cached] = (tmp_path / "wikidata").iterdir()
    cached.write_text('{"results": {"bind', encoding="utf-8")
    with pytest.raises(ValueError, match=f"{cached.name}.*--refresh"):
        build.pool(_RU, refresh=False)


def test_a_query_matching_nothing_stops_the_build(
        monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    serve(monkeypatch, tmp_path, b'{"results": {"bindings": []}}')
    with pytest.raises(ValueError, match="patronymic-ru: the query matches nothing"):
        build.pool(_RU, refresh=False)


def test_a_pool_short_of_its_size_stops_the_build_unless_it_is_the_whole(
        monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    serve(monkeypatch, tmp_path, _results(3))
    with pytest.raises(ValueError, match="patronymic-ru: the query matched 3 people, "
                                         "fewer than its pool of 6"):
        build.pool(_RU, refresh=False)
    assert len(build.pool(_RU._replace(whole=True), refresh=False)) == 3


def test_a_stratum_marked_whole_whose_pool_fills_stops_the_build(
        monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    serve(monkeypatch, tmp_path, _results(build.POOL_FACTOR))
    with pytest.raises(ValueError, match="patronymic-ru: marked whole=True, but the "
                                         "query filled"):
        build.pool(_RU._replace(whole=True), refresh=False)


def test_an_item_the_response_leaves_out_stops_the_build(
        monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    serve(monkeypatch, tmp_path, b'{"entities": {"Q1": {"id": "Q1"}}}')
    with pytest.raises(ValueError, match="left out Q2"):
        build.entities(["Q1", "Q2"], "labels", refresh=False)


def test_a_missing_person_stops_the_build_and_a_missing_part_does_not(
        monkeypatch: pytest.MonkeyPatch) -> None:
    # A pooled person must exist; a deleted name-part item only refuses
    # the person stating it (it has no spellings), which --refresh could
    # not fix anyway.
    stratum = build.Stratum("s", "Q29", "P1950", "es", 1, least=0)
    _stub_build(monkeypatch, (stratum,), {"s": ["Q10"]})
    deleted = {"id": "Q1", "missing": ""}
    real = build.entities
    monkeypatch.setattr(build, "entities", lambda ids, props, refresh: {
        **real(ids, props, refresh), **({"Q1": deleted} if "Q1" in ids else {})})
    assert build.build(refresh=False) == []  # the part: the person is refused
    monkeypatch.setattr(build, "entities", lambda ids, props, refresh: {
        **real(ids, props, refresh), **({"Q10": deleted} if "Q10" in ids else {})})
    with pytest.raises(ValueError, match="s: WDQS pooled items .*missing: Q10"):
        build.build(refresh=False)


# -- the committed files, by stratum ---------------------------------------------

_STRATA = {stratum.label: stratum for stratum in build.STRATA}


def test_each_committed_stratum_holds_what_the_build_promises() -> None:
    names = {label: {row["file"] for row in _ROWS if row["label"] == label}
             for label in {row["label"] for row in _ROWS}}
    assert set(names) == set(_STRATA)
    for label, ids in names.items():
        assert _STRATA[label].floor <= len(ids) <= _STRATA[label].quota, label
    # one stratum per person: a person in two would be counted twice
    owners = Counter(len({r["label"] for r in _ROWS if r["file"] == qid})
                     for qid in {row["file"] for row in _ROWS})
    assert set(owners) == {1}
    # and every rendering writes its stratum's own field
    assert not [row["text"] for row in _ROWS
                if build.PARTS[_STRATA[row["label"]].prop] not in row["fields"]]
