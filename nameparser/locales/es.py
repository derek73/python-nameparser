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

from nameparser._lexicon import Lexicon
from nameparser._locale import Locale, deviates_by_two_family_names, rules_patch
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
    differently from the default parser: rules/O6's declaration, which
    the cs and sk packs share (_locale.deviates_by_two_family_names);
    the given-name list acts only where O6 does, so it declares
    nothing more."""
    return deviates_by_two_family_names(name)
