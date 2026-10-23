"""The tw-donors local corpus: Taiwan's political donation reports.

tw-donors -- the distinct names of every individual donor in every
campaign finance report Taiwan's Control Yuan publishes on its political
donation platform (ardata.cy.gov.tw, the zips data.gov.tw lists): 454
reports of 64 elections on 2026-10-22, presidential, legislative and
local: every report from 2018's elections on, and the residual reports
of 2014's and 2016's. Each report's zip is cached whole in a reports/
folder beside the corpus (40 MB on 2026-10-22), under the name the
platform's listing gives it, so a refresh downloads only the reports
published or rebuilt since. Names as a candidate's staff typed them
into a filing, published in full where the ID, address and phone
beside them are masked: of the
308,667 on 2026-10-05, 296,820 were three Han characters, 5,449 four
and 5,260 two, so it is the population for unspaced Han names written
family first, and for the married double surname (冠夫姓) a four-
character name often is. Under the Open Government Data License,
version 1.0, which the credit line every report opens with names, with
the platform's own bar on using the data for profit, credit
investigation or another improper purpose; only the donor column is
kept.
"""
from __future__ import annotations

import csv
import io
import re
import sys
import urllib.parse
import zipfile
import zlib
from collections import Counter
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import corpus_build
from local_core import (Fetched, _get_json, _refuse_past, _retried, _zip_stamp,
                        directory)


# -- Taiwan political donations ------------------------------------------------

TW_API = "https://ardata.cy.gov.tw/api/v1"
TW_PAGE = 1000  # one page held all 454 reports on 2026-10-22
#: The seconds of sleep after each report's download.
TW_DELAY = 1.0
TW_INCOMES = "incomes.csv"
#: The columns incomes.csv may hold, in the order the newest reports
#: write them; an older report omits some (a 2020 by-election's had no
#: 更正註記), so a file is read by its own header's names.
TW_HEADER = (
    "序號", "擬參選人／政黨", "選舉名稱", "申報序號／年度", "交易日期", "收支科目",
    "捐贈者／支出對象", "身分證／統一編號", "收入金額", "支出金額", "捐贈方式",
    "存入專戶日期", "返還/繳庫", "支出用途", "金錢類", "地址", "聯絡電話",
    "應揭露之支出對象", "支出對象之內部人員姓名", "支出對象之內部人員職稱",
    "政黨之內部人員姓名", "政黨之內部人員職稱", "關係", "更正註記", "資料更正日期")
TW_CATEGORY, TW_DONOR, TW_SERIAL = "收支科目", "捐贈者／支出對象", "申報序號／年度"
#: The candidate's column, the one a report with no income fills in
#: the single row it writes, every other column holding TW_EMPTY.
TW_CANDIDATE = "擬參選人／政黨"
#: The columns every file must hold, the ones read.
TW_NEEDED = frozenset({TW_CATEGORY, TW_DONOR, TW_SERIAL, TW_CANDIDATE})
TW_EMPTY = "-"
TW_INDIVIDUAL = "個人捐贈收入"
#: The income categories a candidate's report holds (the platform's
#: classTypes with ctrlTp 0): individual, business, party and civic
#: group donations, anonymous gifts, other income.
TW_CATEGORIES = frozenset({
    TW_INDIVIDUAL, "營利事業捐贈收入", "政黨捐贈收入", "人民團體捐贈收入",
    "匿名捐贈", "其他收入"})
#: A report's serial: 1 the first report, 2 to 6 the five reports on
#: the money left over.
TW_SERIALS = range(1, 7)
_TW_NUMERALS = "一二三四五"
#: A donor cell that holds no name: anonymous (19 individual donations
#: wrote it on 2026-10-22) or a dash.
TW_NO_NAME = frozenset({"匿名", TW_EMPTY})
#: A character that masks part of a name (3 donor names held an
#: asterisk on 2026-10-22): such a name is counted, not kept.
_TW_MASK = re.compile(r"[*＊○]")
#: More than this share of the fetch's rows not as long as their file's
#: header, without a category, or cut off by a stray quote, or of its
#: individual donations naming a masked donor, refuses the fetch, as
#: FEC_MAX_BAD does. One 2021 residual report held a row with no
#: category, an income of NT$53 with no donor ID (2026-10-22).
TW_MAX_BAD = 1 / 10_000
#: More than this share of ONE report's rows bad refuses the fetch too:
#: the share over the whole fetch would let a small report's rows all
#: go (the worst report on 2026-10-22 had 1 bad row of 6).
TW_MAX_REPORT_BAD = 1 / 2
#: What a row is counted as when it is read past without a name.
_TW_BAD = ("rows_not_as_long_as_the_header", "rows_without_a_category",
           "rows_cut_by_a_stray_quote")


def _tw_reports() -> list[dict[str, Any]]:
    """Every election report the platform lists, paged: the listing is
    what says a report exists, since the download answers a report that
    does not and a fault alike, with a 500 and an incident number. Two
    reports listed under one zip name are refused, since the cache keeps
    a zip by its name."""
    reports: list[dict[str, Any]] = []
    seen: set[tuple[str, str, int]] = set()
    zips: set[object] = set()
    page, count = 1, None
    while count is None or len(reports) < count:
        query = urllib.parse.urlencode({"page": page, "pageSize": TW_PAGE})
        data = _get_json(f"{TW_API}/search/elections?{query}")
        count = int(data["paging"]["recordCount"])
        if not data["data"]:
            break
        for row in data["data"]:
            serial = row["yearOrSerial"]
            if row["type"] != "Election" or serial not in TW_SERIALS:
                raise ValueError(f"a listed report is not an election's first or "
                                 f"residual report: type {row['type']!r}, serial "
                                 f"{serial!r}; the listing has changed")
            key = (row["electionName"], row["electionArea"], int(serial))
            if key in seen:
                raise ValueError(f"{key} was listed twice: the listing shifted "
                                 f"under the fetch; fetch again")
            if row["zipFileName"] in zips:
                raise ValueError(f"{key} is listed under the zip name "
                                 f"{row['zipFileName']!r} another report has")
            seen.add(key)
            zips.add(row["zipFileName"])
            reports.append(row)
        page += 1
    if len(reports) != count:
        raise ValueError(f"listed {len(reports):,} reports of the {count:,} the "
                         f"platform counted; fetch again")
    return reports


def _tw_versions(reports: list[dict[str, Any]]) -> set[tuple[str, str, int, str]]:
    """Each report with the zip its listing names, which carries the
    date the platform built it: a replaced report lists another."""
    return {(r["electionName"], r["electionArea"], int(r["yearOrSerial"]),
             r["zipFileName"]) for r in reports}


def _tw_url(report: dict[str, Any]) -> str:
    """A report's zip, asked for by the fields its listing row gives."""
    return f"{TW_API}/Search/download?" + urllib.parse.urlencode({
        "ElectionName": report["electionName"],
        "ElectionArea": report["electionArea"], "AccountNumber": "",
        "YearOrSerial": int(report["yearOrSerial"]), "Version": "",
        "SearchType": 2, "DownloadType": 3})


def _tw_serial_names(serial: int) -> frozenset[str]:
    """How a report's rows write its serial: 首次申報 for the first, 第N次賸餘
    for a residual one, N in either numerals (both are written)."""
    if serial == 1:
        return frozenset({"首次申報"})
    return frozenset({f"第{serial - 1}次賸餘", f"第{_TW_NUMERALS[serial - 2]}次賸餘"})


def _tw_incomes(body: bytes) -> tuple[bytes, str] | None:
    """A report zip's incomes.csv and its timestamp, None where the zip
    holds none, or ValueError where the body is no whole zip or its
    member does not inflate: a download cut short or damaged, which
    _retried retries."""
    try:
        with zipfile.ZipFile(io.BytesIO(body)) as archive:
            if TW_INCOMES not in archive.namelist():
                return None
            member = archive.getinfo(TW_INCOMES)
            stamp = _zip_stamp(member)
            return archive.read(member), stamp
    except (zipfile.BadZipFile, zlib.error, EOFError) as exc:
        start = body[:2]
        raise ValueError(f"not a whole zip ({type(exc).__name__}: {exc}; it starts "
                         f"{start!r})") from None


#: The cached reports' folder, beside the corpus.
TW_REPORTS = "reports"
#: A listed zip's name, the only kind cached under it: the name is the
#: platform's and becomes a path.
_TW_ZIP_NAME = re.compile(r"[\w-]+\.zip", re.ASCII)


def _tw_cached(report: dict[str, Any]) -> Path:
    return directory("tw-donors") / TW_REPORTS / report["zipFileName"]


def _tw_report_zip(report: dict[str, Any],
                   label: str) -> tuple[bytes, str, bytes | None]:
    """A listed report's incomes.csv, its timestamp, and the zip when it
    was downloaded rather than read from the reports folder, where an
    earlier fetch cached it under the name the listing gives. The name
    carries the date the platform built the zip, so a rebuilt report is
    downloaded anew, and a cached zip that is no whole zip is too. A zip
    holding no incomes.csv is refused without being retried: a layout
    the tool was not written for, or one bad answer. The caller caches a
    downloaded zip only once its rows are read (_tw_cache_zip), since a
    cached zip that is refused would refuse every later fetch."""
    name = report["zipFileName"]
    if not isinstance(name, str) or not _TW_ZIP_NAME.fullmatch(name):
        raise ValueError(f"{label} is listed with the zip name {name!r}, which is "
                         f"no file name this tool caches; the listing has changed")
    path = _tw_cached(report)
    if path.exists():
        try:
            if got := _tw_incomes(path.read_bytes()):
                return (*got, None)
        except ValueError:
            print(f"  downloading again a cached zip that is not whole: {path}",
                  file=sys.stderr)
    # Read inside _retried, so that a zip cut short is retried, and once.
    body, got = _retried(_tw_url(report), lambda body: (body, _tw_incomes(body)),
                         TW_DELAY)
    if got is None:
        raise ValueError(f"{label}'s zip holds no {TW_INCOMES}: the reports' "
                         f"layout has changed")
    return (*got, body)


def _tw_cache_zip(report: dict[str, Any], body: bytes) -> None:
    path = _tw_cached(report)
    path.parent.mkdir(exist_ok=True)
    corpus_build.write_atomic(path, body)


def _tw_lines(text: str) -> list[str]:
    """`text` cut into its lines at CRLF, CR or LF, each keeping its
    ending, as csv reads a file opened with newline="" and no further:
    str.splitlines() would cut at U+2028 and the other separators too,
    which a name may hold (corpus_build.jsonl_lines)."""
    return re.findall(r"[^\r\n]*(?:\r\n|\r|\n)|[^\r\n]+$", text)


def _tw_rows(text: str, width: int, counts: Counter[str]) -> Iterator[list[str]]:
    """incomes.csv's records after its header. A record whose field
    holds line breaks is a quoted field spanning lines, or a stray quote
    opening a field and taking the rows after it in until another quote
    closes it: on 2026-10-22, 12 records in three reports took in 169
    rows that way, and every line of all 12 read as a whole row with
    quotes taken literally. So where every line of a record does, those
    are its rows; this also parts two rows that two stray quotes, one
    after the other, joined into one record exactly as wide as the
    header (8 of the 12). Else, where one of the lines after its first
    reads as a whole row alone as quoted, the record is cut back into
    its lines, each read alone: the lines as wide as the header are
    rows, and the rest are counted as cut by the quote. Otherwise it
    stays one record, a quoted field that truly spans lines."""
    lines = _tw_lines(text)
    reader = csv.reader(lines)
    next(reader, None)
    start = reader.line_num
    for record in reader:
        end = reader.line_num
        if end - start > 1:
            literal = [next(csv.reader([line], quoting=csv.QUOTE_NONE), [])
                       for line in lines[start:end]]
            if all(len(row) == width for row in literal):
                counts["records_cut_back_into_their_lines"] += 1
                yield from literal
                start = end
                continue
            alone = [next(csv.reader([line]), []) for line in lines[start:end]]
            if any(len(row) == width for row in alone[1:]):
                counts["records_cut_back_into_their_lines"] += 1
                for row in alone:
                    if len(row) == width:
                        yield row
                    else:
                        counts["rows_cut_by_a_stray_quote"] += 1
                start = end
                continue
        start = end
        yield record


def _tw_read(incomes: bytes, report: dict[str, Any], label: str, names: set[str],
             counts: Counter[str]) -> None:
    """Add a report's donor names to `names`, counting into `counts`
    what is read past. A header or a category this tool was not written
    for is refused, not read: a moved column would put another field's
    values in the corpus, so a header holding a column TW_HEADER does
    not name, a column twice, or not every column TW_NEEDED names is
    refused; one missing a column the tool does not read is read. A row
    whose serial is not the report's is refused: the zip is another
    report's. The one row a report with no income writes, every column a
    dash but the candidate's, is counted apart."""
    try:
        text = incomes.decode("utf-8-sig")
    except UnicodeDecodeError as exc:
        raise ValueError(f"{label}'s {TW_INCOMES} is not UTF-8 ({exc})") from None
    header = next(csv.reader(_tw_lines(text)), [])
    if (not set(header) <= set(TW_HEADER) or len(set(header)) != len(header)
            or not TW_NEEDED <= set(header)):
        raise ValueError(f"{label}'s {TW_INCOMES} has the header {tuple(header)}, "
                         f"which is not columns of TW_HEADER, each once, holding "
                         f"those TW_NEEDED names")
    category_at, donor_at, serial_at, candidate_at = (
        header.index(column) for column in (TW_CATEGORY, TW_DONOR, TW_SERIAL, TW_CANDIDATE))
    serials = _tw_serial_names(int(report["yearOrSerial"]))
    mine = Counter[str]()
    try:
        rows = list(_tw_rows(text, len(header), mine))
    except csv.Error as exc:
        raise ValueError(f"{label}'s {TW_INCOMES} is not a CSV file csv can "
                         f"read ({exc})") from None
    for row in rows:
        mine["rows"] += 1
        if len(row) != len(header):
            mine["rows_not_as_long_as_the_header"] += 1
            continue
        if {f for i, f in enumerate(row) if i != candidate_at} == {TW_EMPTY}:
            mine["rows_of_a_report_with_no_income"] += 1
            continue
        category = row[category_at]
        if not category:
            mine["rows_without_a_category"] += 1
            continue
        if category not in TW_CATEGORIES:
            raise ValueError(f"{label}'s {TW_INCOMES} holds the category "
                             f"{category!r}, which TW_CATEGORIES does not list")
        if row[serial_at] not in serials:
            raise ValueError(f"{label}'s {TW_INCOMES} holds a row of the report "
                             f"{row[serial_at]!r}: the zip is another report's")
        if category != TW_INDIVIDUAL:
            mine["rows_from_other_categories"] += 1
            continue
        mine["individual_donations"] += 1
        name = row[donor_at].strip()
        if not name or name in TW_NO_NAME:
            mine["donations_without_a_name"] += 1
        elif _TW_MASK.search(name):
            mine["donations_naming_a_masked_donor"] += 1
        else:
            names.add(name)
    bad = sum(mine[key] for key in _TW_BAD)
    if bad > (mine["rows"] + mine["rows_cut_by_a_stray_quote"]) * TW_MAX_REPORT_BAD:
        raise ValueError(f"{bad:,} of {label}'s rows are read past as malformed: "
                         f"the file's layout has changed")
    counts.update(mine)


def fetch_tw() -> Fetched:
    """The distinct names of every individual donor in every election
    report the platform lists, one record per name.

    Every report is read, the first and the residual ones alike, and a
    name is kept once however many reports, candidates or elections it
    gave to, as the FEC source keeps one per name. Only the donor column
    of the rows the category marks as individual donations is kept, its
    spaces stripped; the masked ID, address and phone columns and the
    amounts are read past, and a donor cell that holds no name or a
    masked one is counted. Each report's zip is cached
    (_tw_report_zip), so a fetch cut short or refused goes on where it
    stopped, and a refresh downloads only the reports published or
    rebuilt since: a zip rebuilt under the name it had is not seen, and
    deleting the reports folder downloads every one again. A cached zip
    the listing no longer names is deleted at the end of a fetch that
    passes its checks, and a downloaded zip is cached only once its rows
    are read, so a zip refused is downloaded again rather than refused
    from the cache for good. The listing is read again at the end, and a
    report published, replaced or withdrawn during the fetch refuses it.
    The data date is the newest incomes.csv's own timestamp, which
    carries no time zone."""
    reports = _tw_reports()
    names: set[str] = set()
    counts: Counter[str] = Counter()
    stamps: list[str] = []
    for number, report in enumerate(reports, 1):
        if number % 50 == 0:
            print(f"  {number:,} of {len(reports):,} reports", file=sys.stderr)
        label = f"{report['electionName']} {report['electionArea']} " \
                f"report {int(report['yearOrSerial'])}"
        incomes, stamp, downloaded = _tw_report_zip(report, label)
        stamps.append(stamp)
        _tw_read(incomes, report, label, names, counts)
        if downloaded is not None:
            _tw_cache_zip(report, downloaded)
    rows, donations = counts["rows"], counts["individual_donations"]
    _refuse_past([(counts["rows_not_as_long_as_the_header"], rows, TW_MAX_BAD,
                   "rows are not as long as their file's header"),
                  (counts["rows_without_a_category"], rows, TW_MAX_BAD,
                   "rows are without a category"),
                  (counts["rows_cut_by_a_stray_quote"], rows, TW_MAX_BAD,
                   "rows are cut by a stray quote"),
                  (counts["donations_naming_a_masked_donor"], donations, TW_MAX_BAD,
                   "individual donations name a masked donor")],
                 "the files' layout has changed")
    if _tw_versions(_tw_reports()) != _tw_versions(reports):
        raise ValueError("the platform published, replaced or withdrew a report "
                         "during the fetch; fetch again")
    listed = {r["zipFileName"] for r in reports}
    for stale in (directory("tw-donors") / TW_REPORTS).glob("*.zip"):
        if stale.name not in listed:
            stale.unlink()
    detail: dict[str, Any] = {
        "reports": len(reports),
        "first_reports": sum(int(r["yearOrSerial"]) == 1 for r in reports),
        "elections": len({r["electionName"] for r in reports})}
    for key in ("rows", "individual_donations", "rows_from_other_categories",
                "donations_without_a_name", "donations_naming_a_masked_donor",
                "rows_of_a_report_with_no_income", "records_cut_back_into_their_lines",
                *_TW_BAD):
        detail[key] = counts[key]
    return Fetched([{"name": name} for name in sorted(names)], max(stamps, default=""),
                   detail)
