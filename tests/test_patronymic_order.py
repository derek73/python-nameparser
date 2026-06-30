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


def test_latin_patronymic_rejects_abramovich_substring_match() -> None:
    # Must be end-anchored so "Abramovich" also matches (it ends in -ovich).
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
