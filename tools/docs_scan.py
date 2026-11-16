"""List the places in docs/*.rst a reader is likely to get lost.

A mechanical scan, for candidates only: it finds what can be counted
and nothing else, so a clean page is not thereby a clear one. It flags

- PARA     a paragraph over ``--paragraph`` words
- ITEM     a list item's paragraph over ``--paragraph`` words
- CELL     a ``list-table`` cell over ``--cell`` words
- SECTION  more than ``--section`` lines of prose under one heading
- DATE     an ISO date in a paragraph, a list item or a table cell

What it reads: paragraphs and list items at any indent, the bodies of
admonitions (``note``, ``warning`` and the like) and the cells of a
``list-table``. What it does not: every other directive's body
(doctests, code blocks), a literal block after ``::``, a comment, and
a grid or simple table. docs/AGENTS.md says what each finding usually
means and what no scan can see.

    uv run python tools/docs_scan.py                 # every page, counts
    uv run python tools/docs_scan.py locales.rst     # one page's findings
    uv run python tools/docs_scan.py --all           # every page's findings

It exits 0 whatever it finds: a finding is a place to look, not a
failure. A docs folder with no page to scan is an error.
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

#: The directives whose body is prose a reader reads.
ADMONITIONS = frozenset({
    "note", "warning", "tip", "important", "caution", "attention",
    "danger", "error", "hint", "seealso", "admonition", "versionadded",
    "versionchanged", "deprecated"})

# an RST adornment: one punctuation character repeated
_ADORNMENT = re.compile(r"^([!-/:-@\[-`{-~])\1{2,}\s*$")
_DATE = re.compile(r"\b20\d\d-\d\d-\d\d\b")
_ITEM = re.compile(r"^(\s*)(?:[-*+]|#\.|\d+\.) ")
_DIRECTIVE = re.compile(r"^(\s*)\.\. ([\w-]+)::")
_ROW = re.compile(r"^(\s*)\* - ")


class Finding(NamedTuple):
    line: int
    kind: str
    detail: str


def _excerpt(text: str, limit: int = 70) -> str:
    text = " ".join(text.split())
    return text if len(text) <= limit else text[:limit] + "..."


def _indent(line: str) -> int:
    return len(line) - len(line.lstrip(" "))


class _Scan:
    def __init__(self, lines: list[str], paragraph: int, cell: int,
                 section: int) -> None:
        self.lines = lines
        self.paragraph, self.cell, self.section = paragraph, cell, section
        self.found: list[Finding] = []
        # a heading is a text line with an adornment below it at least as
        # long as the text, and perhaps the same adornment above it
        self.titles: dict[int, int] = {}       # first line -> lines it spans
        for i in range(len(lines) - 1):
            text, under = lines[i], lines[i + 1]
            if (text.strip() and not _ADORNMENT.match(text)
                    and _ADORNMENT.match(under)
                    and len(under.rstrip()) >= len(text.rstrip())):
                over = i > 0 and lines[i - 1].rstrip() == under.rstrip()
                self.titles[i - 1 if over else i] = 3 if over else 2
        self.heading, self.heading_line, self.prose = "(top of page)", 1, 0

    def _measure(self, kind: str, text: str, line: int) -> None:
        words = len(text.split())
        if words > self.paragraph:
            self.found.append(Finding(
                line, kind, f"{words} words: {_excerpt(text)}"))
        self._dates(text, line)

    def _dates(self, text: str, line: int) -> None:
        for m in _DATE.finditer(text):
            self.found.append(Finding(
                line, "DATE", f"{m.group()}: "
                f"{_excerpt(text[max(0, m.start() - 40):m.end()])}"))

    def _body_end(self, start: int, indent: int) -> int:
        """The line after the block indented deeper than `indent` that
        begins at `start`."""
        end = start
        while end < len(self.lines) and (
                not self.lines[end].strip()
                or _indent(self.lines[end]) > indent):
            end += 1
        return end

    def _close_section(self) -> None:
        if self.prose > self.section:
            self.found.append(Finding(
                self.heading_line, "SECTION",
                f"{self.prose} lines of prose under {self.heading!r}"))

    def _table(self, start: int, end: int) -> None:
        """Each cell of the list-table whose body is lines[start:end]."""
        cells: list[tuple[int, list[str]]] = []
        dash = -1
        for k in range(start, end):
            line = self.lines[k]
            row = _ROW.match(line)
            if row and (dash < 0 or len(row.group(1)) + 2 == dash):
                dash = len(row.group(1)) + 2
                cells.append((k, [line[dash + 2:]]))
            elif dash >= 0 and line.startswith(" " * dash + "- "):
                cells.append((k, [line[dash + 2:]]))
            elif cells:
                cells[-1][1].append(line)
        for k, content in cells:
            text = " ".join(content)
            words = len(text.split())
            if words > self.cell:
                self.found.append(Finding(
                    k + 1, "CELL", f"{words} words: {_excerpt(text)}"))
            self._dates(text, k + 1)

    def run(self) -> list[Finding]:
        lines = self.lines
        i = 0
        literal = -1      # the indent a literal block must exceed, or -1
        while i < len(lines):
            line = lines[i]
            if i in self.titles:
                self._close_section()
                span = self.titles[i]
                self.heading = lines[i + span - 2].strip()
                self.heading_line, self.prose, literal = i + span - 1, 0, -1
                i += span
                continue
            if not line.strip():
                i += 1
                continue
            indent = _indent(line)
            if literal >= 0:
                if indent > literal:          # the literal block's text
                    i = self._body_end(i, literal)
                    literal = -1
                    continue
                literal = -1
            directive = _DIRECTIVE.match(line)
            if directive:
                end = self._body_end(i + 1, indent)
                name = directive.group(2)
                if name == "list-table":
                    self._table(i + 1, end)
                    i = end
                elif name in ADMONITIONS:
                    i += 1                    # its body is read as prose
                else:
                    i = end
                continue
            if line.lstrip().startswith(".."):
                # a label, a substitution or a comment: no prose in it
                i = (i + 1 if re.match(r"\s*\.\. (_|\|)", line)
                     else self._body_end(i + 1, indent))
                continue
            # a block of prose: up to the next blank line or heading
            end = i
            while end < len(lines) and lines[end].strip() \
                    and end not in self.titles:
                end += 1
            self.prose += end - i
            item = _ITEM.match(line)
            if item:
                # one item per marker at the block's own indent
                starts = [k for k in range(i, end)
                          if (m := _ITEM.match(lines[k]))
                          and len(m.group(1)) == len(item.group(1))]
                for a, b in zip(starts, [*starts[1:], end]):
                    self._measure("ITEM", " ".join(lines[a:b]), a + 1)
            else:
                self._measure("ITEM" if indent else "PARA",
                              " ".join(lines[i:end]), i + 1)
            if lines[end - 1].rstrip().endswith("::"):
                literal = indent
            i = end
        self._close_section()
        return sorted(self.found)


def scan(text: str, *, paragraph: int = PARAGRAPH_WORDS,
         cell: int = CELL_WORDS, section: int = SECTION_LINES
         ) -> list[Finding]:
    """The findings of one page's text, in line order."""
    return _Scan(text.splitlines(), paragraph, cell, section).run()


def pages(docs: Path = DOCS) -> list[Path]:
    """The pages scanned: every docs/*.rst but the ones that are lists."""
    return sorted(p for p in docs.glob("*.rst") if p.name not in SKIPPED)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=(__doc__ or "").split("\n", 1)[0],
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
    if not known:
        parser.error(f"no page to scan in {args.docs}: it holds no .rst "
                     f"file but the skipped ones; pass --docs <folder>")
    for name in args.page:
        if name in SKIPPED:
            parser.error(f"{name} is not scanned, being a list by nature; "
                         f"choose from {', '.join(known)}")
        if name not in known:
            parser.error(f"no such page to scan: {name}; "
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
