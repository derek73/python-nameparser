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


def test_doc_has_rules() -> None:
    assert RULES, "rules.md holds no rules yet -- extraction not started"


@pytest.mark.parametrize("rule", RULES, ids=lambda r: r.rule_id)
def test_every_rule_has_examples_and_boundary(rule: Rule) -> None:
    assert rule.examples, f"{rule.rule_id} has no examples"
    assert rule.has_boundary_or_waiver(), (
        f"{rule.rule_id}: add a '· boundary' example or an explicit "
        f"'no-boundary: <reason>'")


def _check_diagnostic(example: Example) -> None:
    import re as _re
    from collections.abc import Callable
    from typing import cast

    from tests.v2.rules_doc import SUBJECTS
    fn = cast(Callable[[], object], SUBJECTS[example.subject or ""])
    pattern = _re.escape(str(example.value))
    if example.field == "warns":
        with pytest.warns(UserWarning, match=pattern):
            fn()
    else:
        with pytest.raises((TypeError, ValueError), match=pattern):
            fn()


def _pieces(text: str, policy: Policy | None) -> list[list[str]]:
    from nameparser._pipeline import run
    from nameparser._pipeline._state import ParseState
    from nameparser._parser import Parser as _P
    p = _P(policy=policy) if policy is not None else _P()
    state = run(ParseState(original=text, lexicon=p.lexicon,
                           policy=p.policy, segmenter=None))
    return [[state.tokens[i].text for i in piece]
            for seg in state.pieces for piece in seg]


def _run(example: Example) -> object:
    policy: Policy | None = None
    locale: str | None = None
    if example.annotation is not None:
        kind, obj = resolve_annotation(example.annotation)
        if kind == "policy":
            assert isinstance(obj, Policy)
            policy = obj
        elif kind == "locale":
            assert isinstance(obj, str)
            assert obj != "ja", (
                "ja needs the optional segmenter: use the "
                "[ja+segmenter] gate so CI without the extra skips it")
            locale = obj
        elif kind == "gated_locale":
            if importlib.util.find_spec("namedivider") is None:
                pytest.skip("optional extra absent; the ja-extra CI job "
                            "runs this")
            assert isinstance(obj, str)
            locale = obj
    if example.field == "pieces":
        return _pieces(example.text, policy)
    if locale is not None:
        parsed = parser_for(locales.get(locale)).parse(example.text)
    elif policy is not None:
        parsed = Parser(policy=policy).parse(example.text)
    else:
        parsed = parse(example.text)
    if example.field == "ambiguities":
        return tuple(a.kind.value for a in parsed.ambiguities)
    if example.field == "initials":
        return parsed.initials()
    if example.field == "capitalized":
        return str(parsed.capitalized())
    return getattr(parsed, example.field)


_EXAMPLES = [(r, e) for r in RULES for e in r.examples]
_EXAMPLE_IDS = [f"{r.rule_id}-{i}" for r in RULES
                for i, _ in enumerate(r.examples)]


@pytest.mark.parametrize("rule, example", _EXAMPLES, ids=_EXAMPLE_IDS)
def test_example(rule: Rule, example: Example) -> None:
    if example.field in ("warns", "raises"):
        _check_diagnostic(example)
        return
    actual = _run(example)
    if example.deviates_issue is not None:
        assert actual == example.today_value, (
            f"{rule.rule_id}: deviation #{example.deviates_issue} moved -- "
            f"update or remove the marker in the same PR")
        assert example.value != example.today_value, (
            f"{rule.rule_id}: intended equals today -- remove the marker")
    else:
        assert actual == example.value
