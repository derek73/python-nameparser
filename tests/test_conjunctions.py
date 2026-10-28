import pytest

from nameparser import parse

from tests.base import ParsedNameTestBase


class ConjunctionTestCase(ParsedNameTestBase):
    # Last name with conjunction
    def test_last_name_with_conjunction(self) -> None:
        hn = parse('Jose Aznar y Lopez')
        self.m(hn.given, "Jose", hn)
        self.m(hn.family, "Aznar y Lopez", hn)

    def test_multiple_conjunctions(self) -> None:
        hn = parse("part1 of The part2 of the part3 and part4")
        self.m(hn.given, "part1 of The part2 of the part3 and part4", hn)

    def test_multiple_conjunctions2(self) -> None:
        hn = parse("part1 of and The part2 of the part3 And part4")
        self.m(hn.given, "part1 of and The part2 of the part3 And part4", hn)

    def test_ends_with_conjunction(self) -> None:
        hn = parse("Jon Dough and")
        self.m(hn.given, "Jon", hn)
        self.m(hn.family, "Dough and", hn)

    def test_ends_with_two_conjunctions(self) -> None:
        hn = parse("Jon Dough and of")
        self.m(hn.given, "Jon", hn)
        self.m(hn.family, "Dough and of", hn)

    def test_starts_with_conjunction(self) -> None:
        hn = parse("and Jon Dough")
        self.m(hn.given, "and Jon", hn)
        self.m(hn.family, "Dough", hn)

    def test_starts_with_two_conjunctions(self) -> None:
        hn = parse("the and Jon Dough")
        self.m(hn.given, "the and Jon", hn)
        self.m(hn.family, "Dough", hn)

    # Potential conjunction/prefix treated as initial (because uppercase)
    def test_uppercase_middle_initial_conflict_with_conjunction(self) -> None:
        hn = parse('John E Smith')
        self.m(hn.given, "John", hn)
        self.m(hn.middle, "E", hn)
        self.m(hn.family, "Smith", hn)

    def test_lowercase_middle_initial_with_period_conflict_with_conjunction(self) -> None:
        hn = parse('john e. smith')
        self.m(hn.given, "john", hn)
        self.m(hn.middle, "e.", hn)
        self.m(hn.family, "smith", hn)

    # The conjunction "e" can also be an initial
    def test_lowercase_first_initial_conflict_with_conjunction(self) -> None:
        hn = parse('e j smith')
        self.m(hn.given, "e", hn)
        self.m(hn.middle, "j", hn)
        self.m(hn.family, "smith", hn)

    def test_lowercase_middle_initial_conflict_with_conjunction(self) -> None:
        hn = parse('John e Smith')
        self.m(hn.given, "John", hn)
        self.m(hn.middle, "e", hn)
        self.m(hn.family, "Smith", hn)

    def test_lowercase_middle_initial_and_suffix_conflict_with_conjunction(self) -> None:
        hn = parse('John e Smith, III')
        self.m(hn.given, "John", hn)
        self.m(hn.middle, "e", hn)
        self.m(hn.family, "Smith", hn)
        self.m(hn.suffix, "III", hn)

    def test_lowercase_middle_initial_and_nocomma_suffix_conflict_with_conjunction(self) -> None:
        hn = parse('John e Smith III')
        self.m(hn.given, "John", hn)
        self.m(hn.middle, "e", hn)
        self.m(hn.family, "Smith", hn)
        self.m(hn.suffix, "III", hn)

    def test_lowercase_middle_initial_comma_lastname_and_suffix_conflict_with_conjunction(self) -> None:
        hn = parse('Smith, John e, III, Jr')
        self.m(hn.given, "John", hn)
        self.m(hn.middle, "e", hn)
        self.m(hn.family, "Smith", hn)
        self.m(hn.suffix, "III, Jr", hn)

    @pytest.mark.xfail(reason="#490")
    def test_two_initials_conflict_with_conjunction(self) -> None:
        # Supporting this seems to screw up titles with periods in them like M.B.A.
        hn = parse('E.T. Smith')
        self.m(hn.given, "E.", hn)
        self.m(hn.middle, "T.", hn)
        self.m(hn.family, "Smith", hn)

    def test_couples_names(self) -> None:
        hn = parse('John and Jane Smith')
        self.m(hn.given, "John and Jane", hn)
        self.m(hn.family, "Smith", hn)

    def test_couples_names_with_conjunction_lastname(self) -> None:
        hn = parse('John and Jane Aznar y Lopez')
        self.m(hn.given, "John and Jane", hn)
        self.m(hn.family, "Aznar y Lopez", hn)

    def test_couple_titles(self) -> None:
        hn = parse('Mr. and Mrs. John and Jane Smith')
        self.m(hn.title, "Mr. and Mrs.", hn)
        self.m(hn.given, "John and Jane", hn)
        self.m(hn.family, "Smith", hn)

    def test_couple_titles_ampersand_conjunction(self) -> None:
        # issue 151: single-char conjunctions in the conjunctions list should
        # be honored even when total_length < 4
        hn = parse('Mr. & Mrs. John Smith')
        self.m(hn.title, "Mr. & Mrs.", hn)
        self.m(hn.given, "John", hn)
        self.m(hn.family, "Smith", hn)

    def test_ampersand_conjunction_short_name_no_titles(self) -> None:
        # & is non-alpha so it should always be honored as a conjunction,
        # even when total_length < 4 (no titles to inflate the count)
        hn = parse('John & Jane')
        self.m(hn.given, "John & Jane", hn)

    def test_single_char_alpha_conjunction_still_treated_as_initial_when_short(self) -> None:
        # single-char alpha conjunctions (e, y) are still treated as initials
        # when total_length < 4; only non-alpha symbols like & bypass this guard
        hn = parse('John y Jane')
        self.m(hn.given, "John", hn)
        self.m(hn.middle, "y", hn)
        self.m(hn.family, "Jane", hn)

    def test_title_with_three_part_name_last_initial_is_suffix_uppercase_no_period(self) -> None:
        hn = parse("Pope John Alexander V")
        self.m(hn.title, "Pope", hn)
        self.m(hn.given, "John", hn)
        self.m(hn.family, "Alexander", hn)
        self.m(hn.suffix, "V", hn)

    def test_four_name_parts_with_suffix_that_could_be_initial_lowercase_no_period(self) -> None:
        hn = parse("larry james edward johnson v")
        self.m(hn.given, "larry", hn)
        self.m(hn.middle, "james edward", hn)
        self.m(hn.family, "johnson", hn)
        self.m(hn.suffix, "v", hn)

    def test_four_name_parts_with_suffix_that_could_be_initial_uppercase_no_period(self) -> None:
        hn = parse("Larry James Johnson I")
        self.m(hn.given, "Larry", hn)
        self.m(hn.middle, "James", hn)
        self.m(hn.family, "Johnson", hn)
        self.m(hn.suffix, "I", hn)

    def test_roman_numeral_initials(self) -> None:
        hn = parse("Larry V I")
        self.m(hn.given, "Larry", hn)
        self.m(hn.middle, "V", hn)
        self.m(hn.family, "I", hn)
        self.m(hn.suffix, "", hn)

    def test_roman_numeral_suffix_not_in_suffix_list(self) -> None:
        # VI-X are not in the suffix word lists, so they reach the
        # is_roman_numeral(nxt) branch rather than are_suffixes()
        hn = parse("John Smith VI")
        self.m(hn.given, "John", hn)
        self.m(hn.family, "Smith", hn)
        self.m(hn.suffix, "VI", hn)

    # tests for Rev. title (Reverend)
    def test124(self) -> None:
        hn = parse("Rev. John A. Kenneth Doe")
        self.m(hn.title, "Rev.", hn)
        self.m(hn.middle, "A. Kenneth", hn)
        self.m(hn.given, "John", hn)
        self.m(hn.family, "Doe", hn)

    def test125(self) -> None:
        hn = parse("Rev John A. Kenneth Doe")
        self.m(hn.title, "Rev", hn)
        self.m(hn.middle, "A. Kenneth", hn)
        self.m(hn.given, "John", hn)
        self.m(hn.family, "Doe", hn)

    def test126(self) -> None:
        hn = parse("Doe, Rev. John A. Jr.")
        self.m(hn.title, "Rev.", hn)
        self.m(hn.given, "John", hn)
        self.m(hn.family, "Doe", hn)
        self.m(hn.middle, "A.", hn)
        self.m(hn.suffix, "Jr.", hn)

    def test127(self) -> None:
        hn = parse("Buca di Beppo")
        self.m(hn.given, "Buca", hn)
        self.m(hn.family, "di Beppo", hn)

    def test_le_as_last_name(self) -> None:
        hn = parse("Yin Le")
        self.m(hn.given, "Yin", hn)
        self.m(hn.family, "Le", hn)

    def test_le_as_last_name_with_middle_initial(self) -> None:
        hn = parse("Yin a Le")
        self.m(hn.given, "Yin", hn)
        self.m(hn.middle, "a", hn)
        self.m(hn.family, "Le", hn)

    def test_conjunction_in_an_address_with_a_title(self) -> None:
        hn = parse("His Excellency Lord Duncan")
        self.m(hn.title, "His Excellency Lord", hn)
        self.m(hn.family, "Duncan", hn)

    def test_conjunction_in_an_address_with_a_first_name_title(self) -> None:
        hn = parse("Her Majesty Queen Elizabeth")
        self.m(hn.title, "Her Majesty Queen", hn)
        # if you want to be technical, Queen is in GIVEN_NAME_TITLES
        self.m(hn.given, "Elizabeth", hn)

    def test_name_is_conjunctions(self) -> None:
        hn = parse("e and e")
        self.m(hn.given, "e and e", hn)

    def test_conjunction_bridges_prefix_chain(self) -> None:
        # "von" and "zu" are both prefixes, but "und" between them is only a
        # conjunction. join_on_conjunctions() merges "von und zu" into one
        # piece before the prefix-joining step runs, so without registering
        # that merged piece as a prefix too, it's stranded in the middle name
        # instead of joining to the last name. See German nobility styles
        # like "von und zu".
        hn = parse("Alois von und zu Liechtenstein")
        self.m(hn.given, "Alois", hn)
        self.m(hn.middle, "", hn)
        self.m(hn.family, "von und zu Liechtenstein", hn)

    def test_conjunction_bridges_prefix_chain_with_leading_title(self) -> None:
        # Same bridging, but with extra prefix words on both sides of the
        # conjunction and a leading title-like word ("Freiherrin") that is
        # itself a prefix, confirming the chain still joins fully into last.
        hn = parse("Annette Charlotte Freiherrin von und zu der Tann-Rathsamhausen")
        self.m(hn.given, "Annette", hn)
        self.m(hn.middle, "Charlotte", hn)
        self.m(hn.family, "Freiherrin von und zu der Tann-Rathsamhausen", hn)

    def test_conjunction_prefix_merge_at_start_stays_first_name(self) -> None:
        # Guards the i == 0 branch of the same fix: when the conjunction is
        # merged with a following prefix at the very start of the name, the
        # existing leading-prefix rule (a lone prefix opening the name is
        # treated as part of the first name, not joined to last) must still
        # apply to the merged piece.
        hn = parse("and van Buren")
        self.m(hn.given, "and van", hn)
        self.m(hn.family, "Buren", hn)

    def test_conjunction_bridges_word_that_is_both_title_and_prefix(self) -> None:
        # "freiherr" is registered as both a title and a prefix. When it sits
        # next to a conjunction, join_on_conjunctions() runs the is_title and
        # is_prefix checks independently (not elif), so the merged piece
        # ("freiherr und") is added to both constants sets. Confirms that
        # dual registration doesn't break the prefix-bridging into last.
        hn = parse("Fritz Freiherr und von Bar")
        self.m(hn.given, "Fritz", hn)
        self.m(hn.middle, "", hn)
        self.m(hn.family, "Freiherr und von Bar", hn)

    def test_conjunction_bridges_prefix_chain_with_multiple_conjunctions(self) -> None:
        # Two separate conjunctions ("und" appearing twice, not contiguous)
        # each bridge their own pair of adjacent prefixes, so both merges
        # must register as prefixes for the whole chain to join into last.
        hn = parse("Alois von und zu und von Liechtenstein")
        self.m(hn.given, "Alois", hn)
        self.m(hn.middle, "", hn)
        self.m(hn.family, "von und zu und von Liechtenstein", hn)
