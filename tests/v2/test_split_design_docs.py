"""tools/split_design_docs.py: the one-shot split of rules.md and
decisions.md, and the citation rewrite (#713)."""
from __future__ import annotations

import importlib.util
from pathlib import Path
from types import ModuleType

import pytest

_SCRIPT = Path(__file__).resolve().parents[2] / "tools" / "split_design_docs.py"


def _load() -> ModuleType:
    spec = importlib.util.spec_from_file_location("split_design_docs", _SCRIPT)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


split = _load()

RULES = (
    "# Parsing rules\n\nPreamble.\n\n## Not in scope\n\n- nothing\n\n"
    "## Titles & honorifics (H)\n\nBackground: titles.\n\n"
    "H1. Rationale: one.\n    Statement one.\n"
    '      "Dr. Smith"  →  family="Smith"\n'
    "    history: decisions.md#H1\n\n"
    "H2. Rationale: two.\n    Statement two.\n"
    '      "Dr. Jones"  →  family="Jones"\n\n'
    "## Suffixes: generational & credentials (S)\n\n"
    "Background: suffixes.\n\n"
    "S1. Rationale: s.\n    Statement.\n"
    '      "José Smith"  →  family="Smith"\n')
NAMES = {"H1": "a title and one name word", "H2": "the leading abbreviation",
         "S1": "a bracketed credential is not a nickname"}

DECISIONS = (
    "# Decisions\n\nPreamble.\n\n"
    "### H1 — a title and one name word\n\nBody one.\n\n"
    "### differential-ledger, the dormancy arc (2026-08)\n\nL1.\n\n"
    "### vocabulary-collisions — when a word earns the ambiguous "
    "marking\n\nV.\n\n"
    "### differential-ledger, the rule-order arc (2026-09)\n\nL2.\n")
SECTIONS = {"H": "Titles & honorifics (H)",
            "S": "Suffixes: generational & credentials (S)"}


def test_split_rules_round_trips() -> None:
    assert split.join_rules(split.split_rules(RULES, NAMES)) == RULES


def test_split_decisions_round_trips() -> None:
    files, order = split.split_decisions(DECISIONS, SECTIONS)
    assert split.join_decisions(files, order) == DECISIONS


def test_split_rules_names_files_by_id_and_name() -> None:
    files = split.split_rules(RULES, NAMES)
    assert set(files) == {
        "README.md", "H-titles-and-honorifics.md",
        "H1-title-and-one-name-word.md", "H2-leading-abbreviation.md",
        "S-suffixes-generational-and-credentials.md",
        "S1-bracketed-credential-is-not-a-nickname.md"}
    assert files["H1-title-and-one-name-word.md"].startswith(
        "# H1 — a title and one name word\n\nH1. Rationale: one.\n")
    assert files["S-suffixes-generational-and-credentials.md"].startswith(
        "## Suffixes: generational & credentials (S)\n")
    readme = files["README.md"]
    assert readme.startswith("# Parsing rules\n\nPreamble.\n\n## Not in scope")
    assert ("- [H1 — a title and one name word]"
            "(H1-title-and-one-name-word.md)\n") in readme


def test_ledger_chunks_share_one_file_in_order() -> None:
    files, _ = split.split_decisions(DECISIONS, SECTIONS)
    ledger = files["differential-ledger.md"]
    assert ledger.startswith(f"# differential-ledger — {split.LEDGER_NAME}\n")
    assert ledger.index("## differential-ledger, the dormancy arc") < (
        ledger.index("## differential-ledger, the rule-order arc"))
    assert "vocabulary-collisions.md" in files
    assert files["H1-title-and-one-name-word.md"].startswith(
        "# H1 — a title and one name word\n")


def test_rewrite_citations_changes_only_the_two_docs() -> None:
    assert split.rewrite_citations(
        "rules.md#S2 and decisions.md#ma-do, mechanisms.md#X, rules.md") == (
        "rules/S2 and decisions/ma-do, mechanisms.md#X, rules.md")


def test_split_refuses_to_write_when_the_round_trip_fails(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    design = tmp_path / "docs" / "design"
    design.mkdir(parents=True)
    (design / "rules.md").write_text(RULES, encoding="utf-8")
    (design / "decisions.md").write_text(DECISIONS, encoding="utf-8")
    monkeypatch.setattr(split, "RULE_NAMES", NAMES)
    monkeypatch.setattr(split, "join_rules", lambda files: RULES[:-1])
    with pytest.raises(AssertionError):
        split.main(["split"], root=tmp_path)
    assert not (design / "rules").exists()
    assert (design / "rules.md").exists()
