"""The Slovenian locale pack: a choice of languages, ``sl``, and nothing
else -- no lexicon fragment and no policy patch (3.0, phase 3f, #753;
mechanisms.md#LOCALE-PACKS-PURE-DATA). Choosing it turns on
nameparser/vocab/sl.toml's readings written ``default = false``: the
generations ``ml.`` (mlajši) and ``st.`` (starejši); on a word sl.toml
holds a vocabulary reading of, other languages' vocabulary readings
leave (`st`'s Saint title and particle, so ``St Clair`` is a given name
under this pack; a caller whose names also hold the English Saint
chooses ``fr`` too, whose only other word the choice changes is
``père``, as decisions/vocabulary-model's 2026-10-30 phase 3f entry
records).

Data sources: the readings' own entries in nameparser/vocab/sl.toml,
each with its issue and the vetting on its note; nothing is listed
here.

Deviations: derived, not declared. The words a choice of ``sl``
can move are ``_reading_index.changed_words``, which the
non-interference gate in tests/v2/test_locales.py reads
(decisions/deviates-registry), so this module carries no DEVIATES.
"""
from __future__ import annotations

from nameparser._lexicon import Lexicon
from nameparser._locale import Locale

SL = Locale(code="sl", lexicon=Lexicon.empty(),
            languages=frozenset({"sl"}))
