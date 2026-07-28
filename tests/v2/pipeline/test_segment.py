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
    suffix_acronyms=frozenset({"phd"}),
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


def test_suffix_comma_when_all_rest_groups_are_suffixes() -> None:
    out = _segmented("John Smith, PhD")
    assert out.structure is Structure.SUFFIX_COMMA
    assert [_texts(out, s) for s in out.segments] == [["John", "Smith"], ["PhD"]]


def test_suffix_comma_lenient_accepts_initial_shaped_suffix_word() -> None:
    # "V" is initial-shaped; the strict test vetoes it, the post-comma
    # lenient test accepts suffix_words unconditionally (v1 parity)
    out = _segmented("John Ingram, V")
    assert out.structure is Structure.SUFFIX_COMMA


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
