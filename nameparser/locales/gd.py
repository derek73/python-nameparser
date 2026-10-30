"""The Scottish Gaelic locale pack: vocabulary-only -- it chooses the
language ``gd``, which turns on the clan reading
nameparser/vocab/gd.toml writes ``default = false``: ``nic`` (daughter
of, beside ``mac``), written spaced (decisions/vocabulary-model, the
2026-10-30 phase 3h entry). It is then a particle that joins the
surname behind it: ``Màiri Nic Leòid`` gives family ``Nic Leòid`` where
the default gives middle ``Nic``. The genitive ``mhic``, which the
Irish pack turns on, is left out: in Scottish Gaelic it mostly links a
patronymic chain, which a second particle would split (gd.toml's note).
``Nic`` is a given name too (its reading is in ga.toml, and holds in
every choice), so a leading Nic stays the given name in a name read
given-first, reported (rules/P1), as ``Mac`` does by default.

Data sources: the counts on each reading in ga.toml and gd.toml
(tools/name_usage.py). The pack carries no lexicon fragment and no
policy patch.

Declared deviations (mechanisms.md#LOCALE-PACKS-PURE-DATA): a
vocabulary pack's deviations are derived, not declared -- the words
whose compiled readings its choice changes
(``_reading_index.changed_words``), which the non-interference gate in
tests/v2/test_locales.py reads -- so this module defines no DEVIATES.
"""
from __future__ import annotations

from nameparser._lexicon import Lexicon
from nameparser._locale import Locale

GD = Locale(
    code="gd",
    lexicon=Lexicon.empty(),
    languages=frozenset({"gd"}),
)
