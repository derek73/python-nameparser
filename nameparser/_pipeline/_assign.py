"""Stage: assign.

Consumes: pieces + piece_tags (grouped), segments, structure, tokens.
Produces: tokens with roles set on every main-stream token.
Reads: Policy.name_order (#270), is_suffix_lenient on the trailing
piece of a two-part comma name, and Policy.script_orders (#271, which
overrides it when every name piece is written wholly in one script, or
in the Han/Hiragana/Katakana repertoire the #272 kana license shares
across pieces); token/piece tags; Lexicon only through tags already
applied by classify (plus the leading-title period rule).

Implements rules H2, H4, H5, N3, O4, O5 and W4 of docs/design/rules.md,
each cited at its code below. Ports v1's assignment loops.
NO_COMMA (per name_order):
leading title pieces chain while no given-position name has been seen
(a title needs a following piece, unless the whole name is one title);
then positional assignment per name_order with the trailing-suffix
rule: the piece from which everything after is a strict suffix is the
last name-position piece, the rest are suffixes. That peel is only
provisional: behind it a trailing run of period-marked title words
chains into the title from the end, leaving one name piece standing,
and the peel then runs ONCE over the pieces with the titled ones
spliced out, so a trailing title is transparent to it.
The v1 single-name+nickname rule lives here (decisions.md#N3): a
nonempty nickname beside exactly one piece in total puts that piece
in FAMILY.
FAMILY_COMMA: segment 0 wholly FAMILY (v1 parity) UNLESS segment 1
holds no name word (titles and suffixes only), which fixed no family
boundary -- there segment 0 takes the NO_COMMA positional read instead,
order and all ('John Smith, Dr.', 'John Smith, Mr. Jr.'); segment
1 is wholly SUFFIX when it is nothing but suffix pieces ('Smith, Jr.',
'Smith, Ph. D. Jr.' -- the credential run C1 describes, in the listing
form), else gets leading titles, then the same trailing title run
over the pieces this segment does not read as suffixes ('Smith, John
Prof.'), then given, then middles with those suffix-reading pieces to
suffix -- one predicate for both; segments 2+ are suffixes (lenient --
segment already flagged non-suffixy ones COMMA_STRUCTURE).
SUFFIX_COMMA: segment 0 as NO_COMMA; segments 1+ wholly SUFFIX.
Emits PARTICLE_OR_GIVEN when the leading name piece is a lone
particles_ambiguous token with more pieces following ("Van Johnson",
and since #367 "Dr. Van Johnson" too, a title no longer displacing the
particle out of that position) -- whatever role name_order assigns.
Emits SUFFIX_OR_NAME at three sites: the trailing roman numeral, each
ambiguous acronym the trailing peel had to resolve, and the bare-suffix
carve-out where an input that is nothing but post-nominal vocabulary
gets its first word made into the name (H4's suffix half, #491). And
at the one site that places a LONE name word, GIVEN_OR_FAMILY for the
field the convention picked (O5, #449) and TITLE_OR_NAME for the two
shapes where the doubt is whether a word is a title instead (H4,
#491): the peel leaving one title-vocabulary word standing, and a
joined unit carrying title vocabulary.
"""
from __future__ import annotations

import dataclasses
from collections.abc import Sequence, Set
from typing import NamedTuple

from nameparser._lexicon import Lexicon
from nameparser._pipeline._vocab import (
    effective_script, is_suffix_lenient, resolve_script_set,
)
from nameparser._pipeline._pieces import (
    is_suffix_piece, leading_titles, peel_trailing, peel_walk,
    segment_suffix_reading, trailing_titles,
)
from nameparser._pipeline._state import (
    ParseState, PendingAmbiguity, Structure, WorkToken, _NEVER_FLIPPED,
)
from nameparser._policy import Policy, Script
from nameparser._types import AmbiguityKind, Role

def _set_roles(tokens: list[WorkToken], piece: tuple[int, ...],
               role: Role) -> None:
    for i in piece:
        tokens[i] = dataclasses.replace(tokens[i], role=role)


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


# rules.md#H2: "an abbreviation opening the part of the name that
# carries the given name — the whole name, or the part after a
# family comma — reads as a title even when unlisted" -- the count is
# _pieces.leading_titles since #424 (its test, is_leading_title, is
# the leading-particle scan's too); the roles are set here.
def _peel_leading_titles(pieces: tuple[tuple[int, ...], ...],
                         ptags: tuple[frozenset[str], ...],
                         tokens: list[WorkToken]) -> int:
    """Assign TITLE to the leading title pieces and return the first
    non-title index."""
    n = leading_titles(pieces, ptags, tokens)
    for k in range(n):
        _set_roles(tokens, pieces[k], Role.TITLE)
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


# rules.md#W4: "a name written wholly in one East Asian script, or in
# the kana-licensed Japanese repertoire, reads family-first whatever
# order the caller declared; a wholly-katakana name keeps the declared
# order" (history: decisions.md#W4)
def _effective_order(policy: Policy,
                     pieces: list[tuple[int, ...]],
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

    Returns an EffectiveOrder: the order triple, and `by_script` set only on
    the one path where an entry answered. Every fallback below is a
    script rule DECLINING, and reports it as such.
    """
    declared = EffectiveOrder(policy.name_order, by_script=False)
    # #298 transcription marker -- see the docstring; codepoint-scoped
    # (only U+00B7 records; decisions.md#T3)
    if dot_divided:
        return declared
    if not policy.script_orders:
        return declared
    # Collect every token's script rather than comparing pairwise as
    # tokens are seen: the kana license needs the WHOLE set (a Han
    # piece and a Hiragana piece only license together, never one at a
    # time), so resolution is deferred to resolve_script_set below.
    found: set[Script] = set()
    for piece in pieces:
        for i in piece:
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


# rules.md#O4: "words no vocabulary has claimed read by position. In
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
    # rules.md#O5: "a name of one name word that nothing else has
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


def _assign_main(seg_idx: int, state: ParseState,
                 tokens: list[WorkToken],
                 ambiguities: list[PendingAmbiguity],
                 ) -> tuple[Role, Role, Role] | None:
    """Returns the order the positional read used, for ParseState.order
    -- None on every path that returns before resolving one."""
    pieces = state.pieces[seg_idx]
    ptags = state.piece_tags[seg_idx]
    has_nickname = any(t.role is Role.NICKNAME for t in tokens)
    n = _peel_leading_titles(pieces, ptags, tokens)
    if n == len(pieces):
        return None
    # group-flagged suffix pieces (the ph-d merge) are suffixes at ANY
    # position -- v1's fix_phd extracted the credential from the string
    # before parsing, so position never mattered (PR review I3).
    # Walked rather than collected first: a comprehension is a frame of
    # its own on 3.11 and the list was never read again, which is one
    # frame back against the one the H5 walk below costs
    # (decisions.md#parse-cost).
    for k in range(n, len(pieces)):
        if "suffix" in ptags[k]:
            _set_roles(tokens, pieces[k], Role.SUFFIX)
    rest = peel_walk(n, ptags)
    if not rest:
        return None
    # rules.md#N3: "a name that is only a nickname and one name word
    # reads that word as the family name" (history: decisions.md#N3)
    # -- v1's p_len == 1 counted
    # the WHOLE segment before any title peeling -- 'Xyz. (Bud) Smith'
    # has two pieces, so the title peel wins and Smith stays the given
    # name (pinned live 2026-07-17)
    if len(pieces) == 1 and len(rest) == 1 and has_nickname:
        _set_roles(tokens, pieces[rest[0]], Role.FAMILY)
        return None
    # peel the trailing suffix run: k = first index in rest from which
    # every piece is a suffix. The walk is _pieces.peel_trailing since
    # #425 -- one walk, shared with the bound-given reserve, and
    # documented there. Every bare ambiguous acronym it had to resolve
    # is one coin-flip each, in either direction, so the report
    # collects rather than overwrites. Deferred to after assignment
    # because the wording reads the role back, and which role "not
    # peeled" means depends on name_order. (The roman-numeral fork
    # needs no such deferral and is reported here.)
    #
    # This first peel is PROVISIONAL: all it settles is where the H5
    # walk below starts. Its roles and its reports are never used --
    # the walk can remove the very word that stopped it, so when the
    # walk takes anything the peel is asked again over the pieces as
    # they then stand, and that second answer is the only one that
    # places a piece or reports a fork.
    peeled = peel_trailing(rest, pieces, ptags, tokens)
    # rules.md#H5: "successive single words that wear the abbreviation
    # shape and are title vocabulary chain into the title from the end,
    # leaving one name word standing"
    # -- read over what the suffix
    # peel left and set BEFORE _name_positions, so the shortened list is
    # what the positional read and the script test both see (a trailing
    # Latin title must not make a wholly-CJK name look mixed-script, the
    # same reason the leading peel runs first). Placed ahead of the
    # bare-suffix carve-out because with no name piece left there is
    # nothing for the walk to read: its floor returns 0 on an empty
    # list, so the branch below is reached exactly as before.
    titled_tail = trailing_titles(rest[:peeled.names], pieces, ptags,
                                  tokens)
    if titled_tail:
        cut = peeled.names - titled_tail
        for piece_idx in rest[cut:peeled.names]:
            _set_roles(tokens, pieces[piece_idx], Role.TITLE)
        # The title is TRANSPARENT to the suffix peel: the pieces the
        # walk took are spliced out and the peel runs once over what
        # is left -- the name pieces the walk kept, then the pieces
        # the provisional peel had taken, in original order -- so
        # 'X Prof. Y' reads exactly as 'X Y' reads, plus the title.
        # 'John Smith Jr. Prof.' reads suffix 'Jr.' where a single
        # pass promoted a generational suffix to the family name, and
        # 'John Prof. MA' reads the family 'MA' that 'John MA' reads.
        rest = rest[:cut] + rest[peeled.names:]
        peeled = peel_trailing(rest, pieces, ptags, tokens)
    if peeled.numeral is not None:
        # a trailing single letter is a name part unless it happens
        # to be a roman numeral -- and V/X/I are ordinary middle
        # initials, so taking it as a suffix is a call, not a fact
        ambiguities.append(PendingAmbiguity(
            AmbiguityKind.SUFFIX_OR_NAME,
            f"{tokens[peeled.numeral[0]].text!r} is a roman numeral, so "
            f"it reads as a generational suffix; any other single "
            f"letter there would be a middle initial",
            peeled.numeral))
    name_pieces, suffix_pieces = rest[:peeled.names], rest[peeled.names:]
    if peeled.names == 0:
        # everything suffix-shaped after titles: first one is the name
        name_pieces, suffix_pieces = suffix_pieces[:1], suffix_pieces[1:]
    # AFTER both peels, and load-bearing: the script test sees the NAME
    # pieces only, so a Latin title or suffix ('Dr. 毛 泽东', '毛 泽东,
    # PhD') cannot make a wholly-CJK name look mixed-script.
    resolved = _effective_order(state.policy,
                                [pieces[i] for i in name_pieces], tokens,
                                dot_divided=bool(state.interpunct_offsets))
    order = resolved.order
    roles = _name_positions(order, len(name_pieces))
    for pos, piece_idx in enumerate(name_pieces):
        _set_roles(tokens, pieces[piece_idx], roles[pos])
    for piece_idx in suffix_pieces:
        _set_roles(tokens, pieces[piece_idx], Role.SUFFIX)
    # Both emitters below turn on the PEEL's count, so neither can
    # reach a name that kept two name pieces, and the two scans are
    # nested under the count rather than run beside it: they cost the
    # call budget on every parse otherwise (decisions.md#parse-cost).
    if peeled.names <= 1:
        head = pieces[name_pieces[0]]
        token = tokens[head[0]]
        assert token.role is not None
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
        # rules.md#H4: "an input whose every word is post-nominal
        # vocabulary reads its first word as a name and reports
        # `suffix-or-name`" (history: decisions.md#H4) -- only the
        # word made into a name reports, and no name piece survived
        # the peel, so the carve-out above made the first post-nominal
        # the name. The role comes off the token for the reason stated
        # at the particle emitter below.
        if peeled.names == 0 and field_undecided:
            text = " ".join(tokens[i].text for i in head)
            ambiguities.append(PendingAmbiguity(
                AmbiguityKind.SUFFIX_OR_NAME,
                f"{text!r} is post-nominal vocabulary with no name word "
                f"beside it; read as a {token.role.value} name rather than "
                f"a post-nominal, nothing else being left to be the name",
                tuple(head)))
        # One name piece off the peel: the convention placed a lone
        # name word. A suffix beside it is not a decision -- 'Smith
        # Jr.' and "'Smitty' Jones Jr." ARE this convention -- and the
        # count comes off the peel rather than off name_pieces, which
        # is what keeps the carve-out above out of these branches.
        # Title vocabulary in the unit makes the doubt H4's (is the
        # WORD a title), anything else O5's (which FIELD it took), so
        # only the second reads `field_undecided`.
        if peeled.names == 1 and not resolved.by_script:
            # rules.md#H4: "an input whose only remaining name word
            # after the title peel is itself title vocabulary reads
            # that word as the name by convention and reports
            # `title-or-name`" (history: decisions.md#H4), and H4's
            # join clause, stated at rules.md#O5 as its exception --
            # one branch, its detail naming a field only in the join
            # shape ('John of Prince', 'Attorney General of
            # Minnesota'), where the unit is more than the title word.
            # A LONE title word never reaches here ('Dr.', 'Prince of
            # Wales'): the leading-title peel took the whole name.
            if any("vocab:title" in tokens[i].tags for i in head):
                text = " ".join(tokens[i].text for i in head)
                ambiguities.append(PendingAmbiguity(
                    AmbiguityKind.TITLE_OR_NAME,
                    f"{text!r} is title vocabulary and the only name word "
                    f"the title peel left standing; read as the name by "
                    f"convention rather than as more title"
                    if len(head) == 1 else
                    f"{text!r} is the only name unit and joins title "
                    f"vocabulary to a name word; read as a "
                    f"{token.role.value} name by convention",
                    tuple(head)))
            # rules.md#O5: "a name of one name word that nothing else has
            # decided reads that word as the given name under the default
            # given-first order, and as the family name under a declared
            # family-first one" (history: decisions.md#O5). Past
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
                    f"decides it; read as a {token.role.value} name by "
                    f"convention, which follows the read order",
                    tuple(head)))
    for piece in peeled.picks:
        # every pick is in rest, so the loops above just gave it a role
        token = tokens[piece[0]]
        assert token.role is not None
        taken, declined = (
            ("a suffix", "a name part") if token.role is Role.SUFFIX
            else (f"a {token.role.value} name", "a post-nominal"))
        ambiguities.append(PendingAmbiguity(
            AmbiguityKind.SUFFIX_OR_NAME,
            f"{token.text!r} written without periods is both a "
            f"post-nominal and an ordinary name; read as {taken} "
            f"rather than {declined}",
            piece))
    # leading ambiguous particle read as a name (#121 surfaced)
    if name_pieces:
        head = pieces[name_pieces[0]]
        if (len(head) == 1 and len(name_pieces) > 1
                and "vocab:particle-ambiguous" in tokens[head[0]].tags):
            # the loops above gave the head piece its role from
            # `order`, which is _effective_order's answer and not
            # necessarily name_order's -- a script_orders entry
            # overrides it. So read the role off the token rather than
            # assume given, or re-derive it here; same reason as
            # SUFFIX_OR_NAME just above.
            token = tokens[head[0]]
            assert token.role is not None
            ambiguities.append(PendingAmbiguity(
                AmbiguityKind.PARTICLE_OR_GIVEN,
                f"leading {token.text!r} may be a family-name "
                f"particle; read as a {token.role.value} name",
                tuple(head)))
    return order


def _reads_as_a_trailing_suffix(piece: Sequence[int],
                               prev_piece: Sequence[int],
                               prev_ptags: Set[str],
                               tokens: Sequence[WorkToken],
                               lexicon: Lexicon) -> bool:
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

    NOT is_trailing_numeral_suffix, though it answers the period half:
    it also refuses a numeral behind an initial-shaped piece, which is
    a no-comma rule and the opposite of this path's v1 parity --
    'Chang, Andy C I' is first Andy, middle C, suffix I, and asking
    that predicate here made the numeral a middle. The #401/#421 entry
    under decisions.md#P5 records the same fork declining to transfer
    to this walk under LENIENT.
    """
    text = tokens[piece[0]].text
    if text.endswith(".") and not is_suffix_piece(
            prev_piece, prev_ptags, tokens):
        return False
    return is_suffix_lenient(text, lexicon)


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
        # name, so P6's attachment in post_rules decides that fork and
        # reports it there, at the site that takes the branch (#405).
        # The positional read below (a comma followed by no
        # name word) emits and consults both, being the no-comma read
        # of segment 0; group's chain emitter still does not, since
        # group runs before assign decides which read applies (recorded
        # at decisions.md#C1).
        # v1: "lastname part may have suffixes in it" -- the first
        # piece is always the family even if suffix-shaped; any later
        # strict-suffix piece goes to SUFFIX per piece ('Smith Jr.,
        # John' -> family=Smith, suffix=Jr.)
        fam_pieces = state.pieces[0]
        fam_tags = state.piece_tags[0]
        # A comma followed by no name word fixed nothing, so segment 0
        # keeps its positional read -- including script_orders, the
        # particle fork, and the ORDER, which post_rules' family-first
        # fold (P1) and its leading-piece scan key on: "assign records
        # no order after a family comma" is the invariant those rules
        # rest on, and this is the path that gives one, so they read
        # segment 0 as the name it is ('de Mesnil Jean, Dr.' under a
        # family-first order keeps family 'de Mesnil'; the test review
        # found the fold missing it). The wholly-family branch below
        # suppresses all three precisely because the comma HAD fixed
        # the family. Needs two NAME pieces: with one, the positional
        # read would make it a lone GIVEN, which is worse than what it
        # replaces -- and the count is of name pieces, since the
        # positional read peels a trailing suffix first: 'Smith Jr.,
        # Mr.' has two pieces and one name, and read positionally lost
        # its family (the code review).
        reading = segment_suffix_reading(
            state.pieces[1], state.piece_tags[1], tokens,
            state.policy.lenient_comma_suffixes)
        # Segment 1 is read FIRST, ahead of either branch below. It
        # consumes `reading`, piece tags and text only -- nothing
        # segment 0's read writes -- and running it first is what puts
        # a TITLE role on the title standing after the comma ('John V,
        # Dr.') before _assign_main scans for one, so the positional
        # read below sees that title the way it sees its own peeled
        # ones (#449 review round; it replaced a `titled` keyword).
        if len(state.segments) > 1:
            pieces = state.pieces[1]
            ptags = state.piece_tags[1]
            titled_idx: tuple[int, ...] = ()

            def reads_as_a_suffix(m: int, last: int) -> bool:
                """Does this segment's walk read piece `m` as a suffix?

                Asked twice, and by one predicate rather than by two
                conditions written to match
                (mechanisms.md#ONE-PREDICATE-PER-QUESTION): once to
                find the pieces the H5 title walk must not reach past,
                and once by the walk order below, which is the site
                that places them. `last` is where this segment's name
                ends -- provisionally the segment's last piece, and
                after the title walk the last piece the walk left,
                since a title it took is not where a name ends.

                `titled_idx` is read at CALL time and is empty on the
                first pass, which is what makes the second reading the
                one 'as if the titled pieces were absent': the lenient
                test's preceding piece skips them too.
                """
                if is_suffix_piece(pieces[m], ptags[m], tokens):
                    return True
                prev = m - 1
                while prev in titled_idx:
                    prev -= 1
                # trailing piece of a two-part name is unambiguously
                # positioned: v1 accepts the lenient test there
                # ('Smith, John V' -> suffix='V', #144); with a third
                # comma part the trailing token is more likely a middle
                # initial, so strict only
                return (m == last and len(state.segments) == 2
                        and len(pieces[m]) == 1
                        and _reads_as_a_trailing_suffix(
                            pieces[m], pieces[prev], ptags[prev],
                            tokens, state.lexicon))

            # rules.md#C1: "a credential run after the comma means the
            # name is in natural order with suffixes appended" -- and
            # with one word before the comma the listing form holds,
            # the family is that word, and the run is still the
            # credential run. A no-name segment is read piece by
            # piece, the suffix vocabulary's verdict BEFORE the title
            # reading of the same word: the slot after a family comma
            # is postnominal position, so a segment of nothing but
            # suffix pieces is the credential run, whole (#296:
            # 'Smith, Jr.' read title 'Jr.' through the period-
            # abbreviation inference; #325: 'Smith, Ph. D. Jr.' put
            # the split credential in the given name, the lone-piece
            # route not applying), and a mixed run is a title and a
            # postnominal, each where it stands ('Smith, Mr. Jr.').
            # Vocabulary decides which words qualify -- 'Smith, Dr.'
            # reads the title, 'dr' not being suffix vocabulary since
            # the audit -- and position breaks the tie for the genuine
            # duals ('Smith, Sr.' is Senior, 'Sr. Garcia' Señor). A
            # name word in the segment makes it v1's walk ('Smith,
            # John Jr.').
            if reading is not None:
                # the gate's own reading (#430)
                for k, piece in enumerate(pieces):
                    _set_roles(tokens, piece,
                               Role.SUFFIX if reading[k] else Role.TITLE)
                n = len(pieces)
            else:
                n = _peel_leading_titles(pieces, ptags, tokens)
                # rules.md#H5: "the title is TRANSPARENT to the suffix
                # reading: where two or more name words stand, what
                # stands once the chain is taken reads exactly as it
                # would read written without the title, plus the title"
                # -- the trailing title run, on this walk
                # too. A name word in segment 1 is what keeps the gate
                # above from reading the segment as a credential run,
                # so 'Smith, John Prof.' had no route to title at all
                # and read middle 'Prof.' at every baseline; the
                # 'Smith, Dr.' family of rows that already route are
                # the gate's doing, a different mechanism.
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
                # would say of it, so it is always a candidate.
                walkable = [k for k in range(n, len(pieces))
                            if k == n or not reads_as_a_suffix(
                                k, len(pieces) - 1)]
                taken = trailing_titles(walkable, pieces, ptags, tokens)
                if taken:
                    titled_idx = tuple(walkable[len(walkable) - taken:])
                    for k in titled_idx:
                        _set_roles(tokens, pieces[k], Role.TITLE)
            # v1 walk order: the first non-title piece is ALWAYS the
            # given, before any suffix check -- 'Hardman, RN - CRNA'
            # keeps first='RN'. The one deliberate 2.0 deviation,
            # classified fix(comma-family) -- a last piece that is
            # unambiguously suffix-shaped is a suffix, where v1 made
            # it the given ('Andrews, M.D.', 'Smith, Dr. Jr.') -- is
            # the no-name read above now: a segment whose only
            # non-title piece is a suffix piece holds no name word,
            # so the walk here never meets the case.
            if n < len(pieces):
                _set_roles(tokens, pieces[n], Role.GIVEN)
            # the walk's floor leaves a name piece standing, so the
            # given above is never one of the pieces it took; what the
            # walk DOES move is where this segment's name ends, and the
            # lenient tail test below turns on that (#144)
            last_kept = len(pieces) - 1
            while last_kept in titled_idx:
                last_kept -= 1
            for m in range(n + 1, len(pieces)):
                if m in titled_idx:
                    continue
                if reads_as_a_suffix(m, last_kept):
                    _set_roles(tokens, pieces[m], Role.SUFFIX)
                else:
                    _set_roles(tokens, pieces[m], Role.MIDDLE)
        if reading is not None and sum(
                1 for k, piece in enumerate(fam_pieces)
                if not is_suffix_piece(piece, fam_tags[k], tokens)) > 1:
            order = _assign_main(0, state, tokens, ambiguities)
        else:
            for k, piece in enumerate(fam_pieces):
                if k > 0 and is_suffix_piece(piece, fam_tags[k], tokens):
                    _set_roles(tokens, piece, Role.SUFFIX)
                else:
                    _set_roles(tokens, piece, Role.FAMILY)
        tail = 2
    # segments past the structure's name segments are wholly suffixes
    for seg_idx in range(tail, len(state.segments)):
        for piece in state.pieces[seg_idx]:
            _set_roles(tokens, piece, Role.SUFFIX)
    return dataclasses.replace(state, tokens=tuple(tokens),
                               order=order,
                               ambiguities=tuple(ambiguities))
