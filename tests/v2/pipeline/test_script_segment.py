"""Stage: script_segment (#271, #272) -- unspaced CJK splitting, by
vocabulary and by the pluggable segmenter behind it."""
import dataclasses

import pytest

from nameparser import Parser
from nameparser._lexicon import Lexicon
from nameparser._pipeline._script_segment import script_segment
from nameparser._pipeline._segment import segment
from nameparser._pipeline._state import (
    ParseState, PendingAmbiguity, Structure,
)
from nameparser._pipeline._tokenize import tokenize
from nameparser._policy import Policy, Script
from nameparser._types import AmbiguityKind, Segmentation, Segmenter

_HAN = Policy(segment_scripts=frozenset({Script.HAN}))
_HANGUL = Policy()      # HANGUL is the default activation
# the JA pack's own activation (amendment 2026-07-29): HIRAGANA is the
# kana license's carrier key, so a kanji+kana composite gates in
# through it; KATAKANA is deliberately absent from every set.
_JA = Policy(segment_scripts=frozenset({Script.HAN, Script.HIRAGANA}))
# 欧 AND 欧阳 both present on purpose: compound-before-single must
# pick 欧阳 (the issue's own acceptance example); same for 남/남궁.
# "jr" so the comma cases can reach SUFFIX_COMMA.
_LEX = Lexicon(surnames=frozenset({"毛", "欧", "欧阳", "김", "남", "남궁"}),
               suffix_words=frozenset({"jr"}))


def _run(text: str, policy: Policy = _HAN, lexicon: Lexicon = _LEX,
         segmenter: Segmenter | None = None) -> ParseState:
    state = ParseState(original=text, lexicon=lexicon, policy=policy,
                       segmenter=segmenter)
    return script_segment(segment(tokenize(state)))


def _texts(state: ParseState) -> list[str]:
    return [t.text for t in state.tokens]


def _fake(splits: tuple[int, ...],
          confidence: float | None = None) -> Segmenter:
    """A segmenter that gives the same answer whatever it is handed:
    every case below pins what the STAGE does with an answer, not how a
    real segmenter arrives at one (no external dependency here)."""
    def segmenter(text: str) -> Segmentation | None:
        return Segmentation(splits, confidence=confidence)
    return segmenter


def _declines(text: str) -> Segmentation | None:
    return None


def test_splits_leading_surname_and_spans_index_the_original() -> None:
    state = _run("毛泽东")
    assert _texts(state) == ["毛", "泽东"]
    assert [(t.span.start, t.span.end) for t in state.tokens] == [
        (0, 1), (1, 3)]
    assert all(state.original[t.span.start:t.span.end] == t.text
               for t in state.tokens)


def test_compound_before_single() -> None:
    assert _texts(_run("欧阳明")) == ["欧阳", "明"]
    assert _texts(_run("남궁민수", policy=_HANGUL)) == ["남궁", "민수"]


def test_hangul_splits_under_the_default_policy() -> None:
    assert _texts(_run("김민준", policy=_HANGUL)) == ["김", "민준"]


def test_han_needs_the_opt_in() -> None:
    # default policy activates HANGUL only: Han tokens stay whole
    assert _texts(_run("毛泽东", policy=_HANGUL)) == ["毛泽东"]


def test_inert_without_surname_vocabulary() -> None:
    assert _texts(_run("毛泽东", lexicon=Lexicon.empty())) == ["毛泽东"]


def test_inert_with_segmentation_disabled() -> None:
    off = Policy(segment_scripts=())  # type: ignore[arg-type]
    assert _texts(_run("김민준", policy=off)) == ["김민준"]


def test_whole_token_surname_does_not_split() -> None:
    # a bare surname has nothing to split off; a lone token's role is
    # the order resolution's call, not this stage's. The trap: 欧 and
    # 남 are ALSO listed, so without the whole-token guard these
    # would split 欧+阳 / 남+궁 by the shorter prefix
    assert _texts(_run("欧阳")) == ["欧阳"]
    assert _texts(_run("남궁", policy=_HANGUL)) == ["남궁"]


def test_no_match_leaves_the_token_alone() -> None:
    assert _texts(_run("阿明")) == ["阿明"]


def test_only_the_first_script_token_is_considered() -> None:
    assert _texts(_run("毛泽东 毛泽东")) == ["毛", "泽东", "毛泽东"]


def test_leading_non_script_token_is_skipped_over() -> None:
    assert _texts(_run("Dr 毛泽东")) == ["Dr", "毛", "泽东"]


def test_mixed_script_token_is_not_split() -> None:
    assert _texts(_run("毛zedong")) == ["毛zedong"]


def test_first_script_token_decides_even_on_no_match() -> None:
    # no fallthrough: the front of the name is the only surname site
    assert _texts(_run("阿明 毛泽东")) == ["阿明", "毛泽东"]


def test_compound_fork_emits_segmentation_ambiguity() -> None:
    # both 欧阳+明 and 欧+阳明 are vocabulary-supported: the stage
    # decided a fork, and the pipeline contract is that deciding
    # stages record it (indices = the two result tokens)
    out = _run("欧阳明")
    assert [a.kind for a in out.ambiguities] == [
        AmbiguityKind.SEGMENTATION]
    assert out.ambiguities[0].indices == (0, 1)
    # the documented promise: detail names BOTH readings
    detail = out.ambiguities[0].detail
    assert "欧阳" in detail and "明" in detail
    assert "阳明" in detail
    ko = _run("남궁민수", policy=_HANGUL)
    assert [a.kind for a in ko.ambiguities] == [
        AmbiguityKind.SEGMENTATION]


def test_single_possible_split_emits_no_ambiguity() -> None:
    # only 毛 matches: no fork, no noise
    assert _run("毛泽东").ambiguities == ()
    assert _run("김민준", policy=_HANGUL).ambiguities == ()


def test_family_comma_is_inert() -> None:
    # the comma declared the family: splitting it would invent a
    # boundary the writer did not draw ("남궁 민수" with a space)
    out = _run("남궁민수, 지훈", policy=_HANGUL)
    assert out.structure is Structure.FAMILY_COMMA
    assert _texts(out) == ["남궁민수", "지훈"]
    assert out.ambiguities == ()


def test_family_comma_given_side_untouched() -> None:
    assert _texts(_run("박, 남궁민수", policy=_HANGUL)) == [
        "박", "남궁민수"]


def test_one_word_before_the_comma_is_never_suffix_comma() -> None:
    # an unspaced CJK name is ONE word, and segment's suffix-comma
    # rule needs >1 word before the comma -- so this reads as
    # FAMILY_COMMA and the opt-out above covers it too
    out = _run("김민준, Jr.", policy=_HANGUL)
    assert out.structure is Structure.FAMILY_COMMA
    assert _texts(out) == ["김민준", "Jr."]


def test_suffix_comma_name_part_still_splits() -> None:
    out = _run("Dr 김민준, Jr.", policy=_HANGUL)
    assert out.structure is Structure.SUFFIX_COMMA
    assert _texts(out) == ["Dr", "김", "민준", "Jr."]


def test_segments_remap_after_the_split() -> None:
    out = _run("Dr 김민준, Jr.", policy=_HANGUL)
    # name segment gains the second half in place; the suffix
    # segment's index follows the token it names
    assert out.segments == ((0, 1, 2), (3,))
    assert [[out.tokens[i].text for i in run] for run in out.segments] \
        == [["Dr", "김", "민준"], ["Jr."]]


def test_ambiguity_indices_shift_past_the_split() -> None:
    state = segment(tokenize(ParseState(
        original="毛泽东 X", lexicon=_LEX, policy=_HAN)))
    state = dataclasses.replace(state, ambiguities=(
        PendingAmbiguity(AmbiguityKind.UNBALANCED_DELIMITER,
                         "synthetic", indices=(0,)),
        PendingAmbiguity(AmbiguityKind.UNBALANCED_DELIMITER,
                         "synthetic", indices=(1,)),
    ))
    out = script_segment(state)
    # index 0 (the split token itself) stays; index 1 moves right
    assert out.ambiguities[0].indices == (0,)
    assert out.ambiguities[1].indices == (2,)


def test_the_real_fold_splits_and_keeps_the_stage_after_segment() -> None:
    # the stage-order contract end to end: a set-comparison ownership
    # test cannot catch a reorder, but this can -- placed before
    # segment, the split would feed segment two words where the writer
    # wrote one and turn the family-comma parse below into a
    # suffix-comma one
    p = Parser(lexicon=_LEX, policy=_HANGUL)
    plain = p.parse("김민준")
    assert (plain.family, plain.given) == ("김", "민준")
    declared = p.parse("남궁민수, 지훈")
    assert (declared.family, declared.given) == ("남궁민수", "지훈")


def test_delimited_only_input_reaches_the_empty_segments_guard() -> None:
    # extraction masks the whole string, so segment produces no runs
    # at all -- the guard the stage-level helper above cannot reach
    nick = Parser(lexicon=_LEX, policy=_HANGUL).parse("(민준)")
    assert nick.nickname == "민준"


# -- the pluggable segmenter, consulted on decline (#272) ---------------


def test_segmenter_splits_on_vocabulary_decline() -> None:
    # the baseline: with no segmenter configured a declined token is
    # simply left whole, so every split below is the hook's doing
    assert _texts(_run("山田太郎", policy=_JA)) == ["山田太郎"]
    # 山田太郎 has no vocabulary surname prefix at all, so the
    # vocabulary declines and the token reaches the segmenter
    state = _run("山田太郎", policy=_JA, segmenter=_fake((2,)))
    assert _texts(state) == ["山田", "太郎"]
    assert [(t.span.start, t.span.end) for t in state.tokens] == [
        (0, 2), (2, 4)]
    assert all(state.original[t.span.start:t.span.end] == t.text
               for t in state.tokens)


def test_vocabulary_wins_over_the_segmenter() -> None:
    # precedence, and the reason parser_for(ZH, JA, segmenter=...)
    # composes: a matched surname is a dictionary certainty, so the
    # segmenter is not even asked
    asked: list[str] = []

    def seg(text: str) -> Segmentation | None:
        asked.append(text)
        return Segmentation((2,))

    state = _run("毛泽东", policy=_JA, segmenter=seg)
    assert _texts(state) == ["毛", "泽东"]
    assert asked == []


def test_segmenter_decline_and_confident_whole_are_distinct() -> None:
    # two different ANSWERS -- None is "I don't know", () is
    # "confidently one token" -- with the same effect on the tokens:
    # the difference is the protocol's to carry, not this stage's
    for seg in (_declines, _fake(())):
        out = _run("山田太郎", policy=_JA, segmenter=seg)
        assert _texts(out) == ["山田太郎"]
        assert out.ambiguities == ()   # nothing decided, nothing to report


def test_kana_licensed_token_gates_in_for_the_segmenter() -> None:
    # the gate reads effective_script, not single_script: 高橋みなみ is
    # mixed Han+hiragana, which the kana license resolves to the
    # HIRAGANA carrier entry -- and HIRAGANA is in the JA activation
    state = _run("高橋みなみ", policy=_JA, segmenter=_fake((2,)))
    assert _texts(state) == ["高橋", "みなみ"]


def test_pure_katakana_never_gates_in() -> None:
    # the license's other half: a lone katakana token is predominantly
    # a transcribed foreign name, so KATAKANA sits in no activation set
    # and no segmenter is consulted for one
    out = _run("マイケル", policy=_JA, segmenter=_fake((2,)))
    assert _texts(out) == ["マイケル"]
    assert out.ambiguities == ()


def test_kana_licensed_token_stays_whole_under_default_policy() -> None:
    # the pack IS the language declaration: without it the default
    # activation is HANGUL alone, so nothing gates in and the
    # configured segmenter is inert
    out = _run("高橋みなみ", segmenter=_fake((2,)))
    assert _texts(out) == ["高橋みなみ"]
    assert out.ambiguities == ()


def test_segmenter_multi_split_produces_n_plus_one_tokens() -> None:
    # n cuts make n+1 sub-slices, and every index the earlier stages
    # recorded shifts by n rather than by one
    state = segment(tokenize(ParseState(
        original="山田太 X", lexicon=_LEX, policy=_JA,
        segmenter=_fake((1, 2)))))
    state = dataclasses.replace(state, ambiguities=(
        PendingAmbiguity(AmbiguityKind.UNBALANCED_DELIMITER,
                         "synthetic", indices=(1,)),))
    out = script_segment(state)
    assert _texts(out) == ["山", "田", "太", "X"]
    assert [(t.span.start, t.span.end) for t in out.tokens] == [
        (0, 1), (1, 2), (2, 3), (4, 5)]
    assert all(out.original[t.span.start:t.span.end] == t.text
               for t in out.tokens)
    assert out.segments == ((0, 1, 2, 3),)
    assert out.ambiguities[0].indices == (3,)


def test_low_confidence_emits_segmentation_ambiguity() -> None:
    # a statistical guess is a fork the stage decided, so a score under
    # _SEGMENTER_CONFIDENCE_FLOOR is reported -- unlike a vocabulary
    # split, which reports only when a SECOND surname also matched
    state = _run("山田太郎", policy=_JA,
                 segmenter=_fake((2,), confidence=0.42))
    assert [a.kind for a in state.ambiguities] == [
        AmbiguityKind.SEGMENTATION]
    assert "0.42" in state.ambiguities[0].detail
    assert state.ambiguities[0].indices == (0, 1)


def test_high_confidence_and_no_confidence_emit_nothing() -> None:
    # a confident answer is not a fork, and an opinionless one gives
    # the stage nothing to judge -- neither is worth a report
    # 0.9 is the floor itself: the comparison is strict, so an answer
    # AT the floor is not under it
    for conf in (0.99, 0.9, None):
        state = _run("山田太郎", policy=_JA,
                     segmenter=_fake((2,), confidence=conf))
        assert _texts(state) == ["山田", "太郎"]
        assert state.ambiguities == ()


def test_out_of_bounds_split_raises() -> None:
    # Segmentation cannot check the upper bound (it never sees the
    # text), so the stage does -- and it RAISES, the same call the
    # wrong-answer-type check beside it makes: both are protocol
    # violations by the segmenter's author, inside the declared
    # totality exception. Declining silently instead (as this did
    # before the review) made an off-by-one segmenter undebuggable --
    # every answer vanished and the name merely looked undivided.
    with pytest.raises(ValueError,
                       match=r"segmenter returned splits beyond the "
                             r"token: last offset 5, token length 2"):
        _run("山田", policy=_JA, segmenter=_fake((5,)))
    # 2 on a two-character token is the boundary itself: the check is
    # >=, not >, since a cut at len(text) would leave an empty piece
    with pytest.raises(ValueError, match="last offset 2, token length 2"):
        _run("山田", policy=_JA, segmenter=_fake((2,)))


def test_family_comma_gates_the_segmenter_too() -> None:
    # the comma doctrine is about the input's structure, not the
    # split's source: the structural opt-out runs before any consult
    out = _run("山田太郎, 花子", policy=_JA, segmenter=_fake((2,)))
    assert out.structure is Structure.FAMILY_COMMA
    assert _texts(out) == ["山田太郎", "花子"]
    assert out.ambiguities == ()


def test_empty_vocabulary_still_consults_the_segmenter() -> None:
    # "consult on vocabulary decline" has no unstated exception for a
    # lexicon that declines EVERYTHING: a surname-less vocabulary is
    # the JA pack's own shape (the segmenter is its whole mechanism),
    # so an emptiness bail here would make it silently inert
    state = _run("山田太郎", policy=_JA, lexicon=Lexicon.empty(),
                 segmenter=_fake((2,)))
    assert _texts(state) == ["山田", "太郎"]


def test_a_wrong_answer_type_raises_a_curated_error() -> None:
    # a duck-typed lookalike would otherwise wander into the split
    # path and surface as a ValueError naming Token -- the reader's
    # bug is in their segmenter, and the message must say so
    class NotASegmentation:
        splits = (2,)
        confidence = None

    def seg(text: str) -> Segmentation | None:
        return NotASegmentation()   # type: ignore[return-value]

    with pytest.raises(TypeError,
                       match="segmenter must return Segmentation or None, "
                             "got NotASegmentation"):
        _run("山田太郎", policy=_JA, segmenter=seg)


def test_a_neighbour_in_an_UNACTIVATED_script_still_blocks_the_consult() -> None:
    # The precondition counts a second script-written token whatever
    # script it is written in -- effective_script merely non-None, NOT
    # membership in the activation set. A katakana or hangul neighbour
    # is a boundary its writer drew just as deliberately as a Han one,
    # so the name is already divided and the segmenter must not be
    # asked. Narrowing the check to `in scripts` would make both of
    # these split 山 + 田太郎 while the writer's own boundary sat one
    # token to the right.
    for name in ("山田太郎 マイケル", "山田太郎 김민준"):
        out = _run(name, policy=_JA, segmenter=_fake((1,)))
        assert _texts(out) == name.split(), name
        assert out.ambiguities == (), name


def test_the_segmenter_is_handed_the_gated_token_only() -> None:
    # It is asked where ONE token divides, so it gets that token's text
    # and nothing else -- not the original, not the name part joined
    # back together. A leading Latin title is the case that can tell
    # the difference: it is skipped by the gate (no script) and is not
    # a neighbour for the precondition either, so the consult happens
    # and the argument is observable.
    asked: list[str] = []

    def seg(text: str) -> Segmentation | None:
        asked.append(text)
        return Segmentation((2,))

    out = _run("Dr 山田太郎", policy=_JA, segmenter=seg)
    assert asked == ["山田太郎"]
    assert _texts(out) == ["Dr", "山田", "太郎"]


