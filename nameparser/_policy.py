"""Immutable behavior configuration for the 2.0 API.

Layering: imports nameparser._types only (enforced by
tests/v2/test_layering.py).
"""
from __future__ import annotations

import dataclasses
from dataclasses import dataclass, field
from enum import Enum, StrEnum, auto

from nameparser._types import Role, _guarded_getstate, _guarded_setstate


class PatronymicRule(StrEnum):
    """Stable rule names (API); implementations live in the pipeline.
    Enable via ``Policy(patronymic_rules={...})`` or, more commonly, a
    locale pack (:mod:`nameparser.locales`)."""

    #: East Slavic formal order: "Sidorov Ivan Petrovich"
    #: (family, given, patronymic) is detected by the patronymic
    #: ending and reordered. Enabled by locales.RU.
    EAST_SLAVIC = "east-slavic"
    #: Turkic patronymic markers: a standalone "oglu"/"qizi"/"kyzy"
    #: (etc.) binds to the preceding name as a patronymic. Enabled by
    #: locales.TR_AZ.
    TURKIC = "turkic"


# Order-spec constants (#270). Each reads as its contents because roles
# are named given/family, not first/last.

#: Western order (the default): the first word of positional input is
#: the given name, the last is the family name, everything between is
#: middle. One of the three valid ``Policy(name_order=...)`` values.
GIVEN_FIRST = (Role.GIVEN, Role.MIDDLE, Role.FAMILY)
#: Family name first, given name second, remaining words middle
#: (e.g. Hungarian, or East Asian order). One of the three valid
#: ``Policy(name_order=...)`` values.
FAMILY_FIRST = (Role.FAMILY, Role.GIVEN, Role.MIDDLE)
#: Family name first, given name LAST, words between middle
#: (e.g. Vietnamese full-name order). One of the three valid
#: ``Policy(name_order=...)`` values.
FAMILY_FIRST_GIVEN_LAST = (Role.FAMILY, Role.MIDDLE, Role.GIVEN)

_NAME_ROLES = frozenset({Role.GIVEN, Role.MIDDLE, Role.FAMILY})

#: Policy.nickname_delimiters' default (v1 parity: quotes + parentheses).
#: Public and named so customizations read as set math against a
#: documented value -- e.g. ``DEFAULT_NICKNAME_DELIMITERS | {("«", "»")}``
#: -- instead of a rebuilt literal the user had to go discover.
DEFAULT_NICKNAME_DELIMITERS = frozenset(
    {("'", "'"), ('"', '"'), ("(", ")")})


def _reject_bare_string_order(value: object) -> None:
    # tuple("gmf") would be ("g", "m", "f") -- catch the bare string
    # with the same TypeError every other iterable field raises.
    # Single-sourced: called from Policy AND PolicyPatch __post_init__.
    if isinstance(value, str):
        raise TypeError(
            f"name_order must be an iterable of three Roles, "
            f"not a bare string: {value!r}"
        )


@dataclass(frozen=True, slots=True)
class Policy:
    """The behavior switches a parser runs with: name order,
    patronymic rules, delimiter routing, input scrubbing. Immutable
    and hashable; every field has a safe default, so construct with
    only what you change -- ``Policy(maiden_delimiters={("(", ")")})``
    -- and pass the result to ``Parser(policy=...)``."""

    #: How positional (no-comma) input maps onto given/middle/family.
    #: Valid values are exactly the three exported
    #: :ref:`name-order constants <name-order-constants>` --
    #: GIVEN_FIRST (the default), FAMILY_FIRST, and
    #: FAMILY_FIRST_GIVEN_LAST; any other tuple of Roles raises
    #: ValueError. Ignored when the input contains a comma: the comma
    #: itself states the order -- "Thomas, John" puts the family name
    #: first no matter which words could otherwise be either
    #: ("Thomas" and "John" both work as given or family names).
    name_order: tuple[Role, Role, Role] = GIVEN_FIRST
    #: Opt-in detectors that reorder patronymic-shaped names
    #: (EAST_SLAVIC, TURKIC); usually set via a locale pack.
    patronymic_rules: frozenset[PatronymicRule] = frozenset()
    #: Folds middle into family instead of splitting them (v1's
    #: middle_name_as_last).
    middle_as_family: bool = False  # v1's middle_name_as_last
    #: (open, close) pairs whose enclosed content becomes the nickname
    #: field. Defaults to DEFAULT_NICKNAME_DELIMITERS (#273).
    nickname_delimiters: frozenset[tuple[str, str]] = DEFAULT_NICKNAME_DELIMITERS
    #: (open, close) pairs whose enclosed content becomes the maiden
    #: field instead; a pair listed here is dropped from the effective
    #: nickname set (maiden wins, see __post_init__), so
    #: maiden_delimiters={("(", ")")} is the whole recipe (#274).
    maiden_delimiters: frozenset[tuple[str, str]] = frozenset()
    #: Additional separators that split suffix groups (e.g. " - " for
    #: "Jane Smith, RN - CRNA"). Additive only: the comma always
    #: splits suffix groups and cannot be replaced -- comma handling
    #: is structural (the same comma reading that parses
    #: "Family, Given" input), not a configurable delimiter.
    extra_suffix_delimiters: frozenset[str] = frozenset()
    #: Governs "Family, Suffix"-shaped input where the suffix word is
    #: also initial-shaped (a single letter, bare or period-written --
    #: of the default vocabulary that means the roman numerals "I" and
    #: "V"): "John Smith, V" reads as John Smith the fifth when True
    #: (the default, v1 behavior); False reads "V" as a given-name
    #: initial instead (family "John Smith", given "V"). Multi-letter
    #: suffixes ("III", "MD") parse the same either way.
    lenient_comma_suffixes: bool = True
    #: Excludes emoji from tokenization: they appear in no token,
    #: field, or rendered view. The original string keeps them (input
    #: is never modified -- spans stay true).
    strip_emoji: bool = True
    #: Excludes bidirectional control characters from tokenization:
    #: they appear in no token, field, or rendered view; the original
    #: string keeps them.
    strip_bidi: bool = True  # =False replaces v1's opt-out CONSTANTS.regexes.bidi = False

    # in the class body so @dataclass(slots=True) keeps them
    __getstate__ = _guarded_getstate
    __setstate__ = _guarded_setstate

    def __post_init__(self) -> None:
        _reject_bare_string_order(self.name_order)
        order = tuple(self.name_order)
        for element in order:
            if not isinstance(element, Role):
                raise TypeError(
                    f"name_order elements must be Role members, "
                    f"got {element!r}"
                )
        # Only the three exported orders have implemented assignment
        # semantics; the unnamed permutations would silently misassign.
        # Pre-2.0 strictness is free -- relaxing later is compatible.
        if order not in (GIVEN_FIRST, FAMILY_FIRST,
                         FAMILY_FIRST_GIVEN_LAST):
            raise ValueError(
                f"name_order must be one of the exported orders, got "
                f"{order!r}; use GIVEN_FIRST, FAMILY_FIRST, or "
                f"FAMILY_FIRST_GIVEN_LAST"
            )
        object.__setattr__(self, "name_order", order)
        if isinstance(self.patronymic_rules, str):
            raise TypeError(
                f"patronymic_rules must be an iterable of rule names, "
                f"not a bare string: {self.patronymic_rules!r}"
            )
        # Probe with iter() rather than wrapping tuple(): non-iterables
        # (True especially -- v1's patronymic_name_order was a bool flag,
        # so it's the likeliest wrong value here) get the migration-
        # pointing message, while an exception raised inside a caller's
        # generator still propagates untouched from the tuple() below
        # instead of being rewritten. Only the enum lookup itself gets
        # the unknown-rule message, naming the offender.
        try:
            rule_iter = iter(self.patronymic_rules)
        except TypeError:
            raise TypeError(
                f"patronymic_rules must be an iterable of PatronymicRule "
                f"names, got {self.patronymic_rules!r}; v1's "
                f"patronymic_name_order=True enabled both rules -- "
                f"patronymic_rules={{PatronymicRule.EAST_SLAVIC, "
                f"PatronymicRule.TURKIC}} (or pick one via "
                f"parser_for(locales.RU) / locales.TR_AZ)"
            ) from None
        items = tuple(rule_iter)
        rules = set()
        for r in items:
            try:
                rules.add(PatronymicRule(r))
            except ValueError:
                valid = ", ".join(v.value for v in PatronymicRule)
                raise ValueError(
                    f"unknown patronymic rule {r!r}; valid rules: {valid}"
                ) from None
        object.__setattr__(self, "patronymic_rules", frozenset(rules))
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
        # Maiden wins: a pair can route to exactly one field, and listing
        # it in maiden_delimiters is the specific intent, so the effective
        # nickname set drops it. Canonicalization, not validation (the
        # name_order coercion precedent): differently-written but
        # equivalent Policies converge to equal values. The v1 facade
        # keeps v1's nickname-wins precedence via a pre-subtraction in
        # _config_shim's snapshot instead.
        object.__setattr__(
            self, "nickname_delimiters",
            self.nickname_delimiters - self.maiden_delimiters)
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
        # Truthy strings ("no", "false") would silently invert the
        # caller's intent downstream; bools are the one field kind the
        # coercing checks above can't cover.
        for flag in ("middle_as_family", "lenient_comma_suffixes",
                     "strip_emoji", "strip_bidi"):
            value = getattr(self, flag)
            if not isinstance(value, bool):
                raise TypeError(
                    f"{flag} must be a bool, got {value!r}"
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
                # __post_init__ restricts to the three named orders, so
                # the fallback is unreachable via the constructor; kept
                # because repr must never raise (e.g. a smuggled
                # __setstate__ value -- layout is validated, values not).
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

    # in the class body so @dataclass(slots=True) keeps them
    __getstate__ = _guarded_getstate
    __setstate__ = _guarded_setstate

    def __post_init__(self) -> None:
        # Canonicalize (but do NOT validate) collection fields so a patch
        # built from a set/list literal is hashable and unions cleanly in
        # apply_patch. name_order needs the same treatment: Policy would
        # coerce a list at apply time, but the patch itself (and any
        # Locale holding it) must already be hashable.
        if self.name_order is not UNSET:
            _reject_bare_string_order(self.name_order)
            object.__setattr__(self, "name_order", tuple(self.name_order))
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
            # same iter() probe as Policy: curated message for
            # non-iterables (with the v1-flag hint where it applies),
            # caller-generator exceptions propagate from frozenset()
            try:
                iter(value)
            except TypeError:
                hint = (
                    "; v1's patronymic_name_order=True enabled both rules"
                    " -- patronymic_rules={PatronymicRule.EAST_SLAVIC, "
                    "PatronymicRule.TURKIC} (or pick one via "
                    "parser_for(locales.RU) / locales.TR_AZ)"
                    if f.name == "patronymic_rules" else ""
                )
                raise TypeError(
                    f"{f.name} must be an iterable, got {value!r}{hint}"
                ) from None
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
