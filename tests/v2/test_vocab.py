"""The per-word vocabulary (nameparser/vocab/*.toml) and its compiler.

The parser reads nameparser/config/_compiled.py, never the TOML, so the
two halves of the guard are: the committed module is exactly what the
TOML compiles to (the snapshot.jsonl pattern -- a stale module fails with
the command that refreshes it), and the compiler's build checks pass on
the shipped files with warnings as errors. Each build check then has a
mutation below that it must refuse, because a check nothing exercises
passes the same way a missing one does.
"""
from __future__ import annotations

import importlib.util
import sys
import warnings
from pathlib import Path
from types import ModuleType
from typing import Any

import pytest

from nameparser._lexicon import Lexicon

_BUILD = Path(__file__).resolve().parents[2] / "tools" / "vocab" / "build.py"


def _load_build() -> ModuleType:
    # tools/ is outside testpaths (see _differential_fixtures.load_tool)
    spec = importlib.util.spec_from_file_location("vocab_build", _BUILD)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    # registered before it runs: its dataclasses look their module up
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


build = _load_build()


@pytest.fixture(scope="module")
def shipped() -> dict[str, str]:
    return build.read_dir()


def _compile(files: dict[str, str]) -> dict[str, Any]:
    with warnings.catch_warnings():
        warnings.simplefilter("error")
        result: dict[str, Any] = build.compile_files(files)
        return result


# ------------------------------------------------------------ shipped data
def test_the_committed_module_is_what_the_toml_compiles_to(shipped: dict[str, str]) -> None:
    fresh = build.render(_compile(shipped))
    committed = build.OUTPUT.read_text(encoding="utf-8")
    assert committed == fresh, (
        f"nameparser/config/_compiled.py is stale against nameparser/vocab/; "
        f"run: {build.REFRESH}")


def test_the_shipped_files_pass_every_check_with_warnings_as_errors(
        shipped: dict[str, str]) -> None:
    assert shipped, "no vocabulary files found; the roster is empty"
    _compile(shipped)


def test_the_compiled_sets_are_the_default_lexicon(shipped: dict[str, str]) -> None:
    c = _compile(shipped)
    lex = Lexicon.default()
    rebuilt = Lexicon(
        titles=c["TITLES"], given_name_titles=c["GIVEN_NAME_TITLES"],
        suffix_acronyms=c["SUFFIX_ACRONYMS"], suffix_words=c["SUFFIX_WORDS"],
        suffix_acronyms_ambiguous=c["SUFFIX_ACRONYMS_AMBIGUOUS"],
        particles=c["PARTICLES"],
        particles_ambiguous=c["PARTICLES"] - c["NON_GIVEN_NAME_PARTICLES"],
        conjunctions=c["CONJUNCTIONS"],
        conjunctions_ambiguous=c["CONJUNCTIONS_AMBIGUOUS"],
        bound_given_names=c["BOUND_GIVEN_NAMES"],
        maiden_markers=c["MAIDEN_MARKERS"], surnames=lex.surnames,
        honorific_tails=c["GLUED_HONORIFICS"],
        capitalization_exceptions=tuple(c["CAPITALIZATION_EXCEPTIONS"].items()),
    )
    assert rebuilt == lex


def test_the_toml_ships_as_package_data() -> None:
    # pyproject's package-data glob is what puts the files in a wheel;
    # a file outside it would be in the checkout and nowhere else
    import tomllib
    pyproject = tomllib.loads(
        (_BUILD.parents[2] / "pyproject.toml").read_text(encoding="utf-8"))
    globs = pyproject["tool"]["setuptools"]["package-data"]["nameparser"]
    assert "vocab/*.toml" in globs
    assert not [p for p in build.VOCAB.rglob("*") if p.is_file() and p.suffix != ".toml"]


# --------------------------------------------- controls on the shipped data
def _edit(shipped: dict[str, str], file: str, old: str, new: str) -> dict[str, str]:
    files = dict(shipped)
    assert files[file].count(old) == 1, (file, old)
    files[file] = files[file].replace(old, new)
    return files


def test_dropping_a_flag_changes_the_compiled_module(shipped: dict[str, str]) -> None:
    files = _edit(shipped, "und.toml", 'text = "ma"\ncredential = { may_be_name = true, ',
                  'text = "ma"\ncredential = { ')
    c = _compile(files)
    assert "ma" not in c["SUFFIX_ACRONYMS_AMBIGUOUS"]
    assert build.render(c) != build.OUTPUT.read_text(encoding="utf-8")


def test_moving_a_word_between_files_changes_nothing(shipped: dict[str, str]) -> None:
    entry = '[[word]]\ntext = "jr"\ngeneration = {}\n'
    files = _edit(shipped, "en.toml", entry, "")
    files["und.toml"] += "\n" + entry
    assert build.render(_compile(files)) == build.render(_compile(shipped))


def test_an_exclusion_in_one_file_refuses_the_reading_in_another(
        shipped: dict[str, str]) -> None:
    files = dict(shipped)
    files["en.toml"] += '\n[[word]]\ntext = "fils"\ngeneration = {}\n'
    with pytest.raises(build.VocabError, match="767 US Census"):
        _compile(files)


# ------------------------------------------------- one mutation per check
OK = 'schema = 1\n\n[[word]]\ntext = "jr"\ngeneration = {}\n'


def _w(body: str) -> str:
    return f"schema = 1\n\n{body}\n"


MUTATIONS = [
    # 1: schema, unknown keys, file names
    ("no-schema", {"und.toml": '[[word]]\ntext = "jr"\ngeneration = {}\n'}, "needs `schema = 1`"),
    ("newer-schema", {"und.toml": OK.replace("schema = 1", "schema = 2")}, "newer than this compiler"),
    ("unknown-top-level-key", {"und.toml": "language = 'en'\n" + OK}, "unknown key 'language'"),
    ("reserved-top-level-key", {"und.toml": "default = false\n" + OK}, "reserved for phase 3"),
    ("file-name-not-a-tag", {"english.toml": OK}, "BCP 47 tag"),
    ("file-name-not-canonical-case", {"pt-br.toml": OK}, "BCP 47 tag"),
    ("reserved-reading-property", {"und.toml": _w('[[word]]\ntext = "mba"\ncredential = { bare_only = true }')}, "reserved for phase 2"),
    ("unknown-reading-property", {"und.toml": _w('[[word]]\ntext = "mba"\ncredential = { acronymm = true }')}, "unknown key 'acronymm'"),
    ("unknown-word-key", {"und.toml": _w('[[word]]\ntext = "jr"\ngeneration = {}\nlang = "en"')}, "unknown key 'lang'"),
    ("descriptive-key-on-the-word", {"und.toml": _w('[[word]]\ntext = "jr"\ngeneration = {}\nnote = "x"')}, "belongs on a reading"),
    # 2: text
    ("text-not-normalized", {"en.toml": _w('[[word]]\ntext = "Jnr."\ngeneration = {}')}, "normalized form"),
    ("text-double-spaced", {"und.toml": _w('[[word]]\ntext = "z  domu"\nbirth_marker = {}')}, "normalized form"),
    ("text-missing", {"und.toml": _w("[[word]]\ngeneration = {}")}, "non-empty `text`"),
    ("text-twice-in-a-file", {"en.toml": _w('[[word]]\ntext = "jr"\ngeneration = {}\n\n[[word]]\ntext = "jr"\nstatus = {}')}, "listed twice"),
    # 3: kinds, properties and values
    ("unregistered-kind", {"hr.toml": _w('[[word]]\ntext = "mlađi"\ngeneraton = {}')}, "unknown key 'generaton'"),
    ("reading-not-a-table", {"en.toml": _w('[[word]]\ntext = "jr"\ngeneration = true')}, "must be a table"),
    ("inert-entry", {"en.toml": _w('[[word]]\ntext = "jr"')}, "inert"),
    ("addresses-reserved-value", {"und.toml": _w('[[word]]\ntext = "sheikh"\ntitle = { addresses = "any" }')}, "reserved for a later phase"),
    ("attached-on-an-acronym", {"und.toml": _w('[[word]]\ntext = "mba"\ncredential = { attached = { side = "after" } }')}, "needs a word reading"),
    ("attached-before", {"ja.toml": _w('[[word]]\ntext = "さん"\nhonorific = { attached = { side = "before" } }')}, "side = 'after'"),
    ("may-be-name-on-a-word", {"en.toml": _w('[[word]]\ntext = "jr"\ngeneration = { may_be_name = true }')}, "may_be_name marks an acronym"),
    ("may-be-initial-on-a-word", {"und.toml": _w('[[word]]\ntext = "and"\nconjunction = { may_be_initial = true }')}, "CASED single letter"),
    ("may-be-initial-caseless", {"ar.toml": _w('[[word]]\ntext = "و"\nconjunction = { may_be_initial = true }')}, "CASED single letter"),
    ("particle-without-may-be-given", {"und.toml": _w('[[word]]\ntext = "van"\nparticle = {}')}, "states may_be_given"),
    ("flag-not-a-bool", {"und.toml": _w('[[word]]\ntext = "van"\nparticle = { may_be_given = "yes" }')}, "true or false"),
    ("issue-not-a-number", {"en.toml": _w('[[word]]\ntext = "jr"\ngeneration = { issue = "661" }')}, "issue number"),
    ("decided-not-a-date", {"en.toml": _w('[[word]]\ntext = "jr"\ngeneration = { decided = "2026-10-18" }')}, "TOML date"),
    ("gender-out-of-range", {"en.toml": _w('[[word]]\ntext = "jr"\ngeneration = { gender = "male" }')}, "gender must be"),
    ("count-without-as-of", {"fr.toml": _w('[[word]]\ntext = "fils"\nfamily = { us_census_2010 = 767 }\nexcluded = { generation = "x" }')}, "needs `as_of`"),
    ("count-source-typo", {"fr.toml": _w('[[word]]\ntext = "fils"\nfamily = { us_census = 767, as_of = 2026-10-16 }\nexcluded = { generation = "x" }')}, "unknown key 'us_census'"),
    ("exclusion-without-a-reason", {"fr.toml": _w('[[word]]\ntext = "fils"\nexcluded = { generation = { issue = 684 } }')}, "needs a reason"),
    ("exclusion-of-an-unknown-kind", {"fr.toml": _w('[[word]]\ntext = "fils"\nexcluded = { generaton = "x" }')}, "unknown kind"),
    ("refused-property-on-its-own-reading", {"ja.toml": _w('[[word]]\ntext = "殿"\nhonorific = { attached = { side = "after" }, excluded = { attached = "surnames end in it" } }')}, "surnames end in it"),
    # 4: one suffix kind per word, across files
    ("two-suffix-kinds", {"en.toml": OK, "und.toml": _w('[[word]]\ntext = "jr"\nstatus = {}')}, "one suffix kind per word"),
    # 5: one word reads one way in every file
    ("acronym-disagrees-across-files", {"ja.toml": _w('[[word]]\ntext = "博士"\ncredential = {}'), "zh.toml": _w('[[word]]\ntext = "博士"\ncredential = { acronym = false }')}, "acronym is"),
    ("may-be-name-disagrees-across-files", {"en.toml": _w('[[word]]\ntext = "ma"\ncredential = {}'), "und.toml": _w('[[word]]\ntext = "ma"\ncredential = { may_be_name = true }')}, "may_be_name is"),
    # 6: an exclusion holds across files
    ("excluded-kind-in-another-file", {"fr.toml": _w('[[word]]\ntext = "fils"\nexcluded = { generation = "Marie Fils" }'), "en.toml": _w('[[word]]\ntext = "fils"\ngeneration = {}')}, "Marie Fils"),
    ("excluded-category-in-another-file", {"und.toml": _w('[[word]]\ntext = "rai"\nexcluded = { suffix = "a surname" }'), "en.toml": _w('[[word]]\ntext = "rai"\ncredential = {}')}, "a surname"),
    ("excluded-property-in-another-file", {"ja.toml": _w('[[word]]\ntext = "博士"\ncredential = { acronym = false, excluded = { attached = "Hiroshi" } }'), "zh.toml": _w('[[word]]\ntext = "博士"\ncredential = { acronym = false, attached = { side = "after" } }')}, "Hiroshi"),
    # 7: same_as and cased
    ("same-as-missing-target", {"en.toml": _w('[[word]]\ntext = "jnr"\ngeneration = { same_as = "jr" }')}, "same_as 'jr'"),
    ("same-as-other-category", {"en.toml": _w('[[word]]\ntext = "jr"\ntitle = {}\n\n[[word]]\ntext = "jnr"\ngeneration = { same_as = "jr" }')}, "no suffix reading"),
    ("cased-spells-other-letters", {"und.toml": _w('[[word]]\ntext = "phd"\ncredential = { cased = "PhDr" }')}, "case mask"),
    ("two-cased-values", {"und.toml": _w('[[word]]\ntext = "ó"\nparticle = { may_be_given = false, cased = "Ó" }'), "ga.toml": _w('[[word]]\ntext = "ó"\ntitle = { cased = "ó" }')}, "one cased mask per word"),
    ("cased-disagrees-across-files", {"und.toml": _w('[[word]]\ntext = "ó"\nparticle = { may_be_given = false, cased = "Ó" }'), "ga.toml": _w('[[word]]\ntext = "ó"\nparticle = { may_be_given = false, cased = "ó" }')}, "cased is"),
    # 8: phrases
    ("phrase-title-addressing-the-family", {"und.toml": _w('[[word]]\ntext = "deputy secretary"\ntitle = {}')}, "phrase can never match"),
    ("phrase-particle", {"und.toml": _w('[[word]]\ntext = "de la"\nparticle = { may_be_given = false }')}, "phrase can never match"),
    # 9: a bound given name that is a particle may be given
    ("bound-given-particle-never-given", {"und.toml": _w('[[word]]\ntext = "abu"\nparticle = { may_be_given = false }\nbound_given = {}')}, "may_be_given = true"),
    # the data invariants that were import-time asserts
    ("elided-particle-without-its-twin", {"und.toml": _w('[[word]]\ntext = "d\'"\nparticle = { may_be_given = false }')}, "U\\+2019 spelling"),
    ("one-kind-acronym-and-word", {"en.toml": _w('[[word]]\ntext = "abc"\ncourtesy = {}'), "und.toml": _w('[[word]]\ntext = "abc"\ncourtesy = { acronym = true }')}, "acronym is"),
]


@pytest.mark.parametrize(("files", "message"), [m[1:] for m in MUTATIONS],
                         ids=[m[0] for m in MUTATIONS])
def test_a_build_check_refuses_its_mutation(files: dict[str, str], message: str) -> None:
    with pytest.raises(build.VocabError, match=message):
        _compile(files)


def test_every_mutation_starts_from_a_pool_the_checks_accept() -> None:
    # the negative control for the table: the shapes it mutates compile
    # when written correctly, so each refusal is the mutation's
    for files in (
        {"en.toml": OK},
        {"ja.toml": _w('[[word]]\ntext = "博士"\ncredential = { acronym = false }'),
         "zh.toml": _w('[[word]]\ntext = "博士"\ncredential = { acronym = false }')},
        {"en.toml": _w('[[word]]\ntext = "jr"\ngeneration = {}\n\n'
                       '[[word]]\ntext = "jnr"\ngeneration = { same_as = "jr" }')},
        {"und.toml": _w('[[word]]\ntext = "abu"\nparticle = { may_be_given = true }\nbound_given = {}')},
        {"und.toml": _w('[[word]]\ntext = "d\'"\nparticle = { may_be_given = false }\n\n'
                        '[[word]]\ntext = "d’"\nparticle = { may_be_given = false }')},
        {"und.toml": _w('[[word]]\ntext = "sir and dame"\ntitle = { addresses = "given" }')},
        {"fr.toml": _w('[[word]]\ntext = "fils"\nfamily = { us_census_2010 = 767, as_of = 2026-10-16 }\n'
                       'excluded = { generation = { reason = "Marie Fils", issue = 684 } }')},
        {"pt-BR.toml": OK, "zh-Hant.toml": _w('[[word]]\ntext = "社長"\nprofessional_honorific = {}'),
         "es-419.toml": _w('[[word]]\ntext = "sr"\ngeneration = {}')},
    ):
        _compile(files)


def test_a_name_reading_on_nothing_warns() -> None:
    files = {"en.toml": _w('[[word]]\ntext = "smith"\nfamily = { us_census_2010 = 2442977, as_of = 2026-10-16 }')}
    with pytest.warns(build.VocabWarning, match="inert"):
        build.compile_files(files)


def test_a_check_failure_names_the_refresh_command_in_main(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
    out = tmp_path / "_compiled.py"
    out.write_text("stale\n", encoding="utf-8")
    monkeypatch.setattr(build, "OUTPUT", out)
    monkeypatch.setattr(build, "ROOT", tmp_path)
    assert build.main(["--check"]) == 1
    assert build.REFRESH in capsys.readouterr().out
    assert out.read_text(encoding="utf-8") == "stale\n"
