# -*- coding: utf-8 -*-
from __future__ import unicode_literals
import re

REGEXES = set([
    ("spaces", re.compile(r"\s+", re.U)),
    ("word", re.compile(r"(\w|\.)+", re.U)),
    ("mac", re.compile(r'^(ma?c)(\w+)', re.I | re.U)),
    ("initial", re.compile(r'^(\w\.|[A-Z])?$', re.U)),
    ("nickname", re.compile(r'\s*?[\("](.+?)[\)"]', re.U)),
    ("roman_numeral", re.compile(r'^(X|IX|IV|V?I{0,3})$', re.I | re.U)),
    ("no_vowels",re.compile(r'^[^aeyiuo]+$', re.I | re.U)),
    ("period_not_at_end",re.compile(r'.*\..+$', re.I | re.U)),
])
"""
All regular expressions used by the parser are precompiled and stored in the config.
"""
