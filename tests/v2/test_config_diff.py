"""Offline checks on tools/differential/config_diff.py.

What these pin is the tool's own logic: how a configuration is named
and built, the input filters, the tally of moves and of the words whose
role changed, the parallel path agreeing with the serial one, and the
gaps report's scoring (broken, fixed, changed, laid to a word) and its
WRITTEN_IN table reaching every tag and pack. The parsers the scoring
tests compare are the default and the default less one reading, so no
count here moves with the vocabulary, and the names are invented.
"""
import importlib
import importlib.util
import sys
from pathlib import Path
from types import ModuleType

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


@pytest.mark.parametrize("spec", ["", "plain:", "strict:XX", "fancy:es", "plain:es+",
                                  "expr:Lexicon.default()"])
def test_a_misnamed_configuration_is_refused(spec: str) -> None:
    with pytest.raises(ValueError):
        cd.build(spec)


# --- comparing ---------------------------------------------------------------------

def _readings(spec_a: str, spec_b: str, text: str) -> tuple[object, object]:
    return (cd.reading(cd.build(spec_a).parse(text)), cd.reading(cd.build(spec_b).parse(text)))


def test_changed_fields_name_the_roles_and_the_ambiguities() -> None:
    a, b = _readings("default", _NO_PHD, "Ana Souza PhD")
    assert cd.changed_fields(a, b) == ("middle", "family", "suffix")
    assert cd.changed_fields(a, a) == ()
    assert cd.word_moves(a, b) == [("souza", "family->middle"), ("phd", "suffix->family")]


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


def _args(**kw: object) -> object:
    import argparse
    base = {"committed": False, "local": [cd.PSC], "group": [], "match": None, "sample": None}
    return argparse.Namespace(**{**base, **kw})


def test_the_filters_keep_a_group_a_match_and_a_sample(monkeypatch: pytest.MonkeyPatch) -> None:
    _psc(monkeypatch, [("Ana Souza", "Brazilian"), ("Bo Lima", "Brazilian"),
                       ("Cy Dias", "French"), ("Ana Souza", "French")])
    every = cd.gather(_args())
    assert sorted(t for t, _o, _i in every) == ["Ana Souza", "Bo Lima", "Cy Dias"]
    assert {i for _t, _o, i in every} == {frozenset({cd.PSC})}
    assert [t for t, _o, _i in cd.gather(_args(group=["French"]))] == ["Cy Dias", "Ana Souza"]
    assert [t for t, _o, _i in cd.gather(_args(match=r"^B"))] == ["Bo Lima"]
    sampled = {t for t, _o, _i in cd.gather(_args(sample=2))}
    assert sampled == {e[0] for e in cd.snapshot.sampled([(t, None) for t in
                                                          ["Ana Souza", "Bo Lima", "Cy Dias"]], 2)}


def test_a_group_needs_a_fielded_corpus(monkeypatch: pytest.MonkeyPatch) -> None:
    with pytest.raises(SystemExit, match="fielded"):
        cd.local_names("ctgov-officials", ["US"])


# --- gaps -------------------------------------------------------------------------

def test_every_choosable_tag_has_a_row_and_no_row_names_another() -> None:
    assert set(cd.WRITTEN_IN) == set(cd.choosable())


def test_every_shipped_pack_rides_on_some_tag() -> None:
    reached = {item.lower() for tag in cd.choosable() for spec in cd.gap_specs(tag)
               for item in spec.partition(":")[2].split("+") if item.isupper()}
    assert set(locales.available()) <= reached


def test_a_pack_choosing_no_language_is_stacked_with_its_tag() -> None:
    assert cd.gap_specs("zh") == ("plain:ZH+zh", "strict:ZH+zh")
    assert cd.gap_specs("tr") == ("plain:TR_AZ+tr", "strict:TR_AZ+tr")
    assert cd.gap_specs("pt-BR") == ("plain:PT_BR", "strict:PT_BR")
    assert cd.gap_specs("vi")[0] == "default"  # vi.toml holds no reading


def test_changed_words_names_the_sets_a_word_leaves_and_joins() -> None:
    plain, strict = Parser().lexicon, cd.build(_NO_PHD).lexicon
    diff = cd.changed_words(plain, strict)
    assert list(diff) == ["phd"]
    lost, gained = diff["phd"]
    assert "suffix_acronyms" in lost and gained == ()


@pytest.mark.parametrize("text", ["Ana Souza PhD", "Ana Souza, Ph.D.", "Ana Souza PHD."])
def test_a_word_is_found_however_its_token_is_spelled(text: str) -> None:
    tokens = cd.reading(parse(text)).tokens
    assert cd.words_in(tokens, {"phd": 1}) == [("phd", len(tokens) - 1)]


def test_a_two_word_entry_is_found_across_adjacent_tokens() -> None:
    tokens = cd.reading(parse("Lt Col Ana Souza")).tokens
    assert ("lt col", 0) in cd.words_in(tokens, {"lt col": 1})


def _orcid(name: str, given: str, family: str) -> dict[str, str]:
    return {"name": name, "given": given, "family": family, "country": "XX"}


def test_a_gaps_record_is_broken_fixed_or_changed_and_laid_to_its_word(
        monkeypatch: pytest.MonkeyPatch) -> None:
    default = Lexicon.default()
    titles = frozenset(default._sets.titles)
    records = {(cd.ORCID, "XX"): [
        _orcid("Ana Souza PhD", "Ana", "Souza PhD"),     # plain agrees, strict not
        _orcid("Ana Souza PhD", "Ana Souza", "PhD"),     # strict agrees, plain not
        _orcid("Dr Ana Souza PhD", "Dr Ana", "Souza PhD"),  # a title typed as given: out
        _orcid("Ana Souza", "Ana", "Souza"),             # neither moves
    ]}
    monkeypatch.setitem(cd.WRITTEN_IN, "xx", cd.Where(("XX",)))
    rows = cd.gap_rows("xx", records, titles)
    assert len(rows) == 3
    specs = ("default", _NO_PHD)
    readings = cd._read_chunk([(r["name"], None, specs) for _s, _g, r in rows])[1]
    diff = cd.changed_words(Parser().lexicon, cd.build(_NO_PHD).lexicon)
    result = cd.score_gaps("xx", specs, rows, readings, diff,
                           cd.local_agreement._title_words(default))
    group = result["groups"][f"{cd.ORCID} XX"]
    assert (group["scored"], group["plain"], group["strict"]) == (3, 2, 2)
    assert (group["broke"], group["fixed"], group["changed"]) == (1, 1, 2)
    word = result["words"]["phd"]
    assert (word["broke"], word["fixed"], word["changed"]) == (1, 1, 2)
    assert word["roles"] == {"suffix->family": 2}
    assert word["example"] == "Ana Souza PhD (XX)" and word["example_broke"]
    assert any("phd" in line and "broke     1" in line for line in cd.format_gaps(result, 5))


def test_a_changed_gaps_record_holding_no_differing_word_is_counted_apart() -> None:
    a, b = cd.reading(parse("Ana Souza")), cd.reading(parse("Souza Ana"))
    rows = [(cd.ORCID, "XX", _orcid("Ana Souza", "Ana", "Souza"))]
    result = cd.score_gaps("xx", ("a", "b"), rows, [(a, b)], {}, frozenset())
    assert list(result["words"]) == [cd.NO_WORD]


def test_select_takes_each_groups_first_records_up_to_the_cap(
        monkeypatch: pytest.MonkeyPatch) -> None:
    _psc(monkeypatch, [(f"Ana Souza{i}", n) for i, n in
                       enumerate(["Vietnamese", "Vietnamese", "Vietnamese", "French"])])
    monkeypatch.setattr(cd, "GAP_SOURCES", ((cd.PSC, "nationality", "nationalities"),))
    got = cd.select(["vi"], cap=2)
    assert [r["name"] for r in got[(cd.PSC, "Vietnamese")]] == ["Ana Souza0", "Ana Souza1"]
    assert set(got) == {(cd.PSC, "Vietnamese")}
