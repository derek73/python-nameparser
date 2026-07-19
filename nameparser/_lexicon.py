"""Immutable vocabulary configuration for the 2.0 API.

Layering: may import nameparser.config DATA modules (the imports in
_default_lexicon() are the authoritative list) as the single source of
vocabulary during 2.x -- never nameparser.config itself, never
nameparser.parser. Enforced by tests/v2/test_layering.py.
"""
from __future__ import annotations

import dataclasses
import functools
from collections.abc import Iterable, Mapping
from dataclasses import dataclass, field
from types import MappingProxyType

#: Vocabulary set fields, in declaration order. add()/remove() operate
#: on exactly these and reject capitalization_exceptions (its entries
#: are pairs -- use dataclasses.replace); __or__ unions these AND merges
#: capitalization_exceptions right-biased.
_VOCAB_FIELDS = (
    "titles", "given_name_titles", "suffix_acronyms", "suffix_words",
    "suffix_acronyms_ambiguous", "particles", "particles_ambiguous",
    "conjunctions", "bound_given_names", "maiden_markers",
)

#: (marker, base) pairs: each marker field narrows how entries of its
#: base vocabulary are read, and carries no vocabulary of its own. An
#: entry present in the marker but absent from the base is never
#: consulted by any rule, so it is rejected rather than silently
#: ignored -- a no-op configuration is the failure mode these fields
#: are most likely to be misused into.
_SUBSET_FIELDS = (
    ("particles_ambiguous", "particles"),
    ("suffix_acronyms_ambiguous", "suffix_acronyms"),
    ("given_name_titles", "titles"),
)


def _normalize(word: str) -> str:
    """Lowercase, strip whitespace and EDGE periods -- v1's lc()
    semantics. Interior periods survive on purpose: 'J.R.' must not
    collapse to 'jr' and hit the periodless vocabulary (v1 parity,
    pinned live 2026-07-17). Suffix-ACRONYM membership alone uses the
    period-free form (see _vocab.suffix_as_written), mirroring v1's
    is_suffix, which removed periods only for the acronym test.

    lower(), NOT casefold(): casefold's caseless-matching folds mutate
    the stored vocabulary itself -- 'κος' becomes the misspelling 'κοσ'
    (final sigma flattened) and 'großfürst' becomes 'grossfürst' --
    while lower() applies Unicode SpecialCasing contextually and keeps
    both as authored. This function is the single fold for storage AND
    match-time lookups, so matching stays symmetric either way; lower()
    is what v1's lc() used, preserving which cross-spellings match."""
    return word.lower().strip().strip(".")


def _normset(entries: Iterable[str], field_name: str) -> frozenset[str]:
    # Reject a bare str before iterating: iterating "dr" would silently
    # yield the single characters {'d', 'r'} -- the set(str) footgun on
    # the primary customization surface.
    if isinstance(entries, str):
        raise TypeError(
            f"Lexicon.{field_name} must be an iterable of strings, "
            f"not a bare string"
        )
    # A Mapping would silently contribute only its keys; a dict here
    # almost always means the caller confused this field with
    # capitalization_exceptions.
    if isinstance(entries, Mapping):
        raise TypeError(
            f"Lexicon.{field_name} must be an iterable of strings, not a "
            f"mapping (only capitalization_exceptions holds key->value pairs)"
        )
    try:
        items = tuple(entries)  # materialize once; entries may be a generator
    except TypeError:
        raise TypeError(
            f"Lexicon.{field_name} must be an iterable of strings, "
            f"got {entries!r}"
        ) from None
    normalized = set()
    for w in items:
        if not isinstance(w, str):
            raise TypeError(
                f"Lexicon.{field_name} entries must be strings, got {w!r}"
            )
        n = _normalize(w)
        # "." or "" is a data bug (stray split artifact, empty CSV
        # cell); dropping it silently would also let a data-module typo
        # vanish instead of failing CI.
        if not n:
            raise ValueError(
                f"Lexicon.{field_name} entry {w!r} normalizes to empty "
                f"(lowercase + strip periods/whitespace leaves nothing)"
            )
        normalized.add(n)
    return frozenset(normalized)


def _normpairs(
    raw: Mapping[str, str] | Iterable[tuple[str, str]],
) -> tuple[tuple[str, str], ...]:
    """Canonicalize capitalization_exceptions input: _normset's sibling
    for the one pair-valued field. Dedupes on the NORMALIZED key so the
    tuple and the derived map always agree ("Ph.D." and "phd" collide
    after normalization); last occurrence wins, matching dict semantics
    and the right-bias rule used elsewhere."""
    if isinstance(raw, str):
        raise TypeError(
            "capitalization_exceptions must be a mapping or an "
            "iterable of (key, value) pairs, not a bare string"
        )
    pairs = raw.items() if isinstance(raw, Mapping) else raw
    try:
        pairs = iter(pairs)
    except TypeError:
        raise TypeError(
            "capitalization_exceptions must be a mapping or an "
            f"iterable of (key, value) pairs, got {raw!r}"
        ) from None
    deduped: dict[str, str] = {}
    for entry in pairs:
        # A 2-char str entry would unpack "ab" into ("a", "b")
        # silently, so reject str outright; other mis-shapes would
        # otherwise surface as bare unpack errors.
        if isinstance(entry, str):
            raise TypeError(
                f"capitalization_exceptions entries must be "
                f"(key, value) pairs, got {entry!r}"
            )
        try:
            k, v = entry
        except (TypeError, ValueError):
            raise TypeError(
                f"capitalization_exceptions entries must be "
                f"(key, value) pairs, got {entry!r}"
            ) from None
        if not isinstance(k, str) or not isinstance(v, str):
            raise TypeError(
                f"capitalization_exceptions entries must be "
                f"str -> str, got {k!r}: {v!r}"
            )
        normalized_key = _normalize(k)
        if not normalized_key:
            raise ValueError(
                f"capitalization_exceptions key {k!r} normalizes to "
                f"empty (lowercase + strip periods/whitespace leaves "
                f"nothing)"
            )
        deduped[normalized_key] = v
    return tuple(sorted(deduped.items()))


@dataclass(frozen=True, slots=True)
class Lexicon:
    """The vocabulary a parser matches against: which words are
    titles, particles, suffixes, and so on. Immutable and hashable.
    Start from :meth:`default` (the shipped vocabulary) or
    :meth:`empty`, derive variants with :meth:`add` / :meth:`remove` /
    ``|`` (union), and pass the result to ``Parser(lexicon=...)``.
    Entries are normalized at construction -- lowercased, edge periods
    stripped -- so matching is case-insensitive. Field docs below show
    examples, not full contents; inspect any field's shipped vocabulary
    directly, e.g. ``Lexicon.default().conjunctions``."""

    #: Pre-nominal titles ("dr", "sir", "capt", ...). Full default
    #: list: :data:`~nameparser.config.titles.TITLES`.
    titles: frozenset[str] = frozenset()
    #: Titles whose single following name reads as a GIVEN name
    #: ("sheikh", "sister", ...) rather than a family name. Full
    #: default list: :data:`~nameparser.config.titles.FIRST_NAME_TITLES`.
    given_name_titles: frozenset[str] = frozenset()
    #: Post-nominal acronym suffixes, matched with or without periods
    #: ("phd" matches "PhD" and "Ph.D."). Full default list:
    #: :data:`~nameparser.config.suffixes.SUFFIX_ACRONYMS`.
    suffix_acronyms: frozenset[str] = frozenset()
    #: Post-nominal word suffixes ("jr", "esquire", "iii", ...). Full
    #: default list:
    #: :data:`~nameparser.config.suffixes.SUFFIX_NOT_ACRONYMS`.
    suffix_words: frozenset[str] = frozenset()
    #: Subset of suffix_acronyms counted as suffixes only when written
    #: WITH periods -- their bare forms are common surnames ("ma",
    #: "do": "Jack Ma" keeps his family name). Full default list:
    #: :data:`~nameparser.config.suffixes.SUFFIX_ACRONYMS_AMBIGUOUS`.
    suffix_acronyms_ambiguous: frozenset[str] = frozenset()
    #: Family-name particles that chain onto the following piece
    #: ("van", "de", "bin", ...). Full default list:
    #: :data:`~nameparser.config.prefixes.PREFIXES`.
    particles: frozenset[str] = frozenset()
    #: Subset of particles that can also BE a given name: a leading
    #: one reads as given and records a particle-or-given ambiguity
    #: ("Van Johnson"). No constant of its own -- the default derives
    #: as particles minus
    #: :data:`~nameparser.config.prefixes.NON_FIRST_NAME_PREFIXES`
    #: (which marks the opposite, never-given subset).
    particles_ambiguous: frozenset[str] = frozenset()
    #: Words or characters that join surrounding pieces into one
    #: ("and", "&", "y", "и", ...). Full default list:
    #: :data:`~nameparser.config.conjunctions.CONJUNCTIONS`.
    conjunctions: frozenset[str] = frozenset()
    #: Given-name prefixes that bind to the following word to form one
    #: given name ("abdul" -> "Abdul Salam"); never standalone names.
    #: Full default list:
    #: :data:`~nameparser.config.bound_first_names.BOUND_FIRST_NAMES`.
    bound_given_names: frozenset[str] = frozenset()
    #: Marker words introducing a birth surname, routed to the maiden
    #: field ("née", "geb.", "roz.", ...). Full default list:
    #: :data:`~nameparser.config.maiden_markers.MAIDEN_MARKERS`.
    maiden_markers: frozenset[str] = frozenset()
    #: Lowercase word -> exact-cased replacement used by capitalized()
    #: ("phd" -> "Ph.D."). Pair-valued: change it with
    #: dataclasses.replace(), not add()/remove(); read it as a mapping
    #: via capitalization_exceptions_map. Full default mapping:
    #: :data:`~nameparser.config.capitalization.CAPITALIZATION_EXCEPTIONS`.
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
        canonical = _normpairs(self.capitalization_exceptions)
        object.__setattr__(self, "capitalization_exceptions", canonical)
        object.__setattr__(self, "_cap_map", MappingProxyType(dict(canonical)))
        for marker, base in _SUBSET_FIELDS:
            orphans = getattr(self, marker) - getattr(self, base)
            if orphans:
                raise ValueError(
                    f"{marker} marks a subset of {base}; "
                    f"not in {base}: {', '.join(sorted(orphans))}. "
                    f"Add them to {base} as well — "
                    f"add({base}={{...}}, {marker}={{...}})"
                )
        # The v2 form of prefixes.py's NON_FIRST_NAME_PREFIXES-disjoint-
        # from-BOUND_FIRST_NAMES assertion. That module guards its own
        # data at import; this guards vocabulary a caller supplies.
        contradictory = (
            self.bound_given_names & self.particles) - self.particles_ambiguous
        if contradictory:
            raise ValueError(
                f"bound_given_names entries that are also particles must be "
                f"in particles_ambiguous; not in particles_ambiguous: "
                f"{', '.join(sorted(contradictory))}. A particle that never "
                f"starts a given name cannot also bind one — add them to "
                f"particles_ambiguous, or drop them from bound_given_names"
            )

    # -- constructors ----------------------------------------------------

    @classmethod
    def empty(cls) -> Lexicon:
        return cls()

    @classmethod
    def default(cls) -> Lexicon:
        return _default_lexicon()

    # -- dunders ----------------------------------------------------------

    def _deltas_from(self, baseline: Lexicon) -> list[tuple[str, int, int]]:
        deltas = []
        for name in _VOCAB_FIELDS + ("capitalization_exceptions",):
            mine = set(getattr(self, name))
            theirs = set(getattr(baseline, name))
            added, removed = len(mine - theirs), len(theirs - mine)
            if added or removed:
                deltas.append((name, added, removed))
        return deltas

    def __repr__(self) -> str:
        # Bounded: renders only which fields deviate from the nearer of
        # the two named constructors and by how many entries -- never the
        # entries themselves (design rule, see nameparser._types module
        # docstring). Diffing empty()-built lexicons against default()
        # would tell the wrong story ("default minus the entire
        # default vocabulary").
        if self == Lexicon.default():
            return "Lexicon(default)"
        if self == Lexicon.empty():
            return "Lexicon(empty)"
        candidates = [(label, self._deltas_from(baseline))
                      for label, baseline in (("default", Lexicon.default()),
                                              ("empty", Lexicon.empty()))]
        label, deltas = min(
            candidates, key=lambda c: sum(a + r for _, a, r in c[1]))
        rendered = ", ".join(
            name + ": " + "".join(
                part for part, n in ((f"+{a}", a), (f"-{r}", r)) if n)
            for name, a, r in deltas)
        return f"Lexicon({label} + {rendered})"

    def __getstate__(self) -> dict[str, object]:
        # _cap_map is a MappingProxyType, which pickle rejects; ship every
        # other slot and rebuild the proxy from the canonical tuple on load.
        return {f.name: getattr(self, f.name)
                for f in dataclasses.fields(self) if f.name != "_cap_map"}

    def __setstate__(self, state: dict[str, object]) -> None:
        # Fail at the unpickle site if the state comes from a different
        # Lexicon field layout (version skew) -- silently loading it
        # would defer the failure to some distant attribute read.
        # Message kept in sync with _types._guarded_setstate by design
        # (layering keeps this module import-free of _types).
        expected = {f.name for f in dataclasses.fields(Lexicon)} - {"_cap_map"}
        if set(state) != expected:
            missing = ", ".join(sorted(expected - set(state))) or "none"
            unexpected = ", ".join(sorted(set(state) - expected)) or "none"
            raise ValueError(
                f"incompatible Lexicon pickle: missing fields: {missing}; "
                f"unexpected fields: {unexpected}"
            )
        for name, value in state.items():
            object.__setattr__(self, name, value)
        object.__setattr__(
            self, "_cap_map",
            MappingProxyType(dict(self.capitalization_exceptions)))

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

    # -- properties -------------------------------------------------------

    @property
    def capitalization_exceptions_map(self) -> Mapping[str, str]:
        return self._cap_map

    # -- editing ----------------------------------------------------------

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


@functools.cache
def _default_lexicon() -> Lexicon:
    # v1 data modules are the single source of vocabulary through 2.x.
    from nameparser.config.bound_first_names import BOUND_FIRST_NAMES
    from nameparser.config.capitalization import CAPITALIZATION_EXCEPTIONS
    from nameparser.config.conjunctions import CONJUNCTIONS
    from nameparser.config.maiden_markers import MAIDEN_MARKERS
    from nameparser.config.prefixes import NON_FIRST_NAME_PREFIXES, PREFIXES
    from nameparser.config.suffixes import (
        SUFFIX_ACRONYMS, SUFFIX_ACRONYMS_AMBIGUOUS, SUFFIX_NOT_ACRONYMS,
    )
    from nameparser.config.titles import FIRST_NAME_TITLES, TITLES

    # v1 data modules export plain `set[str]`; wrap each at this call site
    # so the strictly-typed frozenset[str] fields never see a bare set.
    # keep in sync with _config_shim.Constants._snapshot() (pinned by the
    # default-Constants equality test in tests/v2/test_config_shim.py)
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
        maiden_markers=frozenset(MAIDEN_MARKERS),
        # pass canonical pair-tuples so this strictly-typed call site never
        # feeds a Mapping to the tuple-annotated field; __post_init__
        # still tolerates a Mapping at runtime for interactive use
        capitalization_exceptions=tuple(sorted(CAPITALIZATION_EXCEPTIONS.items())),
    )
