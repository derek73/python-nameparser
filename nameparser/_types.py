"""Core value types for the 2.0 API.

Layering (enforced by tests/v2/test_layering.py): this module imports
nothing from nameparser at module level -- it is the bottom of the
module-import dependency graph. The rendering delegates import _render
at call time, and a TYPE_CHECKING-only _lexicon import supplies the
Lexicon annotation.

Repr policy (applies to every v2 type's __repr__, across this module and
_lexicon.py/_policy.py/_locale.py): bounded output only. No repr may scale
with vocabulary size -- collections render as counts or deltas, never
contents.
"""
from __future__ import annotations

import dataclasses
from collections.abc import Mapping
from dataclasses import dataclass
from enum import Enum, StrEnum
from typing import TYPE_CHECKING, NamedTuple, NoReturn, TypeVar

if TYPE_CHECKING:
    from nameparser._lexicon import Lexicon
    from nameparser._parser import Parser


class Role(Enum):
    # Declaration order IS the canonical field order (conventions §3):
    # every listing of the seven fields anywhere derives from this.
    TITLE = "title"
    GIVEN = "given"
    MIDDLE = "middle"
    FAMILY = "family"
    SUFFIX = "suffix"
    NICKNAME = "nickname"
    MAIDEN = "maiden"


class Span(NamedTuple):
    """Provenance range into ParsedName.original. end is exclusive."""

    start: int
    end: int

    def __add__(self, other: object) -> NoReturn:  # type: ignore[override]
        # Inherited tuple + would concatenate two spans into a 4-tuple --
        # the natural but wrong spelling of "covering span". The real
        # covering operation ships with its consumer, the pipeline's
        # join stage.
        raise TypeError(
            "Span does not support +; tuple concatenation is not a "
            "covering span"
        )


#: Stable, documented tag vocabulary (API). All other tags are
#: namespaced ("vocab:...", "patronymic:...") and unstable. "joined"
#: marks a continuation token of a merged piece (the ph-d merge) and
#: drives the suffix view's space-vs-comma join.
STABLE_TAGS = frozenset({"particle", "conjunction", "initial", "joined"})

_E = TypeVar("_E", bound=Enum)


def _coerce_enum(value: object, enum_cls: type[_E], noun: str, plural: str) -> _E:
    """Coerce value to enum_cls, or raise the enriched ValueError listing
    every valid member (enum lookups stay ValueError for any input --
    stdlib EnumType precedent, see AGENTS.md's taxonomy rule)."""
    if isinstance(value, enum_cls):
        return value
    try:
        return enum_cls(value)
    except ValueError:
        valid = ", ".join(str(m.value) for m in enum_cls)
        raise ValueError(
            f"unknown {noun} {value!r}; valid {plural}: {valid}"
        ) from None


# Pickle support shared by the frozen slots dataclasses: fail at the
# LOAD site when a pickle's field layout does not match this version of
# the class (version skew) -- silently loading would defer the failure
# to a distant attribute read. Values are deliberately NOT re-validated:
# pickle is not a security boundary (arbitrary pickles can execute code
# anyway), and canonical state only comes from a validated instance.
# These are ASSIGNED IN EACH CLASS BODY (not inherited from a mixin):
# @dataclass(slots=True) regenerates the class and installs its own
# pickle methods unless __getstate__/__setstate__ are in the class's
# own __dict__. Lexicon duplicates this logic by design (its slots also
# carry a rebuilt mappingproxy) -- layering keeps _lexicon import-free
# of _types.


def _guarded_getstate(self: object) -> dict[str, object]:
    fields = dataclasses.fields(self)  # type: ignore[arg-type]
    return {f.name: getattr(self, f.name) for f in fields}


def _guarded_setstate(self: object, state: dict[str, object]) -> None:
    fields = dataclasses.fields(self)  # type: ignore[arg-type]
    expected = {f.name for f in fields}
    if set(state) != expected:
        missing = ", ".join(sorted(expected - set(state))) or "none"
        unexpected = ", ".join(sorted(set(state) - expected)) or "none"
        raise ValueError(
            f"incompatible {type(self).__name__} pickle: missing "
            f"fields: {missing}; unexpected fields: {unexpected}"
        )
    for name, value in state.items():
        object.__setattr__(self, name, value)


@dataclass(frozen=True, slots=True)
class Token:
    text: str
    span: Span | None  # None = synthetic (from replace())
    role: Role
    tags: frozenset[str] = frozenset()

    # in the class body so @dataclass(slots=True) keeps them
    __getstate__ = _guarded_getstate
    __setstate__ = _guarded_setstate

    def __post_init__(self) -> None:
        if not isinstance(self.text, str):
            raise TypeError(
                f"Token.text must be a str, got {self.text!r}"
            )
        if not self.text:
            raise ValueError("Token.text must be a non-empty string")
        object.__setattr__(
            self, "role", _coerce_enum(self.role, Role, "Role", "roles"))
        if self.span is not None:
            if not (
                isinstance(self.span, tuple)
                and len(self.span) == 2
                # bool is an int subclass: (False, True) is a comparison
                # result leaking into a coordinate slot, not a span
                and all(isinstance(v, int) and not isinstance(v, bool)
                        for v in self.span)
            ):
                raise TypeError(
                    f"invalid span {self.span!r}: expected a (start, end) "
                    "pair of ints or None"
                )
            start, end = self.span
            if start < 0 or end < start:
                raise ValueError(
                    f"invalid span ({start}, {end}): need 0 <= start <= end"
                )
            object.__setattr__(self, "span", Span(start, end))
        # The same guards _normset applies to Lexicon vocabulary: a bare
        # string would become its character set, a mapping would silently
        # contribute only its keys.
        if isinstance(self.tags, str):
            raise TypeError(
                "Token.tags must be an iterable of strings, "
                "not a bare string"
            )
        if isinstance(self.tags, Mapping):
            raise TypeError(
                "Token.tags must be an iterable of strings, not a mapping"
            )
        tags = frozenset(self.tags)
        for tag in tags:
            if not isinstance(tag, str):
                raise TypeError(
                    f"Token.tags must contain only strings, got {tag!r}"
                )
        object.__setattr__(self, "tags", tags)

    def __repr__(self) -> str:
        # Bounded output: a single token's text/span/role/tags, never
        # scales with vocabulary size (design rule -- see module docstring).
        where = (f"@{self.span.start}:{self.span.end}"
                 if self.span is not None else "@synthetic")
        tags = f" {{{', '.join(sorted(self.tags))}}}" if self.tags else ""
        return f"Token({self.text!r} {where} {self.role.name}{tags})"


class AmbiguityKind(StrEnum):
    """Stable identifiers (API); members ARE their string values."""

    ORDER = "order"
    SUFFIX_OR_NICKNAME = "suffix-or-nickname"
    PARTICLE_OR_GIVEN = "particle-or-given"
    UNBALANCED_DELIMITER = "unbalanced-delimiter"
    COMMA_STRUCTURE = "comma-structure"


@dataclass(frozen=True, slots=True)
class Ambiguity:
    kind: AmbiguityKind
    detail: str
    tokens: tuple[Token, ...]

    # in the class body so @dataclass(slots=True) keeps them
    __getstate__ = _guarded_getstate
    __setstate__ = _guarded_setstate

    def __post_init__(self) -> None:
        object.__setattr__(
            self, "kind",
            _coerce_enum(self.kind, AmbiguityKind, "AmbiguityKind", "kinds"))
        if not isinstance(self.detail, str):
            raise TypeError(
                f"Ambiguity.detail must be a str, got {self.detail!r}"
            )
        if not self.detail:
            raise ValueError("Ambiguity.detail must be a non-empty string")
        toks = tuple(self.tokens)
        for tok in toks:
            if not isinstance(tok, Token):
                raise TypeError(
                    f"Ambiguity.tokens must contain only Token instances, "
                    f"got {tok!r}"
                )
        object.__setattr__(self, "tokens", toks)

    def __repr__(self) -> str:
        texts = "/".join(repr(t.text) for t in self.tokens)
        return f"Ambiguity({self.kind.value!r}: {texts})"


@dataclass(frozen=True, slots=True)
class ParsedName:
    """Immutable result of a parse. Constructor-enforced invariants:
    spans ascending, non-overlapping, in bounds of `original`; every
    Ambiguity's tokens are a subset of `tokens`. Provenance semantics
    (text == original[span] for parser-produced names) are documented,
    not enforced -- transforms like replace() legitimately break them.
    """

    original: str
    tokens: tuple[Token, ...]
    ambiguities: tuple[Ambiguity, ...] = ()

    # in the class body so @dataclass(slots=True) keeps them
    __getstate__ = _guarded_getstate
    __setstate__ = _guarded_setstate

    def __post_init__(self) -> None:
        if not isinstance(self.original, str):
            raise TypeError(
                f"ParsedName.original must be a str, got {self.original!r}"
            )
        object.__setattr__(self, "tokens", tuple(self.tokens))
        object.__setattr__(self, "ambiguities", tuple(self.ambiguities))
        for tok in self.tokens:
            if not isinstance(tok, Token):
                raise TypeError(
                    f"ParsedName.tokens must contain only Token instances, "
                    f"got {tok!r}"
                )
        for amb in self.ambiguities:
            if not isinstance(amb, Ambiguity):
                raise TypeError(
                    f"ParsedName.ambiguities must contain only Ambiguity "
                    f"instances, got {amb!r}"
                )
        prev_end = 0
        for tok in self.tokens:
            if tok.span is None:
                continue
            if tok.span.end > len(self.original):
                raise ValueError(
                    f"token {tok.text!r} span {tuple(tok.span)} is out of "
                    f"bounds for original of length {len(self.original)}"
                )
            if tok.span.start < prev_end:
                raise ValueError(
                    f"token spans must be ascending and non-overlapping; "
                    f"token {tok.text!r} at {tuple(tok.span)} begins before "
                    f"offset {prev_end}"
                )
            prev_end = tok.span.end
        for amb in self.ambiguities:
            for tok in amb.tokens:
                if tok not in self.tokens:
                    raise ValueError(
                        f"Ambiguity token {tok.text!r} is not a subset of "
                        f"this ParsedName's tokens"
                    )

    def __bool__(self) -> bool:
        return bool(self.tokens)

    def __str__(self) -> str:
        return self.render()

    def __repr__(self) -> str:
        lines = []
        for role in Role:
            text = self._text_for(role)
            if text:
                lines.append(f"\t{role.value}: {text!r}")
        if self.ambiguities:
            kinds = [a.kind.value for a in self.ambiguities]
            lines.append(f"\tambiguities: {kinds!r}")
        body = "\n".join(lines)
        return f"<ParsedName: [\n{body}\n]>" if lines else "<ParsedName: []>"

    # -- string views (canonical order = Role declaration order) --------

    def _text_for(self, *roles: Role, tag: str | None = None,
                  without_tag: str | None = None) -> str:
        suffix_join = roles == (Role.SUFFIX,)
        parts: list[str] = []
        for tok in self.tokens:
            if tok.role not in roles:
                continue
            if tag is not None and tag not in tok.tags:
                continue
            if without_tag is not None and without_tag in tok.tags:
                continue
            # "joined" (stable tag) marks a continuation of the previous
            # token ("Ph." + "D."): attach with a space so the suffix
            # view's ", " join does not split one credential in two
            if suffix_join and "joined" in tok.tags and parts:
                parts[-1] += " " + tok.text
            else:
                parts.append(tok.text)
        return (", " if suffix_join else " ").join(parts)

    @property
    def title(self) -> str:
        return self._text_for(Role.TITLE)

    @property
    def given(self) -> str:
        return self._text_for(Role.GIVEN)

    @property
    def middle(self) -> str:
        return self._text_for(Role.MIDDLE)

    @property
    def family(self) -> str:
        return self._text_for(Role.FAMILY)

    @property
    def suffix(self) -> str:
        return self._text_for(Role.SUFFIX)

    @property
    def nickname(self) -> str:
        return self._text_for(Role.NICKNAME)

    @property
    def maiden(self) -> str:
        return self._text_for(Role.MAIDEN)

    # -- derived views (filters over roles + STABLE tags only) ----------

    @property
    def family_particles(self) -> str:
        return self._text_for(Role.FAMILY, tag="particle")

    @property
    def family_base(self) -> str:
        return self._text_for(Role.FAMILY, without_tag="particle")

    @property
    def surnames(self) -> str:
        return self._text_for(Role.MIDDLE, Role.FAMILY)

    @property
    def given_names(self) -> str:
        return self._text_for(Role.GIVEN, Role.MIDDLE)

    # -- structured access ----------------------------------------------

    def tokens_for(self, role: Role) -> tuple[Token, ...]:
        return tuple(t for t in self.tokens if t.role is role)

    def as_dict(self, include_empty: bool = True) -> dict[str, str]:
        # _text_for handles the suffix ", "-join (single-role SUFFIX call)
        d = {role.value: self._text_for(role) for role in Role}
        if not include_empty:
            d = {k: v for k, v in d.items() if v}
        return d

    # -- editing ----------------------------------------------------------

    def replace(self, **fields: str) -> ParsedName:
        """Return a new ParsedName with the named fields re-tokenized as
        synthetic tokens (span=None). Whitespace-splits each value; an
        empty value clears the field. original is unchanged (provenance).
        Ambiguities referencing replaced tokens are dropped.
        """
        by_value = {role.value: role for role in Role}
        for key, value in fields.items():
            if key not in by_value:
                raise TypeError(
                    f"unknown field {key!r}; expected one of "
                    f"{', '.join(by_value)}"
                )
            if not isinstance(value, str):
                raise TypeError(
                    f"field {key!r} must be a str, got {value!r}"
                )

        def synthetic(value: str, role: Role) -> list[Token]:
            return [Token(word, None, role) for word in value.split()]

        replaced = {by_value[k]: v for k, v in fields.items()}
        new_tokens: list[Token] = []
        emitted: set[Role] = set()
        for tok in self.tokens:
            if tok.role in replaced:
                if tok.role not in emitted:
                    new_tokens.extend(synthetic(replaced[tok.role], tok.role))
                    emitted.add(tok.role)
                continue
            new_tokens.append(tok)
        for role in Role:
            if role in replaced and role not in emitted:
                new_tokens.extend(synthetic(replaced[role], role))
        kept = tuple(
            amb for amb in self.ambiguities
            if all(t in new_tokens for t in amb.tokens)
        )
        return ParsedName(self.original, tuple(new_tokens), kept)

    # -- comparison -------------------------------------------------------

    def comparison_key(self) -> tuple[str, ...]:
        """One casefolded component per Role, in canonical order, for
        dedup, dict keys, and sorting. The semantic layer; __eq__ stays
        strict.
        """
        return tuple(self._text_for(role).casefold() for role in Role)

    def matches(self, other: str | ParsedName, *,
                parser: Parser | None = None) -> bool:
        """Component-wise case-insensitive comparison (the semantic
        layer; __eq__ stays strict). A str argument is parsed with
        `parser`, or the default parser when None."""
        if isinstance(other, str):
            import nameparser._parser as _parser
            active = parser if parser is not None else _parser._default_parser()
            other = active.parse(other)
        if not isinstance(other, ParsedName):
            raise TypeError(
                f"matches() takes a str or ParsedName, got {other!r}")
        return self.comparison_key() == other.comparison_key()

    # -- rendering delegates ----------------------------------------------
    # One-line delegation to nameparser._render (core spec §5b): parsing
    # code physically cannot import formatting logic, so these import at
    # call time -- module level stays internal-import-free.

    def render(self, spec: str = "{title} {given} {middle} {family} {suffix}") -> str:
        """Fill the str.format spec from the seven role fields and the
        derived views; empty fields collapse (#254). Unknown keys raise
        KeyError naming the valid fields."""
        import nameparser._render as _render
        return _render.render(self, spec)

    def initials(self, spec: str = "{given} {middle} {family}",
                 delimiter: str = ".", separator: str = " ") -> str:
        """Initials per group; v1's initials_format/_delimiter/_separator
        become call-site arguments (core spec §5b). Valid spec keys:
        given, middle, family."""
        import nameparser._render as _render
        return _render.initials(self, spec, delimiter, separator)

    def capitalized(self, lexicon: Lexicon | None = None, *,
                    force: bool = False) -> ParsedName:
        """Case-fixing transform -> new ParsedName, same spans, new
        token texts. Needs a lexicon for capitalization_exceptions and
        particle rules; None uses the default lexicon. force=False
        preserves mixed-case input (v1 parity). Idempotent."""
        import nameparser._render as _render
        return _render.capitalized(self, lexicon, force=force)
