"""Build the single-character surname list locales.ZH ships past the census.

WHY THIS IS IN THE TREE. The ZH pack divides an unspaced Chinese name
after a listed surname and leaves it whole otherwise (rules/W1). Up to
2.4 it listed the 2020 PRC census top 100, and 6 of the 80 real Chinese
names in the native-script corpus fell outside it (柯洁, 詹桓, #695). The
census publishes nothing past rank 100, so the list is extended from two
openly licensed rankings instead, and this script is how the extension
is re-derived rather than transcribed by hand:

- Taiwan, Ministry of the Interior, Department of Household
  Registration (內政部戶政司), surname ranking by population, 2023
  (data.gov.tw dataset 126774; Open Government Data License, version 1,
  which asks for attribution). Traditional script, Taiwan's own
  frequencies.
- Wikidata (CC0): items that are an instance of "Chinese family name"
  (Q1093580), ranked by how many people carry them as family name
  (P734), with their Chinese labels. Both scripts; it skews toward
  notable people and counts Korean and Vietnamese bearers of the same
  character.

Each ranking contributes its top N single-character surnames (N=300 by
decision, decisions/W1 of 2026-10-18), and the union is what ships, so
neither region's bias decides alone. Where a source gives one script
only, Wikidata's family-name items supply the other, in ONE direction:
a form gains a simplified one where the items labelled with it (any
item that is a family name, Q101352, or a Chinese family name,
Q1093580, at any rank) give exactly one form in their simplified
Chinese labels (zh-hans, zh-cn, zh-sg, zh-my), in the Basic
Multilingual Plane, and it is not the form itself: an item writing the
form the same in both scripts counts against another's simplified
form, as Unihan listed such a character among its own simplified
variants. A traditional form ships only where a source
attests it -- a ranked Wikidata item labelled with both, or the Taiwan
ranking itself -- since a simplified character's traditional forms are
one-to-many (餘 is one of 余's, and no one's surname). Until 3.1 the
simplified forms came from Unihan's variant table (Unicode License v3);
7 of its 19 additions no Wikidata item attests, and they left the list
(decisions/shipped-data-licences, 2026-11-12).

Two-character surnames are NOT taken from here. Taiwan's multi-character
rows are mostly married double surnames (王李, 李林), and an entry like
李林 would cut 李林伟 into 李林 + 伟, so compounds stay a hand-curated
list in zh.py.

    uv run python tools/zh_surnames.py           # the selection, with ranks
    uv run python tools/zh_surnames.py --write   # rewrite zh.py's block
    uv run python tools/zh_surnames.py --refresh # fetch the sources again

Sources are cached outside the repository, in $NAMEPARSER_TOOLS_CACHE
or ~/.cache/nameparser-tools (shared with name_usage.py); --refresh
fetches them again, and the Wikidata ranking moves when it does.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import io
import json
import re
import sys
import unicodedata
import urllib.request
from dataclasses import dataclass, field
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import name_usage  # noqa: E402  (a sibling script, not a package)

ZH_MODULE = Path(__file__).parents[1] / "nameparser" / "locales" / "zh.py"
TOP = 300

MOI_URL = (
    "https://opdadm.moi.gov.tw/api/v1/no-auth/resource/api/dataset/"
    "5D318346-EDFF-42C7-B914-946665D483F5/resource/"
    "E4A6518E-FF4C-4925-8D59-48ECE4401820/download")
MOI_FILE = "moi_surnames_2023.csv"
WIKIDATA_FILE = "wikidata_chinese_family_names.json"
SCRIPTS_FILE = "wikidata_chinese_surname_scripts.json"

#: Chinese label languages; Wikidata keeps each script under several.
LABEL_LANGUAGES = ("zh", "zh-hans", "zh-hant", "zh-cn", "zh-tw", "zh-hk",
                   "zh-sg", "zh-mo")
WIKIDATA_QUERY = f"""
SELECT ?item ?n ?label WHERE {{
  {{ SELECT ?item (COUNT(DISTINCT ?person) AS ?n) WHERE {{
      ?item wdt:P31 wd:Q1093580 . ?person wdt:P734 ?item .
  }} GROUP BY ?item }}
  OPTIONAL {{ ?item rdfs:label ?label
             FILTER(LANG(?label) IN ({", ".join(f'"{x}"' for x in LABEL_LANGUAGES)})) }}
}}"""

#: The labels that write a name in simplified characters.
SIMPLIFIED_LANGUAGES = ("zh-hans", "zh-cn", "zh-sg", "zh-my")
#: Every Chinese label language the script query reads.
SCRIPT_LANGUAGES = (*LABEL_LANGUAGES, "zh-my")


def scripts_query(forms: list[str]) -> str:
    """Every family-name item labelled with one of ``forms``, with its
    Chinese labels. The labels are matched exactly, in each Chinese
    label language, which the query service answers from its index; a
    filter over every family name's labels times out, and so did
    asking for the "X姓" and "X氏" labels as well (2026-11-12)."""
    values = " ".join(f'"{form}"@{lang}' for form in forms
                      for lang in SCRIPT_LANGUAGES)
    langs = ", ".join(f'"{lang}"' for lang in SCRIPT_LANGUAGES)
    return f"""
SELECT DISTINCT ?item ?lab ?lang WHERE {{
  VALUES ?label {{ {values} }}
  ?item rdfs:label ?label .
  VALUES ?cls {{ wd:Q101352 wd:Q1093580 }}
  ?item wdt:P31 ?cls .
  ?item rdfs:label ?lab FILTER(LANG(?lab) IN ({langs}))
  BIND(LANG(?lab) AS ?lang)
}}"""


BEGIN = "# -- BEGIN generated by tools/zh_surnames.py; edit the tool, not this block --"
END = "# -- END generated --"

#: Some items are labelled "X姓" or "X氏" ("surname X"), which is how
#: 易, 鄺 and 閆 appear; the label names the single character.
_SURNAME_WORD = re.compile(r"^(.)[姓氏]$")


def is_han(char: str) -> bool:
    """A unified ideograph. Compatibility ideographs and private-use
    codepoints (about 60 rows of the Taiwan file) are left out: no
    keyboard produces them for a name, and the compatibility block
    NFC-folds to a unified twin anyway."""
    return len(char) == 1 and unicodedata.name(char, "").startswith(
        "CJK UNIFIED IDEOGRAPH")


def read_moi(csv_text: str) -> list[str]:
    """Taiwan's single-character surnames in rank order. The file has
    one row per surname per age band, all carrying the surname's rank,
    and a placeholder row 其他 ("other") that is not a surname."""
    reader = csv.DictReader(io.StringIO(csv_text.lstrip("﻿")))
    if not reader.fieldnames or not {"ranking", "lastname"} <= set(
            reader.fieldnames):
        raise ValueError(f"unexpected Taiwan surname columns: "
                         f"{reader.fieldnames}")
    rank: dict[str, int] = {}
    for row in reader:
        name = row["lastname"].strip()
        rank.setdefault(name, int(row["ranking"]))
    if not rank:
        raise ValueError("the Taiwan surname file holds no rows")
    return [name for name in sorted(rank, key=lambda n: (rank[n], n))
            if is_han(name)]


@dataclass
class Item:
    qid: str
    bearers: int
    labels: set[str] = field(default_factory=set)

    def singles(self) -> set[str]:
        out = set()
        for label in self.labels:
            match = _SURNAME_WORD.match(label)
            word = match.group(1) if match else label
            if is_han(word):
                out.add(word)
        return out


def read_wikidata(rows: list[dict[str, str]]) -> list[Item]:
    """Chinese family-name items with at least one single-character
    label, most-borne first."""
    items: dict[str, Item] = {}
    for row in rows:
        qid = row["item"].rsplit("/", 1)[-1]
        item = items.setdefault(qid, Item(qid, int(row["n"])))
        if row.get("label"):
            item.labels.add(row["label"])
    ranked = [item for item in items.values() if item.singles()]
    return sorted(ranked, key=lambda item: (-item.bearers, item.qid))


def read_scripts(rows: list[dict[str, str]]) -> dict[str, set[str]]:
    """Each form's simplified forms: for every item, the single
    characters its simplified labels give, credited to each of its
    single-character labels. A form an item writes the same in both
    scripts is its own simplified form there, as Unihan's table listed
    such a character among its own simplified variants, so an item
    writing 乾 in simplified characters and another writing 干 leave
    乾 two forms, and :func:`select` adds neither."""
    labels: dict[str, dict[str, set[str]]] = {}
    for row in rows:
        match = _SURNAME_WORD.match(row["lab"])
        word = match.group(1) if match else row["lab"]
        if is_han(word):
            qid = row["item"].rsplit("/", 1)[-1]
            labels.setdefault(qid, {}).setdefault(row["lang"], set()).add(word)
    simplified: dict[str, set[str]] = {}
    for by_lang in labels.values():
        hans = set().union(*(by_lang.get(lang, set())
                             for lang in SIMPLIFIED_LANGUAGES))
        for form in set().union(*by_lang.values()):
            simplified.setdefault(form, set()).update(hans)
    return simplified


@dataclass
class Surname:
    forms: set[str]
    moi_rank: int | None = None
    wikidata_rank: int | None = None

    @property
    def rank(self) -> int:
        return min(r for r in (self.moi_rank, self.wikidata_rank)
                   if r is not None)


def select(moi: list[str], items: list[Item],
           simplified: dict[str, set[str]], top: int = TOP) -> list[Surname]:
    """The union of each ranking's top `top` single-character surnames,
    as surnames (one per set of script forms), best rank first. A
    character two sources share joins their entries, so 衛 from Taiwan
    and the item labelled 卫 and 衛 are one surname."""
    surnames: list[Surname] = []
    by_form: dict[str, Surname] = {}

    def add(forms: set[str], **ranks: int) -> None:
        found = {id(by_form[f]): by_form[f] for f in forms if f in by_form}
        if found:
            target, *others = found.values()
            for other in others:  # two entries this one bridges
                target.forms |= other.forms
                for key in ("moi_rank", "wikidata_rank"):
                    mine, theirs = getattr(target, key), getattr(other, key)
                    if theirs is not None and (mine is None or theirs < mine):
                        setattr(target, key, theirs)
                surnames.remove(other)
        else:
            target = Surname(set())
            surnames.append(target)
        target.forms |= forms
        for key, value in ranks.items():
            if getattr(target, key) is None:
                setattr(target, key, value)
        for form in target.forms:
            by_form[form] = target

    for i, char in enumerate(moi[:top], 1):
        add({char}, moi_rank=i)
    for i, item in enumerate(items[:top], 1):
        add(item.singles(), wikidata_rank=i)
    for surname in list(surnames):
        for form in list(surname.forms):
            # A supplementary-plane form is one only GB 18030's
            # extensions spell (蘭's 𬞕 beside 兰), an alternative to the
            # BMP spelling a name is typed with. A surname whose ONLY
            # spelling is supplementary (Taiwan's 𡍼) ships as ranked.
            variants = {v for v in simplified.get(form, ()) if ord(v) < 0x10000}
            if len(variants) == 1 and not variants <= surname.forms:
                add(variants | {form})
    return sorted(surnames, key=lambda s: (s.rank, min(s.forms)))


def additions(surnames: list[Surname], listed: set[str]) -> list[str]:
    """The forms to generate: every form of every selected surname that
    the hand-kept rows do not already hold, in rank order."""
    out: list[str] = []
    for surname in surnames:
        out.extend(sorted(surname.forms - listed - set(out)))
    return out


def render(forms: list[str]) -> str:
    rows = [", ".join(f'"{c}"' for c in forms[i:i + 10])
            for i in range(0, len(forms), 10)]
    body = "\n".join(f"    {row}," for row in rows)
    return f"{BEGIN}\n_SINGLE_RANKED = (\n{body}\n)\n{END}"


def rewrite(module_text: str, block: str) -> str:
    start, end = module_text.find(BEGIN), module_text.find(END)
    if start < 0 or end < start:
        raise ValueError(f"{ZH_MODULE} has no generated block to replace")
    return module_text[:start] + block + module_text[end + len(END):]


def listed_by_hand(module_text: str) -> set[str]:
    """The rows zh.py keeps by hand, read from its source so the
    script never imports the package it writes."""
    start = module_text.find(BEGIN)
    head = module_text if start < 0 else module_text[:start]
    head = head.split("_COMPOUND = (")[0]
    return {c for c in re.findall(r'"(.)"', head) if is_han(c)}


# -- sources --------------------------------------------------------------

def _fetch(url: str) -> bytes:
    request = urllib.request.Request(
        url, headers={"User-Agent": name_usage.USER_AGENT})
    with urllib.request.urlopen(request, timeout=120) as response:
        data: bytes = response.read()
    return data


def load_moi(refresh: bool) -> list[str]:
    path = name_usage.cache_dir() / MOI_FILE
    if refresh or not path.exists():
        text = _fetch(MOI_URL).decode("utf-8-sig")
        read_moi(text)  # refuse to cache an error page
        path.write_text(text, encoding="utf-8")
    return read_moi(path.read_text(encoding="utf-8"))


def load_wikidata(refresh: bool) -> list[Item]:
    path = name_usage.cache_dir() / WIKIDATA_FILE
    if refresh or not path.exists():
        rows = name_usage._bindings(name_usage._sparql(WIKIDATA_QUERY))
        if not read_wikidata(rows):
            raise ValueError("the Wikidata query returned no surnames")
        path.write_text(json.dumps(rows, ensure_ascii=False),
                        encoding="utf-8")
    return read_wikidata(json.loads(path.read_text(encoding="utf-8")))


def checked_rows(rows: list[dict[str, str]], columns: tuple[str, ...], *,
                 may_be_empty: bool = False) -> list[dict[str, str]]:
    """``rows`` if every one is a whole answer row: each column filled
    and the first an entity IRI. The query service, cut off at its time
    limit, appends its error text to a CSV answer, which reads as rows
    with the trailing columns empty (2026-11-12); an answer of no rows
    is refused too, unless ``may_be_empty`` says no row is a possible
    answer."""
    if not rows and not may_be_empty:
        raise ValueError("the Wikidata query returned no rows")
    for row in rows:
        if (any(not row.get(c) for c in columns)
                or not row[columns[0]].startswith(
                    "http://www.wikidata.org/entity/Q")):
            raise ValueError(f"the Wikidata answer holds a row that is not "
                             f"one ({row!r:.200}): it was cut short or "
                             "answered an error; ask again")
    return rows


#: Forms (or items) a query asks about at once: all 442 forms in one
#: query outran the service's time limit on 2026-11-12.
BATCH = 100


def batched(items: list[str]) -> list[list[str]]:
    ordered = sorted(items)
    return [ordered[i:i + BATCH] for i in range(0, len(ordered), BATCH)]


def ask(queries: list[str], columns: tuple[str, ...], *,
        may_be_empty: bool = False) -> list[dict[str, str]]:
    """The checked rows of each query, one after another."""
    rows: list[dict[str, str]] = []
    for query in queries:
        rows.extend(checked_rows(name_usage._sparql_csv(query), columns,
                                 may_be_empty=may_be_empty))
    return rows


def load_scripts(forms: list[str], refresh: bool) -> dict[str, set[str]]:
    """The simplified forms of ``forms``, from the cache where it holds
    the answer to these very queries, from Wikidata otherwise: an
    answer to other forms, or to a query this code no longer writes, is
    never reused."""
    queries = [scripts_query(batch) for batch in batched(forms)]
    key = hashlib.sha256("".join(queries).encode("utf-8")).hexdigest()
    path = name_usage.cache_dir() / SCRIPTS_FILE
    cached = (json.loads(path.read_text(encoding="utf-8"))
              if path.exists() and not refresh else None)
    if cached is None or cached.get("query_sha256") != key:
        rows = ask(queries, ("item", "lab", "lang"))
        cached = {"query_sha256": key, "rows": rows}
        name_usage._write(path, cached)
    return read_scripts(cached["rows"])


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--write", action="store_true",
                        help="rewrite the generated block in zh.py")
    parser.add_argument("--refresh", action="store_true",
                        help="fetch the sources again")
    parser.add_argument("--top", type=int, default=TOP)
    args = parser.parse_args(argv)
    moi, items = load_moi(args.refresh), load_wikidata(args.refresh)
    forms = sorted(set().union(*(s.forms for s in select(
        moi, items, {}, args.top))))
    surnames = select(moi, items, load_scripts(forms, args.refresh), args.top)
    module_text = ZH_MODULE.read_text(encoding="utf-8")
    listed = listed_by_hand(module_text)
    forms = additions(surnames, listed)
    for s in surnames:
        new = "+" if s.forms - listed else " "
        print(f"{new} {s.rank:4}  Taiwan {s.moi_rank or '-':>4}  "
              f"Wikidata {s.wikidata_rank or '-':>4}  "
              f"{' '.join(sorted(s.forms))}")
    print(f"{len(surnames)} surnames; {len(forms)} forms not in the hand-kept "
          "rows", file=sys.stderr)
    if args.write:
        ZH_MODULE.write_text(rewrite(module_text, render(forms)),
                             encoding="utf-8")
        print(f"wrote {ZH_MODULE}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
