from nameparser import HumanName

from tests.base import HumanNameTestBase


class HumanNameOutputFormatTests(HumanNameTestBase):

    def test_formatting_init_argument(self) -> None:
        hn = HumanName("Rev John A. Kenneth Doe III (Kenny)",
                       string_format="TEST1")
        self.assertEqual(str(hn), "TEST1")

    def test_formatting_constants_attribute(self) -> None:
        from nameparser.config import CONSTANTS
        CONSTANTS.string_format = "TEST2"
        hn = HumanName("Rev John A. Kenneth Doe III (Kenny)")
        self.assertEqual(str(hn), "TEST2")

    def test_capitalize_name_constants_attribute(self) -> None:
        from nameparser.config import CONSTANTS
        CONSTANTS.capitalize_name = True
        hn = HumanName("bob v. de la macdole-eisenhower phd")
        self.assertEqual(str(hn), "Bob V. de la MacDole-Eisenhower Ph.D.")

    def test_force_mixed_case_capitalization_constants_attribute(self) -> None:
        from nameparser.config import CONSTANTS
        CONSTANTS.force_mixed_case_capitalization = True
        hn = HumanName('Shirley Maclaine')
        hn.capitalize()
        self.assertEqual(str(hn), "Shirley MacLaine")

    def test_capitalize_name_and_force_mixed_case_capitalization_constants_attributes(self) -> None:
        from nameparser.config import CONSTANTS
        CONSTANTS.capitalize_name = True
        CONSTANTS.force_mixed_case_capitalization = True
        hn = HumanName('Shirley Maclaine')
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

    def test_keep_emojis(self) -> None:
        from nameparser.config import Constants
        constants = Constants()
        constants.regexes.emoji = False  # type: ignore[assignment]
        hn = HumanName("∫≜⩕ Smith😊", constants)
        self.m(hn.first, "∫≜⩕", hn)
        self.m(hn.last, "Smith😊", hn)
        self.assertEqual(str(hn), "∫≜⩕ Smith😊")
        # test cleanup
