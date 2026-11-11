"""Write the romanized surname table the group suggester reads.

WHY THIS IS IN THE TREE. ``Parser.suggest`` reads a group of Latin-script
names and suggests a name order; a first word that is a known East Asian
surname is its evidence. The table, ``nameparser/config/_order_names.py``,
holds folded spellings: the generated block is the Hanyu Pinyin of every
single-character surname ``locales.ZH`` lists, from Unihan's first
``kMandarin`` reading (Unicode License v3), and the Wade-Giles, Korean and
Vietnamese lists are kept by hand above the generated block, hand-curated
and unchecked against any ranking (see the note in
nameparser/config/_order_names.py).

    uv run python tools/vocab/order_names.py           # print the block
    uv run python tools/vocab/order_names.py --write   # rewrite it
    uv run python tools/vocab/order_names.py --refresh # fetch Unihan again

The second generated block, ``COMMON_GIVEN``, is the given names the
suggester looks up at both ends of a name: per nam_dict country column
the ``TOP`` highest-band names that pass the filter, which keeps a name
of two letters or more written in ORCID's own family box at most
``MAX_FAMILY_SHARE`` of the ``MIN_USES`` or more times its holders wrote
it (a population the suggester is not tested on), and no romanized
surname this run writes. It needs nam_dict and the ORCID local corpus
cached (tools/name_usage.py and tools/differential/local_corpora.py),
each checked whole against its pinned or recorded sha256, and it writes
nothing where a block falls below its floor (``MIN_PINYIN``,
``MIN_GIVEN``) or a word lands in both tables.

Unihan is cached outside the repository with ``tools/zh_surnames.py``'s
copy ($NAMEPARSER_TOOLS_CACHE or ~/.cache/nameparser-tools).
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
import zipfile
from collections import Counter
from collections.abc import Iterable, Mapping
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parents[1]))
import name_usage  # noqa: E402  (a sibling script, not a package)

from nameparser._suggest import fold  # noqa: E402  (the one fold)

TOP = 500
MAX_FAMILY_SHARE = 0.05
MIN_USES = 20
ORCID_RAW = ("local", "orcid-researchers", "raw.jsonl")
#: The fewest entries a generated block may hold: a run that yields
#: fewer read an input cut short or changed, and writes nothing
#: (2026-11-10: 329 pinyin surnames, over 4,000 given names).
MIN_PINYIN = 200
MIN_GIVEN = 3_000

MODULE = Path(__file__).parents[2] / "nameparser" / "config" / "_order_names.py"
UNIHAN_URL = "https://www.unicode.org/Public/16.0.0/ucd/Unihan.zip"
UNIHAN_FILE = "unihan_16.0.0.zip"
UNIHAN_MEMBER = "Unihan_Readings.txt"


def read_mandarin(unihan_readings_text: str) -> dict[str, str]:
    """Each character's first ``kMandarin`` reading, tones folded."""
    out: dict[str, str] = {}
    for line in unihan_readings_text.splitlines():
        if line.startswith("#") or "\tkMandarin\t" not in line:
            continue
        source, _, readings = line.split("\t")
        out[chr(int(source[2:], 16))] = fold(readings.split()[0])
    return out


def pinyin_surnames(surnames: Iterable[str],
                    mandarin: Mapping[str, str]) -> set[str]:
    """The pinyin of the surnames that have one of two or more letters
    (a lone vowel such as 阿's ``a`` would match every initial)."""
    return {mandarin[s] for s in surnames
            if s in mandarin and len(mandarin[s]) >= 2}


def _markers(name: str) -> tuple[str, str]:
    return (f"# -- BEGIN generated: {name}; edit tools/vocab/order_names.py, "
            "not this block --",
            f"# -- END generated: {name} --")


def render_block(name: str, words: Iterable[str]) -> str:
    begin, end = _markers(name)
    ordered = sorted(set(words))
    rows = [", ".join(f'"{w}"' for w in ordered[i:i + 8])
            for i in range(0, len(ordered), 8)]
    body = "".join(f"    {row},\n" for row in rows)
    return f"{begin}\n_{name} = (\n{body})\n{end}"


def rewrite(module_text: str, name: str, block: str) -> str:
    begin, end = _markers(name)
    start, stop = module_text.find(begin), module_text.find(end)
    if start < 0 or stop < start:
        raise ValueError(f"{MODULE} has no generated block {name} to replace")
    return module_text[:start] + block + module_text[stop + len(end):]


def load_mandarin(refresh: bool) -> dict[str, str]:
    path = name_usage.cache_dir() / UNIHAN_FILE
    if refresh or not path.exists():
        name_usage._download(UNIHAN_URL, path, UNIHAN_MEMBER)
    with zipfile.ZipFile(path) as zf:
        return read_mandarin(zf.read(UNIHAN_MEMBER).decode("utf-8"))


def orcid_box_counts(path: Path) -> tuple[Counter[str], Counter[str]]:
    """Folded word counts of ORCID's given-name and family-name boxes,
    streamed (the file is about 1.8M lines). The file is refused unless
    it is whole: its sha256 and its record count are the ones the
    corpus's meta.json, written by the fetch, gives it."""
    meta_path = path.parent / "meta.json"
    try:
        meta = json.loads(meta_path.read_text(encoding="utf-8"))
        want_sha, want_records = meta["sha256"], meta["records"]
    except (OSError, ValueError, KeyError) as exc:
        raise ValueError(f"{meta_path} is missing or unreadable ({exc}); "
                         "fetch the orcid-researchers corpus again") from exc
    given: Counter[str] = Counter()
    family: Counter[str] = Counter()
    digest = hashlib.sha256()
    records = 0
    with open(path, "rb") as fh:
        for raw in fh:
            digest.update(raw)
            # cut at "\n" only, as corpus_build.jsonl_lines cuts
            line = raw.decode("utf-8")
            if not line.strip():
                continue
            records += 1
            record = json.loads(line)
            for box, counts in (("given", given), ("family", family)):
                for word in (record.get(box) or "").split():
                    counts[fold(word.strip(".,"))] += 1
    if records != want_records:
        raise ValueError(f"{path} holds {records} records, not the "
                         f"{want_records} its meta.json counts; fetch it again")
    if digest.hexdigest() != want_sha:
        raise ValueError(f"{path} does not match the sha256 in its "
                         "meta.json; fetch it again")
    return given, family


def common_given(namdict: name_usage.NamDict, given: Counter[str],
                 family: Counter[str], *, top: int, max_family_share: float,
                 min_uses: int, exclude: set[str]) -> set[str]:
    """Per nam_dict country, the ``top`` folded single-word names of
    highest band that pass the filter, unioned over the countries.

    A name passes with two or more letters, not in ``exclude``, at least
    ``min_uses`` uses across ORCID's two boxes and no more than
    ``max_family_share`` of them in the family box."""
    def passes(word: str) -> bool:
        total = given[word] + family[word]
        return (len(word) > 1 and word not in exclude and total >= min_uses
                and family[word] / total <= max_family_share)

    bands: dict[str, dict[str, int]] = {c: {} for c in namdict.countries}
    for entries in namdict.names.values():
        for listed, listed_bands in entries:
            if " " in listed or "+" in listed:
                continue
            word = fold(listed)
            for country, band in listed_bands.items():
                if band > bands[country].get(word, -1):
                    bands[country][word] = band
    chosen: set[str] = set()
    for ranked in bands.values():
        ordered = sorted(ranked.items(), key=lambda kv: (-kv[1], kv[0]))
        chosen.update([w for w, _ in ordered if passes(w)][:top])
    return chosen


def load_namdict() -> name_usage.NamDict:
    """nam_dict, read through name_usage, which checks the cached file
    against its pinned sha256; refused where it is not cached."""
    namdict = name_usage.load_namdict(download=False)
    if namdict is None:
        raise ValueError(
            f"{name_usage.cache_dir() / name_usage.NAMDICT_FILE} is not "
            "cached; uv run python tools/name_usage.py <word> fetches it")
    return namdict


def surname_exclusions(pinyin: set[str]) -> set[str]:
    """The surnames this run writes: the pinyin it computed and the
    hand lists, which the given names must not hold. Read from this
    run, not from the module it rewrites, which may be stale."""
    from nameparser.config import _order_names
    return pinyin | set(_order_names._ZH_OTHER_SPELLINGS
                        + _order_names._KO_SPELLINGS
                        + _order_names._VI_SURNAMES)


def load_common_given(exclude: set[str]) -> set[str]:
    given, family = orcid_box_counts(name_usage.cache_dir().joinpath(*ORCID_RAW))
    return common_given(
        load_namdict(), given, family, top=TOP,
        max_family_share=MAX_FAMILY_SHARE, min_uses=MIN_USES,
        exclude=exclude)


def check_tables(pinyin: set[str], given: set[str]) -> None:
    """Refuse a generated block below its floor, and a given name that
    is a surname too."""
    for words, floor, what in ((pinyin, MIN_PINYIN, "pinyin surnames"),
                               (given, MIN_GIVEN, "given names")):
        if len(words) < floor:
            raise ValueError(f"the run found {len(words)} {what}, below the "
                             f"floor of {floor}: an input is cut or changed")
    if both := pinyin & given:
        raise ValueError("a word is in both tables: "
                         + ", ".join(sorted(both)))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=(__doc__ or "").split("\n")[0])
    parser.add_argument("--write", action="store_true",
                        help="rewrite the generated block")
    parser.add_argument("--refresh", action="store_true",
                        help="fetch Unihan again")
    args = parser.parse_args(argv)
    from nameparser import locales
    singles = [s for s in locales.ZH.lexicon._sets.surnames if len(s) == 1]
    words = pinyin_surnames(singles, load_mandarin(args.refresh))
    given = load_common_given(surname_exclusions(words))
    check_tables(words, given)
    block = render_block("PINYIN", words)
    given_block = render_block("COMMON_GIVEN", given)
    print(block)
    print(given_block)
    if args.write:
        text = MODULE.read_text(encoding="utf-8")
        text = rewrite(text, "PINYIN", block)
        MODULE.write_text(rewrite(text, "COMMON_GIVEN", given_block),
                          encoding="utf-8")
        print(f"wrote {MODULE}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
