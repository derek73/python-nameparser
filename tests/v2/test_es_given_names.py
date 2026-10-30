"""The Spanish given-name list rules/O6's veto reads (#959), and offline
checks on tools/es_given_names.py, which writes it.

The list is generated, not judged word by word, so what a test can hold
is what no cutoff may change: no word the default vocabulary lists as a
never-given particle, a title (an ambiguous one too), a suffix or a
conjunction -- stricter than the TOML build's check 11, which a
generated list does not pass through and which lets a given reading
stand beside a title or particle reading, deriving a marker from the
pair -- every entry in the fold the parse matches by, and the tool's
selection on hand-built rows. The tool's sources are two INE downloads,
which no test touches.
"""
from __future__ import annotations

import importlib.util
import sys
import urllib.request
from collections import Counter
from pathlib import Path
from types import ModuleType

import pytest

from nameparser import Lexicon
from nameparser._pipeline._vocab import given_name_key
from nameparser.locales import _es_given_names

_PATH = Path(__file__).parents[2] / "tools" / "es_given_names.py"


def _load() -> ModuleType:
    spec = importlib.util.spec_from_file_location("es_given_names", _PATH)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


tool = _load()


@pytest.fixture(autouse=True)
def _no_network(monkeypatch: pytest.MonkeyPatch) -> None:
    def refuse(*args: object, **kwargs: object) -> None:
        raise AssertionError("a test reached the network")
    monkeypatch.setattr(urllib.request, "urlopen", refuse)


def _non_name_readings(lexicon: Lexicon) -> dict[str, frozenset[str]]:
    """The default vocabulary's readings of a word as something other
    than a name, each folded as the list is: a never-given particle, a
    title (an ambiguous one too), a suffix and a conjunction."""
    never_given = lexicon.particles - lexicon.particles_ambiguous
    fields = {
        "never-given particle": never_given,
        "title": lexicon.titles | lexicon.titles_ambiguous,
        "suffix": lexicon.suffix_acronyms | lexicon.suffix_words,
        "conjunction": lexicon.conjunctions,
    }
    return {kind: frozenset(given_name_key(w) for w in words)
            for kind, words in fields.items()}


def _overlap(names: frozenset[str], lexicon: Lexicon) -> dict[str, set[str]]:
    return {kind: set(names & words)
            for kind, words in _non_name_readings(lexicon).items()
            if names & words}


#: The check with a word of each kind added: what the test below would
#: report were the tool's exclusion to let one through -- its negative
#: control, recorded so the empty answer cannot be a check reading
#: nothing.
_UNGUARDED_EFFECT = {
    "never-given particle": {"los"},
    "title": {"dr", "dean"},
    "suffix": {"jr"},
    "conjunction": {"y"},
}


def test_the_list_holds_no_word_the_default_reads_as_no_name() -> None:
    # A listed word O6 declines to take is one it would otherwise take
    # into the family; one the default reads as a particle, a title, a
    # suffix or a connective is not a given name the veto could mean,
    # and listing it would contradict the reading that claims it.
    default = Lexicon.default()
    assert _overlap(_es_given_names.GIVEN_NAMES, default) == {}
    planted = _es_given_names.GIVEN_NAMES | {"los", "dr", "dean", "jr", "y"}
    assert _overlap(planted, default) == _UNGUARDED_EFFECT


def test_every_entry_is_written_in_the_fold_it_is_matched_by() -> None:
    # The parse folds the word it asks about (given_name_key) and looks
    # the fold up, so an entry written any other way is never matched.
    ranked = _es_given_names._RANKED
    assert ranked and len(set(ranked)) == len(ranked)
    assert [w for w in ranked if given_name_key(w) != w or not w.isalpha()] == []
    assert _es_given_names.GIVEN_NAMES == frozenset(ranked)


def test_the_module_block_is_what_the_tool_renders() -> None:
    # The block is the tool's output, so a hand edit, or a list the tool
    # would render differently, fails here.
    text = _PATH.parents[1].joinpath(
        "nameparser", "locales", "_es_given_names.py").read_text(
            encoding="utf-8")
    block = tool.render(list(_es_given_names._RANKED))
    assert tool.rewrite(text, block) == text


def test_the_tool_folds_as_the_parse_does() -> None:
    assert tool.fold("JOSÉ") == "jose"
    assert tool.fold("MUÑOZ") == "muñoz"
    assert tool.fold("LLORENÇ") == "llorenç"
    assert tool.fold("José") == "jose"  # NFD
    assert tool.fold("Güell") == "guell"


def test_a_name_is_counted_by_its_words() -> None:
    rows = [("JOSE LUIS", 10), ("MARIA DEL CARMEN", 5), ("D'ARTAGNAN", 7),
            ("JOSE", 3)]
    assert tool.tally(rows) == Counter(
        {"jose": 13, "luis": 10, "maria": 5, "del": 5, "carmen": 5})


def test_a_surname_behind_a_particle_is_not_the_bare_word() -> None:
    # "de Miguel" is a particle unit O6 never takes as the word alone,
    # so it says nothing about a bare "Miguel" in the middle slot.
    rows = [("DE MIGUEL", 40), ("MIGUEL", 2), ("SAN MIGUEL", 9)]
    assert tool.tally(rows, after={"de"}) == Counter(
        {"miguel": 11, "de": 40, "san": 9})


def test_the_selection_keeps_the_mostly_given_words_by_rank() -> None:
    given = Counter({"jose": 100, "martin": 50, "luis": 80, "rosa": 30,
                     "del": 70, "j": 90})
    surname = Counter({"martin": 400, "luis": 8, "rosa": 3})
    # martin is mostly a surname, del is excluded, j writes an initial
    assert tool.select(given, surname, {"del"}, top=10) == [
        "jose", "luis", "rosa"]
    assert tool.select(given, surname, {"del"}, top=2) == ["jose", "luis"]
    # rosa is 30 of 33 uses given (91%): in at 0.9, out at 0.95
    assert "rosa" in tool.select(given, surname, set(), share=0.9)
    assert "rosa" not in tool.select(given, surname, set(), share=0.95)
