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
