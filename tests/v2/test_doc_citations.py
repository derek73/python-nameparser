"""Referential integrity for docs/design/ citations.

Checks: every reference to a design doc, in code and in the
differential ledgers' comments, names a rule, section, mechanism or
decisions entry that exists; every quote a citation carries -- in any
of the shapes _LEAD_RE accepts, chained quotes included -- is a
whitespace-normalized verbatim excerpt of what it cites ("[...]"
eliding, in order): a rule's statement and Accepted: clauses, a
section's Background, a mechanism's Contract statement, a decisions
entry's text;
``implemented:`` lists match the set of modules actually citing the
rule; ``interacts:`` IDs exist (existence only -- the field is
advisory). The legacy-pattern check (armed) keeps gitignored-spec
citation forms out of the committed tree.
"""
from __future__ import annotations

import re
from pathlib import Path
from typing import NamedTuple

from tests.v2.rules_doc import (
    _POINTER_RE, _RULE_RE, RULES_DOC, parse_rules_doc)

REPO = Path(__file__).resolve().parents[2]
MECH_DOC = REPO / "docs" / "design" / "mechanisms.md"
SWEEP_DIRS = ("nameparser", "tests", "tools")
ENFORCE_NO_LEGACY = True    # armed 2026-08-15, the rewrite complete
_LEGACY_RES = (re.compile(r"§"), re.compile(r"superpowers"),
               re.compile(r"plan[\s#]+deviation"),
               re.compile(r"spec\s+[S§]?\d"))

# A reference to a design doc: the doc and the ID or entry key. A
# decisions.md key may be a lowercase slug ('suffix-acronym-collisions').
_MENTION_RE = re.compile(
    r"(?P<doc>rules|mechanisms|decisions)\.md#"
    r"(?P<cid>[A-Za-z][A-Za-z0-9_]*(?:-[A-Za-z0-9_]+)*)")
# A reference is a CITATION when a quote follows it in one of the
# shapes the tree writes: the colon form (`rules.md#S2: "..."`, where
# prose may stand before the quote), or the ID, an optional "'s", up
# to four words and a dash, colon, comma or parenthesis, then the
# quote (`rules.md#P5 -- "..."`, `rules.md#M2's Accepted clause
# ("...")`, `rules.md#S2 consumes "..."`, `rules.md#M2 -- the
# numeral is taken "..."`). Any other reference is a
# pointer, which must still name something that exists.
_COLON_RE = re.compile(r"\s*:")
_LEAD_RE = re.compile(
    r"(?:'s)?(?:\s*(?:--|—))?(?:\s+[A-Za-z]+){0,4}?"
    r"\s*(?:--|—|[:,(])?\s*(?=\")")
# A quote, and the quotes chained to it by "and", a comma or a dash:
# every one of them is part of the citation and must be verbatim.
_QUOTE_RE = re.compile(r'"([^"]*)"')
_CHAIN_RE = re.compile(r'\s*,?\s*(?:and\s+|--\s*|—\s*)?(?=")')
# An excerpt may elide with "[...]": each fragment must then be
# verbatim, non-empty, and in order.
_ELISION = "[...]"
DEC_DOC = REPO / "docs" / "design" / "decisions.md"
# Ledger comments cite rules under the same discipline as code
# (AGENTS.md, "Release-log claims"); they are swept with the code but
# are not "citing modules" -- rules.md's implemented: names parser
# modules, never ledgers.
_LEDGERS = REPO / "tools" / "differential"


class Citation(NamedTuple):
    path: Path
    line: int
    doc: str
    cid: str
    excerpts: tuple[str, ...]   # normalized; () for a pointer
    colon: bool                 # written in the colon form


def _norm(s: str) -> str:
    # "--" is how an ASCII comment spells the em dash the docs use, and
    # a quote nested in a quoted excerpt can only be written single
    s = s.replace(" -- ", " — ").replace('"', "'")
    return " ".join(s.split()).lower()


def _statements() -> dict[str, str]:
    """What a citation may quote: for a rule, its prose -- the
    statement and its Accepted: clauses, everything in the block but
    example, pointer and marker lines; for a section letter
    (`rules.md#H Background`), the section's Background paragraph; for
    a mechanism, its Contract statement."""
    out: dict[str, list[str]] = {}
    current: list[str] | None = None
    section = None
    for line in RULES_DOC.read_text(encoding="utf-8").splitlines():
        m = _RULE_RE.match(line)
        hm = re.match(r"## .*\(([A-Z])\)\s*$", line)
        if hm:
            section = hm.group(1)
        elif section and line.startswith("Background:"):
            out[section] = [line]
            section = None
        if m:
            current = out.setdefault(m.group(1) + m.group(2), [])
            current.append(line[m.end():])
        elif line.startswith("#"):
            current = None
        elif current is not None and line.startswith("    ") and not (
                line.startswith("      ") or _POINTER_RE.match(line)
                or re.match(r"\s*(no-boundary|tolerated):", line)):
            current.append(line)
    stmts = {rid: _norm(" ".join(body)) for rid, body in out.items()}
    mech = MECH_DOC.read_text(encoding="utf-8")
    # split into sections first so a missing Contract line cannot
    # bleed into the next section's statement
    for sec in re.split(r"^(?=#{2,3} )", mech, flags=re.M):
        hm = re.match(r"#{2,3} (?P<slug>[A-Z][A-Z0-9_-]+)(?=[\s—-])", sec)
        if not hm:
            continue
        cm = re.search(r"Contract statement[.:*]*\s*(?P<stmt>.+?)(?=\n\n|\Z)",
                       sec, flags=re.S)
        if cm:
            stmts[hm.group("slug")] = _norm(cm.group("stmt"))
    return stmts


def _decision_entries() -> dict[str, str]:
    """decisions.md entry bodies keyed by their ### key. An entry is a
    dated record rather than a statement, so a citation of one need
    not quote it; but what it does quote must be verbatim. An arc
    spread over several headings ('### differential-ledger, the ...
    arc') answers to its key with all of them."""
    out: dict[str, str] = {}
    text = DEC_DOC.read_text(encoding="utf-8")
    for sec in re.split(r"^(?=#{2,3} )", text, flags=re.M):
        hm = re.match(r"### ([^\s—,]+)", sec)
        if hm:
            out[hm.group(1)] = out.get(hm.group(1), "") + " " + _norm(sec)
    return out


def _is_excerpt(excerpt: str, body: str) -> bool:
    pos = 0
    for frag in excerpt.split(_ELISION):
        frag = frag.strip()
        if not frag:
            return False
        found = body.find(frag, pos)
        if found < 0:
            return False
        pos = found + len(frag)
    return True


def _swept_files() -> list[Path]:
    # this module's own comments show citation shapes, citing nothing
    files = [p for d in SWEEP_DIRS for p in sorted((REPO / d).rglob("*.py"))
             if p != Path(__file__).resolve()]
    return files + sorted(_LEDGERS.glob("*.toml"))


def _quotes(text: str, at: int) -> tuple[str, ...]:
    """The quote opening at `at` and every quote chained to it."""
    out = []
    while (qm := _QUOTE_RE.match(text, at)):
        out.append(_norm(qm.group(1)))
        cm = _CHAIN_RE.match(text, qm.end())
        if not cm:
            break
        at = cm.end()
    return tuple(out)


def _citations() -> list[Citation]:
    """Every reference to a design doc, with what it quotes. A
    reference's text runs to the next reference, over the comment
    lines that continue it; on a line that is not a comment (a
    docstring, a string) it ends with the line, since a quote there
    may be the string's own delimiter."""
    found = []
    for path in _swept_files():
        lines = path.read_text(encoding="utf-8").splitlines()
        for i, line in enumerate(lines):
            for m in _MENTION_RE.finditer(line):
                cid, text = m.group("cid"), line[m.end():]
                if re.fullmatch(r"-[\"']?", text) and i + 1 < len(lines):
                    # a key wrapped at its hyphen ('ONE-PREDICATE-PER-'
                    # then 'QUESTION' on the next line)
                    wm = re.match(r"[\s#\"']*([A-Za-z0-9_]+"
                                  r"(?:-[A-Za-z0-9_]+)*)", lines[i + 1])
                    if wm:
                        cid += "-" + wm.group(1)
                if "#" in line[:m.start()]:
                    for cont in lines[i + 1:]:
                        cs = cont.strip()
                        if not cs.startswith("#"):
                            break
                        text += " " + re.sub(r"^#+:?\s*", "", cs)
                nxt = _MENTION_RE.search(text)
                if nxt:
                    text = text[:nxt.start()]
                colon = bool(_COLON_RE.match(text))
                doc = m.group("doc")
                if colon and doc != "decisions":
                    # the colon form's quote may follow a paraphrase
                    q = text.find('"')
                    excerpts = _quotes(text, q) if q >= 0 else ()
                else:
                    lm = _LEAD_RE.match(text)
                    excerpts = _quotes(text, lm.end()) if lm else ()
                found.append(Citation(path, i + 1, doc, cid,
                                      excerpts, colon))
    return found


def test_citations_are_verbatim_excerpts() -> None:
    statements = _statements()
    entries = _decision_entries()
    problems = []
    for c in _citations():
        where = f"{c.path.relative_to(REPO)}:{c.line}"
        known = entries if c.doc == "decisions" else statements
        if c.cid not in known:
            problems.append(f"{where}: {c.doc}.md#{c.cid} names nothing")
            continue
        if c.colon and c.doc != "decisions" and not c.excerpts:
            problems.append(
                f"{where}: citation of {c.cid} has no quoted excerpt")
        for excerpt in c.excerpts:
            if not _is_excerpt(excerpt, known[c.cid]):
                problems.append(
                    f"{where}: not a verbatim excerpt of "
                    f"{c.doc}.md#{c.cid}: {excerpt[:60]!r}")
    assert not problems, "\n".join(problems)


def test_the_sweep_reaches_every_citation_shape() -> None:
    # Each half of the sweep decides its own scope -- a glob, a lead
    # grammar, an elision, the decisions routing -- and one matching
    # nothing would let the excerpt test pass on what is left.
    cites = _citations()
    ledgers = {c.path.name for c in cites if c.excerpts
               and c.path.suffix == ".toml"}
    assert {"expected_since_1.4.0.toml",
            "expected_since_2.3.0.toml"} <= ledgers
    assert any(c.excerpts and not c.colon for c in cites)
    assert any(c.excerpts and c.doc == "decisions" for c in cites)
    assert any(len(c.excerpts) > 1 for c in cites)
    assert any(_ELISION in e for c in cites for e in c.excerpts)


def test_an_elided_excerpt_must_keep_its_order() -> None:
    assert _is_excerpt("a b [...] d", "a b c d")
    assert not _is_excerpt("d [...] a b", "a b c d")
    assert not _is_excerpt("[...]", "a b c d")
    assert not _is_excerpt("a [...]", "a b c d")


# The recorded negative control: excerpts this module once let through
# (#632), each still false against the text the check reads.
_RETIRED_EXCERPTS = (
    ("rules", "P5", "a trailing roman numeral that assign reads as the "
                    "suffix (S2) is no word to spare, and is not joined"),
    ("rules", "M2", "a bare acronym the reading declines is maiden text "
                    "all the same"),
    ("rules", "S2", "A suffix never BEGINS a name: position outranks "
                    "the vocabulary match"),
    ("rules", "C1", "The part is read as its words stand, before any "
                    "join"),
    ("rules", "A1", "a kind is worth adding only if a reader would "
                    "hesitate too"),
    # a decisions.md quote checked against the rule of the same ID
    ("rules", "P6", "the COMMA form only, deliberately."),
)


def test_retired_excerpts_stay_rejected() -> None:
    statements = _statements()
    for _doc, cid, old in _RETIRED_EXCERPTS:
        assert not _is_excerpt(_norm(old), statements[cid]), (cid, old)


def test_implemented_matches_citing_modules() -> None:
    citing: dict[str, set[str]] = {}
    for c in _citations():
        if not c.colon or c.doc == "decisions" or c.path.suffix != ".py":
            continue
        citing.setdefault(c.cid, set()).add(str(c.path.relative_to(REPO)))
    problems = []
    for rule in parse_rules_doc(RULES_DOC.read_text(encoding="utf-8")):
        actual = citing.get(rule.rule_id, set())
        if rule.implemented:
            declared = set(rule.implemented)
            if actual != declared:
                problems.append(
                    f"{rule.rule_id}: implemented: says {sorted(declared)} "
                    f"but citations found in {sorted(actual)}")
        elif rule.tracked and actual:
            # The other half of test_rules_doc.py's exactly-one-pointer
            # rule: that test cannot see code, so a rule that SHIPPED
            # while keeping tracked: would pass it. Without this branch
            # the stale pointer is invisible -- the loop above skips
            # any rule with no implemented: at all.
            problems.append(
                f"{rule.rule_id}: declares tracked: {sorted(rule.tracked)} "
                f"but code cites it in {sorted(actual)}; swap tracked: for "
                f"implemented: now that something implements it")
    assert not problems, "\n".join(problems)


def test_interacts_ids_exist() -> None:
    rules = parse_rules_doc(RULES_DOC.read_text(encoding="utf-8"))
    ids = {r.rule_id for r in rules}
    missing = [f"{r.rule_id} -> {t}" for r in rules
               for t in r.interacts if t not in ids]
    assert not missing, f"advisory interacts: cite unknown IDs: {missing}"


def test_doc_internal_anchors_resolve() -> None:
    """Every rules.md#X / decisions.md#Y / mechanisms.md#Z reference
    INSIDE the three docs points at a real rule ID, ### key, or
    entry heading (## or ###). The code-side citations are covered
    above; this closes the doc-to-doc half."""
    docs = {name: (REPO / "docs" / "design" / f"{name}.md")
            .read_text(encoding="utf-8")
            for name in ("rules", "decisions", "mechanisms")}
    rule_ids = set(re.findall(r"^([A-Z]\d+)\.\s", docs["rules"], re.M))
    dec_keys = set(re.findall(r"^### ([^\s—]+)", docs["decisions"], re.M))
    mech_slugs = set(re.findall(r"^#{2,3} ([A-Z][A-Z0-9_-]+)",
                                docs["mechanisms"], re.M))
    problems = []
    for name, text in docs.items():
        for m in re.finditer(
                r"(rules|decisions|mechanisms)\.md#([A-Za-z0-9_-]+)", text):
            doc, anchor = m.group(1), m.group(2)
            ok = (anchor in rule_ids if doc == "rules"
                  else anchor in dec_keys if doc == "decisions"
                  else anchor in mech_slugs)
            if not ok:
                line = text[:m.start()].count("\n") + 1
                problems.append(f"{name}.md:{line} -> {doc}.md#{anchor}")
    assert not problems, "\n".join(problems)


def test_no_legacy_citations() -> None:
    if not ENFORCE_NO_LEGACY:
        return   # armed by the final rewrite pass
    self_files = {Path(__file__).name, "test_doc_spellings.py",
                  "rules_doc.py"}
    problems = []
    for d in SWEEP_DIRS:
        for path in sorted((REPO / d).rglob("*")):
            if path.suffix not in (".py", ".toml"):
                continue
            if path.name in self_files:
                continue
            text = path.read_text(encoding="utf-8", errors="ignore")
            for pat in _LEGACY_RES:
                if pat.search(text):
                    problems.append(
                        f"{path}: matches {pat.pattern!r}")
    assert not problems, "\n".join(problems)
