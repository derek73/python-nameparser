"""The Portuguese given-name list rules/O6's veto reads under
locales.PT_BR and locales.PT_PT (#1453), and offline checks on
tools/pt_given_names.py, which writes it.

As for the Spanish lists (tests/v2/test_es_given_names.py), what a test
can hold is what no cutoff may change: no word the default vocabulary
reads as no name, every entry in the fold the parse matches by, the
module's block as the tool renders it, and the tool's tally and
selection on hand-built records. The tool's source is the
`orcid-researchers` local corpus, which no test reads.
"""
from __future__ import annotations

import importlib.util
import sys
from collections import Counter
from pathlib import Path
from types import ModuleType

import pytest

from tests.checkout import HAS_CHECKOUT

import nameparser
from nameparser import Lexicon, locales, parser_for
from nameparser._pipeline._vocab import given_name_key
from nameparser.locales import _pt_given_names

_PATH = Path(__file__).parents[2] / "tools" / "pt_given_names.py"


def _load() -> ModuleType:
    spec = importlib.util.spec_from_file_location("pt_given_names", _PATH)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


tool = _load()


def _record(country: str, given: str, family: str) -> dict[str, str]:
    return {"country": country, "given": given, "family": family,
            "name": f"{given} {family}"}


def test_the_tool_writes_the_module_the_packs_import() -> None:
    assert _pt_given_names.__file__ is not None
    if HAS_CHECKOUT:
        assert tool.MODULE == Path(_pt_given_names.__file__)
    else:
        package = _PATH.parents[1] / "nameparser"
        installed = Path(nameparser.__file__).parent
        assert (tool.MODULE.relative_to(package)
                == Path(_pt_given_names.__file__).relative_to(installed))
    for pack in (locales.PT_BR, locales.PT_PT):
        assert pack.lexicon.given_names == _pt_given_names.GIVEN_NAMES
    # locales.PT, chosen by language, carries neither the list nor O6
    assert not locales.PT.lexicon.given_names


def test_the_list_holds_no_word_the_default_reads_as_no_name() -> None:
    # A word the default reads as a particle, a title, a suffix or a
    # connective is no given name the veto could mean (the Spanish
    # tool's exclusion, which this tool shares)
    sets = Lexicon.default()._sets
    pool = (sets.particles | sets.conjunctions | sets.titles | sets.titles_ambiguous
            | sets.suffix_acronyms | sets.suffix_words)
    folded = {given_name_key(w) for entry in pool for w in entry.split()}
    assert not _pt_given_names.GIVEN_NAMES & folded
    # its negative control: the folded pool does hold the words a
    # Portuguese name writes beside its given names
    assert {"da", "dos", "e", "dr", "jr"} <= folded


def test_every_entry_is_written_in_the_fold_it_is_matched_by() -> None:
    entries = _pt_given_names._RANKED + _pt_given_names._C_SPELLINGS
    assert _pt_given_names._RANKED and len(set(entries)) == len(entries)
    assert [w for w in entries if given_name_key(w) != w or not w.isalpha()] == []
    assert _pt_given_names.GIVEN_NAMES == frozenset(entries)
    assert not any(len(w) == 1 for w in entries)


def test_a_c_spelling_is_a_listed_word_with_its_cedilla_dropped() -> None:
    cedilla = {w.replace("ç", "c") for w in _pt_given_names._RANKED if "ç" in w}
    assert _pt_given_names._C_SPELLINGS
    assert set(_pt_given_names._C_SPELLINGS) <= cedilla
    assert not any("ç" in w for w in _pt_given_names._C_SPELLINGS)


def test_the_module_block_is_what_the_tool_renders() -> None:
    # the module imported, not the tool's path into a checkout, so the
    # check runs against an installed package too
    assert _pt_given_names.__file__ is not None
    text = Path(_pt_given_names.__file__).read_text(encoding="utf-8")
    block = tool.render(list(_pt_given_names._RANKED),
                        list(_pt_given_names._C_SPELLINGS))
    assert tool.rewrite(text, block) == text


def test_the_removed_words_are_out_of_the_list() -> None:
    assert not set(tool.REMOVED) & _pt_given_names.GIVEN_NAMES


def test_the_tally_skips_the_held_out_records_and_the_other_countries() -> None:
    records = [
        _record("PT", "Rui", "Held Out"),         # PT's first: held out
        _record("BR", "Ana", "Held Out"),         # BR's first: held out
        _record("PT", "Rui Miguel", "Sousa Pinto"),
        _record("BR", "Ana Beatriz", "da Paz Lima"),
        _record("AO", "Kiala", "Neto"),           # another country
        _record("BR", "Ana", ""),                 # an empty box
        _record("PT", "M.", "D'Ávila"),           # an initial; an elided word
    ]
    given, family = tool.tally(records, ("PT", "BR"), 1, {"da"})
    # the initial is counted, its full stop folded away, and select()
    # drops it; a word holding an apostrophe is no word a list carries
    assert given == Counter({"rui": 1, "miguel": 1, "ana": 1, "beatriz": 1, "m": 1})
    # `paz` stands behind the particle, a unit O6 takes whole, so it says
    # nothing about the bare word; `da` itself is counted
    assert family == Counter({"sousa": 1, "pinto": 1, "da": 1, "lima": 1})
    # with nothing held out the first records count too
    given_all, _ = tool.tally(records, ("PT",), 0, ())
    assert given_all["rui"] == 2


def test_the_selection_keeps_the_mostly_given_words_over_the_floor() -> None:
    given = Counter({"ana": 100, "augusto": 7, "mateus": 6, "rute": 4,
                     "da": 90, "j": 50, "zelia": 5})
    family = Counter({"augusto": 3, "mateus": 3, "rute": 0, "zelia": 0})
    # mateus is 6 of 9 uses given (67%), under 0.7; rute has 4 uses, under
    # the floor of 5; da is excluded; j writes an initial; zelia is removed
    assert tool.select(given, family, {"da"}, 5, 0.7, removed={"zelia"}) == [
        "ana", "augusto"]
    assert "mateus" in tool.select(given, family, set(), 5, 0.6)
    assert "rute" in tool.select(given, family, set(), 4, 0.7)


def test_a_c_spelling_is_kept_where_its_merged_uses_pass_the_share() -> None:
    # Goncalo stands for Gonçalo and for a Goncalo, so both count; an
    # excluded spelling is no candidate; França, listed, is refused
    # below, its c spelling standing mostly for a surname
    given = Counter({"gonçalo": 89, "goncalo": 3, "françoise": 6,
                     "constança": 11})
    family = Counter({"gonçalo": 3, "franca": 2, "françoise": 0})
    ranked = ["gonçalo", "constança", "françoise"]
    assert tool.c_spellings(ranked, given, family, set(), 0.7) == [
        "goncalo", "constanca", "francoise"]
    assert tool.c_spelling_uses(["gonçalo"], given, family, set()) == [
        ("goncalo", 92, 3)]
    assert tool.c_spellings(["gonçalo"], given, family, {"goncalo"}, 0.7) == []
    surnames = Counter({"frança": 1})
    assert tool.c_spellings(["frança"], surnames, Counter({"frança": 50}),
                            set(), 0.7) == []


@pytest.mark.parametrize(("pack", "name", "field", "value"), [
    # the c spelling an ASCII writer puts in place of the ç
    ("PT_PT", "Pedro Goncalo Matos", "middle", "Goncalo"),
    ("PT_PT", "Pedro Gonçalo Matos", "middle", "Gonçalo"),
    # the cedilla written as a combining mark (its c spelling is listed
    # too, so the accent rows below are what a wrong fold would fail)
    ("PT_BR", "Pedro Gonçalo Matos", "middle", "Gonçalo"),
    # an accent the fold drops, precomposed and as a combining mark
    ("PT_BR", "Pedro Luís Matos", "middle", "Luís"),
    ("PT_PT", "Ana Ine\u0302s Matos", "middle", "Ine\u0302s"),
    ("PT_PT", "Pedro Zzimão Matos", "family", "Zzimão Matos"),
    ("PT_BR", "PEDRO GONCALO MATOS", "middle", "GONCALO"),
    # a word the list lacks is taken (rules/O6's cost)
    ("PT_BR", "Pedro Zzarita Matos", "family", "Zzarita Matos"),
])
def test_the_list_through_the_packs(pack: str, name: str, field: str,
                                    value: str) -> None:
    parsed = parser_for(getattr(locales, pack)).parse(name)
    assert getattr(parsed, field) == value
