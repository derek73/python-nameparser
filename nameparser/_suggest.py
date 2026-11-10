"""The group suggester: given names a caller declares to be one group,
it suggests ``Policy`` settings, chiefly the name order (``Parser.suggest``).

Contracts are stated in prose here, with no doctest blocks. This module
holds the shared spelling fold so the romanized surname table
(``config/_order_names.py``, written by ``tools/vocab/order_names.py``)
and the reader that looks words up in it fold alike, and the per-name
signals: ``name_votes`` reads one name and returns the votes it casts,
a dict from ``Signal`` to either an order (``GIVEN_FIRST`` or
``FAMILY_FIRST``) or, for ``Signal.PATRONYMIC``, the ``PatronymicRule``
its shape matches. A signal that does not apply casts no vote, so the
dict is empty for a name with a comma, no words or one word. Every
signal reads cased Latin evidence only: a word with no cased letter
never counts as capitals, a one-letter word is never looked up in the
name tables, and a script the tables do not hold (Hangul, Han) simply
matches nothing. No signal raises on any string. The patronymic shapes
are the pipeline's own predicates, never a copy of them.
"""
from __future__ import annotations

import unicodedata
from enum import StrEnum

from ._lexicon import Lexicon, _normalize
from ._pipeline._state import COMMA_CHARS
from ._pipeline._vocab import (
    has_patronymic_ending, is_initial, is_patronymic_marker,
)
from ._policy import PatronymicRule
from ._types import FAMILY_FIRST, GIVEN_FIRST, Role
from .config._order_names import COMMON_GIVEN_NAMES, ROMANIZED_SURNAMES

# a letter u with a diaeresis, the pinyin spelling of the vowel written v
# on a keyboard (lü -> lv)
_U_DIAERESIS = {"ü": "v", "Ü": "V"}


def fold(word: str) -> str:
    """The spelling a romanized surname is looked up under: lower case,
    with every diacritic dropped, ``đ`` as ``d`` and ``ü`` as ``v``.

    ``Nguyễn`` folds to ``nguyen``, ``Đặng`` to ``dang`` and ``Lǚ`` to
    ``lv``. The table holds only folded spellings, so a reader folds the
    word first.
    """
    text = unicodedata.normalize("NFKD", word.replace("đ", "d").replace("Đ", "D"))
    for mark, letter in _U_DIAERESIS.items():
        text = text.replace(mark, letter)
    return "".join(c for c in text if not unicodedata.combining(c)).lower()


class Signal(StrEnum):
    """The evidence a single name offers about its writer's name order."""

    CAPITALS = "capitals"
    TRAILING_INITIAL = "trailing-initial"
    PARTICLE = "particle"
    SURNAME = "surname"
    GIVEN_NAME = "given-name"
    PATRONYMIC = "patronymic"


def _is_initialed(word: str) -> bool:
    """An initial: one letter with an optional period, or dotted letters."""
    if is_initial(word):
        return True
    if "." not in word:
        return False
    chunks = word.rstrip(".").split(".")
    return all(chunk and is_initial(chunk + ".") for chunk in chunks)


def _is_caps_word(word: str) -> bool:
    """Two or more letters, all of them capitals, and no initial."""
    letters = [c for c in word if c.isalpha()]
    return (len(letters) >= 2 and word.isupper()
            and not _is_initialed(word))


def _capitals(words: list[str]) -> tuple[Role, Role, Role] | None:
    """A run of capitals words at one end of a name that also holds a
    lowercase letter reads as the family name, which writers set in
    capitals."""
    if not any(c.islower() for w in words for c in w):
        return None
    caps = [_is_caps_word(w) for w in words]
    if all(caps):
        return None
    if caps[0] and not caps[-1]:
        return FAMILY_FIRST
    if caps[-1] and not caps[0]:
        return GIVEN_FIRST
    return None


def _particle(words: list[str], lexicon: Lexicon) -> tuple[Role, Role, Role] | None:
    if len(words) < 3:
        return None
    particles = lexicon._sets.particles

    def is_particle(word: str) -> bool:
        return word == word.lower() and _normalize(word) in particles

    first = is_particle(words[0])
    before_last = is_particle(words[-2])
    if first == before_last:
        return None
    return FAMILY_FIRST if first else GIVEN_FIRST


def _at_one_end(words: list[str], table: frozenset[str]
                ) -> tuple[bool, bool]:
    def listed(word: str) -> bool:
        spelling = fold(word.strip("."))
        return len(spelling) >= 2 and spelling in table

    return listed(words[0]), listed(words[-1])


def name_votes(text: str, lexicon: Lexicon
               ) -> dict[Signal, tuple[Role, Role, Role] | PatronymicRule]:
    """The votes one name casts; empty for a name with a comma, no words
    or one word."""
    words = text.split()
    if len(words) < 2 or any(c in COMMA_CHARS for c in text):
        return {}
    votes: dict[Signal, tuple[Role, Role, Role] | PatronymicRule] = {}

    capitals = _capitals(words)
    if capitals is not None:
        votes[Signal.CAPITALS] = capitals

    if _is_initialed(words[-1]) and not _is_initialed(words[0]):
        votes[Signal.TRAILING_INITIAL] = FAMILY_FIRST

    particle = _particle(words, lexicon)
    if particle is not None:
        votes[Signal.PARTICLE] = particle

    for signal, table, first_order, last_order in (
            (Signal.SURNAME, ROMANIZED_SURNAMES, FAMILY_FIRST, GIVEN_FIRST),
            (Signal.GIVEN_NAME, COMMON_GIVEN_NAMES, GIVEN_FIRST, FAMILY_FIRST)):
        at_first, at_last = _at_one_end(words, table)
        if at_first != at_last:
            votes[signal] = first_order if at_first else last_order

    if any(is_patronymic_marker(w) for w in words):
        votes[Signal.PATRONYMIC] = PatronymicRule.TURKIC
    elif any(has_patronymic_ending(w) for w in words):
        votes[Signal.PATRONYMIC] = PatronymicRule.EAST_SLAVIC
    return votes
