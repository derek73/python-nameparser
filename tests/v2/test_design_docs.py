"""The design docs' folder layout: names, the index, citations."""
from __future__ import annotations

import re
from pathlib import Path

import pytest

from tests.v2.design_docs import (
    DECISIONS_DIR, MENTION_RE, RULES_DIR, read_decision_files, read_index,
    REFERENCE_LISTS, _POINTER_RE, _clean, _entries, _hits,
    has_standing, read_reference_lists, read_rules_text,
    reference_lists, resolve, retired_ids,
    reused_id_findings,
    rule_file_ids, slugify, standing_findings, standing_roster_findings,
    stem_for)
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
        "- 2026-09-14 (Derek) — THE LEAN.\n"
        "- 2026-09-18 — THE BLAST RADIUS.\n"
        "- 2026-09-18, REVIEW ROUND — WHAT IT MOVED.\n"
        "- 2026-09-19 (Derek) (item (ii) superseded by #9, decisions/S7) — Z.\n"
        "- 2026-10-18 (Derek), #718 — THE REPORT.\n"
        "- 2026-10-18, #718 review — THE COMMA.\n"
        "- 2026-10-19 #730 one — X.\n"
        "- 2026-10-19 #730 two — Y.\n"
        "- 2026-10-21 #731/#732 — X.\n"
        "- 2026-10-21 #731/#732 — Y.\n"
        "- 2026-09-19 — W.\n"
        "- 2026-10-22 #740 — A.\n"
        "- 2026-10-22 #740 (part superseded by #9) — B.\n"
        "- 2026-10-23 #741 — X and Y.\n"
        "- 2026-10-23 #741 — Y.\n"
        "- 2026-10-24, #742 review — A.\n"
        "- 2026-10-24, #742 review round — B.\n"
        "- 2026-10-25 (Derek), v2.4 review — A.\n"
        "- 2026-10-25 (Derek), v2.5 review — B.\n"
        "- 2026-10-26, corrected 2026-10-27 — A.\n"
        "- 2026-10-26 — B.\n"
        "- 2026-09-19 (Derek), #533 — Z.\n"
        "- 2026-10-28 (Derek), scope corrected 2026-11-09 — Q.\n"
        "- 2026-10-30, corrected 2026-11-10 and 2026-11-11 — S.\n"
        "- 2026-10-30 — T.\n"
        "- 2026-09-14, corrected 2026-09-17 — WHERE THE FACT LIVES.\n"
        "- 2026-07 (v2 core, PR #288) — v1 parity.\n"
        "- 2026-10-01 (Derek), #562 — SUPERSEDED by #613. The pair.\n"
        "- 2026-09-24 — SUPERSEDED IN PART: the mark.\n"
        "- 2026-10-03 #549 — SUPERSEDED: the skip is reversed.\n"
        "- 2026-10-04 #611 (in part superseded by #613) — FILED.\n"
        "- 2026-10-06 #613 — DECIDED ONCE.\n"
        "- 2026-10-31 #750 (PR on x) — A.\n"
        "- 2026-10-31 #750 — B.\n"
        "- 2026-10-31 #750 — C.\n")


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
    ("- The lean — 2026-09-14 (Derek).\n", None),
    ("- The fact — 2026-09-14, corrected.\n", None),
    ("- One of two — 2026-09-14.\n", "ambiguous pointer 2026-09-14"),
    ("- The lean — 2026-09-14 (Derek), decided again.\n", None),
    ("- The blast — 2026-09-18.\n", None),
    ("- Old shape — 2026-09-19 (Derek).\n", None),
    ("- The report — 2026-10-18 #718.\n", None),
    ("- The comma — 2026-10-18 #718 review.\n", None),
    ("- One of two — 2026-10-19 #730.\n", "ambiguous pointer 2026-10-19 #730"),
    ("- Either twin — 2026-10-21 #731/#732.\n",
     "ambiguous pointer 2026-10-21 #731"),
    ("- The second twin — 2026-10-21 #731/#732, Y.\n", None),
    ("- Noted twin — 2026-10-22 #740, B.\n", None),
    ("- Opens with — 2026-10-23 #741, Y.\n", None),
    ("- Trailing space — 2026-09-14 \n", "ambiguous pointer 2026-09-14"),
    ("- Full words — 2026-10-26, corrected 2026-10-27.\n", None),
    ("- Typo — 2026-10-18 #718 reveiw.\n", "continues no entry's head"),
    ("- Typo — 2026-09-19 (Dreek).\n", "continues no entry's head"),
    ("- Copied head — 2026-10-24, #742 review round.\n", None),
    ("- Two — 2026-10-24 #742 review round, 2026-10-23 #741, Y.\n", None),
    ("\nNot standing: 2026-10-18 #718 reveiw.\n", "not-standing pointer"),
    # The inner dates name no entry, so reading one as a second pointer
    # is a finding rather than a silent extra citation.
    ("- One candidate — 2026-10-28 (Derek), scope corrected 2026-11-09.\n",
     None),
    ("- Cut short — 2026-10-30, corrected 2026-11-10.\n", None),
    ("- Two kinds — 2026-09-24, 2026-10-23 #741, Y.\n", None),
    ("- The round — 2026-09-18, REVIEW ROUND.\n", None),
    ("- Decided once — 2026-10-04 #613.\n", "no entry 2026-10-04 #613"),
    ("- Decided once — 2026-10 #613.\n", "no entry 2026-10 #613"),
    ("- Decided once — 2026-10-06 #613 and 2026-11-01 #999.\n",
     "no entry 2026-11-01 #999"),
    ("\nNot standing: 2026-10-04 #612.\n", "names no entry"),
    ("- Beside a labelled head — 2026-10-31 #750, C.\n", None),
    ("- The labelled head — 2026-10-31 #750 (PR on x).\n", None),
    ("- Either bare twin — 2026-10-31 #750.\n",
     "ambiguous pointer 2026-10-31 #750"),
    ("- Keyed by no text — 2026-10-31 #750, D.\n",
     "ambiguous pointer 2026-10-31 #750"),
    ("- One bare head — 2026-10-18 #718, THE REPORT.\n",
     "continues no entry's head"),
    ("\nNot standing: 2026-10-31 #750, typo here.\n",
     "ambiguous not-standing pointer 2026-10-31 #750"),
    ("\nNot standing: 2026-10-31 #750.\n",
     "ambiguous not-standing pointer 2026-10-31 #750"),
    ("\nNot standing: 2026-10-31 #750, C.\n", None),
], ids=["clean", "no-pointer", "wrong-date", "number-prefix", "superseded",
        "announcing-is-live", "date-only", "date-only-qualified",
        "date-only-qualified-by-its-words", "date-only-shared-date",
        "date-only-qualifier-then-prose", "date-only-bare-beside-qualified",
        "supersession-note-ignored", "issue-bare-picks-unqualified-head",
        "issue-qualified", "issue-shared-ambiguous", "twins-unqualified-ambiguous",
        "twins-qualified-by-text", "twins-differing-by-a-note",
        "twins-text-opens-with-not-contains", "trailing-space-ambiguous",
        "date-inside-the-words", "issue-words-typo", "date-words-typo",
        "head-copied-whole-reads-its-issue", "comma-joined-second-pointer",
        "not-standing-unmatched-words",
        "one-candidate-date-inside-its-words", "cut-words-date-inside",
        "date-only-then-comma-and-an-issue-pointer",
        "date-only-qualified-beside-a-bare-date",
        "later-issue-in-a-head",
        "month-only-date", "second-pointer",
        "not-standing-missing", "twins-beside-a-labelled-head",
        "labelled-head-beside-twins", "twins-beside-a-label-unqualified",
        "twins-beside-a-label-keyed-by-no-text",
        "one-bare-head-words-are-no-twin-key",
        "not-standing-twin-key-typo-ambiguous",
        "not-standing-twins-unqualified-ambiguous",
        "not-standing-twin-key-resolves"])
def test_standing_findings_name_each_broken_pointer(
        standing: str, finding: str | None) -> None:
    found = standing_findings(f"# C1 — x\n\n## Standing\n\n{standing}\n"
                              + _LOG)
    if finding is None:
        assert found == []
    else:
        assert len(found) == 1 and finding in found[0], found


@pytest.mark.parametrize("pointer, head", [
    ("2026-10-18 #718.", "2026-10-18 (Derek), #718"),
    ("2026-10-18 #718 review.", "2026-10-18, #718 review"),
    ("2026-09-14 (Derek), decided again.", "2026-09-14 (Derek)"),
    ("2026-09-14, corrected.", "2026-09-14, corrected 2026-09-17"),
    ("2026-09-18.", "2026-09-18"),
    ("2026-09-18, REVIEW ROUND.", "2026-09-18, REVIEW ROUND"),
    ("2026-10-21 #731/#732, X.", "2026-10-21 #731/#732 — X."),
    ("2026-10-21 #731/#732, Y.", "2026-10-21 #731/#732 — Y."),
    ("2026-09-19.", "2026-09-19"),
    ("2026-09-19 (Derek), again.",
     "2026-09-19 (Derek) (item (ii) superseded by #9, decisions/S7)"),
    ("2026-10-23 #741, Y.", "2026-10-23 #741 — Y."),
    ("2026-10-24 #742 review.", "2026-10-24, #742 review"),
    ("2026-10-24 #742 review round.", "2026-10-24, #742 review round"),
    ("2026-10-25 (Derek), v2.5 review.", "2026-10-25 (Derek), v2.5 review"),
    ("2026-10-26, corrected 2026-10-27.",
     "2026-10-26, corrected 2026-10-27"),
    ("2026-09-19 (Derek), #533.", "2026-09-19 (Derek), #533"),
])
def test_a_pointer_resolves_to_the_entry_its_words_name(
        pointer: str, head: str) -> None:
    # Resolving is not enough: a pointer that lands on a sibling entry
    # of the same date and issue passes every finding, so pin the target.
    line = f"- x — {pointer}"
    m = _POINTER_RE.search(line, line.index("— "))
    assert m is not None
    assert [f"{h} — {r}" if "—" in head else h
            for h, r in _hits(line, m, _entries(_LOG))] == [head]


def test_a_supersession_note_is_dropped_in_any_case_and_only_when_closed(
        ) -> None:
    assert _clean("2026-09-19 (SUPERSEDED in part by #9) x") == "2026-09-19 x"
    assert _clean("2026-09-19 (superseded by #9 #500") == (
        "2026-09-19 (superseded by #9 #500")
    assert _clean("2026-09-19 (Derek)") == "2026-09-19 (Derek)"


def test_a_bold_date_opens_an_entry() -> None:
    assert _entries("- **2026-10-14 #679 — the rest (Derek).** Text.\n"
                    "- **2026-10-15/16** — the model.\n"
                    "- **Declined 2026-09-25 (#540)** — not an entry.\n"
                    "- **NFKC was declined.** Nor this.\n") == [
        ("2026-10-14 #679", "the rest (Derek).** Text."),
        ("2026-10-15/16", "the model.")]
    assert _entries("- **2026-10-15 #5**: text.\n"
                    "- **2026-10-14 #679** (Derek) — x.\n"
                    "- **2026-10-16** — **SUPERSEDED by** 2026-10-17.\n") == [
        ("2026-10-15 #5", "text."), ("2026-10-14 #679 (Derek)", "x."),
        ("2026-10-16", "SUPERSEDED by** 2026-10-17.")]
    head = "# C1 — x\n\n## Standing\n\n{}\n\n## Log\n\n"
    assert standing_findings(
        head.format("- a — 2026-10-16.")
        + "- **2026-10-16** — **SUPERSEDED by** 2026-10-17.\n") == [
        "superseded entry 2026-10-16 #None"]
    assert standing_findings(
        head.format("- a — 2026-10-15 #5.")
        + "- **2026-10-15 #5**: SUPERSEDED by 2026-10-17 #6.\n") == [
        "superseded entry 2026-10-15 #5"]
    assert standing_findings(
        head.format("- a — 2026-10-14 #679 (Derek).")
        + "- **2026-10-14 #679** (Derek) — x.\n"
        "- **2026-10-14 #679** (Joe) — y.\n") == []


def test_a_dated_title_founds_no_entry() -> None:
    title = "# cjk-full-stops — which characters (2026-09-10, #322/#323)\n\n"
    block = "## Standing\n\n- Four stops. — 2026-09-10 #322.\n\n## Log\n\n"
    assert standing_findings(title + block + "- **A.** B.\n") == [
        "no entry 2026-09-10 #322"]
    assert standing_findings(
        title + block + "- 2026-09-10 #322/#323 — the bundle below.\n"
        "- **A.** B.\n") == []
    assert standing_findings(
        title + block.replace("2026-09-10 #322", "2026-10-14 #679")
        + "- **A.** B.\n- **2026-10-14 #679 — the rest.** C.\n") == []


def test_standing_needs_a_log_after_it() -> None:
    assert standing_findings("# C1 — x\n\n## Standing\n\n- a\n") == [
        "## Standing without a ## Log after it"]
    assert standing_findings(
        "# C1 — x\n\n" + _LOG + "\n## Standing\n\n- a — 2026-10-06 #613.\n"
    ) == ["## Log before ## Standing: the block opens the file"]
    assert standing_findings(
        "# C1 — x\n\n" + _LOG + "\n## Standing\n\n- a — 2026-10-06 #613.\n\n"
        + _LOG) == ["## Log before ## Standing: the block opens the file"]


def test_standing_findings_leave_an_absent_block_to_the_roster() -> None:
    assert standing_findings("# C1 — x\n\n" + _LOG) == []


def test_a_prose_mention_of_the_heading_is_no_block() -> None:
    assert not has_standing("- 2026-10-20 — follows the `## Standing` rule.")
    assert not has_standing("### Standing\n")
    assert has_standing("# C1 — x\n\n## Standing\n")


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
    with_standing = [k for k, t in files.items() if has_standing(t)]
    assert with_standing, "no decisions file has a Standing block"
    for key in with_standing:
        assert standing_findings(files[key]) == [], key


@pytest.mark.parametrize("files, finding", [
    ({"C1": "## Standing", "L": "- Declined: x."}, None),
    ({"C1": "## Standing", "C14": "- 2026-10-20 — the `## Standing` rule.",
      "L": "- Declined: x."}, "C14 has no Standing"),
    ({"C1": "## Standing", "C14": "log", "L": "- Declined: x."},
     "C14 has no Standing"),
    ({"C1": "## Standing", "L": "## Standing \n- a"},
     "'## Standing ' is not the heading"),
    ({"C1": "## Standing", "L": "### Standing\n- a"},
     "'### Standing' is not the heading"),
    ({"C1": "## Standing", "L": "  ## Standing\n- a"},
     "'  ## Standing' is not the heading"),
], ids=["clean", "prose-mention-is-no-block", "file-without",
        "misspelled-heading-trailing-space", "misspelled-heading-level",
        "misspelled-heading-indented"])
def test_standing_roster_findings_name_each_break(
        files: dict[str, str], finding: str | None) -> None:
    found = standing_roster_findings(files, {"L"}, frozenset({"L"}))
    if finding is None:
        assert found == []
    else:
        assert len(found) == 1 and finding in found[0], found


def test_reference_lists_are_the_links_under_their_heading() -> None:
    readme = ("## Named topics\n\n- [a-log — x](a-log.md)\n\n"
              "## Reference lists\n\nProse with [a link](x.md).\n\n"
              "- [b-list — y](b-list.md)\n- [c-list](c-list.md)\n\n"
              "## Later\n\n- [d-log — z](d-log.md)\n")
    assert reference_lists(readme) == {"b-list", "c-list"}
    for not_a_listing in ["* [e](e.md)", "> [e](e.md)", "- see [e](e.md)",
                          "- [x] see [e](e.md)"]:
        assert reference_lists(
            f"x\n## Reference lists\n\n{not_a_listing}\n"
            "- [e2 — y](e2.md)\n") == {"e2"}, not_a_listing
    for heading in ["### Reference lists", "## Reference lists (old)",
                    "## Reference lists "]:
        assert reference_lists(
            f"x\n{heading}\n\n- [e — y](e.md)\n") == set(), heading
    assert reference_lists("## Named topics\n\n- [a — x](a.md)\n") == set()


@pytest.mark.parametrize("files, finding", [
    ({"C1": "## Standing", "L": "- Declined: x."}, None),
    ({"C1": "## Standing", "L": "- Declined: x.\n- 2026-10-01 — y."},
     "L is a reference list but is shaped like a log"),
    ({"C1": "## Standing", "L": "- Declined: x.\n- (A) 2026-08-17 — parked."},
     "L is a reference list but is shaped like a log"),
    ({"C1": "## Standing", "L": "- **2026-10-01 #5 — y.**"},
     "L is a reference list but is shaped like a log"),
    ({"C1": "## Standing",
      "L": "# L — a bundle (2026-09-10, #322)\n\n- **NFKC declined.**"},
     "L is a reference list but is shaped like a log"),
    ({"C1": "## Standing",
      "L": "# L — x\n\n- abd — ADDED 2026-08-18, see decisions/P5.\n"
           "- (Derek's call) removed 2026-08-26.\n"},
     None),
    ({"C1": "## Standing", "L": "## Standing\n- x"},
     "L is a reference list and carries ## Standing"),
    ({"C1": "## Standing", "N": "- Declined: x."},
     "N is under Reference lists but is not one"),
], ids=["list", "list-with-entry", "list-with-tagged-date",
        "list-with-bold-entry", "list-with-dated-title",
        "list-with-dates-inside-lines", "list-with-standing",
        "list-new-since-the-rule"])
def test_a_reference_list_carries_no_standing_and_no_log(
        files: dict[str, str], finding: str | None) -> None:
    listed = {"N"} if "N" in files else {"L"}
    found = standing_roster_findings(files, listed, frozenset({"L"}))
    if finding is None:
        assert found == []
    else:
        assert len(found) == 1 and finding in found[0], found
    # Off the heading, the same file is a log with no block.
    if finding is None:
        assert standing_roster_findings(files, set(), frozenset({"L"})) == [
            "L has no Standing block: a decisions file opens with "
            "## Standing and ## Log"]


def test_every_decisions_file_opens_with_standing_or_is_a_reference_list(
        ) -> None:
    assert standing_roster_findings(read_decision_files(),
                                    read_reference_lists()) == []


def test_the_reference_lists_are_a_fixed_five() -> None:
    # Fixed when #762 finished (2026-10-22): a key added here would let a
    # new file skip its block, so the size is asserted rather than
    # trusted to the comment.
    assert len(REFERENCE_LISTS) == 5


_RETIRED_ENTRY = ("# X9 — a retired rule\n\n## Standing\n\n"
                  "Retired: 2026-10-20 #0 — folded into X1.\n\n"
                  "## Log\n\n- 2026-10-20 #0 — RETIRED.\n")


def _retirement_layout(tmp_path: Path, entry: str) -> tuple[Path, Path]:
    """A rules folder holding X1 and X9, and a decisions folder whose
    one indexed file, X9's, holds `entry`."""
    rules, decisions = tmp_path / "rules", tmp_path / "decisions"
    rules.mkdir(parents=True)
    decisions.mkdir()
    (rules / "README.md").write_text("# Rules\n", encoding="utf-8")
    for name in ("X-section.md", "X1-kept.md", "X9-reused.md"):
        (rules / name).write_text(f"# {name}\n", encoding="utf-8")
    (decisions / "README.md").write_text(
        "# Decisions\n\n- [X9 — a retired rule](X9-retired-rule.md)\n",
        encoding="utf-8")
    (decisions / "X9-retired-rule.md").write_text(entry, encoding="utf-8")
    return rules, decisions


def test_a_rule_file_reusing_a_retired_id_is_refused(tmp_path: Path) -> None:
    # The negative control the real tree cannot give (no rule is
    # retired yet): a decisions file recording X9's retirement and a
    # rule file carrying X9 again, read through the same readers the
    # real-tree test uses.
    rules, decisions = _retirement_layout(tmp_path, _RETIRED_ENTRY)
    assert rule_file_ids(rules) == {"X", "X1", "X9"}
    found = reused_id_findings(rule_file_ids(rules),
                               read_decision_files(decisions))
    assert found == ["rules/X9 reuses an ID decisions/X9 records as "
                     "retired: a new rule takes a new ID"]
    # and the Retired: line is what bites: the same files without it
    # pass
    rules, decisions = _retirement_layout(
        tmp_path / "control", _RETIRED_ENTRY.replace("Retired:", "Folded:"))
    assert reused_id_findings(rule_file_ids(rules),
                              read_decision_files(decisions)) == []


@pytest.mark.parametrize("line", [
    "**Retired:** 2026-10-20 #0", "- Retired: 2026-10-20 #0",
    "retired: 2026-10-20 #0", "Retired : 2026-10-20 #0",
    "  Retired: 2026-10-20 #0", "1. Retired: 2026-10-20 #0",
])
def test_a_misspelled_retired_line_is_a_finding(line: str) -> None:
    # each spelling would leave X9 out of retired_ids and the refusal
    # off for it
    entry = _RETIRED_ENTRY.replace("Retired: 2026-10-20 #0", line)
    assert retired_ids({"X9": entry}) == set()
    found = reused_id_findings({"X9"}, {"X9": entry})
    assert len(found) == 1 and "is not a line opening 'Retired:'" in found[0]


def test_a_retired_line_needs_a_rule_key() -> None:
    found = reused_id_findings(set(), {"some-slug": _RETIRED_ENTRY})
    assert found == ["decisions/some-slug carries a Retired: line but is "
                     "keyed by no rule ID, so it retires nothing"]


def test_no_rule_reuses_a_retired_id() -> None:
    """rules/README.md: a rule ID is never reused. No rule is retired
    on 2026-10-20, so on the real tree this passes with nothing to
    refuse; test_a_rule_file_reusing_a_retired_id_is_refused is what
    shows it bites. The readers must still reach both folders, or the
    pass would be vacuous for a second reason."""
    ids = rule_file_ids()
    assert {"C1", "S2", "H"} <= ids
    decisions = read_decision_files()
    assert "C1" in decisions
    assert reused_id_findings(ids, decisions) == []
