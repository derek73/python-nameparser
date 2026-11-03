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


# 2.8.1: 3.0 deletes this module (#1007), so each constant is served by
# __getattr__ and warns at the line that reads it, naming what 3.0
# offers in its place (alias_getattr's docstring says how the
# assignment above stays documented). The library reads _compiled, never
# this module. Hidden from mypy as alias_getattr explains; goes in 3.0.
from typing import TYPE_CHECKING  # noqa: E402

from nameparser.config._deprecated import alias_getattr, words_of  # noqa: E402

if not TYPE_CHECKING:
    __getattr__, __dir__ = alias_getattr(__name__, {}, removed={
        "CONJUNCTIONS": words_of('kind="conjunction"'),
        "CONJUNCTIONS_AMBIGUOUS": words_of('kind="conjunction", may_be_initial=True'),
    }, namespace=globals())

# Star imports read __all__ and never the module __getattr__ -- see the
# note in prefixes.py -- so without it a star import would bind none
# of the names served above, silently.
__all__ = ["CONJUNCTIONS", "CONJUNCTIONS_AMBIGUOUS"]
