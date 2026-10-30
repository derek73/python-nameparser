"""The Bengali locale pack: vocabulary-only -- it chooses the language
``bn``, which turns on the readings nameparser/vocab/bn.toml writes
``default = false``: the romanized salutations ``shri``, ``shrimati``
and ``smt`` and the academic title ``adhyapak`` (professor), which the
default leaves to position because each collides with a name where the
Bengali spelling cannot (decisions/vocabulary-model, the 2026-10-30
phase 3e entry). Each is then a title at the head of a name:
``Adhyapak Anisuzzaman`` gives title ``Adhyapak`` where the default
gives given ``Adhyapak``. ``Adhyapak`` is a Marathi family name too,
which keeps its place at the end of a name under the pack.

Data sources: the counts on each reading in bn.toml and hi.toml
(tools/name_usage.py, ORCID's given and family boxes by country among
them). The pack carries no lexicon fragment and no policy patch.

Declared deviations (mechanisms.md#LOCALE-PACKS-PURE-DATA): a
vocabulary pack's deviations are derived, not declared -- the words
whose compiled readings its choice changes
(``_reading_index.changed_words``), which the non-interference gate in
tests/v2/test_locales.py reads -- so this module defines no DEVIATES.
"""
from __future__ import annotations

from nameparser._lexicon import Lexicon
from nameparser._locale import Locale

BN = Locale(
    code="bn",
    lexicon=Lexicon.empty(),
    languages=frozenset({"bn"}),
)
