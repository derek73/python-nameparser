"""The Mongolian locale pack: it reads a name written wholly in
Cyrillic family-first with the given name last (a ``Policy.script_orders``
entry for ``Script.CYRILLIC``, FAMILY_FIRST_GIVEN_LAST), and it chooses
the language ``mn``, which changes no reading the default holds
(mn.toml's readings are on by default).

A Mongolian name has no inherited family name: it is the father's name,
in the genitive when written in full (``Ухнаагийн Хүрэлсүх``) or in the
nominative as passports write it (``Ухнаа Хүрэлсүх``), then the given
name. The father's name stands in the surname slot of the convention's
own records, so the pack reads it as the ``family`` (#1253's decision,
its first statement): ``Ухнаагийн Хүрэлсүх`` gives family
``Ухнаагийн``, given ``Хүрэлсүх``, where the default gives the reverse.

The order is keyed to the script, not declared for every name, because
a Mongolian writes Cyrillic father's name first but often writes a
romanized name given-first, so a romanized name keeps the caller's
order (``Policy.name_order``, given-first by default, or one
``Parser.suggest`` proposes for a list). Cyrillic is written for many
languages in both orders, so this order is the PACK's, licensed by the
caller's choice of Mongolian, never a default the script settles
(rules/W4). The genitive is not read into the patronymic view (#1237).
The given name is read last rather than second so that a word before
the father's name, a clan name (``Боржигин Ухнаагийн Хүрэлсүх``),
leaves the given name in place; the clan name itself is not read (it
reads as the family, the father's name as the middle).

Data sources: the State Great Khural, JRC-Names, ORCID's Mongolian
bylines and CLDR's mn sample, measured in decisions/vocabulary-model's
2026-11-12 #1237 entry.

Declared deviations (mechanisms.md#LOCALE-PACKS-PURE-DATA): the script
order can move any name of two name words or more written wholly in
Cyrillic that a family comma does not fix (a one-word name reads as
``Policy.lone_name_word`` names under every order, rules/O5), so
DEVIATES below declares every name holding a Cyrillic letter. The
choice's own words are derived (``_reading_index.changed_words``, none
on 2026-11-12), which the non-interference gate in
tests/v2/test_locales.py ors in.
"""
from __future__ import annotations

from nameparser._lexicon import Lexicon
from nameparser._locale import Locale
from nameparser._policy import (
    FAMILY_FIRST_GIVEN_LAST, PolicyPatch, Script, _script_matcher,
)

MN = Locale(
    code="mn",
    lexicon=Lexicon.empty(),
    policy=PolicyPatch(script_orders=((Script.CYRILLIC, FAMILY_FIRST_GIVEN_LAST),)),
    languages=frozenset({"mn"}),
)

#: any Cyrillic letter: the script order reads only a name written
#: wholly in Cyrillic, so this over-declares, the safe direction
DEVIATES = _script_matcher(Script.CYRILLIC)
