"""Unit tests for the rules example-line grammar parser.

DOC below is a SYNTHETIC fixture: it exists only to exercise the
grammar and is never executed against the parser. Its rule IDs and
content are illustrative (they echo the spec's worked examples for
readability) and deliberately do NOT track docs/design/rules/ —
do not "fix" this fixture when the real doc changes.
"""
from __future__ import annotations

import pytest

from tests.v2.rules_doc import Example, parse_rules_doc

DOC = '''\
# Parsing rules (synthetic grammar fixture -- not the real rules)

## Particles

Background: particles link forward to a surname.

P2. Rationale: particles cannot themselves be a given name.
    A never-given particle left alone where the given name would
    go folds the whole name into the family.
      "de la Vega"                →  family="de la Vega"
      "Mesnil de"  family-first   →  family="Mesnil de"
      "de"                        →  given="de"  · boundary
    Accepted: a bare "de" keeps given="de".
    history: decisions/P2 · interacts: H1 · implemented: nameparser/_pipeline/_post_rules.py

P3. Statement with a tracked gap.
      "Swami Vivekananda"         →  family=""  deviates: #346 (today: family="Vivekananda")
    no-boundary: the rule is total over its vocabulary; no adjacent non-firing shape exists.
'''


def test_parses_rule_ids_and_examples() -> None:
    rules = parse_rules_doc(DOC)
    assert [r.rule_id for r in rules] == ["P2", "P3"]
    p2 = rules[0]
    assert len(p2.examples) == 3
    ex = p2.examples[0]
    assert ex == Example(text="de la Vega", annotation=None, field="family",
                         value="de la Vega", boundary=False,
                         deviates_issue=None, today_value=None)


def test_annotation_and_boundary_flags() -> None:
    p2 = parse_rules_doc(DOC)[0]
    assert p2.examples[1].annotation == "family-first"
    assert p2.examples[2].boundary is True
    assert p2.has_boundary_or_waiver()


def test_deviates_marker() -> None:
    p3 = parse_rules_doc(DOC)[1]
    ex = p3.examples[0]
    assert ex.deviates_issue == 346
    assert ex.value == ""
    assert ex.today_value == "Vivekananda"
    assert p3.no_boundary is not None


def test_pointer_line() -> None:
    p2 = parse_rules_doc(DOC)[0]
    assert p2.interacts == ("H1",)
    assert p2.implemented == ("nameparser/_pipeline/_post_rules.py",)


def test_unparseable_example_line_is_an_error() -> None:
    bad = 'X1. Statement.\n      "input" -> family="x"\n'
    with pytest.raises(ValueError, match="X1"):
        parse_rules_doc(bad)


def test_nested_pieces_value_parses() -> None:
    doc = ('X1. Structural claim.\n'
           '      "de Mesnil"  family-first  →  '
           'pieces=[["de"], ["Mesnil"]]\n'
           '    no-boundary: structural form.\n')
    ex = parse_rules_doc(doc)[0].examples[0]
    assert ex.field == "pieces"
    assert ex.value == [["de"], ["Mesnil"]]


def test_tolerated_marker_is_read_off_a_rule() -> None:
    """The 2026-09-01 comma demotion's vehicle, at the grammar layer.

    A rule may declare its examples ILLUSTRATIVE with a
    ``tolerated: <reason>`` line. The grammar's whole job is to make
    the line visible: the examples still parse and are still executed
    by test_rules_doc.py, and the marker tells a reader the rule
    describes best-effort behavior rather than promising it.

    The fixture is synthetic, like DOC above, and stays local to this
    test so the shared fixture keeps describing a normative doc.
    """
    doc = ('X1. Statement the parser only describes.\n'
           '      "Smith, John"  →  family="Smith"\n'
           '    tolerated: nobody writes this shape; current behavior only.\n'
           '    no-boundary: illustrative, not normative.\n')
    rule = parse_rules_doc(doc)[0]
    assert rule.tolerated == (
        "nobody writes this shape; current behavior only.")
    assert len(rule.examples) == 1, (
        "a tolerated rule keeps its examples -- the marker demotes the "
        "claim, it does not un-write the lines")


def test_a_normative_rule_carries_no_tolerated_marker() -> None:
    """The negative control for the test above: without the line the
    field is None, so `rule.tolerated is None` is a real question and
    not a constant the builder's skip could never fail on."""
    assert all(r.tolerated is None for r in parse_rules_doc(DOC))


#: Spellings an author reaching for `tolerated:` can plausibly write,
#: none of which _TOLERATED_RE accepts. Each is a near miss, and the
#: point of the parametrization is that every one of them RAISES: the
#: silent reading leaves the rule reading as a promise, exactly the
#: claim the line was written to withdraw, and files the line as
#: quotable statement prose -- with the whole suite green, since the
#: doc still parses and the examples still pass.
#:
#: The empty-reason row is a decision, not an oversight: the reason is
#: unvalidated free text, but a demotion nobody had to justify is the
#: one nobody reviews, so the validators' house rule (a reason is the
#: whole safeguard) applies here too.
@pytest.mark.parametrize("marker", [
    pytest.param("    Tolerated: capital T, otherwise well formed.",
                 id="capitalized-marker"),
    pytest.param("    tolerated : a space before the colon.",
                 id="space-before-the-colon"),
    pytest.param("    tolerated:", id="no-reason-at-all"),
    pytest.param("    tolerated:    ", id="whitespace-only-reason"),
    pytest.param("    toleraTED: shouting the middle.",
                 id="mixed-case-marker"),
])
def test_a_near_miss_tolerated_marker_is_an_error(marker: str) -> None:
    doc = ('X1. Statement the parser only describes.\n'
           '      "Smith, John"  →  family="Smith"\n'
           f'{marker}\n'
           '    no-boundary: illustrative, not normative.\n')
    with pytest.raises(ValueError, match="X1"):
        parse_rules_doc(doc)


def test_the_near_miss_lint_leaves_the_real_marker_alone() -> None:
    """The negative control for the battery above: the accepted
    spelling still parses to a reason, so the lint is rejecting near
    misses rather than the marker itself."""
    doc = ('X1. Statement the parser only describes.\n'
           '      "Smith, John"  →  family="Smith"\n'
           '    tolerated: reason.\n')
    assert parse_rules_doc(doc)[0].tolerated == "reason."


def test_registry_resolves_policies_and_gates() -> None:
    from tests.v2.rules_doc import resolve_annotation
    kind, obj = resolve_annotation("family-first")
    assert kind == "policy"
    kind, obj = resolve_annotation("[ru]")
    assert kind == "locale" and obj == "ru"
    kind, obj = resolve_annotation("[ja+segmenter]")
    assert kind == "gated_locale" and obj == "ja"
    with pytest.raises(KeyError):
        resolve_annotation("no-such-annotation")


_SIGNAL_DOC = ('X1. Statement.\n'
               '      "a b"  →  family="b"\n'
               '{signal}'
               '    implemented: nameparser/_parser.py\n')


def test_the_signal_line_is_read_off_a_rule() -> None:
    rule = parse_rules_doc(_SIGNAL_DOC.format(
        signal="    Signal: a count: one name word\n"))[0]
    assert rule.signal == "a count: one name word"
    assert rule.hub == ()
    assert rule.implemented == ("nameparser/_parser.py",)


def test_a_hub_signal_names_its_rules() -> None:
    rule = parse_rules_doc(_SIGNAL_DOC.format(
        signal="    Signal: hub of C3, C4, C12\n"))[0]
    assert rule.hub == ("C3", "C4", "C12")


def test_a_rule_without_a_signal_line_has_none() -> None:
    # The negative control: the real-doc test's `signal is not None`
    # is a question the parser can answer no to.
    assert parse_rules_doc(_SIGNAL_DOC.format(signal=""))[0].signal is None


_NEAR = "does not parse"         # the near-miss branch
_PLACE = "directly above"        # the placement branch
_HUB = "hub's signal line"       # the malformed-hub branch


#: Each raises, and from the branch its id names: a near miss read as
#: prose would leave the rule with no signal AND put the line into the
#: quotable statement, a wrapped or misplaced line would do the second,
#: and a malformed hub would read as a plain signal with its rules
#: unchecked.
@pytest.mark.parametrize("signal, branch", [
    pytest.param("    signal: lowercase.\n", _NEAR, id="lowercase"),
    pytest.param("    Signal : a space before the colon.\n", _NEAR,
                 id="space-before-the-colon"),
    pytest.param("    Signal:\n", _NEAR, id="empty"),
    pytest.param("    Signals: a count\n", _NEAR, id="plural"),
    pytest.param("    **Signal:** a count\n", _NEAR, id="bold"),
    pytest.param("    Signal\uff1a a count\n", _NEAR, id="fullwidth-colon"),
    pytest.param("    Signal: a count: one\n      name word\n", _PLACE,
                 id="wrapped"),
    pytest.param("    Signal: a count\n    Accepted: a clause after it.\n",
                 _PLACE, id="not-above-the-pointer"),
    pytest.param("    Signal: hub of C3 and C4\n", _HUB, id="malformed-hub"),
    pytest.param("    Signal: a shape; hub of C3 C4\n", _HUB,
                 id="malformed-hub-after-a-signal"),
    pytest.param("    Signal: a shape, hub of C3, C4\n", _HUB,
                 id="hub-after-a-comma"),
    pytest.param("    Signal: a shape;hub of C3, C4\n", _HUB,
                 id="hub-after-an-unspaced-semicolon"),
    pytest.param("    Signal: a shape — hub of C3, C4\n", _HUB,
                 id="hub-after-a-dash"),
    pytest.param("    Signal: hubs of C3, C4\n", _HUB, id="plural-hub"),
    pytest.param("    Signal: Hub of C3, C4\n", _HUB, id="capitalized-hub"),
    pytest.param("    Signal: hub of C3, C4.\n", _HUB,
                 id="hub-with-a-full-stop"),
    pytest.param("    Signal: hub: C3, C4\n", _HUB, id="hub-colon"),
    # refused by the first form of the check, which raised on the word
    # anywhere; kept so a narrowing cannot drop it (#737's lesson)
    pytest.param("    Signal: hub C3, C4\n", _HUB, id="hub-without-of"),
    pytest.param("    Signal: a shape; hub C3\n", _HUB,
                 id="hub-without-of-after-a-signal"),
])
def test_a_bad_signal_line_is_an_error(signal: str, branch: str) -> None:
    with pytest.raises(ValueError, match=branch):
        parse_rules_doc(_SIGNAL_DOC.format(signal=signal))


def test_a_word_holding_hub_is_a_plain_signal() -> None:
    # The converse of the hub rows: the near-miss test is not a
    # substring test.
    rule = parse_rules_doc(_SIGNAL_DOC.format(
        signal="    Signal: a shape: Hubert, a hub-like word\n"))[0]
    assert rule.hub == ()


#: Lines a rule block cannot hold. Read as nothing, each fell out of the
#: statement a citation quotes and the size budget counts in silence.
@pytest.mark.parametrize("line, match", [
    pytest.param("      Accepted: indented like an example.\n",
                 "no line a rule block holds", id="six-space-prose"),
    pytest.param("\tand a tab-indented clause.\n",
                 "no line a rule block holds", id="tab"),
    pytest.param("  and a two-space clause.\n",
                 "no line a rule block holds", id="two-space"),
    pytest.param("    Accepted : a space before the colon.\n",
                 "Accepted clause", id="accepted-space-colon"),
    pytest.param("    Accepted -- a dash.\n", "Accepted clause",
                 id="accepted-dash"),
    pytest.param("    Accepted (2026): a date.\n", "Accepted clause",
                 id="accepted-bracket"),
    pytest.param("    accepted: lowercase.\n", "Accepted clause",
                 id="accepted-lowercase"),
])
def test_a_line_no_rule_block_holds_is_an_error(line: str,
                                                match: str) -> None:
    doc = 'X1. Statement.\n' + line + '      "a b"  →  family="b"\n'
    with pytest.raises(ValueError, match=match):
        parse_rules_doc(doc)


def test_accepted_followed_by_a_word_is_prose() -> None:
    # P3's mid-clause "Accepted rather than repaired:" is the shape.
    doc = ('X1. Statement.\n    Accepted rather than repaired: prose.\n'
           '      "a b"  →  family="b"\n')
    assert parse_rules_doc(doc)[0].rule_id == "X1"


def test_a_second_signal_line_is_an_error() -> None:
    # Each line is well placed, above a pointer line, so this reaches the
    # one-per-rule branch rather than the placement one.
    doc = _SIGNAL_DOC.format(
        signal="    Signal: a count\n    implemented: x.py\n"
               "    Signal: a shape\n")
    with pytest.raises(ValueError, match="second"):
        parse_rules_doc(doc)


def test_a_signal_line_outside_a_rule_block_is_an_error() -> None:
    doc = "## A section (X)\n\n    Signal: stray\n    implemented: y\n"
    with pytest.raises(ValueError, match="outside any rule block"):
        parse_rules_doc(doc)


def test_a_hub_may_state_its_own_signals_first() -> None:
    rule = parse_rules_doc(_SIGNAL_DOC.format(
        signal="    Signal: a position: x + a shape: y; hub of C3, C4\n"))[0]
    assert rule.hub == ("C3", "C4")
    assert rule.signal == "a position: x + a shape: y; hub of C3, C4"


def test_a_signal_line_ending_the_text_is_an_error() -> None:
    with pytest.raises(ValueError, match="Signal"):
        parse_rules_doc('X1. Statement.\n    Signal: a count\n')
