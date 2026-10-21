"""Unit tests for rules_doc.py: the example-line grammar, the annotation
registry, and the split of the rules text into rules and Backgrounds.

The fixtures are SYNTHETIC: they exercise the grammar and track no real
rule, so do not "fix" them when docs/design/rules/ changes. The rule
format itself is test_rules_skeleton.py's.
"""
from __future__ import annotations

import pytest

from tests.v2.rules_doc import (
    Example, parse_example_line, parse_rules_doc, prose_blocks,
    resolve_annotation)


def _rule(rid: str, fence: str = '"a b"  →  family="b"  · boundary') -> str:
    return (f"# {rid} — one\n\n**When:** w.\n\n**Then:** t.\n\n"
            f"**Because:** b.\n\n```\n{fence}\n```\n\n---\n"
            "**Signal:** a shape\n"
            "**history:** decisions/P2 · **implemented:** "
            "nameparser/_parser.py\n\n")


def test_an_example_line_parses_to_its_fields() -> None:
    assert parse_example_line(
        '"de la Vega"   →  family="de la Vega"', "X1", 1) == Example(
            text="de la Vega", annotation=None, field="family",
            value="de la Vega", boundary=False, deviates_issue=None,
            today_value=None)


def test_annotation_and_boundary_flags() -> None:
    ex = parse_example_line(
        '"Mesnil de"  family-first  →  family="Mesnil"  · boundary', "X1", 1)
    assert ex is not None
    assert ex.annotation == "family-first"
    assert ex.boundary is True


def test_deviates_marker() -> None:
    ex = parse_example_line(
        '"Swami Vivekananda"  →  family=""  deviates: #346 '
        '(today: family="Vivekananda")', "X1", 1)
    assert ex is not None
    assert ex.deviates_issue == 346
    assert ex.value == ""
    assert ex.today_value == "Vivekananda"


def test_nested_pieces_value_parses() -> None:
    ex = parse_example_line(
        '"de Mesnil"  family-first  →  pieces=[["de"], ["Mesnil"]]', "X1", 1)
    assert ex is not None
    assert ex.field == "pieces"
    assert ex.value == [["de"], ["Mesnil"]]


def test_a_subject_example_parses() -> None:
    ex = parse_example_line('[bad-name-order]  →  raises="name_order"',
                            "D2", 1)
    assert ex is not None
    assert ex.subject == "bad-name-order" and ex.text == ""


def test_prose_is_no_example() -> None:
    assert parse_example_line("the thing is read.", "X1", 1) is None


@pytest.mark.parametrize("line, match", [
    pytest.param('"input" -> family="x"', "does not parse", id="ascii-arrow"),
    pytest.param("“input”  →  family=\"x\"", "does not parse",
                 id="curly-quotes"),
    pytest.param('"a"  →  colour="x"', "not assertable",
                 id="unknown-field"),
    pytest.param('"a"  →  family="x"  deviates: #1 (today: given="y")',
                 "differs from the asserted field", id="deviates-field"),
])
def test_a_malformed_example_line_is_an_error(line: str, match: str) -> None:
    with pytest.raises(ValueError, match=match) as ei:
        parse_example_line(line, "X1", 7)
    assert str(ei.value).startswith("X1: line 7")


def test_registry_resolves_policies_and_gates() -> None:
    kind, obj = resolve_annotation("family-first")
    assert kind == "policy"
    kind, obj = resolve_annotation("[ru]")
    assert kind == "locale" and obj == "ru"
    kind, obj = resolve_annotation("[ja+segmenter]")
    assert kind == "gated_locale" and obj == "ja"
    with pytest.raises(KeyError):
        resolve_annotation("no-such-annotation")


_SECTION = "## A section (X)\n\nBackground: a section's words.\nWrapped.\n\n"


def test_the_text_splits_into_rules_and_backgrounds() -> None:
    doc = _SECTION + _rule("X1") + _rule("X2")
    assert [r.rule_id for r in parse_rules_doc(doc)] == ["X1", "X2"]
    prose = prose_blocks(doc)
    assert prose["X"] == ["Background: a section's words.", "Wrapped."]
    assert prose["X1"] == ["w.", "t.", "b."]


def test_a_duplicate_rule_id_is_an_error() -> None:
    with pytest.raises(ValueError, match="duplicate rule ID X1"):
        parse_rules_doc(_rule("X1") + _rule("X1"))


#: A rule in the retired block format, read as nothing, would never run
#: its examples, so each placement raises naming the format (#761).
@pytest.mark.parametrize("doc", [
    pytest.param('X1. Statement.\n      "a b"  →  family="b"\n',
                 id="outside-any-heading"),
    pytest.param(_SECTION + 'X1. Rationale: r.\n    Statement.\n',
                 id="after-a-background"),
    pytest.param('# X1 — one\n\nX1. Statement.\n      "a b"  →  family="b"\n',
                 id="under-a-rule-heading"),
    # inside a field, where it would have joined the prose (review)
    pytest.param(_rule("X1").replace("**Because:** b.\n",
                                     "**Because:** b.\n\nX2. Rationale: r.\n"),
                 id="inside-a-field"),
    pytest.param(_rule("X1").replace("**When:** w.\n",
                                     "**When:** w.\nX2. Rationale: r.\n"),
                 id="glued-to-a-field"),
])
def test_a_block_format_rule_is_refused(doc: str) -> None:
    with pytest.raises(ValueError, match="block format, which #761 retired"):
        parse_rules_doc(doc)


def test_a_background_may_wrap_onto_a_line_opening_with_a_quote() -> None:
    # the H and N Backgrounds do: a quote is no structure
    doc = "## A section (X)\n\nBackground: as in\n\"Rabbi Cohen\".\n\n"
    assert parse_rules_doc(doc) == []
    assert prose_blocks(doc)["X"] == ["Background: as in", '"Rabbi Cohen".']


@pytest.mark.parametrize("doc, match", [
    pytest.param("## A section (X)\n", "has no `Background:`", id="at-the-end"),
    pytest.param("## A section (X)\n\n" + _SECTION, "has no `Background:`",
                 id="before-another-section"),
    pytest.param("## A section (X)\n\n" + _rule("X1"), "has no `Background:`",
                 id="before-a-rule"),
    pytest.param(_SECTION + _SECTION, "headed twice", id="a-letter-twice"),
])
def test_a_section_needs_one_background(doc: str, match: str) -> None:
    with pytest.raises(ValueError, match=match):
        parse_rules_doc(doc)


def test_the_walkers_agree_on_a_section_glued_to_a_background() -> None:
    doc = (_SECTION.rstrip("\n") + "\n## B section (Y)\n\n"
           "Background: y.\n")
    assert parse_rules_doc(doc) == []
    assert prose_blocks(doc) == {
        "X": ["Background: a section's words.", "Wrapped."],
        "Y": ["Background: y."]}


def test_a_signal_line_outside_any_rule_is_an_error() -> None:
    doc = _SECTION + "**Signal:** stray\n"
    with pytest.raises(ValueError, match="outside any rule"):
        parse_rules_doc(doc)


#: Text outside any rule that is neither a section heading nor its one
#: Background paragraph. Read as nothing, each would neither run nor be
#: quotable, with the rule count still matching the file count (review).
@pytest.mark.parametrize("doc", [
    pytest.param(_rule("X1") + '### Notes\n\n```\n"A"  →  family="Q"\n```\n',
                 id="a-subheading-after-the-footer"),
    pytest.param(_rule("X1") + _rule("X2").replace("# X2 —", "# x2 —"),
                 id="a-misspelled-rule-heading"),
    pytest.param(_SECTION + '```\n"A B"  →  family="B"\n```\n',
                 id="a-fence-after-a-background"),
    pytest.param(_SECTION + "**When:** stray.\n",
                 id="a-field-in-a-section-file"),
    pytest.param(_SECTION + "A second paragraph.\n",
                 id="a-second-background-paragraph"),
    pytest.param("Background: with no section heading.\n",
                 id="a-background-with-no-heading"),
    # glued to the Background paragraph, with no blank line (review)
    pytest.param(_SECTION.rstrip("\n") + '\n```\n"A B"  →  family="B"\n```\n',
                 id="a-fence-glued-to-a-background"),
    pytest.param(_SECTION.rstrip("\n") + "\n### Notes\n",
                 id="a-heading-glued-to-a-background"),
    pytest.param(_SECTION.rstrip("\n") + "\n**When:** w.\n",
                 id="a-field-glued-to-a-background"),
    pytest.param(_SECTION.rstrip("\n") + "\n- an item\n",
                 id="a-list-glued-to-a-background"),
])


def test_text_outside_any_rule_is_an_error(doc: str) -> None:
    with pytest.raises(ValueError, match="text outside any rule"):
        parse_rules_doc(doc)


@pytest.mark.parametrize("doc", [
    pytest.param(_SECTION.rstrip("\n") + '\nit reads "A B"  →  family="B"\n',
                 id="on-a-wrapped-line"),
    # every real Background is one line: the example stands on it (review)
    pytest.param('## A section (X)\n\nBackground: as in "A B"  →  '
                 'family="B" here.\n', id="on-the-background-line"),
])
def test_an_example_in_a_background_is_an_error(doc: str) -> None:
    with pytest.raises(ValueError, match="an example in a Background"):
        parse_rules_doc(doc)


@pytest.mark.parametrize("line", [
    pytest.param('as in `"A B"  →  family="B"` here.', id="in-backticks"),
    pytest.param("2026. Then it changed.", id="a-year-opening-a-line"),
    pytest.param("12) items were seen.", id="a-number-past-1"),
])
def test_a_background_wraps_onto_prose(line: str) -> None:
    doc = _SECTION.rstrip("\n") + f"\n{line}\n"
    assert parse_rules_doc(doc) == []
    assert prose_blocks(doc)["X"][-1] == line


#: A rule heading with no field under it: before #761's retirement it
#: produced no rule and dropped its examples silently (review).
@pytest.mark.parametrize("body, match", [
    pytest.param("", "missing the \\*\\*When:\\*\\* field", id="empty"),
    pytest.param('```\n"a b"  →  family="b"\n```\n', "fence outside any field",
                 id="only-a-fence"),
    pytest.param("prose.\n", "a line outside a field", id="only-prose"),
])
def test_a_rule_heading_with_no_field_is_an_error(body: str,
                                                  match: str) -> None:
    with pytest.raises(ValueError, match=match):
        parse_rules_doc(f"# X1 — one\n\n{body}")
