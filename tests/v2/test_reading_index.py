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

import ast
import importlib.util
import sys
import unicodedata
from pathlib import Path
from types import ModuleType
from typing import Any

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


def test_the_module_imports_nothing_internal_at_module_level() -> None:
    # tools/vocab/build.py loads this file by path at its own import; a
    # module-level import of the package would run nameparser/__init__,
    # and so _compiled.py, which a broken rebuild may have left unusable
    tree = ast.parse(Path(ri.__file__).read_text(encoding="utf-8"))
    top = [n for n in tree.body if isinstance(n, (ast.Import, ast.ImportFrom))]
    names = [a.name for n in top if isinstance(n, ast.Import) for a in n.names]
    names += [n.module or "" for n in top if isinstance(n, ast.ImportFrom)]
    assert names and not [m for m in names if m.startswith("nameparser")]


def test_the_index_compiled_with_no_choice_is_the_committed_module() -> None:
    # the no-choice invariant: what the parser reads is the index
    # compiled, byte for byte as the build writes it
    compiled = ri.compile_readings(ri.index())
    assert build.render(compiled) == build.OUTPUT.read_text(encoding="utf-8")
    for name, _ in build.CONSTANTS:
        assert compiled[name] == getattr(_compiled, name), name  # type: ignore[literal-required]


#: A value other than the unwritten one for every behavioral property,
#: so a probe reading carrying it compiles differently from one without.
_SET = {"addresses": "given", "after_given": True, "attaches": ["office"],
        "cased": "ZzQ", "acronym": None, "attached": {"side": "after"},
        "may_be_initial": True}


def _probe_readings() -> list[Any]:
    """A build Reading of every kind, carrying every behavioral
    property its category takes, set away from its unwritten value
    (`acronym` flipped), each word apart; plus a given name written
    short, and a name reading written default = false beside a
    credential, the two properties a name reading compiles from."""
    out = []
    for i, (kind, category) in enumerate(ri.CATEGORY.items()):
        text = "q" if kind == "conjunction" else f"zz{i}"
        props: dict[str, object] = {}
        for prop in ri.BEHAVIORAL[category] - {"default"}:
            value = _SET[prop]
            if prop == "acronym":
                value = kind != "credential"
            elif prop == "cased":
                value = text.upper()
            props[prop] = value
        out.append(build.Reading("en.toml", text, kind, props))
    out.append(build.Reading("en.toml", "chas", "given", {"same_as": "charles"}))
    out.append(build.Reading("en.toml", "zzoff", "credential", {}))
    out.append(build.Reading("de.toml", "zzoff", "family", {"default": False}))
    out.append(build.Reading("de.toml", "zzgen", "generation", {"default": False}))
    return out


def test_every_property_the_compiler_reads_survives_the_index() -> None:
    # an anchor outside the index's own path: compiling the build's
    # readings as their files wrote them, and compiling them as the
    # index keeps them (indexed, then written and read back as a row),
    # give the same sets. A property indexed() drops that the compiler
    # reads is lost only on the second side; the no-choice test above
    # cannot see one, both its sides going through the index
    probes = _probe_readings()
    for readings in (probes, build.load(build.read_dir()).readings):
        written = ri.compile_readings(readings)
        pool_of = build.Pool(readings=list(readings))
        kept = [ri.from_row(r.text, ri.to_row(r)) for r in build.index_rows(pool_of)]
        assert ri.compile_readings(kept) == written
    # the probes reach the compiler: every word carrying a property
    # lands in a compiled constant
    probed: dict[str, Any] = dict(ri.compile_readings(probes))
    for r in probes:
        if r.props and r.on_by_default:
            assert any(r.text in v for v in probed.values()), r


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
