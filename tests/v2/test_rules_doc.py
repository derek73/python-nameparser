"""Executes every example line in docs/design/rules/.

Wrong-on-arrival defense: each example runs against the live parser.
``deviates:`` examples assert TODAY's output (strict, like an xfail)
and additionally that intended != today, so a fixed bug forces the
marker out in the same PR.
"""
from __future__ import annotations

import importlib.util
import re

import pytest

from nameparser import Parser, parse, parser_for
from nameparser import locales
from nameparser._policy import Policy
from tests.v2.design_docs import RULES_DIR, read_rules_text
from tests.v2.rules_doc import (
    Example, Rule, parse_rules_doc, resolve_annotation)

RULES = parse_rules_doc(read_rules_text())


def test_doc_has_rules() -> None:
    assert RULES, "docs/design/rules/ holds no rules"


@pytest.mark.parametrize("rule", RULES, ids=lambda r: r.rule_id)
def test_every_rule_has_examples_and_boundary(rule: Rule) -> None:
    assert rule.examples, f"{rule.rule_id} has no examples"
    assert rule.has_boundary_or_waiver(), (
        f"{rule.rule_id}: add a '· boundary' example or an explicit "
        f"'no-boundary: <reason>'")


@pytest.mark.parametrize("rule", RULES, ids=lambda r: r.rule_id)
def test_every_rule_points_at_code_or_at_the_work(rule: Rule) -> None:
    """A normative rule names the code honoring it, or the issues that
    would ship it -- never neither, so an unimplemented rule cannot sit
    in the doc untracked, and never both.

    Scope, precisely: this test reads the DOC only, so it cannot tell
    that a tracked: rule has since been implemented -- adding the code
    and its citation while leaving tracked: in place passes here. That
    half is test_doc_citations.py::test_implemented_matches_citing_
    modules, which sees the citing modules. Neither test alone makes a
    stale pointer unrepresentable; the pair does.
    """
    assert rule.implemented or rule.tracked, (
        f"{rule.rule_id}: add 'implemented: <path>' or, if nothing "
        f"implements it yet, 'tracked: #N' naming the issues that would")
    assert not (rule.implemented and rule.tracked), (
        f"{rule.rule_id}: has both implemented: and tracked:; drop "
        f"tracked: once the rule ships")
    bad = [t for t in rule.tracked if not re.fullmatch(r"#\d+", t)]
    assert not bad, f"{rule.rule_id}: tracked: wants #N issue refs, got {bad}"


@pytest.mark.parametrize("rule", RULES, ids=lambda r: r.rule_id)
def test_every_rule_states_its_signal(rule: Rule) -> None:
    """What in the written name the rule reads, on its ``Signal:`` line
    (docs/design/AGENTS.md, "One rule per piece of evidence"). A hub
    also names the rules stating the signals it combines, after any
    signal it reads itself, which
    test_doc_citations.py::test_a_hub_names_each_rule_its_map_names
    holds to its map."""
    assert rule.signal is not None, (
        f"{rule.rule_id}: add a `Signal: <what it reads>` line directly "
        f"above its pointer line -- for example a count, a case "
        f"contrast, a shape, a neighbor, a position -- or `Signal: hub of "
        f"X1, X2` (after any signal of its own: `Signal: <its own>; hub "
        f"of X1, X2`) for a hub")


#: The README's recipe for the split candidates, verbatim; in grep's
#: basic syntax "+" is a literal plus.
_SPLIT_GREP = (
    r"grep -lE '^(    Signal:|\*\*Signal:\*\*).* \+ ' docs/design/rules/*.md")


#: _SPLIT_GREP's pattern in Python's syntax: either format's Signal line.
_SPLIT_PATTERN = r"^(    Signal:|\*\*Signal:\*\*).* \+ "


def test_the_split_candidate_recipe_lists_the_two_signal_rules() -> None:
    readme = (RULES_DIR / "README.md").read_text(encoding="utf-8")
    assert f"`{_SPLIT_GREP}`" in readme, (
        "rules/README.md's split-candidate grep changed; update "
        "_SPLIT_GREP and the translation below together")
    listed = {f.name.split("-")[0] for f in RULES_DIR.glob("*.md")
              if re.search(_SPLIT_PATTERN,
                           f.read_text(encoding="utf-8"), re.M)}
    assert listed == {r.rule_id for r in RULES
                      if r.signal and " + " in r.signal}
    # The tree holds no candidate since T4's split (2026-10-19), which
    # leaves the comparison above true of an empty set
    # however the recipe reads, so the two halves are also held to a
    # synthetic rule of each kind.
    for signal, candidate in (("a shape: x + a count: y", True),
                              ("a shape: x", False)):
        doc = ("X1. Rationale: r.\n    Statement.\n"
               '      "A B"                       →  given="A"  · boundary\n'
               f"    Signal: {signal}\n"
               "    history: decisions/P2 · implemented: nameparser/_parser.py\n")
        (rule,) = parse_rules_doc(doc)
        assert rule.signal == signal
        assert (" + " in rule.signal) is candidate
        assert bool(re.search(_SPLIT_PATTERN, doc, re.M)) is candidate
        skeleton = ("# X1 — one\n\n**When:** w.\n\n**Then:** t.\n\n"
                    "**Because:** b.\n\n---\n"
                    f"**Signal:** {signal}\n"
                    "**history:** decisions/P2 · **implemented:** "
                    "nameparser/_parser.py\n")
        (rule,) = parse_rules_doc(skeleton)
        assert rule.signal == signal
        assert bool(re.search(_SPLIT_PATTERN, skeleton, re.M)) is candidate


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
    # R5: the gate returns mixed-case input untouched, so an example
    # asserting what the REPAIR does must ask for it regardless
    if example.field == "capitalized_forced":
        return str(parsed.capitalized(force=True))
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


@pytest.mark.parametrize("decomposed", [
    "inž.",  # H2's abbreviation shape (#652): z + U+030C
    "John й Smith",  # P3's one-letter connective (#665)
    "É. y É. Smith",  # P3's initial beside a connective (#665)
    "김. 민준",  # H2's script veto on hangul typed as jamo (#665)
])
def test_the_nfd_examples_are_still_decomposed(decomposed: str) -> None:
    """The decomposed example lines in the rules are the only executable
    witnesses of its encoding clauses (H2, P3), and an editor or
    formatter that NFC-normalizes the file turns each into the
    composed case, which always worked and still passes. Each entry
    here is typed decomposed, which the first assert checks so that
    normalizing this file cannot hollow the test out either."""
    import unicodedata
    assert not unicodedata.is_normalized("NFC", decomposed)
    text = read_rules_text()
    assert decomposed in text, f"the NFD example {decomposed!r} was recomposed"
