"""Regenerate the Wikidata corpus: real names with a second surname or a patronymic stated.

A corpus with its own provenance. Each corpus covers a blind spot the
others have -- the roster, with each file's source and the blind spot it
leaves, is the table in tools/differential/README.md. This one exists for
the two fields no other open source labels: Wikidata's P1950 (second
family name in a Spanish name) and P5056 (patronym or matronym). CLDR's
names are fictional, and the GND holds `García Márquez` as one surname and
a patronymic inside the forename. Wikidata is CC0.

    uv run python tools/differential/build_wikidata_corpus.py
    uv run python tools/differential/build_wikidata_corpus.py --refresh

Writes three files beside this script, always together:

- corpus_wikidata.jsonl -- one line per distinct (rendering, shape), in
  the existing corpus line format, read by snapshot.py like every other
  corpus.
- wikidata_fields.jsonl -- one line per rendering, with the parts written
  in CLDR's field vocabulary (`given`, `surname`, `surname2`) plus
  `patronymic`, which CLDR has no field for, so cldr_agreement.py
  compares it by the same rules.
- wikidata_LICENSE -- the CC0 statement and the source credit.

Raw responses are cached outside the repository, in a wikidata/
directory under $NAMEPARSER_TOOLS_CACHE (default
~/.cache/nameparser-tools, as tools/name_usage.py uses), so a rebuild reads the same items until
--refresh fetches them again. Wikidata changes constantly; the QID on
each fields line is the provenance.

Selection is one Wikidata Query Service query per stratum (one country
of citizenship and one property), restricted to public figures --
deceased, or with at least MIN_SITELINKS Wikipedia and sister-project
articles -- and ordered by an MD5 of the item URI, so the sample is
deterministic. The queries run one at a time. The items are then fetched
with wbgetentities in batches of 50, and a stratum takes the first items
in that order that survive the alignment below, up to its quota. A
stratum that falls below its floor stops the build before anything is
written, as does a query that matches nothing or a response that is not
what was asked for: a Wikidata change must fail the build, not shrink
the corpus. A stratum's count says what was sampled, not how common the
shape is.

Item labels are NOT concatenated into a name. Joining the parts
reproduced the person's own written name for 12-64% of them, by country,
in the 2026-10-16 corpus survey:
parts are missing, an extra baptismal name is stated, a Russian surname
item holds the masculine form of a woman's name. Instead each written
name -- the person's P1559 (name in native language) and their label in
the stratum's language -- is TOKEN-ALIGNED against the parts: each part's
spellings (its labels in the text's language, the stratum's language and
`mul`, and its P1705 native labels) are found as whole runs of the text's
words, and the text is kept only if

- every word is claimed by exactly one part, except a connective
  (`bin`, `binti`, `i`, `y`, ...) standing directly before a claimed
  part, which joins that part as written (`bin Hamzah`, `i Coll`);
- no part matches in two places, and no two parts claim the same word
  (a person whose P734 and P5056 are the same item, seen in Malaysian
  data, falls out here);
- the stratum's own property is among the parts found, with a given name
  and, for a second surname, the first one.

A woman's Russian surname may be written in the feminine form of its
item's label (`Лядова` for `Лядов`); those forms are added as spellings
for a female person only. A P734 "no value" statement is never needed:
a text with no family part simply states none. A text that writes the
family name first without a comma (the Russian official order) is tagged
FAMILY_FIRST (shape 4), as build_cldr_corpus.py tags CLDR's
surnameFirst renderings; one with a comma is a sorting form, read by the
comma.

The field mapping. P735 → `given`, P734 → `surname`, P1950 → `surname2`,
P5056 → `patronymic`. A part's words are stated as they stand in the text,
so a particle inside a P734 label (`van Gogh`, `del Rey`) stays in the
surname: Wikidata does not split it, so the particle and base views are
not compared. cldr_agreement.py scores `surname2` inside `family` and
`patronymic` inside `given_names` -- a patronymic is not a family name,
the GND and LC convention, so `Vigdís Finnbogadóttir` expects the family
empty -- and also scores each field on its own once ParsedName has one.

Blind to: everything the strict filter drops. The survivors are tidy
names whose every word has a Wikidata item, so short display forms
(`Pedro Martínez`, with no second surname written), nicknames, and names
with an unrecorded middle part are missing; and only the eight
citizenships below are sampled, Malaysia thinly (its floor says why). A
family-first text with no family part (an Icelandic or Malay name in a
sorted list without a comma) cannot be told from a given-first one, so
it would be read given-first; none is in the committed data. No title, credential or suffix is in any text.
"""
from __future__ import annotations

import argparse
import sys
import time
import urllib.parse
import urllib.request
from collections.abc import Iterable
from pathlib import Path
from typing import Any, NamedTuple

# The shared cache and file helpers (corpus_build.py), found by putting
# this directory on sys.path: see corpus_build's docstring for why.
_HERE = str(Path(__file__).resolve().parent)
if _HERE not in sys.path:
    sys.path.append(_HERE)

import corpus_build  # noqa: E402
from corpus_build import corpus_lines, fields_lines  # noqa: E402,F401

HERE = Path(__file__).resolve().parent
CORPUS = HERE / "corpus_wikidata.jsonl"
FIELDS = HERE / "wikidata_fields.jsonl"
LICENSE = HERE / "wikidata_LICENSE"
SPARQL = "https://query.wikidata.org/sparql"
API = "https://www.wikidata.org/w/api.php"
#: WDQS asks for a descriptive agent; "bot" marks automated use.
USER_AGENT = ("python-nameparser-corpus-bot/1.0 build_wikidata_corpus "
              "(https://github.com/derek73/python-nameparser)")
#: Living people count as public figures only with this many sitelinks.
MIN_SITELINKS = 10
#: Items fetched per stratum before the alignment filter cuts it to its
#: quota: the survivors were a quarter to a half in the 2026-10-16 probe.
POOL_FACTOR = 6
BATCH = 50
#: shapes.py's FAMILY_FIRST shape, as build_cldr_corpus.py uses it.
FAMILY_FIRST_SHAPE = 4
FEMALE = "Q6581072"
#: Wikidata property -> the field it is stated as.
PARTS = {"P735": "given", "P734": "surname", "P1950": "surname2",
         "P5056": "patronymic"}
#: Words that introduce the part after them and have no item of their
#: own: Malay bin/binti (and abbreviations), Catalan i, Spanish y. Matched
#: as written: a capital `I` or `Y` is an initial, not a connective.
CONNECTIVES = frozenset({"bin", "binti", "bt", "bt.", "b.", "i", "y",
                         # Malay writes these capitalized too
                         "Bin", "Binti"})

LICENSE_TEXT = """\
corpus_wikidata.jsonl and wikidata_fields.jsonl are derived from Wikidata
(https://www.wikidata.org), read through the Wikidata Query Service and
the wbgetentities API, and carry Wikidata's license.

Wikidata states that "All structured data (i.e. the main, Property,
Lexeme, and EntitySchema namespaces) is released into the public
domain".
https://www.wikidata.org/wiki/Wikidata:Licensing

CC0 1.0 Universal: https://creativecommons.org/publicdomain/zero/1.0/

No attribution is required; this file credits the source anyway.
Source: Wikidata, Wikimedia Foundation. Each line of
wikidata_fields.jsonl names its item's QID, resolvable at
https://www.wikidata.org/wiki/<QID>. Only public figures are sampled
(deceased, or with at least 10 sitelinks), and only name strings and
QIDs are kept.
"""


class Stratum(NamedTuple):
    label: str
    country: str      # Wikidata item for the country of citizenship (P27)
    prop: str         # the property every sampled item states
    language: str     # the language its people's names are written in
    quota: int
    #: The fewest names the build accepts; below it, it stops. Set below
    #: the quota only where the pool is known to run short.
    least: int | None = None

    @property
    def floor(self) -> int:
        return self.quota if self.least is None else self.least


STRATA = (
    Stratum("surname2-es", "Q29", "P1950", "es", 150),
    Stratum("surname2-mx", "Q96", "P1950", "es", 100),
    Stratum("surname2-co", "Q739", "P1950", "es", 80),
    Stratum("patronymic-ru", "Q159", "P5056", "ru", 110),
    Stratum("patronymic-su", "Q15180", "P5056", "ru", 60),
    Stratum("patronymic-ri", "Q34266", "P5056", "ru", 40),
    Stratum("patronymic-is", "Q189", "P5056", "is", 100),
    # 17 Malaysian public figures with a P5056 statement on 2026-10-16,
    # 9 aligning: the pool is the limit, and the floor leaves 3 to lose.
    Stratum("patronymic-my", "Q833", "P5056", "ms", 40, least=6),
)


def _checked(body: bytes | str, source: str, kind: str) -> dict[str, Any]:
    """A WDQS result (`kind` "results") or a wbgetentities response
    ("entities"), or ValueError naming where it came from. An API error
    arrives with status 200, so the shape is what tells."""
    data = corpus_build.parse_json(body, source)
    if not isinstance(data, dict) or kind not in data or "error" in data:
        detail = data.get("error") if isinstance(data, dict) else None
        raise ValueError(f"{source} has no {kind!r}" + (f": {detail}" if detail else ""))
    return data


def _fetch(url: str, data: bytes | None, refresh: bool, kind: str) -> dict[str, Any]:
    def fetch() -> bytes:
        headers = {"User-Agent": USER_AGENT, "Accept": "application/json"}
        request = urllib.request.Request(url, data=data, headers=headers)
        with urllib.request.urlopen(request, timeout=90) as response:
            body: bytes = response.read()
        time.sleep(1)  # sequential, and gentle
        return body
    return corpus_build.cached_json(
        corpus_build.cache_dir("wikidata"), url + "\n" + (data or b"").decode(), url,
        fetch, lambda body, source: _checked(body, source, kind), refresh)


def query(stratum: Stratum) -> str:
    """The stratum's WDQS query: its public figures, in MD5 order."""
    return f"""SELECT ?item WHERE {{
  ?item wdt:{stratum.prop} ?part; wdt:P31 wd:Q5; wdt:P27 wd:{stratum.country};
        wikibase:sitelinks ?links.
  FILTER(?links >= {MIN_SITELINKS} || EXISTS {{ ?item wdt:P570 ?died }})
}} GROUP BY ?item ORDER BY MD5(STR(?item)) LIMIT {stratum.quota * POOL_FACTOR}"""


def pool(stratum: Stratum, refresh: bool) -> list[str]:
    """The stratum's QIDs in MD5 order; raises on a query matching
    nothing, since that means the query or Wikidata changed."""
    data = urllib.parse.urlencode({"query": query(stratum), "format": "json"}).encode()
    result = _fetch(SPARQL, data, refresh, "results")
    qids = [b["item"]["value"].rsplit("/", 1)[1] for b in result["results"]["bindings"]]
    if not qids:
        raise ValueError(f"{stratum.label}: the query matches nothing; has a "
                         f"property or item changed?\n{query(stratum)}")
    return qids


def entities(ids: Iterable[str], props: str, refresh: bool) -> dict[str, Any]:
    """Each requested item, keyed by the id asked for (a redirected item
    comes back under that id, holding its target; a deleted one, marked
    `missing`). Raises on an id the response leaves out."""
    ids = sorted(set(ids))
    out: dict[str, Any] = {}
    for start in range(0, len(ids), BATCH):
        url = API + "?" + urllib.parse.urlencode({
            "action": "wbgetentities", "ids": "|".join(ids[start:start + BATCH]),
            "props": props, "format": "json"})
        out.update(_fetch(url, None, refresh, "entities")["entities"])
    absent = sorted(i for i in ids if i not in out)
    if absent:
        raise ValueError(f"wbgetentities left out {', '.join(absent[:10])}"
                         f"{' ...' if len(absent) > 10 else ''}; rerun with --refresh")
    return out


def statements(item: dict[str, Any], prop: str) -> list[Any]:
    """The values of an item's non-deprecated statements for `prop`;
    an item id for an item value, the text for a monolingual one
    (with its language as a tuple)."""
    out: list[Any] = []
    for claim in item.get("claims", {}).get(prop, []):
        snak = claim["mainsnak"]
        if claim.get("rank") == "deprecated" or snak["snaktype"] != "value":
            continue
        value = snak["datavalue"]["value"]
        if isinstance(value, dict) and "id" in value:
            out.append(value["id"])
        elif isinstance(value, dict) and "text" in value:
            out.append((value["text"], value["language"]))
    return out


def _label(item: dict[str, Any], language: str) -> str:
    return str(item.get("labels", {}).get(language, {}).get("value", ""))


def spellings(part: dict[str, Any], languages: Iterable[str]) -> set[str]:
    """Every way the part item's name may be written in a text."""
    found = {_label(part, lang) for lang in languages}
    found |= {text for text, _ in statements(part, "P1705")}
    return {s.strip() for s in found if s.strip()}


#: Masculine Russian surname endings and their feminine forms.
_FEMININE = (("ский", "ская"), ("цкий", "цкая"), ("ой", "ая"), ("ый", "ая"),
             ("ов", "ова"), ("ев", "ева"), ("ёв", "ёва"), ("ин", "ина"),
             ("ын", "ына"))


def feminine(surname: str) -> str:
    """The feminine form of a masculine Russian surname, or ''."""
    for male, female in _FEMININE:
        if surname.endswith(male):
            return surname[: -len(male)] + female
    return ""


def _word(token: str) -> str:
    """A text word as compared: a comma glued to it is not part of it."""
    return token.rstrip(",")


def _spans(tokens: list[str], words: list[str], names: set[str]) -> set[tuple[int, int]]:
    """Where any spelling occurs as whole words, as (start, end) word
    positions. A comma may only end a span: `Кушнарёв, Юрий` is two parts."""
    found: set[tuple[int, int]] = set()
    for name in names:
        want = name.split()
        for i in range(len(words) - len(want) + 1):
            j = i + len(want)
            if words[i:j] == want and not any(t.endswith(",") for t in tokens[i:j - 1]):
                found.add((i, j))
    return found


def _widest(spans: set[tuple[int, int]]) -> set[tuple[int, int]]:
    """The spans no other span contains: `María José` over its `María`."""
    return {(i, j) for i, j in spans
            if not any(a <= i and j <= b and (a, b) != (i, j) for a, b in spans)}


def align(text: str, parts: list[tuple[str, set[str]]]) -> dict[str, list[int]] | None:
    """Each field's word positions in `text`, or None when the text is
    not covered by exactly one part per word. `parts` holds one
    (field, spellings) entry per statement."""
    tokens = text.split()
    words = [_word(t) for t in tokens]
    claimed: dict[int, str] = {}
    for field, names in parts:
        widest = _widest(_spans(tokens, words, names))
        if len(widest) > 1:
            return None  # the part matches in two places
        for i, j in widest:
            for k in range(i, j):
                if k in claimed:
                    return None  # two parts claim one word
                claimed[k] = field
    # Right to left, so a run of connectives chains to the part after it;
    # tokens[k], not words[k], since a connective carrying a comma joins nothing.
    for k in range(len(words) - 1, -1, -1):
        if k not in claimed and words[k] in CONNECTIVES \
                and k + 1 in claimed and not tokens[k].endswith(","):
            claimed[k] = claimed[k + 1]
    if len(claimed) != len(words):
        return None
    out: dict[str, list[int]] = {}
    for k in sorted(claimed):
        out.setdefault(claimed[k], []).append(k)
    return out


def _order(text: str, fields: dict[str, list[int]]) -> tuple[str, int | None]:
    if "," in text:
        return "sorting", None
    family = fields.get("surname", []) + fields.get("surname2", [])
    if family and min(family) == 0:
        return "surnameFirst", FAMILY_FIRST_SHAPE
    return "givenFirst", None


def renderings(qid: str, person: dict[str, Any], names: dict[str, Any],
               stratum: Stratum) -> list[dict[str, Any]]:
    """The fields lines one person contributes; [] when no written name
    of theirs aligns."""
    female = FEMALE in statements(person, "P21")
    texts = list(statements(person, "P1559"))
    if _label(person, stratum.language):
        texts.append((_label(person, stratum.language), stratum.language))
    rows: list[dict[str, Any]] = []
    seen: set[str] = set()
    for text, lang in texts:
        text = " ".join(text.split())
        if text in seen:
            continue
        seen.add(text)
        languages = (lang, stratum.language, "mul")
        parts: list[tuple[str, set[str]]] = []
        for prop, field in PARTS.items():
            for value in statements(person, prop):
                written = spellings(names.get(value, {}), languages)
                if field == "surname" and female:
                    written |= {f for f in map(feminine, written) if f}
                parts.append((field, written))
        aligned = align(text, parts)
        if aligned is None or PARTS[stratum.prop] not in aligned \
                or "given" not in aligned \
                or (stratum.prop == "P1950" and "surname" not in aligned):
            continue
        order, shape = _order(text, aligned)
        if any(row["order"] == order for row in rows):
            continue  # P1559 first: one rendering per order
        words = [_word(t) for t in text.split()]
        rows.append({"file": qid, "label": stratum.label, "order": order,
                     "text": text, "shape": shape, "composed": False,
                     "fields": {f: " ".join(words[k] for k in ks)
                                for f, ks in aligned.items()}})
    return rows


def build(refresh: bool) -> list[dict[str, Any]]:
    """Every stratum's rows, or ValueError naming each stratum that fell
    below its floor -- raised before main() writes anything."""
    rows: list[dict[str, Any]] = []
    seen: set[str] = set()
    short: list[str] = []
    for stratum in STRATA:
        pooled = pool(stratum, refresh)
        qids = [q for q in pooled if q not in seen]
        people = entities(qids, "labels|claims", refresh)
        # A pooled person must exist; a deleted name-part item is a fact
        # about the data, and only refuses the person stating it.
        stale = sorted(q for q in qids if "missing" in people[q])
        if stale:
            raise ValueError(f"{stratum.label}: WDQS pooled items Wikidata reports "
                             f"missing: {', '.join(stale[:10])}; rerun with --refresh")
        parts = {v for p in people.values() for prop in PARTS
                 for v in statements(p, prop)}
        names = entities(parts, "labels|claims", refresh)
        taken = refused = 0
        for qid in qids:
            if taken == stratum.quota:
                break
            mine = renderings(qid, people[qid], names, stratum)
            if not mine:
                refused += 1
                continue
            seen.add(qid)
            rows.extend(mine)
            taken += 1
        print(f"{stratum.label:15} {taken:3}/{stratum.quota} names "
              f"({refused} refused, {len(pooled) - len(qids)} taken by an "
              f"earlier stratum, {len(pooled)} pooled)")
        if taken < stratum.floor:
            short.append(f"{stratum.label} {taken}/{stratum.floor}")
    if short:
        raise ValueError(f"strata below their floor, nothing written: {', '.join(short)}")
    return rows


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--refresh", action="store_true",
                    help="fetch from Wikidata again instead of reading the cache")
    rows = build(ap.parse_args().refresh)
    corpus_build.write_corpus(rows, CORPUS, FIELDS)
    LICENSE.write_text(LICENSE_TEXT, encoding="utf-8")
    print(f"Wikidata: {len(rows)} renderings of {len({r['file'] for r in rows})} "
          f"names; wrote {CORPUS.name}, {FIELDS.name}, {LICENSE.name}")


if __name__ == "__main__":
    main()
