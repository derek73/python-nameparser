"""The European Portuguese locale pack: locales.PT for names from
Portugal, with two family names. It chooses ``pt-PT``, which selects
its ancestor pt.toml (nameparser/vocab/pt-PT.toml holds only the
[rules] table ``rules_patch`` reads, and no reading for a choice to
select), so it reads every word locales.PT reads
(``do`` a particle, ``da Piedade`` the second half of a compound given
name); it reads two family names (``Policy.two_family_names``,
rules/O6), its policy patch compiled from pt-PT.toml's [rules] table
by tools/vocab/build.py: ``Rui Sousa Pinto`` gives family ``Sousa
Pinto``, where locales.PT gives middle ``Sousa``; and it carries
nameparser/locales/_pt_given_names.py as its lexicon fragment, the
list locales.PT_BR carries, which keeps a given name out of the family:
``Ana Beatriz Costa`` keeps family ``Costa``. Cape Verdean and São
Toméan names read better under it than under locales.PT, Angolan and
Mozambican names worse (decisions/O6, the 2026-11-19 entry, which
measures it).

Data sources: the counts are on the readings in pt.toml; the given
names are measured on ORCID's public data file (CC0), whose credit the
list's module carries.

Declared deviations (mechanisms.md#LOCALE-PACKS-PURE-DATA): the choice's
are derived, as locales.PT's are, and the patch and the fragment act
only where rules/O6 does, so DEVIATES is rules/O6's declaration.
"""
from __future__ import annotations

from nameparser._lexicon import Lexicon
from nameparser._locale import Locale, deviates_by_two_family_names, rules_patch
from nameparser.locales._pt_given_names import GIVEN_NAMES

PT_PT = Locale(
    code="pt_pt",
    lexicon=Lexicon(given_names=GIVEN_NAMES),
    # nameparser/vocab/pt-PT.toml's [rules], the country's own: pt.toml,
    # the language's, holds none (decisions/O6, 2026-11-19)
    policy=rules_patch("pt-PT"),
    languages=frozenset({"pt-PT"}),
)


# rules/O6's declaration, which every pack turning O6 on shares
DEVIATES = deviates_by_two_family_names
