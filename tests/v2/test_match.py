"""Name matching: the settings object and the result types."""
from __future__ import annotations

import itertools
import pickle

import pytest

import nameparser
from nameparser import ParsedName, Parser, Role
from nameparser._match import (
    DEFAULT_ACCEPT,
    CrossRoleMatch,
    Matching,
    MatchResult,
    Outcome,
    RoleMatch,
    Side,
    _fold,
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
)

#: NAMES parsed once by the default parser, for the grid tests, so a
#: pair's check under each setting re-parses nothing.
PARSED: tuple[ParsedName, ...] = tuple(Parser().parse(n) for n in NAMES)

#: The opt-in outcomes this module's settings sweep adds to the default.
OPT_INS: tuple[Outcome, ...] = (
    Outcome.FAMILY_INITIAL, Outcome.GIVEN_ONE_SIDE,
    Outcome.HYPHENATED_PART, Outcome.OTHER_READING, Outcome.ACROSS_ROLES,
)

#: The settings the guarantee and the symmetry are held under: the
#: default, each opt-in added to it alone, and all of them together.
SETTINGS: tuple[frozenset[Outcome], ...] = (
    DEFAULT_ACCEPT,
    *(DEFAULT_ACCEPT | {o} for o in OPT_INS),
    DEFAULT_ACCEPT | set(OPT_INS),
)
_SETTING_IDS = ["default", *(o.value for o in OPT_INS), "all"]

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
        Outcome.SAME, Outcome.FOLDED, Outcome.LISTED_SPELLING,
        Outcome.PARTICLES_ASIDE, Outcome.PART_OF_OTHER, Outcome.INITIAL,
        Outcome.INITIALS_AGREE, Outcome.ONE_SIDE,
        Outcome.GENERATION_ONE_SIDE, Outcome.NOTED,
    }
    assert Matching(Parser()).accept == DEFAULT_ACCEPT


def test_outcomes_are_declared_strongest_first() -> None:
    names = [o.value for o in Outcome]
    assert names[0] == "same" and names[-1] == "conflict"
    assert len(names) == 16


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
    both = RoleMatch(Role.GIVEN, Outcome.SAME, "a", "a", Side.NEITHER)
    assert both.__class__ is RoleMatch
    result = MatchResult(True, (both,))
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


def test_fold_drops_case_accents_and_periods_but_keeps_hyphens() -> None:
    assert _fold("J.-P. O'Mári\u0301a") == "j-p omaria"
    assert _fold("María") == _fold("Mari\u0301a") == "maria"


def test_the_table_has_one_entry_per_role_in_role_order() -> None:
    assert [x.role for x in m.check("John Smith", "John Smith").roles] == list(Role)


def test_check_takes_a_parsed_name() -> None:
    from nameparser import parse
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


@pytest.mark.parametrize("accept", SETTINGS, ids=_SETTING_IDS)
def test_the_check_is_symmetric(accept: frozenset[Outcome]) -> None:
    matching = Matching(Parser(), accept)
    for a, b in itertools.product(PARSED, repeat=2):
        assert matching.check(b, a) == matching.check(a, b).mirrored(), (
            a.original, b.original)


def test_a_single_han_character_is_never_an_initial() -> None:
    from nameparser import parse
    base = parse("John Smith")
    r = m.check(base.replace(given="小"), base.replace(given="小明"))
    assert role(r, Role.GIVEN).outcome is Outcome.CONFLICT


def test_initials_written_apart_agree_with_the_same_initials_joined() -> None:
    from nameparser import parse
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
    assert m.keys("Jane A. de la Vega") == {"vega;j"}
    assert m.keys("Ann Smith-Jones") == {"smith;a", "jones;a", "smithjones;a"}
    assert m.keys("Suharto") == frozenset()


@pytest.mark.parametrize("accept", SETTINGS, ids=_SETTING_IDS)
def test_consistent_names_always_share_a_key(accept: frozenset[Outcome]) -> None:
    """The guarantee, over every ordered pair of NAMES, under the default,
    each opt-in added to it alone and all of them together: a consistent
    pair shares a key, so grouping by key never separates names `check`
    accepts. Negative controls, each the first pair to fail, re-taken
    2026-11-08 after "Ahmed Al", "Ahmed Al-Saud" and "Ahmed Saud" joined
    NAMES: with only the joined form of a hyphenated word keyed, the
    default, given-one-side, hyphenated-part, other-reading and
    across-roles fail on ("Ann Smith-Jones", "Ann Smith"), and
    family-initial and all-opt-ins on ("Ahmed Al-Saud", "Ahmed Saud");
    with part-of-other keeping a hyphen half that is a particle while
    the keys drop it, the default, given-one-side, hyphenated-part,
    other-reading and across-roles fail on ("Ahmed Al", "Ahmed
    Al-Saud"), family-initial and all-opt-ins passing it through the
    family-initial key; with the family-initial key
    removed, family-initial fails on ("J. Smith", "Jane S") and
    all-opt-ins on ("John A. Smith", "Mr. S"); with the bare family keys
    removed, given-one-side and all-opt-ins fail on ("John A. Smith",
    "Mr. Smith"); with the alternative readings' keys removed,
    other-reading fails on ("Mr. Smith", "Della Smith") and all-opt-ins
    on ("Cristiane S", "Suharto"); with the middle words' initials
    removed, across-roles fails on ("Wm. Smith", "John Wm. Smith"), and
    with the nickname's on ('William "Bill" Clinton', "Bill Clinton"),
    the all-opt-ins setting passing both through given-one-side's bare
    family keys; with the maiden name's words removed, across-roles and
    all-opt-ins both fail on ("J. Smith", "Jane Doe (née Smith)").
    hyphenated-part adds no key, its halves sharing the given initial."""
    matching = Matching(Parser(), accept)
    for a, b in itertools.product(PARSED, repeat=2):
        if matching.check(a, b).consistent:
            assert matching.keys(a) & matching.keys(b), (a.original, b.original)


@pytest.mark.parametrize("a, b", [
    ("Ana dos Santos", "Ana Dos"), ("Jan van der Berg", "Jan Van"),
    ("Maria da Silva", "Maria Da"), ("John bin Laden", "John Bin"),
])
def test_a_family_of_particles_alone_is_not_part_of_a_longer_one(
        a: str, b: str) -> None:
    assert not m.check(a, b).consistent
    assert not m.check(b, a).consistent


def test_a_hyphen_half_that_is_a_particle_is_not_a_family_word() -> None:
    assert m.keys("Ahmed Al-Saud") == {"saud;a", "alsaud;a"}
    r = m.check("Ahmed Al", "Ahmed Al-Saud")
    assert not r.consistent and role(r, Role.FAMILY).outcome is Outcome.CONFLICT
    r = m.check("Ahmed Al-Saud", "Ahmed Saud")
    assert r.consistent and role(r, Role.FAMILY).outcome is Outcome.PART_OF_OTHER
    assert m.keys("Ahmed Al-Saud") & m.keys("Ahmed Saud")
    r = m.check("Ann Smith-Jones", "Ann Smith")
    assert r.consistent and role(r, Role.FAMILY).outcome is Outcome.PART_OF_OTHER


@pytest.mark.parametrize("a, b", [
    ("Ana Jo", "Ana José"), ("Ana Ma", "Ana María"), ("Maria Mà", "Maria Ma"),
])
def test_listed_and_folded_spellings_share_a_key(a: str, b: str) -> None:
    assert m.check(a, b).consistent
    assert m.keys(a) & m.keys(b)


def _with(*outcomes: Outcome) -> Matching:
    return Matching(Parser(), DEFAULT_ACCEPT | set(outcomes))


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
    opted = _with(Outcome.OTHER_READING)
    r = opted.check("Suharto", "Suharto")
    assert r.consistent
    assert role(r, Role.FAMILY).outcome is Outcome.OTHER_READING
    assert role(r, Role.GIVEN).outcome is Outcome.OTHER_READING
    assert (role(r, Role.FAMILY).left, role(r, Role.FAMILY).right) == ("Suharto", "Suharto")
    assert "suharto;" in opted.keys("Suharto")
    assert m.keys("Suharto") == frozenset()


def test_the_other_reading_does_not_hide_a_conflict() -> None:
    r = _with(Outcome.OTHER_READING).check("Suharto", "Sukarno")
    assert not r.consistent
    assert role(r, Role.FAMILY).outcome is Outcome.CONFLICT


def test_the_other_reading_of_one_side_meets_the_other_as_parsed() -> None:
    # "Van Gogh" read with Van as a particle has the family "Van Gogh"
    # and no given name, so the given role also needs given-one-side
    r = _with(Outcome.OTHER_READING).check("Van Gogh", "Vincent Van Gogh")
    assert not r.consistent
    assert role(r, Role.GIVEN).outcome is Outcome.GIVEN_ONE_SIDE
    assert role(r, Role.FAMILY).outcome is Outcome.OTHER_READING
    r = _with(Outcome.OTHER_READING, Outcome.GIVEN_ONE_SIDE).check(
        "Van Gogh", "Vincent Van Gogh")
    assert r.consistent and role(r, Role.GIVEN).outcome is Outcome.OTHER_READING
    assert (role(r, Role.FAMILY).left, role(r, Role.FAMILY).right) == (
        "Van Gogh", "Van Gogh")


def test_the_default_reports_the_names_as_parsed() -> None:
    # no alternative reading is searched unless other-reading is accepted
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
    opted = _with(Outcome.OTHER_READING)
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


@pytest.mark.parametrize("a, b, conflicting", [
    ("J. Edgar Hoover", "Edgar Hoover", Role.GIVEN),
    ('William "Bill" Clinton', "Bill Clinton", Role.GIVEN),
    ("Jane Doe (née Smith)", "Jane Smith", Role.FAMILY),
])
def test_the_default_reports_cross_role_pairs_as_parsed(
        a: str, b: str, conflicting: Role) -> None:
    # no cross-role search runs unless across-roles is accepted
    for x, y in ((a, b), (b, a)):
        r = m.check(x, y)
        assert not r.consistent and r.across == ()
        assert role(r, conflicting).outcome is Outcome.CONFLICT


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
    assert _across.keys("Jane Doe (née Smith)") == {"doe;j", "smith;j"}
    assert m.keys("Jane Doe (née Smith)") == {"doe;j"}


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
