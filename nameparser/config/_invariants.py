"""Import-time hygiene checks shared by the vocabulary data modules.

Every constant here is looked up in normalized form, so a stray capital
or a surrounding space makes an entry unreachable by a direct membership
test -- ``'actor ' in TITLES`` is False -- even though the parser's own
ingest (:func:`nameparser._lexicon._normalize`) normalizes it away and
papers over the typo. Checking at import turns a silently-inert entry
into an immediate failure.

Deliberately a weaker fold than ``_normalize``, which also strips edge
periods: entries like ``'esq.'`` are legitimate data here, and this
module cannot import ``_lexicon`` anyway (``_lexicon`` imports these
constants). The relationship checks between constants stay in the
modules that own them -- those encode facts about the data, not hygiene.

Interior whitespace is checked but not forbidden. A PHRASE entry is
legitimate in the two fields ``_lexicon._PHRASE_FIELDS`` names, and
``MAIDEN_MARKERS``'s ``'z domu'`` is the first one shipped; what this
asserts of one is that it is stored as the single-spaced, lowercase,
edge-clean form, so ``'z  domu'`` and ``'Z domu '`` fail here rather
than becoming entries nothing can match. The remaining half of a
phrase's storage rule -- that each WORD is separately stripped of its
periods, so ``'z. domu'`` is stored ``'z domu'`` -- is
``_lexicon._title_key``'s and is deliberately NOT checked here. The
reason is altitude, not layering: importing ``_lexicon`` from here
would in fact work (its config imports are all inside
``_default_lexicon()``, nothing at module scope), but a data module
asserting things with the parser's own fold makes the constant's
hygiene depend on the parser, and the question worth asking is not
"is this entry pre-folded" but "does ``Lexicon`` store it unchanged".
That is one assertion over ``_PHRASE_FIELDS`` in
``tests/v2/test_ledger_guards.py``, the suite that already imports the
parser's fold for exactly this purpose, and it is where an entry
written ``'z. domu'`` is caught.
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
