from nameparser import Parser, Policy, parse

from tests.base import ParsedNameTestBase

# Parentheses routed to the maiden name instead of the nickname.
_MAIDEN_PARENS = Parser(policy=Policy(maiden_delimiters=frozenset({("(", ")")})))


class NicknameTestCase(ParsedNameTestBase):
    # https://code.google.com/p/python-nameparser/issues/detail?id=33
    def test_nickname_in_parenthesis(self) -> None:
        hn = parse("Benjamin (Ben) Franklin")
        self.m(hn.given, "Benjamin", hn)
        self.m(hn.middle, "", hn)
        self.m(hn.family, "Franklin", hn)
        self.m(hn.nickname, "Ben", hn)

    # https://github.com/derek73/python-nameparser/issues/112
    def test_curly_braces_are_not_a_default_nickname_delimiter(self) -> None:
        hn = parse("Benjamin {Ben} Franklin")
        self.m(hn.nickname, "", hn)

    def test_square_brackets_are_not_a_default_nickname_delimiter(self) -> None:
        hn = parse("Benjamin [Ben] Franklin")
        self.m(hn.nickname, "", hn)

    def test_two_word_nickname_in_parenthesis(self) -> None:
        hn = parse("Benjamin (Big Ben) Franklin")
        self.m(hn.given, "Benjamin", hn)
        self.m(hn.middle, "", hn)
        self.m(hn.family, "Franklin", hn)
        self.m(hn.nickname, "Big Ben", hn)

    def test_two_words_in_quotes(self) -> None:
        hn = parse('Benjamin "Big Ben" Franklin')
        self.m(hn.given, "Benjamin", hn)
        self.m(hn.middle, "", hn)
        self.m(hn.family, "Franklin", hn)
        self.m(hn.nickname, "Big Ben", hn)

    def test_nickname_in_parenthesis_with_comma(self) -> None:
        hn = parse("Franklin, Benjamin (Ben)")
        self.m(hn.given, "Benjamin", hn)
        self.m(hn.middle, "", hn)
        self.m(hn.family, "Franklin", hn)
        self.m(hn.nickname, "Ben", hn)

    def test_nickname_in_parenthesis_with_comma_and_suffix(self) -> None:
        hn = parse("Franklin, Benjamin (Ben), Jr.")
        self.m(hn.given, "Benjamin", hn)
        self.m(hn.middle, "", hn)
        self.m(hn.family, "Franklin", hn)
        self.m(hn.suffix, "Jr.", hn)
        self.m(hn.nickname, "Ben", hn)

    def test_nickname_in_single_quotes(self) -> None:
        hn = parse("Benjamin 'Ben' Franklin")
        self.m(hn.given, "Benjamin", hn)
        self.m(hn.middle, "", hn)
        self.m(hn.family, "Franklin", hn)
        self.m(hn.nickname, "Ben", hn)

    def test_nickname_in_double_quotes(self) -> None:
        hn = parse("Benjamin \"Ben\" Franklin")
        self.m(hn.given, "Benjamin", hn)
        self.m(hn.middle, "", hn)
        self.m(hn.family, "Franklin", hn)
        self.m(hn.nickname, "Ben", hn)

    def test_single_quotes_on_first_name_not_treated_as_nickname(self) -> None:
        hn = parse("Brian Andrew O'connor")
        self.m(hn.given, "Brian", hn)
        self.m(hn.middle, "Andrew", hn)
        self.m(hn.family, "O'connor", hn)
        self.m(hn.nickname, "", hn)

    def test_single_quotes_on_both_name_not_treated_as_nickname(self) -> None:
        hn = parse("La'tanya O'connor")
        self.m(hn.given, "La'tanya", hn)
        self.m(hn.middle, "", hn)
        self.m(hn.family, "O'connor", hn)
        self.m(hn.nickname, "", hn)

    def test_single_quotes_on_end_of_last_name_not_treated_as_nickname(self) -> None:
        hn = parse("Mari' Aube'")
        self.m(hn.given, "Mari'", hn)
        self.m(hn.middle, "", hn)
        self.m(hn.family, "Aube'", hn)
        self.m(hn.nickname, "", hn)

    def test_okina_inside_name_not_treated_as_nickname(self) -> None:
        hn = parse("Harrieta Keōpūolani Nāhiʻenaʻena")
        self.m(hn.given, "Harrieta", hn)
        self.m(hn.middle, "Keōpūolani", hn)
        self.m(hn.family, "Nāhiʻenaʻena", hn)
        self.m(hn.nickname, "", hn)

    def test_single_quotes_not_treated_as_nickname_Hawaiian_example(self) -> None:
        hn = parse("Harietta Keopuolani Nahi'ena'ena")
        self.m(hn.given, "Harietta", hn)
        self.m(hn.middle, "Keopuolani", hn)
        self.m(hn.family, "Nahi'ena'ena", hn)
        self.m(hn.nickname, "", hn)

    def test_single_quotes_not_treated_as_nickname_Kenyan_example(self) -> None:
        hn = parse("Naomi Wambui Ng'ang'a")
        self.m(hn.given, "Naomi", hn)
        self.m(hn.middle, "Wambui", hn)
        self.m(hn.family, "Ng'ang'a", hn)
        self.m(hn.nickname, "", hn)

    def test_single_quotes_not_treated_as_nickname_Samoan_example(self) -> None:
        hn = parse("Va'apu'u Vitale")
        self.m(hn.given, "Va'apu'u", hn)
        self.m(hn.middle, "", hn)
        self.m(hn.family, "Vitale", hn)
        self.m(hn.nickname, "", hn)

    # http://code.google.com/p/python-nameparser/issues/detail?id=17
    def test_parenthesis_are_removed_from_name(self) -> None:
        hn = parse("John Jones (Unknown)")
        self.m(hn.given, "John", hn)
        self.m(hn.family, "Jones", hn)
        # not testing the nicknames because we don't actually care
        # about Google Docs here

    def test_duplicate_parenthesis_are_removed_from_name(self) -> None:
        hn = parse("John Jones (Google Docs), Jr. (Unknown)")
        self.m(hn.given, "John", hn)
        self.m(hn.family, "Jones", hn)
        self.m(hn.suffix, "Jr.", hn)

    def test_nickname_and_last_name(self) -> None:
        hn = parse('"Rick" Edmonds')
        self.m(hn.given, "", hn)
        self.m(hn.family, "Edmonds", hn)
        self.m(hn.nickname, "Rick", hn)

    def test_nickname_and_last_name_with_title(self) -> None:
        hn = parse('Senator "Rick" Edmonds')
        self.m(hn.title, "Senator", hn)
        self.m(hn.given, "", hn)
        self.m(hn.family, "Edmonds", hn)
        self.m(hn.nickname, "Rick", hn)

    def test_ambiguous_suffix_acronym_in_parenthesis_stays_nickname(self) -> None:
        # JD is in SUFFIX_ACRONYMS_AMBIGUOUS: both a law-degree acronym and a
        # common given-name nickname. Existing behavior (nickname) must be
        # preserved -- see issue #111.
        hn = parse("JEFFREY (JD) BRICKEN")
        self.m(hn.nickname, "JD", hn)
        self.m(hn.suffix, "", hn)


class MaidenNameTestCase(ParsedNameTestBase):
    def test_maiden_defaults_empty(self) -> None:
        hn = parse("Jenny Baker")
        self.m(hn.maiden, "", hn)

    def test_maiden_key_always_in_as_dict(self) -> None:
        # empty attributes are always '' in 2.0 (#255)
        hn = parse("Bob Dole")
        self.assertEqual(hn.as_dict()['maiden'], '')
        self.assertNotIn('maiden', hn.as_dict(include_empty=False))

    def test_maiden_appears_in_as_dict_when_populated(self) -> None:
        hn = parse("Jenny Baker").replace(maiden="Johnson")
        self.assertEqual(hn.as_dict()['maiden'], "Johnson")
        self.assertEqual(hn.as_dict(include_empty=False)['maiden'], "Johnson")

    def test_maiden_name_in_parenthesis_with_comma(self) -> None:
        hn = _MAIDEN_PARENS.parse("Baker (Johnson), Jenny")
        self.m(hn.given, "Jenny", hn)
        self.m(hn.family, "Baker", hn)
        self.m(hn.maiden, "Johnson", hn)

    def test_maiden_name_in_parenthesis_no_comma(self) -> None:
        hn = _MAIDEN_PARENS.parse("Jenny Baker (Johnson)")
        self.m(hn.given, "Jenny", hn)
        self.m(hn.family, "Baker", hn)
        self.m(hn.maiden, "Johnson", hn)

    def test_quotes_still_nickname_when_parens_routed_to_maiden(self) -> None:
        hn = _MAIDEN_PARENS.parse('Jenny "JJ" Baker (Johnson)')
        self.m(hn.given, "Jenny", hn)
        self.m(hn.family, "Baker", hn)
        self.m(hn.nickname, "JJ", hn)
        self.m(hn.maiden, "Johnson", hn)

    def test_maiden_off_by_default_parenthesis_still_routes_to_nickname(self) -> None:
        hn = parse("Baker (Johnson), Jenny")
        self.m(hn.given, "Jenny", hn)
        self.m(hn.family, "Baker", hn)
        self.m(hn.nickname, "Johnson", hn)
        self.m(hn.maiden, "", hn)

    def test_suffix_shaped_content_in_maiden_bucket_stays_in_place(self) -> None:
        # The #189 suffix-shaped carve-out applies regardless of which bucket the delimiter routes to.
        hn = _MAIDEN_PARENS.parse("Baker (Jr.), Jenny")
        self.m(hn.given, "Jenny", hn)
        self.m(hn.family, "Baker", hn)
        self.m(hn.suffix, "Jr.", hn)
        self.m(hn.maiden, "", hn)

    def test_marker_inside_maiden_parenthesis_is_consumed(self) -> None:
        # #329. Same value as the bare "Jane Smith née Jones", which is the
        # agreement #329 was about.
        hn = _MAIDEN_PARENS.parse("Jane Smith (née Jones)")
        self.m(hn.given, "Jane", hn)
        self.m(hn.family, "Smith", hn)
        self.m(hn.maiden, "Jones", hn)

    def test_unmarked_maiden_parenthesis_keeps_every_word(self) -> None:
        # The other side of the same rule: the drop is conditioned on
        # the first word being a marker, so ordinary two-word content
        # arrives whole.
        hn = _MAIDEN_PARENS.parse("Jane Smith (Mary Jones)")
        self.m(hn.given, "Jane", hn)
        self.m(hn.family, "Smith", hn)
        self.m(hn.maiden, "Mary Jones", hn)

    def test_lone_marker_word_in_its_own_parenthesis_is_a_name(self) -> None:
        # `Nee` is a real surname (Irish Ní/Nee, and a Chinese
        # romanization), so a one-word clause is content whatever it
        # spells -- even with a second clause following that could read
        # as the name it marks.
        hn = _MAIDEN_PARENS.parse("Jane Smith (Nee) (Jones)")
        self.m(hn.given, "Jane", hn)
        self.m(hn.family, "Smith", hn)
        self.m(hn.maiden, "Nee Jones", hn)

    def test_maiden_appears_in_as_dict_via_routing(self) -> None:
        hn = _MAIDEN_PARENS.parse("Baker (Johnson), Jenny")
        self.assertEqual(hn.as_dict()['maiden'], "Johnson")
