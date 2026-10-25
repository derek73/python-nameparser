"""The per-word vocabulary (nameparser/vocab/*.toml) and its compiler.

The parser reads nameparser/config/_compiled.py, never the TOML, so the
two halves of the guard are: the committed module is exactly what the
TOML compiles to (the snapshot.jsonl pattern -- a stale module fails with
the command that refreshes it), and the compiler's build checks pass on
the shipped files with warnings as errors. Each numbered build check
then has a mutation below that it must refuse, because a check nothing
exercises passes the same way a missing one does. A check WIDENED to
refuse more keeps a row for every case its narrower form refused:
#737's review widened check 6 from "the same kind" to "the same set"
and the new check quietly stopped refusing the excluded kind itself
with `acronym` flipped, a case nothing listed because the old check had
made it impossible. compile_pool's final
acronym-and-word check is a backstop check 5 always reaches first, so
its mutation is refused by check 5.
"""
from __future__ import annotations

import importlib.util
import re
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
        after_given_titles=c["AFTER_GIVEN_TITLES"],
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
    assert not [p for p in build.VOCAB.rglob("*")
                if p.is_file() and p.suffix != ".toml" and p.name != build.README]


# --------------------------------------------- controls on the shipped data
def _edit(shipped: dict[str, str], file: str, old: str, new: str) -> dict[str, str]:
    files = dict(shipped)
    assert files[file].count(old) == 1, (file, old)
    files[file] = files[file].replace(old, new)
    return files


def test_dropping_a_flag_changes_the_compiled_module(shipped: dict[str, str]) -> None:
    files = _edit(shipped, "en.toml", 'text = "jd"\ncredential = { may_be_name = true, ',
                  'text = "jd"\ncredential = { ')
    c = _compile(files)
    assert "jd" not in c["SUFFIX_ACRONYMS_AMBIGUOUS"]
    assert build.render(c) != build.OUTPUT.read_text(encoding="utf-8")


def test_moving_a_word_between_files_changes_nothing(shipped: dict[str, str]) -> None:
    entry = '[[word]]\ntext = "jr"\ngeneration = {}\n'
    files = _edit(shipped, "en.toml", entry, "")
    files["und.toml"] += "\n" + entry
    assert build.render(_compile(files)) == build.render(_compile(shipped))


def test_an_exclusion_in_one_file_refuses_the_reading_in_another(
        shipped: dict[str, str]) -> None:
    files = dict(shipped)
    # appended to an ordered file, out of place: the reason still comes
    # first, check 10 running last
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
    ("file-with-no-entries", {"en.toml": OK, "und.toml": "schema = 1\n"}, "no \\[\\[word\\]\\] entries"),
    ("reserved-reading-property", {"und.toml": _w('[[word]]\ntext = "mba"\ncredential = { bare_only = true }')}, "reserved for phase 2"),
    ("unknown-reading-property", {"und.toml": _w('[[word]]\ntext = "mba"\ncredential = { acronymm = true }')}, "unknown key 'acronymm'"),
    ("unknown-word-key", {"und.toml": _w('[[word]]\ntext = "jr"\ngeneration = {}\nlang = "en"')}, "unknown key 'lang'"),
    ("descriptive-key-on-the-word", {"und.toml": _w('[[word]]\ntext = "jr"\ngeneration = {}\nnote = "x"')}, "belongs on a reading"),
    # 2: text
    ("text-not-normalized", {"en.toml": _w('[[word]]\ntext = "Jnr."\ngeneration = {}')}, "normalized form"),
    ("text-double-spaced", {"und.toml": _w('[[word]]\ntext = "z  domu"\nbirth_marker = {}')}, "normalized form"),
    ("text-missing", {"und.toml": _w("[[word]]\ngeneration = {}")}, "non-empty `text`"),
    # a text no token can equal: the tokenizer divides at a comma and a
    # nakaguro, strips a bidi mark, and keeps an invisible character the
    # file does not show
    ("text-with-a-comma", {"en.toml": _w('[[word]]\ntext = "jr,"\ngeneration = {}')}, "divides a name at"),
    ("text-with-a-nakaguro", {"ja.toml": _w('[[word]]\ntext = "さん・"\nhonorific = {}')}, "divides a name at"),
    ("text-with-a-bidi-mark", {"he.toml": _w('[[word]]\ntext = "dr\\u200f"\ntitle = {}')}, "invisible character U\\+200F"),
    ("text-with-a-zero-width-space", {"en.toml": _w('[[word]]\ntext = "dr\\u200b"\ntitle = {}')}, "invisible character U\\+200B"),
    ("text-with-a-control-character", {"en.toml": _w('[[word]]\ntext = "dr\\u0007"\ntitle = {}')}, "invisible character U\\+0007"),
    ("text-with-an-emoji", {"en.toml": _w('[[word]]\ntext = "dr★"\ntitle = {}')}, "strips by default"),
    ("text-with-an-east-asian-interpunct", {"zh.toml": _w('[[word]]\ntext = "先·生"\nhonorific = {}')}, "rules/T3"),
    ("phrase-word-with-an-edge-period", {"de.toml": _w('[[word]]\ntext = "dr. med"\ntitle = { addresses = "given" }')}, "write 'dr med'"),
    ("text-twice-in-a-file", {"en.toml": _w('[[word]]\ntext = "jr"\ngeneration = {}\n\n[[word]]\ntext = "jr"\nstatus = {}')}, "listed twice"),
    # 3: kinds, properties and values
    ("unregistered-kind", {"hr.toml": _w('[[word]]\ntext = "mlađi"\ngeneraton = {}')}, "unknown key 'generaton'"),
    ("reading-not-a-table", {"en.toml": _w('[[word]]\ntext = "jr"\ngeneration = true')}, "must be a table"),
    ("inert-entry", {"en.toml": _w('[[word]]\ntext = "jr"')}, "inert"),
    ("addresses-typo", {"und.toml": _w('[[word]]\ntext = "sheikh"\ntitle = { addresses = "givn" }')}, "must be 'family' or 'given'"),
    # every title kind, not only the generic one (#750): keyed on the
    # kind, a typo on a classified title would compile as the family
    ("addresses-typo-on-a-title-kind", {"ar.toml": _w('[[word]]\ntext = "sheikh"\nstyle = { addresses = "givn" }')}, "must be 'family' or 'given'"),
    ("acronym-with-a-period", {"und.toml": _w('[[word]]\ntext = "x.q"\ncredential = {}')}, "matched with every period removed"),
    ("excluded-property-unknown", {"ja.toml": _w('[[word]]\ntext = "殿"\nhonorific = { excluded = { atached = "x" } }')}, "not a behavioral property"),
    ("excluded-defaulted-property-overridden", {"und.toml": _w('[[word]]\ntext = "mba"\ncredential = { acronym = false, excluded = { acronym = "x" } }')}, "acronym = false is excluded"),
    ("excluded-property-set-in-another-file", {"ja.toml": _w('[[word]]\ntext = "名"\nhonorific = { excluded = { attached = "x" } }'), "zh.toml": _w('[[word]]\ntext = "名"\nhonorific = { attached = { side = "after" } }')}, "attached = .* is excluded"),
    # `cased` compiles per word, so its exclusion holds over every kind
    ("excluded-cased-set-by-another-kind", {"und.toml": _w('[[word]]\ntext = "mc"\ntitle = { excluded = { cased = "keep as written" } }'), "en.toml": _w('[[word]]\ntext = "mc"\nparticle = { may_be_given = true, cased = "MC" }')}, "keep as written"),
    # a property exclusion's baseline is the EXCLUDING kind's unwritten
    # value: a credential keeps its acronym unwritten, a generic suffix
    # does not, so the word reading is the refused one, and says so
    ("excluded-acronym-sidestepped-by-a-word-kind", {"en.toml": _w('[[word]]\ntext = "xyz"\ncredential = { excluded = { acronym = "keep acronym" } }'), "fr.toml": _w('[[word]]\ntext = "xyz"\nsuffix = {}')}, "acronym = false is excluded.*keep acronym"),
    # a refused value is shown as TOML writes it, dates included
    ("refused-value-with-a-date", {"ja.toml": _w('[[word]]\ntext = "名"\nhonorific = { excluded = { attached = "x" } }'), "zh.toml": _w('[[word]]\ntext = "名"\nhonorific = { attached = { side = "after", decided = 2026-10-18 } }')}, "decided = 2026-10-18 }"),
    # the exclusion's reason is shown before check 4's complaint
    ("excluded-reason-shown-before-one-kind-per-word", {"fr.toml": _w('[[word]]\ntext = "fils"\ncredential = {}\nexcluded = { generation = "RECORDED REASON" }'), "en.toml": _w('[[word]]\ntext = "fils"\ngeneration = {}')}, "RECORDED REASON"),
    ("excluded-property-reason-shown-before-one-kind-per-word", {"ja.toml": _w('[[word]]\ntext = "名"\nhonorific = { excluded = { attached = "RECORDED REASON" } }'), "zh.toml": _w('[[word]]\ntext = "名"\ncourtesy = { attached = { side = "after" } }')}, "RECORDED REASON"),
    ("addresses-reserved-value", {"und.toml": _w('[[word]]\ntext = "sheikh"\ntitle = { addresses = "any" }')}, "reserved for a later phase"),
    ("addresses-reserved-value-on-a-title-kind", {"en.toml": _w('[[word]]\ntext = "sir"\nnobility = { addresses = "full" }')}, "reserved for a later phase"),
    ("attached-on-an-acronym", {"und.toml": _w('[[word]]\ntext = "mba"\ncredential = { attached = { side = "after" } }')}, "needs a word reading"),
    ("attached-before", {"ja.toml": _w('[[word]]\ntext = "さん"\nhonorific = { attached = { side = "before" } }')}, "side = 'after'"),
    ("may-be-name-on-a-word", {"en.toml": _w('[[word]]\ntext = "jr"\ngeneration = { may_be_name = true }')}, "may_be_name marks an acronym"),
    ("may-be-initial-on-a-word", {"und.toml": _w('[[word]]\ntext = "and"\nconjunction = { may_be_initial = true }')}, "CASED single letter"),
    ("may-be-initial-caseless", {"ar.toml": _w('[[word]]\ntext = "و"\nconjunction = { may_be_initial = true }')}, "CASED single letter"),
    ("after-given-on-an-office", {"en.toml": _w('[[word]]\ntext = "king"\nnobility = { after_given = true }')}, "after_given is allowed on a salutation reading only"),
    ("after-given-on-a-generic-title", {"und.toml": _w('[[word]]\ntext = "zzq"\ntitle = { after_given = true }')}, "after_given is allowed on a salutation reading only"),
    # herr's shape: refused in de.toml, flagged in da.toml
    ("excluded-after-given-in-another-file", {"de.toml": _w('[[word]]\ntext = "herr"\nsalutation = { excluded = { after_given = "a surname" } }'), "da.toml": _w('[[word]]\ntext = "herr"\nsalutation = { after_given = true }')}, "after_given = true is excluded.*a surname"),
    ("after-given-not-a-flag", {"en.toml": _w('[[word]]\ntext = "mr"\nsalutation = { after_given = "yes" }')}, "after_given must be true or false"),
    ("particle-without-may-be-given", {"und.toml": _w('[[word]]\ntext = "van"\nparticle = {}')}, "states may_be_given"),
    # every particle kind, not only the generic one (#749): unwritten,
    # the flag would read false and put the word in the never-given half
    ("particle-kind-without-may-be-given", {"nl.toml": _w('[[word]]\ntext = "van"\npreposition = {}')}, "states may_be_given"),
    ("flag-not-a-bool", {"und.toml": _w('[[word]]\ntext = "van"\nparticle = { may_be_given = "yes" }')}, "true or false"),
    ("issue-not-a-number", {"en.toml": _w('[[word]]\ntext = "jr"\ngeneration = { issue = "661" }')}, "issue number"),
    ("decided-not-a-date", {"en.toml": _w('[[word]]\ntext = "jr"\ngeneration = { decided = "2026-10-18" }')}, "TOML date"),
    # tomllib reads a date-time as a datetime, which isinstance calls a date
    ("decided-a-date-time", {"en.toml": _w('[[word]]\ntext = "jr"\ngeneration = { decided = 2026-10-18T09:00:00 }')}, "not a string or a date-time"),
    ("as-of-a-date-time", {"fr.toml": _w('[[word]]\ntext = "fils"\nfamily = { us_census_2010 = 767, as_of = 2026-10-16T00:00:00Z }\nexcluded = { generation = "x" }')}, "as_of must be a TOML date"),
    ("as-of-without-a-count", {"fr.toml": _w('[[word]]\ntext = "fils"\nfamily = { as_of = 2026-10-16 }\nexcluded = { generation = "x" }')}, "as_of dates a count"),
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
    ("may-be-given-disagrees-across-files", {"und.toml": _w('[[word]]\ntext = "van"\nparticle = { may_be_given = true }'), "nl.toml": _w('[[word]]\ntext = "van"\nparticle = { may_be_given = false }')}, "may_be_given is"),
    # keyed on the category: a word may take another particle kind in
    # each language, and the kinds must still agree (#749 widened this
    # from the kind; the narrower test let both may_be_given rows through)
    ("may-be-given-disagrees-across-particle-kinds", {"fr.toml": _w('[[word]]\ntext = "de"\npreposition = { may_be_given = false }'), "nl.toml": _w('[[word]]\ntext = "de"\narticle = { may_be_given = true }')}, "may_be_given is"),
    # `cased` too: the narrower check let two kinds through to the
    # per-word mask check, which refused them with its own message
    ("cased-disagrees-across-particle-kinds", {"und.toml": _w('[[word]]\ntext = "ó"\nparticle = { may_be_given = false, cased = "Ó" }'), "ga.toml": _w('[[word]]\ntext = "ó"\nclan = { may_be_given = false, cased = "ó" }')}, "cased is"),
    ("may-be-given-disagrees-with-the-generic-kind", {"und.toml": _w('[[word]]\ntext = "van"\nparticle = { may_be_given = true }'), "nl.toml": _w('[[word]]\ntext = "van"\npreposition = { may_be_given = false }')}, "may_be_given is"),
    ("addresses-disagrees-across-files", {"und.toml": _w('[[word]]\ntext = "sir"\ntitle = { addresses = "given" }'), "en.toml": _w('[[word]]\ntext = "sir"\ntitle = {}')}, "addresses is"),
    # keyed on the category: a title may take another kind in each file
    # (#750), and the kinds must still agree on which name they address
    ("addresses-disagrees-across-title-kinds", {"en.toml": _w('[[word]]\ntext = "sir"\nnobility = { addresses = "given" }'), "fr.toml": _w('[[word]]\ntext = "sir"\nsalutation = {}')}, "addresses is"),
    ("addresses-disagrees-with-the-generic-title", {"und.toml": _w('[[word]]\ntext = "sir"\ntitle = {}'), "en.toml": _w('[[word]]\ntext = "sir"\nnobility = { addresses = "given" }')}, "addresses is"),
    ("may-be-name-disagrees-across-files", {"en.toml": _w('[[word]]\ntext = "ma"\ncredential = {}'), "und.toml": _w('[[word]]\ntext = "ma"\ncredential = { may_be_name = true }')}, "may_be_name is"),
    # 6: an exclusion holds across files
    ("excluded-kind-in-another-file", {"fr.toml": _w('[[word]]\ntext = "fils"\nexcluded = { generation = "Marie Fils" }'), "en.toml": _w('[[word]]\ntext = "fils"\ngeneration = {}')}, "Marie Fils"),
    # the excluded kind ITSELF, with a property moving it to the other
    # set: the narrower test refused this, so the widened one must too
    ("excluded-kind-with-acronym-flipped", {"fr.toml": _w('[[word]]\ntext = "fils"\nexcluded = { generation = "Marie Fils" }'), "en.toml": _w('[[word]]\ntext = "fils"\ngeneration = { acronym = true }')}, "Marie Fils"),
    ("excluded-credential-as-a-word", {"und.toml": _w('[[word]]\ntext = "rai"\nexcluded = { credential = "a surname" }'), "en.toml": _w('[[word]]\ntext = "rai"\ncredential = { acronym = false }')}, "a surname"),
    ("excluded-kind-in-the-same-entry", {"en.toml": _w('[[word]]\ntext = "fils"\ngeneration = { acronym = true }\nexcluded = { generation = "Marie Fils" }')}, "Marie Fils"),
    ("excluded-kind-sidestepped-by-the-generic-kind", {"fr.toml": _w('[[word]]\ntext = "fils"\nexcluded = { generation = "Marie Fils" }'), "und.toml": _w('[[word]]\ntext = "fils"\nsuffix = {}')}, "Marie Fils"),
    ("excluded-kind-sidestepped-by-a-sibling-kind", {"fr.toml": _w('[[word]]\ntext = "fils"\nexcluded = { generation = "Marie Fils" }'), "en.toml": _w('[[word]]\ntext = "fils"\nstatus = {}')}, "Marie Fils"),
    ("excluded-credential-sidestepped-by-an-acronym", {"und.toml": _w('[[word]]\ntext = "rai"\nexcluded = { credential = "a surname" }'), "en.toml": _w('[[word]]\ntext = "rai"\ncourtesy = { acronym = true }')}, "a surname"),
    # a particle kind's exclusion refuses every other particle kind:
    # one particle kind per file made this impossible before #749
    ("excluded-particle-kind-sidestepped-by-a-sibling-kind", {"ar.toml": _w('[[word]]\ntext = "ben"\nexcluded = { patronymic = "Ben is a given name" }'), "pl.toml": _w('[[word]]\ntext = "ben"\npreposition = { may_be_given = false }')}, "Ben is a given name"),
    ("excluded-particle-kind-sidestepped-by-the-generic-kind", {"ar.toml": _w('[[word]]\ntext = "ben"\nexcluded = { patronymic = "Ben is a given name" }'), "und.toml": _w('[[word]]\ntext = "ben"\nparticle = { may_be_given = true }')}, "Ben is a given name"),
    ("excluded-particle-category-refuses-a-kind", {"ga.toml": _w('[[word]]\ntext = "o"\nexcluded = { particle = "a periodless initial" }\nclan = { may_be_given = false }')}, "a periodless initial"),
    # a title kind's exclusion refuses every other title kind, and the
    # title category every kind: one title kind made both impossible
    # before #750
    ("excluded-title-kind-sidestepped-by-a-sibling-kind", {"cs.toml": _w('[[word]]\ntext = "pan"\nexcluded = { salutation = "the Chinese surname Pan" }'), "en.toml": _w('[[word]]\ntext = "pan"\noffice = {}')}, "the Chinese surname Pan"),
    ("excluded-title-kind-sidestepped-by-the-generic-kind", {"cs.toml": _w('[[word]]\ntext = "pan"\nexcluded = { salutation = "the Chinese surname Pan" }'), "und.toml": _w('[[word]]\ntext = "pan"\ntitle = {}')}, "the Chinese surname Pan"),
    # a refused property is refused on every kind of its category, with
    # the recorded reason: keyed on the kind, check 5 would still refuse
    # this, but with its own message instead of the reason
    ("excluded-addresses-reason-shown-across-title-kinds", {"ar.toml": _w('[[word]]\ntext = "sheikh"\nsalutation = { excluded = { addresses = "RECORDED REASON" } }'), "en.toml": _w('[[word]]\ntext = "sheikh"\nnobility = { addresses = "given" }')}, "RECORDED REASON"),
    ("excluded-title-category-refuses-a-kind", {"vi.toml": _w('[[word]]\ntext = "ông"\nexcluded = { title = "a surname that leads" }\nsalutation = {}')}, "a surname that leads"),
    ("excluded-category-in-another-file", {"und.toml": _w('[[word]]\ntext = "rai"\nexcluded = { suffix = "a surname" }'), "en.toml": _w('[[word]]\ntext = "rai"\ncredential = {}')}, "a surname"),
    # a reason written as a table reaches the refusal too
    ("excluded-kind-with-a-table-reason", {"fr.toml": _w('[[word]]\ntext = "fils"\nexcluded = { generation = { reason = "TABLE REASON", issue = 684 } }'), "en.toml": _w('[[word]]\ntext = "fils"\ngeneration = {}')}, "TABLE REASON"),
    ("excluded-property-in-another-file", {"ja.toml": _w('[[word]]\ntext = "博士"\ncredential = { acronym = false, excluded = { attached = "Hiroshi" } }'), "zh.toml": _w('[[word]]\ntext = "博士"\ncredential = { acronym = false, attached = { side = "after" } }')}, "Hiroshi"),
    # 7: same_as and cased
    ("same-as-missing-target", {"en.toml": _w('[[word]]\ntext = "jnr"\ngeneration = { same_as = "jr" }')}, "same_as 'jr'"),
    ("same-as-its-own-word", {"en.toml": _w('[[word]]\ntext = "jr"\ngeneration = { same_as = "jr" }')}, "names the word itself"),
    ("same-as-other-category", {"en.toml": _w('[[word]]\ntext = "jr"\ntitle = {}\n\n[[word]]\ntext = "jnr"\ngeneration = { same_as = "jr" }')}, "no suffix reading"),
    ("cased-spells-other-letters", {"und.toml": _w('[[word]]\ntext = "phd"\ncredential = { cased = "PhDr" }')}, "case mask"),
    ("two-cased-values", {"und.toml": _w('[[word]]\ntext = "ó"\nparticle = { may_be_given = false, cased = "Ó" }'), "ga.toml": _w('[[word]]\ntext = "ó"\ntitle = { cased = "ó" }')}, "one cased mask per word"),
    ("cased-disagrees-across-files", {"und.toml": _w('[[word]]\ntext = "ó"\nparticle = { may_be_given = false, cased = "Ó" }'), "ga.toml": _w('[[word]]\ntext = "ó"\nparticle = { may_be_given = false, cased = "ó" }')}, "cased is"),
    # 8: phrases
    ("phrase-title-addressing-the-family", {"und.toml": _w('[[word]]\ntext = "deputy secretary"\ntitle = {}')}, "phrase can never match"),
    ("phrase-title-kind-addressing-the-family", {"en.toml": _w('[[word]]\ntext = "deputy secretary"\noffice = {}')}, "phrase can never match"),
    ("phrase-with-cased", {"und.toml": _w('[[word]]\ntext = "sir and dame"\ntitle = { addresses = "given", cased = "Sir and Dame" }')}, "looked up per word"),
    ("phrase-particle", {"und.toml": _w('[[word]]\ntext = "de la"\nparticle = { may_be_given = false }')}, "phrase can never match"),
    # 9: a bound given name that is a particle may be given
    ("bound-given-particle-never-given", {"und.toml": _w('[[word]]\ntext = "abu"\nparticle = { may_be_given = false }\nbound_given = {}')}, "may_be_given = true"),
    ("bound-given-particle-kind-never-given", {"und.toml": _w('[[word]]\ntext = "abu"\nbound_given = {}'), "ar.toml": _w('[[word]]\ntext = "abu"\nteknonymic = { may_be_given = false }')}, "may_be_given = true"),
    # the data invariants that were import-time asserts
    ("elided-particle-without-its-twin", {"und.toml": _w('[[word]]\ntext = "d\'"\nparticle = { may_be_given = false }')}, "U\\+2019 spelling"),
    ("elided-particle-kind-without-its-twin", {"fr.toml": _w('[[word]]\ntext = "l\'"\narticle = { may_be_given = false }')}, "U\\+2019 spelling"),
    ("one-kind-acronym-and-word", {"en.toml": _w('[[word]]\ntext = "abc"\ncourtesy = {}'), "und.toml": _w('[[word]]\ntext = "abc"\ncourtesy = { acronym = true }')}, "acronym is"),
    # 10: canonical word order. A swapped pair, within a kind and across
    # kinds and categories
    ("words-out-of-order", {"en.toml": _w('[[word]]\ntext = "sr"\ngeneration = {}\n\n[[word]]\ntext = "jr"\ngeneration = {}')}, "'sr' \\(generation\\) belongs after 'jr'"),
    ("kinds-out-of-order", {"en.toml": _w('[[word]]\ntext = "esq"\ncourtesy = {}\n\n[[word]]\ntext = "jr"\ngeneration = {}')}, "'esq' \\(courtesy\\) belongs after 'jr'"),
    ("categories-out-of-order", {"de.toml": _w('[[word]]\ntext = "von"\npreposition = { may_be_given = false }\n\n[[word]]\ntext = "dr"\ntitle = {}')}, "'von' \\(preposition\\) belongs after 'dr'"),
    # the title kinds sort in CATEGORY's order, inside the category
    ("title-kinds-out-of-order", {"en.toml": _w('[[word]]\ntext = "mayor"\noffice = {}\n\n[[word]]\ntext = "mr"\nsalutation = {}')}, "'mayor' \\(office\\) belongs after 'mr'"),
    # a same_as variant sorts after its head, not by its own text: in
    # plain alphabetical order jnr would come first
    ("same-as-variant-before-its-head", {"en.toml": _w('[[word]]\ntext = "jnr"\ngeneration = { same_as = "jr" }\n\n[[word]]\ntext = "jr"\ngeneration = {}')}, "'jnr' \\(generation\\) belongs after 'jr'"),
    # and beside it: alphabetically 'younger' would follow 'sr'
    ("same-as-variant-away-from-its-head", {"en.toml": _w('[[word]]\ntext = "jr"\ngeneration = {}\n\n[[word]]\ntext = "sr"\ngeneration = {}\n\n[[word]]\ntext = "younger"\ngeneration = { same_as = "jr" }')}, "'sr' \\(generation\\) belongs after 'younger'"),
    # an entry recording only a refusal sorts under the kind it refuses
    ("refusal-out-of-its-kind", {"en.toml": _w('[[word]]\ntext = "jr"\ngeneration = {}\n\n[[word]]\ntext = "esq"\ncourtesy = {}\n\n[[word]]\ntext = "senior"\nexcluded = { generation = "x" }')}, "'esq' \\(courtesy\\) belongs after 'senior'"),
    ("refusal-first-in-the-file", {"en.toml": _w('[[word]]\ntext = "senior"\nexcluded = { generation = "x" }\n\n[[word]]\ntext = "jr"\ngeneration = {}')}, "'senior' \\(sorted as generation, the kind it refuses\\) belongs after 'jr'"),
    # the entry named is the one to move: a word appended at the end,
    # not the neighbours it displaced
    ("appended-word-out-of-place", {"en.toml": _w('[[word]]\ntext = "jr"\ngeneration = {}\n\n[[word]]\ntext = "sr"\ngeneration = {}\n\n[[word]]\ntext = "aa"\ngeneration = {}')}, "'aa' \\(generation\\) belongs before 'jr'"),
    # placed against the run kept in order, not beside a neighbour that
    # is out of place itself: of c d b a, b goes before c, not after a
    ("place-named-against-the-kept-run", {"en.toml": _w('[[word]]\ntext = "c"\ngeneration = {}\n\n[[word]]\ntext = "d"\ngeneration = {}\n\n[[word]]\ntext = "b"\ngeneration = {}\n\n[[word]]\ntext = "a"\ngeneration = {}')}, "'b' \\(generation\\) belongs before 'c'"),
    ("appended-word-mid-file", {"en.toml": _w('[[word]]\ntext = "jr"\ngeneration = {}\n\n[[word]]\ntext = "sr"\ngeneration = {}\n\n[[word]]\ntext = "ta"\ngeneration = {}\n\n[[word]]\ntext = "tb"\ngeneration = {}\n\n[[word]]\ntext = "ka"\ngeneration = {}')}, "'ka' \\(generation\\) belongs after 'jr'"),
    # a refused category sorts as its first kind
    ("refused-category-out-of-place", {"en.toml": _w('[[word]]\ntext = "zzz"\nexcluded = { relation = "x" }\n\n[[word]]\ntext = "jr"\ngeneration = {}')}, "'zzz' \\(sorted as birth_marker, the kind it refuses\\) belongs after 'jr'"),
    # the file's own chains decide its order, not another file's: de
    # makes jr a spelling of aa, and en must still put its jr first
    ("other-files-chain-does-not-place-a-head", {"de.toml": _w('[[word]]\ntext = "aa"\ngeneration = {}\n\n[[word]]\ntext = "jr"\ngeneration = { same_as = "aa" }'), "en.toml": _w('[[word]]\ntext = "jnr"\ngeneration = { same_as = "jr" }\n\n[[word]]\ntext = "jr"\ngeneration = {}')}, "en.toml: 'jnr' \\(generation\\) belongs after 'jr'"),
    # every other refusal is seen before the order's: a same_as typo
    ("same-as-typo-before-the-order", {"en.toml": _w('[[word]]\ntext = "jr"\ngeneration = {}\n\n[[word]]\ntext = "sr"\ngeneration = {}\n\n[[word]]\ntext = "younger"\ngeneration = { same_as = "jrx" }')}, "same_as 'jrx' has no suffix reading"),
    # a chain must end for the key to exist; und.toml's too, though
    # its order is not checked
    ("same-as-cycle", {"en.toml": _w('[[word]]\ntext = "jr"\ngeneration = { same_as = "jnr" }\n\n[[word]]\ntext = "jnr"\ngeneration = { same_as = "jr" }')}, "same_as loops, jnr -> jr -> jnr;"),
    ("same-as-cycle-in-und", {"und.toml": _w('[[word]]\ntext = "jr"\ngeneration = { same_as = "jnr" }\n\n[[word]]\ntext = "jnr"\ngeneration = { same_as = "jr" }')}, "same_as loops, jnr -> jr -> jnr;"),
    # over every same_as written: a loop across files, one another file's
    # head for the same word would hide, and one through an entry's
    # second kind of a category
    ("same-as-cycle-across-files", {"en.toml": _w('[[word]]\ntext = "jr"\ngeneration = {}\n\n[[word]]\ntext = "jnr"\ngeneration = { same_as = "jr" }'), "fr.toml": _w('[[word]]\ntext = "jr"\ngeneration = { same_as = "jnr" }')}, "same_as loops"),
    ("same-as-cycle-behind-another-files-head", {"de.toml": _w('[[word]]\ntext = "x"\ngeneration = {}\n\n[[word]]\ntext = "jr"\ngeneration = { same_as = "x" }'), "en.toml": _w('[[word]]\ntext = "jnr"\ngeneration = { same_as = "jr" }\n\n[[word]]\ntext = "jr"\ngeneration = { same_as = "jnr" }')}, "same_as loops, jnr -> jr -> jnr;"),
    ("same-as-cycle-through-a-second-kind", {"nl.toml": _w('[[word]]\ntext = "c"\npreposition = { may_be_given = true }\n\n[[word]]\ntext = "a"\npreposition = { may_be_given = true, same_as = "c" }\narticle = { may_be_given = true, same_as = "b" }\n\n[[word]]\ntext = "b"\narticle = { may_be_given = true, same_as = "a" }')}, "same_as loops, a -> b -> a;"),
    # a chain running INTO a loop: the loop is named, not the chain
    ("same-as-chain-into-a-loop", {"en.toml": _w('[[word]]\ntext = "xa"\ngeneration = { same_as = "xb" }\n\n[[word]]\ntext = "xb"\ngeneration = { same_as = "xc" }\n\n[[word]]\ntext = "xc"\ngeneration = { same_as = "xb" }')}, "same_as loops, xb -> xc -> xb;"),
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
        {"en.toml": _w('[[word]]\ntext = "sir and dame"\nnobility = { addresses = "given" }')},
        # a same_as may name a word of another title kind: check 7 asks
        # for the category
        {"en.toml": _w('[[word]]\ntext = "mr"\nsalutation = {}'),
         "de.toml": _w('[[word]]\ntext = "mister"\noffice = { same_as = "mr" }')},
        # a title kind's exclusion refuses the title set, not the word:
        # its particle reading stays free
        {"cs.toml": _w('[[word]]\ntext = "pan"\nexcluded = { salutation = "the Chinese surname Pan" }'),
         "und.toml": _w('[[word]]\ntext = "pan"\nparticle = { may_be_given = true }')},
        # one title in a different kind per file, agreeing on addresses
        {"en.toml": _w('[[word]]\ntext = "sir"\nnobility = { addresses = "given" }'),
         "fr.toml": _w('[[word]]\ntext = "sir"\nsalutation = { addresses = "given" }')},
        # a zero-width joiner or non-joiner is spelling, and a token keeps it
        {"fa.toml": _w('[[word]]\ntext = "ab\\u200ccd"\ntitle = {}\n\n'
                       '[[word]]\ntext = "ef\\u200dgh"\ntitle = {}')},
        # an interpunct is part of the word except between two East Asian
        # characters, and an East Asian text may end in one
        {"ca.toml": _w('[[word]]\ntext = "l·l"\ntitle = {}'),
         "zh.toml": _w('[[word]]\ntext = "先·"\nhonorific = {}')},
        # a phrase word may hold an interior period; a date is a date
        {"und.toml": _w('[[word]]\ntext = "lt.col and dame"\ntitle = { addresses = "given", decided = 2026-10-18 }')},
        {"fr.toml": _w('[[word]]\ntext = "fils"\nfamily = { us_census_2010 = 767, as_of = 2026-10-16 }\n'
                       'excluded = { generation = { reason = "Marie Fils", issue = 684 } }')},
        # the name kinds refuse only themselves: refused as a given name, a
        # word may still record its surname evidence
        {"fr.toml": _w('[[word]]\ntext = "fils"\nfamily = { us_census_2010 = 767, as_of = 2026-10-16 }\n'
                       'excluded = { given = "x", generation = "Marie Fils" }')},
        # a property exclusion refuses a value other than the default:
        # writing the default, as a particle must for may_be_given, passes
        {"und.toml": _w('[[word]]\ntext = "zz"\nparticle = { may_be_given = false, excluded = { may_be_given = "x" } }\n\n'
                        '[[word]]\ntext = "yy"\ncredential = { may_be_name = false, excluded = { may_be_name = "x" } }\n\n'
                        '[[word]]\ntext = "xx"\ncredential = { excluded = { acronym = "x" } }')},
        # the defaults agree with the written value across files
        {"und.toml": _w('[[word]]\ntext = "dr"\ntitle = {}'),
         "en.toml": _w('[[word]]\ntext = "dr"\ntitle = { addresses = "family" }')},
        # an exclusion refuses the set its kind feeds, not every suffix:
        # refusing the generation word leaves an acronym reading free
        {"fr.toml": _w('[[word]]\ntext = "fils"\nexcluded = { generation = "Marie Fils" }'),
         "und.toml": _w('[[word]]\ntext = "fils"\ncredential = {}')},
        {"pt-BR.toml": OK, "zh-Hant.toml": _w('[[word]]\ntext = "社長"\nprofessional_honorific = {}'),
         "es-419.toml": _w('[[word]]\ntext = "sr"\ngeneration = {}')},
        # check 10's order, met: kinds in CATEGORY order, a head before
        # its spellings, a refusal under the kind it refuses, a name
        # reading placing nothing beside a refusal, a comment moving with
        # its entry; und.toml is exempt, so its reverse order passes
        {"en.toml": _w('[[word]]\ntext = "dr"\ntitle = {}\n\n'
                       '[[word]]\ntext = "jr"\ngeneration = {}\n\n'
                       '[[word]]\ntext = "jnr"\ngeneration = { same_as = "jr" }\n\n'
                       '[[word]]\ntext = "junior"\ngeneration = { same_as = "jr" }\n\n'
                       '[[word]]\ntext = "senior"\nfamily = { us_census_2010 = 3864, as_of = 2026-10-16 }\n'
                       'excluded = { generation = "x" }\n\n'
                       '# a comment above an entry belongs to it\n'
                       '[[word]]\ntext = "sr"\ngeneration = {}\n\n'
                       '[[word]]\ntext = "esq"\ncourtesy = {}'),
         "und.toml": _w('[[word]]\ntext = "von"\nparticle = { may_be_given = false }\n\n'
                        '[[word]]\ntext = "sir"\ntitle = {}')},
        # a spelling's own spellings follow it, under the root head: by
        # the direct same_as alone, ed- would sort after ul-, under el-
        {"ar.toml": _w('[[word]]\ntext = "al-"\narticle = { may_be_given = false }\n\n'
                       '[[word]]\ntext = "ad-"\narticle = { may_be_given = false, same_as = "al-" }\n\n'
                       '[[word]]\ntext = "el-"\narticle = { may_be_given = false, same_as = "al-" }\n\n'
                       '[[word]]\ntext = "ed-"\narticle = { may_be_given = false, same_as = "el-" }\n\n'
                       '[[word]]\ntext = "ul-"\narticle = { may_be_given = false, same_as = "al-" }')},
        # a word sorts under its EARLIEST kind, not its first written;
        # a vocabulary reading outranks a refusal beside it; a refused
        # category sorts as its first kind
        {"en.toml": _w('[[word]]\ntext = "dr"\ntitle = {}\n\n'
                       '[[word]]\ntext = "md"\ncredential = {}\ntitle = {}\n\n'
                       '[[word]]\ntext = "jr"\ngeneration = {}\n\n'
                       '[[word]]\ntext = "aaa"\ncredential = {}\nexcluded = { generation = "x" }\n\n'
                       '[[word]]\ntext = "zzz"\nexcluded = { relation = "x" }')},
        # another file's chain does not place this file's head
        {"de.toml": _w('[[word]]\ntext = "aa"\ngeneration = {}\n\n'
                       '[[word]]\ntext = "jr"\ngeneration = { same_as = "aa" }'),
         "en.toml": _w('[[word]]\ntext = "jr"\ngeneration = {}\n\n'
                       '[[word]]\ntext = "jnr"\ngeneration = { same_as = "jr" }')},
        # texts compare by codepoint, script by script
        {"sr.toml": _w('[[word]]\ntext = "mlađi"\ngeneration = {}\n\n'
                       '[[word]]\ntext = "млађи"\ngeneration = {}')},
    ):
        _compile(files)


def _apply_order_messages(texts: list[str]) -> int:
    """Move entries as check 10's messages say until it passes; the moves."""
    moves = 0
    while True:
        words: list[dict[str, Any]] = [{"text": t, "generation": {}} for t in texts]
        try:
            build.check_order({"en.toml": words})
            return moves
        except build.VocabError as e:
            m = re.search(r"'(\w+)' \(generation\) belongs (after|before) '(\w+)'", str(e))
            assert m, str(e)
            word, side, other = m.groups()
            texts.remove(word)
            texts.insert(texts.index(other) + (side == "after"), word)
            moves += 1


def test_following_the_order_messages_takes_the_fewest_moves() -> None:
    # every order of six words: the fewest moves that sort a list is its
    # length less its longest run already in order, and following the
    # messages takes exactly that many (#767's second review found the
    # first version taking up to 22 moves where 10 would do)
    from itertools import permutations
    for order in permutations("abcdef"):
        ranks = [ord(c) - ord("a") for c in order]
        longest = [1] * 6
        for i in range(6):
            for j in range(i):
                if ranks[j] < ranks[i]:
                    longest[i] = max(longest[i], longest[j] + 1)
        assert _apply_order_messages(list(order)) == 6 - max(longest), order


def test_the_order_check_ends_on_its_own() -> None:
    # check_order called alone, without check 7 having refused a
    # self-reference first, and on a chain longer than Python's
    # recursion limit: it returns, it does not hang or recurse out
    build.check_order({"en.toml": [{"text": "a", "preposition": {"same_as": "a"}},
                                   {"text": "b", "preposition": {}}]})
    chain = [{"text": f"w{i:04d}", "generation": {"same_as": f"w{i + 1:04d}"}}
             for i in range(sys.getrecursionlimit() + 100)]
    build.check_order({"und.toml": chain})


def test_every_character_the_tokenizer_ignores_is_refused() -> None:
    # check 2's hand copies are held to the pipeline, and the sweep is
    # driven by the tokenizer's own predicate, so a separator or strip
    # class added there fails here until the build refuses it too. The
    # interpunct between East Asian characters is divided by context in
    # _tokenize_region, not by _ignorable, so the sweep cannot see it:
    # the MUTATIONS row text-with-an-east-asian-interpunct holds that check,
    # and the pins below hold only its constants
    from nameparser._pipeline import _tokenize
    from nameparser._pipeline._state import COMMA_CHARS, ParseState
    from nameparser._policy import Policy, _SCRIPT_RANGES
    assert build.DIVIDERS == COMMA_CHARS | _tokenize._NAME_DOT_SEPARATORS
    assert build.EMOJI_RANGES == _tokenize._EMOJI_RANGES
    assert build.EAST_ASIAN_RANGES == tuple(
        span for spans in _SCRIPT_RANGES.values() for span in spans)
    assert build.INTERPUNCT == _tokenize._INTERPUNCT
    state = ParseState(original="", lexicon=Lexicon.default(), policy=Policy(),
                       segmenter=None)
    ignored = [chr(c) for c in range(0x110000)
               # a space is the one ignored character a text holds: the
               # separator between a phrase's words
               if not 0xD800 <= c <= 0xDFFF and c != 0x20
               and (_tokenize._ignorable(chr(c), state) or chr(c) in COMMA_CHARS)]
    assert len(ignored) > 100, len(ignored)  # whitespace, bidi, emoji, dots, commas
    for ch in ignored:
        escaped = f"\\U{ord(ch):08X}"  # a TOML escape: no raw control in the file
        # refused by check 2 itself, not by whichever later check happens
        # to trip, which would leave a new class guarded by accident
        with pytest.raises(build.VocabError,
                           match="divides a name|strips by default|rules/T3|"
                                 "invisible character|not in normalized form"):
            build.load({"und.toml": _w(f'[[word]]\ntext = "dr{escaped}x"\ntitle = {{}}')})


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


def test_query_tells_a_refused_reading_from_a_refused_property() -> None:
    # --excluded <kind> is the words refused that reading; a property
    # refused on a reading the word keeps answers only to its own name
    spec = importlib.util.spec_from_file_location("vocab_query", _BUILD.with_name("query.py"))
    assert spec is not None and spec.loader is not None
    query = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = query
    spec.loader.exec_module(query)
    pool = query.build.load({
        "ja.toml": _w('[[word]]\ntext = "殿"\nhonorific = { excluded = { attached = "surnames end in it" } }'),
        "zh.toml": _w('[[word]]\ntext = "君"\nexcluded = { honorific = "王君 is a name" }'),
    })
    assert [r.text for r in query.select(pool, excluded="honorific")] == ["君"]
    assert [r.text for r in query.select(pool, excluded="attached")] == ["殿"]
    assert [r.text for r in query.select(pool, excluded="suffix")] == ["君"]
    # the label is for display only, built from the same fields
    assert sorted(r.label for r in query.rows(pool)) == [
        "excluded:honorific", "honorific", "honorific excluded:attached"]


def _load_query() -> ModuleType:
    spec = importlib.util.spec_from_file_location("vocab_query", _BUILD.with_name("query.py"))
    assert spec is not None and spec.loader is not None
    query = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = query
    spec.loader.exec_module(query)
    return query


QUERY_POOL = {
    "ja.toml": _w('[[word]]\ntext = "さん"\nhonorific = { issue = 308, attached = { side = "after", issue = 707 } }\n\n'
                  '[[word]]\ntext = "殿"\nhonorific = { excluded = { attached = { reason = "x", issue = 707 } } }'),
    "en.toml": _w('[[word]]\ntext = "jr"\ngeneration = { issue = 661 }\n\n'
                  '[[word]]\ntext = "senior"\nexcluded = { generation = { reason = "a surname", issue = 661 } }'),
    "und.toml": _w('[[word]]\ntext = "dr"\ntitle = {}'),
}


@pytest.mark.parametrize(("filters", "texts"), [
    ({"issue": 707}, ["殿", "さん"]),                 # in `attached`, and in an exclusion's table
    ({"issue": 308}, ["さん"]),
    ({"issue": 661}, ["jr", "senior"]),               # a reading and an exclusion
    ({"issue": 661, "kind": "generation"}, ["jr"]),   # --kind alone lists readings
    ({"kind": "suffix"}, ["さん", "殿", "jr"]),       # a category matches its kinds
    ({"kind": "honorific", "excluded": "attached"}, ["殿"]),
    ({"excluded": "suffix"}, ["senior"]),
    ({"excluded": "attach"}, []),                  # a property by its whole name only
    ({"file": "und.toml"}, ["dr"]),
    ({"word": "jr", "kind": "title"}, []),
])
def test_query_filters_combine(filters: dict[str, Any], texts: list[str]) -> None:
    query = _load_query()
    pool = query.build.load(QUERY_POOL)
    assert sorted(r.text for r in query.select(pool, **filters)) == sorted(texts)


def test_query_validates_its_arguments_and_reports_no_match(
        capsys: pytest.CaptureFixture[str]) -> None:
    query = _load_query()
    for argv in (["--kind", "honorifc"], ["--excluded", "attachd"], ["--file", "xx"]):
        with pytest.raises(SystemExit) as e:
            query.main(argv)
        assert e.value.code == 2, argv
    capsys.readouterr()
    assert query.main(["--word", "Dr.", "--count"]) == 0  # normalized to 'dr'
    assert capsys.readouterr().out.strip() not in ("", "0")
    assert query.main(["--word", "zzqnoword"]) == 1


def test_the_build_does_not_import_the_package_it_writes() -> None:
    # a _compiled.py left broken must not stop the tool that rewrites it
    import subprocess
    code = (f"import importlib.util, sys; "
            f"spec = importlib.util.spec_from_file_location('b', {str(_BUILD)!r}); "
            f"m = importlib.util.module_from_spec(spec); sys.modules['b'] = m; "
            f"spec.loader.exec_module(m); "
            f"print(sorted(n for n in sys.modules if n.split('.')[0] == 'nameparser'))")
    out = subprocess.run([sys.executable, "-I", "-c", code], capture_output=True,
                         text=True, check=True).stdout
    assert out.strip() == "[]"


def test_broken_data_exits_2_not_1(monkeypatch: pytest.MonkeyPatch,
                                   capsys: pytest.CaptureFixture[str]) -> None:
    monkeypatch.setattr(build, "read_dir", lambda: {"en.toml": _w('[[word]]\ntext = "jr"')})
    assert build.main(["--check"]) == 2
    assert "inert" in capsys.readouterr().err


def test_an_unreadable_file_exits_2(tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
                                    capsys: pytest.CaptureFixture[str]) -> None:
    # exit 1 means "stale", so a file that is not UTF-8 must not exit 1
    (tmp_path / "en.toml").write_bytes(b"schema = 1\n\xff\n")
    with pytest.raises(build.VocabError, match="UTF-8"):
        build.read_dir(tmp_path)
    read_dir = build.read_dir
    monkeypatch.setattr(build, "read_dir", lambda: read_dir(tmp_path))
    assert build.main(["--check"]) == 2
    assert "UTF-8" in capsys.readouterr().err


def test_an_empty_word_is_a_usage_error() -> None:
    query = _load_query()
    with pytest.raises(SystemExit) as e:
        query.main(["--word", "."])
    assert e.value.code == 2


@pytest.mark.parametrize(("layout", "message"), [
    ({}, "no vocabulary files"),
    ({"EN.TOML": OK}, "BCP 47 tag"),          # misnamed files are read, then refused
    ({"en.toml.orig": OK}, "BCP 47 tag"),
    ({"readme.md": OK}, "BCP 47 tag"),        # only README.md, by its exact name, is skipped
    ({"README.md": OK}, "no vocabulary files"),
    ({"sub/en.toml": OK}, "no subfolders"),
    ({"en.toml": "->nowhere.toml"}, "a link to nothing"),
])
def test_the_folder_is_read_whole(tmp_path: Path, layout: dict[str, str], message: str) -> None:
    for name, text in layout.items():
        (tmp_path / name).parent.mkdir(parents=True, exist_ok=True)
        if text.startswith("->"):
            (tmp_path / name).symlink_to(tmp_path / text[2:])
        else:
            (tmp_path / name).write_text(text, encoding="utf-8")
    (tmp_path / ".DS_Store").write_bytes(b"\x00")  # a dotfile is ignored, never read
    with pytest.raises(build.VocabError, match=message):
        build.compile_files(build.read_dir(tmp_path))
    with pytest.raises(build.VocabError, match="no vocabulary folder"):
        build.read_dir(tmp_path / "missing")


def _point_at(monkeypatch: pytest.MonkeyPatch, tmp_path: Path, files: dict[str, str]) -> None:
    folder = tmp_path / "vocab"
    folder.mkdir()
    for name, text in files.items():
        (folder / name).write_text(text, encoding="utf-8")
    read_dir = build.read_dir
    monkeypatch.setattr(build, "read_dir", lambda: read_dir(folder))
    monkeypatch.setattr(build, "ROOT", tmp_path)
    monkeypatch.setattr(build, "OUTPUT", tmp_path / "_compiled.py")


def test_no_error_exits_1_the_code_for_stale(tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
                                             capsys: pytest.CaptureFixture[str]) -> None:
    _point_at(monkeypatch, tmp_path, {"en.toml": OK})
    # an unreadable module is stale: rebuilding replaces it
    build.OUTPUT.write_bytes(b"\xff")
    assert build.main(["--check"]) == 1
    assert "unreadable" in capsys.readouterr().out
    assert build.main([]) == 0
    assert build.main(["--check"]) == 0
    # a module that cannot be written is an internal error, exit 3
    build.OUTPUT.unlink()
    build.OUTPUT.mkdir()
    assert build.main([]) == 3


def test_a_warning_raised_as_an_error_exits_2(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    # a soft finding raised under -W error is a data error, not a bug
    _point_at(monkeypatch, tmp_path, {"en.toml": _w('[[word]]\ntext = "smith"\nfamily = {}')})
    with warnings.catch_warnings():
        warnings.simplefilter("error")
        assert build.main(["--check"]) == 2


def test_a_repointed_root_does_not_move_the_lexicon_module(tmp_path: Path,
                                                           monkeypatch: pytest.MonkeyPatch) -> None:
    # the tests above repoint ROOT at a fixture tree holding no
    # _lexicon.py; a cold cache must still load the parser's own, or
    # each of them passes only after another test has warmed it
    monkeypatch.setattr(build, "_LEXICON", [])
    monkeypatch.setattr(build, "ROOT", tmp_path)
    assert build._normalize(" Dr. ") == "dr"


def test_a_broken_lexicon_module_exits_3(monkeypatch: pytest.MonkeyPatch) -> None:
    def broken() -> ModuleType:
        raise SyntaxError("conflict markers")
    monkeypatch.setattr(build, "_LEXICON", [])
    monkeypatch.setattr(build, "_load_lexicon_module", broken)
    assert build.main(["--check"]) == 3


def test_a_query_error_exits_3_not_1(monkeypatch: pytest.MonkeyPatch) -> None:
    query = _load_query()
    def broken(*args: object, **kwargs: object) -> list[object]:
        raise KeyError("a bug in select")
    monkeypatch.setattr(query, "select", broken)
    assert query.main(["--word", "dr"]) == 3


def test_a_satisfied_property_exclusion_does_not_claim_the_refusal() -> None:
    # suffix = { acronym = true } is what a credential's acronym exclusion
    # keeps, so the exclusion has nothing to say; the word is still
    # refused, by check 4, for having two suffix kinds -- and the message
    # must not read backwards, calling acronym = true the refused value
    files = {"en.toml": _w('[[word]]\ntext = "xyz"\ncredential = { excluded = { acronym = "keep acronym" } }'),
             "fr.toml": _w('[[word]]\ntext = "xyz"\nsuffix = { acronym = true }')}
    with pytest.raises(build.VocabError, match="one suffix kind per word") as e:
        _compile(files)
    assert "is excluded" not in str(e.value)



# ------------------------------------------------- the README's reference
# nameparser/vocab/README.md documents the kinds and properties for
# whoever edits the TOML. Its tables are held to the names build.py
# accepts, each kind's compiled sets and each behavioral property's
# effect to what the compiler does with a probe reading, and each
# property's unwritten value to the default the compiler gives it.
def _readme_table(heading: str) -> list[list[str]]:
    """The rows of the first table under `heading`, header and divider
    dropped, each a list of its cells. A cell may hold an escaped pipe
    (GFM's `\\|`), and every row has as many cells as the header."""
    lines = (build.VOCAB / build.README).read_text(encoding="utf-8").splitlines()
    assert heading in lines, f"README.md has no {heading!r} heading"
    rows: list[list[str]] = []
    for line in lines[lines.index(heading) + 1:]:
        if line.startswith("#"):
            break
        if line.startswith("|"):
            line = line.strip()
            assert line.endswith("|"), f"{heading}: unterminated row {line!r}"
            rows.append([c.strip() for c in re.split(r"(?<!\\)\|", line[1:-1])])
        elif rows:
            break
    assert len(rows) > 2, f"no table under {heading!r}"
    for row in rows:
        assert len(row) == len(rows[0]), f"{heading}: {row} has {len(row)} cells"
    return rows[2:]


def _code(cell: str) -> list[str]:
    return re.findall(r"`([^`]+)`", cell)


def _sets_fed(kind: str, props: str = "{}", text: str = "zzq") -> set[str]:
    """The compiled constants a one-word file holding a `kind` reading
    with `props` puts the word into (a particle states may_be_given)."""
    if build.CATEGORY.get(kind) == "particle" and "may_be_given" not in props:
        props = "{ may_be_given = true }"
    files = {"en.toml": _w(f'[[word]]\ntext = "{text}"\n{kind} = {props}')}
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", build.VocabWarning)  # a name reading is inert
        compiled = build.compile_files(files)
    return {name for name, value in compiled.items() if text in value}


#: For each behavioral property, a reading that sets it away from its
#: unwritten value (kind, props, text): what that changes in the compiled
#: sets, against the same kind written bare, is the property's effect.
_PROPERTY_PROBES = {
    "addresses": ("title", '{ addresses = "given" }', "zzq"),
    "acronym": ("generation", "{ acronym = true }", "zzq"),
    "may_be_name": ("credential", "{ may_be_name = true }", "zzq"),
    "attached": ("honorific", '{ attached = { side = "after" } }', "zzq"),
    "may_be_given": ("particle", "{ may_be_given = false }", "zzq"),
    "may_be_initial": ("conjunction", "{ may_be_initial = true }", "q"),
    "cased": ("title", '{ cased = "ZzQ" }', "zzq"),
    "after_given": ("salutation", "{ after_given = true }", "zzq"),
}
#: The behavioral properties the build refuses to leave unwritten.
_REQUIRED = {"may_be_given"}


@pytest.mark.parametrize("kind", [k for k, c in build.CATEGORY.items() if c == "title"])
def test_every_title_kind_compiles_its_behavioral_properties(kind: str) -> None:
    # GIVEN_NAME_TITLES is compiled by category, so a classified title
    # keeps addresses (#750): keyed on the generic kind, a nobility sir
    # would lose it; and every title kind is allowed `cased`, which the
    # compiler reads from any reading
    assert _sets_fed(kind, '{ addresses = "given" }') == {"TITLES", "GIVEN_NAME_TITLES"}
    files = {"en.toml": _w(f'[[word]]\ntext = "zzq"\n{kind} = {{ cased = "ZzQ" }}')}
    assert build.compile_files(files)["CAPITALIZATION_EXCEPTIONS"] == {"zzq": "ZzQ"}


def test_the_readme_lists_every_kind_with_its_category_and_set() -> None:
    rows = _readme_table("## Kinds")
    # in CATEGORY's order, which is check 10's canonical order of the kinds
    assert [(_code(r[0])[0], _code(r[1])[0]) for r in rows] == list(build.CATEGORY.items())
    for kind, _, fed in rows:
        assert set(_code(fed)) == _sets_fed(_code(kind)[0]), kind


def test_the_readme_lists_every_property_with_its_type_and_categories() -> None:
    rows = _readme_table("## Properties")
    behavioral = {p for ps in build.BEHAVIORAL.values() for p in ps}
    assert {_code(r[0])[0]: r[1] for r in rows} == (
        {p: "behavioral" for p in behavioral} | {p: "descriptive" for p in build.DESCRIPTIVE})
    assert len(rows) == len(behavioral | build.DESCRIPTIVE)
    for prop, kind_of, applies, *_ in rows:
        name = _code(prop)[0]
        if kind_of == "behavioral":
            assert set(_code(applies)) == {
                c for c, ps in build.BEHAVIORAL.items() if name in ps}, name
        else:
            # a name reading takes only the descriptive keys in NAME_KEYS
            assert ("but `name`" in applies) == (name not in build.NAME_KEYS), name


def test_the_readme_states_each_behavioral_propertys_effect() -> None:
    rows = {_code(r[0])[0]: r[4] for r in _readme_table("## Properties") if r[1] == "behavioral"}
    assert set(_PROPERTY_PROBES) == set(rows)
    for prop, (kind, props, text) in _PROPERTY_PROBES.items():
        bare = "{ may_be_given = true }" if kind == "particle" else "{}"
        moved = _sets_fed(kind, props, text) ^ _sets_fed(kind, bare, text)
        assert moved, prop  # a probe that moves nothing tests nothing
        assert set(_code(rows[prop])) & {n for n, _ in build.CONSTANTS} == moved, prop


def test_the_readme_states_each_behavioral_propertys_unwritten_value() -> None:
    for row in _readme_table("## Properties"):
        prop, kind_of, _, unwritten = _code(row[0])[0], row[1], row[2], row[3]
        if kind_of != "behavioral":
            continue
        if prop in _REQUIRED:
            assert "required" in unwritten, prop
            continue
        defaults = {build._behavior(build.Reading("en.toml", "zzq", kind, {}), prop)
                    for kind, cat in build.CATEGORY.items()
                    if prop in build.BEHAVIORAL.get(cat, ())}
        for value in defaults:
            if isinstance(value, bool):
                assert ("true" if value else "false") in unwritten, prop
            elif isinstance(value, str):
                assert f'"{value}"' in unwritten, prop
            else:
                assert value is None and not {"true", "false"} & set(unwritten.split()), prop


def test_the_readme_names_every_compiled_constant() -> None:
    # each constant is reached by a kind or by a behavioral property
    named = {name for heading in ("## Kinds", "## Properties")
             for row in _readme_table(heading) for cell in row[1:] for name in _code(cell)}
    assert {name for name, _ in build.CONSTANTS} <= named


def test_the_readme_lists_the_name_reading_keys() -> None:
    rows = _readme_table("### Name readings")
    assert {_code(r[0])[0] for r in rows} == build.NAME_KEYS
    assert len(rows) == len(build.NAME_KEYS)


def test_the_readme_lists_the_reserved_names_with_their_phases() -> None:
    rows = _readme_table("## Names reserved for later phases")
    assert {_code(r[0])[0]: int(r[1]) for r in rows} == build.RESERVED
    assert len(rows) == len(build.RESERVED)
