"""Compile nameparser/vocab/*.toml into nameparser/config/_compiled.py.

Usage::

    uv run python tools/vocab/build.py           # rewrite _compiled.py
    uv run python tools/vocab/build.py --check   # exit 1 if it is stale

The vocabulary is written per word, in one TOML file per BCP 47 language
tag (`und` for words not yet assigned one, `mul` for words shared on
purpose). Each word lists its READINGS -- what it can be read as, keyed by
kind -- and the compiler folds them into the sets the parser reads
(decisions/vocabulary-model). The parser never parses TOML: the build
writes a module of frozenset literals, committed beside the data, and
tests/v2/test_vocab.py fails when the two disagree.

The build checks below replace the import-time asserts the data modules
used to carry. Each raises VocabError naming the file and the word; the
one soft finding (a name reading on a word with no vocabulary reading)
is a VocabWarning, which the shipped-data test turns into an error.
"""
from __future__ import annotations

import argparse
import datetime
import re
import sys
import tomllib
import warnings
from collections.abc import Iterable, Mapping
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from nameparser._lexicon import _alnum, _normalize

ROOT = Path(__file__).resolve().parents[2]
VOCAB = ROOT / "nameparser" / "vocab"
OUTPUT = ROOT / "nameparser" / "config" / "_compiled.py"
REFRESH = "uv run python tools/vocab/build.py"

#: The format version this compiler reads. A new kind or property is
#: additive and does not bump it; a change to what an existing key means
#: does.
SCHEMA = 1

#: kind -> category. The category decides which compiled field a reading
#: feeds. A generic category key is itself a kind (`title = {}`: a title
#: not yet classified), so classifying a word later moves no set. Kind
#: names are unique across categories; a fine kind arrives with its
#: category's classification, in a core PR, as one row here.
CATEGORY: dict[str, str] = {
    "title": "title",
    "suffix": "suffix",
    "generation": "suffix",
    "credential": "suffix",
    "honorific": "suffix",
    "professional_honorific": "suffix",
    "status": "suffix",
    "courtesy": "suffix",
    "particle": "particle",
    "conjunction": "conjunction",
    "bound_given": "bound_given",
    "birth_marker": "relation",
    "given": "name",
    "family": "name",
}
#: The categories a word-level `excluded` may name besides the kinds.
CATEGORIES = frozenset(CATEGORY.values())

#: Behavioral properties per category: each compiles into a field, and
#: its allowed values are exactly what today's pipeline does.
BEHAVIORAL: dict[str, frozenset[str]] = {
    "title": frozenset({"addresses", "cased"}),
    "suffix": frozenset({"acronym", "may_be_name", "attached", "cased"}),
    "particle": frozenset({"may_be_given", "cased"}),
    "conjunction": frozenset({"may_be_initial", "cased"}),
    "bound_given": frozenset({"cased"}),
    "relation": frozenset({"cased"}),
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


@dataclass
class Reading:
    file: str
    text: str
    kind: str
    props: dict[str, Any]

    @property
    def category(self) -> str:
        return CATEGORY[self.kind]

    def where(self) -> str:
        return f"{self.file}: {self.text!r} {self.kind}"


@dataclass
class Exclusion:
    """A refused reading (`prop` None: `kind` is a kind or a category) or
    a refused property of the `kind` reading the word keeps."""
    file: str
    text: str
    kind: str
    prop: str | None
    reason: str
    props: dict[str, Any]  # the value's table: reason, issue, decided, note

    def where(self) -> str:
        what = f"excluded {self.kind}" if self.prop is None else f"{self.kind} excluded {self.prop}"
        return f"{self.file}: {self.text!r} {what}"


@dataclass
class Pool:
    """Every reading and exclusion in the files, in file order."""
    readings: list[Reading] = field(default_factory=list)
    exclusions: list[Exclusion] = field(default_factory=list)


# ---------------------------------------------------------------- loading
def _reserved_or_unknown(where: str, key: str, allowed: Iterable[str]) -> VocabError:
    if key in RESERVED:
        return VocabError(f"{where}: {key!r} is reserved for phase {RESERVED[key]}; "
                          f"phase 1 gives it no behavior")
    return VocabError(f"{where}: unknown key {key!r}; allowed: {sorted(allowed)}")


def _exclusion(file: str, text: str, kind: str, prop: str | None,
               value: object) -> Exclusion:
    """An `excluded` value: a reason string, or a table with `reason`."""
    ex = Exclusion(file, text, kind, prop, "", {})
    if isinstance(value, str) and value:
        ex.reason, ex.props = value, {"reason": value}
        return ex
    if isinstance(value, dict):
        for k in value:
            if k not in EXCLUSION_KEYS:
                raise _reserved_or_unknown(ex.where(), k, EXCLUSION_KEYS)
        _check_descriptive(ex.where(), value)
        reason = value.get("reason")
        if isinstance(reason, str) and reason:
            ex.reason, ex.props = reason, value
            return ex
    raise VocabError(f"{ex.where()}: an exclusion needs a reason, as a "
                     f"string or a table with `reason`")


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
    if "decided" in props and not isinstance(props["decided"], datetime.date):
        raise VocabError(f"{where}: decided must be a TOML date (2026-10-18), not a string")
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
    case, and no two differing only by case (a macOS or Windows checkout
    cannot hold both)."""
    seen: dict[str, str] = {}
    for name in names:
        if not name.endswith(".toml") or not _TAG.fullmatch(name[:-5]):
            raise VocabError(
                f"{name}: a vocabulary file is named for a BCP 47 tag in "
                f"canonical case (pt.toml, pt-BR.toml, zh-Hant.toml), or "
                f"und.toml / mul.toml")
        fold = name.lower()
        if fold in seen:
            raise VocabError(f"{name} and {seen[fold]} differ only by case")
        seen[fold] = name


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
        seen: set[str] = set()
        for entry in words:
            if not isinstance(entry, dict):
                raise VocabError(f"{name}: `word` must be an array of tables ([[word]])")
            _load_entry(name, entry, seen, pool)
    return pool


def _load_entry(name: str, e: dict[str, Any], seen: set[str], pool: Pool) -> None:
    text = e.get("text")
    if not isinstance(text, str) or not text:
        raise VocabError(f"{name}: an entry needs a non-empty `text`, got {text!r}")
    if _normalize(text) != text or " ".join(text.split()) != text:
        raise VocabError(
            f"{name}: text {text!r} is not in normalized form; write "
            f"{' '.join(_normalize(text).split())!r} (lowercase, NFC, no edge "
            f"periods, single-spaced)")
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
        if COUNT_SOURCES & p.keys() and not isinstance(p.get("as_of"), datetime.date):
            raise VocabError(f"{where}: a count needs `as_of`, a TOML date")
        _check_descriptive(where, p)
        pool.readings.append(r)
        return
    allowed = BEHAVIORAL[r.category] | DESCRIPTIVE | {"excluded"}
    for k in p:
        if k not in allowed:
            raise _reserved_or_unknown(where, k, allowed)
    _check_descriptive(where, p)
    for flag in ("acronym", "may_be_name", "may_be_given", "may_be_initial"):
        if flag in p and not isinstance(p[flag], bool):
            raise VocabError(f"{where}: {flag} must be true or false")
    if r.category == "title":
        addresses = p.get("addresses", "family")
        if addresses in ("full", "any"):
            raise VocabError(f"{where}: addresses = {addresses!r} is reserved "
                             f"for a later phase; phase 1 has 'family' and 'given'")
        if addresses not in ("family", "given"):
            raise VocabError(f"{where}: addresses must be 'family' or 'given'")
    if r.category == "suffix":
        acronym = _acronym(r)
        if "may_be_name" in p and not acronym:
            raise VocabError(f"{where}: may_be_name marks an acronym reading; "
                             f"this reading has acronym = false")
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
    if r.category == "conjunction" and p.get("may_be_initial"):
        if len(r.text) != 1 or r.text.upper() == r.text.lower():
            raise VocabError(
                f"{where}: may_be_initial needs a CASED single letter; the "
                f"fork reads only a cased one-letter token, so this is inert")
    if "cased" in p:
        cased = p["cased"]
        if not isinstance(cased, str) or _alnum(_normalize(cased)) != _alnum(r.text):
            raise VocabError(f"{where}: cased {cased!r} must spell {r.text!r}'s "
                             f"letters and digits, recased (a case mask, #459)")
    if "excluded" in p:
        ex = p["excluded"]
        if not isinstance(ex, dict) or not ex:
            raise VocabError(f"{where}: excluded must be a table of properties")
        for prop, why in ex.items():
            if prop not in BEHAVIORAL[r.category]:
                raise VocabError(f"{where}: excluded names {prop!r}, which is not "
                                 f"a behavioral property of a {r.category}")
            ex = _exclusion(r.file, r.text, r.kind, prop, why)
            if prop in p:
                raise VocabError(f"{where}: {prop} is excluded: {ex.reason}")
            pool.exclusions.append(ex)
    # build check 8: a phrase is matched whole only as a given-addressing
    # title run or a birth marker; anywhere else it can never match
    if " " in r.text and not (r.kind == "birth_marker" or (
            r.category == "title" and p.get("addresses") == "given")):
        raise VocabError(f"{where}: a phrase can never match as a {r.kind}; "
                         f"only birth_marker and addresses = 'given' titles are "
                         f"matched as a whole run")
    pool.readings.append(r)


def _acronym(r: Reading) -> bool:
    return bool(r.props.get("acronym", r.kind == "credential"))


# ------------------------------------------------------------- compiling
def check_pool(pool: Pool) -> None:
    """The cross-file build checks (4-7, 9) and the data invariants."""
    by_text: dict[str, list[Reading]] = {}
    for r in pool.readings:
        by_text.setdefault(r.text, []).append(r)

    # 4: one suffix kind per word, across files
    for text, rs in by_text.items():
        kinds = sorted({r.kind for r in rs if r.category == "suffix"})
        if len(kinds) > 1:
            raise VocabError(f"{text!r}: one suffix kind per word, got {kinds} "
                             f"({', '.join(sorted({r.file for r in rs}))})")

    # 5: the same kind of the same word agrees on every behavioral
    # property in every file -- the default loads them all, so a word
    # cannot read two ways (per-language behavior is phase 3's)
    for text, rs in by_text.items():
        first: dict[str, Reading] = {}
        for r in rs:
            if r.category == "name":
                continue
            seen = first.setdefault(r.kind, r)
            for prop in BEHAVIORAL[r.category]:
                a, b = _behavior(seen, prop), _behavior(r, prop)
                if a != b:
                    raise VocabError(
                        f"{text!r} {r.kind}: {prop} is {a!r} in {seen.file} "
                        f"but {b!r} in {r.file}; one word reads one way")

    # 6: an excluded kind or property is absent from the whole pool
    for x in pool.exclusions:
        for r in by_text.get(x.text, ()):
            if x.prop is None and (r.kind == x.kind or r.category == x.kind):
                raise VocabError(f"{r.where()}: {x.kind} is excluded for "
                                 f"{x.text!r} in {x.file}: {x.reason}")
            if x.prop is not None and r.kind == x.kind and x.prop in r.props:
                raise VocabError(f"{r.where()}: {x.prop} is excluded for "
                                 f"{x.text!r} in {x.file}: {x.reason}")

    # 7: same_as names a word of the same category; one cased per word
    for r in pool.readings:
        target = r.props.get("same_as")
        if target is not None and not any(
                t.category == r.category for t in by_text.get(target, ())):
            raise VocabError(f"{r.where()}: same_as {target!r} has no "
                             f"{r.category} reading")
    for text, rs in by_text.items():
        masks = {r.props["cased"] for r in rs if "cased" in r.props}
        if len(masks) > 1:
            raise VocabError(f"{text!r}: one cased mask per word, got {sorted(masks)}")

    # 9: a bound given name that is also a particle must be one that may
    # be given -- the bound join reads it as a given name (Lexicon raises)
    for text, rs in by_text.items():
        if any(r.kind == "bound_given" for r in rs):
            for r in rs:
                if r.category == "particle" and not r.props.get("may_be_given"):
                    raise VocabError(f"{r.where()}: also a bound given name, so "
                                     f"the particle needs may_be_given = true")

    # an elided particle reads only the apostrophe it is spelled with,
    # nothing folding U+2019 to U+0027, so both spellings ship (#700)
    particles = {r.text for r in pool.readings if r.category == "particle"}
    for text in sorted(particles):
        for a, b in (("’", "'"), ("'", "’")):
            if a in text and text.replace(a, b) not in particles:
                raise VocabError(f"{text!r}: an elided particle needs its ASCII "
                                 f"and its U+2019 spelling; add "
                                 f"{text.replace(a, b)!r}")

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
        return _acronym(r)
    if prop == "addresses":
        return r.props.get("addresses", "family")
    if prop == "attached":
        att = r.props.get("attached")
        return None if att is None else att.get("side")
    return r.props.get(prop, False if prop.startswith("may_be") else None)


#: The constants _compiled.py defines, in its order, each with the
#: nameparser.config module that re-exports it.
CONSTANTS = (
    ("GIVEN_NAME_TITLES", "titles"),
    ("TITLES", "titles"),
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


def compile_pool(pool: Pool) -> dict[str, Any]:
    """Fold the readings into today's constants."""
    check_pool(pool)
    s: dict[str, set[str]] = {name: set() for name, _ in CONSTANTS[:-1]}
    cased: dict[str, str] = {}
    for r in pool.readings:
        t, p = r.text, r.props
        if "cased" in p:
            cased[t] = p["cased"]
        if r.category == "title":
            s["TITLES"].add(t)
            if p.get("addresses") == "given":
                s["GIVEN_NAME_TITLES"].add(t)
        elif r.category == "suffix":
            if _acronym(r):
                s["SUFFIX_ACRONYMS"].add(t)
                if p.get("may_be_name"):
                    s["SUFFIX_ACRONYMS_AMBIGUOUS"].add(t)
            else:
                s["SUFFIX_WORDS"].add(t)
                if "attached" in p:
                    s["GLUED_HONORIFICS"].add(t)
        elif r.category == "particle":
            s["PARTICLES"].add(t)
        elif r.category == "conjunction":
            s["CONJUNCTIONS"].add(t)
            if p.get("may_be_initial"):
                s["CONJUNCTIONS_AMBIGUOUS"].add(t)
        elif r.category == "bound_given":
            s["BOUND_GIVEN_NAMES"].add(t)
        elif r.category == "relation":
            s["MAIDEN_MARKERS"].add(t)
    # a particle is never-given unless SOME reading says it may be given
    # (check 5 makes every reading of one word agree, so "some" is "all")
    s["NON_GIVEN_NAME_PARTICLES"] = {
        r.text for r in pool.readings
        if r.category == "particle" and not r.props.get("may_be_given")}
    out: dict[str, Any] = {k: frozenset(v) for k, v in s.items()}
    out["CAPITALIZATION_EXCEPTIONS"] = dict(sorted(cased.items()))
    # One form per post-nominal: the word test strips only edge periods
    # and the acronym test strips all of them, so a word in both is
    # matched twice by two rules, and which one fired is unreadable from
    # outside. The sharper stake is the ambiguous set's: suffix_as_written
    # ORs the two branches, so an ambiguous acronym that were also a word
    # would be claimed through the word and bypass the period gate the
    # marking exists to impose. The single overlap was 'esq', dropped
    # 2026-09-08 (decisions/suffix-acronym-collisions). This guards the
    # SHIPPED data only: Lexicon has no matching invariant, so a caller
    # may still put a word in both. Check 4 makes the overlap unreachable
    # through kinds; this catches one kind spelled both ways in two files,
    # which check 5 reports first.
    both = out["SUFFIX_ACRONYMS"] & out["SUFFIX_WORDS"]
    if both:
        raise VocabError(f"{sorted(both)}: a post-nominal is an acronym or a "
                         f"word, never both (check `acronym` in every file)")
    return out


def read_dir(path: Path = VOCAB) -> dict[str, str]:
    return {f.name: f.read_text(encoding="utf-8") for f in sorted(path.glob("*.toml"))}


def compile_files(files: Mapping[str, str]) -> dict[str, Any]:
    return compile_pool(load(files))


# --------------------------------------------------------------- output
HEADER = f'''"""The compiled vocabulary. GENERATED from nameparser/vocab/*.toml by
tools/vocab/build.py -- do not edit; edit the TOML and run

    {REFRESH}

The public names are re-exported, with their documentation, by the
nameparser.config modules (titles, particles, suffixes, ...).
"""
'''


def render(compiled: Mapping[str, Any]) -> str:
    """One sorted entry per line, so a one-word change is a one-line diff."""
    out = [HEADER]
    for name, _ in CONSTANTS:
        v = compiled[name]
        out.append("")
        if isinstance(v, dict):
            out.append(f"{name}: dict[str, str] = {{")
            out += [f"    {k!r}: {v[k]!r}," for k in sorted(v)]
            out.append("}")
        else:
            out.append(f"{name}: frozenset[str] = frozenset({{")
            out += [f"    {w!r}," for w in sorted(v)]
            out.append("})")
    return "\n".join(out) + "\n"


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--check", action="store_true",
                    help="exit 1 if the committed module is stale")
    args = ap.parse_args(argv)
    text = render(compile_files(read_dir()))
    current = OUTPUT.read_text(encoding="utf-8") if OUTPUT.exists() else ""
    if args.check:
        if current != text:
            print(f"{OUTPUT.relative_to(ROOT)} is stale; run: {REFRESH}")
            return 1
        print(f"{OUTPUT.relative_to(ROOT)} is current")
        return 0
    if current == text:
        print(f"{OUTPUT.relative_to(ROOT)} is current")
    else:
        OUTPUT.write_text(text, encoding="utf-8")
        print(f"wrote {OUTPUT.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
