"""The opensanctions-parliaments local corpus: members of national
parliaments, as each parliament writes their names.

opensanctions-parliaments -- the members OpenSanctions' crawlers read
off twenty-two national chambers' own websites, and the regional heads
Indonesia elected in 2018 (DATASETS), each
dataset's `targets.simple.csv`: a row per person, the `name` column as
the parliament writes it and `aliases` the other forms the crawler
found, joined by ";" (another script, Kazakh beside Russian Cyrillic,
Uzbek Cyrillic beside its Latin, Devanagari beside Latin, Hangul and
Hanja beside a Korean member's Latin, Hebrew beside an Israeli's; a short
parliamentary name, `Jorge Costa` for `Jorge Fernando Magalhães da
Costa`; the name with its title, `Shrimati Savitri Kulaste`; another
surname, in Ukraine's; another transliteration, in Ethiopia's). A row
is a target; on 2026-11-08 every one of the 19,216 was a Person, 3,479
of them spelled two ways or more, 24,084 spellings in all, distinct
within each member. The parliaments write
the shapes the other corpora barely hold: Turkic patronymics (`Həmid
qızı`, `Серикбайулы`, `Bolatuly`, `Gurbangulyyevich`, `o‘g‘li`) and East
Slavic ones, in Cyrillic and in Latin, family first and last, the family
often in capitals (`AĞAZADƏ Əminə`, `Mehmet DEMİR`); Indic titles and
initials (`Shri`, `Smt.`, `Dr.`, initials before the name); Slavic and
Portuguese double surnames; Indonesian names in capitals with `H.`
(Haji) or `R.` (Raden) before them and no family name; Ethiopian names
of given, father's and grandfather's name; Korean names in Hangul and
Hanja, and Hebrew ones. Issues #1186 to #1192 were
read from it, in a 2026-11-07/08 check of the shipped packs; the
Indonesian datasets measure #1205 and #1206, Ethiopia's #1203, Korea's
#1213, #1215 and #1216, and Israel's #1209, #1210 and #1211.

A record is one distinct spelling of one member: the spelling (`name`),
the member (`entity`, the dataset and OpenSanctions' id, so a member of
two parliaments is two entities, each read within its own), the
spelling's script (local_jrc.script, so the groups and alike views pair
a member's spellings as they pair a JRC-Names person's), the dataset's
id (`dataset`, the group config_diff.py --group keeps) and where the
spelling stood (`form`, "name" or "alias").

OpenSanctions licenses its data under CC BY-NC 4.0
(https://www.opensanctions.org/licensing/, read 2026-11-08):
non-commercial use, crediting OpenSanctions, which the credit line does.
The names are public officials', published by their parliaments, and
are cached, never committed.
"""
from __future__ import annotations

import csv
import io
import sys
import unicodedata
from collections import Counter
from typing import Any

from local_core import (Fetched, _get_json, _is_count, _listed_resource, _pinned,
                        _refuse_past, _retried, _sha1_checked)
import local_jrc


PARLIAMENTS = "opensanctions-parliaments"
#: The datasets read, each a national chamber's members as its own
#: website lists them, save id_regional_2018: the governors, regents and
#: mayors Indonesia elected in 2018, as its election commission lists
#: them, read beside the two chambers because it writes names as they do
#: and holds most of their `H.` (Haji), 128 of 138 on 2026-11-08. A
#: corpus fetched over another list is refused on load (check_parliaments).
DATASETS = ("az_parliament", "kg_jogorku_kenesh", "uz_legislative_chamber", "uz_senate",
            "kz_mazhilis", "kz_senate", "tm_mejlis", "tr_parliament", "hr_sabor",
            "si_dz_rs", "sk_nrsr_poslanci", "pt_parliament", "in_sansad", "ua_rada",
            "by_council_republic", "ru_duma_deputies", "ru_federation_council",
            "id_dpr", "id_dpd", "id_regional_2018", "et_hopr",
            "kr_assembly", "il_knesset_members")
INDEX_URL = "https://data.opensanctions.org/datasets/latest/{dataset}/index.json"
RESOURCE = "targets.simple.csv"
#: The columns read; the file holds others (birth dates, contacts), and
#: a new one is no reason to refuse it.
COLUMNS = ("id", "schema", "name", "aliases")
PERSON = "Person"
#: The separator of a multi-valued column in the simple CSV. The name
#: column is split at it too: one cell on 2026-11-08 held two names
#: (counted in the detail as "name cells split").
SEPARATOR = ";"
#: Characters no name or aliases cell holds, which a cell holding would
#: be multi-valued and joined by another separator than SEPARATOR: none
#: did on 2026-11-08. Read in the raw cell, since spellings() folds a
#: tab into a space; counted by row, and past MAX_BAD refused.
FOREIGN_SEPARATORS = ("|", "\t")
#: How a file is read into records, stored in meta.json's detail with the
#: Unicode version and local_jrc.JRC_READ_VERSION, the version of the
#: script() the records are labelled by: a change to what _read keeps or
#: how it splits a spelling bumps it by hand, and a corpus read the old
#: way is then refused on load (check_parliaments).
READ_VERSION = 1
#: The share of rows that may be malformed (another number of fields
#: than the header) before a file is refused: none were on 2026-11-08.
MAX_BAD = 1 / 100
#: The least share of rows that are people before a file is refused:
#: every row was on 2026-11-08. A schema renamed would otherwise read as
#: a parliament of none.
MIN_PERSONS = 1 / 2
#: The share of people that may have no name before a file is refused:
#: none had on 2026-11-08.
MAX_NAMELESS = 1 / 100


def spellings(*values: str) -> list[str]:
    """The distinct spellings in `values`, each split at SEPARATOR, its
    whitespace read as single spaces, in order, an empty one dropped."""
    found: dict[str, None] = {}
    for value in values:
        for part in value.split(SEPARATOR):
            if spelling := " ".join(part.split()):
                found[spelling] = None
    return list(found)


def _read(dataset: str, text: str, targets: int) -> tuple[list[dict[str, str]], Counter[str]]:
    """The records of one dataset's simple CSV, which must hold the
    `targets` rows its index counts, end with a whole row, and give
    every person an id of its own."""
    rows = list(csv.reader(io.StringIO(text, newline="")))
    header = rows[0] if rows else []
    if missing := [c for c in COLUMNS if c not in header]:
        raise ValueError(f"{dataset}'s {RESOURCE} has no {', '.join(missing)} column: "
                         f"its layout has changed")
    # csv returns a body cut inside its last row as a short last row,
    # which the count below would take for a whole one (local_ukec's
    # _ukec_rows says so too). Every file ended with a line break on
    # 2026-11-08.
    if not text.endswith("\n") or len(rows) > 1 and len(rows[-1]) < len(header):
        raise ValueError(f"{dataset}'s {RESOURCE} ends inside a row: cut short; fetch again")
    body = rows[1:]
    if len(body) != targets:
        raise ValueError(f"{dataset}'s {RESOURCE} holds {len(body):,} rows where its index "
                         f"counts {targets:,} targets: a cut or changed file; fetch again")
    at = {c: header.index(c) for c in COLUMNS}
    counts: Counter[str] = Counter()
    records: list[dict[str, str]] = []
    ids: set[str] = set()
    for row in body:
        if len(row) != len(header):
            counts["malformed"] += 1
            continue
        if row[at["schema"]] != PERSON:
            counts["other schema"] += 1
            continue
        counts["persons"] += 1
        # An empty or repeated id would merge two members into one
        # entity, whose spellings the groups and alike views then pair.
        id_ = row[at["id"]].strip()
        if not id_ or id_ in ids:
            raise ValueError(f"{dataset}'s {RESOURCE} gives a person an empty or repeated "
                             f"id {id_!r}: its layout has changed")
        ids.add(id_)
        if any(c in row[at[k]] for k in ("name", "aliases") for c in FOREIGN_SEPARATORS):
            counts["foreign separator"] += 1
        names = spellings(row[at["name"]])
        if not names:
            counts["nameless"] += 1
            continue
        if len(names) > 1:
            counts["name cells split"] += 1
        entity = f"{dataset}:{id_}"
        for form, values in (("name", names), ("alias", spellings(row[at["aliases"]]))):
            for name in values:
                if form == "alias" and name in names:
                    continue
                records.append({"name": name, "entity": entity,
                                "script": local_jrc.script(name), "dataset": dataset,
                                "form": form})
                counts[form] += 1
    of = f"rows of {dataset}'s {RESOURCE}"
    _refuse_past([(counts["malformed"], len(body), MAX_BAD, f"{of} are not "
                   f"{len(header)} fields"),
                  (counts["nameless"], counts["persons"], MAX_NAMELESS,
                   f"people in {dataset}'s {RESOURCE} have no name"),
                  (counts["foreign separator"], counts["persons"], MAX_BAD,
                   f"people in {dataset}'s {RESOURCE} have a name or aliases cell "
                   f"holding a separator other than {SEPARATOR!r}")],
                 "the file's layout has changed")
    if not counts["persons"]:
        raise ValueError(f"{dataset}'s {RESOURCE} holds no {PERSON} of its {len(body):,} rows: "
                         f"an emptied file, a schema renamed, or another dataset")
    if counts["persons"] < len(body) * MIN_PERSONS:
        raise ValueError(f"{counts['persons']:,} of {len(body):,} {of} are a {PERSON}: "
                         f"a schema renamed, or another dataset")
    return records, counts


def fetch_parliaments() -> Fetched:
    """Every spelling of every member of every dataset in DATASETS,
    one record each. Each dataset's index is read first, and its file
    must state its targets, its date and the file's url, size and sha1;
    the file must be that size and sha1 (retried, then refused,
    otherwise), and _read's checks pass.
    The data date is the newest dataset's `updated_at`; each dataset's
    own, with its export's version and its counts, is in the detail."""
    records: list[dict[str, str]] = []
    datasets: dict[str, dict[str, Any]] = {}
    for dataset in DATASETS:
        where = INDEX_URL.format(dataset=dataset)
        index = _get_json(where)
        if not _is_count(index.get("target_count")):
            raise ValueError(f"{where} states no target_count")
        if not isinstance(index.get("updated_at"), str) or not index["updated_at"]:
            raise ValueError(f"{where} states no updated_at, the data date")
        url, sha1, size = _listed_resource(index, RESOURCE, where)
        print(f"downloading {url} ...", file=sys.stderr)
        body = _retried(url, _sha1_checked(sha1, size), 0.1)
        read, counts = _read(dataset, body.decode("utf-8"), index["target_count"])
        records += read
        datasets[dataset] = {"version": str(index.get("version", "")),
                             "updated_at": index["updated_at"], **counts}
    return Fetched(records, max(d["updated_at"] for d in datasets.values()), {
        "datasets": list(DATASETS), "read_version": READ_VERSION,
        "script_version": local_jrc.JRC_READ_VERSION,
        "unicode": unicodedata.unidata_version, "per_dataset": datasets})


_check_datasets = _pinned("datasets", lambda: list(DATASETS),
                          "was fetched from the datasets {held}, and this tool reads {wanted}")
_check_read = _pinned("read_version", lambda: READ_VERSION,
                      "was read by read version {held}, and this tool reads version {wanted}")
_check_script = _pinned("script_version", lambda: local_jrc.JRC_READ_VERSION,
                        "was labelled by version {held} of local_jrc.script, and this tool "
                        "is version {wanted}")
_check_unicode = _pinned("unicode", lambda: unicodedata.unidata_version,
                         "was labelled under Unicode {held}, and this Python reads "
                         "Unicode {wanted}")


def check_parliaments(meta: dict[str, Any]) -> str:
    """Why a corpus fetched over another DATASETS, read by another
    READ_VERSION, or labelled by another version of script() or under
    another Unicode version is refused, or ""."""
    return (_check_datasets(meta) or _check_read(meta) or _check_script(meta)
            or _check_unicode(meta))
