"""The group suggester: given names a caller declares to be one group,
it suggests ``Policy`` settings, chiefly the name order (``Parser.suggest``).

Contracts are stated in prose here, with no doctest blocks. This module
holds the shared spelling fold so the romanized surname table
(``config/_order_names.py``, written by ``tools/vocab/order_names.py``)
and the reader that looks words up in it fold alike.
"""
from __future__ import annotations

import unicodedata

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
