"""Stable-string contract tests (core spec §7.4): every enum member and
stable tag has a canonical triggering input, parametrized by iterating
the registries -- a new member without an entry here fails loudly."""
import pytest

from nameparser import Parser, Policy, parse
from nameparser._policy import PatronymicRule
from nameparser._types import STABLE_TAGS, AmbiguityKind

_AMBIGUITY_TRIGGERS: dict[AmbiguityKind, str | None] = {
    AmbiguityKind.PARTICLE_OR_GIVEN: "Van Johnson",
    AmbiguityKind.UNBALANCED_DELIMITER: 'Jon "Nick Smith',
    AmbiguityKind.COMMA_STRUCTURE: "Smith, John, Extra, Jr.",
    # no emitter yet -- arrives with locale-pack order detection (2.x)
    AmbiguityKind.ORDER: None,
    # no emitter yet -- arrives with suffix/nickname refinement (2.x)
    AmbiguityKind.SUFFIX_OR_NICKNAME: None,
}


@pytest.mark.parametrize("kind", [
    pytest.param(k, marks=pytest.mark.xfail(
        strict=True, reason=f"{k.value}: emitter not yet implemented"))
    if k in _AMBIGUITY_TRIGGERS and _AMBIGUITY_TRIGGERS[k] is None else k
    for k in AmbiguityKind
])
def test_every_ambiguity_kind_has_a_registered_trigger(
        kind: AmbiguityKind) -> None:
    assert kind in _AMBIGUITY_TRIGGERS, (
        f"new AmbiguityKind {kind.value!r} needs a canonical trigger "
        f"(or an explicit None with its planned emitter)")
    trigger = _AMBIGUITY_TRIGGERS[kind]
    assert trigger is not None  # None triggers are strict-xfail marked
    kinds = {a.kind for a in parse(trigger).ambiguities}
    assert kind in kinds


_PATRONYMIC_TRIGGERS: dict[PatronymicRule, tuple[str, str]] = {
    # rule -> (input, expected given)
    PatronymicRule.EAST_SLAVIC: ("Сидоров Иван Петрович", "Иван"),
    PatronymicRule.TURKIC: ("Mammadova Aygun Ali kizi", "Aygun"),
}


@pytest.mark.parametrize("rule", list(PatronymicRule))
def test_every_patronymic_rule_has_a_trigger(rule: PatronymicRule) -> None:
    assert rule in _PATRONYMIC_TRIGGERS
    text, expected_given = _PATRONYMIC_TRIGGERS[rule]
    p = Parser(policy=Policy(patronymic_rules=frozenset({rule})))
    assert p.parse(text).given == expected_given


_TAG_TRIGGERS: dict[str, tuple[str, str]] = {
    # tag -> (input, token text carrying the tag)
    "particle": ("Juan de la Vega", "de"),
    "conjunction": ("Mr. and Mrs. John Smith", "and"),
    "initial": ("John A. Smith", "A."),
    "joined": ("John Ph. D.", "D."),
}


@pytest.mark.parametrize("tag", sorted(STABLE_TAGS))
def test_every_stable_tag_has_a_trigger(tag: str) -> None:
    assert tag in _TAG_TRIGGERS
    text, token_text = _TAG_TRIGGERS[tag]
    pn = parse(text)
    tagged = next(t for t in pn.tokens if t.text == token_text)
    assert tag in tagged.tags
