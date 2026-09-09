"""Unit tests for the shared piece predicates.

_pieces has had no unit-test module since #439 moved it out of _group;
its predicates were reached only end to end through the case table.
These pin the two contracts that shape cannot reach: a defensive branch
no parse can produce, and the stability its readers rest on.
"""
from nameparser._lexicon import Lexicon
from nameparser._pipeline._assign import assign
from nameparser._pipeline._classify import classify
from nameparser._pipeline._group import group
from nameparser._pipeline._pieces import (
    _numeral_behind_the_initial_veto, leading_titles,
    segment_suffix_reading,
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

    Asserted directly because it cannot be asserted through a name --
    and with a piece the TAG test would accept, so that only the guard
    can produce the False. A first version of this test used the merged
    Ph./D. piece, whose head carries vocab:suffix but not initial: it
    COVERED the line and pinned nothing, since the tag test answered
    first and deleting the guard changed no result.
    """
    state = _through_group("Smith, V PSM")
    tokens = list(state.tokens)
    head = next(i for i, tok in enumerate(tokens) if tok.text == "V")
    assert {"vocab:suffix", "initial"} <= tokens[head].tags, (
        "the probe needs a token the TAG test would accept, or the "
        "assertion below passes without reaching the guard")

    # one token: the tag test answers, and answers yes
    assert _numeral_behind_the_initial_veto((head,), tokens) is True
    # two tokens headed by that same token: only the guard can say no,
    # so deleting it flips this
    assert _numeral_behind_the_initial_veto((head, head + 1), tokens) is False


def test_the_reading_is_positional_and_total() -> None:
    """One verdict per piece, in order -- the invariant its readers
    index by, and the only thing that makes reading[k] mean pieces[k].
    Three read it until #436 took the render join out of group;
    assign's gate and its router are what remain."""
    state = _through_group("Smith, MD PSM I")
    reading = segment_suffix_reading(
        state.pieces[1], state.piece_tags[1], list(state.tokens), True)
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
        state.pieces[1], state.piece_tags[1], list(state.tokens), True)
    after_state = assign(state)
    after = segment_suffix_reading(
        after_state.pieces[1], after_state.piece_tags[1],
        list(after_state.tokens), True)
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


def _leading(text: str) -> int:
    state = _through_group(text)
    return leading_titles(state.pieces[0], state.piece_tags[0],
                          list(state.tokens))


def test_the_leading_run_gives_back_the_name_word_a_suffix_cannot_be() -> None:
    """The peel's second floor, at the predicate.

    The run is counted before the trailing suffix peel runs, so its
    only floor was "leave one piece" and a run in front of nothing but
    suffix pieces took the last name word with it. The floor gives one
    word back -- and only where the rest really is all suffix pieces,
    which is what separates the first two readings below.
    """
    assert _leading("Dr King Jr") == 1     # the floor fired: 2 -> 1
    assert _leading("Dr King") == 1        # no all-suffix rest to see
    assert _leading("Lord Chancellor Jr") == 1
    assert _leading("Lord Chancellor") == 1


def test_the_leading_run_declines_to_give_back_a_suffix_word() -> None:
    """The three shapes the floor must not touch.

    The word given back has to be a name CANDIDATE, so a run whose
    last word is itself suffix vocabulary keeps it; and a run with
    nothing behind it has no all-suffix rest to read at all, which is
    what leaves the whole-segment carve-out and the all-title inputs
    exactly as they were.
    """
    assert _leading("MD DDS") == 1         # 'MD' is suffix vocabulary
    assert _leading("Jr. Ph. D.") == 1     # so is 'Jr.'
    assert _leading("Marquess of Bath") == 1   # nothing behind the run
    assert _leading("Dr.") == 1            # the whole-segment carve-out


def test_the_leading_run_keeps_a_joined_unit_it_cannot_give_back() -> None:
    """The piece given back has to be ONE WORD.

    A joined unit led by a title is a title run in its own right, so
    handing it back would turn the title into a given name and leave
    the name with no title at all -- 'Prince of Wales Jr' reads title
    'Prince of Wales', family 'Jr'. The run behind it is all suffix
    pieces and its last piece is no kind of suffix, so every other
    condition of the floor is met and only the length gate declines.
    """
    assert _leading("Prince of Wales Jr") == 1
    assert _leading("Prince of Wales") == 1
