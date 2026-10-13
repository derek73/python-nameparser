"""Where nameparser and CLDR disagree about a name's fields -- a ratchet.

CLDR's person-name test data (see build_cldr_corpus.py) states every
name's fields separately. This module parses each CLDR rendering with the
working tree and compares, role by role, with what CLDR says; the
DISAGREEMENTS are recorded in cldr_agreement.json, and
tests/v2/test_cldr_agreement.py fails when the tree's disagreements stop
matching the record:

- a role that agreed now disagrees (a regression);
- a recorded disagreement now agrees (progress, which must be recorded so
  that it is guarded from then on);
- a recorded disagreement's answer changed (a different wrong answer, or
  progress in disguise -- which keeps the recorded answers current; the
  recorded `text` and `expected` are refreshed only by a re-record).

    uv run python tools/differential/cldr_agreement.py           # summary
    uv run python tools/differential/cldr_agreement.py --record  # re-record

A second view does the same with each locale pack (#672): the renderings
of every CLDR file in LOCALE_FILES are parsed with parser_for(pack), and
their disagreements are recorded in cldr_agreement_locales.json and
ratcheted the same way, so a pack change shows what it moved on its own
language. --record rewrites both records. A pack needing an optional
extra that is not installed (JA's namedivider) is not measured, and its
recorded entries are carried over unchanged.

Re-record deliberately, and say why in the commit, as with a watched diff.
The record doubles as a measured worklist: every entry is a place the
parser and CLDR read a name differently.

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

from nameparser import FAMILY_FIRST, ParsedName, Parser, Policy, locales, parser_for

ROLES = ("title", "given_names", "family", "suffix",
         "family_particles", "family_base")
HERE = Path(__file__).resolve().parent
FIELDS = HERE / "cldr_fields.jsonl"
RECORD = HERE / "cldr_agreement.json"
LOCALE_RECORD = HERE / "cldr_agreement_locales.json"
RECORD_COMMAND = "uv run python tools/differential/cldr_agreement.py --record"
#: shapes.py's FAMILY_FIRST shape, the only tag build_cldr_corpus.py writes.
FAMILY_FIRST_SHAPE = 4
_PARSERS = {None: Parser(),
            FAMILY_FIRST_SHAPE: Parser(policy=Policy(name_order=FAMILY_FIRST))}

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
    """Whether a CLDR field's value appears in a rendering: word by word
    where the rendering has spaces (so `Wolf` is not found in `Wolfgang`),
    by substring where it has none (unspaced scripts)."""
    if _has_space(text):
        need = Counter(_words(value))
        return bool(need) and not need - Counter(_words(text))
    return bool(_squash(value)) and _squash(value) in _squash(text)


def expected_roles(fields: dict[str, str], text: str) -> dict[str, str]:
    """What CLDR says each role holds IN THIS RENDERING. CLDR's formats
    drop fields by locale and order, so a role is built only from the
    fields whose value occurs in the text; a role with none expects ''.
    The particle and base views are compared only where CLDR states the
    split, i.e. the name has a surname-core."""
    def present(*names: str) -> str:
        # In the order the values occur in the text, not CLDR's field
        # order: an unspaced rendering compares in order, and one that
        # writes given2 before given would otherwise never agree.
        found = [fields[n] for n in names if n in fields and occurs(fields[n], text)]
        return " ".join(sorted(found, key=lambda v: _squash(text).find(_squash(v))))

    family = (("surname", "surname2") if "surname" in fields
              else ("surname-prefix", "surname-core", "surname2"))
    roles = {"title": present("title"),
             "given_names": present("given", "given2"),
             "family": present(*family),
             "suffix": present("generation", "credentials")}
    if "surname-core" in fields:
        roles["family_particles"] = present("surname-prefix")
        roles["family_base"] = present("surname-core", "surname2")
    return roles


def same(expected: str, got: str, text: str) -> bool:
    """Agreement, decided by the rendering as occurs() is: the same
    multiset of words where it has spaces (order within a role is free),
    the same text with spaces and commas removed where it has none."""
    if _has_space(text):
        return Counter(_words(expected)) == Counter(_words(got))
    return _squash(expected) == _squash(got)


def got_roles(name: ParsedName) -> dict[str, str]:
    return {"title": name.title, "given_names": name.given_names,
            "family": name.family, "suffix": name.suffix,
            "family_particles": name.family_particles,
            "family_base": name.family_base}


def rendering_key(row: dict[str, Any]) -> str:
    return f"{row['file']}/{row['label']}/{row['order']}"


def parse_rendering(text: str, shape: int | None, pack: str | None = None) -> ParsedName:
    """The one place a rendering is parsed, so the recorder and the
    checker cannot read it two ways. `pack` names a nameparser.locales
    pack for the locale view; its parser keeps the shape's name order."""
    return _parser(pack, shape).parse(text)


def load_rows(path: Path = FIELDS) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()
            if line.strip()]


def locale_rows(rows: list[dict[str, Any]], pack: str) -> list[dict[str, Any]]:
    """The renderings the locale view parses with `pack`."""
    return [row for row in rows if LOCALE_FILES.get(row["file"]) == pack]


def disagreements(rows: list[dict[str, Any]],
                  locale: bool = False) -> dict[str, dict[str, Any]]:
    """Every rendering where some role disagrees, with each disagreeing
    role's expected and parsed value, sorted by key. With `locale`, each
    row is parsed with its file's pack, so every row must be mapped."""
    found: dict[str, dict[str, Any]] = {}
    for row in rows:
        pack = LOCALE_FILES[row["file"]] if locale else None
        got = got_roles(parse_rendering(row["text"], row["shape"], pack))
        bad = {role: {"expected": expected, "got": got[role]}
               for role, expected in expected_roles(row["fields"], row["text"]).items()
               if not same(expected, got[role], row["text"])}
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
            out.append(f"gone: {key} is recorded but no longer a CLDR rendering")
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


def locale_changes(rows: list[dict[str, Any]], pack: str,
                   recorded: dict[str, dict[str, Any]]) -> list[str]:
    """changes() for one pack in the locale view: its renderings against
    its share of the locale record."""
    mine = locale_rows(rows, pack)
    return changes({k: v for k, v in recorded.items()
                    if LOCALE_FILES.get(_file_of(k)) == pack},
                   disagreements(mine, locale=True),
                   {rendering_key(row) for row in mine})


def unmapped(recorded: dict[str, dict[str, Any]]) -> list[str]:
    """Locale-record entries whose file is no longer in LOCALE_FILES: no
    pack's check reads them, so they are reported here as gone."""
    return [f"gone: {key} is recorded but its file is not in LOCALE_FILES"
            for key in sorted(recorded) if _file_of(key) not in LOCALE_FILES]


def _packs() -> list[str]:
    return sorted(set(LOCALE_FILES.values()))


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--record", action="store_true",
                    help=f"rewrite {RECORD.name} and {LOCALE_RECORD.name} "
                    "from the working tree")
    args = ap.parse_args(argv)
    rows = load_rows()
    current = disagreements(rows)
    if args.record:
        write_record(current)
        print(f"recorded {len(current)} disagreeing renderings to {RECORD.name}")
        old = read_record(LOCALE_RECORD) if LOCALE_RECORD.exists() else {}
        measured = [p for p in _packs() if pack_available(p)]
        unmeasured = set(_packs()) - set(measured)
        locale = {k: v for k, v in old.items()
                  if LOCALE_FILES.get(_file_of(k)) in unmeasured}
        for pack in sorted(unmeasured):
            print(f"{pack} not measured (needs {_EXTRAS[pack]}); "
                  "its recorded entries are kept unchanged")
        locale.update(disagreements(
            [r for p in measured for r in locale_rows(rows, p)], locale=True))
        write_record(dict(sorted(locale.items())), LOCALE_RECORD)
        print(f"recorded {len(locale)} disagreeing renderings to {LOCALE_RECORD.name}")
        return 0
    totals: Counter[str] = Counter()
    for row in rows:
        totals.update(expected_roles(row["fields"], row["text"]).keys())
    wrong = Counter(role for entry in current.values() for role in entry if role != "text")
    for role in ROLES:
        agree = totals[role] - wrong[role]
        print(f"{role:17} {agree:5}/{totals[role]:<5} agree")
    problems = changes(read_record(), current, {rendering_key(r) for r in rows})
    print("\n".join(problems) or "default view matches the record")
    print("\nlocale view, renderings with every role agreeing:")
    recorded = read_record(LOCALE_RECORD)
    locale_problems = unmapped(recorded)
    for pack in _packs():
        mine = locale_rows(rows, pack)
        files = ", ".join(sorted({row["file"] for row in mine}))
        if not pack_available(pack):
            print(f"{pack:6} {files}: not measured (needs {_EXTRAS[pack]})")
            continue
        found = disagreements(mine, locale=True)
        before = sum(rendering_key(row) not in current for row in mine)
        after = len(mine) - len(found)
        print(f"{pack:6} {files}: {before}/{len(mine)} default -> "
              f"{after}/{len(mine)} with the pack")
        locale_problems += locale_changes(rows, pack, recorded)
    print("\n".join(locale_problems) or "locale view matches the record")
    return 1 if problems or locale_problems else 0


if __name__ == "__main__":
    sys.exit(main())
