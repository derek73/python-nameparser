"""Executes every example line in docs/design/rules.md.

Wrong-on-arrival defense: each example runs against the live parser.
``deviates:`` examples assert TODAY's output (strict, like an xfail)
and additionally that intended != today, so a fixed bug forces the
marker out in the same PR.
"""
from __future__ import annotations

import importlib.util

import pytest

from nameparser import Parser, parse, parser_for
from nameparser import locales
from nameparser._policy import Policy
from tests.v2.rules_doc import (
    RULES_DOC, Example, Rule, parse_rules_doc, resolve_annotation)

RULES = parse_rules_doc(RULES_DOC.read_text(encoding="utf-8"))


@pytest.mark.xfail(strict=True, reason="until the first extraction pass")
def test_doc_has_rules() -> None:
    assert RULES, "rules.md holds no rules yet -- extraction not started"


@pytest.mark.parametrize("rule", RULES, ids=lambda r: r.rule_id)
def test_every_rule_has_examples_and_boundary(rule: Rule) -> None:
    assert rule.examples, f"{rule.rule_id} has no examples"
    assert rule.has_boundary_or_waiver(), (
        f"{rule.rule_id}: add a '· boundary' example or an explicit "
        f"'no-boundary: <reason>'")


def _run(example: Example) -> object:
    if example.field in ("warns", "ambiguities", "pieces"):
        pytest.skip("assertion form lands with its first using rule")
    policy: Policy | None = None
    locale: str | None = None
    if example.annotation is not None:
        kind, obj = resolve_annotation(example.annotation)
        if kind == "policy":
            assert isinstance(obj, Policy)
            policy = obj
        elif kind == "locale":
            assert isinstance(obj, str)
            locale = obj
        elif kind == "gated_locale":
            if importlib.util.find_spec("namedivider") is None:
                pytest.skip("optional extra absent; the ja-extra CI job "
                            "runs this")
            assert isinstance(obj, str)
            locale = obj
    if locale is not None:
        parsed = parser_for(locales.get(locale)).parse(example.text)
    elif policy is not None:
        parsed = Parser(policy=policy).parse(example.text)
    else:
        parsed = parse(example.text)
    return getattr(parsed, example.field)


_EXAMPLES = [(r, e) for r in RULES for e in r.examples]
_EXAMPLE_IDS = [f"{r.rule_id}-{i}" for r in RULES
                for i, _ in enumerate(r.examples)]


@pytest.mark.parametrize("rule, example", _EXAMPLES, ids=_EXAMPLE_IDS)
def test_example(rule: Rule, example: Example) -> None:
    actual = _run(example)
    if example.deviates_issue is not None:
        assert actual == example.today_value, (
            f"{rule.rule_id}: deviation #{example.deviates_issue} moved -- "
            f"update or remove the marker in the same PR")
        assert example.value != example.today_value, (
            f"{rule.rule_id}: intended equals today -- remove the marker")
    else:
        assert actual == example.value
