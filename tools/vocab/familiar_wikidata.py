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
languages, the tag Wikidata puts on a label, birth name or nickname;
one tagged `mul`, language-independent, read as the country's language
where it writes one alone). A person a given or family name of whom
the language cannot read (an item with no one-word label in it or in
`mul`) is left out of it, since the relations could not tell that
name from the word they pair:

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
   the given name (`Józsi` / `József` kept, `Pista` / `István` left
   out).
3. `label`: the label against the given name, where no word of the
   label is a given name of the person's: the label's words less its
   family names (P734), and less a patronymic, must be one word, and a
   family name must have stood in it (a stage name pairs with nothing).

Each word is a name word (familiar_candidates.is_name_word: no initial,
no digit), no title of the default lexicon's, and the two words differ
under the name match's fold and are written in one script. A pair is
counted once per person whichever relations, languages or citizenships
evidence it, spellings the name match folds alike are one pair
(`Алена` / `Алёна`), and it goes in the file of each language it was
found in.

What is left to the review: two spellings of one name (`Sergei` /
`Sergey`, shape `spelling`), another language's form, another name the
person used. A pair already in tools/vocab/familiar_reviewed.tsv is not
proposed again.

    uv run python tools/vocab/familiar_wikidata.py fetch           # every country, cached
    uv run python tools/vocab/familiar_wikidata.py fetch --country hu
    uv run python tools/vocab/familiar_wikidata.py pairs --min 1   # write the candidates

`fetch` keeps each query's answer in $NAMEPARSER_TOOLS_CACHE (or
~/.cache/nameparser-tools) under FETCH_DIR, named by the query's
digest, and asks the query service again only for an answer it does
not hold; `pairs` reads the kept answers alone, refusing to run on a
missing one, and writes CANDIDATES_FILE beside them (a file of its own
for `--country`). The requests name no person or project (USER_AGENT).
The candidates hold given names, counts and country codes, no person.
"""
from __future__ import annotations

import argparse
import collections
import csv
import hashlib
import http.client
import io
import json
import re
import sys
import tempfile
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
#: index alone, a country's in seconds; joining the given- and
#: family-name items' labels to the people in one
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
    after some rows, an error page, or a body cut inside or at the end
    of a line."""


def _unescape(text: str) -> str:
    return re.sub(r"\\(.)", lambda m: {"t": "\t", "n": "\n", "r": "\r"}.get(
        m.group(1), m.group(1)), text)


_ENTITY = re.compile(r"^<http://www\.wikidata\.org/entity/(Q\d+)>$")
_UNKNOWN = "<http://www.wikidata.org/.well-known/genid/"
_LITERAL = re.compile(r'^"((?:[^"\\]|\\.)*)"@([A-Za-z0-9-]+)$')


def read_answer(text: str,
                langs: Iterable[str] | None = None) -> list[tuple[str, str, str]]:
    """A `?h ?v` TSV answer's rows, each (QID, value, language): an
    item's QID with an empty language, or a literal's text and tag.
    A statement of unknown value (a blank node) is left out. Raises
    FetchError on any line of another shape, a literal with no language
    tag or, where `langs` is given, a tag not among them, and an answer
    not ending in a line break: every literal these queries ask for is
    tagged, so a cut inside a line (`"Kovács János"@h`) is refused, and
    one at a line's end is refused by the missing break."""
    if not text.endswith("\n"):
        raise FetchError(f"an answer not ending in a line break: "
                         f"{text[-120:]!r}")
    lines = text[:-1].split("\n")
    if lines[0] != "?h\t?v":
        raise FetchError(f"not a ?h ?v answer: {text[:120]!r}")
    allowed = None if langs is None else frozenset(langs)
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
        elif literal and (allowed is None or literal.group(2) in allowed):
            out.append((h.group(1), _unescape(literal.group(1)),
                        literal.group(2)))
        else:
            raise FetchError(f"line {number}'s value is neither an item "
                             f"nor a literal tagged as asked: {v[:120]!r}")
    return out


def _sleep(seconds: float) -> None:
    time.sleep(seconds)


def ask(query: str, name: str = "a query",
        langs: Iterable[str] | None = None) -> str:
    """The query service's TSV answer, checked whole (read_answer),
    retried after a rate limit, a server error or timeout, a cut answer
    or a connection the client timed out; `name` says which in each
    message."""
    body = urllib.parse.urlencode({"query": query}).encode()
    request = urllib.request.Request(ENDPOINT, data=body, headers={
        "Accept": "text/tab-separated-values",
        "Content-Type": "application/x-www-form-urlencoded; charset=utf-8",
        "User-Agent": USER_AGENT})
    for attempt in range(RETRIES + 1):
        try:
            with urllib.request.urlopen(request, timeout=120) as response:
                text: str = response.read().decode("utf-8")
            read_answer(text, langs)
            return text
        except urllib.error.HTTPError as exc:
            if exc.code not in (429, 500, 502, 503, 504) or attempt == RETRIES:
                raise FetchError(f"{name}: HTTP {exc.code}") from exc
            retry = exc.headers.get("Retry-After", "")
            wait = int(retry) if retry.isdigit() else 30 * (attempt + 1)
            reason = f"HTTP {exc.code}"
            exc.close()
        except (FetchError, OSError, http.client.HTTPException) as exc:
            # OSError takes URLError and the client's own timeout
            if attempt == RETRIES:
                raise FetchError(f"{name}: {exc}") from exc
            wait, reason = 30 * (attempt + 1), str(exc)[:200]
        print(f"{name}: {reason}; waiting {wait}s", file=sys.stderr)
        _sleep(wait)
    raise AssertionError("unreachable")


def fetch_dir() -> Path:
    path = name_usage.cache_dir() / FETCH_DIR
    path.mkdir(parents=True, exist_ok=True)
    return path


def _digest(text: str) -> str:
    return hashlib.sha256(text.encode()).hexdigest()[:16]


def _kept(folder: Path, name: str, query: str, offline: bool,
          langs: Iterable[str] | None = None) -> str:
    """The answer to `query`, kept in `folder` under `name` and the
    query's digest, so a changed query (another country's languages, an
    edited template) is asked again rather than read from an old answer;
    asked for first if missing, unless `offline`, which raises naming
    the file instead. Written under a temporary name of its own and
    renamed once whole, and checked whole again when read back."""
    path = folder / f"{name}-{_digest(query)}.tsv"
    if not path.exists():
        if offline:
            raise SystemExit(f"{path} is not fetched; run `uv run python "
                             f"tools/vocab/familiar_wikidata.py fetch`")
        text = ask(query, name, langs)
        with tempfile.NamedTemporaryFile(
                "w", encoding="utf-8", dir=folder, prefix=path.name,
                suffix=".part", delete=False) as tmp:
            tmp.write(text)
        Path(tmp.name).replace(path)
        return text
    text = path.read_text(encoding="utf-8")
    try:
        read_answer(text, langs)
    except FetchError as exc:
        raise SystemExit(f"{path}: {exc}; delete it and fetch again") from exc
    return text


def _sparql_strings(values: Iterable[str]) -> str:
    return ", ".join(json.dumps(v) for v in values)


#: The queries whose literals must be in the label languages asked.
_LABEL_QUERIES = frozenset({"label"})


def fetch(qid: str, folder: Path | None = None,
          offline: bool = False) -> dict[str, str]:
    """Every answer one country's relations read, by query name, the
    item labels under `items`, each kept in `folder`; `offline` reads
    the folder alone (_kept)."""
    folder = folder or fetch_dir()
    code, tags = COUNTRIES[qid]
    asked = label_langs(tags)
    langs = _sparql_strings(asked)
    out = {}
    for name, template in QUERIES.items():
        out[name] = _kept(folder, f"{code}-{name}",
                          template.format(country=qid, langs=langs), offline,
                          asked if name in _LABEL_QUERIES else None)
    items = sorted({v for name in ("given", "family")
                    for _, v, _ in read_answer(out[name])},
                   key=lambda q: int(q[1:]))
    parts = []
    for start in range(0, len(items), LABEL_BATCH):
        batch = items[start:start + LABEL_BATCH]
        query = ITEM_LABELS.format(
            items=" ".join(f"wd:{q}" for q in batch), langs=langs)
        text = _kept(folder, f"{code}-items", query, offline, asked)
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
#: (`Kovácsné`, `Istvánné`); a name of three letters or more before it,
#: so the given name `René` stays.
_NOT_OWN = {"hu": re.compile(r"\w{3}né$", re.I)}


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
           tag: str) -> list[str] | None:
    """The one-word labels of `items` in `tag`, or the language-
    independent ones (`mul`) of an item with none in it, which many
    name items carry alone; None where an item has neither, or only a
    label of several words (`Anna Mária`), which a relation could not
    tell from the person's other words."""
    out = []
    for q in items:
        by_lang = labels.get(q, {})
        texts = [t for t in by_lang.get(tag) or by_lang.get("mul", set())
                 if len(t.split()) == 1]
        if not texts:
            return None
        out += texts
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
        if given is None or family is None:
            continue  # a name the relations cannot read in this language
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
            if not any(_key(w) in f_keys for w in lw):
                continue  # no family name in it: a stage name
            rest = [w for w in lw if _key(w) not in f_keys
                    and not _is_patronymic(w)]
            if len(rest) != 1:
                continue
            x = rest[0]
            y = _one_by_letter(x, given)
            if y is not None:
                out.add(Found(x, y, tag, "label"))
    return {f for f in out if _pairable(f.x, f.y)}


def _one_script(word: str) -> bool:
    return len({fc.script(c) for c in word}) == 1


def _pairable(x: str, y: str) -> bool:
    """Two different name words, each written in one script and both in
    the same: a given-name item's label is a name word too only once
    tested (`Сол/Саул`, `Богданa` with a Latin `a`)."""
    return (fc.is_name_word(x) and fc.is_name_word(y)
            and _one_script(x) and _one_script(y)
            and _match_fold(x) != _match_fold(y)
            and fc.script(x) == fc.script(y))


@dataclass
class Evidence:
    """One pair's people in one language: every person (QID), and the
    people each relation and each country found, so a column counts a
    person once however many languages, spellings or citizenships
    found them."""

    people: set[str] = field(default_factory=set)
    relations: dict[str, set[str]] = field(default_factory=dict)
    countries: dict[str, set[str]] = field(default_factory=dict)


Pairs = dict[tuple[str, str, str], Evidence]


def mine(found: Iterable[tuple[str, str, Found]]) -> Pairs:
    """Each (a, b, tag) with its evidence, from (QID, country, Found)
    triples: a person counts once a pair, whichever relations found it."""
    out: Pairs = {}
    for qid, country, f in found:
        a, b = sorted((build._normalize(f.x), build._normalize(f.y)))
        ev = out.setdefault((a, b, f.tag), Evidence())
        ev.people.add(qid)
        ev.relations.setdefault(f.relation, set()).add(qid)
        ev.countries.setdefault(country, set()).add(qid)
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


def _union(maps: Iterable[Mapping[str, set[str]]]) -> dict[str, set[str]]:
    out: dict[str, set[str]] = {}
    for m in maps:
        for k, q in m.items():
            out.setdefault(k, set()).update(q)
    return out


def _folded_pair(a: str, b: str) -> frozenset[str]:
    """The pair as the name match reads it, each name folded
    (`Алена` and `Алёна` one name)."""
    return frozenset((_match_fold(a), _match_fold(b)))


def rows(pairs: Pairs, minimum: int,
         known: set[frozenset[str]]) -> list[list[str]]:
    """The candidate rows: each pair as the name match reads it, its
    spellings, languages and people merged (`Алена` and `Алёна` one
    name) and written as its most attested spelling; at `minimum` people
    or more in all, and not yet reviewed in any spelling the match folds
    alike; most people first."""
    seen = {_folded_pair(*pair) for pair in known if len(pair) == 2}
    merged: dict[frozenset[str], list[tuple[str, str, str, Evidence]]] = {}
    for (a, b, tag), ev in pairs.items():
        key = _folded_pair(a, b)
        if key not in seen:
            merged.setdefault(key, []).append((a, b, tag, ev))
    out = []
    for evs in merged.values():
        people_ = set().union(*(ev.people for *_, ev in evs))
        if len(people_) < minimum:
            continue
        spelled: collections.Counter[tuple[str, str]] = collections.Counter()
        for a, b, _, ev in evs:
            spelled[a, b] += len(ev.people)
        (a, b), _ = min(spelled.items(), key=lambda kv: (-kv[1], kv[0]))
        rel = _union(ev.relations for *_, ev in evs)
        cty = _union(ev.countries for *_, ev in evs)
        out.append([a, b, SOURCE, str(len(people_)), fc.shape(a, b),
                    " ".join(sorted({t for _, _, t, _ in evs})),
                    ", ".join(f"{r} {len(q)}" for r, q in sorted(rel.items())),
                    ", ".join(f"{c} {len(q)}" for c, q in sorted(
                        cty.items(), key=lambda kv: (-len(kv[1]), kv[0])))])
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
                   help="the fewest people a pair needs, its languages "
                        "together (#1387's review read 2)")
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
        found += country_found(qid, fetch(qid, folder, offline=True), titles)
    pairs = mine(found)
    out = rows(pairs, args.min, fc.known_pairs())
    path = name_usage.cache_dir() / candidates_file(args.country)
    path.write_text(write_tsv(out), encoding="utf-8")
    print(f"{len(pairs):,} pairs by language, {len(out):,} candidates at "
          f"{args.min}+ people not yet reviewed; wrote {path}",
          file=sys.stderr)
    return 0


def candidates_file(codes: list[str] | None) -> str:
    """CANDIDATES_FILE for every country; for some, a name of its own
    holding their codes, so a partial run never overwrites a whole one."""
    if not codes:
        return CANDIDATES_FILE
    return CANDIDATES_FILE.replace(".tsv", "-" + "-".join(sorted(set(codes)))
                                   + ".tsv")


if __name__ == "__main__":
    sys.exit(main())
