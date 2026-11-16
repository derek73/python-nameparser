"""List the places in docs/*.rst a reader is likely to get lost.

A mechanical scan, for candidates only: it finds what can be counted
and nothing else, so a clean page is not thereby a clear one. It flags

- PARA     a paragraph over ``--paragraph`` words
- ITEM     a list item over ``--paragraph`` words
- CELL     a ``list-table`` cell over ``--cell`` words
- SECTION  more than ``--section`` lines of prose under one heading
- DATE     an ISO date in prose or in a table cell

The bodies of directives other than ``list-table`` (doctests, code
blocks, notes) are not read. docs/AGENTS.md says what each finding
usually means and what the scan cannot see.

    uv run python tools/docs_scan.py                 # every page, counts
    uv run python tools/docs_scan.py locales.rst     # one page's findings
    uv run python tools/docs_scan.py --all           # every page's findings

It always exits 0: a finding is a place to look, not a failure.
"""
from __future__ import annotations

import argparse
import re
from pathlib import Path
from typing import NamedTuple

DOCS = Path(__file__).resolve().parents[1] / "docs"

#: Pages that are lists by nature, where length says nothing.
SKIPPED = frozenset({"release_log.rst", "modules.rst", "index.rst"})

PARAGRAPH_WORDS = 110
CELL_WORDS = 45
SECTION_LINES = 60

_UNDERLINE = re.compile(r"^([=\-~^\"])\1{3,}$")
_DATE = re.compile(r"\b20\d\d-\d\d-\d\d\b")
_ITEM = re.compile(r"^(?:[-*]|#\.|\d+\.) ")
_CELL = re.compile(r"\n\s+(?:\* )?- ")


class Finding(NamedTuple):
    line: int
    kind: str
    detail: str


def _excerpt(text: str, limit: int = 70) -> str:
    text = " ".join(text.split())
    return text if len(text) <= limit else text[:limit] + "..."


def _dates(text: str, line: int) -> list[Finding]:
    return [Finding(line, "DATE", f"{m.group()}: "
                    f"{_excerpt(text[max(0, m.start() - 40):m.end()])}")
            for m in _DATE.finditer(text)]


def scan(text: str, *, paragraph: int = PARAGRAPH_WORDS,
         cell: int = CELL_WORDS, section: int = SECTION_LINES
         ) -> list[Finding]:
    """The findings of one page's text, in line order."""
    lines = text.split("\n")
    # a heading is a non-blank line with an underline below it
    titles = {i for i in range(len(lines) - 1)
              if lines[i].strip() and _UNDERLINE.match(lines[i + 1])}
    found: list[Finding] = []
    heading, heading_line, prose = "(top of page)", 1, 0

    def close_section() -> None:
        if prose > section:
            found.append(Finding(
                heading_line, "SECTION",
                f"{prose} lines of prose under {heading!r}"))

    i = 0
    while i < len(lines):
        line = lines[i]
        if i in titles:
            close_section()
            heading, heading_line, prose = line.strip(), i + 1, 0
            i += 2
            continue
        if line.startswith(".. ") and not line.startswith(".. _"):
            # a directive: its body is the indented and blank lines below
            end = i + 1
            while end < len(lines) and (
                    not lines[end].strip() or lines[end].startswith(" ")):
                end += 1
            if line.startswith(".. list-table::"):
                body = "\n".join(lines[i:end])
                for content in _CELL.split(body)[1:]:
                    words = len(content.split())
                    if words > cell:
                        found.append(Finding(
                            i + 1, "CELL",
                            f"{words} words: {_excerpt(content)}"))
                    found.extend(_dates(content, i + 1))
            i = end
            continue
        if not line.strip() or line.startswith(".. _"):
            i += 1
            continue
        # a block of prose: up to the next blank line or heading
        end = i
        while end < len(lines) and lines[end].strip() and end not in titles:
            end += 1
        prose += end - i
        # a list holds one item per bullet at the block's own indent
        starts = [k for k in range(i, end) if _ITEM.match(lines[k])]
        if starts and starts[0] == i:
            for a, b in zip(starts, [*starts[1:], end]):
                item = " ".join(lines[a:b])
                words = len(item.split())
                if words > paragraph:
                    found.append(Finding(
                        a + 1, "ITEM", f"{words} words: {_excerpt(item)}"))
                found.extend(_dates(item, a + 1))
        elif not line.startswith(" "):
            block = " ".join(lines[i:end])
            words = len(block.split())
            if words > paragraph:
                found.append(Finding(
                    i + 1, "PARA", f"{words} words: {_excerpt(block)}"))
            found.extend(_dates(block, i + 1))
        i = end
    close_section()
    return sorted(found)


def pages(docs: Path = DOCS) -> list[Path]:
    """The pages scanned: every docs/*.rst but the ones that are lists."""
    return sorted(p for p in docs.glob("*.rst") if p.name not in SKIPPED)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=__doc__.split("\n", 1)[0],
        epilog="See the module docstring and docs/AGENTS.md.")
    parser.add_argument("page", nargs="*",
                        help="page names to list findings for, e.g. "
                             "locales.rst (default: counts only)")
    parser.add_argument("--all", action="store_true",
                        help="list every page's findings")
    parser.add_argument("--paragraph", type=int, default=PARAGRAPH_WORDS,
                        help="words in a paragraph or list item "
                             "(default %(default)s)")
    parser.add_argument("--cell", type=int, default=CELL_WORDS,
                        help="words in a table cell (default %(default)s)")
    parser.add_argument("--section", type=int, default=SECTION_LINES,
                        help="lines of prose under one heading "
                             "(default %(default)s)")
    parser.add_argument("--docs", type=Path, default=DOCS,
                        help="the docs folder (default: this checkout's)")
    args = parser.parse_args(argv)

    known = {p.name: p for p in pages(args.docs)}
    unknown = [name for name in args.page if name not in known]
    if unknown:
        parser.error(f"no such page to scan: {', '.join(unknown)}; "
                     f"choose from {', '.join(known)}")
    results = {
        name: scan(path.read_text(encoding="utf-8"),
                   paragraph=args.paragraph, cell=args.cell,
                   section=args.section)
        for name, path in known.items()}
    for name, found in sorted(results.items(),
                              key=lambda kv: (-len(kv[1]), kv[0])):
        kinds: dict[str, int] = {}
        for finding in found:
            kinds[finding.kind] = kinds.get(finding.kind, 0) + 1
        summary = ", ".join(f"{n} {k}" for k, n in sorted(kinds.items()))
        print(f"{name:22} {len(found):3}  {summary}")
    for name in (sorted(known) if args.all else args.page):
        print()
        for finding in results[name]:
            print(f"docs/{name}:{finding.line}: "
                  f"{finding.kind:8} {finding.detail}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
