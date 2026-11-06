"""The uit-vinames local corpus: Vietnamese full names in native order.

uit-vinames -- the distinct full names of UIT-ViNames, the gender-labelled
dataset of the University of Information Technology (VNU-HCM) NLP group
(Huy Quoc To, Kiet Van Nguyen, Ngan Luu-Thuy Nguyen, Anh Gia-Tuan Nguyen,
"Gender Prediction Based on Vietnamese Names with Machine Learning
Techniques", NLPIR 2020, doi:10.1145/3443279.3443309), as the authors'
GitHub repository ships it: one zip, pinned here by commit and sha256,
whose Full.csv holds 26,851 rows of a full name and a gender: 21,090
distinct names of two words or more, and 3 rows of one word (2026-11-05). The
names are written in the Vietnamese order, family name first and given
name last (`Lê Thị Tuyết Trinh`), with their diacritics (all but 109 of
the 21,090 carry a letter outside ASCII), and 20,593 of the 21,090 are
three or four words long. So it is the
population for a family-first Vietnamese reading such as #1108
proposes, and a corpus whose middle names are scored apart from the
given name, which ORCID's two boxes, the given box holding the middle
names too, cannot do.

The dataset states the name whole, not its parts, so a record's
family, middle and given are DERIVED by the Vietnamese convention
(split): the first word the family name, the last the given name, and
the words between the middle name. The convention is what a reader of
the name assumes, not a box anyone filled, and it misreads the names it
does not hold for: a two-word family name (`Tôn Nữ`, `Nguyễn Phúc`,
`Âu Dương`) reads its second word as a middle name, and the foreign
students' names the dataset keeps (most of the 11 written wholly in
capitals on 2026-11-05 are Lao and Khmer names, and others are in mixed
case) are split the same way whatever their order. A one-word name has
no parts the convention can tell apart and is read past
(rows_of_one_word). The split is versioned (SPLIT_VERSION), as the read
is (UIT_READ_VERSION), and a corpus split or read by another version is
refused on load.

The repository states no licence, and the authors offer the dataset for
research use, citing the paper; the names are students' and other real
people's, so it is cached, never committed, and what reaches the
repository is counts and made-up names.
"""
from __future__ import annotations

import csv
import hashlib
import io
import sys
import zipfile
from collections import Counter
from typing import Any

from local_core import Fetched, _pinned, _retried


UIT = "uit-vinames"
#: The commit the zip is read from, and the zip's sha256 there: the
#: repository had not changed since 2021-07-08 when read on 2026-11-05, so a pin both names the
#: data exactly and refuses a zip cut in transit or changed upstream.
UIT_COMMIT = "443eee8d7fa7942fffd103de68c2286294106608"
UIT_DATE = "2021-07-08"
UIT_URL = (f"https://raw.githubusercontent.com/JkUndead/UIT-ViNames-Dataset/"
           f"{UIT_COMMIT}/UIT-ViNames-v1.zip")
UIT_SHA256 = "444b882fa960ec193368aaa68d7f88eaa38e83925e112463dc97884204067c56"
UIT_MEMBER = "UIT-ViNames/UIT-ViNames - Full.csv"
UIT_COLUMNS = ("Full_Name", "Gender")
#: The rows Full.csv held at UIT_COMMIT: the README says 26,850.
UIT_ROWS = 26_851
UIT_GENDERS = {"0": "female", "1": "male"}
#: How a record is read from Full.csv (_uit_read): a change bumps it,
#: and a corpus read by another version is refused on load (check_uit).
UIT_READ_VERSION = 1
#: How a name's family, middle and given are derived (split), for this
#: corpus and vn-assembly's alike: a change bumps it, and a corpus of
#: either split by another version is refused on load (check_uit,
#: local_vnassembly.check_vn).
SPLIT_VERSION = 1


def split(name: str) -> dict[str, str]:
    """The Vietnamese convention's parts of a name of two words or more:
    the first word the family name, the last the given name, the words
    between the middle name (empty for two words)."""
    words = name.split()
    if len(words) < 2:
        raise ValueError(f"{name!r} has no parts the convention tells apart")
    return {"family": words[0], "middle": " ".join(words[1:-1]), "given": words[-1]}


def _a_pinned_zip(body: bytes) -> bytes:
    """`body` where it is the pinned zip, else ValueError, which _retried
    takes for a body cut short in transit."""
    digest = hashlib.sha256(body).hexdigest()
    if digest != UIT_SHA256:
        raise ValueError(f"the zip's sha256 is {digest}, not the pinned {UIT_SHA256}")
    return body


def _uit_read(body: bytes) -> Fetched:
    with zipfile.ZipFile(io.BytesIO(body)) as archive:
        text = archive.read(UIT_MEMBER).decode("utf-8-sig")
    rows = list(csv.reader(io.StringIO(text, newline="")))
    if not rows or tuple(rows[0]) != UIT_COLUMNS or len(rows) - 1 != UIT_ROWS:
        raise ValueError(f"{UIT_MEMBER} is not the {UIT_ROWS:,} rows of "
                         f"{', '.join(UIT_COLUMNS)} this reads")
    genders: dict[str, set[str]] = {}
    counts: Counter[str] = Counter()
    for row in rows[1:]:
        if len(row) != 2 or row[1] not in UIT_GENDERS:
            raise ValueError(f"a row of {UIT_MEMBER} is not a name and a gender "
                             f"{'/'.join(UIT_GENDERS)}: {len(row)} fields")
        words = row[0].split()
        if len(words) < 2:
            counts["rows_of_one_word"] += 1
            continue
        name = " ".join(words)
        genders.setdefault(name, set()).add(UIT_GENDERS[row[1]])
    records = []
    for name in sorted(genders):
        gender = genders[name].pop() if len(genders[name]) == 1 else "both"
        counts[f"names_{gender}"] += 1
        records.append({"name": name, "gender": gender,
                        **{k: v for k, v in split(name).items() if v}})
    detail: dict[str, Any] = {"commit": UIT_COMMIT, "rows": UIT_ROWS,
                              "read_version": UIT_READ_VERSION,
                              "split_version": SPLIT_VERSION, **counts}
    return Fetched(records, UIT_DATE, detail)


def fetch_uit() -> Fetched:
    """The distinct names of Full.csv, one record per name: the name with
    its runs of spaces read as one, its gender (`female`, `male`, or
    `both` for a name the dataset labels both ways: 127 of 21,090 on
    2026-11-05) and its parts as the convention derives them (split),
    an empty middle name left out. A zip other than the pinned one, a
    member of another header or row count, or a row that is not a name
    and a gender of 0 or 1, is refused. The data date is the pinned
    commit's."""
    print(f"downloading {UIT_URL} ...", file=sys.stderr)
    return _uit_read(_retried(UIT_URL, _a_pinned_zip, 0))


_check_read = _pinned(
    "read_version", lambda: UIT_READ_VERSION,
    "the corpus was read by version {held} of _uit_read, and this tool is version {wanted}")
_check_split = _pinned(
    "split_version", lambda: SPLIT_VERSION,
    "the corpus was split by version {held} of split, and this tool is version {wanted}")


def check_uit(meta: dict[str, Any]) -> str:
    """Why a corpus read by another UIT_READ_VERSION, or split by another
    SPLIT_VERSION, is refused, or ""."""
    return _check_read(meta) or _check_split(meta)
