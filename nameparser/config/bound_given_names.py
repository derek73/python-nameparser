# The words, and the vetting notes that stood beside them here, live in
# nameparser/vocab/*.toml; tools/vocab/build.py
# compiles them into _compiled.py and runs the checks that were
# import-time asserts here (decisions/vocabulary-model).
from nameparser.config import _compiled

#: Bound Arabic given-name prefixes that attach to the following word to
#: form one given name (e.g. "abdul salam smith" → given name "abdul
#: salam"). They are never standalone names. The join is a group-stage
#: rule on the FIRST non-title piece, so it is not about roles -- it
#: fires whatever name_order later assigns. It reserves a piece for what
#: follows: three pieces that are neither title nor suffix in a main
#: segment -- counting the bound word's OWN piece even where that word is
#: also suffix vocabulary, since it is the piece the rule has claimed
#: rather than one left to spare -- which is why two-word "abdul salam"
#: stays given "abdul" plus
#: family "salam"; only two after a family comma, where the family name
#: is already fixed ("salam, abdul rahman" → given "abdul rahman").
#: Mirrors :py:data:`~nameparser.config.particles.PARTICLES`, which
#: chains onto the piece that follows it.
BOUND_GIVEN_NAMES: frozenset[str] = _compiled.BOUND_GIVEN_NAMES

# Star imports read __all__ and never the module __getattr__ -- see the
# note in prefixes.py. Without it `_compiled`, imported only to re-export
# the constant, is bound by a star import as though it were vocabulary
# (#356).
__all__ = ["BOUND_GIVEN_NAMES"]


# 2.8.1: 3.0 deletes this module (#1007), so each constant is served by
# __getattr__ and warns at the line that reads it, naming the 3.0 call
# that lists the same words (alias_getattr's docstring says how the
# assignment above stays documented). The library reads _compiled, never
# this module. Hidden from mypy as alias_getattr explains; goes in 3.0.
from typing import TYPE_CHECKING  # noqa: E402

from nameparser.config._deprecated import alias_getattr, words_of  # noqa: E402

if not TYPE_CHECKING:
    __getattr__, __dir__ = alias_getattr(__name__, {}, removed={
        "BOUND_GIVEN_NAMES": words_of('kind="bound_given"'),
    }, namespace=globals())
