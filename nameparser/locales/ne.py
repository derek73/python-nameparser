"""The Nepali locale pack: vocabulary-only -- it chooses the language
``ne``, which turns on the readings nameparser/vocab/ne.toml writes
``default = false``: the given-name readings of ``श्री``, ``guru`` and
``गुरु``, words the default reads as titles (decisions/vocabulary-model,
the 2026-10-30 phase 3d entry). Each is then a title only inside a
title phrase (rules/H9), so it reads as the given name at the head of a
name: ``श्री कृष्ण श्रेष्ठ`` gives given ``श्री`` where the default
gives title ``श्री``.

It also reads two or more single letters ending a romanized name as
its family name (``Policy.initials_as_family``, rules/O8), its policy
patch compiled from ne.toml's [rules] table: Nepali surnames are often
written as their initials, ``B K`` for Bishwakarma and ``K C`` for
Khatri Chhetri, so ``Ram Bahadur B K`` gives middle ``Bahadur``, family ``B K``
where the default gives middle ``Bahadur B``, family ``K``.

Data sources: nepal-candidates, Nepal's 2079 BS local election
candidates, each name written in Devanagari and romanized
(tools/differential/local_nepal.py); the counts are on the readings in
ne.toml and, for the letters, in decisions/O8. The pack carries no
lexicon fragment.

Declared deviations (mechanisms.md#LOCALE-PACKS-PURE-DATA): the
words whose compiled readings its choice changes are derived
(``_reading_index.changed_words``), which the non-interference gate in
tests/v2/test_locales.py reads, so DEVIATES declares only what the
patch changes.
"""
from __future__ import annotations

from nameparser._lexicon import Lexicon
from nameparser._locale import Locale, rules_patch
from nameparser._policy import initials_as_family_may_move


def DEVIATES(name: str) -> bool:
    """True when the pack's patch may parse `name` differently from the
    default parser: rules/O8 moves only letters standing two or more in
    a row, which Policy's initials_as_family_may_move tests, dividing
    words at every character that is not a letter or a combining mark,
    so it over-declares, the safe direction."""
    return initials_as_family_may_move(name)


NE = Locale(
    code="ne",
    lexicon=Lexicon.empty(),
    # nameparser/vocab/ne.toml's [rules], compiled by tools/vocab/build.py
    policy=rules_patch("ne"),
    languages=frozenset({"ne"}),
)
