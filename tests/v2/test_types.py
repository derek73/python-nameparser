import pytest

from nameparser._types import Role, Span, Token


def test_role_declaration_order_is_canonical_field_order():
    assert [r.value for r in Role] == [
        "title", "given", "middle", "family", "suffix", "nickname", "maiden",
    ]


def test_token_construction_and_span_coercion():
    t = Token("Juan", (0, 4), Role.GIVEN)
    assert t.span == Span(0, 4)
    assert isinstance(t.span, Span)
    assert t.span.start == 0 and t.span.end == 4
    assert t.tags == frozenset()


def test_synthetic_token_has_no_span():
    t = Token("Jane", None, Role.GIVEN)
    assert t.span is None


def test_token_rejects_empty_text():
    with pytest.raises(ValueError, match="non-empty"):
        Token("", (0, 0), Role.GIVEN)


def test_token_rejects_inverted_span():
    with pytest.raises(ValueError, match="start <= end"):
        Token("x", (5, 2), Role.GIVEN)


def test_token_rejects_negative_span():
    with pytest.raises(ValueError, match="start <= end"):
        Token("x", (-1, 1), Role.GIVEN)


def test_token_is_frozen_and_hashable():
    t = Token("Juan", (0, 4), Role.GIVEN)
    with pytest.raises(AttributeError):
        t.text = "X"  # type: ignore[misc]
    assert hash(t) == hash(Token("Juan", (0, 4), Role.GIVEN))
