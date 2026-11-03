"""2.8.1's warnings for the 3.0 breaks 2.8.0 did not announce.

Three families, each a ``DeprecationWarning`` attributed to the caller's
line and naming the 3.0 replacement and the migration guide:

* the ``Lexicon`` set fields 3.0 makes internal (#754), written through
  ``Lexicon(...)``, ``add()``, ``remove()`` or ``dataclasses.replace``;
* the constants of the eight ``nameparser.config`` vocabulary modules
  3.0 deletes (#1007);
* ``nameparser.config.regexes`` (#1008).

The tables are written out literally rather than read from the modules,
for the reason tests/v2/test_config_aliases.py gives: imported, every
assertion would prove the bridge self-consistent rather than complete.
Reading an attribute (``lexicon.titles``) is deliberately not warned:
the pipeline reads those fields per token, so a property in their place
would cost a frame per read on the hot path (see the release log).
"""
from __future__ import annotations

import dataclasses
import importlib
import inspect
import pickle
import warnings
from collections.abc import Callable, Iterator
from contextlib import contextmanager

import pytest

import nameparser
from nameparser import Lexicon, Parser, locales, parse, parser_for

GUIDE = "https://nameparser.readthedocs.io/en/latest/migrate.html"


@contextmanager
def _caught() -> Iterator[list[warnings.WarningMessage]]:
    with warnings.catch_warnings(record=True) as record:
        warnings.simplefilter("always")
        yield record


def _deprecations(record: list[warnings.WarningMessage]
                  ) -> list[warnings.WarningMessage]:
    return [w for w in record if issubclass(w.category, DeprecationWarning)]


def _line_after() -> int:
    """The line after the caller's: where the call under test stands."""
    frame = inspect.currentframe()
    assert frame is not None and frame.f_back is not None
    return frame.f_back.f_lineno + 1


# -- the vocabulary and regex modules (#1007, #1008) --------------------------

#: (module, constant, a phrase its replacement clause must hold). Every
#: public name of the nine modules, the 1.x aliases (which
#: test_config_aliases.py asserts) aside.
REMOVED_CONSTANTS = [
    ("titles", "GIVEN_NAME_TITLES", 'words(kind="title", addresses="given")'),
    ("titles", "TITLES", 'words(kind="title")'),
    ("titles", "AFTER_GIVEN_TITLES",
     'words(kind="salutation", after_given=True)'),
    ("titles", "TITLES_AMBIGUOUS", 'words(kind="title")'),
    ("titles", "TITLE_MODIFIERS", 'words(kind="modifier")'),
    ("titles", "TITLE_STYLES", 'words(kind="style")'),
    ("titles", "TITLE_PHRASES", "attaches=[...]"),
    ("suffixes", "SUFFIX_WORDS", 'words(kind="suffix")'),
    ("suffixes", "GLUED_HONORIFICS", 'words(kind="suffix")'),
    ("suffixes", "SUFFIX_WORDS_AMBIGUOUS", 'words(kind="suffix")'),
    ("suffixes", "AGNOMENS", 'words(kind="agnomen")'),
    ("suffixes", "SUFFIX_ACRONYMS_AMBIGUOUS", 'words(kind="credential")'),
    ("suffixes", "SUFFIX_ACRONYMS", 'words(kind="credential")'),
    ("particles", "NON_GIVEN_NAME_PARTICLES", 'words(kind="particle")'),
    ("particles", "PARTICLES", 'words(kind="particle")'),
    ("conjunctions", "CONJUNCTIONS", 'words(kind="conjunction")'),
    ("conjunctions", "CONJUNCTIONS_AMBIGUOUS",
     'words(kind="conjunction", may_be_initial=True)'),
    ("bound_given_names", "BOUND_GIVEN_NAMES", 'words(kind="bound_given")'),
    ("given_names", "GIVEN_NAME_ABBREVIATIONS", 'words(kind="given")'),
    ("maiden_markers", "MAIDEN_MARKERS", 'words(kind="birth_marker")'),
    ("capitalization", "CAPITALIZATION_EXCEPTIONS",
     "Lexicon.default().capitalization_exceptions"),
    ("regexes", "re_emoji", "Policy(strip_emoji=...)"),
    ("regexes", "re_bidi", "Policy(strip_bidi=...)"),
    ("regexes", "EMPTY_REGEX", "copy a pattern you reuse"),
    ("regexes", "REGEXES", "copy a pattern you reuse"),
]
REMOVED_MODULES = sorted({m for m, _, _ in REMOVED_CONSTANTS})


def _id(row: tuple[str, str, str]) -> str:
    return f"{row[0]}.{row[1]}"


def _issue(module: str) -> str:
    return "#1008" if module == "regexes" else "#1007"


def _assert_removal(w: warnings.WarningMessage, module: str, name: str,
                    phrase: str, line: int) -> None:
    message = str(w.message)
    assert w.category is DeprecationWarning
    assert message.startswith(
        f"nameparser.config.{module}.{name} is deprecated and will be "
        f"removed in 3.0 ({_issue(module)})"), message
    assert phrase in message, message
    assert message.endswith(f"See {GUIDE}"), message
    assert (w.filename, w.lineno) == (__file__, line), (w.filename, w.lineno)


@pytest.mark.parametrize("row", REMOVED_CONSTANTS, ids=_id)
def test_reading_a_removed_constant_warns_at_the_reading_line(
        row: tuple[str, str, str]) -> None:
    module_name, name, phrase = row
    module = importlib.import_module(f"nameparser.config.{module_name}")
    with _caught() as record:
        line = _line_after()
        value = getattr(module, name)
    [w] = _deprecations(record)
    _assert_removal(w, module_name, name, phrase, line)
    # served unchanged: the library's own copy is the same object
    if module_name != "regexes":
        from nameparser.config import _compiled
        assert value is getattr(_compiled, name)


@pytest.mark.parametrize("row", REMOVED_CONSTANTS, ids=_id)
def test_importing_a_removed_constant_warns_at_the_import_line(
        row: tuple[str, str, str]) -> None:
    module_name, name, phrase = row
    namespace: dict[str, object] = {"__name__": __name__}
    source = f"from nameparser.config.{module_name} import {name}"
    with _caught() as record:
        exec(compile(source, __file__, "exec"), namespace)  # noqa: S102
    [w] = _deprecations(record)
    _assert_removal(w, module_name, name, phrase, 1)


@pytest.mark.parametrize("module_name", REMOVED_MODULES)
def test_the_table_covers_every_public_name(module_name: str) -> None:
    # __all__ lists every public name (test_config_aliases holds it to
    # star imports); less the 1.x aliases, each one must warn here
    module = importlib.import_module(f"nameparser.config.{module_name}")
    aliases = set(getattr(module.__getattr__, "deprecated_aliases", {}))
    listed = {n for m, n, _ in REMOVED_CONSTANTS if m == module_name}
    assert set(module.__all__) - aliases == listed


def test_the_module_imports_quietly_and_surnames_stays() -> None:
    with warnings.catch_warnings():
        warnings.simplefilter("error")
        for module_name in REMOVED_MODULES:
            importlib.import_module(f"nameparser.config.{module_name}")
        from nameparser.config.surnames import KOREAN_SURNAMES
        assert KOREAN_SURNAMES


def test_an_alias_to_a_removed_constant_warns_once_naming_both() -> None:
    from nameparser.config import prefixes
    with _caught() as record:
        prefixes.PREFIXES  # noqa: B018
    [w] = _deprecations(record)
    message = str(w.message)
    assert "nameparser.config.prefixes.PREFIXES is deprecated since 2.2" in message
    assert "nameparser.config.particles.PARTICLES is deprecated" in message
    assert w.filename == __file__


# -- Lexicon's set fields (#754) ----------------------------------------------

#: field -> (the 3.0 add() call for "zork", its remove() call). Every
#: compiled-set field 3.0 makes internal; surnames is asserted below.
SET_FIELDS = {
    "titles": (".add('zork', kind='title')", ".remove('zork', kind='title')"),
    "given_name_titles": (".add('zork', kind='title', addresses='given')",
                          ".remove('zork', kind='title')"),
    "suffix_acronyms": (".add('zork', kind='credential')",
                        ".remove('zork', kind='suffix')"),
    "suffix_words": (".add('zork', kind='suffix')",
                     ".remove('zork', kind='suffix')"),
    "suffix_acronyms_ambiguous": (".add('zork', kind='family')",
                                  ".remove('zork', kind='family')"),
    "particles": (".add('zork', kind='particle')",
                  ".remove('zork', kind='particle')"),
    "particles_ambiguous": (".add('zork', kind='given')",
                            ".remove('zork', kind='given')"),
    "conjunctions": (".add('zork', kind='conjunction')",
                     ".remove('zork', kind='conjunction')"),
    "conjunctions_ambiguous": (
        ".add('zork', kind='conjunction', may_be_initial=True)",
        ".remove('zork', kind='conjunction')"),
    "bound_given_names": (".add('zork', kind='bound_given')",
                          ".remove('zork', kind='bound_given')"),
    "given_name_abbreviations": (".add('zork', kind='given', same_as=",
                                 ".remove('zork', kind='given')"),
    "maiden_markers": (".add('zork', kind='birth_marker')",
                       ".remove('zork', kind='birth_marker')"),
    "honorific_tails": (".add('zork', kind='suffix', attached=",
                        ".remove('zork', kind='suffix')"),
    "after_given_titles": (".add('zork', kind='salutation', after_given=True)",
                           ".remove('zork', kind='salutation')"),
    "suffix_words_ambiguous": (".add('zork', kind='family')",
                               ".remove('zork', kind='family')"),
    "agnomens": (".add('zork', kind='agnomen')",
                 ".remove('zork', kind='agnomen')"),
    "titles_ambiguous": (".add('zork', kind='title').add('zork', kind='given')",
                         ".remove('zork', kind='title')"),
    "title_modifiers": (".add('zork', kind='modifier')",
                        ".remove('zork', kind='modifier')"),
    "title_styles": (".add('zork', kind='style')",
                     ".remove('zork', kind='style')"),
    "title_phrases": (".add('zork', kind='title', attaches=['zap'])",
                      ".remove('zork', kind='title')"),
}

#: the base a marker field needs beside it, or construction refuses it
#: as an orphan (_lexicon._SUBSET_FIELDS)
_BASES = {
    "particles_ambiguous": "particles",
    "suffix_acronyms_ambiguous": "suffix_acronyms",
    "honorific_tails": "suffix_words",
    "suffix_words_ambiguous": "suffix_words",
}


def _entries(field: str) -> dict[str, frozenset[str]]:
    word = frozenset({"zork zap" if field == "title_phrases" else "zork"})
    entries = {field: word}
    if field in _BASES:
        entries[_BASES[field]] = word
    return entries


def _assert_set_field(w: warnings.WarningMessage, spelling: str,
                      base: str, calls: str, line: int) -> None:
    message = str(w.message)
    assert w.category is DeprecationWarning
    assert message.startswith(
        "Lexicon's set fields are deprecated and become internal in 3.0"
    ), message
    assert f"refuses {spelling} with a set field (#754)" in message, message
    assert f"(#754); in 3.0 write {base}" in message, message
    assert calls in message, message
    assert message.endswith(f"See {GUIDE}"), message
    assert (w.filename, w.lineno) == (__file__, line), (w.filename, w.lineno)


@pytest.mark.parametrize("field", SET_FIELDS)
def test_constructing_with_a_set_field_warns(field: str) -> None:
    with _caught() as record:
        line = _line_after()
        Lexicon(**_entries(field))  # type: ignore[arg-type]
    [w] = _deprecations(record)
    _assert_set_field(w, "Lexicon()", "Lexicon.empty().",
                      SET_FIELDS[field][0], line)


@pytest.mark.parametrize("field", SET_FIELDS)
def test_add_with_a_set_field_warns(field: str) -> None:
    lexicon = Lexicon.empty()
    with _caught() as record:
        line = _line_after()
        lexicon.add(**_entries(field))
    [w] = _deprecations(record)
    _assert_set_field(w, "add()", "lexicon.", SET_FIELDS[field][0], line)


@pytest.mark.parametrize("field", SET_FIELDS)
def test_remove_with_a_set_field_warns(field: str) -> None:
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", DeprecationWarning)
        lexicon = Lexicon(**_entries(field))  # type: ignore[arg-type]
    with _caught() as record:
        line = _line_after()
        lexicon.remove(**_entries(field))
    [w] = _deprecations(record)
    _assert_set_field(w, "remove()", "lexicon.", SET_FIELDS[field][1], line)


@pytest.mark.parametrize("field", SET_FIELDS)
def test_replace_with_a_set_field_warns(field: str) -> None:
    lexicon = Lexicon.empty()
    with _caught() as record:
        line = _line_after()
        dataclasses.replace(lexicon, **_entries(field))  # type: ignore[arg-type]
    [w] = _deprecations(record)
    _assert_set_field(w, "dataclasses.replace()", "lexicon.",
                      SET_FIELDS[field][0], line)


def test_the_table_covers_every_set_field() -> None:
    from nameparser._lexicon import _VOCAB_FIELDS
    assert set(SET_FIELDS) == set(_VOCAB_FIELDS) - {"surnames"}


def test_surnames_through_add_or_remove_names_the_field_spelling() -> None:
    lexicon = Lexicon.empty()
    with _caught() as record:
        line = _line_after()
        lexicon.add(surnames={"kim"})
    [w] = _deprecations(record)
    _assert_set_field(w, "add()", "lexicon | Lexicon(surnames={'kim'})",
                      "", line)
    with _caught() as record:
        line = _line_after()
        lexicon.remove(surnames={"kim"})
    [w] = _deprecations(record)
    _assert_set_field(
        w, "remove()",
        "dataclasses.replace(lexicon, surnames=lexicon.surnames - {'kim'})",
        "", line)


def test_an_iterator_is_read_once_and_still_reaches_the_edit() -> None:
    with _caught() as record:
        edited = Lexicon.empty().add(titles=iter(["zork"]))
    assert edited.titles == frozenset({"zork"})
    [w] = _deprecations(record)
    assert ".add('zork', kind='title')" in str(w.message)


def test_a_bad_value_raises_its_own_error_before_any_warning() -> None:
    with warnings.catch_warnings():
        warnings.simplefilter("error")
        with pytest.raises(TypeError, match="decode first"):
            Lexicon.empty().add(titles=b"dr")  # type: ignore[arg-type]


@pytest.mark.parametrize("make", [
    pytest.param(lambda: Lexicon.empty(), id="empty"),
    pytest.param(lambda: Lexicon(surnames=frozenset({"kim"})), id="surnames"),
    pytest.param(lambda: Lexicon(capitalization_exceptions=(("phd", "PhD"),)),
                 id="capitalization_exceptions"),
    pytest.param(lambda: dataclasses.replace(
        Lexicon.default(), capitalization_exceptions=()), id="replace-cap"),
    pytest.param(lambda: Lexicon.default() | Lexicon(surnames=frozenset({"kim"})),
                 id="union"),
    pytest.param(lambda: pickle.loads(pickle.dumps(Lexicon.default())),
                 id="pickle"),
])
def test_the_fields_3_0_keeps_stay_quiet(make: Callable[[], object]) -> None:
    with warnings.catch_warnings():
        warnings.simplefilter("error")
        make()


# -- the library itself -------------------------------------------------------

def _packs() -> list[str]:
    # available() names the packs as their modules are named, lowercase
    return [name.upper() for name in locales.available()]


@pytest.mark.parametrize("call", [
    pytest.param(lambda: parse("Dr. Juan Q. de la Vega III, PhD"), id="parse"),
    pytest.param(Lexicon.default, id="Lexicon.default"),
    pytest.param(Parser, id="Parser"),
    pytest.param(lambda: Parser().revise(parse("John Smith"), given="Jane"),
                 id="revise"),
    *(pytest.param((lambda p: lambda: parser_for(getattr(locales, p)))(p),
                   id=f"parser_for-{p}") for p in _packs()),
])
def test_the_library_emits_none_of_these(call: Callable[[], object]) -> None:
    # every DeprecationWarning an error, the 2.8.0 facade messages aside;
    # parser_for(JA) warns a UserWarning without a segmenter, which is
    # not this test's
    with warnings.catch_warnings():
        warnings.simplefilter("error", DeprecationWarning)
        warnings.simplefilter("ignore", UserWarning)
        call()


def test_every_pack_module_imports_quietly() -> None:
    with warnings.catch_warnings():
        warnings.simplefilter("error")
        for pack in _packs():
            getattr(locales, pack)
            importlib.import_module(
                f"nameparser.locales.{pack.lower()}")


def test_the_facade_reads_none_of_these() -> None:
    # HumanName and Constants read the vocabulary and REGEXES; they warn
    # their own 2.8.0 removal, and nothing of 2.8.1's
    from nameparser import HumanName
    from nameparser.config import CONSTANTS, Constants
    with _caught() as record:
        HumanName("Dr. Juan de la Vega III").last  # noqa: B018
        Constants().titles  # noqa: B018
        CONSTANTS.regexes.word  # noqa: B018
    messages = [str(w.message) for w in _deprecations(record)]
    assert not [m for m in messages if "2.8.1" in m or "(#754)" in m
                or "(#1007)" in m or "(#1008)" in m], messages


def test_the_package_still_exports_the_lexicon_quietly() -> None:
    with warnings.catch_warnings():
        warnings.simplefilter("error")
        assert nameparser.Lexicon is Lexicon
