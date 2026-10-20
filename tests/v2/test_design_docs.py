"""The design docs' folder layout: names, the index, citations."""
from __future__ import annotations

import re
from pathlib import Path

import pytest

from tests.v2.design_docs import (
    DECISIONS_DIR, MENTION_RE, RULES_DIR, read_decision_files, read_index,
    read_rules_text, read_standing_exempt, resolve, slugify,
    standing_findings, standing_roster_findings, stem_for)
from tests.v2.rules_doc import parse_rules_doc

_FIXTURE_FILES = ("S-suffixes.md", "S1-x.md",
                  "S6-case-signal-at-the-suffix-slot.md",
                  "vocabulary-collisions.md")


@pytest.fixture
def folder(tmp_path: Path) -> Path:
    (tmp_path / "README.md").write_text(
        "# Index\n\n"
        "## [Suffixes (S)](S-suffixes.md)\n\n"
        "- [S1 — x](S1-x.md)\n"
        "- [S6 — the case signal at the suffix slot]"
        "(S6-case-signal-at-the-suffix-slot.md)\n\n"
        "## Named topics\n\n"
        "- [vocabulary-collisions — when a word earns the ambiguous "
        "marking](vocabulary-collisions.md)\n",
        encoding="utf-8")
    for name in _FIXTURE_FILES:
        (tmp_path / name).write_text(f"# {name}\n", encoding="utf-8")
    return tmp_path


def test_slugify_follows_the_spec() -> None:
    assert slugify("the case signal at the suffix slot") == (
        "case-signal-at-the-suffix-slot")
    assert slugify("Titles & honorifics") == "titles-and-honorifics"
    assert slugify("a title and one name word") == "title-and-one-name-word"
    assert slugify("Suffixes: generational & credentials") == (
        "suffixes-generational-and-credentials")
    assert slugify('the "Ph. D." split') == "ph-d-split"
    assert slugify("the title run's floor") == "title-runs-floor"
    assert slugify("the writer’s divisions") == "writers-divisions"


def test_stem_for_names_rules_and_keeps_slugs() -> None:
    assert stem_for("S6", "the case signal at the suffix slot") == (
        "S6-case-signal-at-the-suffix-slot")
    assert stem_for("S", "Suffixes") == "S-suffixes"
    assert stem_for("vocabulary-collisions", "when a word …") == (
        "vocabulary-collisions")


def test_read_index_keeps_order_and_keys(folder: Path) -> None:
    entries = read_index(folder)
    assert [e.key for e in entries] == [
        "S", "S1", "S6", "vocabulary-collisions"]
    assert entries[2].title == "S6 — the case signal at the suffix slot"
    assert entries[2].path == folder / "S6-case-signal-at-the-suffix-slot.md"
    (folder / "README.md").write_text(
        "- [differential-ledger — the differential ledger's arcs]"
        "(differential-ledger.md)\n", encoding="utf-8")
    assert read_index(folder)[0].key == "differential-ledger"


@pytest.mark.parametrize(("text", "doc", "cid"), [
    ("see rules/S2.", "rules", "S2"),
    ("rules/S2's Accepted clause", "rules", "S2"),
    ("rules/H Background", "rules", "H"),
    ("decisions/vocabulary-collisions, which", "decisions",
     "vocabulary-collisions"),
    ("mechanisms.md#VERSION-TELL", "mechanisms", "VERSION-TELL"),
])
def test_mention_re_reads_each_shape(text: str, doc: str, cid: str) -> None:
    m = MENTION_RE.search(text)
    assert m is not None
    assert (m.group("doc") or m.group("mdoc"), m.group("cid")) == (doc, cid)


def test_mention_re_reads_a_key_wrapped_at_its_hyphen() -> None:
    # a comment wraps a long key at a hyphen; the checker joins the
    # next line's half on, so the first half must still match
    for text in ("mechanisms.md#ONE-PREDICATE-PER-",
                 "decisions/two-input-'"):
        m = MENTION_RE.search(text)
        assert m is not None, text
        assert m.group("cid") in ("ONE-PREDICATE-PER", "two-input")


@pytest.mark.parametrize("text", [
    "docs/design/rules/S6-case-signal-at-the-suffix-slot.md",
    "decisions/README.md",
    "rules/README.md",
    "docs/design/rules/",
])
def test_mention_re_skips_file_paths(text: str) -> None:
    assert MENTION_RE.search(text) is None


def test_resolve_section_letter_is_not_a_rule(folder: Path) -> None:
    def name(cid: str) -> str | None:
        p = resolve("rules", cid, folder)
        return p.name if p else None
    assert name("S") == "S-suffixes.md"
    assert name("S6") == "S6-case-signal-at-the-suffix-slot.md"
    assert name("S99") is None
    assert name("README") is None
    assert resolve("decisions", "vocabulary-collisions", folder) == (
        folder / "vocabulary-collisions.md")


_LOG = ("## Log\n\n"
        "- 2026-07 (v2 core, PR #288) — v1 parity.\n"
        "- 2026-10-01 (Derek), #562 — SUPERSEDED by #613. The pair.\n"
        "- 2026-09-24 — SUPERSEDED IN PART: the mark.\n"
        "- 2026-10-03 #549 — SUPERSEDED: the skip is reversed.\n"
        "- 2026-10-04 #611 (in part superseded by #613) — FILED.\n"
        "- 2026-10-06 #613 — DECIDED ONCE.\n")


@pytest.mark.parametrize("standing, finding", [
    ("- Only the second part decides — 2026-07 PR #288.\n"
     "- Decided once — 2026-10-06 #613, (1)–(4).\n"
     "\nNot standing: 2026-10-01 #562, answered by #613.\n", None),
    ("- Decided once.\n", "no entry pointer"),
    ("- Decided once — 2026-10-07 #613.\n", "no entry 2026-10-07 #613"),
    ("- Decided once — 2026-10-06 #61.\n", "no entry 2026-10-06 #61"),
    ("- The pair — 2026-10-01 #562.\n", "superseded entry"),
    ("- The skip — 2026-10-03 #549.\n", None),
    ("- The mark — 2026-09-24, in part.\n", None),
    ("- Decided once — 2026-10-04 #613.\n", "no entry 2026-10-04 #613"),
    ("- Decided once — 2026-10 #613.\n", "no entry 2026-10 #613"),
    ("- Decided once — 2026-10-06 #613 and 2026-11-01 #999.\n",
     "no entry 2026-11-01 #999"),
    ("\nNot standing: 2026-10-04 #612.\n", "names no entry"),
], ids=["clean", "no-pointer", "wrong-date", "number-prefix", "superseded",
        "announcing-is-live", "date-only", "later-issue-in-a-head",
        "month-only-date", "second-pointer",
        "not-standing-missing"])
def test_standing_findings_name_each_broken_pointer(
        standing: str, finding: str | None) -> None:
    found = standing_findings(f"# C1 — x\n\n## Standing\n\n{standing}\n"
                              + _LOG)
    if finding is None:
        assert found == []
    else:
        assert len(found) == 1 and finding in found[0], found


def test_standing_needs_a_log_and_is_optional() -> None:
    assert standing_findings("# C1 — x\n\n## Standing\n\n- a\n") == [
        "## Standing without a ## Log after it"]
    assert standing_findings("# C1 — x\n\n" + _LOG) == []


# -- the real tree ---------------------------------------------------------

@pytest.mark.parametrize("folder", [RULES_DIR, DECISIONS_DIR],
                         ids=["rules", "decisions"])
def test_every_entry_file_is_indexed_once(folder: Path) -> None:
    indexed = [e.path for e in read_index(folder)]
    assert len(indexed) == len(set(indexed)), "an index lists a file twice"
    on_disk = {p for p in folder.glob("*.md") if p.name != "README.md"}
    assert set(indexed) == on_disk


@pytest.mark.parametrize("folder", [RULES_DIR, DECISIONS_DIR],
                         ids=["rules", "decisions"])
def test_index_title_matches_heading_and_file_name(folder: Path) -> None:
    for e in read_index(folder):
        first = e.path.read_text(encoding="utf-8").split("\n", 1)[0]
        if len(e.key) == 1:     # a section keeps its old heading
            assert first == "## " + e.title, e.path.name
            name = e.title.rsplit(" (", 1)[0]
        else:
            assert first == "# " + e.title, e.path.name
            name = e.title.split(" — ", 1)[1] if " — " in e.title else ""
        assert e.path.stem == stem_for(e.key, name), e.path.name


def test_each_citation_key_resolves_to_one_file() -> None:
    for doc, folder in (("rules", RULES_DIR), ("decisions", DECISIONS_DIR)):
        for e in read_index(folder):
            assert resolve(doc, e.key) == e.path, (doc, e.key)


def test_the_folders_are_not_empty() -> None:
    rule_files = [p for p in RULES_DIR.glob("*.md")
                  if re.match(r"[A-Z]\d+-", p.name)]
    rules = parse_rules_doc(read_rules_text())
    assert len(rules) == len(rule_files) >= 46
    assert len(read_decision_files()) >= 60


def test_every_standing_line_points_at_a_live_entry() -> None:
    files = read_decision_files()
    with_standing = [k for k, t in files.items() if "## Standing" in t]
    assert with_standing, "no decisions file has a Standing block"
    for key in with_standing:
        assert standing_findings(files[key]) == [], key


@pytest.mark.parametrize("files, exempt, finding", [
    ({"C1": "## Standing", "P2": "log"}, {"P2"}, None),
    ({"C1": "## Standing", "C14": "log"}, set(), "C14 has no Standing"),
    ({"C1": "## Standing", "P2": "## Standing"}, {"P2"},
     "P2 has a Standing block: take it off"),
    ({"C1": "## Standing"}, {"P2"}, "P2 is listed"),
], ids=["clean", "new-file-without", "listed-file-gained-one",
        "listed-file-gone"])
def test_standing_roster_findings_name_each_break(
        files: dict[str, str], exempt: set[str], finding: str | None) -> None:
    found = standing_roster_findings(files, exempt)
    if finding is None:
        assert found == []
    else:
        assert len(found) == 1 and finding in found[0], found


def test_a_decisions_file_off_the_list_opens_with_standing() -> None:
    assert standing_roster_findings(read_decision_files(),
                                    read_standing_exempt()) == []
