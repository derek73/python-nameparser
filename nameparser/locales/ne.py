"""The Nepali locale pack: vocabulary-only -- it chooses the language
``ne``, which turns on the readings nameparser/vocab/ne.toml writes
``default = false``: the given-name readings of ``श्री``, ``guru`` and
``गुरु``, words the default reads as titles (decisions/vocabulary-model,
the 2026-10-30 phase 3d entry). Each is then a title only inside a
title phrase (rules/H9), so it reads as the given name at the head of a
name: ``श्री कृष्ण श्रेष्ठ`` gives given ``श्री`` where the default
gives title ``श्री``.

Data sources: nepal-candidates, Nepal's 2079 BS local election
candidates, each name written in Devanagari and romanized
(tools/differential/local_nepal.py); the counts are on the readings in
ne.toml. The pack carries no lexicon fragment and no policy patch.

Declared deviations (mechanisms.md#LOCALE-PACKS-PURE-DATA): a
vocabulary pack's deviations are derived, not declared -- the words
whose compiled readings its choice changes
(``_reading_index.changed_words``), which the non-interference gate in
tests/v2/test_locales.py reads -- so this module defines no DEVIATES.
"""
from __future__ import annotations

from nameparser._lexicon import Lexicon
from nameparser._locale import Locale

NE = Locale(
    code="ne",
    lexicon=Lexicon.empty(),
    languages=frozenset({"ne"}),
)
