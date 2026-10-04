"""Unit tests for the shared piece predicates.

_pieces has had no unit-test module since #439 moved it out of _group;
its predicates were reached only end to end through the case table.
These pin the two contracts that shape cannot reach: a defensive branch
no parse can produce, and the stability its readers rest on.
"""
import dataclasses
import itertools
from collections.abc import Callable, Sequence, Set

import pytest

from nameparser import Parser, parse
from nameparser._lexicon import Lexicon, _normalize
from nameparser._pipeline import STAGES
from nameparser._pipeline._assign import assign
from nameparser._pipeline._classify import classify
from nameparser._pipeline import _group
from nameparser._pipeline._group import group
from nameparser._pipeline._pieces import (
    _anchors, _numeral_behind_the_initial_veto, anchor_in_reach,
    credential_anchors,
    credential_at_the_given_slot, is_leading_title, leading_titles,
    own_words, peel_trailing, peel_walk, segment_suffix_reading,
    tail_reading, trailing_candidates, trailing_titles,
)
from nameparser._pipeline._segment import segment
from nameparser._pipeline._state import (
    AMBIGUOUS_ACRONYM_TAG, ParseState, PendingAmbiguity, WorkToken,
)
from nameparser._pipeline._tokenize import tokenize
from nameparser._pipeline._vocab import is_one_case, is_title_shaped, tag_marker_runs
from nameparser._policy import Policy

from ..cases import CASES


def _through_group(text: str, policy: Policy = Policy()) -> ParseState:
    state = ParseState(original=text, lexicon=Lexicon.default(),
                       policy=policy)
    for stage in (tokenize, segment, classify, group):
        state = stage(state)
    return state


def _state_through(stage_name: str, text: str) -> ParseState:
    """Run the pipeline up to and including the named stage (STAGES'
    own names), for a test that needs a state a later stage has not
    yet touched (#289/#516)."""
    state = ParseState(original=text, lexicon=Lexicon.default(),
                       policy=Policy())
    for stage in STAGES:
        state = stage(state)
        if stage.__name__ == stage_name:
            break
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
        state.pieces[1], state.piece_tags[1], list(state.tokens), True,
        state.one_case)
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
        state.pieces[1], state.piece_tags[1], list(state.tokens), True,
        state.one_case)
    after_state = assign(state)
    after = segment_suffix_reading(
        after_state.pieces[1], after_state.piece_tags[1],
        list(after_state.tokens), True, after_state.one_case)
    assert before == after == (True, True)


def test_strict_ends_the_run_at_the_initial_shaped_numeral() -> None:
    """C1's strict knob, at the predicate rather than through a parse.

    Lenient continues the credential run through a one-character
    suffix word; strict vetoes initial-shaped words, so the run is no
    run at all and the segment falls to the walk. Asked behind a
    title/suffix dual, which opens no part when nothing says the name
    before the comma is whole (#603). Behind a credential that does
    open it ('PSM'), strict refuses the numeral the suffix reading but
    the opened part takes it in all the same, and hands it to the
    caller to report.
    """
    state = _through_group("Smith, MD I")
    args = (state.pieces[1], state.piece_tags[1], list(state.tokens))
    assert segment_suffix_reading(*args, True, state.one_case) == (True, True)
    assert segment_suffix_reading(*args, False, state.one_case) is None
    state = _through_group("Smith, PSM I")
    args = (state.pieces[1], state.piece_tags[1], list(state.tokens))
    for lenient, taken in ((True, []), (False, [1])):
        absorbed: list[int] = []
        assert segment_suffix_reading(*args, lenient, state.one_case,
                                      None, absorbed) == (True, True)
        assert absorbed == taken


def _comma_part_reading(text: str) -> tuple[tuple[bool, ...] | None,
                                            list[int]]:
    state = _through_group(text)
    picks: list[int] = []
    reading = segment_suffix_reading(
        state.pieces[1], state.piece_tags[1], list(state.tokens), True,
        state.one_case, picks)
    return reading, picks


def test_the_reading_names_the_picks_its_anchor_made() -> None:
    """#544: the members the anchor read as credentials after their
    own writing declined -- the picks assign reports. A member whose
    capitals lean credential decided itself and is not among them,
    and nothing stands in front of piece 0 to anchor it."""
    assert _comma_part_reading("Smith, PhD Ma") == ((True, True), [1])
    assert _comma_part_reading("Smith, PhD MA") == ((True, True), [])
    assert _comma_part_reading("Smith, Dr. PhD Ed Ma") == (
        (False, True, True, True), [2, 3])
    assert _comma_part_reading("Smith, MA PhD ba") == (
        (True, True, True), [2])


def test_a_dual_in_the_leading_title_run_turns_the_anchor_off() -> None:
    """#544: a title/suffix dual standing in the given part's leading
    title run is a title there, and this reading then anchors nothing
    in the part -- neither by that dual, nor by a second one in the
    same run, nor by a credential behind them -- so the walk reads it
    as the parent did, its given slot's company starting past the
    given name. A plain title does not do this, and a dual behind a
    credential anchors like any suffix word."""
    for text in ("Smith, Ms Ma", "Smith, Ms MD Ma", "Smith, MD PhD Ma",
                 "Smith, MD MS Ma", "SMITH, MD MS BA",
                 "Smith, Prof. MD Ma", "smith, prof. md ma",
                 "Smith, Dr. MD PhD Ma"):
        assert _comma_part_reading(text)[0] is None, text
    assert _comma_part_reading("Smith, Dr. PhD LAc") == (
        (False, True, True), [2])
    assert _comma_part_reading("Smith, PhD Ms Ma") == (
        (True, True, True), [2])
    # with no member to anchor, the dual reads as the suffix it is
    assert _comma_part_reading("Smith, MD PhD") == ((True, True), [])
    # and the walk's given slot, past the given name, reads its own
    # company as behind any given name
    assert parse("Smith, MD PhD Jr Ma").suffix == "Jr Ma"
    assert parse("Smith, MD PhD Jr Ma").given == "PhD"


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


def _trailing(text: str) -> int:
    """trailing_titles over the rest assign hands it: the name pieces
    the S2 peel left, after the leading run is counted off.

    The count is what the chain LEAVES STANDING, the way peel_trailing
    counts -- so a walk that takes nothing returns the length of the
    rest it was handed, and each title taken is one off that."""
    state = _through_group(text)
    pieces, ptags = state.pieces[0], state.piece_tags[0]
    tokens = list(state.tokens)
    rest = peel_walk(leading_titles(pieces, ptags, tokens), ptags)
    peeled = peel_trailing(rest, pieces, ptags, tokens, state.one_case)
    return trailing_titles(rest[:peeled.names], pieces, ptags, tokens)


def test_the_trailing_run_chains_period_marked_title_words() -> None:
    """A RUN, mirroring the leading one.

    One word only would leave 'Prof.' a name word in the first
    reading below, which is the reason the walk chains rather than
    taking the last piece and stopping.
    """
    assert _trailing("John Smith Prof. Dr.") == 2   # of four: both taken
    assert _trailing("John Smith Prof.") == 2       # of three
    assert _trailing("Dr. John Smith Prof.") == 2   # leading run too


def test_the_trailing_run_leaves_one_name_piece_standing() -> None:
    """The floor, and the empty rest assign's carve-out needs.

    A name is never all title: the walk stops with one name piece
    left. An input that IS all title never reaches the walk at all --
    the leading peel took the whole segment and the rest is empty,
    where the same floor returns 0 and leaves assign's bare-suffix
    carve-out reached exactly as before.
    """
    assert _trailing("Smith Prof.") == 1     # of two: the title taken
    assert _trailing("Dr. Prof.") == 1      # the floor, on a rest the
                                            # walk would otherwise take
    assert _trailing("Smith") == 1          # one-piece rest
    assert _trailing("Prof.") == 0          # empty rest


def test_the_trailing_run_reads_vocabulary_and_not_shape() -> None:
    """The whole difference from is_leading_title.

    That predicate carries H2's unlisted-abbreviation inference, so
    with it the first reading below would lose its family name to a
    title. The trailing slot has no shape rule: a period-marked word
    is claimed there only when the vocabulary claims it, and a bare
    title word is claimed not at all.
    """
    # nothing claimed: the walk leaves every piece it was handed
    assert _trailing("John Smith Xyz.") == 3    # unlisted abbreviation
    assert _trailing("John Smith Sir") == 3     # no period
    assert _trailing("John Smith Esq.") == 2    # the peel took it first


def test_the_trailing_run_refuses_a_joined_piece() -> None:
    """ONE WORD per piece, the gate the leading give-back shares.

    'de la Prof.' is one piece of three tokens, and the tokens of a
    joined unit are not each a title word -- the particle chain made
    that unit a name.

    That first row does not PIN the gate, though: with the one-word
    test deleted it stands unchanged, because the shape test then runs
    on the piece's first token and 'de' wears no period (measured
    2026-09-09). The conjunction-merged unit is the row that pins it
    -- 'Prof. and Dr.' is one piece whose first token is a
    period-marked title word, so without the gate the walk takes it
    and the name loses its family (measured one piece fewer standing
    under that mutation).
    """
    assert _trailing("John de la Prof.") == 2
    assert _trailing("John Smith Prof. and Dr.") == 3


def _peel_inputs(text: str, policy: Policy = Policy()
                 ) -> tuple[list[int], Sequence[Sequence[int]],
                           Sequence[Set[str]],
                           Sequence[WorkToken]]:
    """The trailing peel's own inputs for segment 0, run through
    `group` (#289/#516's `one_case` reaches the peel only after group
    has assigned tags, so the shorter `_through_group` fixture -- not
    a bare tokenize+segment -- is what these tests need).

    The walk starts AFTER the leading title run, exactly as
    `_assign_main` and `_trailing` above start it: `peel_walk(0, ...)`
    would leave a leading title piece sitting in `rest` as an ordinary
    name piece the walk never filters out (peel_walk only drops
    group-flagged suffix pieces), and 'Mr MA' needs the title excluded
    to reach the one-piece floor its own test pins.
    """
    state = _through_group(text, policy)
    pieces, ptags = state.pieces[0], state.piece_tags[0]
    tokens = state.tokens
    start = leading_titles(pieces, ptags, tokens)
    return peel_walk(start, ptags), pieces, ptags, tokens


def test_peel_trailing_takes_the_three_lean_outcomes() -> None:
    # #289 at the trailing slot, the three outcomes against the peel's
    # three: a CREDENTIAL lean consumes with no words to spare, a NAME
    # lean declines WITH words to spare, and no lean at all leaves
    # rules.md#S2's count deciding exactly as it did.
    # Every case still REPORTS: the pick is appended either way, which
    # is what the fork's report is built from.
    for text, one_case, names, picked in (
            ("Jack MA", False, 1, True),      # credential lean, k == 2
            ("Jack Ma", False, 2, True),      # name lean, k == 2
            ("Jack MA", True, 2, True),       # one case: today's count
            ("John Smith Ma", False, 3, True),   # name lean, k == 3
            ("John Smith MA", False, 2, True),   # credential lean
            ("JOHN SMITH MA", True, 2, True),    # one case: the count
    ):
        rest, pieces, ptags, tokens = _peel_inputs(text)
        peeled = peel_trailing(rest, pieces, ptags, tokens,
                               one_case=one_case)
        assert peeled.names == names, (text, one_case)
        assert bool(peeled.picks) is picked, (text, one_case)


def test_peel_trailing_keeps_its_two_piece_floor_under_a_lean() -> None:
    # The floor is not what the lean moves. One piece behind a title
    # never reaches the peel at all -- measured 2026-09-15, 'Mr MA'
    # reads title 'Mr', family 'MA' and reports nothing -- and a lean
    # that reached below `k >= 2` would read it as a title with a
    # credential and no name at all.
    rest, pieces, ptags, tokens = _peel_inputs("Mr MA")
    peeled = peel_trailing(rest, pieces, ptags, tokens, one_case=False)
    assert peeled.names == len(rest)
    assert peeled.picks == ()


def test_peel_trailing_takes_a_declined_pick_an_anchor_stands_before(
) -> None:
    # #544 reverses the cost decisions.md#S2 had accepted: the surname
    # lean declines 'Ma', but the unambiguous 'Jr' IN FRONT of it
    # anchors it, so the walk takes it and reaches 'Jr' too -- and the
    # member is still a pick, reported as a counted one is.
    rest, pieces, ptags, tokens = _peel_inputs("abdul Smith Jr Ma")
    peeled = peel_trailing(rest, pieces, ptags, tokens, one_case=False)
    assert peeled.names == len(rest) - 2
    assert len(peeled.picks) == 1
    # a credential BEHIND the member anchors nothing: the walk peels
    # 'PhD' and stops at the declined 'Ma', a name word
    rest, pieces, ptags, tokens = _peel_inputs("Wang Ma PhD")
    peeled = peel_trailing(rest, pieces, ptags, tokens, one_case=False)
    assert peeled.names == len(rest) - 1


def test_the_walks_own_leading_piece_never_anchors_what_follows_it(
) -> None:
    # #544: a
    # bare unambiguous suffix word standing in the walk's OWN leading
    # position -- 'PhD'/'Om'/'Jr' are each unambiguous suffix
    # vocabulary and also plausible given names/surnames -- must never
    # anchor a member behind it, because that leading position is
    # always the name H4's carve-out keeps. Anchoring it let the run
    # collapse entirely: 'PhD Ma' read given 'PhD', suffix 'Ma',
    # losing the family outright, rather than 'PhD Ma' keeping the
    # reading the count alone gives it (given 'PhD', family 'Ma').
    for text, family in (("Om Ma", "Ma"), ("PhD Ma", "Ma"),
                         ("Jr Ma", "Ma")):
        rest, pieces, ptags, tokens = _peel_inputs(text)
        peeled = peel_trailing(rest, pieces, ptags, tokens, one_case=None)
        assert peeled.names == len(rest), text
    n = parse("Om Ma")
    assert (n.given, n.family, n.suffix) == ("Om", "Ma", "")
    n = parse("Om Ma Jr")
    assert (n.given, n.family, n.suffix) == ("Om", "Ma", "Jr")
    n = parse("PhD Ma")
    assert (n.given, n.family, n.suffix) == ("PhD", "Ma", "")
    # a genuine given name ahead of it frees the SAME word to anchor:
    # 'Om' is no longer the walk's own leading piece once 'John' is,
    # so it anchors 'Ma' exactly as any other unambiguous credential
    # standing in front does
    n = parse("John Om Ma")
    assert (n.family, n.suffix) == ("", "Om Ma")


def test_a_reserve_kept_leading_piece_beside_a_genuine_family_loss(
) -> None:
    # decisions.md#S2's Accepted boundary ("an unambiguous suffix is
    # consumed even when that leaves no family name at all", 'Smith
    # Jr.' -> family='') applies just the same when the LEADING piece
    # is itself listed suffix vocabulary rather than an ordinary name:
    # 'Om' is the walk's own leading piece and stays given (the
    # reserve), but 'Jr' -- NOT the leading piece -- is still consumed
    # unconditionally, leaving no family at all.
    n = parse("Om Jr")
    assert (n.given, n.family, n.suffix) == ("Om", "", "Jr")
    # and 'Jr', standing in front of 'Ma' but not itself the leading
    # piece, anchors it exactly as any other unambiguous credential
    # does -- the boundary costs the family, not the anchor
    n = parse("Om Jr Ma")
    assert (n.given, n.family, n.suffix) == ("Om", "", "Jr Ma")


def _anchored_words(text: str) -> list[str]:
    rest, pieces, ptags, tokens = _peel_inputs(text)
    return [" ".join(tokens[t].text for t in pieces[i])
            for i, anchored in zip(
                rest, credential_anchors(rest, pieces, ptags, tokens))
            if anchored]


def test_credential_anchors_reads_in_front_and_through_members() -> None:
    # #544: a position is anchored when the run in FRONT of it holds a
    # suffix piece that may anchor, and a lone member passes the
    # anchor on to the member behind it
    assert _anchored_words("John Smith PhD Ma") == ["Ma"]
    assert _anchored_words("John Smith PhD Ed Ma") == ["Ed", "Ma"]
    # the credential behind anchors nothing
    assert _anchored_words("John Smith Ma PhD") == []
    assert _anchored_words("Wang Ma PhD") == []


def test_credential_anchors_stops_at_a_numeral_or_a_name_word() -> None:
    # the piece straight behind the credential is marked whatever it
    # is; what matters is the member past it, which a single-letter
    # roman numeral (one letter, in any case, the shape a bare middle
    # initial is written in) or a name word leaves unanchored. A
    # multi-letter numeral is not this shape and anchors like any
    # other suffix piece (pinned below).
    assert _anchored_words("John Smith PhD v Ma") == ["v"]
    assert _anchored_words("John Smith PhD Jones Ma") == ["Jones"]
    assert _anchored_words("John Smith PhD III Ma") == ["III", "Ma"]


def test_a_connective_or_a_numeral_suffix_word_anchors_nothing() -> None:
    # the generational 'i' is also Catalan's conjunction, and between
    # two name words it is a link (rules.md#P3); a single-letter roman
    # numeral, in any case, is ONE LETTER, the shape a middle initial
    # is written in -- not excluded for being "no credential", since a
    # multi-letter numeral ('III') anchors like any other suffix word
    # (pinned in `test_credential_anchors_stops_at_a_numeral...` and
    # `test_a_multi_letter_numeral_anchors_like_any_suffix_word`
    # below). Neither a connective nor a single-letter numeral may
    # anchor.
    state = _through_group("John Smith Jr Ma")
    tokens = list(state.tokens)
    jr = next(i for i, t in enumerate(tokens) if t.text == "Jr")
    assert _anchors((jr,), tokens)
    tokens[jr] = dataclasses.replace(
        tokens[jr], tags=tokens[jr].tags | {"conjunction"})
    assert not _anchors((jr,), tokens)
    state = _through_group("John Smith v Ma")
    v = next(i for i, t in enumerate(state.tokens) if t.text == "v")
    assert not _anchors((v,), state.tokens)
    # a particle that is also suffix vocabulary is the head of the
    # family name behind it, not a credential: the same 'Jr' tagged a
    # particle anchors nothing either
    tokens[jr] = dataclasses.replace(
        tokens[jr], tags=(tokens[jr].tags - {"conjunction"}) | {"particle"})
    assert not _anchors((jr,), tokens)


@pytest.mark.parametrize("text, fields", [
    ("Jan vd Ma", {"given": "Jan", "family": "vd Ma"}),
    ("Smith vd Ma, John", {"given": "John", "family": "Smith vd Ma"}),
    ("Smith Mc Ma, John", {"given": "John", "family": "Smith Mc Ma"}),
    ("D. Mc Ba Ed, Smith", {"given": "Smith", "family": "D. Mc Ba Ed"}),
])
def test_a_particle_in_suffix_vocabulary_anchors_nothing(
        text: str, fields: dict[str, str]) -> None:
    # #544: 'vd' and 'mc' are particle AND unambiguous suffix
    # vocabulary; standing in front of a member they head the family
    # name, and anchoring there split it around a suffix ('Smith vd
    # Ma, John' read family 'Smith Ma', suffix 'vd'). A particle
    # MEMBER is still anchored by a credential in front of it.
    n = parse(text)
    assert {k: v for k, v in n.as_dict().items() if v} == fields
    assert parse("doe, jane v phd do").suffix == "v phd do"


def test_anchor_in_reach_is_false_only_where_the_pass_is() -> None:
    # the reach test is a necessary condition for the pass: False
    # where the first piece in front past the lone members is no
    # suffix piece, True (ask the pass) otherwise -- including where
    # the pass then answers False, a non-anchoring suffix piece
    # ('v') or the kept leading piece being in reach
    for text, expect in (("John Smith Ma", False),
                         ("John Smith Ed Ma", False),
                         ("John Smith PhD Ma", True),
                         ("John Smith PhD Ed Ma", True),
                         ("John Smith PhD v Ma", True)):
        rest, pieces, ptags, tokens = _peel_inputs(text)
        back = rest[len(rest) - 2::-1]
        assert anchor_in_reach(back, pieces, ptags, tokens) is expect, text
        if not expect:
            assert not credential_anchors(rest, pieces, ptags, tokens)[-1]
    # `skip` splices pieces out of the walk
    rest, pieces, ptags, tokens = _peel_inputs("John Smith PhD Ma")
    assert not anchor_in_reach(rest[2::-1], pieces, ptags, tokens,
                               skip={rest[2]})
    # a merged split credential is ONE suffix piece of two tokens, and
    # it anchors as the unsplit spelling does wherever it is in the
    # walk -- after a comma ('John Smith Ph. D. MEng' is the no-comma
    # peel's Accepted limit, the merged piece standing outside its walk)
    assert parse("Doe, Jane Ph. D. MEng").suffix == "Ph. D. MEng"
    assert parse("Smith, Ph. D. MEng").suffix == "Ph. D. MEng"
    # and the member it speaks for reports as the pick it is
    assert [(a.kind.value, [t.text for t in a.tokens])
            for a in parse("Smith, Ph. D. MEng").ambiguities] == [
        ("suffix-or-name", ["MEng"])]


def test_a_multi_letter_numeral_anchors_like_any_suffix_word() -> None:
    # #544: the exclusion is about SHAPE (a single letter
    # reads as a middle initial, 'John Smith PhD V Ma' keeping 'V' a
    # name word), not about numerals being no credential -- 'III' is
    # unambiguous suffix vocabulary of more than one letter and
    # anchors exactly as 'Jr' does.
    n = parse("John Smith PhD III Ma")
    assert (n.family, n.suffix) == ("Smith", "PhD III Ma")
    # without the degree in front: the single letter is a middle
    # initial and anchors nothing. With it, since #602, the degree
    # starts a run to the end of the part and 'V Ma' are inside it
    # ('John Smith PhD V Ma' reads suffix 'PhD V Ma').
    n = parse("John Smith V Ma")
    assert (n.middle, n.family, n.suffix) == ("Smith V", "Ma", "")


def test_the_anchor_pass_starts_past_the_leading_title_run() -> None:
    # a title/suffix dual opening the given part is a title there and
    # anchors nothing, at the given slot and in the part read whole
    assert parse("Smith, MD MA Ma").middle == "Ma"
    assert parse("Smith, Ms Ma").given == "Ma"
    # past that position the same dual anchors
    assert parse("John Smith MD MEng").suffix == "MD MEng"


def test_the_given_slot_asks_the_anchor_only_when_the_writing_declines(
) -> None:
    # #544: `credential_at_the_given_slot` takes the anchor as a THUNK
    # and asks it last, so a member the writing already settles never
    # pays for the anchor pass
    calls: list[str] = []

    def anchored() -> bool:
        calls.append("asked")
        return True

    tokens = _through_group("Doe, John MA Ma do").tokens
    caps, title, particle = (
        next(t for t in tokens if t.text == text)
        for text in ("MA", "Ma", "do"))
    # the capitals lean credential, and one case leans nothing (the
    # count's reading): neither asks
    assert credential_at_the_given_slot(caps, False, anchored)
    assert credential_at_the_given_slot(title, True, anchored)
    assert calls == []
    # a Title-case member and a particle member with no lean decline,
    # so the anchor answers -- once each
    assert credential_at_the_given_slot(title, False, anchored)
    assert credential_at_the_given_slot(particle, True, anchored)
    assert calls == ["asked", "asked"]
    # with no anchor to ask, the declined reading stands
    assert not credential_at_the_given_slot(title, False)
    assert not credential_at_the_given_slot(particle, True)


def test_a_shape_only_token_reports_without_being_taken() -> None:
    # `Policy(unlisted_dotted_suffixes=False)`: name material
    # everywhere, as 2.3 read it -- and
    # the fork is still reported, because the parser chose the name
    # reading over a credential one and that is the call a caller
    # wants told (#516).
    rest, pieces, ptags, tokens = _peel_inputs(
        "John Smith X.Y.Z.", Policy(unlisted_dotted_suffixes=False))
    peeled = peel_trailing(rest, pieces, ptags, tokens, one_case=False)
    assert peeled.names == len(rest)
    assert peeled.picks != ()


def test_a_by_shape_token_takes_the_count_and_never_a_lean() -> None:
    # A token admitted by SHAPE carries no writing convention to read,
    # so the count decides it in either case spelling (#516).
    for text, names in (("John Smith X.Y.Z.", 2),
                        ("john smith x.y.z.", 2),
                        ("Jack X.Y.Z.", 2)):
        rest, pieces, ptags, tokens = _peel_inputs(text)
        peeled = peel_trailing(rest, pieces, ptags, tokens, one_case=False)
        assert peeled.names == names, text
        assert peeled.picks != (), text


@pytest.mark.parametrize("text, expected", [
    ("Xyz.", True),        # H2 (rules.md): an unlisted Latin abbreviation
    ("김민준.", False),     # #323: hangul has no period abbreviations
    ("田中.", False),       # nor Han
    ("たなか.", False),     # nor kana
    ("Kim김.", False),        # contains-any, not wholly-of: one CJK char vetoes
    ("J.", False),          # a bare initial never was (H2 boundary)
])
def test_leading_title_shape_refuses_an_initialless_script(
        text: str, expected: bool) -> None:
    # Xyz. rather than Rev. for the Latin side: Rev. is LISTED, so
    # is_title_piece claims it before the shape is asked
    state = _through_group(text + " Smith")
    assert is_leading_title(state.pieces[0][0], state.piece_tags[0][0],
                            state.tokens) is expected


@pytest.mark.parametrize("text", [
    "Xyz.", "Dr.", "Xyz", "X.", "田中.", "김민준.", "たなか.", "Kim김.", "J.",
])
def test_is_title_shaped_and_is_leading_title_agree(text: str) -> None:
    # The two spellings of H2's shape test -- `is_title_shaped`'s own
    # docstring and `is_leading_title`'s inline copy each point here --
    # kept in step by a check over the UNION of both predicates' own
    # example tables (this one and test_vocab.py's
    # test_is_title_shaped_is_h2_s_shape_alone), rather than by a
    # sentence alone (#289/#516 quality-review follow-up).
    # 'Dr.' answers True through `is_leading_title`'s EARLIER
    # `is_title_piece` (LISTED vocabulary) branch, not through the
    # inline shape copy this test means to pin -- it stays in the
    # union for parity with `is_title_shaped`'s own table (which
    # answers True the same way, for the same reason: listed or not
    # is a question neither predicate asks), not because it exercises
    # the shape branch on either side.
    state = _through_group(text + " Smith")
    assert is_title_shaped(text) == is_leading_title(
        state.pieces[0][0], state.piece_tags[0][0], state.tokens)


def test_own_words_is_the_name_s_own_span_and_its_clause_cut() -> None:
    # rules.md#P3 says the case question is asked of the name's OWN
    # words. This helper is that span, taken off the token stream so
    # both the site that runs before classify and classify itself ask
    # one function (#289/#516).
    state = _state_through("segment", "Jane née Jones Smith")
    texts, cut = own_words(state.tokens, state.comma_offsets,
                           state.lexicon.maiden_markers)
    assert texts == ["Jane"]
    assert cut == 1
    # a delimited clause's tokens arrive with a role already set, so
    # they are not the name's own words either
    state = _state_through("segment", "Andrew (Andy) Perkins")
    texts, cut = own_words(state.tokens, state.comma_offsets,
                           state.lexicon.maiden_markers)
    assert texts == ["Andrew", "Perkins"]
    assert cut == 3
    # `comma_offsets` is load-bearing only for a marker PHRASE whose
    # words would otherwise straddle a comma: 'z domu' is one entry,
    # and 'z' and 'domu' sit on opposite sides of the comma in 'Anna
    # z, domu Nowak'. With the real offsets the two words are in
    # different buckets, the phrase cannot complete, and clause_at
    # falls through to the whole name; passing () collapses every
    # token into one bucket, the phrase wrongly completes, and the
    # cut lands at 'z' instead. Measured 2026-09-17.
    state = _state_through("segment", "Anna z, domu Nowak")
    texts, cut = own_words(state.tokens, state.comma_offsets,
                           state.lexicon.maiden_markers)
    assert texts == ["Anna", "z", "domu", "Nowak"]
    assert cut == 4
    texts, cut = own_words(state.tokens, (), state.lexicon.maiden_markers)
    assert texts == ["Anna"]
    assert cut == 1


def test_own_words_takes_a_marker_map_when_the_caller_has_one() -> None:
    # classify has already decided which tokens are marker RUN heads,
    # so it hands that map over rather than paying a second walk.
    state = _state_through("segment", "Jane née Jones Smith")
    heads = {1: "vocab:maiden-marker", 2: "vocab:maiden-marker-cont"}
    assert own_words(state.tokens, state.comma_offsets,
                     state.lexicon.maiden_markers,
                     heads) == (["Jane"], 1)
    # an incomplete phrase entry: no head tag, so the map's answer is
    # "no clause" -- and the self-built path agrees, since both now
    # run the SAME completion test (#289/#516)
    state = _state_through("segment", "Anna z Nowak")
    assert own_words(state.tokens, state.comma_offsets,
                     state.lexicon.maiden_markers,
                     {}) == (["Anna", "z", "Nowak"], 3)
    assert own_words(state.tokens, state.comma_offsets,
                     state.lexicon.maiden_markers)[1] == 3


def test_own_words_two_spellings_agree_on_the_one_case_verdict() -> None:
    # #289/#516's fix: own_words' self-built path (no marker_tags map)
    # now calls _vocab.tag_marker_runs -- the SAME run-completion test
    # classify uses -- instead of approximating it with a text-only
    # head walk (the retired first_marker_head). The two spellings
    # below -- an explicit map built ahead of time, and none at all --
    # are now the SAME computation, so they agree on the CUT, not just
    # the verdict, by construction rather than by corpus luck.
    #
    # 'ANNA z Nowak, MD' is why the old approximation was not merely
    # imprecise but wrong: 'z' opens the phrase entry 'z domu', which
    # completes neither way, but the text-only walk took the open
    # alone as the cut (1: just 'ANNA', one-case True), while the real
    # run-completion test finds no run and falls through to the full
    # own-words span (mixed case, False) -- a flipped verdict, not a
    # different span with the same answer. Measured 2026-09-17.
    for text in ("Anna z Nowak", "Anna z (domu) Nowak", "ANNA z Nowak, MD"):
        state = _state_through("segment", text)
        folded = [_normalize(t.text) for t in state.tokens]
        built_map = tag_marker_runs(state.tokens, state.comma_offsets,
                                    state.lexicon.maiden_markers, folded)
        tagged = own_words(state.tokens, state.comma_offsets,
                           state.lexicon.maiden_markers, built_map)
        walked = own_words(state.tokens, state.comma_offsets,
                           state.lexicon.maiden_markers)
        assert tagged == walked, text
        assert is_one_case(tagged[0]) == is_one_case(walked[0]), text


def test_tag_marker_runs_answers_in_ascending_index_order() -> None:
    """`own_words` depends on it, and nothing else said so.

    Its own docstring states the requirement -- "`marker_tags`' keys
    must arrive in index order for the walk below to find the SMALLEST
    head in one pass" -- and then satisfies it by BREAKING at the first
    head. So a map whose keys arrived out of order would cut the span
    at whichever head happened to come first, silently, and every
    caller's one-case verdict with it. The guarantee lives in
    `tag_marker_runs`' left-to-right walk; this is the assertion that
    holds it there (2026-09-18 review round).
    """
    for text in ("Anna z Nowak nee Jones", "Jane née Jones geb Schmidt",
                 "Anna z domu Nowak nee Jones", "John Smith"):
        state = _state_through("segment", text)
        folded = [_normalize(t.text) for t in state.tokens]
        keys = list(tag_marker_runs(state.tokens, state.comma_offsets,
                                    state.lexicon.maiden_markers,
                                    folded))
        assert keys == sorted(keys), text


#: The run words of the reach sweep below: unambiguous credentials,
#: members (one a particle too), the two particles of the suffix
#: vocabulary, a one-letter numeral, titles and a name word.
_REACH_WORDS = ("PhD", "Jr", "MA", "Ma", "Ed", "Do", "vd", "Mc", "V",
                "Prof.", "Dr.", "Jones")


def _reach_failures(texts: Sequence[str]) -> list[str]:
    """Every (text, segment, position, first_kept, start) at which
    `anchor_in_reach` answers False while `credential_anchors` anchors
    the lone member standing there -- the direction the reach test
    must never get wrong, since a False skips the pass. Asked of every
    segment of every text, over `order` both from the segment's first
    piece and from past its leading title run, and with the leading
    position both kept and read, the reach walking everything in
    front each time (the superset every caller passes)."""
    out = []
    for text in texts:
        state = _through_group(text)
        tokens = state.tokens
        for seg, (pieces, ptags) in enumerate(
                zip(state.pieces, state.piece_tags)):
            for start in {0, leading_titles(pieces, ptags, tokens)}:
                order = range(start, len(pieces))
                for first_kept in (True, False):
                    anchors = credential_anchors(order, pieces, ptags,
                                                 tokens, first_kept)
                    for pos, m in enumerate(order):
                        piece = pieces[m]
                        if not (len(piece) == 1 and AMBIGUOUS_ACRONYM_TAG
                                in tokens[piece[0]].tags):
                            continue
                        if anchors[pos] and not anchor_in_reach(
                                range(m - 1, -1, -1), pieces, ptags,
                                tokens):
                            out.append(f"{text!r} seg {seg} at {m} "
                                       f"first_kept={first_kept} "
                                       f"start={start}")
    return out


def test_anchor_in_reach_never_hides_an_anchor() -> None:
    """`anchor_in_reach` False implies `credential_anchors` False, at
    every lone member of every segment, over the case table's texts
    and every run of one to three `_REACH_WORDS` behind 'John Smith '
    and 'Doe, Jane ' (4,497 distinct texts, 742 of them the table's;
    0.23s on py3.11, measured 2026-09-28). RECORDED NEGATIVE CONTROL:
    with the reach test reading a "vocab:suffix" token as no suffix
    piece (returning False there), 878 positions fail (measured
    2026-09-28)."""
    texts = {case.text for case in CASES if case.policy is None
             and case.locale is None}
    for n in (1, 2, 3):
        for run in itertools.product(_REACH_WORDS, repeat=n):
            for head in ("John Smith ", "Doe, Jane "):
                texts.add(head + " ".join(run))
    failures = _reach_failures(sorted(texts))
    assert not failures, (f"{len(failures)} anchored member(s) the "
                          f"reach test hides:\n" + "\n".join(failures[:15]))


def test_a_title_the_fixed_point_splices_out_keeps_no_peel_pick() -> None:
    # tail_reading's resumed pass (#558) carries the picks of the walk
    # before it, and that walk STOPPED at the title the chain then took:
    # where the title is also an ambiguous acronym the stop was a pick,
    # and a fresh walk over the spliced pieces never meets the word.
    # No default title is an ambiguous acronym, so a caller's lexicon is
    # the only way here. Recorded negative control (2026-10-01): with
    # the drop removed, this reads the same fields and reports
    # 'suffix-or-name' on 'Ma.', a word the parse took as a title.
    parser = Parser(lexicon=Lexicon.default().add(titles={"ma"}))
    name = parser.parse("John Smith Ma. PhD Jr.")
    assert (name.title, name.given, name.family, name.suffix) == (
        "Ma.", "John", "Smith", "PhD Jr.")
    assert name.ambiguities == ()


# rules.md#S2 (#602): a credential after the name core starts a run to
# the end of its part. The exclusion tests pass before the change too:
# they are the negative controls that make the first two meaningful.
def test_a_credential_after_two_name_words_starts_the_run() -> None:
    name = parse("John Smith PhD Jones")
    assert (name.given, name.family, name.suffix, name.middle) == (
        "John", "Smith", "PhD Jones", "")


def test_a_title_word_inside_the_run_reads_as_a_title() -> None:
    name = parse("Eric H. Holder Jr. Attorney General")
    assert (name.title, name.suffix, name.family) == (
        "Attorney General", "Jr.", "Holder")


def test_a_title_word_never_starts_the_run() -> None:
    # 746 title words are in no suffix set, many of them surnames
    assert parse("Mary Jane King Smith").family == "Smith"


def test_the_ambiguous_class_and_initials_do_not_start_the_run() -> None:
    assert parse("John Smith MA Jones").family == "Jones"
    assert parse("John Smith V Jones").family == "Jones"


def test_a_joined_connective_does_not_start_the_run() -> None:
    assert parse("Josep Carod i Rovira").suffix == ""


def test_one_name_word_before_the_credential_is_no_core() -> None:
    assert parse("John PhD Smith").family == "Smith"


def test_the_given_part_after_a_family_comma_reads_the_run_too() -> None:
    name = parse("Smith, John PhD Jones")
    assert (name.given, name.family, name.suffix, name.middle) == (
        "John", "Smith", "PhD Jones", "")


def test_a_title_inside_the_given_parts_run_is_a_title() -> None:
    name = parse("Holder, Eric Jr. Attorney General")
    assert (name.title, name.suffix) == ("Attorney General", "Jr.")


# #610: `trailing_candidates` is the maiden take's choice of which
# clause words to read the clause-free view over, and its contract is
# a SUPERSET of what `tail_reading` takes from that view. Checked AT
# THE TAKE, on the pieces the take is handed -- before any join, which
# is where it runs -- by wrapping `_group._maiden_take` and the
# candidates call inside it: the clause-free name is the head plus every
# clause word after the first (which the take always keeps), and every
# piece the tail reading takes from it must fall at or after the cut.
_CANDIDATE_HEADS = ("Jane Doe", "J.", "Jane van der Berg", "Mai Le",
                    "abdul Berg", "John")
_CANDIDATE_WORDS = ("Smith", "VI", "V", "III", "MA", "Ma", "PhD", "Jr.",
                    "Prof.", "Dr.", "King.", "do", "DO", "de", "X.Y.Z.",
                    "Ph. D.", "i", "Jones")


def _candidate_misses(monkeypatch: pytest.MonkeyPatch,
                      candidates: Callable[..., int] = trailing_candidates,
                      ) -> list[str]:
    misses: list[str] = []
    seen: list[tuple[int, int]] = []
    real_take = _group._maiden_take

    def cut(lo: int, pieces: Sequence[Sequence[int]],
            ptags: Sequence[Set[str]],
            tokens: Sequence[WorkToken]) -> int:
        c = candidates(lo, pieces, ptags, tokens)
        seen.append((lo, c))
        return c

    def take(pieces: Sequence[Sequence[int]], ptags: Sequence[Set[str]],
             tokens: Sequence[WorkToken], one_case: bool | None,
             site: _group.ClauseSite,
             ambiguities: list[PendingAmbiguity],
             ) -> _group.MaidenIndices | None:
        seen.clear()
        answer = real_take(pieces, ptags, tokens, one_case, site,
                           ambiguities)
        for lo, c in seen:
            m = next(v for v in range(1, len(pieces))
                     if _group._is_maiden_marker_piece(pieces[v], tokens))
            left = list(range(m)) + list(range(lo + 1, len(pieces)))
            view = [pieces[q] for q in left]
            vtags = [ptags[q] for q in left]
            rest = peel_walk(leading_titles(view, vtags, tokens), vtags)
            kept, chained, peel = tail_reading(rest, view, vtags, tokens,
                                               one_case)
            taken = {left[q] for q in (*kept[peel.names:], *chained)
                     if q >= m}
            if any(j < c for j in taken):
                misses.append(" ".join(tokens[i].text for p in pieces
                                       for i in p))
        return answer

    monkeypatch.setattr(_group, "trailing_candidates", cut)
    monkeypatch.setattr(_group, "_maiden_take", take)
    for head in _CANDIDATE_HEADS:
        for n in (1, 2, 3):
            for tail in itertools.product(_CANDIDATE_WORDS, repeat=n):
                _through_group(f"{head} nee Smith {' '.join(tail)}")
    return misses


def test_the_trailing_candidates_cover_what_the_tail_reading_takes(
        monkeypatch: pytest.MonkeyPatch) -> None:
    """M2's take ends the clause at the trailing run the clause-free
    name reads, which it can only find if every word that run might
    hold is in its view. 6 heads x 18 words to a tail of three after
    'nee Smith', 37,044 parses through `group`, about 2.6s on py3.11
    (measured 2026-10-04).

    RECORDED NEGATIVE CONTROL, measured 2026-10-04 on this grid: the
    candidate loop as #601 shipped it (master 8a8459a8), which admitted
    a roman numeral by its shape only as the clause's LAST word, misses
    432 texts -- every one a numeral in no wordlist ('VI') with
    a period-marked title or the merged 'Ph. D.' behind it. The chain
    takes the title first, and the walk never holds the flagged
    'Ph. D.', so either way the numeral is the walk's last piece and
    the fork reads it: 'Jane Doe nee Smith VI Prof.' kept maiden 'Smith
    VI' where 'John Smith VI Prof.' reads suffix 'VI'. A first draft of
    the fix covered the title half and missed the 'Ph. D.' half.

    A first version of this test read plain names through all of
    `group`, so its pieces had the joins applied that the take runs
    before ('de VI Prof.' arrived as one piece); review moved the
    oracle to the take itself.
    """
    assert _candidate_misses(monkeypatch) == []
