"""Stable-string contract tests: every enum member and
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
    once, at its first call, while the v1 shim's ``Constants`` copy
    from them at every construction. A runtime ``TITLES.add("dean")``
    was therefore always visible to a freshly built ``Constants``, and
    visible to the default ``Lexicon`` only when it landed before the
    first parse -- after that the cache was already built and the same
    edit was invisible there. Two APIs disagreeing about their own
    defaults, decided by construction order, and no way from the
    mutating code to tell which branch it was on. Frozen makes that
    unrepresentable: the mutation raises where it is written.

    It also carries more than it did. ``_default_lexicon()`` used to
    wrap every constant in ``frozenset(...)`` on the way into the
    ``Lexicon``; #293 dropped the wraps because the sources are frozen,
    which makes this test the only thing anywhere that checks they
    still are. The import-time ``assert``\\ s in the config modules
    check normalization and subset relations, never mutability.

    The roster is DERIVED from the source tree for the same reason the
    guarded-module roster above is: a hand-written list fails open on
    the next module or the next constant. ``rglob``, not ``glob``, so a
    future ``config/`` subpackage is in scope from the day it lands
    rather than from the day someone notices.

    Scope stops at ``nameparser/config``, which is where the hazard is:
    three consumers read these constants at three different moments
    (the cached ``Lexicon.default()``, a per-construction ``Constants``,
    the import-time ``CONSTANTS``), so a mutable one lets two defaults
    disagree. A locale pack has one consumer and one moment -- the
    ``Lexicon(...)`` in its own module body, whose fields are frozen
    copies -- so ``locales/zh.py``'s ``_SURNAMES`` could not desync
    anything even as a plain ``set``. It is a ``frozenset`` anyway.

    The two deprecated alias modules are in the glob too and contribute
    nothing: the bridge deliberately does not write a resolved value
    back into their globals (see ``config/_deprecated.py``), so their
    ``vars()`` never gains a vocabulary name however often it is read,
    and the roster does not depend on what ran first.
    """
    import importlib
    import pathlib

    import nameparser.config

    # The two mapping constants, EXEMPT and named rather than dropped by
    # the isinstance filter without comment. REGEXES is a compiled-
    # pattern table rather than vocabulary and was never in #293's
    # scope. CAPITALIZATION_EXCEPTIONS is vocabulary-shaped and is a
    # decided, in-scope exemption, which means the split-default hazard
    # the freeze closes is STILL LIVE for it -- an edit reaches a
    # freshly built Constants and neither the cached Lexicon.default()
    # nor the shared CONSTANTS. Written down here, in docs/migrate.rst
    # and in AGENTS.md so it does not read as covered.
    exempt_mappings = {
        "capitalization.CAPITALIZATION_EXCEPTIONS",
        "regexes.REGEXES",
    }

    config_dir = pathlib.Path(nameparser.config.__file__).parent
    checked = []
    offenders = []
    exempt_seen = set()
    for path in sorted(config_dir.rglob("*.py")):
        relative = path.relative_to(config_dir).with_suffix("")
        if any(part.startswith("_") for part in relative.parts):
            continue
        stem = ".".join(relative.parts)
        module = importlib.import_module(f"nameparser.config.{stem}")
        for name, value in sorted(vars(module).items()):
            if not name.isupper():
                continue
            qualified = f"{stem}.{name}"
            if isinstance(value, dict):
                assert qualified in exempt_mappings, (
                    f"{qualified} is a mutable mapping constant with no "
                    f"recorded exemption; freeze it, or add it to "
                    f"exempt_mappings with the reason it stays mutable")
                exempt_seen.add(qualified)
                continue
            if not isinstance(value, (set, frozenset)):
                continue
            checked.append(qualified)
            if not isinstance(value, frozenset):
                offenders.append(qualified)
    assert exempt_seen == exempt_mappings, (
        f"exempt_mappings names {sorted(exempt_mappings - exempt_seen)}, "
        f"which the sweep never found -- a stale exemption hides the "
        f"next mutable mapping that inherits the name")
    # A FLOOR, not a presence check: `assert checked` is satisfied by
    # one surviving constant, so a filter or a path change that quietly
    # dropped twelve of the thirteen would still read as a pass. Twelve
    # distinct constants across seven modules, plus the thirteenth entry
    # -- particles.BOUND_GIVEN_NAMES, the same object as
    # bound_given_names.BOUND_GIVEN_NAMES, imported there for the
    # disjointness assert and counted once per module it appears in.
    # Raise this when a constant is added; a drop is the regression.
    assert len(checked) >= 13, (
        f"only {len(checked)} vocabulary set constants found under "
        f"{config_dir} ({checked}) -- the derivation shrank, and a "
        f"roster that shrinks silently stops guarding silently")
    assert not offenders, (
        f"vocabulary constants must be frozensets (#293): {offenders}")


def test_the_documented_replacements_for_an_in_place_edit_work() -> None:
    """``docs/migrate.rst``'s two recipes, as behavior (#293).

    Both live there as ``::`` literal blocks, which ``sphinx -b
    doctest`` never runs -- so the page that tells a 1.x caller what to
    do INSTEAD of ``TITLES.add("dean")`` was the one claim about the
    freeze with nothing checking it. "dean" is the canonical example
    for this: a common academic title and a common given name, so it is
    deliberately absent from the shipped ``TITLES`` and a caller who
    wants it has to add it themselves.
    """
    from nameparser import HumanName, Lexicon, Parser
    from nameparser.config import Constants
    from nameparser.config.titles import TITLES

    # what the freeze retired
    with pytest.raises(AttributeError):
        TITLES.add("dean")  # type: ignore[attr-defined]
    assert HumanName("Dean Smith").title == ""

    # recipe 1: a private Constants for the v1 API
    constants = Constants()
    constants.titles.add("dean")
    assert HumanName("Dean Smith", constants=constants).title == "Dean"

    # recipe 2: an extended Lexicon for the 2.0 API
    parser = Parser(lexicon=Lexicon.default().add(titles={"dean"}))
    assert parser.parse("Dean Smith").title == "Dean"
