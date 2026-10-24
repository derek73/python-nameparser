"""Regenerate the native-script Wikidata corpus: real names in their own scripts.

A corpus with its own provenance (the roster, with each file's source and
blind spot, is the table in tools/differential/README.md). Every other
real-name corpus is Latin script but for Wikidata's Russian patronymics,
and CLDR's native-script names are fictional, so the parser's
script-conditional readings -- family-first order for Han, Hangul and
kana, Korean surname segmentation -- had been tested against no real
name. It holds no honorific, so it does not exercise the CJK honorific
peel; it shows only that the peel leaves plain names alone. This corpus holds real names as Wikidata writes
them in Arabic (with Persian and Urdu), Hebrew, Devanagari (Hindi,
Marathi and Nepali), Bengali, Thai, Greek, Georgian, Armenian, Hangul,
Han and kana, and Cyrillic beyond Russian. Wikidata is
CC0.

    uv run python tools/differential/build_wikidata_native_corpus.py
    uv run python tools/differential/build_wikidata_native_corpus.py --refresh
    uv run python tools/differential/build_wikidata_native_corpus.py --lc-check

Writes three files beside this script, always together:

- corpus_wikidata_native.jsonl -- one line per distinct (rendering,
  shape), read by snapshot.py like every other corpus.
- wikidata_native_fields.jsonl -- one line per rendering, in
  build_wikidata_corpus.py's field vocabulary (`given`, `surname`,
  `patronymic`), scored by cldr_agreement.py, which also scores the
  Han and kana strata under their locale packs (its NATIVE_LABELS).
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
  used only if every letter and combining mark in it is in the
  stratum's script (digits and punctuation are not asked): `mul`
  labels are Latin, and a Latin text would pass as a Hindi name.
- Unspaced text is aligned by character. A Han, kana or Hangul text
  with no space (most of them) is aligned with the same rule over its
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
  is what the corpus is for. Pure katakana, which the parser leaves to
  the declared order, and any other text are ordered by where the
  surname stands, as build_wikidata_corpus.py orders them.

A stratum that falls below its floor stops the build before anything is
written, as does a query matching nothing or a response that is not what
was asked for. A stratum's count says what was sampled, not how common
the shape is. Its pool is sized from the yield measured on 2026-10-16
(2026-10-23 for the Hindi, Marathi, Urdu and Nepali strata).
Where the yield was thin (under about two and a half times the quota),
or the pool is the whole population (Thailand, Kazakhstan, Bangladesh,
Hindi in India, Urdu in Pakistan, Nepal),
the floor is set below the quota, leaving a margin a re-pool may lose.
A pool short of its size stops the build unless the stratum is marked
as its whole population, and so does a stratum so marked whose pool
comes back full, since its population has then outgrown the mark.

--lc-check compares each name, where its item states a Library of
Congress authority id (P244), with the native-script variants (MARC 400
$a) of that LC record, and prints per stratum how many LC confirms and
which it splits differently. LC is a witness, never a source: the check
runs after the build has written its files, and adds nothing to them and
filters nothing from them. LC's split is its comma (`הלוי,
אהרן`) or, in CJK, a space (`이 병기`); most Han variants are written
unspaced and give no split. Records are cached under
$NAMEPARSER_TOOLS_CACHE/lc; an LCCN LC no longer has (HTTP 404) is
counted as such and not cached.

Blind to: everything the strict filter drops. Survivors are tidy names
whose every word has a Wikidata item labelled in the script. Arabic
nasab chains never align, since `بن` is not a connective in Arabic
script, and `آل` family names and kunyas are missing because most
Arabic items state no family name, so the Arabic rows are mostly
two-word modern names; Chinese rows are names whose given name has an
item, a minority; most Japanese items are refused because the
given-name item holds only a kana reading; Devanagari, Bengali, Urdu
and Thai items are mostly labelled in Latin script only, so those
strata are small: Hindi's whole population of 4,806 yields 147 in build
order, and Dari in Afghanistan, left out, 4 of 291 (2026-10-23). A transcribed foreign name written with the 间隔号
(·) never aligns. No title, credential or suffix is in any text, and
Wikidata's P734 is a convention, not a fact, where a culture has no
family name (an Arabic nisba such as `البغدادي` is entered as one).
"""
from __future__ import annotations

import argparse
import sys
import unicodedata
import urllib.error
import urllib.parse
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
    #: Unicode character-name prefixes every letter and combining mark of
    #: a text must have.
    script: tuple[str, ...]
    feminine: tuple[tuple[str, str], ...] = ()


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
    "mr": Language(("mr",), ("DEVANAGARI",)),
    "ne": Language(("ne",), ("DEVANAGARI",)),
    "ur": Language(("ur",), ("ARABIC",)),
    "bn": Language(("bn",), ("BENGALI",)),
    "th": Language(("th",), ("THAI",)),
    "el": Language(("el",), ("GREEK",), _GREEK),
    "ka": Language(("ka",), ("GEORGIAN",)),
    "hy": Language(("hy",), ("ARMENIAN",)),
    "ko": Language(("ko",), ("HANGUL",)),
    "ja": Language(("ja",), (*_HAN, "HIRAGANA", "KATAKANA")),
    "zh": Language(("zh", "zh-hans", "zh-hant", "zh-cn", "zh-tw", "zh-hk"), _HAN),
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
    #: How many people the query takes, sized from the yield measured on
    #: 2026-10-16 (2026-10-23 for the strata a STRATA comment so dates).
    pool: int
    #: The fewest names the build accepts; below it, it stops. Set below
    #: the quota where the yield is thin enough that a re-pool could
    #: fall short, or the pool is the whole population.
    least: int | None = None
    #: Whether the query's whole population is smaller than `pool`. A
    #: pool short of `pool` stops the build unless this is set: a query
    #: that suddenly matches less would otherwise drift the sample unseen.
    whole: bool = False

    @property
    def floor(self) -> int:
        return self.quota if self.least is None else self.least


# The yields in the comments are names kept of 600 pooled, 2026-10-16,
# unless the comment gives another denominator.
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
    # The four India strata share their people: each takes no one an
    # earlier one took. Yields measured 2026-10-23 in build order with no
    # quota cap; hi-in's pool is the whole population, and ur-in's yield
    # is its quota, the floor its only margin.
    Stratum("hi-in", "Q668", "hi", 60, 5000, least=50, whole=True),  # 147 of 4806
    Stratum("mr-in", "Q668", "mr", 30, 3000, least=25),  # 40 of 3000
    Stratum("ur-in", "Q668", "ur", 12, 3000, least=10),  # 12 of 3000
    # The pools below are the whole population on 2026-10-16.
    Stratum("bn-bd", "Q902", "bn", 15, 600, least=12, whole=True),  # 26 of 563
    Stratum("kk-kz", "Q232", "kk", 15, 600, least=12, whole=True),  # 22 of 491
    Stratum("th-th", "Q869", "th", 10, 600, least=8, whole=True),   # 13 of 224
    # The whole population on 2026-10-23, yields measured with no quota cap.
    Stratum("ur-pk", "Q843", "ur", 20, 1600, least=15, whole=True),  # 24 of 1456
    Stratum("ne-np", "Q837", "ne", 10, 200, least=8, whole=True),    # 12 of 170
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
    """The stratum's QIDs in MD5 order."""
    return wikidata.pooled(stratum.label, query(stratum), stratum.pool,
                           stratum.whole, refresh)


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
    def spans(names: set[str]) -> set[tuple[int, int]]:
        found: set[tuple[int, int]] = set()
        for name in names:
            name = "".join(name.split())
            start = text.find(name) if name else -1
            while start != -1:
                found.add((start, start + len(name)))
                start = text.find(name, start + 1)
        return found
    claimed = wikidata.claim([(field, spans(names)) for field, names in parts])
    if claimed is None or len(claimed) != len(text):
        return None
    return wikidata.by_field(claimed)


def script_orders(text: str) -> bool:
    """Whether the parser reads `text` family-first by its script alone:
    Han, kana or Hangul, but not pure katakana."""
    return in_script(text, _SELF_ORDERED) and not in_script(text, ("KATAKANA",))


def _texts(person: dict[str, Any], language: Language) -> list[tuple[str, str]]:
    """The person's written names in the language that are in its script,
    P1559 first, each as (text, its language), whitespace-normalized and
    deduplicated."""
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
        # Only Han, kana and Hangul are written unspaced; a one-word text
        # in another script is word-aligned, and so never splits a word.
        by_char = len(text.split()) == 1 and in_script(text, _SELF_ORDERED)
        aligned = align_chars(text, parts) if by_char else align(text, parts)
        if aligned is None or "given" not in aligned or "surname" not in aligned:
            continue
        units, joint = (text, "") if by_char else (
            [wikidata._word(t) for t in text.split()], " ")
        fields = {f: joint.join(units[k] for k in ks) for f, ks in aligned.items()}
        order, shape = wikidata._order(text, aligned)
        if script_orders(text):
            shape = None  # the script decides the order: what is under test
        return [{"file": qid, "label": stratum.label, "order": order, "text": text,
                 "shape": shape, "composed": False, "fields": fields}]
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
    one. The loop is `wikidata.build_strata`, shared with the parent
    builder. Raises ValueError, before main() writes anything, naming
    each stratum below its floor, or on a pooled person Wikidata reports
    missing, or (from pool()) on a pool that is empty or the wrong size."""
    lccns: dict[str, str] = {}

    def keep(qid: str, person: dict[str, Any]) -> None:
        if (found := lccn(person)) is not None:
            lccns[qid] = found
    rows = wikidata.build_strata(
        STRATA, props=PARTS, label_width=6, refresh=refresh, pool=pool,
        entities=lambda ids, stratum, refresh: entities(ids, stratum.language, refresh),
        renderings=renderings, keep=keep)
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
        return corpus_build.fetch_bytes(url, user_agent=wikidata.USER_AGENT,
                                        timeout=60, delay=1)
    try:
        record = corpus_build.cached_json(corpus_build.cache_dir("lc"), url, url,
                                          fetch, _lc_checked, refresh)
    except urllib.error.HTTPError as error:
        if error.code == 404:
            error.close()  # it holds the response; unclosed, 3.14 warns
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
        family, comma, rest = variant.replace("،", ",").partition(",")
        # inverted, so the text may write the parts either way round
        if comma and whole in (_squash(family + rest), _squash(rest + family)):
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
        if variants is None:
            counts["no LC record"] += 1  # a stale P244
            continue
        split = lc_split(row, variants)
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
                                        ("names", "with an LCCN", "no LC record",
                                         "LC splits it", "agree")))
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
