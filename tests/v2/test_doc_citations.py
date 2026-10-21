"""Referential integrity for docs/design/ citations.

Checks: every reference to a design doc in code names a rule,
section, mechanism or
decisions entry that exists; every quote a citation carries -- in any
of the shapes _LEAD_RE accepts, chained quotes included -- is a
normalized verbatim excerpt of what it cites ("[...]" eliding, in
order): a rule's quotable prose, a section's Background, a mechanism's Contract statement, a decisions entry's
text. Normalized means whitespace, case, "--" for the em dash and '
for a nested ", so emphasis in capitals is not checked. A quote
standing more than four words from its ID and chained to nothing is
prose to this module and is NOT checked: the reader cannot tell it
from a name written in double quotes, which is the common case;
``implemented:`` lists match the set of modules actually citing the
rule; every rule ID a rule's prose names exists. The legacy-pattern check (armed) keeps gitignored-spec
citation forms out of the committed tree.
"""
from __future__ import annotations

import re
import subprocess
from collections.abc import Callable
from pathlib import Path
from typing import NamedTuple

import pytest

from tests.v2.design_docs import (
    DECISIONS_DIR, MECHANISMS_DOC, MENTION_RE, RULES_DIR,
    read_decision_files, read_rules_text)
from tests.v2.rules_doc import Rule, parse_rules_doc, prose_blocks
from tests.v2.rules_skeleton import skeleton_prose

REPO = Path(__file__).resolve().parents[2]
MECH_DOC = MECHANISMS_DOC
SWEEP_DIRS = ("nameparser", "tests", "tools")
ENFORCE_NO_LEGACY = True    # armed 2026-08-15, the rewrite complete
_LEGACY_RES = (re.compile(r"§"), re.compile(r"superpowers"),
               re.compile(r"plan[\s#]+deviation"),
               re.compile(r"spec\s+[S§]?\d"))

# A reference to a design doc: the doc and the ID or entry key
# (design_docs.MENTION_RE). A decisions key may be a lowercase slug
# ('suffix-acronym-collisions').
_MENTION_RE = MENTION_RE
# The same reference in the docs themselves, where a key starting with a
# digit (decisions/3-0-reevaluations) is checked too.
_DOC_ANCHOR_RE = re.compile(MENTION_RE.pattern.replace(
    "[A-Za-z][A-Za-z0-9_]*", "[A-Za-z0-9][A-Za-z0-9_]*", 1))
assert _DOC_ANCHOR_RE.pattern != MENTION_RE.pattern, (
    "MENTION_RE was reworded; widen its key's first character here again")
# A reference is a CITATION when a quote follows it in one of the
# shapes the tree writes: the colon form (`rules/S2: "..."`, where
# prose may stand before the quote), or the ID, an optional "'s", up
# to four words and optionally a dash, colon, comma or parenthesis,
# then the
# quote (`rules/P5 -- "..."`, `rules/M2's Accepted clause
# ("...")`, `rules/S2 consumes "..."`, `rules/M2 -- the
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


class Citation(NamedTuple):
    path: Path
    line: int
    doc: str
    cid: str
    excerpts: tuple[str, ...]   # normalized; () for a pointer
    colon: bool                 # written in the colon form
    lead: str                   # the text between the ID and its quote


def _cite(doc: str, cid: str) -> str:
    return f"{doc}.md#{cid}" if doc == "mechanisms" else f"{doc}/{cid}"


def _norm(s: str) -> str:
    # Case folds because a quote routinely lowercases the first letter
    # of the sentence it lifts; "--" is how an ASCII comment spells the
    # em dash the docs use, and a quote nested in a quoted excerpt can
    # only be written single
    s = s.replace(" -- ", " — ").replace('"', "'")
    return " ".join(s.split()).lower()


def _statements() -> dict[str, str]:
    """What a citation may quote: for a rule, the text of its fields
    (#761) -- When,
    Tolerated, Then and its bullets, Because, and the Except,
    Precedence and Accepted bullets -- with the labels, the fences and
    the footer below `---` left out (rules_skeleton.skeleton_prose);
    for a section letter (`rules/H Background`), the section's
    Background paragraph; for a mechanism, its Contract statement."""
    out = prose_blocks(read_rules_text())
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
    """decisions entry bodies keyed by their key, one file each. An
    entry is a dated record rather than a statement, so a citation of
    one need not quote it; but what it does quote must be verbatim. An
    arc spread over several headings (the differential-ledger arcs)
    answers to its key with all of them."""
    return {key: _norm(text) for key, text in read_decision_files().items()}


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
    # this module's own comments show citation shapes, citing nothing,
    # and so do test_design_docs.py's fixtures for the citation pattern
    shapes = {Path(__file__).resolve(),
              REPO / "tests" / "v2" / "test_design_docs.py"}
    files = [p for d in SWEEP_DIRS for p in sorted((REPO / d).rglob("*.py"))
             if p not in shapes]
    return files


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
                doc = m.group("doc") or m.group("mdoc")
                if colon and doc != "decisions":
                    # the colon form's quote may follow a paraphrase
                    q = text.find('"')
                else:
                    lm = _LEAD_RE.match(text)
                    q = lm.end() if lm else -1
                excerpts = _quotes(text, q) if q >= 0 else ()
                found.append(Citation(path, i + 1, doc, cid, excerpts,
                                      colon, text[:q] if excerpts else ""))
    return found


def test_citations_are_verbatim_excerpts() -> None:
    statements = _statements()
    entries = _decision_entries()
    problems = []
    for c in _citations():
        where = f"{c.path.relative_to(REPO)}:{c.line}"
        known = entries if c.doc == "decisions" else statements
        if c.cid not in known:
            problems.append(f"{where}: {_cite(c.doc, c.cid)} names nothing")
            continue
        if c.colon and c.doc != "decisions" and not c.excerpts:
            problems.append(
                f"{where}: citation of {c.cid} has no quoted excerpt")
        for excerpt in c.excerpts:
            if not _is_excerpt(excerpt, known[c.cid]):
                problems.append(
                    f"{where}: not a verbatim excerpt of "
                    f"{_cite(c.doc, c.cid)}: {excerpt[:60]!r}")
    assert not problems, "\n".join(problems)


def test_the_sweep_reaches_every_citation_shape() -> None:
    # Each half of the sweep decides its own scope -- a glob, a lead
    # grammar, an elision, the decisions routing -- and one matching
    # nothing would let the excerpt test pass on what is left.
    cites = _citations()
    leads = [c.lead for c in cites if c.excerpts and not c.colon]
    # The possessive lead (`rules/X's Accepted clause ("...")`), the
    # dash lead (`rules/X -- "..."`) and the "[...]" elision had
    # their only witnesses in the differential ledgers' comments,
    # deleted with them (#664). The grammar still reads both leads, and
    # test_an_elided_excerpt_must_keep_its_order holds the elision.
    for lead in ("'s Accepted clause (", " -- "):
        m = _LEAD_RE.match(lead + '"')
        assert m is not None and m.group() == lead
    assert any("(" in ld for ld in leads)
    assert any(re.fullmatch(r"(?:\s+[A-Za-z]+)+\s*", ld) for ld in leads)
    assert any(c.excerpts and c.doc == "decisions" for c in cites)
    assert any(len(c.excerpts) > 1 for c in cites)


def test_the_sweep_finds_the_tree_s_citations() -> None:
    # A change to the citation pattern can narrow what it reads without
    # failing anything: #713's first pattern dropped three keys wrapped
    # at a hyphen, found only by diffing citation sets (that shape is
    # pinned by test_mention_re_reads_a_key_wrapped_at_its_hyphen).
    # 1,010 references, pointers included, on 2026-10-17 (#713): the
    # floor catches a pattern that stops reading a large shape -- the
    # mechanisms.md form, slug keys, hyphenated keys -- and not a small
    # one, nor a lead change that turns citations into pointers.
    assert len(_citations()) >= 1000


def test_an_elided_excerpt_must_keep_its_order() -> None:
    assert _is_excerpt("a b [...] d", "a b c d")
    assert not _is_excerpt("d [...] a b", "a b c d")
    assert not _is_excerpt("[...]", "a b c d")
    assert not _is_excerpt("a [...]", "a b c d")


def test_the_quotable_text_is_the_prose_and_only_the_prose() -> None:
    stmts = _statements()
    # an Accepted bullet, and a Background's wrapped lines, are quotable
    assert _is_excerpt(_norm("an unambiguous suffix is consumed even "
                             "when that leaves no family name at all"),
                       stmts["S2"])
    assert _is_excerpt(_norm("another's opener"), stmts["N"])
    # an example line, and a footer no-boundary: waiver, are not
    assert not _is_excerpt(_norm("Smith Jr."), stmts["S2"])
    assert not _is_excerpt(_norm("its boundaries are the other rules"),
                           stmts["O4"])
    # an Except bullet is quotable, its fenced example not
    assert _is_excerpt(_norm("A numeral past X is a name word"),
                       stmts["S10"])
    assert not _is_excerpt(_norm("John Smith XI"), stmts["S10"])


# The recorded negative control: excerpts that stood stale in the tree
# until #632, each still false against the text the check reads. They
# guard the QUOTABLE TEXT -- an Accepted clause or a fold loosening the
# match far enough to let one back in. The scanner's reach is the reach
# test's to guard.
_RETIRED_EXCERPTS = (
    ("P5", "a trailing roman numeral that assign reads as the "
            "suffix (S2) is no word to spare, and is not joined"),
    ("M2", "a bare acronym the reading declines is maiden text "
            "all the same"),
    ("S2", "A suffix never BEGINS a name: position outranks "
            "the vocabulary match"),
    ("C7", "The part is read as its words stand, before any "
            "join"),
    ("A1", "a kind is worth adding only if a reader would "
            "hesitate too"),
)


_BULLET_LEAD_RE = re.compile(r"^- \*\*(?P<lead>[^*]+)\*\*", re.M)


def _bullet_leads(rule_id: str, label: str) -> list[str]:
    """The bold leads of a rule's bullets under one label, normalized."""
    (path,) = RULES_DIR.glob(f"{rule_id}-*.md")
    text = path.read_text(encoding="utf-8")
    m = re.search(rf"^\*\*{label}:\*\*\n(?P<body>.*?)(?=^\*\*\w+:\*\*|^---$)",
                  text, re.S | re.M)
    body = m.group("body") if m else ""
    return [_norm(lm.group("lead")).rstrip(".:") for lm in
            _BULLET_LEAD_RE.finditer(body)]


def bullet_lead_findings(
        citations: list[Citation],
        leads: Callable[[str, str], list[str]] = _bullet_leads,
) -> tuple[int, list[str]]:
    """How many citations name a rule's Except or Precedence bullet and
    quote it, and those whose quote is not one of that rule's bold leads
    under that label."""
    found, problems = 0, []
    for c in citations:
        lm = re.search(r"\b(Except|Precedence) bullet", c.lead)
        if lm is None or c.doc != "rules" or not c.excerpts:
            continue
        found += 1
        named = leads(c.cid, lm.group(1))
        if not any(c.excerpts[0].startswith(lead) for lead in named):
            problems.append(
                f"{c.path.name}:{c.line} quotes rules/{c.cid}'s "
                f"{lm.group(1)} bullet as {c.excerpts[0]!r}; quote the "
                f"bullet's bold lead, one of {named}")
    return found, problems


def test_a_citation_naming_a_bullet_quotes_its_bold_lead() -> None:
    """A comment that names a rule's Except or Precedence bullet and
    quotes it quotes the bullet's bold lead, which is the bullet's name:
    the excerpt check holds a quote only to the rule's text, so another
    sentence of the rule would pass it (#768's review). A comment that
    describes a bullet without quoting it is not read here."""
    found, problems = bullet_lead_findings(_citations())
    assert found >= 2, "no citation names a bullet; the check reads nothing"
    assert not problems, "\n".join(problems)


@pytest.mark.parametrize("label, quote, finding", [
    ("Except", "one letter needs words", False),
    ("Except", "either reading is reported", True),
    ("Precedence", "before a comma", False),
    ("Precedence", "one letter needs words", True),
])
def test_bullet_lead_findings_catch_a_quote_that_is_no_lead(
        label: str, quote: str, finding: bool) -> None:
    leads = {"Except": ["one letter needs words"],
             "Precedence": ["before a comma"]}
    c = Citation(path=Path("x.py"), line=1, doc="rules", cid="X1",
                 excerpts=(quote,), colon=False, lead=f"'s {label} bullet ")
    found, problems = bullet_lead_findings(
        [c], lambda cid, lab: leads[lab])
    assert found == 1
    assert bool(problems) is finding, problems


def test_retired_excerpts_stay_rejected() -> None:
    statements = _statements()
    for cid, old in _RETIRED_EXCERPTS:
        assert not _is_excerpt(_norm(old), statements[cid]), (cid, old)


def test_implemented_matches_citing_modules() -> None:
    citing: dict[str, set[str]] = {}
    for c in _citations():
        if not c.colon or c.doc == "decisions" or c.path.suffix != ".py":
            continue
        citing.setdefault(c.cid, set()).add(str(c.path.relative_to(REPO)))
    problems = []
    for rule in parse_rules_doc(read_rules_text()):
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


_ID_RE = re.compile(r"\b[A-Z]\d+\b")


def _skeleton_texts(r: Rule) -> list[str]:
    sk = r.skeleton
    assert sk is not None
    return skeleton_prose(sk)


def named_id_findings(rules: list[Rule]) -> list[str]:
    """Every rule ID a rule names that no rule has: the IDs written
    anywhere in its quotable prose, every field's text as
    rules_skeleton.skeleton_prose lists it. A rule's own ID is not a
    citation of another."""
    ids = {r.rule_id for r in rules}
    out = []
    for r in rules:
        found: set[str] = set()
        for text in _skeleton_texts(r):
            found |= set(_ID_RE.findall(text)) - {r.rule_id}
        out += [f"{r.rule_id} -> {t}" for t in sorted(found)
                if t not in ids]
    return out


def test_the_rule_ids_a_rule_names_exist() -> None:
    missing = named_id_findings(parse_rules_doc(read_rules_text()))
    assert not missing, f"rules name unknown rule IDs: {missing}"


def _skeleton_doc(*, signal: str = "a shape", then: str = "",
                  bullets: tuple[str, ...] = (), excepts: tuple[str, ...] = (),
                  precedence: tuple[str, ...] = (),
                  accepted: tuple[str, ...] = (),
                  when: str = "a name ends in a thing.",
                  tolerated: str = "",
                  because: str = "it is how it is written.",
                  others: tuple[str, ...] = ("X2",)) -> str:
    """A synthetic rule X1, then a minimal rule for each of ``others``
    (each under its own heading, which ends the footer)."""
    out = f'# X1 — one\n\n**When:** {when}\n\n'
    if tolerated:
        out += f"**Tolerated:** {tolerated}\n\n"
    out += f'**Then:** {then or "the thing is read."}\n\n'
    out += "".join(f"- {b}\n" for b in bullets)
    out += f"\n**Because:** {because}\n\n"
    out += '```\n"John Smith III"  →  suffix="III"\n```\n\n'
    if excepts:
        out += "**Except:**\n\n" + "".join(
            f'- {b}\n  ```\n  "John V"  →  family="V"  · boundary\n  ```\n'
            for b in excepts) + "\n"
    if precedence:
        out += "**Precedence:**\n\n" + "".join(
            f"- {b}\n" for b in precedence) + "\n"
    if accepted:
        out += "**Accepted:**\n\n" + "".join(
            f"- {b}\n" for b in accepted) + "\n"
    out += (f"---\n**Signal:** {signal}\n"
            "**history:** decisions/P2 · **implemented:** "
            "nameparser/_parser.py\n\n")
    return out + "".join(_minimal_rule(o) for o in others)


def _minimal_rule(rid: str) -> str:
    return (f"# {rid} — other\n\n**When:** w.\n\n**Then:** t.\n\n"
            "**Because:** b.\n\n```\n\"a\"  →  given=\"a\"  · boundary\n"
            "```\n\n---\n**Signal:** a shape\n"
            "**history:** decisions/P2 · **implemented:** "
            "nameparser/_parser.py\n\n")


def test_ids_a_skeleton_rule_names_exist() -> None:
    doc = _skeleton_doc(precedence=("X9 decides first.",))
    assert named_id_findings(parse_rules_doc(doc)) == ["X1 -> X9"]
    # its own ID, and an ID that exists, are fine
    doc = _skeleton_doc(precedence=("X1 and X2 agree.",))
    assert named_id_findings(parse_rules_doc(doc)) == []


@pytest.mark.parametrize("field", [
    "when", "tolerated", "then", "bullets", "because", "excepts",
    "precedence", "accepted"])
def test_an_unknown_id_in_any_skeleton_field_is_a_finding(field: str) -> None:
    # every quotable field is scanned, read off skeleton_prose (#768)
    text = "X9 says so."
    value: str | tuple[str, ...] = (
        (text,) if field in ("bullets", "excepts", "precedence", "accepted")
        else text)
    doc = _skeleton_doc(**{field: value})  # type: ignore[arg-type]
    assert named_id_findings(parse_rules_doc(doc)) == ["X1 -> X9"]


def _skeleton_hub_findings(r: Rule, ids: set[str]) -> list[str]:
    """A skeleton hub's map is the bullet list under its Then: the
    union of the rule IDs the bullets name. Each hub rule must be in
    it, each ID in it must be a hub rule, and each bullet must name
    a rule."""
    assert r.skeleton is not None
    problems = []
    bullets = r.skeleton.then_bullets
    mapped = set().union(*(set(_ID_RE.findall(b.text)) for b in bullets))
    for rid in r.hub:
        where = f"{r.rule_id}'s Signal: hub of ... {rid}"
        if rid not in ids or rid == r.rule_id:
            problems.append(f"{where}: names no other rule")
        elif rid not in mapped:
            problems.append(f"{where}: its statement's map omits it")
    for rid in sorted(mapped & ids - set(r.hub) - {r.rule_id}):
        problems.append(f"{r.rule_id}'s map names {rid}, which its "
                        f"Signal: hub of ... leaves off")
    for b in bullets:
        # a bullet naming a rule off the hub list is the "leaves off"
        # finding above; this one is a bullet naming no rule at all
        if not set(_ID_RE.findall(b.text)) & ((ids | set(r.hub)) - {r.rule_id}):
            problems.append(f"{r.rule_id}'s map bullet names no rule of "
                            f"its hub: {b.text!r}")
    return problems


def hub_findings(rules: list[Rule]) -> list[str]:
    """A hub's ``**Signal:** ... hub of ...`` names the rules stating
    the signals it combines, and its map is the bullet list under its
    Then; each rule on the list must be another rule and named by a
    bullet, every bullet must name one of them, and the check runs both
    ways: a rule a bullet names that
    the Signal: line leaves off is a finding too, which is the half of
    S2's lost S9 (named in neither its map nor its pointer line before
    PR #745) the first direction alone would miss."""
    ids = {r.rule_id for r in rules}
    problems = []
    for r in rules:
        if r.hub:
            problems += _skeleton_hub_findings(r, ids)
    return problems


def test_a_hub_names_each_rule_its_map_names() -> None:
    rules = parse_rules_doc(read_rules_text())
    assert [r.rule_id for r in rules if r.hub], "no hub to check"
    problems = hub_findings(rules)
    assert not problems, "\n".join(problems)


@pytest.mark.parametrize("signal, bullets, excepts, finding", [
    ("hub of X2, X3", ("**Reach:** X2 first.", "**Then:** X3 next."),
     (), None),
    # the map omits X3
    ("hub of X2, X3", ("**Reach:** X2 first.",), (),
     "its statement's map omits it"),
    # a map bullet names X4, which the hub list leaves off
    ("hub of X2, X3", ("X2 first.", "X3 next.", "X4 last."), (),
     "which its Signal: hub of ... leaves off"),
    # a map bullet naming no rule of the hub
    ("hub of X2, X3", ("X2 first.", "X3 next.", "Only the last one."), (),
     "names no rule of its hub"),
    # X2 named only in an Except bullet is not in the map
    ("hub of X2, X3", ("X3 next.",), ("X2 is an exception.",),
     "its statement's map omits it"),
    ("hub of X9", ("X9 first.",), (), "names no other rule"),
    # a hub naming itself names no other rule
    ("hub of X1, X2", ("X1 and X2.",), (), "names no other rule"),
    # X2 is not named merely because X21 is
    ("hub of X2, X3", ("X21 and X3.",), (), "its statement's map omits it"),
])
def test_skeleton_hub_findings_catch_each_gap(
        signal: str, bullets: tuple[str, ...], excepts: tuple[str, ...],
        finding: str | None) -> None:
    doc = _skeleton_doc(signal=signal, bullets=bullets, excepts=excepts,
                        others=("X2", "X3", "X4"))
    got = hub_findings(parse_rules_doc(doc))
    if finding is None:
        assert got == []
    else:
        assert len(got) == 1 and finding in got[0], got


def test_a_quote_of_a_bold_lead_matches_and_a_fenced_example_does_not(
        ) -> None:
    doc = _skeleton_doc(
        bullets=("**One letter needs a word to spare** when it is last.",))
    text = _norm(" ".join(prose_blocks(doc)["X1"]))
    assert _is_excerpt(_norm("One letter needs a word to spare"), text)
    assert _is_excerpt(_norm("spare when it is last"), text)
    # "Smith III" occurs only in the fence
    assert not _is_excerpt(_norm("John Smith III"), text)


def test_doc_internal_anchors_resolve() -> None:
    """Every rules/X / decisions/Y / mechanisms.md#Z reference
    INSIDE the three docs points at a real rule ID, ### key, or
    entry heading (## or ###). The code-side citations are covered
    above; this closes the doc-to-doc half."""
    paths = [*sorted(RULES_DIR.glob("*.md")),
             *sorted(DECISIONS_DIR.glob("*.md")), MECH_DOC]
    docs = {str(p.relative_to(REPO)): p.read_text(encoding="utf-8")
            for p in paths}
    # the parser's own reading, so a new rule format needs no copy here
    rule_ids = {r.rule_id for r in parse_rules_doc(read_rules_text())}
    dec_keys = set(read_decision_files())
    mech_slugs = set(re.findall(r"^#{2,3} ([A-Z][A-Z0-9_-]+)",
                                docs[str(MECH_DOC.relative_to(REPO))], re.M))
    problems = []
    for name, text in docs.items():
        for m in _DOC_ANCHOR_RE.finditer(text):
            doc, anchor = m.group("doc") or m.group("mdoc"), m.group("cid")
            ok = (anchor in rule_ids if doc == "rules"
                  else anchor in dec_keys if doc == "decisions"
                  else anchor in mech_slugs)
            if not ok:
                line = text[:m.start()].count("\n") + 1
                problems.append(f"{name}:{line} -> {_cite(doc, anchor)}")
    assert not problems, "\n".join(problems)


def test_no_legacy_citations() -> None:
    if not ENFORCE_NO_LEGACY:
        return   # armed by the final rewrite pass
    self_files = {Path(__file__).name, "test_doc_spellings.py",
                  "rules_doc.py"}
    problems = []
    for d in SWEEP_DIRS:
        for path in sorted((REPO / d).rglob("*")):
            if path.suffix != ".py":
                continue
            if path.name in self_files:
                continue
            text = path.read_text(encoding="utf-8", errors="ignore")
            for pat in _LEGACY_RES:
                if pat.search(text):
                    problems.append(
                        f"{path}: matches {pat.pattern!r}")
    assert not problems, "\n".join(problems)


_OLD_ANCHOR_RE = re.compile(r"\b(rules|decisions)\.md#")


def test_no_old_design_doc_anchors() -> None:
    """rules.md and decisions.md are folders since #713, cited as
    rules/S2 and decisions/key. An old-form citation written from habit
    would not be read by the citation check at all, so its quote would
    go unchecked; this keeps the form out of every tracked file."""
    tracked = subprocess.run(["git", "ls-files"], cwd=REPO, check=True,
                             capture_output=True, text=True).stdout.split()
    problems = []
    for rel in tracked:
        if not rel.endswith((".py", ".md", ".rst")):
            continue
        path = REPO / rel
        if not path.exists():
            continue
        for i, line in enumerate(
                path.read_text(encoding="utf-8").splitlines(), 1):
            if _OLD_ANCHOR_RE.search(line):
                problems.append(f"{rel}:{i}: {line.strip()[:80]}")
    assert not problems, (
        f"{len(problems)} old-form citations; write rules/ID or "
        "decisions/key:\n" + "\n".join(problems[:40]))
