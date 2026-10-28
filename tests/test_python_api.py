import pytest

from nameparser import Lexicon, Parser, parse

from tests.base import ParsedNameTestBase


class PythonApiTests(ParsedNameTestBase):

    def test_utf8(self) -> None:
        hn = parse("de la Véña, Jüan")
        self.m(hn.given, "Jüan", hn)
        self.m(hn.family, "de la Véña", hn)

    def test_string_output(self) -> None:
        hn = parse("de la Véña, Jüan")
        self.m(str(hn), "Jüan de la Véña", hn)

    def test_escaped_utf8_bytes(self) -> None:
        # bytes input was removed in 2.0 (#245, warned since 1.3.0):
        # decode first
        with pytest.raises(TypeError, match="decode"):
            parse(b'B\xc3\xb6ck, Gerald')  # type: ignore[arg-type]
        hn = parse(b'B\xc3\xb6ck, Gerald'.decode('utf-8'))
        self.m(hn.given, "Gerald", hn)
        self.m(hn.family, "Böck", hn)

    def test_reparse_of_another_name(self) -> None:
        hn = parse("John A. Kenneth Doe, Jr.")
        self.m(hn.given, "John", hn)
        self.m(hn.family, "Doe", hn)
        self.m(hn.middle, "A. Kenneth", hn)
        self.m(hn.suffix, "Jr.", hn)
        hn = parse("Juan Velasquez y Garcia III")
        self.m(hn.given, "Juan", hn)
        self.m(hn.family, "Velasquez y Garcia", hn)
        self.m(hn.suffix, "III", hn)

    def test_comparison_key_components(self) -> None:
        hn = parse("Dr. Juan Q. Xavier de la Vega III")
        self.assertEqual(
            hn.comparison_key(),
            ('dr.', 'juan', 'q. xavier', 'de la vega', 'iii', '', ''))

    def test_comparison_key_case_insensitive_across_formats(self) -> None:
        hn1 = parse("Dr. Juan Q. Xavier de la Vega III")
        hn2 = parse("de la vega, dr. juan Q. xavier III")
        self.assertEqual(hn1.comparison_key(), hn2.comparison_key())

    def test_comparison_key_usable_for_dedup(self) -> None:
        names = [parse("John Smith"), parse("Smith, John"),
                 parse("JOHN SMITH"), parse("Jane Smith")]
        unique = {n.comparison_key(): n for n in names}
        self.assertEqual(len(unique), 2)

    def test_matches_case_insensitive(self) -> None:
        hn1 = parse("Doe-Ray, Dr. John P., CLU, CFP, LUTC")
        hn2 = parse("dr. john p. doe-Ray, CLU, CFP, LUTC")
        self.assertTrue(hn1.matches(hn2))
        self.assertTrue(hn1.matches("Dr. John P. Doe-ray clu, CFP, LUTC"))

    def test_matches_str_is_semantic_not_textual(self) -> None:
        # any written form of the same name matches
        hn = parse("Dr. Juan Q. Xavier de la Vega III")
        self.assertTrue(hn.matches("de la vega, dr. juan Q. xavier III"))
        self.assertTrue(hn.matches("Dr. Juan Q. Xavier de la Vega III"))
        self.assertFalse(hn.matches("Juan de la Vega"))

    def test_matches_parsed_name_operand(self) -> None:
        hn = parse("John Smith")
        self.assertTrue(hn.matches(parse("JOHN SMITH")))
        self.assertFalse(hn.matches(parse("Jane Smith")))

    def test_matches_parses_str_with_the_parsers_lexicon(self) -> None:
        # the custom title must not be a default one ('chancellor' is!), or
        # this passes without the custom parse path ever mattering
        self.assertNotIn('zephyrmark', Lexicon.default().titles)
        parser = Parser(lexicon=Lexicon.default().add(titles={'zephyrmark'}))
        hn = parser.parse("Zephyrmark Jane Smith")
        # the str operand is parsed with the parser's lexicon, so the custom
        # title is recognized in the comma form; parsed with the default,
        # 'zephyrmark' would land in given/middle and the keys would differ
        self.assertTrue(parser.matches(hn, "smith, zephyrmark jane"))

    def test_empty_parses_share_a_comparison_key(self) -> None:
        # documented caveat: empty/unparsable input collapses to the
        # all-empty key, so such names match each other and collide in
        # dedup
        self.assertTrue(parse("").matches(parse(",")))
        self.assertEqual(parse("()").comparison_key(),
                         parse("").comparison_key())

    def test_matches_non_ascii_case_insensitive(self) -> None:
        hn = parse("JOSÉ GARCÍA")
        self.assertTrue(hn.matches("José García"))

    def test_conjunction_names(self) -> None:
        hn = parse("johnny y")
        self.m(hn.given, "johnny", hn)
        self.m(hn.family, "y", hn)

    def test_prefix_names(self) -> None:
        hn = parse("vai la")
        self.m(hn.given, "vai", hn)
        self.m(hn.family, "la", hn)

    def test_degenerate_comma_input_leaves_no_empty_pieces(self) -> None:
        hn = parse(",")
        self.m(hn.given, "", hn)
        self.m(hn.middle, "", hn)
        self.m(hn.family, "", hn)
        self.assertEqual(hn.tokens, ())
        hn = parse("Doe,, Jr.")
        self.m(hn.given, "", hn)
        self.m(hn.family, "Doe", hn)
        self.m(hn.suffix, "Jr.", hn)
        # an empty family segment before the comma must not become a family
        hn = parse(", John")
        self.m(hn.family, "", hn)
        self.m(hn.given, "John", hn)

    def test_blank_name(self) -> None:
        hn = parse("")
        self.m(hn.given, "", hn)
        self.m(hn.family, "", hn)

    def test_surnames_attribute(self) -> None:
        hn = parse("John Edgar Casey Williams III")
        self.m(hn.surnames, "Edgar Casey Williams", hn)

    def test_given_names_attribute(self) -> None:
        hn = parse("John Edgar Casey Williams III")
        self.m(hn.given_names, "John Edgar Casey", hn)

    def test_given_names_attribute_first_only(self) -> None:
        hn = parse("John Williams")
        self.m(hn.given_names, "John", hn)

    def test_given_names_attribute_empty(self) -> None:
        hn = parse("Dr. Williams")
        self.m(hn.given_names, "", hn)
