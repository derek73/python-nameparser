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
        object.__setattr__(self, "tokens", tuple(self.tokens))
