import dataclasses

import pytest

from nameparser import parse
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


def test_mixed_conventions_both_extract_leftmost_wins() -> None:
    # Review finding (2026-07-19, three agents independently): with the
    # default #273 pairs, a string containing TWO delimited asides in
    # different conventions mis-extracted -- the earlier-sorted pair
    # claimed the other's close character ('“' closes „…“ but opens
    # “…”) as its own open and swallowed a bogus span across the real
    # boundary, silently dropping the legitimate match. The scan must
    # be position-driven: the leftmost genuine opener wins.
    text = "Hans „Erster“ und “Zweiter” Müller"
    out = extract_delimited(_state(text))
    assert [text[s.start:s.end] for _, s in out.extracted] == [
        "Erster", "Zweiter"]
    assert out.ambiguities == ()


def test_mixed_guillemet_directions_both_extract() -> None:
    text = "Jean «Petit» Dupont »Rex« Martin"
    out = extract_delimited(_state(text))
    assert [text[s.start:s.end] for _, s in out.extracted] == [
        "Petit", "Rex"]
    assert out.ambiguities == ()


def test_mixed_conventions_across_maiden_and_nickname_buckets() -> None:
    # same shape across ROLES: guillemets routed to maiden must not let
    # the reversed nickname pair steal the maiden close
    policy = Policy(maiden_delimiters=frozenset({("«", "»")}))
    text = "Jean «Dupont» Martin »Rex« Smith"
    out = extract_delimited(_state(text, policy))
    got = {(role, text[s.start:s.end]) for role, s in out.extracted}
    assert got == {(Role.MAIDEN, "Dupont"), (Role.NICKNAME, "Rex")}
    assert out.ambiguities == ()


def test_extraction_and_genuine_unbalanced_coexist() -> None:
    # the kept path: a successful extraction must not suppress a REAL
    # dangling open elsewhere in the same string
    text = 'John (Jack) Smith "Extra'
    out = extract_delimited(_state(text))
    assert [text[s.start:s.end] for _, s in out.extracted] == ["Jack"]
    assert [a.kind for a in out.ambiguities] == [
        AmbiguityKind.UNBALANCED_DELIMITER]


def test_same_char_bulk_unbalanced_filtered_by_other_pairs_mask() -> None:
    # the same-char forward-scan records EVERY dangling quote; one that
    # sits inside a region another pair successfully extracts is
    # literal content, not a dangling delimiter -- only the truly
    # dangling ones surface. All three quotes here fail the close-walk
    # (no quote is followed by a boundary), so the bulk pass records
    # all three; the middle one lands inside the paren match.
    #       01234567890123456789
    text = 'Jon "A (x "y) Bob "C'
    out = extract_delimited(_state(text))
    assert [text[s.start:s.end] for _, s in out.extracted] == ['x "y']
    # quotes at 4 and 18 are genuinely dangling; the one at 10 was
    # consumed by the parenthesized extraction
    assert sorted(a.detail for a in out.ambiguities) == [
        "unmatched '\"' at offset 18; treated as literal text",
        "unmatched '\"' at offset 4; treated as literal text",
    ]
    assert all(a.kind is AmbiguityKind.UNBALANCED_DELIMITER
               for a in out.ambiguities)


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


@pytest.mark.parametrize(("text", "char"), [
    ("John Smith)", ")"),
    ("John Jack) Smith", ")"),
    ('John Smith"', '"'),
    ("John Smith」", "」"),          # a #273 typographic pair
])
def test_unmatched_close_is_reported(text: str, char: str) -> None:
    # the scan is opener-driven, so a close with no open to its left was
    # never in its search space and went unreported -- even though the
    # AmbiguityKind docstring promises "or closed without opening"
    kinds = [a.kind for a in parse(text).ambiguities]
    assert kinds == [AmbiguityKind.UNBALANCED_DELIMITER]
    assert char in parse(text).ambiguities[0].detail


def test_word_final_apostrophe_is_not_an_unbalanced_delimiter() -> None:
    # ambiguity means the part could REASONABLY read two ways where it
    # sits. A "'" after a word character is an apostrophe -- it is the
    # one delimiter character that occurs inside and at the end of real
    # name parts, and the least likely to mark a nickname. The same
    # position with a quote IS ambiguous, because quotes do not appear
    # inside names. (#273 excluded the curly apostrophe from the
    # delimiters entirely for this reason; the straight one is a
    # delimiter, so it needs the carve-out here instead.)
    assert parse("Mari' Aube'").ambiguities == ()
    assert parse("Ali Baba'").ambiguities == ()
    quoted = parse('Mari" Aube"')
    assert [a.kind for a in quoted.ambiguities] == \
        [AmbiguityKind.UNBALANCED_DELIMITER] * 2


def test_apostrophe_after_a_space_is_still_reported() -> None:
    # the carve-out is about what PRECEDES the character: an apostrophe
    # opening a quote is still an unmatched open when nothing closes it
    assert [a.kind for a in parse("John 'Jack Smith").ambiguities] == \
        [AmbiguityKind.UNBALANCED_DELIMITER]


@pytest.mark.parametrize("text", [
    "Brian O'connor",       # apostrophe mid-word, not a delimiter
    "O'B. John Smith",
    "The Queen's Bench",
    "John (Jack) Smith",    # matched pair
    'John "Jack" Smith',
])
def test_no_spurious_unmatched_close(text: str) -> None:
    assert [a for a in parse(text).ambiguities
            if a.kind is AmbiguityKind.UNBALANCED_DELIMITER] == []


def test_unmatched_open_is_not_double_reported_as_a_close() -> None:
    # a symmetric delimiter can satisfy both boundary tests; it must
    # still produce exactly one ambiguity
    assert len(parse('John " Smith').ambiguities) == 1
    assert len(parse('Jon "Nick Smith').ambiguities) == 1


@pytest.mark.parametrize(("text", "expected"), [
    ('Jon "Nick Smith', '"Nick'),
    ("John (Jack Smith", "(Jack"),
    ("John Smith)", "Smith)"),
    ("John Jack) Smith", "Jack)"),
])
def test_unbalanced_delimiter_points_at_its_token(
    text: str, expected: str
) -> None:
    # the kind was documented as possibly carrying no tokens, but the
    # stray character does survive into one -- without it the ambiguity
    # is locatable only by parsing an offset back out of the detail
    # string, which is not an API
    (amb,) = parse(text).ambiguities
    assert [t.text for t in amb.tokens] == [expected]
