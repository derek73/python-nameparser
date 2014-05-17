# -*- coding: utf-8 -*-
from __future__ import unicode_literals
import re

REGEXES = set([
    ("spaces", re.compile(r"\s+", re.U)),
    ("word", re.compile(r"\w+", re.U)),
    ("mac", re.compile(r'^(ma?c)(\w+)', re.I | re.U)),
    ("initial", re.compile(r'^(\w\.|[A-Z])?$', re.U)),
    ("nickname", re.compile(r'\s*?[\("](.+?)[\)"]', re.U)),
    ("roman_numeral", re.compile(r'^(XC|XL|L?X{0,3})(IX|IV|V?I{0,3})$', re.I | re.U)),
])
"""
All regular expressions used by the parser are precompiled and stored in the config.
"""
