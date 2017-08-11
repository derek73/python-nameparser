# -*- coding: utf-8 -*-
from __future__ import unicode_literals
import re

# emoji regex from https://stackoverflow.com/questions/26568722/remove-unicode-emoji-using-re-in-python
try:
    # Wide UCS-4 build
    re_emoji = re.compile('['
        '\U0001F300-\U0001F64F'
        '\U0001F680-\U0001F6FF'
        '\u2600-\u26FF\u2700-\u27BF]+', 
        re.UNICODE)
except re.error:
    # Narrow UCS-2 build
    re_emoji = re.compile('('
        '\ud83c[\udf00-\udfff]|'
        '\ud83d[\udc00-\ude4f\ude80-\udeff]|'
        '[\u2600-\u26FF\u2700-\u27BF])+', 
        re.UNICODE)

REGEXES = set([
    ("spaces", re.compile(r"\s+", re.U)),
    ("word", re.compile(r"(\w|\.)+", re.U)),
    ("mac", re.compile(r'^(ma?c)(\w{2,})', re.I | re.U)),
    ("initial", re.compile(r'^(\w\.|[A-Z])?$', re.U)),
    ("nickname", re.compile(r'\s*?[\("](.+?)[\)"]', re.U)),
    ("roman_numeral", re.compile(r'^(X|IX|IV|V?I{0,3})$', re.I | re.U)),
    ("no_vowels",re.compile(r'^[^aeyiuo]+$', re.I | re.U)),
    ("period_not_at_end",re.compile(r'.*\..+$', re.I | re.U)),
    ("emoji",re_emoji),
])
"""
All regular expressions used by the parser are precompiled and stored in the config.
"""
