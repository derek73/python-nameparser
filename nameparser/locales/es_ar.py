"""The Argentine Spanish locale pack: locales.ES with a longer given-name
list. It chooses ``es-AR``, which selects nameparser/vocab/es.toml (no
es-AR.toml exists: a tag selects its own file and its ancestors'), reads
two family names as locales.ES does (``Policy.two_family_names``,
rules/O6, es.toml's [rules] table), and carries
nameparser/locales/_es_ar_given_names.py as its lexicon fragment, a list
that keeps the second given name Argentine names write before one
surname out of the family: ``Pablo Sebastián Rosales`` gives family
``Rosales`` where locales.ES gives ``Sebastián Rosales``, and ``Ana
García López`` gives family ``García López`` under both
(decisions/O6, the 2026-11-04 entry, which measures it).

Data sources: the given names are INE's 2025 census tables (CC BY 4.0),
whose credit the list's module carries.

Declared deviations (mechanisms.md#LOCALE-PACKS-PURE-DATA): the choice's
are derived, as locales.ES's are, and the patch and the fragment act
only where rules/O6 does, so DEVIATES is rules/O6's declaration.
"""
from __future__ import annotations

from nameparser._lexicon import Lexicon
from nameparser._locale import Locale, deviates_by_two_family_names, rules_patch
from nameparser.locales._es_ar_given_names import GIVEN_NAMES

ES_AR = Locale(
    code="es_ar",
    lexicon=Lexicon(given_names=GIVEN_NAMES),
    # nameparser/vocab/es.toml's [rules], the language's own: Argentina
    # writes two family names often enough that O6 stays on
    policy=rules_patch("es"),
    languages=frozenset({"es-AR"}),
)


def DEVIATES(name: str) -> bool:
    """True when this pack's patch or fragment may parse `name`
    differently from the default parser: rules/O6's declaration, which
    every pack turning O6 on shares (_locale.deviates_by_two_family_names);
    the given-name list acts only where O6 does, so it declares nothing
    more."""
    return deviates_by_two_family_names(name)
