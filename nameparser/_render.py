"""Rendering for the 2.0 API: ParsedName -> display strings.

Layering: imports nameparser._types, and nameparser._lexicon only for
Lexicon.default() when capitalized() receives lexicon=None (enforced by
tests/v2/test_layering.py). Parsing code never imports this module;
ParsedName's rendering methods delegate here via call-time imports.
"""
from __future__ import annotations

import re

_SPACES = re.compile(r"\s+")
_SPACE_BEFORE_COMMA = re.compile(r"\s+,")
_COMMA_CHAR = re.compile(r"[,،，]")  # ASCII, Arabic, fullwidth


def _collapse(rendered: str) -> str:
    """The #254 collapse, normative (core spec §5b): empty fields
    substitute '' and every artifact of that is removed -- dangling
    empty-nickname wrappers, space runs, space-before-comma, one
    trailing comma character (any script), leading/trailing ', '
    debris."""
    rendered = (rendered.replace(" ()", "")
                        .replace(" ''", "")
                        .replace(' ""', ""))
    rendered = _SPACE_BEFORE_COMMA.sub(",", rendered)
    rendered = _SPACES.sub(" ", rendered.strip())
    if rendered and _COMMA_CHAR.fullmatch(rendered[-1]):
        rendered = rendered[:-1]
    return rendered.strip(", ")
