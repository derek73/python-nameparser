"""Compile nameparser/vocab/*.toml into nameparser/config/_compiled.py.

Usage::

    uv run python tools/vocab/build.py           # rewrite _compiled.py
    uv run python tools/vocab/build.py --check   # exit 1 if it is stale

Either exits 2, printing the failed check, when the vocabulary fails one
or a vocabulary file cannot be read, and 3 on an internal error or a
module it cannot write, so neither is ever mistaken for exit 1's
"stale". An unreadable _compiled.py IS stale, rebuilding replacing it,
and --check reports it so.

The vocabulary is written per word, in one TOML file per BCP 47 language
tag (`und` for words not yet assigned one, `mul` for words shared on
purpose). Each word lists its READINGS -- what it can be read as, keyed by
kind -- and the compiler folds them into the sets the parser reads
(decisions/vocabulary-model). The parser never parses TOML: the build
writes a module of frozenset literals, committed beside the data, and
tests/v2/test_vocab.py fails when the two disagree.

The build checks replace the import-time asserts the data modules used
to carry. Lexicon.__post_init__ still runs on the result, and three
checks repeat one of its own -- 7's case mask, 9, and through 4 and 5
its gate-bypass raise -- so the shipped data fails here, naming the file and
the word, rather than at the first import.
Each raises VocabError naming the word, and the file where one file is
at fault:

1. `schema` present and supported, no unknown key anywhere (a name a
   later phase will use says so), the file name a BCP 47 tag, at least
   one entry in the file;
2. `text` normalized, non-empty, once per file, each word of a phrase
   normalized on its own, and a text some token can equal: no comma or
   nakaguro, no character the tokenizer strips by default (an emoji),
   no interpunct between two East Asian characters, no invisible
   character but the two joiners;
3. every kind registered, every property allowed on its kind with an
   allowed value (a date, never a date-time; `as_of` only beside a
   count), an acronym's text free of periods (it is matched with them
   removed), a `note` on a name reading with no count, saying why it
   is declared, and no entry without a reading or an exclusion;
4. one suffix kind per word, across files;
5. the same category of the same word agrees on every behavioral
   property in every file, whatever kind each file gives it;
6. an excluded kind is absent from every file, along with every other
   kind that compiles to the same set (a name kind refuses only itself),
   and an excluded property never takes a value other than the one it
   has unwritten on a reading of the excluding kind, on any reading of
   its category (`cased`: of the word);
   run before 4 and 5, so the recorded reason is what a contributor sees;
7. `same_as` names another word of the same category, `cased` spells
   its word's letters (#459), at most one `cased` per word;
8. a phrase only as a birth_marker or an addresses = "given" title, and
   never with a `cased`, which is looked up per word;
9. a bound given name that is also a particle has a given reading;
10. no same_as chain loops, in any file, and the words of every file
    but und.toml in canonical order (_order_key): by kind, then by the
    word a spelling is the same_as of, then by text;
11. a clash with a name is stated as a name reading, from which the two
    markers are derived (decisions/vocabulary-model, 2026-10-25):
    `may_be_name` and `may_be_given = true` are refused, each naming
    the reading to write, and a particle reading states
    `may_be_given = false` exactly where its word has no `given`
    reading in any file;

numbered by subject, not by when they run: 1-3, 8, 7's case mask and
11's refusals run per entry as each file loads, and 4-7, 9, 11's
particle statement and 10 over the whole pool in check_pool, 6 first
and 10 last;

plus the data invariants that were asserts: may_be_initial only on a
cased single letter, an elided particle in both apostrophes (#700), and
after_given only on a salutation reading (#835).
No post-nominal is both an acronym and a word, by checks 4 and 5; a
final check in compile_pool is the backstop. The subset relations
(GIVEN_NAME_TITLES and AFTER_GIVEN_TITLES in TITLES, each marker set in
its base) need no
check: a flag cannot exist without its reading, and a derived marker is
read off the reading it marks. The one soft finding, a
name reading on a word with no vocabulary reading and no exclusion, is
a VocabWarning, which the shipped-data test turns into an error.
"""
from __future__ import annotations

import argparse
import datetime
import re
import sys
import tomllib
import traceback
import unicodedata
import warnings
from collections.abc import Iterable, Mapping
from dataclasses import dataclass, field
from pathlib import Path
from types import ModuleType
from typing import Any, TypedDict

ROOT = Path(__file__).resolve().parents[2]
# bound at import like VOCAB and OUTPUT below, so a test repointing ROOT
# at a fixture tree does not move the parser's own module out from under
# a cold _LEXICON cache
_LEXICON_PATH = ROOT / "nameparser" / "_lexicon.py"


def _load_lexicon_module() -> ModuleType:
    """nameparser/_lexicon.py, loaded by path rather than imported.

    Importing it through the package would run nameparser/__init__,
    which imports the config modules and so _compiled.py itself -- and a
    _compiled.py left broken (merge-conflict markers, or a new constant
    the module does not define yet) would then stop the one tool that
    regenerates it. _lexicon imports nothing internal at module level
    (its config imports sit inside _default_lexicon), so it loads on its
    own; tests/v2/test_vocab.py's
    test_the_build_does_not_import_the_package_it_writes holds that."""
    import importlib.util
    spec = importlib.util.spec_from_file_location("_vocab_build_lexicon", _LEXICON_PATH)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    # registered before it runs: its dataclasses look their module up
    sys.modules[spec.name] = module
    try:
        spec.loader.exec_module(module)
    except BaseException:
        del sys.modules[spec.name]
        raise
    return module


_LEXICON: list[ModuleType] = []


def _lexicon() -> ModuleType:
    # loaded at first use, inside main's error handling, so a broken
    # _lexicon.py exits 3 rather than failing the import with exit 1
    if not _LEXICON:
        _LEXICON.append(_load_lexicon_module())
    return _LEXICON[0]


def _normalize(word: str) -> str:
    result: str = _lexicon()._normalize(word)
    return result


def _alnum(text: str) -> str:
    result: str = _lexicon()._alnum(text)
    return result

VOCAB = ROOT / "nameparser" / "vocab"
OUTPUT = ROOT / "nameparser" / "config" / "_compiled.py"
REFRESH = "uv run python tools/vocab/build.py"
#: The folder's reference for editors, the one file read_dir skips by name.
README = "README.md"

#: The format version this compiler reads. A new kind or property is
#: additive and does not bump it; a change to what an existing key means
#: does.
SCHEMA = 1

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
#: The categories a word-level `excluded` may name besides the kinds.
CATEGORIES = frozenset(CATEGORY.values())
#: CATEGORY's order is the canonical order of the kinds, and of the
#: categories by their first kind: check 10 sorts a file's words by it,
#: and the README's kind table lists the kinds in it. A category's kinds
#: are contiguous, so ordering by kind orders by category first.
KIND_ORDER = {kind: i for i, kind in enumerate(CATEGORY)}
_RUNS = [c for i, c in enumerate(CATEGORY.values())
         if i == 0 or c != list(CATEGORY.values())[i - 1]]
assert len(_RUNS) == len(set(_RUNS)), "a category's kinds are listed apart in CATEGORY"
#: The file exempt from check 10: it holds no language's words, only
#: those no language file fits yet (nameparser/vocab/README.md).
UNORDERED = "und.toml"

#: Behavioral properties per category: each compiles into a field, and
#: its allowed values are exactly what today's pipeline does.
BEHAVIORAL: dict[str, frozenset[str]] = {
    "title": frozenset({"addresses", "after_given", "cased"}),
    "suffix": frozenset({"acronym", "attached", "cased"}),
    "particle": frozenset({"cased"}),
    "conjunction": frozenset({"may_be_initial", "cased"}),
    "bound_given": frozenset({"cased"}),
    "relation": frozenset({"cased"}),
}
#: Stated properties per category: compiled to nothing, but held to the
#: word's readings (check 11). A particle states `may_be_given = false`
#: where its word has no given reading, so a new particle never falls to
#: the never-given side unremarked (decisions/vocabulary-collisions C-i).
STATED: dict[str, frozenset[str]] = {
    "particle": frozenset({"may_be_given"}),
}
#: The two markers phase 1 wrote as flags and phase 2 derives from a
#: name reading (check 11), each with the reading that now states it.
DERIVED = {
    "may_be_name": "a `given` or `family` reading on the word",
    "may_be_given": "a `given` reading on the word",
}
#: Descriptive properties: recorded, validated, compiled to nothing.
DESCRIPTIVE = frozenset({"note", "issue", "decided", "expands", "same_as",
                         "native", "gender"})
#: What a name reading (`given`, `family`) may carry.
COUNT_SOURCES = frozenset({"us_census_2010", "us_ssa", "wikidata"})
NAME_KEYS = COUNT_SOURCES | {"as_of", "native", "note", "gender"}
#: The keys of an `excluded` value's table, and of an `attached` table.
EXCLUSION_KEYS = frozenset({"reason", "issue", "decided", "note"})
ATTACHED_KEYS = frozenset({"side", "issue", "decided", "note"})
#: Names a later phase will give meaning to. Writing one now is an error
#: that says so, rather than "unknown", so nothing reads as working.
RESERVED = {
    "default": 3, "prefer": 3, "strict": 3,
    "bare_only": 2, "leading_only": 2, "trailing_only": 2,
    "attaches": 2, "separators": 2,
}
_TAG = re.compile(r"[a-z]{2,3}(-[A-Z][a-z]{3})?(-([A-Z]{2}|[0-9]{3}))?")


class VocabError(ValueError):
    """A build check failed; the message names the file and the word."""


class VocabWarning(UserWarning):
    """A finding that compiles but is probably a mistake."""


@dataclass(frozen=True)
class Reading:
    file: str
    text: str
    kind: str
    props: dict[str, Any]

    @property
    def category(self) -> str:
        return CATEGORY[self.kind]

    # the defaults of the two behavioral properties whose unwritten value
    # is not false, each defined once: checks, compile_pool and
    # _behavior all read them here
    @property
    def acronym(self) -> bool:
        """Matched with its periods removed: unwritten, true only for a
        credential."""
        return bool(self.props.get("acronym", self.kind == "credential"))

    def flag(self, prop: str) -> bool:
        """A `may_be_*` flag or `after_given`: unwritten, false."""
        return bool(self.props.get(prop, False))

    @property
    def addresses(self) -> object:
        """Which name a title addresses: unwritten, the family name. An
        object, not a str, because it is read before check 3 has
        refused a value that is not one of the allowed strings."""
        return self.props.get("addresses", "family")

    def where(self) -> str:
        return f"{self.file}: {self.text!r} {self.kind}"


def _exclusion_where(file: str, text: str, kind: str, prop: str | None) -> str:
    what = f"excluded {kind}" if prop is None else f"{kind} excluded {prop}"
    return f"{file}: {text!r} {what}"


@dataclass(frozen=True)
class Exclusion:
    """A refused reading (`prop` None: `kind` is a kind or a category) or
    a refused property of the `kind` reading the word keeps.
    `props["reason"]` is always a non-empty string: __post_init__
    refuses any other, so _exclusion builds one even from a value with
    no reason and lets the refusal come from here."""
    file: str
    text: str
    kind: str
    prop: str | None
    props: dict[str, Any]  # the value's table: reason, issue, decided, note

    def __post_init__(self) -> None:
        reason = self.props.get("reason")
        if not isinstance(reason, str) or not reason:
            raise VocabError(f"{self.where()}: an exclusion needs a reason, as a "
                             f"string or a table with `reason`")

    @property
    def reason(self) -> str:
        reason: str = self.props["reason"]
        return reason

    def where(self) -> str:
        return _exclusion_where(self.file, self.text, self.kind, self.prop)


@dataclass
class Pool:
    """Every reading and exclusion in the files, in file order."""
    readings: list[Reading] = field(default_factory=list)
    exclusions: list[Exclusion] = field(default_factory=list)
    #: each file's entries as written, for check 10's word order
    entries: dict[str, list[dict[str, Any]]] = field(default_factory=dict)


# ---------------------------------------------------------------- loading
def _reserved_or_unknown(where: str, key: str, allowed: Iterable[str]) -> VocabError:
    if key in RESERVED:
        return VocabError(f"{where}: {key!r} is reserved for phase {RESERVED[key]}; "
                          f"phase 1 gives it no behavior")
    return VocabError(f"{where}: unknown key {key!r}; allowed: {sorted(allowed)}")


def _exclusion(file: str, text: str, kind: str, prop: str | None,
               value: object) -> Exclusion:
    """An `excluded` value: a reason string, or a table with `reason`."""
    where = _exclusion_where(file, text, kind, prop)
    if isinstance(value, str) and value:
        return Exclusion(file, text, kind, prop, {"reason": value})
    if isinstance(value, dict):
        for k in value:
            if k not in EXCLUSION_KEYS:
                raise _reserved_or_unknown(where, k, EXCLUSION_KEYS)
        _check_descriptive(where, value)
        return Exclusion(file, text, kind, prop, value)
    # a bare value that is no reason string: Exclusion's own refusal
    return Exclusion(file, text, kind, prop, {})


def _is_date(value: object) -> bool:
    # tomllib reads a TOML date-time as a datetime, which IS a date to
    # isinstance: a recorded day must not carry an hour it never had
    return isinstance(value, datetime.date) and not isinstance(value, datetime.datetime)


def _check_descriptive(where: str, props: Mapping[str, Any]) -> None:
    for k in ("note", "native"):
        if k in props and not isinstance(props[k], str):
            raise VocabError(f"{where}: {k} must be a string")
    if "issue" in props:
        v = props["issue"]
        vs = v if isinstance(v, list) else [v]
        if not vs or not all(isinstance(i, int) and not isinstance(i, bool) and i > 0
                             for i in vs):
            raise VocabError(f"{where}: issue must be an issue number or a list of them")
    if "decided" in props and not _is_date(props["decided"]):
        raise VocabError(f"{where}: decided must be a TOML date (2026-10-18), "
                         f"not a string or a date-time")
    if "expands" in props:
        v = props["expands"]
        vs = v if isinstance(v, list) else [v]
        if not vs or not all(isinstance(s, str) and s for s in vs):
            raise VocabError(f"{where}: expands must be a string or a list of strings")
    if "gender" in props and props["gender"] not in ("f", "m", "n"):
        raise VocabError(f"{where}: gender must be 'f', 'm' or 'n'")
    if "same_as" in props and not isinstance(props["same_as"], str):
        raise VocabError(f"{where}: same_as must be a text")


def check_file_names(names: Iterable[str]) -> None:
    """Build check 1, the file half: each name a BCP 47 tag in canonical
    case. Canonical case is also what keeps two names from differing only
    by case, which a macOS or Windows checkout cannot hold: of any two
    such names, at most one is canonical."""
    for name in names:
        if not name.endswith(".toml") or not _TAG.fullmatch(name[:-5]):
            raise VocabError(
                f"{name}: a vocabulary file is named for a BCP 47 tag in "
                f"canonical case (pt.toml, pt-BR.toml, zh-Hant.toml), or "
                f"und.toml / mul.toml")


def load(files: Mapping[str, str]) -> Pool:
    """Parse {file name: TOML text} and run the per-entry checks (1-3, 8)."""
    check_file_names(files)
    pool = Pool()
    for name in sorted(files):
        try:
            data = tomllib.loads(files[name])
        except tomllib.TOMLDecodeError as e:
            raise VocabError(f"{name}: not valid TOML: {e}") from None
        schema = data.get("schema")
        if not isinstance(schema, int) or isinstance(schema, bool):
            raise VocabError(f"{name}: needs `schema = {SCHEMA}` at the top")
        if schema > SCHEMA:
            raise VocabError(f"{name}: schema {schema} is newer than this "
                             f"compiler reads ({SCHEMA}); upgrade nameparser")
        if schema != SCHEMA:
            raise VocabError(f"{name}: schema {schema} is not supported")
        for k in data:
            if k not in ("schema", "word"):
                raise _reserved_or_unknown(name, k, ("schema", "word"))
        words = data.get("word", [])
        if not isinstance(words, list):
            raise VocabError(f"{name}: `word` must be an array of tables ([[word]])")
        if not words:
            # a file with the header and nothing else -- a botched move,
            # every entry cut and none pasted -- compiles to nothing
            raise VocabError(f"{name}: no [[word]] entries; delete the file "
                             f"or add its words")
        seen: set[str] = set()
        for entry in words:
            if not isinstance(entry, dict):
                raise VocabError(f"{name}: `word` must be an array of tables ([[word]])")
            _load_entry(name, entry, seen, pool)
        pool.entries[name] = words
    return pool


# ------------------------------------------------------------ word order
def _sort_kind(e: Mapping[str, Any]) -> str:
    """The kind an entry sorts under: the earliest of its vocabulary
    readings in canonical order; else, for an entry that records only a
    refusal (`fils`, `senior`), the earliest kind it excludes, a
    category counting as its first kind; else its earliest name reading.
    A name reading is evidence for something else, so it places the
    entry only alone."""
    kinds = [k for k in e if k in CATEGORY]
    vocabulary = [k for k in kinds if CATEGORY[k] != "name"]
    if vocabulary:
        return min(vocabulary, key=KIND_ORDER.__getitem__)
    refused = [k if k in CATEGORY else next(c for c in CATEGORY if CATEGORY[c] == k)
               for k in e.get("excluded", ())]
    return min(refused or kinds, key=KIND_ORDER.__getitem__)


def _heads(words: Iterable[Mapping[str, Any]]) -> dict[tuple[str, str], str]:
    """Each word's same_as in each category, from one file's entries:
    the same_as of the word's earliest reading of that category that
    carries one. A same_as naming its own word is left out, for check 7
    to refuse, so following these always ends."""
    heads: dict[tuple[str, str], str] = {}
    for e in words:
        for k in sorted((k for k in e if k in CATEGORY), key=KIND_ORDER.__getitem__):
            if e[k].get("same_as") not in (None, e["text"]):
                heads.setdefault((CATEGORY[k], e["text"]), e[k]["same_as"])
    return heads


def _order_key(e: Mapping[str, Any],
               heads: Mapping[tuple[str, str], str]) -> tuple[int, tuple[str, ...]]:
    """Check 10's sort key: the entry's kind (_sort_kind), then its
    same_as PATH -- the word it is a spelling of, that word's own head,
    and so on as far as the file's own entries go, written root first
    and ending in the entry's text. So a head sorts before its spellings
    (`jr`, then `jnr` and `junior`), a spelling's own spellings follow
    it (`el-` under `al-`, then el-'s assimilated forms), and an entry
    with no same_as is a path of one, sorted by its text. Only the
    file's own chains are followed (`heads` is _heads of the file), so
    no other file decides its order. Texts compare by codepoint: they
    are already normalized (check 2), so this is the codepoint order of
    the normalized text, whatever the script -- defined everywhere,
    stable across Python versions and locales, and no one language's
    collation."""
    kind = _sort_kind(e)
    category = CATEGORY[kind]
    path = [e["text"]]
    head = e[kind].get("same_as") if kind in e else None
    if head == path[0]:
        head = None  # check 7's to refuse
    # _heads holds no self-reference and _check_same_as_cycles has
    # refused every longer loop, so this ends
    while head is not None:
        path.append(head)
        head = heads.get((category, head))
    return KIND_ORDER[kind], tuple(reversed(path))


def _check_same_as_cycles(entries: Mapping[str, list[dict[str, Any]]]) -> None:
    """Check 10's first half: no same_as chain loops, in any file,
    und.toml's included, over EVERY same_as written -- a word may name a
    different head in each file or each kind, and a loop through any of
    them is refused, not only through the one a file's order follows."""
    edges: dict[tuple[str, str], set[str]] = {}
    for words in entries.values():
        for e in words:
            for k, v in e.items():
                if k in CATEGORY and "same_as" in v and v["same_as"] != e["text"]:
                    edges.setdefault((CATEGORY[k], e["text"]), set()).add(v["same_as"])
    done: set[tuple[str, str]] = set()
    for start in sorted(edges):
        # depth first, iteratively (a chain can be longer than Python's
        # recursion limit): meeting a word already on the open path is a
        # loop, and the loop is the path from that word on, since a
        # chain may run INTO a loop its first word is not part of
        path = [start]
        todo = [iter(sorted(edges[start]))]
        while path:
            head = next(todo[-1], None)
            if head is None:
                done.add(path.pop())
                todo.pop()
                continue
            node = (start[0], head)
            if node in path:
                loop = [t for _, t in path[path.index(node):]] + [head]
                raise VocabError(f"{head!r} {start[0]}: same_as loops, "
                                 f"{' -> '.join(loop)}; a spelling names the "
                                 f"word it is a spelling of, which does not "
                                 f"name it back")
            if node not in done:
                path.append(node)
                todo.append(iter(sorted(edges.get(node, ()))))


def _misplaced(ranks: list[int]) -> tuple[int, set[int]]:
    """The entry to move and the entries to keep: the first entry
    outside a longest run of entries already in their relative order,
    and that run. Placed against the run, each move the check names
    lengthens it by one, so following the messages takes the fewest
    moves, and a word appended at the end of a file is the one named,
    not the neighbours it displaced. Ties keep the later entries, so of
    two swapped words the first is named."""
    best = [1] * len(ranks)
    prev = [-1] * len(ranks)
    for i in range(len(ranks)):
        for j in range(i):
            if ranks[j] < ranks[i] and best[j] + 1 >= best[i]:
                best[i], prev[i] = best[j] + 1, j
    i = max(range(len(ranks)), key=lambda k: (best[k], k))
    kept = set()
    while i != -1:
        kept.add(i)
        i = prev[i]
    return min(set(range(len(ranks))) - kept), kept


def check_order(entries: Mapping[str, list[dict[str, Any]]]) -> None:
    """Build check 10: no same_as chain loops, and every file but
    und.toml lists its words in _order_key's order. Checked, never
    rewritten: a comment above an entry belongs to it and must move
    with it, which a TOML reader cannot see. Run last, so a file out of
    order is reported only once every other check has passed: a
    contributor sees an exclusion's reason (6) or a same_as typo (7)
    before being told where the entry goes."""
    _check_same_as_cycles(entries)
    for name, words in sorted(entries.items()):
        if name == UNORDERED:
            continue
        heads = _heads(words)
        keys = [_order_key(e, heads) for e in words]
        ordered = sorted(range(len(words)), key=keys.__getitem__)
        if ordered == list(range(len(words))):
            continue
        ranks = [0] * len(words)
        for at, i in enumerate(ordered):
            ranks[i] = at
        m, kept = _misplaced(ranks)
        # its place among the kept entries, which are in order already
        below = [i for i in kept if ranks[i] < ranks[m]]
        kind = _sort_kind(words[m])
        what = kind if kind in words[m] else f"sorted as {kind}, the kind it refuses"
        if below:
            place = f"after {words[max(below, key=ranks.__getitem__)]['text']!r}"
        else:
            above = min(kept, key=ranks.__getitem__)
            place = f"before {words[above]['text']!r}"
        raise VocabError(
            f"{name}: {words[m]['text']!r} ({what}) belongs {place}. A file "
            f"lists its words by kind in the README's table order, then by "
            f"the word a spelling is the same_as of, head first, then by "
            f"text; move the entry with any comment above it ({UNORDERED} "
            f"is exempt)")


#: Hand copies of what the tokenizer divides or strips at under the
#: default Policy (this tool cannot import the pipeline without the
#: package), each held to its source by tests/v2/test_vocab.py, which
#: also sweeps every codepoint the tokenizer ignores.
#:
#: The separators: nameparser/_pipeline/_state.py's COMMA_CHARS and
#: _tokenize.py's _NAME_DOT_SEPARATORS. The main stream divides at both;
#: inside a delimited clause a comma is kept as written (rules/N1), and
#: there rules/M3 reads a marker followed by a comma as no marker, which
#: holds only while the vocabulary stores no comma.
DIVIDERS = frozenset({",", "\u060c", "\uff0c", "\u30fb", "\uff65"})
#: _tokenize.py's _EMOJI_RANGES, stripped under strip_emoji (default on).
EMOJI_RANGES = ((0x1F300, 0x1F64F), (0x1F680, 0x1F6FF),
                (0x2600, 0x26FF), (0x2700, 0x27BF))
#: The spans of nameparser/_policy.py's _SCRIPT_RANGES (Han, Hangul,
#: hiragana, katakana): an interpunct between two of these characters
#: divides the name (rules/T3), anywhere else it is part of the word.
EAST_ASIAN_RANGES = ((0x3005, 0x3006), (0x3400, 0x4DBF), (0x4E00, 0x9FFF),
                     (0xF900, 0xFAFF), (0x20000, 0x323AF), (0xAC00, 0xD7A3),
                     (0x3040, 0x309F), (0x30A0, 0x30FF), (0xFF65, 0xFF9F))
INTERPUNCT = "\u00b7"
#: The format characters a word may hold: the zero-width non-joiner and
#: joiner are spelling in Persian and the Indic scripts, and a token
#: keeps them.
JOINERS = frozenset({"\u200c", "\u200d"})


def _in(ch: str, ranges: tuple[tuple[int, int], ...]) -> bool:
    return any(lo <= ord(ch) <= hi for lo, hi in ranges)


def _check_tokenizable(name: str, text: str) -> None:
    """Build check 2's second half. The normalized-form test passes each
    of these. An emoji and an interpunct between East Asian characters
    match no token under the default Policy; a comma could only match
    inside a delimited clause, where rules/M3 needs the vocabulary to
    hold none; an invisible character is a spelling the file does not
    show; and a phrase word with an edge period is a second spelling of
    the key Lexicon folds it to."""
    for i, ch in enumerate(text):
        if ch in DIVIDERS:
            raise VocabError(
                f"{name}: {text!r} holds {ch!r} (U+{ord(ch):04X}), which the "
                f"tokenizer divides a name at; no vocabulary word holds one")
        if _in(ch, EMOJI_RANGES):
            raise VocabError(
                f"{name}: {text!r} holds U+{ord(ch):04X}, which the tokenizer "
                f"strips by default, so no token can equal it")
        if (ch == INTERPUNCT and 0 < i < len(text) - 1
                and _in(text[i - 1], EAST_ASIAN_RANGES)
                and _in(text[i + 1], EAST_ASIAN_RANGES)):
            raise VocabError(
                f"{name}: {text!r} holds an interpunct between two East Asian "
                f"characters, where the tokenizer divides the name (rules/T3), "
                f"so no token can equal it")
        category = unicodedata.category(ch)
        if (category == "Cf" and ch not in JOINERS) or category == "Cc":
            # a bidi mark is stripped by default; a zero-width space, word
            # joiner, BOM or control character is kept but unseen, so the
            # entry reads as the word without it and matches only text
            # carrying the same invisible character
            raise VocabError(
                f"{name}: {text!r} holds the invisible character "
                f"U+{ord(ch):04X} ({unicodedata.name(ch, 'a control character')}); "
                f"remove it")
    if " " in text:
        # Lexicon folds each word of a phrase on its own (_title_key), so
        # 'z. domu' is stored and matched as 'z domu': the entry works,
        # but the compiled set would hold a spelling Lexicon never keeps.
        # One key, one spelling, as check 2 asks of every text
        words = [_normalize(w) for w in text.split(" ")]
        if " ".join(words) != text:
            raise VocabError(
                f"{name}: phrase {text!r} is not in normalized form, which "
                f"folds each word; write {' '.join(w for w in words if w)!r}")


def _load_entry(name: str, e: dict[str, Any], seen: set[str], pool: Pool) -> None:
    text = e.get("text")
    if not isinstance(text, str) or not text:
        raise VocabError(f"{name}: an entry needs a non-empty `text`, got {text!r}")
    if _normalize(text) != text or " ".join(text.split()) != text:
        raise VocabError(
            f"{name}: text {text!r} is not in normalized form; write "
            f"{' '.join(_normalize(text).split())!r} (lowercase, NFC, no edge "
            f"periods, single-spaced)")
    _check_tokenizable(name, text)
    if text in seen:
        raise VocabError(f"{name}: {text!r} is listed twice in one file")
    seen.add(text)
    where = f"{name}: {text!r}"
    has_reading = False
    for key, value in e.items():
        if key == "text":
            continue
        if key == "excluded":
            if not isinstance(value, dict) or not value:
                raise VocabError(f"{where}: excluded must be a table of kinds")
            for kind, why in value.items():
                if kind not in CATEGORY and kind not in CATEGORIES:
                    raise VocabError(f"{where}: excluded names unknown kind {kind!r}")
                pool.exclusions.append(_exclusion(name, text, kind, None, why))
            continue
        if key not in CATEGORY:
            if key in DESCRIPTIVE:
                raise VocabError(f"{where}: {key!r} belongs on a reading, not the word")
            raise _reserved_or_unknown(where, key, set(CATEGORY) | {"text", "excluded"})
        if not isinstance(value, dict):
            raise VocabError(f"{where}: reading {key!r} must be a table "
                             f"({key} = {{}}), never a bare value")
        has_reading = True
        _check_reading(Reading(name, text, key, value), pool)
    if not has_reading and not any(x.text == text and x.file == name
                                   for x in pool.exclusions):
        raise VocabError(f"{where}: an entry with no reading and no exclusion is inert")


def _check_reading(r: Reading, pool: Pool) -> None:
    where = r.where()
    p = r.props
    if r.category == "name":
        for k in p:
            if k not in NAME_KEYS:
                raise _reserved_or_unknown(where, k, NAME_KEYS)
        for src in COUNT_SOURCES & p.keys():
            if not isinstance(p[src], int) or isinstance(p[src], bool) or p[src] < 1:
                raise VocabError(f"{where}: {src} must be a positive count "
                                 f"(absent means below the source's floor)")
        if COUNT_SOURCES & p.keys() and "as_of" not in p:
            raise VocabError(f"{where}: a count needs `as_of`, a TOML date")
        if "as_of" in p and not _is_date(p["as_of"]):
            raise VocabError(f"{where}: as_of must be a TOML date (2026-10-16), "
                             f"not a string or a date-time")
        if "as_of" in p and not COUNT_SOURCES & p.keys():
            raise VocabError(f"{where}: as_of dates a count, and this reading "
                             f"has none ({', '.join(sorted(COUNT_SOURCES))})")
        if not COUNT_SOURCES & p.keys() and "note" not in p:
            # a name reading may stand without a count -- a particle kept
            # possibly given under C-i's default, with no source counting
            # it -- but says why, so an unexamined word stays findable
            raise VocabError(f"{where}: a name reading with no count needs a "
                             f"`note` saying why it is declared")
        _check_descriptive(where, p)
        pool.readings.append(r)
        return
    stated = STATED.get(r.category, frozenset())
    allowed = BEHAVIORAL[r.category] | stated | DESCRIPTIVE | {"excluded"}
    for k in p:
        if k in stated and not isinstance(p[k], bool):
            raise VocabError(f"{where}: {k} must be true or false")
        if k in DERIVED and not (k in stated and p[k] is False):
            # build check 11: the marker is derived from a name reading
            raise VocabError(f"{where}: {k} = {_shown(p[k])} is derived since "
                             f"phase 2; write {DERIVED[k]} instead, with dated "
                             f"counts from tools/name_usage.py or a `note` "
                             f"saying why")
        if k not in allowed:
            raise _reserved_or_unknown(where, k, allowed)
    _check_descriptive(where, p)
    for flag in ("acronym", "may_be_initial", "after_given"):
        if flag in p and not isinstance(p[flag], bool):
            raise VocabError(f"{where}: {flag} must be true or false")
    if r.category == "title":
        addresses = r.addresses
        if addresses in ("full", "any"):
            raise VocabError(f"{where}: addresses = {addresses!r} is reserved "
                             f"for a later phase; phase 1 has 'family' and 'given'")
        if addresses not in ("family", "given"):
            raise VocabError(f"{where}: addresses must be 'family' or 'given'")
        if r.flag("after_given") and r.kind != "salutation":
            # a salutation is a form of address, where an office or a
            # rank is borne as a middle name: the reason the given
            # part's end may read one as a title (decisions/H8, #835)
            raise VocabError(f"{where}: after_given is allowed on a "
                             f"salutation reading only, not on {r.kind!r} "
                             f"(rules/H8)")
    if r.category == "suffix":
        acronym = r.acronym
        if acronym and "." in r.text:
            # suffix_as_written looks an acronym up with EVERY period
            # removed, so a dotted entry is never matched -- and it slips
            # past the per-text checks beside its undotted twin
            raise VocabError(
                f"{where}: an acronym is matched with every period removed, "
                f"so {r.text!r} can never match; write "
                f"{r.text.replace('.', '')!r} (it reads the dotted spelling too)")
        if "attached" in p:
            att = p["attached"]
            if not isinstance(att, dict):
                raise VocabError(f"{where}: attached must be a table")
            for k in att:
                if k not in ATTACHED_KEYS:
                    raise _reserved_or_unknown(f"{where} attached", k, ATTACHED_KEYS)
            if att.get("side") != "after":
                raise VocabError(f"{where}: attached supports only side = 'after' "
                                 f"in phase 1 (the #308 peel)")
            if acronym:
                raise VocabError(f"{where}: attached needs a word reading "
                                 f"(acronym = false); the peel splits word tails")
            _check_descriptive(f"{where} attached", att)
    if r.category == "conjunction" and r.flag("may_be_initial"):
        if len(r.text) != 1 or r.text.upper() == r.text.lower():
            raise VocabError(
                f"{where}: may_be_initial needs a CASED single letter; the "
                f"fork reads only a cased one-letter token, so this is inert")
    if "cased" in p:
        cased = p["cased"]
        if " " in r.text:
            # capitalization_exceptions is looked up one word at a time
            raise VocabError(f"{where}: cased is looked up per word, so a "
                             f"phrase's is never read; put it on each word")
        if not isinstance(cased, str) or _alnum(_normalize(cased)) != _alnum(r.text):
            raise VocabError(f"{where}: cased {cased!r} must spell {r.text!r}'s "
                             f"letters and digits, recased (a case mask, #459)")
    if "excluded" in p:
        refused = p["excluded"]
        if not isinstance(refused, dict) or not refused:
            raise VocabError(f"{where}: excluded must be a table of properties")
        for prop, why in refused.items():
            if prop not in BEHAVIORAL[r.category]:
                raise VocabError(f"{where}: excluded names {prop!r}, which is not "
                                 f"a behavioral property of a {r.category}")
            # a refused property set on this same reading is caught by
            # check 6 with the rest of the pool
            pool.exclusions.append(_exclusion(r.file, r.text, r.kind, prop, why))
    # build check 8: a phrase is matched whole only as a given-addressing
    # title run or a birth marker; anywhere else it can never match
    if " " in r.text and not (r.kind == "birth_marker" or (
            r.category == "title" and r.addresses == "given")):
        raise VocabError(f"{where}: a phrase can never match as a {r.kind}; "
                         f"only birth_marker and addresses = 'given' titles are "
                         f"matched as a whole run")
    pool.readings.append(r)


def _refused_by(r: Reading, excluded: str) -> bool:
    """Whether a word-level exclusion of `excluded` refuses reading r.

    A category name refuses every reading of the category (`excluded =
    { suffix = ... }`). A kind refuses every reading of that kind, whatever
    its properties, and also every OTHER kind that compiles into the set
    the excluded kind would, written with its defaults: refusing
    `generation` refuses a generic `suffix = {}` and a `status = {}`, either
    of which would put the word in the very set the recorded reason keeps
    it out of. In the suffix category `acronym` splits the kinds between
    two sets. The name kinds compile to nothing and mean opposite things
    (a word refused as a given name may well be a surname), so there a
    kind refuses only itself."""
    if excluded in CATEGORIES:
        return r.category == excluded
    if r.kind == excluded:
        return True
    if CATEGORY[excluded] != r.category or r.category == "name":
        return False
    return r.category != "suffix" or r.acronym == (excluded == "credential")


def _shown(value: object) -> str:
    """A property value as TOML writes it, for a refusal message."""
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, str):
        return f'"{value}"'
    if isinstance(value, dict):
        return "{ " + ", ".join(f"{k} = {_shown(v)}" for k, v in value.items()) + " }"
    if isinstance(value, datetime.date):
        return value.isoformat()
    return repr(value)


def _overrides(r: Reading, x: Exclusion) -> bool:
    """Whether r gives x's property a value other than the one it takes
    UNWRITTEN ON A READING OF x's KIND -- what a property exclusion
    refuses. The baseline is the excluding kind's, not r's: in the suffix
    category `acronym` is unwritten-true for a credential and
    unwritten-false for every other kind, so an exclusion of a
    credential's `acronym` refuses a generic `suffix = {}` (a word, where
    the exclusion keeps the acronym) and lets `suffix = { acronym = true }`
    through. Writing the baseline (`after_given = false`) is the same as
    omitting it."""
    assert x.prop is not None
    baseline = Reading(x.file, x.text, x.kind, {})
    return _behavior(r, x.prop) != _behavior(baseline, x.prop)


# ------------------------------------------------------------- compiling
def check_pool(pool: Pool) -> None:
    """The cross-file build checks (4-7, 9, 10 last) and the data invariants."""
    by_text: dict[str, list[Reading]] = {}
    for r in pool.readings:
        by_text.setdefault(r.text, []).append(r)

    # 6: an excluded kind is absent from the whole pool, and an excluded
    # property never takes a value other than the one it has unwritten on
    # a reading of the excluding kind (_overrides) --
    # run first, so a contributor adding a refused reading meets the
    # recorded reason rather than check 4's or 5's complaint about it.
    # A refused property holds over every kind of its category, the sets
    # it feeds being sets of WORDS (a second suffix kind would be refused
    # by check 4 anyway, but without the reason), and `cased`, compiled
    # once per word whatever the reading, over every reading of the word
    for x in pool.exclusions:
        for r in by_text.get(x.text, ()):
            if x.prop is None and _refused_by(r, x.kind):
                raise VocabError(f"{r.where()}: {x.kind} is excluded for "
                                 f"{x.text!r} in {x.file}: {x.reason}")
            if (x.prop is not None
                    and (r.category == CATEGORY[x.kind] or x.prop == "cased")
                    and _overrides(r, x)):
                # the value r actually takes, written or not: the refused one
                value = r.props[x.prop] if x.prop in r.props else _behavior(r, x.prop)
                raise VocabError(
                    f"{r.where()}: {x.prop} = {_shown(value)} is excluded for "
                    f"{x.text!r} in {x.file}: {x.reason}")

    # 4: one suffix kind per word, across files
    for text, rs in by_text.items():
        kinds = sorted({r.kind for r in rs if r.category == "suffix"})
        if len(kinds) > 1:
            raise VocabError(f"{text!r}: one suffix kind per word, got {kinds} "
                             f"({', '.join(sorted({r.file for r in rs}))})")

    # 5: the same category of the same word agrees on every behavioral
    # property in every file -- the default loads them all, so a word
    # cannot read two ways (per-language behavior is phase 3's). Keyed
    # on the CATEGORY, not the kind: the sets are sets of words, and a
    # particle may take a different kind in each language (`de`, a
    # preposition in French and an article in Dutch), and two kinds
    # disagreeing on a property would compile silently to one of them
    for text, rs in by_text.items():
        first: dict[str, Reading] = {}
        for r in rs:
            if r.category == "name":
                continue
            seen = first.setdefault(r.category, r)
            for prop in BEHAVIORAL[r.category]:
                a, b = _behavior(seen, prop), _behavior(r, prop)
                if a != b:
                    raise VocabError(
                        f"{text!r} {r.kind}: {prop} is {a!r} in {seen.file} "
                        f"but {b!r} in {r.file}; one word reads one way")

    # 7: same_as names another word of the same category; one cased
    # per word
    for r in pool.readings:
        target = r.props.get("same_as")
        if target == r.text:
            raise VocabError(f"{r.where()}: same_as names the word itself; it "
                             f"names the word this one is a spelling of")
        if target is not None and not any(
                t.category == r.category for t in by_text.get(target, ())):
            raise VocabError(f"{r.where()}: same_as {target!r} has no "
                             f"{r.category} reading")
    for text, rs in by_text.items():
        masks = {r.props["cased"] for r in rs if "cased" in r.props}
        if len(masks) > 1:
            raise VocabError(f"{text!r}: one cased mask per word, got {sorted(masks)}")

    # 11, the pool's half: a particle reading states may_be_given = false
    # exactly where its word has no given reading in any file. Stated,
    # never defaulted: the old encoding listed the never-given particles,
    # so a new one was ambiguous unless argued otherwise
    # (decisions/vocabulary-collisions C-i), and a default here would
    # silently pick one side of that; a false beside a given reading
    # would say the opposite of the marker it derives
    given = {t for t, rs in by_text.items() if any(r.kind == "given" for r in rs)}
    for r in pool.readings:
        if r.category != "particle":
            continue
        if r.text in given and "may_be_given" in r.props:
            raise VocabError(f"{r.where()}: may_be_given = false contradicts "
                             f"the word's given reading, which derives it; "
                             f"drop the property")
        if r.text not in given and "may_be_given" not in r.props:
            raise VocabError(f"{r.where()}: a particle states may_be_given = "
                             f"false, or its word carries a given reading; "
                             f"under uncertainty, the given reading "
                             f"(vocabulary-collisions C-i)")

    # 9: a bound given name that is also a particle must be one that may
    # be given -- the bound join reads it as a given name. Lexicon raises
    # on the same contradiction; this says which file and word
    for text, rs in by_text.items():
        if any(r.kind == "bound_given" for r in rs) and text not in given:
            for r in rs:
                if r.category == "particle":
                    raise VocabError(f"{r.where()}: also a bound given name, so "
                                     f"the word needs a given reading")

    # an elided particle reads only the apostrophe it is spelled with,
    # nothing folding U+2019 to U+0027, so both spellings ship (#700)
    particles = {r.text for r in pool.readings if r.category == "particle"}
    for text in sorted(particles):
        for a, b in (("’", "'"), ("'", "’")):
            if a in text and text.replace(a, b) not in particles:
                raise VocabError(f"{text!r}: an elided particle needs its ASCII "
                                 f"and its U+2019 spelling; add "
                                 f"{text.replace(a, b)!r}")

    # 10: no same_as loop, and each file but und.toml in word order --
    # last, so every other refusal is seen first
    check_order(pool.entries)

    # soft: a name reading compiles to nothing, so one on a word with no
    # vocabulary reading and no exclusion anywhere -- an exclusion's
    # evidence is what a name reading usually is -- informs nothing
    excluded_texts = {x.text for x in pool.exclusions if x.prop is None}
    for text, rs in by_text.items():
        if all(r.category == "name" for r in rs) and text not in excluded_texts:
            warnings.warn(f"{rs[0].where()}: a name reading on a word with no "
                          f"vocabulary reading is inert", VocabWarning, stacklevel=2)


def _behavior(r: Reading, prop: str) -> object:
    if prop == "acronym":
        return r.acronym
    if prop == "addresses":
        return r.addresses
    if prop == "attached":
        att = r.props.get("attached")
        return None if att is None else att.get("side")
    if prop == "may_be_initial" or prop == "after_given":
        return r.flag(prop)
    return r.props.get(prop)


#: The constants _compiled.py defines, in its order, each with the
#: nameparser.config module that re-exports it.
CONSTANTS = (
    ("GIVEN_NAME_TITLES", "titles"),
    ("TITLES", "titles"),
    ("AFTER_GIVEN_TITLES", "titles"),
    ("NON_GIVEN_NAME_PARTICLES", "particles"),
    ("PARTICLES", "particles"),
    ("CONJUNCTIONS", "conjunctions"),
    ("CONJUNCTIONS_AMBIGUOUS", "conjunctions"),
    ("BOUND_GIVEN_NAMES", "bound_given_names"),
    ("MAIDEN_MARKERS", "maiden_markers"),
    ("SUFFIX_WORDS", "suffixes"),
    ("GLUED_HONORIFICS", "suffixes"),
    ("SUFFIX_ACRONYMS_AMBIGUOUS", "suffixes"),
    ("SUFFIX_ACRONYMS", "suffixes"),
    ("CAPITALIZATION_EXCEPTIONS", "capitalization"),
)


class Compiled(TypedDict):
    """What compile_pool returns: one key per constant, in CONSTANTS
    order, typed as _compiled.py declares it."""
    GIVEN_NAME_TITLES: frozenset[str]
    TITLES: frozenset[str]
    AFTER_GIVEN_TITLES: frozenset[str]
    NON_GIVEN_NAME_PARTICLES: frozenset[str]
    PARTICLES: frozenset[str]
    CONJUNCTIONS: frozenset[str]
    CONJUNCTIONS_AMBIGUOUS: frozenset[str]
    BOUND_GIVEN_NAMES: frozenset[str]
    MAIDEN_MARKERS: frozenset[str]
    SUFFIX_WORDS: frozenset[str]
    GLUED_HONORIFICS: frozenset[str]
    SUFFIX_ACRONYMS_AMBIGUOUS: frozenset[str]
    SUFFIX_ACRONYMS: frozenset[str]
    CAPITALIZATION_EXCEPTIONS: dict[str, str]


# the one tie between the two: mypy holds compile_pool to Compiled's
# keys, and this holds Compiled's keys to the roster render writes
assert tuple(Compiled.__annotations__) == tuple(name for name, _ in CONSTANTS), (
    "Compiled and CONSTANTS list different constants")


def compile_pool(pool: Pool) -> Compiled:
    """Fold the readings into today's constants."""
    check_pool(pool)
    # the two derived markers (check 11): a clash with a name is a word's
    # name reading beside the reading it clashes with
    named = {r.text for r in pool.readings if r.category == "name"}
    given = {r.text for r in pool.readings if r.kind == "given"}
    titles: set[str] = set()
    given_titles: set[str] = set()
    after_given: set[str] = set()
    particles: set[str] = set()
    never_given: set[str] = set()
    conjunctions: set[str] = set()
    initial_conjunctions: set[str] = set()
    bound: set[str] = set()
    markers: set[str] = set()
    words: set[str] = set()
    glued: set[str] = set()
    ambiguous: set[str] = set()
    acronyms: set[str] = set()
    cased: dict[str, str] = {}
    for r in pool.readings:
        t, p = r.text, r.props
        if "cased" in p:
            cased[t] = p["cased"]
        if r.category == "title":
            titles.add(t)
            if r.addresses == "given":
                given_titles.add(t)
            if r.flag("after_given"):
                after_given.add(t)
        elif r.category == "suffix":
            if r.acronym:
                acronyms.add(t)
                if t in named:
                    ambiguous.add(t)
            else:
                words.add(t)
                if "attached" in p:
                    glued.add(t)
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
    out = Compiled(
        GIVEN_NAME_TITLES=frozenset(given_titles),
        TITLES=frozenset(titles),
        AFTER_GIVEN_TITLES=frozenset(after_given),
        NON_GIVEN_NAME_PARTICLES=frozenset(never_given),
        PARTICLES=frozenset(particles),
        CONJUNCTIONS=frozenset(conjunctions),
        CONJUNCTIONS_AMBIGUOUS=frozenset(initial_conjunctions),
        BOUND_GIVEN_NAMES=frozenset(bound),
        MAIDEN_MARKERS=frozenset(markers),
        SUFFIX_WORDS=frozenset(words),
        GLUED_HONORIFICS=frozenset(glued),
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
    # unreachable -- check 4 refuses two suffix kinds on one word, check 5
    # one kind with `acronym` differing between files, and check 2 a word
    # twice in one file -- so this is a backstop kept because it costs one
    # set intersection, not a check any input reaches today.
    both = out["SUFFIX_ACRONYMS"] & out["SUFFIX_WORDS"]
    if both:
        raise VocabError(f"{sorted(both)}: a post-nominal is an acronym or a "
                         f"word, never both (check `acronym` in every file)")
    return out


def read_dir(path: Path = VOCAB) -> dict[str, str]:
    """Every file in the vocabulary folder, by name. Every entry but a
    dotfile and README.md, the folder's reference, is read, so a
    misnamed one (EN.TOML, en.toml.orig, readme.md) reaches check 1's
    file-name check instead of being skipped, and a missing or empty
    folder is an error rather than an empty vocabulary."""
    if not path.is_dir():
        raise VocabError(f"{path}: no vocabulary folder there")
    files = {}
    for f in sorted(path.iterdir()):
        if f.name.startswith(".") or f.name == README:
            continue
        if f.is_symlink() and not f.exists():
            raise VocabError(f"{f.name}: a link to nothing ({f.readlink()})")
        if not f.is_file():
            raise VocabError(f"{f.name}: the vocabulary folder holds no subfolders; "
                             f"a file there would not be read")
        try:
            files[f.name] = f.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError) as e:
            raise VocabError(f"{f.name}: cannot be read as UTF-8 text: {e}") from None
    if not files:
        raise VocabError(f"{path}: no vocabulary files; compiling would write an "
                         f"empty vocabulary")
    return files


def compile_files(files: Mapping[str, str]) -> Compiled:
    return compile_pool(load(files))


# --------------------------------------------------------------- output
HEADER = f'''"""The compiled vocabulary. GENERATED from nameparser/vocab/*.toml by
tools/vocab/build.py -- do not edit; edit the TOML and run

    {REFRESH}

The public names are re-exported, with their documentation, by the
nameparser.config modules (titles, particles, suffixes, ...).
"""
'''


def render(compiled: Compiled) -> str:
    """One sorted entry per line, so a one-word change is a one-line diff."""
    out = [HEADER]
    # a TypedDict is read by literal key; the roster loop reads it as
    # the Mapping it also is
    values: Mapping[str, object] = compiled
    for name, _ in CONSTANTS:
        v = values[name]
        out.append("")
        if isinstance(v, dict):
            out.append(f"{name}: dict[str, str] = {{")
            out += [f"    {k!r}: {v[k]!r}," for k in sorted(v)]
            out.append("}")
        else:
            assert isinstance(v, frozenset), (name, type(v))
            out.append(f"{name}: frozenset[str] = frozenset({{")
            out += [f"    {w!r}," for w in sorted(v)]
            out.append("})")
    return "\n".join(out) + "\n"


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--check", action="store_true",
                    help="exit 1 if the committed module is stale "
                         "(2 if the vocabulary fails a check, 3 on an "
                         "internal error)")
    args = ap.parse_args(argv)
    try:
        return _run(check=args.check)
    except (VocabError, VocabWarning) as e:
        # exit 2, not 1: a script must tell broken data from a stale module
        # (a VocabWarning arrives here raised, under -W error)
        print(f"vocabulary error: {e}", file=sys.stderr)
        return 2
    except Exception:
        # a bug in the compiler, or a module it could not write: still
        # never exit 1
        traceback.print_exc()
        return 3


def _run(*, check: bool) -> int:
    text = render(compile_files(read_dir()))
    try:
        current: str | None = OUTPUT.read_text(encoding="utf-8") if OUTPUT.exists() else ""
    except (OSError, UnicodeDecodeError):
        # an unreadable module is stale in the one sense that matters:
        # rebuilding replaces it
        current = None
    name = OUTPUT.relative_to(ROOT)
    if check:
        if current != text:
            state = "stale" if current is not None else "unreadable"
            print(f"{name} is {state}; run: {REFRESH}")
            return 1
        print(f"{name} is current")
        return 0
    if current == text:
        print(f"{name} is current")
    else:
        OUTPUT.write_text(text, encoding="utf-8")
        print(f"wrote {name}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
