"""Stage: assign.

Consumes: pieces + piece_tags (grouped), segments, structure, tokens.
Produces: tokens with roles set on every main-stream token.
Reads: Policy.name_order (#270); token/piece tags; Lexicon only through
tags already applied by classify (plus the leading-title period rule).

Ports v1's assignment loops. NO_COMMA (per name_order):
leading title pieces chain while no given-position name has been seen
(a title needs a following piece, unless the whole name is one title);
then positional assignment per name_order with the trailing-suffix
rule: the piece from which everything after is a strict suffix is the
last name-position piece, the rest are suffixes. The v1 single-name+
nickname rule lives here (plan deviation #2): one non-title piece plus
a nonempty nickname puts that piece in FAMILY.
FAMILY_COMMA: segment 0 wholly FAMILY (v1 parity); segment 1 gets
leading titles, then given, then middles with strict-suffix pieces to
suffix; segments 2+ are suffixes (lenient -- segment already flagged
non-suffixy ones COMMA_STRUCTURE).
SUFFIX_COMMA: segment 0 as NO_COMMA; segments 1+ wholly SUFFIX.
Emits PARTICLE_OR_GIVEN when the given position consumed a leading
particles_ambiguous token with more pieces following ("Van Johnson").
"""
from __future__ import annotations

import dataclasses
import re

from nameparser._pipeline._group import (
    _is_suffix_piece, _is_title_piece,
)
from nameparser._pipeline._state import (
    ParseState, PendingAmbiguity, Structure, WorkToken,
)
from nameparser._types import AmbiguityKind, Role

# Ported verbatim from v1 (nameparser/config/regexes.py
# "period_abbreviation" and "roman_numeral") -- layering forbids the
# config import; keep in sync by hand.
_PERIOD_ABBREV = re.compile(r'^[^\W\d_]{2,}\.$')
_ROMAN = re.compile(r'^(X|IX|IV|V?I{0,3})$', re.I)


def _set_roles(tokens: list[WorkToken], piece: tuple[int, ...],
               role: Role) -> None:
    for i in piece:
        tokens[i] = dataclasses.replace(tokens[i], role=role)


def _is_leading_title(piece: tuple[int, ...], ptags: frozenset[str],
                      tokens: list[WorkToken]) -> bool:
    if _is_title_piece(list(piece), set(ptags), tuple(tokens)):
        return True
    return (len(piece) == 1
            and bool(_PERIOD_ABBREV.match(tokens[piece[0]].text)))


def _name_positions(order: tuple[Role, Role, Role],
                    count: int) -> list[Role]:
    """Roles for `count` name pieces (titles/suffixes already peeled),
    per name_order. GIVEN_FIRST: given, middles..., family.
    FAMILY_FIRST: family, given, middles... FAMILY_FIRST_GIVEN_LAST:
    family, middles..., given. One piece takes order[0]'s role
    (spec §5a); two pieces take order[0] and the other primary."""
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
                 ambiguities: list[PendingAmbiguity]) -> None:
    pieces = state.pieces[seg_idx]
    ptags = state.piece_tags[seg_idx]
    has_nickname = any(t.role is Role.NICKNAME for t in tokens)
    # peel leading titles
    n = 0
    while n < len(pieces):
        has_next = n + 1 < len(pieces)
        if ((has_next or len(pieces) == 1)
                and _is_leading_title(pieces[n], ptags[n], tokens)):
            _set_roles(tokens, pieces[n], Role.TITLE)
            n += 1
            continue
        break
    rest = list(range(n, len(pieces)))
    if not rest:
        return
    # v1 nickname rule (plan deviation #2)
    if len(rest) == 1 and has_nickname:
        _set_roles(tokens, pieces[rest[0]], Role.FAMILY)
        return
    # peel the trailing suffix run: k = first index in rest from which
    # every piece is a strict suffix (v1's are_suffixes tail rule, with
    # the roman-numeral special: a final roman numeral after a
    # non-initial piece is a suffix)
    k = len(rest)
    while k > 0:
        piece = pieces[rest[k - 1]]
        tags = ptags[rest[k - 1]]
        if _is_suffix_piece(list(piece), set(tags), tuple(tokens)):
            k -= 1
            continue
        if (k == len(rest) and k >= 2 and len(piece) == 1
                and _ROMAN.match(tokens[piece[0]].text)
                and "initial" not in tokens[pieces[rest[k - 2]][0]].tags):
            k -= 1
            continue
        break
    name_pieces, suffix_pieces = rest[:k], rest[k:]
    if not name_pieces and suffix_pieces:
        # everything suffix-shaped after titles: first one is the name
        name_pieces, suffix_pieces = suffix_pieces[:1], suffix_pieces[1:]
    roles = _name_positions(state.policy.name_order, len(name_pieces))
    for pos, piece_idx in enumerate(name_pieces):
        _set_roles(tokens, pieces[piece_idx], roles[pos])
    for piece_idx in suffix_pieces:
        _set_roles(tokens, pieces[piece_idx], Role.SUFFIX)
    # leading ambiguous particle read as a name (#121 surfaced)
    if name_pieces:
        head = pieces[name_pieces[0]]
        if (len(head) == 1 and len(name_pieces) > 1
                and "vocab:particle-ambiguous" in tokens[head[0]].tags):
            ambiguities.append(PendingAmbiguity(
                AmbiguityKind.PARTICLE_OR_GIVEN,
                f"leading {tokens[head[0]].text!r} may be a family-name "
                f"particle; read as a given name",
                tuple(head)))


def assign(state: ParseState) -> ParseState:
    tokens = list(state.tokens)
    ambiguities = list(state.ambiguities)
    if not state.segments:
        return state
    if state.structure is Structure.NO_COMMA:
        _assign_main(0, state, tokens, ambiguities)
    elif state.structure is Structure.SUFFIX_COMMA:
        _assign_main(0, state, tokens, ambiguities)
        for seg_idx in range(1, len(state.segments)):
            for piece in state.pieces[seg_idx]:
                _set_roles(tokens, piece, Role.SUFFIX)
    else:  # FAMILY_COMMA
        # PARTICLE_OR_GIVEN is deliberately not emitted here: after a
        # comma the family is already fixed, so a leading given-position
        # particle is not meaningfully ambiguous.
        for piece in state.pieces[0]:
            _set_roles(tokens, piece, Role.FAMILY)
        if len(state.segments) > 1:
            pieces = state.pieces[1]
            ptags = state.piece_tags[1]
            given_done = False
            n = 0
            while n < len(pieces):
                if (not given_done
                        and _is_leading_title(pieces[n], ptags[n], tokens)
                        and (n + 1 < len(pieces) or len(pieces) == 1)):
                    _set_roles(tokens, pieces[n], Role.TITLE)
                    n += 1
                    continue
                break
            for m in range(n, len(pieces)):
                if _is_suffix_piece(list(pieces[m]), set(ptags[m]),
                                    tuple(tokens)):
                    _set_roles(tokens, pieces[m], Role.SUFFIX)
                elif not given_done:
                    _set_roles(tokens, pieces[m], Role.GIVEN)
                    given_done = True
                else:
                    _set_roles(tokens, pieces[m], Role.MIDDLE)
        for seg_idx in range(2, len(state.segments)):
            for piece in state.pieces[seg_idx]:
                _set_roles(tokens, piece, Role.SUFFIX)
    return dataclasses.replace(state, tokens=tuple(tokens),
                               ambiguities=tuple(ambiguities))
