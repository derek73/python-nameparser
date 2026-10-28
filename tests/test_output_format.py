from nameparser import parse

from tests.base import ParsedNameTestBase

_KENNY = "Rev John A. Kenneth Doe III (Kenny)"


class OutputFormatTests(ParsedNameTestBase):

    def test_capitalize_name(self) -> None:
        hn = parse("bob v. de la macdole-eisenhower phd").capitalized()
        self.assertEqual(str(hn), "Bob V. de la MacDole-Eisenhower PhD")

    def test_force_mixed_case_capitalization(self) -> None:
        hn = parse('Shirley Maclaine').capitalized(force=True)
        self.assertEqual(str(hn), "Shirley MacLaine")

    def test_quote_nickname_formating(self) -> None:
        hn = parse(_KENNY)
        self.assertEqual(
            hn.render("{title} {given} {middle} {family} {suffix} '{nickname}'"),
            "Rev John A. Kenneth Doe III 'Kenny'")
        self.assertEqual(
            hn.render("{family}, {title} {given} {middle}, {suffix} '{nickname}'"),
            "Doe, Rev John A. Kenneth, III 'Kenny'")

    def test_formating_removing_keys_from_format_string(self) -> None:
        hn = parse(_KENNY)
        self.assertEqual(
            hn.render("{title} {given} {middle} {family} {suffix} '{nickname}'"),
            "Rev John A. Kenneth Doe III 'Kenny'")
        self.assertEqual(
            hn.render("{family}, {title} {given} {middle}, {suffix}"),
            "Doe, Rev John A. Kenneth, III")
        self.assertEqual(hn.render("{family}, {title} {given} {middle}"),
                         "Doe, Rev John A. Kenneth")
        self.assertEqual(hn.render("{family}, {given} {middle}"),
                         "Doe, John A. Kenneth")
        self.assertEqual(hn.render("{family}, {given}"), "Doe, John")
        self.assertEqual(hn.render("{given} {family}"), "John Doe")

    def test_formating_removing_pieces_from_name_buckets(self) -> None:
        spec = "{title} {given} {middle} {family} {suffix}"
        hn = parse(_KENNY)
        self.assertEqual(
            hn.render("{title} {given} {middle} {family} {suffix} '{nickname}'"),
            "Rev John A. Kenneth Doe III 'Kenny'")
        self.assertEqual(hn.render(spec), "Rev John A. Kenneth Doe III")
        hn = hn.replace(middle='')
        self.assertEqual(hn.render(spec), "Rev John Doe III")
        hn = hn.replace(suffix='')
        self.assertEqual(hn.render(spec), "Rev John Doe")
        hn = hn.replace(title='')
        self.assertEqual(hn.render(spec), "John Doe")

    def test_formating_of_nicknames_with_parenthesis(self) -> None:
        spec = "{title} {given} {middle} {family} {suffix} ({nickname})"
        hn = parse(_KENNY)
        self.assertEqual(hn.render(spec), "Rev John A. Kenneth Doe III (Kenny)")
        self.assertEqual(hn.replace(nickname='').render(spec),
                         "Rev John A. Kenneth Doe III")

    def test_formating_of_nicknames_with_single_quotes(self) -> None:
        spec = "{title} {given} {middle} {family} {suffix} '{nickname}'"
        hn = parse(_KENNY)
        self.assertEqual(hn.render(spec), "Rev John A. Kenneth Doe III 'Kenny'")
        self.assertEqual(hn.replace(nickname='').render(spec),
                         "Rev John A. Kenneth Doe III")

    def test_formating_of_nicknames_with_double_quotes(self) -> None:
        spec = "{title} {given} {middle} {family} {suffix} \"{nickname}\""
        hn = parse(_KENNY)
        self.assertEqual(hn.render(spec), "Rev John A. Kenneth Doe III \"Kenny\"")
        self.assertEqual(hn.replace(nickname='').render(spec),
                         "Rev John A. Kenneth Doe III")

    def test_formating_of_nicknames_in_middle(self) -> None:
        spec = "{title} {given} ({nickname}) {middle} {family} {suffix}"
        hn = parse(_KENNY)
        self.assertEqual(hn.render(spec), "Rev John (Kenny) A. Kenneth Doe III")
        self.assertEqual(hn.replace(nickname='').render(spec),
                         "Rev John A. Kenneth Doe III")

    def test_name_containing_none_substring_survives_formatting(self) -> None:
        # Residue of the #254 regression: v1's None-mode __str__ once
        # scrubbed the literal string 'None' from formatted output. The
        # None mode is gone in 2.0 (#255), but real name text spelled
        # 'None'/'Nonez' must still never be scrubbed by formatting.
        self.assertEqual(str(parse("Nonez Smith")), "Nonez Smith")
        self.assertEqual(str(parse("None Smith")), "None Smith")

    def test_empty_field_drops_surrounding_whitespace(self) -> None:
        # issue #139: adjacent whitespace/punctuation should be dropped when a field is empty
        hn = parse("John Smith")
        self.assertEqual(hn.render("{family} {suffix}, {given}"), "Smith, John")

    def test_empty_field_present_suffix_unaffected(self) -> None:
        hn = parse("John Smith Jr")
        self.assertEqual(hn.render("{family} {suffix}, {given}"),
                         "Smith Jr, John")

    def test_multiple_empty_fields_before_comma(self) -> None:
        hn = parse("John Smith")
        self.assertEqual(hn.render("{title} {suffix}, {given} {family}"),
                         "John Smith")

    def test_remove_emojis(self) -> None:
        hn = parse("Sam Smith 😊")
        self.m(hn.given, "Sam", hn)
        self.m(hn.family, "Smith", hn)
        self.assertEqual(str(hn), "Sam Smith")

    def test_keep_non_emojis(self) -> None:
        hn = parse("∫≜⩕ Smith 😊")
        self.m(hn.given, "∫≜⩕", hn)
        self.m(hn.family, "Smith", hn)
        self.assertEqual(str(hn), "∫≜⩕ Smith")

    def test_remove_bidi_control_chars(self) -> None:
        # LRM/RLM and friends ride along with copy-pasted names and stick to
        # the parts they surround. Covers every character in the bidi set.
        for mark in ("‎", "‏", "؜", "‪", "‫",
                     "‬", "‭", "‮", "⁦", "⁧",
                     "⁨", "⁩"):
            hn = parse(mark + "John" + mark + " Smith")
            self.m(hn.given, "John", hn)
            self.m(hn.family, "Smith", hn)

    def test_bidi_stripped_name_compares_equal(self) -> None:
        # The reported symptom: an invisible RLM around an RTL name makes the
        # parsed part fail equality against the clean string (issue #266).
        hn = parse("‏محمد بن سلمان‏")
        self.assertEqual(hn.given, "محمد")
