from nameparser import HumanName
from nameparser.config import CONSTANTS

from tests.base import HumanNameTestBase


class FirstNamePrefixesTestCase(HumanNameTestBase):

    def test_default_set_contents(self) -> None:
        for word in ("abdul", "abdel", "abdal", "abu", "abou", "umm"):
            assert word in CONSTANTS.first_name_prefixes, f"{word!r} missing from first_name_prefixes"

    def test_is_first_name_prefix_true(self) -> None:
        hn = HumanName("test")
        assert hn.is_first_name_prefix("Abdul")

    def test_is_first_name_prefix_false(self) -> None:
        hn = HumanName("test")
        assert not hn.is_first_name_prefix("Ahmed")

    # --- no-comma: basic joining ---
    def test_no_comma_basic_join(self) -> None:
        hn = HumanName("abdul salam ahmed salem")
        self.m(hn.first, "abdul salam", hn)
        self.m(hn.middle, "ahmed", hn)
        self.m(hn.last, "salem", hn)

    def test_no_comma_three_tokens_no_middle(self) -> None:
        hn = HumanName("abdul salam salem")
        self.m(hn.first, "abdul salam", hn)
        self.m(hn.middle, "", hn)
        self.m(hn.last, "salem", hn)

    def test_no_comma_guard_two_tokens_no_join(self) -> None:
        """Guard: only last name remains after prefix → no join."""
        hn = HumanName("abdul salam")
        self.m(hn.first, "abdul", hn)
        self.m(hn.last, "salam", hn)
