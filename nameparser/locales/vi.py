"""The Vietnamese locale pack: it reads a name family-first with the
given name last (``Policy.name_order``, FAMILY_FIRST_GIVEN_LAST), its
policy patch compiled from nameparser/vocab/vi.toml's [rules] table by
tools/vocab/build.py; it chooses the language ``vi``, which turns on
the readings vi.toml writes ``default = false`` (the academic titles
written before a name, ``TS``, ``PGS`` and their stacked form
``PGS.TS.``); and its lexicon fragment takes out the particle and
connective readings other languages give the syllables Vietnamese names
are written with, so ``Nguyen Van Anh`` gives family ``Nguyen``, middle
``Van``, given ``Anh`` where the Dutch ``van`` would chain into the
given name ``Van Anh`` (decisions/vocabulary-model, the 2026-11-05
#1108 entry).

The fragment is the one pack content that removes: a choice prefers
only by a vocabulary reading, and a name reading never settles a clash
(decision 15 of decisions/vocabulary-model), so no reading vi.toml
could write makes ``van`` a name word under a plain choice. The order
already commits a caller to Vietnamese names, which is what makes the
removal cost nothing further.

Data sources: the titles' vetting is on the words in vi.toml
(tools/name_usage.py); the syllables were measured on the uit-vinames
and vn-assembly local corpora, in the 2026-11-05 #1108 entry of
decisions/vocabulary-model.

Declared deviations (mechanisms.md#LOCALE-PACKS-PURE-DATA): the order
moves every name a family comma does not fix, a one-word name included
(``Andrew`` reads family ``Andrew``), and the fragment every name
holding one of its syllables, so DEVIATES below declares every name
holding a word: a narrower declaration would restate the comma reading
by hand. The choice's own words are derived
(``_reading_index.changed_words``), which the non-interference gate in
tests/v2/test_locales.py ors in.
"""
from __future__ import annotations

from nameparser._lexicon import Lexicon
from nameparser._locale import Locale, rules_patch

#: Syllables of Vietnamese names that another language's file reads as
#: a particle: Văn, Lê, Đỗ, Du (Dư), Di, La, Thọ, Đa, unaccented, and
#: San, the saint particle
_PARTICLES = ("da", "di", "do", "du", "la", "le", "san", "tho", "van")
#: and as a connective: Thế and Ý
_CONJUNCTIONS = ("the", "y")

VI = Locale(
    code="vi",
    lexicon=(Lexicon.empty()
             .remove(*_PARTICLES, kind="particle")
             .remove(*_CONJUNCTIONS, kind="conjunction")),
    # nameparser/vocab/vi.toml's [rules], compiled by tools/vocab/build.py
    policy=rules_patch("vi"),
    languages=frozenset({"vi"}),
)


def DEVIATES(name: str) -> bool:
    """True when this pack may parse `name` differently from the
    default parser (the declared-deviation predicate the
    non-interference gate consumes): any name holding a letter or a
    digit, the order reading every name a family comma does not fix."""
    return any(c.isalnum() for c in name)
