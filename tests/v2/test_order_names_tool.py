"""Checks on tools/vocab/order_names.py, which writes the romanized
surname table the group suggester reads (``config/_order_names.py``).

The table is read by the suggester only, never by a parse. The tool's
reading and folding are pinned on hand-built input; the shipped block is
held to what the tool writes from its cached Wikidata answer, skipped
where the cache is absent.
"""
from __future__ import annotations

import importlib.util
import json
import sys
import urllib.request
from pathlib import Path
from types import ModuleType

import pytest

from nameparser.config import _order_names
from tests.checkout import needs_checkout

_TOOLS = Path(__file__).parents[2] / "tools"
_PATH = _TOOLS / "vocab" / "order_names.py"


def _load() -> ModuleType:
    sys.path.insert(0, str(_TOOLS))
    try:
        spec = importlib.util.spec_from_file_location("order_names", _PATH)
        assert spec is not None and spec.loader is not None
        module = importlib.util.module_from_spec(spec)
        sys.modules[spec.name] = module
        spec.loader.exec_module(module)
    finally:
        sys.path.remove(str(_TOOLS))
    return module


@pytest.fixture(scope="module")
def tool() -> ModuleType:
    return _load()


@pytest.fixture(autouse=True)
def _no_network(monkeypatch: pytest.MonkeyPatch) -> None:
    def refuse(*args: object, **kwargs: object) -> None:
        raise AssertionError("a test reached the network")
    monkeypatch.setattr(urllib.request, "urlopen", refuse)


def _stub_sparql(monkeypatch: pytest.MonkeyPatch, tool: ModuleType,
                 answer: object) -> None:
    """Answer every query through the ``name_usage`` the tool's ``ask``
    calls: the copy ``zh_surnames`` holds, which another test module's
    loader may have made a different object from ``tool.name_usage``."""
    monkeypatch.setattr(tool.zh_surnames.name_usage, "_sparql_csv", answer)


@needs_checkout
def test_fold_strips_tones_and_vietnamese_marks(tool: ModuleType) -> None:
    assert tool.fold("Nguyễn") == "nguyen"
    assert tool.fold("Đặng") == "dang"
    assert tool.fold("Lǚ") == "lv"


@needs_checkout
def test_pinyin_is_every_reading_of_every_item_labelled_with_the_character(
        tool: ModuleType) -> None:
    w = "http://www.wikidata.org/entity/"
    items = [{"label": "鄭", "item": w + "Q1"}, {"label": "郑", "item": w + "Q1"},
             {"label": "乐", "item": w + "Q2"}, {"label": "乐", "item": w + "Q3"},
             {"label": "田", "item": w + "Q4"}]
    pinyin = [{"item": w + "Q1", "py": "Zhèng"}, {"item": w + "Q2", "py": "Lè"},
              {"item": w + "Q3", "py": "Yuè"}, {"item": w + "Q3", "py": "Yuè"},
              # a P460 target's native label written in Han, and a phrase
              {"item": w + "Q4", "py": "田"}, {"item": w + "Q4", "py": "Tián Jiā"}]
    assert tool.read_pinyin(items, pinyin) == {
        "鄭": {"zheng"}, "郑": {"zheng"}, "乐": {"le", "yue"}}


@needs_checkout
def test_the_queries_ask_each_character_and_every_pinyin_statement(
        tool: ModuleType) -> None:
    items = tool.items_query(["鄭", "王"])
    assert all(f'"{c}"@{lang}' in items for c in "鄭王"
               for lang in tool.LABEL_LANGUAGES)
    assert "wd:Q101352" in items and "wd:Q1093580" in items
    pinyin = tool.pinyin_query(["Q1", "Q2"])
    assert "wd:Q1 wd:Q2" in pinyin
    # the three statements, each qualified as Hanyu Pinyin (Q42222)
    assert "ps:P2440 ?py ; pq:P459 wd:Q42222" in pinyin
    assert "?item p:P1705 ?st . ?st pq:P1721 ?py" in pinyin
    assert "pq:P1013 wd:Q42222" in pinyin and "?latin wdt:P1705 ?py" in pinyin


@needs_checkout
def test_the_pinyin_cache_answers_only_the_queries_it_was_asked(
        tool: ModuleType, monkeypatch: pytest.MonkeyPatch,
        tmp_path_factory: pytest.TempPathFactory) -> None:
    from ._differential_fixtures import own_cache
    cache = own_cache(monkeypatch, tmp_path_factory)
    w = "http://www.wikidata.org/entity/"
    asked: list[str] = []

    def sparql_csv(query: str) -> list[dict[str, str]]:
        asked.append(query)
        if "?label ?item" in query:
            return [{"label": "鄭", "item": w + "Q1"}]
        return [{"item": w + "Q1", "py": "Zhèng"}]
    _stub_sparql(monkeypatch, tool, sparql_csv)
    assert tool.load_pinyin(["鄭"], False) == {"鄭": {"zheng"}}
    assert len(asked) == 2
    tool.load_pinyin(["鄭"], False)
    assert len(asked) == 2
    tool.load_pinyin(["鄭"], True)
    tool.load_pinyin(["鄭", "王"], False)
    assert len(asked) == 6
    # a SUBSET of the characters cached is another query: asked again
    tool.load_pinyin(["王"], False)
    assert len(asked) == 8
    # and so is the same characters asked by another pinyin query
    monkeypatch.setattr(tool, "pinyin_query",
                        lambda qids: "SELECT ?item ?py # another" + str(qids))
    tool.load_pinyin(["王"], False)
    assert len(asked) == 10
    assert (cache / tool.PINYIN_FILE).exists()


@needs_checkout
def test_a_batch_of_items_with_no_reading_is_an_answer(
        tool: ModuleType, monkeypatch: pytest.MonkeyPatch,
        tmp_path_factory: pytest.TempPathFactory) -> None:
    from ._differential_fixtures import own_cache
    own_cache(monkeypatch, tmp_path_factory)
    w = "http://www.wikidata.org/entity/"

    def sparql_csv(query: str) -> list[dict[str, str]]:
        if "?label ?item" in query:
            return [{"label": "刁", "item": w + "Q1"}]
        return []
    _stub_sparql(monkeypatch, tool, sparql_csv)
    assert tool.load_pinyin(["刁"], False) == {}


@needs_checkout
def test_a_cut_pinyin_answer_is_refused(
        tool: ModuleType, monkeypatch: pytest.MonkeyPatch,
        tmp_path_factory: pytest.TempPathFactory) -> None:
    from ._differential_fixtures import own_cache
    cache = own_cache(monkeypatch, tmp_path_factory)
    w = "http://www.wikidata.org/entity/"

    def sparql_csv(query: str) -> list[dict[str, str | None]]:
        if "?label ?item" in query:
            return [{"label": "鄭", "item": w + "Q1"}]
        # csv.DictReader fills a short row's missing columns with None
        return [{"item": "http:/SPARQL-QUERY: queryStr=", "py": None}]
    _stub_sparql(monkeypatch, tool, sparql_csv)
    with pytest.raises(ValueError, match="not one"):
        tool.load_pinyin(["鄭"], False)
    assert not (cache / tool.PINYIN_FILE).exists()


@needs_checkout
def test_pinyin_surnames_drop_one_letter_readings_and_unread_characters(
        tool: ModuleType) -> None:
    assert tool.pinyin_surnames(["阿", "鄭", "刁"],
                                {"阿": {"a"}, "鄭": {"zheng"}}) == {"zheng"}


@needs_checkout
def test_a_block_round_trips_through_rewrite(tool: ModuleType) -> None:
    block = tool.render_block("PINYIN", ["wang", "zhang"])
    other = tool.render_block("OTHER", ["x"])
    text = f"head\n{block}\nmid\n{other}\ntail\n"
    new = tool.render_block("PINYIN", ["li"])
    out = tool.rewrite(text, "PINYIN", new)
    assert new in out and other in out and "wang" not in out
    assert tool.rewrite(text, "PINYIN", block) == text
    with pytest.raises(ValueError, match="no generated block"):
        tool.rewrite("nothing here", "PINYIN", block)


@needs_checkout
def test_the_hand_lists_are_folded_and_the_table_has_no_one_letter_entry() -> None:
    table = _order_names.ROMANIZED_SURNAMES
    assert all(len(w) >= 2 and w == w.lower() and w.isascii() and w.isalpha()
               for w in table)
    for name in ("_ZH_OTHER_SPELLINGS", "_KO_SPELLINGS", "_VI_SURNAMES"):
        words = getattr(_order_names, name)
        assert words and set(words) <= table
    assert {"zheng", "nguyen", "kim", "wong"} <= table


def _cached_pinyin(tool: ModuleType) -> dict[str, set[str]]:
    """The readings from the tool's cached Wikidata answer, read
    without the network; skipped where it is absent."""
    path = tool.name_usage.cache_dir() / tool.PINYIN_FILE
    if not path.exists():
        pytest.skip("the Wikidata pinyin cache is absent "
                    "(tools/vocab/order_names.py fetches it)")
    cached = json.loads(path.read_text(encoding="utf-8"))
    return tool.read_pinyin(cached["items"], cached["pinyin"])


@needs_checkout
def test_the_shipped_surname_block_is_what_the_tool_writes(
        tool: ModuleType) -> None:
    from nameparser import locales
    readings = _cached_pinyin(tool)
    singles = [s for s in locales.ZH.lexicon._sets.surnames if len(s) == 1]
    block = tool.render_block("PINYIN", sorted(
        tool.pinyin_surnames(singles, readings)))
    text = Path(_order_names.__file__).read_text(encoding="utf-8")
    assert tool.rewrite(text, "PINYIN", block) == text


def _common(tool: ModuleType, countries: dict[str, dict[str, int]],
            given: dict[str, int], family: dict[str, int] | None = None, *,
            top: int = 10, min_country_uses: int = 1,
            exclude: frozenset[str] = frozenset()) -> set[str]:
    # the family share is the tool's own constant, so a test of the cut
    # fails when the constant moves
    from collections import Counter
    return tool.common_given(  # type: ignore[no-any-return]
        {c: Counter(words) for c, words in countries.items()},
        Counter(given), Counter(family or {}), top=top,
        min_country_uses=min_country_uses,
        max_family_share=tool.MAX_FAMILY_SHARE,
        min_uses=20, exclude=set(exclude))


@needs_checkout
def test_a_name_mostly_written_as_a_family_name_is_dropped(
        tool: ModuleType) -> None:
    got = _common(tool, {"X": {"thomas": 9, "kim": 9, "anna": 9}},
                  {"thomas": 85, "kim": 50, "anna": 100},
                  {"thomas": 15, "kim": 50, "anna": 1})
    assert got == {"anna"}


@needs_checkout
def test_the_family_share_cut_is_ten_percent(tool: ModuleType) -> None:
    # #1357: a given name written in the family box 7 times in 100
    # (`John`) is kept, one written there exactly 10 in 100 is kept, and
    # one written there 11 in 100 is not
    names = {"zzseven": 9, "zzten": 9, "zzeleven": 9}
    got = _common(tool, {"X": names},
                  {"zzseven": 93, "zzten": 90, "zzeleven": 89},
                  {"zzseven": 7, "zzten": 10, "zzeleven": 11})
    assert got == {"zzseven", "zzten"}


@needs_checkout
def test_a_romanized_surname_a_one_letter_name_and_a_dotted_word_never_enter(
        tool: ModuleType) -> None:
    got = _common(tool, {"X": {"lee": 9, "a": 9, "dr.ahmed": 9, "anna": 9}},
                  {"lee": 100, "a": 100, "dr.ahmed": 100, "anna": 100},
                  exclude=frozenset({"lee"}))
    assert got == {"anna"}


@needs_checkout
def test_top_is_per_country_then_unioned(tool: ModuleType) -> None:
    got = _common(tool, {"X": {"anna": 9, "bea": 5}, "Y": {"carl": 9, "dan": 5}},
                  {"anna": 99, "bea": 99, "carl": 99, "dan": 99}, top=1)
    assert got == {"anna", "carl"}


@needs_checkout
def test_a_tie_is_broken_by_the_word_and_a_rare_word_is_not_ranked(
        tool: ModuleType) -> None:
    uses = {"anna": 99, "bea": 99, "carl": 99}
    assert _common(tool, {"X": {"bea": 5, "anna": 5}}, uses, top=1) == {"anna"}
    assert _common(tool, {"X": {"anna": 2, "carl": 3}}, uses,
                   min_country_uses=3) == {"carl"}


@needs_checkout
def test_the_shipped_given_block_is_what_the_tool_writes(
        tool: ModuleType) -> None:
    from nameparser import locales
    cache = tool.name_usage.cache_dir()
    orcid = cache / "local" / "orcid-researchers" / "raw.jsonl"
    if not orcid.exists():
        pytest.skip("the ORCID local corpus is not cached")
    readings = _cached_pinyin(tool)
    singles = [s for s in locales.ZH.lexicon._sets.surnames if len(s) == 1]
    pinyin = tool.pinyin_surnames(singles, readings)
    words = tool.load_common_given(tool.surname_exclusions(pinyin))
    tool.check_tables(pinyin, words)
    block = tool.render_block("COMMON_GIVEN", words)
    text = Path(_order_names.__file__).read_text(encoding="utf-8")
    assert tool.rewrite(text, "COMMON_GIVEN", block) == text
    assert not words & _order_names.ROMANIZED_SURNAMES
    assert _order_names.COMMON_GIVEN_NAMES == frozenset(words)


# -- the inputs must be whole, and the tables must make sense ----------------


def _plant_orcid(cache: Path, records: list[dict[str, str]], *,
                 count: int | None = None, sha256: str | None = None) -> Path:
    import hashlib
    import json
    folder = cache / "local" / "orcid-researchers"
    folder.mkdir(parents=True)
    body = "".join(json.dumps(r) + "\n" for r in records).encode("utf-8")
    (folder / "raw.jsonl").write_bytes(body)
    (folder / "meta.json").write_text(json.dumps({
        "records": len(records) if count is None else count,
        "sha256": sha256 or hashlib.sha256(body).hexdigest()}),
        encoding="utf-8")
    return folder / "raw.jsonl"


@needs_checkout
def test_whole_orcid_boxes_are_counted(
        tool: ModuleType, monkeypatch: pytest.MonkeyPatch,
        tmp_path_factory: pytest.TempPathFactory) -> None:
    from ._differential_fixtures import own_cache
    cache = own_cache(monkeypatch, tmp_path_factory)
    path = _plant_orcid(cache, [
        {"given": "Anna", "family": "Kim", "country": "KR"},
        {"given": "Łukasz", "family": "Nowak"},
        {"given": "Marie Anne", "family": "Curie", "country": "FR"},
        {"given": "Ivan Petrovich", "family": "Ivanov", "country": "RU"}])
    given, family, first_given = tool.orcid_box_counts(path)
    assert given == {"anna": 1, "lukasz": 1, "marie": 1, "anne": 1,
                     "ivan": 1, "petrovich": 1}
    assert family == {"kim": 1, "nowak": 1, "curie": 1, "ivanov": 1}
    # only the given box's first word is ranked, by the stated country:
    # a second given name or a patronymic typed after it is not
    assert first_given == {"KR": {"anna": 1}, "FR": {"marie": 1},
                           "RU": {"ivan": 1}}


@needs_checkout
@pytest.mark.parametrize("damage, fragment", [
    ({"count": 3}, "holds 2 records, not the 3"),
    ({"sha256": "0" * 64}, "sha256"),
])
def test_a_cut_orcid_corpus_is_refused(
        tool: ModuleType, monkeypatch: pytest.MonkeyPatch,
        tmp_path_factory: pytest.TempPathFactory,
        damage: dict[str, object], fragment: str) -> None:
    from ._differential_fixtures import own_cache
    cache = own_cache(monkeypatch, tmp_path_factory)
    path = _plant_orcid(cache, [{"given": "Anna", "family": "Kim"},
                                {"given": "Jan", "family": "Nowak"}],
                        **damage)  # type: ignore[arg-type]
    with pytest.raises(ValueError, match=fragment):
        tool.orcid_box_counts(path)


@needs_checkout
def test_an_orcid_corpus_without_its_meta_is_refused(
        tool: ModuleType, monkeypatch: pytest.MonkeyPatch,
        tmp_path_factory: pytest.TempPathFactory) -> None:
    from ._differential_fixtures import own_cache
    cache = own_cache(monkeypatch, tmp_path_factory)
    path = _plant_orcid(cache, [{"given": "Anna", "family": "Kim"}])
    (path.parent / "meta.json").unlink()
    with pytest.raises(ValueError, match="meta.json"):
        tool.orcid_box_counts(path)


@needs_checkout
@pytest.mark.parametrize("typed, key", [
    ("Ala'", "ala"), ("“Anna”", "anna"), ("(Anna)", "anna"), ("Anna.", "anna"),
    ("Anna,", "anna"), ("Łukasz", "lukasz"), ("«Anna»", "anna"),
    ("[Anna.]", "anna"), ("Jose\u0301", "jose"), ("Ｊｏｓé", "jose"),
    # the suggester strips the quotes, then the full stop, so a quote
    # before a full stop stays: the tool keys it as the suggester does
    ("'Anna'.", "anna'"),
])
def test_a_word_is_counted_under_the_spelling_the_suggester_looks_up(
        tool: ModuleType, typed: str, key: str) -> None:
    from nameparser import Parser
    from nameparser._suggest import Signal, _name_words, fold, name_votes
    assert tool.spelling(typed) == key
    # the suggester's own path: the words it reads (quotes and brackets
    # stripped, composed), then its lookup's full stops and fold; a
    # comma divides a name there, so the tool's comma strip is its own
    words, _ = _name_words(f"{typed.rstrip(',')} Zzyzx", Parser().lexicon)
    assert fold(words[0].strip(".")) == key
    # and it meets that key: a listed given name written so at the head
    # votes given-first
    if key in _order_names.COMMON_GIVEN_NAMES:
        votes = name_votes(f"{typed.rstrip(',')} Zzyzx", Parser().lexicon)
        assert Signal.GIVEN_NAME in votes


@needs_checkout
def test_a_listed_title_is_refused_and_an_ambiguous_one_is_not(
        tool: ModuleType) -> None:
    titles = tool.listed_titles()
    assert {"prof", "dr", "dra", "lady", "sir"} <= titles
    # a title that may also be a given name stays a candidate
    assert not {"grace", "king", "dean", "princess", "justice"} & titles
    # unless the lexicon lists it as an abbreviation: with its full
    # stop the parse reads it as the title at either end of a name
    assert {"gen", "maj", "brig", "hon"} <= titles
    assert not titles & _order_names.COMMON_GIVEN_NAMES


@needs_checkout
def test_a_listed_suffix_is_refused_ambiguous_or_not(
        tool: ModuleType) -> None:
    # #1357: a post-nominal stands at the end of a name with no comma,
    # where a table word votes that the given name is written last
    suffixes = tool.listed_suffixes()
    assert {"md", "phd", "jr", "mst", "cem"} <= suffixes
    # a suffix that may also be a name is refused too, unlike a title:
    # written in capitals after a name word, the parse reads it as the
    # credential
    assert {"asa", "ace", "ala"} <= suffixes
    assert not suffixes & _order_names.COMMON_GIVEN_NAMES


@needs_checkout
def test_the_table_is_built_without_listed_titles_and_suffixes(
        tool: ModuleType, monkeypatch: pytest.MonkeyPatch,
        tmp_path_factory: pytest.TempPathFactory) -> None:
    # the exclusions as the build applies them, on a planted corpus:
    # each word is typed first in the given box 25 times in one country
    from ._differential_fixtures import own_cache
    cache = own_cache(monkeypatch, tmp_path_factory)
    _plant_orcid(cache, [
        {"given": word, "family": "Zzfam", "country": "BD"}
        for word in ("Md", "Asa", "Prof", "Gen", "Pere", "Zzgiv", "Zzsur")
        for _ in range(25)])
    # `Pere` is refused by the fold: the lexicon lists `père`, and a
    # table word is the folded spelling, so the listed words are folded
    # as the candidates are
    assert tool.load_common_given({"zzsur"}) == {"zzgiv"}


@needs_checkout
def test_the_given_names_exclude_this_runs_surnames(tool: ModuleType) -> None:
    hand = set(_order_names._ZH_OTHER_SPELLINGS + _order_names._KO_SPELLINGS
               + _order_names._VI_SURNAMES)
    assert tool.surname_exclusions({"zzpinyin"}) == hand | {"zzpinyin"}


@needs_checkout
@pytest.mark.parametrize("pinyin, given, fragment", [
    ({f"p{i}" for i in range(149)}, {f"g{i}" for i in range(5000)},
     "149 pinyin surnames, below the floor of 150"),
    ({f"p{i}" for i in range(150)}, {f"g{i}" for i in range(4999)},
     "4999 given names, below the floor of 5000"),
    ({f"p{i}" for i in range(150)}, {"p1"} | {f"g{i}" for i in range(5000)},
     "both tables: p1"),
])
def test_a_table_below_its_floor_or_overlapping_is_refused(
        tool: ModuleType, pinyin: set[str], given: set[str],
        fragment: str) -> None:
    with pytest.raises(ValueError, match=fragment):
        tool.check_tables(pinyin, given)
    tool.check_tables({f"p{i}" for i in range(150)},
                      {f"g{i}" for i in range(5000)})


# -- #1364: the surname table, the given-name recipe's mirror ---------------
def _surnames(tool: ModuleType, given: dict[str, int],
              family: dict[str, int], *,
              exclude: frozenset[str] = frozenset()) -> set[str]:
    # the share and the floor are the tool's own constants, so a test of
    # the cut fails when one moves
    from collections import Counter
    return tool.common_surnames(  # type: ignore[no-any-return]
        Counter(given), Counter(family), min_uses=tool.MIN_SURNAME_USES,
        max_given_share=tool.MAX_GIVEN_SHARE, exclude=set(exclude))


@needs_checkout
def test_the_given_share_cut_is_five_percent(tool: ModuleType) -> None:
    # a surname typed in the given box 10 times in 200 is kept, 11 in
    # 200 is not; the share counts both boxes, as the given-name table's
    # does
    got = _surnames(tool, {"zzfive": 10, "zzsix": 11, "zznone": 0},
                    {"zzfive": 190, "zzsix": 189, "zznone": 100})
    assert got == {"zzfive", "zznone"}


@needs_checkout
def test_the_floor_counts_the_family_box_alone(tool: ModuleType) -> None:
    # 100 uses in the family box is the floor; 99 there and any number in
    # the given box is under it
    got = _surnames(tool, {"zzunder": 1}, {"zzat": 100, "zzunder": 99})
    assert got == {"zzat"}


@needs_checkout
def test_a_one_letter_word_a_dotted_word_and_an_excluded_one_never_enter(
        tool: ModuleType) -> None:
    family = {"z": 500, "zz.qq": 500, "zzgiv": 500, "zzsur": 500}
    got = _surnames(tool, {}, family, exclude=frozenset({"zzgiv"}))
    assert got == {"zzsur"}


@needs_checkout
def test_a_name_piece_is_refused(tool: ModuleType) -> None:
    # typed into the family box beside the surname it belongs to
    pieces = tool.listed_name_pieces()
    assert {"von", "der", "de", "da", "van", "y", "abou", "nee"} <= pieces
    # the Hangul census surnames, which the parse reads by their script
    assert tool.fold("김") in pieces
    assert not pieces & _order_names.COMMON_SURNAMES


@needs_checkout
def test_the_surnames_refuse_every_other_table_and_listed_word(
        tool: ModuleType) -> None:
    got = tool.surname_refusals({"zzpinyin"}, {"zzgiven"})
    assert {"zzpinyin", "zzgiven", "lee", "nguyen", "prof", "phd", "filho",
            "von"} <= got


@needs_checkout
def test_the_surname_table_is_built_without_listed_words(
        tool: ModuleType, monkeypatch: pytest.MonkeyPatch,
        tmp_path_factory: pytest.TempPathFactory) -> None:
    # the refusals as the build applies them, on a planted corpus: each
    # word is typed in the family box 120 times and never in the given
    # box. `Filho` is a listed suffix, `Prof` a listed title, `von` a
    # particle, `кызы` a Turkic
    # patronymic marker refused by its shape, `Zzgiv` a given name of
    # this run
    from ._differential_fixtures import own_cache
    cache = own_cache(monkeypatch, tmp_path_factory)
    _plant_orcid(cache, [
        {"given": "Zzanna", "family": word}
        for word in ("Zzsur", "Filho", "von", "кызы", "Zzgiv", "Prof")
        for _ in range(120)])
    assert tool.load_common_surnames(
        tool.surname_refusals(set(), {"zzgiv"})) == {"zzsur"}


@needs_checkout
def test_the_shipped_surname_table_is_what_the_tool_writes(
        tool: ModuleType) -> None:
    from nameparser import locales
    cache = tool.name_usage.cache_dir()
    orcid = cache / "local" / "orcid-researchers" / "raw.jsonl"
    if not orcid.exists():
        pytest.skip("the ORCID local corpus is not cached")
    readings = _cached_pinyin(tool)
    singles = [s for s in locales.ZH.lexicon._sets.surnames if len(s) == 1]
    pinyin = tool.pinyin_surnames(singles, readings)
    given = tool.load_common_given(tool.surname_exclusions(pinyin))
    words = tool.load_common_surnames(tool.surname_refusals(pinyin, given))
    tool.check_tables(pinyin, given, words)
    block = tool.render_block("COMMON_SURNAMES", words)
    text = Path(_order_names.__file__).read_text(encoding="utf-8")
    assert tool.rewrite(text, "COMMON_SURNAMES", block) == text
    assert _order_names.COMMON_SURNAMES == frozenset(words)
    assert not words & (_order_names.ROMANIZED_SURNAMES
                        | _order_names.COMMON_GIVEN_NAMES)
    assert (_order_names.SURNAMES
            == _order_names.ROMANIZED_SURNAMES | _order_names.COMMON_SURNAMES)


@needs_checkout
@pytest.mark.parametrize("surnames, fragment", [
    ({f"s{i}" for i in range(399)}, "399 surnames, below the floor of 400"),
    ({f"s{i}" for i in range(400)} | {"g1"}, "both tables: g1"),
    ({f"s{i}" for i in range(400)} | {"p1"}, "both tables: p1"),
    # a hand-listed romanized surname is in the surname table too
    ({f"s{i}" for i in range(400)} | {"nguyen"}, "both tables: nguyen"),
])
def test_a_surname_table_below_its_floor_or_overlapping_is_refused(
        tool: ModuleType, surnames: set[str], fragment: str) -> None:
    pinyin = {f"p{i}" for i in range(150)}
    given = {f"g{i}" for i in range(5000)}
    with pytest.raises(ValueError, match=fragment):
        tool.check_tables(pinyin, given, surnames)
    tool.check_tables(pinyin, given, {f"s{i}" for i in range(400)})


def test_the_three_tables_share_no_spelling_and_are_folded() -> None:
    # read from the shipped module, so it runs where the ORCID cache is
    # absent (CI): a hand-listed romanized spelling added later that a
    # generated table holds would vote both ways
    from nameparser._suggest import fold
    surnames = _order_names.COMMON_SURNAMES
    romanized = _order_names.ROMANIZED_SURNAMES
    given = _order_names.COMMON_GIVEN_NAMES
    assert not surnames & romanized
    assert not surnames & given
    assert not romanized & given
    assert all(fold(w) == w and len(w) >= 2 for w in surnames)
    assert _order_names.SURNAMES == surnames | romanized
