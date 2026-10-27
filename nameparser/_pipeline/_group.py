"""Stage: group.

Consumes: tokens (classified), segments, structure, one_case, extracted
(the role + inner span per delimited region, for the #329 pass below;
post_rules reads it too, for S13); and, through
`_comma.decide`, comma_offsets (the own-words span of the name's case
contrast) and dropped, which decide extends.
Produces: structure -- its head decides a comma form once the words
are tagged (rules/C1, #613, `_comma.decide`), binding the SUFFIX and
TITLE roles of a postnominal part after the comma, emptying its
segment and dropping its delimiter cores before any join, plus the SUFFIX_OR_NAME
ambiguities that decision reports, those the particle chain and a
maiden clause report on a trailing member they take into the name
(an ambiguous acronym, or since #718 a declined numeral), and the
caps shape's acronym tags on
a bound all-caps word (#564); pieces + piece_tags per segment
(runs of token indices -- tokens are NEVER joined into strings: the
anti-#100 invariant); maiden tail tokens get role=MAIDEN, and the
trailing run a maiden take gives up gets its SUFFIX and TITLE roles
here (#601), so no join can reach it; marker tokens land in dropped;
and tail_reads, rules/S2's trailing run of each main segment read
ONCE, after P3's connective joins and before the particle chain and
the bound-given join, and split off so neither reaches it (#614),
which assign places and reports rather than peeling again.
Reads: token tags (from classify), Lexicon.given_name_titles (the
P5 licence, #369) and Policy.extra_suffix_delimiters, whose
delimiter-core tokens part a tail segment as a comma would and are
dropped (v1 suffix_delimiter parity, #549), as the built-in cores'
are (rules/C10, #889); and, through
`_comma.decide`, what that module's own header lists
(Policy.lenient_comma_suffixes and Policy.unlisted_caps_suffixes among
them). The v1
"derived titles/prefixes" registration becomes piece_tags entries --
per-parse state that dissolves with the state (v1 kept per-parse sets
for the same reason).

Implements rules P2, P3, P4 and M2, S2's trailing read (#614), C1's
decision through _comma, and
the
group half of M1 (#329: the marker dropped inside EXTRACTED maiden
content, which M2's pieces walk cannot reach because extract's
content never enters pieces); each is cited at its code below. Also
implements rule P5 (cited below at the bound-given join) and ports
the "Ph. D."-split merge (v1 fix_phd; decisions/phd-merge).

The piece-level predicates moved to _pieces in #439 -- the S2
trailing peel, the leading-title and title-piece tests, the
suffix-piece test, the no-name-segment test. Most are shared with
assign; trailing_start is group's alone and travelled because the
shared ones call it (is_title_piece was too, until #602 and #603 gave
assign calls of its own). They had collected here
by import direction rather than by topic (assign imported group and
could not be imported back), which is the accumulation
mechanisms.md#ONE-PREDICATE-PER-QUESTION describes; group imports them
back like any other caller, and still does the work H3 and S2 describe
with them. is_prefix_piece and is_conj_piece followed in #617, with
the merge and rules/P3's connective joins (join_connectives), when
the comma decision's own copy of those joins was folded into them.
What remains defined here is group's own: _is_rootname and
_is_maiden_marker_piece.
"""
from __future__ import annotations

import bisect
from collections.abc import Iterable, Sequence, Set
from enum import IntEnum
from typing import assert_never

from nameparser._lexicon import _run_addresses_by_given
from nameparser._pipeline._pieces import (
    split_credential_report,
    Peel, TailRead, chain_lead, chain_run_end, is_conj_piece, is_leading_title, is_prefix_piece,
    is_suffix_piece, is_title_piece, join_connectives, joined_tags,
    leading_titles, merge_particle_runs, merge_pieces, peel_walk,
    read_trailing_run, settled_by_case, tail_reading, trailing_candidates,
    trailing_run_start, trailing_start,
    trailing_start_past_titles,
)
from nameparser._pipeline._state import (
    AMBIGUOUS_ACRONYM_TAG, SPLIT_CREDENTIAL_TAG, SPLIT_MEMBER_TAG, ParseState,
    Deferred, PendingAmbiguity, Structure, WorkToken,
    _AMBIGUOUS_CREDENTIAL_TAGS, copy_with,
)
import nameparser._pipeline._comma as _comma
from nameparser._pipeline._vocab import (
    comma_follows_marker, delimiter_cores, name_reading,
    reads_as_a_reported_numeral, suffix_reading,
)
from nameparser._types import AmbiguityKind, Role

# the split credential is `_vocab.split_pair`, which classify asks of
# every adjacent pair and writes on the pair's first word, and which
# is_wholly_suffix asks to merge the same Ph./D. pair, as
# `_comma._pieces` reads the tag -- so that predicate's callers read
# what this stage merges: `_comma.decide`'s reading of the part after
# the comma, segment's C2 flag on a tail part, and script_segment's
# decline of a wholly-suffix post-comma run, all of which see the
# merged reading

Piece = list[int]
#: What the marker pass took out of a segment: the marker's TOKEN
#: indices (more than one where the entry is a phrase, 'z domu'), and
#: every other piece it took with the role that piece takes -- the
#: maiden name's Role.MAIDEN, and the trailing run's SUFFIX or TITLE
#: (#601). `_group_segment` produces it.
MaidenTake = tuple[Piece, list[tuple[Piece, Role]]]
#: What `_maiden_take` answers with, one index space further out: PIECE
#: indices into its own `pieces` argument. `_group_segment` resolves
#: them to the token indices MaidenTake declares, which is the only
#: reason the two are different types rather than one name used twice.
MaidenIndices = tuple[list[int], list[tuple[int, Role]]]


class ClauseSite(IntEnum):
    """Where a maiden clause stands, which decides whether a marker
    counts there at all and which rule reads the end of the part
    (rules/M2, #601).

    A marker counts only in the part holding the family name, so
    GIVEN_SLOT and TAIL are statements, not defaults: a marker there is
    an ordinary word. FAMILY_PART is the part before a family comma,
    where a marker counts but no trailing rule reads the words after
    the clause.

    A CLOSED set: `_maiden_take` dispatches on it exhaustively, ONCE
    (`typing.assert_never`). group() is the one place (structure,
    segment index) is mapped onto it, and tests/v2/pipeline/
    test_group.py's `test_the_site_is_pinned_to_the_structure_it_is_
    read_from` pins that mapping -- by watching the call, not by
    restating it -- along with this enum's size.
    """

    FAMILY_PART = 0  # FAMILY_COMMA segment 0: a marker counts, nothing trails
    TRAILING = 1     # NO_COMMA, SUFFIX_COMMA segment 0: S2 peel + H5 chain
    GIVEN_SLOT = 2   # FAMILY_COMMA segment 1: a marker is an ordinary word
    TAIL = 3         # every tail segment: a marker is an ordinary word


class BoundJoin(IntEnum):
    """v1 _join_bound_first_name's reserve_last, as the three states it
    actually has. IntEnum: the value IS the number of name pieces
    assign's peel must leave in the JOINED view for the join to stand
    (#425), so the >= comparison below reads unchanged. Post-comma the
    reserve runs no peel -- the pair alone is that one piece; the
    decline reads H5's trailing run only where a title word follows
    the bound word (#637) -- and DISABLED
    is a mode, never compared: as a threshold 0 would join everything,
    which is why the block is entered on identity first."""

    DISABLED = 0   # the FAMILY_COMMA family segment (v1 never joined it)
    LENIENT = 1    # FAMILY_COMMA's post-comma segment (reserve_last=False)
    STRICT = 2     # main segments (reserve_last=True: keep a family piece)


# rules/M2: "A marker that counts takes the words after it as the
# maiden name, and is itself dropped" -- where a marker counts, and up
# to what, are `_maiden_take`'s (history: decisions/M2)
#
# A marker piece is a LONE marker -- M2's When ("a recognized maiden
# marker stands as a word in a name"). The consumer runs before every join but the Ph. D. merge
# (see _group_segment), so a marker inside a wider piece is one the
# consumer left there: declined ("Jane van der Berg née" reads family
# 'van der Berg née'), or never examined (a leading marker, or a second
# marker behind the span it took). Matching inside joined pieces would
# re-read those.
#
# With the pass ahead of the joins no default-vocabulary input reaches
# the lone-piece half through the one caller left that sees joined
# pieces (P5's marker decline, on `fk + 1`): a marker-headed wider
# piece needs a connective right after a declined marker, and a
# connective after a marker is a word the consumer takes. Measured at
# #420's review --
# dropping `len(piece) == 1` leaves the suite and a 337k-name sweep
# identical -- so it stays as the rule's definition, not as a guard a
# pin holds.
def _is_maiden_marker_piece(piece: Sequence[int],
                            tokens: Sequence[WorkToken]) -> bool:
    return (len(piece) == 1
            and "vocab:maiden-marker" in tokens[piece[0]].tags)


# mechanisms.md#ONE-PREDICATE-PER-QUESTION: "where the reader comes
# AFTER the decider, record the answer on the state instead" -- which is
# what the marker tags are. classify owns the phrase lookahead; group,
# running later, reads what it wrote.
def marker_run_length(following: Iterable[Set[str]]) -> int:
    """How many tokens a marker run spans, given the tag sets of what
    FOLLOWS its head, in order: 1 plus the leading continuations.

    One walk for both places group asks -- over pieces below and over
    token indices in the clause drop at the end of this module, 700
    lines apart and differing only in index space. `following` is
    consumed lazily and only until the run ends, so a caller passes a
    generator over the rest of its sequence rather than materializing
    one."""
    run = 1
    for tags in following:
        if "vocab:maiden-marker-cont" not in tags:
            break
        run += 1
    return run


def _marker_run_pieces(pieces: Sequence[Sequence[int]],
                       tokens: Sequence[WorkToken], m: int) -> int:
    """How many pieces the marker run at pieces[m] spans: 1
    for a single-word marker, more for a phrase entry ('z domu').

    classify already decided where the run ends and recorded it on the
    tokens -- "vocab:maiden-marker" on the head,
    "vocab:maiden-marker-cont" on the rest.

    Each continuation is the NEXT piece, and
    that holds because classify REFUSES to tag a run whose tokens are
    not structurally contiguous. It is not a property of this walk, and
    the reasons a token can be absent between two pieces are wider
    than they look. No join has run yet, so a piece is one token. A
    tail segment is cut at its delimiter cores and grouped part by
    part (#549), and a core between two marker words would be a token
    between them, which classify would not have tagged as a run. And
    `pieces` comes from a SEGMENT, or a part of one, and segment keeps
    only the tokens no stage has given a role, bucketed by the commas
    before them -- so a run half inside a bracketed clause, or split across a
    structure comma, is one no segment holds whole. Walking cont tags
    without classify's refusal read a proper PREFIX of the phrase as
    the whole marker, and 'Anna z (domu) Nowak' lost its given name to
    a bare preposition. Any future stage that removes a token from a
    segment owes this the same refusal.

    What classify guarantees is exactly the main stream's half of that
    and no more: a run of ROLE-LESS tokens stays inside one segment. It
    can also tag a run across two adjacent clauses of the same role,
    which this walk never sees because a role-bearing token is in no
    segment at all -- see _vocab.tag_marker_runs, which states the limit.
    """
    return marker_run_length(
        tokens[pieces[k][0]].tags for k in range(m + 1, len(pieces)))


def _maiden_take(pieces: Sequence[Sequence[int]],
                 ptags: Sequence[Set[str]],
                 tokens: Sequence[WorkToken],
                 one_case: bool | None,
                 site: ClauseSite,
                 ambiguities: list[PendingAmbiguity],
                 ) -> MaidenIndices | None:
    """The PIECE indices the marker pass removes, split the way
    MaidenIndices declares them: the marker's pieces (one, or several
    for a phrase entry like 'z domu'), then the maiden name's and the
    trailing run's, each with the role it takes. None where the marker is
    an ordinary word. Piece indices into `pieces`, not the TOKEN
    indices `_group_segment` builds out of them.

    Three questions, in order (rules/M2, #601):

    * WHERE A MARKER COUNTS. Only in the part holding the family name
      -- never in the given part after a family comma, never in a tail
      part -- and only with a name word straight before it: not a word
      of the leading title run (H3's give-back included, so 'Lord
      Chancellor née Jones' counts; a lone title is a title), not a
      suffix word unless it opens the name (S2), not a connective. A
      particle counts: with nothing after it to attach to it is no
      particle there ('Mai Le née Nguyen').
    * WHAT IT TAKES. Every word after it up to the trailing run the
      name reads as if the clause were not written, and always the
      first word after it. The run is read over the VIEW -- the head
      plus the vocabulary-shaped tail, and anything from the first
      credential that starts a run (S8, #602) -- by `tail_reading`, so
      the count of words to spare is the clause-free name's. Before a
      family comma no trailing rule reads the part, and the family
      part takes a suffix word from anywhere in it: the clause stops
      at the first one and hands the rest back unbound.
    * THE RUN IS BOUND. Where a trailing rule reads the part, the take
      consumes the run and returns the role the reading gave each
      piece, so no join below this pass can reach into it.

    Computed before any join (the Ph. D. merge aside), as the marker
    pass always has been (#420): the joins see a name without the
    clause in it.
    """
    if site is ClauseSite.GIVEN_SLOT or site is ClauseSite.TAIL:
        return None
    m = next((v for v in range(1, len(pieces))
              if _is_maiden_marker_piece(pieces[v], tokens)), None)
    if m is None:
        return None
    # the marker may be a phrase, in which case it is several pieces
    lo = m + _marker_run_pieces(pieces, tokens, m)
    if lo >= len(pieces):
        return None
    before = m - 1
    lead = (1 if m == 1 and is_title_piece(pieces[0], ptags[0], tokens)
            else leading_titles(pieces[:m], ptags[:m], tokens))
    if (before < lead
            or (before > lead
                and is_suffix_piece(pieces[before], ptags[before], tokens))
            or is_conj_piece(pieces[before], ptags[before], tokens)):
        return None
    # a suffix word straight after the marker: nothing was announced
    if is_suffix_piece(pieces[lo], ptags[lo], tokens):
        return None
    if site is ClauseSite.FAMILY_PART:
        end = next((j for j in range(lo + 1, len(pieces))
                    if "suffix" in ptags[j]
                    or is_suffix_piece(pieces[j], ptags[j], tokens)),
                   len(pieces))
        return list(range(m, lo)), [(j, Role.MAIDEN)
                                    for j in range(lo, end)]
    if site is not ClauseSite.TRAILING:
        assert_never(site)
    c = trailing_candidates(lo, pieces, ptags, tokens)
    end = len(pieces)
    released: list[tuple[int, Role]] = []
    # the view's picks, for the kept member below (#718)
    picked: tuple[tuple[int, ...], ...] = ()
    # nothing behind the clause that a trailing rule could take: the
    # view would be the head alone, and the whole rest is the clause
    if c < len(pieces):
        left = list(range(m)) + list(range(c, len(pieces)))
        view = [pieces[i] for i in left]
        vtags = [ptags[i] for i in left]
        vrest, vchained, vpeel = tail_reading(
            peel_walk(leading_titles(view, vtags, tokens), vtags),
            view, vtags, tokens, one_case)
        picked = vpeel.picks
        titles = set(vchained) | set(vpeel.run_titles)
        in_run = titles | set(vrest[vpeel.names:]) | {
            q for q in range(m, len(view)) if "suffix" in vtags[q]}
        e = len(view)
        while e - 1 >= m and (e - 1) in in_run:
            e -= 1
        end = c + (e - m)
        released = [(j, Role.TITLE if m + (j - c) in titles
                     else Role.SUFFIX) for j in range(end, len(pieces))]
        # rules/S12: "where the count takes the pair, the reading is reported" --
        # the clause-free reading took it, and the take binds it here
        for j, role in released:
            if "split" in ptags[j] and role is Role.SUFFIX:
                ambiguities.append(
                    split_credential_report(
                        pieces[j], tokens,
                        name_reading(tokens[pieces[j][0]], Role.MAIDEN)))
        # mechanisms.md#AMBIGUITY-AT-THE-DECISION-SITE: "Emit at the
        # site that takes the branch, not where an ambiguous tag sits"
        # -- the take consumed the run, so the forks the reading called
        # on it are reported here, where assign will never see them
        consumed = {i for j in range(end, len(pieces)) for i in pieces[j]}
        for piece in (*vpeel.picks, *vpeel.absorbed,
                      *vpeel.numerals):
            if piece[0] in consumed:
                ambiguities.append(PendingAmbiguity(
                    AmbiguityKind.SUFFIX_OR_NAME,
                    f"{tokens[piece[0]].text!r} after the maiden name "
                    f"reads as a suffix; it may be a name word",
                    tuple(piece),
                    # a name word there ends the clause's maiden name
                    alternative=name_reading(tokens[piece[0]],
                                             Role.MAIDEN)))
    # ...and the member the clause KEEPS as its last word: the reading
    # left it a name word, which is a fork too
    last = pieces[end - 1]
    word = tokens[last[0]]
    # a one-word member: a split credential the clause keeps is one the
    # count declined, which reports nothing (rules/S12), and its first
    # word is not the clause's last
    if len(last) == 1 and not word.tags.isdisjoint(_AMBIGUOUS_CREDENTIAL_TAGS):
        ambiguities.append(PendingAmbiguity(
            AmbiguityKind.SUFFIX_OR_NAME,
            f"{word.text!r} ending the maiden name is also a "
            f"post-nominal; the maiden marker's clause keeps it rather "
            f"than reading it as one", tuple(last),
            alternative=suffix_reading(word)))
    elif tuple(last) in picked:
        # rules/S10: "either reading is reported" -- a numeral the read
        # declined, for want of words to spare or for its Title case,
        # which the clause keeps
        why = ("but the name has no other word to spare for it"
               if len(word.text.rstrip(".")) == 1
               else "but written in Title case it leans to the name")
        ambiguities.append(PendingAmbiguity(
            AmbiguityKind.SUFFIX_OR_NAME,
            f"{word.text!r} ending the maiden name is a roman numeral, "
            f"{why}; the maiden marker's clause keeps it rather than "
            f"reading it as a generational suffix", tuple(last),
            alternative=suffix_reading(word)))
    elif (released and len(last) == 1 and end - 2 >= lo
          and reads_as_a_reported_numeral(
              word.text, word.tags, tokens[pieces[end - 2][0]].text,
              one_case)):
        # rules/S10: "a one-letter numeral before a credential is the
        # family name, and the reading is reported" -- the clause's
        # twin of assign's report (#721's review): the clause keeps the
        # numeral its released post-nominal stands behind
        ambiguities.append(PendingAmbiguity(
            AmbiguityKind.SUFFIX_OR_NAME,
            f"{word.text!r} ending the maiden name is a roman numeral, "
            f"but a post-nominal follows it; the maiden marker's clause "
            f"keeps it rather than reading it as a generational suffix",
            tuple(last), alternative=suffix_reading(word)))
    return (list(range(m, lo)),
            [(j, Role.MAIDEN) for j in range(lo, end)] + released)


#: What `_between_name_words` reads instead of walking: two arrays over
#: the segment's pieces, giving for each index the nearest piece on
#: its left and on its right that is NOT a connective -- `-1` and
#: `len(pieces)` where the run reaches the end. Built by
#: `_run_neighbours`, and an ALIAS rather than a NamedTuple because a
#: NamedTuple's __new__ is a frame of its own (decisions/parse-cost).
_Beside = tuple[list[int], list[int]]


def _run_neighbours(pieces: Sequence[Sequence[int]],
                    ptags: Sequence[Set[str]],
                    tokens: Sequence[WorkToken]) -> _Beside:
    """The nearest piece that is not a connective, on each side of
    every index.

    EVERY MEMBER OF ONE RUN HAS THE SAME ANSWER, which is the whole
    of the fix: `_between_name_words` used to walk the run itself, so a
    name holding a run of n connectives walked it n times and the
    stage went quadratic in the run's length -- measured 2026-09-20,
    `"Josep " + "i " * n + "Rovira"` grew 3.8x per doubling against
    the 2.0x every other shape holds, 59ms at n=800. Two linear
    passes answer the same question once for the whole segment.
    `tests/v2/test_benchmark.py`'s `link_run` shape is the guard.

    `is_conj_piece` is asked ONCE per piece, into a list the second
    pass then reads: asking it in both passes would double the calls,
    and it is the only per-piece call this builder makes. Recorded in
    the FIRST pass rather than by a comprehension of its own -- which
    is a code object on 3.11 and a bytecode saving here rather than a
    frame one, measured: the profile hook emits no call event for it.

    WHAT IT COSTS A SHORT NAME, because answering for the whole
    segment is not free where the walk would have stopped at once:
    this call, plus `is_conj_piece` for the pieces the walk never
    reached. Re-measured 2026-09-21 on py3.11 against b9ed1429, the
    whole pair through `tests/v2/test_benchmark.py`'s own
    `_frames_for` shape -- `Josep Carod i Rovira` 311 -> 313 frames
    (one call and two more `is_conj_piece` over its four pieces,
    less the frame the fold below saved) and `Jane Doe nee Puig i
    Soler` 315 -> 319. An O(1) rise per link-bearing name against an
    unbounded saving: the same name with a run of 64 links goes
    6,741 -> 2,587. (The pair first written here read 304 -> 307 and
    307 -> 312, with 6,741 -> 2,652 for the run of 64. Re-measured
    2026-09-22 on py3.11, WHICH OF THOSE REPRODUCE is: the two
    short-name pairs, neither of them; the run-of-64 pair, its left
    half only -- b9ed1429 reads 6,741 exactly, while 6048eb5d, the
    tree the 2,652 was taken on, reads 2,651 here. So the interpreter
    splice ran through a single arrow, which is what the table
    `tools/perf/call_count.py`'s own docstring warns about. Every
    figure above is one interpreter, stated.)
    `tools/perf/call_count.py` is unmoved (parse=406.00,
    facade=443.00) -- its reference name carries no link -- and so are
    `John Smith`, `Smith, John`, `Juan Garcia y Lopez` and `Jane Doe
    nee Smith`, none of which reaches this at all.

    Called only where a generational connective was found in the
    segment (the `frozen` loop), so no ordinary name pays for it at
    all.

    Dropping either pass's `not` fails
    test_a_connective_piece_counts_toward_the_carve_outs_total
    (mutation-checked 2026-09-20; how the two arrays are READ is
    checked in `_between_name_words`, which reads them).
    """
    n = len(pieces)
    left = [-1] * n
    right = [n] * n
    conj = [False] * n
    prev = -1
    for k in range(n):
        left[k] = prev
        is_conj = is_conj_piece(pieces[k], ptags[k], tokens)
        conj[k] = is_conj
        if not is_conj:
            prev = k
    nxt = n
    for k in range(n - 1, -1, -1):
        right[k] = nxt
        if not conj[k]:
            nxt = k
    return left, right


def _is_rootname(piece: Sequence[int], ptags: Set[str],
                 tokens: Sequence[WorkToken]) -> bool:
    if len(piece) == 1 and "initial" in tokens[piece[0]].tags:
        return False
    # rules/P3: "A connective counts as a name word wherever this
    # rule counts them, whatever else the vocabulary says the word is"
    # (#397). The order against the `initial` refusal above decides
    # nothing, and what makes that safe lives in classify rather than
    # here: for a single letter it writes `initial` or `conjunction`
    # and never both, so a one-case `I`/`i` arrives with no conjunction
    # tag whichever test runs first -- measured, hoisting this arm
    # above the refusal moves no field, report or initial on any
    # corpus name under three name orders, and no test. INLINE rather
    # than a call to is_conj_piece: this runs once per piece of every
    # name (frame budget).
    if ("conjunction" in ptags
            or (len(piece) == 1 and "conjunction" in tokens[piece[0]].tags)):
        return True
    return not (is_title_piece(piece, ptags, tokens)
                or is_prefix_piece(piece, ptags, tokens)
                or is_suffix_piece(piece, ptags, tokens))


# rules/P3: "a word the rest of the parse reads as a name word
# rather than as a generation, a credential or an honorific, looked
# for past any run of connectives standing between. A connective with
# nothing to its right is connecting nothing, and a word of that
# vocabulary ending a name, or standing before the credential a name
# ends with, is the generation it also spells" (#397) -- the WHOLE
# clause, its second sentence included, because that sentence is what
# this predicate answering `False` means. Reading it as a generation
# is the CALLER's half: `_group_segment`'s `frozen` set is where a
# connective this refuses is placed as the generation.
# `Sequence[Sequence[int]]` rather than `Sequence[Piece]`: this reads a
# piece and never edits one (widened when the maiden walk was a
# second caller, before #601).
def _between_name_words(k: int, lo: int, hi: int,
                        pieces: Sequence[Sequence[int]],
                        ptags: Sequence[Set[str]],
                        tokens: Sequence[WorkToken],
                        beside: _Beside) -> bool:
    """Whether such a word stands on EACH side of the connective piece
    at `k`.

    Both sides in one call because neither caller ever wants one: a
    connective is placed to join only where a name word stands on both
    sides of it, so the two answers were always ANDed at the call site
    and the left one short-circuits the right either way. One frame per
    generational connective rather than two, which is the whole of the
    saving -- the left arm below is the old left call and the right arm
    the old right one, unchanged (#397 follow-up).

    `lo` and `hi` bound the name's own words: assign peels the pieces
    below `lo` as its leading titles and those from `hi` up as its
    trailing suffix run, so a piece outside that span is a credential
    or an honorific however it is spelled, and the numeral or bare
    acronym the peel takes ('i V', 'i MA') is inside `hi` by
    construction rather than by a second reading of the vocabulary
    (mechanisms.md#ONE-PREDICATE-PER-QUESTION).

    Inside the span the suffix and title tests still run, because
    neither bound reaches a credential or an honorific standing in
    the MIDDLE of a name ('Josep Jr. i Rovira', 'Josep Dr. i
    Rovira'): the peel walks from the end and stops at the first name
    word, the title run from the front.

    The answer steps over connectives because a RUN of them joins as
    one ('Carod i y Rovira'), so the word this rule is about is the
    first one past the run -- and where the run runs out ('Juan i e')
    there is no name word on that side at all. `beside` is where that
    stepping already happened:
    `_run_neighbours` walked every run once for the whole segment, so
    this reads an index rather than walking to it. A SENTINEL OUT OF
    RANGE is how "the run ran out" arrives --
    -1 on the left, `len(pieces)` on the right -- and each bound test
    below turns it into False, exactly as the walk did when it ran
    here and stopped at the same place. `lo` is never negative and
    `hi` never past `len(pieces)`, so neither sentinel can pass the
    bound, and the piece tests are never asked about an index that is
    not one.

    Mutation-checked 2026-09-21, every arm of both sides by a NAMED
    test. Reading the LEFT array for the right arm too fails
    test_a_connective_with_nothing_to_its_right_does_not_join;
    the RIGHT array for the left arm too fails
    test_a_leading_title_on_the_left_is_no_name_word.
    The bounds, WIDENED to the whole segment rather than dropped --
    dropping the right one indexes past the pieces on the sentinel and
    raises instead of failing a test -- fail
    test_the_marker_is_not_the_name_word_on_the_links_left (left) and
    test_the_right_hand_test_reads_the_peel_not_the_suffix_piece
    (right). Either piece test on the LEFT fails
    test_a_credential_or_honorific_mid_name_is_no_name_word_either;
    either on the RIGHT fails
    test_a_credential_or_honorific_mid_name_on_the_right_too, which is
    the row the fold asked for: while this was two per-side calls a
    mutation hit both sides at once and the left-hand rows covered for
    the right-hand ones, whose own rows stand at the END of the name
    where `hi` refuses them first. SWAPPING the two arrays outright is
    an EQUIVALENT mutant and no test fails: the two arms are ANDed, so
    which array answers which side is not a question the conjunction
    can see.
    """
    left = beside[0][k]
    if not (lo <= left < hi
            and not is_suffix_piece(pieces[left], ptags[left], tokens)
            and not is_title_piece(pieces[left], ptags[left], tokens)):
        return False
    right = beside[1][k]
    return (lo <= right < hi
            and not is_suffix_piece(pieces[right], ptags[right], tokens)
            and not is_title_piece(pieces[right], ptags[right], tokens))


# rules/S12: "where the count declines it, the pair is the two words
# it is written as" -- after the trailing read, which is where the
# count is asked in a main segment
def _settle_splits(pieces: list[Piece], ptags: list[set[str]]) -> None:
    """Split every merged split credential left in `pieces` back into
    its two words, in place: a pair the trailing read declined reads
    as it reads unmerged. One a connective join took into a wider piece
    keeps the join and loses the tag (the only shape that reaches it
    is a pair beside a connective, 'Pharm D and')."""
    k = 0
    while k < len(pieces):
        if "split" in ptags[k]:
            if len(pieces[k]) == 2 and ptags[k] == {"split"}:
                a, b = pieces[k]
                pieces[k:k + 1] = [[a], [b]]
                ptags[k:k + 1] = [set(), set()]
                k += 2
                continue
            ptags[k] = ptags[k] - {"split"}
        k += 1


def _group_segment(seg: tuple[int, ...], additional: int,
                   tokens: Sequence[WorkToken],
                   bound_join: BoundJoin = BoundJoin.STRICT,
                   ambiguities: list[PendingAmbiguity] | None = None,
                   given_name_titles: Set[str] = frozenset(),
                   opens_the_name: bool = False,
                   *,
                   one_case: bool | None,
                   site: ClauseSite,
                   reads: list[TailRead | None] | None = None,
                   ) -> tuple[list[Piece], list[set[str]], MaidenTake | None]:
    pieces: list[Piece] = [[i] for i in seg]
    ptags: list[set[str]] = [set() for _ in seg]
    # Out-parameter, same shape as _assign_main: forks are reported
    # where they are decided. A caller that passes None (or a throwaway
    # list) suppresses reporting -- see group() for when that applies.
    if ambiguities is None:
        ambiguities = []
    # The maiden take reports on this same channel: it reports only at
    # the TRAILING site, which group() never suppresses.

    # ph-d merge first: "Ph." "D." adjacent -> one suffix piece
    # (decisions/phd-merge; v1 fix_phd did this by regex on the
    # raw string)
    # A suffix never BEGINS a name: position outranks the vocabulary
    # match (#371). This merge is what makes a leading "Ph." "D." a
    # credential at all -- every other suffix-shaped word standing
    # first already falls out as a title (H2's abbreviation clause, or
    # TITLES membership) or as a name word, so the pair is the only
    # shape that reaches the defect, and it reached it by emptying the
    # family: "Ph. D. Van Johnson" read given 'Van Johnson' with no
    # surname at all.
    #
    # WHERE THE INPUT BEGINS, and that is v1's own boundary rather
    # than a new one: fix_phd was a regex requiring a preceding space
    # (`\s(ph\.?\s+d\.?)`), so it could never fire at the head of the
    # string and fired everywhere else -- mid-name as readily as
    # trailing. Three tests, because "the head" has three meanings
    # here and only one of them is v1's:
    #   `k == 0`     the first PIECE, which is not the first word --
    #                extract_delimited removes a bracketed or quoted
    #                clause before segment runs, so `"Bob" Ph. D. John
    #                Smith` reaches this with the pair at k == 0 and a
    #                word standing before it in the input. v1 merges
    #                there; declining broke parity on 112 measured
    #                names, every one opening with a quote or bracket.
    #   `a[0] == 0`  the first TOKEN, which is v1's boundary.
    #   seg_idx 0    and not after a family comma: a credential run
    #                legitimately opens segment 1 ("Smith, Ph. D.
    #                Jr.", C8's credential run in the listing form), and segment 0 before a
    #                comma is the family the comma named, where v1
    #                merges too ("Ph. D., John" reads last 'Ph. D.').
    #
    # A leading TITLE is therefore NOT stepped over, unlike the #367
    # scan below, and the two disagree on purpose: that scan asks
    # where the NAME begins, this asks where the STRING does. `Sir
    # Ph. D. Van Johnson` keeps suffix 'Ph. D.' with an empty family,
    # which is #371's symptom surviving one word to the left -- 1.4.0
    # parity, stated as a boundary in rules/S2 rather than fixed
    # here, because "the first piece of the name" cannot be computed
    # before this merge: `is_leading_title` is true of `Ph.` itself,
    # so the scan would step over the very piece being judged.
    #
    # Every other split credential ('Pharm. D.', `_vocab.split_pair`'s
    # "split" answer) merges under the same head test as a member of
    # the ambiguous class, where a rule reads such a member: in a main
    # segment, where S2's read below decides it by the count, kept
    # whole where the read takes it and split back into its two words
    # where it does not (`_settle_splits`), so a declined pair reads
    # exactly as the two words read; and in the given part after a
    # family comma behind the given word, where S5's walk reads it,
    # merged ahead of the joins so the particle chain stops in front of
    # it and P5's bound join declines it as it declines a suffix word,
    # and a pair declined there is middle-name text whole or split.
    # (A connective beside a pair keeps it from merging at all, in
    # classify.)
    # Not in the part before a family comma, which reads no member as
    # a suffix ('Smith MA, John'). Classify tagged each pair's first
    # word, so the test here is a tag.
    splits = False
    given_from: int | None = None
    k = 0
    while k < len(pieces) - 1:
        a, b = pieces[k], pieces[k + 1]
        tags = tokens[a[0]].tags
        if (len(a) == 1 and len(b) == 1
                and not (opens_the_name and k == 0 and a[0] == 0)):
            if SPLIT_CREDENTIAL_TAG in tags:
                merge_pieces(pieces, ptags, k, k + 2, add={"suffix"})
                continue
            if SPLIT_MEMBER_TAG in tags:
                if site is ClauseSite.TRAILING:
                    merge_pieces(pieces, ptags, k, k + 2, add={"split"})
                    splits = True
                    continue
                if site is ClauseSite.GIVEN_SLOT:
                    if given_from is None:
                        given_from = leading_titles(pieces, ptags, tokens)
                    if k > given_from:
                        merge_pieces(pieces, ptags, k, k + 2, add={"split"})
                        continue
        k += 1

    # rules/M2: "A marker that counts takes the words after it as
    # the maiden name, and is itself dropped" (history:
    # decisions/M2) -- the marker pass (#274), and it runs
    # BEFORE every join below. Each join rule asks a question about the
    # name -- how many words it has (P3's carve-out, P5's reserve),
    # what the word after a particle or a bound word is -- and the
    # marker and the maiden name are not part of that name: they leave.
    # Asked while they were still pieces, the count answered for a name
    # that would not exist ('juan y garcia nee jones' counted five, 'y'
    # joined, and the family was empty once the clause left: #418), and
    # a join could absorb the marker before the pass looked for a lone
    # one ('Jane van der Berg née y Jones' kept the marker in the
    # family: #412). Removing the pieces first makes both impossible by
    # construction, with no stop on the chain (#399, #417) and no
    # exclusion in the reserve (#411) left to keep in step.
    #
    # The tokens are not touched here: this function reads them and
    # returns what it took, and group() records the drop and the roles.
    taken: MaidenTake | None = None
    take = _maiden_take(pieces, ptags, tokens, one_case,
                        site, ambiguities)
    if take is not None:
        marker_ks, removed = take
        taken = ([i for k in marker_ks for i in pieces[k]],
                 [(pieces[k], role) for k, role in removed])
        for k in reversed(marker_ks + [k for k, _ in removed]):
            del pieces[k]
            del ptags[k]

    # S2's trailing run, read once below once the connectives have
    # joined (#614)
    read: TailRead | None = None
    tail_pieces: list[Piece] = []
    tail_ptags: list[set[str]] = []
    # too few pieces for the read: a split credential has no words to
    # spare (rules/S4)
    if splits and len(pieces) + additional < 3:
        _settle_splits(pieces, ptags)
    if len(pieces) + additional >= 3:
        # rules/P3: "A connective that is also generational
        # vocabulary joins only where a name word stands on each side
        # of it" (#397). `frozen` holds the TOKEN index of every such
        # connective missing a name word on one side: it is the
        # generation it also spells, so no join of its own reaches it,
        # it may not merge into a run, and it does not count toward
        # the carve-out total. A token index because the joins below
        # move piece indices. A neighbour's join can still absorb it:
        # `join_connectives`' neighbour-join loop skips a frozen piece
        # only as the join's subject.
        #
        # Asked here, of the pieces as classify left them and of the
        # neighbours' class, because after a merge the absorbed suffix
        # IS the word on the right. No length test: the clause names a
        # class, not a spelling, while the three-word carve-out below
        # stays single-letter because its own sentence says so. Only a
        # connective of the suffix vocabulary reaches the body, so a
        # name with none pays no call for this test. decisions/P3.
        frozen: set[int] = set()
        # whether any connective is left free to join: a segment with
        # none skips the rootname count and the shared loop, both of
        # which then do nothing (0 of 3,153 such calls changed a piece
        # over the corpora and case table, #617's /simplify), as
        # `_comma._reading_pieces` skips it for the part after a comma
        free = False
        lo = hi = -1
        beside: _Beside = ([], [])
        for k, piece in enumerate(pieces):
            tok = tokens[piece[0]]
            if len(piece) != 1 or "conjunction" not in tok.tags:
                continue
            if "vocab:suffix" not in tok.tags:
                free = True
                continue
            # The bounds and the run memo, computed once per segment
            # and only where such a connective was found, so the cost
            # is the link's own and no ordinary name pays any of it.
            if hi < 0:
                lo = leading_titles(pieces, ptags, tokens)
                # H5's reading and not the peel over the pieces as
                # WRITTEN: a title standing behind the suffix run
                # hides it from `trailing_start`, which then answers
                # `len(pieces)` and hands this loop a credential as
                # the name word on the link's right. 'John Quincy
                # Adams i MA Prof.' joined to family 'Adams i MA' with
                # no report at all, where 'John Quincy Adams i MA' --
                # the same name, one title shorter -- reads family
                # 'Adams', suffix 'i MA' and reports the acronym
                # (#397 second review).
                hi = trailing_start_past_titles(lo, pieces, ptags,
                                                tokens,
                                                one_case=one_case)
                # ONE ANSWER PER RUN: every member of a contiguous run
                # of connectives has the same nearest name word on
                # each side, and asking per member walked the run once
                # per member -- quadratic in its length, 3.8x per
                # doubling measured at `b9ed1429`.
                beside = _run_neighbours(pieces, ptags, tokens)
            if _between_name_words(k, lo, hi, pieces, ptags, tokens,
                                   beside):
                free = True
            else:
                frozen.add(piece[0])
        if free:
            total = sum(_is_rootname(p, t, tokens)
                        for p, t in zip(pieces, ptags)
                        if p[0] not in frozen) + additional
            # The threshold of P3's carve-out ("except a single-letter
            # connective in a three-word name, which stays a name word")
            # reads the ROOTNAME count, and since #397 a connective counts
            # ITSELF toward that count WHERE IT IS JOINING, so a connective
            # that is also suffix vocabulary no longer raises the bar for
            # its own join and no longer lowers it for an unrelated one
            # ("Carod y Rovira i" counted the trailing generation and let
            # the `y` join).
            join_connectives(pieces, ptags, tokens, letter_stays=total < 4,
                             titles_only=False, frozen=frozen)
        # rules/S2's trailing run is read ONCE, here -- after P3's
        # connective joins, which do not depend on it and make the
        # units it counts, and before the particle chain and the
        # bound-given join, which do -- and bound (#614): the run is
        # split off, the chain and the join group the name in front of
        # it, and assign places the run off this reading. Group had
        # asked the peel before and after those joins -- the chain's
        # stop and its re-ask after its own merges, the reserve's two
        # views -- because they change the pieces the count reads; the
        # read counts the units the chain will build instead
        # (_pieces.read_trailing_run), so there is nothing to re-ask,
        # and no join takes a word the run took ('John van der Berg
        # Prof.' keeps its title). The main segments only (no comma,
        # or the part before a suffix comma); a family comma's parts, a
        # part past a comma and a segment of fewer than three pieces --
        # which no join reaches anyway -- read as before, and so does a
        # run holding a name piece (_pieces.read_trailing_run).
        # The particles straight behind each other are merged first,
        # into the one piece the chain would open its run with, so the
        # read counts and absorbs the run as that piece (#625);
        # `premerged` keeps which runs the merge made, for the chain's
        # report below.
        premerged: Set[int] = frozenset()
        if site is ClauseSite.TRAILING:
            n = leading_titles(pieces, ptags, tokens)
            premerged, lead = merge_particle_runs(pieces, ptags, tokens, n)
            found = read_trailing_run(pieces, ptags, tokens, one_case, n,
                                      lead)
            if found is not None:
                read, start = found
                tail_pieces, tail_ptags = pieces[start:], ptags[start:]
                del pieces[start:]
                del ptags[start:]
            # the read has decided every split credential: one it took
            # left with the run, and one still here is two name words
            if splits:
                _settle_splits(pieces, ptags)
        # rules/S2: "a trailing word of the suffix vocabulary reads as a
        # suffix" -- on a main segment the run read above decides it
        # and is split off already; elsewhere the chain stops where
        # assign's peel begins (`trailing_run_start`, trailing titles
        # included, in the given part after a family comma; else
        # `trailing_start`; the H5 paragraph below explains the
        # titles). decisions/P2 (#424).
        # rules/P2: "a particle joins the words after it into one name
        # part, the join running until the next particle starts a group of
        # its own, a trailing suffix begins" -- and on to the maiden marker
        # (M2) or the name's end; the final group reads as the family name,
        # earlier groups by position. (history: decisions/P2)
        # rules/P4: "a particle in the name's leading position chains
        # nothing: the words stay separate" (history: decisions/P2)
        #
        # "Leading" is the first piece of the NAME, past assign's own
        # title run (`leading_titles`), unless a word in that run is
        # also a particle: then the last such word leads in the run's
        # place (`chain_lead`, decisions/P2 (#624)). Computed once,
        # before the loop: every merge below starts past this index, so
        # none can move it. Suffix pieces are deliberately not skipped
        # when finding the leading piece (decisions/P2). A maiden
        # marker still here is one the consumer declined, an ordinary
        # word to the chain. decisions/M2 (#417).
        name_start = leading_titles(pieces, ptags, tokens)
        leading = chain_lead(pieces, ptags, tokens, name_start)
        # rules/P2: "a trailing suffix begins" -- where it begins
        # is read by assign's peel over the pieces as they stand
        # (#424), once per segment and kept as a length from the end,
        # which the chain's merges ahead of it do not move -- except
        # where a particle that is suffix vocabulary too (vd, mc, do)
        # starts the run: the prefix run below takes it as a particle,
        # as P6 reads it after a comma, and 'John van Mc' keeps family
        # 'van Mc' (every baseline's reading). A suffix WORD stops the
        # chain wherever it stands, and the trailing
        # run -- the numeral, or the bare acronym with words to spare
        # -- stops it where the suffix-piece test alone did not ('John
        # van der Berg V' read family 'van der Berg V'). The chain
        # takes both forks, and where no run was read ahead of it it
        # asks again after its merges whether the acronym still has
        # the pieces the fork counted (below).
        # the run read above is already split off (#614), so the chain
        # stops at the end of what is left.
        # rules/H5: "the title is TRANSPARENT to the suffix reading"
        # -- in the given part after a family comma too, where assign's
        # walk reads the trailing title run, so the chain stops before
        # the run of suffixes and titles `tail_reading` takes there
        # rather than before the suffixes alone, and does not carry a
        # trailing title into the particle's name ('Smith, John van der
        # Berg Prof.' reads title 'Prof.' as 'Smith, John Prof.' does,
        # #623). The bound matters only where a particle stands past the
        # chain's lead, so it is not asked otherwise: the chain then
        # merges nothing (the test is `is_prefix_piece`'s, inline).
        # rules/C2: "a part past the second comma holds no name word"
        # -- assign reads such a part wholly as suffixes and its title
        # words as titles, so the chain builds no name unit there and is
        # not run, and a title word behind a particle run stays a word
        # C2 can read ('John Smith, Jr., van der Berg Prof.', #636). The
        # part after a suffix comma reaches no chain either: `_comma.
        # decide` binds it and empties its segment before any join
        # (#613).
        chains = False
        if read is None and site is not ClauseSite.TAIL:
            for k in range(leading + 1, len(pieces)):
                if ("prefix" in ptags[k]
                        or len(pieces[k]) == 1
                        and "particle" in tokens[pieces[k][0]].tags):
                    chains = True
                    break
        given_slot = site is ClauseSite.GIVEN_SLOT
        tail = (0 if not chains
                else len(pieces) - (
                    trailing_run_start(name_start, pieces, ptags, tokens,
                                       one_case) if given_slot
                    else trailing_start(name_start, pieces, ptags, tokens,
                                        one_case=one_case)))
        # the members the chain reports below, which the read's picks
        # then give up (#614)
        took: set[tuple[int, ...]] = set()

        def chain(tail: int) -> None:
            # `pieces[:titled]` are known to be leading titles. A merge
            # from k to j changes only indices from k on, and k only
            # grows, so a piece behind k is final and its answer can
            # be kept: the
            # cursor makes the all-titles-ahead test below one walk per
            # chain rather than one per chain site (#559).
            titled = 0
            k = 0
            while k < len(pieces):
                if k <= leading or not is_prefix_piece(pieces[k],
                                                       ptags[k], tokens):
                    k += 1
                    continue
                j = chain_run_end(k, pieces, ptags, tokens,
                                  len(pieces) - tail,
                                  one_case if given_slot else None)
                # The other half of PARTICLE_OR_GIVEN. _assign reports the
                # fork when an ambiguous particle stays a lone leading piece
                # ("Van Johnson" -> given under the default order, family
                # under FAMILY_FIRST); the chain here takes the opposite
                # branch when the particle is not the name's leading piece.
                # A fork whose two sides are decided in different stages
                # needs an emitter in each.
                #
                # Narrow, and #367 is why. `titled == k` says every
                # piece ahead of this one is a title, and the loop
                # skipped every piece up to `leading`, so `leading` is
                # STRICTLY before k -- one of those titles, and, being
                # before the title run's end, a prefix as well
                # (`chain_lead`): a word in both vocabularies (`st`,
                # `freiherr` by default, or any overlap a caller
                # configures). A plain title alone can no longer put a
                # particle off the name's leading piece; it is stepped
                # over and _assign reports the fork instead.
                #
                # What that leaves is wider than one shape: any number of
                # plain title pieces, then a piece in BOTH vocabularies,
                # then any number of further titles, then the ambiguous
                # particle whose chain claims something. "Freiherr von
                # Richthofen" is the canonical spelling and the one
                # tests/v2/cases.py and tests/v2/test_parser.py lead with,
                # but "St Van Johnson", "Do St Johnson" (the chained
                # particle itself in both vocabularies) and "Dr. Do van
                # Johnson" (a plain title AHEAD of the both-vocabulary
                # word) all reach here too. What none of them can do is
                # dispense with the both-vocabulary WORD. The conjunction
                # merge is the only other way a piece acquires `title` or
                # `prefix`, and it cannot manufacture the pair: it derives
                # from ONE neighbor, which is the left one whenever there
                # is a left one, and its right operands are always fresh
                # pieces (the loop runs left to right, so nothing to the
                # right has been merged yet). Both tags therefore have to
                # come from the piece it extends, which bottoms out at a
                # lone token in both vocabularies.
                #
                # j > k + 1 is what makes this a DECISION rather than a
                # shape: when the next piece is a suffix the inner scan
                # never advances, the merge from k to k+1 folds a piece
                # into itself, and the particle stays a lone leading
                # piece -- nothing
                # was chained, and _assign reports that case instead.
                # Without this the two emitters both fire on the same token.
                # A run merged ahead of the read (`premerged`, #625) has
                # claimed the particles behind it already, so its chain
                # is a decision though `j == k + 1` ('Freiherr von der').
                # (Tag test first: it is a set lookup and almost no name
                # has an ambiguous particle, while is_leading_title is a
                # call per piece.)
                if ((j > k + 1 or pieces[k][0] in premerged)
                        and "vocab:particle-ambiguous"
                        in tokens[pieces[k][0]].tags):
                    while titled < k and is_leading_title(
                            pieces[titled], ptags[titled], tokens):
                        titled += 1
                    if titled == k:
                        i = pieces[k][0]
                        ambiguities.append(PendingAmbiguity(
                            AmbiguityKind.PARTICLE_OR_GIVEN,
                            f"{tokens[i].text!r} was chained onto the "
                            f"following name piece; it is also a given "
                            f"name in other names",
                            (i,),
                            # where it would stand unchained is
                            # assign's to name
                            alternative=name_reading(tokens[i],
                                                     Deferred.UNCHAINED)))
                # rules/S4: "A BARE ambiguous acronym is consumed
                # only when the name has words to spare — as the second
                # of two words it stays the family name — and at the
                # slots that report, either reading carries the
                # ambiguity flag"
                #
                # The chain's half of SUFFIX_OR_NAME: once the chain
                # takes the acronym, the lone piece assign reports on
                # is gone, so the fork reports here
                # (mechanisms.md#AMBIGUITY-AT-THE-DECISION-SITE). It is
                # the DECLINED reading: the scan stops at
                # `len(pieces) - tail`, before every piece the peel
                # took, and a re-peel truncates the first pass's
                # appends with the pieces. `j > k + 1` is its floor
                # too, and `not is_prefix_piece(last, ...)` leaves a
                # word in both vocabularies ending a PARTICLE run to
                # P6's fork; it costs a frame, so it is tested last. A
                # member S2's read picked is reported here and leaves
                # the read's picks. decisions/S6 (#289), decisions/S2
                # (#614).
                last = pieces[j - 1]
                # A numeral S2's read declined (rules/S10, #718) is not
                # reported here: it stays one of the read's picks, and
                # assign words it from the role it ends in ('Freiherr
                # von Richthofen V', 'a family name'), the chain taking
                # nothing the read had not already given up
                if (j > k + 1 and len(last) == 1
                        and not tokens[last[0]].tags.isdisjoint(
                            _AMBIGUOUS_CREDENTIAL_TAGS)
                        and not is_prefix_piece(last, ptags[j - 1],
                                                tokens)):
                    ambiguities.append(PendingAmbiguity(
                        AmbiguityKind.SUFFIX_OR_NAME,
                        f"{tokens[last[0]].text!r} is both a post-nominal "
                        f"and an ordinary name; the particle chain took "
                        f"it into the name rather than reading it as a "
                        f"post-nominal",
                        tuple(last),
                        alternative=suffix_reading(tokens[last[0]])))
                    took.add(tuple(last))
                merge_pieces(pieces, ptags, k, j, drop={"prefix"})
                k += 1

        # Where the run was read above (#614) it is split off and
        # `tail` is 0, so none of what follows runs, as it does not
        # where no particle stands past the lead (#623); it is the path
        # for the segments that read no run above -- a family comma's
        # two name parts and a run with a name piece inside it (a part past the
        # second comma makes no chain, #636) -- and the given part
        # reaches it still
        # ('Smith, Freiherr van Berg X.Y.Z.', the row that holds it).
        #
        # The peel was read over the pieces as they stand, and the
        # chain's own merges can change what it counts: behind a word
        # in both the title and particle vocabularies the scan above
        # stops where assign's title peel does not (P4, #367), so the
        # chain takes the name's first word, and the acronym the fork
        # counted with three pieces meets assign with two -- 'Freiherr
        # von Berg Ma' read given 'von Berg', family 'Ma' (1.4.0's
        # reading; the reviews found it behind the claim that the
        # merges leave the count alone). So the peel is asked again
        # over the pieces the chain leaves, and where it no longer
        # takes what the chain stopped before, the chain runs again
        # without that stop: what assign will not peel is a name word,
        # and the chain takes it. The numeral cannot flip (a chain
        # group is never initial-shaped), so the second run is the
        # acronym's alone, and rare; the snapshot is one copy per
        # segment with a trailing run, linear like the rest.
        if tail:
            kept = ([list(q) for q in pieces], [set(t) for t in ptags],
                    len(ambiguities))
            chain(tail)
            start = leading_titles(pieces, ptags, tokens)
            left = len(pieces) - (
                trailing_run_start(start, pieces, ptags, tokens, one_case)
                if given_slot
                else trailing_start(start, pieces, ptags, tokens,
                                    one_case=one_case))
            if left < tail:
                pieces[:], ptags[:] = kept[0], kept[1]
                del ambiguities[kept[2]:]
                chain(left)
        elif site is not ClauseSite.TAIL:
            chain(0)
            if read is not None and took:
                # built, not `_replace`d: two frames a call
                peel = read.peel
                read = TailRead(read.tail, read.titles, read.run_titles, Peel(
                    peel.names, peel.numerals,
                    tuple([p for p in peel.picks if p not in took]),
                    peel.anchors, peel.run_titles, peel.absorbed))
        # rules/P5: "a recognized bound given-name word joins the
        # word after it into one given name" (history: decisions/P5)
        # -- bound given names: the first non-title piece joins the next
        # ONCE (pairwise, v1 parity: 'Salem, Abdul Rahman Ahmed' keeps
        # Ahmed a middle name). BoundJoin encodes v1's reserve_last.
        # "the first non-title piece" by assign's count (#424): group's
        # title test does not see H2's unlisted abbreviations, and
        # 'Xyz. abdul John Smith' joined nothing where 'Dr. abdul John
        # Smith' read given 'abdul John'.
        fk = leading_titles(pieces, ptags, tokens)
        if (bound_join is not BoundJoin.DISABLED
                and fk + 1 < len(pieces)
                and len(pieces[fk]) == 1
                and "vocab:bound-given" in tokens[pieces[fk][0]].tags):
            # P5 joins the bound word to "the word after it", and a
            # marker is not a name word -- it is the announcement that
            # another name follows. The only marker left by now is one
            # the consumer declined (nothing after it, or nothing but
            # a suffix), and the join must still not take it: 'Berg,
            # abdul nee PhD' read given 'abdul nee', and 'Berg, abdul
            # nee' clears the LENIENT reserve the same way. Measured
            # rather than assumed -- dropping this undid #411 on
            # exactly that row. Nor is a suffix piece (#421) --
            # rules/P5: "nor a word of the unambiguous suffix
            # vocabulary (S2), wherever position will then place it"
            # -- and declining it is also what keeps merge_pieces' tag
            # union from making the joined piece a suffix piece.
            # rules/P5: "nor a title word a trailing rule reads as a
            # title" -- after a family comma one H5's trailing run takes
            # from the given part, read as the comma-less name reads it,
            # plus the bare salutations H8 adds after a family comma
            # (`salutations=True`),
            # which the LENIENT join reads no peel for and so asks here,
            # only where a title word follows ('Berg, abdul Prof.',
            # #637; where the given part's own walk then reads the words
            # behind it otherwise, the title stays a name word, which
            # rules/P5 accepts); in a part past the second
            # comma any title word, which C2 reads as a title ('John
            # Smith, Jr., abdul Dr. Smith', #640). A title word standing
            # in the name is a name word and joins ('abdul Sir Smith
            # Berg', 'Berg, abdul Prof. Ali').
            # A credential split across a space (rules/S12) is declined
            # as its one-word spelling is: merged in the given part
            # before this join, so the particle chain stops in front of
            # it too ('Rahman, Abdul MB ChB', 'Smith, John van Pharm D')
            # After a family comma a member its capitals settle as the
            # credential (rules/S6) is declined as a suffix word is: the
            # join would read it as the given name's second word, where
            # the given part's trailing slot or the run S8 starts takes
            # it ('Smith, Abdul MA'); with no comma nothing would, and
            # the join stands ('Abdul MA Smith')
            nxt, nxt_tags = pieces[fk + 1], ptags[fk + 1]
            if (_is_maiden_marker_piece(nxt, tokens)
                    or is_suffix_piece(nxt, nxt_tags, tokens)
                    or "split" in nxt_tags
                    or (bound_join is BoundJoin.LENIENT and len(nxt) == 1
                        and AMBIGUOUS_ACRONYM_TAG in tokens[nxt[0]].tags
                        and settled_by_case(tokens[nxt[0]], one_case))
                    or ((site is ClauseSite.TAIL
                         or bound_join is BoundJoin.LENIENT)
                        and is_title_piece(nxt, nxt_tags, tokens)
                        and (site is ClauseSite.TAIL
                             or fk + 1 in tail_reading(
                                 peel_walk(fk, ptags), pieces, ptags,
                                 tokens, one_case,
                                 salutations=True)[1]))):
                pass
            elif bound_join is BoundJoin.LENIENT:
                # post-comma the family is fixed and the pair is the
                # given whatever follows, so no peel is read
                # (decisions/P5, #423), save the title test above
                merge_pieces(pieces, ptags, fk, fk + 2, drop={"title"})
            else:
                # rules/P5: "the trailing suffix run (S2) and the
                # trailing title run (H5), each read over what the other
                # leaves until neither takes anything more, are read
                # once, before the join is tried, and the name words they
                # leave are the words to spare" (history: decisions/P5).
                # That reading is the one above, after P3's joins and
                # before the chain (#614): the run is
                # split off, every piece left is a name piece, and the
                # join leaves one fewer. Nor can the join move a suffix
                # -- rules/P5: "a word the run left as a name word
                # stays one, whatever the join makes of the word in
                # front of it" -- since nothing in group reads the run
                # again after it.
                #
                # Where the run was not read above (a run with a name
                # piece inside it, _pieces.read_trailing_run), the
                # reserve still reads both views, as it did everywhere
                # before #614: the join tried on the pieces as it would
                # leave them, the reading assign runs over each (the
                # ONE function, _pieces.tail_reading), the suffixes
                # compared as the peeled pieces themselves -- 'abdul
                # Smith V' peels the V unjoined and nothing joined (no
                # word to spare there, rules/S10), 'abdul Smith Ma'
                # peels the acronym unjoined and keeps it joined.
                if read is not None:
                    same_suffixes = True
                    chained = False
                    names_after = len(peel_walk(fk, ptags)) - 1
                else:
                    rest, chain_took, before = tail_reading(
                        peel_walk(fk, ptags), pieces, ptags, tokens,
                        one_case)
                    view, view_tags = list(pieces), list(ptags)
                    view[fk:fk + 2] = [pieces[fk] + pieces[fk + 1]]
                    view_tags[fk:fk + 2] = [joined_tags(ptags, fk, fk + 2,
                                                        drop={"title"})]
                    view_rest, _, after = tail_reading(
                        peel_walk(fk, view_tags), view, view_tags, tokens,
                        one_case)
                    same_suffixes = (
                        [tuple(view[j]) for j in view_rest[after.names:]]
                        == [tuple(pieces[j]) for j in rest[before.names:]])
                    chained = fk + 1 in chain_took
                    names_after = after.names
                # rules/P5: "a trailing roman numeral the run takes
                # (S10), or a bare acronym it takes, or a trailing title
                # word the run takes, is no word to spare" -- and the join joins
                # two NAME words, so a piece the chain takes is no more
                # joinable than a marker or a suffix piece is: 'Sir
                # abdul Prof.' reads title 'Sir Prof.', given 'abdul'.
                # Read off the UNJOINED view, the one that still has
                # the title as a piece of its own -- the join would
                # swallow it, and a swallowed title is a title the
                # joined view can no longer see. The suffix comparison
                # alone said this while the counts were subtractions,
                # by leaving the chained piece in the tail it compared;
                # under the shared reading the chain takes it out of
                # both views, so the rule is asked as the rule.
                # A given-name title ahead of the bound word asserts
                # that a given name follows -- the assertion H1 reads
                # when it keeps "Sir John" a given name -- so behind
                # one there is no family to spare (#369). Asked of the
                # title run through the ONE predicate post_rules asks
                # for H1, so the two rules cannot disagree about what
                # one run asserts; what it reads is the whole run's key
                # or that key's LAST word (#489). And it is the same
                # RUN on both sides: `range(fk)` is the pieces AHEAD of
                # the bound word, and H1 asks its own question of the
                # leading run too (_post_rules._addressing_run). They
                # did disagree for one commit -- H1 keyed every TITLE
                # token, so the trailing title in 'Sir abdul rahman
                # Prof.' joined this run and flipped the join's own
                # premise, handing the licensed pair to the family.
                # Reading the leading run at both sites is what makes
                # that unreachable rather than merely unlikely: a
                # trailing title is behind the word, and neither site
                # can see it. What H2's unlisted abbreviations do
                # inside such a run is the predicate's own business,
                # and its docstring is where they are worked through.
                # The licence lifts the reserve for two name
                # WORDS: the piece the join would take must be one word
                # -- a particle chain is the family name P2 built ('Sir
                # abdul van der Berg' keeps family 'van der Berg').
                licensed = (fk > 0 and len(pieces[fk + 1]) == 1
                            and _run_addresses_by_given(
                                (tokens[i].text
                                 for k in range(fk)
                                 for i in pieces[k]),
                                given_name_titles))
                reserve = BoundJoin.LENIENT if licensed else BoundJoin.STRICT
                if (not chained and same_suffixes
                        and names_after >= reserve):
                    # the pair is a given name whatever tag the word
                    # carried (rules/P5); joined_tags says why the
                    # title tag is dropped. Pinned in test_group.py.
                    merge_pieces(pieces, ptags, fk, fk + 2, drop={"title"})
    if reads is not None:
        reads.append(read)
    pieces.extend(tail_pieces)
    ptags.extend(tail_ptags)
    return pieces, ptags, taken


def group(state: ParseState) -> ParseState:
    # rules/C1's decision, read once now that classify has tagged
    # the words and before any join below can reach the part after the
    # comma (#613); a postnominal part comes back bound, its segment
    # emptied (a name with no comma asks nothing)
    if state.structure is Structure.FAMILY_COMMA:
        state = _comma.decide(state)
    tokens = list(state.tokens)
    dropped = list(state.dropped)
    ambiguities = list(state.ambiguities)
    all_pieces: list[tuple[tuple[int, ...], ...]] = []
    all_ptags: list[tuple[frozenset[str], ...]] = []
    all_reads: list[TailRead | None] = []
    # v1 parity: additional_parts_count=1 applies only to FAMILY_COMMA
    # parts; the SUFFIX_COMMA pre-comma segment gets 0.
    additional = 1 if state.structure is Structure.FAMILY_COMMA else 0
    # v1 expand_suffix_delimiter parity (#206): tail segments (wholly
    # consumed as suffixes by assign) are cut at their delimiter-core
    # tokens, which land in `dropped` as the maiden marker does; the
    # built-in cores, which no v1 release read, cut them too (#889)
    cores = delimiter_cores(state.policy.extra_suffix_delimiters)
    tail_start = {Structure.SUFFIX_COMMA: 1,
                  Structure.FAMILY_COMMA: 2}.get(state.structure)
    family_comma = state.structure is Structure.FAMILY_COMMA
    for seg_idx, seg in enumerate(state.segments):
        if family_comma:
            bound_join = (BoundJoin.LENIENT if seg_idx == 1
                          else BoundJoin.DISABLED)
        else:
            bound_join = BoundJoin.STRICT
        # Suppressed after a family comma for the same reason _assign
        # suppresses it there: the family name is already fixed, so
        # there is no fork left to report. A tail segment needs no
        # suppression: group makes no particle chain there (#636) and
        # takes no maiden clause (rules/M2, #601), so nothing in group
        # reports in one. rules/C2: "a part the parse consumes wholly
        # as suffixes raises no report that a word of it was read as a
        # name"
        tail = tail_start is not None and seg_idx >= tail_start
        # #601: where a maiden clause would stand, off the three facts
        # already in hand here -- which decides whether a marker counts
        # at all and which rule reads the end of the part.
        if tail:
            site = ClauseSite.TAIL
        elif family_comma:
            site = (ClauseSite.GIVEN_SLOT if seg_idx == 1
                    else ClauseSite.FAMILY_PART)
        else:
            site = ClauseSite.TRAILING
        # rules/C10: "a suffix delimiter parts the suffix words on each
        # side of it as a comma would" (#549): the segment is
        # grouped as the parts between its cores, each read exactly as
        # the comma twin's own segment would be, and the cores are
        # dropped (v1 expand_suffix_delimiter parity, #206), where
        # post_rules' entry pass reads them back as entry boundaries.
        # No join or link search reaches across a core, because none
        # of them ever sees one, and a maiden marker in a tail part is
        # an ordinary word (#601). A one-token segment that
        # is its core keeps it (v1 expand() splits within a part, never
        # erases a lone part); a segment of several cores and nothing
        # else drops them all, as the #206 drop did.
        # Accumulated in a list and frozen once per part: a tuple
        # extended per token is quadratic in the part's length, C-level
        # work no frame guard sees (#553's class; review of #549).
        # Measured 2026-10-03, py3.11, 'Smith, John, ' + 'PhD ' * n +
        # '- MD' under a ' - ' delimiter: 4.7x for n 4,000 -> 16,000 as
        # written, the default policy's own 4.5x, where the tuple read
        # 8.0x. No clock guard: _PREFIXED_SHAPES parses with the default
        # policy and _POLICY_SHAPES repeats a unit with no prefix, and a
        # tail needs both, so a row would mean a table of its own.
        parts: list[tuple[int, ...]] = [seg]
        if tail and cores and len(seg) > 1:
            parts = []
            current: list[int] = []
            for i in seg:
                if tokens[i].text in cores:
                    dropped.append(i)
                    if current:
                        parts.append(tuple(current))
                    current = []
                else:
                    current.append(i)
            if current:
                parts.append(tuple(current))
        pieces = []
        ptags = []
        seg_reads: list[TailRead | None] = []
        for part in parts:
            part_pieces, part_ptags, taken = _group_segment(
                part, additional, tokens, bound_join,
                None if family_comma else ambiguities,
                state.lexicon.given_name_titles,
                opens_the_name=(seg_idx == 0 and not family_comma),
                one_case=state.one_case,
                site=site, reads=seg_reads)
            pieces.extend(part_pieces)
            ptags.extend(part_ptags)
            # the marker is dropped and the maiden name's tokens become
            # MAIDEN (#274); which pieces those are was settled in
            # _group_segment, before the joins
            if taken is not None:
                marker_piece, removed_pieces = taken
                dropped.extend(marker_piece)
                # the maiden name, and the trailing run the take
                # consumed with the roles the clause-free name's
                # reading gave it (#601)
                for piece, role in removed_pieces:
                    for i in piece:
                        tokens[i] = copy_with(tokens[i], role=role)
        # Group used to decide the suffix ENTRY, marking a continuation
        # token "joined" between pieces off segment SHAPE -- `tail` by
        # index, ORed since #429 with segment_suffix_reading's
        # per-piece content verdict, gated per piece and sticky across
        # an interleaved title. post_rules derives that from the
        # commas the writer typed instead (#436/#437, rules/R1),
        # which is what the input answers directly. The stickiness
        # survives by construction rather than by code:
        # 'Smith, MD Dr. PhD' has no comma between MD and PhD and a
        # title between them renders elsewhere, so they join, while
        # 'Smith Jr., Mr. Jr.' has the writer's own comma and they do
        # not.
        # continuation tokens of a suffix-merged piece (the ph-d merge)
        # carry the stable "joined" tag: the suffix string view joins
        # SUFFIX tokens with ", ", and the tag lets it heal the split
        for piece, piece_tags_ in zip(pieces, ptags):
            if "suffix" in piece_tags_ and len(piece) > 1:
                for i in piece[1:]:
                    tokens[i] = copy_with(
                        tokens[i], tags=tokens[i].tags | {"joined"})
        all_pieces.append(tuple(tuple(p) for p in pieces))
        all_ptags.append(tuple(frozenset(t) for t in ptags))
        all_reads.append(seg_reads[0] if len(seg_reads) == 1 else None)
    # rules/M1: "a leading recognized marker is dropped where the
    # clause holds a word past it" and "a clause of nothing but its
    # marker keeps its words" — Then's marker drop and the Then bullet
    # on a marker-only clause, for a marker inside EXTRACTED maiden
    # content (decisions/M1, #329). Classify tags
    # such a marker like any other token -- what the #274 rule above
    # lacks is not the TAG but the token: extract claims a delimited
    # clause and tokenize gives its tokens Role.MAIDEN up front, so
    # segment (main stream = role is None) leaves them out of every
    # segment, they never enter `pieces`, and a rule that walks pieces
    # cannot reach them.
    #
    # Scoped to the CLAUSE, via state.extracted (one role + inner span
    # per delimited region), rather than to a maiden token's
    # neighbours. Both reasons are load-bearing:
    #   * Role.MAIDEN is not proof of extraction -- the #274 rule above
    #     sets it too, on the bare form, earlier in this same function.
    #     A neighbour test would fire there and eat the 'Nee' out of
    #     "Jane Smith nee Nee Jones". Keying on extracted spans puts
    #     the bare path out of reach by construction.
    #   * Separate clauses are separate content. In "(Nee) (Jones)" the
    #     two land as one contiguous run of maiden tokens, so only the
    #     clause bound keeps the lone "(Nee)" intact.
    # Drop the clause's LEADING MARKER only when the clause holds a
    # word past it: `Nee` is a real surname (Irish Ni/Nee, and a
    # Chinese romanization), so a one-token "(Nee)" is a maiden name,
    # not a marker. The marker and no more, whatever the clause holds
    # past it: cases.py's maiden_marker_delimited_three_token_clause is
    # the row that bounds this in both directions, every other
    # delimited row having a two-token clause where the two readings
    # agree. The marker is one token for a word entry and the whole run
    # for a phrase one ('z domu'), which is why the loop below counts
    # continuation tags rather than assuming one.
    # Spans index the original string by the anti-#100
    # invariant, and script_segment only ever splits a token into
    # sub-slices, so containment stays exact.
    #
    # Bisect rather than scan the token list per clause: that is
    # quadratic in the number of delimited pairs, and "(a) " * 3200 --
    # 4x test_benchmark's base, NOT a doubling -- measured a 14.1x cost
    # against the 4.1x the same shape holds under a policy with no
    # maiden_delimiters. The control is what says which unit a ratio is
    # in: linear is ~4 for 4x the input and ~2 for a doubling, so a 4.1x
    # control cannot be per doubling. Re-measured 2026-08-03 at 11.2x
    # against 4.2x (3.2x against 2.1x per doubling) -- the separation
    # replicates, the exact ratio moves with the runner. Same idiom,
    # and the same reason, as _extract._overlaps and _tokenize's origin
    # resolution. test_benchmark's maiden_pairs shape is the guard.
    if any(role is Role.MAIDEN for role, _ in state.extracted):
        starts = [t.span.start for t in tokens]
        for role, clause in state.extracted:
            if role is not Role.MAIDEN:
                continue
            # first token starting at or after the clause opens; tokens
            # are span-sorted and group never reorders or resizes them
            first = bisect.bisect_left(starts, clause.start)
            if (first >= len(tokens)
                    or "vocab:maiden-marker" not in tokens[first].tags):
                continue
            # How many tokens the marker is: one, or the whole run of a
            # phrase entry, as classify recorded it. Same walk the
            # piece test above makes, in token-index space.
            run = marker_run_length(
                tokens[k].tags for k in range(first + 1, len(tokens)))
            # Testing the end of the token AFTER the run proves the run
            # AND that token are all inside: tokens do not overlap and
            # are index-ordered, so every earlier one ends no later,
            # and bisect already put first.start at or after
            # clause.start. That is also the "more than the marker"
            # test, since the tokens inside a clause are contiguous in
            # index order -- a clause holding nothing but its marker
            # keeps its words, exactly as a one-token "(Nee)" does.
            # rules/M3: "a marker followed by a comma is no marker"
            # -- asked of the same word extract's M3 test asks it of
            if (first + run < len(tokens)
                    and tokens[first + run].span.end <= clause.end
                    and not comma_follows_marker(tokens[first + run].text)):
                dropped.extend(range(first, first + run))
    return copy_with(
        state, tokens=tuple(tokens), pieces=tuple(all_pieces),
        piece_tags=tuple(all_ptags), dropped=tuple(dropped),
        tail_reads=tuple(all_reads), ambiguities=tuple(ambiguities))
