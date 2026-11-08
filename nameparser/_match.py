"""Name matching: the settings object and the result types.

Consumes: nothing at parse time. This module holds the types a match
reads and reports; `Matching` carries a `Parser` and the set of outcomes
the caller accepts.
Produces: `Outcome`, `Side`, `RoleMatch`, `MatchResult`, `DEFAULT_ACCEPT`
and `Matching`.
Reads: no `Policy` or `Lexicon` field; the `Parser` is held, not read.

Consistent means nothing in the two names contradicts it, under the
outcomes the caller accepts. The module imports `_types` and `_lexicon`
only, `Parser` for typing alone.
"""
from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from enum import StrEnum
from typing import TYPE_CHECKING

from nameparser._types import (
    Role,
    _guarded_getstate,
    _guarded_setstate,
)

if TYPE_CHECKING:
    from nameparser._parser import Parser


class Outcome(StrEnum):
    """How one role of one name compares with the same role of another,
    strongest first. `conflict` is the one outcome that is never accepted."""

    SAME = "same"
    FOLDED = "folded"
    LISTED_SPELLING = "listed-spelling"
    PARTICLES_ASIDE = "particles-aside"
    PART_OF_OTHER = "part-of-other"
    INITIAL = "initial"
    INITIALS_AGREE = "initials-agree"
    ONE_SIDE = "one-side"
    GENERATION_ONE_SIDE = "generation-one-side"
    NOTED = "noted"
    FAMILY_INITIAL = "family-initial"
    GIVEN_ONE_SIDE = "given-one-side"
    HYPHENATED_PART = "hyphenated-part"
    OTHER_READING = "other-reading"
    ACROSS_ROLES = "across-roles"
    CONFLICT = "conflict"


class Side(StrEnum):
    """Which side of a comparison carried more of the role's text."""

    LEFT = "left"
    RIGHT = "right"
    NEITHER = "neither"


_MIRROR = {Side.LEFT: Side.RIGHT, Side.RIGHT: Side.LEFT, Side.NEITHER: Side.NEITHER}


@dataclass(frozen=True, slots=True)
class RoleMatch:
    """One role's comparison: the outcome, both sides' text, and which
    side carried more."""

    role: Role
    outcome: Outcome
    left: str
    right: str
    more: Side

    __getstate__ = _guarded_getstate
    __setstate__ = _guarded_setstate

    def mirrored(self) -> RoleMatch:
        """The same comparison with the two names swapped."""
        return RoleMatch(self.role, self.outcome, self.right, self.left,
                         _MIRROR[self.more])


@dataclass(frozen=True, slots=True)
class MatchResult:
    """The result of comparing two names: whether nothing in them
    contradicts the match under the accepted outcomes, and one
    `RoleMatch` per `Role`, in `Role` order."""

    consistent: bool
    roles: tuple[RoleMatch, ...]

    __getstate__ = _guarded_getstate
    __setstate__ = _guarded_setstate

    def mirrored(self) -> MatchResult:
        """The same result with the two names swapped: each role's left
        and right text exchanged and its `more` side flipped."""
        return MatchResult(self.consistent,
                           tuple(m.mirrored() for m in self.roles))


#: The outcomes accepted when a caller states none.
DEFAULT_ACCEPT: frozenset[Outcome] = frozenset({
    Outcome.SAME, Outcome.FOLDED, Outcome.LISTED_SPELLING,
    Outcome.PARTICLES_ASIDE, Outcome.PART_OF_OTHER, Outcome.INITIAL,
    Outcome.INITIALS_AGREE, Outcome.ONE_SIDE, Outcome.GENERATION_ONE_SIDE,
    Outcome.NOTED,
})

_VALID = ", ".join(o.value for o in Outcome if o is not Outcome.CONFLICT)


def _outcome(value: object) -> Outcome:
    if isinstance(value, Outcome):
        return value
    if isinstance(value, str):
        try:
            return Outcome(value)
        except ValueError:
            raise ValueError(
                f"unknown outcome {value!r}; valid outcomes: {_VALID}"
            ) from None
    raise TypeError(
        f"accept must be an iterable of outcome names or Outcome members, "
        f"got a member {value!r} of type {type(value).__name__}; pass "
        f"e.g. accept={{'initial', 'family-initial'}}")


@dataclass(frozen=True, slots=True)
class Matching:
    """The settings of a name match: the parser that reads the names and
    the outcomes accepted as consistent.

    `accept` takes any iterable of `Outcome` members or their names and is
    stored as a frozenset with `same` always present. Passing it replaces
    the default set rather than extending it, so extend with
    `DEFAULT_ACCEPT | {"family-initial"}`. `conflict` cannot be accepted.
    """

    parser: Parser
    accept: frozenset[Outcome] = DEFAULT_ACCEPT

    __getstate__ = _guarded_getstate
    __setstate__ = _guarded_setstate

    def __post_init__(self) -> None:
        if not callable(getattr(self.parser, "parse", None)):
            raise TypeError(
                f"parser must be a Parser, got {type(self.parser).__name__}; "
                f"pass Parser() or use Parser.matching()")
        accept = self.accept
        if isinstance(accept, (str, bytes, Mapping)) or not isinstance(accept, Iterable):
            raise TypeError(
                f"accept must be an iterable of outcome names, got "
                f"{type(accept).__name__} {accept!r}; pass e.g. "
                f"accept={{'initial', 'family-initial'}}")
        outcomes = frozenset(_outcome(v) for v in accept)
        if Outcome.CONFLICT in outcomes:
            raise ValueError(
                f"'conflict' cannot be accepted: it is the outcome of a "
                f"contradiction; drop it from accept (valid outcomes: "
                f"{_VALID})")
        object.__setattr__(self, "accept", outcomes | {Outcome.SAME})

    def __repr__(self) -> str:
        added = sorted(o.value for o in self.accept - DEFAULT_ACCEPT)
        removed = sorted(o.value for o in DEFAULT_ACCEPT - self.accept)
        parts = ["default"]
        if added:
            parts.append("+ " + ", ".join(added))
        if removed:
            parts.append("- " + ", ".join(removed))
        return f"Matching({' '.join(parts)})"

