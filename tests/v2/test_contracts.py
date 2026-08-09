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
    # 남 and 남궁 are both shipped surnames, so longest-first picks
    # between two vocabulary-supported splits
    AmbiguityKind.SEGMENTATION: "남궁민수",
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

    ``maiden_markers`` and ``surnames`` are lazy (imported inside
    ``_snapshot``/``_default_lexicon``), so their guards fire only
    incidentally, whenever some other test happens to build a default
    Lexicon. Importing them all here makes every guard unconditional.

    The roster is DERIVED from the source tree, not listed: a
    hand-written tuple fails open, silently skipping the next guarded
    module nobody remembers to add.
    """
    import importlib
    import pathlib

    import nameparser.config

    config_dir = pathlib.Path(nameparser.config.__file__).parent
    # private modules excluded: _invariants DEFINES the guard (the
    # substring hits its own def) and holds no vocabulary of its own
    guarded = sorted(
        p.stem for p in config_dir.glob("*.py")
        if not p.stem.startswith("_")
        and "assert_normalized(" in p.read_text(encoding="utf-8"))
    assert guarded, (
        f"no guarded config module found in {config_dir} -- the "
        f"derivation broke, and an empty roster asserts nothing")
    for name in guarded:
        importlib.import_module(f"nameparser.config.{name}")


def test_every_vocabulary_constant_is_frozen() -> None:
    """A module vocabulary constant must not be mutable (#293).

    ``Lexicon.default()`` is ``functools.cache``d and reads these sets
    once, while the v1 shim's ``Constants`` copy from them at every
    construction. A runtime ``TITLES.add("dean")`` was therefore
    visible to a freshly built ``Constants`` and invisible to the
    cached default ``Lexicon`` -- two APIs disagreeing about their own
    defaults, decided by construction order. Frozen makes that
    unrepresentable: the mutation raises where it is written.

    The roster is DERIVED from the source tree for the same reason the
    guarded-module roster above is: a hand-written list fails open on
    the next module or the next constant.

    The deprecated alias modules are in the glob too, and contribute
    whatever the bridge has cached back into their globals -- so the
    NAMES collected here depend on what ran first. The verdict does
    not: a cached alias is the same object its 2.2 home contributes,
    and every one of those is frozen, so the cache can only ever add a
    duplicate entry under an old name.
    """
    import importlib
    import pathlib

    import nameparser.config

    config_dir = pathlib.Path(nameparser.config.__file__).parent
    checked = []
    offenders = []
    for path in sorted(config_dir.glob("*.py")):
        if path.stem.startswith("_"):
            continue
        module = importlib.import_module(f"nameparser.config.{path.stem}")
        for name, value in sorted(vars(module).items()):
            if not name.isupper() or not isinstance(value, (set, frozenset)):
                continue
            checked.append(f"{path.stem}.{name}")
            if not isinstance(value, frozenset):
                offenders.append(f"{path.stem}.{name}")
    assert checked, (
        "no vocabulary set constant found -- the derivation broke, and "
        "an empty roster asserts nothing")
    assert not offenders, (
        f"vocabulary constants must be frozensets (#293): {offenders}")
