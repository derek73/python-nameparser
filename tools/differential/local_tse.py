"""The tse-donors local corpus: Brazil's TSE campaign donors.

tse-donors -- every individual donor to a candidate in Brazil's 2022
general and 2024 municipal elections, from the TSE's candidates'
accounts (receitas, rows whose origin is "Recursos de pessoas
físicas"): the name as the campaign's accounts filed it, beside the
federal tax registry's name for the same CPF. Each election's national
member is read from the CDN in ranges, not downloaded whole, so a
fetch (the first, or `fetch --refresh`) reads the current file. A record
is a pair, so counts are of pairs. Like the FEC's, nearly all in capitals
(845,498 of 848,351 filed names fetched 2026-10-22) but in spoken order
with no comma (184 records held one), and with particles (DE, DA, DOS) and
agnomens (FILHO, NETO, JUNIOR) throughout. The portal publishes the data
under CC BY, which the credit line names; only the two name columns are
kept, and the CPF beside them, unmasked in the file, is read past.
"""
from __future__ import annotations

import csv
import http.client
import io
import sys
import urllib.request
import zipfile
import zlib
from collections import Counter
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from _typeshed import WriteableBuffer

import local_core
from local_core import Fetched, _backed_off, _pinned, _refuse_past, _zip_stamp


#: The latest general election and the latest municipal one. An older
#: election is one more year here: 2018's national member was 26 MB
#: compressed and 2020's 203 MB on 2026-10-22; 2014 and 2016 publish no
#: zip at this path.
TSE_ELECTIONS = ("2022", "2024")
TSE_URL = ("https://cdn.tse.jus.br/estatistica/sead/odsele/prestacao_contas/"
           "prestacao_de_contas_eleitorais_candidatos_{year}.zip")
#: Every state's receipts in one member (its Bahia rows were the 2022
#: state member's 10,788, row for row, in the file dated 2026-10-18);
#: the per-state members repeat
#: it, and the doador_originario members name who gave to a party
#: before the party passed the money on, a different question.
TSE_MEMBER = "receitas_candidatos_{year}_BRASIL.csv"
#: The header's width and the three columns read, found by name: 60
#: columns in 2022 and 2024.
TSE_COLUMNS = 60
TSE_ORIGIN, TSE_NAME, TSE_REGISTRY = "DS_ORIGEM_RECEITA", "NM_DOADOR", "NM_DOADOR_RFB"
TSE_INDIVIDUALS = "Recursos de pessoas físicas"
#: Every DS_ORIGEM_RECEITA value 2022 and 2024 hold. A value outside it
#: refuses the file, since a renamed TSE_INDIVIDUALS would otherwise
#: read as an election with no individual donors, and a file no longer
#: in Latin-1 shows here first (físicas spelled another way).
TSE_ORIGINS = frozenset({
    TSE_INDIVIDUALS, "Recursos de partido político", "Recursos de outros candidatos",
    "Recursos próprios", "Recursos de Financiamento Coletivo", "#NULO",
    "Rendimentos de aplicações financeiras", "Recursos de origens não identificadas",
    "Doações pela Internet", "Comercialização de Bens com OR",
    "Comercialização de Bens com FEFC"})
#: The bytes a Range request asks for: 43 requests read 2022's member
#: in the file dated 2026-10-18.
TSE_BLOCK = 1 << 20
#: As local_fec.FEC_MAX_BAD, for rows that are not TSE_COLUMNS columns and for
#: physical lines that fall inside a quoted field (a quote left open,
#: or a line break typed into a name): none of 2,715,955 rows in the
#: two files dated 2026-10-18 and 2026-10-23 was either.
TSE_MAX_BAD = 1 / 10_000
#: An election is refused where fewer of its rows than this are from
#: individuals (78% of 2022's and 28% of 2024's on 2026-10-22), since a
#: member published as its header alone, or with the individuals'
#: donations moved under another listed category, would otherwise pass
#: as an election with few donors; where more of its individuals' rows
#: than TSE_MAX_MISSING carry no name or no registry name, a value with
#: no letter counted as none (20 and 41 rows did, in the files dated
#: 2026-10-18 and 2026-10-23), which is what a masked column would
#: show; where more than TSE_MAX_NUMBERED carry a number beside letters
#: (7 and 42 did), which is what a numeric column moved under a name
#: would show; or where its distinct filed names, or its distinct
#: registry names, are fewer than TSE_MIN_DISTINCT of its individuals'
#: rows (filed names 89% of 2022's and 72% of 2024's on 2026-10-22),
#: which is what a column masked with one word would show.
TSE_MIN_INDIVIDUALS = 1 / 10
TSE_MAX_MISSING = 1 / 100
TSE_MAX_NUMBERED = 1 / 1000
TSE_MIN_DISTINCT = 1 / 4
#: A name holding more digits than this is not kept, nor its pair: some
#: campaigns typed a number into the name field (98 individuals' rows
#: in the files dated 2026-10-18 and 2026-10-23 before a name with no
#: letter was counted as missing, 54 of their names exactly 11 digits,
#: a CPF's length), and a record must hold no identifier. No registry
#: name held more than 4.
TSE_MAX_DIGITS = 4
#: An unknown DS_ORIGEM_RECEITA value is quoted in the refusal only when
#: it holds no digit and at least this many rows, and this share of all
#: rows, hold it, as a category does: a header that no longer matches
#: its rows puts names and CPFs in that column, and a frequent donor's
#: name can repeat, but not in a thousandth of an election's rows.
TSE_QUOTED_ORIGIN = 10
TSE_QUOTED_SHARE = 1 / 1000
#: The file is Latin-1 by its bytes but written from Windows: read as
#: cp1252, where the five bytes cp1252 leaves undefined stay Latin-1.
#: One byte in 0x80-0x9F appeared in 2022's 432 MB, in no name, and none
#: in 2024's (files dated 2026-10-18 and 2026-10-22).
_CP1252 = {b: bytes([b]).decode("cp1252") for b in range(0x80, 0xA0)
           if b not in (0x81, 0x8D, 0x8F, 0x90, 0x9D)}


class _RangeFile(io.RawIOBase):
    """A file on the TSE's CDN read by HTTP Range requests, for zipfile:
    the national member of a candidates' zip without the zip around it
    (41 MB of 467 MB for 2022, 168 MB of 1.36 GB for 2024, on
    2026-10-22). Every range request carries If-Range with the strong
    validator the HEAD gave, so a file replaced during the read is
    answered whole instead of in part, which is refused, as is a part
    whose Content-Range is not the range asked for: the TSE regenerates
    these zips every few days (all four of 2018-2024 were stamped within
    the week before 2026-10-22), and a member read across two versions
    would be neither."""

    def __init__(self, url: str) -> None:
        super().__init__()
        self.url, self.position = url, 0
        #: The error a request ended on: zipfile turns an OSError raised
        #: while it looks for the end of the archive into a BadZipFile
        #: that does not name it, and fetch_tse raises this instead.
        self.error: Exception | None = None
        request = urllib.request.Request(url, method="HEAD",
                                         headers={"User-Agent": local_core.USER_AGENT})
        _, headers, _ = self._request(request)
        length = headers.get("Content-Length", "")
        etag = headers.get("ETag", "")
        # If-Range takes a strong validator only (RFC 9110 13.1.5): a
        # server answers a weak ETag with the whole file every time.
        self.validator = (etag if etag and not etag.startswith("W/")
                          else headers.get("Last-Modified", ""))
        if (not length.isdigit() or not self.validator
                or headers.get("Accept-Ranges", "bytes") != "bytes"):
            raise ValueError(f"{url} states no length, no strong ETag or "
                             f"Last-Modified, or no byte ranges: a read in ranges "
                             f"could not tell a replaced file from this one")
        self.size = int(length)

    def readable(self) -> bool:
        return True

    def seekable(self) -> bool:
        return True

    def tell(self) -> int:
        return self.position

    def seek(self, offset: int, whence: int = io.SEEK_SET) -> int:
        base = {io.SEEK_SET: 0, io.SEEK_CUR: self.position, io.SEEK_END: self.size}
        if whence not in base or base[whence] + offset < 0:
            raise OSError(f"cannot seek to {offset} from {whence} in {self.url}")
        self.position = base[whence] + offset
        return self.position

    def readinto(self, buffer: WriteableBuffer, /) -> int:
        view = memoryview(buffer).cast("B")
        want = min(len(view), self.size - self.position)
        if want <= 0:
            return 0
        data = self._range(self.position, want)
        view[:want] = data
        self.position += want
        return want

    def _range(self, start: int, want: int) -> bytes:
        """`want` bytes from `start`. A part that is not the range asked
        for raises a ValueError naming what came instead."""
        end = start + want - 1
        request = urllib.request.Request(self.url, headers={
            "User-Agent": local_core.USER_AGENT, "If-Range": self.validator,
            "Range": f"bytes={start}-{end}"})
        status, headers, data = self._request(request, want)
        if status != 206:
            self.error = ValueError(
                f"{self.url} answered a range request whole (HTTP {status}): "
                f"the file changed during the fetch, or the server no longer "
                f"serves ranges; fetch again")
            raise self.error
        stated = headers.get("Content-Range", "")
        if stated != f"bytes {start}-{end}/{self.size}" or len(data) > want:
            self.error = ValueError(
                f"{self.url} answered bytes {start}-{end} of {self.size:,} with "
                f"{stated or 'no Content-Range'} and {len(data):,} bytes; fetch again")
            raise self.error
        return data

    def _request(self, request: urllib.request.Request, want: int | None = None
                 ) -> tuple[int, Any, bytes]:
        """The status, headers and body of `request`'s answer, retried under
        local_core's policy (_backed_off), Retry-After included (a member
        is up to about 170 requests, and starting over costs them all). The body is read only from a 206,
        up to one byte past `want` so that a longer part shows; a shorter
        one is retried as a body cut short. The last attempt's error, or
        any 4xx but a 429, is kept in self.error and raised."""
        for attempt in range(local_core.RETRIES):
            try:
                with urllib.request.urlopen(request, timeout=60) as response:
                    body = b""
                    if want is not None and response.status == 206:
                        body = response.read(want + 1)
                        if len(body) < want:
                            raise http.client.IncompleteRead(body, want - len(body))
                    return response.status, response.headers, body
            except local_core._TRANSIENT as exc:
                if not _backed_off(exc, attempt, self.url):
                    self.error = exc
                    raise
        raise AssertionError("unreachable: the last attempt raises")


def _tse_read(year: str, archive: zipfile.ZipFile,
              pairs: set[tuple[str, str]]) -> tuple[str, dict[str, int]]:
    """Add one election's individual donors to `pairs`; the member's
    timestamp and the counts."""
    member = TSE_MEMBER.format(year=year)
    if member not in archive.namelist():
        raise ValueError(f"{TSE_URL.format(year=year)} holds no {member}")
    info = archive.getinfo(member)
    stamp = _zip_stamp(info)
    counts: Counter[str] = Counter()
    before = len(pairs)
    distinct: set[tuple[str, str]] = set()
    with archive.open(info) as binary, \
            io.TextIOWrapper(binary, encoding="latin-1", newline="") as text:
        rows = csv.reader(text, delimiter=";")
        header = next(rows, [])
        missing = [c for c in (TSE_ORIGIN, TSE_NAME, TSE_REGISTRY) if c not in header]
        if len(header) != TSE_COLUMNS or missing:
            raise ValueError(f"{member}'s header is {len(header)} columns, not "
                             f"{TSE_COLUMNS}, or lacks {', '.join(missing) or '-'}: "
                             f"the file's layout has changed")
        origin, name_at, registry_at = (header.index(c) for c in
                                        (TSE_ORIGIN, TSE_NAME, TSE_REGISTRY))
        unknown: Counter[str] = Counter()
        for row in rows:
            counts["rows"] += 1
            if len(row) != TSE_COLUMNS:
                counts["malformed"] += 1
                continue
            if row[origin] not in TSE_ORIGINS:
                unknown[row[origin]] += 1
            if row[origin] != TSE_INDIVIDUALS:
                continue
            counts["individual"] += 1
            raw_name, raw_registry = row[name_at], row[registry_at]
            name = raw_name.translate(_CP1252).strip()
            registry = raw_registry.translate(_CP1252).strip()
            counts["cp1252"] += name != raw_name.strip() or registry != raw_registry.strip()
            if _missing(name):
                counts["nameless"] += 1
                continue
            if _missing(registry):
                registry = ""
            if max(_digits(name), _digits(registry)) > TSE_MAX_DIGITS:
                counts["numbered"] += 1
                continue
            counts["no_registry"] += not registry
            distinct.add((name, registry))
        # The physical lines read past the header, against the rows: a
        # line inside a quoted field, a quote left open or a line break
        # typed into a name, is read without making a row.
        folded = rows.line_num - 1 - counts["rows"]
    pairs |= distinct
    if unknown:
        floor = max(TSE_QUOTED_ORIGIN, counts["rows"] * TSE_QUOTED_SHARE)
        common = sorted(v for v, n in unknown.items()
                        if n >= floor and not _digits(v))
        shown = (f"such as {common[0]!r}" if common else
                 "none held by enough rows to be a category (not shown)")
        raise ValueError(f"{member} holds {len(unknown)} {TSE_ORIGIN} value(s) "
                         f"outside TSE_ORIGINS, {shown}: the file's categories, "
                         f"its layout or its encoding have changed")
    for count, what in ((counts["malformed"], f"rows not {TSE_COLUMNS} columns"),
                        (folded, "lines folded into another row's field")):
        if count > counts["rows"] * TSE_MAX_BAD:
            raise ValueError(f"{member} holds {count:,} {what} in {counts['rows']:,} "
                             f"rows: the file's layout has changed")
    if counts["individual"] < counts["rows"] * TSE_MIN_INDIVIDUALS or not counts["individual"]:
        raise ValueError(f"{counts['individual']:,} of {counts['rows']:,} rows of "
                         f"{member} are from individuals: the file is cut short or "
                         f"its categories have moved")
    carry = f"individuals' rows of {member} carry"
    _refuse_past([(counts["nameless"], counts["individual"], TSE_MAX_MISSING, f"{carry} no name"),
                  (counts["no_registry"], counts["individual"], TSE_MAX_MISSING,
                   f"{carry} no registry name"),
                  (counts["numbered"], counts["individual"], TSE_MAX_NUMBERED,
                   f"{carry} a number in a name")],
                 "a name column may be masked or moved")
    for column, index in ((TSE_NAME, 0), (TSE_REGISTRY, 1)):
        seen = len({pair[index] for pair in distinct})
        if seen < counts["individual"] * TSE_MIN_DISTINCT:
            raise ValueError(f"{member}'s {counts['individual']:,} individuals' rows "
                             f"hold {seen:,} distinct {column}: the column may be masked")
    return stamp, {f"{year}_rows": counts["rows"],
                   f"{year}_rows_from_individuals": counts["individual"],
                   f"{year}_records": len(distinct),
                   f"{year}_new_records": len(pairs) - before,
                   f"{year}_rows_not_{TSE_COLUMNS}_columns": counts["malformed"],
                   f"{year}_lines_folded_into_a_field": folded,
                   f"{year}_individuals_without_a_name": counts["nameless"],
                   f"{year}_individuals_without_a_registry_name": counts["no_registry"],
                   f"{year}_individuals_whose_name_holds_a_number": counts["numbered"],
                   f"{year}_rows_read_as_cp1252": counts["cp1252"]}


def _digits(text: str) -> int:
    return sum(char.isdigit() for char in text)


def _missing(name: str) -> bool:
    """No name: empty, a placeholder the TSE writes with a leading # (its
    #NULO, #NE), or one with no letter (***, -4)."""
    return name.startswith("#") or not any(char.isalpha() for char in name)


def fetch_tse() -> Fetched:
    """The individual donors to candidates in each of TSE_ELECTIONS, one
    record per distinct pair of NM_DOADOR, the name as the candidate's
    accounts filed it, and NM_DOADOR_RFB, the federal tax registry's
    name for the same donor's CPF: a typed name with its reference form
    beside it (the pairs differ in 205,925 of 854,531 records fetched
    2026-10-22). A donor in both elections under the same pair is one
    record; under two spellings, two.

    Only those two columns are read into a record. The CPF beside them is
    unmasked in the file, and like every other column it is read past,
    never stored or printed; a pair either of whose names holds more than
    TSE_MAX_DIGITS digits is dropped and counted, since a number typed
    into the name field may be one. Each election's national member is
    read in ranges from the CDN (_RangeFile) rather than cached: the
    zips are replaced every few days, so a cached one goes stale within
    the week, and a fetch reads 209 MB of members where the zips are
    1.82 GB (2026-10-22). A row that is not TSE_COLUMNS columns, or a
    line folded into another row's field, is counted, past TSE_MAX_BAD
    refusing the file, as do a zip without the national member, a header
    that is not TSE_COLUMNS wide or lacks the three columns, a category
    outside TSE_ORIGINS, too few rows from individuals
    (TSE_MIN_INDIVIDUALS), too many without a name or a registry name
    (TSE_MAX_MISSING) or with a number in one (TSE_MAX_NUMBERED), and
    too few distinct pairs (TSE_MIN_DISTINCT)."""
    pairs: set[tuple[str, str]] = set()
    detail: dict[str, Any] = {"elections": " ".join(TSE_ELECTIONS)}
    stamps = []
    for year in TSE_ELECTIONS:
        url = TSE_URL.format(year=year)
        print(f"reading {TSE_MEMBER.format(year=year)} from {url} ...", file=sys.stderr)
        reader = _RangeFile(url)
        try:
            with zipfile.ZipFile(io.BufferedReader(reader, TSE_BLOCK)) as archive:
                stamp, counts = _tse_read(year, archive, pairs)
        except zipfile.BadZipFile as exc:
            if reader.error is not None:
                raise reader.error from None
            raise ValueError(f"{url} is not a readable zip ({exc}); fetch again") from None
        except (csv.Error, zlib.error, EOFError) as exc:
            raise ValueError(f"{TSE_MEMBER.format(year=year)} in {url} cannot be "
                             f"read ({type(exc).__name__}: {exc}); fetch again") from None
        stamps.append(f"{stamp} ({year})")
        detail.update(counts)
    detail["records_whose_name_differs_from_the_registry"] = sum(
        name != registry for name, registry in pairs)
    return Fetched([{"name": name, "registry": registry}
                    for name, registry in sorted(pairs)], ", ".join(stamps), detail)


check_tse = _pinned("elections", lambda: " ".join(TSE_ELECTIONS),
                    "holds the elections {held}, and this tool reads {wanted}")
