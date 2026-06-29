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

    def test_capitalize_empty_middle_produces_no_leading_space_in_surnames(self) -> None:
        # str.split(' ') on an empty string returns [''] rather than [], so an
        # absent middle produced a spurious token that leaked into surnames_list
        # and caused a leading space in the surnames property (' Doe' not 'Doe').
        hn = HumanName('john doe')
        hn.capitalize()
        self.m(hn.surnames, 'Doe', hn)
        self.assertEqual(hn.middle_list, [])
        self.assertEqual(hn.surnames_list, ['Doe'])

    def test_capitalize_force_empty_middle_produces_no_leading_space_in_surnames(self) -> None:
        # Without force=True, capitalize() exits early for mixed-case names and
        # never reaches the split lines. Confirm the fix covers that path too.
        hn = HumanName('Jane Doe')
        hn.capitalize(force=True)
        self.m(hn.surnames, 'Doe', hn)
        self.assertEqual(hn.middle_list, [])

    def test_capitalize_empty_attributes_produce_no_spurious_tokens(self) -> None:
        # Confirm the fix extends beyond surnames: empty attribute lists are []
        # not [''], and non-empty ones contain only real tokens.
        hn = HumanName('Jane Doe')
        hn.capitalize(force=True)
        self.assertEqual(hn.title_list, [])
        self.assertEqual(hn.first_list, ['Jane'])
        self.assertEqual(hn.last_list, ['Doe'])

    def test_capitalize_title_and_last_only_no_spurious_tokens(self) -> None:
        # title+last with no first or middle leaves first_list and middle_list
        # both empty. All-caps triggers capitalize() without force=True.
        hn = HumanName('DR DOE')
        hn.capitalize()
        self.assertEqual(hn.first_list, [])
        self.assertEqual(hn.middle_list, [])
        self.m(str(hn), 'Dr Doe', hn)

    def test_capitalize_empty_suffix_produces_no_spurious_tokens(self) -> None:
        # ''.split(', ') returns [''] just like ''.split(' ') did for the other
        # attributes — an absent suffix should produce suffix_list == [], not [''].
        hn = HumanName('JOHN DOE')
        hn.capitalize()
        self.assertEqual(hn.suffix_list, [])

    def test_capitalize_single_suffix_still_works(self) -> None:
        hn = HumanName('JOHN DOE PHD')
        hn.capitalize()
        self.assertEqual(hn.suffix_list, ['Ph.D.'])

    def test_capitalize_multiple_suffixes_still_split_correctly(self) -> None:
        hn = HumanName('JOHN DOE PHD MD')
        hn.capitalize()
        self.assertEqual(hn.suffix_list, ['Ph.D.', 'M.D.'])

    def test_capitalize_suffix_acronym_with_dots(self) -> None:
        # Suffixes already written with dots (e.g. "M.D.") should capitalize
        # to their exception form, not title-case to "M.d." (issue #141)
        hn = HumanName('GREGORY HOUSE M.D.')
        hn.capitalize()
        self.assertEqual(hn.suffix, 'M.D.')

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
