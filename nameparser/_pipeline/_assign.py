"""Stage: assign.

Consumes: pieces + piece_tags (grouped), segments, structure, tokens,
one_case, and tail_reads -- rules/S2's trailing run as group read it
once, after P3's joins and before the particle chain (#614), which the
main segment's placement takes rather than peeling again, save where
group's joins left no name word in front of it.
Produces: tokens with roles set on every main-stream token, and the
folded-middle tag on the particles P6's attachment joins to the family
after a family comma (#613).
Reads: Policy.name_order (#270), is_suffix_lenient on the trailing
piece of a two-part comma name, and Policy.script_orders (#271, which
overrides it when every name piece is written wholly in one script, or
in the Han/Hiragana/Katakana repertoire the #272 kana license shares
across pieces); token/piece tags; Lexicon only through tags already
applied by classify (plus the leading-title period rule), and
Lexicon.given_name_titles, which an ambiguity's alternative asks for
rules/P5's given-name-title licence.

Implements rules H2, H4, H5, H6, H7, H8, N3, O4, O5, S10, W4, and P6 after a family comma,
of docs/design/rules/,
each cited at its code below. Ports v1's assignment loops.
NO_COMMA (per name_order):
leading title pieces chain while no given-position name has been seen
(a title needs a following piece, unless the whole name is one title);
then positional assignment per name_order with the trailing-suffix
rule: the piece from which everything after is a strict suffix is the
last name-position piece, the rest are suffixes. Behind that peel a
trailing run of period-marked title words chains into the title from
the end, leaving one name piece standing; where the run TAKES
something the peel was only provisional and runs again over the pieces
with the titled ones spliced out, the two alternating until the run
takes nothing, so a trailing title is transparent to the suffix
reading however many titles are written (_pieces.tail_reading). Where
the run takes nothing -- almost every name -- the first peel is the
only one and its answer stands.
The v1 single-name+nickname rule lives here (decisions/N3): a
nonempty nickname beside exactly one piece in total puts that piece
in FAMILY.
FAMILY_COMMA: segment 0 FAMILY but for a leading run of listed titles
(rules/H6, #701; v1 kept them in the family) and the post-nominals
behind its first family piece (SUFFIX, 'Smith Jr., John'). A part after the
comma that holds no name word, or that a credential opens (#603), is
not read here: group's head binds its SUFFIX and TITLE roles before
any join (`_comma.decide`, #613), making the comma a suffix comma
behind a whole name ('John Smith, Dr.', 'John Smith, PhD Jones') and
leaving the family comma behind one name word ('Smith, Jr.', 'Smith,
PhD Jones'), where segment 1 then reaches this stage with no pieces.
A segment 1 that does reach it gets leading titles, then the same
trailing title run over the pieces this segment does not read as
suffixes ('Smith, John Prof.'), then given, then middles with those
suffix-reading pieces to suffix -- one predicate for both -- and
#602's run after the given word ('Smith, John PhD Jones'); segments 2+
are suffixes but for their title words (#603), lenient -- segment
already flagged the ones that are neither COMMA_STRUCTURE.
SUFFIX_COMMA: segment 0 as NO_COMMA; segment 1 arrives bound by group,
and segments 2+ are read as after a family comma.
Emits PARTICLE_OR_GIVEN when the leading name piece is a lone
particles_ambiguous token with more pieces following ("Van Johnson",
and since #367 "Dr. Van Johnson" too, a title no longer displacing the
particle out of that position) -- whatever role name_order assigns --
and, since #613, at P6's attachment after a family comma where the run
holds an ambiguous particle ("Beethoven, Ludwig van").
Emits SUFFIX_OR_NAME at these sites: the trailing roman numeral, taken
or declined (since #718 for want of words to spare, since #752 for its
Title case), a numeral ending the family part before a family comma,
one of two or more letters ending a given part's walk, each
ambiguous acronym the trailing peel had to resolve, the bare-suffix
carve-out where an input that is nothing but post-nominal vocabulary
gets its first word made into the name (H4's suffix half, #491),
-- since #289 -- the FAMILY-COMMA path's own read of the first
post-comma piece as the given name, -- since #531 -- the class member
ENDING that path's given part, which the first-piece emitter could
never reach, -- since #602 -- each name word the credential run
absorbs, in the no-comma name and in the given part after a family
comma, and -- since #613 -- P6's attachment after a family comma,
where it declines a post-nominal reading or stands down inside a
credential run.
Further emitters of the same kind live in `_comma.py` (called at
group's head: the comma's own decision, #544's anchored members and
#603's absorbed words) and `_group.py`; they are not assign's and are
not counted here. And
at the one site that places a LONE name word, GIVEN_OR_FAMILY for the
field the convention picked (O5, #449) and TITLE_OR_NAME for the two
shapes where the doubt is whether a word is a title instead (H4 and
H7, #491): the peel leaving one title-vocabulary word standing, and a
joined unit carrying title vocabulary.
"""
from __future__ import annotations

from collections.abc import Sequence, Set
from typing import NamedTuple

from nameparser._lexicon import Lexicon, _run_addresses_by_given
from nameparser._pipeline._vocab import (
    _ROMAN, effective_script, in_a_title_phrase, is_initial_shaped,
    PARTICLE_READING, TITLE_READING, is_listed_numeral,
    is_suffix_lenient, name_reading, suffix_reading,
    numeral_leans_to_the_name, numeral_settled_by_case,
    reads_as_a_reported_numeral, reads_as_generation, resolve_script_set,
)
from nameparser._pipeline._pieces import (
    split_credential_report,
    anchor_in_reach, credential_at_the_given_slot, given_slot_anchors,
    _NOT_A_RUN_START, has_name_content, is_lone_never_given_particle,
    Peel, TailRead, is_suffix_piece, is_title_piece, leading_titles,
    particle_tail, listed_lean, peel_walk, settled_by_case,
    starts_a_credential_run,
    tail_reading, trailing_titles,
)
from nameparser._pipeline._state import (
    AMBIGUOUS_ACRONYM_TAG, NAME_ROLES, TITLE_AMBIGUOUS_TAG, ParseState,
    Beside, Deferred, PendingAmbiguity, PendingReading, Structure,
    WorkToken, _AMBIGUOUS_CREDENTIAL_TAGS, _NEVER_FLIPPED, copy_with,
)
from nameparser._policy import Policy, Script
from nameparser._types import (FOLDED_TAG, SHAPE_ACRONYM_TAG, AmbiguityKind,
                               ReadingKind, ReadingSource, Role)

def _set_roles(tokens: list[WorkToken], piece: tuple[int, ...],
               role: Role) -> None:
    for i in piece:
        tokens[i] = copy_with(tokens[i], role=role)


def _name_pieces(state: ParseState, tokens: Sequence[WorkToken],
                 seg_idx: int) -> list[tuple[int, ...]]:
    """The pieces of segment `seg_idx` the parse read as name words."""
    return [q for q in state.pieces[seg_idx]
            if tokens[q[0]].role in NAME_ROLES]


def _slot_field(state: ParseState, seg_idx: int, pos: int, count: int,
                order: tuple[Role, Role, Role] | None) -> Role:
    """The field position `pos` of `count` name words takes in segment
    `seg_idx`, every other word read as the parse read it: the family
    before a family comma, the given part's given or middle name after
    one, and otherwise the order the main segment's read set."""
    if state.structure is Structure.FAMILY_COMMA:
        return (Role.FAMILY if seg_idx == 0
                else Role.GIVEN if pos == 0 else Role.MIDDLE)
    assert order is not None  # the main segment's read sets it
    return _name_positions(order, count)[pos]


def _name_alt(token: WorkToken, role: Role,
              front: Sequence[int] | None, tokens: Sequence[WorkToken],
              first: bool, licensed: bool) -> PendingReading:
    """The name reading of a word read as something else, landing in
    `role` unless the name piece `front` it stands behind would take it
    in, so that it lands where that piece lands: a particle chain runs
    to the end of the part's name words (rules/P2), and a lone particle
    stands unchained only for want of a word behind it, unless it opens
    the part, where it never chains (rules/P4); and a bound given name
    opening the part joins the word after it where it is `licensed`, a
    family comma having fixed the family or a given-name title standing
    ahead (rules/P5),
    since the word would otherwise be the family word the join
    reserves; and a never-given particle opening the part folds it into
    the family (rules/P1). The front's field is named at
    assemble, where P6 may since have attached it to the family, which
    it would not have done with a word behind it (`Beside`)."""
    alt = name_reading(token, role)
    if front is None:
        return alt
    tags = tokens[front[0]].tags
    # rules/P1's fold: a never-given particle opening the part takes the
    # word behind it into the family, whatever the order and the part
    if first and is_lone_never_given_particle(front, tokens):
        return copy_with(alt, role=Role.FAMILY)
    # a piece opening the part with a bound given name is P5's join,
    # not a chain, though `abu` is a particle too: the word stands apart
    bound = first and "vocab:bound-given" in tags
    if ("particle" in tags and (len(front) > 1 or not first) and not bound
            or licensed and bound and len(front) == 1):
        # a front P6 has already attached held `role`'s field before it
        return copy_with(alt, role=Beside(
            front[0], role if FOLDED_TAG in tags else tokens[front[0]].role))
    return alt


def _absorbed(piece: Sequence[int], tokens: Sequence[WorkToken],
              alt: PendingReading | None) -> PendingAmbiguity:
    """rules/S8's report for a name word #602's run absorbs, one
    spelling for the no-comma and the given-part run. `alt` is its
    name reading, whose field the caller's positional read knows (None
    where the caller fills it in once it does)."""
    text = " ".join(tokens[i].text for i in piece)
    return PendingAmbiguity(
        AmbiguityKind.SUFFIX_OR_NAME,
        f"{text!r} follows a credential, so it reads as part of the "
        f"suffix run; it may be a name word", tuple(piece),
        alternative=alt)


#: Tags that say the word's own reading was claimed before position
#: could speak, so O5's convention decided nothing. Built from M4's
#: `_NEVER_FLIPPED` pair rather than respelling it: the two sets answer
#: different questions -- may M4 retag the word, and did anything
#: decide the field -- and share the pair because a word vocabulary
#: claimed as a given name, or wrote as an initial, answers both. The
#: third, `particle`, is here alone because a lone particle's reading
#: is P4's. None is a predicate this emitter owns: they are read off
#: the tags classify already recorded (mechanisms.md#TWO-LAYER-ASSIGN).
_WORD_ALREADY_CLAIMED = _NEVER_FLIPPED | frozenset({"particle"})


# rules/H2: "an abbreviation opening the part of the name that
# carries the given name — the whole name, or the part after a
# family comma — reads as a title even when unlisted" -- the count is
# _pieces.leading_titles since #424 (the chain's leading position is
# read off the same run, _pieces.chain_lead, #624); the roles are set
# here.
def _peel_leading_titles(pieces: tuple[tuple[int, ...], ...],
                         ptags: tuple[frozenset[str], ...],
                         tokens: list[WorkToken],
                         ambiguities: list[PendingAmbiguity] | None,
                         lexicon: Lexicon) -> int:
    """Assign TITLE to the leading title pieces and return the first
    non-title index. `ambiguities` is None where a family comma has
    already marked the part as the given name, so no fork is left to
    report."""
    n = leading_titles(pieces, ptags, tokens)
    for k in range(n):
        _set_roles(tokens, pieces[k], Role.TITLE)
    # rules/H9: "read as a name word where it is the first name word
    # after any titles" -- the peel stops at it because classify read it
    # out of the title, so it is the first piece the peel leaves
    # ('Dean Smith', 'Mr Dean Smith'); and rules/H9: "a word no listed
    # phrase holds is a title only behind a style or a modifier, or
    # before `of`", so standing alone it reports nothing ('Grace Smith')
    if (ambiguities is not None and n < len(pieces) and len(pieces[n]) == 1
            and TITLE_AMBIGUOUS_TAG in tokens[pieces[n][0]].tags
            and "vocab:title" not in tokens[pieces[n][0]].tags
            and in_a_title_phrase(tokens[pieces[n][0]].text, lexicon)):
        i = pieces[n][0]
        ambiguities.append(PendingAmbiguity(
            AmbiguityKind.TITLE_OR_NAME,
            f"{tokens[i].text!r} is a title that may also be a given name, "
            f"and stands in no title phrase; read as ", (i,),
            field_tail=" rather than a title", alternative=TITLE_READING))
    return n


class EffectiveOrder(NamedTuple):
    """What _effective_order made of a name's scripts. `order` is the
    order the positional read uses; `by_script` says a script_orders
    entry RESOLVED it, which is not the same as `order` happening to
    equal the declared name_order -- under a declared family-first
    order a Han name's W4 entry and the declaration agree, and only
    this flag distinguishes the script rule DECIDING the reading from
    the caller's declaration standing unopposed. O5's convention
    report reads it (#449)."""

    order: tuple[Role, Role, Role]
    by_script: bool


# rules/W4: "a name written wholly in one East Asian script, or in
# the kana-licensed Japanese repertoire, reads family-first whatever
# order the caller declared; a wholly-katakana name keeps the declared
# order" (history: decisions/W4)
def _effective_order(policy: Policy,
                     pieces: Sequence[tuple[int, ...]],
                     name_pieces: Sequence[int],
                     tokens: list[WorkToken],
                     *, dot_divided: bool) -> EffectiveOrder:
    """script_orders resolution (#271): when every name piece is
    written wholly in ONE script that has an entry, that script's
    order governs the positional read; anything else -- Latin, mixed
    scripts, no entry -- falls back to name_order. A 间隔号-divided
    name (`dot_divided`, #298) suppresses the whole lookup first: the
    dot marks a transcription -- playing the role pure katakana plays
    in the kana license, orthography naming the convention -- so the
    license yields to name_order. Piece-level, after
    title/suffix peeling: 'Dr. 毛泽东' is a wholly-Han NAME under a
    Latin title. Kana-licensed tokens (高橋みなみ, #272) resolve to
    HIRAGANA the same way a wholly-Han or wholly-Hangul token resolves
    to its own script -- and so does a kana-licensed NAME split across
    separately single-script PIECES ('高橋 みなみ', Han piece plus
    Hiragana piece): resolve_script_set generalizes the license from
    one token's characters to the whole found-script set below, which
    is why Han+Hangul ('毛 김') still declines even though both
    individually read family-first -- the license is specific to the
    Han/Hiragana/Katakana repertoire, not "the entries happen to
    agree".

    Naming note, since the two are easy to conflate: THIS function
    resolves the ORDER for a whole name; `_vocab.effective_script`
    resolves the SCRIPT for a single token. This function calls that
    one per token below.

    Takes the segment's pieces and WHICH of them the name kept, the
    shape every piece-layer predicate takes: a caller holding those
    indices had to build a second list of the same pieces to hand
    over otherwise, which on 3.11 is a comprehension frame on every
    parse (decisions/parse-cost).

    Returns an EffectiveOrder: the order triple, and `by_script` set only on
    the one path where an entry answered. Every fallback below is a
    script rule DECLINING, and reports it as such.
    """
    declared = EffectiveOrder(policy.name_order, by_script=False)
    # #298 transcription marker -- see the docstring; codepoint-scoped
    # (only U+00B7 records; decisions/T3)
    if dot_divided:
        return declared
    if not policy.script_orders:
        return declared
    # Collect every token's script rather than comparing pairwise as
    # tokens are seen: the kana license needs the WHOLE set (a Han
    # piece and a Hiragana piece only license together, never one at a
    # time), so resolution is deferred to resolve_script_set below.
    found: set[Script] = set()
    for piece_idx in name_pieces:
        for i in pieces[piece_idx]:
            script = effective_script(tokens[i].text)
            if script is None:
                # Latin, mixed, or a script with no entry: never a key
                return declared
            found.add(script)
    resolved = resolve_script_set(found)
    if resolved is None:
        # e.g. Han+Hangul: two scripts, neither the kana license's
        # Han/Hiragana/Katakana repertoire -- no single tradition
        return declared
    for script, order in policy.script_orders:
        if script is resolved:
            return EffectiveOrder(order, by_script=True)
    # the resolved script has no entry: the declaration stands, and
    # nothing about the writing system decided the reading
    return declared


# rules/O4: "words no vocabulary has claimed read by position. In
# the default given-first order the first name word is the given name,
# the last is the family name, and everything between is middle names"
def _name_positions(order: tuple[Role, Role, Role],
                    count: int) -> list[Role]:
    """Roles for `count` name pieces (titles/suffixes already peeled),
    per name_order. GIVEN_FIRST: given, middles..., family.
    FAMILY_FIRST: family, given, middles... FAMILY_FIRST_GIVEN_LAST:
    family, middles..., given. One piece takes order[0]'s role; two
    pieces take order[0] and the other primary."""
    first, second = order[0], order[1]
    # rules/O5: "a name of one name word that nothing else has
    # decided reads that word as the given name under the default
    # given-first order, and as the family name under a declared
    # family-first one" -- a convention, not a determination: O4 has
    # no positions to compare at one word, so this line is where the
    # library picks one of two equally consistent readings and picks
    # it the same way every time. The rules that DO decide such a
    # name (H1, N3, M4) run after this and retag.
    if count == 1:
        return [first]
    if first is Role.GIVEN:                      # GIVEN_FIRST
        return ([Role.GIVEN] + [Role.MIDDLE] * (count - 2)
                + [Role.FAMILY])
    if second is Role.GIVEN:                     # FAMILY_FIRST
        return ([Role.FAMILY, Role.GIVEN]
                + [Role.MIDDLE] * (count - 2))
    return ([Role.FAMILY] + [Role.MIDDLE] * (count - 2)   # F_F_GIVEN_LAST
            + [Role.GIVEN])


def _placed(read: TailRead, rest: list[int],
            pieces: tuple[tuple[int, ...], ...],
            ) -> tuple[list[int], tuple[int, ...], Peel]:
    """`tail_reading`'s three answers, taken off the run group read at
    its head (#614) rather than read again over the joined pieces: the
    walk with the name pieces first and the run's suffixes after them,
    the pieces the H5 chain took, and the read's peel with `names` and
    `run_titles` renumbered onto these pieces. Group split the run off
    before its joins and put it back after them unchanged, so each of
    its pieces is whole here and a membership test on its first token
    places it."""
    names: list[int] = []
    suffixes: list[int] = []
    titled: list[int] = []
    run_titles: list[int] = []
    for k in rest:
        first = pieces[k][0]
        if first not in read.tail:
            names.append(k)
        elif first in read.titles:
            titled.append(k)
        else:
            suffixes.append(k)
            if first in read.run_titles:
                run_titles.append(k)
    peel = read.peel
    count = len(names)
    names.extend(suffixes)
    # built, not `_replace`d: that is two frames on every read
    return names, tuple(titled), Peel(
        count, peel.numerals, peel.picks, peel.anchors, tuple(run_titles),
        peel.absorbed)


def _assign_main(seg_idx: int, state: ParseState,
                 tokens: list[WorkToken],
                 ambiguities: list[PendingAmbiguity],
                 ) -> tuple[Role, Role, Role] | None:
    """Returns the order the positional read used, for ParseState.order
    -- None on every path that returns before resolving one."""
    pieces = state.pieces[seg_idx]
    ptags = state.piece_tags[seg_idx]
    n = _peel_leading_titles(pieces, ptags, tokens, ambiguities,
                             state.lexicon)
    if n == len(pieces):
        return None
    # group-flagged suffix pieces (the ph-d merge) are suffixes at ANY
    # position -- v1's fix_phd extracted the credential from the string
    # before parsing, so position never mattered (PR review I3).
    # Walked rather than collected first: the list was never read
    # again, and on 3.11 a comprehension is a frame of its own, which
    # is one frame back against the one the H5 reading below costs. A
    # 3.11 FACT and not a portable one: PEP 709 inlines comprehensions
    # from 3.12, where this tree's reference parse costs 395 written
    # either way (measured 2026-09-09, against 416 and 417 on 3.11).
    # 3.11 is the interpreter the band is quoted for, so 3.11 is what
    # the shape is chosen on (decisions/parse-cost).
    for k in range(n, len(pieces)):
        if "suffix" in ptags[k]:
            _set_roles(tokens, pieces[k], Role.SUFFIX)
    rest = peel_walk(n, ptags)
    if not rest:
        return None
    # rules/N3: "a name that is only a nickname and one name word
    # reads that word as the family name" (history: decisions/N3)
    # -- v1's p_len == 1 counted
    # the WHOLE segment before any title peeling -- 'Xyz. (Bud) Smith'
    # has two pieces, so the title peel wins and this rule declines;
    # H1 then names Smith the family (rules/N3's title bullet)
    # The nickname scan sits LAST in the test: it is a generator, which
    # every interpreter resumes once per token (seven call events on
    # the reference name), and only a one-piece segment ever reads its
    # answer. Hoisting it to the top of the read, where it once stood,
    # is what put 3.12-3.15 one call over the band (decisions/parse-cost).
    if (len(pieces) == 1 and len(rest) == 1
            and any(t.role is Role.NICKNAME for t in tokens)):
        _set_roles(tokens, pieces[rest[0]], Role.FAMILY)
        return None
    # rules/S2's trailing peel and rules/H5's title chain, read
    # together to their fixed point by _pieces.tail_reading -- one
    # function since the /simplify round, shared with the bound-given
    # reserve (P5), which must count the name words this leaves.
    #
    # rules/H5: "successive single words that wear the abbreviation
    # shape and are title vocabulary chain into the title from the end,
    # leaving one name word standing" -- the titles are set BEFORE
    # _name_positions, so the shortened list is what the positional
    # read and the script test both see (a trailing Latin title must
    # not make a wholly-CJK name look mixed-script, the same reason the
    # leading peel runs first). Read ahead of the bare-suffix carve-out
    # because with no name piece left there is nothing for the chain to
    # read: its floor keeps 0 pieces of an empty list, so the branch
    # below is reached exactly as before.
    #
    # Every bare ambiguous acronym the FINAL peel had to resolve is one
    # coin-flip each, in either direction, so the report collects
    # rather than overwrites. Deferred to after assignment because what
    # a pick is declined as depends on the role it took, and which role
    # "not peeled" means depends on name_order; the field itself is
    # worded by assemble (#626). (The roman-numeral fork's TAKEN branch
    # needs no such deferral and is reported here; its declined branch
    # is a pick, #718, and is reported with the others.)
    #
    # Read once in group, after P3's connective joins and ahead of the
    # particle chain, on a main segment of three or more pieces whose
    # run is one block at its end (#614): the run is placed off that
    # reading. Where the read left name pieces and
    # group's joins then left none past the leading titles -- a join
    # that made the name a title ('Freiherr von Berg Dr. and Ed.
    # Prof.') -- the reading is taken here over what stands, as it was
    # taken everywhere before #614, so the name keeps a word. The same
    # procedure and not always the same answer: the run group read
    # split off was kept out of group's joins, so what stands differs
    # from what stood before #614 (that name read family 'von Berg Dr.
    # and Ed. Prof.' then).
    read = (state.tail_reads[seg_idx]
            if seg_idx < len(state.tail_reads) else None)
    if read is not None:
        placed = _placed(read, rest, pieces)
        if read.peel.names and not placed[2].names:
            read = None
        else:
            rest, titled_tail, peeled = placed
    if read is None:
        rest, titled_tail, peeled = tail_reading(rest, pieces, ptags, tokens,
                                                 state.one_case)
    for piece_idx in titled_tail:
        _set_roles(tokens, pieces[piece_idx], Role.TITLE)
    # rules/S8: "except a title word, which reads as a title" -- the
    # credential run (#602) is placed here, so a name word it absorbed
    # is reported here too
    for piece_idx in peeled.run_titles:
        _set_roles(tokens, pieces[piece_idx], Role.TITLE)
    # the name reading of a word the run or the numeral fork took lands
    # where one more name word after the name's would: its field is
    # filled in below, once the positional read has an order
    trailing_alts = len(ambiguities)
    for piece in peeled.absorbed:
        ambiguities.append(_absorbed(piece, tokens, None))
    for numeral in peeled.numerals:
        # a single letter is a name part unless it happens to be a
        # roman numeral -- and V/X/I are ordinary middle initials, so
        # taking it as a suffix is a call, not a fact; a numeral read
        # by its shape alone is in no wordlist, and may be a name word
        text = tokens[numeral[0]].text
        ambiguities.append(PendingAmbiguity(
            AmbiguityKind.SUFFIX_OR_NAME,
            f"{text!r} is a roman numeral, so it reads as a "
            f"generational suffix; "
            + ("any other single letter there would be a middle initial"
               if len(text.rstrip(".")) == 1
               else "it may be a name word"),
            numeral))
    name_pieces, suffix_pieces = rest[:peeled.names], rest[peeled.names:]
    if peeled.run_titles:
        suffix_pieces = [q for q in suffix_pieces
                         if q not in peeled.run_titles]
    if peeled.names == 0:
        # everything suffix-shaped after titles: first one is the name
        name_pieces, suffix_pieces = suffix_pieces[:1], suffix_pieces[1:]
    # AFTER the whole tail reading, and load-bearing: the script test
    # sees the NAME pieces only, so a Latin title or suffix ('Dr. 毛
    # 泽东', '毛 泽东, PhD') cannot make a wholly-CJK name look
    # mixed-script.
    resolved = _effective_order(state.policy, pieces, name_pieces, tokens,
                                dot_divided=bool(state.interpunct_offsets))
    order = resolved.order
    roles = _name_positions(order, len(name_pieces))
    for pos, piece_idx in enumerate(name_pieces):
        _set_roles(tokens, pieces[piece_idx], roles[pos])
    for piece_idx in suffix_pieces:
        _set_roles(tokens, pieces[piece_idx], Role.SUFFIX)

    def as_a_name(i: int) -> PendingReading:
        # every other word read as the parse reads it -- the carve-out's
        # name word too -- the name word the reading declines would be
        # the last of one more than the name's; asked per report, so a
        # name that makes no report here pays nothing
        front = (pieces[name_pieces[-1]] if name_pieces
                 and i not in pieces[name_pieces[-1]] else None)
        # rules/P5's other licence, a given-name title ahead, asked of
        # the leading run through the predicate group's join asks, so
        # the two cannot disagree about what one run asserts; asked
        # only where the bound branch could take it, so a report per
        # word of a long run never walks the name (the scaling test)
        licensed = (front is not None and len(name_pieces) == 1
                    and "vocab:bound-given" in tokens[front[0]].tags
                    and _run_addresses_by_given(
                        (tokens[j].text for k in range(name_pieces[0])
                         for j in pieces[k]),
                        state.lexicon.given_name_titles))
        return _name_alt(tokens[i],
                         _slot_field(state, seg_idx, len(name_pieces),
                                     len(name_pieces) + 1, order),
                         front, tokens, len(name_pieces) == 1, licensed)

    for r in range(trailing_alts, len(ambiguities)):
        report = ambiguities[r]
        ambiguities[r] = copy_with(
            report, alternative=as_a_name(report.indices[0]))
    # Both emitters below turn on the PEEL's count, so neither can
    # reach a name that kept two name pieces, and the two scans are
    # nested under the count rather than run beside it: they cost the
    # call budget on every parse otherwise (decisions/parse-cost).
    if peeled.names <= 1:
        head = pieces[name_pieces[0]]
        # Both conventions here turn on a lone name word, so both
        # report at the site that places one
        # (mechanisms.md#AMBIGUITY-AT-THE-DECISION-SITE), and one
        # predicate carries what says nothing else decided the FIELD:
        # a title (segment 0's own peel, or one a family comma left in
        # the next segment -- either is a Role.TITLE by now, and
        # either makes the reading H1's), a maiden name (M4's), or a
        # script order convention. `resolved.by_script` rather than a
        # comparison against name_order: a declared family-first order
        # agreeing with a Han name's entry is agreement, not
        # authorship, and for a lone CJK honorific ('さん', '씨') it
        # scopes W2's reading out rather than excusing it (#271/#308).
        titled = any(t.role is Role.TITLE for t in tokens)
        field_undecided = (
            not resolved.by_script and not titled
            and not any(t.role is Role.MAIDEN for t in tokens))
        # rules/H4: "an input whose every word is post-nominal
        # vocabulary reads its first word as a name and reports
        # `suffix-or-name`" (history: decisions/H4) -- only the
        # word made into a name reports, and no name piece survived
        # the peel, so the carve-out above made the first post-nominal
        # the name. Its field is worded by assemble from the final role
        # (`PendingAmbiguity.field_tail`, #626).
        if peeled.names == 0 and field_undecided:
            text = " ".join(tokens[i].text for i in head)
            ambiguities.append(PendingAmbiguity(
                AmbiguityKind.SUFFIX_OR_NAME,
                f"{text!r} is post-nominal vocabulary with no name word "
                f"beside it; read as ", tuple(head),
                field_tail=" rather than a post-nominal, nothing else "
                           "being left to be the name",
                alternative=suffix_reading(tokens[head[0]])))
        # One name piece off the peel: the convention placed a lone
        # name word. A suffix beside it is not a decision -- 'Smith
        # Jr.' and "'Smitty' Jones Jr." ARE this convention -- and the
        # count comes off the peel rather than off name_pieces, which
        # is what keeps the carve-out above out of these branches.
        # Title vocabulary in the unit makes the doubt H4's or H7's (is
        # the WORD a title), anything else O5's (which FIELD it took),
        # so only the second reads `field_undecided`.
        if peeled.names == 1 and not resolved.by_script:
            # rules/H4: "an input whose only remaining name word
            # after the title peel is itself title vocabulary reads
            # that word as the name by convention and reports
            # `title-or-name`" (history: decisions/H4), and
            # rules/H7: "one name UNIT of more than one word carrying
            # title vocabulary reports `title-or-name`" (history:
            # decisions/H7, decisions/H4 #518) -- one branch, its detail
            # naming a field only in H7's shape ('John of Bishop',
            # 'Attorney General of Minnesota'), where the unit is more
            # than the title word.
            # A LONE title word never reaches here ('Dr.', 'Prince of
            # Wales'): the leading-title peel took the whole name.
            if any("vocab:title" in tokens[i].tags for i in head):
                text = " ".join(tokens[i].text for i in head)
                lone = len(head) == 1
                ambiguities.append(PendingAmbiguity(
                    AmbiguityKind.TITLE_OR_NAME,
                    f"{text!r} is title vocabulary and the only name word "
                    f"the title peel left standing; read as the name by "
                    f"convention rather than as more title"
                    if lone else
                    f"{text!r} is the only name unit and joins title "
                    f"vocabulary to a name word; read as ",
                    tuple(head),
                    field_tail=None if lone else " by convention",
                    alternative=TITLE_READING))
            # rules/O5: "a name of one name word that nothing else has
            # decided reads that word as the given name under the default
            # given-first order, and as the family name under a declared
            # family-first one" (history: decisions/O5). Past
            # `field_undecided`, two clauses of O5's own: the word's
            # own reading may have claimed it, and A2's content test
            # -- a piece with no alphanumeric character is no name
            # word, so parse("(") keeps its unbalanced-delimiter
            # report and gains nothing here.
            elif (field_undecided
                    and all(tokens[i].tags.isdisjoint(_WORD_ALREADY_CLAIMED)
                            for i in head)
                    and any(c.isalnum() for i in head
                            for c in tokens[i].text)):
                text = " ".join(tokens[i].text for i in head)
                ambiguities.append(PendingAmbiguity(
                    AmbiguityKind.GIVEN_OR_FAMILY,
                    f"{text!r} is the only name word and nothing else "
                    f"decides it; read as ", tuple(head),
                    field_tail=" by convention, which follows the read "
                               "order",
                    # the other primary field, named from the final
                    # role by assemble
                    alternative=PendingReading(ReadingKind.NAME,
                                               ReadingSource.POSITION,
                                               Deferred.OTHER_PRIMARY)))
    # rules/S10: "a one-letter numeral before a credential is the
    # family name, and the reading is reported" -- the part's last name
    # word with nothing but the trailing run behind it (#721, Derek:
    # 'John Smith V PhD' keeps family 'V' and reports, as 'john i, phd'
    # does). Decided here, where the trailing read has said what that
    # run is
    # `_ROMAN` first, C-level, so an ordinary name word pays no frame
    if (len(name_pieces) >= 2
            and len(last := pieces[name_pieces[-1]]) == 1
            and _ROMAN.match((word := tokens[last[0]].text).rstrip("."))
            is not None
            # the trailing run, or the Ph./D. pair, which the walk
            # leaves out, behind it
            and (suffix_pieces or titled_tail
                 or name_pieces[-1] + 1 < len(pieces)
                 and "suffix" in ptags[name_pieces[-1] + 1])
            and tuple(last) not in peeled.picks
            and reads_as_a_reported_numeral(
                word, tokens[last[0]].tags,
                tokens[pieces[name_pieces[-2]][0]].text, state.one_case)):
        ambiguities.append(PendingAmbiguity(
            AmbiguityKind.SUFFIX_OR_NAME,
            f"{word!r} is a roman numeral, but a post-nominal or title "
            f"follows it; read as ", tuple(last),
            field_tail=" rather than a generational suffix",
            alternative=suffix_reading(tokens[last[0]])))
    for piece in peeled.picks:
        # every pick is in rest, so the loops above just gave it a
        # role; whether it was read as a suffix or a name settles what
        # it was declined as, and which field assemble names (#626)
        token = tokens[piece[0]]
        assert token.role is not None
        # rules/S10: "either reading is reported" -- the numeral fork's
        # declined pick (#718), which carries neither credential tag
        # (the acronym fork's picks carry one) and is never a suffix
        if token.tags.isdisjoint(_AMBIGUOUS_CREDENTIAL_TAGS):
            # a pick a credential run in front then took is the run's
            # absorbed name word (rules/S8); otherwise it is declined
            # for want of words to spare (one letter) or for its Title
            # case (two or more, rules/S10's lean)
            if token.role is Role.SUFFIX:
                ambiguities.append(_absorbed(piece, tokens,
                                             as_a_name(piece[0])))
                continue
            why = ("is a roman numeral, but the name has no other word "
                   "to spare for it" if len(token.text.rstrip(".")) == 1
                   else "is a roman numeral written in Title case, which "
                        "leans to the name")
            ambiguities.append(PendingAmbiguity(
                AmbiguityKind.SUFFIX_OR_NAME,
                f"{token.text!r} {why}; read as ", piece,
                field_tail=" rather than a generational suffix",
                alternative=suffix_reading(token)))
            continue
        declined = ("a name part" if token.role is Role.SUFFIX
                    else "a post-nominal")
        # rules/S9: "An unlisted word joins the ambiguous class (S4) by
        # SHAPE" (and rules/S3); such a word is in no
        # wordlist and may be written with its periods, so the listed
        # member's wording would misdescribe it on both counts (#563)
        what = ("is shaped like a post-nominal but listed in no "
                "vocabulary, so it may be an ordinary name"
                if SHAPE_ACRONYM_TAG in token.tags
                else "written without periods is both a post-nominal "
                     "and an ordinary name")
        ambiguities.append(PendingAmbiguity(
            AmbiguityKind.SUFFIX_OR_NAME,
            f"{token.text!r} {what}; read as ", piece,
            field_tail=f" rather than {declined}",
            alternative=(as_a_name(piece[0])
                         if token.role is Role.SUFFIX
                         else suffix_reading(token))))
    # leading ambiguous particle read as a name (#121 surfaced)
    if name_pieces:
        head = pieces[name_pieces[0]]
        if (len(head) == 1 and len(name_pieces) > 1
                and "vocab:particle-ambiguous" in tokens[head[0]].tags):
            # the field is assemble's to word from the final role
            # (`PendingAmbiguity.field_tail`, #626), never assumed given:
            # `order` above is _effective_order's answer, not
            # necessarily name_order's, and a later rule may still move
            # the word ('Van Ivan Petrovich' under the East Slavic rule
            # rotates 'Van' into the family)
            ambiguities.append(PendingAmbiguity(
                AmbiguityKind.PARTICLE_OR_GIVEN,
                f"leading {tokens[head[0]].text!r} may be a family-name "
                f"particle; read as ", tuple(head), field_tail="",
                alternative=PARTICLE_READING))
    return order


def _family_part_numeral(word: WorkToken, preceding: str, names: int,
                         one_case: bool | None) -> Role | None:
    """The role of a roman numeral ending the family part before a
    family comma, behind `names` pieces of that part, as the comma-less
    name reads one ending it (rules/S10), or None where the numeral's
    predicate reads no numeral there (an initial in front, a letter with
    its period): the suffix where it reads as the generation, a
    one-letter numeral needing two name words in front of it, and the
    family name where that count fails or its Title case leans to the
    name."""
    if reads_as_generation(word.text, word.tags, preceding, one_case):
        if (names < 2 and len(word.text) == 1
                and not numeral_settled_by_case(word.text, one_case)):
            return Role.FAMILY
        return Role.SUFFIX
    if numeral_leans_to_the_name(word.text, word.tags, preceding, one_case):
        return Role.FAMILY
    return None


def _reads_as_a_trailing_suffix(piece: Sequence[int],
                               prev_piece: Sequence[int],
                               prev_ptags: Set[str],
                               tokens: Sequence[WorkToken],
                               lexicon: Lexicon,
                               one_case: bool | None) -> bool:
    """The lenient tail test for a trailing one-token piece after a
    family comma, and #432's carve-out from it.

    A word that could be a middle initial, written with the period that
    marks an abbreviation, is name material -- so 'Smith, John V.' is
    middle 'V.' where 'Smith, John V' stays suffix 'V' (v1 parity,
    #144). Only behind a NAME word: behind a suffix the credential run
    owns it, and 'Smith, John PhD I.' keeps suffix 'PhD, I.'.

    The period is the whole carve-out. is_initial_shaped would be
    redundant beside it: the caller only consults this where
    is_suffix_piece said no, and a lenient single token it refuses is
    one carrying the `initial` tag, so the shape is already implied.

    reads_as_generation is asked with no word in front (`preceding`
    None): its initial-in-front refusal is a no-comma rule and the
    opposite of this path's v1 parity -- 'Chang, Andy C I' is first
    Andy, middle C, suffix I, and asking it with the word in front
    made the numeral a middle. The #401/#421 entry
    under decisions/P5 records the same fork declining to transfer
    to this walk under LENIENT.
    """
    # rules/C9: "behind a name word it is the generation only when
    # written bare, a period marking it the abbreviation of a name and
    # so a middle initial"
    tok = tokens[piece[0]]
    text = tok.text
    if text.endswith(".") and not is_suffix_piece(
            prev_piece, prev_ptags, tokens):
        return False
    # the numeral's predicate, which in this slot reads a bare
    # one-letter numeral by the vocabulary ('Smith, John X' keeps
    # middle 'X'); `_ROMAN` first, C-level
    if len(text) == 1 and _ROMAN.match(text) is not None:
        return reads_as_generation(text, tok.tags, None, one_case)
    return is_suffix_lenient(text, lexicon)


def _inside_a_credential_run(seg: Sequence[Sequence[int]],
                             tokens: list[WorkToken], given_at: int,
                             k: int, end: int,
                             ambiguities: list[PendingAmbiguity]) -> bool:
    """rules/P9 (P6's third exception) for the run `seg[k:end]`: a
    run assign read as post-nominals, with a credential read in
    front of it and another behind, stands INSIDE the credential run
    assign read whole rather than ending the name, so it keeps that
    reading -- 'DOE, JANE PHD VD MA' reads suffix 'PHD VD MA' where the
    attachment had pulled VD out of the middle of it (#573). Behind as
    well as in front: with nothing behind it the word ends the name,
    and 'Doe, Jane PhD vd' keeps family 'vd Doe'. A title between it
    and the post-nominal in front is transparent, as it is to every
    trailing reading (H5): 'DOE, JANE PHD PROF. VD MA' reads as 'DOE,
    JANE PHD VD MA' does. The run is never empty: the caller asks
    only where `k < end`, and over an empty range the test below would
    pass vacuously and report a fork on the word behind (#613's
    review, ', Jane PhD do MA'). (Behind it no title is skipped: a title
    there leaves the word a name in assign, so nothing reaches here.)

    The test is the ROLES assign gave, not S7's company query: the
    question is whether assign read the run whole, and a member in
    front that the writing or a count made the credential ('DOE, JANE
    MA VD PHD') says so as plainly as a degree does. So does a
    generation, in front or behind ('Berg, Jan PhD vd Jr.'): the
    tussenvoegsel P6 is about stands right behind the given name, and
    a post-nominal between them says this word is not one. The run's own
    role is what keeps a plain particle out ('Doe, Jane PhD de PhD',
    whose 'de' is a name word, not a post-nominal), and the given
    name in front is what keeps 'Doe, Jane vd PhD' attaching.
    Reported as S4's credential fork, at the site that declines the
    attachment."""
    def suffix_read(q: int) -> bool:
        return all(tokens[i].role is Role.SUFFIX for i in seg[q])

    def is_title(q: int) -> bool:
        return all(tokens[i].role is Role.TITLE for i in seg[q])

    if not all(suffix_read(q) for q in range(k, end)):
        return False
    front = k - 1
    while front > given_at and is_title(front):
        front -= 1
    if (front <= given_at or end == len(seg)
            or not suffix_read(front) or not suffix_read(end)):
        return False
    run = seg[k]
    text = " ".join(tokens[i].text for i in run)
    ambiguities.append(PendingAmbiguity(
        AmbiguityKind.SUFFIX_OR_NAME,
        f"{text!r} written without periods is both a post-nominal and a "
        f"family-name particle; between credentials after a family "
        f"comma it reads as a post-nominal",
        tuple(run), alternative=PARTICLE_READING))
    return True


def _attach_particle_tail(pieces: Sequence[Sequence[int]],
                          tokens: list[WorkToken], given_at: int,
                          k: int, end: int,
                          ambiguities: list[PendingAmbiguity]) -> None:
    """rules/P6's attachment after a family comma: the particle run
    `pieces[k:end]` ending the given part joins the family the comma
    named and is written before it -- the Dutch alphabetized listing,
    "Beethoven, Ludwig van" being how "Ludwig van Beethoven" is filed.
    The caller has found the run (`particle_tail`) and checked that a
    given word stands ahead of it and that P1's fold will not take the
    part; this declines only where the run stands inside a credential
    run the walk read whole (`_inside_a_credential_run`, the third
    exception).

    Keyed on the tokens' VOCABULARY, not their roles, which is what
    gives the attachment its stated precedence over S2: `vd`, `mc` and
    `do` are the three words in both vocabularies; the walk reads a
    trailing `vd` or `mc` as a post-nominal, so those two need the
    override, and `do` is in the AMBIGUOUS acronym half, which already
    leaves it a name word, so it attaches by the plain rule. After a
    family comma the tussenvoegsel is the commoner reading.

    The words-to-spare guard is a piece test, not a count: every
    trailing piece that is wholly particles attaches, and the run must
    leave a GIVEN word ahead of it, so "Nguyen, Van" keeps its only
    given word. Only the DEGENERATE Vietnamese listing is protected by
    that -- "Nguyen, Thi Van" has a given word to spare, so `Van`
    attaches and the given name is lost. rules/P6 records why that
    is accepted.

    mechanisms.md#FOLDED_TAG does the rest: tokens never move, so the
    family view reads the tag and renders these before the base.

    Decided in assign since #613, in the pass that read the given
    part; until then post_rules took it a stage later, and assign held
    the tail back from #602's run by predicting it."""
    if _inside_a_credential_run(pieces, tokens, given_at, k, end,
                                ambiguities):
        return
    run = [i for piece in pieces[k:end] for i in piece]
    # mechanisms.md#AMBIGUITY-AT-THE-DECISION-SITE: "Emit at
    # the site that takes the branch, not where an ambiguous
    # tag sits" -- this attachment is where the fork is
    # decided, so the report is raised here, at the attachment,
    # rather than by the given-part walk's own emitters, which
    # read the run before the attachment decides it (#405).
    #
    # Two arms, keyed on what the attachment OVERRODE rather
    # than on what the words are, so each names a branch the
    # parse actually weighed. `declined_suffix` reads the role
    # the walk gave the run, which is why both lists are built
    # BEFORE the re-roling loop below overwrites it.
    #
    # ORDERED, not asserted disjoint. The two cannot both hold
    # under the shipped vocabulary -- `vd` and `mc` are the
    # only words in both the particle and the unambiguous
    # suffix vocabularies, and neither is ambiguous particle
    # vocabulary -- but a caller's Lexicon may put one word in
    # both, and rules/A1 says parsing never fails on any
    # input, so this decides instead of raising. (Measured: an
    # assert here DID fire on `Berg, Jan zz` under a Lexicon
    # adding `zz` to particles_ambiguous and suffix_acronyms.)
    # The suffix arm wins because it names the reading the
    # parse actually took: assign had read the word as a
    # post-nominal, so the name-word reading was never on the
    # table for the attachment to decline.
    #
    # Both details name the ATTACHMENT and stop there. What
    # P6 decides is that the run joins the family the comma
    # named instead of standing on its own; how the joined
    # words then READ is R2's call, taken by the UNJOINED_TAG
    # loop at the end of post_rules. The two can disagree:
    # `de la, Jan van` attaches `van` and leaves an
    # all-particle family, which R2 marks, so every other view
    # -- `family_base`, the initials, case repair -- reads
    # those words as ordinary name words ('Jan Van De La'
    # forced). A detail promising "read as the family's
    # particle" would contradict all three.
    ambiguous = [i for i in run
                 if "vocab:particle-ambiguous" in tokens[i].tags]
    declined_suffix = [i for i in run
                       if tokens[i].role is Role.SUFFIX]
    text = " ".join(tokens[i].text for i in run)
    if declined_suffix:
        ambiguities.append(PendingAmbiguity(
            AmbiguityKind.SUFFIX_OR_NAME,
            f"{text!r} written without periods is both a "
            f"post-nominal and a family-name particle; after a "
            f"family comma it joins the family the comma named "
            f"rather than standing as a post-nominal",
            tuple(run), alternative=suffix_reading(tokens[run[0]])))
    elif ambiguous:
        word = tokens[ambiguous[0]].text
        walked = tokens[run[0]].role
        assert walked is not None  # the given part's walk roled the run
        ambiguities.append(PendingAmbiguity(
            AmbiguityKind.PARTICLE_OR_GIVEN,
            f"{word!r} is both a family-name particle and an "
            f"ordinary given name; after a family comma "
            f"{text!r} joins the family the comma named "
            f"rather than standing as a name word of its own",
            tuple(run),
            # where the given part's walk placed it, before this moves
            # it: a name word, or a title the walk read off its period
            # ('Doe, Jane nee Smith St.'); a name word is taken in by
            # the piece in front where that piece would take it
            alternative=(TITLE_READING if tokens[run[0]].role is Role.TITLE
                         else _name_alt(
                             tokens[ambiguous[0]],
                             walked,
                             pieces[k - 1] if k - 1 >= given_at
                             and tokens[pieces[k - 1][0]].role in NAME_ROLES
                             else None,
                             tokens, k - 1 == given_at, True))))
    for i in run:
        tokens[i] = copy_with(
            tokens[i], role=Role.FAMILY,
            tags=tokens[i].tags | {FOLDED_TAG})


def _split_name_alt(state: ParseState, tokens: Sequence[WorkToken],
                    seg_idx: int, piece: Sequence[int],
                    order: tuple[Role, Role, Role] | None) -> PendingReading:
    """The name reading of a split credential assign placed, every
    other word read as the parse read it: the family before a family
    comma, the given part's given or middle name after one, and
    otherwise the last of the part's name words -- or wherever the name
    piece in front of it would take it in (`_name_alt`)."""
    names = [q for q in _name_pieces(state, tokens, seg_idx)
             if q[0] < piece[0]]
    role = _slot_field(state, seg_idx, len(names), len(names) + 1, order)
    return _name_alt(tokens[piece[0]], role, names[-1] if names else None,
                     tokens, len(names) == 1,
                     state.structure is Structure.FAMILY_COMMA)


def _resolve_deferred(state: ParseState, tokens: Sequence[WorkToken],
                      ambiguities: list[PendingAmbiguity],
                      order: tuple[Role, Role, Role] | None) -> None:
    """Name the field of each alternative classify or group deferred,
    from the positions just read: a connective's join takes in the name
    word on each side, so where those stand in two pieces the joined
    unit takes the place of the first, and where both are inside the
    letter's own piece, or the join would leave the name one word, the
    letter keeps its own field (named at assemble); a chained particle
    stands as a name word of its own in front of its piece, one more
    unit. Every other word keeps its reading, so the field is
    the one the positional read gives that place: the family before a
    family comma, the given part's given or middle name after one, and
    the declared order's otherwise. A referent outside every name
    position is left deferred, and surfaces as no alternative."""
    for r, report in enumerate(ambiguities):
        alt = report.alternative
        if (alt is None or alt.role not in (Deferred.JOINED,
                                            Deferred.UNCHAINED)
                or not report.indices):
            continue
        i = report.indices[0]
        for seg_idx in range(len(state.pieces)):
            names = _name_pieces(state, tokens, seg_idx)
            at = next((k for k, q in enumerate(names) if i in q), None)
            if at is not None:
                break
        else:
            continue
        if alt.role is Deferred.UNCHAINED:
            pos, count = at, len(names) + 1
        else:
            # the join takes in the name word on each side: a word of
            # the connective's own piece, or the piece beside it. One
            # inside its piece joins nothing the piece did not hold, so
            # it lands where its piece lands; one opening or ending the
            # name has no word to join on that side, and no field
            piece = names[at]
            k = piece.index(i)
            first = at - 1 if k == 0 else at
            last = at + 1 if k == len(piece) - 1 else at
            if first < 0 or last >= len(names):
                continue
            pos, count = first, len(names) - (last - first)
            # rules/P3: "a single-letter connective in a three-word name"
            # stays a name word, so a join that would leave the name one
            # word is no join, and the letter keeps its own field; a
            # family comma's surname is a word of the name the given
            # part's count does not see
            if first == last or (
                    count == 1
                    and state.structure is not Structure.FAMILY_COMMA):
                ambiguities[r] = copy_with(report, alternative=copy_with(
                    alt, role=Beside(i)))
                continue
        ambiguities[r] = copy_with(report, alternative=copy_with(
            alt, role=_slot_field(state, seg_idx, pos, count, order)))


def assign(state: ParseState) -> ParseState:
    tokens = list(state.tokens)
    ambiguities = list(state.ambiguities)
    if not state.segments:
        return state
    order: tuple[Role, Role, Role] | None = None
    if state.structure is Structure.NO_COMMA:
        order = _assign_main(0, state, tokens, ambiguities)
        tail = len(state.segments)
    elif state.structure is Structure.SUFFIX_COMMA:
        order = _assign_main(0, state, tokens, ambiguities)
        tail = 1
    else:  # FAMILY_COMMA
        # PARTICLE_OR_GIVEN is deliberately not emitted on the
        # wholly-family read: after a comma that fixed the family, a
        # leading given-position particle is not meaningfully
        # ambiguous, and script_orders is not consulted for the parallel
        # reason. Scoped, not silent: the comma fixed WHICH PIECE is the
        # family and said nothing about a particle trailing the given
        # name, so P6's attachment after the given-part walk below
        # decides that fork and reports it there, at the site that
        # takes the branch (#405). Behind a whole name, a comma followed
        # by no name word is not this path since #613: `_comma.decide`
        # makes it the suffix comma, read positionally by the branch
        # above, which emits and consults both as the comma-less name
        # does -- and group's chain emitter with them, the comma being
        # decided before the chain runs. Behind one name word it is
        # this path, with segment 1 already bound ('Smith, Jr.').
        # v1: "lastname part may have suffixes in it" -- the first
        # piece is always the family even if suffix-shaped; any later
        # strict-suffix piece goes to SUFFIX per piece ('Smith Jr.,
        # John' -> family=Smith, suffix=Jr.)
        fam_pieces = state.pieces[0]
        fam_tags = state.piece_tags[0]
        # The part after the comma reaches here as the given part, or
        # bound and with no pieces left: group's `_comma.decide` binds a
        # postnominal one before any join (#613, rules/C7), so this
        # path is the listing form's, and the positional read #296 gave
        # a comma followed by no name word behind two name words is
        # decide's suffix comma now, read by the NO_COMMA branch above.
        # rules/C11's report, scoped to the ambiguous credential
        # class: this is the given-name half of the comma's OWN
        # decision (listing or credential run), where the writing left
        # the fork open. `_comma.decide` reports the credential half,
        # where it binds the part, and P6's attachment fork reports
        # from `_attach_particle_tail` above ("Berg, Jan vd") -- a
        # different fork. Each half is reported where its branch is
        # taken, so this DECISION is never reported twice; a second ambiguous
        # token elsewhere in the name is a second fork and reports on
        # its own (#289, mechanisms.md#AMBIGUITY-AT-THE-DECISION-SITE).
        #
        # The report tracks the FORK BEING CONSULTED, not the lean --
        # exactly as the trailing slot has always done (`Jack MA`
        # reported before #289 too, even where the pick was declined
        # for want of words to spare). So membership alone gates it:
        # a caseless script or an all-lower spelling still called this
        # fork and read it positionally.
        #
        # The gate reads EITHER tag (`_AMBIGUOUS_CREDENTIAL_TAGS`, the
        # same pair `_group`'s chain emitter asks), and the shape one
        # is what reaches a by-shape member -- under EITHER 2.4
        # switch, the dotted and the caps alike, since classify writes
        # it from both branches. It reaches one with the dotted switch
        # OFF as well: classify writes the shape tag whether or not
        # the switch admits the token to the class, which is what lets
        # a declined fork be REPORTED without being taken ('Smith,
        # A.B.' under `unlisted_dotted_suffixes=False` reports and
        # keeps its given). An earlier wording said the class reaches
        # a by-shape member "once `Policy.unlisted_dotted_suffixes`
        # admits it", which is true of the CLASS and false of this
        # report.
        #
        # Read off the FIRST post-comma piece only -- on this path it
        # is the given name, `_comma.decide` having read the part and
        # found a name word in it, and it is the one piece the lean
        # can reach at one word before the comma. So `"Smith, MA PhD"` reports ONCE, for 'MA' alone:
        # 'PhD' is settled vocabulary and carries neither tag, and
        # even a second CLASS member there would not be read here
        # (test_assign.py asserts the count).
        #
        # The #531 emitter at the far end of this branch counts
        # differently, and the difference is the slot rather than a
        # second policy: it reports once per member of the trailing
        # run it reads, so 'Doe, John MA JD' reports TWICE, matching
        # the comma-less 'John Smith MA JD'. A member the writing
        # keeps as a name stops that run, which is why
        # 'Doe, John MA Ma' reports once and for 'Ma' alone -- 'MA'
        # then has a name word behind it and is never asked
        # (rules/S5).
        if state.pieces[1] and len(state.pieces[1][0]) == 1:
            i = state.pieces[1][0][0]
            if not tokens[i].tags.isdisjoint(_AMBIGUOUS_CREDENTIAL_TAGS):
                # the field is assemble's to word: with nothing before
                # the comma and a title after the word, H1 moves it to
                # the family (', Ma Dr.', #626's review)
                ambiguities.append(PendingAmbiguity(
                    AmbiguityKind.SUFFIX_OR_NAME,
                    f"{tokens[i].text!r} after the comma is also an "
                    f"ordinary name word; read as ", (i,), field_tail="",
                    # the comma's other branch: the part a credential run
                    alternative=suffix_reading(tokens[i])))
        # Segment 1 is read before segment 0's family pass. It
        # consumes piece tags and text only -- nothing segment 0's
        # read writes. (A title standing after the comma behind a whole
        # name, 'John V, Dr.', is bound at group's head since #613 and
        # never reaches this path.)
        if len(state.segments) > 1:
            pieces = state.pieces[1]
            ptags = state.piece_tags[1]
            # Both are the walk's, filled once the title run is found.
            titled_idx: frozenset[int] = frozenset()
            walkable: frozenset[int] = frozenset()
            #: Where the trailing suffix run starts, for the #531
            #: report below: `trailing_floor`'s answer, read once on
            #: the first member the loop meets and -1 until then (no
            #: piece index can be negative, and the loop's own floor is
            #: n + 1). Once is enough for the same reason one number is
            #: enough inside that walk: the question is MONOTONE, the
            #: loop below ascends, and a later member can only ask for
            #: LESS of the walk than the first one did.
            run_floor = -1

            def previous_kept(m: int, titled: frozenset[int]) -> int:
                """The piece before `m` that the H5 chain did NOT
                take. Both readings this segment needs are that one:
                the piece the lenient tail test measures against, and
                -- asked of one past the end -- where the segment's
                name ENDS, since a title the chain took is not where a
                name ends (#144). One walk for both, so 'as if the
                titled pieces were absent' cannot come to mean two
                things.

                DEFENSIVE, and measured inert: over 191,146 generated
                inputs the skip fired on 153 of the 140,227 walks the
                lenient test's `prev` asked for, and deleting it
                changed no parse among them (2026-09-09, on the shape
                this replaced, where the name's END walked past the
                same pieces in a copy of this loop). Kept because "as
                if the titled pieces were absent" is the rule the
                predicate below implements, and a caller's vocabulary
                reaches shapes the sweep's word list does not -- an
                inert branch is cheaper than a rule with a hole in it.
                """
                m -= 1
                while m in titled:
                    m -= 1
                return m

            #: State of the #531 walk below, per `titled` value: how
            #: far down the trailing suffix run has been walked, and
            #: whether that walk has SETTLED (it stopped on a piece
            #: that refuses, so no lower piece can end the given part
            #: either and the refusal is never re-asked).
            #:
            #: The key carries `titled` for the same reason the
            #: predicate takes it as a parameter: the two passes ask
            #: about the same pieces with different ones spliced out.
            #: It CANNOT go stale. Everything the recorded verdict
            #: rests on is tags and text -- `is_suffix_piece` reads
            #: ptags and token tags, `_reads_as_a_trailing_suffix`
            #: reads text plus `is_suffix_piece`, `listed_lean` reads
            #: tags, text and `state.one_case` -- and none of them
            #: reads `.role`, verified by reading all three
            #: (2026-09-19). The one thing this segment's code rewrites
            #: between the two passes is the role, through `_set_roles`,
            #: which is a `copy_with(role=...)` and leaves
            #: text and tags identical.
            floors: dict[frozenset[int], tuple[int, bool]] = {}
            #: #544's anchors, per `titled` value like `floors` and for
            #: the same reason: `given_slot_anchors` over the pieces the
            #: chain kept, computed once, the first time a member's own
            #: writing declines, so a run of members is read in one
            #: forward pass rather than one look-behind per member.
            anchor_memo: dict[frozenset[int], list[bool]] = {}

            def anchored(m: int, titled: frozenset[int]) -> bool:
                memo = anchor_memo.get(titled)
                if memo is None:
                    # nothing in front the pass could read as an
                    # anchor: the ordinary 'Smith, John Ma' stops here.
                    # Asked only before the pass exists -- once it
                    # does it answers in one lookup, where the reach
                    # test walks back through the run
                    if not anchor_in_reach(range(m - 1, -1, -1), pieces,
                                           ptags, tokens, titled):
                        return False
                    # from past the leading title run, which `n` already
                    # counts: this closure is reached only from the walk
                    # below `_peel_leading_titles` sets it on
                    memo = given_slot_anchors(pieces, ptags, tokens, n,
                                              skip=titled)
                    anchor_memo[titled] = memo
                return memo[m]

            def trailing_floor(m: int, titled: frozenset[int]) -> int:
                """Where the trailing suffix run starts, walked as far
                down as `m` needs it: `m >= trailing_floor(m, titled)`
                is exactly "every kept piece behind `m` reads as a
                suffix", which is what ENDING the given part means
                (rules/S5, #531).

                ONE walk per `titled` value, shared by the predicate
                below and by that rule's report at the foot of this
                segment, and the reason both are LINEAR in the run's
                length. The question is MONOTONE -- a piece ends the
                given part whenever the piece behind it does -- so a
                single descent answers for every member, each piece
                read at most once. Asked member by member instead, the
                reading is recursive (a member ends the given part iff
                everything kept behind it reads as a suffix, and a
                piece behind it is a member asking the same of its own
                tail): a walk per member, which cost O(run**2) with the
                per-member memo this replaced and 2**run without one.
                Measured on `'Doe, John ' + 'MA '*k`, k doubling from
                200: 2.1/4.1/8.3/17.1ms here, against 8.6/31.4/120/463
                with the memo and 1.5/3.2/7.2/17.3 at cc78c960, where
                no such walk existed at all (2026-09-19).

                `low` descends only to `m`, so what comes back is a
                floor FOR `m` rather than the run's own first piece
                whenever the run reaches past it; that is all either
                caller asks, and stopping there is what keeps the
                member's own frame count where it was. `final` carries
                the other half: a piece that refuses settles the floor
                for everything in front of it.

                Re-entrant by construction, and it has to be: the
                descent asks the predicate below about a piece that is
                itself often a member, which asks this back. `floors`
                names the piece under test BEFORE that call, so the
                re-entrant reading is "this piece ends the given part",
                which is what the descent has just established of it.
                """
                entry = floors.get(titled)
                if entry is None:
                    # previous_kept() of one past the end, spelled out
                    # here rather than called: the frame budget again,
                    # this walk being asked of every family-comma name
                    # with a member in the given part, and the skip is
                    # two lines. Keep the two in step.
                    low = len(pieces) - 1
                    while low in titled:
                        low -= 1
                    entry = (low, False)
                    floors[titled] = entry
                low, final = entry
                while not final and low > m:
                    if reads_as_a_suffix(low, titled):
                        low -= 1
                        while low in titled:
                            low -= 1
                    else:
                        final = True
                    floors[titled] = (low, final)
                return low

            #: where the particle run opening the given part ends,
            #: per `titled` value -- `attaches_the_lead`'s one walk
            lead_run_ends: dict[frozenset[int], int] = {}

            def attaches_the_lead(m: int, titled: frozenset[int]) -> bool:
                """Is piece `m` the name word a never-given particle
                opening the given part attaches to? post_rules' P1
                fold takes such a particle forward into the family and
                needs a name word for it to attach to, so the given
                name the #531 slot below counts on is not there, and
                the first word past the particle run is the surname it
                heads rather than a word to spare ('SMITH, VD MA'
                reads as 'Smith, vd Ma' does, #573). Only where the
                member's writing says nothing: capitals in a mixed-case
                name still make it the credential ('Smith, de MA'
                keeps suffix 'MA'), as they do with no words to spare
                anywhere (rules/S5). Asked only of a class member
                the slot would otherwise take."""
                if not is_lone_never_given_particle(pieces[n], tokens):
                    return False
                if listed_lean(tokens[pieces[m][0]],
                               state.one_case) == "credential":
                    return False
                # The member is the particle run's word when it is the
                # first kept piece past that run. Where the run ends is
                # one answer per `titled` value, walked once and kept,
                # so a run of members costs one walk rather than one
                # each (the second review measured the per-member scan
                # quadratic on 'SMITH, VD ' + 'DE '*k + 'MA '*k). Every
                # token, not the piece's tags: a chain of particles
                # ('DE LA') is one piece whose tags say nothing of it
                # ('SMITH, VD DE LA MA').
                run_end = lead_run_ends.get(titled)
                if run_end is None:
                    run_end = n + 1
                    while run_end < len(pieces) and (
                            run_end in titled
                            or all("particle" in tokens[i].tags
                                   for i in pieces[run_end])):
                        run_end += 1
                    lead_run_ends[titled] = run_end
                return m <= run_end

            def reads_as_a_suffix(m: int, titled: frozenset[int]) -> bool:
                """Does this segment's walk read piece `m` as a suffix?

                Asked twice, and by one predicate rather than by two
                conditions written to match
                (mechanisms.md#ONE-PREDICATE-PER-QUESTION): once to
                find the pieces the H5 title chain must not reach
                past, and once by the walk order below, which is the
                site that places them.

                `titled` is a PARAMETER because the two passes hand it
                different values -- an empty set on the first, the
                chain's own pieces on the second, which is what makes
                that second reading the one 'as if the titled pieces
                were absent'.
                A closure over the caller's local said the same thing,
                but only by WHEN it was rebound.
                """
                if is_suffix_piece(pieces[m], ptags[m], tokens):
                    return True
                # rules/S10: "A numeral of two or more letters reads as
                # the generation" in the given part, which asks no
                # initial in front -- 'Smith, John VI' as 'Smith, John
                # III' (#752); `_ROMAN` first, C-level
                if (len(pieces[m]) == 1
                        and len(stem := (tok := tokens[pieces[m][0]]).text
                                .rstrip(".")) >= 2
                        and _ROMAN.match(stem) is not None):
                    return reads_as_generation(tok.text, tok.tags, None,
                                               state.one_case)
                # rules/S5: "a word that ENDS that part reads as the credential
                # unless its WRITING says otherwise" -- the given part's
                # trailing slot (#531).
                # INLINE, and that is the frame budget talking rather
                # than taste: the candidates pass asks this closure once
                # per piece of every family-comma segment, so a helper
                # call would cost a frame on every non-member piece and
                # a generator expression would cost its own on 3.11.
                # Membership is therefore a bare `in` on tags already
                # in hand, after a `len` -- 'Doe, John Q.' and
                # 'Smith, John V' measure +0 with this shape and +1
                # with a helper (2026-09-18).
                #
                # That "once per piece" is the NON-MEMBER cost, and
                # only it. A member is asked a second time by
                # trailing_floor()'s descent above, and twice is the
                # whole of it: the descent takes each piece once and
                # the candidates pass asks each piece once, which is what
                # makes the run linear. What the slot costs, measured
                # against cc78c960: 'Smith, John', 'Doe, John Q.',
                # 'Smith, John V', 'Smith, MA' and 'Berg, Jan vd' are
                # all +0 frames, while 'Doe, John MA' is +6 and 'Doe,
                # John MA PhD' +23 -- the member's descent, its lean,
                # and the report below (2026-09-19).
                #
                # The comma has already named the family and the first
                # piece after it is the given name, so the words to
                # spare S4's count asks about are there by
                # construction and the count says nothing at this
                # slot. What is left is the writing, which is the same
                # evidence the comma-less spelling of the same name
                # reads. #144's two-segment restriction below is NOT
                # inherited: it exists because a trailing 'V' before a
                # third comma part is likely a middle initial, and a
                # class member is not initial-shaped while a
                # credential list behind it makes the credential
                # reading likelier rather than less.
                piece = pieces[m]
                # rules/S12: a split credential reads "as a member of the
                # ambiguous class", here read as the class is with no
                # writing to lean on and in silence, as group merges it
                # only behind the given word
                if len(piece) == 2 and "split" in ptags[m]:
                    return (m >= trailing_floor(m, titled)
                            and not attaches_the_lead(m, titled))
                if len(piece) == 1:
                    tok = tokens[piece[0]]
                    if AMBIGUOUS_ACRONYM_TAG in tok.tags:
                        # 'ending the given part' reaches past the
                        # credentials behind it and past a trailing
                        # title, which trailing_floor() skips the way
                        # previous_kept() does -- so 'Doe, John MA
                        # Prof.' and 'Doe, John Prof. MA' land on one
                        # answer without a second notion of trailing.
                        # A name word behind the member ends the
                        # reach, and the member is an ordinary middle
                        # name read in silence.
                        if (m >= trailing_floor(m, titled)
                                and not attaches_the_lead(m, titled)):
                            # A member that is ALSO particle
                            # vocabulary reads as the credential only
                            # on a POSITIVE credential lean: P6's
                            # attachment outranks this reading in
                            # every other spelling, and 'Doe, John do'
                            # leans nothing, so the positional reading
                            # would take it -- the wrong answer there,
                            # not merely a stray report
                            # (decisions/S5, 2026-09-18).
                            #
                            # A FUNCTION since #533 rather than a
                            # condition written here (mechanisms.md
                            # #ONE-PREDICATE-PER-QUESTION). The call
                            # costs one frame PER MEMBER asked at this
                            # slot, not one per name: against
                            # 2f57ff21, 'Doe, John MA' is 310 -> 311
                            # and 'Doe, John MA Ma MA', which asks
                            # four times, 439 -> 443, while a name
                            # with no member here never reaches it
                            # ('Smith, John' 206, 'MA JD' 185, both
                            # unchanged). Measured 2026-09-19 per
                            # `Parser.parse`; Derek took that trade
                            # deliberately.
                            # #544: an unambiguous credential in front
                            # of it in the same run anchors it -- asked
                            # through a thunk, so only a member the
                            # writing declines pays for the pass
                            if credential_at_the_given_slot(
                                    tok, state.one_case,
                                    lambda: anchored(m, titled)):
                                return True
                prev = previous_kept(m, titled)
                # trailing piece of a two-part name is unambiguously
                # positioned: v1 accepts the lenient test there
                # ('Smith, John V' -> suffix='V', #144); with a third
                # comma part the trailing token is more likely a middle
                # initial, so strict only
                return (m == previous_kept(len(pieces), titled)
                        and len(state.segments) == 2
                        and len(pieces[m]) == 1
                        and _reads_as_a_trailing_suffix(
                            pieces[m], pieces[prev], ptags[prev],
                            tokens, state.lexicon, state.one_case))

            # rules/C1: "anything else after the comma means the
            # listing form" -- and this walk reads it. A segment of no
            # name word never reaches here: it is `_comma.decide`'s, read piece by piece and bound at
            # group's head (#613, rules/C8), the suffix verdict
            # before the title reading of the same word (#296, #325).
            # A name word in the segment makes it v1's walk ('Smith,
            # John Jr.').
            # rules/H9: "no comma has marked the given name" -- here the
            # family comma has, so the peel reports nothing
            n = _peel_leading_titles(pieces, ptags, tokens, None,
                                     state.lexicon)
            # rules/H5: "the title is TRANSPARENT to the suffix
            # reading: where two or more name words stand, what
            # stands once the chain is taken reads exactly as it
            # would read written without the title, plus the title"
            # -- the trailing title run, on this walk
            # too. A name word in segment 1 is what keeps
            # `_comma.decide` from reading the segment as the
            # postnominal part, so 'Smith, John Prof.' had no route
            # to title at all and read middle 'Prof.' at every
            # baseline; the 'Smith, Dr.' family of rows are decide's
            # doing, a different mechanism.
            #
            # The candidates are the pieces this walk would NOT
            # read as a suffix, which is this path's answer to the
            # peel the no-comma path runs first -- 'Smith, John
            # Prof. Jr.' must reach `Prof.` past the postnominal
            # behind it, and 'Smith, John Prof. V' past the
            # numeral the lenient tail test claims (#144), which
            # is why the filter is the walk's own predicate and
            # not the strict suffix test alone. Piece `n` is
            # always the given below, whatever that predicate
            # would say of it, so it is always a candidate. That
            # `k == n` is LOAD-BEARING, not defensive: it is what
            # the walk's floor stands on when the given piece
            # itself reads as a suffix, and dropping it leaves
            # 'Smith, II Mr. V' a middle 'Mr.' where the title is
            # (24 inputs of that shape move, of 191,146 generated,
            # measured 2026-09-09).
            #
            # `candidates` is the ORDER, which `trailing_titles` and
            # its slice read; everything after asks MEMBERSHIP,
            # once per piece, and a list or tuple answers that by
            # scanning, so the walk was quadratic in the part's
            # length (#553). Hence the two sets. A tuple keying
            # `floors` or `anchor_memo` above would also re-hash
            # its whole length at every lookup, where a frozenset
            # caches its hash.
            candidates = [k for k in range(n, len(pieces))
                          if k == n
                          or not reads_as_a_suffix(k, frozenset())]
            # rules/H8: "the word joins the title field, and the given
            # part reads as it would without it" -- a bare salutation
            # chains here as a period-marked title does
            kept = trailing_titles(candidates, pieces, ptags, tokens,
                                   salutations=True)
            walkable = frozenset(candidates)
            titled_idx = frozenset(candidates[kept:])
            for k in titled_idx:
                _set_roles(tokens, pieces[k], Role.TITLE)
            # v1 walk order: the first non-title piece is ALWAYS the
            # given, before any suffix check -- 'Smith, V. Jones' keeps
            # first='V.'. Two 2.x deviations are `_comma.decide`'s
            # reading now (#613), so the walk here never meets
            # either: a last piece
            # that is unambiguously suffix-shaped is a suffix, where v1
            # made it the given ('Andrews, M.D.', 'Smith, Dr. Jr.';
            # classified fix(comma-family)), a segment whose only
            # non-title piece is a suffix piece holding no name word;
            # and a credential opening the segment makes it the
            # postnominal part whatever follows ('Hardman, RN - CRNA'
            # kept first='RN' until #603).
            if n < len(pieces):
                _set_roles(tokens, pieces[n], Role.GIVEN)
            # The chain's floor leaves a name piece standing, so the
            # given above is never one of the pieces it took. What the
            # chain DOES move is where this segment's name ends, which
            # the lenient tail test turns on (#144) -- so where it took
            # something the question is re-asked with the pieces it
            # left. Where it took nothing, `walkable` already IS this
            # predicate's answer for every piece: the first pass's own
            # memo, not a second spelling of the question, and it
            # cannot have gone stale because nothing the chain does
            # moved the end of the name.
            # rules/S8: "or after the given word in the part after a
            # family comma" -- the given part's own credential run
            # (#602), the comma having fixed the family. The tag tests are inline ahead of the
            # predicate, as in `_pieces.credential_run`, so a name word
            # pays no frame: this loop runs on every family-comma name.
            sticky_from = len(pieces)
            for m in range(n + 1, len(pieces)):
                tags = tokens[pieces[m][0]].tags
                if (m not in titled_idx
                        and ("suffix" in ptags[m] or "split" in ptags[m]
                             or (("vocab:suffix" in tags
                                  or AMBIGUOUS_ACRONYM_TAG in tags
                                  or _ROMAN.match(tokens[pieces[m][0]].text
                                                  .rstrip(".")) is not None)
                                 and tags.isdisjoint(_NOT_A_RUN_START)))
                        and starts_a_credential_run(pieces[m], ptags[m],
                                                    tokens, None,
                                                    state.one_case)):
                    sticky_from = m
                    break
            # rules/P6: "a particle ending the name attaches to that
            # family name" -- decided here, in the pass that reads the
            # given part, rather than predicted for post_rules to take
            # a stage later (#613). The tail is `pieces[k6:end6]`, found
            # by `particle_tail` ONCE, at the moment the walk reaches
            # #602's run (or, with no run, once the walk has placed
            # every piece): the pieces in front of the run hold the roles
            # this walk gave them and the run's own words hold none
            # yet, which is the state in which the walk's answer equals
            # the one it would give over the finished roles -- the run
            # reads every word it keeps as a suffix or a title, neither
            # a name role, and a class member in it as the credential,
            # where the walk's #531 stop wants it. The tail's words are
            # left to the walk, not the run: absorbing them reported a
            # suffix reading the attachment then overrode ('Smith, John
            # PhD de', 'Smith, John PhD de Jr.'). A particle the walk
            # does not end on -- one with a credential behind it and
            # another particle past that, 'Smith, John PhD de PhD van'
            # -- stays in the run, as does a lone member of the
            # ambiguous credential class (`do`), which the run reads as
            # the credential.
            k6 = end6 = len(pieces)

            def as_a_middle(m: int, token: WorkToken) -> PendingReading:
                # the name reading of a word the walk read as a suffix:
                # a middle name, or taken in by the name word in front
                front = pieces[m - 1]
                return _name_alt(
                    token, Role.MIDDLE,
                    front if tokens[front[0]].role in NAME_ROLES else None,
                    tokens, m - 1 == n, True)

            for m in range(n + 1, len(pieces)):
                if m == sticky_from:
                    k6, end6 = particle_tail(pieces, tokens)
                if m in titled_idx:
                    continue
                suffix_here = (reads_as_a_suffix(m, titled_idx)
                               if titled_idx else m not in walkable)
                # rules/S10: "A numeral read by its shape alone reports
                # too" -- one of two or more letters the walk reads as
                # the generation; `_ROMAN` first, C-level
                if (suffix_here and len(pieces[m]) == 1
                        and len(stem := (tok := tokens[pieces[m][0]]).text
                                .rstrip(".")) >= 2
                        and _ROMAN.match(stem) is not None
                        and not is_listed_numeral(tok.text, tok.tags)
                        and not numeral_settled_by_case(tok.text,
                                                        state.one_case)):
                    ambiguities.append(PendingAmbiguity(
                        AmbiguityKind.SUFFIX_OR_NAME,
                        f"{tok.text!r} is a roman numeral, so it reads as "
                        f"a generational suffix; it may be a name word",
                        (pieces[m][0],),
                        # a name word the walk keeps past the given
                        # name is a middle one
                        alternative=as_a_middle(m, tok)))
                # rules/C9: "a lone letter ending the given part ahead of
                # a further comma is the middle initial, whatever stands
                # before it" -- the further comma has named the suffix,
                # so the credential run in front stops short of it
                # (#819); `len` first, C-level
                if (m > sticky_from and len(state.segments) > 2
                        and len(pieces[m]) == 1
                        and len(tokens[pieces[m][0]].text.rstrip(".")) == 1
                        and m == previous_kept(len(pieces), titled_idx)
                        and is_initial_shaped(
                            tokens[pieces[m][0]].text.upper())):
                    _set_roles(tokens, pieces[m], Role.MIDDLE)
                    continue
                if m >= sticky_from and not k6 <= m < end6:
                    # inside the run: a title word reads as a title,
                    # every other word as a suffix, and a word the walk
                    # would have kept as a name is reported, here where
                    # the run absorbs it
                    if (m > sticky_from
                            and not is_suffix_piece(pieces[m], ptags[m],
                                                    tokens)
                            and is_title_piece(pieces[m], ptags[m],
                                               tokens)):
                        _set_roles(tokens, pieces[m], Role.TITLE)
                        continue
                    piece = pieces[m]
                    if (len(piece) == 1
                            and not tokens[piece[0]].tags.isdisjoint(
                                _AMBIGUOUS_CREDENTIAL_TAGS)):
                        # a class member inside the run is still the
                        # fork #531's report names, now read as the
                        # credential, as #544's anchor reads one --
                        # unless its capitals settled it (rules/S6)
                        if not settled_by_case(tokens[piece[0]],
                                               state.one_case):
                            ambiguities.append(PendingAmbiguity(
                                AmbiguityKind.SUFFIX_OR_NAME,
                                f"{tokens[piece[0]].text!r} ending the given "
                                f"part is also an ordinary name word; read "
                                f"as a credential", (piece[0],),
                                alternative=as_a_middle(
                                    m, tokens[piece[0]])))
                    # the run's own first word is the credential that
                    # starts it, a split one ('Pharm D') included
                    elif (not suffix_here and m != sticky_from
                          and has_name_content(piece, tokens)):
                        ambiguities.append(
                            _absorbed(piece, tokens,
                                      as_a_middle(m, tokens[piece[0]])))
                    _set_roles(tokens, piece, Role.SUFFIX)
                    continue
                _set_roles(tokens, pieces[m],
                           Role.SUFFIX if suffix_here else Role.MIDDLE)
                # #531's report, one of this module's SUFFIX_OR_NAME
                # sites (the header lists them). The gate reads EITHER tag, as the
                # first-post-comma emitter's does: classify writes the
                # shape tag whether or not the dotted switch admits
                # the token, which is what lets a declined fork be
                # reported without being taken.
                #
                # The report tracks the FORK CONSULTED, not the lean
                # (#289's rule), so a member the writing kept as a
                # name reports too -- 'Doe, John Ma' stays a middle
                # name and says so. It reports only in the TRAILING
                # RUN: with a name word behind it no fork was
                # consulted, and AGENTS.md's "a kind is worth adding
                # only if a reader would hesitate too" is why that
                # must stay silent rather than why it happens to (the
                # sentence is the 2.0-conventions section's, not
                # rules/A1's, which this cited until 2026-09-19).
                #
                # The `do` carve-out is a REPORT carve-out on top of
                # the reading one above: a particle-tagged member this
                # walk did not itself take is P6's fork, and P6
                # reports it in its own kind, which is
                # mechanisms.md#AMBIGUITY-AT-THE-DECISION-SITE read
                # strictly. Without it 'Doe, John do' reported both
                # kinds.
                piece = pieces[m]
                if (len(piece) == 1
                        and not tokens[piece[0]].tags.isdisjoint(
                            _AMBIGUOUS_CREDENTIAL_TAGS)
                        and (suffix_here
                             or "particle" not in tokens[piece[0]].tags)
                        # rules/S6: "a clash settled by the writing is
                        # not reported"
                        and not (suffix_here and settled_by_case(
                            tokens[piece[0]], state.one_case))):
                    # The SAME floor the predicate measures members
                    # against, so this report has no walk of its own to
                    # regress: it had one, and on a run the predicate's
                    # memo had already made quadratic the report was
                    # CUBIC, because its per-member walk re-scanned
                    # `walkable` -- a list -- at every step. Measured
                    # then on `'Doe, ' + 'John '*r + 'MA '*r`, r
                    # doubling from 100: 5.8/28/175/1229ms, 4.9x then
                    # 6.2x then 7.0x per doubling and heading for the
                    # 8x a cubic gives, against 1.8/3.7/8.0ms here
                    # (2026-09-19). Nothing guarded it: the scan was a
                    # C-level `in` over a list and emitted no frame, so
                    # the frame-ratio test in tests/v2/test_benchmark.py
                    # was structurally blind to it, and the clock-based
                    # shapes beside it repeat ONE unit where this cost
                    # needs a name holding two runs (`_PREFIXED_SHAPES`
                    # adds a prefix but still repeats one run, so it
                    # does not reach this either). What keeps it gone
                    # is the structure: one walk, read by both callers,
                    # so a second would have to be written on purpose.
                    #
                    # Read once for the whole loop, `run_floor` being
                    # where the FIRST member's walk stopped and the
                    # floor for every later member too: if the walk
                    # reached that member, nothing behind it refuses
                    # and no later member can be refused either; if it
                    # stopped short, it stopped at the LAST piece that
                    # refuses, which is exactly what a later member's
                    # own walk would have found (2026-09-19).
                    if run_floor < 0:
                        run_floor = trailing_floor(m, titled_idx)
                    if m >= run_floor:
                        i2 = piece[0]
                        ambiguities.append(PendingAmbiguity(
                            AmbiguityKind.SUFFIX_OR_NAME,
                            f"{tokens[i2].text!r} ending the given "
                            f"part is also an ordinary name word; "
                            f"read as "
                            f"{'a credential' if suffix_here else 'a name'}",
                            (i2,),
                            alternative=(
                                as_a_middle(m, tokens[i2])
                                if suffix_here
                                else suffix_reading(tokens[i2]))))
            if sticky_from == len(pieces):
                k6, end6 = particle_tail(pieces, tokens)
            # Behind every family comma, one with nothing before it
            # too, which then makes the particle the whole family
            # (', Dr. Jones vd'; decisions/C15, #892). GIVEN ahead of
            # the tail -- rules/P6: "at least one given word must
            # remain" -- the given is piece `n`, so a tail starting
            # there leaves none ('Nguyen, Van').
            # And not where a never-given particle opens the part: P1's
            # fold takes every given and middle word into the family in
            # post_rules, so no given word remains for this one either
            # ('Smith, de Mesnil van' keeps 'van' where the fold puts
            # it, not hoisted in front of 'Smith', the 2026-08-18
            # defect); with no name word behind it to fold, the tail
            # stays the suffix, behind an empty head as behind its twin
            # (', de PhD vd' as 'Smith, de PhD vd', #892).
            if (n < k6 < end6
                    and not is_lone_never_given_particle(pieces[n],
                                                         tokens)):
                _attach_particle_tail(pieces, tokens, n, k6, end6,
                                      ambiguities)
        # rules/H6: "A run of title words opening the part before a
        # family comma is the title" -- by vocabulary only, never H2's
        # shape, leaving one piece for the family, and stopping at a
        # word that is a particle too ('St Pierre', 'Freiherr von
        # Berg'), or where everything behind it is post-nominal, which
        # leaves no family word to address -- H3's concern, by a
        # stricter test than H3's one-word give-back, so this is not
        # `leading_titles` ('RA PhD Jr., John' keeps family 'RA', where
        # 'RA PhD Jr. John' reads title 'RA'). A dual is a title wherever
        # a name word follows it ('Rev. Sr. Smith, Mary').
        # `is_title_piece` is H5's vocabulary read, so the two slots that
        # refuse the shape agree on what a title word is.
        lead = 0
        floor = len(fam_pieces)
        # the length test and the tag test first, both C-level: a part
        # no title opens ('Smith, John', 'Smith Jones, John') pays no
        # frame. The tags are the two arms `is_title_piece` answers yes
        # from, so the predicate stays the one that answers
        if (floor > 1
                and ("title" in fam_tags[0]
                     or "vocab:title" in tokens[fam_pieces[0][0]].tags)
                and is_title_piece(fam_pieces[0], fam_tags[0], tokens)):
            # where the trailing post-nominal run starts: walked once,
            # and only for a part a title opens
            while floor > 1 and is_suffix_piece(fam_pieces[floor - 1],
                                                fam_tags[floor - 1],
                                                tokens):
                floor -= 1
            # the first piece is a title, asked above
            while (lead + 1 < floor
                   and (lead == 0 or is_title_piece(
                       fam_pieces[lead], fam_tags[lead], tokens))
                   and "particle" not in tokens[fam_pieces[lead][0]].tags):
                _set_roles(tokens, fam_pieces[lead], Role.TITLE)
                lead += 1
        # rules/P9: "a particle that is also suffix vocabulary heads
        # the name word behind it" -- with a name piece behind it in
        # this part (vd, mc), it heads that name, as P2's join does,
        # and is not peeled from between two family words
        # (#573: 'SMITH VD MA, JOHN', where the uniform case left the
        # chain stopped before VD; 'SMITH VD JR, JOHN', a suffix word
        # behind it, keeps suffix 'VD JR'). Read here because only
        # this family pass needs it: a comma followed by no name
        # word behind a whole name is group's suffix comma since #613,
        # and the NO_COMMA read takes segment 0, trailing run and all
        # ('Berg de MA, Prof.'). The first piece the title run leaves
        # is the family's first and is family whatever it is, as piece
        # 0 is with no title ('Dr. PhD Smith, John' as 'PhD Smith, John').
        # A piece at or past the floor is already known to be a suffix
        # with nothing but suffixes behind it, so it is not asked again.
        for k in range(lead, len(fam_pieces)):
            piece = fam_pieces[k]
            if k >= floor:
                _set_roles(tokens, piece, Role.SUFFIX)
            # rules/C1: "a numeral ending the family part is read as the
            # comma-less name reads it" -- the numeral's predicate, a
            # one-letter numeral with two name words in front of it
            # (rules/S10), so 'John Smith V, M.J.' keeps suffix 'V' as
            # 'John Smith III, M.J.' keeps 'III' (#774). `_ROMAN`
            # first, C-level, so a family word pays no frame
            elif (k > lead and len(piece) == 1
                    and _ROMAN.match(
                        (word := tokens[piece[0]]).text.rstrip("."))
                    is not None
                    and all(is_suffix_piece(fam_pieces[j], fam_tags[j],
                                            tokens)
                            for j in range(k + 1, len(fam_pieces)))
                    and (numeral := _family_part_numeral(
                        word, tokens[fam_pieces[k - 1][0]].text,
                        k - lead, state.one_case)) is not None):
                _set_roles(tokens, piece, numeral)
                # reported where taken: a name word here is the family
                # name the comma has just named, which nobody misreads
                if (numeral is Role.SUFFIX
                        and not is_listed_numeral(word.text, word.tags)
                        and not numeral_settled_by_case(word.text,
                                                        state.one_case)):
                    ambiguities.append(PendingAmbiguity(
                        AmbiguityKind.SUFFIX_OR_NAME,
                        f"{word.text!r} ending the family part is a roman "
                        f"numeral, so it reads as a generational suffix; "
                        f"it may be a name word", tuple(piece),
                        alternative=name_reading(word, Role.FAMILY)))
            elif (k > lead and is_suffix_piece(piece, fam_tags[k], tokens)
                    and not (k + 1 < len(fam_pieces)
                             and "particle" in tokens[piece[0]].tags
                             and not is_suffix_piece(
                                 fam_pieces[k + 1], fam_tags[k + 1],
                                 tokens))):
                _set_roles(tokens, piece, Role.SUFFIX)
            else:
                _set_roles(tokens, piece, Role.FAMILY)
        tail = 2
    # rules/C2: segments past the structure's name segments are
    # consumed as suffixes, except "a word of the title vocabulary there
    # that is not also suffix vocabulary is a title" (#603) -- a part
    # past the second comma holds no name word, so the surnames H5
    # keeps a bare trailing title word from misreading are not there to
    # protect ('Eric H. Holder, Jr., Attorney General'). A
    # piece holding a suffix word stays the postnominal the slot makes
    # it, a dual alone as after a family comma (C8) and a dual group's
    # connective join took into a title ('PhD - and MD') alike.
    for seg_idx in range(tail, len(state.segments)):
        for piece, ptags_ in zip(state.pieces[seg_idx],
                                 state.piece_tags[seg_idx]):
            # the tag tests inline ahead of the predicate: every tail
            # past the name segments runs this ('John Smith, Jr., PhD'),
            # the part after a suffix comma being bound by group, and the call
            # would be its frame. Both arms are needed -- a connective
            # join tags a piece a title though its first token is none
            # ('and Secretary of State')
            _set_roles(tokens, piece,
                       Role.TITLE
                       if (("title" in ptags_
                            or "vocab:title" in tokens[piece[0]].tags)
                           and is_title_piece(piece, ptags_, tokens)
                           and not any("vocab:suffix" in tokens[i].tags
                                       for i in piece))
                       else Role.SUFFIX)
    # rules/S12: "where the count takes the pair, the reading is reported" -- at
    # the end of a name, at the end of the given part, as a run start,
    # here where its roles are final (the part a comma's decision binds reports in `_comma`, a
    # pair a maiden clause releases in group). A loop over the piece
    # tags, so a name with no pair pays no frame for it.
    for seg_idx in range(min(tail, len(state.segments))):
        for piece, ptags_ in zip(state.pieces[seg_idx],
                                 state.piece_tags[seg_idx]):
            if ("split" in ptags_ and len(piece) == 2
                    and tokens[piece[0]].role is Role.SUFFIX
                    and tokens[piece[1]].role is Role.SUFFIX):
                ambiguities.append(split_credential_report(
                    piece, tokens, _split_name_alt(state, tokens, seg_idx,
                                                   piece, order)))
    # the reports earlier stages left a field for: only a name that
    # has one pays the walk
    if state.ambiguities:
        _resolve_deferred(state, tokens, ambiguities, order)
    return copy_with(state, tokens=tuple(tokens),
                     order=order,
                     ambiguities=tuple(ambiguities))
