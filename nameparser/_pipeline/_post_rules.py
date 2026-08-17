"""Stage: post_rules.

Consumes: tokens (roles assigned), plus structure for the rotation
gate.
Produces: tokens with roles adjusted by the post rules.
Reads: Policy.patronymic_rules, Policy.middle_as_family;
Lexicon.given_name_titles.

Implements rules H1, P1, O1, O2 and O3 of docs/design/rules.md; each
is cited at its code below, and P1/O1/O2's history lives in
docs/design/decisions.md.

P1 is SPLIT across two stages as of #390, and the split is the rule's
own shape rather than an accident: a leading particle CLAIMS the
family before positions exist, so that half lives in assign; a lone
particle that positioning has already dropped into the GIVEN role can
only be seen afterwards, so that half stays here. The pieces scan the
leading half used (`_leading_name_piece`, and with it the reading of
state.pieces) went with it -- assign reaches the same piece by peeling
titles before it counts name pieces.
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


def _idx(tokens: list[WorkToken], role: Role) -> list[int]:
    return [i for i, t in enumerate(tokens) if t.role is role]


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
    # surname-only: the particle run and the one name word it
    # attaches to are the family, and any name words beyond that
    # read by position." (v1 handle_non_first_name_prefix; history:
    # decisions.md#P1)
    # This is P1's SECOND site only. The opening-the-name half moved to
    # assign in #390, where the claim can happen before positions are
    # handed out; what is left here is the case assign cannot see --
    # a lone particle that positional assignment has already dropped
    # into the GIVEN role (Mesnil de under FAMILY_FIRST). It has no
    # piece after it to attach to, so the fold is backward and the
    # whole remainder is one word anyway.
    # Code-local: a lone TOKEN in the given role is the test, so a
    # particle group already chained forward never reaches it, and
    # rule H1 above cannot be what produces this family reading --
    # H1 is gated on `not families`.
    site = tuple(givens)
    if len(givens) + len(middles) + len(families) > 1 and (
            len(site) == 1
            and "particle" in tokens[site[0]].tags
            and "vocab:particle-ambiguous" not in tokens[site[0]].tags):
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
