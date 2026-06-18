from nameparser import HumanName

from tests.base import HumanNameTestBase


class InitialsTestCase(HumanNameTestBase):
    def test_initials(self) -> None:
        hn = HumanName("Andrew Boris Petersen")
        self.m(hn.initials(), "A. B. P.", hn)

    def test_initials_simple_name(self) -> None:
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

    def test_initials_empty_part_with_none_default_not_literal_none(self) -> None:
        # Regression: when empty_attribute_default is None, an empty name part
        # used to be interpolated by str.format as the literal "None" (e.g.
        # "John Doe" -> "J. None D."). Empty parts must render as ''.
        hn = HumanName("John Doe", constants=None)
        hn.C.empty_attribute_default = None
        self.assertEqual(hn.initials(), "J. D.")
        self.assertTrue("None" not in hn.initials())

    def test_initials_all_empty_returns_empty_attribute_default(self) -> None:
        # Regression: a fully-empty result must fall back to
        # empty_attribute_default (here None), matching the first/last accessors,
        # rather than rendering the literal "None None None".
        hn = HumanName("", constants=None)
        hn.C.empty_attribute_default = None
        self.assertEqual(hn.initials(), None)

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
