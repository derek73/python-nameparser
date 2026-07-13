import dataclasses

from nameparser._lexicon import Lexicon
from nameparser._pipeline._extract import extract_delimited
from nameparser._pipeline._state import ParseState
from nameparser._pipeline._tokenize import tokenize
from nameparser._policy import Policy
from nameparser._types import Role


def _tokenized(text: str, policy: Policy | None = None) -> ParseState:
    state = ParseState(original=text, lexicon=Lexicon.empty(),
                       policy=policy or Policy())
    return tokenize(extract_delimited(state))


def test_whitespace_split_with_spans() -> None:
    out = _tokenized("John  Smith")
    assert [(t.text, tuple(t.span)) for t in out.tokens] == [
        ("John", (0, 4)), ("Smith", (6, 11)),
    ]
    assert all(t.role is None for t in out.tokens)


def test_provenance_text_equals_original_slice() -> None:
    out = _tokenized(" Dr.  Juan  de la Vega ")
    for t in out.tokens:
        assert t.text == out.original[t.span.start:t.span.end]


def test_commas_are_separators_and_recorded() -> None:
    out = _tokenized("Smith, John")
    assert [t.text for t in out.tokens] == ["Smith", "John"]
    assert out.comma_offsets == (5,)


def test_fullwidth_and_arabic_commas_segment() -> None:
    out = _tokenized("سميث، جون")
    assert out.comma_offsets == (4,)
    out2 = _tokenized("山田，太郎")
    assert out2.comma_offsets == (2,)


def test_extracted_regions_are_skipped_and_tokenized_with_role() -> None:
    out = _tokenized('John "Jack Jr" Kennedy')
    main = [(t.text, t.role) for t in out.tokens if t.role is None]
    nick = [(t.text, t.role) for t in out.tokens if t.role is Role.NICKNAME]
    assert main == [("John", None), ("Kennedy", None)]
    assert nick == [("Jack", Role.NICKNAME), ("Jr", Role.NICKNAME)]
    # tokens are span-sorted overall
    starts = [t.span.start for t in out.tokens]
    assert starts == sorted(starts)


def test_comma_inside_extracted_region_is_not_an_offset() -> None:
    out = _tokenized('John "Jack, Jr" Kim')
    assert out.comma_offsets == ()
    nick = [t.text for t in out.tokens if t.role is Role.NICKNAME]
    assert nick == ["Jack", "Jr"]


def test_emoji_and_bidi_are_ignorable_by_policy() -> None:
    out = _tokenized("John‏ \U0001f600Smith")
    assert [t.text for t in out.tokens] == ["John", "Smith"]
    keep = dataclasses.replace(Policy(), strip_emoji=False, strip_bidi=False)
    out2 = _tokenized("John \U0001f600Smith", keep)
    assert [t.text for t in out2.tokens] == ["John", "\U0001f600Smith"]


def test_empty_and_whitespace_yield_no_tokens() -> None:
    assert _tokenized("").tokens == ()
    assert _tokenized("   ").tokens == ()
