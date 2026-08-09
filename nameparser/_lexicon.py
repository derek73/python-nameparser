"""Immutable vocabulary configuration for the 2.0 API.

Layering: may import nameparser.config DATA modules (the imports in
_default_lexicon() are the authoritative list) as the single source of
vocabulary during 2.x -- never nameparser.config itself, never
nameparser.parser. Enforced by tests/v2/test_layering.py.
"""
from __future__ import annotations

import dataclasses
import functools
import sys
import warnings
from collections.abc import Iterable, Mapping
from dataclasses import dataclass, field
from types import FrameType, MappingProxyType
from typing import cast

#: Vocabulary set fields, in declaration order. add()/remove() operate
#: on exactly these and reject capitalization_exceptions (its entries
#: are pairs -- use dataclasses.replace); __or__ unions these AND merges
#: capitalization_exceptions right-biased.
_VOCAB_FIELDS = (
    "titles", "given_name_titles", "suffix_acronyms", "suffix_words",
    "suffix_acronyms_ambiguous", "particles", "particles_ambiguous",
    "conjunctions", "bound_given_names", "maiden_markers", "surnames",
    "honorific_tails",
)

#: (marker, base, why) triples. Each marker QUALIFIES how entries of
#: its base vocabulary are read and carries no vocabulary of its own,
#: so an entry outside the base is a configuration mistake -- but the
#: mistake differs per pair, and the reason is recorded here rather
#: than generalized, because an orphan is NOT simply inert. Nor is the
#: qualification one-directional: the first two NARROW their base (an
#: entry is read as vocabulary in fewer places), while honorific_tails
#: WIDENS it, granting a suffix word the glued position on top of the
#: whole-token match every suffix word already gets.
#:
#: * particles_ambiguous: _assign keys on the tag alone, so an orphan
#:   makes the parse emit a spurious particle-or-given ambiguity.
#: * suffix_acronyms_ambiguous: _vocab returns True on the ambiguous
#:   set before testing suffix_acronyms, so an orphan silently turns a
#:   word into a period-gated suffix.
#: * honorific_tails: script_segment peels the tail into its own token
#:   before classify ever runs, so an orphan splits the name and leaves
#:   the fragment stranded inside it -- worse than not peeling at all.
#:   Its base is deliberately NARROWER than what actually claims the
#:   peeled piece: suffix_as_written ORs suffix_words with the
#:   non-ambiguous suffix_acronyms, so a tail listed only as an acronym
#:   would classify fine yet is rejected here. Accepted, and a decision
#:   rather than an oversight -- the three-term predicate is easy to
#:   get wrong in the dangerous direction (an ambiguous acronym admitted
#:   as a tail would peel a period-gated word off a real name), and
#:   nothing needs the acronym half: the shipped tails are CJK
#:   honorifics, which are words.
#:   The same relation is asserted a second time in config/suffixes.py,
#:   over the raw GLUED_HONORIFICS/SUFFIX_WORDS constants at
#:   import. The two are not redundant in the way they look: that one
#:   is an `assert`, stripped under `python -O`, while the check here
#:   raises unconditionally -- so under -O this is what still holds the
#:   SHIPPED vocabulary to the invariant, as it is the only thing that
#:   ever held a caller's own.
#:
#: given_name_titles is deliberately NOT here and has no check of its
#: own -- see the note in __post_init__ for why every attempt at one
#: rejected working configurations.
_SUBSET_FIELDS = (
    ("particles_ambiguous", "particles",
     "an orphan emits a spurious particle-or-given ambiguity"),
    ("suffix_acronyms_ambiguous", "suffix_acronyms",
     "an orphan silently becomes a period-gated suffix"),
    ("honorific_tails", "suffix_words",
     "an orphan splits the name and leaves the tail inside it"),
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
    is what v1's lc() used, preserving which cross-spellings match.

    Strips to a FIXED POINT. A single strip().strip(".") leaves
    periods-around-whitespace half done ('. a .' -> ' a '), so a value
    that is re-normalized later -- on unpickle, or by a second add() --
    would change under its owner. v1 never re-normalized, so this only
    matters now that storage and match-time share one fold."""
    word = word.lower()
    while True:
        stripped = word.strip().strip(".")
        if stripped == word:
            return word
        word = stripped


def _title_key(words: Iterable[str]) -> str:
    """The given_name_titles lookup key for a run of title words.

    A multi-word title is matched as one key ('lt col'), so the fold has
    to run per word and rejoin -- _normalize on the whole phrase would
    leave interior periods. Defined once because it is built at match
    time (post_rules) and at translation time (the v1 facade's
    first_name_titles), and a divergence between the two fails silently:
    the entry simply stops matching.

    Words that fold away are DROPPED, not joined as empty. Keeping the
    gap makes the fold non-idempotent -- 'lt .' would store 'lt ', which
    match time can never build (post_rules joins token texts, and a lone
    '.' is not a title token), so the entry is inert. Storage re-runs
    this fold on unpickle and on every dataclasses.replace, so a value
    that changes under a second pass is one Lexicon later rejects as
    "not written by this version". _normalize converges for the same
    reason; so must anything built on top of it."""
    return " ".join(filter(None, (_normalize(w) for w in words)))


def _reject_buffer(value: object, label: str, plural: str) -> None:
    """Binary sequences iterate to INTS, so every downstream entry check
    reports a byte value -- "must be strings, got 100" for b'dr', where
    100 is 'd'. That names neither the cause nor the fix. v1 shipped a
    decode hint for this (#238), and parse() and the facade both carry
    one, so no config entry point should be the odd one out.
    """
    if isinstance(value, (bytes, bytearray, memoryview)):
        raise TypeError(
            f"{label} must be an iterable of {plural}, not "
            f"{type(value).__name__} -- decode first, e.g. "
            f"raw.decode('utf-8')"
        )


def _warn_dead_entry(message: str) -> None:
    # A fixed stacklevel always lands on library internals: the call
    # depth differs per entry point (Lexicon(), add(), unpickle,
    # dataclasses.replace, and the v1 shim's lazy snapshot -- built on
    # the first parse after a Constants mutation, several facade frames
    # below the user's own add()). Walk out of this module (and
    # dataclasses' replace frames, and the facade layer that builds
    # lexicons on the caller's behalf) so the warning points at the
    # caller's own line.
    level = 2
    frame: FrameType | None = sys._getframe(1)
    while frame is not None and frame.f_globals.get("__name__") in (
            __name__, "dataclasses",
            "nameparser._config_shim", "nameparser._facade"):
        frame, level = frame.f_back, level + 1
    warnings.warn(message, UserWarning, stacklevel=level)


def _normset(
    entries: Iterable[str], field_name: str, warn: bool = True,
) -> frozenset[str]:
    # Reject a bare str before iterating: iterating "dr" would silently
    # yield the single characters {'d', 'r'} -- the set(str) footgun on
    # the primary customization surface.
    if isinstance(entries, str):
        raise TypeError(
            f"Lexicon.{field_name} must be an iterable of strings, "
            f"not a bare string"
        )
    _reject_buffer(entries, f"Lexicon.{field_name}", "strings")
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
        # given_name_titles is the one field whose entries are matched as
        # a multi-word run, so it folds per word: stored as the same key
        # post_rules builds, or 'lt. col' would be kept verbatim and
        # never match anything (a silent no-op on the config surface).
        # Every other field holds single words, where the two folds
        # agree.
        n = _title_key(w.split()) if field_name == "given_name_titles" \
            else _normalize(w)
        # "." or "" is a data bug (stray split artifact, empty CSV
        # cell); dropping it silently would also let a data-module typo
        # vanish instead of failing CI.
        if not n:
            raise ValueError(
                f"Lexicon.{field_name} entry {w!r} normalizes to empty "
                f"(lowercase + strip periods/whitespace leaves nothing)"
            )
        # Every field but given_name_titles is matched one word at a
        # time, so a multi-word entry can never match -- the library
        # itself shipped eight such dead entries for years (repaired
        # 2026-07-26). Warn, never raise: an inert entry produces
        # nothing, and the given_name_titles precedent says a raise
        # here costs working configurations (see __post_init__).
        # warn=False is _edit()'s pass (both ops): add() warns via the
        # new instance's __post_init__; remove() stores nothing, so
        # warning there would name entries the caller is trying to get
        # RID of, with "split it" advice that makes no sense for a
        # no-op.
        if (warn and field_name != "given_name_titles"
                # interior whitespace test; split() covers all Unicode
                # whitespace
                and n != "".join(n.split())):
            _warn_dead_entry(
                f"Lexicon.{field_name} entries are matched one word at "
                f"a time; multi-word entry {w!r} can never match. "
                f"Split it into separate entries")
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
    _reject_buffer(raw, "capitalization_exceptions", "(key, value) pairs")
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
        # capitalized() looks words up one at a time (the _WORD regex
        # never yields spaces), so a multi-word key is unreachable.
        # interior whitespace test; split() covers all Unicode whitespace
        if normalized_key != "".join(normalized_key.split()):
            _warn_dead_entry(
                f"capitalization_exceptions keys are matched one word "
                f"at a time; multi-word key {k!r} can never match. "
                f"Split it into per-word entries")
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
    stripped -- so matching is case-insensitive. Vocabulary entries are
    single words -- a multi-word entry warns at construction and can
    never match (``given_name_titles``, matched as a space-joined run,
    is the one exception). Field docs below show examples, not full
    contents; inspect any field's shipped vocabulary directly, e.g.
    ``Lexicon.default().conjunctions``."""

    #: Pre-nominal titles ("dr", "sir", "capt", ...). Full default
    #: list: :data:`~nameparser.config.titles.TITLES`.
    titles: frozenset[str] = frozenset()
    #: Titles whose single following name reads as a GIVEN name
    #: ("sheikh", "sister", ...) rather than a family name. Full
    #: default list: :data:`~nameparser.config.titles.GIVEN_NAME_TITLES`.
    given_name_titles: frozenset[str] = frozenset()
    #: Post-nominal acronym suffixes, matched with or without periods
    #: ("phd" matches "PhD" and "Ph.D."). Full default list:
    #: :data:`~nameparser.config.suffixes.SUFFIX_ACRONYMS`.
    suffix_acronyms: frozenset[str] = frozenset()
    #: Post-nominal word suffixes ("jr", "esquire", "iii", ...). Full
    #: default list:
    #: :data:`~nameparser.config.suffixes.SUFFIX_WORDS`.
    suffix_words: frozenset[str] = frozenset()
    #: Subset of suffix_acronyms counted as suffixes only when written
    #: WITH periods -- their bare forms are common surnames ("ma",
    #: "do": "Jack Ma" keeps his family name). Full default list:
    #: :data:`~nameparser.config.suffixes.SUFFIX_ACRONYMS_AMBIGUOUS`.
    suffix_acronyms_ambiguous: frozenset[str] = frozenset()
    #: Family-name particles that chain onto the following piece
    #: ("van", "de", "bin", ...). Full default list:
    #: :data:`~nameparser.config.particles.PARTICLES`.
    particles: frozenset[str] = frozenset()
    #: Subset of particles that can also BE a given name ("Van
    #: Johnson", but also "Van Buren"). Membership decides nothing
    #: about chaining: the prefix chain skips index 0 unconditionally
    #: and never consults this set, so it leaves a leading particle a
    #: piece of its own whether listed or not -- "de Mesnil" groups
    #: into two pieces exactly as "van Gogh" does. What membership
    #: decides is what becomes of that piece afterwards. Under EITHER
    #: ``name_order`` a member records a particle-or-given ambiguity
    #: and a non-member records none, and a non-member is additionally
    #: folded back into the family name once roles exist, so the whole
    #: name is the surname ("de Mesnil" -- a bare "de", with nothing to
    #: fold into, is left alone). That fold is order-independent too
    #: (#359): a word that can never be a given name leaves
    #: ``name_order`` nothing to decide. Which field a MEMBER's piece
    #: lands in is ``name_order``'s question, not this set's.
    #: No constant of its own -- the default derives
    #: as particles minus
    #: :data:`~nameparser.config.particles.NON_GIVEN_NAME_PARTICLES`
    #: (which marks the opposite, never-given subset).
    particles_ambiguous: frozenset[str] = frozenset()
    #: Words or characters that join surrounding pieces into one
    #: ("and", "&", "y", "и", ...). Full default list:
    #: :data:`~nameparser.config.conjunctions.CONJUNCTIONS`.
    conjunctions: frozenset[str] = frozenset()
    #: Given-name prefixes that bind to the following word to form one
    #: given name ("abdul" -> "Abdul Salam"); never standalone names.
    #: Full default list:
    #: :data:`~nameparser.config.bound_given_names.BOUND_GIVEN_NAMES`.
    bound_given_names: frozenset[str] = frozenset()
    #: Marker words introducing a birth surname, routed to the maiden
    #: field ("née", "geb.", "roz.", ...). Full default list:
    #: :data:`~nameparser.config.maiden_markers.MAIDEN_MARKERS`.
    maiden_markers: frozenset[str] = frozenset()
    #: Family names for the unspaced-name segmentation stage (#271),
    #: matched longest-first against the start of the FIRST token
    #: written wholly in a script :attr:`Policy.segment_scripts
    #: <nameparser.Policy.segment_scripts>` activates. The default
    #: carries the Korean census list
    #: (:data:`~nameparser.config.surnames.KOREAN_SURNAMES`); Chinese
    #: surnames ship in locales.ZH because Han segmentation is opt-in.
    surnames: frozenset[str] = frozenset()
    #: Honorifics that may be peeled off the END of a name token
    #: (#308), matched longest-first: 田中さん splits into 田中 and さん
    #: before the tokens are classified. Every entry must also be a
    #: :attr:`suffix_words` entry -- the peeled tail is claimed by
    #: suffix classification like any other post-nominal. Deliberately
    #: NOT gated on :attr:`Policy.segment_scripts
    #: <nameparser.Policy.segment_scripts>` (unlike :attr:`surnames`
    #: above): 田中さん peels under the default policy, where HAN is in
    #: no activation set, because a tail entry carries its own license
    #: to fire. Entries are matched against the RAW token text, and
    #: only within a name containing a non-ASCII character, so an ASCII
    #: or mixed-case entry is at best conditionally active -- a ``"Jr"``
    #: entry is stored ``"jr"`` and matches only lowercase text. The
    #: field is effectively CJK-scoped in 2.1, which is what the shipped
    #: vocabulary is. Full default list:
    #: :data:`~nameparser.config.suffixes.GLUED_HONORIFICS`.
    honorific_tails: frozenset[str] = frozenset()
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
        for marker, base, why in _SUBSET_FIELDS:
            orphans = getattr(self, marker) - getattr(self, base)
            if orphans:
                raise ValueError(
                    f"{marker} marks a subset of {base}; "
                    f"not in {base}: {', '.join(sorted(orphans))} "
                    f"({why}). Add them to {base}, or drop them from "
                    f"{marker}"
                )
        # NOT validated: given_name_titles against titles. The lookup
        # key is the space-joined run of Role.TITLE tokens, built by the
        # parse rather than drawn from this vocabulary, and a
        # conjunction inside a run is itself tagged Role.TITLE -- so
        # "sir and dame" is a matchable key whose middle word is in
        # conjunctions, not titles. A whole-entry check rejected
        # multi-word entries; a per-word check rejected that one. An
        # unreachable entry here is inert: nothing consults it, nothing
        # misparses. That is the cheap failure, and guarding it proved
        # the expensive one -- three working configurations broken
        # across two attempts. Do not add a third.
        #
        # The v2 form of particles.py's NON_GIVEN_NAME_PARTICLES-disjoint-
        # from-BOUND_GIVEN_NAMES assertion. That module guards its own
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
        # suffix_as_written ORs the acronym and word branches, so a word
        # membership bypasses the period gate the ambiguous set exists
        # to impose: listing 'ma' in suffix_words would make "Jack Ma"
        # read as a suffix and lose the family name.
        gate_bypassed = self.suffix_acronyms_ambiguous & self.suffix_words
        if gate_bypassed:
            raise ValueError(
                f"an ambiguous suffix acronym must not also be a suffix "
                f"word; in both: {', '.join(sorted(gate_bypassed))}. The "
                f"word branch matches without periods, which bypasses the "
                f"period gate suffix_acronyms_ambiguous exists to impose"
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
        # Re-run construction validation rather than trusting the blob.
        # The layout check above catches SHAPE skew; this catches
        # CONTENT skew, which is likelier -- particles_ambiguous flipped
        # meaning between v1's never-given set and v2's may-be-given set
        # without changing its name, so an old pickle would otherwise
        # load a semantically inverted lexicon in silence. Rebuilds
        # _cap_map for free, which this used to do by hand.
        self.__post_init__()
        # __post_init__ also normalizes, and quietly accepting a
        # rewritten value would make this a place where caller data
        # changes without a word. A pickle this library wrote is always
        # normalized already (_normalize converges), so a difference
        # here means the state came from somewhere else -- say so while
        # the offending entries can still be named.
        # One pass per field, in _VOCAB_FIELDS declaration order. cast is
        # safe: __post_init__ just ran _normset over each of these and
        # raised for anything that was not an iterable of str.
        drifted = []
        for name in _VOCAB_FIELDS:
            lost = frozenset(
                cast("Iterable[str]", state[name])) - getattr(self, name)
            if lost:
                drifted.append(f"{name}: {', '.join(sorted(lost))}")
        # the pair field too, or ten fields raise and the eleventh is
        # quietly re-canonicalized (keys normalized, sorted, deduped)
        given_pairs = cast("Iterable[tuple[str, str]]",
                          state["capitalization_exceptions"])
        if tuple(given_pairs) != self.capitalization_exceptions:
            drifted.append("capitalization_exceptions")
        if drifted:
            raise ValueError(
                "incompatible Lexicon pickle: entries are not normalized "
                f"({'; '.join(drifted)}); this state was not written by "
                "this version of nameparser"
            )

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
            # warn=False: this pass only computes the new set membership,
            # never stores it directly. add() still warns exactly once,
            # from the replaced instance's own __post_init__ -> _normset;
            # remove() never reaches __post_init__ with the dead entry
            # (it is subtracted out here), so it stays silent -- correct,
            # since a removal stores nothing a warning could be about.
            # That silence covers the entry BEING REMOVED only: a
            # different multi-word entry still stored re-warns from the
            # derived instance's __post_init__, since the warning is
            # per-construction by design.
            normalized = _normset(words, name, warn=False)
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
    from nameparser.config.bound_given_names import BOUND_GIVEN_NAMES
    from nameparser.config.capitalization import CAPITALIZATION_EXCEPTIONS
    from nameparser.config.conjunctions import CONJUNCTIONS
    from nameparser.config.maiden_markers import MAIDEN_MARKERS
    from nameparser.config.particles import NON_GIVEN_NAME_PARTICLES, PARTICLES
    from nameparser.config.suffixes import (
        GLUED_HONORIFICS, SUFFIX_ACRONYMS, SUFFIX_ACRONYMS_AMBIGUOUS,
        SUFFIX_WORDS,
    )
    from nameparser.config.surnames import KOREAN_SURNAMES
    from nameparser.config.titles import GIVEN_NAME_TITLES, TITLES

    # every vocabulary constant is a frozenset since #293, so each one
    # feeds its strictly-typed frozenset[str] field as it stands -- and
    # this cache reading them ONCE is the reason they are frozen. A
    # mutated module set always reached a freshly built Constants, and
    # reached this Lexicon only when the edit landed before the first
    # call; after it, the cache was already built and the same edit was
    # invisible here. Which of the two a program got was not something
    # the code doing the mutating could see.
    # keep in sync with _config_shim.Constants._snapshot() (pinned by the
    # default-Constants equality test in tests/v2/test_config_shim.py)
    return Lexicon(
        titles=TITLES,
        given_name_titles=GIVEN_NAME_TITLES,
        suffix_acronyms=SUFFIX_ACRONYMS,
        suffix_words=SUFFIX_WORDS,
        suffix_acronyms_ambiguous=SUFFIX_ACRONYMS_AMBIGUOUS,
        particles=PARTICLES,
        # FLIPPED from v1: v1 marks the never-given subset; v2 marks the
        # may-be-given subset (migration: complement translation).
        particles_ambiguous=PARTICLES - NON_GIVEN_NAME_PARTICLES,
        conjunctions=CONJUNCTIONS,
        bound_given_names=BOUND_GIVEN_NAMES,
        maiden_markers=MAIDEN_MARKERS,
        surnames=KOREAN_SURNAMES,
        honorific_tails=GLUED_HONORIFICS,
        # pass canonical pair-tuples so this strictly-typed call site never
        # feeds a Mapping to the tuple-annotated field; __post_init__
        # still tolerates a Mapping at runtime for interactive use
        capitalization_exceptions=tuple(sorted(CAPITALIZATION_EXCEPTIONS.items())),
    )
