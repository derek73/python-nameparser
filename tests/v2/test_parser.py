import dataclasses
import pickle
import re
import unicodedata

import pytest

from nameparser import (
    Lexicon, Locale, Parser, Policy, PolicyPatch, locales, parse, parser_for,
)
from nameparser._policy import (
    FAMILY_FIRST, FAMILY_FIRST_GIVEN_LAST, PatronymicRule,
)
from nameparser._types import AmbiguityKind, Role, Segmentation


def test_parser_defaults_and_properties() -> None:
    p = Parser()
    assert p.lexicon == Lexicon.default()
    assert p.policy == Policy()


def test_parser_rejects_wrong_types_eagerly() -> None:
    with pytest.raises(TypeError, match="lexicon"):
        Parser(lexicon={"titles": set()})  # type: ignore[arg-type]
    with pytest.raises(TypeError, match="policy"):
        Parser(policy="strict")  # type: ignore[arg-type]


def test_parse_end_to_end_with_default_vocabulary() -> None:
    pn = parse("Dr. Juan de la Vega III")
    assert pn.title == "Dr."
    assert pn.given == "Juan"
    assert pn.family == "de la Vega"
    assert pn.suffix == "III"
    assert str(pn) == "Dr. Juan de la Vega III"


def test_parse_rejects_non_str_with_decode_hint() -> None:
    with pytest.raises(TypeError, match="decode"):
        parse(b"John Smith")  # type: ignore[arg-type]
    with pytest.raises(TypeError, match="str"):
        parse(None)  # type: ignore[arg-type]


def test_degenerate_inputs_are_total() -> None:
    # the quote-pair defaults table (rule N2's conventions)
    assert not parse("")
    assert not parse("   ")
    assert parse("").original == ""
    # an input with no alphanumeric character is not a name (v1 kept it)
    assert not parse(".,")
    assert not parse("- -")
    assert parse(".,").original == ".,"     # but the raw input is kept
    single = parse("John")
    assert single.given == "John"
    family_first = Parser(policy=Policy(name_order=FAMILY_FIRST))
    assert family_first.parse("Yamada").family == "Yamada"
    title_only = parse("Dr.")
    assert title_only.title == "Dr." and not title_only.given
    unbalanced = parse('Jon "Nick Smith')
    kinds = {a.kind for a in unbalanced.ambiguities}
    assert AmbiguityKind.UNBALANCED_DELIMITER in kinds
    assert '"Nick' in [t.text for t in unbalanced.tokens]  # literal


def test_parser_is_picklable_and_frozen() -> None:
    p = Parser(policy=Policy(name_order=FAMILY_FIRST))
    loaded = pickle.loads(pickle.dumps(p))
    assert loaded == p
    assert loaded.parse("Yamada Taro").family == "Yamada"
    with pytest.raises(AttributeError):
        p.policy = Policy()  # type: ignore[misc]


def test_parser_repr_composes_component_reprs() -> None:
    assert repr(Parser()) == "Parser(Lexicon(default), Policy())"
    p = Parser(policy=Policy(name_order=FAMILY_FIRST))
    assert repr(p) == "Parser(Lexicon(default), Policy(name_order=FAMILY_FIRST))"


def test_parsedname_repr_includes_ambiguities_line() -> None:
    pn = parse("Van Johnson")
    r = repr(pn)
    assert "given: 'Van'" in r
    assert "ambiguities:" in r and "particle-or-given" in r


def test_module_parse_reuses_the_default_parser() -> None:
    import nameparser._parser as parser_mod
    assert parser_mod._default_parser() is parser_mod._default_parser()


def test_parser_for_stacks_locales() -> None:
    ru = Locale(code="ru",
                lexicon=Lexicon.empty().add(titles={"г-н"}),
                policy=PolicyPatch(patronymic_rules=frozenset(
                    {PatronymicRule.EAST_SLAVIC})))
    p = parser_for(ru)
    assert PatronymicRule.EAST_SLAVIC in p.policy.patronymic_rules
    pn = p.parse("г-н Сидоров Иван Петрович")
    assert pn.title == "г-н"
    assert pn.given == "Иван"
    assert pn.family == "Сидоров"


def test_parser_for_rejects_non_locales() -> None:
    with pytest.raises(TypeError, match="Locale"):
        parser_for("ru")  # type: ignore[arg-type]


def test_parser_for_wraps_pack_errors_with_identity() -> None:
    # PolicyPatch validates lazily (by design), so an invalid value sits
    # latent in a perfectly constructible Locale until apply time
    bad = Locale(code="xx", lexicon=Lexicon.empty(),
                 policy=PolicyPatch(name_order=(1, 2, 3)))  # type: ignore[arg-type]
    # the rewrap preserves the taxonomy's exception type (here the
    # non-Role element TypeError) while adding the pack identity
    with pytest.raises(TypeError, match="while applying locale 'xx'"):
        parser_for(bad)


def test_parser_for_warns_on_scalar_conflict() -> None:
    a = Locale(code="aa", lexicon=Lexicon.empty(),
               policy=PolicyPatch(strip_emoji=False))
    b = Locale(code="bb", lexicon=Lexicon.empty(),
               policy=PolicyPatch(strip_emoji=True))
    with pytest.warns(UserWarning, match="strip_emoji"):
        p = parser_for(a, b)
    assert p.policy.strip_emoji is True  # later wins


def test_matches_component_wise_case_insensitive() -> None:
    pn = parse("John Smith")
    assert pn.matches("JOHN SMITH")
    assert pn.matches(parse("john smith"))
    assert not pn.matches("John Smythe")
    with pytest.raises(TypeError, match="str or ParsedName"):
        pn.matches(42)  # type: ignore[arg-type]


def test_family_first_given_last_places_middle_between() -> None:
    # T1: the three-piece FAMILY_FIRST_GIVEN_LAST assignment -- family
    # from the front, given from the END, middle between (not a rotation
    # of FAMILY_FIRST)
    p = Parser(policy=Policy(name_order=FAMILY_FIRST_GIVEN_LAST))
    pn = p.parse("Zeng Xiao Long")
    assert (pn.family, pn.middle, pn.given) == ("Zeng", "Xiao", "Long")


def test_ambiguous_particle_middle_defeats_both_family_first_orders() -> None:
    # the vocabulary layer joins the ambiguous particle "van" forward
    # before the positional layer runs, so a name whose middle word
    # collides with it parses identically under either family-first
    # order -- the caution in customize.rst rests on this
    for order in (FAMILY_FIRST, FAMILY_FIRST_GIVEN_LAST):
        pn = Parser(policy=Policy(name_order=order)).parse("Nguyen Van Minh")
        assert (pn.family, pn.middle, pn.given) == ("Nguyen", "", "Van Minh")


def test_multiple_unbalanced_delimiters_each_reported() -> None:
    # T4: the extract scan continues past the first unmatched opener;
    # each one is reported and treated as literal text
    pn = parse('John "Jack (Smith')
    unbalanced = [a for a in pn.ambiguities
                  if a.kind is AmbiguityKind.UNBALANCED_DELIMITER]
    assert len(unbalanced) == 2
    assert pn.given == "John" and pn.family == "(Smith"
    assert not pn.nickname


def test_matches_accepts_explicit_parser() -> None:
    family_first = Parser(policy=Policy(name_order=FAMILY_FIRST))
    pn = family_first.parse("Yamada Taro")
    assert pn.matches("Yamada Taro", parser=family_first)
    assert not pn.matches("Yamada Taro")  # default parser reads given-first


def test_phd_split_heals_in_the_suffix_view() -> None:
    # v1 parity via fix_phd: the split credential renders as one suffix
    assert parse("John Ph. D.").suffix == "Ph. D."
    assert parse("John Smith PhD MD").suffix == "PhD, MD"  # unchanged


def test_phd_split_mid_name_is_a_suffix() -> None:
    # v1 parity: fix_phd extracted the credential BEFORE parsing, so
    # position never mattered; the merged piece is a suffix anywhere
    pn = parse("Dr. John Ph. D. Smith")
    assert pn.suffix == "Ph. D."
    assert pn.family == "Smith"
    assert pn.middle == ""


def test_ambiguous_acronym_reports_the_reading_it_took() -> None:
    # 'ma' is both a post-nominal and a surname, so whichever way the
    # peel resolves it is a guess -- the same shape as the leading
    # ambiguous particle that already reports PARTICLE_OR_GIVEN
    took_suffix = parse("John Smith MA")
    assert took_suffix.suffix == "MA"
    assert [a.kind for a in took_suffix.ambiguities] == \
        [AmbiguityKind.SUFFIX_OR_NAME]
    assert [t.text for t in took_suffix.ambiguities[0].tokens] == ["MA"]

    took_family = parse("Jack MA")
    assert took_family.family == "MA"
    assert [a.kind for a in took_family.ambiguities] == \
        [AmbiguityKind.SUFFIX_OR_NAME]


@pytest.mark.parametrize("text", [
    "John Smith M.A.",                   # periods decide it; no guess
    "Ma, Jack",                          # a comma fixes the family
    "Joao da Silva do Amaral de Souza",  # 'do' mid-name, never at the peel
    "John Smith PhD",                    # unambiguous vocabulary
])
def test_no_suffix_ambiguity_when_nothing_was_guessed(text: str) -> None:
    assert [a for a in parse(text).ambiguities
            if a.kind is AmbiguityKind.SUFFIX_OR_NAME] == []


def test_delimited_ambiguous_acronym_reports_suffix_or_nickname() -> None:
    # inside delimiters the competing readings are suffix and nickname:
    # "(MBA)" is unambiguously a credential and escapes to suffix, while
    # "(JD)" could be either, so it keeps the nickname reading -- a
    # guess, and until now a silent one
    n = parse("JEFFREY (JD) BRICKEN")
    assert n.nickname == "JD"
    assert [a.kind for a in n.ambiguities] == \
        [AmbiguityKind.SUFFIX_OR_NICKNAME]
    assert [t.text for t in n.ambiguities[0].tokens] == ["JD"]
    # the unambiguous one decided on vocabulary, so it is not a guess
    assert parse("Andrew Perkins (MBA)").ambiguities == ()


def test_every_ambiguous_acronym_in_a_name_is_reported() -> None:
    # one coin-flip per acronym: a single-slot record dropped all but
    # the last, which defeats the point of reporting at all
    n = parse("John Smith MA JD")
    assert n.suffix == "MA, JD"
    assert [a.kind for a in n.ambiguities] == \
        [AmbiguityKind.SUFFIX_OR_NAME] * 2
    assert sorted(t.text for a in n.ambiguities for t in a.tokens) == \
        ["JD", "MA"]


def test_ambiguous_acronym_detail_names_the_role_it_got() -> None:
    # the unpeeled piece is the last NAME piece, which is the family
    # name only under GIVEN_FIRST -- FAMILY_FIRST puts it in given, so
    # the detail has to follow the role actually assigned
    fam_first = Parser(policy=Policy(name_order=FAMILY_FIRST))
    n = fam_first.parse("Jack MA")
    assert (n.family, n.given) == ("Jack", "MA")
    assert "given name" in n.ambiguities[0].detail
    assert "family name" not in n.ambiguities[0].detail


def test_leading_particle_detail_names_the_role_it_got() -> None:
    # the same requirement as the acronym above, for the other kind:
    # `detail` is public output, so the role it names has to survive
    # assembly into ParsedName under a non-default order, not just be
    # right where _assign builds it
    fam_first = Parser(policy=Policy(name_order=FAMILY_FIRST))
    n = fam_first.parse("Van Johnson")
    assert (n.family, n.given) == ("Van", "Johnson")
    (amb,) = n.ambiguities
    assert amb.kind is AmbiguityKind.PARTICLE_OR_GIVEN
    assert amb.detail == (
        "leading 'Van' may be a family-name particle; "
        "read as a family name")
    # the default order is untouched by that change
    (default,) = parse("Van Johnson").ambiguities
    assert default.detail == (
        "leading 'Van' may be a family-name particle; "
        "read as a given name")


def test_trailing_roman_numeral_reports_the_fork() -> None:
    # a trailing single letter is a name part unless it happens to be a
    # roman numeral, in which case it is silently reclassified -- and
    # V/X/I are common middle initials, so this is a real coin-flip
    numeral = parse("John Smith V")
    assert numeral.suffix == "V"
    assert [a.kind for a in numeral.ambiguities] == \
        [AmbiguityKind.SUFFIX_OR_NAME]
    assert [t.text for t in numeral.ambiguities[0].tokens] == ["V"]
    # the same shape with a non-numeral letter faces no fork
    assert parse("John Smith B").ambiguities == ()
    # and a numeral after an initial is not treated as a suffix at all
    assert parse("John Q. V").ambiguities == ()


#: The words the _group-emitter tests below spell, apart from the
#: by-construction test, which invents its own. The emitter asks two
#: DIFFERENT things of two different words. Measured against
#: "Freiherr von Richthofen", one membership dropped at a time:
#:
#:   leading word ('Freiherr')  titles & PARTICLES, and the two halves
#:       buy different things. Without `particles` there is no CHAIN --
#:       'von' is the leading name piece again (given='von',
#:       family='Richthofen') and _assign reports the fork. Without
#:       `titles` the chain still happens (family='von Richthofen') but
#:       this emitter's `all(title(x) for x in range(k))` guard fails,
#:       so the REPORT is lost and _assign reports a fork about
#:       'Freiherr' instead. The merge sits outside that guard.
#:       Its `particles_ambiguous` membership is irrelevant either way,
#:       pinned by control 3 in the test below.
#:   chained word ('von')       PARTICLES_AMBIGUOUS. Drop it and the
#:       chain still happens (family='von Richthofen') but no fork is
#:       reported -- an unambiguous particle is not a decision.
#:
#: The distinction matters because this file used to assert
#: `titles & particles_ambiguous` for the LEADING word, which is the
#: wrong set. It reads as correct only because the two intersections are
#: the same three words today. #360 moves words between the may-be-given
#: and never-given halves of the particle vocabulary; both halves are
#: subsets of `particles`, so it cannot empty `titles & particles` and
#: cannot orphan this emitter.
#:
#: Both roles are supplied rather than borrowed, because reachability is
#: a property of the EMITTER, not of the shipped word lists: a caller may
#: configure the overlap themselves, and no `Lexicon` invariant forbids
#: it -- constructing one emits no warning. Supplying only the leading
#: half would leave the tests coupled to #360 through the chained word,
#: which is the bug the first cut of this commit shipped.
#:
#: What the SHIPPED vocabulary reaches is a separate claim, pinned in
#: tests/v2/cases.py's "Freiherr von Richthofen" row. Note that row
#: tracks the PARSE, not the memberships: moving `freiherr` between the
#: particle halves leaves it green, and only a change to the leading
#: word's `titles`/`particles` membership, or to `von`'s ambiguous one,
#: moves it.
_TITLE_PARTICLES = frozenset({"freiherr", "do", "st"})

#: The words those tests CHAIN. Disjoint from the leading set on purpose
#: -- the two roles need different memberships, and holding them apart is
#: what keeps that legible.
_CHAINED_PARTICLES = frozenset({"von", "van"})


def _overlap_parser(policy: Policy | None = None) -> Parser:
    """A Parser whose lexicon gives each word the memberships its ROLE
    needs, whatever the shipped data says today: the leading words become
    titles and particles, the chained words ambiguous particles.

    `particles` covers both because `_SUBSET_FIELDS` requires
    `particles_ambiguous <= particles`; the leading words are deliberately
    NOT made ambiguous, since that membership does nothing for them and
    asserting it is how the wrong set got written down in the first place.
    """
    lex = Lexicon.default().add(
        titles=_TITLE_PARTICLES,
        particles=_TITLE_PARTICLES | _CHAINED_PARTICLES,
        particles_ambiguous=_CHAINED_PARTICLES,
    )
    return Parser(lexicon=lex, policy=policy or Policy())


def test_the_chained_emitter_is_reachable_by_construction() -> None:
    """_group's PARTICLE_OR_GIVEN emitter fires when a piece that is both a
    title and a PARTICLE sits ahead of the chained particle.

    Asserted against a lexicon built here, so what it pins is the emitter
    rather than today's word lists. Three controls carry the weight, one
    per membership the claim rests on: drop the leading word's `particles`
    and the chain is gone; drop the chained word's `particles_ambiguous`
    and the report is gone; drop the leading word's `particles_ambiguous`
    and nothing moves at all -- which is the whole correction, since
    asserting THAT membership is what this file used to do.

    If this test fails, the emitter is gone or broken, or one of the two
    words this test builds has lost a membership it supplies itself. An
    empty `titles & particles_ambiguous` in the SHIPPED vocabulary does
    not fail it and does not mean the emitter is unreachable.
    """
    word = "zzoverlap"
    base = Lexicon.default().add(
        particles=_CHAINED_PARTICLES, particles_ambiguous=_CHAINED_PARTICLES)
    overlap = base.add(titles={word}, particles={word})
    text = f"{word} van Johnson"

    # the emitter, reached by construction
    chained = Parser(lexicon=overlap).parse(text)
    assert (chained.given, chained.family) == ("", "van Johnson")
    (amb,) = chained.ambiguities
    assert amb.kind is AmbiguityKind.PARTICLE_OR_GIVEN
    assert amb.detail == (
        "'van' was chained onto the following name piece; "
        "it is also a given name in other names")

    # control 1 -- leading word a plain title, NOT a particle: no chain
    # at all, and _assign reports the other side of the same fork.
    title_only = Parser(lexicon=base.add(titles={word})).parse(text)
    assert (title_only.given, title_only.family) == ("van", "Johnson")
    assert [a.detail for a in title_only.ambiguities] == [
        "leading 'van' may be a family-name particle; read as a given name"]

    # control 2 -- overlap intact but the CHAINED word unambiguous: the
    # chain still fires, so the parse matches, and the only difference is
    # that there is no decision left to report. Without this control the
    # assertion above could not tell "the emitter ran" from "the chain
    # happened to produce this grouping".
    unambiguous = dataclasses.replace(
        overlap, particles_ambiguous=overlap.particles_ambiguous - {"van"})
    quiet = Parser(lexicon=unambiguous).parse(text)
    assert (quiet.given, quiet.family) == (chained.given, chained.family)
    assert quiet.ambiguities == ()

    # control 3 -- the leading word made ambiguous as well, which is the
    # membership the deleted guard test asserted. Byte-identical to the
    # treatment, fork included: it buys the emitter nothing. This is the
    # executable half of the correction; without it the claim that
    # `titles & particles` is the right set lives only in a comment, and
    # a fixture supplying all three sets could never contradict it.
    also_ambiguous = overlap.add(particles_ambiguous={word})
    same = Parser(lexicon=also_ambiguous).parse(text)
    assert (same.given, same.family) == (chained.given, chained.family)
    assert [a.detail for a in same.ambiguities] == [amb.detail]


def test_ambiguous_particle_reports_both_branches_of_its_fork() -> None:
    # "von Richthofen" reads von as a given name and says so. Put a
    # piece in front of it that is BOTH a title and a particle and von
    # is no longer the name's leading piece, the prefix-chain merge
    # fires, and von becomes a particle instead -- the SAME fork,
    # called the other way. The two branches are taken in different
    # stages (_assign vs _group), so only the one with an emitter used
    # to report.
    #
    # Spelled with 'Freiherr' rather than the 'Dr.' this test used
    # until 2.2: an ordinary title is now transparent to the
    # leading-particle exception (#367), so "Dr. Van Johnson" takes the
    # _assign branch like everything else. `freiherr`/`st`/`do` -- a
    # title that could also be the name's own first piece -- is what
    # still reaches _group's emitter. This is the canonical spelling of
    # that, not the only one: "St Van Johnson", "Do St Johnson" and
    # "Dr. Do van Johnson" reach it as well.
    #
    # Parsed through _overlap_parser so the memberships are supplied
    # rather than borrowed -- see _TITLE_PARTICLES.
    p = _overlap_parser()
    given_reading = p.parse("von Richthofen")
    assert given_reading.given == "von"
    assert [a.kind for a in given_reading.ambiguities] == \
        [AmbiguityKind.PARTICLE_OR_GIVEN]

    particle_reading = p.parse("Freiherr von Richthofen")
    assert particle_reading.family == "von Richthofen"
    assert [a.kind for a in particle_reading.ambiguities] == \
        [AmbiguityKind.PARTICLE_OR_GIVEN]
    assert [t.text for t in particle_reading.ambiguities[0].tokens] == ["von"]
    # and the branch the title no longer takes: "Dr. Van Johnson" is
    # now byte-identical to the bare "Van Johnson", fork included
    titled, bare = p.parse("Dr. Van Johnson"), p.parse("Van Johnson")
    assert (titled.given, titled.family) == (bare.given, bare.family) \
        == ("Van", "Johnson")
    assert [a.detail for a in titled.ambiguities] == \
        [a.detail for a in bare.ambiguities]


def test_unambiguous_particle_chain_reports_nothing() -> None:
    # 'de' is never a given name, so merging it is not a fork
    assert parse("Dr. de la Vega").ambiguities == ()


def test_bound_given_name_that_is_also_a_particle() -> None:
    # The one case #367 regressed, restored by #369 for the right
    # reason. Through 2.1 it read correctly only because the title
    # displaced 'abu' out of the leading position and the prefix chain
    # claimed 'Bakar' -- a side effect of the #367 bug, not a rule. Now
    # the bound given-name join reads it: "Sheik" is a given-name
    # title, which licenses the join with one word to spare
    # (rules.md#P5), so the particle never enters into it -- and a
    # bound word read as the bound word is not a fork, so the
    # PARTICLE_OR_GIVEN report the chain used to emit is gone. The
    # same precedence, untitled, is what "Abu Bakar Salim" has always
    # had; where the reserve blocks the join, P4 and its report stand.
    titled = parse("Sheik Abu Bakar")
    assert (titled.given, titled.ambiguities) == ("Abu Bakar", ())
    assert parse("Abu Bakar Salim").ambiguities == ()
    assert [a.kind for a in parse("Abu Bakar").ambiguities] == \
        [AmbiguityKind.PARTICLE_OR_GIVEN]


def test_a_given_name_title_licenses_the_bound_given_join() -> None:
    # rules.md#P5 (#369): the contrast #367's release note draws --
    # "Sheik abdul salam", whose lead is a bound given name and NOT a
    # particle -- now joins the same way, and for the same reason. A
    # plain title does not license it: "Dr." addresses by family, so
    # the second word stays the family name.
    licensed = parse("Sheik abdul salam")
    assert (licensed.title, licensed.given, licensed.family) == \
        ("Sheik", "abdul salam", "")
    plain = parse("Dr. abdul salam")
    assert (plain.title, plain.given, plain.family) == \
        ("Dr.", "abdul", "salam")
    # and the pair's report: a bound word read as the bound word is
    # not a fork, so the pick 'Sheik John Ma' reports is not reported
    # for 'Sheik abdul Ma' (decisions.md#P5, the #369 precedent)
    assert parse("Sheik abdul Ma").ambiguities == ()
    assert [a.kind for a in parse("Sheik John Ma").ambiguities] == \
        [AmbiguityKind.SUFFIX_OR_NAME]


def test_the_bound_given_reserve_spares_the_family_assign_will_keep() -> None:
    # #401: the reserve asks whether a family name survives the join,
    # and the only right answer is the one assign gives. 'V' is the
    # suffix there, so there is no word to spare -- and behind a
    # given-name title (#369's licence) the same count declines.
    n = parse("abdul Smith V")
    assert (n.given, n.family, n.suffix) == ("abdul", "Smith", "V")
    assert [a.kind for a in n.ambiguities] == [AmbiguityKind.SUFFIX_OR_NAME]
    licensed = parse("Sir abdul V")
    assert (licensed.given, licensed.family, licensed.suffix) == \
        ("abdul", "", "V")


def test_the_bound_given_join_leaves_a_suffix_where_it_stands() -> None:
    # #421: the join declines a suffix piece, so an inner suffix goes
    # where it goes for any given name -- 'John Jr Smith Berg' reads
    # middle 'Jr Smith' -- and the split credential is a suffix again,
    # which is 1.4.0's reading restored.
    n = parse("abdul Jr Smith Berg")
    assert (n.given, n.middle, n.family, n.suffix) == \
        ("abdul", "Jr Smith", "Berg", "")
    n = parse("abdul Ph. D. Smith Berg")
    assert (n.given, n.middle, n.family, n.suffix) == \
        ("abdul", "Smith", "Berg", "Ph. D.")
    # after a family comma the decline holds under the LENIENT reserve
    n = parse("Berg, abdul Jr Smith")
    assert (n.given, n.middle, n.family, n.suffix) == \
        ("abdul", "Smith", "Berg", "Jr")


def test_the_reserve_declines_and_assign_reads_the_unjoined_pieces() -> None:
    # 'abdul J. V': the reserve reads the V as the suffix it would be
    # behind the joined pair, declines, and assign then sees the
    # unjoined pieces and reads the V as the family -- exactly as it
    # reads 'John J. V'. Decided, not accidental (decisions.md#P5).
    for text in ("abdul J. V", "John J. V"):
        n = parse(text)
        assert (n.middle, n.family, n.suffix) == ("J.", "V", "")
    # and behind a merged credential, which assign drops from its walk
    # so the V is last in it, the family survives
    n = parse("abdul Smith V Ph. D.")
    assert (n.given, n.family, n.suffix) == ("abdul", "Smith", "V, Ph. D.")


def test_the_reserve_spares_the_family_the_acronym_fork_would_take() -> None:
    # #425: with a suffix word between the pair and a bare ambiguous
    # acronym, assign peels the acronym (three pieces, words to spare)
    # and then the suffix, and the family the join left was never
    # there. The reserve now runs assign's peel over the joined view
    # and declines, so these read as their ordinary-given twins.
    for bound, plain in (("abdul Smith Jr Ma", "John Smith Jr Ma"),
                         ("abdul Rahman PhD MA", "John Rahman PhD MA")):
        n, m = parse(bound), parse(plain)
        assert (n.family, n.suffix) == (m.family, m.suffix)
        assert n.family != ""
    n = parse("abu Bakar Jr Ed")
    assert (n.family, n.suffix) == ("Bakar", "Jr, Ed")
    # and the join never turns a suffix into a name: unjoined, the
    # acronym is a credential with words to spare, so 'abdul Smith
    # Ma' reads as 'John Smith Ma' does (1.4.0 parity restored)
    n, m = parse("abdul Smith Ma"), parse("John Smith Ma")
    assert (n.family, n.suffix) == (m.family, m.suffix) == ("Smith", "Ma")


def test_a_joined_pair_is_never_peeled_as_a_title() -> None:
    # The conjunction merge derives a title tag for 'Sheikh and Ahmad';
    # the bound join takes the piece (a mid-name title word is a name
    # word, as 1.4.0 read it) and the pair must stay the given name,
    # not inherit the tag and be peeled as a leading title.
    n = parse("abdul Sheikh and Ahmad Bakar")
    assert (n.title, n.given, n.family) == \
        ("", "abdul Sheikh and Ahmad", "Bakar")
    # the title-word class: name words to P5, as v1 read them --
    # parity restored for the post-comma shape, never lost for the
    # main-walk one
    n = parse("abdul Sir Smith Berg")
    assert (n.given, n.middle, n.family) == ("abdul Sir", "Smith", "Berg")
    n = parse("Berg, abdul Sir")
    assert (n.given, n.family) == ("abdul Sir", "Berg")


def test_the_licence_does_not_lift_the_equality() -> None:
    # Behind a given-name title the reserve needs one name piece, so
    # "changes no suffix reading" is the only thing between 'Sir abdul
    # J. V' and a join that turns the V from a name word into the
    # suffix (#369 had joined it). It reads exactly as 'Sir John J. V'
    # does.
    for text in ("Sir abdul J. V", "Sir John J. V"):
        n = parse(text)
        assert (n.middle, n.family, n.suffix) == ("J.", "V", "")


def test_the_chain_and_the_walk_stop_where_the_peel_begins() -> None:
    # #424: the third and fourth sites that asked "is this a suffix?"
    # with the initial-vetoed test. Each reads as its ordinary twin
    # ('John Smith V', 'John Smith Ma') reads.
    for text, family, suffix in (
            ("John van der Berg V", "van der Berg", "V"),
            ("John van der Berg X", "van der Berg", "X"),
            ("abdul van der Berg V", "van der Berg", "V"),
            ("John van der Berg Ma", "van der Berg", "Ma")):
        n = parse(text)
        assert (n.family, n.suffix) == (family, suffix), text
    n = parse("John née Jones Smith V")
    assert (n.maiden, n.suffix) == ("Jones Smith", "V")
    n = parse("Jane Smith née Jones V")
    assert (n.family, n.maiden, n.suffix) == ("Smith", "Jones", "V")
    # the numeral must read as the suffix as the take leaves the name
    # too: an initial before the marker vetoes the fork, so the walk
    # keeps the V as maiden text rather than hand it to the family
    n = parse("J. née Jones Smith V")
    assert (n.family, n.maiden, n.suffix) == ("", "Jones Smith V", "")
    # an unlisted abbreviation is as transparent to the leading
    # particle as a listed title (H2 meets #367), so the acronym fork
    # counts the same pieces in group and in assign
    for abbrev in ("Xyz.", "Dr."):
        n = parse(f"{abbrev} van Berg MA")
        assert (n.given, n.family, n.suffix) == ("van", "Berg", "MA"), abbrev
        n = parse(f"{abbrev} van Johnson")
        assert (n.given, n.family) == ("van", "Johnson"), abbrev
        n = parse(f"{abbrev} abdul John Smith")
        assert (n.given, n.middle) == ("abdul John", ""), abbrev
    # behind a title-and-particle word the chain takes the name's first
    # word (#367), and the acronym it leaves has no words to spare for
    # assign: the chain keeps it rather than leave it as the family
    n = parse("Freiherr von Berg MA")
    assert (n.title, n.family, n.suffix) == ("Freiherr", "von Berg MA", "")
    # the numeral keeps its three pieces behind the same word, and the
    # chain, now the one name piece, reads as 'Dr. Smith V' reads
    n = parse("Freiherr von Richthofen V")
    assert (n.given, n.family, n.suffix) == ("von Richthofen", "", "V")
    n = parse("Dr. Smith V")
    assert (n.given, n.family, n.suffix) == ("Smith", "", "V")
    # the walk takes the numeral only: an acronym between the maiden
    # name and the numeral is maiden text
    n = parse("Jane Smith née Jones Ma V")
    assert (n.maiden, n.suffix) == ("Jones Ma", "V")


def test_the_numeral_fork_fires_on_the_last_piece_only() -> None:
    # The shared peel's own contract, pinned at the stage that owns
    # it: a numeral with a suffix behind it is a name word, for an
    # ordinary given name and the bound pair alike.
    for text, family in (("John Smith V Jr", "V"),
                         ("abdul Smith V Jr", "V")):
        n = parse(text)
        assert (n.family, n.suffix) == (family, "Jr")


@pytest.mark.parametrize("bound", ["abd", "abu"])
@pytest.mark.parametrize("numeral", ["I", "X"])
def test_every_bound_word_spares_the_family_before_every_numeral(
        bound: str, numeral: str) -> None:
    # The release log's claim: I and X as well as V, and the bound
    # words that are ALSO suffix vocabulary ('abd') or an ambiguous
    # particle ('abu') -- the dual-vocabulary paths where a veto could
    # hide. Two name words behind the bound word, so the join fires.
    n = parse(f"{bound} Allah Smith {numeral}")
    assert (n.given, n.family, n.suffix) == (f"{bound} Allah", "Smith", numeral)


@pytest.mark.parametrize("title", [
    "Sir", "Sheikh", "King", "الشيخ", "Dr.", "Mr.", "Mr. Sir", "Sir Dr.",
    "Sir and Dame", "Mr. and Mrs.", "Sheik and Mrs"])
def test_the_p5_licence_and_h1_read_a_title_run_the_same_way(
        title: str) -> None:
    # The licence's one invariant, as a contract: P5 lifts the reserve
    # behind a title run exactly when H1 keeps the one word after that
    # run a given name. Both key the run through _title_key; if either
    # side's key construction drifted, a run P5 licensed that H1 then
    # read as title-plus-family would hand the joined pair to the
    # family. So "no family" must agree, run by run.
    assert (parse(f"{title} John").family == "") == \
        (parse(f"{title} abdul rahman").family == "")


# The first three reach the chain loop and decline inside it: the piece
# after the particle is a suffix, so the scan never advances and merge()
# is a no-op -- nothing was chained, no fork taken. They are spelled with
# a title that is ALSO a particle ('Do', 'St'), because that is what
# still puts an ambiguous particle off the name's leading position since
# #367. The last three are the same strings with a plain title, which
# now decline one step earlier -- the particle IS the leading name piece
# and the loop skips it -- and are kept so the pair stays visible: two
# different reasons, one output, and neither may start reporting a fork.
@pytest.mark.parametrize("text", [
    "Do Van Jr.", "Do Van MD", "St Van Jr.",
    "Dr. Van Jr.", "Dr. Van MD", "Dr. Do Jr.",
])
def test_no_op_prefix_chain_is_not_a_fork(text: str) -> None:
    assert _overlap_parser().parse(text).ambiguities == ()


def test_a_fork_is_reported_by_exactly_one_stage() -> None:
    # the no-op merge left the particle a lone leading piece, which is
    # _assign's trigger, so both stages reported the same token.
    # 'Do' rather than the 'Dr.' this used until 2.2, for the reason
    # above: with a plain title the chain loop never fires at all now,
    # so the double-report it guards against is out of reach there.
    n = _overlap_parser().parse("Do Van Jr Smith")
    assert n.given == "Van"
    assert len(n.ambiguities) == 1


def test_chained_particle_detail_does_not_claim_a_role() -> None:
    # _group runs before assignment, so it cannot know which field the
    # chained piece lands in -- "Freiherr von Richthofen de la Cruz"
    # puts it in GIVEN, while the bare "Freiherr von Richthofen" above
    # puts it in FAMILY. The detail must describe the decision, not
    # guess a role.
    n = _overlap_parser().parse("Freiherr von Richthofen de la Cruz")
    assert n.given == "von Richthofen"
    (amb,) = n.ambiguities
    assert "family name" not in amb.detail


@pytest.mark.parametrize("policy", [
    Policy(),
    Policy(name_order=FAMILY_FIRST),
    Policy(name_order=FAMILY_FIRST_GIVEN_LAST),
])
def test_chained_particle_detail_is_order_invariant(policy: Policy) -> None:
    # _group's emitter is the reason the docs can scope leading-particle
    # DESTINATIONS to the default order without qualifying this text:
    # it names no field, and the chain it reports is a grouping-stage
    # decision taken before any role exists. "Freiherr von Richthofen"
    # takes the chained branch under every order, so the string is the
    # same one three times -- pin it, or the invariant is only an
    # intention. ("Dr. Van Johnson" carried this until 2.2; #367 made a
    # plain title transparent, so it no longer chains at all.)
    n = _overlap_parser(policy).parse("Freiherr von Richthofen")
    assert (n.given, n.family) == ("", "von Richthofen")
    (amb,) = n.ambiguities
    assert amb.kind is AmbiguityKind.PARTICLE_OR_GIVEN
    assert amb.detail == (
        "'von' was chained onto the following name piece; "
        "it is also a given name in other names")

    # The shape above is the one #367 did NOT move, so pin the one it
    # did in the same three orders: a plain title is transparent, so
    # "Dr. Van Johnson" is byte-identical to the bare "Van Johnson"
    # under every name_order, and the fork comes from _assign -- whose
    # detail DOES name the role, unlike the grouping-stage text above.
    # through _overlap_parser as well: 'Van' has to be an ambiguous
    # particle for _assign to report anything here, and that membership
    # is exactly what #360 may move
    p = _overlap_parser(policy)
    titled = p.parse("Dr. Van Johnson")
    bare = p.parse("Van Johnson")
    assert titled.title == "Dr."
    assert (titled.given, titled.middle, titled.family) == \
        (bare.given, bare.middle, bare.family)
    (titled_amb,) = titled.ambiguities
    assert titled_amb.detail == bare.ambiguities[0].detail
    role = "family" if policy.name_order[0] is Role.FAMILY else "given"
    assert titled_amb.detail == (
        f"leading 'Van' may be a family-name particle; "
        f"read as a {role} name")


def test_each_suffix_or_name_branch_describes_itself() -> None:
    # one kind, two causes: the acronym branch turns on periods, the
    # roman-numeral branch turns on the letter being a numeral. Sharing
    # one template made "V written without periods" -- a distinction
    # that does not exist for V -- and hid which branch fired.
    acronym = parse("John Smith MA").ambiguities[0].detail
    assert "periods" in acronym and "post-nominal" in acronym

    numeral = parse("John Smith V").ambiguities[0].detail
    assert "periods" not in numeral
    assert "numeral" in numeral and "initial" in numeral


def test_parser_matches_uses_its_own_config() -> None:
    p = Parser(lexicon=Lexicon.default().add(titles=["moff"]))
    a = p.parse("Moff Tarkin")
    # ParsedName.matches falls back to the DEFAULT parser for the str
    # argument, which reads "Moff" as a given name -- mismatch.
    assert not a.matches("Moff Tarkin")
    # Parser.matches parses the str with the same config -- match.
    assert p.matches(a, "Moff Tarkin")
    assert p.matches("Moff Tarkin", "MOFF TARKIN")


def test_parser_matches_rejects_wrong_types() -> None:
    p = Parser()
    with pytest.raises(TypeError, match="takes str or ParsedName"):
        p.matches(42, "John Smith")  # type: ignore[arg-type]
    with pytest.raises(TypeError, match="takes str or ParsedName"):
        p.matches("John Smith", 42)  # type: ignore[arg-type]


def test_parser_capitalized_uses_its_own_lexicon() -> None:
    # pair-tuples, not a dict: the field is tuple-annotated and typed
    # call sites pass canonical pairs (see _default_lexicon's note)
    exceptions = dict(
        Lexicon.default().capitalization_exceptions_map) | {"zqx": "ZqX"}
    lex = dataclasses.replace(
        Lexicon.default(),
        capitalization_exceptions=tuple(sorted(exceptions.items())))
    p = Parser(lexicon=lex)
    n = p.parse("john zqx")
    assert p.capitalized(n).family == "ZqX"
    # ParsedName.capitalized() with no argument uses the DEFAULT
    # lexicon, which has no such exception.
    assert n.capitalized().family == "Zqx"


def test_parser_capitalized_rejects_non_parsed_name() -> None:
    with pytest.raises(TypeError, match="takes a ParsedName"):
        Parser().capitalized("john smith")  # type: ignore[arg-type]


def test_revise_preserves_particle_tags() -> None:
    p = Parser()
    n = p.parse("Juan de la Vega")
    r = p.revise(n, family="de la Vega Smith")
    assert r.family == "de la Vega Smith"
    assert r.family_particles == "de la"
    assert r.initials() == "J. V. S."   # particles contribute no initial


def test_revise_keeps_multiword_suffix_one_credential() -> None:
    p = Parser()
    n = p.parse("John Smith Ph.D.")
    r = p.revise(n, suffix="Ph. D.")
    assert r.suffix == "Ph. D."         # replace() would render "Ph., D."


def test_revise_views_match_a_fresh_parse() -> None:
    p = Parser()
    r = p.revise(p.parse("John Smith"), family="de la Vega")
    f = p.parse("John de la Vega")
    for view in ("given", "family", "family_particles", "family_base"):
        assert getattr(r, view) == getattr(f, view)
    assert r.initials() == f.initials()


def test_revise_replace_shared_semantics() -> None:
    p = Parser()
    n = p.parse("Dr. Juan de la Vega Jr.")
    r = p.revise(n, given="José", suffix="")
    assert r.given == "José"
    assert r.suffix == ""               # empty value clears the field
    assert p.revise(n, suffix="()").suffix == ""   # punctuation-only too
    assert r.original == n.original     # provenance unchanged
    assert all(t.span is None for t in r.tokens_for("given"))
    assert r.title == "Dr."             # untouched fields keep spans


def test_revise_validation_matches_replace() -> None:
    p = Parser()
    n = p.parse("John Smith")
    with pytest.raises(TypeError, match="takes a ParsedName"):
        p.revise("John Smith", family="Doe")  # type: ignore[arg-type]
    with pytest.raises(TypeError, match="unknown field 'last'"):
        p.revise(n, last="Doe")
    with pytest.raises(TypeError, match="must be a str"):
        p.revise(n, family=None)  # type: ignore[arg-type]


def test_revise_strips_the_fold_marker() -> None:
    # middle_as_family's fold tag must not survive the harvest: a
    # carried tag would make the family view reorder the value.
    p = Parser(policy=Policy(middle_as_family=True))
    r = p.revise(p.parse("Juan Perez"), family="Gabriel García Márquez")
    assert r.family == "Gabriel García Márquez"


def test_revise_clears_a_stale_unjoined_mark() -> None:
    # UNJOINED_TAG says a particle stands alone in its PART, so an edit
    # that re-roles tokens invalidates it -- the harvest splices a
    # sub-parse's tokens into one field, and a particle marked alone
    # there can land beside a name word. Recomputed rather than
    # stripped (the fold marker above is stripped, which is only right
    # for one direction). Without this, an identity revise drifted:
    # base 'Toro' became 'del Toro' and initials 'T.' became 'd. T.'
    p = Parser()
    r = p.parse("Mr. do Jr. del Toro")
    assert (r.family, r.family_base, r.family_particles) == (
        "del Toro", "Toro", "del")
    again = p.revise(r, family=r.family)
    assert (again.family, again.family_base, again.family_particles) == (
        "del Toro", "Toro", "del")
    assert again.initials() == r.initials()


def test_revise_sets_a_missing_unjoined_mark() -> None:
    # The other direction, and the one that made rules.md#R2's
    # invariant false through this path: "St" alone parses as a TITLE
    # (a word in both the title and particle vocabularies), so the
    # sub-parse marks nothing, and the harvest then re-roles a bare
    # particle into FAMILY. The recompute marks it there, so a
    # non-empty family still has a non-empty base. Spelled with "Do"
    # until #296's audit took 'do' out of TITLES; "Do" alone is a
    # marked given name now, which is the other path (kept below).
    p = Parser()
    revised = p.revise(p.parse("Juan de la Vega"), family="St")
    assert revised.family == "St"
    assert revised.family_base == "St"
    assert revised.family_particles == ""
    revised = p.revise(p.parse("Juan de la Vega"), family="Do")
    assert (revised.family, revised.family_base) == ("Do", "Do")


def test_revise_sub_parse_structural_behavior() -> None:
    # the docstring's three structural promises, pinned: delimiters
    # never become tokens, marker words are consumed as in parsing,
    # and the sub-parse's ambiguities are discarded.
    p = Parser()
    n = p.parse("John Smith")
    assert p.revise(n, family="Smith (Jones)").family == "Smith Jones"
    revised = p.revise(n, family="Mary née Smith")
    assert revised.family == "Mary Smith"
    assert revised.maiden == ""
    assert p.revise(n, given="J.R. 'Bob'").given == "J.R. Bob"
    assert p.revise(n, family="Smith (Jones").ambiguities == ()


def test_revise_sub_parses_under_this_parsers_policy() -> None:
    # the sub-parse runs on SELF, not on a default Parser: revise's
    # docstring promises a marker LEADING a delimited value is
    # consumed, and only a policy routing that pair to maiden makes
    # the value delimited at all. Sub-parsing with Parser() instead
    # leaves the rest of the suite green -- every other revise
    # assertion uses a default parser, so nothing else can tell the
    # two apart.
    p = Parser(policy=Policy(maiden_delimiters=frozenset({("(", ")")})))
    n = p.parse("John Smith")
    assert p.revise(n, family="(née Jones)").family == "Jones"
    # and the third leg: a leading marker in an UNDELIMITED value is
    # no marker at all, so the same words keep it (#329)
    assert p.revise(n, family="née Jones").family == "née Jones"


def test_revise_forces_the_named_role_on_every_harvested_token() -> None:
    # the sub-parse reads "Dr." as a title and "Jr." as a suffix; the
    # named field's role must win for every token or the family view
    # silently drops them
    p = Parser()
    r = p.revise(p.parse("John Smith"), family="Dr. Vega Jr.")
    assert r.family == "Dr. Vega Jr."
    assert all(t.role is Role.FAMILY for t in r.tokens_for(Role.FAMILY))


def test_wholly_cjk_names_read_family_first_by_default() -> None:
    # the 2026-07-27 amendment: script determines the convention, so
    # no pack is needed -- release-log-classified fix (#271)
    n = parse("毛 泽东")
    assert (n.family, n.given) == ("毛", "泽东")
    n = parse("김 민준")
    assert (n.family, n.given) == ("김", "민준")
    # a lone wholly-CJK token takes the script order's first role: Han
    # segmentation is opt-in (locales.ZH), so the default parser leaves
    # this one token whole and reads it as the family name
    assert parse("毛泽东").family == "毛泽东"


def test_nfd_korean_input_still_reads_family_first() -> None:
    # fix(#271) classification, landed via the #272 NFC-classification
    # amendment: NFD decomposes each Hangul syllable onto bare jamo,
    # entirely outside the HANGUL range, so raw NFD input used to miss
    # script_orders' family-first rule and fall back to the positional
    # default -- a live gap in #294's shipped behavior until
    # single_script started classifying an NFC-normalized copy.
    n = parse(unicodedata.normalize("NFD", "김 민준"))
    # classification-only: the rendered text is exactly what was
    # typed (still NFD, spans untouched), so compare NFC-normalized --
    # the point under test is the ORDER (family first), not encoding
    assert (unicodedata.normalize("NFC", n.family),
            unicodedata.normalize("NFC", n.given)) == ("김", "민준")
    # pinned, not just stated: a future tokenize-level normalize (the
    # tempting over-fix, and an anti-#100 violation) must fail here
    assert n.family == unicodedata.normalize("NFD", "김")


def test_kana_licensed_names_read_family_first_by_default() -> None:
    # the #272 amendment: hiragana identifies Japanese as certainly
    # as hangul identifies Korean -- release-log-classified fix
    n = parse("高橋 みなみ")
    assert (n.family, n.given) == ("高橋", "みなみ")
    n = parse("山田 エミ")    # kanji piece + katakana piece: native
    assert (n.family, n.given) == ("山田", "エミ")
    # lone kana-licensed token takes the family role, unsplit
    assert parse("高橋みなみ").family == "高橋みなみ"


def test_iteration_mark_counts_as_han() -> None:
    # 々 (U+3005) repeats the preceding kanji. It is Script=Han under
    # UAX #24 already, but it lives outside every CJK ideograph BLOCK,
    # and the classifier is a block table -- so without its singleton
    # entry a 佐々木 token was in no script at all: the name reversed,
    # and the token never reached the segmentation gate. The Script
    # property would have got this one right unaided; the block table
    # is what needed the special case.
    n = parse("佐々木 太郎")
    assert (n.family, n.given) == ("佐々木", "太郎")
    n = parse("野々村 真")
    assert (n.family, n.given) == ("野々村", "真")
    # and a lone one takes the family role like any other Han token
    assert parse("奈々").family == "奈々"


def test_pure_katakana_stays_positional() -> None:
    # transcribed foreign names keep their original (usually Western)
    # order; katakana alone licenses nothing
    n = parse("マイケル ジャクソン")
    assert (n.given, n.family) == ("マイケル", "ジャクソン")


def test_katakana_transcription_parses_by_its_divider() -> None:
    # the dot tells us where the parts meet; transcriptions keep the
    # source language's order, which the positional default provides
    n = parse("マイケル・ジャクソン")
    assert (n.given, n.family) == ("マイケル", "ジャクソン")


def test_nakaguro_split_han_tokens_take_the_han_order() -> None:
    # different code path from the katakana case above: splitting on
    # the dot here produces two PURE-HAN tokens (no kana involved), so
    # script_orders' family-first HAN entry fires, same as any other
    # two-token Han name -- the dot only decides where the split falls
    n = parse("高橋・一郎")
    assert (n.family, n.given) == ("高橋", "一郎")


def test_halfwidth_nakaguro_splits_at_parse_level_too() -> None:
    # decision, not accident: halfwidth kana classify as no script at
    # all (_SCRIPT_RANGES only covers the fullwidth blocks), so this
    # is order-agnostic positional fallback, not a script-order rule --
    # the dot still divides the tokens regardless
    text = "ﾏｲｹﾙ･ｼﾞｬｸｿﾝ"
    n = parse(text)
    assert (n.given, n.family) == (
        "ﾏｲｹﾙ", "ｼﾞｬｸｿﾝ")


def test_nakaguro_inside_a_nickname_still_splits() -> None:
    # decision, not accident: delimited content tokenizes under the
    # same separator rules as the main stream, so a dot inside a
    # nickname still divides it -- and re-rendering a token stream
    # necessarily uses the render join, so the dot comes back as a
    # space, same as any other separator
    n = parse("山田 太郎 (マイケル・ジャクソン)")
    assert n.nickname == "マイケル ジャクソン"
    assert (n.family, n.given) == ("山田", "太郎")


def test_latin_names_are_untouched_by_script_orders() -> None:
    n = parse("John Smith")
    assert (n.given, n.family) == ("John", "Smith")
    # mixed-script names fall back to name_order too
    n = parse("John 王")
    assert (n.given, n.family) == ("John", "王")


def test_script_order_survives_latin_titles_and_suffixes() -> None:
    # The script test runs on the NAME pieces, after both peels, so a
    # Latin title or post-nominal cannot make the name look mixed.
    n = parse("Dr. 毛 泽东")
    assert (n.title, n.family, n.given) == ("Dr.", "毛", "泽东")
    n = parse("毛 泽东, PhD")
    assert (n.family, n.given, n.suffix) == ("毛", "泽东", "PhD")


def test_a_comma_still_decides_the_family_name_for_cjk() -> None:
    # The family-comma structure fixes the family before any positional
    # read, so the table is never consulted -- same rule name_order has.
    n = parse("泽东, 毛")
    assert (n.family, n.given) == ("泽东", "毛")


def test_three_cjk_pieces_take_the_script_order_middles() -> None:
    n = parse("毛 泽东 泽民")
    assert (n.family, n.given, n.middle) == ("毛", "泽东", "泽民")


def test_two_cjk_scripts_fall_back_even_though_both_read_family_first() -> None:
    # The rule is one script, or the Han/kana repertoire the #272
    # license covers -- not "the entries agree": Han+Hangul is written
    # in neither tradition, so it takes the positional default.
    n = parse("毛 김")
    assert (n.given, n.family) == ("毛", "김")


def test_a_hyphen_in_a_name_piece_declines_the_script_order() -> None:
    # Documenting the conservative direction, not proposing it: ANY
    # non-CJK character in a name piece (here the hyphen) puts that
    # piece in no script, so the piece set has two members and
    # script_orders declines in favour of the positional default.
    n = parse("毛 泽东-泽民")
    assert (n.given, n.family) == ("毛", "泽东-泽民")


def test_script_orders_opt_out_restores_positional_reading() -> None:
    p = Parser(policy=Policy(script_orders={}))  # type: ignore[arg-type]
    n = p.parse("毛 泽东")
    assert (n.given, n.family) == ("毛", "泽东")


def test_script_order_beats_explicit_global_name_order() -> None:
    # the script entry is the more specific rule; opting out means
    # script_orders={}, not a different name_order
    p = Parser(policy=Policy(name_order=FAMILY_FIRST_GIVEN_LAST))
    n = p.parse("김 민준")
    assert (n.family, n.given) == ("김", "민준")


def test_unspaced_korean_names_parse_by_default() -> None:
    # the whole point of shipping the census list as default
    # vocabulary (#271): no pack, no config
    n = parse("김민준")
    assert (n.family, n.given) == ("김", "민준")
    n = parse("남궁민수")     # two-syllable surname beats single 남
    assert (n.family, n.given) == ("남궁", "민수")


# -- the segmenter hook (#272) ------------------------------------------


def _module_level_decline(text: str) -> Segmentation | None:
    return None   # module-level so pickle can find it


# Inert sentinels for the plumbing tests below, which only ever compare
# identity. Two of them, because the override test needs the loser and
# the winner to be DISTINCT objects or its assertion is vacuous.
def _decline_a(text: str) -> Segmentation | None:
    return None


def _decline_b(text: str) -> Segmentation | None:
    return None


def test_parser_segmenter_is_keyword_only_and_validated() -> None:
    assert Parser().segmenter is None
    with pytest.raises(TypeError, match="callable"):
        Parser(segmenter=5)  # type: ignore[arg-type]
    with pytest.raises(TypeError, match="positional"):
        Parser(Lexicon.default(), Policy(), None)  # type: ignore[misc]  # positional: rejected


def test_parser_for_carries_the_base_segmenter() -> None:
    # not given: the base's carries through unchanged
    p = parser_for(locales.get("zh"), base=Parser(segmenter=_decline_a))
    assert p.segmenter is _decline_a


def test_parser_for_rejects_a_non_parser_base() -> None:
    with pytest.raises(TypeError, match="base must be a Parser"):
        parser_for(locales.get("zh"), base=5)  # type: ignore[arg-type]


def test_parser_for_takes_a_segmenter_keyword() -> None:
    p = parser_for(locales.get("zh"), segmenter=_decline_a)
    assert p.segmenter is _decline_a
    assert parser_for(locales.get("zh")).segmenter is None


def test_parser_for_segmenter_keyword_overrides_the_base() -> None:
    # later wins, the same rule scalar policy fields follow
    p = parser_for(locales.get("zh"), base=Parser(segmenter=_decline_a),
                   segmenter=_decline_b)
    assert p.segmenter is _decline_b


def test_parser_for_segmenter_none_clears_the_base() -> None:
    # the third state UNSET buys (#272 review): None is a VALUE here,
    # not an absence, so passing it explicitly drops the base's
    # segmenter instead of inheriting the very thing it was asked to
    # remove. Omitting the keyword is what carries the base's through
    # (the test above), and this is how you derive an unsegmented
    # parser from a segmented one without rebuilding its lexicon and
    # policy by hand.
    base = Parser(segmenter=_decline_a)
    pack = locales.get("zh")
    assert parser_for(pack, base=base, segmenter=None).segmenter is None
    # ...and the base is untouched: parser_for builds a fresh Parser
    assert base.segmenter is _decline_a


def test_parser_picklability_is_conditional_on_the_segmenter() -> None:
    # declared contract (locales spec section 4): Parser pickles iff
    # its segmenter does -- like any callable-holding object
    p = pickle.loads(pickle.dumps(Parser(segmenter=_module_level_decline)))
    assert p.segmenter is _module_level_decline
    unpicklable = Parser(segmenter=lambda t: None)  # constructs fine
    with pytest.raises(Exception):   # pickle's exception type varies
        pickle.dumps(unpicklable)    # only pickling fails


def test_segmenter_exceptions_propagate() -> None:
    # the ONE exception to parse-totality (locales spec section 4,
    # declared 2026-07-11): a user-supplied callable's own error is a
    # user-code error, not a content error, and must not be swallowed
    def boom(text: str) -> Segmentation | None:
        raise RuntimeError("segmenter bug")

    p = parser_for(locales.get("zh"), base=Parser(segmenter=boom))
    with pytest.raises(RuntimeError, match="segmenter bug"):
        p.parse("阿明")   # zh pack active, 阿 unmatched by vocabulary ->
                          # the stage consults the segmenter


def test_the_segmenter_sees_only_an_undivided_name() -> None:
    # its precondition (#272 Task 5): a segmenter answers where an
    # UNDIVIDED name divides, so a name part carrying a second
    # script-written token is already divided and the segmenter is not
    # consulted -- otherwise "山田 太郎" would have its family divided
    # again. A Latin title/suffix is not such a boundary.
    def always(text: str) -> Segmentation | None:
        return Segmentation((1,), confidence=1.0)

    p = parser_for(locales.get("zh"), base=Parser(segmenter=always))
    assert p.parse("阿明").family == "阿"          # one token: consulted
    n = p.parse("阿明 日月")                        # already divided
    assert (n.family, n.given) == ("阿明", "日月")
    assert p.parse("Dr 阿明").family == "阿"       # a title is not a split


def test_a_segmenter_split_reaches_the_fields() -> None:
    # end to end: the sub-slices the stage makes are ordinary tokens
    # from there on, so the pack's family-first order reads them like
    # any vocabulary split, and a low-confidence answer surfaces
    def two(text: str) -> Segmentation | None:
        return Segmentation((1,), confidence=0.5)

    p = parser_for(locales.get("zh"), base=Parser(segmenter=two))
    n = p.parse("阿明")
    assert (n.family, n.given) == ("阿", "明")
    assert [a.kind for a in n.ambiguities] == [AmbiguityKind.SEGMENTATION]

    # two cuts, three pieces -- and the token indices the comma
    # structure recorded still name the right words afterwards
    def three(text: str) -> Segmentation | None:
        return Segmentation((1, 2))

    q = parser_for(locales.get("zh"), base=Parser(segmenter=three))
    n3 = q.parse("Dr 阿明日, Jr.")
    assert (n3.title, n3.family, n3.given, n3.middle, n3.suffix) == (
        "Dr", "阿", "明", "日", "Jr.")


def _noop_segmenter(text: str) -> None:
    return None


def test_segmenterless_activation_without_vocabulary_warns() -> None:
    # The JA pack activates HAN and HIRAGANA segmentation but ships no
    # vocabulary, and no bundled list could serve those scripts -- so
    # without a segmenter, Japanese names can never divide. That is a
    # CONFIGURATION gap, not a fact about any name, and it was silent:
    # the misconfigured parser behaved identically to a working one
    # minus the feature. Statically detectable at construction, so
    # warn there.
    with pytest.warns(UserWarning, match=r"ja_segmenter"):
        parser_for(locales.JA)


def test_the_activation_warning_offers_a_spelling_that_type_checks() -> None:
    # The message's actionable half is the deactivation it offers, and
    # a user pastes it verbatim. nameparser ships py.typed, so that
    # paste has to survive a type checker: Policy(segment_scripts=())
    # is an arg-type error, since the field is annotated with what it
    # STORES (a frozenset) rather than everything the constructor
    # accepts. Nothing pinned this half of the message before.
    with pytest.warns(UserWarning) as caught:
        parser_for(locales.JA)
    message = str(caught[0].message)
    assert "Policy(segment_scripts=frozenset())" in message
    assert "Policy(segment_scripts=())" not in message


def test_a_segmenter_silences_the_activation_warning() -> None:
    # any segmenter counts: the gap is "nothing can divide these",
    # not "you did not use namedivider"
    parser_for(locales.JA, segmenter=_noop_segmenter)


def test_covered_activation_does_not_warn() -> None:
    # HANGUL is served by the census surnames; the zh pack ships the
    # vocabulary its own activation needs
    Parser()
    parser_for(locales.ZH)


def test_stacked_activation_warns_only_for_uncovered_scripts() -> None:
    # zh covers HAN and the default vocabulary covers HANGUL; only
    # HIRAGANA is left unservable, and the message must say WHICH
    # scripts are dead rather than naming the whole activation set
    with pytest.warns(UserWarning) as caught:
        parser_for(locales.ZH, locales.JA)
    # select by content: pack application can emit its own warnings
    # ahead of construction, so positional indexing is order-fragile
    message = next(str(w.message) for w in caught
                   if "segment_scripts activates" in str(w.message))
    assert "hiragana" in message
    assert "hangul" not in message


#: The corpus names a maiden clause can be appended to without the
#: clause itself being the variable: Latin script, no comma (a clause
#: behind a comma is post-comma text, rules.md#M2's Accepted row), and
#: no marker already present.
_LATIN = re.compile(r"^[\x00-\u024f]*$")


def _clause_free_latin_corpus_names() -> list[str]:
    from nameparser.config.maiden_markers import MAIDEN_MARKERS

    from ._differential_fixtures import _CORPUS_NAMES
    return [name for name in _CORPUS_NAMES
            if _LATIN.match(name) and "," not in name
            and not any(word.lower().rstrip(".") in MAIDEN_MARKERS
                        for word in name.split())]


@pytest.mark.parametrize("name", _clause_free_latin_corpus_names())
def test_a_maiden_clause_changes_nothing_else(name: str) -> None:
    """The grouping rules count and join only the words that remain
    once the marker and the maiden name leave (rules.md#M2, #418), so
    appending a clause adds a maiden name and moves no other field.

    Over the corpus rather than by example, because the defect was an
    appended-clause shape on names that are otherwise ordinary ('John
    e Smith', 'Lt.Gov. juan e garcia'), which no corpus carries in
    that form and which the differential gate therefore cannot see.
    Before the marker pass moved ahead of the joins, seven of these
    names failed this.

    One boundary, and it is not the grouping stage's: a name whose
    residual is a single name piece (a title plus one word, 'Dr.
    Jane') places that piece in `family` alone and in `given` once a
    maiden name exists -- #410's shape, pre-existing, so those names
    are stepped over rather than asserted either way.
    """
    base = parse(name)
    if base.given == "":
        pytest.skip("#410: a lone residual piece moves between fields")
    with_clause = parse(name + " née Jones")
    assert with_clause.maiden == "Jones"
    for field in ("title", "given", "middle", "family", "suffix",
                  "nickname"):
        assert getattr(with_clause, field) == getattr(base, field), (
            f"{name!r}: {field} reads {getattr(base, field)!r} alone and "
            f"{getattr(with_clause, field)!r} with a maiden clause")
