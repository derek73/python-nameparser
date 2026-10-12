"""How often is a word borne as a given name, and as a family name?

WHY THIS IS IN THE TREE. Vocabulary membership is decided by
decisions.md#vocabulary-collisions: a word may join a set the parser
claims by position (titles, never-given particles) only if it is not
borne as a name IN THE POSITION THE CLAIM ACTS ON. Until this tool,
that check was run from memory, and memory missed collisions the data
shows at once: `shehu` is an Albanian surname as well as a Hausa given
name, and `herra` (a title since #606) is borne by about 640 people in
the 2010 US Census. This answers the question with counts instead.

    uv run python tools/name_usage.py shehu greve marshal
    uv run python tools/name_usage.py --no-wikidata knight   # offline
    uv run python tools/name_usage.py --json justice         # machine-readable

It reports; it does not decide. Read the counts against the rule's
position qualifier: given-name bearers threaten a title or a leading
particle in every culture, while family-name bearers threaten one only
where the family name is written first -- which is what Wikidata's
per-country breakdown is for.

Sources, each answering for one role and one population:

- US Census 2010 surnames (public domain): every surname with 100 or
  more bearers, with rank and ethnic shares. Downloaded once into the
  cache. Census names are ASCII with spaces and punctuation removed
  (O'Brien is OBRIEN), so a word is folded the same way before lookup.
- US Social Security given names, 1880 onward (CC0 via data.gov),
  counted by sex across all years. ssa.gov refuses scripted downloads,
  so this one is fetched by hand -- the tool prints where to put it.
- Wikidata (CC0), queried live: people whose given name (P735) or
  family name (P734) is an item labelled with the word, with their
  countries of citizenship. A LOWER BOUND: many people have no P735
  statement at all (Shehu Shagari has none), so a small count proves
  little and a zero proves nothing.

Data is cached outside the repository, in $NAMEPARSER_TOOLS_CACHE or
~/.cache/nameparser-tools: third-party data stays out of the tree, and
the Census file alone is 9 MB.
"""
from __future__ import annotations

import argparse
import csv
import io
import json
import os
import sys
import unicodedata
import urllib.parse
import urllib.request
import zipfile
from collections import Counter
from dataclasses import asdict, dataclass, field
from pathlib import Path

CENSUS_URL = "https://www2.census.gov/topics/genealogy/2010surnames/names.zip"
CENSUS_MEMBER = "Names_2010Census.csv"
SSA_URL = "https://www.ssa.gov/oact/babynames/names.zip"
SSA_FILE = "ssa_names.zip"
WIKIDATA_ENDPOINT = "https://query.wikidata.org/sparql"
USER_AGENT = ("nameparser-name-usage/0.1 "
              "(https://github.com/derek73/python-nameparser)")

#: Label languages a name item is matched in. `mul` is Wikidata's
#: language-independent label, which most name items now carry; the
#: rest catch items labelled only in a language of their own. Matching
#: one exact literal per language keeps the query on the label index --
#: a FILTER over every label would time out.
WIKIDATA_LANGUAGES = (
    "mul", "en", "de", "fr", "es", "it", "pt", "nl", "sv", "da", "nb",
    "fi", "et", "lv", "lt", "pl", "cs", "sk", "sl", "hr", "sr", "bs",
    "hu", "ro", "bg", "ru", "uk", "el", "tr", "az", "sq", "ga", "cy",
    "is", "ar", "fa", "ur", "he", "hi", "bn", "ta", "te", "ja", "ko",
    "vi", "th", "id", "ms", "tl", "sw", "ha", "yo", "ig", "am", "so",
    # Chinese labels sit under script and region tags far more often
    # than plain `zh`: the 关 surname item is labelled only zh-hans and
    # zh-cn, so without these a simplified-script surname finds nothing.
    "zh", "zh-hans", "zh-hant", "zh-cn", "zh-tw", "zh-hk", "yue",
)


@dataclass
class Usage:
    """One source's answer for one word."""

    source: str
    given: int | None = None
    family: int | None = None
    #: Top countries of citizenship per role, Wikidata only.
    given_countries: list[tuple[str, int]] = field(default_factory=list)
    family_countries: list[tuple[str, int]] = field(default_factory=list)
    #: People of that role with no citizenship statement, kept out of the
    #: country lists: they are often the largest group and say nothing
    #: about which culture bears the name.
    given_stateless: int = 0
    family_stateless: int = 0
    note: str = ""


def cache_dir() -> Path:
    path = Path(os.environ.get("NAMEPARSER_TOOLS_CACHE",
                               Path.home() / ".cache" / "nameparser-tools"))
    path.mkdir(parents=True, exist_ok=True)
    return path


# -- US Census surnames --------------------------------------------------

def census_key(word: str) -> str:
    """Fold a word the way the Census list spells names: diacritics
    dropped, then everything but ASCII letters removed, upper-cased."""
    ascii_word = unicodedata.normalize("NFKD", word).encode(
        "ascii", "ignore").decode()
    return "".join(ch for ch in ascii_word if ch.isalpha()).upper()


def read_census(csv_text: str) -> dict[str, dict[str, str]]:
    return {row["name"]: row for row in csv.DictReader(io.StringIO(csv_text))}


def load_census() -> dict[str, dict[str, str]]:
    path = cache_dir() / "census2010_surnames.zip"
    if not path.exists():
        print(f"downloading {CENSUS_URL} ...", file=sys.stderr)
        _download(CENSUS_URL, path)
    with zipfile.ZipFile(path) as zf:
        return read_census(zf.read(CENSUS_MEMBER).decode("utf-8"))


def census_usage(word: str, table: dict[str, dict[str, str]]) -> Usage:
    key = census_key(word)
    if not key:
        return Usage("US Census 2010 surnames",
                     note="not representable in the Census's ASCII spelling")
    row = table.get(key)
    if row is None:
        return Usage("US Census 2010 surnames", family=0,
                     note="under 100 bearers, or absent")
    shares = ", ".join(
        f"{label} {row[col]}%" for label, col in (
            ("white", "pctwhite"), ("black", "pctblack"),
            ("asian/PI", "pctapi"), ("hispanic", "pcthispanic"))
        if row[col] not in ("(S)", ""))
    note = f"rank {int(row['rank']):,}; {shares}"
    if key != word.upper():
        note += f"; looked up as {key}"
    return Usage("US Census 2010 surnames", family=int(row["count"]),
                 note=note)


# -- US Social Security given names --------------------------------------

def read_ssa(zf: zipfile.ZipFile) -> dict[str, Counter[str]]:
    """Total each given name's births by sex across every yobYYYY.txt."""
    totals: dict[str, Counter[str]] = {}
    for member in zf.namelist():
        if not (member.startswith("yob") and member.endswith(".txt")):
            continue
        for line in zf.read(member).decode("utf-8").splitlines():
            if not line.strip():
                continue
            name, sex, count = line.split(",")
            totals.setdefault(name.lower(), Counter())[sex] += int(count)
    return totals


def load_ssa() -> dict[str, Counter[str]] | None:
    path = cache_dir() / SSA_FILE
    if not path.exists():
        return None
    with zipfile.ZipFile(path) as zf:
        return read_ssa(zf)


def ssa_missing_message() -> str:
    return (f"SSA given names not downloaded. ssa.gov refuses scripted "
            f"downloads, so open {SSA_URL} in a browser and save it as "
            f"{cache_dir() / SSA_FILE}")


def ssa_usage(word: str, table: dict[str, Counter[str]] | None) -> Usage:
    source = "US SSA given names 1880-"
    if table is None:
        return Usage(source, note="not downloaded (see the end of the report)")
    sexes = table.get(census_key(word).lower())
    if not sexes:
        return Usage(source, given=0, note="under 5 births in any year, or absent")
    split = ", ".join(f"{sex} {n:,}" for sex, n in sorted(sexes.items()))
    return Usage(source, given=sum(sexes.values()), note=split)


# -- Wikidata ------------------------------------------------------------

def wikidata_query(word: str, languages: tuple[str, ...] = WIKIDATA_LANGUAGES,
                   ) -> str:
    """People bearing `word` as given (P735) or family (P734) name, one
    row per role and country of citizenship. A person with no P27 lands
    under an empty country; one with two counts under both, so per-country
    counts may sum past the role's total -- the total comes from the
    distinct count, not from the sum."""
    literal = json.dumps(word, ensure_ascii=False)
    values = " ".join(f"{literal}@{lang}" for lang in languages)
    return f"""
SELECT ?role ?country (COUNT(DISTINCT ?p) AS ?n) WHERE {{
  VALUES ?label {{ {values} }}
  ?item rdfs:label ?label .
  {{ ?p wdt:P735 ?item . BIND("given" AS ?role) }}
  UNION
  {{ ?p wdt:P734 ?item . BIND("family" AS ?role) }}
  OPTIONAL {{ ?p wdt:P27 ?c . ?c rdfs:label ?country .
             FILTER(LANG(?country) = "en") }}
}} GROUP BY ?role ?country"""


def wikidata_totals_query(word: str,
                          languages: tuple[str, ...] = WIKIDATA_LANGUAGES,
                          ) -> str:
    literal = json.dumps(word, ensure_ascii=False)
    values = " ".join(f"{literal}@{lang}" for lang in languages)
    return f"""
SELECT ?role (COUNT(DISTINCT ?p) AS ?n) WHERE {{
  VALUES ?label {{ {values} }}
  ?item rdfs:label ?label .
  {{ ?p wdt:P735 ?item . BIND("given" AS ?role) }}
  UNION
  {{ ?p wdt:P734 ?item . BIND("family" AS ?role) }}
}} GROUP BY ?role"""


def _bindings(response: dict) -> list[dict[str, str]]:  # type: ignore[type-arg]
    return [{key: cell["value"] for key, cell in row.items()}
            for row in response["results"]["bindings"]]


def read_wikidata(totals: list[dict[str, str]],
                  by_country: list[dict[str, str]], top: int) -> Usage:
    usage = Usage("Wikidata people (lower bound)", given=0, family=0)
    for row in totals:
        setattr(usage, row["role"], int(row["n"]))
    for role in ("given", "family"):
        rows = [row for row in by_country if row["role"] == role]
        counts = sorted(((row["country"], int(row["n"]))
                         for row in rows if row.get("country")),
                        key=lambda item: -item[1])
        setattr(usage, f"{role}_countries", counts[:top])
        setattr(usage, f"{role}_stateless",
                sum(int(row["n"]) for row in rows if not row.get("country")))
    return usage


def wikidata_usage(word: str, top: int) -> Usage:
    forms = list(dict.fromkeys([word, word.capitalize()]))
    totals: list[dict[str, str]] = []
    by_country: list[dict[str, str]] = []
    try:
        for form in forms:
            totals += _bindings(_sparql(wikidata_totals_query(form)))
            by_country += _bindings(_sparql(wikidata_query(form)))
    except OSError as exc:
        return Usage("Wikidata people (lower bound)", note=f"query failed: {exc}")
    return read_wikidata(_merge(totals, ("role",)),
                         _merge(by_country, ("role", "country")), top)


def _merge(rows: list[dict[str, str]],
           keys: tuple[str, ...]) -> list[dict[str, str]]:
    """Sum counts from the case variants' queries. A person whose name
    item carries both spellings would count twice; name items carry one
    canonical label, so in practice the variants find different items."""
    merged: dict[tuple[str, ...], int] = {}
    for row in rows:
        key = tuple(row.get(k, "") for k in keys)
        merged[key] = merged.get(key, 0) + int(row["n"])
    return [dict(zip(keys, key), n=str(n)) for key, n in merged.items()]


def _sparql(query: str) -> dict:  # type: ignore[type-arg]
    url = WIKIDATA_ENDPOINT + "?" + urllib.parse.urlencode({"query": query})
    request = urllib.request.Request(url, headers={
        "Accept": "application/sparql-results+json",
        "User-Agent": USER_AGENT})
    with urllib.request.urlopen(request, timeout=90) as response:
        return json.load(response)  # type: ignore[no-any-return]


def _download(url: str, path: Path) -> None:
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(request, timeout=120) as response:
        data = response.read()
    tmp = path.with_suffix(".part")
    tmp.write_bytes(data)
    tmp.replace(path)


# -- output --------------------------------------------------------------

def _count(n: int | None) -> str:
    return "-" if n is None else f"{n:,}"


def render(word: str, usages: list[Usage]) -> str:
    lines = [word]
    width = max(len(u.source) for u in usages)
    lines.append(f"  {'source':<{width}}  {'given':>9}  {'family':>9}")
    for u in usages:
        lines.append(f"  {u.source:<{width}}  {_count(u.given):>9}  "
                     f"{_count(u.family):>9}")
        if u.note:
            lines.append(f"  {'':<{width}}    {u.note}")
        for role, countries, stateless in (
                ("given", u.given_countries, u.given_stateless),
                ("family", u.family_countries, u.family_stateless)):
            if countries or stateless:
                parts = [f"{c} {n}" for c, n in countries]
                if stateless:
                    parts.append(f"{stateless} with no citizenship stated")
                lines.append(f"  {'':<{width}}    {role} by citizenship: "
                             + ", ".join(parts))
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Count how often words are borne as given and family names.")
    parser.add_argument("words", nargs="+")
    parser.add_argument("--no-wikidata", action="store_true",
                        help="offline: cached sources only")
    parser.add_argument("--countries", type=int, default=5, metavar="N",
                        help="countries of citizenship to list per role")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)

    census = load_census()
    ssa = load_ssa()
    report = {}
    for word in args.words:
        usages = [census_usage(word, census), ssa_usage(word, ssa)]
        if not args.no_wikidata:
            usages.append(wikidata_usage(word, args.countries))
        report[word] = usages
    if args.json:
        print(json.dumps({w: [asdict(u) for u in us] for w, us in report.items()},
                         ensure_ascii=False, indent=2))
    else:
        print("\n\n".join(render(w, us) for w, us in report.items()))
    if ssa is None:
        sys.stdout.flush()  # keep the notice after the report, not before it
        print("\n" + ssa_missing_message(), file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
