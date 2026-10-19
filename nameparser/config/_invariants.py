"""Import-time hygiene checks for vocabulary data still written in Python.

Since the word lists moved to nameparser/vocab/*.toml, whose compiler
(tools/vocab/build.py) refuses an unnormalized spelling itself, the one
constant this module still checks is ``surnames.KOREAN_SURNAMES``, a
segmentation list outside the per-word model.

A constant is looked up in normalized form, so a stray capital or a
surrounding space makes an entry unreachable by a direct membership
test -- ``'김 ' in KOREAN_SURNAMES`` would be False -- even though the
parser's own ingest (:func:`nameparser._lexicon._normalize`) normalizes
it away and papers over the typo. Checking at import turns a
silently-inert entry into an immediate failure.

Deliberately a weaker fold than ``_normalize``, which also NFC-composes
and strips edge full stops. Importing ``_lexicon`` here would work (its
config imports sit inside ``_default_lexicon``), but a data module's
hygiene should not depend on the parser's own fold. It asserts that an
entry is stored lowercase, edge-clean and, where it is a phrase,
single-spaced.
"""
from __future__ import annotations

from collections.abc import Iterable


def assert_normalized(name: str, entries: Iterable[str]) -> None:
    """Assert every entry is stored lowercase, edge-clean, and -- where
    it is a phrase -- single-spaced."""
    # " ".join(w.split()) rather than w.strip(): it subsumes the strip
    # and additionally collapses interior runs, which is what a phrase
    # entry made worth checking. For a single word the two are
    # identical, so no existing constant's verdict changes.
    offenders = sorted(w for w in entries if w != " ".join(w.lower().split()))
    assert not offenders, (
        f"{name} entries must be stored lowercase, without edge "
        f"whitespace, and single-spaced if a phrase; "
        f"offending: {offenders}"
    )
