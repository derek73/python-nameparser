"""Core runner over the shared case table. The facade
runner (migration plan) consumes the same CASES."""
import pytest

from nameparser import Parser, Role, locales, parser_for

from .cases import CASES, Case

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
