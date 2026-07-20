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
"""
from __future__ import annotations

from collections.abc import Iterable


def assert_normalized(name: str, entries: Iterable[str]) -> None:
    """Assert every entry is stored lowercase and free of edge whitespace."""
    offenders = sorted(w for w in entries if w != w.strip().lower())
    assert not offenders, (
        f"{name} entries must be stored lowercase and whitespace-free; "
        f"offending: {offenders}"
    )
