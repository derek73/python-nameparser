from nameparser.config import CONSTANTS

from tests.base import HumanNameTestBase


class FirstNamePrefixesTestCase(HumanNameTestBase):

    def test_default_set_contents(self) -> None:
        for word in ("abdul", "abdel", "abdal", "abu", "abou", "umm"):
            assert word in CONSTANTS.first_name_prefixes, f"{word!r} missing from first_name_prefixes"
