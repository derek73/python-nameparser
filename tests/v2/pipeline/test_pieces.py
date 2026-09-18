"""Unit tests for the shared piece predicates.

_pieces has had no unit-test module since #439 moved it out of _group;
its predicates were reached only end to end through the case table.
These pin the two contracts that shape cannot reach: a defensive branch
no parse can produce, and the stability its readers rest on.
"""
from collections.abc import Sequence, Set

import pytest

from nameparser._lexicon import Lexicon, _normalize
from nameparser._pipeline import STAGES
from nameparser._pipeline._assign import assign
from nameparser._pipeline._classify import classify
from nameparser._pipeline._group import group
from nameparser._pipeline._pieces import (
    _numeral_behind_the_initial_veto, is_leading_title, leading_titles,
    own_words, peel_trailing, peel_walk, segment_suffix_reading,
    trailing_titles,
)
from nameparser._pipeline._segment import segment
from nameparser._pipeline._state import ParseState, WorkToken
from nameparser._pipeline._tokenize import tokenize
from nameparser._pipeline._vocab import is_one_case, is_title_shaped, tag_marker_runs
from nameparser._policy import Policy


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
    run at all and the segment falls to the walk.
    """
    state = _through_group("Smith, PSM I")
    args = (state.pieces[1], state.piece_tags[1], list(state.tokens))
    assert segment_suffix_reading(*args, True, state.one_case) == (True, True)
    assert segment_suffix_reading(*args, False, state.one_case) is None


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


def test_peel_trailing_stops_at_a_declined_ambiguous_pick() -> None:
    # The accepted cost (decisions.md#S2): the surname lean breaks the
    # walk AT 'Ma', so the unambiguous 'Jr' in front of it is never
    # reached and becomes a name word. The walk stops at the declined
    # pick rather than continuing past it.
    rest, pieces, ptags, tokens = _peel_inputs("abdul Smith Jr Ma")
    peeled = peel_trailing(rest, pieces, ptags, tokens, one_case=False)
    assert peeled.names == len(rest)


def test_a_shape_only_token_reports_without_being_taken() -> None:
    # Switch A off: name material everywhere, as 2.3 read it -- and
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
