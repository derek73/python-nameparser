# The words, and the vetting notes that stood beside them here, live in
# nameparser/vocab/*.toml: a conjunction reading with may_be_initial = true is
# what puts a word in CONJUNCTIONS_AMBIGUOUS, so that set is a subset by
# construction, and tools/vocab/build.py refuses the flag on anything but
# a CASED single letter -- the fork reads only a cased one-letter token,
# so a caseless letter (Arabic و) or a longer entry would be inert. That
# guards the SHIPPED data only: the pair is deliberately absent from
# Lexicon's subset checks, so a CALLER'S orphan is never rejected -- it
# is inert instead, the classify fork and its emitter both requiring the
# base entry before they read the marker (see decisions/P8, the
# 2026-09-13 entries).
from nameparser.config import _compiled

CONJUNCTIONS = _compiled.CONJUNCTIONS
"""
Pieces that should join to their neighboring pieces, e.g. "and", "y" and "&".
"of" and "the" are also include to facilitate joining multiple titles,
e.g. "President of the United States".
"""

CONJUNCTIONS_AMBIGUOUS = _compiled.CONJUNCTIONS_AMBIGUOUS
"""
Single-letter entries of :data:`CONJUNCTIONS` that read as an initial,
not a connective, in a name written wholly in one case.
"""

