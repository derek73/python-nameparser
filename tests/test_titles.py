import pytest

from nameparser import HumanName

from tests.base import HumanNameTestBase


class TitleTestCase(HumanNameTestBase):

    def test_last_name_is_also_title(self) -> None:
        hn = HumanName("Amy E Maid")
        self.m(hn.first, "Amy", hn)
        self.m(hn.middle, "E", hn)
        self.m(hn.last, "Maid", hn)

    def test_last_name_is_also_title_no_comma(self) -> None:
        hn = HumanName("Dr. Martin Luther King Jr.")
        self.m(hn.title, "Dr.", hn)
        self.m(hn.first, "Martin", hn)
        self.m(hn.middle, "Luther", hn)
        self.m(hn.last, "King", hn)
        self.m(hn.suffix, "Jr.", hn)

    def test_last_name_is_also_title_with_comma(self) -> None:
        hn = HumanName("Dr Martin Luther King, Jr.")
        self.m(hn.title, "Dr", hn)
        self.m(hn.first, "Martin", hn)
        self.m(hn.middle, "Luther", hn)
        self.m(hn.last, "King", hn)
        self.m(hn.suffix, "Jr.", hn)

    def test_last_name_is_also_title3(self) -> None:
        hn = HumanName("John King")
        self.m(hn.first, "John", hn)
        self.m(hn.last, "King", hn)

    def test_title_with_conjunction(self) -> None:
        hn = HumanName("Secretary of State Hillary Clinton")
        self.m(hn.title, "Secretary of State", hn)
        self.m(hn.first, "Hillary", hn)
        self.m(hn.last, "Clinton", hn)

    def test_compound_title_with_conjunction(self) -> None:
        hn = HumanName("Cardinal Secretary of State Hillary Clinton")
        self.m(hn.title, "Cardinal Secretary of State", hn)
        self.m(hn.first, "Hillary", hn)
        self.m(hn.last, "Clinton", hn)

    def test_title_is_title(self) -> None:
        hn = HumanName("Coach")
        self.m(hn.title, "Coach", hn)

    # TODO: fix handling of U.S.
    @pytest.mark.xfail
    def test_chained_title_first_name_title_is_initials(self) -> None:
        hn = HumanName("U.S. District Judge Marc Thomas Treadwell")
        self.m(hn.title, "U.S. District Judge", hn)
        self.m(hn.first, "Marc", hn)
        self.m(hn.middle, "Thomas", hn)
        self.m(hn.last, "Treadwell", hn)

    def test_conflict_with_chained_title_first_name_initial(self) -> None:
        hn = HumanName("U. S. Grant")
        self.m(hn.first, "U.", hn)
        self.m(hn.middle, "S.", hn)
        self.m(hn.last, "Grant", hn)

    def test_chained_title_first_name_initial_with_no_period(self) -> None:
        hn = HumanName("US Magistrate Judge T Michael Putnam")
        self.m(hn.title, "US Magistrate Judge", hn)
        self.m(hn.first, "T", hn)
        self.m(hn.middle, "Michael", hn)
        self.m(hn.last, "Putnam", hn)

    def test_chained_hyphenated_title(self) -> None:
        hn = HumanName("US Magistrate-Judge Elizabeth E Campbell")
        self.m(hn.title, "US Magistrate-Judge", hn)
        self.m(hn.first, "Elizabeth", hn)
        self.m(hn.middle, "E", hn)
        self.m(hn.last, "Campbell", hn)

    def test_chained_hyphenated_title_with_comma_suffix(self) -> None:
        hn = HumanName("Mag-Judge Harwell G Davis, III")
        self.m(hn.title, "Mag-Judge", hn)
        self.m(hn.first, "Harwell", hn)
        self.m(hn.middle, "G", hn)
        self.m(hn.last, "Davis", hn)
        self.m(hn.suffix, "III", hn)

    @pytest.mark.xfail
    def test_title_multiple_titles_with_apostrophe_s(self) -> None:
        hn = HumanName("The Right Hon. the President of the Queen's Bench Division")
        self.m(hn.title, "The Right Hon. the President of the Queen's Bench Division", hn)

    def test_title_starts_with_conjunction(self) -> None:
        hn = HumanName("The Rt Hon John Jones")
        self.m(hn.title, "The Rt Hon", hn)
        self.m(hn.first, "John", hn)
        self.m(hn.last, "Jones", hn)

    def test_conjunction_before_title(self) -> None:
        hn = HumanName('The Lord of the Universe')
        self.m(hn.title, "The Lord of the Universe", hn)

    def test_double_conjunction_on_title(self) -> None:
        hn = HumanName('Lord of the Universe')
        self.m(hn.title, "Lord of the Universe", hn)

    def test_triple_conjunction_on_title(self) -> None:
        hn = HumanName('Lord and of the Universe')
        self.m(hn.title, "Lord and of the Universe", hn)

    def test_multiple_conjunctions_on_multiple_titles(self) -> None:
        hn = HumanName('Lord of the Universe and Associate Supreme Queen of the World Lisa Simpson')
        self.m(hn.title, "Lord of the Universe and Associate Supreme Queen of the World", hn)
        self.m(hn.first, "Lisa", hn)
        self.m(hn.last, "Simpson", hn)

    def test_title_with_last_initial_is_suffix(self) -> None:
        hn = HumanName("King John V.")
        self.m(hn.title, "King", hn)
        self.m(hn.first, "John", hn)
        self.m(hn.last, "V.", hn)

    def test_initials_also_suffix(self) -> None:
        hn = HumanName("Smith, J.R.")
        self.m(hn.first, "J.R.", hn)
        # self.m(hn.middle, "R.", hn)
        self.m(hn.last, "Smith", hn)

    def test_two_title_parts_separated_by_periods(self) -> None:
        hn = HumanName("Lt.Gen. John A. Kenneth Doe IV")
        self.m(hn.title, "Lt.Gen.", hn)
        self.m(hn.first, "John", hn)
        self.m(hn.last, "Doe", hn)
        self.m(hn.middle, "A. Kenneth", hn)
        self.m(hn.suffix, "IV", hn)

    def test_two_part_title(self) -> None:
        hn = HumanName("Lt. Gen. John A. Kenneth Doe IV")
        self.m(hn.title, "Lt. Gen.", hn)
        self.m(hn.first, "John", hn)
        self.m(hn.last, "Doe", hn)
        self.m(hn.middle, "A. Kenneth", hn)
        self.m(hn.suffix, "IV", hn)

    def test_two_part_title_with_lastname_comma(self) -> None:
        hn = HumanName("Doe, Lt. Gen. John A. Kenneth IV")
        self.m(hn.title, "Lt. Gen.", hn)
        self.m(hn.first, "John", hn)
        self.m(hn.last, "Doe", hn)
        self.m(hn.middle, "A. Kenneth", hn)
        self.m(hn.suffix, "IV", hn)

    def test_two_part_title_with_suffix_comma(self) -> None:
        hn = HumanName("Lt. Gen. John A. Kenneth Doe, Jr.")
        self.m(hn.title, "Lt. Gen.", hn)
        self.m(hn.first, "John", hn)
        self.m(hn.last, "Doe", hn)
        self.m(hn.middle, "A. Kenneth", hn)
        self.m(hn.suffix, "Jr.", hn)

    def test_possible_conflict_with_middle_initial_that_could_be_suffix(self) -> None:
        hn = HumanName("Doe, Rev. John V, Jr.")
        self.m(hn.title, "Rev.", hn)
        self.m(hn.first, "John", hn)
        self.m(hn.last, "Doe", hn)
        self.m(hn.middle, "V", hn)
        self.m(hn.suffix, "Jr.", hn)

    def test_possible_conflict_with_suffix_that_could_be_initial(self) -> None:
        hn = HumanName("Doe, Rev. John A., V, Jr.")
        self.m(hn.title, "Rev.", hn)
        self.m(hn.first, "John", hn)
        self.m(hn.last, "Doe", hn)
        self.m(hn.middle, "A.", hn)
        self.m(hn.suffix, "V, Jr.", hn)

    # 'ben' is removed from PREFIXES in v0.2.5
    # this test could re-enable this test if we decide to support 'ben' as a prefix
    @pytest.mark.xfail
    def test_ben_as_conjunction(self) -> None:
        hn = HumanName("Ahmad ben Husain")
        self.m(hn.first, "Ahmad", hn)
        self.m(hn.last, "ben Husain", hn)

    def test_ben_as_first_name(self) -> None:
        hn = HumanName("Ben Johnson")
        self.m(hn.first, "Ben", hn)
        self.m(hn.last, "Johnson", hn)

    def test_ben_as_first_name_with_middle_name(self) -> None:
        hn = HumanName("Ben Alex Johnson")
        self.m(hn.first, "Ben", hn)
        self.m(hn.middle, "Alex", hn)
        self.m(hn.last, "Johnson", hn)

    def test_ben_as_middle_name(self) -> None:
        hn = HumanName("Alex Ben Johnson")
        self.m(hn.first, "Alex", hn)
        self.m(hn.middle, "Ben", hn)
        self.m(hn.last, "Johnson", hn)

    # http://code.google.com/p/python-nameparser/issues/detail?id=13
    def test_last_name_also_prefix(self) -> None:
        hn = HumanName("Jane Doctor")
        self.m(hn.first, "Jane", hn)
        self.m(hn.last, "Doctor", hn)

    def test_title_with_periods(self) -> None:
        hn = HumanName("Lt.Gov. John Doe")
        self.m(hn.title, "Lt.Gov.", hn)
        self.m(hn.first, "John", hn)
        self.m(hn.last, "Doe", hn)

    def test_title_with_periods_lastname_comma(self) -> None:
        hn = HumanName("Doe, Lt.Gov. John")
        self.m(hn.title, "Lt.Gov.", hn)
        self.m(hn.first, "John", hn)
        self.m(hn.last, "Doe", hn)

    def test_mac_with_spaces(self) -> None:
        hn = HumanName("Jane Mac Beth")
        self.m(hn.first, "Jane", hn)
        self.m(hn.last, "Mac Beth", hn)

    def test_mac_as_first_name(self) -> None:
        hn = HumanName("Mac Miller")
        self.m(hn.first, "Mac", hn)
        self.m(hn.last, "Miller", hn)

    def test_multiple_prefixes(self) -> None:
        hn = HumanName("Mike van der Velt")
        self.m(hn.first, "Mike", hn)
        self.m(hn.last, "van der Velt", hn)

    def test_2_same_prefixes_in_the_name(self) -> None:
        hh = HumanName("Vincent van Gogh van Beethoven")
        self.m(hh.first, "Vincent", hh)
        self.m(hh.middle, "van Gogh", hh)
        self.m(hh.last, "van Beethoven", hh)

    # Non-ASCII title normalization — confirm diacritic titles survive
    # the lowercase lookup path end-to-end.

    def test_señora_non_ascii_title(self) -> None:
        hn = HumanName("Señora María García")
        self.m(hn.title, "Señora", hn)
        self.m(hn.first, "María", hn)
        self.m(hn.last, "García", hn)

    def test_señora_lowercase_non_ascii_title(self) -> None:
        hn = HumanName("señora María García")
        self.m(hn.title, "señora", hn)
        self.m(hn.first, "María", hn)
        self.m(hn.last, "García", hn)

    def test_frøken_non_ascii_title(self) -> None:
        hn = HumanName("Frøken Jensen")
        self.m(hn.title, "Frøken", hn)
        self.m(hn.first, "", hn)
        self.m(hn.last, "Jensen", hn)

    def test_herr_title_not_first_name(self) -> None:
        hn = HumanName("Herr Schmidt")
        self.m(hn.title, "Herr", hn)
        self.m(hn.first, "", hn)
        self.m(hn.last, "Schmidt", hn)

    def test_herr_title_with_first_name(self) -> None:
        hn = HumanName("Herr Klaus Schmidt")
        self.m(hn.title, "Herr", hn)
        self.m(hn.first, "Klaus", hn)
        self.m(hn.last, "Schmidt", hn)
