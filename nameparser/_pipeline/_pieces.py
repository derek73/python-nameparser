"""Shared piece-level predicates for pipeline stages.

How a PIECE reads -- its tokens, plus the tags classify wrote on them
and the tags group derived for the piece -- where _vocab answers how a
WORD reads from text alone. Both are consulted by more than one
stage; the split is by what the question takes, not by
which stage happens to ask (mechanisms.md#ONE-PREDICATE-PER-QUESTION).
_vocab points here from its own side: "Text-level tests used by more
than one stage; piece-level ones live in _pieces, the sibling layer
over tokens-plus-tags." own_words (#289/#516) answers over the whole
token STREAM rather than one piece -- pieces do not exist yet at the
stages that call it -- but the question is still piece-shaped, not
word-shaped: it reads token ROLE, which _vocab's text-level tests
never take.

Before this module those predicates lived in _group, not because
grouping owned them but because assign imported group and could not be
imported back, so group was the only place both stages could reach.
They arrived there that way across three PRs -- #424 brought
is_leading_title, leading_titles and trailing_start, #425 the peel
(peel_walk, peel_trailing), #429 the no-name-segment test that
#430 turned into segment_suffix_reading.
is_title_piece and is_suffix_piece are older than any of that: they
were group's from its first commit, and travel because the others
call them.

The import that forced all of it is the one #439 removed: assign no
longer names _group at all. What still holds is the rule that replaced
it, and tests/v2/test_layering.py is where it is written down -- a
piece predicate may not depend on a stage, in either direction.

The S2 trailing peel travels as the unit decisions.md describes --
peel_walk, peel_trailing and trailing_start together -- though only
the first two cross a stage boundary. trailing_titles joins them
because it reads what that peel left: the two answer one question
between them, where the tail of a name stops being the name -- and
tail_reading is that one question, running them against each other to
their fixed point for the two stages that must not disagree about the
answer.

Layering: imports _state and _vocab only; FOUR stages import it --
_segment, _classify, _group and _assign, segment being the one the
#289/#516 own-words span added -- and neither of the two it imports
imports it back.

Naming follows _vocab's: inside an already-private module the leading
underscore marks module-PRIVATE, so the names other stages call are
bare and only the internals keep it (_PERIOD_ABBREV here). Getting that
backwards -- which this module did until the underscores came off --
costs a reader the one cheap way to tell a shared predicate from a
helper.
"""
from __future__ import annotations

from collections.abc import Mapping, Sequence, Set
from typing import NamedTuple

from nameparser._pipeline._state import (
    AMBIGUOUS_ACRONYM_TAG, SHAPE_ACRONYM_TAG, WorkToken,
)
from nameparser._pipeline._vocab import (
    _PERIOD_ABBREV, Lean, ambiguous_lean, in_initialless_script,
    is_trailing_numeral_suffix, tag_marker_runs,
)


# rules.md#P3: "both questions this rule asks of a name — how many
# words it has, and whether it is written in one case — are asked of
# the name's OWN words: a maiden marker taken as one, and the words it
# takes (M2), are not among them, and neither is a delimited clause
# (N1, M1)" (history: decisions.md#P3)
def own_words(tokens: Sequence[WorkToken], comma_offsets: Sequence[int],
              markers: frozenset[str],
              marker_tags: Mapping[int, str] | None = None,
              ) -> tuple[list[str], int]:
    """The name's OWN word texts and the index the maiden clause
    starts at -- one span for the two stages that ask about it
    (#289/#516).

    Own words are the role-less tokens before the clause: a delimited
    clause's tokens arrive from extract with a role already set, and
    everything from a maiden marker on is the clause. Appending a
    clause to a name must not change how a word in the name reads.

    `marker_tags` is the map `_vocab.tag_marker_runs` already built,
    index -> "vocab:maiden-marker"/"...-cont"; a caller that has it
    (classify) hands it over and pays no second walk. A caller that
    runs BEFORE those tags exist (segment) omits it, and this
    function calls `tag_marker_runs` itself to build the SAME map
    classify would -- not an approximation of it, which is what a
    from-scratch text walk (this module's earlier `first_marker_head`)
    could disagree with on a name where a marker's head opens an entry
    but no run completes ('z' of 'z domu'): measured, 'ANNA z Nowak,
    MD' flipped the recorded one-case verdict under that approximation
    (decisions.md#P3). Sharing the exact function instead makes the
    two paths agree by construction, not by corpus luck.

    Takes tokens/comma_offsets/markers rather than a whole ParseState:
    both call sites have all three already, and passing them lets this
    function sit beside the piece predicates rather than in _vocab
    (mechanisms.md#ONE-PREDICATE-PER-QUESTION; the
    _post_rules.suffix_entries precedent, AGENTS.md's named exception)
    -- it answers with the SPAN, where `tag_marker_runs` answers only
    which tokens open a run.

    `marker_tags`' keys must arrive in index order for the walk below
    to find the SMALLEST head in one pass: `tag_marker_runs` walks its
    tokens left to right, so the first head it records is already the
    smallest, and a caller building its own map must preserve that
    order too.

    A plain tuple, not a NamedTuple: measured 2026-09-17, wrapping
    this in a `NamedTuple` (this module's `Peel` is one) cost the
    reference name one more frame (413.00 vs the 412.00 band this
    commit must hold) -- a NamedTuple's `__new__` is itself a call,
    where a bare tuple literal is not. `Peel` can afford the frame
    because assign builds one only where the trailing peel actually
    ran; `own_words` returns on every parse.
    """
    if marker_tags is None:
        marker_tags = tag_marker_runs(tokens, comma_offsets, markers)
    clause_at = len(tokens)
    for i, tag in marker_tags.items():
        if tag == "vocab:maiden-marker" and tokens[i].role is None:
            clause_at = i
            break
    return ([t.text for t in tokens[:clause_at] if t.role is None],
            clause_at)


# rules.md#H3: "successive title words at the start of the part
# carrying the given name chain into one title; a title word
# elsewhere in the name does not"
def is_title_piece(piece: Sequence[int], ptags: Set[str],
                    tokens: Sequence[WorkToken]) -> bool:
    if "title" in ptags:
        return True
    return len(piece) == 1 and "vocab:title" in tokens[piece[0]].tags


# _PERIOD_ABBREV: imported from _vocab, not redefined here (#289/#516,
# quality-review finding) -- _vocab.name_word_count needed the SAME
# shape test is_leading_title asks (_vocab.is_title_shaped), and
# layering only allows the move in that direction (_pieces may import
# _vocab; _vocab may not import _pieces). tests/v2/test_regex_sync.py
# still reaches it as `_pieces._PERIOD_ABBREV` -- an import binds the
# same name here, so the sync test's target did not move. Out of
# assign since #424 and in the piece layer since #439: the test is
# assign's, and group's leading-particle scan and trailing-run walk
# must start where assign starts.


# rules.md#H2: "an abbreviation opening the part of the name that
# carries the given name — the whole name, or the part after a
# family comma — reads as a title even when unlisted"
# (history: decisions.md#H2)
def is_leading_title(piece: Sequence[int], ptags: Set[str],
                      tokens: Sequence[WorkToken]) -> bool:
    if is_title_piece(piece, ptags, tokens):
        return True
    if len(piece) != 1:
        return False
    text = tokens[piece[0]].text
    # INLINED rather than calling _vocab.is_title_shaped, which asks
    # the exact same question (#289/#516, quality-review finding: the
    # two must not drift, and did once -- name_word_count's own
    # vocabulary-only title test read 'Xyz.' as a name word where this
    # predicate reads it as a title, and the disagreement flipped a
    # comma structure `Dr. Smith, Ed`'s LISTED spelling did not).
    # Measured, and THIS is the one home for the number -- both
    # `_vocab.is_title_shaped` and `_vocab.name_word_count` point here
    # rather than restating it, two homes for one measurement being
    # how they come to disagree. Routing this hot path through the
    # shared function costs one frame per call (`is_leading_title`
    # runs on every leading piece of every parse, unlike
    # name_word_count's comma-only path), moving the reference name
    # from 412/449 to 417/454 -- five calls on `Dr. Juan de la Vega
    # III`, recomputable with `uv run python
    # tools/perf/call_count.py`. Kept as two
    # spellings of ONE test instead -- if you touch one, touch both,
    # and `test_is_title_shaped_and_is_leading_title_agree` (this
    # module's own test file) checks it over the union of both
    # predicates' example tables rather than leaving it to a sentence.
    return (bool(_PERIOD_ABBREV.match(text))
            and (text.isascii() or not in_initialless_script(text)))


def leading_titles(pieces: Sequence[Sequence[int]],
                    ptags: Sequence[Set[str]],
                    tokens: Sequence[WorkToken]) -> int:
    """How many leading pieces assign peels as titles: the first
    non-title index. A title needs a following piece, unless the whole
    segment is one title (v1 parity). And the run gives back its last
    piece when that piece is a name candidate: where everything behind
    the run is suffix pieces, the run gives back its last piece, when
    that piece is one word and is not itself suffix vocabulary
    (rules.md#H3, decisions.md#H3 -- the block at the floor below
    carries the examples of each half, and the ordering its two inline
    tag reads were measured on).
    One definition, read by assign (which sets the roles) and by the
    chain's trailing-run walk; the leading-particle scan shares the
    predicate, is_leading_title, but stops at a title-and-particle
    word (P4, #367, #424)."""
    n = 0
    while n < len(pieces):
        if ((n + 1 < len(pieces) or len(pieces) == 1)
                and is_leading_title(pieces[n], ptags[n], tokens)):
            n += 1
            continue
        break
    # rules.md#H3: "where everything behind the run is post-nominal,
    # the run gives its last word back to the name, provided that word
    # stands alone and is not itself suffix vocabulary"
    #
    # ONE WORD, because a joined unit led by a title is a title run and
    # handing it back would lose the title: 'Prince of Wales Jr' reads
    # title 'Prince of Wales', family 'Jr', not given 'Prince of Wales'
    # with no title at all.
    #
    # Two residuals. A run whose last word IS suffix vocabulary is not
    # given back, so 'Dr King MD PhD' still reads title 'Dr King MD',
    # family 'PhD'. And the floor asks is_suffix_piece, which vetoes a
    # bare initial-shaped numeral, so 'Dr King V' keeps the whole run
    # as the title and reads the numeral as the name -- given 'V',
    # 'king' being a given-name title and the run's last word, where
    # 'Dr Smith V' reads suffix 'V'. That numeral fork is outside this
    # floor (decisions.md#H3).
    #
    # The two inline tag reads are the cheapest NECESSARY condition for
    # the piece behind the run to be a suffix piece at all --
    # is_suffix_piece cannot answer yes without one of them -- so the
    # ordinary titled name, whose next piece is no kind of suffix,
    # leaves this branch without entering a frame. Measured on the
    # plan's ordering rather than the shape below: asking the
    # authoritative predicate first cost 8 calls per parse of the
    # reference name (leading_titles runs four times), against a band
    # with room for two (decisions.md#parse-cost). is_suffix_piece
    # stays the predicate that ANSWERS, here and in the walk.
    if (n and n < len(pieces)
            and ("suffix" in ptags[n]
                 or "vocab:suffix" in tokens[pieces[n][0]].tags)
            and len(pieces[n - 1]) == 1
            and not is_suffix_piece(pieces[n - 1], ptags[n - 1],
                                    tokens)):
        for k in range(n, len(pieces)):
            if not is_suffix_piece(pieces[k], ptags[k], tokens):
                break
        else:
            # nothing behind the run but suffix pieces
            n -= 1
    return n


def is_suffix_piece(piece: Sequence[int], ptags: Set[str],
                     tokens: Sequence[WorkToken]) -> bool:
    if "suffix" in ptags:
        return True
    if len(piece) != 1:
        return False
    tags = tokens[piece[0]].tags
    return "vocab:suffix" in tags and "initial" not in tags


def _numeral_behind_the_initial_veto(piece: Sequence[int],
                                     tokens: Sequence[WorkToken]) -> bool:
    """Suffix vocabulary that is_suffix_piece refuses because it is
    also initial-shaped: a ONE-CHARACTER entry, bare or with a period.

    Named for the shape rather than enumerated, because the shape is
    what the code tests and the enumeration goes stale -- in the
    shipped lexicon it reaches i, v and 2, and NOT x or ix (roman, but
    not suffix vocabulary) nor ii/iii/iv (suffix vocabulary, but two
    characters, so never initial-shaped and never vetoed in the first
    place). A caller adding a one-character suffix in a script that
    has initials extends it.

    The veto is right where such a word could be a middle initial, and
    wrong where it is describing the suffix in front of it, which is
    the only place this is asked from. The len(piece) != 1 guard is
    defensive: a merged multi-token piece carries "suffix" in ptags, so
    is_suffix_piece claims it one branch earlier and no reachable input
    arrives here with one.
    """
    if len(piece) != 1:
        return False
    tags = tokens[piece[0]].tags
    return "vocab:suffix" in tags and "initial" in tags


def segment_suffix_reading(pieces: Sequence[Sequence[int]],
                           ptags: Sequence[Set[str]],
                           tokens: Sequence[WorkToken],
                           lenient: bool,
                           one_case: bool | None,
                           ) -> tuple[bool, ...] | None:
    """How each piece of a no-name segment reads: True a suffix, False
    a title. None when the segment holds a name word and so is not a
    credential run at all.

    `one_case` admits #289's credential lean: an ALL-CAPS member of
    the ambiguous set inside a mixed-case name is a credential in this
    slot even with one word before the comma, because the writing is
    evidence the count does not have ('Smith, MA' -> family 'Smith',
    suffix 'MA'). Only the LEAN reaches here: a token admitted to the
    class by SHAPE takes the count instead, which is decided at the
    comma and not in this walk ('Smith, A.B.' -> given 'A.B.').

    ONE answer for two readers, both in _assign.py -- the no-name gate
    and the router -- because they must agree piece for piece. #429
    shipped the inverse of its own fix by deriving that agreement twice
    (mechanisms.md#ONE-PREDICATE-PER-QUESTION). It answered for a third
    until #436: group's one-entry join asked it too, and the render's
    entry boundary is a rule over the written commas in post_rules now
    (rules.md#R1), which asks this nothing.

    rules.md#S2's initial veto keeps a roman numeral out of a suffix
    reading, which is right after a NAME word: 'Smith, John V.' is a
    middle initial (#432). After a SUFFIX word the numeral is
    describing that suffix -- 'PSM I' is Professional Scrum Master
    level I -- so the run continues through it, period included, an
    initial there being no shape anyone writes (#430). A title resets
    that: what follows a bare title is not continuing a credential.

    None covers both ways a segment can fail to be a run: a name word
    anywhere in it, and no pieces at all ('Doe,, Jr.', which holds no
    title to read by).

    `lenient` is Policy.lenient_comma_suffixes, and only the numeral
    continuation consults it. C1: "by default a recognized suffix word
    counts even written like an initial, while strict mode vetoes
    initial-shaped words" -- so under strict the veto stands and the
    run ends where it always did. Reading no policy here silently
    overrode the one knob a caller sets to prevent exactly this.

    The FAMILY_COMMA rule "segment 0 is wholly the family name" rests
    on the writer having said where the family name ends. A comma
    followed by no name word said no such thing -- 'John Smith, Dr.' is
    'Dr. John Smith' with the honorific moved -- so the pre-comma name
    keeps its positional read instead of being merged. Uses the same
    is_leading_title predicate the peel does, period-abbreviation
    inference included, so the two cannot disagree about what a title
    is; a mixed run like 'Smith, Dr. Jr.' is a title and a postnominal,
    each read where it stands, never a title run 'Dr. Jr.'.
    """
    if not pieces:
        return None
    out: list[bool] = []
    for piece, tags in zip(pieces, ptags):
        # the verdict just recorded IS "stands behind a suffix" -- keeping
        # a separate flag meant maintaining that equality by hand at three
        # sites, and a fourth branch that appended without assigning would
        # have diverged silently
        after_suffix = bool(out) and out[-1]
        if is_suffix_piece(piece, tags, tokens):
            out.append(True)
        elif (len(piece) == 1
                and AMBIGUOUS_ACRONYM_TAG in tokens[piece[0]].tags
                and listed_lean(tokens[piece[0]], one_case)
                == "credential"):
            out.append(True)
        elif (lenient and after_suffix
                and _numeral_behind_the_initial_veto(piece, tokens)):
            out.append(True)
        elif is_leading_title(piece, tags, tokens):
            out.append(False)
        else:
            return None
    return tuple(out)


class Peel(NamedTuple):
    """What assign's trailing peel made of a walk. `names` is a count
    of positions in the caller's `rest`: rest[:names] are the name
    pieces and rest[names:] the suffixes. The other two are pieces --
    token-index tuples, as PendingAmbiguity wants them -- and each is
    one token long: `numeral` is the piece the roman-numeral fork
    took (None when it did not fire; always the walk's last piece),
    `picks` the bare ambiguous acronyms the peel had to resolve, in
    peel order, either way (the last may sit at rest[names - 1])."""

    names: int
    numeral: tuple[int, ...] | None
    picks: tuple[tuple[int, ...], ...]


# rules.md#S2: "a trailing word of the suffix vocabulary reads as a
# suffix — generational forms and credential acronyms alike, and an
# ambiguous acronym written with its periods, one after each letter,
# counts unambiguously; a single trailing period is the abbreviation
# shape any word can wear and does not. A BARE ambiguous acronym is
# consumed only when the name has words to spare"
# (v1's are_suffixes tail rule, with the roman-numeral special)
def peel_walk(start: int, ptags: Sequence[Set[str]],
               skip: Set[int] = frozenset()) -> list[int]:
    """The indices peel_trailing walks: `start` to the segment's end,
    minus the group-flagged credential pieces (the Ph. D. merge),
    which assign reads as suffixes at any position, and minus `skip`
    -- a tail segment's delimiter cores, which are structure rather
    than words (the maiden walk's case, #424). Built here and nowhere
    else, so the walk's input cannot drift between assign and the
    group sites that read it: the numeral fork is a last-piece
    test that reads the piece before as rest[k - 2], which holds only
    over this list."""
    return [j for j in range(start, len(ptags))
            if j not in skip and "suffix" not in ptags[j]]


def trailing_start(start: int, pieces: Sequence[Sequence[int]],
                    ptags: Sequence[Set[str]], tokens: Sequence[WorkToken],
                    skip: Set[int] = frozenset(),
                    numeral_only: bool = False,
                    *, one_case: bool | None) -> int:
    """Where assign's trailing suffix run begins, read over the pieces
    as they stand from `start`: the index of the first piece the S2
    peel takes, or len(pieces) when it takes none (#424). What P2's
    chain and M2's walk stop before -- each had asked "is this a
    suffix?" with the suffix-piece test, which vetoes a bare 'V' as
    an initial (the #401 question), and so took a trailing numeral,
    or a bare acronym with words to spare, into the family or the
    maiden name.

    `numeral_only` is the maiden walk's reading: the bare-acronym
    fork counts pieces, and the walk removes the very pieces it
    counted, so an acronym peeled over the pieces as they stand may
    be the family of what is left ('John née Jones Smith Ma' read
    maiden 'Jones Smith', family 'Ma'). The numeral fork reads one
    piece, the one before the numeral, and _maiden_take re-asks it
    with the piece the take leaves there; the acronym is left to
    assign."""
    rest = peel_walk(start, ptags, skip)
    peeled = peel_trailing(rest, pieces, ptags, tokens, one_case)
    if numeral_only:
        return rest[-1] if peeled.numeral is not None else len(pieces)
    return rest[peeled.names] if peeled.names < len(rest) else len(pieces)


# #289/#516: the "listed member, not by-shape" test both
# peel_trailing and segment_suffix_reading ask before reading the
# lean -- shared here so the two cannot drift on what counts
# (quality-review finding: it was spelled twice, once per site,
# before this). Both callers test "vocab:suffix-ambiguous" in tags
# INLINE, before calling this, rather than leaving that cheap check to
# this function's own body: measured, a caller whose `elif` reaches
# this on every piece (segment_suffix_reading's does, one per
# family-comma segment 1, member or not) pays one frame for the call
# regardless of what is inside it, and the inline pre-check is what
# keeps a non-member piece ("Smith, John"'s "John") from ever making
# the call at all.
def listed_lean(token: WorkToken, one_case: bool | None) -> Lean | None:
    """`ambiguous_lean` for a LISTED bare-ambiguous token, or None if
    the token is not tagged a listed member, is admitted by SHAPE
    instead (`SHAPE_ACRONYM_TAG`, a switch's doing, not the writing's),
    or there is no case fact to ask at all."""
    if (one_case is None or AMBIGUOUS_ACRONYM_TAG not in token.tags
            or SHAPE_ACRONYM_TAG in token.tags):
        return None
    return ambiguous_lean(token.text, one_case)


def peel_trailing(rest: Sequence[int], pieces: Sequence[Sequence[int]],
                   ptags: Sequence[Set[str]],
                   tokens: Sequence[WorkToken],
                   one_case: bool | None) -> Peel:
    """The S2 trailing peel over `rest`, a peel_walk list. In the
    piece layer rather than in assign because group's bound-given
    reserve asks the same question of the view the join would leave
    (#425): one walk, so the reserve and the assignment cannot drift. Pure -- the ambiguities are
    returned for assign to report, in the order it always reported
    them.

    `one_case` is ParseState.one_case, the recorded fact: None means
    nobody asked, which is every caller that has no state to ask with,
    and reads as "no lean" -- rules.md#S2's count alone, the behavior
    of every release before this one.
    """
    picks: list[tuple[int, ...]] = []
    numeral: tuple[int, ...] | None = None
    k = len(rest)
    while k > 0:
        piece = pieces[rest[k - 1]]
        if is_suffix_piece(piece, ptags[rest[k - 1]], tokens):
            k -= 1
            continue
        # a final single letter that is a roman numeral, after a piece
        # that is not initial-shaped; the predicate's docstring carries
        # the is_initial_shaped reasoning (#320)
        if (k == len(rest) and k >= 2 and len(piece) == 1
                and is_trailing_numeral_suffix(
                    tokens[piece[0]].text,
                    tokens[pieces[rest[k - 2]][0]].text)):
            numeral = tuple(piece)
            k -= 1
            continue
        # A bare ambiguous acronym ("MA", not "M.A.") is a credential
        # only when peeling it still leaves a given AND a family name.
        # With two pieces, "one of them is a credential" is the less
        # likely reading, so it stays the family name -- "Jack MA" is a
        # person, "John Smith MA" is a person with a degree. This is
        # v1's reserve_last narrowed to the ambiguous set: 2.0
        # deliberately peels UNambiguous suffixes even when nothing is
        # left ("Smith PhD" -> suffix, a classified fix), because there
        # the vocabulary is not in doubt.
        bare_ambiguous = (len(piece) == 1
                          and AMBIGUOUS_ACRONYM_TAG in tokens[piece[0]].tags)
        # #516, switch off: the writing still makes this token
        # credential-SHAPED, and the parser is choosing the name
        # reading over that one -- the fork the caller asked to be
        # told about. Reported here, unconsumed, rather than folded
        # into `bare_ambiguous` above: with the switch off the token
        # never carries "vocab:suffix-ambiguous" (classify's own
        # gate), so `bare_ambiguous` is already False and this is the
        # ONLY place the report can be recorded. Switch ON, the token
        # carries BOTH tags, so `not bare_ambiguous` is what stands
        # this branch down and lets the consuming branch below take
        # it; the two are not exclusive.
        if (not bare_ambiguous and k >= 2 and len(piece) == 1
                and SHAPE_ACRONYM_TAG in tokens[piece[0]].tags):
            picks.append(tuple(piece))
            break
        # #289: written case is evidence the count does not have, and
        # it overrides the count in BOTH directions -- an all-caps
        # member of a mixed-case name is taken with nothing to spare
        # ("Jack MA"), a Title-case one is declined with plenty
        # ("John Smith Ma"). The lean is the LISTED set's alone: a
        # token admitted to this class by SHAPE carries no writing
        # convention to read, so it takes the count (decisions.md#S2).
        #
        # k < 2 means it is the only piece left, which is not the fork
        # this reports -- and not a floor the lean moves: the walk
        # starts after the leading title run, so one piece behind a
        # title ("Mr MA") is exactly this case and must stay a name.
        # The lean is computed only past this floor -- membership,
        # then the floor, then the count-or-lean, in that order, with
        # nothing computed a step earlier could discard.
        if bare_ambiguous and k >= 2:
            picks.append(tuple(piece))
            lean = listed_lean(tokens[piece[0]], one_case)
            # peeling still leaves given + family, or the writing says
            # to peel anyway
            if lean == "credential" or (lean is None and k >= 3):
                k -= 1
                continue
        break
    return Peel(k, numeral, tuple(picks))


# rules.md#H5: "only a word the vocabulary knows as a title is one,
# and a bare title word is a name word"
# -- the trailing run's own predicate. NOT is_leading_title:
# that predicate carries H2's unlisted-abbreviation inference, which is
# the LEADING slot's shape rule and has no trailing counterpart, so
# with it 'John Smith Xyz.' would lose its family name to a title
# (decisions.md#H5). The vocabulary read is is_title_piece's, shared
# with the leading run so the two cannot disagree about what a title
# WORD is while disagreeing, deliberately, about what a title SHAPE is.
def trailing_titles(rest: Sequence[int], pieces: Sequence[Sequence[int]],
                     ptags: Sequence[Set[str]],
                     tokens: Sequence[WorkToken]) -> int:
    """How many pieces of `rest` the trailing title chain LEAVES
    standing: `rest[:kept]` are the name pieces and `rest[kept:]` the
    period-marked title words the chain took, in piece order. Counted
    the way `peel_trailing` counts, so the two answers compose without
    arithmetic at the call site. `rest` is the caller's NAME pieces:
    on the no-comma path what the S2 peel left, after a family comma
    the segment's pieces that the segment's own suffix reading does
    not claim, and in `tail_reading` the leftovers of whichever peel
    is current.
    Floor: one name piece stands, so a name is never all title -- and
    an empty `rest` returns 0, which is what leaves assign's
    bare-suffix carve-out reached exactly as before.

    ONE WORD per piece, the same gate the leading peel's give-back
    uses: a joined unit is not the shape this reads, and the tokens of
    one are not each a title word.

    Every parse with a name word to place enters this frame -- assign
    asks the question here rather than answering a cheaper version of
    it inline (mechanisms.md#ONE-PREDICATE-PER-QUESTION) -- so what it
    costs an ordinary name is one frame and one regex match. The
    exceptions return before it: a segment that is all title, and a
    comma part read wholly as a credential run, have no name piece to
    hand this (52 of the 1289 corpus parses, measured 2026-09-09 --
    'Coach', 'Lord of the Universe', 'Smith, Jr.', 'MD, PHD').
    The shape test
    runs BEFORE the vocabulary one to keep it at that: _PERIOD_ABBREV
    is a compiled regex (a C call, no Python frame) where
    is_title_piece is a call, and almost no name ends in a
    period-marked word, so the ordinary parse pays the one match and
    stops (decisions.md#parse-cost).
    """
    k = len(rest)
    while k > 1:
        idx = rest[k - 1]
        piece = pieces[idx]
        # no #323 veto on the shape here, unlike is_leading_title's:
        # the shape is ANDed with is_title_piece, so the word is listed
        # vocabulary, and a listed CJK title wearing a stop should read
        # as a title.
        if (len(piece) == 1
                and _PERIOD_ABBREV.match(tokens[piece[0]].text)
                and is_title_piece(piece, ptags[idx], tokens)):
            k -= 1
            continue
        break
    return k


# rules.md#H5: "the title is TRANSPARENT to the suffix reading: where
# two or more name words stand, what stands once the chain is taken
# reads exactly as it would read written without the title, plus the
# title"
def tail_reading(rest: list[int], pieces: Sequence[Sequence[int]],
                  ptags: Sequence[Set[str]],
                  tokens: Sequence[WorkToken],
                  one_case: bool | None,
                  ) -> tuple[list[int], tuple[int, ...], Peel]:
    """The S2 peel and the H5 chain read together to a FIXED POINT:
    peel, chain, splice the chained pieces out, peel again over what
    is left -- the name pieces the chain kept, then the pieces the
    peel had taken, in original order -- until the chain takes
    nothing. Where it takes nothing on the first pass, which is almost
    every name, that first peel is the answer and the loop costs one
    comparison.

    Returns the walk with the chained pieces spliced out, the pieces
    the chain took, and the FINAL peel -- whose numeral fork and
    ambiguous picks are the ones assign reports. The walk is
    partitioned by that peel exactly as a caller partitions its own:
    `rest[:peel.names]` the name pieces, `rest[peel.names:]` the
    suffixes. A bare tuple rather than a named one because a
    NamedTuple's __new__ is a frame of its own on every parse
    (decisions.md#parse-cost), and `_group_segment` returns its three
    the same way.

    Transparency is what the fixed point buys: 'X Prof. Y' reads
    exactly as 'X Y' reads plus the title, however many titles are
    written and wherever the peel then stops. Iterating ONCE reads a
    second title only half way -- 'John Prof. MA Prof.' un-peeled the
    acronym and re-exposed the first title, reading family 'Prof.'
    with suffix 'MA' where 'John Prof. MA' reads family 'MA'.

    One function for two readers -- assign's placement and group's
    bound-given reserve (P5), which must count the name words assign
    will leave. Deriving that agreement twice is what left the two
    disagreeing at S2's bare-ambiguous reserve: 'abdul rahman MA'
    declined the join and 'abdul rahman MA Prof.' took it
    (mechanisms.md#ONE-PREDICATE-PER-QUESTION).

    `rest` is a peel_walk list and is not mutated -- the splice
    rebinds this local -- so a caller's own reference still names the
    walk it built. Both callers read the one returned here instead,
    which is the one the final peel partitions.
    """
    titled: list[int] = []
    while True:
        peeled = peel_trailing(rest, pieces, ptags, tokens, one_case)
        kept = trailing_titles(rest[:peeled.names], pieces, ptags,
                               tokens)
        if kept == peeled.names:
            return rest, tuple(titled), peeled
        # the chain's pieces reach this list back to front, so each
        # run goes in FRONT of what the pass before it took
        titled[:0] = rest[kept:peeled.names]
        rest = rest[:kept] + rest[peeled.names:]
