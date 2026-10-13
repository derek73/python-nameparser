"""How often is a word borne as a given name, and as a family name?

WHY THIS IS IN THE TREE. Vocabulary claims are weighed by
decisions.md#vocabulary-collisions: a word the parser claims by
position (titles, never-given particles) is safe to claim outright only
if it is not borne as a name IN THE POSITION THE CLAIM ACTS ON (C-i;
decisions.md#salutation-titles records the one TITLES-only exception,
decided on counts). That check was often run from memory, which misses
what the data shows at once: `shehu`, a title until #660, is also an
Albanian and Nigerian surname, with 561 bearers in the 2010 US Census.
This answers the question with counts instead.

    uv run python tools/name_usage.py shehu greve marshal
    uv run python tools/name_usage.py McDonald     # pass names as written
    uv run python tools/name_usage.py --no-wikidata knight   # offline
    uv run python tools/name_usage.py --json justice         # machine-readable

It reports; it does not decide. Read the counts against the rule's
position qualifier: given-name bearers threaten a title or a leading
particle in every culture, while family-name bearers threaten one only
where the family name is written first -- which is what Wikidata's
per-country breakdown is for.

What a number means depends on its source, and the report says so:

- US Census 2010 surnames (public domain): surnames with 100 or more
  bearers, with rank and ethnic shares. A surname under 100 is not
  listed, so it reports "<100", never 0. Downloaded once into the
  cache.
- US Social Security given names, 1880 onward (CC0 via data.gov),
  summed by sex across all years. A name-sex pair is listed for a year
  only with 5 or more births, so a count is a floor and an unlisted
  name reports "<5/yr". ssa.gov refuses scripted downloads, so this
  file is fetched by hand -- the tool says where to put it.
- Wikidata (CC0), queried live: people whose given name (P735) or
  family name (P734) is an item labelled with the word, with their
  countries of citizenship. A LOWER BOUND: many people have no P735
  statement at all (Shehu Shagari has none), so a small count proves
  little and a zero proves nothing. Labels are matched exactly, in the
  spellings the report lists, so a name with internal capitals is found
  only when passed as written (`McDonald`, not `mcdonald`).

Both US sources spell names in ASCII letters only, without spaces or
punctuation (O'Brien is OBRIEN), so a word is folded the same way
before lookup. A letter the fold cannot carry over (any non-Latin
script) makes the word unrepresentable there: no answer, never a zero.

Data is cached outside the repository, in $NAMEPARSER_TOOLS_CACHE or
~/.cache/nameparser-tools, so third-party data stays out of the tree.

Exit status is 2 when any source failed to answer (a query error, an
unusable download), so a script cannot mistake a partial report for a
complete one; a source that is merely not downloaded is not a failure.
"""
from __future__ import annotations

import argparse
import csv
import http.client
import io
import json
import os
import re
import sys
import unicodedata
import urllib.parse
import urllib.request
import zipfile
from collections import Counter
from collections.abc import Callable
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Literal, TypeVar

CENSUS_URL = "https://www2.census.gov/topics/genealogy/2010surnames/names.zip"
CENSUS_FILE = "census2010_surnames.zip"
CENSUS_MEMBER = "Names_2010Census.csv"
CENSUS_COLUMNS = {"name", "rank", "count", "pctwhite", "pctblack", "pctapi",
                  "pcthispanic"}
SSA_URL = "https://www.ssa.gov/oact/babynames/names.zip"
SSA_FILE = "ssa_names.zip"
#: The national file holds one yobYYYY.txt per year from 1880. Fewer than
#: this many is a partial or wrong download (the state-level zip holds
#: AK.TXT and so on, none of them yob files).
SSA_MIN_YEARS = 100
WIKIDATA_ENDPOINT = "https://query.wikidata.org/sparql"
USER_AGENT = ("nameparser-name-usage/0.1 "
              "(https://github.com/derek73/python-nameparser)")

#: Label languages a name item is matched in. `mul` is Wikidata's
#: language-independent label, which many name items carry; the rest
#: catch items labelled only in a language of their own. Matching one
#: exact literal per language keeps the query on the label index -- a
#: FILTER over every label times out.
WIKIDATA_LANGUAGES = (
    "mul", "en", "de", "fr", "es", "it", "pt", "nl", "sv", "da", "nb",
    "fi", "et", "lv", "lt", "pl", "cs", "sk", "sl", "hr", "sr", "bs",
    "hu", "ro", "bg", "ru", "uk", "el", "tr", "az", "sq", "ga", "cy",
    "is", "ar", "fa", "ur", "he", "hi", "bn", "ta", "te", "ja", "ko",
    "vi", "th", "id", "ms", "tl", "sw", "ha", "yo", "ig", "am", "so",
    # Chinese labels sit under script and region tags far more often
    # than plain `zh`: neither 关 surname item has a `zh` or `mul` label,
    # so without these a simplified-script surname finds nothing.
    "zh", "zh-hans", "zh-hant", "zh-cn", "zh-tw", "zh-hk", "zh-sg", "yue",
)

#: Letters NFKD leaves whole, so an ASCII fold would delete them and look
#: up a different name (Sørensen as SRENSEN). Spelled as English-language
#: records spell them.
_TRANSLITERATE = str.maketrans({
    "ß": "ss", "ẞ": "SS", "ø": "o", "Ø": "O", "æ": "ae", "Æ": "AE",
    "œ": "oe", "Œ": "OE", "ł": "l", "Ł": "L", "đ": "d", "Đ": "D",
    "ð": "d", "Ð": "D", "þ": "th", "Þ": "TH", "ı": "i", "ŋ": "ng", "Ŋ": "NG",
})

Status = Literal["ok", "unrepresentable", "not downloaded", "failed"]
T = TypeVar("T")


@dataclass(slots=True)
class Usage:
    """One source's answer for one word.

    `given`/`family` are None when the source gave no answer for that
    role -- it does not cover the role, or `status` says why it could
    not answer. A number is a count; `floor` says what an unlisted name
    reads as instead of 0 ("<100"), and `lower_bound` that the true
    count may be higher.
    """

    source: str
    status: Status = "ok"
    given: int | None = None
    family: int | None = None
    floor: str = ""
    lower_bound: bool = False
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


# -- the US sources' spelling ---------------------------------------------

def us_key(word: str) -> str:
    """Fold a word the way the Census and SSA lists spell names: ASCII
    letters only, upper-cased. Empty when any letter of the word has no
    ASCII spelling -- a lossy fold looks up a DIFFERENT name, which is
    worse than no lookup."""
    folded = unicodedata.normalize("NFKD", word.translate(_TRANSLITERATE))
    letters = []
    for ch in folded:
        # Combining marks are accents NFKD split off; modifier letters
        # (category Lm) are apostrophe-like marks such as the Hawaiian
        # ʻokina in Kaʻahumanu. Both are dropped, as O'Brien's apostrophe
        # is -- refusing them would leave such names with no answer.
        if unicodedata.combining(ch) or unicodedata.category(ch) == "Lm":
            continue
        if ch.isascii():
            if ch.isalpha():
                letters.append(ch)
        elif ch.isalpha():
            return ""
    return "".join(letters).upper()


def _lookup_note(word: str, key: str) -> str:
    return "" if key == word.upper() else f"looked up as {key}"


def _join(*parts: str) -> str:
    return "; ".join(p for p in parts if p)


# -- US Census surnames --------------------------------------------------

def read_census(csv_text: str) -> dict[str, dict[str, str]]:
    reader = csv.DictReader(io.StringIO(csv_text))
    missing = CENSUS_COLUMNS - set(reader.fieldnames or ())
    if missing:
        raise ValueError(f"Census file lacks columns {sorted(missing)}; "
                         f"has {reader.fieldnames}")
    return {row["name"]: row for row in reader}


def load_census(download: bool) -> dict[str, dict[str, str]] | None:
    """The cached Census table; None when it is not cached and `download`
    is off. Raises ValueError naming the cache file when the cached file
    is unusable."""
    path = cache_dir() / CENSUS_FILE
    if not path.exists():
        if not download:
            return None
        print(f"downloading {CENSUS_URL} ...", file=sys.stderr)
        _download(CENSUS_URL, path, required_member=CENSUS_MEMBER)
    try:
        with zipfile.ZipFile(path) as zf:
            return read_census(zf.read(CENSUS_MEMBER).decode("utf-8"))
    except (zipfile.BadZipFile, KeyError, ValueError) as exc:
        raise ValueError(f"{path} is unusable ({exc}); delete it and run "
                         "again to re-download") from exc


def census_usage(word: str, table: dict[str, dict[str, str]] | None) -> Usage:
    usage = Usage("US Census 2010 surnames", floor="<100")
    if table is None:
        usage.status = "not downloaded"
        usage.note = "not cached, and --no-wikidata does not download"
        return usage
    key = us_key(word)
    if not key:
        usage.status = "unrepresentable"
        usage.note = "a letter has no ASCII spelling in the Census list"
        return usage
    row = table.get(key)
    if row is None:
        usage.family = 0
        usage.note = _join("not listed: under 100 bearers, or none",
                           _lookup_note(word, key))
        return usage
    shares = ", ".join(
        f"{label} {row[col]}%" for label, col in (
            ("white", "pctwhite"), ("black", "pctblack"),
            ("asian/PI", "pctapi"), ("hispanic", "pcthispanic"))
        if row[col] not in ("(S)", ""))
    usage.family = int(row["count"])
    usage.note = _join(f"rank {int(row['rank']):,}", shares,
                       _lookup_note(word, key))
    return usage


# -- US Social Security given names --------------------------------------

_YOB = re.compile(r"yob(\d{4})\.txt", re.IGNORECASE)


def read_ssa(zf: zipfile.ZipFile, source: str = "the SSA zip",
             ) -> dict[str, Counter[str]]:
    """Total each given name's births by sex across every yobYYYY.txt,
    matched by basename in any case so a re-zipped folder still reads.
    Raises ValueError when the zip is not the national file."""
    totals: dict[str, Counter[str]] = {}
    years = 0
    for member in zf.namelist():
        if not _YOB.fullmatch(Path(member).name):
            continue
        years += 1
        for number, line in enumerate(
                zf.read(member).decode("utf-8").splitlines(), 1):
            if not line.strip():
                continue
            try:
                name, sex, count = line.split(",")
                totals.setdefault(name.lower(), Counter())[sex] += int(count)
            except ValueError as exc:
                raise ValueError(f"{source}: {member} line {number} is not "
                                 f"Name,Sex,Count: {line!r}") from exc
    if years < SSA_MIN_YEARS:
        raise ValueError(
            f"{source} holds {years} yobYYYY.txt files; the national file "
            f"from {SSA_URL} holds one per year since 1880")
    return totals


def load_ssa() -> dict[str, Counter[str]] | None:
    path = cache_dir() / SSA_FILE
    if not path.exists():
        return None
    try:
        with zipfile.ZipFile(path) as zf:
            return read_ssa(zf, str(path))
    except zipfile.BadZipFile as exc:
        raise ValueError(f"{path} is not a zip ({exc}); save {SSA_URL} "
                         "there again") from exc


def ssa_missing_message() -> str:
    return (f"SSA given names not downloaded. ssa.gov refuses scripted "
            f"downloads, so open {SSA_URL} in a browser and save it as "
            f"{cache_dir() / SSA_FILE}")


def ssa_usage(word: str, table: dict[str, Counter[str]] | None) -> Usage:
    usage = Usage("US SSA given names 1880-", floor="<5/yr", lower_bound=True)
    if table is None:
        usage.status = "not downloaded"
        usage.note = "see the end of the report"
        return usage
    key = us_key(word)
    if not key:
        usage.status = "unrepresentable"
        usage.note = "a letter has no ASCII spelling in the SSA list"
        return usage
    sexes = table.get(key.lower())
    if not sexes:
        usage.given = 0
        usage.note = _join("not listed: under 5 births of either sex in "
                           "every year, or none", _lookup_note(word, key))
        return usage
    usage.given = sum(sexes.values())
    usage.note = _join(", ".join(f"{sex} {n:,}" for sex, n in sorted(sexes.items())),
                       _lookup_note(word, key))
    return usage


# -- Wikidata ------------------------------------------------------------

def spellings(word: str) -> list[str]:
    """The label spellings a word is matched in: as written, lower-case,
    and capitalized per word. A name with internal capitals (McDonald)
    has no rule that reconstructs it, so it must be passed as written."""
    capped = " ".join(w[:1].upper() + w[1:].lower() for w in word.split(" "))
    return list(dict.fromkeys([word, word.lower(), capped, word.title()]))


def _values(forms: list[str], languages: tuple[str, ...]) -> str:
    return " ".join(f"{json.dumps(form, ensure_ascii=False)}@{lang}"
                    for form in forms for lang in languages)


def _people(forms: list[str], languages: tuple[str, ...]) -> str:
    # Every spelling in one VALUES block, so COUNT(DISTINCT ?p) counts a
    # person reached through two spellings once.
    return f"""
  VALUES ?label {{ {_values(forms, languages)} }}
  ?item rdfs:label ?label .
  {{ ?p wdt:P735 ?item . BIND("given" AS ?role) }}
  UNION
  {{ ?p wdt:P734 ?item . BIND("family" AS ?role) }}"""


def wikidata_totals_query(forms: list[str],
                          languages: tuple[str, ...] = WIKIDATA_LANGUAGES,
                          ) -> str:
    return f"""
SELECT ?role (COUNT(DISTINCT ?p) AS ?n) WHERE {{{_people(forms, languages)}
}} GROUP BY ?role"""


def wikidata_countries_query(forms: list[str],
                             languages: tuple[str, ...] = WIKIDATA_LANGUAGES,
                             ) -> str:
    """People per role and country of citizenship. A country with no
    English label is named by its Q-id rather than dropped, and an
    "unknown value" citizenship (a blank-node IRI, not an item) is named
    as such, so only a person with no P27 at all lands in the empty
    country. A person with two citizenships counts under both, so these
    rows may sum past the role's total, which comes from
    wikidata_totals_query."""
    return f"""
SELECT ?role ?country (COUNT(DISTINCT ?p) AS ?n) WHERE {{{_people(forms, languages)}
  OPTIONAL {{ ?p wdt:P27 ?c .
             OPTIONAL {{ ?c rdfs:label ?cl . FILTER(LANG(?cl) = "en") }} }}
  BIND(IF(!BOUND(?c), "",
          COALESCE(?cl, IF(STRSTARTS(STR(?c), STR(wd:)),
                           STRAFTER(STR(?c), STR(wd:)),
                           "unknown citizenship")))
       AS ?country)
}} GROUP BY ?role ?country"""


def _bindings(response: dict[str, Any]) -> list[dict[str, str]]:
    return [{key: cell["value"] for key, cell in row.items()}
            for row in response["results"]["bindings"]]


def read_wikidata(totals: list[dict[str, str]],
                  by_country: list[dict[str, str]], top: int) -> Usage:
    """Raises ValueError on a role the queries cannot produce, rather
    than letting it fall through to a count of 0."""
    roles = {"given", "family"}
    for row in totals + by_country:
        if row["role"] not in roles:
            raise ValueError(f"unexpected role {row['role']!r}")
    counts = {role: 0 for role in roles}
    for row in totals:
        counts[row["role"]] = int(row["n"])
    countries: dict[str, list[tuple[str, int]]] = {role: [] for role in roles}
    stateless = {role: 0 for role in roles}
    for row in by_country:
        if row.get("country"):
            countries[row["role"]].append((row["country"], int(row["n"])))
        else:
            stateless[row["role"]] += int(row["n"])
    for role in roles:
        countries[role].sort(key=lambda item: -item[1])
    return Usage(
        "Wikidata people", given=counts["given"], family=counts["family"],
        lower_bound=True,
        given_countries=countries["given"][:top],
        family_countries=countries["family"][:top],
        given_stateless=stateless["given"],
        family_stateless=stateless["family"])


def wikidata_usage(word: str, top: int) -> Usage:
    forms = spellings(word)
    try:
        usage = read_wikidata(
            _bindings(_sparql(wikidata_totals_query(forms))),
            _bindings(_sparql(wikidata_countries_query(forms))), top)
    except (OSError, ValueError, KeyError, http.client.HTTPException) as exc:
        return Usage("Wikidata people", status="failed", lower_bound=True,
                     note=f"query failed: {type(exc).__name__}: {exc}")
    zero = "a zero proves nothing" if not (usage.given or usage.family) else ""
    usage.note = _join("matched as " + ", ".join(forms), zero)
    return usage


def _sparql(query: str) -> dict[str, Any]:
    url = WIKIDATA_ENDPOINT + "?" + urllib.parse.urlencode({"query": query})
    request = urllib.request.Request(url, headers={
        "Accept": "application/sparql-results+json",
        "User-Agent": USER_AGENT})
    with urllib.request.urlopen(request, timeout=90) as response:
        result: dict[str, Any] = json.load(response)
    return result


def _download(url: str, path: Path, required_member: str) -> None:
    """Fetch a zip into the cache, refusing to cache anything that is not
    a zip holding `required_member` -- an error page saved under the
    cache name would otherwise break every later run."""
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(request, timeout=120) as response:
        data = response.read()
    try:
        with zipfile.ZipFile(io.BytesIO(data)) as zf:
            zf.getinfo(required_member)
    except (zipfile.BadZipFile, KeyError) as exc:
        raise ValueError(f"{url} did not return a zip holding "
                         f"{required_member} ({exc}); it began {data[:80]!r}"
                         ) from exc
    tmp = path.with_suffix(".part")
    tmp.write_bytes(data)
    tmp.replace(path)


# -- output --------------------------------------------------------------

def _attempt(load: Callable[[], T | None]) -> tuple[T | None, str]:
    """Run a source's loader, returning its table (None when not
    downloaded) and "" -- or None and the error it raised. A source that
    cannot be loaded is reported per word as failed; it must not take the
    other sources' answers down with it."""
    try:
        return load(), ""
    except (OSError, ValueError, http.client.HTTPException) as exc:
        return None, f"{type(exc).__name__}: {exc}"


def _count(n: int | None, usage: Usage) -> str:
    if n is None:
        return "-"
    if n == 0 and usage.floor:
        return usage.floor
    return f"{n:,}+" if usage.lower_bound else f"{n:,}"


def render(word: str, usages: list[Usage]) -> str:
    lines = [word]
    width = max(len(u.source) for u in usages)
    lines.append(f"  {'source':<{width}}  {'given':>9}  {'family':>9}")
    for u in usages:
        lines.append(f"  {u.source:<{width}}  {_count(u.given, u):>9}  "
                     f"{_count(u.family, u):>9}")
        note = u.note if u.status == "ok" else _join(u.status, u.note)
        if note:
            lines.append(f"  {'':<{width}}    {note}")
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
                        help="offline: cached sources only, nothing downloaded")
    parser.add_argument("--countries", type=int, default=5, metavar="N",
                        help="countries of citizenship to list per role")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)

    census, census_error = _attempt(
        lambda: load_census(download=not args.no_wikidata))
    ssa, ssa_error = _attempt(load_ssa)

    report = {}
    for word in args.words:
        census_row, ssa_row = census_usage(word, census), ssa_usage(word, ssa)
        for row, error in ((census_row, census_error), (ssa_row, ssa_error)):
            if error:
                row.status, row.note = "failed", error
        usages = [census_row, ssa_row]
        if not args.no_wikidata:
            usages.append(wikidata_usage(word, args.countries))
        report[word] = usages
    if args.json:
        print(json.dumps({w: [asdict(u) for u in us] for w, us in report.items()},
                         ensure_ascii=False, indent=2))
    else:
        print("\n\n".join(render(w, us) for w, us in report.items()))
    if ssa is None and not ssa_error:
        sys.stdout.flush()  # keep the notice after the report, not before it
        print("\n" + ssa_missing_message(), file=sys.stderr)
    failed = any(u.status == "failed" for us in report.values() for u in us)
    return 2 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
