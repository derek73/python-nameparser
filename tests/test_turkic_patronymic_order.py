import re
from typing import cast

from nameparser import HumanName
from nameparser.config import Constants
from tests.base import FlaggedConstantsTestBase, HumanNameTestBase

# The 2.0 regexes proxy types its attributes as ``object`` (reads are
# informational); the pattern-inspection tests below cast once here.
_R = Constants().regexes
_TURKIC = cast('re.Pattern[str]', _R.turkic_patronymic_marker)
_TURKIC_CYR = cast('re.Pattern[str]', _R.turkic_patronymic_marker_cyrillic)
_EAST_SLAVIC = cast('re.Pattern[str]', _R.east_slavic_patronymic)
_EAST_SLAVIC_CYR = cast('re.Pattern[str]', _R.east_slavic_patronymic_cyrillic)


def test_marker_is_whole_word_not_substring() -> None:
    # is_turkic_patronymic_marker() deliberately uses whole-word .match(),
    # not suffix .search() (unlike is_east_slavic_patronymic()) — pin this
    # so a future .match()->.search() slip doesn't silently start matching
    # surnames/given-names that merely contain a marker as a substring.
    assert not _TURKIC.match("ogluu")
    assert not _TURKIC.match("Bogluchik")
    assert not _TURKIC_CYR.match("оглуш")
    assert not _TURKIC_CYR.match("Оглуев")


class TurkicPatronymicNameOrderReorderTests(FlaggedConstantsTestBase):
    """Names that SHOULD be rotated when the flag is on."""

    constants_kwargs = {"patronymic_name_order": True}

    def test_oglu(self) -> None:
        n = self.hn("Aliyev Vusal Said oglu")
        assert n.first == "Vusal"
        assert n.middle == "Said oglu"
        assert n.last == "Aliyev"

    def test_oglu_native_orthography(self) -> None:
        n = self.hn("Aliyev Vusal Said oğlu")
        assert n.first == "Vusal"
        assert n.middle == "Said oğlu"
        assert n.last == "Aliyev"

    def test_ogly(self) -> None:
        n = self.hn("Aliyev Vusal Said ogly")
        assert n.first == "Vusal"
        assert n.middle == "Said ogly"
        assert n.last == "Aliyev"

    def test_ogli(self) -> None:
        n = self.hn("Aliyev Vusal Said ogli")
        assert n.first == "Vusal"
        assert n.middle == "Said ogli"
        assert n.last == "Aliyev"

    def test_ogli_uzbek_modifier_apostrophe(self) -> None:
        # U+02BB modifier letter turned comma, the official Uzbek orthography.
        n = self.hn("Yusupov Aziz Karim oʻgʻli")
        assert n.first == "Aziz"
        assert n.middle == "Karim oʻgʻli"
        assert n.last == "Yusupov"

    def test_ogli_straight_apostrophe(self) -> None:
        n = self.hn("Yusupov Aziz Karim o'g'li")
        assert n.first == "Aziz"
        assert n.middle == "Karim o'g'li"
        assert n.last == "Yusupov"

    def test_ogli_right_single_quote(self) -> None:
        # U+2019 right single quotation mark, common in informal data.
        n = self.hn("Yusupov Aziz Karim o’g’li")
        assert n.first == "Aziz"
        assert n.middle == "Karim o’g’li"
        assert n.last == "Yusupov"

    def test_qizi(self) -> None:
        n = self.hn("Aliyeva Mehriban Arif qizi")
        assert n.first == "Mehriban"
        assert n.middle == "Arif qizi"
        assert n.last == "Aliyeva"

    def test_qizi_native_orthography(self) -> None:
        n = self.hn("Aliyeva Mehriban Arif qızı")
        assert n.first == "Mehriban"
        assert n.middle == "Arif qızı"
        assert n.last == "Aliyeva"

    def test_kizi(self) -> None:
        n = self.hn("Yusupova Nodira Karim kizi")
        assert n.first == "Nodira"
        assert n.middle == "Karim kizi"
        assert n.last == "Yusupova"

    def test_kyzy(self) -> None:
        n = self.hn("Bekova Aigul Nurlan kyzy")
        assert n.first == "Aigul"
        assert n.middle == "Nurlan kyzy"
        assert n.last == "Bekova"

    def test_gyzy(self) -> None:
        n = self.hn("Annayeva Gozel Merdan gyzy")
        assert n.first == "Gozel"
        assert n.middle == "Merdan gyzy"
        assert n.last == "Annayeva"

    def test_uly(self) -> None:
        n = self.hn("Nazarbayev Nursultan Abish uly")
        assert n.first == "Nursultan"
        assert n.middle == "Abish uly"
        assert n.last == "Nazarbayev"

    def test_uulu(self) -> None:
        n = self.hn("Atambayev Almazbek Sharshenovich uulu")
        assert n.first == "Almazbek"
        assert n.middle == "Sharshenovich uulu"
        assert n.last == "Atambayev"

    def test_cyrillic_oglu(self) -> None:
        n = self.hn("Алиев Вусал Саид оглу")
        assert n.first == "Вусал"
        assert n.middle == "Саид оглу"
        assert n.last == "Алиев"

    def test_cyrillic_ogly(self) -> None:
        n = self.hn("Алиев Вусал Саид оглы")
        assert n.first == "Вусал"
        assert n.middle == "Саид оглы"
        assert n.last == "Алиев"

    def test_cyrillic_oglu_azerbaijani_native(self) -> None:
        n = self.hn("Алиев Вусал Саид оғлу")
        assert n.first == "Вусал"
        assert n.middle == "Саид оғлу"
        assert n.last == "Алиев"

    def test_cyrillic_ugli_uzbek_native(self) -> None:
        n = self.hn("Юсупов Азиз Карим ўғли")
        assert n.first == "Азиз"
        assert n.middle == "Карим ўғли"
        assert n.last == "Юсупов"

    def test_cyrillic_ugli_russian_rendering(self) -> None:
        n = self.hn("Юсупов Азиз Карим угли")
        assert n.first == "Азиз"
        assert n.middle == "Карим угли"
        assert n.last == "Юсупов"

    def test_cyrillic_kyzy(self) -> None:
        n = self.hn("Бекова Айгуль Нурлан кызы")
        assert n.first == "Айгуль"
        assert n.middle == "Нурлан кызы"
        assert n.last == "Бекова"

    def test_cyrillic_gyzy(self) -> None:
        n = self.hn("Аннаева Гозель Мердан гызы")
        assert n.first == "Гозель"
        assert n.middle == "Мердан гызы"
        assert n.last == "Аннаева"

    def test_cyrillic_qizi_uzbek(self) -> None:
        n = self.hn("Юсупова Нодира Карим қизи")
        assert n.first == "Нодира"
        assert n.middle == "Карим қизи"
        assert n.last == "Юсупова"

    def test_cyrillic_qyzy_kazakh_native(self) -> None:
        n = self.hn("Назарбаева Дана Абиш қызы")
        assert n.first == "Дана"
        assert n.middle == "Абиш қызы"
        assert n.last == "Назарбаева"

    def test_cyrillic_uly_russian_rendering(self) -> None:
        n = self.hn("Назарбаев Нурсултан Абиш улы")
        assert n.first == "Нурсултан"
        assert n.middle == "Абиш улы"
        assert n.last == "Назарбаев"

    def test_cyrillic_uly_kazakh_native(self) -> None:
        n = self.hn("Назарбаев Нурсултан Абиш ұлы")
        assert n.first == "Нурсултан"
        assert n.middle == "Абиш ұлы"
        assert n.last == "Назарбаев"

    def test_cyrillic_uulu(self) -> None:
        n = self.hn("Атамбаев Алмазбек Шаршенович уулу")
        assert n.first == "Алмазбек"
        assert n.middle == "Шаршенович уулу"
        assert n.last == "Атамбаев"

    def test_all_caps_latin(self) -> None:
        n = self.hn("ALIYEV VUSAL SAID OGLU")
        assert n.first == "VUSAL"
        assert n.middle == "SAID OGLU"
        assert n.last == "ALIYEV"

    def test_all_caps_cyrillic(self) -> None:
        n = self.hn("АЛИЕВ ВУСАЛ САИД ОГЛЫ")
        assert n.first == "ВУСАЛ"
        assert n.middle == "САИД ОГЛЫ"
        assert n.last == "АЛИЕВ"


class TurkicPatronymicNameOrderGuardsTests(FlaggedConstantsTestBase):
    """Names that must NOT be reordered even when the flag is on."""

    constants_kwargs = {"patronymic_name_order": True}

    def test_already_correct_natural_order(self) -> None:
        n = self.hn("Vusal Said oglu Aliyev")
        assert n.first == "Vusal"
        assert n.middle == "Said oglu"
        assert n.last == "Aliyev"

    def test_comma_guard(self) -> None:
        n = self.hn("Aliyev, Vusal Said oglu")
        assert n.first == "Vusal"
        assert n.middle == "Said oglu"
        assert n.last == "Aliyev"

    def test_three_token_no_surname(self) -> None:
        # No surname to rotate into place — parses as last=oglu, unchanged.
        n = self.hn("Vusal Said oglu")
        assert n.first == "Vusal"
        assert n.middle == "Said"
        assert n.last == "oglu"

    def test_five_token_extra_given_name(self) -> None:
        # Extra token before the patronymic phrase breaks the strict 4-token shape.
        n = self.hn("Aliyev Vusal Rza Said oglu")
        assert n.first == "Aliyev"
        assert n.middle == "Vusal Rza Said"
        assert n.last == "oglu"

    def test_ordinary_western_four_token_name(self) -> None:
        # Last word isn't a recognised marker → no rotation.
        n = self.hn("Smith John Michael Anderson")
        assert n.first == "Smith"
        assert n.middle == "John Michael"
        assert n.last == "Anderson"


class TurkicPatronymicNameOrderFlagOffTests(HumanNameTestBase):
    """With default Constants (flag=False) nothing changes."""

    def test_reversed_order_unchanged(self) -> None:
        n = HumanName("Aliyev Vusal Said oglu")
        assert n.first == "Aliyev"
        assert n.middle == "Vusal Said"
        assert n.last == "oglu"


class PatronymicHandlerInteractionTests(FlaggedConstantsTestBase):
    """Both handlers run in sequence under the same flag; confirm no interference."""

    constants_kwargs = {"patronymic_name_order": True}

    def test_east_slavic_shape_unaffected_by_turkic_handler(self) -> None:
        # If handle_turkic_patronymic_name_order() ran BEFORE the East-Slavic
        # handler could fire, middle_list would already be length 1 (not 2),
        # so the Turkic guard is a no-op here regardless of call order.
        n = self.hn("Ivanov Ivan Ivanovich")
        assert n.first == "Ivan"
        assert n.middle == "Ivanovich"
        assert n.last == "Ivanov"

    def test_turkic_shape_unaffected_by_east_slavic_handler(self) -> None:
        # East-Slavic's own guard requires middle_list of length 1; this
        # input has middle_list of length 2, so it's a genuine no-op rather
        # than a partial mutation before the Turkic handler runs.
        n = self.hn("Aliyev Vusal Said oglu")
        assert n.first == "Vusal"
        assert n.middle == "Said oglu"
        assert n.last == "Aliyev"

    def test_no_regex_collision_latin(self) -> None:
        east_slavic_examples = [
            "Ivanovich", "Ivanovna", "Sergeevich", "Sergeevna",
            "Nikitichna", "Ilyich", "Kuzmich", "Lukich", "Fomich", "Fokich",
        ]
        turkic_examples = [
            "oglu", "oğlu", "ogly", "ogli", "o'g'li",
            "qizi", "qızı", "kizi", "kyzy", "gyzy", "uly", "uulu",
        ]
        for word in east_slavic_examples:
            # Sanity check: each word actually matches its own family's
            # regex, so the non-collision assertion below is non-vacuous.
            assert _EAST_SLAVIC.search(word), word
            assert not _TURKIC.match(word), word
        for word in turkic_examples:
            assert _TURKIC.match(word), word
            assert not _EAST_SLAVIC.search(word), word

    def test_no_regex_collision_cyrillic(self) -> None:
        east_slavic_examples = [
            "Иванович", "Ивановна", "Сергеевич", "Сергеевна",
            "Никитична", "Ильич", "Кузьмич", "Лукич", "Фомич", "Фокич",
        ]
        turkic_examples = [
            "оглу", "оглы", "оғлу", "ўғли", "угли",
            "кызы", "гызы", "қызы", "қизи", "улы", "ұлы", "уулу",
        ]
        for word in east_slavic_examples:
            # Sanity check: each word actually matches its own family's
            # regex, so the non-collision assertion below is non-vacuous.
            assert _EAST_SLAVIC_CYR.search(word), word
            assert not _TURKIC_CYR.match(word), word
        for word in turkic_examples:
            assert _TURKIC_CYR.match(word), word
            assert not _EAST_SLAVIC_CYR.search(word), word
