"""The Brazilian Portuguese locale pack: vocabulary-only -- it chooses
the language ``pt-BR``, which selects nameparser/vocab/pt-BR.toml and
its ancestor pt.toml, and turns on the agnomen reading pt-BR.toml
writes ``default = false``: ``SB``, Sobrinho abbreviated as Brazilian
filings write it, which outside Brazil is the S.B. degree
(decisions/vocabulary-model, the 2026-10-30 phase 3h entry). It is then
gated by the count as ``sobrinho`` is (rules/S11): ``JOSE CARLOS SILVA
SB`` gives suffix ``SB`` where the default gives family ``SB``. The
single letters ``F`` and ``N`` the same filings write for Filho and
Neto stay out, the pack included: in those filings the letter more
often abbreviates a surname (pt-BR.toml's exclusions).
Choosing ``pt-BR`` also chooses ``pt``, whose readings it prefers where
another language's clash (``do`` a particle, not the DO credential),
and whose ``default = false`` titles it turns on as locales.PT does
(``Doutor``, ``Doutora``, ``Professora``, ``Profa.``, since phase 3g).

Data sources: tse-donors, Brazilian candidates' receipts as filed beside
the registry's spelling (tools/differential/local_tse.py); the counts
are on the readings in pt-BR.toml. The pack carries no lexicon fragment
and no policy patch.

Declared deviations (mechanisms.md#LOCALE-PACKS-PURE-DATA): a
vocabulary pack's deviations are derived, not declared -- the words
whose compiled readings its choice changes
(``_reading_index.changed_words``), which the non-interference gate in
tests/v2/test_locales.py reads -- so this module defines no DEVIATES.
"""
from __future__ import annotations

from nameparser._lexicon import Lexicon
from nameparser._locale import Locale

PT_BR = Locale(
    code="pt_br",
    lexicon=Lexicon.empty(),
    languages=frozenset({"pt-BR"}),
)
