"""Unit tests for parity_check.py, the 1.4.0 check of the case table's
`parity` rows.

Nothing here spawns `uv` or reaches the network: the baseline is a
stub reading each text as a table says, so what is tested is the
mapping from a row to 1.4.0's attributes, the comparison, the report,
and the planted rows that make a run unable to report nothing when its
baseline is not 1.4.0. The run against the real wheel is the tool's
own, and needs the network or uv's cache.
"""
from dataclasses import dataclass, field
from collections.abc import Callable, Mapping, Sequence

import pytest

from ._differential_fixtures import load_tool

parity = load_tool("parity_check")


@dataclass(frozen=True)
class _Case:
    """The fields of tests/v2/cases.py's Case the tool reads."""
    id: str
    text: str
    expect: dict[str, str]
    classification: str = "parity"
    policy: object = None
    locale: str | None = None
    notes: str = field(default="")


def _v1(**fields: str) -> dict[str, str]:
    """A 1.4.0 reading keyed by its attribute names, from field names."""
    return {parity.FIELDS[f]: v for f, v in fields.items()}


#: 1.4.0's readings by text: the planted rows' text read as 1.4.0 reads it.
_READS = {"John Smith": _v1(given="John", family="Smith")}


def _stub(reads: Mapping[str, dict[str, str]]
          ) -> Callable[[Sequence[str]], list[dict[str, str]]]:
    def read(texts: Sequence[str]) -> list[dict[str, str]]:
        return [dict(reads[t]) for t in texts]
    return read


def test_every_field_maps_to_the_attribute_1_4_0_reads_it_from() -> None:
    """given and family are 1.4.0's first and last; the rest keep their
    names, maiden included, which 1.4.0's HumanName has."""
    got = parity.from_v1({"title": "Dr.", "first": "Jane", "middle": "Q.",
                          "last": "Doe", "suffix": "Jr.", "nickname": "J",
                          "maiden": "Smith"})
    assert got == {"title": "Dr.", "given": "Jane", "middle": "Q.",
                   "family": "Doe", "suffix": "Jr.", "nickname": "J",
                   "maiden": "Smith"}


def test_a_missing_attribute_reads_empty() -> None:
    assert parity.from_v1({"first": "Jane"})["maiden"] == ""


def test_selection_skips_a_policy_or_locale_row_and_ignores_other_kinds() -> None:
    rows, skipped = parity.select([
        _Case("plain", "John Smith", {"given": "John"}),
        _Case("policy", "John Smith", {"given": "John"}, policy=object()),
        _Case("locale", "John Smith", {"given": "John"}, locale="ru"),
        _Case("fixed", "John Smith", {"given": "John"}, classification="fix(#1)"),
    ])
    assert [r.id for r in rows] == ["plain"]
    assert skipped == ["policy", "locale"]
    assert rows[0].expect == {"title": "", "given": "John", "middle": "",
                              "family": "", "suffix": "", "nickname": "",
                              "maiden": ""}


@pytest.mark.parametrize("want,have", [
    ("PhD I.", "PhD, I."),
    ("Jr., MD", "Jr., MD"),
    ("vd Jr", "vd, Jr"),
])
def test_a_suffix_differing_only_by_its_commas_is_the_same_reading(
        want: str, have: str) -> None:
    row = parity.Row("r", "x", {**dict.fromkeys(parity.FIELDS, ""), "suffix": want})
    assert parity.differ(row, {**dict.fromkeys(parity.FIELDS, ""), "suffix": have}) == {}


@pytest.mark.parametrize("want,have", [
    ("VI Ph. D.", "Ph. D., VI"),   # reordered
    ("PhD Jones", "PhD"),          # a word left out
    ("MD, PhD", "PhD"),
    ("Jr.,", "Jr."),               # a trailing comma is no join
    ("Jr.", "Jr.,"),
    ("MD,PhD", "MD PhD"),          # nor a comma with no space after it
])
def test_a_suffix_with_other_words_or_order_differs(want: str, have: str) -> None:
    row = parity.Row("r", "x", {**dict.fromkeys(parity.FIELDS, ""), "suffix": want})
    got = {**dict.fromkeys(parity.FIELDS, ""), "suffix": have}
    assert parity.differ(row, got) == {"suffix": (want, have)}


def test_commas_count_in_every_other_field() -> None:
    row = parity.Row("r", "x", {**dict.fromkeys(parity.FIELDS, ""), "family": "Smith"})
    got = {**dict.fromkeys(parity.FIELDS, ""), "family": "Smith,"}
    assert parity.differ(row, got) == {"family": ("Smith", "Smith,")}


def test_a_row_1_4_0_reads_otherwise_is_reported_with_its_fields() -> None:
    cases = [
        _Case("agrees", "Jane Doe", {"given": "Jane", "family": "Doe"}),
        _Case("disagrees", "Doe, Jane MD", {"given": "Jane", "family": "Doe",
                                            "suffix": "MD"}),
        _Case("switched", "Doe, Jane MD", {"given": "Jane"}, policy=object()),
    ]
    reads = {**_READS,
             "Jane Doe": _v1(given="Jane", family="Doe"),
             "Doe, Jane MD": _v1(given="Jane", middle="MD", family="Doe")}
    result = parity.check(cases, _stub(reads))
    assert [m.row.id for m in result.mismatches] == ["disagrees"]
    assert result.mismatches[0].fields == {"middle": ("", "MD"),
                                           "suffix": ("MD", "")}
    assert result.compared == 2 and result.skipped == ("switched",)
    source = 'x\n    Case("agrees", ...\n    Case("disagrees", ...\n'
    assert parity.report(result, source) == [
        "cases.py:3 disagrees 'Doe, Jane MD'",
        "    middle: expected '', 1.4.0 'MD'",
        "    suffix: expected 'MD', 1.4.0 ''",
        "1 of 2 parity rows read otherwise under 1.4.0",
        "1 parity rows carrying a policy or a locale skipped: 1.4.0 has "
        "no Policy to read them under",
    ]


def test_a_baseline_reading_as_the_table_expects_aborts() -> None:
    """The harness proof: a baseline answering from the tree reads
    every row as the table says, the planted wrong row included, so
    the run would report no mismatch at all. The planted row is what
    turns that into an abort."""
    cases = [_Case("row", "Jane Doe", {"given": "Jane", "family": "Doe"})]

    def as_expected(texts: Sequence[str]) -> list[dict[str, str]]:
        expect = {c.text: c.expect for c in cases}
        planted = iter(parity._PLANTED.values())
        return [_v1(**(expect[t] if t in expect else next(planted)))
                for t in texts]
    with pytest.raises(SystemExit, match="planted rows came back wrong"):
        parity.check(cases, as_expected)


def test_a_baseline_reading_nothing_aborts() -> None:
    """The converse: a baseline returning empty readings reports every
    row, the planted match included."""
    with pytest.raises(SystemExit, match="planted rows came back wrong"):
        parity.check([], lambda texts: [{} for _ in texts])


def test_a_baseline_returning_too_few_readings_aborts() -> None:
    with pytest.raises(SystemExit, match="readings for"):
        parity.check([], lambda texts: [])


def test_a_planted_wrong_parity_row_in_the_table_is_reported() -> None:
    """A row planted into the table, wrongly labelled parity, comes out
    of a run against a stub that reads as 1.4.0 does."""
    cases = [_Case("planted", "Smith, John Jr", {"given": "John",
                                                 "family": "Smith Jr"})]
    reads = {**_READS,
             "Smith, John Jr": _v1(given="John", family="Smith", suffix="Jr")}
    result = parity.check(cases, _stub(reads))
    assert [m.row.id for m in result.mismatches] == ["planted"]


def test_the_worker_pins_the_wheel_and_reads_every_field() -> None:
    source = parity.worker_source("1.4.0")
    assert 'dependencies = ["nameparser==1.4.0"]' in source
    assert repr(tuple(parity.FIELDS.values())) in source


def test_the_worker_runs_with_no_import_path_overrides(
        monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("PYTHONPATH", "/somewhere")
    monkeypatch.setenv("PYTHONHOME", "/elsewhere")
    env = parity.worker_env(parity._compare())
    assert "PYTHONPATH" not in env and "PYTHONHOME" not in env
    assert env["PYTHONSAFEPATH"] == "1"


def test_check_exits_nonzero_only_when_asked(
        monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
    """--check turns a mismatch into exit 1; without it the run exits 0."""
    found = parity.Result((parity.Mismatch(parity.Row("r", "x", {}),
                                           {"given": ("a", "b")}),), 1, ())
    monkeypatch.setattr(parity, "check", lambda cases, read: found)
    assert parity.main([]) == 0
    assert parity.main(["--check"]) == 1
    monkeypatch.setattr(parity, "check",
                        lambda cases, read: parity.Result((), 1, ()))
    assert parity.main(["--check"]) == 0
    capsys.readouterr()
