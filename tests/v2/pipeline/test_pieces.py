"""Unit tests for the shared piece predicates.

_pieces has had no unit-test module since #439 moved it out of _group;
its predicates were reached only end to end through the case table.
These pin the two contracts that shape cannot reach: a defensive branch
no parse can produce, and the stability the three readers rest on.
"""
from nameparser._lexicon import Lexicon
from nameparser._pipeline._assign import assign
from nameparser._pipeline._classify import classify
from nameparser._pipeline._group import group
from nameparser._pipeline._pieces import (
    _numeral_behind_the_initial_veto, segment_suffix_reading,
)
from nameparser._pipeline._segment import segment
from nameparser._pipeline._state import ParseState
from nameparser._pipeline._tokenize import tokenize
from nameparser._policy import Policy


def _through_group(text: str) -> ParseState:
    state = ParseState(original=text, lexicon=Lexicon.default(),
                       policy=Policy())
    for stage in (tokenize, segment, classify, group):
        state = stage(state)
    return state


def test_the_numeral_veto_refuses_a_multi_token_piece() -> None:
    """The len(piece) != 1 guard, which no parse can exercise.

    A merged multi-token piece carries "suffix" in its PIECE tags, so
    is_suffix_piece claims it one branch earlier and the reading never
    asks this helper about one -- the review instrumented it over the
    whole suite and both differential corpora and found no call with a
    longer piece. That makes the guard unreachable, not wrong: without
    it the helper would read piece[0]'s tags and answer for the FIRST
    token of a piece rather than for the piece, which is a wrong answer
    where returning False is a safe one.

    Asserted directly because it cannot be asserted through a name.
    """
    state = _through_group("Smith, Ph. D.")
    tokens = list(state.tokens)
    merged = next(p for seg in state.pieces for p in seg if len(p) > 1)
    assert len(merged) > 1, "the Ph./D. merge should give a 2-token piece"
    assert _numeral_behind_the_initial_veto(merged, tokens) is False

    # and the single-token form it does answer for
    numeral = _through_group("Smith, PSM I")
    ntokens = list(numeral.tokens)
    last = numeral.pieces[1][-1]
    assert len(last) == 1
    assert _numeral_behind_the_initial_veto(last, ntokens) is True


def test_the_reading_is_positional_and_total() -> None:
    """One verdict per piece, in order -- the invariant all three
    readers index by, and the only thing that makes reading[k] mean
    pieces[k]."""
    state = _through_group("Smith, MD PSM I")
    reading = segment_suffix_reading(
        state.pieces[1], state.piece_tags[1], list(state.tokens))
    assert reading is not None
    assert len(reading) == len(state.pieces[1])
    assert all(isinstance(v, bool) for v in reading)


def test_the_reading_does_not_move_when_roles_are_assigned() -> None:
    """The stability the shared-predicate design rests on.

    group reads the reading before assign runs and assign reads it
    again afterwards; that is only safe because the predicates read
    token TAGS and text, which assign never rewrites -- it writes
    roles. If a stage ever tagged during assignment the two readers
    would silently disagree, which is the drift #429 and #430 are.
    """
    state = _through_group("Smith, PSM I")
    before = segment_suffix_reading(
        state.pieces[1], state.piece_tags[1], list(state.tokens))
    after_state = assign(state)
    after = segment_suffix_reading(
        after_state.pieces[1], after_state.piece_tags[1],
        list(after_state.tokens))
    assert before == after == (True, True)


def test_strict_ends_the_run_at_the_initial_shaped_numeral() -> None:
    """C1's strict knob, at the predicate rather than through a parse.

    Lenient continues the credential run through a one-character
    suffix word; strict vetoes initial-shaped words, so the run is no
    run at all and the segment falls to the walk.
    """
    state = _through_group("Smith, PSM I")
    args = (state.pieces[1], state.piece_tags[1], list(state.tokens))
    assert segment_suffix_reading(*args, True) == (True, True)
    assert segment_suffix_reading(*args, False) is None
