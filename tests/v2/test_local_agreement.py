"""Offline checks on tools/differential/local_agreement.py.

The score compares a parse of each filed display name with the boxes the
filer typed it into, so what these pin is the comparison's three
decisions (the fold, the suffix counted in the surname box, the title
box set aside as filer error), each beside the reading with the decision
off, and the record's refusals: no record, a record that is not one, a record of
another fetch or another scorer, and a corpus damaged under the stream. The names are invented.
"""
import hashlib
import importlib
import itertools
import json
import sys
import unicodedata
from pathlib import Path

import pytest

# @needs_checkout: the harness refuses a nameparser imported from outside the checkout
from tests.checkout import needs_checkout


from nameparser import Parser

from ._differential_fixtures import checkout_copy, load_tool, own_cache, plant_corpus

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


@pytest.mark.parametrize("surname", ["Roe, Jr.", "Roe,Jr.", "Roe, III", "Roe, Jr., PhD"])
def test_a_suffix_after_a_comma_in_the_surname_box_agrees(
        monkeypatch: pytest.MonkeyPatch, surname: str) -> None:
    # The parser reads "Bob Roe, Jr." as family Roe and suffix Jr., and
    # the surname box holds the two with the filer's comma between them.
    filed = _filed("", "Bob", surname=surname)
    assert _read(filed)[0] == {}
    # The control: the fold before commas were read as spaces misses it.
    monkeypatch.setattr(agreement, "fold",
                        lambda text: " ".join(text.replace(".", "").casefold().split()))
    assert list(_read(filed)[0]) == ["family"]


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
    # The sample pinned as the real source pins it: a --base child
    # loads the corpus under the real Source and its check.
    plant_corpus(monkeypatch, corpora, _PSC, list(records), "2026-10-22", "filed names",
                 {"sample": f"1 in {importlib.import_module('local_psc').PSC_SAMPLE}"})


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


@needs_checkout
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


@needs_checkout
def test_a_record_of_another_fetch_is_refused(
        monkeypatch: pytest.MonkeyPatch, _own_cache: Path) -> None:
    _corpus(monkeypatch, *_ALL)
    assert agreement.main([_PSC, "--record"]) == 0
    _corpus(monkeypatch, *_ALL[:2])
    with pytest.raises(SystemExit, match="recorded from another fetch"):
        agreement.main([_PSC])
    path = _own_cache / "local" / _PSC / agreement.RECORD
    header = json.loads(path.read_text().splitlines()[0])
    assert set(header) == {"raw_sha256", "scorer", "data_date", "tree", "entries", "locale"}


@needs_checkout
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


@needs_checkout
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


@needs_checkout
def test_a_record_written_by_another_scorer_is_refused(
        monkeypatch: pytest.MonkeyPatch) -> None:
    _corpus(monkeypatch, *_ALL)
    assert agreement.main([_PSC, "--record"]) == 0
    before = agreement.scorer_fingerprint(_PSC)
    # Each part of the code that decides a record's entry moves the
    # fingerprint: how a field is compared, which records get an entry,
    # how an entry is keyed, and the source's own boxes; another source's
    # boxes do not, so adding a source leaves this one's record standing.
    other = next(s for s in agreement.FIELDED if s != _PSC)
    with monkeypatch.context() as patch:
        patch.setitem(agreement.FIELDED, other,
                      agreement.Fielded({"forename": "given", "surname": "family"}, group="x"))
        assert agreement.scorer_fingerprint(_PSC) == before, other
        patch.setitem(agreement.FIELDED, _PSC,
                      agreement.Fielded({"forename": "given", "surname": "family"}, group="x"))
        assert agreement.scorer_fingerprint(_PSC) != before, "its own boxes"
    for name, changed in (("fold", lambda text: text.casefold()),
                          ("score", lambda rows, fielded, parser: None),
                          ("titled", lambda *args: False),
                          ("key", lambda record: str(record))):
        with monkeypatch.context() as patch:
            patch.setattr(agreement, name, changed)
            assert agreement.scorer_fingerprint(_PSC) != before, name
    with monkeypatch.context() as patch:
        patch.setattr(agreement.corpus_build, "jsonl_line",
                      lambda obj, sort_keys=False: str(obj))
        assert agreement.scorer_fingerprint(_PSC) != before, "jsonl_line"
    # fold() casefolds, so a Python whose Unicode database moves it reads
    # names differently; its moves would be the database's, not the parser's.
    with monkeypatch.context() as patch:
        patch.setattr(unicodedata, "unidata_version", "0.0.0")
        assert agreement.scorer_fingerprint(_PSC) != before, "unidata_version"
    assert agreement.scorer_fingerprint(_PSC) == before
    monkeypatch.setattr(agreement, "fold", lambda text: text.casefold())
    with pytest.raises(SystemExit, match="another version of this scorer"):
        agreement.main([_PSC])


@needs_checkout
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


@needs_checkout
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


# -- --base ----------------------------------------------------------------------

def _kept(cache: Path) -> list[Path]:
    return sorted((cache / "local" / _PSC / agreement.KEPT).glob("*.jsonl"))


@needs_checkout
def test_a_base_check_reports_a_change_planted_in_the_base_and_none_across_a_copy(
        monkeypatch: pytest.MonkeyPatch, _own_cache: Path, tmp_path: Path,
        capsys: pytest.CaptureFixture[str]) -> None:
    # The harness must be able to report a difference: a base scored with
    # the head's tree by mistake would show no move across a planted one.
    _corpus(monkeypatch, *_ALL)
    planted = checkout_copy(tmp_path / "planted", planted=True)
    assert agreement.main([_PSC, "--base", str(planted)]) == 1
    out = capsys.readouterr().out
    assert f"base: {planted.resolve()}, nameparser/ " in out and "scored it now" in out
    assert "progress: 3 records (" in out and "regression" not in out
    # The control: an unplanted copy is the head's package byte for byte.
    copy = checkout_copy(tmp_path / "copy")
    assert agreement.main([_PSC, "--base", str(copy)]) == 0
    out = capsys.readouterr().out
    assert "matches the base" in out and "byte-identical" in out
    assert len(_kept(_own_cache)) == 2


@needs_checkout
def test_a_base_check_never_touches_the_shared_record(
        monkeypatch: pytest.MonkeyPatch, _own_cache: Path, tmp_path: Path) -> None:
    _corpus(monkeypatch, *_ALL)
    shared = _own_cache / "local" / _PSC / agreement.RECORD
    base = checkout_copy(tmp_path / "base", planted=True)
    assert agreement.main([_PSC, "--base", str(base)]) == 1
    assert not shared.exists()
    assert agreement.main([_PSC, "--record"]) == 0
    shared.write_text(shared.read_text().splitlines()[0] + "\n")  # would read as moves
    before = (shared.stat().st_mtime_ns, shared.read_bytes())
    assert agreement.main([_PSC, "--base", str(checkout_copy(tmp_path / "copy"))]) == 0
    assert (shared.stat().st_mtime_ns, shared.read_bytes()) == before


@needs_checkout
def test_a_kept_base_record_is_reused_and_a_damaged_one_scored_again(
        monkeypatch: pytest.MonkeyPatch, _own_cache: Path, tmp_path: Path,
        capsys: pytest.CaptureFixture[str]) -> None:
    _corpus(monkeypatch, *_ALL)
    base = checkout_copy(tmp_path / "base", planted=True)
    assert agreement.main([_PSC, "--base", str(base)]) == 1
    [kept] = _kept(_own_cache)
    recorded = kept.read_bytes()
    capsys.readouterr()
    real = agreement._score_base

    def unscored(*args: object) -> None:
        raise AssertionError("scored the base again")
    monkeypatch.setattr(agreement, "_score_base", unscored)
    assert agreement.main([_PSC, "--base", str(base)]) == 1
    assert "reused the kept record" in capsys.readouterr().out
    # A record cut short on a line boundary still parses line by line;
    # its header's count is what refuses it.
    header = json.loads(recorded.decode().splitlines()[0])
    uncounted = json.dumps({**header, "entries": None}) + "\n" + "".join(
        recorded.decode().splitlines(keepends=True)[1:])
    for damage in ("not a record\n", "".join(recorded.decode().splitlines(keepends=True)[:-1]),
                   uncounted):
        kept.write_text(damage)
        with pytest.raises(AssertionError, match="scored the base again"):
            agreement.main([_PSC, "--base", str(base)])
        assert "deleted the kept record" in capsys.readouterr().out
        monkeypatch.setattr(agreement, "_score_base", real)
        assert agreement.main([_PSC, "--base", str(base)]) == 1
        assert kept.read_bytes() == recorded
        assert not list(kept.parent.glob(".base-*"))  # the child's scratch is gone
        monkeypatch.setattr(agreement, "_score_base", unscored)


@needs_checkout
def test_a_base_that_changed_while_it_was_scored_keeps_no_record(
        monkeypatch: pytest.MonkeyPatch, _own_cache: Path, tmp_path: Path) -> None:
    _corpus(monkeypatch, *_ALL)
    base = checkout_copy(tmp_path / "base", planted=True)
    # The module base_entries imports by its bare name (local_agreement
    # put its folder on sys.path), not a second load by path.
    snapshot = importlib.import_module("snapshot")
    answers = ["a" * 64, "b" * 64]
    published: list[bool] = []

    def digest(root: Path) -> str:
        if not answers:
            return "c" * 64
        if len(answers) == 1:  # the check after the score: nothing kept yet
            published.append(bool(_kept(_own_cache)))
        return answers.pop(0)
    monkeypatch.setattr(snapshot, "_source_digest", digest)
    with pytest.raises(SystemExit, match="changed while it was scored"):
        agreement.main([_PSC, "--base", str(base)])
    # Written to the kept path before the check, a sibling could have
    # reused it as the base it was keyed for in between.
    assert published == [False]
    assert not _kept(_own_cache)
    assert not list((_own_cache / "local" / _PSC / agreement.KEPT).glob(".base-*"))


@needs_checkout
def test_a_base_that_is_the_tree_read_or_no_checkout_is_refused(
        monkeypatch: pytest.MonkeyPatch, _own_cache: Path, tmp_path: Path) -> None:
    _corpus(monkeypatch, *_ALL)
    with pytest.raises(SystemExit, match="is the tree being read"):
        agreement.main([_PSC, "--base", str(agreement.HERE.parents[1])])
    with pytest.raises(SystemExit, match="no nameparser package"):
        agreement.main([_PSC, "--base", str(tmp_path)])
    assert not _kept(_own_cache)


@needs_checkout
def test_a_base_whose_import_fails_is_refused_with_the_childs_output(
        monkeypatch: pytest.MonkeyPatch, _own_cache: Path, tmp_path: Path) -> None:
    _corpus(monkeypatch, *_ALL)
    base = checkout_copy(tmp_path / "base")
    with open(base / "nameparser" / "__init__.py", "a", encoding="utf-8") as f:
        f.write("\nraise ImportError('planted')\n")
    with pytest.raises(SystemExit, match="(?s)scoring the base .* failed.*planted"):
        agreement.main([_PSC, "--base", str(base)])
    assert not _kept(_own_cache)


def test_a_base_check_refuses_to_record(
        monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
    _corpus(monkeypatch, *_ALL)
    for extra in (["--record"], ["--out", "x.jsonl"]):
        with pytest.raises(SystemExit) as raised:
            agreement.main([_PSC, "--base", ".", *extra])
        assert raised.value.code == 2 and "--base compares" in capsys.readouterr().err


@needs_checkout
def test_record_writes_where_out_says_and_leaves_the_shared_record(
        monkeypatch: pytest.MonkeyPatch, _own_cache: Path, tmp_path: Path) -> None:
    _corpus(monkeypatch, *_ALL)
    out = tmp_path / "elsewhere.jsonl"
    assert agreement.main([_PSC, "--record", "--out", str(out)]) == 0
    assert agreement.read_record(out, corpora.load(_PSC))
    assert not (_own_cache / "local" / _PSC / agreement.RECORD).exists()


# -- --jobs ----------------------------------------------------------------------

def test_a_score_read_in_workers_is_the_score_read_in_process(
        monkeypatch: pytest.MonkeyPatch) -> None:
    # Every decision's record, so a worker dropping one reads differently.
    serial = agreement.score(list(_ALL), _PSC_FIELDS, Parser())
    monkeypatch.setattr(importlib.import_module("snapshot"), "PARALLEL_FLOOR", 1)
    assert agreement.score(list(_ALL), _PSC_FIELDS, Parser(), jobs=2) == serial
    assert serial.entries and serial.set_aside and serial.by_suffix


def test_a_score_in_workers_refuses_a_parser_it_cannot_send_them() -> None:
    from nameparser import Lexicon
    configured = Parser(lexicon=Lexicon.default().add("partner", kind="title"))
    with pytest.raises(ValueError, match=r"parser_of\(''\)"):
        agreement.score(list(_ALL), _PSC_FIELDS, configured, jobs=2)
    agreement.score(list(_ALL), _PSC_FIELDS, configured)  # the control: in process


def test_a_score_whose_worker_read_another_nameparser_aborts(
        monkeypatch: pytest.MonkeyPatch) -> None:
    import nameparser
    monkeypatch.setattr(importlib.import_module("snapshot"), "PARALLEL_FLOOR", 1)
    monkeypatch.setattr(nameparser, "__file__", "/elsewhere/nameparser/__init__.py")
    with pytest.raises(SystemExit, match="a worker imported nameparser from"):
        agreement.score(list(_ALL), _PSC_FIELDS, Parser(), jobs=2)


# -- a source whose given box holds the middle names (orcid-researchers) -----

_ORCID_FIELDS = agreement.FIELDED[corpora.ORCID]


def _held(given: str, family: str, country: str = "NZ") -> dict[str, str]:
    return {"name": f"{given} {family}".strip(), "given": given, "family": family,
            "country": country}


def test_a_given_box_holding_the_middle_names_is_compared_with_both() -> None:
    # The parser reads Marie as a middle name; the box holds both words.
    agrees = agreement.read(_held("Ann Marie", "Lee"), _ORCID_FIELDS, Parser(), _LISTED)
    assert (agrees.got, agrees.set_aside) == ({}, False)
    # Off: the box compared with the given name alone misses.
    alone = agreement.Fielded({"given": "given", "family": "family"}, group="country")
    assert agreement.read(_held("Ann Marie", "Lee"), alone, Parser(), _LISTED).got == {
        "given": "Ann"}


def test_a_source_with_no_title_box_counts_a_title_typed_as_a_given_name_apart() -> None:
    # #1501: neither a miss nor filer error set aside, but a class of its own.
    reading = agreement.read(_held("Dr Ann", "Lee"), _ORCID_FIELDS, Parser(), _LISTED)
    assert (reading.got, reading.set_aside, reading.titled) == (
        {"given+middle": "Ann"}, False, "Dr")


def test_a_peeled_suffix_is_compared_inside_the_family_box_of_a_joined_source() -> None:
    reading = agreement.read(_held("Bob", "Roe Jr"), _ORCID_FIELDS, Parser(), _LISTED)
    assert (reading.got, reading.by_suffix) == ({}, True)


@pytest.mark.parametrize("given", [
    "B.A.S.D.",       # given B., middle A.S.D.
    "K.S",            # given K., middle S
    "B.H. Nuwan",     # given B., middle H. Nuwan
    "V.G.Ravi",       # given V., middle G.Ravi
    "A.B.C",          # given A., middle B.C
    "Md.Karim",       # given Md., middle Karim (#1477)
    "Moh.Rafi Nuwan", # given Moh., middle Rafi Nuwan
    "Jo.Ann",         # given Jo., middle Ann, no vocabulary involved
])
def test_a_box_the_parse_cuts_after_its_full_stops_agrees(given: str) -> None:
    # #1470, #1477: the parse holds the box's letters in the box's
    # field, a space after a full stop the filer typed being all that
    # differs.
    record = _held(given, "Kumarasiri", "LK")
    assert agreement.read(record, _ORCID_FIELDS, Parser(), _LISTED).got == {}
    # The control: compared folded alone, as before #1470, it is a miss.
    assert agreement.fold(given) != agreement.fold(
        " ".join(filter(None, (lambda p: (p.given, p.middle))(Parser().parse(record["name"])))))


@pytest.mark.parametrize(("given", "family", "got"), [
    # The box's letters read as a title: no field holds them.
    ("AB", "Lee", {"given+middle": ""}),
    # A word of the family box read into the given box's field.
    ("K.S", "Perera Silva", {"given+middle": "K. S Perera", "family": "Silva"}),
    # A title glued before the box's letters, peeled to a field ORCID
    # has no box for: since #1501 a class of its own (titled), not an
    # agreement, which the cut alone would not make it.
    ("Dr.A.B.", "Perera", {"given+middle": "A. B."}),
    ("Dr.Ahmed", "Hassan", {"given+middle": "Ahmed"}),
])
def test_a_misreading_beside_a_cut_at_a_full_stop_never_agrees(
        given: str, family: str, got: dict[str, str]) -> None:
    assert agreement.read(_held(given, family), _ORCID_FIELDS, Parser(), _LISTED).got == got


# -- a listed title typed into the given-names box (#1501) ---------------------

_PV_FIELDS = agreement.FIELDED[corpora.PV]


@pytest.mark.parametrize(("given", "family", "title", "got"), [
    ("Dr. Anna", "Berg", "Dr.", "Anna"),
    ("Dr/ Anna", "Berg", "Dr", "Anna"),          # a slash for the full stop (#1149)
    ("د. منى", "حسن", "د.", "منى"),
    ("Dr.Ahmed", "Hassan", "Dr.", "Ahmed"),      # glued, cut at its full stop (#1477)
    ("Prof. Dr. Anna", "Berg", "Prof. Dr.", "Anna"),
    ("Dr. Anna Maria", "Berg", "Dr.", "Anna Maria"),
])
@pytest.mark.parametrize("fielded", [_ORCID_FIELDS, _PV_FIELDS], ids=["orcid", "patentsview"])
def test_a_listed_title_typed_into_the_given_box_is_counted_apart(
        given: str, family: str, title: str, got: str, fielded: object) -> None:
    reading = agreement.read(_held(given, family), fielded, Parser(), _LISTED)
    assert (reading.got, reading.titled, reading.set_aside) == (
        {"given+middle": got}, title, False)


def test_a_title_typed_into_the_forename_box_beside_an_empty_title_box_is_counted_apart(
        ) -> None:
    reading = agreement.read(_filed("", "Dr Anna", "Maria", "Berg"), _PSC_FIELDS,
                             Parser(), _LISTED)
    assert (reading.got, reading.titled) == ({"title": "Dr", "given": "Anna"}, "Dr")


@pytest.mark.parametrize(("record", "fielded", "got"), [
    # A title the vocabulary does not list, read by its shape alone: the
    # mistake a source with no title box exists to catch.
    (_held("Xyz. Anna", "Berg"), _ORCID_FIELDS, {"given+middle": "Anna"}),
    # A box holding only a title: no names in it to agree.
    (_held("Dr", "Berg"), _ORCID_FIELDS, {"given+middle": ""}),
    # A title typed into the family box, read as the title after it.
    (_held("Anna", "Berg Dr."), _ORCID_FIELDS, {"family": "Berg"}),
    # Another field disagrees too, the given box agreeing (the family
    # box's nickname is no family; the set check alone refuses it).
    (_held("Dr Anna", "Berg (Lee)"), _ORCID_FIELDS, {"family": "Berg"} | {
        "given+middle": "Anna"}),
    (_held("Dr Anna", "Berg Silva"), _ORCID_FIELDS, {"given+middle": "Anna Berg",
                                                     "family": "Silva"}),
    # The box holds more than the title and the names read (a nickname),
    # nothing else disagreeing: the comparison alone refuses it.
    (_held("Dr (Ann) Anna", "Berg"), _ORCID_FIELDS, {"given+middle": "Anna"}),
    # A slash glued inside a word is not read as the title's full stop;
    # only a title word ending in it is (`Dr/ Anna`).
    (_held("Dr/Anna", "Berg"), _ORCID_FIELDS, {"given+middle": "Anna"}),
    # A title box filed: the title is scored against it.
    (_filed("Mrs", "Dr Anna", surname="Berg"), _PSC_FIELDS, {"title": "Mrs Dr",
                                                             "given": "Anna"}),
    # A box holding only a title, the names in the next box.
    (_filed("", "Dr", "Anna", "Berg"), _PSC_FIELDS, {"title": "Dr", "given": "Anna",
                                                     "middle": ""}),
])
def test_a_title_outside_the_class_stays_a_miss(
        record: dict[str, str], fielded: object, got: dict[str, str]) -> None:
    reading = agreement.read(record, fielded, Parser(), _LISTED)
    assert (reading.got, reading.titled) == (got, "")


def test_a_title_word_the_parse_reads_as_a_given_name_agrees() -> None:
    # `Dean` is a title only inside a title phrase (rules/H9), so the
    # parse reads the box's words as its names.
    reading = agreement.read(_held("Dean Anna", "Berg"), _ORCID_FIELDS, Parser(), _LISTED)
    assert (reading.got, reading.titled) == ({}, "")


#: How many of the class's rows (the parametrized rows above, read as
#: ORCID records) the scorer read as misses before #1501: the guard's
#: negative control, re-taken whenever its rows or the parse move.
_TITLED_ROWS = (("Dr. Anna", "Berg"), ("Dr/ Anna", "Berg"), ("د. منى", "حسن"),
                ("Dr.Ahmed", "Hassan"), ("Prof. Dr. Anna", "Berg"), ("Dr. Anna Maria", "Berg"))
_UNTITLED_EFFECT = 6


def test_the_titled_class_is_counted_apart_from_the_agreement_figure(
        monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(agreement, "GROUP_FLOOR", 1)
    rows = [_held(g, f) for g, f in _TITLED_ROWS] + [_held("Ann", "Lee"),
                                                     _held("Xyz. Anna", "Berg")]
    result = agreement.score(rows, _ORCID_FIELDS, Parser())
    assert result.scored == {"NZ": 2} and result.agreed == {"NZ": 1}
    assert result.titled == {"Dr.": 3, "Dr": 1, "د.": 1, "Prof. Dr.": 1}
    assert all(result.entries[agreement.key(r)].get("titled") for r in rows[:6])
    lines = "\n".join(agreement.report(result, _ORCID_FIELDS, 5))
    assert "every field agrees: 1 of 2 (50.0%)" in lines
    assert result.titled_groups == {"NZ": 6}
    assert "  NZ                                2  50.0%         1        0        6" in lines
    assert "read as the title: 6 (counted apart" in lines
    assert "titles most often read in the given-names box:\n          3  Dr." in lines
    # The negative control: with the class off, each of its rows is a miss.
    monkeypatch.setattr(agreement, "titled", lambda *args: False)
    off = agreement.score(rows, _ORCID_FIELDS, Parser())
    assert not off.titled
    assert sum(bool(agreement.read(r, _ORCID_FIELDS, Parser(), _LISTED).got)
               for r in rows[:6]) == _UNTITLED_EFFECT


def test_a_record_entering_or_leaving_the_titled_class_is_reported_apart() -> None:
    miss = {"got": {"given+middle": "Anna"}}
    titled = {"got": {"given+middle": "Anna"}, "titled": "Dr."}
    other = {"got": {"given+middle": "Anna"}, "titled": "Prof. Dr."}
    old = {"a": miss, "c": titled, "d": titled, "e": miss, "f": titled}
    new = {"a": titled, "b": titled, "c": miss, "e": {"got": {"family": "Lee"}}, "f": other}
    found = agreement.moves(old, new)
    # A record in the class on both sides, read with another title, changed.
    assert found == {"regression": [], "progress": [], "changed": ["e", "f"],
                     "titled in": ["a", "b"], "titled out": ["c", "d"]}
    lines = agreement.summarize(found, old, new)
    assert "titled in: 2 records, a title typed into the given-names box (Dr. 2)" in lines
    assert "titled out: 2 records, a title typed into the given-names box (Dr. 2)" in lines


def test_a_cut_across_two_boxes_stays_a_miss() -> None:
    # psc-individuals compares each box alone: `Md.Karim` typed in the
    # forename box and read given `Md.`, middle `Karim` puts a word in
    # the middle-name box the filer left empty (#1477).
    assert _read(_filed("", "Md.Karim", surname="Hossain"))[0] == {
        "given": "Md.", "middle": "Karim"}


@pytest.mark.parametrize(("box", "got", "same"), [
    ("a.b.", "a. b.", True),         # box joined, reading spaced
    ("a. b.", "a.b.", True),         # box spaced, reading joined
    ("A.B. Lee", "a. b. lee", True),
    ("A.B.", "A. B. Lee", False),    # a word left over
    ("A.B. Lee", "A. B. Ann Lee", False),  # a word left over in the middle
    ("A.Bc.D.", "A. Bc. D.", True),  # a word inside the run (#1477)
    ("Md.Karim", "Md. Karim", True), # a word before the full stop
    ("1.2.", "1. 2.", True),         # whatever stands before it
    ("A.B.", "A. C.", False),        # other letters
    ("A.B.", "A.", False),           # letters missing
    ("AB", "A B", False),            # no full stops: a word, not initials
    ("A B", "AB", False),
    ("MD", "M D", False),
    ("Al", "A l", False),
    ("Jo.Ann", "Jo. Ann", True),
    ("K.S", "K S", False),           # the reading's full stop gone
    ("Md.Karim", "Md Karim", False),
    ("Md.Karim", "Md. Karin", False),  # other letters
    ("क.ख.", "क. ख.", True),          # letters of any script
    ("कि.ख.", "कि. ख.", True),        # a letter with its vowel sign (a regression row)
    ("Md.Karim", "Md. Karim Lee", False),  # a word left over after a cut word
])
def test_agreement_across_a_cut_after_a_full_stop_only(box: str, got: str, same: bool) -> None:
    assert agreement.agrees(box, got) is same
    assert agreement.agrees(got, box) is same


#: The grid: a run of initials or a word ending in a full stop, with a
#: name word glued to it, one or two spaced from it, or none, before a
#: one- and a two-word family.
_RUNS = ("A.", "A.B.", "A.B", "A.B.C.", "A.B.C", "Т.В.", "क.ख.", "Md.", "Jo.", "Moh.R.")
#: How many of the grid's records the comparison before #1470 scored a
#: miss, though the reading held the box's letters in the box's field: the
#: guard's negative control, re-taken whenever the grid or the parse moves.
_UNGUARDED_EFFECT = 25
#: The grid's records whose reading holds the box's letters in the box's
#: field, and the rest, read with a word of the family box in the given
#: box's field (`A.B. Kumarasiri Silva`), which stay misses.
_HELD, _MISREAD = 40, 40
#: How many of the grid's held records #1470's rule, a cut forgiven only
#: after initials, still scored a miss: the rows #1477 added
#: (`Md.Nuwan`, `Jo.Nuwan`, `Moh.R.Nuwan`).
_INITIALS_ONLY_EFFECT = 3


def _joined_after_initials(joined: list[str], spaced: list[str]) -> bool:
    """#1470's _joined, kept here as the guard's second control: a cut
    forgiven only after a piece that is one or more initials."""
    def initials(word: str) -> bool:
        return word.endswith(".") and all(
            chunk[:1].isalpha() and all(unicodedata.category(c).startswith("M") for c in chunk[1:])
            for chunk in word[:-1].split("."))
    i = 0
    for word in joined:
        if i < len(spaced) and agreement.fold(word) == agreement.fold(spaced[i]):
            i += 1
            continue
        built, j = spaced[i] if i < len(spaced) else "", i + 1
        while j < len(spaced) and len(built) < len(word) and initials(spaced[j - 1]):
            built, j = built + spaced[j], j + 1
        if j - i < 2 or built.casefold() != word.casefold():
            return False
        i = j
    return i == len(spaced)


def test_a_reading_cut_only_after_a_full_stop_is_never_scored_a_miss(
        monkeypatch: pytest.MonkeyPatch) -> None:
    # #1470: 3.1's #1296 began reading `B.A.S.D.` as given `B.`, middle
    # `A.S.D.`, and the space the scorer's join puts between the two,
    # which the fold kept, scored a miss where the box was read right.
    # Wherever the box's field holds the box's letters, the cut a parse
    # draws after a full stop the filer typed must not decide the score,
    # whatever stands before it (#1477).
    # "The box's letters" is the fold with its spaces removed, which is
    # looser than the rule (`AB` against `A B` would pass it): every run
    # in the grid holds a full stop, so the filter never meets that case.
    parser = Parser()
    rows: list[dict[str, str]] = []
    misread: list[dict[str, str]] = []
    for run, rest, family in itertools.product(
            _RUNS, ("", " Nuwan", "Nuwan", " Nuwan Ravi"), ("Perera", "Kumarasiri Silva")):
        record = _held(run + rest, family, "LK")
        name = parser.parse(record["name"])
        held = " ".join(filter(None, (name.given, name.middle)))
        same = agreement.fold(held).replace(" ", "") == agreement.fold(record["given"]).replace(" ", "")
        (rows if same else misread).append(record)
    assert (len(rows), len(misread)) == (_HELD, _MISREAD)

    def misses(records: list[dict[str, str]]) -> int:
        return sum("given+middle" in agreement.read(r, _ORCID_FIELDS, parser, _LISTED).got
                   for r in records)

    assert misses(rows) == 0
    # The other half: a word of the family box read into the given box's
    # field stays a miss.
    assert misses(misread) == _MISREAD
    # The negative controls: a cut forgiven only after initials, as
    # #1470 had it, and compared folded alone, as before #1470.
    with monkeypatch.context() as patch:
        patch.setattr(agreement, "_joined", _joined_after_initials)
        assert misses(rows) == _INITIALS_ONLY_EFFECT
    monkeypatch.setattr(agreement, "agrees", lambda box, got: agreement.fold(box) == agreement.fold(got))
    assert misses(rows) == _UNGUARDED_EFFECT


def test_a_country_code_group_prints_as_written(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(agreement, "GROUP_FLOOR", 1)
    result = agreement.score([_held("Ann", "Lee"), _held("Bo Yu", "Wu Li", "CN")],
                             _ORCID_FIELDS, Parser())
    assert result.scored == {"NZ": 1, "CN": 1}
    assert result.misses == {"CN": {"given+middle": 1, "family": 1}}
    assert result.shapes == {"given+middle 2->3, family 2->1": 1}


def test_the_roles_a_box_may_name_are_the_parsers() -> None:
    from nameparser import Role
    assert agreement.ROLES == {role.value for role in Role}


@pytest.mark.parametrize("fields", [
    {"forename": "given", "surname": "famly"},
    {"forename": "given+midle", "surname": "family"},
    {"forename": "given"}])
def test_a_fielded_source_naming_an_unknown_role_or_no_family_is_refused(
        fields: dict[str, str]) -> None:
    with pytest.raises(ValueError, match="each box names roles of"):
        agreement.Fielded(fields, group="nationality")


# -- a source with a box after the name (cz-candidates) --------------------------

_VOLBY = corpora.VOLBY
_VOLBY_FIELDS = agreement.FIELDED[_VOLBY]


def _candidate(before: str, given: str, family: str, after: str = "",
               election: str = "kv2022") -> dict[str, str]:
    boxes = {"titulpred": before, "jmeno": given, "prijmeni": family, "titulza": after}
    return {"name": importlib.import_module("local_volby").compose(boxes),
            "election": election, **{k: v for k, v in boxes.items() if v}}


def _volby_read(record: dict[str, str], fielded: object = _VOLBY_FIELDS
                ) -> tuple[dict[str, str], bool, bool]:
    """The record's reading, as _read gives it, under `fielded`."""
    reading = agreement.read(record, fielded, Parser(), _LISTED)
    return reading.got, reading.set_aside, reading.by_suffix


@pytest.mark.parametrize(("record", "titled"), [
    # A listed title typed into the given-names box, the title box empty,
    # whatever stands after the name.
    (_candidate("", "Dr. Jan", "Novák"), "Dr."),
    (_candidate("", "Mgr. Jan", "Novák", "Ph.D."), "Mgr."),
    # The title box filed: the title is scored against it.
    (_candidate("Ing.", "Dr. Jan", "Novák"), ""),
    # A title the default vocabulary does not list.
    (_candidate("", "Ing. Jan", "Novák"), ""),
])
def test_a_source_with_a_title_box_counts_a_title_in_the_given_box_only_where_it_is_empty(
        record: dict[str, str], titled: str) -> None:
    assert agreement.read(record, _VOLBY_FIELDS, Parser(), _LISTED).titled == titled


def test_a_filed_title_box_keeps_a_record_out_of_the_titled_class() -> None:
    # A filed title box puts its words in the parse's title, so the
    # comparison refuses such a record too; this pins the clause itself.
    got, wrong = {"title": "Dr", "given": "Anna", "middle": "", "family": "Berg"}, {
        "title": "Dr", "given": "Anna"}
    record = {"forename": "Dr Anna", "surname": "Berg"}
    assert agreement.titled(record, _PSC_FIELDS, "Dr", got, wrong, _LISTED)
    assert not agreement.titled({**record, "title": "Dr"}, _PSC_FIELDS, "Dr", got, wrong,
                                _LISTED)


def test_a_suffix_is_compared_with_the_box_after_the_name_not_the_surname() -> None:
    assert _volby_read(_candidate("Ing.", "Jan", "Novák", "Ph.D.")) == ({}, False, False)
    # The control: read as a source with no suffix box, the parser's
    # suffix is appended to the family, which the surname box then misses.
    joined = agreement.Fielded({"titulpred": "title", "jmeno": "given+middle",
                                "prijmeni": "family"}, group="election")
    assert _volby_read(_candidate("Ing.", "Jan", "Novák", "Ph.D."),
                       joined)[0] == {"family": "Novák Ph.D."}


def test_a_title_box_the_parse_misses_is_scored_where_the_source_sets_nothing_aside() -> None:
    # Bc. is a title by its shape (rules/H2) and listed in no vocabulary,
    # so the title box holds an unlisted word; the parse reads the
    # diploma after the name as a second title.
    missed = _candidate("Bc.", "Jan", "Novák", "DiS.")
    assert _volby_read(missed)[:2] == ({"title": "Bc. DiS.", "suffix": ""}, False)
    # The control: a source that sets aside would excuse the parser's miss.
    setting = agreement.Fielded(dict(_VOLBY_FIELDS.fields), group="election")
    assert _volby_read(missed, setting)[1]


def test_the_report_of_a_source_with_a_suffix_box_counts_by_election(
        monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(agreement, "GROUP_FLOOR", 1)
    rows = [_candidate("Ing.", "Jan", "Novák"), _candidate("", "Eva", "Malá", "DiS."),
            _candidate("Mgr.", "Bo", "Dvořák", election="ps2025")]
    result = agreement.score(rows, _VOLBY_FIELDS, Parser())
    assert result.scored == {"kv2022": 2, "ps2025": 1}
    assert result.misses == {"kv2022": {"title": 1, "suffix": 1}}
    lines = agreement.report(result, _VOLBY_FIELDS, 5)
    assert lines[:2] == ["scored 3; none set aside", "every field agrees: 2 of 3 (66.7%)"]
    assert not any("set-aside" in line for line in lines)


@needs_checkout
def test_a_locale_scores_its_pack_s_parser_against_a_record_of_its_own(
        monkeypatch: pytest.MonkeyPatch, _own_cache: Path,
        capsys: pytest.CaptureFixture[str]) -> None:
    from nameparser import locales, parser_for
    assert agreement.parser_of("cs") == parser_for(locales.CS)
    assert agreement.parser_of("") == Parser()
    # MgA. et Mgr. is a run of two titles only where MgA. is listed,
    # as locales.CS lists it and the default does not: the two parsers
    # read it apart.
    rows = [_candidate("MgA. et Mgr.", "Jan", "Novák"), _candidate("Ing.", "Eva", "Malá")]
    plant_corpus(monkeypatch, corpora, _VOLBY, rows, "kv2022 2026-03-28", "candidates",
                 {"elections": "kv2022 ps2025", "read_version": 1})
    assert agreement.main([_VOLBY, "--record"]) == 0
    assert agreement.main([_VOLBY, "--record", "--locale", "CS"]) == 0
    out = capsys.readouterr().out
    assert "under parser_for(locales.CS)" in out
    folder = _own_cache / "local" / _VOLBY
    default, cs = (agreement.read_record(folder / name, corpora.load(_VOLBY), locale)
                   for name, locale in (("agreement.jsonl", ""), ("agreement.cs.jsonl", "cs")))
    assert len(default) == 1 and cs == {}
    assert agreement.main([_VOLBY, "--locale", "cs"]) == 0  # its own record: no moves
    with pytest.raises(SystemExit, match="scored under the locale 'cs', not '\\(default\\)'"):
        agreement.read_record(folder / "agreement.cs.jsonl", corpora.load(_VOLBY))
    loaded = corpora.load(_VOLBY)
    assert agreement.kept_path(_VOLBY, loaded, "d" * 64, "cs") != agreement.kept_path(
        _VOLBY, loaded, "d" * 64)


def test_a_score_in_workers_reads_with_the_locale_s_parser(
        monkeypatch: pytest.MonkeyPatch) -> None:
    rows = [_candidate("MgA. et Mgr.", "Jan", "Novák"), _candidate("Ing.", "Eva", "Malá")]
    cs = agreement.parser_of("cs")
    serial = agreement.score(rows, _VOLBY_FIELDS, cs)
    monkeypatch.setattr(importlib.import_module("snapshot"), "PARALLEL_FLOOR", 1)
    assert agreement.score(rows, _VOLBY_FIELDS, cs, jobs=2, locale="cs") == serial
    assert serial != agreement.score(rows, _VOLBY_FIELDS, Parser())  # the control
    with pytest.raises(ValueError, match="parser_of\\('cs'\\)"):
        agreement.score(rows, _VOLBY_FIELDS, Parser(), jobs=2, locale="cs")


@needs_checkout
def test_an_unknown_locale_is_refused_naming_the_packs(
        monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
    plant_corpus(monkeypatch, corpora, _VOLBY, [_candidate("Ing.", "Eva", "Malá")],
                 "kv2022 2026-03-28", "candidates",
                 {"elections": "kv2022 ps2025", "read_version": 1})
    # With no record and with a base too: the locale is refused first, not
    # as "no record" or as the base's child failing on it.
    for extra in (["--record"], [], ["--base", str(agreement.HERE.parents[1])]):
        with pytest.raises(SystemExit) as raised:
            agreement.main([_VOLBY, *extra, "--locale", "xx"])
        assert raised.value.code == 2, extra
        assert "no such pack; the packs are" in capsys.readouterr().err, extra


@needs_checkout
def test_a_base_check_under_a_locale_scores_the_base_under_it(
        monkeypatch: pytest.MonkeyPatch, _own_cache: Path, tmp_path: Path,
        capsys: pytest.CaptureFixture[str]) -> None:
    rows = [_candidate("MgA. et Mgr.", "Jan", "Novák"), _candidate("Ing.", "Eva", "Malá")]
    plant_corpus(monkeypatch, corpora, _VOLBY, rows, "kv2022 2026-03-28", "candidates",
                 {"elections": "kv2022 ps2025", "read_version": 1})
    copy = checkout_copy(tmp_path / "copy")
    assert agreement.main([_VOLBY, "--base", str(copy), "--locale", "cs"]) == 0
    assert "matches the base" in capsys.readouterr().out
    [kept] = (_own_cache / "local" / _VOLBY / agreement.KEPT).glob("*.jsonl")
    assert kept.name.endswith("-cs.jsonl")
    # The control: the default's base reads the MgA. run apart, so its
    # record, kept beside the locale's, is not the locale's.
    assert agreement.main([_VOLBY, "--base", str(copy)]) == 0
    records = sorted((_own_cache / "local" / _VOLBY / agreement.KEPT).glob("*.jsonl"))
    assert len(records) == 2
    assert {len(agreement.read_record(r, corpora.load(_VOLBY), "cs" if r == kept else ""))
            for r in records} == {0, 1}
