"""Rendering for the 2.0 API: ParsedName -> display strings.

Layering: imports nameparser._types, and nameparser._lexicon only for
Lexicon.default() when capitalized() receives lexicon=None (enforced by
tests/v2/test_layering.py). Parsing code never imports this module;
ParsedName's rendering methods delegate here via call-time imports.
"""
from __future__ import annotations

import re

from nameparser._types import ParsedName, Role

_SPACES = re.compile(r"\s+")
_SPACE_BEFORE_COMMA = re.compile(r"\s+,")
_COMMA_CHAR = re.compile(r"[,،，]")  # ASCII, Arabic, fullwidth

#: str.format keys render() accepts: the seven role fields in canonical
#: order (derived from Role -- never restated) plus the derived views.
_DERIVED_VIEWS = ("family_base", "family_particles", "surnames", "given_names")
_RENDER_KEYS = tuple(r.value for r in Role) + _DERIVED_VIEWS


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


def render(name: ParsedName, spec: str) -> str:
    """Fill the str.format spec from the seven role fields and the
    derived views (empty fields substitute ''), then apply the #254
    collapse. Unknown keys raise KeyError naming the valid fields."""
    values = {key: getattr(name, key) for key in _RENDER_KEYS}
    try:
        rendered = spec.format(**values)
    except KeyError as exc:
        raise KeyError(
            f"unknown render field {exc.args[0]!r}; valid fields: "
            f"{', '.join(_RENDER_KEYS)}"
        ) from None
    return _collapse(rendered)
