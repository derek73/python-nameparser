"""Offline checks on tools/differential/local_mycandidates.py, the
my-candidates local corpus of Malaysia's election candidates.

Every name here is invented: the candidates are real people, so their
records stay in the cache. What these pin is what a fetch keeps (one
record per distinct spelling within an election and ethnicity, its
election, form and ethnicity, the ethnicity as its group), which column
each pinned file is read by, and the fetch's refusals: a file other than
the pinned one, another header or row count, a file ending inside a row
(each arm), rows of another width or with an empty name past their
shares, and a corpus read at another commit or by another version. The
network is a stub answering by URL.
"""
import hashlib
import importlib
import time
import urllib.error
import urllib.request

import pytest

from ._differential_fixtures import _Response, load_tool, own_cache

local = load_tool("local_corpora")
# The modules the fetch reads its constants from, by name
# (test_local_corpora.py says why a second load by path would not do).
my = importlib.import_module("local_mycandidates")
core = importlib.import_module("local_core")

_SOURCE = my.MY
_ONE = ("name", "ethnicity", "votes")
_TWO = ("name_ballot", "name", "ethnicity")


@pytest.fixture(autouse=True)
def _own_cache(monkeypatch: pytest.MonkeyPatch, tmp_path_factory: pytest.TempPathFactory) -> None:
    own_cache(monkeypatch, tmp_path_factory)


def _csv(header: tuple[str, ...], *rows: tuple[str, ...]) -> bytes:
    return "".join(",".join(r) + "\n" for r in (header, *rows)).encode()


def _serve(monkeypatch: pytest.MonkeyPatch, files: list[tuple[str, tuple[str, ...], bytes]], *,
           pinned: dict[str, str] | None = None, rows: dict[str, int] | None = None
           ) -> list[str]:
    """Pin FILES to `files`, each (election, header, body): one ballot
    form for a header of one name column, a ballot and a full form for
    _TWO, the sha256 being the body's (`pinned`'s where given) and the
    rows its lines less the header (`rows`' where given); answer each
    pinned URL with its body. The URLs asked."""
    pinned, rows = pinned or {}, rows or {}
    answers: dict[str, bytes] = {}
    pins = []
    for election, header, body in files:
        forms = ((("ballot", "name_ballot"), ("full", "name")) if header == _TWO
                 else (("ballot", "name"),))
        file = my.File(election, f"candidates_{election}.csv",
                       pinned.get(election, hashlib.sha256(body).hexdigest()),
                       rows.get(election, body.count(b"\n") - 1), header, forms)
        pins.append(file)
        answers[my.MY_URL.format(commit=my.MY_COMMIT, file=file.file)] = body
    monkeypatch.setattr(my, "FILES", tuple(pins))
    asked: list[str] = []

    def urlopen(request: urllib.request.Request, timeout: int) -> _Response:
        asked.append(request.full_url)
        if request.full_url not in answers:
            raise urllib.error.HTTPError(request.full_url, 404, "Not Found", {}, None)  # type: ignore[arg-type]
        return _Response(answers[request.full_url])
    monkeypatch.setattr(urllib.request, "urlopen", urlopen)
    monkeypatch.setattr(time, "sleep", lambda seconds: None)
    return asked


#: A general election's ballot names: one candidate standing twice (once
#: padded), and the same name under another ethnicity, which is another
#: record; a state election's ballot and full names, one full name equal
#: to its ballot name.
_FILES = [
    ("ge99", _ONE, _csv(_ONE, ("NORAZLAN BIN ZAKARIM", "bumiputera", "10"),
                        ("  NORAZLAN  BIN ZAKARIM ", "bumiputera", "12"),
                        ("NORAZLAN BIN ZAKARIM", "other", "3"),
                        ("LIM KOK WEE", "chinese", "7"))),
    ("prn99", _TWO, _csv(_TWO, ("USTAZ NORAZLAN", "NORAZLAN BIN ZAKARIM", "malay"),
                         ("MUTHUVEL A/L SANGARAN", "MUTHUVEL A/L SANGARAN", "indian"))),
]


def test_a_fetch_keeps_each_distinct_spelling_with_its_election_form_and_ethnicity(
        monkeypatch: pytest.MonkeyPatch) -> None:
    asked = _serve(monkeypatch, _FILES)
    corpus = local.fetch(_SOURCE)
    assert asked == [my.MY_URL.format(commit=my.MY_COMMIT, file=f"candidates_{e}.csv")
                     for e, _, _ in _FILES]

    def rec(name: str, election: str, form: str, ethnicity: str) -> dict[str, str]:
        return {"name": name, "election": election, "form": form, "ethnicity": ethnicity}
    assert corpus.records == [
        rec("NORAZLAN BIN ZAKARIM", "ge99", "ballot", "bumiputera"),
        rec("NORAZLAN BIN ZAKARIM", "ge99", "ballot", "other"),
        rec("LIM KOK WEE", "ge99", "ballot", "chinese"),
        # A spelling is distinct within its election, so the full name
        # that a general election held as a ballot name is a record here.
        rec("USTAZ NORAZLAN", "prn99", "ballot", "malay"),
        rec("NORAZLAN BIN ZAKARIM", "prn99", "full", "malay"),
        rec("MUTHUVEL A/L SANGARAN", "prn99", "ballot", "indian")]
    assert corpus.meta["data_date"] == my.MY_DATE
    assert corpus.meta["names"] == 4
    detail = corpus.meta["detail"]
    assert detail["commit"] == my.MY_COMMIT and detail["read_version"] == my.MY_READ_VERSION
    assert detail["elections"] == {"ge99": {"rows": 4, "ballot": 3, "repeated": 1},
                                   "prn99": {"rows": 2, "ballot": 2, "full": 1,
                                             "repeated": 1}}


def test_the_source_is_grouped_by_ethnicity() -> None:
    assert local.SOURCES[_SOURCE].group == "ethnicity"


def test_each_pinned_file_reads_columns_its_header_holds() -> None:
    assert [f.election for f in my.FILES] == ["ge12", "ge13", "ge14", "ge15", "prn15"]
    for file in my.FILES:
        assert "ethnicity" in file.header
        assert {form for form, _ in file.forms} <= {"ballot", "full"}
        assert all(column in file.header for _, column in file.forms)
        assert len(file.sha256) == 64 and file.rows > 0
    # GE15's `name` is the full name recased into title case, so only its
    # ballot name is read; PRN15 writes both in capitals.
    assert dict(my.FILES[3].forms) == {"ballot": "name_display"}
    assert dict(my.FILES[4].forms) == {"ballot": "name_ballot", "full": "name"}


def test_a_file_other_than_the_pinned_one_is_retried_then_refused(
        monkeypatch: pytest.MonkeyPatch) -> None:
    asked = _serve(monkeypatch, _FILES[:1], pinned={"ge99": "0" * 64})
    with pytest.raises(ValueError, match="sha256 is .* not the pinned 0000"):
        local.fetch(_SOURCE)
    assert len(asked) == core.RETRIES


@pytest.mark.parametrize(("body", "rows", "match"), [
    (_csv(("name", "ethnicity")), None, "header is not the 3 columns"),
    (_FILES[0][2], 5, "holds 4 rows where 5 are pinned"),
    # The two arms of a body cut inside its last row: no closing line
    # break, and a short last row (a cut inside a quoted name that held a
    # line break ends with one).
    (_FILES[0][2].rstrip(b"\n"), None, "ends inside a row"),
    (_csv(_ONE, ("LIM KOK WEE", "chinese", "7")) + b'"TAN\n', 2, "ends inside a row"),
], ids=["header", "row count", "no closing line break", "short last row"])
def test_a_changed_or_cut_file_is_refused(monkeypatch: pytest.MonkeyPatch, body: bytes,
                                          rows: int | None, match: str) -> None:
    _serve(monkeypatch, [("ge99", _ONE, body)], rows={"ge99": rows} if rows else None)
    with pytest.raises(ValueError, match=match):
        local.fetch(_SOURCE)


def test_a_long_last_row_is_left_to_the_malformed_share(
        monkeypatch: pytest.MonkeyPatch) -> None:
    rows = [("LIM KOK WEE", "chinese", "7")] * 99 + [("TAN AH KOW", "chinese", "7", "x")]
    _serve(monkeypatch, [("ge99", _ONE, _csv(_ONE, *rows))])
    assert local.fetch(_SOURCE).meta["detail"]["elections"]["ge99"]["malformed"] == 1


@pytest.mark.parametrize(("bad", "share", "kind"), [
    (("TAN AH KOW", "chinese"), "MY_MAX_BAD", "are not 3 fields"),
    (("", "chinese", "7"), "MY_MAX_NAMELESS", "have an empty name"),
], ids=["malformed", "nameless"])
def test_the_rows_read_past_are_refused_past_their_shipped_share(
        monkeypatch: pytest.MonkeyPatch, bad: tuple[str, ...], share: str, kind: str) -> None:
    # At the shipped share, one row in a hundred: accepted at it, and
    # refused one past it. The last row is whole, so the wholeness check
    # does not answer first.
    assert getattr(my, share) == 1 / 100
    whole = ("LIM KOK WEE", "chinese", "7")
    _serve(monkeypatch, [("ge99", _ONE, _csv(_ONE, bad, *[whole] * 99))])
    local.fetch(_SOURCE)  # the control: 1 of 100
    _serve(monkeypatch, [("ge99", _ONE, _csv(_ONE, bad, bad, *[whole] * 98))])
    with pytest.raises(ValueError, match=f"2 of 100 rows of candidates_ge99.csv {kind}"):
        local.fetch(_SOURCE)


@pytest.mark.parametrize(("constant", "value", "match"), [
    ("MY_COMMIT", "f" * 40, "read at commit .* reads f{40}"),
    ("MY_READ_VERSION", 99, "read by version 1 of _read.*version 99"),
], ids=["commit", "read version"])
def test_a_corpus_read_another_way_is_refused_on_load(
        monkeypatch: pytest.MonkeyPatch, constant: str, value: object, match: str) -> None:
    _serve(monkeypatch, _FILES)
    local.fetch(_SOURCE)
    assert local.load(_SOURCE) is not None  # the control
    monkeypatch.setattr(my, constant, value)
    with pytest.raises(ValueError, match=f"{match}.*fetch {_SOURCE} --refresh"):
        local.load(_SOURCE)
