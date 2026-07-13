from nameparser._lexicon import Lexicon
from nameparser._pipeline._vocab import is_initial, is_suffix_lenient, is_suffix_strict

_LEX = Lexicon(
    suffix_acronyms=frozenset({"phd"}),
    suffix_words=frozenset({"jr", "v"}),
    suffix_acronyms_ambiguous=frozenset({"ma"}),
)


def test_is_initial() -> None:
    assert is_initial("A.")
    assert is_initial("j.")
    assert is_initial("B")
    assert not is_initial("Jo")
    assert not is_initial("b")  # bare lowercase letter is not an initial


def test_strict_suffix_initial_veto() -> None:
    assert is_suffix_strict("PhD", _LEX)
    assert not is_suffix_strict("V.", _LEX)   # initial veto
    assert not is_suffix_strict("V", _LEX)    # initial veto
    assert is_suffix_strict("Jr", _LEX)


def test_ambiguous_acronym_needs_periods_and_beats_the_veto() -> None:
    assert is_suffix_strict("M.A.", _LEX)
    assert not is_suffix_strict("Ma", _LEX)


def test_lenient_accepts_suffix_words_unconditionally() -> None:
    assert is_suffix_lenient("V", _LEX)
    assert is_suffix_lenient("V.", _LEX)
    assert not is_suffix_lenient("Ma", _LEX)
