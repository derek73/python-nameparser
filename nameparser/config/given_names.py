# The words, and the vetting notes that stand beside them, live in
# nameparser/vocab/*.toml; tools/vocab/build.py compiles them into
# _compiled.py (decisions/vocabulary-model).
from nameparser.config import _compiled

#: Given names written short ("chas" for Charles, "wm" for William,
#: Filipino "ma" for María): a word with a ``given`` reading whose
#: ``same_as`` is the full name. Period-marked and opening the part of
#: the name that carries the given name, one reads as that given name,
#: where an unlisted abbreviation there reads as a title by its shape
#: alone ("Chas. Smith" reads given "Chas.", "Xyz. Smith" title
#: "Xyz."). A listed title outranks it, and anywhere else the word is
#: read as it would be unlisted.
GIVEN_NAME_ABBREVIATIONS: frozenset[str] = _compiled.GIVEN_NAME_ABBREVIATIONS

# Star imports read __all__ and never the module __getattr__ -- see the
# note in prefixes.py.
__all__ = ["GIVEN_NAME_ABBREVIATIONS"]


# 2.8.1: 3.0 deletes this module (#1007), so each constant is served by
# __getattr__ and warns at the line that reads it, naming what 3.0
# offers in its place (alias_getattr's docstring says how the
# assignment above stays documented). The library reads _compiled, never
# this module. Hidden from mypy as alias_getattr explains; goes in 3.0.
from typing import TYPE_CHECKING  # noqa: E402

from nameparser.config._deprecated import alias_getattr, words_of  # noqa: E402

if not TYPE_CHECKING:
    __getattr__, __dir__ = alias_getattr(__name__, {}, removed={
        "GIVEN_NAME_ABBREVIATIONS": words_of('kind="given"', "the given names whose reading carries same_as"),
    }, namespace=globals())
