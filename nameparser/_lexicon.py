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


# The Arabic tatweel (kashida) stretches a word for looks and carries no
# letter, so deleting it changes no word's identity (#1151: `الدكتــور`
# is the title `الدكتور`). Token text is never rewritten.
_TATWEEL = "\u0640"


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

    Tatweel (U+0640) is deleted, in a non-ASCII word only (#1151).

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
        if _TATWEEL in word:
            word = word.replace(_TATWEEL, "")
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
    P5 licence both reach it) and wherever a caller's word is stored or
    looked up (_edit_words, which folds every word add() and remove()
    take, a phrase included, and readings_of), and a divergence between
    them fails silently: the entry simply stops matching."""
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


def _normset(entries: Iterable[str], field_name: str) -> frozenset[str]:
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
        n = _normalize(w)
        # "." or "" is a data bug (stray split artifact, empty CSV
        # cell); dropping it silently would also let a data-module typo
        # vanish instead of failing CI.
        if not n:
            raise ValueError(
                f"Lexicon.{field_name} entry {w!r} normalizes to empty "
                f"(lowercase + strip full stops/whitespace leaves nothing)"
            )
        # A list is matched one word at a time, so a multi-word entry
        # can never match -- the library itself shipped eight such dead
        # entries for years (repaired 2026-07-26). Warn, never raise: an
        # inert entry produces nothing, while a raise costs a working
        # configuration (AGENTS.md's gotcha on given-name title runs,
        # the precedent). split() covers all Unicode whitespace.
        if n != "".join(n.split()):
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

#: What those sets do not record: the kinds the views read (rules/R8,
#: rules/R9), and the titles written short that rules/H5's trailing
#: chain and rules/H9's article partner read where one may also be a
#: given name (#999), which is no
#: kind; the name is the tuple's first use.
#: `_LexiconSets` attributes after the `_VOCAB_FIELDS` ones, each a
#: compiled constant of its own.
_KIND_FIELDS = ("generation_words", "credential_words", "honorific_words",
                "patronymic_particles", "title_abbreviations",
                "title_case_name_words", "shared_names",
                "particle_given_names", "saint_particles",
                "capitalized_particles", "capital_opening_particles",
                "dotted_titles", "glued_titles", "bound_phrases")

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
    #: `iii`), a credential written as a word (`kc`), or an honorific
    #: (`さん`, `先生`), and the particles read as patronymics (`bin`):
    #: the kinds rules/R8's and rules/R9's views read, which the sets
    #: above do not record
    generation_words: frozenset[str]
    credential_words: frozenset[str]
    honorific_words: frozenset[str]
    patronymic_particles: frozenset[str]
    #: the words whose title reading is written `abbreviation=True`
    #: (`maj`); rules/H5's trailing chain reads one only beside
    #: `titles_ambiguous`, through classify's TRAILING_TITLE_TAG (#999)
    title_abbreviations: frozenset[str]
    #: the suffix words written `title_case_is_name=True` (`fils`,
    #: `kc`), whose writing leans where a name reading gates them:
    #: lower case is the suffix, Title case the name (rules/S6, #1039)
    title_case_name_words: frozenset[str]
    #: the names written `shared=True` (Sikh `kaur`, `singh`), which a
    #: community gives every member: rules/O6 and O7 neither take nor
    #: complete one, and P10 completes none (#704)
    shared_names: frozenset[str]
    #: the given names written `after_particle=True` (`carmen`), the
    #: second of a compound given name written behind a particle
    #: (`María del Carmen`): rules/P10 reads one as a middle name behind
    #: a one-word given name, and O6 leaves it there (#704)
    particle_given_names: frozenset[str]
    #: the particles of the `saint` kind (`san`, `santa`, `st`, `ste`): no given
    #: name phrase opens with one, `Santa María` being a surname (#704)
    saint_particles: frozenset[str]
    #: the particles of the kinds written with a capital, `saint` and
    #: `rank` (`st`, `san`, `freiherr`, `graf`): rules/R4's case repair
    #: writes one as a name word, not in lowercase (#1069)
    capitalized_particles: frozenset[str]
    #: the particles written `capital_opening=True` (`ter`, `der`):
    #: rules/R12's case repair writes one with a capital where no
    #: particle stands before it in the family name, nor, where it opens
    #: the family name, written right before it in any role (`Levon Ter
    #: Petrosyan`, but `Van der Walt`)
    capital_opening_particles: frozenset[str]
    #: the titles written `dotted=True` (`us`, `uk`, `pd`): rules/H10
    #: reads a run of single letters joined by full stops that spells
    #: one, at the head of a name (the given part's title run, or H6's
    #: before a family comma), as that title where a title the run keeps
    #: stands behind it (`U.S. District Judge`, #490)
    dotted_titles: frozenset[str]
    #: the titles written `attached="before"` (Thai `นาย`, `นางสาว`,
    #: `อาจารย์`): rules/W6 splits one off the start of the name's first
    #: word it is glued to, the mirror of `honorific_tails` (#317)
    glued_titles: frozenset[str]
    #: the two-word given names a bound word's `completed_by` lists
    #: ('عبد الله'), which rules/P12 joins past the first name word (#694)
    bound_phrases: frozenset[str]


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
    "honorific_words": "HONORIFIC_WORDS",
    "patronymic_particles": "PATRONYMIC_PARTICLES",
    "title_abbreviations": "TITLE_ABBREVIATIONS",
    "title_case_name_words": "TITLE_CASE_NAME_WORDS",
    "shared_names": "SHARED_NAMES",
    "particle_given_names": "PARTICLE_GIVEN_NAMES",
    "saint_particles": "SAINT_PARTICLES",
    "capitalized_particles": "CAPITALIZED_PARTICLES",
    "capital_opening_particles": "CAPITAL_OPENING_PARTICLES",
    "dotted_titles": "DOTTED_TITLES",
    "glued_titles": "GLUED_TITLES",
    "bound_phrases": "BOUND_PHRASES",
}


#: The groups `SAME_AS` is keyed by, one per kind of role a name match
#: compares (`_reading_index.SAME_AS_GROUPS` maps a reading's kind to
#: one; tests/v2/test_lexicon.py holds the two to one list).
_SAME_AS_GROUPS = frozenset({"given", "family", "title", "suffix"})

#: A group -> word -> the words it is a listed spelling of.
SameAs = Mapping[str, Mapping[str, frozenset[str]]]


def _same_as_of(compiled: Mapping[str, Any]) -> SameAs:
    """The compile's `SAME_AS` as the lexicon keeps it: per group, each
    word's full forms normalized, as a caller's `same_as` is written
    free-form."""
    return MappingProxyType({
        group: MappingProxyType({
            w: frozenset(_normalize(h) for h in heads)
            for w, heads in words.items()})
        for group, words in compiled["SAME_AS"].items()})


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


#: A group -> the words of it with a listed spelling that are a name of
#: their own too (`SAME_AS_NAMED`).
SameAsNamed = Mapping[str, frozenset[str]]


# -- the name match's fold, which the familiar-form index shares --------

#: Full stops and apostrophes: the typed one, the typographic U+2019,
#: the modifier letter U+02BC, and Uzbek Latin's other spellings of
#: the `ʻ` in `oʻ` and `gʻ` (U+02BB, U+2018, the backtick), so
#: `O’Brien` folds to `obrien` and `Gʻofurov` to `gofurov`
#: (decisions/name-matching, 2026-11-09). And the Arabic tatweel U+0640,
#: which `_normalize` deletes too (#1151), so a name's two spellings that
#: differ by one fold alike where the vocabulary and the match meet.
_DROPPED = str.maketrans("", "", ".'`\u2019\u02bc\u02bb\u2018\u0640")
#: The scripts whose combining marks `_fold` drops as accents.
_ACCENTED_SCRIPTS = ("LATIN ", "GREEK ", "CYRILLIC ")

def _fold(text: str) -> str:
    """The text with case, accents, full stops and apostrophes folded
    away: NFC, `.` and the apostrophes and their stand-ins (`_DROPPED`) removed,
    NFD, casefolded, then NFC again, so the folded text, and every key
    cut from it, is precomposed (a Hangul syllable, never a conjoining
    jamo). Hyphens and spaces are kept. A combining mark (Mn) is dropped
    only where the letter it attaches to is Latin, Greek or Cyrillic,
    where it is an accent; in another script (a Devanagari virama,
    anusvara or vowel sign) it is spelling and is kept. A letter counts
    as in those scripts where it or its casefolded form is, so a letter
    that casefolds into one (the micro sign U+00B5 into Greek mu, U+2183
    into Latin) loses its mark on the first fold, which keeps the fold
    idempotent; so does removing the full stops and apostrophes before
    the marks are read, a mark after one then attaching to the letter
    before it, and again after casefolding, which can write one (U+0149
    `ŉ` casefolds to `ʼn`). The iota subscript U+0345 is a mark like any
    other, so `ᾳ` folds to `α`."""
    if text.isascii():
        # no accent, no composition, and no apostrophe but the typed
        # one and the backtick
        return text.casefold().translate(_DROPPED)
    decomposed = unicodedata.normalize(
        "NFD", unicodedata.normalize("NFC", text).translate(_DROPPED))
    kept = []
    accented = False
    for c in decomposed:
        if unicodedata.category(c) == "Mn":
            if accented:
                continue
        else:
            accented = (unicodedata.name(c, "").startswith(_ACCENTED_SCRIPTS)
                        or unicodedata.name(c.casefold()[:1] or c, "")
                        .startswith(_ACCENTED_SCRIPTS))
        kept.append(c)
    # again after casefolding, which can write an apostrophe (U+0149)
    return unicodedata.normalize(
        "NFC", "".join(kept).casefold().translate(_DROPPED))


#: A given name -> every name it is paired with as a familiar form, in
#: either direction (`FAMILIAR`, read both ways).
Familiar = Mapping[str, frozenset[str]]


def _familiar_of(compiled: Mapping[str, Any],
                 key: str = "FAMILIAR") -> Familiar:
    """The compile's `FAMILIAR`, a familiar form -> the longer names its
    `short_for` lists, read both ways: each word with every name it is
    paired with directly, as the shorter name or the longer. The
    sources do not always write the shorter name first (the nicknames
    list's `barbara` / `babs`), so the
    match reads a pair whichever way it was written, and never chains
    two pairs (decisions/name-matching, 2026-11-08
    FAMILIAR FORMS). Each name is indexed under its fold too (`_fold`,
    the match's own), so a pair written accented (`józsi`, `józsef`)
    is found from either name written without its accents. With
    `key="ALTERNATE_SPELLINGS"` the same index of the alternate
    spellings, which pair alike (decisions/name-matching, 2026-11-12
    ALTERNATE SPELLINGS ARE OPT-IN)."""
    paired: dict[str, set[str]] = {}
    for short, longs in compiled[key].items():
        for long in longs:
            for key in {short, _fold(short)}:
                paired.setdefault(key, set()).add(long)
            for key in {long, _fold(long)}:
                paired.setdefault(key, set()).add(short)
    return MappingProxyType({w: frozenset(ns) for w, ns in paired.items()})


#: What a lexicon's readings compile to: the vocabulary sets by
#: `_LexiconSets` name, the listed-spelling map, the words in it that
#: are a name of their own as well, the familiar forms and the alternate
#: spellings.
_Compiled = tuple[Mapping[str, frozenset[str]], SameAs, SameAsNamed,
                  Familiar, Familiar]


def _compiled_of(compiled: Mapping[str, Any]) -> _Compiled:
    return (MappingProxyType(_vocab_fields(compiled)), _same_as_of(compiled),
            MappingProxyType(dict(compiled["SAME_AS_NAMED"])),
            _familiar_of(compiled),
            _familiar_of(compiled, "ALTERNATE_SPELLINGS"))


@functools.cache
def _default_compiled() -> _Compiled:
    # the compiled data module is the default's one source, so the
    # default never loads the reading index (decisions/vocabulary-
    # model, 2026-10-29 3a; its 2026-11-02 #754 entry, item 4)
    import nameparser.config._compiled as compiled
    return _compiled_of(vars(compiled))


_NO_SETS: Mapping[str, frozenset[str]] = MappingProxyType(
    {name: frozenset() for name in _COMPILED_FIELDS} | {
        "particles_ambiguous": frozenset()})
#: What the empty base compiles to: no sets and no listed spellings.
_NOTHING_COMPILED: _Compiled = (_NO_SETS, MappingProxyType(
    {g: MappingProxyType({}) for g in sorted(_SAME_AS_GROUPS)}),
    MappingProxyType({g: frozenset() for g in sorted(_SAME_AS_GROUPS)}),
    MappingProxyType({}), MappingProxyType({}))


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
    bare = _index_module().IndexReading("", "", kind, MappingProxyType({}))
    if prop == "acronym":
        return bare.acronym
    if prop == "addresses":
        return bare.addresses
    return bare.flag(prop)


#: The properties whose value is a list of words, each with what its
#: entries are and an example, for the messages refusing a value.
_LIST_PROPS: Mapping[str, str] = MappingProxyType({
    "attaches": "title kinds or title words, e.g. attaches=['military']",
    "completed_by": "single words, e.g. completed_by=['الله']",
    "short_for": "given names, e.g. short_for=['maxwell']",
    "spelling_of": "given names, e.g. spelling_of=['olga']",
})

#: Each matching-only category's list property: the names a familiar
#: form stands for, the names a spelling is another spelling of. A
#: caller's add of one EXTENDS the word's names in a reading of its own
#: (decisions/name-matching, 2026-11-08 FAMILIAR FORMS and 2026-11-12
#: ALTERNATE SPELLINGS ARE OPT-IN).
_MATCHING_LISTS: Mapping[str, str] = MappingProxyType({
    "familiar": "short_for", "spelling": "spelling_of"})


def _prop_value(kind: str, prop: str, value: object) -> object:
    """`value` canonical for the log, None where it is the unwritten
    one (which removes the property)."""
    if value is None or (isinstance(value, (bool, str))
                         and value == _unwritten(kind, prop)):
        return None
    if prop in ("abbreviation", "acronym", "after_given", "may_be_initial",
                "title_case_is_name", "shared", "after_particle",
                "capital_opening", "dotted"):
        if not isinstance(value, bool):
            raise TypeError(f"{prop} must be True or False, got {value!r}")
        return value
    if prop == "addresses":
        if value != "given":
            raise ValueError(f"addresses must be 'given' or 'family', "
                             f"got {value!r}")
        return value
    if prop == "attached":
        # a suffix glued after the name (rules/W2) or a title glued in
        # front of it (rules/W6), the side its category reads
        side = ("before" if _index_module().CATEGORY.get(kind) == "title"
                else "after")
        if value != side:
            raise ValueError(f"attached on a {kind!r} reading must be "
                             f"{side!r} (a {'title peeled off the start' if side == 'before' else 'tail peeled off the end'} "
                             f"of a name token) or None, got {value!r}")
        return value
    if prop in _LIST_PROPS:
        what = _LIST_PROPS[prop]
        if isinstance(value, (str, bytes)) or isinstance(value, Mapping):
            raise TypeError(f"{prop} must be an iterable of {what}, "
                            f"got {value!r}")
        try:
            items: tuple[object, ...] = tuple(cast("Iterable[object]", value))
        except TypeError:
            raise TypeError(f"{prop} must be an iterable of {what}, "
                            f"got {value!r}") from None
        words = [x for x in items if isinstance(x, str)]
        if len(words) != len(items):
            raise TypeError(f"{prop} entries must be strings, got "
                            f"{value!r}")
        if prop in ("short_for", "spelling_of") and (
                not words or any(not _normalize(x) for x in words)):
            # the build's check 3: each a given name, none empty
            raise ValueError(
                f"{prop} must be a non-empty list of given names, none "
                f"normalizing to nothing, got {value!r}; write e.g. "
                f"{what}")
        folded = tuple(sorted({_normalize(x) for x in words} - {""}))
        if prop == "completed_by" and any(" " in w for w in folded):
            # rules/P12 joins a bound word to the ONE word after it
            raise ValueError(f"completed_by entries must be single words, "
                             f"got {value!r}; list each completing word "
                             f"on its own")
        if prop in ("short_for", "spelling_of") and any(
                " " in w for w in folded):
            # the match compares a given name word by word
            raise ValueError(f"{prop} entries must be single given "
                             f"names, got {value!r}; list each on its own")
        return folded or None
    # same_as: the word this one is a listed spelling of, a given name
    # written short's full name (#789) or a title's or suffix's full form
    if not isinstance(value, str) or not value.strip():
        raise TypeError(f"same_as must be the word this one is a spelling "
                        f"of, a non-empty string, got {value!r}")
    return value


def _check_kind(kind: object, op: str) -> str | None:
    """`kind` checked for `op`: a kind, or on `remove` and `words` a
    category too; None (every reading) only on `remove`."""
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
        if op in ("remove", "words"):
            return kind
        raise ValueError(
            f"{kind!r} is a category with no kind of its name; add() "
            f"takes one of its kinds: " + ", ".join(
                k for k, c in ri.CATEGORY.items() if c == kind))
    raise ValueError(
        f"unknown reading kind {kind!r}; the kinds are "
        + ", ".join(ri.CATEGORY)
        + (f" (or a category, on {op}: "
           + ", ".join(sorted(categories)) + ")"
           if op in ("remove", "words") else ""))


def _edit_words(words: tuple[object, ...], op: str,
                kind: str | None) -> tuple[str, ...]:
    if not words:
        if op == "remove" and kind is not None:
            # every word's readings of `kind`: a remove of a whole kind,
            # which `remove` writes only with every=True, so that an
            # empty `remove(*words, kind=...)` never reaches it
            return ()
        raise TypeError(
            f"{op}() takes at least one word, e.g. {op}('dean', kind="
            f"'title')" + (", or every=True with a kind to take out every "
                           "word's readings of it, e.g. remove(kind="
                           "'title', every=True)" if op == "remove" else ""))
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
    if kind == "family":
        # a name category's property that only a given name takes: the
        # raise below names it, so the generic message leaves it out
        allowed -= {"after_particle"}
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
        if prop == "after_particle" and kind == "family":
            raise ValueError(
                "after_particle names a given name written behind a "
                "particle (rules/O7), so only a given reading takes it: "
                "write add(word, kind='given', after_particle=True)")
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
    k = _check_kind(kind, op)
    ws = _edit_words(words, op, k)
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
    if category in _MATCHING_LISTS:
        # the build's check 3: a familiar reading lists the longer names,
        # a spelling the names it is another spelling of
        prop = _MATCHING_LISTS[category]
        names = dict(p).get(prop)
        if not names:
            raise ValueError(
                f"a {category} reading needs {prop}, a non-empty list of "
                f"given names, e.g. add({'max' if category == 'familiar' else 'olha'!r}, "
                f"kind={category!r}, {_LIST_PROPS[prop]})")
        for w in ws:
            if w in names:
                raise ValueError(
                    f"{prop} names the word itself, {w!r}; it lists the "
                    f"other given names")
    for w in ws:
        # the build's check 8: a phrase is matched whole only as a birth
        # marker or a run of titles addressing the given name
        if " " in w and not (k == "birth_marker" or (
                category == "title" and ("addresses", "given") in p)):
            raise ValueError(
                f"{w!r} is a phrase, which can never match as a {k}: only "
                f"a birth_marker and a title with addresses='given' are "
                f"matched as a whole run; add its words one by one")
        # the build refuses attached on a title phrase: the glued-title
        # peel splits one word (rules/W6)
        if " " in w and category == "title" and ("attached", "before") in p:
            raise ValueError(
                f"{w!r} is a phrase; attached='before' marks a one-word "
                f"title that the glued-title peel splits off a word")
        # the build refuses may_be_initial on anything but a cased single
        # letter: no other word reads as an initial (rules/P8)
        if ("may_be_initial", True) in p and not (
                len(w) == 1 and w.upper() != w.lower()):
            raise ValueError(
                f"may_be_initial marks a single cased letter that may read "
                f"as an initial; {w!r} is not one")
    return _Edit(op, ws, k, p)


def _apply_edit(pool: dict[str, tuple[Any, ...]],
                edit: _Edit) -> tuple[str, ...]:
    """Apply `edit` to `pool` (word -> its readings) in place, returning
    the words it touched. An add of a kind the word holds updates that
    reading's properties in every file holding it, and turns a reading
    written `default = false` on; otherwise it adds the caller's own
    reading, which names no file. A remove with no words is one of a
    whole kind, reaching every word in the pool that holds a reading of
    it, whatever turned the reading on."""
    ri = _index_module()
    words = edit.words or tuple(
        w for w, rs in pool.items()
        if any(r.kind == edit.kind or r.category == edit.kind for r in rs))
    for w in words:
        rs = pool.get(w, ())
        if (edit.op == "add" and edit.kind is not None
                and edit.kind in _MATCHING_LISTS):
            # EXTENDS: the caller's names go in a reading of the caller's
            # own, attributed to the edit and to no file, and the compile
            # unions it with each file's, which stay as they are
            # (decisions/name-matching, 2026-11-08 FAMILIAR FORMS); an
            # explicit replace is remove, then add
            prop = _MATCHING_LISTS[edit.kind]
            added = set(dict(edit.props)[prop])
            mine = [r for r in rs if r.kind == edit.kind and not r.tag]
            if mine:
                added |= set(mine[0].props.get(prop, ()))
            reading = ri.IndexReading(w, "", edit.kind, MappingProxyType(
                {prop: tuple(sorted(added))}))
            pool[w] = tuple(r for r in rs if r not in mine) + (reading,)
            continue
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
    return words


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


@functools.lru_cache(maxsize=32)
def _chosen_pool(base: object, chosen: frozenset[str], strict: bool) -> Pool:
    """A base's readings under the choice of the file tags `chosen`,
    before the caller's edits (decisions/vocabulary-model, 2026-11-02
    #754, item 4): `choose` over the base's readings, under `strict`
    only the chosen files', mul.toml's and native-script ones; a
    reading an
    unchosen file leaves off stays in the pool off, so a caller's add
    of its kind still turns it on, as it does with no choice."""
    pool = _base_pool(base)
    if not chosen:
        return pool
    ri = _index_module()
    readings = [r for rs in pool.values() for r in rs]
    if strict:
        readings = ri.strict_kept(readings, chosen)
    out: dict[str, list[Any]] = {}
    for r in ri.choose(readings, chosen):
        out.setdefault(r.text, []).append(r)
    for r in readings:
        if not r.on_by_default and r.tag not in chosen:
            out.setdefault(r.text, []).append(r)
    return MappingProxyType({t: tuple(rs) for t, rs in out.items()})


@functools.lru_cache(maxsize=128)
def _built(base: object, edits: tuple[_Edit, ...], chosen: frozenset[str],
           strict: bool) -> tuple[Pool, Mapping[str, frozenset[str]],
                                  SameAs, SameAsNamed, Familiar, Familiar]:
    """A lexicon's readings by word and the sets they compile to, kept
    per base, log and choice: a compile costs milliseconds, paid once
    per configuration (decisions/vocabulary-model, 2026-11-01 #754).
    The choice filters the base's readings and the log applies after
    it, so a caller's reading survives any choice; one that clashes
    with a reading the choice turns on is refused, naming the edit
    (2026-11-02 #754, item 3)."""
    pool = dict(_chosen_pool(base, chosen, strict))
    touched = [(edit, _apply_edit(pool, edit)) for edit in edits]
    for w in dict.fromkeys(w for _, ws in touched for w in ws):
        try:
            _check_pool(pool, (w,))
        except ValueError as exc:
            if not chosen or _clashes_unchosen(base, edits):
                raise
            mine = " and ".join(_rendered(e for e, ws in touched if w in ws))
            raise ValueError(
                f"the lexicon's {mine} clashes with a reading the choice "
                f"turns on: {exc}") from None
    ri = _index_module()
    try:
        compiled = ri.compile_readings(
            r for rs in pool.values() for r in rs)
    except ri.CompileError as exc:
        raise ValueError(str(exc)) from None
    return (MappingProxyType(pool), *_compiled_of(compiled))


def _clashes_unchosen(base: object, edits: tuple[_Edit, ...]) -> bool:
    """Whether `edits` clash on `base` with no choice, so that a clash
    under one is the log's own rather than the choice's."""
    try:
        _built(base, edits, frozenset(), False)
    except ValueError:
        return True
    return False


def _compiled_for(base: object, edits: tuple[_Edit, ...],
                  chosen: frozenset[str] = frozenset(),
                  strict: bool = False) -> _Compiled:
    if not edits and base == "default":
        # under a choice, the shipped index compiled once per choice by
        # the reader every pack shares
        return (_choice_compiled(chosen, strict) if chosen
                else _default_compiled())
    if not edits and not chosen and base == "empty":
        return _NOTHING_COMPILED
    _, sets, same_as, named, familiar, alternate = _built(
        base, edits, chosen, strict)
    return sets, same_as, named, familiar, alternate


@functools.lru_cache(maxsize=32)
def _choice_compiled(chosen: frozenset[str], strict: bool) -> _Compiled:
    ri = _index_module()
    return _compiled_of(ri.compile_choice(chosen, strict))


class _ReadingFiles:
    """The files whose readings are on in one lexicon, by word: what
    ``Reading.languages`` names (decisions/vocabulary-model, 2026-11-02
    #754, sub-phase 4i-d). One per base, log and choice
    (`_reading_files`), held by each `Lexicon` it describes and never
    pickled; it hashes by identity, in C, so assemble's memo keyed by
    it costs no frame on a hit.

    The default answers from the reading index's rows
    (`_reading_index.languages_of`), and a choice with no log from the
    word's own rows under `choose`, which is exact because a choice's
    preference is per word; neither builds the lexicon's whole pool,
    which a log or a snapshot base has built already, at construction."""

    __slots__ = ("_base", "_edits", "_chosen", "_strict")

    def __init__(self, base: object, edits: tuple[_Edit, ...],
                 chosen: frozenset[str], strict: bool) -> None:
        self._base, self._edits = base, edits
        self._chosen, self._strict = chosen, strict

    def pool(self) -> Pool:
        """The lexicon's readings by word (`Lexicon._pool`)."""
        if not self._edits:
            return _chosen_pool(self._base, self._chosen, self._strict)
        return _built(self._base, self._edits, self._chosen,
                      self._strict)[0]

    def languages(self, text: str, kinds: frozenset[str]) -> tuple[str, ...]:
        """The tags of the files holding a reading of `text` (as the
        vocabulary stores it) of one of `kinds`, on in this lexicon,
        sorted; a caller's own reading names none."""
        ri = _index_module()
        readings: Iterable[Any]
        if self._edits or self._base not in ("default", "empty"):
            readings = self.pool().get(text, ())
        elif self._base == "empty":
            return ()
        elif not self._chosen:
            return cast("tuple[str, ...]", ri.languages_of(text, kinds))
        else:
            readings = ri.chosen_readings(ri.readings_of(text), self._chosen,
                                          self._strict)
        return tuple(sorted({r.tag for r in readings
                             if r.tag and r.kind in kinds
                             and r.on_by_default}))


@functools.lru_cache(maxsize=128)
def _reading_files(base: object, edits: tuple[_Edit, ...],
                   chosen: frozenset[str], strict: bool) -> _ReadingFiles:
    # one per configuration, so equal lexicons share assemble's memo
    return _ReadingFiles(base, edits, chosen, strict)


def _check_choice(languages: object, strict: object) -> tuple[
        frozenset[str], frozenset[str]]:
    """A recorded choice validated as `parser_for` validates one: its
    languages in canonical case and the file tags they select, the
    selection raising for a tag no file serves (decisions/
    vocabulary-model, 2026-11-02 #754, item 3)."""
    if not isinstance(strict, bool):
        raise TypeError(f"_strict must be True or False, got {strict!r}")
    if (isinstance(languages, (str, bytes, bytearray, Mapping))
            or not isinstance(languages, Iterable)):
        raise TypeError(f"_languages must be a set of BCP 47 tags, e.g. "
                        f"frozenset({{'pt'}}), got {languages!r}")
    tags = frozenset(cast("Iterable[object]", languages))
    for tag in tags:
        if not isinstance(tag, str):
            raise TypeError(f"_languages entries must be str BCP 47 tags, "
                            f"got {tag!r}")
    if not tags:
        if strict:
            raise ValueError(
                "a strict choice keeps only the chosen languages' "
                "vocabulary and the shared words (mul.toml), and "
                "_languages chooses none; choose through "
                "parser_for(..., strict=True) with a pack that chooses one")
        return frozenset(), frozenset()
    canon = frozenset(_canonical(cast(str, t)) for t in tags)
    return canon, _index_module().selected(canon, strict=strict)


def _canonical(tag: str) -> str:
    """`tag` in BCP 47's canonical case: the language subtag lowercase,
    a four-letter script subtag title case, a two-letter region
    uppercase, every other subtag lowercase (RFC 5646, 2.1.1). Equal
    choices then compare and hash equal, whatever case they were
    written in."""
    first, *rest = tag.split("-")
    out = [first.lower()]
    for sub in rest:
        if len(sub) == 4 and sub.isalpha():
            out.append(sub.title())
        elif len(sub) == 2 and sub.isalpha():
            out.append(sub.upper())
        else:
            out.append(sub.lower())
    return "-".join(out)


#: The most tags a repr lists (a `Lexicon`'s choice, a `Locale`'s); a
#: longer choice is shown by its size, so the repr stays bounded however
#: many languages are chosen.
_REPR_TAGS = 3


def _shown_choice(languages: frozenset[str]) -> str:
    if len(languages) > _REPR_TAGS:
        return f"languages: {len(languages)}"
    return "languages " + "+".join(sorted(languages))


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


@functools.cache
def _choice_masks(chosen: frozenset[str], strict: bool = False) -> tuple[
        frozenset[str], tuple[tuple[str, str], ...]]:
    """The case masks the choice of the file tags `chosen` moves against
    the default's compile: the ones that leave and the ones set. A mask
    is no reading (a `Lexicon` keeps its masks in a field of their own),
    so `parser_for` moves them in that field, as 3b's delta did."""
    ri = _index_module()
    old = ri.compile_choice(frozenset())["CAPITALIZATION_EXCEPTIONS"]
    new = ri.compile_choice(chosen, strict)["CAPITALIZATION_EXCEPTIONS"]
    return (frozenset(old.keys() - new.keys()),
            tuple(sorted((k, v) for k, v in new.items() if old.get(k) != v)))


def _rechosen_masks(lexicon: Lexicon, chosen: frozenset[str],
                    strict: bool) -> tuple[tuple[str, str], ...]:
    """`lexicon`'s masks moved from its own choice's to `chosen`'s: the
    base's choice's moves undone, then the new choice's applied, so a
    chained choice moves them as the union does."""
    cap = dict(lexicon.capitalization_exceptions)
    if lexicon.languages:
        default = _index_module().compile_choice(
            frozenset())["CAPITALIZATION_EXCEPTIONS"]
        gone, joined = _choice_masks(lexicon._chosen, lexicon.strict)
        for k in gone:
            cap.setdefault(k, default[k])
        for k, v in joined:
            if cap.get(k) == v:
                if k in default:
                    cap[k] = default[k]
                else:
                    del cap[k]
    gone, joined = _choice_masks(chosen, strict)
    for k in gone:
        cap.pop(k, None)
    cap.update(joined)
    return tuple(sorted(cap.items()))


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
        # a remove of a whole kind (no words) joins no call of words
        if (calls and e.words and calls[-1][1]
                and calls[-1][0] == e.op
                and calls[-1][2:] == (e.kind, e.props)):
            calls[-1][1].extend(e.words)
        else:
            calls.append((e.op, list(e.words), e.kind, e.props))
    out = []
    for op, words, kind, props in calls:
        args = [repr(w) for w in words]
        if kind is not None:
            args.append(f"kind={kind!r}")
        args += [f"{k}={_shown_value(kind, k, v)}" for k, v in props]
        if op == "remove" and not words:
            args.append("every=True")
        out.append(f".{op}({', '.join(args)})")
    return out


def _shown_value(kind: str | None, prop: str, value: object) -> str:
    """A logged property value as a caller writes it: a removed one as
    its unwritten value where it has one (`may_be_initial=False`)."""
    if value is None and kind is not None and prop in (
            "abbreviation", "acronym", "addresses", "after_given",
            "may_be_initial", "title_case_is_name", "shared",
            "after_particle", "capital_opening", "dotted"):
        value = _unwritten(kind, prop)
    if isinstance(value, tuple) and len(value) > _SHOWN_WORDS:
        # bounded: a reading's list may name every title word it
        # reaches
        return (repr(list(value[:_SHOWN_WORDS]))[:-1]
                + f", ... {len(value) - _SHOWN_WORDS} more]")
    return repr(list(value) if isinstance(value, tuple) else value)


#: The most words a clash message shows of one property's list.
_SHOWN_WORDS = 6


def _refusal(where: str, removed: Mapping[str, object]) -> TypeError:
    """The TypeError for a 2.x spelling: a list or the masks with the
    call that changes them, a set field with docs/migrate.rst's table,
    which names the kind of each (decisions/vocabulary-model,
    2026-11-08 #1003)."""
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
        f"remove(*words, kind=...); docs/migrate.rst's Lexicon table "
        f"gives the kind for each 2.x field")


#: The keys of the one 2.x `Lexicon` layout 3.0 loaded, 2.7's and
#: 2.8's, read off a 2.8.0 `Lexicon.default()` state; 3.0 admitted
#: `given_names` beside them. A record of what shipped, so it never
#: follows `_VOCAB_FIELDS`, which a new vocabulary field joins.
_LAYOUT_3_0_LOADED = frozenset({
    "after_given_titles", "agnomens", "bound_given_names",
    "capitalization_exceptions", "conjunctions", "conjunctions_ambiguous",
    "given_name_abbreviations", "given_name_titles", "honorific_tails",
    "maiden_markers", "particles", "particles_ambiguous", "suffix_acronyms",
    "suffix_acronyms_ambiguous", "suffix_words", "suffix_words_ambiguous",
    "surnames", "title_modifiers", "title_phrases", "title_styles",
    "titles", "titles_ambiguous"})


def _refused_2x(state: Mapping[str, object]) -> ValueError:
    """The ValueError for a 2.x `Lexicon` state, its remedy told by the
    state's layout, since a caller holding an old pickle seldom knows
    which release wrote it (decisions/vocabulary-model, 2026-11-08
    #1003). It is raised wherever the `Lexicon` is, so a `Parser` or
    locale pack holding one is named too. Any other layout is named by
    the keys it lacks and holds beyond that one, as 3.0 named them."""
    held = "the Lexicon, or the Parser or locale pack holding it"
    missing = sorted(_LAYOUT_3_0_LOADED - set(state))
    unexpected = sorted(set(state) - _LAYOUT_3_0_LOADED - {"given_names"})
    if not missing and not unexpected:
        return ValueError(
            f"this Lexicon was pickled by nameparser 2.7 or 2.8, which "
            f"3.1 no longer loads: load the pickle under 3.0 and pickle "
            f"the loaded object ({held}) again; if 3.0 refuses the "
            f"pickle too, build the object again")
    return ValueError(
        f"this Lexicon was pickled by nameparser 2.x in a layout no 3.x "
        f"release loads (missing: {', '.join(missing) or 'none'}; "
        f"unexpected: {', '.join(unexpected) or 'none'}), as 2.6 and "
        f"earlier wrote: build the object ({held}) again")


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
    one is a title only inside a title phrase (rules/H9). Added in
    3.0."""

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
    the field and pointing at docs/migrate.rst's table of the kind each
    field's words take. Three fields stay, being outside the per-word model:
    ``surnames``, ``given_names`` and ``capitalization_exceptions``.

    State is a base (the shipped vocabulary, none, or a pickled
    release's), the choice of languages :func:`~nameparser.parser_for`
    records (:attr:`languages`, :attr:`strict`), the ordered log of
    :meth:`add` and :meth:`remove` calls applied after the choice, and
    the three fields; two lexicons are equal when all of them are, the log compared call by call as written, so two
    logs that read alike can still differ (decisions/vocabulary-model,
    2026-11-02 #754, item 3)."""

    #: Family names for the unspaced-name segmentation stage (#271),
    #: matched longest-first against the start of the FIRST token
    #: written wholly in a script :attr:`Policy.segment_scripts
    #: <nameparser.Policy.segment_scripts>` activates. The default
    #: carries the Korean census list
    #: (``nameparser/config/_ko_surnames.py``); Chinese
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
    #: the switch on. Added in 3.0.
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
    #: capitalization_exceptions_map; the default's are
    #: ``Lexicon.default().capitalization_exceptions``.
    # Canonical storage: sorted tuple of (key, value) pairs. The
    # constructor tolerates any Mapping (or pair iterable) at runtime and
    # canonicalizes here; this closes the caller-aliasing hole and keeps
    # Lexicon hashable. Read via capitalization_exceptions_map.
    capitalization_exceptions: tuple[tuple[str, str], ...] = ()
    # The base, the log and the choice: constructor parameters under
    # underscore names, so that dataclasses.replace and copy.replace
    # carry them, and no public API (decisions/vocabulary-model,
    # 2026-11-02 #754, item 3); a choice is set publicly by parser_for
    # alone, and read through `languages` and `strict`.
    _base: Any = "empty"
    _edits: tuple[_Edit, ...] = ()
    # marked added: a 4i-b pickle, from no release, holds no choice and
    # loads choosing nothing, its log already holding what a choice of
    # 3b's delta had written into it
    _languages: frozenset[str] = field(
        default=frozenset(), metadata={_ADDED_IN: "3.0.0"})
    _strict: bool = field(default=False, metadata={_ADDED_IN: "3.0.0"})
    # the file tags the choice selects, derived from it
    _chosen: frozenset[str] = field(
        init=False, repr=False, compare=False, hash=False)
    _cap_map: Mapping[str, str] = field(
        init=False, repr=False, compare=False, hash=False)
    _sets: _LexiconSets = field(
        init=False, repr=False, compare=False, hash=False)
    # group -> word -> the words it is a listed spelling of (`given`:
    # `wm` -> {`william`}), from every reading's `same_as` in the group
    # of its kind; built at construction, never pickled, like `_cap_map`
    _same_as: SameAs = field(
        init=False, repr=False, compare=False, hash=False)
    # group -> the words with a link there that are a name of their own
    # too (`jo` among given names), whose links need the period
    # (`_headwords`); built like `_same_as`
    _same_as_named: SameAsNamed = field(
        init=False, repr=False, compare=False, hash=False)
    # a given name -> every name it is paired with as a familiar form,
    # either way (`max` -> {`maxwell`, `maximilian`, ...},
    # `maximilian` -> {`max`}), from every `familiar` reading's
    # `short_for`, read by the name match alone (`_familiar_forms`);
    # built like `_same_as`
    _familiar: Familiar = field(
        init=False, repr=False, compare=False, hash=False)
    # a given name -> every name it is paired with as an alternate
    # spelling, either way, from every `spelling` reading's
    # `spelling_of`, read by the name match alone (`_alternate_spellings`);
    # built like `_familiar`
    _alternate: Familiar = field(
        init=False, repr=False, compare=False, hash=False)
    # what assemble keys Reading.languages by: one per base, log and
    # choice (_ReadingFiles)
    _files: _ReadingFiles = field(
        init=False, repr=False, compare=False, hash=False)

    def __init__(
        self, *,
        surnames: Iterable[str] = frozenset(),
        given_names: Iterable[str] = frozenset(),
        capitalization_exceptions: (Mapping[str, str]
                                    | Iterable[tuple[str, str]]) = (),
        _base: object = "empty",
        _edits: Iterable[_Edit] = (),
        _languages: Iterable[str] = frozenset(),
        _strict: bool = False,
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
        languages, chosen = _check_choice(_languages, _strict)
        put("_languages", languages)
        put("_strict", _strict)
        put("_chosen", chosen)
        compiled, same_as, named, familiar, alternate = _compiled_for(
            self._base, canon, chosen, _strict)
        put("_files", _reading_files(self._base, canon, chosen, _strict))
        put("_same_as", same_as)
        put("_same_as_named", named)
        put("_familiar", familiar)
        put("_alternate", alternate)
        put("_sets", _LexiconSets(
            **compiled, surnames=self.surnames, given_names=self.given_names))
        if removed:
            raise _refusal("Lexicon() (and dataclasses.replace)", removed)

    # -- constructors ----------------------------------------------------

    @classmethod
    def empty(cls) -> Lexicon:
        """A lexicon holding no readings, no surnames, no given names
        and no case masks, equal to ``Lexicon()``: the start for a
        fragment to join onto another with ``|``, or for a vocabulary
        built from nothing. A parser over it still reads by shape and
        position (``Dr. John Smith`` keeps title ``Dr.``, a period-marked
        word opening a name), and, the default :class:`Policy
        <nameparser.Policy>` dividing unspaced Hangul, warns at
        construction that no surnames cover it."""
        return cls()

    @classmethod
    def default(cls) -> Lexicon:
        """The shipped vocabulary, the lexicon ``Parser()`` uses when
        given none: every reading the language files turn on by
        default, the Korean census surnames and the case masks, with no
        :attr:`given_names` and no choice of languages. Cached, so
        every call returns the same object, which being immutable is
        safe to share; configure a copy with :meth:`add`,
        :meth:`remove` or ``|``."""
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
        # A choice is shown by its tags, and the readings counted against
        # the named lexicon under the same choice
        choice = ""
        named = [("default", Lexicon.default()), ("empty", Lexicon.empty())]
        if self._languages:
            choice = ", " + _shown_choice(self._languages) + (
                ", strict" if self._strict else "")
            named = [(label, dataclasses.replace(
                other, _languages=self._languages, _strict=self._strict,
                capitalization_exceptions=_rechosen_masks(
                    other, self._chosen, self._strict)))
                for label, other in named]
        for label, other in named:
            if self == other:
                return f"Lexicon({label}{choice})"
        candidates = [(label, self._deltas_from(other))
                      for label, other in named]
        label, (kinds, lists) = min(
            candidates,
            key=lambda c: sum(a + r for _, a, r in c[1][0] + c[1][1]))

        def counts(deltas: list[tuple[str, int, int]]) -> str:
            return ", ".join(
                name + ": " + "".join(
                    part for part, n in ((f"+{a}", a), (f"-{r}", r)) if n)
                for name, a, r in deltas)

        rendered = "; ".join(filter(None, (counts(kinds), counts(lists))))
        return (f"Lexicon({label} + {rendered or f'edits: {len(self._edits)}'}"
                f"{choice})")

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
                "_base": base, "_edits": tuple(tuple(e) for e in self._edits),
                "_languages": self._languages, "_strict": self._strict}

    def __setstate__(self, state: dict[str, object]) -> None:
        # A 2.x state holds the compiled sets, refused since 3.1
        # (decisions/vocabulary-model, 2026-11-08 #1003); a 3.0 one is
        # checked for its layout as _types._guarded_setstate checks the
        # other frozen types', the one skew admitted a field marked
        # `_ADDED_IN` with a default (`_languages`, `_strict`), and then
        # built through the constructor, which validates every value as
        # for a caller's.
        if "titles" in state:
            raise _refused_2x(state)
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
        that is not empty and the choice the one that is made, and two
        different bases, or two different choices, raise."""
        if not isinstance(other, Lexicon):
            return NotImplemented
        if (self._languages and other._languages
                and (self._languages, self._strict)
                != (other._languages, other._strict)):
            raise ValueError(
                "cannot join two lexicons compiled under different choices "
                "of languages or of strictness; combine choices with "
                "parser_for, which unions them: parser_for(*packs, "
                "base=parser)")
        mine = self if self._languages else other
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
            _base=base, _edits=self._edits + other._edits,
            _languages=mine._languages, _strict=mine._strict)

    # -- properties -------------------------------------------------------

    @property
    def capitalization_exceptions_map(self) -> Mapping[str, str]:
        return self._cap_map

    @property
    def languages(self) -> frozenset[str]:
        """The languages this lexicon's readings are chosen under, as
        BCP 47 tags; empty where none was chosen. Set by
        :func:`~nameparser.parser_for`, which unions a base's choice
        with its packs' (decisions/vocabulary-model, 2026-11-02 #754,
        item 4): the shipped readings are filtered by the choice, and
        the lexicon's own :meth:`add` and :meth:`remove` calls apply
        after it. Added in 3.0."""
        return self._languages

    @property
    def strict(self) -> bool:
        """Whether the choice is strict: only the chosen languages'
        vocabulary files, mul.toml and native-script words' readings (as a
        plain choice of the same languages keeps them) are read. Added in 3.0."""
        return self._strict

    # -- access -----------------------------------------------------------

    def readings_of(self, word: str) -> tuple[LexiconReading, ...]:
        """The readings this lexicon holds for `word`: one per kind and
        properties, each with the shipped files that hold it, a reading
        a caller added naming none; empty for a word it holds no reading
        of. `word` is normalized as the lexicon stores it, a phrase
        (``"z domu"``) whole. "Is X a title here?" is ``any(r.category
        == "title" for r in lexicon.readings_of(x))``; whether a parse
        read it as one is :attr:`Token.reading`'s. Added in 3.0."""
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

    def words(self, *, kind: str, **properties: object) -> tuple[str, ...]:
        """The words holding a reading of `kind` on in this lexicon,
        sorted: a kind or a category, as :meth:`remove` takes it
        (``words(kind="title")`` lists every title word, ``dean``
        among them, whichever set its readings compile to), and
        `properties`, which a kind takes (``title``, ``suffix`` and
        ``particle`` are kinds as well as categories, and take their
        own kind's properties), narrowing to the readings that carry
        them as :meth:`add` spells them, each compared in its own
        reading's kind (so through a category an unwritten value means
        each kind's own: ``acronym=None`` under ``suffix`` lists the
        credentials, unwritten-true, and the suffix words, unwritten-
        false, alike)
        (``words(kind="title", addresses="given")``, the titles that
        address a person by the given name). A phrase the lexicon holds
        whole (``"z domu"``) is one entry. Added in 3.0."""
        k = _check_kind(kind, "words")
        assert k is not None
        ri = _index_module()
        if properties:
            if k not in ri.CATEGORY:
                raise ValueError(
                    f"words() takes properties with a kind, not the "
                    f"category {k!r}; name one of its kinds: " + ", ".join(
                        x for x, c in ri.CATEGORY.items() if c == k))
            # checked against the kind named; compared below against
            # each reading's own kind, since a kind that is also a
            # category reaches kinds whose unwritten value differs
            # (`acronym` is unwritten-true on a credential, false on a
            # suffix word)
            _edit_props(k, properties)

        return tuple(sorted(
            w for w, rs in self._pool().items()
            if any(r.on_by_default and (r.kind == k or r.category == k)
                   # a reading holds its properties canonical, as the
                   # build and add write them, the unwritten value never
                   and all(r.props.get(p) == _prop_value(r.kind, p, v)
                           for p, v in properties.items())
                   for r in rs)))

    # -- editing ----------------------------------------------------------

    # `kind` is required, and a type checker reads it so: the runtime
    # default exists only to catch a 2.x call, which names no kind, and
    # refuse it pointing at docs/migrate.rst's table of kinds rather than
    # with Python's own missing-argument error
    if TYPE_CHECKING:
        def add(self, *words: str, kind: str,
                **properties: object) -> Lexicon: ...
    else:
        def add(self, *words: str, kind: str | None = None,
                **properties: object) -> Lexicon:
            """This lexicon with a reading of `kind` added to each word.
            `kind` is required; the signature's default exists only so
            that a 2.x call, which names no kind, is refused pointing at
            docs/migrate.rst's table of kinds. It is a vocabulary kind as
            the language files write it, a key of
            ``nameparser._reading_index.CATEGORY`` (``"title"``,
            ``"office"``, ``"credential"``, ``"generation"``,
            ``"preposition"``, ``"conjunction"``, ``"bound_given"``,
            ``"birth_marker"``, ``"given"``, ``"family"``, ...), and
            `properties` that kind's behavioral properties as the files
            spell them (``addresses="given"``, ``after_given=True``,
            ``abbreviation=True``, ``attaches=[...]``, ``acronym=...``, ``attached="after"`` on a suffix word reading
            and ``attached="before"`` on a one-word title reading (rules/W2
            and W6),
            ``may_be_initial=True``, ``completed_by=[...]`` on a
            ``bound_given`` reading, ``after_particle=True`` on a
            ``given`` reading, ``shared=True`` on a name reading,
            ``capital_opening=True`` on a particle reading,
            ``dotted=True`` on a title reading, and
            ``same_as=...`` on a reading of any kind: the word this one
            is a spelling of, which name matching reads as a
            ``listed-spelling`` and keys alike in the roles that read
            the kind's words (a ``given`` reading's in the given name,
            middle name and nickname, a ``family`` reading's in the
            family and maiden names, a title's and a suffix's in theirs),
            and which on a ``given`` reading also marks a given name
            written short; written on a word, it applies to the word's
            given readings, so the word keeps no plain given reading
            and its link counts written bare, where a word the
            vocabulary also holds as a name of its own counts only
            written with its period), and ``short_for=[...]`` on a
            ``familiar`` reading, the longer given names a familiar
            form stands for, which name matching reads as a
            ``familiar-form`` where that outcome is accepted and no
            parse reads (``add("max", kind="familiar",
            short_for=["maxwell"])``), which EXTENDS the longer names
            the word's shipped familiar readings list, in a reading of
            the caller's own that names no file, rather than replacing
            them (unlike an add of any other kind the word holds); to
            replace them, ``remove(word, kind="familiar")`` first. A
            pair lives on the word whose reading lists the other (its
            shorter name, as the files write it): to cut
            ``Max`` / ``Maximilian``, remove ``max``'s familiar
            reading and add it back without ``maximilian``; a property
            given its unwritten value (``None``, ``False``) is removed. Where the word holds a reading of `kind`
            already, the add updates its properties in every file holding
            it; otherwise it adds the caller's own reading, which names no
            file. Warns where it makes a title reading that a ``given``
            reading keeps a title only inside a title phrase (rules/H9),
            naming the ``remove`` that makes it a title everywhere."""
            old = {k: properties.pop(k) for k in list(properties)
                   if k in _SET_FIELDS + _LIST_FIELDS
                   or k == "capitalization_exceptions"}
            if old:
                raise _refusal("add()", old)
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
               every: bool = False, **removed: object) -> Lexicon:
        """This lexicon without each word's readings of `kind`: a kind,
        or a category, matching every kind of it (``kind="title"`` takes
        out ``dean``'s ``office`` reading, ``kind="name"`` its ``given``
        and ``family`` ones), or None, taking out every reading, so the
        word leaves the vocabulary. With ``every=True``, no words and a
        `kind`, every word's readings of it go (``remove(kind="title",
        every=True)``), those a later choice of languages turns on
        included; a call with no words and no `every` raises, so an
        empty ``remove(*words, kind=...)`` never takes out a whole kind.
        Removing a reading the word does not hold changes nothing now,
        and is kept: a later choice of languages may turn that reading
        on."""
        if removed:
            raise _refusal("remove()", removed)
        if not isinstance(every, bool):
            raise TypeError(f"remove() takes every as True or False, got "
                            f"{every!r}")
        if every and words:
            raise TypeError(
                f"remove() takes words or every=True, not both: every=True "
                f"takes out every word's readings of the kind; got "
                f"{len(words)} word(s)")
        if every and kind is None:
            raise TypeError(
                "remove(every=True) takes a kind, e.g. remove(kind='title', "
                "every=True); to remove everything, start from "
                "Lexicon.empty()")
        if not every and not words:
            raise TypeError(
                "remove() takes at least one word, e.g. remove('dean', "
                "kind='title'), or every=True with a kind to take out every "
                "word's readings of it, e.g. remove(kind='title', "
                "every=True)")
        edit = _make_edit("remove", words, kind, ())
        return dataclasses.replace(self, _edits=self._edits + (edit,))

    # -- private helpers --------------------------------------------------

    def _pool(self) -> Pool:
        return self._files.pool()

    def _headwords(self, word: str, group: str, *,
                   period: bool = True) -> frozenset[str]:
        """Every word reachable from `word`, normalized, through the
        `same_as` links of `group` (`given`, `family`, `title` or
        `suffix`, the group of the readings' kinds), the word itself
        included: `Wm.` among given names is {`wm`, `william`}, and `sr`
        among titles {`sr`, `señor`, `senhor`}. A word's readings of
        another kind are another group's (`ma` is María written short
        among given names and only itself among surnames), and a word
        with no listed spelling is itself alone. A loop, which a
        caller's edits can write where the build refuses it in the
        files, yields every word in it. The name match reads two words
        as listed spellings of each other where their sets meet. `period`
        says whether the word was written with its trailing full stop,
        which normalizing drops: a word that is a name of its own in
        `group` as well as a spelling (`jo`, José written short and the
        given name Jo) reaches its links only where it was, and is itself
        alone where it was not."""
        links = self._same_as.get(group)
        if links is None:
            raise ValueError(f"unknown same_as group {group!r}; the groups "
                             f"are {', '.join(sorted(_SAME_AS_GROUPS))}")
        start = _normalize(word)
        if not period and start in self._same_as_named[group]:
            return frozenset({start})
        seen = {start}
        todo = [start]
        while todo:
            for head in links.get(todo.pop(), ()):
                if head not in seen:
                    seen.add(head)
                    todo.append(head)
        return frozenset(seen)

    def _familiar_forms(self, word: str) -> frozenset[str]:
        """The given names `word`, normalized, is paired with directly
        as a familiar form, in either direction (`max` -> {`maxwell`,
        `maximilian`, ...}, `maximilian` -> {`max`}), empty for a
        word in no pair. Never chained: two longer names paired with
        one shorter one (`maximilian`, `maxim`) do not reach each
        other. Read by the name match alone, never by a parse."""
        return self._familiar.get(_normalize(word), frozenset())

    def _alternate_spellings(self, word: str) -> frozenset[str]:
        """The given names `word`, normalized, is paired with directly
        as an alternate spelling, in either direction (`olha` ->
        {`olga`}, `olga` -> {`olha`}), empty for a word in no pair.
        Never chained, as familiar forms are not: `yurii` and `yury`,
        each paired with `yuri`, do not reach each other. Read by the
        name match alone, never by a parse."""
        return self._alternate.get(_normalize(word), frozenset())

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
    # nameparser/config/_compiled.py, compiled from nameparser/vocab/, is
    # the single source of the default vocabulary: its sets are read from
    # it, never compiled from the index here (_compiled_for), so
    # Lexicon.default() loads no index.
    from nameparser.config._compiled import CAPITALIZATION_EXCEPTIONS
    from nameparser.config._ko_surnames import KOREAN_SURNAMES

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
