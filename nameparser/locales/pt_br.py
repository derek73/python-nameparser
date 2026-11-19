"""The Brazilian Portuguese locale pack. It chooses the language
``pt-BR``, which selects nameparser/vocab/pt-BR.toml and its ancestor
pt.toml, and turns on the agnomen reading pt-BR.toml writes
``default = false``: ``SB``, Sobrinho abbreviated as Brazilian filings
write it, which outside Brazil is the S.B. degree
(decisions/vocabulary-model, the 2026-10-30 phase 3h entry). It is then
gated by the count as ``sobrinho`` is (rules/S11): ``JOSE CARLOS SILVA
SB`` gives suffix ``SB`` where the default gives family ``SB``. The
single letters ``F`` and ``N`` the same filings write for Filho and
Neto stay out, the pack included: in those filings the letter more
often abbreviates a surname (pt-BR.toml's exclusions).
Choosing ``pt-BR`` also chooses ``pt``, whose readings it prefers where
another language's clash (``do`` a particle, not the DO credential),
as locales.PT does; pt's titles (``Doutor``, ``Professora``) are read
by default since #1115.

It reads two family names (``Policy.two_family_names``, rules/O6), its
policy patch compiled from pt-BR.toml's [rules] table by
tools/vocab/build.py: ``Ana Souza Lima`` gives family ``Souza Lima``.
And it carries the Portuguese given-name list as its lexicon fragment,
``Lexicon(given_names=...)``, which keeps a given name out of the
family: ``Ana Beatriz Costa`` keeps family ``Costa``. locales.PT, the
pack chosen by language, turns neither on, since Angolan and
Mozambican names lose under the switch (decisions/O6, the 2026-11-19
entry).

Data sources: tse-donors, Brazilian candidates' receipts as filed beside
the registry's spelling (tools/differential/local_tse.py); the counts
are on the readings in pt-BR.toml. The given names are
nameparser/locales/_pt_given_names.py's, measured on ORCID's public
data file (CC0), whose docstring credits it.

Declared deviations (mechanisms.md#LOCALE-PACKS-PURE-DATA): the choice's
are derived, not declared -- the words whose compiled readings it
changes (``_reading_index.changed_words``), which the non-interference
gate in tests/v2/test_locales.py ors in -- and the patch and the
fragment act only where rules/O6 does, so DEVIATES is rules/O6's
declaration.
"""
from __future__ import annotations

from nameparser._lexicon import Lexicon
from nameparser._locale import Locale, deviates_by_two_family_names, rules_patch
from nameparser.locales._pt_given_names import GIVEN_NAMES

PT_BR = Locale(
    code="pt_br",
    lexicon=Lexicon(given_names=GIVEN_NAMES),
    # nameparser/vocab/pt-BR.toml's [rules], the country's own: pt.toml,
    # the language's, holds none (decisions/O6, 2026-11-19)
    policy=rules_patch("pt-BR"),
    languages=frozenset({"pt-BR"}),
)


# rules/O6's declaration, which every pack turning O6 on shares
DEVIATES = deviates_by_two_family_names
