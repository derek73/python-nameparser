import pytest

from nameparser._render import _collapse
from nameparser._types import ParsedName, Role, Span, Token


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
    from nameparser._render import render
    pn = _delavega()
    assert render(pn, "{title} {given} {middle} {family} {suffix}") \
        == "Dr. Juan de la Vega III"
    # empty middle collapses; comma survives correctly
    assert render(pn, "{family}, {given} {middle}") == "de la Vega, Juan"


def test_render_accepts_derived_view_keys() -> None:
    from nameparser._render import render
    assert render(_delavega(), "{family_base}, {given} {family_particles}") \
        == "Vega, Juan de la"
    assert render(_delavega(), "{surnames}") == "de la Vega"
    assert render(_delavega(), "{given_names}") == "Juan"


def test_render_every_role_key_is_valid() -> None:
    from nameparser._render import render
    pn = _delavega()
    for role in Role:
        render(pn, f"{{{role.value}}}")  # must not raise


def test_render_unknown_key_raises_enriched_keyerror() -> None:
    from nameparser._render import render
    with pytest.raises(KeyError, match="valid fields"):
        render(_delavega(), "{first}")  # v1 spelling: redirected loudly


def test_render_empty_parse_is_empty_string() -> None:
    from nameparser._render import render
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
