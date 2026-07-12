"""Core value types for the 2.0 API.

Layering (enforced by tests/v2/test_layering.py): this module imports
nothing from nameparser -- it is the bottom of the dependency graph.
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
        object.__setattr__(self, "tokens", tuple(self.tokens))
        object.__setattr__(self, "ambiguities", tuple(self.ambiguities))
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
