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
