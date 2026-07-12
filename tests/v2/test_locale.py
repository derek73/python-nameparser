import pytest

from nameparser._lexicon import Lexicon
from nameparser._locale import Locale
from nameparser._policy import PatronymicRule, PolicyPatch


def test_locale_holds_code_lexicon_fragment_and_patch():
    ru = Locale(
        code="ru",
        lexicon=Lexicon.empty(),
        policy=PolicyPatch(
            patronymic_rules=frozenset({PatronymicRule.EAST_SLAVIC})),
    )
    assert ru.code == "ru"
    assert ru.policy.patronymic_rules == frozenset(
        {PatronymicRule.EAST_SLAVIC})


def test_locale_defaults_to_empty_patch():
    assert Locale(code="xx", lexicon=Lexicon.empty()).policy == PolicyPatch()


def test_locale_code_must_be_nonempty_lowercase():
    with pytest.raises(ValueError, match="lowercase"):
        Locale(code="RU", lexicon=Lexicon.empty())
    with pytest.raises(ValueError, match="non-empty"):
        Locale(code="", lexicon=Lexicon.empty())


def test_locale_code_rejects_whitespace():
    for bad in ("ru ", " ru", "ru\n", "r u"):
        with pytest.raises(ValueError, match="whitespace"):
            Locale(code=bad, lexicon=Lexicon.empty())


def test_locale_is_hashable():
    loc = Locale(code="ru", lexicon=Lexicon.empty())
    assert isinstance(hash(loc), int)


def test_locale_validates_component_types():
    with pytest.raises(ValueError, match="Lexicon"):
        Locale(code="ru", lexicon={"titles": set()})  # type: ignore[arg-type]
    with pytest.raises(ValueError, match="PolicyPatch"):
        Locale(code="ru", lexicon=Lexicon.empty(), policy={"name_order": None})  # type: ignore[arg-type]


def test_locale_with_lexicon_pickles_round_trip():
    import pickle

    loc = Locale(code="ru", lexicon=Lexicon.empty().add(titles={"Dr."}))
    assert pickle.loads(pickle.dumps(loc)) == loc
