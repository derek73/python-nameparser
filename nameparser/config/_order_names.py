"""Romanized Chinese, Korean and Vietnamese surnames, for the group
suggester only (``Parser.suggest``); no parse reads this module.

A group of Latin-script names whose first word is a listed surname more
often than its last is evidence the group is written family name first.
Every entry is FOLDED (``nameparser._suggest.fold``: lower case, no
diacritics, ``đ`` as ``d``, ``ü`` as ``v``) and has two or more letters.

Sources and licences:

- ``_PINYIN`` (generated below): the Hanyu Pinyin of every
  single-character surname ``locales.ZH`` lists, from the first
  ``kMandarin`` reading in the Unicode Consortium's Unihan database
  (Unicode License v3), tones dropped. See tools/vocab/order_names.py.
- ``_ZH_OTHER_SPELLINGS``, ``_KO_SPELLINGS`` and ``_VI_SURNAMES``:
  hand-curated common romanizations (Wade-Giles, Cantonese, Hokkien and
  Southeast Asian Chinese spellings; Korean spellings beside the Revised
  Romanization; Vietnamese surnames with diacritics folded), assembled
  for this feature on 2026-11-10 and not checked against any published
  ranking or register.

The hand lists are curated, so a word that is also a given name in
another culture may appear in two tables; the table lists spellings,
not languages.
"""
from __future__ import annotations

_ZH_OTHER_SPELLINGS = (
    "chan", "wong", "leung", "cheung", "lau", "ng", "chow", "chau", "tsang",
    "tse", "yip", "lai", "kwok", "fung", "lam", "mak", "mok", "chiu", "ho",
    "hui", "kwan", "tam", "tang", "poon", "siu", "cheng", "yeung", "yuen",
    "choi", "sze", "to", "au", "law", "kong", "lo", "chang", "chen", "lin",
    "huang", "hsu", "hsieh", "tsai", "liu", "chung", "kuo", "hung", "chiang",
    "tseng", "chou", "yeh", "lu", "su", "tu", "wu", "chao", "kao", "chu",
    "hsiao", "fu", "sun", "ma", "kang", "tan", "teo", "lim", "goh", "ong",
    "koh", "tay", "chia", "lee", "yap",
)

_KO_SPELLINGS = (
    "kim", "lee", "yi", "rhee", "rhie", "park", "pak", "bak", "choi", "choe",
    "chae", "jung", "jeong", "chung", "chong", "kang", "cho", "jo", "yoon",
    "yun", "jang", "chang", "lim", "im", "han", "oh", "seo", "suh", "shin",
    "sin", "kwon", "gwon", "hwang", "ahn", "an", "song", "yoo", "yu", "ryu",
    "hong", "jeon", "jun", "chun", "ko", "go", "moon", "mun", "yang", "son",
    "sohn", "bae", "baek", "paik", "heo", "hur", "huh", "nam", "noh", "roh",
    "ha", "kwak", "gwak", "sung", "seong", "cha", "joo", "ju", "woo", "wu",
    "koo", "ku", "min", "jin", "na", "ji", "eom", "um", "uhm", "won",
)

_VI_SURNAMES = (
    "nguyen", "tran", "le", "pham", "hoang", "huynh", "phan", "vu", "vo",
    "dang", "bui", "do", "ho", "ngo", "duong", "ly", "dinh", "trinh", "mai",
    "luong", "lam", "truong", "cao", "luu", "doan", "vuong", "ta", "thai",
    "tang", "quach", "la", "ha", "kieu", "ton",
)

# -- BEGIN generated: PINYIN; edit tools/vocab/order_names.py, not this block --
_PINYIN = (
    "ai", "an", "ao", "ba", "bai", "bao", "bi", "bian",
    "bing", "bo", "cai", "cao", "cen", "ceng", "cha", "chai",
    "chang", "chao", "che", "chen", "cheng", "chi", "chou", "chu",
    "cong", "cui", "dai", "dan", "dang", "deng", "di", "diao",
    "ding", "dong", "dou", "du", "duan", "fan", "fang", "fei",
    "feng", "fu", "gai", "gan", "gao", "ge", "geng", "gong",
    "gu", "guan", "gui", "guo", "han", "hao", "he", "hong",
    "hou", "hu", "hua", "huan", "huang", "hui", "huo", "ji",
    "jia", "jian", "jiang", "jiao", "jie", "jin", "jing", "ju",
    "kang", "ke", "kong", "kou", "kuang", "lai", "lan", "lang",
    "lao", "le", "lei", "leng", "li", "lian", "liang", "liao",
    "lin", "ling", "liu", "long", "lou", "lu", "luan", "luo",
    "lv", "ma", "mai", "mao", "mei", "meng", "mi", "miao",
    "min", "ming", "mo", "mou", "mu", "nan", "ni", "nie",
    "ning", "niu", "nong", "ou", "pan", "pang", "pei", "peng",
    "ping", "pu", "qi", "qian", "qiang", "qiao", "qin", "qiu",
    "qu", "quan", "que", "ran", "rao", "ren", "rong", "ru",
    "ruan", "sang", "sha", "shang", "shao", "she", "shen", "sheng",
    "shi", "shu", "si", "song", "su", "sui", "sun", "suo",
    "tan", "tang", "tao", "teng", "tian", "tong", "tu", "wan",
    "wang", "wei", "wen", "weng", "wu", "xi", "xia", "xiang",
    "xiao", "xie", "xin", "xing", "xiong", "xu", "xuan", "xue",
    "yan", "yang", "yao", "ye", "yi", "yin", "ying", "yong",
    "you", "yu", "yuan", "yue", "yun", "zang", "zhan", "zhang",
    "zhao", "zhen", "zheng", "zhi", "zhong", "zhou", "zhu", "zhuang",
    "zhuo", "zi", "zong", "zou", "zu", "zuo",
)
# -- END generated: PINYIN --

ROMANIZED_SURNAMES: frozenset[str] = frozenset(
    word
    for word in (*_PINYIN, *_ZH_OTHER_SPELLINGS, *_KO_SPELLINGS, *_VI_SURNAMES)
    if len(word) >= 2)
