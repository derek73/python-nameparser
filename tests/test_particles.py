import pytest

from nameparser import Lexicon, PatronymicRule, Parser, Policy, parse
from nameparser.config.particles import NON_GIVEN_NAME_PARTICLES
from nameparser.config.titles import TITLES

from tests.base import ParsedNameTestBase


class ParticlesTestCase(ParsedNameTestBase):

    def test_prefix(self) -> None:
        hn = parse("Juan del Sur")
        self.m(hn.given, "Juan", hn)
        self.m(hn.family, "del Sur", hn)

    def test_prefix_with_period(self) -> None:
        hn = parse("Jill St. John")
        self.m(hn.given, "Jill", hn)
        self.m(hn.family, "St. John", hn)

    def test_prefix_before_two_part_last_name(self) -> None:
        hn = parse("pennie von bergen wessels")
        self.m(hn.given, "pennie", hn)
        self.m(hn.family, "von bergen wessels", hn)

    def test_prefix_is_first_name(self) -> None:
        hn = parse("Van Johnson")
        self.m(hn.given, "Van", hn)
        self.m(hn.family, "Johnson", hn)

    def test_prefix_is_first_name_with_middle_name(self) -> None:
        hn = parse("Van Jeremy Johnson")
        self.m(hn.given, "Van", hn)
        self.m(hn.middle, "Jeremy", hn)
        self.m(hn.family, "Johnson", hn)

    def test_prefix_before_two_part_last_name_with_suffix(self) -> None:
        hn = parse("pennie von bergen wessels III")
        self.m(hn.given, "pennie", hn)
        self.m(hn.family, "von bergen wessels", hn)
        self.m(hn.suffix, "III", hn)

    def test_prefix_before_two_part_last_name_with_acronym_suffix(self) -> None:
        hn = parse("pennie von bergen wessels M.D.")
        self.m(hn.given, "pennie", hn)
        self.m(hn.family, "von bergen wessels", hn)
        self.m(hn.suffix, "M.D.", hn)

    def test_title_before_and_after_prefixed_last_name(self) -> None:
        # Issue #100: a repeated title/suffix token before AND after a
        # prefixed last name used to corrupt the middle name into
        # " dr Vincent van" because the suffix-boundary lookup matched the
        # LEADING token instead of the trailing one. The token was "dr"
        # until #296's audit took 'dr' out of the suffix vocabulary (it
        # is not a postnominal); "lt" is both a title and a suffix, which
        # is the only property these three tests need.
        hn = parse("lt Vincent van Gogh lt")
        self.m(hn.title, "lt", hn)
        self.m(hn.given, "Vincent", hn)
        self.m(hn.middle, "", hn)
        self.m(hn.family, "van Gogh", hn)
        self.m(hn.suffix, "lt", hn)

    def test_suffix_token_collision_with_two_word_prefix(self) -> None:
        # Same fix as #100 but with a two-word prefix ("van der"). Exercises a
        # different iteration count through the prefix-joining loop.
        hn = parse("lt Vincent van der Gogh lt")
        self.m(hn.title, "lt", hn)
        self.m(hn.given, "Vincent", hn)
        self.m(hn.middle, "", hn)
        self.m(hn.family, "van der Gogh", hn)
        self.m(hn.suffix, "lt", hn)

    def test_title_before_and_after_prefixed_last_name_with_middle(self) -> None:
        # The pre-fix bug corrupted the middle field; verify it is not disturbed
        # when a genuine middle name is present alongside the repeated token.
        hn = parse("lt Vincent James van Gogh lt")
        self.m(hn.title, "lt", hn)
        self.m(hn.given, "Vincent", hn)
        self.m(hn.middle, "James", hn)
        self.m(hn.family, "van Gogh", hn)
        self.m(hn.suffix, "lt", hn)

    @pytest.mark.timeout(2)
    def test_many_repeated_prefixes_does_not_blow_up(self) -> None:
        # Issue #108: a name with a long run of repeated prefixes used to grow
        # the pieces list exponentially and exhaust memory. The 2-second timeout
        # enforces this locally and in CI — if the test hangs, an exponential
        # regression has been reintroduced.
        name = "Jan " + "van der " * 30 + "Berg"
        hn = parse(name)
        self.m(hn.given, "Jan", hn)
        self.assertIn("Berg", hn.family)

    def test_two_part_last_name_with_suffix_comma(self) -> None:
        hn = parse("pennie von bergen wessels, III")
        self.m(hn.given, "pennie", hn)
        self.m(hn.family, "von bergen wessels", hn)
        self.m(hn.suffix, "III", hn)

    def test_two_part_last_name_with_suffix(self) -> None:
        hn = parse("von bergen wessels, pennie III")
        self.m(hn.given, "pennie", hn)
        self.m(hn.family, "von bergen wessels", hn)
        self.m(hn.suffix, "III", hn)

    def test_last_name_two_part_last_name_with_two_suffixes(self) -> None:
        hn = parse("von bergen wessels MD, pennie III")
        self.m(hn.given, "pennie", hn)
        self.m(hn.family, "von bergen wessels", hn)
        self.m(hn.suffix, "MD, III", hn)

    def test_comma_two_part_last_name_with_acronym_suffix(self) -> None:
        hn = parse("von bergen wessels, pennie MD")
        self.m(hn.given, "pennie", hn)
        self.m(hn.family, "von bergen wessels", hn)
        self.m(hn.suffix, "MD", hn)

    def test_comma_two_part_last_name_with_suffix_in_first_part(self) -> None:
        # I'm kinda surprised this works, not really sure if this is a
        # realistic place for a suffix to be.
        hn = parse("von bergen wessels MD, pennie")
        self.m(hn.given, "pennie", hn)
        self.m(hn.family, "von bergen wessels", hn)
        self.m(hn.suffix, "MD", hn)

    def test_title_two_part_last_name_with_suffix_in_first_part(self) -> None:
        hn = parse("pennie von bergen wessels MD, III")
        self.m(hn.given, "pennie", hn)
        self.m(hn.family, "von bergen wessels", hn)
        self.m(hn.suffix, "MD, III", hn)

    def test_portuguese_dos(self) -> None:
        hn = parse("Rafael Sousa dos Anjos")
        self.m(hn.given, "Rafael", hn)
        self.m(hn.middle, "Sousa", hn)
        self.m(hn.family, "dos Anjos", hn)

    def test_portuguese_prefixes(self) -> None:
        hn = parse("Joao da Silva do Amaral de Souza")
        self.m(hn.given, "Joao", hn)
        self.m(hn.middle, "da Silva do Amaral", hn)
        self.m(hn.family, "de Souza", hn)

    def test_three_conjunctions(self) -> None:
        hn = parse("Dr. Juan Q. Xavier de la dos Vega III")
        self.m(hn.given, "Juan", hn)
        self.m(hn.family, "de la dos Vega", hn)
        self.m(hn.title, "Dr.", hn)
        self.m(hn.middle, "Q. Xavier", hn)
        self.m(hn.suffix, "III", hn)

    def test_lastname_three_conjunctions(self) -> None:
        hn = parse("de la dos Vega, Dr. Juan Q. Xavier III")
        self.m(hn.given, "Juan", hn)
        self.m(hn.family, "de la dos Vega", hn)
        self.m(hn.title, "Dr.", hn)
        self.m(hn.middle, "Q. Xavier", hn)
        self.m(hn.suffix, "III", hn)

    def test_comma_three_conjunctions(self) -> None:
        hn = parse("Dr. Juan Q. Xavier de la dos Vega, III")
        self.m(hn.given, "Juan", hn)
        self.m(hn.family, "de la dos Vega", hn)
        self.m(hn.title, "Dr.", hn)
        self.m(hn.middle, "Q. Xavier", hn)
        self.m(hn.suffix, "III", hn)

    # The subset-of-PARTICLES and disjoint-from-BOUND_GIVEN_NAMES invariants
    # hold by construction or by the vocabulary build's checks
    # (tools/vocab/build.py, tests/v2/test_vocab.py), so they are not
    # repeated as tests here.

    def test_non_given_name_particles_expected_members(self) -> None:
        # 'abu' is in PARTICLES but excluded (it is a bound_first_name);
        # 'von'/'van'/'della'/'di'/'del' are excluded (they can be first names).
        self.assertIn('de', NON_GIVEN_NAME_PARTICLES)
        self.assertIn('dos', NON_GIVEN_NAME_PARTICLES)
        self.assertNotIn('abu', NON_GIVEN_NAME_PARTICLES)
        self.assertNotIn('von', NON_GIVEN_NAME_PARTICLES)
        self.assertNotIn('van', NON_GIVEN_NAME_PARTICLES)
        self.assertNotIn('della', NON_GIVEN_NAME_PARTICLES)

    def test_non_first_name_prefixes_disjoint_from_titles(self) -> None:
        # A member that is also a title is consumed as a title before the fold
        # would run, making it inert (the st/ste footgun). Pin the invariant on
        # the live default sets.
        self.assertEqual(NON_GIVEN_NAME_PARTICLES & TITLES, set())


class LastNamePrefixSplitTestCase(ParsedNameTestBase):

    def test_van_gogh_last_base(self) -> None:
        hn = parse("Vincent van Gogh")
        self.m(hn.family_base, "Gogh", hn)

    def test_van_gogh_last_prefixes(self) -> None:
        hn = parse("Vincent van Gogh")
        self.m(hn.family_particles, "van", hn)

    def test_von_bergen_wessels(self) -> None:
        hn = parse("pennie von bergen wessels")
        self.m(hn.family_base, "bergen wessels", hn)
        self.m(hn.family_particles, "von", hn)

    def test_de_la_vega_multiword_prefix(self) -> None:
        hn = parse("Juan de la Vega")
        self.m(hn.family_base, "Vega", hn)
        self.m(hn.family_particles, "de la", hn)

    def test_no_prefix(self) -> None:
        hn = parse("John Smith")
        self.m(hn.family_base, "Smith", hn)
        self.m(hn.family_particles, "", hn)

    def test_do_guard_surname_equals_prefix_word(self) -> None:
        # "Do" is in PARTICLES; without the guard last_base would be empty
        hn = parse("Anh Do")
        self.m(hn.family_base, "Do", hn)
        self.m(hn.family_particles, "", hn)

    def test_all_particles_guard(self) -> None:
        # Artificial case: last name whose every word is a prefix — must not strip
        hn = parse("Smith van der")
        # last="van der"; both words are prefixes — guard fires, base = full last
        self.m(hn.family_base, hn.family, hn)
        self.m(hn.family_particles, "", hn)

    def test_da_silva_title_plus_prefix(self) -> None:
        hn = parse("Dra. Andréia da Silva")
        self.m(hn.family_base, "Silva", hn)
        self.m(hn.family_particles, "da", hn)

    def test_empty_name(self) -> None:
        hn = parse("")
        self.m(hn.family_base, "", hn)
        self.m(hn.family_particles, "", hn)

    def test_case_insensitive_prefix_detection(self) -> None:
        hn = parse("VINCENT VAN GOGH")
        self.m(hn.family_particles, "VAN", hn)
        self.m(hn.family_base, "GOGH", hn)

    # --- targets: leading non-first-name prefix becomes the surname ---

    def test_leading_non_first_name_prefix_de(self) -> None:
        hn = parse("de Mesnil")
        self.m(hn.given, "", hn)
        self.m(hn.middle, "", hn)
        self.m(hn.family, "de Mesnil", hn)

    def test_leading_non_first_name_prefix_dos(self) -> None:
        hn = parse("dos Santos")
        self.m(hn.given, "", hn)
        self.m(hn.family, "dos Santos", hn)

    def test_leading_non_first_name_prefix_chain(self) -> None:
        hn = parse("de la Vega")
        self.m(hn.given, "", hn)
        self.m(hn.family, "de la Vega", hn)

    def test_leading_non_first_name_prefix_derived_props(self) -> None:
        hn = parse("de Mesnil")
        self.m(hn.family_particles, "de", hn)
        self.m(hn.family_base, "Mesnil", hn)

    def test_non_first_name_prefix_with_custom_title(self) -> None:
        # 'Gunny' is NOT a default title -> genuinely exercises the custom-title
        # path. Title is consumed first, so the fold does
        # not fire and the surname is already correct; asserts we don't corrupt
        # the title case.
        parser = Parser(lexicon=Lexicon.default().add(titles={'gunny'}))
        hn = parser.parse("Gunny de Mesnil")
        self.m(hn.title, "Gunny", hn)
        self.m(hn.given, "", hn)
        self.m(hn.family, "de Mesnil", hn)

    def test_repeated_prefix_chain_de_la(self) -> None:
        hn = parse("Juan de la de la Vega")
        self.m(hn.given, "Juan", hn)
        self.m(hn.family, "de la de la Vega", hn)

    def test_repeated_prefix_chain_van_der(self) -> None:
        hn = parse("Charles van der van der Berg")
        self.m(hn.given, "Charles", hn)
        self.m(hn.family, "van der van der Berg", hn)

    def test_triple_repeated_prefix_chain(self) -> None:
        # a stronger regression guard than the 2-repeat cases above: the
        # contiguous-prefix absorption loop should chain any number of
        # repeats, not just handle exactly two
        hn = parse("Juan de la de la de la Vega")
        self.m(hn.given, "Juan", hn)
        self.m(hn.family, "de la de la de la Vega", hn)

    def test_repeated_prefix_chain_followed_by_suffix(self) -> None:
        # the prefix-run absorption loop and the suffix-boundary loop share
        # the same index variable, so a repeated chain immediately
        # followed by a suffix is worth pinning down explicitly
        hn = parse("Juan de la de la Vega Jr.")
        self.m(hn.given, "Juan", hn)
        self.m(hn.family, "de la de la Vega", hn)
        self.m(hn.suffix, "Jr.", hn)

    # --- safety: excluded / ambiguous particles are unchanged ---

    def test_leading_von_is_unchanged(self) -> None:
        hn = parse("von Braun")
        self.m(hn.given, "von", hn)
        self.m(hn.family, "Braun", hn)

    def test_leading_van_is_unchanged(self) -> None:
        hn = parse("Van Johnson")
        self.m(hn.given, "Van", hn)
        self.m(hn.family, "Johnson", hn)

    def test_leading_della_is_unchanged(self) -> None:
        hn = parse("Della Reese")
        self.m(hn.given, "Della", hn)
        self.m(hn.family, "Reese", hn)

    def test_leading_di_is_unchanged(self) -> None:
        hn = parse("Di Caprio")
        self.m(hn.given, "Di", hn)
        self.m(hn.family, "Caprio", hn)

    def test_leading_del_is_unchanged(self) -> None:
        hn = parse("Del Toro")
        self.m(hn.given, "Del", hn)
        self.m(hn.family, "Toro", hn)

    def test_non_leading_prefix_is_unchanged(self) -> None:
        hn = parse("Jean de Mesnil")
        self.m(hn.given, "Jean", hn)
        self.m(hn.family, "de Mesnil", hn)

    # --- guard: bare particle with nothing to attach to ---

    def test_bare_non_first_name_prefix_guard(self) -> None:
        hn = parse("de")
        self.m(hn.given, "de", hn)
        self.m(hn.family, "", hn)

    # --- interactions with opt-in handlers that also run in post_process ---

    def test_leading_non_first_name_prefix_case_insensitive(self) -> None:
        hn = parse("DE MESNIL")
        self.m(hn.given, "", hn)
        self.m(hn.family, "DE MESNIL", hn)

    def test_leading_non_first_name_prefix_with_suffix(self) -> None:
        hn = parse("de Mesnil Jr.")
        self.m(hn.given, "", hn)
        self.m(hn.family, "de Mesnil", hn)
        self.m(hn.suffix, "Jr.", hn)

    def test_leading_non_first_name_prefix_with_patronymic_name_order(self) -> None:
        # The fold requires a single given-name piece; the patronymic rules
        # only matter once there is more than one piece, so the fold
        # and this opt-in handler don't fight over the same input shape here.
        policy = Policy(patronymic_rules=frozenset({PatronymicRule.EAST_SLAVIC, PatronymicRule.TURKIC}))
        hn = Parser(policy=policy).parse("de Mesnil")
        self.m(hn.given, "", hn)
        self.m(hn.family, "de Mesnil", hn)

    def test_leading_non_first_name_prefix_with_middle_name_as_last(self) -> None:
        # The leading-particle fold runs first and empties the middle, so
        # the later opt-in middle_as_family has nothing left to do.
        hn = Parser(policy=Policy(middle_as_family=True)).parse("de Mesnil Garcia")
        self.m(hn.given, "", hn)
        self.m(hn.family, "de Mesnil Garcia", hn)
