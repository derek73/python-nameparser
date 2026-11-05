"""Offline checks on tools/differential/config_diff.py.

What these pin is the tool's own logic: how a configuration is named
and built, the input filters and their refusals, the tally of moves
(the views included) and of the words whose role changed, the parallel
path agreeing with the serial one, a run through main(), and the gaps
report's scoring (broken, fixed, changed, laid to the word whose own
token moved) and its country tables reaching every tag and pack. The
parsers the scoring tests compare are the default and the default less
one reading, so no count here moves with the vocabulary, and the names
are invented.
"""
import argparse
import importlib
import importlib.util
import sys
from pathlib import Path
from types import ModuleType
from typing import Any

import pytest

from nameparser import Lexicon, Parser, locales, parse

from ._differential_fixtures import own_cache, plant_corpus

_PATH = Path(__file__).parents[2] / "tools" / "differential" / "config_diff.py"


def _load() -> ModuleType:
    spec = importlib.util.spec_from_file_location("config_diff", _PATH)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


cd = _load()
_NO_PHD = 'expr:Parser(lexicon=Lexicon.default().remove("phd", kind="credential"))'


@pytest.fixture(autouse=True)
def _own_cache(monkeypatch: pytest.MonkeyPatch, tmp_path_factory: pytest.TempPathFactory) -> Path:
    return own_cache(monkeypatch, tmp_path_factory)


# --- configurations -------------------------------------------------------------

def test_a_configuration_names_packs_in_capitals_and_tags_in_lower_case() -> None:
    assert cd.build("default") == Parser()
    # the pack carries its [rules] policy; the bare tag only the choice
    assert cd.build("plain:ES").policy.two_family_names
    assert not cd.build("plain:es").policy.two_family_names
    assert cd.build("strict:es").lexicon.languages == frozenset({"es"})
    assert cd.build("strict:PT_BR+en").lexicon.languages == frozenset({"pt-BR", "en"})
    assert cd.build("plain:locales.ZH+zh").lexicon.languages == frozenset({"zh"})
    assert "phd" not in cd.build(_NO_PHD).lexicon._sets.suffix_acronyms


@pytest.mark.parametrize("spec,tag", [("plain:pt-BR", "pt-BR"), ("strict:en-GB", "en-GB")])
def test_a_bare_region_tag_builds(spec: str, tag: str) -> None:
    # a Locale's code must be lower case and a region tag is not, so a
    # bare choice carries a constant code (#1025 review)
    assert cd.build(spec).lexicon.languages == frozenset({tag})


@pytest.mark.parametrize("spec", ["", "plain:", "strict:XX", "fancy:es", "plain:es+",
                                  "expr:Lexicon.default()"])
def test_a_misnamed_configuration_is_refused(spec: str) -> None:
    with pytest.raises(ValueError):
        cd.build(spec)


def test_a_refused_bare_tag_is_named_as_typed() -> None:
    with pytest.raises(ValueError, match="'plain:xx': xx refused"):
        cd.build("plain:xx")


@pytest.mark.parametrize("spec", ["expr:Parser(1, 2, 3, 4)", "expr:Lexicon.nope()"])
def test_an_expr_that_raises_is_a_usage_error_not_a_traceback(spec: str) -> None:
    with pytest.raises(SystemExit) as stop:
        cd.main(["diff", "default", spec])
    assert stop.value.code == 2


# --- comparing ---------------------------------------------------------------------

def _readings(spec_a: str, spec_b: str, text: str) -> tuple[Any, Any]:
    return (cd.reading(cd.build(spec_a).parse(text)), cd.reading(cd.build(spec_b).parse(text)))


def test_changed_fields_name_the_roles_and_the_ambiguities() -> None:
    a, b = _readings("default", _NO_PHD, "Ana Souza PhD")
    assert cd.changed_fields(a, b) == ("middle", "family", "suffix", "credentials")
    assert cd.changed_fields(a, a) == ()
    assert cd.word_moves(a, b) == [("souza", "family->middle"), ("phd", "suffix->family")]


def test_a_view_moving_where_no_role_does_is_a_move() -> None:
    a, b = _readings("default", "plain:RU", "Ivan Ivanovich Petrov")
    assert a.fields == b.fields
    assert cd.changed_fields(a, b) == ("patronymic",)


def test_a_name_whose_tokens_differ_is_tallied_as_retokenized() -> None:
    a = cd.reading(parse("Ana Souza"))
    b = cd.Reading(a.fields[::-1], (), (("Ana Souza", "given"),))
    assert cd.word_moves(a, b) == [(cd.RETOKENIZED, "")]


def test_the_tally_counts_moves_by_input_fields_and_word() -> None:
    texts = ["Ana Souza PhD", "Bo Lima, PhD", "Ana Souza", "Cy Dias Ph.D."]
    names = [(t, None, frozenset({"one"} if i % 2 else {"one", "two"}))
             for i, t in enumerate(texts)]
    specs = ("default", _NO_PHD)
    readings = cd._read_chunk([(t, o, specs) for t, o, _ in names])[1]
    [t] = cd.tally(names, readings, 2)
    assert t.total == {"one": 4, "two": 2}
    assert t.moved == {"one": 3, "two": 1}
    # the dotted Ph.D. stays a suffix by its shape (rules/S3): only its
    # ambiguities move, so it is a moved name with no word moved
    assert t.words == {"phd": 2, "souza": 1, "bo": 1}
    assert t.word_move["phd"] == {"suffix->family": 1, "suffix->given": 1}
    assert t.word_example["phd"] == "Ana Souza PhD"
    assert t.by_fields[("ambiguities",)] == ["Cy Dias Ph.D."]
    assert sum(len(v) for v in t.by_fields.values()) == 3
    lines = cd.format_tally(_NO_PHD, "default", t, 5)
    assert lines[0].endswith("3 names moved") and any("phd" in line for line in lines)


def test_the_tally_counts_a_word_once_a_name() -> None:
    # two tokens of one word move in one name: one name for the word,
    # two moves for its commonest-move count
    a = cd.Reading(("", "Ana", "", "", "", "", ""), (), (("Ana", "given"), ("Bo", "family"),
                                                         ("Bo", "suffix")))
    b = cd.Reading(("", "Ana", "", "", "", "", ""), (), (("Ana", "given"), ("Bo", "middle"),
                                                         ("Bo", "family")))
    b = b._replace(fields=("", "Ana", "Bo", "Bo", "", "", ""))
    [t] = cd.tally([("Ana Bo Bo", None, frozenset({"x"}))], [(a, b)], 2)
    assert t.words == {"bo": 1}
    assert sum(t.word_move["bo"].values()) == 2


def test_the_parallel_path_reads_as_the_serial_one(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(cd.snapshot, "PARALLEL_FLOOR", 1)
    items = [(t, o, ("default", "strict:pt")) for t, o in
             [("Paulo Silva Junior", None), ("Dr John Smith", None),
              ("Smith John", "FAMILY_FIRST"), ("Ana de Souza, PhD", None)]]
    assert cd.read(items, 2) == cd.read(items, 1)


def test_a_shape_order_reads_the_name_under_it() -> None:
    [[r]] = [cd._read_chunk([("Smith John", "FAMILY_FIRST", ("default",))])[1][0]]
    assert dict(zip(cd.ROLES, r.fields))["family"] == "Smith"


# --- inputs ---------------------------------------------------------------------

def _psc(monkeypatch: pytest.MonkeyPatch, rows: list[tuple[str, str]]) -> None:
    corpora = cd.local_corpora
    records = [{"name": name, "forename": name.split()[0], "surname": name.split()[-1],
                "nationality": nat} for name, nat in rows]
    plant_corpus(monkeypatch, corpora, cd.PSC, records, "2026-10-22", "filed names",
                 {"sample": f"1 in {importlib.import_module('local_psc').PSC_SAMPLE}"})
    corpora.fetch(cd.PSC)


def _args(**kw: object) -> argparse.Namespace:
    base = {"committed": False, "local": [cd.PSC], "group": [], "match": None, "sample": None}
    return argparse.Namespace(**{**base, **kw})


def test_the_filters_keep_a_group_a_match_and_a_sample(monkeypatch: pytest.MonkeyPatch) -> None:
    _psc(monkeypatch, [("Ana Souza", "Brazilian"), ("Bo Lima", "Brazilian"),
                       ("Cy Dias", "French"), ("Ana Souza", "French")])
    every = cd.gather(_args())
    assert sorted(t for t, _o, _i in every) == ["Ana Souza", "Bo Lima", "Cy Dias"]
    assert {i for _t, _o, i in every} == {frozenset({cd.PSC})}
    assert [t for t, _o, _i in cd.gather(_args(group=["French"]))] == ["Cy Dias", "Ana Souza"]
    # found anywhere in the name, not only at its start
    assert [t for t, _o, _i in cd.gather(_args(match=r"Lima"))] == ["Bo Lima"]
    sampled = {t for t, _o, _i in cd.gather(_args(sample=2))}
    assert sampled == {e[0] for e in cd.snapshot.sampled([(t, None) for t in
                                                          ["Ana Souza", "Bo Lima", "Cy Dias"]], 2)}


@pytest.mark.parametrize("kw,message", [
    ({"local": None, "group": ["BR"]}, "give --local"),
    ({"committed": True, "group": ["Brazilian"]}, "drop --committed"),
    ({"group": ["brazilian"]}, "no record read holds it"),
])
def test_a_group_that_cannot_filter_is_refused(monkeypatch: pytest.MonkeyPatch,
                                               kw: dict[str, object], message: str) -> None:
    _psc(monkeypatch, [("Ana Souza", "Brazilian")])
    with pytest.raises(SystemExit, match=message):
        cd.gather(_args(**kw))


def test_a_source_holding_none_of_a_group_says_so(
        monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
    _psc(monkeypatch, [("Ana Souza", "Brazilian")])
    monkeypatch.setattr(cd, "local_names", lambda source, groups: (
        (["Ana Souza"], {"Brazilian"}) if source == cd.PSC else ([], set())))
    monkeypatch.setattr(cd.local_corpora, "SOURCES", {cd.PSC: None, cd.ORCID: None})
    got = cd.gather(_args(local=[cd.PSC, cd.ORCID], group=["Brazilian"]))
    assert [t for t, _o, _i in got] == ["Ana Souza"]
    assert f"no record of {cd.ORCID} holds it" in capsys.readouterr().out


def test_a_group_needs_a_fielded_corpus() -> None:
    with pytest.raises(SystemExit, match="fielded"):
        cd.local_names("ctgov-officials", ["US"])


def test_local_all_with_a_group_reads_the_fielded_corpora_only(
        monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
    _psc(monkeypatch, [("Ana Souza", "Brazilian"), ("Cy Dias", "French")])
    got = cd.gather(_args(local=["all"], group=["Brazilian"]))
    assert [t for t, _o, _i in got] == ["Ana Souza"]
    assert "fielded corpora only" in capsys.readouterr().out


def test_main_runs_a_diff_end_to_end(monkeypatch: pytest.MonkeyPatch,
                                     capsys: pytest.CaptureFixture[str], tmp_path: Path) -> None:
    _psc(monkeypatch, [("Ana Souza PhD", "Brazilian"), ("Bo Lima", "Brazilian")])
    out = tmp_path / "readings.jsonl"
    assert cd.main(["diff", "default", _NO_PHD, "--local", cd.PSC, "--jobs", "1",
                    "--readings", str(out)]) == 0
    printed = capsys.readouterr().out
    assert printed.startswith("2 names under 2 configurations")
    assert "1 names moved" in printed and "phd" in printed
    assert len(cd.snapshot.jsonl_lines(out.read_text(encoding="utf-8"))) == 2


# --- gaps -------------------------------------------------------------------------

def test_every_choosable_tag_stands_under_a_country_or_is_named_unmeasured() -> None:
    listed = {tag for tags in cd.LANGUAGES_OF.values() for tag in tags}
    assert listed <= set(cd.choosable())
    assert listed | cd.NO_COUNTRY == set(cd.choosable())
    assert not listed & cd.NO_COUNTRY
    assert set(cd.NATIONALITY.values()) <= set(cd.LANGUAGES_OF)


def test_every_shipped_pack_rides_on_some_tag() -> None:
    from nameparser._reading_index import selected
    reached = {item.lower() for tag in cd.choosable() for spec in cd.gap_specs(tag)
               for item in spec.partition(":")[2].split("+") if item.isupper()}
    # a pack choosing a region tag no file holds (es_ar's es-AR) selects
    # its language's files and nothing more, so the strict gap the report
    # measures for the pack choosing those files is its own
    files = {code: selected(locales.get(code).languages)
             for code in locales.available() if locales.get(code).languages}
    same_files = {code for code, f in files.items()
                  if any(f == files.get(other) for other in reached - {code})}
    assert same_files == {"es_ar"}
    assert set(locales.available()) <= reached | same_files


def test_a_pack_choosing_no_language_is_stacked_with_its_tag() -> None:
    assert cd.gap_specs("zh") == ("plain:ZH+zh", "strict:ZH+zh")
    assert cd.gap_specs("tr") == ("plain:TR_AZ+tr", "strict:TR_AZ+tr")
    assert cd.gap_specs("pt-BR") == ("plain:PT_BR", "strict:PT_BR")
    assert cd.gap_specs("vi")[0] == "default"  # vi.toml holds no reading


def test_a_group_is_placed_by_country_or_nationality() -> None:
    assert cd.stands_under(cd.ORCID, "IN", "ta") and cd.stands_under(cd.ORCID, "IN", "en")
    assert cd.stands_under(cd.PSC, "Scottish", "gd") and not cd.stands_under(cd.PSC, "British", "gd")
    assert cd.country_of(cd.PSC, "British,Irish") == "GB"
    assert cd.country_of(cd.ORCID, "ZZ") is None and cd.country_of(cd.PSC, "Martian") is None


def test_unmapped_names_every_group_the_tables_place_nowhere_at_any_count() -> None:
    # #1025's second review: a floor hid real nationalities, and a
    # joined spelling spread one over several groups
    counts = {(cd.ORCID, "ZZ"): 500, (cd.ORCID, "BR"): 900, (cd.PSC, "Martian"): 120,
              (cd.PSC, "Venusian"): 3, (cd.PSC, "Venusian,British"): 2,
              (cd.PSC, "Venusian/British"): 1, (cd.PSC, "British/Venusian"): 4}
    assert cd.unmapped(counts) == [(cd.ORCID, "ZZ", 500), (cd.PSC, "Martian", 120),
                                   (cd.PSC, "Venusian", 6)]


def test_a_joined_nationality_is_read_by_its_first() -> None:
    assert cd.first_spelling("British,Irish") == cd.first_spelling("British/Irish") == "British"
    assert cd.country_of(cd.PSC, "Australian/British") == "AU"


def test_changed_words_names_the_sets_a_word_leaves_and_joins() -> None:
    plain, strict = Parser().lexicon, cd.build(_NO_PHD).lexicon
    diff = cd.changed_words(plain, strict)
    assert list(diff) == ["phd"]
    lost, gained = diff["phd"]
    assert "suffix_acronyms" in lost and gained == ()


@pytest.mark.parametrize("text", ["Ana Souza PhD", "Ana Souza, Ph.D.", "Ana Souza PHD."])
def test_a_word_is_found_however_its_token_is_spelled(text: str) -> None:
    tokens = cd.reading(parse(text)).tokens
    n = len(tokens)
    assert cd.words_in(tokens, {"phd": 1}) == [("phd", n - 1, n)]


def test_a_two_word_entry_is_found_across_adjacent_tokens() -> None:
    tokens = cd.reading(parse("Lt Col Ana Souza")).tokens
    assert ("lt col", 0, 2) in cd.words_in(tokens, {"lt col": 1})


def _orcid(name: str, given: str, family: str) -> dict[str, str]:
    return {"name": name, "given": given, "family": family, "country": "XX"}


def _score(rows: list[tuple[str, str, dict[str, str]]], specs: tuple[str, str]) -> dict[str, Any]:
    readings = cd._read_chunk([(r["name"], None, specs) for _s, _g, r in rows])[1]
    diff = cd.changed_words(cd.build(specs[0]).lexicon, cd.build(specs[1]).lexicon)
    return cd.score_gaps("xx", specs, rows, readings, diff,
                         cd.local_agreement._title_words(Lexicon.default()))


def test_a_gaps_record_is_broken_fixed_or_changed_and_laid_to_its_word(
        monkeypatch: pytest.MonkeyPatch) -> None:
    titles = frozenset(Lexicon.default()._sets.titles)
    records = {(cd.ORCID, "XX"): [
        _orcid("Ana Souza PhD", "Ana", "Souza PhD"),     # plain agrees, strict not
        _orcid("Ana Souza PhD", "Ana Souza", "PhD"),     # strict agrees, plain not
        _orcid("Dr Ana Souza PhD", "Dr Ana", "Souza PhD"),  # a title typed as given: out
        _orcid("Ana Souza", "Ana", "Souza"),             # neither moves
    ]}
    monkeypatch.setitem(cd.LANGUAGES_OF, "XX", ("xx",))
    rows = cd.gap_rows("xx", records, titles)
    assert len(rows) == 3
    result = _score(rows, ("default", _NO_PHD))
    group = result["groups"][f"{cd.ORCID} XX"]
    assert (group["scored"], group["plain"], group["strict"]) == (3, 2, 2)
    assert (group["broke"], group["fixed"], group["changed"]) == (1, 1, 2)
    word = result["words"]["phd"]
    assert (word["broke"], word["fixed"], word["changed"], word["beside"]) == (1, 1, 2, 1)
    assert word["roles"] == {"suffix->family": 2}
    assert word["example"] == "Ana Souza PhD (XX)" and word["example_broke"]
    assert any("phd" in line and "broke     1" in line for line in cd.format_gaps(result, 5))


def test_a_break_is_laid_to_the_word_that_moved_not_one_beside_it() -> None:
    # #1025 review: in `Miss Beatriz Guadalupe Do Bom Jesus` under strict
    # pt, miss broke the name and do, read differently but keeping its
    # role there, only stood in it. Here do differs in a set this name
    # never reaches, so its token keeps its role while miss's moves.
    specs = ("default", 'expr:Parser(lexicon=Lexicon.default().remove("miss", kind="salutation"))')
    rows = [(cd.ORCID, "XX", _orcid("Miss Ana Do Souza", "Ana", "Do Souza"))]
    readings = cd._read_chunk([(r["name"], None, specs) for _s, _g, r in rows])[1]
    [(a, b)] = readings
    assert a.tokens[0][1] != b.tokens[0][1] and a.tokens[2][1] == b.tokens[2][1]
    diff = {**cd.changed_words(cd.build(specs[0]).lexicon, cd.build(specs[1]).lexicon),
            "do": (("suffix_acronyms",), ())}
    result = cd.score_gaps("xx", specs, rows, readings, diff,
                           cd.local_agreement._title_words(Lexicon.default()))
    assert result["words"]["miss"]["broke"] == 1
    assert "do" not in result["words"]  # stood in it, credited nothing


def test_a_particle_beside_the_moved_token_is_credited_when_none_moved_itself() -> None:
    p = cd.Reading(("", "Ana", "", "Da Souza", "", "", ""), (),
                   (("Ana", "given"), ("Da", "family"), ("Souza", "family")))
    s = cd.Reading(("", "Ana", "Da", "Souza", "", "", ""), (),
                   (("Ana", "given"), ("Da", "family"), ("Souza", "middle")))
    assert cd.credited(p, s, [("da", 1, 2)]) == [("da", 1, 2)]
    assert cd.credited(p, s, [("ana", 0, 1)]) == []


def test_a_word_twice_in_a_record_is_credited_once() -> None:
    # #1025's second review: `Sultan Sultan Hamad Mohammed Al Azri` gave
    # its group 1 break and sultan 2; beside is once a record too
    p = cd.Reading(("Sultan", "Sultan", "", "Hamad", "", "", ""), (),
                   (("Sultan", "title"), ("Sultan", "given"), ("Hamad", "family")))
    s = cd.Reading(("", "Sultan", "Sultan", "Hamad", "", "", ""), (),
                   (("Sultan", "given"), ("Sultan", "middle"), ("Hamad", "family")))
    rows = [(cd.ORCID, "XX", _orcid("Sultan Sultan Hamad", "Sultan", "Hamad"))]
    result = cd.score_gaps("xx", ("a", "b"), rows, [(p, s)],
                           {"sultan": (("titles",), ())}, frozenset())
    assert result["groups"][f"{cd.ORCID} XX"]["broke"] == 1
    word = result["words"]["sultan"]
    assert (word["broke"], word["changed"], word["beside"]) == (1, 1, 1)
    assert word["roles"] == {"title->given": 1}


def test_a_changed_gaps_record_holding_no_differing_word_is_counted_apart() -> None:
    a, b = cd.reading(parse("Ana Souza")), cd.reading(parse("Souza Ana"))
    rows = [(cd.ORCID, "XX", _orcid("Ana Souza", "Ana", "Souza"))]
    result = cd.score_gaps("xx", ("a", "b"), rows, [(a, b)], {}, frozenset())
    assert list(result["words"]) == [cd.NO_WORD]


def test_gaps_counts_a_change_of_roles_not_of_ambiguities() -> None:
    a = cd.reading(parse("Ana Souza"))
    b = a._replace(kinds=("GIVEN_OR_FAMILY",))
    rows = [(cd.ORCID, "XX", _orcid("Ana Souza", "Ana", "Souza"))]
    result = cd.score_gaps("xx", ("a", "b"), rows, [(a, b)], {}, frozenset())
    assert result["groups"][f"{cd.ORCID} XX"]["changed"] == 0


def test_select_takes_each_groups_first_records_up_to_the_cap(
        monkeypatch: pytest.MonkeyPatch) -> None:
    _psc(monkeypatch, [(f"Ana Souza{i}", n) for i, n in
                       enumerate(["Vietnamese", "Vietnamese", "Vietnamese", "French", "Martian"])])
    monkeypatch.setattr(cd, "GAP_SOURCES", ((cd.PSC, "nationality"),))
    got, counts = cd.select(["vi"], cap=2)
    assert [r["name"] for r in got[(cd.PSC, "Vietnamese")]] == ["Ana Souza0", "Ana Souza1"]
    assert set(got) == {(cd.PSC, "Vietnamese")}
    assert counts[(cd.PSC, "Martian")] == 1 and counts[(cd.PSC, "Vietnamese")] == 3


# --- score -------------------------------------------------------------------------

def test_a_switch_suffix_sets_bool_policy_fields_over_the_packs_patch() -> None:
    assert cd.switched("plain:ES@two_family_names=0,two_given_names=1") == (
        "plain:ES", {"two_family_names": False, "two_given_names": True})
    # the switch is set last, so it turns off what the pack's [rules] turned on
    assert not cd.build("plain:ES@two_family_names=0").policy.two_family_names
    assert cd.build("default@two_given_names=1").policy.two_given_names
    # an expr's own @ is Python, not a switch
    assert cd.switched("expr:Parser()@x") == ("expr:Parser()@x", {})


@pytest.mark.parametrize("spec", ["default@name_order=1", "default@two_family_names=yes",
                                  "default@two_family_names", "default@nope=1",
                                  "default@two_family_names=1,two_family_names=0"])
def test_a_misnamed_switch_is_refused(spec: str) -> None:
    with pytest.raises(ValueError, match="switch|twice"):
        cd.build(spec)


def test_expand_writes_every_combination_in_full() -> None:
    assert cd.expand(["default"], []) == ["default"]
    assert cd.expand(["default", "plain:ES"], ["two_family_names", "two_given_names"]) == [
        f"{spec}@two_family_names={a},two_given_names={b}"
        for spec in ("default", "plain:ES") for a in "01" for b in "01"]


def test_score_rows_counts_agreement_and_fixes_and_breaks_against_the_first() -> None:
    rows = [_orcid("Ana García López", "Ana", "García López"),   # O6 reads it right
            _orcid("Ana María López", "Ana María", "López"),     # the default does
            _orcid("Ana López", "Ana", "López")]                 # both do
    specs = ("default", "default@two_family_names=1")
    readings = cd._read_chunk([(r["name"], None, specs) for r in rows])[1]
    scored, per = cd.score_rows(rows, cd.local_agreement.FIELDED[cd.ORCID], readings,
                                cd.local_agreement._title_words(Lexicon.default()))
    assert scored == 3
    assert [(s.agree, s.fixed, s.broken) for s in per] == [(2, 0, 0), (2, 1, 1)]
    lines = cd.format_score(specs, [{"source": cd.ORCID, "group": "XX", "scored": scored,
                                     "specs": [dict(spec=s, agree=p.agree, fixed=p.fixed,
                                                    broken=p.broken)
                                               for s, p in zip(specs, per)]}])
    assert lines[-1].split()[:5] == ["ORCID", "XX", "3", "66.67", "66.67"]
    assert lines[-1].split()[5:] == ["[0]", "+0.00", "0/0"]


def test_score_selects_a_named_group_or_a_languages_countries(
        monkeypatch: pytest.MonkeyPatch) -> None:
    _psc(monkeypatch, [("Ana Souza", "Brazilian"), ("Bo Lima", "French"),
                       ("Cy Pena", "Spanish")])
    monkeypatch.setattr(cd, "GAP_SOURCES", ((cd.PSC, "nationality"),))
    assert set(cd.score_select(["French"], [], cap=5)) == {(cd.PSC, "French")}
    assert set(cd.score_select([], ["es"], cap=5)) == {(cd.PSC, "Spanish")}
    assert len(cd.score_select([], [], cap=5)) == 3


def test_main_runs_a_score_end_to_end(monkeypatch: pytest.MonkeyPatch,
                                      capsys: pytest.CaptureFixture[str]) -> None:
    _psc(monkeypatch, [("Ana Souza", "Brazilian"), ("Bo Lima", "Brazilian")])
    monkeypatch.setattr(cd, "GAP_SOURCES", ((cd.PSC, "nationality"),))
    assert cd.main(["score", "default", "--switches", "two_family_names",
                    "--group", "Brazilian", "--min", "1", "--jobs", "1"]) == 0
    out = capsys.readouterr().out
    assert "[1] default@two_family_names=1" in out
    assert out.splitlines()[-1].split()[:5] == ["PSC", "Brazilian", "2", "100.00", "100.00"]


def test_a_second_suffix_or_switches_over_an_expr_is_refused() -> None:
    with pytest.raises(ValueError, match="one @ suffix"):
        cd.build("default@two_family_names=1@two_given_names=0")
    # each names the fix that applies to it: an expr: reads no suffix
    with pytest.raises(ValueError, match="never reads; set the fields in the expression's Policy"):
        cd.expand(["expr:Parser()"], ["two_family_names"])
    with pytest.raises(ValueError, match="drop the SPEC's suffix, or --switches"):
        cd.expand(["plain:ES@two_given_names=1"], ["two_family_names"])


def test_score_drops_title_and_empty_box_records_and_small_groups(
        monkeypatch: pytest.MonkeyPatch) -> None:
    big = [_orcid("Ana García López", "Ana", "García López"),
           _orcid("Ana López", "Ana", ""),                   # no family box: out
           _orcid("Dr Ana López", "Dr Ana", "López")]        # a title typed as given: out
    small = [{**_orcid("Bo Lima", "Bo", "Lima"), "country": "YY"}]
    monkeypatch.setattr(cd, "score_select", lambda *_a: {(cd.ORCID, "XX"): big,
                                                         (cd.ORCID, "YY"): small})
    results = cd.score(("default",), [], [], cap=10, floor=1, jobs=1)
    assert [(r["group"], r["scored"]) for r in results] == [("XX", 1), ("YY", 1)]
    results = cd.score(("default",), [], [], cap=10, floor=2, jobs=1)
    assert results == []


def test_score_refuses_a_group_or_language_that_selects_nothing(
        monkeypatch: pytest.MonkeyPatch) -> None:
    _psc(monkeypatch, [("Ana Souza", "Brazilian")])
    monkeypatch.setattr(cd, "GAP_SOURCES", ((cd.PSC, "nationality"),))
    with pytest.raises(SystemExit, match="Brazil: no record holds it"):
        cd.score_select(["Brazil"], [], cap=5)
    for argv in (["--languages", "bo"], ["--min", "0"]):
        with pytest.raises(SystemExit) as stop:
            cd.main(["score", "default", *argv])
        assert stop.value.code == 2
