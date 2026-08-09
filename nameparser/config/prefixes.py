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

# `from nameparser.config.prefixes import *` consults __all__ and NOTHING
# else -- a module __getattr__ is invisible to it (PEP 562 defines the
# hook for attribute access; star imports without __all__ read the
# module's __dict__ directly). Without this, the one 1.x import form the
# bridge did not cover failed in the mode the bridge exists to prevent:
# no warning, no AttributeError, just a NameError later at an unrelated
# line -- plus `alias_getattr` bound into the caller's namespace. Listing
# the retired names here routes each through __getattr__, so a star
# import warns per name exactly as an attribute read does.
__all__ = ["NON_FIRST_NAME_PREFIXES", "PREFIXES"]  # noqa: F822
