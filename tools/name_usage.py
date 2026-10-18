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
    uv run python tools/name_usage.py 殿 議員 二世           # CJK: ends-with too

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
- Wikidata, name ends with (CC0), for a word holding a Han, kana or
  hangul letter only: people bearing a name item whose CJK label ENDS
  in the word, which is what a glued honorific's peel risks (#707). The
  matching runs against a local index of every CJK label on the
  name-item classes, fetched once (resumable; 33 minutes on 2026-10-17) and
  refreshed with --refresh-index; the bearers are counted live. It
  also counts the names the word ends ACROSS the family/given join,
  family ending 部 + given 長 for 部長. A lower bound, like the row
  above, and blind to people whose name has no item at all.

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
import shutil
import sys
import time
import unicodedata
import urllib.error
import urllib.parse
import urllib.request
import zipfile
from collections import Counter
from collections.abc import Callable
from dataclasses import asdict, dataclass, field
from datetime import date
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
#: Times a rate-limited query is retried after its Retry-After.
SPARQL_RETRIES = 5

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
    #: Where the word can end a name across the family/given boundary,
    #: the ends-with row only.
    splits: list[Split] = field(default_factory=list)


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


def _unrepresentable(source: str, word: str) -> str:
    if is_cjk(word):
        return (f"does not apply to a CJK word: the {source} list spells "
                "names in Latin letters only")
    return f"a letter has no ASCII spelling in the {source} list"


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
        usage.note = _unrepresentable("Census", word)
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
        usage.note = _unrepresentable("SSA", word)
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


def _label_match(forms: list[str], languages: tuple[str, ...]) -> str:
    # Every spelling in one VALUES block, so COUNT(DISTINCT ?p) counts a
    # person reached through two spellings once.
    return f"""VALUES ?label {{ {_values(forms, languages)} }}
  ?item rdfs:label ?label ."""


def _item_match(qids: list[str]) -> str:
    return "VALUES ?item { " + " ".join(f"wd:{q}" for q in qids) + " }"


def _people(match: str) -> str:
    return f"""
  {match}
  {{ ?p wdt:P735 ?item . BIND("given" AS ?role) }}
  UNION
  {{ ?p wdt:P734 ?item . BIND("family" AS ?role) }}"""


def wikidata_totals_query(forms: list[str],
                          languages: tuple[str, ...] = WIKIDATA_LANGUAGES,
                          ) -> str:
    return _totals_query(_label_match(forms, languages))


def wikidata_countries_query(forms: list[str],
                             languages: tuple[str, ...] = WIKIDATA_LANGUAGES,
                             ) -> str:
    return _countries_query(_label_match(forms, languages))


def _totals_query(match: str) -> str:
    return f"""
SELECT ?role (COUNT(DISTINCT ?p) AS ?n) WHERE {{{_people(match)}
}} GROUP BY ?role"""


def _countries_query(match: str) -> str:
    """People per role and country of citizenship. A country with no
    English label is named by its Q-id rather than dropped, and an
    "unknown value" citizenship (a blank-node IRI, not an item) is named
    as such, so only a person with no P27 at all lands in the empty
    country. A person with two citizenships counts under both, so these
    rows may sum past the role's total, which comes from
    _totals_query."""
    return f"""
SELECT ?role ?country (COUNT(DISTINCT ?p) AS ?n) WHERE {{{_people(match)}
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
    than letting it fall through to a count of 0. Rows from several
    queries over disjoint item sets are summed."""
    roles = {"given", "family"}
    for row in totals + by_country:
        if row["role"] not in roles:
            raise ValueError(f"unexpected role {row['role']!r}")
    counts = {role: 0 for role in roles}
    for row in totals:
        counts[row["role"]] += int(row["n"])
    countries: dict[str, Counter[str]] = {role: Counter() for role in roles}
    stateless = {role: 0 for role in roles}
    for row in by_country:
        if row.get("country"):
            countries[row["role"]][row["country"]] += int(row["n"])
        else:
            stateless[row["role"]] += int(row["n"])
    return Usage(
        "Wikidata people", given=counts["given"], family=counts["family"],
        lower_bound=True,
        given_countries=countries["given"].most_common(top),
        family_countries=countries["family"].most_common(top),
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


#: Patched out by the tests.
_sleep = time.sleep


def _sparql(query: str) -> dict[str, Any]:
    result: dict[str, Any] = json.loads(
        _post(query, "application/sparql-results+json"))
    return result


def _sparql_csv(query: str) -> list[dict[str, str]]:
    """The rows as CSV, for a listing too big for JSON: 700,581 family-name
    items are 30MB as CSV and were cut off at 73MB as JSON (2026-10-17)."""
    return list(csv.DictReader(io.StringIO(_post(query, "text/csv").decode())))


def _post(query: str, accept: str) -> bytes:
    # POSTed, not a GET: the VALUES block repeats every spelling once per
    # label language, so a seven-letter Cyrillic word already pushes the
    # URL past the endpoint's limit (HTTP 431, #680).
    body = urllib.parse.urlencode({"query": query}).encode()
    request = urllib.request.Request(WIKIDATA_ENDPOINT, data=body, headers={
        "Accept": accept,
        "Content-Type": "application/x-www-form-urlencoded; charset=utf-8",
        "User-Agent": USER_AGENT})
    for attempt in range(SPARQL_RETRIES + 1):
        try:
            with urllib.request.urlopen(request, timeout=90) as response:
                data: bytes = response.read()
            return data
        except urllib.error.HTTPError as exc:
            # WDQS gives each client about a minute of query time a
            # minute and answers 429 past it; the index build reaches
            # that within a few queries.
            if exc.code != 429 or attempt == SPARQL_RETRIES:
                raise
            retry = exc.headers.get("Retry-After", "")
            wait = int(retry) if retry.isdigit() else 60
            print(f"rate-limited by {WIKIDATA_ENDPOINT}; waiting {wait}s",
                  file=sys.stderr)
            _sleep(wait)
    raise AssertionError("unreachable")


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


# -- Wikidata CJK name index ----------------------------------------------
#
# Exact labels answer "is this word a name?"; a glued honorific asks
# whether a name can END in the word (#707). WDQS cannot answer that
# live: STRENDS over every label of every name item ran past its 60s
# limit even with no person join (measured 2026-10-17), and its full-text
# search matches a CJK word only where the tokenizer split it out (4 of
# the ~90 Japanese surnames ending in 殿). So the CJK labels of the name
# classes are fetched once into the cache, a word is matched there, and
# only the bearers of the matching items are counted live.
#
# The fetch lists a class's items, then asks for their labels by VALUES
# batch. Slicing the class inside one query instead (by Q-id suffix)
# scans the whole class every time -- 700,581 family-name items -- so a
# slice of 250 labels overran as surely as one of 25,000.

#: Name-item classes the index lists, and the role their items play.
#: Read off the P31 statements of known items, 2026-10-17: Japanese and
#: Chinese items usually carry the general class beside their own, but
#: not always, and the undifferentiated kanji surnames (高橋, 阿部 as bare
#: kanji, no reading) carry only theirs.
NAME_CLASSES = {
    "Q101352": "family",    # family name
    "Q19914123": "family",  # Japanese family name
    "Q88865432": "family",  # undifferentiated kanji surname
    "Q1093580": "family",   # Chinese family name
    "Q27951364": "family",  # Korean family name
    "Q202444": "given",     # given name
    "Q12308941": "given",   # male given name
    "Q11879590": "given",   # female given name
    "Q3409032": "given",    # unisex given name
    "Q22812564": "given",   # Japanese given name
    "Q22809413": "given",   # Chinese given name
}
INDEX_DIR = "wikidata_cjk_names"
#: Items per label query. Measured 2026-10-17 on family-name items not
#: queried before: 1,000 took 2.2-2.4s and 2,000 took 24s.
INDEX_BATCH = 1000
#: A batch that overruns is halved; one this small that still overruns
#: is an error, not a reason to keep halving.
INDEX_MIN_BATCH = 50
#: Items per bearer query; more are counted in several and summed.
ITEM_CHUNK = 500
ENDS_WITH_SOURCE = "Wikidata people, name ends with"

#: Kana with the iteration mark 々, the CJK ideograph blocks with their
#: compatibility block, hangul syllables, and halfwidth katakana. One
#: such letter makes a label CJK; the query and is_cjk share it.
_CJK_CHARS = ("々぀-ヿ㐀-鿿가-힯"
              "豈-﫿･-ﾟ")
_CJK = re.compile(f"[{_CJK_CHARS}]")


def is_cjk(word: str) -> bool:
    return _CJK.search(word) is not None


@dataclass(frozen=True, slots=True)
class IndexEntry:
    qid: str
    role: str
    label: str


@dataclass(slots=True)
class Split:
    """People whose family name ends in `family_tail` and whose given
    name is `given`, so that the two written together end in the word:
    阿部 + 長 ends in 部長."""

    family_tail: str
    given: str
    family_items: list[str]
    given_items: list[str]
    family_examples: list[str] = field(default_factory=list)
    people: int | None = None
    example: str = ""


@dataclass(slots=True)
class NameIndex:
    entries: list[IndexEntry]
    fetched: str

    def ending_in(self, word: str) -> list[IndexEntry]:
        return [e for e in self.entries if e.label.endswith(word)]

    def boundaries(self, word: str) -> list[Split]:
        given: dict[str, set[str]] = {}
        for e in self.entries:
            if e.role == "given":
                given.setdefault(e.label, set()).add(e.qid)
        splits = []
        for cut in range(1, len(word)):
            tail, rest = word[:cut], word[cut:]
            if rest not in given:
                continue
            family = [e for e in self.entries
                      if e.role == "family" and e.label.endswith(tail)]
            if family:
                splits.append(Split(
                    tail, rest, sorted({e.qid for e in family}),
                    sorted(given[rest]),
                    sorted({e.label for e in family})[:3]))
        return splits


def ids_query(cls: str) -> str:
    return f"SELECT ?item WHERE {{ ?item wdt:P31 wd:{cls} }}"


def count_query(cls: str) -> str:
    return f"SELECT (COUNT(?item) AS ?n) WHERE {{ ?item wdt:P31 wd:{cls} }}"


def labels_query(qids: list[str]) -> str:
    """The CJK labels of the items, every language."""
    return f"""
SELECT ?item ?label WHERE {{
  {_item_match(qids)}
  ?item rdfs:label ?label .
  FILTER(REGEX(STR(?label), "[{_CJK_CHARS}]"))
}}"""


class _Overrun(Exception):
    """The endpoint ran out of time on a query; a smaller one may not."""


class _Missing(Exception):
    """Part of the index is not cached and fetching is off."""


def _qid(iri: str) -> str:
    qid = iri.rsplit("/", 1)[-1]
    if not re.fullmatch(r"Q\d+", qid):
        raise ValueError(f"index row names {iri!r}, not an item")
    return qid


def _index_sparql(query: str, as_csv: bool = False) -> list[dict[str, str]]:
    try:
        return _sparql_csv(query) if as_csv else _bindings(_sparql(query))
    except urllib.error.HTTPError as exc:
        # A 500 is an overrun only when it says so: halving a malformed
        # query would send it again and again.
        if exc.code in (502, 504) or (
                exc.code == 500 and b"TimeoutException" in exc.read()):
            raise _Overrun(f"HTTP {exc.code}") from exc
        raise
    except (ValueError, TimeoutError, http.client.IncompleteRead) as exc:
        # At its limit WDQS cuts a 200 off mid-stream, which surfaces as
        # JSON that stops (ValueError) or a short read.
        raise _Overrun(f"{type(exc).__name__}: {exc}") from exc


def _write(path: Path, data: object) -> None:
    tmp = path.with_suffix(".part")
    tmp.parent.mkdir(parents=True, exist_ok=True)
    tmp.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
    tmp.replace(path)


def _class_ids(cls: str, fetch: bool) -> list[str]:
    path = cache_dir() / INDEX_DIR / f"{cls}-ids.json"
    if path.exists():
        ids: list[str] = json.loads(path.read_text(encoding="utf-8"))
        return ids
    if not fetch:
        raise _Missing(path.name)
    try:
        [count] = _index_sparql(count_query(cls))
        rows = _index_sparql(ids_query(cls), as_csv=True)
    except _Overrun as exc:
        raise ValueError(f"listing wd:{cls} items overran ({exc})") from exc
    # CSV has no closing bracket to show a stream cut short, so the
    # listing is held to a count taken just before it. The slack is for
    # edits landing between the two queries; a cut loses far more.
    expected = int(count["n"])
    if len(rows) < expected - expected // 1000:
        raise ValueError(f"listing wd:{cls} returned {len(rows):,} of "
                         f"{expected:,} items; it was cut short")
    # Lexemes, their senses and their forms (L1000723, L2873-S1) carry
    # P31 family name too, and no person bears one; anything else that
    # is not an item is still an error.
    ids = sorted({_qid(row["item"]) for row in rows
                  if not re.search(r"/L\d+(-[SF]\d+)?$", row["item"])},
                 key=lambda q: int(q[1:]))
    _write(path, ids)
    print(f"  wd:{cls}: {len(ids):,} items", file=sys.stderr)
    return ids


def _fetch_batch(cls: str, ids: list[str], start: int, end: int, fetch: bool,
                 out: list[IndexEntry], dates: set[str]) -> bool:
    """Read the labels of ids[start:end] into `out`, querying them if they
    are not cached and halving the batch when it overruns. A finished
    batch is written at once and a halved one is marked, so a build that
    stops resumes where it stopped and never re-asks a halved batch.
    True when anything was queried."""
    base = cache_dir() / INDEX_DIR / f"{cls}-{start}-{end}"
    done, halved = base.with_suffix(".json"), base.with_suffix(".halved")
    if done.exists():
        data = json.loads(done.read_text(encoding="utf-8"))
        dates.add(data["fetched"])
        out.extend(IndexEntry(q, NAME_CLASSES[cls], label)
                   for q, label in data["rows"])
        return False
    if not halved.exists():
        if not fetch:
            raise _Missing(done.name)
        try:
            rows = [[_qid(row["item"]), row["label"]]
                    for row in _index_sparql(labels_query(ids[start:end]))]
        except _Overrun as exc:
            if end - start <= INDEX_MIN_BATCH:
                raise ValueError(f"wd:{cls} items {start}-{end} still "
                                 f"overran ({exc})") from exc
            halved.parent.mkdir(parents=True, exist_ok=True)
            halved.touch()
        else:
            today = date.today().isoformat()
            _write(done, {"fetched": today, "rows": rows})
            dates.add(today)
            out.extend(IndexEntry(q, NAME_CLASSES[cls], label)
                       for q, label in rows)
            return True
    middle = (start + end) // 2
    first = _fetch_batch(cls, ids, start, middle, fetch, out, dates)
    second = _fetch_batch(cls, ids, middle, end, fetch, out, dates)
    return first or second


def load_index(download: bool, refresh: bool = False) -> NameIndex | None:
    """The cached CJK name index; None when part of it is not cached and
    `download` is off. Building it is a one-time fetch of about a
    thousand queries, paced by the endpoint's rate limit, and resumable."""
    path = cache_dir() / INDEX_DIR
    if refresh and path.exists():
        shutil.rmtree(path)
    if download and not path.exists():
        print(f"building the CJK name index in {path} -- a one-time fetch "
              "of about half an hour; an interrupted build resumes",
              file=sys.stderr)
    entries: list[IndexEntry] = []
    dates: set[str] = set()
    try:
        for cls in NAME_CLASSES:
            ids = _class_ids(cls, download)
            for start in range(0, len(ids), INDEX_BATCH):
                end = min(start + INDEX_BATCH, len(ids))
                fetched = _fetch_batch(cls, ids, start, end, download,
                                       entries, dates)
                if fetched and (start // INDEX_BATCH) % 50 == 49:
                    print(f"  wd:{cls}: {end:,} of {len(ids):,} items",
                          file=sys.stderr)
    except _Missing:
        return None
    return NameIndex(list(dict.fromkeys(entries)),
                     fetched=min(dates) if dates else "")


def _count_items(qids: list[str], top: int) -> tuple[Usage, int]:
    chunks = [qids[i:i + ITEM_CHUNK] for i in range(0, len(qids), ITEM_CHUNK)]
    totals: list[dict[str, str]] = []
    by_country: list[dict[str, str]] = []
    for chunk in chunks:
        totals += _bindings(_sparql(_totals_query(_item_match(chunk))))
        by_country += _bindings(_sparql(_countries_query(_item_match(chunk))))
    return read_wikidata(totals, by_country, top), len(chunks)


def _count_split(split: Split) -> None:
    family = " ".join(f"wd:{q}" for q in split.family_items)
    given = " ".join(f"wd:{q}" for q in split.given_items)
    [row] = _bindings(_sparql(f"""
SELECT (COUNT(DISTINCT ?p) AS ?n) (SAMPLE(?p) AS ?example) WHERE {{
  VALUES ?f {{ {family} }}
  VALUES ?g {{ {given} }}
  ?p wdt:P734 ?f ; wdt:P735 ?g .
}}""")) or [{"n": "0"}]
    split.people = int(row["n"])
    split.example = row.get("example", "").rsplit("/", 1)[-1]


def ends_with_usage(word: str, index: NameIndex, top: int) -> Usage:
    """Bearers of the indexed name items whose label ends in the word,
    and of the family/given pairs that end in it together."""
    matches = index.ending_in(word)
    qids = sorted({e.qid for e in matches})
    fetched = f"index fetched {index.fetched}"
    try:
        if qids:
            usage, queries = _count_items(qids, top)
            # With its Q-id, so an item reached through a transcription or
            # a mislabel (厄德二世 is the given name Odo) can be looked up.
            named = sorted({(e.label, e.qid) for e in matches})
            shown = ", ".join(f"{label} {qid}" for label, qid in named[:8])
            if len(named) > 8:
                shown += ", ..."
            twice = (f"summed over {queries} queries, so a person bearing "
                     "two of these names may count twice"
                     if queries > 1 else "")
            items = "1 name item ends" if len(qids) == 1 else (
                f"{len(qids)} name items end")
            usage.note = _join(f"{items} in it: {shown}",
                               twice, fetched)
        else:
            usage = Usage("", given=0, family=0, lower_bound=True,
                          note=_join(f"no indexed name item ends in {word}",
                                     fetched))
        usage.splits = index.boundaries(word)
        for split in usage.splits:
            _count_split(split)
    except (OSError, ValueError, KeyError, http.client.HTTPException) as exc:
        return Usage(ENDS_WITH_SOURCE, status="failed", lower_bound=True,
                     note=f"query failed: {type(exc).__name__}: {exc}")
    usage.source = ENDS_WITH_SOURCE
    return usage


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
        for split in u.splits:
            example = "; ".join(split.family_examples
                                + ([split.example] if split.example else []))
            lines.append(
                f"  {'':<{width}}    family ending {split.family_tail} + "
                f"given {split.given}: {_count(split.people, u)} people"
                + (f" (e.g. {example})" if example else ""))
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
    parser.add_argument("--refresh-index", action="store_true",
                        help="fetch the CJK name index again")
    args = parser.parse_args(argv)

    census, census_error = _attempt(
        lambda: load_census(download=not args.no_wikidata))
    ssa, ssa_error = _attempt(load_ssa)
    index: NameIndex | None = None
    index_error = ""
    if not args.no_wikidata and any(map(is_cjk, args.words)):
        index, index_error = _attempt(
            lambda: load_index(download=True, refresh=args.refresh_index))

    report = {}
    for word in args.words:
        census_row, ssa_row = census_usage(word, census), ssa_usage(word, ssa)
        for row, error in ((census_row, census_error), (ssa_row, ssa_error)):
            if error:
                row.status, row.note = "failed", error
        usages = [census_row, ssa_row]
        if not args.no_wikidata:
            usages.append(wikidata_usage(word, args.countries))
            if is_cjk(word):
                usages.append(
                    ends_with_usage(word, index, args.countries)
                    if index is not None else
                    Usage(ENDS_WITH_SOURCE, status="failed", lower_bound=True,
                          note=index_error or "the index did not load"))
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
