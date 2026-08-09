"""Deprecated alias module: the particle vocabulary moved to
:mod:`nameparser.config.particles` in 2.2 (#293), where the constant
names match the :class:`~nameparser.Lexicon` fields they feed. Reading
a name from here warns and returns the constant from its new home; this
module is deleted in 3.0.
"""
from nameparser.config._deprecated import alias_getattr

__getattr__, __dir__ = alias_getattr(__name__, {
    "PREFIXES": ("nameparser.config.particles", "PARTICLES"),
    "NON_FIRST_NAME_PREFIXES": (
        "nameparser.config.particles", "NON_GIVEN_NAME_PARTICLES"),
})
