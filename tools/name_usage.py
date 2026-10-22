"""How often is a word borne as a given name, and as a family name --
and how often is it written as a credential?

WHY THIS IS IN THE TREE. Vocabulary claims are weighed by
decisions/vocabulary-collisions: a word the parser claims by
position (titles, never-given particles) is safe to claim outright only
if it is not borne as a name IN THE POSITION THE CLAIM ACTS ON (C-i;
decisions/salutation-titles records the one TITLES-only exception,
decided on counts). That check was often run from memory, which misses
what the data shows at once: `shehu`, a title until #660, is also an
Albanian and Nigerian surname, with 561 bearers in the 2010 US Census.
This answers the question with counts instead.

    uv run python tools/name_usage.py shehu greve marshal
    uv run python tools/name_usage.py McDonald     # pass names as written
    uv run python tools/name_usage.py --no-wikidata knight   # offline
    uv run python tools/name_usage.py --json justice         # machine-readable
    uv run python tools/name_usage.py 殿 議員 二世           # CJK: ends-with too
    uv run python tools/name_usage.py In Bay Bin   # non-US given names
    uv run python tools/name_usage.py --fetch-nppes ma do   # credentials too
    uv run python tools/name_usage.py --rank 50 --unlisted  # top credentials

A suffix that collides with a name is the same question from the other
side: `ma`, `do` and `ba` are credentials and surnames both, and
decisions/suffix-acronym-collisions weighs which reading to keep. The
credential column answers its half, and --rank lists the commonest
credentials beside nameparser's vocabulary, their name counts and how a
comma name ending in each one parses (#797 came from that list).

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
- Wikidata, name ends with (CC0), only for a word holding at least one
  Han, kana or hangul letter: people bearing a name item whose CJK label ENDS
  in the word, which is what a glued honorific's peel risks (#707). The
  matching runs against a local index of every CJK rdfs:label (not aliases) on the
  name-item classes, fetched once (resumable; 33 minutes on 2026-10-17) and
  refreshed with --refresh-index; the bearers are counted live. It
  also counts the names the word ends ACROSS the family/given join,
  family ending 部 + given 長 for 部長. A lower bound, like the row
  above, and blind to people whose name has no item at all.

- nam_dict given names (Jörg Michael, 2008; GNU FDL 1.2), the
  dictionary shipped in the gender-guesser 0.4.0 sdist: 45,371 given-name
  spellings (counted 2026-10-19; the file is pinned), each with a
  frequency band in 55 columns, 54 countries and "other countries" in
  the order its own legend gives, 1 = rare up to D = extremely common.
  The scale is logarithmic, a factor of two a step only where a
  country's statistics are good. It is the non-US given-name evidence
  the other sources lack (Korean `In` is band A in Korea, Vietnamese
  `Bay` band 6 in Vietnam). A band is not a count, so the row's given
  cell shows the peak band and the bands go in `given_bands`. A
  SELECTION, not a census, and written in Latin letters only: a missing
  name proves nothing (`Shehu` has no entry), and a non-Latin word is
  unrepresentable. Matched ignoring case, in the Turkish fold too
  (`Ilker` finds `İlker`, `ışıl` finds `Işıl`), with
  a `+` in a listed name (`Jun+Wei`; the header says Arabic, Chinese and
  Korean names only) standing for a hyphen, a space or nothing. Other
  letters are matched as written: `Käte` and `Işıl` are listed, `Kaete`
  and `Isil` are not. Downloaded
  once into the cache, pinned by the sdist's sha256; only that one file
  is kept, and never in the tree.
- NPPES credentials (CMS, public; NBER's monthly mirror, since CMS keeps
  only the current month): the free-text credential field of every
  individual US healthcare provider, 7,415,294 of them in the pinned
  August 2026 file, 4,824,544 with a credential (counted 2026-10-21).
  The credential cell counts PROVIDERS writing the word, each once
  however often their field repeats it. A census of that field, so 0 is
  a real zero -- but only for US healthcare: law, accounting, academic
  and British credentials (`Esq`, `CPA`, `FRS`) are missing because the
  source holds no such people, not because nobody writes them. The
  file is upper-cased, so case is not recorded, and a word is matched
  ignoring case and periods, as the parser matches an acronym. 673 MB,
  so it is downloaded only when asked (--fetch-nppes, or --rank
  online), pinned by sha256, and read once into a tally cached beside
  it; the zip itself is never unpacked.

- Local corpora (tools/differential/local_corpora.py): whole names as
  people typed them, fetched into the cache by that script and never
  committed, so this tool only reads them. One row per local corpus,
  one not yet fetched naming the command that fetches it: the source's
  credit and data date, how many records write the word anywhere in the
  name and how many after a comma, and the spellings as written. Words
  are matched ignoring case, periods and edge punctuation
  (local_corpora.word_key); a spaced word ('Ph. D.') is matched as its
  words in a row, with the joined spelling's count beside it. The first is
  ClinicalTrials.gov's study officials, where `MD` after a comma is the
  usual case and a credential before it is the noise worth seeing.
  Not a census of anyone: it counts what the source's typists wrote.

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
import hashlib
import http.client
import io
import json
import os
import re
import shutil
import sys
import tarfile
import time
import unicodedata
import urllib.error
import urllib.parse
import urllib.request
import zipfile
import zlib
from collections import Counter
from collections.abc import Callable, Iterator
from dataclasses import asdict, dataclass, field
from datetime import date
from pathlib import Path
from types import ModuleType
from typing import TYPE_CHECKING, Any, Literal, TypeVar

if TYPE_CHECKING:  # loaded by path at run time, _local_corpora
    from local_corpora import Local

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
NAMDICT_URL = ("https://files.pythonhosted.org/packages/a8/dc/"
               "69939b7af56b7adf3aa2736771b7c3e7191f7cd36fbc80b0727570c275fa/"
               "gender-guesser-0.4.0.tar.gz")
NAMDICT_SHA256 = ("1591c14592805ca7da06a46d5f7202511f7cb87547049a68dfccbeedb879f31b")
NAMDICT_MEMBER = "gender-guesser-0.4.0/gender_guesser/data/nam_dict.txt"
NAMDICT_FILE = "nam_dict.txt"
NAMDICT_SOURCE = "nam_dict given names"
NAMDICT_CREDIT = ("nam_dict.txt by Jörg Michael (2008), GNU Free Documentation "
                  "License 1.2, from the gender-guesser 0.4.0 sdist")
#: Countries the legend must name; a file giving another number is not
#: the one the column reading was written for.
NAMDICT_COUNTRIES = 55
#: NBER keeps every month at a fixed URL (2025/08 still answered on
#: 2026-10-21); CMS's own page keeps only the current one.
#: The pinned month; re-pinning is this and NPPES_SHA256.
NPPES_MONTH = "202608"
NPPES_URL = (f"https://data.nber.org/npi/{NPPES_MONTH[:4]}/{NPPES_MONTH[4:]}/"
             f"core_{NPPES_MONTH}_csv.zip")
NPPES_SHA256 = ("5f431813422d843c2021ec839d2eb5f80d3117cc19de660ce70af79767bc1a13")
NPPES_MEMBER = f"core_{NPPES_MONTH}.csv"
NPPES_FILE = f"nppes_core_{NPPES_MONTH}_csv.zip"
NPPES_TALLY = f"nppes_core_{NPPES_MONTH}_credentials.json"
NPPES_SOURCE = "NPPES US healthcare credentials"
NPPES_SIZE = "673 MB"
#: Bumped whenever what the tally holds or how a field becomes keys
#: changes -- the `[,;]` split in tally_credentials, credential_key,
#: _squash or _resolve; a tally written by another version is rebuilt.
#: NPPES_MIN_ALONE and NPPES_SPELLINGS, beside _resolve, are written into
#: the tally and checked too, so changing either rebuilds it without a
#: bump.
TALLY_VERSION = 2  # 2: the tally keeps _resolve's spelling choice
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

    `given`/`family`/`credential` are None when the source gave no
    answer for that role -- it does not cover the role, or `status` says
    why it could not answer. A number is a count; `floor` says what an
    unlisted name reads as instead of 0 ("<100"), and `lower_bound` that
    the true count may be higher.
    """

    source: str
    status: Status = "ok"
    given: int | None = None
    family: int | None = None
    #: Providers writing the word as a credential, NPPES only.
    credential: int | None = None
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
    #: Frequency band per country as a given name, nam_dict only: 1
    #: (rare) to 13 (extremely common), highest first. Not a count, so
    #: `given` stays None beside it.
    given_bands: list[tuple[str, int]] = field(default_factory=list)
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

def _folded(word: str) -> Iterator[str]:
    """The word's characters with the letters NFKD leaves whole
    transliterated (_TRANSLITERATE) and the rest decomposed, less the
    marks no ASCII spelling keeps. Combining marks are accents NFKD split
    off; modifier letters (category Lm) are apostrophe-like marks such
    as the Hawaiian ʻokina in Kaʻahumanu. Both are dropped, as O'Brien's
    apostrophe is -- refusing them would leave such names with no
    answer."""
    for ch in unicodedata.normalize("NFKD", word.translate(_TRANSLITERATE)):
        if not (unicodedata.combining(ch) or unicodedata.category(ch) == "Lm"):
            yield ch


def us_key(word: str) -> str:
    """Fold a word the way the Census and SSA lists spell names: ASCII
    letters only, upper-cased. Empty when any letter of the word has no
    ASCII spelling -- a lossy fold looks up a DIFFERENT name, which is
    worse than no lookup."""
    letters = []
    for ch in _folded(word):
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


# -- nam_dict given names --------------------------------------------------
#
# Fixed-width lines, 0-based: a gender code in [0:2] (M, F, ?M, ...,
# which this tool does not report), the name from [3] to the sort flag at
# [29], one hexadecimal band per country from [30], in the order the
# comment legend gives, and " $" to end the line. Lines opening with "="
# are nickname equivalences ("=  Al Albert"). A "+" sort flag marks the
# lines re-sorted with expanded umlauts, which the header says to ignore;
# most repeat a "-" line, and the handful that do not (Saša) are skipped
# with them.

_NAME_START, _SORT_FLAG, _BANDS_START = 3, 29, 30
_LINE_END = " $"
#: The cached file's own sha256, checked at every load. A file cut at a
#: line boundary still parses and reports every name it lost as not
#: listed; a floor on the names read missed a cut that kept most of
#: them, and the file is pinned, so only its exact bytes are accepted.
NAMDICT_FILE_SHA256 = ("bfe79b1f3533d188333c36d7b0722868b873b2d366bb15bed3ed9a4f85db3c8c")


@dataclass(slots=True)
class NamDict:
    countries: list[str]
    #: Folded spelling -> a list of (spelling as listed, {country: band}),
    #: one per listing line and per "+" expansion: `dean` holds the M and
    #: ? lines of Dean and the ? line of De+An.
    names: dict[str, list[tuple[str, dict[str, int]]]]
    #: Folded short form -> the long forms it is listed as short for.
    short_for: dict[str, list[str]]

    def lookup(self, word: str) -> list[tuple[str, dict[str, int]]]:
        found = {id(e): e for key in namdict_keys(word)
                 for e in self.names.get(key, [])}
        return list(found.values())

    def short_forms(self, word: str) -> list[str]:
        return list(dict.fromkeys(long for key in namdict_keys(word)
                                  for long in self.short_for.get(key, [])))


def namdict_keys(word: str) -> list[str]:
    """The folds the dictionary is matched under, for stored names and
    looked-up words alike: the default case fold, with the dot it leaves
    on a Turkish İ (i + U+0307) dropped so Ilker finds İlker, and the
    Turkish one, where I lowers to dotless ı, so ışıl and IŞIL find
    Işıl. The dotless ı itself is a letter, not a case: Isil does not
    find Işıl, as Kaete does not find Käte."""
    turkish = word.replace("I", "ı").replace("İ", "i").lower()
    return list(dict.fromkeys([
        word.casefold().replace("i\u0307", "i"), turkish]))


def _legend(comments: list[str]) -> list[str]:
    """The countries in column order, read from the legend: each label
    line is followed by a line holding only a "|" in that country's
    column. Raises ValueError unless the bars fill NAMDICT_COUNTRIES
    consecutive columns from _BANDS_START."""
    countries, columns = [], []
    for above, line in zip(comments, comments[1:]):
        if line.strip("# $") == "|":
            countries.append(above.strip("# $"))
            columns.append(line.index("|"))
    expected = list(range(_BANDS_START, _BANDS_START + NAMDICT_COUNTRIES))
    if columns != expected:
        raise ValueError(f"nam_dict legend marks columns {columns}, not the "
                         f"{NAMDICT_COUNTRIES} from {_BANDS_START} this tool "
                         "reads")
    return countries


def expand_plus(name: str) -> list[str]:
    """The spellings a listed name stands for. A "+" is a hyphen, a space
    or nothing, the last joining lower-case as the header's example
    does: Jun+Wei is Jun-Wei, Jun Wei and Junwei."""
    first, *rest = name.split("+")
    forms = [first]
    for part in rest:
        forms = [f + joined for f in forms for joined in (
            "-" + part, " " + part, part[:1].lower() + part[1:])]
    return forms


def _fixed_width(line: str, countries: int) -> bool:
    # A line shifted by a column keeps its length, so the gaps around
    # the name are checked too: read shifted, In's Korea band lands
    # under Vietnam and the name gains a leading space.
    return (len(line) == _BANDS_START + countries + len(_LINE_END)
            and line.endswith(_LINE_END) and line[2] == " "
            and line[_NAME_START] != " " and line[_SORT_FLAG - 1] == " ")


def read_namdict(text: str) -> NamDict:
    lines = text.splitlines()
    countries = _legend([line for line in lines if line.startswith("#")])
    names: dict[str, list[tuple[str, dict[str, int]]]] = {}
    short_for: dict[str, list[str]] = {}
    for number, line in enumerate(lines, 1):
        if not line or line.startswith("#"):
            continue
        if not _fixed_width(line, len(countries)):
            raise ValueError(f"nam_dict line {number} is not fixed-width: "
                             f"{line!r}")
        if line[_SORT_FLAG] == "+":
            continue
        name = line[_NAME_START:_SORT_FLAG].rstrip()
        if line.startswith("="):
            pair = name.split()
            if len(pair) != 2:
                raise ValueError(f"nam_dict line {number} is not "
                                 f"'=  short long': {line!r}")
            for key in namdict_keys(pair[0]):
                short_for.setdefault(key, []).append(pair[1])
            continue
        bands = {}
        for country, digit in zip(
                countries, line[_BANDS_START:_BANDS_START + len(countries)]):
            if digit != " ":
                try:
                    bands[country] = int(digit, 16)
                except ValueError:
                    raise ValueError(f"nam_dict line {number} has band "
                                     f"{digit!r} for {country}") from None
        # The name as listed is filed too, so Jun+Wei copied from the
        # file finds itself.
        entry = (name, bands)
        for key in dict.fromkeys(k for form in [name, *expand_plus(name)]
                                 for k in namdict_keys(form)):
            names.setdefault(key, []).append(entry)
    return NamDict(countries, names, short_for)


def _fetch_namdict(path: Path) -> None:
    """Download the sdist, check it against NAMDICT_SHA256, and cache the
    one member. The archive is read in memory and never unpacked to
    disk. Raises ValueError when the pinned constants do not describe
    the archive (a hash or member left stale by an edit), so the other
    sources still answer."""
    request = urllib.request.Request(NAMDICT_URL,
                                     headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(request, timeout=120) as response:
        data = response.read()
    digest = hashlib.sha256(data).hexdigest()
    if digest != NAMDICT_SHA256:
        raise ValueError(f"{NAMDICT_URL} has sha256 {digest}, not the "
                         f"pinned {NAMDICT_SHA256}")
    try:
        with tarfile.open(fileobj=io.BytesIO(data), mode="r:gz") as tf:
            member = tf.extractfile(NAMDICT_MEMBER)
            if member is None:
                raise ValueError("it is not a file")
            text = member.read()
    except (tarfile.TarError, KeyError, EOFError, zlib.error) as exc:
        raise ValueError(f"cannot read {NAMDICT_MEMBER} from {NAMDICT_URL} "
                         f"({exc})") from exc
    digest = hashlib.sha256(text).hexdigest()
    if digest != NAMDICT_FILE_SHA256:
        raise ValueError(f"{NAMDICT_MEMBER} in {NAMDICT_URL} has sha256 "
                         f"{digest}, not the pinned {NAMDICT_FILE_SHA256}")
    tmp = path.with_suffix(".part")
    tmp.write_bytes(text)
    tmp.replace(path)


def load_namdict(download: bool) -> NamDict | None:
    """The cached dictionary; None when it is not cached and `download`
    is off. Raises ValueError naming the cache file when it is unusable,
    and lets a failed download through as raised (OSError, or ValueError
    from _fetch_namdict)."""
    path = cache_dir() / NAMDICT_FILE
    if not path.exists():
        if not download:
            return None
        print(f"downloading {NAMDICT_CREDIT} ...", file=sys.stderr)
        _fetch_namdict(path)
    try:
        data = path.read_bytes()
        digest = hashlib.sha256(data).hexdigest()
        if digest != NAMDICT_FILE_SHA256:
            raise ValueError(f"sha256 {digest}, not the pinned file's "
                             f"{NAMDICT_FILE_SHA256}")
        return read_namdict(data.decode("utf-8"))
    except ValueError as exc:  # UnicodeDecodeError included
        raise ValueError(f"{path} is unusable ({exc}); delete it and run "
                         "again to re-download") from exc


def _latin_only(word: str) -> bool:
    return all(not ch.isalpha() or unicodedata.name(ch, "").startswith("LATIN")
               for ch in word)


def namdict_usage(word: str, table: NamDict | None, top: int) -> Usage:
    usage = Usage(NAMDICT_SOURCE, lower_bound=True)
    if table is None:
        usage.status = "not downloaded"
        usage.note = "not cached, and --no-wikidata does not download"
        return usage
    if not _latin_only(word):
        usage.status = "unrepresentable"
        usage.note = "the dictionary spells names in Latin letters only"
        return usage
    entries = table.lookup(word)
    short = ", ".join(table.short_forms(word))
    short_note = f"listed as a short form of {short}" if short else ""
    if not entries:
        usage.note = _join("not listed, which proves nothing: the dictionary "
                           "is a selection, and letters are matched as "
                           "written (Käte, not Kaete; Işıl, not Isil)",
                           short_note)
        return usage
    peak: dict[str, int] = {}
    for _, bands in entries:
        for country, band in bands.items():
            peak[country] = max(band, peak.get(country, 0))
    order = {c: i for i, c in enumerate(table.countries)}
    ranked = sorted(peak.items(), key=lambda cb: (-cb[1], order[cb[0]]))
    usage.given_bands = ranked[:top]
    listed = ", ".join(dict.fromkeys(name for name, _ in entries))
    more = len(ranked) - top
    usage.note = _join(
        f"listed as {listed}",
        f"banded in {len(ranked)} "
        + ("country" if len(ranked) == 1 else "countries") + (
            f", the top {top} shown" if more > 0 else ""),
        "1 rare to D extremely common, logarithmic: x2 a step where the "
        "statistics are good",
        short_note)
    return usage


# -- NPPES credentials -----------------------------------------------------
#
# A provider's credential field is a list written by hand: 'MD',
# 'M.D., PH.D.', 'MS CCC-SLP', 'PHARM D', 'NURSE PRACTITIONER'. Commas
# and semicolons divide it into segments, which are taken as written. A
# segment holding a space is one of three things, and the data tells
# them apart, since every piece is also written somewhere as a whole
# segment of its own:
#
# - one credential in pieces ('PHARM D', 'M. D.', 'PA C', 'OTR L'): the
#   pieces joined are written alone far more often than the rarest
#   piece is -- PHARMD 138,758 times against PHARM's 160 and D's 839;
# - several credentials ('MD PHD', 'MS CCC-SLP', 'RN BSN'): each piece
#   is written alone more often than the pieces joined (MD/PHD and MD-PHD
#   755 times against PHD's 112,945);
# - a job title ('NURSE PRACTITIONER', 'REGISTERED NURSE'): some piece is
#   rarely written alone at all (PRACTITIONER 19 times, REGISTERED 12),
#   and the segment stays whole.
#
# A segment kept whole takes any credential in it along: 'MA COUNSELING'
# is a key of its own, and its providers do not count toward MA. The
# kept segments holding MS have 1,448 providers, MA 1,212, MD 684 and PHD
# 420 -- an undercount of 1.2% of MA, 0.95% of MS and less of the others,
# a little less still since a few of them write the credential in
# another segment too. Splitting the credential off
# instead would split 'NURSE PRACTITIONER' as well, NURSE being written
# alone 583 times, and give NURSE up to 12,213 more providers (687 write
# it as a credential); the undercount is the smaller error.
#
# (Counts measured on the pinned file, 2026-10-21.)

#: A piece written alone fewer times than this, that joins with nothing,
#: marks its segment as a phrase. Measured 2026-10-21: the job-title
#: words sit at 11-22 (ASSISTANT, REGISTERED, PRACTITIONER, ASSOCIATE)
#: and the rarest fragment that must still split off at 97 (LIC).
NPPES_MIN_ALONE = 50
NPPES_SPELLINGS = 5


def credential_key(text: str) -> str:
    """A credential as the tally files it: upper-cased with every period
    dropped and spaces collapsed, which is how the parser matches an
    acronym (M.D. and md are MD). Hyphens and slashes are kept, so
    FNP-C and OTR/L are their own keys."""
    return " ".join(text.upper().replace(".", "").split())


def _squash(text: str) -> str:
    return "".join(ch for ch in text if ch.isalnum())


def _resolve(segment: str, alone: Counter[str],
             joined: dict[str, tuple[str, int]]) -> list[tuple[str, str]]:
    """The (key, spelling) pairs a spaced segment stands for, by the rules
    above. `alone` counts each key written as a whole segment, and
    `joined` maps a key's letters and digits to its commonest spelling
    among those keys and their summed count."""
    # A piece that is only periods ('M . D.') folds to nothing and is
    # dropped with its spelling, so the two lists stay aligned.
    written = [w for w in segment.split() if credential_key(w)]
    pieces = [credential_key(w) for w in written]
    out: list[tuple[str, str]] = []
    i = 0
    while i < len(pieces):
        for j in range(len(pieces), i + 1, -1):
            hit = joined.get(_squash("".join(pieces[i:j])))
            if hit and hit[1] > min(alone[p] for p in pieces[i:j]):
                out.append((hit[0], " ".join(written[i:j])))
                i = j
                break
        else:
            if alone[pieces[i]] < NPPES_MIN_ALONE:
                return [(" ".join(pieces), " ".join(written))]
            out.append((pieces[i], written[i]))
            i += 1
    return out


@dataclass(slots=True)
class CredentialTally:
    #: Individual providers read, and those with any credential.
    people: int
    credentialed: int
    #: Key -> (providers writing it, its commonest spellings with counts).
    tokens: dict[str, tuple[int, list[tuple[str, int]]]]
    #: A key's letters and digits -> the key _resolve files a spaced
    #: segment of those letters under ('PAC' -> 'PA-C'), kept so the
    #: lookup reads the tally's own choice instead of deriving one.
    joined: dict[str, str]

    def __post_init__(self) -> None:
        """What every tally must hold, built or loaded. An empty one
        would answer 0 for every word -- the false zero this source must
        not give -- and happens if the entity column's coding changes
        ('Individual' read as 1), which the pin cannot see. A share divides
        by `credentialed`, and --rank prints each token's first spelling,
        so a cache breaking either would crash the run outside the
        loader's error handling."""
        if not self.tokens:
            raise ValueError(f"no individual provider with a credential "
                             f"({self.people:,} individuals read)")
        if not 0 < self.credentialed <= self.people:
            raise ValueError(f"credentialed {self.credentialed:,} is not "
                             f"between 1 and people {self.people:,}")
        for key, (n, spellings) in self.tokens.items():
            if not (0 < n <= self.credentialed and spellings
                    and all(c > 0 for _, c in spellings)):
                raise ValueError(f"token {key!r} needs a count from 1 to "
                                 "credentialed and a spelling")
        for letters, key in self.joined.items():
            if key not in self.tokens or _squash(key) != letters:
                raise ValueError(f"joined {letters!r} names {key!r}, not a "
                                 "token with those letters")

    def ranked(self) -> list[tuple[str, int, list[tuple[str, int]]]]:
        return sorted(((k, n, s) for k, (n, s) in self.tokens.items()),
                      key=lambda row: (-row[1], row[0]))


def tally_credentials(rows: Iterator[dict[str, str]]) -> CredentialTally:
    """Count the credential tokens of the individual providers in `rows`
    (dicts with `entity` and `pcredential`). Spaced segments are settled
    after the scan, once `alone` holds every whole-segment count."""
    people = 0
    fields: Counter[tuple[str, ...]] = Counter()
    for row in rows:
        if row["entity"] != "Individual":
            continue
        people += 1
        segments = tuple(" ".join(s.split())
                         for s in re.split(r"[,;]", row["pcredential"]))
        segments = tuple(s for s in segments if s.strip("."))
        if segments:
            fields[segments] += 1
    alone: Counter[str] = Counter()
    for segments, n in fields.items():
        for s in segments:
            if " " not in s:
                alone[credential_key(s)] += n
    joined: dict[str, tuple[str, int]] = {}
    for key, n in alone.most_common():
        # The commonest spelling comes first and keeps the entry.
        spelling, total = joined.get(_squash(key), (key, 0))
        joined[_squash(key)] = (spelling, total + n)
    providers: Counter[str] = Counter()
    spellings: dict[str, Counter[str]] = {}
    for segments, n in fields.items():
        keys = set()
        for s in segments:
            pairs = (_resolve(s, alone, joined) if " " in s
                     else [(credential_key(s), s)])
            for key, spelling in pairs:
                keys.add(key)
                spellings.setdefault(key, Counter())[spelling] += n
        for key in keys:
            providers[key] += n
    return CredentialTally(
        people, sum(fields.values()),
        {k: (n, spellings[k].most_common(NPPES_SPELLINGS))
         for k, n in providers.items()},
        {letters: key for letters, (key, _) in joined.items()})


def _fetch_nppes(path: Path) -> None:
    """Stream the pinned zip into the cache, hashing as it lands, and
    keep it only when the hash and the member are the pinned ones."""
    print(f"downloading {NPPES_URL} ({NPPES_SIZE}) ...", file=sys.stderr)
    request = urllib.request.Request(NPPES_URL, headers={"User-Agent": USER_AGENT})
    tmp = path.with_suffix(".part")
    digest = hashlib.sha256()
    try:
        with urllib.request.urlopen(request, timeout=120) as response, \
                tmp.open("wb") as out:
            while chunk := response.read(1 << 20):
                digest.update(chunk)
                out.write(chunk)
        if digest.hexdigest() != NPPES_SHA256:
            raise ValueError(f"{NPPES_URL} has sha256 {digest.hexdigest()}, "
                             f"not the pinned {NPPES_SHA256}")
        try:
            with zipfile.ZipFile(tmp) as zf:
                zf.getinfo(NPPES_MEMBER)
        except (zipfile.BadZipFile, KeyError) as exc:
            raise ValueError(f"cannot read {NPPES_MEMBER} from {NPPES_URL} "
                             f"({exc})") from exc
        tmp.replace(path)
    finally:
        tmp.unlink(missing_ok=True)


def _read_nppes(path: Path) -> CredentialTally:
    """Tally the zip, read in place. The zip is checked against its pin
    first, since the tally written from it is trusted afterwards."""
    digest = hashlib.sha256()
    with path.open("rb") as fh:
        while chunk := fh.read(1 << 20):
            digest.update(chunk)
    if digest.hexdigest() != NPPES_SHA256:
        raise ValueError(f"sha256 {digest.hexdigest()}, not the pinned "
                         f"{NPPES_SHA256}")
    print(f"tallying credentials in {path} (about a minute, once) ...",
          file=sys.stderr)
    try:
        with zipfile.ZipFile(path) as zf, zf.open(NPPES_MEMBER) as raw:
            reader = csv.DictReader(io.TextIOWrapper(raw, encoding="utf-8"))
            missing = {"entity", "pcredential"} - set(reader.fieldnames or ())
            if missing:
                raise ValueError(f"{NPPES_MEMBER} lacks columns {sorted(missing)}")
            return tally_credentials(reader)
    except (zipfile.BadZipFile, KeyError, EOFError, zlib.error,
            csv.Error) as exc:
        raise ValueError(f"cannot read {NPPES_MEMBER} ({exc})") from exc


def _tally_rules() -> dict[str, int]:
    return {"min_alone": NPPES_MIN_ALONE, "spellings": NPPES_SPELLINGS}


def _tally_json(tally: CredentialTally) -> dict[str, Any]:
    return {"version": TALLY_VERSION, "source_sha256": NPPES_SHA256,
            "rules": _tally_rules(),
            "people": tally.people, "credentialed": tally.credentialed,
            "tokens": {k: [n, [list(s) for s in spellings]]
                       for k, (n, spellings) in tally.tokens.items()},
            "joined": tally.joined}


def _tally_from_json(data: object) -> CredentialTally | None:
    """The tally a cache file holds; None when it was written by another
    version or from another zip, so it is rebuilt. Raises ValueError on
    anything else that is not a tally."""
    if not isinstance(data, dict):
        raise ValueError("not a tally object")
    if (data.get("version") != TALLY_VERSION
            or data.get("source_sha256") != NPPES_SHA256
            or data.get("rules") != _tally_rules()):
        return None
    people, credentialed, tokens, joined = (
        data.get("people"), data.get("credentialed"), data.get("tokens"),
        data.get("joined"))
    if not (isinstance(people, int) and isinstance(credentialed, int)
            and isinstance(tokens, dict) and isinstance(joined, dict)
            and all(isinstance(v, str) for v in joined.values())):
        raise ValueError("needs people, credentialed, a tokens map and a "
                         "joined map")
    out: dict[str, tuple[int, list[tuple[str, int]]]] = {}
    for key, value in tokens.items():
        if not (isinstance(value, list) and len(value) == 2
                and isinstance(value[0], int) and isinstance(value[1], list)
                and all(isinstance(s, list) and len(s) == 2
                        and isinstance(s[0], str) and isinstance(s[1], int)
                        for s in value[1])):
            raise ValueError(f"token {key!r} is not [count, spellings]")
        out[key] = (value[0], [(s, n) for s, n in value[1]])
    # Types are checked here; values by CredentialTally itself.
    return CredentialTally(people, credentialed, out, joined)


def load_nppes(download: bool) -> CredentialTally | None:
    """The cached tally, built from the cached zip when it is missing or
    stale, and the zip downloaded first only when `download` is on;
    None when neither is cached and `download` is off. Raises ValueError
    naming the file it cannot use, and lets a failed download through
    as raised."""
    zip_path, tally_path = cache_dir() / NPPES_FILE, cache_dir() / NPPES_TALLY
    if tally_path.exists():
        try:
            cached = _tally_from_json(json.loads(
                tally_path.read_text(encoding="utf-8")))
        except ValueError as exc:  # json.JSONDecodeError included
            raise ValueError(f"{tally_path} is unusable ({exc}); delete it "
                             "and run again to re-tally") from exc
        if cached is not None:
            return cached
    if not zip_path.exists():
        if not download:
            return None
        _fetch_nppes(zip_path)
    try:
        tally = _read_nppes(zip_path)
    except ValueError as exc:
        raise ValueError(f"{zip_path} is unusable ({exc}); delete it and run "
                         "again with --fetch-nppes to re-download") from exc
    _write(tally_path, _tally_json(tally))
    return tally


def _share(fraction: float) -> str:
    # A credential a few hundred providers write is under 0.01%, which
    # 2 places would print as a zero.
    return "<0.01%" if 0 < fraction < 0.0001 else f"{fraction:.2%}"


def ascii_credential(word: str) -> str:
    """The word as the NPPES file could spell it: accents dropped, the
    letters us_key transliterates spelled out, any dash written as a
    hyphen (PA–C is PA-C), and ASCII punctuation and digits kept for
    credential_key. Empty when anything else non-ASCII is left -- a
    letter, a curly quote -- since the file holds no such character (0 of
    49,116 keys, 2026-10-21), and a word that can only miss must not read
    as a zero."""
    kept = []
    for ch in _folded(word):
        if unicodedata.category(ch) == "Pd":
            ch = "-"
        if not ch.isascii():
            return ""
        kept.append(ch)
    return "".join(kept)


_NPPES_SCOPE = "US healthcare only: a credential of another field reads 0 here"


def credential_usage(word: str, tally: CredentialTally | None) -> Usage:
    usage = Usage(NPPES_SOURCE)
    if tally is None:
        usage.status = "not downloaded"
        usage.note = (f"not cached; --fetch-nppes downloads it "
                      f"({NPPES_SIZE}, once)")
        return usage
    # Empty too for a word of nothing but spaces, periods or combining
    # marks, which would otherwise read "no provider writes" no key.
    key = credential_key(ascii_credential(word))
    if not key:
        usage.status = "unrepresentable"
        usage.note = ("nothing in it is a credential the NPPES file could "
                      "spell; it spells every one in ASCII")
        return usage
    # Keys differing only in punctuation are spellings of one credential
    # kept apart (PA-C, PAC). A spaced word is looked up under the spelling
    # the tally files those letters under when _resolve joins a segment,
    # so 'PA C' finds PA-C and not PAC. It does not ask whether _resolve
    # would join it: 'MD PHD' finds MD/PHD's 721, though the tally counted
    # those segments as MD and PHD. Letters only spaced keys hold (a job
    # title, 'REGISTERED NURSE') have no stored choice, and a word spaced
    # unlike all of them takes the commonest: 'Registered / Nurse' finds
    # REGISTERED NURSE's 5,054. And every answer names the others, so a
    # spelling few write cannot stand alone: OTR-L's 416 providers are
    # reported beside OTR/L's 61,789. A word with no letters or digits
    # ('-') shares them with nothing.
    letters = _squash(key)
    sharing = sorted(((k, n) for k, (n, _) in tally.tokens.items()
                      if k != key and _squash(k) == letters),
                     key=lambda kn: (-kn[1], kn[0])) if letters else []
    if key in tally.tokens:
        found: str | None = key
    elif " " in key and sharing:
        found = tally.joined.get(letters, sharing[0][0])
        sharing = [kn for kn in sharing if kn[0] != found]
    else:
        found = None
    others = ("also written " + ", ".join(f"{k} {n:,}" for k, n in sharing[:3])
              if sharing else "")
    if found is None:
        usage.credential = 0
        usage.note = _join(f"no provider writes {key}", others, _NPPES_SCOPE)
        return usage
    n, spellings = tally.tokens[found]
    usage.credential = n
    usage.note = _join(
        f"{_share(n / tally.credentialed)} of {tally.credentialed:,} credentialed "
        "providers",
        "written " + ", ".join(f"{s} {c:,}" for s, c in spellings),
        _lookup_note(word, found), others, _NPPES_SCOPE)
    return usage


# -- local corpora ---------------------------------------------------------

def _local_corpora() -> ModuleType:
    """tools/differential/local_corpora.py, which owns the local corpora's
    cache layout and the checks on loading one, loaded by path the way
    the differential tools load corpus_build."""
    here = str(Path(__file__).resolve().parent / "differential")
    if here not in sys.path:
        sys.path.append(here)
    import local_corpora
    return local_corpora


def load_locals() -> list[tuple[str, Local | None, str]]:
    """Every local corpus: (source, the corpus or None when not fetched,
    the error that stopped it loading). load() refuses with ValueError
    anything it cannot read, so a damaged corpus fails its own row."""
    module = _local_corpora()
    return [(source, *_attempt(lambda source=source: module.load(source)))
            for source in sorted(module.SOURCES)]


def local_usage(word: str, source: str, local: Local | None) -> Usage:
    module = _local_corpora()
    usage = Usage(f"{source} (local corpus)")
    if local is None:
        usage.status = "not downloaded"
        usage.note = (f"not fetched; tools/differential/local_corpora.py "
                      f"fetch {source}")
        return usage
    keys = module.words(word)
    if not keys:
        usage.status = "unrepresentable"
        usage.note = "nothing in it is left once periods and punctuation go"
        return usage
    unit = module.SOURCES[source].unit
    credit = f"{module.SOURCES[source].credit}, data as of {local.meta['data_date']}"
    index = local.index
    if len(keys) == 1:
        anywhere, after = index.anywhere[keys[0]], index.after_comma[keys[0]]
        written = index.spellings.get(keys[0])
        spelled = ("written " + ", ".join(f"{s} {n:,}" for s, n in
                                          written.most_common(3))
                   if written else "")
    else:
        # A spaced word ('Ph. D.') is no key of the index, which holds
        # single words: its words are looked for in a row instead, and
        # the same letters written as one word are reported beside it.
        anywhere, after = module.phrase_counts(local, keys)
        joined = "".join(keys)
        spelled = (f"as one word '{joined}' {index.anywhere[joined]:,}"
                   if index.anywhere[joined] else "")
    usage.note = _join(
        credit,
        f"{anywhere:,} of {len(local.records):,} {unit} write it, "
        f"{after:,} after a comma", spelled)
    return usage


def local_rows(word: str, locals_: list[tuple[str, Local | None, str]]) -> list[Usage]:
    """One row per local corpus, a corpus that failed to load reported
    as failed. A function of its own so its loop names cannot shadow
    main's: written inline there, its `index` replaced the CJK name
    index the ends-with row reads."""
    rows = []
    for source, local, error in locals_:
        row = local_usage(word, source, local)
        if error:
            row.status, row.note = "failed", error
        rows.append(row)
    return rows


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
                     note=_failure(exc))
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
    """The rows as CSV, for a listing too big for JSON: the 700,581
    family-name listing rows are 30MB as CSV and were cut off at 73MB as JSON (2026-10-17)."""
    body = _post(query, "text/csv").decode()
    if body and not body.endswith("\n"):
        # A line cut inside its IRI is still a valid Q-id (Q1234567
        # arriving as Q12); the missing line end is the only sign.
        raise ValueError("CSV response ends mid-line; it was cut short")
    try:
        return list(csv.DictReader(io.StringIO(body)))
    except csv.Error as exc:
        raise ValueError(f"unreadable CSV response: {exc}") from exc


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
            exc.close()  # it holds the response; 3.14 warns on a leak
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
# scans the whole class every time -- 700,581 family-name listing rows,
# 700,304 items once lexemes are dropped -- so a slice of 250 labels
# overran as surely as one of 25,000.

Role = Literal["given", "family"]

#: Name-item classes the index lists, and the role their items play.
#: Counted on the index, 2026-10-17: Japanese and Chinese family-name
#: items and Chinese given-name items nearly all carry the general class
#: beside their own, but Japanese given names almost never do (13 of
#: 4,620), nor do most male and female given names, and the
#: undifferentiated kanji surnames (高橋, 阿部 as bare kanji, no
#: reading) carry only theirs -- so every class is listed.
NAME_CLASSES: dict[str, Role] = {
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
# A misspelled role would drop its class out of the boundary count
# without a word, so the roles are checked here, where a typo lands.
assert set(NAME_CLASSES.values()) == {"given", "family"}, NAME_CLASSES

INDEX_DIR = "wikidata_cjk_names"
#: Bumped whenever what the index holds changes (2 widened the character
#: class to supplementary-plane Han, 3 to Extension H and keyed each batch
#: by its whole membership); a cache built by another version is rebuilt
#: rather than trusted.
INDEX_VERSION = 3
#: Items per label query. Measured 2026-10-17 on family-name items not
#: queried before: 1,000 took 2.2-2.4s and 2,000 took 24s.
INDEX_BATCH = 1000
#: A batch that overruns is halved; one this small that still overruns
#: is an error, not a reason to keep halving.
INDEX_MIN_BATCH = 50
#: Items per bearer query; more are counted in several and summed.
ITEM_CHUNK = 500
ENDS_WITH_SOURCE = "Wikidata people, name ends with"

#: The iteration mark 々 and 〇, kana, the CJK ideograph blocks (Extension
#: A, the unified block, compatibility, and the supplementary planes from
#: Extension B through Extension H as of Unicode 15, where rare surname
#: characters live), hangul syllables, and halfwidth katakana. The Yijing
#: hexagrams between Extension A and the unified block are left out. One
#: such letter makes a label or a word CJK; the query and is_cjk share
#: the class, so widening it is an INDEX_VERSION bump.
_CJK_CHARS = ("\u3005\u3007\u3040-\u30ff\u3400-\u4dbf\u4e00-\u9fff"
              "\uac00-\ud7af\uf900-\ufaff\uff65-\uff9f"
              "\U00020000-\U000323af")
_CJK = re.compile(f"[{_CJK_CHARS}]")


def is_cjk(word: str) -> bool:
    return _CJK.search(word) is not None


@dataclass(frozen=True, slots=True)
class IndexEntry:
    qid: str
    role: Role
    label: str


@dataclass(slots=True)
class Split:
    """People whose family name ends in `family_tail` and whose given
    name is `given`, so that the two written together end in the word:
    阿部 + 長 ends in 部長. `people` is None until counted, and stays
    None, with `error` saying why, when the count failed."""

    family_tail: str
    given: str
    family_items: list[str]
    given_items: list[str]
    family_examples: list[str] = field(default_factory=list)
    people: int | None = None
    #: The Q-id of one bearer, for looking the pairing up.
    example: str = ""
    error: str = ""


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
    """The CJK rdfs:labels of the items, every language. Aliases and
    native-label statements are not read."""
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
        try:
            overran = exc.code in (502, 504) or (
                exc.code == 500 and b"TimeoutException" in exc.read())
        finally:
            exc.close()
        if overran:
            raise _Overrun(f"HTTP {exc.code}") from None
        raise
    except (ValueError, TimeoutError, http.client.IncompleteRead) as exc:
        # At its limit WDQS cuts a 200 off mid-stream, which surfaces as
        # JSON that stops (ValueError), a CSV line with no end, or a
        # short read.
        raise _Overrun(f"{type(exc).__name__}: {exc}") from exc


def _write(path: Path, data: object) -> None:
    tmp = path.with_suffix(".part")
    tmp.parent.mkdir(parents=True, exist_ok=True)
    tmp.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
    tmp.replace(path)


def _unusable(path: Path, why: str) -> ValueError:
    return ValueError(f"{path} is unusable ({why}); delete it, or run "
                      "again with --refresh-index")


def _read_json(path: Path) -> object:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise _unusable(path, f"{type(exc).__name__}: {exc}") from exc


def _is_qid(value: object) -> bool:
    return isinstance(value, str) and re.fullmatch(r"Q\d+", value) is not None


def _class_ids(cls: str, fetch: bool) -> list[str]:
    path = cache_dir() / INDEX_DIR / f"{cls}-ids.json"
    if path.exists():
        cached = _read_json(path)
        if not (isinstance(cached, list) and cached
                and all(map(_is_qid, cached))):
            raise _unusable(path, "not a non-empty list of Q-ids")
        return [str(q) for q in cached]
    if not fetch:
        raise _Missing(path.name)
    try:
        [count] = _index_sparql(count_query(cls))
        rows = _index_sparql(ids_query(cls), as_csv=True)
    except _Overrun as exc:
        raise ValueError(f"listing wd:{cls} items overran ({exc})") from exc
    if rows and "item" not in rows[0]:
        raise ValueError(f"listing wd:{cls} has columns {sorted(rows[0])}, "
                         "not item")
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
    if not ids:
        # A merged or mistyped class answers 0 to both queries; caching
        # that would make every later ends-with row a silent zero.
        raise ValueError(f"wd:{cls} lists no items; check NAME_CLASSES")
    _write(path, ids)
    print(f"  wd:{cls}: {len(ids):,} items", file=sys.stderr)
    return ids


def _batch_digest(qids: list[str]) -> str:
    """What a batch file is keyed by: its whole membership, since batches
    are named by position and, after a class is listed again, the same
    position can hold other items -- at either end or in between."""
    return hashlib.sha256(" ".join(qids).encode()).hexdigest()


def _cached_batch(path: Path, digest: str,
                  ids: list[str]) -> tuple[str, list[list[str]]] | None:
    """A batch file's date and rows, or None when it was built for other
    items."""
    data = _read_json(path)
    if not (isinstance(data, dict) and isinstance(data.get("fetched"), str)
            and isinstance(data.get("rows"), list)):
        raise _unusable(path, "not a batch: needs fetched, digest and rows")
    if data.get("digest") != digest:
        return None
    rows = data["rows"]
    batch = set(ids)
    for row in rows:
        if not (isinstance(row, list) and len(row) == 2
                and row[0] in batch and isinstance(row[1], str)):
            raise _unusable(path, f"row {row!r} is not an item of the batch")
    return data["fetched"], rows


def _fetch_batch(cls: str, ids: list[str], start: int, end: int, fetch: bool,
                 out: list[IndexEntry], dates: set[str]) -> bool:
    """Read the labels of ids[start:end] into `out`, querying them if they
    are not cached and halving the batch when it overruns. A finished
    batch is written at once and a halved one is marked, so a build that
    stops resumes where it stopped and never re-asks a halved batch.
    True when anything was queried."""
    base = cache_dir() / INDEX_DIR / f"{cls}-{start}-{end}"
    done, halved = base.with_suffix(".json"), base.with_suffix(".halved")
    batch = ids[start:end]
    middle = (start + end) // 2
    # The marker is read first: a whole batch's file from an earlier
    # listing must not shadow the halves this one was cached as. A marker
    # left by an earlier listing only splits the batch, which costs a
    # query and loses nothing, since each half is checked by itself.
    if halved.exists():
        first = _fetch_batch(cls, ids, start, middle, fetch, out, dates)
        second = _fetch_batch(cls, ids, middle, end, fetch, out, dates)
        return first or second
    digest = _batch_digest(batch)
    if done.exists():
        cached = _cached_batch(done, digest, batch)
        if cached is not None:
            dates.add(cached[0])
            out.extend(IndexEntry(q, NAME_CLASSES[cls], label)
                       for q, label in cached[1])
            return False
    if not fetch:
        raise _Missing(done.name)
    try:
        rows = [[_qid(row["item"]), row["label"]]
                for row in _index_sparql(labels_query(batch))]
    except _Overrun as exc:
        if end - start <= INDEX_MIN_BATCH:
            raise ValueError(f"wd:{cls} items {start}-{end} still "
                             f"overran ({exc})") from exc
        done.unlink(missing_ok=True)
        halved.parent.mkdir(parents=True, exist_ok=True)
        halved.touch()
        _fetch_batch(cls, ids, start, middle, fetch, out, dates)
        _fetch_batch(cls, ids, middle, end, fetch, out, dates)
        return True
    today = date.today().isoformat()
    _write(done, {"fetched": today, "digest": digest, "rows": rows})
    dates.add(today)
    out.extend(IndexEntry(q, NAME_CLASSES[cls], label) for q, label in rows)
    return True


def load_index(download: bool, refresh: bool = False) -> NameIndex | None:
    """The cached CJK name index; None when part of it is not cached and
    `download` is off. Building it is a one-time fetch of about 900
    queries (2026-10-17), paced by the endpoint's rate limit, and
    resumable. Raises ValueError naming any cache file it cannot use."""
    path = cache_dir() / INDEX_DIR
    version = path / "version.json"
    if refresh and path.exists():
        shutil.rmtree(path)
    if path.exists() and (not version.exists()
                          or _read_json(version) != INDEX_VERSION):
        if not download:
            return None
        print(f"the CJK name index in {path} was built by an older version "
              "of this tool; rebuilding it", file=sys.stderr)
        shutil.rmtree(path)
    if not path.exists():
        if not download:
            return None
        print(f"building the CJK name index in {path} -- a one-time fetch "
              "of about half an hour; an interrupted build resumes",
              file=sys.stderr)
        _write(version, INDEX_VERSION)
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


def _chunks(qids: list[str]) -> list[list[str]]:
    return [qids[i:i + ITEM_CHUNK] for i in range(0, len(qids), ITEM_CHUNK)]


def _count_items(qids: list[str], top: int) -> tuple[Usage, int]:
    chunks = _chunks(qids)
    totals: list[dict[str, str]] = []
    by_country: list[dict[str, str]] = []
    for chunk in chunks:
        totals += _bindings(_sparql(_totals_query(_item_match(chunk))))
        by_country += _bindings(_sparql(_countries_query(_item_match(chunk))))
    return read_wikidata(totals, by_country, top), len(chunks)


def _count_split(split: Split) -> None:
    """The distinct bearers of the pairing, the family items asked in
    chunks (a one-letter tail such as 部 or 田 matches hundreds) and the
    people gathered here, so a person is counted once across chunks."""
    given = " ".join(f"wd:{q}" for q in split.given_items)
    people: set[str] = set()
    for chunk in _chunks(split.family_items):
        family = " ".join(f"wd:{q}" for q in chunk)
        rows = _bindings(_sparql(f"""
SELECT DISTINCT ?p WHERE {{
  VALUES ?f {{ {family} }}
  VALUES ?g {{ {given} }}
  ?p wdt:P734 ?f ; wdt:P735 ?g .
}}"""))
        people |= {_qid(row["p"]) for row in rows}
    split.people = len(people)
    split.example = min(people, key=lambda q: int(q[1:])) if people else ""


_QUERY_ERRORS = (OSError, ValueError, KeyError, http.client.HTTPException)


def _failure(exc: BaseException) -> str:
    """The note for a query that failed. An HTTPError holds its response
    open, and since 3.14 one collected unclosed warns, so it is closed
    here, where the report lets go of it."""
    if isinstance(exc, urllib.error.HTTPError):
        exc.close()
    return f"query failed: {type(exc).__name__}: {exc}"


def ends_with_usage(word: str, index: NameIndex, top: int) -> Usage:
    """Bearers of the indexed name items whose label ends in the word,
    and of the family/given pairs that end in it together. A failed
    pairing count fails only that pairing (Split.error)."""
    matches = index.ending_in(word)
    qids = sorted({e.qid for e in matches})
    about = (f"index of {len(index.entries):,} entries fetched "
             f"{index.fetched}")
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
            usage.note = _join(f"{items} in it: {shown}", twice, about)
        else:
            usage = Usage("", given=0, family=0, lower_bound=True,
                          note=_join(f"no indexed name item ends in {word}",
                                     about))
    except _QUERY_ERRORS as exc:
        return Usage(ENDS_WITH_SOURCE, status="failed", lower_bound=True,
                     note=_failure(exc))
    usage.source = ENDS_WITH_SOURCE
    usage.splits = index.boundaries(word)
    for split in usage.splits:
        try:
            _count_split(split)
        except _QUERY_ERRORS as exc:
            split.error = _failure(exc)
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
        if isinstance(exc, urllib.error.HTTPError):
            exc.close()
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
    lines.append(f"  {'source':<{width}}  {'given':>9}  {'family':>9}  "
                 f"{'credential':>10}")
    for u in usages:
        given = (f"band {u.given_bands[0][1]:X}" if u.given_bands
                 else _count(u.given, u))
        lines.append(f"  {u.source:<{width}}  {given:>9}  "
                     f"{_count(u.family, u):>9}  {_count(u.credential, u):>10}")
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
        if u.given_bands:
            lines.append(f"  {'':<{width}}    given band by country: "
                         + ", ".join(f"{c} {b:X}" for c, b in u.given_bands))
        for split in u.splits:
            example = "; ".join(
                split.family_examples
                + ([f"bearer {split.example}"] if split.example else []))
            detail = split.error or (f"e.g. {example}" if example else "")
            lines.append(
                f"  {'':<{width}}    family ending {split.family_tail} + "
                f"given {split.given}: {_count(split.people, u)} people"
                + (f" ({detail})" if detail else ""))
    return "\n".join(lines)


#: Fields a parse may put a credential in, in the order a reading is
#: named by; the first holding all of it wins.
_FIELDS = ("suffix", "title", "given", "middle", "family", "nickname", "maiden")


def _lands(name: str, text: str) -> str:
    """The field `text` lands in when `name` is parsed, or "split" when
    no one field holds all of it."""
    from nameparser import parse
    parsed = parse(name)
    want = text.split()
    for role in _FIELDS:
        words = getattr(parsed, role).replace(",", " ").split()
        if any(words[i:i + len(want)] == want for i in range(len(words))):
            return role
    return "split"


def _vocabulary(key: str) -> str:
    """How nameparser's default vocabulary lists a key: its suffix kind
    (an ambiguous acronym is marked so), then any title or particle
    reading, matched as the parser matches -- an acronym with every
    period gone, a word with its edge periods gone (the key has none)."""
    from nameparser import Lexicon
    lexicon = Lexicon.default()
    low = key.lower()
    kinds = []
    if low in lexicon.suffix_acronyms_ambiguous:
        kinds.append("ambiguous acronym")
    elif low in lexicon.suffix_acronyms:
        kinds.append("acronym")
    if low in lexicon.suffix_words:
        kinds.append("suffix word")
    if low in lexicon.titles:
        kinds.append("title")
    if low in lexicon.particles:
        kinds.append("particle")
    return ", ".join(kinds) or "-"


def _listed_suffix(key: str) -> bool:
    from nameparser import Lexicon
    lexicon, low = Lexicon.default(), key.lower()
    return (low in lexicon.suffix_acronyms_ambiguous
            or low in lexicon.suffix_acronyms or low in lexicon.suffix_words)


def _cell(usage: Usage, count: int | None, error: str) -> str:
    """A name source's --rank cell: its count, or why it has none."""
    if error:
        return "failed"
    return _count(count, usage) if usage.status == "ok" else usage.status


@dataclass(slots=True)
class RankRow:
    rank: int
    credential: str
    providers: int
    share: float
    spellings: list[tuple[str, int]]
    vocabulary: str
    #: Where the commonest spelling lands in "John Smith, X" and in
    #: "John Smith X".
    after_comma: str
    bare: str
    census: str
    ssa: str


def rank_rows(tally: CredentialTally, top: int, unlisted: bool,
              census: dict[str, dict[str, str]] | None, census_error: str,
              ssa: dict[str, Counter[str]] | None,
              ssa_error: str) -> list[RankRow]:
    """The `top` commonest credentials -- only those the vocabulary does
    not list as a suffix, with `unlisted` -- each with the name counts
    and readings. The rank is the credential's place among all of them,
    so a filtered list shows where each one stands."""
    rows = []
    for rank, (key, n, spellings) in enumerate(tally.ranked(), 1):
        if unlisted and _listed_suffix(key):
            continue
        spelling = spellings[0][0]
        census_row, ssa_row = census_usage(key, census), ssa_usage(key, ssa)
        rows.append(RankRow(
            rank, key, n, n / tally.credentialed, spellings, _vocabulary(key),
            _lands(f"John Smith, {spelling}", spelling),
            _lands(f"John Smith {spelling}", spelling),
            _cell(census_row, census_row.family, census_error),
            _cell(ssa_row, ssa_row.given, ssa_error)))
        if len(rows) == top:
            break
    return rows


def render_rank(rows: list[RankRow], tally: CredentialTally) -> str:
    header = (f"{'rank':>6}  {'credential':<12} {'providers':>10} {'share':>7}  "
              f"{'nameparser':<27} {'Smith, X':<9} {'Smith X':<8} "
              f"{'census':>7} {'ssa':>7}  spellings")
    lines = [f"{tally.credentialed:,} of {tally.people:,} individual providers "
             "write a credential; Smith, X and Smith X are where the "
             "commonest spelling lands in 'John Smith, X' and 'John Smith X'",
             header]
    for r in rows:
        lines.append(
            f"{r.rank:>6}  {r.credential:<12} {r.providers:>10,} {_share(r.share):>7}  "
            f"{r.vocabulary:<27} {r.after_comma:<9} {r.bare:<8} "
            f"{r.census:>7} {r.ssa:>7}  "
            + ", ".join(f"{s} {c:,}" for s, c in r.spellings[:3]))
    return "\n".join(lines)


def _ssa_notice(ssa: dict[str, Counter[str]] | None, ssa_error: str) -> None:
    if ssa is None and not ssa_error:
        sys.stdout.flush()  # keep the notice after the report, not before it
        print("\n" + ssa_missing_message(), file=sys.stderr)


def _positive(text: str) -> int:
    # 0 would empty nam_dict's band list, and its given cell would then
    # show the "-" a name that is not listed shows.
    n = int(text)
    if n < 1:
        raise argparse.ArgumentTypeError(f"must be 1 or more, not {n}")
    return n


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Count how often words are borne as given and family "
                    "names, and written as credentials.",
        epilog="Sources: US Census 2010 surnames (public domain); US SSA "
               "given names (CC0); Wikidata (CC0); " + NAMDICT_CREDIT
               + "; NPPES (CMS, public) via NBER. Downloads are cached in "
               "$NAMEPARSER_TOOLS_CACHE or ~/.cache/nameparser-tools, never "
               "in the repository.")
    parser.add_argument("words", nargs="*")
    parser.add_argument("--no-wikidata", action="store_true",
                        help="offline: cached sources only, nothing downloaded")
    parser.add_argument("--fetch-nppes", action="store_true",
                        help=f"download the NPPES credentials ({NPPES_SIZE}) "
                             "if they are not cached")
    parser.add_argument("--rank", type=_positive, metavar="N",
                        help="list the N commonest credentials instead of "
                             "reporting words (downloads NPPES unless "
                             "offline, --no-wikidata)")
    parser.add_argument("--unlisted", action="store_true",
                        help="with --rank: only credentials nameparser's "
                             "vocabulary does not list as a suffix")
    parser.add_argument("--countries", type=_positive, default=5, metavar="N",
                        help="countries to list per role (citizenship, "
                             "or nam_dict's bands)")
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--refresh-index", action="store_true",
                        help="fetch the CJK name index again")
    args = parser.parse_args(argv)
    if args.rank is None and not args.words:
        parser.error("give words to report, or --rank N")
    if args.rank is not None and args.words:
        parser.error("--rank lists credentials; it takes no words")
    if args.unlisted and args.rank is None:
        parser.error("--unlisted goes with --rank")

    census, census_error = _attempt(
        lambda: load_census(download=not args.no_wikidata))
    ssa, ssa_error = _attempt(load_ssa)
    nppes, nppes_error = _attempt(lambda: load_nppes(
        download=not args.no_wikidata
        and (args.fetch_nppes or args.rank is not None)))
    if args.rank is not None:
        return _main_rank(args, nppes, nppes_error, census, census_error,
                          ssa, ssa_error)
    namdict, namdict_error = _attempt(
        lambda: load_namdict(download=not args.no_wikidata))
    # Wikidata labels are NFC: a decomposed word (hangul as conjoining
    # jamo, an accent as a combining mark) would match no label at all.
    words = [unicodedata.normalize("NFC", word) for word in args.words]
    index: NameIndex | None = None
    index_error = ""
    if not args.no_wikidata and (args.refresh_index
                                 or any(map(is_cjk, words))):
        index, index_error = _attempt(
            lambda: load_index(download=True, refresh=args.refresh_index))

    locals_ = load_locals()
    report = {}
    for word in words:
        census_row, ssa_row = census_usage(word, census), ssa_usage(word, ssa)
        namdict_row = namdict_usage(word, namdict, args.countries)
        nppes_row = credential_usage(word, nppes)
        for row, error in ((census_row, census_error), (ssa_row, ssa_error),
                           (namdict_row, namdict_error),
                           (nppes_row, nppes_error)):
            if error:
                row.status, row.note = "failed", error
        usages = [census_row, ssa_row, namdict_row, nppes_row,
                  *local_rows(word, locals_)]
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
    _ssa_notice(ssa, ssa_error)
    failed = any(u.status == "failed" or any(s.error for s in u.splits)
                 for us in report.values() for u in us)
    if args.refresh_index and index_error:
        # A Latin word has no ends-with row to carry this, and the refresh
        # has already deleted the old index.
        print(f"CJK name index: {index_error}", file=sys.stderr)
        failed = True
    return 2 if failed else 0


def _main_rank(args: argparse.Namespace, nppes: CredentialTally | None,
               nppes_error: str, census: dict[str, dict[str, str]] | None,
               census_error: str, ssa: dict[str, Counter[str]] | None,
               ssa_error: str) -> int:
    """--rank: the list needs the tally, so a tally that did not load
    fails the run; a name source that did not load leaves its column
    saying so and fails the run too, as a failed row does."""
    if nppes is None:
        print(f"{NPPES_SOURCE}: " + (nppes_error or (
            "not cached, and --no-wikidata does not download")),
            file=sys.stderr)
        return 2
    rows = rank_rows(nppes, args.rank, args.unlisted, census, census_error,
                     ssa, ssa_error)
    if args.json:
        print(json.dumps({"people": nppes.people,
                          "credentialed": nppes.credentialed,
                          "rows": [asdict(r) for r in rows]}, indent=2))
    else:
        print(render_rank(rows, nppes))
    for name, error in (("US Census 2010 surnames", census_error),
                        ("US SSA given names", ssa_error)):
        if error:
            print(f"{name}: {error}", file=sys.stderr)
    _ssa_notice(ssa, ssa_error)
    return 2 if census_error or ssa_error else 0


if __name__ == "__main__":
    sys.exit(main())
