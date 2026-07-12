import pytest

from nameparser._types import (
    STABLE_TAGS, Ambiguity, AmbiguityKind, ParsedName, Role, Span, Token,
)


def test_role_declaration_order_is_canonical_field_order():
    assert [r.value for r in Role] == [
        "title", "given", "middle", "family", "suffix", "nickname", "maiden",
    ]


def test_token_construction_and_span_coercion():
    t = Token("Juan", (0, 4), Role.GIVEN)  # type: ignore[arg-type]
    assert t.span == Span(0, 4)
    assert isinstance(t.span, Span)
    assert t.span.start == 0 and t.span.end == 4
    assert t.tags == frozenset()


def test_synthetic_token_has_no_span():
    t = Token("Jane", None, Role.GIVEN)
    assert t.span is None


def test_token_rejects_empty_text():
    with pytest.raises(ValueError, match="non-empty"):
        Token("", Span(0, 0), Role.GIVEN)


def test_token_rejects_inverted_span():
    with pytest.raises(ValueError, match="start <= end"):
        Token("x", Span(5, 2), Role.GIVEN)


def test_token_rejects_negative_span():
    with pytest.raises(ValueError, match="start <= end"):
        Token("x", Span(-1, 1), Role.GIVEN)


def test_token_rejects_malformed_span_shapes():
    with pytest.raises(ValueError, match="expected a \\(start, end\\) pair"):
        Token("x", (0, 4, 9), Role.GIVEN)  # type: ignore[arg-type]
    with pytest.raises(ValueError, match="expected a \\(start, end\\) pair"):
        Token("x", 5, Role.GIVEN)  # type: ignore[arg-type]


def test_token_rejects_non_string_text():
    with pytest.raises(ValueError, match="got None"):
        Token(None, None, Role.GIVEN)  # type: ignore[arg-type]


def test_token_is_frozen_and_hashable():
    t = Token("Juan", Span(0, 4), Role.GIVEN)
    with pytest.raises(AttributeError):
        t.text = "X"  # type: ignore[misc]
    assert hash(t) == hash(Token("Juan", Span(0, 4), Role.GIVEN))


def test_ambiguity_kind_members_are_their_string_values():
    assert AmbiguityKind.PARTICLE_OR_GIVEN == "particle-or-given"
    assert AmbiguityKind("order") is AmbiguityKind.ORDER


def test_ambiguity_construction_coerces_kind_string():
    t = Token("Van", Span(0, 3), Role.GIVEN, frozenset({"particle"}))
    a = Ambiguity("particle-or-given", "leading 'van' may be a particle", (t,))  # type: ignore[arg-type]
    assert a.kind is AmbiguityKind.PARTICLE_OR_GIVEN
    assert a.tokens == (t,)


def test_ambiguity_rejects_unknown_kind():
    with pytest.raises(ValueError, match="particle-or-given"):
        Ambiguity("no-such-kind", "detail", ())  # type: ignore[arg-type]


def test_ambiguity_rejects_non_token_elements():
    with pytest.raises(ValueError, match="only Token instances"):
        Ambiguity("order", "detail", ("not-a-token",))  # type: ignore[arg-type]


def test_ambiguity_rejects_empty_detail():
    with pytest.raises(ValueError, match="non-empty string"):
        Ambiguity(AmbiguityKind.ORDER, "", ())


def _pn(original, tokens, ambiguities=()):
    return ParsedName(original=original, tokens=tuple(tokens),
                      ambiguities=tuple(ambiguities))


def test_parsedname_accepts_valid_spans_and_is_truthy():
    pn = _pn("John Smith", [
        Token("John", Span(0, 4), Role.GIVEN),
        Token("Smith", Span(5, 10), Role.FAMILY),
    ])
    assert bool(pn) is True


def test_empty_parse_is_falsy():
    assert bool(_pn("", [])) is False
    assert bool(_pn("   ", [])) is False


def test_parsedname_rejects_out_of_bounds_span():
    with pytest.raises(ValueError, match="out of bounds"):
        _pn("John", [Token("Johnny", Span(0, 6), Role.GIVEN)])


def test_parsedname_rejects_overlapping_spans():
    with pytest.raises(ValueError, match="ascending"):
        _pn("John Smith", [
            Token("John", Span(0, 4), Role.GIVEN),
            Token("ohn S", Span(1, 6), Role.FAMILY),
        ])


def test_parsedname_rejects_descending_spans():
    with pytest.raises(ValueError, match="ascending"):
        _pn("John Smith", [
            Token("Smith", Span(5, 10), Role.FAMILY),
            Token("John", Span(0, 4), Role.GIVEN),
        ])


def test_synthetic_tokens_skip_span_checks():
    pn = _pn("John Smith", [
        Token("John", Span(0, 4), Role.GIVEN),
        Token("Qux", None, Role.MIDDLE),
        Token("Smith", Span(5, 10), Role.FAMILY),
    ])
    assert len(pn.tokens) == 3


def test_ambiguity_tokens_must_be_subset_of_parse_tokens():
    inside = Token("Van", Span(0, 3), Role.GIVEN)
    outside = Token("Zzz", None, Role.GIVEN)
    with pytest.raises(ValueError, match="subset"):
        _pn("Van Johnson",
            [inside, Token("Johnson", Span(4, 11), Role.FAMILY)],
            [Ambiguity(AmbiguityKind.PARTICLE_OR_GIVEN, "d", (outside,))])


def test_parsedname_equality_is_strict_structural():
    a = _pn("John", [Token("John", Span(0, 4), Role.GIVEN)])
    b = _pn("John", [Token("John", Span(0, 4), Role.GIVEN)])
    c = _pn("John ", [Token("John", Span(0, 4), Role.GIVEN)])
    assert a == b and hash(a) == hash(b)
    assert a != c  # different original: not interchangeable


def test_parsedname_rejects_non_str_original():
    with pytest.raises(ValueError, match="must be a str"):
        _pn(None, [])  # type: ignore[arg-type]


def test_parsedname_rejects_non_token_and_non_ambiguity_elements():
    with pytest.raises(ValueError, match="only Token instances"):
        _pn("x", ["not-a-token"])  # type: ignore[list-item]
    with pytest.raises(ValueError, match="only Ambiguity instances"):
        _pn("John", [Token("John", Span(0, 4), Role.GIVEN)], ["nope"])  # type: ignore[list-item]


def _delavega():
    # "Dr. Juan de la Vega III" -- hand-built, spans verified by hand
    #  0123456789012345678901234
    return _pn("Dr. Juan de la Vega III", [
        Token("Dr.", Span(0, 3), Role.TITLE),
        Token("Juan", Span(4, 8), Role.GIVEN),
        Token("de", Span(9, 11), Role.FAMILY, frozenset({"particle"})),
        Token("la", Span(12, 14), Role.FAMILY, frozenset({"particle"})),
        Token("Vega", Span(15, 19), Role.FAMILY),
        Token("III", Span(20, 23), Role.SUFFIX),
    ])


def test_string_properties_join_by_role():
    pn = _delavega()
    assert pn.title == "Dr."
    assert pn.given == "Juan"
    assert pn.middle == ""
    assert pn.family == "de la Vega"
    assert pn.suffix == "III"
    assert pn.nickname == ""
    assert pn.maiden == ""


def test_suffix_joins_with_comma_space():
    pn = _pn("John Smith PhD MD", [
        Token("John", Span(0, 4), Role.GIVEN),
        Token("Smith", Span(5, 10), Role.FAMILY),
        Token("PhD", Span(11, 14), Role.SUFFIX),
        Token("MD", Span(15, 17), Role.SUFFIX),
    ])
    assert pn.suffix == "PhD, MD"


def test_derived_views_filter_on_stable_particle_tag():
    # Pin the hard-coded "particle" string in _text_for to the published
    # contract until Plan 3's tag-emission contract tests land.
    assert "particle" in STABLE_TAGS
    pn = _delavega()
    assert pn.family_particles == "de la"
    assert pn.family_base == "Vega"
    assert pn.surnames == "de la Vega"       # middle + family
    assert pn.given_names == "Juan"           # given + middle


def test_tokens_for_preserves_order():
    pn = _delavega()
    assert [t.text for t in pn.tokens_for(Role.FAMILY)] == ["de", "la", "Vega"]
    assert pn.tokens_for(Role.NICKNAME) == ()


def test_as_dict_canonical_order_and_empty_filtering():
    pn = _delavega()
    d = pn.as_dict()
    assert list(d) == ["title", "given", "middle", "family",
                       "suffix", "nickname", "maiden"]
    assert d["family"] == "de la Vega" and d["middle"] == ""
    d2 = pn.as_dict(include_empty=False)
    assert list(d2) == ["title", "given", "family", "suffix"]


def test_replace_swaps_field_with_synthetic_tokens_in_place():
    pn = _delavega()
    pn2 = pn.replace(given="Jean Paul")
    assert pn2.given == "Jean Paul"
    assert pn2.family == "de la Vega"           # untouched
    assert pn2.original == pn.original           # provenance unchanged
    assert all(t.span is None for t in pn2.tokens_for(Role.GIVEN))
    assert pn.given == "Juan"                    # source object unchanged
    # positional: synthetic given tokens sit where the old ones were
    assert [t.role for t in pn2.tokens][:3] == [Role.TITLE, Role.GIVEN, Role.GIVEN]


def test_replace_adds_missing_field_at_end():
    pn = _pn("John Smith", [
        Token("John", Span(0, 4), Role.GIVEN),
        Token("Smith", Span(5, 10), Role.FAMILY),
    ])
    pn2 = pn.replace(suffix="Jr")
    assert pn2.suffix == "Jr"
    assert pn2.tokens[-1].role is Role.SUFFIX


def test_replace_with_empty_string_clears_field():
    pn = _delavega()
    assert pn.replace(title="").title == ""


def test_replace_rejects_unknown_field():
    with pytest.raises(TypeError, match="given"):
        _delavega().replace(firstname="X")


def test_replace_drops_ambiguities_referencing_removed_tokens():
    van = Token("Van", Span(0, 3), Role.GIVEN)
    pn = _pn("Van Johnson",
             [van, Token("Johnson", Span(4, 11), Role.FAMILY)],
             [Ambiguity(AmbiguityKind.PARTICLE_OR_GIVEN, "d", (van,))])
    assert pn.replace(given="Bob").ambiguities == ()
    assert pn.replace(family="Smith").ambiguities != ()


def test_replace_rejects_non_str_value():
    with pytest.raises(TypeError, match="must be a str"):
        _delavega().replace(given=None)  # type: ignore[arg-type]


def test_replace_appends_missing_roles_in_canonical_order():
    pn = _pn("John", [Token("John", Span(0, 4), Role.GIVEN)])
    pn2 = pn.replace(maiden="X", suffix="Y")
    assert [t.role for t in pn2.tokens] == [Role.GIVEN, Role.SUFFIX, Role.MAIDEN]


def test_comparison_key_is_casefolded_canonical_seven_tuple():
    pn = _delavega()
    assert pn.comparison_key() == (
        "dr.", "juan", "", "de la vega", "iii", "", "",
    )
    upper = _pn("JUAN DE LA VEGA", [
        Token("JUAN", Span(0, 4), Role.GIVEN),
        Token("DE", Span(5, 7), Role.FAMILY, frozenset({"particle"})),
        Token("LA", Span(8, 10), Role.FAMILY, frozenset({"particle"})),
        Token("VEGA", Span(11, 15), Role.FAMILY),
    ])
    lower = _pn("juan de la vega", [
        Token("juan", Span(0, 4), Role.GIVEN),
        Token("de", Span(5, 7), Role.FAMILY, frozenset({"particle"})),
        Token("la", Span(8, 10), Role.FAMILY, frozenset({"particle"})),
        Token("vega", Span(11, 15), Role.FAMILY),
    ])
    assert upper.comparison_key() == lower.comparison_key()
