import pytest

from nameparser._lexicon import Lexicon
from nameparser._render import _collapse, render
from nameparser._types import Ambiguity, AmbiguityKind, ParsedName, Role, Span, Token


def test_collapse_is_the_254_algorithm() -> None:
    # normative: leading/trailing whitespace, doubled spaces,
    # space-before-comma, one trailing comma char (incl. Arabic/CJK),
    # leading/trailing ', ' debris, and empty-wrapper artifacts from
    # empty fields are removed
    assert _collapse("  John   Smith  ") == "John Smith"
    assert _collapse("Smith , John") == "Smith, John"
    assert _collapse("John Smith ,") == "John Smith"
    assert _collapse("John Smith،") == "John Smith"  # Arabic comma
    assert _collapse("John Smith，") == "John Smith"  # fullwidth comma
    assert _collapse(", John Smith, ") == "John Smith"
    assert _collapse("John Smith ()") == "John Smith"
    assert _collapse("John Smith ''") == "John Smith"
    assert _collapse('John Smith ""') == "John Smith"
    assert _collapse("") == ""


def _pn(original: str, tokens: list[Token]) -> ParsedName:
    return ParsedName(original=original, tokens=tuple(tokens))


def _delavega() -> ParsedName:
    # "Dr. Juan de la Vega III" -- spans verified by hand
    #  0123456789012345678901234
    return _pn("Dr. Juan de la Vega III", [
        Token("Dr.", Span(0, 3), Role.TITLE),
        Token("Juan", Span(4, 8), Role.GIVEN),
        Token("de", Span(9, 11), Role.FAMILY, frozenset({"particle"})),
        Token("la", Span(12, 14), Role.FAMILY, frozenset({"particle"})),
        Token("Vega", Span(15, 19), Role.FAMILY),
        Token("III", Span(20, 23), Role.SUFFIX),
    ])


def test_render_fills_fields_and_collapses() -> None:
    pn = _delavega()
    assert render(pn, "{title} {given} {middle} {family} {suffix}") \
        == "Dr. Juan de la Vega III"
    # empty middle collapses; comma survives correctly
    assert render(pn, "{family}, {given} {middle}") == "de la Vega, Juan"


def test_render_accepts_derived_view_keys() -> None:
    assert render(_delavega(), "{family_base}, {given} {family_particles}") \
        == "Vega, Juan de la"
    assert render(_delavega(), "{surnames}") == "de la Vega"
    assert render(_delavega(), "{given_names}") == "Juan"


def test_render_every_role_key_is_valid() -> None:
    pn = _delavega()
    for role in Role:
        render(pn, f"{{{role.value}}}")  # must not raise


def test_render_unknown_key_raises_enriched_keyerror() -> None:
    with pytest.raises(KeyError, match="valid fields"):
        render(_delavega(), "{first}")  # v1 spelling: redirected loudly


def test_render_empty_parse_is_empty_string() -> None:
    assert render(_pn("", []), "{title} {given} {middle} {family} {suffix}") == ""


def test_parsedname_render_and_str_delegate() -> None:
    pn = _delavega()
    assert pn.render() == "Dr. Juan de la Vega III"
    assert pn.render("{family}, {given}") == "de la Vega, Juan"
    assert str(pn) == pn.render()
    assert str(_pn("", [])) == ""


def _bobdole() -> ParsedName:
    # "Sir Bob Andrew Dole"
    #  01234567890123456789
    return _pn("Sir Bob Andrew Dole", [
        Token("Sir", Span(0, 3), Role.TITLE),
        Token("Bob", Span(4, 7), Role.GIVEN),
        Token("Andrew", Span(8, 14), Role.MIDDLE),
        Token("Dole", Span(15, 19), Role.FAMILY),
    ])


def test_initials_default_spec() -> None:
    assert _bobdole().initials() == "B. A. D."


def test_initials_skips_tagged_particles_outside_given() -> None:
    # family "de la Vega" with particle tags -> only V contributes;
    # a given-name token always contributes even if tagged
    assert _delavega().initials() == "J. V."
    # conjunction tag skips too
    pn = _pn("Mr. and Mrs. Smith", [
        Token("Mr.", Span(0, 3), Role.TITLE),
        Token("and", Span(4, 7), Role.FAMILY, frozenset({"conjunction"})),
        Token("Smith", Span(13, 18), Role.FAMILY),
    ])
    assert pn.initials("{family}") == "S."


def test_initials_custom_delimiter_and_separator() -> None:
    assert _bobdole().initials(delimiter="", separator="") == "B A D"


def test_initials_multiword_group_joins_within_group() -> None:
    pn = _pn("Mary Jane Watson", [
        Token("Mary", Span(0, 4), Role.GIVEN),
        Token("Jane", Span(5, 9), Role.GIVEN),
        Token("Watson", Span(10, 16), Role.FAMILY),
    ])
    assert pn.initials() == "M. J. W."


def test_initials_custom_spec_and_unknown_key() -> None:
    assert _bobdole().initials("{given} {middle}") == "B. A."
    with pytest.raises(KeyError, match="valid fields"):
        _bobdole().initials("{title}")


def test_initials_already_initial_words() -> None:
    pn = _pn("J. Doe", [
        Token("J.", Span(0, 2), Role.GIVEN),
        Token("Doe", Span(3, 6), Role.FAMILY),
    ])
    assert pn.initials() == "J. D."


def test_initials_empty_group_renders_empty() -> None:
    # v2 returns "" for an empty result -- no v1-style
    # empty_attribute_default fallback
    assert _bobdole().initials("{middle}") == "A."
    assert _pn("Cher", [Token("Cher", Span(0, 4), Role.GIVEN)]).initials("{middle}") == ""


def _lowercase_mac() -> ParsedName:
    # v1 capitalize() doctest input: 'bob v. de la macdole-eisenhower phd'
    #  0123456789012345678901234567890123456
    return _pn("bob v. de la macdole-eisenhower phd", [
        Token("bob", Span(0, 3), Role.GIVEN),
        Token("v.", Span(4, 6), Role.MIDDLE),
        Token("de", Span(7, 9), Role.FAMILY),
        Token("la", Span(10, 12), Role.FAMILY),
        Token("macdole-eisenhower", Span(13, 31), Role.FAMILY),
        Token("phd", Span(32, 35), Role.SUFFIX),
    ])


def test_capitalized_all_lower_input_v1_parity() -> None:
    out = _lowercase_mac().capitalized()
    assert out.given == "Bob"
    assert out.middle == "V."
    assert out.family == "de la MacDole-Eisenhower"  # particles stay lower
    assert out.suffix == "Ph.D."                     # exceptions map, verbatim
    # same spans, new texts (provenance is a documented non-invariant)
    assert [t.span for t in out.tokens] == [t.span for t in _lowercase_mac().tokens]


def test_capitalized_all_upper_input() -> None:
    pn = _pn("JOHN SMITH", [
        Token("JOHN", Span(0, 4), Role.GIVEN),
        Token("SMITH", Span(5, 10), Role.FAMILY),
    ])
    assert str(pn.capitalized()) == "John Smith"


def test_capitalized_preserves_mixed_case_unless_forced() -> None:
    pn = _pn("Shirley Maclaine", [
        Token("Shirley", Span(0, 7), Role.GIVEN),
        Token("Maclaine", Span(8, 16), Role.FAMILY),
    ])
    assert pn.capitalized() == pn                       # untouched
    assert pn.capitalized(force=True).family == "MacLaine"


def test_capitalized_is_idempotent() -> None:
    once = _lowercase_mac().capitalized()
    assert once.capitalized() == once
    assert once.capitalized(force=True) == once


def test_capitalized_with_explicit_lexicon() -> None:
    # empty lexicon: no particle rule, no exceptions -> plain capitalize
    out = _lowercase_mac().capitalized(Lexicon.empty())
    assert out.family == "De La MacDole-Eisenhower"
    assert out.suffix == "Phd"


def test_capitalized_lowers_conjunctions() -> None:
    #  01234567890123456789
    pn = _pn("juan ortega Y gasset", [
        Token("juan", Span(0, 4), Role.GIVEN),
        Token("ortega", Span(5, 11), Role.FAMILY),
        Token("Y", Span(12, 13), Role.FAMILY, frozenset({"conjunction"})),
        Token("gasset", Span(14, 20), Role.FAMILY),
    ])
    out = pn.capitalized(force=True)
    assert out.family == "Ortega y Gasset"


def test_capitalized_rebuilds_ambiguity_tokens() -> None:
    tok = Token("van", Span(0, 3), Role.GIVEN, frozenset({"particle"}))
    pn = ParsedName(
        original="van johnson",
        tokens=(tok, Token("johnson", Span(4, 11), Role.FAMILY)),
        ambiguities=(Ambiguity(AmbiguityKind.PARTICLE_OR_GIVEN,
                               "leading 'van' may be a particle", (tok,)),),
    )
    out = pn.capitalized()
    # the ambiguity references the NEW capitalized token (subset invariant)
    assert out.ambiguities[0].tokens[0] is out.tokens[0]
    assert out.ambiguities[0].tokens[0].text == "Van"


def test_render_and_initials_reject_non_str_arguments() -> None:
    # eager, like every constructor: not an AttributeError frames deep
    pn = _delavega()
    with pytest.raises(TypeError, match="spec must be a str"):
        pn.render(7)  # type: ignore[arg-type]
    with pytest.raises(TypeError, match="spec must be a str"):
        pn.initials(7)  # type: ignore[arg-type]
    with pytest.raises(TypeError, match="delimiter must be a str"):
        pn.initials(delimiter=None)  # type: ignore[arg-type]
    with pytest.raises(TypeError, match="separator must be a str"):
        pn.initials(separator=0)  # type: ignore[arg-type]


def test_capitalized_rejects_non_lexicon_argument() -> None:
    # previously a silent no-op on mixed-case input and a deep
    # AttributeError on single-case input
    with pytest.raises(TypeError, match="must be a Lexicon"):
        _delavega().capitalized("garbage")  # type: ignore[arg-type]
    with pytest.raises(TypeError, match="must be a Lexicon"):
        _lowercase_mac().capitalized({"titles": set()})  # type: ignore[arg-type]


def test_initials_given_tokens_ignore_skip_tags() -> None:
    # documented: a given-name token contributes even when tagged (the
    # PARTICLE_OR_GIVEN case -- 'van' read as a given name)
    pn = _pn("van Johnson", [
        Token("van", Span(0, 3), Role.GIVEN, frozenset({"particle"})),
        Token("Johnson", Span(4, 11), Role.FAMILY),
    ])
    assert pn.initials() == "v. J."


def test_render_malformed_specs_surface_raw_format_errors() -> None:
    # documented contract: only unknown KEYS get the enriched KeyError;
    # positional fields and bad conversions raise str.format's own error
    pn = _delavega()
    with pytest.raises(IndexError):
        pn.render("{}")
    with pytest.raises(ValueError):
        pn.render("{given!q}")
