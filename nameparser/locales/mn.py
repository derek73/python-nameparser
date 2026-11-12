"""The Mongolian locale pack: it reads a name family-first with the
given name last (``Policy.name_order``, FAMILY_FIRST_GIVEN_LAST), its
policy patch compiled from nameparser/vocab/mn.toml's [rules] table by
tools/vocab/build.py, and it chooses the language ``mn``, which changes
no reading the default holds (mn.toml's readings are on by default).

A Mongolian name has no inherited family name: it is the father's name,
in the genitive when written in full (``Ухнаагийн Хүрэлсүх``) or in the
nominative as passports write it (``Ухнаа Хүрэлсүх``), then the given
name. The father's name stands in the surname slot of the convention's
own records, so the pack reads it as the ``family`` (#1253's decision,
its first statement): ``Ухнаагийн Хүрэлсүх`` gives family
``Ухнаагийн``, given ``Хүрэлсүх``, where the default gives the reverse.
The genitive is not read into the patronymic view (#1237). The given
name is read last rather than second so that a word before the father's
name, a clan name (``Боржигин Ухнаагийн Хүрэлсүх``), leaves the given
name in place; the clan name itself is not read (it reads as the
family, the father's name as the middle).

Data sources: the State Great Khural, JRC-Names, ORCID's Mongolian
bylines and CLDR's mn sample, measured in decisions/vocabulary-model's
2026-11-12 #1237 entry.

Declared deviations (mechanisms.md#LOCALE-PACKS-PURE-DATA): the order
can move any name of two name words or more that a family comma does
not fix (a one-word name reads as ``Policy.lone_name_word`` names under
every order, given by default, rules/O5), in any script but those whose
order rules/W4 settles, so DEVIATES below declares a superset: every
name holding a letter or a digit. The choice's own words are derived
(``_reading_index.changed_words``, none on 2026-11-12), which the
non-interference gate in tests/v2/test_locales.py ors in.
"""
from __future__ import annotations

from nameparser._lexicon import Lexicon
from nameparser._locale import Locale, rules_patch

MN = Locale(
    code="mn",
    lexicon=Lexicon.empty(),
    # nameparser/vocab/mn.toml's [rules], compiled by tools/vocab/build.py
    policy=rules_patch("mn"),
    languages=frozenset({"mn"}),
)


def DEVIATES(name: str) -> bool:
    """True when this pack may parse `name` differently from the
    default parser (the declared-deviation predicate the
    non-interference gate consumes): any name holding a letter or a
    digit, since the order can move any name of two name words or more
    that a family comma does not fix, so no narrower predicate is worth
    stating by hand."""
    return any(c.isalnum() for c in name)
