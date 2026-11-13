"""Offline checks on tools/vocab/familiar.py, which writes the familiar
readings from the nicknames list (decisions/name-matching, 2026-11-08
FAMILIAR FORMS, 2026-11-09 THE NICKNAMES LIST and 2026-11-12 ENGLISH
ONLY UNTIL REBUILT).

The list is a file cached outside the tree, so these read a list built
here in its layout, and the tree's own files: the failure that matters
is a refused pair written anyway, a pair in another file than
English's, or a regeneration that rewrites what the tool does not own.
"""
from __future__ import annotations

import hashlib
import importlib.util
import io
import os
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


def test_a_held_word_gains_a_line_and_the_rest_an_entry_in_the_block() -> None:
    words = {"ed": {"edward"}, "bill": {"william"},
             "al": {"alfred", "albert"}}
    out = tool.rewrite(_FILE, words, "en.toml")
    assert out is not None
    data = tomllib.loads(out)
    by_text = {e["text"]: e for e in data["word"]}
    assert by_text["ed"]["familiar"]["short_for"] == ["edward"]
    assert by_text["al"]["familiar"] == {
        "short_for": ["albert", "alfred"], "note": tool.NICKNAMES_SOURCE}
    # the held word keeps its place; the new ones follow in text order
    assert [e["text"] for e in data["word"]] == ["jr", "ed", "al", "bill"]
    # regenerating is idempotent, and stripping gives the file back
    assert tool.rewrite(out, words, "en.toml") == out
    assert tool.strip(out) == _FILE
    assert tool.rewrite(out, {}, "en.toml") == _FILE


def test_a_file_only_the_tool_wrote_goes_when_it_holds_nothing() -> None:
    made = tool.rewrite(None, {"salvu": {"saviour"}}, "xx.toml")
    assert made is not None and tomllib.loads(made)["word"][0]["text"] == "salvu"
    assert tool.rewrite(made, {}, "xx.toml") is None


def test_a_familiar_reading_written_by_hand_is_refused() -> None:
    hand = _FILE.replace('given = { note = "x" }',
                         'familiar = { short_for = ["edgar"], note = "mine" }')
    with pytest.raises(ValueError, match="does not own"):
        tool.rewrite(hand, {"ed": {"edward"}}, "en.toml")


def test_every_shipped_reading_is_one_the_tool_writes() -> None:
    # nam_dict's pairs are not shipped: a compiler's list copied whole
    # keeps its licence, and nam_dict's is the GFDL
    # (decisions/shipped-data-licences, 2026-11-12 #1370 FACTS WE
    # MEASURE), so every familiar and spelling reading is the nicknames
    # list's, in NICKNAMES_TAG's file, or the reviewed file's
    by_kind: dict[str, list[tuple[str, str]]] = {k: [] for k in tool.KINDS}
    for path in sorted(_VOCAB.glob("*.toml")):
        for e in tomllib.loads(path.read_text())["word"]:
            for kind in tool.KINDS:
                if kind in e:
                    by_kind[kind].append((path.name, e[kind]["note"]))
    assert len(by_kind["familiar"]) >= 1000 and len(by_kind["spelling"]) >= 300
    notes = {note for found in by_kind.values() for _, note in found}
    assert notes <= tool._OWNED_NOTES
    assert not any("nam_dict" in note for note in notes)
    assert {name for found in by_kind.values() for name, note in found
            if tool.NICKNAMES_SOURCE in note} == {f"{tool.NICKNAMES_TAG}.toml"}


def test_stripping_the_tree_leaves_no_familiar_reading() -> None:
    # without the source: every familiar reading in the tree is one the
    # tool owns, and taking them out leaves a file the build reads
    for path in sorted(_VOCAB.glob("*.toml")):
        text = path.read_text()
        stripped = tool.strip(text)
        assert "familiar = " not in stripped, path.name
        tomllib.loads(stripped)  # still a file


#: The cached files' folder, worked out without creating it as
#: name_usage.cache_dir() does: collecting this module must write
#: nothing.
_CACHE = Path(os.environ.get(
    "NAMEPARSER_TOOLS_CACHE", Path.home() / ".cache" / "nameparser-tools"))


@pytest.mark.skipif(
    not (_CACHE / tool.NICKNAMES_FILE).exists(),
    reason="the list is not cached (tools/vocab/familiar.py --fetch)")
def test_the_tree_is_what_the_tool_writes_from_the_cached_list() -> None:
    assert tool.stale(tool.source()) == []


def test_the_shipped_refusals_read() -> None:
    # offline: the reviewed list parses, whatever is cached
    refused = tool.load_exclusions()
    assert refused
    assert set(refused.values()) <= tool.EXCLUSION_CATEGORIES


# -- the format's edge cases -------------------------------------------------

@pytest.mark.parametrize("markers", [
    [tool.BEGIN], [tool.END], [tool.END, tool.BEGIN],
    [tool.BEGIN, tool.END, tool.BEGIN, tool.END],
])
def test_a_generated_block_with_broken_markers_is_refused(
        markers: list[str]) -> None:
    text = _FILE + "\n".join(markers) + "\n"
    with pytest.raises(ValueError, match="en.toml: the generated block"):
        tool.rewrite(text, {"ed": {"edward"}}, "en.toml")


# -- the command, on a planted cache and vocabulary ----------------------------

_PLANTED_LIST = ("name1,relationship,name2\r\n"
                 "william,has_nickname,will\r\n"
                 "william,has_nickname,bill\r\n"
                 "aaron,has_nickname,erin\r\n")
_PLANTED_REVIEWED = "\t".join(tool.REVIEWED_HEADER) + "\n"
_PLANTED_REFUSED = ("full\tnickname\tcategory\treason\n"
                    "aaron\terin\tdifferent-name\tresemblance only\n")


@pytest.fixture
def planted(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """A cache holding a planted nicknames list, pinned by its own hash,
    a refusals file, and a vocabulary folder holding two files, one of
    them with a reading the tool wrote in another language's file: never
    the real cache or tree."""
    cache = tmp_path / "cache"
    cache.mkdir()
    monkeypatch.setenv("NAMEPARSER_TOOLS_CACHE", str(cache))
    listed = _PLANTED_LIST.encode("utf-8")
    (cache / tool.NICKNAMES_FILE).write_bytes(listed)
    monkeypatch.setattr(tool, "NICKNAMES_SHA256",
                        hashlib.sha256(listed).hexdigest())
    refused = tmp_path / "refused.tsv"
    refused.write_text(_PLANTED_REFUSED, encoding="utf-8")
    monkeypatch.setattr(tool, "NICKNAMES_EXCLUDED", refused)
    reviewed = tmp_path / "reviewed.tsv"
    reviewed.write_text(_PLANTED_REVIEWED, encoding="utf-8")
    monkeypatch.setattr(tool, "REVIEWED", reviewed)
    vocab = tmp_path / "vocab"
    vocab.mkdir()
    (vocab / "en.toml").write_text(_FILE, encoding="utf-8")
    stray = tool.rewrite(None, {"sepp": {"josef"}}, "de.toml")
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
        "short_for": ["william"], "note": tool.NICKNAMES_SOURCE}
    assert by_text["will"]["familiar"]["short_for"] == ["william"]
    # the refused pair left out
    assert "erin" not in by_text


# -- the nicknames list ----------------------------------------------------------

_LIST = ("name1,relationship,name2\r\n"
         "richard,has_nickname,ricky\r\n"
         "richard,has_nickname,rick\r\n"
         "aaron,has_nickname,erin\r\n")


def test_the_lists_rows_read_as_name_and_nickname() -> None:
    assert tool.read_nicknames(_LIST) == [
        ("richard", "ricky"), ("richard", "rick"), ("aaron", "erin")]


@pytest.mark.parametrize(("text", "match"), [
    ("name,relationship,nickname\r\nrichard,has_nickname,ricky\r\n",
     "header"),
    (_LIST + "richard,is_spelling_of,rychard\r\n", "line 5"),
    (_LIST + "richard,has_nickname\r\n", "line 5"),
    (_LIST + "richard,has_nickname,\r\n", "empty name"),
    (_LIST + "richard,has_nickname,ricky\r\n", "repeats a row"),
    ("name1,relationship,name2\r\n", "holds no row"),
    # cut inside a row: csv would read it as a short last row
    (_LIST[:-6], "line break"),
])
def test_a_malformed_list_is_refused(text: str, match: str) -> None:
    with pytest.raises(ValueError, match=match):
        tool.read_nicknames(text)


_REFUSED = ("full\tnickname\tcategory\treason\n"
            "aaron\terin\tdifferent-name\tdistinct name\n")


def test_the_refusals_read_as_pair_and_category() -> None:
    assert tool.read_exclusions(_REFUSED) == {
        ("aaron", "erin"): "different-name"}


@pytest.mark.parametrize(("text", "match"), [
    (_REFUSED.replace("full\t", "name\t"), "header"),
    (_REFUSED + "x\ty\tspelling\n", "four"),
    (_REFUSED + "x\ty\ttypo\tone letter\n", "'typo' is not one of"),
    (_REFUSED + "x\ty\tspelling\t \n", "needs its reason"),
    (_REFUSED + "aaron\terin\tunclear\tagain\n", "listed twice"),
])
def test_a_malformed_refusal_is_refused(text: str, match: str) -> None:
    with pytest.raises(ValueError, match=match):
        tool.read_exclusions(text)


def test_a_refusal_naming_no_row_of_the_list_is_refused() -> None:
    # a new commit of the list that drops a row leaves its refusal stale
    with pytest.raises(ValueError, match="1 pairs the list does not hold"):
        tool.keep_nicknames([("richard", "ricky")],
                            tool.read_exclusions(_REFUSED))


def test_a_listed_pair_whose_names_normalize_alike_is_refused() -> None:
    with pytest.raises(ValueError, match="normalize alike"):
        tool.keep_nicknames([("Ann", "ann")], {})


def test_the_lists_pairs_are_kept_less_the_refused_ones() -> None:
    kept = tool.keep_nicknames(tool.read_nicknames(_LIST),
                               tool.read_exclusions(_REFUSED))
    assert kept == {"ricky": {"richard"}, "rick": {"richard"}}


class _Response(io.BytesIO):
    def __enter__(self) -> _Response:
        return self

    def __exit__(self, *exc: object) -> None:
        self.close()


def test_fetch_caches_the_list_only_when_its_hash_is_the_pinned_one(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("NAMEPARSER_TOOLS_CACHE", str(tmp_path))
    data = _LIST.encode("utf-8")
    monkeypatch.setattr(tool.urllib.request, "urlopen",
                        lambda *a, **k: _Response(data))
    with pytest.raises(SystemExit, match="not the pinned"):
        tool.fetch_nicknames()
    assert not (tmp_path / tool.NICKNAMES_FILE).exists()
    monkeypatch.setattr(tool, "NICKNAMES_SHA256",
                        hashlib.sha256(data).hexdigest())
    assert tool.main(["--fetch"]) == 0
    assert tool.load_nicknames() == tool.read_nicknames(_LIST)


def test_a_missing_list_names_the_command_that_fetches_it(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("NAMEPARSER_TOOLS_CACHE", str(tmp_path))
    with pytest.raises(SystemExit, match="familiar.py --fetch"):
        tool.load_nicknames()


def test_a_refusal_is_of_the_pair_whichever_way_round() -> None:
    both_ways = [("caroline", "carol"), ("carol", "caroline"),
                 ("aaron", "erin"), ("erin", "aaron")]
    refused = {("aaron", "erin"): "different-name",
               ("erin", "aaron"): "different-name"}
    assert tool.keep_nicknames(both_ways, refused) == {
        "carol": {"caroline"}, "caroline": {"carol"}}
    # one row refused and the other kept is the review's to settle: the
    # match reads both as one pair, so the refusal would reach nothing
    with pytest.raises(ValueError, match="carol = caroline but not"):
        tool.keep_nicknames(both_ways, {("carol", "caroline"): "unclear"})


def test_a_kept_name_that_is_not_letters_alone_is_refused() -> None:
    rows = [("casey", "k.c."), ("kasey", "k.c.")]
    with pytest.raises(ValueError, match="k.c. = kasey: a name"):
        tool.keep_nicknames(rows, {("casey", "k.c."): "spelling"})
    assert tool.keep_nicknames(rows, {r: "spelling" for r in rows}) == {}


def test_a_list_reading_on_a_word_the_file_holds_goes_under_its_text() -> None:
    out = tool.rewrite(_FILE, {"jr": {"junior"}}, "en.toml")
    assert out is not None
    data = tomllib.loads(out)
    assert data["word"][0] == {
        "text": "jr", "generation": {},
        "familiar": {"short_for": ["junior"], "note": tool.NICKNAMES_SOURCE}}
    assert tool.BEGIN not in out
    assert tool.strip(out) == _FILE


def test_a_hand_note_opening_with_the_source_is_not_the_tools() -> None:
    hand = _FILE.replace(
        'given = { note = "x" }',
        'familiar = { short_for = ["edgar"], '
        f'note = "{tool.NICKNAMES_SOURCE}, and a census I read" }}')
    with pytest.raises(ValueError, match="does not own"):
        tool.rewrite(hand, {"ed": {"edward"}}, "en.toml")


def test_a_cached_list_of_another_hash_is_refused(
        planted: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(tool, "NICKNAMES_SHA256", "0" * 64)
    with pytest.raises(SystemExit, match="not the pinned"):
        tool.load_nicknames()


def test_no_refused_pair_is_shipped() -> None:
    # offline, from the committed files alone: every refusal is of a
    # pair the default lexicon does not pair, whichever way round
    from nameparser import Lexicon
    lexicon = Lexicon.default()
    shipped = [(full, nickname) for full, nickname in tool.load_exclusions()
               if tool.build._normalize(full)
               in lexicon._familiar_forms(tool.build._normalize(nickname))]
    assert shipped == []


# -- the reviewed pairs (decisions/name-matching, 2026-11-12 SPELLINGS ARE
# A KIND OF THEIR OWN) --------------------------------------------------------

def _reviewed(*rows: tuple[str, ...]) -> str:
    return "\n".join(["\t".join(tool.REVIEWED_HEADER),
                      *("\t".join(r) for r in rows)]) + "\n"


def _row(a: str, b: str, category: str, status: str = "",
         languages: str = "pl") -> tuple[str, ...]:
    return (a, b, category, status, category, category, "why", languages,
            "orcid", "3")


def test_the_reviewed_pairs_are_placed_by_category_and_language() -> None:
    rows = tool.read_reviewed(_reviewed(
        _row("george", "georgios", "translation", languages="el"),
        _row("george", "jorge", "split", languages="es"),
        _row("john", "jon", "spelling", "held", "en"),
        _row("kasia", "katarzyna", "familiar", languages="pl en"),
        _row("lukasz", "łukasz", "spelling"),
    ))
    placed = tool.place({"bill": {"william"}}, rows)
    src = tool.REVIEWED_SOURCE
    # a familiar pair on its shorter name, in each file its row names
    assert placed["pl"]["kasia"] == {"familiar": {src: {"katarzyna"}}}
    assert placed["en"]["kasia"] == {"familiar": {src: {"katarzyna"}}}
    # a spelling on the second name in order, listing the first
    assert placed["pl"]["łukasz"] == {"spelling": {src: {"lukasz"}}}
    # held, split and recorded pairs ship nowhere
    assert "jon" not in placed["en"] and "john" not in placed["en"]
    assert "es" not in placed and "el" not in placed
    # the nicknames list's own pair beside them
    assert placed["en"]["bill"] == {"familiar": {tool.NICKNAMES_SOURCE: {"william"}}}


def test_a_word_both_sources_pair_takes_one_reading_naming_both() -> None:
    words = {"ed": {"familiar": {tool.NICKNAMES_SOURCE: {"edward"},
                                 tool.REVIEWED_SOURCE: {"edwin"}}},
             "zzs": {"spelling": {tool.REVIEWED_SOURCE: {"zzr"}}}}
    out = tool.rewrite(_FILE, words, "en.toml")
    assert out is not None
    by_text = {e["text"]: e for e in tomllib.loads(out)["word"]}
    assert by_text["ed"]["familiar"] == {
        "short_for": ["edward", "edwin"],
        "note": f"{tool.NICKNAMES_SOURCE}; {tool.REVIEWED_SOURCE}"}
    assert by_text["zzs"]["spelling"] == {
        "spelling_of": ["zzr"], "note": tool.REVIEWED_SOURCE}
    # the tool owns both notes: regenerating is idempotent, and
    # stripping gives the file back
    assert tool.rewrite(out, words, "en.toml") == out
    assert tool.strip(out) == _FILE
    tool.build.compile_files({"en.toml": out})


def test_a_spelling_written_by_hand_is_refused() -> None:
    hand = _FILE.replace('given = { note = "x" }',
                         'spelling = { spelling_of = ["edd"], note = "mine" }')
    with pytest.raises(ValueError, match="holds a spelling reading"):
        tool.rewrite(hand, {"ed": {"spelling": {tool.REVIEWED_SOURCE: {"edd"}}}},
                     "en.toml")


@pytest.mark.parametrize(("rows", "match"), [
    ((("a",),), "fields"),
    ((_row("kasia", "katarzyna", "nickname"),), "'nickname' is not one of"),
    ((_row("kasia", "katarzyna", "familiar", "held"),), "only a spelling is held"),
    ((_row("katarzyna", "kasia", "familiar"),), "in order"),
    ((_row("Kasia", "katarzyna", "familiar"),), "normalized"),
    ((_row("kasia", "katarzyna", "familiar"),
      _row("kasia", "katarzyna", "familiar")), "listed twice or out of order"),
    ((_row("lukasz", "łukasz", "spelling"),
      _row("kasia", "katarzyna", "familiar")), "listed twice or out of order"),
    ((_row("kasia", "katarzyna", "familiar", languages=""),), "needs a file"),
])
def test_a_malformed_review_is_refused(rows: tuple[tuple[str, ...], ...],
                                       match: str) -> None:
    with pytest.raises(ValueError, match=match):
        tool.read_reviewed(_reviewed(*rows))


#: The reviewed pairs the review did not ship that the given names'
#: listed spellings link all the same: written short by a `given`
#: reading's `same_as` before this review (`moh`, `mohd`), or
#: reached through a third spelling both words were agreed to be, as
#: listed spellings chain (`yuri`, `natalia`, `viktoria`).
_LINKED_WITHOUT_SHIPPING = {
    ("moh", "mohammad"), ("mohammad", "mohd"),
    ("mohammed", "mohd"), ("nataliia", "natalya"), ("victoria", "viktoriia"),
    ("yurii", "yury")}


def test_the_committed_review_ships_what_both_readers_agreed_and_no_more() -> None:
    # offline: every agreed familiar pair is a familiar form, every
    # agreed spelling not held a listed spelling, and no other pair is
    # linked but those _LINKED_WITHOUT_SHIPPING names
    from nameparser import Lexicon
    rows = tool.load_reviewed()
    assert len(rows) >= 1600
    lexicon = Lexicon.default()
    linked = set()
    for r in rows:
        a, b = r["a"], r["b"]
        familiar = b in lexicon._familiar_forms(a)
        spelling = bool(lexicon._headwords(a, "given")
                        & lexicon._headwords(b, "given"))
        if r["category"] == "familiar":
            assert familiar, (a, b)
        elif r["category"] == "spelling" and not r["status"]:
            assert spelling, (a, b)
        elif spelling:
            linked.add((a, b))
    assert linked == _LINKED_WITHOUT_SHIPPING
    # the held pairs stay apart
    held = [(r["a"], r["b"]) for r in rows if r["status"] == "held"]
    assert held and not linked & set(held)
