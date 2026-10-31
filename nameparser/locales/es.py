"""The Spanish locale pack: it chooses the language ``es``, which turns
on the readings nameparser/vocab/es.toml writes ``default = false`` --
the courtesy, academic and professional titles that lead a name
(``Lic.``, ``Licenciada``, ``Doctora``, ``Profesora``, ``Mtro.``,
``Arq.``, ``Ingeniero``, ``Doña``) -- and prefers es.toml's readings
where another language's clash: ``Lic Juan Pérez`` gives title ``Lic``
where the default gives given ``Lic``. It reads two family names
(``Policy.two_family_names``, rules/O6), its policy patch compiled from
es.toml's [rules] table by tools/vocab/build.py: ``Gabriel García
Márquez`` gives family ``García Márquez``. And it carries the Spanish
given-name list as its lexicon fragment, ``Lexicon(given_names=...)``,
which keeps a given name out of the family: ``José Luis Pérez`` keeps
family ``Pérez`` (decisions/vocabulary-model, the 2026-10-30 phase 3g
entry).

Data sources: the titles' counts are on their readings in es.toml
(tools/name_usage.py and the local corpora); the given names are
nameparser/locales/_es_given_names.py's, derived from INE's 2025 census
tables (CC BY 4.0), whose docstring credits them.

Declared deviations (mechanisms.md#LOCALE-PACKS-PURE-DATA): the choice's
are derived, not declared -- the words whose compiled readings it
changes (``_reading_index.changed_words``), which the non-interference
gate in tests/v2/test_locales.py ors in -- so DEVIATES below declares
only what the patch and the fragment change.
"""
from __future__ import annotations

import unicodedata

from nameparser._lexicon import Lexicon
from nameparser._locale import Locale, rules_patch
from nameparser.locales._es_given_names import GIVEN_NAMES

ES = Locale(
    code="es",
    lexicon=Lexicon(given_names=GIVEN_NAMES),
    # nameparser/vocab/es.toml's [rules], compiled by tools/vocab/build.py
    policy=rules_patch("es"),
    languages=frozenset({"es"}),
)


def DEVIATES(name: str) -> bool:
    """True when this pack's patch or fragment may parse `name`
    differently from the default parser: rules/O6 acts only on a name
    of three or more name words, and the given-name list only where O6
    acts, so a name of three or more words, commas read as spaces, or of
    three or more runs of letters declares. Titles, suffixes and a
    family comma count here though O6 reads none of them, which
    over-declares, the safe direction."""
    pieces = name.replace(",", " ").split()
    return len(pieces) >= 3 or _letter_runs(name) >= 3


def _letter_runs(text: str) -> int:
    """The runs of letters in `text`, whatever separates one from the
    next: a hyphen, a zero-width space or an interpunct, which the
    tokenizer may read as separators (rules/T1, T2, T3). A run of Han,
    hangul or kana counts twice, since segmentation may divide it into a
    family and a given name (rules/W1). A letter written with a combining
    mark splits a run, which over-declares. Written with str methods
    rather than a pattern, since tests/v2/test_locales.py reads a
    module-level pattern as a marker regex to sweep."""
    runs, inside = 0, False
    for ch in text:
        letter = ch.isalpha()
        if letter and not inside:
            runs += 2 if unicodedata.name(ch, "").startswith(_CJK) else 1
        inside = letter
    return runs


_CJK = ("CJK", "HANGUL", "HIRAGANA", "KATAKANA")
