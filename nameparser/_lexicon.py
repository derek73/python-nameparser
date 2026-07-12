"""Immutable vocabulary configuration for the 2.0 API.

Layering: may import nameparser.config DATA modules (titles, suffixes,
prefixes, conjunctions, capitalization, bound_first_names) as the single
source of vocabulary during 2.x -- never nameparser.config itself, never
nameparser.parser. Enforced by tests/v2/test_layering.py.
"""
from __future__ import annotations

import dataclasses
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


def _normset(entries: Iterable[str], field_name: str) -> frozenset[str]:
    # Reject a bare str before iterating: iterating "dr" would silently
    # yield the single characters {'d', 'r'} -- the set(str) footgun on
    # the primary customization surface.
    if isinstance(entries, str):
        raise ValueError(
            f"Lexicon.{field_name} must be an iterable of strings, "
            f"not a bare string"
        )
    items = tuple(entries)  # materialize once; entries may be a generator
    for w in items:
        if not isinstance(w, str):
            raise ValueError(
                f"Lexicon.{field_name} entries must be strings, got {w!r}"
            )
    result = frozenset(_normalize(w) for w in items)
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
            object.__setattr__(self, name, _normset(getattr(self, name), name))
        raw = self.capitalization_exceptions
        pairs = raw.items() if isinstance(raw, Mapping) else raw
        # Dedupe on the NORMALIZED key before storing so the tuple and the
        # map always agree ("Ph.D." and "phd" collide after normalization).
        # Last occurrence wins, matching dict semantics and the right-bias
        # rule used elsewhere.
        deduped: dict[str, str] = {}
        for k, v in pairs:
            if not isinstance(k, str) or not isinstance(v, str):
                raise ValueError(
                    f"capitalization_exceptions entries must be "
                    f"str -> str, got {k!r}: {v!r}"
                )
            normalized_key = _normalize(k)
            if not normalized_key:
                continue  # mirror _normset's drop-empty rule
            deduped[normalized_key] = v
        canonical = tuple(sorted(deduped.items()))
        object.__setattr__(self, "capitalization_exceptions", canonical)
        object.__setattr__(self, "_cap_map", MappingProxyType(dict(canonical)))
        if not self.particles_ambiguous <= self.particles:
            extra = ", ".join(sorted(self.particles_ambiguous - self.particles))
            raise ValueError(
                f"particles_ambiguous must be a subset of particles; "
                f"not in particles: {extra}"
            )

    def __repr__(self) -> str:
        # Bounded: renders only which fields deviate from default() and by
        # how many entries -- never the entries themselves (design rule,
        # see nameparser._types module docstring).
        default = Lexicon.default()
        if self == default:
            return "Lexicon(default)"
        deltas = []
        for name in _VOCAB_FIELDS + ("capitalization_exceptions",):
            mine = set(getattr(self, name))
            theirs = set(getattr(default, name))
            added, removed = len(mine - theirs), len(theirs - mine)
            if added or removed:
                delta = "".join(
                    part for part, n in ((f"+{added}", added), (f"-{removed}", removed)) if n
                )
                deltas.append(f"{name}: {delta}")
        return f"Lexicon(default + {', '.join(deltas)})"

    def __getstate__(self) -> dict[str, object]:
        # _cap_map is a MappingProxyType, which pickle rejects; ship every
        # other slot and rebuild the proxy from the canonical tuple on load.
        return {f.name: getattr(self, f.name)
                for f in dataclasses.fields(self) if f.name != "_cap_map"}

    def __setstate__(self, state: dict[str, object]) -> None:
        for name, value in state.items():
            object.__setattr__(self, name, value)
        object.__setattr__(
            self, "_cap_map",
            MappingProxyType(dict(self.capitalization_exceptions)))

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

    # -- composition ------------------------------------------------------

    def _edit(self, op: str, entries: Mapping[str, Iterable[str]]) -> Lexicon:
        updates: dict[str, frozenset[str]] = {}
        for name, words in entries.items():
            if name == "capitalization_exceptions":
                raise TypeError(
                    "capitalization_exceptions holds key->value pairs; "
                    "use dataclasses.replace(lexicon, "
                    "capitalization_exceptions={...}) instead of "
                    f"{op}()"
                )
            if name not in _VOCAB_FIELDS:
                raise TypeError(
                    f"unknown Lexicon field {name!r}; valid fields: "
                    f"{', '.join(_VOCAB_FIELDS)}"
                )
            current: frozenset[str] = getattr(self, name)
            normalized = _normset(words, name)
            updates[name] = (current | normalized if op == "add"
                             else current - normalized)
        # mypy's dataclasses.replace() typing checks a **dict's single
        # value type against every field's type (it can't see which keys
        # are actually present behind the unpack), so a homogeneous
        # frozenset[str] dict is flagged against the tuple/Mapping-typed
        # capitalization_exceptions/_cap_map fields even though this dict
        # never contains those keys (guarded above).
        return dataclasses.replace(self, **updates)  # type: ignore[arg-type]

    def add(self, **entries: Iterable[str]) -> Lexicon:
        return self._edit("add", entries)

    def remove(self, **entries: Iterable[str]) -> Lexicon:
        return self._edit("remove", entries)

    def __or__(self, other: Lexicon) -> Lexicon:
        if not isinstance(other, Lexicon):
            return NotImplemented
        updates: dict[str, object] = {
            name: getattr(self, name) | getattr(other, name)
            for name in _VOCAB_FIELDS
        }
        # right-biased on key conflicts, mirroring later-wins for scalars
        merged = dict(self._cap_map) | dict(other._cap_map)
        updates["capitalization_exceptions"] = tuple(sorted(merged.items()))
        return dataclasses.replace(self, **updates)  # type: ignore[arg-type]


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
