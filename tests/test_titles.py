import pytest

from nameparser import parse

from tests.base import ParsedNameTestBase


class TitleTestCase(ParsedNameTestBase):

    def test_last_name_is_also_title(self) -> None:
        hn = parse("Amy E Maid")
        self.m(hn.given, "Amy", hn)
        self.m(hn.middle, "E", hn)
        self.m(hn.family, "Maid", hn)

    def test_last_name_is_also_title_no_comma(self) -> None:
        hn = parse("Dr. Martin Luther King Jr.")
        self.m(hn.title, "Dr.", hn)
        self.m(hn.given, "Martin", hn)
        self.m(hn.middle, "Luther", hn)
        self.m(hn.family, "King", hn)
        self.m(hn.suffix, "Jr.", hn)

    def test_last_name_is_also_title_with_comma(self) -> None:
        hn = parse("Dr Martin Luther King, Jr.")
        self.m(hn.title, "Dr", hn)
        self.m(hn.given, "Martin", hn)
        self.m(hn.middle, "Luther", hn)
        self.m(hn.family, "King", hn)
        self.m(hn.suffix, "Jr.", hn)

    def test_leading_period_abbreviation_is_title(self) -> None:
        hn = parse("Major. Dona Smith")
        self.m(hn.title, "Major.", hn)
        self.m(hn.given, "Dona", hn)
        self.m(hn.family, "Smith", hn)

    def test_last_name_is_also_title3(self) -> None:
        hn = parse("John Pope")
        self.m(hn.given, "John", hn)
        self.m(hn.family, "Pope", hn)

    def test_title_with_conjunction(self) -> None:
        hn = parse("Secretary of State Hillary Clinton")
        self.m(hn.title, "Secretary of State", hn)
        self.m(hn.given, "Hillary", hn)
        self.m(hn.family, "Clinton", hn)

    def test_compound_title_with_conjunction(self) -> None:
        hn = parse("Cardinal Secretary of State Hillary Clinton")
        self.m(hn.title, "Cardinal Secretary of State", hn)
        self.m(hn.given, "Hillary", hn)
        self.m(hn.family, "Clinton", hn)

    def test_title_is_title(self) -> None:
        hn = parse("Coach")
        self.m(hn.title, "Coach", hn)

    # TODO: fix handling of U.S. -- 2.0 matches v1 here: lc()-style
    # normalization keeps 'u.s' out of the titles vocabulary, so the
    # chain never starts (an interim 2.0 build that stripped interior
    # periods made this pass, but that normalization wrongly turned
    # 'J.R.' into the title 'jr'; v1 parity won)
    @pytest.mark.xfail(reason="#490")
    def test_chained_title_first_name_title_is_initials(self) -> None:
        hn = parse("U.S. District Judge Marc Thomas Treadwell")
        self.m(hn.title, "U.S. District Judge", hn)
        self.m(hn.given, "Marc", hn)
        self.m(hn.middle, "Thomas", hn)
        self.m(hn.family, "Treadwell", hn)

    def test_conflict_with_chained_title_first_name_initial(self) -> None:
        hn = parse("U. S. Grant")
        self.m(hn.given, "U.", hn)
        self.m(hn.middle, "S.", hn)
        self.m(hn.family, "Grant", hn)

    def test_chained_title_first_name_initial_with_no_period(self) -> None:
        hn = parse("US Magistrate Judge T Michael Putnam")
        self.m(hn.title, "US Magistrate Judge", hn)
        self.m(hn.given, "T", hn)
        self.m(hn.middle, "Michael", hn)
        self.m(hn.family, "Putnam", hn)

    def test_chained_hyphenated_title(self) -> None:
        hn = parse("US Magistrate-Judge Elizabeth E Campbell")
        self.m(hn.title, "US Magistrate-Judge", hn)
        self.m(hn.given, "Elizabeth", hn)
        self.m(hn.middle, "E", hn)
        self.m(hn.family, "Campbell", hn)

    def test_chained_hyphenated_title_with_comma_suffix(self) -> None:
        hn = parse("Mag-Judge Harwell G Davis, III")
        self.m(hn.title, "Mag-Judge", hn)
        self.m(hn.given, "Harwell", hn)
        self.m(hn.middle, "G", hn)
        self.m(hn.family, "Davis", hn)
        self.m(hn.suffix, "III", hn)

    def test_title_multiple_titles_with_apostrophe_s(self) -> None:
        # v1 aspired to read the whole string as one title, and shipped this
        # as an xfail.
        # NOT FIXED, decided 2026-09-01 (v1-xfail triage,
        # decisions/v1-xfail-triage): this is a name parser, not a title
        # parser. Handed an input that is all titles, it assumes the last
        # title-word is the name, so 'Division' becomes the family. Accepted
        # convention rather than a defect; #491 tracks reporting the guess.
        hn = parse("The Right Hon. the President of the Queen's Bench Division")
        self.m(hn.title, "The Right Hon. the President of the Queen's Bench", hn)
        self.m(hn.given, "", hn)
        self.m(hn.middle, "", hn)
        self.m(hn.family, "Division", hn)
        self.m(hn.suffix, "", hn)

    def test_title_starts_with_conjunction(self) -> None:
        hn = parse("The Rt Hon John Jones")
        self.m(hn.title, "The Rt Hon", hn)
        self.m(hn.given, "John", hn)
        self.m(hn.family, "Jones", hn)

    def test_conjunction_before_title(self) -> None:
        hn = parse('The Lord of the Universe')
        self.m(hn.title, "The Lord of the Universe", hn)

    def test_double_conjunction_on_title(self) -> None:
        hn = parse('Lord of the Universe')
        self.m(hn.title, "Lord of the Universe", hn)

    def test_triple_conjunction_on_title(self) -> None:
        hn = parse('Lord and of the Universe')
        self.m(hn.title, "Lord and of the Universe", hn)

    def test_multiple_conjunctions_on_multiple_titles(self) -> None:
        hn = parse('Lord of the Universe and Associate Supreme Queen of the World Lisa Simpson')
        self.m(hn.title, "Lord of the Universe and Associate Supreme Queen of the World", hn)
        self.m(hn.given, "Lisa", hn)
        self.m(hn.family, "Simpson", hn)

    def test_title_with_last_initial_is_suffix(self) -> None:
        hn = parse("Pope John V.")
        self.m(hn.title, "Pope", hn)
        self.m(hn.given, "John", hn)
        self.m(hn.family, "V.", hn)

    def test_initials_also_suffix(self) -> None:
        hn = parse("Smith, J.R.")
        self.m(hn.given, "J.R.", hn)
        # self.m(hn.middle, "R.", hn)
        self.m(hn.family, "Smith", hn)

    def test_two_title_parts_separated_by_periods(self) -> None:
        hn = parse("Lt.Gen. John A. Kenneth Doe IV")
        self.m(hn.title, "Lt.Gen.", hn)
        self.m(hn.given, "John", hn)
        self.m(hn.family, "Doe", hn)
        self.m(hn.middle, "A. Kenneth", hn)
        self.m(hn.suffix, "IV", hn)

    def test_two_part_title(self) -> None:
        hn = parse("Lt. Gen. John A. Kenneth Doe IV")
        self.m(hn.title, "Lt. Gen.", hn)
        self.m(hn.given, "John", hn)
        self.m(hn.family, "Doe", hn)
        self.m(hn.middle, "A. Kenneth", hn)
        self.m(hn.suffix, "IV", hn)

    def test_two_part_title_with_lastname_comma(self) -> None:
        hn = parse("Doe, Lt. Gen. John A. Kenneth IV")
        self.m(hn.title, "Lt. Gen.", hn)
        self.m(hn.given, "John", hn)
        self.m(hn.family, "Doe", hn)
        self.m(hn.middle, "A. Kenneth", hn)
        self.m(hn.suffix, "IV", hn)

    def test_two_part_title_with_suffix_comma(self) -> None:
        hn = parse("Lt. Gen. John A. Kenneth Doe, Jr.")
        self.m(hn.title, "Lt. Gen.", hn)
        self.m(hn.given, "John", hn)
        self.m(hn.family, "Doe", hn)
        self.m(hn.middle, "A. Kenneth", hn)
        self.m(hn.suffix, "Jr.", hn)

    def test_possible_conflict_with_middle_initial_that_could_be_suffix(self) -> None:
        hn = parse("Doe, Rev. John V, Jr.")
        self.m(hn.title, "Rev.", hn)
        self.m(hn.given, "John", hn)
        self.m(hn.family, "Doe", hn)
        self.m(hn.middle, "V", hn)
        self.m(hn.suffix, "Jr.", hn)

    def test_possible_conflict_with_suffix_that_could_be_initial(self) -> None:
        hn = parse("Doe, Rev. John A., V, Jr.")
        self.m(hn.title, "Rev.", hn)
        self.m(hn.given, "John", hn)
        self.m(hn.family, "Doe", hn)
        self.m(hn.middle, "A.", hn)
        self.m(hn.suffix, "V, Jr.", hn)

    # 'ben' was removed from the particle set (then PREFIXES) in v0.2.5
    def test_ben_is_not_a_particle(self) -> None:
        # v1 aspired to read 'ben' as a particle joining the family
        # ("ben Husain"), and shipped this as an xfail.
        # NOT FIXED, decided 2026-09-01 (v1-xfail triage,
        # decisions/v1-xfail-triage): the question was already settled in
        # v0.2.5, when 'ben' was removed from the prefixes. 'ben' collides with
        # the given name Ben, which is the same criterion
        # (decisions/vocabulary-collisions) that keeps it out today.
        # test_ben_as_first_name below is the collision it protects.
        hn = parse("Ahmad ben Husain")
        self.m(hn.title, "", hn)
        self.m(hn.given, "Ahmad", hn)
        self.m(hn.middle, "ben", hn)
        self.m(hn.family, "Husain", hn)
        self.m(hn.suffix, "", hn)

    def test_ben_as_first_name(self) -> None:
        hn = parse("Ben Johnson")
        self.m(hn.given, "Ben", hn)
        self.m(hn.family, "Johnson", hn)

    def test_ben_as_first_name_with_middle_name(self) -> None:
        hn = parse("Ben Alex Johnson")
        self.m(hn.given, "Ben", hn)
        self.m(hn.middle, "Alex", hn)
        self.m(hn.family, "Johnson", hn)

    def test_ben_as_middle_name(self) -> None:
        hn = parse("Alex Ben Johnson")
        self.m(hn.given, "Alex", hn)
        self.m(hn.middle, "Ben", hn)
        self.m(hn.family, "Johnson", hn)

    # http://code.google.com/p/python-nameparser/issues/detail?id=13
    def test_last_name_also_prefix(self) -> None:
        hn = parse("Jane Doctor")
        self.m(hn.given, "Jane", hn)
        self.m(hn.family, "Doctor", hn)

    def test_title_with_periods(self) -> None:
        hn = parse("Lt.Gov. John Doe")
        self.m(hn.title, "Lt.Gov.", hn)
        self.m(hn.given, "John", hn)
        self.m(hn.family, "Doe", hn)

    def test_title_with_periods_lastname_comma(self) -> None:
        hn = parse("Doe, Lt.Gov. John")
        self.m(hn.title, "Lt.Gov.", hn)
        self.m(hn.given, "John", hn)
        self.m(hn.family, "Doe", hn)

    def test_title_with_periods_and_single_letter_middle_name(self) -> None:
        # A derived title ("Lt.Gov.") must be excluded from the rootname
        # count that join_on_conjunctions() uses for its single-letter
        # conjunction heuristic. If is_rootname() misses the derived titles,
        # the count reaches 4 and "e" is treated as a conjunction, joining
        # "juan e garcia" into a single last-name piece with no first name.
        hn = parse("Lt.Gov. juan e garcia")
        self.m(hn.title, "Lt.Gov.", hn)
        self.m(hn.given, "juan", hn)
        self.m(hn.middle, "e", hn)
        self.m(hn.family, "garcia", hn)

    def test_mac_with_spaces(self) -> None:
        hn = parse("Jane Mac Beth")
        self.m(hn.given, "Jane", hn)
        self.m(hn.family, "Mac Beth", hn)

    def test_mac_as_first_name(self) -> None:
        hn = parse("Mac Miller")
        self.m(hn.given, "Mac", hn)
        self.m(hn.family, "Miller", hn)

    def test_multiple_prefixes(self) -> None:
        hn = parse("Mike van der Velt")
        self.m(hn.given, "Mike", hn)
        self.m(hn.family, "van der Velt", hn)

    def test_2_same_prefixes_in_the_name(self) -> None:
        hh = parse("Vincent van Gogh van Beethoven")
        self.m(hh.given, "Vincent", hh)
        self.m(hh.middle, "van Gogh", hh)
        self.m(hh.family, "van Beethoven", hh)

    # Non-ASCII title normalization — confirm diacritic titles survive
    # the lowercase lookup path end-to-end.

    def test_señora_non_ascii_title(self) -> None:
        hn = parse("Señora María García")
        self.m(hn.title, "Señora", hn)
        self.m(hn.given, "María", hn)
        self.m(hn.family, "García", hn)

    def test_señora_lowercase_non_ascii_title(self) -> None:
        hn = parse("señora María García")
        self.m(hn.title, "señora", hn)
        self.m(hn.given, "María", hn)
        self.m(hn.family, "García", hn)

    def test_frøken_non_ascii_title(self) -> None:
        hn = parse("Frøken Jensen")
        self.m(hn.title, "Frøken", hn)
        self.m(hn.given, "", hn)
        self.m(hn.family, "Jensen", hn)

    def test_herr_title_not_first_name(self) -> None:
        hn = parse("Herr Schmidt")
        self.m(hn.title, "Herr", hn)
        self.m(hn.given, "", hn)
        self.m(hn.family, "Schmidt", hn)

    def test_herr_title_with_first_name(self) -> None:
        hn = parse("Herr Klaus Schmidt")
        self.m(hn.title, "Herr", hn)
        self.m(hn.given, "Klaus", hn)
        self.m(hn.family, "Schmidt", hn)

    def test_leading_period_abbreviation_suffix_comma(self) -> None:
        hn = parse("Major. John Smith, Jr.")
        self.m(hn.title, "Major.", hn)
        self.m(hn.given, "John", hn)
        self.m(hn.family, "Smith", hn)
        self.m(hn.suffix, "Jr.", hn)

    def test_leading_period_abbreviation_lastname_comma(self) -> None:
        hn = parse("Smith, Major. John")
        self.m(hn.title, "Major.", hn)
        self.m(hn.given, "John", hn)
        self.m(hn.family, "Smith", hn)

    def test_leading_period_abbreviation_unknown_word(self) -> None:
        hn = parse("Foo. John Smith")
        self.m(hn.title, "Foo.", hn)
        self.m(hn.given, "John", hn)
        self.m(hn.family, "Smith", hn)

    def test_leading_period_abbreviation_chained(self) -> None:
        hn = parse("Foo. Xyz. John Smith")
        self.m(hn.title, "Foo. Xyz.", hn)
        self.m(hn.given, "John", hn)
        self.m(hn.family, "Smith", hn)

    def test_leading_single_letter_initial_excluded(self) -> None:
        hn = parse("J. Smith")
        self.m(hn.given, "J.", hn)
        self.m(hn.family, "Smith", hn)
        self.m(hn.title, "", hn)

    def test_leading_internal_period_abbreviation_excluded(self) -> None:
        hn = parse("E.T. Smith")
        self.m(hn.given, "E.T.", hn)
        self.m(hn.family, "Smith", hn)
        self.m(hn.title, "", hn)

    def test_period_abbreviation_after_first_name_stays_middle(self) -> None:
        hn = parse("John Major. Smith")
        self.m(hn.given, "John", hn)
        self.m(hn.middle, "Major.", hn)
        self.m(hn.family, "Smith", hn)
        self.m(hn.title, "", hn)

    def test_known_title_with_period_still_a_title(self) -> None:
        hn = parse("Dr. John Smith")
        self.m(hn.title, "Dr.", hn)
        self.m(hn.given, "John", hn)
        self.m(hn.family, "Smith", hn)

    def test_middle_initial_with_period_unaffected(self) -> None:
        hn = parse("John Q. Smith")
        self.m(hn.given, "John", hn)
        self.m(hn.middle, "Q.", hn)
        self.m(hn.family, "Smith", hn)

    def test_leading_period_abbreviation_excludes_digits(self) -> None:
        hn = parse("No1. John Smith")
        self.m(hn.title, "", hn)
        self.m(hn.given, "No1.", hn)
        self.m(hn.family, "Smith", hn)

    def test_leading_period_abbreviation_excludes_apostrophe(self) -> None:
        hn = parse("O'B. John Smith")
        self.m(hn.title, "", hn)
        self.m(hn.given, "O'B.", hn)
        self.m(hn.family, "Smith", hn)

    def test_leading_period_abbreviation_case_insensitive(self) -> None:
        hn = parse("xyz. John Smith")
        self.m(hn.title, "xyz.", hn)
        self.m(hn.given, "John", hn)
        self.m(hn.family, "Smith", hn)

    def test_leading_period_abbreviation_with_nickname(self) -> None:
        hn = parse("Xyz. (Bud) Smith")
        self.m(hn.title, "Xyz.", hn)
        self.m(hn.given, "", hn)
        self.m(hn.family, "Smith", hn)
        self.m(hn.nickname, "Bud", hn)

    def test_charge_daffaires_chains_as_title(self) -> None:
        hn = parse("Chargé d'Affaires John Smith")
        self.m(hn.title, "Chargé d'Affaires", hn)
        self.m(hn.given, "John", hn)
        self.m(hn.family, "Smith", hn)

    def test_unaccented_charge_daffaires_chains_as_title(self) -> None:
        # both spellings ship, like attaché/attache
        hn = parse("Charge d'Affaires John Smith")
        self.m(hn.title, "Charge d'Affaires", hn)
        self.m(hn.given, "John", hn)
        self.m(hn.family, "Smith", hn)
