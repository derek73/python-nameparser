"""Measure Parser.suggest on groups of names whose written order is known.

`Parser.suggest(names)` reads a group of names a caller declares to share
one convention and suggests a `name_order` (and `patronymic_rules`). Its
decision rule (`_suggest._MIN_VOTES`, `_MIN_SHARE`,
`_MIN_PATRONYMIC_SHARE`, `_MIN_PATRONYMIC_VOTES`) and its word tables
(`config/_order_names.py`, written by tools/vocab/order_names.py) were
chosen with this tool, and the figures quoted for them in `suggest`'s
docstring and docs/design/decisions/group-suggestion.md are its output.

    uv run python tools/differential/suggest_measure.py
    uv run python tools/differential/suggest_measure.py --sizes 5,10 --trials 100
    uv run python tools/differential/suggest_measure.py --set _MIN_VOTES=1000000 --set _MIN_PATRONYMIC_VOTES=1000000
    uv run python tools/differential/suggest_measure.py --base <base checkout>

THE POPULATIONS, from the local corpora in $NAMEPARSER_TOOLS_CACHE
(~/.cache/nameparser-tools, `local_corpora.py fetch`), each name composed
from the boxes its filer typed it into, so its order is known:
PatentsView inventors by country (PV_COUNTRIES, read from the
patentsview-inventors extract, uncapped), UK company filers by
nationality (psc-individuals, PSC_NATIONALITIES, forename and middle name
before the surname), Czech candidates (cz-candidates, `jmeno` and
`prijmeni`) and Vietnamese names (uit-vinames, the middle name before the
given name, as Vietnamese writes them). A population keeps at most
POOL_CAP names, drawn by a seeded reservoir. A source not fetched is
left out with a note; one present but unreadable stops the run.

THE GROUPS: for each population, written order (`Given Family` and
`Family Given`, from the same boxes) and size, `--trials` groups drawn
with a generator seeded by `--seed` and the population, each read by
`Parser.suggest` under both base orders (`Parser()` and a `Parser` whose
policy is `name_order=FAMILY_FIRST`). A group is RIGHT where the
suggested parser's `name_order` writes the family at the end the group
was written with; a given-first group under the given-first base is right
where the suggester kept or confirmed the base, and wrong only where it
moved. The table prints the share right per population, written order,
base and size: the anti-goal (decisions/group-suggestion) is the two
same-order rows, which must not fall below 95%.

THE SIGNALS: per population and written order, over at most SIGNAL_NAMES
names, the per-NAME order votes (`suggest`'s unit: right, wrong,
contested, none) and each signal's own votes right and wrong. With
`--wrong-words N`, each signal's N commonest words in a wrong vote.

THE PARLIAMENTS, from the opensanctions-parliaments raw.jsonl, rows whose
`form` is "name" and whose `script` is Latin or Cyrillic: the Turkic
table of decisions/group-suggestion's 2026-11-10 TURKIC entry (its
TURKIC_LISTS, scored by TURKIC_CONVENTION under each fixed policy and
end to end through `suggest`), then every list's suggestion as a whole,
beside the order the list was read by eye to write (LIST_ORDER).

THE CHECKS (`--checks`, in place of the tables): over every population's
whole pool written both ways, the surname table's right and wrong votes
(East Asian populations apart), the wrong votes the short romanized
surnames (SHORT_SURNAMES) cast, the names ending in a bare letter, ASCII
or not, the given-name votes folding `ø` and `ł` would move; and over a
draw of groups of its own, how many decide another patronymic rule when
the names whose only evidence is a contested order leave the share's
denominator.

`--set NAME=VALUE` overrides one of `_suggest`'s thresholds in every
worker, so a rule can be tried without editing the module; it is also the
harness's proof that it can report a difference: `--set
_MIN_VOTES=1000000 --set _MIN_PATRONYMIC_VOTES=1000000` decides nothing
(the first holds the order, the second the patronymic rule, which forces
an order of its own), so every family-first group under the given-first
base must read 0% (and every given-first group under the family-first
base). `--base` runs the same measurement against another
checkout in a child process and lists every cell that moved.

Runtime, measured 2026-11-10 on a 12-CPU machine with every source
fetched and the defaults (sizes 2-200, 300 trials, --jobs 12): 20s
wall clock, 6s of it reading the corpora in one process; with --base,
twice that.
"""
from __future__ import annotations

import argparse
import contextlib
import gzip
import json
import os
import random
import subprocess
import sys
import tempfile
from collections import Counter
from collections.abc import Iterator
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from nameparser import Policy

HERE = Path(__file__).resolve().parent
if str(HERE) not in sys.path:
    sys.path.append(str(HERE))
import corpus_build  # noqa: E402
import snapshot  # noqa: E402

REPO_ROOT = HERE.parents[1]
SIZES = (2, 3, 4, 5, 10, 20, 50, 200)
TRIALS = 300
SEED = 20261110
#: The most names a population keeps, drawn by a seeded reservoir.
POOL_CAP = 20_000
#: The names each population's signal counts read.
SIGNAL_NAMES = 3_000
PV_COUNTRIES = ("US", "DE", "FR", "CN", "JP", "KR", "IN", "IT", "ES", "RU",
                "BR", "TW", "NL")
PSC_NATIONALITIES = ("British", "Romanian", "Indian", "Chinese", "Polish",
                     "Nigerian", "Turkish", "Spanish")
GF, FF = "GF", "FF"
#: The thresholds --set may override.
SETTABLE = ("_MIN_VOTES", "_MIN_SHARE", "_MIN_PATRONYMIC_SHARE",
            "_MIN_PATRONYMIC_VOTES")
#: The thresholds that count names, read as int.
_COUNTS = ("_MIN_VOTES", "_MIN_PATRONYMIC_VOTES")

#: decisions/group-suggestion's TURKIC lists, and the end each writes the
#: family at: "caps" where the one capitals word is the family, else the
#: end read by eye off the list's first twelve names (2026-11-10).
TURKIC_LISTS = ("az_parliament", "kz_senate", "uz_senate",
                "uz_legislative_chamber", "tm_mejlis", "kz_mazhilis",
                "kg_jogorku_kenesh")
TURKIC_CONVENTION = {
    "az_parliament": "caps", "kz_mazhilis": "caps", "kz_senate": "first",
    "uz_senate": "first", "uz_legislative_chamber": "last",
    "tm_mejlis": "last", "kg_jogorku_kenesh": "last"}
#: The order each parliament list writes its names in, read by eye off
#: its first names (the spike's thirteen Latin lists, the TURKIC lists,
#: and ru_duma_deputies and ua_rada, 2026-11-10). kz_mazhilis writes the
#: family last, in capitals (`Тилектес Серикбайулы АДАМБЕКОВ`).
LIST_ORDER = {
    "az_parliament": FF, "by_council_republic": FF, "hr_sabor": GF,
    "in_sansad": GF, "kg_jogorku_kenesh": GF, "kz_mazhilis": GF,
    "kz_senate": FF, "pt_parliament": GF, "ru_duma_deputies": GF,
    "ru_federation_council": GF, "si_dz_rs": GF, "sk_nrsr_poslanci": GF,
    "tm_mejlis": GF, "tr_parliament": GF, "ua_rada": FF,
    "uz_legislative_chamber": GF, "uz_senate": FF}
#: The fixed policies of the TURKIC table, as decisions/group-suggestion
#: heads its columns: (label, patronymic rules, name order).
TURKIC_POLICIES = (
    ("nothing", (), None), ("{T}", ("TURKIC",), None),
    ("{T}+FF", ("TURKIC",), "FAMILY_FIRST"),
    ("{T}+FFGL", ("TURKIC",), "FAMILY_FIRST_GIVEN_LAST"),
    ("{E}", ("EAST_SLAVIC",), None),
    ("{E,T}", ("EAST_SLAVIC", "TURKIC"), None),
    ("FF alone", (), "FAMILY_FIRST"))

Pool = list[tuple[str, str]]  # (given part as written, family)


def local(source: str) -> Path:
    return corpus_build.cache_dir(f"local/{source}", create=False)


# -- the populations ---------------------------------------------------------

def _rows(path: Path) -> Iterator[dict[str, Any]]:
    """A raw.jsonl's records, cut at "\\n" only (corpus_build.jsonl_lines
    cuts the same way), streamed."""
    with open(path, encoding="utf-8", newline="\n") as lines:
        for line in lines:
            if line.strip():
                yield json.loads(line)


def pool_rng(seed: int, label: str) -> random.Random:
    """The generator a population's reservoir draws its names with."""
    return random.Random(f"{seed}-{label}-pool")


def group_rng(seed: int, label: str) -> random.Random:
    """The generator a population's groups are drawn with: a stream of
    its own, never the reservoir's. Seeded alike, the two drew the same
    indices, so a group's names were the slots the reservoir had just
    filled, consecutive records of a sorted file (five Đ-family names
    in a row in vi), and the against-base cells moved by up to 25
    points with the reservoir's seed alone."""
    return random.Random(f"{seed}-{label}-groups")


class _Reservoir:
    """At most POOL_CAP names per label, a seeded uniform draw."""

    def __init__(self, seed: int) -> None:
        self.pools: dict[str, Pool] = {}
        self.seen: Counter[str] = Counter()
        self.seed = seed
        self.rngs: dict[str, random.Random] = {}

    def slot(self, label: str) -> int | None:
        """Where the next name of `label` goes, or None where the draw
        passes it over: asked before the name is decoded."""
        pool = self.pools.setdefault(label, [])
        if (rng := self.rngs.get(label)) is None:
            rng = self.rngs[label] = pool_rng(self.seed, label)
        self.seen[label] += 1
        if len(pool) < POOL_CAP:
            return len(pool)
        j = rng.randrange(self.seen[label])
        return j if j < POOL_CAP else None

    def put(self, label: str, at: int, given: str, family: str) -> None:
        """A name into the slot `slot` gave; one missing either box is
        left out (its slot, where it was a fresh one, stays unfilled)."""
        given, family = " ".join(given.split()), " ".join(family.split())
        if not given or not family:
            return
        pool = self.pools[label]
        if at == len(pool):
            pool.append((given, family))
        elif at < len(pool):
            pool[at] = (given, family)

    def add(self, label: str, given: str, family: str) -> None:
        if (at := self.slot(label)) is not None:
            self.put(label, at, given, family)


def _patentsview(keep: _Reservoir) -> None:
    """The extract the patentsview-inventors fetch keeps, every name
    (local_patentsview.pv_boxes reads the same file, but decodes all of
    its 5.3 million lines; a line naming no wanted country is skipped
    here undecoded, and a decoded one must name the country it seemed
    to)."""
    import local_patentsview
    path = local_patentsview.extract_path()
    if not path.exists():
        raise FileNotFoundError(2, "not fetched", str(path))
    wanted = {f'"country": "{c}"': c for c in PV_COUNTRIES}
    with gzip.open(path, "rt", encoding="utf-8", newline="\n") as lines:
        if json.loads(next(lines)).get("release") != local_patentsview.PV_RELEASE:
            raise ValueError(f"{path} is not an extract of the "
                             f"{local_patentsview.PV_RELEASE} release")
        for line in lines:
            country = wanted.get(line[1:16])
            if country is None:
                continue
            label = f"pv-{country}"
            if (at := keep.slot(label)) is None:
                continue
            record = json.loads(line)
            if record.get("country") != country:
                raise ValueError(f"{path}: a line read as {country} is not: "
                                 f"{line[:60]!r}")
            keep.put(label, at, record.get("given", ""),
                     record.get("family", ""))


def _psc(keep: _Reservoir) -> None:
    for r in _rows(local("psc-individuals") / "raw.jsonl"):
        if (n := r.get("nationality")) in PSC_NATIONALITIES:
            given = f"{r.get('forename', '')} {r.get('middle_name', '')}"
            keep.add(f"psc-{n}", given, r.get("surname", ""))


def _cz(keep: _Reservoir) -> None:
    for r in _rows(local("cz-candidates") / "raw.jsonl"):
        keep.add("cz", r.get("jmeno", ""), r.get("prijmeni", ""))


def _vi(keep: _Reservoir) -> None:
    for r in _rows(local("uit-vinames") / "raw.jsonl"):
        keep.add("vi", f"{r.get('middle', '')} {r.get('given', '')}",
                 r.get("family", ""))


SOURCES = (("patentsview-inventors", _patentsview),
           ("psc-individuals", _psc), ("cz-candidates", _cz),
           ("uit-vinames", _vi))


def load_pools(seed: int) -> tuple[dict[str, Pool], list[str]]:
    """Every population fetched, and a note for each source that is
    not. A source present but unreadable stops the run: a cut file is a
    broken measurement, not a smaller one."""
    keep = _Reservoir(seed)
    notes = []
    for source, read in SOURCES:
        try:
            read(keep)
        except FileNotFoundError as e:
            notes.append(f"{source}: not fetched ({e.filename}); "
                         f"uv run python tools/differential/local_corpora.py "
                         f"fetch {source}")
        except (OSError, ValueError, KeyError, EOFError) as e:
            raise SystemExit(f"{source}: present but unreadable "
                             f"({type(e).__name__}: {e}); fetch it again") from e
    return dict(sorted(keep.pools.items())), notes


def written(name: tuple[str, str], order: str) -> str:
    given, family = name
    return f"{family} {given}" if order == FF else f"{given} {family}"


def parliament_lists() -> dict[str, dict[str, list[str]]] | None:
    """The opensanctions-parliaments names by dataset and script, Latin
    and Cyrillic rows of form "name" only, or None where not fetched."""
    path = local("opensanctions-parliaments") / "raw.jsonl"
    if not path.exists():
        return None
    lists: dict[str, dict[str, list[str]]] = {}
    for r in _rows(path):
        if r.get("form") == "name" and r.get("script") in ("Latin", "Cyrillic"):
            lists.setdefault(r["dataset"], {}).setdefault(
                r["script"], []).append(r["name"])
    return dict(sorted(lists.items()))


# -- one population's measurement (a worker) ---------------------------------

@contextlib.contextmanager
def _thresholds(overrides: dict[str, float]) -> Iterator[None]:
    """`_suggest`'s thresholds overridden for the block, and restored
    after it: a run with --jobs 1 measures in the caller's process."""
    from nameparser import _suggest
    before = {name: getattr(_suggest, name) for name in overrides}
    try:
        for name, value in overrides.items():
            setattr(_suggest, name, value)
        yield
    finally:
        for name, value in before.items():
            setattr(_suggest, name, value)


def _bases() -> dict[str, Any]:
    from nameparser import FAMILY_FIRST, Parser, Policy
    return {GF: Parser(), FF: Parser(policy=Policy(name_order=FAMILY_FIRST))}


def _end(order: tuple[Any, ...]) -> str:
    from nameparser import Role
    return FF if order[0] is Role.FAMILY else GF


def measure_population(job: tuple[str, Pool, tuple[int, ...], int, int,
                                  dict[str, float], int]) -> dict[str, Any]:
    """One population's cells, signal counts and wrong words."""
    label, pool, sizes, trials, seed, overrides, wrong_words = job
    with _thresholds(overrides):
        return _measure_population(label, pool, sizes, trials, seed,
                                   wrong_words)


def _measure_population(label: str, pool: Pool, sizes: tuple[int, ...],
                        trials: int, seed: int, wrong_words: int
                        ) -> dict[str, Any]:
    from nameparser import PatronymicRule
    from nameparser._suggest import name_votes
    bases = _bases()
    lexicon = bases[GF].lexicon
    rng = group_rng(seed, label)
    cells: dict[str, list[float | None]] = {}
    east_slavic = 0
    for order in (GF, FF):
        row = {base: [] for base in bases}
        for size in sizes:
            if size > len(pool):
                for base in bases:
                    row[base].append(None)
                continue
            right = Counter[str]()
            for _ in range(trials):
                group = [written(t, order) for t in rng.sample(pool, size)]
                for base, parser in bases.items():
                    s = parser.suggest(group)
                    right[base] += _end(s.parser.policy.name_order) == order
                    east_slavic += PatronymicRule.EAST_SLAVIC in (
                        s.parser.policy.patronymic_rules)
            for base in bases:
                row[base].append(right[base] / trials)
        for base in bases:
            cells[f"{order}/{base}"] = row[base]
    signals: dict[str, dict[str, int]] = {}
    words: dict[str, dict[str, list[tuple[str, int]]]] = {}
    sample = random.Random(f"{seed}-{label}-signals").sample(
        pool, min(SIGNAL_NAMES, len(pool)))
    for order in (GF, FF):
        truth = bases[order].policy.name_order
        stats: Counter[str] = Counter()
        wrong: dict[str, Counter[str]] = {}
        for t in sample:
            text = written(t, order)
            votes = name_votes(text, lexicon)
            ends = {v for s, v in votes.items() if s.value != "patronymic"}
            stats["names"] += 1
            if not ends:
                stats["name:none"] += 1
            elif len(ends) > 1:
                stats["name:contested"] += 1
            else:
                stats["name:right" if ends == {truth} else "name:wrong"] += 1
            for signal, vote in votes.items():
                if signal.value == "patronymic":
                    stats[f"patronymic:{vote.value}"] += 1  # type: ignore[union-attr]
                    continue
                ok = vote == truth
                stats[f"{signal.value}:{'right' if ok else 'wrong'}"] += 1
                if not ok:
                    w = text.split()
                    at = w[0] if (signal.value in ("surname", "particle", "capitals")
                                  ) == (_end(vote) == FF) else w[-1]  # type: ignore[arg-type]
                    wrong.setdefault(signal.value, Counter())[at] += 1
        signals[order] = dict(stats)
        words[order] = {s: c.most_common(wrong_words) for s, c in wrong.items()}
    return {"label": label, "size": len(pool), "cells": cells,
            "signals": signals, "words": words, "east_slavic": east_slavic}


#: The populations whose names the romanized surname table is for.
EAST_ASIAN = frozenset({"pv-CN", "pv-TW", "pv-KR", "pv-JP", "psc-Chinese", "vi"})
#: The short romanized surnames that are common words or given names
#: elsewhere, which --checks counts.
SHORT_SURNAMES = frozenset({"do", "to", "la", "le", "ha", "ho", "an"})
#: What --checks tries as a wider fold: the two letters NFKD leaves.
_STROKES = str.maketrans({"ø": "o", "ł": "l"})


def check_population(job: tuple[str, Pool, tuple[int, ...], int, int,
                                dict[str, float]]) -> dict[str, Any]:
    """--checks: the deferred per-name checks over one population's
    whole pool, written both ways, and the patronymic share's two
    denominators over a draw of groups of its own."""
    label, pool, sizes, trials, seed, overrides = job
    with _thresholds(overrides):
        return _check_population(label, pool, sizes, trials, seed)


def _check_population(label: str, pool: Pool, sizes: tuple[int, ...],
                      trials: int, seed: int) -> dict[str, Any]:
    from nameparser import FAMILY_FIRST, GIVEN_FIRST, Lexicon
    from nameparser._suggest import (
        Signal, _patronymic_winner, _Tally, fold, name_votes,
    )
    from nameparser.config._order_names import COMMON_GIVEN_NAMES
    lexicon = Lexicon.default()
    wider = frozenset(w.translate(_STROKES) for w in COMMON_GIVEN_NAMES)
    c: Counter[str] = Counter()
    words: Counter[str] = Counter()
    cache: dict[tuple[str, str], dict[Signal, Any]] = {}

    def listed(word: str, table: frozenset[str], widen: bool) -> bool:
        spelling = fold(word.strip("."))
        if widen:
            spelling = spelling.translate(_STROKES)
        return len(spelling) >= 2 and spelling in table

    for order, truth in ((GF, GIVEN_FIRST), (FF, FAMILY_FIRST)):
        for t in pool:
            text = written(t, order)
            w = text.split()
            votes = cache[t, order] = name_votes(text, lexicon)
            c["names"] += 1
            if (vote := votes.get(Signal.SURNAME)) is not None:
                word = fold((w[0] if vote == FAMILY_FIRST else w[-1]).strip("."))
                region = "east-asian" if label in EAST_ASIAN else "other"
                ok = "right" if vote == truth else "wrong"
                c[f"surname:{region}:{ok}"] += 1
                if ok == "wrong":
                    c["surname:short:wrong"] += word in SHORT_SURNAMES
                    if region == "other":
                        words[word] += 1
            if len(w) >= 2 and len(w[-1]) == 1 and w[-1].isalpha():
                c["bare-letter:" + ("ascii" if w[-1].isascii() else "other")] += 1
            if len(w) >= 2:
                # the given-name signal's test, both ways round; a comma
                # name reads alike under both, casting no vote at all
                first, last = (listed(x, wider, True) for x in (w[0], w[-1]))
                new = None if first == last else (GIVEN_FIRST if first else FAMILY_FIRST)
                first, last = (listed(x, COMMON_GIVEN_NAMES, False)
                               for x in (w[0], w[-1]))
                old = None if first == last else (GIVEN_FIRST if first else FAMILY_FIRST)
                if new != old:
                    c["fold:" + ("right" if new == truth else "away")] += 1
    # the patronymic share's denominator: every name casting a vote, or
    # those less the names whose only evidence is a contested order
    rng = random.Random(f"{seed}-{label}-checks")
    for order in (GF, FF):
        for size in sizes:
            if size > len(pool):
                continue
            moved = 0
            for _ in range(trials):
                tally, voters, contested_only = _Tally(), 0, 0
                for t in rng.sample(pool, size):
                    votes = cache[t, order]
                    voters += bool(votes)
                    ends = {v for k, v in votes.items() if k is not Signal.PATRONYMIC}
                    contested_only += len(ends) > 1 and Signal.PATRONYMIC not in votes
                    tally.add([(k, v) for k, v in votes.items()
                               if k is Signal.PATRONYMIC])
                moved += (_patronymic_winner(tally, voters)
                          != _patronymic_winner(tally, voters - contested_only))
            c["denominator:groups"] += trials
            c["denominator:moved"] += moved
            c["denominator:worst-cell"] = max(c["denominator:worst-cell"],
                                              round(1000 * moved / trials))
    return {"label": label, "counts": dict(c), "words": words.most_common(8)}


def report_checks(results: list[dict[str, Any]]) -> None:
    total: Counter[str] = Counter()
    words: Counter[str] = Counter()
    for r in results:
        worst = r["counts"].pop("denominator:worst-cell", 0)
        total["denominator:worst-cell"] = max(total["denominator:worst-cell"], worst)
        total.update(r["counts"])
        words.update(dict(r["words"]))
    t = total
    print(f"\n-- deferred checks, every population's whole pool written both "
          f"ways: {t['names']} names")
    print(f"surname votes, East Asian populations ({', '.join(sorted(EAST_ASIAN))}): "
          f"{t['surname:east-asian:right']} right, {t['surname:east-asian:wrong']} wrong; "
          f"other populations: {t['surname:other:right']} right, "
          f"{t['surname:other:wrong']} wrong")
    surname_votes = sum(v for k, v in t.items() if k.startswith("surname:")
                        and not k.startswith("surname:short"))
    print(f"wrong surname votes from {', '.join(sorted(SHORT_SURNAMES))}: "
          f"{t['surname:short:wrong']} of {surname_votes} surname votes")
    print("wrong surname votes outside East Asian populations, by word: "
          + ", ".join(f"{w} {n}" for w, n in words.most_common(8)))
    print(f"a name ending in a bare letter: {t['bare-letter:other']} non-ASCII "
          f"(no trailing-initial vote), {t['bare-letter:ascii']} ASCII")
    print(f"folding ø and ł as o and l on both sides moves {t['fold:right']} "
          f"given-name votes to right and {t['fold:away']} away from it ("
          + ", ".join(f"{r['label']} {r['counts']['fold:right']}/"
                      f"{r['counts'].get('fold:away', 0)}"
                      for r in sorted(results, key=lambda r: -r["counts"].get(
                          "fold:right", 0))[:3] if r["counts"].get("fold:right"))
          + ")")
    print(f"patronymic share without the contested-only names: "
          f"{t['denominator:moved']} of {t['denominator:groups']} groups decide "
          f"another rule; worst cell {t['denominator:worst-cell'] / 10:.1f}%")


def _policy(rules: tuple[str, ...], order: str | None) -> Policy:
    import nameparser
    from nameparser import PatronymicRule, Policy
    kwargs: dict[str, Any] = {"patronymic_rules": frozenset(
        PatronymicRule[r] for r in rules)}
    if order is not None:
        kwargs["name_order"] = getattr(nameparser, order)
    return Policy(**kwargs)


def _turkic_truth(dataset: str, name: str) -> str | None:
    words = name.split()
    if len(words) < 2:
        return None
    convention = TURKIC_CONVENTION[dataset]
    if convention == "caps":
        caps = [w for w in words if w.isupper()]
        return caps[0] if len(caps) == 1 else None
    return words[0] if convention == "first" else words[-1]


def measure_parliaments(lists: dict[str, dict[str, list[str]]],
                        overrides: dict[str, float]) -> dict[str, Any]:
    with _thresholds(overrides):
        return _measure_parliaments(lists)


def _measure_parliaments(lists: dict[str, dict[str, list[str]]]
                         ) -> dict[str, Any]:
    from nameparser import Parser
    turkic = {}
    parsers = [(label, Parser(policy=_policy(rules, order)))
               for label, rules, order in TURKIC_POLICIES]
    for dataset in TURKIC_LISTS:
        names = [n for script in lists.get(dataset, {}).values() for n in script]
        scored = [(n, t) for n in names
                  if (t := _turkic_truth(dataset, n)) is not None]
        row = {label: sum(p.parse(n).family == t for n, t in scored)
               for label, p in parsers}
        suggested = Parser().suggest(names).parser
        row["suggest"] = sum(suggested.parse(n).family == t for n, t in scored)
        row["scored"] = len(scored)
        turkic[dataset] = row
    suggestions = []
    bases = _bases()
    for dataset, scripts in lists.items():
        for script, names in scripts.items():
            for base, parser in bases.items():
                s = parser.suggest(names)
                order, rules = s.evidence
                suggestions.append({
                    "dataset": dataset, "script": script, "base": base,
                    "names": len(names), "order": _end(order.value),  # type: ignore[arg-type]
                    "order_decided": order.decided,
                    "counts": [order.votes_for, order.votes_against,
                               order.contested, order.no_evidence],
                    "rules": sorted(r.value for r in rules.value),  # type: ignore[attr-defined]
                    "rules_decided": rules.decided,
                    "rule_counts": [rules.votes_for, rules.votes_against]})
    return {"turkic": turkic, "suggestions": suggestions}


def measure(pools: dict[str, Pool], lists: dict[str, dict[str, list[str]]] | None,
            sizes: tuple[int, ...], trials: int, seed: int,
            overrides: dict[str, float], jobs: int, wrong_words: int
            ) -> dict[str, Any]:
    work = [(label, pool, sizes, trials, seed, overrides, wrong_words)
            for label, pool in pools.items()]
    if jobs <= 1:
        results = [measure_population(job) for job in work]
        parl = measure_parliaments(lists, overrides) if lists else None
    else:
        with ProcessPoolExecutor(jobs) as ex:
            futures = [ex.submit(measure_population, job) for job in work]
            parl_future = (ex.submit(measure_parliaments, lists, overrides)
                           if lists else None)
            results = [f.result() for f in futures]
            parl = parl_future.result() if parl_future else None
    return {"sizes": list(sizes), "trials": trials, "seed": seed,
            "populations": results, "parliaments": parl}


# -- the report --------------------------------------------------------------

def _pct(x: float | None, places: int = 0) -> str:
    width = 6 + places + bool(places)
    return " " * (width - 1) + "-" if x is None else f"{x:{width}.{places}%}"


def report(result: dict[str, Any], show_words: bool) -> None:
    sizes = result["sizes"]
    print(f"\n-- groups suggested right, {result['trials']} trials a cell "
          f"(seed {result['seed']}); written order / base order")
    print(f"{'population':14} {'written':7} {'base':4} "
          + " ".join(f"{n:>6}" for n in sizes) + "   names")
    for p in result["populations"]:
        for key, row in p["cells"].items():
            order, base = key.split("/")
            mark = "  <- anti-goal row" if order == base and any(
                x is not None and x < 0.95 for x in row) else ""
            print(f"{p['label']:14} {order:7} {base:4} "
                  + " ".join(_pct(x) for x in row) + f"   {p['size']}{mark}")
        if p["east_slavic"]:
            print(f"{'':14} (the East Slavic rule was decided in "
                  f"{p['east_slavic']} groups, and forced a given-first order)")
    print(f"\n-- votes per name (right/wrong/contested/none) and per signal "
          f"(right/wrong), at most {SIGNAL_NAMES} names")
    for p in result["populations"]:
        for order, st in p["signals"].items():
            n = st.get("names", 0) or 1
            parts = [f"names {st.get('name:right', 0)}/{st.get('name:wrong', 0)}/"
                     f"{st.get('name:contested', 0)}/{st.get('name:none', 0)} "
                     f"({st.get('name:wrong', 0) / n:.1%} wrong)"]
            for signal in ("capitals", "trailing-initial", "particle",
                           "surname", "given-name"):
                r, w = st.get(f"{signal}:right", 0), st.get(f"{signal}:wrong", 0)
                if r or w:
                    parts.append(f"{signal} {r}/{w}")
            for k, v in sorted(st.items()):
                if k.startswith("patronymic:"):
                    parts.append(f"{k} {v}")
            print(f"{p['label']:14} {order}: " + ", ".join(parts))
            if show_words:
                for signal, ws in p["words"][order].items():
                    if ws:
                        print(f"{'':18} wrong {signal}: "
                              + ", ".join(f"{w} {c}" for w, c in ws))
    parl = result["parliaments"]
    if parl is None:
        return
    labels = [label for label, _, _ in TURKIC_POLICIES] + ["suggest"]
    print("\n-- decisions/group-suggestion TURKIC: family right of the scored names")
    print(f"{'list':24} " + " ".join(f"{label:>9}" for label in labels))
    for dataset, row in parl["turkic"].items():
        print(f"{dataset:24} " + " ".join(
            f"{row[label]:>4}/{row['scored']:<4}" for label in labels))
    print("\n-- every parliament list's suggestion (order: for/against/"
          "contested/none; by eye = the order the list writes)")
    for s in parl["suggestions"]:
        expected = LIST_ORDER.get(s["dataset"])
        rules = ",".join(s["rules"]) or "none"
        verdict = ("" if expected is None else
                   "  rule" if s["rules_decided"] and "east-slavic" in s["rules"]
                   else "  ok" if s["order"] == expected else "  WRONG")
        print(f"{s['dataset']:24} {s['script']:8} base {s['base']} "
              f"n={s['names']:<5} by eye {expected or '?'}  order "
              f"{s['order']}{'' if s['order_decided'] else ' (undecided)'} "
              f"{'/'.join(map(str, s['counts']))}  rules {rules}"
              f"{'' if s['rules_decided'] else ' (undecided)'}{verdict}")


def moved(base: dict[str, Any], head: dict[str, Any]) -> list[str]:
    """The cells that differ between two runs of the same draw."""
    old = {p["label"]: p["cells"] for p in base["populations"]}
    out = []
    for p in head["populations"]:
        for key, row in p["cells"].items():
            before = old.get(p["label"], {}).get(key)
            if before != row:
                out.append(f"{p['label']:14} {key:6} "
                           + " ".join(_pct(x, 1) for x in before or [])
                           + "  ->  " + " ".join(_pct(x, 1) for x in row))
    return out


def _overrides(items: list[str]) -> dict[str, float]:
    out: dict[str, float] = {}
    for item in items:
        name, _, value = item.partition("=")
        if name not in SETTABLE or not value:
            raise SystemExit(f"--set takes NAME=VALUE with NAME one of "
                             f"{', '.join(SETTABLE)}, got {item!r}")
        out[name] = int(value) if name in _COUNTS else float(value)
    return out


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--sizes", default=",".join(map(str, SIZES)),
                    help="group sizes, comma-separated")
    ap.add_argument("--trials", type=int, default=TRIALS)
    ap.add_argument("--seed", type=int, default=SEED)
    ap.add_argument("--set", action="append", default=[], metavar="NAME=VALUE",
                    help=f"override one of {', '.join(SETTABLE)}")
    ap.add_argument("--wrong-words", type=int, default=0, metavar="N",
                    help="each signal's N commonest words in a wrong vote")
    ap.add_argument("--jobs", type=int, default=os.cpu_count() or 1)
    ap.add_argument("--checks", action="store_true",
                    help="print the per-name checks instead of the tables")
    ap.add_argument("--base", metavar="PATH",
                    help="list the cells that moved against this checkout")
    ap.add_argument("--tree", metavar="PATH", help=argparse.SUPPRESS)
    ap.add_argument("--json", type=Path, help=argparse.SUPPRESS)
    args = ap.parse_args(argv)
    sizes = tuple(int(n) for n in args.sizes.split(","))
    overrides = _overrides(args.set)
    tree = Path(args.tree).resolve() if args.tree else REPO_ROOT
    if args.tree:
        sys.path.insert(0, str(tree))
    import nameparser
    snapshot.check_source(nameparser.__file__, tree)
    pools, notes = load_pools(args.seed)
    for note in notes:
        print(note)
    lists = parliament_lists()
    if lists is None:
        print("opensanctions-parliaments: not fetched; uv run python "
              "tools/differential/local_corpora.py fetch opensanctions-parliaments")
    if args.checks:
        work = [(label, pool, sizes, args.trials, args.seed, overrides)
                for label, pool in pools.items()]
        if args.jobs <= 1:
            report_checks([check_population(job) for job in work])
        else:
            with ProcessPoolExecutor(args.jobs) as ex:
                report_checks(list(ex.map(check_population, work)))
        return 0
    if overrides:
        print("thresholds overridden: " + ", ".join(
            f"{k}={v}" for k, v in overrides.items()))
    result = measure(pools, lists, sizes, args.trials, args.seed, overrides,
                     args.jobs, args.wrong_words)
    if args.json:
        args.json.write_text(json.dumps(result), encoding="utf-8")
        return 0
    print(f"head: {tree}")
    report(result, args.wrong_words > 0)
    if args.base:
        base_root = snapshot.base_root(args.base, tree)
        with tempfile.TemporaryDirectory() as scratch:
            out = Path(scratch) / "base.json"
            command = [sys.executable, str(Path(__file__).resolve()),
                       "--tree", str(base_root), "--json", str(out),
                       "--sizes", args.sizes, "--trials", str(args.trials),
                       "--seed", str(args.seed), "--jobs", str(args.jobs),
                       *(f"--set={s}" for s in args.set)]
            done = subprocess.run(command, env=snapshot.child_env(),
                                  capture_output=True, text=True)
            if done.returncode:
                raise SystemExit(f"reading {base_root} failed:\n"
                                 f"{done.stdout}{done.stderr}")
            base = json.loads(out.read_text(encoding="utf-8"))
        cells = moved(base, result)
        print(f"\n-- against the base {base_root}: {len(cells)} cells moved")
        for line in cells:
            print(line)
    return 0


if __name__ == "__main__":
    sys.exit(main())
