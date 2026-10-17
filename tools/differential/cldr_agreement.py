"""Where nameparser disagrees with each source's stated fields -- a ratchet.

CLDR's person-name test data (see build_cldr_corpus.py) states every
name's fields separately. This module parses each CLDR rendering with the
working tree and compares, role by role, with what CLDR says; the
DISAGREEMENTS are recorded in cldr_agreement.json, and
tests/v2/test_cldr_agreement.py fails when the tree's disagreements stop
matching the record. The GND corpus (build_gnd_corpus.py) writes its
fields in CLDR's vocabulary, so it is a second SOURCE compared by the
same rules, with its record in gnd_agreement.json, and so is the
Wikidata corpus (build_wikidata_corpus.py, wikidata_agreement.json),
which states the two fields CLDR's vocabulary merges or lacks, and the
hand-written conventions table (build_conventions_corpus.py,
conventions_agreement.json), which adds `honorific`, a word of address
written after the name, scored inside `suffix`, and the native-script
Wikidata corpus (build_wikidata_native_corpus.py,
wikidata_native_agreement.json), real names in their own scripts;
"CLDR" below means any
source wherever the rule is about fields. For each source the
test fails on:

- a role that agreed now disagrees (a regression);
- a recorded disagreement now agrees (progress, which must be recorded so
  that it is guarded from then on);
- a recorded disagreement's answer changed (a different wrong answer, or
  progress in disguise -- which keeps the recorded answers current; the
  recorded `text` and `expected` are refreshed only by a re-record);
- a recorded rendering that no longer exists.

    uv run python tools/differential/cldr_agreement.py           # summary
    uv run python tools/differential/cldr_agreement.py --record  # re-record

--record rewrites every record, each source's and the locale ones below, and first prints, per source, how many of each kind of change
it is accepting, so a re-record made for one source cannot slip another
source's regressions in unseen.

A second view does the same with each locale pack (#672): the renderings
of every CLDR file in LOCALE_FILES, and every native-script Wikidata
rendering naming a pack (`pack`: its Han and kana names), are parsed
with parser_for(pack), and their disagreements are recorded in
cldr_agreement_locales.json and wikidata_native_agreement_locales.json
and ratcheted the same way, so a pack change shows what it moved on its
own language. A pack needing an optional extra that is not installed
(JA's namedivider) is not measured, and its recorded entries are
carried over unchanged.

Re-record deliberately, and say why in the commit, as with a watched diff.
Each record doubles as a measured worklist: every entry is a place the
parser and the source read a name differently.

Two fields are stated but not yet scored on their own: `surname2` (a
second surname: CLDR's `surname2`, Wikidata's P1950) and `patronymic`
(Wikidata's P5056, a field CLDR does not have). ParsedName has neither,
so each is scored inside the role it belongs to today -- `surname2`
inside `family`, as CLDR's own merge does, and `patronymic` inside
`given_names`, since a patronymic is not a family name (the GND and LC
convention: `Vigdís Finnbogadóttir` expects the family empty). They are
in PENDING_ROLES, and each is also scored on its own the day ParsedName
gains an attribute of that name; until then the summary says how many
renderings state it. Scoring a field on its own does not end the merged
scoring; only a 3.0 decision to take the field out of `family` or
`given_names` changes PENDING_ROLES. The conventions source's
`honorific` is not pending: it is scored inside `suffix` by design, as
nameparser reads `さん`, and ParsedName is not meant to gain it.

A field name no rule reads raises: a mistyped `honorfic` would
otherwise be expected in no role and pass as agreement. KNOWN_FIELDS is
every name expected_roles reads, IGNORED_FIELDS what a source states
that no rendering writes (CLDR's `locale` and `given-informal`).

Nothing is special-cased. A deliberately unnatural rendering, `さん` read
as a suffix where CLDR calls it a title, a lone word under a family-first
order: each simply disagrees, and the ratchet guards what agrees.
"""
from __future__ import annotations

import argparse
import functools
import json
import sys
from collections import Counter
from importlib.util import find_spec
from pathlib import Path
from typing import Any

from nameparser import (FAMILY_FIRST, FAMILY_FIRST_GIVEN_LAST, ParsedName, Parser, Policy,
                        locales, parser_for)

ROLES = ("title", "given_names", "family", "suffix",
         "family_particles", "family_base")
#: Fields a source states that ParsedName has no attribute for yet, each
#: with the role it is scored inside: always there, and ALSO on its own
#: once ParsedName has it (see got_roles). Whether the merged role should
#: then drop it is the 3.0 design's question, not this one.
PENDING_ROLES = {"surname2": "family", "patronymic": "given_names"}
HERE = Path(__file__).resolve().parent
FIELDS = HERE / "cldr_fields.jsonl"
RECORD = HERE / "cldr_agreement.json"
LOCALE_RECORD = HERE / "cldr_agreement_locales.json"
GND_FIELDS = HERE / "gnd_fields.jsonl"
GND_RECORD = HERE / "gnd_agreement.json"
WIKIDATA_FIELDS = HERE / "wikidata_fields.jsonl"
WIKIDATA_RECORD = HERE / "wikidata_agreement.json"
CONVENTIONS_FIELDS = HERE / "conventions_fields.jsonl"
CONVENTIONS_RECORD = HERE / "conventions_agreement.json"
NATIVE_FIELDS = HERE / "wikidata_native_fields.jsonl"
NATIVE_RECORD = HERE / "wikidata_native_agreement.json"
NATIVE_LOCALE_RECORD = HERE / "wikidata_native_agreement_locales.json"
RECORD_COMMAND = "uv run python tools/differential/cldr_agreement.py --record"
#: shapes.py's FAMILY_FIRST shape, the only tag build_cldr_corpus.py writes.
FAMILY_FIRST_SHAPE = 4
#: shapes.py's FAMILY_FIRST_GIVEN_LAST shape, which a conventions row may name.
FAMILY_FIRST_GIVEN_LAST_SHAPE = 5
_PARSERS = {None: Parser(),
            FAMILY_FIRST_SHAPE: Parser(policy=Policy(name_order=FAMILY_FIRST)),
            FAMILY_FIRST_GIVEN_LAST_SHAPE:
                Parser(policy=Policy(name_order=FAMILY_FIRST_GIVEN_LAST))}

#: The locale view: CLDR file -> the nameparser.locales pack its
#: renderings are parsed with. One pack per file, so the locale record is
#: keyed like the default one. A new pack adds its files here, or its
#: name to NO_CLDR; test_cldr_agreement.py fails on a pack in neither.
LOCALE_FILES = {"zh": "ZH", "zh_Hant": "ZH", "yue": "ZH", "yue_Hans": "ZH",
                "ja": "JA", "ru": "RU", "tr": "TR_AZ", "az": "TR_AZ"}
#: Packs with no CLDR file to measure them on.
NO_CLDR: frozenset[str] = frozenset()
#: Packs measured only where an optional extra is installed: pack -> the
#: module the extra provides.
_EXTRAS = {"JA": "namedivider"}


def pack_available(pack: str) -> bool:
    """Whether the locale view can measure this pack here."""
    module = _EXTRAS.get(pack)
    return module is None or find_spec(module) is not None


@functools.cache
def _parser(pack: str | None, shape: int | None) -> Parser:
    if pack is None:
        return _PARSERS[shape]
    if pack == "JA":
        return parser_for(locales.JA, base=_PARSERS[shape],
                          segmenter=locales.ja_segmenter())
    return parser_for(getattr(locales, pack), base=_PARSERS[shape])


def _has_space(text: str) -> bool:
    return any(ch.isspace() for ch in text)


#: Commas a rendering may carry: nameparser's own COMMA_CHARS (ASCII,
#: Arabic U+060C, fullwidth U+FF0C) plus the Myanmar U+104A and
#: Ethiopic U+1363 marks CLDR's sorting forms use, and the ideographic
#: U+3001, which no CLDR 48 rendering holds -- defensive. A comma
#: left glued to a word hides that word from occurs(), and CLDR's field
#: is then expected empty -- a disagreement no parser fix could resolve.
_COMMAS = str.maketrans({c: " " for c in ",\u060c\uff0c\u104a\u1363\u3001"})


def _words(text: str) -> list[str]:
    return text.translate(_COMMAS).split()


def _squash(text: str) -> str:
    return "".join(text.translate(_COMMAS).split())


def occurs(value: str, text: str) -> bool:
    """Whether a field's value appears in a rendering: word by word
    where the rendering has spaces (so `Wolf` is not found in `Wolfgang`),
    by substring where it has none (unspaced scripts)."""
    if _has_space(text):
        need = Counter(_words(value))
        return bool(need) and not need - Counter(_words(text))
    return bool(_squash(value)) and _squash(value) in _squash(text)


#: Every field name expected_roles reads, and the ones it skips on purpose.
KNOWN_FIELDS = frozenset({"title", "given", "given2", "surname", "surname-prefix",
                          "surname-core", "generation", "credentials", "honorific",
                          *PENDING_ROLES})
IGNORED_FIELDS = frozenset({"locale", "given-informal"})


def expected_roles(fields: dict[str, str], text: str) -> dict[str, str]:
    """What the source says each role holds IN THIS RENDERING. CLDR's
    formats drop fields by locale and order, so a role is built only from
    the fields whose value occurs in the text; a role with none expects
    ''. The particle and base views are compared only where the source
    states the split, i.e. the name has a surname-core."""
    unknown = set(fields) - KNOWN_FIELDS - IGNORED_FIELDS
    if unknown:
        raise ValueError(f"fields {sorted(unknown)} of {text!r} are read by no "
                         f"rule; use one of {sorted(KNOWN_FIELDS)}")
    def present(*names: str) -> str:
        # In the order the values occur in the text, not CLDR's field
        # order: an unspaced rendering compares in order, and one that
        # writes given2 before given would otherwise never agree.
        found = [fields[n] for n in names if n in fields and occurs(fields[n], text)]
        return " ".join(sorted(found, key=lambda v: _squash(text).find(_squash(v))))

    def pending(role: str) -> tuple[str, ...]:
        """The PENDING_ROLES fields scored inside `role`."""
        return tuple(f for f, merged in PENDING_ROLES.items() if merged == role)

    family = ("surname",) if "surname" in fields else ("surname-prefix", "surname-core")
    roles = {"title": present("title"),
             "given_names": present("given", "given2", *pending("given_names")),
             "family": present(*family, *pending("family")),
             "suffix": present("generation", "credentials", "honorific")}
    if "surname-core" in fields:
        roles["family_particles"] = present("surname-prefix")
        roles["family_base"] = present("surname-core", *pending("family"))
    for role in PENDING_ROLES:
        if role in fields:
            roles[role] = present(role)
    return roles


def same(expected: str, got: str, text: str) -> bool:
    """Agreement, decided by the rendering as occurs() is: the same
    multiset of words where it has spaces (order within a role is free),
    the same text with spaces and commas removed where it has none."""
    if _has_space(text):
        return Counter(_words(expected)) == Counter(_words(got))
    return _squash(expected) == _squash(got)


def got_roles(name: ParsedName) -> dict[str, str]:
    """The parser's answer for every role it can answer: ROLES always,
    a PENDING_ROLES field only once ParsedName has it."""
    got = {"title": name.title, "given_names": name.given_names,
           "family": name.family, "suffix": name.suffix,
           "family_particles": name.family_particles,
           "family_base": name.family_base}
    for role in PENDING_ROLES:
        value = getattr(name, role, None)
        if isinstance(value, str):
            got[role] = value
    return got


def rendering_key(row: dict[str, Any]) -> str:
    return f"{row['file']}/{row['label']}/{row['order']}"


def parse_rendering(text: str, shape: int | None, pack: str | None = None) -> ParsedName:
    """The one place a rendering is parsed, so the recorder and the
    checker cannot read it two ways. `pack` names a nameparser.locales
    pack for the locale view; its parser keeps the shape's name order."""
    return _parser(pack, shape).parse(text)


def load_rows(path: Path = FIELDS) -> list[dict[str, Any]]:
    """A fields file's rows. An empty file is an error: compared against
    an empty record it would agree with everything."""
    rows = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()
            if line.strip()]
    if not rows:
        raise ValueError(f"{path} holds no renderings; rebuild it with its "
                         f"build_*_corpus.py")
    return rows


def row_pack(row: dict[str, Any]) -> str | None:
    """The pack the locale view parses a rendering with: the one it
    names (`pack`, which the native-script Wikidata rows carry), else its
    CLDR file's in LOCALE_FILES, else none."""
    pack = row.get("pack")
    return str(pack) if pack is not None else LOCALE_FILES.get(row["file"])


def locale_rows(rows: list[dict[str, Any]], pack: str) -> list[dict[str, Any]]:
    """The renderings the locale view parses with `pack`."""
    return [row for row in rows if row_pack(row) == pack]


def disagreements(rows: list[dict[str, Any]],
                  locale: bool = False) -> dict[str, dict[str, Any]]:
    """Every rendering where some role disagrees, with each disagreeing
    role's expected and parsed value, sorted by key. With `locale`, each
    row is parsed with its pack (row_pack), so every row must have one."""
    found: dict[str, dict[str, Any]] = {}
    for row in rows:
        pack = row_pack(row) if locale else None
        if locale and pack is None:
            raise ValueError(f"{rendering_key(row)} has no locale pack")
        got = got_roles(parse_rendering(row["text"], row["shape"], pack))
        bad = {role: {"expected": expected, "got": got[role]}
               for role, expected in expected_roles(row["fields"], row["text"]).items()
               if (role in got or role not in PENDING_ROLES)
               and not same(expected, got[role], row["text"])}
        if bad:
            found[rendering_key(row)] = {"text": row["text"], **bad}
    return dict(sorted(found.items()))


def read_record(path: Path = RECORD) -> dict[str, dict[str, Any]]:
    record: dict[str, dict[str, Any]] = json.loads(path.read_text(encoding="utf-8"))
    return record


def write_record(record: dict[str, dict[str, Any]], path: Path = RECORD) -> None:
    path.write_text(json.dumps(record, ensure_ascii=False, indent=1, sort_keys=True)
                    + "\n", encoding="utf-8")


def changes(recorded: dict[str, dict[str, Any]], current: dict[str, dict[str, Any]],
            keys: set[str]) -> list[str]:
    """How the current disagreements differ from the record: a
    regression, progress, a changed wrong answer, or a recorded
    rendering that no longer exists. `keys` is every current rendering."""
    out: list[str] = []
    for key in sorted(set(recorded) | set(current)):
        if key not in keys:
            out.append(f"gone: {key} is recorded but no longer a rendering")
            continue
        old, new = recorded.get(key, {}), current.get(key, {})
        for role in sorted((set(old) | set(new)) - {"text"}):
            if role not in old:
                out.append(f"regression: {key} {role}: expected "
                           f"{new[role]['expected']!r}, got {new[role]['got']!r} "
                           f"(agreed before) -- {new['text']!r}")
            elif role not in new:
                out.append(f"progress: {key} {role} now agrees (recorded got "
                           f"{old[role]['got']!r}); re-record so it is guarded")
            elif old[role]["got"] != new[role]["got"]:
                out.append(f"changed: {key} {role}: expected "
                           f"{new[role]['expected']!r}, recorded got "
                           f"{old[role]['got']!r}, now {new[role]['got']!r}")
    return out


def _file_of(key: str) -> str:
    return key.split("/", 1)[0]


def _key_packs(rows: list[dict[str, Any]],
               recorded: dict[str, dict[str, Any]]) -> dict[str, str | None]:
    """The pack each locale-record entry belongs to: its rendering's,
    while the rendering exists, else its CLDR file's in LOCALE_FILES (so
    a CLDR rendering that is gone is still reported by its pack's check)."""
    packs = {rendering_key(row): row_pack(row) for row in rows}
    return {key: packs[key] if key in packs else LOCALE_FILES.get(_file_of(key))
            for key in recorded}


def locale_changes(rows: list[dict[str, Any]], pack: str,
                   recorded: dict[str, dict[str, Any]]) -> list[str]:
    """changes() for one pack in the locale view: its renderings against
    its share of the locale record."""
    mine = locale_rows(rows, pack)
    packs = _key_packs(rows, recorded)
    return changes({k: v for k, v in recorded.items() if packs[k] == pack},
                   disagreements(mine, locale=True),
                   {rendering_key(row) for row in mine})


def unmapped(recorded: dict[str, dict[str, Any]],
             rows: list[dict[str, Any]] | None = None) -> list[str]:
    """Locale-record entries no pack's check reads -- a CLDR file no
    longer in LOCALE_FILES, or a rendering that is gone and names no
    CLDR file -- reported here as gone."""
    packs = _key_packs(rows or [], recorded)
    return [f"gone: {key} is recorded but no locale pack reads it"
            for key in sorted(recorded) if packs[key] is None]


def _packs() -> list[str]:
    return sorted(set(LOCALE_FILES.values()))


def sources() -> dict[str, tuple[Path, Path]]:
    """Each source of stated fields: name -> (fields file, record). Read
    at call time, so a test that points a record elsewhere is obeyed."""
    return {"CLDR": (FIELDS, RECORD), "GND": (GND_FIELDS, GND_RECORD),
            "Wikidata": (WIKIDATA_FIELDS, WIKIDATA_RECORD),
            "Conventions": (CONVENTIONS_FIELDS, CONVENTIONS_RECORD),
            "Wikidata native": (NATIVE_FIELDS, NATIVE_RECORD)}


def locale_sources() -> dict[str, tuple[Path, Path]]:
    """The sources the locale view reads: name -> (fields file, locale
    record), each also a source in sources() by the same name. CLDR's renderings take their pack from LOCALE_FILES, the
    native-script Wikidata renderings from their own `pack`."""
    return {"CLDR": (FIELDS, LOCALE_RECORD),
            "Wikidata native": (NATIVE_FIELDS, NATIVE_LOCALE_RECORD)}


def _summary(name: str, rows: list[dict[str, Any]],
             current: dict[str, dict[str, Any]], record: Path) -> list[str]:
    """Print one source's per-role agreement; return its changes."""
    totals: Counter[str] = Counter()
    for row in rows:
        totals.update(expected_roles(row["fields"], row["text"]).keys())
    wrong = Counter(role for entry in current.values() for role in entry if role != "text")
    print(f"{name}, {len(rows)} renderings:")
    for role in ROLES:
        agree = totals[role] - wrong[role]
        print(f"{role:17} {agree:5}/{totals[role]:<5} agree")
    answered = got_roles(parse_rendering("Ana Ruiz", None))
    for role, merged in PENDING_ROLES.items():
        if totals[role] and role not in answered:
            print(f"{role:17} {totals[role]:5} stated, not a ParsedName field "
                  f"yet (scored inside {merged})")
    problems = changes(read_record(record), current, {rendering_key(r) for r in rows})
    print("\n".join(problems) or f"{name} view matches the record")
    return problems


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--record", action="store_true",
                    help="rewrite every source's record and the locale record "
                    "from the working tree")
    args = ap.parse_args(argv)
    loaded = {name: (load_rows(fields), record)
              for name, (fields, record) in sources().items()}
    current = {name: disagreements(rows) for name, (rows, _) in loaded.items()}
    if args.record:
        for name, (source_rows, record) in loaded.items():
            old_record = read_record(record) if record.exists() else {}
            kinds = Counter(line.split(":", 1)[0] for line in changes(
                old_record, current[name], {rendering_key(r) for r in source_rows}))
            accepted = ", ".join(f"{n} {kind}" for kind, n in sorted(kinds.items()))
            write_record(current[name], record)
            print(f"recorded {len(current[name])} disagreeing renderings to "
                  f"{record.name} (accepting: {accepted or 'no change'})")
        for name, (fields, record) in locale_sources().items():
            _record_locale(name, load_rows(fields), record)
        return 0
    problems: list[str] = []
    for name, (source_rows, record) in loaded.items():
        problems += _summary(name, source_rows, current[name], record)
        print()
    for name, (fields, record) in locale_sources().items():
        problems += _locale_summary(name, loaded[name][0], record, set(current[name]))
    return 1 if problems else 0


def _record_locale(name: str, rows: list[dict[str, Any]], record: Path) -> None:
    """Rewrite one source's locale record, keeping the entries of a pack
    this run cannot measure."""
    old = read_record(record) if record.exists() else {}
    measured = [p for p in _packs() if pack_available(p)]
    unmeasured = set(_packs()) - set(measured)
    packs = _key_packs(rows, old)
    locale = {k: v for k, v in old.items() if packs[k] in unmeasured}
    for pack in sorted(unmeasured):
        print(f"{name}: {pack} not measured (needs {_EXTRAS[pack]}); "
              "its recorded entries are kept unchanged")
    locale.update(disagreements(
        [r for p in measured for r in locale_rows(rows, p)], locale=True))
    write_record(dict(sorted(locale.items())), record)
    print(f"recorded {len(locale)} disagreeing renderings to {record.name}")


def _locale_summary(name: str, rows: list[dict[str, Any]], record: Path,
                    default_wrong: set[str]) -> list[str]:
    """Print one source's locale view, pack by pack; return its changes.
    `default_wrong` is the keys the default parser disagrees on."""
    print(f"{name} locale view, renderings with every role agreeing:")
    recorded = read_record(record)
    problems = unmapped(recorded, rows)
    stray = {row_pack(row) for row in rows} - {None} - set(_packs())
    problems += [f"unmeasured: renderings name pack {pack!r}, which no locale view "
                 "measures; add it to LOCALE_FILES" for pack in sorted(map(str, stray))]
    for pack in _packs():
        mine = locale_rows(rows, pack)
        if not mine:  # nothing to print, but its recorded entries are still checked
            problems += locale_changes(rows, pack, recorded)
            continue
        where = ", ".join(sorted({row["label"] if "pack" in row else row["file"]
                                  for row in mine}))
        if not pack_available(pack):
            print(f"{pack:6} {where}: not measured (needs {_EXTRAS[pack]})")
            continue
        found = disagreements(mine, locale=True)
        before = sum(rendering_key(row) not in default_wrong for row in mine)
        after = len(mine) - len(found)
        print(f"{pack:6} {where}: {before}/{len(mine)} default -> "
              f"{after}/{len(mine)} with the pack")
        problems += locale_changes(rows, pack, recorded)
    print("\n".join(problems) or f"{name} locale view matches the record")
    print()
    return problems


if __name__ == "__main__":
    sys.exit(main())
