"""Stage: post_rules.

Consumes: tokens (roles assigned).
Produces: tokens with roles adjusted by the post rules.
Reads: Policy.patronymic_rules; Lexicon.given_name_titles.

Rules (each a small pure function over the role-bearing tokens):
1. v1 handle_firstnames: when the parse is exactly a title plus ONE
   given token (no other roles), and the title is not a given-name
   title ('Sir'), that token is a family name -- "Mr. Johnson".
2. EAST_SLAVIC (opt-in): positional GIVEN/MIDDLE/FAMILY each exactly
   one token, the FAMILY-position token carries an East Slavic
   patronymic ending, and the MIDDLE-position token does NOT (given +
   patronymic + patronymic-derived surname like Abramovich must not
   rotate) -> rotate: given<-old MIDDLE, middle<-old FAMILY (the
   patronymic), family<-old GIVEN (v1 parity, pinned live).
3. TURKIC (opt-in): exactly 1 GIVEN + 2 MIDDLE + 1 FAMILY tokens and
   the FAMILY-position token is a standalone Turkic marker ->
   given<-first MIDDLE, middle<-(second MIDDLE, marker), family<-old
   GIVEN.

Both rotations fire only on Structure.NO_COMMA (v1 gates them on
`not self._had_comma`): a comma already established the family.
"""
from __future__ import annotations

import dataclasses
import re

from nameparser._lexicon import _normalize
from nameparser._pipeline._state import ParseState, Structure, WorkToken
from nameparser._policy import PatronymicRule
from nameparser._types import Role

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
    others = [t for t in tokens
              if t.role in (Role.SUFFIX, Role.NICKNAME, Role.MAIDEN)]

    # rule 1: title + lone given -> family (v1 handle_firstnames)
    if titles and givens and not middles and not families and not others:
        joined = " ".join(_normalize(tokens[i].text) for i in titles)
        if joined not in state.lexicon.given_name_titles:
            for i in givens:
                _retag(tokens, i, Role.FAMILY)

    # rule 1b: a leading particle that is NEVER a given name means the
    # whole name is a surname -- fold given (and middles) into family
    # (v1 handle_non_first_name_prefix; 'de la Vega' -> family, while
    # ambiguous 'van Gogh' keeps the given reading). The middle/family
    # guard leaves a degenerate bare 'de' as given rather than
    # inventing a surname.
    if len(givens) == 1 and (middles or families):
        gtags = tokens[givens[0]].tags
        if "particle" in gtags and "vocab:particle-ambiguous" not in gtags:
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
    if state.structure is not Structure.NO_COMMA:
        rules = frozenset()
    if PatronymicRule.EAST_SLAVIC in rules and \
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
    if PatronymicRule.TURKIC in rules and \
            len(givens) == 1 and len(middles) == 2 and len(families) == 1:
        tail = tokens[families[0]].text
        if _TURKIC.match(tail) or _TURKIC_CYR.match(tail):
            g, m1, m2, f = givens[0], middles[0], middles[1], families[0]
            _retag(tokens, m1, Role.GIVEN)
            _retag(tokens, m2, Role.MIDDLE)
            _retag(tokens, f, Role.MIDDLE)
            _retag(tokens, g, Role.FAMILY)
    # rule 4: opt-in fold of middles into family (v1
    # handle_middle_name_as_last; span order reproduces v1's prepend)
    if state.policy.middle_as_family:
        for i in _idx(tokens, Role.MIDDLE):
            _retag(tokens, i, Role.FAMILY)
    return dataclasses.replace(state, tokens=tuple(tokens))
