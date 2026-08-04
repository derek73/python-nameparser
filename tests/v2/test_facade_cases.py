"""Facade runner (migration spec §5): the shared case table asserted
through HumanName. Deleted wholesale in 3.0 with the facade."""
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
#: Two rows still skip, each needing a spelling of its own:
#: maiden_marker_delimited_beside_a_nickname_clause routes braces, which
#: v1 rejects with ValueError('references unknown regexes key'), and
#: maiden_marker_kyusei_delimited adds fullwidth parens alongside ASCII.
_MAIDEN_PARENS = frozenset({("(", ")")})


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
    unexpressible = (
        policy.name_order != default.name_order
        # script_orders has no v1 Constants spelling at all (the v1
        # surface is frozen), so a row opting out must SKIP here rather
        # than fail against the facade's inherited default.
        or policy.script_orders != default.script_orders
        or policy.lenient_comma_suffixes != default.lenient_comma_suffixes
        or policy.strip_emoji != default.strip_emoji
        or policy.strip_bidi != default.strip_bidi
        # Both delimiter clauses have to admit the bucket move: the
        # canonicalization that routes the pair to maiden is the same
        # step that takes it out of nickname, so a row expressible this
        # way necessarily differs from the default on BOTH.
        or (policy.nickname_delimiters != default.nickname_delimiters
            and not maiden_via_bucket_move)
        or (policy.maiden_delimiters != default.maiden_delimiters
            and not maiden_via_bucket_move)
    )
    if unexpressible:
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
