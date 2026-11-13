"""Offline checks on tools/zh_surnames.py, which writes the ZH pack's
ranked surname block (#695).

The tool's sources are two downloads and a live SPARQL query, none of
which a test may touch, so these pin the reading and the selection on
hand-built inputs: the failure that matters is a wrong surname shipped
silently -- a placeholder row, a variant no one bears as a surname --
since nothing downstream can tell a shipped entry from a meant one.
"""
from __future__ import annotations

import importlib.util
import sys
import urllib.request
from pathlib import Path
from types import ModuleType

import pytest

from nameparser.locales import zh

_PATH = Path(__file__).parents[2] / "tools" / "zh_surnames.py"


def _load() -> ModuleType:
    spec = importlib.util.spec_from_file_location("zh_surnames", _PATH)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module  # @dataclass looks itself up here
    spec.loader.exec_module(module)
    return module


tool = _load()


@pytest.fixture(autouse=True)
def _no_network(monkeypatch: pytest.MonkeyPatch) -> None:
    def refuse(*args: object, **kwargs: object) -> None:
        raise AssertionError("a test reached the network")
    monkeypatch.setattr(urllib.request, "urlopen", refuse)


# One row per surname per age band, as the Taiwan file has it, with its
# placeholder row and a compatibility ideograph (U+F9A8, which NFC-folds
# to 令) among them.
_MOI = """﻿年度,ranking,lastname,age,人口數
112,1,陳,0-14,1
112,1,陳,15-64,1
112,1,陳,65+,1
112,2,其他,0-14,1
112,3,令,0-14,1
112,4,衛,0-14,1
112,5,張簡,0-14,1
"""


def test_the_taiwan_file_reads_as_single_unified_surnames_in_rank_order() -> None:
    # 其他 ("other") is a placeholder, 張簡 a compound (compounds are
    # curated by hand), and the compatibility ideograph no keyboard
    # produces for a name.
    assert tool.read_moi(_MOI) == ["陳", "衛"]


def test_an_error_page_is_refused_rather_than_read_as_empty() -> None:
    with pytest.raises(ValueError, match="columns"):
        tool.read_moi("<html>Service unavailable</html>")


def _item(qid: str, bearers: int, *labels: str) -> list[dict[str, str]]:
    return [{"item": f"http://www.wikidata.org/entity/{qid}",
             "n": str(bearers), "label": label} for label in labels]


def test_a_label_written_as_surname_x_names_the_character() -> None:
    # 易, 鄺 and 閆 are labelled this way on Wikidata; read literally,
    # they had dropped out of the ranking.
    (item,) = tool.read_wikidata(_item("Q1", 9, "鄺姓", "邝氏"))
    assert item.singles() == {"鄺", "邝"}


def test_items_rank_by_bearers_and_compounds_are_not_singles() -> None:
    rows = (_item("Q1", 5, "卫", "衛") + _item("Q2", 9, "欧阳")
            + _item("Q3", 7, "柯"))
    assert [i.qid for i in tool.read_wikidata(rows)] == ["Q3", "Q1"]


def _forms(surnames: list[object]) -> list[set[str]]:
    return [s.forms for s in surnames]  # type: ignore[attr-defined]


def test_one_surname_in_two_sources_is_one_entry_with_both_ranks() -> None:
    items = tool.read_wikidata(_item("Q1", 5, "卫", "衛"))
    (surname,) = tool.select(["衛"], items, {}, top=10)
    assert surname.forms == {"卫", "衛"}
    assert (surname.moi_rank, surname.wikidata_rank) == (1, 1)


def test_an_item_bridging_two_entries_merges_them_keeping_the_best_ranks() -> None:
    # Two ranked rows that are one surname in two scripts become one
    # entry once an item labelled with both joins them, keeping the
    # better rank of each source.
    items = tool.read_wikidata(_item("Q1", 5, "卫", "衛"))
    surnames = tool.select(["陳", "衛", "卫"], items, {}, top=10)
    (merged,) = [s for s in surnames if "衛" in s.forms]
    assert len(surnames) == 2 and merged.forms == {"卫", "衛"}
    assert (merged.moi_rank, merged.wikidata_rank) == (2, 1)


def test_a_traditional_form_gains_its_one_simplified_variant() -> None:
    assert _forms(tool.select(["關"], [], {"關": {"关"}})) == [{"關", "关"}]


def _label(qid: str, lab: str, lang: str) -> dict[str, str]:
    return {"item": f"http://www.wikidata.org/entity/{qid}", "lab": lab,
            "lang": lang}


def test_a_form_gains_the_simplified_labels_of_the_items_labelled_with_it() -> None:
    variants = tool.read_scripts([
        _label("Q1", "關", "zh-hant"), _label("Q1", "關", "zh"),
        _label("Q1", "关", "zh-hans"), _label("Q1", "关", "zh-cn"),
        # a label written "surname X" names the character
        _label("Q2", "顏姓", "zh-tw"), _label("Q2", "颜姓", "zh-hans")])
    assert variants == {"關": {"关"}, "顏": {"颜"}}
    assert _forms(tool.select(["關"], [], variants)) == [{"關", "关"}]


def test_a_supplementary_plane_variant_does_not_count_against_the_bmp_one() -> None:
    # A label may give 蘭 both 兰 and a GB 18030 extension form; a name
    # is typed with 兰, so 兰 is the one variant.
    variants = tool.read_scripts([
        _label("Q1", "蘭", "zh-hant"), _label("Q1", "兰", "zh-hans"),
        _label("Q1", "\U0002C795", "zh-cn")])
    assert _forms(tool.select(["蘭"], [], variants)) == [{"蘭", "兰"}]


def test_two_simplified_forms_leave_a_form_as_ranked() -> None:
    variants = tool.read_scripts([
        _label("Q1", "乾", "zh-hant"), _label("Q1", "干", "zh-hans"),
        _label("Q2", "乾", "zh-hant"), _label("Q2", "乾", "zh-hans")])
    assert variants == {"乾": {"干"}}
    variants = tool.read_scripts([
        _label("Q1", "乾", "zh-hant"), _label("Q1", "干", "zh-hans"),
        _label("Q2", "乾", "zh-tw"), _label("Q2", "亁", "zh-cn")])
    assert _forms(tool.select(["乾"], [], variants)) == [{"乾"}]


def test_a_simplified_form_never_gains_an_unattested_traditional_one() -> None:
    # 余's traditional forms include 餘, which is no one's surname; only
    # the simplified labels are read, so a form written only in
    # simplified labels gains nothing.
    variants = tool.read_scripts([
        _label("Q1", "余", "zh-hans"), _label("Q1", "余", "zh-cn")])
    assert variants == {}
    assert _forms(tool.select(["余"], [], variants)) == [{"余"}]


def test_the_script_query_asks_each_form_in_each_label_language() -> None:
    query = tool.scripts_query(["關", "王"])
    assert all(f'"{form}"@{lang}' in query for form in "關王"
               for lang in tool.SCRIPT_LANGUAGES)
    assert "wd:Q101352" in query and "wd:Q1093580" in query


def test_each_ranking_contributes_only_its_top() -> None:
    surnames = tool.select(["陳", "林", "詹"], [], {}, top=2)
    assert _forms(surnames) == [{"陳"}, {"林"}]


def test_the_shipped_block_is_what_the_tool_writes_for_its_own_contents() -> None:
    # A hand edit inside the generated block, or a block the tool could
    # not have written, is caught here without the sources. The module
    # read is the one imported, not tool.ZH_MODULE's path into a source
    # tree: Debian's autopkgtest runs these against the installed package.
    text = Path(zh.__file__).read_text(encoding="utf-8")
    assert tool.rewrite(text, tool.render(list(zh._SINGLE_RANKED))) == text


def test_the_block_repeats_no_census_row_and_holds_only_single_ideographs() -> None:
    by_hand = set(zh._SINGLE) | set(zh._SINGLE_TRADITIONAL)
    assert tool.listed_by_hand(Path(zh.__file__).read_text(encoding="utf-8")) == by_hand
    assert not by_hand & set(zh._SINGLE_RANKED)
    assert all(tool.is_han(c) for c in zh._SINGLE_RANKED)
