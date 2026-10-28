"""Stable-string contract tests: every enum member and
stable tag has a canonical triggering input, parametrized by iterating
the registries -- a new member without an entry here fails loudly."""
import pytest

from nameparser import Parser, Policy, parse
from nameparser._policy import PatronymicRule
from nameparser._types import STABLE_TAGS, AmbiguityKind

_AMBIGUITY_TRIGGERS: dict[AmbiguityKind, str | None] = {
    AmbiguityKind.PARTICLE_OR_GIVEN: "Van Johnson",
    # #479 row 1, all-upper: 'E' is a marked single-letter connective
    # and the name's one case says nothing about which reading is meant
    AmbiguityKind.CONJUNCTION_OR_INITIAL: "JOSE E MARIA SANTOS",
    AmbiguityKind.UNBALANCED_DELIMITER: 'Jon "Nick Smith',
    AmbiguityKind.COMMA_STRUCTURE: "Smith, John, Extra, Jr.",
    AmbiguityKind.SUFFIX_OR_NICKNAME: "JEFFREY (JD) BRICKEN",
    # Title case: capitals in a name of mixed case settle the word and
    # report nothing (rules/S6, #785)
    AmbiguityKind.SUFFIX_OR_NAME: "John Smith Ma",
    AmbiguityKind.GIVEN_OR_FAMILY: "Andrew",
    AmbiguityKind.TITLE_OR_NAME: "Lord Chancellor",
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

    Since the vocabulary moved to nameparser/vocab/*.toml, whose
    compiler checks it (tests/v2/test_vocab.py), the asserts left are
    on data still written in Python -- ``surnames`` today, which is
    lazy (imported inside ``_snapshot``/``_default_lexicon``), so its
    guard fires only incidentally, whenever some other test happens to
    build a default Lexicon. Importing them all here makes every guard
    unconditional.

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
    once, at its first call, so a runtime ``TITLES.add("dean")`` would
    reach the default ``Lexicon`` only when it landed before the first
    parse -- after that the cache is already built and the same edit is
    invisible. Through 2.x the v1 ``Constants`` also copied the sets at
    every construction, so the two APIs could disagree about their own
    defaults by construction order. Frozen makes that unrepresentable:
    the mutation raises where it is written.

    It also carries more than it did. ``_default_lexicon()`` used to
    wrap every constant in ``frozenset(...)`` on the way into the
    ``Lexicon``; #293 dropped the wraps because the sources are frozen,
    which makes this test the only thing anywhere that checks they
    still are. The vocabulary build's checks (tools/vocab/build.py)
    cover normalization and subset relations, never mutability.

    The roster is DERIVED from the source tree for the same reason the
    guarded-module roster above is: a hand-written list fails open on
    the next module or the next constant. ``rglob``, not ``glob``, so a
    future ``config/`` subpackage is in scope from the day it lands
    rather than from the day someone notices.

    Scope stops at ``nameparser/config``, which is where the hazard is:
    the constants are public, read by callers as well as by the cached
    ``Lexicon.default()``, so a mutable one lets a caller's copy and the
    default disagree. A locale pack has one consumer and one moment -- the
    ``Lexicon(...)`` in its own module body, whose fields are frozen
    copies -- so ``locales/zh.py``'s ``_SURNAMES`` could not desync
    anything even as a plain ``set``. It is a ``frozenset`` anyway.
    """
    import importlib
    import pathlib

    import nameparser.config

    # The two mapping constants, EXEMPT and named rather than dropped by
    # the isinstance filter without comment. REGEXES is a compiled-
    # pattern table rather than vocabulary and was never in #293's
    # scope. CAPITALIZATION_EXCEPTIONS is vocabulary-shaped and is a
    # decided, in-scope exemption, which means the hazard the freeze
    # closes is STILL LIVE for it -- an edit after the first parse
    # misses the cached Lexicon.default(). Written down here, in
    # docs/migrate.rst and in AGENTS.md so it does not read as covered.
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
    # dropped twelve of the thirteen would still read as a pass. Thirteen
    # distinct constants across seven modules (measured 2026-10-18; the
    # fourteenth entry before then was particles.BOUND_GIVEN_NAMES, an
    # import for a disjointness assert that became a vocabulary build
    # check). The private _compiled.py they are assigned from is skipped
    # with the other private modules: its objects are the same ones.
    # Raise this when a constant is added; a drop is the regression.
    assert len(checked) >= 13, (
        f"only {len(checked)} vocabulary set constants found under "
        f"{config_dir} ({checked}) -- the derivation shrank, and a "
        f"roster that shrinks silently stops guarding silently")
    assert not offenders, (
        f"vocabulary constants must be frozensets (#293): {offenders}")


def test_the_documented_replacements_for_an_in_place_edit_work() -> None:
    """``docs/migrate.rst``'s recipe, as behavior (#293).

    It lived there as a ``::`` literal block, which ``sphinx -b
    doctest`` never runs -- so the page that tells a 1.x caller what to
    do INSTEAD of ``TITLES.add("dean")`` was the one claim about the
    freeze with nothing checking it. "dean" is the canonical example
    for this: a common academic title and a common given name, so it is
    deliberately absent from the shipped ``TITLES`` and a caller who
    wants it has to add it themselves.
    """
    from nameparser import Lexicon, Parser, parse
    from nameparser.config.titles import TITLES

    # what the freeze retired
    with pytest.raises(AttributeError):
        TITLES.add("dean")  # type: ignore[attr-defined]
    assert parse("Dean Smith").title == ""

    # the recipe: an extended Lexicon
    parser = Parser(lexicon=Lexicon.default().add(titles={"dean"}))
    assert parser.parse("Dean Smith").title == "Dean"


@pytest.mark.parametrize("code", [
    "import nameparser",
    "from nameparser import *",
    "from nameparser.config.titles import TITLES",
    "from nameparser import parse; parse('John Smith')",
])
def test_imports_and_the_core_stay_quiet(code: str) -> None:
    import subprocess
    import sys

    # a fresh interpreter, since this one has imported everything
    result = subprocess.run(
        [sys.executable, "-W", "error", "-c", code],
        capture_output=True, text=True, check=False)
    assert result.returncode == 0, result.stderr


@pytest.mark.parametrize("module_name", [
    "nameparser.config.titles", "nameparser.config.suffixes"])
def test_star_import_binds_the_module_s_live_constants(module_name: str) -> None:
    """``from x import *`` consults ``__all__`` and nothing else.

    The expected set is DERIVED from the module rather than listed, so a
    constant added to ``suffixes``/``titles`` without a matching
    ``__all__`` entry fails here, and each is checked to be the module's
    own object, so an ``__all__`` entry routed elsewhere fails too.
    """
    import importlib
    import warnings

    module = importlib.import_module(module_name)
    # `TYPE_CHECKING` has the name shape of a constant and is not
    # vocabulary; every live constant is a frozenset (the 2.2 freeze)
    live = {n for n, v in vars(module).items()
            if n.isupper() and not n.startswith("_")
            and isinstance(v, frozenset)}
    assert live
    namespace: dict[str, object] = {}
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", DeprecationWarning)
        exec(f"from {module_name} import *", namespace)  # noqa: S102
    bound = {n for n in namespace if not n.startswith("__")}
    assert live <= bound
    for name in live:
        assert namespace[name] is vars(module)[name], name
