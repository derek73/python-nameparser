import unicodedata

from nameparser._lexicon import Lexicon
from nameparser._pipeline._vocab import (
    effective_script, is_initial, is_initial_shaped, is_suffix_lenient,
    is_suffix_strict, resolve_script_set, single_script,
)
from nameparser._policy import Script, _NO_INITIALS, _SCRIPT_RANGES

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


def test_is_initial_script_repertoire() -> None:
    # An initial is a single LETTER standing in for a name. Alphabets
    # have letters, so these are real initials ("А. С. Пушкин").
    assert is_initial("А.")    # Cyrillic
    assert is_initial("Α.")    # Greek
    assert is_initial("م.")    # Arabic
    assert is_initial("ה.")    # Hebrew
    assert is_initial("र.")    # Devanagari
    assert is_initial("Ա.")    # Armenian
    # Han ideographs, hangul syllables and kana are morphemes or
    # syllables -- a single one never stands in for a name (#320).
    assert not is_initial("씨.")
    assert not is_initial("様.")
    assert not is_initial("김.")
    assert not is_initial("さ.")
    assert not is_initial("ラ.")
    # unchanged: a digit is the visible edge of \w's reach, and the
    # shape half still owns it -- only the repertoire narrowed
    assert is_initial("2.")
    # unchanged: the SHAPE half still requires a single character
    assert not is_initial("राम.")


def test_is_initial_shaped_keeps_the_shape_half_reachable() -> None:
    """The two halves are separately askable (#320): assign's
    roman-numeral fork asks the SHAPE question about the piece before a
    trailing 'V', and answering it with the narrowed predicate dropped
    the family name out of 'John 씨. V' entirely."""
    for text in ("A.", "j.", "B", "2."):
        assert is_initial_shaped(text) is is_initial(text) is True
    for text in ("Jo", "b", "raam."):
        assert is_initial_shaped(text) is is_initial(text) is False
    # the whole difference between them, in both directions
    for text in ("씨.", "様.", "김.", "さ.", "ラ."):
        assert is_initial_shaped(text) and not is_initial(text)


def test_strict_suffix_veto_skips_cjk() -> None:
    """#320: the initial veto is what stopped a period-written CJK
    honorific being recognized. _normalize strips the trailing period,
    so '씨.' reaches the vocabulary as '씨' -- the veto was the only
    thing rejecting it."""
    lex = Lexicon(suffix_words=frozenset({"씨", "様"}))
    assert is_suffix_strict("씨.", lex)
    assert is_suffix_strict("様.", lex)


def _representative(script: Script) -> str:
    """The first codepoint of `script`'s _SCRIPT_RANGES spans that the
    SHAPE half admits as an initial. Shape-admitted, not simply the
    first codepoint: a range's first codepoint is often unassigned or
    punctuation (KATAKANA's 0x30A0 is a hyphen, HIRAGANA's 0x3040 is
    unassigned), which \\w does not match -- and testing is_initial on
    such a character answers False for the SHAPE's reason, making the
    repertoire assertion below vacuously green. Raising when no span
    holds one is the point rather than a corner: a script whose
    declared ranges contain no initial-shaped character at all has
    ranges that do not describe it."""
    for lo, hi in _SCRIPT_RANGES[script]:
        for cp in range(lo, hi + 1):
            if is_initial_shaped(chr(cp) + "."):
                return chr(cp)
    raise AssertionError(
        f"no character in _SCRIPT_RANGES[{script}] is initial-SHAPED, "
        f"so this script's declaration cannot be tested against "
        f"is_initial -- check that the ranges are that script's")


def test_every_script_is_classified_for_initials() -> None:
    """A member joining Script must be classified here on purpose;
    _policy._NO_INITIALS carries the reasoning.

    The classification lives in this table rather than the assertion
    being `set(Script) == set(_NO_INITIALS)`: that passes trivially
    today, since all four current members are CJK, and the only way to
    green it again after adding a script would be to declare that
    script initial-less. That prejudges the answer. The point is to
    force a decision, not a particular one.

    Three bindings, not two: the table covers Script, the table's
    False rows are _NO_INITIALS, and -- the one that makes this a
    behavioral test rather than a comparison of two constants -- each
    row is checked against is_initial on a character DERIVED from that
    script's own _SCRIPT_RANGES entry. Without the third, a script
    declared initial-less under ranges that are not its own passes all
    the way through while is_initial still says yes to its characters.
    """
    has_initials = {
        Script.HAN: False,       # ideographs are morphemes
        Script.HANGUL: False,    # syllable blocks
        Script.HIRAGANA: False,  # syllables
        Script.KATAKANA: False,  # syllables
    }
    assert set(has_initials) == set(Script), (
        "a Script member is unclassified for initials: decide whether "
        "a single character of it can stand in for a name, add the row, "
        "and put it in _policy._NO_INITIALS if it cannot")
    assert {s for s, yes in has_initials.items() if not yes} \
        == set(_NO_INITIALS), (
        "this table and _policy._NO_INITIALS disagree about which "
        "scripts have initials: a row here saying False is what puts a "
        "script in the constant, so add the missing member to "
        "_NO_INITIALS -- or, if the constant is the one that's right, "
        "flip the row")
    for script, yes in has_initials.items():
        char = _representative(script)
        assert is_initial(char + ".") is yes, (
            f"the declaration for {script} does not reach is_initial: "
            f"the row says has_initials={yes}, but is_initial("
            f"{char + '.'!r}) -- on a character taken from "
            f"_SCRIPT_RANGES[{script}] -- says {not yes}. Either the "
            f"ranges are not this script's, or _NO_INITIALS and the "
            f"repertoire predicate have come apart")


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
    # U+30A0 with no gap at all, and HAN's U+3005-U+3006 span sits just
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
