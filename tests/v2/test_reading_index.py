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

import pytest
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
    fresh = build.render_index(build.index_rows(pool), build.file_tags(pool))
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


# -- a choice of languages (phase 3b) --


def _r(text: str, tag: str, kind: str, **props: object) -> ri.IndexReading:
    return ri.IndexReading(text, tag, kind, props)


def _kept(readings: list[ri.IndexReading], chosen: set[str]
          ) -> set[tuple[str, str, str, tuple[tuple[str, Any], ...]]]:
    return {(r.text, r.tag, r.kind, tuple(sorted(r.props.items())))
            for r in ri.choose(readings, frozenset(chosen))}


def test_a_tag_selects_its_own_file_and_its_ancestors_never_its_descendants() -> None:
    assert ri.selected(["pt-BR"]) == {"pt-BR", "pt"}
    assert ri.selected(["pt"]) == {"pt"}
    # BCP 47 tags are matched without regard to case, so the lowercase
    # spelling cannot silently select only the parent
    assert ri.selected(["pt-br"]) == {"pt-BR", "pt"}
    # a region no file holds selects what its language's file holds
    assert ri.selected(["pt-PT"]) == {"pt"}
    # no macrolanguage table: Malay does not select Indonesian
    assert ri.selected(["ms"]) == {"ms"}
    assert ri.selected([]) == frozenset()


@pytest.mark.parametrize("tag,match", [
    ("mul", "not a language to choose"),
    ("UND", "not a language to choose"),
    ("xx", "no vocabulary file holds the language 'xx'.*: ak, am"),
    ("xx-PT", "no vocabulary file holds"),
])
def test_a_tag_no_file_holds_is_refused_naming_those_that_are(
        tag: str, match: str) -> None:
    with pytest.raises(ValueError, match=match):
        ri.selected([tag])


def test_an_empty_choice_compiles_the_default() -> None:
    compiled = ri.compile_choice(frozenset())
    for name, _ in build.CONSTANTS:
        assert compiled[name] == getattr(_compiled, name), name  # type: ignore[literal-required]
    assert ri.changed_words(frozenset()) == frozenset()


def test_a_chosen_language_turns_its_readings_off_by_default_on() -> None:
    pool = [_r("h", "es", "generation", default=False),
            _r("h", "en", "given", default=False)]
    assert _kept(pool, set()) == set()
    # the chosen file's own reading only, its `default` gone; another
    # file's reading left off by default stays off
    assert _kept(pool, {"es"}) == {("h", "es", "generation", ())}


def test_prefer_drops_other_languages_vocabulary_readings_of_the_word() -> None:
    pool = [_r("do", "pt", "preposition"), _r("do", "en", "credential"),
            _r("do", "en", "given"), _r("do", "mul", "generation"),
            _r("de", "en", "credential")]
    kept = _kept(pool, {"pt"})
    # the name reading stays (decision 15: it keeps the gate on), and
    # mul's, every language's; a word pt holds nothing of is untouched
    assert kept == {("do", "pt", "preposition", ()), ("do", "en", "given", ()),
                    ("do", "mul", "generation", ()),
                    ("de", "en", "credential", ())}
    # two chosen languages that each hold one both keep it
    assert len(_kept(pool, {"pt", "en"})) == len(pool)


def test_a_name_reading_never_settles_a_clash() -> None:
    # vi holds only a name reading of `do`: choosing it settles nothing,
    # so the credential stays, gated as in the default (the RFC's `do`)
    pool = [_r("do", "vi", "family"), _r("do", "en", "credential")]
    assert _kept(pool, {"vi"}) == _kept(pool, set())


def test_a_chosen_conjunction_drops_its_shape_clash_with_the_initial() -> None:
    pool = [_r("e", "pt", "conjunction", may_be_initial=True),
            _r("y", "es", "conjunction", may_be_initial=True)]
    assert _kept(pool, {"pt"}) == {
        ("e", "pt", "conjunction", ()),
        ("y", "es", "conjunction", (("may_be_initial", True),))}
    compiled = ri.compile_readings(ri.choose(pool, frozenset({"pt"})))
    assert compiled["CONJUNCTIONS"] == {"e", "y"}
    assert compiled["CONJUNCTIONS_AMBIGUOUS"] == {"y"}


def test_the_deviation_surface_is_the_words_whose_compile_changes() -> None:
    pt = frozenset({"pt"})
    default, choice = ri.compile_choice(frozenset()), ri.compile_choice(pt)
    moved = {w for k in default
             if not isinstance(default[k], dict)  # type: ignore[literal-required]
             for w in default[k] ^ choice[k]}  # type: ignore[literal-required]
    assert moved and moved <= ri.changed_words(pt)
    assert "e" in ri.changed_words(pt) and "do" in ri.changed_words(pt)


def test_a_choice_moves_only_words_its_own_files_hold() -> None:
    # every file tag, chosen alone: what a choice changes is a word one
    # of its selected files holds a reading of (a phrase's word counted
    # through the phrase), never a word only other files hold
    for tag in sorted(ri.tags() - ri.UNCHOOSABLE):
        chosen = ri.selected([tag])
        held = {r.text for r in ri.index() if r.tag in chosen}
        held |= {w for t in held for w in t.split()}
        surface = ri.changed_words(chosen)
        assert surface <= held | {w for t in ri.compile_choice(chosen)[
            "TITLE_PHRASES"] for w in t.split()}, (tag, surface - held)


def test_prefer_never_drops_a_reading_of_unknown_language() -> None:
    # und.toml holds words whose language is not known, so no choice can
    # say they are another language's
    pool = [_r("bon", "fr", "particle"), _r("bon", "und", "particle"),
            _r("bon", "mul", "generation")]
    assert len(_kept(pool, {"fr"})) == 3


@pytest.mark.parametrize("text,kind,held", [
    ("bin", "patronymic", True),
    ("بن", "patronymic", True),
    # `ben` is excluded as a patronymic (ar.toml) and `van` is another
    # kind of particle; a word no file holds holds nothing
    ("ben", "patronymic", False),
    ("van", "patronymic", False),
    ("zzq", "patronymic", False),
    # a reading written `default = false` is held all the same
    ("st", "generation", True),
])
def test_holds_kind_reads_every_file_whatever_the_default(
        text: str, kind: str, held: bool) -> None:
    assert ri.holds_kind(text, kind) is held


# -- strict (#753, 3j) ------------------------------------------------

@pytest.mark.parametrize("text,native", [
    ("씨", True), ("господин", True), ("श्री", True), ("殿", True),
    ("dr", False), ("ông", False), ("&", False), ("2", False),
])
def test_native_script_is_a_letter_and_no_latin_letter(
        text: str, native: bool) -> None:
    assert ri.is_native_script(text) is native


def test_a_strict_pool_holds_the_chosen_files_and_native_script_only() -> None:
    chosen = ri.selected(["pt-BR"], strict=True)
    pool = ri.strict_pool(chosen)
    assert {r.tag for r in pool if not ri.is_native_script(r.text)} == chosen
    # mul.toml and und.toml are another language's file under strict
    assert not [r for r in pool if r.tag in ri.UNCHOOSABLE
                and not ri.is_native_script(r.text)]
    native = [r for r in ri.index() if ri.is_native_script(r.text)]
    assert native and all(r in pool for r in native)


def test_a_file_holding_no_reading_is_chosen_only_strictly() -> None:
    empty = ri.files() - ri.tags()
    assert empty and ri.tags() <= ri.files()
    for tag in sorted(empty):
        with pytest.raises(ValueError, match=f"{tag}.toml holds no reading"):
            ri.selected([tag])
        assert ri.selected([tag], strict=True) == {tag}
        # nothing Latin is left to compile: the native-script pool alone
        assert ri.compile_choice(frozenset({tag}), True) == ri.compile_readings(
            ri.choose([r for r in ri.index() if ri.is_native_script(r.text)],
                      frozenset({tag})))


#: The words each strict choice of one tag ungates against the plain
#: choice of the same tag (decisions/vocabulary-model's 2026-10-30 #753,
#: file-strict entry: 16 words, 27 word-and-tag pairs over 13 tags). A
#: word leaves this table when a name reading is written in the chosen
#: file whose names carry it, and joins it when a chosen file's
#: vocabulary reading loses its gate: review each move.
STRICT_UNGATED = {
    "ar": {"cheikh", "sultan"},
    "cs": {"st"},
    "fr": {"la", "marquis", "marquise", "st"},
    "ga": {"mac"},
    "gd": {"mac", "nic"},
    "hr": {"st"},
    "it": {"del", "la", "san", "santa"},
    "ms": {"bin", "sultan"},
    "nl": {"den", "tho"},
    "pt": {"da", "do", "santa"},
    "pt-BR": {"da", "do", "santa"},
    "sk": {"st"},
    "sl": {"st"},
}


def test_the_words_strict_ungates_are_the_reviewed_set() -> None:
    got = {}
    for tag in sorted(ri.files() - ri.UNCHOOSABLE):
        words = ri.strict_ungated(ri.selected([tag], strict=True))
        if words:
            got[tag] = set(words)
    assert got == STRICT_UNGATED


def test_strict_ungated_compares_with_the_plain_choice_not_the_default() -> None:
    # cs turns on the generation `st`, gated by en's given reading; the
    # default's markers hold no generation `st` at all, so a comparison
    # with them would miss it
    cs = frozenset({"cs"})
    assert "st" not in ri.compile_choice(frozenset())["SUFFIX_WORDS"]
    assert "st" in ri.strict_ungated(cs)
