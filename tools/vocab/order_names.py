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

Unihan is cached outside the repository with ``tools/zh_surnames.py``'s
copy ($NAMEPARSER_TOOLS_CACHE or ~/.cache/nameparser-tools).
"""
from __future__ import annotations

import argparse
import sys
import zipfile
from collections.abc import Iterable, Mapping
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parents[1]))
import name_usage  # noqa: E402  (a sibling script, not a package)

from nameparser._suggest import fold  # noqa: E402  (the one fold)

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
    block = render_block("PINYIN", words)
    print(block)
    if args.write:
        text = MODULE.read_text(encoding="utf-8")
        MODULE.write_text(rewrite(text, "PINYIN", block), encoding="utf-8")
        print(f"wrote {MODULE}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
