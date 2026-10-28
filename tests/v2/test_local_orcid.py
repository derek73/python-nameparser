"""Offline checks on tools/differential/local_orcid.py, the
orcid-researchers local corpus.

Every name here is invented, and no reading of a real ORCID record may
reach the repository: the file is CC0, but its names are living
people's, which is why the corpus is local. What these pin is what a
summary gives (the boxes, the country's order of preference, the
refusals), the stream's resuming and its refusal of a file that is not
the pinned one, what the fetch keeps and counts, and the per-country
cap.
"""
import email.message
import gzip
import hashlib
import importlib
import io
import json
import tarfile
import urllib.request
from pathlib import Path

import pytest

from ._differential_fixtures import load_tool, own_cache

local = load_tool("local_corpora")
# The module the fetch reads its constants from, by name: a patch set on
# a second load by path would reach nothing (test_local_corpora.py).
orcid = importlib.import_module("local_orcid")

_ORCID = "orcid-researchers"
_MODIFIED = "Fri, 17 Oct 2025 13:21:49 GMT"
_NS = " ".join(f'xmlns:{p}="http://www.orcid.org/ns/{p}"' for p in (
    "record", "person", "personal-details", "other-name", "address", "common",
    "activities", "employment", "education", "preferences"))


@pytest.fixture(autouse=True)
def _own_cache(monkeypatch: pytest.MonkeyPatch, tmp_path_factory: pytest.TempPathFactory) -> Path:
    return own_cache(monkeypatch, tmp_path_factory)


def _org(kind: str, country: str) -> str:
    return (f"<activities:{kind}s><activities:affiliation-group>"
            f"<{kind}:{kind}-summary><common:organization><common:name>Uni</common:name>"
            f"<common:address><common:city>X</common:city><common:country>{country}"
            f"</common:country></common:address></common:organization>"
            f"</{kind}:{kind}-summary></activities:affiliation-group></activities:{kind}s>")


def _xml(given: str | None = "Ann", family: str = "", credit: str = "",
         other: tuple[str, ...] = (), address: str = "", employment: str = "",
         education: str = "", locale: str = "en") -> bytes:
    """A summary as the file writes one; `given` None leaves out the
    whole name, as a record whose name is private does."""
    name = "" if given is None else (
        "<person:name>"
        + (f"<personal-details:given-names>{given}</personal-details:given-names>" if given else "")
        + (f"<personal-details:family-name>{family}</personal-details:family-name>" if family else "")
        + (f"<personal-details:credit-name>{credit}</personal-details:credit-name>" if credit else "")
        + "</person:name>")
    others = "".join(f"<other-name:other-name><other-name:content>{o}</other-name:content>"
                     f"</other-name:other-name>" for o in other)
    home = (f"<address:addresses><address:address><address:country>{address}"
            f"</address:country></address:address></address:addresses>" if address else "")
    return (f'<?xml version="1.0" encoding="UTF-8"?><record:record {_NS}>'
            f"<preferences:preferences><preferences:locale>{locale}</preferences:locale>"
            f"</preferences:preferences><person:person>{name}"
            f"<other-name:other-names>{others}</other-name:other-names>{home}</person:person>"
            f"<activities:activities-summary>"
            + (_org("education", education) if education else "")
            + (_org("employment", employment) if employment else "")
            + "</activities:activities-summary></record:record>").encode()


def test_a_summary_gives_its_boxes_other_names_and_the_holders_own_country() -> None:
    body = _xml("Ann  Marie", "Lee", "A. M. Lee", ("Анна Ли",), address="nz",
                employment="FR", education="DE", locale="ru")
    assert orcid._summary(body) == ("record", {
        "given": "Ann Marie", "family": "Lee", "credit": "A. M. Lee", "other": ["Анна Ли"],
        "country": "NZ", "country_from": "address", "locale": "ru"})


@pytest.mark.parametrize(("where", "country_from"), [
    ({"employment": "FR", "education": "DE"}, "employment"),
    ({"education": "DE"}, "education")])
def test_without_an_address_the_country_is_the_first_organizations(
        where: dict[str, str], country_from: str) -> None:
    # An organization's own address is {.../common}address: it never
    # reads as the holder's.
    _, record = orcid._summary(_xml(employment=where.get("employment", ""),
                                    education=where.get("education", "")))
    assert record is not None
    assert (record["country"], record["country_from"]) == (
        where[country_from], country_from)


def test_a_summary_with_no_country_keeps_its_name_without_one() -> None:
    assert orcid._summary(_xml("Bo", "Wu", locale="")) == ("record", {"given": "Bo", "family": "Wu"})


@pytest.mark.parametrize(("body", "outcome"), [
    (_xml(None), "name_private"),
    (_xml(""), "name_empty"),
    (b"<record", "not_xml"),
    (b'<?xml version="1.0"?><!DOCTYPE r [<!ENTITY a "aaaa">]><r>&a;</r>', "dtd_refused")])
def test_a_summary_without_a_public_name_is_counted_and_gives_no_record(
        body: bytes, outcome: str) -> None:
    assert orcid._summary(body) == (outcome, None)


# -- the stream --------------------------------------------------------------

class _Response:
    """A ranged response serving `body` from `start`, cut after `cut`
    bytes with a reset connection where `cut` is set."""

    def __init__(self, body: bytes, start: int, *, cut: int | None = None,
                 size: int | None = None, modified: str = _MODIFIED) -> None:
        self.status = 206
        self.headers = email.message.Message()
        total = len(body) if size is None else size
        self.headers["Content-Range"] = f"bytes {start}-{total - 1}/{total}"
        self.headers["Last-Modified"] = modified
        self._body = io.BytesIO(body[start:])
        self._cut = cut

    def end_at(self, n: int) -> None:
        """End the body cleanly after `n` bytes, as a server closing early does."""
        self._body = io.BytesIO(self._body.read(n))

    def readinto(self, buffer: memoryview) -> int:
        if self._cut is not None and self._body.tell() >= self._cut:
            raise ConnectionResetError("reset by peer")
        limit = len(buffer) if self._cut is None else min(len(buffer), self._cut - self._body.tell())
        return self._body.readinto(memoryview(buffer)[:limit])

    def close(self) -> None:
        pass


def _summaries_in(body: bytes) -> int:
    """The summaries a served tar.gz holds, or 0 for a body that is not one."""
    try:
        with tarfile.open(fileobj=io.BytesIO(body), mode="r:gz") as tar:
            return sum(m.isfile() and bool(orcid._SUMMARY.fullmatch(m.name)) for m in tar)
    except (tarfile.TarError, OSError, EOFError):
        return 0


def _serve(monkeypatch: pytest.MonkeyPatch, body: bytes, *,
           cuts: tuple[int, ...] = (), size: int | None = None,
           modified: str = _MODIFIED, status: int = 206,
           eofs: tuple[int, ...] = ()) -> list[str]:
    """`body` as the pinned file, its size, MD5 and count of summaries
    pinned, each connection cut after the next of `cuts` bytes with a
    reset, or ending cleanly after the next of `eofs`; the Ranges asked."""
    monkeypatch.setattr(orcid, "ORCID_SIZE", len(body))
    monkeypatch.setattr(orcid, "ORCID_MD5", hashlib.md5(body).hexdigest())
    monkeypatch.setattr(orcid, "ORCID_SUMMARIES", _summaries_in(body))
    monkeypatch.setattr(importlib.import_module("local_core").time, "sleep", lambda _s: None)
    asked: list[str] = []
    pending, ends = list(cuts), list(eofs)

    def urlopen(request: urllib.request.Request, timeout: int) -> _Response:
        assert request.full_url == orcid.ORCID_URL
        ranged = request.get_header("Range")
        assert ranged is not None
        asked.append(ranged)
        start = int(ranged.removeprefix("bytes=").removesuffix("-"))
        response = _Response(body, start, cut=pending.pop(0) if pending else None, size=size,
                             modified=modified)
        response.status = status
        if ends:
            response.end_at(ends.pop(0))
        return response

    monkeypatch.setattr(orcid.urllib.request, "urlopen", urlopen)
    return asked


def test_a_stream_cut_mid_body_resumes_from_the_byte_it_reached(
        monkeypatch: pytest.MonkeyPatch) -> None:
    body = bytes(range(256)) * 40
    asked = _serve(monkeypatch, body, cuts=(1000, 2500))
    stream = orcid._RangeStream(orcid.ORCID_URL, orcid.ORCID_SIZE, orcid.ORCID_MD5)
    assert io.BufferedReader(stream, 700).read() == body
    stream.finish()
    assert asked == ["bytes=0-", "bytes=1000-", "bytes=3500-"]


def test_a_stream_refuses_a_file_replaced_mid_read(monkeypatch: pytest.MonkeyPatch) -> None:
    body = bytes(range(256)) * 8
    _serve(monkeypatch, body, cuts=(100,))
    stream = orcid._RangeStream(orcid.ORCID_URL, orcid.ORCID_SIZE, orcid.ORCID_MD5)
    assert stream.read(100)
    monkeypatch.setattr(orcid.urllib.request, "urlopen", lambda request, timeout: _Response(
        body, 100, modified="Sat, 01 Nov 2025 00:00:00 GMT"))
    with pytest.raises(ValueError, match="not the pinned one"):
        stream.read(100)


def test_a_stream_refuses_a_file_of_another_size(monkeypatch: pytest.MonkeyPatch) -> None:
    body = b"x" * 100
    _serve(monkeypatch, body, size=101)
    with pytest.raises(ValueError, match="not the pinned one"):
        orcid._RangeStream(orcid.ORCID_URL, orcid.ORCID_SIZE, orcid.ORCID_MD5).read(10)


def test_a_stream_whose_bytes_are_not_the_pinned_md5_is_refused_at_the_end(
        monkeypatch: pytest.MonkeyPatch) -> None:
    body = b"x" * 100
    _serve(monkeypatch, body)
    stream = orcid._RangeStream(orcid.ORCID_URL, orcid.ORCID_SIZE, "0" * 32)
    assert stream.read() == body
    with pytest.raises(ValueError, match="is pinned; fetch it again"):
        stream.finish()


# -- the fetch ---------------------------------------------------------------

def _tar(*members: tuple[str, bytes]) -> bytes:
    raw = io.BytesIO()
    with tarfile.open(fileobj=raw, mode="w") as tar:
        for name, body in members:
            info = tarfile.TarInfo(name)
            info.size = len(body)
            tar.addfile(info, io.BytesIO(body))
    return gzip.compress(raw.getvalue())


def _member(digits: str, body: bytes) -> tuple[str, bytes]:
    return f"ORCID_2025_10_summaries/{digits[-3:]}/0000-0002-1825-{digits}.xml", body


_FILE = [_member("0097", _xml("Ann", "Lee", "Lee, Ann", address="NZ")),
         _member("1097", _xml("Ann", "Lee", "Lee, Ann", address="NZ")),
         _member("2097", _xml("Bo", "Wu", employment="CN")),
         _member("3097", _xml("Cy")),
         _member("409X", _xml(None))]


def test_an_orcid_fetch_keeps_each_record_once_and_counts_the_rest(
        monkeypatch: pytest.MonkeyPatch) -> None:
    _serve(monkeypatch, _tar(*_FILE))
    corpus = local.fetch(_ORCID)
    assert corpus.records == [
        {"credit": "Lee, Ann", "country": "NZ", "country_from": "address",
         "family": "Lee", "given": "Ann", "name": "Ann Lee"},
        {"country": "CN", "country_from": "employment", "family": "Wu", "given": "Bo",
         "name": "Bo Wu"},
        {"given": "Cy", "name": "Cy"}]
    assert corpus.meta["data_date"] == "2025-10-17T13:21:49"
    assert corpus.meta["detail"] == {
        "kept": orcid._kept(), "summaries": 5, "record": 4, "name_private": 1,
        "countries": 2, "countries_at_the_cap": 0}
    # The corpus reads the credit name beside the joined boxes.
    corpus_lines = (local.directory(_ORCID) / local.CORPUS).read_text(encoding="utf-8")
    assert '"Lee, Ann"' in corpus_lines and '"Ann Lee"' in corpus_lines


def test_the_extract_keeps_every_record_with_its_other_names_and_locale(
        monkeypatch: pytest.MonkeyPatch) -> None:
    _serve(monkeypatch, _tar(_member("0097", _xml("Ann", "Lee", "A. Lee", other=("Анна",),
                                                  address="NZ"))))
    local.fetch(_ORCID)
    with gzip.open(orcid.extract_path(), "rt", encoding="utf-8") as lines:
        header, *records = lines.read().splitlines()
    assert '"file": "ORCID_2025_10_summaries.tar.gz"' in header
    assert records == [
        '{"country": "NZ", "country_from": "address", "credit": "A. Lee", "family": "Lee",'
        ' "given": "Ann", "locale": "en", "other": ["Анна"]}']


def test_workers_extract_what_one_process_does(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(orcid, "_BATCH", 2)
    body = _tar(*_FILE)
    extracts = []
    for jobs in (1, 2):
        _serve(monkeypatch, body)
        orcid.renew_orcid(jobs=jobs)
        extracts.append(gzip.decompress(orcid.extract_path().read_bytes()))
    assert extracts[0] == extracts[1]


def test_the_extract_holds_no_member_it_has_read(monkeypatch: pytest.MonkeyPatch) -> None:
    held: list[int] = []
    next_member = tarfile.TarFile.next

    def counting(self: tarfile.TarFile) -> tarfile.TarInfo | None:
        held.append(len(self.members))  # type: ignore[attr-defined]  # undeclared in typeshed
        return next_member(self)

    _serve(monkeypatch, _tar(*_FILE))  # counts the tar's summaries, before the patch
    monkeypatch.setattr(tarfile.TarFile, "next", counting)
    orcid.renew_orcid(jobs=1)
    # Without clearing, the list grows by a member a read: [0, 1, 2, ...].
    assert len(held) > 3 and max(held) <= 1


def test_a_fetch_that_fails_its_md5_keeps_the_extract_it_had(
        monkeypatch: pytest.MonkeyPatch) -> None:
    _serve(monkeypatch, _tar(*_FILE))
    orcid.renew_orcid(jobs=1)
    before = orcid.extract_path().read_bytes()
    _serve(monkeypatch, _tar(*_FILE[:2]))
    monkeypatch.setattr(orcid, "ORCID_MD5", "0" * 32)
    with pytest.raises(ValueError, match="is pinned"):
        orcid.renew_orcid(jobs=1)
    assert orcid.extract_path().read_bytes() == before
    assert sorted(p.name for p in orcid.extract_path().parent.iterdir()) == [
        orcid.extract_path().name]


def test_a_file_past_the_share_of_unreadable_summaries_is_refused(
        monkeypatch: pytest.MonkeyPatch) -> None:
    _serve(monkeypatch, _tar(*_FILE, _member("5097", b"<record")))
    with pytest.raises(ValueError, match="1 of 6 summaries are not XML"):
        local.fetch(_ORCID)
    monkeypatch.setattr(orcid, "ORCID_MAX_BAD", 1 / 5)
    assert local.fetch(_ORCID).meta["detail"]["not_xml"] == 1


def test_a_tar_past_the_share_of_files_that_are_not_summaries_is_refused(
        monkeypatch: pytest.MonkeyPatch) -> None:
    stray = ("ORCID_2025_10_summaries/README.txt", b"not a summary")
    _serve(monkeypatch, _tar(*_FILE, stray))
    with pytest.raises(ValueError, match="1 of 6 files in the tar are not summaries"):
        local.fetch(_ORCID)
    monkeypatch.setattr(orcid, "ORCID_MAX_BAD", 1 / 5)
    assert local.fetch(_ORCID).meta["detail"]["members_not_summaries"] == 1


def test_a_corpus_kept_under_another_cap_is_refused_on_load(
        monkeypatch: pytest.MonkeyPatch) -> None:
    _serve(monkeypatch, _tar(*_FILE))
    local.fetch(_ORCID)
    assert local.load(_ORCID) is not None
    monkeypatch.setattr(orcid, "ORCID_CAP", 7)
    with pytest.raises(local.CorpusDamaged, match="at most 7 records a country"):
        local.load(_ORCID)


# -- the cap -----------------------------------------------------------------

def _people(country: str, n: int) -> list[dict[str, str]]:
    return [{"name": f"Ann Lee{i}", "country": country} for i in range(n)]


def test_the_cap_samples_a_large_country_and_keeps_a_small_one_whole() -> None:
    records = _people("NZ", 30) + _people("FR", 3) + [{"name": "Cy"}] * 2
    kept = orcid.orcid_kept(iter(records), 10)
    by_country = [r.get("country", "") for r in kept]
    assert (by_country.count("NZ"), by_country.count("FR"), by_country.count("")) == (10, 3, 1)


def test_the_cap_keeps_the_same_records_whatever_the_order_or_the_rest() -> None:
    nz = _people("NZ", 40)
    kept = orcid.orcid_kept(iter(nz), 10)
    shuffled = orcid.orcid_kept(iter(nz[::-1] + _people("FR", 50) + nz[:5]), 10)
    assert sorted(map(str, kept)) == sorted(map(str, (r for r in shuffled if r["country"] == "NZ")))


# -- what a summary gives, further -------------------------------------------

def test_the_first_organization_naming_a_country_gives_it() -> None:
    body = _xml(employment="FR").replace(
        b"</activities:affiliation-group></activities:employments>",
        b"</activities:affiliation-group><activities:affiliation-group>"
        b"<employment:employment-summary><common:organization><common:address>"
        b"<common:country>DE</common:country></common:address></common:organization>"
        b"</employment:employment-summary></activities:affiliation-group>"
        b"</activities:employments>")
    assert b"DE" in body
    _, record = orcid._summary(body)
    assert record is not None and record["country"] == "FR"


@pytest.mark.parametrize(("body", "outcome", "record"), [
    (_xml("", credit="A. Lee"), "name_empty", None),
    (_xml("", "Lee"), "record", {"family": "Lee", "locale": "en"})])
def test_a_name_is_its_two_boxes_and_a_credit_name_alone_is_none(
        body: bytes, outcome: str, record: dict[str, str] | None) -> None:
    assert orcid._summary(body) == (outcome, record)


# -- the stream, further -----------------------------------------------------

def test_a_stream_refuses_an_answer_that_is_not_a_range(monkeypatch: pytest.MonkeyPatch) -> None:
    # A server ignoring Range answers 200 with the body from byte 0, which
    # on a resume would splice the file's start into the stream.
    _serve(monkeypatch, b"x" * 100, status=200)
    with pytest.raises(ValueError, match="answered 200"):
        orcid._RangeStream(orcid.ORCID_URL, orcid.ORCID_SIZE, orcid.ORCID_MD5).read(10)


def test_a_stream_refuses_a_file_that_states_no_last_modified(
        monkeypatch: pytest.MonkeyPatch) -> None:
    # Without it the replaced-file check would have nothing to compare.
    _serve(monkeypatch, b"x" * 100, modified="")
    with pytest.raises(ValueError, match="last modified not stated"):
        orcid._RangeStream(orcid.ORCID_URL, orcid.ORCID_SIZE, orcid.ORCID_MD5).read(10)


def test_a_body_that_ends_early_without_an_error_resumes(monkeypatch: pytest.MonkeyPatch) -> None:
    body = bytes(range(256)) * 8
    asked = _serve(monkeypatch, body, eofs=(1000,))
    stream = orcid._RangeStream(orcid.ORCID_URL, orcid.ORCID_SIZE, orcid.ORCID_MD5)
    assert io.BufferedReader(stream, 700).read() == body
    stream.finish()
    assert asked == ["bytes=0-", "bytes=1000-"]


def test_a_stream_rides_out_more_failures_than_a_small_request_would(
        monkeypatch: pytest.MonkeyPatch) -> None:
    body = bytes(range(256)) * 4
    failures = orcid.ORCID_RETRIES - 1
    assert failures > importlib.import_module("local_core").RETRIES
    asked = _serve(monkeypatch, body, cuts=(0,) * failures)
    sleeps: list[float] = []
    monkeypatch.setattr(importlib.import_module("local_core").time, "sleep", sleeps.append)
    stream = orcid._RangeStream(orcid.ORCID_URL, orcid.ORCID_SIZE, orcid.ORCID_MD5)
    assert stream.read() == body
    assert len(asked) == failures + 1
    assert sleeps == [min(2 ** n, 60) for n in range(failures)]


def test_a_gzip_whose_crc_fails_after_the_tar_ends_is_refused(
        monkeypatch: pytest.MonkeyPatch) -> None:
    body = bytearray(_tar(*_FILE))
    body[-8] ^= 0xFF  # the trailer's CRC32, read only past the tar's end
    _serve(monkeypatch, bytes(body))
    with pytest.raises(gzip.BadGzipFile, match="CRC check failed"):
        orcid.renew_orcid(jobs=1)
    assert not orcid.extract_path().parent.exists() or not any(
        orcid.extract_path().parent.iterdir())


# -- the reader's checks -----------------------------------------------------

def _write_extract(header: dict[str, object] | bytes, lines: tuple[str, ...] = ()) -> Path:
    """An extract written by hand: `header` and `lines`, or bytes as they stand."""
    path = orcid.extract_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    if isinstance(header, bytes):
        path.write_bytes(header)
    else:
        text = json.dumps(header) + "\n" + "".join(f"{line}\n" for line in lines)
        path.write_bytes(gzip.compress(text.encode()))
    return path


_HEAD = {"file": orcid.ORCID_FILE, "data_date": "2025-10-17T13:21:49", "counts": {"record": 0}}


@pytest.mark.parametrize("header", [
    {**_HEAD, "file": "ORCID_2024_10_summaries.tar.gz"},
    {**_HEAD, "counts": [0]},
    {**_HEAD, "counts": {"record": "0"}},
    {k: v for k, v in _HEAD.items() if k != "data_date"},
    {**_HEAD, "data_date": 2025},
    gzip.compress(b"", mtime=0),  # a gzip header holds its time: one id for every worker
    b"not gzip"], ids=["another file", "counts not a dict", "a count not an int",
                       "no data date", "a data date not text", "empty", "not gzip"])
def test_a_file_that_is_not_an_extract_is_refused_naming_the_refresh(
        header: dict[str, object] | bytes) -> None:
    with pytest.raises(ValueError, match="not an extract this tool wrote.*--refresh"):
        orcid._orcid_read(_write_extract(header))


def test_a_tar_read_only_in_part_is_refused_and_the_extract_kept(
        monkeypatch: pytest.MonkeyPatch) -> None:
    # tarfile ends a stream at a damaged header without raising, and the
    # bytes still pass their MD5: only the pinned count shows it.
    _serve(monkeypatch, _tar(*_FILE))
    orcid.renew_orcid(jobs=1)
    before = orcid.extract_path().read_bytes()
    monkeypatch.setattr(orcid, "ORCID_SUMMARIES", len(_FILE) + 1)
    with pytest.raises(ValueError, match="the tar was read in part"):
        orcid.renew_orcid(jobs=1)
    assert orcid.extract_path().read_bytes() == before
    assert sorted(p.name for p in orcid.extract_path().parent.iterdir()) == [
        orcid.extract_path().name]


def test_an_extract_missing_records_its_header_counts_is_refused(
        monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(orcid, "ORCID_SUMMARIES", 2)
    path = _write_extract({**_HEAD, "counts": {"record": 2}},
                          ('{"country": "NZ", "family": "Lee", "given": "Ann"}',))
    with pytest.raises(ValueError, match="holds 1 records .* counts 2 records"):
        orcid._orcid_read(path)


@pytest.mark.parametrize(("extra", "says"), [
    (_member("5097", b"<record"), "1 of 6 summaries are not XML"),
    (_member("5097", b'<?xml version="1.0"?><!DOCTYPE r><r/>'),
     "1 of 6 summaries declare a DTD or an entity"),
    (("ORCID_2025_10_summaries/README.txt", b"x"), "1 of 6 files in the tar are not summaries"),
    (_member("5097", _xml("Di", "Ng", address="nzl")),
     "1 of 4 countries are not two capital letters")])
def test_a_file_past_a_share_of_what_it_reads_past_is_refused_before_it_is_kept(
        monkeypatch: pytest.MonkeyPatch, extra: tuple[str, bytes], says: str) -> None:
    _serve(monkeypatch, _tar(*_FILE))
    orcid.renew_orcid(jobs=1)
    before = orcid.extract_path().read_bytes()
    _serve(monkeypatch, _tar(*_FILE, extra))
    with pytest.raises(ValueError, match=says):
        orcid.renew_orcid(jobs=1)
    assert orcid.extract_path().read_bytes() == before


@pytest.mark.parametrize("bad", [1, 2])
def test_the_share_of_unreadable_summaries_is_held_at_its_shipped_value(
        monkeypatch: pytest.MonkeyPatch, bad: int) -> None:
    assert orcid.ORCID_MAX_BAD == 1 / 10_000
    monkeypatch.setattr(orcid, "ORCID_SUMMARIES", 10_000)
    good = 10_000 - bad
    lines = tuple(f'{{"country": "NZ", "family": "Lee{i}", "given": "Ann"}}' for i in range(good))
    path = _write_extract({**_HEAD, "counts": {"record": good, "not_xml": bad}}, lines)
    if bad == 1:
        assert orcid._orcid_read(path).detail["not_xml"] == 1
    else:
        with pytest.raises(ValueError, match="2 of 10,000 summaries are not XML"):
            orcid._orcid_read(path)


@pytest.mark.parametrize(("members", "says"), [
    # The name moved: every summary reads as private.
    ([_member(f"{n}097", _xml(None)) for n in range(4)] + _FILE[:1],
     "only 1 of 5 summaries give a record"),
    # The family box was renamed: no record holds one.
    ([_member(f"{n}097", _xml(f"Ann{n}", address="NZ")) for n in range(4)],
     "only 0 of 4 records hold a family name"),
    # The address and organization namespaces moved: no record has a country.
    ([_member(f"{n}097", _xml(f"Ann{n}", "Lee")) for n in range(4)],
     "only 0 of 4 records hold a country")])
def test_a_file_whose_layout_moved_under_the_reader_is_refused(
        monkeypatch: pytest.MonkeyPatch, members: list[tuple[str, bytes]], says: str) -> None:
    _serve(monkeypatch, _tar(*members))
    with pytest.raises(ValueError, match=says):
        local.fetch(_ORCID)


def test_the_countries_at_the_cap_leave_out_the_records_with_none(
        monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(orcid, "ORCID_CAP", 1)
    _serve(monkeypatch, _tar(*_FILE))
    detail = local.fetch(_ORCID).meta["detail"]
    assert (detail["countries"], detail["countries_at_the_cap"]) == (2, 2)


def test_an_extract_of_another_version_is_streamed_again(monkeypatch: pytest.MonkeyPatch) -> None:
    _serve(monkeypatch, _tar(*_FILE))
    orcid.fetch_orcid()
    asked = _serve(monkeypatch, _tar(*_FILE))
    orcid.fetch_orcid()
    assert asked == []  # the extract cached for this version is read
    monkeypatch.setattr(orcid, "ORCID_EXTRACT_VERSION", orcid.ORCID_EXTRACT_VERSION + 1)
    orcid.fetch_orcid()
    assert asked == ["bytes=0-"]
