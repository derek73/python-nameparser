"""Shared vocabulary predicates for pipeline stages.

Text-level tests used by more than one stage; token/piece-level
predicates live with their stage. All take normalized-or-raw text
explicitly -- no state.

Layering: imports _lexicon and _types only.
"""
from __future__ import annotations

import re

from nameparser._lexicon import Lexicon, _normalize

# Ported verbatim from v1 (nameparser/config/regexes.py "initial") minus
# its empty-string alternative -- WorkToken text is never empty. Kept in
# sync by hand; layering forbids importing the config package here.
_INITIAL = re.compile(r"^(\w\.|[A-Z])$")


def is_initial(text: str) -> bool:
    """'A.' / 'j.' / bare capital -- v1's is_an_initial."""
    return bool(_INITIAL.fullmatch(text))


def is_suffix_strict(text: str, lexicon: Lexicon) -> bool:
    """v1's is_suffix: suffix vocabulary with the initial veto ('V.' in
    'John V. Smith' is a middle initial, not roman five); ambiguous
    acronyms count only when written with periods ('M.A.' yes, 'Ma' no).
    """
    n = _normalize(text)
    if "." in text and n in lexicon.suffix_acronyms_ambiguous:
        return True
    if is_initial(text):
        return False
    # ambiguous subset excluded from the plain test (see _classify)
    return (n in lexicon.suffix_acronyms
            and n not in lexicon.suffix_acronyms_ambiguous) \
        or n in lexicon.suffix_words


def is_suffix_lenient(text: str, lexicon: Lexicon) -> bool:
    """v1's is_suffix_lenient: suffix_words accepted unconditionally,
    bypassing the initial veto -- only safe in unambiguous positions
    (after a comma)."""
    return _normalize(text) in lexicon.suffix_words or \
        is_suffix_strict(text, lexicon)
