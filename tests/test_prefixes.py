import pytest

from nameparser import HumanName
from nameparser.config import CONSTANTS, Constants
from nameparser.config.prefixes import NON_FIRST_NAME_PREFIXES

from tests.base import HumanNameTestBase


class PrefixesTestCase(HumanNameTestBase):

    def test_prefix(self) -> None:
        hn = HumanName("Juan del Sur")
        self.m(hn.first, "Juan", hn)
        self.m(hn.last, "del Sur", hn)

    def test_prefix_with_period(self) -> None:
        hn = HumanName("Jill St. John")
        self.m(hn.first, "Jill", hn)
        self.m(hn.last, "St. John", hn)

    def test_prefix_before_two_part_last_name(self) -> None:
        hn = HumanName("pennie von bergen wessels")
        self.m(hn.first, "pennie", hn)
        self.m(hn.last, "von bergen wessels", hn)

    def test_prefix_is_first_name(self) -> None:
        hn = HumanName("Van Johnson")
        self.m(hn.first, "Van", hn)
        self.m(hn.last, "Johnson", hn)

    def test_prefix_is_first_name_with_middle_name(self) -> None:
        hn = HumanName("Van Jeremy Johnson")
        self.m(hn.first, "Van", hn)
        self.m(hn.middle, "Jeremy", hn)
        self.m(hn.last, "Johnson", hn)

    def test_prefix_before_two_part_last_name_with_suffix(self) -> None:
        hn = HumanName("pennie von bergen wessels III")
        self.m(hn.first, "pennie", hn)
        self.m(hn.last, "von bergen wessels", hn)
        self.m(hn.suffix, "III", hn)

    def test_prefix_before_two_part_last_name_with_acronym_suffix(self) -> None:
        hn = HumanName("pennie von bergen wessels M.D.")
        self.m(hn.first, "pennie", hn)
        self.m(hn.last, "von bergen wessels", hn)
        self.m(hn.suffix, "M.D.", hn)

    def test_title_before_and_after_prefixed_last_name(self) -> None:
        # Issue #100: a repeated title/suffix token ("dr") before AND after a
        # prefixed last name used to corrupt the middle name into
        # " dr Vincent van" because the suffix-boundary lookup matched the
        # LEADING "dr" instead of the trailing one.
        hn = HumanName("dr Vincent van Gogh dr")
        self.m(hn.title, "dr", hn)
        self.m(hn.first, "Vincent", hn)
        self.m(hn.middle, "", hn)
        self.m(hn.last, "van Gogh", hn)
        self.m(hn.suffix, "dr", hn)

    def test_suffix_token_collision_with_two_word_prefix(self) -> None:
        # Same fix as #100 but with a two-word prefix ("van der"). Exercises a
        # different iteration count through the prefix-joining loop.
        hn = HumanName("dr Vincent van der Gogh dr")
        self.m(hn.title, "dr", hn)
        self.m(hn.first, "Vincent", hn)
        self.m(hn.middle, "", hn)
        self.m(hn.last, "van der Gogh", hn)
        self.m(hn.suffix, "dr", hn)

    def test_title_before_and_after_prefixed_last_name_with_middle(self) -> None:
        # The pre-fix bug corrupted the middle field; verify it is not disturbed
        # when a genuine middle name is present alongside the repeated token.
        hn = HumanName("dr Vincent James van Gogh dr")
        self.m(hn.title, "dr", hn)
        self.m(hn.first, "Vincent", hn)
        self.m(hn.middle, "James", hn)
        self.m(hn.last, "van Gogh", hn)
        self.m(hn.suffix, "dr", hn)

    @pytest.mark.timeout(2)
    def test_many_repeated_prefixes_does_not_blow_up(self) -> None:
        # Issue #108: a name with a long run of repeated prefixes used to grow
        # the pieces list exponentially and exhaust memory. The 2-second timeout
        # enforces this locally and in CI — if the test hangs, an exponential
        # regression has been reintroduced.
        name = "Jan " + "van der " * 30 + "Berg"
        hn = HumanName(name)
        self.assertFalse(hn.unparsable)
        self.m(hn.first, "Jan", hn)
        self.assertIn("Berg", hn.last)

    def test_two_part_last_name_with_suffix_comma(self) -> None:
        hn = HumanName("pennie von bergen wessels, III")
        self.m(hn.first, "pennie", hn)
        self.m(hn.last, "von bergen wessels", hn)
        self.m(hn.suffix, "III", hn)

    def test_two_part_last_name_with_suffix(self) -> None:
        hn = HumanName("von bergen wessels, pennie III")
        self.m(hn.first, "pennie", hn)
        self.m(hn.last, "von bergen wessels", hn)
        self.m(hn.suffix, "III", hn)

    def test_last_name_two_part_last_name_with_two_suffixes(self) -> None:
        hn = HumanName("von bergen wessels MD, pennie III")
        self.m(hn.first, "pennie", hn)
        self.m(hn.last, "von bergen wessels", hn)
        self.m(hn.suffix, "MD, III", hn)

    def test_comma_two_part_last_name_with_acronym_suffix(self) -> None:
        hn = HumanName("von bergen wessels, pennie MD")
        self.m(hn.first, "pennie", hn)
        self.m(hn.last, "von bergen wessels", hn)
        self.m(hn.suffix, "MD", hn)

    def test_comma_two_part_last_name_with_suffix_in_first_part(self) -> None:
        # I'm kinda surprised this works, not really sure if this is a
        # realistic place for a suffix to be.
        hn = HumanName("von bergen wessels MD, pennie")
        self.m(hn.first, "pennie", hn)
        self.m(hn.last, "von bergen wessels", hn)
        self.m(hn.suffix, "MD", hn)

    def test_title_two_part_last_name_with_suffix_in_first_part(self) -> None:
        hn = HumanName("pennie von bergen wessels MD, III")
        self.m(hn.first, "pennie", hn)
        self.m(hn.last, "von bergen wessels", hn)
        self.m(hn.suffix, "MD, III", hn)

    def test_portuguese_dos(self) -> None:
        hn = HumanName("Rafael Sousa dos Anjos")
        self.m(hn.first, "Rafael", hn)
        self.m(hn.middle, "Sousa", hn)
        self.m(hn.last, "dos Anjos", hn)

    def test_portuguese_prefixes(self) -> None:
        hn = HumanName("Joao da Silva do Amaral de Souza")
        self.m(hn.first, "Joao", hn)
        self.m(hn.middle, "da Silva do Amaral", hn)
        self.m(hn.last, "de Souza", hn)

    def test_three_conjunctions(self) -> None:
        hn = HumanName("Dr. Juan Q. Xavier de la dos Vega III")
        self.m(hn.first, "Juan", hn)
        self.m(hn.last, "de la dos Vega", hn)
        self.m(hn.title, "Dr.", hn)
        self.m(hn.middle, "Q. Xavier", hn)
        self.m(hn.suffix, "III", hn)

    def test_lastname_three_conjunctions(self) -> None:
        hn = HumanName("de la dos Vega, Dr. Juan Q. Xavier III")
        self.m(hn.first, "Juan", hn)
        self.m(hn.last, "de la dos Vega", hn)
        self.m(hn.title, "Dr.", hn)
        self.m(hn.middle, "Q. Xavier", hn)
        self.m(hn.suffix, "III", hn)

    def test_comma_three_conjunctions(self) -> None:
        hn = HumanName("Dr. Juan Q. Xavier de la dos Vega, III")
        self.m(hn.first, "Juan", hn)
        self.m(hn.last, "de la dos Vega", hn)
        self.m(hn.title, "Dr.", hn)
        self.m(hn.middle, "Q. Xavier", hn)
        self.m(hn.suffix, "III", hn)

    # The subset-of-PREFIXES and disjoint-from-BOUND_FIRST_NAMES invariants
    # are enforced by import-time asserts in nameparser/config/prefixes.py,
    # so they are not repeated as tests here.

    def test_non_first_name_prefixes_expected_members(self) -> None:
        # 'abu' is in PREFIXES but excluded (it is a bound_first_name);
        # 'von'/'van'/'della'/'di'/'del' are excluded (they can be first names).
        self.assertIn('de', NON_FIRST_NAME_PREFIXES)
        self.assertIn('dos', NON_FIRST_NAME_PREFIXES)
        self.assertNotIn('abu', NON_FIRST_NAME_PREFIXES)
        self.assertNotIn('von', NON_FIRST_NAME_PREFIXES)
        self.assertNotIn('van', NON_FIRST_NAME_PREFIXES)
        self.assertNotIn('della', NON_FIRST_NAME_PREFIXES)

    def test_constants_exposes_non_first_name_prefixes(self) -> None:
        self.assertEqual(set(CONSTANTS.non_first_name_prefixes), NON_FIRST_NAME_PREFIXES)

    def test_non_first_name_prefixes_disjoint_from_titles(self) -> None:
        # A member that is also a title is consumed as a title before the fold
        # would run, making it inert (the st/ste footgun). Pin the invariant on
        # the live default sets.
        self.assertEqual(
            set(CONSTANTS.non_first_name_prefixes) & set(CONSTANTS.titles),
            set(),
        )

    def test_non_first_name_prefixes_constructor_arg(self) -> None:
        c = Constants(non_first_name_prefixes={'zzz'})
        self.assertEqual(set(c.non_first_name_prefixes), {'zzz'})


class LastNamePrefixSplitTestCase(HumanNameTestBase):

    def test_van_gogh_last_base(self) -> None:
        hn = HumanName("Vincent van Gogh")
        self.m(hn.last_base, "Gogh", hn)

    def test_van_gogh_last_prefixes(self) -> None:
        hn = HumanName("Vincent van Gogh")
        self.m(hn.last_prefixes, "van", hn)

    def test_van_gogh_last_base_list(self) -> None:
        hn = HumanName("Vincent van Gogh")
        self.m(hn.last_base_list, ["Gogh"], hn)

    def test_van_gogh_last_prefixes_list(self) -> None:
        hn = HumanName("Vincent van Gogh")
        self.m(hn.last_prefixes_list, ["van"], hn)

    def test_von_bergen_wessels(self) -> None:
        hn = HumanName("pennie von bergen wessels")
        self.m(hn.last_base, "bergen wessels", hn)
        self.m(hn.last_prefixes, "von", hn)
        self.m(hn.last_base_list, ["bergen", "wessels"], hn)
        self.m(hn.last_prefixes_list, ["von"], hn)

    def test_de_la_vega_multiword_prefix(self) -> None:
        hn = HumanName("Juan de la Vega")
        self.m(hn.last_base, "Vega", hn)
        self.m(hn.last_prefixes, "de la", hn)
        self.m(hn.last_prefixes_list, ["de", "la"], hn)

    def test_no_prefix(self) -> None:
        hn = HumanName("John Smith")
        self.m(hn.last_base, "Smith", hn)
        self.m(hn.last_prefixes, "", hn)
        # self.m() coerces [] via `expected or empty_attribute_default`; use assertEqual for empty lists
        self.assertEqual(hn.last_prefixes_list, [])

    def test_do_guard_surname_equals_prefix_word(self) -> None:
        # "Do" is in PREFIXES; without the guard last_base would be empty
        hn = HumanName("Anh Do")
        self.m(hn.last_base, "Do", hn)
        self.m(hn.last_prefixes, "", hn)

    def test_all_particles_guard(self) -> None:
        # Artificial case: last name whose every word is a prefix — must not strip
        hn = HumanName("Smith van der")
        # last="van der"; both words are prefixes — guard fires, base = full last
        self.m(hn.last_base, hn.last, hn)
        self.m(hn.last_prefixes, "", hn)

    def test_alias_family_equals_last_base(self) -> None:
        hn = HumanName("Vincent van Gogh")
        self.m(hn.family, hn.last_base, hn)

    def test_alias_family_prefixes_equals_last_prefixes(self) -> None:
        hn = HumanName("Vincent van Gogh")
        self.m(hn.family_prefixes, hn.last_prefixes, hn)

    def test_da_silva_title_plus_prefix(self) -> None:
        hn = HumanName("Dra. Andréia da Silva")
        self.m(hn.last_base, "Silva", hn)
        self.m(hn.last_prefixes, "da", hn)

    def test_empty_name(self) -> None:
        hn = HumanName()
        self.m(hn.last_base, "", hn)
        self.m(hn.last_prefixes, "", hn)
        # self.m() coerces [] via `expected or empty_attribute_default`; use assertEqual for empty lists
        self.assertEqual(hn.last_base_list, [])
        self.assertEqual(hn.last_prefixes_list, [])

    def test_case_insensitive_prefix_detection(self) -> None:
        hn = HumanName("VINCENT VAN GOGH")
        self.m(hn.last_prefixes, "VAN", hn)
        self.m(hn.last_base, "GOGH", hn)

    # --- targets: leading non-first-name prefix becomes the surname ---

    def test_leading_non_first_name_prefix_de(self) -> None:
        hn = HumanName("de Mesnil")
        self.m(hn.first, "", hn)
        self.m(hn.middle, "", hn)
        self.m(hn.last, "de Mesnil", hn)

    def test_leading_non_first_name_prefix_dos(self) -> None:
        hn = HumanName("dos Santos")
        self.m(hn.first, "", hn)
        self.m(hn.last, "dos Santos", hn)

    def test_leading_non_first_name_prefix_chain(self) -> None:
        hn = HumanName("de la Vega")
        self.m(hn.first, "", hn)
        self.m(hn.last, "de la Vega", hn)

    def test_leading_non_first_name_prefix_derived_props(self) -> None:
        hn = HumanName("de Mesnil")
        self.m(hn.last_prefixes, "de", hn)
        self.m(hn.last_base, "Mesnil", hn)

    def test_non_first_name_prefix_with_custom_title(self) -> None:
        # 'Gunny' is NOT a default title -> genuinely exercises the custom-title
        # path. Title is consumed first (first_list == ['']), so the fold does
        # not fire and the surname is already correct; asserts we don't corrupt
        # the title case.
        CONSTANTS.titles.add('gunny')
        hn = HumanName("Gunny de Mesnil")
        self.m(hn.title, "Gunny", hn)
        self.m(hn.first, "", hn)
        self.m(hn.last, "de Mesnil", hn)

    def test_repeated_prefix_chain_de_la(self) -> None:
        hn = HumanName("Juan de la de la Vega")
        self.m(hn.first, "Juan", hn)
        self.m(hn.last, "de la de la Vega", hn)

    def test_repeated_prefix_chain_van_der(self) -> None:
        hn = HumanName("Charles van der van der Berg")
        self.m(hn.first, "Charles", hn)
        self.m(hn.last, "van der van der Berg", hn)

    def test_triple_repeated_prefix_chain(self) -> None:
        # a stronger regression guard than the 2-repeat cases above: the
        # contiguous-prefix absorption loop should chain any number of
        # repeats, not just handle exactly two
        hn = HumanName("Juan de la de la de la Vega")
        self.m(hn.first, "Juan", hn)
        self.m(hn.last, "de la de la de la Vega", hn)

    def test_repeated_prefix_chain_followed_by_suffix(self) -> None:
        # the prefix-run absorption loop and the suffix-boundary loop share
        # the same index variable, so a repeated chain immediately
        # followed by a suffix is worth pinning down explicitly
        hn = HumanName("Juan de la de la Vega Jr.")
        self.m(hn.first, "Juan", hn)
        self.m(hn.last, "de la de la Vega", hn)
        self.m(hn.suffix, "Jr.", hn)

    # --- safety: excluded / ambiguous particles are unchanged ---

    def test_leading_von_is_unchanged(self) -> None:
        hn = HumanName("von Braun")
        self.m(hn.first, "von", hn)
        self.m(hn.last, "Braun", hn)

    def test_leading_van_is_unchanged(self) -> None:
        hn = HumanName("Van Johnson")
        self.m(hn.first, "Van", hn)
        self.m(hn.last, "Johnson", hn)

    def test_leading_della_is_unchanged(self) -> None:
        hn = HumanName("Della Reese")
        self.m(hn.first, "Della", hn)
        self.m(hn.last, "Reese", hn)

    def test_leading_di_is_unchanged(self) -> None:
        hn = HumanName("Di Caprio")
        self.m(hn.first, "Di", hn)
        self.m(hn.last, "Caprio", hn)

    def test_leading_del_is_unchanged(self) -> None:
        hn = HumanName("Del Toro")
        self.m(hn.first, "Del", hn)
        self.m(hn.last, "Toro", hn)

    def test_non_leading_prefix_is_unchanged(self) -> None:
        hn = HumanName("Jean de Mesnil")
        self.m(hn.first, "Jean", hn)
        self.m(hn.last, "de Mesnil", hn)

    # --- guard: bare particle with nothing to attach to ---

    def test_bare_non_first_name_prefix_guard(self) -> None:
        hn = HumanName("de")
        self.m(hn.first, "de", hn)
        self.m(hn.last, "", hn)

    # --- interactions with opt-in handlers that also run in post_process ---

    def test_leading_non_first_name_prefix_case_insensitive(self) -> None:
        hn = HumanName("DE MESNIL")
        self.m(hn.first, "", hn)
        self.m(hn.last, "DE MESNIL", hn)

    def test_leading_non_first_name_prefix_with_suffix(self) -> None:
        hn = HumanName("de Mesnil Jr.")
        self.m(hn.first, "", hn)
        self.m(hn.last, "de Mesnil", hn)
        self.m(hn.suffix, "Jr.", hn)

    def test_leading_non_first_name_prefix_with_patronymic_name_order(self) -> None:
        # The fold requires a single-token first_list; patronymic_name_order
        # only matters once first_list has more than one piece, so the fold
        # and this opt-in handler don't fight over the same input shape here.
        constants = Constants(patronymic_name_order=True)
        hn = HumanName("de Mesnil", constants=constants)
        self.m(hn.first, "", hn)
        self.m(hn.last, "de Mesnil", hn)

    def test_leading_non_first_name_prefix_with_middle_name_as_last(self) -> None:
        # handle_non_first_name_prefix runs first and empties middle_list, so
        # the later opt-in handle_middle_name_as_last has nothing left to do.
        constants = Constants(middle_name_as_last=True)
        hn = HumanName("de Mesnil Garcia", constants=constants)
        self.m(hn.first, "", hn)
        self.m(hn.last, "de Mesnil Garcia", hn)
