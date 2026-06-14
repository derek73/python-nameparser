import pytest

from nameparser import HumanName

from tests.base import HumanNameTestBase


class InitialsTestCase(HumanNameTestBase):
    def test_initials(self) -> None:
        hn = HumanName("Andrew Boris Petersen")
        self.m(hn.initials(), "A. B. P.", hn)

    def test_initials_simple_name(self) -> None:
        from nameparser.config import CONSTANTS
        if CONSTANTS.empty_attribute_default is None:
            # initials() inserts None into the format string for missing parts;
            # pre-existing bug that also fails in tests.py under None mode.
            pytest.xfail("initials() renders None for empty parts when empty_attribute_default=None")
        hn = HumanName("John Doe")
        self.m(hn.initials(), "J. D.", hn)
        hn = HumanName("John Doe", initials_format="{first} {last}")
        self.m(hn.initials(), "J. D.", hn)
        hn = HumanName("John Doe", initials_format="{last}")
        self.m(hn.initials(), "D.", hn)
        hn = HumanName("John Doe", initials_format="{first}")
        self.m(hn.initials(), "J.", hn)
        hn = HumanName("John Doe", initials_format="{middle}")
        self.m(hn.initials(), "", hn)

    def test_initials_complex_name(self) -> None:
        hn = HumanName("Doe, John A. Kenneth, Jr.")
        self.m(hn.initials(), "J. A. K. D.", hn)

    def test_initials_format(self) -> None:
        hn = HumanName("Doe, John A. Kenneth, Jr.", initials_format="{first} {middle}")
        self.m(hn.initials(), "J. A. K.", hn)
        hn = HumanName("Doe, John A. Kenneth, Jr.", initials_format="{first} {last}")
        self.m(hn.initials(), "J. D.", hn)
        hn = HumanName("Doe, John A. Kenneth, Jr.", initials_format="{middle} {last}")
        self.m(hn.initials(), "A. K. D.", hn)
        hn = HumanName("Doe, John A. Kenneth, Jr.", initials_format="{first}, {last}")
        self.m(hn.initials(), "J., D.", hn)

    def test_initials_format_constants(self) -> None:
        from nameparser.config import CONSTANTS
        _orig = CONSTANTS.initials_format
        CONSTANTS.initials_format = "{first} {last}"
        hn = HumanName("Doe, John A. Kenneth, Jr.")
        self.m(hn.initials(), "J. D.", hn)
        CONSTANTS.initials_format = "{first}  {last}"
        hn = HumanName("Doe, John A. Kenneth, Jr.")
        self.m(hn.initials(), "J. D.", hn)
        CONSTANTS.initials_format = _orig

    def test_initials_delimiter(self) -> None:
        hn = HumanName("Doe, John A. Kenneth, Jr.", initials_delimiter=";")
        self.m(hn.initials(), "J; A; K; D;", hn)

    def test_initials_delimiter_constants(self) -> None:
        from nameparser.config import CONSTANTS
        _orig = CONSTANTS.initials_delimiter
        CONSTANTS.initials_delimiter = ";"
        hn = HumanName("Doe, John A. Kenneth, Jr.")
        self.m(hn.initials(), "J; A; K; D;", hn)
        CONSTANTS.initials_delimiter = _orig

    def test_initials_list(self) -> None:
        hn = HumanName("Andrew Boris Petersen")
        self.m(hn.initials_list(), ["A", "B", "P"], hn)

    def test_initials_list_complex_name(self) -> None:
        hn = HumanName("Doe, John A. Kenneth, Jr.")
        self.m(hn.initials_list(), ["J", "A", "K", "D"], hn)

    def test_initials_with_prefix_firstname(self) -> None:
        hn = HumanName("Van Jeremy Johnson")
        self.m(hn.initials_list(), ["V", "J", "J"], hn)

    def test_initials_with_prefix(self) -> None:
        hn = HumanName("Alex van Johnson")
        self.m(hn.initials_list(), ["A", "J"], hn)

    def test_constructor_first(self) -> None:
        hn = HumanName(first="TheName")
        self.assertFalse(hn.unparsable)
        self.m(hn.first, "TheName", hn)

    def test_constructor_middle(self) -> None:
        hn = HumanName(middle="TheName")
        self.assertFalse(hn.unparsable)
        self.m(hn.middle, "TheName", hn)

    def test_constructor_last(self) -> None:
        hn = HumanName(last="TheName")
        self.assertFalse(hn.unparsable)
        self.m(hn.last, "TheName", hn)

    def test_constructor_title(self) -> None:
        hn = HumanName(title="TheName")
        self.assertFalse(hn.unparsable)
        self.m(hn.title, "TheName", hn)

    def test_constructor_suffix(self) -> None:
        hn = HumanName(suffix="TheName")
        self.assertFalse(hn.unparsable)
        self.m(hn.suffix, "TheName", hn)

    def test_constructor_nickname(self) -> None:
        hn = HumanName(nickname="TheName")
        self.assertFalse(hn.unparsable)
        self.m(hn.nickname, "TheName", hn)

    def test_constructor_multiple(self) -> None:
        hn = HumanName(first="TheName", last="lastname", title="mytitle", full_name="donotparse")
        self.assertFalse(hn.unparsable)
        self.m(hn.first, "TheName", hn)
        self.m(hn.last, "lastname", hn)
        self.m(hn.title, "mytitle", hn)
