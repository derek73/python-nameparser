"""The Dutch locale pack: a choice of languages, ``nl``, and nothing
else -- no lexicon fragment and no policy patch
(mechanisms.md#LOCALE-PACKS-PURE-DATA; #1455). Choosing it turns on
nameparser/vocab/nl.toml's readings written ``default = false``: the
preposition ``ten`` (te den), so ``Jan ten Brink`` gives family
``ten Brink`` where the default gives middle ``ten``, family ``Brink``.
The default leaves ``ten`` to position because it is also a syllable of
Chinese given names, written between two words (``Kheng Ten Choo``),
which the particle would take into the family name under the pack too
(decisions/vocabulary-collisions, 2026-11-18 #1455). A ``Ten`` opening
a name stays the given name under the pack and reports the fork
(``Ten Kao Liu``), zh.toml declaring the given name, save under
``strict=True``, where zh.toml is not chosen and a leading ``Ten``
reads as the family name (``Ten Brink`` → family ``Ten Brink``).

The Dutch particles read by default (``van``, ``de``, ``ter``, ``oude``
and the rest) read the same with or without the pack.

On a word nl.toml holds a vocabulary reading of, other languages'
vocabulary readings leave: ``vd`` (van der, abbreviated) is then
Dutch's particle alone and no longer English's credential VD (the
Volunteer Decoration), so ``John Smith VD`` gives middle ``Smith``,
family ``VD`` where the default gives suffix ``VD``. A caller whose
names also carry the credential chooses ``en`` too.

Data sources: the readings' own entries in nameparser/vocab/nl.toml,
each with its issue and the vetting on its note; nothing is listed
here.

Deviations: derived, not declared. The words a choice of ``nl``
can move are ``_reading_index.changed_words``, which the
non-interference gate in tests/v2/test_locales.py reads
(decisions/deviates-registry), so this module carries no DEVIATES.
"""
from __future__ import annotations

from nameparser._lexicon import Lexicon
from nameparser._locale import Locale

NL = Locale(code="nl", lexicon=Lexicon.empty(),
            languages=frozenset({"nl"}))
