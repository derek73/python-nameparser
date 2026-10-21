"""Grammar tests for the skeleton rule format (rules_skeleton.py).

HEAD is a SYNTHETIC fixture, like test_rules_doc_grammar.py's: it
exercises the grammar and tracks no real rule.
"""
from __future__ import annotations

import pytest

from tests.v2.rules_doc import parse_rules_doc, prose_blocks
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

def test_a_skeleton_rule_parses_its_fields() -> None:
    rules = parse_rules_doc(HEAD)
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


def test_every_example_reaches_rule_examples() -> None:
    r = parse_rules_doc(HEAD)[0]
    assert [(e.text, e.boundary) for e in r.examples] == [
        ("John Smith III", False), ("John V", True),
        ("John Smith V PhD", False)]
    assert r.skeleton is not None
    assert len(r.skeleton.excepts[0].examples) == 1
    assert r.has_boundary_or_waiver()


def test_a_fence_under_a_bullet_belongs_to_it_and_a_column_0_fence_does_not(
) -> None:
    sk = parse_rules_doc(HEAD)[0].skeleton
    assert sk is not None
    assert sk.then_bullets[0].examples == ()
    assert [e.text for e in sk.excepts[0].examples] == ["John V"]
    assert [e.text for e in sk.accepted[0].examples] == ["John Smith V PhD"]


def test_skeleton_prose_is_the_fields_without_examples_or_labels() -> None:
    prose = prose_blocks(HEAD)["X1"]
    assert any(ln.startswith("One letter needs a word to spare")
               for ln in prose)
    assert not any("→" in ln or "**" in ln for ln in prose)
    assert prose[0].startswith("a name ends in a thing")
    assert prose[-1].startswith("A thing with a credential behind it")


def test_tolerated_field_sets_rule_tolerated() -> None:
    doc = HEAD.replace(
        "**Then:**", "**Tolerated:** no convention writes it.\n\n**Then:**")
    r = parse_rules_doc(doc)[0]
    assert r.skeleton is not None
    assert r.skeleton.tolerated == "no convention writes it."
    head = parse_rules_doc(HEAD)[0].skeleton
    assert head is not None and head.tolerated is None


def test_a_hub_signal_and_no_boundary_in_the_footer() -> None:
    doc = HEAD.replace("**Signal:** a shape",
                       "no-boundary: total.\n**Signal:** hub of C3, C4")
    r = parse_rules_doc(doc)[0]
    assert r.no_boundary == "total."
    assert r.hub == ("C3", "C4")


@pytest.mark.parametrize("text, n", [
    ("One. Two.", 2),
    ('Reads "John Smith V." here.', 1),
    ("Like e.g. C4 does.", 1),
    ("A `x. Y` b.", 1),
    # an initial, and the title abbreviations, end no sentence (#768)
    ("V. Smith reads it.", 1),
    ("Read by J. Smith here.", 1),
    ("Dr. Smith reads it.", 1),
    ("Mr. Smith reads it.", 1),
    ("Mrs. Smith reads it.", 1),
    ("Ms. Smith reads it.", 1),
    ("St. Clair reads it.", 1),
    ("Prof. Smith reads it.", 1),
    ("John Smith Jr. Reads it.", 1),
    ("John Smith Sr. Reads it.", 1),
    # the boundary is still a terminator then a capital, after a word
    ("A word. B is next.", 2),
    ("It reads Dr. Then It. Stops.", 2),
    # not detected, as the docstring says: a sentence ending in an
    # initial, and a sentence opening in lowercase
    ("It ends in V. Then more.", 1),
    ("One. two.", 1),
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


def test_a_column_0_line_opening_with_a_hash_is_prose_not_a_heading(
) -> None:
    # only a markdown heading (a `#` run and a space) ends a rule (#768)
    doc = _sub("It is rare otherwise.\n",
               "It is rare otherwise.\n#761 settled it.\n")
    r = parse_rules_doc(doc)[0]
    assert r.skeleton is not None
    assert r.skeleton.because.endswith("#761 settled it.")
    assert r.signal == "a shape"
    assert len(r.examples) == 3


def test_a_bullet_continuation_opening_with_a_hash_is_prose() -> None:
    # #768's review: it raised "a nested list" (#761)
    doc = _sub("- **Before a comma**: C1 decides.\n",
               "- **Before a comma**: C1 decides.\n  #761 settled it.\n")
    r = parse_rules_doc(doc)[0]
    assert r.skeleton is not None
    assert r.skeleton.precedence[0].text.endswith("#761 settled it.")


@pytest.mark.parametrize("old, new", [
    ("It is rare otherwise.", "It is written `\"a\"  →  family=\"b\"`."),
    ("- **Before a comma**: C1 decides.",
     "- **Before a comma**: C1 decides `\"John V\"  →  family=\"V\"`."),
])
def test_an_assertion_inside_a_backtick_span_is_prose(old: str,
                                                      new: str) -> None:
    # writing ABOUT the grammar is no example (#768's review, #761)
    r = parse_rules_doc(_sub(old, new))[0]
    assert r.skeleton is not None
    assert len(r.examples) == 3


def test_tracked_in_the_footer_sets_rule_tracked() -> None:
    doc = _sub("**implemented:** nameparser/_parser.py",
               "**tracked:** #761, #768")
    r = parse_rules_doc(doc)[0]
    assert r.tracked == ("#761", "#768")
    assert r.implemented == ()


def test_bullet_examples_are_the_rule_examples_placed() -> None:
    # Bullet.examples is a placement view of rule.examples: the same
    # objects, each under at most one bullet
    r = parse_rules_doc(HEAD)[0]
    sk = r.skeleton
    assert sk is not None
    placed = [e for b in (*sk.then_bullets, *sk.excepts, *sk.precedence,
                          *sk.accepted) for e in b.examples]
    assert placed
    assert all(any(e is x for x in r.examples) for e in placed)
    assert len({id(e) for e in placed}) == len(placed)


BAD = {
    "unclosed fence": (
        HEAD[:HEAD.index("**Except:**")].rstrip("\n").rsplit("\n", 1)[0]
        + "\n", "unclosed"),
    "a non-example in a fence": (
        _sub('"John V"  →  family="V"  · boundary',
             'John V is an example'), "every line inside a fence"),
    "unbolded When": (_sub("**When:**", "When:"), "a label is bold"),
    "lowercase bold": (_sub("**Then:**", "**then:**"),
                       "unknown field label"),
    "Rationale": (_sub("**Because:**", "**Rationale:**"),
                  "unknown field label"),
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
    # the Signal line in the footer
    "a second Signal line": (
        _sub("**Signal:** a shape\n**history:**",
             "**Signal:** a shape\n**history:** decisions/P3\n"
             "**Signal:** a count\n**history:**"), "second"),
    "a Signal line ending the text": (
        HEAD.replace("**history:** decisions/P2 · **implemented:** "
                     "nameparser/_parser.py\n", ""), "the text ends"),
    "a wrapped Signal line": (
        _sub("**Signal:** a shape\n", "**Signal:** a shape:\nwrapped\n"),
        "directly above"),
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
    "colon outside the bold": (_sub("**When:**", "**When**:"),
                               "the colon goes inside the bold"),
    # an example where prose stands is never run (G1, #768)
    "an example on a label's line": (
        _sub('**When:** a name ends in a thing — "John Smith III".',
             '**When:** "John V"  →  family="V"'), "outside a fence"),
    "an example as a bullet's first line": (
        _sub("- **Before a comma**: C1 decides.\n",
             '- "John V"  →  family="V"\n'), "outside a fence"),
    "an unquoted example outside a fence": (
        _sub("It is rare otherwise.\n",
             'It is rare otherwise.\nJohn V  →  family="V"\n'),
        "outside a fence"),
    "an unquoted example on a label's line": (
        _sub("**Then:** the thing is the suffix.",
             '**Then:** John V  →  family="V"'), "outside a fence"),
    # the pointer line (G3)
    "a misspelled pointer key": (
        _sub("**implemented:**", "**implmented:**"), "pointer line"),
    "a pointer part with no colon": (
        _sub("**implemented:** nameparser", "implemented nameparser"),
        "pointer line"),
    "a repeated pointer key": (
        _sub("**history:** decisions/P2 ·",
             "**history:** decisions/P2 · **history:** decisions/P3 ·"),
        "repeated"),
    # empty structures (G4)
    "a bullet field with no bullets": (
        _sub("**Precedence:**\n\n- **Before a comma**: C1 decides.\n",
             "**Precedence:**\n"), "no bullets"),
    "an empty bullet": (
        _sub("- **Before a comma**: C1 decides.\n",
             "- **Before a comma**: C1 decides.\n- \n"), "empty bullet"),
    "an empty fence under a bullet": (
        _sub('  ```\n  "John Smith V PhD"  →  family="V"\n  ```\n',
             "  ```\n  ```\n"), "empty fence"),
    "an empty fence in a field": (
        _sub('```\n"John Smith III"  →  suffix="III"\n```\n',
             '```\n"John Smith III"  →  suffix="III"\n```\n\n```\n```\n'),
        "empty fence"),
    # Then (G5)
    "a star bullet under Then": (
        _sub("- **Reach:** only", "* **Reach:** only"), "a bullet is"),
    "a hyphen glued to the bold under Then": (
        _sub("- **Reach:** only", "-**Reach:** only"), "a bullet is"),
    # numbered, which markdown renders as a list (review)
    "a numbered list in a prose field": (
        _sub('**When:** a name ends in a thing — "John Smith III".\n',
             "**When:** a name holds:\n1. A comma.\n2. A title.\n"),
        "a bullet is"),
    "a bare numbered item ending a line": (
        _sub("It is rare otherwise.\n", "It is rare otherwise.\n\n1.\n"),
        "a bullet is"),
    "a numbered list with a parenthesis": (
        _sub("- **Reach:** only", "1) **Reach:** only"), "a bullet is"),
    "a star bullet under Except": (
        _sub("- **One letter", "* **One letter"), "a bullet is"),
    "a second Then paragraph": (
        _sub("**Then:** the thing is the suffix.\n",
             "**Then:** the thing is the suffix.\n\nand more of it.\n"),
        "Then is one paragraph"),
    # When and Tolerated as Then, which they accepted silently (#768)
    "a second When paragraph": (
        _sub('**When:** a name ends in a thing — "John Smith III".\n',
             '**When:** a name ends in a thing — "John Smith III".\n\n'
             "and more of it.\n"), "When is one paragraph"),
    "a second Tolerated paragraph": (
        _sub("**Then:**", "**Tolerated:** no convention writes it.\n\n"
             "and more of it.\n\n**Then:**"),
        "Tolerated is one paragraph"),
    # a bullet's continuation lines (#768)
    "a nested list under a bullet": (
        _sub("- **Before a comma**: C1 decides.\n",
             "- **Before a comma**: C1 decides.\n  - nested.\n"),
        "nested list"),
    # the other markers a nested list may wear (review)
    "a nested star list under a bullet": (
        _sub("- **Before a comma**: C1 decides.\n",
             "- **Before a comma**: C1 decides.\n  * nested.\n"),
        "nested list"),
    "a nested plus list under a bullet": (
        _sub("- **Before a comma**: C1 decides.\n",
             "- **Before a comma**: C1 decides.\n  + nested.\n"),
        "nested list"),
    "a nested numbered list under a bullet": (
        _sub("- **Before a comma**: C1 decides.\n",
             "- **Before a comma**: C1 decides.\n  1. nested.\n"),
        "nested list"),
    "a heading under a bullet": (
        _sub("- **Before a comma**: C1 decides.\n",
             "- **Before a comma**: C1 decides.\n  ## Heading\n"),
        "heading inside a bullet"),
    "an assertion outside a backtick span": (
        _sub("It is rare otherwise.",
             "It is `written` so →  family=\"V\" here."),
        "outside a fence"),
    # Tolerated, in the spellings an author reaching for it may write
    "an unbolded Tolerated": (
        _sub("**Then:**", "Tolerated: why.\n\n**Then:**"),
        "a label is bold"),
    "a lowercase Tolerated": (
        _sub("**Then:**", "**tolerated:** why.\n\n**Then:**"),
        "unknown field label"),
    "a Tolerated with its colon outside the bold": (
        _sub("**Then:**", "**Tolerated**: why.\n\n**Then:**"),
        "the colon goes inside the bold"),
    "a block-format tolerated line": (
        _sub("**Then:**", "tolerated: why.\n\n**Then:**"),
        "a label is bold"),
    # footer lines above the footer (G6)
    "a Signal line above the footer": (
        _sub("It is rare otherwise.\n",
             "It is rare otherwise.\nSignal: a shape\n"),
        "below the `---`"),
    "a bold Signal line above the footer": (
        _sub("It is rare otherwise.\n",
             "It is rare otherwise.\n**Signal:** a shape\n"),
        "below the `---`"),
    "a lowercase signal line in a bullet": (
        _sub("- **Before a comma**: C1 decides.\n",
             "- **Before a comma**: C1 decides.\n  signal: a shape\n"),
        "below the `---`"),
    "a no-boundary line above the footer": (
        _sub("It is rare otherwise.\n",
             "It is rare otherwise.\nno-boundary: total.\n"),
        "below the `---`"),
}


@pytest.mark.parametrize("name", sorted(BAD))
def test_malformed_skeleton_raises(name: str) -> None:
    doc, fragment = BAD[name]
    with pytest.raises(ValueError, match="X1") as ei:
        parse_rules_doc(doc)
    assert fragment in str(ei.value)


def _signal(text: str) -> str:
    return _sub("**Signal:** a shape\n", f"{text}\n")


#: Footer lines meant as the signal line but spelled otherwise: read as
#: anything else they would leave the rule with no signal.
@pytest.mark.parametrize("line", [
    pytest.param("signal: lowercase", id="lowercase-unbolded"),
    pytest.param("Signal: a count", id="unbolded"),
    pytest.param("**Signal :** a count", id="space-before-the-colon"),
    pytest.param("**Signal:**", id="empty"),
    pytest.param("**Signals:** a count", id="plural"),
    pytest.param("**Signal：** a count", id="fullwidth-colon"),
])
def test_a_misspelled_signal_line_is_an_error(line: str) -> None:
    with pytest.raises(ValueError, match="below the `---` footer only"):
        parse_rules_doc(_signal(line))


#: Each would read as a plain signal with its rules unchecked.
@pytest.mark.parametrize("signal", [
    pytest.param("hub of C3 and C4", id="malformed-hub"),
    pytest.param("a shape; hub of C3 C4", id="malformed-hub-after-a-signal"),
    pytest.param("a shape, hub of C3, C4", id="hub-after-a-comma"),
    pytest.param("a shape;hub of C3, C4",
                 id="hub-after-an-unspaced-semicolon"),
    pytest.param("a shape — hub of C3, C4", id="hub-after-a-dash"),
    pytest.param("hubs of C3, C4", id="plural-hub"),
    pytest.param("Hub of C3, C4", id="capitalized-hub"),
    pytest.param("hub of C3, C4.", id="hub-with-a-full-stop"),
    pytest.param("hub: C3, C4", id="hub-colon"),
    # refused by the first form of the check, which raised on the word
    # anywhere; kept so a narrowing cannot drop it (#737's lesson)
    pytest.param("hub C3, C4", id="hub-without-of"),
    pytest.param("a shape; hub C3", id="hub-without-of-after-a-signal"),
])
def test_a_malformed_hub_signal_is_an_error(signal: str) -> None:
    with pytest.raises(ValueError, match="a hub's signal"):
        parse_rules_doc(_signal(f"**Signal:** {signal}"))


def test_a_hub_may_state_its_own_signals_first() -> None:
    r = parse_rules_doc(_signal(
        "**Signal:** a position: x + a shape: y; hub of C3, C4"))[0]
    assert r.hub == ("C3", "C4")
    assert r.signal == "a position: x + a shape: y; hub of C3, C4"


def test_a_word_holding_hub_is_a_plain_signal() -> None:
    # the near-miss test is not a substring test
    r = parse_rules_doc(_signal("**Signal:** a shape: Hubert, hub-like"))[0]
    assert r.hub == ()
    assert r.signal == "a shape: Hubert, hub-like"


def test_a_rule_without_a_signal_line_has_none() -> None:
    # the negative control: test_rules_doc.py's `signal is not None` is
    # a question the parser can answer no to
    assert parse_rules_doc(_sub("**Signal:** a shape\n", ""))[0].signal is None
