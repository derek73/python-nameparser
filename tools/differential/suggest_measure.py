"""Measure Parser.suggest on groups of names whose written order is known.

`Parser.suggest(names)` reads a group of names a caller declares to share
one convention and suggests a `name_order` (and `patronymic_rules`). Its
decision rule (`_suggest._MIN_VOTES`, `_MIN_SHARE`,
`_MIN_PATRONYMIC_SHARE`, `_MIN_PATRONYMIC_VOTES`, the trailing-initial
signal's `_MIN_TRAILING_NAMES` and `_MIN_TRAILING_SHARE`, and for
`initials_as_family`, `_MIN_RUN_NAMES` and `_MIN_RUN_SHARE`) and its word tables
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
`prijmeni`), Vietnamese names (uit-vinames, the middle name before the
given name, as Vietnamese writes them) and ORCID credit names written as
a byline (orcid-researchers, `orcid-byline`: `Huntley R P`, the given
name its initials, the family name the box it matches; written
family-first it is the byline itself), and ORCID holders who typed one
box wholly in capitals and the other with none, in a name holding a
lowercase letter (rules/O9, #659): `orcid-famcaps` the family box
(`Jean DUPONT`, the convention `capitals_as_family` reads),
`orcid-famcaps-ea` the same from CN, KR, VN and TW, where many surnames
are two or three letters, and `orcid-givcaps` the given box (`ANNA
Smith`, the convention's other writing). A population keeps at most
POOL_CAP names, drawn by a seeded reservoir. A source not fetched is
left out with a note, as is one present that yields no names and each
population a present source yields none of; one present but unreadable
stops the run.

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
same-order rows, which must not fall below 95%, save orcid-byline's
given-first row and orcid-givcaps' two, which the capitals signal reads
the wrong way round at the base too. Under each population,
the groups that decided the East Slavic rule and the groups that decided
`initials_as_family` (rules/O8), each over every group of both written
orders and both bases; `--base` lists a population whose counts moved.
`--set _MIN_RUN_NAMES=1000000` decides the switch in no group. Then the
share of groups deciding `capitals_as_family` (rules/O9), per written
order, base and size, where any group did; `--base` lists every such
cell that moved. `--set _MIN_CAPITALS_LETTERS=1000000` decides it in no
group.

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
surnames (SHORT_SURNAMES) cast, and the names ending in a bare letter,
ASCII or not; and over a draw of groups of its own, of the groups that
hold enough names of one patronymic rule to decide it
(`_MIN_PATRONYMIC_VOTES`), how many decide another rule when the names
whose only evidence is a contested order leave the share's denominator.

`--set NAME=VALUE` overrides one of `_suggest`'s thresholds in every
worker, so a rule can be tried without editing the module (a `--base`
checkout without that threshold runs its own rule, and the comparison
says so); it is also the
harness's proof that it can report a difference: `--set
_MIN_VOTES=1000000 --set _MIN_PATRONYMIC_VOTES=1000000` decides nothing
(the first holds the order, the second the patronymic rule, which forces
an order of its own), so every family-first group under the given-first
base must read 0% (and every given-first group under the family-first
base). `--base` runs the same measurement against another
checkout in a child process and lists every cell that moved, every
population whose count of groups deciding the East Slavic rule moved,
and every TURKIC row and parliament suggestion that moved.

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
import re
import subprocess
import sys
import tempfile
import unicodedata
from collections import Counter
from collections.abc import Callable, Iterator
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from nameparser import Policy

HERE = Path(__file__).resolve().parent
if str(HERE) not in sys.path:
    sys.path.append(str(HERE))
import corpus_build  # noqa: E402
import local_corpora  # noqa: E402
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
            "_MIN_PATRONYMIC_VOTES", "_MIN_TRAILING_NAMES",
            "_MIN_TRAILING_SHARE", "_MIN_RUN_NAMES", "_MIN_RUN_SHARE",
            "_MIN_CAPITALS_LETTERS")
#: The thresholds that count names (or letters), read as int.
_COUNTS = ("_MIN_VOTES", "_MIN_PATRONYMIC_VOTES", "_MIN_TRAILING_NAMES",
           "_MIN_RUN_NAMES", "_MIN_CAPITALS_LETTERS")
#: The countries `orcid-famcaps-ea` reads.
EAST_ASIAN_COUNTRIES = frozenset({"CN", "KR", "VN", "TW"})

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


def _checked_rows(source: str) -> Iterator[dict[str, Any]]:
    """`source`'s raw.jsonl records, streamed, once local_corpora.load
    has checked the cache as every other reader of it does: its
    meta.json, the files' sha256 and the source's own check (a
    parliaments cache fetched from another dataset list is refused,
    which reading raw.jsonl alone let pass); FileNotFoundError where the
    source is not fetched, CorpusDamaged (a ValueError) where it is
    stale or damaged, both raised here rather than on the first record."""
    if local_corpora.load(source) is None:
        raise FileNotFoundError(2, "not fetched", str(local(source) / "raw.jsonl"))
    return _rows(local(source) / "raw.jsonl")


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


#: A line's country field, wherever the line puts it: the extract's
#: lines are JSON objects whose keys a writer may order any way.
_PV_COUNTRY = re.compile(r'"country":\s*"([^"]*)"')


def _patentsview(keep: _Reservoir) -> None:
    """The extract the patentsview-inventors fetch keeps, every name
    (local_patentsview.pv_boxes reads the same file, but decodes all of
    its 5.3 million lines; a line naming no wanted country is skipped
    here undecoded, its country found by a search rather than by its
    place in the line, and a decoded one must name the country it
    seemed to)."""
    import local_patentsview
    path = local_patentsview.extract_path()
    if not path.exists():
        raise FileNotFoundError(2, "not fetched", str(path))
    wanted = frozenset(PV_COUNTRIES)
    with gzip.open(path, "rt", encoding="utf-8", newline="\n") as lines:
        if json.loads(next(lines)).get("release") != local_patentsview.PV_RELEASE:
            raise ValueError(f"{path} is not an extract of the "
                             f"{local_patentsview.PV_RELEASE} release")
        for line in lines:
            found = _PV_COUNTRY.search(line)
            country = found[1] if found else None
            if country not in wanted:
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
    for r in _checked_rows("psc-individuals"):
        if (n := r.get("nationality")) in PSC_NATIONALITIES:
            given = f"{r.get('forename', '')} {r.get('middle_name', '')}"
            keep.add(f"psc-{n}", given, r.get("surname", ""))


def _cz(keep: _Reservoir) -> None:
    for r in _checked_rows("cz-candidates"):
        keep.add("cz", r.get("jmeno", ""), r.get("prijmeni", ""))


def _vi(keep: _Reservoir) -> None:
    for r in _checked_rows("uit-vinames"):
        keep.add("vi", f"{r.get('middle', '')} {r.get('given', '')}",
                 r.get("family", ""))


#: An initial a byline writes after the family name: one letter, with
#: or without its full stop, or letters joined by full stops or written
#: as two or three capitals (`R`, `R.`, `R.S.`, `RS`).
_BYLINE_INITIAL = re.compile(r"^(?:[^\W\d_]\.?|(?:[^\W\d_]\.)+[^\W\d_]?\.?|[A-Z]{2,3})$")


def _orcid(keep: _Reservoir) -> None:
    """The ORCID populations: the bylines, and the boxes typed one
    wholly in capitals (`_orcid_capitals`)."""
    from nameparser._pipeline._vocab import is_capitals_word
    for r in _checked_rows("orcid-researchers"):
        _orcid_capitals(keep, r, is_capitals_word)
        _orcid_byline(keep, r)


def _orcid_capitals(keep: _Reservoir, r: dict[str, Any],
                    is_capitals_word: Callable[[str], bool]) -> None:
    """A holder whose name holds a lowercase letter, one box every word
    of it in capitals (`_vocab.is_capitals_word`, rules/O9's test) and
    the other box none: `orcid-famcaps` (and `orcid-famcaps-ea`) where
    it is the family box, `orcid-givcaps` where it is the given box."""
    given = unicodedata.normalize("NFC", r.get("given") or "").split()
    family = unicodedata.normalize("NFC", r.get("family") or "").split()
    if not (given and family) or not any(
            c.islower() for w in given + family for c in w):
        return
    in_given = [is_capitals_word(w) for w in given]
    in_family = [is_capitals_word(w) for w in family]
    pair = (" ".join(given), " ".join(family))
    if all(in_family) and not any(in_given):
        keep.add("orcid-famcaps", *pair)
        if r.get("country") in EAST_ASIAN_COUNTRIES:
            keep.add("orcid-famcaps-ea", *pair)
    elif all(in_given) and not any(in_family):
        keep.add("orcid-givcaps", *pair)


def _orcid_byline(keep: _Reservoir, r: dict[str, Any]) -> None:
    """ORCID credit names written as a byline, the family name first and
    the given names as initials (`Huntley R P`, `Hoy AM`, `Smith J.`),
    each confirmed by the holder's own boxes: the word in front is the
    family box, and the first initial the given box's first letter. A
    pair keeps the initials as the given name, so written family-first
    it is the byline as the holder wrote it (#1254)."""
    credit, family, given = r.get("credit"), r.get("family"), r.get("given")
    if not (credit and family and given):
        return
    words = credit.split()
    if len(words) < 2 or not all(_BYLINE_INITIAL.match(w) for w in words[1:]):
        return
    if (words[0].casefold().replace("-", "")
            != family.strip().casefold().replace("-", "").replace(" ", "")):
        return
    if words[1][0].casefold() != given.strip()[:1].casefold():
        return
    keep.add("orcid-byline", " ".join(words[1:]), words[0])


SOURCES = (("patentsview-inventors", _patentsview),
           ("psc-individuals", _psc), ("cz-candidates", _cz),
           ("uit-vinames", _vi), ("orcid-researchers", _orcid))


#: The populations each source is read for.
WANTED = {"patentsview-inventors": tuple(f"pv-{c}" for c in PV_COUNTRIES),
          "psc-individuals": tuple(f"psc-{n}" for n in PSC_NATIONALITIES),
          "cz-candidates": ("cz",), "uit-vinames": ("vi",),
          "orcid-researchers": ("orcid-byline", "orcid-famcaps",
                                "orcid-famcaps-ea", "orcid-givcaps")}


def load_pools(seed: int) -> tuple[dict[str, Pool], list[str]]:
    """Every population fetched, and a note for each source that is
    not, each present source that yields no names and each population a
    present source yields none of. A source present but unreadable stops
    the run: a cut file is a broken measurement, not a smaller one."""
    keep = _Reservoir(seed)
    notes = []
    for source, read in SOURCES:
        try:
            read(keep)
        except FileNotFoundError as e:
            notes.append(f"{source}: not fetched ({e.filename}); "
                         f"uv run python tools/differential/local_corpora.py "
                         f"fetch {source}")
            continue
        except (OSError, ValueError, KeyError, EOFError) as e:
            raise SystemExit(f"{source}: present but unreadable "
                             f"({type(e).__name__}: {e}); fetch it again") from e
        empty = [label for label in WANTED[source]
                 if not keep.pools.get(label)]
        if len(empty) == len(WANTED[source]):
            notes.append(f"{source}: present, but no names read; is it the "
                         f"file this tool reads?")
        else:
            notes.extend(f"{label}: no names in {source}" for label in empty)
    pools = {label: pool for label, pool in keep.pools.items() if pool}
    return dict(sorted(pools.items())), notes


def written(name: tuple[str, str], order: str) -> str:
    given, family = name
    return f"{family} {given}" if order == FF else f"{given} {family}"


def parliament_lists() -> tuple[dict[str, dict[str, list[str]]] | None,
                                list[str]]:
    """The opensanctions-parliaments names by dataset and script, Latin
    and Cyrillic rows of form "name" only, or None where not fetched;
    and a note for each list the tables read that holds no such row."""
    try:
        rows = _checked_rows("opensanctions-parliaments")
    except FileNotFoundError:
        return None, []
    except ValueError as e:
        raise SystemExit(f"opensanctions-parliaments: present but unreadable "
                         f"({e})") from e
    lists: dict[str, dict[str, list[str]]] = {}
    for r in rows:
        if r.get("form") == "name" and r.get("script") in ("Latin", "Cyrillic"):
            lists.setdefault(r["dataset"], {}).setdefault(
                r["script"], []).append(r["name"])
    notes = [f"{dataset}: no names in opensanctions-parliaments"
             for dataset in sorted(set(TURKIC_LISTS) | set(LIST_ORDER))
             if dataset not in lists]
    return dict(sorted(lists.items())), notes


# -- one population's measurement (a worker) ---------------------------------

@contextlib.contextmanager
def _thresholds(overrides: dict[str, float]) -> Iterator[None]:
    """`_suggest`'s thresholds overridden for the block, and restored
    after it: a run with --jobs 1 measures in the caller's process."""
    from nameparser import _suggest
    # a threshold this tree does not have (a base checkout older than
    # the threshold) is left alone here: the tree runs its own rule, and
    # measure() records the name so the comparison says so
    before = {name: getattr(_suggest, name) for name in overrides
              if hasattr(_suggest, name)}
    overrides = {name: value for name, value in overrides.items()
                 if name in before}
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
    capitals: dict[str, list[float | None]] = {}
    east_slavic = letters = 0
    for order in (GF, FF):
        row = {base: [] for base in bases}
        caps_row = {base: [] for base in bases}
        for size in sizes:
            if size > len(pool):
                for base in bases:
                    row[base].append(None)
                    caps_row[base].append(None)
                continue
            right = Counter[str]()
            decided = Counter[str]()
            for _ in range(trials):
                group = [written(t, order) for t in rng.sample(pool, size)]
                for base, parser in bases.items():
                    s = parser.suggest(group)
                    right[base] += _end(s.parser.policy.name_order) == order
                    east_slavic += PatronymicRule.EAST_SLAVIC in (
                        s.parser.policy.patronymic_rules)
                    # rules/O8's switch (#1254) and rules/O9's (#659); a
                    # tree without the field reads False
                    letters += getattr(s.parser.policy,
                                       "initials_as_family", False)
                    decided[base] += getattr(s.parser.policy,
                                             "capitals_as_family", False)
            for base in bases:
                row[base].append(right[base] / trials)
                caps_row[base].append(decided[base] / trials)
        for base in bases:
            cells[f"{order}/{base}"] = row[base]
            capitals[f"{order}/{base}"] = caps_row[base]
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
            "signals": signals, "words": words, "east_slavic": east_slavic,
            "letters": letters,
            # only where some group decided it, so a population none
            # decides in compares equal against a tree without the switch
            "capitals": (capitals if any(x for row in capitals.values()
                                         for x in row) else {})}


#: The populations whose names the romanized surname table is for.
EAST_ASIAN = frozenset({"pv-CN", "pv-TW", "pv-KR", "pv-JP", "psc-Chinese", "vi"})
#: The short romanized surnames that are common words or given names
#: elsewhere, which --checks counts.
SHORT_SURNAMES = frozenset({"do", "to", "la", "le", "ha", "ho", "an"})


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
    from nameparser import _suggest
    from nameparser._suggest import (
        Signal, _patronymic_winner, _Tally, fold, name_votes,
    )
    _MIN_PATRONYMIC_VOTES = _suggest._MIN_PATRONYMIC_VOTES
    lexicon = Lexicon.default()
    c: Counter[str] = Counter()
    words: Counter[str] = Counter()
    cache: dict[tuple[str, str], dict[Signal, Any]] = {}

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
    # the patronymic share's denominator: every name casting a vote, or
    # those less the names whose only evidence is a contested order
    rng = random.Random(f"{seed}-{label}-checks")
    for order in (GF, FF):
        for size in sizes:
            if size > len(pool):
                continue
            moved = could = 0
            for _ in range(trials):
                tally, voters, contested_only = _Tally(), 0, 0
                for t in rng.sample(pool, size):
                    votes = cache[t, order]
                    voters += bool(votes)
                    ends = {v for k, v in votes.items() if k is not Signal.PATRONYMIC}
                    contested_only += len(ends) > 1 and Signal.PATRONYMIC not in votes
                    tally.add([(k, v) for k, v in votes.items()
                               if k is Signal.PATRONYMIC])
                # only a group holding enough names of one rule can
                # decide it under either denominator
                if max(tally.by_name.values(), default=0) < _MIN_PATRONYMIC_VOTES:
                    continue
                could += 1
                moved += (_patronymic_winner(tally, voters)
                          != _patronymic_winner(tally, voters - contested_only))
            c["denominator:groups"] += trials
            c["denominator:could"] += could
            c["denominator:moved"] += moved
            if could:
                c["denominator:worst-cell"] = max(
                    c["denominator:worst-cell"], round(1000 * moved / could))
    return {"label": label, "counts": dict(c), "words": words.most_common(8)}


def report_checks(results: list[dict[str, Any]], min_votes: int) -> None:
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
    print(f"patronymic share without the contested-only names: "
          f"{t['denominator:moved']} of {t['denominator:could']} groups that "
          f"could decide a rule (holding {min_votes} or more "
          f"names of one; {t['denominator:groups']} drawn) decide another; "
          f"worst cell {t['denominator:worst-cell'] / 10:.1f}%")


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
    if convention == "first":
        return words[0]
    # a name of three words ending in a standalone marker has no
    # surname: the father's name and the marker stand where it would
    # (#1253's first statement, rules/O2, #1187), as in kg_jogorku_kenesh's
    # three `уулу` names and one `кызы`
    from nameparser._pipeline._vocab import is_patronymic_marker
    if len(words) == 3 and is_patronymic_marker(words[-1]):
        return " ".join(words[-2:])
    return words[-1]


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
                # by setting, not position: a tree that suggests a
                # setting more (initials_as_family, #1254) adds an entry
                evidence = {e.setting: e for e in s.evidence}
                order = evidence["name_order"]
                rules = evidence["patronymic_rules"]
                row = {
                    "dataset": dataset, "script": script, "base": base,
                    "names": len(names), "order": _end(order.value),  # type: ignore[arg-type]
                    "order_decided": order.decided,
                    "counts": [order.votes_for, order.votes_against,
                               order.contested, order.no_evidence],
                    "rules": sorted(r.value for r in rules.value),  # type: ignore[attr-defined]
                    "rules_decided": rules.decided,
                    "rule_counts": [rules.votes_for, rules.votes_against]}
                letters = evidence.get("initials_as_family")
                # recorded only where decided, so a base that cannot
                # suggest it compares equal on every other list
                if letters is not None and letters.decided:
                    row["letters"] = [letters.votes_for, letters.votes_against]
                capitals = evidence.get("capitals_as_family")
                if capitals is not None and capitals.decided:
                    row["capitals"] = [capitals.votes_for,
                                       capitals.votes_against]
                suggestions.append(row)
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
    from nameparser import _suggest
    unknown = sorted(name for name in overrides
                     if not hasattr(_suggest, name))
    return {"unknown_settings": unknown,
            "sizes": list(sizes), "trials": trials, "seed": seed,
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
        if p.get("letters"):
            print(f"{'':14} (initials_as_family was decided in "
                  f"{p['letters']} groups)")
    caps = [p for p in result["populations"] if p.get("capitals")]
    if caps:
        print("\n-- groups deciding capitals_as_family (rules/O9), where "
              "any did; written order / base order")
        print(f"{'population':16} {'written':7} {'base':4} "
              + " ".join(f"{n:>6}" for n in sizes))
        for p in caps:
            for key, row in p["capitals"].items():
                order, base = key.split("/")
                print(f"{p['label']:16} {order:7} {base:4} "
                      + " ".join(_pct(x) for x in row))
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
    """What differs between two runs of the same draw: the cells, the
    groups that decided the East Slavic rule, the TURKIC table's rows
    and every parliament list's suggestion."""
    old = {p["label"]: p for p in base["populations"]}
    out = []
    for p in head["populations"]:
        was = old.get(p["label"], {})
        for key, row in p["cells"].items():
            before = was.get("cells", {}).get(key)
            if before != row:
                out.append(f"{p['label']:14} {key:6} "
                           + " ".join(_pct(x, 1) for x in before or [])
                           + "  ->  " + " ".join(_pct(x, 1) for x in row))
        if was.get("east_slavic") != p["east_slavic"]:
            out.append(f"{p['label']:14} east_slavic groups "
                       f"{was.get('east_slavic')} -> {p['east_slavic']}")
        if was.get("letters", 0) != p.get("letters", 0):
            out.append(f"{p['label']:14} initials_as_family groups "
                       f"{was.get('letters', 0)} -> {p.get('letters', 0)}")
        old_caps, new_caps = was.get("capitals") or {}, p.get("capitals") or {}
        for key in sorted(set(old_caps) | set(new_caps)):
            before, after = old_caps.get(key), new_caps.get(key)
            if before != after:
                out.append(f"{p['label']:14} capitals_as_family {key:6} "
                           + " ".join(_pct(x, 1) for x in before or [])
                           + "  ->  " + " ".join(_pct(x, 1) for x in after or []))
    parl_old, parl_new = base.get("parliaments") or {}, head.get("parliaments") or {}
    turkic_old = parl_old.get("turkic", {})
    for dataset, row in (parl_new.get("turkic") or {}).items():
        if turkic_old.get(dataset) != row:
            out.append(f"TURKIC {dataset}: {turkic_old.get(dataset)} -> {row}")
    def key(s: dict[str, Any]) -> tuple[Any, ...]:
        return (s.get("dataset"), s.get("script"), s.get("base"))
    sugg_old = {key(s): s for s in parl_old.get("suggestions", [])}
    for s in parl_new.get("suggestions", []):
        if sugg_old.get(key(s)) != s:
            out.append(f"suggestion {' '.join(map(str, key(s)))}: "
                       f"{sugg_old.get(key(s))} -> {s}")
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
    lists, list_notes = parliament_lists()
    for note in list_notes:
        print(note)
    if lists is None:
        print("opensanctions-parliaments: not fetched; uv run python "
              "tools/differential/local_corpora.py fetch opensanctions-parliaments")
    if args.checks:
        from nameparser import _suggest
        work = [(label, pool, sizes, args.trials, args.seed, overrides)
                for label, pool in pools.items()]
        min_votes = int(overrides.get("_MIN_PATRONYMIC_VOTES",
                                      _suggest._MIN_PATRONYMIC_VOTES))
        if args.jobs <= 1:
            report_checks([check_population(job) for job in work], min_votes)
        else:
            with ProcessPoolExecutor(args.jobs) as ex:
                report_checks(list(ex.map(check_population, work)), min_votes)
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
        if base.get("unknown_settings"):
            print(f"\nthe base has no {', '.join(base['unknown_settings'])}: "
                  f"--set left it to its own rule")
        print(f"\n-- against the base {base_root}: {len(cells)} cells moved")
        for line in cells:
            print(line)
    return 0


if __name__ == "__main__":
    sys.exit(main())
