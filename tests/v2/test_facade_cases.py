"""Facade runner (mechanisms.md#FACADE-CONTRACT): the shared case
table asserted
through HumanName. Deleted wholesale in 3.0 with the facade."""
import dataclasses

import pytest

from nameparser import Policy
from nameparser._config_shim import Constants
from nameparser._facade import HumanName

from .cases import CASES, Case

_V1_KEY = {"given": "first", "family": "last"}  # identity for the rest

#: The parenthesis maiden shape. A row routing parens to maiden does
#: NOT carry the default nickname set: Policy's maiden-wins
#: canonicalization subtracts the pair from nickname_delimiters at
#: CONSTRUCTION, so the shape to match is the default MINUS the pair.
#: Comparing against the unsubtracted default is what kept this gate
#: false for every row until #329.
#:
#: The v1 side has two spellings and only one of them is equivalent.
#: ADDING parenthesis to the maiden bucket leaves the nickname bucket
#: holding it too, and v1 gives a shared pair to nickname -- measured on
#: "Baker (Johnson), Jenny", that spelling yields nickname Johnson and
#: an empty maiden, the reverse of what maiden_delimiters_win_when_shared
#: asserts. MOVING it (pop from nickname, assign to maiden) yields
#: maiden Johnson and an empty nickname, matching. That is the idiom
#: tests/test_nicknames.py already uses, and the one below.
#:
#: Which rows this leaves skipping is not described here but asserted,
#: by id, in test_core_only_rows_are_the_declared_ones below.
_MAIDEN_PARENS = frozenset({("(", ")")})

#: Policy fields _constants_for does not translate. A row moving one
#: off its default SKIPS: the facade would otherwise run it under the
#: field's inherited default and pass or fail on a knob the row never
#: asked for. Some have no v1 spelling at all -- script_orders and
#: segment_scripts, the v1 surface being frozen -- and the rest have
#: none this runner has ever needed to write.
_UNTRANSLATED = frozenset({
    "name_order",
    "script_orders",
    "segment_scripts",
    "lenient_comma_suffixes",
    "strip_emoji",
    "strip_bidi",
})

#: Expressible in exactly one shape, the parenthesis bucket move.
#: BOTH delimiter fields are listed because the canonicalization that
#: routes the pair to maiden is the same step that takes it out of
#: nickname, so a row expressible this way necessarily differs from
#: the default on both.
_BUCKET_MOVE_ONLY = frozenset({
    "nickname_delimiters",
    "maiden_delimiters",
})

#: Fields _constants_for writes into the Constants it returns.
_TRANSLATED = frozenset({
    "patronymic_rules",
    "middle_as_family",
    "extra_suffix_delimiters",
})

#: The non-locale rows the facade never sees. Held here rather than
#: described in prose, because pytest reports a skipped row exactly
#: like a row nobody wrote: reverting the _MAIDEN_PARENS shape above
#: to the unsubtracted default pushes every parenthesis-maiden row
#: into this set and turns nothing red.
_CORE_ONLY_IDS = frozenset({
    "leading_never_given_particle_two_leftovers_family_first",
    "leading_never_given_particle_two_leftovers_family_first_given_last",
    "maiden_marker_delimited_beside_a_nickname_clause",
    "maiden_marker_stops_the_leading_run_family_first",
    "maiden_marker_stops_the_leading_run_family_first_given_last",
    "maiden_marker_kyusei_delimited",
    "ko_honorific_period_under_strict_comma_suffixes",
    "ja_honorific_glued_family_comma_strict_knob",
    "ja_honorific_glued_family_comma_credential_pair_strict_knob",
})


def _constants_for(case: Case) -> Constants | None:
    """Translate the row's Policy to a Constants, or None if the policy
    has no v1 spelling (those rows are core-only)."""
    policy = case.policy or Policy()
    default = Policy()
    c = Constants()
    maiden_via_bucket_move = (
        policy.maiden_delimiters == _MAIDEN_PARENS
        and policy.nickname_delimiters
        == default.nickname_delimiters - _MAIDEN_PARENS
    )
    # field by field, off the dataclass rather than by hand: a field
    # named in no table above would be admitted here and then run
    # under the facade's default for it (see
    # test_every_policy_field_is_translated_or_skipped).
    moved = {f.name for f in dataclasses.fields(Policy)
             if getattr(policy, f.name) != getattr(default, f.name)}
    if moved & _UNTRANSLATED or (moved & _BUCKET_MOVE_ONLY
                                 and not maiden_via_bucket_move):
        return None
    if policy.patronymic_rules:
        c.patronymic_name_order = True
    if policy.middle_as_family:
        c.middle_name_as_last = True
    if policy.extra_suffix_delimiters:
        c.suffix_delimiter = next(iter(policy.extra_suffix_delimiters))
    if maiden_via_bucket_move:
        # pop, not assign: leaving parenthesis in the nickname bucket
        # would give v1's shared-pair reading, which goes to nickname.
        c.maiden_delimiters["parenthesis"] = c.nickname_delimiters.pop(
            "parenthesis")
    return c


def test_every_policy_field_is_translated_or_skipped() -> None:
    # a Policy field in none of the three tables is neither rejected
    # nor written into the Constants, so a row setting it is ADMITTED
    # and then asserted under the facade's default value for that
    # field. segment_scripts sat in exactly that state until
    # 2026-08-03, invisibly, because no row set it. Same job
    # test_policy_patch_mirrors_policy_field_names does one file over.
    assert (_UNTRANSLATED | _BUCKET_MOVE_ONLY | _TRANSLATED
            == {f.name for f in dataclasses.fields(Policy)})


def test_core_only_rows_are_the_declared_ones() -> None:
    # the gate that decides this is one comparison away from claiming
    # no policy is expressible (see _MAIDEN_PARENS), and every row it
    # wrongly rejects leaves the suite green -- a skip reads as a pass.
    assert {case.id for case in CASES
            if case.locale is None
            and _constants_for(case) is None} == _CORE_ONLY_IDS


@pytest.mark.parametrize("case", CASES, ids=lambda c: c.id)
def test_facade_case(case: Case) -> None:
    if case.locale is not None:
        # v1 Constants' patronymic bool enables BOTH the East Slavic and
        # Turkic rules at once, so it cannot express a single-rule pack
        # faithfully -- these rows are core-only (proven via parser_for
        # in test_cases.py instead).
        pytest.skip("locale rows are core-only")
    constants = _constants_for(case)
    if constants is None:
        pytest.skip("policy not expressible through v1 Constants")
    name = HumanName(case.text, constants=constants)
    for field, expected in case.expect.items():
        assert getattr(name, _V1_KEY.get(field, field)) == expected, (
            f"{case.id}: {field}")
    for field in {"title", "given", "middle", "family", "suffix",
                  "nickname", "maiden"} - set(case.expect):
        assert getattr(name, _V1_KEY.get(field, field)) == "", (
            f"{case.id}: {field} expected empty")
