"""Which names two or more parser configurations read differently, in one tree, in parallel.

snapshot.py compares two TREES under one configuration and
local_agreement.py scores one configuration against filed boxes; this
compares CONFIGURATIONS within the tree it runs in, the measurement a
vocabulary or language-choice change keeps needing (#1000's four
lexicons, #1005's strict losses, a reviewer's grid of choices):

    uv run python tools/differential/config_diff.py diff default strict:pt
    uv run python tools/differential/config_diff.py diff plain:ES strict:ES+en \\
        --local orcid-researchers --group ES --group MX
    uv run python tools/differential/config_diff.py diff default \\
        'expr:Parser(lexicon=Lexicon.default().remove("phd", kind="credential"))' \\
        --local all --match '(?i)\\bph\\.? ?d\\b' --sample 10
    uv run python tools/differential/config_diff.py gaps pt pt-BR vi --top 15

**Configurations** (SPEC). `default` is `Parser()`. `plain:<items>` and
`strict:<items>` are `parser_for(*items)` and `parser_for(*items,
strict=True)`, the items joined by `+`: an item in capitals is the
shipped pack of that name (`ES`, `PT_BR`, `ZH`, `locales.ES`), one in
lower case a bare choice of that language tag (`Locale(code=tag,
lexicon=Lexicon.empty(), languages={tag})`, `pt-BR` included).
`expr:<python>` evaluates an expression returning a `Parser`, with
`Parser`, `Policy`, `Lexicon`, `Locale`, `locales`, `parser_for` and
`bare(tag)` in scope. The first configuration is the baseline, each
other compared with it.

**Inputs.** `--committed` reads the committed `corpus*.jsonl` beside
this file (snapshot.corpus_entries, each name under its shape's order);
`--local SOURCE` (repeatable, or `all`) a fetched local corpus's
distinct names. With neither, the committed corpora. `--group` keeps a
fielded local corpus's records of that country or nationality
(local_agreement.FIELDED names the key), `--match` the names a regular
expression finds, `--sample N` one name in N (snapshot.sampled, by a
hash of the name, so a sample is the same in every tree and run).

**What is compared**: the seven role fields and the ambiguity kinds.
The report, per configuration against the baseline: how many names
moved, per input; the moves grouped by which fields changed, with
examples; and the words whose token changed role, ranked, each with its
commonest move and an example. A name whose tokens differ between the
two parses (a choice that splits a word) has no per-word move and is
counted under RETOKENIZED. `--json` writes every count and every moved
name's readings, `--readings` every name's, one JSON line a name in
sorted order, so a run in each of two trees (a word moved between
files, say) compares line by line.

**gaps**: the strict-gap report. For each language tag a choice can name
(every vocabulary file but `mul` and `und`, the shipped packs riding on
their tags, packs_for), over the records of the countries the language
is written in (WRITTEN_IN) from the three fielded local corpora that
record one (ORCID by country of affiliation, PatentsView by the
inventor's country, PSC by nationality), the plain choice against the
strict one, each scored against the filed boxes (local_agreement.read):
a record is BROKEN where the plain choice agrees with the boxes and the
strict one does not, FIXED the other way round, CHANGED where the two
parses differ. Each changed record is laid to the words in it that the
two lexicons read differently (changed_words), ranked per language by
records broken, each with the sets it leaves or joins, its commonest
role move and an example; a changed record holding none is counted
under NO_WORD, which should stay near empty. ORCID records a country
of affiliation, not a language, and PSC is a UK register whose filers
write `Ms` and `Miss` whatever their nationality, so a language's
strict choice is measured on the population a caller who chose it for
that country would face. The records whose given box opens with a word
the default lists as a title are left out of ORCID and PatentsView (a
holder's `Dr` typed as a given name is evidence of nothing; the
2026-10-30 entry of decisions/vocabulary-model filtered so); PSC's are
set aside by local_agreement.read with the default's title words, the
same records in every column. Each group is its first --cap records in
raw.jsonl's order.

WRITTEN_IN, the country each language is written in, is a measurement
aid read by this report and nothing else: decisions/vocabulary-model
forbids the parser any table from country to language. A country
writing several languages (IN, ES, BE, NG) stands under each; a tag
with no country of its own (`bo`, `yi`) has none and is reported as
unmeasured.

Every parse runs in --jobs spawned worker processes (snapshot.parallel,
default every CPU), each building a configuration once from its spec
and refusing a nameparser from outside this tree. The output quotes
names; keep it out of the tree.
"""
from __future__ import annotations

import argparse
import dataclasses
import json
import os
import re
import sys
import warnings
from collections import Counter, defaultdict
from collections.abc import Iterable, Sequence
from pathlib import Path
from typing import TYPE_CHECKING, Any, NamedTuple

if TYPE_CHECKING:
    from nameparser import Lexicon, Locale, ParsedName, Parser

HERE = Path(__file__).resolve().parent
if str(HERE) not in sys.path:
    sys.path.append(str(HERE))
import local_agreement  # noqa: E402
import local_corpora  # noqa: E402
import snapshot  # noqa: E402

ROLES = snapshot.V2_FIELDS
#: Where a moved name whose two parses hold different tokens is tallied.
RETOKENIZED = "(retokenized)"
#: Where a changed gaps record holding no word the lexicons read
#: differently is counted.
NO_WORD = "(no word)"
ORCID = "orcid-researchers"
PATENTSVIEW = "patentsview-inventors"
PSC = "psc-individuals"


# --- configurations ---------------------------------------------------------

def bare(tag: str) -> Locale:
    from nameparser import Lexicon, Locale
    return Locale(code=tag, lexicon=Lexicon.empty(), languages=frozenset({tag}))


def _item(item: str) -> Locale:
    from nameparser import locales
    name = item.removeprefix("locales.")
    if name.isupper():
        if name.lower() not in locales.available():
            raise ValueError(f"{item!r} is no shipped pack; packs: "
                             f"{', '.join(c.upper() for c in locales.available())}")
        return locales.get(name.lower())
    if not name:
        raise ValueError("an empty item in a configuration")
    return bare(name)


def build(spec: str) -> Parser:
    """The Parser a configuration names (see the module docstring)."""
    from nameparser import Lexicon, Locale, Parser, Policy, locales, parser_for
    kind, _, rest = spec.partition(":")
    if spec == "default":
        return Parser()
    if kind in ("plain", "strict") and rest:
        packs = [_item(i) for i in rest.split("+")]
        with warnings.catch_warnings():
            # A pack whose script needs a segmenter (locales.JA) warns
            # without one; the vocabulary is what is compared here.
            warnings.filterwarnings("ignore", message=".*segment", category=UserWarning)
            return parser_for(*packs, strict=kind == "strict")
    if kind == "expr" and rest:
        scope = {"Parser": Parser, "Policy": Policy, "Lexicon": Lexicon, "Locale": Locale,
                 "locales": locales, "parser_for": parser_for, "bare": bare}
        parser = eval(rest, scope)  # noqa: S307 -- the caller's own expression
        if not isinstance(parser, Parser):
            raise ValueError(f"{spec!r} evaluates to {type(parser).__name__}, not a Parser")
        return parser
    raise ValueError(f"{spec!r} is no configuration: write default, plain:<items>, "
                     f"strict:<items> (items joined by '+', a pack in capitals, a "
                     f"language tag in lower case) or expr:<python>")


# --- reading, in a worker -----------------------------------------------------

class Reading(NamedTuple):
    """One name under one configuration: its seven role fields, its
    ambiguity kinds, and each token's text and role."""
    fields: tuple[str, ...]
    kinds: tuple[str, ...]
    tokens: tuple[tuple[str, str], ...]


#: The parsers a worker has built, by (spec, order): a worker keeps its
#: configurations across the chunks it is handed.
_BUILT: dict[tuple[str, str | None], Parser] = {}


def _parser(spec: str, order: str | None) -> Parser:
    key = (spec, order)
    if key not in _BUILT:
        parser = build(spec)
        if order is not None:
            import nameparser
            parser = dataclasses.replace(parser, policy=dataclasses.replace(
                parser.policy, name_order=getattr(nameparser, order)))
        _BUILT[key] = parser
    return _BUILT[key]


def reading(parsed: ParsedName) -> Reading:
    return Reading(tuple(str(getattr(parsed, f) or "") for f in ROLES),
                   tuple(sorted({a.kind.name for a in parsed.ambiguities})),
                   tuple((t.text, str(t.role or "")) for t in parsed.tokens))


def _read_chunk(items: Sequence[tuple[str, str | None, tuple[str, ...]]]
                ) -> tuple[str, list[tuple[Reading, ...]]]:
    """The nameparser this process imported, and every item's readings,
    one per spec it names."""
    import nameparser
    return nameparser.__file__, [
        tuple(reading(_parser(spec, order).parse(text)) for spec in specs)
        for text, order, specs in items]


def read(items: list[tuple[str, str | None, tuple[str, ...]]], jobs: int
         ) -> list[tuple[Reading, ...]]:
    return snapshot.parallel(_read_chunk, items, jobs, module="config_diff")


# --- comparing two readings -------------------------------------------------------

def fold(text: str) -> str:
    """A token as the vocabulary looks it up: folded, edge periods gone."""
    from nameparser._lexicon import _normalize
    return _normalize(text)


def changed_fields(a: Reading, b: Reading) -> tuple[str, ...]:
    moved = tuple(f for f, x, y in zip(ROLES, a.fields, b.fields) if x != y)
    return moved + (("ambiguities",) if a.kinds != b.kinds else ())


def word_moves(a: Reading, b: Reading) -> list[tuple[str, str]]:
    """Each word whose token changed role, with its move (`title->given`);
    [(RETOKENIZED, "")] where the two parses hold different tokens."""
    if [t for t, _ in a.tokens] != [t for t, _ in b.tokens]:
        return [(RETOKENIZED, "")]
    return [(fold(t), f"{r or 'none'}->{s or 'none'}")
            for (t, r), (_, s) in zip(a.tokens, b.tokens) if r != s]


@dataclasses.dataclass
class Tally:
    """One configuration's moves against the baseline."""
    moved: Counter[str] = dataclasses.field(default_factory=Counter)  # by input
    total: Counter[str] = dataclasses.field(default_factory=Counter)
    by_fields: dict[tuple[str, ...], list[str]] = dataclasses.field(
        default_factory=lambda: defaultdict(list))
    words: Counter[str] = dataclasses.field(default_factory=Counter)
    word_move: dict[str, Counter[str]] = dataclasses.field(
        default_factory=lambda: defaultdict(Counter))
    word_example: dict[str, str] = dataclasses.field(default_factory=dict)


def tally(names: Sequence[tuple[str, str | None, frozenset[str]]],
          readings: Sequence[tuple[Reading, ...]], n_specs: int) -> list[Tally]:
    """Per non-baseline configuration, its moves against reading 0."""
    out = [Tally() for _ in range(n_specs - 1)]
    for (text, _order, inputs), rs in zip(names, readings):
        for t, other in zip(out, rs[1:]):
            for i in inputs:
                t.total[i] += 1
            fields = changed_fields(rs[0], other)
            if not fields:
                continue
            for i in inputs:
                t.moved[i] += 1
            t.by_fields[fields].append(text)
            for word in dict.fromkeys(w for w, _ in word_moves(rs[0], other)):
                t.words[word] += 1
                t.word_example.setdefault(word, text)
            for word, move in word_moves(rs[0], other):
                t.word_move[word][move] += 1
    return out


def format_tally(spec: str, base: str, t: Tally, top: int) -> list[str]:
    lines = [f"== {spec} against {base}: {sum(len(v) for v in t.by_fields.values()):,} "
             f"names moved"]
    for i in sorted(t.total):
        lines.append(f"   {i}: {t.moved[i]:,} of {t.total[i]:,}")
    lines.append("   by changed fields:")
    for fields, texts in sorted(t.by_fields.items(), key=lambda kv: (-len(kv[1]), kv[0])):
        lines.append(f"     {', '.join(fields)}: {len(texts):,}  e.g. "
                     + "; ".join(texts[:3]))
    lines.append(f"   words whose role changed (names; commonest move; example), top {top}:")
    for word, n in sorted(t.words.items(), key=lambda kv: (-kv[1], kv[0]))[:top]:
        move = t.word_move[word].most_common(1)[0][0] if t.word_move[word] else ""
        lines.append(f"     {word:14} {n:6,}  {move:20} e.g. {t.word_example[word]}")
    return lines


# --- inputs -----------------------------------------------------------------

def local_names(source: str, groups: Sequence[str]) -> list[str]:
    """A fetched local corpus's names: every distinct one, or with
    `groups` those of a fielded corpus's records in them."""
    fielded = local_agreement.FIELDED.get(source)
    if groups and fielded is None:
        raise SystemExit(f"--group needs a fielded corpus ({', '.join(local_agreement.FIELDED)}),"
                         f" not {source}")
    corpus = local_corpora.require(source)
    if not groups or fielded is None:
        return list(dict.fromkeys(json.loads(line) for line in snapshot.jsonl_lines(
            local_corpora.corpus_path(source).read_text(encoding="utf-8"))))
    wanted = set(groups)
    return list(dict.fromkeys(r["name"] for r in local_agreement.records(corpus)
                              if r.get(fielded.group, "") in wanted))


def gather(args: argparse.Namespace) -> list[tuple[str, str | None, frozenset[str]]]:
    """Every (name, order) the inputs hold, each with the inputs holding it."""
    found: dict[tuple[str, str | None], set[str]] = defaultdict(set)
    sources = (list(local_corpora.SOURCES) if args.local == ["all"] else args.local or [])
    if args.committed or not sources:
        for text, order in snapshot.corpus_entries():
            found[(text, order)].add("committed")
    for source in sources:
        if source == "all" or source not in local_corpora.SOURCES:
            raise SystemExit(f"--local {source}: not a local corpus; "
                             f"{', '.join(local_corpora.SOURCES)} or all")
        if local_corpora.load(source) is None and args.local == ["all"]:
            print(f"(not fetched, skipped: {source})")
            continue
        for text in local_names(source, args.group):
            found[(text, None)].add(source)
    pattern = re.compile(args.match) if args.match else None
    entries = [e for e in found if pattern is None or pattern.search(e[0])]
    if args.sample:
        entries = snapshot.sampled(entries, args.sample)
    return [(text, order, frozenset(found[(text, order)])) for text, order in entries]


# --- gaps ----------------------------------------------------------------

class Where(NamedTuple):
    """Where a language is written: ISO 3166 codes for ORCID and
    PatentsView, PSC nationalities as the register spells them."""
    countries: tuple[str, ...] = ()
    nationalities: tuple[str, ...] = ()


#: The countries each language tag is written in, for the gaps report
#: only. A choosable tag missing here fails test_config_diff, so a new
#: vocabulary file earns a row, empty where no country writes it.
WRITTEN_IN: dict[str, Where] = {
    "ak": Where(("GH",), ("Ghanaian",)),
    "am": Where(("ET",), ()),
    "ar": Where(("EG", "SA", "IQ", "JO", "DZ", "MA"),
                ("Moroccan", "Egyptian", "Iraqi", "Syrian", "Algerian", "Jordanian",
                 "Saudi Arabian", "Lebanese", "Sudanese", "Tunisian", "Yemeni")),
    "as": Where(("IN",), ("Indian",)),
    "be": Where(("BY",), ("Belarusian",)),
    "bg": Where(("BG",), ("Bulgarian",)),
    "bin": Where(("NG",), ("Nigerian",)),
    "bn": Where(("BD",), ("Bangladeshi",)),
    "bo": Where(),
    "bs": Where(("BA",), ()),
    "ca": Where(("ES", "AD"), ("Spanish",)),
    "cs": Where(("CZ",), ("Czech",)),
    "da": Where(("DK",), ("Danish",)),
    "de": Where(("DE", "AT", "CH"), ("German", "Austrian", "Swiss")),
    "el": Where(("GR", "CY"), ("Greek", "Cypriot")),
    "en": Where(("GB", "US", "AU", "NZ", "IE", "CA"),
                ("British", "English", "Scottish", "Welsh", "Northern Irish", "Irish",
                 "American", "Australian", "Canadian", "New Zealander")),
    "es": Where(("ES", "MX", "AR", "CO", "CL", "PE", "EC", "CU", "VE"),
                ("Spanish", "Mexican", "Colombian", "Argentine", "Venezuelan", "Chilean")),
    "et": Where(("EE",), ("Estonian",)),
    "fa": Where(("IR", "AF"), ("Iranian", "Afghan")),
    "ff": Where(("SN", "GN"), ()),
    "fi": Where(("FI",), ("Finnish",)),
    "fil": Where(("PH",), ("Filipino",)),
    "fr": Where(("FR", "BE"), ("French", "Belgian")),
    "ga": Where(("IE",), ("Irish",)),
    "gd": Where((), ("Scottish",)),
    "gu": Where(("IN",), ("Indian",)),
    "ha": Where(("NG", "NE"), ("Nigerian",)),
    "he": Where(("IL",), ("Israeli",)),
    "hi": Where(("IN",), ("Indian",)),
    "hr": Where(("HR",), ("Croatian",)),
    "hu": Where(("HU",), ("Hungarian",)),
    "hy": Where(("AM",), ()),
    "id": Where(("ID",), ("Indonesian",)),
    "is": Where(("IS",), ()),
    "it": Where(("IT",), ("Italian",)),
    "ja": Where(("JP",), ("Japanese",)),
    "ka": Where(("GE",), ("Georgian",)),
    "kk": Where(("KZ",), ("Kazakh",)),
    "km": Where(("KH",), ()),
    "kn": Where(("IN",), ("Indian",)),
    "ko": Where(("KR",), ("South Korean",)),
    "kok": Where(("IN",), ("Indian",)),
    "lo": Where(("LA",), ()),
    "lt": Where(("LT",), ("Lithuanian",)),
    "lv": Where(("LV",), ("Latvian",)),
    "mi": Where(("NZ",), ("New Zealander",)),
    "mk": Where(("MK",), ()),
    "ml": Where(("IN",), ("Indian",)),
    "mn": Where(("MN",), ()),
    "mr": Where(("IN",), ("Indian",)),
    "ms": Where(("MY", "BN", "SG"), ("Malaysian", "Singaporean")),
    "my": Where(("MM",), ()),
    "nb": Where(("NO",), ("Norwegian",)),
    "ne": Where(("NP",), ("Nepalese",)),
    "nl": Where(("NL", "BE"), ("Dutch", "Belgian")),
    "nn": Where(("NO",), ("Norwegian",)),
    "or": Where(("IN",), ("Indian",)),
    "pa": Where(("IN", "PK"), ("Indian", "Pakistani")),
    "pl": Where(("PL",), ("Polish",)),
    "pt": Where(("PT", "AO", "MZ"), ("Portuguese",)),
    "pt-BR": Where(("BR",), ("Brazilian",)),
    "ro": Where(("RO", "MD"), ("Romanian", "Moldovan")),
    "ru": Where(("RU", "BY", "KZ"), ("Russian",)),
    "sd": Where(("PK",), ("Pakistani",)),
    "shn": Where(("MM",), ()),
    "si": Where(("LK",), ("Sri Lankan",)),
    "sk": Where(("SK",), ("Slovak",)),
    "sl": Where(("SI",), ("Slovenian",)),
    "sr": Where(("RS", "ME", "BA"), ("Serbian",)),
    "sv": Where(("SE",), ("Swedish",)),
    "sw": Where(("KE", "TZ"), ("Kenyan", "Tanzanian")),
    "ta": Where(("IN", "LK"), ("Indian", "Sri Lankan")),
    "te": Where(("IN",), ("Indian",)),
    "th": Where(("TH",), ("Thai",)),
    "ti": Where(("ER", "ET"), ("Eritrean",)),
    "tr": Where(("TR", "AZ"), ("Turkish", "Azerbaijani")),
    "uk": Where(("UA",), ("Ukrainian",)),
    "ur": Where(("PK",), ("Pakistani",)),
    "vi": Where(("VN",), ("Vietnamese",)),
    "yi": Where(),
    "yo": Where(("NG", "BJ"), ("Nigerian", "Beninese")),
    "zh": Where(("CN", "TW", "HK", "SG"),
                ("Chinese", "Taiwanese", "Hong Konger", "Singaporean")),
    "zu": Where(("ZA",), ("South African",)),
}

#: How each fielded source names its groups: the record key, and
#: WRITTEN_IN's field read for it.
GAP_SOURCES = ((ORCID, "country", "countries"), (PATENTSVIEW, "country", "countries"),
               (PSC, "nationality", "nationalities"))
#: Records per (source, group), the first in raw.jsonl's order; ORCID's
#: and PatentsView's caches hold at most 20,000 a country.
CAP = 20_000


def choosable() -> list[str]:
    """Every tag a choice can name: each vocabulary file but `mul`/`und`."""
    from nameparser import _reading_index
    return sorted(_reading_index.files() - _reading_index.UNCHOOSABLE)


def _pack_tag(code: str) -> str | None:
    """The tag a pack choosing no language rides on: its code where that
    is a tag (`zh`, `ja`, `ru`), else the code's language (`tr_az`)."""
    from nameparser import _reading_index
    for tag in (code.replace("_", "-"), code.split("_")[0]):
        if tag in _reading_index.files():
            return tag
    return None


def gap_specs(tag: str) -> tuple[str, str]:
    """The plain and strict configurations of `tag`: the shipped packs
    choosing it, or else the packs choosing no language whose code is
    it stacked with the bare tag (a strict call needs a language), or
    else the bare tag. A file holding no reading is refused as a plain
    choice (it would change nothing), so its plain side is the default."""
    from nameparser import _reading_index, locales
    packs = [locales.get(c) for c in sorted(locales.available())]
    items = [p.code.upper() for p in packs if tag in p.languages]
    if not items:
        items = [p.code.upper() for p in packs
                 if not p.languages and _pack_tag(p.code) == tag] + [tag]
    joined = "+".join(items)
    return (f"plain:{joined}" if tag in _reading_index.tags() else "default",
            f"strict:{joined}")


def _set_fields(lexicon: Lexicon) -> dict[str, frozenset[str]]:
    sets = lexicon._sets
    names = ([f.name for f in dataclasses.fields(sets)] if dataclasses.is_dataclass(sets)
             else list(type(sets).__slots__))
    return {name: getattr(sets, name) for name in names}


def changed_words(plain: Lexicon, strict: Lexicon) -> dict[str, tuple[tuple[str, ...], tuple[str, ...]]]:
    """Each word some vocabulary set holds under one lexicon and not
    the other: the sets it is in only under `plain`, and only under
    `strict`."""
    a, b = _set_fields(plain), _set_fields(strict)
    lost: dict[str, list[str]] = defaultdict(list)
    gained: dict[str, list[str]] = defaultdict(list)
    for field in a:
        for word in a[field] - b[field]:
            lost[word].append(field)
        for word in b[field] - a[field]:
            gained[word].append(field)
    return {w: (tuple(lost.get(w, ())), tuple(gained.get(w, ())))
            for w in sorted(lost.keys() | gained.keys())}


def words_in(tokens: Sequence[tuple[str, str]], words: Iterable[str] | dict[str, Any]
             ) -> list[tuple[str, int]]:
    """The words of `words` in a reading's tokens, each with the index of
    the token it starts at, matched folded and with every period removed
    (as an acronym is); a two-word entry (a title phrase) matched across
    adjacent tokens."""
    def keys(text: str) -> set[str]:
        folded = fold(text)
        return {folded, folded.replace(".", "")} - {""}
    found = []
    for i, (text, _role) in enumerate(tokens):
        ks = keys(text)
        if i + 1 < len(tokens):
            ks |= {f"{k} {n}" for k in keys(text) for n in keys(tokens[i + 1][0])}
        found += [(k, i) for k in sorted(ks) if k in words]
    return found


class _Parsed:
    """A parser stand-in handing local_agreement.read a reading already
    made: read asks only for `parse(text)`'s role fields."""

    def __init__(self, r: Reading) -> None:
        self.name = dict(zip(ROLES, r.fields))

    def parse(self, _text: str) -> _Parsed:
        return self

    def __getattr__(self, role: str) -> str:
        try:
            return self.__dict__["name"][role]
        except KeyError:
            raise AttributeError(role) from None


def select(tags: Sequence[str], cap: int) -> dict[tuple[str, str], list[dict[str, str]]]:
    """Every group any of `tags` reads, its first `cap` records."""
    wanted = {(source, g) for tag in tags for source, _key, field in GAP_SOURCES
              for g in getattr(WRITTEN_IN[tag], field)}
    out: dict[tuple[str, str], list[dict[str, str]]] = {k: [] for k in sorted(wanted)}
    for source, key, _field in GAP_SOURCES:
        if not any(s == source for s, _g in wanted):
            continue
        for record in local_agreement.records(local_corpora.require(source)):
            bucket = out.get((source, record.get(key, "")))
            if bucket is not None and len(bucket) < cap:
                bucket.append(record)
    return out


def _given_opens_with_title(record: dict[str, str], titles: frozenset[str]) -> bool:
    words = record.get("given", "").replace(".", " ").split()
    return bool(words) and words[0].casefold() in titles


def gap_rows(tag: str, records: dict[tuple[str, str], list[dict[str, str]]],
             titles: frozenset[str]) -> list[tuple[str, str, dict[str, str]]]:
    """`tag`'s (source, group, record) rows to read: its countries'
    records, less the given boxes opening with a title word in the
    sources with no title box."""
    rows = []
    for source, _key, field in GAP_SOURCES:
        no_title_box = not local_agreement._box(local_agreement.FIELDED[source], "title")
        for group in getattr(WRITTEN_IN[tag], field):
            rows += [(source, group, r) for r in records.get((source, group), [])
                     if not (no_title_box and _given_opens_with_title(r, titles))]
    return rows


@dataclasses.dataclass
class GroupCount:
    scored: int = 0
    plain: int = 0
    strict: int = 0
    broke: int = 0
    fixed: int = 0
    changed: int = 0


@dataclasses.dataclass
class WordCount:
    broke: int = 0
    fixed: int = 0
    changed: int = 0
    lost: tuple[str, ...] = ()
    gained: tuple[str, ...] = ()
    roles: Counter[str] = dataclasses.field(default_factory=Counter)
    example: str = ""
    example_broke: bool = False


def score_gaps(tag: str, specs: tuple[str, str],
               rows: Sequence[tuple[str, str, dict[str, str]]],
               readings: Sequence[tuple[Reading, Reading]],
               diff: dict[str, tuple[tuple[str, ...], tuple[str, ...]]],
               listed: frozenset[str]) -> dict[str, Any]:
    """`tag`'s plain and strict readings of its rows scored against the
    boxes: per group the agreement of each, per word what strict moved."""
    per_group: dict[str, GroupCount] = {}
    per_word: dict[str, WordCount] = {}
    for (source, group, record), (p, s) in zip(rows, readings):
        fielded = local_agreement.FIELDED[source]
        count = per_group.setdefault(f"{source} {group}", GroupCount())
        rp = local_agreement.read(record, fielded, _Parsed(p), listed)  # type: ignore[arg-type]
        if rp.set_aside:
            continue
        rs = local_agreement.read(record, fielded, _Parsed(s), listed)  # type: ignore[arg-type]
        count.scored += 1
        count.plain += not rp.got
        count.strict += not rs.got
        if p.fields == s.fields:
            continue
        broke, fixed = not rp.got and bool(rs.got), bool(rp.got) and not rs.got
        count.changed += 1
        count.broke += broke
        count.fixed += fixed
        same_tokens = [t for t, _ in p.tokens] == [t for t, _ in s.tokens]
        for word, at in words_in(p.tokens, diff) or [(NO_WORD, -1)]:
            wc = per_word.get(word)
            if wc is None:
                wc = per_word[word] = WordCount(0, 0, 0, *diff.get(word, ((), ())))
            wc.changed += 1
            wc.broke += broke
            wc.fixed += fixed
            if at >= 0:
                after = s.tokens[at][1] if same_tokens else "?"
                wc.roles[f"{p.tokens[at][1] or 'none'}->{after or 'none'}"] += 1
            if not wc.example or (broke and not wc.example_broke):
                wc.example, wc.example_broke = f"{record['name']} ({group})", broke
    return {"tag": tag, "specs": list(specs), "words_differing": len(diff),
            "groups": {k: dataclasses.asdict(v) for k, v in per_group.items()},
            "words": {k: {**dataclasses.asdict(v), "roles": dict(v.roles.most_common())}
                      for k, v in per_word.items()}}


def _short(source: str) -> str:
    return {ORCID: "ORCID", PATENTSVIEW: "PV", PSC: "PSC"}.get(source, source)


def format_gaps(result: dict[str, Any], top: int) -> list[str]:
    """One language's lines: its groups, then its words by records broken."""
    lines = [f"== {result['tag']}  ({result['specs'][0]} vs {result['specs'][1]}; "
             f"{result['words_differing']} words read differently)"]
    if not result["groups"]:
        return [*lines, "   unmeasured: no country in WRITTEN_IN"]
    total = GroupCount()
    for key, g in result["groups"].items():
        source, group = key.split(" ", 1)
        for f in dataclasses.fields(GroupCount):
            setattr(total, f.name, getattr(total, f.name) + g[f.name])
        if g["scored"]:
            lines.append(f"   {_short(source):5} {group:16} n={g['scored']:6,}"
                         f"  plain {100 * g['plain'] / g['scored']:6.2f}%"
                         f"  strict {100 * g['strict'] / g['scored']:6.2f}%"
                         f"  -{g['broke']} +{g['fixed']}  changed {g['changed']}")
    lines.append(f"   all: n={total.scored:,}  broke {total.broke:,}  fixed {total.fixed:,}"
                 f"  changed {total.changed:,}")
    ranked = sorted(result["words"].items(),
                    key=lambda kv: (-kv[1]["broke"], -kv[1]["changed"], kv[0]))
    for word, w in ranked[:top]:
        moved = " ".join(filter(None, (f"-{'/'.join(w['lost'])}" if w["lost"] else "",
                                      f"+{'/'.join(w['gained'])}" if w["gained"] else "")))
        # The word's own token's commonest move; one where it kept its
        # role (a neighbour moved) only where it never moved.
        role = next((r for r in w["roles"] if len(set(r.split("->"))) == 2),
                    next(iter(w["roles"]), ""))
        lines.append(f"   {word:12} broke {w['broke']:5,} fixed {w['fixed']:4,}"
                     f" changed {w['changed']:5,}  {role:18} {moved:40} e.g. {w['example']}")
    return lines


def gaps(tags: Sequence[str], cap: int, jobs: int) -> list[dict[str, Any]]:
    from nameparser import Lexicon
    default = Lexicon.default()
    titles = frozenset(default._sets.titles)
    listed = local_agreement._title_words(default)
    records = select(tags, cap)
    per_tag = {tag: gap_rows(tag, records, titles) for tag in tags}
    specs = {tag: gap_specs(tag) for tag in tags}
    items = [(r["name"], None, specs[tag]) for tag in tags for _s, _g, r in per_tag[tag]]
    readings = iter(read(items, jobs))
    results = []
    for tag in tags:
        mine = [next(readings) for _ in per_tag[tag]]
        plain, strict = (build(s).lexicon for s in specs[tag])
        results.append(score_gaps(tag, specs[tag], per_tag[tag], mine,  # type: ignore[arg-type]
                                  changed_words(plain, strict), listed))
    return results


# --- command line ----------------------------------------------------------------

def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    sub = ap.add_subparsers(dest="mode", required=True)
    d = sub.add_parser("diff", help="names two or more configurations read differently")
    d.add_argument("specs", nargs="+", metavar="SPEC")
    d.add_argument("--committed", action="store_true", help="the committed corpus*.jsonl")
    d.add_argument("--local", action="append", metavar="SOURCE", help="a local corpus, or all")
    d.add_argument("--group", action="append", default=[], help="a fielded corpus's country "
                   "or nationality (repeatable)")
    d.add_argument("--match", help="keep the names this regular expression finds")
    d.add_argument("--sample", type=int, help="one name in N, by a hash of the name")
    g = sub.add_parser("gaps", help="each language's strict choice against its plain one")
    g.add_argument("tags", nargs="*", help="language tags (default: every choosable tag)")
    g.add_argument("--cap", type=int, default=CAP, help="records per (source, group)")
    for p in (d, g):
        p.add_argument("--top", type=int, default=15, help="words printed per configuration")
        p.add_argument("--jobs", type=int, default=os.cpu_count() or 1)
        p.add_argument("--json", type=Path, help="write every count to this file")
    d.add_argument("--readings", type=Path, help="write every name's readings, one JSON line "
                   "a name, sorted: two trees' files compare line by line")
    args = ap.parse_args(argv)
    import nameparser
    snapshot.check_source(nameparser.__file__)
    if args.mode == "gaps":
        tags = args.tags or choosable()
        if unknown := [t for t in tags if t not in WRITTEN_IN]:
            ap.error(f"no WRITTEN_IN row for {unknown}; choosable tags: {', '.join(choosable())}")
        results = gaps(tags, args.cap, args.jobs)
        print(f"strict against plain choice, {len(tags)} tags, cap {args.cap:,} a group")
        for result in results:
            print("\n".join(format_gaps(result, args.top)))
        if args.json:
            args.json.write_text(json.dumps({"cap": args.cap, "results": results},
                                            ensure_ascii=False, indent=1), encoding="utf-8")
        return 0
    if len(args.specs) < 2:
        ap.error("diff needs two configurations or more, the first the baseline")
    for spec in args.specs:
        try:
            build(spec)
        except (ValueError, SyntaxError, NameError) as exc:
            ap.error(str(exc))
    names = gather(args)
    specs = tuple(args.specs)
    readings = read([(t, o, specs) for t, o, _i in names], args.jobs)
    tallies = tally(names, readings, len(specs))
    print(f"{len(names):,} names under {len(specs)} configurations")
    for spec, t in zip(specs[1:], tallies):
        print("\n".join(format_tally(spec, specs[0], t, args.top)))
    if args.readings:
        args.readings.write_text("".join(sorted(
            snapshot.jsonl_line({"name": text, "order": order,
                                 "readings": {s: [list(r.fields), list(r.kinds)]
                                              for s, r in zip(specs, rs)}}) + "\n"
            for (text, order, _i), rs in zip(names, readings))), encoding="utf-8")
    if args.json:
        moved = [{"name": text, "order": order, "inputs": sorted(inputs),
                  "readings": {s: r._asdict() for s, r in zip(specs, rs)}}
                 for (text, order, inputs), rs in zip(names, readings)
                 if any(changed_fields(rs[0], r) for r in rs[1:])]
        args.json.write_text(json.dumps({"specs": specs, "names": len(names), "moved": moved,
                                         "tallies": [{"moved": t.moved, "total": t.total,
                                                      "words": t.words} for t in tallies]},
                                        ensure_ascii=False, indent=1), encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
