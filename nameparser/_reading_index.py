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

This module is the compiler both the build and a choice of languages
(phase 3b, :func:`choose`) run, so there is one implementation of what a reading
compiles to; tests/v2/test_reading_index.py holds that compiling the
index reproduces _compiled.py exactly. It is also the one way to read
the index at run time (:func:`readings_of`, :func:`index`), and the
reader every parse calls for ``Reading.languages``
(:func:`languages_of`), so the first parse in a process loads it.

It imports nothing internal at module level, and the index only inside
:func:`index`: the build loads this file by path, as it loads
_lexicon.py, so that a generated module left broken cannot stop the
tool that rewrites it.
"""
from __future__ import annotations

import functools
import unicodedata
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
#: category's classification, in a core PR, as one row here. The
#: familiar category's one kind, `familiar` (a short given name standing
#: for longer ones, `max` of `maximilian`), compiles into FAMILIAR alone,
#: which only the name match reads: no parse reads it (decisions/
#: name-matching, 2026-11-08 FAMILIAR FORMS).
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
    "familiar": "familiar",
}

#: The categories a choice neither prefers nor drops by (`choose`): a
#: name reading keeps a gate on and settles nothing, and a familiar
#: reading moves no parse at all, so neither competes with another
#: file's reading of the word.
UNPREFERRED = frozenset({"name", "familiar"})

#: Behavioral properties per category: each compiles into a field, and
#: its allowed values are exactly what today's pipeline does. A name
#: reading's are `default` (phase 3a), `cased`, the word's case mask
#: (the shipped ones on `family` readings, #1014), `shared`, which
#: rules/P10, O6 and O7 read, and `after_particle`, which P10 and O6 read
#: (#704): its other keys are evidence. A particle reading's
#: `capital_opening` is rules/R12's: the particle takes a capital where
#: it opens the family name, the Armenian `Ter` and `Der`.
BEHAVIORAL: dict[str, frozenset[str]] = {
    "title": frozenset({"abbreviation", "addresses", "after_given",
                        "attached", "attaches", "cased", "default",
                        "dotted"}),
    "suffix": frozenset({"acronym", "attached", "cased", "default",
                         "title_case_is_name"}),
    "particle": frozenset({"capital_opening", "cased", "default"}),
    "conjunction": frozenset({"may_be_initial", "cased", "default"}),
    "bound_given": frozenset({"completed_by", "cased", "default"}),
    "relation": frozenset({"cased", "default"}),
    "name": frozenset({"after_particle", "cased", "default", "shared"}),
    "familiar": frozenset({"default"}),
}

#: The suffix word kinds a name reading gates (rules/S11): the third
#: derived marker reads these, and a name reading beside another word
#: kind marks nothing, no gate reading that clash yet. A credential is
#: here for one written as a word (`acronym = false`), `kc`, `pc` and
#: `dl`, whose dotted spellings must stay the paired initials (#965); a
#: credential acronym's clash is the second marker's.
GATED_WORDS = frozenset({"generation", "agnomen", "credential"})

#: The suffix word kinds rules/R8's `honorifics` view holds: a form of
#: address written after the name (`さん`, `님`, `先生`), which CLDR
#: files as a title; an office written there (`議員`) is a credential
#: (#326).
HONORIFIC_KINDS = frozenset({"honorific", "professional_honorific"})

#: The particle kinds written with a capital, a saint's name (`St Clair`,
#: `San Martín`) and a German rank inside the surname (`Freiherr von
#: Richthofen`): rules/R4's case repair does not lowercase them (#1069).
CAPITALIZED_PARTICLE_KINDS = frozenset({"saint", "rank"})


#: The group a reading's `same_as` is read in, by the reading's
#: category, a name reading's being its kind (`given`, `family`): the
#: roles of a name each read one group (decisions/name-matching,
#: 2026-11-08), so a given name's listed spelling is not a surname's
#: (`ma`, María written short, beside the surname Ma). A bound given
#: name stands in the given name and a particle in the surname, so
#: theirs are read there; a conjunction's and a birth marker's stand in
#: no role a match compares, and compile to no group.
SAME_AS_GROUPS: Mapping[str, str] = MappingProxyType({
    "given": "given",
    "bound_given": "given",
    "family": "family",
    "particle": "family",
    "title": "title",
    "suffix": "suffix",
})


def same_as_group(kind: str) -> str | None:
    """The `SAME_AS` group a `kind` reading's `same_as` compiles into,
    or None where it compiles into none."""
    category = CATEGORY[kind]
    return SAME_AS_GROUPS.get(kind if category == "name" else category)


def indexed(kind: str) -> frozenset[str]:
    """The properties of a `kind` reading the index keeps: its
    category's behavioral ones, and on every kind but `familiar`
    `same_as`, the word a spelling stands for, which compiles into
    SAME_AS (in the group of `same_as_group`) and on a `given` reading
    also into GIVEN_NAME_ABBREVIATIONS (#789); on a `familiar` reading
    `short_for`, the longer given names the word stands for, which
    compiles into FAMILIAR. Everything else a reading carries is
    evidence, compiled to nothing."""
    if CATEGORY[kind] == "familiar":
        return BEHAVIORAL["familiar"] | {"short_for"}
    return BEHAVIORAL[CATEGORY[kind]] | {"same_as"}


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
        """A `may_be_*` flag, `after_given`, `abbreviation`,
        `title_case_is_name`, `shared`, `after_particle`,
        `capital_opening` or `dotted`: unwritten, false."""
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
    keeps of it is its tag, in ``Reading.languages``
    (:func:`languages_of`)."""

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
    what an empty ``Reading.languages`` says; the parse reads the tags
    through :func:`languages_of`, which builds no IndexReading."""
    return tuple(from_row(text, row) for row in _by_text().get(text, ()))


#: The tags no choice names: mul.toml's readings are every language's
#: and und.toml's no known language's, so neither is a language to
#: choose. A plain choice never removes a reading of either (choose); a
#: strict one, which drops every file not chosen, keeps mul.toml's all
#: the same, as it keeps native-script words' readings, and drops
#: und.toml's (:func:`strict_pool`; decisions/vocabulary-model,
#: 2026-11-02 #1005).
UNCHOOSABLE = frozenset({"mul", "und"})


@functools.cache
def tags() -> frozenset[str]:
    """The tags of the shipped files that hold a reading a choice can
    change: any but a familiar one. A plain choice never drops a
    familiar reading, which no parse reads, so a file holding only
    those (`hu.toml`, `mt.toml`, `sq.toml`) would change nothing as a
    plain choice, and is refused as one holding no reading
    (decisions/name-matching, 2026-11-08 FAMILIAR FORMS)."""
    return frozenset(row[0] for rows in _by_text().values() for row in rows
                     if CATEGORY[row[1]] != "familiar")


@functools.cache
def files() -> frozenset[str]:
    """The tags of every shipped vocabulary file, one holding no
    reading (only exclusions) included: :func:`tags` and the files a
    strict choice may name, which a plain one may not."""
    from nameparser.config._index import FILES
    return frozenset(FILES)


def selected(languages: Iterable[str], *,
             strict: bool = False) -> frozenset[str]:
    """The file tags a choice of `languages` selects: each chosen tag's
    own and its ancestors', never its descendants' (``pt-BR`` selects
    ``pt-BR`` and ``pt``; ``pt`` only ``pt``), matched without regard to
    case, as BCP 47 tags are. No macrolanguage table is read: ``ms``
    does not select ``id``.

    A plain choice selects among the files that hold a reading, since a
    file holding none would change nothing; a `strict` one among every
    file, since it drops whatever is not chosen and so is never inert
    (``hu``, whose file holds only exclusions and familiar forms).

    Raises ValueError for ``mul`` or ``und``, and for a tag that selects
    no file at all, naming the tags that do."""
    held = (files() if strict else tags()) - UNCHOOSABLE
    by_fold = {t.casefold(): t for t in held}
    out: set[str] = set()
    for tag in languages:
        if tag.casefold() in UNCHOOSABLE:
            raise ValueError(
                f"{tag!r} is not a language to choose: mul.toml's readings "
                f"are every language's and und.toml's no known language's; "
                f"every choice, plain or strict, keeps mul.toml's, a plain "
                f"one keeps und.toml's too and a strict one drops "
                f"und.toml's. Drop it")
        found = {by_fold[a] for a in _ancestors(tag) if a in by_fold}
        if not found:
            empty = sorted(t for t in files() - tags() - UNCHOOSABLE
                           if t.casefold() in _ancestors(tag))
            if empty:
                raise ValueError(
                    f"{empty[0]}.toml holds no reading a parse reads yet, "
                    f"so a plain choice of {tag!r} would change nothing; a "
                    f"strict one (strict=True) accepts it")
            raise ValueError(
                f"no vocabulary file holds the language {tag!r} or one it "
                f"belongs to; the languages that have one: "
                f"{', '.join(sorted(by_fold.values()))}")
        out |= found
    return frozenset(out)


def _ancestors(tag: str) -> list[str]:
    """`tag` and the tags it belongs to, casefolded, longest first."""
    parts = tag.split("-")
    return ["-".join(parts[:i]).casefold() for i in range(len(parts), 0, -1)]


def choose(readings: Iterable[IndexReading],
           chosen: frozenset[str]) -> list[IndexReading]:
    """The readings a choice of the file tags `chosen` compiles, each
    as :func:`compile_readings` is to read it (decisions/vocabulary-model,
    2026-10-27 #753, items 2 and 7):

    * **turning on**: a chosen file's ``default = false`` readings join
      the readings on by default;
    * **prefer**: on a word where a chosen file holds a vocabulary
      reading (any category but a name), the other files' vocabulary
      readings leave, save mul.toml's, which are every language's, and
      und.toml's, whose language is not known to be another's. Name
      readings never leave and never settle anything (decision 15):
      they keep the gate on; nor do familiar readings, which no parse
      reads (:data:`UNPREFERRED`);
    * **the shape clash**: a chosen file's conjunction reading drops
      ``may_be_initial``, the clash it records being with the initial
      the letter spells, a shape reading, which a preference outranks
      (decision 20).

    With nothing chosen this is the readings on by default, unchanged,
    so the default is the compile of an empty choice."""
    if not chosen:
        return [r for r in readings if r.on_by_default]
    live = [r for r in readings if r.on_by_default or r.tag in chosen]
    preferred = {r.text for r in live
                 if r.tag in chosen and r.category not in UNPREFERRED}
    out = []
    for r in live:
        if (r.text in preferred and r.category not in UNPREFERRED
                and r.tag not in chosen and r.tag not in UNCHOOSABLE):
            continue
        if r.tag in chosen and ("default" in r.props
                                or (r.category == "conjunction"
                                    and "may_be_initial" in r.props)):
            props = {k: v for k, v in r.props.items()
                     if k not in ("default", "may_be_initial")}
            r = IndexReading(r.text, r.tag, r.kind, MappingProxyType(props))
        out.append(r)
    return out


def is_native_script(text: str) -> bool:
    """Whether a strict choice keeps `text` whatever its file: it holds
    a letter and no Latin letter (the CJK honorifics, the Cyrillic and
    Devanagari titles), so it selects itself by script, which is read
    from the word as the parse always reads it. A word with no letter
    (``&``, ``2``) is not native-script."""
    letters = [c for c in text if c.isalpha()]
    return bool(letters) and not any(
        "LATIN" in unicodedata.name(c, "") for c in letters)


def strict_pool(chosen: frozenset[str]) -> list[IndexReading]:
    """The readings a strict choice of the file tags `chosen` compiles
    from, before :func:`choose`: the chosen files' and mul.toml's
    readings and every reading of a native-script word
    (:func:`is_native_script`) whatever file holds it, name readings
    included; no other file's, und.toml's among them
    (file-strict; decisions/vocabulary-model, 2026-10-30, and
    2026-11-02 #1005 for mul.toml)."""
    return strict_kept(index(), chosen)


def strict_kept(readings: Iterable[IndexReading],
                chosen: frozenset[str]) -> list[IndexReading]:
    """The readings of `readings` a strict choice of the file tags
    `chosen` keeps: the chosen files', mul.toml's, which are every
    language's, and native-script ones."""
    return [r for r in readings
            if r.tag in chosen or r.tag == "mul" or is_native_script(r.text)]


def chosen_readings(readings: Iterable[IndexReading], chosen: frozenset[str],
                    strict: bool) -> list[IndexReading]:
    """`readings` under the choice of the file tags `chosen`: under
    `strict` only the chosen files', mul.toml's and native-script ones (as
    :func:`strict_pool` keeps them), then :func:`choose`. What
    :func:`compile_choice` compiles, and what a `Lexicon` under a
    choice reads a word's readings by."""
    return choose(strict_kept(readings, chosen) if strict else readings,
                  chosen)


@functools.cache
def compile_choice(chosen: frozenset[str], strict: bool = False) -> Compiled:
    """The constants the shipped index compiles to under a choice of
    the file tags `chosen` (:func:`selected`'s result), kept per choice:
    a compile costs milliseconds, paid once per choice and only by a
    caller who makes one. An empty plain choice compiles the default; a
    `strict` one compiles from :func:`strict_pool` alone."""
    return compile_readings(chosen_readings(index(), chosen, strict))


def strict_ungated(chosen: frozenset[str]) -> frozenset[str]:
    """The words a strict choice of the file tags `chosen` ungates: a
    chosen file or mul.toml holds the word's vocabulary reading and
    only a dropped file the name reading gating it, so under strict a possibly-given
    particle is never-given, a title only inside a phrase is a title,
    and a suffix gated by the count is not. Compared with the PLAIN
    choice of the same tags, never with the default's markers, which
    miss a reading the choice turns on (decisions/vocabulary-model,
    2026-10-30 #753, file-strict)."""
    plain, strict = compile_choice(chosen), compile_choice(chosen, True)
    out = ((plain["PARTICLES"] - plain["NON_GIVEN_NAME_PARTICLES"])
           & strict["NON_GIVEN_NAME_PARTICLES"])
    out |= plain["TITLES_AMBIGUOUS"] & strict["TITLES"]
    out |= plain["SUFFIX_ACRONYMS_AMBIGUOUS"] & (
        strict["SUFFIX_ACRONYMS"] - strict["SUFFIX_ACRONYMS_AMBIGUOUS"])
    out |= plain["SUFFIX_WORDS_AMBIGUOUS"] & (
        strict["SUFFIX_WORDS"] - strict["SUFFIX_WORDS_AMBIGUOUS"])
    return frozenset(out)


def changed_words(chosen: frozenset[str]) -> frozenset[str]:
    """The words whose compiled readings the choice `chosen` changes:
    every entry that joins or leaves a constant, a title phrase's two
    words among them, and every word whose case mask changes. This is a
    vocabulary choice's deviation surface, derived from the index rather
    than declared by hand (the RFC's "Measuring a pack"): a name holding
    none of these words parses under the choice as under the default."""
    if not chosen:
        return frozenset()
    default, choice = compile_choice(frozenset()), compile_choice(chosen)
    words: set[str] = set()
    for key in default:
        if key in ("SAME_AS", "SAME_AS_NAMED", "FAMILIAR"):
            # a word's listed spelling moves no word between sets, so it
            # changes no parse: a choice's `sr` of `senhor`, not `señor`,
            # and whether the match reads the link written bare; nor does
            # a familiar form, which only the match reads
            continue
        a: Any = default[key]  # type: ignore[literal-required]
        b: Any = choice[key]  # type: ignore[literal-required]
        if isinstance(a, dict):
            words |= {k for k in a.keys() | b.keys() if a.get(k) != b.get(k)}
        else:
            words |= a ^ b
    return frozenset(w for entry in words for w in (entry, *entry.split()))


def languages_of(text: str, kinds: frozenset[str]) -> tuple[str, ...]:
    """The tags of the files holding a reading of `text`, on by
    default, of one of `kinds` (keys of :data:`CATEGORY`), each once,
    in index order; empty for a word no file holds as one of them.
    `text` is normalized as :func:`readings_of` takes it. What
    ``Reading.languages`` holds under the default lexicon, which reads
    it through ``Lexicon._files`` (decisions/vocabulary-model,
    2026-10-29; 2026-11-02, 4i-d); its first call in a process loads
    the index."""
    out: list[str] = []
    for tag, kind, pairs in _by_text().get(text, ()):
        if (kind in kinds and tag not in out
                and ("default", False) not in pairs):
            out.append(tag)
    return tuple(out)


def suffix_kind_of(text: str) -> str | None:
    """The kind of `text`'s suffix reading (a key of :data:`CATEGORY`
    whose category is ``suffix``), on by default or not; None for a
    word no file holds as a suffix. A word has one suffix kind in every
    file (the build's check 4), so the first row says it. `text` is
    normalized as :func:`readings_of` takes it. The shipped files'
    answer only: since 3.0's 4i-b the parse reads a suffix word's kind
    from its own `Lexicon`, which compiles it (GENERATION_WORDS,
    CREDENTIAL_WORDS, HONORIFIC_WORDS), and this agrees with the default's."""
    for _tag, kind, _pairs in _by_text().get(text, ()):
        if CATEGORY[kind] == "suffix":
            return kind
    return None


def holds_kind(text: str, kind: str) -> bool:
    """Whether a file holds `text` in a reading of `kind` (a key of
    :data:`CATEGORY`), on by default or not. `text` is normalized as
    :func:`readings_of` takes it. The shipped files' answer only: since
    3.0's 4i-b the parse reads a particle's patronymic kind from its
    own `Lexicon` (PATRONYMIC_PARTICLES)."""
    return any(k == kind for _tag, k, _pairs in _by_text().get(text, ()))


class CompileError(ValueError):
    """The readings cannot compile: a fact about the data, which the
    build reports as a vocabulary error (exit 2) where any other
    exception from the compiler is an internal one (exit 3)."""


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
    GENERATION_WORDS: frozenset[str]
    CREDENTIAL_WORDS: frozenset[str]
    HONORIFIC_WORDS: frozenset[str]
    PATRONYMIC_PARTICLES: frozenset[str]
    TITLE_ABBREVIATIONS: frozenset[str]
    TITLE_CASE_NAME_WORDS: frozenset[str]
    SHARED_NAMES: frozenset[str]
    PARTICLE_GIVEN_NAMES: frozenset[str]
    SAINT_PARTICLES: frozenset[str]
    CAPITALIZED_PARTICLES: frozenset[str]
    CAPITAL_OPENING_PARTICLES: frozenset[str]
    DOTTED_TITLES: frozenset[str]
    GLUED_TITLES: frozenset[str]
    BOUND_PHRASES: frozenset[str]
    SAME_AS: dict[str, dict[str, tuple[str, ...]]]
    SAME_AS_NAMED: dict[str, frozenset[str]]
    FAMILIAR: dict[str, tuple[str, ...]]


def compile_readings(readings: Iterable[ReadingProperties]) -> Compiled:
    """Fold the readings on by default into the default vocabulary's
    constants. The readings are taken as already checked (the build's
    checks run before it calls this); each needs ``text``, ``kind``
    and ``props``.

    Raises :class:`CompileError` on a post-nominal that is both an
    acronym and a word, a backstop the build's checks 4 and 5 always
    reach first. Any other exception is a bug in this function."""
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
    written_short: set[str] = set()
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
    generations: set[str] = set()
    credential_words: set[str] = set()
    honorific_words: set[str] = set()
    patronymics: set[str] = set()
    saints: set[str] = set()
    capitalized: set[str] = set()
    capital_opening: set[str] = set()
    dotted: set[str] = set()
    glued_titles: set[str] = set()
    title_case_names: set[str] = set()
    shared: set[str] = set()
    after_particle: set[str] = set()
    bound_phrases: set[str] = set()
    cased: dict[str, str] = {}
    same_as: dict[str, dict[str, set[str]]] = {
        g: {} for g in SAME_AS_GROUPS.values()}
    # per name kind, the words a reading of it writes short (`same_as`)
    # and the words it names with none: a name of its own
    short_names: dict[str, set[str]] = {}
    own_names: dict[str, set[str]] = {}
    # a familiar form -> the given names it stands for, every file's
    familiar: dict[str, set[str]] = {}
    for r, t in texts:
        p = r.props
        if r.category == "familiar":
            familiar.setdefault(t, set()).update(p.get("short_for", ()))
            continue
        if "same_as" in p and (group := same_as_group(r.kind)) is not None:
            same_as[group].setdefault(t, set()).add(p["same_as"])
        if r.category == "name":
            into = short_names if "same_as" in p else own_names
            into.setdefault(r.kind, set()).add(t)
        if "cased" in p:
            cased[t] = p["cased"]
        if r.category == "name" and r.flag("shared"):
            shared.add(t)
        if r.kind == "given" and r.flag("after_particle"):
            after_particle.add(t)
        if r.category == "title":
            titles.add(t)
            if r.addresses == "given":
                given_titles.add(t)
            if r.flag("after_given"):
                after_given.add(t)
            if r.flag("dotted"):
                dotted.add(t)
            if "attached" in p:
                # a title reading's side is "before", the build's check
                glued_titles.add(t)
            if r.flag("abbreviation"):
                written_short.add(t)
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
                if r.flag("title_case_is_name"):
                    title_case_names.add(t)
                if r.kind == "agnomen":
                    agnomens.add(t)
                elif r.kind == "generation":
                    generations.add(t)
                elif r.kind == "credential":
                    credential_words.add(t)
                elif r.kind in HONORIFIC_KINDS:
                    honorific_words.add(t)
        elif r.category == "particle":
            particles.add(t)
            if r.kind == "patronymic":
                patronymics.add(t)
            elif r.kind == "saint":
                saints.add(t)
            if r.kind in CAPITALIZED_PARTICLE_KINDS:
                capitalized.add(t)
            if r.flag("capital_opening"):
                capital_opening.add(t)
            if t not in given:
                never_given.add(t)
        elif r.category == "conjunction":
            conjunctions.add(t)
            if r.flag("may_be_initial"):
                initial_conjunctions.add(t)
        elif r.category == "bound_given":
            bound.add(t)
            bound_phrases.update(f"{t} {w}"
                                 for w in p.get("completed_by", ()))
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
        # the kinds the compiled sets above do not record, which the
        # generation, credentials, honorifics and patronymic views read (rules/R8,
        # rules/R9): a suffix WORD's kind, `jr` and `esq` both being in
        # SUFFIX_WORDS, and a particle's. Internal, re-exported by no
        # config module (#754, 4i-b)
        GENERATION_WORDS=frozenset(generations),
        CREDENTIAL_WORDS=frozenset(credential_words),
        HONORIFIC_WORDS=frozenset(honorific_words),
        PATRONYMIC_PARTICLES=frozenset(patronymics),
        # the title readings written short (`abbreviation`), which H5's
        # trailing chain takes where the word may also be a given name
        # (#999); internal, like the kind sets above
        TITLE_ABBREVIATIONS=frozenset(written_short),
        # the suffix words whose Title case is their writing as a name
        # (`fils`, `kc`): of a word gated by a name reading, the one
        # kind whose writing leans (rules/S6, S11, #1039)
        TITLE_CASE_NAME_WORDS=frozenset(title_case_names),
        # the names a community gives every member (Sikh `kaur`,
        # `singh`), no personal or family name of the bearer's own,
        # which the two-name switches neither move nor complete
        # (rules/O6, O7, #704); internal, like the kind sets above
        SHARED_NAMES=frozenset(shared),
        # the given names written behind a particle as the second of a
        # compound given name (`del Carmen`, `de los Ángeles`), which
        # rules/P10 reads as a middle name behind a one-word given name
        # (#704)
        PARTICLE_GIVEN_NAMES=frozenset(after_particle),
        # the particles naming a saint (`san`, `santa`, `st`), which
        # open a place name or a surname (`Santa María`), never a given
        # name's second, so a given name phrase holds none (#704)
        SAINT_PARTICLES=frozenset(saints),
        # the particles of the kinds written with a capital (`St`,
        # `San`, `Freiherr`, `Graf`), which case repair does not
        # lowercase, rules/R4 (#1069)
        CAPITALIZED_PARTICLES=frozenset(capitalized),
        # the particles written `capital_opening` (`ter`, `der`), which
        # case repair writes with a capital where no particle stands
        # before one in the family name, nor, where it opens the family
        # name, written right before it in any role, rules/R12
        CAPITAL_OPENING_PARTICLES=frozenset(capital_opening),
        # the titles written `dotted` (`us`, `uk`, `pd`), which a run of
        # single letters joined by full stops spells at the head of a
        # name where a title the run keeps stands behind it, rules/H10
        DOTTED_TITLES=frozenset(dotted),
        # the titles written `attached` (side "before"), which
        # rules/W6's front peel splits off the start of the name's first
        # word they are glued to (`นายสมชาย`, #317)
        # a title that may be a given name is a title only in a phrase
        # (rules/H9), so none is split off a glued word: the given name
        # it opens would be cut and no title read (#317)
        GLUED_TITLES=frozenset(glued_titles - contested),
        # `completed_by` resolved to the two-word given names it lists,
        # the bound word and each word that completes it ('عبد الله'),
        # which rules/P12 joins wherever they stand (#694)
        BOUND_PHRASES=frozenset(bound_phrases),
        # every reading's `same_as` in the group of its kind: the words
        # it is a listed spelling of (`wm` of `william` among given
        # names, `junior` of `jr` among suffixes, `sr` of both `señor`
        # and `senhor` among titles), which no set above records
        SAME_AS={g: {w: tuple(sorted(heads))
                     for w, heads in sorted(same_as[g].items())}
                 for g in sorted(same_as)},
        # the derived marker of a listed spelling: a word whose name
        # reading carries a `same_as` beside a reading of the same kind
        # with none, a name written short that is a name of its own too
        # (`jo`, José written short and the given name Jo), whose links
        # the name match reads only where the word is written with its
        # period (decisions/name-matching, 2026-11-08 #1006 follow-up).
        # A bound given name's or a particle's `same_as` is a spelling
        # written without one (`ابو` of `أبو`), and marks nothing
        SAME_AS_NAMED={g: frozenset(
            w for k, short in short_names.items()
            if same_as_group(k) == g
            for w in short & own_names.get(k, set()))
            for g in sorted(same_as)},
        # a familiar form and the longer given names it stands for, one
        # way (`max` of `maxim` and `maximilian`, which do not stand for
        # each other), every file's together: read by the name match's
        # opt-in `familiar-form` alone, never by a parse
        # (decisions/name-matching, 2026-11-08 FAMILIAR FORMS)
        FAMILIAR={w: tuple(sorted(longs))
                  for w, longs in sorted(familiar.items())},
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
        raise CompileError(f"{sorted(both)}: a post-nominal is an acronym or a "
                         f"word, never both (check `acronym` in every file)")
    return out
