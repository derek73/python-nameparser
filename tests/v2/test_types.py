import dataclasses
from collections.abc import Iterable

import pytest

from nameparser import parse
from nameparser._types import (
    STABLE_TAGS, Ambiguity, AmbiguityKind, ParsedName, Role, Segmentation,
    Span, Token,
)


def test_role_declaration_order_is_canonical_field_order() -> None:
    assert [r.value for r in Role] == [
        "title", "given", "middle", "family", "suffix", "nickname", "maiden",
    ]


def test_role_members_are_their_string_values() -> None:
    # Role is a StrEnum, like AmbiguityKind: members compare, hash,
    # and stringify as their field names.
    assert Role.GIVEN == "given"
    assert str(Role.FAMILY) == "family"
    d: dict[str, int] = {Role.GIVEN: 1}
    assert d["given"] == 1
    assert isinstance(Role.GIVEN, str)
    assert repr(Role.GIVEN) == "<Role.GIVEN: 'given'>"  # repr keeps .name form
    assert Role("maiden") is Role.MAIDEN


def test_token_construction_and_span_coercion() -> None:
    t = Token("Juan", (0, 4), Role.GIVEN)  # type: ignore[arg-type]
    assert t.span == Span(0, 4)
    assert isinstance(t.span, Span)
    assert t.span.start == 0 and t.span.end == 4
    assert t.tags == frozenset()


def test_synthetic_token_has_no_span() -> None:
    t = Token("Jane", None, Role.GIVEN)
    assert t.span is None


def test_token_rejects_empty_text() -> None:
    with pytest.raises(ValueError, match="non-empty"):
        Token("", Span(0, 0), Role.GIVEN)


def test_token_rejects_inverted_span() -> None:
    with pytest.raises(ValueError, match="start <= end"):
        Token("x", Span(5, 2), Role.GIVEN)


def test_token_rejects_negative_span() -> None:
    with pytest.raises(ValueError, match="start <= end"):
        Token("x", Span(-1, 1), Role.GIVEN)


def test_token_rejects_malformed_span_shapes() -> None:
    with pytest.raises(TypeError, match="expected a \\(start, end\\) pair"):
        Token("x", (0, 4, 9), Role.GIVEN)  # type: ignore[arg-type]
    with pytest.raises(TypeError, match="expected a \\(start, end\\) pair"):
        Token("x", 5, Role.GIVEN)  # type: ignore[arg-type]


def test_token_rejects_non_string_text() -> None:
    with pytest.raises(TypeError, match="got None"):
        Token(None, None, Role.GIVEN)  # type: ignore[arg-type]


def test_token_is_frozen_and_hashable() -> None:
    t = Token("Juan", Span(0, 4), Role.GIVEN)
    with pytest.raises(AttributeError):
        t.text = "X"  # type: ignore[misc]
    assert hash(t) == hash(Token("Juan", Span(0, 4), Role.GIVEN))


def test_segmentation_validates_splits() -> None:
    s = Segmentation((2,), confidence=0.97)
    assert s.splits == (2,) and s.confidence == 0.97
    assert Segmentation(()).confidence is None
    with pytest.raises(ValueError, match="ascending"):
        Segmentation((3, 2))
    with pytest.raises(ValueError, match="interior"):
        Segmentation((0,))
    with pytest.raises(TypeError, match="integers"):
        Segmentation(("2",))  # type: ignore[arg-type]
    with pytest.raises(ValueError, match="confidence"):
        Segmentation((2,), confidence=1.5)


def test_segmentation_rejects_mappings_and_non_iterables() -> None:
    # Token.tags' guards, on the other collection field: a mapping
    # would silently contribute only its keys, and a bare int would
    # surface as an uncurated "not iterable" naming nothing
    with pytest.raises(TypeError, match="Segmentation.splits"):
        Segmentation({2: "a", 3: "b"})  # type: ignore[arg-type]
    with pytest.raises(TypeError, match="Segmentation.splits"):
        Segmentation(5)  # type: ignore[arg-type]


def test_segmentation_is_frozen_and_hashable() -> None:
    s = Segmentation((2,))
    assert isinstance(hash(s), int)
    with pytest.raises(dataclasses.FrozenInstanceError):
        s.splits = (3,)  # type: ignore[misc]


def test_ambiguity_kind_members_are_their_string_values() -> None:
    assert AmbiguityKind.PARTICLE_OR_GIVEN == "particle-or-given"
    assert AmbiguityKind("order") is AmbiguityKind.ORDER


def test_ambiguity_construction_coerces_kind_string() -> None:
    t = Token("Van", Span(0, 3), Role.GIVEN, frozenset({"particle"}))
    a = Ambiguity("particle-or-given", "leading 'van' may be a particle", (t,))  # type: ignore[arg-type]
    assert a.kind is AmbiguityKind.PARTICLE_OR_GIVEN
    assert a.tokens == (t,)


def test_ambiguity_rejects_unknown_kind() -> None:
    with pytest.raises(ValueError, match="particle-or-given"):
        Ambiguity("no-such-kind", "detail", ())  # type: ignore[arg-type]


def test_ambiguity_rejects_non_token_elements() -> None:
    with pytest.raises(TypeError, match="only Token instances"):
        Ambiguity("order", "detail", ("not-a-token",))  # type: ignore[arg-type]


def test_ambiguity_rejects_empty_detail() -> None:
    with pytest.raises(ValueError, match="non-empty string"):
        Ambiguity(AmbiguityKind.ORDER, "", ())


def test_ambiguity_rejects_non_str_detail() -> None:
    with pytest.raises(TypeError, match="must be a str"):
        Ambiguity(AmbiguityKind.ORDER, None, ())  # type: ignore[arg-type]


def _pn(original: str, tokens: Iterable[Token],
        ambiguities: Iterable[Ambiguity] = ()) -> ParsedName:
    return ParsedName(original=original, tokens=tuple(tokens),
                      ambiguities=tuple(ambiguities))


def test_parsedname_accepts_valid_spans_and_is_truthy() -> None:
    pn = _pn("John Smith", [
        Token("John", Span(0, 4), Role.GIVEN),
        Token("Smith", Span(5, 10), Role.FAMILY),
    ])
    assert bool(pn) is True


def test_empty_parse_is_falsy() -> None:
    assert bool(_pn("", [])) is False
    assert bool(_pn("   ", [])) is False


def test_parsedname_rejects_out_of_bounds_span() -> None:
    with pytest.raises(ValueError, match="out of bounds"):
        _pn("John", [Token("Johnny", Span(0, 6), Role.GIVEN)])


def test_parsedname_rejects_overlapping_spans() -> None:
    with pytest.raises(ValueError, match="ascending"):
        _pn("John Smith", [
            Token("John", Span(0, 4), Role.GIVEN),
            Token("ohn S", Span(1, 6), Role.FAMILY),
        ])


def test_parsedname_rejects_descending_spans() -> None:
    with pytest.raises(ValueError, match="ascending"):
        _pn("John Smith", [
            Token("Smith", Span(5, 10), Role.FAMILY),
            Token("John", Span(0, 4), Role.GIVEN),
        ])


def test_synthetic_tokens_skip_span_checks() -> None:
    pn = _pn("John Smith", [
        Token("John", Span(0, 4), Role.GIVEN),
        Token("Qux", None, Role.MIDDLE),
        Token("Smith", Span(5, 10), Role.FAMILY),
    ])
    assert len(pn.tokens) == 3


def test_ambiguity_tokens_must_be_subset_of_parse_tokens() -> None:
    inside = Token("Van", Span(0, 3), Role.GIVEN)
    outside = Token("Zzz", None, Role.GIVEN)
    with pytest.raises(ValueError, match="subset"):
        _pn("Van Johnson",
            [inside, Token("Johnson", Span(4, 11), Role.FAMILY)],
            [Ambiguity(AmbiguityKind.PARTICLE_OR_GIVEN, "d", (outside,))])


def test_parsedname_equality_is_strict_structural() -> None:
    a = _pn("John", [Token("John", Span(0, 4), Role.GIVEN)])
    b = _pn("John", [Token("John", Span(0, 4), Role.GIVEN)])
    c = _pn("John ", [Token("John", Span(0, 4), Role.GIVEN)])
    assert a == b and hash(a) == hash(b)
    assert a != c  # different original: not interchangeable


def test_parsedname_rejects_non_str_original() -> None:
    with pytest.raises(TypeError, match="must be a str"):
        _pn(None, [])  # type: ignore[arg-type]


def test_parsedname_rejects_non_token_and_non_ambiguity_elements() -> None:
    with pytest.raises(TypeError, match="only Token instances"):
        _pn("x", ["not-a-token"])  # type: ignore[list-item]
    with pytest.raises(TypeError, match="only Ambiguity instances"):
        _pn("John", [Token("John", Span(0, 4), Role.GIVEN)], ["nope"])  # type: ignore[list-item]


def _delavega() -> ParsedName:
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


def test_string_properties_join_by_role() -> None:
    pn = _delavega()
    assert pn.title == "Dr."
    assert pn.given == "Juan"
    assert pn.middle == ""
    assert pn.family == "de la Vega"
    assert pn.suffix == "III"
    assert pn.nickname == ""
    assert pn.maiden == ""


def test_suffix_joins_with_comma_space() -> None:
    pn = _pn("John Smith PhD MD", [
        Token("John", Span(0, 4), Role.GIVEN),
        Token("Smith", Span(5, 10), Role.FAMILY),
        Token("PhD", Span(11, 14), Role.SUFFIX),
        Token("MD", Span(15, 17), Role.SUFFIX),
    ])
    assert pn.suffix == "PhD, MD"


def test_derived_views_filter_on_stable_particle_tag() -> None:
    # Pin the hard-coded "particle" string in _text_for to the published
    # contract until parser tag-emission contract tests land.
    assert "particle" in STABLE_TAGS
    pn = _delavega()
    assert pn.family_particles == "de la"
    assert pn.family_base == "Vega"
    assert pn.surnames == "de la Vega"       # middle + family
    assert pn.given_names == "Juan"           # given + middle


def test_tokens_for_preserves_order() -> None:
    pn = _delavega()
    assert [t.text for t in pn.tokens_for(Role.FAMILY)] == ["de", "la", "Vega"]
    assert pn.tokens_for(Role.NICKNAME) == ()


def test_as_dict_canonical_order_and_empty_filtering() -> None:
    pn = _delavega()
    d = pn.as_dict()
    assert list(d) == ["title", "given", "middle", "family",
                       "suffix", "nickname", "maiden"]
    assert d["family"] == "de la Vega" and d["middle"] == ""
    d2 = pn.as_dict(include_empty=False)
    assert list(d2) == ["title", "given", "family", "suffix"]


def test_replace_swaps_field_with_synthetic_tokens_in_place() -> None:
    pn = _delavega()
    pn2 = pn.replace(given="Jean Paul")
    assert pn2.given == "Jean Paul"
    assert pn2.family == "de la Vega"           # untouched
    assert pn2.original == pn.original           # provenance unchanged
    assert all(t.span is None for t in pn2.tokens_for(Role.GIVEN))
    assert pn.given == "Juan"                    # source object unchanged
    # positional: synthetic given tokens sit where the old ones were
    assert [t.role for t in pn2.tokens][:3] == [Role.TITLE, Role.GIVEN, Role.GIVEN]


def test_replace_adds_missing_field_at_end() -> None:
    pn = _pn("John Smith", [
        Token("John", Span(0, 4), Role.GIVEN),
        Token("Smith", Span(5, 10), Role.FAMILY),
    ])
    pn2 = pn.replace(suffix="Jr")
    assert pn2.suffix == "Jr"
    assert pn2.tokens[-1].role is Role.SUFFIX


def test_replace_with_empty_string_clears_field() -> None:
    pn = _delavega()
    assert pn.replace(title="").title == ""


def test_replace_rejects_unknown_field() -> None:
    with pytest.raises(TypeError, match="given"):
        _delavega().replace(firstname="X")


def test_replace_drops_ambiguities_referencing_removed_tokens() -> None:
    van = Token("Van", Span(0, 3), Role.GIVEN)
    pn = _pn("Van Johnson",
             [van, Token("Johnson", Span(4, 11), Role.FAMILY)],
             [Ambiguity(AmbiguityKind.PARTICLE_OR_GIVEN, "d", (van,))])
    assert pn.replace(given="Bob").ambiguities == ()
    assert pn.replace(family="Smith").ambiguities != ()


def test_replace_rejects_non_str_value() -> None:
    with pytest.raises(TypeError, match="must be a str"):
        _delavega().replace(given=None)  # type: ignore[arg-type]


def test_replace_appends_missing_roles_in_canonical_order() -> None:
    pn = _pn("John", [Token("John", Span(0, 4), Role.GIVEN)])
    pn2 = pn.replace(maiden="X", suffix="Y")
    assert [t.role for t in pn2.tokens] == [Role.GIVEN, Role.SUFFIX, Role.MAIDEN]


def test_comparison_key_is_casefolded_canonical_seven_tuple() -> None:
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


def test_matches_casefolds_unicode_case_pairs() -> None:
    # Deliberate 1.4 deviation (release log): comparison folds with
    # casefold() where 1.4 used lower(). Comparison is the one surface
    # where casefold's aggressive folds are WANTED -- ß/SS and final-
    # sigma forms are the same name under different case conventions,
    # and the key is opaque, so the spelling-mutation bug casefold
    # caused in vocabulary storage (which stays lower(), v1 lc parity
    # -- see _lexicon._normalize) cannot happen here.
    from nameparser import HumanName, parse

    assert parse("Hans Straße").matches("HANS STRASSE")   # ß <-> SS
    assert parse("Νίκος Παπαδόπουλος").matches("Νίκοσ Παπαδόπουλοσ")  # ς <-> σ
    # same fold on the facade path -- both APIs share the deviation
    assert HumanName("Hans Straße").matches("HANS STRASSE")
    key = parse("Hans Straße").comparison_key()
    assert key == parse("HANS STRASSE").comparison_key()


def test_token_rejects_bare_string_and_mapping_tags() -> None:
    # frozenset("particle") is the set(str) footgun: eight single chars.
    with pytest.raises(TypeError, match="bare string"):
        Token("Van", None, Role.GIVEN, tags="particle")  # type: ignore[arg-type]
    with pytest.raises(TypeError, match="mapping"):
        Token("Van", None, Role.GIVEN, tags={"particle": 1})  # type: ignore[arg-type]


def test_token_rejects_non_str_tags() -> None:
    with pytest.raises(TypeError, match="tags must contain only strings"):
        Token("Van", None, Role.GIVEN, tags=frozenset({1}))  # type: ignore[arg-type]


def test_token_coerces_role_string_and_rejects_unknown() -> None:
    # mirror Ambiguity.kind: coerce the string form, ValueError for any
    # failed enum lookup (stdlib EnumType precedent).
    assert Token("Juan", None, "given").role is Role.GIVEN  # type: ignore[arg-type]
    with pytest.raises(ValueError, match="title, given"):
        Token("Juan", None, "chief")  # type: ignore[arg-type]
    with pytest.raises(ValueError, match="title, given"):
        Token("Juan", None, 5)  # type: ignore[arg-type]


def test_types_pickle_round_trip() -> None:
    import pickle

    pn = _delavega()
    assert pickle.loads(pickle.dumps(pn)) == pn
    amb = Ambiguity(AmbiguityKind.ORDER, "two-comma structure", ())
    assert pickle.loads(pickle.dumps(amb)) == amb
    tok = Token("de", Span(9, 11), Role.FAMILY, frozenset({"particle"}))
    assert pickle.loads(pickle.dumps(tok)) == tok


def test_span_add_is_blocked() -> None:
    # NamedTuple + would concatenate into a 4-tuple, the natural but
    # wrong spelling of "covering span" (a real cover() arrives with the
    # pipeline's join stage, its consumer).
    with pytest.raises(TypeError, match="covering span"):
        Span(0, 2) + Span(3, 4)  # type: ignore[operator]


def test_token_rejects_bool_span_coordinates() -> None:
    # bool is an int subclass; (False, True) is a comparison result
    # leaking into a coordinate slot, not a span.
    with pytest.raises(TypeError, match="pair of ints"):
        Token("x", (False, True), Role.GIVEN)  # type: ignore[arg-type]


def test_setstate_rejects_layout_skew_on_frozen_types() -> None:
    # version-skewed pickles must fail at the LOAD site, naming the
    # mismatch -- not at a distant attribute read (same policy as
    # Lexicon; values are deliberately NOT re-validated: pickle is not
    # a security boundary)
    tok = Token("Juan", Span(0, 4), Role.GIVEN)
    state = tok.__getstate__()
    bad = dict(state)
    del bad["tags"]
    with pytest.raises(ValueError, match="tags"):
        Token.__new__(Token).__setstate__(bad)
    pn = _pn("Juan", [tok])
    bad_pn = dict(pn.__getstate__())
    bad_pn["zq_future"] = ()
    with pytest.raises(ValueError, match="zq_future"):
        ParsedName.__new__(ParsedName).__setstate__(bad_pn)


def test_tokens_for_accepts_role_string() -> None:
    name = parse("Juan de la Vega")
    assert name.tokens_for("family") == name.tokens_for(Role.FAMILY)
    assert name.tokens_for("given") == name.tokens_for(Role.GIVEN)


def test_tokens_for_unknown_role_raises_listing_roles() -> None:
    with pytest.raises(ValueError, match=r"unknown Role 'last'.*valid roles: title, given, middle"):
        parse("John Smith").tokens_for("last")


def test_tokens_for_non_coercible_raises() -> None:
    with pytest.raises(ValueError, match="unknown Role 3"):
        parse("John Smith").tokens_for(3)  # type: ignore[arg-type]


def test_stable_tags_is_public_api() -> None:
    import nameparser
    assert "STABLE_TAGS" in nameparser.__all__
    # the documented stable tag vocabulary -- these four values are API
    assert nameparser.STABLE_TAGS == frozenset(
        {"particle", "conjunction", "initial", "joined"})


def test_as_dict_include_empty_is_keyword_only() -> None:
    with pytest.raises(TypeError):
        parse("John Smith").as_dict(False)  # type: ignore[misc]


def test_particle_tag_marks_vocabulary_membership_not_role() -> None:
    # the tag follows the WORD, not the field: a leading ambiguous
    # particle read as a given name still carries it (STABLE_TAGS docs)
    tok = parse("Van Johnson").tokens_for(Role.GIVEN)[0]
    assert "particle" in tok.tags


def test_str_enum_value_sets_are_pairwise_disjoint() -> None:
    # three StrEnums cross-compare by value; a future collision would
    # make unrelated members equal
    from nameparser import AmbiguityKind, PatronymicRule
    role = {m.value for m in Role}
    kind = {m.value for m in AmbiguityKind}
    rule = {m.value for m in PatronymicRule}
    assert not (role & kind) and not (role & rule) and not (kind & rule)


def test_with_field_tokens_rejects_mismatched_roles() -> None:
    name = parse("John Smith")
    with pytest.raises(ValueError, match="has role family, not given"):
        name._with_field_tokens(
            {Role.GIVEN: (Token("x", None, Role.FAMILY),)})


