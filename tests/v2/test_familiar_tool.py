"""Offline checks on tools/vocab/familiar.py, which writes the familiar
and spelling readings from the reviewed pairs (decisions/name-matching,
2026-11-08 FAMILIAR FORMS and 2026-11-12 ALTERNATE SPELLINGS ARE
OPT-IN; decisions/shipped-data-licences, 2026-11-13 THE NICKNAMES LIST
LEAVES).

The failure that matters is a pair the review did not ship written
anyway, a pair in another file than its row names, a pair from a source
the project may not use, or a regeneration that rewrites what the tool
does not own.
"""
from __future__ import annotations

import importlib.util
import sys
import tomllib
from pathlib import Path
from types import ModuleType

import pytest

from tests.checkout import require_checkout

# the tool loads tools/vocab/build.py, which reads the package's own
# modules by checkout path
require_checkout()

_PATH = Path(__file__).parents[2] / "tools" / "vocab" / "familiar.py"
_VOCAB = Path(__file__).parents[2] / "nameparser" / "vocab"


def _load() -> ModuleType:
    spec = importlib.util.spec_from_file_location("familiar", _PATH)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


tool = _load()


_FILE = '''schema = 1

[[word]]
text = "jr"
generation = {}

[[word]]
text = "ed"
given = { note = "x" }
credential = {}
'''


def _familiar(**words: set[str]) -> dict[str, dict[str, set[str]]]:
    return {w: {"familiar": names} for w, names in words.items()}


def test_a_held_word_gains_a_line_and_the_rest_an_entry_in_the_block() -> None:
    words = _familiar(ed={"edward"}, bill={"william"},
                      al={"alfred", "albert"})
    out = tool.rewrite(_FILE, words, "en.toml")
    assert out is not None
    data = tomllib.loads(out)
    by_text = {e["text"]: e for e in data["word"]}
    assert by_text["ed"]["familiar"]["short_for"] == ["edward"]
    assert by_text["al"]["familiar"] == {
        "short_for": ["albert", "alfred"], "note": tool.REVIEWED_SOURCE}
    # the held word keeps its place; the new ones follow in text order
    assert [e["text"] for e in data["word"]] == ["jr", "ed", "al", "bill"]
    # regenerating is idempotent, and stripping gives the file back
    assert tool.rewrite(out, words, "en.toml") == out
    assert tool.strip(out) == _FILE
    assert tool.rewrite(out, {}, "en.toml") == _FILE


def test_a_file_only_the_tool_wrote_goes_when_it_holds_nothing() -> None:
    made = tool.rewrite(None, _familiar(salvu={"saviour"}), "xx.toml")
    assert made is not None and tomllib.loads(made)["word"][0]["text"] == "salvu"
    assert tool.rewrite(made, {}, "xx.toml") is None


def test_held_words_and_the_block_are_each_placed_by_their_rule() -> None:
    # each held word's lines go right under its own text, and the new
    # words go in one block in the build's word order, by kind before
    # text: a familiar form ahead of a spelling whatever their texts
    words = {"aa": {"spelling": {"ab"}}, "zz": {"familiar": {"zzz"}},
             "jr": {"familiar": {"junior"}}, "ed": {"familiar": {"edward"}}}
    out = tool.rewrite(_FILE, words, "en.toml")
    assert out is not None
    lines = out.split("\n")
    for held in ("jr", "ed"):
        at = lines.index(f'text = "{held}"')
        assert lines[at + 1].startswith("familiar = {"), held
    block = lines[lines.index(tool.BEGIN):lines.index(tool.END)]
    assert [line for line in block if line.startswith("text = ")] == [
        'text = "zz"', 'text = "aa"']
    tool.build.compile_files({"en.toml": out})


def test_a_familiar_reading_written_by_hand_is_refused() -> None:
    hand = _FILE.replace('given = { note = "x" }',
                         'familiar = { short_for = ["edgar"], note = "mine" }')
    with pytest.raises(ValueError, match="does not own"):
        tool.rewrite(hand, _familiar(ed={"edward"}), "en.toml")


def test_every_shipped_reading_is_one_the_tool_writes() -> None:
    # no compiler's list is shipped: a list copied whole keeps its
    # licence (decisions/shipped-data-licences, 2026-11-12 #1370 FACTS
    # WE MEASURE, 2026-11-13 THE NICKNAMES LIST LEAVES), so every
    # familiar and spelling reading is the reviewed file's
    by_kind: dict[str, list[tuple[str, str]]] = {k: [] for k in tool.KINDS}
    for path in sorted(_VOCAB.glob("*.toml")):
        for e in tomllib.loads(path.read_text())["word"]:
            for kind in tool.KINDS:
                if kind in e:
                    by_kind[kind].append((path.name, e[kind]["note"]))
    assert len(by_kind["familiar"]) >= 800 and len(by_kind["spelling"]) >= 300
    notes = {note for found in by_kind.values() for _, note in found}
    assert notes == {tool.REVIEWED_SOURCE}


def test_stripping_the_tree_leaves_no_familiar_or_spelling_reading() -> None:
    # without the review: every familiar and spelling reading in the
    # tree is one the tool owns, and taking them out leaves a file the
    # build reads
    for path in sorted(_VOCAB.glob("*.toml")):
        text = path.read_text()
        stripped = tool.strip(text)
        for kind in tool.KINDS:
            assert f"{kind} = " not in stripped, (path.name, kind)
        tomllib.loads(stripped)  # still a file


def test_the_tree_is_what_the_tool_writes_from_the_review() -> None:
    # the source is committed, so this needs no cache
    assert tool.stale(tool.source()) == []


# -- the format's edge cases -------------------------------------------------

@pytest.mark.parametrize("markers", [
    [tool.BEGIN], [tool.END], [tool.END, tool.BEGIN],
    [tool.BEGIN, tool.END, tool.BEGIN, tool.END],
])
def test_a_generated_block_with_broken_markers_is_refused(
        markers: list[str]) -> None:
    text = _FILE + "\n".join(markers) + "\n"
    with pytest.raises(ValueError, match="en.toml: the generated block"):
        tool.rewrite(text, _familiar(ed={"edward"}), "en.toml")


# -- the command, on a planted review and vocabulary ----------------------------

def _reviewed(*rows: tuple[str, ...]) -> str:
    return "\n".join(["\t".join(tool.REVIEWED_HEADER),
                      *("\t".join(r) for r in rows)]) + "\n"


def _row(a: str, b: str, category: str, status: str = "",
         languages: str = "pl", source: str = "orcid") -> tuple[str, ...]:
    return (a, b, category, status, category, category, "why", languages,
            source, "3")


@pytest.fixture
def planted(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """A planted review and a vocabulary folder holding two files, one
    of them with a reading the tool wrote that the review no longer
    gives: never the real tree."""
    reviewed = tmp_path / "reviewed.tsv"
    reviewed.write_text(_reviewed(
        _row("aaron", "erin", "different-name", languages="en"),
        _row("bill", "william", "familiar", languages="en", source="fec"),
        _row("will", "william", "familiar", languages="en",
             source="congress")), encoding="utf-8")
    monkeypatch.setattr(tool, "REVIEWED", reviewed)
    vocab = tmp_path / "vocab"
    vocab.mkdir()
    (vocab / "en.toml").write_text(_FILE, encoding="utf-8")
    stray = tool.rewrite(None, _familiar(sepp={"josef"}), "de.toml")
    assert stray is not None
    (vocab / "de.toml").write_text(stray, encoding="utf-8")
    monkeypatch.setattr(tool, "VOCAB", vocab)
    return vocab


def test_check_reports_stale_until_write_brings_the_files_current(
        planted: Path) -> None:
    assert tool.main(["--check"]) == 1
    assert tool.stale(tool.source(), planted) == [
        planted / "de.toml", planted / "en.toml"]
    assert tool.main(["--write"]) == 0
    assert tool.main(["--check"]) == 0
    written = {p.name: p.read_text(encoding="utf-8")
               for p in sorted(planted.glob("*.toml"))}
    # the file only the tool wrote is gone with its reading
    assert set(written) == {"en.toml"}
    # the written file passes the build's checks
    tool.build.compile_files(written)
    by_text = {e["text"]: e for e in tomllib.loads(written["en.toml"])["word"]}
    assert by_text["bill"]["familiar"] == {
        "short_for": ["william"], "note": tool.REVIEWED_SOURCE}
    assert by_text["will"]["familiar"]["short_for"] == ["william"]
    # a pair recorded and not shipped is left out
    assert "erin" not in by_text and "aaron" not in by_text


# -- the reviewed pairs (decisions/name-matching, 2026-11-12 ALTERNATE
# SPELLINGS ARE OPT-IN) --------------------------------------------------------

def test_the_reviewed_pairs_are_placed_by_category_and_language() -> None:
    rows = tool.read_reviewed(_reviewed(
        _row("george", "georgios", "translation", languages="el"),
        _row("george", "jorge", "split", languages="es"),
        _row("john", "jon", "split", "pending", "en"),
        _row("kasia", "katarzyna", "familiar", languages="pl en"),
        _row("kasia", "kaśka", "refused", "decided"),
        _row("lukasz", "łukasz", "spelling"),
        _row("natalia", "natalya", "spelling"),
        _row("olga", "olha", "spelling", "decided", "uk"),
    ))
    placed = tool.place(rows)
    # a familiar pair on its shorter name, in each file its row names
    assert placed["pl"]["kasia"] == {"familiar": {"katarzyna"}}
    assert placed["en"]["kasia"] == {"familiar": {"katarzyna"}}
    # a spelling on the second name in order, listing the first, save
    # one the match's fold reads `folded` already
    assert placed["pl"]["natalya"] == {"spelling": {"natalia"}}
    assert "łukasz" not in placed["pl"] and "lukasz" not in placed["pl"]
    # a split the maintainer decided ships as decided
    assert placed["uk"]["olha"] == {"spelling": {"olga"}}
    # pending, refused, split and recorded pairs ship nowhere
    assert "jon" not in placed["en"] and "john" not in placed["en"]
    assert "kaśka" not in placed["pl"]
    assert "es" not in placed and "el" not in placed


def test_a_word_of_both_kinds_takes_a_reading_of_each() -> None:
    words = {"ed": {"familiar": {"edward", "edwin"}},
             "zzs": {"familiar": {"zzt"}, "spelling": {"zzr"}}}
    out = tool.rewrite(_FILE, words, "en.toml")
    assert out is not None
    by_text = {e["text"]: e for e in tomllib.loads(out)["word"]}
    assert by_text["ed"]["familiar"] == {
        "short_for": ["edward", "edwin"], "note": tool.REVIEWED_SOURCE}
    assert by_text["zzs"]["spelling"] == {
        "spelling_of": ["zzr"], "note": tool.REVIEWED_SOURCE}
    assert by_text["zzs"]["familiar"]["short_for"] == ["zzt"]
    # regenerating is idempotent, and stripping gives the file back
    assert tool.rewrite(out, words, "en.toml") == out
    assert tool.strip(out) == _FILE
    tool.build.compile_files({"en.toml": out})


def test_a_spelling_written_by_hand_is_refused() -> None:
    hand = _FILE.replace('given = { note = "x" }',
                         'spelling = { spelling_of = ["edd"], note = "mine" }')
    with pytest.raises(ValueError, match="holds a spelling reading"):
        tool.rewrite(hand, {"ed": {"spelling": {"edd"}}}, "en.toml")


def test_a_hand_note_opening_with_the_source_is_not_the_tools() -> None:
    hand = _FILE.replace(
        'given = { note = "x" }',
        'familiar = { short_for = ["edgar"], '
        f'note = "{tool.REVIEWED_SOURCE}, and a census I read" }}')
    with pytest.raises(ValueError, match="does not own"):
        tool.rewrite(hand, _familiar(ed={"edward"}), "en.toml")


def test_a_reading_on_a_word_the_file_holds_goes_under_its_text() -> None:
    out = tool.rewrite(_FILE, _familiar(jr={"junior"}), "en.toml")
    assert out is not None
    data = tomllib.loads(out)
    assert data["word"][0] == {
        "text": "jr", "generation": {},
        "familiar": {"short_for": ["junior"], "note": tool.REVIEWED_SOURCE}}
    assert tool.BEGIN not in out
    assert tool.strip(out) == _FILE


@pytest.mark.parametrize(("rows", "match"), [
    ((("a",),), "fields"),
    ((_row("kasia", "katarzyna", "nickname"),), "'nickname' is not one of"),
    ((_row("kasia", "katarzyna", "familiar", "held"),), "status 'held'"),
    ((_row("kasia", "katarzyna", "familiar", "pending"),), "a pending pair is a split"),
    ((_row("kasia", "katarzyna", "split", "decided"),), "no longer is"),
    ((_row("kasia", "katarzyna", "refused"),), "only a decided one is refused"),
    ((_row("katarzyna", "kasia", "familiar"),), "in order"),
    ((_row("Kasia", "katarzyna", "familiar"),), "normalized"),
    ((_row("kasia", "katarzyna", "familiar"),
      _row("kasia", "katarzyna", "familiar")), "listed twice or out of order"),
    ((_row("lukasz", "łukasz", "spelling"),
      _row("kasia", "katarzyna", "familiar")), "listed twice or out of order"),
    ((_row("kasia", "katarzyna", "familiar", languages=""),), "needs a file"),
    # a pair from a list of familiar forms, not data the project measured
    ((_row("kasia", "katarzyna", "familiar", source="nicknames-spelling"),),
     "source 'nicknames-spelling' is not one of"),
    # Wikidata joins only with its fetch tool (#1387)
    ((_row("kasia", "katarzyna", "familiar", source="wikidata"),),
     "source 'wikidata' is not one of"),
])
def test_a_malformed_review_is_refused(rows: tuple[tuple[str, ...], ...],
                                       match: str) -> None:
    with pytest.raises(ValueError, match=match):
        tool.read_reviewed(_reviewed(*rows))


def test_the_sources_are_the_ones_whose_counts_the_tree_reproduces() -> None:
    # a widening needs its counting recipe or tool in the tree first
    assert tool.REVIEW_SOURCES == {"orcid", "fec", "congress"}


@pytest.mark.parametrize("source", sorted(tool.REVIEW_SOURCES))
def test_each_source_the_project_may_use_is_accepted(source: str) -> None:
    (row,) = tool.read_reviewed(_reviewed(
        _row("kasia", "katarzyna", "familiar", source=source)))
    assert row["source"] == source


def test_the_committed_review_ships_what_was_agreed_or_decided_and_no_more() -> None:
    # offline: every familiar pair agreed or decided is a familiar form
    # and every spelling an alternate spelling, read pair by pair, and
    # no other pair of the review is either
    from nameparser import Lexicon, Parser
    from nameparser._match import _forms
    rows = tool.load_reviewed()
    assert len(rows) >= 1600
    lexicon = Lexicon.default()
    for r in rows:
        a, b = r["a"], r["b"]
        familiar = b in lexicon._familiar_forms(a)
        alternate = b in lexicon._alternate_spellings(a)
        folded = not _forms(a).isdisjoint(_forms(b))
        assert familiar == (r["category"] == "familiar"), (a, b)
        assert alternate == (r["category"] == "spelling" and not folded), (a, b)
        if r["category"] == "spelling" and folded:
            # a keyboard's spelling, read `folded` by default instead
            assert Parser().matching().check(f"{a} Smith", f"{b} Smith").consistent
    # the spellings stay out of the default's listed spellings
    assert not any(lexicon._headwords(r["a"], "given")
                   & lexicon._headwords(r["b"], "given")
                   for r in rows if r["category"] == "spelling")
