import dataclasses
import unicodedata

import pytest

from nameparser._lexicon import Lexicon
from nameparser._pipeline._extract import extract_delimited
from nameparser._pipeline._state import ParseState
from nameparser._pipeline import _tokenize
from nameparser._pipeline._tokenize import tokenize
from nameparser import _policy
from nameparser._policy import Policy, Script
from nameparser._types import Role


def _tokenized(text: str, policy: Policy | None = None) -> ParseState:
    state = ParseState(original=text, lexicon=Lexicon.empty(),
                       policy=policy or Policy())
    return tokenize(extract_delimited(state))


def test_whitespace_split_with_spans() -> None:
    out = _tokenized("John  Smith")
    assert [(t.text, tuple(t.span)) for t in out.tokens] == [
        ("John", (0, 4)), ("Smith", (6, 11)),
    ]
    assert all(t.role is None for t in out.tokens)


def test_provenance_text_equals_original_slice() -> None:
    out = _tokenized(" Dr.  Juan  de la Vega ")
    for t in out.tokens:
        assert t.text == out.original[t.span.start:t.span.end]


def test_commas_are_separators_and_recorded() -> None:
    out = _tokenized("Smith, John")
    assert [t.text for t in out.tokens] == ["Smith", "John"]
    assert out.comma_offsets == (5,)


def test_fullwidth_and_arabic_commas_segment() -> None:
    out = _tokenized("سميث، جون")
    assert out.comma_offsets == (4,)
    out2 = _tokenized("山田，太郎")
    assert out2.comma_offsets == (2,)


def test_extracted_regions_are_skipped_and_tokenized_with_role() -> None:
    out = _tokenized('John "Jack Jr" Kennedy')
    main = [(t.text, t.role) for t in out.tokens if t.role is None]
    nick = [(t.text, t.role) for t in out.tokens if t.role is Role.NICKNAME]
    assert main == [("John", None), ("Kennedy", None)]
    assert nick == [("Jack", Role.NICKNAME), ("Jr", Role.NICKNAME)]
    # tokens are span-sorted overall
    starts = [t.span.start for t in out.tokens]
    assert starts == sorted(starts)


def test_two_simultaneous_extracted_regions_interleave_correctly() -> None:
    # tokenize's masked/extracted loops each run over ALL their regions
    # before the final span-sort; every other test here exercises at
    # most one masked region at a time. With two active extraction
    # types (nickname parens AND a configured maiden bracket) on the
    # same string, main-stream and both extracted regions must still
    # interleave into the correct overall span order.
    pol = Policy(maiden_delimiters=frozenset({("[", "]")}))
    out = _tokenized("John (Jack) [Doe] Smith", pol)
    assert [(t.text, t.role) for t in out.tokens] == [
        ("John", None),
        ("Jack", Role.NICKNAME),
        ("Doe", Role.MAIDEN),
        ("Smith", None),
    ]
    starts = [t.span.start for t in out.tokens]
    assert starts == sorted(starts)


def test_comma_inside_extracted_region_is_word_text_not_an_offset() -> None:
    # #653: a region segments nothing, so its comma is punctuation the
    # clause keeps, like ';' -- the view then renders 'Jack, Jr'
    out = _tokenized('John "Jack, Jr" Kim')
    assert out.comma_offsets == ()
    nick = [t.text for t in out.tokens if t.role is Role.NICKNAME]
    assert nick == ["Jack,", "Jr"]


def test_emoji_and_bidi_are_ignorable_by_policy() -> None:
    out = _tokenized("John‏ \U0001f600Smith")
    assert [t.text for t in out.tokens] == ["John", "Smith"]
    keep = dataclasses.replace(Policy(), strip_emoji=False, strip_bidi=False)
    out2 = _tokenized("John \U0001f600Smith", keep)
    assert [t.text for t in out2.tokens] == ["John", "\U0001f600Smith"]


_KEEP_ALL = Policy(strip_emoji=False, strip_bidi=False)


@pytest.mark.parametrize("policy", [Policy(), _KEEP_ALL],
                         ids=["default", "keep-emoji-and-bidi"])
@pytest.mark.parametrize("ch", ["​", "\u2063", "﻿"],
                         ids=["zero-width-space", "invisible-separator",
                              "byte-order-mark"])
def test_the_invisible_separators_separate_under_every_policy(
        ch: str, policy: Policy) -> None:
    # #851: no opt-out reaches them -- neither strip switch covers
    # them, since none is an emoji or a direction control; U+2063, the
    # invisible separator, is the one whose Unicode name says what it is
    for text, words in [(f"John{ch}Smith", ["John", "Smith"]),
                        (f"{ch}Dr. John", ["Dr.", "John"]),
                        (f"John {ch}Smith{ch}", ["John", "Smith"])]:
        state = _tokenized(text, policy)
        assert [t.text for t in state.tokens] == words
        assert all(state.original[t.span.start:t.span.end] == t.text
                   for t in state.tokens)
        assert state.comma_offsets == ()


@pytest.mark.parametrize("ch", ["‌", "‍", "⁠", "­",
                                "\u2061", "\u2062", "\u2064", "\u180e"],
                         ids=["zwnj", "zwj", "word-joiner", "soft-hyphen",
                              "function-application", "invisible-times",
                              "invisible-plus", "mongolian-vowel-separator"])
def test_joiners_and_soft_hyphen_stay_inside_the_word(ch: str) -> None:
    # #851's exclusions: ZWNJ and ZWJ decide how the letters beside
    # them join, the word joiner means no break, and the soft hyphen
    # marks a break inside one word, so splitting at any of them would
    # cut a real word in two. The invisible math operators beside
    # U+2063 join operands rather than separate words, and the
    # Mongolian vowel separator shapes the letters beside it
    assert [t.text for t in _tokenized(f"ab{ch}cd ef").tokens] == [
        f"ab{ch}cd", "ef"]


def test_zero_width_space_defeats_the_flank_guard_like_a_space() -> None:
    # #851: a separator, not a stripped mark, so beside the interpunct
    # it reads as whitespace does, not as U+200F does
    spaced = _tokenized("威廉· 莎士比亚")
    zwsp = _tokenized("威廉·​莎士比亚")
    assert [t.text for t in zwsp.tokens] == [t.text for t in spaced.tokens]
    assert zwsp.interpunct_offsets == spaced.interpunct_offsets == ()


def test_empty_and_whitespace_yield_no_tokens() -> None:
    assert _tokenized("").tokens == ()
    assert _tokenized("   ").tokens == ()


def test_nakaguro_separates_and_enters_no_token() -> None:
    # U+30FB divides transcribed foreign names (マイケル・ジャクソン);
    # native names never contain it -- amendment 2026-07-29 section 1b
    state = _tokenized("マイケル・ジャクソン")
    assert [t.text for t in state.tokens] == ["マイケル", "ジャクソン"]
    assert all(state.original[t.span.start:t.span.end] == t.text
               for t in state.tokens)
    # like whitespace, and unlike COMMA_CHARS: it never records an offset
    assert state.comma_offsets == ()
    # leading/trailing dots are plain separators, not content
    assert [t.text for t in _tokenized("・ジャクソン").tokens] == ["ジャクソン"]


def test_nakaguro_next_to_a_real_comma_still_only_the_comma_offsets() -> None:
    # the dot and a real comma side by side must not blur together --
    # the comma still segments and records; the dot still separates
    # and stays silent
    state = _tokenized("マイケル・, X")
    assert [t.text for t in state.tokens] == ["マイケル", "X"]
    assert state.comma_offsets == (5,)


def test_interpunct_splits_between_classified_characters() -> None:
    state = _tokenized("威廉·莎士比亚")
    assert [t.text for t in state.tokens] == ["威廉", "莎士比亚"]
    assert state.interpunct_offsets == (2,)


def test_interpunct_stays_in_latin_names() -> None:
    # the Catalan punt volat is INTERIOR to names; Latin neighbors
    # never qualify
    state = _tokenized("Gal·la Marcet")
    assert [t.text for t in state.tokens] == ["Gal·la", "Marcet"]
    assert state.interpunct_offsets == ()


def test_interpunct_between_kana_splits() -> None:
    # sloppy-IME katakana transcription
    state = _tokenized("マイケル·ジャクソン")
    assert [t.text for t in state.tokens] == ["マイケル", "ジャクソン"]


# rules/T3 on hangul typed decomposed (#1087): the flank guard reads raw
# characters, so it sees the conjoining jamo a decomposed syllable is
# written in. Each row: the text, its tokens composed, and the tokens
# with the HANGUL range back at the precomposed syllables alone, the
# table before #1087 (recorded 2026-11-05; the control below re-takes it
# live).
_DECOMPOSED_FLANKS = [
    ("이서연·김민준", ["이서연", "김민준"], ["이서연·김민준"]),
    ("김·민준", ["김", "민준"], ["김·민준"]),
    # one row per jamo span, the extended ones archaic and composing to
    # nothing, so their tokens are their own text
    ("ꥠᅡ·김민준", ["ꥠᅡ", "김민준"], ["ꥠᅡ·김민준"]),
    ("김ힰ·김민준", ["김ힰ", "김민준"], ["김ힰ·김민준"]),
    # half-flanked: a Latin neighbour never qualifies, in either table
    ("김민준·Smith", ["김민준·Smith"], ["김민준·Smith"]),
]


@pytest.mark.parametrize(("text", "tokens"),
                         [(text, tokens) for text, tokens, _ in _DECOMPOSED_FLANKS])
def test_interpunct_beside_decomposed_hangul_reads_as_composed(
        text: str, tokens: list[str]) -> None:
    nfd = unicodedata.normalize("NFD", text)
    assert nfd != text  # sanity: the decomposition ran
    got = [unicodedata.normalize("NFC", t.text) for t in _tokenized(nfd).tokens]
    assert got == tokens
    # the composed twin reads the same
    assert [t.text for t in _tokenized(text).tokens] == tokens


@pytest.mark.parametrize(("text", "unguarded"),
                         [(text, unguarded) for text, _, unguarded in _DECOMPOSED_FLANKS])
def test_decomposed_flank_control_without_the_jamo_range(
        monkeypatch: pytest.MonkeyPatch, text: str, unguarded: list[str]) -> None:
    # the negative control: the flank classifier rebuilt by the shipped
    # factory over a table whose HANGUL holds the syllables alone
    monkeypatch.setitem(_policy._SCRIPT_RANGES, Script.HANGUL,
                        (_policy._HANGUL_SYLLABLES,))
    monkeypatch.setattr(_tokenize, "_classified_char", _policy._script_matcher(
        *_policy._SCRIPT_RANGES, whole=True))
    nfd = unicodedata.normalize("NFD", text)
    got = [unicodedata.normalize("NFC", t.text) for t in _tokenized(nfd).tokens]
    assert got == unguarded


def test_the_decomposed_flank_control_moves_a_row() -> None:
    assert any(row[1] != row[2] for row in _DECOMPOSED_FLANKS)


def test_interpunct_at_edges_stays() -> None:
    # no classified neighbor on one side: not a divider position
    state = _tokenized("·威廉")
    assert [t.text for t in state.tokens] == ["·威廉"]


def test_stripped_bidi_mark_is_transparent_to_the_flank_guard() -> None:
    # an RTL document quoting a transcription: U+200F beside the dot,
    # visually identical to the clean form -- the stripped mark must
    # not occupy a flank position
    state = _tokenized("威廉‏·莎士比亚")
    assert [t.text for t in state.tokens] == ["威廉", "莎士比亚"]
    assert state.interpunct_offsets != ()


def test_stripped_emoji_is_transparent_to_the_flank_guard() -> None:
    state = _tokenized("威廉\U0001f600·莎士比亚")
    assert [t.text for t in state.tokens] == ["威廉", "莎士比亚"]


def test_unstripped_bidi_mark_defeats_the_guard() -> None:
    # the contrast: with strip_bidi off the mark is real token text,
    # an unclassified flank -- the dot stays interior
    state = _tokenized("威廉‏·莎士比亚",
                       policy=Policy(strip_bidi=False))
    assert state.interpunct_offsets == ()


def test_interpunct_trailing_edge_stays() -> None:
    # the upper bound: a trailing dot has no right flank -- and
    # dropping the bound is an IndexError, not a wrong answer
    state = _tokenized("威廉·")
    assert [t.text for t in state.tokens] == ["威廉·"]


def test_interpunct_minimal_flanks_split() -> None:
    state = _tokenized("威·廉")
    assert [t.text for t in state.tokens] == ["威", "廉"]
    assert state.interpunct_offsets == (1,)


def test_interpunct_one_sided_flank_stays() -> None:
    # the AND in the guard: one classified neighbor is not enough,
    # and no offset records (a spurious record would fake the
    # transcription marker downstream)
    state = _tokenized("Anna·威")
    assert [t.text for t in state.tokens] == ["Anna·威"]
    assert state.interpunct_offsets == ()


def test_hangul_flanks_split_and_record() -> None:
    # Korean writes transcribed foreign names with the interpunct too
    # (마틴·루터·킹) -- hangul flanks are classified flanks
    state = _tokenized("김·민준")
    assert [t.text for t in state.tokens] == ["김", "민준"]
    assert state.interpunct_offsets == (1,)


def test_interpunct_in_delimited_regions_splits_but_does_not_record() -> None:
    # a B7 inside a nickname must not mark the OUTER name as a
    # transcription -- same flag that keeps nickname commas out of
    # comma_offsets
    state = _tokenized("山田 太郎 (マイケル·ジャクソン)")
    assert state.interpunct_offsets == ()
    assert "マイケル" in [t.text for t in state.tokens]


def test_nakaguro_never_records() -> None:
    # the Japanese dot is roster/divider typography, not the
    # transcription marker: it separates (#272) and records nothing --
    # 高橋・一郎 keeps its family-first roster reading downstream
    state = _tokenized("威廉・莎士比亚")
    assert [t.text for t in state.tokens] == ["威廉", "莎士比亚"]
    assert state.interpunct_offsets == ()


def test_halfwidth_nakaguro_separates_too() -> None:
    # U+FF65 between halfwidth katakana -- build the string from
    # escapes and VERIFY the codepoints (the U+F900 homoglyph lesson):
    # ﾏｲｹﾙ = halfwidth マイケル (MA I KE RU),
    # ･ = the halfwidth dot, ｼﾞｬｸｿﾝ =
    # halfwidth ジャクソン (SI + voiced-sound-mark, small-YA, KU, SO, N)
    text = ("\uff8f\uff72\uff79\uff99"   # \uff8f\uff72\uff79\uff99 = halfwidth MA I KE RU
            "\uff65"                       # \uff65 = halfwidth middle dot
            "\uff7c\uff9e\uff6c\uff78\uff7f\uff9d")  # halfwidth SI+voice, small-YA, KU, SO, N
    # belt and braces: the escapes above must spell the halfwidth dot,
    # not the fullwidth U+30FB it could be confused for by eye -- and
    # this is exactly the check the un-escaped version was missing:
    # it would still pass with U+30FB substituted for U+FF65
    assert "･" in text
    state = _tokenized(text)
    assert len(state.tokens) == 2
    assert "･" not in "".join(t.text for t in state.tokens)


@pytest.mark.parametrize("text, words, commas", [
    # #1202: the Ethiopic and Burmese commas segment like ',' does,
    # glued or spaced, and record an offset
    ("ከበደ፣ አበበ", ["ከበደ", "አበበ"], (3,)),
    ("ከበደ ፣ አበበ", ["ከበደ", "አበበ"], (4,)),
    ("မောင်မောင်ခ၊ ဦး", ["မောင်မောင်ခ", "ဦး"], (11,)),
    # the Ethiopic wordspace divides like the nakaguro (rules/T2) and,
    # like it, records no offset
    ("አበበ፡ከበደ፡ተሰማ", ["አበበ", "ከበደ", "ተሰማ"], ()),
    ("አበበ፡ ከበደ፡ ተሰማ", ["አበበ", "ከበደ", "ተሰማ"], ()),
])
def test_ethiopic_and_burmese_separators(text: str, words: list[str],
                                         commas: tuple[int, ...]) -> None:
    state = _tokenized(text)
    assert [t.text for t in state.tokens] == words
    assert state.comma_offsets == commas


_KHORLOO = "ᠬᠣᠷᠯᠤ᠎ᠠ"  # the stem, holding the vowel separator U+180E
_YIN = "ᠶ᠋ᠢᠨ"  # the genitive suffix, holding a variation selector


@pytest.mark.parametrize("text, words", [
    # #1236: between two Mongolian letters U+202F is the suffix
    # connector and joins the suffix to its stem
    (f"{_KHORLOO} {_YIN} ᠴᠣᠢᠢᠪᠠᠯᠰᠠᠩ",
     [f"{_KHORLOO} {_YIN}", "ᠴᠣᠢᠢᠪᠠᠯᠰᠠᠩ"]),
    ("ᠯᠤᠪᠰᠠᠩᠨᠠᠮᠰᠠᠷᠠᠢ ᠢᠢᠨ ᠣᠶᠤᠨ-ᠡᠷᠳᠡᠨᠢ",
     ["ᠯᠤᠪᠰᠠᠩᠨᠠᠮᠰᠠᠷᠠᠢ ᠢᠢᠨ", "ᠣᠶᠤᠨ-ᠡᠷᠳᠡᠨᠢ"]),
    # anywhere else it is the narrow space it is named for: between
    # Latin letters, beside one Mongolian letter, before French ':',
    # and at a string's edge
    ("Jean Dupont", ["Jean", "Dupont"]),
    ("ᠴᠣᠢᠢᠪᠠᠯᠰᠠᠩ Smith", ["ᠴᠣᠢᠢᠪᠠᠯᠰᠠᠩ", "Smith"]),
    ("Smith ᠴᠣᠢᠢᠪᠠᠯᠰᠠᠩ", ["Smith", "ᠴᠣᠢᠢᠪᠠᠯᠰᠠᠩ"]),
    ("Jean : Dupont", ["Jean", ":", "Dupont"]),
    (" ᠴᠣᠢᠢᠪᠠᠯᠰᠠᠩ ", ["ᠴᠣᠢᠢᠪᠠᠯᠰᠠᠩ"]),
    # Mongolian punctuation and digits are no letters: the comma U+1802
    # and the digit one U+1811 beside it leave it a space
    ("ᠴᠣᠢ᠂ ᠪᠠᠯ", ["ᠴᠣᠢ᠂", "ᠪᠠᠯ"]),
    ("ᠴᠣᠢ ᠑", ["ᠴᠣᠢ", "᠑"]),
    # a plain space before the suffix still divides (decisions/T1)
    (f"{_KHORLOO} {_YIN}", [_KHORLOO, _YIN]),
])
def test_narrow_no_break_space_joins_only_between_mongolian_letters(
        text: str, words: list[str]) -> None:
    assert [t.text for t in _tokenized(text).tokens] == words
