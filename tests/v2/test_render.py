import dataclasses
import unicodedata
import warnings

import pytest

from nameparser import FAMILY_FIRST, HumanName, Parser, Policy, parse
from nameparser._lexicon import Lexicon
from nameparser.config import Constants
from nameparser._render import _apply_mask, _collapse, render
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


def test_a_suffix_run_survives_a_render_and_a_reparse() -> None:
    """str() of a fixed parse re-parses to the same suffix (#436).

    The instability #429 recorded and left open: its fix made
    'Smith, MD PhD' render suffix 'MD PhD', and str() of that parse
    is 'Smith MD PhD' -- a NO-COMMA string, which the no-comma path
    then read back as 'MD, PhD'. One writing round-tripped, the other
    did not, and which was which depended on a comma the render had
    already dropped. Three spellings of one run, each its own path
    into the entry rule: a lone family plus the run, the full name
    plus a comma, and the full name with no comma at all.
    """
    for text in ("Smith, MD PhD", "John Smith, MD PhD",
                 "John Smith MD PhD"):
        once = parse(text)
        assert once.suffix == "MD PhD", text
        assert parse(str(once)).suffix == once.suffix, text


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
    """rules.md#R3, settled (#461).

    This pinned TODAY's output on an open question so that settling it
    would fail the suite until the pin moved with it. It fired, and
    this is the pin moved: a connective contributes no initial where
    it is JOINING, and a part holding nothing else for it to join is a
    part where it initials like any other name word, agreeing with the
    base. The all-particle rows below are unchanged, because R2's mark
    already readmitted the word there; what moved is everything under
    the default vocabulary, where a lone connective now initials too.
    decisions.md#R3 records the rule and what it costs.

    Still not a `deviates:` marker and still not a rules.md example
    line: markers hang on example lines and every line there names an
    input parsed with the DEFAULT vocabulary, over which `particles`
    and `conjunctions` are disjoint, so no string reaches the
    all-particle-with-a-connective shape. It is also what keeps the
    values quoted in prose by decisions.md, mechanisms.md and
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

    # OUTSIDE such a part the skip stands where the connective is
    # JOINING, and these are what the readmission must not reach --
    # the question is asked of the whole PART and never of a word
    # count, which is what keeps a part of two words with a name word
    # in it on this side of the line
    assert p.parse("Juan Velasquez y Garcia").initials() == "J. V. G."
    assert parse("Jon Dough and").initials() == "J. D."
    # Under THIS lexicon 'Juan y Garcia' is one of them, and for a
    # reason worth spelling out: making 'y' a particle folds it into
    # the family, so the part is 'y Garcia' and holds a name word for
    # it to join. Unchanged, where the same string under the default
    # vocabulary moves -- which is the row below.
    assert p.parse("Juan y Garcia").initials() == "J. G."
    # and it DOES reach a part holding nothing else, under the default
    # vocabulary too, where 'y' is no particle and only the new mark
    # readmits it
    assert parse("Juan y Garcia").initials() == "J. y. G."
    assert parse("Juan de y").initials() == "J. y."
    assert parse("Juan y").initials() == "J. y."


def test_repair_keeps_a_lone_connective_lowercase_where_it_initials(
) -> None:
    """rules.md#R4's own reading, and the view split it accepts.

    A connective that initials BECAUSE it joins nothing is still not
    written the way a name is written, so case repair leaves it
    lowercase while initials() takes its letter. That is R4's reason
    rather than a borrowing from R3 -- the two rules answer different
    questions about the same token and this is the row where their
    answers part. mechanisms.md#RENDER-HONORS-THE-PARSE records the
    shape; decisions.md#R4 records the split.
    """
    assert parse("Juan de y").initials() == "J. y."
    assert parse("Juan de y").capitalized().family == "de y"
    assert parse("juan y").capitalized(force=True).given == "Juan"
    assert parse("juan y").capitalized(force=True).family == "y"


def test_repair_capitalizes_a_generation_the_connective_also_spells(
) -> None:
    """rules.md#R4's other half (#397 review), and the row that made
    the sentence need two clauses.

    A word can be the connective and the generation at once -- 'i' is
    the Catalan link and the roman numeral -- and where the parse read
    the GENERATION the token still carries the `conjunction` tag
    classify gave it. Repair reads the ROLE the parse decided, not the
    tag alone, so a suffix-roled letter is repaired as the suffix it
    was read as. Without that test these gave 'John Quincy Smith i'
    and 'Carod i', where every release through 2.3 gave the capital.

    Both surfaces, because the v1 facade repairs through this same
    helper and a fix on one of them would be a split.
    """
    assert parse("John Quincy Smith i").suffix == "i"
    assert str(parse("John Quincy Smith i").capitalized(
        force=True)) == "John Quincy Smith I"
    assert str(parse("Carod i").capitalized(force=True)) == "Carod I"
    assert str(parse("Josep Lluis Carod i III").capitalized(
        force=True)) == "Josep Lluis Carod I III"
    v1 = HumanName("John Quincy Smith i")
    v1.capitalize(force=True)
    assert str(v1) == "John Quincy Smith I"
    v1_two = HumanName("Carod i")
    v1_two.capitalize(force=True)
    assert str(v1_two) == "Carod I"
    # the contrast that keeps the role test honest: the SAME letter
    # in a NAME part is a connective and keeps its lowercase, which
    # is the answer 'y' has always had there
    assert parse("Josep i Rovira").middle == "i"
    assert str(parse("Josep i Rovira").capitalized(
        force=True)) == "Josep i Rovira"
    assert str(parse("Josep y Rovira").capitalized(
        force=True)) == "Josep y Rovira"


def test_repair_keeps_a_plain_connective_the_suffix_field_holds_lower(
) -> None:
    """rules.md#R4, the GENERATION half read narrowly (#397 second
    review). The clause turns on the generation and not on the field:
    the test is the suffix ROLE **and** the suffix VOCABULARY, and a
    role test alone capitalized every plain connective that merely
    LANDS in the suffix field.

    The third part of a comma form is the shape that puts one there
    -- assign reads those words as the suffix run whatever they are
    -- and none of them is generational vocabulary, so none of them
    was read as a generation and all of them keep the lowercase they
    have always had. Expected strings measured 2026-09-20 on the
    released 1.4.0 and 2.3.0 wheels from a throwaway environment, and
    they agree with each other and with the parent commit 46651750.

    'Smith, John, и' is the one row where the two wheels part, and
    for a reason older than this rule: Cyrillic 'и' is a 2.x
    conjunction and not a 1.4.0 one, so 1.4.0 gives 'John Smith И'
    and 2.3.0 gives 'John Smith и'. The tree follows 2.3.0, as
    _render.py's own note on that word says it must.
    """
    for text, plain, forced in (
            ("Smith, John, and", "John Smith and", "John Smith and"),
            ("Smith, John, y", "John Smith y", "John Smith y"),
            ("Smith, John, e", "John Smith e", "John Smith e"),
            ("Smith, John, und", "John Smith und", "John Smith und"),
            ("Smith, John, of", "John Smith of", "John Smith of"),
            ("Smith, John, и", "John Smith и", "John Smith и"),
            ("Doe, Jane, and Jr.", "Jane Doe and Jr.",
             "Jane Doe and Jr."),
            ("Smith, John, and III", "John Smith and III",
             "John Smith and III")):
        name = parse(text)
        assert name.suffix.split()[0] == text.split(", ")[-1].split()[0]
        assert str(name.capitalized()) == plain, text
        assert str(name.capitalized(force=True)) == forced, text
        v1 = HumanName(text)
        v1.capitalize(force=True)
        assert str(v1) == forced, text
    # A SPLICED field is the other way in, and R4's Accepted
    # paragraph is explicit about it: text nobody read gets the
    # vocabulary's answer, so a suffix set to 'de y' keeps its 'y'
    # exactly as a family set to 'de y' does. 1.4.0 and 2.3.0 both
    # give 'John Smith De, y'.
    spliced = HumanName(first="John", last="Smith", suffix="de y")
    spliced.capitalize(force=True)
    assert str(spliced) == "John Smith De, y"
    # ... and the vocabulary's answer is what a spliced 'i' gets too,
    # which is a CHANGE from the parent and the shape to know about:
    # 'i' is connective vocabulary here and was not there, so the
    # spliced field follows 'y' now where it used to follow the
    # numeral. The PARSED name is unaffected -- it has a reading, and
    # the reading is the generation (above).
    spliced_i = HumanName(first="John", last="Smith", suffix="i")
    spliced_i.capitalize(force=True)
    assert str(spliced_i) == "John Smith i"
    spliced_y = HumanName(first="John", last="Smith", suffix="y")
    spliced_y.capitalize(force=True)
    assert str(spliced_y) == "John Smith y"


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
    assert out.suffix == "PhD"                       # exceptions map, a mask
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


def test_the_gate_leaves_the_suffixes_out() -> None:
    """rules.md#R5 (#492): a credential or a generation written the
    way one is written ('III', 'PhD', 'Jr.') is no evidence about how
    the NAME was cased, so the one-case test reads every token but
    the SUFFIX-roled ones. Titles stay in -- a cased title still holds
    repair back -- and so does every name word."""
    for text, repaired in (("juan garcia III", "Juan Garcia III"),
                           ("juan garcia PhD", "Juan Garcia PhD"),
                           ("JUAN GARCIA Jr.", "Juan Garcia Jr."),
                           ("dr. juan garcia III", "Dr. Juan Garcia III"),
                           ("JUAN GARCIA iii", "Juan Garcia III"),
                           # a cased suffix that is NOT the trailing
                           # token: the gate excludes every SUFFIX-roled
                           # token, not only the last one
                           ("juan garcia PhD MD", "Juan Garcia PhD MD"),
                           ("juan garcia, PhD, MD", "Juan Garcia PhD, MD"),
                           # an untagged suffix: 'VI' reads suffix by
                           # shape (roman numeral) and carries no
                           # vocab:* tag, so a tag-driven gate would
                           # wrongly keep it in the one-case test
                           ("juan garcia VI", "Juan Garcia VI"),
                           # the gate over each comma shape: SUFFIX_COMMA,
                           # FAMILY_COMMA, and a FAMILY_COMMA plus a
                           # trailing suffix segment
                           ("juan garcia, III", "Juan Garcia III"),
                           ("garcia, juan III", "Juan Garcia III"),
                           ("GARCIA, JUAN, Jr.", "Juan Garcia Jr.")):
        assert str(parse(text).capitalized()) == repaired, text
    assert parse("juan garcia VI").tokens[-1].tags == frozenset()
    for untouched in ("Dr. juan garcia", "DR. juan garcia III",
                      "Juan garcia III", "Juan Garcia iii",
                      # NICKNAME and MAIDEN tokens stay IN the gate
                      # text -- only SUFFIX is excluded, so a cased
                      # nickname or maiden word still holds repair
                      # back (a mutant that also filtered those
                      # roles survived the whole suite otherwise)
                      "jane doe nee SMITH III", "juan garcia (Bob)"):
        name = parse(untouched)
        assert name.capitalized() == name, untouched
    # a caseless name with a MIXED-CASE suffix: the old gate counted
    # the suffix, read the whole joined text as mixed case and
    # refused; the new gate excludes it, and the non-suffix text has
    # no case at all (trivially one-case), so the name is admitted --
    # and then the suffix, written in more than one case, is kept as
    # written (2026-09-24), while one written in one case repairs
    assert str(parse("김민준 Phd").capitalized()) == "민준 김 Phd"
    assert str(parse("김민준 PHD").capitalized()) == "민준 김 PhD"
    # no non-suffix token at all -- a synthetic name only, since every
    # parse names somebody (rules.md#H4): the empty text is one-case
    only_suffixes = _pn("phd md", [
        Token("phd", Span(0, 3), Role.SUFFIX),
        Token("md", Span(4, 6), Role.SUFFIX),
    ])
    assert [t.text for t in only_suffixes.capitalized().tokens] \
        == ["PhD", "MD"]


def test_a_suffix_written_in_more_than_one_case_is_kept_as_written(
) -> None:
    """rules.md#R5 (decided 2026-09-24): the gate leaves the suffixes
    out because a cased suffix says nothing about the NAME, and read
    to its end that also means repair has no business re-spelling
    one. So where repair was not forced, a SUFFIX token written in
    more than one case is kept as written -- 'EdD' stays 'EdD' where
    the acronym clause would write 'EDD' -- while one written in a
    single case is repaired as before. Force repairs both. The cost is
    the garbled spelling kept with the deliberate one ('Iii'), pinned
    here as a boundary. Both surfaces."""
    for text, plain, forced in (
            ("john smith EdD", "John Smith EdD", "John Smith EDD"),
            ("JANE DOE, DSc", "Jane Doe DSc", "Jane Doe DSc"),
            ("juan garcia PsyD", "Juan Garcia PsyD", "Juan Garcia PsyD"),
            ("john smith B.Tech.", "John Smith B.Tech.",
             "John Smith B.TECH."),
            ("john smith, EdD, PhD", "John Smith EdD, PhD",
             "John Smith EDD, PhD"),
            # boundary: the garbled spelling is kept too
            ("juan garcia Iii", "Juan Garcia Iii", "Juan Garcia III"),
            ("john smith Mba", "John Smith Mba", "John Smith MBA"),
            # a suffix written in ONE case is repaired as any token is
            ("juan garcia III", "Juan Garcia III", "Juan Garcia III"),
            ("JUAN GARCIA iii", "Juan Garcia III", "Juan Garcia III"),
            ("john smith edd", "John Smith EDD", "John Smith EDD"),
            # unchanged by the rule: already written as repair writes
            ("juan garcia PhD", "Juan Garcia PhD", "Juan Garcia PhD"),
            ("juan garcia Jr.", "Juan Garcia Jr.", "Juan Garcia Jr.")):
        name = parse(text)
        assert str(name.capitalized()) == plain, text
        assert str(name.capitalized(force=True)) == forced, text
        hn = HumanName(text)
        hn.capitalize()
        assert str(hn) == plain, text
        hn = HumanName(text)
        hn.capitalize(force=True)
        assert str(hn) == forced, text


def test_the_gate_and_the_parser_read_a_cased_suffix_differently() -> None:
    """decisions.md#R5's split: the parser's own one-case readings
    (rules.md#P3, #S2) still count a cased suffix, while R5's gate
    leaves it out. So 'john e jones III' is MIXED to the parser, which
    reads its 'e' as a connective, and one-case to the gate, which
    repairs it -- keeping the connective lowercase -- where the one-case
    'john e jones iii' reads 'e' as an initial. The gate follows the
    parse's suffix call, the ambiguous credential class included, so
    'jack MA' (S2's lean read MA as the credential) and 'MD, PhD'
    (family MD, suffix PhD) repair on the default path too."""
    mixed = parse("john e jones III")
    one_case = parse("john e jones iii")
    assert "conjunction" in mixed.tokens[1].tags
    assert "initial" in one_case.tokens[1].tags
    for name, repaired in ((mixed, "John e Jones III"),
                           (one_case, "John E Jones III"),
                           (parse("jack MA"), "Jack MA"),
                           (parse("MD, PhD"), "Md PhD")):
        assert str(name.capitalized()) == repaired, name.original


def test_capitalized_is_idempotent() -> None:
    once = _lowercase_mac().capitalized()
    assert once.capitalized() == once
    assert once.capitalized(force=True) == once


def test_capitalized_with_explicit_lexicon() -> None:
    # empty lexicon: no particle rule, no exceptions -> plain capitalize
    out = _lowercase_mac().capitalized(Lexicon.empty())
    assert out.family == "De La MacDole-Eisenhower"
    assert out.suffix == "Phd"


def _repaired_under(pairs: tuple[tuple[str, str], ...], text: str, *,
                    force: bool = True) -> ParsedName:
    """`text` parsed and repaired under the default lexicon with its
    exceptions map replaced by `pairs`."""
    p = Parser(lexicon=dataclasses.replace(
        Lexicon.default(), capitalization_exceptions=pairs))
    return p.capitalized(p.parse(text), force=force)


def test_a_mask_recases_the_word_as_the_writer_punctuated_it() -> None:
    """rules.md#R4's mask (#459): an exceptions-map value is its key's
    letters in the case each takes, laid over the word as written --
    one entry covers every punctuation of the word, and repair adds
    and removes nothing."""
    for text, suffix in (("john smith phd", "PhD"),
                         ("john smith ph.d.", "Ph.D."),
                         ("JOHN SMITH PH.D.", "Ph.D."),
                         ("john smith bsc", "BSc"),
                         ("JOHN SMITH MSC", "MSc")):
        assert parse(text).capitalized().suffix == suffix, text
    # two tokens, and 'ph.' is no key: no mask applies, and each word
    # title-cases on its own
    assert str(parse("john smith ph. d.").capitalized()) \
        == "John Smith Ph. D."
    # the mask is asked BEFORE the acronym clause, which would give
    # 'BSC' -- bsc is a listed acronym too
    assert "bsc" in Lexicon.default().suffix_acronyms
    # forced: a mixed-case corpus name R5 would otherwise hold back
    assert str(parse("Dr. med. univ. Margit Popp, MSc").capitalized(
        force=True)) == "Dr. Med. Univ. Margit Popp MSc"
    # the mask is also asked BEFORE the numeral clause, which would
    # give 'III' -- an identity mask ('iii' stays lowercase) proves
    # the mask decided rather than merely agreeing with it
    assert _repaired_under((("iii", "iii"),), "john smith iii",
                           force=False).suffix == "iii"


def test_a_mask_applies_whatever_role_the_word_took() -> None:
    """The map stays role-free (#459): an entry is the caller saying
    how a word is written, wherever it stands. The acronym and
    numeral clauses read the role; the mask does not."""
    assert str(parse("phd smith").capitalized()) == "PhD Smith"
    assert str(parse("john phd smith").capitalized()) == "John PhD Smith"
    assert str(parse("MSc Dr. med. univ.").capitalized(force=True)) \
        == "MSc Dr. Med. Univ."


def test_a_word_that_left_the_map_repairs_by_the_role_it_took() -> None:
    """md, ii, iii and iv left the exceptions map (#459). A suffix md
    is a listed acronym and a suffix numeral a numeral, so the acronym
    and numeral clauses write them in capitals -- keeping whatever
    punctuation the writer used, which the map's substitution did
    not. A word the parse put in a NAME role is repaired as a name
    word whatever vocabulary holds it (decisions.md#R4's given-role
    half), which is also how the abbreviated Mohammed is written."""
    assert str(parse("john smith md").capitalized()) == "John Smith MD"
    assert str(parse("john smith m.d.").capitalized()) == "John Smith M.D."
    assert str(parse("john smith iii").capitalized()) == "John Smith III"
    assert str(parse("john smith iii.").capitalized()) == "John Smith III."
    assert str(parse("Andrew Perkins (M.D)").capitalized(force=True)) \
        == "Andrew Perkins M.D"
    assert str(parse("Md Abdul Karim").capitalized(force=True)) \
        == "Md Abdul Karim"
    assert parse("iv smith").given == "iv"
    assert str(parse("iv smith").capitalized()) == "Iv Smith"
    # the other name-role numeral shape: a numeral in a name role
    # repairs as the name word the parse read it as, decided
    assert str(parse("john iii smith").capitalized()) == "John Iii Smith"


def test_a_credential_read_by_its_shape_repairs_to_capitals() -> None:
    """rules.md#R4, #516's by-shape half (#459): a suffix classify
    admitted to the credential class by its dotted shape alone
    carries SHAPE_ACRONYM_TAG and no vocabulary entry, and repairs as
    a listed acronym does."""
    assert str(parse("john smith x.y.z.").capitalized()) \
        == "John Smith X.Y.Z."
    assert str(parse("John Smith R.A.I.").capitalized(force=True)) \
        == "John Smith R.A.I."
    # the same shape read as the FAMILY -- no words to spare -- is a
    # name word
    assert parse("Jack X.Y.Z.").family == "X.Y.Z."
    assert str(parse("Jack X.Y.Z.").capitalized(force=True)) \
        == "Jack X.y.z."
    # and with the dotted-shape switch off it is family by position
    off = Parser(policy=Policy(unlisted_dotted_suffixes=False))
    assert str(off.capitalized(off.parse("john smith x.y.z."))) \
        == "John Smith X.y.z."
    # the opt-in all-caps half writes the same tag
    caps = Parser(policy=Policy(unlisted_caps_suffixes=True))
    assert str(caps.capitalized(caps.parse("John Smith XYZ"),
                                force=True)) == "John Smith XYZ"
    assert str(parse("John Smith XYZ").capitalized(force=True)) \
        == "John Smith Xyz"


def test_a_suffix_numeral_repairs_to_capitals_by_its_shape() -> None:
    """rules.md#R4 (#459): vi through x carry no vocabulary tag and
    title-cased to 'Vi'/'Ix'; the numeral clause reads the roman
    shape of a SUFFIX-roled word. xi and up are no suffix to the
    parse (its roman shape stops at x), and a numeral after a family
    comma is the given name -- parse limits both, so both repair as
    the name words they were read as."""
    for text, suffix in (("john smith vi", "VI"),
                         ("john smith vii", "VII"),
                         ("john smith viii", "VIII"),
                         ("john smith ix", "IX"),
                         ("john smith x", "X"),
                         ("john smith, v", "V")):
        name = parse(text)
        assert name.suffix == text.split()[-1], text
        assert name.capitalized().suffix == suffix, text
    assert parse("john smith xi").family == "xi"
    assert str(parse("john smith xi").capitalized()) == "John Smith Xi"
    assert parse("john smith, vi").given == "vi"
    assert str(parse("john smith, vi").capitalized()) == "Vi John Smith"
    # the generation guard's other half: a generational 'i' skips the
    # connective arm, and the numeral clause is what writes it
    assert str(parse("Carod i").capitalized(force=True)) == "Carod I"
    # the clause reads no vocabulary, so an empty lexicon repairs too
    assert _pn("john smith vi", [
        Token("john", Span(0, 4), Role.GIVEN),
        Token("smith", Span(5, 10), Role.FAMILY),
        Token("vi", Span(11, 13), Role.SUFFIX),
    ]).capitalized(Lexicon.empty()).suffix == "VI"
    # the documented Unicode boundary of the case-only invariant: _ROMAN
    # matches under re.I, which admits the dotless Turkish 'ı' (casefold-
    # unequal to 'i') as a roman-numeral suffix, and the numeral clause
    # writes it in capitals same as any other
    assert "ı".casefold() != "i".casefold()
    assert parse("john smith ıv").capitalized().suffix == "IV"


def test_the_mask_keeps_every_non_letter_and_declines_a_miscount() -> None:
    assert _apply_mask("ph.d.", "PhD") == "Ph.D."
    assert _apply_mask("PHD", "PhD") == "PhD"
    assert _apply_mask("bsc", "BSc") == "BSc"
    # The lookup key is NFC-composed and the word is not: decomposed
    # hangul spells one syllable in two letters, so the counts differ
    # and the applier declines rather than guess -- and the repair
    # falls through to the next clause instead of raising.
    decomposed = unicodedata.normalize("NFD", "씨")
    assert len(decomposed) == 2
    assert _apply_mask(decomposed, "씨") is None
    assert _repaired_under((("씨", "씨"),), unicodedata.normalize(
        "NFD", "John Smith 씨")).suffix == decomposed


def test_a_split_initial_is_capitalized_only_where_the_mask_keeps_it_joined(
) -> None:
    """rules.md#R4 (#459 review, narrowed): a letter written alone
    beside a full stop is an initial ONLY where the MASK writes that
    same letter inside a run of two or more letters. Where the mask
    spells it alone too, the mask's own case stands ('h.c' on 'h.c.'
    stays 'h.c.'), and a run of two or more letters beside a full
    stop ('sc' in 'b.sc.') is never an initial."""
    for word, mask, expected in (
            ("p.h.d.", "PhD", "P.H.D."),
            ("b.sc.", "BSc", "B.Sc."),
            ("h.c.", "h.c", "h.c."),   # mask ALSO spells each letter alone
            ("y", "y", "y"),           # no full stop at all
            (".a", "a", ".a"),         # single-letter mask never overrides
            ("a.", "a", "a."),
            ("2b.", "2b", "2b."),      # 'b' has no LETTER neighbor in '2b'
            # a digit ends a run on the NEXT side too, not only the
            # previous one the row above covers
            ("b.2", "b2", "b.2"),
            ("2.b.", "2b", "2.b."),
            # the mask's own 'A' already agrees, so this row alone
            # cannot tell the override from plain masking; the two
            # all-lowercase masks after it can
            ("a.bc", "Abc", "A.bc"),
            ("a.bc", "abc", "A.bc"),   # stop after the run's first letter
            ("ab.c", "abc", "ab.C"),   # stop before the run's last letter
            # a digit ends a run: the mask's runs are {x} and {bc}, so
            # 'x' keeps its lowercase (and has no stop beside it) while
            # the split 'b' and 'c' are forced upper
            ("x2b.c", "x2bc", "x2B.C"),
            # a fullwidth stop is a full stop too -- reachable by a
            # direct call only, since _WORD splits a token at it
            ("a．bc", "abc", "A．bc"),
            ("ab．c", "abc", "ab．C"),  # fullwidth stop on the previous side
            # a TITLECASE mask letter (Ǆ, the digraph DŽ's title form)
            # reads as upper -- `not mask_chars[at].islower()` is true
            # for it same as for a plain uppercase letter -- a
            # documented limit (_apply_mask's own docstring)
            ("ǆ", "ǅ", "Ǆ"),
    ):
        assert _apply_mask(word, mask) == expected, (word, mask)
    # The override's two index guards ('i > 0' before reading
    # word[i - 1], 'i < last' before reading word[i + 1]) matter only
    # for a split letter at an actual EDGE of the word -- reachable
    # here only by calling _apply_mask directly, since through
    # _cap_text a hyphen is never handed to it: _WORD splits a token
    # at a hyphen first (and the hyphen clause in _cap_text handles
    # that text separately), so only a full stop reaches this far.
    assert _apply_mask("ab-c", "abc") == "ab-c"
    assert _apply_mask("a-bc.", "abc") == "a-bc."
    for text, suffix in (("john smith b.s.c.", "B.S.C."),
                         ("JOHN SMITH B.S.C.", "B.S.C."),
                         ("john smith m.s.c.", "M.S.C."),
                         ("john smith p.h.d.", "P.H.D.")):
        assert parse(text).capitalized().suffix == suffix, text
        hn = HumanName(text)
        hn.capitalize()
        assert hn.suffix == suffix, text
    # the boundary the rule draws: a two-letter run beside a period
    # is not lone, and still takes the mask's case
    assert parse("john smith b.sc.").capitalized().suffix == "B.Sc."
    # end to end: a caller's own mask that ALSO spells each letter
    # alone (honoris causa -- "Dr. h.c.") leaves the split-looking
    # word unchanged rather than forcing capitals nobody asked for
    assert str(_repaired_under((("h.c", "h.c"),), "dr. h.c. hans meier")) \
        == "Dr. h.c. Hans Meier"


def test_a_decomposed_mask_value_reads_the_same_split_as_composed() -> None:
    """A mask value is stored NFC-composed (#459 review): decomposed,
    'é' would be a base letter plus a non-alpha combining mark, and
    the split-off-initial rule would read the base as split off. Both
    spellings of one value must repair the split word identically."""
    composed = unicodedata.normalize("NFC", "Péx")
    decomposed = unicodedata.normalize("NFD", "Péx")
    assert decomposed != composed
    for value in (composed, decomposed):
        assert _repaired_under((("pé.x.", value),),
                               "john smith pé.x.").suffix == "Pé.X."


def test_a_masks_upper_fallback_can_lengthen_a_word_through_ss() -> None:
    """decisions.md#R4 (2026-09-24 review): where the whole-word
    upper-casing does not keep the word's length, _apply_mask falls
    back to a per-character `c.upper()`, which lengthens 'ß' to 'SS'
    as the acronym/numeral clauses' `word.upper()` does -- whether
    the letter is upper by the split-off-initial override ('a.ß') or
    by the mask's own case ('STRAẞE', with the capital ẞ). Both masks
    validate, spelling their keys' own letters; the validator's
    refusal of ('straße', 'STRASSE') is a different question."""
    assert _repaired_under((("a.ß", "aß"),),
                           "john a.ß smith").middle == "A.SS"
    assert _repaired_under((("straße", "STRAẞE"),),
                           "john straße").family == "STRASSE"


def test_a_lengthening_mask_is_not_a_fixpoint_under_a_second_forced_pass(
) -> None:
    """decisions.md#R4 (2026-09-24 review, sub-clause (a)): capitalized()'s
    own docstring claims every clause is a fixpoint, so a repaired name
    comes back unchanged if repaired again -- true everywhere except
    this one boundary. The FIRST forced pass over 'a.ß' under the
    ('a.ß', 'aß') mask gives 'A.SS' (the previous test). Forcing that
    OUTPUT through the same lexicon a second time folds it to 'a.ss',
    which is a different letter sequence from the stored key 'a.ß' --
    not merely a different case of the same one -- so the exceptions
    map lookup that found the entry on the first pass misses on the
    second, and the word falls through to plain title-casing."""
    lex = dataclasses.replace(Lexicon.default(),
                              capitalization_exceptions=(("a.ß", "aß"),))
    first = parse("john a.ß smith").capitalized(lex, force=True)
    assert first.middle == "A.SS"
    second = first.capitalized(lex, force=True)
    assert second.middle == "A.ss"
    assert second.middle != first.middle


def test_a_masks_punctuation_marks_its_joins_and_is_never_written() -> None:
    """#459 review: a value's punctuation is never written into the
    word -- under ('md', 'M.D.') 'md' repairs to 'MD' and 'm.d.' to
    'M.D.', as under a plain 'MD' -- but it is not IGNORED: it marks
    which of the mask's letters are one run, and the split-off-initial
    rule reads that. So 'h.c' and 'hc', differing ONLY in punctuation,
    repair the writer's 'h.c.' differently."""
    with warnings.catch_warnings():
        warnings.simplefilter("error")
        lex = dataclasses.replace(
            Lexicon.default(),
            capitalization_exceptions=(("md", "M.D."),))
    p = Parser(lexicon=lex)
    assert str(p.capitalized(p.parse("john smith md"))) == "John Smith MD"
    assert str(p.capitalized(p.parse("john smith m.d."))) \
        == "John Smith M.D."
    # the facade twin: warning-free at the first parse, where the
    # shim's lazily built Lexicon snapshot is the one place a
    # construction diagnostic could be raised
    c = Constants(capitalization_exceptions={'md': 'M.D.'})
    with warnings.catch_warnings():
        warnings.simplefilter("error")
        hn = HumanName("john smith md", constants=c)
    hn.capitalize()
    assert str(hn) == "John Smith MD"
    with warnings.catch_warnings():
        warnings.simplefilter("error")
        joined = dataclasses.replace(
            Lexicon.default(), capitalization_exceptions=(("hc", "h.c"),))
        split = dataclasses.replace(
            Lexicon.default(), capitalization_exceptions=(("hc", "hc"),))
    pj, ps = Parser(lexicon=joined), Parser(lexicon=split)
    assert str(pj.capitalized(pj.parse("dr. h.c. hans meier"),
                              force=True)) == "Dr. h.c. Hans Meier"
    assert str(ps.capitalized(ps.parse("dr. h.c. hans meier"),
                              force=True)) == "Dr. H.C. Hans Meier"


def test_a_mask_recases_a_digit_key_unchanged() -> None:
    """#459 review: the mask walks ALPHANUMERICS, so a digit is carried
    through (it has no case) while the letters take the mask's case.
    A synthetic GIVEN-roled token keeps the row off the role-gated
    acronym/numeral clauses and off how '2nd' happens to parse."""
    lex = dataclasses.replace(Lexicon.default(),
                              capitalization_exceptions=(("2nd", "2ND"),))
    assert _pn("2nd", [
        Token("2nd", Span(0, 3), Role.GIVEN),
    ]).capitalized(lex, force=True).given == "2ND"


def test_a_mask_cases_through_the_whole_word_for_context_sensitive_letters(
) -> None:
    """#459 review: casing goes through word.lower()/word.upper() when
    both keep the word's length, since a per-character call is
    context-free and writes a Greek medial sigma where a FINAL one
    belongs."""
    assert _apply_mask("ΚΟΣ", "Κος") == "Κος"  # final sigma
    # the per-character fallback: 'straße'.upper() is 'STRASSE',
    # longer than the word, and there ß keeps its own lowercase under
    # the mask's lowercase letter
    assert _apply_mask("straße", "STRAßE") == "STRAßE"
    # same fallback (the word's own upper/lower length still
    # disagrees regardless of the mask's case), with a LOWERCASE mask
    # this time: the per-character path lowers every letter,
    # including ß's own, to 'straße'
    assert _apply_mask("STRAßE", "straße") == "straße"
    # `same_length` chains three lengths (lowered, uppered, word); the
    # ß rows above both fail it through the UPPERED side ('ß' grows
    # under .upper()). This row fails it through the LOWERED side
    # instead -- 'İ' (capital dotted I) grows under .lower() to 'i̇'
    # (dotless i + combining dot above) -- and the last row fails it
    # through BOTH at once, mixing ß and İ in one word.
    assert _apply_mask("İx", "ix") == "İx".lower()
    assert _apply_mask("ßİ", "ßi") == "".join(c.lower() for c in "ßİ")
    # end to end, through a custom Lexicon: a per-character
    # c.lower()/c.upper() walk gave 'Κοσ' here (medial sigma), wrong
    lex = dataclasses.replace(Lexicon.default(),
                              capitalization_exceptions=(("κος", "Κος"),))
    assert _pn("ΚΟΣ", [
        Token("ΚΟΣ", Span(0, 3), Role.GIVEN),
    ]).capitalized(lex, force=True).given == "Κος"


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


def test_a_link_inside_a_hyphenated_word_keeps_its_lowercase() -> None:
    """rules.md#R4 (#478): inside one hyphenated word, a part that is
    connective vocabulary with a worded part on each side of it keeps
    its lowercase, in every role. At either END it is ordinary name
    text -- #458's answer, kept -- and a word outside the connective
    vocabulary is never reached, the Maori 'a' among them. A single
    letter marked with a period is an initial there too, never the
    connective -- a multi-letter word marked with a period is not."""
    for text, repaired in (
            ("jose ortega-y-gasset", "Jose Ortega-y-Gasset"),
            ("JOSE ORTEGA-Y-GASSET", "Jose Ortega-y-Gasset"),
            ("maria silva-e-sousa", "Maria Silva-e-Sousa"),
            ("mary-e-smith", "Mary-e-Smith"),
            ("john smith-and-jones", "John Smith-and-Jones"),
            # edges
            ("juan e-f smith", "Juan E-F Smith"),
            ("juan y-garcia", "Juan Y-Garcia"),
            ("jose ortega-y-", "Jose Ortega-Y-"),
            ("jose -y-gasset", "Jose -Y-Gasset"),
            # no connective, and the particle arm's own per-word answer
            ("donovan mcnabb-smith", "Donovan McNabb-Smith"),
            ("maria da-silva", "Maria da-Silva"),
            # three worded parts on the ambiguous side of `first < at
            # < last`, so a mutant dropping that bound cannot pass
            ("juan y-garcia-lopez", "Juan Y-Garcia-Lopez"),
            ("juan garcia-lopez-y", "Juan Garcia-Lopez-Y"),
            # non-link parts inside a THREE-part hyphenated token still
            # get the full per-word repair -- the particle arm
            # ("de"/"la") and the Mac rule ("mcnabb") each apply per
            # part, not only to a two-part compound
            ("juan garcia-de-la-vega", "Juan Garcia-de-la-Vega"),
            ("donovan mcnabb-y-smith", "Donovan McNabb-y-Smith"),
            # a leading EMPTY part shifts which named index is "first":
            # 'y' sits at the edge of the NAMED parts (index 0 of
            # ['y', 'garcia', 'lopez']) though it is not part 0 of the
            # split, so it stays ordinary name text -- a mutant using
            # the raw part index (0 < at < len(parts)-1) instead of the
            # named-relative bound would wrongly read it as interior
            # and lower it
            ("jose -y-garcia-lopez", "Jose -Y-Garcia-Lopez"),
            ("jose garcia-lopez-y-", "Jose Garcia-Lopez-Y-"),
            # a part holding only punctuation ('.') is not a worded
            # neighbour -- the split is ['.', 'y', 'garcia'], so 'y'
            # has only ONE worded neighbour and stays ordinary name
            # text rather than reading as the connective
            ("jose .-y-garcia", "Jose .-Y-Garcia")):
        assert str(parse(text).capitalized()) == repaired, text
    # mixed case is R5's: untouched unless forced
    mixed = parse("Jose Ortega-Y-Gasset")
    assert mixed.capitalized() == mixed
    assert str(mixed.capitalized(force=True)) == "Jose Ortega-y-Gasset"
    # not connective vocabulary, so not reached (decisions.md#R4)
    assert "a" not in Lexicon.default().conjunctions
    assert str(parse("Te Awanui-a-Rangi Black").capitalized(
        force=True)) == "Te Awanui-A-Rangi Black"
    # a single letter marked with a period is an initial there,
    # exactly as in spaced text, never the connective -- `_normalize`
    # strips the period, so a naive vocabulary check alone would read
    # 'e.'/'y.' as the connective and lower it
    assert str(parse("j.-e.-p. dupont").capitalized(
        force=True)) == "J.-E.-P. Dupont"
    assert str(parse("J.-Y.-M. COUSTEAU").capitalized()) == \
        "J.-Y.-M. Cousteau"
    # a MULTI-letter word marked with a period is not an initial, and
    # stays reachable as the connective, the same as its spaced
    # reading ('hans smith und. jones' tags 'und.' a conjunction)
    assert str(parse("hans smith-und.-jones").capitalized(
        force=True)) == "Hans Smith-und.-Jones"
    # every role, not only FAMILY above
    assert str(parse("smith, jose ortega-y-gasset").capitalized(
        force=True)) == "Jose Ortega-y-Gasset Smith"


def test_the_hyphen_is_the_writers_join_even_in_a_one_case_name() -> None:
    """rules.md#R4's hyphen clause against rules.md#P3's one-case fork,
    a split DECIDED 2026-09-24 (decisions.md#R4): spaced, a marked
    letter in a name written in one case reads as an initial and
    repairs to a capital; hyphenated, the writer joined the surname on
    purpose, so the interior word is the connective whatever case the
    name is in. The cost is a one-case name whose hyphenated bare
    initials spell a connective -- 'J-E-P DUPONT' repairs to
    'J-e-P Dupont', where 1.4.0 and the parent gave 'J-E-P'. And
    conjunctions_ambiguous, P3's knob, does not reach a hyphenated
    word: marking 'y' moves the spaced spelling only."""
    for text, repaired in (("J-E-P DUPONT", "J-e-P Dupont"),
                           ("JOHN A-Y-B SMITH", "John A-y-B Smith"),
                           ("maria silva-e-sousa", "Maria Silva-e-Sousa"),
                           ("maria silva e sousa", "Maria Silva E Sousa")):
        assert str(parse(text).capitalized()) == repaired, text
        hn = HumanName(text)
        hn.capitalize()
        assert str(hn) == repaired, text
    marked = Parser(lexicon=Lexicon.default().add(
        conjunctions_ambiguous={"y"}))
    for text, default, under_mark in (
            ("JOSE ORTEGA Y GASSET", "Jose Ortega y Gasset",
             "Jose Ortega Y Gasset"),
            ("JOSE ORTEGA-Y-GASSET", "Jose Ortega-y-Gasset",
             "Jose Ortega-y-Gasset")):
        assert str(parse(text).capitalized()) == default, text
        assert str(marked.capitalized(marked.parse(text))) == under_mark, \
            text


def test_a_shipped_mask_spells_its_suffix_in_either_single_case() -> None:
    """#459 (decisions.md#R4, 2026-09-24): the PROPERTY every shipped
    mask pair serves, derived from the pairs rather than restating
    them -- `john smith <key>` puts the key in the suffix role, and
    repair spells it as the mask whether it was written all lower or
    all upper, where the acronym clause alone would write it in
    capitals. Both surfaces."""
    pairs = tuple(Lexicon.default().capitalization_exceptions)
    assert pairs  # an empty map would make the loop vacuous
    for key, mask in pairs:
        for text in (f"john smith {key}", f"JOHN SMITH {key.upper()}"):
            name = parse(text)
            assert name.suffix.lower() == key, text
            assert name.capitalized().suffix == mask, text
            hn = HumanName(text)
            hn.capitalize()
            assert hn.suffix == mask, text


def test_a_listed_acronym_that_is_a_name_word_gets_no_mask() -> None:
    """decisions.md#R4's Excluded block for CAPITALIZATION_EXCEPTIONS
    (meng, edd, lac, ded): a mask applies in every role, so an acronym
    that is also a name word must not carry one. The fork it protects:
    in a NAME role the word repairs as a title-cased name word, and in
    the suffix role, with no mask, the acronym clause writes it in
    capitals. The recorded negative control is the mask added back,
    which re-spells the person."""
    for text, repaired in (("MENG LI", "Meng Li"),
                           ("edd smith", "Edd Smith"),
                           ("john smith meng", "John Smith MENG"),
                           ("john smith edd", "John Smith EDD")):
        assert str(parse(text).capitalized()) == repaired, text
        hn = HumanName(text)
        hn.capitalize()
        assert str(hn) == repaired, text
    default = Lexicon.default()
    masked = Parser(lexicon=dataclasses.replace(
        default, capitalization_exceptions=tuple(
            default.capitalization_exceptions)
        + (("meng", "MEng"), ("edd", "EdD"))))
    for text, respelled in (("MENG LI", "MEng Li"),
                            ("edd smith", "EdD Smith")):
        assert str(masked.capitalized(masked.parse(text))) == respelled


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


def test_capitalized_one_case_connective_that_reads_as_an_initial() -> None:
    """#383/#479, the half no differential gate can see (decisions.md#R4).

    Repair lowercases a CONJUNCTION even inside a part it otherwise
    capitalizes (rules.md#R4's carve-out). Once a marked single letter
    in a one-case name is read as an INITIAL instead, that carve-out no
    longer reaches it and the letter capitalizes like any name word.
    The 'y' line is the control: it stays the connective, so it stays
    lowercase, and the two together show the carve-out itself is
    untouched.
    """
    assert str(parse("john e jones").capitalized()) == "John E Jones"
    assert str(parse("john e smith").capitalized()) == "John E Smith"
    assert str(parse("juan garcia y lopez").capitalized()) \
        == "Juan Garcia y Lopez"
    # R5's gate: mixed-case input is the writer's choice and repair
    # defers to it, so this one is not repaired at all
    assert str(parse("John e Smith").capitalized()) == "John e Smith"


def test_facade_initials_follow_the_one_case_fork() -> None:
    """Both surfaces read the same letter the same way (#528).

    The core's initials() follows the parse's tags: in a name written
    wholly in one case an 'e' is an INITIAL and a 'y' is the connective
    (rules.md#P3), so R3's "each given, middle, and base family word"
    reaches the first and not the second. Until #528 HumanName.initials()
    re-derived that from the lexicon and the part's raw shape instead,
    and kept 1.4.0's answer on both letters; it now reads the same tags,
    so the two views of one parse agree. decisions.md#R3 records it.
    """
    assert parse("john e smith").initials() == "j. e. s."
    assert HumanName("john e smith").initials() == "j. e. s."
    # #461 moved the VALUE and not the agreement: 'Y' holds the middle
    # part alone, so it initials on both surfaces -- which is also
    # 1.4.0's answer on this name, restored. The joined control below
    # is where the letter still drops, on both surfaces.
    assert parse("JUAN Y GARCIA").initials() == "J. Y. G."
    assert HumanName("JUAN Y GARCIA").initials() == "J. Y. G."
    assert parse("JUAN GARCIA Y LOPEZ").initials() == "J. G. L."
    assert HumanName("JUAN GARCIA Y LOPEZ").initials() == "J. G. L."
    # The mixed-case controls, where the writing decides the letter and
    # nothing moved on either surface
    assert HumanName("John E Smith").initials() == "J. E. S."
    assert HumanName("Juan Y. Garcia").initials() == "J. Y. G."
    # 'maria y lopez' is a ONE-CASE control, not a mixed-case one: written
    # wholly in lowercase, its 'y' is outside the marked set (rules.md#P3),
    # so it stays the CONNECTIVE on both surfaces rather than reading as
    # an initial the way 'e' does (tests/v2/test_ledger_guards.py's
    # "one-case controls" wording, around line 1118). What it no longer
    # witnesses is the DROP: #461 gave the letter its initial back here,
    # because it holds the middle part alone and so joins nothing
    # (decisions.md#R3). The joining one-case control below is where
    # a lowercase 'y' still drops, which is what keeps this row's point
    # -- the tag, not the value -- observable.
    assert HumanName("maria y lopez").initials() == "m. y. l."
    assert parse("maria y lopez").initials() == "m. y. l."
    assert HumanName("juan garcia y lopez").initials() == "j. g. l."
    assert parse("juan garcia y lopez").initials() == "j. g. l."
    # The GIVEN group, where #461 dropped the facade's own blanket
    # exemption as well as the core's: a connective among given names
    # is joining there like anywhere else, so it contributes nothing
    # on BOTH surfaces. Without the facade half these read 'J. a. J.
    # S.' and 'D. o. E.' while the core reads them as below, which is
    # the disagreement the one rule exists to prevent.
    assert parse("John and Jane Smith").initials() == "J. J. S."
    assert HumanName("John and Jane Smith").initials() == "J. J. S."
    assert parse("Duke of Edinburgh").initials() == "D. E."
    assert HumanName("Duke of Edinburgh").initials() == "D. E."
    assert parse("John & Jane").initials() == "J. J."
    assert HumanName("John & Jane").initials() == "J. J."
    # The one corpus name where the two views still differ, and it is
    # not this rule's: the facade merges 'Ph.' + 'D.' into one list
    # element and renders it with no inner delimiter
    # (fix(initials-per-word) the Ph. D. merge, decisions.md#phd-merge)
    assert HumanName("Ph. D., John").initials() == "J. P D."
    assert parse("Ph. D., John").initials() == "J. P. D."


def test_initials_separator_is_honored_on_the_live_token_path() -> None:
    # tests/test_initials.py's two "Van Berg" separator tests call
    # _process_initial("Van Berg", firstname=True) directly -- v1's
    # string path, with tokens=None -- which #528 kept working but no
    # longer the path HumanName.initials() itself takes. This pins
    # initials_separator on the live TOKEN path (tokens= passed by
    # _initials_lists), so a regression that reads initials_separator
    # only on the string branch would pass those two tests and fail
    # here. Measured.
    assert HumanName("Ph. D., John", initials_separator="-").initials() \
        == "J. P-D."
    assert HumanName("Ph. D., John", initials_separator="").initials() \
        == "J. PD."
    assert HumanName("Ph. D., John", initials_separator="") \
        .initials_list() == ["J", "PD"]
