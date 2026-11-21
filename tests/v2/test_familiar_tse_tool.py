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
    pair = tool.pair_of(civil, ballot, _TITLES, _PARTICLES)
    return None if pair is None else tuple(sorted(pair))  # type: ignore[return-value]


@pytest.mark.parametrize("civil, ballot, pair", [
    # rule 1, the same first letter and the form's last three letters
    # inside it, over rule 2's first given word of that letter
    ("JOSÉ JOAQUIM PEREIRA", "JUQUIM", ("joaquim", "juquim")),
    # rule 2, the same first letter (`nho`, `hos` inside neither)
    ("PAULO HENRIQUE DA SILVA", "PAULINHO", ("paulinho", "paulo")),
    ("JOSÉ CARLOS PEREIRA", "CARLINHOS", ("carlinhos", "carlos")),
    # rule 3, the last three letters alone (`iao` inside `sebastiao`)
    ("SEBASTIÃO ALVES", "TIÃO DO POVO", ("sebastião", "tião")),
    ("MARIA APARECIDA SOUZA", "CIDA", ("aparecida", "cida")),
    # else the first given word
    ("SEVERINO RAMOS LIMA", "BIU", ("biu", "severino")),
    # a title, a particle and a word of the civil name are read past
    ("ANTONIO MARCOS FERREIRA", "DR TONHO", ("antonio", "tonho")),
    ("PAULO SILVA", "DO PAULINHO", ("paulinho", "paulo")),
    ("PAULO SILVA", "SILVA PAULINHO", ("paulinho", "paulo")),
    # a particle in the civil name takes no given-word place
    ("MARIA DAS GRAÇAS SOUZA", "GRACINHA", ("gracinha", "graças")),
    # a family name that is no name word still ends the name
    ("JOÃO CARLOS D'ÁVILA", "CARLINHOS", ("carlinhos", "carlos")),
    ("JOÃO CARLOS WAN-DALL", "CARLINHOS", ("carlinhos", "carlos")),
    # edge punctuation and a quote the court's cp1252 writes
    ("PAULO SILVA", '"PAULINHO"', ("paulinho", "paulo")),
    ("PAULO SILVA", "\u201cPAULINHO\u201d", ("paulinho", "paulo")),
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
    # the civil word past the given words: a surname, as the third word,
    # or as the second where nothing follows it
    ("PEDRO HENRIQUE CASTRO", "CASTR"),
    ("PEDRO CASTRO", "CASTRINHO"),
    ("MARIA DA SILVA", "SILVINHA"),
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
    for cut in (whole + '"2";"ANA LIMA";"ANI',
                # inside the last field: a full-width row to csv
                whole + '"2";"ANA LIMA";"ANINHA";"-4";"0123'):
        with pytest.raises(ValueError, match="is cut"):
            tool.read_member(io.StringIO(cut), "2024")
    with pytest.raises(ValueError, match="lacks"):
        tool.read_member(io.StringIO('"A";"B"\r\n'), "2024")
    # a year stating voter numbers needs the column; 1994 does not
    header = '"SQ_CANDIDATO";"NM_CANDIDATO";"NM_URNA_CANDIDATO"\r\n'
    body = header + '"1";"PAULO SILVA";"PAULINHO"\r\n'
    with pytest.raises(ValueError, match="NR_TITULO_ELEITORAL_CANDIDATO"):
        tool.read_member(io.StringIO(body), "2024")
    assert tool.read_member(io.StringIO(body), "1994")[1]["people"] == 1


def _rows(n: int, row: str) -> list[str]:
    return [row.format(i=i + 1, v=f"{i + 1:012d}") for i in range(n)]


@pytest.mark.parametrize("bad, ok", [
    # a row of another width, a line folded into a name, a nameless row,
    # a row no number names: one is let pass, two in a few rows are not
    ('"{i}";"X"', 1),
    ('"{i}";"ANA\r\nLIMA";"ANINHA";"-4";"{v}"', 1),
    ('"{i}";"#NULO#";"ANINHA";"-4";"{v}"', 1),
    ('"{i}";"ANA LIMA";"ANINHA";"-4";"-4"', 1),
])
def test_a_member_too_much_of_which_is_unread_is_refused(bad: str, ok: int) -> None:
    good = _rows(4, '"{i}";"PAULO SILVA";"PAULINHO";"-4";"{v}"')
    tool.read_member(_member(*_rows(ok, bad), *good), "2024")
    with pytest.raises(ValueError, match="layout has changed"):
        tool.read_member(_member(*_rows(ok + 1, bad), *good), "2024")


def test_a_member_of_no_named_candidate_is_refused() -> None:
    # a header alone, and one nameless row, which the nameless share lets
    # pass: no person is read
    for body in (_member(), _member('"1";"#NULO#";"X";"-4";"012345678901"')):
        with pytest.raises(ValueError, match="no candidate"):
            tool.read_member(body, "2024")


def test_a_persons_second_pair_of_names_in_a_year_is_kept() -> None:
    records, counts = tool.read_member(_member(
        '"1";"PAULO SILVA";"PAULINHO";"-4";"012345678901"',
        '"2";"PAULO SILVA";"PAULÃO";"-4";"012345678901"'), "2024")
    assert sorted(r["ballot"] for r in records) == ["PAULINHO", "PAULÃO"]
    assert counts["people"] == 1


def test_the_records_no_pair_came_from_are_counted_by_reason() -> None:
    records = [{"civil": "PAULO SILVA", "ballot": "PAULO", "person": "1"},
               {"civil": "PAULO SILVA", "ballot": "2024", "person": "2"},
               {"civil": "PEDRO CASTRO", "ballot": "CASTRINHO", "person": "3"},
               {"civil": "PAULO SILVA", "ballot": "PAULINHO", "person": "4"}]
    mined = tool.mine(records, _TITLES, _PARTICLES)
    assert mined.dropped == {"no ballot word outside the civil name": 1,
                             "the ballot word no name word": 1,
                             "the civil word no given word": 1}


@pytest.mark.parametrize("row, kind", [
    ({"NR_TITULO_ELEITORAL_CANDIDATO": "012345678901",
      "NR_CPF_CANDIDATO": "12345678909"}, "voter"),       # the voter number first
    ({"NR_TITULO_ELEITORAL_CANDIDATO": "1234567",
      "NR_CPF_CANDIDATO": "12345678909"}, "cpf"),         # seven digits name no one
    ({"NR_TITULO_ELEITORAL_CANDIDATO": "-4",
      "NR_CPF_CANDIDATO": "00000000000", "SQ_CANDIDATO": "7"}, "seq"),  # a repeated digit
])
def test_a_person_is_named_by_the_first_number_that_names_one(
        row: dict[str, str], kind: str) -> None:
    assert tool.person_key(row, "2024")[1] == kind


def test_a_candidate_number_names_a_person_of_its_year_alone() -> None:
    row = {"SQ_CANDIDATO": "7"}
    assert tool.person_key(row, "1994")[0] != tool.person_key(row, "1996")[0]
    assert tool.person_key(row, "1994")[0] != tool.person_key({"SQ_CANDIDATO": "8"}, "1994")[0]
    for bad in ("", "-1", "0"):
        with pytest.raises(ValueError, match="SQ_CANDIDATO"):
            tool.person_key({"SQ_CANDIDATO": bad}, "1994")


def test_a_kept_reading_is_named_by_its_zip_and_checked_whole(
        tmp_path: Path) -> None:
    import zipfile
    member = tool.MEMBER.format(year="2024")
    with zipfile.ZipFile(tmp_path / "consulta_cand_2024.zip", "w") as archive:
        archive.writestr(member, _member(
            '"1";"PAULO SILVA";"PAULINHO";"-4";"012345678901"').getvalue().encode("latin-1"))
    records = tool.fetch("2024", tmp_path, offline=True)
    assert [r["ballot"] for r in records] == ["PAULINHO"]
    (kept,) = tmp_path.glob("candidates_2024_*_v*.jsonl")
    assert tool.fetch("2024", tmp_path, offline=True) == records
    # a republished zip is read again, not answered from the old reading
    with zipfile.ZipFile(tmp_path / "consulta_cand_2024.zip", "w") as archive:
        archive.writestr(member, _member(
            '"1";"ANA LIMA";"ANINHA";"-4";"012345678902"').getvalue().encode("latin-1"))
    assert [r["ballot"] for r in tool.fetch("2024", tmp_path, offline=True)] == ["ANINHA"]
    kept.unlink()
    (kept,) = tmp_path.glob("candidates_2024_*_v*.jsonl")
    kept.write_text(kept.read_text("utf-8").splitlines()[0] + "\n", "utf-8")
    with pytest.raises(SystemExit, match="delete it"):
        tool.fetch("2024", tmp_path, offline=True)
    with pytest.raises(SystemExit, match="is not fetched"):
        tool.fetch("2022", tmp_path, offline=True)


@pytest.mark.parametrize("word", sorted(tool.STOP))
def test_a_stop_word_pairs_nothing(word: str) -> None:
    # each would pair with `paulo` by the last rule were it not stopped
    assert _pair("PAULO SILVA", word.upper()) is None


def test_the_pair_names_the_ballot_word_first() -> None:
    assert tool.pair_of("PAULO SILVA", "PAULINHO", _TITLES, _PARTICLES) == (
        "paulinho", "paulo")


def _people(n: int, civil: str, ballot: str, tag: str) -> list[dict[str, str]]:
    return [{"civil": civil, "ballot": ballot, "person": f"{tag}{i}"}
            for i in range(n)]


def test_a_byname_is_dropped_and_its_concentrated_pairs_rescued(
        monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(tool, "BYNAME_PEOPLE", 2)
    monkeypatch.setattr(tool, "RESCUE_PEOPLE", 2)
    # `dona` beside four names, each as often as the name is borne: a
    # byname; `zé` beside four names, three often borne, but on José far
    # beyond José's share: a form of several names, José's pair rescued
    records = []
    for name in ("MARIA", "ANA", "RITA", "VERA"):
        records += _people(40, f"{name} SILVA", name, name)  # the base
        records += _people(4, f"{name} LIMA", "DONA", "d" + name)
        records += _people(2, f"{name} REIS", "ZÉ", "z" + name)
    records += _people(30, "JOSÉ SOUZA", "ZÉ", "zj")
    mined = tool.mine(records, _TITLES, _PARTICLES)
    assert tool.bynames(mined) == frozenset({"dona", "ze"})
    assert mined.lift("dona", "maria") < tool.MIN_LIFT
    assert mined.lift("ze", "jose") >= tool.MIN_LIFT
    pairs = {(r[0], r[1]) for r in tool.rows(mined, 2, set())}
    assert pairs == {("josé", "zé")}
    # and a rescued pair needs RESCUE_PEOPLE
    monkeypatch.setattr(tool, "RESCUE_PEOPLE", 31)
    assert tool.rows(mined, 2, set()) == []


def test_the_shipped_thresholds_part_a_byname_from_a_familiar_form() -> None:
    # at the shipped values: a ballot word of three partners is no
    # byname; one of four is, and its pair at lift about 4 is dropped
    # while its pair at lift about 8 with 50 people is kept
    records: list[dict[str, str]] = []
    for n, name in zip((40, 40, 40, 10, 2000),
                       ("MARIA", "ANA", "RITA", "VERA", "LUCIA")):
        records += _people(n, f"{name} SILVA", name, f"base{name}")
    for name in ("MARIA", "ANA", "RITA"):
        records += _people(10, f"{name} LIMA", "TRIO", "t" + name)
    for name, n in (("MARIA", 10), ("ANA", 10), ("RITA", 10), ("VERA", 60)):
        records += _people(n, f"{name} REIS", "BIBA", "b" + name)
    mined = tool.mine(records, _TITLES, _PARTICLES)
    assert tool.bynames(mined) == frozenset({"biba"})
    assert 3 < mined.lift("biba", "maria") < tool.MIN_LIFT < mined.lift("biba", "vera")
    pairs = {(r[0], r[1]) for r in tool.rows(mined, 10, set())}
    assert {("ana", "trio"), ("maria", "trio"), ("rita", "trio"),
            ("biba", "vera")} <= pairs
    assert ("biba", "maria") not in pairs


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
