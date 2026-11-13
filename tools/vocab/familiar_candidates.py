"""Draw candidate familiar forms from CC0 data, for a review by hand.

WHY THIS IS IN THE TREE. The shipped familiar forms are English alone
since nam_dict's pairs left (decisions/name-matching, 2026-11-12
ENGLISH ONLY UNTIL REBUILT): a compiler's list copied whole keeps its
licence (decisions/shipped-data-licences, 2026-11-12 #1370 FACTS WE
MEASURE), so other languages' pairs are rebuilt from pairs the project
FINDS in data it may use and then reviews by hand, as the nicknames
list was reviewed. This tool finds them; it never reads nam_dict or any
other list of familiar forms, so what it proposes is a measurement of
usage, not a selection copied from a compiler.

THE EVIDENCE: ONE PERSON WRITING THEIR NAME BOTH WAYS. ORCID's public
data file (CC0 1.0, read from the orcid-researchers local corpus's
extract, tools/differential/local_orcid.py) holds each holder's given
name box, family name box, and the published ("credit") and other names
the holder typed beside them. Where the given box is one word, Y, and a
credit or other name is exactly two words, X and the family box's last
word, with X a different word from Y, the holder writes their given
name both as Y and as X: `given = Katarzyna`, `credit = Kasia Nowak`.
Each distinct holder counts once for a pair, whichever of the names they
wrote it in, and the pair is unordered: X is not always the shorter.

What is dropped before counting, each because it is not evidence of a
familiar form: a title in either name (the default lexicon's titles,
read as `_pipeline` reads them, by the folded word); a given box of
more than one word, whose credit name may use the second given name
(`Maria Teresa` / `Teresa`) rather than a familiar form; a word of one
letter or with a digit; a word of two or three capitals (`MD`, `JJ`,
initials written without stops); two words the name match already
reads as one, equal under its fold (`_match._fold`: `José` / `Jose`);
and two words in different scripts (`Ігор` / `Игорь`, a
transliteration).

What stays for the review to refuse, as the nicknames list's review
refused it (tools/vocab/nicknames_excluded.tsv's categories): two
spellings of one name (`Oxana` / `Oksana`, flagged SPELLING_SHAPED here
by a similarity a reviewer may overrule), another language's form
(`Jorge` / `George`), and another name used beside the given one
(`Scott` / `Robert`). Measured on the 2025 file (2026-11-12): of the
pairs at three or more holders in neither the shipped list nor its
refusals, about four fifths of a hand-read sample were familiar forms.

THE SECOND ATTESTATION. GND's authority records (CC0, read through the
lobid API, `--gnd`) name a person's preferred forename and the
forenames they are also known by; a pair GND records for one person or
more either way round is counted in a column of its own. GND alone is
no source: most of its variant forenames are other languages' forms and
Latin ones (`Henri` / `Heinrich`, `Guilelmus` / `Wilhelm`).

THE LANGUAGE. A pair goes in the vocabulary file of each language
written in the countries its holders work or live in
(config_diff.LANGUAGES_OF, a record's country as local_orcid reads it),
where that language's holders are LANGUAGE_MIN_SHARE of the pair's
holders with a country and at least LANGUAGE_MIN_HOLDERS; else in
mul.toml. The review may move a pair.

    uv run python tools/vocab/familiar_candidates.py --min 3        # mine, write the cache's TSV
    uv run python tools/vocab/familiar_candidates.py --min 3 --gnd  # and ask GND about each
    uv run python tools/vocab/familiar_candidates.py --sample 200 --seed 1   # the pilot draw

Reads the ORCID extract from the cache (`local_corpora.py fetch
orcid-researchers` writes it); writes `familiar-candidates.tsv` into
$NAMEPARSER_TOOLS_CACHE (or ~/.cache/nameparser-tools), with GND's
answers cached beside it in `familiar-gnd.json`. Nothing it writes holds
a family name: the file is given names and counts alone, as ORCID's use
policy asks the privacy of its holders be kept.
"""
from __future__ import annotations

import argparse
import collections
import csv
import difflib
import gzip
import io
import json
import random
import re
import sys
import unicodedata
import urllib.parse
import urllib.request
from collections.abc import Callable, Iterable, Iterator, Mapping
from dataclasses import dataclass, field
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parents[1]))
sys.path.insert(0, str(Path(__file__).parents[1] / "differential"))
sys.path.insert(0, str(Path(__file__).parent))
import build  # noqa: E402  (a sibling script, not a package)
import familiar  # noqa: E402
import name_usage  # noqa: E402

from nameparser._match import _fold as _match_fold  # noqa: E402

#: A language's holders must be this share of a pair's holders with a
#: country, and at least LANGUAGE_MIN_HOLDERS, for the pair to go in
#: that language's file.
LANGUAGE_MIN_SHARE = 0.25
LANGUAGE_MIN_HOLDERS = 2
#: The file of a pair no language takes.
SHARED = "mul"
#: Folded similarity at or above which, with lengths within two letters,
#: a pair is flagged as shaped like two spellings of one name.
SPELLING_RATIO = 0.75

CANDIDATES_FILE = "familiar-candidates.tsv"
GND_FILE = "familiar-gnd.json"
GND_URL = "https://lobid.org/gnd/search"

HEADER = ["a", "b", "holders", "spelling_shaped", "languages",
          "countries", "gnd"]

_WORD = re.compile(r"^[^\W\d_]+$")


def fold(word: str) -> str:
    """The word's letters lower-cased with every combining mark dropped,
    as the name match folds Latin, Greek and Cyrillic: the test for two
    words being one word written with or without accents."""
    return "".join(c for c in unicodedata.normalize("NFD", word.casefold())
                   if unicodedata.category(c) != "Mn")


def script(word: str) -> str:
    """The script of the word's first letter, by its Unicode name's first
    word (LATIN, CYRILLIC, GREEK, ...)."""
    return unicodedata.name(word[0], "?").split(" ")[0]


def is_name_word(word: str) -> bool:
    """A word that can stand for a given name here: letters alone, two
    or more, and not two or three capitals (initials written without
    their stops)."""
    if not _WORD.match(word) or len(word) < 2:
        return False
    return not (word.isupper() and len(word) <= 3)


def spelling_shaped(a: str, b: str) -> bool:
    """Two words shaped like two spellings of one name: folded, alike by
    SPELLING_RATIO and of lengths within two letters (`oxana` /
    `oksana`). A flag for the review, which may overrule it."""
    fa, fb = fold(a), fold(b)
    return (abs(len(fa) - len(fb)) <= 2
            and difflib.SequenceMatcher(None, fa, fb).ratio() >= SPELLING_RATIO)


@dataclass
class Evidence:
    """One unordered pair's holders: how many, and in which countries
    (the empty string for a holder with none)."""

    holders: int = 0
    countries: collections.Counter[str] = field(
        default_factory=collections.Counter)


def _is_title(word: str, titles: frozenset[str]) -> bool:
    """The word, its edge full stops dropped and folded, is a title."""
    return fold(build._normalize(word)) in titles


def pairs_of(record: Mapping[str, object],
             titles: frozenset[str]) -> set[tuple[str, str]]:
    """The unordered pairs one record evidences, each as (x, y) sorted,
    every word normalized as the vocabulary writes it (build._normalize)."""
    given, family = record.get("given"), record.get("family")
    if not isinstance(given, str) or not isinstance(family, str):
        return set()
    words = [w for w in given.split() if not _is_title(w, titles)]
    surnames = family.split()
    if len(words) != 1 or not surnames or not is_name_word(words[0]):
        return set()
    y, last = words[0], fold(surnames[-1])
    names = [record["credit"]] if isinstance(record.get("credit"), str) else []
    other = record.get("other")
    if isinstance(other, list):
        names += [n for n in other if isinstance(n, str)]
    out = set()
    for name in names:
        written = [w for w in name.replace(",", " ").split()
                   if not _is_title(w, titles)]
        if len(written) != 2 or fold(written[1]) != last:
            continue
        x = written[0]
        if (not is_name_word(x) or _match_fold(x) == _match_fold(y)
                or script(x) != script(y)):
            continue
        a, b = sorted((build._normalize(x), build._normalize(y)))
        out.add((a, b))
    return out


def mine(records: Iterable[Mapping[str, object]],
         titles: frozenset[str]) -> dict[tuple[str, str], Evidence]:
    """Every pair the records evidence, with its holders."""
    out: dict[tuple[str, str], Evidence] = {}
    for record in records:
        for pair in pairs_of(record, titles):
            evidence = out.setdefault(pair, Evidence())
            evidence.holders += 1
            country = record.get("country")
            evidence.countries[country if isinstance(country, str) else ""] += 1
    return out


def languages(countries: Mapping[str, int],
              languages_of: Mapping[str, tuple[str, ...]]) -> tuple[str, ...]:
    """The tags of the files a pair goes in: each language whose
    countries' holders are LANGUAGE_MIN_SHARE of the holders with a
    country and at least LANGUAGE_MIN_HOLDERS; SHARED where none is."""
    placed = sum(n for c, n in countries.items() if c)
    by_tag: collections.Counter[str] = collections.Counter()
    for country, n in countries.items():
        for tag in languages_of.get(country, ()):
            by_tag[tag] += n
    out = tuple(sorted(t for t, n in by_tag.items()
                       if n >= LANGUAGE_MIN_HOLDERS
                       and n >= LANGUAGE_MIN_SHARE * placed))
    return out or (SHARED,)


def known_pairs() -> set[frozenset[str]]:
    """The pairs the nicknames list already gives or its review refused,
    either way round: nothing to review again."""
    rows = familiar.load_nicknames()
    refused = familiar.load_exclusions()
    return {frozenset((build._normalize(f), build._normalize(n)))
            for f, n in [*rows, *refused]}


def orcid_records(path: Path) -> Iterator[dict[str, object]]:
    """The extract's records, its header line skipped."""
    with gzip.open(path, "rt", encoding="utf-8", newline="\n") as lines:
        next(lines)
        for line in lines:
            yield json.loads(line)


def gnd_count(preferred: str, variant: str) -> int:
    """How many GND persons hold `preferred` as a forename of their
    preferred name and `variant` as one of a variant name."""
    query = (f'preferredNameEntityForThePerson.forename:"{preferred}" AND '
             f'variantNameEntityForThePerson.forename:"{variant}"')
    url = GND_URL + "?" + urllib.parse.urlencode(
        {"q": query, "filter": "type:DifferentiatedPerson",
         "format": "json", "size": 0})
    request = urllib.request.Request(
        url, headers={"User-Agent": name_usage.USER_AGENT})
    with urllib.request.urlopen(request, timeout=60) as response:
        return int(json.load(response).get("totalItems", 0))


def gnd_attest(pairs: Iterable[tuple[str, str]], cache: Path,
               ask: Callable[[str, str], int] = gnd_count,
               ) -> dict[tuple[str, str], int]:
    """GND's persons for each pair, either way round, asked once and
    kept in `cache` (a JSON object keyed "a|b")."""
    kept: dict[str, int] = (json.loads(cache.read_text(encoding="utf-8"))
                            if cache.exists() else {})
    out = {}
    for a, b in pairs:
        key = f"{a}|{b}"
        if key not in kept:
            kept[key] = ask(a.title(), b.title()) + ask(b.title(), a.title())
            cache.write_text(json.dumps(kept, ensure_ascii=False),
                             encoding="utf-8")
        out[(a, b)] = kept[key]
    return out


def rows(found: Mapping[tuple[str, str], Evidence], minimum: int,
         known: set[frozenset[str]],
         languages_of: Mapping[str, tuple[str, ...]],
         gnd: Mapping[tuple[str, str], int] | None = None) -> list[list[str]]:
    """The candidate rows: pairs at `minimum` holders or more, less the
    known ones, most holders first, then by text."""
    out = []
    for (a, b), ev in sorted(found.items(),
                             key=lambda kv: (-kv[1].holders, kv[0])):
        if ev.holders < minimum or frozenset((a, b)) in known:
            continue
        top = ", ".join(f"{c or '-'} {n}"
                        for c, n in ev.countries.most_common(5))
        out.append([a, b, str(ev.holders),
                    "yes" if spelling_shaped(a, b) else "",
                    " ".join(languages(ev.countries, languages_of)), top,
                    "" if gnd is None else str(gnd.get((a, b), 0))])
    return out


def write_tsv(rows_: list[list[str]]) -> str:
    out = io.StringIO()
    writer = csv.writer(out, delimiter="\t", lineterminator="\n")
    writer.writerow(HEADER)
    writer.writerows(rows_)
    return out.getvalue()


def read_tsv(text: str) -> list[dict[str, str]]:
    reader = csv.DictReader(io.StringIO(text), delimiter="\t")
    if reader.fieldnames != HEADER:
        raise ValueError(f"{CANDIDATES_FILE}: the header is "
                         f"{reader.fieldnames}, not {HEADER}")
    return list(reader)


def sample(candidates: list[dict[str, str]], size: int,
           seed: int) -> list[dict[str, str]]:
    """A seeded draw of `size` candidates, stratified by holders: an
    equal share from each band of BANDS, the rest from the largest."""
    bands = [[c for c in candidates if lo <= int(c["holders"]) <= hi]
             for lo, hi in BANDS]
    rng = random.Random(seed)
    per = size // len(bands)
    drawn = []
    for band in bands:
        drawn += rng.sample(band, min(per, len(band)))
    return drawn


#: The holder bands a pilot draw is stratified by.
BANDS = ((3, 3), (4, 5), (6, 10), (11, 10**9))


def _languages_of() -> Mapping[str, tuple[str, ...]]:
    import config_diff
    return config_diff.LANGUAGES_OF


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--min", type=int, default=3,
                        help="the fewest holders a pair needs (default 3)")
    parser.add_argument("--gnd", action="store_true",
                        help="ask GND (lobid) about each pair, cached")
    parser.add_argument("--sample", type=int, metavar="N",
                        help="print a stratified draw of N candidates from "
                             "the written TSV, instead of mining")
    parser.add_argument("--seed", type=int, default=1)
    args = parser.parse_args(argv)
    cache = name_usage.cache_dir()
    path = cache / CANDIDATES_FILE
    if args.sample:
        drawn = sample(read_tsv(path.read_text(encoding="utf-8")),
                       args.sample, args.seed)
        print(write_tsv([[r[h] for h in HEADER] for r in drawn]), end="")
        return 0
    import local_orcid
    extract = local_orcid.extract_path()
    if not extract.exists():
        raise SystemExit(f"{extract} is not cached; run `uv run python "
                         f"tools/differential/local_corpora.py fetch "
                         f"orcid-researchers`")
    from nameparser import Lexicon
    titles = frozenset(fold(t) for t in Lexicon.default()._sets.titles)
    found = mine(orcid_records(extract), titles)
    known = known_pairs()
    kept = [p for p, ev in found.items()
            if ev.holders >= args.min and frozenset(p) not in known]
    gnd = gnd_attest(sorted(kept), cache / GND_FILE) if args.gnd else None
    out = rows(found, args.min, known, _languages_of(), gnd)
    path.write_text(write_tsv(out), encoding="utf-8")
    print(f"{len(found):,} pairs mined, {len(out):,} at {args.min}+ holders "
          f"in neither the list nor its refusals; wrote {path}",
          file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
