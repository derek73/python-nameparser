import re

import pytest

from nameparser import HumanName
from nameparser.config import Constants

from tests.base import HumanNameTestBase


class NicknameTestCase(HumanNameTestBase):
    # https://code.google.com/p/python-nameparser/issues/detail?id=33
    def test_nickname_in_parenthesis(self) -> None:
        hn = HumanName("Benjamin (Ben) Franklin")
        self.m(hn.first, "Benjamin", hn)
        self.m(hn.middle, "", hn)
        self.m(hn.last, "Franklin", hn)
        self.m(hn.nickname, "Ben", hn)

    # https://github.com/derek73/python-nameparser/issues/112
    def test_add_custom_nickname_delimiter(self) -> None:
        hn = HumanName("Benjamin {Ben} Franklin", constants=None)
        # curly braces aren't a recognized delimiter by default
        self.m(hn.nickname, "", hn)
        hn.C.nickname_delimiters['curly_braces'] = re.compile(r'\{(.*?)\}')
        hn.parse_full_name()
        self.m(hn.first, "Benjamin", hn)
        self.m(hn.last, "Franklin", hn)
        self.m(hn.nickname, "Ben", hn)

    def test_remove_custom_nickname_delimiter(self) -> None:
        hn = HumanName("Benjamin {Ben} Franklin", constants=None)
        hn.C.nickname_delimiters['curly_braces'] = re.compile(r'\{(.*?)\}')
        hn.parse_full_name()
        self.m(hn.nickname, "Ben", hn)
        del hn.C.nickname_delimiters['curly_braces']
        hn.parse_full_name()
        self.m(hn.nickname, "", hn)

    def test_multiple_custom_nickname_delimiters_together(self) -> None:
        # Two extras registered at once must both be recognized in a single
        # parse, independent of insertion order.
        hn = HumanName("Benjamin {Ben} <Benny> Franklin", constants=None)
        hn.C.nickname_delimiters['curly_braces'] = re.compile(r'\{(.*?)\}')
        hn.C.nickname_delimiters['angle_brackets'] = re.compile(r'<(.*?)>')
        hn.parse_full_name()
        self.m(hn.first, "Benjamin", hn)
        self.m(hn.last, "Franklin", hn)
        self.m(hn.nickname, "Ben Benny", hn)

    def test_overriding_builtin_regex_still_affects_nickname_parsing(self) -> None:
        # The pre-existing customization path (overriding self.C.regexes
        # directly) must keep working: nickname_delimiters' three built-in
        # entries resolve self.C.regexes.<name> live at parse time rather than
        # storing a snapshotted pattern.
        hn = HumanName("Benjamin [Ben] Franklin", constants=None)
        self.m(hn.nickname, "", hn)
        hn.C.regexes['parenthesis'] = re.compile(r'\[(.*?)\]')
        hn.parse_full_name()
        self.m(hn.first, "Benjamin", hn)
        self.m(hn.last, "Franklin", hn)
        self.m(hn.nickname, "Ben", hn)

    def test_two_word_nickname_in_parenthesis(self) -> None:
        hn = HumanName("Benjamin (Big Ben) Franklin")
        self.m(hn.first, "Benjamin", hn)
        self.m(hn.middle, "", hn)
        self.m(hn.last, "Franklin", hn)
        self.m(hn.nickname, "Big Ben", hn)

    def test_two_words_in_quotes(self) -> None:
        hn = HumanName('Benjamin "Big Ben" Franklin')
        self.m(hn.first, "Benjamin", hn)
        self.m(hn.middle, "", hn)
        self.m(hn.last, "Franklin", hn)
        self.m(hn.nickname, "Big Ben", hn)

    def test_nickname_in_parenthesis_with_comma(self) -> None:
        hn = HumanName("Franklin, Benjamin (Ben)")
        self.m(hn.first, "Benjamin", hn)
        self.m(hn.middle, "", hn)
        self.m(hn.last, "Franklin", hn)
        self.m(hn.nickname, "Ben", hn)

    def test_nickname_in_parenthesis_with_comma_and_suffix(self) -> None:
        hn = HumanName("Franklin, Benjamin (Ben), Jr.")
        self.m(hn.first, "Benjamin", hn)
        self.m(hn.middle, "", hn)
        self.m(hn.last, "Franklin", hn)
        self.m(hn.suffix, "Jr.", hn)
        self.m(hn.nickname, "Ben", hn)

    def test_nickname_in_single_quotes(self) -> None:
        hn = HumanName("Benjamin 'Ben' Franklin")
        self.m(hn.first, "Benjamin", hn)
        self.m(hn.middle, "", hn)
        self.m(hn.last, "Franklin", hn)
        self.m(hn.nickname, "Ben", hn)

    def test_nickname_in_double_quotes(self) -> None:
        hn = HumanName("Benjamin \"Ben\" Franklin")
        self.m(hn.first, "Benjamin", hn)
        self.m(hn.middle, "", hn)
        self.m(hn.last, "Franklin", hn)
        self.m(hn.nickname, "Ben", hn)

    def test_single_quotes_on_first_name_not_treated_as_nickname(self) -> None:
        hn = HumanName("Brian Andrew O'connor")
        self.m(hn.first, "Brian", hn)
        self.m(hn.middle, "Andrew", hn)
        self.m(hn.last, "O'connor", hn)
        self.m(hn.nickname, "", hn)

    def test_single_quotes_on_both_name_not_treated_as_nickname(self) -> None:
        hn = HumanName("La'tanya O'connor")
        self.m(hn.first, "La'tanya", hn)
        self.m(hn.middle, "", hn)
        self.m(hn.last, "O'connor", hn)
        self.m(hn.nickname, "", hn)

    def test_single_quotes_on_end_of_last_name_not_treated_as_nickname(self) -> None:
        hn = HumanName("Mari' Aube'")
        self.m(hn.first, "Mari'", hn)
        self.m(hn.middle, "", hn)
        self.m(hn.last, "Aube'", hn)
        self.m(hn.nickname, "", hn)

    def test_okina_inside_name_not_treated_as_nickname(self) -> None:
        hn = HumanName("Harrieta Keōpūolani Nāhiʻenaʻena")
        self.m(hn.first, "Harrieta", hn)
        self.m(hn.middle, "Keōpūolani", hn)
        self.m(hn.last, "Nāhiʻenaʻena", hn)
        self.m(hn.nickname, "", hn)

    def test_single_quotes_not_treated_as_nickname_Hawaiian_example(self) -> None:
        hn = HumanName("Harietta Keopuolani Nahi'ena'ena")
        self.m(hn.first, "Harietta", hn)
        self.m(hn.middle, "Keopuolani", hn)
        self.m(hn.last, "Nahi'ena'ena", hn)
        self.m(hn.nickname, "", hn)

    def test_single_quotes_not_treated_as_nickname_Kenyan_example(self) -> None:
        hn = HumanName("Naomi Wambui Ng'ang'a")
        self.m(hn.first, "Naomi", hn)
        self.m(hn.middle, "Wambui", hn)
        self.m(hn.last, "Ng'ang'a", hn)
        self.m(hn.nickname, "", hn)

    def test_single_quotes_not_treated_as_nickname_Samoan_example(self) -> None:
        hn = HumanName("Va'apu'u Vitale")
        self.m(hn.first, "Va'apu'u", hn)
        self.m(hn.middle, "", hn)
        self.m(hn.last, "Vitale", hn)
        self.m(hn.nickname, "", hn)

    # http://code.google.com/p/python-nameparser/issues/detail?id=17
    def test_parenthesis_are_removed_from_name(self) -> None:
        hn = HumanName("John Jones (Unknown)")
        self.m(hn.first, "John", hn)
        self.m(hn.last, "Jones", hn)
        # not testing the nicknames because we don't actually care
        # about Google Docs here

    def test_duplicate_parenthesis_are_removed_from_name(self) -> None:
        hn = HumanName("John Jones (Google Docs), Jr. (Unknown)")
        self.m(hn.first, "John", hn)
        self.m(hn.last, "Jones", hn)
        self.m(hn.suffix, "Jr.", hn)

    def test_nickname_and_last_name(self) -> None:
        hn = HumanName('"Rick" Edmonds')
        self.m(hn.first, "", hn)
        self.m(hn.last, "Edmonds", hn)
        self.m(hn.nickname, "Rick", hn)

    @pytest.mark.xfail
    def test_nickname_and_last_name_with_title(self) -> None:
        hn = HumanName('Senator "Rick" Edmonds')
        self.m(hn.title, "Senator", hn)
        self.m(hn.first, "", hn)
        self.m(hn.last, "Edmonds", hn)
        self.m(hn.nickname, "Rick", hn)

    def test_ambiguous_suffix_acronym_in_parenthesis_stays_nickname(self) -> None:
        # JD is in SUFFIX_ACRONYMS_AMBIGUOUS: both a law-degree acronym and a
        # common given-name nickname. Existing behavior (nickname) must be
        # preserved -- see issue #111.
        hn = HumanName("JEFFREY (JD) BRICKEN")
        self.m(hn.nickname, "JD", hn)
        self.m(hn.suffix, "", hn)

    def test_ambiguous_suffix_acronym_in_custom_delimiter_stays_nickname(self) -> None:
        # Same suffix-vs-nickname disambiguation as above, but through a
        # custom delimiter added via nickname_delimiters -- confirms
        # handle_match() is applied uniformly regardless of which delimiter
        # matched, not just the three built-ins.
        hn = HumanName("JEFFREY {JD} BRICKEN", constants=None)
        hn.C.nickname_delimiters['curly_braces'] = re.compile(r'\{(.*?)\}')
        hn.parse_full_name()
        self.m(hn.nickname, "JD", hn)
        self.m(hn.suffix, "", hn)


class MaidenNameTestCase(HumanNameTestBase):
    def test_maiden_assignment_and_property(self) -> None:
        hn = HumanName("Jenny Baker")
        hn.maiden = "Johnson"
        self.m(hn.maiden, "Johnson", hn)

    def test_maiden_defaults_empty(self) -> None:
        hn = HumanName("Jenny Baker")
        self.m(hn.maiden, "", hn)

    def test_maiden_key_always_in_as_dict(self) -> None:
        hn = HumanName("Bob Dole")
        self.assertEqual(hn.as_dict()['maiden'], hn.C.empty_attribute_default)
        self.assertNotIn('maiden', hn.as_dict(False))

    def test_maiden_appears_in_as_dict_when_populated(self) -> None:
        hn = HumanName("Jenny Baker")
        hn.maiden = "Johnson"
        self.assertEqual(hn.as_dict()['maiden'], "Johnson")
        self.assertEqual(hn.as_dict(False)['maiden'], "Johnson")

    def test_maiden_appears_in_slice(self) -> None:
        hn = HumanName("Jenny Baker")
        hn.maiden = "Johnson"
        self.assertIn("Johnson", hn[:])

    def test_maiden_via_constructor_kwarg(self) -> None:
        hn = HumanName(first="Jenny", last="Baker", maiden="Johnson")
        self.m(hn.first, "Jenny", hn)
        self.m(hn.last, "Baker", hn)
        self.m(hn.maiden, "Johnson", hn)
        self.assertFalse(hn.unparsable)

    def test_maiden_name_in_parenthesis_with_comma(self) -> None:
        C = Constants()
        C.maiden_delimiters['parenthesis'] = C.nickname_delimiters.pop('parenthesis')
        hn = HumanName("Baker (Johnson), Jenny", constants=C)
        self.m(hn.first, "Jenny", hn)
        self.m(hn.last, "Baker", hn)
        self.m(hn.maiden, "Johnson", hn)

    def test_maiden_name_in_parenthesis_no_comma(self) -> None:
        C = Constants()
        C.maiden_delimiters['parenthesis'] = C.nickname_delimiters.pop('parenthesis')
        hn = HumanName("Jenny Baker (Johnson)", constants=C)
        self.m(hn.first, "Jenny", hn)
        self.m(hn.last, "Baker", hn)
        self.m(hn.maiden, "Johnson", hn)

    def test_quotes_still_nickname_when_parens_routed_to_maiden(self) -> None:
        C = Constants()
        C.maiden_delimiters['parenthesis'] = C.nickname_delimiters.pop('parenthesis')
        hn = HumanName('Jenny "JJ" Baker (Johnson)', constants=C)
        self.m(hn.first, "Jenny", hn)
        self.m(hn.last, "Baker", hn)
        self.m(hn.nickname, "JJ", hn)
        self.m(hn.maiden, "Johnson", hn)

    def test_maiden_off_by_default_parenthesis_still_routes_to_nickname(self) -> None:
        hn = HumanName("Baker (Johnson), Jenny")
        self.m(hn.first, "Jenny", hn)
        self.m(hn.last, "Baker", hn)
        self.m(hn.nickname, "Johnson", hn)
        self.m(hn.maiden, "", hn)

    def test_suffix_shaped_content_in_maiden_bucket_stays_in_place(self) -> None:
        # The #189 suffix-shaped carve-out in handle_match() applies
        # regardless of which bucket the delimiter routes to.
        C = Constants()
        C.maiden_delimiters['parenthesis'] = C.nickname_delimiters.pop('parenthesis')
        hn = HumanName("Baker (Jr.), Jenny", constants=C)
        self.m(hn.first, "Jenny", hn)
        self.m(hn.last, "Baker", hn)
        self.m(hn.suffix, "Jr.", hn)
        self.m(hn.maiden, "", hn)

    def test_maiden_appears_in_as_dict_via_routing(self) -> None:
        C = Constants()
        C.maiden_delimiters['parenthesis'] = C.nickname_delimiters.pop('parenthesis')
        hn = HumanName("Baker (Johnson), Jenny", constants=C)
        self.assertEqual(hn.as_dict()['maiden'], "Johnson")
