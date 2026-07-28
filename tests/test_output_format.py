import pytest

from nameparser import HumanName
from nameparser.config import Constants

from tests.base import HumanNameTestBase


class HumanNameOutputFormatTests(HumanNameTestBase):

    def test_formatting_init_argument(self) -> None:
        hn = HumanName("Rev John A. Kenneth Doe III (Kenny)",
                       string_format="TEST1")
        self.assertEqual(str(hn), "TEST1")

    # The four *_constants_attribute tests below ran on the shared CONSTANTS
    # singleton in v1; 2.0 deprecates shared mutation, so they use a private
    # Constants passed as constants= (the migration-guide idiom) -- the
    # config attribute under test is the same either way.

    def test_formatting_constants_attribute(self) -> None:
        c = Constants()
        c.string_format = "TEST2"
        hn = HumanName("Rev John A. Kenneth Doe III (Kenny)", constants=c)
        self.assertEqual(str(hn), "TEST2")

    def test_capitalize_name_constants_attribute(self) -> None:
        c = Constants()
        c.capitalize_name = True
        hn = HumanName("bob v. de la macdole-eisenhower phd", constants=c)
        self.assertEqual(str(hn), "Bob V. de la MacDole-Eisenhower Ph.D.")

    def test_force_mixed_case_capitalization_constants_attribute(self) -> None:
        c = Constants()
        c.force_mixed_case_capitalization = True
        hn = HumanName('Shirley Maclaine', constants=c)
        hn.capitalize()
        self.assertEqual(str(hn), "Shirley MacLaine")

    def test_capitalize_name_and_force_mixed_case_capitalization_constants_attributes(self) -> None:
        c = Constants()
        c.capitalize_name = True
        c.force_mixed_case_capitalization = True
        hn = HumanName('Shirley Maclaine', constants=c)
        self.assertEqual(str(hn), "Shirley MacLaine")

    def test_quote_nickname_formating(self) -> None:
        hn = HumanName("Rev John A. Kenneth Doe III (Kenny)")
        hn.string_format = "{title} {first} {middle} {last} {suffix} '{nickname}'"
        self.assertEqual(str(hn), "Rev John A. Kenneth Doe III 'Kenny'")
        hn.string_format = "{last}, {title} {first} {middle}, {suffix} '{nickname}'"
        self.assertEqual(str(hn), "Doe, Rev John A. Kenneth, III 'Kenny'")

    def test_formating_removing_keys_from_format_string(self) -> None:
        hn = HumanName("Rev John A. Kenneth Doe III (Kenny)")
        hn.string_format = "{title} {first} {middle} {last} {suffix} '{nickname}'"
        self.assertEqual(str(hn), "Rev John A. Kenneth Doe III 'Kenny'")
        hn.string_format = "{last}, {title} {first} {middle}, {suffix}"
        self.assertEqual(str(hn), "Doe, Rev John A. Kenneth, III")
        hn.string_format = "{last}, {title} {first} {middle}"
        self.assertEqual(str(hn), "Doe, Rev John A. Kenneth")
        hn.string_format = "{last}, {first} {middle}"
        self.assertEqual(str(hn), "Doe, John A. Kenneth")
        hn.string_format = "{last}, {first}"
        self.assertEqual(str(hn), "Doe, John")
        hn.string_format = "{first} {last}"
        self.assertEqual(str(hn), "John Doe")

    def test_formating_removing_pieces_from_name_buckets(self) -> None:
        hn = HumanName("Rev John A. Kenneth Doe III (Kenny)")
        hn.string_format = "{title} {first} {middle} {last} {suffix} '{nickname}'"
        self.assertEqual(str(hn), "Rev John A. Kenneth Doe III 'Kenny'")
        hn.string_format = "{title} {first} {middle} {last} {suffix}"
        self.assertEqual(str(hn), "Rev John A. Kenneth Doe III")
        hn.middle = ''
        self.assertEqual(str(hn), "Rev John Doe III")
        hn.suffix = ''
        self.assertEqual(str(hn), "Rev John Doe")
        hn.title = ''
        self.assertEqual(str(hn), "John Doe")

    def test_formating_of_nicknames_with_parenthesis(self) -> None:
        hn = HumanName("Rev John A. Kenneth Doe III (Kenny)")
        hn.string_format = "{title} {first} {middle} {last} {suffix} ({nickname})"
        self.assertEqual(str(hn), "Rev John A. Kenneth Doe III (Kenny)")
        hn.nickname = ''
        self.assertEqual(str(hn), "Rev John A. Kenneth Doe III")

    def test_formating_of_nicknames_with_single_quotes(self) -> None:
        hn = HumanName("Rev John A. Kenneth Doe III (Kenny)")
        hn.string_format = "{title} {first} {middle} {last} {suffix} '{nickname}'"
        self.assertEqual(str(hn), "Rev John A. Kenneth Doe III 'Kenny'")
        hn.nickname = ''
        self.assertEqual(str(hn), "Rev John A. Kenneth Doe III")

    def test_formating_of_nicknames_with_double_quotes(self) -> None:
        hn = HumanName("Rev John A. Kenneth Doe III (Kenny)")
        hn.string_format = "{title} {first} {middle} {last} {suffix} \"{nickname}\""
        self.assertEqual(str(hn), "Rev John A. Kenneth Doe III \"Kenny\"")
        hn.nickname = ''
        self.assertEqual(str(hn), "Rev John A. Kenneth Doe III")

    def test_formating_of_nicknames_in_middle(self) -> None:
        hn = HumanName("Rev John A. Kenneth Doe III (Kenny)")
        hn.string_format = "{title} {first} ({nickname}) {middle} {last} {suffix}"
        self.assertEqual(str(hn), "Rev John (Kenny) A. Kenneth Doe III")
        hn.nickname = ''
        self.assertEqual(str(hn), "Rev John A. Kenneth Doe III")

    def test_name_containing_none_substring_survives_formatting(self) -> None:
        # Residue of the #254 regression: v1's None-mode __str__ once
        # scrubbed the literal string 'None' from formatted output. The
        # None mode is gone in 2.0 (#255), but real name text spelled
        # 'None'/'Nonez' must still never be scrubbed by formatting.
        self.assertEqual(str(HumanName("Nonez Smith")), "Nonez Smith")
        self.assertEqual(str(HumanName("None Smith")), "None Smith")

    def test_empty_field_drops_surrounding_whitespace(self) -> None:
        # issue #139: adjacent whitespace/punctuation should be dropped when a field is empty
        hn = HumanName("John Smith")
        hn.string_format = "{last} {suffix}, {first}"
        self.assertEqual(str(hn), "Smith, John")

    def test_empty_field_present_suffix_unaffected(self) -> None:
        hn = HumanName("John Smith Jr")
        hn.string_format = "{last} {suffix}, {first}"
        self.assertEqual(str(hn), "Smith Jr, John")

    def test_multiple_empty_fields_before_comma(self) -> None:
        hn = HumanName("John Smith")
        hn.string_format = "{title} {suffix}, {first} {last}"
        self.assertEqual(str(hn), "John Smith")

    def test_remove_emojis(self) -> None:
        hn = HumanName("Sam Smith 😊")
        self.m(hn.first, "Sam", hn)
        self.m(hn.last, "Smith", hn)
        self.assertEqual(str(hn), "Sam Smith")

    def test_keep_non_emojis(self) -> None:
        hn = HumanName("∫≜⩕ Smith 😊")
        self.m(hn.first, "∫≜⩕", hn)
        self.m(hn.last, "Smith", hn)
        self.assertEqual(str(hn), "∫≜⩕ Smith")

    def test_keep_emojis_opt_out_moved_to_policy(self) -> None:
        # v1's regexes.emoji = False opt-out is not supported in 2.0
        # (deliberate divergence, migration spec section 3 uniform rule):
        # the assignment raises, and the error names the replacement,
        # Policy(strip_emoji=False).
        constants = Constants()
        with pytest.raises(TypeError, match="strip_emoji"):
            constants.regexes.emoji = False  # type: ignore[assignment]

    def test_remove_bidi_control_chars(self) -> None:
        # LRM/RLM and friends ride along with copy-pasted names and stick to
        # the parts they surround. Covers every character in the bidi set.
        for mark in ("\u200e", "\u200f", "\u061c", "\u202a", "\u202b",
                     "\u202c", "\u202d", "\u202e", "\u2066", "\u2067",
                     "\u2068", "\u2069"):
            hn = HumanName(mark + "John" + mark + " Smith")
            self.m(hn.first, "John", hn)
            self.m(hn.last, "Smith", hn)

    def test_bidi_stripped_name_compares_equal(self) -> None:
        # The reported symptom: an invisible RLM around an RTL name makes the
        # parsed part fail equality against the clean string (issue #266).
        hn = HumanName("\u200fمحمد بن سلمان\u200f")
        self.assertEqual(hn.first, "محمد")

    def test_keep_bidi_opt_out_moved_to_policy(self) -> None:
        # v1's regexes.bidi = False opt-out is not supported in 2.0
        # (deliberate divergence, migration spec section 3 uniform rule):
        # the assignment raises, and the error names the replacement,
        # Policy(strip_bidi=False).
        constants = Constants()
        with pytest.raises(TypeError, match="strip_bidi"):
            constants.regexes.bidi = False  # type: ignore[assignment]
