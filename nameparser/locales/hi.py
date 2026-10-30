"""The Hindi locale pack: vocabulary-only -- it chooses the language
``hi``, which turns on the readings nameparser/vocab/hi.toml writes
``default = false``: the romanized salutations ``shri``, ``shrimati``,
``smt`` and ``shriyut``, which the default leaves to position because
each collides with given names where the Devanagari spelling cannot
(decisions/vocabulary-model, the 2026-10-30 phase 3e entry). Each is
then a title at the head of a name: ``Shri Narendra Modi`` gives title
``Shri`` where the default gives given ``Shri``. ``Shri`` is a
given-name element too (``Shri Kant Tripathi``), which reads the title
under the pack; that is the cost the choice takes.

Data sources: the counts on each reading in hi.toml (tools/name_usage.py,
ORCID's given and family boxes by country among them). The pack carries
no lexicon fragment and no policy patch.

Declared deviations (mechanisms.md#LOCALE-PACKS-PURE-DATA): a
vocabulary pack's deviations are derived, not declared -- the words
whose compiled readings its choice changes
(``_reading_index.changed_words``), which the non-interference gate in
tests/v2/test_locales.py reads -- so this module defines no DEVIATES.
"""
from __future__ import annotations

from nameparser._lexicon import Lexicon
from nameparser._locale import Locale

HI = Locale(
    code="hi",
    lexicon=Lexicon.empty(),
    languages=frozenset({"hi"}),
)
