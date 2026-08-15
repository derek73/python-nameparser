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

# Ported verbatim from v1 (nameparser/config/regexes.py "initial",
# minus the empty alternative) -- layering forbids importing the
# pipeline here; keep in sync with _pipeline/_vocab.py by hand.
# Deliberately NOT composed with that module's repertoire test (#320):
# layering forbids the import, and nothing here needs it. The only use
# is v1's conjunction carve-out in _cap_word below, which this pattern
# can only reach once `normalized in lex.conjunctions` already holds --
# and no CJK token reaches that, the shipped vocabulary carrying no CJK
# conjunction or particle in the default lexicon or in any locale pack.
# That is a property of the shipped DATA, not an invariant -- conjunctions
# is public, configurable API -- but the divergence stays harmless if a
# user adds one: CJK is caseless, so the carve-out's word.lower() and the
# fall-through's word.capitalize() return the same string either way.
# So the two copies keep identical PATTERNS and divergent PREDICATES;
# test_regex_sync pins the patterns, which is the promise being kept.
_INITIAL = re.compile(r"^(\w\.|[A-Z])$")


def _collapse(rendered: str) -> str:
    """The #254 collapse: empty fields substitute '' and every artifact
    of that is removed -- dangling empty-nickname wrappers, space runs,
    space-before-comma, one trailing comma character (any script),
    leading/trailing ', ' debris."""
    rendered = (rendered.replace(" ()", "")
                        .replace(" ''", "")
                        .replace(' ""', ""))
    rendered = _SPACE_BEFORE_COMMA.sub(",", rendered)
    rendered = _SPACES.sub(" ", rendered.strip())
    if rendered and _COMMA_CHAR.fullmatch(rendered[-1]):
        rendered = rendered[:-1]
    return rendered.strip(", ")


def _format_spec(spec: str, values: dict[str, str], noun: str,
                 keys: tuple[str, ...]) -> str:
    """Shared tail of render()/initials(): fill the spec, enrich
    unknown-KEY errors with the valid key list, collapse."""
    if not isinstance(spec, str):
        raise TypeError(f"spec must be a str, got {spec!r}")
    try:
        rendered = spec.format(**values)
    except KeyError as exc:
        raise KeyError(
            f"unknown {noun} field {exc.args[0]!r}; valid fields: "
            f"{', '.join(keys)}"
        ) from None
    return _collapse(rendered)


def render(name: ParsedName, spec: str) -> str:
    """Fill the str.format spec from the seven role fields and the
    derived views (empty fields substitute ''), then apply the #254
    collapse. Unknown keys raise KeyError naming the valid fields."""
    values = {key: getattr(name, key) for key in _RENDER_KEYS}
    return _format_spec(spec, values, "render", _RENDER_KEYS)


# rules.md#R3: "initials take the first letter of each given, middle,
# and base family word; titles, suffixes, particles and nicknames
# contribute nothing"
def initials(name: ParsedName, spec: str, delimiter: str, separator: str) -> str:
    """First letter of each contributing token per group, v1 semantics:
    delimiter follows each initial, separator sits between initials
    within a group. Tokens tagged particle/conjunction contribute no
    initial in middle/family (given-name tokens always contribute);
    tags come from the pipeline -- hand-built untagged tokens all
    contribute. Valid spec keys: given, middle, family."""
    if not isinstance(delimiter, str):
        raise TypeError(f"delimiter must be a str, got {delimiter!r}")
    if not isinstance(separator, str):
        raise TypeError(f"separator must be a str, got {separator!r}")
    values: dict[str, str] = {}
    for key in _INITIALS_KEYS:
        role = Role(key)
        tokens = name.tokens_for(role)
        if role is not Role.GIVEN:
            tokens = tuple(t for t in tokens
                           if not (_SKIP_TAGS & t.tags))
        values[key] = separator.join(
            t.text[0] + delimiter for t in tokens)
    return _format_spec(spec, values, "initials", _INITIALS_KEYS)


def _cap_word(word: str, role: Role, lex: Lexicon) -> str:
    # v1 cap_word order: particle/conjunction rule first, then the
    # exceptions map, then Mac/Mc, then str.capitalize
    normalized = _normalize(word)
    # v1's is_conjunction excludes initials: 'E.' in 'Scott E. Werner'
    # is an initial, not the conjunction 'e' (pinned live 2026-07-17)
    if ((normalized in lex.particles and role in (Role.MIDDLE, Role.FAMILY))
            or (normalized in lex.conjunctions
                and not _INITIAL.fullmatch(word))):
        return word.lower()
    # v1 cap_word tries the edge-stripped form, then the period-free
    # form ('Ph.D.' -> 'ph.d' -> 'phd' hits the exceptions map)
    for key in (normalized, normalized.replace(".", "")):
        exception = lex.capitalization_exceptions_map.get(key)
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


# rules.md#R4: "case repair returns a repaired copy — vocabulary
# exceptions (McDonald) included — and never mutates the parse"
def capitalized(name: ParsedName, lexicon: Lexicon | None, *,
                force: bool) -> ParsedName:
    """Case-fixing transform -> new ParsedName, same spans, new token
    texts. Gate (v1 parity): only single-case input is
    touched unless force=True; the gate reads the joined token texts
    (not render() output -- the case gate stays decoupled from spec
    formatting and the #254 collapse).
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
