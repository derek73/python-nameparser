from nameparser import PatronymicRule, parse
from nameparser._pipeline._vocab import (
    _EAST_SLAVIC,
    _EAST_SLAVIC_CYR,
    _TURKIC,
    _TURKIC_CYR,
)
from tests.base import FlaggedPolicyTestBase, ParsedNameTestBase

_BOTH_RULES = {"patronymic_rules": {PatronymicRule.EAST_SLAVIC,
                                    PatronymicRule.TURKIC}}


def test_marker_is_whole_word_not_substring() -> None:
    # The Turkic marker test deliberately uses whole-word .match(),
    # not suffix .search() (unlike the East Slavic one) — pin this
    # so a future .match()->.search() slip doesn't silently start matching
    # surnames/given-names that merely contain a marker as a substring.
    assert not _TURKIC.match("ogluu")
    assert not _TURKIC.match("Bogluchik")
    assert not _TURKIC_CYR.match("оглуш")
    assert not _TURKIC_CYR.match("Оглуев")


class TurkicPatronymicNameOrderReorderTests(FlaggedPolicyTestBase):
    """Names that SHOULD be rotated when the flag is on."""

    policy_kwargs = _BOTH_RULES

    def test_oglu(self) -> None:
        n = self.hn("Aliyev Vusal Said oglu")
        assert n.given == "Vusal"
        assert n.middle == "Said oglu"
        assert n.family == "Aliyev"

    def test_oglu_native_orthography(self) -> None:
        n = self.hn("Aliyev Vusal Said oğlu")
        assert n.given == "Vusal"
        assert n.middle == "Said oğlu"
        assert n.family == "Aliyev"

    def test_ogly(self) -> None:
        n = self.hn("Aliyev Vusal Said ogly")
        assert n.given == "Vusal"
        assert n.middle == "Said ogly"
        assert n.family == "Aliyev"

    def test_ogli(self) -> None:
        n = self.hn("Aliyev Vusal Said ogli")
        assert n.given == "Vusal"
        assert n.middle == "Said ogli"
        assert n.family == "Aliyev"

    def test_ogli_uzbek_modifier_apostrophe(self) -> None:
        # U+02BB modifier letter turned comma, the official Uzbek orthography.
        n = self.hn("Yusupov Aziz Karim oʻgʻli")
        assert n.given == "Aziz"
        assert n.middle == "Karim oʻgʻli"
        assert n.family == "Yusupov"

    def test_ogli_straight_apostrophe(self) -> None:
        n = self.hn("Yusupov Aziz Karim o'g'li")
        assert n.given == "Aziz"
        assert n.middle == "Karim o'g'li"
        assert n.family == "Yusupov"

    def test_ogli_right_single_quote(self) -> None:
        # U+2019 right single quotation mark, common in informal data.
        n = self.hn("Yusupov Aziz Karim o’g’li")
        assert n.given == "Aziz"
        assert n.middle == "Karim o’g’li"
        assert n.family == "Yusupov"

    def test_qizi(self) -> None:
        n = self.hn("Aliyeva Mehriban Arif qizi")
        assert n.given == "Mehriban"
        assert n.middle == "Arif qizi"
        assert n.family == "Aliyeva"

    def test_qizi_native_orthography(self) -> None:
        n = self.hn("Aliyeva Mehriban Arif qızı")
        assert n.given == "Mehriban"
        assert n.middle == "Arif qızı"
        assert n.family == "Aliyeva"

    def test_kizi(self) -> None:
        n = self.hn("Yusupova Nodira Karim kizi")
        assert n.given == "Nodira"
        assert n.middle == "Karim kizi"
        assert n.family == "Yusupova"

    def test_kyzy(self) -> None:
        n = self.hn("Bekova Aigul Nurlan kyzy")
        assert n.given == "Aigul"
        assert n.middle == "Nurlan kyzy"
        assert n.family == "Bekova"

    def test_gyzy(self) -> None:
        n = self.hn("Annayeva Gozel Merdan gyzy")
        assert n.given == "Gozel"
        assert n.middle == "Merdan gyzy"
        assert n.family == "Annayeva"

    def test_uly(self) -> None:
        n = self.hn("Nazarbayev Nursultan Abish uly")
        assert n.given == "Nursultan"
        assert n.middle == "Abish uly"
        assert n.family == "Nazarbayev"

    def test_uulu(self) -> None:
        n = self.hn("Atambayev Almazbek Sharshenovich uulu")
        assert n.given == "Almazbek"
        assert n.middle == "Sharshenovich uulu"
        assert n.family == "Atambayev"

    def test_cyrillic_oglu(self) -> None:
        n = self.hn("Алиев Вусал Саид оглу")
        assert n.given == "Вусал"
        assert n.middle == "Саид оглу"
        assert n.family == "Алиев"

    def test_cyrillic_ogly(self) -> None:
        n = self.hn("Алиев Вусал Саид оглы")
        assert n.given == "Вусал"
        assert n.middle == "Саид оглы"
        assert n.family == "Алиев"

    def test_cyrillic_oglu_azerbaijani_native(self) -> None:
        n = self.hn("Алиев Вусал Саид оғлу")
        assert n.given == "Вусал"
        assert n.middle == "Саид оғлу"
        assert n.family == "Алиев"

    def test_cyrillic_ugli_uzbek_native(self) -> None:
        n = self.hn("Юсупов Азиз Карим ўғли")
        assert n.given == "Азиз"
        assert n.middle == "Карим ўғли"
        assert n.family == "Юсупов"

    def test_cyrillic_ugli_russian_rendering(self) -> None:
        n = self.hn("Юсупов Азиз Карим угли")
        assert n.given == "Азиз"
        assert n.middle == "Карим угли"
        assert n.family == "Юсупов"

    def test_cyrillic_kyzy(self) -> None:
        n = self.hn("Бекова Айгуль Нурлан кызы")
        assert n.given == "Айгуль"
        assert n.middle == "Нурлан кызы"
        assert n.family == "Бекова"

    def test_cyrillic_gyzy(self) -> None:
        n = self.hn("Аннаева Гозель Мердан гызы")
        assert n.given == "Гозель"
        assert n.middle == "Мердан гызы"
        assert n.family == "Аннаева"

    def test_cyrillic_qizi_uzbek(self) -> None:
        n = self.hn("Юсупова Нодира Карим қизи")
        assert n.given == "Нодира"
        assert n.middle == "Карим қизи"
        assert n.family == "Юсупова"

    def test_cyrillic_qyzy_kazakh_native(self) -> None:
        n = self.hn("Назарбаева Дана Абиш қызы")
        assert n.given == "Дана"
        assert n.middle == "Абиш қызы"
        assert n.family == "Назарбаева"

    def test_cyrillic_uly_russian_rendering(self) -> None:
        n = self.hn("Назарбаев Нурсултан Абиш улы")
        assert n.given == "Нурсултан"
        assert n.middle == "Абиш улы"
        assert n.family == "Назарбаев"

    def test_cyrillic_uly_kazakh_native(self) -> None:
        n = self.hn("Назарбаев Нурсултан Абиш ұлы")
        assert n.given == "Нурсултан"
        assert n.middle == "Абиш ұлы"
        assert n.family == "Назарбаев"

    def test_cyrillic_uulu(self) -> None:
        n = self.hn("Атамбаев Алмазбек Шаршенович уулу")
        assert n.given == "Алмазбек"
        assert n.middle == "Шаршенович уулу"
        assert n.family == "Атамбаев"

    def test_all_caps_latin(self) -> None:
        n = self.hn("ALIYEV VUSAL SAID OGLU")
        assert n.given == "VUSAL"
        assert n.middle == "SAID OGLU"
        assert n.family == "ALIYEV"

    def test_all_caps_cyrillic(self) -> None:
        n = self.hn("АЛИЕВ ВУСАЛ САИД ОГЛЫ")
        assert n.given == "ВУСАЛ"
        assert n.middle == "САИД ОГЛЫ"
        assert n.family == "АЛИЕВ"


class TurkicPatronymicNameOrderGuardsTests(FlaggedPolicyTestBase):
    """Names that must NOT be reordered even when the flag is on."""

    policy_kwargs = _BOTH_RULES

    def test_already_correct_natural_order(self) -> None:
        n = self.hn("Vusal Said oglu Aliyev")
        assert n.given == "Vusal"
        assert n.middle == "Said oglu"
        assert n.family == "Aliyev"

    def test_comma_guard(self) -> None:
        n = self.hn("Aliyev, Vusal Said oglu")
        assert n.given == "Vusal"
        assert n.middle == "Said oglu"
        assert n.family == "Aliyev"

    def test_three_token_no_surname(self) -> None:
        # No surname to rotate into place — parses as last=oglu, unchanged.
        n = self.hn("Vusal Said oglu")
        assert n.given == "Vusal"
        assert n.middle == "Said"
        assert n.family == "oglu"

    def test_five_token_extra_given_name(self) -> None:
        # Extra token before the patronymic phrase breaks the strict 4-token shape.
        n = self.hn("Aliyev Vusal Rza Said oglu")
        assert n.given == "Aliyev"
        assert n.middle == "Vusal Rza Said"
        assert n.family == "oglu"

    def test_ordinary_western_four_token_name(self) -> None:
        # Last word isn't a recognised marker → no rotation.
        n = self.hn("Smith John Michael Anderson")
        assert n.given == "Smith"
        assert n.middle == "John Michael"
        assert n.family == "Anderson"


class TurkicPatronymicNameOrderFlagOffTests(ParsedNameTestBase):
    """With the default Policy (no patronymic rules) nothing changes."""

    def test_reversed_order_unchanged(self) -> None:
        n = parse("Aliyev Vusal Said oglu")
        assert n.given == "Aliyev"
        assert n.middle == "Vusal Said"
        assert n.family == "oglu"


class PatronymicHandlerInteractionTests(FlaggedPolicyTestBase):
    """Both rules run in sequence under the same policy; confirm no interference."""

    policy_kwargs = _BOTH_RULES

    def test_east_slavic_shape_unaffected_by_turkic_handler(self) -> None:
        # If the Turkic rule ran BEFORE the East-Slavic rule could fire,
        # the middle would already be one word (not two),
        # so the Turkic guard is a no-op here regardless of call order.
        n = self.hn("Ivanov Ivan Ivanovich")
        assert n.given == "Ivan"
        assert n.middle == "Ivanovich"
        assert n.family == "Ivanov"

    def test_turkic_shape_unaffected_by_east_slavic_handler(self) -> None:
        # East-Slavic's own guard requires a one-word middle; this input
        # has two middle words, so it's a genuine no-op rather than a
        # partial mutation before the Turkic rule runs.
        n = self.hn("Aliyev Vusal Said oglu")
        assert n.given == "Vusal"
        assert n.middle == "Said oglu"
        assert n.family == "Aliyev"

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
