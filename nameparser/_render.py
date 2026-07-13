"""Rendering for the 2.0 API: ParsedName -> display strings.

Layering: imports nameparser._types, and nameparser._lexicon for
Lexicon.default() (capitalized() with lexicon=None) and _normalize
(enforced by tests/v2/test_layering.py). Parsing code never imports
this module; ParsedName's rendering methods delegate here via
call-time imports.

Malformed str.format specs beyond unknown keys (positional fields,
bad conversions) surface the raw str.format error; only unknown KEYS
get the enriched KeyError.
"""
from __future__ import annotations

import re

from nameparser._lexicon import Lexicon, _normalize
from nameparser._types import Ambiguity, ParsedName, Role, Token

_SPACES = re.compile(r"\s+")
_SPACE_BEFORE_COMMA = re.compile(r"\s+,")
_COMMA_CHAR = re.compile(r"[,،，]")  # ASCII, Arabic, fullwidth
_MAC = re.compile(r"^(ma?c)(\w{2,})", re.IGNORECASE)
_WORD = re.compile(r"(\w|\.)+")

#: str.format keys render() accepts: the seven role fields in canonical
#: order (derived from Role -- never restated) plus the derived views.
_DERIVED_VIEWS = ("family_base", "family_particles", "surnames", "given_names")
_RENDER_KEYS = tuple(r.value for r in Role) + _DERIVED_VIEWS

#: str.format keys initials() accepts: the three name-bearing roles.
_INITIALS_KEYS = (Role.GIVEN.value, Role.MIDDLE.value, Role.FAMILY.value)

#: Tags whose tokens contribute no initial outside the given group.
#: Not STABLE_TAGS -- that also contains "initial", which must contribute.
_SKIP_TAGS = frozenset({"particle", "conjunction"})


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
    if not isinstance(spec, str):
        raise TypeError(f"spec must be a str, got {spec!r}")
    values = {key: getattr(name, key) for key in _RENDER_KEYS}
    try:
        rendered = spec.format(**values)
    except KeyError as exc:
        raise KeyError(
            f"unknown render field {exc.args[0]!r}; valid fields: "
            f"{', '.join(_RENDER_KEYS)}"
        ) from None
    return _collapse(rendered)


def initials(name: ParsedName, spec: str, delimiter: str, separator: str) -> str:
    """First letter of each contributing token per group, v1 semantics:
    delimiter follows each initial, separator sits between initials
    within a group. Tokens tagged particle/conjunction contribute no
    initial in middle/family (given-name tokens always contribute);
    tags come from the pipeline -- hand-built untagged tokens all
    contribute. Valid spec keys: given, middle, family."""
    for arg_name, arg in (("spec", spec), ("delimiter", delimiter),
                          ("separator", separator)):
        if not isinstance(arg, str):
            raise TypeError(f"{arg_name} must be a str, got {arg!r}")
    values: dict[str, str] = {}
    for key in _INITIALS_KEYS:
        role = Role(key)
        tokens = name.tokens_for(role)
        if role is not Role.GIVEN:
            tokens = tuple(t for t in tokens
                           if not (_SKIP_TAGS & t.tags))
        letters = [t.text[0] for t in tokens]
        values[key] = ((delimiter + separator).join(letters) + delimiter
                       if letters else "")
    try:
        rendered = spec.format(**values)
    except KeyError as exc:
        raise KeyError(
            f"unknown initials field {exc.args[0]!r}; valid fields: "
            f"{', '.join(_INITIALS_KEYS)}"
        ) from None
    return _collapse(rendered)


def _cap_word(word: str, role: Role, lex: Lexicon) -> str:
    # v1 cap_word order: particle/conjunction rule first, then the
    # exceptions map, then Mac/Mc, then str.capitalize
    normalized = _normalize(word)
    if (normalized in lex.particles
            and role in (Role.MIDDLE, Role.FAMILY)) \
            or normalized in lex.conjunctions:
        return word.lower()
    exception = lex.capitalization_exceptions_map.get(normalized)
    if exception is not None:
        return exception
    if _MAC.match(word):
        return _MAC.sub(
            lambda m: m.group(1).capitalize() + m.group(2).capitalize(),
            word)
    return word.capitalize()


def _cap_text(text: str, role: Role, lex: Lexicon) -> str:
    # word-by-word within the token text: hyphenated names capitalize
    # both sides ("macdole-eisenhower" -> "MacDole-Eisenhower")
    return _WORD.sub(lambda m: _cap_word(m.group(0), role, lex), text)


def capitalized(name: ParsedName, lexicon: Lexicon | None, *,
                force: bool) -> ParsedName:
    """Case-fixing transform -> new ParsedName, same spans, new token
    texts (core spec §5b). Gate (v1 parity): only single-case input is
    touched unless force=True; the gate reads the joined token texts.
    Idempotent: without force, a capitalized result is mixed-case and
    the gate returns it unchanged; with force, every _cap_word rule is
    a fixpoint on its own output."""
    if lexicon is not None and not isinstance(lexicon, Lexicon):
        # eager, before the gate: a garbage argument must not become a
        # silent no-op on mixed-case input or a deep AttributeError
        raise TypeError(f"lexicon must be a Lexicon or None, got {lexicon!r}")
    lex = Lexicon.default() if lexicon is None else lexicon
    joined = " ".join(t.text for t in name.tokens)
    if not force and joined not in (joined.upper(), joined.lower()):
        return name
    new_tokens = tuple(
        Token(_cap_text(t.text, t.role, lex), t.span, t.role, t.tags)
        for t in name.tokens)
    # equal tokens (possible only for synthetic span=None duplicates)
    # collapse to one mapping entry -- benign: the rebuilt ambiguity
    # references an equal token, so the subset invariant still holds
    replacement = dict(zip(name.tokens, new_tokens))
    new_ambiguities = tuple(
        Ambiguity(a.kind, a.detail,
                  tuple(replacement[t] for t in a.tokens))
        for a in name.ambiguities)
    return ParsedName(original=name.original, tokens=new_tokens,
                      ambiguities=new_ambiguities)
