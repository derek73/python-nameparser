"""Deprecated alias module: the bound given-name vocabulary moved to
:mod:`nameparser.config.bound_given_names` in 2.2 (#293), where the
constant name matches the :class:`~nameparser.Lexicon` field it feeds.
Reading a name from here warns and returns the constant from its new
home; this module is deleted in 3.0.
"""
from nameparser.config._deprecated import alias_getattr

__getattr__, __dir__ = alias_getattr(__name__, {
    "BOUND_FIRST_NAMES": (
        "nameparser.config.bound_given_names", "BOUND_GIVEN_NAMES"),
})

# Star imports read __all__ and never the module __getattr__ -- see the
# note in prefixes.py for what that cost before this line existed.
__all__ = ["BOUND_FIRST_NAMES"]  # noqa: F822
