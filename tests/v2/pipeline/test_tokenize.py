import dataclasses

from nameparser._lexicon import Lexicon
from nameparser._pipeline._extract import extract_delimited
from nameparser._pipeline._state import ParseState
from nameparser._pipeline._tokenize import tokenize
from nameparser._policy import Policy
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


def test_comma_inside_extracted_region_is_not_an_offset() -> None:
    out = _tokenized('John "Jack, Jr" Kim')
    assert out.comma_offsets == ()
    nick = [t.text for t in out.tokens if t.role is Role.NICKNAME]
    assert nick == ["Jack", "Jr"]


def test_emoji_and_bidi_are_ignorable_by_policy() -> None:
    out = _tokenized("John‏ \U0001f600Smith")
    assert [t.text for t in out.tokens] == ["John", "Smith"]
    keep = dataclasses.replace(Policy(), strip_emoji=False, strip_bidi=False)
    out2 = _tokenized("John \U0001f600Smith", keep)
    assert [t.text for t in out2.tokens] == ["John", "\U0001f600Smith"]


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
