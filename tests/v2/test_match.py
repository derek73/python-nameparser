"""Name matching: the settings object, the result types, the check
and the grouping keys, with the symmetry and key-guarantee properties
held over one shared parsed grid (NAMES)."""
from __future__ import annotations

import dataclasses
import functools
import itertools
import pickle
import re
import unicodedata

import pytest

import nameparser
from nameparser import (
    Lexicon,
    FAMILY_FIRST,
    ParsedName,
    Parser,
    Policy,
    Role,
    locales,
    parse,
    parser_for,
)
from nameparser._pipeline._vocab import _HYPHEN_CHARS
from nameparser._match import (
    DEFAULT_ACCEPT,
    CrossRoleMatch,
    Matching,
    MatchResult,
    Outcome,
    RoleMatch,
    Side,
    _PARSER_FIELDS,
    _RULES,
    _fold,
    _spelling_keys,
)

#: Every name string the check's tests compare; the symmetry test runs
#: every ordered pair of them.
NAMES: tuple[str, ...] = (
    "John A. Smith", "John Smith", "J. Smith", "John Smith Jr.",
    "John Smith Sr.", "María Vega", "MARIA VEGA", "Mari\u0301a Vega",
    "Wm. Smith", "William Smith", "Juan de la Vega", "Juan Vega",
    "SELENNA AGNES DE MELO SCHMITT", "SELENNA AGNES DE MELO SCHMITT E BRAGA",
    "Ann Smith-Jones", "Ann Smith", "J.-P. Dupont", "Jean-Pierre Dupont",
    "Cristiane S", "Cristiane Stallbaum", "Mr. Smith", "Dr. John Smith",
    "Mr. John Smith", "John Smith PhD", "James Smith", "Suharto", "",
    "김민준", "王小明", "王小", "John Smith Junior", "John A. B. Smith",
    "John Anne Beth Smith", "John A. Beth Smith", "John Anne Smith",
    "कुमार सिंह", "कमार सिंह", "हंस सिंह", "हस सिंह",
    "Ana dos Santos", "Ana Dos", "Jan van der Berg", "Jan Van",
    "Maria da Silva", "Maria Da", "John bin Laden", "John Bin",
    "Ana Jo", "Ana José", "Ana Ma", "Ana María", "Maria Mà", "Maria Ma",
    "Hong Guo", "Hong-Yi Guo", "Yi Guo", "Mr. S", "John Stallbaum",
    "Van Gogh", "Gogh", "Vincent Van Gogh", "JOHN SMITH MA", "Sukarno",
    "Dean Gogh", "Dean Smith", "Della Smith", "Mary Smith",
    "J. Edgar Hoover", "Edgar Hoover", 'William "Bill" Clinton',
    "Bill Clinton", "Jane Doe (née Smith)", "Jane Smith", "John E. Hoover",
    "Allan Hoover", "Jane Brown", "Jane Doe", "Jane S", "Hong-Yi Hoover",
    "John Hong Hoover", "Alice Smith", "Ann A. Smith", "E. Hoover",
    "John Edgar Hoover", "Edgar E. Hoover", "John Edgar Allan Hoover",
    "Edgar Allan Hoover", 'Robert "Bobby Joe" Smith', "Bobby Joe Smith",
    "Bobby Smith", "John Wm. Smith", "John Smith, PhD",
    "Ahmed Al", "Ahmed Al-Saud", "Ahmed Saud",
    "Pat O'Brien", "O\u2019Brien, Pat", "Pat O\u02bcBrien",
    "Jo Garcia", "Jose Garcia", "José Garcia", "Ma. Santos", "Maria Santos",
    "Ma. Cruz", "MARIA CRUZ", "Ma, Jack", "María, Jack", "Ma Cruz",
    "María Cruz", "Junior Smith", "Jr Smith", "Sr. John Smith",
    "Señor John Smith", "Senhor John Smith", "John J.-P. Smith", "J.-P. Smith",
    "Anne J.-P. Smith", "Jo. Garcia", "Joanne Garcia", "Ma Santos",
    "María Santos", "Jas Singh", "Jas. Singh", "James Singh", "Wm Smith",
    "WM SMITH", "WILLIAM SMITH", "Ana Mà. Cruz", "Ana María Cruz",
    "Garcia, Jo.", "Garcia, José", "Ana Ma\u0300. Cruz",
    "Max Smith", "Maximilian Smith", "Maxim Smith", "Maxwell Smith",
    "Bill Smith", "BILL SMITH", "Sepp Huber", "Josef Huber", "Bob Smith",
    "Robert Smith", "John Bill Smith", "John William Smith",
    'Robert "Bob" Smith', "Smith, Bill", "Masha Ivanova", "Maria Ivanova",
    "Yuliya Ivanova", "Iuliia Ivanova",
    # a keyboard's spelling (2026-11-12 A KEYBOARD'S SPELLING IS FOLDED)
    "Łukasz Nowak", "Lukasz Nowak", "Hans Müller", "Hans Mueller",
    # any of the pipeline's hyphens, and a maiden name's particles (#1264)
    "Ann Smith\u2010Jones", "Ann Smith\u2013Jones", "Jean\u2010Pierre Dupont",
    "Ana Ruiz (née de la Vega)", "Ana Ruiz (née Vega)",
    "Ana Ruiz (née de la Vega Gómez)", "Ana Ruiz (née Vega\u2013Gómez)",
)

#: NAMES parsed once by the default parser, for the grid tests, so a
#: pair's check under each setting re-parses nothing.
PARSED: tuple[ParsedName, ...] = tuple(Parser().parse(n) for n in NAMES)

#: The opt-in outcomes this module's settings sweep adds to the default.
OPT_INS: tuple[Outcome, ...] = (
    Outcome.ALTERNATE_SPELLING, Outcome.FAMILIAR_FORM, Outcome.FAMILY_INITIAL,
    Outcome.GIVEN_ONE_SIDE,
    Outcome.HYPHENATED_PART, Outcome.ACROSS_ROLES,
)

#: The settings the guarantee and the symmetry are held under, each an
#: accept set and the other-readings switch: the default, each opt-in
#: added to it alone, the switch on alone, and all of them together.
SETTINGS: tuple[tuple[frozenset[Outcome], bool], ...] = (
    (DEFAULT_ACCEPT, False),
    *((DEFAULT_ACCEPT | {o}, False) for o in OPT_INS),
    (DEFAULT_ACCEPT, True),
    (DEFAULT_ACCEPT | set(OPT_INS), True),
)
_SETTING_IDS = ["default", *(o.value for o in OPT_INS), "other-readings", "all"]

m = Matching(Parser())


def role(r: MatchResult, which: Role) -> RoleMatch:
    return next(x for x in r.roles if x.role is which)


def _result() -> MatchResult:
    return MatchResult(
        consistent=True,
        roles=tuple(
            RoleMatch(role, Outcome.INITIAL, "J.", "John", Side.RIGHT)
            for role in Role
        ),
    )


def test_accept_rejects_a_bare_string() -> None:
    with pytest.raises(TypeError, match="iterable of outcome names"):
        Matching(Parser(), accept="initial")  # type: ignore[arg-type]


def test_accept_rejects_a_mapping() -> None:
    with pytest.raises(TypeError, match="iterable of outcome names"):
        Matching(Parser(), accept={"initial": 1})  # type: ignore[arg-type]


def test_accept_rejects_a_non_iterable() -> None:
    with pytest.raises(TypeError, match="iterable of outcome names"):
        Matching(Parser(), accept=3)  # type: ignore[arg-type]


def test_accept_rejects_a_non_outcome_member() -> None:
    with pytest.raises(TypeError, match="iterable of outcome names"):
        Matching(Parser(), accept={3})  # type: ignore[arg-type]


def test_parser_must_be_a_parser() -> None:
    with pytest.raises(TypeError, match="Parser"):
        Matching("nope")  # type: ignore[arg-type]


def test_accept_rejects_an_unknown_outcome_naming_the_valid_ones() -> None:
    with pytest.raises(ValueError, match="'nickname-table'.*family-initial"):
        Matching(Parser(), accept={"nickname-table"})  # type: ignore[arg-type]


def test_conflict_cannot_be_accepted() -> None:
    for spelling in ("conflict", Outcome.CONFLICT):
        with pytest.raises(ValueError, match="conflict"):
            Matching(Parser(), accept={spelling})  # type: ignore[arg-type]


def test_accept_takes_strings_or_outcomes() -> None:
    expected = {Outcome.FAMILY_INITIAL, Outcome.SAME}
    assert Matching(Parser(), accept={"family-initial"}).accept == expected  # type: ignore[arg-type]
    assert Matching(Parser(), accept=[Outcome.FAMILY_INITIAL]).accept == expected  # type: ignore[arg-type]


def test_passing_accept_replaces_the_default() -> None:
    assert Matching(Parser(), accept=set()).accept == {Outcome.SAME}  # type: ignore[arg-type]


def test_the_default_accepts_what_the_spec_lists() -> None:
    assert DEFAULT_ACCEPT == {
        Outcome.SAME, Outcome.FOLDED, Outcome.JOINED,
        Outcome.LISTED_SPELLING, Outcome.PARTICLES_ASIDE,
        Outcome.PART_OF_OTHER, Outcome.INITIAL,
        Outcome.INITIALS_AGREE, Outcome.ONE_SIDE,
        Outcome.GENERATION_ONE_SIDE, Outcome.NOTED,
    }
    assert Matching(Parser()).accept == DEFAULT_ACCEPT


def test_outcomes_are_declared_strongest_first() -> None:
    names = [o.value for o in Outcome]
    assert names[0] == "same" and names[-1] == "conflict"
    assert len(names) == 18


def test_match_types_round_trip_through_pickle() -> None:
    matching = Matching(Parser(), accept={"initial"})  # type: ignore[arg-type]
    across = _with(Outcome.ACROSS_ROLES).check("J. Edgar Hoover", "Edgar Hoover")
    assert across.across
    for obj in (matching, _result(), _result().roles[0], across,
                across.across[0]):
        assert pickle.loads(pickle.dumps(obj)) == obj


def test_cross_role_match_is_exported_beside_the_other_match_types() -> None:
    assert nameparser.CrossRoleMatch is CrossRoleMatch
    assert "CrossRoleMatch" in nameparser.__all__


def test_mirrored_swaps_text_and_sides() -> None:
    mirrored = _result().mirrored()
    assert mirrored.consistent
    first = mirrored.roles[0]
    assert (first.left, first.right, first.more) == ("John", "J.", Side.LEFT)
    assert [m.role for m in mirrored.roles] == list(Role)
    assert mirrored.mirrored() == _result()


def test_mirrored_swaps_the_roles_and_texts_of_a_cross_role_match() -> None:
    cross = CrossRoleMatch(Role.MIDDLE, Role.GIVEN, Outcome.SAME, "Edgar", "Ed")
    result = MatchResult(True, _result().roles, (cross,))
    assert result.mirrored().across == (
        CrossRoleMatch(Role.GIVEN, Role.MIDDLE, Outcome.SAME, "Ed", "Edgar"),)
    assert result.mirrored().mirrored() == result
    assert _result().across == ()


def test_mirrored_keeps_neither() -> None:
    rows = tuple(RoleMatch(r, Outcome.SAME, "a", "a", Side.NEITHER)
                 for r in Role)
    result = MatchResult(True, rows)
    assert result.mirrored().roles[0].more is Side.NEITHER


def test_matching_repr_shows_only_the_deviation() -> None:
    assert repr(Matching(Parser())) == "Matching(default)"
    assert repr(Matching(
        Parser(), DEFAULT_ACCEPT | {Outcome.FAMILY_INITIAL},
    )) == "Matching(default + family-initial)"
    assert repr(Matching(
        Parser(), DEFAULT_ACCEPT - {Outcome.NOTED, Outcome.INITIAL},
    )) == "Matching(default - initial, noted)"
    assert repr(Matching(
        Parser(), (DEFAULT_ACCEPT - {Outcome.NOTED}) | {Outcome.ACROSS_ROLES},
    )) == "Matching(default + across-roles - noted)"
    assert repr(Matching(Parser(), other_readings=True)) == (
        "Matching(default + other-readings)")
    assert repr(Matching(
        Parser(), (DEFAULT_ACCEPT - {Outcome.NOTED}) | {Outcome.ACROSS_ROLES},
        other_readings=True,
    )) == "Matching(default + across-roles, other-readings - noted)"


def test_matching_repr_shows_a_parser_that_is_not_the_default() -> None:
    # by the parser's own bounded repr, and only where it deviates
    # (#1264), so the default matcher's repr is unchanged
    assert repr(parser_for(locales.ES).matching()) == (
        f"Matching(default, parser={parser_for(locales.ES)!r})")
    two = Parser(policy=Policy(two_family_names=True))
    assert repr(two.matching(accept=two.matching().accept | {"across-roles"})) == (
        "Matching(default + across-roles, "
        "parser=Parser(Lexicon(default), Policy(two_family_names=True)))")
    assert repr(Parser(lexicon=Lexicon.default()).matching()) == (
        "Matching(default)")


def test_a_parse_only_object_is_refused_at_construction() -> None:
    # eager: an object with a `parse` but no lexicon would fail only at
    # its first check() or keys()
    class Bare:
        def parse(self, text: str) -> ParsedName:
            return parse(text)

    with pytest.raises(TypeError, match="parser must be a Parser, got Bare"):
        Matching(Bare())  # type: ignore[arg-type]


def test_matching_repr_names_a_parser_subclass_by_its_class() -> None:
    # a subclass's repr and equality are unbounded and unchecked, so it
    # is shown by its class name, never compared
    class Sub(Parser):
        def __repr__(self) -> str:
            return "x" * 50_000

    # a default subclass too: its fields are not compared
    assert repr(Matching(Sub())) == "Matching(default, parser=Sub)"
    assert repr(Matching(Sub(policy=Policy(two_family_names=True)))) == (
        "Matching(default, parser=Sub)")

    class Raising(Policy):
        def __eq__(self, other: object) -> bool:
            raise RuntimeError("never compared")

        __hash__ = Policy.__hash__

    # a Parser holding a subclass of Policy is not compared either
    assert repr(Matching(Parser(policy=Raising()))) == (
        "Matching(default, parser=Parser)")
    # nor is a Parser missing a field, built past its constructor
    assert repr(Matching(object.__new__(Parser))) == (
        "Matching(default, parser=Parser)")


def test_the_repr_compares_every_field_of_parser() -> None:
    # a field added to Parser must join _PARSER_FIELDS, or a parser
    # differing only in it would read as the default
    assert _PARSER_FIELDS == tuple(f.name for f in dataclasses.fields(Parser))


def test_matching_repr_shows_a_parser_with_a_segmenter() -> None:
    def cut(text: str) -> None:
        return None

    assert repr(Parser(segmenter=cut).matching()) == (
        "Matching(default, parser=Parser(Lexicon(default), Policy(), "
        "segmenter=test_matching_repr_shows_a_parser_with_a_segmenter."
        "<locals>.cut))")


def test_other_readings_is_off_by_default_and_passed_through() -> None:
    assert Matching(Parser()).other_readings is False
    parser = Parser()
    switched = parser.matching(other_readings=True)
    assert switched.other_readings is True
    assert switched.accept == DEFAULT_ACCEPT
    assert switched == Matching(parser, DEFAULT_ACCEPT, other_readings=True)
    assert pickle.loads(pickle.dumps(switched)) == switched


@pytest.mark.parametrize("value", [1, "yes", None])
def test_other_readings_must_be_a_bool(value: object) -> None:
    with pytest.raises(TypeError, match="other_readings must be a bool.*"
                       "pass other_readings=True or other_readings=False"):
        Matching(Parser(), other_readings=value)  # type: ignore[arg-type]


_OFFERED_SWITCH = "parser.matching(other_readings=True)"


def test_other_reading_in_accept_offers_the_switch() -> None:
    parser = Parser()
    with pytest.raises(ValueError) as caught:
        parser.matching(accept=parser.matching().accept | {"other-reading"})
    message = str(caught.value)
    assert "'other-reading' is not an outcome" in message
    assert message.endswith(f"e.g. {_OFFERED_SWITCH}")
    # the offered code runs and switches the search on
    offered = eval(message.split("e.g. ")[1], {"parser": parser})
    assert offered.other_readings and offered.accept == DEFAULT_ACCEPT
    # and type-checks, the same spelling written out for mypy
    assert parser.matching(other_readings=True) == offered


def test_a_tatweel_stretching_a_name_is_no_difference() -> None:
    """#1151: `_normalize` deletes the tatweel, so the match's fold does
    too; otherwise the vocabulary links a stretched spelling to the plain
    one as a listed spelling that no list holds."""
    result = Parser().matching().check("محمـــد علي", "محمد علي")
    assert result.consistent
    given = next(r for r in result.roles if r.role is Role.GIVEN)
    assert given.outcome is Outcome.FOLDED


def test_fold_drops_case_accents_and_periods_but_keeps_hyphens() -> None:
    assert _fold("J.-P. O'Mári\u0301a") == "j-p omaria"
    assert _fold("María") == _fold("Mari\u0301a") == "maria"


@pytest.mark.parametrize("hyphen", list(_HYPHEN_CHARS))
def test_fold_writes_every_hyphen_of_the_pipeline_as_the_hyphen_minus(
        hyphen: str) -> None:
    # rules/O6's joiners, the set the pipeline reads (#1264)
    assert _fold(f"Smith{hyphen}Jones") == "smith-jones"


def test_fold_is_idempotent_and_keeps_hyphens_over_every_code_point() -> None:
    # The key guarantee rests on these two: keys fold a spelling set's
    # members again, and a family word's hyphen halves are cut from the
    # raw word by position (_spelling_keys, _family_words), at any of
    # the pipeline's hyphens, each folding to the hyphen-minus. Every
    # assigned code point is folded alone, after a letter, beside a
    # hyphen on either side, and with a combining mark after it behind a
    # Latin letter, a hyphen and a Devanagari letter (an unassigned one
    # has no decomposition, case or mark to fold). The mark contexts
    # found the micro sign U+00B5 and U+2183, which casefold into Greek
    # and Latin, and a full stop or apostrophe before a mark (review of
    # #1221). Measured 2026-11-08: about 6 s serial on py3.11, the module's
    # heaviest test; 2026-11-11, with the hyphen set counted (#1264),
    # 10 to 16 s against the merge base's 6 to 10 s run in the same
    # minutes, under a load average near 20.
    bad = []
    for i in range(0x110000):
        c = chr(i)
        if unicodedata.category(c) in ("Cn", "Cs"):
            continue
        for text in (c, "a" + c, c + "-a", "-" + c, c + " x",
                     "a" + c + "\u0301", "-" + c + "\u0301",
                     "\u0915" + c + "\u0301"):
            folded = _fold(text)
            # a hyphen of `_HYPHEN_CHARS` folds to the hyphen-minus
            # (#1264), so it is the set that is counted
            if (_fold(folded) != folded or _hyphens(folded) != _hyphens(text)
                    or folded.count(" ") != text.count(" ")):
                bad.append((hex(i), text, folded))
    assert bad == []


def _hyphens(text: str) -> int:
    """How many of the pipeline's hyphens `text` holds."""
    return sum(text.count(h) for h in _HYPHEN_CHARS)


def test_fold_reads_a_letters_script_before_and_after_casefolding() -> None:
    # the micro sign casefolds into Greek and U+2183 into Latin, so their
    # marks are accents; the iota subscript stays a mark; U+0149 casefolds
    # to an apostrophe and n; a full stop before a mark moves the mark onto
    # the letter before it
    assert _fold("\u00b5\u0301") == "\u03bc"
    assert _fold("\u2183\u0301") == "\u2184"
    assert _fold("\u1fb3") == _fold("\u03b1\u0345") == "\u03b1"
    assert _fold("\u0149") == "n"
    assert _fold("a.\u0301") == "a"


def test_the_table_has_one_entry_per_role_in_role_order() -> None:
    assert [x.role for x in m.check("John Smith", "John Smith").roles] == list(Role)


def test_check_takes_a_parsed_name() -> None:
    assert m.check(parse("John Smith"), "John Smith").consistent


def test_check_rejects_a_non_name() -> None:
    with pytest.raises(TypeError, match="ParsedName"):
        m.check(3, "John Smith")  # type: ignore[arg-type]


def test_a_missing_middle_name_is_consistent_and_says_which_side() -> None:
    r = m.check("John A. Smith", "John Smith")
    assert r.consistent
    assert (role(r, Role.MIDDLE).outcome, role(r, Role.MIDDLE).more) == (Outcome.ONE_SIDE, Side.LEFT)


def test_an_initial_against_a_name_is_consistent() -> None:
    r = m.check("J. Smith", "John A. Smith")
    assert r.consistent and role(r, Role.GIVEN).outcome is Outcome.INITIAL
    assert role(r, Role.GIVEN).more is Side.RIGHT


def test_different_generations_conflict() -> None:
    assert not m.check("John Smith Jr.", "John Smith Sr.").consistent


def test_a_generation_on_one_side_is_its_own_outcome() -> None:
    r = m.check("John Smith", "John Smith Jr.")
    assert r.consistent and role(r, Role.SUFFIX).outcome is Outcome.GENERATION_ONE_SIDE


def test_a_generation_on_one_side_is_its_outcome_whatever_the_credentials() -> None:
    # a credential beside it is only noted where the generations agree
    r = m.check("John Smith Jr.", "John Smith, PhD")
    assert r.consistent
    assert role(r, Role.SUFFIX).outcome is Outcome.GENERATION_ONE_SIDE
    without = Matching(Parser(), DEFAULT_ACCEPT - {Outcome.GENERATION_ONE_SIDE})
    assert not without.check("John Smith Jr.", "John Smith, PhD").consistent
    assert not without.check("John Smith, PhD", "John Smith Jr.").consistent


def test_folding_ignores_case_and_accents() -> None:
    assert role(m.check("María Vega", "MARIA VEGA"), Role.GIVEN).outcome is Outcome.FOLDED


def test_fold_treats_nfc_and_nfd_alike() -> None:
    assert m.check("María Vega", "Mari\u0301a Vega").consistent


def test_listed_spellings_are_consistent() -> None:
    assert role(m.check("Wm. Smith", "William Smith"), Role.GIVEN).outcome is Outcome.LISTED_SPELLING


def test_particles_are_set_aside() -> None:
    assert role(m.check("Juan de la Vega", "Juan Vega"), Role.FAMILY).outcome is Outcome.PARTICLES_ASIDE


def test_the_armenian_ter_prefix_is_a_particle_set_aside() -> None:
    # տեր is a rank particle (#1225): the spaced Տեր- surname sets it
    # aside against the bare surname, and a hyphen half that is a listed
    # particle is no key of its own, so every Տեր- surname does not share
    # one keyed on the prefix and the initial alone
    r = m.check("Զավեն Տեր Եղիյան", "Զավեն Եղիյան")
    assert r.consistent and role(r, Role.FAMILY).outcome is Outcome.PARTICLES_ASIDE
    assert m.keys("Լևոն Տեր-Պետրոսյան") == {
        "պետրոսյան;լ", "տերպետրոսյան;լ", "տեր-պետրոսյան;լ"}


@pytest.mark.parametrize("a, b", [
    ("Juan de la Vega", "Juan Marcos Vega"),
    ("Զավեն Տեր Եղիյան", "Զավեն Մարկոս Եղիյան"),
])
def test_a_set_aside_particle_leaves_another_middle_name_one_side(
        a: str, b: str) -> None:
    # the spaced Տեր reads as de la Vega does (#1225): with the particle
    # set aside the middle the other side holds is one side's, where on
    # 3.0.1 the middle Տեր conflicted with it
    for x, y in ((a, b), (b, a)):
        r = m.check(x, y)
        assert r.consistent and r["family"].outcome is Outcome.PARTICLES_ASIDE, (x, y)


def test_a_cut_short_surname_list_is_part_of_the_other() -> None:
    r = m.check("SELENNA AGNES DE MELO SCHMITT", "SELENNA AGNES DE MELO SCHMITT E BRAGA")
    assert r.consistent and role(r, Role.FAMILY).outcome is Outcome.PART_OF_OTHER


def test_a_hyphenated_surname_against_one_half_is_part_of_the_other() -> None:
    assert role(m.check("Ann Smith-Jones", "Ann Smith"), Role.FAMILY).outcome is Outcome.PART_OF_OTHER


def test_hyphenated_initials_match_their_hyphenated_name() -> None:
    assert role(m.check("J.-P. Dupont", "Jean-Pierre Dupont"), Role.GIVEN).outcome is Outcome.INITIAL


def test_a_family_initial_is_not_consistent_by_default() -> None:
    r = m.check("Cristiane S", "Cristiane Stallbaum")
    assert not r.consistent
    assert role(r, Role.FAMILY).outcome is Outcome.FAMILY_INITIAL


def test_a_missing_given_name_is_not_consistent_by_default() -> None:
    r = m.check("Mr. Smith", "John Smith")
    assert not r.consistent
    assert role(r, Role.GIVEN).outcome is Outcome.GIVEN_ONE_SIDE


def test_titles_and_credentials_never_conflict() -> None:
    assert m.check("Dr. John Smith", "Mr. John Smith").consistent
    assert m.check("John Smith PhD", "John Smith").consistent


def test_different_given_names_conflict() -> None:
    assert role(m.check("John Smith", "James Smith"), Role.GIVEN).outcome is Outcome.CONFLICT


def test_a_name_with_no_family_is_consistent_with_nothing_by_default() -> None:
    assert not m.check("Suharto", "Suharto").consistent
    assert not m.check("", "").consistent


def test_cjk_names_compare_as_same_and_never_as_initials() -> None:
    assert m.check("김민준", "김민준").consistent
    assert role(m.check("王小明", "王小"), Role.GIVEN).outcome is not Outcome.INITIAL


@pytest.mark.parametrize("setting", SETTINGS, ids=_SETTING_IDS)
def test_the_check_is_symmetric(
        setting: tuple[frozenset[Outcome], bool]) -> None:
    matching = Matching(Parser(), *setting)
    for a, b in itertools.product(PARSED, repeat=2):
        result = matching.check(a, b)
        assert matching.check(b, a) == result.mirrored(), (
            a.original, b.original)


def test_a_single_han_character_is_never_an_initial() -> None:
    base = parse("John Smith")
    r = m.check(base.replace(given="小"), base.replace(given="小明"))
    assert role(r, Role.GIVEN).outcome is Outcome.CONFLICT


def test_a_burmese_letter_is_never_an_initial() -> None:
    """rules/R7 (#1234): Burmese writes no initials, so a Burmese letter
    with or without its period is a whole name, on either side: Kyaw
    (က) and Kyi (ကြည်) conflict, where 3.0.1 read the one as the
    other's initial."""
    for a, b in (("က. Smith", "ကြည် Smith"), ("က ဇော ဦး", "ကြည် ဇော ဦး")):
        for x, y in ((a, b), (b, a)):
            assert role(m.check(x, y), Role.GIVEN).outcome is Outcome.CONFLICT
    assert role(m.check("J. Smith", "John Smith"), Role.GIVEN).outcome \
        is Outcome.INITIAL


def test_initials_written_apart_agree_with_the_same_initials_joined() -> None:
    base = parse("John Smith")
    r = m.check(base.replace(given="J.-P."), base.replace(given="J. P."))
    assert r.consistent and role(r, Role.GIVEN).outcome is Outcome.INITIALS_AGREE


def test_a_listed_generation_spelling_does_not_conflict() -> None:
    r = m.check("John Smith Jr.", "John Smith Junior")
    assert r.consistent and role(r, Role.SUFFIX).outcome is Outcome.LISTED_SPELLING


def test_a_middle_name_compares_word_by_word_taking_the_weakest() -> None:
    r = m.check("John A. B. Smith", "John Anne Beth Smith")
    assert role(r, Role.MIDDLE).outcome is Outcome.INITIAL
    r = m.check("John A. Beth Smith", "John Anne Smith")
    assert role(r, Role.MIDDLE).outcome is Outcome.ONE_SIDE


def test_fold_keeps_a_mark_that_spells_an_indic_letter() -> None:
    # the virama, anusvara and vowel signs are Mn but spelling, not accent
    assert _fold("क्ष") != _fold("कष")
    assert _fold("Ελένη") == _fold("Ελενη") and _fold("Йо") == _fold("Ио")


def test_a_devanagari_vowel_sign_is_not_folded_away() -> None:
    r = m.check("कुमार सिंह", "कमार सिंह")
    assert not r.consistent and role(r, Role.GIVEN).outcome is Outcome.CONFLICT


def test_a_devanagari_anusvara_is_not_folded_away() -> None:
    r = m.check("हंस सिंह", "हस सिंह")
    assert not r.consistent and role(r, Role.GIVEN).outcome is Outcome.CONFLICT


def test_default_keys_are_family_words_with_the_given_initial() -> None:
    # the base's words, and the whole family joined, particles kept
    assert m.keys("Jane A. de la Vega") == {"vega;j", "delavega;j"}
    # a hyphenated word is keyed by each half, joined, and whole
    assert m.keys("Ann Smith-Jones") == {
        "smith;a", "jones;a", "smithjones;a", "smith-jones;a"}
    assert m.keys("Suharto") == frozenset()


@pytest.mark.parametrize("setting", SETTINGS, ids=_SETTING_IDS)
def test_consistent_names_always_share_a_key(
        setting: tuple[frozenset[Outcome], bool]) -> None:
    """The guarantee, over every ordered pair of NAMES, under the default,
    each opt-in added to it alone and all of them together: a consistent
    pair shares a key, so grouping by key never separates names `check`
    accepts. Each setting must find a consistent pair of two different
    names, or the guarantee holds vacuously. The negative controls,
    each mutation's first failing pair under each setting, are
    `_RECORDED_CONTROLS`, which says when they were taken and holds each
    pair to still being one the guarantee is about.
    hyphenated-part adds no key, its halves sharing the given initial.
    Two keys no pair of NAMES needs, each failing a named test when
    removed (re-taken 2026-11-09): the whole hyphenated word's
    spellings (test_a_hyphenated_listed_spelling_shares_a_key, under a
    caller's hyphenated full form, and the two key-content tests of
    hyphenated family words) and the spellings read from the folded
    word (test_a_listed_spelling_holds_whatever_the_accents, "Ana Mà.
    Cruz"). The period rule moves no pair here: with the period test
    removed from `_spellings`, the bare word's links restored, this
    test and the symmetry test pass under every setting, since the
    check and the keys read the one spelling set, while
    test_a_name_of_its_own_written_bare_is_itself (four rows) and
    test_a_bare_name_of_its_own_is_not_keyed_by_its_long_form fail."""
    default = None if setting == SETTINGS[0] else Matching(Parser())
    _assert_the_key_guarantee(Matching(Parser(), *setting), PARSED, default)


def _assert_the_key_guarantee(matching: Matching,
                              parsed: tuple[ParsedName, ...],
                              default: Matching | None = None,
                              symmetric: bool = False) -> None:
    """Every consistent ordered pair of `parsed` shares a key, at least
    one such pair is of two different names, and, given the `default`
    matcher, at least one such pair of two different names is one it
    refuses, so a setting that adds to the default reaches the grid at
    all. With `symmetric`, each pair's check is also held to the mirror
    of the swapped pair's, from the one result."""
    found = beyond = False
    for a, b in itertools.product(parsed, repeat=2):
        result = matching.check(a, b)
        if symmetric:
            assert matching.check(b, a) == result.mirrored(), (
                a.original, b.original)
        if result.consistent:
            assert matching.keys(a) & matching.keys(b), (a.original, b.original)
            found = found or a.original != b.original
            beyond = beyond or (default is not None
                                and a.original != b.original
                                and not default.check(a, b).consistent)
    assert found, f"no consistent pair of two names under {matching!r}"
    assert default is None or beyond, (
        f"no pair consistent under {matching!r} that {default!r} refuses")


#: The key guarantee's negative controls, for
#: test_consistent_names_always_share_a_key: for each mutation, what it
#: mutates (the keys, or the check, made to accept a pair the keys were
#: not cut for) and the first ordered pair of NAMES that fails the
#: guarantee under each setting of `_SETTING_IDS`, `None` where the
#: setting still passes, every setting not named passing too. Recorded
#: as prose from 2026-11-08, and re-taken 2026-11-11 (#1264) as data,
#: each mutation applied to `_match.py` and reverted, every pair as the
#: prose had it and the symmetry test passing under every one. Not
#: re-run here: a mutation edits `_match` from inside, so a re-take is
#: by hand, after any commit that moves NAMES, the keys or the check;
#: re-taken 2026-11-11 for #1264's names and hyphen fold, every pair
#: standing and the new mutation added. The alternate-spelling setting
#: (2026-11-12) stands in each older row beside familiar-form, as it
#: reads those mutations as familiar-form does: added, not re-taken, and
#: held by test_a_recorded_control_still_reaches_what_it_mutated; its own
#: mutation was taken. The maiden name's words, removed, once failed
#: across-roles and all-opt-ins on ("J. Smith", "Jane Doe (née
#: Smith)"), until #1261 keyed the maiden name whole, joined; those
#: keys are held since by
#: test_listed_compound_surnames_keep_the_key_guarantee_and_symmetry's
#: ("Ann Smith", "Ann Doe (née Schmidt)"), a listed spelling the whole
#: text cannot give.
_RECORDED_CONTROLS: dict[str, tuple[str, dict[str, tuple[str, str] | None]]] = {
    "only the joined form of a hyphenated word keyed": ("keys", {
        **dict.fromkeys(("default", "alternate-spelling", "familiar-form",
                         "given-one-side", "hyphenated-part",
                         "other-readings", "across-roles"),
                        ("Ann Smith-Jones", "Ann Smith")),
        **dict.fromkeys(("family-initial", "all"),
                        ("Ahmed Al-Saud", "Ahmed Saud")),
    }),
    "part-of-other keeping a hyphen half that is a particle the keys drop": ("check", {
        **dict.fromkeys(("default", "alternate-spelling", "familiar-form",
                         "given-one-side", "hyphenated-part",
                         "other-readings", "across-roles"),
                        ("Ahmed Al", "Ahmed Al-Saud")),
        # passed through the family-initial key
        "family-initial": None, "all": None,
    }),
    "the familiar forms' paired names left out of the given letters": ("keys", {
        # a listed spelling of the longer name; all passes it through
        # given-one-side's bare family keys
        "familiar-form": ("Wm. Smith", "Bill Smith"), "all": None,
    }),
    # taken 2026-11-12 with the alternate-spelling outcome, the keys'
    # alternate block removed: the main grid's one witness, whose
    # letters differ (an Aleksey / Alexey witness shared a key without
    # the block and caught nothing); all passes it through
    # given-one-side's bare family keys
    "the alternate spellings' paired names left out of the given letters": ("keys", {
        "alternate-spelling": ("Yuliya Ivanova", "Iuliia Ivanova"), "all": None,
    }),
    "the family-initial key removed": ("keys", {
        "family-initial": ("J. Smith", "Jane S"),
        "all": ("John A. Smith", "Mr. S"),
    }),
    "the bare family keys removed": ("keys", {
        "given-one-side": ("John A. Smith", "Mr. Smith"),
        "all": ("John A. Smith", "Mr. Smith"),
    }),
    "the other readings' keys removed": ("keys", {
        "other-readings": ("Mr. Smith", "Della Smith"),
        "all": ("Cristiane S", "Suharto"),
    }),
    "the middle words' given letters removed": ("keys", {
        # all passes it through given-one-side's bare family keys
        "across-roles": ("Wm. Smith", "John Wm. Smith"), "all": None,
    }),
    "the nickname's given letter removed": ("keys", {
        "across-roles": ('William "Bill" Clinton', "Bill Clinton"),
        "all": None,
    }),
    # the keys alone cutting a family word at the hyphen-minus, the check
    # at every hyphen (#1264): the narrowing on one side the grids catch
    "the keys' family words cut at the hyphen-minus alone": ("keys", {
        **dict.fromkeys(("default", "alternate-spelling", "familiar-form",
                         "given-one-side", "hyphenated-part",
                         "other-readings", "across-roles"),
                        ("Ann Smith", "Ann Smith\u2010Jones")),
        # passed through the family-initial key
        "family-initial": None, "all": None,
    }),
}


@pytest.mark.parametrize(
    "mutation, mutated, setting_id, pair",
    [(m_, side, s_, p_) for m_, (side, row) in _RECORDED_CONTROLS.items()
     for s_, p_ in row.items() if p_ is not None],
    ids=lambda v: v if isinstance(v, str) else None)
def test_a_recorded_control_still_reaches_what_it_mutated(
        mutation: str, mutated: str, setting_id: str,
        pair: tuple[str, str]) -> None:
    """Each recorded control's pair is still one the guarantee is about,
    under its setting as the code stands: where the mutation removed
    keys, a consistent pair sharing a key; where it made the check
    accept more, a pair the check refuses. A control that has stopped
    reaching what it was taken against shows here rather than going
    stale in place."""
    matching = Matching(Parser(), *SETTINGS[_SETTING_IDS.index(setting_id)])
    a, b = (PARSED[NAMES.index(n)] for n in pair)
    if mutated == "keys":
        assert matching.check(a, b).consistent
        assert matching.keys(a) & matching.keys(b)
    else:
        assert mutated == "check"
        assert not matching.check(a, b).consistent


def test_every_recorded_control_names_a_setting_of_the_sweep() -> None:
    assert _RECORDED_CONTROLS
    for side, row in _RECORDED_CONTROLS.values():
        assert side in ("keys", "check")
        assert row and set(row) <= set(_SETTING_IDS), row


#: Names the main grid does not hold, read under every parser of
#: `_SHAPE_PARSERS`: comma shapes (a full name, a one-word name and
#: nothing before the comma, a particle surname before it); names the
#: family-first order and the Spanish pack read differently from
#: `Parser()`, with a name each pairs them with
#: (test_each_shape_parser_reads_names_of_the_grid_its_own_way); and a
#: pair for each opt-in and the other-reading switch to find under
#: every parser beyond what its default matcher accepts (familiar form,
#: one-sided given name, hyphenated part, the lone `Smith`).
_SHAPE_NAMES: tuple[str, ...] = (
    "Smith, John", ", John", "de la Vega, Juan", "Juan de la Vega",
    "Vega, Juan", "Smith, J.", "John Smith", "J. Smith", "Smith John",
    "Smith J.", ", Smith", "Dr. Smith, John", "Smith, John Jr.",
    "Smith Jr., John", "Smith-Jones, Ann", "Ann Smith", "Smith-Jones Ann",
    "Smith Ann", "Juan Vega",
    "de la Vega, J.", "Jane Doe (née Smith)", "Smith, Jane",
    "García López, María", "María García López", "María García",
    "María López", "José Luis Pérez", "José Pérez", "Pérez, José Luis",
    "Wang Xiaoming", "Xiaoming Wang", "김민준", "Kim Min-jun",
    "Min-jun Kim", "Nguyễn Văn An", "Nguyen An", "Bill Smith",
    "William Smith", "Smith Bill", "Smith William", "Yuliya Smith",
    "Iuliia Smith", "Smith Yuliya", "Smith Iuliia", "Müller, Hans",
    "Mueller, Hans", "Hans Mueller", "Mr. Smith",
    "Della Smith", "Smith", "Hong Guo", "Hong-Yi Guo", "Guo Hong",
    "Guo Hong-Yi",
    # any of the pipeline's hyphens, and a maiden name's particles (#1264)
    "Smith\u2010Jones, Ann", "Ann Smith\u2013Jones", "Guo Hong\u2010Yi",
    "María López (née de la Vega)", "María López (née Vega)",
)

#: Names only one parser of `_SHAPE_PARSERS` reads differently from
#: the others, read under that parser alone, as a grid pairs a text
#: only with configurations that can read it differently: a Spanish
#: double surname the Spanish pack's given names leave whole, and Han
#: names the Chinese pack segments, written run together and spaced.
_PACK_NAMES: dict[str, tuple[str, ...]] = {
    "es": ("Juan Carlos Pérez Gómez", "Juan Carlos Pérez"),
    "zh": ("王小明", "王李小明", "王小", "李小明", "王 小明", "王李 小明"),
}

#: The parsers the shape grid is read under, beside the default.
_SHAPE_PARSERS: dict[str, Parser] = {
    "default": Parser(),
    "family-first": Parser(policy=Policy(name_order=FAMILY_FIRST)),
    "es": parser_for(locales.ES),
    "zh": parser_for(locales.ZH),
}


#: The shape grid's negative controls, taken 2026-11-11 (#1264) with
#: the mutations of `_RECORDED_CONTROLS` applied to `_match.py` one at
#: a time and reverted: for each mutation that fails a run, under each
#: parser of `_SHAPE_PARSERS`, the first failing ordered pair of
#: `_SHAPE_NAMES` under each setting that fails, every run not named
#: passing. The part-of-other mutation and the nickname's fail no run
#: of this grid. Re-taken 2026-11-11 for #1264's names and hyphen fold,
#: every pair standing and the new mutation added (24 runs). Not
#: re-run here, as `_RECORDED_CONTROLS` is not.
_FOUR = ("default", "family-first", "es", "zh")
_SHAPE_CONTROLS: dict[str, dict[str, dict[str, tuple[str, str]]]] = {
    "only the joined form of a hyphenated word keyed": {
        parser_id: dict.fromkeys(
            ("default", "alternate-spelling", "familiar-form",
             "given-one-side", "hyphenated-part", "across-roles",
             "other-readings"),
            ("Smith-Jones, Ann",
             "Smith Ann" if parser_id == "family-first" else "Ann Smith"))
        for parser_id in _FOUR
    },
    "the familiar forms' paired names left out of the given letters": {
        # all passes it through given-one-side's bare family keys
        parser_id: {"familiar-form": (
            ("Smith Bill", "Smith William") if parser_id == "family-first"
            else ("Bill Smith", "William Smith"))}
        for parser_id in _FOUR
    },
    "the alternate spellings' paired names left out of the given letters": {
        # taken 2026-11-12; all passes it through given-one-side's bare
        # family keys
        parser_id: {"alternate-spelling": (
            ("Smith Yuliya", "Smith Iuliia") if parser_id == "family-first"
            else ("Yuliya Smith", "Iuliia Smith"))}
        for parser_id in _FOUR
    },
    "the family-initial key removed": {
        parser_id: dict.fromkeys(
            ("family-initial", "all"),
            ("John Smith", "J. Smith") if parser_id == "family-first"
            else ("Smith John", "Smith J."))
        for parser_id in _FOUR
    },
    "the bare family keys removed": {
        parser_id: dict.fromkeys(("given-one-side", "all"),
                                 ("Smith, John", "Mr. Smith"))
        for parser_id in _FOUR
    },
    "the other readings' keys removed": {
        parser_id: {
            "other-readings": (("Mr. Smith", "Smith")
                               if parser_id == "family-first"
                               else ("Mr. Smith", "Della Smith")),
            "all": ("Smith, John", "Smith"),
        }
        for parser_id in _FOUR
    },
    "the middle words' given letters removed": {
        "family-first": {"across-roles": ("María García López", "María López")},
    },
    "the keys' family words cut at the hyphen-minus alone": {
        parser_id: dict.fromkeys(
            ("default", "alternate-spelling", "familiar-form",
             "given-one-side", "hyphenated-part", "across-roles",
             "other-readings"),
            ("Smith Ann" if parser_id == "family-first" else "Ann Smith",
             "Smith\u2010Jones, Ann"))
        for parser_id in _FOUR
    },
}


def test_every_shape_control_names_a_mutation_parser_and_setting() -> None:
    assert _SHAPE_CONTROLS and set(_SHAPE_CONTROLS) <= set(_RECORDED_CONTROLS)
    for row in _SHAPE_CONTROLS.values():
        for parser_id, runs in row.items():
            assert parser_id in _SHAPE_PARSERS
            assert runs and set(runs) <= set(_SETTING_IDS)
            for pair in runs.values():
                assert set(pair) <= set(_shape_names(parser_id))


@functools.cache
def _shape_grid(parser_id: str) -> tuple[ParsedName, ...]:
    """A parser's shape names (`_shape_names`) parsed once, for the
    shape-grid tests."""
    parser = _SHAPE_PARSERS[parser_id]
    return tuple(parser.parse(n) for n in _shape_names(parser_id))


def _shape_names(parser_id: str) -> tuple[str, ...]:
    """The names the shape grid reads under one parser: `_SHAPE_NAMES`
    and that parser's `_PACK_NAMES`."""
    return _SHAPE_NAMES + _PACK_NAMES.get(parser_id, ())


@pytest.mark.parametrize(
    "parser_id", [p for p in _SHAPE_PARSERS if p != "default"])
def test_each_shape_parser_reads_names_of_the_grid_its_own_way(
        parser_id: str) -> None:
    """A configured parser earns its place in the shape grid only by
    reading some of its names differently from `Parser()`, and by
    calling a pair holding one of those consistent that the default
    parser's matcher refuses, so the grid's guarantee and symmetry are
    held over that parser's own readings: put `Parser()` in its place
    and this fails."""
    grid = _shape_grid(parser_id)
    default = tuple(Parser().parse(n) for n in _shape_names(parser_id))
    moved = {a.original for a, b in zip(grid, default)
             if a.as_dict() != b.as_dict()}
    assert moved
    mine, theirs = _SHAPE_PARSERS[parser_id].matching(), Parser().matching()
    assert any(
        a.original != b.original and {a.original, b.original} & moved
        and mine.check(a, b).consistent and not theirs.check(da, db).consistent
        for (a, da), (b, db) in itertools.product(zip(grid, default), repeat=2))


@pytest.mark.parametrize(
    "mutation, parser_id, runs",
    [(m_, p_, runs) for m_, row in _SHAPE_CONTROLS.items()
     for p_, runs in row.items()],
    ids=lambda v: v if isinstance(v, str) else None)
def test_a_shape_control_still_reaches_the_keys_it_removed(
        mutation: str, parser_id: str,
        runs: dict[str, tuple[str, str]]) -> None:
    """Each shape control's pair is still consistent and shares a key
    under the setting it was recorded failing, as the code stands (every
    shape control removes keys), so a control that no longer reaches
    them shows here."""
    grid = dict(zip(_shape_names(parser_id), _shape_grid(parser_id)))
    for setting_id, (first, second) in runs.items():
        a, b = grid[first], grid[second]
        matching = Matching(_SHAPE_PARSERS[parser_id],
                            *SETTINGS[_SETTING_IDS.index(setting_id)])
        assert matching.check(a, b).consistent, setting_id
        assert matching.keys(a) & matching.keys(b), setting_id


@pytest.mark.parametrize("setting", SETTINGS, ids=_SETTING_IDS)
@pytest.mark.parametrize("parser_id", list(_SHAPE_PARSERS))
def test_the_key_guarantee_and_symmetry_hold_over_comma_shapes_and_packs(
        parser_id: str, setting: tuple[frozenset[Outcome], bool]) -> None:
    """The guarantee and the symmetry over each parser's shape names
    (`_shape_names`), read under a family-first order and the Spanish
    and Chinese packs as well as the default (#1264): a configured
    parser fills the roles differently and reads its own spellings, so
    each holds only if it holds there too. Each setting beyond the
    default must find a pair of two names its parser's default matcher
    refuses. 32 runs, about 12 seconds serial (measured 2026-11-11 under a load average near 4 from other work, so an upper bound); with #1264's five names added, 17 seconds against the merge base's 12 run alternately in the same minutes (2026-11-11, load average 9 to 14). Its negative controls are
    `_SHAPE_CONTROLS`."""
    parser = _SHAPE_PARSERS[parser_id]
    _assert_the_key_guarantee(
        Matching(parser, *setting), _shape_grid(parser_id),
        None if setting == SETTINGS[0] else Matching(parser),
        symmetric=True)


@pytest.mark.parametrize("a, b", [
    ("Ana dos Santos", "Ana Dos"), ("Jan van der Berg", "Jan Van"),
    ("Maria da Silva", "Maria Da"), ("John bin Laden", "John Bin"),
])
def test_a_family_of_particles_alone_is_not_part_of_a_longer_one(
        a: str, b: str) -> None:
    assert not m.check(a, b).consistent
    assert not m.check(b, a).consistent


def test_a_hyphen_half_that_is_a_particle_is_not_a_family_word() -> None:
    assert m.keys("Ahmed Al-Saud") == {"saud;a", "alsaud;a", "al-saud;a"}
    r = m.check("Ahmed Al", "Ahmed Al-Saud")
    assert not r.consistent and role(r, Role.FAMILY).outcome is Outcome.CONFLICT
    r = m.check("Ahmed Al-Saud", "Ahmed Saud")
    assert r.consistent and role(r, Role.FAMILY).outcome is Outcome.PART_OF_OTHER
    assert m.keys("Ahmed Al-Saud") & m.keys("Ahmed Saud")
    r = m.check("Ann Smith-Jones", "Ann Smith")
    assert r.consistent and role(r, Role.FAMILY).outcome is Outcome.PART_OF_OTHER


@pytest.mark.parametrize("a, b", [
    ("Jo. Garcia", "José Garcia"), ("Jo. Garcia", "Jose Garcia"),
    ("Ma. Santos", "Maria Santos"), ("Ma. Cruz", "MARIA CRUZ"),
    ("Ma. Cruz", "María Cruz"), ("Maria Mà", "Maria Ma"),
])
def test_listed_and_folded_spellings_share_a_key(a: str, b: str) -> None:
    # a listed spelling is read with the accent fold on both sides: `jo`
    # is listed as `josé`, so `Jose` is one of its spellings too (written
    # `Jo.`, `jo` being a given name of its own as well)
    assert m.check(a, b).consistent
    assert m.keys(a) & m.keys(b)


def _with(*outcomes: Outcome, other_readings: bool = False) -> Matching:
    return Matching(Parser(), DEFAULT_ACCEPT | set(outcomes), other_readings)


_other = _with(other_readings=True)


def test_a_family_initial_is_consistent_where_accepted() -> None:
    assert not m.check("Cristiane S", "Cristiane Stallbaum").consistent
    opted = _with(Outcome.FAMILY_INITIAL)
    r = opted.check("Cristiane S", "Cristiane Stallbaum")
    assert r.consistent and role(r, Role.FAMILY).outcome is Outcome.FAMILY_INITIAL
    assert "s;c" in opted.keys("Cristiane Stallbaum")
    assert "s;c" not in m.keys("Cristiane Stallbaum")


def test_a_given_name_on_one_side_is_consistent_where_accepted() -> None:
    assert not m.check("Mr. Smith", "John Smith").consistent
    opted = _with(Outcome.GIVEN_ONE_SIDE)
    r = opted.check("Mr. Smith", "John Smith")
    assert r.consistent and role(r, Role.GIVEN).outcome is Outcome.GIVEN_ONE_SIDE
    assert "smith" in opted.keys("John Smith") and "smith" in opted.keys("Mr. Smith")
    assert "smith" not in m.keys("John Smith")


def test_a_given_name_against_the_first_half_of_a_hyphenated_one() -> None:
    r = m.check("Hong Guo", "Hong-Yi Guo")
    assert not r.consistent
    assert role(r, Role.GIVEN).outcome is Outcome.HYPHENATED_PART
    assert role(r, Role.GIVEN).more is Side.RIGHT
    r = _with(Outcome.HYPHENATED_PART).check("Hong Guo", "Hong-Yi Guo")
    assert r.consistent and role(r, Role.GIVEN).outcome is Outcome.HYPHENATED_PART


def test_a_given_name_against_the_second_half_still_conflicts() -> None:
    # the second half does not share the given initial a key is cut on
    r = _with(Outcome.HYPHENATED_PART).check("Yi Guo", "Hong-Yi Guo")
    assert role(r, Role.GIVEN).outcome is Outcome.CONFLICT


def test_the_other_reading_is_consistent_where_accepted() -> None:
    r = m.check("Suharto", "Suharto")
    assert not r.consistent
    assert role(r, Role.FAMILY).outcome is Outcome.CONFLICT
    assert (r.left_alternative, r.right_alternative) == (None, None)
    opted = _other
    r = opted.check("Suharto", "Suharto")
    assert r.consistent
    assert role(r, Role.FAMILY).outcome is Outcome.SAME
    assert role(r, Role.GIVEN).outcome is Outcome.SAME
    assert (role(r, Role.FAMILY).left, role(r, Role.FAMILY).right) == ("Suharto", "Suharto")
    lone = parse("Suharto").ambiguities[0]
    assert (r.left_alternative, r.right_alternative) == (lone, lone)
    assert "suharto;" in opted.keys("Suharto")
    assert m.keys("Suharto") == frozenset()


def test_an_ambiguity_with_no_alternative_reading_is_skipped() -> None:
    # an unbalanced delimiter reports a shape, not a fork between two
    # readings, so it offers no other reading to try; the pair conflicts
    # as parsed, so the search runs and finds nothing else to read
    name = parse("John (Smith Doe")
    assert [a.alternative for a in name.ambiguities] == [None]
    r = _other.check(name, "James (Smith Doe")
    assert not r.consistent
    assert r == m.check(name, "James (Smith Doe")
    assert (r.left_alternative, r.right_alternative) == (None, None)


def test_the_other_reading_does_not_hide_a_conflict() -> None:
    r = _other.check("Suharto", "Sukarno")
    assert not r.consistent
    assert role(r, Role.FAMILY).outcome is Outcome.CONFLICT


def test_the_other_reading_of_one_side_meets_the_other_as_parsed() -> None:
    # "Van Gogh" read with Van as a particle has the family "Van Gogh"
    # and no given name, so the given role also needs given-one-side
    r = _other.check("Van Gogh", "Vincent Van Gogh")
    assert not r.consistent
    assert role(r, Role.GIVEN).outcome is Outcome.GIVEN_ONE_SIDE
    r = _with(Outcome.GIVEN_ONE_SIDE, other_readings=True).check(
        "Van Gogh", "Vincent Van Gogh")
    assert r.consistent and role(r, Role.GIVEN).outcome is Outcome.GIVEN_ONE_SIDE
    assert role(r, Role.FAMILY).outcome is Outcome.SAME
    assert (role(r, Role.FAMILY).left, role(r, Role.FAMILY).right) == (
        "Van Gogh", "Van Gogh")
    assert r.left_alternative == parse("Van Gogh").ambiguities[0]
    assert r.right_alternative is None


def test_the_default_reports_the_names_as_parsed() -> None:
    # no alternative reading is searched unless other_readings is on
    r = m.check("Van Gogh", "Dean Smith")
    assert not r.consistent
    assert (role(r, Role.GIVEN).left, role(r, Role.GIVEN).right) == ("Van", "Dean")
    assert role(r, Role.GIVEN).outcome is Outcome.CONFLICT
    assert role(r, Role.FAMILY).left == "Gogh"
    for a, b in (("Della Smith", "Mary Smith"), ("Van Gogh", "Dean Gogh")):
        r = m.check(a, b)
        assert not r.consistent
        assert role(r, Role.GIVEN).outcome is Outcome.CONFLICT, (a, b)


@pytest.mark.parametrize("a, b", [
    ("Van Gogh", "Dean Gogh"), ("Van Gogh", "Dean Smith"),
    ("Della Smith", "Mary Smith"),
])
def test_the_other_reading_does_not_make_conflicting_given_names_agree(
        a: str, b: str) -> None:
    # an alternative into a role that never conflicts (Dean as a title)
    # is not used, so it cannot empty a given role to agree with another
    opted = _other
    assert not opted.check(a, b).consistent
    assert not opted.check(b, a).consistent


# -- across roles ----------------------------------------------------------

_across = _with(Outcome.ACROSS_ROLES)


def test_a_middle_name_used_as_given_matches_across_roles() -> None:
    r = Parser().matching(accept=DEFAULT_ACCEPT | {"across-roles"}).check(  # type: ignore[arg-type]
        "J. Edgar Hoover", "Edgar Hoover")
    assert r.consistent and (r.across[0].left_role, r.across[0].right_role) == (
        Role.MIDDLE, Role.GIVEN)
    assert r.across == (CrossRoleMatch(
        Role.MIDDLE, Role.GIVEN, Outcome.SAME, "Edgar", "Edgar"),)
    given = role(r, Role.GIVEN)
    assert (given.outcome, given.left, given.right) == (
        Outcome.ACROSS_ROLES, "J.", "Edgar")
    # the middle word used as the given name leaves the middle comparison
    assert role(r, Role.MIDDLE).outcome is Outcome.SAME


def test_a_nickname_used_as_given_matches_across_roles() -> None:
    r = _across.check('William "Bill" Clinton', "Bill Clinton")
    assert r.consistent and role(r, Role.GIVEN).outcome is Outcome.ACROSS_ROLES
    assert r.across == (CrossRoleMatch(
        Role.NICKNAME, Role.GIVEN, Outcome.SAME, "Bill", "Bill"),)


def test_a_birth_name_used_as_family_matches_across_roles() -> None:
    r = _across.check("Jane Doe (née Smith)", "Jane Smith")
    assert r.consistent and role(r, Role.FAMILY).outcome is Outcome.ACROSS_ROLES
    assert r.across == (CrossRoleMatch(
        Role.MAIDEN, Role.FAMILY, Outcome.SAME, "Smith", "Smith"),)


@pytest.mark.parametrize("a, b, conflicting, outcome", [
    ("J. Edgar Hoover", "Edgar Hoover", Role.GIVEN, Outcome.CONFLICT),
    # William / Bill is a familiar form, reported though not accepted
    ('William "Bill" Clinton', "Bill Clinton", Role.GIVEN,
     Outcome.FAMILIAR_FORM),
    ("Jane Doe (née Smith)", "Jane Smith", Role.FAMILY, Outcome.CONFLICT),
])
def test_the_default_reports_cross_role_pairs_as_parsed(
        a: str, b: str, conflicting: Role, outcome: Outcome) -> None:
    # no cross-role search runs unless across-roles is accepted
    for x, y in ((a, b), (b, a)):
        r = m.check(x, y)
        assert not r.consistent and r.across == ()
        assert role(r, conflicting).outcome is outcome


def test_a_cross_role_match_counts_a_listed_spelling() -> None:
    r = _across.check("John Wm. Smith", "William Smith")
    assert r.consistent and r.across == (CrossRoleMatch(
        Role.MIDDLE, Role.GIVEN, Outcome.LISTED_SPELLING, "Wm.", "William"),)


@pytest.mark.parametrize("a, b", [
    ("John A. Smith", "Alice Smith"), ("John A. Smith", "Ann Smith"),
    ("J. Edgar Hoover", "E. Hoover"), ("John E. Hoover", "Edgar Hoover"),
    ("John E. Hoover", "E. Hoover"), ("John A. Smith", "Ann A. Smith"),
])
def test_a_cross_role_match_never_counts_an_initial(a: str, b: str) -> None:
    # a full name on both sides, or the roles are not matched across
    for x, y in ((a, b), (b, a)):
        r = _across.check(x, y)
        assert not r.consistent and r.across == (), (x, y)


def test_a_middle_word_matched_as_given_leaves_the_middle_comparison() -> None:
    r = _across.check("John Edgar Hoover", "Edgar E. Hoover")
    assert r.consistent and r.across == (CrossRoleMatch(
        Role.MIDDLE, Role.GIVEN, Outcome.SAME, "Edgar", "Edgar"),)
    middle = role(r, Role.MIDDLE)
    assert (middle.outcome, middle.left, middle.right, middle.more) == (
        Outcome.ONE_SIDE, "Edgar", "E.", Side.RIGHT)


def test_the_middle_words_left_over_compare_role_to_role() -> None:
    r = _across.check("John Edgar Allan Hoover", "Edgar Allan Hoover")
    assert r.consistent
    assert role(r, Role.MIDDLE).outcome is Outcome.SAME


def test_a_nickname_of_two_words_meets_a_given_name_whole() -> None:
    # known miss: the nickname is compared whole, never split over the
    # other's given and middle names
    for other in ("Bobby Joe Smith", "Bobby Smith"):
        r = _across.check('Robert "Bobby Joe" Smith', other)
        assert not r.consistent and r.across == (), other


def test_a_cross_role_match_reads_in_either_direction() -> None:
    r = _across.check("Edgar Hoover", "J. Edgar Hoover")
    assert r.consistent and r.across == (CrossRoleMatch(
        Role.GIVEN, Role.MIDDLE, Outcome.SAME, "Edgar", "Edgar"),)
    assert r == _across.check("J. Edgar Hoover", "Edgar Hoover").mirrored()


def test_a_cross_role_match_resolves_only_a_role_that_needs_it() -> None:
    r = _across.check("John Smith", "John Smith")
    assert r.consistent and r.across == ()
    r = _across.check("John A. Smith", "John Smith")
    assert r.across == () and role(r, Role.MIDDLE).outcome is Outcome.ONE_SIDE


@pytest.mark.parametrize("a, b", [
    ("J. Edgar Hoover", "Allan Hoover"), ("Jane Doe (née Smith)", "Jane Brown"),
    ('William "Bill" Clinton', "James Smith"),
])
def test_a_cross_role_match_does_not_hide_a_conflict(a: str, b: str) -> None:
    for x, y in ((a, b), (b, a)):
        r = _across.check(x, y)
        assert not r.consistent and r.across == ()


def test_a_cross_role_match_never_counts_an_opt_in_outcome() -> None:
    # middle Hong against given Hong-Yi is hyphenated-part, never a
    # cross-role match even where hyphenated-part is accepted
    for matching in (_across, _with(Outcome.ACROSS_ROLES, Outcome.HYPHENATED_PART)):
        r = matching.check("John Hong Hoover", "Hong-Yi Hoover")
        assert not r.consistent and r.across == ()


def test_across_roles_keys_add_the_middle_nickname_and_birth_name() -> None:
    assert "hoover;e" in _across.keys("J. Edgar Hoover")
    assert "hoover;e" not in m.keys("J. Edgar Hoover")
    assert "clinton;b" in _across.keys('William "Bill" Clinton')
    assert "clinton;b" not in m.keys('William "Bill" Clinton')
    # `doe` keys as `do`: a key writes the transcription digraphs as
    # their first letter (`_key`), so it is shared by every form
    assert _across.keys("Jane Doe (née Smith)") == {"do;j", "smith;j"}
    assert m.keys("Jane Doe (née Smith)") == {"do;j"}


@pytest.mark.parametrize(("a", "b"), [
    ("Jack de", "Jack Smith (née de)"),
    ("Jack B. al", "Jack S. (née al)"),
    ("de, Jack", "Smith, Jack (née de)"),
    ("Jack de la", "Jack Smith (née de la)"),
    ("Jack van der", "Smith, Jack (née van der)"),
    ("Jack De", "Jack Smith (née De)"),
])
def test_a_birth_name_of_particles_alone_is_keyed_as_the_check_compares_it(
        a: str, b: str) -> None:
    # the check matches the family against the birth name whole, its
    # particles kept, so the keys add it whole too: its base, the text
    # less its particles, is empty and once added no key (#1286)
    for x, y in ((a, b), (b, a)):
        assert _across.check(x, y).consistent
    assert _across.keys(a) & _across.keys(b)


def test_across_roles_keys_no_middle_word_the_check_cannot_match() -> None:
    # J.-P. is initials alone once split on its hyphen, so the check
    # never matches it across roles, and the keys add no part for it;
    # Anne's own letter tells the two apart
    for name in ("John J.-P. Smith", "Anne J.-P. Smith"):
        assert "smith;j" not in _across.keys(name) - m.keys(name), name
    assert _across.keys("Anne J.-P. Smith") == {"smith;a"}
    # and the check reads the pair as it did: J.-P. is no given name
    # for John, so the middle is one-sided and the given conflicts
    r = _across.check("John J.-P. Smith", "J.-P. Smith")
    assert not r.consistent and r.across == ()
    assert role(r, Role.GIVEN).outcome is Outcome.CONFLICT
    assert role(r, Role.MIDDLE).outcome is Outcome.ONE_SIDE


def test_across_roles_keys_a_nickname_the_check_compares_whole() -> None:
    # the check compares the nickname whole, so one that opens with an
    # initial but is not initials alone can meet a given name, and its
    # first word's letter is keyed
    left = parse('Anne "J. Bob" Smith')
    right = parse("Anne Smith").replace(given="J. Bob")
    r = _across.check(left, right)
    assert r.consistent and r.across == (CrossRoleMatch(
        Role.NICKNAME, Role.GIVEN, Outcome.SAME, "J. Bob", "J. Bob"),)
    assert _across.keys(left) & _across.keys(right) == {"smith;j"}


def test_a_cross_role_row_says_the_side_that_held_both_roles_carried_more() -> None:
    # the left name holds the given initial and the middle name used
    # as the given name, so it carries more; the less specific name is
    # the one that carries more of no role
    r = _across.check("J. Edgar Hoover", "Edgar Hoover")
    assert role(r, Role.GIVEN).more is Side.LEFT
    assert role(r, Role.MIDDLE).more is Side.NEITHER
    assert all(x.more is not Side.LEFT
               for x in _across.check("Edgar Hoover", "J. Edgar Hoover").roles)
    r = _across.check("Jane Doe (née Smith)", "Jane Smith")
    assert role(r, Role.FAMILY).more is Side.LEFT
    r = _across.check('William "Bill" Clinton', "Bill Clinton")
    assert role(r, Role.GIVEN).more is Side.LEFT


_every = Matching(Parser(), DEFAULT_ACCEPT | set(OPT_INS), other_readings=True)


@pytest.mark.parametrize("a, b, which, outcome", [
    ("Smith", "Jane Smith", Role.GIVEN, Outcome.GIVEN_ONE_SIDE),
    ("Van Gogh", "Gogh", Role.FAMILY, Outcome.PARTICLES_ASIDE),
])
def test_a_row_reached_through_another_reading_keeps_its_own_outcome(
        a: str, b: str, which: Role, outcome: Outcome) -> None:
    # the leniency the other reading still needed stays visible
    r = _every.check(a, b)
    assert r.consistent and role(r, which).outcome is outcome
    assert r.left_alternative == parse(a).ambiguities[0]
    assert r == _every.check(b, a).mirrored()


def test_mirrored_swaps_the_alternatives() -> None:
    lone = parse("Suharto").ambiguities[0]
    result = MatchResult(True, _result().roles, (), lone, None)
    assert (result.mirrored().left_alternative,
            result.mirrored().right_alternative) == (None, lone)
    assert result.mirrored().mirrored() == result
    assert result != MatchResult(True, _result().roles, (), None, lone)
    assert pickle.loads(pickle.dumps(result)) == result


_OFFERED = 'parser.matching(accept=parser.matching().accept | {"family-initial"})'


@pytest.mark.parametrize("accept", ["initial", {3}])
def test_a_bad_accept_offers_code_that_extends_the_default(accept: object) -> None:
    with pytest.raises(TypeError) as caught:
        Matching(Parser(), accept=accept)  # type: ignore[arg-type]
    message = str(caught.value)
    assert message.endswith(f"pass e.g. {_OFFERED}")
    # the offered code runs, keeps the default and adds the outcome
    parser = Parser()
    offered = eval(message.split("pass e.g. ")[1], {"parser": parser})
    assert offered.accept == DEFAULT_ACCEPT | {Outcome.FAMILY_INITIAL}
    # and type-checks, the same spelling written out for mypy
    written = parser.matching(accept=parser.matching().accept | {"family-initial"})
    assert written == offered


@pytest.mark.parametrize("apostrophe", ["\u2019", "\u02bc", "\u02bb",
                                        "\u2018", "`"])
def test_a_typographic_apostrophe_folds_like_a_typed_one(apostrophe: str) -> None:
    # U+02BB, U+2018 and the backtick are the Uzbek spellings of the
    # okina in gʻ and oʻ (#1186's sweep): G'ofurov and Gʻofurov are one
    written = f"O{apostrophe}Brien, Pat"
    assert _fold(f"O{apostrophe}Brien") == _fold("O'Brien") == "obrien"
    r = m.check(written, "Pat O'Brien")
    assert r.consistent and role(r, Role.FAMILY).outcome is Outcome.FOLDED
    assert m.keys(written) == m.keys("Pat O'Brien") == {"obrien;p"}
    uzbek = f"G{apostrophe}ofurov, Aziz"
    assert m.check(uzbek, "Aziz G'ofurov").consistent


def test_keys_are_recomposed_so_a_hangul_given_letter_is_a_syllable() -> None:
    # the fold decomposes to filter the marks, then recomposes, so a
    # key never holds a conjoining jamo however the name was encoded
    import unicodedata
    assert m.keys("김민준") == {"김;민"}
    decomposed = m.keys(unicodedata.normalize("NFD", "김민준"))
    assert decomposed and all(
        k == unicodedata.normalize("NFC", k) for k in decomposed)
    assert _fold("Máría") == unicodedata.normalize("NFC", _fold("Máría"))
    assert _fold("क्ष") == unicodedata.normalize("NFC", "क्ष")


# -- listed spellings, read per role (decisions/name-matching, 2026-11-08)


@pytest.mark.parametrize("a, b, field", [
    ("Jo. Garcia", "Jose Garcia", "given"),
    ("Ma. Santos", "Maria Santos", "given"),
    ("Ma. Cruz", "MARIA CRUZ", "given"), ("Ma. Cruz", "María Cruz", "given"),
    # the written word's accent folded away before it is looked up, in
    # the middle name (a leading `Mà.` reads as a title by shape, H2)
    ("Ana Mà. Cruz", "Ana María Cruz", "middle"),
    ("Ana Ma\u0300. Cruz", "Ana María Cruz", "middle"),
])
def test_a_listed_spelling_holds_whatever_the_accents(
        a: str, b: str, field: str) -> None:
    r = m.check(a, b)
    assert r.consistent and r[field].outcome is Outcome.LISTED_SPELLING
    assert m.keys(a) & m.keys(b)


# -- a listed spelling of a name of its own needs its period
# (decisions/name-matching, 2026-11-08 #1006 follow-up)


@pytest.mark.parametrize("a, b", [
    ("Jo. Garcia", "José Garcia"), ("Ma. Santos", "María Santos"),
    ("Jas. Singh", "James Singh"), ("JO. GARCIA", "JOSÉ GARCIA"),
    ("Garcia, Jo.", "Garcia, José"),
    # every full stop the vocabulary strips marks the period (#322)
    ("Jo\uff0e Garcia", "José Garcia"), ("Ma\uff61 Santos", "María Santos"),
    # a spelling of a word that is no name of its own needs no period
    ("Wm Smith", "William Smith"), ("Wm. Smith", "William Smith"),
    ("WM SMITH", "WILLIAM SMITH"),
])
def test_a_listed_spelling_with_its_period_or_of_no_name_of_its_own(
        a: str, b: str) -> None:
    for x, y in ((a, b), (b, a)):
        r = m.check(x, y)
        assert r.consistent and r["given"].outcome is Outcome.LISTED_SPELLING
    assert m.keys(a) & m.keys(b)


@pytest.mark.parametrize("a, b, outcome", [
    ("Jo Garcia", "José Garcia", Outcome.CONFLICT),
    ("Jo Garcia", "Jose Garcia", Outcome.CONFLICT),
    # the review pairs `jo` with Joanne: a familiar form, which
    # the table reports and the default does not accept
    ("Jo Garcia", "Joanne Garcia", Outcome.FAMILIAR_FORM),
    ("Ma Santos", "María Santos", Outcome.CONFLICT),
    ("Jas Singh", "James Singh", Outcome.CONFLICT),
    ("JAS SINGH", "JAMES SINGH", Outcome.CONFLICT),
    ("Garcia, Jo", "Garcia, José", Outcome.CONFLICT),
])
def test_a_name_of_its_own_written_bare_is_itself(
        a: str, b: str, outcome: Outcome) -> None:
    # `jo`, `ma` and `jas` are given names of their own as well as
    # spellings of José, María and James, so written without the period
    # each is the name, not a listed spelling of the long form
    for x, y in ((a, b), (b, a)):
        r = m.check(x, y)
        assert not r.consistent and r["given"].outcome is outcome


def test_a_bare_middle_name_of_its_own_is_itself() -> None:
    r = m.check("Ana Ma Cruz", "Ana María Cruz")
    assert not r.consistent and r["middle"].outcome is Outcome.CONFLICT


def test_the_mark_is_every_short_name_beside_a_plain_one() -> None:
    # the property, computed from the lexicon's own readings: a word whose
    # name reading carries `same_as` beside a name reading of the same
    # kind carrying none
    from nameparser import _reading_index as ri
    lexicon = Lexicon.default()
    short: dict[str, set[str]] = {}
    plain: dict[str, set[str]] = {}
    for text, readings in lexicon._pool().items():
        for r in readings:
            if not r.on_by_default or r.category != "name":
                continue
            group = ri.same_as_group(r.kind)
            assert group is not None
            into = short if "same_as" in r.props else plain
            into.setdefault(group, set()).add(text)
    for group, named in lexicon._same_as_named.items():
        expected = short.get(group, set()) & plain.get(group, set())
        assert named == expected, group
        assert named <= set(lexicon._same_as[group]), group
    assert lexicon._same_as_named["given"]
    assert not any(lexicon._same_as_named[g] for g in ("family", "title", "suffix"))


def _choice(languages: set[str], strict: bool) -> Parser:
    from nameparser import Locale, parser_for
    return parser_for(Locale(code="x", lexicon=Lexicon.empty(),
                             languages=frozenset(languages)), strict=strict)


# measured 2026-11-08: the mark follows the chosen vocabulary
@pytest.mark.parametrize("languages, strict, named, jo, jas", [
    (None, False, {"jas", "jo", "ma"}, False, False),
    ({"fil"}, False, {"jas", "jo", "ma"}, False, False),
    ({"en", "fil"}, True, {"jo", "ma"}, False, True),
    ({"en", "pa"}, True, {"jas"}, False, False),
    # Filipino alone: Jo has no reading as a name of its own (ruling)
    ({"fil"}, True, set(), True, False),
    # English alone: pa.toml's Jas left out, the accepted cost
    ({"en"}, True, set(), False, True),
])
def test_the_mark_under_each_choice_of_languages(
        languages: set[str] | None, strict: bool, named: set[str],
        jo: bool, jas: bool) -> None:
    parser = Parser() if languages is None else _choice(languages, strict)
    assert parser.lexicon._same_as_named["given"] == named
    matching = parser.matching()
    assert matching.check("Jo Smith", "José Smith").consistent is jo
    assert matching.check("Jas Singh", "James Singh").consistent is jas


def test_a_callers_edit_moves_the_mark() -> None:
    # removing jo's given kind removes both its readings, link and all
    removed = Lexicon.default().remove("jo", kind="given")
    assert "jo" not in removed._same_as_named["given"]
    assert "jo" not in removed._same_as["given"]
    # a caller's same_as is written onto every given reading of the
    # word, replacing the link and leaving no plain reading to mark it
    joseph = Lexicon.default().add("jo", kind="given", same_as="joseph")
    assert joseph._same_as["given"]["jo"] == {"joseph"}
    assert "jo" not in joseph._same_as_named["given"]
    assert Matching(Parser(lexicon=joseph)).check(
        "Jo Smith", "Joseph Smith").consistent
    short = Lexicon.empty().add("zzq", kind="given", same_as="zzr")
    assert short._same_as["given"]["zzq"] == {"zzr"}
    assert not short._same_as_named["given"]


def test_a_bare_name_of_its_own_is_not_keyed_by_its_long_form() -> None:
    # the keys are cut from the one spelling set the check reads, so the
    # period is read there too: `Jo.` reaches José's folded form, `Jo`
    # only itself (a key holds a given name's initial, which `Jo` and
    # `José` share, so the set is what shows it)
    lexicon = Lexicon.default()
    assert _spelling_keys("Jo.", "given", lexicon) == {"jo", "jose"}
    assert _spelling_keys("Jo", "given", lexicon) == {"jo"}
    assert _spelling_keys("MA", "given", lexicon) == {"ma"}
    assert _spelling_keys("Jas.", "given", lexicon) == {"jas", "james"}
    assert _spelling_keys("WM", "given", lexicon) == {"wm", "william"}


@pytest.mark.parametrize("a, b", [("Ma, Jack", "María, Jack"),
                                  ("Ana Ma", "Ana María")])
def test_a_given_names_spelling_does_not_reach_the_family(a: str, b: str) -> None:
    # `ma` is listed as a spelling of the given name María; the surname
    # Ma is another word
    r = m.check(a, b)
    assert not r.consistent and r["family"].outcome is Outcome.CONFLICT


def test_a_generations_spelling_does_not_reach_the_given_name() -> None:
    r = m.check("Junior Smith", "Jr Smith")
    assert r["given"].outcome is not Outcome.LISTED_SPELLING
    assert not r.consistent


def test_a_title_listed_as_two_words_spells_each() -> None:
    # `sr` is listed under both `señor` and `senhor`, so it reads as a
    # spelling of each; the two full forms share no listed word and are
    # only noted, as different titles are
    assert m.check("Sr. John Smith", "Señor John Smith")["title"].outcome is (
        Outcome.LISTED_SPELLING)
    assert m.check("Sr. John Smith", "Senhor John Smith")["title"].outcome is (
        Outcome.LISTED_SPELLING)
    assert m.check("Señor John Smith", "Senhor John Smith")["title"].outcome is (
        Outcome.NOTED)


def _matching_with(lexicon: Lexicon) -> Matching:
    return Matching(Parser(lexicon=lexicon))


def test_a_callers_same_as_loop_makes_its_words_spellings_of_each_other() -> None:
    lexicon = (Lexicon.default().add("bob", kind="given", same_as="robert")
               .add("robert", kind="given", same_as="bob"))
    matching = _matching_with(lexicon)
    r = matching.check("Bob Smith", "Robert Smith")
    assert r.consistent and r["given"].outcome is Outcome.LISTED_SPELLING
    assert matching.keys("Bob Smith") & matching.keys("Robert Smith")


def test_a_callers_reverse_same_as_keeps_the_shipped_one() -> None:
    lexicon = Lexicon.default().add("william", kind="given", same_as="wm")
    r = _matching_with(lexicon).check("Wm. Smith", "William Smith")
    assert r.consistent and r["given"].outcome is Outcome.LISTED_SPELLING


def test_a_hyphenated_listed_spelling_shares_a_key() -> None:
    lexicon = Lexicon.default().add("Dd", kind="family", same_as="Ee-Ff")
    matching = _matching_with(lexicon)
    r = matching.check("aa Dd", "aa Ee-Ff")
    assert r.consistent and r["family"].outcome is Outcome.LISTED_SPELLING
    assert matching.keys("aa Dd") & matching.keys("aa Ee-Ff")


# -- ranking outcomes and reading a row by role


def test_strength_ranks_the_outcomes_in_declaration_order() -> None:
    # `<` on an Outcome compares names: `folded` sorts before `same`
    assert min(Outcome.SAME, Outcome.FOLDED) is Outcome.FOLDED
    assert Outcome.SAME.strength > Outcome.FOLDED.strength
    assert min(Outcome, key=lambda o: o.strength) is Outcome.CONFLICT
    assert sorted(Outcome, key=lambda o: o.strength, reverse=True) == list(Outcome)
    # every outcome is one a row can read, so the ranks run unbroken
    # from conflict's 0 to same's
    assert sorted(o.strength for o in Outcome) == list(range(len(Outcome)))
    assert Outcome.CONFLICT.strength == 0


def test_weakest_is_the_weakest_rows_outcome() -> None:
    assert m.check("John Smith", "John Smith").weakest is Outcome.SAME
    assert m.check("John A. Smith", "John Smith").weakest is Outcome.ONE_SIDE
    assert m.check("John Smith", "Jane Smith").weakest is Outcome.CONFLICT


def test_a_result_is_read_by_role() -> None:
    r = m.check("John Smith Jr.", "John Smith Junior")
    assert r["suffix"] is r[Role.SUFFIX] is r.roles[list(Role).index(Role.SUFFIX)]
    with pytest.raises(ValueError):
        r["surname"]


def test_a_result_holds_one_row_per_role_in_role_order() -> None:
    rows = _result().roles
    with pytest.raises(ValueError, match="one RoleMatch per Role"):
        MatchResult(True, rows[:-1])
    with pytest.raises(ValueError, match="one RoleMatch per Role"):
        MatchResult(True, rows[::-1])
    with pytest.raises(TypeError, match="RoleMatch"):
        MatchResult(True, ("x",) * len(rows))  # type: ignore[arg-type]
    with pytest.raises(TypeError, match="tuple"):
        MatchResult(True, list(rows))  # type: ignore[arg-type]


# -- familiar forms (decisions/name-matching, 2026-11-08 FAMILIAR FORMS) --

_familiar = _with(Outcome.FAMILIAR_FORM)


@pytest.mark.parametrize("a, b, key", [
    ("Max Smith", "Maximilian Smith", "smith;m"),
    ("Bill Smith", "William Smith", "smith;w"),
    ("Bob Smith", "Robert Smith", "smith;r"),
    ("BILL SMITH", "WILLIAM SMITH", "smith;w"),
    ("Smith, Bill", "William Smith", "smith;w"),
])
def test_a_familiar_form_is_consistent_where_accepted(
        a: str, b: str, key: str) -> None:
    r = _familiar.check(a, b)
    assert r.consistent
    assert role(r, Role.GIVEN).outcome is Outcome.FAMILIAR_FORM
    assert role(r, Role.GIVEN).more is Side.RIGHT
    assert key in _familiar.keys(a) & _familiar.keys(b)
    # not accepted by default, but reported in the table all the same
    r = m.check(a, b)
    assert not r.consistent
    assert role(r, Role.GIVEN).outcome is Outcome.FAMILIAR_FORM


def test_the_default_keys_a_familiar_form_by_its_own_letter_alone() -> None:
    assert m.keys("Bill Smith") == {"smith;b"}
    assert _familiar.keys("Bill Smith") == {"smith;b", "smith;w"}
    # a name keys through every name it is paired with, either way
    assert m.keys("William Smith") == {"smith;w"}
    assert _familiar.keys("William Smith") == {"smith;b", "smith;w"}


@pytest.mark.parametrize("short, long", [("maria", "masha"),
                                         ("masha", "maria")])
def test_a_pair_reads_whichever_way_the_source_wrote_it(
        short: str, long: str) -> None:
    # a pair may be written on its long name (the tool writes it on
    # the shorter, which can be the full one: `charles` / `charlie`, and
    # a caller may write either), so a pair is read either way: written
    # either way round here, on a lexicon holding no other familiar
    # reading, it matches and keys alike
    lexicon = Lexicon.default().remove(kind="familiar", every=True).add(
        short, kind="familiar", short_for=[long])
    matching = Matching(Parser(lexicon=lexicon),
                        DEFAULT_ACCEPT | {Outcome.FAMILIAR_FORM})
    for a, b in (("Masha Ivanova", "Maria Ivanova"),
                 ("Maria Ivanova", "Masha Ivanova")):
        r = matching.check(a, b)
        assert r.consistent, (short, a)
        assert role(r, Role.GIVEN).outcome is Outcome.FAMILIAR_FORM
        assert matching.keys(a) & matching.keys(b)


@pytest.mark.parametrize("a, b", [
    # never chained: each is paired with Max alone, not with each other
    ("Maximilian Smith", "Maxim Smith"),
    # pairs no source lists: Rickie is paired with Rick and Roderick,
    # Pancho with nothing
    ("Rickie Smith", "Richard Smith"),
    ("Pancho Smith", "Francisco Smith"),
])
def test_a_familiar_form_reaches_only_its_listed_longer_names(
        a: str, b: str) -> None:
    r = _familiar.check(a, b)
    assert not r.consistent
    assert role(r, Role.GIVEN).outcome is Outcome.CONFLICT


def test_a_familiar_form_is_read_in_the_middle_name_and_nickname() -> None:
    r = _familiar.check("John Bill Smith", "John William Smith")
    assert r.consistent and role(r, Role.MIDDLE).outcome is Outcome.FAMILIAR_FORM
    r = _familiar.check('Robert "Bob" Smith', 'Robert "Robert" Smith')
    assert role(r, Role.NICKNAME).outcome is Outcome.FAMILIAR_FORM


def test_a_familiar_form_is_not_read_in_the_family_name() -> None:
    r = _familiar.check("Bill, John", "William, John")
    assert not r.consistent and role(r, Role.FAMILY).outcome is Outcome.CONFLICT


def test_a_familiar_form_meets_a_listed_spelling_of_its_longer_name() -> None:
    # Wm. is William written short, which Bill stands for
    r = _familiar.check("Wm. Smith", "Bill Smith")
    assert r.consistent and role(r, Role.GIVEN).outcome is Outcome.FAMILIAR_FORM
    assert _familiar.keys("Wm. Smith") & _familiar.keys("Bill Smith")


def test_a_familiar_form_ranks_below_every_default_outcome() -> None:
    # and below an alternate spelling alone, the one opt-in stronger:
    # a spelling of the name says more than a familiar form of it
    assert all(o.strength > Outcome.FAMILIAR_FORM.strength
               for o in DEFAULT_ACCEPT)
    assert all(o.strength < Outcome.FAMILIAR_FORM.strength
               for o in OPT_INS if o not in (Outcome.FAMILIAR_FORM,
                                             Outcome.ALTERNATE_SPELLING))
    assert all(o.strength > Outcome.ALTERNATE_SPELLING.strength
               for o in DEFAULT_ACCEPT)
    assert Outcome.ALTERNATE_SPELLING.strength > Outcome.FAMILIAR_FORM.strength


# -- alternate spellings (decisions/name-matching, 2026-11-12 ALTERNATE
# SPELLINGS ARE OPT-IN) --------------------------------------------------------

_alternate = _with(Outcome.ALTERNATE_SPELLING)


@pytest.mark.parametrize("a, b", [
    ("Yuliya Ivanova", "Iuliia Ivanova"),
    ("Aleksey Ivanov", "Alexey Ivanov"),
    ("Smith, Mohammad", "Muhammad Smith"),
])
def test_an_alternate_spelling_is_consistent_only_where_accepted(
        a: str, b: str) -> None:
    for x, y in ((a, b), (b, a)):
        r = _alternate.check(x, y)
        assert r.consistent
        assert role(r, Role.GIVEN).outcome is Outcome.ALTERNATE_SPELLING
        assert _alternate.keys(x) & _alternate.keys(y)
        # people spell a name differently on purpose, to be told apart:
        # not accepted by default, reported in the table all the same
        r = m.check(x, y)
        assert not r.consistent
        assert role(r, Role.GIVEN).outcome is Outcome.ALTERNATE_SPELLING


def test_an_alternate_spelling_is_never_chained() -> None:
    # each is paired with `aleksei` and `aleksey` with `aleksej` by no
    # row of the review: a chain through the third spelling would ship
    # a pair nobody read
    lexicon = Lexicon.default()
    assert "aleksei" in lexicon._alternate_spellings("aleksej")
    assert "aleksei" in lexicon._alternate_spellings("aleksey")
    assert "aleksey" not in lexicon._alternate_spellings("aleksej")
    r = _alternate.check("Aleksej Petrov", "Aleksey Petrov")
    assert not r.consistent


def test_an_alternate_spelling_is_no_familiar_form_and_no_listed_spelling() -> None:
    # the familiar forms' opt-in does not reach it, and the default's
    # listed spellings never hold it
    assert not _familiar.check("Aleksey Ivanov", "Alexey Ivanov").consistent
    assert not Lexicon.default()._headwords("aleksey", "given") & (
        Lexicon.default()._headwords("alexey", "given"))


@pytest.mark.parametrize("accepted, consistent, outcome", [
    ((Outcome.FAMILIAR_FORM,), False, Outcome.ALTERNATE_SPELLING),
    ((Outcome.ALTERNATE_SPELLING,), False, Outcome.FAMILIAR_FORM),
    ((Outcome.ALTERNATE_SPELLING, Outcome.FAMILIAR_FORM), True,
     Outcome.FAMILIAR_FORM),
])
def test_a_given_name_needing_both_is_accepted_only_with_both(
        accepted: tuple[Outcome, ...], consistent: bool,
        outcome: Outcome) -> None:
    # two given words, one an alternate spelling, the other a familiar
    # form: accepted on neither alone, the row naming the one refused,
    # and the keys shared wherever it is consistent (review of #1379:
    # a familiar-form-only caller once accepted it with no shared key)
    parser = Parser(policy=Policy(two_given_names=True))
    matching = Matching(parser, DEFAULT_ACCEPT | set(accepted))
    a, b = "Iuliia Liz Smith", "Yuliya Elizabeth Smith"
    for x, y in ((a, b), (b, a)):
        r = matching.check(x, y)
        assert r.consistent is consistent
        assert role(r, Role.GIVEN).outcome is outcome
        if consistent:
            assert matching.keys(x) & matching.keys(y)


@pytest.mark.parametrize("a, b, accepted, hidden", [
    # an alternate spelling, unaccepted, beside an accepted familiar form
    ("John Iuliia Liz Smith", "John Yuliya Elizabeth Smith",
     Outcome.FAMILIAR_FORM, Outcome.ALTERNATE_SPELLING),
    # a familiar form, unaccepted, beside an accepted hyphenated part
    ("John Liz Jean Smith", "John Elizabeth Jean-Paul Smith",
     Outcome.HYPHENATED_PART, Outcome.FAMILIAR_FORM),
])
def test_an_accepted_middle_word_never_hides_an_unaccepted_one(
        a: str, b: str, accepted: Outcome, hidden: Outcome) -> None:
    matching = Matching(Parser(), DEFAULT_ACCEPT | {accepted})
    r = matching.check(a, b)
    assert not r.consistent
    assert role(r, Role.MIDDLE).outcome is hidden
    both = Matching(Parser(), DEFAULT_ACCEPT | {accepted, hidden})
    assert both.check(a, b).consistent


# -- a keyboard's spelling (decisions/name-matching, 2026-11-12 A KEYBOARD'S
# SPELLING IS FOLDED) ---------------------------------------------------------

@pytest.mark.parametrize("a, b", [
    # (a) a letter a keyboard lacks, written as one types it
    ("Łukasz Nowak", "Lukasz Nowak"), ("Anna Kowałski", "Anna Kowalski"),
    ("Pınar Yılmaz", "Pinar Yilmaz"), ("Søren Hansen", "Soren Hansen"),
    ("Đorđe Petrović", "Dorde Petrovic"), ("Ægir Olsen", "Aegir Olsen"),
    ("Hrafn Þórsson", "Hrafn Thorsson"),
    # (b) a standard transcription, read from either side
    ("Hans Müller", "Hans Mueller"), ("Jürgen Weber", "Juergen Weber"),
    ("Søren Hansen", "Soeren Hansen"), ("Ola Ågård", "Ola Aagaard"),
    ("Srđan Petrović", "Srdjan Petrovic"), ("Mueller, Hans", "Hans Müller"),
    # letter by letter: a word or a text mixing the two writings (review
    # of #1379)
    ("Martin Ødegård", "Martin Odegaard"),
    ("Jørgen Søndergård", "Joergen Sondergaard"),
    ("Hans Göthe-Müller", "Hans Goethe-Muller"),
    ("Müller Lüdenscheidt, Hans", "Mueller Ludenscheidt, Hans"),
])
def test_a_keyboards_spelling_reads_folded_by_default(a: str, b: str) -> None:
    for x, y in ((a, b), (b, a)):
        r = m.check(x, y)
        assert r.consistent, (x, y)
        assert {row.outcome for row in r.roles} <= {
            Outcome.SAME, Outcome.FOLDED}, (x, y)
        assert Outcome.FOLDED in {row.outcome for row in r.roles}
        assert m.keys(x) & m.keys(y)


def test_a_transcription_reaches_a_family_base_and_the_birth_name() -> None:
    # word by word, through the spelling set: a particle surname compares
    # by its base (taken 2026-11-12: the transcription left out of
    # `_spellings` refuses the first pair, and left out of the keys as
    # well, keeps the second consistent under across-roles with no key)
    assert m.check("Hans von Müller", "Hans Mueller").consistent
    across = _with(Outcome.ACROSS_ROLES)
    a, b = "Ann Smith (née Müller)", "Ann Mueller"
    assert across.check(a, b).consistent
    assert across.keys(a) & across.keys(b)


def test_a_transcription_reaches_a_hyphen_half_and_the_vocabulary() -> None:
    # every side of a comparison reads the forms, not one of them (#1293):
    # a hyphenated part, a caller's listed spelling, familiar form and
    # alternate spelling, each asked from either side
    hyphen = _with(Outcome.HYPHENATED_PART)
    assert hyphen.check("Jürgen Smith", "Juergen-Paul Smith").consistent
    lexicon = (Lexicon.default()
               .add("günni", kind="familiar", short_for=["günther"])
               .add("jöran", kind="spelling", spelling_of=["göran"])
               .add("jürg", kind="given", same_as="jürgen"))
    matching = Matching(Parser(lexicon=lexicon), DEFAULT_ACCEPT | {
        Outcome.FAMILIAR_FORM, Outcome.ALTERNATE_SPELLING})
    for a, b in (("Günni Smith", "Guenther Smith"),
                 ("Guenni Smith", "Günther Smith"),
                 # both written out, which asking each side alone missed
                 ("Guenni Smith", "Guenther Smith"),
                 # accepted: each side reaches its member of the listed
                 # pair by a form of its own (review of #1379)
                 ("Gunni Smith", "Guenther Smith"),
                 ("Jöran Smith", "Goeran Smith"),
                 ("Joeran Smith", "Göran Smith"),
                 ("Joeran Smith", "Goeran Smith"),
                 ("Jürg Smith", "Juergen Smith")):
        for x, y in ((a, b), (b, a)):
            r = matching.check(x, y)
            assert r.consistent, (x, y)
            assert matching.check(y, x) == r.mirrored()
            assert matching.keys(x) & matching.keys(y)


def test_a_callers_pair_written_with_another_hyphen_reads_both_ways() -> None:
    # the lexicon's pair index reads the pipeline's hyphens as the match
    # does (review of 87b1d5c3: a pair written with U+2010 was found
    # from its own side alone)
    lexicon = Lexicon.default().add("jöri", kind="familiar",
                                    short_for=["jöran\u2010peter"])
    matching = Matching(Parser(lexicon=lexicon),
                        DEFAULT_ACCEPT | {Outcome.FAMILIAR_FORM})
    for long in ("Jöran-Peter Smith", "Joeran-Peter Smith",
                 "Jöran\u2010Peter Smith"):
        r = matching.check("Jöri Smith", long)
        assert r.consistent, long
        assert matching.check(long, "Jöri Smith") == r.mirrored()


def test_a_name_with_many_transcribable_letters_has_few_keys() -> None:
    # the keys collapse the transcription digraphs, so a name's keys do
    # not grow with its forms (2^k for k letters: 530 keys for this name
    # before the review of #1379)
    name = "Hans Ødegård-Søndergård-Bøgh-Åsøå"
    assert len(m.keys(name)) <= 8
    for other in ("Hans Odegaard-Sondergaard-Bogh-Aasoaa",
                  "Hans Oedegard-Soendergard-Boegh-Asoa"):
        assert m.check(name, other).consistent
        assert m.keys(name) & m.keys(other)


def test_past_eight_transcribable_letters_a_text_has_two_forms() -> None:
    # 2^k forms for k letters, so a text holding more than eight is read
    # all written-out or none, never letter by letter
    from nameparser._lexicon import _MOST_TRANSCRIBED, _forms
    name = "Hans Ødegård-Søndergård-Bøgh-Åsøåø"
    assert sum(c in "øå" for c in name.casefold()) == _MOST_TRANSCRIBED + 1
    assert len(_forms(name)) == 2
    assert m.check(name, "Hans Oedegaard-Soendergaard-Boegh-Aasoeaaoe").consistent
    assert m.check(name, "Hans Odegard-Sondergard-Bogh-Asoao").consistent


def test_a_given_part_needing_no_pair_has_no_familiar_outcome() -> None:
    # every word folds alike or is a listed spelling: no alternate or
    # familiar reading is asked for, whatever the caller accepts
    from nameparser._match import Outcome, _familiar_outcome
    lexicon = Lexicon.default()
    every = frozenset(Outcome)
    assert _familiar_outcome(["anna"], ["Anna"], lexicon, every) is None
    assert _familiar_outcome(["wm"], ["william"], lexicon, every) is None


def test_a_transcription_is_read_only_from_the_letter_it_writes_out() -> None:
    # Muller and Mueller each meet Müller, and not each other: neither
    # holds the letter, and the check is not transitive
    assert not m.check("Hans Muller", "Hans Mueller").consistent
    assert m.check("Hans Muller", "Hans Müller").consistent
    assert m.check("Hans Mueller", "Hans Müller").consistent


def test_no_parse_reads_an_alternate_spelling() -> None:
    # every spelling reading taken out: every set a parse reads, and the
    # parse of every spelling as a given name, are what they were
    default = Lexicon.default()
    without = default.remove(kind="spelling", every=True)
    assert default._alternate and not without._alternate
    assert all(getattr(default._sets, f) == getattr(without._sets, f)
               for f in type(default._sets).__slots__)
    assert default._same_as == without._same_as
    bare, plain = Parser(), Parser(lexicon=without)
    for w in sorted(default._alternate):
        for text in (f"{w.title()} Smith", f"Smith, {w.title()}",
                     f"{w.title()}. Smith"):
            a, b = bare.parse(text), plain.parse(text)
            assert a.tokens == b.tokens and a.ambiguities == b.ambiguities, text


def test_a_choice_of_languages_keeps_its_own_alternate_spellings() -> None:
    # a plain choice drops none (a choice prefers by none); a strict one
    # keeps its own files' and mul.toml's, and no other's
    from nameparser._reading_index import index
    plain = Lexicon(_base="default", _languages={"uk"})
    assert plain._alternate == Lexicon.default()._alternate
    ukrainian = Lexicon(_base="default", _languages={"uk"}, _strict=True)
    english = Lexicon(_base="default", _languages={"en"}, _strict=True)
    # the pairs a spelling reading of uk.toml writes and none of en.toml's
    # or mul.toml's does
    def pairs(tags: set[str]) -> set[frozenset[str]]:
        return {frozenset((r.text, n)) for r in index()
                if r.kind == "spelling" and r.tag in tags
                for n in r.props["spelling_of"]}
    uk_only = pairs({"uk"}) - pairs({"en", "mul"})
    assert uk_only
    for a, b in map(sorted, uk_only):
        assert b in ukrainian._alternate_spellings(a)
        assert b not in english._alternate_spellings(a)


def test_a_callers_spelling_extends_the_shipped_ones() -> None:
    shipped = Lexicon.default()._alternate_spellings("aleksey")
    lexicon = Lexicon.default().add("aleksey", kind="spelling",
                                    spelling_of=["Aleksiy"])
    assert lexicon._alternate_spellings("aleksey") == shipped | {"aleksiy"}
    assert lexicon._alternate_spellings("aleksiy") == {"aleksey"}
    assert Lexicon.empty().add("zzq", kind="spelling", spelling_of=["zzr"]
                               ).words(kind="spelling") == ("zzq",)
    with pytest.raises(ValueError, match="needs spelling_of"):
        Lexicon.default().add("zzq", kind="spelling")
    with pytest.raises(ValueError, match="names the word itself"):
        Lexicon.default().add("zzq", kind="spelling", spelling_of=["zzq"])


def test_a_callers_familiar_form_extends_the_shipped_ones() -> None:
    # an add EXTENDS the word's longer names, in a reading of the
    # caller's own that names no file; the shipped readings stay
    shipped = Lexicon.default()._familiar_forms("max")
    assert "maxence" not in shipped
    lexicon = Lexicon.default().add("max", kind="familiar",
                                    short_for=["Maxence"])
    assert lexicon._familiar_forms("Max") == shipped | {"maxence"}
    readings = [r for r in lexicon.readings_of("max") if r.kind == "familiar"]
    files = [r for r in readings if r.languages]
    assert files and len(readings) == len(files) + 1
    assert next(r for r in readings if not r.languages).properties == (
        ("short_for", ("maxence",)),)
    matching = Matching(Parser(lexicon=lexicon),
                        DEFAULT_ACCEPT | {Outcome.FAMILIAR_FORM})
    for long in ("Maxence", "Maximilian"):
        assert matching.check("Max Smith", f"{long} Smith").consistent
        assert matching.keys("Max Smith") & matching.keys(f"{long} Smith")
    # a second add extends the caller's own reading
    again = lexicon.add("max", kind="familiar", short_for=["maxi"])
    assert again._familiar_forms("max") == shipped | {"maxence", "maxi"}
    assert len([r for r in again.readings_of("max")
                if r.kind == "familiar"]) == len(files) + 1
    added = Lexicon.empty().add("zzq", kind="familiar", short_for=["zzr"])
    assert added._familiar_forms("zzq") == {"zzr"}
    assert added._familiar_forms("zzr") == {"zzq"}
    assert added.words(kind="familiar") == ("zzq",)


def test_a_callers_familiar_form_is_replaced_by_remove_then_add() -> None:
    # a pair lives on its short side: cutting Max / Maximilian is
    # removing max's readings and adding back the names to keep; a
    # reading on Maxie pairing it with Max (added here; none ships) stays
    cut = Lexicon.default().add(
        "maxie", kind="familiar", short_for=["max"]).remove(
        "max", kind="familiar").add(
        "max", kind="familiar", short_for=["maxim", "maksim"])
    assert cut._familiar_forms("max") == {"maksim", "maxim", "maxie"}
    matching = Matching(Parser(lexicon=cut),
                        DEFAULT_ACCEPT | {Outcome.FAMILIAR_FORM})
    assert not matching.check("Max Smith", "Maximilian Smith").consistent
    assert matching.check("Max Smith", "Maxim Smith").consistent


#: Each matching-only kind, its list property and the word it is added
#: to, for the refusals every one of them shares.
_MATCHING_KINDS = (("familiar", "short_for", "max"),
                   ("spelling", "spelling_of", "olha"))


@pytest.mark.parametrize("kind, prop, word", _MATCHING_KINDS)
@pytest.mark.parametrize("value, other, error, match", [
    (None, {}, ValueError, "needs {prop}"),
    ([], {}, ValueError, "non-empty list"),
    (["."], {}, ValueError, "none normalizing to nothing"),
    ([".", "zzr"], {}, ValueError, "none normalizing to nothing"),
    ("{Word}", {}, ValueError, "names the word itself"),
    ("zzr", {}, TypeError, "{prop} must be an iterable"),
    (["zz r"], {}, ValueError, "single given names"),
    (["zzr"], {"same_as": "zzr"}, ValueError, "takes {prop}"),
])
def test_a_callers_matching_reading_is_refused_where_it_lists_no_name(
        kind: str, prop: str, word: str, value: object, other: dict[str, object],
        error: type[Exception], match: str) -> None:
    # the guard, the hint and the refusal for the whole family: every
    # matching-only kind refuses alike (AGENTS.md)
    if value == "{Word}":
        value = [word.title()]
    props = dict(other) if value is None else {prop: value, **other}
    with pytest.raises(error, match=match.format(prop=prop)):
        Lexicon.default().add(word, kind=kind, **props)


@pytest.mark.parametrize("kind, prop, word", _MATCHING_KINDS)
def test_the_code_a_refusal_offers_runs(kind: str, prop: str, word: str) -> None:
    for bad in ({}, {prop: ["."]}):
        with pytest.raises(ValueError) as info:
            Lexicon.default().add(word, kind=kind, **bad)
        offered = re.search(r"e\.g\. (add\(.*\)|\w+=\[.*\])$", str(info.value))
        assert offered is not None, str(info.value)
        code = offered.group(1)
        if not code.startswith("add("):
            code = f"add({word!r}, kind={kind!r}, {code})"
        lexicon = eval(f"Lexicon.default().{code}", {"Lexicon": Lexicon})
        assert kind in {r.kind for r in lexicon.readings_of(eval(code[4:].split(",")[0]))}


def test_a_callers_pair_under_a_strict_choice_reaches_no_other_file() -> None:
    from nameparser import Locale, parser_for
    strict = parser_for(Locale(code="test", lexicon=Lexicon.empty(),
                               languages=frozenset({"de"})), strict=True)
    lexicon = strict.lexicon.add("bill", kind="familiar",
                                 short_for=["william"])
    assert lexicon._familiar_forms("bill") == {"william"}
    assert [r.languages for r in lexicon.readings_of("bill")
            if r.kind == "familiar"] == [()]
    # en.toml's readings do not come back, and de.toml's own pair of
    # max does
    assert not lexicon._familiar_forms("bob")
    assert not lexicon._familiar_forms("peggy")
    assert lexicon._familiar_forms("max") == {"maximilian"}
    assert Parser(lexicon=lexicon).parse("Bill Smith").tokens == strict.parse(
        "Bill Smith").tokens


def test_no_parse_reads_a_familiar_form() -> None:
    # every familiar reading taken out: every set a parse reads, and the
    # parse of every familiar form as a given name, reading and
    # languages included, are what they were
    default = Lexicon.default()
    without = default.remove(kind="familiar", every=True)
    assert default._familiar and not without._familiar
    assert all(getattr(default._sets, f) == getattr(without._sets, f)
               for f in type(default._sets).__slots__)
    assert default._same_as == without._same_as
    assert default._same_as_named == without._same_as_named
    words = sorted(default._familiar)
    for name in ("given", "family", "title", "suffix", "particle"):
        assert default.words(kind=name) == without.words(kind=name)
    bare, plain = Parser(), Parser(lexicon=without)
    for w in words:
        for text in (f"{w.title()} Smith", f"Smith, {w.title()}",
                     f"John {w.title()}"):
            a, b = bare.parse(text), plain.parse(text)
            assert a.tokens == b.tokens and a.ambiguities == b.ambiguities, text


def test_a_choice_of_languages_keeps_its_own_familiar_forms() -> None:
    # a plain choice drops no familiar reading (a choice prefers by none);
    # a strict one keeps its own files' and mul.toml's alone: German's
    # `aleks` and `max` of Maximilian, every language's `ajay`, and not
    # English's `bill` nor any other file's `max`
    plain = Lexicon(_base="default", _languages={"de"})
    assert plain._familiar == Lexicon.default()._familiar
    assert plain._familiar_forms("max") == (
        Lexicon.default()._familiar_forms("max"))
    german = Lexicon(_base="default", _languages={"de"}, _strict=True)
    assert german._familiar_forms("aleks") == {"aleksandra"}
    assert german._familiar_forms("ajay") == {"ajaykumar"}
    assert not german._familiar_forms("bill")
    assert german._familiar_forms("max") == {"maximilian"}


#: Accented pairs as a caller writes them, none of them shipped (the
#: shipped accented pairs are others: `gosia` of `małgorzata`): Hungarian
#: `józsi` of `józsef`, `klára` written long first of `klári`, and `mari`
#: of `mária`.
_ACCENTED = Matching(
    Parser(lexicon=Lexicon.default()
           .add("józsi", kind="familiar", short_for=["józsef"])
           .add("klára", kind="familiar", short_for=["klári"])
           .add("mari", kind="familiar", short_for=["mária"])),
    DEFAULT_ACCEPT | {Outcome.FAMILIAR_FORM})


@pytest.mark.parametrize("a, b", [
    # each accented pair in each of its four spellings: as written, the
    # short name folded, the long name folded, both folded
    ("Józsi Kovács", "József Kovács"), ("Jozsi Kovacs", "József Kovács"),
    ("Józsi Kovács", "Jozsef Kovacs"), ("Jozsi Kovacs", "Jozsef Kovacs"),
    ("Klára Nagy", "Klári Nagy"), ("Klara Nagy", "Klári Nagy"),
    ("Klára Nagy", "Klari Nagy"), ("Klara Nagy", "Klari Nagy"),
    ("Mari Kovács", "Mária Kovács"), ("Mari Kovács", "Maria Kovács"),
])
def test_a_familiar_form_holds_whatever_the_accents(a: str, b: str) -> None:
    for x, y in ((a, b), (b, a)):
        r = _ACCENTED.check(x, y)
        assert r.consistent and role(r, Role.GIVEN).outcome is Outcome.FAMILIAR_FORM
        assert _ACCENTED.keys(x) & _ACCENTED.keys(y)


#: The shipped pairs whose short name reads as a title in front of a
#: name, so the pair is never compared as two given names: a pair is
#: inert while a name of it reads as a title. None since the nicknames
#: list's pairs left (`Ab` / Abraham, `Pres` / Prescott; decisions/
#: shipped-data-licences, 2026-11-13 THE NICKNAMES LIST LEAVES); a new
#: one is a pair to weigh before it ships.
_TITLE_SHORT_FORMS: set[tuple[str, str]] = set()


@pytest.mark.parametrize("table", ["FAMILIAR", "ALTERNATE_SPELLINGS"])
def test_every_shipped_pair_is_consistent_in_every_spelling(table: str) -> None:
    # every shipped pair, familiar form or alternate spelling, each name
    # as written and folded, as given names before one family name:
    # consistent under its opt-in, with a shared key; the pairs whose
    # name parses as a title are the ones listed, and none else is
    # skipped, so a pair shipping inert is a failure here
    from nameparser.config import _compiled
    pairs = getattr(_compiled, table)
    matching = _familiar if table == "FAMILIAR" else _alternate
    assert len(pairs) >= 100, table
    parser = matching.parser
    skipped = set()
    for short, longs in pairs.items():
        for long in longs:
            for a in dict.fromkeys((short, _fold(short))):
                for b in dict.fromkeys((long, _fold(long))):
                    x = parser.parse(f"{a.capitalize()} Kovacs")
                    y = parser.parse(f"{b.capitalize()} Kovacs")
                    if (x.given.casefold(), y.given.casefold()) != (a, b):
                        skipped.add((short, long))
                        continue
                    assert matching.check(x, y).consistent, (a, b)
                    assert matching.keys(x) & matching.keys(y), (a, b)
    assert skipped == (_TITLE_SHORT_FORMS if table == "FAMILIAR" else set())


def test_a_familiar_form_that_reads_as_a_title_is_never_compared() -> None:
    # a pair whose short name reads as a title in front of a name stays
    # inert while that reading stands: no shipped pair is one any more
    # (_TITLE_SHORT_FORMS), so one is planted, as the nicknames list
    # shipped `pres` of Prescott
    lexicon = Lexicon.default().add("pres", kind="familiar",
                                    short_for=["prescott"])
    matching = Matching(Parser(lexicon=lexicon),
                        DEFAULT_ACCEPT | {Outcome.FAMILIAR_FORM})
    pres = matching.parser.parse("Pres Kovacs")
    assert (pres.title, pres.given) == ("Pres", "")
    result = matching.check(pres, "Prescott Kovacs")
    assert not result.consistent
    assert Outcome.FAMILIAR_FORM not in {row.outcome for row in result.roles}
    # the control: the same pair with Pres's title reading taken away
    # reads `familiar-form`, so the title reading alone keeps it inert
    # (without the pair, `Pres Kovacs` / `Prescott Kovacs` would read
    # `given-one-side` either way)
    bare = lexicon.remove("pres", kind="office")
    control = Matching(Parser(lexicon=bare),
                       DEFAULT_ACCEPT | {Outcome.FAMILIAR_FORM})
    assert control.parser.parse("Pres Kovacs").given == "Pres"
    paired = control.check("Pres Kovacs", "Prescott Kovacs")
    assert paired.consistent
    assert paired[Role.GIVEN].outcome is Outcome.FAMILIAR_FORM


def test_a_planted_accented_pair_is_found_from_either_name() -> None:
    # the pair written on the familiar form, accented; the lookup from
    # the unaccented long name reaches it through the fold index
    lexicon = Lexicon.default().remove("mari", kind="familiar").add(
        "mari", kind="familiar", short_for=["mária"])
    matching = Matching(Parser(lexicon=lexicon),
                        DEFAULT_ACCEPT | {Outcome.FAMILIAR_FORM})
    for x, y in (("Mari K", "Maria K"), ("Maria K", "Mari K")):
        assert matching.check(x, y).consistent
        assert matching.keys(x) & matching.keys(y)


@pytest.mark.parametrize("accepted, consistent, outcome", [
    ((), False, Outcome.FAMILIAR_FORM),
    ((Outcome.HYPHENATED_PART,), True, Outcome.HYPHENATED_PART),
    ((Outcome.FAMILIAR_FORM,), True, Outcome.FAMILIAR_FORM),
    ((Outcome.FAMILIAR_FORM, Outcome.HYPHENATED_PART), True,
     Outcome.FAMILIAR_FORM),
])
def test_a_row_reports_the_strongest_accepted_outcome_that_holds(
        accepted: tuple[Outcome, ...], consistent: bool,
        outcome: Outcome) -> None:
    # Jean / Jean-Paul is a hyphenated part and, with this caller's
    # pair, a familiar form: the stronger one, unaccepted, must not hide
    # the weaker one accepted; where neither is, the stronger is shown
    lexicon = Lexicon.default().add("jean", kind="familiar",
                                    short_for=["jean-paul"])
    matching = Matching(Parser(lexicon=lexicon),
                        DEFAULT_ACCEPT | set(accepted))
    for x, y in (("Jean Smith", "Jean-Paul Smith"),
                 ("Jean-Paul Smith", "Jean Smith")):
        r = matching.check(x, y)
        assert r.consistent is consistent
        assert role(r, Role.GIVEN).outcome is outcome
        assert matching.check(y, x) == r.mirrored()
        if consistent:
            assert matching.keys(x) & matching.keys(y)


@pytest.mark.parametrize("a, b, outcome", [
    ("Bill Jack", "William John", Outcome.FAMILIAR_FORM),
    ("Bill Jack", "William Jane", Outcome.CONFLICT),
    ("Bill", "William Jack", Outcome.CONFLICT),
    ("Bill Jack", "William Jack", Outcome.FAMILIAR_FORM),
])
def test_every_word_of_a_given_name_must_agree(
        a: str, b: str, outcome: Outcome) -> None:
    # a given name of several words (as a bound pair or a caller's
    # replace makes one) reads familiar-form only where every word is
    # the same, a listed spelling or a familiar form, word for word
    base = parse("John Smith")
    x, y = base.replace(given=a), base.replace(given=b)
    r = _familiar.check(x, y)
    assert role(r, Role.GIVEN).outcome is outcome
    assert r.consistent is (outcome is Outcome.FAMILIAR_FORM)


@pytest.mark.parametrize("word, kind", [
    ("dr", "title"), ("van", "particle"), ("jr", "suffix"), ("ma", "given"),
])
def test_a_callers_familiar_reading_moves_no_parse(word: str, kind: str) -> None:
    # a familiar reading on a title, particle, suffix or name word
    # changes no token, reading or language, under the default and
    # under a strict choice
    from nameparser import Locale, parser_for
    assert any(r.category == kind or r.kind == kind
               for r in Lexicon.default().readings_of(word))
    texts = (f"{word.title()} John Smith", f"John {word.title()} Smith",
             f"John Smith {word.title()}", f"Smith, John {word.title()}")
    strict = parser_for(Locale(code="test", lexicon=Lexicon.empty(),
                               languages=frozenset({"en"})), strict=True)
    for base in (Parser(), strict):
        mine = Parser(lexicon=base.lexicon.add(
            word, kind="familiar", short_for=["zzqname"]),
            policy=base.policy)
        assert mine.lexicon._familiar_forms(word) >= {"zzqname"}
        for text in texts:
            a, b = base.parse(text), mine.parse(text)
            assert a.tokens == b.tokens and a.ambiguities == b.ambiguities, text


#: Narrowing `accept` still refuses: each pair's row reads, on the
#: default, an outcome the narrowed setting drops, and no weaker outcome
#: that outcome implies stands in for it (decisions/name-matching,
#: 2026-11-08 FAMILIAR FORMS, the review's ruling 1).
_IMPLIED_ROWS = [
    ("John Smith", "John SMITH", Outcome.FOLDED, {Role.FAMILY: Outcome.FOLDED}),
    ("José García", "José Garcia", Outcome.FOLDED, {Role.FAMILY: Outcome.FOLDED}),
    ("John O'Brien", "John OBrien", Outcome.FOLDED,
     {Role.FAMILY: Outcome.FOLDED}),
    ("J. Smith", "J Smith", Outcome.FOLDED, {Role.GIVEN: Outcome.FOLDED}),
    ("J. P. Smith", "J P Smith", Outcome.FOLDED,
     {Role.GIVEN: Outcome.FOLDED, Role.MIDDLE: Outcome.FOLDED}),
    ("John de la Vega", "John Vega", Outcome.PARTICLES_ASIDE,
     {Role.FAMILY: Outcome.PARTICLES_ASIDE}),
]


@pytest.mark.parametrize("a, b, dropped, rows", _IMPLIED_ROWS)
def test_narrowing_accept_refuses_and_no_implied_outcome_stands_in(
        a: str, b: str, dropped: Outcome, rows: dict[Role, Outcome]) -> None:
    default = m.check(a, b)
    assert default.consistent
    for which, outcome in rows.items():
        assert role(default, which).outcome is outcome
    narrowed = Matching(Parser(), DEFAULT_ACCEPT - {dropped})
    for x, y in ((a, b), (b, a)):
        r = narrowed.check(x, y)
        assert not r.consistent
        for which, outcome in rows.items():
            assert role(r, which).outcome is outcome


def test_an_equal_given_name_reads_folded_beside_a_conflicting_family() -> None:
    r = m.check("J. Smith", "J Garcia")
    assert role(r, Role.GIVEN).outcome is Outcome.FOLDED
    assert role(r, Role.FAMILY).outcome is Outcome.CONFLICT


def test_every_role_has_one_rule_and_its_columns_agree() -> None:
    # the table holds each role's rules (#1260): a Role added without a
    # row would raise KeyError in the check, so the table is held to the
    # enum here rather than found missing there
    from nameparser._match import _compare_noted, _compare_suffix
    assert list(_RULES) == list(Role)
    for role, rule in _RULES.items():
        # a cross role is another role of the same group: the keys cut a
        # cross role's words in the role's own group
        assert role not in rule.across
        assert all(_RULES[other].group == rule.group for other in rule.across)
        # a role another reading is not tried into is one whose
        # comparator conflicts on no text (the title, noted) or only on
        # a generation (the suffix), so a word moved there could only
        # empty a role that does
        never_conflicts = rule.compare in (_compare_noted, _compare_suffix)
        assert rule.tried_into is not never_conflicts, role
        # a comparator reading the names whole takes no empty-side cells
        assert (rule.empty is None) is (rule.compare is _compare_suffix), role


# -- each role's rule, on the paths the corpora never reach (#1260) ---------
# A one-cell change to `_RULES` that no corpus pair reaches is held here:
# the review of #1260 mutated every cell and found these paths moved by
# nothing else (decisions/name-matching, 2026-11-09 #1260).

@pytest.mark.parametrize("a, b, outcome", [
    ("Jane Doe (née Smith)", "Jane Doe (née Jones)", Outcome.CONFLICT),
    ("Jane Doe (née Smith)", "Jane Doe (née SMITH)", Outcome.FOLDED),
    # read in the family group: Mc is listed as a spelling of Mac there
    ("Jane Doe (née Mc)", "Jane Doe (née Mac)", Outcome.LISTED_SPELLING),
    # its particles set aside, and part of the other, as the family
    # name's are (#1264; a conflict before)
    ("Jane Doe (née de la Vega)", "Jane Doe (née Vega)",
     Outcome.PARTICLES_ASIDE),
    ("Jane Doe (née Smith Jones)", "Jane Doe (née Smith)",
     Outcome.PART_OF_OTHER),
])
def test_a_maiden_name_on_both_sides_is_compared_as_a_surname(
        a: str, b: str, outcome: Outcome) -> None:
    for x, y in ((a, b), (b, a)):
        r = m.check(x, y)
        assert r["maiden"].outcome is outcome
        assert r.consistent is (outcome is not Outcome.CONFLICT)


def test_a_maiden_name_is_not_matched_across_into_the_family() -> None:
    # the family is tried against the other's maiden name; the maiden is
    # not tried against the other's family, so a swap still conflicts
    across = Matching(Parser(), DEFAULT_ACCEPT | {Outcome.ACROSS_ROLES})
    r = across.check("Jane Smith (née Doe)", "Jane Doe (née Smith)")
    assert r["family"].outcome is Outcome.ACROSS_ROLES
    assert r["maiden"].outcome is Outcome.CONFLICT and not r.consistent


def test_a_nickname_of_several_words_is_compared_whole() -> None:
    r = m.check('John "Billy Joe" Smith', 'John "Billy" Smith')
    assert r["nickname"].outcome is Outcome.CONFLICT and not r.consistent


def test_a_nickname_is_not_matched_across_into_the_given_name() -> None:
    # the given name is tried against the other's nickname; the nickname
    # is not tried against the other's given name, so a swap still
    # conflicts in the nickname
    across = Matching(Parser(), DEFAULT_ACCEPT | {Outcome.ACROSS_ROLES})
    r = across.check('John "Billy" Smith', 'Billy "John" Smith')
    assert r["given"].outcome is Outcome.ACROSS_ROLES
    assert r["nickname"].outcome is Outcome.CONFLICT and not r.consistent
    assert len(r.across) == 1


def test_a_title_on_one_side_is_noted() -> None:
    r = m.check("Sir John Smith", "John Smith")
    assert r["title"].outcome is Outcome.NOTED and r.consistent


def test_another_reading_is_tried_into_the_middle_and_the_given_name() -> None:
    # `Smith John V` read family first reads V as the generation, its
    # other reading as a middle name (family first) or as the given
    # name's second word (given last); a family comma offers the same
    # under the default order (`Smith, John V`)
    from nameparser import FAMILY_FIRST, FAMILY_FIRST_GIVEN_LAST, Policy
    first = Parser(policy=Policy(name_order=FAMILY_FIRST))
    r = first.matching(other_readings=True).check(
        "Smith John V", "Smith John Victor III")
    assert r.consistent and r.left_alternative is not None
    assert r["middle"].outcome is Outcome.INITIAL
    last = Parser(policy=Policy(name_order=FAMILY_FIRST_GIVEN_LAST))
    other = last.revise(last.parse("Smith Victor III"), given="John Victor")
    r = last.matching(other_readings=True).check("Smith John V", other)
    assert r.consistent and r.left_alternative is not None
    assert r["given"].outcome is Outcome.INITIAL


def test_a_hand_built_middle_of_whitespace_alone_compares_without_raising() -> None:
    # parse() never writes one, but a ParsedName built by hand may: the
    # table hands both texts to the middle's comparator as present, and
    # its words are none, so the two middles agree rather than the
    # weakest of no outcomes raising (decisions/name-matching #1260)
    from nameparser import Token
    name = parse("John Smith")
    blank = ParsedName(name.original,
                       (*name.tokens, Token("　", None, Role.MIDDLE)))
    r = m.check(blank, blank)
    assert r["middle"].outcome is Outcome.SAME and r.consistent


# -- a listed surname spelling inside a compound surname (#1262) -------------

#: smyth and schmidt listed as smith, smithe as smyth (a chain), and the
#: surname vance as the particle van, which a base sets aside.
_SMYTH_LEXICON = (Lexicon.default()
                  .add("smyth", "schmidt", kind="family", same_as="smith")
                  .add("smithe", kind="family", same_as="smyth")
                  .add("vance", kind="family", same_as="van"))
_SMYTH = Matching(Parser(lexicon=_SMYTH_LEXICON))


@pytest.mark.parametrize("a, b, outcome", [
    ("Ann Smyth", "Ann Smith", Outcome.LISTED_SPELLING),
    # a listed half among the other's words
    ("Ann Smyth-Jones", "Ann Smith", Outcome.PART_OF_OTHER),
    ("Ann Smyth-Jones", "Ann Smith-Jones", Outcome.PART_OF_OTHER),
    ("Ann Smithe-Jones", "Ann Smith", Outcome.PART_OF_OTHER),
    # the bases listed word for word, particles set aside, a family
    # comma giving a base of several words
    ("Ann de Smyth", "Ann Smith", Outcome.PARTICLES_ASIDE),
    ("Ann de la Smyth", "Ann de Smith", Outcome.PARTICLES_ASIDE),
    ("de Smyth Jones, Ann", "Smith Jones, Ann", Outcome.PARTICLES_ASIDE),
    # every word of one side must be covered, not one of them
    ("Ann Smyth-Jones", "Ann Smith-Brown", Outcome.CONFLICT),
    ("Ann Smith-Jones", "Ann Smith-Brown", Outcome.CONFLICT),
    ("de Smyth Jones, Ann", "Smith Brown, Ann", Outcome.CONFLICT),
    ("García López, Ann", "García Pérez, Ann", Outcome.CONFLICT),
    # a half that is no listed spelling, and a surname listed as a
    # particle, which the base sets aside before comparing
    ("Ann Smyth-Jones", "Ann Brown", Outcome.CONFLICT),
    ("Ann Vance", "Ann van Smith", Outcome.CONFLICT),
])
def test_a_listed_surname_spelling_counts_inside_a_compound_surname(
        a: str, b: str, outcome: Outcome) -> None:
    for x, y in ((a, b), (b, a)):
        r = _SMYTH.check(x, y)
        assert r["family"].outcome is outcome, (x, y)
        assert r.consistent is (outcome is not Outcome.CONFLICT)
        if r.consistent:
            assert _SMYTH.keys(x) & _SMYTH.keys(y)


@pytest.mark.parametrize("a, b", [
    # Wm is listed as William among given names: a surname word is read
    # in the family group, where Wm is no spelling of anything
    ("Jack Wm-Lee", "Jack William"),
    ("Jack de Wm", "Jack William"),
])
def test_a_given_name_spelling_does_not_count_inside_a_surname(
        a: str, b: str) -> None:
    for x, y in ((a, b), (b, a)):
        r = m.check(x, y)
        assert r["family"].outcome is Outcome.CONFLICT and not r.consistent


#: Compound surnames written with the caller's spellings and without,
#: hyphenated, behind particles and before a family comma.
_COMPOUNDS: tuple[str, ...] = (
    "Ann Smith", "Ann Smyth", "Ann Schmidt", "Ann Smithe", "Ann Vance",
    "Ann Smith-Jones", "Ann Smyth-Jones", "Ann Jones-Schmidt",
    "Ann Smithe-Brown", "Ann de Smyth", "Ann van Smith", "Ann de la Smith",
    "A. Smyth-Jones", "Smyth Jones, Ann", "de Smith Jones, Ann",
    "Ann Jones", "Ann Smith (née Smyth-Jones)", "Ann Smyth (née Jones)",
    "Ann Doe (née Schmidt)",
)


@pytest.mark.parametrize("setting", SETTINGS, ids=_SETTING_IDS)
def test_listed_compound_surnames_keep_the_key_guarantee_and_symmetry(
        setting: tuple[frozenset[Outcome], bool]) -> None:
    accept, other_readings = setting
    matching = Matching(Parser(lexicon=_SMYTH_LEXICON), accept,
                        other_readings=other_readings)
    for a in _COMPOUNDS:
        for b in _COMPOUNDS:
            r = matching.check(a, b)
            assert matching.check(b, a) == r.mirrored(), (a, b)
            if r.consistent:
                assert matching.keys(a) & matching.keys(b), (a, b)


# -- a family name written with its spaces or hyphens dropped (#1261) --------

@pytest.mark.parametrize("a, b, role_name", [
    ("Ignazio LaRussa", "Ignazio La Russa", "family"),
    ("IGNAZIO LARUSSA", "Ignazio La Russa", "family"),
    ("Ann SmithJones", "Ann Smith-Jones", "family"),
    ("Ann Vanderberg", "Ann Van der Berg", "family"),
    ("Charles DeGaulle", "Charles de Gaulle", "family"),
    ("Լևոն Տեր-Պետրոսյան", "Լևոն Տեր Պետրոսյան", "family"),
    ("ALCIDES DINIZ DASILVA", "ALCIDES DINIZ DA SILVA", "family"),
    ("Jeanpierre Martin", "Jean-Pierre Martin", "given"),
    ("Jane Doe (née LaRussa)", "Jane Doe (née La Russa)", "maiden"),
])
def test_a_name_written_with_its_spaces_or_hyphens_dropped_is_joined(
        a: str, b: str, role_name: str) -> None:
    for x, y in ((a, b), (b, a)):
        r = m.check(x, y)
        assert r[role_name].outcome is Outcome.JOINED, (x, y)
        assert r.consistent and m.keys(x) & m.keys(y)


@pytest.mark.parametrize("a, b", [
    # letters that differ, not only their spacing
    ("Ann LaRusso", "Ann La Russa"),
    ("Ann Smith Jones", "Ann SmithJones"),  # Smith is the middle name here
])
def test_a_joined_name_needs_the_same_letters(a: str, b: str) -> None:
    for x, y in ((a, b), (b, a)):
        assert not m.check(x, y).consistent


def test_initials_written_apart_stay_initials_agree_beside_joined() -> None:
    # two texts of initials alone are initials-agree's to read, so a
    # caller who does not accept joined keeps accepting them
    base = parse("John Smith")
    without = Matching(Parser(), DEFAULT_ACCEPT - {Outcome.JOINED})
    for matching in (m, without):
        r = matching.check(base.replace(given="J.-P."),
                           base.replace(given="J. P."))
        assert r.consistent
        assert role(r, Role.GIVEN).outcome is Outcome.INITIALS_AGREE


def test_a_caller_without_joined_keeps_the_leniencies_it_accepted() -> None:
    # joined does not end the outcomes the way folded does: the family
    # leniencies that read the words apart are still asked after it
    without = Matching(Parser(), DEFAULT_ACCEPT - {Outcome.JOINED})
    r = without.check("Ann De La Cruz", "Ann Dela Cruz")
    assert r["family"].outcome is Outcome.PARTICLES_ASIDE and r.consistent
    assert m.check("Ann De La Cruz", "Ann Dela Cruz")["family"].outcome is (
        Outcome.JOINED)
    # and a pair only joined reads is refused, as on master
    r = without.check("Ignazio LaRussa", "Ignazio La Russa")
    assert r["family"].outcome is Outcome.JOINED and not r.consistent


#: Family names written joined and apart, behind particles, hyphenated,
#: before a family comma and as a maiden name.
_JOINED_NAMES: tuple[str, ...] = (
    "Ignazio LaRussa", "Ignazio La Russa", "Ignazio La-Russa",
    "Ann Vanderberg", "Ann Van der Berg", "Ann van der-Berg",
    "Ann SmithJones", "Ann Smith-Jones", "Smith Jones, Ann",
    "Ann De La Cruz", "Ann Dela Cruz", "Ann Delacruz",
    "Jane Doe (née LaRussa)", "Jane LaRussa (née Doe)",
    "Jane Doe (née La Russa)", "J. LaRussa", "Jean-Pierre Martin",
    "Jeanpierre Martin",
    # a stray leading hyphen, which joined reads past: the given letter
    # is the first letter once joined, in the given name and in the
    # middle name and nickname across-roles compares it with
    "-Pierre Dupont", "Pierre Dupont", "Dupont, -Pierre",
    "Jean -Pierre Dupont", "Jean (-Pierre) Dupont",
    # no given name beside a nickname: the empty given letter stays
    # beside the nickname's under across-roles
    "Pastor Saycon", 'Pastor "Boy" Saycon',
    # a first word of a hyphen or a full stop alone, which joined reads
    # past: the letter comes from the first word that joins to something
    '"- Boy" Dupont', '". Boy" Dupont', "Pierre (- Boy) Dupont",
    "Boy Dupont",
)


@pytest.mark.parametrize("setting", SETTINGS, ids=_SETTING_IDS)
def test_joined_names_keep_the_key_guarantee_and_symmetry(
        setting: tuple[frozenset[Outcome], bool]) -> None:
    accept, other_readings = setting
    matching = Matching(Parser(), accept, other_readings=other_readings)
    for a in _JOINED_NAMES:
        for b in _JOINED_NAMES:
            r = matching.check(a, b)
            assert matching.check(b, a) == r.mirrored(), (a, b)
            if r.consistent:
                assert matching.keys(a) & matching.keys(b), (a, b)



def test_a_noted_role_reads_noted_where_its_spelling_is_not_accepted() -> None:
    # a title or a suffix never conflicts: equal by an outcome the caller
    # refuses, it reads noted, which is accepted, as it did before joined
    for dropped, a, b, role_name in (
            (Outcome.JOINED, "John Smith Ph D", "John Smith PhD", "suffix"),
            (Outcome.JOINED, "Lt Col John Smith", "LtCol John Smith", "title"),
            (Outcome.FOLDED, "John Smith PHD", "John Smith PhD", "suffix")):
        without = Matching(Parser(), DEFAULT_ACCEPT - {dropped})
        r = without.check(a, b)
        assert r[role_name].outcome is Outcome.NOTED and r.consistent
        assert m.check(a, b)[role_name].outcome is dropped


def test_a_caller_without_joined_keeps_a_hyphenated_part_it_accepted() -> None:
    # the given role's leniencies are asked after joined too
    accept = (DEFAULT_ACCEPT | {Outcome.HYPHENATED_PART}) - {Outcome.JOINED}
    matching = Matching(Parser(), accept)
    base = parse("Hong Smith")
    for a, b in ((base, base.replace(given="Hong-")),
                 ("Hong Smith", "Hong- Smith"), ("Smith, Hong", "Smith, Hong-")):
        r = matching.check(a, b)
        assert r["given"].outcome is Outcome.HYPHENATED_PART and r.consistent


def test_joined_ranks_below_folded_and_above_listed_spelling() -> None:
    # the decided place in the order, seen through weakest
    assert m.check("IGNAZIO LARUSSA", "Ignazio La Russa").weakest is (
        Outcome.JOINED)
    assert m.check("Wm. LaRussa", "William La Russa").weakest is (
        Outcome.LISTED_SPELLING)


@pytest.mark.parametrize("a, b", [
    # one side written in initials alone, the other joined into one word,
    # reads joined: only two texts of initials alone are initials-agree's
    ("JP", "J. P."), ("JP", "J.-P."), ("J.P.", "J.-P."),
])
def test_initials_against_their_letters_joined_read_joined(
        a: str, b: str) -> None:
    base = parse("John Smith")
    r = m.check(base.replace(given=a), base.replace(given=b))
    assert r["given"].outcome is Outcome.JOINED and r.consistent


@pytest.mark.parametrize("stray", ["- ", ". "])
def test_a_given_name_opening_with_a_stray_mark_keys_its_first_letter(
        stray: str) -> None:
    base = parse("Ann Dupont")
    a, b = base.replace(given=stray + "Pierre"), base.replace(given="Pierre")
    assert m.check(a, b).consistent
    assert m.keys(a) == m.keys(b) == {"dupont;p"}


# -- middle names aligned as a subsequence (#1263) -----------------------------

@pytest.mark.parametrize("a, b", [
    ("John Beth Smith", "John Anne Beth Smith"),
    ("John B. Smith", "John A. B. Smith"),
    ("Gonzalo Fernández Llona", "Gonzalo José Fernández Llona"),
    ("John Anne Smith", "John Anne Marie Beth Smith"),
])
def test_a_middle_name_aligns_with_any_words_of_a_longer_one(
        a: str, b: str) -> None:
    for x, y in ((a, b), (b, a)):
        r = m.check(x, y)
        assert r["middle"].outcome is Outcome.ONE_SIDE and r.consistent
        assert m.keys(x) & m.keys(y)


@pytest.mark.parametrize("a, b", [
    # as many words: compared pair by pair, so a typo still conflicts
    ("Abdon Assis Injosa Andrade", "Abdon Assis Inojosa Andrade"),
    # the order of the words is kept
    ("John Anne Beth Smith", "John Beth Anne Smith"),
    # a word of the shorter side that no word of the longer agrees with
    ("John Clara Smith", "John Anne Beth Smith"),
])
def test_a_middle_name_still_conflicts_where_no_alignment_holds(
        a: str, b: str) -> None:
    for x, y in ((a, b), (b, a)):
        r = m.check(x, y)
        assert r["middle"].outcome is Outcome.CONFLICT and not r.consistent


def test_a_consumed_middle_word_leaves_the_rest_to_align() -> None:
    # across-roles: John is the other's middle name, consumed, and what is
    # left (Beth against Anne Beth) aligns, a conflict from the left
    across = Matching(Parser(), DEFAULT_ACCEPT | {Outcome.ACROSS_ROLES})
    r = across.check("John Beth Hoover", "Edgar John Anne Beth Hoover")
    assert r.consistent and r["given"].outcome is Outcome.ACROSS_ROLES
    assert r["middle"].outcome is Outcome.ONE_SIDE


@pytest.mark.parametrize("a, b", [
    # Edgar and John each match the other's given name across roles;
    # consuming Edgar leaves Anne Beth / John Beth, which conflict, and
    # consuming John leaves Edgar Anne Beth / Beth, which align
    ("John Edgar Anne Beth Hoover", "Edgar John Beth Hoover"),
    ("John Anne Beth Carol Smith", "Anne John Carol Smith"),
])
def test_the_middle_word_consumed_is_the_one_that_leaves_the_rest_agreeing(
        a: str, b: str) -> None:
    across = Matching(Parser(), DEFAULT_ACCEPT | {Outcome.ACROSS_ROLES})
    for x, y in ((a, b), (b, a)):
        r = across.check(x, y)
        assert r.consistent and r["middle"].outcome is Outcome.ONE_SIDE
        assert [c.left for c in r.across] == ["John"]


def test_the_consumption_leaving_the_middle_accepted_outranks_a_stronger_match(
        ) -> None:
    # John matches John (same) and Jose matches José (folded): consuming
    # John leaves Anne Beth / José Beth, a conflict, so the weaker match,
    # which leaves an accepted middle, is the one taken
    across = Matching(Parser(), DEFAULT_ACCEPT | {Outcome.ACROSS_ROLES})
    a, b = "Jose John Anne Beth Smith", "John José Beth Smith"
    for x, y in ((a, b), (b, a)):
        r = across.check(x, y)
        assert r.consistent and r["middle"].outcome is Outcome.ONE_SIDE
        assert {r.across[0].left, r.across[0].right} == {"Jose", "José"}


@pytest.mark.parametrize("a, b", [
    # the left reading pairs Max with Maximilian, a familiar form, refused
    # here; the alignment pairs it with Max-Paul, a hyphenated part,
    # accepted: the accepted reading is taken though it is weaker
    ("John Max Smith", "John Maximilian Max-Paul Smith"),
    ("John Bill Smith", "John William Bill-Bob Smith"),
])
def test_an_accepted_reading_of_a_middle_name_outranks_a_refused_one(
        a: str, b: str) -> None:
    hyphenated = Matching(Parser(), DEFAULT_ACCEPT | {Outcome.HYPHENATED_PART})
    for x, y in ((a, b), (b, a)):
        r = hyphenated.check(x, y)
        assert r["middle"].outcome is Outcome.HYPHENATED_PART and r.consistent


def test_an_aligned_pair_must_be_accepted() -> None:
    # B. aligns with Beth only by initial: refused, it aligns nowhere
    without = Matching(Parser(), DEFAULT_ACCEPT - {Outcome.INITIAL})
    for x, y in (("John B. Smith", "John Anne Beth Smith"),
                 ("John Anne Beth Smith", "John B. Smith")):
        r = without.check(x, y)
        assert r["middle"].outcome is Outcome.CONFLICT and not r.consistent


@pytest.mark.parametrize("a, b", [
    # the left reading pairs Max with Maximilian, a familiar form; the
    # alignment pairs it with Max, the same word: the stronger is taken,
    # so accepting familiar-form does not weaken the row
    ("John Max Smith", "John Maximilian Max Smith"),
    # among the alignments the strongest is taken, wherever it stands
    ("John Max Smith", "John Anne Maximilian Max Smith"),
    ("John Max Smith", "John Anne Max Maximilian Smith"),
])
def test_the_strongest_reading_of_a_middle_name_is_taken(
        a: str, b: str) -> None:
    familiar = Matching(Parser(), DEFAULT_ACCEPT | {Outcome.FAMILIAR_FORM})
    for x, y in ((a, b), (b, a)):
        r = familiar.check(x, y)
        assert r["middle"].outcome is Outcome.ONE_SIDE and r.consistent


@pytest.mark.parametrize("a, b", [
    ("John Bill Smith", "John William Anne Smith"),  # from the left
    ("John Bill Smith", "John Anne William Smith"),  # aligned
])
def test_a_word_left_over_is_refused_where_one_side_is(a: str, b: str) -> None:
    # an accepted familiar form, weaker than one-side, does not hide the
    # one-sided word from a caller who refuses one-side
    accept = (DEFAULT_ACCEPT - {Outcome.ONE_SIDE}) | {Outcome.FAMILIAR_FORM}
    matching = Matching(Parser(), accept)
    for x, y in ((a, b), (b, a)):
        r = matching.check(x, y)
        assert r["middle"].outcome is Outcome.ONE_SIDE and not r.consistent


_MIDDLES: tuple[str, ...] = (
    "John Smith", "John A. Smith", "John Anne Smith", "John Beth Smith",
    "John Anne Beth Smith", "John Beth Anne Smith", "John A. B. Smith",
    "John Anne B. Smith", "John Anne Marie Beth Smith", "John Ann Smith",
    # across-roles: a given name the other holds as a middle name, the
    # rest left to align; familiar-form: a middle name's familiar form
    "Edgar John Anne Beth Smith", "John Edgar Beth Smith",
    "John Max Smith", "John Maximilian Max Smith",
    "John Edgar Anne Beth Smith", "Edgar John Beth Smith",
)


@pytest.mark.parametrize("setting", SETTINGS, ids=_SETTING_IDS)
def test_aligned_middle_names_keep_the_key_guarantee_and_symmetry(
        setting: tuple[frozenset[Outcome], bool]) -> None:
    accept, other_readings = setting
    matching = Matching(Parser(), accept, other_readings=other_readings)
    for a in _MIDDLES:
        for b in _MIDDLES:
            r = matching.check(a, b)
            assert matching.check(b, a) == r.mirrored(), (a, b)
            if r.consistent:
                assert matching.keys(a) & matching.keys(b), (a, b)


# rules/T7 (#1296): a given name written as a run of initials parts
# into them, and the name match reads each initial as a word of its
# own, the field writing a longer run's middle letters together
@pytest.mark.parametrize("glued,apart", [
    ("E.T. Smith", "E. T. Smith"),
    ("E.T. Smith", "Edward T. Smith"),
    ("E.T. Smith", "Edward Thomas Smith"),
    ("E.T. Smith", "Edward Smith"),
    ("Smith, E.T.", "Edward Smith"),
    ("J.R.R. Tolkien", "John Ronald Reuel Tolkien"),
    ("J.P. Smith", "John Paul Smith"),
    ("J.R.R. Tolkien", "J. R. R. Tolkien"),
    ("J.R.R. Tolkien", "J. R. Tolkien"),
    ("J.R. Smith", "j.r. smith"),
])
def test_a_given_name_written_as_initials_run_together_matches_them_apart(
        glued: str, apart: str) -> None:
    matching = Parser().matching()
    assert matching.check(glued, apart).consistent
    assert set(matching.keys(glued)) & set(matching.keys(apart))


def test_initials_run_together_still_conflict_where_a_letter_does() -> None:
    # the control: parted letters are compared, not waved through
    matching = Parser().matching()
    assert not matching.check("J.R.R. Tolkien", "John Ronald Peter Tolkien"
                              ).consistent
    assert not matching.check("E.T. Smith", "T. Smith").consistent


def test_the_table_shows_a_run_of_initials_as_written() -> None:
    # the comparison reads 'R. R.'; the table keeps the field's 'R.R.'
    result = Parser().matching().check("J.R.R. Tolkien",
                                       "John Ronald Reuel Tolkien")
    middle = next(r for r in result.roles if r.role is Role.MIDDLE)
    assert (middle.left, middle.right) == ("R.R.", "Ronald Reuel")


@pytest.mark.parametrize("left,right,consistent", [
    ("Smith J.R.R.", "Smith J. R. R.", True),
    ("Smith E.T.", "Smith Edward Thomas", True),
    ("Smith E.T.", "Smith Thomas", True),
    # the given name is the last letter there, T. against Edward
    ("Smith E.T.", "Smith Edward", False),
])
def test_a_run_of_initials_matches_under_the_given_last_order(
        left: str, right: str, consistent: bool) -> None:
    # rules/T7 makes the run's last letter the given name under
    # FAMILY_FIRST_GIVEN_LAST, and the middle letters stay written
    # together, which the match reads one by one (#1296)
    from nameparser import FAMILY_FIRST_GIVEN_LAST, Policy
    matching = Parser(
        policy=Policy(name_order=FAMILY_FIRST_GIVEN_LAST)).matching()
    assert matching.check(left, right).consistent is consistent
    assert bool(set(matching.keys(left)) & set(matching.keys(right))) \
        is consistent


def test_only_two_initials_written_together_read_as_two_words() -> None:
    # _role_text parts two written-together tokens only where both are
    # initials (rules/T7, #1296); two that are not stay one word, as the
    # field writes them. No parse builds the second today, so it is
    # built by hand.
    from nameparser._match import _role_text
    from nameparser._types import Span, Token
    initials = ParsedName(original="J.R. Smith", tokens=(
        Token("J.", Span(0, 2), Role.GIVEN, frozenset({"initial"})),
        Token("R.", Span(2, 4), Role.GIVEN, frozenset({"initial"})),
        Token("Smith", Span(5, 10), Role.FAMILY)))
    words = ParsedName(original="Ab.c Smith", tokens=(
        Token("Ab.", Span(0, 3), Role.GIVEN),
        Token("c", Span(3, 4), Role.GIVEN),
        Token("Smith", Span(5, 10), Role.FAMILY)))
    assert (initials.given, _role_text(initials, Role.GIVEN)) == ("J.R.", "J. R.")
    assert (words.given, _role_text(words, Role.GIVEN)) == ("Ab.c", "Ab.c")


# -- any of the pipeline's hyphens is a hyphen (#1264) ------------------------

#: Names holding the hyphen-minus wherever a hyphen stands and the
#: parser reads the name alike whichever hyphen it holds: in a family
#: name (before and after a family comma), a given name and a maiden
#: name, beside a particle half (`Al-`, `al-`, `Ter-`), in a title at
#: the head, at the end and after a comma (`Dipl.-Ing.`, `Lt.-Col.`,
#: `Dr.-Ing.`), doubled, leading, trailing, stray before a given name
#: or a nickname (#1261's rows), and spaced as a separator, which must
#: read as the spaced hyphen-minus does and never join the words it
#: stands between. No suffix written with a hyphen is among them: the
#: parser reads none alike (`_PARSER_HYPHEN_LIMITS`). Each is read again
#: with every other hyphen in the hyphen-minus's place
#: (test_any_hyphen_reads_as_the_hyphen_minus).
_HYPHENATED: tuple[str, ...] = (
    "Ann Smith-Jones", "Smith-Jones, Ann", "Smith-Jones Ann",
    "Jean-Paul Smith", "Ann Smith (née Vega-Gómez)",
    "Ana Ruiz (née de la Vega-Gómez)", "Ahmed Al-Saud", "Sami al-Rashid",
    "Levon Ter-Petrosyan", "Ann Smith--Jones", "Ann -Smith", "Ann Smith-",
    "- Pierre Dupont", '"- Boy" Dupont', "Dipl.-Ing. Hans Meier",
    "Hans Meier Dipl.-Ing.", "John Smith Lt.-Col.", "Hans Meier, Dr.-Ing.",
    "Hong-Yi Guo", "Kim Min-jun", "J.-P. Dupont",
    "Ann Smith - Jones", "Jean - Pierre Dupont", "John Smith-Jones Jr.",
)

#: What they are compared with besides one another: each one's parts,
#: written whole, spaced, joined and with the hyphen-minus.
_HYPHEN_PARTNERS: tuple[str, ...] = (
    "Ann Smith", "Ann Jones", "Ann SmithJones", "Ann Smith Jones",
    "Smith, Ann", "Smith Ann", "Jean Smith", "Jeanpaul Smith", "J. Smith",
    "Ann Smith (née Vega)", "Ann Smith (née Gómez)", "Ana Ruiz (née Vega)",
    "Ahmed Saud", "Ahmed Al", "Sami Rashid", "Levon Petrosyan",
    "Pierre Dupont", "Boy Dupont", "Hans Meier", "Dr. Hans Meier",
    "John Smith", "Lt. Col. John Smith",
    "Hong Guo", "Kim Min Jun", "Jean-Pierre Dupont", "John Smith Jr.",
)

#: The other hyphens rules/O6 lists, written out here rather than read
#: from `_HYPHEN_CHARS`, so a character leaving that set fails the
#: parse parity and the match below, the hyphen-minus being the one
#: they are read as.
_OTHER_HYPHENS = "\u2010\u2011\u2012\u2013\u2212\ufe63\uff0d"

#: Characters that are no hyphen, each of which makes the parser read
#: some name of `_HYPHENATED` differently (a trailing title written
#: with one is no title shape), so a character joining the set fails
#: test_no_other_character_reads_as_a_hyphen.
_NOT_HYPHENS = "\u2014\u2015/~"


@functools.cache
def _hyphen_parse(parser_id: str, text: str) -> ParsedName:
    return _SHAPE_PARSERS[parser_id].parse(text)


def _reads_as(result: MatchResult, ascii: MatchResult) -> bool:
    """`result` reads as `ascii`, the same pair with the hyphen-minus
    written in place of another hyphen: the same verdict and each row's
    outcome, save that a row `ascii` reads `same` may read `folded`
    where its two texts differ."""
    return result.consistent is ascii.consistent and all(
        r.outcome is a.outcome or (
            a.outcome is Outcome.SAME and r.outcome is Outcome.FOLDED
            and r.left != r.right)
        for r, a in zip(result.roles, ascii.roles))


@pytest.mark.parametrize("parser_id", list(_SHAPE_PARSERS))
def test_any_hyphen_reads_as_the_hyphen_minus(parser_id: str) -> None:
    """Every hyphen of `_HYPHEN_CHARS` reads as the hyphen-minus, on
    either side, on both and in the keys alike (#1264), under the
    default and with every opt-in and the other-reading switch on: a
    name written with one has the keys of the name written with the
    hyphen-minus, and compared with that name, with every partner and
    with every other hyphenated name written with the en dash (U+2010
    for the en dash itself), in either order, reads as the hyphen-minus
    pair does (`_reads_as`); a consistent pair shares a key. Linear in
    the names, so every hyphen is read; the pairwise grids read U+2010
    and the en dash (NAMES, `_SHAPE_NAMES`). The parser reads each name
    alike whichever hyphen it holds, every field the hyphen-minus
    reading with the hyphen written back, which this test asserts too,
    so the rest is the match's reading alone, for these names: the
    names the parser reads differently are `_PARSER_HYPHEN_LIMITS`. About
    3.3 seconds a parser, serial (2026-11-11). Negative controls, taken
    2026-11-11 with each mutation applied and reverted, every one failing
    all four parsers: the fold mapping no hyphen; `_part_agrees` cutting at
    the hyphen-minus alone (`J.‐P. Dupont`); `_family_words` cutting at
    it alone, the check and the keys both; the keys' joined and whole
    forms of a hyphenated word reading it alone; `_noted` folding one
    side with the lexicon's fold alone (`Dipl.‐Ing. Hans Meier`, which
    no name reached before #1264's review); and `_HYPHEN_CHARS` cut to
    the hyphen-minus (the parse parity, through the trailing titles).
    The keys alone cutting a family word at it is `_RECORDED_CONTROLS`'
    last, which the grids catch; a non-hyphen joining the set is
    test_no_other_character_reads_as_a_hyphen's (the em dash added fails
    it under all four parsers)."""
    p = functools.partial(_hyphen_parse, parser_id)
    partners = [p(x) for x in _HYPHEN_PARTNERS]
    read: set[str] = set()
    for setting in (SETTINGS[0], SETTINGS[-1]):
        matching = Matching(_SHAPE_PARSERS[parser_id], *setting)
        keys = functools.cache(matching.keys)
        check = functools.cache(matching.check)
        for text in _HYPHENATED:
            ascii = p(text)
            for hyphen in _OTHER_HYPHENS:
                written = p(text.replace("-", hyphen))
                read.add(hyphen)
                where = (parser_id, setting, written.original)
                # the parser reads the name as it reads the hyphen-minus
                assert {f: v.replace(hyphen, "-") for f, v in
                        written.as_dict().items()} == ascii.as_dict(), where
                assert keys(written) == keys(ascii), where
                theirs = "\u2010" if hyphen == "\u2013" else "\u2013"
                pairs = [(ascii, ascii), *((x, x) for x in partners),
                         *((p(o.replace("-", theirs)), p(o))
                           for o in _HYPHENATED)]
                for other, other_ascii in pairs:
                    for result, expected in (
                            (check(written, other), check(ascii, other_ascii)),
                            (check(other, written), check(other_ascii, ascii))):
                        assert _reads_as(result, expected), (
                            where, other.original)
                        if result.consistent:
                            assert keys(written) & keys(other), (
                                where, other.original)
    # every listed hyphen was read, so the test cannot pass on nothing
    assert _OTHER_HYPHENS and read == set(_OTHER_HYPHENS)


@pytest.mark.parametrize("parser_id", list(_SHAPE_PARSERS))
def test_no_other_character_reads_as_a_hyphen(parser_id: str) -> None:
    """The parse parity above is discriminating: each character of
    `_NOT_HYPHENS` written in the hyphen-minus's place makes some name
    of `_HYPHENATED` read differently, under every parser (the trailing
    titles), so one joining `_HYPHEN_CHARS` fails here (#1264)."""
    p = functools.partial(_hyphen_parse, parser_id)
    for dash in _NOT_HYPHENS:
        assert any(
            {f: v.replace(dash, "-") for f, v in
             p(text.replace("-", dash)).as_dict().items()} != p(text).as_dict()
            for text in _HYPHENATED), (parser_id, dash)


#: Names the PARSER reads differently with another hyphen in the
#: hyphen-minus's place, under every parser of `_SHAPE_PARSERS`, at the
#: merge base of #1264 too: credentials and a generation joined by one,
#: a trailing title the vocabulary lists with the hyphen-minus, and a
#: spaced one between credentials, each with the hyphen-minus reading
#: and the one the other hyphens give. The match reads the fields the
#: parse gives, so these pairs stay apart; a parser fix moves a row,
#: which then belongs in `_HYPHENATED`. (#1264's review, 2026-11-11.)
_PARSER_HYPHEN_LIMITS: tuple[tuple[str, str], ...] = (
    ("John Smith MD-PhD", "suffix"), ("John Smith, NP-C", "suffix"),
    ("John Smith, OTR-L", "suffix"), ("John Smith Jr.-III", "suffix"),
    ("John Smith, M.D.-Ph.D.", "suffix"), ("Hans Meier Priv.-Doz.", "title"),
)
#: Of those, the ones the family-first order reads consistent with the
#: hyphen-minus spelling: the moved word lands in the middle name there
#: and reads one-sided; after a comma it lands in the given name.
_LIMITS_CONSISTENT_FAMILY_FIRST = frozenset({
    "John Smith MD-PhD", "John Smith Jr.-III", "Hans Meier Priv.-Doz."})


@pytest.mark.parametrize("text, role_name", _PARSER_HYPHEN_LIMITS)
@pytest.mark.parametrize("parser_id", list(_SHAPE_PARSERS))
def test_the_parser_reads_a_joined_credential_by_its_hyphen(
        parser_id: str, text: str, role_name: str) -> None:
    # the hyphen-minus spelling reads the last word in `role_name`; each
    # other hyphen moves it out into a name field, where the pair
    # conflicts, save the family-first readings that land it in the
    # middle name (`_LIMITS_CONSISTENT_FAMILY_FIRST`)
    p = functools.partial(_hyphen_parse, parser_id)
    word = text.split()[-1]
    assert getattr(p(text), role_name) == word
    matching = Matching(_SHAPE_PARSERS[parser_id])
    for hyphen in _OTHER_HYPHENS:
        written = p(text.replace("-", hyphen))
        assert getattr(written, role_name) == "", (parser_id, written.original)
        assert matching.check(written, p(text)).consistent is (
            parser_id == "family-first"
            and text in _LIMITS_CONSISTENT_FAMILY_FIRST)


def test_a_spaced_hyphen_between_credentials_is_read_by_its_character() -> None:
    # the hyphen-minus spaced between credentials divides them, another
    # hyphen spaced so is a word the suffix keeps (parser, #1264's review)
    assert parse("John Smith, MD - PhD").suffix == "MD, PhD"
    assert parse("John Smith, MD \u2010 PhD").suffix == "MD \u2010 PhD"


# -- the maiden name sets its particles aside as the family name does (#1264) -

@pytest.mark.parametrize("a, b, outcome", [
    ("Ana Ruiz (née de la Vega)", "Ana Ruiz (née Vega)",
     Outcome.PARTICLES_ASIDE),
    ("Ana Ruiz (geb. von Berg)", "Ana Ruiz (geb. Berg)",
     Outcome.PARTICLES_ASIDE),
    ("Ana Ruiz (née de la Vega Gómez)", "Ana Ruiz (née Vega)",
     Outcome.PART_OF_OTHER),
    # a hyphen half, any hyphen, and a hyphen half that is a particle
    ("Ana Ruiz (née Vega-Gómez)", "Ana Ruiz (née Vega)",
     Outcome.PART_OF_OTHER),
    ("Ana Ruiz (née Vega‐Gómez)", "Ana Ruiz (née Vega)",
     Outcome.PART_OF_OTHER),
    ("Ana Ruiz (née Al-Vega)", "Ana Ruiz (née Vega)", Outcome.PART_OF_OTHER),
    ("山田 花子 (旧姓 田中 中)", "山田 花子 (旧姓 田中)", Outcome.PART_OF_OTHER),
    # the outcomes it read before stay
    ("Ana Ruiz (née DelaVega)", "Ana Ruiz (née de la Vega)", Outcome.JOINED),
    ("Ana Ruiz (née VEGA)", "Ana Ruiz (née Vega)", Outcome.FOLDED),
    ("Ana Ruiz (née Vega–Gómez)", "Ana Ruiz (née Vega-Gómez)",
     Outcome.FOLDED),
    # an initial against it reads `initial`, never the opt-in
    # `family-initial` the family chain would give it
    ("Ana Ruiz (née V.)", "Ana Ruiz (née Vega)", Outcome.INITIAL),
    ("Ana Ruiz (née Vega)", "Ana Ruiz", Outcome.ONE_SIDE),
    # particles alone: a maiden particle carries no unjoined tag, so
    # both bases are empty and neither leniency holds, where the family
    # name keeps them (test_where_the_maiden_name_departs_from_the_family)
    ("Ana Ruiz (née de la)", "Ana Ruiz (née de)", Outcome.CONFLICT),
    ("Ana Ruiz (née V.)", "Ana Ruiz (née de la Vega)", Outcome.CONFLICT),
    # two texts of initials alone are initials-agree's to read, as they
    # are joined's exception, so they read as before (part-of-other
    # would cover each by the other)
    ("Ana Ruiz (née J.-P.)", "Ana Ruiz (née J. P.)", Outcome.INITIALS_AGREE),
    ("Ana Ruiz (née J. P.)", "Ana Ruiz (née P. J.)", Outcome.CONFLICT),
    ("Ana Ruiz (née J.)", "Ana Ruiz (née J. P.)", Outcome.CONFLICT),
    # a maiden marker with no name after it is the nickname, as parsed
    ("Ana Ruiz (née)", "Ana Ruiz (née Vega)", Outcome.ONE_SIDE),
])
def test_a_maiden_name_reads_the_family_names_leniencies(
        a: str, b: str, outcome: Outcome) -> None:
    # Negative control (2026-11-11): the maiden row given its comparator
    # at the merge base back (`_compare_text`) fails the seven rows
    # reading particles-aside and part-of-other here, both rows of
    # test_a_maiden_name_on_both_sides_is_compared_as_a_surname,
    # test_a_listed_spelling_counts_inside_a_compound_maiden_name and the
    # hyphen-half row of
    # test_a_maiden_outcome_accepted_at_the_merge_base_stays_accepted;
    # the initials exception removed fails the three initials rows here
    for x, y in ((a, b), (b, a)):
        r = m.check(x, y)
        assert r["maiden"].outcome is outcome, (x, y)
        assert r.consistent is (outcome is not Outcome.CONFLICT), (x, y)


def test_a_listed_spelling_counts_inside_a_compound_maiden_name() -> None:
    # as in a compound family name (#1262), in the family group (#1264)
    matching = Matching(Parser(lexicon=_SMYTH_LEXICON))
    r = matching.check("Ann Doe (née Smyth-Jones)", "Ann Doe (née Smith)")
    assert r["maiden"].outcome is Outcome.PART_OF_OTHER and r.consistent
    r = matching.check("Ann Doe (née de Smyth)", "Ann Doe (née Smith)")
    assert r["maiden"].outcome is Outcome.PARTICLES_ASIDE and r.consistent


_NO_PART_OF_OTHER = ((DEFAULT_ACCEPT - {Outcome.PART_OF_OTHER})
                     | {Outcome.HYPHENATED_PART})


@pytest.mark.parametrize("a, b, accept", [
    ("Ana Ruiz (née Vega-Gómez)", "Ana Ruiz (née Vega)", _NO_PART_OF_OTHER),
    ("Ana Ruiz (née V.)", "Ana Ruiz (née Vega)", _NO_PART_OF_OTHER),
    ("Ana Ruiz (née V.)", "Ana Ruiz (née Vega)",
     DEFAULT_ACCEPT | {Outcome.FAMILY_INITIAL}),
])
def test_a_maiden_outcome_accepted_at_the_merge_base_stays_accepted(
        a: str, b: str, accept: frozenset[Outcome]) -> None:
    # outside the family chain (#1264): each pair is consistent under
    # its setting with the merge base's `_match.py` too, a caller who
    # accepts hyphenated-part but not part-of-other still reading the
    # hyphen half, and the initial still reading `initial`
    matching = Matching(Parser(), accept)
    assert matching.check(a, b).consistent
    assert matching.check(b, a).consistent


def test_where_the_maiden_name_departs_from_the_family() -> None:
    # two departures from the family comparison, each recorded in
    # decisions/name-matching's #1264 entry: particles alone (no
    # unjoined tag on a maiden particle, so its base is empty; new with
    # the maiden bases, a conflict before as now) and a hyphen half
    # that is a particle (read as `hyphenated-part` outside the chain,
    # at the merge base too)
    assert m.check("de la, Ana", "de, Ana")["family"].outcome \
        is Outcome.PART_OF_OTHER
    assert m.check("Ana Ruiz (née de la)", "Ana Ruiz (née de)")["maiden"] \
        .outcome is Outcome.CONFLICT
    hyphenated = Matching(Parser(), DEFAULT_ACCEPT | {Outcome.HYPHENATED_PART})
    assert not hyphenated.check("al-Rashid, Ana", "al, Ana").consistent
    r = hyphenated.check("Ana Ruiz (née al-Rashid)", "Ana Ruiz (née al)")
    assert r["maiden"].outcome is Outcome.HYPHENATED_PART and r.consistent


def test_a_maiden_name_against_the_family_still_counts_full_names_only() -> None:
    # across-roles compares a family name with the other's maiden name
    # by full names alone (`_full_outcome`), so particles are not set
    # aside across the two roles, as at the merge base (#1264)
    across = Matching(Parser(), DEFAULT_ACCEPT | {Outcome.ACROSS_ROLES})
    for a, b in (("Ana Vega", "Ana Ruiz (née de la Vega)"),
                 ("Ana de la Vega", "Ana Ruiz (née Vega)")):
        assert not across.check(a, b).consistent
        assert not across.check(b, a).consistent


@pytest.mark.parametrize("name", [
    "Ana Ruiz (née de la Vega)", "Ana Ruiz (née Vega)",
    "Ana Ruiz (née de la Vega Gómez)", "Ana Ruiz (née Vega-Gómez)",
    "山田 花子 (旧姓 田中)",
])
def test_the_default_keys_hold_no_maiden_word(name: str) -> None:
    # the maiden leniencies need no key: a consistent pair's family
    # names agree, and they are keyed (#1264)
    without = name.split(" (")[0]
    assert m.keys(name) == m.keys(without)


# -- Muhammad written short (#1383) -------------------------------------------

#: The short forms of Muhammad against its long spellings and each other:
#: each short form lists the long spellings written where it is, so the
#: pairs ORCID's holders wrote both ways (`Mohd` / `Mohammad`) read
#: `listed-spelling` by default, as `Wm` / `William` does.
_MUHAMMAD: tuple[tuple[str, str, Outcome], ...] = (
    ("Mohd Rahman", "Mohammad Rahman", Outcome.LISTED_SPELLING),
    ("Mohd Rahman", "Muhammad Rahman", Outcome.LISTED_SPELLING),
    ("Mohd Rahman", "Mohammed Rahman", Outcome.LISTED_SPELLING),
    ("Mohd Rahman", "Mohamed Rahman", Outcome.LISTED_SPELLING),
    ("Mohd Rahman", "Mohamad Rahman", Outcome.LISTED_SPELLING),
    ("Moh. Rahman", "Mohammad Rahman", Outcome.LISTED_SPELLING),
    ("Moh. Rahman", "Mohamad Rahman", Outcome.LISTED_SPELLING),
    ("Md Rahman", "Mohammad Rahman", Outcome.LISTED_SPELLING),
    ("Md. Rahman", "Muhammad Rahman", Outcome.LISTED_SPELLING),
    ("MD RAHMAN", "MOHAMMED RAHMAN", Outcome.LISTED_SPELLING),
    ("Md Rahman", "Mohamed Rahman", Outcome.LISTED_SPELLING),
    # two short forms meet through the long spellings they share
    ("Md Rahman", "Mohd Rahman", Outcome.LISTED_SPELLING),
    ("Moh Rahman", "Md. Rahman", Outcome.LISTED_SPELLING),
    # `md` lists no `mohamad`, which Bangladesh's holders do not write;
    # the pair reads as the opt-in spelling it is through `mohamed`
    ("Md Rahman", "Mohamad Rahman", Outcome.ALTERNATE_SPELLING),
    # `muhammed` (Turkish) is listed by none
    ("Mohd Rahman", "Muhammed Rahman", Outcome.CONFLICT),
    ("Md Rahman", "Muhammed Rahman", Outcome.CONFLICT),
)


@pytest.mark.parametrize("a, b, outcome", _MUHAMMAD)
def test_muhammad_written_short_matches_its_long_spellings(
        a: str, b: str, outcome: Outcome) -> None:
    # Negative control (2026-11-13): on master 3dadc263 every
    # `listed-spelling` row with Md is a conflict (no given reading), or
    # `given-one-side` where `Md.` read as a title, and
    # Mohd or Moh against Mohammad, Mohammed or Mohamed reads
    # `alternate-spelling`, refused by default
    for x, y in ((a, b), (b, a)):
        r = m.check(x, y)
        assert r["given"].outcome is outcome, (x, y)
        assert r.consistent is (outcome in m.accept), (x, y)
        assert m.keys(x) & m.keys(y), (x, y)


def test_muhammad_written_short_is_not_transitive_across_long_spellings() -> None:
    # Accepted (decisions/name-matching, 2026-11-13 #1383): two long
    # spellings are each consistent with a short form that lists both,
    # and not with each other by default, that pair being an opt-in
    # alternate spelling
    assert m.check("Mohammad Rahman", "Md Rahman").consistent
    assert m.check("Md Rahman", "Muhammad Rahman").consistent
    r = m.check("Mohammad Rahman", "Muhammad Rahman")
    assert not r.consistent
    assert r["given"].outcome is Outcome.ALTERNATE_SPELLING


def test_muhammad_written_short_keys_by_its_letter() -> None:
    # the keys are the default's, the long spellings sharing the letter
    for name in ("Md Rahman", "Md. Rahman", "Mohd Rahman", "Moh Rahman",
                 "Mohammad Rahman", "Muhammad Rahman"):
        assert m.keys(name) == {"rahman;m"}, name
