import pytest

from nameparser import HumanName

from tests.base import HumanNameTestBase


class HumanNameCapitalizationTestCase(HumanNameTestBase):
    def test_capitalization_exception_for_III(self) -> None:
        hn = HumanName('juan q. xavier velasquez y garcia iii')
        hn.capitalize()
        self.m(str(hn), 'Juan Q. Xavier Velasquez y Garcia III', hn)

    # FIXME: this test does not pass due to a known issue
    # http://code.google.com/p/python-nameparser/issues/detail?id=22
    @pytest.mark.xfail
    def test_capitalization_exception_for_already_capitalized_III_KNOWN_FAILURE(self) -> None:
        hn = HumanName('juan garcia III')
        hn.capitalize()
        self.m(str(hn), 'Juan Garcia III', hn)

    def test_capitalize_title(self) -> None:
        hn = HumanName('lt. gen. john a. kenneth doe iv')
        hn.capitalize()
        self.m(str(hn), 'Lt. Gen. John A. Kenneth Doe IV', hn)

    def test_capitalize_title_to_lower(self) -> None:
        hn = HumanName('LT. GEN. JOHN A. KENNETH DOE IV')
        hn.capitalize()
        self.m(str(hn), 'Lt. Gen. John A. Kenneth Doe IV', hn)

    # Capitalization with M(a)c and hyphenated names
    def test_capitalization_with_Mac_as_hyphenated_names(self) -> None:
        hn = HumanName('donovan mcnabb-smith')
        hn.capitalize()
        self.m(str(hn), 'Donovan McNabb-Smith', hn)

    def test_capitization_middle_initial_is_also_a_conjunction(self) -> None:
        hn = HumanName('scott e. werner')
        hn.capitalize()
        self.m(str(hn), 'Scott E. Werner', hn)

    # Leaving already-capitalized names alone
    def test_no_change_to_mixed_chase(self) -> None:
        hn = HumanName('Shirley Maclaine')
        hn.capitalize()
        self.m(str(hn), 'Shirley Maclaine', hn)

    def test_force_capitalization(self) -> None:
        hn = HumanName('Shirley Maclaine')
        hn.capitalize(force=True)
        self.m(str(hn), 'Shirley MacLaine', hn)

    def test_capitalize_diacritics(self) -> None:
        hn = HumanName('matthëus schmidt')
        hn.capitalize()
        self.m(str(hn), 'Matthëus Schmidt', hn)

    # http://code.google.com/p/python-nameparser/issues/detail?id=15
    def test_downcasing_mac(self) -> None:
        hn = HumanName('RONALD MACDONALD')
        hn.capitalize()
        self.m(str(hn), 'Ronald MacDonald', hn)

    # http://code.google.com/p/python-nameparser/issues/detail?id=23
    def test_downcasing_mc(self) -> None:
        hn = HumanName('RONALD MCDONALD')
        hn.capitalize()
        self.m(str(hn), 'Ronald McDonald', hn)

    def test_short_names_with_mac(self) -> None:
        hn = HumanName('mack johnson')
        hn.capitalize()
        self.m(str(hn), 'Mack Johnson', hn)

    def test_portuguese_prefixes(self) -> None:
        hn = HumanName("joao da silva do amaral de souza")
        hn.capitalize()
        self.m(str(hn), 'Joao da Silva do Amaral de Souza', hn)

    def test_capitalize_prefix_clash_on_first_name(self) -> None:
        hn = HumanName("van nguyen")
        hn.capitalize()
        self.m(str(hn), 'Van Nguyen', hn)
