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
Emits PARTICLE_OR_GIVEN when the leading name piece is a lone
particles_ambiguous token with more pieces following ("Van Johnson") --
whatever role name_order assigns that position.
"""
from __future__ import annotations

import dataclasses
import re

from nameparser._pipeline._vocab import is_suffix_lenient
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
    if _is_title_piece(piece, ptags, tokens):
        return True
    return (len(piece) == 1
            and bool(_PERIOD_ABBREV.match(tokens[piece[0]].text)))


def _peel_leading_titles(pieces: tuple[tuple[int, ...], ...],
                         ptags: tuple[frozenset[str], ...],
                         tokens: list[WorkToken]) -> int:
    """Assign TITLE to the leading title pieces and return the first
    non-title index. A title needs a following piece, unless the whole
    segment is one title (v1 parity)."""
    n = 0
    while n < len(pieces):
        if ((n + 1 < len(pieces) or len(pieces) == 1)
                and _is_leading_title(pieces[n], ptags[n], tokens)):
            _set_roles(tokens, pieces[n], Role.TITLE)
            n += 1
            continue
        break
    return n


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
                 ambiguities: list[PendingAmbiguity]) -> None:
    pieces = state.pieces[seg_idx]
    ptags = state.piece_tags[seg_idx]
    has_nickname = any(t.role is Role.NICKNAME for t in tokens)
    n = _peel_leading_titles(pieces, ptags, tokens)
    rest = list(range(n, len(pieces)))
    if not rest:
        return
    # group-flagged suffix pieces (the ph-d merge) are suffixes at ANY
    # position -- v1's fix_phd extracted the credential from the string
    # before parsing, so position never mattered (PR review I3)
    flagged = [k for k in rest if "suffix" in ptags[k]]
    for k in flagged:
        _set_roles(tokens, pieces[k], Role.SUFFIX)
    rest = [k for k in rest if "suffix" not in ptags[k]]
    if not rest:
        return
    # v1 nickname rule (plan deviation #2): v1's p_len == 1 counted
    # the WHOLE segment before any title peeling -- 'Xyz. (Bud) Smith'
    # has two pieces, so the title peel wins and Smith stays the given
    # name (pinned live 2026-07-17)
    if len(pieces) == 1 and len(rest) == 1 and has_nickname:
        _set_roles(tokens, pieces[rest[0]], Role.FAMILY)
        return
    # peel the trailing suffix run: k = first index in rest from which
    # every piece is a strict suffix (v1's are_suffixes tail rule, with
    # the roman-numeral special: a final roman numeral after a
    # non-initial piece is a suffix)
    # (piece, reading taken, reading declined) when the peel had to
    # resolve a bare ambiguous acronym; both directions are guesses
    ambiguous_pick: tuple[tuple[int, ...], str, str] | None = None
    k = len(rest)
    while k > 0:
        piece = pieces[rest[k - 1]]
        tags = ptags[rest[k - 1]]
        if _is_suffix_piece(piece, tags, tokens):
            k -= 1
            continue
        if (k == len(rest) and k >= 2 and len(piece) == 1
                and _ROMAN.match(tokens[piece[0]].text)
                and "initial" not in tokens[pieces[rest[k - 2]][0]].tags):
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
                          and "vocab:suffix-ambiguous" in tokens[piece[0]].tags)
        if bare_ambiguous and k - 1 >= 2:
            ambiguous_pick = (piece, "a suffix", "an ordinary surname")
            k -= 1
            continue
        if bare_ambiguous and k >= 2:
            # not peeled, so it stays the last name piece -- the family
            # name under every order. (k < 2 means it is the only piece
            # left and lands in the given position, which is not the
            # fork this reports.)
            ambiguous_pick = (piece, "a family name", "a post-nominal")
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
    if ambiguous_pick is not None:
        piece, taken, declined = ambiguous_pick
        ambiguities.append(PendingAmbiguity(
            AmbiguityKind.SUFFIX_OR_FAMILY,
            f"{tokens[piece[0]].text!r} written without periods is both "
            f"a post-nominal and a surname; read as {taken} rather than "
            f"{declined}",
            tuple(piece)))
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
        tail = len(state.segments)
    elif state.structure is Structure.SUFFIX_COMMA:
        _assign_main(0, state, tokens, ambiguities)
        tail = 1
    else:  # FAMILY_COMMA
        # PARTICLE_OR_GIVEN is deliberately not emitted here: after a
        # comma the family is already fixed, so a leading given-position
        # particle is not meaningfully ambiguous.
        # v1: "lastname part may have suffixes in it" -- the first
        # piece is always the family even if suffix-shaped; any later
        # strict-suffix piece goes to SUFFIX per piece ('Smith Jr.,
        # John' -> family=Smith, suffix=Jr.)
        fam_pieces = state.pieces[0]
        fam_tags = state.piece_tags[0]
        for k, piece in enumerate(fam_pieces):
            if k > 0 and _is_suffix_piece(piece, fam_tags[k], tokens):
                _set_roles(tokens, piece, Role.SUFFIX)
            else:
                _set_roles(tokens, piece, Role.FAMILY)
        if len(state.segments) > 1:
            pieces = state.pieces[1]
            ptags = state.piece_tags[1]
            n = _peel_leading_titles(pieces, ptags, tokens)
            given_done = False
            for m in range(n, len(pieces)):
                # v1 walk order: the first non-title piece is ALWAYS
                # the given, before any suffix check --
                # 'Hardman, RN - CRNA' keeps first='RN'. One deliberate
                # 2.0 deviation, classified fix(comma-family): when that
                # piece is the segment's ONLY piece and unambiguously
                # suffix-shaped ('Andrews, M.D.'), it is a suffix -- v1
                # made it the given.
                if not given_done:
                    if (m == len(pieces) - 1
                            and _is_suffix_piece(pieces[m], ptags[m],
                                                 tokens)):
                        _set_roles(tokens, pieces[m], Role.SUFFIX)
                        continue
                    _set_roles(tokens, pieces[m], Role.GIVEN)
                    given_done = True
                    continue
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
                               ambiguities=tuple(ambiguities))
