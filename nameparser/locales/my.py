"""The Burmese locale pack (#1231): it chooses the language ``my``, the
BCP 47 tag of Burmese (not the country code of Malaysia, whose language
is Malay, ``ms``), which turns on the readings nameparser/vocab/my.toml
writes ``default = false``: the honorifics ``U`` (Mr.) and ``Daw``
(Mrs.) written before a name, read as titles, so ``U Thein Sein`` gives
title ``U``, given ``Thein``, family ``Sein`` where the default gives
given ``U``, middle ``Thein``. And its lexicon fragment takes out the
particle readings other languages give the syllables Burmese names are
written with, so ``Daw Aung San Suu Kyi`` gives middle ``San Suu``,
family ``Kyi`` where the Spanish ``san`` would take ``San Suu Kyi`` into
the family name. It also takes out ``do``'s credential reading, so a
name written in capitals keeps a final ``DO`` (``AUNG SAN DO`` gives
family ``DO``, where with ``san`` no particle the credential would end
the name).

Burmese names have no family name: every word is a personal name, and
the last one lands in ``family`` by position as it does in any name
read positionally. ``U.`` with its full stop stays an initial
(``U. S. Grant``), a one-letter word with a capital written with its
period being no title in any lexicon (rules/H11); a Burmese ``U.``
written so (``U. Thein Aung``) reads as the given name. A title and one name word
reads the word as the family name, as everywhere (rules/H1), so ``U
Thant`` gives family ``Thant``.

Left as name words: the honorifics ``Ko``, ``Ma`` and ``Maung``, which
are also name syllables (``Maung Maung Kyaw``), and the ethnic prefixes
``Saw``, ``Sai``, ``Nang``, ``Naw``, ``Khun`` and ``Mahn``; and the
military and religious styles (``Bogyoke``, ``Sayadaw``), each rare
(decisions/vocabulary-collisions, the 2026-11-19 #1231 entry).

The fragment removes readings, as ``locales.VI``'s does, the one kind
of pack content that may: a choice prefers only by a vocabulary reading, and a
name reading never settles a clash (decision 15 of
decisions/vocabulary-model), so no reading my.toml could write makes
``san`` a name word under a plain choice. The removals cost a caller who
applies the pack to names that are not Burmese those nine words'
particle readings in Spanish, Italian, Portuguese, French, Filipino,
Dutch and Māori surnames (``Juan de la Cruz`` keeps ``de la Cruz``,
``de`` not being among them, but ``Maria la Torre``, ``Jan van Dijk``
and ``Kiri Te Kanawa`` lose theirs) and the credential DO
(``Jane Doe, DO`` gives given ``DO``), the measured cost in the
decisions entry.

Data sources: the honorifics' vetting is on the words in my.toml
(tools/name_usage.py); the syllables were measured on OpenSanctions'
sanctions and PEP records of Myanmar and Wikidata's labels of people
with Myanmar citizenship, in the decisions entry.

Declared deviations (mechanisms.md#LOCALE-PACKS-PURE-DATA): the
choice's own words, ``u`` and ``daw``, are derived
(``_reading_index.changed_words``), which the non-interference gate in
tests/v2/test_locales.py ors in; DEVIATES below declares what the
fragment changes, every name holding one of its syllables as a word
(``do`` among them).
"""
from __future__ import annotations

from nameparser._lexicon import Lexicon
from nameparser._locale import Locale

#: Syllables of Burmese names that another language's file reads as a
#: particle: San (Aung San), La, Le, Do, Da, Du, Te, Di, and Van, a
#: syllable of Chin names (#1231)
_PARTICLES = ("da", "di", "do", "du", "la", "le", "san", "te", "van")

#: and as a credential, which the particle chain had kept from ending a
#: name written in capitals (``AUNG SAN DO``): Do
_CREDENTIALS = ("do",)

_SYLLABLES = frozenset(_PARTICLES + _CREDENTIALS)

MY = Locale(
    code="my",
    lexicon=(Lexicon.empty()
             .remove(*_PARTICLES, kind="particle")
             .remove(*_CREDENTIALS, kind="credential")),
    languages=frozenset({"my"}),
)


def DEVIATES(name: str) -> bool:
    """True when this pack's fragment may parse `name` differently from
    the default parser (the declared-deviation predicate the
    non-interference gate consumes): a name holding one of the
    syllables whose particle reading the fragment takes out as a word
    of its own, cut at every character that is no letter or digit, so
    the halves of a hyphenated or apostrophized word and a word written
    with its full stop count too (over-declaring, the safe direction).
    Cut without a pattern: the pack contract reads a module that
    imports ``re`` as one declaring by marker regex."""
    words = "".join(c if c.isalnum() else " " for c in name.lower()).split()
    return not _SYLLABLES.isdisjoint(words)
