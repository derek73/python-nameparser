from nameparser import HumanName

from tests.base import HumanNameTestBase


class HumanNameCommaVariantsTests(HumanNameTestBase):
    """Non-ASCII comma characters should split "Last, First" the same as ',' (#265)."""

    def test_arabic_comma_splits_lastname_format(self) -> None:
        hn = HumanName("سلمان، محمد")
        self.m(hn.first, "محمد", hn)
        self.m(hn.last, "سلمان", hn)

    def test_fullwidth_comma_splits_lastname_format(self) -> None:
        hn = HumanName("Smith，John")
        self.m(hn.first, "John", hn)
        self.m(hn.last, "Smith", hn)

    def test_arabic_comma_does_not_pollute_output(self) -> None:
        hn = HumanName("سلمان، محمد")
        self.assertNotIn("،", hn.last)
        self.assertNotIn("،", str(hn))

    def test_trailing_arabic_comma_stripped(self) -> None:
        # matches ASCII behavior: a single word with a trailing comma has
        # nothing after the comma, so it's a bare name, not "Last,"
        hn = HumanName("سلمان،")
        self.m(hn.first, "سلمان", hn)

    # The v1 test for a custom regexes dict omitting the 'commas' key (the
    # EMPTY_REGEX shatter guard) died with the mechanism: Constants(regexes=
    # ...) raises TypeError in 2.0 (deliberate divergence, migration spec
    # section 3 uniform rule) -- pinned in test_python_api.py's
    # test_override_regex_raises.
