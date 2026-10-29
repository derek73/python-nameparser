"""The reading index, and the compiler that folds readings into sets.

The default vocabulary is written per word in nameparser/vocab/*.toml,
each word listing its READINGS (what it can be read as, keyed by kind)
in the file of the language whose names it occurs in
(decisions/vocabulary-model). tools/vocab/build.py checks the files and
writes two modules from them, each generated and committed:

* nameparser/config/_index.py, the READING INDEX: for each word, one
  row per reading, ``(tag, kind, properties)``, the tag being its file's
  BCP 47 tag and the properties the ones the compiler reads. It is what
  a set has forgotten, which file each word came from.
* nameparser/config/_compiled.py, the sets the parser reads, which is
  :func:`compile_readings` run over the index.

This module is the compiler both the build and, from phase 3b, a choice
of languages run, so there is one implementation of what a reading
compiles to; tests/v2/test_reading_index.py holds that compiling the
index reproduces _compiled.py exactly. It is also the one way to read
the index at run time (:func:`readings_of`, :func:`index`).

It imports nothing internal at module level, and the index only inside
:func:`index`: the build loads this file by path, as it loads
_lexicon.py, so that a generated module left broken cannot stop the
tool that rewrites it.
"""
from __future__ import annotations

import functools
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from types import MappingProxyType
from typing import Any, TypedDict

#: kind -> category. The category decides which compiled field a reading
#: feeds. For title, suffix, particle and conjunction, the category's own
#: name is also a kind (`title = {}`: a title not yet classified), so
#: classifying a word later moves no set. bound_given's one kind shares
#: its category's name; the relation (birth_marker) and name (given,
#: family) categories have no generic kind. Kind
#: names are unique across categories; a fine kind arrives with its
#: category's classification, in a core PR, as one row here.
CATEGORY: dict[str, str] = {
    "title": "title",
    "salutation": "title",
    "style": "title",
    "academic": "title",
    "religious": "title",
    "nobility": "title",
    "military": "title",
    "office": "title",
    "occupation": "title",
    "kinship": "title",
    "modifier": "title",
    "suffix": "suffix",
    "generation": "suffix",
    "agnomen": "suffix",
    "credential": "suffix",
    "honorific": "suffix",
    "professional_honorific": "suffix",
    "status": "suffix",
    "courtesy": "suffix",
    "particle": "particle",
    "preposition": "particle",
    "article": "particle",
    "patronymic": "particle",
    "teknonymic": "particle",
    "clan": "particle",
    "rank": "particle",
    "saint": "particle",
    "alias": "particle",
    "conjunction": "conjunction",
    "bound_given": "bound_given",
    "birth_marker": "relation",
    "given": "name",
    "family": "name",
}

#: Behavioral properties per category: each compiles into a field, and
#: its allowed values are exactly what today's pipeline does. A name
#: reading's one is `default` (phase 3a): its other keys are evidence.
BEHAVIORAL: dict[str, frozenset[str]] = {
    "title": frozenset({"addresses", "after_given", "attaches", "cased",
                        "default"}),
    "suffix": frozenset({"acronym", "attached", "cased", "default"}),
    "particle": frozenset({"cased", "default"}),
    "conjunction": frozenset({"may_be_initial", "cased", "default"}),
    "bound_given": frozenset({"cased", "default"}),
    "relation": frozenset({"cased", "default"}),
    "name": frozenset({"default"}),
}

#: The suffix word kinds a name reading gates (rules/S11): the third
#: derived marker reads these, and a name reading beside another word
#: kind marks nothing, no gate reading that clash yet.
GATED_WORDS = frozenset({"generation", "agnomen"})


def indexed(kind: str) -> frozenset[str]:
    """The properties of a `kind` reading the index keeps: its
    category's behavioral ones, and on a `given` reading `same_as`,
    which compiles the word into GIVEN_NAME_ABBREVIATIONS (#789).
    Everything else a reading carries is evidence, compiled to
    nothing."""
    keep = BEHAVIORAL[CATEGORY[kind]]
    return keep | {"same_as"} if kind == "given" else keep


class ReadingProperties:
    """The unwritten values of the properties whose default is not
    false, defined once for every reading type that has a `kind` and
    `props`: the build's Reading, which holds a reading as its file
    wrote it, and :class:`IndexReading`, which holds it as the index
    does."""

    __slots__ = ()
    text: str
    kind: str
    props: Mapping[str, Any]

    @property
    def category(self) -> str:
        return CATEGORY[self.kind]

    @property
    def acronym(self) -> bool:
        """Matched with its periods removed: unwritten, true only for a
        credential."""
        return bool(self.props.get("acronym", self.kind == "credential"))

    @property
    def on_by_default(self) -> bool:
        """Compiled into the default vocabulary: unwritten, true. A
        reading written `default = false` is recorded and checked as a
        reading but compiles to nothing, a name reading included (3a),
        for a pack to turn on in phase 3 (decisions/vocabulary-model)."""
        return self.props.get("default", True) is not False

    def flag(self, prop: str) -> bool:
        """A `may_be_*` flag or `after_given`: unwritten, false."""
        return bool(self.props.get(prop, False))

    @property
    def addresses(self) -> object:
        """Which name a title addresses: unwritten, the family name. An
        object, not a str, because the build reads it before its check
        3 has refused a value that is not one of the allowed strings."""
        return self.props.get("addresses", "family")


@dataclass(frozen=True, slots=True)
class IndexReading(ReadingProperties):
    """One row of the reading index.

    ``text`` is the word, normalized as the vocabulary stores it;
    ``tag`` the BCP 47 tag of the file holding the reading (``"en"``,
    ``"pt-BR"``, ``"mul"``, ``"und"``); ``kind`` its vocabulary kind,
    a key of :data:`CATEGORY` (``"credential"``, ``"preposition"``,
    ``"given"``), finer than :class:`nameparser.ReadingKind`;
    ``props`` the properties :func:`indexed` keeps, as written, read
    through the accessors above for their unwritten values. A word in
    several files has a row per file, and a reading written
    ``default = false`` has its row too, with
    ``on_by_default`` false.

    A lookup result, not a value to keep: its ``props`` is a read-only
    view, so an IndexReading neither hashes nor pickles. What a parse
    keeps of it (phase 4a's ``Reading.languages``) is its tag."""

    text: str
    tag: str
    kind: str
    props: Mapping[str, Any]


#: A row as nameparser/config/_index.py writes it, under its word:
#: (tag, kind, properties), the properties as sorted (key, value) pairs,
#: a list value as a sorted tuple and the `attached` table as its side,
#: so the whole index is one constant.
Row = tuple[str, str, tuple[tuple[str, Any], ...]]
#: The index as written: (text, rows) per word, sorted by text, its
#: rows by tag and then kind.
Index = tuple[tuple[str, tuple[Row, ...]], ...]


def to_row(r: IndexReading) -> Row:
    """`r` as the index writes it under its word."""
    pairs = []
    for key in sorted(r.props):
        value = r.props[key]
        if key == "attached":
            value = value["side"] if isinstance(value, Mapping) else value
        elif isinstance(value, (list, tuple, set, frozenset)):
            value = tuple(sorted(value))
        pairs.append((key, value))
    return (r.tag, r.kind, tuple(pairs))


def from_row(text: str, row: Row) -> IndexReading:
    tag, kind, pairs = row
    return IndexReading(text, tag, kind, MappingProxyType(dict(pairs)))


@functools.cache
def _by_text() -> Mapping[str, tuple[Row, ...]]:
    # the index is written grouped by word, so this is one dict() call
    # in C, and an IndexReading is built only for a word looked up:
    # building all of them costs more than importing the index
    # (decisions/vocabulary-model, 2026-10-29 3a)
    from nameparser.config._index import READINGS
    return MappingProxyType(dict(READINGS))


@functools.cache
def index() -> tuple[IndexReading, ...]:
    """Every row of the shipped reading index, in its order (by text,
    then tag, then kind), for a compile over the whole pool. Built on
    first call and kept: the index describes the shipped files, which
    do not change in a process."""
    return tuple(from_row(text, row)
                 for text, rows in _by_text().items() for row in rows)


def readings_of(text: str) -> tuple[IndexReading, ...]:
    """Every reading the shipped files hold for `text`, on by default
    or not, one per file and kind, in index order; empty for a word no
    file holds.

    `text` is looked up as the vocabulary stores it (lowercase, NFC,
    edge periods removed; _lexicon._normalize), and a phrase whole
    (``"z domu"``). A reading the parse took from a caller's own
    vocabulary, from a shape or from position has no row here, which is
    what phase 4a's ``Reading.languages`` reads as empty."""
    return tuple(from_row(text, row) for row in _by_text().get(text, ()))


class Compiled(TypedDict):
    """What :func:`compile_readings` returns: one key per constant, in
    the order nameparser/config/_compiled.py defines them, typed as it
    declares them."""
    GIVEN_NAME_TITLES: frozenset[str]
    TITLES: frozenset[str]
    AFTER_GIVEN_TITLES: frozenset[str]
    TITLES_AMBIGUOUS: frozenset[str]
    TITLE_MODIFIERS: frozenset[str]
    TITLE_STYLES: frozenset[str]
    TITLE_PHRASES: frozenset[str]
    NON_GIVEN_NAME_PARTICLES: frozenset[str]
    PARTICLES: frozenset[str]
    CONJUNCTIONS: frozenset[str]
    CONJUNCTIONS_AMBIGUOUS: frozenset[str]
    BOUND_GIVEN_NAMES: frozenset[str]
    GIVEN_NAME_ABBREVIATIONS: frozenset[str]
    MAIDEN_MARKERS: frozenset[str]
    SUFFIX_WORDS: frozenset[str]
    GLUED_HONORIFICS: frozenset[str]
    SUFFIX_WORDS_AMBIGUOUS: frozenset[str]
    AGNOMENS: frozenset[str]
    SUFFIX_ACRONYMS_AMBIGUOUS: frozenset[str]
    SUFFIX_ACRONYMS: frozenset[str]
    CAPITALIZATION_EXCEPTIONS: dict[str, str]


def compile_readings(readings: Iterable[ReadingProperties]) -> Compiled:
    """Fold the readings on by default into the default vocabulary's
    constants. The readings are taken as already checked (the build's
    checks run before it calls this); each needs ``text``, ``kind``
    and ``props``.

    Raises ValueError on a post-nominal that is both an acronym and a
    word, a backstop the build's checks 4 and 5 always reach first."""
    texts = [(r, r.text) for r in readings if r.on_by_default]
    # the derived markers (the build's check 11): a clash with a name is
    # a word's name reading beside the reading it clashes with, and a
    # name reading written `default = false` marks nothing in the
    # default, as it compiles to nothing (3a)
    named = {t for r, t in texts if r.category == "name"}
    given = {t for r, t in texts if r.kind == "given"}
    titles: set[str] = set()
    given_titles: set[str] = set()
    after_given: set[str] = set()
    title_kinds: dict[str, set[str]] = {}
    attaches: dict[str, set[str]] = {}
    particles: set[str] = set()
    never_given: set[str] = set()
    conjunctions: set[str] = set()
    initial_conjunctions: set[str] = set()
    bound: set[str] = set()
    abbreviations: set[str] = set()
    markers: set[str] = set()
    words: set[str] = set()
    glued: set[str] = set()
    ambiguous_words: set[str] = set()
    agnomens: set[str] = set()
    ambiguous: set[str] = set()
    acronyms: set[str] = set()
    cased: dict[str, str] = {}
    for r, t in texts:
        p = r.props
        if "cased" in p:
            cased[t] = p["cased"]
        if r.category == "title":
            titles.add(t)
            if r.addresses == "given":
                given_titles.add(t)
            if r.flag("after_given"):
                after_given.add(t)
            title_kinds.setdefault(t, set()).add(r.kind)
            attaches.setdefault(t, set()).update(p.get("attaches", ()))
        elif r.category == "suffix":
            if r.acronym:
                acronyms.add(t)
                if t in named:
                    ambiguous.add(t)
            else:
                words.add(t)
                if "attached" in p:
                    glued.add(t)
                if t in named and r.kind in GATED_WORDS:
                    ambiguous_words.add(t)
                if r.kind == "agnomen":
                    agnomens.add(t)
        elif r.category == "particle":
            particles.add(t)
            if t not in given:
                never_given.add(t)
        elif r.category == "conjunction":
            conjunctions.add(t)
            if r.flag("may_be_initial"):
                initial_conjunctions.add(t)
        elif r.category == "bound_given":
            bound.add(t)
        elif r.category == "relation":
            markers.add(t)
        elif r.kind == "given" and "same_as" in p:
            abbreviations.add(t)
    contested = titles & given - particles
    out = Compiled(
        GIVEN_NAME_TITLES=frozenset(given_titles),
        # a title that may be a given name compiles into TITLES_AMBIGUOUS
        # INSTEAD: a word in TITLES is a title wherever it stands, which
        # is what a caller listing one there has always asked for
        TITLES=frozenset(titles - contested),
        AFTER_GIVEN_TITLES=frozenset(after_given),
        # the fourth derived marker (check 11): a title that may be a
        # given name, a title only inside a title phrase (rules/H9), and
        # so not in TITLES above. A
        # title that is also a particle ('st', 'freiherr') is left to the
        # particle rules, which weigh its given reading at the front
        # already (rules/P4)
        TITLES_AMBIGUOUS=frozenset(contested),
        # a word every title reading of which is a modifier: a title only
        # with a head title behind it in its run (decision 10, rules/H9)
        TITLE_MODIFIERS=frozenset(
            t for t, ks in title_kinds.items() if ks == {"modifier"}),
        TITLE_STYLES=frozenset(
            t for t, ks in title_kinds.items() if "style" in ks),
        # `attaches` resolved to the two-word phrases it licenses, the
        # word before and each title word of a kind it names
        TITLE_PHRASES=frozenset(
            f"{t} {h}" for t, kinds in attaches.items() if kinds
            for h, hk in title_kinds.items()
            if h != t and (hk & kinds or h in kinds)),
        NON_GIVEN_NAME_PARTICLES=frozenset(never_given),
        PARTICLES=frozenset(particles),
        CONJUNCTIONS=frozenset(conjunctions),
        CONJUNCTIONS_AMBIGUOUS=frozenset(initial_conjunctions),
        BOUND_GIVEN_NAMES=frozenset(bound),
        # a given name written short (`chas`, Filipino `ma`): opening the
        # given part period-marked, it is the given name, which outranks
        # rules/H2's shape (#789)
        GIVEN_NAME_ABBREVIATIONS=frozenset(abbreviations),
        MAIDEN_MARKERS=frozenset(markers),
        SUFFIX_WORDS=frozenset(words),
        GLUED_HONORIFICS=frozenset(glued),
        SUFFIX_WORDS_AMBIGUOUS=frozenset(ambiguous_words),
        AGNOMENS=frozenset(agnomens),
        SUFFIX_ACRONYMS_AMBIGUOUS=frozenset(ambiguous),
        SUFFIX_ACRONYMS=frozenset(acronyms),
        CAPITALIZATION_EXCEPTIONS=dict(sorted(cased.items())),
    )
    # One form per post-nominal: the word test strips only edge periods
    # and the acronym test strips all of them, so a word in both is
    # matched twice by two rules, and which one fired is unreadable from
    # outside. The sharper stake is the ambiguous set's: suffix_as_written
    # ORs the two branches, so an ambiguous acronym that were also a word
    # would be claimed through the word and bypass the period gate the
    # marking exists to impose. The single overlap was 'esq', dropped
    # 2026-09-08 (decisions/suffix-acronym-collisions). Lexicon guards
    # only that ambiguous half (its gate-bypass raise), so a caller may
    # still put an unambiguous word in both. In the TOML the overlap is
    # unreachable -- the build's check 4 refuses two suffix kinds on one
    # word, check 5 one kind with `acronym` differing between files, and
    # check 2 a word twice in one file -- so this is a backstop kept
    # because it costs one set intersection, not a check any input
    # reaches today.
    both = out["SUFFIX_ACRONYMS"] & out["SUFFIX_WORDS"]
    if both:
        raise ValueError(f"{sorted(both)}: a post-nominal is an acronym or a "
                         f"word, never both (check `acronym` in every file)")
    return out
