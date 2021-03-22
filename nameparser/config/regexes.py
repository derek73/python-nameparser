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

REGEXES = [
    ("spaces", re.compile(r"\s+", re.U)),
    ("word", re.compile(r"(\w|\.)+", re.U)),
    ("mac", re.compile(r'^(ma?c)(\w{2,})', re.I | re.U)),
    ("initial", re.compile(r'^(\w\.|[A-Z])?$', re.U)),
    ("double_apostrophe_ASCII", re.compile(r"(?!\w)''(\w[^']*?)''(?!\w)", re.U), 'nickname'),
    ("smart_quote", re.compile(r"(?!\w)“(\w[^”]*?)”(?!\w)", re.U), 'nickname'),
    ("smart_single_quote", re.compile(r"(?!\w)‘(\w[^’]*?)’(?!\w)", re.U), 'nickname'),
    ("grave_accent", re.compile(r'(?!\w)`(\w[^`]*?)`(?!\w)', re.U), 'nickname'),
    ("grave_acute", re.compile(r'(?!\w)`(\w[^´]*?)´(?!\w)', re.U), 'nickname'),
    ("apostrophe_ASCII", re.compile(r"(?!\w)'(\w[^']*?)'(?!\w)", re.U), 'nickname'),
    ("quote_ASCII", re.compile(r'(?!\w)"(\w[^"]*?)"(?!\w)', re.U), 'nickname'),
    ("parenthesis", re.compile(r'(?!\w)\((\w[^)]*?)\)(?!\w)', re.U), 'nickname'),
    ("roman_numeral", re.compile(r'^(X|IX|IV|V?I{0,3})$', re.I | re.U)),
    ("no_vowels",re.compile(r'^[^aeyiuo]+$', re.I | re.U)),
    ("period_not_at_end",re.compile(r'.*\..+$', re.I | re.U)),
    ("emoji",re_emoji),
    ("phd", re.compile(r'\s(ph\.?\s+d\.?)', re.I | re.U)),
    ("nn_sep_safe", re.compile(r'[^ ,]', re.U)),
]
"""
All regular expressions used by the parser are precompiled and stored in the config.

REGEX tuple positions are:
    [0] - name of the pattern, used in code as named attribute
    [1] - compiled pattern
    [2] - (optional) label/tag of the pattern, used in code for 
          filtering patterns
          
All nickname patterns should follow this pattern: 
    (?!\w)leading_delim([^trailing_delim]*?)trailing_delim(?!\w)

Nicknames are assume to be delimited by non-word characters.

"""
