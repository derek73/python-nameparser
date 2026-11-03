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
lower case a bare choice of that language tag (`Locale(code="choice",
lexicon=Lexicon.empty(), languages={tag})`, a region tag such as
`pt-BR` or `en-GB` included). `expr:<python>` evaluates an expression
returning a `Parser`, with `Parser`, `Policy`, `Lexicon`, `Locale`,
`locales`, `parser_for` and `bare(tag)` in scope. The first
configuration is the baseline, each other compared with it.

**Inputs.** `--committed` reads the committed `corpus*.jsonl` beside
this file (snapshot.corpus_entries, each name under its shape's order);
`--local SOURCE` (repeatable, or `all`) a fetched local corpus's
distinct names. With neither, the committed corpora. `--group` keeps a
fielded local corpus's records of that country or nationality
(local_agreement.FIELDED names the key, matched exactly as the corpus
writes it), and needs `--local`: with `--committed` beside it, which
has no groups, it is refused, as is a group no record read holds; with
`--local all` it reads the fielded corpora alone, saying so. `--match`
keeps the names a regular expression finds anywhere in them, `--sample
N` one name in N (snapshot.sampled, by a hash of the name, so a sample
is the same in every tree and run).

**What is compared**: the seven role fields, the ambiguity kinds and
3.0's views (VIEWS: `generation`, `credentials`, `patronymic`,
`surname2`), which can move where no role does (`Ivan Ivanovich
Petrov` under `plain:RU` gains patronymic 'Ivanovich'). The report,
per configuration against the baseline: how many names moved, per
input; the moves grouped by which fields changed, with examples; and
the words whose token changed role, ranked, each with its commonest
move and an example. A name whose tokens differ between the two parses
(a choice that splits a word) has no per-word move and is counted under
RETOKENIZED. `--json` writes every count and every moved name's
readings, `--readings` every name's, one JSON line a name in sorted
order, so a run in each of two trees (a word moved between files, say)
compares line by line.

**gaps**: the strict-gap report. For each language tag a choice can name
(every vocabulary file but `mul` and `und`, the shipped packs riding on
their tags, gap_specs), over the records of the countries the language
is written in (LANGUAGES_OF) from the three fielded local corpora that
record one (ORCID by country of affiliation, PatentsView by the
inventor's country, PSC by nationality), the plain choice against the
strict one, each scored against the filed boxes (local_agreement.read):
a record is BROKEN where the plain choice agrees with the boxes and the
strict one does not, FIXED the other way round, CHANGED where the two
parses' roles differ. Each changed record is laid to the words in it
that the two lexicons read differently (changed_words) AND whose own
token changed role; where no such word's token moved, to those beside a
token that did (a particle whose neighbour is taken into the family);
where neither, to NO_WORD, which should stay small. A word is ranked
per language by the records it broke so, with the sets it leaves or
joins, its commonest role move and an example; `beside` counts every
broken record the word stood in, credited or not, so the gap between
the two is the records it stood in without moving (`do` in a name whose
`Miss` broke it). A word is credited once a record, however often it
stands there. ORCID records a country of affiliation, not a language, and PSC is
a UK register whose filers write `Ms` and `Miss` whatever their
nationality, so a language's strict choice is measured on the
population a caller who chose it for that country would face. The
records whose given box opens with a word the default lists as a title
are left out of ORCID and PatentsView (a holder's `Dr` typed as a given
name is evidence of nothing; the 2026-10-30 entry of
decisions/vocabulary-model filtered so); PSC's are set aside by
local_agreement.read with the default's title words, the same records
in every column. Each group is its first --cap records in raw.jsonl's
order.

LANGUAGES_OF, the language tags written in each country, and
NATIONALITY, the country each PSC nationality names, are a measurement
aid read by this report and nothing else: decisions/vocabulary-model
forbids the parser any table from country to language. A country
writing several languages stands under each (IN under hi, bn, ta, en
and the rest; NG under en, yo, ha, bin), the UK's nations by their ISO
3166-2 codes so that a Scottish filer stands under gd too; a tag no
country is listed for (`bo`, `yi`) is in NO_COUNTRY and reported as
unmeasured. A PSC nationality joined with others (`British,Irish`,
`Australian/British`) is read by its first. The report closes with
every group the tables place nowhere, at any count (a PSC nationality
by its first spelling), so the tables cannot miss a country in silence;
what is left there is misspellings and free text (`Britsh`,
`Director`).

Every parse runs in --jobs spawned worker processes (snapshot.parallel,
default every CPU), each building a configuration once from its spec
and refusing a nameparser from outside this tree. The output quotes
names; keep it out of the tree.
"""
from __future__ import annotations

import argparse
import contextlib
import dataclasses
import json
import os
import re
import sys
import warnings
from collections import Counter, defaultdict
from collections.abc import Iterable, Iterator, Sequence
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
#: 3.0's views, compared beside the roles: each can move where no role
#: does.
VIEWS = ("generation", "credentials", "patronymic", "surname2")
#: Where a moved name whose two parses hold different tokens is tallied.
RETOKENIZED = "(retokenized)"
#: Where a changed gaps record is counted when no word the lexicons read
#: differently moved there or beside a token that moved.
NO_WORD = "(no word)"
ORCID = "orcid-researchers"
PATENTSVIEW = "patentsview-inventors"
PSC = "psc-individuals"


# --- configurations ---------------------------------------------------------

def bare(tag: str) -> Locale:
    """A choice of `tag` and nothing else. The code is a constant, as
    snapshot.py's choice is: a Locale's code must be lower case, and a
    region tag (`pt-BR`) is not."""
    from nameparser import Lexicon, Locale
    return Locale(code="choice", lexicon=Lexicon.empty(), languages=frozenset({tag}))


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


@contextlib.contextmanager
def _quiet() -> Iterator[None]:
    """A pack whose script needs a segmenter (locales.JA) warns without
    one, at parser_for and again at any later rebuild of the Parser; the
    vocabulary is what is compared here."""
    with warnings.catch_warnings():
        warnings.filterwarnings("ignore", message=".*segment", category=UserWarning)
        yield


def build(spec: str) -> Parser:
    """The Parser a configuration names (see the module docstring)."""
    from nameparser import Lexicon, Locale, Parser, Policy, locales, parser_for
    kind, _, rest = spec.partition(":")
    if spec == "default":
        return Parser()
    if kind in ("plain", "strict") and rest:
        items = rest.split("+")
        packs = [_item(i) for i in items]
        try:
            with _quiet():
                return parser_for(*packs, strict=kind == "strict")
        except ValueError as exc:
            # a bare choice's Locale is named "choice"; name what was typed
            raise ValueError(f"{spec!r}: {', '.join(i for i in items if not i.isupper())} "
                             f"refused: {exc}") from None
    if kind == "expr" and rest:
        scope = {"Parser": Parser, "Policy": Policy, "Lexicon": Lexicon, "Locale": Locale,
                 "locales": locales, "parser_for": parser_for, "bare": bare}
        with _quiet():
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
    ambiguity kinds, each token's text and role, and its VIEWS."""
    fields: tuple[str, ...]
    kinds: tuple[str, ...]
    tokens: tuple[tuple[str, str], ...]
    views: tuple[str, ...] = ()


#: The parsers a worker has built, by (spec, order): a worker keeps its
#: configurations across the chunks it is handed.
_BUILT: dict[tuple[str, str | None], Parser] = {}


def _parser(spec: str, order: str | None) -> Parser:
    key = (spec, order)
    if key not in _BUILT:
        with _quiet():
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
                   tuple((t.text, str(t.role or "")) for t in parsed.tokens),
                   tuple(str(getattr(parsed, v) or "") for v in VIEWS))


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
    views = tuple(v for v, x, y in zip(VIEWS, a.views, b.views) if x != y)
    return moved + (("ambiguities",) if a.kinds != b.kinds else ()) + views


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
    words: Counter[str] = dataclasses.field(default_factory=Counter)  # names, once each
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
            moves = word_moves(rs[0], other)
            for word in dict.fromkeys(w for w, _ in moves):
                t.words[word] += 1
                t.word_example.setdefault(word, text)
            for word, move in moves:
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

def local_names(source: str, groups: Sequence[str]) -> tuple[list[str], set[str]]:
    """A fetched local corpus's names: every distinct one, or with
    `groups` those of a fielded corpus's records in them, beside the
    groups that held a record."""
    fielded = local_agreement.FIELDED.get(source)
    if groups and fielded is None:
        raise SystemExit(f"--group needs a fielded corpus ({', '.join(local_agreement.FIELDED)}),"
                         f" not {source}")
    corpus = local_corpora.require(source)
    if not groups or fielded is None:
        return list(dict.fromkeys(json.loads(line) for line in snapshot.jsonl_lines(
            local_corpora.corpus_path(source).read_text(encoding="utf-8")))), set()
    wanted, found = set(groups), set()
    names: dict[str, None] = {}
    for r in local_agreement.records(corpus):
        group = r.get(fielded.group, "")
        if group in wanted:
            found.add(group)
            names[r["name"]] = None
    return list(names), found


def gather(args: argparse.Namespace) -> list[tuple[str, str | None, frozenset[str]]]:
    """Every (name, order) the inputs hold, each with the inputs holding it."""
    found: dict[tuple[str, str | None], set[str]] = defaultdict(set)
    every = args.local == ["all"]
    sources = list(local_corpora.SOURCES) if every else args.local or []
    if args.group:
        if not sources:
            raise SystemExit(f"--group filters a fielded local corpus; give --local "
                             f"{' or '.join(local_agreement.FIELDED)}")
        if args.committed:
            raise SystemExit("--group filters local corpora only, and the committed corpora "
                             "have no groups: drop --committed, or --group")
        if every:
            sources = [s for s in sources if s in local_agreement.FIELDED]
            print(f"(--group: reading the fielded corpora only: {', '.join(sources)})")
    if args.committed or not sources:
        for text, order in snapshot.corpus_entries():
            found[(text, order)].add("committed")
    held: set[str] = set()
    for source in sources:
        if source == "all" or source not in local_corpora.SOURCES:
            raise SystemExit(f"--local {source}: not a local corpus; "
                             f"{', '.join(local_corpora.SOURCES)} or all")
        if every and local_corpora.load(source) is None:
            print(f"(not fetched, skipped: {source})")
            continue
        texts, groups = local_names(source, args.group)
        if args.group and (absent := sorted(set(args.group) - groups)):
            print(f"(--group {', '.join(absent)}: no record of {source} holds it)")
        held |= groups
        for text in texts:
            found[(text, None)].add(source)
    if missing := sorted(set(args.group) - held):
        keys = "; ".join(f"{s} by {f.group}" for s, f in local_agreement.FIELDED.items())
        raise SystemExit(f"--group {', '.join(missing)}: no record read holds it; a group is "
                         f"matched as the corpus writes it, ORCID and PatentsView an ISO code "
                         f"such as BR, PSC a nationality such as Brazilian ({keys})")
    pattern = re.compile(args.match) if args.match else None
    entries = [e for e in found if pattern is None or pattern.search(e[0])]
    if args.sample:
        entries = snapshot.sampled(entries, args.sample)
    return [(text, order, frozenset(found[(text, order)])) for text, order in entries]


# --- gaps: where each language is written ------------------------------------------

#: The language tags written in each country, for the gaps report only:
#: ISO 3166-1 codes as ORCID and PatentsView record them, and the UK's
#: nations by their ISO 3166-2 codes, which only PSC's nationalities
#: reach. Each tag is one a choice can name (test_config_diff holds it);
#: a country none of whose languages has a file maps to ().
LANGUAGES_OF: dict[str, tuple[str, ...]] = {
    "AD": ("ca",), "AE": ("ar", "en"), "AF": ("fa",), "AG": ("en",), "AL": (),
    "AM": ("hy",), "AO": ("pt",), "AQ": (), "AR": ("es",), "AS": ("en",),
    "AT": ("de",), "AU": ("en",), "AW": ("nl",), "AX": ("sv",), "AZ": ("tr",),
    "BA": ("bs", "hr", "sr"), "BB": ("en",), "BD": ("bn",), "BE": ("nl", "fr", "de"),
    "BF": ("fr",), "BG": ("bg",), "BH": ("ar",), "BI": ("fr",), "BJ": ("fr", "yo"),
    "BM": ("en",), "BN": ("ms",), "BO": ("es",), "BR": ("pt-BR",), "BS": ("en",),
    "BT": (), "BW": ("en",), "BY": ("be", "ru"), "BZ": ("en",), "CA": ("en", "fr"),
    "CD": ("fr",), "CF": ("fr",), "CG": ("fr",), "CH": ("de", "fr", "it"),
    "CI": ("fr",), "CL": ("es",), "CM": ("fr", "en"), "CN": ("zh",), "CO": ("es",),
    "CR": ("es",), "CU": ("es",), "CV": ("pt",), "CW": ("nl",), "CY": ("el", "tr"),
    "CZ": ("cs",), "DE": ("de",), "DJ": ("fr", "ar"), "DK": ("da",), "DM": ("en",),
    "DO": ("es",), "DZ": ("ar", "fr"), "EC": ("es",), "EE": ("et",), "EG": ("ar",),
    "ER": ("ti", "ar"), "ES": ("es", "ca"), "ET": ("am",), "FI": ("fi", "sv"),
    "FJ": ("en",), "FO": ("da",), "FR": ("fr",), "GA": ("fr",),
    "GB": ("en",), "GB-ENG": ("en",), "GB-NIR": ("en", "ga"), "GB-SCT": ("en", "gd"),
    "GB-WLS": ("en",), "GD": ("en",), "GE": ("ka",), "GF": ("fr",), "GH": ("en", "ak"),
    "GL": ("da",), "GM": ("en",), "GN": ("fr", "ff"), "GP": ("fr",), "GQ": ("es", "fr"),
    "GR": ("el",), "GT": ("es",), "GU": ("en",), "GW": ("pt",), "GY": ("en",),
    "HK": ("zh", "en"), "HN": ("es",), "HR": ("hr",), "HT": ("fr",), "HU": ("hu",),
    "ID": ("id",), "IE": ("en", "ga"), "IL": ("he", "ar"), "IM": ("en",),
    "IN": ("hi", "bn", "ta", "te", "mr", "gu", "kn", "ml", "or", "pa", "as", "ur",
           "kok", "sd", "ne", "en"),
    "IQ": ("ar",), "IR": ("fa",), "IS": ("is",), "IT": ("it",), "JE": ("en",),
    "JM": ("en",), "JO": ("ar",), "JP": ("ja",), "KE": ("sw", "en"), "KG": ("ru",),
    "KH": ("km",), "KM": ("ar", "fr"), "KN": ("en",), "KP": ("ko",), "KR": ("ko",),
    "KW": ("ar",), "KY": ("en",), "KZ": ("kk", "ru"), "LA": ("lo",), "LB": ("ar", "fr"),
    "LC": ("en",), "LI": ("de",), "LK": ("si", "ta"), "LR": ("en",), "LS": ("en",),
    "LT": ("lt",), "LU": ("fr", "de"), "LV": ("lv",), "LY": ("ar",), "MA": ("ar", "fr"),
    "MC": ("fr",), "MD": ("ro", "ru"), "ME": ("sr",), "MG": ("fr",), "MK": ("mk",),
    "ML": ("fr",), "MM": ("my", "shn"), "MN": ("mn",), "MO": ("zh", "pt"),
    "MQ": ("fr",), "MR": ("ar",), "MT": ("en",), "MU": ("en", "fr"), "MV": (),
    "MW": ("en",), "MX": ("es",), "MY": ("ms", "zh", "ta", "en"), "MZ": ("pt",),
    "NA": ("en",), "NC": ("fr",), "NE": ("fr", "ha"), "NG": ("en", "yo", "ha", "bin"),
    "NI": ("es",), "NL": ("nl",), "NO": ("nb", "nn"), "NP": ("ne",), "NZ": ("en", "mi"),
    "OM": ("ar",), "PA": ("es",), "PE": ("es",), "PF": ("fr",), "PG": ("en",),
    "PH": ("fil", "en"), "PK": ("ur", "pa", "sd", "en"), "PL": ("pl",), "PR": ("es", "en"),
    "PS": ("ar",), "PT": ("pt",), "PY": ("es",), "QA": ("ar",), "RE": ("fr",),
    "RO": ("ro",), "RS": ("sr",), "RU": ("ru",), "RW": ("fr", "en"), "SA": ("ar",),
    "SC": ("en", "fr"), "SD": ("ar",), "SE": ("sv",), "SG": ("zh", "ms", "ta", "en"),
    "SI": ("sl",), "SK": ("sk",), "SL": ("en",), "SN": ("fr", "ff"), "SO": ("ar",),
    "SR": ("nl",), "SS": ("en",), "ST": ("pt",), "SV": ("es",), "SX": ("nl", "en"),
    "SY": ("ar",), "SZ": ("en",), "TD": ("fr", "ar"), "TG": ("fr",), "TH": ("th",),
    "TJ": ("ru",), "TL": ("pt",), "TM": ("ru",), "TN": ("ar", "fr"), "TR": ("tr",),
    "TT": ("en",), "TW": ("zh",), "TZ": ("sw", "en"), "UA": ("uk", "ru"),
    "UG": ("en", "sw"), "UM": ("en",), "US": ("en",), "UY": ("es",), "UZ": ("ru",),
    "VE": ("es",), "VG": ("en",), "VI": ("en",), "VN": ("vi",), "XK": (),  # Albanian, which no file holds
    "YE": ("ar",), "ZA": ("en", "zu"), "ZM": ("en",), "ZW": ("en",),
    # territories and small states
    "AI": ("en",), "BL": ("fr",), "BQ": ("nl",), "BV": (), "CC": ("en",), "CK": ("en",),
    "CX": ("en",), "EH": ("ar",), "FK": ("en",), "FM": ("en",), "GG": ("en",), "GI": ("en",),
    "GS": (), "HM": (), "IO": ("en",), "KI": ("en",), "MF": ("fr",), "MH": ("en",),
    "MP": ("en",), "MS": ("en",), "NF": ("en",), "NR": ("en",), "NU": ("en",), "PM": ("fr",),
    "PN": ("en",), "PW": ("en",), "SB": ("en",), "SH": ("en",), "SJ": ("nb",), "SM": ("it",),
    "TC": ("en",), "TF": ("fr",), "TK": ("en",), "TO": ("en",), "TV": ("en",), "VA": ("it",),
    "VC": ("en",), "VU": ("en", "fr"), "WF": ("fr",), "WS": ("en",), "YT": ("fr",),
    # no country recorded
    "": (),
}

#: The country each PSC nationality names, as the register spells it. A
#: nationality joined with others (`British,Irish`) is read by its first.
NATIONALITY: dict[str, str] = {
    "Afghan": "AF", "Albanian": "AL", "Algerian": "DZ", "American": "US",
    "Angolan": "AO", "Argentine": "AR", "Armenian": "AM", "Australian": "AU",
    "Austrian": "AT", "Azerbaijani": "AZ", "Bahraini": "BH", "Bangladeshi": "BD",
    "Barbadian": "BB", "Belarusian": "BY", "Belgian": "BE", "Beninese": "BJ",
    "Bolivian": "BO", "Botswanan": "BW", "Brazilian": "BR", "British": "GB",
    "British Virgin Islander": "VG", "Bulgarian": "BG", "Burkinan": "BF", "Burmese": "MM",
    "Cameroonian": "CM", "Canadian": "CA", "Chilean": "CL", "Chinese": "CN",
    "Citizen Of Bosnia And Herzegovina": "BA", "Colombian": "CO",
    "Congolese (Congo)": "CG", "Congolese (Drc)": "CD", "Costa Rican": "CR",
    "Croatian": "HR", "Cuban": "CU", "Cypriot": "CY", "Czech": "CZ", "Danish": "DK",
    "Dominican": "DO", "Dutch": "NL", "Ecuadorean": "EC", "Egyptian": "EG",
    "Emirati": "AE", "English": "GB-ENG", "Eritrean": "ER", "Estonian": "EE",
    "Ethiopian": "ET", "Fijian": "FJ", "Filipino": "PH", "Finnish": "FI", "French": "FR",
    "Gabonese": "GA", "Gambian": "GM", "Georgian": "GE", "German": "DE",
    "Ghanaian": "GH", "Greek": "GR", "Grenadian": "GD", "Guinean": "GN",
    "Guyanese": "GY", "Hong Konger": "HK", "Hungarian": "HU", "Icelandic": "IS",
    "Indian": "IN", "Indonesian": "ID", "Iranian": "IR", "Iraqi": "IQ", "Irish": "IE",
    "Israeli": "IL", "Italian": "IT", "Ivorian": "CI", "Jamaican": "JM",
    "Japanese": "JP", "Jordanian": "JO", "Kazakh": "KZ", "Kenyan": "KE",
    "Kittitian": "KN", "Kosovan": "XK", "Kuwaiti": "KW", "Kyrgyz": "KG",
    "Latvian": "LV", "Lebanese": "LB", "Libyan": "LY", "Lithuanian": "LT",
    "Luxembourger": "LU", "Macedonian": "MK", "Malagasy": "MG", "Malawian": "MW",
    "Malaysian": "MY", "Maltese": "MT", "Mauritian": "MU", "Mexican": "MX",
    "Moldovan": "MD", "Mongolian": "MN", "Moroccan": "MA", "Namibian": "NA",
    "Nepalese": "NP", "New Zealander": "NZ", "Nigerian": "NG", "Nigerien": "NE",
    "Northern Irish": "GB-NIR", "Norwegian": "NO", "Omani": "OM", "Pakistani": "PK",
    "Palestinian": "PS", "Panamanian": "PA", "Peruvian": "PE", "Polish": "PL",
    "Portuguese": "PT", "Qatari": "QA", "Romanian": "RO", "Russian": "RU",
    "Rwandan": "RW", "Saudi Arabian": "SA", "Scottish": "GB-SCT", "Senegalese": "SN",
    "Serbian": "RS", "Sierra Leonean": "SL", "Singaporean": "SG", "Slovak": "SK",
    "Slovenian": "SI", "Somali": "SO", "South African": "ZA", "South Korean": "KR",
    "Spanish": "ES", "Sri Lankan": "LK", "St Lucian": "LC", "Sudanese": "SD",
    "Swedish": "SE", "Swiss": "CH", "Syrian": "SY", "Taiwanese": "TW", "Tajik": "TJ",
    "Tanzanian": "TZ", "Thai": "TH", "Togolese": "TG", "Trinidadian": "TT",
    "Tunisian": "TN", "Turkish": "TR", "Turkmen": "TM", "Ugandan": "UG", "Uk": "GB",
    "Ukrainian": "UA", "United Kingdom": "GB", "Uruguayan": "UY", "Uzbek": "UZ",
    "Venezuelan": "VE", "Vietnamese": "VN", "Welsh": "GB-WLS", "Yemeni": "YE",
    "Zambian": "ZM", "Zimbabwean": "ZW",
    # under 100 records: every real nationality of 5 or more (2026-11-03)
    "Andorran": "AD", "Bahamian": "BS", "Belizean": "BZ", "Bermudian": "BM",
    "Bhutanese": "BT", "Bruneian": "BN", "Burundian": "BI", "Cambodian": "KH",
    "Cape Verdean": "CV", "Cayman Islander": "KY", "Central African": "CF", "Chadian": "TD",
    "Citizen Of Antigua And Barbuda": "AG", "Citizen Of Guinea-Bissau": "GW",
    "Citizen Of Seychelles": "SC", "Citizen Of The Dominican Republic": "DO",
    "Citizen Of Vanuatu": "VU", "Comoran": "KM", "Congolese": "CG", "Cornish": "GB-ENG",
    "Cymraes": "GB-WLS", "Cymro": "GB-WLS", "Cymro / Cymraes": "GB-WLS",
    "Djiboutian": "DJ", "East Timorese": "TL", "Equatorial Guinean": "GQ",
    "Gibraltarian": "GI", "Guatemalan": "GT", "Haitian": "HT", "Honduran": "HN",
    "Korean": "KR", "Lao": "LA", "Liberian": "LR", "Liechtenstein Citizen": "LI",
    "Macanese": "MO", "Malian": "ML", "Maldivian": "MV", "Mauritanian": "MR",
    "Monegasque": "MC", "Montenegrin": "ME", "Montserratian": "MS", "Mosotho": "LS",
    "Mozambican": "MZ", "Nicaraguan": "NI", "North Korean": "KP", "Papua New Guinean": "PG",
    "Paraguayan": "PY", "Salvadorean": "SV", "Sao Tomean": "ST", "Slovakian": "SK",
    "South Sudanese": "SS", "Surinamese": "SR", "Swazi": "SZ", "Tongan": "TO",
    "Vincentian": "VC", "Anguillan": "AI", "Srilankan": "LK",
    # the country or a spelling of it typed where the nationality goes
    "British Citizen": "GB", "Uk Citizen": "GB", "U.K.": "GB", "Gb": "GB", "England": "GB-ENG",
    "New Zealand": "NZ", "Netherlands": "NL", "Romania": "RO", "Ukraine": "UA",
    "United States": "US", "Usa": "US", "China": "CN", "Italy": "IT", "India": "IN",
    "Spain": "ES", "Portugese": "PT",
}

#: Tags no country is listed for: reported as unmeasured.
NO_COUNTRY = frozenset({"bo", "yi"})

#: How each fielded source names its groups: the record key.
GAP_SOURCES = ((ORCID, "country"), (PATENTSVIEW, "country"), (PSC, "nationality"))
#: Records per (source, group), the first in raw.jsonl's order; ORCID's
#: and PatentsView's caches hold at most 20,000 a country.
CAP = 20_000


def country_of(source: str, group: str) -> str | None:
    """The LANGUAGES_OF key a source's group stands for, or None where
    the tables place it nowhere."""
    if source != PSC:
        return group if group in LANGUAGES_OF else None
    for spelling in (group, first_spelling(group)):
        if spelling in NATIONALITY:
            return NATIONALITY[spelling]
    return None


def first_spelling(nationality: str) -> str:
    """A joined PSC nationality's first (`British` of `British,Irish`
    and of `British/Pakistani`)."""
    return re.split(r"[,/]", nationality)[0].strip()


def stands_under(source: str, group: str, tag: str) -> bool:
    country = country_of(source, group)
    return country is not None and tag in LANGUAGES_OF[country]


def unmapped(counts: dict[tuple[str, str], int]) -> list[tuple[str, str, int]]:
    """Every group the tables place nowhere, at any count, a PSC
    nationality counted by its first spelling, most records first."""
    out: Counter[tuple[str, str]] = Counter()
    for (s, g), n in counts.items():
        if country_of(s, g) is None:
            out[(s, first_spelling(g) if s == PSC else g)] += n
    return sorted(((s, g, n) for (s, g), n in out.items()), key=lambda x: (-x[2], x[0], x[1]))


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


# --- gaps: the report --------------------------------------------------------------

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
             ) -> list[tuple[str, int, int]]:
    """The words of `words` in a reading's tokens, each with the indexes
    of the tokens it spans, matched folded and with every period removed
    (as an acronym is); a two-word entry (a title phrase) matched across
    adjacent tokens."""
    def keys(text: str) -> set[str]:
        folded = fold(text)
        return {folded, folded.replace(".", "")} - {""}
    found = []
    for i, (text, _role) in enumerate(tokens):
        found += [(k, i, i + 1) for k in sorted(keys(text)) if k in words]
        if i + 1 < len(tokens):
            found += [(k, i, i + 2) for k in sorted(
                {f"{a} {b}" for a in keys(text) for b in keys(tokens[i + 1][0])})
                if k in words]
    return found


def credited(p: Reading, s: Reading, found: Sequence[tuple[str, int, int]]
             ) -> list[tuple[str, int, int]]:
    """The words of `found` a changed record is laid to: those whose own
    token changed role between the two parses, or, where none did, those
    beside a token that did; none where the parses hold different tokens."""
    if [t for t, _ in p.tokens] != [t for t, _ in s.tokens]:
        return []
    moved = {i for i, ((_, a), (_, b)) in enumerate(zip(p.tokens, s.tokens)) if a != b}
    own = [w for w in found if moved & set(range(w[1], w[2]))]
    return own or [w for w in found if moved & {w[1] - 1, w[2]}]


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


def select(tags: Sequence[str], cap: int
           ) -> tuple[dict[tuple[str, str], list[dict[str, str]]], dict[tuple[str, str], int]]:
    """Every group any of `tags` stands under, its first `cap` records,
    beside every group's record count (for `unmapped`)."""
    out: dict[tuple[str, str], list[dict[str, str]]] = {}
    counts: Counter[tuple[str, str]] = Counter()
    wanted = set(tags)
    for source, key in GAP_SOURCES:
        for record in local_agreement.records(local_corpora.require(source)):
            group = record.get(key, "")
            counts[(source, group)] += 1
            country = country_of(source, group)
            if country is None or not wanted & set(LANGUAGES_OF[country]):
                continue
            bucket = out.setdefault((source, group), [])
            if len(bucket) < cap:
                bucket.append(record)
    return out, dict(counts)


def _given_opens_with_title(record: dict[str, str], titles: frozenset[str]) -> bool:
    words = record.get("given", "").replace(".", " ").split()
    return bool(words) and words[0].casefold() in titles


def gap_rows(tag: str, records: dict[tuple[str, str], list[dict[str, str]]],
             titles: frozenset[str]) -> list[tuple[str, str, dict[str, str]]]:
    """`tag`'s (source, group, record) rows to read: the records of the
    groups it stands under, less the given boxes opening with a title
    word in the sources with no title box."""
    rows = []
    for (source, group), recs in sorted(records.items()):
        if not stands_under(source, group, tag):
            continue
        no_title_box = not local_agreement._box(local_agreement.FIELDED[source], "title")
        rows += [(source, group, r) for r in recs
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
    beside: int = 0  # broken records the word stood in, credited or not
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

    def word(w: str) -> WordCount:
        if w not in per_word:
            per_word[w] = WordCount(lost=diff.get(w, ((), ()))[0], gained=diff.get(w, ((), ()))[1])
        return per_word[w]

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
        if p.fields == s.fields:  # the roles, which the boxes are scored on
            continue
        broke, fixed = not rp.got and bool(rs.got), bool(rp.got) and not rs.got
        count.changed += 1
        count.broke += broke
        count.fixed += fixed
        found = words_in(p.tokens, diff)
        for w in dict.fromkeys(w for w, _i, _j in found):
            word(w).beside += broke
        # once a word a record, at its first credited occurrence
        # (`Sultan Sultan Hamad`), as `beside` counts above
        laid = list({w: (w, i, j) for w, i, j in reversed(credited(p, s, found))}.values())[::-1]
        for w, i, _j in laid or [(NO_WORD, -1, -1)]:
            wc = word(w)
            wc.changed += 1
            wc.broke += broke
            wc.fixed += fixed
            if i >= 0:
                wc.roles[f"{p.tokens[i][1] or 'none'}->{s.tokens[i][1] or 'none'}"] += 1
            if not wc.example or (broke and not wc.example_broke):
                wc.example, wc.example_broke = f"{record['name']} ({group})", broke
    return {"tag": tag, "specs": list(specs), "words_differing": len(diff),
            "groups": {k: dataclasses.asdict(v) for k, v in per_group.items()},
            "words": {k: {**dataclasses.asdict(v), "roles": dict(v.roles.most_common())}
                      for k, v in per_word.items() if v.changed}}


def _short(source: str) -> str:
    return {ORCID: "ORCID", PATENTSVIEW: "PV", PSC: "PSC"}.get(source, source)


def format_gaps(result: dict[str, Any], top: int) -> list[str]:
    """One language's lines: its groups, then its words by records broken."""
    lines = [f"== {result['tag']}  ({result['specs'][0]} vs {result['specs'][1]}; "
             f"{result['words_differing']} words read differently)"]
    if not result["groups"]:
        return [*lines, "   unmeasured: no country in LANGUAGES_OF"]
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
    for w, c in ranked[:top]:
        moved = " ".join(filter(None, (f"-{'/'.join(c['lost'])}" if c["lost"] else "",
                                      f"+{'/'.join(c['gained'])}" if c["gained"] else "")))
        role = next(iter(c["roles"]), "")
        lines.append(f"   {w:12} broke {c['broke']:5,} (beside {c['beside']:5,}) fixed "
                     f"{c['fixed']:4,} changed {c['changed']:5,}  {role:18} {moved:40} "
                     f"e.g. {c['example']}")
    return lines


def gaps(tags: Sequence[str], cap: int, jobs: int
         ) -> tuple[list[dict[str, Any]], list[tuple[str, str, int]]]:
    from nameparser import Lexicon
    default = Lexicon.default()
    titles = frozenset(default._sets.titles)
    listed = local_agreement._title_words(default)
    records, counts = select(tags, cap)
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
    return results, unmapped(counts)


# --- command line ----------------------------------------------------------------

def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    sub = ap.add_subparsers(dest="mode", required=True)
    d = sub.add_parser("diff", help="names two or more configurations read differently")
    d.add_argument("specs", nargs="+", metavar="SPEC")
    d.add_argument("--committed", action="store_true", help="the committed corpus*.jsonl")
    d.add_argument("--local", action="append", metavar="SOURCE", help="a local corpus, or all")
    d.add_argument("--group", action="append", default=[], help="a fielded corpus's country "
                   "or nationality, as the corpus writes it (repeatable; needs --local)")
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
        if unknown := sorted(set(tags) - set(choosable())):
            ap.error(f"{unknown} is no tag a choice can name; choosable: {', '.join(choosable())}")
        results, missing = gaps(tags, args.cap, args.jobs)
        print(f"strict against plain choice, {len(tags)} tags, cap {args.cap:,} a group")
        for result in results:
            print("\n".join(format_gaps(result, args.top)))
        print(f"\ngroups LANGUAGES_OF and NATIONALITY place nowhere, at any count: "
              f"{len(missing)}, {sum(n for _s, _g, n in missing):,} records")
        for source in dict.fromkeys(s for s, _g, _n in missing):
            print(f"   {_short(source)}: " + ", ".join(
                f"{g or '(none)'} {n}" for s, g, n in missing if s == source))
        if args.json:
            args.json.write_text(json.dumps({"cap": args.cap, "results": results,
                                             "unmapped": missing},
                                            ensure_ascii=False, indent=1), encoding="utf-8")
        return 0
    if len(args.specs) < 2:
        ap.error("diff needs two configurations or more, the first the baseline")
    for spec in args.specs:
        try:
            build(spec)
        except Exception as exc:  # an expr: may raise anything; report it, no traceback
            ap.error(f"{spec}: {type(exc).__name__}: {exc}")
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
                                 "readings": {s: [list(r.fields), list(r.kinds), list(r.views)]
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
