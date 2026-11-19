"""The my-candidates local corpus: Malaysia's election candidates, as
their ballots name them.

my-candidates -- the candidates of Malaysia's general elections GE12
(2008) to GE15 (2022) and of the six state elections of 2023 (PRN15),
from Thevesh Theva's analysis-election-msia repository on GitHub
(`data/candidates_<election>.csv`), pinned here by commit and by each
file's sha256. A row is one candidacy: on 2026-11-19 the five files held
480, 579, 687, 945 and 570 rows. The names are written in capitals, as
the Election Commission gazettes them, save one candidate's, written in
mixed case in each of GE12 to GE14 (`Xxx Yyy ZZZ`, its last word in
capitals).

Which column holds that writing differs by file, and is read so
(FILES): GE12 to GE14 have one, `name`, the name as it stood on the
ballot (often shortened: the full name's `BIN X` dropped, an honorific
added). GE15 has two: `name_display`, the ballot name in capitals,
and `name`, the full name recased by the repository's author into title
case (`Xxx Bin Yyy`); the capitals it was recased from are not in the
file, and recasing it back would be a guess (the mixed-case name above
shows a writer's case is not always capitals), so only `name_display`
is read. PRN15 has two, both in capitals: `name_ballot`, the ballot
name, and `name`, the full name; both are read, as the forms `ballot`
and `full`. So every election gives its ballot names, and PRN15 its full
names too, the population with the most `BIN` and `BINTI`.

The shapes it holds and the other corpora barely do: Malay names joined
by `BIN`, `BINTI`, `B.`, `BT` and `@` (an alias, `X @ Y`); Indian names
joined by `A/L` and `A/P`; Iban and other Sarawak names joined by
`ANAK`; `MD` and `MOHD` as given names; honorifics opening a ballot name
(`USTAZ`, `CIKGU`, `DR`, `HJ`, `KAPT (B)`); and Chinese names written
family first in capitals, beside a Western given name or not (#1467,
#1468, #1164, #1183, #1179). Each record keeps the candidate's
`ethnicity` as the file writes it, the group config_diff.py --group
keeps (GE12 to GE15 write `bumiputera`, which takes in Sabah's and
Sarawak's peoples beside the Malays, and PRN15, whose six states are all
in the peninsula, writes `malay`; `chinese`, `indian` and `other` in
all), and its `election`.

A record is one distinct spelling within an election and ethnicity: a
candidate standing in two seats of one election is one record, and a
full name equal to its ballot name is recorded once, as the ballot
name. It holds no fields, so it is a snapshot.py --local population,
not a local_agreement.py one.

The repository is licensed under the GPL-3.0; the names are candidates'
as the Election Commission published them. They are cached, never
committed or shipped, and what reaches the repository is counts and
made-up names.
"""
from __future__ import annotations

import csv
import hashlib
import io
import sys
from collections import Counter
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from local_core import Fetched, _pinned, _refuse_past, _retried


MY = "my-candidates"
#: The commit the files are read from: the repository's last, of
#: 2023-08-13, when read on 2026-11-19, so a pin both names the data
#: exactly and refuses a file cut in transit or changed upstream.
MY_COMMIT = "b20331b0aef7efa4ab3ad6df83b188663771d9eb"
MY_DATE = "2023-08-13"
MY_URL = ("https://raw.githubusercontent.com/Thevesh/analysis-election-msia/"
          "{commit}/data/{file}")


@dataclass(frozen=True)
class File:
    """One election's file: its name, sha256 and rows at MY_COMMIT, its
    header exactly, and the column read for each form."""
    election: str
    file: str
    sha256: str
    rows: int
    header: tuple[str, ...]
    forms: tuple[tuple[str, str], ...]


_GE_HEADER = ("state", "parlimen", "ballot_order", "name", "age", "sex", "ethnicity",
              "party", "votes", "result", "result_desc")
#: The files read, in order. A form is ("ballot", column) or ("full",
#: column); the module docstring says why each column is the one read.
FILES = (
    File("ge12", "candidates_ge12.csv",
         "592ab00dbf96fc643ccbfd5c0715ed5b6ae55470e263cd2a13dff268bc60980f", 480,
         _GE_HEADER, (("ballot", "name"),)),
    File("ge13", "candidates_ge13.csv",
         "dee0046e7e47210f93893c9749b968420da9e5baca21b07a5ad57eab14d7fc4e", 579,
         _GE_HEADER, (("ballot", "name"),)),
    File("ge14", "candidates_ge14.csv",
         "4a8c0c4db659c572522b701e60b80c9d945f23e439a657c00fe4e55dda03fb8e", 687,
         _GE_HEADER, (("ballot", "name"),)),
    File("ge15", "candidates_ge15.csv",
         "6eef7ef032a64bd3492812b3971ca0e2a4204cb71d72e8daef0559146b4c0204", 945,
         ("state", "parlimen", "ballot_order", "name", "name_display", "age", "sex",
          "ethnicity", "party", "votes", "result", "result_desc", "new_mp"),
         (("ballot", "name_display"),)),
    File("prn15", "candidates_prn15.csv",
         "1669a1e78bbdc67347f549fa091032d94071a5cc207ccaef1c2bc5db12ef5c0c", 570,
         ("state", "parlimen", "dun", "ballot_order_x", "name", "name_ballot", "party",
          "acronym", "age", "sex", "ethnicity", "ballot_order_y", "votes", "votes_perc",
          "result"),
         (("ballot", "name_ballot"), ("full", "name"))),
)
#: How a record is read from the files (_read): a change to what is kept
#: or how a spelling is read bumps it, and a corpus read by another
#: version is refused on load (check_my).
MY_READ_VERSION = 1
#: The share of a file's rows that may be another number of fields than
#: its header before the file is refused: none was on 2026-11-19.
MY_MAX_BAD = 1 / 100
#: The share of a file's rows that may have an empty name in a column
#: read (a row counted once, however many) before the file is refused:
#: none had on 2026-11-19.
MY_MAX_NAMELESS = 1 / 100


def _sha256_checked(file: File) -> Callable[[bytes], bytes]:
    """A reader returning a body that is `file`'s pinned bytes, else
    raising ValueError, which _retried takes for a body cut short."""
    def read(body: bytes) -> bytes:
        digest = hashlib.sha256(body).hexdigest()
        if digest != file.sha256:
            raise ValueError(f"{file.file}'s sha256 is {digest}, not the pinned {file.sha256}")
        return body
    return read


def _read(file: File, text: str) -> tuple[list[dict[str, str]], Counter[str]]:
    """The records of one election's file, which must have exactly its
    header and its rows, and end with a whole row."""
    rows = list(csv.reader(io.StringIO(text, newline="")))
    header = tuple(rows[0]) if rows else ()
    if header != file.header:
        raise ValueError(f"{file.file}'s header is not the {len(file.header)} columns "
                         f"this reads: {', '.join(header)}")
    # csv returns a body cut inside its last row as a short last row,
    # which the count below would take for a whole one (local_ukec's
    # _ukec_rows says so too). A cut only shortens a row, so a long last
    # row is left to the malformed share. Every file ended with a line
    # break on 2026-11-19.
    if not text.endswith("\n") or len(rows) > 1 and len(rows[-1]) < len(header):
        raise ValueError(f"{file.file} ends inside a row: cut short; fetch again")
    body = rows[1:]
    if len(body) != file.rows:
        raise ValueError(f"{file.file} holds {len(body):,} rows where {file.rows:,} are "
                         f"pinned: a cut or changed file; fetch again")
    ethnicity_at = header.index("ethnicity")
    columns = [(form, header.index(column)) for form, column in file.forms]
    counts: Counter[str] = Counter()
    records: list[dict[str, str]] = []
    seen: set[tuple[str, str]] = set()
    for row in body:
        if len(row) != len(header):
            counts["malformed"] += 1
            continue
        ethnicity = row[ethnicity_at].strip()
        if any(not row[at].strip() for _, at in columns):
            counts["nameless"] += 1
        for form, at in columns:
            name = " ".join(row[at].split())
            if not name:
                continue
            if (name, ethnicity) in seen:
                counts["repeated"] += 1
                continue
            seen.add((name, ethnicity))
            records.append({"name": name, "election": file.election, "form": form,
                            "ethnicity": ethnicity})
            counts[form] += 1
    of = f"rows of {file.file}"
    _refuse_past([(counts["malformed"], len(body), MY_MAX_BAD,
                   f"{of} are not {len(header)} fields"),
                  (counts["nameless"], len(body), MY_MAX_NAMELESS,
                   f"{of} have an empty name")],
                 "the file is not the one this reads")
    return records, counts


def fetch_my() -> Fetched:
    """Every distinct spelling of every candidate in FILES, one record
    each, with its election, form and ethnicity. A file other than the
    pinned one (retried first, as a body cut short), of another header
    or row count, or not ending with a whole row, is refused, as is one
    past MY_MAX_BAD rows of another width or MY_MAX_NAMELESS rows with an
    empty name. The data date is the pinned commit's."""
    records: list[dict[str, str]] = []
    elections: dict[str, dict[str, int]] = {}
    for file in FILES:
        url = MY_URL.format(commit=MY_COMMIT, file=file.file)
        print(f"downloading {url} ...", file=sys.stderr)
        body = _retried(url, _sha256_checked(file), 0)
        read, counts = _read(file, body.decode("utf-8"))
        records += read
        elections[file.election] = {"rows": file.rows, **counts}
    detail: dict[str, Any] = {"commit": MY_COMMIT, "read_version": MY_READ_VERSION,
                              "elections": elections}
    return Fetched(records, MY_DATE, detail)


_check_commit = _pinned("commit", lambda: MY_COMMIT,
                        "the corpus was read at commit {held}, and this tool reads {wanted}")
_check_read = _pinned("read_version", lambda: MY_READ_VERSION,
                      "the corpus was read by version {held} of _read, and this tool is "
                      "version {wanted}")


def check_my(meta: dict[str, Any]) -> str:
    """Why a corpus read at another MY_COMMIT or by another
    MY_READ_VERSION is refused, or ""."""
    return _check_commit(meta) or _check_read(meta)
