"""The Malay locale pack (#1179): a choice of the language ``ms``, and
nothing else. The choice turns on the readings nameparser/vocab/ms.toml
writes ``default = false``: the salutations ``Puan`` (Mrs.) and ``Cik``
(Miss), the religious teachers' titles ``Ustaz`` and ``Ustazah``, and
``Cikgu`` (teacher), each then a title at the head of a name: ``Puan
Siti binti Ahmad`` gives title ``Puan``, given ``Siti`` where the
default gives given ``Puan``. It turns on the honours too (#1180):
``Tun``, ``Haji``, ``Dato`` written without its apostrophe, and the
phrases ``Tan Sri`` and ``Puan Sri``, each a title addressing the given
name (``Tan Sri Ahmad bin Ali`` gives title ``Tan Sri``, given
``Ahmad``). ``Encik`` (Mr.) and the honours ``Datuk``, ``Dato'``,
``Datin`` and ``Hajah`` are titles by default already. Each is off by
default because a word of it is a name elsewhere (``Puan``, an
Indonesian given name, as in ``Puan Maharani``; ``Tun`` and ``Tan``,
Chinese surnames; ``Sri``, an Indonesian and Indian given name;
``Haji``, a given name and a surname; ``Dato``, an Italian surname and
a Georgian given name) or is written so only in Malaysian lists. ``Tan`` and
``Sri`` are each a title only in its phrase (rules/H9), so a name
opening with either and no phrase stays a name word under the pack and
reports the title it might be (``Tan Chee Chai`` reads given ``Tan``);
a style before either makes a phrase of its own (``Hon. Tan Ah Kow``
gives title ``Hon. Tan``).

``Tuan`` is left a name word under the pack too: Malaysians who file
their own names write it first as the hereditary prefix, repeated before
the father's name (``Tuan Aminah binti Tuan Yusof``), where honours
lists write it as the salutation (decisions/salutation-titles, the 2026-11-19
#1179 entry).

The pack is a plain choice, not a strict one: Malaysian lists mix
Malay, Chinese and Indian names with English and Arabic titles, and a
strict choice of ``ms`` drops the readings other languages' files give
them (``abdul``'s bound reading, English titles such as ``Sir`` and
``Lawyer``), so it reads Malaysia's ORCID holders worse than the
default (the same entry).

Data sources: the counts on each reading in ms.toml
(tools/name_usage.py; Malaysia's election candidates and ORCID's,
PatentsView's and Companies House's Malaysian records). The pack
carries no lexicon fragment and no policy patch.

Declared deviations (mechanisms.md#LOCALE-PACKS-PURE-DATA): a
vocabulary pack's deviations are derived, not declared -- the words
whose compiled readings its choice changes
(``_reading_index.changed_words``), which the non-interference gate in
tests/v2/test_locales.py reads -- so this module defines no DEVIATES.
"""
from __future__ import annotations

from nameparser._lexicon import Lexicon
from nameparser._locale import Locale

MS = Locale(
    code="ms",
    lexicon=Lexicon.empty(),
    languages=frozenset({"ms"}),
)
