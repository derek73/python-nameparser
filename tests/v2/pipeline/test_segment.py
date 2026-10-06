from nameparser._lexicon import Lexicon
from nameparser._pipeline._extract import extract_delimited
from nameparser._pipeline._segment import segment
from nameparser._pipeline._state import ParseState, Structure
from nameparser._pipeline._tokenize import tokenize
import dataclasses

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


def test_single_pre_comma_word_never_suffix_comma() -> None:
    # v1: suffix-comma requires >1 word before the comma
    out = _segmented("Johnson, Jr.")
    assert out.structure is Structure.FAMILY_COMMA


def test_excess_non_suffix_segment_flags_comma_structure() -> None:
    out = _segmented("Smith, John, Extra, Jr.")
    assert out.structure is Structure.FAMILY_COMMA
    kinds = [a.kind for a in out.ambiguities]
    assert AmbiguityKind.COMMA_STRUCTURE in kinds


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


def test_strict_comma_suffixes_veto_lenient_only_members() -> None:
    # lenient_comma_suffixes=False: the post-comma test drops back to
    # the strict predicate, so initial-shaped suffix words no longer
    # qualify and the structure reads FAMILY_COMMA
    state = ParseState(
        original="John Ingram, V", lexicon=_LEX,
        policy=dataclasses.replace(Policy(), lenient_comma_suffixes=False))
    out = segment(tokenize(extract_delimited(state)))
    assert out.structure is Structure.FAMILY_COMMA


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


def _flip_reports(state: ParseState) -> list[list[str]]:
    return [_texts(state, a.indices) for a in state.ambiguities
            if a.kind is AmbiguityKind.SUFFIX_OR_NAME]


def test_the_run_test_declines_a_name_word_and_a_numeral() -> None:
    # a name word anywhere in the part, or a word that is neither
    # vocabulary nor a member, keeps the listing form -- and so does a
    # single-letter roman numeral, in any case, for its one-letter
    # shape (a multi-letter one runs: 'John Smith, III Ma')
    for text in ("John Smith, Jones Ma", "John Smith, PhD Jones Ma",
                 "John Smith, V Ma", "John Smith, PhD v Ma",
                 "John Smith, PhD Ma.", "John Smith, J. Ma"):
        out = _segmented(text)
        assert out.structure is Structure.FAMILY_COMMA, text
        assert not _flip_reports(out), text


def test_a_listed_surname_still_carries_the_name_contrast() -> None:
    # #564: a word a caller lists as a SURNAME is name text, so it
    # carries the contrast the comma caps reading needs
    # (`_vocab.claimed_as_non_name` leaves the surname and bound-given
    # lists out); `in_any_wordlist`, the caps shape's own "unlisted",
    # is a different question. A draft shared one predicate for both
    # and this read given 'XYZ'.
    from nameparser import Lexicon, Parser
    parser = Parser(lexicon=Lexicon.default().add(surnames={"smith", "jones"}))
    assert parser.parse("Smith Jones, XYZ").suffix == "XYZ"


def test_segment_records_the_case_fact_only_where_c2_asks() -> None:
    # (a-lazy): segment asks the fact only for C2's flag on a part past
    # the second comma that neither suffix reading recognizes case-free;
    # the comma decision reads classify's record of it (#613)
    assert _segmented("John Smith MA").one_case is None
    assert _segmented("John Smith, MA").one_case is None
    assert _segmented("Smith, John").one_case is None
    assert _segmented("John Smith, MD, Ma").one_case is False
