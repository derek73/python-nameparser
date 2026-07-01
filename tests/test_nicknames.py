import pytest

from nameparser import HumanName

from tests.base import HumanNameTestBase


class NicknameTestCase(HumanNameTestBase):
    # https://code.google.com/p/python-nameparser/issues/detail?id=33
    def test_nickname_in_parenthesis(self) -> None:
        hn = HumanName("Benjamin (Ben) Franklin")
        self.m(hn.first, "Benjamin", hn)
        self.m(hn.middle, "", hn)
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


# class MaidenNameTestCase(HumanNameTestBase):
#
#     def test_parenthesis_and_quotes_together(self):
#         hn = HumanName("Jennifer 'Jen' Jones (Duff)")
#         self.m(hn.first, "Jennifer", hn)
#         self.m(hn.last, "Jones", hn)
#         self.m(hn.nickname, "Jen", hn)
#         self.m(hn.maiden, "Duff", hn)
#
#     def test_maiden_name_with_nee(self):
#         # https://en.wiktionary.org/wiki/née
#         hn = HumanName("Mary Toogood nee Johnson")
#         self.m(hn.first, "Mary", hn)
#         self.m(hn.last, "Toogood", hn)
#         self.m(hn.maiden, "Johnson", hn)
#
#     def test_maiden_name_with_accented_nee(self):
#         # https://en.wiktionary.org/wiki/née
#         hn = HumanName("Mary Toogood née Johnson")
#         self.m(hn.first, "Mary", hn)
#         self.m(hn.last, "Toogood", hn)
#         self.m(hn.maiden, "Johnson", hn)
#
#     def test_maiden_name_with_nee_and_comma(self):
#         # https://en.wiktionary.org/wiki/née
#         hn = HumanName("Mary Toogood, née Johnson")
#         self.m(hn.first, "Mary", hn)
#         self.m(hn.last, "Toogood", hn)
#         self.m(hn.maiden, "Johnson", hn)
#
#     def test_maiden_name_with_nee_with_parenthesis(self):
#         hn = HumanName("Mary Toogood (nee Johnson)")
#         self.m(hn.first, "Mary", hn)
#         self.m(hn.last, "Toogood", hn)
#         self.m(hn.maiden, "Johnson", hn)
#
#     def test_maiden_name_with_parenthesis(self):
#         hn = HumanName("Mary Toogood (Johnson)")
#         self.m(hn.first, "Mary", hn)
