"""Referential integrity for docs/design/ citations.

Checks: cited rule/mechanism IDs exist; citation sentences are
whitespace-normalized verbatim excerpts of their statements;
``implemented:`` lists match the set of modules actually citing the
rule; ``interacts:`` IDs exist (existence only -- the field is
advisory). The legacy-pattern check (armed) keeps gitignored-spec
citation forms out of the committed tree.
"""
from __future__ import annotations

import re
from pathlib import Path

from tests.v2.rules_doc import RULES_DOC, parse_rules_doc

REPO = Path(__file__).resolve().parents[2]
MECH_DOC = REPO / "docs" / "design" / "mechanisms.md"
SWEEP_DIRS = ("nameparser", "tests", "tools")
ENFORCE_NO_LEGACY = True    # armed 2026-08-15, the rewrite complete
_LEGACY = ("§", "superpowers", "plan deviation")

_CITE_RE = re.compile(
    r"#\s*(?:rules|mechanisms|decisions)\.md#"
    r"(?P<cid>[A-Z]\d+|[A-Z][A-Z0-9_]*(?:-[A-Z0-9_]+)*)"
    r":\s*(?P<first>.*)")
# The excerpt is the FIRST double-quoted span after the ID, wrapped
# over continuation comment lines; text outside the quotes (v1 names,
# history pointers, code-local notes) is free.
_EXCERPT_RE = re.compile(r'"(.*?)"')


def _norm(s: str) -> str:
    return " ".join(s.split()).lower()


def _statements() -> dict[str, str]:
    out: dict[str, str] = {}
    text = RULES_DOC.read_text(encoding="utf-8")
    for block in re.split(r"^(?=[A-Z]\d+\.\s)", text, flags=re.M):
        m = re.match(r"([A-Z]\d+)\.\s(.*)", block, flags=re.S)
        if m:
            body = m.group(2).split('\n      "')[0]     # stop at examples
            out[m.group(1)] = _norm(body)
    mech = MECH_DOC.read_text(encoding="utf-8")
    for mm in re.finditer(
            r"^## (?P<slug>[A-Z][A-Z0-9_-]+)(?=[\s—-])"
            r".*?Contract statement[.:*]*\s*"
            r"(?P<stmt>.+?)(?=\n\n|\Z)", mech, flags=re.M | re.S):
        out[mm.group("slug")] = _norm(mm.group("stmt"))
    return out


def _citations() -> list[tuple[Path, int, str, str]]:
    found = []
    for d in SWEEP_DIRS:
        for path in sorted((REPO / d).rglob("*.py")):
            lines = path.read_text(encoding="utf-8").splitlines()
            for i, line in enumerate(lines):
                m = _CITE_RE.search(line)
                if not m:
                    continue
                block = [m.group("first")]
                for cont in lines[i + 1:]:
                    cs = cont.strip()
                    if cs.startswith("#") and not _CITE_RE.search(cont):
                        block.append(cs.lstrip("# "))
                    else:
                        break
                qm = _EXCERPT_RE.search(" ".join(block))
                found.append((path, i + 1, m.group("cid"),
                              _norm(qm.group(1)) if qm else ""))
    return found


def test_citations_are_verbatim_excerpts() -> None:
    statements = _statements()
    problems = []
    for path, lineno, cid, excerpt in _citations():
        if cid not in statements:
            problems.append(f"{path}:{lineno}: cites unknown ID {cid}")
        elif not excerpt:
            problems.append(
                f"{path}:{lineno}: citation of {cid} has no quoted excerpt")
        elif excerpt not in statements[cid]:
            problems.append(
                f"{path}:{lineno}: not a verbatim excerpt of {cid}")
    assert not problems, "\n".join(problems)


def test_implemented_matches_citing_modules() -> None:
    citing: dict[str, set[str]] = {}
    for path, _lineno, cid, _x in _citations():
        citing.setdefault(cid, set()).add(str(path.relative_to(REPO)))
    problems = []
    for rule in parse_rules_doc(RULES_DOC.read_text(encoding="utf-8")):
        if rule.implemented:
            actual = citing.get(rule.rule_id, set())
            declared = set(rule.implemented)
            if actual != declared:
                problems.append(
                    f"{rule.rule_id}: implemented: says {sorted(declared)} "
                    f"but citations found in {sorted(actual)}")
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
            for pat in _LEGACY:
                if pat in text:
                    problems.append(f"{path}: contains {pat!r}")
    assert not problems, "\n".join(problems)
