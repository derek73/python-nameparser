"""Checks on tools/vocab/order_names.py, which writes the romanized
surname table the group suggester reads (``config/_order_names.py``).

The table is read by the suggester only, never by a parse. The tool's
reading and folding are pinned on hand-built input; the shipped block is
held to what the tool writes from the cached Unihan, skipped where the
cache is absent.
"""
from __future__ import annotations

import importlib.util
import sys
import zipfile
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
def test_mandarin_takes_the_first_reading_without_tone(tool: ModuleType) -> None:
    assert tool.read_mandarin("U+912D\tkMandarin\tzhèng\n")["鄭"] == "zheng"
    assert tool.read_mandarin("U+4E50\tkMandarin\tlè yuè\n")["乐"] == "le"


@needs_checkout
def test_pinyin_surnames_drop_one_letter_readings(tool: ModuleType) -> None:
    assert tool.pinyin_surnames(["阿", "鄭"], {"阿": "a", "鄭": "zheng"}) == {"zheng"}


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


@needs_checkout
def test_the_shipped_surname_block_is_what_the_tool_writes(
        tool: ModuleType) -> None:
    from nameparser import locales
    path = tool.name_usage.cache_dir() / tool.UNIHAN_FILE
    if not path.exists():
        pytest.skip("the Unihan cache is absent (tools/zh_surnames.py fetches it)")
    with zipfile.ZipFile(path) as zf:
        mandarin = tool.read_mandarin(
            zf.read(tool.UNIHAN_MEMBER).decode("utf-8"))
    singles = [s for s in locales.ZH.lexicon._sets.surnames if len(s) == 1]
    block = tool.render_block("PINYIN", sorted(
        tool.pinyin_surnames(singles, mandarin)))
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
    cache = tool.name_usage.cache_dir()
    namdict = cache / "nam_dict.txt"
    orcid = cache / "local" / "orcid-researchers" / "raw.jsonl"
    if not (namdict.exists() and orcid.exists()):
        pytest.skip("nam_dict or the ORCID local corpus is not cached")
    words = tool.load_common_given()
    block = tool.render_block("COMMON_GIVEN", words)
    text = Path(_order_names.__file__).read_text(encoding="utf-8")
    assert tool.rewrite(text, "COMMON_GIVEN", block) == text
    assert not words & _order_names.ROMANIZED_SURNAMES
    assert _order_names.COMMON_GIVEN_NAMES == frozenset(words)
