"""The Spanish given-name list rules/O6's veto reads (#959), and offline
checks on tools/es_given_names.py, which writes it.

The list is generated, not judged word by word, so what a test can hold
is what no cutoff may change: no word the default vocabulary lists as a
particle or a title (ambiguous ones too), a suffix or a conjunction -- stricter than the TOML build's check 11, which a
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

from tests.checkout import HAS_CHECKOUT, needs_docs

import nameparser
from nameparser import Lexicon
from nameparser._pipeline._vocab import given_name_key
from nameparser.locales import _es_ar_given_names, _es_given_names

_PATH = Path(__file__).parents[2] / "tools" / "es_given_names.py"


def _load() -> ModuleType:
    spec = importlib.util.spec_from_file_location("es_given_names", _PATH)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


tool = _load()
#: Every list the tool writes, by the tag LISTS keys it with: the
#: checks below hold each of them.
_MODULES = {"es": _es_given_names, "es-AR": _es_ar_given_names}


@pytest.fixture(autouse=True)
def _no_network(monkeypatch: pytest.MonkeyPatch) -> None:
    def refuse(*args: object, **kwargs: object) -> None:
        raise AssertionError("a test reached the network")
    monkeypatch.setattr(urllib.request, "urlopen", refuse)


def _non_name_readings(lexicon: Lexicon) -> dict[str, frozenset[str]]:
    """The default vocabulary's readings of a word as something other
    than a name, each folded as the list is: a particle (ambiguous ones
    too, `del` and `da` among them, which the tool also leaves out), a
    title (an ambiguous one too), a suffix and a conjunction."""
    fields = {
        "particle": lexicon._sets.particles,
        "title": lexicon._sets.titles | lexicon._sets.titles_ambiguous,
        "suffix": lexicon._sets.suffix_acronyms | lexicon._sets.suffix_words,
        "conjunction": lexicon._sets.conjunctions,
    }
    return {kind: frozenset(given_name_key(w) for w in words)
            for kind, words in fields.items()}


def _overlap(names: frozenset[str], lexicon: Lexicon) -> dict[str, set[str]]:
    names = names - tool.FOLD_KEPT
    return {kind: set(names & words)
            for kind, words in _non_name_readings(lexicon).items()
            if names & words}


#: The check with a word of each kind added: what the test below would
#: report were the tool's exclusion to let one through -- its negative
#: control, recorded so the empty answer cannot be a check reading
#: nothing.
_UNGUARDED_EFFECT = {
    "particle": {"los", "del"},
    "title": {"dr", "dean"},
    "suffix": {"jr"},
    "conjunction": {"y"},
}


def test_the_tool_writes_one_module_a_list() -> None:
    assert set(tool.LISTS) == set(_MODULES)
    # In a checkout the tool writes the very file imported. Against the
    # installed package (tests/checkout.py) the two are different copies,
    # so the file is matched by its place in the package instead.
    package = _PATH.parents[1] / "nameparser"
    installed = Path(nameparser.__file__).parent
    for tag, module in _MODULES.items():
        assert module.__file__ is not None
        if HAS_CHECKOUT:
            assert tool.LISTS[tag][0] == Path(module.__file__), tag
        else:
            assert (tool.LISTS[tag][0].relative_to(package)
                    == Path(module.__file__).relative_to(installed)), tag


@pytest.mark.parametrize("tag", sorted(_MODULES))
def test_a_list_holds_no_word_the_default_reads_as_no_name(tag: str) -> None:
    assert _overlap(_MODULES[tag].GIVEN_NAMES, Lexicon.default()) == {}


def test_the_list_holds_no_word_the_default_reads_as_no_name() -> None:
    # A listed word O6 declines to take is one it would otherwise take
    # into the family; one the default reads as a particle, a title, a
    # suffix or a connective is not a given name the veto could mean,
    # and listing it would contradict the reading that claims it.
    default = Lexicon.default()
    assert _overlap(_es_given_names.GIVEN_NAMES, default) == {}
    # each kept word is a listed given name a vocabulary word folds to,
    # so the exception cannot outlive its clash
    folded = set().union(*_non_name_readings(default).values())
    assert tool.FOLD_KEPT and tool.FOLD_KEPT <= _es_given_names.GIVEN_NAMES & folded
    planted = _es_given_names.GIVEN_NAMES | {"los", "del", "dr", "dean",
                                             "jr", "y"}
    assert _overlap(planted, default) == _UNGUARDED_EFFECT


@pytest.mark.parametrize("tag", sorted(_MODULES))
def test_every_entry_is_written_in_the_fold_it_is_matched_by(tag: str) -> None:
    # The parse folds the word it asks about (given_name_key) and looks
    # the fold up, so an entry written any other way is never matched.
    module = _MODULES[tag]
    entries = module._RANKED + module._N_SPELLINGS
    assert module._RANKED and len(set(entries)) == len(entries)
    assert [w for w in entries if given_name_key(w) != w or not w.isalpha()] == []
    assert module.GIVEN_NAMES == frozenset(entries)


@pytest.mark.parametrize("tag", sorted(_MODULES))
def test_an_n_spelling_is_a_listed_word_with_its_tilde_dropped(tag: str) -> None:
    # #1081: the fold runs one way, from a listed word written with ñ to
    # the n an ASCII writer puts in its place, so every extra entry is
    # one of those and none holds ñ itself
    module = _MODULES[tag]
    tilded = {w.replace("ñ", "n") for w in module._RANKED if "ñ" in w}
    assert module._N_SPELLINGS
    assert set(module._N_SPELLINGS) <= tilded
    assert not any("ñ" in w for w in module._N_SPELLINGS)


@pytest.mark.parametrize("tag", sorted(_MODULES))
def test_the_module_block_is_what_the_tool_renders(tag: str) -> None:
    # The block is the tool's output, so a hand edit, or a list the tool
    # would render differently, fails here.
    # the module imported, not the tool's path into a checkout: Debian's
    # autopkgtest runs these against the installed package
    module = _MODULES[tag]
    assert module.__file__ is not None
    path = Path(module.__file__)
    text = path.read_text(encoding="utf-8")
    block = tool.render(list(_MODULES[tag]._RANKED),
                        list(_MODULES[tag]._N_SPELLINGS))
    assert tool.rewrite(text, block, path) == text


@pytest.mark.parametrize("tag", sorted(_MODULES))
def test_each_list_holds_its_cutoff(tag: str) -> None:
    assert len(_MODULES[tag]._RANKED) == tool.LISTS[tag][1]


def test_the_argentine_list_holds_the_spanish_one() -> None:
    # decisions/O6, 2026-11-04: a looser share and a longer cutoff over
    # the same tables, so ES and ES_AR stacked read as ES_AR
    assert _es_given_names.GIVEN_NAMES < _es_ar_given_names.GIVEN_NAMES


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


def test_an_n_spelling_is_kept_where_its_merged_uses_pass_the_share() -> None:
    # #1081: Begona stands for Begoña and for a Begona, so both count;
    # Martino stands for Martiño, a given name, and for Martino, mostly
    # a surname, so it fails though martiño passes; a listed n word
    # (marina) and an excluded one are not written twice
    given = Counter({"begoña": 750, "martiño": 74, "martino": 15,
                     "mariña": 9, "marina": 1000, "doña": 50})
    surname = Counter({"begoña": 5, "martiño": 31, "martino": 304,
                       "mariña": 3})
    ranked = ["marina", "begoña", "martiño", "mariña", "doña"]
    assert tool.n_spellings(ranked, given, surname, {"dona"}, share=0.5) == [
        "begona"]
    # martiño alone is 70% given: the merged spelling is 21%
    assert tool.select(given, surname, set(), share=0.5).count("martiño") == 1
    assert tool.n_spellings(["martiño"], given, Counter(), set(),
                            share=0.5) == ["martino"]
    # the given side is summed too: zuriñe's 40 uses alone are 44% of
    # the 90 its n spelling counts with the surname, the summed 100
    # are 67%
    given2 = Counter({"zuriñe": 40, "zurine": 60})
    surname2 = Counter({"zurine": 50})
    assert tool.n_spellings(["zuriñe"], given2, surname2, set(),
                            share=0.5) == ["zurine"]
    assert tool.n_spelling_uses(["zuriñe"], given2, surname2, set()) == [
        ("zurine", 100, 50)]


@needs_docs
def test_the_list_holds_the_tools_cutoff_and_the_docs_say_so() -> None:
    # The user docs state the list's size; the cutoff is the tool's TOP,
    # so a cutoff change fails here until the prose moves with it. The
    # release log is a record of what shipped, so it is not held.
    assert len(_es_given_names._RANKED) == tool.TOP
    docs = _PATH.parents[1] / "docs"
    for name in ("locales.rst", "customize.rst"):
        text = " ".join(docs.joinpath(name).read_text(encoding="utf-8").split())
        assert f"{tool.TOP:,} Spanish given names" in text, name


#: (pack, name, field, value): #1081's one-way fold through the packs.
#: The first rows are the fix: a listed word written without its ñ.
#: The rest held before it and must still hold: a word written with ñ
#: never matches an n entry (Oña against `ona`, Mariño against
#: `marino`), and Martino, the n spelling the share test refuses, is
#: taken into the family as before.
_N_SPELLING_ROWS = [
    ("ES", "Maria Begona Lopez", "middle", "Begona"),
    ("ES", "MARIA BEGONA LOPEZ", "middle", "BEGONA"),
    ("ES_AR", "Jon Inigo Perez", "middle", "Inigo"),
    ("ES", "María Begoña López", "middle", "Begoña"),
    ("ES", "Juan Oña Pérez", "family", "Oña Pérez"),
    ("ES_AR", "Ana Mariño López", "family", "Mariño López"),
    ("ES_AR", "Luis Martino Gil", "family", "Martino Gil"),
    ("ES", "Jon Inigo Perez", "family", "Inigo Perez"),
]


@pytest.mark.parametrize(("pack", "name", "field", "value"), _N_SPELLING_ROWS)
def test_the_n_spellings_through_the_packs(pack: str, name: str,
                                           field: str, value: str) -> None:
    from nameparser import locales, parser_for
    parsed = parser_for(getattr(locales, pack)).parse(name)
    assert getattr(parsed, field) == value
