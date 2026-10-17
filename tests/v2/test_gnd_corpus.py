"""Offline checks on tools/differential/build_gnd_corpus.py.

The build script is the only part of the GND corpus that touches the
network, so the renderings it writes from a lobid record are pinned here
on hand-written records in lobid's shape, its sampling on a stubbed
search, and the committed files on the invariants the build promises.
tools/ is not a package, so the module is loaded by path, as
_differential_fixtures.py loads compare.py.
"""
import json
from collections import Counter
from collections.abc import Callable
from pathlib import Path
from typing import Any

import pytest

from ._differential_fixtures import load_tool, serve

build = load_tool("build_gnd_corpus")
agreement = load_tool("cldr_agreement")

_PLAIN = build.Stratum("plain", "q", 1)
_FAMILY_FIRST = build.Stratum("cjk", "q", 1, family_first=True)


def _record(written: str, gnd: str = "118540238", **entity: str) -> dict[str, Any]:
    return {"gndIdentifier": gnd, "preferredName": written,
            "preferredNameEntityForThePerson": {k: [v] for k, v in entity.items()}}


def _texts(rows: list[dict[str, Any]]) -> list[tuple[str, str, bool]]:
    return [(row["order"], row["text"], row["composed"]) for row in rows]


# -- renderings ---------------------------------------------------------------

def test_a_surname_record_gives_its_index_form_and_a_composed_one() -> None:
    rows = build.renderings(_record("Gogh, Vincent van", forename="Vincent",
                                    prefix="van", surname="Gogh"), _PLAIN)
    assert _texts(rows) == [("sorting", "Gogh, Vincent van", False),
                            ("givenFirst", "Vincent van Gogh", True)]
    assert rows[0]["fields"] == {"given": "Vincent", "surname-prefix": "van",
                                 "surname-core": "Gogh"}


@pytest.mark.parametrize(("written", "entity"), [
    ("Zuylen van Nijevelt, Julius van",
     {"forename": "Julius", "prefix": "van", "surname": "Zuylen van Nijevelt"}),
    ("Croix, Edmond de La", {"forename": "Edmond", "prefix": "de La", "surname": "Croix"}),
])
def test_the_split_is_compared_only_before_a_one_word_core(
        written: str, entity: dict[str, str]) -> None:
    # A core of several words may hold an unstated particle (the second
    # `van`), so its family is stated whole; a one-word core keeps the split.
    index = build.renderings(_record(written, **entity), _PLAIN)[0]
    split = " " not in entity["surname"]
    assert ("surname-core" in index["fields"]) is split
    assert ("family_particles" in agreement.expected_roles(index["fields"], written)) is split


def test_a_surname_with_no_prefix_is_stated_whole() -> None:
    # GND keeps a particle inside a surname (`Vélez de Guevara`), so a
    # missing prefix is not a statement that there is none. As
    # surname-core it would expect family_particles '' and record the
    # parser's `de` as a disagreement no fix could clear.
    rows = build.renderings(_record("Vélez de Guevara, Luis", forename="Luis",
                                    surname="Vélez de Guevara"), _PLAIN)
    for row in rows:
        assert row["fields"] == {"given": "Luis", "surname": "Vélez de Guevara"}
        assert "family_particles" not in agreement.expected_roles(row["fields"], row["text"])


@pytest.mark.parametrize("mark", build._GLUED)
def test_a_glued_particle_is_stated_whole_where_it_is_glued(mark: str) -> None:
    # `d'` and `Arenberg` are not words of `d'Arenberg`: stated apart, the
    # comparison would expect an empty family no parser fix could match.
    index, composed = build.renderings(
        _record(f"Arenberg, Auguste d{mark}", forename="Auguste",
                prefix=f"d{mark}", surname="Arenberg"), _PLAIN)
    assert composed["text"] == f"Auguste d{mark}Arenberg"
    assert composed["fields"] == {"given": "Auguste", "surname": f"d{mark}Arenberg"}
    assert index["fields"]["surname-prefix"] == f"d{mark}"


def test_a_family_first_area_keeps_the_index_form_only() -> None:
    rows = build.renderings(_record("Zhang, Tingyu", forename="Tingyu",
                                    surname="Zhang"), _FAMILY_FIRST)
    assert _texts(rows) == [("sorting", "Zhang, Tingyu", False)]


def test_a_personal_name_expects_no_family_name() -> None:
    [row] = build.renderings(_record("Björk", personalName="Björk"), _PLAIN)
    assert row["fields"] == {"given": "Björk"}
    assert agreement.expected_roles(row["fields"], row["text"])["family"] == ""


def test_a_regnal_name_is_composed_without_its_name_addition() -> None:
    record = _record("Johann II., Pfalz-Zweibrücken, Pfalzgraf",
                     personalName="Johann", counting="II.",
                     nameAddition="Pfalz-Zweibrücken, Pfalzgraf")
    [row] = build.renderings(record, _PLAIN)
    assert (row["text"], row["composed"]) == ("Johann II.", True)
    assert row["fields"] == {"given": "Johann", "generation": "II."}


def test_a_field_value_is_read_without_its_edge_spaces() -> None:
    [index, _] = build.renderings(_record("Gogh, Vincent", forename=" Vincent ",
                                          surname="Gogh"), _PLAIN)
    assert index["fields"]["given"] == "Vincent"


def _multi(written: str, **entity: list[str]) -> dict[str, Any]:
    return {"gndIdentifier": "1", "preferredName": written,
            "preferredNameEntityForThePerson": entity}


@pytest.mark.parametrize("record", [
    # Grouped by the guard each row is for; the comment names it.
    # a descriptor the fields cannot place
    _record("Eutychios, von Alexandria", personalName="Eutychios",
            nameAddition="von Alexandria"),
    # a nameAddition on a surname record whose index form still matches
    _record("King, Martin", forename="Martin", surname="King", nameAddition="Jr."),
    # a preferred name its fields do not spell
    _record("Gogh, Vincent", forename="Vincent", prefix="van", surname="Gogh"),
    _record("Amha Selassie", personalName="Amha Selassie I."),
    _record("Something else", personalName="Ludwig", counting="II."),
    # a personalName beside surname fields
    _record("Musabbiḥī al-", personalName="Musabbiḥī", prefix="al-"),
    _record("Ludwig II.", personalName="Ludwig", counting="II.",
            prefix="von", surname="Bayern"),
    # a comma inside a field, where the written name agrees
    _record("A, B", personalName="A, B"),
    _record("A, B, C", surname="A, B", forename="C"),
    # a surname with no forename
    _record("Gogh", surname="Gogh"),
    # a field this script does not know
    _record("Björk", personalName="Björk", epithet="the Great"),
    # two values for one field: the plain direct name would lose its number
    _multi("Johann", personalName=["Johann"], counting=["II.", "III."]),
    _multi("A, B", surname=["A", "C"], forename=["B"]),
])
def test_a_record_its_fields_cannot_account_for_is_left_out(
        record: dict[str, Any]) -> None:
    assert build.renderings(record, _PLAIN) == []


def test_the_corpus_holds_each_text_once() -> None:
    rows = [{"text": "Björk", "shape": None}, {"text": "Björk", "shape": None},
            {"text": "Abe, Kōbō", "shape": None}]
    assert build.corpus_lines(rows) == ['"Abe, Kōbō"', '"Björk"']


def test_a_duplicate_rendering_is_refused() -> None:
    row = {"file": "1", "label": "x", "order": "sorting", "text": "A, B"}
    with pytest.raises(ValueError, match="duplicate rendering 1/x/sorting"):
        build.fields_lines([row, dict(row)])


def test_every_stratum_has_a_distinct_label() -> None:
    labels = [stratum.label for stratum in build.STRATA]
    assert len(labels) == len(set(labels))


# -- sampling: pool() and build() on a stubbed search --------------------------

def _stub_search(totals: dict[str, int], members: dict[str, list[dict[str, Any]]],
                 calls: list[tuple[str, int, int]]
                 ) -> Callable[[str, int, int, bool], dict[str, Any]]:
    """A _search answering by the query's id-slice suffix ('' for none)."""
    def search(query: str, size: int, start: int, refresh: bool) -> dict[str, Any]:
        suffix = query.rsplit("gndIdentifier:", 1)[1] if "gndIdentifier:" in query else ""
        calls.append((suffix, size, start))
        return {"totalItems": totals[suffix],
                "member": members.get(suffix, [])[start:start + size]}
    return search


def _people(n: int) -> list[dict[str, Any]]:
    return [_record(f"P{i}", gnd=str(i), personalName=f"P{i}") for i in range(n)]


def test_pool_takes_the_widest_slice_that_fits_and_pages_it_whole(
        monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[tuple[str, int, int]] = []
    totals = {"": build.POOL + 1, "*7": build.POOL, "*07": 3, "*007": 1}
    monkeypatch.setattr(build, "_search", _stub_search(
        totals, {"*7": _people(build.POOL)}, calls))
    records = build.pool(_PLAIN, refresh=False)
    assert len(records) == build.POOL          # total == POOL fits
    pages = [start for suffix, size, start in calls if size == build.PAGE]
    assert pages == list(range(0, build.POOL, build.PAGE))
    assert {suffix for suffix, _, _ in calls} == {"", "*7"}


def test_pool_applies_the_stratum_predicate(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(build, "_search", _stub_search({"": 4}, {"": _people(4)}, []))
    odd = build.Stratum("odd", "q", 1, keep=lambda r: int(r["gndIdentifier"]) % 2 == 1)
    assert [r["gndIdentifier"] for r in build.pool(odd, False)] == ["1", "3"]


@pytest.mark.parametrize(("totals", "members", "message"), [
    ({"": 0}, {}, "matches nothing"),
    ({"": 5}, {"": _people(3)}, "paged for a total of 5"),
    ({"": 2}, {"": [_people(1)[0], _people(1)[0]]}, r"\(1 distinct\)"),
    ({s: build.POOL + 1 for s in build.SLICES}, {}, "add a slice"),
])
def test_pool_refuses_a_stratum_it_cannot_trust(
        monkeypatch: pytest.MonkeyPatch, totals: dict[str, int],
        members: dict[str, list[dict[str, Any]]], message: str) -> None:
    monkeypatch.setattr(build, "_search", _stub_search(totals, members, []))
    with pytest.raises(ValueError, match=message):
        build.pool(_PLAIN, refresh=False)


def test_build_takes_records_once_in_hash_order_up_to_the_quota(
        monkeypatch: pytest.MonkeyPatch) -> None:
    people = _people(6)
    # A refused record that sorts FIRST, so it is met before the quota fills.
    gnd = min((str(i) for i in range(100, 200)),
              key=lambda g: build._order({"gndIdentifier": g}))
    refused = _record("Wrong", gnd=gnd, personalName="Right")
    assert build._order(refused) < min(build._order(p) for p in people)
    first = build.Stratum("first", "a", 2)
    second = build.Stratum("second", "b", 10, least=1)
    pools = {"a": [*people, refused], "b": list(people)}
    monkeypatch.setattr(build, "STRATA", (first, second))
    monkeypatch.setattr(build, "pool", lambda stratum, refresh: pools[stratum.query])
    rows = build.build(refresh=False)
    taken = {label: [r["file"] for r in rows if r["label"] == label]
             for label in ("first", "second")}
    by_hash = [p["gndIdentifier"] for p in sorted(people, key=build._order)]
    # taken in hash order, not input order; the refused record costs no quota
    assert taken["first"] == by_hash[:2]
    # an id the first stratum took is not taken again
    assert taken["second"] == by_hash[2:]


def test_build_stops_before_writing_when_a_stratum_falls_short(
        monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(build, "STRATA", (build.Stratum("thin", "a", 5, least=3),))
    monkeypatch.setattr(build, "pool", lambda stratum, refresh: _people(2))
    with pytest.raises(ValueError, match="thin 2/3"):
        build.build(refresh=False)


# -- the cache ----------------------------------------------------------------



_GOOD = json.dumps({"totalItems": 0, "member": []}).encode()


def test_a_cached_response_is_read_without_fetching(
        monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    fetched = serve(monkeypatch, tmp_path, _GOOD)
    build._get_json({"q": "x"}, refresh=False)
    build._get_json({"q": "x"}, refresh=False)
    assert len(fetched) == 1
    build._get_json({"q": "x"}, refresh=True)
    assert len(fetched) == 2
    assert not list((tmp_path / "gnd").glob("*.part"))


def test_a_response_that_is_not_a_search_result_is_not_cached(
        monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    serve(monkeypatch, tmp_path, b'{"error": "rate limited"}')
    with pytest.raises(ValueError, match="not a lobid search response"):
        build._get_json({"q": "x"}, refresh=False)
    assert not list((tmp_path / "gnd").iterdir())


def test_a_damaged_cache_file_is_named(
        monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    serve(monkeypatch, tmp_path, _GOOD)
    build._get_json({"q": "x"}, refresh=False)
    [cached] = (tmp_path / "gnd").iterdir()
    cached.write_text('{"totalItems": 0, "memb', encoding="utf-8")
    with pytest.raises(ValueError, match=f"{cached.name}.*--refresh"):
        build._get_json({"q": "x"}, refresh=False)


# -- the committed files -------------------------------------------------------

_ROWS = agreement.load_rows(agreement.GND_FIELDS)
_STRATA = {stratum.label: stratum for stratum in build.STRATA}


def test_each_committed_stratum_holds_what_the_build_promises() -> None:
    names = {label: {row["file"] for row in _ROWS if row["label"] == label}
             for label in {row["label"] for row in _ROWS}}
    assert set(names) == set(_STRATA)
    for label, ids in names.items():
        assert _STRATA[label].floor <= len(ids) <= _STRATA[label].quota, label
    # one stratum per person: a person in two would be counted twice
    owners = Counter(len({r["label"] for r in _ROWS if r["file"] == gnd})
                     for gnd in {row["file"] for row in _ROWS})
    assert set(owners) == {1}
    assert not [row for row in _ROWS if _STRATA[row["label"]].family_first
                and row["order"] == "givenFirst"]
