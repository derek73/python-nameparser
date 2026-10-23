"""The fec-individuals local corpus: the FEC's individual contributors.

fec-individuals -- the distinct names of every individual contributor
in the FEC's bulk file of itemized contributions by individuals for the
cycle (indiv26.zip, 2.3 GB on 2026-10-18, downloaded into the cache once
and read without unpacking; `fetch --refresh` downloads it again).
Itemized contributions only: a committee need itemize only a donor
whose gifts to it pass $200, so a smaller donor is there only where a
committee itemized the gift anyway. Mostly a filer's software writing a form's fields in a fixed
order, family, comma, given, in capitals -- every one of the 1,893,964
names on 2026-10-18 was in capitals and all but three held a comma --
with hand-typed text inside the fields: 3,306 held a second comma, for
a credential run or a suffix in a part of its own. So it is the
population for the one-case family-comma shape, and blind to case and
to names written in their spoken order. The FEC's terms (52 U.S.C.
30111(a)(4)) bar using the names to solicit contributions or for any
commercial purpose, which the credit line every report opens with
repeats; only the NAME column is kept.
"""
from __future__ import annotations

import zipfile
from collections import Counter
from pathlib import Path

from local_core import (Fetched, _download, _pinned, _refuse_past, _zip_stamp,
                        directory, fetch_command)


# -- FEC individual contributions --------------------------------------------

FEC_CYCLE = "2026"
FEC_ZIP = f"indiv{FEC_CYCLE[2:]}.zip"
FEC_URL = f"https://www.fec.gov/files/bulk-downloads/{FEC_CYCLE}/{FEC_ZIP}"
#: The whole cycle in one file; the zip's by_date/ members repeat it in slices.
FEC_MEMBER = "itcont.txt"
#: The file's columns (the FEC's contributions-by-individuals file
#: description): 21, pipe-separated, ENTITY_TP the 7th and NAME the 8th.
FEC_COLUMNS, FEC_ENTITY, FEC_NAME = 21, 6, 7
#: The file has no header row to check the columns against, so a fetch
#: refuses one that no longer looks like the file the constants above
#: were written for: more than this share of its lines malformed or not
#: UTF-8 (none were, of 34,264,742 lines in the file dated 2026-10-18),
#: or fewer than FEC_MIN_COMMA of its names holding a comma (1,893,961
#: of 1,893,964 did), which is what a column moved under NAME would show.
FEC_MAX_BAD = 1 / 10_000
FEC_MIN_COMMA = 0.9


def _fec_download(path: Path) -> None:
    """Download FEC_URL over the cached zip (_download), and remove a zip
    of another cycle once this one has arrived."""
    _download(FEC_URL, path)
    for stale in path.parent.glob("indiv*.zip"):
        if stale != path:
            stale.unlink()


def _fec_read(path: Path) -> Fetched:
    names: set[str] = set()
    entities: Counter[str] = Counter()
    rows = malformed = latin1 = nameless = 0
    with zipfile.ZipFile(path) as archive:
        if FEC_MEMBER not in archive.namelist():
            raise ValueError(f"{path} holds no {FEC_MEMBER}")
        member = archive.getinfo(FEC_MEMBER)
        stamp = _zip_stamp(member)
        with archive.open(member) as lines:
            for line in lines:
                rows += 1
                try:
                    text = line.decode("utf-8")
                except UnicodeDecodeError:
                    latin1 += 1
                    text = line.decode("latin-1")
                cols = text.rstrip("\r\n").split("|")
                if len(cols) != FEC_COLUMNS:
                    malformed += 1
                    continue
                entities[cols[FEC_ENTITY]] += 1
                if cols[FEC_ENTITY] != "IND":
                    continue
                if name := cols[FEC_NAME].strip():
                    names.add(name)
                else:
                    nameless += 1
    _refuse_past([(malformed, rows, FEC_MAX_BAD, f"lines of {path} are not {FEC_COLUMNS} columns"),
                  (latin1, rows, FEC_MAX_BAD, f"lines of {path} are not UTF-8")],
                 "the file's layout has changed under FEC_COLUMNS")
    with_comma = sum("," in name for name in names)
    if names and with_comma < len(names) * FEC_MIN_COMMA:
        raise ValueError(f"{with_comma:,} of {len(names):,} names hold a comma: "
                         f"column {FEC_NAME + 1} of {path} no longer holds NAME")
    return Fetched([{"name": name} for name in sorted(names)], stamp, {
        "cycle": FEC_CYCLE, "file": f"{FEC_ZIP}/{FEC_MEMBER}", "rows": rows,
        "individual_contributions": entities["IND"],
        "rows_from_other_entities": sum(entities.values()) - entities["IND"],
        "individuals_without_a_name": nameless,
        "lines_not_21_columns": malformed, "lines_not_utf8": latin1})


def fetch_fec() -> Fetched:
    """The distinct names of every individual contributor in the cycle's
    file, one record per name, read from the zip cached beside the
    corpus (downloaded when missing, and again by `fetch --refresh`).

    A record is a NAME, not a contribution or a contributor: one donor
    gives many times (34,264,742 rows held 1,893,964 names in the file
    dated 2026-10-18), and a contribution count would weight a shape by
    how often its bearers give. Only the name is kept, stripped of the
    spaces around it; the address, employer and amount columns are read
    past. The data date is the member's own timestamp, which carries no
    time zone. A line that is not 21 columns is counted and skipped, a
    line that is not UTF-8 is counted and read as Latin-1, and a row from
    an entity that is not a person and a person with no name are
    counted; past FEC_MAX_BAD, or with too few names holding a comma, the
    file is refused rather than read as a smaller or a different corpus."""
    path = directory("fec-individuals") / FEC_ZIP
    if not path.exists():
        _fec_download(path)
    try:
        return _fec_read(path)
    except zipfile.BadZipFile as exc:
        raise ValueError(f"{path} is not a readable zip ({exc}); download it "
                         f"again: {fetch_command('fec-individuals', refresh=True)}"
                         ) from None


def renew_fec() -> None:
    """Download the current file over the cached zip."""
    _fec_download(directory("fec-individuals") / FEC_ZIP)


check_fec = _pinned("cycle", lambda: FEC_CYCLE,
                    "holds the {held} cycle, and this tool reads the {wanted} cycle")
