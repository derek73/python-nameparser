"""Name matching: the settings object and the result types."""
from __future__ import annotations

import itertools
import pickle

import pytest

from nameparser import Parser, Role
from nameparser._match import (
    DEFAULT_ACCEPT,
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
)

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
    for obj in (matching, _result(), _result().roles[0]):
        assert pickle.loads(pickle.dumps(obj)) == obj


def test_mirrored_swaps_text_and_sides() -> None:
    mirrored = _result().mirrored()
    assert mirrored.consistent
    first = mirrored.roles[0]
    assert (first.left, first.right, first.more) == ("John", "J.", Side.LEFT)
    assert [m.role for m in mirrored.roles] == list(Role)
    assert mirrored.mirrored() == _result()


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


def test_the_check_is_symmetric() -> None:
    for a, b in itertools.product(NAMES, repeat=2):
        assert m.check(b, a) == m.check(a, b).mirrored(), (a, b)


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


def test_consistent_names_always_share_a_key() -> None:
    """The guarantee, over every ordered pair of NAMES: under the default
    settings a consistent pair shares a key, so grouping by key never
    separates names `check` accepts. Negative control: with the hyphen
    halves removed from `keys`, this fails on ("Ann Smith-Jones",
    "Ann Smith")."""
    for a, b in itertools.product(NAMES, repeat=2):
        if m.check(a, b).consistent:
            assert m.keys(a) & m.keys(b), (a, b)


@pytest.mark.parametrize("a, b", [
    ("Ana dos Santos", "Ana Dos"), ("Jan van der Berg", "Jan Van"),
    ("Maria da Silva", "Maria Da"), ("John bin Laden", "John Bin"),
])
def test_a_family_of_particles_alone_is_not_part_of_a_longer_one(
        a: str, b: str) -> None:
    assert not m.check(a, b).consistent
    assert not m.check(b, a).consistent


@pytest.mark.parametrize("a, b", [
    ("Ana Jo", "Ana José"), ("Ana Ma", "Ana María"), ("Maria Mà", "Maria Ma"),
])
def test_listed_and_folded_spellings_share_a_key(a: str, b: str) -> None:
    assert m.check(a, b).consistent
    assert m.keys(a) & m.keys(b)
