from nameparser._lexicon import Lexicon
from nameparser._pipeline._vocab import (
    is_initial, is_suffix_lenient, is_suffix_strict, single_script,
)
from nameparser._policy import Script

_LEX = Lexicon(
    suffix_acronyms=frozenset({"phd", "ma"}),
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


def test_strict_excludes_bare_ambiguous_even_when_in_acronyms() -> None:
    # mirrors the real data shape: ambiguous is a SUBSET of acronyms
    assert not is_suffix_strict("Ma", _LEX)
    assert is_suffix_strict("M.A.", _LEX)


def test_single_script_requires_every_char_in_one_script() -> None:
    assert single_script("毛泽东") is Script.HAN
    assert single_script("諸葛") is Script.HAN          # traditional
    assert single_script("김민준") is Script.HANGUL
    assert single_script("Smith") is None
    assert single_script("毛zedong") is None            # mixed
    assert single_script("毛김") is None                 # mixed CJK
    assert single_script("イチロー") is None             # kana: not HAN


def test_single_script_range_edges() -> None:
    # one char at each declared bound, and a neighbour outside
    assert single_script("㐀") is Script.HAN    # Ext A first
    assert single_script("䶿") is Script.HAN    # Ext A last
    assert single_script("䷀") is None          # hexagram, not Han
    # U+F900 is a COMPATIBILITY ideograph; it renders identically to
    # the URO 豈 (U+8C48) it decomposes to, so spell it as an escape
    # or this assertion silently tests the URO range instead
    assert single_script("\uf900") is Script.HAN
    assert single_script("\U00020bb7") is Script.HAN  # Ext B (𠮷)
    assert single_script("가") is Script.HANGUL
    assert single_script("힣") is Script.HANGUL  # last ASSIGNED syllable
    assert single_script("ힰ") is None          # jungseong, not a syllable
    assert single_script("ㄱ") is None          # bare jamo
