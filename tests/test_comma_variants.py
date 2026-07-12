from nameparser import HumanName
from nameparser.config import Constants
from nameparser.config.regexes import REGEXES

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

    def test_custom_regexes_without_commas_key_does_not_shatter_name(self) -> None:
        # A custom regexes dict that omits "commas" entirely must not fall
        # back to RegexTupleManager's EMPTY_REGEX default for splitting --
        # re.compile('').split(...) matches between every character, which
        # explodes any name into single-char pieces instead of leaving it
        # unsplit (the EMPTY_REGEX convention elsewhere in this codebase
        # means "feature disabled", not "split on every character").
        # With comma splitting disabled, "Smith, John" is tokenized like any
        # other no-comma input (word tokenizing drops the punctuation),
        # yielding a plain first/last pair -- not the inverted "Last, First"
        # reading, and definitely not single-character pieces.
        custom = {k: v for k, v in REGEXES.items() if k != 'commas'}
        c = Constants(regexes=custom)
        hn = HumanName("Smith, John", constants=c)
        self.m(hn.first, "Smith", hn)
        self.m(hn.last, "John", hn)
