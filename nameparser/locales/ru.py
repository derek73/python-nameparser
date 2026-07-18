"""The Russian locale pack (locales spec §3): policy-only -- it turns
on the EAST_SLAVIC patronymic rule. The morphology data (-ovich/-ovna
endings, Cyrillic and transliterated) lives inside the rule
implementation in nameparser/_pipeline/_post_rules.py, not in the
Lexicon (mirrors v1's patronymic_name_order flag design, v1.3.0).
Cyrillic titles/conjunctions are default-lexicon vocabulary (#269),
not pack data (spec §2 sorting rule).

Data sources: the v1.3.0 patronymic rule (PR #154 discussion and the
east-slavic test bank); no external lists -- the pack itself carries
no vocabulary.

Declared deviations (spec §2 authoring requirement 3): applying this
pack changes only NO_COMMA names whose final token carries an East
Slavic patronymic ending while the middle token does not --
DEVIATES(name) below is the machine-readable declaration the
non-interference gate checks.
"""
from __future__ import annotations

import re

from nameparser._lexicon import Lexicon
from nameparser._locale import Locale
from nameparser._policy import PatronymicRule, PolicyPatch

RU = Locale(
    code="ru",
    lexicon=Lexicon.empty(),
    policy=PolicyPatch(
        patronymic_rules=frozenset({PatronymicRule.EAST_SLAVIC})),
)

# Ported by hand from nameparser/_pipeline/_post_rules.py's
# _EAST_SLAVIC/_EAST_SLAVIC_CYR (the rule is the source of truth; this
# predicate only DECLARES the deviation surface for the non-interference
# gate -- layering forbids importing the pipeline from a pack). Keep
# both alternations byte-identical to those two patterns.
_EAST_SLAVIC = re.compile(
    r"(ovich|ovna|evich|evna|ichna|ilyich|kuzmich|lukich|fomich|fokich)$",
    re.I)
_EAST_SLAVIC_CYR = re.compile(
    r"(ович|овна|евич|евна|ична|ильич|кузьмич|лукич|фомич|фокич)$", re.I)


def DEVIATES(name: str) -> bool:
    """True when this pack may parse `name` differently from the
    default parser (the declared-deviation predicate the
    non-interference gate consumes)."""
    # Scan per token: the rule fires on the family-POSITION token, not
    # the name's final characters, so a whole-string search would miss
    # 'Ivan Petr Sidorovich Jr.' (a suffix after the ending -> the $
    # anchor never lands: under-declaration, the unsafe direction for
    # the gate). Per-token scanning instead OVER-declares (e.g.
    # 'Sidorovich Anna' matches though the rule's 1+1+1 shape never
    # fires) -- the safe direction: DEVIATES may claim more than the
    # rule changes, never less.
    return any(_EAST_SLAVIC.search(tok) or _EAST_SLAVIC_CYR.search(tok)
               for tok in name.split())
