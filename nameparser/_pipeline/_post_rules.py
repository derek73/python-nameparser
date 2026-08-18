"""Stage: post_rules.

Consumes: tokens (roles assigned), plus pieces and structure -- the
particle fold reads the opening piece of segment 0, or of segment 1
under a family comma (#359). structure was always read here, for the
rotation gate.
Produces: tokens with roles adjusted by the post rules.
Reads: Policy.patronymic_rules, Policy.middle_as_family;
Lexicon.given_name_titles.

Implements rules H1, P1, O1, O2 and O3 of docs/design/rules.md; each
is cited at its code below, and P1/O1/O2's history lives in
docs/design/decisions.md.
"""
from __future__ import annotations

import dataclasses
import re

from nameparser._lexicon import _title_key
from nameparser._pipeline._assign import _name_positions
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


# rules.md#P2: "a particle joins the words after it into one name
# part, the join running until the next particle starts a group of
# its own or the name ends"
# rules.md#P3: "the joined part is ONE name word wherever another
# rule counts them"
# rules.md#P5: "a recognized bound given-name word joins the word
# after it into one given name"
def _unit_end(tokens: list[WorkToken], idx: list[int], i: int) -> int:
    """One past the end of the unit starting at `idx[i]`.

    RECURSIVE, and that is the whole point: what a conjunction or a
    bound given-name word joins is the next UNIT, not the next word.
    Absorbing a single index instead strands a particle at the end of
    the unit, severed from the words it chains -- "de la Vega y la
    Vega" cut between `la` and `Vega`, reporting family
    "de la Vega y la", which is the same defect as a bare particle
    opening the given name, mirrored."""
    if "particle" in tokens[idx[i]].tags:
        j = i
        while j + 1 < len(idx) and "particle" in tokens[idx[j + 1]].tags:
            j += 1
        # ... then the words it joins, stopping where the next
        # particle starts a group of its own, at a suffix word (the
        # stop _group's chain uses), or at a conjunction, which the
        # shared loop below joins to the whole unit after it rather
        # than to the one word after it.
        while (j + 1 < len(idx)
               and "particle" not in tokens[idx[j + 1]].tags
               and "conjunction" not in tokens[idx[j + 1]].tags
               and "vocab:suffix" not in tokens[idx[j + 1]].tags):
            j += 1
        end = j + 1
    else:
        end = i + 1
        if "vocab:bound-given" in tokens[idx[i]].tags and end < len(idx):
            end = _unit_end(tokens, idx, end)
    while end + 1 < len(idx) and "conjunction" in tokens[idx[end]].tags:
        end = _unit_end(tokens, idx, end + 1)
    return end


def _units(tokens: list[WorkToken], idx: list[int]) -> list[list[int]]:
    """`idx` split into the units other rules COUNT: one name word
    each, except where another rule has already made several words one
    name. Three do -- a particle and the words it chains, a
    conjunction-joined run, and a bound given-name word with the word
    it completes -- so `van der Berg` and `abdul Rahman` are each one
    unit and the fold cannot leave half of either behind.

    Read off the TAGS rather than the pieces, for two different
    reasons. A conjunction join grouping DID build and the prefix
    chain then swallowed: "de la Vega y Santos Juan" reaches this as
    [de][la Vega y Santos Juan], the ambiguous particle having chained
    forward over the join, so the join's own boundary is gone. (The
    leading particle keeps its piece -- it has to, or the fold's
    lone-piece site test would not fire at all.) The bound-given join grouping
    never built at all: P5 joins only where the bound word is the
    first non-title piece, and at a fold site the first piece is the
    particle -- "ibn Awf abdul Rahman" reaches here as four separate
    pieces. The tag is the only witness in both cases.

    The particle chain is what keeps this partition agreeing with the
    one `assign` reads off pieces: strip the folded run and `assign`
    gives the same tail one role, so the fold must not hand its words
    out separately."""
    units: list[list[int]] = []
    i = 0
    while i < len(idx):
        end = _unit_end(tokens, idx, i)
        units.append(list(idx[i:end]))
        i = end
    return units


def _fold_reach(tokens: list[WorkToken], name_idx: list[int]) -> int:
    """How many of `name_idx` the fold takes: the particle run, plus
    the one name word it attaches to -- one UNIT, so a conjunction
    join goes whole ("de la Vega y Santos Juan" keeps Vega y Santos
    together). All of them when the name is nothing but particles."""
    i = 0
    while i < len(name_idx) and "particle" in tokens[name_idx[i]].tags:
        i += 1
    if i == len(name_idx):
        return i
    return i + len(_units(tokens, name_idx[i:])[0])


def _is_lone_never_given_particle(site: tuple[int, ...],
                                  tokens: list[WorkToken]) -> bool:
    return (len(site) == 1
            and "particle" in tokens[site[0]].tags
            and "vocab:particle-ambiguous" not in tokens[site[0]].tags)


def post_rules(state: ParseState) -> ParseState:
    tokens = list(state.tokens)
    titles = _idx(tokens, Role.TITLE)
    givens = _idx(tokens, Role.GIVEN)
    middles = _idx(tokens, Role.MIDDLE)
    families = _idx(tokens, Role.FAMILY)
    others = any(t.role in (Role.SUFFIX, Role.NICKNAME, Role.MAIDEN)
                 for t in tokens)

    # rules.md#H1: "a title followed by exactly one name word and
    # nothing else makes that word the family name, unless the title
    # is a given-name title" (v1 handle_firstnames)
    if titles and givens and not middles and not families and not others:
        joined = _title_key(tokens[i].text for i in titles)
        if joined not in state.lexicon.given_name_titles:
            for i in givens:
                _retag(tokens, i, Role.FAMILY)
            # every rule below reads these lists; recompute after any
            # retag so no guard can inspect a name that has already
            # moved -- a stale index list is the bug shape #359 fixed
            givens = _idx(tokens, Role.GIVEN)
            middles = _idx(tokens, Role.MIDDLE)
            families = _idx(tokens, Role.FAMILY)

    # rules.md#P1: "a never-given particle standing alone where the
    # given name would go — or opening the name — marks the name as
    # surname-only: the particle run and the name words it attaches
    # to are the family." (v1 handle_non_first_name_prefix; history:
    # decisions.md#P1)
    # How far the fold reaches depends on the order the name was READ
    # under (#395; decisions.md#P1, 2026-08-17): declaring a
    # family-first order asserts that what follows the family is not
    # more surname, which is the very question of where the run stops.
    # Under that declaration the run takes its own particles and ONE
    # name word; under the default order it keeps taking the rest of
    # the name, nothing having marked where the surname ends. The
    # narrowing is the LEADING site's alone: a particle
    # standing in the given slot keeps the old reach. Note what
    # actually holds the family-comma shape back, since it is NOT
    # that test -- "Smith, de Mesnil Juan" DOES fire the leading site,
    # segment 1 opening with the particle. It keeps the old reach
    # because assign records no order after a family comma, the comma
    # having already fixed the surname, so `order is None` here.
    # Anything that later gives that path an order turns the
    # narrowing on for it.
    # Code-local: a lone PIECE is the test at both sites, so a
    # particle group already chained forward is not a lone particle,
    # and rule H1 above cannot be what produces the fold's family
    # reading -- H1 is gated on `not families`.
    lead = _leading_name_piece(state, tokens)
    lead_fires = _is_lone_never_given_particle(lead, tokens)
    sites_fire = lead_fires or _is_lone_never_given_particle(
        tuple(givens), tokens)
    if len(givens) + len(middles) + len(families) > 1 and sites_fire:
        order = state.order
        if lead_fires and order is not None and order[0] is Role.FAMILY:
            # `state.order`, not policy.name_order: a script_orders
            # entry can put the family first under a given-first
            # policy, and the roles below have to match the read
            # assign actually made.
            name_idx = sorted(givens + middles + families)
            cut = _fold_reach(tokens, name_idx)
            for i in name_idx[:cut]:
                _retag(tokens, i, Role.FAMILY)
            # What is left is a shorter name of the same order: one
            # family already placed, so drop that slot and lay the
            # rest out as _name_positions would for n + 1 pieces.
            rest = _units(tokens, name_idx[cut:])
            for unit, role in zip(rest, _name_positions(
                    order, len(rest) + 1)[1:]):
                for i in unit:
                    _retag(tokens, i, role)
        else:
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
    # rules.md#O1: "a name of exactly three name words — titles,
    # suffixes and nicknames aside — whose last name word carries a
    # patronymic ending and whose middle name word does not reads as
    # family-first" (history: decisions.md#O1)
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
    # rules.md#O2: "a name of exactly four name words — titles,
    # suffixes and nicknames aside — ending in a standalone
    # patronymic marker reads family-first: the first name word is
    # the family name" (history: decisions.md#O2)
    if rotations_apply and PatronymicRule.TURKIC in rules and \
            len(givens) == 1 and len(middles) == 2 and len(families) == 1:
        tail = tokens[families[0]].text
        if _TURKIC.match(tail) or _TURKIC_CYR.match(tail):
            g, m1, m2, f = givens[0], middles[0], middles[1], families[0]
            _retag(tokens, m1, Role.GIVEN)
            _retag(tokens, m2, Role.MIDDLE)
            _retag(tokens, f, Role.MIDDLE)
            _retag(tokens, g, Role.FAMILY)
    # rules.md#O3: "every middle word joins the family name and is
    # rendered before it" (v1 handle_middle_name_as_last). v1
    # PREPENDED middle_list to last_list; mechanisms.md#FOLDED_TAG:
    # "tokens never move: a rule that needs different rendering order
    # tags the token, and the rendering views consult the tag"
    if state.policy.middle_as_family:
        for i in _idx(tokens, Role.MIDDLE):
            tokens[i] = dataclasses.replace(
                tokens[i], role=Role.FAMILY,
                tags=tokens[i].tags | {FOLDED_TAG})
    return dataclasses.replace(state, tokens=tuple(tokens))
