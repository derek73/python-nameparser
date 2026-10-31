"""The Portuguese locale pack: vocabulary-only -- it chooses the
language ``pt``, which turns on the academic titles
nameparser/vocab/pt.toml writes ``default = false`` (``Doutor``,
``Doutora``, ``Professora``, ``Profa.``) and prefers pt.toml's readings
where another language's clash: ``do`` the particle, not the DO
credential, and ``e`` the connective even in a name written in one
case, while ``Sr`` keeps both readings, Senhor in front and the
generation behind, as the default reads it (decisions/vocabulary-model,
the 2026-10-30 phase 3g entry). ``Doutor João Silva`` gives title
``Doutor`` where the default gives given ``Doutor``. locales.PT_BR
chooses ``pt-BR``, which selects ``pt`` too, so it reads all of these
the same way.

Data sources: the counts are on the readings in pt.toml
(tools/name_usage.py and the local corpora). The pack carries no
lexicon fragment and no policy patch.

Declared deviations (mechanisms.md#LOCALE-PACKS-PURE-DATA): a
vocabulary pack's deviations are derived, not declared -- the words
whose compiled readings its choice changes
(``_reading_index.changed_words``), which the non-interference gate in
tests/v2/test_locales.py reads -- so this module defines no DEVIATES.
"""
from __future__ import annotations

from nameparser._lexicon import Lexicon
from nameparser._locale import Locale

PT = Locale(
    code="pt",
    lexicon=Lexicon.empty(),
    languages=frozenset({"pt"}),
)
