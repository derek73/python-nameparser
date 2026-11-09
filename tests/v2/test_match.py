"""Name matching: the settings object, the result types, the check
and the grouping keys, with the symmetry and key-guarantee properties
held over one shared parsed grid (NAMES)."""
from __future__ import annotations

import itertools
import pickle
import unicodedata

import pytest

import nameparser
from nameparser import Lexicon, ParsedName, Parser, Role, parse
from nameparser._match import (
    DEFAULT_ACCEPT,
    CrossRoleMatch,
    Matching,
    MatchResult,
    Outcome,
    RoleMatch,
    Side,
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
)

#: NAMES parsed once by the default parser, for the grid tests, so a
#: pair's check under each setting re-parses nothing.
PARSED: tuple[ParsedName, ...] = tuple(Parser().parse(n) for n in NAMES)

#: The opt-in outcomes this module's settings sweep adds to the default.
OPT_INS: tuple[Outcome, ...] = (
    Outcome.FAMILIAR_FORM, Outcome.FAMILY_INITIAL, Outcome.GIVEN_ONE_SIDE,
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


def test_fold_drops_case_accents_and_periods_but_keeps_hyphens() -> None:
    assert _fold("J.-P. O'Mári\u0301a") == "j-p omaria"
    assert _fold("María") == _fold("Mari\u0301a") == "maria"


def test_fold_is_idempotent_and_keeps_hyphens_over_every_code_point() -> None:
    # The key guarantee rests on these two: keys fold a spelling set's
    # members again, and a family word's hyphen halves are cut from the
    # raw word by position (_spelling_keys, _family_words). Every
    # assigned code point is folded alone, after a letter, beside a
    # hyphen on either side, and with a combining mark after it behind a
    # Latin letter, a hyphen and a Devanagari letter (an unassigned one
    # has no decomposition, case or mark to fold). The mark contexts
    # found the micro sign U+00B5 and U+2183, which casefold into Greek
    # and Latin, and a full stop or apostrophe before a mark (review of
    # #1221). Measured 2026-11-08: about 6 s serial on py3.11, the module's
    # heaviest test.
    bad = []
    for i in range(0x110000):
        c = chr(i)
        if unicodedata.category(c) in ("Cn", "Cs"):
            continue
        for text in (c, "a" + c, c + "-a", "-" + c, c + " x",
                     "a" + c + "\u0301", "-" + c + "\u0301",
                     "\u0915" + c + "\u0301"):
            folded = _fold(text)
            if (_fold(folded) != folded or folded.count("-") != text.count("-")
                    or folded.count(" ") != text.count(" ")):
                bad.append((hex(i), text, folded))
    assert bad == []


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
    assert m.keys("Jane A. de la Vega") == {"vega;j"}
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
    accepts. Negative controls, each the first pair to fail, re-taken
    2026-11-08 after the familiar forms' names ("Max Smith" through
    "Maria Ivanova") joined NAMES, familiar-form joined the settings and
    a familiar-form pair came to be read and keyed either way round,
    each mutation applied in-process, every pair unmoved since the
    period rule's names ("Jo. Garcia" through "Ana Mà. Cruz" written
    decomposed) and before them "Ahmed Al", "Ahmed Al-Saud" and "Ahmed
    Saud" joined it, and the symmetry test passing under every one:
    with only the joined form of a hyphenated word keyed, the default,
    familiar-form, given-one-side, hyphenated-part, other-reading and
    across-roles fail on ("Ann Smith-Jones", "Ann Smith"), and
    family-initial and all-opt-ins on ("Ahmed Al-Saud", "Ahmed Saud");
    with part-of-other keeping a hyphen half that is a particle while
    the keys drop it, the default, familiar-form, given-one-side,
    hyphenated-part, other-reading and across-roles fail on ("Ahmed
    Al", "Ahmed Al-Saud"), family-initial and all-opt-ins passing it
    through the family-initial key; with the familiar forms' longer
    names left out of the given letters, familiar-form fails on ("Wm.
    Smith", "Bill Smith"), a listed spelling of the longer name, and
    all-opt-ins passes it through given-one-side's bare family keys;
    with the family-initial key
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
    hyphenated-part adds no key, its halves sharing the given initial.
    Two keys no pair of NAMES needs, each failing a named test when
    removed (re-taken the same day): the whole hyphenated word's
    spellings (test_a_hyphenated_listed_spelling_shares_a_key, under a
    caller's hyphenated full form, and the two key-content tests of
    hyphenated family words) and the spellings read from the folded
    word (test_a_listed_spelling_holds_whatever_the_accents, "Ana Mà.
    Cruz"). The period rule moves no pair here: with the period test
    removed from `_spellings`, the bare word's links restored, this
    test and the symmetry test pass under every setting, since the
    check and the keys read the one spelling set, while
    test_a_name_of_its_own_written_bare_is_itself (four rows) and
    test_a_bare_name_of_its_own_is_not_keyed_by_its_long_form fail.
    Other-reading names the setting with `other_readings=True`, which
    was the `other-reading` member of accept when these were taken."""
    matching = Matching(Parser(), *setting)
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
    assert _across.keys("Jane Doe (née Smith)") == {"doe;j", "smith;j"}
    assert m.keys("Jane Doe (née Smith)") == {"doe;j"}


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


@pytest.mark.parametrize("apostrophe", ["\u2019", "\u02bc"])
def test_a_typographic_apostrophe_folds_like_a_typed_one(apostrophe: str) -> None:
    written = f"O{apostrophe}Brien, Pat"
    assert _fold(f"O{apostrophe}Brien") == _fold("O'Brien") == "obrien"
    r = m.check(written, "Pat O'Brien")
    assert r.consistent and role(r, Role.FAMILY).outcome is Outcome.FOLDED
    assert m.keys(written) == m.keys("Pat O'Brien") == {"obrien;p"}


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


@pytest.mark.parametrize("a, b", [
    ("Jo Garcia", "José Garcia"), ("Jo Garcia", "Jose Garcia"),
    ("Jo Garcia", "Joanne Garcia"), ("Ma Santos", "María Santos"),
    ("Jas Singh", "James Singh"), ("JAS SINGH", "JAMES SINGH"),
    ("Garcia, Jo", "Garcia, José"),
])
def test_a_name_of_its_own_written_bare_is_itself(a: str, b: str) -> None:
    # `jo`, `ma` and `jas` are given names of their own as well as
    # spellings of José, María and James, so written without the period
    # each is the name, and conflicts with the long form
    for x, y in ((a, b), (b, a)):
        r = m.check(x, y)
        assert not r.consistent and r["given"].outcome is Outcome.CONFLICT


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
    assert Outcome.ACROSS_ROLES.strength == 1


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
    ("Sepp Huber", "Josef Huber", "huber;j"),
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
    # nam_dict writes some pairs long first (`Maria` / `Masha`), so a
    # pair is read either way: written either way round here, on a
    # lexicon holding no other familiar reading, it matches and keys alike
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
    assert _familiar.check("Masha Ivanova", "Maria Ivanova").consistent


@pytest.mark.parametrize("a, b", [
    # never chained: each is paired with Max alone, not with each other
    ("Maximilian Smith", "Maxim Smith"),
    # a pair nam_dict does not list
    ("Max Smith", "Maxwell Smith"),
    ("Peggy Smith", "Margaret Smith"),
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
    assert all(o.strength > Outcome.FAMILIAR_FORM.strength
               for o in DEFAULT_ACCEPT)
    assert all(o.strength < Outcome.FAMILIAR_FORM.strength
               for o in OPT_INS if o is not Outcome.FAMILIAR_FORM)


def test_a_callers_familiar_form_is_read_and_keyed() -> None:
    # an add of a kind the word holds updates its properties in every
    # file holding it, so it replaces the longer names, as a same_as is
    # replaced; listing the shipped ones keeps them
    lexicon = Lexicon.default().add("max", kind="familiar",
                                    short_for=["Maxwell"])
    assert lexicon._familiar_forms("Max") == {"maxwell"}
    matching = Matching(Parser(lexicon=lexicon),
                        DEFAULT_ACCEPT | {Outcome.FAMILIAR_FORM})
    assert matching.check("Max Smith", "Maxwell Smith").consistent
    assert not matching.check("Max Smith", "Maximilian Smith").consistent
    assert matching.keys("Max Smith") & matching.keys("Maxwell Smith")
    kept = Lexicon.default().add("max", kind="familiar", short_for=[
        *sorted(Lexicon.default()._familiar_forms("max")), "maxwell"])
    assert kept._familiar_forms("max") == {
        "maksim", "maxim", "maximilian", "maxwell"}
    added = Lexicon.empty().add("zzq", kind="familiar", short_for=["zzr"])
    assert added._familiar_forms("zzq") == {"zzr"}
    assert added.words(kind="familiar") == ("zzq",)
    with pytest.raises(TypeError, match="short_for must be an iterable"):
        Lexicon.default().add("max", kind="familiar", short_for="maxwell")
    with pytest.raises(ValueError, match="single given names"):
        Lexicon.default().add("max", kind="familiar", short_for=["max well"])


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
    # a strict one keeps its own files' alone
    plain = Lexicon(_base="default", _languages={"de"})
    strict = Lexicon(_base="default", _languages={"de"}, _strict=True)
    assert plain._familiar == Lexicon.default()._familiar
    assert plain._familiar_forms("max") == {"maksim", "maxim", "maximilian"}
    assert strict._familiar_forms("max") == {"maximilian"}
    assert not strict._familiar_forms("bill")


@pytest.mark.parametrize("a, b", [
    # an accented pair (hu `józsi` of `józsef`) in each of its four
    # spellings: as written, the short name folded, the long name
    # folded, both folded
    ("Józsi Kovács", "József Kovács"), ("Jozsi Kovacs", "József Kovács"),
    ("Józsi Kovács", "Jozsef Kovacs"), ("Jozsi Kovacs", "Jozsef Kovacs"),
    ("Klára Nagy", "Klári Nagy"), ("Klara Nagy", "Klári Nagy"),
    ("Klára Nagy", "Klari Nagy"), ("Klara Nagy", "Klari Nagy"),
    ("Mari Kovács", "Mária Kovács"), ("Mari Kovács", "Maria Kovács"),
])
def test_a_familiar_form_holds_whatever_the_accents(a: str, b: str) -> None:
    for x, y in ((a, b), (b, a)):
        r = _familiar.check(x, y)
        assert r.consistent and role(r, Role.GIVEN).outcome is Outcome.FAMILIAR_FORM
        assert _familiar.keys(x) & _familiar.keys(y)


#: The shipped pairs whose short name reads as a title in front of a
#: name, so the pair is never compared as two given names: a pair is
#: inert while its short form reads as a title.
_TITLE_SHORT_FORMS = {("nanny", "nannette"), ("timi", "tímea")}


def test_every_shipped_pair_is_consistent_in_every_spelling() -> None:
    # every FAMILIAR pair, each name as written and folded, as given
    # names before one family name: consistent under the opt-in, with
    # a shared key; the pairs whose short name parses as a title are
    # the ones listed, and none else is skipped
    from nameparser.config._compiled import FAMILIAR
    parser = _familiar.parser
    skipped = set()
    for short, longs in FAMILIAR.items():
        for long in longs:
            for a in dict.fromkeys((short, _fold(short))):
                for b in dict.fromkeys((long, _fold(long))):
                    x = parser.parse(f"{a.capitalize()} Kovacs")
                    y = parser.parse(f"{b.capitalize()} Kovacs")
                    if (x.given.casefold(), y.given.casefold()) != (a, b):
                        skipped.add((short, long))
                        continue
                    assert _familiar.check(x, y).consistent, (a, b)
                    assert _familiar.keys(x) & _familiar.keys(y), (a, b)
    assert skipped == _TITLE_SHORT_FORMS


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
