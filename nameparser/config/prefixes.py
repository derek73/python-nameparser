# -*- coding: utf-8 -*-
from __future__ import unicode_literals

#: Name pieces that appear before a last name. Prefixes join to the piece
#: that follows them to make one new piece. They can be chained together, e.g
#: "von der" and "de la". Because they only appear in middle or last names,
#: they also signify that all following name pieces should be in the same name
#: part, for example, "von" will be joined to all following pieces that are not
#: prefixes or suffixes, allowing recognition of double last names when they
#: appear after a prefixes. So in "pennie von bergen wessels MD", "von" will
#: join with all following name pieces until the suffix "MD", resulting in the
#: correct parsing of the last name "von bergen wessels".
PREFIXES = set([
    'abu',
    'al',
    'bin',
    'bon',
    'da',
    'dal',
    'de',
    'de\'',
    'degli',
    'dei',
    'del',
    'dela',
    'della',
    'delle',
    'delli',
    'dello',
    'der',
    'di',
    'dí',
    'do',
    'dos',
    'du',
    'ibn',
    'la',
    'le',
    'mac',
    'mc',
    'san',
    'santa',
    'st',
    'ste',
    'van',
    'vander',
    'vel',
    'von',
    'vom',
])
