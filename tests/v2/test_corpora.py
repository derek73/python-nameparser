"""The corpora under tools/differential/ that are GENERATED stay equal to
what their generators would write, and every corpus line is one the
snapshot can read.

A generated corpus that falls behind its source silently narrows the
names snapshot.jsonl watches: a case row or a rules example added
without regenerating is then read by nothing but its own test, which
moves with the change it pins. These pins make a stale corpus fail
instead.
"""
import json
from pathlib import Path

import pytest

from ._differential_fixtures import _TOOLS, load_tool

snapshot = load_tool("snapshot")


def _checked_in(name: str) -> list[object]:
    return [json.loads(line) for line in
            (_TOOLS / name).read_text(encoding="utf-8").splitlines()
            if line.strip()]


def test_cjk_corpus_matches_the_case_table() -> None:
    """corpus_cjk.jsonl is every distinct case-table text bearing a
    codepoint the script table classifies (#295; build_cjk_corpus.py
    says why no other corpus can carry these names)."""
    module = load_tool("build_cjk_corpus")
    assert _checked_in("corpus_cjk.jsonl") == module.selected_names(), (
        "corpus_cjk.jsonl is stale: regenerate with "
        "`uv run python tools/differential/build_cjk_corpus.py`")


def test_shapes_corpus_matches_the_case_table() -> None:
    """corpus_shapes.jsonl is generated from the shape-tagged case rows."""
    module = load_tool("build_shapes_corpus")
    assert _checked_in("corpus_shapes.jsonl") == module.selected(), (
        "corpus_shapes.jsonl is stale: regenerate with "
        "`uv run python tools/differential/build_shapes_corpus.py`")


def test_conventions_corpus_matches_its_table() -> None:
    """corpus_conventions.jsonl and conventions_fields.jsonl are
    generated from conventions.py's hand-written table (#686)."""
    module = load_tool("build_conventions_corpus")
    for name, expected in (("corpus_conventions.jsonl", module.selected()),
                           ("conventions_fields.jsonl", module.fields_rows())):
        assert _checked_in(name) == expected, (
            f"{name} is stale: regenerate with "
            "`uv run python tools/differential/build_conventions_corpus.py`")


def test_case_shape_ids_exist_in_the_inventory() -> None:
    """cases.py cannot import tools/, so Case.__post_init__ validates
    every shape tag against its own hand copy of the inventory's ids
    (cases._SHAPE_IDS). The equality holds that copy honest; the subset
    check catches a row tagged under a stale copy."""
    from tests.v2 import cases
    shapes = load_tool("shapes")
    tagged = {c.shape for c in cases.CASES if c.shape is not None}
    assert tagged <= set(shapes.SHAPES), (
        f"tests/v2/cases.py tags shape id(s) "
        f"{sorted(tagged - set(shapes.SHAPES))} that are not in "
        f"tools/differential/shapes.py's SHAPES; add the shape there "
        f"or fix the tag in cases.py")
    assert cases._SHAPE_IDS == set(shapes.SHAPES), (
        f"cases._SHAPE_IDS {sorted(cases._SHAPE_IDS)} != shapes.py's "
        f"{sorted(shapes.SHAPES)}; they are hand copies of one "
        f"inventory -- update whichever side is stale")


def test_rules_corpus_matches_the_rules_doc() -> None:
    """corpus_rules.jsonl is generated from docs/design/rules/'s own
    examples (#414), through the doc's parser. test_rules_doc executes
    every example against an expectation stored beside it, so a
    deliberate behavior change edits both and stays green; the snapshot
    is what shows the moved name in the diff."""
    module = load_tool("build_rules_corpus")
    assert _checked_in("corpus_rules.jsonl") == module.selected_names(), (
        "corpus_rules.jsonl is stale: regenerate with "
        "`uv run python tools/differential/build_rules_corpus.py`")

    # The equality cannot see a generator that silently selects LESS:
    # regenerating then agrees with the degraded selection. A rule
    # whose ID line stops matching, or that gains a heading mid-block,
    # loses its examples to the previous rule or to nothing.
    from .design_docs import read_rules_text
    from .rules_doc import parse_rules_doc
    rules = parse_rules_doc(read_rules_text())
    assert len(rules) >= 38, (
        f"docs/design/rules/ parsed to {len(rules)} rules, fewer than the 38 this "
        f"corpus was built from. A rule block that stops parsing hands "
        f"its examples to its neighbour and shrinks the corpus "
        f"silently. Ratchet this floor up when rules are added")
    empty = [r.rule_id for r in rules
             if not any(e.text for e in r.examples)]
    assert empty == ["D1", "D2"], (
        f"rules with no example NAME: {empty}. D1 and D2 are the "
        f"expected two -- their examples name a policy rather than a "
        f"name string. Any other rule contributing nothing means its "
        f"examples stopped being recognized as examples")


_ORDERS = {k: s.order for k, s in load_tool("shapes").SHAPES.items()}


@pytest.mark.parametrize("line,expected", [
    ('"John Smith"', ("John Smith", None)),
    ('{"name": "John Smith", "tests": ["t"]}', ("John Smith", None)),
    ('{"name": "Ménil Christophe du", "shape": 4}',
     ("Ménil Christophe du", "FAMILY_FIRST")),
])
def test_a_corpus_line_reads_as_a_name_and_order(
        line: str, expected: tuple[str, str | None]) -> None:
    assert snapshot._corpus_line(Path("corpus_x.jsonl"), line, _ORDERS) == expected


@pytest.mark.parametrize("line,match", [
    # A misspelled key would drop the shape the line declares and read
    # the name under the default order with nothing saying so.
    ('{"name": "John Smith", "shpae": 4}', r"corpus_x\.jsonl.*'shpae'"),
    ('{"name": "John Smith", "order": "FAMILY_FIRST"}', "'order'"),
    ('{"name": "John Smith", "tests": "t"}', "'tests' must be a list"),
    # bool is an int subclass and hash(True) == hash(1): unrefused, it
    # would read the name under shape 1's order.
    ('{"name": "John Smith", "shape": true}', "'shape' must name"),
    ('{"name": "John Smith", "shape": 99}', "'shape' must name"),
    ('{"nmae": "John Smith"}', "neither a JSON string"),
])
def test_a_malformed_corpus_line_is_a_hard_error(line: str, match: str) -> None:
    with pytest.raises(SystemExit, match=match):
        snapshot._corpus_line(Path("corpus_x.jsonl"), line, _ORDERS)



harvester = load_tool("build_issues_corpus")


def test_a_backticked_name_is_harvested() -> None:
    """This tracker writes names in backticks, because issues are
    markdown. Matching only quoted names left the corpus whose whole
    purpose is "what users reported" blind to how this project reports
    (#413).
    """
    assert harvester._harvest(
        "the tussenvoegsel in `Beethoven, Ludwig van` is filed behind "
        "the given name") == {"Beethoven, Ludwig van"}


def test_a_call_inside_backticks_yields_the_name_not_the_call() -> None:
    """The reason backticks are a SECOND PASS rather than a third
    alternative in one pattern.

    A reporter writes the failing input as a call inside a code span.
    Regex scanning takes the leftmost match, so a backtick alternative
    starts one character before the HumanName branch can and swallows
    the whole span -- harvesting the call and losing the name inside
    it. This is the bug the two-pass structure exists to prevent, and
    it is reachable from a single string.
    """
    got = harvester._harvest('reported as `HumanName("John  Q  Doe")`')
    assert got == {"John  Q  Doe"}

    # ... and a call anywhere in the span, not only at its start
    assert not any("HumanName(" in n for n in
                   harvester._harvest('see `Foo HumanName("Jane Roe")`'))


def test_a_sentence_is_not_a_name() -> None:
    """Prose is quoted and backticked as often as names are, and a
    capitalized phrase is well-formed enough that the character screen
    cannot see it.
    """
    for text in ("`What this gate does not cover` is the section",
                 "the note said `Takes everything` about it",
                 "`C is CONSTANTS` in that example",
                 "wrote `NO Latin twins on purpose` there",
                 "raised `TypeError: a bytes-like object is required`"):
        assert harvester._harvest(text) == set(), text


def test_the_sentence_screen_keeps_its_hands_off_names() -> None:
    """The screen matches a function word only where it is written
    LOWERCASE, which is what keeps it off names: a name capitalizes its
    words and a sentence's function words do not.

    Every name here contains a word that is in the stop list, and every
    one is a real naming convention -- Burmese, Norwegian, Estonian,
    Cantonese, Luhya, Dutch, Lakota. Without the case test the screen
    drops all of them, silently, from the one corpus meant to catch
    what users report.
    """
    for name in ("U Than Shwe", "Sven Are Olsen", "Kertu Must",
                 "Chan On Kei", "Wafula Were", "John Does",
                 "Marie Takes War Bonnet", "Rob And Beth Edmunds",
                 "Duke of Wellington", "Anh Do", "Will De Groot"):
        assert harvester._harvest(f"reported `{name}` today") == {name}, name
