"""Offline checks on tools/vocab/familiar.py, which writes the familiar
readings seeded from nam_dict (decisions/name-matching, 2026-11-08
FAMILIAR FORMS).

The source is a GFDL file cached outside the tree, so these read a
dictionary built here in its layout, and the tree's own files: the
failure that matters is a pair placed in the wrong language's file, or
a regeneration that rewrites what the tool does not own.
"""
from __future__ import annotations

import hashlib
import importlib.util
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


def _load() -> ModuleType:
    spec = importlib.util.spec_from_file_location("familiar", _PATH)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module  # @dataclass looks itself up here
    spec.loader.exec_module(module)
    return module


tool = _load()
_COUNTRIES = list(tool.COUNTRY_LANGUAGE)


def _legend(countries: list[str] = _COUNTRIES) -> list[str]:
    lines = []
    for i, country in enumerate(countries):
        column = 30 + i
        lines.append(f"#{country:>{column}} $")
        lines.append("#" + " " * (column - 1) + "|" + " " * (86 - column - 1) + "$")
    return lines


def _line(code: str, name: str, bands: dict[str, str], flag: str = " ") -> str:
    digits = "".join(bands.get(c, " ") for c in _COUNTRIES)
    return f"{code:<3}{name:<25} {flag}{digits} $"


def _dict(*lines: str) -> str:
    return "\n".join([*_legend(), *lines]) + "\n"


def test_the_equivalence_lines_read_with_their_bands() -> None:
    text = _dict(
        _line("M", "Max", {"Germany": "4"}),
        _line("=", "Max Maximilian", {"Austria": "1"}),
        _line("=", "Bill William", {"Great Britain": "2", "U.S.A.": "4"}),
        _line("=", "Käte Katharina", {"Germany": "1"}, flag="-"),
        # the umlaut-expanded duplicate the header says to ignore
        _line("=", "Käte Katharina", {"Germany": "1"}, flag="+"),
    )
    assert tool.read_pairs(text) == [
        tool.Pair("Max", "Maximilian", {"Austria": 1}),
        tool.Pair("Bill", "William", {"Great Britain": 2, "U.S.A.": 4}),
        tool.Pair("Käte", "Katharina", {"Germany": 1}),
    ]


def test_a_shifted_line_is_refused() -> None:
    with pytest.raises(ValueError, match="not fixed-width"):
        # the name a column late, its bands read one country off
        tool.read_pairs(_dict(_line("=", " Max Maximilian", {})[:-3] + " $"))


def test_a_pair_goes_in_the_file_of_each_language_attesting_it() -> None:
    placed = tool.place([
        tool.Pair("Max", "Maxim", {"Russia": 1, "Belarus": 2}),
        tool.Pair("Max", "Maximilian", {"Austria": 1, "Swiss": 3}),
        tool.Pair("Bill", "William", {"Great Britain": 2, "U.S.A.": 4}),
        tool.Pair("Zzq", "Zzr", {}),
        tool.Pair("Zzs", "Zzt", {"other countries": 1}),
    ])
    assert placed == {
        "ru": {"max": {"Maxim": {"Russia": 1}}},
        "be": {"max": {"Maxim": {"Belarus": 2}}},
        "de": {"max": {"Maximilian": {"Austria": 1, "Swiss": 3}}},
        "en": {"bill": {"William": {"Great Britain": 2, "U.S.A.": 4}}},
        "mul": {"zzq": {"Zzr": {}}, "zzs": {"Zzt": {"other countries": 1}}},
    }


def test_a_column_no_language_was_chosen_for_is_refused() -> None:
    with pytest.raises(ValueError, match="Belgium, whose column"):
        tool.place([tool.Pair("Jan", "Johannes", {"Belgium": 1})])


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
    words = {"ed": {"Edward": {"U.S.A.": 2}}, "bill": {"William": {}},
             "al": {"Albert": {"U.S.A.": 1}, "Alfred": {"U.S.A.": 1}}}
    out = tool.rewrite(_FILE, words, "en.toml")
    assert out is not None
    data = tomllib.loads(out)
    by_text = {e["text"]: e for e in data["word"]}
    assert by_text["ed"]["familiar"]["short_for"] == ["edward"]
    assert by_text["al"]["familiar"]["short_for"] == ["albert", "alfred"]
    assert by_text["al"]["familiar"]["note"].startswith(tool.SOURCE)
    assert "Alfred, U.S.A. 1" in by_text["al"]["familiar"]["note"]
    # the held word keeps its place; the new ones follow in text order
    assert [e["text"] for e in data["word"]] == ["jr", "ed", "al", "bill"]
    # regenerating is idempotent, and stripping gives the file back
    assert tool.rewrite(out, words, "en.toml") == out
    assert tool.strip(out) == _FILE
    assert tool.rewrite(out, {}, "en.toml") == _FILE


def test_a_file_only_the_tool_wrote_goes_when_it_holds_nothing() -> None:
    made = tool.rewrite(None, {"salvu": {"Saviour": {"Malta": 1}}}, "mt.toml")
    assert made is not None and tomllib.loads(made)["word"][0]["text"] == "salvu"
    assert tool.rewrite(made, {}, "mt.toml") is None


def test_a_familiar_reading_written_by_hand_is_refused() -> None:
    hand = _FILE.replace('given = { note = "x" }',
                         'familiar = { short_for = ["edgar"], note = "mine" }')
    with pytest.raises(ValueError, match="does not own"):
        tool.rewrite(hand, {"ed": {"Edward": {}}}, "en.toml")


def test_every_shipped_familiar_reading_credits_its_source() -> None:
    # the tool owns these, and the note carries nam_dict's licence and
    # author; a familiar reading written by hand says where it comes from
    vocab = Path(__file__).parents[2] / "nameparser" / "vocab"
    readings = [e["familiar"] for path in sorted(vocab.glob("*.toml"))
                for e in tomllib.loads(path.read_text())["word"]
                if "familiar" in e]
    assert len(readings) >= 600
    assert all(r["note"].startswith(tool.SOURCE) for r in readings)


def test_stripping_the_tree_leaves_no_familiar_reading() -> None:
    # without the source: every familiar reading in the tree is one the
    # tool owns, and taking them out leaves a file the build reads
    vocab = Path(__file__).parents[2] / "nameparser" / "vocab"
    for path in sorted(vocab.glob("*.toml")):
        text = path.read_text()
        stripped = tool.strip(text)
        assert "familiar = " not in stripped, path.name
        tomllib.loads(stripped)  # still a file


#: The cached file's path, worked out without creating the cache folder
#: as name_usage.cache_dir() does: collecting this module must write
#: nothing.
_CACHED = Path(os.environ.get(
    "NAMEPARSER_TOOLS_CACHE", Path.home() / ".cache" / "nameparser-tools")
) / tool.name_usage.NAMDICT_FILE


@pytest.mark.skipif(
    not _CACHED.exists(),
    reason="nam_dict.txt is not cached (tools/name_usage.py downloads it)")
def test_the_tree_is_what_the_tool_writes_from_the_cached_source() -> None:
    assert tool.stale(tool.place(tool.load_pairs())) == []


# -- the format's edge cases -------------------------------------------------

def test_an_accented_line_a_hex_band_and_its_expanded_duplicate_read() -> None:
    pairs = tool.read_pairs(_dict(
        _line("=", "Józsi József", {"Hungary": "D"}, flag="-"),
        _line("=", "Józsi József", {"Hungary": "D"}, flag="+"),
    ))
    assert pairs == [tool.Pair("Józsi", "József", {"Hungary": 13})]


def test_an_expanded_line_duplicating_no_kept_pair_is_refused() -> None:
    with pytest.raises(ValueError, match="no pair kept is Käte = Katharina"):
        tool.read_pairs(_dict(
            _line("=", "Max Maximilian", {"Austria": "1"}),
            _line("=", "Käte Katharina", {"Germany": "1"}, flag="+")))


def test_three_names_on_a_line_are_refused() -> None:
    with pytest.raises(ValueError, match="'=  short long'"):
        tool.read_pairs(_dict(_line("=", "Max Maxi Maximilian", {})))


def test_a_legend_differing_from_the_column_map_is_refused() -> None:
    renamed = ["Britain", *_COUNTRIES[1:]]
    with pytest.raises(ValueError, match="COUNTRY_LANGUAGE"):
        tool.read_pairs("\n".join([*_legend(renamed),
                                   _line("=", "Max Maximilian", {})]) + "\n")


def test_a_file_holding_no_pair_is_refused() -> None:
    with pytest.raises(ValueError, match="holds no equivalence line"):
        tool.read_pairs(_dict(_line("M", "Max", {"Germany": "4"})))


def test_a_pair_whose_names_normalize_alike_is_refused() -> None:
    with pytest.raises(ValueError, match="normalize alike"):
        tool.place([tool.Pair("Max", "MAX.", {"Germany": 1})])


@pytest.mark.parametrize("markers", [
    [tool.BEGIN], [tool.END], [tool.END, tool.BEGIN],
    [tool.BEGIN, tool.END, tool.BEGIN, tool.END],
])
def test_a_generated_block_with_broken_markers_is_refused(
        markers: list[str]) -> None:
    text = _FILE + "\n".join(markers) + "\n"
    with pytest.raises(ValueError, match="en.toml: the generated block"):
        tool.rewrite(text, {"ed": {"Edward": {}}}, "en.toml")


# -- the command, on a planted cache and vocabulary ----------------------------

_PLANTED = _dict(
    _line("=", "Bill William", {"Great Britain": "2", "U.S.A.": "4"}),
    _line("=", "Sepp Josef", {"Germany": "1"}),
)


@pytest.fixture
def planted(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """A cache holding a planted nam_dict, pinned by its own hash, and a
    vocabulary folder holding one file: never the real cache or tree."""
    cache = tmp_path / "cache"
    cache.mkdir()
    data = _PLANTED.encode("utf-8")
    (cache / tool.name_usage.NAMDICT_FILE).write_bytes(data)
    monkeypatch.setenv("NAMEPARSER_TOOLS_CACHE", str(cache))
    monkeypatch.setattr(tool.name_usage, "NAMDICT_FILE_SHA256",
                        hashlib.sha256(data).hexdigest())
    vocab = tmp_path / "vocab"
    vocab.mkdir()
    (vocab / "en.toml").write_text(_FILE, encoding="utf-8")
    monkeypatch.setattr(tool, "VOCAB", vocab)
    return vocab


def test_check_reports_stale_until_write_brings_the_files_current(
        planted: Path) -> None:
    assert tool.main(["--check"]) == 1
    assert tool.stale(tool.place(tool.load_pairs()), planted) == [
        planted / "de.toml", planted / "en.toml"]
    assert tool.main(["--write"]) == 0
    assert tool.main(["--check"]) == 0
    written = {p.name: p.read_text(encoding="utf-8")
               for p in sorted(planted.glob("*.toml"))}
    assert set(written) == {"de.toml", "en.toml"}
    # the written files pass the build's checks
    tool.build.compile_files(written)
    by_text = {e["text"]: e for e in tomllib.loads(written["en.toml"])["word"]}
    assert by_text["bill"]["familiar"]["short_for"] == ["william"]


def test_a_cache_file_of_another_hash_is_refused(
        planted: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(tool.name_usage, "NAMDICT_FILE_SHA256", "0" * 64)
    with pytest.raises(SystemExit, match="not the pinned"):
        tool.load_pairs()


def test_a_missing_cache_file_names_the_command_that_fetches_it(
        planted: Path, monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    empty = tmp_path / "empty"
    empty.mkdir()
    monkeypatch.setenv("NAMEPARSER_TOOLS_CACHE", str(empty))
    with pytest.raises(SystemExit, match="tools/name_usage.py"):
        tool.load_pairs()
