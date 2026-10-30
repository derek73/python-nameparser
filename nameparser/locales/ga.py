"""The Irish locale pack: vocabulary-only -- it chooses the language
``ga``, which turns on the clan readings nameparser/vocab/ga.toml writes
``default = false``: ``nic`` (daughter of, beside ``mac``), the married
forms ``mhic`` and ``uí`` (of ``mac`` and ``ó``), and the genitive
``mic`` (decisions/vocabulary-model, the 2026-10-30 phase 3h entry).
Each is then a particle that joins the surname behind it:
``Máire Uí Bhriain`` gives family ``Uí Bhriain`` where the default
gives middle ``Uí``. ``nic`` and ``mic`` are given names too, so a
leading one stays the given name, reported (rules/P1).

Data sources: the counts on each reading in ga.toml (tools/name_usage.py,
ORCID's family box by country among them). The pack carries no lexicon
fragment and no policy patch.

Declared deviations (mechanisms.md#LOCALE-PACKS-PURE-DATA): a
vocabulary pack's deviations are derived, not declared -- the words
whose compiled readings its choice changes
(``_reading_index.changed_words``), which the non-interference gate in
tests/v2/test_locales.py reads -- so this module defines no DEVIATES.
"""
from __future__ import annotations

from nameparser._lexicon import Lexicon
from nameparser._locale import Locale

GA = Locale(
    code="ga",
    lexicon=Lexicon.empty(),
    languages=frozenset({"ga"}),
)
