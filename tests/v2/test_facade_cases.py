"""Facade runner (migration spec §5): the shared case table asserted
through HumanName. Deleted wholesale in 3.0 with the facade."""
import pytest

from nameparser import Policy
from nameparser._config_shim import Constants
from nameparser._facade import HumanName

from .cases import CASES, Case

_V1_KEY = {"given": "first", "family": "last"}  # identity for the rest

#: the one non-default maiden_delimiters shape the table exercises
#: ("nickname_bucket_wins_when_shared"): expressible in v1 Constants via
#: the delimiter-manager's parenthesis sentinel added to the maiden
#: bucket, leaving the nickname bucket at its (also-parenthesis-holding)
#: default -- see _config_shim._DelimiterManager.
_MAIDEN_PARENS = frozenset({("(", ")")})


def _constants_for(case: Case) -> Constants | None:
    """Translate the row's Policy to a Constants, or None if the policy
    has no v1 spelling (those rows are core-only)."""
    policy = case.policy or Policy()
    default = Policy()
    c = Constants()
    maiden_via_sentinel = (
        policy.maiden_delimiters == _MAIDEN_PARENS
        and policy.nickname_delimiters == default.nickname_delimiters
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
        or policy.nickname_delimiters != default.nickname_delimiters
        or (policy.maiden_delimiters != default.maiden_delimiters
            and not maiden_via_sentinel)
    )
    if unexpressible:
        return None
    if policy.patronymic_rules:
        c.patronymic_name_order = True
    if policy.middle_as_family:
        c.middle_name_as_last = True
    if policy.extra_suffix_delimiters:
        c.suffix_delimiter = next(iter(policy.extra_suffix_delimiters))
    if maiden_via_sentinel:
        # bucket-move idiom (see _DelimiterManager docstring): adds
        # parenthesis to maiden while nickname keeps its own default
        # (which already includes parenthesis) -- the nickname reading
        # still wins on a shared delimiter, matching the row's Policy.
        c.maiden_delimiters["parenthesis"] = "parenthesis"
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
