"""Grammar tests for the skeleton rule format (rules_skeleton.py).

DOC is a SYNTHETIC fixture, like test_rules_doc_grammar.py's: it
exercises the grammar and tracks no real rule.
"""
from __future__ import annotations

import pytest

from tests.v2.rules_doc import parse_rules_doc, prose_blocks, split_accepted
from tests.v2.rules_skeleton import count_sentences

HEAD = '''\
# X1 — one

**When:** a name ends in a thing — "John Smith III".

**Then:** the thing is the suffix.

- **Reach:** only the last one.

**Because:** a thing at the end is how it is written. It is rare otherwise.

```
"John Smith III"  →  suffix="III"
```

**Except:**

- **One letter needs a word to spare.**
  ```
  "John V"  →  family="V"  · boundary
  ```

**Precedence:**

- **Before a comma**: C1 decides.

**Accepted:**

- A thing with a credential behind it is the family.
  ```
  "John Smith V PhD"  →  family="V"
  ```

---

**Signal:** a shape
**history:** decisions/P2 · **implemented:** nameparser/_parser.py
'''

OLD = '''\

# X2 — two

X2. Rationale: old format.
    The old statement.
      "Jane Doe"  →  family="Doe"  · boundary
    history: decisions/P3 · interacts: H1 · implemented: nameparser/_parser.py
'''

DOC = HEAD + OLD


def test_a_skeleton_rule_parses_its_fields() -> None:
    rules = parse_rules_doc(DOC)
    r = rules[0]
    sk = r.skeleton
    assert sk is not None
    assert sk.when == 'a name ends in a thing — "John Smith III".'
    assert sk.then == "the thing is the suffix."
    assert sk.because.startswith("a thing at the end")
    assert len(sk.then_bullets) == 1
    assert len(sk.excepts) == 1
    assert len(sk.precedence) == 1
    assert len(sk.accepted) == 1
    assert r.signal == "a shape"
    assert r.implemented == ("nameparser/_parser.py",)
    assert r.interacts == ()


def test_every_example_reaches_rule_examples() -> None:
    r = parse_rules_doc(DOC)[0]
    assert [(e.text, e.boundary) for e in r.examples] == [
        ("John Smith III", False), ("John V", True),
        ("John Smith V PhD", False)]
    assert r.skeleton is not None
    assert len(r.skeleton.excepts[0].examples) == 1
    assert r.has_boundary_or_waiver()


def test_an_old_rule_beside_a_skeleton_one_parses_as_before() -> None:
    rules = parse_rules_doc(DOC)
    assert rules[1].rule_id == "X2"
    assert rules[1].skeleton is None
    assert len(rules[1].examples) == 1
    assert rules[1].interacts == ("H1",)


def test_a_fence_under_a_bullet_belongs_to_it_and_a_column_0_fence_does_not(
) -> None:
    sk = parse_rules_doc(DOC)[0].skeleton
    assert sk is not None
    assert sk.then_bullets[0].examples == ()
    assert [e.text for e in sk.excepts[0].examples] == ["John V"]
    assert [e.text for e in sk.accepted[0].examples] == ["John Smith V PhD"]


def test_skeleton_prose_is_the_fields_without_examples_or_labels() -> None:
    prose = prose_blocks(DOC)["X1"]
    assert any(ln.startswith("One letter needs a word to spare")
               for ln in prose)
    assert not any("→" in ln or "**" in ln for ln in prose)
    assert prose[-1].startswith("Accepted: ")
    statement, clauses = split_accepted(prose)
    assert len(clauses) == 1
    assert statement[0].startswith("a name ends in a thing")
    assert prose_blocks(DOC)["X2"][0] == "Rationale: old format."


def test_tolerated_field_sets_rule_tolerated() -> None:
    doc = HEAD.replace(
        "**Then:**", "**Tolerated:** no convention writes it.\n\n**Then:**")
    r = parse_rules_doc(doc)[0]
    assert r.tolerated == "no convention writes it."
    assert r.skeleton is not None
    assert r.skeleton.tolerated == "no convention writes it."
    assert parse_rules_doc(HEAD)[0].tolerated is None


def test_a_hub_signal_and_no_boundary_in_the_footer() -> None:
    doc = HEAD.replace("**Signal:** a shape",
                       "no-boundary: total.\n**Signal:** hub of C3, C4"
                       ).replace("**Except:**", "**Except:**")
    r = parse_rules_doc(doc)[0]
    assert r.no_boundary == "total."
    assert r.hub == ("C3", "C4")


@pytest.mark.parametrize("text, n", [
    ("One. Two.", 2),
    ('Reads "John Smith V." here.', 1),
    ("Like e.g. C4 does.", 1),
    ("A `x. Y` b.", 1),
])
def test_count_sentences(text: str, n: int) -> None:
    assert count_sentences(text) == n


def test_a_column_0_fence_after_a_bullet_list_belongs_to_the_field(
) -> None:
    doc = _sub("- **Reach:** only the last one.\n",
               "- **Reach:** only the last one.\n\n```\n"
               '"John Smith IV"  →  suffix="IV"\n```\n')
    r = parse_rules_doc(doc)[0]
    assert r.skeleton is not None
    assert r.skeleton.then_bullets[0].examples == ()
    assert "John Smith IV" in [e.text for e in r.examples]


def _sub(old: str, new: str) -> str:
    assert old in HEAD
    return HEAD.replace(old, new, 1)


BAD = {
    "unclosed fence": (
        HEAD[:HEAD.index("**Except:**")].rstrip("\n").rsplit("\n", 1)[0]
        + "\n", "unclosed"),
    "a non-example in a fence": (
        _sub('"John V"  →  family="V"  · boundary',
             'John V is an example'), "every line inside a fence"),
    "unbolded When": (_sub("**When:**", "When:"), "label"),
    "lowercase bold": (_sub("**Then:**", "**then:**"), "label"),
    "Rationale": (_sub("**Because:**", "**Rationale:**"), "label"),
    "unknown label": (_sub("**Precedence:**", "**Foo:**"), "unknown"),
    "Then before When": (
        _sub('**When:** a name ends in a thing — "John Smith III".\n\n'
             '**Then:** the thing is the suffix.',
             '**Then:** the thing is the suffix.\n\n'
             '**When:** a name ends in a thing — "John Smith III".'),
        "out of order"),
    "two Because": (_sub("**Except:**", "**Because:** again.\n\n**Except:**"),
                    "repeated"),
    "missing Because": (
        _sub("**Because:** a thing at the end is how it is written. "
             "It is rare otherwise.\n\n", ""), "missing"),
    "example-less Except": (
        _sub('  ```\n  "John V"  →  family="V"  · boundary\n  ```\n', ""),
        "no example"),
    "four-sentence Because": (
        _sub("It is rare otherwise.", "It is rare. Very rare. Truly rare."),
        "sentences"),
    "two-sentence Then": (
        _sub("the thing is the suffix.", "the thing is. It is the suffix."),
        "one sentence"),
    "stray footer line": (_sub("**Signal:** a shape",
                               "stray words\n**Signal:** a shape"),
                          "footer"),
    "Signal not above pointer": (
        _sub("**Signal:** a shape\n", "**Signal:** a shape\n\n"),
        "directly above"),
    "interacts in footer": (
        _sub("**history:** decisions/P2", "**history:** decisions/P2 · "
             "**interacts:** H1"), "interacts: is retired"),
    "stray prose outside a field": (
        _sub("**Precedence:**\n\n- **Before a comma**: C1 decides.\n",
             "**Precedence:**\n\n- **Before a comma**: C1 decides.\n\n"
             "loose words\n"), "outside a field"),
    "an example line after Because, outside a fence": (
        _sub("It is rare otherwise.\n",
             'It is rare otherwise.\n"John Smith IV"  →  suffix="IV"\n'),
        "outside a fence"),
    "an example line under a bullet, outside a fence": (
        _sub("- **Before a comma**: C1 decides.\n",
             "- **Before a comma**: C1 decides.\n"
             '  "John Smith IV"  →  suffix="IV"\n'), "outside a fence"),
    "a malformed example line outside a fence": (
        _sub("It is rare otherwise.\n",
             'It is rare otherwise.\n"John Smith IV"  →  suffix=IV\n'),
        "outside a fence"),
    "a tilde fence": (
        _sub('```\n"John Smith III"  →  suffix="III"\n```\n',
             '~~~\n"John Smith III"  →  suffix="III"\n~~~\n'),
        "bare"),
    "a fence with a language tag": (
        _sub('```\n"John Smith III"  →  suffix="III"\n```\n',
             '```text\n"John Smith III"  →  suffix="III"\n```\n'),
        "bare"),
    "a tagged fence under a bullet": (
        _sub('  ```\n  "John V"', '  ```text\n  "John V"'), "bare"),
    "an empty Tolerated": (
        _sub("**Then:**", "**Tolerated:**\n\n**Then:**"), "Tolerated"),
    "colon outside the bold": (_sub("**When:**", "**When**:"), "label"),
}


@pytest.mark.parametrize("name", sorted(BAD))
def test_malformed_skeleton_raises(name: str) -> None:
    doc, fragment = BAD[name]
    with pytest.raises(ValueError, match="X1") as ei:
        parse_rules_doc(doc)
    assert fragment in str(ei.value)
