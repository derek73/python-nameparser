from nameparser.config import Constants


def test_latin_patronymic_matches_ovich() -> None:
    C = Constants()
    assert C.regexes.patronymic.search("Ivanovich")


def test_latin_patronymic_matches_ovna() -> None:
    C = Constants()
    assert C.regexes.patronymic.search("Ivanovna")


def test_latin_patronymic_matches_evich() -> None:
    C = Constants()
    assert C.regexes.patronymic.search("Sergeevich")


def test_latin_patronymic_matches_evna() -> None:
    C = Constants()
    assert C.regexes.patronymic.search("Sergeevna")


def test_latin_patronymic_matches_ichna() -> None:
    C = Constants()
    assert C.regexes.patronymic.search("Nikitichna")


def test_latin_patronymic_matches_special_ilyich() -> None:
    C = Constants()
    assert C.regexes.patronymic.search("Ilyich")


def test_latin_patronymic_rejects_non_patronymic() -> None:
    # EMPTY_REGEX (the default for missing keys) matches everything,
    # so this test is red until the real pattern is in place.
    C = Constants()
    assert not C.regexes.patronymic.search("Smith")


def test_latin_patronymic_matches_surname_with_patronymic_suffix() -> None:
    # Surnames that end in a patronymic suffix also match the regex;
    # the end-anchor does not prevent this.
    # Separate guard tests verify the *parser* doesn't reorder it incorrectly.
    C = Constants()
    assert C.regexes.patronymic.search("Abramovich")


def test_cyrillic_patronymic_matches_ovich() -> None:
    C = Constants()
    assert C.regexes.patronymic_cyrillic.search("Иванович")


def test_cyrillic_patronymic_matches_ovna() -> None:
    C = Constants()
    assert C.regexes.patronymic_cyrillic.search("Ивановна")


def test_cyrillic_patronymic_rejects_non_patronymic() -> None:
    C = Constants()
    assert not C.regexes.patronymic_cyrillic.search("Иванов")


def test_cyrillic_patronymic_matches_evich() -> None:
    C = Constants()
    assert C.regexes.patronymic_cyrillic.search("Сергеевич")


def test_cyrillic_patronymic_matches_evna() -> None:
    C = Constants()
    assert C.regexes.patronymic_cyrillic.search("Сергеевна")


def test_cyrillic_patronymic_matches_ichna() -> None:
    C = Constants()
    assert C.regexes.patronymic_cyrillic.search("Никитична")


def test_cyrillic_patronymic_matches_special_ilyich() -> None:
    C = Constants()
    assert C.regexes.patronymic_cyrillic.search("ильич")


def test_cyrillic_patronymic_matches_special_kuzmich() -> None:
    C = Constants()
    assert C.regexes.patronymic_cyrillic.search("кузьмич")


def test_cyrillic_patronymic_matches_special_lukich() -> None:
    C = Constants()
    assert C.regexes.patronymic_cyrillic.search("лукич")


def test_cyrillic_patronymic_matches_special_fomich() -> None:
    C = Constants()
    assert C.regexes.patronymic_cyrillic.search("фомич")


def test_cyrillic_patronymic_matches_special_fokich() -> None:
    C = Constants()
    assert C.regexes.patronymic_cyrillic.search("фокич")


class PatronymicNameOrderFlagTests:

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
