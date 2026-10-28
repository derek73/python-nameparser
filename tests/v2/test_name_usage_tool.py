"""Offline checks on tools/name_usage.py, the name-collision lookup.

The tool's sources are a downloaded file, a hand-downloaded file and a
live SPARQL endpoint, none of which a test may touch -- the autouse
guard below turns any network call into a failure. What CAN go wrong
without them is the folding and the bookkeeping, and the failure that
matters is a FALSE ZERO: a word that misses because it was folded into a
different name, or a source that read nothing, reports "not listed",
which is the all-clear the tool exists to withhold. These pin those
pieces, and each spelling row records what the first version got wrong.

tools/ is not a package, so the module is loaded by path, as
_differential_fixtures.py loads compare.py.
"""
import importlib.util
import hashlib
import http.client
import io
import json
import unicodedata
import sys
import urllib.error
import urllib.parse
import urllib.request
import zipfile
from collections import Counter
from collections.abc import Callable
from pathlib import Path
from types import ModuleType
from typing import Any, Protocol

import pytest

from ._differential_fixtures import own_cache, plant_corpus

_PATH = Path(__file__).parents[2] / "tools" / "name_usage.py"


def _load() -> ModuleType:
    spec = importlib.util.spec_from_file_location("name_usage", _PATH)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    # Registered before it runs: @dataclass looks the module up in
    # sys.modules to check string annotations for ClassVar/InitVar, and
    # fails on a module loaded by path that is not in it.
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


tool = _load()


class _NetworkUsed(AssertionError):
    pass


@pytest.fixture(autouse=True)
def _no_network(monkeypatch: pytest.MonkeyPatch) -> None:
    def refuse(*args: object, **kwargs: object) -> None:
        raise _NetworkUsed("a test reached the network")
    monkeypatch.setattr(urllib.request, "urlopen", refuse)


#: The real loader, for the tests that read a cached dictionary through
#: main; every other test sees no dictionary, as an empty cache under
#: --no-wikidata would, since an online main would otherwise download it.
_LOAD_NAMDICT = tool.load_namdict


@pytest.fixture(autouse=True)
def _no_namdict(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(tool, "load_namdict", lambda download: None)


#: The same for the NPPES tally, which a developer's real cache may hold:
#: a test reading it would pass or fail by what is on that machine.
_LOAD_NPPES = tool.load_nppes


@pytest.fixture(autouse=True)
def _no_nppes(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(tool, "load_nppes", lambda download: None)


#: And for the local corpora, which a developer's cache may hold too.
_LOAD_LOCALS = tool.load_locals


@pytest.fixture(autouse=True)
def _no_locals(monkeypatch: pytest.MonkeyPatch,
               tmp_path_factory: pytest.TempPathFactory) -> None:
    # The cache too: a local corpus's word index is written there, and a
    # test's must never land in the developer's.
    own_cache(monkeypatch, tmp_path_factory)
    monkeypatch.setattr(tool, "load_locals", lambda: [])


def test_the_network_guard_bites() -> None:
    # Negative control for the guard: without it, this call goes to
    # query.wikidata.org.
    with pytest.raises(_NetworkUsed):
        tool._sparql("SELECT * WHERE {}")


def test_sparql_sends_the_query_in_the_body_not_the_url(
        monkeypatch: pytest.MonkeyPatch) -> None:
    # #680: a GET carried the query in the URL, and the endpoint answered
    # HTTP 431 once it passed about 7 KB -- reached by a seven-letter
    # Cyrillic word (Младший), each letter six bytes percent-encoded and
    # repeated once per label language and spelling.
    sent: list[urllib.request.Request] = []

    def capture(request: urllib.request.Request, **kwargs: object) -> io.BytesIO:
        sent.append(request)
        return io.BytesIO(b'{"results": {"bindings": []}}')
    monkeypatch.setattr(urllib.request, "urlopen", capture)
    query = tool.wikidata_countries_query(tool.spellings("Младший"))
    assert tool._sparql(query) == {"results": {"bindings": []}}
    (request,) = sent
    assert request.get_method() == "POST"
    assert request.full_url == tool.WIKIDATA_ENDPOINT
    assert isinstance(request.data, bytes)
    assert urllib.parse.parse_qs(request.data.decode()) == {"query": [query]}


_CENSUS = """name,rank,count,prop100k,cum_prop100k,pctwhite,pctblack,pctapi,pctaian,pct2prace,pcthispanic
OBRIEN,258,118557,40.19,0,93.85,1.29,0.76,0.27,1.51,2.32
SHEHU,39212,561,0.19,0,94.47,3.92,(S),0,0.89,(S)
SORENSEN,1101,28069,9.5,0,96.6,0.5,0.6,0.5,1.1,0.7
"""


@pytest.mark.parametrize(("word", "key"), [
    ("O'Brien", "OBRIEN"),       # apostrophe dropped, as the Census spells it
    ("de la Cruz", "DELACRUZ"),  # spaces dropped
    ("Ó Murchú", "OMURCHU"),     # diacritics folded away
    # Letters NFKD leaves whole. The first version deleted them, looking
    # up a DIFFERENT name: SRENSEN, STRAU, UKASZ, and SIR for Æsir.
    ("Sørensen", "SORENSEN"),
    ("Strauß", "STRAUSS"),
    ("Łukasz", "LUKASZ"),
    ("Æsir", "AESIR"),
    ("Đorđević", "DORDEVIC"),
    # A modifier letter (the ʻokina) is an apostrophe, dropped like
    # O'Brien's. The second version refused it as a letter with no ASCII
    # spelling, leaving the name with no answer.
    ("Kaʻahumanu", "KAAHUMANU"),
    # No ASCII spelling, wholly or in part: no key at all, never a partial
    # one (the first version looked up AHMED for the second).
    ("关", ""),
    ("Ahmed关", ""),
])
def test_us_key_folds_a_word_the_way_the_us_lists_spell_it(word: str, key: str) -> None:
    assert tool.us_key(word) == key


def test_census_usage_finds_a_folded_surname_and_says_how() -> None:
    usage = tool.census_usage("Sørensen", tool.read_census(_CENSUS))
    assert usage.family == 28069
    assert "looked up as SORENSEN" in usage.note


def test_census_usage_omits_suppressed_shares() -> None:
    # (S) marks a share the Census suppressed for privacy; printing it as a
    # percentage would invent a number.
    note = tool.census_usage("shehu", tool.read_census(_CENSUS)).note
    assert "asian/PI" not in note and "hispanic" not in note
    assert "white 94.47%" in note


def test_census_usage_distinguishes_unlisted_from_unrepresentable() -> None:
    table = tool.read_census(_CENSUS)
    unlisted = tool.census_usage("Marshal", table)
    assert (unlisted.status, unlisted.family) == ("ok", 0)
    unrepresentable = tool.census_usage("关", table)
    assert unrepresentable.status == "unrepresentable"
    assert unrepresentable.family is None  # no answer, not a zero


def test_read_census_names_missing_columns() -> None:
    with pytest.raises(ValueError, match="pctwhite"):
        tool.read_census("name,rank,count\nSMITH,1,2442977\n")


def _zip(files: dict[str, str]) -> zipfile.ZipFile:
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as zf:
        for name, text in files.items():
            zf.writestr(name, text)
    buffer.seek(0)
    return zipfile.ZipFile(buffer)


def _ssa_files(**extra: str) -> dict[str, str]:
    files = {f"yob{year}.txt": "Filler,F,5\n" for year in range(1880, 1990)}
    files.update(extra)
    return files


def test_read_ssa_totals_each_name_by_sex_across_years() -> None:
    totals = tool.read_ssa(_zip(_ssa_files(**{
        "yob1990.txt": "Justice,F,40\nJustice,M,60\n",
        "yob2000.txt": "Justice,M,100\nMarshal,M,7\n",
        "NationalReadMe.pdf": "not data",
    })))
    assert totals["justice"] == {"F": 40, "M": 160}
    assert tool.ssa_usage("Justice", totals).given == 200


def test_read_ssa_reads_a_re_zipped_folder_in_any_case() -> None:
    files = {f"names/YOB{year}.TXT": "Justice,M,5\n" for year in range(1880, 1990)}
    assert tool.read_ssa(_zip(files))["justice"] == {"M": 5 * 110}


@pytest.mark.parametrize("files", [
    {"AK.TXT": "AK,F,1910,Mary,14\n"},           # the state-level zip
    {f"yob{y}.txt": "A,F,5\n" for y in range(1880, 1900)},  # a partial set
])
def test_read_ssa_refuses_a_zip_that_is_not_the_national_file(files: dict[str, str]) -> None:
    # The first version read such a zip as empty, so every word reported
    # "not listed" -- a false zero for every name.
    with pytest.raises(ValueError, match="yobYYYY.txt"):
        tool.read_ssa(_zip(files))


def test_ssa_usage_distinguishes_unlisted_from_unrepresentable() -> None:
    table = {"justice": Counter(M=5)}
    assert tool.ssa_usage("Zzyzx", table).given == 0
    unrepresentable = tool.ssa_usage("关", table)
    assert unrepresentable.status == "unrepresentable"
    assert unrepresentable.given is None


def test_ssa_usage_reports_a_missing_download_without_a_count() -> None:
    usage = tool.ssa_usage("justice", None)
    assert (usage.status, usage.given) == ("not downloaded", None)


def test_render_shows_no_answer_and_unlisted_differently_from_a_count() -> None:
    text = tool.render("x", [
        tool.Usage("census", family=0, floor="<100"),
        tool.Usage("ssa", status="not downloaded"),
        tool.Usage("wikidata", given=0, family=12, lower_bound=True),
    ])
    rows = {cells[0]: cells[1:]
            for cells in map(str.split, text.splitlines()[2:]) if cells}
    assert rows["census"] == ["-", "<100", "-"]
    assert rows["ssa"] == ["-", "-", "-"]
    assert rows["wikidata"] == ["0+", "12+", "-"]


def test_spellings_cover_lower_and_capitalized_forms_once() -> None:
    assert tool.spellings("de la cruz") == ["de la cruz", "De La Cruz"]
    assert tool.spellings("McDonald") == ["McDonald", "mcdonald", "Mcdonald"]


def test_wikidata_queries_escape_the_word_in_every_language() -> None:
    query = tool.wikidata_totals_query(['Say "hi"'], languages=("mul", "zh-hans"))
    assert r'"Say \"hi\""@mul' in query
    assert r'"Say \"hi\""@zh-hans' in query


def _stub_sparql(monkeypatch: pytest.MonkeyPatch,
                 responses: list[Any]) -> list[str]:
    queries: list[str] = []

    def fake(query: str) -> dict[str, Any]:
        queries.append(query)
        response = responses[len(queries) - 1]
        if isinstance(response, Exception):
            raise response
        return {"results": {"bindings": [
            {k: {"value": v} for k, v in row.items()} for row in response]}}
    monkeypatch.setattr(tool, "_sparql", fake)
    return queries


def test_wikidata_usage_sends_every_spelling_in_one_query(monkeypatch: pytest.MonkeyPatch) -> None:
    # The first version queried each spelling separately and summed the
    # counts, counting twice a person reached through two spellings.
    queries = _stub_sparql(monkeypatch, [
        [{"role": "family", "n": "180"}, {"role": "given", "n": "1"}],
        [{"role": "family", "country": "Albania", "n": "11"},
         {"role": "family", "n": "148"}],
    ])
    usage = tool.wikidata_usage("shehu", top=5)
    assert len(queries) == 2
    assert '"shehu"@mul' in queries[0] and '"Shehu"@mul' in queries[0]
    assert (usage.given, usage.family) == (1, 180)
    assert usage.family_countries == [("Albania", 11)]
    assert usage.family_stateless == 148
    assert "matched as shehu, Shehu" in usage.note


@pytest.mark.parametrize("failure", [
    OSError("timed out"),
    json.JSONDecodeError("Expecting value", "<html>", 0),  # not an OSError
])
def test_wikidata_usage_reports_a_failed_query_as_no_answer(
        monkeypatch: pytest.MonkeyPatch, failure: Exception) -> None:
    _stub_sparql(monkeypatch, [[{"role": "given", "n": "3"}], failure])
    usage = tool.wikidata_usage("shehu", top=5)
    assert usage.status == "failed"
    assert (usage.given, usage.family) == (None, None)


def test_read_wikidata_refuses_a_role_it_cannot_have_produced() -> None:
    # A misspelled role must not fall through to a count of 0.
    with pytest.raises(ValueError, match="givn"):
        tool.read_wikidata([{"role": "givn", "n": "5"}], [], top=5)


def test_main_reports_json_offline_without_downloading(
        monkeypatch: pytest.MonkeyPatch, tmp_path: Path,
        capsys: pytest.CaptureFixture[str]) -> None:
    monkeypatch.setenv("NAMEPARSER_TOOLS_CACHE", str(tmp_path))
    with zipfile.ZipFile(tmp_path / tool.CENSUS_FILE, "w") as zf:
        zf.writestr(tool.CENSUS_MEMBER, _CENSUS)
    status = tool.main(["--no-wikidata", "--json", "O'Brien", "关"])
    out, err = capsys.readouterr()
    report = json.loads(out)
    assert status == 0
    assert list(report) == ["O'Brien", "关"]
    assert [u["source"] for u in report["关"]] == [
        "US Census 2010 surnames", "US SSA given names 1880-",
        tool.NAMDICT_SOURCE, tool.NPPES_SOURCE]
    assert report["O'Brien"][0]["family"] == 118557
    assert report["关"][0]["family"] is None  # null, not 0
    assert "SSA given names not downloaded" in err


def test_main_does_not_download_under_no_wikidata(
        monkeypatch: pytest.MonkeyPatch, tmp_path: Path,
        capsys: pytest.CaptureFixture[str]) -> None:
    monkeypatch.setenv("NAMEPARSER_TOOLS_CACHE", str(tmp_path))
    assert tool.main(["--no-wikidata", "--json", "knight"]) == 0
    census = json.loads(capsys.readouterr().out)["knight"][0]
    assert (census["status"], census["family"]) == ("not downloaded", None)


def test_main_exits_2_when_a_source_failed(
        monkeypatch: pytest.MonkeyPatch, tmp_path: Path,
        capsys: pytest.CaptureFixture[str]) -> None:
    monkeypatch.setenv("NAMEPARSER_TOOLS_CACHE", str(tmp_path))
    (tmp_path / tool.CENSUS_FILE).write_text("<html>error page</html>")
    assert tool.main(["--no-wikidata", "knight"]) == 2
    assert "delete it and run again" in capsys.readouterr().out


def test_main_reports_a_bad_ssa_zip_without_losing_the_other_sources(
        monkeypatch: pytest.MonkeyPatch, tmp_path: Path,
        capsys: pytest.CaptureFixture[str]) -> None:
    # The second version validated the SSA zip outside any try, so a
    # state-level zip saved in its place crashed the run and lost the
    # Census answer too.
    monkeypatch.setenv("NAMEPARSER_TOOLS_CACHE", str(tmp_path))
    with zipfile.ZipFile(tmp_path / tool.CENSUS_FILE, "w") as zf:
        zf.writestr(tool.CENSUS_MEMBER, _CENSUS)
    with zipfile.ZipFile(tmp_path / tool.SSA_FILE, "w") as zf:
        zf.writestr("AK.TXT", "AK,F,1910,Mary,14\n")
    assert tool.main(["--no-wikidata", "--json", "shehu"]) == 2
    out, err = capsys.readouterr()
    census, ssa, *_ = json.loads(out)["shehu"]
    assert census["family"] == 561
    assert (ssa["status"], ssa["given"]) == ("failed", None)
    assert "not downloaded" not in err  # the file exists; it is just wrong


# -- the CJK name index (#707) --------------------------------------------

@pytest.mark.parametrize(("word", "cjk"), [
    ("关", True), ("씨", True), ("さん", True), ("ｻﾝ", True),
    ("佐々木", True), ("Smith", False), ("Sørensen", False),
])
def test_is_cjk_finds_han_kana_and_hangul(word: str, cjk: bool) -> None:
    assert tool.is_cjk(word) is cjk


def test_us_sources_say_they_do_not_apply_to_a_cjk_word() -> None:
    # A CJK word is not an unlisted name there: the lists hold no
    # non-Latin spelling at all, and the report says so in those words.
    census = tool.census_usage("議員", tool.read_census(_CENSUS))
    ssa = tool.ssa_usage("議員", {"justice": Counter(M=5)})
    for usage in (census, ssa):
        assert usage.status == "unrepresentable"
        assert "does not apply to a CJK word" in usage.note


def test_labels_query_asks_for_the_batch_by_item_and_filters_to_cjk() -> None:
    query = tool.labels_query(["Q1", "Q2"])
    assert "VALUES ?item { wd:Q1 wd:Q2 }" in query
    assert "REGEX(STR(?label)" in query
    assert "wd:Q101352" in tool.ids_query("Q101352")


def _listing(*qids: str) -> list[list[dict[str, str]]]:
    """The count query's answer, then the listing's."""
    return [[{"n": str(len(qids))}],
            [{"item": f"http://www.wikidata.org/entity/{q}"} for q in qids]]


def _labels(*pairs: tuple[str, str]) -> list[dict[str, str]]:
    return [{"item": f"http://www.wikidata.org/entity/{q}", "label": label}
            for q, label in pairs]


def _overrun() -> Exception:
    # What WDQS sends at its limit: a 200 whose JSON stops mid-stream.
    return json.JSONDecodeError("Expecting ',' delimiter", "{...", 3)


@pytest.fixture
def one_class(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    # The listing is fetched as CSV; route it through the _sparql stub so
    # one response queue serves every query.
    monkeypatch.setattr(tool, "_sparql_csv",
                        lambda query: tool._bindings(tool._sparql(query)))
    monkeypatch.setenv("NAMEPARSER_TOOLS_CACHE", str(tmp_path))
    monkeypatch.setattr(tool, "NAME_CLASSES", {"Q101352": "family"})
    monkeypatch.setattr(tool, "INDEX_BATCH", 2)
    monkeypatch.setattr(tool, "INDEX_MIN_BATCH", 1)


def _values(query: str) -> list[str]:
    return query.split("VALUES ?item { ")[1].split(" }")[0].split()


@pytest.mark.usefixtures("one_class")
def test_a_class_is_listed_once_and_labelled_by_batch(
        monkeypatch: pytest.MonkeyPatch) -> None:
    queries = _stub_sparql(monkeypatch, [
        *_listing("Q10", "Q9", "Q300", "Q2", "Q9"),  # unsorted, one repeat
        _labels(("Q2", "向殿")), _labels(("Q10", "井殿")),
    ])
    index = tool.load_index(download=True)
    assert index is not None
    # Sorted by number, not as strings, with the repeat dropped.
    assert [_values(q) for q in queries[2:]] == [
        ["wd:Q2", "wd:Q9"], ["wd:Q10", "wd:Q300"]]
    assert {(e.qid, e.role, e.label) for e in index.entries} == {
        ("Q2", "family", "向殿"), ("Q10", "family", "井殿")}


@pytest.mark.usefixtures("one_class")
def test_the_listing_skips_lexemes_and_refuses_anything_else(
        monkeypatch: pytest.MonkeyPatch) -> None:
    # Lexemes and their senses carry P31 family name too (L1000723 and
    # L2873-S1 did, 2026-10-17); no person bears one, and the first two
    # builds failed on them.
    queries = _stub_sparql(monkeypatch, [
        *_listing("Q1", "L1000723", "L2873-S1", "L5-F2"), _labels()])
    assert tool.load_index(download=True) is not None
    assert _values(queries[2]) == ["wd:Q1"]
    _stub_sparql(monkeypatch, [[{"n": "1"}], [{"item": "_:b0"}]])
    with pytest.raises(ValueError, match="not an item"):
        tool.load_index(download=True, refresh=True)


@pytest.mark.usefixtures("one_class")
def test_a_batch_that_overruns_is_halved(
        monkeypatch: pytest.MonkeyPatch) -> None:
    queries = _stub_sparql(monkeypatch, [
        *_listing("Q1", "Q2"), _overrun(), _labels(("Q1", "向殿")), _labels(),
    ])
    index = tool.load_index(download=True)
    assert index is not None
    assert [_values(q) for q in queries[2:]] == [
        ["wd:Q1", "wd:Q2"], ["wd:Q1"], ["wd:Q2"]]
    assert [e.label for e in index.entries] == ["向殿"]


@pytest.mark.usefixtures("one_class")
def test_a_resumed_build_queries_only_what_is_missing(
        monkeypatch: pytest.MonkeyPatch) -> None:
    # An interrupted build keeps its finished batches and its item list,
    # and a halved batch is not asked whole again -- it would only
    # overrun a second time.
    _stub_sparql(monkeypatch, [
        *_listing("Q1", "Q2", "Q3", "Q4"), _overrun(), _labels(("Q1", "向殿")),
        OSError("down")])
    with pytest.raises(OSError):
        tool.load_index(download=True)
    queries = _stub_sparql(monkeypatch, [
        _labels(("Q2", "井殿")), _labels(("Q3", "殿"))])
    index = tool.load_index(download=True)
    assert index is not None
    assert [_values(q) for q in queries] == [["wd:Q2"], ["wd:Q3", "wd:Q4"]]
    assert sorted(e.label for e in index.entries) == ["井殿", "向殿", "殿"]


@pytest.mark.usefixtures("one_class")
def test_a_complete_index_loads_offline_and_an_incomplete_one_does_not(
        monkeypatch: pytest.MonkeyPatch) -> None:
    _stub_sparql(monkeypatch, [])  # any query fails the test
    assert tool.load_index(download=False) is None
    _stub_sparql(monkeypatch, [*_listing("Q1"), _labels(("Q1", "向殿"))])
    fetched = tool.load_index(download=True)
    assert fetched is not None and fetched.fetched
    _stub_sparql(monkeypatch, [])
    index = tool.load_index(download=False)
    assert index is not None and index.entries[0].label == "向殿"


@pytest.mark.usefixtures("one_class")
def test_refresh_fetches_the_index_again(
        monkeypatch: pytest.MonkeyPatch) -> None:
    _stub_sparql(monkeypatch, [*_listing("Q1"), _labels(("Q1", "向殿"))])
    tool.load_index(download=True)
    _stub_sparql(monkeypatch, [*_listing("Q1"), _labels(("Q1", "井殿"))])
    index = tool.load_index(download=True, refresh=True)
    assert index is not None and index.entries[0].label == "井殿"


@pytest.mark.usefixtures("one_class")
@pytest.mark.parametrize("failure", [
    urllib.error.HTTPError("u", 400, "Bad Request", {}, io.BytesIO(b"syntax")),  # type: ignore[arg-type]
    urllib.error.HTTPError("u", 500, "Error", {}, io.BytesIO(b"MalformedQuery")),  # type: ignore[arg-type]
])
def test_an_error_that_is_not_an_overrun_is_not_retried_smaller(
        monkeypatch: pytest.MonkeyPatch, failure: Exception) -> None:
    queries = _stub_sparql(monkeypatch, [*_listing("Q1", "Q2"), failure])
    with pytest.raises(urllib.error.HTTPError):
        tool.load_index(download=True)
    assert len(queries) == 3  # count, listing, and the one failure


@pytest.mark.usefixtures("one_class")
@pytest.mark.parametrize("failure", [
    urllib.error.HTTPError("u", 504, "Gateway Timeout", {}, io.BytesIO(b"")),  # type: ignore[arg-type]
    urllib.error.HTTPError("u", 500, "Error", {}, io.BytesIO(  # type: ignore[arg-type]
        b"java.util.concurrent.TimeoutException")),
    urllib.error.HTTPError("u", 502, "Bad Gateway", {}, io.BytesIO(b"")),  # type: ignore[arg-type]
    http.client.IncompleteRead(b""),
    TimeoutError("read timed out"),
])
def test_a_timeout_is_an_overrun(
        monkeypatch: pytest.MonkeyPatch, failure: Exception) -> None:
    _stub_sparql(monkeypatch, [*_listing("Q1", "Q2"), failure, _labels(), _labels()])
    assert tool.load_index(download=True) is not None


@pytest.mark.usefixtures("one_class")
def test_halving_stops_at_the_smallest_batch(
        monkeypatch: pytest.MonkeyPatch) -> None:
    _stub_sparql(monkeypatch, [*_listing("Q1", "Q2"), _overrun(), _overrun()])
    with pytest.raises(ValueError, match="items 0-1 still overran"):
        tool.load_index(download=True)


@pytest.mark.usefixtures("one_class")
def test_a_listing_cut_short_is_an_error(
        monkeypatch: pytest.MonkeyPatch) -> None:
    _stub_sparql(monkeypatch, [[{"n": "5000"}], _listing("Q1", "Q2")[1]])
    with pytest.raises(ValueError, match="returned 2 of 5,000 items"):
        tool.load_index(download=True)


def test_sparql_csv_reads_the_rows_by_header(
        monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(urllib.request, "urlopen", lambda request, timeout: (
        io.BytesIO(b"item\r\nhttp://www.wikidata.org/entity/Q1\r\n")))
    assert tool._sparql_csv("SELECT") == [
        {"item": "http://www.wikidata.org/entity/Q1"}]


@pytest.mark.usefixtures("one_class")
def test_an_overrun_listing_is_an_error_not_an_empty_class(
        monkeypatch: pytest.MonkeyPatch) -> None:
    _stub_sparql(monkeypatch, [_overrun()])
    with pytest.raises(ValueError, match="listing wd:Q101352 items overran"):
        tool.load_index(download=True)


class _Index(Protocol):
    # tools/ is loaded by path, so mypy cannot see NameIndex itself.
    def ending_in(self, word: str) -> list[Any]: ...
    def boundaries(self, word: str) -> list[Any]: ...


def _index(*entries: tuple[str, str, str]) -> _Index:
    return tool.NameIndex([tool.IndexEntry(*e) for e in entries],
                          fetched="2026-10-17")


def test_ending_in_matches_labels_that_end_in_the_word_or_equal_it() -> None:
    index = _index(("Q1", "family", "向殿"), ("Q2", "family", "殿"),
                   ("Q3", "family", "殿村"), ("Q4", "given", "二世"))
    assert {e.qid for e in index.ending_in("殿")} == {"Q1", "Q2"}


def test_boundaries_find_a_family_tail_followed_by_a_whole_given_name() -> None:
    # 阿部 + 長 is how 部長 ends a real name without either part ending
    # in 部長: the argument #707 makes against peeling it.
    index = _index(("Q1", "family", "阿部"), ("Q2", "family", "岡部"),
                   ("Q3", "given", "長"), ("Q4", "given", "部長代"),
                   ("Q5", "family", "長"))
    splits = index.boundaries("部長")
    assert [(s.family_tail, s.given) for s in splits] == [("部", "長")]
    assert splits[0].family_items == ["Q1", "Q2"]
    assert splits[0].given_items == ["Q3"]


def test_ends_with_usage_counts_bearers_of_the_matched_items(
        monkeypatch: pytest.MonkeyPatch) -> None:
    index = _index(("Q1", "family", "向殿"), ("Q2", "family", "井殿"),
                   ("Q3", "given", "太郎"))
    queries = _stub_sparql(monkeypatch, [
        [{"role": "family", "n": "7"}],
        [{"role": "family", "country": "Japan", "n": "6"},
         {"role": "family", "n": "1"}],
    ])
    usage = tool.ends_with_usage("殿", index, top=5)
    assert "VALUES ?item { wd:Q1 wd:Q2 }" in queries[0]
    assert "rdfs:label" not in queries[0].split("UNION")[0]
    assert (usage.given, usage.family) == (0, 7)
    assert usage.family_countries == [("Japan", 6)]
    assert "2 name items end in it: 井殿 Q2, 向殿 Q1" in usage.note


def test_ends_with_usage_names_a_single_item_in_the_singular(
        monkeypatch: pytest.MonkeyPatch) -> None:
    _stub_sparql(monkeypatch, [[{"role": "given", "n": "109"}], []])
    usage = tool.ends_with_usage("二世", _index(("Q18339792", "given", "厄德二世")),
                                 top=5)
    assert "1 name item ends in it: 厄德二世 Q18339792" in usage.note


@pytest.mark.usefixtures("one_class")
def test_loading_a_cached_index_prints_no_progress(
        monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture[str]) -> None:
    monkeypatch.setattr(tool, "INDEX_BATCH", 1)
    _stub_sparql(monkeypatch, [*_listing(*(f"Q{n}" for n in range(1, 51))),
                               *([_labels()] * 50)])
    tool.load_index(download=True)
    assert "50 of 50 items" in capsys.readouterr().err
    _stub_sparql(monkeypatch, [])
    tool.load_index(download=True)
    assert capsys.readouterr().err == ""


def test_ends_with_usage_with_no_matching_item_sends_no_query(
        monkeypatch: pytest.MonkeyPatch) -> None:
    queries = _stub_sparql(monkeypatch, [])
    usage = tool.ends_with_usage("議員", _index(("Q1", "family", "向殿")), top=5)
    assert queries == []
    assert (usage.status, usage.given, usage.family) == ("ok", 0, 0)
    assert "no indexed name item ends in 議員" in usage.note


def test_ends_with_usage_sums_chunks_and_says_it_may_double_count(
        monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(tool, "ITEM_CHUNK", 1)
    index = _index(("Q1", "family", "向殿"), ("Q2", "family", "井殿"))
    _stub_sparql(monkeypatch, [
        [{"role": "family", "n": "3"}], [{"role": "family", "n": "3"}],
        [{"role": "family", "n": "4"}], [{"role": "family", "n": "4"}],
    ])
    usage = tool.ends_with_usage("殿", index, top=5)
    assert usage.family == 7
    assert "may count twice" in usage.note


def test_ends_with_usage_counts_people_across_a_boundary(
        monkeypatch: pytest.MonkeyPatch) -> None:
    index = _index(("Q1", "family", "阿部"), ("Q3", "given", "長"))
    queries = _stub_sparql(monkeypatch, [_people("Q99", "Q7")])
    usage = tool.ends_with_usage("部長", index, top=5)
    assert (usage.given, usage.family) == (0, 0)  # nothing ENDS in 部長
    assert "VALUES ?f { wd:Q1 }" in queries[0]
    assert "VALUES ?g { wd:Q3 }" in queries[0]
    [split] = usage.splits
    assert (split.people, split.example) == (2, "Q7")
    text = tool.render("部長", [usage])
    assert "family ending 部 + given 長: 2+ people" in text
    assert "e.g. 阿部; bearer Q7" in text


def test_sparql_waits_out_a_rate_limit_and_retries(
        monkeypatch: pytest.MonkeyPatch) -> None:
    waits: list[float] = []
    calls: list[int] = []

    def answer(request: urllib.request.Request, timeout: float) -> io.BytesIO:
        calls.append(1)
        if len(calls) == 1:
            raise urllib.error.HTTPError(
                "u", 429, "Too Many Requests",
                {"Retry-After": "7"}, io.BytesIO(b""))  # type: ignore[arg-type]
        return io.BytesIO(b'{"results": {"bindings": []}}')
    monkeypatch.setattr(urllib.request, "urlopen", answer)
    monkeypatch.setattr(tool, "_sleep", waits.append)
    assert tool._sparql("SELECT") == {"results": {"bindings": []}}
    assert waits == [7]


def test_main_skips_the_index_for_a_latin_word(
        monkeypatch: pytest.MonkeyPatch, tmp_path: Path,
        capsys: pytest.CaptureFixture[str]) -> None:
    monkeypatch.setenv("NAMEPARSER_TOOLS_CACHE", str(tmp_path))
    monkeypatch.setattr(tool, "load_census", lambda download: None)
    monkeypatch.setattr(tool, "load_index", lambda download, refresh=False: (
        pytest.fail("the index was loaded for a Latin word")))
    _stub_sparql(monkeypatch, [[], []])
    assert tool.main(["--json", "knight"]) == 0
    sources = [u["source"] for u in json.loads(capsys.readouterr().out)["knight"]]
    assert sources[-1] == "Wikidata people"


@pytest.mark.parametrize("local", ["none", "not fetched", "fetched"])
def test_main_adds_the_ends_with_row_for_a_cjk_word(
        monkeypatch: pytest.MonkeyPatch, tmp_path: Path,
        capsys: pytest.CaptureFixture[str], local: str) -> None:
    # With a local corpus listed, fetched or not: the local rows' loop
    # once shadowed main's CJK index, so the row read None or a WordIndex.
    monkeypatch.setenv("NAMEPARSER_TOOLS_CACHE", str(tmp_path))
    monkeypatch.setattr(tool, "load_census", lambda download: None)
    corpus = _local("Ann Lee, MD")
    locals_ = {"none": [],
               "not fetched": [("ctgov-officials", None, "")],
               "fetched": [("ctgov-officials", corpus, "")]}
    monkeypatch.setattr(tool, "load_locals", lambda: locals_[local])
    monkeypatch.setattr(tool, "load_index", lambda download, refresh=False:
                        _index(("Q1", "family", "向殿")))
    _stub_sparql(monkeypatch, [[], [], [{"role": "family", "n": "1"}], []])
    assert tool.main(["--json", "殿"]) == 0
    rows = json.loads(capsys.readouterr().out)["殿"]
    assert rows[-1]["source"] == tool.ENDS_WITH_SOURCE
    assert rows[-1]["family"] == 1


def test_main_reports_an_index_that_failed_to_load(
        monkeypatch: pytest.MonkeyPatch, tmp_path: Path,
        capsys: pytest.CaptureFixture[str]) -> None:
    monkeypatch.setenv("NAMEPARSER_TOOLS_CACHE", str(tmp_path))
    monkeypatch.setattr(tool, "load_census", lambda download: None)

    def broken(download: bool, refresh: bool = False) -> None:
        raise OSError("down")
    monkeypatch.setattr(tool, "load_index", broken)
    _stub_sparql(monkeypatch, [[], []])
    assert tool.main(["--json", "殿"]) == 2
    row = json.loads(capsys.readouterr().out)["殿"][-1]
    assert (row["status"], row["family"]) == ("failed", None)


# -- review of #712: the index's failure paths ------------------------------

def _people(*qids: str) -> list[dict[str, str]]:
    return [{"p": f"http://www.wikidata.org/entity/{q}"} for q in qids]


@pytest.mark.usefixtures("one_class")
def test_each_class_keeps_its_own_role_and_batches(
        monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(tool, "NAME_CLASSES",
                        {"Q101352": "family", "Q202444": "given"})
    queries = _stub_sparql(monkeypatch, [
        *_listing("Q1"), _labels(("Q1", "向殿")),
        *_listing("Q2"), _labels(("Q2", "太郎")),
    ])
    index = tool.load_index(download=True)
    assert index is not None
    assert {(e.qid, e.role) for e in index.entries} == {
        ("Q1", "family"), ("Q2", "given")}
    assert [_values(q) for q in queries if "rdfs:label" in q] == [
        ["wd:Q1"], ["wd:Q2"]]


@pytest.mark.usefixtures("one_class")
def test_a_class_that_lists_no_items_is_an_error_not_an_empty_index(
        monkeypatch: pytest.MonkeyPatch) -> None:
    # A mistyped or merged class answers 0 to both queries; caching that
    # would make every later ends-with row a silent zero.
    _stub_sparql(monkeypatch, [*_listing()])
    with pytest.raises(ValueError, match="wd:Q101352 lists no items"):
        tool.load_index(download=True)
    assert not (tool.cache_dir() / tool.INDEX_DIR / "Q101352-ids.json").exists()


@pytest.mark.usefixtures("one_class")
@pytest.mark.parametrize(("rows", "loads"), [(999, True), (998, False)])
def test_the_listing_count_allows_a_thousandth_of_slack(
        monkeypatch: pytest.MonkeyPatch, rows: int, loads: bool) -> None:
    monkeypatch.setattr(tool, "INDEX_BATCH", 5000)
    qids = [f"Q{n}" for n in range(1, rows + 1)]
    _stub_sparql(monkeypatch, [[{"n": "1000"}], _listing(*qids)[1], _labels()])
    if loads:
        assert tool.load_index(download=True) is not None
    else:
        with pytest.raises(ValueError, match="returned 998 of 1,000"):
            tool.load_index(download=True)


@pytest.mark.usefixtures("one_class")
@pytest.mark.parametrize(("name", "content"), [
    ("Q101352-ids.json", "["),
    ("Q101352-ids.json", "{}"),
    ("Q101352-ids.json", '["Q1", "L5"]'),
    ("Q101352-ids.json", "[]"),
    ("Q101352-0-1.json", '{"rows": []}'),
    ("Q101352-0-1.json", '[]'),
    ("Q101352-0-1.json", '{"fetched": "x", "digest": "DIGEST", "rows": null}'),
    ("Q101352-0-1.json", '{"fetched": "x", "digest": "DIGEST", "rows": [["Q9", "殿"]]}'),
    ("Q101352-0-1.json", '{"fetched": "x", "digest": "DIGEST", "rows": [["Q1"]]}'),
    ("Q101352-0-1.json", '{"fetched": "x", "digest": "DIGEST", "rows": [["Q1", 5]]}'),
    ("version.json", "{"),
])
def test_an_unusable_cache_file_is_named_with_its_remedy(
        monkeypatch: pytest.MonkeyPatch, name: str, content: str) -> None:
    _stub_sparql(monkeypatch, [*_listing("Q1"), _labels(("Q1", "向殿"))])
    tool.load_index(download=True)
    # DIGEST stands for the batch's own, so the row checks are reached.
    (tool.cache_dir() / tool.INDEX_DIR / name).write_text(
        content.replace("DIGEST", tool._batch_digest(["Q1"])))
    _stub_sparql(monkeypatch, [])
    with pytest.raises(ValueError, match=f"{name} is unusable.*--refresh-index"):
        tool.load_index(download=True)


@pytest.mark.usefixtures("one_class")
def test_a_batch_cached_against_another_listing_is_fetched_again(
        monkeypatch: pytest.MonkeyPatch) -> None:
    # Deleting one class's listing must not leave its batches answering
    # for whatever items now sit at the same positions.
    _stub_sparql(monkeypatch, [*_listing("Q1", "Q2"), _labels(("Q1", "向殿"))])
    tool.load_index(download=True)
    (tool.cache_dir() / tool.INDEX_DIR / "Q101352-ids.json").unlink()
    queries = _stub_sparql(monkeypatch, [
        *_listing("Q10", "Q11"), _labels(("Q11", "井殿"))])
    index = tool.load_index(download=True)
    assert index is not None
    assert [(e.qid, e.label) for e in index.entries] == [("Q11", "井殿")]
    assert _values(queries[2]) == ["wd:Q10", "wd:Q11"]


@pytest.mark.usefixtures("one_class")
def test_an_index_from_an_older_version_of_the_tool_is_rebuilt(
        monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture[str]) -> None:
    _stub_sparql(monkeypatch, [*_listing("Q1"), _labels(("Q1", "向殿"))])
    tool.load_index(download=True)
    (tool.cache_dir() / tool.INDEX_DIR / "version.json").write_text("1")
    _stub_sparql(monkeypatch, [])
    assert tool.load_index(download=False) is None
    capsys.readouterr()
    _stub_sparql(monkeypatch, [*_listing("Q1"), _labels(("Q1", "井殿"))])
    index = tool.load_index(download=True)
    assert index is not None and index.entries[0].label == "井殿"
    assert "older version" in capsys.readouterr().err


def test_sparql_csv_refuses_a_body_cut_mid_line(
        monkeypatch: pytest.MonkeyPatch) -> None:
    # A last line cut inside its IRI (Q1234567 arriving as Q12) is still
    # a valid Q-id; the missing newline is the only sign.
    monkeypatch.setattr(urllib.request, "urlopen", lambda request, timeout: (
        io.BytesIO(b"item\r\nhttp://www.wikidata.org/entity/Q12")))
    with pytest.raises(ValueError, match="cut short"):
        tool._sparql_csv("SELECT")


def test_sparql_csv_asks_for_csv(monkeypatch: pytest.MonkeyPatch) -> None:
    seen: list[str | None] = []

    def answer(request: urllib.request.Request, timeout: float) -> io.BytesIO:
        seen.append(request.get_header("Accept"))
        return io.BytesIO(b"item\r\n")
    monkeypatch.setattr(urllib.request, "urlopen", answer)
    tool._sparql_csv("SELECT")
    assert seen == ["text/csv"]


@pytest.mark.parametrize(("word", "cjk"), [
    ("𠮷田", True),     # supplementary-plane Han (Extension B)
    ("〇", True),
    ("䷀", False),      # a Yijing hexagram, inside the old range
])
def test_is_cjk_covers_the_supplementary_han_planes(word: str, cjk: bool) -> None:
    assert tool.is_cjk(word) is cjk


def test_the_index_query_and_is_cjk_share_one_character_class() -> None:
    assert f"[{tool._CJK_CHARS}]" in tool.labels_query(["Q1"])


def test_boundaries_try_every_cut_and_match_the_given_name_whole() -> None:
    index = _index(("Q1", "family", "某国会"), ("Q2", "given", "議員"),
                   ("Q3", "given", "信議員"), ("Q4", "given", "某国"),
                   ("Q5", "given", "国会議員"))
    splits = index.boundaries("国会議員")
    # The only split is at the second cut, and 信議員 ends in the tail
    # without being it; 某国 is a GIVEN name ending in the head, which is
    # no family name; and a word equal to a whole given name is no split.
    assert [(s.family_tail, s.given, s.family_items, s.given_items)
            for s in splits] == [("国会", "議員", ["Q1"], ["Q2"])]


def test_a_failed_bearer_count_fails_the_row(
        monkeypatch: pytest.MonkeyPatch) -> None:
    _stub_sparql(monkeypatch, [OSError("down")])
    usage = tool.ends_with_usage("殿", _index(("Q1", "family", "向殿")), top=5)
    assert (usage.source, usage.status) == (tool.ENDS_WITH_SOURCE, "failed")
    assert (usage.given, usage.family) == (None, None)


def test_a_failed_boundary_count_keeps_the_rows_other_counts(
        monkeypatch: pytest.MonkeyPatch) -> None:
    index = _index(("Q1", "family", "阿部"), ("Q2", "given", "長"),
                   ("Q3", "family", "山部長"))
    _stub_sparql(monkeypatch, [[{"role": "family", "n": "7"}], [],
                               OSError("timed out")])
    usage = tool.ends_with_usage("部長", index, top=5)
    assert (usage.status, usage.family) == ("ok", 7)
    [split] = usage.splits
    assert split.people is None and "timed out" in split.error
    assert "family ending 部 + given 長: - people (query failed" in (
        tool.render("部長", [usage]))


def test_a_boundary_count_is_chunked_and_counts_a_person_once(
        monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(tool, "ITEM_CHUNK", 1)
    index = _index(("Q1", "family", "阿部"), ("Q2", "family", "岡部"),
                   ("Q3", "given", "長"))
    # The larger answer first: a count that kept only the last chunk's
    # people would read 1.
    queries = _stub_sparql(monkeypatch, [_people("Q9", "Q8"), _people("Q9")])
    usage = tool.ends_with_usage("部長", index, top=5)
    assert len(queries) == 2
    assert usage.splits[0].people == 2


def test_an_empty_boundary_answer_is_zero_people(
        monkeypatch: pytest.MonkeyPatch) -> None:
    _stub_sparql(monkeypatch, [[]])
    usage = tool.ends_with_usage(
        "部長", _index(("Q1", "family", "阿部"), ("Q3", "given", "長")), top=5)
    assert (usage.splits[0].people, usage.splits[0].example) == (0, "")


def test_the_ends_with_note_gives_the_index_size(
        monkeypatch: pytest.MonkeyPatch) -> None:
    _stub_sparql(monkeypatch, [])
    usage = tool.ends_with_usage("議員", _index(("Q1", "family", "向殿")), top=5)
    assert "index of 1 entries" in usage.note


def test_chunked_country_counts_are_summed(
        monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(tool, "ITEM_CHUNK", 1)
    index = _index(("Q1", "family", "向殿"), ("Q2", "family", "井殿"))
    _stub_sparql(monkeypatch, [
        [{"role": "family", "n": "3"}], [{"role": "family", "country": "Japan", "n": "3"}],
        [{"role": "family", "n": "4"}], [{"role": "family", "country": "Japan", "n": "4"}],
    ])
    usage = tool.ends_with_usage("殿", index, top=5)
    assert usage.family_countries == [("Japan", 7)]


def _http_error(code: int, retry_after: str = "") -> urllib.error.HTTPError:
    headers = {"Retry-After": retry_after} if retry_after else {}
    return urllib.error.HTTPError("u", code, "x", headers, io.BytesIO(b""))  # type: ignore[arg-type]


def test_sparql_raises_a_non_rate_limit_error_without_waiting(
        monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[int] = []
    waits: list[float] = []

    def answer(request: urllib.request.Request, timeout: float) -> io.BytesIO:
        calls.append(1)
        raise _http_error(500)
    monkeypatch.setattr(urllib.request, "urlopen", answer)
    monkeypatch.setattr(tool, "_sleep", waits.append)
    with pytest.raises(urllib.error.HTTPError) as caught:
        tool._sparql("SELECT")
    caught.value.close()  # 3.14 warns on an HTTPError left open
    assert (len(calls), waits) == (1, [])


def test_sparql_gives_up_after_its_retries_with_the_http_error(
        monkeypatch: pytest.MonkeyPatch) -> None:
    waits: list[float] = []

    def answer(request: urllib.request.Request, timeout: float) -> io.BytesIO:
        raise _http_error(429, "Fri, 17 Oct 2026 18:00:00 GMT")
    monkeypatch.setattr(urllib.request, "urlopen", answer)
    monkeypatch.setattr(tool, "_sleep", waits.append)
    with pytest.raises(urllib.error.HTTPError) as caught:
        tool._sparql("SELECT")
    caught.value.close()
    # A date-form Retry-After waits the default minute.
    assert waits == [60] * tool.SPARQL_RETRIES


@pytest.mark.parametrize(("argv", "refresh"), [
    (["--json", "殿"], False), (["--json", "--refresh-index", "殿"], True),
    (["--json", "--refresh-index", "knight"], True),
])
def test_main_passes_refresh_to_the_index(
        monkeypatch: pytest.MonkeyPatch, tmp_path: Path,
        argv: list[str], refresh: bool) -> None:
    monkeypatch.setenv("NAMEPARSER_TOOLS_CACHE", str(tmp_path))
    monkeypatch.setattr(tool, "load_census", lambda download: None)
    seen: list[bool] = []

    def load(download: bool, refresh: bool = False) -> _Index:
        seen.append(refresh)
        return _index(("Q1", "family", "x"))
    monkeypatch.setattr(tool, "load_index", load)
    monkeypatch.setattr(tool, "_sparql", lambda query: {"results": {"bindings": []}})
    tool.main(argv)
    assert seen == [refresh]


def test_main_reads_a_decomposed_word_as_its_composed_twin(
        monkeypatch: pytest.MonkeyPatch, tmp_path: Path,
        capsys: pytest.CaptureFixture[str]) -> None:
    # Wikidata labels are NFC; a decomposed hangul word is conjoining
    # jamo, which neither is_cjk nor any label would match.
    monkeypatch.setenv("NAMEPARSER_TOOLS_CACHE", str(tmp_path))
    monkeypatch.setattr(tool, "load_census", lambda download: None)
    monkeypatch.setattr(tool, "load_index", lambda download, refresh=False:
                        _index(("Q1", "given", "민준씨")))
    monkeypatch.setattr(tool, "_sparql", lambda query: {"results": {"bindings": []}})
    tool.main(["--json", unicodedata.normalize("NFD", "씨")])
    [rows] = json.loads(capsys.readouterr().out).values()
    assert rows[-1]["source"] == tool.ENDS_WITH_SOURCE


def test_main_exits_2_when_a_boundary_count_failed(
        monkeypatch: pytest.MonkeyPatch, tmp_path: Path,
        capsys: pytest.CaptureFixture[str]) -> None:
    monkeypatch.setenv("NAMEPARSER_TOOLS_CACHE", str(tmp_path))
    monkeypatch.setattr(tool, "load_census", lambda download: None)
    monkeypatch.setattr(tool, "load_index", lambda download, refresh=False:
                        _index(("Q1", "family", "阿部"), ("Q2", "given", "長")))
    _stub_sparql(monkeypatch, [[], [], OSError("timed out")])
    assert tool.main(["--json", "部長"]) == 2


def test_main_reports_an_unusable_cache_without_losing_the_other_sources(
        monkeypatch: pytest.MonkeyPatch, tmp_path: Path,
        capsys: pytest.CaptureFixture[str]) -> None:
    monkeypatch.setenv("NAMEPARSER_TOOLS_CACHE", str(tmp_path))
    monkeypatch.setattr(tool, "NAME_CLASSES", {"Q101352": "family"})
    with zipfile.ZipFile(tmp_path / tool.CENSUS_FILE, "w") as zf:
        zf.writestr(tool.CENSUS_MEMBER, _CENSUS)
    index_dir = tmp_path / tool.INDEX_DIR
    index_dir.mkdir()
    (index_dir / "version.json").write_text(str(tool.INDEX_VERSION))
    (index_dir / "Q101352-ids.json").write_text("{")
    _stub_sparql(monkeypatch, [[], []])
    assert tool.main(["--json", "殿"]) == 2
    rows = json.loads(capsys.readouterr().out)["殿"]
    assert rows[-1]["status"] == "failed" and "unusable" in rows[-1]["note"]


# -- second review of #712 ---------------------------------------------------

@pytest.mark.usefixtures("one_class")
@pytest.mark.parametrize("relisted", [
    ("Q1", "Q3"),          # the first item kept
    ("Q0", "Q2"),          # the last item kept
])
def test_a_batch_whose_items_changed_at_either_end_is_fetched_again(
        monkeypatch: pytest.MonkeyPatch, relisted: tuple[str, str]) -> None:
    _stub_sparql(monkeypatch, [*_listing("Q1", "Q2"), _labels(("Q1", "向殿"))])
    tool.load_index(download=True)
    (tool.cache_dir() / tool.INDEX_DIR / "Q101352-ids.json").unlink()
    queries = _stub_sparql(monkeypatch, [*_listing(*relisted), _labels()])
    tool.load_index(download=True)
    assert _values(queries[2]) == [f"wd:{q}" for q in relisted]


@pytest.mark.usefixtures("one_class")
def test_a_batch_whose_middle_item_changed_is_fetched_again(
        monkeypatch: pytest.MonkeyPatch) -> None:
    # Same first and last items, another in between: the batch's whole
    # membership is what its file is checked against.
    monkeypatch.setattr(tool, "INDEX_BATCH", 3)
    _stub_sparql(monkeypatch, [*_listing("Q1", "Q2", "Q4"),
                               _labels(("Q2", "向殿"))])
    tool.load_index(download=True)
    (tool.cache_dir() / tool.INDEX_DIR / "Q101352-ids.json").unlink()
    queries = _stub_sparql(monkeypatch, [*_listing("Q1", "Q3", "Q4"),
                                         _labels(("Q3", "井殿"))])
    index = tool.load_index(download=True)
    assert index is not None
    assert [e.label for e in index.entries] == ["井殿"]
    assert _values(queries[2]) == ["wd:Q1", "wd:Q3", "wd:Q4"]


@pytest.mark.usefixtures("one_class")
def test_a_batch_halved_under_a_new_listing_leaves_no_stale_whole(
        monkeypatch: pytest.MonkeyPatch) -> None:
    # Listing A fetched the batch whole; listing B overran it and cached
    # its halves. The whole batch's old file must not shadow the halves,
    # or the complete index reads as missing offline.
    _stub_sparql(monkeypatch, [*_listing("Q1", "Q2"), _labels(("Q1", "向殿"))])
    tool.load_index(download=True)
    (tool.cache_dir() / tool.INDEX_DIR / "Q101352-ids.json").unlink()
    _stub_sparql(monkeypatch, [*_listing("Q1", "Q3"), _overrun(),
                               _labels(("Q1", "向殿")), _labels(("Q3", "井殿"))])
    tool.load_index(download=True)
    _stub_sparql(monkeypatch, [])  # any query fails the test
    offline = tool.load_index(download=False)
    assert offline is not None
    assert sorted(e.label for e in offline.entries) == ["井殿", "向殿"]
    online = tool.load_index(download=True)
    assert online is not None and len(online.entries) == 2


@pytest.mark.usefixtures("one_class")
def test_an_index_built_before_versioning_is_rebuilt(
        monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture[str]) -> None:
    # The first index (2026-10-17) had no version file at all, and its
    # character class missed supplementary-plane Han.
    _stub_sparql(monkeypatch, [*_listing("Q1"), _labels(("Q1", "向殿"))])
    tool.load_index(download=True)
    (tool.cache_dir() / tool.INDEX_DIR / "version.json").unlink()
    _stub_sparql(monkeypatch, [])
    assert tool.load_index(download=False) is None
    capsys.readouterr()
    _stub_sparql(monkeypatch, [*_listing("Q1"), _labels(("Q1", "𠮷田"))])
    index = tool.load_index(download=True)
    assert index is not None and index.entries[0].label == "𠮷田"
    assert "older version" in capsys.readouterr().err


@pytest.mark.usefixtures("one_class")
def test_a_listing_without_an_item_column_is_an_error(
        monkeypatch: pytest.MonkeyPatch) -> None:
    _stub_sparql(monkeypatch, [[{"n": "1"}], [{"x": "y"}]])
    with pytest.raises(ValueError, match="not item"):
        tool.load_index(download=True)


@pytest.mark.parametrize(("word", "cjk"), [
    ("\U00031350", True),   # Extension H
    ("\U0002f800", True),   # the supplementary compatibility block
])
def test_is_cjk_covers_extension_h(word: str, cjk: bool) -> None:
    assert tool.is_cjk(word) is cjk


def _closable(code: int, body: bytes = b"") -> tuple[urllib.error.HTTPError, io.BytesIO]:
    fp = io.BytesIO(body)
    return urllib.error.HTTPError("u", code, "x", {}, fp), fp  # type: ignore[arg-type]


@pytest.mark.usefixtures("one_class")
@pytest.mark.parametrize(("code", "body"), [
    (504, b""), (500, b"java.util.concurrent.TimeoutException"), (400, b"syntax")])
def test_the_index_closes_each_http_error_it_reads(
        monkeypatch: pytest.MonkeyPatch, code: int, body: bytes) -> None:
    # Since 3.14 an HTTPError left open warns when collected.
    error, fp = _closable(code, body)
    _stub_sparql(monkeypatch, [*_listing("Q1", "Q2"), error, _labels(), _labels()])
    try:
        tool.load_index(download=True)
    except urllib.error.HTTPError:
        pass
    assert fp.closed


def test_a_failed_wikidata_row_closes_its_http_error(
        monkeypatch: pytest.MonkeyPatch) -> None:
    error, fp = _closable(400)
    _stub_sparql(monkeypatch, [error])
    assert tool.wikidata_usage("shehu", top=5).status == "failed"
    assert fp.closed


def test_a_failed_ends_with_row_and_pairing_close_their_http_errors(
        monkeypatch: pytest.MonkeyPatch) -> None:
    first, first_fp = _closable(400)
    _stub_sparql(monkeypatch, [first])
    tool.ends_with_usage("殿", _index(("Q1", "family", "向殿")), top=5)
    second, second_fp = _closable(400)
    _stub_sparql(monkeypatch, [second])
    tool.ends_with_usage(
        "部長", _index(("Q1", "family", "阿部"), ("Q3", "given", "長")), top=5)
    assert first_fp.closed and second_fp.closed


def test_main_reports_a_refresh_that_failed_for_a_latin_word(
        monkeypatch: pytest.MonkeyPatch, tmp_path: Path,
        capsys: pytest.CaptureFixture[str]) -> None:
    # A Latin word has no ends-with row to carry the failure, and the
    # refresh has already deleted the old index.
    monkeypatch.setenv("NAMEPARSER_TOOLS_CACHE", str(tmp_path))
    monkeypatch.setattr(tool, "load_census", lambda download: None)

    def broken(download: bool, refresh: bool = False) -> None:
        raise OSError("down")
    monkeypatch.setattr(tool, "load_index", broken)
    _stub_sparql(monkeypatch, [[], []])
    assert tool.main(["--refresh-index", "knight"]) == 2
    assert "CJK name index: OSError: down" in capsys.readouterr().err


# -- nam_dict given names ----------------------------------------------------
#
# A dictionary built here in the file's own layout: the 55-country legend,
# each label above a line holding only a bar in its column, then
# fixed-width lines. The real file is GFDL and is never in the tree.

_COUNTRIES = ([f"Country {i}" for i in range(52)]
              + ["Korea", "Vietnam", "other countries"])


def _legend_lines(columns: list[int]) -> list[str]:
    lines = []
    for country, column in zip(_COUNTRIES, columns):
        lines.append(f"#{country:>{column}} $")
        lines.append("#" + " " * (column - 1) + "|" + " " * (86 - column - 1) + "$")
    return lines


def _line(code: str, name: str, bands: dict[str, str], flag: str = " ") -> str:
    digits = "".join(bands.get(c, " ") for c in _COUNTRIES)
    return f"{code:<2} {name:<26}{flag}{digits} $"


def _namdict_text(*lines: str, columns: list[int] | None = None) -> str:
    header = ["# nam_dict.txt", "#"] + _legend_lines(
        columns or list(range(30, 85))) + ["#"]
    return "\r\n".join(header + list(lines)) + "\r\n"


_DICT = _namdict_text(
    _line("?", "In", {"Korea": "A"}),
    _line("M", "Dean", {"Country 0": "5", "Country 2": "5"}),
    _line("?", "Dean", {"Country 2": "6", "Country 30": "1"}),
    # Joined, De+An spells Dean too; its lower Country 2 band comes after
    # Dean's 6, so a last-wins merge would show.
    _line("?", "De+An", {"Country 2": "2", "Country 50": "2"}),
    _line("?", "Jun+Wei", {"Country 50": "3"}),
    _line("M", "İlker", {"Country 47": "5"}),
    _line("F", "Işıl", {"Country 47": "6"}),
    _line("M", "Isa", {"Country 46": "4"}),
    _line("M", "İsa", {"Country 47": "7"}),
    _line("M", "Kasim", {"Country 46": "3"}),
    _line("M", "Kasım", {"Country 47": "5"}),
    # Tied bands, the later line naming the earlier legend country.
    _line("M", "Ali", {"Country 5": "3"}),
    _line("?", "Ali", {"Country 1": "3"}),
    # An expanded-umlaut copy: skipped, so its band never shows.
    _line("F", "Käte", {"Country 11": "4"}, flag="-"),
    _line("F", "Käte", {"Country 11": "D"}, flag="+"),
    _line("=", "Al Albert", {"Country 0": "1"}),
)


_DICT_SHA256 = hashlib.sha256(_DICT.encode()).hexdigest()


def test_read_namdict_reads_the_countries_from_the_legend() -> None:
    table = tool.read_namdict(_DICT)
    assert table.countries == _COUNTRIES
    assert table.names["in"] == [("In", {"Korea": 10})]


def test_read_namdict_keeps_every_listing_line_of_a_name() -> None:
    table = tool.read_namdict(_DICT)
    assert table.names["dean"] == [
        ("Dean", {"Country 0": 5, "Country 2": 5}),
        ("Dean", {"Country 2": 6, "Country 30": 1}),
        ("De+An", {"Country 2": 2, "Country 50": 2}),
    ]


def test_read_namdict_skips_the_expanded_umlaut_copies() -> None:
    assert tool.read_namdict(_DICT).names["käte"] == [("Käte", {"Country 11": 4})]


def test_read_namdict_reads_equivalences_as_short_forms_not_names() -> None:
    table = tool.read_namdict(_DICT)
    assert "al" not in table.names and "al albert" not in table.names
    assert table.short_for["al"] == ["Albert"]


@pytest.mark.parametrize(("name", "forms"), [
    ("Dean", ["Dean"]),
    ("Jun+Wei", ["Jun-Wei", "Jun Wei", "Junwei"]),
    ("Maria+da+Glória", [
        "Maria-da-Glória", "Maria-da Glória", "Maria-daglória",
        "Maria da-Glória", "Maria da Glória", "Maria daglória",
        "Mariada-Glória", "Mariada Glória", "Mariadaglória"]),
])
def test_expand_plus_reads_a_plus_as_hyphen_space_or_nothing(
        name: str, forms: list[str]) -> None:
    assert tool.expand_plus(name) == forms


def test_read_namdict_files_every_expansion_of_a_plus_name() -> None:
    table = tool.read_namdict(_DICT)
    # The listed spelling too, so a name copied from the file finds itself.
    for form in ("jun+wei", "jun-wei", "jun wei", "junwei"):
        assert table.names[form] == [("Jun+Wei", {"Country 50": 3})]


@pytest.mark.parametrize("columns", [
    list(range(31, 86)),           # shifted a column
    list(range(30, 84)) + [86],    # a gap before the last country
])
def test_read_namdict_refuses_a_legend_it_was_not_written_for(
        columns: list[int]) -> None:
    with pytest.raises(ValueError, match="legend marks columns"):
        tool.read_namdict(_namdict_text(_line("?", "In", {}), columns=columns))


@pytest.mark.parametrize("line", [
    "?  In A",                                          # short
    " " + _line("?", "In", {"Korea": "A"})[:-3] + " $",  # shifted, same length
    _line("?", "In", {"Korea": "A"})[:28] + "x" + _line("?", "In", {})[29:],
    _line("?", "In", {"Korea": "A"})[:-2] + "  ",        # no " $" end
])
def test_read_namdict_refuses_a_line_that_is_not_fixed_width(line: str) -> None:
    # A shifted line keeps its length: read as written, In's Korea band
    # would land under Vietnam, filed under " in".
    with pytest.raises(ValueError, match="line .* is not fixed-width"):
        tool.read_namdict(_namdict_text(line))


@pytest.mark.parametrize("pair", ["Al", "Al Albert Bert"])
def test_read_namdict_names_the_line_of_a_malformed_equivalence(pair: str) -> None:
    with pytest.raises(ValueError, match=r"line \d+ is not '=  short long'"):
        tool.read_namdict(_namdict_text(_line("=", pair, {})))


def test_namdict_usage_reports_bands_highest_first_never_as_a_count() -> None:
    usage = tool.namdict_usage("Dean", tool.read_namdict(_DICT), top=5)
    assert usage.given is None and usage.lower_bound
    # Peak per country across the M and ? lines, then legend order.
    assert usage.given_bands == [("Country 2", 6), ("Country 0", 5),
                                 ("Country 50", 2), ("Country 30", 1)]
    assert "banded in 4 countries" in usage.note
    assert "listed as Dean, De+An" in usage.note


def test_namdict_usage_breaks_a_tie_in_legend_order() -> None:
    usage = tool.namdict_usage("Ali", tool.read_namdict(_DICT), top=5)
    assert usage.given_bands == [("Country 1", 3), ("Country 5", 3)]


@pytest.mark.parametrize(("word", "bands"), [
    # casefold() turns İ into i + U+0307, so a plain fold missed every
    # name listed only under İ (24 in the real file, measured 2026-10-19).
    ("Ilker", [("Country 47", 5)]),
    ("ilker", [("Country 47", 5)]),
    ("ILKER", [("Country 47", 5)]),
    ("İlker", [("Country 47", 5)]),   # as listed: the plain fold had it
    # Turkish lowers I to dotless ı, so a Turkish speaker's lowercase and
    # capitals of Işıl miss under the default fold, which lowers I to i.
    ("ışıl", [("Country 47", 6)]),
    ("IŞIL", [("Country 47", 6)]),
    ("Işıl", [("Country 47", 6)]),    # as listed: the plain fold had it
    ("işıl", [("Country 47", 6)]),    # the default fold of Işıl: had it too
    # Isa and İsa are one name with two capitals, so both answer both.
    ("Isa", [("Country 47", 7), ("Country 46", 4)]),
    ("İsa", [("Country 47", 7), ("Country 46", 4)]),
    # ...but dotless ı is a letter, not a case: Kasim is not Kasım,
    # though KASIM, written in capitals, may be either.
    ("Kasim", [("Country 46", 3)]),
    ("Kasım", [("Country 47", 5)]),
    ("KASIM", [("Country 47", 5), ("Country 46", 3)]),
])
def test_namdict_usage_matches_turkish_capitals_in_both_folds(
        word: str, bands: list[tuple[str, int]]) -> None:
    usage = tool.namdict_usage(word, tool.read_namdict(_DICT), top=5)
    assert usage.given_bands == bands


@pytest.mark.parametrize("word", ["Isil", "isil", "ISIL", "Işil"])
def test_namdict_usage_does_not_fold_a_dotless_i_into_a_dotted_one(
        word: str) -> None:
    # The Turkish fold must not turn ı into i: Işıl is not Isil, as Käte
    # is not Kaete.
    usage = tool.namdict_usage(word, tool.read_namdict(_DICT), top=5)
    assert usage.given_bands == []


def test_namdict_usage_matches_ignoring_case_and_reads_a_plus_name() -> None:
    table = tool.read_namdict(_DICT)
    assert tool.namdict_usage("IN", table, top=5).given_bands == [("Korea", 10)]
    for word in ("Jun Wei", "Jun+Wei"):
        usage = tool.namdict_usage(word, table, top=5)
        assert usage.given_bands == [("Country 50", 3)]
        assert "listed as Jun+Wei" in usage.note


def test_namdict_usage_shows_the_top_countries_and_says_so() -> None:
    usage = tool.namdict_usage("Dean", tool.read_namdict(_DICT), top=1)
    assert usage.given_bands == [("Country 2", 6)]
    assert "banded in 4 countries, the top 1 shown" in usage.note


def test_namdict_usage_reports_a_missing_name_as_no_answer() -> None:
    # The dictionary is a selection (Shehu has no entry): a miss must not
    # read as a zero anywhere, in the row or in the JSON.
    usage = tool.namdict_usage("Shehu", tool.read_namdict(_DICT), top=5)
    assert (usage.status, usage.given, usage.given_bands) == ("ok", None, [])
    assert "proves nothing" in usage.note
    assert tool.render("Shehu", [usage]).splitlines()[2].split()[-3:] == ["-", "-", "-"]


def test_namdict_usage_names_a_short_form() -> None:
    usage = tool.namdict_usage("Al", tool.read_namdict(_DICT), top=5)
    assert usage.given is None
    assert "short form of Albert" in usage.note


def test_namdict_usage_calls_a_non_latin_word_unrepresentable() -> None:
    table = tool.read_namdict(_DICT)
    for word in ("关", "Иван"):
        usage = tool.namdict_usage(word, table, top=5)
        assert (usage.status, usage.given) == ("unrepresentable", None)


def test_namdict_usage_reports_a_missing_download_without_an_answer() -> None:
    usage = tool.namdict_usage("Dean", None, top=5)
    assert (usage.status, usage.given) == ("not downloaded", None)


def test_render_shows_the_peak_band_and_the_bands_by_country() -> None:
    usage = tool.namdict_usage("Dean", tool.read_namdict(_DICT), top=5)
    text = tool.render("Dean", [usage])
    assert text.splitlines()[2].split()[-4:] == ["band", "6", "-", "-"]
    assert ("given band by country: Country 2 6, Country 0 5, Country 50 2, "
            "Country 30 1") in text


def test_render_writes_a_band_in_hex_as_the_note_does() -> None:
    usage = tool.namdict_usage("In", tool.read_namdict(_DICT), top=5)
    text = tool.render("In", [usage])
    assert text.splitlines()[2].split()[-4:] == ["band", "A", "-", "-"]
    assert "given band by country: Korea A" in text


def _sdist(member_text: bytes, member: str = tool.NAMDICT_MEMBER) -> bytes:
    import tarfile
    buffer = io.BytesIO()
    with tarfile.open(fileobj=buffer, mode="w:gz") as tf:
        for name, data in ((member, member_text),
                           ("gender-guesser-0.4.0/setup.py", b"print('no')")):
            info = tarfile.TarInfo(name)
            info.size = len(data)
            tf.addfile(info, io.BytesIO(data))
    return buffer.getvalue()


def _serve(monkeypatch: pytest.MonkeyPatch, data: bytes,
           url: str | None = None) -> None:
    def answer(request: urllib.request.Request, timeout: float) -> io.BytesIO:
        assert request.full_url == (url or tool.NAMDICT_URL)
        return io.BytesIO(data)
    monkeypatch.setattr(urllib.request, "urlopen", answer)


def test_load_namdict_caches_only_the_dictionary_from_a_pinned_sdist(
        monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setenv("NAMEPARSER_TOOLS_CACHE", str(tmp_path))
    sdist = _sdist(_DICT.encode())
    monkeypatch.setattr(tool, "NAMDICT_SHA256", hashlib.sha256(sdist).hexdigest())
    monkeypatch.setattr(tool, "NAMDICT_FILE_SHA256", _DICT_SHA256)
    _serve(monkeypatch, sdist)
    table = _LOAD_NAMDICT(download=True)
    assert table is not None and table.names["in"] == [("In", {"Korea": 10})]
    assert sorted(p.name for p in tmp_path.iterdir()) == [tool.NAMDICT_FILE]


def test_load_namdict_refuses_an_sdist_that_is_not_the_pinned_one(
        monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setenv("NAMEPARSER_TOOLS_CACHE", str(tmp_path))
    _serve(monkeypatch, _sdist(_DICT.encode()))
    with pytest.raises(ValueError, match="not the pinned"):
        _LOAD_NAMDICT(download=True)
    assert list(tmp_path.iterdir()) == []  # nothing cached


def test_load_namdict_does_not_download_when_told_not_to(
        monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setenv("NAMEPARSER_TOOLS_CACHE", str(tmp_path))
    assert _LOAD_NAMDICT(download=False) is None


def test_main_reads_a_cached_dictionary_offline(
        monkeypatch: pytest.MonkeyPatch, tmp_path: Path,
        capsys: pytest.CaptureFixture[str]) -> None:
    monkeypatch.setenv("NAMEPARSER_TOOLS_CACHE", str(tmp_path))
    monkeypatch.setattr(tool, "load_namdict", _LOAD_NAMDICT)
    monkeypatch.setattr(tool, "NAMDICT_FILE_SHA256", _DICT_SHA256)
    (tmp_path / tool.NAMDICT_FILE).write_text(_DICT, encoding="utf-8")
    assert tool.main(["--no-wikidata", "--json", "In", "Shehu"]) == 0
    report = json.loads(capsys.readouterr().out)
    assert report["In"][2]["given_bands"] == [["Korea", 10]]
    assert report["Shehu"][2]["given"] is None  # null, not 0


def test_main_exits_2_on_an_unusable_cached_dictionary(
        monkeypatch: pytest.MonkeyPatch, tmp_path: Path,
        capsys: pytest.CaptureFixture[str]) -> None:
    monkeypatch.setenv("NAMEPARSER_TOOLS_CACHE", str(tmp_path))
    monkeypatch.setattr(tool, "load_namdict", _LOAD_NAMDICT)
    (tmp_path / tool.NAMDICT_FILE).write_text("<html>error</html>")
    assert tool.main(["--no-wikidata", "--json", "In"]) == 2
    row = json.loads(capsys.readouterr().out)["In"][2]
    assert (row["status"], row["given"]) == ("failed", None)
    assert "delete it and run again" in row["note"]



@pytest.mark.parametrize(("sdist", "why"), [
    (lambda: _sdist(_DICT.encode(), member="elsewhere/nam_dict.txt"), "not found"),
    (lambda: b"not a gzip at all", ""),
    (lambda: _sdist(_DICT.encode())[:200], ""),  # truncated
])
def test_load_namdict_reports_an_archive_the_pin_does_not_describe(
        monkeypatch: pytest.MonkeyPatch, tmp_path: Path,
        sdist: Callable[[], bytes], why: str) -> None:
    # A hash bumped without the member path, or an archive of another
    # layout: tarfile raises KeyError, ReadError or EOFError, none of them
    # an OSError, which escaped _attempt and took every source down.
    monkeypatch.setenv("NAMEPARSER_TOOLS_CACHE", str(tmp_path))
    data = sdist()
    monkeypatch.setattr(tool, "NAMDICT_SHA256", hashlib.sha256(data).hexdigest())
    _serve(monkeypatch, data)
    with pytest.raises(ValueError, match=f"cannot read .*{why}"):
        _LOAD_NAMDICT(download=True)
    assert list(tmp_path.iterdir()) == []


def _legend_only() -> str:
    return _DICT.split("\r\n?  In")[0] + "\r\n"


@pytest.mark.parametrize("cut", [
    _legend_only,                                 # every name gone
    lambda: _DICT[:_DICT.rindex("\r\n", 0, -2) + 2],  # the last line gone
    lambda: _DICT[:-20],                          # cut inside a line
])
def test_load_namdict_refuses_a_cache_file_cut_short(
        monkeypatch: pytest.MonkeyPatch, tmp_path: Path,
        cut: Callable[[], str]) -> None:
    # Cut at a line boundary, the file still parses, and every name it
    # lost would read "not listed" -- the SSA zip's false zero again. A
    # floor on the names read refused the first and not the second.
    monkeypatch.setenv("NAMEPARSER_TOOLS_CACHE", str(tmp_path))
    monkeypatch.setattr(tool, "NAMDICT_FILE_SHA256", _DICT_SHA256)
    (tmp_path / tool.NAMDICT_FILE).write_bytes(cut().encode())
    with pytest.raises(ValueError, match="unusable"):
        _LOAD_NAMDICT(download=False)


def test_load_namdict_accepts_the_pinned_file(
        monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setenv("NAMEPARSER_TOOLS_CACHE", str(tmp_path))
    monkeypatch.setattr(tool, "NAMDICT_FILE_SHA256", _DICT_SHA256)
    (tmp_path / tool.NAMDICT_FILE).write_bytes(_DICT.encode())
    table = _LOAD_NAMDICT(download=False)
    assert table is not None and table.lookup("In") == [("In", {"Korea": 10})]


def test_load_namdict_does_not_cache_a_member_the_pin_does_not_describe(
        monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    # The sdist matches its pin but the member does not match its own:
    # caching it would leave a file every later load refuses.
    monkeypatch.setenv("NAMEPARSER_TOOLS_CACHE", str(tmp_path))
    sdist = _sdist(_DICT.encode())
    monkeypatch.setattr(tool, "NAMDICT_SHA256", hashlib.sha256(sdist).hexdigest())
    _serve(monkeypatch, sdist)
    with pytest.raises(ValueError, match="not the pinned"):
        _LOAD_NAMDICT(download=True)
    assert list(tmp_path.iterdir()) == []


def test_main_does_not_download_the_dictionary_under_no_wikidata(
        monkeypatch: pytest.MonkeyPatch, tmp_path: Path,
        capsys: pytest.CaptureFixture[str]) -> None:
    # With the flag ignored, the download would reach the network guard,
    # whose AssertionError _attempt does not catch.
    monkeypatch.setenv("NAMEPARSER_TOOLS_CACHE", str(tmp_path))
    monkeypatch.setattr(tool, "load_namdict", _LOAD_NAMDICT)
    assert tool.main(["--no-wikidata", "--json", "In"]) == 0
    row = json.loads(capsys.readouterr().out)["In"][2]
    assert (row["status"], row["given"]) == ("not downloaded", None)


def test_main_downloads_the_dictionary_when_online(
        monkeypatch: pytest.MonkeyPatch, tmp_path: Path,
        capsys: pytest.CaptureFixture[str]) -> None:
    monkeypatch.setenv("NAMEPARSER_TOOLS_CACHE", str(tmp_path))
    monkeypatch.setattr(tool, "load_namdict", _LOAD_NAMDICT)
    monkeypatch.setattr(tool, "load_census", lambda download: None)
    monkeypatch.setattr(tool, "NAMDICT_FILE_SHA256", _DICT_SHA256)
    sdist = _sdist(_DICT.encode())
    monkeypatch.setattr(tool, "NAMDICT_SHA256", hashlib.sha256(sdist).hexdigest())
    _serve(monkeypatch, sdist)
    _stub_sparql(monkeypatch, [[], []])
    assert tool.main(["--json", "In"]) == 0
    row = json.loads(capsys.readouterr().out)["In"][2]
    assert row["given_bands"] == [["Korea", 10]]


def test_main_refuses_fewer_than_one_country(
        capsys: pytest.CaptureFixture[str]) -> None:
    # --countries 0 emptied the band list, and a listed name's given cell
    # then showed the "-" of a name that is not listed.
    with pytest.raises(SystemExit):
        tool.main(["--countries", "0", "In"])
    assert "must be 1 or more" in capsys.readouterr().err


# -- NPPES credentials ------------------------------------------------------

def _providers(*fields: str, organizations: int = 0) -> list[dict[str, str]]:
    rows = [{"entity": "Individual", "pcredential": f} for f in fields]
    return rows + [{"entity": "Organization", "pcredential": "MD"}] * organizations


def test_tally_counts_a_provider_once_per_credential_and_keeps_spellings() -> None:
    tally = tool.tally_credentials(iter(_providers("MD, M.D.", "M.D", "")))
    assert (tally.people, tally.credentialed) == (3, 2)
    providers, spellings = tally.tokens["MD"]
    assert providers == 2
    assert dict(spellings) == {"MD": 1, "M.D.": 1, "M.D": 1}


def test_tally_reads_only_individual_providers() -> None:
    tally = tool.tally_credentials(iter(_providers("RN", organizations=3)))
    assert tally.people == 1 and tally.tokens["RN"][0] == 1
    assert "MD" not in tally.tokens


def test_tally_joins_one_credential_written_in_pieces() -> None:
    # PHARMD alone far outnumbers its rarest piece, so the pieces are
    # one credential; split, 'PHARM D' scored a D the field never meant.
    fields = ["PHARMD"] * 100 + ["PHARM"] * 3 + ["PHARM D"]
    tally = tool.tally_credentials(iter(_providers(*fields)))
    assert tally.tokens["PHARMD"][0] == 101
    assert ("PHARM D", 1) in tally.tokens["PHARMD"][1]
    assert "D" not in tally.tokens and tally.tokens["PHARM"][0] == 3


def test_tally_joins_pieces_onto_a_hyphenated_or_slashed_spelling() -> None:
    fields = ["PA-C"] * 100 + ["OTR/L"] * 100 + ["PA"] * 60 + [
        "PA C", "OTR L"]
    tally = tool.tally_credentials(iter(_providers(*fields)))
    assert tally.tokens["PA-C"][0] == 101 and tally.tokens["OTR/L"][0] == 101
    assert tally.tokens["PA"][0] == 60


def test_tally_splits_credentials_written_side_by_side() -> None:
    # Each piece is written alone more often than the two joined.
    fields = ["MD"] * 100 + ["PHD"] * 80 + ["MD/PHD"] * 5 + [
        "MD PHD"]
    tally = tool.tally_credentials(iter(_providers(*fields)))
    assert (tally.tokens["MD"][0], tally.tokens["PHD"][0]) == (101, 81)
    assert tally.tokens["MD/PHD"][0] == 5


def test_tally_keeps_a_job_title_whole() -> None:
    # PRACTITIONER is rarely written alone (19 times on the real file);
    # splitting the title would have counted NURSE for each of the 5,803
    # providers who write NURSE PRACTITIONER.
    fields = ["NURSE"] * 60 + ["NURSE PRACTITIONER"] * 2
    tally = tool.tally_credentials(iter(_providers(*fields)))
    assert tally.tokens["NURSE PRACTITIONER"][0] == 2
    assert tally.tokens["NURSE"][0] == 60
    assert "PRACTITIONER" not in tally.tokens


def test_tally_splits_after_a_join_inside_one_segment() -> None:
    fields = (["MS"] * 100 + ["CCC-SLP"] * 100 + ["CCC"] * 2
              + ["SLP"] * 60 + ["MS CCC SLP"])
    tally = tool.tally_credentials(iter(_providers(*fields)))
    assert tally.tokens["MS"][0] == 101 and tally.tokens["CCC-SLP"][0] == 101


def test_tally_drops_a_piece_that_is_only_periods() -> None:
    fields = ["MD"] * 100 + ["M"] * 2 + ["D"] * 2 + ["M . D."]
    tally = tool.tally_credentials(iter(_providers(*fields)))
    assert tally.tokens["MD"][0] == 101


class _Tally(Protocol):
    # tools/ is loaded by path, so mypy cannot see CredentialTally itself.
    people: int
    credentialed: int
    tokens: dict[str, tuple[int, list[tuple[str, int]]]]
    joined: dict[str, str]


def _tally(joined: dict[str, str] | None = None, /, **tokens: int) -> _Tally:
    """A tally of these provider counts. Unless `joined` is given, each
    unspaced key's letters are filed under the commonest key holding them,
    as tally_credentials files them when providers and whole segments
    agree."""
    credentialed = sum(tokens.values()) or 1
    if joined is None:
        joined = {}
        for k, _ in sorted(tokens.items(), key=lambda kn: -kn[1]):
            if " " not in k:
                joined.setdefault(tool._squash(k), k)
    return tool.CredentialTally(
        people=max(1000, credentialed), credentialed=credentialed,
        tokens={k: (n, [(k, n)]) for k, n in tokens.items()}, joined=joined)


@pytest.mark.parametrize("word", ["m.d.", "MD", "Md", "M. D."])
def test_credential_usage_matches_as_the_parser_matches_an_acronym(word: str) -> None:
    usage = tool.credential_usage(word, _tally(MD=40, RN=60))
    assert (usage.status, usage.credential) == ("ok", 40)


def test_credential_usage_finds_a_credential_the_tally_joined() -> None:
    usage = tool.credential_usage("Ph. D.", _tally(PHD=7))
    assert usage.credential == 7 and "looked up as PHD" in usage.note


def test_credential_usage_files_a_spaced_word_as_the_tally_filed_it() -> None:
    # The tally files 'PA C' under the commonest key sharing its letters;
    # the lookup first squashed it to PAC and read 5,910 where the
    # credential's providers number 122,676 (review of the first version).
    tally = _tally(**{"PA-C": 120, "PAC": 6})
    usage = tool.credential_usage("PA C", tally)
    assert usage.credential == 120 and "looked up as PA-C" in usage.note


def test_credential_usage_reads_the_tallys_choice_not_the_provider_order() -> None:
    # The lookup used to re-derive the choice by provider count, and
    # _resolve made it by whole segments: CPRI's one provider writes it
    # twice, so _resolve filed 'CPR I' under CPRI while the lookup, by
    # providers then by key, found CPR-I (measured 2026-10-21).
    tally = _tally({"CPRI": "CPRI"}, **{"CPR-I": 1, "CPRI": 1})
    usage = tool.credential_usage("CPR I", tally)
    assert "looked up as CPRI" in usage.note
    assert "also written CPR-I 1" in usage.note


def test_credential_usage_names_the_other_spellings_of_its_letters() -> None:
    tally = _tally(**{"PA-C": 120, "PAC": 6})
    assert "also written PA-C 120" in tool.credential_usage("PAC", tally).note
    missing = tool.credential_usage("OTR-L", _tally(**{"OTR/L": 60}))
    assert missing.credential == 0 and "also written OTR/L 60" in missing.note


def test_credential_usage_takes_a_spaced_key_the_tally_holds_whole() -> None:
    tally = _tally(**{"NURSE PRACTITIONER": 9, "NURSEPRACTITIONER": 40})
    usage = tool.credential_usage("Nurse Practitioner", tally)
    assert usage.credential == 9
    assert "also written NURSEPRACTITIONER 40" in usage.note


def test_credential_usage_gives_a_word_without_letters_no_siblings() -> None:
    usage = tool.credential_usage("- -", _tally(**{"-": 5, "MD": 1}))
    assert usage.credential == 0 and "also written" not in usage.note


def test_credential_usage_reports_a_missing_word_as_zero_with_the_scope() -> None:
    # The field is a census, so 0 is an answer -- but for US healthcare
    # alone, which the note must carry wherever the zero goes.
    usage = tool.credential_usage("CPA", _tally(MD=1))
    assert (usage.status, usage.credential) == ("ok", 0)
    assert "US healthcare only" in usage.note


def test_credential_usage_reports_a_missing_download_without_a_count() -> None:
    usage = tool.credential_usage("MD", None)
    assert (usage.status, usage.credential) == ("not downloaded", None)
    assert "--fetch-nppes" in usage.note


def test_render_shows_the_credential_column() -> None:
    text = tool.render("MA", [tool.credential_usage("MA", _tally(MA=1234))])
    assert text.splitlines()[1].split()[-1] == "credential"
    assert text.splitlines()[2].split()[-3:] == ["-", "-", "1,234"]


def test_share_never_prints_a_zero_for_a_credential_someone_writes() -> None:
    assert tool._share(5 / 4_824_544) == "<0.01%"
    assert tool._share(0.0234) == "2.34%"


def _nppes_zip(*fields: str, header: str = "npi,entity,pcredential",
               text: str | None = None, member: str | None = None) -> bytes:
    """A zip of individual providers with these credential fields, or of
    `text` as written, under `member` (the pinned member by default)."""
    if text is None:
        lines = [header] + [f'{i},Individual,"{f}"' for i, f in enumerate(fields)]
        text = "\n".join(lines) + "\n"
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as zf:
        zf.writestr(member or tool.NPPES_MEMBER, text)
    return buffer.getvalue()


def _pin_nppes(monkeypatch: pytest.MonkeyPatch, tmp_path: Path,
               data: bytes, cached: bool = False) -> None:
    """Point the cache at tmp_path and the pin at `data`, and with `cached`
    put `data` there as the downloaded zip."""
    monkeypatch.setenv("NAMEPARSER_TOOLS_CACHE", str(tmp_path))
    monkeypatch.setattr(tool, "NPPES_SHA256", hashlib.sha256(data).hexdigest())
    if cached:
        (tmp_path / tool.NPPES_FILE).write_bytes(data)


def test_load_nppes_downloads_the_pinned_zip_and_caches_its_tally(
        monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    data = _nppes_zip("MD", "RN, MD")
    _pin_nppes(monkeypatch, tmp_path, data)
    _serve(monkeypatch, data, tool.NPPES_URL)
    tally = _LOAD_NPPES(download=True)
    assert tally is not None and tally.tokens["MD"][0] == 2
    assert sorted(p.name for p in tmp_path.iterdir()) == [
        tool.NPPES_TALLY, tool.NPPES_FILE]
    # The second load reads the tally and never opens the zip.
    (tmp_path / tool.NPPES_FILE).unlink()
    again = _LOAD_NPPES(download=False)
    assert again is not None and again.tokens == tally.tokens
    assert again.joined == tally.joined and again.joined


def test_load_nppes_refuses_a_zip_that_is_not_the_pinned_one(
        monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setenv("NAMEPARSER_TOOLS_CACHE", str(tmp_path))
    _serve(monkeypatch, _nppes_zip("MD"), tool.NPPES_URL)
    with pytest.raises(ValueError, match="not the pinned"):
        _LOAD_NPPES(download=True)
    assert list(tmp_path.iterdir()) == []  # nothing cached, no .part left


def test_load_nppes_refuses_a_pinned_zip_without_the_member(
        monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    data = _nppes_zip(text="entity,pcredential\n", member="elsewhere.csv")
    _pin_nppes(monkeypatch, tmp_path, data)
    _serve(monkeypatch, data, tool.NPPES_URL)
    with pytest.raises(ValueError, match="cannot read"):
        _LOAD_NPPES(download=True)
    assert list(tmp_path.iterdir()) == []


def test_load_nppes_does_not_download_when_told_not_to(
        monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setenv("NAMEPARSER_TOOLS_CACHE", str(tmp_path))
    assert _LOAD_NPPES(download=False) is None


def test_load_nppes_refuses_a_cached_zip_that_does_not_match_its_pin(
        monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    # A whole, readable zip of another month (or one missing rows) opens
    # and tallies without complaint; only the hash says it is not the
    # file the counts claim to be. A truncated zip did not test this --
    # it fails to open whether the pin is checked or not.
    _pin_nppes(monkeypatch, tmp_path, _nppes_zip("MD", "RN"))
    (tmp_path / tool.NPPES_FILE).write_bytes(_nppes_zip("MD"))
    with pytest.raises(ValueError, match="not the pinned.*--fetch-nppes"):
        _LOAD_NPPES(download=False)
    assert not (tmp_path / tool.NPPES_TALLY).exists()


def test_load_nppes_names_a_member_without_the_credential_column(
        monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    data = _nppes_zip("MD", header="npi,entity,credential")
    _pin_nppes(monkeypatch, tmp_path, data, cached=True)
    with pytest.raises(ValueError, match="pcredential"):
        _LOAD_NPPES(download=False)


@pytest.mark.parametrize("stale", [
    {"version": 0}, {"source_sha256": "0" * 64},
    {"rules": {"min_alone": 1, "spellings": tool.NPPES_SPELLINGS}}])
def test_load_nppes_rebuilds_a_tally_from_another_version_or_zip(
        monkeypatch: pytest.MonkeyPatch, tmp_path: Path,
        stale: dict[str, object]) -> None:
    data = _nppes_zip("MD", "MD")
    _pin_nppes(monkeypatch, tmp_path, data, cached=True)
    old = tool._tally_json(_tally(RN=9)) | stale
    (tmp_path / tool.NPPES_TALLY).write_text(json.dumps(old))
    tally = _LOAD_NPPES(download=False)
    assert tally is not None and dict(
        (k, n) for k, (n, _) in tally.tokens.items()) == {"MD": 2}


def test_load_nppes_rebuilds_a_tally_written_before_the_rules_were_recorded(
        monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    data = _nppes_zip("MD")
    _pin_nppes(monkeypatch, tmp_path, data, cached=True)
    old = tool._tally_json(_tally(RN=9))
    del old["rules"]
    (tmp_path / tool.NPPES_TALLY).write_text(json.dumps(old))
    tally = _LOAD_NPPES(download=False)
    assert tally is not None and "RN" not in tally.tokens


def test_load_nppes_leaves_a_stale_tally_unread_when_nothing_can_rebuild_it(
        monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setenv("NAMEPARSER_TOOLS_CACHE", str(tmp_path))
    old = tool._tally_json(_tally(RN=9)) | {"version": 0}
    (tmp_path / tool.NPPES_TALLY).write_text(json.dumps(old))
    assert _LOAD_NPPES(download=False) is None


@pytest.mark.parametrize("cut", [
    lambda text: text[:len(text) // 2],              # cut mid-file
    lambda text: text.replace('"tokens": {', '"tokens": {}, "x": {', 1),
    lambda text: "[]",
])
def test_load_nppes_refuses_a_tally_that_is_not_whole(
        monkeypatch: pytest.MonkeyPatch, tmp_path: Path,
        cut: Callable[[str], str]) -> None:
    # A tally missing tokens would read every credential it lost as 0,
    # which this source reports as a real zero.
    monkeypatch.setenv("NAMEPARSER_TOOLS_CACHE", str(tmp_path))
    text = json.dumps(tool._tally_json(_tally(MD=3, RN=4)))
    (tmp_path / tool.NPPES_TALLY).write_text(cut(text))
    with pytest.raises(ValueError, match="unusable.*re-tally"):
        _LOAD_NPPES(download=False)


def _cache_tally(monkeypatch: pytest.MonkeyPatch, tmp_path: Path,
                 tally: _Tally) -> None:
    monkeypatch.setenv("NAMEPARSER_TOOLS_CACHE", str(tmp_path))
    monkeypatch.setattr(tool, "load_nppes", _LOAD_NPPES)
    (tmp_path / tool.NPPES_TALLY).write_text(json.dumps(tool._tally_json(tally)))


def test_main_reports_a_cached_tally_offline(
        monkeypatch: pytest.MonkeyPatch, tmp_path: Path,
        capsys: pytest.CaptureFixture[str]) -> None:
    _cache_tally(monkeypatch, tmp_path, _tally(MA=12, DO=30))
    assert tool.main(["--no-wikidata", "--json", "ma", "CPA"]) == 0
    report = json.loads(capsys.readouterr().out)
    assert [r["credential"] for r in report["ma"]] == [None, None, None, 12]
    assert report["CPA"][3]["credential"] == 0


def test_main_does_not_download_nppes_unless_asked(
        monkeypatch: pytest.MonkeyPatch, tmp_path: Path,
        capsys: pytest.CaptureFixture[str]) -> None:
    # Online and uncached: without --fetch-nppes the 673 MB download
    # must not start (the network guard would raise if it did).
    monkeypatch.setenv("NAMEPARSER_TOOLS_CACHE", str(tmp_path))
    monkeypatch.setattr(tool, "load_nppes", _LOAD_NPPES)
    monkeypatch.setattr(tool, "load_census", lambda download: None)
    _stub_sparql(monkeypatch, [[], []])
    assert tool.main(["--json", "MD"]) == 0
    row = json.loads(capsys.readouterr().out)["MD"][3]
    assert (row["status"], row["credential"]) == ("not downloaded", None)


def test_main_fetches_nppes_when_asked(
        monkeypatch: pytest.MonkeyPatch, tmp_path: Path,
        capsys: pytest.CaptureFixture[str]) -> None:
    data = _nppes_zip("MD", "MD, RN")
    _pin_nppes(monkeypatch, tmp_path, data)
    monkeypatch.setattr(tool, "load_nppes", _LOAD_NPPES)
    monkeypatch.setattr(tool, "load_census", lambda download: None)
    _serve(monkeypatch, data, tool.NPPES_URL)
    monkeypatch.setattr(tool, "wikidata_usage",
                        lambda word, top: tool.Usage("Wikidata people"))
    assert tool.main(["--fetch-nppes", "--json", "MD"]) == 0
    assert json.loads(capsys.readouterr().out)["MD"][3]["credential"] == 2


def test_main_exits_2_on_an_unusable_tally_without_losing_the_other_sources(
        monkeypatch: pytest.MonkeyPatch, tmp_path: Path,
        capsys: pytest.CaptureFixture[str]) -> None:
    monkeypatch.setenv("NAMEPARSER_TOOLS_CACHE", str(tmp_path))
    monkeypatch.setattr(tool, "load_nppes", _LOAD_NPPES)
    with zipfile.ZipFile(tmp_path / tool.CENSUS_FILE, "w") as zf:
        zf.writestr(tool.CENSUS_MEMBER, _CENSUS)
    (tmp_path / tool.NPPES_TALLY).write_text("{")
    assert tool.main(["--no-wikidata", "--json", "shehu"]) == 2
    census, _, _, nppes = json.loads(capsys.readouterr().out)["shehu"]
    assert census["family"] == 561
    assert (nppes["status"], nppes["credential"]) == ("failed", None)


def test_main_rank_lists_credentials_with_vocabulary_and_readings(
        monkeypatch: pytest.MonkeyPatch, tmp_path: Path,
        capsys: pytest.CaptureFixture[str]) -> None:
    # Q-R-S still reverses after a comma: joined single letters are no
    # caps shape (rules/S9), so the given-name readout stays exercised
    _cache_tally(monkeypatch, tmp_path, _tally(RA=50, **{"Q-R-S": 40}, ESQ=3))
    assert tool.main(["--no-wikidata", "--json", "--rank", "5"]) == 0
    rows = {r["credential"]: r for r in json.loads(capsys.readouterr().out)["rows"]}
    assert [r["rank"] for r in rows.values()] == [1, 2, 3]
    assert rows["RA"]["vocabulary"] == "acronym, title"
    assert (rows["RA"]["after_comma"], rows["RA"]["bare"]) == ("suffix", "suffix")
    assert rows["Q-R-S"]["vocabulary"] == "-"
    assert (rows["Q-R-S"]["after_comma"], rows["Q-R-S"]["bare"]) == ("given", "family")
    assert rows["ESQ"]["vocabulary"] == "suffix word"
    assert rows["RA"]["census"] == "not downloaded"


def test_main_rank_unlisted_keeps_each_credentials_overall_rank(
        monkeypatch: pytest.MonkeyPatch, tmp_path: Path,
        capsys: pytest.CaptureFixture[str]) -> None:
    _cache_tally(monkeypatch, tmp_path, _tally(MD=50, **{"QRS-C": 40}, MA=30))
    assert tool.main(["--no-wikidata", "--json", "--rank", "5", "--unlisted"]) == 0
    rows = json.loads(capsys.readouterr().out)["rows"]
    assert [(r["credential"], r["rank"]) for r in rows] == [("QRS-C", 2)]


def test_main_rank_exits_2_without_a_tally(
        monkeypatch: pytest.MonkeyPatch, tmp_path: Path,
        capsys: pytest.CaptureFixture[str]) -> None:
    monkeypatch.setenv("NAMEPARSER_TOOLS_CACHE", str(tmp_path))
    monkeypatch.setattr(tool, "load_nppes", _LOAD_NPPES)
    assert tool.main(["--no-wikidata", "--rank", "5"]) == 2
    assert "not cached" in capsys.readouterr().err


@pytest.mark.parametrize(("argv", "message"), [
    ([], "give words"),
    (["--rank", "5", "MD"], "takes no words"),
    (["--unlisted", "MD"], "goes with --rank"),
    (["--rank", "0"], "must be 1 or more"),
])
def test_main_refuses_a_rank_request_it_cannot_answer(
        argv: list[str], message: str,
        capsys: pytest.CaptureFixture[str]) -> None:
    with pytest.raises(SystemExit):
        tool.main(argv)
    assert message in capsys.readouterr().err


@pytest.mark.parametrize(("key", "expected"), [
    ("MA", "ambiguous acronym"),
    ("DO", "ambiguous acronym, particle"),
    ("ESQ", "suffix word"),
    ("JR", "suffix word"),
    ("PHD", "acronym"),
    ("QRS-C", "-"),
])
def test_vocabulary_reads_the_suffix_kind_as_the_parser_does(
        key: str, expected: str) -> None:
    assert tool._vocabulary(key) == expected


@pytest.mark.parametrize(("word", "found"), [
    ("Psicóloga", "PSICOLOGA"),   # the file has no accents at all
    ("Médico", "MEDICO"),
    ("Ørn", "ORN"),               # a letter NFKD leaves whole, transliterated
])
def test_credential_usage_folds_an_accented_word_as_the_file_spells_it(
        word: str, found: str) -> None:
    # Unfolded, the accented key could never match and read a false 0.
    usage = tool.credential_usage(word, _tally(**{found: 16}))
    assert (usage.status, usage.credential) == ("ok", 16)
    assert f"looked up as {found}" in usage.note


def test_credential_usage_reads_any_dash_as_a_hyphen() -> None:
    # The file writes only the ASCII hyphen; PA–C (an en dash) read 0
    # beside PA-C's 122,676 after the first accent fold.
    for dash in ("\u2013", "\u2010", "\u2014"):
        usage = tool.credential_usage(f"PA{dash}C", _tally(**{"PA-C": 120}))
        assert (usage.status, usage.credential) == ("ok", 120), dash


@pytest.mark.parametrize("word", ["博士", "врач", "M.D.\u2019", "", "  ", "\u0301",
                                  ".", ". ."])
def test_credential_usage_calls_a_non_latin_word_unrepresentable(word: str) -> None:
    # The file spells every credential in ASCII: no answer, never a zero.
    usage = tool.credential_usage(word, _tally(MD=1))
    assert (usage.status, usage.credential) == ("unrepresentable", None)
    assert tool.render(word, [usage]).splitlines()[2].split()[-1] == "-"


def test_load_nppes_refuses_a_source_with_no_individual_provider(
        monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    # An empty tally answers 0 for every word. Cached, it read "no
    # provider writes MD" with exit 0 for one run, and was refused only by
    # the next one's load.
    data = _nppes_zip(text="npi,entity,pcredential\n1,1,MD\n"
                           "2,Organization,MD\n")
    _pin_nppes(monkeypatch, tmp_path, data, cached=True)
    with pytest.raises(ValueError, match="no individual provider"):
        _LOAD_NPPES(download=False)
    assert not (tmp_path / tool.NPPES_TALLY).exists()


# A row replacing the tokens replaces `joined` with them: left naming a
# dropped token, it is refused by the joined check too, so with its own
# value check deleted it still passes (mechanisms.md#SHADOWED-NEGATIVE-ROWS).
@pytest.mark.parametrize("change", [
    {"credentialed": 0},              # a share divided by zero
    {"credentialed": 2000},           # more than the people read
    {"tokens": {"MD": [0, [["MD", 1]]]}, "joined": {"MD": "MD"}},
    {"tokens": {"MD": [5000, [["MD", 1]]]}, "joined": {"MD": "MD"}},
    {"tokens": {"MD": [5, []]}, "joined": {"MD": "MD"}},  # --rank printed spellings[0]
    {"tokens": {"MD": [5, [["MD", 0]]]}, "joined": {"MD": "MD"}},
    {"joined": {"PAC": "PA-C"}},      # names no token
    {"joined": {"RN": "MD"}},         # names a token of other letters
    {"joined": None},                 # a version-2 tally without the map
])
def test_load_nppes_refuses_a_tally_whose_values_cannot_be(
        monkeypatch: pytest.MonkeyPatch, tmp_path: Path,
        change: dict[str, object]) -> None:
    # Each parsed as a tally and crashed the run later, outside _attempt,
    # taking every other source's answer down with it.
    monkeypatch.setenv("NAMEPARSER_TOOLS_CACHE", str(tmp_path))
    data = tool._tally_json(_tally(MD=3, RN=4)) | change
    (tmp_path / tool.NPPES_TALLY).write_text(json.dumps(data))
    with pytest.raises(ValueError, match="unusable.*re-tally"):
        _LOAD_NPPES(download=False)


def test_main_rank_downloads_nppes_when_online(
        monkeypatch: pytest.MonkeyPatch, tmp_path: Path,
        capsys: pytest.CaptureFixture[str]) -> None:
    data = _nppes_zip("MD", "MD, RN")
    _pin_nppes(monkeypatch, tmp_path, data)
    monkeypatch.setattr(tool, "load_nppes", _LOAD_NPPES)
    monkeypatch.setattr(tool, "load_census", lambda download: None)
    _serve(monkeypatch, data, tool.NPPES_URL)
    assert tool.main(["--json", "--rank", "5"]) == 0
    rows = json.loads(capsys.readouterr().out)["rows"]
    assert [(r["credential"], r["providers"]) for r in rows] == [
        ("MD", 2), ("RN", 1)]


def test_main_rank_cuts_the_list_at_n(
        monkeypatch: pytest.MonkeyPatch, tmp_path: Path,
        capsys: pytest.CaptureFixture[str]) -> None:
    _cache_tally(monkeypatch, tmp_path, _tally(MD=50, RN=40, DO=30))
    assert tool.main(["--no-wikidata", "--json", "--rank", "1"]) == 0
    rows = json.loads(capsys.readouterr().out)["rows"]
    assert [r["credential"] for r in rows] == ["MD"]


def test_main_rank_reports_a_failed_name_source_and_exits_2(
        monkeypatch: pytest.MonkeyPatch, tmp_path: Path,
        capsys: pytest.CaptureFixture[str]) -> None:
    # The column must say failed, not the "not downloaded" a missing file
    # gets, and the run must not exit 0.
    _cache_tally(monkeypatch, tmp_path, _tally(MD=50))
    (tmp_path / tool.CENSUS_FILE).write_text("<html>error page</html>")
    assert tool.main(["--no-wikidata", "--json", "--rank", "3"]) == 2
    out, err = capsys.readouterr()
    assert json.loads(out)["rows"][0]["census"] == "failed"
    assert "US Census 2010 surnames:" in err and "delete it" in err


def test_main_rank_prints_a_table(
        monkeypatch: pytest.MonkeyPatch, tmp_path: Path,
        capsys: pytest.CaptureFixture[str]) -> None:
    # Every other rank test reads --json, so a bad format spec in the
    # table would have crashed the default output unseen.
    _cache_tally(monkeypatch, tmp_path, _tally(MD=5000, **{"Q-R-S": 40}))
    assert tool.main(["--no-wikidata", "--rank", "2"]) == 0
    lines = capsys.readouterr().out.splitlines()
    assert lines[0].startswith("5,040 of 5,040 individual providers")
    assert lines[1].split()[:3] == ["rank", "credential", "providers"]
    assert lines[3].split()[:4] == ["2", "Q-R-S", "40", "0.79%"]
    assert lines[3].split()[4:7] == ["-", "given", "family"]


def test_lands_says_split_when_no_field_holds_the_whole_credential() -> None:
    assert tool._lands("John Smith, PA C", "PA C") == "split"
    assert tool._lands("John Smith, MD", "MD") == "suffix"


def test_credential_usage_falls_back_to_a_sibling_for_letters_only_phrases_hold() -> None:
    # The tally stores a choice only for letters some UNSPACED key holds.
    # A job title spaced unlike every recorded spelling has none, and the
    # first version of the stored choice read 0 for it, beside the
    # sibling's 5,054 -- where the lookup before it had found the sibling.
    usage = tool.credential_usage("Registered / Nurse",
                                  _tally(**{"REGISTERED NURSE": 50, "MD": 5}))
    assert usage.credential == 50
    assert "looked up as REGISTERED NURSE" in usage.note
    assert "also written" not in usage.note  # found, not also another


# -- local corpora ---------------------------------------------------------------

_CREDIT = "ClinicalTrials.gov (NLM) study officials, data as of 2026-10-21"


def _local(*names: str) -> object:
    return tool._local_corpora().Local(
        "ctgov-officials", {"data_date": "2026-10-21"}, [{"name": n} for n in names])


def test_a_local_corpus_not_fetched_names_the_fetch(
        monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setenv("NAMEPARSER_TOOLS_CACHE", str(tmp_path))
    # One row per source, every one not fetched naming its own fetch.
    loaded = _LOAD_LOCALS()
    assert loaded == [(source, None, "")
                      for source in sorted(tool._local_corpora().SOURCES)]
    assert {"ctgov-officials", "fec-individuals"} <= {s for s, _, _ in loaded}
    for source, corpus, _ in loaded:
        row = tool.local_usage("MD", source, corpus)
        assert row.status == "not downloaded"
        assert f"local_corpora.py fetch {source}" in row.note


def test_a_local_corpus_row_counts_officials_and_the_comma_side() -> None:
    corpus = _local("Ann Lee, M.D.", "MD Bo Wu", "Cy Doe, MD, PhD", "Di Fox, MD/PhD",
                    "Ed Ng, md; MD")
    row = tool.local_usage("m.d", "ctgov-officials", corpus)
    assert row.status == "ok"
    # The credit and date lead, as ClinicalTrials.gov's terms ask; the
    # spellings count records, so none exceeds the officials writing it.
    assert row.note == (f"{_CREDIT}; 5 of 5 officials write it, 4 after a comma; "
                        "written MD 4, M.D. 1, md 1")
    assert tool.local_usage("PhD", "ctgov-officials", corpus).note.startswith(
        f"{_CREDIT}; 2 of 5 officials write it, 2 after a comma")
    missing = tool.local_usage("FNP-C", "ctgov-officials", corpus)
    assert missing.note == f"{_CREDIT}; 0 of 5 officials write it, 0 after a comma"
    assert tool.local_usage("..", "ctgov-officials", corpus).status == "unrepresentable"


@pytest.mark.parametrize("word", ["Ph. D.", "Ph D", "ph d,"])
def test_a_spaced_word_is_looked_up_as_its_words_in_a_row(word: str) -> None:
    # As one key it could match no word of the index, so it read zero.
    corpus = _local("Ann Lee, Ph. D.", "Bo Wu, Ph D", "Cy Doe, PhD")
    row = tool.local_usage(word, "ctgov-officials", corpus)
    assert row.note == (f"{_CREDIT}; 2 of 3 officials write it, 2 after a comma; "
                        "as one word 'phd' 1")


def test_a_local_corpus_row_appears_in_the_report(
        monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
    monkeypatch.setattr(tool, "load_locals", lambda: [
        ("ctgov-officials", _local("Ann Lee, MD"), "")])
    assert tool.main(["--no-wikidata", "MD"]) == 0
    out = capsys.readouterr().out
    assert "ctgov-officials (local corpus)" in out
    assert "1 of 1 officials write it, 1 after a comma" in out


def test_a_local_corpus_that_fails_to_load_fails_the_run(
        monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
    monkeypatch.setattr(tool, "load_locals", lambda: [
        ("ctgov-officials", None, "ValueError: does not match the sha256")])
    assert tool.main(["--no-wikidata", "MD"]) == 2
    assert "failed; ValueError: does not match the sha256" in capsys.readouterr().out


def test_a_bug_in_a_lookup_is_raised_not_reported_as_a_failed_row(
        monkeypatch: pytest.MonkeyPatch) -> None:
    def broken(*args: object) -> None:
        raise ValueError("a bug, not a damaged corpus")
    monkeypatch.setattr(tool._local_corpora(), "lookup", broken)
    with pytest.raises(ValueError, match="a bug"):
        tool.local_rows("MD", [("ctgov-officials", _local("Ann Lee, MD"), "")])


def test_records_damaged_after_the_index_was_cached_fail_their_own_row(
        monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    # A cached index answers load_locals without the records; a spaced
    # word then reads them first in the lookup, outside its guard.
    monkeypatch.setenv("NAMEPARSER_TOOLS_CACHE", str(tmp_path))
    module = tool._local_corpora()
    plant_corpus(monkeypatch, module, "ctgov-officials", [{"name": "Ann Lee, Ph. D."}],
                 "2026-10-21", "officials")
    _LOAD_LOCALS()  # builds and caches the index
    locals_ = [row for row in _LOAD_LOCALS() if row[0] == "ctgov-officials"]
    (tmp_path / "local" / "ctgov-officials" / "raw.jsonl").write_text("")
    [row] = tool.local_rows("Ph. D.", locals_)
    assert row.status == "failed" and "does not match the sha256" in row.note


@pytest.mark.parametrize("damage", ["meta key", "record shape"])
def test_a_damaged_local_corpus_fails_its_row_not_the_run(
        monkeypatch: pytest.MonkeyPatch, tmp_path: Path,
        capsys: pytest.CaptureFixture[str], damage: str) -> None:
    # The real loader over a real cache: a meta.json missing a key raised
    # KeyError, which _attempt does not catch, and took every row down.
    monkeypatch.setenv("NAMEPARSER_TOOLS_CACHE", str(tmp_path))
    module = tool._local_corpora()
    plant_corpus(monkeypatch, module, "ctgov-officials", [{"name": "Ann Lee, MD"}],
                 "2026-10-21", "officials")
    folder = tmp_path / "local" / "ctgov-officials"
    meta = json.loads((folder / "meta.json").read_text())
    if damage == "meta key":
        del meta["sha256"]
    else:
        raw = b'{"nom": "Ann Lee, MD"}\n'
        (folder / "raw.jsonl").write_bytes(raw)
        meta["sha256"] = hashlib.sha256(raw).hexdigest()
    (folder / "meta.json").write_text(json.dumps(meta))
    monkeypatch.setattr(tool, "load_locals", _LOAD_LOCALS)
    assert tool.main(["--no-wikidata", "MD"]) == 2
    out = capsys.readouterr().out
    assert "ctgov-officials (local corpus)" in out and "failed; CorpusDamaged" in out
    assert "US Census 2010 surnames" in out


# -- box indexes -----------------------------------------------------------------

def _boxes() -> object:
    corpora = tool._local_corpora()
    return corpora.BoxIndex(
        totals={"ES": 400, "MX": 100, "US": 5000, "": 9000},
        given={"del": {"MX": 30, "ES": 20, "": 50}},
        family={"del": {"ES": 60, "MX": 10, "US": 5, "": 80}})


def test_a_box_row_counts_each_box_and_gives_each_country_its_share() -> None:
    row = tool.box_usage("del", "patentsview-inventors", _boxes(), "", 2, [])
    assert (row.given, row.family) == (100, 155)
    # Ranked by people writing it, the records stating no country last:
    # they would lead every list and say nothing of where a name is borne.
    assert row.given_shares == [("MX", 30, 100), ("ES", 20, 400), ("--", 50, 9000)]
    assert row.family_shares == [("ES", 60, 400), ("MX", 10, 100), ("--", 80, 9000)]
    assert "14,500 people in 3 countries" in row.note


def test_a_country_asked_for_is_listed_outside_the_top() -> None:
    row = tool.box_usage("del", "patentsview-inventors", _boxes(), "", 1, ["US", "PH"])
    assert row.family_shares == [("ES", 60, 400), ("US", 5, 5000), ("PH", 0, 0),
                                 ("--", 80, 9000)]
    rendered = tool.render("del", [row])
    assert "family box by country: ES 60 (15.00% of 400), US 5 (0.10% of 5,000), " \
           "PH 0 (- of 0), -- 80 (0.89% of 9,000)" in rendered


@pytest.mark.parametrize(("word", "says"), [
    ("de la", "a spaced word is not looked up"),
    ("..", "nothing in it is left")])
def test_a_box_row_answers_single_words_only(word: str, says: str) -> None:
    row = tool.box_usage(word, "patentsview-inventors", _boxes(), "", 5, [])
    assert row.status == "unrepresentable" and says in row.note


def test_a_box_row_not_fetched_or_failed_says_so() -> None:
    missing = tool.box_usage("del", "patentsview-inventors", None, "", 5, [])
    assert missing.status == "not downloaded"
    assert "local_corpora.py fetch patentsview-inventors" in missing.note
    failed = tool.box_usage("del", "patentsview-inventors", None, "ValueError: gone", 5, [])
    assert (failed.status, failed.note) == ("failed", "ValueError: gone")


def test_only_the_sources_with_boxes_get_a_box_row(
        monkeypatch: pytest.MonkeyPatch) -> None:
    built: list[str] = []
    module = tool._local_corpora()
    def built_for(source: str) -> object:
        built.append(source)
        return _boxes()

    monkeypatch.setattr(module, "cached_box_index", built_for)
    locals_ = [(source, object(), "") for source in sorted(module.SOURCES)]
    found = tool.load_box_indexes(locals_)  # type: ignore[arg-type]
    assert [s for s, _, _ in found] == built == sorted(
        s for s, src in module.SOURCES.items() if src.boxes is not None)
    assert {"orcid-researchers", "patentsview-inventors"} <= set(built)


def test_the_country_option_reaches_the_box_rows(
        monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
    monkeypatch.setattr(tool, "load_locals", lambda: [])
    monkeypatch.setattr(tool, "load_box_indexes", lambda locals_: [
        ("patentsview-inventors", _boxes(), "")])
    assert tool.main(["--no-wikidata", "--countries", "1", "--country", "us", "del"]) == 0
    out = capsys.readouterr().out
    assert "patentsview-inventors (boxes by country)" in out
    assert "family box by country: ES 60 (15.00% of 400), US 5 (0.10% of 5,000)" in out


def test_the_box_rows_are_built_only_when_asked_for(
        monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
    # Building one takes minutes and reading one seconds: a plain lookup
    # must not pay for rows nobody asked for.
    asked: list[object] = []
    monkeypatch.setattr(tool, "load_locals", lambda: [])
    def loaded(locals_: object) -> list[tuple[str, object, str]]:
        asked.append(1)
        return [("patentsview-inventors", _boxes(), "")]

    monkeypatch.setattr(tool, "load_box_indexes", loaded)
    assert tool.main(["--no-wikidata", "del"]) == 0
    assert asked == [] and "boxes by country" not in capsys.readouterr().out
    assert tool.main(["--no-wikidata", "--boxes", "del"]) == 0
    assert asked == [1] and "boxes by country" in capsys.readouterr().out


def test_a_country_asked_for_twice_or_blank_is_listed_once(
        monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
    monkeypatch.setattr(tool, "load_locals", lambda: [])
    monkeypatch.setattr(tool, "load_box_indexes", lambda locals_: [
        ("patentsview-inventors", _boxes(), "")])
    assert tool.main(["--no-wikidata", "--countries", "1", "--country", "us",
                      "--country", "US", "--country", " ", "del"]) == 0
    line = next(l for l in capsys.readouterr().out.splitlines() if "family box" in l)
    assert line.count("US 5") == 1 and line.count("--") == 1
