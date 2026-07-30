import unicodedata

from nameparser._lexicon import Lexicon
from nameparser._pipeline._vocab import (
    _SCRIPT_RANGES, effective_script, is_initial, is_suffix_lenient,
    is_suffix_strict, resolve_script_set, single_script,
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
    # kana classifies as its own script (#272), not HAN -- was None
    # before kana had a table entry; single_script's job is telling
    # kana apart from Han, not lumping the two together
    assert single_script("イチロー") is Script.KATAKANA


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


def test_single_script_empty_string_is_no_script() -> None:
    assert single_script("") is None


def test_no_script_range_reaches_ascii() -> None:
    # single_script short-circuits on an ASCII token instead of
    # sweeping the ranges (the hot path: every Latin name). The
    # classifications above stay pinned either way; what the shortcut
    # rests on is this floor, so a future script entry that dips below
    # it fails here rather than silently going unclassified.
    assert all(lo >= 0x80
               for ranges in _SCRIPT_RANGES.values() for lo, _ in ranges)


def test_kana_singles_classify() -> None:
    assert single_script("みなみ") is Script.HIRAGANA
    assert single_script("エミ") is Script.KATAKANA
    assert single_script("ー") is Script.KATAKANA   # prolonged mark, in-block


def test_effective_script_kana_license() -> None:
    # pure single-script tokens pass through unchanged
    assert effective_script("山田") is Script.HAN
    assert effective_script("みなみ") is Script.HIRAGANA
    assert effective_script("マイケル") is Script.KATAKANA
    # the license: a MIXED token wholly in Han∪kana is Japanese and
    # resolves to the HIRAGANA carrier entry
    assert effective_script("高橋みなみ") is Script.HIRAGANA  # kanji+hira
    assert effective_script("山田エミ") is Script.HIRAGANA    # kanji+kata
    assert effective_script("さくらエミ") is Script.HIRAGANA  # hira+kata
    # outside the license: anything beyond the JA repertoire
    assert effective_script("毛김") is None
    assert effective_script("山田x") is None
    # NOT None: U+30FB sits INSIDE the katakana block (verified by
    # codepoint), so this stays a PURE-katakana token, same as
    # "マイケル" above -- the license only ever fires on a MIXED
    # token, and this one isn't mixed. It has no order-default entry
    # (DEFAULT_SCRIPT_ORDERS carries no KATAKANA key), which is where
    # "declines the license" actually shows up. tokenize (#272 Task 2b)
    # now turns U+30FB into a token separator, so this exact string
    # arrives at effective_script as two tokens during a real parse --
    # this unit test calls effective_script directly on the whole
    # string, bypassing tokenize, so it still sees the dot and must
    # keep passing unchanged.
    assert effective_script("マイケル・ジャクソン") is Script.KATAKANA
    assert effective_script("") is None


def test_resolve_script_set_generalizes_the_license_across_pieces() -> None:
    # a single script passes through as-is, including a script with no
    # order-default entry (KATAKANA): the caller decides what to do
    # with that, this function only reports what was found
    assert resolve_script_set([Script.HAN]) is Script.HAN
    assert resolve_script_set([Script.HAN, Script.HAN]) is Script.HAN
    assert resolve_script_set([Script.KATAKANA]) is Script.KATAKANA
    # the license, generalized: Han + Hiragana across two SEPARATE,
    # individually single-script pieces (never mixed within one
    # token) is exactly the repertoire effective_script licenses
    # inside a single token, so it collapses to the carrier key
    assert resolve_script_set([Script.HAN, Script.HIRAGANA]) \
        is Script.HIRAGANA
    assert resolve_script_set([Script.HAN, Script.KATAKANA]) \
        is Script.HIRAGANA
    assert resolve_script_set([Script.HIRAGANA, Script.KATAKANA]) \
        is Script.HIRAGANA
    # outside the license: Han+Hangul is two real scripts, neither
    # kana -- no single tradition, so this declines like the caller's
    # own None (Latin, mixed, empty)
    assert resolve_script_set([Script.HAN, Script.HANGUL]) is None
    assert resolve_script_set([]) is None


def test_nfd_katakana_still_classifies_and_declines_the_license() -> None:
    # Built via normalize(), never pasted as decomposed literals --
    # NFD "ガガ" is base katakana カ + COMBINING VOICED SOUND MARK
    # (U+3099) twice; U+3099 sits in the HIRAGANA block, not
    # katakana's, so classifying raw NFD text would see one char from
    # each block and either call it mixed (single_script: None) or
    # wrongly grant the kana license (effective_script: HIRAGANA) for
    # what is really one pure-katakana token. NFC-normalizing first
    # (the #272 amendment's NFC decision) recomposes it back to ガガ,
    # which reads as ordinary katakana either way -- the license
    # still correctly declines, because this token isn't mixed.
    nfd = unicodedata.normalize("NFD", "ガガ")
    assert nfd != "ガガ"  # sanity: confirms the decomposition actually ran
    assert single_script(nfd) is Script.KATAKANA
    assert effective_script(nfd) is Script.KATAKANA


def test_nfd_hangul_still_classifies() -> None:
    # NFD decomposes each precomposed syllable onto 2-3 jamo
    # (U+1100-U+11FF), entirely outside the HANGUL range -- raw NFD
    # input would silently miss the shipped family-first order rule
    # rather than merely misclassify. Built via normalize(), not
    # pasted decomposed literals, same reason as above.
    nfd = unicodedata.normalize("NFD", "김민준")
    assert nfd != "김민준"  # sanity: confirms the decomposition actually ran
    assert single_script(nfd) is Script.HANGUL


def test_script_ranges_are_pairwise_disjoint() -> None:
    # The table's own comment states this invariant and nothing
    # checked it: single_script returns the FIRST covering entry (dict
    # iteration order), so any overlap would make the answer depend on
    # declaration order instead of being well-defined. Compared over
    # every entry of every script rather than script by script,
    # because the adjacent blocks are exactly where a future edit
    # would go wrong -- HIRAGANA ends at U+309F and KATAKANA opens at
    # U+30A0 with no gap at all, and HAN's singleton U+3005 sits just
    # below both.
    spans = [(lo, hi, script)
             for script, ranges in _SCRIPT_RANGES.items()
             for lo, hi in ranges]
    assert len(spans) > 1        # never passes vacuously
    for i, (lo, hi, script) in enumerate(spans):
        assert lo <= hi, f"{script} range ({lo:#x}, {hi:#x}) is inverted"
        for other_lo, other_hi, other in spans[i + 1:]:
            assert hi < other_lo or other_hi < lo, (
                f"{script} range ({lo:#x}, {hi:#x}) overlaps {other} "
                f"range ({other_lo:#x}, {other_hi:#x})")
