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

# Without __all__ a star import binds any import here not written with
# a leading underscore, as though it were vocabulary (#356); the note in
# particles.py says more.
__all__ = ["GIVEN_NAME_ABBREVIATIONS"]
