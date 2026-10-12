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
import urllib.request
import zipfile
from collections import Counter
from pathlib import Path
from types import ModuleType
from typing import Any

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
