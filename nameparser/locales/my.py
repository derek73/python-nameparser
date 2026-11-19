"""The Burmese locale pack (#1231): a choice of the language ``my``, the
BCP 47 tag of Burmese (not the country code of Malaysia, whose language
is Malay, ``ms``), and nothing else. The choice turns on the readings
nameparser/vocab/my.toml writes ``default = false``: the honorifics
``U`` (Mr.) and ``Daw`` (Mrs.) written before a name, read as titles,
so ``U Thein Sein`` gives title ``U``, given ``Thein``, family ``Sein``
where the default gives given ``U``, middle ``Thein``.

Burmese names have no family name: every word is a personal name, and
the last one lands in ``family`` by position as it does in any name
read positionally. The title vocabulary reads ``U.`` with its full
stop as it reads ``U``, so a Western initial can be the title under
the pack too (``U. S. Grant`` gives title ``U.``, given ``S.``;
``Smith, U.`` and ``Dr. U. Smith`` give no given name), the accepted
cost and the reason to keep the pack to Burmese names; a bare ``U.``
between two name words stays an initial (``John U. Smith``). A title
and one name word reads the word as the family name, as everywhere
(rules/H1), so ``U Thant`` gives family ``Thant``.

**A list of nothing but Burmese names is read with the strict
choice**, ``parser_for(locales.MY, strict=True)`` (#1483): it reads no
other language's file, so the syllables Burmese names are written with
lose the particle and credential readings Spanish, Italian, Dutch or
English give them (``Aung San Win`` gives middle ``San``, family
``Win``; ``THEIN AUNG PE`` keeps family ``PE``), and the English ranks
and ``Sir`` such lists write are my.toml's own readings
(``Lt Gen``, ``Senior General``). The plain choice reads those
syllables as other languages do (``Aung San Win`` gives family ``San
Win``, as by default): it suits a list mixing Burmese names with
others, whose particles and credentials a strict choice would cost.

Left as name words: the honorifics ``Ko``, ``Ma`` and ``Maung``, which
are also name syllables (``Maung Maung Kyaw``), and the ethnic prefixes
``Saw``, ``Sai``, ``Nang``, ``Naw``, ``Khun`` and ``Mahn``; and the
military and religious styles (``Bogyoke``, ``Sayadaw``), each rare
(decisions/vocabulary-collisions, the 2026-11-19 #1231 entry).

Data sources: the honorifics' vetting is on the words in my.toml
(tools/name_usage.py); the strict choice was measured on OpenSanctions'
sanctions and PEP records of Myanmar and Wikidata's labels of people
with Myanmar citizenship, in decisions/vocabulary-collisions (the
2026-11-19 #1483 entry).

Declared deviations (mechanisms.md#LOCALE-PACKS-PURE-DATA): none. The
pack is nothing but a choice, whose words (``u`` and ``daw``) are
derived (``_reading_index.changed_words``), so it declares no
DEVIATES.
"""
from __future__ import annotations

from nameparser._lexicon import Lexicon
from nameparser._locale import Locale

MY = Locale(code="my", lexicon=Lexicon.empty(), languages=frozenset({"my"}))
