import pytest

from nameparser._types import Ambiguity, AmbiguityKind, ParsedName, Role, Span, Token


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


def test_token_rejects_malformed_span_shapes():
    with pytest.raises(ValueError, match="expected a \\(start, end\\) pair"):
        Token("x", (0, 4, 9), Role.GIVEN)  # type: ignore[arg-type]
    with pytest.raises(ValueError, match="expected a \\(start, end\\) pair"):
        Token("x", 5, Role.GIVEN)  # type: ignore[arg-type]


def test_token_rejects_non_string_text():
    with pytest.raises(ValueError, match="got None"):
        Token(None, None, Role.GIVEN)  # type: ignore[arg-type]


def test_token_is_frozen_and_hashable():
    t = Token("Juan", (0, 4), Role.GIVEN)
    with pytest.raises(AttributeError):
        t.text = "X"  # type: ignore[misc]
    assert hash(t) == hash(Token("Juan", (0, 4), Role.GIVEN))


def test_ambiguity_kind_members_are_their_string_values():
    assert AmbiguityKind.PARTICLE_OR_GIVEN == "particle-or-given"
    assert AmbiguityKind("order") is AmbiguityKind.ORDER


def test_ambiguity_construction_coerces_kind_string():
    t = Token("Van", (0, 3), Role.GIVEN, frozenset({"particle"}))
    a = Ambiguity("particle-or-given", "leading 'van' may be a particle", (t,))
    assert a.kind is AmbiguityKind.PARTICLE_OR_GIVEN
    assert a.tokens == (t,)


def test_ambiguity_rejects_unknown_kind():
    with pytest.raises(ValueError, match="particle-or-given"):
        Ambiguity("no-such-kind", "detail", ())


def test_ambiguity_rejects_non_token_elements():
    with pytest.raises(ValueError, match="only Token instances"):
        Ambiguity("order", "detail", ("not-a-token",))  # type: ignore[arg-type]


def test_ambiguity_rejects_empty_detail():
    with pytest.raises(ValueError, match="non-empty string"):
        Ambiguity("order", "", ())


def _pn(original, tokens, ambiguities=()):
    return ParsedName(original=original, tokens=tuple(tokens),
                      ambiguities=tuple(ambiguities))


def test_parsedname_accepts_valid_spans_and_is_truthy():
    pn = _pn("John Smith", [
        Token("John", (0, 4), Role.GIVEN),
        Token("Smith", (5, 10), Role.FAMILY),
    ])
    assert bool(pn) is True


def test_empty_parse_is_falsy():
    assert bool(_pn("", [])) is False
    assert bool(_pn("   ", [])) is False


def test_parsedname_rejects_out_of_bounds_span():
    with pytest.raises(ValueError, match="out of bounds"):
        _pn("John", [Token("Johnny", (0, 6), Role.GIVEN)])


def test_parsedname_rejects_overlapping_spans():
    with pytest.raises(ValueError, match="ascending"):
        _pn("John Smith", [
            Token("John", (0, 4), Role.GIVEN),
            Token("ohn S", (1, 6), Role.FAMILY),
        ])


def test_parsedname_rejects_descending_spans():
    with pytest.raises(ValueError, match="ascending"):
        _pn("John Smith", [
            Token("Smith", (5, 10), Role.FAMILY),
            Token("John", (0, 4), Role.GIVEN),
        ])


def test_synthetic_tokens_skip_span_checks():
    pn = _pn("John Smith", [
        Token("John", (0, 4), Role.GIVEN),
        Token("Qux", None, Role.MIDDLE),
        Token("Smith", (5, 10), Role.FAMILY),
    ])
    assert len(pn.tokens) == 3


def test_ambiguity_tokens_must_be_subset_of_parse_tokens():
    inside = Token("Van", (0, 3), Role.GIVEN)
    outside = Token("Zzz", None, Role.GIVEN)
    with pytest.raises(ValueError, match="subset"):
        _pn("Van Johnson",
            [inside, Token("Johnson", (4, 11), Role.FAMILY)],
            [Ambiguity(AmbiguityKind.PARTICLE_OR_GIVEN, "d", (outside,))])


def test_parsedname_equality_is_strict_structural():
    a = _pn("John", [Token("John", (0, 4), Role.GIVEN)])
    b = _pn("John", [Token("John", (0, 4), Role.GIVEN)])
    c = _pn("John ", [Token("John", (0, 4), Role.GIVEN)])
    assert a == b and hash(a) == hash(b)
    assert a != c  # different original: not interchangeable


def test_parsedname_rejects_non_str_original():
    with pytest.raises(ValueError, match="must be a str"):
        _pn(None, [])  # type: ignore[arg-type]


def test_parsedname_rejects_non_token_and_non_ambiguity_elements():
    with pytest.raises(ValueError, match="only Token instances"):
        _pn("x", ["not-a-token"])  # type: ignore[list-item]
    with pytest.raises(ValueError, match="only Ambiguity instances"):
        _pn("John", [Token("John", (0, 4), Role.GIVEN)], ["nope"])  # type: ignore[list-item]
