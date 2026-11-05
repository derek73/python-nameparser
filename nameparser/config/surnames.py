"""The Korean census surnames the default lexicon segments unspaced
hangul on (#271), deprecated in 2.8.2: 3.0 makes the module private,
and ``Lexicon.default().surnames`` holds the same words in 2.x and 3.0
alike."""
# The list itself lives in _ko_surnames.py, which the library reads, so
# only a caller's read of this module's constant warns (#1007, as
# titles.py over _compiled).
from typing import TYPE_CHECKING

from nameparser.config import _ko_surnames
from nameparser.config._deprecated import alias_getattr

KOREAN_SURNAMES = _ko_surnames.KOREAN_SURNAMES
"""
Korean surnames (#271), used by the 2.0 API's unspaced-name
segmentation: a hangul token like "김민준" splits into surname + given
name by longest match. Ships as DEFAULT vocabulary because a hangul
entry can only ever match hangul text, and hangul text is unambiguously
Korean. Chinese surnames live in ``nameparser.locales.zh`` instead (Han
segmentation is opt-in; a zh list corrupts Japanese kanji names).

Deprecated since 2.8.2, and private in 3.0: read
``Lexicon.default().surnames``, which holds the same words, and extend
it with ``Lexicon.default() | Lexicon(surnames=frozenset({...}))``.
"""

# outside the type checker's view, for the reason alias_getattr's
# docstring gives: a module __getattr__ mypy can see answers every
# missing attribute of the module
if not TYPE_CHECKING:
    # 2.8.2: the constant is served by __getattr__ and warns at the line
    # that reads it, naming the Lexicon field 3.0 keeps public
    __getattr__, __dir__ = alias_getattr(__name__, {}, removed={
        "KOREAN_SURNAMES": (
            "Lexicon.default().surnames holds the same words, now and in 3.0"),
    }, namespace=globals())

# star imports read __all__ and never the module __getattr__ -- see the
# note in prefixes.py
__all__ = ["KOREAN_SURNAMES"]
