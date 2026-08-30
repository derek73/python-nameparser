import pytest

from nameparser import FAMILY_FIRST, HumanName, Parser, Policy, parse
from nameparser._lexicon import Lexicon
from nameparser._render import _collapse, render
from nameparser._types import (FOLDED_TAG, UNCLASSIFIED_TAG, UNJOINED_TAG,
                               Ambiguity, AmbiguityKind, ParsedName, Role,
                               Span, Token)


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


def test_repair_keeps_a_conjunction_lowercase_in_a_particle_part() -> None:
    """rules.md#R4's conjunction carve-out, which no shipped name reaches.

    The unjoined mark makes the words of an all-particle part
    ordinary name words, since none of them is acting as a particle
    there -- but repair's conjunction conjunct is deliberately UNGATED
    on that mark, R4 keeping a conjunction lowercase "even inside such
    a part". Witnessing it needs a word in `particles` AND
    `conjunctions`; the shipped sets are disjoint, in the default
    vocabulary and in every locale pack, so no input string can
    witness it and rules.md can carry no example line for it. Gating
    the conjunct on the mark passed the entire suite until this test
    existed.

    Only the FORCED call gets here: R5's gate returns a mixed-case
    name before any of this is consulted.
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
    assert van.capitalized(lex, force=True).family == "y Van"


def test_initials_readmits_a_conjunction_in_a_particle_part() -> None:
    """Today's answer on an OPEN question (#461), pinned as such.

    rules.md#R3 says a conjunction never initials "even then" -- even
    inside the all-particle part R2 turns into ordinary name words --
    and `initials()` does not do that: the mark readmits the part's
    words whichever skip tag they carry. #461 made the code match the
    clause and was backed out, the clause rather than the code being
    what is now in question (decisions.md, under R2).

    So this pins what a `deviates:` marker would pin if one could
    hang here -- TODAY's output, strictly, so that settling #461
    fails the suite until this moves with it. It cannot be a marker:
    markers hang on rules.md example lines and every line there names
    an input string parsed with the DEFAULT vocabulary, over which
    `particles` and `conjunctions` are disjoint and no string reaches
    this shape. It is also what keeps the values quoted in prose by
    decisions.md, mechanisms.md#RENDER-HONORS-THE-PARSE and
    `_render.py` from going stale unnoticed.
    """
    assert "y" in Lexicon.default().conjunctions, (
        "'y' left the default conjunctions; this test builds the "
        "particle/conjunction overlap it needs from the other side and "
        "no longer has one. Pick another shipped conjunction.")
    p = Parser(lexicon=Lexicon.default().add(particles={"y"}))

    # the part the mark has turned into name words: every word of it
    # initials, the conjunction included, and the base agrees
    de_y = p.parse("Juan de y")
    assert de_y.family_base == "de y"
    assert de_y.initials() == "J. d. y."
    assert p.parse("Anh y Van").initials() == "A. y. V."
    assert p.parse("johnny y").initials() == "j. y."

    # and OUTSIDE such a part the skip stands, joining or not --
    # these are what the readmission must not reach
    assert p.parse("Juan Velasquez y Garcia").initials() == "J. V. G."
    assert p.parse("Juan y Garcia").initials() == "J. G."
    # including under the default vocabulary, where 'y' is no particle
    # and the family is therefore not all-particle
    assert parse("Juan de y").initials() == "J."


def test_initials_order_folded_words_first_like_the_family_field() -> None:
    """#408: the view and the field must read one parse the same way.

    O3's fold and P6's attachment both tag rather than move (spans
    cannot reorder), and the family field reads that tag. `initials()`
    walked tokens in written order and did not, so the two views
    disagreed about the same parse -- 'der, y van' gave family
    'van der' and initials 'y. d. v.'
    (mechanisms.md#RENDER-HONORS-THE-PARSE names #408 as that shape).

    Each assertion pairs the field with the view deliberately: a
    regression that reordered BOTH would still be caught by the
    literal, and one that reordered neither by the pairing.
    """
    # P6's attachment, the one CORPUS name the default policy moves
    # -- constructed ones move too (`de la, y van`, `der, e van`),
    # so the count is the corpus's reach and not the rule's
    van_der = parse("der, y van")
    assert van_der.family == "van der"
    assert van_der.initials() == "y. v. d."
    # and the facade, which reached this answer by its own route
    # (its *_list views prepend the carriers) -- so the core view was
    # the one out of step
    assert HumanName("der, y van").initials() == "y. v. d."

    # O3's fold, which is where the reach is (71 of the corpus's 1094
    # names move under this policy at the default order, measured
    # 2026-08-30)
    maf = Parser(policy=Policy(middle_as_family=True))
    hassan = maf.parse("Hassan, Mohamad Ahmad Ali")
    assert hassan.family == "Ahmad Ali Hassan"
    assert hassan.initials() == "M. A. A. H."
    # The folded RUN needs two elements too, and distinguishable
    # ones: hassan's run is `Ahmad Ali`, which both initial to
    # `A.`, so reversing the folded half alone passes every test
    # above. Same arity trap as the fixture drafts, one level
    # down -- the partition BUILDS a group, and that group needs
    # the treatment too (mechanisms.md#TWO-ELEMENT-GROUPS).
    doe2 = maf.parse("Doe, John A. Kenneth")
    assert doe2.family == "A. Kenneth Doe"
    assert doe2.initials() == "J. A. K. D."

    doe = maf.parse("Doe, Dr. John A.")
    assert doe.family == "A. Doe"
    assert doe.initials() == "J. A. D."

    # under a non-default order too: the fold is not order-specific
    ff = Parser(policy=Policy(name_order=FAMILY_FIRST,
                              middle_as_family=True))
    vega = ff.parse("Smith Juan Vega")
    assert vega.family == "Vega Smith"
    assert vega.initials() == "J. V. S."


def test_folded_tag_lands_only_on_family_today() -> None:
    """The guard under the per-role claim three prose sites make.

    `_render.initials`, its sibling test and mechanics.md#FOLDED_TAG all
    say the pipeline puts the tag on FAMILY tokens alone, which is why
    the GIVEN and MIDDLE arms of the partition are uniformity rather
    than reachable behavior. That claim was true and tested nowhere: a
    rule that ever folded into another part would falsify all three
    silently, and turn `initials()`'s "would otherwise reopen #408
    there" from a hypothetical into a live gap with nothing to fail.
    """
    from .cases import CASES
    seen = 0
    for policy in (Policy(), Policy(middle_as_family=True)):
        p = Parser(policy=policy)
        for case in CASES:
            if case.locale is not None:
                continue
            for tok in p.parse(case.text).tokens:
                if FOLDED_TAG in tok.tags:
                    seen += 1
                    assert tok.role is Role.FAMILY, (
                        f"{case.text!r}: {tok.text!r} carries FOLDED_TAG in "
                        f"{tok.role}. Both producers re-role to FAMILY today; "
                        f"if that changed on purpose, the per-role claims in "
                        f"_render.initials, its sibling test and "
                        f"mechanisms.md#FOLDED_TAG all move with it")
    assert seen, "no case row exercises the fold; this guard is inert"


def test_initials_folds_in_every_role_it_renders() -> None:
    """The partition is applied per role, exactly as _text_for applies
    it -- not scoped to FAMILY, where the pipeline's two producers put
    the tag today.

    Both producers (O3's fold, P6's attachment) re-role to FAMILY, so
    no input string reaches this and it is pinned from a hand-built
    name instead. Uniformity with the mechanism is the point: a
    producer that ever folded into another part would otherwise
    reopen #408 there, silently, with nothing to fail.
    """
    pn = _pn("Ann Bea Cyd Dee Eve Fay", [
        Token("Ann", Span(0, 3), Role.GIVEN),
        Token("Bea", Span(4, 7), Role.MIDDLE),
        Token("Cyd", Span(8, 11), Role.GIVEN, frozenset({FOLDED_TAG})),
        Token("Dee", Span(12, 15), Role.MIDDLE, frozenset({FOLDED_TAG})),
        Token("Eve", Span(16, 19), Role.FAMILY),
        Token("Fay", Span(20, 23), Role.FAMILY, frozenset({FOLDED_TAG})),
    ])
    # the fields already order this way; the view now agrees. All
    # THREE roles carry two tokens, per
    # mechanisms.md#TWO-ELEMENT-GROUPS: "on a one-element group a
    # partition is the identity" and the mutation that should expose
    # it passes. Two drafts got this wrong in the same way one role
    # apart, the first carrying both misses: it gave MIDDLE one token,
    # and skipping the
    # partition for MIDDLE alone passed the whole suite; the second
    # gave FAMILY none, so skipping it for FAMILY passed THIS test
    # and was caught only by its siblings and by R3's example line. A group with zero elements
    # is the identity too, and reads even less like a gap.
    assert pn.given == "Cyd Ann"
    assert pn.initials("{given}") == "C. A."
    assert pn.middle == "Dee Bea"
    assert pn.initials("{middle}") == "D. B."
    assert pn.family == "Fay Eve"
    assert pn.initials("{family}") == "F. E."


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


def test_case_repair_falls_back_for_text_the_parse_never_read() -> None:
    """A token carrying UNCLASSIFIED_TAG holds raw text no parse read,
    so there is no decision to honor and case repair -- which is handed
    a lexicon -- asks the vocabulary instead, getting the answer the
    parser would have given, v1's initial carve-out included.

    ONE view falls back. `initials()` takes no lexicon, so it has none
    to ask; the sibling test below pins what that costs.
    """
    p = Parser()
    base = p.parse("john smith")

    spliced = base.replace(family="velasquez y garcia")
    assert all(UNCLASSIFIED_TAG in t.tags for t in spliced.tokens[1:])
    assert spliced.capitalized(force=True).family == "Velasquez y Garcia"
    # the carve-out rides along: an assigned middle initial is an
    # initial, not the Italian conjunction
    assert base.replace(middle="e.").capitalized(force=True).middle == "E."

    # the per-part particle question is NOT asked: re-deriving it needs
    # a reading on every word of the part and these words have none, so
    # it falls through to plain particle treatment
    assert base.replace(family="de la").capitalized(force=True).family == "de la"
    assert (base.replace(family="de la vega")
            .capitalized(force=True).family == "de la Vega")
    # ... and revise(), which classifies, crosses it
    assert p.revise(base, family="de la").capitalized(force=True).family == "De La"
    assert (p.revise(base, family="velasquez y garcia")
            .capitalized(force=True).family == "Velasquez y Garcia")

    # a token the parse DID see is decided by its tags, so a hyphenated
    # word it read as one ordinary name word stays one
    assert p.parse("juan e-f smith").capitalized(force=True).middle == "E-F"


def test_the_mark_and_not_the_span_says_a_token_was_never_read() -> None:
    """`span is None` means SYNTHETIC, which is a wider set than
    unclassified, and keying the fallback on it was a measured
    regression (#463 review).

    `Parser.revise()` builds span-less tokens too, from a full
    sub-parse whose tags it keeps on purpose, and its docstring
    promises the tag-driven views "behave as if the text had been
    parsed". Under the span discriminator the fallback overrode exactly
    those tags: `revise(middle='e-f')` repaired to 'e-F' where the same
    words parsed gave 'E-F'. A HAND-BUILT span-less token is not marked
    either, so it takes the tag path like every other token in the
    library -- tag-driven semantics, not span-driven.
    """
    p = Parser()
    base = p.parse("john smith")

    revised = p.revise(base, middle="e-f")
    assert [t.span for t in revised.tokens if t.role is Role.MIDDLE] == [None]
    assert UNCLASSIFIED_TAG not in revised.tokens_for(Role.MIDDLE)[0].tags
    # both sides of the pair the span discriminator split
    assert p.parse("john e-f smith").capitalized(force=True).middle == "E-F"
    assert revised.capitalized(force=True).middle == "E-F"

    # the initials half of the same regression, which needs a lexicon
    # holding no particles at all to witness -- under the default one
    # 'de la vega' is particle vocabulary and the parse skips it too.
    # segment_scripts off because a from-scratch Lexicon covers no
    # script the default policy activates, and the warning is an error
    # under this suite's filters.
    empty = Parser(lexicon=Lexicon(),
                   policy=Policy(segment_scripts=frozenset()))
    assert (empty.parse("john de la vega").initials()
            == empty.revise(empty.parse("john smith"),
                            family="de la vega").initials()
            == "j. d. l. v.")

    # hand-built, span-less, untagged: classified by default
    handbuilt = _pn("john de la vega", [
        Token("john", None, Role.GIVEN),
        Token("de", None, Role.FAMILY),
        Token("la", None, Role.FAMILY),
        Token("vega", None, Role.FAMILY),
    ])
    assert handbuilt.initials() == "j. d. l. v."
    assert handbuilt.capitalized(force=True).family == "de la Vega"
    # ... and the same tokens MARKED take the fallback, which is the
    # only thing that moves them
    marked = _pn("john de la vega", [
        Token("john", None, Role.GIVEN),
        Token("de", None, Role.FAMILY),
        Token("la", None, Role.FAMILY),
        Token("y", None, Role.FAMILY, frozenset({UNCLASSIFIED_TAG})),
        Token("vega", None, Role.FAMILY),
    ])
    assert marked.capitalized(force=True).family == "de la y Vega"


def test_initials_has_no_lexicon_so_a_spliced_field_is_all_name_words()\
        -> None:
    """The accepted cost of `initials()` taking no lexicon: a field
    spliced in as raw text has no reading, and this view has nothing to
    read one from, so every word of it initials.

    That disagrees with the facade and with the same name parsed, and
    it is a 2.0-core defect rather than a decision -- see #464, filed
    for giving `Parser` an `initials` crossing. A fallback to
    `Lexicon.default()` was written and dropped: it guesses a
    vocabulary, and under a caller's own the guess erases a whole
    field (`Lexicon.default().add(particles={'y'})`, family 'de y').
    """
    p = Parser()
    base = p.parse("john smith")

    assert base.replace(family="de la vega").initials() == "j. d. l. v."
    assert p.parse("john de la vega").initials() == "j. v."
    assert HumanName("john de la vega").initials() == "j. v."

    # the vocabulary a fallback would have had to guess, and the field
    # it erased when it guessed wrong
    y_lex = Lexicon.default().add(particles={"y"})
    py = Parser(lexicon=y_lex)
    assert py.parse("Juan de y").initials() == "J. d. y."
    assert py.parse("Juan Perez").replace(family="de y").initials() == "J. d. y."


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
