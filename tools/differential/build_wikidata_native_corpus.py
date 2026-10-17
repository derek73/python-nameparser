"""Regenerate the native-script Wikidata corpus: real names in their own scripts.

A corpus with its own provenance (the roster, with each file's source and
blind spot, is the table in tools/differential/README.md). Every other
real-name corpus is Latin script but for Wikidata's Russian patronymics,
and CLDR's native-script names are fictional, so the parser's
script-conditional rules -- family-first order for Han, Hangul and kana,
Korean surname segmentation, the CJK honorific peel -- had been tested
against no real name. This corpus holds real names as Wikidata writes
them in Arabic, Hebrew, Devanagari, Bengali, Thai, Greek, Georgian,
Armenian, Hangul, Han and kana, and Cyrillic beyond Russian. Wikidata is
CC0.

    uv run python tools/differential/build_wikidata_native_corpus.py
    uv run python tools/differential/build_wikidata_native_corpus.py --refresh
    uv run python tools/differential/build_wikidata_native_corpus.py --lc-check

Writes three files beside this script, always together:

- corpus_wikidata_native.jsonl -- one line per distinct (rendering,
  shape), read by snapshot.py like every other corpus.
- wikidata_native_fields.jsonl -- one line per rendering, in
  build_wikidata_corpus.py's field vocabulary (`given`, `surname`,
  `patronymic`), scored by cldr_agreement.py; a rendering in a script a
  locale pack exists for also names that pack (`pack`), and the locale
  view scores it under the pack as well.
- wikidata_native_LICENSE -- the CC0 statement and the source credit.

The machinery is build_wikidata_corpus.py's, imported: the cache under
$NAMEPARSER_TOOLS_CACHE/wikidata, the fetches, statements() and
spellings(), and the token alignment, which keeps a written name only
where every word is claimed by exactly one stated part (P735 given,
P734 surname, P5056 patronymic). What this builder adds:

- Selection by script, not by property. A stratum is one country of
  citizenship and one language; its query takes public figures --
  deceased, or with at least MIN_SITELINKS sitelinks -- who state a given
  or family name and carry a label in that language, in MD5 order. A
  text (the person's P1559 in that language, or their label in it) is
  used only if every letter in it is in the stratum's script: `mul`
  labels are Latin, and a Latin text would pass as a Hindi name.
- Unspaced text is aligned by character. A text with no space (most
  Han, kana and Hangul names) is aligned with the same rule over its
  characters: each part's widest occurrence must be its only one, no
  two parts may claim a character, and every character must be
  claimed. No part is inferred: a Chinese item stating only P734 (most
  do) leaves its given name unstated, and the person is not used,
  rather than reading the rest of the text as the given name.
- Feminine surnames, per language. A woman's surname may be written in
  a feminine form of its item's label (Greek `Λελούδα` for `Λελούδας`,
  Bulgarian `-ова`, Ukrainian `-ська`); without these the filter would
  drop women and the sample would skew male. A wrong form costs
  nothing: it matches no word, and the name falls out as before.
- The script decides the order. A Han, kana or Hangul text carries no
  shape: the parser reads those scripts family-first by itself, which
  is what the corpus is for. Any other text is ordered as
  build_wikidata_corpus.py orders it.

A stratum that falls below its floor stops the build before anything is
written, as does a query matching nothing or a response that is not what
was asked for. A stratum's count says what was sampled, not how common
the shape is. Its pool is sized from the yield measured on 2026-10-16;
some pools are the whole population (Thailand, Kazakhstan, Bangladesh),
and their floors are set below the quota for that reason.

--lc-check compares each name, where its item states a Library of
Congress authority id (P244), with the native-script variants (MARC 400
$a) of that LC record, and prints per stratum how many LC confirms and
which it splits differently. LC is a witness, never a source: the check
writes nothing and filters nothing. LC's split is its comma (`הלוי,
אהרן`) or, in CJK, a space (`이 병기`); most Han variants are written
unspaced and give no split. Records are cached under
$NAMEPARSER_TOOLS_CACHE/lc.

Blind to: everything the strict filter drops. Survivors are tidy names
whose every word has a Wikidata item labelled in the script: Arabic
nasab chains (`بن`), `آل` family names and kunyas are missing because
most Arabic items state no family name, so the Arabic rows are mostly
two-word modern names; Chinese rows are names whose given name has an
item, a minority; Japanese given-name items mostly carry kana readings,
so kanji given names are thin; Devanagari, Bengali and Thai items are
mostly labelled in Latin script only, so those strata are small. A
transcribed foreign name written with the 间隔号 (·) never aligns.
Urdu and Marathi are left out: 8 and 5 names of 600 aligned
(2026-10-16). No title, credential or suffix is in any text, and
Wikidata's P734 is a convention, not a fact, where a culture has no
family name (an Arabic nisba such as `البغدادي` is entered as one).
"""
from __future__ import annotations

import argparse
import sys
import unicodedata
import urllib.error
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from collections import Counter
from pathlib import Path
from typing import Any, NamedTuple

# The shared modules, found by putting this directory on sys.path: see
# corpus_build's docstring for why.
_HERE = str(Path(__file__).resolve().parent)
if _HERE not in sys.path:
    sys.path.append(_HERE)

import build_wikidata_corpus as wikidata  # noqa: E402
import corpus_build  # noqa: E402
from corpus_build import corpus_lines, fields_lines  # noqa: E402,F401
from build_wikidata_corpus import align, statements  # noqa: E402

HERE = Path(__file__).resolve().parent
CORPUS = HERE / "corpus_wikidata_native.jsonl"
FIELDS = HERE / "wikidata_native_fields.jsonl"
LICENSE = HERE / "wikidata_native_LICENSE"
LC_RECORD = "https://id.loc.gov/authorities/names/{}.marcxml.xml"
MARC = "{http://www.loc.gov/MARC21/slim}"
#: The parts a native-script name is aligned to. P1950 is Spanish only.
PARTS = {"P735": "given", "P734": "surname", "P5056": "patronymic"}

#: Feminine surname endings, longest first, by language.
_GREEK = (("όπουλος", "οπούλου"), ("ίδης", "ίδου"), ("άδης", "άδου"),
          ("άκης", "άκη"), ("ής", "ή"), ("ης", "η"), ("άς", "ά"), ("ας", "α"),
          ("ός", "ού"), ("ος", "ου"))
_SLAVIC = (("ов", "ова"), ("ев", "ева"), ("ёв", "ёва"), ("ин", "ина"))
_BULGARIAN = (("ски", "ска"), ("цки", "цка"), *_SLAVIC)
_UKRAINIAN = (("ський", "ська"), ("цький", "цька"), ("ін", "іна"), *_SLAVIC)


class Language(NamedTuple):
    #: Label languages a text may come from (P1559 is matched by prefix).
    labels: tuple[str, ...]
    #: Unicode character-name prefixes every letter of a text must have.
    script: tuple[str, ...]
    feminine: tuple[tuple[str, str], ...] = ()
    #: The nameparser.locales pack the locale view also scores it under.
    pack: str | None = None


_HAN = ("CJK UNIFIED", "CJK COMPATIBILITY", "IDEOGRAPHIC")
#: Scripts the parser reads family-first by itself (Policy.script_orders):
#: a text in them carries no shape -- unless it is pure katakana, which
#: the parser leaves to the declared order (a transcribed foreign name).
_SELF_ORDERED = (*_HAN, "HANGUL", "HIRAGANA", "KATAKANA")
LANGUAGES = {
    "ar": Language(("ar",), ("ARABIC",)),
    "fa": Language(("fa",), ("ARABIC",)),
    "he": Language(("he",), ("HEBREW",)),
    "hi": Language(("hi",), ("DEVANAGARI",)),
    "bn": Language(("bn",), ("BENGALI",)),
    "th": Language(("th",), ("THAI",)),
    "el": Language(("el",), ("GREEK",), _GREEK),
    "ka": Language(("ka",), ("GEORGIAN",)),
    "hy": Language(("hy",), ("ARMENIAN",)),
    "ko": Language(("ko",), ("HANGUL",)),
    "ja": Language(("ja",), (*_HAN, "HIRAGANA", "KATAKANA"), pack="JA"),
    "zh": Language(("zh", "zh-hans", "zh-hant", "zh-cn", "zh-tw", "zh-hk"), _HAN,
                   pack="ZH"),
    "uk": Language(("uk",), ("CYRILLIC",), _UKRAINIAN),
    "bg": Language(("bg",), ("CYRILLIC",), _BULGARIAN),
    "sr": Language(("sr", "sr-ec"), ("CYRILLIC",)),
    "kk": Language(("kk", "kk-cyrl"), ("CYRILLIC",), _SLAVIC),
}


class Stratum(NamedTuple):
    label: str
    country: str      # Wikidata item for the country of citizenship (P27)
    language: str     # a LANGUAGES key
    quota: int
    #: How many people the query takes, from the yield measured on
    #: 2026-10-16; a pool short of this is the whole population.
    pool: int
    #: The fewest names the build accepts; below it, it stops. Set below
    #: the quota only where the pool is known to run short.
    least: int | None = None

    @property
    def floor(self) -> int:
        return self.quota if self.least is None else self.least


# The yields in the comments are names kept of 600 pooled, 2026-10-16.
STRATA = (
    Stratum("ko-kr", "Q884", "ko", 120, 300),           # 405
    Stratum("ka-ge", "Q230", "ka", 60, 150),            # 402
    Stratum("sr-rs", "Q403", "sr", 60, 300),            # 192
    Stratum("bg-bg", "Q219", "bg", 60, 300),            # 165
    Stratum("he-il", "Q801", "he", 60, 400),            # 144
    Stratum("ar-sy", "Q858", "ar", 60, 400),            # 145
    Stratum("ar-eg", "Q79", "ar", 60, 450),             # 131
    Stratum("ar-sa", "Q851", "ar", 30, 600, least=25),  # 61
    Stratum("hy-am", "Q399", "hy", 60, 500),            # 106
    Stratum("el-gr", "Q41", "el", 60, 600),             # 84, before feminine forms
    Stratum("ja-jp", "Q17", "ja", 60, 700),             # 85
    Stratum("zh-cn", "Q148", "zh", 50, 800),            # 61
    Stratum("zh-tw", "Q865", "zh", 30, 700, least=25),  # 41
    Stratum("fa-ir", "Q794", "fa", 30, 600, least=25),  # 49
    Stratum("uk-ua", "Q212", "uk", 30, 900, least=25),  # 38, before feminine forms
    Stratum("bn-in", "Q668", "bn", 25, 900, least=20),  # 29
    # The pools below are the whole population on 2026-10-16.
    Stratum("bn-bd", "Q902", "bn", 15, 600, least=12),  # 26 of 563
    Stratum("kk-kz", "Q232", "kk", 15, 600, least=12),  # 22 of 491
    Stratum("hi-in", "Q668", "hi", 15, 1000, least=12),  # 21
    Stratum("th-th", "Q869", "th", 10, 600, least=8),   # 13 of 224
)

LICENSE_TEXT = """\
corpus_wikidata_native.jsonl and wikidata_native_fields.jsonl are derived
from Wikidata (https://www.wikidata.org), read through the Wikidata Query
Service and the wbgetentities API, and carry Wikidata's license.

Wikidata states that "All structured data (i.e. the main, Property,
Lexeme, and EntitySchema namespaces) is released into the public
domain".
https://www.wikidata.org/wiki/Wikidata:Licensing

CC0 1.0 Universal: https://creativecommons.org/publicdomain/zero/1.0/

No attribution is required; this file credits the source anyway.
Source: Wikidata, Wikimedia Foundation. Each line of
wikidata_native_fields.jsonl names its item's QID, resolvable at
https://www.wikidata.org/wiki/<QID>. Only public figures are sampled
(deceased, or with at least 10 sitelinks), and only name strings and
QIDs are kept.
"""


def query(stratum: Stratum) -> str:
    """The stratum's WDQS query: its public figures with a stated given or
    family name and a label in its language, in MD5 order."""
    return f"""SELECT ?item WHERE {{
  ?item wdt:P31 wd:Q5; wdt:P27 wd:{stratum.country}; wdt:P735|wdt:P734 ?part;
        rdfs:label ?own; wikibase:sitelinks ?links.
  FILTER(LANG(?own) = "{LANGUAGES[stratum.language].labels[0]}")
  FILTER(?links >= {wikidata.MIN_SITELINKS} || EXISTS {{ ?item wdt:P570 ?died }})
}} GROUP BY ?item ORDER BY MD5(STR(?item)) LIMIT {stratum.pool}"""


def pool(stratum: Stratum, refresh: bool) -> list[str]:
    """The stratum's QIDs in MD5 order; raises on a query matching
    nothing, since that means the query or Wikidata changed."""
    data = urllib.parse.urlencode({"query": query(stratum), "format": "json"}).encode()
    result = wikidata._fetch(wikidata.SPARQL, data, refresh, "results")
    qids = [b["item"]["value"].rsplit("/", 1)[1] for b in result["results"]["bindings"]]
    if not qids:
        raise ValueError(f"{stratum.label}: the query matches nothing; has a "
                         f"property or item changed?\n{query(stratum)}")
    return qids


def entities(ids: list[str], language: str, refresh: bool) -> dict[str, Any]:
    """wbgetentities for `ids`, with labels in the language's label
    languages and `mul` only."""
    return wikidata.entities(ids, "labels|claims", refresh,
                             (*LANGUAGES[language].labels, "mul"))


def in_script(text: str, script: tuple[str, ...]) -> bool:
    """Whether every letter and mark of `text` is in the script (named by
    Unicode character-name prefixes); spaces, punctuation and joiners are
    not asked. A text with no letter is in no script."""
    letters = [ch for ch in text
               if ch.isalpha() or unicodedata.category(ch).startswith("M")]
    return bool(letters) and all(unicodedata.name(ch, "").startswith(script)
                                 for ch in letters)


def align_chars(text: str,
                parts: list[tuple[str, set[str]]]) -> dict[str, list[int]] | None:
    """align() for a text with no space: each field's character positions,
    or None unless every character is claimed by exactly one part, each
    part matching (at its widest spelling) in one place only."""
    claimed: dict[int, str] = {}
    for field, names in parts:
        spans: set[tuple[int, int]] = set()
        for name in names:
            name = "".join(name.split())
            start = text.find(name) if name else -1
            while start != -1:
                spans.add((start, start + len(name)))
                start = text.find(name, start + 1)
        widest = wikidata._widest(spans)
        if len(widest) > 1:
            return None  # the part matches in two places
        for i, j in widest:
            for k in range(i, j):
                if k in claimed:
                    return None  # two parts claim one character
                claimed[k] = field
    if len(claimed) != len(text):
        return None
    out: dict[str, list[int]] = {}
    for k in sorted(claimed):
        out.setdefault(claimed[k], []).append(k)
    return out


def _texts(person: dict[str, Any], language: Language) -> list[tuple[str, str]]:
    """The person's written names in the language, P1559 first, each as
    (text, its language), whitespace-normalized and deduplicated."""
    found = [(text, lang) for text, lang in statements(person, "P1559")
             if lang.split("-")[0] == language.labels[0].split("-")[0]]
    found += [(wikidata._label(person, lang), lang) for lang in language.labels]
    out: dict[str, str] = {}
    for text, lang in found:
        text = " ".join(text.split())
        if text and text not in out and in_script(text, language.script):
            out[text] = lang
    return list(out.items())


def renderings(qid: str, person: dict[str, Any], names: dict[str, Any],
               stratum: Stratum) -> list[dict[str, Any]]:
    """The fields lines one person contributes: at most one, their first
    written name that aligns with a given name and a surname."""
    language = LANGUAGES[stratum.language]
    female = wikidata.FEMALE in statements(person, "P21")
    for text, lang in _texts(person, language):
        parts: list[tuple[str, set[str]]] = []
        for prop, field in PARTS.items():
            for value in statements(person, prop):
                written = wikidata.spellings(names.get(value, {}),
                                             (lang, *language.labels, "mul"))
                if field == "surname" and female and language.feminine:
                    written |= {f for f in (wikidata.feminine(w, language.feminine)
                                            for w in written) if f}
                parts.append((field, written))
        spaced = len(text.split()) > 1
        aligned = align(text, parts) if spaced else align_chars(text, parts)
        if aligned is None or "given" not in aligned or "surname" not in aligned:
            continue
        if spaced:
            words = [wikidata._word(t) for t in text.split()]
            fields = {f: " ".join(words[k] for k in ks) for f, ks in aligned.items()}
        else:
            fields = {f: "".join(text[k] for k in ks) for f, ks in aligned.items()}
        order, shape = wikidata._order(text, aligned) if spaced else (
            "surnameFirst" if min(aligned["surname"]) == 0 else "givenFirst", None)
        if in_script(text, _SELF_ORDERED) and not in_script(text, ("KATAKANA",)):
            shape = None  # the script decides the order: what is under test
        row = {"file": qid, "label": stratum.label, "order": order, "text": text,
               "shape": shape, "composed": False, "fields": fields}
        if language.pack:
            row["pack"] = language.pack
        return [row]
    return []


def lccn(person: dict[str, Any]) -> str | None:
    """The person's Library of Congress authority id (P244), if stated."""
    ids = [v for v in (claim["mainsnak"].get("datavalue", {}).get("value")
                       for claim in person.get("claims", {}).get("P244", [])
                       if claim.get("rank") != "deprecated")
           if isinstance(v, str)]
    return ids[0] if ids else None


def build(refresh: bool) -> tuple[list[dict[str, Any]], dict[str, str]]:
    """Every stratum's rows, and the LCCN of each person used who states
    one; or ValueError naming each stratum below its floor, raised
    before main() writes anything."""
    rows: list[dict[str, Any]] = []
    lccns: dict[str, str] = {}
    seen: set[str] = set()
    short: list[str] = []
    for stratum in STRATA:
        pooled = pool(stratum, refresh)
        qids = [q for q in pooled if q not in seen]
        people = entities(qids, stratum.language, refresh)
        stale = sorted(q for q in qids if "missing" in people[q])
        if stale:
            raise ValueError(f"{stratum.label}: WDQS pooled items Wikidata reports "
                             f"missing: {', '.join(stale[:10])}; rerun with --refresh")
        parts = {v for p in people.values() for prop in PARTS for v in statements(p, prop)}
        names = entities(sorted(parts), stratum.language, refresh)
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
            if (found := lccn(people[qid])) is not None:
                lccns[qid] = found
            taken += 1
        print(f"{stratum.label:6} {taken:3}/{stratum.quota} names ({refused} refused, "
              f"{len(pooled) - len(qids)} taken by an earlier stratum, "
              f"{len(pooled)} pooled)")
        if taken < stratum.floor:
            short.append(f"{stratum.label} {taken}/{stratum.floor}")
    if short:
        raise ValueError(f"strata below their floor, nothing written: {', '.join(short)}")
    return rows, lccns


# -- the LC cross-check -------------------------------------------------------

def _lc_checked(body: bytes | str, source: str) -> dict[str, Any]:
    """An LC MARC record's 400 $a variants, or ValueError naming the
    source when the body is not a MARC record."""
    try:
        root = ET.fromstring(body)
    except ET.ParseError as error:
        raise ValueError(f"{source} is not MARC XML ({error})") from None
    if not root.tag.endswith("record"):
        raise ValueError(f"{source} is not a MARC record: <{root.tag}>")
    variants = ["".join(sf.text or "" for sf in field.iter(MARC + "subfield")
                        if sf.get("code") == "a").strip(" ,.")
                for field in root.iter(MARC + "datafield") if field.get("tag") == "400"]
    return {"variants": [v for v in variants if v]}


def lc_variants(lccn: str, refresh: bool) -> list[str] | None:
    """The record's 400 $a variants, or None when LC has no such record."""
    url = LC_RECORD.format(urllib.parse.quote(lccn))

    def fetch() -> bytes:
        request = urllib.request.Request(url, headers={"User-Agent": wikidata.USER_AGENT})
        with urllib.request.urlopen(request, timeout=60) as response:
            body: bytes = response.read()
        wikidata.time.sleep(1)
        return body
    try:
        record = corpus_build.cached_json(corpus_build.cache_dir("lc"), url, url,
                                          fetch, _lc_checked, refresh)
    except urllib.error.HTTPError as error:
        if error.code == 404:
            return None
        raise
    return list(record["variants"])


def _squash(text: str) -> str:
    return "".join(text.replace(",", " ").replace("،", " ").split())


def lc_split(row: dict[str, Any], variants: list[str]) -> tuple[str, str] | None:
    """LC's (family, rest) for the rendering: from a variant that writes
    the same letters with a comma (`הלוי, אהרן` for `אהרן הלוי`), or, for a text with no
    space, with one space (`이 병기`); None when no variant gives one."""
    whole = _squash(row["text"])
    for variant in variants:
        for mark in (",", "،"):
            if mark in variant:
                family, _, rest = variant.partition(mark)
                # inverted, so the text may write the parts either way round
                if whole in (_squash(family + rest), _squash(rest + family)):
                    return _squash(family), _squash(rest)
        words = variant.split()
        if " " not in row["text"] and len(words) == 2 and _squash(variant) == whole:
            return words[0], words[1]
    return None


def lc_check(rows: list[dict[str, Any]], lccns: dict[str, str], refresh: bool) -> None:
    """Print, per stratum, how often LC's split agrees with Wikidata's."""
    tally: dict[str, Counter[str]] = {}
    differ: list[str] = []
    for row in rows:
        counts = tally.setdefault(row["label"], Counter())
        counts["names"] += 1
        if row["file"] not in lccns:
            continue
        counts["with an LCCN"] += 1
        variants = lc_variants(lccns[row["file"]], refresh)
        split = lc_split(row, variants or [])
        if split is None:
            continue
        counts["LC splits it"] += 1
        fields = row["fields"]
        ours = (_squash(fields["surname"]),
                _squash(" ".join(v for f, v in fields.items() if f != "surname")))
        if split == ours:
            counts["agree"] += 1
        else:
            differ.append(f"  {row['file']} {row['text']!r}: Wikidata {ours}, "
                          f"LC {split} (lccn {lccns[row['file']]})")
    for label, counts in tally.items():
        print(f"{label:6} " + ", ".join(f"{k} {counts[k]}" for k in
                                        ("names", "with an LCCN", "LC splits it", "agree")))
    print(f"{len(differ)} split differently:", *differ, sep="\n")


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--refresh", action="store_true",
                    help="fetch from Wikidata (and LC) again instead of reading the cache")
    ap.add_argument("--lc-check", action="store_true",
                    help="also compare each name with its Library of Congress record")
    args = ap.parse_args()
    rows, lccns = build(args.refresh)
    corpus_build.write_corpus(rows, CORPUS, FIELDS)
    LICENSE.write_text(LICENSE_TEXT, encoding="utf-8")
    print(f"Wikidata native: {len(rows)} renderings; wrote {CORPUS.name}, "
          f"{FIELDS.name}, {LICENSE.name}")
    if args.lc_check:
        lc_check(rows, lccns, args.refresh)


if __name__ == "__main__":
    main()
