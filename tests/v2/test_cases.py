"""Core runner over the shared case table (spec §7.2). The facade
runner (migration plan) consumes the same CASES."""
import pytest

from nameparser import Parser

from .cases import CASES, Case

_FIELDS = ("title", "given", "middle", "family", "suffix", "nickname",
           "maiden")


@pytest.mark.parametrize("case", CASES, ids=lambda c: c.id)
def test_case(case: Case) -> None:
    parser = Parser(policy=case.policy) if case.policy else Parser()
    pn = parser.parse(case.text)
    actual = {f: getattr(pn, f) for f in _FIELDS if getattr(pn, f)}
    assert actual == case.expect, f"{case.text!r} ({case.classification})"
    kinds = sorted(a.kind.value for a in pn.ambiguities)
    assert kinds == sorted(case.ambiguities), \
        f"{case.text!r} ({case.classification})"
