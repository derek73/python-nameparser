import pytest

from nameparser import Parser
from nameparser._lexicon import Lexicon
from nameparser._render import _collapse, render
from nameparser._types import (UNJOINED_TAG, Ambiguity, AmbiguityKind,
                               ParsedName, Role, Span, Token)


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


def test_default_str_includes_nickname_and_maiden() -> None:
    # Derek's terminal find (2026-07-19): str(parse('Von Johnson
    # (smith)')) dropped the nickname; the default spec now shows all
    # seven fields -- nickname quoted after the given name, maiden
    # parenthesized after the family name (Derek's chosen format).
    # The nickname decoration round-trips exactly; the maiden parens
    # re-extract as a NICKNAME on reparse (documented trade-off:
    # presentation over lossless round-trip).
    from nameparser import parse

    assert str(parse("Von Johnson (smith)")) == 'Von "smith" Johnson'
    assert str(parse("Jane Smith née Jones")) == "Jane Smith (Jones)"
    both = parse("Jane (Janie) Smith née Jones")
    assert str(both) == 'Jane "Janie" Smith (Jones)'
    # no orphaned decoration when the fields are empty
    assert str(parse("Dr. Juan Q. Xavier de la Vega III")) == (
        "Dr. Juan Q. Xavier de la Vega III")


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


def test_initials_and_repair_agree_on_a_conjunction_in_a_particle_part() -> None:
    """#461, and the one shape that needs a caller's own Lexicon.

    The unjoined mark readmits the words of an all-particle part
    because none of them is acting as a particle there -- but it says
    nothing about a conjunction, which rules.md#R3 excludes "even
    then". Reaching that needs a word in `particles` AND
    `conjunctions`; the shipped sets are disjoint, in the default
    vocabulary and in every locale pack, so no input string can
    witness it and rules.md can carry no example line for it.

    This is also where the two views can be shown to agree, which is
    the whole point of the carve-out: before #461, `Anh y Van`
    capitalized as `Anh y Van` and initialed as `A. y. V.` -- one
    token, two views, opposite readings. The `capitalized` assertions
    here are what pins case repair's ungated conjunction conjunct
    (rules.md#R4); gating it on the mark passed the entire suite until
    this test existed, since no shipped name reaches it either.
    """
    # mechanisms.md#VOCABULARY-OVERLAP-AS-PRECONDITION: "assert the
    # intersection as a precondition" -- built here rather than found,
    # so what has to hold is the half not being added.
    assert "y" in Lexicon.default().conjunctions, (
        "'y' left the default conjunctions; this test builds the "
        "particle/conjunction overlap it needs from the other side and "
        "no longer has one. Pick another shipped conjunction.")
    lex = Lexicon.default().add(particles={"y"})
    p = Parser(lexicon=lex)

    van = p.parse("Anh y Van")
    tags = [t.tags for t in van.tokens if t.text == "y"][0]
    assert {"conjunction", "particle", UNJOINED_TAG} <= tags, sorted(tags)
    assert van.initials() == "A. V."
    assert van.capitalized(lex, force=True).family == "y Van"

    # R3's own example line, under a lexicon that makes `de y` the
    # all-particle part the default vocabulary cannot: `de` initials
    # as the ordinary name word R2 makes it, `y` still does not.
    assert p.parse("Juan de y").initials() == "J. d."
    # and a base that IS the conjunction contributes nothing at all
    assert p.parse("johnny y").initials() == "j."
    # unchanged where the part is particles alone
    assert p.parse("Juan van der").initials() == "J. v. d."


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


def test_capitalized_lowers_the_words_the_parse_tagged_conjunction() -> None:
    # #458: whether a word is the conjunction or an initial is
    # classify's decision, recorded as the tag; repair honors the tag
    # and never asks the word. Both halves of that are asserted here,
    # since a repair that lowered every conjunction-vocabulary word
    # would pass the first alone.
    #  01234567890123456789
    pn = _pn("juan ortega y gasset", [
        Token("juan", Span(0, 4), Role.GIVEN),
        Token("ortega", Span(5, 11), Role.FAMILY),
        Token("y", Span(12, 13), Role.FAMILY, frozenset({"conjunction"})),
        Token("gasset", Span(14, 20), Role.FAMILY),
    ])
    out = pn.capitalized(force=True)
    assert out.family == "Ortega y Gasset"
    # v1's is_conjunction excludes initial-shaped words, so classify
    # withholds the tag from an uppercase 'Y' and repair capitalizes it
    # ('JOSE ORTEGA Y GASSET' -> 'Jose Ortega Y Gasset', pinned live
    # against v1.4 2026-07-17 and pinned end to end in
    # tests/test_capitalization.py). These tokens are what a parse of
    # the uppercase name builds.
    upper = _pn("JUAN ORTEGA Y GASSET", [
        Token("JUAN", Span(0, 4), Role.GIVEN),
        Token("ORTEGA", Span(5, 11), Role.FAMILY),
        Token("Y", Span(12, 13), Role.FAMILY),
        Token("GASSET", Span(14, 20), Role.FAMILY),
    ])
    assert upper.capitalized(force=True).family == "Ortega Y Gasset"
    # The tag decides even against the shape: a token tagged
    # conjunction lowers however it is written. Nothing shipped builds
    # this token -- that is the point, since the old predicate could
    # not have honored it.
    tagged = _pn("JUAN ORTEGA Y GASSET", [
        Token("JUAN", Span(0, 4), Role.GIVEN),
        Token("ORTEGA", Span(5, 11), Role.FAMILY),
        Token("Y", Span(12, 13), Role.FAMILY, frozenset({"conjunction"})),
        Token("GASSET", Span(14, 20), Role.FAMILY),
    ])
    assert tagged.capitalized(force=True).family == "Ortega y Gasset"
    # ... and an untagged word of the conjunction vocabulary is an
    # ordinary name word. The reachable shape is a token whose text is
    # more than one word, since the repair walks a token's words while
    # the tag is the whole token's: 'juan e-f smith' capitalized to
    # 'Juan e-F Smith' while the old predicate re-decided per word.
    hyphenated = _pn("juan e-f smith", [
        Token("juan", Span(0, 4), Role.GIVEN),
        Token("e-f", Span(5, 8), Role.MIDDLE),
        Token("smith", Span(9, 14), Role.FAMILY),
    ])
    assert hyphenated.capitalized(force=True).middle == "E-F"


def test_views_fall_back_to_the_vocabulary_for_text_never_parsed() -> None:
    """A token with no span was never classified, so there is no
    decision to honor and the views ask the vocabulary instead --
    getting the answer the parser would have given, v1's initial
    carve-out included. Both views, on one parse: `replace()` splices
    raw text into a field, and reading it two ways is what #458's
    review found.

    The two views ask it of different scopes, and that is the whole of
    the asymmetry. Case repair walks one word at a time and never sees
    the part, so it answers the per-WORD question (conjunction or
    initial?) and leaves the per-PART one (is this particle acting as
    a particle?) to fall through to particle treatment -- widening it
    there would reverse rules.md#R4's Accepted boundary, whose crossing
    is revise(), which the `de la` capitalization assertions pin.
    initials() DOES hold the part -- every token of the role is in hand
    -- so it answers both, by _types._remarked's own test with the
    vocabulary standing in for the tags a spliced token never got.
    """
    p = Parser()
    base = p.parse("john smith")

    spliced = base.replace(family="velasquez y garcia")
    assert [t.span for t in spliced.tokens[1:]] == [None, None, None]
    assert spliced.capitalized(force=True).family == "Velasquez y Garcia"
    assert spliced.initials() == "j. v. g."
    # the carve-out rides along: an assigned middle initial is an
    # initial, not the Italian conjunction, in either view
    assert base.replace(middle="e.").capitalized(force=True).middle == "E."
    assert base.replace(middle="E.").initials() == "j. E. s."
    assert base.replace(family="velasquez Y garcia").initials() == "j. v. Y. g."

    # the per-part question, which initials() can answer: a spliced
    # family with a name word in it has its particles skipped, and one
    # that is nothing but particles has them all contribute (R2/R3).
    # Each is what the facade and the parse both give.
    assert base.replace(family="de la vega").initials() == "j. v."
    assert base.replace(family="van der berg").initials() == "j. b."
    assert base.replace(family="de la").initials() == "j. d. l."
    assert p.parse("john de la").initials() == "j. d. l."
    assert base.replace(family="smith").initials() == "j. s."

    # unchanged: the boundary a spliced particle keeps in CASE REPAIR,
    # which cannot see the part
    assert base.replace(family="de la").capitalized(force=True).family == "de la"
    assert (base.replace(family="de la vega")
            .capitalized(force=True).family == "de la Vega")
    # ... and revise(), which classifies, still crosses it
    assert p.revise(base, family="de la").capitalized(force=True).family == "De La"
    assert (p.revise(base, family="velasquez y garcia")
            .capitalized(force=True).family == "Velasquez y Garcia")

    # unchanged: a token the parse DID see is decided by its tags, so
    # a hyphenated word it read as one ordinary name word stays one
    assert p.parse("juan e-f smith").capitalized(force=True).middle == "E-F"

    # A role holding both is not reachable through replace(), which
    # replaces a role whole (measured), but is constructible: each
    # token answers with its best evidence, which is what _remarked
    # would have computed had the spliced half been classified. Here
    # the parsed 'de' is particle-TAGGED and the spliced 'la' is only
    # particle vocabulary, so the part is all particles and both
    # contribute; swap in a name word and neither does.
    mixed = _pn("john de la", [
        Token("john", Span(0, 4), Role.GIVEN),
        Token("de", Span(5, 7), Role.FAMILY, frozenset({"particle"})),
        Token("la", None, Role.FAMILY),
    ])
    assert mixed.initials() == "j. d. l."
    with_name_word = _pn("john de la", [
        Token("john", Span(0, 4), Role.GIVEN),
        Token("de", Span(5, 7), Role.FAMILY, frozenset({"particle"})),
        Token("vega", None, Role.FAMILY),
    ])
    assert with_name_word.initials() == "j. v."

    # Scoped per ROLE, not per name: a role the parse classified whole
    # keeps its tags as the answer however the other roles were built.
    # The family here is all particle vocabulary and carries no mark,
    # which is the parse saying those words are doing a particle's work
    # -- a spliced middle beside it does not reopen that. Hand-built
    # because every edit path recomputes the mark (_types._remarked)
    # and would agree with the vocabulary by construction; per-NAME
    # scoping passes every other test in the suite and fails here.
    other_role_spliced = _pn("john van der", [
        Token("john", Span(0, 4), Role.GIVEN),
        Token("q", None, Role.MIDDLE),
        Token("van", Span(5, 8), Role.FAMILY, frozenset({"particle"})),
        Token("der", Span(9, 12), Role.FAMILY, frozenset({"particle"})),
    ])
    assert other_role_spliced.initials() == "j. q."


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
