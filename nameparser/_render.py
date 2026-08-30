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
from nameparser._types import (UNJOINED_TAG, Ambiguity, ParsedName, Role,
                               Token)

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

#: Tags whose tokens contribute no initial outside the given group --
#: unless the token also carries UNJOINED_TAG, i.e. the whole part is
#: particles, in which case they are the part's only words and do
#: contribute (rules.md#R3, #404).
#: Not STABLE_TAGS -- that also contains "initial", which must contribute.
_SKIP_TAGS = frozenset({"particle", "conjunction"})

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
                           if not (_SKIP_TAGS & t.tags)
                           or UNJOINED_TAG in t.tags)
        values[key] = separator.join(
            t.text[0] + delimiter for t in tokens)
    return _format_spec(spec, values, "initials", _INITIALS_KEYS)


def _cap_word(word: str, role: Role, tags: frozenset[str],
              lex: Lexicon) -> str:
    # v1 cap_word order: particle/conjunction rule first, then the
    # exceptions map, then Mac/Mc, then str.capitalize
    normalized = _normalize(word)
    # rules.md#R4: "a part whose every word is particle vocabulary is
    # repaired as ordinary name words, since none of them is doing a
    # particle's work there" -- UNJOINED_TAG is that mark (#407).
    # Only the PARTICLE conjunct is gated on it, and that is the rule
    # rather than an omission: rules.md#R4 carries the carve-out R3
    # already states for initials -- "A CONJUNCTION never initials, so
    # a base that is one contributes nothing even then" -- so a
    # conjunction keeps conjunction treatment even inside a part the
    # mark has turned into ordinary name words.
    # No SHIPPED name witnesses the difference: `particles` and
    # `conjunctions` are disjoint in the default vocabulary and in
    # every locale pack, so no shipped conjunction can sit in an
    # all-particle part and carry the mark. That is a property of the
    # shipped DATA, not an invariant -- both sets are public,
    # configurable API, and a caller's Lexicon may put one word in
    # both, the way _pipeline/_post_rules.py's arms allow for. Measured:
    # under `Lexicon.default().add(particles={'y'})`, `anh y van` has
    # an all-particle family whose `y` carries both tags and the mark,
    # and gives 'Anh y Van'; gating this conjunct too would give
    # 'Anh Y Van'.
    # That conjunct reads the TAG, not the word (#458). classify takes
    # the conjunction-versus-initial decision once, over the whole
    # token -- v1's is_conjunction excludes initials, so 'E.' in
    # 'Scott E. Werner' is an initial and is never tagged (pinned live
    # 2026-07-17) -- and a view honors that decision rather than taking
    # it again from the spelling (mechanisms.md#VOCAB-TAGS: "later
    # stages test tags"). Asking again was not even the same question:
    # the copy of the initial pattern that stood here was the SHAPE
    # half alone, and it re-decided per WORD of a token's text, so
    # 'juan e-f smith' capitalized to 'Juan e-F Smith'. What moves the
    # other way is a token the parse never saw: one hand-built, or
    # spliced in by replace(), carries no decision to honor and is
    # repaired as an ordinary name word -- rules.md#R4's Accepted
    # boundary, which the particle conjunct above draws in the opposite
    # direction because it still asks the vocabulary itself.
    if ((normalized in lex.particles and role in (Role.MIDDLE, Role.FAMILY)
            and UNJOINED_TAG not in tags)
            or "conjunction" in tags):
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


def _cap_text(text: str, role: Role, tags: frozenset[str],
              lex: Lexicon) -> str:
    # word-by-word within the token text: hyphenated names capitalize
    # both sides ("macdole-eisenhower" -> "MacDole-Eisenhower")
    return _WORD.sub(lambda m: _cap_word(m.group(0), role, tags, lex), text)


# rules.md#R4: "case repair returns a repaired copy and never mutates
# the parse"
def capitalized(name: ParsedName, lexicon: Lexicon | None, *,
                force: bool) -> ParsedName:
    """Case-fixing transform -> new ParsedName, same spans, new token
    texts. Gate (v1 parity): only single-case input is
    touched unless force=True; the gate reads the joined token texts
    (not render() output -- the case gate stays decoupled from spec
    formatting and the #254 collapse).
    The repair reads token TAGS as well as texts: a part whose every
    word is particle vocabulary is repaired as ordinary name words,
    and the mark saying so comes from the pipeline, as does the
    reading that a word is a conjunction rather than an initial. A
    hand-built token, or one replace() splices in, carries no tags:
    it is repaired as a plain particle, and as no conjunction at all.
    A family set that way to 'de la' stays 'de la' where the same
    words parsed give 'De La', while one set to 'de y' gives 'de Y'
    where the parse would keep the conjunction lowercase.
    Parser.revise() is the edit that classifies the value, and gives
    'De La' (rules.md#R4's Accepted boundary).
    Idempotent: without force, a capitalized result is mixed-case and
    the gate returns it unchanged; with force, every _cap_word rule is
    a fixpoint on its own output."""
    if lexicon is not None and not isinstance(lexicon, Lexicon):
        # eager, before the gate: a garbage argument must not become a
        # silent no-op on mixed-case input or a deep AttributeError
        raise TypeError(f"lexicon must be a Lexicon or None, got {lexicon!r}")
    lex = Lexicon.default() if lexicon is None else lexicon
    joined = " ".join(t.text for t in name.tokens)
    # rules.md#R5: "case repair acts only on a name written entirely
    # in one case"
    if not force and joined not in (joined.upper(), joined.lower()):
        return name
    new_tokens = tuple(
        Token(_cap_text(t.text, t.role, t.tags, lex), t.span, t.role, t.tags)
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
