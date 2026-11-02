"""Immutable vocabulary configuration: a Lexicon holds readings, what
each word may be read as, and compiles the sets a parse reads from them
(3.0's 4i-b; decisions/vocabulary-model, 2026-11-02 #754).

Layering: may import nameparser.config DATA modules as the single
source of vocabulary -- never the nameparser.config package itself --
and nameparser._reading_index, the shared compiler and the index's
reader, at call time only: tools/vocab/build.py loads this module by
path. Enforced by tests/v2/test_layering.py.
"""
from __future__ import annotations

import dataclasses
import functools
import sys
import unicodedata
import warnings
from collections.abc import Iterable, Mapping, Set
from dataclasses import dataclass, field
from types import FrameType, MappingProxyType, ModuleType
from typing import TYPE_CHECKING, Any, NamedTuple, cast

#: Vocabulary set fields, in declaration order. add()/remove() operate
#: on exactly these and reject capitalization_exceptions (its entries
#: are pairs -- use dataclasses.replace); __or__ unions these AND merges
#: capitalization_exceptions right-biased.
_VOCAB_FIELDS = (
    "titles", "given_name_titles", "suffix_acronyms", "suffix_words",
    "suffix_acronyms_ambiguous", "particles", "particles_ambiguous",
    "conjunctions", "conjunctions_ambiguous", "bound_given_names",
    "given_name_abbreviations",
    "maiden_markers", "surnames", "honorific_tails", "after_given_titles",
    "suffix_words_ambiguous", "agnomens", "titles_ambiguous",
    "title_modifiers", "title_styles", "title_phrases", "given_names",
)

#: The metadata key a Lexicon field added after `Lexicon` first shipped
#: carries, naming the release that added it, with a default: a pickle
#: written before that release lacks the field and loads with the
#: default. The same string as `_types.ADDED_IN`, the key the other
#: frozen types' shared guard reads; layering keeps this module from
#: importing `_types`, so tests/v2/test_lexicon.py holds the two equal.
_ADDED_IN = "nameparser.added_in"

#: The fields whose entries may be PHRASES: stored space-joined and
#: folded per word (_title_key), and exempt from the dead-entry warning
#: below. Every other field is matched one word at a time, where a
#: multi-word entry can never match.
#:
#: The two are not the same mechanism, and the difference is why the
#: exemption is a list rather than a rule. A given_name_titles run is
#: identified per word FIRST -- 'lt' and 'col' are each title
#: vocabulary -- and only then looked up, as the whole run's key or as
#: its LAST word's (_run_addresses_by_given, #489). The whole-run arm
#: is the one a phrase entry is matched by; the last-word arm is a
#: single word and cannot reach a phrase, so storage stays what it was
#: (the two are asked together, not in precedence). A maiden marker
#: phrase has no such per-word foothold: 'z' and 'domu' are not markers
#: individually, and adding them separately (which this warning used to
#: advise) reads 'Maria Kowalska z domu Nowak' as maiden 'domu Nowak'
#: and strips 'Anna z Nowak' of its family name. So markers are matched
#: by a genuine multi-token lookahead instead --
#: _pipeline._vocab.maiden_marker_run, longest first -- and only the
#: STORAGE rule is shared with titles.
_PHRASE_FIELDS = ("given_name_titles", "maiden_markers", "title_phrases")


#: Every character the parser reads as a full stop at a WORD'S EDGE
#: (#322/#323): the ASCII period, the fullwidth FULL STOP U+FF0E, the
#: IDEOGRAPHIC FULL STOP U+3002 and its halfwidth form U+FF61. One
#: string, four readers -- the lookup fold below, _vocab's script
#: classification fold, _script_segment's surname site and honorific
#: tail match -- so that "which characters are a period" is answered
#: once; the bundle's fifth site, _pieces' opening-abbreviation shape,
#: reads no stop set at all but the no-initials repertoire
#: (_policy._NO_INITIALS) that licenses every reader here. NFKC is
#: NOT a substitute for listing them: it folds U+FF0E to '.' and
#: U+FF61 to U+3002, and leaves U+3002 as it is.
#: Not every period test reads this set, and the ones that do not are
#: named so the claim is checkable: the interior-period shapes -- the
#: dotted acronym 'M.A.' and the split 'Ph. D.' (_vocab) -- and FOUR
#: ASCII-only edge tests on Latin shapes, across THREE modules -- the
#: initial 'J.' (_vocab), the bracketed credential '(Mgr.)' and the
#: word-internal apostrophe rule (_extract), and the trailing
#: middle-initial carve-out 'V.' (_assign) -- stay ASCII. That is a
#: fact about those TESTS and not about this set's reach: the fold
#: below is script-agnostic, so a LATIN word wearing a wide stop
#: reaches vocabulary the ASCII veto would have taken it out of.
#: 'V。' folds to 'v' and does not end in the ASCII period the
#: trailing-suffix carve-out tests (_assign, not is_initial), so
#: it is roman five -- suffix -- where 'V.' stays a middle
#: initial through that same carve-out; 'Jr。' simply reaches its
#: entry, and 'Dr。' its title.
#: decisions/cjk-full-stops carries the measurements.
FULL_STOPS = ".．。｡"


def _normalize(word: str) -> str:
    """Lowercase, NFC-compose, strip whitespace and EDGE full stops
    (FULL_STOPS, not the ASCII period alone -- #322). Interior periods
    survive on purpose: 'J.R.' must not collapse to 'jr' and hit the
    periodless vocabulary (v1 parity, pinned live 2026-07-17).
    Suffix-ACRONYM membership alone uses the period-free form (see
    _vocab.suffix_as_written), mirroring v1's is_suffix, which removed
    periods only for the acronym test.

    lower(), NOT casefold(): casefold's caseless-matching folds mutate
    the stored vocabulary itself -- 'κος' becomes the misspelling 'κοσ'
    (final sigma flattened) and 'großfürst' becomes 'grossfürst' --
    while lower() applies Unicode SpecialCasing contextually and keeps
    both as authored. This function is the single fold for storage AND
    match-time lookups, so matching stays symmetric either way; lower()
    is what v1's lc() used, preserving which cross-spellings match.

    NFC, since #322, and only for a non-ASCII word (ASCII is already
    NFC, and this runs per token on the parse path --
    decisions/parse-cost). NFD hangul decomposes to jamo and missed
    every vocabulary entry; composing at lookup AND at storage keeps
    the two symmetric, and no shipped entry changes under it (measured
    2026-09-09: fold every string member of every Lexicon.default()
    field through NFC and count the changes; zero of 1735). This is
    the same NFC composition script classification already applies
    (_vocab._normalized_for_script); token text is never rewritten.

    Strips to a FIXED POINT. A single strip().strip(FULL_STOPS) leaves
    stops-around-whitespace half done ('. a .' -> ' a '), so a value
    that is re-normalized later -- on unpickle, or by a second add() --
    would change under its owner. v1 never re-normalized, so this only
    matters now that storage and match-time share one fold."""
    word = word.lower()
    if not word.isascii():
        word = unicodedata.normalize("NFC", word)
    while True:
        stripped = word.strip().strip(FULL_STOPS)
        if stripped == word:
            return word
        word = stripped


# rules/P7: "A one-letter word written with its period is an
# initial and not a particle"
def _spells_an_initial(n: str, text: str) -> bool:
    """Whether `text` is ONE letter written with its period ('Ó.',
    'j.'), which makes it an initial whatever particle the letter also
    spells (#604). `n` is `_normalize(text)`, folded once by the caller.

    Every particle test asks this AFTER its membership hit, so a word
    no particle set holds never pays the frame. It lives here rather
    than in _pipeline._vocab because _render's case repair, which
    re-reads the particle vocabulary over a parsed name, must ask it
    too and may not import the pipeline (the 2.x facade's initials and
    last-name split were a second such reader).

    The ASCII period only, as `_vocab.is_initial` takes it: a CJK full
    stop marks no initial ('Ó。' is the particle). The other half of
    is_initial, the scripts that write no initials (#320), is NOT asked
    -- its script table is _policy's, which this module may not import
    -- so a caller's one-character particle in such a script, written
    with a period, is vetoed where is_initial would call it no initial
    (decisions/P7). No shipped particle is one character of those
    scripts."""
    return len(n) == 1 and text[-1] == "."


def _fold_words(words: Iterable[str]) -> list[str]:
    """The words of a title run, folded for storage and lookup.

    A multi-word title is matched as one key ('lt col'), so the fold has
    to run per word -- _normalize on the whole phrase would leave
    interior periods.

    Words that fold away are DROPPED, not kept as empty. Keeping the
    gap makes the key non-idempotent -- 'lt .' would store 'lt ', which
    match time can never build: a run CAN carry a lone '.' (the
    conjunction merge puts one there), but the fold drops the empty
    word, so the key is 'lt' and the stored entry is inert. Storage
    re-runs this fold on unpickle and on every dataclasses.replace, so a
    value that changes under a second pass is one Lexicon later rejects as
    "not written by this version". _normalize converges for the same
    reason; so must anything built on top of it.

    A LIST, so that _run_addresses_by_given's last-word arm can be the
    last word of this fold rather than a re-split of the joined key --
    "the last word of the FOLDED key" is then structural, and the two
    arms read one fold between them.

    map/filter rather than a comprehension: both are C calls where a
    comprehension is a Python frame on 3.11, and this runs on the parse
    path for every name carrying a title run (decisions/parse-cost).
    """
    return list(filter(None, map(_normalize, words)))


def _title_key(words: Iterable[str]) -> str:
    """The given_name_titles lookup key for a run of title words: the
    folded words, space-joined.

    Defined once because it is built at match time
    (_run_addresses_by_given, which is how post_rules' H1 and group's
    P5 licence both reach it) and at construction (_normset's
    given_name_titles), and a divergence between them fails silently:
    the entry simply stops matching."""
    return " ".join(_fold_words(words))


def _run_addresses_by_given(words: Iterable[str],
                            vocabulary: Set[str]) -> bool:
    """Whether a run of title words addresses by the GIVEN name.

    Two sites ask it and they must agree -- post_rules for H1, group
    for the P5 licence -- because a run read two ways is a rule
    contradicting itself (decisions/P5, the 2026-08-22 #369 entry).
    One predicate, so they cannot drift.

    The WHOLE run's key, or that key's LAST word (#489): a run is
    written as several titles and addresses the way its final one does,
    so 'Her Majesty Queen' addresses by given name because 'queen'
    does. The two arms are asked of one key and neither is the other's
    fallback -- the `or` short-circuits but decides nothing, since for
    a one-word run the key IS its last word. Both arms read one
    _fold_words list, so the last word is the last word of the FOLDED
    key by construction rather than by agreement, and a run token that
    folds away cannot empty that arm: the conjunction merge can put a
    lone '.' in the run ('Sir and . John'), and the fold drops it.
    What the drop leaves as the last word can then be the CONJUNCTION
    -- 'Sir and . John' keys 'sir and' and reads family 'John', where
    'Sir and Dame John' keys 'sir and dame' and reads given. Harmless
    on the shipped vocabulary, which holds no entry ending in a
    connective, and a caller who stored one would be asking for it
    (measured 2026-09-09).

    The whole-run arm is what keeps a caller's multi-word phrase entry
    working: 'lt col' is stored as one key and matched as one run. Over
    the SHIPPED vocabulary it is dead -- every shipped entry is a single
    word (asserted in test_lexicon.py), so it can only ever match a
    one-word run, which is a run the last-word arm reads the same way.

    H2's unlisted abbreviations ride in the run. One can never match as
    the last-word key, being in no vocabulary by definition -- written
    as the inputs that produce those runs, 'Xyz. Sir John' keys 'xyz
    sir', matches on 'sir' and reads given 'John', while 'Sir Xyz.
    John' keys 'sir xyz', matches on neither arm and reads family
    'John'. It CAN sit inside a whole-run key that matches, because
    given_name_titles is deliberately not validated against titles: a
    caller who stores 'sir xyz' makes 'Sir Xyz. John' read given.

    The vocabulary is passed in rather than read off a default: a
    caller's own Lexicon is the one that has to be consulted, and this
    module is where Lexicon is defined."""
    folded = _fold_words(words)
    if not folded:
        # every word folded away, so there is no key and no last word:
        # the joined spelling built "" here, which matched nothing
        return False
    return " ".join(folded) in vocabulary or folded[-1] in vocabulary


def _reject_buffer(value: object, label: str, plural: str) -> None:
    """Binary sequences iterate to INTS, so every downstream entry check
    reports a byte value -- "must be strings, got 100" for b'dr', where
    100 is 'd'. That names neither the cause nor the fix. v1 shipped a
    decode hint for this (#238), and parse() carries one, so no config
    entry point should be the odd one out.
    """
    if isinstance(value, (bytes, bytearray, memoryview)):
        raise TypeError(
            f"{label} must be an iterable of {plural}, not "
            f"{type(value).__name__} -- decode first, e.g. "
            f"raw.decode('utf-8')"
        )


def _warn_at_caller(message: str) -> None:
    # A fixed stacklevel always lands on library internals: the call
    # depth differs per entry point (Lexicon(), add(), unpickle,
    # dataclasses.replace). Walk out of this module (and dataclasses'
    # replace frames) so the warning points at the caller's own line.
    level = 2
    frame: FrameType | None = sys._getframe(1)
    while frame is not None and frame.f_globals.get("__name__") in (
            __name__, "dataclasses"):
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
        # A phrase field's entries are matched as a multi-word run, so
        # they fold per word: stored as the same key the match site
        # builds, or 'lt. col' (and 'z. domu') would be kept verbatim
        # and never match anything -- a silent no-op on the config
        # surface. Every other field holds single words, where the two
        # folds agree. See _PHRASE_FIELDS for how the two differ once
        # stored.
        n = _title_key(w.split()) if field_name in _PHRASE_FIELDS \
            else _normalize(w)
        # "." or "" is a data bug (stray split artifact, empty CSV
        # cell); dropping it silently would also let a data-module typo
        # vanish instead of failing CI.
        if not n:
            raise ValueError(
                f"Lexicon.{field_name} entry {w!r} normalizes to empty "
                f"(lowercase + strip full stops/whitespace leaves nothing)"
            )
        # Every field outside _PHRASE_FIELDS is matched one word at a
        # time, so a multi-word entry can never match -- the library
        # itself shipped eight such dead entries for years (repaired
        # 2026-07-26). Warn, never raise: an inert entry produces
        # nothing, and the given_name_titles precedent says a raise
        # here costs working configurations (see __post_init__).
        # warn=False is _edit()'s pass (both ops): add() warns via the
        # new instance's __post_init__; remove() stores nothing, so
        # warning there would name entries the caller is trying to get
        # RID of, with "split it" advice that makes no sense for a
        # no-op. Both invariants are indifferent to WHICH fields are
        # exempt: the exemption only decides whether a warning exists to
        # be emitted once or suppressed.
        if (warn and field_name not in _PHRASE_FIELDS
                # interior whitespace test; split() covers all Unicode
                # whitespace
                and n != "".join(n.split())):
            _warn_at_caller(
                f"Lexicon.{field_name} entries are matched one word at "
                f"a time; multi-word entry {w!r} can never match. "
                f"Split it into separate entries")
        normalized.add(n)
    return frozenset(normalized)


def _alnum(text: str) -> str:
    return "".join(c for c in text if c.isalnum())


def _offered_mask(normalized_key: str) -> str:
    """The working value a mismatched-mask error offers: the
    key upper-cased, or the key unchanged -- an identity mask, always
    legal -- where .upper() changes the letter count ('straße' ->
    'STRASSE') and would fail the check if pasted back in."""
    upper = normalized_key.upper()
    return upper if _alnum(_normalize(upper)) == _alnum(
        normalized_key) else normalized_key


class _MaskValueError(ValueError):
    """_normpairs' error for a value that does not spell its key.
    Built in the UnicodeDecodeError idiom -- structure in, message
    out: `key`, `normalized_key` and `value` are the offending inputs;
    `offered` (the fix quoted in the message below) is computed from
    them, not carried separately.

    __reduce__ is explicit because the inherited one re-calls
    __init__ with self.args, which holds the message alone, not the
    three fields __init__ needs -- and a ProcessPoolExecutor pickles a
    worker's exception to deliver it, surfacing a construction failure
    as BrokenProcessPool. Passing self.__dict__ as reduce's third
    element (restored via a plain __dict__.update, there being no
    __setstate__ here) carries along anything added after construction
    -- e.g. add_note() -- that reconstructing from the three fields
    alone would not. (An exception, so _types.py's frozen-dataclass
    pickle guards do not apply.)"""

    def __init__(self, key: str, normalized_key: str, value: str) -> None:
        self.key = key
        self.normalized_key = normalized_key
        self.value = value
        self.offered = _offered_mask(normalized_key)
        super().__init__(
            f"capitalization_exceptions value {value!r} for key {key!r} "
            f"does not spell the key's letters and digits: a value "
            f"is a case mask, the key's own letters and digits "
            f"recased -- e.g. "
            f"capitalization_exceptions=(({normalized_key!r}, "
            f"{self.offered!r}),)")

    def __reduce__(
        self,
    ) -> tuple[type[_MaskValueError], tuple[str, str, str], dict[str, object]]:
        return (type(self), (self.key, self.normalized_key, self.value),
                self.__dict__)


def _normpairs(
    raw: Mapping[str, str] | Iterable[tuple[str, str]],
) -> tuple[tuple[str, str], ...]:
    """Canonicalize capitalization_exceptions input: _normset's sibling
    for the one pair-valued field. Dedupes on the NORMALIZED key so the
    tuple and the derived map always agree ("PHD" and "phd" collide
    after normalization; "Ph.D." does not, the fold keeping interior
    periods, so it is a key of its own, "ph.d"); last occurrence wins,
    matching dict semantics and the right-bias rule used elsewhere."""
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
                f"empty (lowercase + strip full stops/whitespace leaves "
                f"nothing)"
            )
        # Stored NFC-composed, case kept (unicodedata, not _normalize):
        # one stored spelling per value, whichever form the caller
        # wrote. _apply_mask reads both forms alike since #542
        # (_render._beside looks past combining marks); before it, a
        # decomposed letter read as a base letter split off beside a
        # non-alpha combining mark. The mask check below
        # passes either spelling, _normalize composing both of its
        # sides. `written` keeps the caller's own spelling -- composed
        # or not -- for the mismatch error below: a decomposed value
        # (e.g. 'e' + a combining acute) and its NFC form print
        # identically to a reader's eye but are different str objects,
        # so echoing the composed spelling back would show the caller
        # a value they did not write.
        written = v
        v = unicodedata.normalize("NFC", v)
        # capitalized() looks words up one at a time (the _WORD regex
        # never yields spaces), so a multi-word key is unreachable --
        # checked FIRST, ahead of the mask check below, because an
        # invariant guards harm and a value that can never be read
        # does no harm no matter what it says (AGENTS.md: "a check
        # guards harm, not no-ops"). Raising the mask error for such a
        # key -- as a naive mask-first order does -- would refuse a
        # config that was always going to be a no-op.
        # interior whitespace test; split() covers all Unicode whitespace
        if normalized_key != "".join(normalized_key.split()):
            _warn_at_caller(
                f"capitalization_exceptions keys are matched one word "
                f"at a time; multi-word key {k!r} can never match. "
                f"Split it into per-word entries")
            deduped[normalized_key] = v
            continue
        # A value is a case MASK (#459): the key's own letters and
        # digits recased, compared through the key's own fold. Its
        # punctuation marks which letters are joined into one run
        # (_render._apply_mask reads that) and is never written into
        # the word. A raise, not a warning: a mismatched value used to
        # be SUBSTITUTED for the word, and rules/R4: "Repair
        # changes case and nothing else", so there is no reading of
        # one that repair can honor.
        if _alnum(_normalize(v)) != _alnum(normalized_key):
            # key is the RAW key, not normalized_key, and `written`,
            # not `v`: the message names the entry as the caller wrote
            # it, not as the fold or NFC composed it.
            raise _MaskValueError(k, normalized_key, written)
        deduped[normalized_key] = v
    return tuple(sorted(deduped.items()))


#: The two lists outside the per-word model (decisions/vocabulary-model's
#: Standing line on name readings): `Lexicon` fields, changed through
#: ``|`` with a fragment or ``dataclasses.replace``, and copied into
#: `_LexiconSets` beside the compiled sets.
_LIST_FIELDS = ("surnames", "given_names")

#: The 20 sets a compile of readings gives, under the names the 2.x
#: `Lexicon` fields had: internal since 3.0 (#754, 4i-b), read through
#: `Lexicon._sets`, and the names an old spelling is refused by.
_SET_FIELDS = tuple(f for f in _VOCAB_FIELDS if f not in _LIST_FIELDS)

#: The kinds those sets do not record, which the views read (rules/R8,
#: rules/R9): `_LexiconSets` attributes after the `_VOCAB_FIELDS` ones,
#: each a compiled constant of its own.
_KIND_FIELDS = ("generation_words", "credential_words",
                "patronymic_particles")

#: Each marker set over the base set it qualifies. A compile from
#: readings holds every pair by construction, the marker existing only
#: beside its base reading; `_parser._apply_choice` reads the pairs to
#: drop a word's marks where a choice drops it from the base.
_MARKER_BASES = (
    ("particles_ambiguous", "particles"),
    ("suffix_acronyms_ambiguous", "suffix_acronyms"),
    ("honorific_tails", "suffix_words"),
    ("suffix_words_ambiguous", "suffix_words"),
)


@dataclass(frozen=True, slots=True, eq=False, repr=False)
class _LexiconSets:
    """The vocabulary sets a parse reads: the pipeline, `_render`,
    `_parser` and the tools read `lexicon._sets.titles` (#754, 4i-a;
    tests/v2/test_layering.py holds it), the 2.x public fields having
    become internal in 4i-b. One attribute per `_VOCAB_FIELDS` entry, in
    that order, then one per `_KIND_FIELDS` entry, each a frozenset, so
    a membership test stays a C-level attribute read and costs no frame.

    Built once per `Lexicon`, at construction: the compiled sets from
    its readings by `compile_readings`, or for `Lexicon.default()` from
    nameparser/config/_compiled.py, so the reading index stays unloaded
    on `parse("John Smith")`; the two lists from its fields. Never
    compared, hashed or pickled: a `Lexicon`'s equality and pickle are
    its fields', and a load or a `dataclasses.replace` builds this
    again.

    Not a mapping and no repr of its own: it holds whole word lists,
    and a repr of them would be unbounded."""

    titles: frozenset[str]
    given_name_titles: frozenset[str]
    suffix_acronyms: frozenset[str]
    suffix_words: frozenset[str]
    suffix_acronyms_ambiguous: frozenset[str]
    particles: frozenset[str]
    particles_ambiguous: frozenset[str]
    conjunctions: frozenset[str]
    conjunctions_ambiguous: frozenset[str]
    bound_given_names: frozenset[str]
    given_name_abbreviations: frozenset[str]
    maiden_markers: frozenset[str]
    surnames: frozenset[str]
    honorific_tails: frozenset[str]
    after_given_titles: frozenset[str]
    suffix_words_ambiguous: frozenset[str]
    agnomens: frozenset[str]
    titles_ambiguous: frozenset[str]
    title_modifiers: frozenset[str]
    title_styles: frozenset[str]
    title_phrases: frozenset[str]
    given_names: frozenset[str]
    #: the suffix words whose suffix reading is a generation (`jr`,
    #: `iii`), a credential written as a word (`kc`), and the particles
    #: read as patronymics (`bin`): the kinds rules/R8's and rules/R9's
    #: views read, which the sets above do not record
    generation_words: frozenset[str]
    credential_words: frozenset[str]
    patronymic_particles: frozenset[str]


#: Lexicon field -> the compiled constant it is read from, for every
#: set the vocabulary compiles (nameparser/_reading_index.py's
#: Compiled); `particles_ambiguous` is derived (_vocab_fields below).
#: tests/v2/test_parser.py holds that these, read from the compile of
#: no choice, are Lexicon.default()'s.
_COMPILED_FIELDS = {
    "titles": "TITLES",
    "given_name_titles": "GIVEN_NAME_TITLES",
    "suffix_acronyms": "SUFFIX_ACRONYMS",
    "suffix_words": "SUFFIX_WORDS",
    "suffix_acronyms_ambiguous": "SUFFIX_ACRONYMS_AMBIGUOUS",
    "particles": "PARTICLES",
    "conjunctions": "CONJUNCTIONS",
    "conjunctions_ambiguous": "CONJUNCTIONS_AMBIGUOUS",
    "bound_given_names": "BOUND_GIVEN_NAMES",
    "given_name_abbreviations": "GIVEN_NAME_ABBREVIATIONS",
    "maiden_markers": "MAIDEN_MARKERS",
    "honorific_tails": "GLUED_HONORIFICS",
    "after_given_titles": "AFTER_GIVEN_TITLES",
    "suffix_words_ambiguous": "SUFFIX_WORDS_AMBIGUOUS",
    "agnomens": "AGNOMENS",
    "titles_ambiguous": "TITLES_AMBIGUOUS",
    "title_modifiers": "TITLE_MODIFIERS",
    "title_styles": "TITLE_STYLES",
    "title_phrases": "TITLE_PHRASES",
    "generation_words": "GENERATION_WORDS",
    "credential_words": "CREDENTIAL_WORDS",
    "patronymic_particles": "PATRONYMIC_PARTICLES",
}


def _vocab_fields(compiled: Mapping[str, Any]) -> dict[str, frozenset[str]]:
    """The sets a compile of the vocabulary gives, by `_LexiconSets`
    name (the constants of nameparser/config/_compiled.py, or a compile
    of readings), the two lists aside."""
    out = {name: compiled[key] for name, key in _COMPILED_FIELDS.items()}
    # FLIPPED from v1: v1 marked the never-given subset; the sets mark
    # the may-be-given one
    out["particles_ambiguous"] = (compiled["PARTICLES"]
                                  - compiled["NON_GIVEN_NAME_PARTICLES"])
    return out


@functools.cache
def _default_compiled() -> Mapping[str, frozenset[str]]:
    # the compiled data module is the default's one source, so the
    # default never loads the reading index (decisions/vocabulary-
    # model, 2026-10-29 3a; its 2026-11-02 #754 entry, item 4)
    import nameparser.config._compiled as compiled
    return MappingProxyType(_vocab_fields(vars(compiled)))


_NO_SETS: Mapping[str, frozenset[str]] = MappingProxyType(
    {name: frozenset() for name in _COMPILED_FIELDS} | {
        "particles_ambiguous": frozenset()})


# -- readings ------------------------------------------------------------

#: A reading's properties as the log and the repr compare them: sorted
#: (key, value) pairs, a list value a sorted tuple.
_Props = tuple[tuple[str, Any], ...]


class _Edit(NamedTuple):
    """One `add` or `remove`, stored frozen as written (decisions/
    vocabulary-model, 2026-11-02 #754, item 3): its words normalized,
    its kind (None on a `remove` of every reading), its properties
    sorted pairs, a property given its unwritten value held as None,
    which removes it. Compared and hashed as a tuple."""

    op: str
    words: tuple[str, ...]
    kind: str | None
    props: _Props


def _index_module() -> ModuleType:
    # the reading index's reader, imported at call time: tools/vocab/
    # build.py loads this module by path, before the index it rewrites
    # can be trusted to import (root AGENTS.md's layering bullet)
    import nameparser._reading_index as ri
    return ri


def _clean(props: Mapping[str, Any]) -> _Props:
    """A reading's properties as a caller states them: `default` (a
    caller's reading is on) and `cased` (a case mask, configured through
    `capitalization_exceptions`) left out."""
    return tuple(sorted((k, v) for k, v in props.items()
                        if k not in ("default", "cased")))


def _unwritten(kind: str, prop: str) -> object:
    """The value `prop` takes on a `kind` reading that does not write
    it, read through _reading_index.ReadingProperties: `acronym` is
    true on a credential, `addresses` the family name."""
    if prop == "acronym":
        return kind == "credential"
    if prop == "addresses":
        return "family"
    return False


def _prop_value(kind: str, prop: str, value: object) -> object:
    """`value` canonical for the log, None where it is the unwritten
    one (which removes the property)."""
    if value is None or (isinstance(value, (bool, str))
                         and value == _unwritten(kind, prop)):
        return None
    if prop in ("acronym", "after_given", "may_be_initial"):
        if not isinstance(value, bool):
            raise TypeError(f"{prop} must be True or False, got {value!r}")
        return value
    if prop == "addresses":
        if value != "given":
            raise ValueError(f"addresses must be 'given' or 'family', "
                             f"got {value!r}")
        return value
    if prop == "attached":
        if value != "after":
            raise ValueError(f"attached must be 'after' (a tail peeled "
                             f"off the end of a name token) or None, "
                             f"got {value!r}")
        return value
    if prop == "attaches":
        if isinstance(value, (str, bytes)) or isinstance(value, Mapping):
            raise TypeError(f"attaches must be an iterable of title kinds "
                            f"or title words, e.g. attaches=['military'], "
                            f"got {value!r}")
        try:
            items: tuple[object, ...] = tuple(cast("Iterable[object]", value))
        except TypeError:
            raise TypeError(f"attaches must be an iterable of title kinds "
                            f"or title words, got {value!r}") from None
        words = [x for x in items if isinstance(x, str)]
        if len(words) != len(items):
            raise TypeError(f"attaches entries must be strings, got "
                            f"{value!r}")
        folded = tuple(sorted({_normalize(x) for x in words} - {""}))
        return folded or None
    # same_as, a given name written short's full name (#789)
    if not isinstance(value, str) or not value.strip():
        raise TypeError(f"same_as must be the full given name, a "
                        f"non-empty string, got {value!r}")
    return value


def _check_kind(kind: object, op: str) -> str | None:
    ri = _index_module()
    if kind is None and op == "remove":
        return None
    if not isinstance(kind, str):
        raise TypeError(f"{op}() takes kind as a string, a vocabulary "
                        f"kind such as 'title' or 'credential', got "
                        f"{kind!r}")
    if kind in ri.CATEGORY:
        return kind
    categories = set(ri.CATEGORY.values())
    if kind in categories:
        if op == "remove":
            return kind
        raise ValueError(
            f"{kind!r} is a category with no kind of its name; add() "
            f"takes one of its kinds: " + ", ".join(
                k for k, c in ri.CATEGORY.items() if c == kind))
    raise ValueError(
        f"unknown reading kind {kind!r}; the kinds are "
        + ", ".join(ri.CATEGORY)
        + (" (or a category, on remove: "
           + ", ".join(sorted(categories)) + ")" if op == "remove" else ""))


def _edit_words(words: tuple[object, ...], op: str) -> tuple[str, ...]:
    if not words:
        raise TypeError(f"{op}() takes at least one word, e.g. "
                        f"{op}('dean', kind='title')")
    out = []
    for w in words:
        _reject_buffer(w, f"{op}() words", "strings")
        if not isinstance(w, str):
            raise TypeError(
                f"{op}() takes each word as its own argument, a string, "
                f"got {w!r}; unpack a collection: {op}(*words, kind=...)")
        n = _title_key(w.split())
        if not n:
            raise ValueError(f"{op}() word {w!r} normalizes to empty "
                             f"(lowercase + strip full stops/whitespace "
                             f"leaves nothing)")
        out.append(n)
    return tuple(out)


def _edit_props(kind: str, props: Mapping[str, object]) -> _Props:
    ri = _index_module()
    allowed = ri.indexed(kind) - {"default", "cased"}
    out: dict[str, object] = {}
    for prop, value in props.items():
        if prop == "default":
            raise ValueError(
                "add() takes no default: a caller's reading is on, which "
                "is the caller's choice; take one out with remove(word, "
                "kind=...)")
        if prop == "cased":
            raise ValueError(
                "add() takes no cased: a case mask is configured through "
                "capitalization_exceptions, e.g. dataclasses.replace("
                "lexicon, capitalization_exceptions=(*lexicon."
                "capitalization_exceptions, ('phd', 'PhD')))")
        if prop not in allowed:
            raise ValueError(
                f"a {kind} reading takes "
                + (", ".join(sorted(allowed)) or "no properties")
                + f"; got {prop!r}")
        out[prop] = _prop_value(kind, prop, value)
    return tuple(sorted(out.items()))


def _make_edit(op: object, words: object, kind: object,
               props: object) -> _Edit:
    """An edit checked and canonical: what `add` and `remove` store and
    what a constructor's `_edits` must already be."""
    if op not in ("add", "remove"):
        raise ValueError(f"an edit is 'add' or 'remove', got {op!r}")
    if not isinstance(words, tuple):
        raise TypeError(f"an edit's words are a tuple, got {words!r}")
    ws = _edit_words(words, op)
    k = _check_kind(kind, op)
    if op == "remove":
        if props:
            raise ValueError(f"remove() takes no properties, got {props!r}")
        return _Edit(op, ws, k, ())
    assert k is not None
    if not isinstance(props, (tuple, Mapping)):
        raise TypeError(f"an edit's properties are pairs, got {props!r}")
    p = _edit_props(k, dict(props))
    ri = _index_module()
    category = ri.CATEGORY[k]
    for w in ws:
        # the build's check 8: a phrase is matched whole only as a birth
        # marker or a run of titles addressing the given name
        if " " in w and not (k == "birth_marker" or (
                category == "title" and ("addresses", "given") in p)):
            raise ValueError(
                f"{w!r} is a phrase, which can never match as a {k}: only "
                f"a birth_marker and a title with addresses='given' are "
                f"matched as a whole run; add its words one by one")
        # the build refuses may_be_initial on anything but a cased single
        # letter: no other word reads as an initial (rules/P8)
        if ("may_be_initial", True) in p and not (
                len(w) == 1 and w.upper() != w.lower()):
            raise ValueError(
                f"may_be_initial marks a single cased letter that may read "
                f"as an initial; {w!r} is not one")
    return _Edit(op, ws, k, p)


def _apply_edit(pool: dict[str, tuple[Any, ...]], edit: _Edit) -> None:
    """Apply `edit` to `pool` (word -> its readings) in place. An add of
    a kind the word holds updates that reading's properties in every
    file holding it, and turns a reading written `default = false` on;
    otherwise it adds the caller's own reading, which names no file."""
    ri = _index_module()
    for w in edit.words:
        rs = pool.get(w, ())
        if edit.op == "remove":
            kept = tuple(r for r in rs if edit.kind is not None
                         and r.kind != edit.kind and r.category != edit.kind)
        elif any(r.kind == edit.kind for r in rs):
            kept = tuple(
                ri.IndexReading(w, r.tag, r.kind, MappingProxyType(
                    _merged(r.props, edit.props)))
                if r.kind == edit.kind else r for r in rs)
        else:
            kept = rs + (ri.IndexReading(w, "", edit.kind, MappingProxyType(
                {k: v for k, v in edit.props if v is not None})),)
        if kept:
            pool[w] = kept
        else:
            pool.pop(w, None)


def _merged(props: Mapping[str, Any], update: _Props) -> dict[str, Any]:
    out = {k: v for k, v in props.items() if k != "default"}
    for k, v in update:
        if v is None:
            out.pop(k, None)
        else:
            out[k] = v
    return out


Pool = Mapping[str, tuple[Any, ...]]


@functools.lru_cache(maxsize=8)
def _base_pool(base: object) -> Pool:
    """A base's readings by word, on by default or not: the shipped
    index for `"default"`, none for `"empty"`, a snapshot's own rows."""
    if base == "empty":
        return MappingProxyType({})
    ri = _index_module()
    rows = ri._by_text().items() if base == "default" else base
    return MappingProxyType({
        text: tuple(ri.from_row(text, row) for row in rs)
        for text, rs in rows})  # type: ignore[union-attr]


def _check_pool(pool: Pool, words: Iterable[str]) -> None:
    """The build's checks a caller's edits can reach, over the words
    they touch (checks 3 and 8 run per edit, in _make_edit): one suffix
    kind per word (check 4), an agnomen has a name reading (check 11's
    agnomen clause), and a bound given name that is also a particle has
    a given reading (check 9)."""
    for w in dict.fromkeys(words):
        on = [r for r in pool.get(w, ()) if r.on_by_default]
        suffix = {r.kind: r for r in on if r.category == "suffix"}
        if len(suffix) > 1:
            held = sorted(k for k, r in suffix.items() if r.tag)
            drop = held[0] if held else sorted(suffix)[0]
            raise ValueError(
                f"{w!r} would hold two suffix kinds, "
                f"{' and '.join(sorted(suffix))}, and a word holds one; "
                f"remove the one it holds first: .remove({w!r}, "
                f"kind={drop!r})")
        kinds = {r.category for r in on} | {r.kind for r in on}
        # check 11's agnomen clause: an agnomen is written in the case of
        # the name around it, so only the count gates it, and the gate is
        # a name reading beside it (rules/S11)
        if "agnomen" in kinds and "name" not in kinds:
            raise ValueError(
                f"{w!r} is an agnomen with no name reading, and an agnomen "
                f"is read as the suffix only where a name reading gates "
                f"it by the count: write .add({w!r}, kind='family') "
                f"first, then the agnomen")
        if {"bound_given", "particle"} <= kinds and "given" not in kinds:
            raise ValueError(
                f"{w!r} is a bound given name and a particle with no given "
                f"reading, and a particle that never starts a given name "
                f"cannot bind one: .add({w!r}, kind='given'), or "
                f".remove({w!r}, kind='bound_given')")


@functools.lru_cache(maxsize=128)
def _built(base: object, edits: tuple[_Edit, ...]) -> tuple[
        Pool, Mapping[str, frozenset[str]]]:
    """A lexicon's readings by word and the sets they compile to, kept
    per base and log: a compile costs milliseconds, paid once per
    configuration (decisions/vocabulary-model, 2026-11-01 #754)."""
    pool = dict(_base_pool(base))
    for edit in edits:
        _apply_edit(pool, edit)
    _check_pool(pool, (w for e in edits for w in e.words))
    ri = _index_module()
    try:
        compiled = ri.compile_readings(
            r for rs in pool.values() for r in rs)
    except ri.CompileError as exc:
        raise ValueError(str(exc)) from None
    return MappingProxyType(pool), MappingProxyType(_vocab_fields(compiled))


def _compiled_for(base: object,
                  edits: tuple[_Edit, ...]) -> Mapping[str, frozenset[str]]:
    if not edits:
        if base == "default":
            return _default_compiled()
        if base == "empty":
            return _NO_SETS
    return _built(base, edits)[1]


def _check_base(base: object) -> object:
    """`"default"`, `"empty"`, or a snapshot of index rows from a pickle
    (decisions/vocabulary-model, 2026-11-02 #754, items 3 and 5), which
    becomes `"default"` where it is the running release's index."""
    if base in ("default", "empty"):
        return base
    if not isinstance(base, tuple):
        raise TypeError(f"a Lexicon's base is 'default', 'empty' or a "
                        f"snapshot of index rows, got {base!r}")
    ri = _index_module()
    from nameparser.config._index import READINGS
    if base == READINGS:
        return "default"
    shape = ("a Lexicon snapshot is (word, rows) pairs, each row (tag, "
             "kind, properties), the properties (name, value) pairs")
    for entry in base:
        if not (isinstance(entry, tuple) and len(entry) == 2
                and isinstance(entry[0], str)
                and isinstance(entry[1], tuple)):
            raise TypeError(f"{shape}; got {entry!r}")
        word, rows = entry
        for row in rows:
            if not (isinstance(row, tuple) and len(row) == 3):
                raise TypeError(f"{shape}; {word!r} has the row {row!r}")
            tag, kind, pairs = row
            if not isinstance(tag, str) or not isinstance(kind, str):
                raise TypeError(f"{shape}, the tag and the kind strings; "
                                f"{word!r} has the row {row!r}")
            if kind not in ri.CATEGORY:
                raise ValueError(
                    f"a Lexicon snapshot holds the reading kind {kind!r}, "
                    f"which this release does not know")
            if not isinstance(pairs, tuple) or not all(
                    isinstance(p, tuple) and len(p) == 2
                    and isinstance(p[0], str) for p in pairs):
                raise TypeError(f"{shape}; {word!r} has the row {row!r}")
            for name, value in pairs:
                if name not in ri.indexed(kind):
                    raise ValueError(
                        f"a Lexicon snapshot gives {word!r}'s {kind} reading "
                        f"the property {name!r}, which a {kind} reading "
                        f"does not take in this release")
                try:
                    hash(value)
                except TypeError:
                    raise TypeError(
                        f"a Lexicon snapshot gives {word!r}'s {kind} reading "
                        f"{name}={value!r}; a value is a string, a bool or "
                        f"a tuple") from None
    return base


# -- the 2.x set fields, translated --------------------------------------

#: The fields whose membership puts a word in a category. A marker set
#: implies its base here; a 2.x orphan, a marker entry its base does not
#: hold, never reaches this, `_inert_dropped` having taken it out.
_TITLE_FIELDS = frozenset({
    "titles", "titles_ambiguous", "given_name_titles", "after_given_titles",
    "title_modifiers", "title_styles"})
_ACRONYM_FIELDS = frozenset({"suffix_acronyms", "suffix_acronyms_ambiguous"})
_WORD_FIELDS = frozenset({
    "suffix_words", "suffix_words_ambiguous", "agnomens", "honorific_tails",
    "generation_words", "credential_words"})
_PARTICLE_FIELDS = frozenset({
    "particles", "particles_ambiguous", "patronymic_particles"})


def _props_by_kind(readings: Iterable[Any]) -> dict[str, list[dict[str, Any]]]:
    out: dict[str, list[dict[str, Any]]] = {}
    for r in readings:
        out.setdefault(r.kind, []).append(dict(_clean(r.props)))
    return out


def _by_kind(readings: Iterable[Any]) -> dict[str, dict[str, Any]]:
    out: dict[str, dict[str, Any]] = {}
    for r in readings:
        out.setdefault(r.kind, dict(_clean(r.props)))
    return out


def _target_readings(word: str, member: frozenset[str],
                     heads: frozenset[str] | None,
                     on: dict[str, dict[str, Any]],
                     hints: dict[str, dict[str, Any]],
                     kinds_known: bool) -> dict[str, dict[str, Any]]:
    """The readings, kind -> properties, that compile `word` into the
    sets `member` names, keeping each reading `word` holds (`on`) where
    it fits and taking a kind it lacks from `hints`, then from the
    category's own kind. `heads` are the title words a phrase starting
    with `word` must reach, None where they do not change. A best
    effort: the caller compiles the result and compares."""
    ri = _index_module()

    def kinds(category: str) -> list[str]:
        return ([k for k in on if ri.CATEGORY[k] == category]
                or [k for k in hints if ri.CATEGORY[k] == category])

    def props(kind: str) -> dict[str, Any]:
        return dict(on[kind] if kind in on else hints.get(kind, {}))

    out: dict[str, dict[str, Any]] = {}
    if member & _TITLE_FIELDS or heads:
        ks = kinds("title") or ["title"]
        if "title_modifiers" in member:
            ks = ["modifier"]
        else:
            ks = [k for k in ks if k != "modifier"] or ["title"]
            if "title_styles" in member and "style" not in ks:
                ks = [k for k in ks if k != "title"] + ["style"]
            elif "title_styles" not in member:
                ks = [k for k in ks if k != "style"] or ["title"]
        for k in ks:
            p = props(k)
            p.pop("addresses", None)
            p.pop("after_given", None)
            if "given_name_titles" in member:
                p["addresses"] = "given"
            if "after_given_titles" in member:
                p["after_given"] = True
            if heads is not None or k not in on:
                p.pop("attaches", None)
                if heads:
                    p["attaches"] = tuple(sorted(heads))
            out[k] = p
    particled = bool(member & _PARTICLE_FIELDS)
    if particled:
        ks = kinds("particle") or ["particle"]
        if kinds_known:
            if "patronymic_particles" in member:
                ks = ["patronymic"]
            else:
                ks = [k for k in ks if k != "patronymic"] or ["particle"]
        for k in ks:
            out[k] = props(k)
    if member & {"conjunctions", "conjunctions_ambiguous"}:
        p = props("conjunction")
        p.pop("may_be_initial", None)
        if "conjunctions_ambiguous" in member:
            p["may_be_initial"] = True
        out["conjunction"] = p
    if "bound_given_names" in member:
        out["bound_given"] = props("bound_given")
    if "maiden_markers" in member:
        out["birth_marker"] = props("birth_marker")
    acronym, worded = member & _ACRONYM_FIELDS, member & _WORD_FIELDS
    held: str | None = next(iter(kinds("suffix")), None)
    titled = "titles" in member
    given_needed = (("titles_ambiguous" in member and not titled)
                    or "particles_ambiguous" in member
                    or "given_name_abbreviations" in member)
    suffix: str | None = None
    if acronym and not worded:
        suffix = held or "credential"
    elif worded:
        if "agnomens" in member:
            suffix = "agnomen"
        elif kinds_known and "generation_words" in member:
            suffix = "generation"
        elif kinds_known and "credential_words" in member:
            suffix = "credential"
        elif "suffix_words_ambiguous" in member:
            # an agnomen is its own kind, so a word that stops being one
            # is the generation the gated class otherwise holds
            suffix = (held if held in ri.GATED_WORDS and held != "agnomen"
                      else "generation")
        else:
            suffix = held or "suffix"
            if suffix == "agnomen" or (kinds_known and suffix in (
                    "generation", "credential")) or (
                    suffix in ri.GATED_WORDS and given_needed):
                suffix = "suffix"
    # the name readings, which gate the vocabulary readings beside them:
    # a word's own kept where they gate nothing they must not
    names = {k: dict(p) for k, p in on.items() if ri.CATEGORY[k] == "name"}
    given_ok = (not (titled and not particled)
                and not (particled and "particles_ambiguous" not in member))
    named_ok = not ((acronym and "suffix_acronyms_ambiguous" not in member)
                    or (worded and suffix in ri.GATED_WORDS
                        and "suffix_words_ambiguous" not in member))
    if not given_ok or not named_ok:
        names.pop("given", None)
    if not named_ok:
        names.pop("family", None)
    if given_needed and "given" not in names:
        names["given"] = props("given")
    if "given" in names:
        if "given_name_abbreviations" in member:
            names["given"].setdefault("same_as", word)
        else:
            names["given"].pop("same_as", None)
    if (member & {"suffix_acronyms_ambiguous", "suffix_words_ambiguous"}
            and not names):
        names["family"] = {}
    if suffix is not None:
        p = props(suffix)
        p.pop("acronym", None)
        p.pop("attached", None)
        if acronym and not worded:
            if suffix != "credential":
                p["acronym"] = True
        else:
            if suffix == "credential":
                p["acronym"] = False
            if "honorific_tails" in member:
                p["attached"] = "after"
        out[suffix] = p
    out.update(names)
    return out


#: (marker, the sets one of which holds a word its marker qualifies): no
#: reading compiles a marker without its base, a property needing its
#: reading, so `_inert_dropped` takes a 2.x entry outside them out of
#: both sides of every compare, and a 2.x spelling or pickle that left
#: one behind -- `remove(titles={"air"})` keeping `air` a modifier --
#: reads as though the marker went with its word. 2.x did read such an
#: orphan in two places, which move, an accepted difference
#: (decisions/vocabulary-model, 2026-11-02 #754, a marker left behind):
#: an orphan given-name title still made rules/H2's period-shape title
#: address the given name (`Sir. Smith` read given `Smith`), and any
#: orphan counted as a listed word in the capitals shape (`John Smith,
#: AIR` read given `AIR`).
_MARKER_READ_WITH = (
    ("given_name_titles", ("titles", "titles_ambiguous")),
    ("after_given_titles", ("titles",)),
    ("title_modifiers", ("titles", "titles_ambiguous")),
    ("title_styles", ("titles", "titles_ambiguous")),
    ("conjunctions_ambiguous", ("conjunctions",)),
    ("particles_ambiguous", ("particles",)),
    ("patronymic_particles", ("particles",)),
    ("suffix_acronyms_ambiguous", ("suffix_acronyms",)),
    ("suffix_words_ambiguous", ("suffix_words",)),
    ("honorific_tails", ("suffix_words",)),
    ("generation_words", ("suffix_words",)),
    ("credential_words", ("suffix_words",)),
    ("agnomens", ("suffix_words_ambiguous",)),
)


def _inert_dropped(sets: Mapping[str, frozenset[str]],
                   ) -> dict[str, frozenset[str]]:
    """`sets` without the entries no reading compiles: a marker's word
    its base sets do not hold, and a title phrase or a given-name title
    run holding a word that is no title. In the order of
    `_MARKER_READ_WITH`, so an agnomen whose ambiguous suffix word went
    goes too."""
    out = dict(sets)
    for marker, bases in _MARKER_READ_WITH:
        if marker in out:
            read = frozenset().union(*(out[b] for b in bases))
            out[marker] = frozenset(
                w for w in out[marker]
                if w in read or (marker == "given_name_titles" and " " in w
                                 and all(x in read for x in w.split())))
    titles = out["titles"] | out["titles_ambiguous"]
    out["title_phrases"] = frozenset(
        p for p in out["title_phrases"]
        if " " in p and all(w in titles for w in p.split(" ")))
    return out


def _edits_toward(pool: Pool, current: Mapping[str, frozenset[str]],
                  target: Mapping[str, frozenset[str]],
                  hints: Pool | None = None) -> tuple[_Edit, ...]:
    """The edits that take the readings of `pool`, which compile to the
    sets `current`, toward the sets `target` (by `_LexiconSets` name;
    a set it leaves out stays as `current` has it), word by word: for
    each word whose memberships differ, a `remove` of each kind it no
    longer holds, then an `add` of each kind it lacks or whose
    properties change. The one translation from sets to readings, which
    the refusals of a 2.x spelling, the load of a 2.x pickle and
    `_parser._apply_choice` share; a best effort, so each caller
    compiles the result where it must be exact. `hints` are readings a
    word's new kinds are taken from before its held ones (a choice's)."""
    ri = _index_module()
    kinds_known = all(k in target for k in _KIND_FIELDS)
    fields = _SET_FIELDS + (_KIND_FIELDS if kinds_known else ())
    full = _inert_dropped({f: target.get(f, current[f]) for f in fields})
    current = _inert_dropped({f: current[f] for f in fields})
    changed: set[str] = set()
    for f in fields:
        if f == "title_phrases":
            changed |= {p.split(" ", 1)[0]
                        for p in full[f] ^ current[f]}
        else:
            changed |= full[f] ^ current[f]

    def heads(phrases: frozenset[str], word: str) -> frozenset[str]:
        # a 2.x entry of one word is no phrase, and no head
        return frozenset(p.partition(" ")[2] for p in phrases
                         if p.partition(" ")[0] == word and " " in p)

    out: list[_Edit] = []
    for w in sorted(changed):
        held = pool.get(w, ())
        on = _by_kind(r for r in held if r.on_by_default)
        everything = _by_kind(held)
        # a new kind is taken from the hints first, then from the
        # readings the word holds turned off
        hinted = _by_kind((hints or {}).get(w, ()))
        for k, p in everything.items():
            hinted.setdefault(k, p)
        member = frozenset(f for f in fields
                           if f != "title_phrases" and w in full[f])
        new_heads = heads(full["title_phrases"], w)
        moved = new_heads != heads(current["title_phrases"], w)
        want = _target_readings(w, member, new_heads if moved else None,
                                on, hinted, kinds_known)
        dropped = [k for k in on if k not in want]
        gone_categories = {k for k in dropped if ri.CATEGORY[k] == k}
        for k in dropped:
            out.append(_Edit("remove", (w,), k, ()))
        # every reading of a kind the add reaches, files disagreeing (a
        # given name written short in one file, `ma`, and plain in
        # another), so the delta takes each of them to `p`
        after = {k: ps for k, ps in _props_by_kind(held).items()
                 if k not in dropped and ri.CATEGORY[k] not in gone_categories}
        for k, p in want.items():
            if k in after:
                if k in on and all(q == p for q in after[k]):
                    continue
                delta = {x: v for x, v in p.items()
                         if any(q.get(x) != v for q in after[k])}
                delta |= {x: None for q in after[k] for x in q if x not in p}
            else:
                delta = p
            out.append(_make_edit("add", (w,), k, delta))
    return tuple(out)


def _fields_of(sets: _LexiconSets | Mapping[str, frozenset[str]],
               ) -> dict[str, frozenset[str]]:
    get = (sets.__getitem__ if isinstance(sets, Mapping)
           else functools.partial(getattr, sets))
    return {f: get(f) for f in _SET_FIELDS + _KIND_FIELDS}


def _rendered(edits: Iterable[_Edit]) -> list[str]:
    """Edits as the calls that make them, consecutive ones of one kind
    and properties joined into one call."""
    calls: list[tuple[str, list[str], str | None, _Props]] = []
    for e in edits:
        if calls and calls[-1][0] == e.op and calls[-1][2:] == (e.kind,
                                                               e.props):
            calls[-1][1].extend(e.words)
        else:
            calls.append((e.op, list(e.words), e.kind, e.props))
    out = []
    for op, words, kind, props in calls:
        args = [repr(w) for w in words]
        if kind is not None:
            args.append(f"kind={kind!r}")
        args += [f"{k}={_shown_value(kind, k, v)}" for k, v in props]
        out.append(f".{op}({', '.join(args)})")
    return out


def _shown_value(kind: str | None, prop: str, value: object) -> str:
    """A logged property value as a caller writes it: a removed one as
    its unwritten value where it has one (`may_be_initial=False`)."""
    if value is None and kind is not None and prop in (
            "acronym", "addresses", "after_given", "may_be_initial"):
        value = _unwritten(kind, prop)
    if isinstance(value, tuple) and len(value) > _SHOWN_WORDS:
        # bounded: a phrase taken out of a kind's reach lists every
        # other title word the kind reached (`chief justice`)
        return (repr(list(value[:_SHOWN_WORDS]))[:-1]
                + f", ... {len(value) - _SHOWN_WORDS} more]")
    return repr(list(value) if isinstance(value, tuple) else value)


#: The most words a refusal shows of one property's list.
_SHOWN_WORDS = 6


#: The most calls a refusal spells out before it counts the rest.
_SHOWN_CALLS = 8


def _translation(lexicon: Lexicon, changes: Mapping[str, frozenset[str]],
                 prefix: str = "lexicon") -> str:
    """What a 2.x set spelling asks of `lexicon`, as 3.0 calls: the
    sets it would leave, translated word by word (_edits_toward, the
    translation the 2.x pickle load uses)."""
    target = {f: v for f, v in changes.items() if f in _SET_FIELDS}
    current = _fields_of(lexicon._sets)
    # every set compared, so a reading that also moves a set the call did
    # not name (a given reading gating a credential) is no exact match;
    # a word in both titles and titles_ambiguous compared as in titles
    # alone, as a 2.x pickle is (the two spellings parse alike)
    wanted = {f: target.get(f, current[f]) for f in _SET_FIELDS}
    wanted["titles_ambiguous"] = wanted["titles_ambiguous"] - wanted["titles"]
    wanted = _inert_dropped(wanted)
    try:
        edits = _edits_toward(lexicon._pool(), current, target)
        result = _inert_dropped(
            _built(lexicon._base, lexicon._edits + edits)[1])
        exact = all(result[f] == wanted[f] for f in _SET_FIELDS)
    except (TypeError, ValueError):
        edits, exact = (), False
    if not edits and exact:
        return ("the lexicon already reads those words so, an entry it "
                "would add or remove being a marker without its word's "
                "reading, which goes with that reading in 3.0; no call is "
                "needed")
    if not edits:
        return ("no readings give those words exactly those sets (a word "
                "holds one suffix kind, an acronym or a word, and a "
                "property is read only beside its reading); "
                "docs/migrate.rst's Lexicon table has every field")
    calls = _rendered(edits)
    shown = "".join(calls[:_SHOWN_CALLS]) + (
        f" ... ({len(calls) - _SHOWN_CALLS} calls more)"
        if len(calls) > _SHOWN_CALLS else "")
    if not exact:
        return ("no readings compile to exactly that set; the nearest is "
                f"{prefix}{shown}, and docs/migrate.rst's Lexicon table "
                "has every field")
    return f"write {prefix}{shown}"


def _refusal(where: str, lexicon: Lexicon,
             removed: Mapping[str, object]) -> TypeError:
    """The TypeError for a 2.x spelling, translated for the words it
    names (decisions/vocabulary-model, 2026-11-02 #754, item 6)."""
    unknown = [k for k in removed
               if k not in _SET_FIELDS + _LIST_FIELDS
               and k != "capitalization_exceptions"]
    if unknown:
        return TypeError(f"{where} got an unexpected keyword argument "
                         f"{unknown[0]!r}")
    if "capitalization_exceptions" in removed:
        return TypeError(
            "capitalization_exceptions holds key->value pairs; use "
            "dataclasses.replace(lexicon, capitalization_exceptions=(*lexicon."
            "capitalization_exceptions, ('key', 'KEY'))) instead of "
            f"{where}")
    lists = [k for k in removed if k in _LIST_FIELDS]
    if lists:
        name = lists[0]
        given = removed[name]
        words = (sorted(given) if isinstance(given, Iterable)
                 and not isinstance(given, (str, bytes, Mapping))
                 and all(isinstance(w, str) for w in given) and given
                 else ["word"])
        shown = "{" + ", ".join(map(repr, words)) + "}"
        code = (f"dataclasses.replace(lexicon, {name}=lexicon.{name} - "
                f"{shown})" if where.startswith("remove")
                else f"lexicon | Lexicon({name}={shown})")
        return TypeError(
            f"{name} is a list, changed with a fragment since 3.0, not "
            f"{where}: write {code}")
    return TypeError(
        f"{where} takes no {', '.join(removed)} since 3.0: a Lexicon is "
        f"configured by reading, add(*words, kind=..., **properties) and "
        f"remove(*words, kind=...); for these words, "
        + _translation(lexicon, {
            f: cast("frozenset[str]", v) for f, v in removed.items()},
            # a bare constructor call names the base it starts from
            "Lexicon.empty()" if where.startswith("Lexicon()")
            and lexicon == Lexicon.empty() else "lexicon"))


def _translated_2x(state: Mapping[str, object]) -> dict[str, object]:
    """A 2.x `Lexicon` pickle's state as 3.0 constructor arguments: the
    sets translated onto the nearer of the two named bases, as the
    repr counts it (the fewest entries differing), and a log replacing
    each word whose memberships differ from that base's compile
    (decisions/vocabulary-model, 2026-11-02 #754, item 5). Raises
    ValueError where no readings compile the pickled sets back, naming
    the fields; a word in both `titles` and `titles_ambiguous` is
    compared as in `titles` alone, the two spellings parsing alike."""
    expected = set(_VOCAB_FIELDS) | {"capitalization_exceptions"}
    missing_set = expected - set(state) - {"given_names"}
    if missing_set or not set(state) <= expected:
        missing = ", ".join(sorted(missing_set)) or "none"
        unexpected = ", ".join(sorted(set(state) - expected)) or "none"
        raise ValueError(
            f"incompatible Lexicon pickle: missing fields: {missing}; "
            f"unexpected fields: {unexpected}")
    sets: dict[str, frozenset[str]] = {}
    drifted = []
    for name in _VOCAB_FIELDS:
        given = state.get(name, frozenset())
        try:
            folded = _normset(cast("Iterable[str]", given), name, warn=False)
        except (TypeError, ValueError) as exc:
            raise ValueError(f"incompatible Lexicon pickle: {exc}") from None
        lost = frozenset(cast("Iterable[str]", given)) - folded
        if lost:
            drifted.append(f"{name}: {', '.join(sorted(lost))}")
        sets[name] = folded
    if drifted:
        raise ValueError(
            "incompatible Lexicon pickle: entries are not normalized "
            f"({'; '.join(drifted)}); this state was not written by "
            "this version of nameparser")
    sets["titles_ambiguous"] -= sets["titles"]
    # an entry 2.x never read (an orphan marker) is no part of what the
    # pickle parsed as, and no reading compiles one
    wanted = _inert_dropped({f: sets[f] for f in _SET_FIELDS})

    def distance(compiled: Mapping[str, frozenset[str]]) -> int:
        compiled = _inert_dropped(compiled)
        return sum(len(wanted[f] ^ compiled[f]) for f in _SET_FIELDS)

    base = min(("default", "empty"),
               key=lambda b: distance(_compiled_for(b, ())))
    try:
        edits = _edits_toward(_base_pool(base), _compiled_for(base, ()),
                              wanted)
        got = _inert_dropped(_compiled_for(base, edits))
    except ValueError as exc:
        raise ValueError(f"a 2.x Lexicon pickle that 3.0 readings cannot "
                         f"express: {exc}") from None
    differ = [f for f in _SET_FIELDS if got[f] != wanted[f]]
    if differ:
        raise ValueError(
            f"a 2.x Lexicon pickle that 3.0 readings cannot express: no "
            f"readings compile its {', '.join(differ)} back; rebuild the "
            f"lexicon in 3.0 (docs/migrate.rst's Lexicon table)")
    return {"surnames": sets["surnames"],
            "given_names": sets["given_names"],
            "capitalization_exceptions": state["capitalization_exceptions"],
            "_base": base, "_edits": edits}


# -- the public types ----------------------------------------------------

@dataclass(frozen=True, slots=True)
class LexiconReading:
    """One reading a :class:`Lexicon` holds for a word, as
    :meth:`Lexicon.readings_of` returns it: what the word may be read
    as, in the vocabulary files' terms (decisions/vocabulary-model,
    2026-11-02 #754, item 2).

    ``kind`` is a vocabulary kind as the language files write it
    (``"office"``, ``"credential"``, ``"preposition"``, ``"given"``),
    finer than :class:`ReadingKind`, which is the parse's; ``category``
    its category (``"title"``, ``"suffix"``, ``"particle"``,
    ``"conjunction"``, ``"bound_given"``, ``"relation"``, ``"name"``);
    ``properties`` its behavioral properties as sorted ``(name, value)``
    pairs, spelled as the files spell them (``("addresses", "given")``),
    a list value a sorted tuple; ``languages`` the BCP 47 tags of the
    shipped files holding it, sorted, empty for a reading a caller
    added. Whether the parse READ a word this way is the parse's
    question, :attr:`Token.reading`: a title reading beside a ``given``
    one is a title only inside a title phrase (rules/H9)."""

    text: str
    kind: str
    category: str
    properties: tuple[tuple[str, Any], ...] = ()
    languages: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        ri = _index_module()
        for name in ("text", "kind", "category"):
            if not isinstance(getattr(self, name), str):
                raise TypeError(f"LexiconReading.{name} must be a string, "
                                f"got {getattr(self, name)!r}")
        if self.kind not in ri.CATEGORY:
            raise ValueError(f"unknown reading kind {self.kind!r}; the "
                             f"kinds are {', '.join(ri.CATEGORY)}")
        if self.category != ri.CATEGORY[self.kind]:
            raise ValueError(
                f"a {self.kind} reading's category is "
                f"{ri.CATEGORY[self.kind]!r}, got {self.category!r}")
        for name in ("properties", "languages"):
            if not isinstance(getattr(self, name), tuple):
                raise TypeError(f"LexiconReading.{name} must be a tuple, "
                                f"got {getattr(self, name)!r}")

    def __getstate__(self) -> dict[str, object]:
        return {f.name: getattr(self, f.name)
                for f in dataclasses.fields(self)}

    def __setstate__(self, state: dict[str, object]) -> None:
        # the layout check the other frozen types share
        # (_types._guarded_setstate), held here by layering
        expected = {f.name for f in dataclasses.fields(LexiconReading)}
        if set(state) != expected:
            missing = ", ".join(sorted(expected - set(state))) or "none"
            unexpected = ", ".join(sorted(set(state) - expected)) or "none"
            raise ValueError(
                f"incompatible LexiconReading pickle: missing fields: "
                f"{missing}; unexpected fields: {unexpected}")
        for name, value in state.items():
            object.__setattr__(self, name, value)


@dataclass(frozen=True, slots=True, init=False, repr=False)
class Lexicon:
    """The vocabulary a parser matches against: which words may be read
    as titles, particles, suffixes, and so on. Immutable and hashable.
    Start from :meth:`default` (the shipped vocabulary) or
    :meth:`empty`, configure it by READING -- :meth:`add` and
    :meth:`remove` take words and a vocabulary kind as the language
    files write it, ``add("leed", "ap", kind="credential")`` -- join
    fragments with ``|``, and pass the result to ``Parser(lexicon=...)``.
    Ask what a word may be read as with :meth:`readings_of`.

    Words are normalized as they are stored -- lowercased, NFC-composed,
    edge full stops stripped -- so matching is case-insensitive.

    Since 3.0 the sets a parse reads are compiled from the readings and
    are internal; the 2.x set fields (``titles``, ``suffix_acronyms``,
    ...) are refused wherever they were written, each refusal naming
    the calls that configure the same words (docs/migrate.rst has the
    table). Three fields stay, being outside the per-word model:
    ``surnames``, ``given_names`` and ``capitalization_exceptions``.

    State is a base (the shipped vocabulary, none, or a pickled
    release's), the ordered log of :meth:`add` and :meth:`remove` calls
    applied after it, and the three fields; two lexicons are equal when
    all of them are, the log compared call by call as written, so two
    logs that read alike can still differ (decisions/vocabulary-model,
    2026-11-02 #754, item 3)."""

    #: Family names for the unspaced-name segmentation stage (#271),
    #: matched longest-first against the start of the FIRST token
    #: written wholly in a script :attr:`Policy.segment_scripts
    #: <nameparser.Policy.segment_scripts>` activates. The default
    #: carries the Korean census list
    #: (:data:`~nameparser.config.surnames.KOREAN_SURNAMES`); Chinese
    #: surnames ship in locales.ZH because Han segmentation is opt-in.
    #: A list, outside the per-word model: add to it with a fragment,
    #: ``lexicon | Lexicon(surnames={...})``.
    surnames: frozenset[str] = frozenset()
    #: Given names read by two-family-name handling alone
    #: (:attr:`Policy.two_family_names
    #: <nameparser.Policy.two_family_names>`, rules/O6): the word that
    #: rule would take into the family stays where it is when listed, so
    #: "José Luis Pérez" keeps family "Pérez". A word matches as
    #: written or with its acute and grave accents and diaeresis
    #: dropped (the tilde on n and the cedilla on c kept), so an entry
    #: written "jose" matches "José" too. No other rule reads it. Empty
    #: by default, so the switch reads as without it; a caller passes
    #: a list of its own, and ``locales.ES`` carries a Spanish list, with
    #: the switch on.
    given_names: frozenset[str] = frozenset()
    #: Lowercase word -> case mask used by capitalized(): the word's
    #: own letters and digits, each in the case it takes ("phd" ->
    #: "PhD"), laid over the word as written, so the one entry
    #: repairs "ph.d." to "Ph.D.". The mask's own punctuation marks
    #: where its letters are joined into one run versus split apart,
    #: and is never written into the word -- repair keeps the writer's
    #: own punctuation. A value that does not spell the key's letters
    #: and digits raises ValueError. Pair-valued: change it with
    #: dataclasses.replace(); read it as a mapping via
    #: capitalization_exceptions_map. Full default mapping:
    #: :data:`~nameparser.config.capitalization.CAPITALIZATION_EXCEPTIONS`.
    # Canonical storage: sorted tuple of (key, value) pairs. The
    # constructor tolerates any Mapping (or pair iterable) at runtime and
    # canonicalizes here; this closes the caller-aliasing hole and keeps
    # Lexicon hashable. Read via capitalization_exceptions_map.
    capitalization_exceptions: tuple[tuple[str, str], ...] = ()
    # The base and the log: constructor parameters under underscore
    # names, so that dataclasses.replace and copy.replace carry them,
    # and no public API (decisions/vocabulary-model, 2026-11-02 #754,
    # item 3). 4i-c adds the choice beside them.
    _base: Any = "empty"
    _edits: tuple[_Edit, ...] = ()
    _cap_map: Mapping[str, str] = field(
        init=False, repr=False, compare=False, hash=False)
    _sets: _LexiconSets = field(
        init=False, repr=False, compare=False, hash=False)

    def __init__(
        self, *,
        surnames: Iterable[str] = frozenset(),
        given_names: Iterable[str] = frozenset(),
        capitalization_exceptions: (Mapping[str, str]
                                    | Iterable[tuple[str, str]]) = (),
        _base: object = "empty",
        _edits: Iterable[_Edit] = (),
        **removed: object,
    ) -> None:
        put = functools.partial(object.__setattr__, self)
        put("surnames", _normset(surnames, "surnames"))
        put("given_names", _normset(given_names, "given_names"))
        canonical = _normpairs(capitalization_exceptions)
        put("capitalization_exceptions", canonical)
        put("_cap_map", MappingProxyType(dict(canonical)))
        put("_base", _check_base(_base))
        if isinstance(_edits, (str, bytes)) or not isinstance(
                _edits, Iterable):
            raise TypeError(f"_edits must be a tuple of edits, got "
                            f"{_edits!r}")
        edits = tuple(_edits)
        for e in edits:
            if not isinstance(e, tuple) or len(e) != 4:
                raise TypeError(f"an edit is (op, words, kind, props), "
                                f"got {e!r}")
        canon = tuple(_make_edit(*e) for e in edits)
        if canon != edits:
            raise ValueError(
                "_edits holds an edit not in canonical form; build a "
                "Lexicon's log with add() and remove()")
        put("_edits", canon)
        compiled = _compiled_for(self._base, canon)
        put("_sets", _LexiconSets(
            **compiled, surnames=self.surnames, given_names=self.given_names))
        if removed:
            raise _refusal("Lexicon() (and dataclasses.replace)", self,
                           self._changed("set", removed))

    # -- constructors ----------------------------------------------------

    @classmethod
    def empty(cls) -> Lexicon:
        return cls()

    @classmethod
    def default(cls) -> Lexicon:
        return _default_lexicon()

    # -- dunders ----------------------------------------------------------

    # hidden from a type checker, which would otherwise read any
    # attribute as defined and stop flagging `lexicon.titles` itself
    if not TYPE_CHECKING:
        def __getattr__(self, name: str) -> object:
            if name in _SET_FIELDS:
                raise AttributeError(
                    f"Lexicon.{name} is internal since 3.0, compiled from "
                    f"the lexicon's readings: ask lexicon.readings_of(word) "
                    f"what a word may be read as, and a parse's "
                    f"Token.reading what it was read as")
            raise AttributeError(
                f"{type(self).__name__!r} object has no attribute {name!r}")

    def __repr__(self) -> str:
        # Bounded: counts readings by kind against the nearer of the two
        # named lexicons, never naming a word (the design rule in
        # nameparser._types' module docstring)
        if self == Lexicon.default():
            return "Lexicon(default)"
        if self == Lexicon.empty():
            return "Lexicon(empty)"
        candidates = [(label, self._deltas_from(other))
                      for label, other in (("default", Lexicon.default()),
                                           ("empty", Lexicon.empty()))]
        label, (kinds, lists) = min(
            candidates,
            key=lambda c: sum(a + r for _, a, r in c[1][0] + c[1][1]))

        def counts(deltas: list[tuple[str, int, int]]) -> str:
            return ", ".join(
                name + ": " + "".join(
                    part for part, n in ((f"+{a}", a), (f"-{r}", r)) if n)
                for name, a, r in deltas)

        rendered = "; ".join(filter(None, (counts(kinds), counts(lists))))
        return (f"Lexicon({label} + {rendered or f'edits: {len(self._edits)}'})")

    def __getstate__(self) -> dict[str, object]:
        # the base as a snapshot of its rows, so a pickle parses as it
        # did where it was written (decisions/vocabulary-model,
        # 2026-11-02 #754, item 5)
        base = self._base
        if base == "default":
            from nameparser.config._index import READINGS
            base = READINGS
        return {"surnames": self.surnames, "given_names": self.given_names,
                "capitalization_exceptions": self.capitalization_exceptions,
                "_base": base, "_edits": tuple(tuple(e) for e in self._edits)}

    def __setstate__(self, state: dict[str, object]) -> None:
        # A 2.x state holds the compiled sets, translated onto a base
        # and a log; a 3.0 one is checked for its layout as
        # _types._guarded_setstate checks the other frozen types', the
        # one skew admitted a field marked `_ADDED_IN` with a default
        # (none yet), and then built through the constructor, which
        # validates every value as for a caller's.
        if "titles" in state:
            state = _translated_2x(state)
        fields = [f for f in dataclasses.fields(Lexicon) if f.init]
        expected = {f.name for f in fields}
        added = {f.name: f.default for f in fields
                 if _ADDED_IN in f.metadata
                 and f.default is not dataclasses.MISSING}
        missing_set = expected - set(state) - set(added)
        if missing_set or not set(state) <= expected:
            missing = ", ".join(sorted(missing_set)) or "none"
            unexpected = ", ".join(sorted(set(state) - expected)) or "none"
            raise ValueError(
                f"incompatible Lexicon pickle: missing fields: {missing}; "
                f"unexpected fields: {unexpected}")
        defaulted = {name for name in added if name not in state}
        state = {**{name: added[name] for name in defaulted}, **state}
        Lexicon.__init__(self, **state)  # type: ignore[misc, arg-type]
        # The constructor normalizes, and quietly accepting a rewritten
        # value would make this a place where caller data changes
        # without a word. A pickle this library wrote is always
        # normalized already (_normalize converges), so a difference
        # here means the state came from somewhere else -- say so while
        # the offending entries can still be named.
        drifted = []
        for name in _LIST_FIELDS:
            lost = frozenset(
                cast("Iterable[str]", state[name])) - getattr(self, name)
            if lost:
                drifted.append(f"{name}: {', '.join(sorted(lost))}")
        given_pairs = state["capitalization_exceptions"]
        if (isinstance(given_pairs, tuple)
                and given_pairs != self.capitalization_exceptions):
            drifted.append("capitalization_exceptions")
        faulty = [d for d in drifted if d.split(":")[0] in defaulted]
        if faulty:
            raise ValueError(
                "Lexicon field default is not normalized "
                f"({'; '.join(faulty)}): a field marked _ADDED_IN loads "
                "its default into every pickle written before it, so "
                "the default must be normalized entries; this is a "
                "defect in nameparser, not in the pickle")
        if drifted:
            raise ValueError(
                "incompatible Lexicon pickle: entries are not normalized "
                f"({'; '.join(drifted)}); this state was not written by "
                "this version of nameparser")

    def __or__(self, other: Lexicon) -> Lexicon:
        """The union of two lexicons: the lists unioned, the masks taken
        right-biased, and the logs concatenated, this one's first, so a
        later lexicon's edits apply after an earlier one's (decisions/
        vocabulary-model, 2026-11-02 #754, item 3); the base is the one
        that is not empty, and two different ones raise."""
        if not isinstance(other, Lexicon):
            return NotImplemented
        if "empty" in (self._base, other._base) or self._base == other._base:
            base = other._base if self._base == "empty" else self._base
        else:
            raise ValueError(
                "cannot join two lexicons built on different bases (the "
                "shipped vocabulary of two releases); rebuild one from "
                "Lexicon.default() or Lexicon.empty()")
        merged = dict(self._cap_map) | dict(other._cap_map)
        return Lexicon(
            surnames=self.surnames | other.surnames,
            given_names=self.given_names | other.given_names,
            capitalization_exceptions=tuple(sorted(merged.items())),
            _base=base, _edits=self._edits + other._edits)

    # -- properties -------------------------------------------------------

    @property
    def capitalization_exceptions_map(self) -> Mapping[str, str]:
        return self._cap_map

    # -- access -----------------------------------------------------------

    def readings_of(self, word: str) -> tuple[LexiconReading, ...]:
        """The readings this lexicon holds for `word`: one per kind and
        properties, each with the shipped files that hold it, a reading
        a caller added naming none; empty for a word it holds no reading
        of. `word` is normalized as the lexicon stores it, a phrase
        (``"z domu"``) whole. "Is X a title here?" is ``any(r.category
        == "title" for r in lexicon.readings_of(x))``; whether a parse
        read it as one is :attr:`Token.reading`'s."""
        _reject_buffer(word, "readings_of()", "characters")
        if not isinstance(word, str):
            raise TypeError(f"readings_of() takes a word, a string, got "
                            f"{word!r}")
        text = _title_key(word.split())
        ri = _index_module()
        grouped: dict[tuple[str, _Props], list[str]] = {}
        for r in self._pool().get(text, ()):
            if r.on_by_default:
                grouped.setdefault((r.kind, _clean(r.props)), []).append(
                    r.tag)
        order = list(ri.CATEGORY)
        return tuple(
            LexiconReading(text, kind, ri.CATEGORY[kind], props,
                           tuple(sorted(t for t in set(tags) if t)))
            for (kind, props), tags in sorted(
                grouped.items(),
                key=lambda item: (order.index(item[0][0]), repr(item[0][1]))))

    # -- editing ----------------------------------------------------------

    # `kind` is required, and a type checker reads it so: the runtime
    # default exists only to catch a 2.x call, which names no kind, and
    # refuse it with its translation rather than with Python's own
    # missing-argument error
    if TYPE_CHECKING:
        def add(self, *words: str, kind: str,
                **properties: object) -> Lexicon: ...
    else:
        def add(self, *words: str, kind: str | None = None,
                **properties: object) -> Lexicon:
            """This lexicon with a reading of `kind` added to each word.
            `kind` is required; the signature's default exists only so
            that a 2.x call, which names no kind, is refused with its
            translation. It is a vocabulary kind as the language files
            write it, a key
            of ``nameparser._reading_index.CATEGORY`` (``"title"``,
            ``"office"``, ``"credential"``, ``"generation"``,
            ``"preposition"``, ``"conjunction"``, ``"bound_given"``,
            ``"birth_marker"``, ``"given"``, ``"family"``, ...), and
            `properties` that kind's behavioral properties as the files
            spell them (``addresses="given"``, ``after_given=True``,
            ``attaches=[...]``, ``acronym=...``, ``attached="after"``,
            ``may_be_initial=True``, ``same_as=...`` on a ``given``
            reading); a property given its unwritten value (``None``,
            ``False``) is removed. Where the word holds a reading of `kind`
            already, the add updates its properties in every file holding
            it; otherwise it adds the caller's own reading, which names no
            file. Warns where it makes a title reading that a ``given``
            reading keeps a title only inside a title phrase (rules/H9),
            naming the ``remove`` that makes it a title everywhere."""
            old = {k: properties.pop(k) for k in list(properties)
                   if k in _SET_FIELDS + _LIST_FIELDS
                   or k == "capitalization_exceptions"}
            if old:
                raise _refusal("add()", self, self._changed("add", old))
            if kind is None:
                raise TypeError("add() missing required keyword argument "
                                "'kind', e.g. add('leed', kind='credential')")
            edit = _make_edit("add", words, kind, properties)
            added = dataclasses.replace(self, _edits=self._edits + (edit,))
            ri = _index_module()
            if ri.CATEGORY[edit.kind] == "title":  # type: ignore[index]
                before = self._pool()
                for w in edit.words:
                    if (w in added._sets.titles_ambiguous
                            and not _updates(before.get(w, ()), edit)):
                        _warn_at_caller(
                            f"{w!r} holds a given reading, so it reads as a "
                            f"title only inside a title phrase (rules/H9) and "
                            f"this add reads no name differently elsewhere; to "
                            f"read it as a title everywhere, write "
                            f".remove({w!r}, kind='given')")
            return added

    def remove(self, *words: str, kind: str | None = None,
               **removed: object) -> Lexicon:
        """This lexicon without each word's readings of `kind`: a kind,
        or a category, matching every kind of it (``kind="title"`` takes
        out ``dean``'s ``office`` reading, ``kind="name"`` its ``given``
        and ``family`` ones), or None, taking out every reading, so the
        word leaves the vocabulary. Removing a reading the word does not
        hold changes nothing now, and is kept: a later choice of
        languages may turn that reading on."""
        if removed:
            raise _refusal("remove()", self, self._changed("remove", removed))
        edit = _make_edit("remove", words, kind, ())
        return dataclasses.replace(self, _edits=self._edits + (edit,))

    # -- private helpers --------------------------------------------------

    def _pool(self) -> Pool:
        if not self._edits:
            return _base_pool(self._base)
        return _built(self._base, self._edits)[0]

    def _changed(self, op: str,
                 entries: Mapping[str, object]) -> dict[str, object]:
        """A 2.x call's set fields as the sets it would leave, `op`
        being "add", "remove" or "set" (a constructor's or
        `dataclasses.replace`'s), for its refusal to translate; a list
        or the masks pass through, refused by name."""
        out: dict[str, object] = {}
        for name, words in entries.items():
            if name not in _SET_FIELDS:
                out[name] = words
                continue
            try:
                given = _normset(cast("Iterable[str]", words), name,
                                 warn=False)
            except (TypeError, ValueError):
                given = frozenset()
            current = getattr(self._sets, name)
            out[name] = (given if op == "set" else current | given
                         if op == "add" else current - given)
        return out

    def _deltas_from(self, other: Lexicon) -> tuple[
            list[tuple[str, int, int]], list[tuple[str, int, int]]]:
        ri = _index_module()
        mine, theirs = _keyed(self._pool()), _keyed(other._pool())
        kinds = []
        for kind in ri.CATEGORY:
            a = sum(1 for key in mine - theirs if key[1] == kind)
            r = sum(1 for key in theirs - mine if key[1] == kind)
            if a or r:
                kinds.append((kind, a, r))
        lists = []
        for name in _LIST_FIELDS + ("capitalization_exceptions",):
            m, t = set(getattr(self, name)), set(getattr(other, name))
            if m != t:
                lists.append((name, len(m - t), len(t - m)))
        return kinds, lists


def _keyed(pool: Pool) -> set[tuple[str, str, _Props]]:
    """The readings on in `pool`, each once, as the repr counts them:
    by word, kind and properties, whatever file holds them."""
    return {(r.text, r.kind, _clean(r.props))
            for rs in pool.values() for r in rs if r.on_by_default}


def _updates(held: Iterable[Any], edit: _Edit) -> bool:
    """Whether `edit` only updates the properties of a reading of its
    kind the word holds: the title warning's exemption (decisions/
    vocabulary-model, 2026-11-01 #754, the title warning)."""
    return any(r.kind == edit.kind
               and _clean(_merged(r.props, edit.props)) != _clean(r.props)
               for r in held)


@functools.cache
def _default_lexicon() -> Lexicon:
    # the config data modules, compiled from nameparser/vocab/, are the
    # single source of the default vocabulary: its sets are read from
    # nameparser/config/_compiled.py, never compiled from the index here
    # (_compiled_for), so Lexicon.default() loads no index.
    from nameparser.config.capitalization import CAPITALIZATION_EXCEPTIONS
    from nameparser.config.surnames import KOREAN_SURNAMES

    # every vocabulary constant is a frozenset since #293, and this
    # cache reading them ONCE is the reason they are frozen.
    return Lexicon(
        surnames=KOREAN_SURNAMES,
        # pass canonical pair-tuples so this strictly-typed call site never
        # feeds a Mapping to the tuple-annotated field; __init__ still
        # tolerates a Mapping at runtime for interactive use
        capitalization_exceptions=tuple(sorted(CAPITALIZATION_EXCEPTIONS.items())),
        _base="default",
    )
