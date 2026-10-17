"""Regenerate the GND corpus from the German National Library's authority file.

A corpus with its own provenance. Each corpus covers a blind spot the
others have -- the roster, with each file's source and the blind spot it
leaves, is the table in tools/differential/README.md. This one is the
first with ground truth for REAL people. The GND (Gemeinsame Normdatei,
CC0) catalogs every person under a preferred name whose parts are stored
separately: `surname`, `forename`, `prefix` (the particle, `van`, `d'`,
`al-`), `counting` (a regnal number), or a single `personalName` where
the person is entered under the name as a whole, with no surname to
invert -- Icelanders, Malays, rulers, saints. CLDR's names are
fictional; these are deceased people notable enough for a Wikipedia
article, which keeps the corpus to public figures.

    uv run python tools/differential/build_gnd_corpus.py
    uv run python tools/differential/build_gnd_corpus.py --refresh

Writes three files beside this script, always together:

- corpus_gnd.jsonl -- one line per distinct text (two records can
  render alike), in the existing corpus line format, read by
  snapshot.py like every other corpus.
- gnd_fields.jsonl -- one line per rendering, with the GND fields
  written in CLDR's field vocabulary (`given`, `surname`,
  `surname-prefix` and `surname-core`, `generation`), so
  cldr_agreement.py compares both sources by the same rules.
- gnd_LICENSE -- the CC0 statement and the source credit.

Raw lobid responses are cached outside the repository, in a gnd/
directory under $NAMEPARSER_TOOLS_CACHE (default
~/.cache/nameparser-tools, as tools/name_usage.py uses), so a rebuild
reads the same records until --refresh fetches them again. The GND changes daily; the GND id on each
fields line is the provenance.

Selection is by SHAPE and AREA, never at random: each stratum below is a
lobid query plus a predicate, narrowed to the widest slice of GND ids
(`gndIdentifier:*7`, `*07`, ...) that holds at most POOL records,
fetched whole, and taken in sha256 order of the id -- skipping a record
whose fields cannot account for its name or that an earlier stratum
took -- up to its quota. A stratum that falls below its floor stops
the build before anything is written, as does a query that matches
nothing or a pool that pages short: a lobid change must fail the build,
not shrink the corpus. A stratum's count says what was sampled, not how
common the shape is.

Renderings, per record:

- a surname record gives GND's preferred name as written -- the index
  form, `Gogh, Vincent van` -- and, outside the family-first areas, a
  given-first rendering COMPOSED from the fields (`Vincent van Gogh`,
  `Ibrāhīm al-Ǧaʿfarī`, a particle ending in an apostrophe or a
  hyphen joined without a space). The composed line says so
  (`composed: true`): it tests the parser on a real name in a form this
  script wrote, as CLDR's renderings are formatter output. A glued
  particle's composed line states the glued word as a whole `surname`,
  since the comparison matches fields word by word; the index form,
  where the particle is a word of its own, keeps the split. The split
  is stated only for a prefix before a one-word surname; otherwise the
  family is stated whole (`surname`, not `surname-core`): GND does not
  split a particle inside a surname (`Vélez de Guevara`, `Zuylen van
  Nijevelt`), so what it leaves unsplit means "not stated", not "no
  particle", and only the family is compared.
- a personalName record gives the name as written; it is in direct
  order and has no inverted form. CLDR's `given` holds it, so the
  family name is expected empty.
- a counting record gives `personalName counting` (`Johann II.`), the
  preferred name without its `nameAddition` (`Pfalz-Zweibrücken,
  Pfalzgraf`, a German descriptor rather than a part of the name), so
  it is composed too.

A record whose fields do not spell its preferred name, or that carries
a field this script does not know, is left out.

Records with a nameAddition are otherwise left out: it mixes bynames,
offices and occupations in German, and no field says which.

Blind to: names as their bearers wrote them. GND writes in German
library romanization (`Dostoevskij, Fëdor Michajlovič`) and German forms
for historic figures (`Elisabeth`, `Thomas von Aquin`), Latin script
only. Its entry rules, not the bearer's culture, decide what counts as
a surname: Vietnamese and Thai names are entered as a personalName
(direct order), which would read their family names as given names, so
no stratum samples those areas; and an Icelandic family name (`Jón
Thoroddsen`) is a personalName too. GND's entry rules keep titles,
credentials and nicknames out of the preferred name, though a few slip
in as part of a personalName (`Imam Bonjol`, `Paku Alam VIII`).
"""
from __future__ import annotations

import argparse
import hashlib
import sys
import urllib.parse
import urllib.request
from collections.abc import Callable
from pathlib import Path
from typing import Any, NamedTuple

# The shared cache and file helpers (corpus_build.py). sys.path[0] is
# this directory when run as a script; the tests load this module by path.
_HERE = str(Path(__file__).resolve().parent)
if _HERE not in sys.path:
    sys.path.append(_HERE)

import corpus_build  # noqa: E402
from corpus_build import corpus_lines, fields_lines  # noqa: E402,F401

HERE = Path(__file__).resolve().parent
CORPUS = HERE / "corpus_gnd.jsonl"
FIELDS = HERE / "gnd_fields.jsonl"
LICENSE = HERE / "gnd_LICENSE"
SEARCH = "https://lobid.org/gnd/search"
USER_AGENT = ("python-nameparser build_gnd_corpus "
              "(https://github.com/derek73/python-nameparser)")
#: Deceased and notable: public figures only.
BASE = "_exists_:dateOfDeath AND _exists_:wikipedia"
#: The most records a stratum fetches before it is cut to its quota.
POOL = 300
PAGE = 100
#: Id-suffix slices, tried widest first until a stratum's pool fits
#: POOL. A sliced stratum never holds an id whose check digit is X.
SLICES = ("", "*7", "*07", "*007")
_ENTITY = "preferredNameEntityForThePerson"
_NO_ADDITION = f"NOT _exists_:{_ENTITY}.nameAddition"
#: Particles that join the next word without a space.
_GLUED = ("'", "’", "ʼ", "-")
#: The preferred-name fields this script knows; a record holding any
#: other is refused, so a field lobid adds is noticed, not ignored.
KNOWN = frozenset({"personalName", "counting", "nameAddition",
                   "surname", "forename", "prefix"})

LICENSE_TEXT = """\
corpus_gnd.jsonl and gnd_fields.jsonl are derived from the Gemeinsame
Normdatei (GND) of the Deutsche Nationalbibliothek, read through
lobid-gnd (https://lobid.org/gnd), and carry the GND's license.

The Deutsche Nationalbibliothek states that the GND authority data "is
available free of charge for general use under Creative Commons Zero
(CC0 1.0) terms."
https://www.dnb.de/EN/Professionell/Metadatendienste/Datenbezug/geschaeftsmodell.html

CC0 1.0 Universal: https://creativecommons.org/publicdomain/zero/1.0/

No attribution is required; this file credits the source anyway.
Source: Gemeinsame Normdatei (GND), Deutsche Nationalbibliothek, via
lobid-gnd (hbz). Each line of gnd_fields.jsonl names its record's GND
id, resolvable at https://d-nb.info/gnd/<id>.
"""


def area(code: str) -> str:
    return ('geographicAreaCode.id:"https://d-nb.info/standards/vocab/gnd/'
            f'geographic-area-code#{code}"')


def areas(*codes: str) -> str:
    return "(" + " OR ".join(area(c) for c in codes) + ")"


def _has(field: str) -> str:
    return f"_exists_:{_ENTITY}.{field}"


def _lacks(field: str) -> str:
    return f"NOT _exists_:{_ENTITY}.{field}"


def _entity(record: dict[str, Any]) -> dict[str, list[str]]:
    entity: dict[str, list[str]] = record.get(_ENTITY) or {}
    return entity


def _one(entity: dict[str, list[str]], field: str) -> str:
    values = entity.get(field) or []
    return values[0].strip() if len(values) == 1 else ""


def _compound(record: dict[str, Any]) -> bool:
    """A surname of two or more words, or hyphenated. The strata using
    it exclude a prefix in their query."""
    surname = _one(_entity(record), "surname")
    return " " in surname or "-" in surname.strip("-")


def _any(record: dict[str, Any]) -> bool:
    return True


class Stratum(NamedTuple):
    label: str
    query: str
    quota: int
    keep: Callable[[dict[str, Any]], bool] = _any
    #: An area where a name is written family-first: only GND's own
    #: index form is kept, since a composed given-first text would be
    #: unnatural and the area is where the person was active, not their
    #: culture, so a family-first composition could not be trusted.
    family_first: bool = False
    #: The fewest names the build accepts; below it, it stops. Set below
    #: the quota only where the pool is known to run short.
    least: int | None = None

    @property
    def floor(self) -> int:
        return self.quota if self.least is None else self.least


_SURNAME = f"{_has('surname')} AND {_NO_ADDITION}"
_DIRECT = f"{_has('personalName')} AND {_lacks('counting')} AND {_NO_ADDITION}"
_PARTICLE = f"{_has('prefix')} AND {_NO_ADDITION}"

STRATA = (
    # No surname: entered under the name as a whole.
    Stratum("direct-is", f"{_DIRECT} AND {area('XA-IS')}", 30),
    Stratum("direct-my-id", f"{_DIRECT} AND {areas('XB-MY', 'XB-ID')}", 30),
    Stratum("direct-arab", f"{_DIRECT} AND {areas('XC-EG', 'XB-IQ', 'XB-SY', 'XB-SA')}", 30),
    Stratum("direct-ir-af", f"{_DIRECT} AND {areas('XB-IR', 'XB-AF')}", 20),
    Stratum("direct-et-mm", f"{_DIRECT} AND {areas('XC-ET', 'XB-MM')}", 20, least=12),
    Stratum("direct-eu", f"{_DIRECT} AND {areas('XA-DE', 'XA-IT', 'XA-FR')}", 30),
    # Regnal numbers.
    Stratum("regnal", f"{_has('personalName')} AND {_has('counting')}", 40),
    # Particles, by area, and the elided d' and l' wherever they occur.
    Stratum("particle-de-at", f"{_PARTICLE} AND {areas('XA-DE', 'XA-AT', 'XA-CH')}", 30),
    Stratum("particle-nl-be", f"{_PARTICLE} AND {areas('XA-NL', 'XA-BE')}", 30),
    Stratum("particle-fr", f"{_PARTICLE} AND {area('XA-FR')}", 25),
    Stratum("particle-it", f"{_PARTICLE} AND {area('XA-IT')}", 20),
    Stratum("particle-iberia", f"{_PARTICLE} AND {areas('XA-ES', 'XA-PT', 'XD-BR', 'XD-MX', 'XD-AR')}", 25),
    Stratum("particle-elided", f"{_NO_ADDITION} AND ({_ENTITY}.prefix:d\\' OR {_ENTITY}.prefix:l\\')", 15, least=10),
    Stratum("particle-arab", f"{_PARTICLE} AND {areas('XC-EG', 'XB-IQ', 'XB-SY', 'XB-SA', 'XB-LB', 'XC-MA')}", 20),
    # Compound surnames (two words or hyphenated), no particle.
    Stratum("compound-iberia", f"{_SURNAME} AND {_lacks('prefix')} AND {areas('XA-ES', 'XA-PT')}", 30, _compound),
    Stratum("compound-latam", f"{_SURNAME} AND {_lacks('prefix')} AND {areas('XD-BR', 'XD-MX', 'XD-AR', 'XD-CO', 'XD-CL', 'XD-PE')}", 30, _compound),
    # Family-first areas: the index form only.
    Stratum("index-cjk", f"{_SURNAME} AND {areas('XB-CN', 'XB-TW', 'XB-JP', 'XB-KR')}", 40, family_first=True),
    Stratum("index-hu", f"{_SURNAME} AND {area('XA-HU')}", 20, family_first=True),
    # A control slice of plain surname, forename names.
    Stratum("plain-anglo", f"{_SURNAME} AND {_lacks('prefix')} AND {areas('XD-US', 'XA-GB', 'XA-IE')}", 25),
    Stratum("plain-europe", f"{_SURNAME} AND {_lacks('prefix')} AND {areas('XA-DE', 'XA-RU', 'XA-PL', 'XA-CZ', 'XA-GR')}", 25),
)


def _checked(body: bytes | str, source: str) -> dict[str, Any]:
    """A lobid search response, or ValueError naming where it came from."""
    data = corpus_build.parse_json(body, source)
    if not isinstance(data, dict) or "totalItems" not in data or "member" not in data:
        raise ValueError(f"{source} is not a lobid search response")
    return data


def _get_json(params: dict[str, str | int], refresh: bool) -> dict[str, Any]:
    url = f"{SEARCH}?{urllib.parse.urlencode(params)}"

    def fetch() -> bytes:
        request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
        with urllib.request.urlopen(request, timeout=120) as response:
            body: bytes = response.read()
        return body
    return corpus_build.cached_json(corpus_build.cache_dir("gnd"), url, url,
                                    fetch, _checked, refresh)


def _search(query: str, size: int, start: int, refresh: bool) -> dict[str, Any]:
    return _get_json({"q": f"{BASE} AND {query}", "filter": "type:Person",
                      "format": "json", "size": size, "from": start,
                      "sort": "gndIdentifier:asc"}, refresh)


def pool(stratum: Stratum, refresh: bool) -> list[dict[str, Any]]:
    """Every record of the stratum's widest id slice that fits POOL,
    after the stratum's own predicate. Raises on a query that matches
    nothing and on pages that do not add up to the total, since either
    means the query or the API changed (or the cache mixes two days'
    pages: --refresh)."""
    for suffix in SLICES:
        query = stratum.query + (f" AND gndIdentifier:{suffix}" if suffix else "")
        total = int(_search(query, 0, 0, refresh)["totalItems"])
        if total <= POOL:
            break
    else:
        raise ValueError(f"{stratum.label}: {total} records even in the "
                         f"narrowest slice; add a slice to SLICES")
    if total == 0:
        raise ValueError(f"{stratum.label}: the query matches nothing; "
                         f"has lobid's schema changed? {stratum.query}")
    records: list[dict[str, Any]] = []
    for start in range(0, total, PAGE):
        records.extend(_search(query, PAGE, start, refresh)["member"])
    ids = {str(r["gndIdentifier"]) for r in records}
    if len(records) != total or len(ids) != total:
        raise ValueError(f"{stratum.label}: {len(records)} records ({len(ids)} "
                         f"distinct) paged for a total of {total}; rerun with --refresh")
    return [r for r in records if stratum.keep(r)]


def _order(record: dict[str, Any]) -> str:
    return hashlib.sha256(str(record["gndIdentifier"]).encode()).hexdigest()


def renderings(record: dict[str, Any], stratum: Stratum) -> list[dict[str, Any]]:
    """The fields lines one record contributes; [] when its preferred
    name holds anything the fields cannot account for."""
    entity = _entity(record)
    if set(entity) - KNOWN or any(len(values) != 1 for values in entity.values()):
        return []
    gnd = str(record["gndIdentifier"])
    written = str(record["preferredName"]).strip()

    def row(order: str, text: str, fields: dict[str, str], composed: bool) -> dict[str, Any]:
        return {"file": gnd, "label": stratum.label, "order": order, "text": text,
                "shape": None, "composed": composed, "fields": fields}

    personal, counting = _one(entity, "personalName"), _one(entity, "counting")
    if personal:
        if {"surname", "forename", "prefix"} & set(entity) or "," in personal:
            return []
        if counting:
            regnal = f"{personal} {counting}"
            addition = _one(entity, "nameAddition")
            if written != (f"{regnal}, {addition}" if addition else regnal):
                return []
            return [row("givenFirst", regnal,
                        {"given": personal, "generation": counting}, True)]
        if written != personal:
            return []
        return [row("givenFirst", written, {"given": personal}, False)]
    surname, forename = _one(entity, "surname"), _one(entity, "forename")
    prefix = _one(entity, "prefix")
    if not surname or not forename or "nameAddition" in entity or "," in surname + forename:
        return []
    index = f"{surname}, {forename}" + (f" {prefix}" if prefix else "")
    if written != index:
        return []  # the preferred name is not what its fields say
    # The particle split is stated only where GND states all of it: a
    # prefix before a one-word core. With no prefix, or a core of several
    # words (`Zuylen van Nijevelt`), a particle may sit unstated inside,
    # so the family is stated whole and the split is not compared.
    if prefix and " " not in surname:
        fields = {"given": forename, "surname-prefix": prefix, "surname-core": surname}
    else:
        fields = {"given": forename,
                  "surname": f"{prefix} {surname}" if prefix else surname}
    rows = [row("sorting", written, fields, False)]
    if not stratum.family_first:
        if prefix.endswith(_GLUED):
            # One word: the comparison matches fields word by word, so
            # the glued word is stated whole; the index form, where the
            # particle is a word of its own, keeps the split.
            glued = prefix + surname
            rows.append(row("givenFirst", f"{forename} {glued}",
                            {"given": forename, "surname": glued}, True))
        else:
            family = f"{prefix} {surname}" if prefix else surname
            rows.append(row("givenFirst", f"{forename} {family}", fields, True))
    return rows


def build(refresh: bool) -> list[dict[str, Any]]:
    """Every stratum's rows, or ValueError naming each stratum that fell
    below its floor -- raised before main() writes anything."""
    rows: list[dict[str, Any]] = []
    seen: set[str] = set()
    short: list[str] = []
    for stratum in STRATA:
        taken = earlier = refused = 0
        for record in sorted(pool(stratum, refresh), key=_order):
            if taken == stratum.quota:
                break
            gnd = str(record["gndIdentifier"])
            if gnd in seen:
                earlier += 1
                continue
            mine = renderings(record, stratum)
            if not mine:
                refused += 1
                continue
            seen.add(gnd)
            rows.extend(mine)
            taken += 1
        print(f"{stratum.label:16} {taken:3}/{stratum.quota} names "
              f"({refused} refused, {earlier} taken by an earlier stratum)")
        if taken < stratum.floor:
            short.append(f"{stratum.label} {taken}/{stratum.floor}")
    if short:
        raise ValueError(f"strata below their floor, nothing written: {', '.join(short)}")
    return rows


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--refresh", action="store_true",
                    help="fetch from lobid again instead of reading the cache")
    rows = build(ap.parse_args().refresh)
    corpus_build.write_corpus(rows, CORPUS, FIELDS)
    LICENSE.write_text(LICENSE_TEXT, encoding="utf-8")
    print(f"GND: {len(rows)} renderings of {len({r['file'] for r in rows})} "
          f"names; wrote {CORPUS.name}, {FIELDS.name}, {LICENSE.name}")


if __name__ == "__main__":
    main()
