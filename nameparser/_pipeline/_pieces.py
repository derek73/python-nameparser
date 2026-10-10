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

Layering: imports _state and _vocab only; segment, script_segment,
classify, group, assign, post_rules and _comma import it (segment,
script_segment and classify for the #289/#516 own-words span alone) -- and neither of the two it imports imports it
back.

Naming follows _vocab's: inside an already-private module the leading
underscore marks module-PRIVATE, so the names other stages call are
bare and only the internals keep it (_PERIOD_ABBREV here). Getting that
backwards -- which this module did until the underscores came off --
costs a reader the one cheap way to tell a shared predicate from a
helper.
"""
from __future__ import annotations

from collections.abc import (
    Callable, Container, Iterable, Mapping, Sequence, Set)
from typing import NamedTuple

from nameparser._pipeline._state import (
    AMBIGUOUS_ACRONYM_TAG, NAME_ROLES, SHAPE_ACRONYM_TAG, SUFFIX_OR_UNREAD,
    WorkToken,
)
from nameparser._pipeline._vocab import (
    _PERIOD_ABBREV, _ROMAN, Lean, ambiguous_lean, in_initialless_script,
    is_single_letter_numeral, is_trailing_numeral_suffix, tag_marker_runs,
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


# A particle, or a piece a join made one: what group's prefix chain
# (at its loop in _group_segment) chains and stops at, what P3's join
# derives a prefix from, and what group's rootname count and leading
# scan step past.
def is_prefix_piece(piece: Sequence[int], ptags: Set[str],
                    tokens: Sequence[WorkToken]) -> bool:
    if "prefix" in ptags:
        return True
    return len(piece) == 1 and "particle" in tokens[piece[0]].tags


# rules.md#P3: "a recognized connective joins its neighbors into one
# name part, connective runs included — except a single-letter
# connective in a three-word name, which stays a name word, and a
# single-letter connective that reads as an initial instead, which
# never joins" (history: decisions.md#P3)
def is_conj_piece(piece: Sequence[int], ptags: Set[str],
                  tokens: Sequence[WorkToken]) -> bool:
    if "conjunction" in ptags:
        return True
    return len(piece) == 1 and "conjunction" in tokens[piece[0]].tags


def joined_tags(ptags: Sequence[Set[str]], lo: int, hi: int,
                add: Set[str] = frozenset(),
                drop: Set[str] = frozenset()) -> set[str]:
    # the ONE definition of a merged piece's tags: merge_pieces applies
    # it, and P5's reserve reads it to model the join it is
    # weighing (#425) -- so the view cannot drift from the merge.
    # A merged piece inherits every part's tags, so a site whose
    # product is not what its parts were drops what no longer
    # applies: the particle chain drops `prefix`, the bound join
    # `title` (a derived title tag on the pair would have assign
    # peel the given name as a leading title).
    return (set().union(*ptags[lo:hi]) | add) - drop


def merge_pieces(pieces: list[list[int]], ptags: list[set[str]],
                 lo: int, hi: int, add: Set[str] = frozenset(),
                 drop: Set[str] = frozenset()) -> None:
    # pieces/ptags are parallel arrays; every merge must update
    # both in lockstep.
    #
    # Extend the first piece IN PLACE rather than rebuilding the
    # merged list. The obvious spelling --
    #     pieces[lo:hi] = [[i for p in pieces[lo:hi] for i in p]]
    # -- re-flattens everything accumulated so far on every call, so
    # a chain that merges into the same piece n times copies
    # 1+2+...+n and the stage goes quadratic in the length of the
    # chain. A conjunction run ("and " * n) does exactly that: it
    # measured 2.4x-2.9x per doubling against the 2.0x every other
    # shape holds. No piece list is aliased outside this function
    # (each caller builds every piece as a fresh list -- group's
    # [i], _comma's _pieces -- and reads pieces[k] only before a
    # merge), so mutating is safe; verified
    # identical token/role/tag/span/ambiguity output over 54,877
    # names. tests/v2/test_benchmark.py's "and " shape is the guard.
    #
    # Every call site passes lo < hi, and this REQUIRES it: with
    # lo >= hi the slice assignment would insert rather than
    # replace, putting a second reference to pieces[lo] into the
    # array, and the next merge to touch either index would extend
    # the same list twice. The old rebuild-a-fresh-list spelling
    # was harmless there. Keep the bound if you add a caller.
    combined = pieces[lo]
    for piece in pieces[lo + 1:hi]:
        combined.extend(piece)
    pieces[lo:hi] = [combined]
    ptags[lo:hi] = [joined_tags(ptags, lo, hi, add, drop)]


def join_connectives(pieces: list[list[int]], ptags: list[set[str]],
                     tokens: Sequence[WorkToken], *,
                     letter_stays: bool, titles_only: bool,
                     frozen: Set[int] = frozenset()) -> None:
    """rules.md#P3's connective joins, for both parts that make them:
    group's name segments, and the part after a comma, which
    `_comma.decide` reads before group joins anything (#617, where the
    two had been copies that differed). Contiguous connectives merge
    into one first (v1: "of the"); then each connective joins its
    neighbours, taking its kind from the one on its left, or from the
    one on its right where it opens the part.

    `letter_stays` is the single-letter carve-out's answer for this
    part, and it reaches a LONE single-letter connective only: one
    beside another connective merges into their run first and joins
    with it. Group reads it from the name's rootname count; the comma
    part, which a title joins and a name word never does, always keeps
    the lone letter. `titles_only` is the comma part's: a join is made
    only where the neighbour is a title, and makes the joined piece
    one ('Mr. and Mrs.') with no prefix kind, nothing in that part
    being a particle chain; any other connective there is left a word,
    the reading deciding what it is. Otherwise every join is made and
    takes the neighbour's title and prefix kinds. `frozen` holds the
    TOKEN index of each connective that is to make no join or run of
    its own -- group's, the generational ones with no name word on one
    side; the comma part's, every generational one -- though a
    neighbour's join may still take one in."""
    # contiguous conjunction runs merge first
    #
    # `pieces[k][0] in frozen` and not `frozen.isdisjoint(...)`:
    # the piece this loop extends GROWS with every merge, so a
    # test over its tokens costs 1+2+...+n and the stage goes
    # quadratic in the length of a connective run -- measured,
    # 'and ' x3200 took 41.8ms against 21.7ms, 6.2x per 4x input
    # where the shape reads 4.1x, and tests/v2/test_benchmark.py's
    # "and " shape is the guard that caught it. Reading the first
    # token alone is exact rather than an approximation: a frozen
    # piece is one token and this branch never merges it, and this
    # loop finishes before the join below can take one into a
    # neighbour's piece, so a piece holding a frozen token here IS
    # that token.
    k = 0
    while k < len(pieces) - 1:
        if (is_conj_piece(pieces[k], ptags[k], tokens)
                and is_conj_piece(pieces[k + 1], ptags[k + 1], tokens)
                and pieces[k][0] not in frozen
                and pieces[k + 1][0] not in frozen):
            merge_pieces(pieces, ptags, k, k + 2, add={"conjunction"})
        else:
            k += 1
    # each conjunction joins its neighbors, rules.md#P3: "except a
    # single-letter connective in a three-word name, which stays a
    # name word" (v1's Google Code issue 11 carve-out, the
    # "john e smith" bug).
    k = 0
    while k < len(pieces):
        # first token again, and here it is exact for the second
        # reason as well: the piece a join produces is left BEHIND
        # `k`, so no merged piece is ever tested twice.
        if (not is_conj_piece(pieces[k], ptags[k], tokens)
                or pieces[k][0] in frozen):
            k += 1
            continue
        if letter_stays and len(pieces[k]) == 1:
            text = tokens[pieces[k][0]].text
            if len(text) == 1 and text.isalpha():
                k += 1
                continue
        start = max(0, k - 1)
        end = min(len(pieces), k + 2)
        neighbor = start if start < k else end - 1
        derived = set()
        if is_title_piece(pieces[neighbor], ptags[neighbor], tokens):
            derived.add("title")
        elif titles_only:
            k += 1
            continue
        if (not titles_only
                and is_prefix_piece(pieces[neighbor], ptags[neighbor],
                                    tokens)):
            derived.add("prefix")
        merge_pieces(pieces, ptags, start, end, add=derived)
        k = start + 1


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
    # THIS is the one home for the number, `is_title_shaped` pointing
    # here rather than restating it: routing this hot path through the
    # shared function costs one frame per call (`is_leading_title`
    # runs on every leading piece of every parse, unlike
    # name_word_count's comma-only path), moving the reference name
    # from 412/449 to 417/454 -- five calls on `Dr. Juan de la Vega
    # III`, recomputable with `uv run python
    # tools/perf/call_count.py`. Kept as two spellings of ONE test
    # instead -- if you touch one, touch both, and
    # `test_is_title_shaped_and_is_leading_title_agree` (this module's
    # own test file) checks it over the union of both predicates'
    # example tables rather than leaving it to a sentence.
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


# rules.md#S2: "A title word never starts the run, and neither does a
# member of the ambiguous class, a single letter, a connective" -- what
# starts #602's credential run, one predicate for the trailing peel and
# the given-part walk (mechanisms.md#ONE-PREDICATE-PER-QUESTION)
def starts_a_credential_run(piece: Sequence[int], ptags: Set[str],
                            tokens: Sequence[WorkToken]) -> bool:
    """Whether one piece starts #602's run: an unambiguous LATIN
    suffix word of two or more letters -- a credential acronym or a
    generational word -- that no other vocabulary claims as a name.

    `is_suffix_piece` already refuses the ambiguous class and an
    initial-shaped letter. Refused here: any single letter (a lowercase
    `i` or `v` mid-name is an initial or a connective far more often
    than a numeral, and carries no `initial` tag), a connective, a
    word that is also bound given-name or particle vocabulary (`abd`
    heads `Abd Allah`; `vd`, `mc`), and the non-Latin honorific words.

    The split credential group merges ('Ph. D.', the one piece carrying
    the "suffix" piece tag) starts it as its one-token spelling 'PhD'
    does: a run that started for one spelling of a word and not the
    other is the vocabulary-against-shape split AGENTS.md's spelling
    sweep names (#603 found it, 'Smith, John Ph. D. Jones' keeping
    middle 'Jones' where 'Smith, John PhD Jones' reads suffix
    'PhD Jones'). The no-comma spelling is not reached: `run_start`
    asks only of the pieces `peel_walk` keeps, and the walk drops the
    merged piece, so 'John Smith Ph. D. Jones' still reads family
    'Jones'.
    """
    if "suffix" in ptags:
        # the Ph./D. pair alone: a connective join keeps the tag on the
        # wider piece ('Ph. D. and Mary'), which starts nothing, as
        # 'PhD and Mary' does not
        return len(piece) == 2
    if len(piece) != 1 or not is_suffix_piece(piece, ptags, tokens):
        return False
    tok = tokens[piece[0]]
    if not tok.tags.isdisjoint(_NOT_A_RUN_START):
        return False
    # C-level, no generator frame per character
    letters = "".join(filter(str.isalpha, tok.text.lower()))
    return len(letters) >= 2 and letters.isascii()


#: tags of suffix words another vocabulary claims as a name word or a
#: joiner, which therefore never start #602's run
_NOT_A_RUN_START = frozenset({"conjunction", "particle",
                              "vocab:bound-given"})


def is_lone_never_given_particle(piece: Sequence[int],
                                 tokens: Sequence[WorkToken]) -> bool:
    """A piece that is one never-given particle (rules.md#P1's fold
    site). One predicate, asked by the fold in post_rules and by two
    sites in assign that predict the fold will take the particle
    forward: the given slot, which then leaves no given name in front
    of a member (#573), and P6's attachment after a family comma,
    which then leaves no given word for the tail to stand behind
    (#613) -- copies would drift silently, each site's own tests
    still passing (mechanisms.md#ONE-PREDICATE-PER-QUESTION)."""
    return (len(piece) == 1
            and "particle" in tokens[piece[0]].tags
            and "vocab:particle-ambiguous" not in tokens[piece[0]].tags)


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


def _anchors(piece: Sequence[int], tokens: Sequence[WorkToken]) -> bool:
    """Whether a suffix piece may ANCHOR an ambiguous member behind it
    (#544): not a connective, not a particle, and not a single-letter
    roman numeral.

    A connective anchors nothing because between two name words it is
    a link -- the generational 'i' is also Catalan's 'i' (rules.md#P3)
    -- and 'Jane Doe nee Puig i Ma' must keep its clause. A particle
    anchors nothing for the same reason from the other side: it joins
    the name word behind it (rules.md#P2), so a word that is both
    particle and suffix vocabulary ('vd', 'mc') standing in front of
    a member is the head of a family name, not a credential list --
    'Smith vd Ma, John' keeps family 'Smith vd Ma' and 'Jan vd Ma'
    family 'vd Ma'. A particle MEMBER is still anchored by a
    credential in front of it ('doe, jane v phd do'); the exclusion is
    of the anchor only. A single-letter roman numeral, in any case
    ('V', 'v', 'I.'), anchors nothing for its SHAPE: one letter is
    the shape a middle initial is written in ('V' can be one), and S3
    retired single-character vocabulary matches for the same reason.
    Not because a numeral is no credential -- a multi-letter suffix
    word ('III', 'Jr') anchors like any other suffix piece
    (`is_single_letter_numeral`). A title/suffix DUAL ('ms', 'md',
    'sr') does anchor, except in the given part's
    leading title run, where it stands in title position ('Smith, Ms
    Ma' is Ms. Ma Smith); that exclusion is the callers', which start
    their walks past the leading title run or, in
    `segment_suffix_reading`, read no anchor at all in a part whose
    leading title run holds one.

    Asked only of a piece `is_suffix_piece` accepted, and only once a
    member's own writing has declined, so an ordinary name never pays
    for it."""
    if len(piece) != 1:
        return True
    tok = tokens[piece[0]]
    return ("conjunction" not in tok.tags
            and "particle" not in tok.tags
            and not is_single_letter_numeral(tok.text))


# #544: an ambiguous member standing BEHIND an unambiguous credential
# in one run is described by that credential's company, not by its
# own writing -- 'PhD MEng' is a list of degrees whatever case 'MEng'
# is written in. ONE forward pass per question, so a run of members
# is read in linear time: a look-behind per member is quadratic in
# the run, which test_benchmark's frame-ratio guard is built to catch.
def credential_anchors(order: Sequence[int],
                       pieces: Sequence[Sequence[int]],
                       ptags: Sequence[Set[str]],
                       tokens: Sequence[WorkToken],
                       first_kept: bool = True) -> list[bool]:
    """For each position of `order` (piece indices in text order),
    whether a lone listed member standing there is ANCHORED: the
    contiguous run of pieces in FRONT of it that are suffix pieces or
    lone ambiguous members ends in -- counting back past the members --
    a suffix piece that may anchor (`_anchors`). Any other piece ends
    the run. The anchor is in front only: 'Wang Ma PhD' leaves 'Ma'
    unanchored.

    The caller decides where the walk starts, and starts it past the
    leading title run, where a title/suffix dual reads as a title
    ('Smith, MD MA Ma' keeps its middle name). Where `order` holds the
    name part, its own leading position is the name the reserve keeps
    -- `rest[0]` at the no-comma peel, the given part's own first
    piece at the given-slot call sites -- so ITS writing never anchors
    what stands behind it, whatever vocabulary it carries: 'PhD Ma'
    keeps the count's reading, family 'Ma', rather than reading as a
    credential list headed by the given name itself. `first_kept`
    False is the one caller with no reserve, `segment_suffix_reading`,
    asking whether a comma part is a credential run at all: there the
    first piece is a run member like any other ('Smith, PhD MEng')."""
    out: list[bool] = []
    anchor = False
    for pos, idx in enumerate(order):
        out.append(anchor)
        if pos == 0 and first_kept:
            continue
        piece = pieces[idx]
        if is_suffix_piece(piece, ptags[idx], tokens):
            # a suffix piece that may not anchor still ENDS the run it
            # would have anchored: 'PhD v Ma' is not a credential list
            # through the numeral
            anchor = _anchors(piece, tokens)
        elif not (len(piece) == 1
                  and AMBIGUOUS_ACRONYM_TAG in tokens[piece[0]].tags):
            anchor = False
    return out


def given_slot_anchors(pieces: Sequence[Sequence[int]],
                       ptags: Sequence[Set[str]],
                       tokens: Sequence[WorkToken],
                       start: int, end: int | None = None,
                       skip: Container[int] = ()) -> list[bool]:
    """`credential_anchors` for the given part's slot, indexed by PIECE
    rather than by position: the pass over `start` to `end`, `skip`
    spliced out, and False before `start`, from `end` on and at every
    skipped piece. `start` is where the leading title run ends, so a
    title/suffix dual standing in it anchors nothing ('Smith, MD MA
    Ma'), and the piece at `start` is the given name the reserve keeps.
    The one home of that query for assign's given slot."""
    stop = len(pieces) if end is None else end
    order: Sequence[int] = range(start, stop)
    if skip:
        order = [q for q in order if q not in skip]
    out = [False] * len(pieces)
    for q, anchored in zip(order, credential_anchors(order, pieces, ptags,
                                                     tokens)):
        out[q] = anchored
    return out


def anchor_in_reach(back: Iterable[int],
                    pieces: Sequence[Sequence[int]],
                    ptags: Sequence[Set[str]],
                    tokens: Sequence[WorkToken],
                    skip: Container[int] = ()) -> bool:
    """False where `credential_anchors` must answer False for the
    member standing just behind `back` -- the piece indices in front
    of it, nearest first, `skip` spliced out: past the lone members
    in front, the first other piece is no suffix piece, or there is
    none. True means only "ask the pass".

    Exact in that direction because the test is weaker than the
    pass's: a suffix piece carries "suffix" in its ptags or is one
    token carrying "vocab:suffix" (`is_suffix_piece`), so a piece
    failing both can neither anchor nor carry a run on. Read from tags
    alone, with no frame per piece, so the ordinary name ending in a
    Title-case member ('John Smith Ma', 'Doe, John Q. Ma') spends one
    frame here rather than the pass's one per piece. Callers pass the
    positions the pass itself would read or a superset reaching
    further back: the walk meets any anchor the pass would find before
    it reaches past the pass's start, so reaching further can cost a
    pass that finds nothing and never a reading."""
    for q in back:
        if q in skip:
            continue
        piece = pieces[q]
        if "suffix" in ptags[q]:
            return True
        if len(piece) != 1:
            return False
        tags = tokens[piece[0]].tags
        if "vocab:suffix" in tags:
            return True
        if AMBIGUOUS_ACRONYM_TAG not in tags:
            return False
    return False


def segment_suffix_reading(pieces: Sequence[Sequence[int]],
                           ptags: Sequence[Set[str]],
                           tokens: Sequence[WorkToken],
                           lenient: bool,
                           one_case: bool | None,
                           anchored: list[int] | None = None,
                           absorbed: list[int] | None = None,
                           licensed: Container[int] = (),
                           ) -> tuple[bool, ...] | None:
    """How each piece of a no-name segment reads: True a suffix, False
    a title. None when the segment holds a name word and so is not a
    credential run at all.

    `one_case` admits #289's credential lean: an ALL-CAPS member of
    the ambiguous set inside a mixed-case name is a credential in this
    slot even with one word before the comma, because the writing is
    evidence the count does not have ('Smith, MA' -> family 'Smith',
    suffix 'MA'). Only the LEAN reaches here on its own: a token
    admitted to the class by SHAPE takes the count instead, which
    `_comma.decide` takes and hands in as `licensed`, below ('Smith,
    A.B.' -> given 'A.B.', one name word being no count).

    A listed member ANCHORED by an unambiguous credential in front of
    it in the same run reads as a credential too, whatever its writing
    (#544, `credential_anchors`): 'Smith, PhD MEng' is family 'Smith'
    with two degrees. A title/suffix dual standing in the part's
    LEADING TITLE RUN -- every piece ahead of it a title or another
    such dual -- is a title there, and in a part that holds one this
    reading anchors nothing at all, not by the dual and not by a
    later credential: the dual makes the next name-position word the
    given name, and reading the part wholly as credentials would
    stack the anchor's guess on the dual's ('Smith, Ms Ma', 'Smith,
    Ms MD Ma' and 'Smith, MD PhD Ma' keep a given name, 'Smith,
    Prof. MD Ma' too). The walk then reads the part, and its given
    slot's company starts past that given name ('Smith, MD PhD Jr
    Ma' reads suffix 'Jr Ma'). A plain title ahead of the credential
    does not stop this reading ('Smith, Dr. PhD LAc' reads title
    'Dr.', suffix 'PhD LAc').

    `anchored`, when the caller passes a list, receives the index of
    every piece the anchor read as a credential after its own writing
    declined -- the picks the caller reports, since this decides them
    (mechanisms.md#AMBIGUITY-AT-THE-DECISION-SITE). A member whose own
    capitals lean credential is not among them. Meaningful only when
    the answer is not None: a segment the walk abandons part-way may
    have appended to it first.

    ONE reader since #613: `_comma.decide`, which reads the part once
    at group's head and binds the roles this returns, so the decision
    that the part holds no name word and the roles its words get
    cannot disagree. Until then it answered for two readers in
    _assign.py, the no-name gate and the router, and #429 shipped the
    inverse of its own fix by deriving that agreement twice
    (mechanisms.md#ONE-PREDICATE-PER-QUESTION); it answered for a
    third until #436, group's one-entry join.

    `licensed` holds the pieces rules.md#C1's count has licensed as
    credentials -- ambiguous-class words in a credential run behind
    two name words -- and each reads as a suffix whatever its writing
    or company.

    rules.md#S2's initial veto keeps a roman numeral out of a suffix
    reading, which is right after a NAME word: 'Smith, John V.' is a
    middle initial (#432). After a SUFFIX word the numeral is
    describing that suffix -- 'PSM I' is Professional Scrum Master
    level I -- so the run continues through it, period included, an
    initial there being no shape anyone writes (#430). A title resets
    that: what follows a bare title is not continuing a credential.

    A part OPENED by a credential is the postnominal part however it
    goes on (#603, rules.md#C1): where an unambiguous suffix word that
    starts #602's run (`starts_a_credential_run`) is the first suffix
    word of the part, with only titles in front of it (a title/suffix
    dual among them ends the chance: a credential behind one opens
    nothing), every later
    word is read as #602's run reads the given part -- a title word as
    a title, anything else as a suffix -- so 'John Smith, PhD Jones'
    and 'Smith, PhD Jones' read suffix 'PhD Jones'. A word of the
    title vocabulary as well opens nothing (#603, Derek): in front of
    a given name it is the listing form's title ('Smith, Ms Jane'),
    and no count of the words before the comma can tell a two-word
    surname from a given name and a family name, so none decides it.
    `absorbed`, when passed, receives the index
    of every piece the opened part takes that would otherwise have
    made this None -- the caller reports them, as #602's run reports
    the name words it takes.

    None covers both ways a segment can fail to be a run: a name word
    anywhere in it (in a part no credential opened), and no pieces at
    all ('Doe,, Jr.', which holds no
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
    keeps its positional read instead of being merged (through
    `_comma.decide`'s suffix comma, behind a whole name). Uses the same
    is_leading_title predicate the peel does, period-abbreviation
    inference included, so the two cannot disagree about what a title
    is; a mixed run like 'Smith, Dr. Jr.' is a title and a postnominal,
    each read where it stands, never a title run 'Dr. Jr.'.
    """
    if not pieces:
        return None
    out: list[bool] = []
    # #544: `credential_anchors` over the whole part, computed the
    # first time a member's writing declines with a suffix piece in
    # reach in front of it (`anchor_in_reach`, asked only while the
    # pass does not exist yet). A member opening the part has nothing
    # in front and asks neither ('Smith, Ed', 'Smith, Ma John'); a
    # name word in front returns None before the member is reached;
    # and a title in front ends the reach test, so 'Smith, Dr. Ma'
    # pays that one test and no pass.
    anchors: list[bool] | None = None
    # Whether every piece so far stands in the part's leading title
    # run (titles, and title/suffix duals), and whether a dual has
    # stood there: once one has, nothing in the part anchors. Tracked
    # here rather than read off `leading_titles`, whose period-shape
    # inference counts a suffix like 'Esq.' into the run ('Smith, Esq.
    # MD Ma' keeps its anchored 'Ma' only by this walk's reading).
    leading = True
    dual_led = False
    # #603: the first suffix word of the leading run, which may open
    # the part unless a dual stood ahead of it; asked whether it does
    # only once a piece reaches the title and name branches below, so a
    # part of nothing but suffix words ('Smith, Jr.', 'Smith, PhD MA')
    # never pays for the question
    opener: tuple[Sequence[int], Set[str]] | None = None
    opened = False
    for piece, tags in zip(pieces, ptags):
        # the verdict just recorded IS "stands behind a suffix" -- keeping
        # a separate flag meant maintaining that equality by hand at three
        # sites, and a fourth branch that appended without assigning would
        # have diverged silently
        after_suffix = bool(out) and out[-1]
        if is_suffix_piece(piece, tags, tokens):
            if (leading and len(piece) == 1
                    and "vocab:title" in tokens[piece[0]].tags):
                dual_led = True
            else:
                if leading and not dual_led:
                    opener = (piece, tags)
                leading = False
            out.append(True)
            continue
        member = (len(piece) == 1
                  and AMBIGUOUS_ACRONYM_TAG in tokens[piece[0]].tags)
        if member and listed_lean(tokens[piece[0]], one_case) \
                == "credential":
            leading = False
            out.append(True)
            continue
        # A word rules.md#C1's count licenses as a credential: the
        # caller (`_comma.decide`) counted two name words before the
        # comma and found the part a credential run, which settles the
        # ambiguous word here before S2's anchors are asked (#613)
        if len(piece) == 1 and piece[0] in licensed:
            leading = False
            out.append(True)
            continue
        if (member and not dual_led
                and SHAPE_ACRONYM_TAG not in tokens[piece[0]].tags):
            if anchors is None and out and anchor_in_reach(
                    range(len(out) - 1, -1, -1), pieces, ptags, tokens):
                anchors = credential_anchors(range(len(pieces)), pieces,
                                             ptags, tokens, first_kept=False)
            if anchors is not None and anchors[len(out)]:
                leading = False
                if anchored is not None:
                    anchored.append(len(out))
                out.append(True)
                continue
        if (lenient and after_suffix
                and _numeral_behind_the_initial_veto(piece, tokens)):
            leading = False
            out.append(True)
            continue
        if opener is not None:
            # asked once: cleared, as it is set at most once
            opened = starts_a_credential_run(opener[0], opener[1], tokens)
            opener = None
        if opened:
            # #602's run: a title word reads as a title, anything else
            # as a suffix -- vocabulary only, as in the given part
            if is_title_piece(piece, tags, tokens):
                out.append(False)
            else:
                if absorbed is not None:
                    absorbed.append(len(out))
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
    peel order, either way (the last may sit at rest[names - 1]).
    `anchors` is `peel_trailing`'s working state for `tail_reading`
    alone -- the walk's `credential_anchors` pass over `rest` where a
    member needed one, handed to the next pass of the fixed point
    (`peel_trailing`'s `start`). No caller reads it, and the Peel
    `tail_reading` returns carries None."""

    names: int
    numeral: tuple[int, ...] | None
    picks: tuple[tuple[int, ...], ...]
    anchors: list[bool] | None
    #: #602 (`credential_run`): the pieces in rest[names:] that are
    #: title words inside the credential run, and the name pieces the
    #: run absorbed, which assign reports
    run_titles: tuple[int, ...] = ()
    absorbed: tuple[tuple[int, ...], ...] = ()


# rules.md#S2: "a trailing word of the suffix vocabulary reads as a
# suffix — generational forms and credential acronyms alike, and an
# ambiguous acronym written with its periods, one after each letter or
# one after each of two or more letter chunks, counts unambiguously; a
# single trailing period is the abbreviation shape any word can wear
# and does not" -- and: "a BARE ambiguous acronym is consumed only when
# the name has words to spare"
# (v1's are_suffixes tail rule, with the roman-numeral special)
def peel_walk(start: int, ptags: Sequence[Set[str]]) -> list[int]:
    """The indices peel_trailing walks: `start` to the segment's end,
    minus the group-flagged credential pieces (the Ph. D. merge),
    which assign reads as suffixes at any position. Built here and nowhere
    else, so the walk's input cannot drift between assign and the
    group sites that read it: the numeral fork is a last-piece
    test that reads the piece before as rest[k - 2], which holds only
    over this list."""
    return [j for j in range(start, len(ptags))
            if "suffix" not in ptags[j]]


def trailing_start(start: int, pieces: Sequence[Sequence[int]],
                    ptags: Sequence[Set[str]], tokens: Sequence[WorkToken],
                    *, one_case: bool | None) -> int:
    """Where assign's trailing suffix run begins, read over the pieces
    as they stand from `start`: the index of the first piece the S2
    peel takes, or len(pieces) when it takes none (#424). What P2's
    chain stops before where S2's run was not read once ahead of it
    (#614: a family comma's parts, a run holding a name piece), and
    what M2's walk stops before where no trailing rule reads the
    clause -- each had asked "is this a
    suffix?" with the suffix-piece test, which vetoes a bare 'V' as
    an initial (the #401 question), and so took a trailing numeral,
    or a bare acronym with words to spare, into the family or the
    maiden name.

    Both forks, always, and #602's credential run on top
    (`credential_run`), so P2's chain stops where the run starts.
    Readers that also need H5's title chain read the same pieces
    through `tail_reading`, which runs this pair's peel and the chain
    to a fixed point -- the maiden take among them (#601). So this
    function's answer is the whole answer only where no trailing
    title chain also reads the pieces."""
    rest = peel_walk(start, ptags)
    names = run_start(rest, peel_trailing(rest, pieces, ptags, tokens,
                                          one_case).names,
                      pieces, ptags, tokens)
    return rest[names] if names < len(rest) else len(pieces)


# #289/#516: the "listed member, not by-shape" test both
# peel_trailing and segment_suffix_reading ask before reading the
# lean -- shared here so the two cannot drift on what counts
# (quality-review finding: it was spelled twice, once per site,
# before this). Those two test "vocab:suffix-ambiguous" in tags
# INLINE, before calling this, rather than leaving that cheap check to
# this function's own body: measured, a caller whose `elif` reaches
# this on every piece (segment_suffix_reading's does, one per
# family-comma segment 1, member or not) pays one frame for the call
# regardless of what is inside it, and the inline pre-check is what
# keeps a non-member piece ("Smith, John"'s "John") from ever making
# the call at all.
#
# A further caller since #533 -- credential_at_the_given_slot just
# below -- deliberately does NOT pre-check: it owns #531's reading
# and leaves membership to its own callers (its docstring says so),
# and the frame argument holds transitively because its caller asks
# inline -- `AMBIGUOUS_ACRONYM_TAG in tok.tags` after a
# `len(piece) == 1` at assign's given-part trailing slot. So no
# non-member piece reaches this function down that route either.
def listed_lean(token: WorkToken, one_case: bool | None) -> Lean | None:
    """`ambiguous_lean` for a LISTED bare-ambiguous token, or None if
    the token is not tagged a listed member, is admitted by SHAPE
    instead (`SHAPE_ACRONYM_TAG`, a switch's doing, not the writing's),
    or there is no case fact to ask at all."""
    if (one_case is None or AMBIGUOUS_ACRONYM_TAG not in token.tags
            or SHAPE_ACRONYM_TAG in token.tags):
        return None
    return ambiguous_lean(token.text, one_case)


def credential_at_the_given_slot(
        token: WorkToken, one_case: bool | None,
        anchored: Callable[[], bool] | None = None) -> bool:
    """#531's reading of a class MEMBER ending the given part after a
    family comma: the credential unless the writing says otherwise.
    The caller decides membership and that the piece ends that part.

    The words to spare are there by construction at that slot, so the
    count says nothing and only the lean does; a member that is also
    particle vocabulary reads as the credential on a POSITIVE lean
    alone, P6's attachment keeping every other spelling.

    Or where the member is ANCHORED (#544): an unambiguous credential
    in front of it in the same run (`credential_anchors`) makes it the
    credential whatever its writing says, a particle member included
    -- a degree in front outranks P6's attachment, as the capitals do
    ('doe, jane v phd do' reads suffix 'v phd do'). Only the caller
    knows the run, so it computes the anchor; `anchored` is a THUNK,
    asked last, so a member the writing already settles never pays
    for the walk.

    Called from assign's walk over the given part, as one function
    rather than a condition written at the site
    (mechanisms.md#ONE-PREDICATE-PER-QUESTION). It is a text-and-tags
    question, which is what puts it in this module rather than beside
    any caller.

    The membership half of that contract is CHECKED rather than
    trusted, because getting it wrong is silent: all three of
    `listed_lean`'s None reasons fall through to the `particle` test
    below, so a non-member handed in by mistake is answered True --
    "read it as the credential" -- for a word the class never admitted.
    An assert rather than a raise or a branch: it enters no Python
    frame (measured -- 'Doe, John MA' stays at 311), it states the
    contract where a reader of the function body meets it, and under
    -O it is exactly the code that was here before.
    """
    assert AMBIGUOUS_ACRONYM_TAG in token.tags, (
        f"credential_at_the_given_slot is #531's reading of a LISTED "
        f"class member; {token.text!r} carries {sorted(token.tags)} "
        f"and is not one. The caller decides membership -- test "
        f"AMBIGUOUS_ACRONYM_TAG before calling")
    lean = listed_lean(token, one_case)
    if lean == "credential" or (lean is None
                                and "particle" not in token.tags):
        return True
    return anchored is not None and anchored()


#: `_chain_units`' marks: a piece opening a name unit, a name word the
#: chain joins to the run in front of it, a particle inside that run
OPENS, JOINED, BOUND = 1, 0, -1


def second_unit(rest: Sequence[int], units: Sequence[int]) -> int:
    """The position in `rest` of the piece opening its second name
    unit, `len(rest)` where there is none: `rest[:m]` holds two units
    exactly when this is below `m`. The first piece always counts as
    a unit's, being where the name the walk reads starts."""
    for i in range(1, len(rest)):
        if units[rest[i]] == OPENS:
            return i
    return len(rest)


def peel_trailing(rest: Sequence[int], pieces: Sequence[Sequence[int]],
                   ptags: Sequence[Set[str]],
                   tokens: Sequence[WorkToken],
                   one_case: bool | None,
                   start: int | None = None,
                   anchors: list[bool] | None = None,
                   units: Sequence[int] | None = None,
                   second: int = 1) -> Peel:
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

    `start` and `anchors` resume a walk rather than begin one: the
    walk picks up at `rest[start - 1]`, as though the pieces from
    `start` on were already peeled, with `anchors` the pass an earlier
    walk built (or None). Only `tail_reading` passes them, and its
    docstring states when that answers what a fresh walk would. The
    returned picks are the resumed walk's own; the numeral is never
    read, `start` standing short of the walk's last piece.

    `second` is where the second name unit opens in `rest`
    (`second_unit`), the caller's to find once; positions are units
    where `units` is None, and it is 1.

    `units`, where given, marks each piece by the unit the chain will
    put it in (`_chain_units`, #620): the words to spare are counted in
    units, so a particle chain counts as the one name word P2 makes of
    it, and a piece the chain joins into a run -- a particle inside
    it, or a word the reading does not weigh -- is a name word the
    walk stops at. The numeral fork still reads the piece in front of the
    numeral as written: an initial there keeps it a name word whatever
    unit the initial is in ('John van der J. V', rules.md#P2).
    """
    picks: list[tuple[int, ...]] = []
    numeral: tuple[int, ...] | None = None
    # where the second name unit opens in `rest`, found once a member
    # asks; positions are units where `units` is None
    k = len(rest) if start is None else start
    while k > 0:
        piece = pieces[rest[k - 1]]
        # a piece the chain joins into a run is a name word: a particle
        # inside the run, or a word the reading does not weigh
        if units is not None and units[rest[k - 1]] != OPENS:
            break
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
            if lean == "credential" or (lean is None and k - 2 >= second):
                k -= 1
                continue
            # #544: or an unambiguous credential stands IN FRONT of it
            # in the same run -- 'John Smith PhD MEng' is a list of
            # degrees, not a family name 'MEng'. Computed once per
            # walk, and only when a member has declined and a suffix
            # piece is in reach, so an ordinary name never pays for
            # it. Still a pick: the fork is reported as a counted
            # member's is.
            #
            # `rest[k - 2:0:-1]` is what stands in front of the member
            # down to, not including, `rest[0]`, the name the reserve
            # keeps, which never anchors (`credential_anchors`). So a
            # member at k == 2 finds nothing in reach. A by-shape member
            # (a lean of None) gets here at k == 2, or, counted in the
            # chain's units (#620), behind a run the chain joins into
            # one word ('Freiherr von Berg G.J.', at k == 3), where
            # what it finds in reach is that run's words.
            # The pass, once built, answers first: asked of every
            # member, the reach test would walk back through the run
            # each time, one look-behind per member.
            if anchors is None and anchor_in_reach(
                    rest[k - 2:0:-1], pieces, ptags, tokens):
                anchors = credential_anchors(rest, pieces, ptags, tokens)
            if anchors is not None and anchors[k - 1]:
                k -= 1
                continue
        break
    return Peel(k, numeral, tuple(picks), anchors)


# rules.md#S2: "A credential after the name core starts a run to the
# end of its part" -- applied to a finished peel (#602), so every
# reader of the trailing run (assign, P5's reserve, P2's chain stop,
# the maiden take) sees one answer.
def run_start(rest: Sequence[int], names: int,
              pieces: Sequence[Sequence[int]],
              ptags: Sequence[Set[str]],
              tokens: Sequence[WorkToken],
              units: Sequence[int] | None = None) -> int:
    """Where #602's run starts in `rest[:names]`: the position of the
    first credential that starts one (`starts_a_credential_run`) with
    two name pieces in front of it, or `names` where none does -- with
    no comma the family has to exist first. A lone particle does not
    count toward the two, 'de Mesnil' being one surname, unless the
    run starts right behind it (#627). The position
    alone, for readers that need only where the name ends
    (`trailing_start`); `credential_run` builds the rest of the answer.

    The tag tests are INLINE ahead of the predicate, so a name word --
    every piece of an ordinary name -- and a connective or particle
    never pay the predicate's frame: this runs on every parse, once
    per piece, and a clause holding a run of links ('Puig i i i ...
    Soler') otherwise paid two frames per link (decisions.md#parse-cost).
    The predicate repeats the refusal; the inline copy is only the
    cheap half of the same question. Under three names no run can
    start, two core pieces having to stand in front of it.

    `units` (`_chain_units`, #620) counts over pieces the chain has not
    joined yet: a word the chain will join to the run in front of it
    is no name word of its own, and a particle opening such a run is
    the one the run makes ('der la', one surname)."""
    if names < 3:
        return names
    core = 0
    lone = False
    for p in range(names):
        q = rest[p]
        tags = tokens[pieces[q][0]].tags
        if (core + lone >= 2 and "vocab:suffix" in tags
                and tags.isdisjoint(_NOT_A_RUN_START)
                and starts_a_credential_run(pieces[q], ptags[q], tokens)):
            return p
        # a lone particle is not yet a name: 'de Mesnil' is one surname
        # -- unless it opens a chain run, which is then the surname
        # (with no `units` every piece opens its own), or the run
        # starts right behind it, leaving it nothing to join: then it
        # is the surname alone, as 'van der' and 'von und zu' are
        # (#627, 'John von PhD Jones')
        if units is None or units[q] == OPENS:
            lone = (len(pieces[q]) == 1 and "particle" in tags
                    and (units is None or q + 1 == len(units)
                         or units[q + 1] == OPENS))
            core += not lone
    return names


# rules.md#P6: "a particle ending the name attaches to that family
# name" -- WHICH particles, asked once, by assign's given-part walk,
# which both leaves them out of #602's run and attaches them (#613;
# #610 had first made the run and post_rules' attachment one walk)
def particle_tail(seg: Sequence[Sequence[int]],
                  tokens: Sequence[WorkToken]) -> tuple[int, int]:
    """`seg[lo:hi]`, the run of wholly-particle pieces P6 attaches: back
    from the end past pieces that hold no name word and are not
    themselves particles -- a post-nominal is written BEHIND the
    particle in this listing -- then back over particle pieces,
    stopping at a lone member of the ambiguous credential class read as
    the credential (#531: the capitals or a degree made it one, so it
    is not the tussenvoegsel).

    The class-member stop keys on the VOCABULARY tag and not on the
    suffix role alone, which is what gives P6's attachment precedence
    over S2: `vd` and `mc` are unambiguous suffix vocabulary, also
    particles, also suffix-roled, and the tag is what keeps them inside
    the run, while the role alone would have stood the attachment down
    for #531's member too ('Doe, John DO' read family 'DO Doe' with the
    condition absent, verified when #531 landed). A trailing piece that
    IS particle vocabulary ends the first walk rather than being looked
    past, since `vd` arrives suffix-roled and is the run.

    Read off ROLES, asked at the moment assign's walk reaches #602's
    run (or, with no run, once the walk has placed every piece; and by
    post_rules' attachment behind an empty family part): every word in front of the run holds the role the walk gave
    it, and the run's words hold none yet -- no name role, and a class
    member not yet read as anything, the run being what will read it
    as the credential. That is why the answer equals the one this
    would give over the finished roles, which is what the attachment
    needs. `lo == hi` where there is no such run.

    The single-token tests are inline (the common piece is one token),
    so the walk pays no frame per piece; it runs on every family-comma
    parse."""
    hi = len(seg)
    while hi > 0:
        piece = seg[hi - 1]
        if (all("particle" in tokens[i].tags for i in piece)
                if len(piece) > 1 else
                "particle" in tokens[piece[0]].tags):
            break
        if (any(tokens[i].role in NAME_ROLES for i in piece)
                if len(piece) > 1 else
                tokens[piece[0]].role in NAME_ROLES):
            break
        hi -= 1
    lo = hi
    while lo > 0:
        piece = seg[lo - 1]
        if len(piece) == 1:
            tok = tokens[piece[0]]
            if "particle" not in tok.tags or (
                    AMBIGUOUS_ACRONYM_TAG in tok.tags
                    and tok.role in SUFFIX_OR_UNREAD):
                break
        elif not all("particle" in tokens[i].tags for i in piece):
            break
        lo -= 1
    return lo, hi


def has_name_content(piece: Sequence[int],
                     tokens: Sequence[WorkToken]) -> bool:
    """Whether a piece holds a letter or digit: a piece with none is
    no name word (rules.md#A2), so a run that takes it in absorbs no
    name and reports nothing. C-level, no frame per character."""
    return any(map(str.isalnum, "".join([tokens[i].text for i in piece])))


def credential_run(rest: Sequence[int], peel: Peel, p: int,
                   pieces: Sequence[Sequence[int]],
                   ptags: Sequence[Set[str]],
                   tokens: Sequence[WorkToken],
                   units: Sequence[int] | None = None) -> Peel:
    """`peel` with its name count cut back to `p`, where #602's run
    starts (`run_start`, which the caller asks first so that a name
    with no run pays one frame, not two).

    Every word from the credential on is then in the suffix run,
    except a title word, which is recorded in `run_titles` for assign
    to read as a title; a name word the run absorbs is recorded in
    `absorbed` for assign to report -- not a word with no letter or
    digit in it, and not a member the peel already reported as a pick.
    One pass, the suffix test first: a credential, the common word in
    a run, leaves both lists without the title test's frame."""
    run_titles: list[int] = []
    absorbed: list[tuple[int, ...]] = []
    r = p + 1
    while r < peel.names:
        q = rest[r]
        # Two or more particles in a row are the one piece P2's chain
        # makes of them wherever they stand, a dual among them ('van
        # mc', 'Mc Mc') no post-nominal of its own: where the chain has
        # run that piece is here already, and S2's read (#620) sees the
        # pieces before it runs, so it gathers the particles its
        # `units` mark BOUND behind the one that opens them. M2's
        # clause-free view reads words before any join and reports them
        # word by word, as it always has.
        e = r + 1
        while (units is not None and e < peel.names
               and units[rest[e]] == BOUND):
            e += 1
        if e > r + 1:
            run: list[int] = []
            for x in rest[r:e]:
                run.extend(pieces[x])
            if has_name_content(run, tokens):
                absorbed.append(tuple(run))
            r = e
            continue
        r += 1
        if is_suffix_piece(pieces[q], ptags[q], tokens):
            continue
        if is_title_piece(pieces[q], ptags[q], tokens):
            run_titles.append(q)
            continue
        piece = tuple(pieces[q])
        if piece not in peel.picks and has_name_content(piece, tokens):
            absorbed.append(piece)
    return Peel(p, peel.numeral, peel.picks, peel.anchors,
                tuple(run_titles), tuple(absorbed))


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
                     tokens: Sequence[WorkToken],
                     end: int | None = None) -> int:
    """How many pieces of `rest` the trailing title chain LEAVES
    standing: `rest[:kept]` are the name pieces and `rest[kept:]` the
    period-marked title words the chain took, in piece order. Counted
    the way `peel_trailing` counts, so the two answers compose without
    arithmetic at the call site. `rest` is the caller's NAME pieces:
    on the no-comma path what the S2 peel left, after a family comma
    the segment's pieces that the segment's own suffix reading does
    not claim, and in `tail_reading` the leftovers of whichever peel
    is current. `end`, where given, reads `rest[:end]` without the
    copy, for `tail_reading`'s passes.
    Floor: the first position of `rest` is never taken, so one name
    piece stands and a name is never all title. An empty
    `rest` returns 0, which is what leaves assign's bare-suffix
    carve-out reached exactly as before.

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
    k = len(rest) if end is None else end
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


# rules.md#H5: "successive single words that wear the abbreviation
# shape and are title vocabulary chain into the title from the end"
# -- one word's half of that, for a caller asking it of a piece the
# chain did not walk to: the maiden take, choosing the words the
# clause-free view is read over (#601). `trailing_titles` asks the same three tests
# INLINE, in the same order, for the frame budget its docstring
# states; keep the two in step.
def is_trailing_title_word(piece: Sequence[int], ptags: Set[str],
                           tokens: Sequence[WorkToken]) -> bool:
    """Whether one piece is a word H5's trailing chain takes: a lone
    token wearing the abbreviation shape that the title vocabulary
    lists. Position is the caller's question -- this answers only
    what the word is."""
    return (len(piece) == 1
            and _PERIOD_ABBREV.match(tokens[piece[0]].text) is not None
            and is_title_piece(piece, ptags, tokens))


#: lone-word tags `trailing_candidates` admits on: the ambiguous class,
#: listed or by shape, and any suffix word -- an initial-shaped one
#: included, which `is_suffix_piece` vetoes and the numeral fork reads
_TRAILING_WORD_TAGS = frozenset({AMBIGUOUS_ACRONYM_TAG, SHAPE_ACRONYM_TAG,
                                 "vocab:suffix"})


# rules.md#M2: "It takes them up to the trailing run of post-nominals
# and titles that the end of the name reads as if the clause were not
# written" -- which words of a clause might be in that run, written
# beside the peel and the chain whose admissions it has to cover (#610)
def trailing_candidates(lo: int, pieces: Sequence[Sequence[int]],
                        ptags: Sequence[Set[str]],
                        tokens: Sequence[WorkToken]) -> int:
    """The first of the pieces after `lo` that `tail_reading` might read
    into the trailing run: `pieces[c:]`, a SUPERSET of what it takes,
    for the maiden take to build its clause-free view over and let
    `tail_reading` decide. `pieces[lo]` itself is never a candidate.

    Back from the end over every piece the peel or the chain admits on
    its own terms -- a suffix piece, a member of the ambiguous class,
    an initial-shaped suffix word, a period-marked title word -- and
    over a roman numeral by the numeral fork's SHAPE test (which asks
    no vocabulary: 'VI' is in no list), where nothing stands behind it
    but such title words and group-flagged suffix pieces: the chain
    takes the titles first and the walk never holds the flagged pieces
    ('Ph. D.'), so either way the numeral is the walk's last piece and
    the fork reads it. Then back to the first
    credential that starts #602's run, whose words the run takes
    whatever they are. A BARE title word is no candidate: H5's chain
    does not take one, and in the view it would only inflate the count
    of words to spare.

    The superset is pinned by tests/v2/pipeline/test_pieces.py over a
    generated grid against `tail_reading` itself, so a new admission
    in the peel or the chain fails there until this covers it."""
    c = len(pieces)
    titles_behind = True
    while c - 1 > lo:
        k = c - 1
        piece = pieces[k]
        title = is_trailing_title_word(piece, ptags[k], tokens)
        if not (title or "suffix" in ptags[k]
                or is_suffix_piece(piece, ptags[k], tokens)
                or (len(piece) == 1 and (
                    not tokens[piece[0]].tags.isdisjoint(_TRAILING_WORD_TAGS)
                    or (titles_behind and is_trailing_numeral_suffix(
                        tokens[piece[0]].text,
                        tokens[pieces[k - 1][0]].text))))):
            break
        # a group-flagged suffix piece is outside the peel's walk
        # altogether (`peel_walk` drops it), so it is behind the
        # numeral the way a chained title is
        titles_behind = titles_behind and (title or "suffix" in ptags[k])
        c = k
    # the tag test is the predicate's own necessary half, inline so a
    # name word pays no frame
    return next((j for j in range(lo + 1, c)
                 if ("suffix" in ptags[j]
                     or "vocab:suffix" in tokens[pieces[j][0]].tags)
                 and starts_a_credential_run(pieces[j], ptags[j], tokens)),
                c)


# rules.md#H5: "the title is TRANSPARENT to the suffix reading: where
# two or more name words stand, what stands once the chain is taken
# reads exactly as it would read written without the title, plus the
# title"
def tail_reading(rest: list[int], pieces: Sequence[Sequence[int]],
                  ptags: Sequence[Set[str]],
                  tokens: Sequence[WorkToken],
                  one_case: bool | None,
                  units: Sequence[int] | None = None,
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
    with suffix 'MA' where 'John Prof. MA' read family 'MA' (written
    in one case today: since #289 capitals in a mixed-case name take
    the acronym whatever the count, so 'john prof. ma prof.' and
    'john prof. ma' are the pair that still reads family 'ma').

    One function for assign's placement, group's bound-given reserve
    (P5), which must count the name words assign will leave, and the
    maiden take (rules.md#M2), which must end the clause where the
    reading of the name will begin -- and since #614, for a main
    segment, the one read group takes between P3's joins and the
    particle chain (`read_trailing_run`), which assign and the reserve
    take their answer from instead. Deriving that agreement twice is what left the two
    disagreeing at S2's bare-ambiguous reserve: 'abdul rahman MA'
    declined the join and 'abdul rahman MA Prof.' took it
    (mechanisms.md#ONE-PREDICATE-PER-QUESTION).

    `rest` is a peel_walk list and is not mutated -- the splice
    rebinds this local -- so a caller's own reference still names the
    walk it built. Every caller reads the one returned here instead,
    which is the one the final peel partitions.

    The chain's floor is `trailing_titles`' own, one name piece left
    standing.

    #602's credential run is applied to the final peel on the way out
    (`credential_run`), so every reader sees the run where it starts.

    Linear in the walk (#558). Re-peeling the whole walk every pass
    re-read each suffix the passes before had already peeled, so a
    name ending 'MA Prof. MA Prof. ...' cost the square of its tail.
    A pass instead RESUMES the walk where the splice left it, over
    `rest` as written: the pieces in front of the splice are the ones
    a fresh walk would meet, and `credential_anchors` reads each
    position off the pieces in front of it, so the carried pass
    answers for them too. What a fresh walk reads differently is the
    position COUNT of the pieces it already peeled, which the splice
    lowers, and two tests of the walk read it. The acronym fork's
    words to spare: a member whose count falls below three can
    decline where it was taken -- 'john prof. ma ma prof.' is exactly
    that, keeping family 'ma' only because the second pass walks
    afresh -- so a pass resumes only with two or more pieces in front
    of the splice, every peeled piece then counting three or more.
    And the numeral fork, which reads the walk's last piece against
    the one before it: a pass resumes only with two or more peeled
    pieces behind the splice, so that pair is the one the first walk
    read. Elsewhere -- a splice near the front of the walk, or before
    two pieces have been peeled -- the pass walks afresh over the
    spliced pieces. The fuzz that checked this against the
    re-peeling loop, the three conditions each shown load-bearing by
    a weakened copy failing it, is recorded on the PR closing #558.
    The splice itself is never materialized in between: the runs are
    collected back to front and joined once.
    """
    # where the second name unit opens, found once for the read: a
    # pass keeps `rest[:hi]`, so it holds while it stands in front of
    # the splice, and each pass rescanning for it from the front cost
    # the square of a run behind a long joined surname (#620's
    # /simplify, 'Freiherr von Berg Berg ... MA Dr. MA Dr. ...')
    second = 1 if units is None else second_unit(rest, units)
    peeled = peel_trailing(rest, pieces, ptags, tokens, one_case,
                           units=units, second=second)
    kept = trailing_titles(rest, pieces, ptags, tokens,
                           end=peeled.names)
    if kept == peeled.names:
        p = run_start(rest, peeled.names, pieces, ptags, tokens, units)
        return rest, (), (peeled if p == peeled.names else credential_run(
            rest, peeled, p, pieces, ptags, tokens, units))
    # `rest[:hi]` stands as written; `behind` holds the peeled runs
    # the splices left after it, and `titled` the chained ones, each
    # back to front -- a pass's run goes in FRONT of what the pass
    # before it took
    hi = len(rest)
    behind: list[list[int]] = []
    behind_count = 0
    titled: list[list[int]] = []
    picks = list(peeled.picks)
    numeral = peeled.numeral
    while kept < peeled.names:
        names = peeled.names
        titled.append(rest[kept:names])
        behind.append(rest[names:hi])
        behind_count += hi - names
        # the walk stopped AT the chain's last title, and a fresh walk
        # will not meet that piece: drop the pick it made there
        if picks and picks[-1] == tuple(pieces[rest[names - 1]]):
            picks.pop()
        hi = kept
        # Counted in units (#620) the position test still answers: a
        # splice lowers a count only by taking out titles that open
        # units of their own, and with fewer than two units in front of
        # it every piece there is in the first piece's chain run, which
        # the titles behind it join -- they count nothing, so nothing
        # the walk peeled loses a word to spare (fuzzed over 372,330
        # names against a units test here: no difference)
        if kept >= 2 and behind_count >= 2:
            peeled = peel_trailing(rest, pieces, ptags, tokens, one_case,
                                   start=hi, anchors=peeled.anchors,
                                   units=units, second=second)
            picks.extend(peeled.picks)
        else:
            rest = rest[:hi] + [j for run in reversed(behind) for j in run]
            if units is not None and second >= hi:
                second = second_unit(rest, units)
            hi = len(rest)
            behind, behind_count = [], 0
            peeled = peel_trailing(rest, pieces, ptags, tokens, one_case,
                                   units=units, second=second)
            picks = list(peeled.picks)
            numeral = peeled.numeral
        kept = trailing_titles(rest, pieces, ptags, tokens,
                               end=peeled.names)
    if behind:
        rest = rest[:hi] + [j for run in reversed(behind) for j in run]
    final = Peel(peeled.names, numeral, tuple(picks), None)
    p = run_start(rest, final.names, pieces, ptags, tokens, units)
    return (rest, tuple(j for run in reversed(titled) for j in run),
            final if p == final.names else credential_run(
                rest, final, p, pieces, ptags, tokens, units))


class TailRead(NamedTuple):
    """S2's trailing run as group reads it ONCE, after P3's connective
    joins and before the particle chain and the bound-given join
    (#614), handed to assign so neither join can move it and assign
    reads no second time -- save where group's joins left no name word
    in front of the run, and assign reads the name again so it keeps
    one ('Prince of Wales Jr'). Token indices rather than piece
    indices, since group's joins renumber the pieces in front of the
    run: `tail` holds every token the run took, `titles` those the H5
    chain took and `run_titles` the title words inside #602's run (both
    inside `tail`), and `peel` the final peel, whose numeral fork, bare
    ambiguous picks and absorbed name words are what assign reports;
    its `names` counts the name pieces as the read left them."""

    tail: frozenset[int]
    titles: frozenset[int]
    run_titles: frozenset[int]
    peel: Peel


# rules.md#P2: "A particle joins the words after it into one name part,
# the join running until the next particle starts a group of its own"
# -- how far, asked by the chain and by S2's read alike (#620), so the
# units the read counts are the ones the chain then builds
def chain_run_end(k: int, pieces: Sequence[Sequence[int]],
                  ptags: Sequence[Set[str]],
                  tokens: Sequence[WorkToken], end: int) -> int:
    """Where the chain run opened by the particle `pieces[k]` ends: past
    the particles straight behind it, then past the name words up to
    `end`, a suffix piece, or the next particle. `pieces[k:j]` is the
    one name unit P2 makes of them; `j == k + 1` where it makes none.

    The particle test is `is_prefix_piece`'s definition written inline:
    the walk runs per piece of every chained name (AGENTS.md's frame
    budget, question 1)."""
    count = len(pieces)
    j = k + 1
    while j < count and ("prefix" in ptags[j]
                         or len(pieces[j]) == 1
                         and "particle" in tokens[pieces[j][0]].tags):
        j += 1
    while (j < end and "prefix" not in ptags[j]
           and not (len(pieces[j]) == 1
                    and "particle" in tokens[pieces[j][0]].tags)
           and not is_suffix_piece(pieces[j], ptags[j], tokens)):
        j += 1
    return j


def _chain_units(pieces: Sequence[Sequence[int]],
                 ptags: Sequence[Set[str]],
                 tokens: Sequence[WorkToken],
                 n: int) -> tuple[list[int] | None, int]:
    """The name units P2's chain will make of `pieces`, as a mark per
    piece -- OPENS where a piece opens a unit, JOINED where the chain
    will join a name word to the run in front of it and the reading
    does not weigh the word (`_weighed`, which keeps a word of its own
    what a position always counted as one), and BOUND for a
    particle inside the run, a word the run took and so a name word
    whatever else it is ('van mc', 'von vd': rules.md#S2, the words
    both particles and suffix vocabulary standing straight behind a
    particle) -- and where the name starts.
    `n` is the end of the leading title run; the chain's leading
    position is the first title that is also a particle ('Freiherr
    von vd', 'St van Mc'), else `n`, and the chain opens no unit there.
    A unit the chain opens INSIDE the titles makes a name of them
    ('Freiherr St van Berg MA', 'Freiherr Freiherr Prof do'), so the
    first unit at or before `n` is where the name starts.

    Nothing is merged: the read counts with the flags and reads every
    piece as written, so no word it weighs is hidden inside a unit
    (#620; the merged copy #614 read through hid a title inside a
    credential run and a shape-only numeral, and its indices drifted
    from the pieces'). None where no particle stands past the first
    piece, every piece then its own unit."""
    count = len(pieces)
    prefix = [("prefix" in ptags[k]
               or len(pieces[k]) == 1
               and "particle" in tokens[pieces[k][0]].tags)
              for k in range(count)]
    if not any(prefix[1:]):
        return None, n
    leading = n
    for k in range(n):
        if prefix[k]:
            leading = k
            break
    units = [OPENS] * count
    at = n
    k = leading + 1
    while k < count:
        if prefix[k]:
            j = chain_run_end(k, pieces, ptags, tokens, count)
            q = k + 1
            while q < j and prefix[q]:
                units[q] = BOUND
                q += 1
            while q < j and not _weighed(pieces[q], tokens):
                units[q] = JOINED
                q += 1
            # a unit with nothing past its opener is no unit the count
            # sees, and makes no name of the titles it opens inside
            if q > k + 1 and k < at:
                at = k
            k = j
            continue
        k += 1
    return units, at


def _weighed(piece: Sequence[int], tokens: Sequence[WorkToken]) -> bool:
    """Whether a word the chain will join is one the trailing reading
    WEIGHS, and so counts as a word of its own, as a position always
    counted it: a suffix word of either kind, the ambiguous class, a
    word in it by shape, an initial, a roman numeral by shape, or a
    period-marked title word. A word the chain joins and the reading
    weighs is a word the reading may yet take ('Freiherr von Berg MA
    X.Y.Z.' keeps suffix 'MA X.Y.Z.'), and one that opens a unit inside
    the titles may leave the titles a title ('St St VI'), so it ends the
    plain run the count folds into the particle (#620's review). A
    connective join is one name word, P3's own count. The tests inline:
    this asks once per word behind a particle run."""
    if len(piece) > 1:
        return False
    tok = tokens[piece[0]]
    return (not tok.tags.isdisjoint(_WEIGHED_TAGS)
            or _ROMAN.match(tok.text) is not None
            or "vocab:title" in tok.tags
            and _PERIOD_ABBREV.match(tok.text) is not None)


_WEIGHED_TAGS = _TRAILING_WORD_TAGS | {"initial"}


def read_trailing_run(pieces: Sequence[Sequence[int]],
                      ptags: Sequence[Set[str]],
                      tokens: Sequence[WorkToken],
                      one_case: bool | None,
                      ) -> tuple[TailRead, int] | None:
    """`tail_reading` read once over a segment's pieces as group holds
    them after rules.md#P3's connective joins and before the particle
    chain (#614), counting name words by the units the chain will make
    (`_chain_units`, #620): a `TailRead`, and the index in `pieces` of
    the first piece of the run, which runs to the end. None where there
    is nothing to read (no name piece past the leading titles), and
    where the run is not one block at the end of `pieces`: a title the
    H5 chain takes standing in front of a name word the peel declined
    ('John Dr. G.J.'), the one shape whose run holds a name piece --
    there group joins as before #614 and assign reads for itself. A
    segment the read takes nothing from reads as a run of no pieces, at
    the end."""
    n = leading_titles(pieces, ptags, tokens)
    if n == len(pieces):
        return None
    units, at = _chain_units(pieces, ptags, tokens, n)
    rest, titled, peel = tail_reading(peel_walk(at, ptags), pieces, ptags,
                                      tokens, one_case, units)
    tail: set[int] = set()
    for k in rest[peel.names:]:
        tail.update(pieces[k])
    titles: set[int] = set()
    for k in titled:
        titles.update(pieces[k])
    tail |= titles
    run_titles: set[int] = set()
    for k in peel.run_titles:
        run_titles.update(pieces[k])
    start = len(pieces)
    for k, piece in enumerate(pieces):
        if piece[0] in tail:
            start = k
            break
    for k in range(start, len(pieces)):
        if pieces[k][0] not in tail and "suffix" not in ptags[k]:
            return None
    return TailRead(frozenset(tail), frozenset(titles),
                    frozenset(run_titles), peel), start


# rules.md#H5: "the title is TRANSPARENT to the suffix reading: where
# two or more name words stand, what stands once the chain is taken
# reads exactly as it would read written without the title, plus the
# title"
def trailing_start_past_titles(start: int,
                                pieces: Sequence[Sequence[int]],
                                ptags: Sequence[Set[str]],
                                tokens: Sequence[WorkToken],
                                *, one_case: bool | None) -> int:
    """`trailing_start` read through H5's chain: where assign's
    trailing suffix run begins once a trailing TITLE has stopped
    hiding it.

    `trailing_start` reads the pieces as WRITTEN, so a title standing
    behind the suffix run makes the peel take nothing and the answer
    is `len(pieces)` -- the reading assign itself has not had since
    H5, because assign runs the peel and the chain to their fixed
    point instead (`tail_reading`). A caller using that answer as the
    right bound of the NAME is told a credential is a name word:
    'John Quincy Adams i MA Prof.' read family 'Adams i MA' where
    'John Quincy Adams i MA' reads family 'Adams' and suffix 'i MA'
    (#397 second review). Every caller that bounds the name wants
    this one; `trailing_start` stays for the callers that count a
    trailing run of the pieces as they stand.

    The returned index bounds the name from the right, and the
    trailing titles the chain spliced out are not under it: they end
    the segment, so they stand at or past the first suffix piece
    whenever there is one. Where the peel takes nothing even past the
    chain this returns `len(pieces)` as `trailing_start` does, and a
    trailing title is then inside the bound and refused by the title
    test the callers already run beside it.
    """
    rest, _titled, peeled = tail_reading(peel_walk(start, ptags),
                                         pieces, ptags, tokens, one_case)
    return rest[peeled.names] if peeled.names < len(rest) else len(pieces)
