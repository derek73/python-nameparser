import dataclasses
import itertools
from collections.abc import Callable, Iterable, Iterator
from pathlib import Path

import pytest

from nameparser import (
    FAMILY_FIRST, FAMILY_FIRST_GIVEN_LAST, GIVEN_FIRST, Lexicon, Locale, Parser,
    Policy, parse,
)
from nameparser._types import (
    STABLE_TAGS, Ambiguity, AmbiguityKind, ParsedName, Reading, Role,
    UNJOINED_TAG, Segmentation, Span, Token,
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
    # wrong TYPE is the TypeError branch, distinct from the range check
    with pytest.raises(TypeError, match="confidence"):
        Segmentation((2,), confidence="high")  # type: ignore[arg-type]


def test_segmentation_rejects_mappings_and_non_iterables() -> None:
    # Token.tags' guards, on the other collection field: a mapping
    # would silently contribute only its keys, and a bare int would
    # surface as an uncurated "not iterable" naming nothing
    with pytest.raises(TypeError, match="Segmentation.splits"):
        Segmentation({2: "a", 3: "b"})  # type: ignore[arg-type]
    with pytest.raises(TypeError, match="Segmentation.splits"):
        Segmentation(5)  # type: ignore[arg-type]
    # ...and the bare string, the third member of that family and the
    # one with teeth: "" is iterable and empty, so without the guard
    # Segmentation("") became "confidently one token" -- an opinion
    # nobody stated -- while "23" failed one character deep naming '2'
    # instead of the argument. Both must name the field.
    for bad in ("", "23"):
        with pytest.raises(TypeError, match="Segmentation.splits"):
            Segmentation(bad)  # type: ignore[arg-type]


def test_segmentation_rejects_bools_in_both_fields() -> None:
    # bool is an int subclass in both slots: True as an offset is a
    # comparison result leaking into an index, True as a confidence one
    # leaking into a score. Behavioral twin of Token's span guard.
    with pytest.raises(TypeError, match="Segmentation.splits"):
        Segmentation((True,))  # type: ignore[list-item]
    with pytest.raises(TypeError, match="Segmentation.confidence"):
        Segmentation((2,), confidence=True)  # type: ignore[arg-type]


def test_segmentation_lets_a_generator_raise_its_own_error() -> None:
    # the non-iterable guard probes iter(), which cannot run a
    # generator's body; wrapping the tuple() call instead would catch a
    # TypeError raised INSIDE the user's generator and relabel it as
    # "splits must be an iterable", pointing the reader at the wrong bug
    def boom() -> Iterator[int]:
        yield 1
        raise TypeError("boom")

    with pytest.raises(TypeError) as caught:
        Segmentation(boom())  # type: ignore[arg-type]
    # the message is the generator's own, whole -- a `match=` would
    # pass on the relabeled text too, since the generator's repr names
    # the function
    assert str(caught.value) == "boom"


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


# -- the suffix's generation and credentials views (rules/R8, #326) --

@pytest.mark.parametrize("text,generation,credentials", [
    # the empty path: a name with no suffix, and a suffix of one kind
    ("John Smith", "", ""),
    ("John Smith PhD", "", "PhD"),
    ("John Smith Jr.", "Jr.", ""),
    # comma-joined as the suffix is, each view in written order
    ("Smith, John, Jr., MD, Esq.", "Jr.", "MD, Esq."),
    ("John Smith, PhD, Jr., III", "Jr., III", "PhD"),
    # a run written without commas comes apart by kind, two words of
    # one view keeping the separator written between them (a comma
    # anywhere in the gap, else a space); a split credential stays
    # whole
    ("John Smith Jr. III PhD", "Jr. III", "PhD"),
    ("John Smith Ph. D. Jr.", "Jr.", "Ph. D."),
    ("John Smith, MD Jr. PhD", "Jr.", "MD PhD"),
    ("John Smith, MD, Jr. PhD", "Jr.", "MD, PhD"),
    # any entry boundary the suffix renders as a comma (rules/R1)
    ("John Smith, MD / Jr. / PhD", "Jr.", "MD, PhD"),
    # a connective goes with the word before it, dangling where the
    # word after it is in the other view (rules/R8's Accepted)
    ("John Smith, PhD and MD Jr.", "Jr.", "PhD and MD"),
    ("John Smith, Jr. and III", "Jr. and III", ""),
    ("John Smith, Jr. and MD", "Jr. and", "MD"),
    ("Doe, Jane, and Jr.", "Jr.", "and"),
    # a delimiter glued on (rules/C10) reads the word as without it,
    # its text keeping the delimiter as the suffix does
    ("John Smith, Jr.; MD", "Jr.;", "MD"),
    ("Smith, John, Jr.; MD", "Jr.;", "MD"),
    ("John Smith, III; MD", "III;", "MD"),
    ("John Smith, V; MD", "V;", "MD"),
    # a control: no generation word carries the delimiter, so this
    # read alike before the glued stem's kind was read
    ("John Smith, MD; Jr.", "Jr.", "MD;"),
    # a word read by its period-joined chunks ('Jr.' and ';', as
    # 'Lt.Gov.' is read) has no kind of its own, so it is a credential,
    # one made only of generation words included (rules/R8's Accepted)
    ("John Smith Jr.; MD", "", "Jr.; MD"),
    ("John Smith Jr.III", "", "Jr.III"),
    ("John Smith, Jr.III", "", "Jr.III"),
    # an agnomen is a generation; an honorific, a credential
    ("Pedro Alves Filho", "Filho", ""),
    ("王小明先生", "", "先生"),
])
def test_the_suffix_views_partition_it_by_reading(
        text: str, generation: str, credentials: str) -> None:
    pn = parse(text)
    assert (pn.generation, pn.credentials) == (generation, credentials)


@pytest.mark.parametrize("field,kind", [
    # a caller's word in `suffix_words` alone has no row to read a kind
    # from; its gate's marker or the agnomen set gives it one by its tag
    ({"suffix_words": {"zzz"}}, "post-nominal"),
    ({"suffix_words": {"zzz"}, "suffix_words_ambiguous": {"zzz"}},
     "generation"),
    ({"suffix_words": {"zzz"}, "suffix_words_ambiguous": {"zzz"},
      "agnomens": {"zzz"}}, "agnomen"),
])
def test_a_callers_suffix_word_reads_by_its_marker_else_post_nominal(
        field: dict[str, set[str]], kind: str) -> None:
    pn = Parser(lexicon=Lexicon.default().add(**field)).parse(
        "Pedro Alves Silva zzz")
    (tok,) = pn.tokens_for("suffix")
    assert tok.reading is not None and tok.reading.kind.value == kind
    assert pn.generation == ("" if kind == "post-nominal" else "zzz")


def test_a_suffix_word_with_no_reading_is_a_credential() -> None:
    # replace() records no reading, so nothing says what the word was
    # read as (rules/R8's Accepted)
    pn = parse("John Smith Jr.").replace(suffix="Jr. PhD")
    assert pn.suffix == "Jr., PhD"
    assert (pn.generation, pn.credentials) == ("", "Jr., PhD")
    # a field it did not touch keeps its readings, and so its views
    kept = parse("John Smith Jr., PhD").replace(given="Jack")
    assert (kept.generation, kept.credentials) == ("Jr.", "PhD")


def test_the_suffix_views_are_render_keys_and_not_fields() -> None:
    pn = parse("Smith, John, Jr., MD")
    assert pn.render("{family} {generation} ({credentials})") \
        == "Smith Jr. (MD)"
    # views, like family_base: as_dict and replace() take the seven
    # roles only
    assert "generation" not in pn.as_dict()
    with pytest.raises(TypeError):
        pn.replace(generation="Sr.")


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


def test_replace_splits_on_any_whitespace_run() -> None:
    # The value is split on whitespace runs, never on single spaces: a
    # blank value clears the field, and a doubled space makes no empty
    # token (a Token("") raises), which the 2.x facade's setters and
    # #232's initials IndexError reached through this split.
    blank = parse("John Doe").replace(given=" \n ")
    assert blank.given == ""
    assert not blank.tokens_for(Role.GIVEN)
    doubled = parse("John Doe").replace(middle="Q \t R")
    assert [t.text for t in doubled.tokens_for(Role.MIDDLE)] == ["Q", "R"]
    assert doubled.initials() == "J. Q. R. D."


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


def test_comparison_key_includes_maiden() -> None:
    # maiden is in no default render, so str() cannot tell these apart;
    # the key holds all seven fields (ported from the 1.x suite)
    from nameparser import parse

    married = parse("Jenny Baker née Johnson")
    assert married.maiden == "Johnson"
    assert married.comparison_key() != parse("Jenny Baker").comparison_key()


def test_matches_casefolds_unicode_case_pairs() -> None:
    # Deliberate 1.4 deviation (release log): comparison folds with
    # casefold() where 1.4 used lower(). Comparison is the one surface
    # where casefold's aggressive folds are WANTED -- ß/SS and final-
    # sigma forms are the same name under different case conventions,
    # and the key is opaque, so the spelling-mutation bug casefold
    # caused in vocabulary storage (which stays lower(), v1 lc parity
    # -- see _lexicon._normalize) cannot happen here.
    from nameparser import parse

    assert parse("Hans Straße").matches("HANS STRASSE")   # ß <-> SS
    assert parse("Νίκος Παπαδόπουλος").matches("Νίκοσ Παπαδόπουλοσ")  # ς <-> σ
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
    # the family sweep is the point of this test, so a frozen type
    # added later belongs in it -- Segmentation (#272) carries the same
    # guarded __getstate__/__setstate__ pair as its three siblings
    seg = Segmentation((2,), confidence=0.42)
    assert pickle.loads(pickle.dumps(seg)) == seg
    # Reading (#752 phase 2m) carries the same guarded pair
    from nameparser import Reading
    reading = Reading("name", "family", "declared", ("en",))  # type: ignore[arg-type]
    assert pickle.loads(pickle.dumps(reading)) == reading
    assert pickle.loads(pickle.dumps(reading)).languages == ("en",)


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


def test_reading_coerces_its_strings_and_refuses_unknown_values() -> None:
    from nameparser import Reading, ReadingKind, ReadingSource
    r = Reading("name", "family", "declared")  # type: ignore[arg-type]
    assert (r.kind, r.role, r.source) == (
        ReadingKind.NAME, Role.FAMILY, ReadingSource.DECLARED)
    assert r == Reading(ReadingKind.NAME, Role.FAMILY, ReadingSource.DECLARED)
    with pytest.raises(ValueError, match="unknown ReadingKind 'surname'.*"
                                         "valid kinds: credential"):
        Reading("surname", "family", "declared")  # type: ignore[arg-type]
    with pytest.raises(ValueError, match="unknown Role 'last'"):
        Reading("name", "last", "declared")  # type: ignore[arg-type]
    with pytest.raises(ValueError, match="unknown ReadingSource 'guess'.*"
                                         "valid sources: vocabulary"):
        Reading("name", "family", "guess")  # type: ignore[arg-type]


def test_reading_languages_are_a_tuple_of_tags_and_are_not_compared() -> None:
    from nameparser import Reading
    bare = Reading("particle", "family", "vocabulary")  # type: ignore[arg-type]
    held = Reading("particle", "family", "vocabulary", ["es", "fr"])  # type: ignore[arg-type]
    assert bare.languages == ()
    assert held.languages == ("es", "fr")
    assert held == bare and hash(held) == hash(bare)



@pytest.mark.parametrize("bad,match", [
    ("es", r"got the str 'es'; write \('es',\)"),
    ({"es": 1}, r"got \{'es': 1\}; pass a tuple or list of tags"),
    (5, r"got 5; pass a tuple or list of tags, such as \('en',\)"),
    (("es", 1), r"as str, got 1 in \('es', 1\)"),
], ids=["bare-str", "mapping", "not-iterable", "non-str-tag"])
def test_reading_languages_refuses_what_is_not_tags(
        bad: object, match: str) -> None:
    from nameparser import Reading
    with pytest.raises(TypeError, match=match):
        Reading("particle", "family", "vocabulary", bad)  # type: ignore[arg-type]


def test_ambiguity_alternative_is_a_reading_and_is_not_compared() -> None:
    from nameparser import Reading
    tok = Token("MA", Span(11, 13), Role.SUFFIX)
    alt = Reading("name", "family", "declared")  # type: ignore[arg-type]
    with_alt = Ambiguity(AmbiguityKind.SUFFIX_OR_NAME, "d", (tok,), alt)
    assert with_alt == Ambiguity(AmbiguityKind.SUFFIX_OR_NAME, "d", (tok,))
    with pytest.raises(TypeError, match="must be a Reading or None"):
        Ambiguity(AmbiguityKind.SUFFIX_OR_NAME, "d", (tok,),
                  ("name", "family"))  # type: ignore[arg-type]


def _ambiguity_state() -> dict[str, object]:
    tok = Token("MA", Span(11, 13), Role.SUFFIX)
    return dict(Ambiguity(AmbiguityKind.SUFFIX_OR_NAME, "d", (tok,)).__getstate__())


def _token_state() -> dict[str, object]:
    from nameparser import Reading
    return dict(Token("Vega", Span(18, 22), Role.FAMILY, frozenset(),
                      Reading("name", "family", "position")  # type: ignore[arg-type]
                      ).__getstate__())


def _reading_state() -> dict[str, object]:
    return dict(Reading("name", "family", "declared",  # type: ignore[arg-type]
                        ("en",)).__getstate__())


def _without(state: dict[str, object], *names: str) -> dict[str, object]:
    return {k: v for k, v in state.items() if k not in names}


def _renamed(state: dict[str, object], old: str,
             new: str) -> dict[str, object]:
    out = _without(state, old)
    out[new] = state[old]
    return out


#: Every layout skew the guard refused before 2.7, which it still
#: refuses: the widening (#752 phase 2m) admits only a field marked
#: `ADDED_IN` and missing from an older pickle. Measured 2026-10-26:
#: each row raises ValueError under the pre-2.7 guard as under this one
#: (the row with two fields missing added after, by the first review),
#: though where `alternative` is missing the old guard names it among
#: the missing fields too, so its message is not the one matched here;
#: and the one admitted row below raises under the pre-2.7 guard, which
#: is the widening.
_REFUSED_SKEWS = [
    pytest.param(Ambiguity, lambda: _without(_ambiguity_state(), "detail"),
                 "missing fields: detail", id="missing-field-without-default"),
    pytest.param(Token, lambda: _without(dict(Token(
        "Juan", Span(0, 4), Role.GIVEN).__getstate__()), "tags"),
                 "missing fields: tags", id="missing-shipped-field-with-default"),
    pytest.param(ParsedName, lambda: _without(dict(
        _pn("Juan", [Token("Juan", Span(0, 4), Role.GIVEN)]).__getstate__()),
        "ambiguities"),
                 "missing fields: ambiguities",
                 id="missing-shipped-field-with-default-on-parsedname"),
    pytest.param(Ambiguity, lambda: {**_ambiguity_state(), "zq_future": 1},
                 "unexpected fields: zq_future", id="unexpected-field"),
    pytest.param(Ambiguity, lambda: {**_without(_ambiguity_state(),
                                                "alternative"),
                                     "zq_future": 1},
                 "unexpected fields: zq_future",
                 id="unexpected-field-beside-a-missing-added-one"),
    pytest.param(Ambiguity, lambda: _without(_ambiguity_state(),
                                             "alternative", "detail"),
                 "missing fields: detail;",
                 id="missing-field-without-default-beside-a-missing-added-one"),
    pytest.param(Ambiguity, lambda: _renamed(_ambiguity_state(), "detail",
                                             "details"),
                 "missing fields: detail; unexpected fields: details",
                 id="renamed-field"),
    pytest.param(Ambiguity, lambda: _renamed(_ambiguity_state(),
                                             "alternative", "alt"),
                 "unexpected fields: alt",
                 id="renamed-added-field"),
    # ParsedName.order (3.0, #754) is admitted missing, as `alternative`
    # is, and refused renamed or beside a shipped field missing
    pytest.param(ParsedName, lambda: _renamed(dict(
        _pn("Juan", [Token("Juan", Span(0, 4), Role.GIVEN)]).__getstate__()),
        "order", "ordr"),
                 "unexpected fields: ordr",
                 id="renamed-added-field-on-parsedname"),
    pytest.param(ParsedName, lambda: _without(dict(
        _pn("Juan", [Token("Juan", Span(0, 4), Role.GIVEN)]).__getstate__()),
        "order", "ambiguities"),
                 "missing fields: ambiguities;",
                 id="missing-shipped-field-beside-a-missing-order"),
    # Token.reading (3.0) beside the shipped fields it must not excuse
    pytest.param(Token, lambda: _without(_token_state(), "reading", "tags"),
                 "missing fields: tags;",
                 id="missing-shipped-field-beside-a-missing-reading"),
    pytest.param(Token, lambda: _renamed(_token_state(), "reading",
                                         "readings"),
                 "unexpected fields: readings",
                 id="renamed-reading"),
    # Locale.languages (3.0, phase 3b) beside the shipped fields it must
    # not excuse
    pytest.param(Locale, lambda: _without(_locale_state(), "languages",
                                          "policy"),
                 "missing fields: policy;",
                 id="locale-missing-shipped-field-beside-missing-languages"),
    pytest.param(Locale, lambda: _renamed(_locale_state(), "languages",
                                          "language"),
                 "unexpected fields: language",
                 id="locale-renamed-languages"),
    # Reading.languages (3.0) likewise
    pytest.param(Reading, lambda: _without(_reading_state(), "languages",
                                           "source"),
                 "missing fields: source;",
                 id="missing-shipped-field-beside-missing-languages"),
    pytest.param(Reading, lambda: _renamed(_reading_state(), "languages",
                                           "language"),
                 "unexpected fields: language",
                 id="renamed-languages"),
    # Reading.second_surname (3.0, rules/R10) likewise
    pytest.param(Reading, lambda: _without(_reading_state(),
                                           "second_surname", "source"),
                 "missing fields: source;",
                 id="missing-shipped-field-beside-missing-second-surname"),
    pytest.param(Reading, lambda: _renamed(_reading_state(),
                                           "second_surname", "surname2"),
                 "unexpected fields: surname2",
                 id="renamed-second-surname"),
]


def _locale_state() -> dict[str, object]:
    return dict(Locale("pt", Lexicon.empty(),
                       languages=frozenset({"pt"})).__getstate__())


def test_a_locale_pickled_before_3_0_loads_choosing_no_language() -> None:
    state = _without(_locale_state(), "languages")
    loaded = Locale.__new__(Locale)
    loaded.__setstate__(state)
    assert loaded.languages == frozenset()
    assert loaded == Locale("pt", Lexicon.empty())


@pytest.mark.parametrize("cls,state,match", _REFUSED_SKEWS)
def test_setstate_still_refuses_every_skew_it_refused(
        cls: type, state: Callable[[], dict[str, object]], match: str) -> None:
    with pytest.raises(ValueError, match=match):
        object.__new__(cls).__setstate__(state())


def test_setstate_admits_a_field_added_later_missing_from_an_older_pickle(
        ) -> None:
    state = _without(_ambiguity_state(), "alternative")
    loaded = Ambiguity.__new__(Ambiguity)
    loaded.__setstate__(state)
    assert loaded.alternative is None
    assert loaded == Ambiguity(**state)  # type: ignore[arg-type]


def test_a_token_pickled_before_3_0_loads_without_a_reading() -> None:
    state = _without(_token_state(), "reading")
    loaded = Token.__new__(Token)
    loaded.__setstate__(state)
    assert loaded.reading is None
    assert loaded == Token(**_token_state())  # type: ignore[arg-type]


def test_token_reading_is_a_reading_and_is_not_compared() -> None:
    from nameparser import Reading
    read = Reading("name", "family", "position")  # type: ignore[arg-type]
    tok = Token("Vega", Span(18, 22), Role.FAMILY, reading=read)
    bare = Token("Vega", Span(18, 22), Role.FAMILY)
    assert bare.reading is None
    assert tok == bare and hash(tok) == hash(bare)
    assert repr(tok) == repr(bare)
    with pytest.raises(TypeError, match="Token.reading must be a Reading"):
        Token("Vega", Span(18, 22), Role.FAMILY,
              reading=("name", "family"))  # type: ignore[arg-type]


def test_a_parsedname_pickled_by_2_8_0_loads() -> None:
    """tests/v2/data/parsedname_v28.pickle is `parse("Dr. Juan Q. de la
    Vega III")` pickled (protocol 4) by the released 2.8.0 wheel, the
    last 2.x release, its tokens written before `Token.reading`
    existed. Made 2026-10-29 the way the 2.6.0 fixture below was
    (`PYTHONSAFEPATH=1 uv run --isolated --no-project --with
    'nameparser==2.8.0'` outside the checkout, version and module path
    asserted). pickle.load is safe here: a repo-controlled fixture."""
    import pickle
    with open(Path(__file__).parent / "data" / "parsedname_v28.pickle",
              "rb") as f:
        loaded = pickle.load(f)
    now = parse("Dr. Juan Q. de la Vega III")
    assert loaded == now
    assert all(t.reading is None for t in loaded.tokens)
    assert all(t.reading is not None for t in now.tokens)
    again = pickle.loads(pickle.dumps(now))
    assert [t.reading for t in again.tokens] == [t.reading for t in now.tokens]


def test_a_reading_pickled_by_2_8_0_loads_without_languages() -> None:
    """tests/v2/data/parsedname_v28_alternative.pickle is `parse("JOHN
    SMITH MA")` pickled (protocol 4) by the released 2.8.0 wheel, its
    Ambiguity's alternative a Reading written before
    `Reading.languages` existed. Made 2026-10-29 the way the fixture
    above was, version and module path asserted. pickle.load is safe
    here: a repo-controlled fixture."""
    import pickle
    with open(Path(__file__).parent / "data"
              / "parsedname_v28_alternative.pickle", "rb") as f:
        loaded = pickle.load(f)
    now = parse("JOHN SMITH MA")
    (old,), (new,) = loaded.ambiguities, now.ambiguities
    assert old.alternative is not None and new.alternative is not None
    assert old.alternative.languages == ()
    assert new.alternative.languages == ("en",)
    assert old.alternative == new.alternative
    again = pickle.loads(pickle.dumps(now))
    assert [t.reading.languages for t in again.tokens if t.reading] == [
        t.reading.languages for t in now.tokens if t.reading]


def test_a_parsedname_pickled_by_2_6_0_loads() -> None:
    """tests/v2/data/parsedname_v26.pickle is `parse("JOHN SMITH MA")`
    pickled (protocol 4) by the released 2.6.0 wheel, its Ambiguity
    written before `alternative` existed. Made 2026-10-26 with
    `PYTHONSAFEPATH=1 uv run --isolated --no-project --with
    'nameparser==2.6.0'` from a directory outside the checkout, the
    version and the module path asserted (AGENTS.md's v1 comparison
    trap). pickle.load is safe here: a repo-controlled fixture."""
    import pickle
    with open(Path(__file__).parent / "data" / "parsedname_v26.pickle",
              "rb") as f:
        loaded = pickle.load(f)
    now = parse("JOHN SMITH MA")
    # the fields and the report as 2.6.0 read them (the tags are
    # unstable provenance, and `ma` has gained one since)
    assert loaded.as_dict() == now.as_dict()
    assert [(a.kind, a.detail) for a in loaded.ambiguities] == [
        (a.kind, a.detail) for a in now.ambiguities]
    assert loaded.ambiguities[0].alternative is None
    assert now.ambiguities[0].alternative is not None
    assert pickle.loads(pickle.dumps(now)).ambiguities[0].alternative == (
        now.ambiguities[0].alternative)


def test_a_parsedname_pickled_by_2_8_0_loads_and_renders_given_first(
        ) -> None:
    """tests/v2/data/parsedname_v28_korean.pickle is `parse("김민준")` pickled
    (protocol 4) by the released 2.8.0 wheel, written before
    `ParsedName.order` existed. Made 2026-10-29 with `PYTHONSAFEPATH=1
    uv run --isolated --no-project --with 'nameparser==2.8.0'` from a
    directory outside the checkout, the version and the module path
    asserted. It loads with no order and renders given-first, as 2.x
    did, while a fresh parse renders as written and the two compare
    equal (rules/R6's Accepted bullet, decisions/R6). pickle.load is
    safe here: a repo-controlled fixture."""
    import pickle
    with open(Path(__file__).parent / "data"
              / "parsedname_v28_korean.pickle",
              "rb") as f:
        loaded = pickle.load(f)
    now = parse("김민준")
    assert loaded.order is None
    assert now.order == FAMILY_FIRST
    assert loaded == now
    assert (str(loaded), str(now)) == ("민준 김", "김민준")
    assert pickle.loads(pickle.dumps(now)).order == FAMILY_FIRST


def test_a_2_8_0_pickle_renders_as_2_8_0_did_separators_included(
        ) -> None:
    """tests/v2/data/parsednames_v28_separators.pickle holds
    `parse()` of `John Smith, Jr.`, `威廉·莎士比亚` and `山田　太郎`
    pickled (protocol 4) by the released 2.8.0 wheel, whose str() gave
    the three renderings asserted below; made 2026-10-29 as the v28
    fixture above was. The decision promises a 2.x pickle renders as
    today (decisions/vocabulary-model's #754 output-model entry, item
    6), so a name with no order keeps 2.x's spacing too, not only its
    given-first layout. pickle.load is safe here: a repo-controlled
    fixture."""
    import pickle
    with open(Path(__file__).parent / "data"
              / "parsednames_v28_separators.pickle", "rb") as f:
        loaded = pickle.load(f)
    assert [n.order for n in loaded] == [None, None, None]
    assert [str(n) for n in loaded] == [
        "John Smith Jr.", "威廉 莎士比亚", "太郎 山田"]
    assert [str(parse(n.original)) for n in loaded] == [
        "John Smith, Jr.", "威廉·莎士比亚", "山田 太郎"]


def test_parsedname_order_is_not_compared_and_stores_a_tuple() -> None:
    tok = Token("Juan", Span(0, 4), Role.GIVEN)
    assert ParsedName("Juan", (tok,), order=FAMILY_FIRST) == ParsedName(
        "Juan", (tok,))
    listed = ParsedName("Juan", (tok,),
                        order=list(FAMILY_FIRST))  # type: ignore[arg-type]
    assert listed.order == FAMILY_FIRST and isinstance(listed.order, tuple)


def _policy_order(value: object) -> object:
    return Policy(name_order=value)  # type: ignore[arg-type]


def _parsedname_order(value: object) -> object:
    return ParsedName("x", (), order=value)  # type: ignore[arg-type]


# the family: every field holding a name order refuses the same values
# with the same exception (AGENTS.md, "Guard, hint, and emit for the
# WHOLE family")
@pytest.mark.parametrize("build", [_policy_order, _parsedname_order],
                         ids=["Policy.name_order", "ParsedName.order"])
@pytest.mark.parametrize("bad, exc, match", [
    (("given", "middle", "family"), TypeError, "must be Role members"),
    ("gmf", TypeError, "not a bare string"),
    ({Role.GIVEN: 0}, TypeError, "not a mapping"),
    (frozenset(FAMILY_FIRST), TypeError, "ordered iterable"),
    (set(GIVEN_FIRST), TypeError, "ordered iterable"),
    (5, TypeError, "must be an iterable"),
    ((Role.GIVEN, Role.FAMILY, Role.MIDDLE), ValueError, "exported orders"),
])
def test_every_name_order_field_refuses_the_same_values(
        build: Callable[[object], object], bad: object, exc: type,
        match: str) -> None:
    with pytest.raises(exc, match=match):
        build(bad)


def test_replace_and_capitalized_keep_the_order() -> None:
    name = parse("김민준")
    assert name.replace(given="서연").order == FAMILY_FIRST
    assert name.capitalized().order == FAMILY_FIRST
    assert parse("Smith, John").order == GIVEN_FIRST


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
    from nameparser import ReadingKind, ReadingSource
    values = {enum: {m.value for m in enum}
              for enum in (Role, AmbiguityKind, PatronymicRule,
                           ReadingKind, ReadingSource)}
    # the one deliberate overlap: a title reading names the title field
    allowed = {frozenset({Role, ReadingKind}): {"title"}}
    for a, b in itertools.combinations(values, 2):
        assert values[a] & values[b] == allowed.get(frozenset({a, b}), set())


def test_with_field_tokens_rejects_mismatched_roles() -> None:
    name = parse("John Smith")
    with pytest.raises(ValueError, match="has role family, not given"):
        name._with_field_tokens(
            {Role.GIVEN: (Token("x", None, Role.FAMILY),)})


@pytest.mark.parametrize("delimiter", ["/", "-", "+", "&"])
@pytest.mark.parametrize("text,generation", [
    ("John Smith, Jr.{d} MD", "Jr.{d}"),
    ("John Smith, III{d} MD", "III{d}"),
    ("John Smith, MD {d}Jr.", "{d}Jr."),
])
def test_a_declared_delimiter_glued_to_a_generation_keeps_it_one(
        delimiter: str, text: str, generation: str) -> None:
    # the spelling sweep over the delimiter a caller declares, glued to
    # either end (rules/C10): classify reads the stem's kind
    pn = Parser(policy=Policy(
        extra_suffix_delimiters=frozenset({delimiter}))).parse(
            text.format(d=delimiter))
    assert (pn.generation, pn.credentials) == (
        generation.format(d=delimiter), "MD")


# -- the patronymic view (rules/R9, #754) --------------------------------

_RU = Parser(policy=Policy(patronymic_rules={"east-slavic"}))  # type: ignore[arg-type]
_TR = Parser(policy=Policy(patronymic_rules={"turkic"}))  # type: ignore[arg-type]


@pytest.mark.parametrize("parser,text,patronymic,field", [
    # the empty path: no particle, and a name written without one
    (Parser(), "John Smith", "", "Smith"),
    (Parser(), "Anwar Ibrahim", "", "Ibrahim"),
    # a particle and its parent's name, the family keeping them
    (Parser(), "Mahathir bin Mohamad", "bin Mohamad", "bin Mohamad"),
    (Parser(), "Ahmad bin Abdul Rahman", "bin Abdul Rahman", "bin Abdul Rahman"),
    (Parser(), "Abdul Rahman bin Ahmad", "bin Ahmad", "bin Ahmad"),
    (Parser(), "Mahathir bin Mohamad Jr.", "bin Mohamad", "bin Mohamad"),
    # two of them, across the middle and the family
    (Parser(), "Ali bin Ahmad bin Hasan", "bin Ahmad bin Hasan", "bin Hasan"),
    # P6's trailing particle: the family written before it, in the
    # family's order
    (Parser(), "Mohamad, Mahathir bin", "bin Mohamad", "bin Mohamad"),
    (Parser(policy=Policy(name_order=FAMILY_FIRST)), "Mohamad Mahathir bin",
     "bin Mohamad", "bin Mohamad"),
    # the particle read as a name, or ending its field, names no parent
    (Parser(), "Mahathir, bin Mohamad", "", "Mahathir"),
    (Parser(), "Mohamad Mahathir bin", "", "bin"),
    (Parser(), "Fritz Freiherr und von Bar", "", "Freiherr und von Bar"),
    # a nickname inside the run is skipped
    (Parser(), "Ahmad bin (Bob) Ali", "bin Ali", "bin Ali"),
    # the East Slavic arm: a middle word carrying the ending
    (_RU, "Ivan Ivanovich Ivanov", "Ivanovich", "Ivanov"),
    (_RU, "Ivanov, Ivan Ivanovich", "Ivanovich", "Ivanov"),
    (_RU, "Roman Abramovich", "", "Abramovich"),
    (Parser(), "Ivan Ivanovich Ivanov", "", "Ivanov"),
    # under middle_as_family the folded middle is still the middle
    (Parser(policy=Policy(patronymic_rules={"east-slavic"},  # type: ignore[arg-type]
                          middle_as_family=True)),
     "Ivan Ivanovich Ivanov", "Ivanovich", "Ivanovich Ivanov"),
    (Parser(policy=Policy(middle_as_family=True)),
     "Ali bin Ahmad Hasan Musa", "bin Ahmad Hasan Musa", "bin Ahmad Hasan Musa"),
    # the Turkic arm: a marker and the name word before it, in its part
    (_TR, "Ali Ahmad Vali oglu", "Vali oglu", "Ali"),
    (_TR, "Ali Ahmad oglu", "Ahmad oglu", "oglu"),
    (_TR, "Ali (Bob) oglu", "Ali oglu", "oglu"),
    (_TR, "oglu Ali", "", "Ali"),
    (_TR, "Aliyev, oglu", "", "Aliyev"),
])
def test_the_patronymic_view_reads_a_particle_or_a_rule(
        parser: Parser, text: str, patronymic: str, field: str) -> None:
    pn = parser.parse(text)
    assert pn.patronymic == patronymic
    assert pn.family == field


_MAF = Policy(middle_as_family=True)


@pytest.mark.parametrize("policy,text,patronymic", [
    # P6's attachment is told by its shape, not by the field the
    # middle fold reads its folded mark as, so middle_as_family keeps it
    (Policy(), "Mohamad, Mahathir bin", "bin Mohamad"),
    (_MAF, "Mohamad, Mahathir bin", "bin Mohamad"),
    (Policy(), "Levi, Omer Bar", "Bar Levi"),
    (_MAF, "Levi, Omer Bar", "Bar Levi"),
    (Policy(name_order=FAMILY_FIRST, middle_as_family=True),
     "Mohamad Mahathir bin", "bin Mohamad"),
    # a folded middle with a word behind it is a run, not an attachment
    (Policy(name_order=FAMILY_FIRST, middle_as_family=True),
     "Mohamad Mahathir bin Ali", "bin Ali"),
    # a particle ending the family before a comma has no word after it
    # in its field: the given name behind the comma is not its parent's
    (Policy(), "Ali bin, Ali", ""),
    (Policy(), "Ahmad bin, Ali", ""),
    # P6 attaching two particles: the family's own words, not the
    # other folded particle, are the parent's name
    (Policy(name_order=FAMILY_FIRST), "Ahmad Ahmad de bin", "bin Ahmad"),
    # a suffix ends the run, so a family word behind it is not in it
    (Policy(), "bin Ahmad Jr. Hasan, Ali", "bin Ahmad"),
    # P6 attaching a patronymic particle with another particle after
    # it: the attached words and the family they attach to, the second
    # review's D1
    (Policy(), "Bakar, Ali bin Abu", "bin Abu Bakar"),
    (Policy(), "Saud, Mohammed bin Al", "bin Al Saud"),
    (Policy(), "Mohamad, Mahathir bin de", "bin de Mohamad"),
    (Policy(name_order=FAMILY_FIRST), "Ahmad Ali bin al", "bin al Ahmad"),
    (_MAF, "Bakar, Ali bin Abu", "bin Abu Bakar"),
    (Policy(), "Ahmad, Ali bin bin", "bin bin Ahmad"),
    # a trailing particle P6 declines (no given word ahead of it) that
    # O3 folds is no attachment: the second review's D2
    (Policy(), "Rahman, Al bin", ""),
    (_MAF, "Rahman, Al bin", ""),
    (Policy(name_order=FAMILY_FIRST, middle_as_family=True),
     "Rahman, Al bin", ""),
    (_MAF, "Ahmad, bin bin", ""),
    (_MAF, "Ali, van bin", ""),
    (_MAF, "Ahmad Omar, Bar Bar", ""),
    (_MAF, "Ahmad, Dr. bin Bar", ""),
    # a word P6 attached stands as the family under the fold, so a
    # folded middle's run does not reach it
    (_MAF, "Ali, Ahmad bin Ahmad Abu", "bin Ahmad"),
    # behind an empty head P6 attaches the particle as the whole
    # family, which names no one, fold or no fold: the third review's
    # D-A, the empty-head comma (C15) the shape test refused
    (Policy(), ", Siti Aminah binti", ""),
    (_MAF, ", Siti Aminah binti", ""),
    (Policy(name_order=FAMILY_FIRST, middle_as_family=True),
     ", Siti Aminah binti", ""),
    (_MAF, ", Ali Ali bin", ""),
    (_MAF, ", Dr. Ali Ahmad bin", ""),
    (_MAF, ", Dr. Siti Aminah binti Jr.", ""),
    (_MAF, ", Siti Aminah binti (Bob)", ""),
    (Policy(name_order=FAMILY_FIRST_GIVEN_LAST, middle_as_family=True),
     ", Siti Aminah binti", ""),
    # a nickname-only head, and a part past the second comma
    (_MAF, "(Bob), Siti Aminah binti", ""),
    (_MAF, ", Siti Aminah binti, Hasan", ""),
])
def test_the_patronymic_run_and_the_attachment_under_each_policy(
        policy: Policy, text: str, patronymic: str) -> None:
    assert Parser(policy=policy).parse(text).patronymic == patronymic


def test_middle_as_family_moves_no_patronymic_r2_does_not_move() -> None:
    # O3's fold changes where a middle word renders, not what it is, so
    # a name reads the same patronymic with and without it wherever R2
    # reads its particles alike: a part made only of particles is name
    # words (R2's unjoined mark), and the fold can give one a base
    # ('Ali, bin bin Abu' reads patronymic 'bin Abu' under the fold
    # alone, rules/R9's Accepted). The words, not their order: the
    # view writes the family's words as the family does. A grid of
    # particle, comma and given-name shapes (2,540 texts, each under
    # two orders, about a second on 2026-10-29); compared: 4,494 of
    # the 5,080 parses, the rest the R2 shape above. What it guards: a
    # word P6 attached standing as the family under the fold (10 moves
    # on 021268ed). What it cannot see: a shape whose R2 marks differ
    # between the policies, the second review's D2 and the third's
    # empty-head D-A, and one the fold leaves alike, D1; the rows of
    # the test above hold those
    words = ["Ahmad", "bin", "Abu", "de", "Ali,"]
    texts = [" ".join(c) for n in range(2, 6)
             for c in itertools.product(words, repeat=n) if "bin" in c]
    assert len(texts) == 2540

    def unjoined(pn: ParsedName) -> list[bool]:
        return [UNJOINED_TAG in t.tags for t in pn.tokens]

    moved, compared = [], 0
    for order in (GIVEN_FIRST, FAMILY_FIRST):
        plain = Parser(policy=Policy(name_order=order))
        folded = Parser(policy=Policy(name_order=order, middle_as_family=True))
        for text in texts:
            a, b = plain.parse(text), folded.parse(text)
            if unjoined(a) != unjoined(b):
                continue
            compared += 1
            # the same words: the fold writes the family's folded words
            # first, and the view writes the family's words as it does
            if sorted(a.patronymic.split()) != sorted(b.patronymic.split()):
                moved.append((text, order, a.patronymic, b.patronymic))
    assert not moved, moved[:10]
    assert compared == 4494


def test_a_turkic_marker_a_caller_lists_as_a_connective_names_no_father(
        ) -> None:
    # the marker keeps the connective reading the caller's Lexicon gives
    # it, so neither it nor the word before it is a patronymic
    parser = Parser(lexicon=Lexicon.default().add(conjunctions={"oglu"}),
                    policy=Policy(patronymic_rules={"turkic"}))  # type: ignore[arg-type]
    pn = parser.parse("Ali Ahmad Vali oglu Hasan")
    assert pn.patronymic == ""
    assert [t.reading.kind.value for t in pn.tokens if t.reading] == [
        "name", "name", "name", "conjunction", "name"]


def test_a_patronymic_word_with_no_reading_is_not_in_the_view() -> None:
    # replace() and revise() record no reading (4a), so nothing says
    # what the word was; a field they did not touch keeps its readings
    pn = parse("Mahathir bin Mohamad")
    assert pn.replace(family="bin Mohamad").patronymic == ""
    assert Parser().revise(pn, family="bin Ali").patronymic == ""
    assert pn.replace(given="Anwar").patronymic == "bin Mohamad"


def test_the_patronymic_view_is_a_render_key_and_not_a_field() -> None:
    pn = parse("Mahathir bin Mohamad")
    assert pn.render("{given} ({patronymic})") == "Mahathir (bin Mohamad)"
    assert "patronymic" not in pn.as_dict()
    assert "patronymic" not in repr(pn)
    assert pn.comparison_key() == parse("Mahathir bin Mohamad").replace(
        family="bin Mohamad").comparison_key()
    with pytest.raises(TypeError):
        pn.replace(patronymic="bin Ali")  # type: ignore[call-arg]


def test_a_patronymic_parsedname_pickled_by_2_8_0_loads_equal() -> None:
    """tests/v2/data/parsedname_v28_patronymic.pickle is `parse("Mahathir
    bin Mohamad")` pickled (protocol 4) by the released 2.8.0 wheel,
    made 2026-10-29 as the fixture above was. classify's
    `vocab:patronymic` tag never reaches a published token, which
    compares its tags, so the 2.x name is equal to its 3.0 parse and,
    with no readings, has no patronymic. pickle.load is safe here: a
    repo-controlled fixture."""
    import pickle
    with open(Path(__file__).parent / "data"
              / "parsedname_v28_patronymic.pickle", "rb") as f:
        loaded = pickle.load(f)
    now = parse("Mahathir bin Mohamad")
    assert loaded == now
    assert (loaded.patronymic, now.patronymic) == ("", "bin Mohamad")
    assert not any(t.startswith("vocab:patronymic")
                   for tok in now.tokens for t in tok.tags)
    # nor does P6's attachment mark, on the words it attaches
    attached = parse("Bakar, Ali bin Abu")
    assert attached.patronymic == "bin Abu Bakar"
    assert not any(t == "vocab:attached"
                   for tok in attached.tokens for t in tok.tags)


# -- the surname2 view (rules/R10, 3.0's 4d) ---------------------------

_GF, _FF, _FFGL = GIVEN_FIRST, FAMILY_FIRST, FAMILY_FIRST_GIVEN_LAST

#: (text, name_order, middle_as_family, surname2) under
#: two_family_names; every row reads '' with the switch off. The ''
#: rows are the shapes rules/O6 declines, each kept so a widening of
#: what fills the view shows here (AGENTS.md's widened-check rule).
_SURNAME2_ROWS = [
    # given-first: the family O6 found is the second unit
    ("Gabriel García Márquez", _GF, False, "Márquez"),
    ("Ana María García López", _GF, False, "López"),
    ("Juan Pérez de la Vega", _GF, False, "de la Vega"),
    # O3 folds the middles left in front of both units, into neither
    ("Ana María García López", _GF, True, "López"),
    # titles, suffixes and nicknames are no name words
    ("Gabriel García Márquez Jr.", _GF, False, "Márquez"),
    ("Dr. Ana García López", _GF, False, "López"),
    ("Gabriel García Márquez, PhD", _GF, False, "Márquez"),
    ("Ana García (Anita) López", _GF, False, "López"),
    # family-first: the word O6 took is the second unit
    ("García Márquez Gabriel", _FF, False, "Márquez"),
    ("García Márquez Ana María", _FFGL, False, "Márquez"),
    ("García Márquez Ana María", _FF, True, "Márquez"),
    ("García Márquez Ana María", _FFGL, True, "Márquez"),
    ("de Mesnil Jean Paul", _FF, False, "Jean"),
    ("van Gogh Ana María", _FF, False, "Gogh"),
    # P6's particle attaches to the first unit and stays out
    ("Beethoven Ludwig Maria van", _FF, False, "Ludwig"),
    ("Beethoven Ludwig Maria van", _FF, True, "Ludwig"),
    # a family comma alone marks nothing, in every comma shape
    ("Lloyd Webber, Andrew", _GF, False, ""),
    ("García López, Ana", _GF, False, ""),
    ("García López, Ana", _FF, True, ""),
    ("López, Ana García", _GF, True, ""),
    ("Ana, García López", _GF, False, ""),
    (", Ana García López", _GF, False, ""),
    (", Ana García López", _GF, True, ""),
    ('"Anita", Ana García López', _GF, True, ""),
    # a family that already holds two words keeps them as one unit
    ("Ana María García-López", _GF, False, ""),
    ("Ana María García-López", _GF, True, ""),
    ("José María Ortega y Gasset", _GF, False, ""),
    ("Juan Pérez y Gómez", _GF, False, ""),
    ("García de la Vega López", _GF, False, ""),
    ("Ana María de la Vega Rodríguez", _GF, False, ""),
    # O6's other declines
    ("Ana García", _GF, False, ""),
    ("Ana María-José López", _GF, False, ""),
    ("Ana abdul Rahman López", _GF, False, ""),
    ("Ana M. García", _GF, False, ""),
    ("Juan de la Vega Rodríguez", _FF, False, ""),
    ("王 小 明", _GF, False, ""),
]


@pytest.mark.parametrize("text,order,fold,want", _SURNAME2_ROWS)
def test_the_surname2_view_reads_the_second_unit_o6_read(
        text: str, order: tuple[Role, Role, Role], fold: bool,
        want: str) -> None:
    on = Parser(policy=Policy(two_family_names=True, name_order=order,
                              middle_as_family=fold)).parse(text)
    off = Parser(policy=Policy(name_order=order,
                               middle_as_family=fold)).parse(text)
    assert on.surname2 == want
    assert off.surname2 == ""
    if want:
        # a part of `family`, which keeps both units, ending it
        assert on.family.endswith(" " + want)
    # the mark never reaches a published token, which compares its tags
    assert not any(t == "vocab:second-surname"
                   for tok in on.tokens for t in tok.tags)


def test_the_second_surname_keeps_the_reading_it_took() -> None:
    # a patronymic run in the second unit reads both views (rules/R9)
    two = Parser(policy=Policy(two_family_names=True))
    pn = two.parse("Ali Hassan bin Ahmad")
    assert (pn.family, pn.surname2, pn.patronymic) == (
        "Hassan bin Ahmad", "bin Ahmad", "bin Ahmad")
    assert [str(t.reading) for t in pn.tokens[2:]] == [
        "Reading('patronymic' as 'family', 'vocabulary', in ar ms, "
        "second surname)",
        "Reading('patronymic' as 'family', 'position', second surname)"]
    # and a word P6's attached particle makes a parent's name keeps it
    ff = Parser(policy=Policy(two_family_names=True,
                              name_order=FAMILY_FIRST))
    pn = ff.parse("Mohamad Ali Mahathir bin")
    assert (pn.family, pn.surname2, pn.patronymic) == (
        "bin Mohamad Ali", "Ali", "bin Mohamad Ali")


def test_the_surname2_view_beside_an_east_slavic_patronymic() -> None:
    from nameparser import locales, parser_for
    ru = parser_for(locales.RU)
    p = Parser(lexicon=ru.lexicon,
               policy=dataclasses.replace(ru.policy, two_family_names=True))
    pn = p.parse("Ivan Sergeyevich Petrov Ivanov")
    assert (pn.middle, pn.family, pn.surname2, pn.patronymic) == (
        "Sergeyevich", "Petrov Ivanov", "Ivanov", "Sergeyevich")
    # where the rotation fires it decided the family, and O6 reads none
    pn = p.parse("Ivanov Ivan Ivanovich")
    assert (pn.family, pn.surname2) == ("Ivanov", "")


@pytest.mark.parametrize("text,second,family,patronymic", [
    ("Ali Vali oglu", "Vali", "Ali Vali", "Vali oglu"),
    ("Leyla Rasim qizi", "Rasim", "Leyla Rasim", "Rasim qizi"),
])
def test_a_turkic_father_in_the_second_surname_keeps_the_mark(
        text: str, second: str, family: str, patronymic: str) -> None:
    # the father's reading is rebuilt at its marker, which must carry
    # the second-surname mark over (rules/R10 beside rules/R9)
    from nameparser import locales, parser_for
    tr = parser_for(locales.TR_AZ)
    p = Parser(lexicon=tr.lexicon, policy=dataclasses.replace(
        tr.policy, two_family_names=True, name_order=FAMILY_FIRST))
    pn = p.parse(text)
    assert (pn.surname2, pn.family, pn.patronymic) == (
        second, family, patronymic)


def test_the_surname2_view_is_a_render_key_and_not_a_field() -> None:
    p = Parser(policy=Policy(two_family_names=True))
    pn = p.parse("Gabriel García Márquez")
    assert pn.render("{surname2}, {given}") == "Márquez, Gabriel"
    assert "surname2" not in pn.as_dict()
    assert "surname2" not in repr(pn)
    assert pn.comparison_key() == parse("Gabriel García Márquez").replace(
        middle="", family="García Márquez").comparison_key()
    with pytest.raises(TypeError):
        pn.replace(surname2="López")  # type: ignore[call-arg]
    # a family written by replace() or revise() carries no reading
    assert pn.replace(family="García Márquez").surname2 == ""
    assert p.revise(pn, family="García Márquez").surname2 == ""
    assert pn.replace(title="Dr.").surname2 == "Márquez"


def test_a_two_family_name_parsedname_pickled_by_2_8_0_loads_equal() -> None:
    """tests/v2/data/parsedname_v28_two_family_names.pickle is
    `Parser(policy=Policy(two_family_names=True)).parse("Gabriel García
    Márquez")` pickled (protocol 4) by the released 2.8.0 wheel, made
    2026-10-29 as the fixtures above were, version and module path
    asserted. O6's mark never reaches a published token, and
    `Reading.second_surname` is not compared, so the 2.x name is equal
    to its 3.0 parse and, with no readings, has no second surname.
    pickle.load is safe here: a repo-controlled fixture."""
    import pickle
    with open(Path(__file__).parent / "data"
              / "parsedname_v28_two_family_names.pickle", "rb") as f:
        loaded = pickle.load(f)
    now = Parser(policy=Policy(two_family_names=True)).parse(
        "Gabriel García Márquez")
    assert loaded == now
    assert (loaded.surname2, now.surname2) == ("", "Márquez")
    again = pickle.loads(pickle.dumps(now))
    assert again.surname2 == "Márquez"


def test_a_hand_built_mark_outside_the_family_is_not_in_the_view() -> None:
    from nameparser import Reading
    marked = Reading("name", "given", "position", (), True)  # type: ignore[arg-type]
    pn = ParsedName("Ana López", (
        Token("Ana", Span(0, 3), Role.GIVEN, reading=marked),
        Token("López", Span(4, 9), Role.FAMILY)))
    assert pn.surname2 == ""


def test_reading_second_surname_is_a_bool_and_is_not_compared() -> None:
    from nameparser import Reading
    plain = Reading("name", "family", "position")  # type: ignore[arg-type]
    second = Reading("name", "family", "position", (), True)  # type: ignore[arg-type]
    assert plain.second_surname is False and second.second_surname is True
    assert second == plain and hash(second) == hash(plain)
    assert repr(second) == "Reading('name' as 'family', 'position', second surname)"
    assert repr(plain) == "Reading('name' as 'family', 'position')"
    with pytest.raises(TypeError, match=r"must be a bool, got 1; pass True"):
        Reading("name", "family", "position", (), 1)  # type: ignore[arg-type]


def test_a_reading_pickled_by_2_8_0_loads_with_no_second_surname() -> None:
    # the alternative fixture's Reading predates the field (ADDED_IN)
    import pickle
    with open(Path(__file__).parent / "data"
              / "parsedname_v28_alternative.pickle", "rb") as f:
        loaded = pickle.load(f)
    (amb,) = loaded.ambiguities
    assert amb.alternative is not None
    assert amb.alternative.second_surname is False
    # and a fresh report's alternative never names one
    (now,) = parse("JOHN SMITH MA").ambiguities
    assert now.alternative is not None
    assert now.alternative.second_surname is False
