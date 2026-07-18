"""The Turkish/Azerbaijani locale pack (locales spec §3): policy-only
-- it turns on the TURKIC patronymic rule. The marker data (oglu/qizi/
uulu/kyzy and Cyrillic forms) lives inside the rule implementation in
nameparser/_pipeline/_post_rules.py (mirrors v1's flag design).

Data sources: the v1 Turkic patronymic rule (its plan and test bank);
the pack carries no vocabulary.

Declared deviations (spec §2 authoring requirement 3): applying this
pack changes only NO_COMMA names where some token is a standalone
Turkic patronymic marker -- DEVIATES(name) below is the
machine-readable declaration the non-interference gate checks.
"""
from __future__ import annotations

import re

from nameparser._lexicon import Lexicon
from nameparser._locale import Locale
from nameparser._policy import PatronymicRule, PolicyPatch

TR_AZ = Locale(
    code="tr_az",
    lexicon=Lexicon.empty(),
    policy=PolicyPatch(
        patronymic_rules=frozenset({PatronymicRule.TURKIC})),
)

# Ported by hand from nameparser/_pipeline/_post_rules.py's
# _TURKIC/_TURKIC_CYR (the rule is the source of truth; this predicate
# only DECLARES the deviation surface for the non-interference gate --
# layering forbids importing the pipeline from a pack). Keep both
# alternations byte-identical to those two patterns. Note both are
# fullmatch-shaped (^...$): the rule tests a single WHOLE token, so
# DEVIATES below scans per-token rather than searching the whole name.
_TURKIC = re.compile(
    r"^(oglu|oğlu|ogly|ogli|o['’ʻ]g['’ʻ]li"
    r"|qizi|qızı|kizi|kyzy|gyzy|uly|uulu)$", re.I)
_TURKIC_CYR = re.compile(
    r"^(оглу|оглы|оғлу|ўғли|угли|кызы|гызы|қызы|қизи|улы|ұлы|уулу)$", re.I)


def DEVIATES(name: str) -> bool:
    """True when this pack may parse `name` differently from the
    default parser (the declared-deviation predicate the
    non-interference gate consumes)."""
    return any(_TURKIC.match(tok) or _TURKIC_CYR.match(tok)
               for tok in name.split())
