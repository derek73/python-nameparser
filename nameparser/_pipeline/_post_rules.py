"""Stage: post_rules.

Consumes: tokens (roles assigned), plus pieces and structure -- rule 1b
reads the opening piece of segment 0, or of segment 1 under a family
comma (#359). structure was always read here, for the rotation gate.
Produces: tokens with roles adjusted by the post rules.
Reads: Policy.patronymic_rules, Policy.middle_as_family;
Lexicon.given_name_titles.

Rules (each a small pure function over the role-bearing tokens):
1. v1 handle_firstnames: when the parse is exactly a title plus ONE
   given token (no other roles), and the title is not a given-name
   title ('Sir'), that token is a family name -- "Mr. Johnson".
1b. where a particle that is never a given name stands ALONE as a
   piece -- either opening the name or in the given position -- the
   name is left with no given name at all: the given and the middles
   fold into the family. Opening the name it pulls the rest of it in
   ("de la Vega"); in the given position it folds into the family
   beside it ("Mesnil de" under a family-first order). Needs another
   name token to fold into, so a bare "de" stays as it is. Alone among
   these rules it reads the opening position from `pieces` rather than
   from the roles assign left, so that shape holds for a lone leading
   particle piece under every name_order (#359).
2. EAST_SLAVIC (opt-in): positional GIVEN/MIDDLE/FAMILY each exactly
   one token, the FAMILY-position token carries an East Slavic
   patronymic ending, and the MIDDLE-position token does NOT (given +
   patronymic + patronymic-derived surname like Abramovich must not
   rotate) -> rotate: given<-old MIDDLE, middle<-old FAMILY (the
   patronymic), family<-old GIVEN (v1 parity, pinned live 2026-07-12).
3. TURKIC (opt-in): exactly 1 GIVEN + 2 MIDDLE + 1 FAMILY tokens and
   the FAMILY-position token is a standalone Turkic marker ->
   given<-first MIDDLE, middle<-(second MIDDLE, marker), family<-old
   GIVEN.

Both rotations fire only on Structure.NO_COMMA (v1 gates them on
`not self._had_comma`): a comma already established the family.

The rotations reconstruct token POSITION from roles, which is faithful
to v1 only under the default GIVEN_FIRST order; their interaction with
other name_order values is an open design question for the locale-pack
work (#270). Rule 1b read its particle the same way until #359 gave
it the position test as well, the decision there being that a
never-given particle keeps its particle whatever order the caller
declared.
"""
from __future__ import annotations

import dataclasses
import re

from nameparser._lexicon import _title_key
from nameparser._pipeline._state import ParseState, Structure, WorkToken
from nameparser._policy import PatronymicRule
from nameparser._types import FOLDED_TAG, Role

# Ported verbatim from v1 (nameparser/config/regexes.py) -- layering
# forbids the config import; keep in sync by hand.
_EAST_SLAVIC = re.compile(
    r"(ovich|ovna|evich|evna|ichna|ilyich|kuzmich|lukich|fomich|fokich)$",
    re.I)
_EAST_SLAVIC_CYR = re.compile(
    r"(ович|овна|евич|евна|ична|ильич|кузьмич|лукич|фомич|фокич)$",
    re.I)
_TURKIC = re.compile(
    r"^(oglu|oğlu|ogly|ogli|o['’ʻ]g['’ʻ]li"
    r"|qizi|qızı|kizi|kyzy|gyzy|uly|uulu)$", re.I)
_TURKIC_CYR = re.compile(
    r"^(оглу|оглы|оғлу|ўғли|угли|кызы|гызы|қызы|қизи|улы|ұлы|уулу)$", re.I)


_NAME_ROLES = (Role.GIVEN, Role.MIDDLE, Role.FAMILY)


def _idx(tokens: list[WorkToken], role: Role) -> list[int]:
    return [i for i, t in enumerate(tokens) if t.role is role]


def _leading_name_piece(state: ParseState,
                        tokens: list[WorkToken]) -> tuple[int, ...]:
    """The piece that OPENS the name, whatever role name_order gave it:
    the first piece holding a GIVEN, MIDDLE or FAMILY token, in the
    segment the positional read governs. Every piece holding none of
    those is walked past -- title and suffix pieces, but NICKNAME and
    MAIDEN as well, and anything assign left unroled -- and any number
    of them, not only a single leading title. The segment is 0, except
    under a family comma, where segment 0 is already fixed as the
    surname and the name continues in segment 1. Empty on either of
    two exits: that segment does not exist, or none of its pieces
    holds a name token."""
    seg = 1 if state.structure is Structure.FAMILY_COMMA else 0
    if seg >= len(state.pieces):
        return ()
    for piece in state.pieces[seg]:
        if any(tokens[i].role in _NAME_ROLES for i in piece):
            return piece
    return ()


def _retag(tokens: list[WorkToken], i: int, role: Role) -> None:
    tokens[i] = dataclasses.replace(tokens[i], role=role)


def post_rules(state: ParseState) -> ParseState:
    tokens = list(state.tokens)
    titles = _idx(tokens, Role.TITLE)
    givens = _idx(tokens, Role.GIVEN)
    middles = _idx(tokens, Role.MIDDLE)
    families = _idx(tokens, Role.FAMILY)
    others = any(t.role in (Role.SUFFIX, Role.NICKNAME, Role.MAIDEN)
                 for t in tokens)

    # rule 1: title + lone given -> family (v1 handle_firstnames)
    if titles and givens and not middles and not families and not others:
        joined = _title_key(tokens[i].text for i in titles)
        if joined not in state.lexicon.given_name_titles:
            for i in givens:
                _retag(tokens, i, Role.FAMILY)
            # every rule below reads these lists; recompute them the way
            # 1b does after its own fold, so no guard can inspect a name
            # that has already moved. Measured harmless today -- over the
            # 751 differential names in four policies this arm fires 48
            # times, and 1b fires on none of them -- but reading a stale
            # token list is the shape of the bug #359 fixed. `middles`
            # is empty by the guard above and recomputed anyway, so
            # relaxing that guard cannot leave it stale.
            givens = _idx(tokens, Role.GIVEN)
            middles = _idx(tokens, Role.MIDDLE)
            families = _idx(tokens, Role.FAMILY)

    # rule 1b enforces one invariant (v1 handle_non_first_name_prefix):
    # where a particle that is NEVER a given name stands ALONE as a
    # piece -- either opening the name, or in the given position -- the
    # name is left with no given name at all, the given and the middles
    # joining the family. Two shapes, one repair:
    #   * the particle OPENS the name, so the whole name is a surname
    #     and it pulls the rest in -- "de la Vega";
    #   * the particle is left ALONE in the given position, so it folds
    #     into the family beside it -- "Mesnil de" under
    #     name_order=FAMILY_FIRST, where the given position is the
    #     trailing piece.
    # A lone PIECE is the whole of it, which is a clause narrower than
    # "a member is never reported as the given name" -- that reading
    # would be false, and #359 blesses the first of its counterexamples
    # outright: "Juan de la Vega" under FAMILY_FIRST reports given='de
    # la Vega', "Sir de Mesnil" reports given='de Mesnil' in the
    # default order, and the degenerate bare 'de' keeps given='de'. In
    # each the particle is in a piece with something else, or has
    # nothing to fold into.
    # Those two sites are the whole scope, and the MIDDLE position is
    # deliberately not one of them -- which shows: "Mesnil Garcia de"
    # strands middle='de' under FAMILY_FIRST, while under
    # FAMILY_FIRST_GIVEN_LAST the same trailing piece IS the given
    # position, so it folds to family='Mesnil Garcia de'. Whether that
    # difference should stand is #365, not this rule's to settle. How
    # much the fold takes once it fires is the other open question:
    # "de Mesnil Juan" goes wholly to the family in every order,
    # matching the default rather than stopping at the particle group
    # (#364).
    # Only a never-given particle is in scope: an ambiguous one keeps
    # whatever reading name_order gives it -- 'van Gogh' is given
    # 'van' in the default order and family 'van' under a family-first
    # one -- and #360 tracks the vocabulary line.
    # The opening shape is read from `pieces` rather than from the role
    # assign left (#359). Under the default order the opening piece IS
    # the given, so the one role test used to catch both shapes; under
    # FAMILY_FIRST the opening piece is the family and the given sits
    # behind it, and reading the role alone let "de Mesnil" split. The
    # single-token test says the same thing in each shape: a particle
    # group already chained forward is not a lone particle. "Mr. de
    # Mesnil" is three tokens in two pieces -- the title alone, then
    # the particle GROUP -- so both sites are two tokens long and 1b
    # declines on each; the family reading there is rule 1's in the
    # default order and assign's under a family-first one. Both shapes
    # then need another name token to fold with, which leaves a
    # degenerate bare 'de' as it stands rather than inventing a
    # surname.
    sites = (_leading_name_piece(state, tokens), tuple(givens))
    if len(givens) + len(middles) + len(families) > 1 and any(
            len(site) == 1
            and "particle" in tokens[site[0]].tags
            and "vocab:particle-ambiguous" not in tokens[site[0]].tags
            for site in sites):
        for i in givens + middles:
            _retag(tokens, i, Role.FAMILY)
        # downstream rules key on the role counts: recompute
        givens = _idx(tokens, Role.GIVEN)
        middles = _idx(tokens, Role.MIDDLE)
        families = _idx(tokens, Role.FAMILY)

    # v1 gates both rotations on `not self._had_comma`; the
    # middle_as_family fold below runs comma or not (v1 order:
    # patronymics first, then handle_middle_name_as_last)
    rules = state.policy.patronymic_rules
    rotations_apply = state.structure is Structure.NO_COMMA
    if rotations_apply and PatronymicRule.EAST_SLAVIC in rules and \
            len(givens) == 1 and len(middles) == 1 and len(families) == 1:
        tail = tokens[families[0]].text
        mid = tokens[middles[0]].text
        if (_EAST_SLAVIC.search(tail) or _EAST_SLAVIC_CYR.search(tail)) \
                and not (_EAST_SLAVIC.search(mid)
                         or _EAST_SLAVIC_CYR.search(mid)):
            g, m, f = givens[0], middles[0], families[0]
            _retag(tokens, m, Role.GIVEN)
            _retag(tokens, f, Role.MIDDLE)
            _retag(tokens, g, Role.FAMILY)
    if rotations_apply and PatronymicRule.TURKIC in rules and \
            len(givens) == 1 and len(middles) == 2 and len(families) == 1:
        tail = tokens[families[0]].text
        if _TURKIC.match(tail) or _TURKIC_CYR.match(tail):
            g, m1, m2, f = givens[0], middles[0], middles[1], families[0]
            _retag(tokens, m1, Role.GIVEN)
            _retag(tokens, m2, Role.MIDDLE)
            _retag(tokens, f, Role.MIDDLE)
            _retag(tokens, g, Role.FAMILY)
    # rule 4: opt-in fold of middles into family (v1
    # handle_middle_name_as_last). v1 PREPENDED middle_list to
    # last_list; spans cannot reorder (anti-#100), so folded tokens
    # carry a tag and the family views order them first.
    if state.policy.middle_as_family:
        for i in _idx(tokens, Role.MIDDLE):
            tokens[i] = dataclasses.replace(
                tokens[i], role=Role.FAMILY,
                tags=tokens[i].tags | {FOLDED_TAG})
    return dataclasses.replace(state, tokens=tuple(tokens))
