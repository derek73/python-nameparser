"""The folder layout of docs/design/rules/ and docs/design/decisions/.

The one place that knows it: every other reader of the design docs goes
through these functions, so the parsers keep reading the text they
always read, and a change of layout is a change here.

Each folder holds a README.md whose Markdown links, in order, are the
index: one link per file, its text ``<key> — <name>``. A rule, a
section and a rule-keyed decisions entry are filed as
``<key>-<slug of the name>.md``; a decisions entry keyed by a slug is
filed under the slug alone, which already is a name. A citation names
the key only (``rules/S2``, ``decisions/vocabulary-collisions``), so
renaming a file never breaks one.
"""
from __future__ import annotations

import json
import re
import unicodedata
from dataclasses import dataclass
from pathlib import Path

DESIGN_DIR = Path(__file__).resolve().parents[2] / "docs" / "design"
RULES_DIR = DESIGN_DIR / "rules"
DECISIONS_DIR = DESIGN_DIR / "decisions"
MECHANISMS_DOC = DESIGN_DIR / "mechanisms.md"
#: rules order, the order the decisions index groups its entries in
SECTION_ORDER = "HPSNMCOWTARD"

# A citation: the folder and the key, or mechanisms.md and its slug. A
# key is not followed by a word character, nor by a hyphen and another
# word, which is how a file path in the rules folder (a stem like
# S6-case-signal-at-the-suffix-slot) is told from a citation, and a `.md`
# after it marks a file name (the README); a sentence's full stop is
# allowed, and so is a hyphen ending the line, where a comment wraps a
# long key. A decisions key starting with a
# digit (`3-0-reevaluations`) is not matched, as it was not before the
# split.
MENTION_RE = re.compile(
    r"(?:(?P<doc>rules|decisions)/|(?P<mdoc>mechanisms)\.md#)"
    r"(?P<cid>[A-Za-z][A-Za-z0-9_]*(?:-[A-Za-z0-9_]+)*)"
    r"(?![A-Za-z0-9_]|-[A-Za-z0-9_])(?!\.md\b)")

_LINK_RE = re.compile(r"\[(?P<title>[^\]]+)\]\((?P<file>[^)/]+\.md)\)")
_KEY_RE = re.compile(r"[^\s—,]+")
_SECTION_RE = re.compile(r"\(([A-Z])\)$")
_RULE_KEY_RE = re.compile(r"[A-Z]\d*")
_ARTICLE_RE = re.compile(r"^(?:a|an|the)\s+", re.IGNORECASE)


@dataclass(frozen=True)
class IndexEntry:
    key: str
    title: str      # the link text, "S6 — the case signal at the suffix slot"
    path: Path


def slugify(name: str) -> str:
    """A name as a file-name slug: `&` read as "and", one leading
    article dropped, an apostrophe dropped ("run's" is "runs"), folded
    to lowercase ASCII, every run of other characters one hyphen."""
    name = _ARTICLE_RE.sub("", name.replace("&", " and ").strip(' "\''))
    name = re.sub(r"(?<=\w)['’](?=\w)", "", name)
    ascii_name = (unicodedata.normalize("NFKD", name)
                  .encode("ascii", "ignore").decode())
    return re.sub(r"[^a-z0-9]+", "-", ascii_name.lower()).strip("-")


def stem_for(key: str, name: str) -> str:
    """The file stem for an entry: a rule or section key with its
    name's slug, any other key alone."""
    if _RULE_KEY_RE.fullmatch(key):
        return f"{key}-{slugify(name)}"
    return key


def read_index(folder: Path) -> list[IndexEntry]:
    text = (folder / "README.md").read_text(encoding="utf-8")
    entries = []
    for m in _LINK_RE.finditer(text):
        # a section is linked by its heading, "Suffixes: ... (S)"
        km = (_SECTION_RE.search(m.group("title"))
              or _KEY_RE.match(m.group("title")))
        assert km, f"{folder.name}/README.md: link without a key: {m[0]}"
        entries.append(IndexEntry(km.group(km.lastindex or 0),
                                  m.group("title"),
                                  folder / m.group("file")))
    return entries


def read_rules_text(folder: Path = RULES_DIR) -> str:
    """Every section and rule file, in index order, as one text."""
    return "\n".join(e.path.read_text(encoding="utf-8")
                     for e in read_index(folder))


def read_decision_files(folder: Path = DECISIONS_DIR) -> dict[str, str]:
    return {e.key: e.path.read_text(encoding="utf-8")
            for e in read_index(folder)}


def resolve(doc: str, cid: str, folder: Path | None = None) -> Path | None:
    """The one file a citation names, or None when none or several do."""
    if folder is None:
        folder = RULES_DIR if doc == "rules" else DECISIONS_DIR
    hits = [p for p in folder.glob("*.md") if p.name != "README.md"
            and (p.stem == cid or p.stem.startswith(cid + "-"))]
    return hits[0] if len(hits) == 1 else None


# A decisions file may open with `## Standing`, an index of the
# decisions in force, before its entries under `## Log`. Each Standing
# bullet ends its claim with the entry that decided it, by date and
# issue (`— 2026-10-06 #613`); a `Not standing:` line names entries a
# later one answered. An entry is a log bullet whose head
# (the text before its first ` — `) opens with exactly that date and
# whose first issue number is that one -- a head may name a later issue
# in a partial-supersession note, which must not answer for its own
# entry -- or, for a date-only pointer, the one entry of that date
# whose head names no issue; one whose text after the head opens with
# `SUPERSEDED by` is superseded, and a Standing pointer may not rest on
# it alone. An entry opening `SUPERSEDED:` or `SUPERSEDED IN PART:`
# announces what it replaces and is live.
_DATE = r"\d{4}-\d\d(?:-\d\d)?(?:/\d\d)?"
_POINTER_RE = re.compile(
    rf"(?P<date>{_DATE})(?![\d/-])(?:[^—#.;]{{0,40}}?#(?P<num>\d+))?")


def _entries(log: str) -> list[tuple[str, str]]:
    """Each log bullet as its head and the text after it."""
    out = []
    for line in log.splitlines():
        if re.match(r"- \d{4}-\d\d", line):
            head, _, rest = line[2:].partition(" — ")
            out.append((head, rest))
    return out


def _names(head: str, date: str, num: str | None) -> bool:
    m = re.match(_DATE, head)
    first = re.search(r"#(\d+)", head)
    return (m is not None and m.group(0) == date
            and (first.group(1) if first else None) == num)


def standing_findings(text: str) -> list[str]:
    """What is wrong with a decisions file's Standing block: a bullet
    with no `— <date>` pointer, any date-and-issue pointer from there
    to the line's end naming no entry (dates match exactly) or
    to one only `SUPERSEDED by` a later entry, a
    Not-standing pointer to no entry, a Standing with no Log. Empty
    for a file with no Standing block."""
    if "## Standing" not in text:
        return []
    if "\n## Log\n" not in text:
        return ["## Standing without a ## Log after it"]
    standing, log = text.split("## Standing", 1)[1].split("\n## Log\n", 1)
    entries = _entries(log)
    findings = []
    for line in standing.splitlines():
        if line.startswith("- "):
            dash = re.search(rf"— {_DATE}(?![\d/-])", line)
            if not dash:
                findings.append(f"no entry pointer: {line[:60]}")
                continue
            for m in _POINTER_RE.finditer(line, dash.start()):
                hits = [rest for head, rest in entries
                        if _names(head, m["date"], m["num"])]
                if not hits or (m["num"] is None and len(hits) > 1):
                    findings.append(f"no entry {m['date']} #{m['num']}")
                elif all(r.startswith("SUPERSEDED by") for r in hits):
                    findings.append(
                        f"superseded entry {m['date']} #{m['num']}")
        elif line.startswith("Not standing:"):
            for m in _POINTER_RE.finditer(line):
                if not any(_names(head, m["date"], m["num"])
                           for head, _ in entries):
                    findings.append(
                        f"not-standing names no entry {m['date']} "
                        f"#{m['num']}")
    return findings


#: The decisions files allowed to lack a Standing block: every file
#: older than the 2026-10-19 rule that new files open with one. The
#: list only shrinks (decisions/README.md, `## Standing`).
STANDING_EXEMPT = Path(__file__).with_name("decisions_without_standing.json")


def read_standing_exempt(path: Path = STANDING_EXEMPT) -> set[str]:
    return set(json.loads(path.read_text(encoding="utf-8"))["exempt"])


def standing_roster_findings(files: dict[str, str],
                             exempt: set[str]) -> list[str]:
    """What breaks the Standing ratchet: a file off the exempt list with
    no Standing block, a listed file that has gained one (take it off
    the list), and a listed key no file carries any more."""
    findings = []
    for key, text in sorted(files.items()):
        has = "## Standing" in text
        if key in exempt and has:
            findings.append(f"{key} has a Standing block: take it off "
                            f"{STANDING_EXEMPT.name}")
        elif key not in exempt and not has:
            findings.append(f"{key} has no Standing block: a new decisions "
                            "file opens with ## Standing and ## Log")
    for key in sorted(exempt - files.keys()):
        findings.append(f"{key} is listed in {STANDING_EXEMPT.name} "
                        "but no decisions file carries it")
    return findings
