"""Offline checks on tools/name_usage.py, the name-collision lookup.

The tool's sources are a downloaded file, a hand-downloaded file and a
live SPARQL endpoint, none of which a test may touch. What CAN go wrong
without them is the folding and the bookkeeping: a word that misses the
Census because it was folded differently from the Census's own spelling
reads as "under 100 bearers", which is exactly the false all-clear the
tool exists to prevent. These pin those pieces.

tools/ is not a package, so the module is loaded by path, as
_differential_fixtures.py loads compare.py.
"""
import importlib.util
import io
import sys
import zipfile
from pathlib import Path
from types import ModuleType

import pytest

_PATH = Path(__file__).parents[2] / "tools" / "name_usage.py"


def _load() -> ModuleType:
    spec = importlib.util.spec_from_file_location("name_usage", _PATH)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    # Registered before it runs: @dataclass resolves the module's
    # postponed annotations through sys.modules, and fails on a module
    # loaded by path that is not in it.
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


tool = _load()

_CENSUS = """name,rank,count,prop100k,cum_prop100k,pctwhite,pctblack,pctapi,pctaian,pct2prace,pcthispanic
OBRIEN,258,118557,40.19,0,93.85,1.29,0.76,0.27,1.51,2.32
SHEHU,39212,561,0.19,0,94.47,3.92,(S),0,0.89,(S)
"""


@pytest.mark.parametrize(("word", "key"), [
    ("O'Brien", "OBRIEN"),       # apostrophe dropped, as the Census spells it
    ("de la Cruz", "DELACRUZ"),  # spaces dropped
    ("Ó Murchú", "OMURCHU"),     # diacritics folded away
    ("关", ""),                   # nothing left: not representable
])
def test_census_key_folds_a_word_the_way_the_census_spells_it(word: str, key: str) -> None:
    assert tool.census_key(word) == key


def test_census_usage_finds_a_folded_surname_and_says_how() -> None:
    usage = tool.census_usage("O'Brien", tool.read_census(_CENSUS))
    assert usage.family == 118557
    assert "looked up as OBRIEN" in usage.note


def test_census_usage_omits_suppressed_shares() -> None:
    # (S) marks a share the Census suppressed for privacy; printing it as a
    # percentage would invent a number.
    note = tool.census_usage("shehu", tool.read_census(_CENSUS)).note
    assert "asian/PI" not in note and "hispanic" not in note
    assert "white 94.47%" in note


def test_census_usage_distinguishes_absent_from_unrepresentable() -> None:
    table = tool.read_census(_CENSUS)
    absent = tool.census_usage("marshal", table)
    assert absent.family == 0
    unrepresentable = tool.census_usage("关", table)
    assert unrepresentable.family is None  # no answer, not a zero


def _ssa_zip(files: dict[str, str]) -> zipfile.ZipFile:
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as zf:
        for name, text in files.items():
            zf.writestr(name, text)
    buffer.seek(0)
    return zipfile.ZipFile(buffer)


def test_read_ssa_totals_each_name_by_sex_across_years() -> None:
    totals = tool.read_ssa(_ssa_zip({
        "yob1990.txt": "Justice,F,40\nJustice,M,60\n",
        "yob2000.txt": "Justice,M,100\nMarshal,M,7\n",
        "NationalReadMe.pdf": "not data",
    }))
    assert totals["justice"] == {"F": 40, "M": 160}
    usage = tool.ssa_usage("Justice", totals)
    assert usage.given == 200


def test_ssa_usage_reports_a_missing_download_without_a_count() -> None:
    usage = tool.ssa_usage("justice", None)
    assert usage.given is None and "not downloaded" in usage.note


def test_wikidata_query_matches_the_word_in_every_language_and_escapes_it() -> None:
    query = tool.wikidata_query('Say "hi"', languages=("mul", "zh-hans"))
    assert r'"Say \"hi\""@mul' in query
    assert r'"Say \"hi\""@zh-hans' in query


def test_read_wikidata_keeps_stateless_people_out_of_the_country_list() -> None:
    usage = tool.read_wikidata(
        totals=[{"role": "family", "n": "180"}, {"role": "given", "n": "1"}],
        by_country=[
            {"role": "family", "n": "148"},  # no country bound
            {"role": "family", "country": "Albania", "n": "11"},
            {"role": "family", "country": "Nigeria", "n": "20"},
            {"role": "given", "country": "Nigeria", "n": "1"},
        ],
        top=5)
    assert (usage.given, usage.family) == (1, 180)
    assert usage.family_countries == [("Nigeria", 20), ("Albania", 11)]
    assert usage.family_stateless == 148


def test_merge_sums_the_case_variants_per_key() -> None:
    merged = tool._merge(
        [{"role": "given", "n": "2"}, {"role": "given", "n": "3"},
         {"role": "family", "n": "1"}],
        ("role",))
    assert sorted((row["role"], row["n"]) for row in merged) == [
        ("family", "1"), ("given", "5")]
