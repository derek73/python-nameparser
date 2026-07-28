import pytest

from nameparser import HumanName

from tests.base import HumanNameTestBase


class FirstNameHandlingTests(HumanNameTestBase):
    def test_first_name(self) -> None:
        hn = HumanName("Andrew")
        self.m(hn.first, "Andrew", hn)

    def test_assume_title_and_one_other_name_is_last_name(self) -> None:
        hn = HumanName("Rev Andrews")
        self.m(hn.title, "Rev", hn)
        self.m(hn.last, "Andrews", hn)

    def test_assume_suffix_title_and_one_other_name_is_last_name(self) -> None:
        # xfail in v1 (which parsed first='M.D.'); 2.0's family-comma
        # suffix peel routes the post-comma suffix piece to suffix and
        # keeps the pre-comma piece in last, so the long-desired
        # expectation now holds. 2.0: fix(comma-family/suffix-routing).
        hn = HumanName("Andrews, M.D.")
        self.m(hn.suffix, "M.D.", hn)
        self.m(hn.last, "Andrews", hn)

    def test_suffix_in_lastname_part_of_lastname_comma_format(self) -> None:
        hn = HumanName("Smith Jr., John")
        self.m(hn.last, "Smith", hn)
        self.m(hn.first, "John", hn)
        self.m(hn.suffix, "Jr.", hn)

    def test_sir_exception_to_first_name_rule(self) -> None:
        hn = HumanName("Sir Gerald")
        self.m(hn.title, "Sir", hn)
        self.m(hn.first, "Gerald", hn)

    def test_king_exception_to_first_name_rule(self) -> None:
        hn = HumanName("King Henry")
        self.m(hn.title, "King", hn)
        self.m(hn.first, "Henry", hn)

    def test_queen_exception_to_first_name_rule(self) -> None:
        hn = HumanName("Queen Elizabeth")
        self.m(hn.title, "Queen", hn)
        self.m(hn.first, "Elizabeth", hn)

    def test_dame_exception_to_first_name_rule(self) -> None:
        hn = HumanName("Dame Mary")
        self.m(hn.title, "Dame", hn)
        self.m(hn.first, "Mary", hn)

    def test_first_name_is_not_prefix_if_only_two_parts(self) -> None:
        """When there are only two parts, don't join prefixes or conjunctions"""
        hn = HumanName("Van Nguyen")
        self.m(hn.first, "Van", hn)
        self.m(hn.last, "Nguyen", hn)

    def test_first_name_is_not_prefix_if_only_two_parts_comma(self) -> None:
        hn = HumanName("Nguyen, Van")
        self.m(hn.first, "Van", hn)
        self.m(hn.last, "Nguyen", hn)

    @pytest.mark.xfail
    def test_first_name_is_prefix_if_three_parts(self) -> None:
        """Not sure how to fix this without breaking Mr and Mrs"""
        hn = HumanName("Mr. Van Nguyen")
        self.m(hn.first, "Van", hn)
        self.m(hn.last, "Nguyen", hn)
