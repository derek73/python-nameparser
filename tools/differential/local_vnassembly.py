"""The vn-assembly local corpus: Vietnam's National Assembly deputies.

vn-assembly -- the deputies of Vietnam's 15th National Assembly (Quốc
hội khóa XV, 2021-2026) as the Assembly's official deputy database
(dbqh.quochoi.vn) lists them, read through OpenSanctions'
`vn_national_assembly` dataset, which crawls that database weekly and
publishes it as one FollowTheMoney file (657,574 bytes, 499 deputies, on
2026-11-04). Each deputy's name is written in the Vietnamese order,
family name first and given name last (`Trần Quốc Nam`), with its
diacritics, beside the deputy's gender, ethnicity and education. The
education states the academic rank (học hàm: Giáo sư, Phó Giáo sư) and
the degree (học vị: Tiến sĩ, Thạc sĩ) in words, apart from the name, so
it is the one local population whose Vietnamese titles are stated
rather than read off the name: of the 499 on 2026-11-04, 16 held a rank
and 399 a doctorate or a master's degree.

A record's name is COMPOSED: the title the education states, written as
the Vietnamese press and official letters abbreviate it before a name
(`PGS.TS. Trần Quốc Nam`, title), then the name as the database gives
it, which the record keeps too (`official`). The title is derived
(TITLE_VERSION), and so are the name's parts (local_uit.split, the
convention the uit-vinames corpus reads by: first word the family name,
last the given name, the words between the middle name), which the
database does not state. The convention holds for Kinh names, 410 of
the 499 on 2026-11-04, and for many others, but not for every
ethnicity's (an Ê-đê name gives the given name first), so the records
carry the ethnicity the database states, which the score groups by.
A deputy's alias (a religious name with its title, `Hòa thượng Thích
...`, or a former name) is kept in the record, not in the corpus.

OpenSanctions licenses its data under CC BY-NC 4.0
(https://www.opensanctions.org/licensing/, read 2026-11-05):
non-commercial use, crediting OpenSanctions, which the credit line does;
the composed names are derived, which it says too. The names are
public officials', published by the Assembly, and are cached, never
committed.
"""
from __future__ import annotations

import hashlib
import json
import re
import sys
import unicodedata
from collections import Counter
from collections.abc import Callable
from typing import Any

import corpus_build
import local_uit
from local_core import Fetched, _get_json, _pinned, _retried
from local_uit import split


VN = "vn-assembly"
VN_INDEX = ("https://data.opensanctions.org/datasets/latest/"
            "vn_national_assembly/index.json")
VN_RESOURCE = "entities.ftm.json"
#: The academic ranks and degrees an education may state, each with the
#: abbreviation written before a name, the higher tried first; a rank's
#: phrase is matched where no `phó` stands before it, since `Phó Giáo
#: sư` holds `Giáo sư`, so an education naming both reads GS. The doctor of science (Tiến sĩ khoa
#: học, TSKH) is not told apart: no education stated it on 2026-11-04,
#: and the phrase also opens `Tiến sĩ khoa học máy tính`, a doctorate in
#: computer science. A rank and a degree compose glued,
#: the rank first (`PGS.TS.`), as the press writes them.
RANKS = ((re.compile(r"(?<!phó )giáo sư"), "GS"), (re.compile("phó giáo sư"), "PGS"))
DEGREES = ((re.compile("tiến sĩ"), "TS"), (re.compile("thạc sĩ"), "ThS"))
#: How a record's title is derived (title_of): a change bumps it, and a
#: corpus derived by another version, or split by another
#: local_uit.SPLIT_VERSION, is refused on load (check_vn).
TITLE_VERSION = 1
#: The least share of deputies whose education states a title: 399 of
#: 499 on 2026-11-04. An education field emptied or renamed would
#: otherwise read as a register of untitled names.
VN_MIN_TITLED = 1 / 2


def title_of(education: str) -> str:
    """The title an education states, abbreviated: the highest rank and
    the highest degree it names, glued (`PGS.TS.`), or "". The text is
    NFC-composed first, so a decomposed `tiến sĩ` is still found."""
    text = " ".join(unicodedata.normalize("NFC", education).casefold().split())
    rank = next((short for words, short in RANKS if words.search(text)), "")
    degree = next((short for words, short in DEGREES if words.search(text)), "")
    return "".join(f"{short}." for short in (rank, degree) if short)


def _is_count(value: object) -> bool:
    """An int that is not a bool, which JSON's true would be."""
    return isinstance(value, int) and not isinstance(value, bool)


def _resource(index: dict[str, Any]) -> tuple[str, str, int]:
    """The FtM file's URL, sha1 and size, as the dataset's index states."""
    for resource in index.get("resources", []):
        if isinstance(resource, dict) and resource.get("name") == VN_RESOURCE:
            url, sha1, size = (resource.get(k) for k in ("url", "checksum", "size"))
            if isinstance(url, str) and isinstance(sha1, str) and _is_count(size):
                return url, sha1, size
    raise ValueError(f"{VN_INDEX} lists no {VN_RESOURCE} with its url, checksum and size")


def _checked(sha1: str, size: int) -> Callable[[bytes], bytes]:
    """A reader refusing a body of another size or sha1, which _retried
    takes for a body cut short in transit."""
    def read(body: bytes) -> bytes:
        digest = hashlib.sha1(body).hexdigest()
        if len(body) != size or digest != sha1:
            raise ValueError(f"the file is {len(body):,} bytes of sha1 {digest}, not "
                             f"the {size:,} of {sha1} the index states")
        return body
    return read


def _first(properties: dict[str, Any], key: str) -> str:
    values = properties.get(key) or [""]
    return " ".join(str(values[0]).split())


def _vn_read(body: bytes, targets: int) -> tuple[list[dict[str, str]], dict[str, Any]]:
    """The records of every Person in the FtM file, which must hold
    exactly the `targets` the index counts, each with one name, and
    enough of them titled (VN_MIN_TITLED)."""
    records: list[dict[str, str]] = []
    counts: Counter[str] = Counter()
    for line in corpus_build.jsonl_lines(body.decode("utf-8")):
        entity = json.loads(line)
        if not isinstance(entity, dict) or entity.get("schema") != "Person":
            continue
        properties = entity.get("properties", {})
        names = properties.get("name") or []
        words = names[0].split() if len(names) == 1 and isinstance(names[0], str) else []
        if len(words) < 2:
            raise ValueError(f"a deputy holds {len(names)} names, or one that is not "
                             f"text of two words or more: the dataset's shape has changed")
        official = " ".join(words)
        title = title_of("; ".join(properties.get("education") or []))
        counts["titled"] += bool(title)
        counts[f"title {title or '(none)'}"] += 1
        alias = "; ".join(" ".join(str(a).split()) for a in properties.get("alias") or [])
        record = {"name": f"{title} {official}" if title else official,
                  "official": official, "title": title,
                  "gender": _first(properties, "gender"),
                  "ethnicity": _first(properties, "ethnicity"), "alias": alias,
                  **split(official)}
        records.append({k: v for k, v in record.items() if v})
    if len(records) != targets:
        raise ValueError(f"the file holds {len(records):,} deputies where the index "
                         f"counts {targets:,}: a cut or changed file; fetch again")
    if counts["titled"] < len(records) * VN_MIN_TITLED:
        raise ValueError(f"{counts['titled']:,} of {len(records):,} deputies' education "
                         f"states a title: an education field emptied or moved")
    return sorted(records, key=lambda r: r["official"]), dict(counts)


def fetch_vn() -> Fetched:
    """Every deputy the dataset holds, one record each: the composed name,
    the official name, the title, the gender, the ethnicity, the alias
    where there is one, and the derived parts, an empty middle name left
    out. The dataset's index is read first, and the file must be the
    size and sha1 it states and hold the deputies it counts. The data
    date is the index's updated_at, the time OpenSanctions last exported
    the dataset."""
    index = _get_json(VN_INDEX)
    if not _is_count(index.get("target_count")):
        raise ValueError(f"{VN_INDEX} states no target_count")
    url, sha1, size = _resource(index)
    print(f"downloading {url} ...", file=sys.stderr)
    body = _retried(url, _checked(sha1, size), 0)
    records, counts = _vn_read(body, index["target_count"])
    return Fetched(records, str(index.get("updated_at", "")), {
        "version": index.get("version", ""), "title_version": TITLE_VERSION,
        "split_version": local_uit.SPLIT_VERSION, **counts})


_check_title = _pinned(
    "title_version", lambda: TITLE_VERSION,
    "the corpus was derived by version {held} of title_of, and this tool is version {wanted}")
_check_split = _pinned(
    "split_version", lambda: local_uit.SPLIT_VERSION,
    "the corpus was split by version {held} of local_uit.split, and this tool is "
    "version {wanted}")


def check_vn(meta: dict[str, Any]) -> str:
    """Why a corpus derived by another TITLE_VERSION, or split by another
    local_uit.SPLIT_VERSION, is refused, or ""."""
    return _check_title(meta) or _check_split(meta)
