"""The reading index (nameparser/config/_index.py) and the compiler it
shares with the build (nameparser/_reading_index.py), phase 3a of #753.

The index is the vocabulary as readings, each with the file it sits in,
and _compiled.py is the index compiled with no choice of languages. The
second is the invariant the RFC asks for: a choice of languages (3b)
compiles a subset of these same rows with this same function, so the
default and every pack are one compile apart, never two
implementations.
"""
from __future__ import annotations

import importlib.util
import sys
import unicodedata
from pathlib import Path
from types import ModuleType

from nameparser import _reading_index as ri
from nameparser.config import _compiled, _index

_BUILD = Path(__file__).resolve().parents[2] / "tools" / "vocab" / "build.py"


def _load_build() -> ModuleType:
    spec = importlib.util.spec_from_file_location("vocab_build_for_index", _BUILD)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


build = _load_build()


def test_the_index_compiled_with_no_choice_is_the_committed_module() -> None:
    # the no-choice invariant: what the parser reads is the index
    # compiled, byte for byte as the build writes it
    compiled = ri.compile_readings(ri.index())
    assert build.render(compiled) == build.OUTPUT.read_text(encoding="utf-8")
    for name, _ in build.CONSTANTS:
        assert compiled[name] == getattr(_compiled, name), name  # type: ignore[literal-required]


def test_the_committed_index_is_what_the_toml_writes() -> None:
    pool = build.load(build.read_dir())
    fresh = build.render_index(build.index_rows(pool))
    assert build.index_output().read_text(encoding="utf-8") == fresh, (
        f"nameparser/config/_index.py is stale against nameparser/vocab/; "
        f"run: {build.REFRESH}")


def test_the_index_holds_every_reading_of_every_file() -> None:
    # one row per reading the files hold, on by default or not, so a
    # choice can turn on what the default leaves off
    pool = build.load(build.read_dir())
    assert sorted((r.text, r.tag, r.kind) for r in pool.readings) == sorted(
        (r.text, r.tag, r.kind) for r in ri.index())
    assert any(not r.on_by_default for r in ri.index()), (
        "no reading written default = false: the off half is untested")


def test_a_row_round_trips_and_keeps_only_what_the_compiler_reads() -> None:
    for text, rows in _index.READINGS:
        for row in rows:
            r = ri.from_row(text, row)
            assert ri.to_row(r) == row
            assert set(r.props) <= ri.indexed(r.kind), (text, row)


def test_the_index_is_sorted_and_normalized() -> None:
    texts = [text for text, _ in _index.READINGS]
    assert texts == sorted(set(texts))
    for text, rows in _index.READINGS:
        assert unicodedata.normalize("NFC", text) == text == text.lower()
        assert list(rows) == sorted(
            rows, key=lambda row: (row[0], list(ri.CATEGORY).index(row[1])))


def test_readings_of_gives_a_words_rows_in_every_file() -> None:
    for text, rows in _index.READINGS:
        got = ri.readings_of(text)
        assert [(r.text, r.tag, r.kind) for r in got] == [
            (text, tag, kind) for tag, kind, _ in rows]
    assert ri.readings_of("zzq-no-such-word") == ()


def test_the_accessors_give_the_unwritten_values() -> None:
    bare = ri.IndexReading("zzq", "en", "credential", {})
    assert bare.category == "suffix" and bare.acronym and bare.on_by_default
    assert bare.addresses == "family" and not bare.flag("after_given")
    off = ri.IndexReading("zzq", "en", "family", {"default": False})
    assert off.category == "name" and not off.on_by_default
    assert not ri.IndexReading("zzq", "en", "generation", {}).acronym
