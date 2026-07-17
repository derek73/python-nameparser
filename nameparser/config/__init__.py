"""v1 import-path preservation (migration spec §3): the Constants shim
lives in nameparser._config_shim. The vocabulary data modules in this
package (titles, suffixes, ...) remain the single source through 2.x.
This package is deleted in 3.0.

``RegexTupleManager`` is re-exported unchanged from the shim purely for
pickle compatibility: a v1.4 ``Constants`` blob's ``regexes`` field was
pickled as ``nameparser.config.RegexTupleManager(...)``, and unpickling
resolves and reconstructs that nested object before
``Constants.__setstate__`` ever runs. Without this name, loading such a
blob raises ``AttributeError`` looking up the class, not a clean
compatibility failure.
"""
from nameparser._config_shim import CONSTANTS as CONSTANTS
from nameparser._config_shim import Constants as Constants
from nameparser._config_shim import RegexTupleManager as RegexTupleManager
from nameparser._config_shim import SetManager as SetManager
from nameparser._config_shim import TupleManager as TupleManager

__all__ = ["CONSTANTS", "Constants", "RegexTupleManager", "SetManager", "TupleManager"]
