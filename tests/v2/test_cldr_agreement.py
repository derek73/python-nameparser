"""The agreement ratchets, and the comparison rules they rest on.

tools/differential/cldr_agreement.py decides, for each rendering and
each role, whether nameparser agrees with the source's stated fields
(CLDR's, and the GND's, Wikidata's and the conventions table's written
in CLDR's vocabulary). The rules
are pinned here first, each with the wrong answer the plausible
alternative gives recorded beside it; the ratchet test at the end then
holds each source's corpus to its recorded disagreements in
tools/differential/, one record per source.

tools/ is not a package, so the module is loaded by path, as
_differential_fixtures.py loads compare.py.
"""
import contextlib
import functools
import importlib.util
import io
import json
import sys
from collections import Counter
from pathlib import Path
from types import ModuleType
from typing import Any

import pytest

from nameparser import locales, parse

_TOOLS = Path(__file__).parents[2] / "tools" / "differential"


def _load() -> ModuleType:
    spec = importlib.util.spec_from_file_location(
        "cldr_agreement", _TOOLS / "cldr_agreement.py")
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


agreement = _load()


@pytest.mark.parametrize(("value", "text", "result"), [
    ("Falke", "Falke, Iris", True),          # commas stripped from the tokens
    ("Anna Cornelia", "Prof. Anna Cornelia Wolf", True),
    # Token containment, not substring: the substring rule says True here
    # and would expect a surname the rendering dropped.
    ("Wolf", "Wolfgang Smith", False),
    ("佐藤", "佐藤グレース恵子", True),        # unspaced: substring
    ("中村", "中村　敬子", True),          # ideographic space is a space
    # A no-break space is a space too. Treated as "no space", the text
    # falls to substring rules and finds `Ann` inside `Anna`.
    ("Ann", "Anna Smith", False),
    ("", "Iris Falke", False),               # an empty field is never present
])
def test_occurs(value: str, text: str, result: bool) -> None:
    assert agreement.occurs(value, text) is result


def test_expected_roles_drop_fields_the_rendering_omits() -> None:
    # Spanish given-first omits the second surname and the title stays.
    fields = {"title": "Sr.", "given": "Miguel Ángel", "given2": "Juan Antonio",
              "surname-core": "Pablo", "surname2": "Pérez", "generation": "II"}
    roles = agreement.expected_roles(fields, "Sr. Miguel Ángel Juan Antonio Pablo II")
    assert roles == {"title": "Sr.", "given_names": "Miguel Ángel Juan Antonio",
                     "family": "Pablo", "suffix": "II",
                     "family_particles": "", "family_base": "Pablo",
                     # stated, so expected empty where the rendering omits it
                     "surname2": ""}


def test_a_pending_field_is_scored_inside_its_merged_role_until_parsed_name_has_it(
        ) -> None:
    # surname2 inside family, as CLDR merges it; a patronymic inside
    # given_names, never family -- so an Icelandic name expects no family.
    text = "Vigdís Finnbogadóttir"
    roles = agreement.expected_roles({"given": "Vigdís",
                                      "patronymic": "Finnbogadóttir"}, text)
    assert (roles["given_names"], roles["family"]) == (text, "")
    assert roles["patronymic"] == "Finnbogadóttir"
    roles = agreement.expected_roles(
        {"given": "Gabriel", "surname": "García", "surname2": "Márquez"},
        "Gabriel García Márquez")
    assert (roles["family"], roles["surname2"]) == ("García Márquez", "Márquez")
    # Not scored on its own while ParsedName lacks the attribute ...
    assert "surname2" not in agreement.got_roles(parse("Gabriel García Márquez"))
    rows = [{"file": "Q1", "label": "x", "order": "givenFirst", "shape": None,
             "text": "Gabriel García Márquez",
             "fields": {"given": "Gabriel", "surname": "García",
                        "surname2": "Márquez"}}]
    assert "surname2" not in agreement.disagreements(rows).get("Q1/x/givenFirst", {})


@pytest.mark.parametrize("field", sorted(agreement.PENDING_ROLES))
def test_each_pending_field_is_scored_inside_the_role_it_names(field: str) -> None:
    # PENDING_ROLES names the merged role; expected_roles must agree.
    roles = agreement.expected_roles({"given": "Ana", "surname": "Ruiz", field: "Vila"},
                                     "Ana Vila Ruiz")
    merged = agreement.PENDING_ROLES[field]
    assert "Vila" in roles[merged].split()
    assert not [r for r in ("given_names", "family") if r != merged
                and "Vila" in roles[r].split()]


@functools.cache
def _summary_run(*args: str) -> tuple[int, str]:
    """One `main(args)` run and what it printed, shared by the tests that
    read the summary: each run scores every source (about 0.7 s)."""
    out = io.StringIO()
    with contextlib.redirect_stdout(out):
        code = agreement.main(list(args))
    return code, out.getvalue()


def test_the_summary_says_where_each_pending_field_is_scored() -> None:
    _, out = _summary_run()
    assert "patronymic" in out and "(scored inside given_names)" in out
    assert "(scored inside family)" in out


def test_a_role_parsed_name_stops_answering_still_fails_loudly(
        monkeypatch: pytest.MonkeyPatch) -> None:
    # Only a PENDING_ROLES field may go unanswered; any other gap is a bug.
    rows = [{"file": "Q1", "label": "x", "order": "givenFirst", "shape": None,
             "text": "Ana Ruiz", "fields": {"given": "Ana", "surname": "Ruiz"}}]
    real = agreement.got_roles
    monkeypatch.setattr(agreement, "got_roles", lambda name: {
        k: v for k, v in real(name).items() if k != "family"})
    with pytest.raises(KeyError):
        agreement.disagreements(rows)


def test_a_pending_field_is_scored_once_parsed_name_answers_it() -> None:
    class WithSurname2:
        title = given_names = suffix = family_particles = family_base = ""
        family = "García Márquez"
        surname2 = "García"
    assert agreement.got_roles(WithSurname2())["surname2"] == "García"  # type: ignore[arg-type]


def test_an_honorific_is_scored_inside_the_suffix() -> None:
    """A word of address written after the name (the conventions
    source's `honorific`, #686) is a suffix, as nameparser reads さん."""
    roles = agreement.expected_roles({"given": "Murat", "honorific": "Bey"}, "Murat Bey")
    assert roles["suffix"] == "Bey"
    assert roles["title"] == ""
    assert roles["given_names"] == "Murat"
    assert roles["family"] == ""


def test_a_field_no_rule_reads_raises() -> None:
    """A mistyped field would be expected in no role, and a row holding
    it would pass as agreeing with an empty parse."""
    with pytest.raises(ValueError, match="honorfic"):
        agreement.expected_roles({"given": "Murat", "honorfic": "Bey"}, "Murat Bey")


def test_expected_roles_compare_particles_only_where_cldr_splits_them() -> None:
    plain = agreement.expected_roles({"given": "Iris", "surname": "Falke"}, "Iris Falke")
    assert set(plain) == {"title", "given_names", "family", "suffix"}
    split = agreement.expected_roles(
        {"given": "Paul", "surname-prefix": "von", "surname-core": "Fischer"},
        "Paul von Fischer")
    assert (split["family"], split["family_particles"], split["family_base"]) == (
        "von Fischer", "von", "Fischer")


def test_expected_roles_count_a_word_shared_by_two_fields_in_both() -> None:
    roles = agreement.expected_roles(
        {"given": "Syed Sadiq", "surname": "Syed Hassan"}, "Syed Sadiq Syed Hassan")
    assert (roles["given_names"], roles["family"]) == ("Syed Sadiq", "Syed Hassan")


@pytest.mark.parametrize(("expected", "got", "text", "result"), [
    ("Pablo Pérez", "Pérez Pablo", "Pablo Pérez Miguel", True),  # order-free
    ("Pablo", "Pablo Pérez", "Pablo Pérez Miguel", False),       # a word too many
    ("", "", "Iris Falke", True),          # absent on both sides agrees
    ("", "Dr.", "Dr. Iris Falke", False),  # an invented title disagrees
    ("jr. MdB", "jr., MdB", "Paul Fischer jr., MdB", True),     # commas ignored
    ("민규 헨리", "민규헨리", "김민규헨리", True),                  # unspaced text
])
def test_same(expected: str, got: str, text: str, result: bool) -> None:
    assert agreement.same(expected, got, text) is result


def test_got_roles_reads_the_six_views() -> None:
    roles = agreement.got_roles(parse("Dr. Paul von Fischer Jr."))
    assert roles == {"title": "Dr.", "given_names": "Paul", "family": "von Fischer",
                     "suffix": "Jr.", "family_particles": "von",
                     "family_base": "Fischer"}
    assert tuple(roles) == agreement.ROLES


def _row(text: str, shape: int | None, **fields: str) -> dict[str, object]:
    return {"file": "xx", "label": "nativeG", "order": "givenFirst",
            "text": text, "shape": shape, "fields": fields}


def test_a_shape_4_rendering_is_parsed_family_first() -> None:
    # The recorder and the checker share parse_rendering, so they cannot
    # parse a rendering two ways. A lone word under FAMILY_FIRST reads as
    # the family name, so CLDR's given name disagrees -- by design.
    found = agreement.disagreements([_row("Lena", 4, given="Lena")])
    assert found == {"xx/nativeG/givenFirst": {
        "text": "Lena", "given_names": {"expected": "Lena", "got": ""},
        "family": {"expected": "", "got": "Lena"}}}
    assert agreement.disagreements([_row("Lena", None, given="Lena")]) == {}


_RECORDED = {"a/nativeG/givenFirst": {"text": "A", "family": {"expected": "X", "got": "Y"}},
             "b/nativeG/givenFirst": {"text": "B", "title": {"expected": "", "got": "Dr."}}}


def test_changes_is_empty_when_nothing_moved() -> None:
    assert agreement.changes(_RECORDED, _RECORDED, set(_RECORDED)) == []


def test_changes_reports_a_regression() -> None:
    current = {**_RECORDED, "c/nativeG/givenFirst": {
        "text": "C", "family": {"expected": "Z", "got": ""}}}
    [message] = agreement.changes(_RECORDED, current, set(current))
    assert message.startswith("regression: c/nativeG/givenFirst family")


def test_changes_reports_progress_that_must_be_recorded() -> None:
    current = {"a/nativeG/givenFirst": _RECORDED["a/nativeG/givenFirst"]}
    [message] = agreement.changes(_RECORDED, current, set(_RECORDED))
    assert message.startswith("progress: b/nativeG/givenFirst title")


def test_changes_reports_a_changed_wrong_answer() -> None:
    current = {**_RECORDED, "a/nativeG/givenFirst": {
        "text": "A", "family": {"expected": "X", "got": "W"}}}
    [message] = agreement.changes(_RECORDED, current, set(current))
    assert message.startswith("changed: a/nativeG/givenFirst family")
    assert "'Y'" in message and "'W'" in message


def test_changes_reports_a_rendering_that_is_gone() -> None:
    # A rebuild that drops a rendering is not progress.
    [message] = agreement.changes(
        _RECORDED, {"a/nativeG/givenFirst": _RECORDED["a/nativeG/givenFirst"]},
        {"a/nativeG/givenFirst"})
    assert message.startswith("gone: b/nativeG/givenFirst")


#: Each source's corpus file, and a floor its distinct texts must
#: exceed: a truncated file would otherwise pass both checks below, and
#: an emptied one re-recorded would match its emptied record.
_CORPORA = {"CLDR": ("corpus_cldr.jsonl", 1000), "GND": ("corpus_gnd.jsonl", 500),
            "Wikidata": ("corpus_wikidata.jsonl", 500),
            "Conventions": ("corpus_conventions.jsonl", 25),
            "Wikidata native": ("corpus_wikidata_native.jsonl", 700)}
#: Sources whose fields file states only some of its corpus's names: the
#: conventions table leaves a row without fields where no field can state
#: it, and says why in the row's `unstated`.
_PARTIAL = frozenset({"Conventions"})


def test_every_source_has_a_corpus_file() -> None:
    assert set(_CORPORA) == set(agreement.sources())


@pytest.mark.parametrize("source", sorted(_CORPORA))
def test_the_fields_file_holds_the_corpus_renderings(source: str) -> None:
    fields, _ = agreement.sources()[source]
    corpus, least = _CORPORA[source]
    from_fields = {(row["text"], row["shape"]) for row in agreement.load_rows(fields)}
    from_corpus = set()
    for line in (_TOOLS / corpus).read_text(encoding="utf-8").splitlines():
        if line.strip():
            entry = json.loads(line)
            from_corpus.add((entry, None) if isinstance(entry, str)
                            else (entry["name"], entry["shape"]))
    if source in _PARTIAL:
        assert from_fields <= from_corpus
    else:
        assert from_corpus == from_fields
    assert len(from_fields) > least, f"the {source} corpus is missing or truncated"


@pytest.mark.parametrize("source", sorted(set(_CORPORA) - {"CLDR"}))
def test_every_committed_field_occurs_in_its_rendering(source: str) -> None:
    # A field that did not occur would be expected EMPTY by the
    # comparison, a disagreement no parser fix could resolve. CLDR is
    # exempt by design: its formats drop fields by locale and order, and
    # it states fields (locale, given-informal) no rendering writes.
    fields, _ = agreement.sources()[source]
    missing = [(row["text"], value) for row in agreement.load_rows(fields)
               for value in row["fields"].values()
               if not agreement.occurs(value, row["text"])]
    assert not missing


@pytest.mark.parametrize("source", sorted(set(_CORPORA) - {"CLDR"}))
def test_the_fields_partition_their_rendering(source: str) -> None:
    """Every word of a rendering is stated by exactly one field, so a part
    left out is a failure here rather than an expectation of empty. CLDR
    is exempt for the reason above; the other sources' builders claim
    every word, and the conventions table is written to."""
    fields, _ = agreement.sources()[source]
    bad = []
    for row in agreement.load_rows(fields):
        values = list(row["fields"].values())
        if agreement._has_space(row["text"]):
            ok = (Counter(w for v in values for w in agreement._words(v))
                  == Counter(agreement._words(row["text"])))
        else:
            ok = (sum(len(agreement._squash(v)) for v in values)
                  == len(agreement._squash(row["text"])))
        if not ok:
            bad.append((row["text"], row["fields"]))
    assert not bad


@pytest.mark.parametrize("source", sorted(_CORPORA))
def test_nameparser_still_agrees_with_each_source_where_it_did(source: str) -> None:
    fields, record = agreement.sources()[source]
    rows = agreement.load_rows(fields)
    problems = agreement.changes(
        agreement.read_record(record), agreement.disagreements(rows),
        {agreement.rendering_key(row) for row in rows})
    assert not problems, "\n".join([
        *problems[:40],
        f"{len(problems)} change(s) against tools/differential/{record.name}.",
        f"If every one is intended, re-record with `{agreement.RECORD_COMMAND}` "
        "and say why in the commit."])


def test_the_summary_counts_each_role_and_matches_the_record() -> None:
    code, out = _summary_run()
    assert code == 0, out
    for role in agreement.ROLES:
        assert any(line.split()[0] == role and "agree" in line
                   for line in out.splitlines() if line.strip()), role
    for source in agreement.sources():
        assert f"{source} view matches the record" in out
    for source in agreement.locale_sources():
        assert f"{source} locale view matches the record" in out
    # each locale view prints its own default count, not another source's
    native = out.split("Wikidata native locale view", 1)[1]
    rows = agreement.load_rows(agreement.NATIVE_FIELDS)
    wrong = agreement.disagreements(rows)
    zh = agreement.locale_rows(rows, agreement.locale_sources()["Wikidata native"], "ZH")
    before = sum(agreement.rendering_key(r) not in wrong for r in zh)
    assert f"ZH     zh-cn, zh-tw: {before}/{len(zh)} default" in native


@pytest.mark.parametrize("text", [
    "ستوبر، زيزينيا هاميش",   # Arabic comma, as nameparser's COMMA_CHARS has
    "Smith， John",            # fullwidth comma glued to the word
])
def test_a_word_beside_a_non_ascii_comma_still_occurs(text: str) -> None:
    # Only ',' was stripped at first, so the word glued to the comma did
    # not occur and CLDR's field was expected empty -- a false
    # disagreement the parser could never resolve.
    first = text.split()[0].rstrip("،，")
    assert agreement.occurs(first, text)


def test_an_unspaced_role_is_expected_in_text_order() -> None:
    # CLDR's field order is given, given2; this rendering writes given2
    # first. Joined in field order, the parser's correct 'ローズ セシリア'
    # disagreed with 'セシリア ローズ'.
    roles = agreement.expected_roles(
        {"given": "セシリア", "given2": "ローズ", "surname": "ブラウン"},
        "ブラウン・ローズ・セシリア")
    assert agreement.same(roles["given_names"], "ローズ セシリア", "ブラウン・ローズ・セシリア")


# -- the locale view (#672) --------------------------------------------------

def test_every_locale_pack_is_measured_or_listed_as_having_no_cldr_file() -> None:
    # A new pack must add its CLDR files to LOCALE_FILES or say it has
    # none; otherwise it goes unmeasured by omission.
    mapped = set(agreement.LOCALE_FILES.values())
    assert not mapped & agreement.NO_CLDR
    assert mapped | agreement.NO_CLDR == {code.upper() for code in locales.available()}


def test_every_mapped_cldr_file_and_native_stratum_has_renderings() -> None:
    # A misspelled file or stratum in the tables would measure nothing and pass.
    assert set(agreement.LOCALE_FILES) <= {row["file"] for row in agreement.load_rows()}
    native = agreement.load_rows(agreement.NATIVE_FIELDS)
    assert set(agreement.NATIVE_LABELS) <= {row["label"] for row in native}


_CLDR, _NATIVE = (agreement.locale_sources()[name] for name in ("CLDR", "Wikidata native"))
_ZH_ROW = {"file": "Q1", "label": "zh-cn", "order": "surnameFirst",
           "text": "王小明", "shape": None, "fields": {"surname": "王", "given": "小明"}}


def test_the_locale_view_parses_with_the_pack() -> None:
    # A view that fell back to the default parser would record the
    # default's disagreements and still pass its own ratchet. 王小明 is
    # one unspaced Han token: only ZH segments it.
    assert agreement.disagreements([_ZH_ROW], "ZH") == {}
    assert agreement.disagreements([_ZH_ROW]) != {}


def test_each_source_finds_a_renderings_pack_in_its_own_key() -> None:
    # CLDR by its file, the native-script source by its stratum: a QID
    # names no language, and a CLDR label names no stratum.
    assert _CLDR.pack_of("zh/nativeG/givenFirst") == "ZH"
    assert _NATIVE.pack_of("Q1/zh-cn/surnameFirst") == "ZH"
    assert _NATIVE.pack_of("Q1/ja-jp/surnameFirst") == "JA"
    assert _NATIVE.pack_of("Q1/ko-kr/surnameFirst") is None
    assert _CLDR.pack_of("Q1/zh-cn/surnameFirst") is None
    assert agreement.locale_rows([_ZH_ROW], _NATIVE, "ZH") == [_ZH_ROW]


def test_a_pack_parser_keeps_the_family_first_order_of_its_shape() -> None:
    # Latin text: no script decides the order, so only the FAMILY_FIRST
    # base the pack is applied over can read Ivanov as the family.
    name = agreement.parse_rendering("Ivanov Ivan", 4, "RU")
    assert (name.family, name.given) == ("Ivanov", "Ivan")


def test_a_recorded_entry_no_pack_reads_is_reported_gone() -> None:
    # No pack's check reads such an entry, so without this it would sit
    # in the record unguarded -- and survive every re-record.
    [message] = agreement.unmapped({"zh/nativeG/givenFirst": {}, "xx/nativeG/sorting": {}},
                                   _CLDR)
    assert message.startswith("gone: xx/nativeG/sorting")
    [message] = agreement.unmapped({"Q1/zh-cn/surnameFirst": {},
                                    "Q2/xx-yy/surnameFirst": {}}, _NATIVE)
    assert message.startswith("gone: Q2/xx-yy/surnameFirst")
    for name, source in agreement.locale_sources().items():
        assert agreement.unmapped(agreement.read_record(source.record), source) == [], name


def test_a_recorded_rendering_that_is_gone_is_reported_by_its_packs_check() -> None:
    recorded: dict[str, dict[str, Any]] = {"Q2/zh-cn/surnameFirst": {"text": "王"}}
    [message] = agreement.locale_changes([_ZH_ROW], _NATIVE, "ZH", recorded)
    assert message.startswith("gone: Q2/zh-cn/surnameFirst")


def _redirect(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> dict[str, Any]:
    """Point every record, each source's and each locale one, into
    tmp_path through sources() and locale_sources() themselves, so a
    source added later cannot be written into the tree by a test."""
    redirected = {name: (fields, tmp_path / f"{name}.json")
                  for name, (fields, _) in agreement.sources().items()}
    redirected_locale = {name: source._replace(record=tmp_path / f"{name}.locales.json")
                         for name, source in agreement.locale_sources().items()}
    monkeypatch.setattr(agreement, "sources", lambda: redirected)
    monkeypatch.setattr(agreement, "locale_sources", lambda: redirected_locale)
    return redirected_locale


def test_a_re_record_drops_entries_no_pack_reads(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    # The carry-over that keeps an unmeasured pack's entries must not
    # keep an unmapped file's too.
    real, real_locale = agreement.sources(), agreement.locale_sources()
    record = _redirect(tmp_path, monkeypatch)["CLDR"].record
    agreement.write_record({"xx/nativeG/sorting": {"text": "X"}}, record)
    assert agreement.main(["--record"]) == 0
    assert "xx/nativeG/sorting" not in agreement.read_record(record)
    # and the re-record wrote every source's record, not CLDR's alone, and
    # every locale record: each its committed record's measured packs (an
    # unmeasured pack's entries are carried over only from the old record,
    # which here holds none of them)
    for name, (_, written) in agreement.sources().items():
        assert agreement.read_record(written) == agreement.read_record(real[name][1]), name
    for name, source in agreement.locale_sources().items():
        committed = real_locale[name]
        measured = {k: v for k, v in agreement.read_record(committed.record).items()
                    if agreement.pack_available(committed.pack_of(k) or "")}
        assert agreement.read_record(source.record) == measured, name


def test_every_locale_record_is_read() -> None:
    # Dropping a source from locale_sources() would leave its committed
    # record read by nothing, and its rows' ratchet would simply vanish
    # from the parametrization.
    records = {source.record.name for source in agreement.locale_sources().values()}
    assert records == {path.name for path in _TOOLS.glob("*_agreement_locales.json")}
    assert set(agreement.locale_sources()) <= set(agreement.sources())


@pytest.mark.parametrize("source", sorted(agreement.locale_sources()))
def test_a_re_record_keeps_an_unmeasured_packs_entries(
        source: str, tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture[str]) -> None:
    # Without the ja extra, --record must carry the JA entries over, or a
    # run without it would erase them and only CI's ja-extra job would see.
    committed = agreement.locale_sources()[source]
    redirected = committed._replace(record=tmp_path / committed.record.name)
    redirected.record.write_text(committed.record.read_text(encoding="utf-8"),
                                 encoding="utf-8")
    monkeypatch.setattr(agreement, "_EXTRAS", {"JA": "a_module_that_is_not_installed"})
    rows = agreement.load_rows(agreement.sources()[source][0])
    agreement._record_locale(source, rows, redirected)
    old, new = agreement.read_record(committed.record), agreement.read_record(redirected.record)
    kept = {k: v for k, v in old.items() if committed.pack_of(k) == "JA"}
    assert kept, f"{source} records no JA entry: the carry-over is not exercised"
    assert {k: v for k, v in new.items() if committed.pack_of(k) == "JA"} == kept
    assert "JA not measured" in capsys.readouterr().out


def test_the_summary_still_checks_a_pack_with_no_renderings_left(
        capsys: pytest.CaptureFixture[str]) -> None:
    # Its recorded entries are gone, and must be reported as such.
    rows = [r for r in agreement.load_rows()
            if _CLDR.pack_of(agreement.rendering_key(r)) != "ZH"]
    problems = agreement._locale_summary("CLDR", rows, _CLDR, {})
    assert problems and all(p.startswith("gone:") for p in problems)


@pytest.mark.parametrize(("source", "pack"), [
    pytest.param(source, pack, marks=pytest.mark.skipif(
        not agreement.pack_available(pack),
        reason=f"needs {agreement._EXTRAS.get(pack)}; CI's ja-extra job runs it"))
    for source in sorted(agreement.locale_sources())
    for pack in agreement._packs()])
def test_each_pack_still_agrees_with_each_source_where_it_did(source: str, pack: str) -> None:
    locale = agreement.locale_sources()[source]
    problems = agreement.locale_changes(
        agreement.load_rows(agreement.sources()[source][0]), locale, pack,
        agreement.read_record(locale.record))
    assert not problems, "\n".join([
        *problems[:40],
        f"{len(problems)} change(s) against "
        f"tools/differential/{locale.record.name} for {pack}.",
        f"If every one is intended, re-record with `{agreement.RECORD_COMMAND}` "
        "and say why in the commit."])


def test_the_split_view_reports_a_compound_given_name_the_merged_role_passes() -> None:
    # #702: Kim Min Ho reads given Min, middle Ho; the merged role agrees.
    row = _row("Kim Min Ho", 4, given="Min Ho", surname="Kim")
    assert agreement.disagreements([row]) == {}
    assert agreement.split_disagreements([row]) == {"xx/nativeG/givenFirst": {
        "text": "Kim Min Ho", "given": {"expected": "Min Ho", "got": "Min"},
        "middle": {"expected": "", "got": "Ho"}}}
    # a split the source states and the parser reads the same way is silent
    agreed = _row("Ana Maria Ruiz", None, given="Ana", given2="Maria", surname="Ruiz")
    assert agreement.split_disagreements([agreed]) == {}


def test_the_split_view_skips_a_rendering_whose_merged_role_already_disagrees() -> None:
    # reported once, by the ratcheted role, not again by the split view
    row = _row("Kim Min Ho", 4, given="Zed Qux", surname="Kim")
    assert agreement.disagreements([row])
    assert agreement.split_disagreements([row]) == {}


def test_the_split_view_skips_a_rendering_that_states_a_patronymic() -> None:
    # the merged role holds the patronymic; the split has nowhere to put it
    text = "Anna Ivanovna Petrova"
    row = _row(text, None, given="Anna", patronymic="Ivanovna", surname="Petrova")
    assert agreement.parse_rendering(text, None).middle == "Ivanovna"
    assert agreement.split_disagreements([row]) == {}


def test_the_split_view_is_reported_for_exactly_the_sources_that_state_it() -> None:
    # GND and Wikidata record every given name in one field: never scored on it
    assert agreement.SPLIT_SOURCES == {"CLDR", "Conventions"}
    assert agreement.SPLIT_SOURCES <= set(agreement.sources())
    out = _summary_run()[1]
    assert {line.split(" given/middle split")[0] for line in out.splitlines()
            if "given/middle split" in line} == agreement.SPLIT_SOURCES
    assert "expected '" not in out  # no listing without --split


def test_split_lists_the_view_s_renderings() -> None:
    out = _summary_run("--split")[1]
    assert "conventions/Kim Min Ho/FAMILY_FIRST: 'Kim Min Ho': given expected " \
           "'Min Ho', got 'Min'" in out
