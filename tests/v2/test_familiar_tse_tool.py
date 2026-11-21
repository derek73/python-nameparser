"""Offline checks on tools/vocab/familiar_tse.py, which draws candidate
Brazilian Portuguese familiar forms from Brazil's election candidates
for a review by hand (decisions/name-matching, 2026-11-20 #1495).

The failures that matter: a pair evidenced by something other than a
candidate's ballot name standing for their civil given name (a
generation, an epithet, a title, a particle, a surname), a person
counted twice, a body cut short read as whole, a person's number kept,
and a candidate drawn from a compiled list of familiar forms. Every
name here is invented.
"""
from __future__ import annotations

import ast
import importlib.util
import io
import sys
from pathlib import Path
from types import ModuleType

import pytest

from tests.checkout import require_checkout

require_checkout()

_PATH = Path(__file__).parents[2] / "tools" / "vocab" / "familiar_tse.py"


def _load() -> ModuleType:
    spec = importlib.util.spec_from_file_location("familiar_tse", _PATH)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


tool = _load()
_TITLES = frozenset({"dr", "professor", "pastor"})
_PARTICLES = frozenset({"de", "da", "do", "dos", "das"})


def _pair(civil: str, ballot: str) -> tuple[str, str] | None:
    return tool.pair_of(civil, ballot, _TITLES, _PARTICLES)


@pytest.mark.parametrize("civil, ballot, pair", [
    # the same first letter and the form's last three letters inside it
    ("PAULO HENRIQUE DA SILVA", "PAULINHO", ("paulinho", "paulo")),
    ("JOSÉ CARLOS PEREIRA", "CARLINHOS", ("carlinhos", "carlos")),
    # the same first letter, no shared ending
    ("SEBASTIÃO ALVES", "TIÃO DO POVO", ("sebastião", "tião")),
    # the last three letters alone
    ("MARIA APARECIDA SOUZA", "CIDA", ("aparecida", "cida")),
    # else the civil name's first word
    ("SEVERINO RAMOS LIMA", "BIU", ("biu", "severino")),
    # a title and a word of the civil name are read past
    ("ANTONIO MARCOS FERREIRA", "DR TONHO", ("antonio", "tonho")),
])
def test_a_ballot_name_pairs_with_the_given_name_it_stands_for(
        civil: str, ballot: str, pair: tuple[str, str]) -> None:
    assert _pair(civil, ballot) == pair


@pytest.mark.parametrize("civil, ballot", [
    ("PAULO SILVA", "PAULO SILVA"),         # the civil name itself
    ("PAULO SILVA JUNIOR", "JUNIOR"),       # a generation
    ("PAULO SILVA", "JUNINHO"),
    ("PAULO SILVA", "NEGÃO"),               # an epithet
    ("PAULO SILVA", "PROFESSOR SILVA"),     # a title, then the surname
    ("PAULO DA SILVA", "DA SILVA"),         # a particle
    ("PAULO SILVA", "PAULO 2024"),          # no name word
    ("JOSE SILVA", "JOSÉ"),                 # one name under the fold
])
def test_what_is_no_familiar_form_of_the_civil_name_pairs_nothing(
        civil: str, ballot: str) -> None:
    assert _pair(civil, ballot) is None


def _member(*rows: str) -> io.StringIO:
    header = '"SQ_CANDIDATO";"NM_CANDIDATO";"NM_URNA_CANDIDATO";"NR_CPF_CANDIDATO";"NR_TITULO_ELEITORAL_CANDIDATO"'
    return io.StringIO("\r\n".join((header,) + rows) + "\r\n")


def test_a_person_is_one_record_and_their_number_is_kept_hashed() -> None:
    records, counts = tool.read_member(_member(
        '"1";"PAULO SILVA";"PAULINHO";"-4";"012345678901"',
        '"2";"PAULO SILVA";"PAULINHO";"-4";"012345678901"',   # the second round
        '"3";"ANA LIMA";"ANINHA";"12345678909";"-4"',
        '"4";"#NULO#";"X";"-4";"-4"'), "2024")
    assert counts["people"] == 2 and counts["nameless"] == 1
    assert {r["ballot"] for r in records} == {"PAULINHO", "ANINHA"}
    for r in records:
        assert set(r) == {"civil", "ballot", "person"}
        assert "012345678901" not in r["person"] and "12345678909" not in r["person"]


def test_a_member_cut_inside_a_row_is_refused() -> None:
    whole = _member('"1";"PAULO SILVA";"PAULINHO";"-4";"012345678901"').getvalue()
    with pytest.raises(ValueError, match="last row is short"):
        tool.read_member(io.StringIO(whole + '"2";"ANA LIMA";"ANI'), "2024")
    with pytest.raises(ValueError, match="lacks"):
        tool.read_member(io.StringIO('"A";"B"\r\n'), "2024")


def test_a_person_counts_once_and_spellings_folded_alike_are_one_pair() -> None:
    records = [{"civil": "SEBASTIAO ALVES", "ballot": "TIAO", "person": "p1"},
               {"civil": "SEBASTIÃO ALVES", "ballot": "TIÃO", "person": "p1"},
               {"civil": "SEBASTIÃO LIMA", "ballot": "TIÃO", "person": "p2"},
               {"civil": "SEBASTIÃO REIS", "ballot": "TIÃO", "person": "p3"}]
    found = tool.mine(records, _TITLES, _PARTICLES)
    rows = tool.rows(found, 3, set())
    assert [(r[0], r[1], r[3], r[5]) for r in rows] == [
        ("sebastião", "tião", "3", "pt-BR")]
    assert tool.rows(found, 4, set()) == []
    # known in any spelling the match folds alike
    assert tool.rows(found, 1, {frozenset(("sebastiao", "tiao"))}) == []


def test_a_zip_is_kept_only_whole(tmp_path: Path,
                                  monkeypatch: pytest.MonkeyPatch) -> None:
    import zipfile
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        archive.writestr("consulta_cand_2024_BRASIL.csv", "x")
    whole = buffer.getvalue()
    for body, ok in ((whole[:-20], False), (whole, True)):
        monkeypatch.setattr(tool.urllib.request, "urlopen",
                            lambda request, timeout, body=body: io.BytesIO(body))
        path = tmp_path / "z.zip"
        if ok:
            tool._download("https://example.invalid/z.zip", path, "consulta_cand_2024_BRASIL.csv")
            assert path.read_bytes() == whole
        else:
            with pytest.raises(ValueError, match="whole zip"):
                tool._download("https://example.invalid/z.zip", path, "consulta_cand_2024_BRASIL.csv")
            assert not path.exists()
    assert [p.name for p in tmp_path.iterdir()] == ["z.zip"]


def test_the_requests_name_no_person_or_project() -> None:
    assert "nameparser" not in tool.USER_AGENT.lower()
    assert "@" not in tool.USER_AGENT and "http" not in tool.USER_AGENT


def test_the_tool_reads_no_list_of_familiar_forms() -> None:
    tree = ast.parse(_PATH.read_text(encoding="utf-8"))
    names = {n.attr if isinstance(n, ast.Attribute) else n.id
             for n in ast.walk(tree) if isinstance(n, (ast.Attribute, ast.Name))}
    assert not names & {"NAMDICT_FILE", "NAMDICT_FILE_SHA256", "NamDict",
                        "load_pairs", "FAMILIAR", "_familiar_forms",
                        "load_nicknames", "load_exclusions", "familiar"}
