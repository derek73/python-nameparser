"""Offline checks on tools/vocab/familiar_candidates.py, which draws
candidate familiar forms from CC0 data for a review by hand
(decisions/name-matching, 2026-11-12 ENGLISH ONLY UNTIL REBUILT).

The failures that matter: a pair evidenced by something other than one
person writing their given name two ways (a second given name, a title,
initials, a transliteration), a holder counted twice, a pair already
reviewed proposed again, and a candidate drawn from a compiled list of
familiar forms rather than found in data.
"""
from __future__ import annotations

import ast
import importlib.util
import json
import sys
from pathlib import Path
from types import ModuleType

import pytest

from tests.checkout import require_checkout

require_checkout()

_PATH = Path(__file__).parents[2] / "tools" / "vocab" / "familiar_candidates.py"


def _load() -> ModuleType:
    spec = importlib.util.spec_from_file_location("familiar_candidates", _PATH)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


tool = _load()
_TITLES = frozenset({"dr", "prof"})


def _record(given: str, family: str, credit: str = "",
            other: tuple[str, ...] = (), country: str = "") -> dict[str, object]:
    out: dict[str, object] = {"given": given, "family": family}
    if credit:
        out["credit"] = credit
    if other:
        out["other"] = list(other)
    if country:
        out["country"] = country
    return out


def test_a_holder_writing_the_given_name_two_ways_evidences_a_pair() -> None:
    assert tool.pairs_of(_record("Katarzyna", "Nowak", "Kasia Nowak"),
                         _TITLES) == {("kasia", "katarzyna")}
    # an other name counts as the credit name does, a comma or a title
    # in it aside
    assert tool.pairs_of(_record("Konstantinos", "Papadopoulos",
                                 other=("Dr. Kostas Papadopoulos",)),
                         _TITLES) == {("konstantinos", "kostas")}


@pytest.mark.parametrize("record", [
    # a second given name, not a familiar form
    _record("Maria Teresa", "Rossi", "Teresa Rossi"),
    # another family name: not the same name written two ways
    _record("Katarzyna", "Nowak", "Kasia Kowalska"),
    # three words, the middle one unaccounted for
    _record("Katarzyna", "Nowak", "Kasia A. Nowak"),
    # initials, a single letter, a digit
    _record("Muhammad", "Rahman", "MD Rahman"),
    _record("John", "Smith", "J Smith"),
    _record("John", "Smith", "J2 Smith"),
    # one word written with and without its accent, which the match
    # already reads as one
    _record("José", "García", "Jose García"),
    # the same word
    _record("Anna", "Berg", "Anna Berg"),
    # nothing to compare
    _record("Anna", "Berg"),
    {"given": "Anna"},
])
def test_what_is_not_one_person_writing_one_given_name_two_ways_is_dropped(
        record: dict[str, object]) -> None:
    assert tool.pairs_of(record, _TITLES) == set()


def test_a_pair_in_two_scripts_is_kept_and_shaped_as_one() -> None:
    # a transliteration is recorded for the review, not dropped
    pair = tool.pairs_of(_record("Igor", "Petrenko", "Игорь Petrenko"), _TITLES)
    assert pair == {("igor", "игорь")}
    assert tool.shape("igor", "игорь") == "two-scripts"
    assert tool.shape("olga", "olha") == "spelling"
    assert tool.shape("kasia", "katarzyna") == ""


def test_a_holder_counts_once_whichever_names_they_wrote_it_in() -> None:
    found = tool.mine([
        _record("Katarzyna", "Nowak", "Kasia Nowak", ("Kasia Nowak",), "PL"),
        _record("Kasia", "Lis", "Katarzyna Lis", country="GB"),
        _record("Katarzyna", "Zając", "Kasia Zając"),
    ], _TITLES)
    evidence = found[("kasia", "katarzyna")]
    assert evidence.holders == 3
    assert evidence.countries == {"PL": 1, "GB": 1, "": 1}


def test_a_pair_goes_in_each_language_its_countries_hold_enough_of() -> None:
    languages_of = {"PL": ("pl",), "GB": ("en",), "US": ("en",), "CH": ("de", "fr")}
    assert tool.languages({"PL": 6, "GB": 1, "": 9}, languages_of) == ("pl",)
    assert tool.languages({"PL": 3, "GB": 2, "US": 1}, languages_of) == ("en", "pl")
    # one holder is never enough, whatever its share
    assert tool.languages({"CH": 1}, languages_of) == (tool.SHARED,)
    assert tool.languages({}, languages_of) == (tool.SHARED,)


def test_the_rows_leave_out_the_known_pairs_and_the_thin_ones() -> None:
    found = tool.mine(
        [_record("Katarzyna", f"N{i}", f"Kasia N{i}", country="PL") for i in range(4)]
        + [_record("William", f"S{i}", f"Bill S{i}", country="US") for i in range(4)]
        + [_record("Olga", f"P{i}", f"Olha P{i}", country="UA") for i in range(3)]
        + [_record("Anna", "Z", "Ania Z", country="PL")],
        _TITLES)
    known = {frozenset(("bill", "william"))}
    rows = tool.rows(found, 3, known, {"PL": ("pl",), "UA": ("uk",)},
                     {("kasia", "katarzyna"): 2},
                     spellings=[("allan", "allen"), ("olga", "olha")])
    assert rows == [
        ["kasia", "katarzyna", "orcid", "4", "", "pl", "PL 4", "2"],
        ["olga", "olha", "orcid", "3", "spelling", "uk", "UA 3", "0"],
        # a refused spelling comes back once, with whatever ORCID gives it
        ["allan", "allen", "nicknames-spelling", "0", "spelling", "mul", "", "0"],
    ]
    text = tool.write_tsv(rows)
    assert [list(r.values()) for r in tool.read_tsv(text)] == rows
    with pytest.raises(ValueError, match="header"):
        tool.read_tsv(text.replace("holders", "people", 1))


def test_a_refusal_as_a_spelling_is_no_reviewed_pair(
        monkeypatch: pytest.MonkeyPatch) -> None:
    # the nicknames list's review read its pairs as familiar forms only,
    # so a pair it refused as a spelling is reviewed again for the
    # spelling bar; one refused as anything else is not
    monkeypatch.setattr(tool.familiar, "load_nicknames",
                        lambda: [("william", "bill")])
    monkeypatch.setattr(tool.familiar, "load_exclusions", lambda: {
        ("allen", "allan"): "spelling", ("aaron", "erin"): "different-name"})
    assert tool.known_pairs() == {frozenset(("bill", "william")),
                                  frozenset(("aaron", "erin"))}
    assert tool.refused_spellings() == {("allan", "allen")}


def test_gnd_is_asked_both_ways_once_and_kept(tmp_path: Path) -> None:
    asked: list[tuple[str, str]] = []

    def ask(preferred: str, variant: str) -> int:
        asked.append((preferred, variant))
        return {("Josef", "Sepp"): 5}.get((preferred, variant), 0)

    cache = tmp_path / "gnd.json"
    assert tool.gnd_attest([("josef", "sepp")], cache, ask) == {("josef", "sepp"): 5}
    assert asked == [("Josef", "Sepp"), ("Sepp", "Josef")]
    assert json.loads(cache.read_text(encoding="utf-8")) == {"josef|sepp": 5}
    assert tool.gnd_attest([("josef", "sepp")], cache, ask) == {("josef", "sepp"): 5}
    assert len(asked) == 2


def test_the_pilot_draw_is_seeded_and_stratified_by_holders() -> None:
    candidates = [{"holders": str(n), "a": f"a{n}-{i}"}
                  for n in (3, 4, 7, 20) for i in range(10)]
    drawn = tool.sample(candidates, 8, seed=1)
    assert drawn == tool.sample(candidates, 8, seed=1)
    assert sorted(int(c["holders"]) for c in drawn) == [3, 3, 4, 4, 7, 7, 20, 20]


def test_the_tool_reads_no_list_of_familiar_forms() -> None:
    # a candidate is found in data, never selected from a compiled list
    # (decisions/shipped-data-licences, 2026-11-12 #1370 FACTS WE
    # MEASURE): the tool may read the nicknames list and its refusals,
    # to leave out what was already reviewed, and nothing else that
    # names familiar forms; nam_dict least of all
    tree = ast.parse(_PATH.read_text(encoding="utf-8"))
    names = {n.attr if isinstance(n, ast.Attribute) else n.id
             for n in ast.walk(tree) if isinstance(n, (ast.Attribute, ast.Name))}
    assert not names & {"NAMDICT_FILE", "NAMDICT_FILE_SHA256", "NamDict",
                        "load_pairs", "FAMILIAR", "_familiar_forms"}
    used = {n.attr for n in ast.walk(tree) if isinstance(n, ast.Attribute)
            and isinstance(n.value, ast.Name) and n.value.id == "familiar"}
    assert used == {"load_nicknames", "load_exclusions"}
