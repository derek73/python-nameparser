"""The Turkish/Azerbaijani locale pack (rule O2): policy-only
-- it turns on the TURKIC patronymic rule, its policy patch compiled
from nameparser/vocab/tr.toml's [rules] table by tools/vocab/build.py
(#754, 4f; one file for both languages, no az.toml existing, as
decisions/vocabulary-model's 4f entry records). The marker data (oglu/qizi/
uulu/kyzy and Cyrillic forms) lives beside the rule implementation, in
nameparser/_pipeline/_vocab.py's patterns, which _post_rules.py's
rotation and assemble's patronymic reading (rules/R9) both ask
(mirrors v1's flag design).

Data sources: the v1 Turkic patronymic rule (issue #185 and its test
bank, tests/test_turkic_patronymic_order.py); the pack carries no
vocabulary.

Declared deviations (mechanisms.md#LOCALE-PACKS-PURE-DATA):
applying this
pack changes only NO_COMMA names where some token is a standalone
Turkic patronymic marker -- DEVIATES(name) below is the
machine-readable declaration the non-interference gate checks.
"""
from __future__ import annotations

import re

from nameparser._lexicon import Lexicon
from nameparser._locale import Locale, rules_patch

TR_AZ = Locale(
    code="tr_az",
    lexicon=Lexicon.empty(),
    # nameparser/vocab/tr.toml's [rules], compiled by tools/vocab/build.py
    policy=rules_patch("tr"),
)

# Ported by hand from nameparser/_pipeline/_vocab.py's
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
