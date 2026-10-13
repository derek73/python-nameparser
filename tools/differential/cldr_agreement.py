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
  progress in disguise -- and a record that never goes stale).

    uv run python tools/differential/cldr_agreement.py           # summary
    uv run python tools/differential/cldr_agreement.py --record  # re-record

Re-record deliberately, and say why in the commit, as with a watched diff.
The record doubles as a measured worklist: every entry is a place the
parser and CLDR read a name differently.

Nothing is special-cased. A deliberately unnatural rendering, `さん` read
as a suffix where CLDR calls it a title, a lone word under a family-first
order: each simply disagrees, and the ratchet guards what agrees.
"""
from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from pathlib import Path
from typing import Any

from nameparser import FAMILY_FIRST, ParsedName, Parser, Policy

ROLES = ("title", "given_names", "family", "suffix",
         "family_particles", "family_base")
HERE = Path(__file__).resolve().parent
FIELDS = HERE / "cldr_fields.jsonl"
RECORD = HERE / "cldr_agreement.json"
RECORD_COMMAND = "uv run python tools/differential/cldr_agreement.py --record"
#: shapes.py's FAMILY_FIRST shape, the only tag build_cldr_corpus.py writes.
FAMILY_FIRST_SHAPE = 4
_PARSERS = {None: Parser(),
            FAMILY_FIRST_SHAPE: Parser(policy=Policy(name_order=FAMILY_FIRST))}


def _has_space(text: str) -> bool:
    return any(ch.isspace() for ch in text)


def _words(text: str) -> list[str]:
    return text.replace(",", " ").split()


def _squash(text: str) -> str:
    return "".join(text.replace(",", "").split())


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
        return " ".join(fields[n] for n in names
                        if n in fields and occurs(fields[n], text))

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


def parse_rendering(text: str, shape: int | None) -> ParsedName:
    """The one place a rendering is parsed, so the recorder and the
    checker cannot read it two ways."""
    return _PARSERS[shape].parse(text)


def load_rows(path: Path = FIELDS) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()
            if line.strip()]


def disagreements(rows: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    """Every rendering where some role disagrees, with each disagreeing
    role's expected and parsed value, sorted by key."""
    found: dict[str, dict[str, Any]] = {}
    for row in rows:
        got = got_roles(parse_rendering(row["text"], row["shape"]))
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


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--record", action="store_true",
                    help=f"rewrite {RECORD.name} from the working tree")
    args = ap.parse_args(argv)
    rows = load_rows()
    current = disagreements(rows)
    if args.record:
        write_record(current)
        print(f"recorded {len(current)} disagreeing renderings to {RECORD.name}")
        return 0
    totals: Counter[str] = Counter()
    for row in rows:
        totals.update(expected_roles(row["fields"], row["text"]).keys())
    wrong = Counter(role for entry in current.values() for role in entry if role != "text")
    for role in ROLES:
        agree = totals[role] - wrong[role]
        print(f"{role:17} {agree:5}/{totals[role]:<5} agree")
    problems = changes(read_record(), current, {rendering_key(r) for r in rows})
    print("\n".join(problems) or "matches the record")
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())
