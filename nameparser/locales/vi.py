"""The Vietnamese locale pack: it reads a name family-first with the
given name last (``Policy.name_order``, FAMILY_FIRST_GIVEN_LAST), its
policy patch compiled from nameparser/vocab/vi.toml's [rules] table by
tools/vocab/build.py; it chooses the language ``vi``, which turns on
the readings vi.toml writes ``default = false`` (the academic titles
written before a name that are written as initials too, ``TS``, ``GS``,
``PGS``, and their stacked forms such as ``PGS.TS.``; ``ThS`` and the
office ``ĐBQH`` are read by default since #1115); and its
lexicon fragment takes out the particle, connective and credential
readings other languages give the syllables Vietnamese names are
written with, so ``Nguyen Van Anh`` gives family ``Nguyen``, middle
``Van``, given ``Anh`` where the Dutch ``van`` would chain into the
given name ``Van Anh``, and ``NGUYEN VAN DO`` keeps given ``DO`` where
the English credential would take it (decisions/vocabulary-model, the
2026-11-05 #1108 entry).

The fragment is the one pack content that removes: a choice prefers
only by a vocabulary reading, and a name reading never settles a clash
(decision 15 of decisions/vocabulary-model), so no reading vi.toml
could write makes ``van`` a name word under a plain choice. The order
already commits a caller to Vietnamese names, which keeps the removals'
cost to ``DO`` or ``BA`` written as a credential after a Vietnamese
name for English-language readers, with or without a comma (``Nguyen
Van Anh, DO`` reads family ``Nguyen Van Anh``, given ``DO``), and ``CHI``
without one (after a comma the capitals shape keeps a three-letter word
a suffix).

Data sources: the titles' vetting is on the words in vi.toml
(tools/name_usage.py); the syllables were measured on the uit-vinames
and vn-assembly local corpora, in the 2026-11-05 #1108 entry of
decisions/vocabulary-model.

Declared deviations (mechanisms.md#LOCALE-PACKS-PURE-DATA): the order
moves every name of two name words or more that a family comma does
not fix (a one-word name reads as ``Policy.lone_name_word`` names under
every order, given by default, rules/O5), and the fragment every name
holding one of its syllables, and the choice's titles and the
fragment's credentials reach comma names too (``Nguyen, Ts Van Anh``,
``Nguyen Van Anh, DO``), so DEVIATES below declares every name holding
a word. The choice's own words are derived
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
#: as a connective: Thế and Ý (rules/P8 already reads a bare capital Y
#: in a mixed-case name as an initial, so this reaches a lowercase y
#: there and any y in a name written in one case, ``NGUYEN THI Y NHI``)
_CONJUNCTIONS = ("the", "y")
#: and as a credential, which takes the given name of a name in one case
#: (``NGUYEN LINH CHI``): Đỗ, Bá, Chi
_CREDENTIALS = ("ba", "chi", "do")

VI = Locale(
    code="vi",
    lexicon=(Lexicon.empty()
             .remove(*_PARTICLES, kind="particle")
             .remove(*_CONJUNCTIONS, kind="conjunction")
             .remove(*_CREDENTIALS, kind="credential")),
    # nameparser/vocab/vi.toml's [rules], compiled by tools/vocab/build.py
    policy=rules_patch("vi"),
    languages=frozenset({"vi"}),
)


def DEVIATES(name: str) -> bool:
    """True when this pack may parse `name` differently from the
    default parser (the declared-deviation predicate the
    non-interference gate consumes): any name holding a letter or a
    digit, since the order moves every longer name a family comma does
    not fix, and the choice's titles and the fragment's credentials
    reach comma names too, so no narrower predicate is worth stating by
    hand."""
    return any(c.isalnum() for c in name)
