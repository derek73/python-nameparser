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
    AmbiguityKind.SUFFIX_OR_NICKNAME: "JEFFREY (JD) BRICKEN",
    AmbiguityKind.SUFFIX_OR_NAME: "John Smith MA",
    # no emitter yet -- arrives with locale-pack order detection (2.x)
    AmbiguityKind.ORDER: None,
    # the emitter exists (script_segment), but nothing the DEFAULT
    # parser sees can reach it: the default surname vocabulary is
    # still empty, so no input splits at all. A trigger lands with
    # the Korean census list.
    AmbiguityKind.SEGMENTATION: None,
}


@pytest.mark.parametrize("kind", [
    # the per-entry comment above says WHY each None is None (no
    # emitter yet, or an emitter no default parse can reach)
    pytest.param(k, marks=pytest.mark.xfail(
        strict=True, reason=f"{k.value}: no trigger registered yet"))
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


def test_every_guarded_config_module_is_imported() -> None:
    """Import-time asserts only run if the module is imported.

    Five of the seven guarded config modules are pulled in by ``import
    nameparser``, but ``maiden_markers`` is lazy (imported inside
    ``_snapshot``/``_default_lexicon``), so its guard fired only
    incidentally, whenever some other test happened to build a default
    Lexicon. Importing them all here makes every guard unconditional.
    """
    import importlib

    for name in ("titles", "suffixes", "prefixes", "bound_first_names",
                 "conjunctions", "maiden_markers", "capitalization"):
        importlib.import_module(f"nameparser.config.{name}")
