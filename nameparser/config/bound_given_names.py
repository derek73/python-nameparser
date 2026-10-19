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
