import pytest

from nameparser import HumanName

from tests.base import HumanNameTestBase


class SuffixesTestCase(HumanNameTestBase):

    def test_suffix(self) -> None:
        hn = HumanName("Joe Franklin Jr")
        self.m(hn.first, "Joe", hn)
        self.m(hn.last, "Franklin", hn)
        self.m(hn.suffix, "Jr", hn)

    def test_suffix_with_periods(self) -> None:
        hn = HumanName("Joe Dentist D.D.S.")
        self.m(hn.first, "Joe", hn)
        self.m(hn.last, "Dentist", hn)
        self.m(hn.suffix, "D.D.S.", hn)

    def test_two_suffixes(self) -> None:
        hn = HumanName("Kenneth Clarke QC MP")
        self.m(hn.first, "Kenneth", hn)
        self.m(hn.last, "Clarke", hn)
        # NOTE: this adds a comma when the original format did not have one.
        # not ideal but at least its in the right bucket
        self.m(hn.suffix, "QC, MP", hn)

    def test_two_suffixes_lastname_comma_format(self) -> None:
        hn = HumanName("Washington Jr. MD, Franklin")
        self.m(hn.first, "Franklin", hn)
        self.m(hn.last, "Washington", hn)
        # NOTE: this adds a comma when the original format did not have one.
        self.m(hn.suffix, "Jr., MD", hn)

    def test_two_suffixes_suffix_comma_format(self) -> None:
        hn = HumanName("Franklin Washington, Jr. MD")
        self.m(hn.first, "Franklin", hn)
        self.m(hn.last, "Washington", hn)
        self.m(hn.suffix, "Jr. MD", hn)

    def test_suffix_containing_periods(self) -> None:
        hn = HumanName("Kenneth Clarke Q.C.")
        self.m(hn.first, "Kenneth", hn)
        self.m(hn.last, "Clarke", hn)
        self.m(hn.suffix, "Q.C.", hn)

    def test_suffix_containing_periods_lastname_comma_format(self) -> None:
        hn = HumanName("Clarke, Kenneth, Q.C. M.P.")
        self.m(hn.first, "Kenneth", hn)
        self.m(hn.last, "Clarke", hn)
        self.m(hn.suffix, "Q.C. M.P.", hn)

    def test_suffix_containing_periods_suffix_comma_format(self) -> None:
        hn = HumanName("Kenneth Clarke Q.C., M.P.")
        self.m(hn.first, "Kenneth", hn)
        self.m(hn.last, "Clarke", hn)
        self.m(hn.suffix, "Q.C., M.P.", hn)

    def test_suffix_with_single_comma_format(self) -> None:
        hn = HumanName("John Doe jr., MD")
        self.m(hn.first, "John", hn)
        self.m(hn.last, "Doe", hn)
        self.m(hn.suffix, "jr., MD", hn)

    def test_suffix_with_double_comma_format(self) -> None:
        hn = HumanName("Doe, John jr., MD")
        self.m(hn.first, "John", hn)
        self.m(hn.last, "Doe", hn)
        self.m(hn.suffix, "jr., MD", hn)

    def test_phd_with_erroneous_space(self) -> None:
        hn = HumanName("John Smith, Ph. D.")
        self.m(hn.first, "John", hn)
        self.m(hn.last, "Smith", hn)
        self.m(hn.suffix, "Ph. D.", hn)

    def test_phd_extracted_without_comma(self) -> None:
        hn = HumanName("John Smith Ph. D.")
        self.m(hn.first, "John", hn)
        self.m(hn.last, "Smith", hn)
        self.m(hn.suffix, "Ph. D.", hn)

    def test_phd_conflict(self) -> None:
        hn = HumanName("Adolph D")
        self.m(hn.first, "Adolph", hn)
        self.m(hn.last, "D", hn)

    # http://en.wikipedia.org/wiki/Ma_(surname)

    def test_potential_suffix_that_is_also_last_name(self) -> None:
        hn = HumanName("Jack Ma")
        self.m(hn.first, "Jack", hn)
        self.m(hn.last, "Ma", hn)

    def test_potential_suffix_that_is_also_last_name_comma(self) -> None:
        hn = HumanName("Ma, Jack")
        self.m(hn.first, "Jack", hn)
        self.m(hn.last, "Ma", hn)

    def test_potential_suffix_that_is_also_last_name_with_suffix(self) -> None:
        hn = HumanName("Jack Ma Jr")
        self.m(hn.first, "Jack", hn)
        self.m(hn.last, "Ma", hn)
        self.m(hn.suffix, "Jr", hn)

    def test_potential_suffix_that_is_also_last_name_with_suffix_comma(self) -> None:
        hn = HumanName("Ma III, Jack Jr")
        self.m(hn.first, "Jack", hn)
        self.m(hn.last, "Ma", hn)
        self.m(hn.suffix, "III, Jr", hn)

    # https://github.com/derek73/python-nameparser/issues/27
    @pytest.mark.xfail
    def test_king(self) -> None:
        hn = HumanName("Dr King Jr")
        self.m(hn.title, "Dr", hn)
        self.m(hn.last, "King", hn)
        self.m(hn.suffix, "Jr", hn)

    def test_multiple_letter_suffix_with_periods(self) -> None:
        hn = HumanName("John Doe Msc.Ed.")
        self.m(hn.first, "John", hn)
        self.m(hn.last, "Doe", hn)
        self.m(hn.suffix, "Msc.Ed.", hn)

    def test_suffix_with_periods_with_comma(self) -> None:
        hn = HumanName("John Doe, Msc.Ed.")
        self.m(hn.first, "John", hn)
        self.m(hn.last, "Doe", hn)
        self.m(hn.suffix, "Msc.Ed.", hn)

    def test_suffix_with_periods_with_lastname_comma(self) -> None:
        hn = HumanName("Doe, John Msc.Ed.")
        self.m(hn.first, "John", hn)
        self.m(hn.last, "Doe", hn)
        self.m(hn.suffix, "Msc.Ed.", hn)

    def test_suffix_delimiter_default_on_constants(self) -> None:
        from nameparser.config import CONSTANTS
        self.assertIs(CONSTANTS.suffix_delimiter, None)

    def test_suffix_delimiter_kwarg_accepted(self) -> None:
        hn = HumanName("Steven Hardman, RN - CRNA", suffix_delimiter=" - ")
        self.assertEqual(hn.suffix_delimiter, " - ")

    def test_suffix_delimiter_basic(self) -> None:
        hn = HumanName("Steven Hardman, RN - CRNA", suffix_delimiter=" - ")
        self.m(hn.first, "Steven", hn)
        self.m(hn.last, "Hardman", hn)
        self.m(hn.suffix, "RN, CRNA", hn)

    def test_suffix_delimiter_multiple(self) -> None:
        hn = HumanName("John Doe, MD - PhD - FACS", suffix_delimiter=" - ")
        self.m(hn.first, "John", hn)
        self.m(hn.last, "Doe", hn)
        self.m(hn.suffix, "MD, PhD, FACS", hn)

    def test_suffix_delimiter_no_effect_without_comma(self) -> None:
        # suffix_delimiter only applies after the comma split; space-separated
        # suffixes already work via the no-comma parse path
        hn = HumanName("John Doe MD PhD", suffix_delimiter=" - ")
        self.m(hn.first, "John", hn)
        self.m(hn.last, "Doe", hn)
        self.m(hn.suffix, "MD, PhD", hn)
