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
        CONSTANTS.initials_format = "{first} {last}"
        hn = HumanName("Doe, John A. Kenneth, Jr.")
        self.m(hn.initials(), "J. D.", hn)
        CONSTANTS.initials_format = "{first}  {last}"
        hn = HumanName("Doe, John A. Kenneth, Jr.")
        self.m(hn.initials(), "J. D.", hn)

    def test_initials_delimiter(self) -> None:
        hn = HumanName("Doe, John A. Kenneth, Jr.", initials_delimiter=";")
        self.m(hn.initials(), "J; A; K; D;", hn)

    def test_initials_delimiter_constants(self) -> None:
        from nameparser.config import CONSTANTS
        CONSTANTS.initials_delimiter = ";"
        hn = HumanName("Doe, John A. Kenneth, Jr.")
        self.m(hn.initials(), "J; A; K; D;", hn)

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

    def test_initials_delimiter_empty_string_kwarg(self) -> None:
        # Regression: initials_delimiter='' was silently ignored due to `or` defaulting
        hn = HumanName("Doe, John A.", initials_delimiter="")
        self.m(hn.initials(), "J A D", hn)

    def test_initials_format_empty_string_kwarg(self) -> None:
        # Regression: initials_format='' was silently ignored due to `or` defaulting
        hn = HumanName("Doe, John A.")
        hn2 = HumanName("Doe, John A.", initials_format="")
        self.assertNotEqual(hn.initials(), hn2.initials())
        # "".format(...) returns ""; collapse_whitespace returns "" which falls through
        # to empty_attribute_default (may be "" or None depending on config variant).
        self.assertFalse(hn2.initials())

    def test_initials_separator_kwarg(self) -> None:
        # initials_separator="" with initials_format="{first}{middle}{last}" gives
        # period-separated initials with no spaces — a common academic citation style
        hn = HumanName(
            "Doe, John A. Kenneth",
            initials_separator="",
            initials_format="{first}{middle}{last}",
        )
        self.m(hn.initials(), "J.A.K.D.", hn)

    def test_initials_separator_custom_value(self) -> None:
        # Non-empty custom separator exercising __process_initial__ on a multi-word
        # token. "Van Berg" is a single name part whose two words produce two initials
        # joined by initials_separator.
        hn = HumanName("", initials_separator="-", initials_delimiter=".")
        result = hn.__process_initial__("Van Berg", firstname=True)
        self.assertEqual(result, "V-B")

    def test_str_default_behavior_unchanged(self) -> None:
        # Regression guard for the `or` → `is not None` change in __str__:
        # the default path (no string_format kwarg) must still produce the expected string.
        hn = HumanName("John Doe")
        self.assertEqual(str(hn), "John Doe")

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

    def test_initials_separator_kwarg_multiword_part(self) -> None:
        # Regression: initials_separator kwarg must flow into __process_initial__
        # for multi-word name parts, not just into the initials() join calls.
        hn = HumanName("", initials_separator="")
        result = hn.__process_initial__("Van Berg", firstname=True)
        self.assertEqual(result, "VB")

    def test_string_format_empty_string_kwarg(self) -> None:
        # Regression: string_format='' was silently ignored due to `or` defaulting
        hn = HumanName("John Doe", string_format="")
        self.assertEqual(str(hn), "")

    def test_initials_separator_empty_multi_part_middle(self) -> None:
        # Full workflow from issue #152: empty delimiter + separator + compact format
        # gives fully concatenated initials with no spaces or punctuation.
        # Spaces between groups come from initials_format, so that must also be set.
        hn = HumanName(
            "Doe, John A. Kenneth",
            initials_delimiter="",
            initials_separator="",
            initials_format="{first}{middle}{last}",
        )
        self.m(hn.initials(), "JAKD", hn)

    def test_initials_separator_constants_multi_part_middle(self) -> None:
        from nameparser.config import CONSTANTS
        CONSTANTS.initials_delimiter = ""
        CONSTANTS.initials_separator = ""
        CONSTANTS.initials_format = "{first}{middle}{last}"
        hn = HumanName("Doe, John A. Kenneth")
        self.m(hn.initials(), "JAKD", hn)

    def test_initials_separator_default_on_constants(self) -> None:
        # Runs after test_initials_separator_constants_multi_part_middle so that,
        # in file/definition order, it verifies the autouse fixture restored
        # CONSTANTS.initials_separator rather than leaking the "" set above.
        from nameparser.config import CONSTANTS
        self.assertEqual(CONSTANTS.initials_separator, " ")
