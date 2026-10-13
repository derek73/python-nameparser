"""The CLDR agreement ratchet, and the comparison rules it rests on.

tools/differential/cldr_agreement.py decides, for each CLDR rendering and
each role, whether nameparser agrees with CLDR's stated fields. The rules
are pinned here first, each with the wrong answer the plausible
alternative gives recorded beside it; the ratchet test at the end then
holds the whole corpus to the recorded disagreements in
tools/differential/cldr_agreement.json.

tools/ is not a package, so the module is loaded by path, as
_differential_fixtures.py loads compare.py.
"""
import importlib.util
import json
import sys
from pathlib import Path
from types import ModuleType

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
                     "family_particles": "", "family_base": "Pablo"}


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


def test_the_corpus_and_the_fields_file_hold_the_same_renderings() -> None:
    from_fields = {(row["text"], row["shape"]) for row in agreement.load_rows()}
    from_corpus = set()
    for line in (_TOOLS / "corpus_cldr.jsonl").read_text(encoding="utf-8").splitlines():
        if line.strip():
            entry = json.loads(line)
            from_corpus.add((entry, None) if isinstance(entry, str)
                            else (entry["name"], entry["shape"]))
    assert from_corpus == from_fields
    assert len(from_fields) > 1000, "the CLDR corpus is missing or truncated"


def test_nameparser_still_agrees_with_cldr_where_it_did() -> None:
    rows = agreement.load_rows()
    problems = agreement.changes(
        agreement.read_record(), agreement.disagreements(rows),
        {agreement.rendering_key(row) for row in rows})
    assert not problems, "\n".join([
        *problems[:40],
        f"{len(problems)} change(s) against tools/differential/cldr_agreement.json.",
        f"If every one is intended, re-record with `{agreement.RECORD_COMMAND}` "
        "and say why in the commit."])


def test_the_summary_counts_each_role_and_matches_the_record(
        capsys: pytest.CaptureFixture[str]) -> None:
    assert agreement.main([]) == 0
    out = capsys.readouterr().out
    for role in agreement.ROLES:
        assert any(line.split()[0] == role and "agree" in line
                   for line in out.splitlines() if line.strip()), role
    assert "matches the record" in out


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


def test_every_mapped_cldr_file_has_renderings() -> None:
    # A misspelled file in the table would measure nothing and pass.
    files = {row["file"] for row in agreement.load_rows()}
    assert set(agreement.LOCALE_FILES) <= files


def test_the_locale_view_parses_with_the_pack() -> None:
    # A view that fell back to the default parser would record the
    # default's disagreements and still pass its own ratchet. 王小明 is
    # one unspaced Han token: only ZH segments it.
    row = {"file": "zh", "label": "nativeG", "order": "surnameFirst",
           "text": "王小明", "shape": 4, "fields": {"surname": "王", "given": "小明"}}
    assert agreement.disagreements([row], locale=True) == {}
    assert agreement.disagreements([row]) != {}


def test_a_pack_parser_keeps_the_family_first_order_of_its_shape() -> None:
    # Latin text: no script decides the order, so only the FAMILY_FIRST
    # base the pack is applied over can read Ivanov as the family.
    name = agreement.parse_rendering("Ivanov Ivan", 4, "RU")
    assert (name.family, name.given) == ("Ivanov", "Ivan")


def test_a_recorded_entry_whose_file_left_the_table_is_reported_gone() -> None:
    # No pack's check reads such an entry, so without this it would sit
    # in the record unguarded -- and survive every re-record.
    [message] = agreement.unmapped({"zh/nativeG/givenFirst": {}, "xx/nativeG/sorting": {}})
    assert message.startswith("gone: xx/nativeG/sorting")
    assert agreement.unmapped(agreement.read_record(agreement.LOCALE_RECORD)) == []


def test_a_re_record_drops_entries_whose_file_left_the_table(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    # The carry-over that keeps an unmeasured pack's entries must not
    # keep an unmapped file's too.
    record = tmp_path / "locales.json"
    agreement.write_record({"xx/nativeG/sorting": {"text": "X"}}, record)
    monkeypatch.setattr(agreement, "LOCALE_RECORD", record)
    monkeypatch.setattr(agreement, "RECORD", tmp_path / "default.json")
    assert agreement.main(["--record"]) == 0
    assert "xx/nativeG/sorting" not in agreement.read_record(record)


@pytest.mark.parametrize("pack", [
    pytest.param(pack, marks=pytest.mark.skipif(
        not agreement.pack_available(pack),
        reason=f"needs {agreement._EXTRAS.get(pack)}; CI's ja-extra job runs it"))
    for pack in sorted(set(agreement.LOCALE_FILES.values()))])
def test_each_pack_still_agrees_with_cldr_where_it_did(pack: str) -> None:
    problems = agreement.locale_changes(
        agreement.load_rows(), pack, agreement.read_record(agreement.LOCALE_RECORD))
    assert not problems, "\n".join([
        *problems[:40],
        f"{len(problems)} change(s) against "
        f"tools/differential/cldr_agreement_locales.json for {pack}.",
        f"If every one is intended, re-record with `{agreement.RECORD_COMMAND}` "
        "and say why in the commit."])
