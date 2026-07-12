"""Immutable behavior configuration for the 2.0 API.

Layering: imports nameparser._types only (tests/v2/test_layering.py,
added in a later task, enforces this).
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from nameparser._types import Role


class PatronymicRule(StrEnum):
    """Stable rule names (API); implementations live in the pipeline."""

    EAST_SLAVIC = "east-slavic"
    TURKIC = "turkic"


# Order-spec constants (#270). Each reads as its contents because roles
# are named given/family, not first/last.
GIVEN_FIRST = (Role.GIVEN, Role.MIDDLE, Role.FAMILY)
FAMILY_FIRST = (Role.FAMILY, Role.GIVEN, Role.MIDDLE)
FAMILY_FIRST_GIVEN_LAST = (Role.FAMILY, Role.MIDDLE, Role.GIVEN)

_NAME_ROLES = frozenset({Role.GIVEN, Role.MIDDLE, Role.FAMILY})


@dataclass(frozen=True, slots=True)
class Policy:
    name_order: tuple[Role, Role, Role] = GIVEN_FIRST
    patronymic_rules: frozenset[PatronymicRule] = frozenset()
    middle_as_family: bool = False  # v1's middle_name_as_last
    # v1 default delimiter set (#273)
    nickname_delimiters: frozenset[tuple[str, str]] = frozenset(
        {("'", "'"), ('"', '"'), ("(", ")")}
    )
    # empty by default (v1 parity); route ("(", ")") here to send
    # parenthesized content to maiden instead of nickname (#274)
    maiden_delimiters: frozenset[tuple[str, str]] = frozenset()
    extra_suffix_delimiters: frozenset[str] = frozenset()
    lenient_comma_suffixes: bool = True
    strip_emoji: bool = True
    strip_bidi: bool = True  # replaces v1's CONSTANTS.regexes.bidi = False

    def __post_init__(self) -> None:
        order = tuple(self.name_order)
        if len(order) != 3 or set(order) != _NAME_ROLES:
            raise ValueError(
                f"name_order must be a permutation of (Role.GIVEN, "
                f"Role.MIDDLE, Role.FAMILY), got {order!r}; use "
                f"GIVEN_FIRST, FAMILY_FIRST, or FAMILY_FIRST_GIVEN_LAST"
            )
        object.__setattr__(self, "name_order", order)
        try:
            rules = frozenset(PatronymicRule(r) for r in self.patronymic_rules)
        except ValueError:
            valid = ", ".join(r.value for r in PatronymicRule)
            raise ValueError(
                f"unknown patronymic rule in {set(self.patronymic_rules)!r}; "
                f"valid rules: {valid}"
            ) from None
        object.__setattr__(self, "patronymic_rules", rules)
        for pairs_name in ("nickname_delimiters", "maiden_delimiters"):
            for pair in getattr(self, pairs_name):
                if (len(pair) != 2 or not all(
                        isinstance(s, str) and s for s in pair)):
                    raise ValueError(
                        f"{pairs_name} entries must be pairs of non-empty "
                        f"strings, got {pair!r}"
                    )
