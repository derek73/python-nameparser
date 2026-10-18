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
import io
import json
import sys
import urllib.error
import urllib.parse
import urllib.request
import zipfile
from collections import Counter
from pathlib import Path
from types import ModuleType
from typing import Any, Protocol

import pytest

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
    assert rows["census"] == ["-", "<100"]
    assert rows["ssa"] == ["-", "-"]
    assert rows["wikidata"] == ["0+", "12+"]


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
        "US Census 2010 surnames", "US SSA given names 1880-"]
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
    census, ssa = json.loads(out)["shehu"]
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
    queries = _stub_sparql(monkeypatch, [
        [{"n": "2", "example": "http://www.wikidata.org/entity/Q99"}],
    ])
    usage = tool.ends_with_usage("部長", index, top=5)
    assert (usage.given, usage.family) == (0, 0)  # nothing ENDS in 部長
    assert "VALUES ?f { wd:Q1 }" in queries[0]
    assert "VALUES ?g { wd:Q3 }" in queries[0]
    [split] = usage.splits
    assert (split.people, split.example) == (2, "Q99")
    text = tool.render("部長", [usage])
    assert "family ending 部 + given 長: 2+ people" in text
    assert "e.g. 阿部; Q99" in text


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


def test_main_adds_the_ends_with_row_for_a_cjk_word(
        monkeypatch: pytest.MonkeyPatch, tmp_path: Path,
        capsys: pytest.CaptureFixture[str]) -> None:
    monkeypatch.setenv("NAMEPARSER_TOOLS_CACHE", str(tmp_path))
    monkeypatch.setattr(tool, "load_census", lambda download: None)
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
