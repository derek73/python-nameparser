"""Offline checks on tools/differential/local_dof.py, the dof-signatures
local corpus.

Every name here is invented: the signatories in the DOF are real
officials, and their names stay in the cache. What these pin is the
reading of a note's HTML (blocks and bold), the cut rules and what each
records, the fetch's walk over days (resumed from the cache, the notes
robots.txt disallows skipped, a failed request retried) and its
refusals.
"""
import datetime
import gzip
import importlib
import json
import time
import urllib.error
import urllib.request
from collections.abc import Callable
from pathlib import Path
from typing import Any

import pytest

from ._differential_fixtures import _Response, load_tool, own_cache

local = load_tool("local_corpora")
dof = importlib.import_module("local_dof")

_DOF = "dof-signatures"
_BOLD = "<span style='font-family:Arial;font-weight:bold;'>{}</span>"


@pytest.fixture(autouse=True)
def _own_cache(monkeypatch: pytest.MonkeyPatch, tmp_path_factory: pytest.TempPathFactory) -> Path:
    return own_cache(monkeypatch, tmp_path_factory)


def _div(text: str) -> str:
    return f"<div class='Normal'><span style='font-family:Arial;'>{text}</span><br></div>"


#: A court notice, stacked: date, office, the name in bold, "Rúbrica."
#: alone; then an agreement, inline, two signatures in one paragraph,
#: the second name before its office; and a signature in capitals.
_STACKED = (_div("Texto del edicto.") + _div("Ciudad de México, a 2 de enero de 2025.")
            + _div("La Secretaria del Juzgado Primero de Distrito")
            + f"<div>{_BOLD.format('Lic. Ana Ruiz Toledo')}</div>" + _div("Rúbrica."))
_INLINE = ("<p>Se firma en la Ciudad de México, a 2 de enero de 2025.- Por la Entidad: "
           "el Director General, Mtra. " + _BOLD.format("Eva") + " " + _BOLD.format("Mar Soto")
           + ".- Rúbrica.- " + _BOLD.format("Bo Gil Paz") + ", Presidente del Comité.- "
           "Rúbrica.</p>")
_CAPITALS = (_div("JEFE DE DEPARTAMENTO") + f"<div>{_BOLD.format('ING. LUIS PRADO REY')}</div>"
             + _div("Rúbrica."))


def _records(content: str) -> list[dict[str, str] | str]:
    return [found for excerpt in dof.excerpts(content) for found in dof.signatures(excerpt)]


def test_a_stacked_signature_cuts_the_bold_block_and_keeps_the_office_above() -> None:
    assert _records(_STACKED) == [{
        "name": "Lic. Ana Ruiz Toledo", "cut": "bold", "layout": "stacked",
        "title": "Lic.", "joined": "block",
        "clause": "Ciudad de México, a 2 de enero de 2025. | La Secretaria del Juzgado "
                  "Primero de Distrito | Lic. Ana Ruiz Toledo"}]


def test_an_inline_signature_cuts_the_bold_run_with_the_title_before_it() -> None:
    first, second = _records(_INLINE)
    assert first == {
        "name": "Mtra. Eva Mar Soto", "cut": "bold", "layout": "inline", "title": "Mtra.",
        "joined": "comma",
        "clause": "Por la Entidad: el Director General, Mtra. Eva Mar Soto"}
    # The name before its office: the bold run ends at the comma.
    assert second == {
        "name": "Bo Gil Paz", "cut": "bold", "layout": "inline", "title": "",
        "joined": "start", "clause": "Bo Gil Paz, Presidente del Comité"}


def test_a_title_written_in_capitals_is_read_as_one() -> None:
    (found,) = _records(_CAPITALS)
    assert isinstance(found, dict)
    assert (found["name"], found["title"]) == ("ING. LUIS PRADO REY", "ING.")


@pytest.mark.parametrize(("clause", "expected"), [
    # No bold: the run from the last title to the end, the office before
    # it glued with no comma.
    ("El Secretario del Juzgado Licenciada Ema Rey Gil", ("Licenciada Ema Rey Gil", "title")),
    ("Directora de Área, la C.P. Ana Lis Mora", ("C.P. Ana Lis Mora", "title")),
    # The office after the name, set off by a comma, stays out.
    ("Sen. Ana Lis Mora, Secretaria", ("Sen. Ana Lis Mora", "title")),
    # A surname ending a sentence is not a title: the run opens at `Lic.`,
    # not at `Paz.`, though it still runs on to the end of the clause.
    ("firmado por Lic. Ana Ruiz Paz. Conste", ("Lic. Ana Ruiz Paz. Conste", "title")),
])
def test_without_bold_a_title_opens_the_cut(clause: str, expected: tuple[str, str]) -> None:
    assert dof.cut(clause, "0" * len(clause)) == expected


@pytest.mark.parametrize("clause", [
    "El Titular de la Unidad, la Ana Lis Mora",  # neither bold nor a title
    "Ana Lis Mora",
    "II. Remitir mediante oficio dirigido a la Dirección General el convenio",  # a sentence
])
def test_without_bold_or_a_title_short_enough_nothing_is_cut(clause: str) -> None:
    assert dof.cut(clause, "0" * len(clause)) is None


def test_a_title_in_roman_after_a_bold_office_stays_out_of_an_earlier_run() -> None:
    # The bold office ends in a comma, so it is a run of its own, and
    # the last run is the name.
    text = "Gerente de Área, Lic. Ana Lis Mora"
    mask = "".join("1" if 13 <= i <= 15 or i >= 21 else "0" for i in range(len(text)))
    assert dof.cut(text, mask) == ("Lic. Ana Lis Mora", "bold")


@pytest.mark.parametrize(("before", "joined"), [
    ("", "start"), ("Oficina | ", "block"), ("Director General, ", "comma"),
    ("Por la Entidad: ", "colon"), ("Directora, la ", "article"),
    ("La Secretaria del Juzgado ", "word")])
def test_how_a_cut_meets_the_clause_before_it(before: str, joined: str) -> None:
    assert dof.joined(before) == joined


@pytest.mark.parametrize("word", ["Lic.", "C.", "C.P.", "L.C.P.", "Mtro.", "Lcda.", "LIC.",
                                  "MVZ.", "Gral.", "Biól.", "Licenciado", "MAESTRA"])
def test_titles_by_shape_and_by_spelling(word: str) -> None:
    assert dof.is_title(word)


@pytest.mark.parametrize("word", ["Ana", "Rúbrica.", "de", "Lic", "CONSEJO.",
                                  "Paz.", "Ma.", "Gpe.", "Eds."])
def test_words_that_are_not_titles(word: str) -> None:
    assert not dof.is_title(word)


def test_a_rubrica_with_nothing_before_it_is_counted_not_cut() -> None:
    assert _records(_div("Rúbrica.")) == ["stacked, no block above"]
    assert _records("<p>firman de conformidad, .- Rúbrica.</p>") == ["inline, nothing before"]


@pytest.mark.parametrize(("name", "reason"), [
    ("a siete de noviembre de dos mil veinticinco", "cut a date"),
    ("Ciudad de México a 2 de enero de 2025", "cut a date"),
    ("EL SECRETARIO DE SALUD", "cut an office"),
    ("La Gobernadora Constitucional", "cut an office"),
    ("Atentamente", "cut one word"),
])
def test_a_cut_of_one_word_a_date_or_an_office_is_counted_not_kept(name: str, reason: str) -> None:
    signed = _div("Atentamente") + f"<div>{_BOLD.format(name)}</div>" + _div("Rúbrica.")
    assert _records(signed) == [f"stacked, {reason}"]


def test_a_run_in_bold_throughout_keeps_the_part_after_its_last_comma() -> None:
    rank = "GRAL. BRIG. E.M., Ana Sol Pardo"
    assert dof.cut(rank, "1" * len(rank)) == ("Ana Sol Pardo", "bold")
    office = "Ana Sol Pardo, Presidenta de la Comisión"
    assert dof.cut(office, "1" * len(office)) == ("Presidenta de la Comisión", "bold")
    # an office after the name in roman stays out of the run
    roman = "Ana Sol Pardo, Presidenta"
    assert dof.cut(roman, "1" * len("Ana Sol Pardo,") + "0" * len(" Presidenta")) == (
        "Ana Sol Pardo", "bold")


@pytest.mark.parametrize(("name", "office"), [
    ("DIRECTORA GENERAL DE RECURSOS HUMANOS", True),
    ("C. GOBERNADOR CONSTITUCIONAL DEL ESTADO", True),
    ("DEL ESTADO DE YUCATÁN", True),
    ("EL SECRETARIO DE SALUD", True),
    ("Magistrado José Rey Paz", False),  # an office written as a title, before a name
    ("Jueza de Distrito Ana Lis Mora", False),
    ("Del Olmo Blanco", False),  # a surname
    ("LIC. ANA LIS MORA", False),
    ("CONSEJERO FRANCISCO RAMOS SILVA", False),  # an office before a name, in capitals
    ("DIPUTADA SECRETARIA", True),
    ("GOBERNADORA DEL ESTADO", True),
])
def test_an_office_signing_without_a_name(name: str, office: bool) -> None:
    assert dof._office(name) is office


@pytest.mark.parametrize("name", [
    "Lic. Julio Linares Rangel", "Del Olmo Blanco", "CAP. 1/O. AYTE. LUIS REY PAZ"])
def test_a_month_a_digit_or_del_inside_a_name_is_kept(name: str) -> None:
    signed = _div("Atentamente") + f"<div>{_BOLD.format(name)}</div>" + _div("Rúbrica.")
    assert [r["name"] for r in _records(signed) if isinstance(r, dict)] == [name]


def test_adjacent_stacked_signatures_share_an_excerpt_and_cut_apart() -> None:
    two = _STACKED + _div("El Actuario") + f"<div>{_BOLD.format('Juan Rey Paz')}</div>" \
        + _div("Rúbrica.")
    assert len(dof.excerpts(two)) == 1
    names = [r["name"] for r in _records(two) if isinstance(r, dict)]
    assert names == ["Lic. Ana Ruiz Toledo", "Juan Rey Paz"]
    assert _records(two)[1]["clause"] == "El Actuario | Juan Rey Paz"  # type: ignore[index]


def test_robots_disallows_only_the_notes_listed_for_every_agent() -> None:
    robots = ("User-agent: *\nDisallow: /CopiasCert?\nDisallow: /notas/5\n"
              "Disallow: /notas/docFuente/6\n\nUser-agent: AdsBot-Google\nDisallow: /notas/7\n")
    assert dof.disallowed(robots) == frozenset({5, 6})


# -- the fetch -----------------------------------------------------------------

_DAY1, _DAY2 = datetime.date(2025, 1, 3), datetime.date(2025, 1, 4)


def _listing(*entries: dict[str, Any]) -> dict[str, Any]:
    return {"messageCode": 200, "response": "OK", "NotasMatutinas": list(entries),
            "NotasVespertinas": [], "NotasExtraordinarias": []}


def _entry(cod: int, html: str = "S") -> dict[str, Any]:
    return {"codNota": cod, "existeHtml": html}


#: Day 1: the stacked note, the inline note, a section heading without
#: HTML and a note robots.txt disallows. Day 2, a Saturday: no note.
_NOTES: dict[int, str | None] = {1: _STACKED, 2: _INLINE, 9: _CAPITALS}
_DAYS = {"03-01-2025": _listing(_entry(1), _entry(2), _entry(3, "N"), _entry(9)),
         "04-01-2025": _listing()}


def _serve(monkeypatch: pytest.MonkeyPatch, *,
           days: dict[str, dict[str, Any]] = _DAYS, notes: dict[int, str | None] = _NOTES,
           fail: Callable[[str], Exception | bytes | None] = lambda url: None) -> list[str]:
    """Answer SIDOF from `days` and `notes`, robots.txt disallowing note
    9, and a note of None as one published as images, stating size 0;
    `fail` may answer a URL instead. Returns the URLs fetched."""
    monkeypatch.setattr(dof, "DOF_FROM", _DAY1)
    monkeypatch.setattr(dof, "DOF_TO", _DAY2)
    monkeypatch.setattr(time, "sleep", lambda seconds: None)
    asked: list[str] = []

    def urlopen(request: urllib.request.Request, timeout: int) -> _Response:
        url = request.full_url
        asked.append(url)
        answer = fail(url)
        if isinstance(answer, Exception):
            raise answer
        if isinstance(answer, bytes):
            return _Response(answer)
        if url == dof.DOF_ROBOTS_URL:
            return _Response(b"User-agent: *\nDisallow: /notas/9\n")
        tail = url.rsplit("/", 1)[1]
        if "/nota/" in url:
            content = notes[int(tail)]
            note = ({"cadenaContenido": content} if content is not None
                    else {"cadenaContenido": None, "tamanioContenido": "0"})
            body: object = {"messageCode": 200, "Nota": note}
        else:
            body = days[tail]
        return _Response(json.dumps(body).encode())
    monkeypatch.setattr(urllib.request, "urlopen", urlopen)
    return asked


def test_a_dof_fetch_walks_the_days_and_keeps_each_signature(
        monkeypatch: pytest.MonkeyPatch) -> None:
    asked = _serve(monkeypatch)
    corpus = local.fetch(_DOF)
    assert [(r["name"], r["day"], r["note"]) for r in corpus.records] == [
        ("Lic. Ana Ruiz Toledo", "2025-01-03", "1"), ("Mtra. Eva Mar Soto", "2025-01-03", "2"),
        ("Bo Gil Paz", "2025-01-03", "2")]
    assert dof.DOF_NOTE_URL.format(cod=9) not in asked
    assert corpus.meta["data_date"] == "2025-01-04"
    detail = corpus.meta["detail"]
    assert detail["notes"] == {"read": 2, "without html": 1, "disallowed": 1}
    assert (detail["cuts"], detail["uncut"]) == ({"bold": 3}, {})
    assert corpus.header().endswith("3 signatures (local corpus dof-signatures)")


def test_a_second_fetch_reads_the_cached_days_and_asks_nothing(
        monkeypatch: pytest.MonkeyPatch) -> None:
    _serve(monkeypatch)
    first = local.fetch(_DOF).records
    asked = _serve(monkeypatch)
    assert local.fetch(_DOF).records == first
    assert asked == []  # robots.txt is read only once a day needs fetching


def test_a_listing_without_one_of_the_editions_is_refused(
        monkeypatch: pytest.MonkeyPatch) -> None:
    for broken in ({k: v for k, v in _listing().items() if k != "NotasVespertinas"},
                   {**_listing(), "NotasExtraordinarias": None}):
        _serve(monkeypatch, days={**_DAYS, "04-01-2025": broken})
        with pytest.raises(ValueError, match="lists no Notas"):
            local.fetch(_DOF)
    assert not dof._day_path(_DAY2).exists()


def test_weekdays_listing_no_note_past_the_gate_refuse_the_fetch(
        monkeypatch: pytest.MonkeyPatch) -> None:
    _serve(monkeypatch, days={**_DAYS, "05-01-2025": _listing(), "06-01-2025": _listing()})
    monkeypatch.setattr(dof, "DOF_TO", datetime.date(2025, 1, 6))  # a Sunday, a silent Monday
    with pytest.raises(ValueError, match="1 of 2 weekdays listed no note"):
        local.fetch(_DOF)
    monkeypatch.setattr(dof, "DOF_MAX_SILENT", 0.5)
    assert len(local.fetch(_DOF).records) == 3


def test_a_day_cached_under_another_excerpt_version_is_fetched_again(
        monkeypatch: pytest.MonkeyPatch) -> None:
    _serve(monkeypatch)
    local.fetch(_DOF)
    path = dof._day_path(_DAY1)
    held = json.loads(gzip.decompress(path.read_bytes()))
    path.write_bytes(gzip.compress(json.dumps({**held, "excerpt_version": 0}).encode()))
    asked = _serve(monkeypatch)
    local.fetch(_DOF)
    assert dof.DOF_DAY_URL.format(day="03-01-2025") in asked
    assert dof.DOF_DAY_URL.format(day="04-01-2025") not in asked


def test_a_damaged_cached_day_is_refused_naming_the_way_out(
        monkeypatch: pytest.MonkeyPatch) -> None:
    _serve(monkeypatch)
    local.fetch(_DOF)
    dof._day_path(_DAY1).write_bytes(b"not a gzip")
    with pytest.raises(ValueError, match="delete it and fetch again"):
        local.fetch(_DOF)


def test_a_dof_request_failing_once_is_retried(monkeypatch: pytest.MonkeyPatch) -> None:
    note = dof.DOF_NOTE_URL.format(cod=2)
    queue: list[Exception | bytes | None] = [urllib.error.URLError("reset"), b"{\"cut"]
    asked = _serve(monkeypatch, fail=lambda url: queue.pop(0) if url == note and queue else None)
    assert len(local.fetch(_DOF).records) == 3
    assert asked.count(note) == 3


def test_an_answer_that_is_not_message_code_200_is_retried_then_refused(
        monkeypatch: pytest.MonkeyPatch) -> None:
    day = dof.DOF_DAY_URL.format(day="03-01-2025")
    once = [b'{"messageCode": 500}']
    asked = _serve(monkeypatch, fail=lambda url: once.pop() if url == day and once else None)
    assert len(local.fetch(_DOF).records) == 3
    assert asked.count(day) == 2
    _serve(monkeypatch, fail=lambda url: b'{"messageCode": 500}' if url == day else None)
    dof._day_path(_DAY1).unlink()
    with pytest.raises(ValueError, match="answered 500"):
        local.fetch(_DOF)


def test_notes_that_came_back_empty_past_the_gate_refuse_the_fetch(
        monkeypatch: pytest.MonkeyPatch) -> None:
    _serve(monkeypatch, notes={**_NOTES, 2: ""})
    with pytest.raises(ValueError, match="1 of 2 notes with HTML came back empty"):
        local.fetch(_DOF)
    monkeypatch.setattr(dof, "DOF_MAX_EMPTY", 0.5)
    assert local.fetch(_DOF).meta["detail"]["notes"]["empty"] == 1


def test_notes_published_as_images_are_counted_apart_and_gated(
        monkeypatch: pytest.MonkeyPatch) -> None:
    _serve(monkeypatch, notes={**_NOTES, 2: None})
    with pytest.raises(ValueError, match="1 of 2 notes with HTML stated a size of 0"):
        local.fetch(_DOF)
    monkeypatch.setattr(dof, "DOF_MAX_IMAGE_ONLY", 0.5)
    detail = local.fetch(_DOF).meta["detail"]
    assert detail["notes"] == {"read": 1, "image only": 1, "without html": 1, "disallowed": 1}


def test_rubricas_no_rule_cut_past_the_gate_refuse_the_fetch(
        monkeypatch: pytest.MonkeyPatch) -> None:
    _serve(monkeypatch, notes={**_NOTES, 2: _div("Rúbrica.") * 2})
    with pytest.raises(ValueError, match="2 of 3 Rúbricas cut no name"):
        local.fetch(_DOF)


def test_a_corpus_cut_by_another_version_is_refused_on_load(
        monkeypatch: pytest.MonkeyPatch) -> None:
    _serve(monkeypatch)
    local.fetch(_DOF)
    assert local.load(_DOF) is not None
    monkeypatch.setattr(dof, "DOF_CUT_VERSION", dof.DOF_CUT_VERSION + 1)
    with pytest.raises(local.CorpusDamaged, match="cut by cut version"):
        local.load(_DOF)
    monkeypatch.setattr(dof, "DOF_EXCERPT_VERSION", dof.DOF_EXCERPT_VERSION + 1)
    with pytest.raises(local.CorpusDamaged, match="cut from excerpts of version"):
        local.load(_DOF)
    monkeypatch.setattr(dof, "DOF_TO", datetime.date(2025, 1, 5))
    with pytest.raises(local.CorpusDamaged, match="fetched to 2025-01-04"):
        local.load(_DOF)
