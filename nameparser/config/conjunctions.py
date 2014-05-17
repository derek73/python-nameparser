# -*- coding: utf-8 -*-
from __future__ import unicode_literals

CONJUNCTIONS = set([
    '&',
    'and',
    'et',
    'e',
    'of',
    'the',
    'und',
    'y',
])
"""
Pieces that should join to their neighboring pieces, e.g. "and", "y" and "&".
"of" and "the" are also include to facilitate joining multiple titles,
e.g. "President of the United States".
"""