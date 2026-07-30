"""The Chinese locale pack (#271): activates Han segmentation and
ships the surname vocabulary for it. Deliberately does NOT set any
order -- Policy.script_orders already reads wholly-Han names
family-first by default (amendment 2026-07-27); segmentation is the
one Han behavior that must stay opt-in, because a pure-Han string
cannot say whether it is Chinese or Japanese (林 is Lin or Hayashi)
and a zh surname list corrupts Japanese names (高橋一郎 would split
高 + 橋一郎). Applying this pack IS the "my data is Chinese"
declaration. Japanese segmentation is locales.JA's job instead: that
pack activates the same stage for the Japanese repertoire and defers
the division itself to a pluggable segmenter, since no surname list
divides a kanji name.

Data sources: single-character surnames are the top-100 of the 2020
PRC census; traditional-script variant forms are included for names
written in Taiwan/Hong Kong/overseas orthography; two-character
compounds are the Hundred Family Surnames compounds still in modern
use. A coverage floor, not a census roster: extend by giving
parser_for a base whose lexicon already carries the additions --
``parser_for(locales.ZH, base=Parser(lexicon=Lexicon.default().add(
surnames={...})))``. (Adding to the finished parser's lexicon instead
is a silent no-op: Lexicon is frozen, so ``.add`` returns a NEW
lexicon that no parser is holding.)

Declared deviations (spec §2 authoring requirement 3): the pack adds
vocabulary and one union policy field, both self-selecting by script,
so it can only change names containing Han characters -- DEVIATES
below declares exactly that (over-declaring within the script: a Han
name needs an unspaced surname match to actually change, but
per-character scanning is the safe direction).
"""
from __future__ import annotations

from nameparser._lexicon import Lexicon
from nameparser._locale import Locale
from nameparser._policy import PolicyPatch, Script

# 2020 census top-100 plus the annotated additions below, simplified
# forms, census rank order, 10 per row -- append new entries at the
# tail, do not alphabetize (rank order is the only in-file record of
# where the coverage floor sits). Two entries are NOT census rows and
# are called out so the rank-order record stays honest:
#
# * 阎 sits off-rank beside 闫 rather than at the tail, because the two
#   are a reading pair, not a rank neighbour: 闫 is the census row and
#   阎 is the distinct surname sharing its reading (Yan). Keeping them
#   adjacent is worth the one break in rank order.
# * 萧 is at the tail: the mainland census records this surname under
#   the merged 肖 (rank 33 above), but 萧 stays a distinct simplified
#   spelling in current use and both circulate. The traditional form
#   蕭 ships either way, below.
_SINGLE = (
    "王", "李", "张", "刘", "陈", "杨", "黄", "赵", "吴", "周",
    "徐", "孙", "马", "朱", "胡", "郭", "何", "林", "高", "罗",
    "郑", "梁", "谢", "宋", "唐", "许", "韩", "邓", "冯", "曹",
    "彭", "曾", "肖", "田", "董", "潘", "袁", "蔡", "蒋", "余",
    "于", "杜", "叶", "程", "魏", "苏", "吕", "丁", "任", "卢",
    "姚", "沈", "钟", "姜", "崔", "谭", "陆", "范", "汪", "廖",
    "石", "金", "韦", "贾", "夏", "傅", "方", "邹", "熊", "白",
    "孟", "秦", "邱", "侯", "江", "尹", "薛", "闫", "阎", "段",
    "雷", "龙", "黎", "史", "陶", "贺", "毛", "郝", "顾", "龚",
    "邵", "万", "覃", "武", "钱", "戴", "严", "莫", "孔", "向",
    "常", "萧",
)
# Traditional-script forms of the above where the glyph differs. 蕭 is
# the traditional spelling of both 萧 and the merged 肖 (see the note
# above); every other row is a plain 1:1 variant.
_SINGLE_TRADITIONAL = (
    "張", "劉", "陳", "楊", "黃", "趙", "吳", "孫", "馬", "羅",
    "鄭", "謝", "許", "韓", "鄧", "馮", "蕭", "葉", "蘇", "呂",
    "盧", "鍾", "譚", "陸", "韋", "賈", "鄒", "閆", "閻", "龍",
    "賀", "顧", "龔", "萬", "錢", "嚴", "蔣",
)
# Hundred Family Surnames compounds still in modern use, simplified.
_COMPOUND = (
    "欧阳", "司马", "诸葛", "上官", "夏侯", "皇甫", "尉迟", "公孙",
    "长孙", "慕容", "司徒", "司空", "令狐", "宇文", "东方", "独孤",
    "南宫", "西门", "澹台", "淳于", "单于", "申屠", "公羊", "仲孙",
    "轩辕", "呼延", "端木", "百里", "东郭", "闻人", "拓跋", "万俟",
    "夹谷", "太史",
)
# Traditional forms of the compounds where any glyph differs.
_COMPOUND_TRADITIONAL = (
    "歐陽", "司馬", "諸葛", "尉遲", "公孫", "長孫", "東方", "獨孤",
    "南宮", "西門", "澹臺", "單于", "仲孫", "軒轅", "東郭", "聞人",
    "萬俟", "夾谷",
)

# Private: ZH.lexicon.surnames is the supported way to read this, and
# publishing a name later is compatible where un-publishing is not.
_SURNAMES = frozenset(
    _SINGLE + _SINGLE_TRADITIONAL + _COMPOUND + _COMPOUND_TRADITIONAL)

ZH = Locale(
    code="zh",
    lexicon=Lexicon(surnames=_SURNAMES),
    policy=PolicyPatch(segment_scripts=frozenset({Script.HAN})),
)

# Han codepoint spans, kept in sync BY HAND with
# _pipeline/_vocab.py's _SCRIPT_RANGES[Script.HAN] (layering forbids
# a pack importing the pipeline; the sync test in
# tests/v2/test_locales.py pins the equality).
_HAN_RANGES = ((0x3005, 0x3005), (0x3400, 0x4DBF), (0x4E00, 0x9FFF),
               (0xF900, 0xFAFF), (0x20000, 0x323AF))


def DEVIATES(name: str) -> bool:
    """True when this pack may parse `name` differently from the
    default parser (the declared-deviation predicate the
    non-interference gate consumes)."""
    return any(any(lo <= ord(c) <= hi for lo, hi in _HAN_RANGES)
               for c in name)
