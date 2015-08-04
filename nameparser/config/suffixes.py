# -*- coding: utf-8 -*-
from __future__ import unicode_literals

SUFFIXES = set([
    'esq',
    'esquire',
    'jr',
    'jnr',
    'sr',
    'snr',
    '2',
    'i',
    'ii',
    'iii',
    'iv',
    'v',
    'clu',
    'chfc',
    'cfp',
    'cpa',
    'csm',
    'do',
    'dds',
    'dpm',
    'dmd',
    'md',
    'mba',
    'ma',
    'phd',
    'phr',
    'pmp',
    'mp',
    'qc',
])
"""

Pieces that come at the end of the name but are not last names. These potentially
conflict with initials that might be at the end of the name.

These may be updated in the future because some of them are actually titles that just
come at the end of the name, so semantically this is wrong. Positionally, it's correct.

"""