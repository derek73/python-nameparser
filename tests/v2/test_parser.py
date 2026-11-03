import dataclasses
import itertools
import pickle
import re
import unicodedata
import warnings

import pytest

from nameparser import (
    Lexicon, Locale, Parser, Policy, PolicyPatch, Script, locales, parse,
    parser_for,
)
from nameparser._policy import (
    CapsSuffixes, FAMILY_FIRST, FAMILY_FIRST_GIVEN_LAST, GIVEN_FIRST,
    PatronymicRule,
)
from nameparser._types import (UNJOINED_CONJUNCTION_TAG, UNJOINED_TAG,
                               AmbiguityKind, ParsedName, Role, Segmentation)


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
                lexicon=Lexicon.empty().add("г-н", kind="title"),
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


# Each scalar PolicyPatch field, with two values of it that differ, and
# for a mapping-shaped field a respelling of the first in another key
# order: the same value written differently. Held to the patch's own
# field list below, so a new scalar field cannot escape the two tests.
_HAN_FIRST = {Script.HAN: FAMILY_FIRST, Script.HANGUL: GIVEN_FIRST}
_SCALARS: dict[str, tuple[object, object, object]] = {
    "name_order": (GIVEN_FIRST, FAMILY_FIRST, GIVEN_FIRST),
    "script_orders": (_HAN_FIRST, {Script.HAN: GIVEN_FIRST},
                      dict(reversed(list(_HAN_FIRST.items())))),
    "unlisted_caps_suffixes": (CapsSuffixes.OFF, CapsSuffixes.AFTER_COMMA,
                               CapsSuffixes.OFF),
    **{flag: (False, True, False) for flag in (
        "middle_as_family", "lenient_comma_suffixes", "strip_emoji",
        "strip_bidi", "unlisted_dotted_suffixes", "two_family_names",
        "two_given_names")},
}


def test_the_scalar_table_is_every_scalar_patch_field() -> None:
    assert set(_SCALARS) == {f.name for f in dataclasses.fields(PolicyPatch)
                             if f.metadata.get("compose") != "union"}


def _pack(code: str, field: str, value: object) -> Locale:
    return Locale(code=code, lexicon=Lexicon.empty(),
                  policy=PolicyPatch(**{field: value}))  # type: ignore[arg-type]


@pytest.mark.parametrize("field", sorted(_SCALARS))
def test_parser_for_warns_where_two_packs_set_a_scalar_differently(field: str) -> None:
    first, other, _ = _SCALARS[field]
    with pytest.warns(UserWarning, match=f"'bb' overrides scalar policy field {field!r} "
                                         f"already set by locale 'aa'; later wins"):
        stacked = parser_for(_pack("aa", field, first), _pack("bb", field, other))
    # later wins: the field reads as the second pack alone sets it
    assert getattr(stacked.policy, field) == getattr(
        parser_for(_pack("bb", field, other)).policy, field)


@pytest.mark.parametrize("field", sorted(_SCALARS))
def test_parser_for_is_silent_where_two_packs_set_a_scalar_alike(field: str) -> None:
    # two packs agreeing on a value override nothing, whatever spelling of
    # it each writes (filterwarnings = error makes any warning a failure);
    # the warning is for a value that differs, test above
    first, _, respelled = _SCALARS[field]
    for second in (first, respelled):
        stacked = parser_for(_pack("aa", field, first), _pack("bb", field, second))
        assert stacked.policy == parser_for(_pack("aa", field, first)).policy


def test_parser_for_is_silent_over_the_shipped_packs_that_agree() -> None:
    # cs, sk and es all turn two_family_names on: their stacks, in either
    # order, must not fail a caller running with warnings as errors
    for stack in ((locales.CS, locales.SK), (locales.SK, locales.CS),
                  (locales.ES, locales.CS, locales.SK)):
        assert parser_for(*stack).policy.two_family_names is True


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
    # #436: the writer typed no comma, so none is rendered
    assert parse("John Smith PhD MD").suffix == "PhD MD"


def test_phd_split_mid_name_is_a_suffix() -> None:
    # v1 parity: fix_phd extracted the credential BEFORE parsing, so
    # position never mattered; the merged piece is a suffix anywhere
    pn = parse("Dr. John Ph. D. Smith")
    assert pn.suffix == "Ph. D."
    assert pn.family == "Smith"
    assert pn.middle == ""


def _without_phd(label: str) -> Parser:
    """A parser whose lexicon lists no unambiguous `phd` (#1000)."""
    with warnings.catch_warnings():
        # an empty lexicon holds no hangul surnames to segment on
        warnings.filterwarnings(
            "ignore", message="Policy.segment_scripts activates hangul")
        return {
            "removed": lambda: Parser(lexicon=Lexicon.default().remove(
                "phd", kind="credential")),
            "ambiguous": lambda: Parser(lexicon=Lexicon.default().add(
                "phd", kind="family")),
            # an ambiguous suffix WORD, which the split-credential path
            # would admit as a counted member (#1000's third review)
            "ambiguous word": lambda: Parser(lexicon=Lexicon.default()
                                             .remove("phd", kind="credential")
                                             .add("phd", kind="family")
                                             .add("phd", kind="credential",
                                                  acronym=False)),
            "empty": lambda: Parser(lexicon=Lexicon.empty()),
            # a strict choice reads mul.toml, `phd` among it (#1005), so
            # its base removes it
            "strict pt": lambda: parser_for(locales.PT, strict=True, base=Parser(
                lexicon=Lexicon.default().remove("phd", kind="credential"))),
            "strict pt, family first": lambda: parser_for(
                locales.PT, strict=True, base=Parser(
                    lexicon=Lexicon.default().remove("phd", kind="credential"),
                    policy=Policy(name_order=FAMILY_FIRST))),
        }[label]()


# Each of these read suffix 'Ph. D.' under every lexicon before #1000,
# the pair asking no vocabulary.
_PHD_SHAPES = (
    "John Smith Ph. D.",
    "John Smith, Ph. D.",
    "John Smith Ph D",
    "John Smith Ph. D. Jr.",
    "John Ph. D.",
    "Smith, John Ph. D.",
    "John Ph. D. Smith",
)


@pytest.mark.parametrize("text", _PHD_SHAPES)
@pytest.mark.parametrize("label", [
    "removed", "ambiguous", "ambiguous word", "empty", "strict pt",
    "strict pt, family first"])
def test_phd_pair_is_no_credential_where_the_lexicon_lists_no_phd(
        label: str, text: str) -> None:
    # decisions/phd-merge (#1000): a lexicon without `phd` as an
    # unambiguous credential asks the pair as any other split credential,
    # and its fold being unlisted or ambiguous, the pair is its two words
    parser = _without_phd(label)
    words = [t for t in parser.parse(text).tokens
             if t.text in ("Ph.", "Ph", "D.", "D")]
    assert len(words) == 2
    assert all(t.role is not Role.SUFFIX for t in words)


@pytest.mark.parametrize("label", ["removed", "ambiguous", "ambiguous word"])
def test_phd_pair_reads_its_two_words_where_it_does_not_merge(
        label: str) -> None:
    parser = _without_phd(label)
    n = parser.parse("John Smith Ph. D.")
    assert (n.middle, n.family, n.suffix) == ("Smith Ph.", "D.", "")
    h = parser.parse("John Smith, Ph. D.")
    assert (h.title, h.given, h.family) == ("Ph.", "D.", "John Smith")
    # the dotted joined spelling stays a suffix by its shape (rules/S3)
    assert parser.parse("John Smith Ph.D.").suffix == "Ph.D."


@pytest.mark.parametrize("text", [
    # mid-name only the merged pair is a suffix, a bare `PhD` a name word
    # (decisions/phd-merge), so no mid-name row
    "Smith, Ph. D.", "John Ph. D.", "John Smith Ph. D."])
def test_phd_listed_as_a_suffix_word_reads_both_spellings_alike(
        text: str) -> None:
    # the gate is unambiguous suffix vocabulary of either kind, as the
    # joined spelling reads it (#1000's second review)
    parser = Parser(lexicon=Lexicon.default().remove(
        "phd", kind="credential").add("phd", kind="suffix"))
    spaced = parser.parse(text)
    joined = parser.parse(text.replace("Ph. D.", "PhD"))
    assert spaced.suffix == "Ph. D."
    assert joined.suffix == "PhD"
    assert spaced.ambiguities == joined.ambiguities


def test_phd_pair_outranks_an_overlapping_pair_only_where_it_merges() -> None:
    # 'Dr. Ph.' folds to the listed 'drph': the Ph./D. pair takes the
    # overlap where `phd` is an unambiguous credential, and leaves it to
    # that pair where it is not
    assert parse("Jane Doe Dr. Ph. D.").title == "Dr."
    for label in ("removed", "ambiguous"):
        n = _without_phd(label).parse("Jane Doe Dr. Ph. D.")
        assert (n.title, n.suffix) == ("", "Dr. Ph. D."), label


def test_ambiguous_acronym_reports_the_reading_it_took() -> None:
    # 'ma' is both a post-nominal and a surname, so whichever way the
    # peel resolves it is a guess -- the same shape as the leading
    # ambiguous particle that already reports PARTICLE_OR_GIVEN. In a
    # name written in one case: in a name of mixed case the capitals
    # settle the word and nothing reports it (rules/S6, #785)
    took_suffix = parse("JOHN SMITH MA")
    assert took_suffix.suffix == "MA"
    assert [a.kind for a in took_suffix.ambiguities] == \
        [AmbiguityKind.SUFFIX_OR_NAME]
    assert [t.text for t in took_suffix.ambiguities[0].tokens] == ["MA"]

    # MOVED by #289, not deleted: 'MA' is written in capitals inside a
    # mixed-case name, so it now leans CREDENTIAL and is taken with no
    # words to spare -- 'Jack' is the only name word left, which is
    # what also turns on the GIVEN_OR_FAMILY fork (decisions/S6). The
    # capitals settled 'MA', so that fork is the only one (#785).
    took_family = parse("Jack MA")
    assert took_family.suffix == "MA"
    assert not took_family.family
    assert set(a.kind for a in took_family.ambiguities) == \
        {AmbiguityKind.GIVEN_OR_FAMILY}
    # and in one case the count decides, and reports the family it kept
    took_family = parse("JACK MA")
    assert took_family.family == "MA"
    assert [a.kind for a in took_family.ambiguities] == \
        [AmbiguityKind.SUFFIX_OR_NAME]


@pytest.mark.parametrize("text", [
    "John Smith M.A.",                   # periods decide it; no guess
    "Ma, Jack",                          # a comma fixes the family
    "Joao da Silva do Amaral de Souza",  # 'do' mid-name, never at the peel
    "John Smith PhD",                    # unambiguous vocabulary
    "John Smith MA",                     # capitals settle it (#785)
])
def test_no_suffix_ambiguity_when_nothing_was_guessed(text: str) -> None:
    assert [a for a in parse(text).ambiguities
            if a.kind is AmbiguityKind.SUFFIX_OR_NAME] == []


def test_delimited_ambiguous_acronym_reports_suffix_or_nickname() -> None:
    # inside delimiters the competing readings are suffix and nickname:
    # "(MPH)" is unambiguously a credential and escapes to suffix, while
    # "(JD)" could be either, so it keeps the nickname reading -- a
    # guess, and until now a silent one
    n = parse("JEFFREY (JD) BRICKEN")
    assert n.nickname == "JD"
    assert [a.kind for a in n.ambiguities] == \
        [AmbiguityKind.SUFFIX_OR_NICKNAME]
    assert [t.text for t in n.ambiguities[0].tokens] == ["JD"]
    # the unambiguous one decided on vocabulary, so it is not a guess
    assert parse("Andrew Perkins (MPH)").ambiguities == ()


def test_every_ambiguous_acronym_in_a_name_is_reported() -> None:
    # one coin-flip per acronym: a single-slot record dropped all but
    # the last, which defeats the point of reporting at all
    # (in one case, where no writing settles either word, rules/S6)
    n = parse("JOHN SMITH MA JD")
    # the scenery the record is read off; only its separator moved (#436)
    assert n.suffix == "MA JD"
    assert [a.kind for a in n.ambiguities] == \
        [AmbiguityKind.SUFFIX_OR_NAME] * 2
    assert sorted(t.text for a in n.ambiguities for t in a.tokens) == \
        ["JD", "MA"]


def _reports(text: str) -> list[tuple[AmbiguityKind, list[str]]]:
    return [(a.kind, [t.text for t in a.tokens])
            for a in parse(text).ambiguities]


def test_a_member_the_company_decides_after_a_family_comma_reports() -> None:
    # #544: a part after a one-word family comma that a credential in
    # front reads wholly as credentials reports each member it decided
    # -- and only those: a member whose capitals already lean
    # credential decided itself, so the same fields are silent
    n = parse("Smith, PhD Ma")
    assert (n.family, n.given, n.suffix) == ("Smith", "", "PhD Ma")
    assert _reports("Smith, PhD Ma") == [
        (AmbiguityKind.SUFFIX_OR_NAME, ["Ma"])]
    n = parse("Smith, PhD MA")
    assert (n.family, n.given, n.suffix) == ("Smith", "", "PhD MA")
    assert n.ambiguities == ()


def test_a_dotted_credential_is_no_title_run_dual() -> None:
    # 'M.D.' carries the suffix reading and not the title one, so it
    # does not stand in the given part's leading title run: 'PhD'
    # behind it still speaks for 'Ma', and the pick reports (the parent
    # read given 'M.D.', middle 'Ma', suffix 'PhD')
    n = parse("Smith, M.D. PhD Ma")
    assert (n.family, n.given, n.suffix) == ("Smith", "", "M.D. PhD Ma")
    assert _reports("Smith, M.D. PhD Ma") == [
        (AmbiguityKind.SUFFIX_OR_NAME, ["Ma"])]


def test_ambiguous_acronym_detail_names_the_role_it_got() -> None:
    # the unpeeled piece is the last NAME piece, which is the family
    # name only under GIVEN_FIRST -- FAMILY_FIRST puts it in given, so
    # the detail has to follow the role actually assigned
    #
    # MOVED by #289, not deleted: 'Jack MA' is mixed case now, so 'MA'
    # leans CREDENTIAL and is peeled as a suffix under every order --
    # there is no unpeeled acronym left for the detail to name a role
    # for. 'JACK MA' (one case, no lean) is the input that still
    # exercises the mechanism this test pins: the count alone decides,
    # and the detail names whichever role the order actually gave it.
    fam_first = Parser(policy=Policy(name_order=FAMILY_FIRST))
    n = fam_first.parse("JACK MA")
    assert (n.family, n.given) == ("JACK", "MA")
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

    Both get a particle reading; the chained words a given reading too,
    which is what makes a particle ambiguous. The leading words are given
    none here, since that membership does nothing for them and asserting
    it is how the wrong set got written down in the first place (the
    shipped `freiherr`, `do` and `st` hold one of their own, which this
    leaves as it is).
    """
    lex = (Lexicon.default()
           .add(*sorted(_TITLE_PARTICLES), kind="title")
           .add(*sorted(_TITLE_PARTICLES | _CHAINED_PARTICLES), kind="particle")
           .add(*sorted(_CHAINED_PARTICLES), kind="given"))
    return Parser(lexicon=lex, policy=policy or Policy())


def test_the_chained_emitter_is_reachable_by_construction() -> None:
    """_group's PARTICLE_OR_GIVEN emitter fires when a piece that is both a
    title and a PARTICLE sits ahead of the chained particle.

    Asserted against a lexicon built here, so what it pins is the emitter
    rather than today's word lists. Three controls carry the weight, one
    per reading the claim rests on: drop the leading word's particle
    reading and the chain is gone; drop the chained word's given reading
    (its `particles_ambiguous` membership) and the report is gone; give
    the leading word a given reading too and nothing moves at all -- which is the whole correction, since
    asserting THAT membership is what this file used to do.

    If this test fails, the emitter is gone or broken, or one of the two
    words this test builds has lost a reading it supplies itself. An
    empty `titles & particles_ambiguous` in the SHIPPED vocabulary does
    not fail it and does not mean the emitter is unreachable.
    """
    word = "zzoverlap"
    base = (Lexicon.default()
            .add(*sorted(_CHAINED_PARTICLES), kind="particle")
            .add(*sorted(_CHAINED_PARTICLES), kind="given"))
    overlap = base.add(word, kind="title").add(word, kind="particle")
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
    title_only = Parser(lexicon=base.add(word, kind="title")).parse(text)
    assert (title_only.given, title_only.family) == ("van", "Johnson")
    assert [a.detail for a in title_only.ambiguities] == [
        "leading 'van' may be a family-name particle; read as a given name"]

    # control 2 -- overlap intact but the CHAINED word unambiguous: the
    # chain still fires, so the parse matches, and the only difference is
    # that there is no decision left to report. Without this control the
    # assertion above could not tell "the emitter ran" from "the chain
    # happened to produce this grouping".
    unambiguous = overlap.remove("van", kind="given")
    quiet = Parser(lexicon=unambiguous).parse(text)
    assert (quiet.given, quiet.family) == (chained.given, chained.family)
    assert quiet.ambiguities == ()

    # control 3 -- the leading word made ambiguous as well, which is the
    # membership the deleted guard test asserted. Byte-identical to the
    # treatment, fork included: it buys the emitter nothing. This is the
    # executable half of the correction; without it the claim that
    # `titles & particles` is the right set lives only in a comment, and
    # a fixture supplying all three sets could never contradict it.
    also_ambiguous = overlap.add(word, kind="given")
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
    # the bound given-name join reads it: "Sir" is a given-name
    # title, which licenses the join with one word to spare
    # (rules/P5), so the particle never enters into it -- and a
    # bound word read as the bound word is not a fork, so the
    # PARTICLE_OR_GIVEN report the chain used to emit is gone. The
    # same precedence, untitled, is what "Abu Bakar Salim" has always
    # had; where the reserve blocks the join, P4 and its report stand.
    titled = parse("Sir Abu Bakar")
    assert (titled.given, titled.ambiguities) == ("Abu Bakar", ())
    assert parse("Abu Bakar Salim").ambiguities == ()
    assert [a.kind for a in parse("Abu Bakar").ambiguities] == \
        [AmbiguityKind.PARTICLE_OR_GIVEN]


def test_a_given_name_title_licenses_the_bound_given_join() -> None:
    # rules/P5 (#369): the contrast #367's release note draws --
    # "Sheik abdul salam", whose lead is a bound given name and NOT a
    # particle -- now joins the same way, and for the same reason. A
    # plain title does not license it: "Dr." addresses by family, so
    # the second word stays the family name.
    # `sheik` has been a title only inside a title phrase since #752
    # phase 2j, so `Sir` stands in for it here, reading as it did.
    licensed = parse("Sir abdul salam")
    assert (licensed.title, licensed.given, licensed.family) == \
        ("Sir", "abdul salam", "")
    plain = parse("Dr. abdul salam")
    assert (plain.title, plain.given, plain.family) == \
        ("Dr.", "abdul", "salam")
    # and the pair's report. Until #614 a bound word read as the bound
    # word was no fork, so 'Sir abdul Ma' reported nothing where
    # 'Sir John Ma' reports its pick (the #369 precedent). S2's run is
    # read once now, before the join, and the read weighs 'Ma' as a
    # credential and declines it before the join makes it part of the
    # given pair -- so the pick reports in both (decisions/P5,
    # 2026-10-07)
    for text in ("Sir abdul Ma", "Sir John Ma"):
        assert [a.kind for a in parse(text).ambiguities] == \
            [AmbiguityKind.SUFFIX_OR_NAME], text
    assert parse("Sir abdul Ma").given == "abdul Ma"


def test_the_bound_given_reserve_spares_the_family_assign_will_keep() -> None:
    # #401: the reserve asks whether a family name survives the join,
    # and the only right answer is the one assign gives. 'V' is the
    # suffix there, so there is no word to spare -- and behind a
    # given-name title (#369's licence) the same count declines.
    n = parse("abdul Smith V")
    assert (n.given, n.family, n.suffix) == ("abdul", "Smith", "V")
    assert [a.kind for a in n.ambiguities] == [AmbiguityKind.SUFFIX_OR_NAME]
    # Since #718 a one-letter numeral needs words to spare (rules/S10)
    # and a title is none, so 'V' is a name word there, and the
    # licence joins it into the given pair as it would any word
    licensed = parse("Sir abdul V")
    assert (licensed.given, licensed.family, licensed.suffix) == \
        ("abdul V", "", "")


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
    # after a family comma the decline holds under the LENIENT reserve,
    # and since #602 the 'Jr' starts the given part's credential run,
    # taking 'Smith' with it (rules/S8)
    n = parse("Berg, abdul Jr Smith")
    assert (n.given, n.middle, n.family, n.suffix) == \
        ("abdul", "", "Berg", "Jr Smith")


def test_the_reserve_counts_what_the_trailing_read_left() -> None:
    # 'abdul J. V': until #614 the reserve read the V as the suffix it
    # would be behind the joined pair and declined, so the name read as
    # 'John J. V' does. S2's run is read once now, before the join: it
    # takes nothing (the initial-shaped 'J.' suppresses the fork), three
    # name words stand, and the join leaves two, so it stands -- given
    # 'abdul J.', family 'V'. The join no longer re-reads the fork it
    # would move (decisions/P5, 2026-10-07).
    n = parse("abdul J. V")
    assert (n.given, n.middle, n.family, n.suffix) == ("abdul J.", "", "V", "")
    n = parse("John J. V")
    assert (n.middle, n.family, n.suffix) == ("J.", "V", "")
    # and behind a merged credential, which assign drops from its walk
    # so the V is last in it, the numeral is the name word it is behind
    # 'PhD' (rules/S10, #752), so the name reads as its one-word twin
    n = parse("abdul Smith V Ph. D.")
    assert (n.given, n.family, n.suffix) == ("abdul Smith", "V", "Ph. D.")
    twin = parse("abdul Smith V PhD")
    assert (twin.given, twin.family, twin.suffix) == ("abdul Smith", "V", "PhD")


def test_the_reserve_spares_the_family_the_acronym_fork_would_take() -> None:
    # #425: with a suffix word between the pair and a bare ambiguous
    # acronym, assign peels the acronym (three pieces, words to spare)
    # and then the suffix, and the family the join left was never
    # there. The reserve declines, so these read as their
    # ordinary-given twins -- since #614 by counting the names S2's
    # run left before the join, read once, rather than re-reading the
    # peel over the joined view.
    for bound, plain in (("abdul Smith Jr Ma", "John Smith Jr Ma"),
                         ("abdul Rahman PhD MA", "John Rahman PhD MA")):
        n, m = parse(bound), parse(plain)
        assert (n.family, n.suffix) == (m.family, m.suffix)
        assert n.family != ""
    # MOVED by #289, then back by #544: 'Ed' is Title-case in a
    # mixed-case name, so its writing leans SURNAME, but the
    # unambiguous 'Jr' in front of it anchors it, so the peel takes
    # both and the reserve spares the family as for 'abdul Smith Jr
    # Ma' above -- the ordinary-given twin reads the same
    n, m = parse("abu Bakar Jr Ed"), parse("John Bakar Jr Ed")
    assert (n.family, n.suffix) == (m.family, m.suffix) == ("Bakar",
                                                            "Jr Ed")
    # and the join never turns a suffix into a name: unjoined, the
    # acronym is a credential with words to spare, so 'abdul Smith
    # Ma' reads as 'John Smith Ma' does (1.4.0 parity restored)
    #
    # MOVED by #289, not deleted: 'Ma' is Title-case in a mixed-case
    # name, so it leans SURNAME on both sides of the join and stays a
    # name word instead of a credential (decisions/S6).
    n, m = parse("abdul Smith Ma"), parse("John Smith Ma")
    assert (n.family, n.suffix) == (m.family, m.suffix) == ("Ma", "")


def test_the_leading_piece_never_anchors_under_any_name_order() -> None:
    # #544: the walk's leading position is the piece the
    # H4 carve-out keeps regardless of which ROLE it ends up in, so
    # the fix must hold under every name_order -- FAMILY_FIRST puts
    # the same 'PhD'/'Om' word in the FAMILY slot instead, and it
    # still must not anchor 'Ma' behind it.
    for order in (FAMILY_FIRST, FAMILY_FIRST_GIVEN_LAST):
        p = Parser(policy=Policy(name_order=order))
        n = p.parse("Om Ma")
        assert (n.given, n.family, n.suffix) == ("Ma", "Om", "")
        n = p.parse("PhD Ma")
        assert (n.given, n.family, n.suffix) == ("Ma", "PhD", "")


def test_a_joined_pair_is_never_peeled_as_a_title() -> None:
    # The conjunction merge derives a title tag for 'Sir and Ahmad';
    # the bound join takes the piece (a mid-name title word is a name
    # word, as 1.4.0 read it) and the pair must stay the given name,
    # not inherit the tag and be peeled as a leading title.
    n = parse("abdul Sir and Ahmad Bakar")
    assert (n.title, n.given, n.family) == \
        ("", "abdul Sir and Ahmad", "Bakar")
    # the title-word class: name words to P5, as v1 read them --
    # parity restored for the post-comma shape, never lost for the
    # main-walk one
    n = parse("abdul Sir Smith Berg")
    assert (n.given, n.middle, n.family) == ("abdul Sir", "Smith", "Berg")
    n = parse("Berg, abdul Sir")
    assert (n.given, n.family) == ("abdul Sir", "Berg")


def test_the_licence_joins_where_the_read_took_nothing() -> None:
    # Behind a given-name title the reserve needs one name piece, so
    # "changes no suffix reading" was the only thing between 'Sir abdul
    # J. V' and a join that turned the V from a name word into the
    # suffix (#369 had joined it). Since #614 nothing re-reads the
    # suffix after the join: the run, read once before it, takes
    # nothing, and the pair joins with the V still the family -- the
    # suffix reading the equality guarded against no longer arises
    # (decisions/P5, 2026-10-07).
    n = parse("Sir abdul J. V")
    assert (n.given, n.family, n.suffix) == ("abdul J.", "V", "")
    n = parse("Sir John J. V")
    assert (n.middle, n.family, n.suffix) == ("J.", "V", "")


def test_the_chain_and_the_walk_stop_where_the_peel_begins() -> None:
    # #424: the third and fourth sites that asked "is this a suffix?"
    # with the initial-vetoed test. Each reads as its ordinary twin
    # ('John Smith V', 'John Smith Ma') reads.
    for text, family, suffix in (
            ("John van der Berg V", "van der Berg", "V"),
            ("John van der Berg X", "van der Berg", "X"),
            ("abdul van der Berg V", "van der Berg", "V"),
            # MOVED by #289, not deleted: 'Ma' is Title-case in a
            # mixed-case name, so it now leans SURNAME, the
            # run's read leaves it a name word (S2's read ahead of the
            # chain since #614, its re-ask before that), so the chain
            # takes it into the particle run (decisions/S6).
            ("John van der Berg Ma", "van der Berg Ma", "")):
        n = parse(text)
        assert (n.family, n.suffix) == (family, suffix), text
    n = parse("Jane Doe née Jones Smith V")
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
    #
    # MOVED by #289, ACCEPTED COST (decisions/S6): 'MA' is written
    # in capitals inside a mixed-case name, so it now leans CREDENTIAL
    # and the caps lean makes it reachable where the count alone was
    # not -- the lean ends the chain's re-ask with no words to spare,
    # where the count would not have. This was listed as staying
    # fix(#424)'s and measured not to: 1.4.0 read "von Berg", "MA".
    n = parse("Freiherr von Berg MA")
    assert (n.title, n.family, n.suffix) == ("Freiherr", "von Berg", "MA")
    # the numeral keeps its three pieces behind the same word, and the
    # chain is the one name piece. Since #718 a one-letter numeral
    # needs words to spare (rules/S10) and a title is none, so behind
    # one name word the V is a name word: the chain takes it as P2
    # takes any, where 'Dr. Smith V' gives it the family
    n = parse("Freiherr von Richthofen V")
    assert (n.given, n.family, n.suffix) == ("", "von Richthofen V", "")
    n = parse("Dr. Smith V")
    assert (n.given, n.family, n.suffix) == ("Smith", "V", "")
    # both stops read the TRAILING word, so an acronym with the
    # numeral behind it is not the word either fork asks about and
    # stays maiden text -- and so does a numeral with an acronym
    # behind it ('Jane Doe nee Smith V MA' keeps maiden 'Smith V')
    n = parse("Jane Smith née Jones Ma V")
    assert (n.maiden, n.suffix) == ("Jones Ma", "V")
    n = parse("Jane Doe nee Smith V MA")
    assert (n.maiden, n.suffix) == ("Smith V", "MA")


def test_the_numeral_fork_fires_on_the_last_piece_only() -> None:
    # The shared peel's own contract, pinned at the stage that owns
    # it: a numeral with a suffix behind it is a name word, for an
    # ordinary given name and the bound pair alike.
    for text, family in (("John Smith V Jr", "V"),
                         ("abdul Smith V Jr", "V")):
        n = parse(text)
        assert (n.family, n.suffix) == (family, "Jr")


@pytest.mark.parametrize("text, fragment", [
    # rules/S10's Title-case lean, worded for what declined the numeral
    ("John Smith Vi", "written in Title case, which leans to the name"),
    ("Jane Doe nee Smith Vi", "written in Title case it leans to the name"),
    # one-letter, declined for want of words to spare, as #718 words it
    ("John V", "the name has no other word to spare"),
    # a declined numeral a credential run in front then takes is the
    # run's absorbed name word (rules/S8), not a numeral read as a name
    ("John Smith III Vi", "follows a credential"),
    ("John Smith PhD Vi", "follows a credential"),
])
def test_a_declined_numeral_is_reported_for_what_declined_it(
        text: str, fragment: str) -> None:
    # #752's review: the Title-case pick first took #718's "no other
    # word to spare" wording, and one a run took read "as a suffix
    # rather than a generational suffix"
    details = [a.detail for a in parse(text).ambiguities]
    assert any(fragment in d for d in details), (text, details)
    assert not any("rather than a generational suffix" in d
                   and "suffix rather" in d for d in details), details


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
    "Sir", "Swami", "Pope", "الشيخ", "Dr.", "Mr.", "Mr. Sir", "Sir Dr.",
    "Sir and Dame", "Mr. and Mrs.", "Swami and Mrs"])
def test_the_p5_licence_and_h1_read_a_title_run_the_same_way(
        title: str) -> None:
    # The licence's one invariant, as a contract: P5 lifts the reserve
    # behind a title run exactly when H1 keeps the one word after that
    # run a given name. Both ask _run_addresses_by_given, of the
    # LEADING run, for the whole run's key or the run's last word's
    # (#489); if either side's read drifted, a run P5 licensed that H1
    # then read as title-plus-family would hand the joined pair to the
    # family. So "no family" must agree, run by run.
    assert (parse(f"{title} John").family == "") == \
        (parse(f"{title} abdul rahman").family == "")
    # The same invariant with a trailing title behind the pair, and
    # stated the way rules/H5's transparency clause states it
    # rather than as agreement between the two halves: `X Prof.` is
    # `X` plus a title, so adding the title moves NEITHER field. That
    # is what discriminates. Comparing the two spellings' "no family"
    # to each other passes under the composite keying this replaced,
    # where H1 read the TITLE role -- both ends of the name by then --
    # as one run: `sir prof` addresses by neither word, so both
    # spellings handed their name words to the family together and
    # agreed while both were wrong. Pinned by mutation: restore the
    # whole-`titles` key and every given-name-title row below fails
    # here (2026-09-09).
    #
    # The NICKNAME spellings are here because the first fix for this
    # split the run at the first token of another role, which a
    # nickname written in front of the titles satisfies -- so
    # "'Smitty' Sir Jones Prof." found no leading run and read family
    # 'Jones' where "'Smitty' Sir Jones" reads given. What decides is
    # the name WORD, H1's rationale saying in as many words that a
    # nickname beside it does not decide the reading, and only these
    # rows can tell the two splits apart.
    for suffixless in (f"{title} John", f"{title} abdul rahman",
                       f"'Smitty' {title} John",
                       f"'Smitty' {title} abdul rahman"):
        plain, titled = parse(suffixless), parse(f"{suffixless} Prof.")
        assert (titled.given, titled.family) == (plain.given, plain.family)


# The first three reach the chain loop and decline inside it: the piece
# after the particle is a suffix, so the scan never advances and merge_pieces
# is a no-op -- nothing was chained, no fork taken. They are spelled with
# a title that is ALSO a particle ('Do', 'St'), because that is what
# still puts an ambiguous particle off the name's leading position since
# #367. The last three are the same strings with a plain title, which
# now decline one step earlier -- the particle IS the leading name piece
# and the loop skips it -- and are kept so the pair stays visible: two
# different reasons, one output, and neither may start reporting a fork.
@pytest.mark.parametrize("text", [
    "Do Van Jr.", "Do Van MD", "St Van Jr.",
    "Dr. Van Jr.", "Dr. Van MD",
])
def test_no_op_prefix_chain_is_not_a_fork(text: str) -> None:
    assert not _overlap_parser().parse(text).ambiguities


def test_dr_do_jr_reports_the_word_left_standing() -> None:
    """Since #489 this one reports from somewhere else entirely.

    It was the sixth row of the parametrization above until the
    2026-09-09 review, where carrying it made that test assert "no
    fork EXCEPT this one" and so stopped saying the thing it exists
    to say. The leading peel's floor gives 'Do' back as the name word
    (the run stood in front of nothing but 'Jr.'), so 'Dr. Do Jr.'
    reads family 'Do', suffix 'Jr.' and H4's title half claims the
    lone name word, which happens to be title vocabulary here. That
    report is about the word left standing, not about a chain that
    never chained -- PARTICLE_OR_GIVEN is still absent, which is what
    the kind tuple below pins.
    """
    n = _overlap_parser().parse("Dr. Do Jr.")
    assert (n.family, n.suffix) == ("Do", "Jr.")
    assert tuple(a.kind for a in n.ambiguities) == (
        AmbiguityKind.TITLE_OR_NAME,)


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
    acronym = parse("JOHN SMITH MA").ambiguities[0].detail
    assert "periods" in acronym and "post-nominal" in acronym

    numeral = parse("John Smith V").ambiguities[0].detail
    assert "periods" not in numeral
    assert "numeral" in numeral and "initial" in numeral


def test_parser_matches_uses_its_own_config() -> None:
    p = Parser(lexicon=Lexicon.default().add("moff", kind="title"))
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


def test_revise_derives_suffix_entries_from_the_values_commas() -> None:
    # A suffix value's entry structure is the value's own commas, read
    # by rules/R1's pass after the named role is forced (#511). The
    # sub-parse of a bare "MD PhD" reads a title and a family name and
    # so joins nothing on its own; revise() runs the pass again over
    # the forced roles, where the two share a comma bucket.
    p = Parser()
    n = p.parse("John Smith")
    assert p.revise(n, suffix="MD PhD").suffix == "MD PhD"
    assert p.revise(n, suffix="MD, PhD").suffix == "MD, PhD"
    # The Ph. D. MERGE is a head-position rule (#371) with no head to
    # consult in a field value, and it still does not fire here; the
    # ENTRY pass joins the pair for the reason it joins MD and PhD.
    # Supersedes the 2026-08-31 acceptance of 'Ph., D.' on this path
    # (decisions/phd-merge).
    assert p.revise(n, suffix="Ph. D.").suffix == "Ph. D."
    # a dash is a token under the default policy, and a suffix word
    # once the role is forced
    assert (p.revise(n, suffix="MD PhD - FACS Fellow").suffix
            == "MD PhD - FACS Fellow")


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
    # The other direction, and the one that made rules/R2's
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


def test_revise_recomputes_the_connective_mark_in_both_directions(
) -> None:
    # The mark says a connective stands in a part with nothing to
    # join, which is a fact about the PART -- so the harvest that
    # splices a sub-parse's tokens into one field invalidates it both
    # ways, exactly as it does the particle mark above (rules/R3,
    # #461).
    p = Parser()
    lone = p.parse("Juan de y")
    assert lone.initials() == "J. y."
    # STALE: the marked 'y' lands beside a name word
    widened = p.revise(lone, family="y Garcia")
    assert widened.initials() == "J. G."
    # MISSING: a connective revised into a part of its own
    narrowed = p.revise(p.parse("Juan Velasquez y Garcia"), family="y")
    assert narrowed.initials() == "J. y."
    # and the identity revise round-trips, which is the property the
    # particle-mark tests above pin for R2
    again = p.revise(lone, family=lone.family)
    assert (again.family, again.initials()) == (lone.family,
                                                lone.initials())


def test_revise_writes_a_connective_mark_the_sub_parse_did_not(
) -> None:
    # The MISSING direction that role-forcing alone cannot produce,
    # and the one input shape that does: the sub-parse of 'and y'
    # reads 'and' as the given name and 'y' -- a particle under this
    # caller's vocabulary -- as an all-particle family, so R2's mark
    # is what the sub-parse writes on it. Forcing both into one field
    # makes that part no longer all-particle, so R2's mark is cleared
    # and #461's has to be written in its place, by the recompute
    # rather than by any stage. Without it the 'y' carries no mark at
    # all, drops as an ordinary family particle, and the field and
    # the view disagree again.
    p = Parser(lexicon=Lexicon.default().add("y", kind="particle"))
    revised = p.revise(p.parse("John Smith"), family="and y")
    assert revised.family == "and y"
    assert revised.initials() == "J. a. y."
    marks = {t.text: t.tags for t in revised.tokens
             if t.role is Role.FAMILY}
    assert UNJOINED_CONJUNCTION_TAG in marks["y"]
    assert UNJOINED_TAG not in marks["y"]


def test_revise_keeps_r2s_precedence_over_the_connective_mark(
) -> None:
    # The recompute mirrors the pipeline walk's `elif`, and this is
    # the row where the two marks would otherwise both be written:
    # 'de y' under a vocabulary that makes 'y' a particle is an
    # all-particle part, so R2's mark readmits every word of it --
    # the connective included -- and #461's is not written there. The
    # rendered answer is the same either way, which is why this
    # asserts the TAGS: the contract is that one mark is written, and
    # no rendered view tells the two apart.
    p = Parser(lexicon=Lexicon.default().add("y", kind="particle"))
    revised = p.revise(p.parse("John Smith"), family="de y")
    assert revised.initials() == "J. d. y."
    y = [t for t in revised.tokens if t.text == "y"][0]
    assert UNJOINED_TAG in y.tags
    assert UNJOINED_CONJUNCTION_TAG not in y.tags


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


def test_revise_round_trips_a_rendered_suffix() -> None:
    # the view renders entries comma-joined and a comma is what the
    # pass reads, so a name's own suffix revises back to itself --
    # the three shapes #511 reported, none of which round-tripped,
    # and a fourth from the corpus -- the only value in the set whose
    # own suffix CONTAINS A COMMA ('Jr., Col. Ret'), so it is the one
    # pinning that the pass does not over-join two entries into one
    p = Parser()
    for text in ("John Smith MD PhD", "John Smith, Ph. D.",
                 "Doe, John, MD PhD - FACS Fellow",
                 "Andrew Perkins, Jr., Col. (Ret)"):
        n = p.parse(text)
        assert p.revise(n, suffix=n.suffix).suffix == n.suffix, text


def test_revise_leaves_a_policy_delimiter_unparted_without_a_tail_segment() -> None:
    # The pinned limit, and the rule behind it: a configured delimiter
    # core is dropped -- and so parts entries -- only on a TAIL
    # segment, which a value gets only where its own words read as a
    # name. A run of post-nominals has none, with or without a comma
    # of its own, so the core stays a word; a value that reads as a
    # name does part. The round-trip is unaffected because the
    # whole-name view already rendered that boundary as a comma.
    p = Parser(policy=Policy(extra_suffix_delimiters=frozenset({" | "})))
    n = p.parse("Doe, John, MD PhD | FACS")
    assert n.suffix == "MD PhD, FACS"
    assert p.revise(n, suffix="MD PhD | FACS").suffix == "MD PhD | FACS"
    assert p.revise(n, suffix="MD, PhD | FACS").suffix == "MD, PhD | FACS"
    assert p.revise(n, suffix=n.suffix).suffix == "MD PhD, FACS"
    assert (p.revise(n, suffix="John Doe, MD | FACS").suffix
            == "John Doe, MD, FACS")


def test_revise_reads_a_glued_honorific_on_its_own() -> None:
    # The docstring's "classified ON ITS OWN" limit, on the one corpus
    # name of 1117 whose suffix does not revise back to itself after
    # #511 (measured 2026-09-06). The whole-name parse keeps 'J.씨' one
    # glued suffix token; the sub-parse of the bare value peels the
    # honorific off the initial, and the entry pass then joins the
    # two it made. Right entries, the spurious comma of before gone
    # ('씨, J., 씨'), one word read differently in the value than in
    # the name. Honorific peeling is a W-rule question, not R1's.
    p = Parser()
    n = p.parse("김민준씨, J.씨")
    assert n.suffix == "씨, J.씨"
    assert p.revise(n, suffix=n.suffix).suffix == "씨, J. 씨"


#: The suffix-bearing corpus names whose suffix does not revise back
#: to itself: the honorific peel pinned just above, and since
#: 2026-09-10 its stop-bearing spelling, which parses to the same
#: suffix with a stop on the first word ('씨., J.씨' revising to
#: '씨., J. 씨'). One limit, two writings of one name -- the stop
#: rides on 씨 and reaches neither the sub-parse's peel nor the entry
#: join. Named here so the guard below fails on a NEW exception and
#: not on the known one.
#: 'John Smith, Dr. J.씨' joined 2026-10-06 (#613's /simplify): the
#: comma's own decision now reads its part as postnominal, so the whole
#: name leaves 'J.씨' glued where the hand copy had peeled it -- the
#: same limit, characterized by the test below.
_HONORIFIC_PEEL = frozenset({"김민준씨, J.씨", "김민준씨., J.씨",
                             "John Smith, Dr. J.씨"})
#: The second known limit (2026-10-04, #601/#602): a suffix that holds
#: a maiden marker the whole name left a word -- in a tail part, or
#: taken into #602's credential run behind a credential -- and that
#: the value's own sub-parse consumes mid-value, as revise() documents.
#: 'Smith, John, MD - née Jones Smith' left it in #889: the built-in
#: hyphen parts its suffix ('MD, née Jones Smith'), whose sub-parse
#: reads the marker as a word too.
_MARKER_IN_SUFFIX = frozenset({"Jane Doe PhD nee Smith",
                               "Smith, John, PhD née Jones"})


def _suffix_bearing_corpus_names() -> list[str]:
    from ._differential_fixtures import _CORPUS_NAMES
    p = Parser()
    return [n for n in _CORPUS_NAMES
            if p.parse(n).suffix and n not in _HONORIFIC_PEEL
            and n not in _MARKER_IN_SUFFIX]


def test_the_known_round_trip_exceptions_are_one_limit() -> None:
    # What makes the two spellings ONE limit rather than two names
    # somebody enrolled: each one's parsed suffix carries a word that
    # ENDS in a listed honorific_tails entry without BEING one ('J.씨'
    # ends in 씨), which is exactly the shape the sub-parse peels and
    # the whole-name parse leaves glued. A genuinely different
    # round-trip failure added to the frozenset by the same gesture
    # fails here rather than riding in on the exemption. The
    # characterization selects the members and nothing else in the
    # suffix-bearing corpus (two, measured 2026-09-10; three since
    # 2026-10-06).
    p = Parser()
    tails = Lexicon.default()._sets.honorific_tails

    def ends_in_a_tail_without_being_one(name: str) -> bool:
        return any(word not in tails
                   and any(word.endswith(tail) for tail in tails)
                   for word in p.parse(name).suffix.split())

    assert all(ends_in_a_tail_without_being_one(n) for n in _HONORIFIC_PEEL)
    assert not [n for n in _suffix_bearing_corpus_names()
                if ends_in_a_tail_without_being_one(n)]
    # the marker limit, characterized the same way: the parsed suffix,
    # read ON ITS OWN, takes a maiden clause -- its marker the whole
    # name left a word, and the value's sub-parse consumes. Not every
    # suffix holding a marker word: 'Jane Doe Jr. nee Smith' renders
    # 'Jr. nee Smith', whose own parse reads 'Jr.' as a leading title
    # (H2), so the marker stays a word there too and the value
    # round-trips (measured 2026-10-04).
    def takes_a_clause_on_its_own(name: str) -> bool:
        return bool(p.parse(p.parse(name).suffix).maiden)

    assert all(takes_a_clause_on_its_own(n) for n in _MARKER_IN_SUFFIX)
    assert not [n for n in _suffix_bearing_corpus_names()
                if takes_a_clause_on_its_own(n)]


def test_the_suffix_bearing_corpus_is_not_empty() -> None:
    # 367 on 2026-09-06; a floor, so a filter that empties the
    # parametrization below fails here instead of skipping there
    assert len(_suffix_bearing_corpus_names()) > 300


@pytest.mark.parametrize("name", _suffix_bearing_corpus_names())
def test_a_rendered_suffix_revises_back_to_itself(name: str) -> None:
    # The #511 property over the corpus rather than by example, because
    # revise() is off the differential gate's compare path and a change
    # to group's marks, delimiter_cores or the entry predicate could
    # reopen it with the gate green and the four pins above passing.
    p = Parser()
    n = p.parse(name)
    assert p.revise(n, suffix=n.suffix).suffix == n.suffix


def test_revise_keeps_the_sub_parses_within_piece_mark() -> None:
    # The forcing keeps the sub-parse's tags: a "joined" made WITHIN a
    # piece (the Ph. D. merge, mid-value where the head rule lets it
    # fire) is role-blind and right for every role (decisions/R1's
    # #436 DECLINED list), and a draft that cleared it with the role
    # lost it on every non-suffix value. For a suffix value the pass
    # writes the marks itself ('Ph. D. MD' sub-parses with none), so
    # nothing there depends on the sub-parse's own. The between-piece
    # mark a sub-parse leaves on a token forced to another role
    # predates #511; on a ParsedName only the suffix string view reads
    # the tag.
    p = Parser()
    r = p.revise(p.parse("John Smith"), family="John Ph. D. Smith")
    family = r.tokens_for(Role.FAMILY)
    assert [t.text for t in family] == ["John", "Ph.", "D.", "Smith"]
    assert "joined" in family[2].tags
    assert r.family == "John Ph. D. Smith"
    s = p.revise(p.parse("John Smith"), suffix="Ph. D. MD")
    assert s.suffix == "Ph. D. MD"
    assert [("joined" in t.tags) for t in s.tokens_for(Role.SUFFIX)] == [
        False, True, True]
    # the stale between-piece mark, and that no ParsedName view reads it
    stale = p.revise(p.parse("John Smith"), family="Jones MD PhD")
    fam = stale.tokens_for(Role.FAMILY)
    assert "joined" in fam[2].tags
    assert stale.family == "Jones MD PhD"
    assert stale.family_base == stale.family


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
    # decision, not accident: halfwidth kana is katakana (#594), and a
    # name written wholly in katakana keeps the declared order
    # (rules/W4) as マイケル・ジャクソン does -- KATAKANA has no
    # script_orders entry -- while the dot divides the tokens regardless
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
        p.parse("小明")   # zh pack active, 小 unmatched by vocabulary ->
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
    assert p.parse("小明").family == "小"          # one token: consulted
    n = p.parse("小明 日月")                        # already divided
    assert (n.family, n.given) == ("小明", "日月")
    assert p.parse("Dr 小明").family == "小"       # a title is not a split


def test_a_segmenter_split_reaches_the_fields() -> None:
    # end to end: the sub-slices the stage makes are ordinary tokens
    # from there on, so the pack's family-first order reads them like
    # any vocabulary split, and a low-confidence answer surfaces
    def two(text: str) -> Segmentation | None:
        return Segmentation((1,), confidence=0.5)

    p = parser_for(locales.get("zh"), base=Parser(segmenter=two))
    n = p.parse("小明")
    assert (n.family, n.given) == ("小", "明")
    assert [a.kind for a in n.ambiguities] == [AmbiguityKind.SEGMENTATION]

    # two cuts, three pieces -- and the token indices the comma
    # structure recorded still name the right words afterwards
    def three(text: str) -> Segmentation | None:
        return Segmentation((1, 2))

    q = parser_for(locales.get("zh"), base=Parser(segmenter=three))
    n3 = q.parse("Dr 小明日, Jr.")
    assert (n3.title, n3.family, n3.given, n3.middle, n3.suffix) == (
        "Dr", "小", "明", "日", "Jr.")


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
#: behind a comma is post-comma text: rules/M2's Except bullet "In the
#: given part after a family comma, in a part after a suffix comma, and
#: behind a title, a suffix word or a connective, the marker is an
#: ordinary word", decisions/M2), and no marker already present.
_LATIN = re.compile(r"^[\x00-\u024f]*$")


def _clause_free_latin_corpus_names() -> list[str]:
    from nameparser import DEFAULT_NICKNAME_DELIMITERS
    from nameparser._pipeline._vocab import maiden_marker_run
    from nameparser.config._compiled import MAIDEN_MARKERS

    from ._differential_fixtures import _CORPUS_NAMES
    # "Does this name already carry a marker" is the parser's own
    # question, so it is asked with the parser's own predicate rather
    # than by word membership. A word test cannot see a PHRASE entry:
    # no word of 'z domu' is a marker, so 'Maria Kowalska z domu Nowak'
    # sat in this corpus with a maiden clause of its own and the
    # appended one was not the only variable
    # (mechanisms.md#ONE-PREDICATE-PER-QUESTION -- a test guard is as
    # able to write the mirroring condition as a stage is).
    #
    # The strip stays, and runs BEFORE the predicate: a marker glued to
    # a delimiter character is still a marker, and neither the
    # predicate nor the vocabulary strips a bracket, so '(geb.' must
    # lose it before being asked. Stripping only the period admitted
    # every corpus name that brackets its marker, and once rules/M3
    # read such a clause as the maiden name, six of them had a maiden
    # clause of their own. The strip turns away TEN names in all: those
    # six, plus four that M3 declines and that would have been safe to
    # keep -- the one-word '(Nee)', '(Nee) (Jones)' and '(née)', and
    # '(née Jr.)', which S1 takes before M3 sees it. Textual, and so
    # deliberately conservative in exactly that direction.
    #
    # Every count in this comment quantifies over the corpus, so one
    # added corpus row falsifies it silently. Recount rather than
    # adjust:
    # The body must sit flush left: `python -c` compiles it as a module,
    # so an indented first line raises IndentationError on paste.
    # uv run python -c "
    # import re, sys; sys.path.insert(0, 'tests')
    # from nameparser import DEFAULT_NICKNAME_DELIMITERS as D
    # from nameparser._pipeline._vocab import maiden_marker_run as run
    # from nameparser.config._compiled import MAIDEN_MARKERS as M
    # from v2._differential_fixtures import _CORPUS_NAMES
    # base = [n for n in _CORPUS_NAMES if re.match(r'^[\x00-\u024f]*$', n) and ',' not in n]
    # strip = ''.join({c for p in D for c in p}) + '.'
    # words = lambda n, f: [f(w) for w in n.split()]
    # keep = lambda f: [n for n in base if not any(w in M for w in words(n, f))]
    # old = keep(lambda w: w.lower().rstrip('.'))
    # new = keep(lambda w: w.lower().strip(strip))
    # ws = lambda n: words(n, lambda w: w.lower().strip(strip))
    # pred = [n for n in base if not any(run(ws(n)[i:], M) for i in range(len(ws(n))))]
    # print(len(old), len(new), len(pred), sorted(set(old) - set(new)), sorted(set(new) - set(pred)))"
    #
    # Delimiter characters come from the shipped set rather than a
    # literal, so a pair added there cannot quietly reopen this.
    strip = "".join({ch for pair in DEFAULT_NICKNAME_DELIMITERS
                     for ch in pair}) + "."

    def marked(name: str) -> bool:
        words = [word.lower().strip(strip) for word in name.split()]
        return any(maiden_marker_run(words[i:], MAIDEN_MARKERS)
                   for i in range(len(words)))

    return [name for name in _CORPUS_NAMES
            if _LATIN.match(name) and "," not in name and not marked(name)]


def test_the_clause_free_corpus_is_not_empty() -> None:
    """The invariant below is parametrized over a FILTERED corpus, and
    an empty parametrization passes as a skip rather than failing --
    the shape #329 left behind. The filter has been widened twice
    already -- the delimiter strip, then the move from word
    membership to the marker predicate, which a phrase entry made
    necessary -- and the one-liner in that filter's comment recounts
    every stage: 646 names before either, 636 after the strip, 632
    once the predicate decides. Recounted 2026-08-27 by pasting it,
    and recounted AGAIN in the review round, which is the point of
    shipping the one-liner: the first recount was taken before the
    last of #445's rules-corpus rows existed and came out one low at
    every stage. #445 adds five rows in all, of which three clear the
    marker predicate ('Garcia', 'Smith', 'Smith (Jones)'), so every
    stage moves by three -- and the first two figures were already
    one low before any of it, a corpus row having landed without the
    recount this comment asks for. So the floor is what says a future
    widening emptied it. Deliberately far below today's count: this
    asks whether the filter still selects a corpus, not what the
    corpus holds."""
    assert len(_clause_free_latin_corpus_names()) > 100


@pytest.mark.parametrize("name", _clause_free_latin_corpus_names())
def test_a_maiden_clause_changes_nothing_else(name: str) -> None:
    """The grouping rules count and join only the words that remain
    once the marker and the maiden name leave (rules/M2, #418), so
    appending a clause adds a maiden name and moves no other field --
    wherever the appended marker counts at all.

    Over the corpus rather than by example, because the defect was an
    appended-clause shape on names that are otherwise ordinary ('John
    e Smith', 'Lt.Gov. juan e garcia'), which no corpus carries in
    that form and which the differential gate therefore cannot see.
    Before the marker pass moved ahead of the joins, seven of these
    names failed this.

    Whether the marker counts is M2's head rule (#601): the word
    straight before it -- the base name's last word, a nickname aside
    -- must be a name word, which a word of the leading title run, a
    word of the unambiguous suffix vocabulary and a connective are
    not. Where the clause is taken the assertion is the one above;
    where it is not ('Smith Jr.', 'Coach', 'John Smith PhD') the word
    before the marker must be one of those refusals, so neither half
    of the split can pass vacuously. A corpus name that parses to no
    name word ('', '(', '()') has nothing before the marker and is
    skipped.

    One class of name moves ON PURPOSE, and is asserted MOVING rather
    than skipped: rules/M4 makes the clause decide a name that
    holds exactly one name word, because a marker announces a former
    surname and only means anything beside a current one. The flip is
    exactly given -> family with every other field standing still --
    which is the whole of what #445 changed, checked over the corpus
    rather than at the rows cases.py carries.

    The `flips` predicate below is a second reading of M4's guard, and
    that is a maintenance cost taken deliberately rather than the
    silent-drift hazard it resembles: it fails LOUDLY in both
    directions -- narrow M4 and the flip assertion fails, widen it and
    the stands-still assertion does. What it buys is the carve-out
    witness: dropping the `vocab:bound-given` carve-out would stop
    failing here on 'abdul', and the corpus is the only place that
    name is asked.
    """
    base = parse(name)
    if not (base.given or base.middle or base.family
            or base.title or base.suffix):
        pytest.skip("nothing before the marker at all: M2 leaves it a word")
    with_clause = parse(name + " née Jones")
    # The head rule, read both ways. Where the appended marker takes
    # nothing, the word straight before it -- the base name's last
    # word, a nickname aside -- must be one of the rule's refusals: a
    # title, a word of the UNAMBIGUOUS suffix vocabulary (an ambiguous
    # member or a numeral the peel happens to take is none) or the
    # merged credential's continuation, or a connective. A decline for
    # any other reason fails, and so does a taken clause that moves a
    # field, below.
    words = [t for t in base.tokens if t.role is not Role.NICKNAME]
    last = words[-1] if words else None
    if with_clause.maiden == "":
        assert last is not None and (
            last.role is Role.TITLE
            or ("vocab:suffix" in last.tags and "initial" not in last.tags)
            or (last.role is Role.SUFFIX and "joined" in last.tags)
            or "conjunction" in last.tags), (
            f"{name!r}: the appended marker took nothing, but the word "
            f"before it, {last.text if last else None!r}, is none of "
            f"rules/M2's refusals")
        return
    # M4's guard, read off the base parse: one GIVEN token, no other
    # name word, no title (a titled name is H1's), and neither
    # carve-out tag. Tokens rather than fields because the rule counts
    # tokens -- a joined 'de la Vega' in `given` is one field and
    # three of them.
    givens = [t for t in base.tokens if t.role is Role.GIVEN]
    flips = (len(givens) == 1 and not base.middle and not base.family
             and not base.title
             and not ({"initial", "vocab:bound-given"} & givens[0].tags))
    assert with_clause.maiden == "Jones"
    moved = ("title", "middle", "suffix", "nickname") if flips else (
        "title", "given", "middle", "family", "suffix", "nickname")
    if flips:
        assert (with_clause.family, with_clause.given) == (base.given, ""), (
            f"{name!r}: one name word beside a maiden clause is the "
            f"family name (rules/M4), but it reads family "
            f"{with_clause.family!r} / given {with_clause.given!r}")
    for field in moved:
        assert getattr(with_clause, field) == getattr(base, field), (
            f"{name!r}: {field} reads {getattr(base, field)!r} alone and "
            f"{getattr(with_clause, field)!r} with a maiden clause")


def test_a_phrase_marker_outranks_the_word_it_starts_with() -> None:
    # Longest first, and the row cases.py cannot hold: a Case carries a
    # Policy or a Locale, never a Lexicon, so the one marker fork that
    # needs two entries at once lives here.
    #
    # 'geb' ships and 'geb von' is the caller's addition. The phrase
    # must win where it matches -- maiden 'Braun', the particle being
    # part of the marker -- and the bare word must still match
    # everywhere else. Shortest-first would take 'geb' in both and read
    # the first as maiden 'von Braun', which is also what the default
    # vocabulary reads, so the control below is what makes the first
    # assertion mean anything.
    configured = Parser(lexicon=Lexicon.default().add(
        "geb von", kind="birth_marker"))
    assert configured.parse("Jane Smith geb von Braun").maiden == "Braun"
    assert configured.parse("Jane Smith geb Braun").maiden == "Braun"
    assert parse("Jane Smith geb von Braun").maiden == "von Braun"


def test_the_catalan_recipe_unmarks_the_link_for_one_case_names() -> None:
    """rules/P8's per-caller answer for Catalan and Polish data
    (#397 second review), pinned rather than described.

    `i` ships in the MARKED subset, so a name written wholly in one
    case reads it as an initial and reports the fork. A caller whose
    data is Catalan knows better, and the knob the rule names is
    `add("i", kind="conjunction", may_be_initial=False)` -- which
    leaves the letter
    a connective and takes the one-case fork out of its way. The
    prose said so; nothing ran it.
    """
    catalan = Parser(
        lexicon=Lexicon.default().add(
            "i", kind="conjunction", may_be_initial=False))
    for text in ("JOSEP CAROD I ROVIRA", "josep carod i rovira"):
        name = catalan.parse(text)
        assert name.family == text.split(" ", 1)[1]
        assert name.ambiguities == ()
    # the three things the recipe does NOT change, and they are what
    # make it safe to hand a Catalan user. The link with nothing on
    # its right is still the generation it also spells ...
    kept = catalan.parse("JOHN QUINCY SMITH I")
    assert kept.suffix == "I"
    assert kept.family == "SMITH"
    # ... P3's three-word carve-out still leaves a lone letter a name
    # word ...
    assert catalan.parse("JOHN I SMITH").middle == "I"
    # ... and no report is emitted anywhere, the fork the recipe
    # removes being the only one these names raised
    assert catalan.parse("JOHN I SMITH").ambiguities == ()
    assert catalan.parse("JOHN QUINCY SMITH I").ambiguities == ()


_NFD_ROWS = [
    # the period-abbreviation shape (rules/H2, #H5), in each slot
    "Dr. inž. Janez Novak",
    "inž. Janez Novak",
    "prof. dr. inž. Janez Novak",
    "Janez Novak, univ. dipl. inž.",
    "Novak, inž. Janez",
    "Smith, inž. Ž.Š.",
    # the comma shapes nameparser/AGENTS.md asks of every comma grid
    ", inž.",
    "(Bob), inž.",
    # paired initials (rules/C5)
    "Janez Novak, Ž.Š.",
    "Janez Novak, Ž.Š., Jr.",
    # the all-caps credential shape: default policy reads it in the
    # part after a comma
    "Janez Novak, ŽŠČ",
    "Janez NOVAK, ŽŠČ",
    # ... and in every slot under CapsSuffixes.EVERYWHERE
    "Janez Novak ŽŠČ",
    "Smith, John ÉS",
    # the two-letter caps word is a PAIR of initials, and counts
    # letters, not code points (review of the first fix)
    "John Smith, MÁ",
    "John Smith, ŽŠ",
    # the rules name Greek and Cyrillic as well as Latin
    "Επίκ. Νίκος Παπαδόπουλος",
    "Иван Петров, ЙЁЖ",
    # these four read the same even with every shape regex reverted
    # (measured), so they pin nothing but parity
    "Janez Novak inž.",
    "Janez Novak, Ž.Š.Č.",
    "Janez Novak, Žž.Šš.",
    "Smith, Ž.Š. Jones",
    # #665: a period-marked initial (`\w\.`) beside a connective, in
    # each slot and comma shape -- a lone one read alike before the fix
    "É. y É. Smith",
    "Й. John Smith",
    "Ana É. y Luis",
    "Smith, É. y É.",
    ", É. y É.",
    "(Bob), É. y É.",
    # ... and the one-letter connective written in two code points:
    # three words (P3's carve-out keeps it a name word), four words
    # (it joins), one case, and after a comma
    "John й Smith",
    "JOHN Й SMITH",
    "john й smith",
    "Ivan й Petrov Sidorov",
    "Smith, John й Jones",
    # ... and the veto on scripts that write no initials (#320), asked
    # of the composed spelling too: decomposed hangul is conjoining
    # jamo, outside every _NO_INITIALS range, so composing the initial
    # shape alone made a decomposed '씨.' an initial (a title or a
    # given name). Spaced or after a comma, since an UNSPACED
    # decomposed hangul name is not split (docs/usage.rst) and so has
    # no composed twin to match
    "김민준, 씨.",
    "김 민준 씨.",
    "김 민준, 씨.",
    ", 씨.",
    "김. 민준",
]
_NFD_POLICIES = [
    Policy(),
    Policy(name_order=FAMILY_FIRST),
    Policy(name_order=FAMILY_FIRST_GIVEN_LAST),
    Policy(unlisted_caps_suffixes=CapsSuffixes.EVERYWHERE),
]


def _composed_roles(parser: Parser, text: str) -> dict[str, str]:
    return {k: unicodedata.normalize("NFC", v)
            for k, v in parser.parse(text).as_dict().items()}


def _composed_reading(parser: Parser, text: str) -> tuple[object, ...]:
    """The roles, the reports' kinds and initials(), composed: #665's
    `John й Smith` differed in its report as well as its fields."""
    name = parser.parse(text)
    return (_composed_roles(parser, text),
            [a.kind for a in name.ambiguities],
            unicodedata.normalize("NFC", name.initials()))


@pytest.mark.parametrize("policy", _NFD_POLICIES,
                         ids=["default", "family-first", "family-first-given-last",
                              "caps-everywhere"])
@pytest.mark.parametrize("text", _NFD_ROWS)
def test_a_decomposed_abbreviation_reads_as_its_composed_twin(
        text: str, policy: Policy) -> None:
    """#652: the abbreviation shape rules saw a combining mark as the
    end of the word (not \\w), so `inž.` written i, n, z, U+030C, '.'
    was not an abbreviation and `Dr. inž. Janez Novak` made it the
    given name, and the caps shape's isalpha() refused `ŽŠČ` the same
    way. Output keeps the encoding written, so both are compared
    composed. Recorded negative control, measured 2026-10-12 against
    04cc0814's nameparser/ (the package checked out from that commit,
    these tests on top): 22 rows x 4 policies = 88 twin cases, of
    which 58 fail (14 rows under all four policies, `Janez Novak ŽŠČ`
    and `Smith, John ÉS` under caps-everywhere only), and the 3 direct
    tests below fail too: 61 of 91. The four parity rows and the two
    two-letter rows pass there; the two-letter rows exist for the caps
    fix's own length count, which counted code points the first time
    (`John Smith, MÁ` read as a pair composed and a credential
    decomposed, found in the review of 08c0dd60).

    #665 added sixteen rows and compares kinds and initials() too.
    Recorded control, measured 2026-10-13 against f9b2b81c's
    nameparser/: 38 rows x 4 policies = 152 twin cases plus the four
    direct tests, of which 41 fail -- the six initial rows under all
    four policies (24; the same 24 with only `is_initial_shaped`'s
    compose reverted), the three-word `й` rows (12; `_pieces`'
    carve-out alone), `김. 민준` (4), and the one-case report test
    below (1; either `_classify` width site alone). The other four
    hangul rows pass there: they guard the fix itself, failing (with
    `김. 민준`, 20 in all) when `in_initialless_script`'s compose
    alone is reverted, since the composed initial shape without the
    composed veto made a decomposed '씨.' an initial. `Ivan й Petrov
    Sidorov` and `Smith, John й Jones` pass everywhere and pin parity
    only."""
    composed = unicodedata.normalize("NFC", text)
    decomposed = unicodedata.normalize("NFD", text)
    assert decomposed != composed
    parser = Parser(policy=policy)
    assert (_composed_reading(parser, decomposed)
            == _composed_reading(parser, composed))


def test_a_decomposed_conjunction_reports_as_its_composed_twin() -> None:
    """#665: the one-case report on a letter that is both a connective
    and an initial (rules/P8) counted code points, so it is reached
    by `й` only once a caller marks it ambiguous -- no default entry is
    decomposable."""
    parser = Parser(lexicon=Lexicon.default().add(
        "й", kind="conjunction", may_be_initial=True))
    text = "ivan й petrov"
    composed = parser.parse(text)
    assert [a.kind for a in composed.ambiguities] == [
        AmbiguityKind.CONJUNCTION_OR_INITIAL]
    assert (_composed_reading(parser, unicodedata.normalize("NFD", text))
            == _composed_reading(parser, text))


def test_a_decomposed_caps_credential_is_still_a_suffix() -> None:
    """The twin comparison above would pass if both encodings broke
    alike; this pins the reading itself (`Janez Novak, ŽŠČ`)."""
    name = parse(unicodedata.normalize("NFD", "Janez Novak, ŽŠČ"))
    assert unicodedata.normalize("NFC", name.suffix) == "ŽŠČ"
    assert name.given == "Janez"


def test_a_decomposed_chunked_credential_reads_as_its_composed_twin() -> None:
    """`_CHUNKED` is masked by the dotted-shape rule (S3) under the
    default policy; with that off and the acronym listed, the chunked
    gate is the only reader, and it read NFD `Ž.Šč.` as no credential."""
    parser = Parser(
        lexicon=Lexicon.default().add("žšč", kind="credential")
                                 .add("žšč", kind="family"),
        policy=Policy(unlisted_dotted_suffixes=False))
    text = "John Smith Ž.Šč."
    decomposed = unicodedata.normalize("NFD", text)
    assert decomposed != text
    assert (_composed_roles(parser, decomposed)
            == _composed_roles(parser, text))
    assert unicodedata.normalize(
        "NFC", parser.parse(decomposed).suffix) == "Ž.Šč."


def test_a_decomposed_dotted_letter_is_dotted() -> None:
    """`_DOTTED` is unobservable through a parse (`_CHUNKED` subsumes
    it for two or more letters and no input made the single-letter case
    differ), so it is pinned directly."""
    from nameparser._pipeline._vocab import _dotted
    assert _dotted(unicodedata.normalize("NFD", "Ž.")) is True


@pytest.mark.parametrize("mark", ["\u0301", "\u1ab0", "\u1dc0",
                                  "\u20d0", "\ufe20"])
def test_a_mark_from_each_combining_block_stays_in_its_word(
        mark: str) -> None:
    """`_vocab._MARKS` names five combining blocks (#652), and NFD of a
    letter only ever produces the first, so the twin rows above reach
    one. A mark from each block, written after a letter, keeps the
    abbreviation one word and its shape a title. Until 3.0 the class
    was also pinned to config's copy, which #1008 removed; measured
    2026-11-02, dropping U+1AB0-1AFF from `_MARKS` failed nothing else
    in the suite."""
    name = parse(f"Dr. inz{mark}. Janez Novak")
    assert name.title == f"Dr. inz{mark}."
    assert name.given == "Janez"


# #671: the credential, office and generational words, one spelling each
# per distinct entry, all spaced / after-comma vocabulary. #707 vetted
# the glued bar ("can it END a name?") and every word passed but
# 部長/部长, so the two lists below partition this one: a word moves
# between them only on purpose.
_CJK_GLUED_WORDS = (
    "議員", "议员", "国会議員", "國會議員", "太平紳士", "太平绅士",
    "医学博士", "醫學博士", "二世", "社長", "課長", "社长", "课长",
)
_CJK_SPACED_ONLY_WORDS = ("部長", "部长")
_CJK_SPACED_WORDS = _CJK_GLUED_WORDS + _CJK_SPACED_ONLY_WORDS


@pytest.mark.parametrize("word", _CJK_SPACED_WORDS)
def test_a_cjk_credential_word_is_a_suffix_spaced_and_after_a_comma(
        word: str) -> None:
    parser = Parser()
    for text in (f"田中 {word}", f"田中, {word}", f"Tanaka, {word}"):
        parsed = parser.parse(text)
        assert parsed.suffix == word, text
        assert word not in parsed.family + parsed.given, text
    # a one-word head and an empty head (CSV data with the surname
    # missing) are the comma paths that have disagreed before
    assert parser.parse(f", {word}").suffix == word


@pytest.mark.parametrize("word", _CJK_GLUED_WORDS)
def test_a_vetted_cjk_credential_word_peels_off_a_glued_name(
        word: str) -> None:
    parsed = Parser().parse(f"田中{word}")
    assert (parsed.family, parsed.suffix) == ("田中", word)


@pytest.mark.parametrize("word", _CJK_SPACED_ONLY_WORDS)
def test_a_declined_cjk_credential_word_does_not_peel_off_a_glued_name(
        word: str) -> None:
    # 長 alone is a borne given name, so 阿部長 can be 阿部 + 長 (#707).
    assert word not in Parser().lexicon._sets.honorific_tails
    assert Parser().parse(f"田中{word}").suffix == ""


# rules/S13 (#810): where a bracketed member reads differently from its
# twin, a bracketed unambiguous credential in the same place. The twin
# is MPH, a word no head holds, so the twin's reading maps back by
# replacing its text. 1,080 texts, about 2s.
_TWIN_HEADS = (
    "John Smith {c}", "Jack {c}", "{c}", "John {c}", "JOHN SMITH {c}",
    "Smith, John {c}", "Smith, {c}", ", {c}", "(Bob), {c}",
    "John Smith {c}, PhD", "John Smith, PhD {c}", "John Smith PhD {c}",
    "Dr. Jack {c}", "Dr. {c}", "Freiherr von Berg {c}", "Juan de la Vega {c}",
    "Jane Doe nee Smith {c}", "John Smith {c} née Jones",
    "John Smith {c} Dr.", "John Smith {c} VI", "John Smith {c} Ph. D.",
    "Smith, Jane {c} Mrs", "Ortega y Gasset, José {c}",
    "Smith, Freiherr von Berg {c}", "Doe, John van {c}",
    # a third comma part, and a clause whose settling another makes
    # possible, the first settled word making the name mixed case
    "Smith, John, Jr. {c}", "JOHN SMITH (m.a) {c}",
    "john smith (M.A) {c}", "Smith, John, X.Y.Z. {c}",
    "Smith, John, Bob {c}",
)
_TWIN_MEMBERS = ("MA", "M.A", "JD", "DO", "D.O", "MENG")
_TWIN_PAIRS = (("(", ")"), ('"', '"'))
_TWIN_ORDERS = (GIVEN_FIRST, FAMILY_FIRST, FAMILY_FIRST_GIVEN_LAST)


def _twin_reading(name: ParsedName, twin: str | None, word: str) -> tuple[
        dict[str, str], list[tuple[str, str]]]:
    def back(text: str) -> str:
        return text.replace(twin, word) if twin else text
    return ({k: back(v) for k, v in name.as_dict().items() if v},
            [(a.kind.value, back(a.detail)) for a in name.ambiguities])


#: The census, by head and by whether the member was settled or left
#: the nickname, recorded 2026-10-26 (#810). rules/S13's Accepted bullets
#: and its Except bullets name each shape: a lone name word stays N3's
#: family name beside a settled member where its twin's is given; the
#: maiden clause stays the maiden name where the twin's credential run
#: takes it; a part past a second comma reports what is left without
#: the member; a name written in one case settles no capitals; a name
#: with no word of its own (a title, a nickname, nothing) settles no
#: clause, where the twin escapes, read as the name ('(MPH)' given
#: 'MPH', 'Dr. (MPH)' given 'Dr.') or as the suffix behind a comma
#: (', (MPH)'); and a clause another
#: settled one would make settle, on a second reading, is left the
#: nickname.
_TWIN_CENSUS = {
    ("(Bob), {c}", "nickname"): 36,
    (", {c}", "nickname"): 36,
    ("Dr. {c}", "nickname"): 36,
    ("JOHN SMITH (m.a) {c}", "nickname"): 24,
    ("JOHN SMITH {c}", "nickname"): 24,
    ("Jack {c}", "settled"): 36,
    ("John Smith {c} née Jones", "settled"): 36,
    ("John {c}", "settled"): 36,
    ("Smith, John, Bob {c}", "settled"): 36,
    ("Smith, John, X.Y.Z. {c}", "settled"): 36,
    ("john smith (M.A) {c}", "nickname"): 24,
    ("{c}", "nickname"): 36,
}


def test_where_a_bracketed_member_reads_otherwise_than_its_twin() -> None:
    """A census, not a guarantee: one pass decides S13 once the roles are
    read, so the rest of the name is read around the clause as a
    nickname, and that differs from the twin's reading in the shapes
    _TWIN_CENSUS names. A change that moves a count, or adds a head, is
    a change to what rules/S13 accepts: re-record it there and here.
    The twin reading folded to a fixed point (the PR's fourth draft,
    declined by Derek for one pass) differed in none of the settled
    rows."""
    census: dict[tuple[str, str], int] = {}
    for (open_, close), word, head, order in itertools.product(
            _TWIN_PAIRS, _TWIN_MEMBERS, _TWIN_HEADS, _TWIN_ORDERS):
        parser = Parser(policy=Policy(name_order=order))
        name = parser.parse(head.format(c=f"{open_}{word}{close}"))
        twin = parser.parse(head.format(c=f"{open_}MPH{close}"))
        if _twin_reading(name, None, word) != _twin_reading(
                twin, "MPH", word):
            key = (head, "nickname" if word in name.nickname.split()
                   else "settled")
            census[key] = census.get(key, 0) + 1
    assert census == _TWIN_CENSUS


def test_the_joined_tag_never_reaches_a_title() -> None:  # #429 regression guard
    """The "joined" tag is role-blind, so a tag placed for a suffix entry
    would be read by a title too.

    So the pass that writes it (post_rules' R1 entry pass, #436) walks
    the SUFFIX tokens alone and reads every other role as transparent
    to the run rather than as part of it. #429's first draft let any
    piece open an entry: a title piece doing so tagged the title behind
    it. Asserted on the tags because the string views cannot see it --
    titles render space-joined either way.
    """
    def joined(text: str) -> list[str]:
        return [t.text for t in parse(text).tokens if "joined" in t.tags]

    n = parse("Smith, Rev. Dr.")
    assert n.title == "Rev. Dr."
    assert joined("Smith, Rev. Dr.") == []
    # with a suffix already standing from the pre-comma segment, a
    # title opening the entry glued the next suffix backward across
    # the writer's own comma
    assert parse("Smith Jr., Mr. Jr.").suffix == "Jr., Jr."
    assert joined("Smith Jr., Mr. Jr.") == []
    # the control: where the pieces really are one entry, they DO join
    assert joined("Smith, MD PhD") == ["PhD"]
    # a role that renders elsewhere is stepped OVER by the pass and
    # never stepped onto: it needs a suffix word FIRST, so a run is
    # legitimately open, and then TWO titles
    j = parse("Smith, MD Rev. Dr.")
    assert (j.suffix, j.title) == ("MD", "Rev. Dr.")
    assert joined("Smith, MD Rev. Dr.") == []


def test_the_ph_d_pair_reads_by_the_vocabulary() -> None:
    # v1's fix_phd merged 'Ph. D.' by its spelling alone, and through 2.8
    # a config without 'phd' still read the pair as one suffix; since
    # #1000 the lexicon defines both spellings (decisions/phd-merge)
    p = Parser(lexicon=Lexicon.default().remove("phd", kind="credential"))
    s = p.parse("John Smith Ph. D.")
    assert (s.middle, s.family, s.suffix) == ("Smith Ph.", "D.", "")
    h = p.parse("John Smith, Ph. D.")
    assert (h.title, h.given, h.family, h.suffix) == (
        "Ph.", "D.", "John Smith", "")


def test_a_given_name_written_short_listed_as_a_title_is_a_title() -> None:
    # #789: the caller who reads the word as a title gets 1.4's reading
    # back, the leading peel asking the titles before the shape the
    # given_name_abbreviations set outranks. Since 3.0's 4i-b the word
    # leaves that set on the way: its given reading, which made it an
    # abbreviation, would also keep a title reading one only inside a
    # phrase (rules/H9), so a title everywhere is the given reading
    # removed, and 2.x's title beside an abbreviation has no spelling
    assert parse("Chas. Smith").given == "Chas."   # baseline
    p = Parser(lexicon=Lexicon.default().remove("chas", kind="given")
               .add("chas", kind="title"))
    assert p.parse("Chas. Smith").title == "Chas."


# -- a choice of languages (Locale.languages, phase 3b) --


def _choosing(*tags: str, code: str = "choice",
              lexicon: Lexicon | None = None) -> Locale:
    return Locale(code=code, lexicon=lexicon or Lexicon.empty(),
                  languages=frozenset(tags))


def test_the_compiled_fields_are_the_default_lexicons() -> None:
    from nameparser._lexicon import _KIND_FIELDS, _VOCAB_FIELDS, _vocab_fields
    from nameparser._reading_index import compile_choice
    default = Lexicon.default()
    fields = _vocab_fields(compile_choice(frozenset()))
    # surnames is KOREAN_SURNAMES and given_names a pack's list (#959),
    # neither compiled from the vocabulary; the kind sets the views read
    # are compiled beside the 2.x fields
    assert {f for f in fields} | {"surnames", "given_names"} == set(
        _VOCAB_FIELDS) | set(_KIND_FIELDS)
    for name, words in fields.items():
        assert getattr(default._sets, name) == words, name


def test_a_pack_choosing_no_language_leaves_the_vocabulary_as_it_is() -> None:
    base = Parser(lexicon=Lexicon.default().add("zzq", kind="title"))
    assert parser_for(Locale(code="xx", lexicon=Lexicon.empty()),
                      base=base).lexicon == base.lexicon


def test_building_a_parser_with_no_choice_never_loads_the_reading_index() -> None:
    # the index loads on its first lookup (decisions/vocabulary-model,
    # 3a): a parse makes one, for Reading.languages, but building a
    # parser choosing no language never does, where a choice must
    import subprocess
    import sys
    code = ("import sys, nameparser; from nameparser import locales; "
            "nameparser.parser_for(locales.RU, locales.TR_AZ); "
            "assert 'nameparser.config._index' not in sys.modules; "
            "nameparser.parser_for(nameparser.Locale('pt', "
            "nameparser.Lexicon.empty(), languages={'pt'})); "
            "assert 'nameparser.config._index' in sys.modules")
    subprocess.run([sys.executable, "-c", code], check=True)


@pytest.mark.parametrize("tags,name,field,before,after", [
    # prefer, against a shape: the one-case conjunction holds under pt
    (("pt",), "ANA SILVA E SOUZA", "family", "SOUZA", "SILVA E SOUZA"),
    # prefer: ar's bound given name stays, en's credential leaves
    (("ar",), "Haddad, Abd", "given", "", "Abd"),
    # turning on: cs's generation joins, en's Saint readings leave
    (("cs",), "Jiří Dienstbier st.", "suffix", "", "st."),
    # prefer: pt's preposition, en's credential gone
    (("pt",), "John Smith DO", "family", "Smith", "DO"),
    # and the other way: en's credential, pt's preposition gone
    (("en",), "Maria do Carmo", "family", "do Carmo", "Carmo"),
    # both chosen, both kept, gated as in the default
    (("pt", "en"), "John Smith DO", "suffix", "DO", "DO"),
    (("pt", "en"), "Maria do Carmo", "family", "do Carmo", "do Carmo"),
])
def test_a_choice_selects_the_readings_of_its_languages(
        tags: tuple[str, ...], name: str, field: str, before: str,
        after: str) -> None:
    assert getattr(parse(name), field) == before
    assert getattr(parser_for(_choosing(*tags)).parse(name), field) == after


def test_a_choice_settled_by_a_name_reading_keeps_the_gate_on() -> None:
    # en's given reading of `st` still gates the generation cs turns on
    got = parser_for(_choosing("cs")).parse("Jiří Dienstbier st.")
    assert [a.kind for a in got.ambiguities] == [AmbiguityKind.SUFFIX_OR_NAME]


def test_the_packs_choices_are_one_choice_in_any_order() -> None:
    pt, en = _choosing("pt", code="aa"), _choosing("en", code="bb")
    both = parser_for(_choosing("pt", "en")).lexicon
    assert parser_for(pt, en).lexicon == parser_for(en, pt).lexicon == both


def test_a_choice_keeps_a_callers_vocabulary() -> None:
    base = Parser(lexicon=Lexicon.default().add("zzq", kind="title"))
    got = parser_for(_choosing("pt"), base=base)
    assert "zzq" in got.lexicon._sets.titles
    assert got.parse("ANA SILVA E SOUZA").family == "SILVA E SOUZA"


def test_a_packs_own_fragment_is_unioned_on_after_the_choice() -> None:
    # pt drops en's credential reading of `do`; the pack's fragment puts
    # it back, as a caller listing a word has always asked for
    pack = _choosing("pt", lexicon=Lexicon.empty().add("do", kind="credential"))
    assert parser_for(pack).parse("John Smith DO").suffix == "DO"


@pytest.mark.parametrize("tag,match", [
    ("xx", "while applying locale 'choice': no vocabulary file holds"),
    ("mul", "while applying locale 'choice': 'mul' is not a language"),
])
def test_a_choice_no_file_can_serve_is_refused_with_the_pack(
        tag: str, match: str) -> None:
    with pytest.raises(ValueError, match=match):
        parser_for(_choosing(tag))


def test_a_lowercase_region_selects_the_regions_file() -> None:
    assert (parser_for(_choosing("pt-br")).lexicon
            == parser_for(_choosing("pt-BR")).lexicon)


def test_a_word_a_choice_drops_leaves_the_callers_markers_of_it_too() -> None:
    # a caller marked `vd` possibly given (a given reading beside its
    # particle one); en's credential drops nl's preposition, so the word
    # leaves `particles`, and the caller's mark with it, a marker
    # compiling only beside its base (found by review, 3b)
    base = Parser(lexicon=Lexicon.default().add("vd", kind="given"))
    got = parser_for(_choosing("en"), base=base).lexicon._sets
    assert "vd" not in got.particles and "vd" not in got.particles_ambiguous


@pytest.mark.parametrize("mask,error", [
    # a value not a string: a TypeError
    (5, TypeError),
    # a mask spelling other letters: _lexicon._MaskValueError, whose
    # constructor takes three arguments, rewrapped as a plain ValueError
    ("Abc", ValueError),
])
def test_an_error_applying_a_choice_names_the_choice(
        monkeypatch: pytest.MonkeyPatch, mask: object,
        error: type[Exception]) -> None:
    # an error the Lexicon raises while the choice is applied names the
    # languages chosen, as a patch error names its pack. A shipped
    # choice raises only on a caller's clashing reading (the `st` test
    # below), so a choice moving a mask the Lexicon refuses stands in
    import nameparser._parser as parser_mod
    monkeypatch.setattr(parser_mod, "_rechosen_masks",
                        lambda lexicon, chosen, strict: (("zzq", mask),))
    with pytest.raises(error, match="while applying the languages chosen, "
                                    "en, pt \\(by 'aa', 'bb'\\): "
                                    "capitalization_exceptions"):
        parser_for(_choosing("pt", code="aa"), _choosing("en", code="bb"))


def test_a_choice_moves_case_masks_as_it_moves_words() -> None:
    # cs's credentials carry masks the default leaves off (`judr` ->
    # JUDr), a strict choice drops the masks of every file it drops
    # (en.toml's `dphil` under ko) and keeps mul.toml's (`phd`, #1005),
    # and a caller's own mask the choice does not touch is kept
    from nameparser import locales
    mine = dataclasses.replace(Lexicon.default(), capitalization_exceptions=(
        *Lexicon.default().capitalization_exceptions, ("abcq", "AbcQ")))
    cs = parser_for(locales.CS, base=Parser(lexicon=mine)).lexicon
    assert cs.capitalization_exceptions_map["judr"] == "JUDr"
    assert cs.capitalization_exceptions_map["abcq"] == "AbcQ"
    ko = parser_for(_choosing("ko"), strict=True).lexicon
    assert "dphil" not in ko.capitalization_exceptions_map
    assert ko.capitalization_exceptions_map["phd"] == "PhD"
    # chained, the masks move as the union's do: what ko's strict choice
    # dropped and en's keeps comes back
    en, ko_pack = _choosing("en", code="en"), _choosing("ko", code="ko")
    chained = parser_for(en, base=parser_for(ko_pack, strict=True),
                         strict=True)
    assert "dphil" in chained.lexicon.capitalization_exceptions_map
    assert chained.lexicon == parser_for(ko_pack, en, strict=True).lexicon


def test_a_choice_chained_through_base_unions_with_the_bases() -> None:
    # decisions/vocabulary-model, 2026-11-02 #754, item 4: the lexicon
    # records its choice, so en chained on pt's parser chooses both, as
    # one call choosing both does (superseding 2026-10-29's chained
    # choices, where en dropped pt's particle after pt dropped en's
    # credential: family `Carmo`, family `DO`)
    pt, en = _choosing("pt", code="pt"), _choosing("en", code="en")
    chained = parser_for(en, base=parser_for(pt))
    assert chained.parse("Maria do Carmo").family == "do Carmo"
    assert chained.parse("John Smith DO").suffix == "DO"
    together = parser_for(pt, en)
    assert chained.lexicon == together.lexicon
    assert chained.languages == together.languages == {"en", "pt"}


def test_a_choice_whose_reading_clashes_with_the_callers_is_refused() -> None:
    # cs turns on `st`'s generation beside a caller's credential, and a
    # word holds one suffix kind: refused at parser_for, naming the
    # languages, the edit, and the remove that resolves it
    # (decisions/vocabulary-model, 2026-11-02 #754, item 3)
    from nameparser import locales
    mine = Parser(lexicon=Lexicon.default().add("st", kind="credential"))
    with pytest.raises(ValueError, match=(
            r"while applying the languages chosen, cs \(by 'cs'\): the "
            r"lexicon's "
            r"\.add\('st', kind='credential'\) clashes with a reading the "
            r"choice turns on: 'st' would hold two suffix kinds.*"
            r"\.remove\('st', kind='generation'\)")) as raised:
        parser_for(locales.CS, base=mine)
    # the remove it offers applies after the choice, so it runs
    offered = re.search(r"(\.remove\(.*\))$", str(raised.value))
    assert offered is not None
    fixed = eval("Lexicon.default().add('st', kind='credential')"  # noqa: S307
                 + offered.group(1), {"Lexicon": Lexicon})
    got = parser_for(locales.CS, base=Parser(lexicon=fixed))
    assert got.parse("Jiří Dienstbier st.").suffix == "st."


def test_a_clash_the_log_makes_without_the_choice_is_not_the_choices(
        ) -> None:
    # an edit made on a chosen lexicon that clashes with the base alone
    # is refused as it is with no choice, the choice not named
    chosen = parser_for(_choosing("pt")).lexicon
    with pytest.raises(ValueError, match="would hold two suffix kinds") as e:
        chosen.add("jr", kind="credential")
    assert "the choice" not in str(e.value)


def test_a_callers_reading_survives_a_choice_whoever_wrote_first() -> None:
    # superseding 2026-10-29's chained choices item 2, where the delta
    # dropped what the choice removed whoever listed it: a caller's
    # reading applies after the choice
    mine = Lexicon(surnames=Lexicon.default().surnames).add(
        "do", "van", kind="preposition")
    got = parser_for(_choosing("en"), base=Parser(lexicon=mine)).lexicon
    assert got._sets.particles == {"do", "van"}
    # and a caller's removal too: with en's credential of `do` taken out
    # after en preferred it over pt's particle, `do` reads as neither
    removed = Lexicon.default().remove("do", kind="credential")
    en = parser_for(_choosing("en"), base=Parser(lexicon=removed))
    assert en.parse("Maria do Carmo").middle == "do"


def test_a_choice_selects_nothing_in_an_empty_base() -> None:
    # a base built from Lexicon.empty() holds no shipped reading, so a
    # choice turns none on (the 2026-11-02 #754 entry's item 4)
    # (the Korean surnames kept, so the default policy's hangul
    # segmentation has its list)
    empty = Lexicon(surnames=Lexicon.default().surnames)
    got = parser_for(_choosing("cs"), base=Parser(lexicon=empty))
    assert got.languages == {"cs"}
    from nameparser._lexicon import _fields_of
    assert _fields_of(got.lexicon._sets) == _fields_of(empty._sets)


def test_the_choice_is_recorded_and_read_through_the_parser() -> None:
    plain = parser_for(_choosing("pt-br"))
    assert plain.languages == plain.lexicon.languages == {"pt-BR"}
    assert plain.strict is plain.lexicon.strict is False
    strict = parser_for(_choosing("ko"), strict=True)
    assert strict.strict is strict.lexicon.strict is True
    assert Parser().languages == frozenset() and Parser().strict is False
    # a pack choosing nothing chained on a choice keeps it, a strict one
    # included, whatever strict the call leaves at its default (found by
    # review of 4i-c: a policy-only pack on a strict parser raised)
    nothing = Locale(code="xx", lexicon=Lexicon.empty())
    assert parser_for(nothing, base=plain).lexicon == plain.lexicon
    assert parser_for(nothing, base=strict).lexicon == strict.lexicon
    assert parser_for(base=strict, segmenter=None).strict is True


def test_strict_has_three_states_on_a_chained_call() -> None:
    # decided 2026-11-02 (decisions/vocabulary-model, 2026-11-02 #754,
    # sub-phase 4i-c): strict defaults to UNSET, as segmenter does
    ko, en = _choosing("ko", code="ko"), _choosing("en", code="en")
    strict, plain = parser_for(ko, strict=True), parser_for(ko)
    # omitted on a strict base: stays strict
    assert parser_for(en, base=strict).strict is True
    assert parser_for(base=strict).lexicon == strict.lexicon
    # an explicit False on a strict base: refused, naming both spellings
    for packs in ((), (en,)):
        with pytest.raises(ValueError, match=(
                r"chosen with strict=True.*leave strict out or pass "
                r"strict=True.*parser_for\(\*packs, strict=False\)")):
            parser_for(*packs, base=strict, strict=False)
    # an explicit True on a plain base with a choice: becomes strict
    got = parser_for(en, base=plain, strict=True)
    assert got.strict is True
    assert got.lexicon == parser_for(ko, en, strict=True).lexicon
    # omitted on a plain base: stays plain
    assert parser_for(en, base=plain).strict is False
    # an explicit True with no language anywhere: refused, as 3j
    with pytest.raises(ValueError, match="no pack was given"):
        parser_for(strict=True)


def test_a_chained_choice_redoes_a_mask_the_default_lacks() -> None:
    # cs sets `judr`'s mask, which the default holds none of; chained
    # under en, the base's move is undone (the mask deleted) and the
    # union's applied again, as the single call does
    from nameparser import locales
    en = _choosing("en", code="en")
    chained = parser_for(en, base=parser_for(locales.CS))
    assert chained.lexicon.capitalization_exceptions_map["judr"] == "JUDr"
    assert chained.lexicon == parser_for(locales.CS, en).lexicon


def test_a_join_that_cannot_be_made_names_where_it_failed() -> None:
    # two packs whose lexicons record different choices name the pack;
    # a pack's lexicon built on another release's base names the join
    # with base's (rules/D2)
    from nameparser.config._index import READINGS
    pt = Locale(code="aa", lexicon=dataclasses.replace(
        Lexicon.empty(), _languages=frozenset({"pt"})))
    en = Locale(code="bb", lexicon=dataclasses.replace(
        Lexicon.empty(), _languages=frozenset({"en"})))
    with pytest.raises(ValueError, match="while applying locale 'bb': "
                                         "cannot join two lexicons compiled"):
        parser_for(pt, en)
    older = Locale(code="cc", lexicon=Lexicon(_base=READINGS[1:]))
    with pytest.raises(ValueError, match="while applying locale 'cc': "
                                         "cannot join two lexicons built "
                                         "on different bases"):
        parser_for(older)


@pytest.mark.parametrize("packs,match", [
    # a fragment that clashes with base's readings names its pack, as a
    # patch error does (rules/D2; found by review of 4i-c, where the
    # join named no pack): `dc` is a credential in the default
    (("mypack",), "while applying locale 'mypack': 'dc' would hold two "
                  "suffix kinds"),
    # and behind a pack that joins cleanly, the one that clashes
    (("clean", "mypack"), "while applying locale 'mypack': "),
    # a fragment that clashes with a reading the choice turns on: `st`
    # as a credential beside cs's generation
    (("cs_credential",), "while applying locale 'cs_credential': the "
                         "lexicon's \\.add\\('st', kind='credential'\\)"),
])
def test_a_fragments_clash_names_its_pack(packs: tuple[str, ...],
                                          match: str) -> None:
    built = {
        "mypack": Locale(code="mypack",
                         lexicon=Lexicon.empty().add("dc", kind="generation")),
        "clean": Locale(code="clean",
                        lexicon=Lexicon.empty().add("zzq", kind="title")),
        "cs_credential": _choosing("cs", code="cs_credential", lexicon=(
            Lexicon.empty().add("st", kind="credential"))),
    }
    with pytest.raises(ValueError, match=match):
        parser_for(*(built[p] for p in packs))


def test_a_clash_of_base_with_a_choice_it_joins_names_base_too() -> None:
    # base chose pt and added `st` as a credential; chained under cs,
    # which turns on `st`'s generation, the clash is base's own with the
    # union, and the layer names the pack that chose cs and base
    from nameparser import locales
    mine = Parser(lexicon=Lexicon.default().add("st", kind="credential"))
    pt = parser_for(_choosing("pt"), base=mine)
    with pytest.raises(ValueError, match=(
            r"while applying the languages chosen, cs, pt "
            r"\(by 'cs', base\): the lexicon's \.add\('st'")):
        parser_for(locales.CS, base=pt)


def test_a_chained_choice_restores_a_mask_it_had_changed(
        monkeypatch: pytest.MonkeyPatch) -> None:
    # no shipped choice changes a mask the default holds, only adds or
    # drops one, so a stand-in choice does: chained under another
    # language, the base's change is undone to the default's value and
    # the union's applied again, as the single call does
    import nameparser._lexicon as lexicon_mod
    real = lexicon_mod._choice_masks.__wrapped__  # type: ignore[attr-defined]

    def stand_in(chosen: frozenset[str], strict: bool = False) -> object:
        gone, joined = real(chosen, strict)
        if "ga" in chosen:
            joined = (*joined, ("phd", "PHD"))
        return gone, tuple(sorted(joined))
    monkeypatch.setattr(lexicon_mod, "_choice_masks", stand_in)
    ga, en = _choosing("ga", code="ga"), _choosing("en", code="en")
    base = parser_for(ga)
    assert base.lexicon.capitalization_exceptions_map["phd"] == "PHD"
    chained = parser_for(en, base=base)
    assert chained.lexicon == parser_for(ga, en).lexicon
    assert chained.lexicon.capitalization_exceptions_map["phd"] == "PHD"


def test_a_packs_masks_are_laid_over_the_choices() -> None:
    # the choice moves base's masks, and a pack's are laid over them, so
    # a pack's mask of a word the choice joins or drops stands, as on
    # master before 4i-c (found by review of 4i-c); a caller's own mask
    # on a word the choice joins is the choice's, as it was
    from nameparser import locales
    fm = Locale(code="fm", lexicon=dataclasses.replace(
        Lexicon.empty(), capitalization_exceptions=(
            ("phd", "PHD"), ("judr", "JUDR"))))
    for strict in (False, True):
        p = parser_for(fm, locales.CS, strict=strict)
        cap = p.lexicon.capitalization_exceptions_map
        assert (cap["phd"], cap["judr"]) == ("PHD", "JUDR"), strict
        rendered = str(p.capitalized(p.parse("jan novák phd judr")))
        assert "PHD" in rendered and "JUDR" in rendered, strict
    mine = dataclasses.replace(Lexicon.default(), capitalization_exceptions=(
        *Lexicon.default().capitalization_exceptions, ("judr", "Judr")))
    p = parser_for(locales.CS, base=Parser(lexicon=mine))
    assert p.lexicon.capitalization_exceptions_map["judr"] == "JUDr"


def test_a_packs_fragment_joins_under_the_callers_lexicon() -> None:
    # the caller's lexicon goes last, so its own statement outranks a
    # pack's: a pack's credential `do` against a caller's removal of it,
    # and a pack's mask against the caller's (decisions/vocabulary-model,
    # 2026-11-02 #754, item 3)
    fragment = dataclasses.replace(
        Lexicon.empty().add("do", kind="credential"),
        capitalization_exceptions=(("zzq", "ZZq"),))
    pack = _choosing("en", lexicon=fragment)
    mine = dataclasses.replace(
        Lexicon.default().remove("do", kind="credential"),
        capitalization_exceptions=(
            *Lexicon.default().capitalization_exceptions, ("zzq", "ZzQ")))
    got = parser_for(pack, base=Parser(lexicon=mine))
    assert got.parse("John Smith DO").suffix == ""
    assert got.lexicon.capitalization_exceptions_map["zzq"] == "ZzQ"
    # a shipped mask the caller left as shipped is no statement of the
    # caller's, so a pack's mask of the word wins, as its readings win
    # over shipped ones; one the caller changed outranks the pack's
    # (found by review of 4i-c)
    phd = _choosing("en", lexicon=dataclasses.replace(
        Lexicon.empty(), capitalization_exceptions=(("phd", "PHD"),)))
    assert (parser_for(phd).lexicon.capitalization_exceptions_map["phd"]
            == "PHD")
    changed = dataclasses.replace(Lexicon.default(), capitalization_exceptions=(
        *(p for p in Lexicon.default().capitalization_exceptions
          if p[0] != "phd"), ("phd", "Phd")))
    assert (parser_for(phd, base=Parser(lexicon=changed))
            .lexicon.capitalization_exceptions_map["phd"] == "Phd")
    # the accepted limit: a caller's mask written as the shipped value
    # cannot be told from the shipped one, so the pack's wins it
    # (decisions/vocabulary-model, 2026-11-02 #754, sub-phase 4i-c)
    shipped_value = Parser(lexicon=dataclasses.replace(
        Lexicon.default(), capitalization_exceptions=(("phd", "PhD"),)))
    p = parser_for(phd, base=shipped_value)
    assert str(p.capitalized(p.parse("jan novák phd"))) == "Jan Novák PHD"
    # and a later pack's fragment after an earlier one's
    first = _choosing("en", code="aa",
                      lexicon=Lexicon.empty().add("zzq", kind="title"))
    second = _choosing("en", code="bb",
                       lexicon=Lexicon.empty().remove("zzq", kind="title"))
    assert parser_for(first, second).parse("Zzq Smith").title == ""
    assert parser_for(second, first).parse("Zzq Smith").title == "Zzq"


def _languages_of(parser: Parser, name: str, text: str) -> tuple[str, ...]:
    token = next(t for t in parser.parse(name).tokens if t.text == text)
    assert token.reading is not None
    return token.reading.languages


def test_reading_languages_follow_the_choice() -> None:
    # decisions/vocabulary-model, 2026-11-02 #754, sub-phase 4i-d: the
    # field names the files whose reading is on in the parse's own
    # lexicon. Under pt, `it`'s reading of `e`, which pt's preference
    # drops, is no longer named; under cs, the generation `st` the
    # choice turns on names cs; a word only an unchosen file holds keeps
    # that file (`van`, nl's), the plain choice keeping its reading on.
    # These were ('it', 'pt'), () and ('es', 'fr', 'it', 'nl', 'pt')
    # before 4i-d, the files on by default whatever the choice
    pt, cs = parser_for(_choosing("pt")), parser_for(_choosing("cs"))
    assert pt.parse("ANA SILVA E SOUZA").family == "SILVA E SOUZA"
    assert _languages_of(pt, "ANA SILVA E SOUZA", "E") == ("pt",)
    assert cs.parse("Jiří Dienstbier st.").suffix == "st."
    assert _languages_of(cs, "Jiří Dienstbier st.", "st.") == ("cs",)
    assert _languages_of(pt, "Ana de Souza", "de") == ("pt",)
    assert _languages_of(pt, "Vincent van Gogh", "van") == ("nl",)
    # with no choice, the files on by default, as before
    assert _languages_of(Parser(), "Ana de Souza", "de") == (
        "ca", "es", "fil", "fr", "it", "nl", "pt", "si")


def test_reading_languages_under_a_strict_choice_name_the_chosen_files() -> None:
    # a strict choice keeps only the chosen files' readings and
    # mul.toml's (#1005), so nothing else is named; a reading the strict
    # lexicon does not hold is no reading at all (the Pharm/D pair, read
    # as a credential only where the lexicon lists `pharmd`, as the
    # Ph./D. pair is by `phd`: decisions/phd-merge, #1000)
    en = parser_for(_choosing("en"), strict=True)
    assert _languages_of(Parser(), "Baron John Smith", "Baron") == (
        "de", "en", "fr", "nl")
    assert _languages_of(en, "Baron John Smith", "Baron") == ("en",)
    pt = parser_for(_choosing("pt"), strict=True)
    assert _languages_of(pt, "John Smith Ph. D.", "Ph.") == ("mul",)
    assert pt.parse("John Smith Pharm D").suffix == ""
    assert _languages_of(Parser(), "John Smith Pharm D", "Pharm") == ("en",)


def test_an_empty_lexicon_names_no_file() -> None:
    # a word the default lists, asked of a lexicon with no readings: no
    # parse under Lexicon.empty() takes a vocabulary reading since #1000
    # (the Ph./D. pair was the one that did), so the lookup is asked
    # directly
    credential = frozenset({"credential"})
    assert Lexicon.default()._files.languages("phd", credential) == ("mul",)
    assert Lexicon.empty()._files.languages("phd", credential) == ()


def test_reading_languages_follow_a_callers_readings() -> None:
    # the same rule over a caller's log, with no choice: a caller's own
    # reading names no file; an add of a kind a file holds off by
    # default turns that file's reading on, and names it; a remove
    # stops naming the file whose reading it took out
    zzq = Parser(lexicon=Lexicon.default().add("zzq", kind="title"))
    assert zzq.parse("Zzq John Smith").title == "Zzq"
    assert _languages_of(zzq, "Zzq John Smith", "Zzq") == ()
    st = Parser(lexicon=Lexicon.default().add("st", kind="generation"))
    assert st.parse("Jiří Dienstbier st.").suffix == "st."
    assert _languages_of(st, "Jiří Dienstbier st.", "st.") == (
        "cs", "hr", "sk", "sl")
    mine = Lexicon.default().remove("baron", kind="title").add(
        "baron", kind="title")
    assert _languages_of(Parser(lexicon=mine), "Baron John Smith",
                         "Baron") == ()
    # a caller's add under a choice turns its kind on as with none
    chosen = parser_for(_choosing("pt"), base=st)
    assert _languages_of(chosen, "Jiří Dienstbier st.", "st.") == (
        "cs", "hr", "sk", "sl")
    # the empty lexicon lists nothing, so names nothing: no parse under
    # it takes a vocabulary reading since #1000, so
    # test_an_empty_lexicon_names_no_file asks the lookup directly


def test_an_alternative_reading_names_the_files_on_under_the_choice() -> None:
    name = "da Silva Sr. José Pedro Eduardo Jr., MP"
    def alternatives(parser: Parser) -> list[tuple[str, ...]]:
        return [a.alternative.languages for a in parser.parse(name).ambiguities
                if a.alternative is not None]
    assert alternatives(Parser()) == [("it", "pt")]
    assert alternatives(parser_for(_choosing("pt"))) == [("pt",)]


def test_reading_languages_survive_a_pickled_parser() -> None:
    # the lexicon's key is rebuilt on load, never pickled, and equal
    # lexicons share it, so a loaded parser reads as the one written
    pt = parser_for(_choosing("pt"))
    loaded = pickle.loads(pickle.dumps(pt))
    assert loaded.lexicon._files is pt.lexicon._files
    assert _languages_of(loaded, "Ana de Souza", "de") == ("pt",)
    assert "_files" not in pt.lexicon.__getstate__()


def test_a_choice_that_changes_nothing_leaves_the_sets_as_they_are() -> None:
    # sv.toml holds no reading the default leaves off or another file's
    # reading clashes with, so choosing it changes no compiled set; the
    # lexicon records the choice all the same
    from nameparser._reading_index import changed_words, selected
    assert changed_words(selected(["sv"])) == frozenset()
    mine = Lexicon.default().add("zzq", kind="title")
    got = parser_for(_choosing("sv"), base=Parser(lexicon=mine)).lexicon
    from nameparser._lexicon import _fields_of
    assert _fields_of(got._sets) == _fields_of(mine._sets)
    assert got.languages == {"sv"}


# -- strict (#753, 3j: file-strict, decisions/vocabulary-model's
# 2026-10-30 #753, file-strict entry) ---------------------------------

@pytest.mark.parametrize("tags,name,before,after", [
    # romanized Korean: every word below is a common Korean syllable
    # another file holds a vocabulary reading of
    (("ko",), "Kim Do Hyun", {"family": "Do Hyun"},  # pt's particle
     {"middle": "Do", "family": "Hyun"}),
    (("ko",), "Kim Bin Hyun", {"family": "Bin Hyun"},  # ar's and ms's
     {"middle": "Bin", "family": "Hyun"}),
    (("ko",), "Ra Min Jun", {"title": "Ra"},  # de's academic title
     {"given": "Ra", "title": ""}),
    (("ko",), "Kim Min Ra", {"suffix": "Ra"},  # en's credential
     {"family": "Ra", "suffix": ""}),
    # what adding en costs: its credential is back
    (("ko", "en"), "Kim Min Ra", {"suffix": "Ra"}, {"suffix": "Ra"}),
    # en's rank; 'Gen Hoshino' stood here until #999 made 'gen' a
    # title only in a phrase, which reads given 'Gen' with no choice
    (("ja",), "Capt Hoshino", {"title": "Capt"}, {"given": "Capt"}),
    (("zh",), "De Xu", {"family": "De Xu"},
     {"given": "De", "family": "Xu"}),
    # vi.toml holds no reading, which only a strict choice accepts
    (("vi",), "Do Van Minh", {"family": "Van Minh"},
     {"middle": "Van", "family": "Minh"}),
])
def test_a_strict_choice_reads_only_the_chosen_files(
        tags: tuple[str, ...], name: str, before: dict[str, str],
        after: dict[str, str]) -> None:
    default = parse(name)
    for field, value in before.items():
        assert getattr(default, field) == value, field
    got = parser_for(_choosing(*tags), strict=True).parse(name)
    for field, value in after.items():
        assert getattr(got, field) == value, field


def test_a_strict_choice_keeps_mul_and_native_script_vocabulary() -> None:
    strict = parser_for(_choosing("vi"), strict=True)
    # mul.toml's words are every language's, so a strict choice reads
    # them (#1005): its titles, credentials and numerals
    assert strict.parse("Dr Minh Do").title == "Dr"
    assert strict.parse("Mr Minh Do").title == "Mr"
    assert strict.parse("Minh Do, PhD").suffix == "PhD"
    assert strict.parse("Minh Do III").suffix == "III"
    # jr, junior and jnr, written after names in every country's data
    # (2026-11-03, the strict-gap batches)
    assert strict.parse("Minh Do Jr.").suffix == "Jr."
    assert strict.parse("Do, Minh, Junior").suffix == "Junior"
    assert strict.parse("Mrs Minh Do").title == "Mrs"
    # `ms` and `miss` whole, the salutation with the credential and the
    # family reading (2026-11-03): `MS` after a comma stays the degree,
    # and South Indian initials read as the default reads them
    assert strict.parse("Ms Minh Do").title == "Ms"
    assert strict.parse("Miss Minh Do").title == "Miss"
    assert strict.parse("A Israni, MD, MS").suffix == "MS"
    assert strict.parse("Radha MS").suffix == parse("Radha MS").suffix == "MS"
    # the five degrees #1021 moved (and `ms`'s, above), each after a
    # comma and in a run
    assert strict.parse("Minh Do, MSc, MBA").suffix == "MSc, MBA"
    assert strict.parse("Minh Do, MPH, BSc").suffix == "MPH, BSc"
    # en.toml's leave: `md`, kept there since a leading Md abbreviates
    # Muhammad, `mx`, the abbreviation for Mexico, and `rn`
    assert strict.parse("Minh Do, MD").given == "MD"
    assert strict.parse("Mx Minh Do").given == "Mx"
    assert strict.parse("Minh Do, RN").given == "RN"
    # every reading of `do` (en.toml's credential and name readings,
    # pt.toml's particle) is in a file strict vi does not read, so `Do`
    # is a plain name word beside mul.toml's `PhD`
    assert strict.parse("Minh Do, PhD").family == "Do"
    # a native-script word selects itself by script, whatever its file
    assert strict.parse("김민준 씨").suffix == "씨"
    # and the Korean surname list is outside the per-word model
    assert strict.lexicon.surnames == Lexicon.default().surnames


@pytest.mark.parametrize("packs,match", [
    ((), "no pack was given"),
    (("ZH",), "the pack 'zh' chooses none"),
    (("ZH", "RU"), "the packs 'zh', 'ru' choose none"),
    # a code that is no language: the fix offered chooses en
    (("TR_AZ",), "the pack 'tr_az' chooses none.*'en'"),
])
def test_a_strict_call_choosing_no_language_is_refused_with_a_fix_that_runs(
        packs: tuple[str, ...], match: str) -> None:
    from nameparser import locales
    given = tuple(getattr(locales, p) for p in packs)
    with pytest.raises(ValueError, match=match) as info:
        parser_for(*given, strict=True)
    # the message hands the reader a pack to add: it must run
    offered = re.search(r"e\.g\. (Locale\(.*\)\)), or", str(info.value))
    assert offered is not None
    pack = eval(offered.group(1), {"Locale": Locale, "Lexicon": Lexicon})
    assert parser_for(*given, pack, strict=True).lexicon != Lexicon.default()


def test_a_file_with_no_reading_is_a_strict_choice_only() -> None:
    with pytest.raises(ValueError, match=r"vi\.toml holds no reading yet.*"
                                         r"strict=True"):
        parser_for(_choosing("vi"))
    assert "do" not in parser_for(_choosing("vi"), strict=True).lexicon._sets.particles


def test_md_stays_out_of_a_strict_choice_that_does_not_read_en() -> None:
    # `md` stays in en.toml (#1005): a leading Md abbreviates Muhammad
    # (#853), and after a family comma a strict choice reading `md`
    # from mul.toml took the given name as a credential
    bn = parser_for(_choosing("bn"), strict=True)
    for text, given, middle in (("Rahman, Md", "Md", ""),
                                ("Rahman, MD", "MD", ""),
                                ("Karim, Md Abdul", "Md", "Abdul")):
        got = bn.parse(text)
        assert (got.given, got.middle, got.suffix) == (given, middle, ""), text
    assert bn.parse("Md Rahman").given == "Md"


def test_a_caller_removes_a_mul_word_as_any_other() -> None:
    # a mul.toml reading is a default reading like any other: a caller's
    # remove drops it, with or without a choice, strict included (#1005)
    kept = parser_for(_choosing("pt"), strict=True)
    assert kept.parse("Ana Souza, PhD").suffix == "PhD"
    assert kept.parse("Dr Ana Souza").title == "Dr"
    lexicon = Lexicon.default().remove("phd", kind="credential")
    assert Parser(lexicon=lexicon).parse("Ana Souza, PhD").given == "PhD"
    for strict in (False, True):
        got = parser_for(_choosing("pt"), base=Parser(lexicon=lexicon),
                         strict=strict)
        assert got.parse("Ana Souza, PhD").given == "PhD"
    stripped = kept.lexicon.remove("dr", kind="academic")
    assert Parser(lexicon=stripped).parse("Dr Ana Souza").given == "Dr"


def test_a_strict_choice_still_refuses_mul_and_an_unknown_tag() -> None:
    for tag, match in (("mul", "every choice, plain or strict, keeps"),
                       ("xx", "no vocabulary file holds")):
        with pytest.raises(ValueError, match=match):
            parser_for(_choosing(tag), strict=True)


def test_strict_is_a_bool() -> None:
    with pytest.raises(TypeError, match="strict must be True or False"):
        parser_for(_choosing("ko"), strict=1)  # type: ignore[arg-type]


def test_a_strict_choice_keeps_a_callers_readings_over_the_union(
        ) -> None:
    # a caller's reading of a word strict drops stays, as one of a word
    # no file holds does (superseding 3j's clause that the delta dropped
    # it, decisions/vocabulary-model, 2026-11-02 #754, item 4); the
    # union, then strict
    base = Parser(lexicon=Lexicon.default().add("rev", "zzq", kind="title"))
    got = parser_for(_choosing("vi"), base=base, strict=True).lexicon._sets
    assert {"zzq", "rev"} <= got.titles
    assert "rev" not in parser_for(_choosing("vi"), strict=True).lexicon._sets.titles
    ko, en = _choosing("ko", code="aa"), _choosing("en", code="bb")
    assert (parser_for(ko, en, strict=True).lexicon
            == parser_for(en, ko, strict=True).lexicon
            == parser_for(_choosing("ko", "en"), strict=True).lexicon)


def test_a_packs_fragment_is_unioned_on_after_the_strict_compile() -> None:
    pack = _choosing("ko", lexicon=Lexicon.empty().add("ra", kind="credential"))
    assert parser_for(pack, strict=True).parse("Kim Min Ra").suffix == "Ra"


def _choice_tags() -> list[tuple[str, bool]]:
    from nameparser._reading_index import UNCHOOSABLE, files, tags
    return ([(t, False) for t in sorted(tags() - UNCHOOSABLE)]
            + [(t, True) for t in sorted(files() - UNCHOOSABLE)])


#: The lexicons a choice is filtered under: the default, the empty one,
#: and one a caller configured (a removed gate, an added title, two
#: added particles, one of them a word a choice turns a suffix on for)
_CHOICE_BASES = {
    "default": lambda: Lexicon.default(),
    "empty": lambda: Lexicon.empty(),
    "configured": lambda: Lexicon.default().remove("van", "dean", kind="given")
    .add("dean", kind="title").add("zzz", "st", kind="preposition"),
}


@pytest.mark.parametrize("tag,strict", _choice_tags(),
                         ids=lambda v: str(v))
def test_a_choice_moves_only_the_words_the_callers_log_leaves_alone(
        tag: str, strict: bool) -> None:
    # 4i-c filters the base's readings by the choice and applies the
    # caller's log after it (decisions/vocabulary-model, 2026-11-02
    # #754, item 4): for every single file tag a choice may name, plain
    # and strict, the default under the choice compiles as the shipped
    # index does under it, the empty lexicon stays empty, and a
    # configured lexicon differs from the choice alone only in entries
    # holding a word its log names
    from nameparser._lexicon import _NO_SETS, _built, _fields_of, _vocab_fields
    from nameparser._reading_index import compile_choice, selected
    chosen = selected(frozenset({tag}), strict=strict)
    want = _vocab_fields(compile_choice(chosen, strict))
    for name, build in _CHOICE_BASES.items():
        lexicon = build()
        got = dataclasses.replace(lexicon, _languages=frozenset({tag}),
                                  _strict=strict)
        assert got.languages == {tag} and got.strict is strict
        sets = _fields_of(got._sets)
        if name == "empty":
            assert sets == _fields_of(_NO_SETS), name
            continue
        if name == "default":
            # the shortcut every pack takes, and the compile it stands for
            assert sets == _fields_of(want), name
            assert _fields_of(_built("default", (), chosen, strict)[1]) == sets
            continue
        touched = {w for e in lexicon._edits for w in e.words}
        for field, words in sets.items():
            def kept(entries: frozenset[str]) -> frozenset[str]:
                return frozenset(e for e in entries
                                 if not touched & set(e.split()))
            assert kept(words) == kept(want[field]), (name, field)
