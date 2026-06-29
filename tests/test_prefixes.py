from nameparser import HumanName

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

    def test_many_repeated_prefixes_does_not_blow_up(self) -> None:
        # Issue #108: a name with a long run of repeated prefixes used to grow
        # the pieces list exponentially and exhaust memory. Guard against a
        # regression: this must parse quickly and not raise. If an exponential
        # code path is reintroduced, this test will hang (CI timeout catches it).
        name = "Jan " + "van der " * 30 + "Berg"
        hn = HumanName(name)
        self.assertFalse(hn.unparsable)
        self.m(hn.first, "Jan", hn)

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
