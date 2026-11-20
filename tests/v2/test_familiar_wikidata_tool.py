"""Offline checks on tools/vocab/familiar_wikidata.py, which draws
candidate familiar forms from Wikidata's people, per language, for a
review by hand (decisions/name-matching, 2026-11-20 #1387).

The failures that matter: a pair evidenced by something other than one
person named two ways (a changed surname, a stage name, a patronymic, a
second given name), a person counted twice, a pair placed in a language
it was not found in, an answer cut by a timeout kept as whole, and a
candidate drawn from a compiled list of familiar forms.
"""
from __future__ import annotations

import ast
import importlib.util
import sys
from pathlib import Path
from types import ModuleType

import pytest

from tests.checkout import require_checkout

require_checkout()

_PATH = Path(__file__).parents[2] / "tools" / "vocab" / "familiar_wikidata.py"


def _load() -> ModuleType:
    spec = importlib.util.spec_from_file_location("familiar_wikidata", _PATH)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


tool = _load()
_TITLES = frozenset({"dr", "prof"})

#: Item labels: given names Q1 József, Q2 István, Q3 Erzsébet, Q4 Anna,
#: Q5 Katalin (in `mul` only), Q8 Иван; family names Q10 Kovács,
#: Q11 Nagy, Q12 Kiss, Q13 Иванов.
_LABELS = {
    "Q1": {"hu": {"József"}, "mul": {"József"}},
    "Q2": {"hu": {"István"}},
    "Q3": {"hu": {"Erzsébet"}},
    "Q4": {"hu": {"Anna"}},
    "Q5": {"mul": {"Katalin"}},
    "Q8": {"ru": {"Иван"}},
    "Q10": {"hu": {"Kovács"}},
    "Q11": {"hu": {"Nagy"}},
    "Q12": {"hu": {"Kiss"}},
    "Q13": {"ru": {"Иванов"}},
}


def _found(person: object, tags: tuple[str, ...] = ("hu",)) -> set[tuple[str, str, str]]:
    return {(f.x, f.y, f.relation)
            for f in tool.relations(person, _LABELS, tags, _TITLES)}


def test_the_label_against_the_given_name_reads_a_family_first_name() -> None:
    # Hungarian writes the family name first; the pair is the word
    # left once the family name is set aside, not a position
    p = tool.Person(given={"Q1"}, family={"Q10"},
                    labels={"hu": ["Kovács Józsi"]})
    assert _found(p) == {("Józsi", "József", "label")}


@pytest.mark.parametrize("labels", [
    ["Kovács József"],        # the label holds the given name
    ["Józsi"],                # no family name in it: a stage name
    ["Kovács Józsi Pista"],   # two words left
    ["Dr. Kovács József"],    # a title is no name word
    ["Kovács Józsefné"],      # a wife named by her husband's name
])
def test_a_label_naming_no_one_word_against_the_given_name_pairs_nothing(
        labels: list[str]) -> None:
    p = tool.Person(given={"Q1"}, family={"Q10"}, labels={"hu": labels})
    assert {r for r in _found(p) if r[2] == "label"} == set()


def test_a_patronymic_is_set_aside_from_a_label() -> None:
    p = tool.Person(given={"Q8"}, family={"Q13"},
                    labels={"ru": ["Ваня Петрович Иванов"]})
    assert _found(p, ("ru",)) == {("Ваня", "Иван", "label")}


def test_the_birth_name_pairs_where_the_given_name_is_one_of_the_two() -> None:
    p = tool.Person(given={"Q3"}, family={"Q12"},
                    labels={"hu": ["Kiss Böske"]},
                    births={"hu": ["Kiss Erzsébet"]})
    assert ("Böske", "Erzsébet", "birth") in _found(p)


def test_a_changed_surname_in_the_birth_name_pairs_nothing() -> None:
    # Magyarized or married: the one word that differs is the family
    # name, which is no given name of the person's
    p = tool.Person(given={"Q4"}, family={"Q10"},
                    labels={"hu": ["Kovács Anna"]},
                    births={"hu": ["Nagy Anna"]})
    assert {r for r in _found(p) if r[2] == "birth"} == set()


def test_the_birth_name_is_read_in_the_labels_language_only() -> None:
    p = tool.Person(given={"Q3"}, family={"Q12"},
                    labels={"hu": ["Kiss Erzsébet"], "de": ["Böske Kiss"]},
                    births={"de": ["Erzsébet Kiss"]})
    assert {r for r in _found(p) if r[2] == "birth"} == set()


def test_a_nickname_pairs_with_the_given_name_it_is_shaped_like() -> None:
    p = tool.Person(given={"Q1"}, family={"Q10"},
                    labels={"hu": ["Kovács József"]},
                    nicknames={"hu": ["Józsi", "Kovács Jóska"]})
    assert _found(p) == {("Józsi", "József", "nickname"),
                         ("Jóska", "József", "nickname")}


def test_a_nickname_not_shaped_like_the_given_name_pairs_nothing() -> None:
    # Pista / István is a familiar form the filter loses on purpose:
    # an epithet or a stage name shares neither letter
    p = tool.Person(given={"Q2"}, family={"Q10"},
                    labels={"hu": ["Kovács István"]},
                    nicknames={"hu": ["Pista", "Csodacsatár"]})
    assert _found(p) == set()


def test_of_two_given_names_the_one_sharing_the_first_letter_is_paired() -> None:
    p = tool.Person(given={"Q1", "Q2"}, family={"Q10"},
                    labels={"hu": ["Kovács József István"]},
                    nicknames={"hu": ["Józsi"]})
    assert _found(p) == {("Józsi", "József", "nickname")}


def test_a_name_labelled_in_mul_alone_is_read_in_the_countrys_language() -> None:
    p = tool.Person(given={"Q5"}, family={"Q11"},
                    labels={"mul": ["Kati Nagy"]})
    assert _found(p) == {("Kati", "Katalin", "label")}
    # a country of several languages cannot say which a `mul` label is
    assert _found(p, ("hu", "de")) == set()


def test_two_scripts_and_one_folded_name_pair_nothing() -> None:
    p = tool.Person(given={"Q1"}, family={"Q10"},
                    labels={"hu": ["Kovács Jozsef"]})
    assert _found(p) == set()


def test_a_person_counts_once_a_pair_whichever_relations_found_it() -> None:
    found = [("Q100", "hu", tool.Found("Józsi", "József", "hu", "label")),
             ("Q100", "hu", tool.Found("Józsi", "József", "hu", "nickname")),
             ("Q101", "ro", tool.Found("József", "Józsi", "hu", "birth"))]
    pairs = tool.mine(found)
    ev = pairs[("józsef", "józsi", "hu")]
    assert len(ev.people) == 2
    assert ev.relations == {"label": 1, "nickname": 1, "birth": 1}
    assert ev.countries == {"hu": 1, "ro": 1}


def test_the_rows_leave_out_the_known_pairs_and_the_thin_ones() -> None:
    found = [(f"Q{i}", "hu", tool.Found("Józsi", "József", "hu", "label"))
             for i in range(3)]
    found += [("Q9", "hu", tool.Found("Kati", "Katalin", "hu", "label")),
              ("Q8", "sk", tool.Found("Józsi", "József", "sk", "label"))]
    pairs = tool.mine(found)
    rows = tool.rows(pairs, 2, set())
    assert [r[:4] + r[5:6] for r in rows] == [
        ["józsef", "józsi", "wikidata", "3", "hu"]]
    assert tool.rows(pairs, 1, {frozenset(("józsef", "józsi"))})[0][:2] == [
        "katalin", "kati"]
    # a pair in two languages lists each it reaches the bar in
    both = tool.rows(pairs, 1, set())[0]
    assert (both[3], both[5]) == ("4", "hu sk")


def test_an_answer_cut_by_a_timeout_is_refused() -> None:
    whole = ('?h\t?v\n<http://www.wikidata.org/entity/Q1>\t'
             '"Kovács \\"Józsi\\""@hu\n'
             '<http://www.wikidata.org/entity/Q2>\t'
             '<http://www.wikidata.org/entity/Q5>\n'
             '<http://www.wikidata.org/entity/Q3>\t'
             '<http://www.wikidata.org/.well-known/genid/fa0d79>\n')
    assert tool.read_answer(whole) == [("Q1", 'Kovács "Józsi"', "hu"),
                                       ("Q2", "Q5", "")]
    cut = whole + "java.util.concurrent.TimeoutException\n\tat org.x\n"
    with pytest.raises(tool.FetchError):
        tool.read_answer(cut)
    with pytest.raises(tool.FetchError):
        tool.read_answer("upstream request timeout")


def test_an_answer_is_kept_only_once_whole(tmp_path: Path,
                                           monkeypatch: pytest.MonkeyPatch) -> None:
    answers = iter(["?h\t?v\n<http://x>\tbad\n", "?h\t?v\n"])

    def fake_open(request: object, timeout: float) -> object:
        import io
        return io.BytesIO(next(answers).encode())

    monkeypatch.setattr(tool.urllib.request, "urlopen", fake_open)
    monkeypatch.setattr(tool, "_sleep", lambda s: None)
    assert tool._kept(tmp_path / "a.tsv", "SELECT") == "?h\t?v\n"
    assert not (tmp_path / "a.tsv.part").exists()


def test_every_country_writes_a_language_the_vocabulary_has() -> None:
    vocab = Path(__file__).parents[2] / "nameparser" / "vocab"
    tags = {t for _, ts in tool.COUNTRIES.values() for t in ts}
    tags |= set(tool.LABEL_TAGS.values())
    assert {t for t in tags if not (vocab / f"{t}.toml").exists()} <= {"sq"}


def test_the_requests_name_no_person_or_project() -> None:
    assert "nameparser" not in tool.USER_AGENT.lower()
    assert "@" not in tool.USER_AGENT and "http" not in tool.USER_AGENT


def test_the_tool_reads_no_list_of_familiar_forms() -> None:
    # as tools/vocab/familiar_candidates.py: a candidate is found in
    # data, never selected from a compiled list (decisions/
    # shipped-data-licences, 2026-11-12 #1370 FACTS WE MEASURE)
    tree = ast.parse(_PATH.read_text(encoding="utf-8"))
    names = {n.attr if isinstance(n, ast.Attribute) else n.id
             for n in ast.walk(tree) if isinstance(n, (ast.Attribute, ast.Name))}
    assert not names & {"NAMDICT_FILE", "NAMDICT_FILE_SHA256", "NamDict",
                        "load_pairs", "FAMILIAR", "_familiar_forms",
                        "load_nicknames", "load_exclusions", "familiar"}
