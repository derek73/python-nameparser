"""Core value types for the 2.0 API.

Layering (enforced by tests/v2/test_layering.py): this module imports
nothing from nameparser -- it is the bottom of the dependency graph.

Repr policy (applies to every v2 type's __repr__, across this module and
_lexicon.py/_policy.py/_locale.py): bounded output only. No repr may scale
with vocabulary size -- collections render as counts or deltas, never
contents.
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum, StrEnum
from typing import NamedTuple


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


#: Stable, documented tag vocabulary (API). All other tags are
#: namespaced ("vocab:...", "patronymic:...") and unstable.
STABLE_TAGS = frozenset({"particle", "conjunction", "initial"})


@dataclass(frozen=True, slots=True)
class Token:
    text: str
    span: Span | None  # None = synthetic (from replace())
    role: Role
    tags: frozenset[str] = frozenset()

    def __post_init__(self) -> None:
        if not isinstance(self.text, str) or not self.text:
            raise ValueError(
                f"Token.text must be a non-empty string, got {self.text!r}"
            )
        if self.span is not None:
            if not (
                isinstance(self.span, tuple)
                and len(self.span) == 2
                and all(isinstance(v, int) for v in self.span)
            ):
                raise ValueError(
                    f"invalid span {self.span!r}: expected a (start, end) "
                    "pair of ints or None"
                )
            start, end = self.span
            if start < 0 or end < start:
                raise ValueError(
                    f"invalid span ({start}, {end}): need 0 <= start <= end"
                )
            object.__setattr__(self, "span", Span(start, end))
        object.__setattr__(self, "tags", frozenset(self.tags))

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

    def __post_init__(self) -> None:
        if not isinstance(self.kind, AmbiguityKind):
            try:
                object.__setattr__(self, "kind", AmbiguityKind(self.kind))
            except ValueError:
                valid = ", ".join(k.value for k in AmbiguityKind)
                raise ValueError(
                    f"unknown AmbiguityKind {self.kind!r}; valid kinds: {valid}"
                ) from None
        if not isinstance(self.detail, str) or not self.detail:
            raise ValueError(
                f"Ambiguity.detail must be a non-empty string, got {self.detail!r}"
            )
        toks = tuple(self.tokens)
        for tok in toks:
            if not isinstance(tok, Token):
                raise ValueError(
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

    def __post_init__(self) -> None:
        if not isinstance(self.original, str):
            raise ValueError(
                f"ParsedName.original must be a str, got {self.original!r}"
            )
        object.__setattr__(self, "tokens", tuple(self.tokens))
        object.__setattr__(self, "ambiguities", tuple(self.ambiguities))
        for tok in self.tokens:
            if not isinstance(tok, Token):
                raise ValueError(
                    f"ParsedName.tokens must contain only Token instances, "
                    f"got {tok!r}"
                )
        for amb in self.ambiguities:
            if not isinstance(amb, Ambiguity):
                raise ValueError(
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
        joiner = ", " if roles == (Role.SUFFIX,) else " "
        parts = []
        for tok in self.tokens:
            if tok.role not in roles:
                continue
            if tag is not None and tag not in tok.tags:
                continue
            if without_tag is not None and without_tag in tok.tags:
                continue
            parts.append(tok.text)
        return joiner.join(parts)

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
        """Casefolded seven components in canonical order, for dedup,
        dict keys, and sorting. The semantic layer; __eq__ stays strict.
        """
        return tuple(self._text_for(role).casefold() for role in Role)
