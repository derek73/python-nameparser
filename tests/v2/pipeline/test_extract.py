import dataclasses

from nameparser._lexicon import Lexicon
from nameparser._pipeline._extract import extract_delimited
from nameparser._pipeline._state import ParseState
from nameparser._policy import Policy
from nameparser._types import AmbiguityKind, Role, Span


def _state(text: str, policy: Policy | None = None) -> ParseState:
    return ParseState(original=text, lexicon=Lexicon.empty(),
                      policy=policy or Policy())


def test_double_quoted_nickname_extracted() -> None:
    #             0123456789012345678
    out = extract_delimited(_state('John "Jack" Kennedy'))
    assert out.extracted == ((Role.NICKNAME, Span(6, 10)),)
    assert out.masked == (Span(5, 11),)


def test_parenthesized_nickname_extracted() -> None:
    out = extract_delimited(_state("John (Jack) Kennedy"))
    assert out.extracted == ((Role.NICKNAME, Span(6, 10)),)


def test_same_char_delimiter_needs_boundaries() -> None:
    # the apostrophe in O'Connor is not an opening quote
    out = extract_delimited(_state("Sean O'Connor"))
    assert out.extracted == () and out.masked == ()


def test_single_quoted_nickname_at_boundaries() -> None:
    #             01234567890123456789
    out = extract_delimited(_state("John 'Jack' Kennedy"))
    assert out.extracted == ((Role.NICKNAME, Span(6, 10)),)


def test_unbalanced_delimiter_left_literal_with_ambiguity() -> None:
    out = extract_delimited(_state('Jon "Nick Smith'))
    assert out.extracted == () and out.masked == ()
    assert len(out.ambiguities) == 1
    assert out.ambiguities[0].kind is AmbiguityKind.UNBALANCED_DELIMITER


def test_no_spurious_unbalanced_from_role_overlapping_pairs() -> None:
    # #273: '“' closes the German „…“ pair but OPENS the English “…”
    # pair, and '»' closes «…» but opens the reversed »…« pair. A
    # delimiter character consumed by another pair's successful
    # extraction is literal for every other pair -- it must not
    # surface as an unbalanced-delimiter ambiguity.
    policy = Policy(nickname_delimiters=frozenset(
        {("“", "”"), ("„", "“"), ("«", "»"), ("»", "«")}))
    for text, inner in (("Hans „Hansi“ Müller", "Hansi"),
                        ("Jean «Petit» Dupont", "Petit")):
        out = extract_delimited(_state(text, policy))
        assert [text[s.start:s.end] for _, s in out.extracted] == [inner]
        assert out.ambiguities == ()


def test_genuine_unbalanced_still_flagged_alongside_overlapping_pairs() -> None:
    # the suppression must not swallow REAL unbalanced opens: here the
    # German open has no close anywhere, and no other pair extracts
    policy = Policy(nickname_delimiters=frozenset(
        {("“", "”"), ("„", "“")}))
    out = extract_delimited(_state("Hans „Hansi Müller", policy))
    assert out.extracted == ()
    assert [a.kind for a in out.ambiguities] == [
        AmbiguityKind.UNBALANCED_DELIMITER]


def test_maiden_delimiters_route_to_maiden() -> None:
    policy = dataclasses.replace(
        Policy(),
        nickname_delimiters=frozenset({("'", "'"), ('"', '"')}),
        maiden_delimiters=frozenset({("(", ")")}),
    )
    out = extract_delimited(_state("Jane Smith (Jones)", policy))
    assert out.extracted == ((Role.MAIDEN, Span(12, 17)),)


def test_empty_enclosure_is_masked_but_not_extracted() -> None:
    out = extract_delimited(_state("John () Kennedy"))
    assert out.extracted == ()
    assert out.masked == (Span(5, 7),)


def test_multiple_extracts_and_no_overlap() -> None:
    #             0123456789012345678901234
    out = extract_delimited(_state('"Jack" John (Jonny) Kim'))
    roles = {span: role for role, span in out.extracted}
    assert roles == {Span(1, 5): Role.NICKNAME, Span(13, 18): Role.NICKNAME}


def test_adjacent_pairs_extract_separately() -> None:
    out = extract_delimited(_state('John "A" "B" Kim'))
    assert len(out.extracted) == 2


def test_close_at_end_of_string() -> None:
    out = extract_delimited(_state('John "Jack"'))
    assert out.extracted == ((Role.NICKNAME, Span(6, 10)),)


def test_unmatched_open_at_last_char() -> None:
    out = extract_delimited(_state('John "'))
    assert out.extracted == ()
    assert len(out.ambiguities) == 1


def test_nested_delimiters_inner_scan_order_pins() -> None:
    # parens win over quotes when the quote chars sit flush against the
    # parens (their word-boundary test fails); the inner quote chars
    # flow into the extracted span verbatim -- v1 parity, deliberate
    out = extract_delimited(_state('John ("Jack") Kim'))
    assert out.extracted == ((Role.NICKNAME, Span(6, 12)),)
