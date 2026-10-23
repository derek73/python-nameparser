"""Offline checks on tools/differential/local_agreement.py.

The score compares a parse of each filed display name with the boxes the
filer typed it into, so what these pin is the comparison's three
decisions (the fold, the suffix counted in the surname box, the title
box set aside as filer error), each beside the reading with the decision
off, and the record's refusals: no record, a record that is not one, a record of
another fetch or another scorer, and a corpus damaged under the stream. The names are invented.
"""
import hashlib
import json
import sys
import unicodedata
from pathlib import Path

import pytest

from nameparser import Parser

from ._differential_fixtures import load_tool, own_cache, plant_corpus

agreement = load_tool("local_agreement")
corpora = agreement.local_corpora
_PSC = corpora.PSC
_PSC_FIELDS = agreement.FIELDED[_PSC]
_LISTED = agreement._title_words(Parser().lexicon)


@pytest.fixture(autouse=True)
def _own_cache(monkeypatch: pytest.MonkeyPatch, tmp_path_factory: pytest.TempPathFactory) -> Path:
    return own_cache(monkeypatch, tmp_path_factory)


def _filed(title: str = "", forename: str = "", middle_name: str = "", surname: str = "",
           nationality: str = "British") -> dict[str, str]:
    boxes = {"title": title, "forename": forename, "middle_name": middle_name,
             "surname": surname}
    return {"name": " ".join(v for v in boxes.values() if v), "nationality": nationality,
            **{k: v for k, v in boxes.items() if v}}


_AGREES = _filed("Mrs", "Jo", surname="Ng")
_DOUBLE_SURNAME = _filed("", "Ana", surname="García López", nationality="Spanish")
_SUFFIX = _filed("Mr", "Bob", surname="Roe Jr")
_JOB_TITLE = _filed("Managing Partner", "Cy", surname="Doe")
_SHAPE_TITLE = _filed("Insp.", "Di", surname="Fox")


def _read(record: dict[str, str]) -> tuple[dict[str, str], bool, bool]:
    """The record's reading: the fields that disagree, whether it was
    set aside, whether the family agreed by the suffix."""
    reading = agreement.read(record, _PSC_FIELDS, Parser(), _LISTED)
    return reading.got, reading.set_aside, reading.by_suffix


def test_a_box_agrees_whatever_its_case_periods_and_spacing(
        monkeypatch: pytest.MonkeyPatch) -> None:
    assert agreement.fold(" Mr.  ANN ") == "mr ann"
    upper = _filed("MR", "ANN", surname="LEE")
    upper["forename"] = "Ann."
    assert _read(upper)[0] == {}
    # The control: compared as written, the box disagrees.
    monkeypatch.setattr(agreement, "fold", lambda text: text)
    assert _read(upper)[0] == {"given": "ANN"}


def test_a_two_word_surname_read_with_a_middle_name_is_two_misses() -> None:
    got = _read(_DOUBLE_SURNAME)[0]
    assert got == {"middle": "García", "family": "López"}
    assert agreement.shape(_DOUBLE_SURNAME, _PSC_FIELDS, got) == (
        "middle 0->1, family 2->1")


def test_a_peeled_suffix_is_compared_inside_the_surname_box() -> None:
    assert _read(_SUFFIX) == ({}, False, True)
    assert _read(_AGREES) == ({}, False, False)
    # The control: the parser's family alone leaves the box short.
    parsed = Parser().parse(_SUFFIX["name"])
    assert (parsed.family, parsed.suffix) == ("Roe", "Jr")


def test_a_title_box_holding_an_unlisted_word_the_parse_reads_otherwise_is_set_aside(
        monkeypatch: pytest.MonkeyPatch) -> None:
    got, set_aside, _ = _read(_JOB_TITLE)
    assert set_aside and "title" in got
    # An unlisted title the parse reads as the title, by its period, is
    # scored, and agrees.
    assert agreement.unlisted("Insp.", _LISTED)
    assert not agreement.unlisted("Mr. and MRS", _LISTED)  # a connective is listed
    assert _read(_SHAPE_TITLE) == ({}, False, False)
    # The control: with every word listed, the job is three misses.
    monkeypatch.setattr(agreement, "unlisted", lambda title, listed: False)
    assert _read(_JOB_TITLE) == (
        {"title": "", "given": "Managing", "middle": "Partner Cy"}, False, False)


def _corpus(monkeypatch: pytest.MonkeyPatch, *records: dict[str, str]) -> None:
    """A PSC corpus of `records` fetched into the cache, no network behind it."""
    plant_corpus(monkeypatch, corpora, _PSC, list(records), "2026-10-22", "filed names")


_ALL = (_AGREES, _DOUBLE_SURNAME, _SUFFIX, _JOB_TITLE, _SHAPE_TITLE)


def test_the_report_counts_by_group_and_field_and_prints_no_name(
        monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(agreement, "GROUP_FLOOR", 1)
    monkeypatch.setattr(agreement, "TITLE_FLOOR", 1)
    result = agreement.score(list(_ALL), _PSC_FIELDS, Parser())
    assert result.scored == {"British": 3, "Spanish": 1}
    assert result.agreed == {"British": 3}
    assert result.misses == {"Spanish": {"middle": 1, "family": 1}}
    assert result.set_aside == {"Managing Partner": 1}
    assert result.by_suffix == 1
    assert set(result.entries) == {agreement.key(_DOUBLE_SURNAME), agreement.key(_JOB_TITLE)}
    lines = agreement.report(result, _PSC_FIELDS, 5)
    assert "every field agrees: 3 of 4 (75.0%); 1 of them with the parser's suffix" \
        in "\n".join(lines)
    assert "  British                           3 100.0%         0        0        0        0" \
        in lines
    names = {w for r in _ALL for k, v in r.items() if k in ("forename", "surname")
             for w in v.split()}
    printed = " ".join(lines).replace("Managing Partner", "")
    assert not {w for w in names if w in printed.split()}


def test_a_stream_of_damaged_records_is_refused_once_read(
        monkeypatch: pytest.MonkeyPatch, _own_cache: Path) -> None:
    _corpus(monkeypatch, *_ALL)
    loaded = corpora.load(_PSC)
    assert len(list(agreement.records(loaded))) == len(_ALL)  # the control
    raw = _own_cache / "local" / _PSC / "raw.jsonl"
    raw.write_text(raw.read_text().replace("Jo", "Al"))
    with pytest.raises(corpora.CorpusDamaged, match="does not match the sha256"):
        list(agreement.records(loaded))


def test_a_rerun_reports_what_moved_since_the_record(
        monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
    _corpus(monkeypatch, *_ALL)
    assert agreement.main([_PSC, "--record"]) == 0
    assert agreement.main([_PSC]) == 0  # the control: nothing moved
    assert "matches the record" in capsys.readouterr().out
    # A parser that reads every name with its words reversed moves them all.
    real = Parser.parse
    monkeypatch.setattr(Parser, "parse",
                        lambda self, text: real(self, " ".join(reversed(text.split()))))
    assert agreement.main([_PSC]) == 1
    out = capsys.readouterr().out
    assert "regression: 3 records (" in out and "progress" not in out
    assert "changed: 2 records" in out


def test_a_record_of_another_fetch_is_refused(
        monkeypatch: pytest.MonkeyPatch, _own_cache: Path) -> None:
    _corpus(monkeypatch, *_ALL)
    assert agreement.main([_PSC, "--record"]) == 0
    _corpus(monkeypatch, *_ALL[:2])
    with pytest.raises(SystemExit, match="recorded from another fetch"):
        agreement.main([_PSC])
    path = _own_cache / "local" / _PSC / agreement.RECORD
    header = json.loads(path.read_text().splitlines()[0])
    assert set(header) == {"raw_sha256", "scorer", "data_date", "tree"}


def test_a_run_with_no_record_names_the_command_that_writes_one(
        monkeypatch: pytest.MonkeyPatch) -> None:
    _corpus(monkeypatch, *_ALL)
    with pytest.raises(SystemExit, match="--record --tree"):
        agreement.main([_PSC])


def test_a_set_aside_title_shared_by_too_few_records_is_not_printed(
        monkeypatch: pytest.MonkeyPatch) -> None:
    typed = _filed("Jo Bloggs", "Cy", surname="Doe")  # a name in the title box
    result = agreement.score([typed] * 3 + [_JOB_TITLE], _PSC_FIELDS, Parser())
    assert result.set_aside == {"Jo Bloggs": 3, "Managing Partner": 1}
    assert "Bloggs" not in "\n".join(agreement.report(result, _PSC_FIELDS, 5))
    # The control: under a floor of 3 the box shared by 3 records is
    # printed, and the one typed once is not.
    monkeypatch.setattr(agreement, "TITLE_FLOOR", 3)
    printed = "\n".join(agreement.report(result, _PSC_FIELDS, 5))
    assert "Jo Bloggs" in printed and "Managing" not in printed


def test_a_group_below_the_floor_has_no_row_and_rows_run_by_size(
        monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(agreement, "GROUP_FLOOR", 2)
    rows = [_AGREES, _filed("Mr", "Bo", surname="Wu", nationality="  british "),
            _filed("Ms", "Di", surname="Fox", nationality="Irish"),
            _filed("Ms", "Al", surname="Ng", nationality="Irish"),
            _filed("Ms", "Ed", surname="Lin", nationality="Irish"), _DOUBLE_SURNAME,
            _filed("Mr", "Cy", surname="Roe", nationality="")]
    result = agreement.score(rows, _PSC_FIELDS, Parser())
    assert result.scored == {"Irish": 3, "British": 2, "Spanish": 1, "(none)": 1}
    groups = [line.split()[0] for line in agreement.report(result, _PSC_FIELDS, 5)
              if line.startswith("  ") and line.split()[0] in result.scored]
    assert groups == ["Irish", "British"]


def test_a_line_that_is_not_a_record_is_refused_as_damage(
        monkeypatch: pytest.MonkeyPatch, _own_cache: Path) -> None:
    _corpus(monkeypatch, *_ALL)
    loaded = corpora.load(_PSC)
    raw = _own_cache / "local" / _PSC / "raw.jsonl"
    for damage in ('{"name": ', '["a list"]', '{"name": "Al Ng", "surname": 1}'):
        lines = raw.read_text().splitlines(keepends=True)
        raw.write_text("".join(lines[:1] + [damage + "\n"] + lines[1:]))
        # Through score(), which reads each record before the stream ends.
        with pytest.raises(corpora.CorpusDamaged, match="fetch it again"):
            agreement.score(agreement.records(loaded), _PSC_FIELDS, Parser())
        raw.write_text("".join(lines))
    assert len(list(agreement.records(loaded))) == len(_ALL)  # the control


def test_a_record_holding_a_value_that_is_not_text_is_refused_as_damage(
        monkeypatch: pytest.MonkeyPatch, _own_cache: Path) -> None:
    # With its sha256 rewritten to match, as a fetch that wrote a number
    # into a box would leave it, only the stream's own check sees it, and
    # the scorer would otherwise fold a number as a name's box.
    _corpus(monkeypatch, *_ALL)
    folder = _own_cache / "local" / _PSC
    raw = folder / "raw.jsonl"
    body = raw.read_bytes() + b'{"name": "Al Ng", "surname": 1}\n'
    raw.write_bytes(body)
    meta = json.loads((folder / "meta.json").read_text())
    meta["sha256"] = hashlib.sha256(body).hexdigest()
    (folder / "meta.json").write_text(json.dumps(meta))
    loaded = corpora.load(_PSC)
    assert loaded is not None
    with pytest.raises(corpora.CorpusDamaged, match="not text.*fetch it again"):
        list(agreement.records(loaded))


@pytest.mark.parametrize("body", ["", "{not json\n", '["a list"]\n',
                                  '{"raw_sha256": "x"}\n{"got": {}}\n'],
                         ids=["empty", "header not JSON", "header not an object",
                              "a row without its key"])
def test_a_record_that_is_not_one_is_refused_naming_the_record_command(
        monkeypatch: pytest.MonkeyPatch, _own_cache: Path, body: str) -> None:
    _corpus(monkeypatch, *_ALL)
    assert agreement.main([_PSC, "--record"]) == 0
    (_own_cache / "local" / _PSC / agreement.RECORD).write_text(body)
    with pytest.raises(SystemExit, match="is not a record this tool wrote.*--record"):
        agreement.main([_PSC])


def test_a_record_written_by_another_scorer_is_refused(
        monkeypatch: pytest.MonkeyPatch) -> None:
    _corpus(monkeypatch, *_ALL)
    assert agreement.main([_PSC, "--record"]) == 0
    before = agreement.scorer_fingerprint()
    # Each part of the code that decides a record's entry moves the
    # fingerprint: how a field is compared, which records get an entry,
    # and how an entry is keyed.
    for name, changed in (("fold", lambda text: text.casefold()),
                          ("score", lambda rows, fielded, parser: None),
                          ("key", lambda record: str(record))):
        with monkeypatch.context() as patch:
            patch.setattr(agreement, name, changed)
            assert agreement.scorer_fingerprint() != before, name
    with monkeypatch.context() as patch:
        patch.setattr(agreement.corpus_build, "jsonl_line",
                      lambda obj, sort_keys=False: str(obj))
        assert agreement.scorer_fingerprint() != before, "jsonl_line"
    # fold() casefolds, so a Python whose Unicode database moves it reads
    # names differently; its moves would be the database's, not the parser's.
    with monkeypatch.context() as patch:
        patch.setattr(unicodedata, "unidata_version", "0.0.0")
        assert agreement.scorer_fingerprint() != before, "unidata_version"
    assert agreement.scorer_fingerprint() == before
    monkeypatch.setattr(agreement, "fold", lambda text: text.casefold())
    with pytest.raises(SystemExit, match="another version of this scorer"):
        agreement.main([_PSC])


def test_progress_is_reported_where_a_disagreement_now_agrees(
        monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
    _corpus(monkeypatch, *_ALL)
    real = Parser.parse
    monkeypatch.setattr(Parser, "parse", lambda self, text: real(
        self, "Al Ng" if text == _AGREES["name"] else text))
    assert agreement.main([_PSC, "--record"]) == 0
    monkeypatch.setattr(Parser, "parse", real)
    assert agreement.main([_PSC, "--list", "1"]) == 1
    out = capsys.readouterr().out
    assert "progress: 1 records (" in out and "regression" not in out
    assert f"  progress: {agreement.key(_AGREES)}" in out


def test_a_tree_that_is_not_the_imported_package_is_refused(
        monkeypatch: pytest.MonkeyPatch, _own_cache: Path, tmp_path: Path) -> None:
    _corpus(monkeypatch, *_ALL)
    monkeypatch.setattr(sys, "path", list(sys.path))  # main puts the tree on it
    with pytest.raises(SystemExit, match="not from the source package"):
        agreement.main([_PSC, "--record", "--tree", str(tmp_path)])
    assert not (_own_cache / "local" / _PSC / agreement.RECORD).exists()
    # The control: this checkout itself is the tree it imported.
    root = agreement.HERE.parents[1]
    assert agreement.main([_PSC, "--record", "--tree", str(root)]) == 0
