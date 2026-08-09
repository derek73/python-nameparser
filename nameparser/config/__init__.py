"""v1 import-path preservation (migration spec §3): the Constants shim
lives in nameparser._config_shim.

Two unrelated things share this package. The names re-exported below --
``Constants``, ``CONSTANTS``, ``SetManager``, ``TupleManager``,
``RegexTupleManager`` -- are v1 compatibility surface, and go with the
rest of the facade in 3.0. The vocabulary data modules beside them
(:mod:`~nameparser.config.titles`, :mod:`~nameparser.config.particles`,
...) are not compatibility surface at all: they are the word lists the
2.0 :class:`~nameparser.Lexicon` is built from, they are named for its
fields since 2.2 (#293), and its documentation cross-references them.

``RegexTupleManager`` is re-exported unchanged from the shim purely for
pickle compatibility: a v1.4 ``Constants`` blob's ``regexes`` field was
pickled as ``nameparser.config.RegexTupleManager(...)``, and unpickling
resolves and reconstructs that nested object before
``Constants.__setstate__`` ever runs. Without this name, loading such a
blob raises ``AttributeError`` looking up the class, not a clean
compatibility failure.
"""
# Maintainer note, deliberately outside the docstring: the docstring
# above no longer says "this package is deleted in 3.0", which the
# migration spec's §3 list asserts while enumerating only the shim
# names in its parenthetical. Whether the DATA modules keep this
# package as their home in 3.0 or move under the core is an open
# decision, not something to settle in a published docstring -- and it
# now has a consequence, since Lexicon's public field docs
# cross-reference nameparser.config.particles et al. Resolve it when
# 3.0 is planned; until then this docstring claims only what is
# settled, which is that the re-exports below go.
from nameparser._config_shim import CONSTANTS as CONSTANTS
from nameparser._config_shim import Constants as Constants
from nameparser._config_shim import RegexTupleManager as RegexTupleManager
from nameparser._config_shim import SetManager as SetManager
from nameparser._config_shim import TupleManager as TupleManager

__all__ = ["CONSTANTS", "Constants", "RegexTupleManager", "SetManager", "TupleManager"]
