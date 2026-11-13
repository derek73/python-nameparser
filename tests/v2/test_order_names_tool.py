"""Checks on tools/vocab/order_names.py, which writes the romanized
surname table the group suggester reads (``config/_order_names.py``).

The table is read by the suggester only, never by a parse. The tool's
reading and folding are pinned on hand-built input; the shipped block is
held to what the tool writes from its cached Wikidata answer, skipped
where the cache is absent.
"""
from __future__ import annotations

import importlib.util
import sys
import json
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
    monkeypatch.setattr(tool.name_usage, "_sparql_csv", sparql_csv)
    assert tool.load_pinyin(["鄭"], False) == {"鄭": {"zheng"}}
    assert len(asked) == 2
    tool.load_pinyin(["鄭"], False)
    assert len(asked) == 2
    tool.load_pinyin(["鄭"], True)
    tool.load_pinyin(["鄭", "王"], False)
    assert len(asked) == 6
    assert (cache / tool.PINYIN_FILE).exists()


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
    monkeypatch.setattr(tool.name_usage, "_sparql_csv", sparql_csv)
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


def _namdict(tool: ModuleType, countries: dict[str, dict[str, int]]) -> object:
    """A NamDict whose only entries are ``{country: {name: band}}``."""
    names: dict[str, list[tuple[str, dict[str, int]]]] = {}
    for country, bands in countries.items():
        for name, band in bands.items():
            names.setdefault(name, []).append((name, {country: band}))
    return tool.name_usage.NamDict(
        countries=list(countries), names=names, short_for={})


@needs_checkout
def test_a_name_mostly_written_as_a_family_name_is_dropped(
        tool: ModuleType) -> None:
    nd = _namdict(tool, {"X": {"thomas": 9, "kim": 9, "anna": 9}})
    from collections import Counter
    given = Counter({"thomas": 90, "kim": 50, "anna": 100})
    family = Counter({"thomas": 10, "kim": 50, "anna": 1})
    got = tool.common_given(nd, given, family, top=10, max_family_share=0.05,
                            min_uses=20, exclude=set())
    assert got == {"anna"}


@needs_checkout
def test_a_romanized_surname_and_a_one_letter_name_never_enter(
        tool: ModuleType) -> None:
    from collections import Counter
    nd = _namdict(tool, {"X": {"lee": 9, "a": 9, "anna": 9}})
    given = Counter({"lee": 100, "a": 100, "anna": 100})
    got = tool.common_given(nd, given, Counter(), top=10, max_family_share=0.05,
                            min_uses=20, exclude={"lee"})
    assert got == {"anna"}


@needs_checkout
def test_top_is_per_country_then_unioned(tool: ModuleType) -> None:
    from collections import Counter
    nd = _namdict(tool, {"X": {"anna": 9, "bea": 5}, "Y": {"carl": 9, "dan": 5}})
    given = Counter({"anna": 99, "bea": 99, "carl": 99, "dan": 99})
    got = tool.common_given(nd, given, Counter(), top=1, max_family_share=0.05,
                            min_uses=20, exclude=set())
    assert got == {"anna", "carl"}


@needs_checkout
def test_the_shipped_given_block_is_what_the_tool_writes(
        tool: ModuleType) -> None:
    from nameparser import locales
    cache = tool.name_usage.cache_dir()
    namdict = cache / "nam_dict.txt"
    orcid = cache / "local" / "orcid-researchers" / "raw.jsonl"
    if not (namdict.exists() and orcid.exists()):
        pytest.skip("nam_dict or the ORCID local corpus is not cached")
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
    path = _plant_orcid(cache, [{"given": "Anna", "family": "Kim"},
                                {"given": "Łukasz", "family": "Nowak"}])
    given, family = tool.orcid_box_counts(path)
    assert given == {"anna": 1, "lukasz": 1}
    assert family == {"kim": 1, "nowak": 1}


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
def test_nam_dict_is_read_checked_and_refused_when_absent_or_cut(
        tool: ModuleType, monkeypatch: pytest.MonkeyPatch,
        tmp_path_factory: pytest.TempPathFactory) -> None:
    from ._differential_fixtures import own_cache
    cache = own_cache(monkeypatch, tmp_path_factory)
    with pytest.raises(ValueError, match="nam_dict.txt is not cached"):
        tool.load_namdict()
    (cache / "nam_dict.txt").write_text("cut\n", encoding="utf-8")
    with pytest.raises(ValueError, match="sha256"):
        tool.load_namdict()


@needs_checkout
def test_the_given_names_exclude_this_runs_surnames(tool: ModuleType) -> None:
    hand = set(_order_names._ZH_OTHER_SPELLINGS + _order_names._KO_SPELLINGS
               + _order_names._VI_SURNAMES)
    assert tool.surname_exclusions({"zzpinyin"}) == hand | {"zzpinyin"}


@needs_checkout
@pytest.mark.parametrize("pinyin, given, fragment", [
    ({f"p{i}" for i in range(149)}, {f"g{i}" for i in range(3000)},
     "149 pinyin surnames, below the floor of 150"),
    ({f"p{i}" for i in range(150)}, {f"g{i}" for i in range(2999)},
     "2999 given names, below the floor of 3000"),
    ({f"p{i}" for i in range(150)}, {"p1"} | {f"g{i}" for i in range(3000)},
     "both tables: p1"),
])
def test_a_table_below_its_floor_or_overlapping_is_refused(
        tool: ModuleType, pinyin: set[str], given: set[str],
        fragment: str) -> None:
    with pytest.raises(ValueError, match=fragment):
        tool.check_tables(pinyin, given)
    tool.check_tables({f"p{i}" for i in range(150)},
                      {f"g{i}" for i in range(3000)})
