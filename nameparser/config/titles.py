# The words, and the vetting notes that stood beside them here, live in
# nameparser/vocab/*.toml -- one entry per word, its readings keyed by
# kind. tools/vocab/build.py compiles them into _compiled.py and runs the
# checks that were import-time asserts here: a title reading with
# addresses = "given" is what puts a word in GIVEN_NAME_TITLES, so the
# subset relation with the title readings holds by construction -- the
# readings, not the TITLES constant, since a word that may also be a
# given name compiles to TITLES_AMBIGUOUS instead (decisions/vocabulary-model), as
# a salutation reading with after_given = true does for AFTER_GIVEN_TITLES.
from nameparser.config import _compiled

GIVEN_NAME_TITLES = _compiled.GIVEN_NAME_TITLES
"""
When these titles appear with a single other name, that name is a given name, e.g.
"Sir John", "Sister Mary", "Dame Mary".
"""

#: **Cannot include things that could also be given names**: a title that
#: may be one ("dean") is in TITLES_AMBIGUOUS instead, a title only inside
#: a title phrase, and listing it here makes it a title everywhere.
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

TITLES_AMBIGUOUS = _compiled.TITLES_AMBIGUOUS
"""
Titles that may be a given name, each a title only inside a title
phrase: "Dean of Students" and "Major General" are titles, where "Dean
Smith" and "Mr Major Smith" read "Dean" and "Major" as the given name.
Kept out of TITLES, where a word is a title wherever it stands, and
derived from a given-name reading on the word.
"""

TITLE_MODIFIERS = _compiled.TITLE_MODIFIERS
"""
Titles that only qualify a head title ("vice", "wing", "grand"): at the
head of a name each is a title only with a head title behind it in its
run, so "Wing Commander Lau" keeps the title where "Wing Lau" reads
"Wing" as the given name. Each is in TITLES, or in TITLES_AMBIGUOUS
where it may be a given name too ("wing"), and is then read everywhere
as at the head of a name.
"""

TITLE_STYLES = _compiled.TITLE_STYLES
"""
Honorific styles ("hon", "excellency", "highness"): one standing before
a title that may be a given name makes it part of a title phrase, as in
"The Hon. Justice Smith". Each is in TITLES, or in TITLES_AMBIGUOUS
where it may be a given name too ("grace", "sheikh").
"""

TITLE_PHRASES = _compiled.TITLE_PHRASES
"""
Two-word title phrases, each a title word and a title it qualifies
("chief justice", "major general"), so a title that may be a given name
reads as a title inside one.
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
           "TITLES_AMBIGUOUS", "TITLE_MODIFIERS", "TITLE_STYLES",
           "TITLE_PHRASES", "FIRST_NAME_TITLES"]
