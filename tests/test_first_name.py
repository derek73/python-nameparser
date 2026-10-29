from nameparser import parse

from tests.base import ParsedNameTestBase


class FirstNameHandlingTests(ParsedNameTestBase):
    def test_first_name(self) -> None:
        hn = parse("Andrew")
        self.m(hn.given, "Andrew", hn)

    def test_assume_title_and_one_other_name_is_last_name(self) -> None:
        hn = parse("Rev Andrews")
        self.m(hn.title, "Rev", hn)
        self.m(hn.family, "Andrews", hn)

    def test_assume_suffix_title_and_one_other_name_is_last_name(self) -> None:
        # xfail in v1 (which parsed first='M.D.'); 2.0's family-comma
        # suffix peel routes the post-comma suffix piece to suffix and
        # keeps the pre-comma piece in last, so the long-desired
        # expectation now holds. 2.0: fix(comma-family/suffix-routing).
        hn = parse("Andrews, M.D.")
        self.m(hn.suffix, "M.D.", hn)
        self.m(hn.family, "Andrews", hn)

    def test_suffix_in_lastname_part_of_lastname_comma_format(self) -> None:
        hn = parse("Smith Jr., John")
        self.m(hn.family, "Smith", hn)
        self.m(hn.given, "John", hn)
        self.m(hn.suffix, "Jr.", hn)

    def test_sir_exception_to_first_name_rule(self) -> None:
        hn = parse("Sir Gerald")
        self.m(hn.title, "Sir", hn)
        self.m(hn.given, "Gerald", hn)

    def test_pope_exception_to_first_name_rule(self) -> None:
        hn = parse("Pope Francis")
        self.m(hn.title, "Pope", hn)
        self.m(hn.given, "Francis", hn)

    def test_king_is_a_first_name_outside_a_title_phrase(self) -> None:
        # #752 phase 2j: 'king' is a title only inside a title phrase
        hn = parse("King Henry")
        self.m(hn.given, "King", hn)
        self.m(hn.family, "Henry", hn)
        hn = parse("His Majesty King Henry")
        self.m(hn.title, "His Majesty King", hn)
        self.m(hn.given, "Henry", hn)

    def test_queen_is_a_first_name_outside_a_title_phrase(self) -> None:
        # #913: 'queen' is a title only inside a title phrase
        hn = parse("Queen Latifah")
        self.m(hn.given, "Queen", hn)
        self.m(hn.family, "Latifah", hn)
        hn = parse("Her Majesty Queen Elizabeth")
        self.m(hn.title, "Her Majesty Queen", hn)
        self.m(hn.given, "Elizabeth", hn)

    def test_dame_exception_to_first_name_rule(self) -> None:
        hn = parse("Dame Mary")
        self.m(hn.title, "Dame", hn)
        self.m(hn.given, "Mary", hn)

    def test_first_name_is_not_prefix_if_only_two_parts(self) -> None:
        """When there are only two parts, don't join prefixes or conjunctions"""
        hn = parse("Van Nguyen")
        self.m(hn.given, "Van", hn)
        self.m(hn.family, "Nguyen", hn)

    def test_first_name_is_not_prefix_if_only_two_parts_comma(self) -> None:
        hn = parse("Nguyen, Van")
        self.m(hn.given, "Van", hn)
        self.m(hn.family, "Nguyen", hn)

    def test_first_name_is_prefix_if_three_parts(self) -> None:
        """Fixed in 2.2 (#367) by making titles transparent to the
        leading-particle exception. This carried v1's ``xfail`` and the
        docstring "Not sure how to fix this without breaking Mr and
        Mrs" for the whole life of the 1.x line -- the exception was
        keyed on piece index 0, so any title displaced the particle and
        the prefix chain fired, giving last='Van Nguyen'. It is keyed on
        the first piece that is not a title OR is a particle -- not the
        naive "first piece that is not a title", which collapses
        'St John Smith' into one given name and broke the title-
        customization tests (now tests/test_constants.py's
        LexiconCustomizationTests), 15 failures in all on the 2.x
        suite. The Mr/Mrs conclusion
        holds under either rule, which is why the Mr/Mrs shapes are
        asserted here rather than only asserted about: a bare 'Mr./Mrs. Surname'
        has no particle to displace, so nothing about it reaches the
        rule that moved. v1's concern was about the fix it had in mind,
        not about this one."""
        hn = parse("Mr. Van Nguyen")
        self.m(hn.given, "Van", hn)
        self.m(hn.family, "Nguyen", hn)
        for text, last in [("Mr. Smith", "Smith"), ("Mrs. Smith", "Smith"),
                           ("Mr. Nguyen", "Nguyen")]:
            titled = parse(text)
            self.m(titled.given, "", titled)
            self.m(titled.family, last, titled)
        titled = parse("Mr. John Smith")
        self.m(titled.given, "John", titled)
        self.m(titled.family, "Smith", titled)
