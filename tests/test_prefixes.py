import pytest

from nameparser import HumanName
from nameparser.config.prefixes import PREFIXES, NON_FIRST_NAME_PREFIXES
from nameparser.config.first_name_prefixes import FIRST_NAME_PREFIXES

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

    def test_non_first_name_prefixes_subset_of_prefixes(self) -> None:
        # Every non-first-name prefix must still be a prefix so it joins forward.
        self.assertTrue(NON_FIRST_NAME_PREFIXES <= PREFIXES)

    def test_non_first_name_prefixes_disjoint_from_first_name_prefixes(self) -> None:
        # A word cannot be both "joins to the first name" and "never a first
        # name" (e.g. 'abu' is a first_name_prefix, so it is excluded here).
        self.assertEqual(NON_FIRST_NAME_PREFIXES & FIRST_NAME_PREFIXES, set())

    def test_non_first_name_prefixes_expected_members(self) -> None:
        # 'abu' is in PREFIXES but excluded (it is a first_name_prefix);
        # 'von'/'van'/'della'/'di'/'del' are excluded (they can be first names).
        self.assertIn('de', NON_FIRST_NAME_PREFIXES)
        self.assertIn('dos', NON_FIRST_NAME_PREFIXES)
        self.assertNotIn('abu', NON_FIRST_NAME_PREFIXES)
        self.assertNotIn('von', NON_FIRST_NAME_PREFIXES)
        self.assertNotIn('van', NON_FIRST_NAME_PREFIXES)
        self.assertNotIn('della', NON_FIRST_NAME_PREFIXES)


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
