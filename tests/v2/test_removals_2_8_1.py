"""2.8.1's warnings for the 3.0 breaks 2.8.0 did not announce.

Three families, each a ``DeprecationWarning`` attributed to the caller's
line and naming the 3.0 replacement and the migration guide:

* the ``Lexicon`` set fields 3.0 makes internal (#754), written through
  ``Lexicon(...)``, ``add()``, ``remove()`` or ``dataclasses.replace``;
* the constants of the eight ``nameparser.config`` vocabulary modules
  3.0 deletes (#1007);
* ``nameparser.config.regexes`` (#1008);
* and, since 2.8.2, ``nameparser.config.surnames``, which 3.0 makes
  private (its words are ``Lexicon.default().surnames``).

The tables are written out literally rather than read from the modules,
for the reason tests/v2/test_config_aliases.py gives: imported, every
assertion would prove the bridge self-consistent rather than complete.
Reading an attribute (``lexicon.titles``) is deliberately not warned:
the pipeline reads those fields per token, so a property in their place
would cost a frame per read on the hot path (see the release log).
"""
from __future__ import annotations

import copy
import dataclasses
import importlib
import inspect
import pickle
import sys
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
#: public name of the ten modules, the 1.x aliases (which
#: test_config_aliases.py asserts) aside; surnames since 2.8.2.
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
    ("suffixes", "GLUED_HONORIFICS", 'words(kind="suffix", attached="after")'),
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
    ("regexes", "re_emoji", "copy a pattern you reuse"),
    ("regexes", "re_bidi", "copy a pattern you reuse"),
    ("regexes", "EMPTY_REGEX", "copy a pattern you reuse"),
    ("regexes", "REGEXES", "copy a pattern you reuse"),
    ("surnames", "KOREAN_SURNAMES", "Lexicon.default().surnames"),
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
    if module_name == "surnames":
        from nameparser.config import _ko_surnames
        assert value is _ko_surnames.KOREAN_SURNAMES
    elif module_name != "regexes":
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


def test_the_modules_import_quietly() -> None:
    with warnings.catch_warnings():
        warnings.simplefilter("error")
        for module_name in REMOVED_MODULES:
            importlib.import_module(f"nameparser.config.{module_name}")


def test_the_surnames_replacement_runs_quietly_and_holds_the_same_words(
        ) -> None:
    # 2.8.2: the message offers Lexicon.default().surnames, the field
    # 3.0 keeps public, as the code that replaces the read; run the
    # code it names and hold it to the constant it replaces
    from nameparser.config import surnames
    with _caught() as record:
        held = surnames.KOREAN_SURNAMES
    [w] = _deprecations(record)
    code = str(w.message).split("; ", 1)[1].split(" holds", 1)[0]
    assert code == "Lexicon.default().surnames"
    with warnings.catch_warnings():
        warnings.simplefilter("error")
        offered = eval(code, {"Lexicon": Lexicon})  # noqa: S307
    assert offered == held


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

#: Every compiled-set field 3.0 makes internal; surnames, which 3.0 keeps
#: as a field, is asserted on its own below. The message names the field
#: and the guide's row for it, never a computed 3.0 call: the right
#: reading for a word depends on its other readings (decided 2026-11-02).
SET_FIELDS = [
    "titles", "given_name_titles", "suffix_acronyms", "suffix_words",
    "suffix_acronyms_ambiguous", "particles", "particles_ambiguous",
    "conjunctions", "conjunctions_ambiguous", "bound_given_names",
    "given_name_abbreviations", "maiden_markers", "honorific_tails",
    "after_given_titles", "suffix_words_ambiguous", "agnomens",
    "titles_ambiguous", "title_modifiers", "title_styles", "title_phrases",
]
FIELDS_GUIDE = GUIDE + "#lexicon-fields-readings"

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
                      fields: list[str], line: int) -> None:
    message = str(w.message)
    assert w.category is DeprecationWarning
    assert message.startswith("Lexicon's set fields are deprecated (#754): "), (
        message)
    assert f"{spelling} writes {', '.join(fields)}, which 3.0 makes internal" \
        in message, message
    assert "TypeError" in message and '"Lexicon fields → readings"' in message
    # no computed 3.0 call: those were wrong for many words
    assert "kind=" not in message, message
    assert message.endswith(f"See {FIELDS_GUIDE}"), message
    assert (w.filename, w.lineno) == (__file__, line), (w.filename, w.lineno)


@pytest.mark.parametrize("field", SET_FIELDS)
def test_constructing_with_a_set_field_warns(field: str) -> None:
    entries = _entries(field)
    with _caught() as record:
        line = _line_after()
        Lexicon(**entries)  # type: ignore[arg-type]
    [w] = _deprecations(record)
    # named in declaration order, which _VOCAB_FIELDS keeps
    _assert_set_field(w, "Lexicon()",
                      [f for f in SET_FIELDS if f in entries], line)


@pytest.mark.parametrize("field", SET_FIELDS)
def test_add_with_a_set_field_warns(field: str) -> None:
    lexicon = Lexicon.empty()
    entries = _entries(field)
    with _caught() as record:
        line = _line_after()
        lexicon.add(**entries)
    [w] = _deprecations(record)
    _assert_set_field(w, "add()", list(entries), line)


@pytest.mark.parametrize("field", SET_FIELDS)
def test_remove_with_a_set_field_warns(field: str) -> None:
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", DeprecationWarning)
        lexicon = Lexicon(**_entries(field))  # type: ignore[arg-type]
    entries = _entries(field)
    with _caught() as record:
        line = _line_after()
        lexicon.remove(**entries)
    [w] = _deprecations(record)
    _assert_set_field(w, "remove()", list(entries), line)


@pytest.mark.parametrize("field", SET_FIELDS)
def test_replace_with_a_set_field_warns(field: str) -> None:
    lexicon = Lexicon.empty()
    entries = _entries(field)
    with _caught() as record:
        line = _line_after()
        dataclasses.replace(lexicon, **entries)  # type: ignore[arg-type]
    [w] = _deprecations(record)
    _assert_set_field(w, "dataclasses.replace()",
                      [f for f in SET_FIELDS if f in entries], line)


@pytest.mark.skipif(sys.version_info < (3, 13), reason="copy.replace is 3.13+")
def test_copy_replace_with_a_set_field_warns() -> None:
    # 3.13's dataclasses._replace names the instance `self`, where
    # dataclasses.replace names it `obj`
    lexicon = Lexicon.empty()
    with _caught() as record:
        line = _line_after()
        copy.replace(lexicon, titles=frozenset({"zork"}))  # type: ignore[attr-defined]
    [w] = _deprecations(record)
    _assert_set_field(w, "copy.replace()", ["titles"], line)


def test_the_table_covers_every_set_field() -> None:
    from nameparser._lexicon import _VOCAB_FIELDS
    assert SET_FIELDS == [f for f in _VOCAB_FIELDS if f != "surnames"]


def test_an_empty_set_field_still_names_the_field() -> None:
    # 3.0 refuses the keyword whatever it holds
    with _caught() as record:
        line = _line_after()
        Lexicon.empty().add(titles=frozenset())
    [w] = _deprecations(record)
    _assert_set_field(w, "add()", ["titles"], line)


def test_a_mixed_constructor_names_only_the_fields_3_0_refuses() -> None:
    with _caught() as record:
        line = _line_after()
        Lexicon(titles=frozenset({"zork"}), surnames=frozenset({"kim"}),
                capitalization_exceptions=(("phd", "PhD"),))
    [w] = _deprecations(record)
    _assert_set_field(w, "Lexicon()", ["titles"], line)
    assert "surnames" not in str(w.message)


@pytest.mark.parametrize("op", ["add", "remove"])
def test_surnames_through_add_or_remove_offers_code_that_runs_quietly(
        op: str) -> None:
    # the one 3.0 spelling that runs on 2.8.1 too, so the message hands
    # over code: run it, quietly, and get what the 2.x call made
    lexicon = Lexicon.empty().add(surnames=frozenset({"lee"}))
    if op == "remove":
        lexicon = lexicon | Lexicon(surnames=frozenset({"kim"}))
    with _caught() as record:
        line = _line_after()
        made = getattr(lexicon, op)(surnames=iter(["Kim"]))
    [w] = _deprecations(record)
    message = str(w.message)
    assert message.startswith("Lexicon's set fields are deprecated (#754): ")
    assert f"3.0 keeps surnames a field, but {op}() no longer takes it: " \
        "write " in message, message
    assert "which 3.0 makes internal" not in message
    assert message.endswith(f"See {FIELDS_GUIDE}")
    assert (w.filename, w.lineno) == (__file__, line)
    code = message.split(": write ", 1)[1].split(", which runs on", 1)[0]
    assert code == {
        "add": "lexicon | Lexicon(surnames=frozenset({'kim'}))",
        "remove": "dataclasses.replace(lexicon, "
                  "surnames=lexicon.surnames - {'kim'})",
    }[op]
    with warnings.catch_warnings():
        warnings.simplefilter("error")
        offered = eval(code, {"lexicon": lexicon, "Lexicon": Lexicon,  # noqa: S307
                              "dataclasses": dataclasses})
    assert offered == made


def test_a_long_surname_list_is_described_not_spelled() -> None:
    with _caught() as record:
        Lexicon.empty().add(surnames=frozenset("abcdefg"))
    [w] = _deprecations(record)
    assert "join a Lexicon holding those 7 surnames to it with |" in str(
        w.message)


def test_a_bad_value_raises_its_own_error_before_any_warning() -> None:
    with warnings.catch_warnings():
        warnings.simplefilter("error")
        with pytest.raises(TypeError, match="decode first"):
            Lexicon.empty().add(titles=b"dr")  # type: ignore[arg-type]


_QUIET = [
    pytest.param(lambda: Lexicon.empty(), id="empty"),
    pytest.param(lambda: Lexicon(surnames=frozenset({"kim"})), id="surnames"),
    pytest.param(lambda: Lexicon(capitalization_exceptions=(("phd", "PhD"),)),
                 id="capitalization_exceptions"),
    pytest.param(lambda: dataclasses.replace(
        Lexicon.default(), capitalization_exceptions=()), id="replace-cap"),
    pytest.param(lambda: dataclasses.replace(
        Lexicon.default(), surnames=frozenset({"kim"})), id="replace-surnames"),
    pytest.param(lambda: Lexicon.default() | Lexicon(surnames=frozenset({"kim"})),
                 id="union"),
    pytest.param(lambda: pickle.loads(pickle.dumps(Lexicon.default())),
                 id="pickle"),
    pytest.param(lambda: copy.deepcopy(Lexicon.default()), id="deepcopy"),
]
if sys.version_info >= (3, 13):
    _QUIET.append(pytest.param(
        lambda: copy.replace(  # type: ignore[attr-defined]
            Lexicon.default(), surnames=frozenset({"kim"})),
        id="copy.replace-surnames"))


@pytest.mark.parametrize("make", _QUIET)
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
