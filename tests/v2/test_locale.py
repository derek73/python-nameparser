import pytest

from nameparser._lexicon import Lexicon
from nameparser._locale import Locale
from nameparser._policy import PatronymicRule, PolicyPatch


def test_locale_holds_code_lexicon_fragment_and_patch() -> None:
    ru = Locale(
        code="ru",
        lexicon=Lexicon.empty(),
        policy=PolicyPatch(
            patronymic_rules=frozenset({PatronymicRule.EAST_SLAVIC})),
    )
    assert ru.code == "ru"
    assert ru.policy.patronymic_rules == frozenset(
        {PatronymicRule.EAST_SLAVIC})


def test_locale_defaults_to_empty_patch() -> None:
    assert Locale(code="xx", lexicon=Lexicon.empty()).policy == PolicyPatch()


def test_locale_code_must_be_nonempty_lowercase() -> None:
    with pytest.raises(ValueError, match="lowercase"):
        Locale(code="RU", lexicon=Lexicon.empty())
    with pytest.raises(ValueError, match="non-empty"):
        Locale(code="", lexicon=Lexicon.empty())


def test_locale_code_rejects_whitespace() -> None:
    # caught by the [a-z0-9_]+ charset pin (a dedicated whitespace check
    # would be pure redundancy; the charset message is accurate)
    for bad in ("ru ", " ru", "ru\n", "r u"):
        with pytest.raises(ValueError, match="a-z0-9_"):
            Locale(code=bad, lexicon=Lexicon.empty())


def test_locale_is_hashable() -> None:
    loc = Locale(code="ru", lexicon=Lexicon.empty())
    assert isinstance(hash(loc), int)


def test_locale_validates_component_types() -> None:
    with pytest.raises(TypeError, match="Lexicon"):
        Locale(code="ru", lexicon={"titles": set()})  # type: ignore[arg-type]
    with pytest.raises(TypeError, match="PolicyPatch"):
        Locale(code="ru", lexicon=Lexicon.empty(), policy={"name_order": None})  # type: ignore[arg-type]
    with pytest.raises(TypeError, match="must be a str"):
        Locale(code=5, lexicon=Lexicon.empty())  # type: ignore[arg-type]


def test_locale_with_lexicon_pickles_round_trip() -> None:
    import pickle

    loc = Locale(code="ru", lexicon=Lexicon.empty().add(titles={"Dr."}))
    assert pickle.loads(pickle.dumps(loc)) == loc


def test_locale_code_is_pinned_to_registry_charset() -> None:
    # Codes become registry keys the moment parser_for and third-party
    # packs exist: every accepted character is supported forever, so pin
    # [a-z0-9_]+ now (matches ru/tr_az). One separator only -- allowing
    # both '-' and '_' would make tr-az and tr_az distinct keys.
    for bad in ("ru!", "tr-az", "тр", "zh/tw"):
        with pytest.raises(ValueError, match="a-z0-9_"):
            Locale(code=bad, lexicon=Lexicon.empty())
    assert Locale(code="tr_az", lexicon=Lexicon.empty()).code == "tr_az"


def test_setstate_rejects_layout_skew() -> None:
    loc = Locale(code="ru", lexicon=Lexicon.empty())
    state = dict(loc.__getstate__())
    del state["code"]
    with pytest.raises(ValueError, match="code"):
        Locale.__new__(Locale).__setstate__(state)


def test_locale_chooses_no_language_unless_given_some() -> None:
    assert Locale(code="xx", lexicon=Lexicon.empty()).languages == frozenset()
    pt = Locale(code="pt", lexicon=Lexicon.empty(), languages=["pt", "pt"])  # type: ignore[arg-type]
    assert pt.languages == frozenset({"pt"})
    assert Locale(code="pt", lexicon=Lexicon.empty(),
                  languages=frozenset({"pt-BR"})).languages == {"pt-BR"}


@pytest.mark.parametrize("bad,error,match", [
    ("pt", TypeError, "not a bare string"),
    (b"pt", TypeError, "decode first"),
    ({"pt": True}, TypeError, "not a mapping"),
    (5, TypeError, "iterable of BCP 47 tags"),
    ([5], TypeError, "str BCP 47 tags"),
    (["p"], ValueError, "BCP 47 tags such as"),
    (["pt_BR"], ValueError, "BCP 47 tags such as"),
    (["pt-"], ValueError, "BCP 47 tags such as"),
    ([" pt"], ValueError, "BCP 47 tags such as"),
])
def test_locale_languages_must_be_bcp47_tags(
        bad: object, error: type[Exception], match: str) -> None:
    with pytest.raises(error, match=match):
        Locale(code="xx", lexicon=Lexicon.empty(), languages=bad)  # type: ignore[arg-type]


def test_locales_choosing_different_languages_differ() -> None:
    pt = Locale(code="xx", lexicon=Lexicon.empty(), languages=frozenset({"pt"}))
    assert pt != Locale(code="xx", lexicon=Lexicon.empty())
    assert hash(pt) == hash(Locale(code="xx", lexicon=Lexicon.empty(),
                                   languages=frozenset({"pt"})))


def test_locale_with_languages_pickles_round_trip() -> None:
    import pickle

    loc = Locale(code="pt", lexicon=Lexicon.empty(),
                 languages=frozenset({"pt", "pt-BR"}))
    assert pickle.loads(pickle.dumps(loc)) == loc
