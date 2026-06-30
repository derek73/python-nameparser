from nameparser import HumanName
from nameparser.config import Constants
from tests.base import HumanNameTestBase


def test_latin_patronymic_matches() -> None:
    # One common suffix and one irregular — the integration tests cover the rest.
    C = Constants()
    assert C.regexes.patronymic.search("Ivanovich")
    assert C.regexes.patronymic.search("Ilyich")


def test_latin_patronymic_rejects_non_patronymic() -> None:
    # EMPTY_REGEX (the default for missing keys) matches everything,
    # so this test is red until the real pattern is in place.
    C = Constants()
    assert not C.regexes.patronymic.search("Smith")


def test_latin_patronymic_end_anchored() -> None:
    # A surname ending in a patronymic suffix matches; the end-anchor does not
    # prevent this. The parser guard tests verify reordering is suppressed.
    C = Constants()
    assert C.regexes.patronymic.search("Abramovich")


def test_cyrillic_patronymic_matches() -> None:
    # One common suffix and one irregular.
    C = Constants()
    assert C.regexes.patronymic_cyrillic.search("Иванович")
    assert C.regexes.patronymic_cyrillic.search("ильич")


def test_cyrillic_patronymic_rejects_non_patronymic() -> None:
    C = Constants()
    assert not C.regexes.patronymic_cyrillic.search("Иванов")


class PatronymicNameOrderReorderTests(HumanNameTestBase):
    """Names that SHOULD be rotated when the flag is on."""

    def setup_method(self) -> None:
        self.C = Constants(patronymic_name_order=True)

    def hn(self, name: str) -> HumanName:
        return HumanName(name, constants=self.C)

    def test_canonical_latin(self) -> None:
        n = self.hn("Ivanov Ivan Ivanovich")
        assert n.first == "Ivan"
        assert n.middle == "Ivanovich"
        assert n.last == "Ivanov"

    def test_sergeevich(self) -> None:
        n = self.hn("Zarubkin Alexander Sergeevich")
        assert n.first == "Alexander"
        assert n.middle == "Sergeevich"
        assert n.last == "Zarubkin"

    def test_hyphenated_surname(self) -> None:
        # A hyphenated surname counts as one token.
        n = self.hn("Blokin-Mechtalin Konstantin Yurievich")
        assert n.first == "Konstantin"
        assert n.middle == "Yurievich"
        assert n.last == "Blokin-Mechtalin"

    def test_surname_looks_like_patronymic(self) -> None:
        # "Petsevich" ends in -evich but is in the FIRST position.
        n = self.hn("Petsevich Sergey Vitalyevich")
        assert n.first == "Sergey"
        assert n.middle == "Vitalyevich"
        assert n.last == "Petsevich"

    def test_cyrillic(self) -> None:
        n = self.hn("Иванов Иван Иванович")
        assert n.first == "Иван"
        assert n.middle == "Иванович"
        assert n.last == "Иванов"

    def test_title_preserved(self) -> None:
        n = self.hn("Dr. Ivanov Ivan Ivanovich")
        assert n.title == "Dr."
        assert n.first == "Ivan"
        assert n.middle == "Ivanovich"
        assert n.last == "Ivanov"

    def test_suffix_preserved(self) -> None:
        n = self.hn("Ivanov Ivan Ivanovich Jr.")
        assert n.first == "Ivan"
        assert n.middle == "Ivanovich"
        assert n.last == "Ivanov"
        assert n.suffix == "Jr."

    def test_western_patronymic_surname_reordered_when_flag_on(self) -> None:
        # Documented opt-in tradeoff: a Western name whose last token ends in a
        # patronymic suffix is reordered incorrectly. Not a bug to fix.
        n = self.hn("David Michael Abramovich")
        assert n.first == "Michael"
        assert n.middle == "Abramovich"
        assert n.last == "David"


class PatronymicNameOrderGuardsTests(HumanNameTestBase):
    """Names that must NOT be reordered even when the flag is on."""

    def setup_method(self) -> None:
        self.C = Constants(patronymic_name_order=True)

    def hn(self, name: str) -> HumanName:
        return HumanName(name, constants=self.C)

    def test_already_correct_order(self) -> None:
        # middle is patronymic → already in Western order, do not rotate
        n = self.hn("Ivan Ivanovich Ivanov")
        assert n.first == "Ivan"
        assert n.middle == "Ivanovich"
        assert n.last == "Ivanov"

    def test_middle_is_patronymic_surname_ends_ovich(self) -> None:
        # "Roman Arkadyevich Abramovich": middle IS patronymic → guard fires
        n = self.hn("Roman Arkadyevich Abramovich")
        assert n.first == "Roman"
        assert n.middle == "Arkadyevich"
        assert n.last == "Abramovich"

    def test_two_token_name(self) -> None:
        # 2-token: middle_list is empty → condition fails
        n = self.hn("Roman Abramovich")
        assert n.first == "Roman"
        assert n.last == "Abramovich"

    def test_no_patronymic(self) -> None:
        # Three tokens but no patronymic suffix on last → not reordered
        n = self.hn("Ivanov Ivan Petrov")
        assert n.first == "Ivanov"
        assert n.middle == "Ivan"
        assert n.last == "Petrov"

    def test_western_name_unchanged(self) -> None:
        n = self.hn("John Michael Smith")
        assert n.first == "John"
        assert n.middle == "Michael"
        assert n.last == "Smith"

    def test_comma_guard_last_first_pat(self) -> None:
        # "Ivanov, Ivan Ivanovich" — comma means the order was declared
        n = self.hn("Ivanov, Ivan Ivanovich")
        assert n.first == "Ivan"
        assert n.middle == "Ivanovich"
        assert n.last == "Ivanov"

    def test_comma_guard_patronymic_form_surname(self) -> None:
        # Without the comma guard this would wrongly rotate
        n = self.hn("Sergeevich, Ivan Petrov")
        assert n.last == "Sergeevich"

class PatronymicNameOrderFlagOffTests(HumanNameTestBase):
    """With default Constants (flag=False) nothing changes."""

    def test_canonical_unchanged(self) -> None:
        n = HumanName("Ivanov Ivan Ivanovich")
        assert n.first == "Ivanov"
        assert n.middle == "Ivan"
        assert n.last == "Ivanovich"


class PatronymicNameOrderFlagTests(HumanNameTestBase):

    def test_default_is_false(self) -> None:
        C = Constants()
        assert C.patronymic_name_order is False

    def test_can_set_true_via_constructor(self) -> None:
        C = Constants(patronymic_name_order=True)
        assert C.patronymic_name_order is True

    def test_does_not_affect_other_instance(self) -> None:
        C1 = Constants(patronymic_name_order=True)
        C2 = Constants()
        assert C1.patronymic_name_order is True
        assert C2.patronymic_name_order is False
