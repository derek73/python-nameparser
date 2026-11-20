"""Draw candidate familiar forms from Wikidata's people, per language, for a review.

WHY THIS IS IN THE TREE. ORCID's holders (tools/vocab/familiar_candidates.py)
evidence English and Western European familiar forms well and Central
and Eastern European ones thinly (#1387). Wikidata (CC0) states, for
many people, the name they go by beside a fuller one; this tool reads
three such relations, one country at a time, and writes every pair it
finds, by the language the names are written in, for the same two-reader
review. It reads no list of familiar forms: what it proposes is a
measurement of how people are named, not a selection copied from a
compiler (decisions/shipped-data-licences, 2026-11-12 #1370 FACTS WE
MEASURE).

THE THREE RELATIONS (decisions/name-matching, 2026-11-20 #1387). For
each person of a country in COUNTRIES, a human (Q5) with a citizenship
(P27) of that country, in each language the country writes (its
LANGUAGES, the label's language tag; a language-independent `mul`
label read as the country's language where it writes one alone):

1. `birth`: the birth name (P1477) against the person's label in the
   same language. Where the label holds exactly one word the birth name
   lacks (x), and the birth name exactly one the label lacks, or one of
   several starting with x's letter (y), the pair is (x, y), kept only
   where x or y is one of the person's given names (P735): without that
   test a changed surname (a Magyarized or a married name) pairs with
   the old one, 3% familiar forms in a Hungarian trial.
2. `nickname`: a one-word stated nickname (P1449; the person's family
   name beside it is set aside) against the person's one given name,
   or the one of several starting with its letter, kept where the two
   share the first letter or the nickname's first two letters stand in
   the given name (`Józsi` / `József`, `Pista` / `István` left out).
3. `label`: the label against the given name, where no word of the
   label is a given name of the person's: the label's words less its
   family names (P734), and less a patronymic, must be one word, and a
   family name must have stood in it (a stage name pairs with nothing).

Each word is a name word (familiar_candidates.is_name_word: no initial,
no digit), no title of the default lexicon's, and the two words differ
under the name match's fold and are written in one script. A pair is
counted once per person whichever relations evidence it, and goes in the
file of the language it was found in.

What is left to the review: two spellings of one name (`Sergei` /
`Sergey`, shape `spelling`), another language's form, another name the
person used. A pair already in tools/vocab/familiar_reviewed.tsv is not
proposed again.

    uv run python tools/vocab/familiar_wikidata.py fetch           # every country, cached
    uv run python tools/vocab/familiar_wikidata.py fetch --country hu
    uv run python tools/vocab/familiar_wikidata.py pairs --min 1   # write the candidates

`fetch` keeps each query's answer in $NAMEPARSER_TOOLS_CACHE (or
~/.cache/nameparser-tools) under FETCH_DIR and asks the query service
again only for an answer it does not hold; `pairs` reads them alone and
writes CANDIDATES_FILE beside them. The requests name no person or
project (USER_AGENT). The candidates are given names and counts alone.
"""
from __future__ import annotations

import argparse
import collections
import csv
import hashlib
import io
import json
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from collections.abc import Iterable, Iterator, Mapping
from dataclasses import dataclass, field
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parents[1]))
sys.path.insert(0, str(Path(__file__).parent))
import build  # noqa: E402  (a sibling script, not a package)
import familiar_candidates as fc  # noqa: E402
import name_usage  # noqa: E402

from nameparser._match import _fold as _match_fold  # noqa: E402
from nameparser._pipeline._vocab import has_patronymic_ending  # noqa: E402

ENDPOINT = "https://query.wikidata.org/sparql"
#: A generic client name: the requests carry no person's or project's
#: details.
USER_AGENT = "familiar-forms-research/0.1 (python-urllib)"
RETRIES = 5
#: Items whose labels one query asks for.
LABEL_BATCH = 400

FETCH_DIR = "familiar-wikidata-people"
CANDIDATES_FILE = "familiar-wikidata-candidates.tsv"
SOURCE = "wikidata"

#: Each country read: its citizenship item (P27) -> (a short code for
#: the cache's file names, the vocabulary tags of the languages it
#: writes). A label's language tag is read through LABEL_TAGS.
COUNTRIES: Mapping[str, tuple[str, tuple[str, ...]]] = {
    "Q28": ("hu", ("hu",)),
    "Q36": ("pl", ("pl",)),
    "Q218": ("ro", ("ro",)),
    "Q217": ("md", ("ro",)),
    "Q213": ("cz", ("cs",)),
    "Q214": ("sk", ("sk",)),
    "Q33946": ("cs", ("cs", "sk")),  # Czechoslovakia
    "Q219": ("bg", ("bg",)),
    "Q403": ("rs", ("sr",)),
    "Q236": ("me", ("sr",)),
    "Q224": ("hr", ("hr",)),
    "Q215": ("si", ("sl",)),
    "Q225": ("ba", ("bs", "hr", "sr")),
    "Q221": ("mk", ("mk",)),
    "Q222": ("al", ("sq",)),
    "Q1246": ("xk", ("sq", "sr")),
    "Q83286": ("yu", ("sr", "hr", "sl", "mk", "bs")),  # SFR Yugoslavia
    "Q159": ("ru", ("ru",)),
    "Q15180": ("su", ("ru", "uk", "be")),  # the Soviet Union
    "Q212": ("ua", ("uk",)),
    "Q184": ("by", ("be",)),
}
#: Wikidata's label languages read as another vocabulary tag.
LABEL_TAGS = {"sr-el": "sr", "sr-ec": "sr", "be-tarask": "be"}

#: The patronymic endings rules/O1 reads, and the Ukrainian feminine
#: ones it does not (`-івна`, `-ївна`), set aside from a Cyrillic
#: label: a label writes the father's name between the given and the
#: family name.
_UK_PATRONYMIC = re.compile(r"(івна|ївна)$", re.I)
_EDGE = "\"'“”„«»()[],.;:!?"


def wikidata_tag(lang: str) -> str:
    return LABEL_TAGS.get(lang, lang)


# -- fetching ---------------------------------------------------------------

#: Each query's name -> its SPARQL, `{country}` the citizenship item and
#: `{langs}` the label languages asked for. Each is answered from the
#: index alone, a country's in seconds; joining labels to people in one
#: query takes a minute and times out (measured 2026-11-20).
QUERIES = {
    "given": "SELECT ?h ?v WHERE {{ ?h wdt:P27 wd:{country}; wdt:P31 wd:Q5; "
             "wdt:P735 ?v }}",
    "family": "SELECT ?h ?v WHERE {{ ?h wdt:P27 wd:{country}; wdt:P31 wd:Q5; "
              "wdt:P734 ?v . FILTER EXISTS {{ ?h wdt:P735 [] }} }}",
    "label": "SELECT ?h ?v WHERE {{ ?h wdt:P27 wd:{country}; wdt:P31 wd:Q5 . "
             "FILTER EXISTS {{ ?h wdt:P735 [] }} "
             "?h rdfs:label ?v FILTER(lang(?v) IN ({langs})) }}",
    "birth": "SELECT ?h ?v WHERE {{ ?h wdt:P27 wd:{country}; wdt:P31 wd:Q5; "
             "wdt:P1477 ?v }}",
    "nickname": "SELECT ?h ?v WHERE {{ ?h wdt:P27 wd:{country}; "
                "wdt:P31 wd:Q5; wdt:P1449 ?v }}",
}
ITEM_LABELS = ("SELECT ?h ?v WHERE {{ VALUES ?h {{ {items} }} "
               "?h rdfs:label ?v FILTER(lang(?v) IN ({langs})) }}")


def label_langs(tags: Iterable[str]) -> list[str]:
    """The label languages asked for a country writing `tags`: each tag,
    the Wikidata codes read as one (LABEL_TAGS) and `mul`."""
    tags = set(tags)
    return sorted(tags | {k for k, v in LABEL_TAGS.items() if v in tags}
                  | {"mul"})


class FetchError(RuntimeError):
    """An answer that is not a whole TSV result: a timeout's stack trace
    after some rows, or an error page."""


def _unescape(text: str) -> str:
    return re.sub(r"\\(.)", lambda m: {"t": "\t", "n": "\n", "r": "\r"}.get(
        m.group(1), m.group(1)), text)


_ENTITY = re.compile(r"^<http://www\.wikidata\.org/entity/(Q\d+)>$")
_UNKNOWN = "<http://www.wikidata.org/.well-known/genid/"
_LITERAL = re.compile(r'^"((?:[^"\\]|\\.)*)"(?:@([A-Za-z0-9-]+))?$')


def read_answer(text: str) -> list[tuple[str, str, str]]:
    """A `?h ?v` TSV answer's rows, each (QID, value, language): an
    item's QID with an empty language, or a literal's text and tag.
    A statement of unknown value (a blank node) is left out. Raises
    FetchError on any line of another shape, so an answer cut by a
    timeout is never kept."""
    lines = text.split("\n")
    if lines[-1] == "":
        lines.pop()
    if not lines or lines[0] != "?h\t?v":
        raise FetchError(f"not a ?h ?v answer: {text[:120]!r}")
    out = []
    for number, line in enumerate(lines[1:], 2):
        cells = line.split("\t")
        h = _ENTITY.match(cells[0]) if len(cells) == 2 else None
        if h is None:
            raise FetchError(f"line {number} is not a row: {line[:120]!r}")
        v = cells[1]
        if v.startswith(_UNKNOWN):
            continue  # a statement of "unknown value"
        item, literal = _ENTITY.match(v), _LITERAL.match(v)
        if item:
            out.append((h.group(1), item.group(1), ""))
        elif literal:
            out.append((h.group(1), _unescape(literal.group(1)),
                        literal.group(2) or ""))
        else:
            raise FetchError(f"line {number}'s value is neither an item "
                             f"nor a literal: {v[:120]!r}")
    return out


def _sleep(seconds: float) -> None:
    time.sleep(seconds)


def ask(query: str) -> str:
    """The query service's TSV answer, retried after a rate limit or a
    timeout, and checked whole (read_answer)."""
    body = urllib.parse.urlencode({"query": query}).encode()
    request = urllib.request.Request(ENDPOINT, data=body, headers={
        "Accept": "text/tab-separated-values",
        "Content-Type": "application/x-www-form-urlencoded; charset=utf-8",
        "User-Agent": USER_AGENT})
    for attempt in range(RETRIES + 1):
        try:
            with urllib.request.urlopen(request, timeout=120) as response:
                text: str = response.read().decode("utf-8")
            read_answer(text)
            return text
        except urllib.error.HTTPError as exc:
            if exc.code not in (429, 500, 502, 503, 504) or attempt == RETRIES:
                raise
            retry = exc.headers.get("Retry-After", "")
            wait = int(retry) if retry.isdigit() else 30 * (attempt + 1)
            exc.close()
        except FetchError:
            if attempt == RETRIES:
                raise
            wait = 30 * (attempt + 1)
        print(f"query service refused or cut an answer; waiting {wait}s",
              file=sys.stderr)
        _sleep(wait)
    raise AssertionError("unreachable")


def fetch_dir() -> Path:
    path = name_usage.cache_dir() / FETCH_DIR
    path.mkdir(parents=True, exist_ok=True)
    return path


def _kept(path: Path, query: str) -> str:
    """The answer kept at `path`, asked for and kept first if missing;
    written to a temporary name and renamed once whole."""
    if not path.exists():
        text = ask(query)
        tmp = path.with_name(path.name + ".part")
        tmp.write_text(text, encoding="utf-8")
        tmp.replace(path)
    return path.read_text(encoding="utf-8")


def _sparql_strings(values: Iterable[str]) -> str:
    return ", ".join(json.dumps(v) for v in values)


def fetch(qid: str, folder: Path | None = None) -> dict[str, str]:
    """Every answer one country's relations read, by query name, the
    item labels under `items`, each kept in `folder`."""
    folder = folder or fetch_dir()
    code, tags = COUNTRIES[qid]
    langs = _sparql_strings(label_langs(tags))
    out = {}
    for name, template in QUERIES.items():
        out[name] = _kept(folder / f"{code}-{name}.tsv",
                          template.format(country=qid, langs=langs))
    items = sorted({v for name in ("given", "family")
                    for _, v, _ in read_answer(out[name])},
                   key=lambda q: int(q[1:]))
    parts = []
    for start in range(0, len(items), LABEL_BATCH):
        batch = items[start:start + LABEL_BATCH]
        query = ITEM_LABELS.format(
            items=" ".join(f"wd:{q}" for q in batch), langs=langs)
        # named by its items, so a batch is never read for another
        digest = hashlib.sha256(" ".join(batch).encode()).hexdigest()[:16]
        text = _kept(folder / f"{code}-items-{digest}.tsv", query)
        parts.append(text.split("\n", 1)[1])
    out["items"] = "?h\t?v\n" + "".join(parts)
    return out


# -- the people -------------------------------------------------------------

@dataclass
class Person:
    """One person's statements a relation reads: their given and family
    name items, their labels, birth names and nicknames by language."""

    given: set[str] = field(default_factory=set)
    family: set[str] = field(default_factory=set)
    labels: dict[str, list[str]] = field(default_factory=dict)
    births: dict[str, list[str]] = field(default_factory=dict)
    nicknames: dict[str, list[str]] = field(default_factory=dict)


def people(answers: Mapping[str, str]) -> dict[str, Person]:
    """A country's people, keyed by QID, from its answers."""
    out: dict[str, Person] = collections.defaultdict(Person)
    for h, v, _ in read_answer(answers["given"]):
        out[h].given.add(v)
    for h, v, _ in read_answer(answers["family"]):
        out[h].family.add(v)
    for name, attr in (("label", "labels"), ("birth", "births"),
                       ("nickname", "nicknames")):
        for h, v, lang in read_answer(answers[name]):
            getattr(out[h], attr).setdefault(wikidata_tag(lang), []).append(v)
    return dict(out)


def item_labels(answer: str) -> dict[str, dict[str, set[str]]]:
    """Each item's labels by language tag (LABEL_TAGS read)."""
    out: dict[str, dict[str, set[str]]] = {}
    for h, v, lang in read_answer(answer):
        out.setdefault(h, {}).setdefault(wikidata_tag(lang), set()).add(v)
    return out


# -- the pairs --------------------------------------------------------------

#: A word a language makes of a name that is not the person's own given
#: name: Hungarian `-né`, a wife named by her husband's name
#: (`Kovácsné`, `Istvánné`).
_NOT_OWN = {"hu": re.compile(r"\wné$", re.I)}


def name_words(text: str, titles: frozenset[str],
               tag: str = "") -> list[str]:
    """The text's words that can stand for a name, edge punctuation
    dropped, titles, initials and a `_NOT_OWN` word of `tag` left out."""
    words = (w.strip(_EDGE) for w in text.split())
    not_own = _NOT_OWN.get(tag)
    return [w for w in words if w and fc.is_name_word(w)
            and not fc._is_title(w, titles)
            and not (not_own and not_own.search(w))]


def _key(word: str) -> str:
    return fc.fold(word)


def _is_patronymic(word: str) -> bool:
    return has_patronymic_ending(word) or bool(_UK_PATRONYMIC.search(word))


@dataclass(frozen=True)
class Found:
    """One pair one person evidences: the two words as written, the
    vocabulary tag of the language they were found in and the relation."""

    x: str
    y: str
    tag: str
    relation: str


def _names(items: Iterable[str], labels: Mapping[str, Mapping[str, set[str]]],
           tag: str) -> list[str]:
    """The one-word labels of `items` in `tag`, or the language-
    independent ones (`mul`) of an item with none in it: a name item is
    labelled in `mul` alone more often than not."""
    out = []
    for q in items:
        by_lang = labels.get(q, {})
        texts = by_lang.get(tag) or by_lang.get("mul", set())
        out += [t for t in texts if len(t.split()) == 1]
    return out


def _one_by_letter(x: str, names: list[str]) -> str | None:
    """The one name, or the one of several starting with x's letter."""
    names = sorted(set(names))
    if len(names) == 1:
        return names[0]
    alike = [n for n in names if _key(n)[:1] == _key(x)[:1]]
    return alike[0] if len(alike) == 1 else None


def _shaped(x: str, y: str) -> bool:
    """The nickname filter: one first letter, or x's first two letters
    inside y (folded)."""
    fx, fy = _key(x), _key(y)
    return fx[:1] == fy[:1] or fx[:2] in fy


def _written(texts: Mapping[str, list[str]], tag: str,
             sole: bool) -> list[str]:
    """The texts in `tag`, and the language-independent ones where the
    country writes that language alone."""
    return texts.get(tag, []) + (texts.get("mul", []) if sole else [])


def relations(person: Person, labels: Mapping[str, Mapping[str, set[str]]],
              tags: tuple[str, ...], titles: frozenset[str]) -> set[Found]:
    """Every pair one person evidences, by each relation."""
    sole = len(tags) == 1
    out: set[Found] = set()
    for tag in tags:
        given = _names(person.given, labels, tag)
        family = _names(person.family, labels, tag)
        g_keys = {_key(g) for g in given}
        f_keys = {_key(f) for f in family}
        written = _written(person.labels, tag, sole)
        # 1. the birth name against the label
        for birth in _written(person.births, tag, sole):
            b = name_words(birth, titles, tag)
            for label in written:
                lw = name_words(label, titles, tag)
                b_keys, l_keys = {_key(w) for w in b}, {_key(w) for w in lw}
                extra_l = [w for w in lw if _key(w) not in b_keys]
                extra_b = [w for w in b if _key(w) not in l_keys]
                if len(extra_l) != 1 or not extra_b:
                    continue
                x = extra_l[0]
                y = _one_by_letter(x, extra_b) if len(extra_b) > 1 else extra_b[0]
                if y is None or not ({_key(x), _key(y)} & g_keys):
                    continue
                out.add(Found(x, y, tag, "birth"))
        # 2. a stated nickname against the given name
        for nickname in _written(person.nicknames, tag, sole):
            words = [w for w in name_words(nickname, titles, tag)
                     if _key(w) not in f_keys]
            if len(words) != 1 or _key(words[0]) in g_keys:
                continue
            x = words[0]
            y = _one_by_letter(x, given)
            if y is not None and _shaped(x, y):
                out.add(Found(x, y, tag, "nickname"))
        # 3. the label against the given name
        for label in written:
            lw = name_words(label, titles, tag)
            if not lw or {_key(w) for w in lw} & g_keys:
                continue
            rest = [w for w in lw if _key(w) not in f_keys
                    and not _is_patronymic(w)]
            if len(rest) != 1 or len(rest) == len(lw):
                continue
            x = rest[0]
            y = _one_by_letter(x, given)
            if y is not None:
                out.add(Found(x, y, tag, "label"))
    return {f for f in out if _pairable(f.x, f.y)}


def _pairable(x: str, y: str) -> bool:
    """Two different names in one script."""
    return (_match_fold(x) != _match_fold(y)
            and fc.script(x) == fc.script(y))


@dataclass
class Evidence:
    """One pair's people in one language: how many, by relation and by
    country."""

    people: set[str] = field(default_factory=set)
    relations: collections.Counter[str] = field(
        default_factory=collections.Counter)
    countries: collections.Counter[str] = field(
        default_factory=collections.Counter)


Pairs = dict[tuple[str, str, str], Evidence]


def mine(found: Iterable[tuple[str, str, Found]]) -> Pairs:
    """Each (a, b, tag) with its evidence, from (QID, country, Found)
    triples: a person counts once a pair, whichever relations found it."""
    out: Pairs = {}
    seen: set[tuple[str, str, str, str, str]] = set()
    for qid, country, f in found:
        a, b = sorted((build._normalize(f.x), build._normalize(f.y)))
        ev = out.setdefault((a, b, f.tag), Evidence())
        if (qid, a, b, f.tag, f.relation) not in seen:
            seen.add((qid, a, b, f.tag, f.relation))
            ev.relations[f.relation] += 1
        if qid not in ev.people:
            ev.people.add(qid)
            ev.countries[country] += 1
    return out


def country_found(qid: str, answers: Mapping[str, str],
                  titles: frozenset[str]) -> Iterator[tuple[str, str, Found]]:
    """Every (QID, country code, Found) of one country's answers."""
    code, tags = COUNTRIES[qid]
    labels = item_labels(answers["items"])
    for person_qid, person in people(answers).items():
        for f in relations(person, labels, tags, titles):
            yield person_qid, code, f


HEADER = ["a", "b", "source", "holders", "shape", "languages", "relations",
          "countries"]


def rows(pairs: Pairs, minimum: int,
         known: set[frozenset[str]]) -> list[list[str]]:
    """The candidate rows: a pair at `minimum` people or more in a
    language, not yet reviewed, its languages joined; most people first."""
    merged: dict[tuple[str, str], list[tuple[str, Evidence]]] = {}
    for (a, b, tag), ev in pairs.items():
        if len(ev.people) >= minimum and frozenset((a, b)) not in known:
            merged.setdefault((a, b), []).append((tag, ev))
    out = []
    for (a, b), evs in merged.items():
        people_ = set().union(*(ev.people for _, ev in evs))
        rel: collections.Counter[str] = sum(
            (ev.relations for _, ev in evs), collections.Counter())
        cty: collections.Counter[str] = sum(
            (ev.countries for _, ev in evs), collections.Counter())
        out.append([a, b, SOURCE, str(len(people_)), fc.shape(a, b),
                    " ".join(sorted(t for t, _ in evs)),
                    ", ".join(f"{r} {n}" for r, n in sorted(rel.items())),
                    ", ".join(f"{c} {n}" for c, n in cty.most_common())])
    out.sort(key=lambda r: (-int(r[3]), r[0], r[1]))
    return out


def write_tsv(rows_: list[list[str]]) -> str:
    out = io.StringIO()
    writer = csv.writer(out, delimiter="\t", lineterminator="\n")
    writer.writerow(HEADER)
    writer.writerows(rows_)
    return out.getvalue()


def _countries(codes: list[str] | None) -> list[str]:
    if not codes:
        return list(COUNTRIES)
    by_code = {code: qid for qid, (code, _) in COUNTRIES.items()}
    unknown = sorted(set(codes) - set(by_code))
    if unknown:
        raise SystemExit(f"no country {unknown}; one of {sorted(by_code)}")
    return [by_code[c] for c in codes]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    sub = parser.add_subparsers(dest="command", required=True)
    f = sub.add_parser("fetch", help="ask the query service, cached")
    f.add_argument("--country", action="append", metavar="CODE")
    p = sub.add_parser("pairs", help="write the candidates from the cache")
    p.add_argument("--country", action="append", metavar="CODE")
    p.add_argument("--min", type=int, default=1,
                   help="the fewest people a pair needs in a language")
    args = parser.parse_args(argv)
    qids = _countries(args.country)
    if args.command == "fetch":
        for qid in qids:
            fetch(qid)
            print(f"{COUNTRIES[qid][0]}: fetched", file=sys.stderr)
        return 0
    folder = fetch_dir()
    titles = fc.default_titles()
    found = []
    for qid in qids:
        code = COUNTRIES[qid][0]
        if not (folder / f"{code}-given.tsv").exists():
            raise SystemExit(f"{code} is not fetched; run `uv run python "
                             f"tools/vocab/familiar_wikidata.py fetch "
                             f"--country {code}`")
        found += country_found(qid, fetch(qid, folder), titles)
    pairs = mine(found)
    out = rows(pairs, args.min, fc.known_pairs())
    path = name_usage.cache_dir() / CANDIDATES_FILE
    path.write_text(write_tsv(out), encoding="utf-8")
    print(f"{len(pairs):,} pairs by language, {len(out):,} candidates at "
          f"{args.min}+ people not yet reviewed; wrote {path}",
          file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
