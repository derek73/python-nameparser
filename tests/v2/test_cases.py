"""Core runner over the shared case table. The facade
runner (migration plan) consumes the same CASES."""
import pytest

from nameparser import Parser, Policy, Role, locales, parser_for
from nameparser._policy import FAMILY_FIRST, FAMILY_FIRST_GIVEN_LAST

from .cases import CASES, Case

_ORDER_NAMES = {FAMILY_FIRST: "family-first",
                FAMILY_FIRST_GIVEN_LAST: "family-first-given-last"}

_FIELDS = tuple(r.value for r in Role)  # declaration order is canonical


def _parser_for_case(case: Case) -> Parser:
    if case.locale is not None:
        return parser_for(locales.get(case.locale))
    return Parser(policy=case.policy) if case.policy else Parser()


@pytest.mark.parametrize("case", CASES, ids=lambda c: c.id)
def test_case(case: Case) -> None:
    parser = _parser_for_case(case)
    pn = parser.parse(case.text)
    actual = {f: getattr(pn, f) for f in _FIELDS if getattr(pn, f)}
    assert actual == case.expect, f"{case.text!r} ({case.classification})"
    kinds = sorted(a.kind.value for a in pn.ambiguities)
    assert kinds == sorted(case.ambiguities), \
        f"{case.text!r} ({case.classification})"


#: The orders the invariant below is checked under. A case row carries
#: its own policy where it needs one; these are applied to every row
#: that does NOT, because the shapes this invariant is about are mostly
#: reached under a family-first order and the table has almost no rows
#: that declare one.
_INVARIANT_ORDERS = (None, FAMILY_FIRST, FAMILY_FIRST_GIVEN_LAST)


@pytest.mark.parametrize("order", _INVARIANT_ORDERS,
                         ids=lambda o: _ORDER_NAMES.get(o, "as-declared"))
@pytest.mark.parametrize("case", CASES, ids=lambda c: c.id)
def test_the_family_partitions_into_particles_and_base(
        case: Case, order: tuple[Role, Role, Role] | None) -> None:
    """rules.md#R2's invariant: a particle needs a base to attach to,
    so a family made only of particles is a family whose words are not
    acting as particles -- and therefore a non-empty family always has
    a non-empty base.

    Asserted as a PARTITION, which is the stronger form: the family's
    words are exactly the particles' words plus the base's words. That
    catches over-marking as well as under-marking, where "the base is
    non-empty" catches only the second. Word multisets rather than
    strings, because the family renders in written order while the two
    views render particles first ("Vega, de la" is family 'Vega de la',
    particles 'de la', base 'Vega').
    """
    if case.locale is not None or (order is not None and case.policy):
        pytest.skip("row carries its own policy or locale")
    parser = (_parser_for_case(case) if order is None
              else Parser(policy=Policy(name_order=order)))
    pn = parser.parse(case.text)
    if not pn.family:
        return
    assert pn.family_base, (
        f"{case.text!r}: family={pn.family!r} but family_base is "
        f"empty (particles={pn.family_particles!r})")
    assert sorted(pn.family.split()) == sorted(
        (pn.family_particles + " " + pn.family_base).split()), (
        f"{case.text!r}: family={pn.family!r} is not partitioned by "
        f"particles={pn.family_particles!r} + base={pn.family_base!r}")
