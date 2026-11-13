"""The Arabic locale pack: a choice of languages, ``ar``, and nothing
else -- no lexicon fragment and no policy patch
(mechanisms.md#LOCALE-PACKS-PURE-DATA; #1257). Choosing it turns on
nameparser/vocab/ar.toml's readings written ``default = false``: the
clan particle ``ben`` of Maghrebi family names, so ``Karim Ben Salah``
gives family ``Ben Salah`` where the default gives middle ``Ben``,
family ``Salah``. The default leaves ``ben`` to position because the
given name Ben, a British middle name too, stands where the particle
claim acts (``Adam Ben Robertson``); a ``Ben`` opening a name stays the
given name under the pack and reports the fork (``Ben Affleck``).

On a word ar.toml holds a vocabulary reading of, other languages'
vocabulary readings leave: ``abd`` is then Arabic's bound given name
alone and no longer English's credential ABD (All But Dissertation), so
``Jane Smith, ABD`` gives given ``ABD``, family ``Jane Smith`` where the
default gives suffix ``ABD``. A caller whose names also carry the
credential chooses ``en`` too.

Data sources: the readings' own entries in nameparser/vocab/ar.toml,
each with its issue and the vetting on its note; nothing is listed
here.

Deviations: derived, not declared. The words a choice of ``ar``
can move are ``_reading_index.changed_words``, which the
non-interference gate in tests/v2/test_locales.py reads
(decisions/deviates-registry), so this module carries no DEVIATES.
"""
from __future__ import annotations

from nameparser._lexicon import Lexicon
from nameparser._locale import Locale

AR = Locale(code="ar", lexicon=Lexicon.empty(),
            languages=frozenset({"ar"}))
