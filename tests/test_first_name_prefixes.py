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
