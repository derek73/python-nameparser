"""Unit tests for the rules.md example-line grammar parser.

DOC below is a SYNTHETIC fixture: it exists only to exercise the
grammar and is never executed against the parser. Its rule IDs and
content are illustrative (they echo the spec's worked examples for
readability) and deliberately do NOT track docs/design/rules.md —
do not "fix" this fixture when the real doc changes.
"""
from __future__ import annotations

import pytest

from tests.v2.rules_doc import Example, parse_rules_doc

DOC = '''\
# Parsing rules (synthetic grammar fixture -- not the real rules.md)

## Particles

Background: particles link forward to a surname.

P2. Rationale: particles cannot themselves be a given name.
    A never-given particle left alone where the given name would
    go folds the whole name into the family.
      "de la Vega"                →  family="de la Vega"
      "Mesnil de"  family-first   →  family="Mesnil de"
      "de"                        →  given="de"  · boundary
    Accepted: a bare "de" keeps given="de".
    history: decisions.md#P2 · interacts: H1 · implemented: nameparser/_pipeline/_post_rules.py

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
    by test_rules_doc.py, and it is build_rules_corpus.py that acts
    on the flag by harvesting nothing from a marked rule. The other
    half of that promise -- that a tolerated rule really contributes
    no name to corpus_rules.jsonl -- is
    test_a_tolerated_rule_puts_no_name_in_the_rules_corpus in
    tests/v2/test_ledger_guards.py, which can see the corpus file.

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
#: silent reading leaves the rule normative, which means
#: build_rules_corpus.py harvests its examples into the contract
#: corpus and enforces at released baselines exactly the claim the
#: line was written to withdraw -- with the whole suite green, since
#: the doc still parses and the examples still pass.
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
