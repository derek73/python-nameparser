"""Offline checks on tools/vocab/familiar.py, which writes the familiar
readings seeded from nam_dict (decisions/name-matching, 2026-11-08
FAMILIAR FORMS).

The source is a GFDL file cached outside the tree, so these read a
dictionary built here in its layout, and the tree's own files: the
failure that matters is a pair placed in the wrong language's file, or
a regeneration that rewrites what the tool does not own.
"""
from __future__ import annotations

import importlib.util
import sys
import tomllib
from pathlib import Path
from types import ModuleType

import pytest

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


def _legend() -> list[str]:
    lines = []
    for i, country in enumerate(_COUNTRIES):
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
        # the umlaut-expanded duplicate the header says to ignore
        _line("=", "Käte Katharina", {"Germany": "1"}, flag="+"),
    )
    assert tool.read_pairs(text) == [
        tool.Pair("Max", "Maximilian", {"Austria": 1}),
        tool.Pair("Bill", "William", {"Great Britain": 2, "U.S.A.": 4}),
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
text = "ed"
given = { note = "x" }

[[word]]
text = "jr"
generation = {}
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
    assert [e["text"] for e in data["word"]] == ["ed", "jr", "al", "bill"]
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


@pytest.mark.skipif(
    not (tool.name_usage.cache_dir() / tool.name_usage.NAMDICT_FILE).exists(),
    reason="nam_dict.txt is not cached (tools/name_usage.py downloads it)")
def test_the_tree_is_what_the_tool_writes_from_the_cached_source() -> None:
    assert tool.stale(tool.place(tool.load_pairs())) == []
