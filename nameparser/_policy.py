"""Immutable behavior configuration for the 2.0 API.

Layering: imports nameparser._types only (tests/v2/test_layering.py,
added in a later task, enforces this).
"""
from __future__ import annotations

import dataclasses
from dataclasses import dataclass, field
from enum import Enum, StrEnum, auto

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
        if isinstance(self.patronymic_rules, str):
            raise TypeError(
                f"patronymic_rules must be an iterable of rule names, "
                f"not a bare string: {self.patronymic_rules!r}"
            )
        # A non-iterable raises its natural TypeError from the frozenset
        # call; only failed enum lookups get the enriched message.
        try:
            rules = frozenset(PatronymicRule(r) for r in self.patronymic_rules)
        except ValueError:
            valid = ", ".join(r.value for r in PatronymicRule)
            raise ValueError(
                f"unknown patronymic rule in {self.patronymic_rules!r}; "
                f"valid rules: {valid}"
            ) from None
        object.__setattr__(self, "patronymic_rules", rules)
        for pairs_name in ("nickname_delimiters", "maiden_delimiters"):
            pairs = tuple(getattr(self, pairs_name))
            for pair in pairs:
                if (not isinstance(pair, tuple) or len(pair) != 2
                        or not all(isinstance(s, str) for s in pair)):
                    raise TypeError(
                        f"{pairs_name} entries must be (open, close) tuples "
                        f"of strings, got {pair!r}"
                    )
                if not all(pair):
                    raise ValueError(
                        f"{pairs_name} entries must be pairs of non-empty "
                        f"strings, got {pair!r}"
                    )
            object.__setattr__(self, pairs_name, frozenset(pairs))
        if isinstance(self.extra_suffix_delimiters, str):
            raise TypeError(
                f"extra_suffix_delimiters must be an iterable of strings, "
                f"not a bare string: {self.extra_suffix_delimiters!r}"
            )
        delimiters = tuple(self.extra_suffix_delimiters)
        for d in delimiters:
            if not isinstance(d, str):
                raise TypeError(
                    f"extra_suffix_delimiters entries must be strings, "
                    f"got {d!r}"
                )
            if not d:
                raise ValueError(
                    "extra_suffix_delimiters entries must be non-empty strings"
                )
        object.__setattr__(
            self, "extra_suffix_delimiters", frozenset(delimiters)
        )

    def __repr__(self) -> str:
        # Bounded: only fields that deviate from the default are shown
        # (design rule, see nameparser._types module docstring).
        constant_names = {
            GIVEN_FIRST: "GIVEN_FIRST",
            FAMILY_FIRST: "FAMILY_FIRST",
            FAMILY_FIRST_GIVEN_LAST: "FAMILY_FIRST_GIVEN_LAST",
        }
        parts = []
        for f in dataclasses.fields(self):
            value = getattr(self, f.name)
            if value == f.default:
                continue
            if f.name == "name_order":
                # Only 3 of the 6 possible role permutations have named
                # constants; fall back to a compact role-name tuple for
                # the rest so this can't KeyError on an unnamed order.
                order_repr = constant_names.get(
                    value, "(" + ", ".join(r.name for r in value) + ")")
                parts.append(f"name_order={order_repr}")
            else:
                parts.append(f"{f.name}={value!r}")
        return f"Policy({', '.join(parts)})"


class _Unset(Enum):
    UNSET = auto()


#: Sentinel for "this patch does not set this field" (picklable enum
#: member, distinguishable from every real value including None/False).
UNSET = _Unset.UNSET

_UNION = {"compose": "union"}  # field metadata: set-valued -> union


@dataclass(frozen=True, slots=True)
class PolicyPatch:
    """A partial Policy: one field per Policy field, all defaulting to
    UNSET. Composition per field is DECLARED via metadata -- set-valued
    fields union, scalars override (later wins). Kept in lockstep with
    Policy by the parity test in tests/v2/test_policy.py.

    Values are validated when the patch is applied (Policy's constructor
    re-runs), not at patch construction.
    """

    name_order: tuple[Role, Role, Role] | _Unset = UNSET
    patronymic_rules: frozenset[PatronymicRule] | _Unset = field(
        default=UNSET, metadata=_UNION)
    middle_as_family: bool | _Unset = UNSET
    nickname_delimiters: frozenset[tuple[str, str]] | _Unset = field(
        default=UNSET, metadata=_UNION)
    maiden_delimiters: frozenset[tuple[str, str]] | _Unset = field(
        default=UNSET, metadata=_UNION)
    extra_suffix_delimiters: frozenset[str] | _Unset = field(
        default=UNSET, metadata=_UNION)
    lenient_comma_suffixes: bool | _Unset = UNSET
    strip_emoji: bool | _Unset = UNSET
    strip_bidi: bool | _Unset = UNSET

    def __post_init__(self) -> None:
        # Canonicalize (but do NOT validate) union-composed fields so a
        # patch built from a set/list literal is hashable and unions
        # cleanly in apply_patch.
        for f in dataclasses.fields(self):
            if f.metadata.get("compose") != "union":
                continue
            value = getattr(self, f.name)
            if value is UNSET:
                continue
            if isinstance(value, str):
                raise TypeError(
                    f"{f.name} must be an iterable, "
                    f"not a bare string: {value!r}"
                )
            object.__setattr__(self, f.name, frozenset(value))


def apply_patch(policy: Policy, patch: PolicyPatch) -> Policy:
    """Fold a PolicyPatch onto a Policy. Policy.__post_init__ re-runs via
    dataclasses.replace, so patched values are revalidated for free."""
    updates: dict[str, object] = {}
    for f in dataclasses.fields(PolicyPatch):
        value = getattr(patch, f.name)
        if value is UNSET:
            continue
        if f.metadata.get("compose") == "union":
            value = getattr(policy, f.name) | value
        updates[f.name] = value
    if not updates:
        return policy
    # Known mypy limitation with **dict-unpacked replace; see the full
    # explanation at Lexicon._edit in _lexicon.py.
    return dataclasses.replace(policy, **updates)  # type: ignore[arg-type]
