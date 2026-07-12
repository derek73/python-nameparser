"""Immutable vocabulary configuration for the 2.0 API.

Layering: may import nameparser.config DATA modules (titles, suffixes,
prefixes, conjunctions, capitalization, bound_first_names) as the single
source of vocabulary during 2.x -- never nameparser.config itself, never
nameparser.parser. Enforced by tests/v2/test_layering.py.
"""
from __future__ import annotations

import functools
from collections.abc import Iterable, Mapping
from dataclasses import dataclass, field
from types import MappingProxyType

#: Vocabulary set fields, in declaration order. add()/remove()/__or__
#: (a later task) operate on exactly these; capitalization_exceptions is
#: deliberately excluded (its entries are pairs -- use dataclasses.replace).
_VOCAB_FIELDS = (
    "titles", "given_name_titles", "suffix_acronyms", "suffix_words",
    "suffix_acronyms_ambiguous", "particles", "particles_ambiguous",
    "conjunctions", "bound_given_names", "maiden_markers",
)


def _normalize(word: str) -> str:
    """Casefold and strip periods -- v1's lc(). Membership tests never
    re-normalize because construction already did."""
    return word.casefold().replace(".", "").strip()


def _normset(entries: Iterable[str]) -> frozenset[str]:
    result = frozenset(_normalize(w) for w in entries)
    return frozenset(w for w in result if w)


@dataclass(frozen=True, slots=True)
class Lexicon:
    titles: frozenset[str] = frozenset()
    given_name_titles: frozenset[str] = frozenset()
    suffix_acronyms: frozenset[str] = frozenset()
    suffix_words: frozenset[str] = frozenset()
    suffix_acronyms_ambiguous: frozenset[str] = frozenset()
    particles: frozenset[str] = frozenset()
    particles_ambiguous: frozenset[str] = frozenset()
    conjunctions: frozenset[str] = frozenset()
    bound_given_names: frozenset[str] = frozenset()
    maiden_markers: frozenset[str] = frozenset()
    # Canonical storage: sorted tuple of (key, value) pairs. The
    # constructor tolerates any Mapping (or pair iterable) at runtime and
    # canonicalizes here; this closes the caller-aliasing hole and keeps
    # Lexicon hashable. Read via capitalization_exceptions_map.
    capitalization_exceptions: tuple[tuple[str, str], ...] = ()
    _cap_map: Mapping[str, str] = field(
        init=False, repr=False, compare=False, hash=False,
        default_factory=lambda: MappingProxyType({}))

    def __post_init__(self) -> None:
        for name in _VOCAB_FIELDS:
            object.__setattr__(self, name, _normset(getattr(self, name)))
        raw = self.capitalization_exceptions
        pairs = raw.items() if isinstance(raw, Mapping) else raw
        canonical = tuple(sorted((_normalize(k), v) for k, v in pairs))
        object.__setattr__(self, "capitalization_exceptions", canonical)
        object.__setattr__(self, "_cap_map", MappingProxyType(dict(canonical)))
        if not self.particles_ambiguous <= self.particles:
            extra = ", ".join(sorted(self.particles_ambiguous - self.particles))
            raise ValueError(
                f"particles_ambiguous must be a subset of particles; "
                f"not in particles: {extra}"
            )

    @property
    def capitalization_exceptions_map(self) -> Mapping[str, str]:
        return self._cap_map

    # -- constructors ----------------------------------------------------

    @classmethod
    def empty(cls) -> Lexicon:
        return cls()

    @classmethod
    def default(cls) -> Lexicon:
        return _default_lexicon()


@functools.cache
def _default_lexicon() -> Lexicon:
    # v1 data modules are the single source of vocabulary through 2.x.
    from nameparser.config.bound_first_names import BOUND_FIRST_NAMES
    from nameparser.config.capitalization import CAPITALIZATION_EXCEPTIONS
    from nameparser.config.conjunctions import CONJUNCTIONS
    from nameparser.config.prefixes import NON_FIRST_NAME_PREFIXES, PREFIXES
    from nameparser.config.suffixes import (
        SUFFIX_ACRONYMS, SUFFIX_ACRONYMS_AMBIGUOUS, SUFFIX_NOT_ACRONYMS,
    )
    from nameparser.config.titles import FIRST_NAME_TITLES, TITLES

    # v1 data modules export plain `set[str]`; wrap each at this call site
    # so the strictly-typed frozenset[str] fields never see a bare set.
    return Lexicon(
        titles=frozenset(TITLES),
        given_name_titles=frozenset(FIRST_NAME_TITLES),
        suffix_acronyms=frozenset(SUFFIX_ACRONYMS),
        suffix_words=frozenset(SUFFIX_NOT_ACRONYMS),
        suffix_acronyms_ambiguous=frozenset(SUFFIX_ACRONYMS_AMBIGUOUS),
        particles=frozenset(PREFIXES),
        # FLIPPED from v1: v1 marks the never-given subset; v2 marks the
        # may-be-given subset (migration: complement translation).
        particles_ambiguous=frozenset(PREFIXES - NON_FIRST_NAME_PREFIXES),
        conjunctions=frozenset(CONJUNCTIONS),
        bound_given_names=frozenset(BOUND_FIRST_NAMES),
        maiden_markers=frozenset({"née", "nee", "geb"}),
        # pass canonical pair-tuples so this strictly-typed call site never
        # feeds a Mapping to the tuple-annotated field; __post_init__
        # still tolerates a Mapping at runtime for interactive use
        capitalization_exceptions=tuple(sorted(CAPITALIZATION_EXCEPTIONS.items())),
    )
