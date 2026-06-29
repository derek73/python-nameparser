import pytest

from nameparser import HumanName

from tests.base import HumanNameTestBase


class HumanNameConjunctionTestCase(HumanNameTestBase):
    # Last name with conjunction
    def test_last_name_with_conjunction(self) -> None:
        hn = HumanName('Jose Aznar y Lopez')
        self.m(hn.first, "Jose", hn)
        self.m(hn.last, "Aznar y Lopez", hn)

    def test_multiple_conjunctions(self) -> None:
        hn = HumanName("part1 of The part2 of the part3 and part4")
        self.m(hn.first, "part1 of The part2 of the part3 and part4", hn)

    def test_multiple_conjunctions2(self) -> None:
        hn = HumanName("part1 of and The part2 of the part3 And part4")
        self.m(hn.first, "part1 of and The part2 of the part3 And part4", hn)

    def test_ends_with_conjunction(self) -> None:
        hn = HumanName("Jon Dough and")
        self.m(hn.first, "Jon", hn)
        self.m(hn.last, "Dough and", hn)

    def test_ends_with_two_conjunctions(self) -> None:
        hn = HumanName("Jon Dough and of")
        self.m(hn.first, "Jon", hn)
        self.m(hn.last, "Dough and of", hn)

    def test_starts_with_conjunction(self) -> None:
        hn = HumanName("and Jon Dough")
        self.m(hn.first, "and Jon", hn)
        self.m(hn.last, "Dough", hn)

    def test_starts_with_two_conjunctions(self) -> None:
        hn = HumanName("the and Jon Dough")
        self.m(hn.first, "the and Jon", hn)
        self.m(hn.last, "Dough", hn)

    # Potential conjunction/prefix treated as initial (because uppercase)
    def test_uppercase_middle_initial_conflict_with_conjunction(self) -> None:
        hn = HumanName('John E Smith')
        self.m(hn.first, "John", hn)
        self.m(hn.middle, "E", hn)
        self.m(hn.last, "Smith", hn)

    def test_lowercase_middle_initial_with_period_conflict_with_conjunction(self) -> None:
        hn = HumanName('john e. smith')
        self.m(hn.first, "john", hn)
        self.m(hn.middle, "e.", hn)
        self.m(hn.last, "smith", hn)

    # The conjunction "e" can also be an initial
    def test_lowercase_first_initial_conflict_with_conjunction(self) -> None:
        hn = HumanName('e j smith')
        self.m(hn.first, "e", hn)
        self.m(hn.middle, "j", hn)
        self.m(hn.last, "smith", hn)

    def test_lowercase_middle_initial_conflict_with_conjunction(self) -> None:
        hn = HumanName('John e Smith')
        self.m(hn.first, "John", hn)
        self.m(hn.middle, "e", hn)
        self.m(hn.last, "Smith", hn)

    def test_lowercase_middle_initial_and_suffix_conflict_with_conjunction(self) -> None:
        hn = HumanName('John e Smith, III')
        self.m(hn.first, "John", hn)
        self.m(hn.middle, "e", hn)
        self.m(hn.last, "Smith", hn)
        self.m(hn.suffix, "III", hn)

    def test_lowercase_middle_initial_and_nocomma_suffix_conflict_with_conjunction(self) -> None:
        hn = HumanName('John e Smith III')
        self.m(hn.first, "John", hn)
        self.m(hn.middle, "e", hn)
        self.m(hn.last, "Smith", hn)
        self.m(hn.suffix, "III", hn)

    def test_lowercase_middle_initial_comma_lastname_and_suffix_conflict_with_conjunction(self) -> None:
        hn = HumanName('Smith, John e, III, Jr')
        self.m(hn.first, "John", hn)
        self.m(hn.middle, "e", hn)
        self.m(hn.last, "Smith", hn)
        self.m(hn.suffix, "III, Jr", hn)

    @pytest.mark.xfail
    def test_two_initials_conflict_with_conjunction(self) -> None:
        # Supporting this seems to screw up titles with periods in them like M.B.A.
        hn = HumanName('E.T. Smith')
        self.m(hn.first, "E.", hn)
        self.m(hn.middle, "T.", hn)
        self.m(hn.last, "Smith", hn)

    def test_couples_names(self) -> None:
        hn = HumanName('John and Jane Smith')
        self.m(hn.first, "John and Jane", hn)
        self.m(hn.last, "Smith", hn)

    def test_couples_names_with_conjunction_lastname(self) -> None:
        hn = HumanName('John and Jane Aznar y Lopez')
        self.m(hn.first, "John and Jane", hn)
        self.m(hn.last, "Aznar y Lopez", hn)

    def test_couple_titles(self) -> None:
        hn = HumanName('Mr. and Mrs. John and Jane Smith')
        self.m(hn.title, "Mr. and Mrs.", hn)
        self.m(hn.first, "John and Jane", hn)
        self.m(hn.last, "Smith", hn)

    def test_couple_titles_ampersand_conjunction(self) -> None:
        # issue 151: single-char conjunctions in the conjunctions list should
        # be honored even when total_length < 4
        hn = HumanName('Mr. & Mrs. John Smith')
        self.m(hn.title, "Mr. & Mrs.", hn)
        self.m(hn.first, "John", hn)
        self.m(hn.last, "Smith", hn)

    def test_ampersand_conjunction_short_name_no_titles(self) -> None:
        # & is non-alpha so it should always be honored as a conjunction,
        # even when total_length < 4 (no titles to inflate the count)
        hn = HumanName('John & Jane')
        self.m(hn.first, "John & Jane", hn)

    def test_single_char_alpha_conjunction_still_treated_as_initial_when_short(self) -> None:
        # single-char alpha conjunctions (e, y) are still treated as initials
        # when total_length < 4; only non-alpha symbols like & bypass this guard
        hn = HumanName('John y Jane')
        self.m(hn.first, "John", hn)
        self.m(hn.middle, "y", hn)
        self.m(hn.last, "Jane", hn)

    def test_title_with_three_part_name_last_initial_is_suffix_uppercase_no_period(self) -> None:
        hn = HumanName("King John Alexander V")
        self.m(hn.title, "King", hn)
        self.m(hn.first, "John", hn)
        self.m(hn.last, "Alexander", hn)
        self.m(hn.suffix, "V", hn)

    def test_four_name_parts_with_suffix_that_could_be_initial_lowercase_no_period(self) -> None:
        hn = HumanName("larry james edward johnson v")
        self.m(hn.first, "larry", hn)
        self.m(hn.middle, "james edward", hn)
        self.m(hn.last, "johnson", hn)
        self.m(hn.suffix, "v", hn)

    def test_four_name_parts_with_suffix_that_could_be_initial_uppercase_no_period(self) -> None:
        hn = HumanName("Larry James Johnson I")
        self.m(hn.first, "Larry", hn)
        self.m(hn.middle, "James", hn)
        self.m(hn.last, "Johnson", hn)
        self.m(hn.suffix, "I", hn)

    def test_roman_numeral_initials(self) -> None:
        hn = HumanName("Larry V I")
        self.m(hn.first, "Larry", hn)
        self.m(hn.middle, "V", hn)
        self.m(hn.last, "I", hn)
        self.m(hn.suffix, "", hn)

    def test_roman_numeral_suffix_not_in_suffix_list(self) -> None:
        # VI-X are not in the suffix word lists, so they reach the
        # is_roman_numeral(nxt) branch rather than are_suffixes()
        hn = HumanName("John Smith VI")
        self.m(hn.first, "John", hn)
        self.m(hn.last, "Smith", hn)
        self.m(hn.suffix, "VI", hn)

    # tests for Rev. title (Reverend)
    def test124(self) -> None:
        hn = HumanName("Rev. John A. Kenneth Doe")
        self.m(hn.title, "Rev.", hn)
        self.m(hn.middle, "A. Kenneth", hn)
        self.m(hn.first, "John", hn)
        self.m(hn.last, "Doe", hn)

    def test125(self) -> None:
        hn = HumanName("Rev John A. Kenneth Doe")
        self.m(hn.title, "Rev", hn)
        self.m(hn.middle, "A. Kenneth", hn)
        self.m(hn.first, "John", hn)
        self.m(hn.last, "Doe", hn)

    def test126(self) -> None:
        hn = HumanName("Doe, Rev. John A. Jr.")
        self.m(hn.title, "Rev.", hn)
        self.m(hn.first, "John", hn)
        self.m(hn.last, "Doe", hn)
        self.m(hn.middle, "A.", hn)
        self.m(hn.suffix, "Jr.", hn)

    def test127(self) -> None:
        hn = HumanName("Buca di Beppo")
        self.m(hn.first, "Buca", hn)
        self.m(hn.last, "di Beppo", hn)

    def test_le_as_last_name(self) -> None:
        hn = HumanName("Yin Le")
        self.m(hn.first, "Yin", hn)
        self.m(hn.last, "Le", hn)

    def test_le_as_last_name_with_middle_initial(self) -> None:
        hn = HumanName("Yin a Le")
        self.m(hn.first, "Yin", hn)
        self.m(hn.middle, "a", hn)
        self.m(hn.last, "Le", hn)

    def test_conjunction_in_an_address_with_a_title(self) -> None:
        hn = HumanName("His Excellency Lord Duncan")
        self.m(hn.title, "His Excellency Lord", hn)
        self.m(hn.last, "Duncan", hn)

    @pytest.mark.xfail
    def test_conjunction_in_an_address_with_a_first_name_title(self) -> None:
        hn = HumanName("Her Majesty Queen Elizabeth")
        self.m(hn.title, "Her Majesty Queen", hn)
        # if you want to be technical, Queen is in FIRST_NAME_TITLES
        self.m(hn.first, "Elizabeth", hn)

    def test_name_is_conjunctions(self) -> None:
        hn = HumanName("e and e")
        self.m(hn.first, "e and e", hn)
