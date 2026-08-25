"""Stage: assign.

Consumes: pieces + piece_tags (grouped), segments, structure, tokens.
Produces: tokens with roles set on every main-stream token.
Reads: Policy.name_order (#270), is_suffix_lenient on the trailing
piece of a two-part comma name, and Policy.script_orders (#271, which
overrides it when every name piece is written wholly in one script, or
in the Han/Hiragana/Katakana repertoire the #272 kana license shares
across pieces); token/piece tags; Lexicon only through tags already
applied by classify (plus the leading-title period rule).

Implements rules H2, N3, O4 and W4 of docs/design/rules.md, each
cited at its code below. Ports v1's assignment loops.
NO_COMMA (per name_order):
leading title pieces chain while no given-position name has been seen
(a title needs a following piece, unless the whole name is one title);
then positional assignment per name_order with the trailing-suffix
rule: the piece from which everything after is a strict suffix is the
last name-position piece, the rest are suffixes. The v1 single-name+
nickname rule lives here (decisions.md#N3): a nonempty nickname
beside exactly one piece in total puts that piece in FAMILY.
FAMILY_COMMA: segment 0 wholly FAMILY (v1 parity) UNLESS segment 1
holds no name word (titles and suffixes only), which fixed no family
boundary -- there segment 0 takes the NO_COMMA positional read instead,
order and all ('John Smith, Dr.', 'John Smith, Mr. Jr.'); segment
1 is wholly SUFFIX when it is nothing but suffix pieces ('Smith, Jr.',
'Smith, Ph. D. Jr.' -- the credential run C1 describes, in the listing
form), else gets leading titles, then given, then middles with
strict-suffix pieces to suffix; segments 2+ are suffixes (lenient --
segment already flagged non-suffixy ones COMMA_STRUCTURE).
SUFFIX_COMMA: segment 0 as NO_COMMA; segments 1+ wholly SUFFIX.
Emits PARTICLE_OR_GIVEN when the leading name piece is a lone
particles_ambiguous token with more pieces following ("Van Johnson",
and since #367 "Dr. Van Johnson" too, a title no longer displacing the
particle out of that position) -- whatever role name_order assigns.
"""
from __future__ import annotations

import dataclasses

from nameparser._pipeline._vocab import (
    effective_script, is_suffix_lenient, resolve_script_set,
)
from nameparser._pipeline._group import (
    _is_suffix_piece, _leading_titles, _peel_trailing, _peel_walk,
    _segment_holds_no_name,
)
from nameparser._pipeline._state import (
    ParseState, PendingAmbiguity, Structure, WorkToken,
)
from nameparser._policy import Policy, Script
from nameparser._types import AmbiguityKind, Role

def _set_roles(tokens: list[WorkToken], piece: tuple[int, ...],
               role: Role) -> None:
    for i in piece:
        tokens[i] = dataclasses.replace(tokens[i], role=role)


# rules.md#H2: "an abbreviation opening the part of the name that
# carries the given name — the whole name, or the part after a
# family comma — reads as a title even when unlisted" -- the count is
# group's _leading_titles since #424 (its test, _is_leading_title, is
# the leading-particle scan's too); the roles are set here.
def _peel_leading_titles(pieces: tuple[tuple[int, ...], ...],
                         ptags: tuple[frozenset[str], ...],
                         tokens: list[WorkToken]) -> int:
    """Assign TITLE to the leading title pieces and return the first
    non-title index."""
    n = _leading_titles(pieces, ptags, tokens)
    for k in range(n):
        _set_roles(tokens, pieces[k], Role.TITLE)
    return n


# rules.md#W4: "a name written wholly in one East Asian script, or in
# the kana-licensed Japanese repertoire, reads family-first whatever
# order the caller declared; a wholly-katakana name keeps the declared
# order" (history: decisions.md#W4)
def _effective_order(policy: Policy,
                     pieces: list[tuple[int, ...]],
                     tokens: list[WorkToken],
                     *, dot_divided: bool) -> tuple[Role, Role, Role]:
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
    """
    # #298 transcription marker -- see the docstring; codepoint-scoped
    # (only U+00B7 records; decisions.md#T3)
    if dot_divided:
        return policy.name_order
    if not policy.script_orders:
        return policy.name_order
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
                return policy.name_order
            found.add(script)
    resolved = resolve_script_set(found)
    if resolved is None:
        # e.g. Han+Hangul: two scripts, neither the kana license's
        # Han/Hiragana/Katakana repertoire -- no single tradition
        return policy.name_order
    return next((order for s, order in policy.script_orders
                 if s is resolved), policy.name_order)


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
    rest = list(range(n, len(pieces)))
    if not rest:
        return None
    # group-flagged suffix pieces (the ph-d merge) are suffixes at ANY
    # position -- v1's fix_phd extracted the credential from the string
    # before parsing, so position never mattered (PR review I3)
    flagged = [k for k in rest if "suffix" in ptags[k]]
    for k in flagged:
        _set_roles(tokens, pieces[k], Role.SUFFIX)
    rest = _peel_walk(n, ptags)
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
    # every piece is a suffix. The walk is group's _peel_trailing since
    # #425 -- one walk, shared with the bound-given reserve, and
    # documented there. Every bare ambiguous acronym it had to resolve
    # is one coin-flip each, in either direction, so the report
    # collects rather than overwrites. Deferred to after assignment
    # because the wording reads the role back, and which role "not
    # peeled" means depends on name_order. (The roman-numeral fork
    # needs no such deferral and is reported here.)
    peeled = _peel_trailing(rest, pieces, ptags, tokens)
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
    if not name_pieces and suffix_pieces:
        # everything suffix-shaped after titles: first one is the name
        name_pieces, suffix_pieces = suffix_pieces[:1], suffix_pieces[1:]
    # AFTER both peels, and load-bearing: the script test sees the NAME
    # pieces only, so a Latin title or suffix ('Dr. 毛 泽东', '毛 泽东,
    # PhD') cannot make a wholly-CJK name look mixed-script.
    order = _effective_order(state.policy,
                             [pieces[i] for i in name_pieces], tokens,
                             dot_divided=bool(state.interpunct_offsets))
    roles = _name_positions(order, len(name_pieces))
    for pos, piece_idx in enumerate(name_pieces):
        _set_roles(tokens, pieces[piece_idx], roles[pos])
    for piece_idx in suffix_pieces:
        _set_roles(tokens, pieces[piece_idx], Role.SUFFIX)
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
        # reason. The positional read below (a comma followed by no
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
        # segment 0 as the name it is ('de Mesnil Juan, Dr.' under a
        # family-first order keeps family 'de Mesnil'; the test review
        # found the fold missing it). The wholly-family branch below
        # suppresses all three precisely because the comma HAD fixed
        # the family. Needs two NAME pieces: with one, the positional
        # read would make it a lone GIVEN, which is worse than what it
        # replaces -- and the count is of name pieces, since the
        # positional read peels a trailing suffix first: 'Smith Jr.,
        # Mr.' has two pieces and one name, and read positionally lost
        # its family (the code review).
        no_name = _segment_holds_no_name(state.pieces[1],
                                         state.piece_tags[1], tokens)
        if no_name and sum(
                1 for k, piece in enumerate(fam_pieces)
                if not _is_suffix_piece(piece, fam_tags[k], tokens)) > 1:
            order = _assign_main(0, state, tokens, ambiguities)
        else:
            for k, piece in enumerate(fam_pieces):
                if k > 0 and _is_suffix_piece(piece, fam_tags[k], tokens):
                    _set_roles(tokens, piece, Role.SUFFIX)
                else:
                    _set_roles(tokens, piece, Role.FAMILY)
        if len(state.segments) > 1:
            pieces = state.pieces[1]
            ptags = state.piece_tags[1]
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
            if no_name:
                for k, piece in enumerate(pieces):
                    _set_roles(tokens, piece,
                               Role.SUFFIX if _is_suffix_piece(
                                   piece, ptags[k], tokens)
                               else Role.TITLE)
                n = len(pieces)
            else:
                n = _peel_leading_titles(pieces, ptags, tokens)
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
            for m in range(n + 1, len(pieces)):
                # trailing piece of a two-part name is unambiguously
                # positioned: v1 accepts the lenient test there
                # ('Smith, John V' -> suffix='V', #144); with a third
                # comma part the trailing token is more likely a middle
                # initial, so strict only
                last_of_two = (m == len(pieces) - 1
                               and len(state.segments) == 2)
                if _is_suffix_piece(pieces[m], ptags[m], tokens) or (
                        last_of_two and len(pieces[m]) == 1
                        and is_suffix_lenient(
                            tokens[pieces[m][0]].text, state.lexicon)):
                    _set_roles(tokens, pieces[m], Role.SUFFIX)
                else:
                    _set_roles(tokens, pieces[m], Role.MIDDLE)
        tail = 2
    # segments past the structure's name segments are wholly suffixes
    for seg_idx in range(tail, len(state.segments)):
        for piece in state.pieces[seg_idx]:
            _set_roles(tokens, piece, Role.SUFFIX)
    return dataclasses.replace(state, tokens=tuple(tokens),
                               order=order,
                               ambiguities=tuple(ambiguities))
