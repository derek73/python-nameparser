"""Stage: script_segment (#271) -- unspaced CJK surname splitting."""
import dataclasses

from nameparser import Parser
from nameparser._lexicon import Lexicon
from nameparser._pipeline._script_segment import script_segment
from nameparser._pipeline._segment import segment
from nameparser._pipeline._state import (
    ParseState, PendingAmbiguity, Structure,
)
from nameparser._pipeline._tokenize import tokenize
from nameparser._policy import Policy, Script
from nameparser._types import AmbiguityKind

_HAN = Policy(segment_scripts=frozenset({Script.HAN}))
_HANGUL = Policy()      # HANGUL is the default activation
# 欧 AND 欧阳 both present on purpose: compound-before-single must
# pick 欧阳 (the issue's own acceptance example); same for 남/남궁.
# "jr" so the comma cases can reach SUFFIX_COMMA.
_LEX = Lexicon(surnames=frozenset({"毛", "欧", "欧阳", "김", "남", "남궁"}),
               suffix_words=frozenset({"jr"}))


def _run(text: str, policy: Policy = _HAN,
         lexicon: Lexicon = _LEX) -> ParseState:
    state = ParseState(original=text, lexicon=lexicon, policy=policy)
    return script_segment(segment(tokenize(state)))


def _texts(state: ParseState) -> list[str]:
    return [t.text for t in state.tokens]


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
