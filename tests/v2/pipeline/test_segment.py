from nameparser._lexicon import Lexicon
from nameparser._pipeline import run
from nameparser._pipeline._assemble import assemble
from nameparser._pipeline._extract import extract_delimited
from nameparser._pipeline._segment import segment
from nameparser._pipeline._state import ParseState, Structure
from nameparser._pipeline._tokenize import tokenize

from nameparser._policy import Policy
from nameparser._types import AmbiguityKind

# synthetic vocabulary: behavior given a lexicon, never default() contents
_LEX = Lexicon(
    suffix_acronyms=frozenset({"phd", "md", "do", "dds", "ma", "ed"}),
    suffix_acronyms_ambiguous=frozenset({"ma", "ed", "do"}),
    suffix_words=frozenset({"jr", "v"}),
)


def _segmented(text: str) -> ParseState:
    state = ParseState(original=text, lexicon=_LEX, policy=Policy())
    return segment(tokenize(extract_delimited(state)))


def _texts(state: ParseState, seg: tuple[int, ...]) -> list[str]:
    return [state.tokens[i].text for i in seg]


def test_no_comma() -> None:
    out = _segmented("John Smith")
    assert out.structure is Structure.NO_COMMA
    assert [_texts(out, s) for s in out.segments] == [["John", "Smith"]]


def test_family_comma() -> None:
    out = _segmented("Smith, John")
    assert out.structure is Structure.FAMILY_COMMA
    assert [_texts(out, s) for s in out.segments] == [["Smith"], ["John"]]


def test_family_comma_with_trailing_suffix_segment() -> None:
    out = _segmented("Smith, John, Jr.")
    assert out.structure is Structure.FAMILY_COMMA
    assert [_texts(out, s) for s in out.segments] == [["Smith"], ["John"], ["Jr."]]


def test_excess_non_suffix_segment_flags_comma_structure() -> None:
    out = _segmented("Smith, John, Extra, Jr.")
    assert out.structure is Structure.FAMILY_COMMA
    kinds = [a.kind for a in out.ambiguities]
    assert AmbiguityKind.COMMA_STRUCTURE in kinds


def test_the_comma_structure_report_names_the_fields_its_part_lands_in() -> None:
    # #629: a title word past the second comma reads as a title
    # (rules.md#C2, #603), so the part lands in two fields and the
    # report names what each word landed in, worded at assemble from
    # the final roles. A part that lands wholly in suffix keeps the
    # wording every release through 2.3.0 gave it.
    lex = _LEX.add(titles={"dr", "secretary", "state"}, conjunctions={"of"})

    def detail(text: str) -> str:
        [report] = [a for a in assemble(run(ParseState(
            original=text, lexicon=lex, policy=Policy()))).ambiguities
            if a.kind is AmbiguityKind.COMMA_STRUCTURE]
        return report.detail

    assert detail("John Smith, Jr., Dr. Bart") == (
        "segment 'Dr. Bart' beyond the recognized comma structures; "
        "consumed as title and suffix best-effort")
    assert detail("John Smith, Jr., Bart") == (
        "segment 'Bart' beyond the recognized comma structures; "
        "consumed as suffix best-effort")
    # C2: a part a connective joins into one title keeps the flag
    assert detail("John Smith, Jr., Secretary of State") == (
        "segment 'Secretary of State' beyond the recognized comma "
        "structures; consumed as title best-effort")


def test_empty_input_yields_no_segments() -> None:
    assert _segmented("").segments == ()


def test_comma_only_input_is_no_comma_structure() -> None:
    out = _segmented(",,,")
    assert out.structure is Structure.NO_COMMA
    assert out.segments == ()


def test_single_trailing_comma_is_cosmetic_and_dropped() -> None:
    # v1 parity: exactly ONE trailing comma is cosmetic and stripped
    # (segment.py's "pop the trailing empty bucket" step), so
    # 'Smith, John,' segments identically to 'Smith, John' -- unlike a
    # genuinely empty INTERIOR bucket ('Doe,, Jr.'), which stays
    # structural and keeps its position.
    out = _segmented("Smith, John,")
    assert out.structure is Structure.FAMILY_COMMA
    assert [_texts(out, s) for s in out.segments] == [["Smith"], ["John"]]


def test_leading_comma_yields_empty_first_segment() -> None:
    # A leading comma produces a non-trailing empty bucket, which is
    # structural (not cosmetic) and keeps its position as segment 0.
    out = _segmented(",John Smith")
    assert out.structure is Structure.FAMILY_COMMA
    assert [_texts(out, s) for s in out.segments] == [[], ["John", "Smith"]]


def test_a_tail_segment_of_leaning_credentials_is_not_flagged() -> None:
    # The third reading site, and the one place this design QUIETS a
    # report: 'DO' leans credential in a mixed-case name, so the third
    # segment is a credential run and rules.md#C2's flag stops firing.
    state = _segmented("Steven Hardman, MD, DO, DDS")
    assert not [a for a in state.ambiguities
                if a.kind is AmbiguityKind.COMMA_STRUCTURE]
    # the one-case spelling keeps today's reading, flag and all
    state = _segmented("STEVEN HARDMAN, MD, DO, DDS")
    assert [a for a in state.ambiguities
            if a.kind is AmbiguityKind.COMMA_STRUCTURE]


def test_segment_records_the_case_fact_only_where_c2_asks() -> None:
    # (a-lazy): segment asks the fact only for C2's flag on a part past
    # the second comma that neither suffix reading recognizes case-free;
    # the comma decision reads classify's record of it (#613)
    assert _segmented("John Smith MA").one_case is None
    assert _segmented("John Smith, MA").one_case is None
    assert _segmented("Smith, John").one_case is None
    assert _segmented("John Smith, MD, Ma").one_case is False
