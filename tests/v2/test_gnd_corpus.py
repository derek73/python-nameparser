"""Offline checks on tools/differential/build_gnd_corpus.py.

The build script is the only part of the GND corpus that touches the
network, so the renderings it writes from a lobid record are pinned here
on hand-written records in lobid's shape. tools/ is not a package, so the
module is loaded by path, as _differential_fixtures.py loads compare.py.
"""
from typing import Any

import pytest

from ._differential_fixtures import load_tool

build = load_tool("build_gnd_corpus")
agreement = load_tool("cldr_agreement")

_PLAIN = build.Stratum("plain", "q", 1)
_FAMILY_FIRST = build.Stratum("cjk", "q", 1, family_first=True)


def _record(written: str, **entity: str) -> dict[str, Any]:
    return {"gndIdentifier": "118540238", "preferredName": written,
            "preferredNameEntityForThePerson": {k: [v] for k, v in entity.items()}}


def _texts(rows: list[dict[str, Any]]) -> list[tuple[str, str, bool]]:
    return [(row["order"], row["text"], row["composed"]) for row in rows]


def test_a_surname_record_gives_its_index_form_and_a_composed_one() -> None:
    rows = build.renderings(_record("Gogh, Vincent van", forename="Vincent",
                                    prefix="van", surname="Gogh"), _PLAIN)
    assert _texts(rows) == [("sorting", "Gogh, Vincent van", False),
                            ("givenFirst", "Vincent van Gogh", True)]
    assert rows[0]["fields"] == {"given": "Vincent", "surname-prefix": "van",
                                 "surname-core": "Gogh"}


def test_every_field_occurs_in_every_rendering() -> None:
    # A field that did not occur would be expected EMPTY by the
    # comparison, a disagreement no parser fix could resolve. That is
    # what a glued particle did before its composed line stated the word
    # whole: `d'` and `Arenberg` are not words of `d'Arenberg`.
    for written, entity in [
            ("Arenberg, Auguste d'", {"forename": "Auguste", "prefix": "d'",
                                      "surname": "Arenberg"}),
            ("Ǧaʿfarī, Ibrāhīm al-", {"forename": "Ibrāhīm", "prefix": "al-",
                                     "surname": "Ǧaʿfarī"}),
            ("García Márquez, Gabriel", {"forename": "Gabriel",
                                         "surname": "García Márquez"})]:
        for row in build.renderings(_record(written, **entity), _PLAIN):
            for value in row["fields"].values():
                assert agreement.occurs(value, row["text"]), (row["text"], value)


def test_a_glued_particle_is_stated_whole_where_it_is_glued() -> None:
    index, composed = build.renderings(
        _record("Arenberg, Auguste d'", forename="Auguste", prefix="d'",
                surname="Arenberg"), _PLAIN)
    assert composed["text"] == "Auguste d'Arenberg"
    assert composed["fields"] == {"given": "Auguste", "surname": "d'Arenberg"}
    assert index["fields"]["surname-prefix"] == "d'"


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


@pytest.mark.parametrize("record", [
    # a descriptor the fields cannot place
    _record("Eutychios, von Alexandria", personalName="Eutychios",
            nameAddition="von Alexandria"),
    _record("King, Martin Luther, Jr.", forename="Martin Luther",
            surname="King", nameAddition="Jr."),
    # a preferred name its fields do not spell
    _record("Gogh, Vincent", forename="Vincent", prefix="van", surname="Gogh"),
    _record("Amha Selassie", personalName="Amha Selassie I."),
    # two values for one field
    {"gndIdentifier": "1", "preferredName": "A, B",
     "preferredNameEntityForThePerson": {"surname": ["A", "C"], "forename": ["B"]}},
])
def test_a_record_its_fields_cannot_account_for_is_left_out(
        record: dict[str, Any]) -> None:
    assert build.renderings(record, _PLAIN) == []


def test_the_corpus_holds_each_text_once() -> None:
    rows = [{"text": "Björk"}, {"text": "Björk"}, {"text": "Abe, Kōbō"}]
    assert build.corpus_lines(rows) == ['"Abe, Kōbō"', '"Björk"']


def test_a_duplicate_rendering_is_refused() -> None:
    row = {"file": "1", "label": "x", "order": "sorting", "text": "A, B"}
    with pytest.raises(ValueError, match="duplicate rendering 1/x/sorting"):
        build.fields_lines([row, dict(row)])


def test_every_stratum_has_a_distinct_label() -> None:
    labels = [stratum.label for stratum in build.STRATA]
    assert len(labels) == len(set(labels))
