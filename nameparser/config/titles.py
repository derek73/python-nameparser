# The words, and the vetting notes that stood beside them here, live in
# nameparser/vocab/*.toml -- one entry per word, its readings keyed by
# kind. tools/vocab/build.py compiles them into _compiled.py and runs the
# checks that were import-time asserts here: a title reading with
# addresses = "given" is what puts a word in GIVEN_NAME_TITLES, so the
# subset relation holds by construction (decisions/vocabulary-model), as
# a salutation reading with after_given = true does for AFTER_GIVEN_TITLES.
from nameparser.config import _compiled

GIVEN_NAME_TITLES = _compiled.GIVEN_NAME_TITLES
"""
When these titles appear with a single other name, that name is a given name, e.g.
"Sir John", "Sister Mary", "Queen Elizabeth".
"""

#: **Cannot include things that could also be given names**, e.g. "dean".
#: Many of these from wikipedia: https://en.wikipedia.org/wiki/Title.
#: The parser recognizes chains of these including conjunctions allowing
#: recognition titles like "Deputy Secretary of State".
TITLES = _compiled.TITLES

AFTER_GIVEN_TITLES = _compiled.AFTER_GIVEN_TITLES
"""
Salutations read as a title where one ends the given part after a family
comma, written without a period: "Doe, Jane Mrs". A subset of TITLES. A
salutation that is also borne as a name (goodman, master, herr) is left
out, so "Doe, John Goodman" keeps middle "Goodman".
"""


# 1.x name, deprecated in 2.2 and removed in 3.0 (#293). Unlike the
# module moves in #293, the constant did not change module, so this
# aliases a name to one of this module's own globals: a module
# __getattr__ runs only once the body has finished and the module is in
# sys.modules, so the lookup resolves rather than recursing.
from typing import TYPE_CHECKING  # noqa: E402

from nameparser.config._deprecated import alias_getattr  # noqa: E402

# Declared for the type checker, served by __getattr__ at runtime. The
# split is what keeps mypy checking this module's LIVE names: an
# assigned module __getattr__ answers every missing attribute, so a
# plain assignment here made `from ... import TITLE` type-check clean.
# See alias_getattr's docstring. Both branches go in 3.0.
if TYPE_CHECKING:
    FIRST_NAME_TITLES: frozenset[str]
else:
    __getattr__, __dir__ = alias_getattr(__name__, {
        "FIRST_NAME_TITLES": (
            "nameparser.config.titles", "GIVEN_NAME_TITLES"),
    })

# Star imports read __all__ and never the module __getattr__ -- see the
# note in prefixes.py. This module keeps its live constants, so they are
# listed too: without __all__ a star import bound them and dropped the
# retired name silently; with a PARTIAL __all__ it would bind the
# retired name and drop the live ones instead.
# Source order, not alphabetical -- see the note in suffixes.py.
__all__ = ["GIVEN_NAME_TITLES", "TITLES", "AFTER_GIVEN_TITLES",
           "FIRST_NAME_TITLES"]
