from nameparser import parse

from tests.base import ParsedNameTestBase


class CommaVariantsTests(ParsedNameTestBase):
    """Non-ASCII comma characters should split "Last, First" the same as ',' (#265)."""

    def test_arabic_comma_splits_lastname_format(self) -> None:
        hn = parse("سلمان، محمد")
        self.m(hn.given, "محمد", hn)
        self.m(hn.family, "سلمان", hn)

    def test_fullwidth_comma_splits_lastname_format(self) -> None:
        hn = parse("Smith，John")
        self.m(hn.given, "John", hn)
        self.m(hn.family, "Smith", hn)

    def test_arabic_comma_does_not_pollute_output(self) -> None:
        hn = parse("سلمان، محمد")
        self.assertNotIn("،", hn.family)
        self.assertNotIn("،", str(hn))

    def test_trailing_arabic_comma_stripped(self) -> None:
        # matches ASCII behavior: a single word with a trailing comma has
        # nothing after the comma, so it's a bare name, not "Last,"
        hn = parse("سلمان،")
        self.m(hn.given, "سلمان", hn)
