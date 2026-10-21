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


# A rule ID is never reused (rules/README.md). A retired rule's file
# leaves rules/, and its decisions file records the retirement on a line
# of its own opening `Retired:`; a rule file carrying that ID again is
# refused. A line that means `Retired:` and misspells it (bold, a list
# marker or number, lowercase) would switch the refusal off for its ID, so it is a
# finding too.
_RETIRED_RE = re.compile(r"^Retired:", re.M)
_NEAR_RETIRED = re.compile(
    r"^[ \t>*_+-]*(?:\d+[.)][ \t]*)?retired[ \t*_]*:.*$", re.M | re.I)


def rule_file_ids(folder: Path = RULES_DIR) -> set[str]:
    """The ID of every rule and section file in the folder, read from
    the file names rather than the index, so a file the index misses is
    still counted."""
    return {p.stem.split("-", 1)[0] for p in folder.glob("*.md")
            if p.name != "README.md"
            and _RULE_KEY_RE.fullmatch(p.stem.split("-", 1)[0])}


def retired_ids(decisions: dict[str, str]) -> set[str]:
    """The keys of the decisions files that record a retirement."""
    return {key for key, text in decisions.items()
            if _RETIRED_RE.search(text)}


def reused_id_findings(rule_ids: set[str],
                       decisions: dict[str, str]) -> list[str]:
    """What breaks never-reused: a rule file whose ID a decisions file
    records as retired, a `Retired:` line in a decisions file keyed by
    no rule ID (it retires nothing), and a line misspelling `Retired:`."""
    findings = []
    for key, text in sorted(decisions.items()):
        for m in _NEAR_RETIRED.finditer(text):
            if not m.group(0).startswith("Retired:"):
                findings.append(f"decisions/{key}: {m.group(0)!r} is not "
                                "a line opening 'Retired:'")
    for key in sorted(retired_ids(decisions)):
        if not _RULE_KEY_RE.fullmatch(key):
            findings.append(f"decisions/{key} carries a Retired: line but "
                            "is keyed by no rule ID, so it retires nothing")
        elif key in rule_ids:
            findings.append(f"rules/{key} reuses an ID decisions/{key} "
                            "records as retired: a new rule takes a new ID")
    return findings


# A decisions file carries `## Standing`, an index of the decisions in
# force, ahead of its entries under `## Log` -- every file but those
# listed in decisions_without_standing.json (below). Each Standing
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


def _hits(line: str, m: re.Match[str],
          entries: list[tuple[str, str]]) -> list[str]:
    """The log entries one pointer names. A date-only pointer may carry
    the opening of its entry's head after the date (`— 2026-09-14
    (Derek)`), which tells apart entries that share a date and name no
    issue; text that matches no head is ordinary prose and narrows
    nothing."""
    hits = [(head, rest) for head, rest in entries
            if _names(head, m["date"], m["num"])]
    if m["num"] is None and len(hits) > 1:
        said = m["date"] + re.split(r"[.;]", line[m.end():], 1)[0].rstrip()
        # Only a head carrying words past its date can be named by them,
        # so a bare-date head never matches a qualified pointer.
        narrowed = [(head, rest) for head, rest in hits
                    if len(head) > len(m["date"]) and len(said) > len(m["date"])
                    and (said.startswith(head) or head.startswith(said))]
        hits = narrowed or hits
    return [rest for _, rest in hits]


_STANDING_HEADING = re.compile(r"^## Standing$", re.M)
_LOG_HEADING = re.compile(r"^## Log$", re.M)
# A line that means the heading and misspells it: the exact match would
# miss it and switch every Standing check off for the file.
_NEAR_STANDING = re.compile(r"^[ \t]*#{1,6}[ \t]*standing\b.*$",
                            re.M | re.I)


def misspelled_standing(text: str) -> list[str]:
    """The lines that try to be the Standing heading and are not it."""
    return [m.group(0) for m in _NEAR_STANDING.finditer(text)
            if m.group(0) != "## Standing"]


def has_standing(text: str) -> bool:
    """Whether a decisions file carries a Standing block: the heading on
    a line of its own, not the words quoted in prose."""
    return _STANDING_HEADING.search(text) is not None


def standing_findings(text: str) -> list[str]:
    """What is wrong with a decisions file's Standing block: a bullet
    with no `— <date>` pointer, any date-and-issue pointer from there
    to the line's end naming no entry (dates match exactly) or
    to one only `SUPERSEDED by` a later entry, a
    Not-standing pointer to no entry, a Standing with no Log after it.
    Empty for a file with no Standing block, whose absence is
    standing_roster_findings' question."""
    head = _STANDING_HEADING.search(text)
    if head is None:
        return []
    if _LOG_HEADING.search(text, 0, head.start()):
        return ["## Log before ## Standing: the block opens the file"]
    log_head = _LOG_HEADING.search(text, head.end())
    if log_head is None:
        return ["## Standing without a ## Log after it"]
    standing, log = text[head.end():log_head.start()], text[log_head.end():]
    entries = _entries(log)
    findings = []
    for line in standing.splitlines():
        if line.startswith("- "):
            dash = re.search(rf"— {_DATE}(?![\d/-])", line)
            if not dash:
                findings.append(f"no entry pointer: {line[:60]}")
                continue
            for m in _POINTER_RE.finditer(line, dash.start()):
                hits = _hits(line, m, entries)
                if not hits or (m["num"] is None and len(hits) > 1):
                    findings.append(f"no entry {m['date']} #{m['num']}")
                elif all(r.startswith("SUPERSEDED by") for r in hits):
                    findings.append(
                        f"superseded entry {m['date']} #{m['num']}")
        elif line.startswith("Not standing:"):
            for m in _POINTER_RE.finditer(line):
                if not _hits(line, m, entries):
                    findings.append(
                        f"not-standing names no entry {m['date']} "
                        f"#{m['num']}")
    return findings


#: The decisions files allowed to lack a Standing block: every file
#: created before the rule, C1's block landing on 2026-10-19
#: (decisions/README.md, `## Standing`). It never holds a key it did not
#: hold when the rule landed.
STANDING_EXEMPT = Path(__file__).with_name("decisions_without_standing.json")
#: The list as recorded when the rule landed. Never edited: the list
#: must stay inside it, so a new file cannot join the list, alone or in
#: exchange for one that leaves it.
STANDING_EXEMPT_ORIGINAL = frozenset({
    '3-0-reevaluations', 'A1', 'A2', 'C10', 'C11', 'C12', 'C3', 'C4',
    'C5', 'C6', 'C7', 'C8', 'C9', 'D1', 'D2', 'H1', 'H2', 'H3', 'H4',
    'H5', 'H6', 'M1', 'M2', 'M3', 'M4', 'N1', 'N2', 'N3', 'O1', 'O2',
    'O4', 'O5', 'P1', 'P2', 'P3', 'P5', 'P6', 'P7', 'R1', 'R2', 'R3',
    'R4', 'R5', 'S10', 'S2', 'S3', 'S4', 'S5', 'S6', 'S7', 'S8', 'S9',
    'T1', 'T3', 'T4', 'W1', 'W2', 'W3', 'W4', 'api-churn-declines',
    'cjk-comma-demotion', 'cjk-full-stops', 'comma-suffix-arc',
    'comparison-surface', 'deviates-registry', 'differential-ledger',
    'generational-words', 'given-name-titles', 'indic-honorifics',
    'initials-repertoire', 'legacy-rule-numbers', 'ma-do', 'nfd-shapes',
    'normalization-fold', 'parse-cost', 'phd-merge',
    'removed-v1-surface', 'render-default',
    'review-agent-single-source', 'salutation-titles',
    'script-table-placement', 'suffix-acronym-collisions',
    'suffix-field-composition', 'two-input-invariants',
    'v1-xfail-triage', 'vocabulary-collisions', 'vocabulary-exclusions',
    'vocabulary-model'})


def read_standing_exempt(path: Path = STANDING_EXEMPT) -> set[str]:
    return set(json.loads(path.read_text(encoding="utf-8"))["exempt"])


def standing_roster_findings(
        files: dict[str, str], exempt: set[str],
        original: frozenset[str] = STANDING_EXEMPT_ORIGINAL) -> list[str]:
    """What breaks the Standing ratchet: a file off the exempt list with
    no Standing block, a listed file that has gained one (take it off
    the list), a listed key no file carries any more, a listed key the
    list did not hold when the rule landed, and a heading that misspells
    `## Standing`."""
    findings = []
    for key, text in sorted(files.items()):
        for line in misspelled_standing(text):
            findings.append(f"{key}: {line!r} is not the heading "
                            "'## Standing'")
    for key in sorted(exempt - original):
        findings.append(f"{key} is listed in {STANDING_EXEMPT.name} but "
                        "was not on it when the rule landed: a new "
                        "decisions file opens with ## Standing instead")
    for key, text in sorted(files.items()):
        has = has_standing(text)
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
