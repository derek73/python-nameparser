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

import re
import unicodedata
from collections.abc import Set as AbstractSet
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
# force, ahead of its entries under `## Log` -- every file but the
# reference lists (below). Each Standing
# bullet ends its claim with the entry that decided it, by date and
# issue (`— 2026-10-06 #613`) or by date alone; a `Not standing:` line
# names entries a later one answered. An entry is a log bullet opening
# with its date, bare or in bold (`- **2026-10-14 #679 — …**`), and its
# head is the text before its first ` — `, read without any
# parenthesized note saying part of it was superseded (README edit kind
# 1). A pointer's candidates are the entries whose head opens with
# exactly its date and whose first issue is its issue -- for a date-only
# pointer, whose head names no issue. Where several are candidates, the
# words after the pointer pick the one whose head continues with them,
# the longest such continuation winning (`— 2026-09-14 (Derek)`,
# `— 2026-10-18 #718 review`); a date inside those words is part of
# them, not a second pointer. A pointer with no words names the
# candidate whose head ends there, and one whose words continue no
# candidate's head is a finding, since nothing tells a typo from prose
# there. Where heads are the same words (twins), the words past the
# head pick the entry whose text opens with them, also where another
# head of that date and issue continues past those words
# (`— 2026-09-13 #383/#479, AMENDS`): there the words are a key, not
# prose. A pointer still naming more than one entry is ambiguous. An
# entry whose text after the head opens with `SUPERSEDED by` is
# superseded, and a Standing pointer may not rest on it; one opening
# `SUPERSEDED:` or `SUPERSEDED IN PART:` announces what it replaces and
# is live. A file's title is never read as an entry
# (`test_a_dated_title_founds_no_entry`); decisions/README.md says how
# a bundle of undated bullets gains a dated line to point at.
_DATE = r"\d{4}-\d\d(?:-\d\d)?(?:/\d\d)?"
# The issue is the first `#N` within 40 characters of the date that no
# `—`, `.`, `;` or other date interrupts, so a head copied whole
# (`2026-10-18 (Derek), #718`) still reads its issue and `— 2026-10-19,
# 2026-10-18 #721` stays two pointers; an issue written in prose
# right after a date-only pointer (`— 2026-09-14, see #500`) is read as
# the pointer's and fails as no entry, so end the pointer first.
_POINTER_RE = re.compile(
    rf"(?P<date>{_DATE})(?![\d/-])"
    rf"(?:(?:(?!\d{{4}}-\d\d)[^—#.;]){{0,40}}?#(?P<num>\d+))?")


_ENTRY_RE = re.compile(r"- (?:\*\*)?(?=\d{4}-\d\d)")


def _entries(log: str) -> list[tuple[str, str]]:
    """Each log bullet as its head and the text after it. A bold
    head's markers are not part of it (`- **2026-10-14 #679** (Derek) —
    x` has the head `2026-10-14 #679 (Derek)`); with no ` — ` in the
    line, a bold head ends where its bold closes and the text follows
    it (`- **2026-10-15 #5**: text`); and a bold opening the text is
    not part of it, so `— **SUPERSEDED by** …` still marks the entry."""
    out = []
    for line in log.splitlines():
        m = _ENTRY_RE.match(line)
        if m:
            body = line[m.end():]
            head, dash, rest = body.partition(" — ")
            if m.group(0).endswith("**"):
                if not dash and "**" in body:
                    head, _, rest = body.partition("**")
                    rest = rest.lstrip(": ")
                head = head.replace("**", "")
            out.append((head, rest.removeprefix("**")))
    return out


def _clean(head: str) -> str:
    """A head without its parenthesized supersession notes, which can
    hold parentheses of their own (`(item (ii) superseded by …)`); the
    word is matched in any case, and a parenthesis never closed is
    text, not a note."""
    out: list[str] = []
    i = 0
    while i < len(head):
        if head[i] == "(":
            depth, j = 0, i
            while j < len(head):
                depth += {"(": 1, ")": -1}.get(head[j], 0)
                if depth == 0:
                    break
                j += 1
            if depth == 0 and "superseded" in head[i:j + 1].lower():
                while out and out[-1] == " ":
                    out.pop()
                i = j + 1
                continue
        out.append(head[i])
        i += 1
    return "".join(out)


def _names(head: str, date: str, num: str | None) -> bool:
    head = _clean(head)
    m = re.match(_DATE, head)
    first = re.search(r"#(\d+)", head)
    return (m is not None and m.group(0) == date
            and (first.group(1) if first else None) == num)


def _tail(head: str, date: str, num: str | None) -> str:
    """What a head says after the date or issue a pointer names. Asked
    only of a candidate, whose head holds that issue by `_names`."""
    head = _clean(head)
    if num is None:
        return head[len(date):]
    at = re.search(rf"#{num}(?!\d)", head)
    assert at is not None
    return head[at.end():]


@dataclass(frozen=True)
class _Resolved:
    hits: list[tuple[str, str]]   # the entries named, as (head, rest)
    used: int                     # characters of the line the pick read
    unmatched: str = ""           # words that continue no candidate


def _resolve(line: str, m: re.Match[str],
             entries: list[tuple[str, str]]) -> _Resolved:
    """The log entries one pointer names."""
    date, num = m["date"], m["num"]
    found = [e for e in entries if _names(e[0], date, num)]
    after = line[m.end():]
    if len(found) < 2:
        return _Resolved(found, _read(after, found, date, num))
    # The words end at `.` or `;`, or where the next pointer's date
    # starts (`— 2026-10-17 #718, 2026-10-18 #721`).
    said = re.split(rf"[.;]|{_DATE}", after, maxsplit=1)[0].rstrip(" ,")
    tails = {e: _tail(e[0], date, num) for e in found}
    # The whole rest of the line is matched, so a period or a date
    # inside a head's words is read as part of them.
    whole = [e for e in found if tails[e] and after.startswith(tails[e])]
    if whole:
        longest = max(len(tails[e]) for e in whole)
        hits = [e for e in whole if len(tails[e]) == longest]
        used = longest
    else:
        cut = [e for e in found if said and tails[e].startswith(said)]
        if cut:
            hits, used = cut, len(said)
        elif said:
            # Words past a bare head are a twin key where two or more
            # heads end at the pointer, though another head continues.
            bare = [e for e in found if not tails[e]]
            if not bare or (len(bare) < 2
                            and len({_clean(h) for h, _ in found}) > 1):
                return _Resolved([], 0, said)
            hits, used = bare, 0
        else:
            hits = [e for e in found if not tails[e]] or found
            used = 0
    if len(hits) > 1 and len({_clean(head) for head, _ in hits}) == 1:
        # Twins: entries whose heads are the same words. What the
        # pointer says past the head names one by how its text opens.
        words = said[len(tails[hits[0]]):].lstrip(" ,")
        twin = [e for e in hits if words and e[1].startswith(words)]
        hits = twin or hits
    return _Resolved(hits, max(used, _read(after, hits, date, num)))


def _read(after: str, hits: list[tuple[str, str]], date: str,
          num: str | None) -> int:
    """How much of the line the one entry named was read as its head's
    words -- however much of them the pointer wrote -- so a date among
    them is not taken for a second pointer."""
    if len(hits) != 1:
        return 0
    tail = _tail(hits[0][0], date, num)
    n = 0
    while n < min(len(after), len(tail)) and after[n] == tail[n]:
        n += 1
    return n


def _hits(line: str, m: re.Match[str],
          entries: list[tuple[str, str]]) -> list[tuple[str, str]]:
    """The log entries one pointer names, as (head, rest) pairs."""
    return _resolve(line, m, entries).hits


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
    with no `— <date>` pointer, any pointer from there to the line's
    end naming no entry (dates match exactly), carrying words that
    continue no candidate's head where its date and issue are shared,
    naming more than one (ambiguous), or naming a `SUPERSEDED by` entry;
    a Not-standing pointer naming no entry, carrying such words or
    naming more than one (a superseded entry is what it may name); a
    Standing with no Log after it.
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
            read_to = 0
            for m in _POINTER_RE.finditer(line, dash.start()):
                if m.start() < read_to:   # a date inside a pick's words
                    continue
                got = _resolve(line, m, entries)
                hits, read_to = got.hits, m.end() + got.used
                if got.unmatched:
                    findings.append(
                        f"pointer {m['date']} #{m['num']}: "
                        f"{got.unmatched!r} continues no entry's head")
                elif not hits:
                    findings.append(f"no entry {m['date']} #{m['num']}")
                elif len(hits) > 1:
                    findings.append(
                        f"ambiguous pointer {m['date']} #{m['num']}: add "
                        "the words its entry's head continues with")
                elif any(r.startswith("SUPERSEDED by") for _, r in hits):
                    findings.append(
                        f"superseded entry {m['date']} #{m['num']}")
        elif line.startswith("Not standing:"):
            read_to = 0
            for m in _POINTER_RE.finditer(line):
                if m.start() < read_to:
                    continue
                got = _resolve(line, m, entries)
                read_to = m.end() + got.used
                if got.unmatched:
                    findings.append(
                        f"not-standing pointer {m['date']} #{m['num']}: "
                        f"{got.unmatched!r} continues no entry's head")
                elif not got.hits:
                    findings.append(
                        f"not-standing names no entry {m['date']} "
                        f"#{m['num']}")
                elif len(got.hits) > 1:
                    findings.append(
                        f"ambiguous not-standing pointer {m['date']} "
                        f"#{m['num']}: add the words its entry's head "
                        "continues with")
    return findings


# A reference list -- a file of Declined, Excluded, Open, removal or
# mapping lines, each already saying what stands -- carries no Standing
# block, which would copy it. The decisions index names them under this
# heading, and only the five in REFERENCE_LISTS may be listed: a new
# decisions file opens with ## Standing whatever it holds (#762). A
# file there may not take a log's shapes: a dated entry, a bullet
# opening with a tag and a date (`- (A) 2026-08-17 — …`, as
# 3-0-reevaluations writes its log), or a dated title (a bundle, as
# cjk-full-stops is). A log written in none of those shapes is caught
# only in review.
_REFERENCE_HEADING = "## Reference lists"
#: The reference lists, fixed when #762 finished giving every other
#: decisions file a Standing block (2026-10-22).
REFERENCE_LISTS = frozenset({
    'api-churn-declines', 'given-name-titles', 'legacy-rule-numbers',
    'removed-v1-surface', 'vocabulary-exclusions'})
_LOG_SHAPED = re.compile(
    r"^- (?:\*\*)?(?:\([^)\n]{1,12}\) )?(?=\d{4}-\d\d)|\A# [^\n]*\d{4}-\d\d",
    re.M)


def reference_lists(readme: str) -> set[str]:
    """The keys the index lists, one bullet each (`- [key — …](…)`),
    under its Reference lists heading, a `## ` line of its own; a link
    in its prose, or one a bullet holds after other words, is no
    listing."""
    at = readme.find(f"\n{_REFERENCE_HEADING}\n")
    if at < 0:
        return set()
    end = readme.find("\n## ", at + 1)
    section = readme[at:end if end >= 0 else len(readme)]
    return {km.group(0) for line in section.splitlines()
            if (m := _LINK_RE.match(line, 2)) and line.startswith("- [")
            and (km := _KEY_RE.match(m.group("title")))}


def read_reference_lists(folder: Path = DECISIONS_DIR) -> set[str]:
    return reference_lists((folder / "README.md").read_text(encoding="utf-8"))


def standing_roster_findings(
        files: dict[str, str], reference: AbstractSet[str],
        allowed: AbstractSet[str] = REFERENCE_LISTS) -> list[str]:
    """What breaks the Standing rule: a file with no Standing block that
    is not a reference list, and a heading that misspells
    `## Standing`; and of a reference list, a Standing block, a log's
    shape (a dated or tagged-date bullet, a dated title), or a key
    outside the fixed set."""
    findings = []
    for key in sorted(reference & files.keys()):
        text = files[key]
        if has_standing(text):
            findings.append(f"{key} is a reference list and carries "
                            "## Standing: index a log under its section")
        if _LOG_SHAPED.search(text):
            findings.append(f"{key} is a reference list but is shaped "
                            "like a log (a dated entry or title): a log "
                            "opens with ## Standing")
    for key in sorted(reference - allowed):
        findings.append(f"{key} is under Reference lists but is not one "
                        "of REFERENCE_LISTS: a decisions file opens with "
                        "## Standing")
    for key, text in sorted(files.items()):
        for line in misspelled_standing(text):
            findings.append(f"{key}: {line!r} is not the heading "
                            "'## Standing'")
    for key, text in sorted(files.items()):
        if key not in reference and not has_standing(text):
            findings.append(f"{key} has no Standing block: a decisions "
                            "file opens with ## Standing and ## Log")
    return findings
