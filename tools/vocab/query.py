"""Query the per-word vocabulary in nameparser/vocab/*.toml.

A decisions/ entry points at its words with a query instead of a list,
so the pointer cannot drift from the data::

    uv run python tools/vocab/query.py --issue 661
    uv run python tools/vocab/query.py --kind honorific
    uv run python tools/vocab/query.py --excluded generation
    uv run python tools/vocab/query.py --word 殿

Filters combine (AND). Each match prints as ``file  text  kind`` and the
reading's properties; an exclusion prints as ``excluded:<kind>``, or
``<kind> excluded:<property>`` for a property refused on a reading the
word keeps, with its reason.

- ``--kind`` matches a kind or every kind of a category (``--kind
  suffix``). Alone it lists readings; beside ``--excluded`` it narrows
  the exclusions to that kind (``--kind honorific --excluded attached``,
  the honorifics refused the glued peel).
- ``--excluded`` matches a refused reading by its kind or category
  (``--excluded generation``), or a property refused on a reading the
  word keeps by the property's name (``--excluded attached``), never
  both.
- ``--issue`` matches an issue cited by a reading, by its ``attached``
  table, or by an exclusion.
- ``--word`` is normalized as the vocabulary is (``--word Dr.`` finds
  ``dr``); ``--file`` takes a tag (``en``) or a file name (``en.toml``).

``--count`` prints only the number of matches. Exits 1 when nothing
matches, 2 for an unknown kind, property or file, an empty ``--word``,
or vocabulary that cannot be read or fails a per-entry check, and 3 on
an internal error. The query reads the files as loaded, with
the per-entry checks only: it answers over a pool whose cross-file
checks may fail, so a contributor can look words up in a tree that does
not compile yet.
"""
from __future__ import annotations

import argparse
import sys
import traceback
from dataclasses import dataclass
from pathlib import Path
from typing import Any

# query.py runs as a script, so it imports its sibling by path; a test
# loading both modules by file gets two copies of build's classes
sys.path.insert(0, str(Path(__file__).resolve().parent))
import build  # noqa: E402


@dataclass
class Row:
    file: str
    text: str
    label: str
    kind: str
    excluded: bool
    props: dict[str, Any]

    def issues(self) -> set[int]:
        found: set[int] = set()
        for table in (self.props, self.props.get("attached")):
            if isinstance(table, dict):
                v = table.get("issue", [])
                found |= set(v if isinstance(v, list) else [v])
        return found


def rows(pool: build.Pool) -> list[Row]:
    out = [Row(r.file, r.text, r.kind, r.kind, False, r.props) for r in pool.readings]
    for x in pool.exclusions:
        label = f"excluded:{x.kind}" if x.prop is None else f"{x.kind} excluded:{x.prop}"
        out.append(Row(x.file, x.text, label, x.kind, True, x.props))
    return out


def _is(kind: str, wanted: str) -> bool:
    return kind == wanted or build.CATEGORY.get(kind, kind) == wanted


def select(pool: build.Pool, *, issue: int | None = None, kind: str | None = None,
           excluded: str | None = None, word: str | None = None,
           file: str | None = None) -> list[Row]:
    found = []
    for row in rows(pool):
        if issue is not None and issue not in row.issues():
            continue
        if kind is not None and not _is(row.kind, kind):
            continue
        # --kind without --excluded lists readings; beside it, it narrows
        # the exclusions
        if kind is not None and excluded is None and row.excluded:
            continue
        # a refused reading matches its kind or category; a refused
        # PROPERTY matches only the property's name, so `--excluded
        # honorific` is the words refused the honorific reading, not the
        # honorifics refused the glued peel
        word_level = row.label.startswith("excluded:")
        if excluded is not None and not (row.excluded and (
                (word_level and _is(row.kind, excluded))
                or (not word_level and row.label.endswith(f":{excluded}")))):
            continue
        if word is not None and row.text != word:
            continue
        if file is not None and row.file != file:
            continue
        found.append(row)
    return found


KINDS = frozenset(build.CATEGORY) | build.CATEGORIES
PROPERTIES = frozenset().union(*build.BEHAVIORAL.values())


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--issue", type=int, help="readings or exclusions citing this issue")
    ap.add_argument("--kind", help="readings of this kind, or of every kind of this category")
    ap.add_argument("--excluded", metavar="KIND_OR_PROPERTY",
                    help="exclusions of this kind or category, or of this "
                         "property refused on a reading the word keeps")
    ap.add_argument("--word", help="every reading and exclusion of this text")
    ap.add_argument("--file", help="only this file, by tag (en) or name (en.toml)")
    ap.add_argument("--count", action="store_true", help="print the number of matches only")
    args = ap.parse_args(argv)
    if args.kind is not None and args.kind not in KINDS:
        ap.error(f"unknown kind {args.kind!r}; known: {', '.join(sorted(KINDS))}")
    if args.excluded is not None and args.excluded not in KINDS | PROPERTIES:
        ap.error(f"unknown kind or property {args.excluded!r}; known: "
                 f"{', '.join(sorted(KINDS | PROPERTIES))}")
    try:
        return _run(ap, args)
    except build.VocabError as e:
        print(f"vocabulary error: {e}", file=sys.stderr)
        return 2
    except Exception:
        # never exit 1 on an error: 1 means "nothing matches"
        traceback.print_exc()
        return 3


def _run(ap: argparse.ArgumentParser, args: argparse.Namespace) -> int:
    word = None if args.word is None else " ".join(build._normalize(args.word).split())
    if word == "":
        ap.error(f"--word {args.word!r} normalizes to nothing")
    files = build.read_dir()
    file = args.file
    if file is not None:
        file = file if file.endswith(".toml") else f"{file}.toml"
        if file not in files:
            ap.error(f"no vocabulary file {file!r}")
    found = select(build.load(files), issue=args.issue, kind=args.kind,
                   excluded=args.excluded, word=word, file=file)
    if args.count:
        print(len(found))
    else:
        for row in found:
            shown = ", ".join(f"{k}={v!r}" for k, v in row.props.items())
            print(f"{row.file:10} {row.text:14} {row.label:24} {shown}")
    return 0 if found else 1


if __name__ == "__main__":
    sys.exit(main())
