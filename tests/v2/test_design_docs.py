"""The design docs' folder layout: names, the index, citations."""
from __future__ import annotations

from pathlib import Path

import pytest

from tests.v2.design_docs import (
    MENTION_RE, read_index, resolve, slugify, stem_for)

_FIXTURE_FILES = ("S-suffixes.md", "S1-x.md",
                  "S2-case-signal-at-the-suffix-slot.md",
                  "vocabulary-collisions.md")


@pytest.fixture
def folder(tmp_path: Path) -> Path:
    (tmp_path / "README.md").write_text(
        "# Index\n\n"
        "## [Suffixes (S)](S-suffixes.md)\n\n"
        "- [S1 — x](S1-x.md)\n"
        "- [S2 — the case signal at the suffix slot]"
        "(S2-case-signal-at-the-suffix-slot.md)\n\n"
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
    assert stem_for("S2", "the case signal at the suffix slot") == (
        "S2-case-signal-at-the-suffix-slot")
    assert stem_for("S", "Suffixes") == "S-suffixes"
    assert stem_for("vocabulary-collisions", "when a word …") == (
        "vocabulary-collisions")


def test_read_index_keeps_order_and_keys(folder: Path) -> None:
    entries = read_index(folder)
    assert [e.key for e in entries] == [
        "S", "S1", "S2", "vocabulary-collisions"]
    assert entries[2].title == "S2 — the case signal at the suffix slot"
    assert entries[2].path == folder / "S2-case-signal-at-the-suffix-slot.md"
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


@pytest.mark.parametrize("text", [
    "docs/design/rules/S2-case-signal-at-the-suffix-slot.md",
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
    assert name("S2") == "S2-case-signal-at-the-suffix-slot.md"
    assert name("S9") is None
    assert name("README") is None
    assert resolve("decisions", "vocabulary-collisions", folder) == (
        folder / "vocabulary-collisions.md")
