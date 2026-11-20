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


@pytest.mark.parametrize("label, tag, given, family", [
    ("Ваня Петрович Иванов", "ru", "Иван", "Иванов"),
    ("Лена Петровна Иванова", "ru", "Елена", "Иванова"),
    ("Ксеня Іванівна Петренко", "uk", "Оксана", "Петренко"),
])
def test_a_patronymic_is_set_aside_from_a_label(
        label: str, tag: str, given: str, family: str) -> None:
    labels = {"Q30": {tag: {given}}, "Q31": {tag: {family}}}
    p = tool.Person(given={"Q30"}, family={"Q31"}, labels={tag: [label]})
    assert {(f.x, f.y) for f in tool.relations(p, labels, (tag,), _TITLES)} == {
        (label.split()[0], given)}


def test_a_patronymic_does_not_stand_for_the_family_name() -> None:
    # a label of a familiar form and a patronymic alone names no family
    p = tool.Person(given={"Q8"}, family={"Q13"},
                    labels={"ru": ["Ваня Петрович"]})
    assert _found(p, ("ru",)) == set()


def test_a_given_name_the_language_cannot_read_stops_the_language() -> None:
    # a second given name labelled only in German, or only as two
    # words, could be the word the label holds (`Péter`): nothing pairs
    for second in ({"de": {"Peter"}}, {"hu": {"Péter Pál"}}):
        labels = {**_LABELS, "Q20": second}
        p = tool.Person(given={"Q1", "Q20"}, family={"Q10"},
                        labels={"hu": ["Kovács Péter"]})
        assert tool.relations(p, labels, ("hu",), _TITLES) == set()


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


def test_a_family_name_the_language_cannot_read_stops_only_two_relations() -> None:
    # the birth name's pair is a given name already, so it still pairs;
    # the nickname and label relations set the family name aside and
    # cannot here (`Kiss` labelled only in German)
    labels = {**_LABELS, "Q24": {"de": {"Kiss"}}}
    p = tool.Person(given={"Q3"}, family={"Q24"},
                    labels={"hu": ["Kiss Böske"]},
                    births={"hu": ["Kiss Erzsébet"]},
                    nicknames={"hu": ["Erzsi"]})
    assert {(f.x, f.y, f.relation)
            for f in tool.relations(p, labels, ("hu",), _TITLES)} == {
        ("Böske", "Erzsébet", "birth")}


def test_a_nickname_holding_the_given_names_second_two_letters_pairs() -> None:
    labels = {**_LABELS, "Q21": {"cs": {"Alois"}}, "Q22": {"cs": {"Novák"}}}
    p = tool.Person(given={"Q21"}, family={"Q22"},
                    labels={"cs": ["Alois Novák"]}, nicknames={"cs": ["Lojza"]})
    assert {(f.x, f.y) for f in tool.relations(p, labels, ("cs",), _TITLES)} == {
        ("Lojza", "Alois")}


def test_two_given_names_of_the_nicknames_letter_pair_neither() -> None:
    labels = {**_LABELS, "Q23": {"hu": {"János"}}}
    p = tool.Person(given={"Q1", "Q23"}, family={"Q10"},
                    labels={"hu": ["Kovács József János"]},
                    nicknames={"hu": ["Józsi"]})
    assert tool.relations(p, labels, ("hu",), _TITLES) == set()
    # nor a birth name of two words of the label word's letter
    p = tool.Person(given={"Q3"}, family={"Q12"},
                    labels={"hu": ["Kiss Böske"]},
                    births={"hu": ["Kiss Borbála Boglárka"]})
    assert {f.relation for f in tool.relations(p, _LABELS, ("hu",), _TITLES)
            } == {"label"}


def test_rene_is_no_wifes_name() -> None:
    assert tool.name_words("Kovács René", _TITLES, "hu") == ["Kovács", "René"]
    assert tool.name_words("Kovács Istvánné", _TITLES, "hu") == ["Kovács"]


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


@pytest.mark.parametrize("given", ["Иван/Ваня", "Иванa"])
def test_a_given_name_label_that_is_no_name_word_pairs_nothing(
        given: str) -> None:
    # a slash-joined label and one holding a Latin letter in Cyrillic
    labels = {**_LABELS, "Q9": {"ru": {given}}}
    p = tool.Person(given={"Q9"}, family={"Q13"},
                    labels={"ru": ["Ваня Иванов"]})
    assert tool.relations(p, labels, ("ru",), _TITLES) == set()


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
    assert ev.relations == {"label": {"Q100"}, "nickname": {"Q100"},
                            "birth": {"Q101"}}
    assert ev.countries == {"hu": {"Q100"}, "ro": {"Q101"}}


def test_each_column_counts_a_person_once() -> None:
    # one person found in two languages (a Czechoslovak labelled in cs
    # and sk) and under two citizenships (ru and su): one holder, and
    # one in each relation and every country that found them
    found = [("Q1", "cs", tool.Found("Pepa", "Josef", "cs", "label")),
             ("Q1", "cs", tool.Found("Pepa", "Josef", "sk", "label")),
             ("Q2", "ru", tool.Found("Ваня", "Иван", "ru", "label")),
             ("Q2", "su", tool.Found("Ваня", "Иван", "ru", "label"))]
    by_pair = {(r[0], r[1]): r for r in tool.rows(tool.mine(found), 1, set())}
    pepa = by_pair["josef", "pepa"]
    assert (pepa[3], pepa[5], pepa[6], pepa[7]) == ("1", "cs sk", "label 1",
                                                     "cs 1")
    vanya = by_pair["ваня", "иван"]
    assert (vanya[3], vanya[6], vanya[7]) == ("1", "label 1", "ru 1, su 1")


def test_the_rows_leave_out_the_known_pairs_and_the_thin_ones() -> None:
    found = [(f"Q{i}", "hu", tool.Found("Józsi", "József", "hu", "label"))
             for i in range(2)]
    found += [("Q9", "hu", tool.Found("Kati", "Katalin", "hu", "label")),
              ("Q8", "sk", tool.Found("Józsi", "József", "sk", "label"))]
    pairs = tool.mine(found)
    # the bar counts a pair's people in every language together, and
    # the row lists each language it was found in
    assert [r[:6] for r in tool.rows(pairs, 3, set())] == [
        ["józsef", "józsi", "wikidata", "3", "", "hu sk"]]
    assert [r[:2] for r in tool.rows(pairs, 1, {frozenset(("józsef", "józsi"))})] == [
        ["katalin", "kati"]]


def test_spellings_the_match_folds_alike_are_one_candidate() -> None:
    # the match reads Алена and Алёна as one name, so the review must
    # read them as one pair (#1387's first draw proposed both, and its
    # readers split one and agreed on the other)
    found = [(f"Q{i}", "ru", tool.Found("Алёна", "Елена", "ru", "label"))
             for i in range(3)]
    found += [("Q9", "ru", tool.Found("Алена", "Елена", "ru", "label")),
              ("Q8", "by", tool.Found("Алена", "Елена", "be", "label"))]
    rows = tool.rows(tool.mine(found), 1, set())
    assert [(r[0], r[1], r[3], r[5]) for r in rows] == [
        ("алёна", "елена", "5", "be ru")]
    # the bar counts the merged spellings' people
    assert tool.rows(tool.mine(found), 6, set()) == []
    # and a reviewed pair is known in every spelling folded alike
    assert tool.rows(tool.mine(found), 1, {frozenset(("алена", "елена"))}) == []


def test_an_answer_cut_by_a_timeout_is_refused() -> None:
    whole = ('?h\t?v\n<http://www.wikidata.org/entity/Q1>\t'
             '"Kovács \\"Józsi\\""@hu\n'
             '<http://www.wikidata.org/entity/Q2>\t'
             '<http://www.wikidata.org/entity/Q5>\n'
             '<http://www.wikidata.org/entity/Q3>\t'
             '<http://www.wikidata.org/.well-known/genid/fa0d79>\n')
    assert tool.read_answer(whole) == [("Q1", 'Kovács "Józsi"', "hu"),
                                       ("Q2", "Q5", "")]
    for cut in (whole + "java.util.concurrent.TimeoutException\n\tat org.x\n",
                "upstream request timeout",
                # cut inside the last line's tag, before it, or at its end
                whole + '<http://www.wikidata.org/entity/Q4>\t"Kovács"@h',
                whole + '<http://www.wikidata.org/entity/Q4>\t"Kovács"\n',
                whole[:-1]):
        with pytest.raises(tool.FetchError):
            tool.read_answer(cut)
    # a label answer refuses a tag it did not ask for
    with pytest.raises(tool.FetchError):
        tool.read_answer(whole, langs={"ro", "mul"})
    assert tool.read_answer(whole, langs={"hu"})[0][2] == "hu"


def _serve(monkeypatch: pytest.MonkeyPatch, answers: list[str]) -> list[str]:
    """Serve `answers` in turn as the query service, recording each
    query asked."""
    import io
    import urllib.parse
    asked: list[str] = []
    queue = iter(answers)

    def fake_open(request: object, timeout: float) -> object:
        body = request.data.decode()  # type: ignore[attr-defined]
        asked.append(urllib.parse.parse_qs(body)["query"][0])
        return io.BytesIO(next(queue).encode())

    monkeypatch.setattr(tool.urllib.request, "urlopen", fake_open)
    monkeypatch.setattr(tool, "_sleep", lambda s: None)
    return asked


def test_an_answer_is_kept_only_once_whole(tmp_path: Path,
                                           monkeypatch: pytest.MonkeyPatch) -> None:
    asked = _serve(monkeypatch, ["?h\t?v\n<http://x>\tbad\n", "?h\t?v\n"])
    assert tool._kept(tmp_path, "a", "SELECT", False) == "?h\t?v\n"
    assert len(asked) == 2
    assert [p.suffix for p in tmp_path.iterdir()] == [".tsv"]
    # read back without asking, and checked whole again
    assert tool._kept(tmp_path, "a", "SELECT", True) == "?h\t?v\n"
    (kept,) = tmp_path.iterdir()
    kept.write_text("?h\t?v\n<http://www.wikidata.org/entity/Q1>\t", "utf-8")
    with pytest.raises(SystemExit, match="delete it and fetch again"):
        tool._kept(tmp_path, "a", "SELECT", True)


@pytest.mark.parametrize("error", [
    "url", "timeout", "incomplete", "http-503"])
def test_a_failed_connection_is_retried(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch, error: str) -> None:
    import http.client
    import io
    import urllib.error
    # built when raised, so an error a case does not raise is never left
    # open (an HTTPError holds its response)
    make = {
        "url": lambda: urllib.error.URLError("refused"),
        "timeout": lambda: TimeoutError("timed out"),
        "incomplete": lambda: http.client.IncompleteRead(b"?h"),
        "http-503": lambda: urllib.error.HTTPError(
            "u", 503, "busy", {}, io.BytesIO()),  # type: ignore[arg-type]
    }[error]
    calls = []

    def fake_open(request: object, timeout: float) -> object:
        calls.append(1)
        if len(calls) == 1:
            raise make()
        return io.BytesIO(b"?h\t?v\n")

    monkeypatch.setattr(tool.urllib.request, "urlopen", fake_open)
    monkeypatch.setattr(tool, "_sleep", lambda s: None)
    assert tool.ask("SELECT", "hu-label") == "?h\t?v\n"
    assert len(calls) == 2


def test_a_refused_query_names_itself(monkeypatch: pytest.MonkeyPatch) -> None:
    import io
    import urllib.error

    def fake_open(request: object, timeout: float) -> object:
        raise urllib.error.HTTPError("u", 400, "bad", {}, io.BytesIO())  # type: ignore[arg-type]

    monkeypatch.setattr(tool.urllib.request, "urlopen", fake_open)
    with pytest.raises(tool.FetchError, match="hu-label: HTTP 400"):
        tool.ask("SELECT", "hu-label")


def test_a_changed_query_is_asked_again_and_offline_refuses(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    # a country's languages are in its label query, so a change to them
    # is never read from the answer kept for the old ones
    asked = _serve(monkeypatch, ["?h\t?v\n", "?h\t?v\n"])
    tool._kept(tmp_path, "hu-label", 'SELECT "hu"', False)
    tool._kept(tmp_path, "hu-label", 'SELECT "hu", "de"', False)
    assert len(asked) == 2
    with pytest.raises(SystemExit, match="is not fetched"):
        tool._kept(tmp_path, "hu-label", 'SELECT "ro"', True)


def test_a_country_is_read_from_its_answers(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    # Serbian written in Latin (`sr-el`) and Cyrillic is one tag
    e = "<http://www.wikidata.org/entity/{}>".format
    answers = {
        "given": f"?h\t?v\n{e('Q1')}\t{e('Q5')}\n{e('Q2')}\t{e('Q5')}\n",
        "family": f"?h\t?v\n{e('Q1')}\t{e('Q6')}\n{e('Q2')}\t{e('Q6')}\n",
        "label": f'?h\t?v\n{e("Q1")}\t"Jova Petrović"@sr-el\n'
                 f'{e("Q2")}\t"Јова Петровић"@sr\n',
        "birth": "?h\t?v\n", "nickname": "?h\t?v\n",
        "items": f'?h\t?v\n{e("Q5")}\t"Jovan"@sr-el\n{e("Q5")}\t"Јован"@sr\n'
                 f'{e("Q6")}\t"Petrović"@sr-el\n{e("Q6")}\t"Петровић"@sr\n',
    }
    found = sorted((q, f.x, f.y, f.tag) for q, _, f in
                   tool.country_found("Q403", answers, _TITLES))
    assert found == [("Q1", "Jova", "Jovan", "sr"), ("Q2", "Јова", "Јован", "sr")]
    # and fetch asks each query once, then reads the kept answers alone
    served = [answers[n] for n in tool.QUERIES] + [answers["items"]]
    asked = _serve(monkeypatch, served)
    fetched = tool.fetch("Q403", tmp_path)
    assert len(asked) == len(served) and fetched["items"] == answers["items"]
    assert tool.fetch("Q403", tmp_path, offline=True) == fetched


def test_a_partial_run_writes_a_file_of_its_own() -> None:
    assert tool.candidates_file(None) == tool.CANDIDATES_FILE
    assert tool.candidates_file(["ro", "hu"]) == (
        "familiar-wikidata-candidates-hu-ro.tsv")


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
