"""What the labeled-corpus builders share: the cache, the files they write.

build_cldr_corpus.py, build_gnd_corpus.py and build_wikidata_corpus.py
each write a corpus file and a fields file in the same formats, and the
two that query a live service cache its raw responses outside the
repository the same way. Not a builder itself: it writes nothing on
import, and has no main().

A builder imports it by name. Run as a script, a builder's own directory
is sys.path[0]; loaded by path in the tests (load_tool), it is not, so
each builder appends its directory first (append, not insert, so nothing
here can shadow another module of the same name).
"""
from __future__ import annotations

import hashlib
import json
import os
from collections.abc import Callable, Iterable
from pathlib import Path
from typing import Any


def cache_dir(name: str) -> Path:
    """The builder's cache directory, outside the repository:
    $NAMEPARSER_TOOLS_CACHE or ~/.cache/nameparser-tools, as
    tools/name_usage.py uses."""
    root = Path(os.environ.get("NAMEPARSER_TOOLS_CACHE",
                               Path.home() / ".cache" / "nameparser-tools"))
    path = root / name
    path.mkdir(parents=True, exist_ok=True)
    return path


def parse_json(body: bytes | str, source: str) -> object:
    """`body` parsed, or ValueError naming where it came from."""
    try:
        return json.loads(body)
    except ValueError as error:
        raise ValueError(f"{source} is not JSON ({error})") from None


def cached_json(cache: Path, key: str, label: str, fetch: Callable[[], bytes],
                check: Callable[[bytes | str, str], dict[str, Any]],
                refresh: bool) -> dict[str, Any]:
    """The response cached under `key`, or fetched and then cached.

    `check` parses a body and raises ValueError naming its source unless
    it is the response asked for; it runs on a cached body too, so a
    damaged file is named with the way out, and on a fetched one BEFORE
    it is cached, so an error answer (often HTTP 200) never is. The write
    is atomic: an interrupted run leaves no truncated cache file."""
    cached = cache / (hashlib.sha256(key.encode()).hexdigest()[:24] + ".json")
    if cached.exists() and not refresh:
        return check(cached.read_text(encoding="utf-8"),
                     f"{cached} (cached {label}; delete it or pass --refresh)")
    body = fetch()
    data = check(body, label)
    partial = cached.with_suffix(".part")
    partial.write_bytes(body)
    os.replace(partial, cached)
    return data


def corpus_lines(rows: Iterable[dict[str, Any]]) -> list[str]:
    """One harness line per distinct (text, shape), sorted for stable
    diffs: a bare JSON string, or {"name", "shape"} where a shape is set."""
    pairs: set[tuple[str, int | None]] = set()
    for row in rows:
        shape = row["shape"]
        if shape is not None and not isinstance(shape, int):
            raise TypeError(f"shape must be an int or None, not {shape!r}")
        pairs.add((str(row["text"]), shape))
    return [json.dumps(text, ensure_ascii=False) if shape is None
            else json.dumps({"name": text, "shape": shape}, ensure_ascii=False)
            for text, shape in sorted(pairs, key=lambda p: (p[0], p[1] or 0))]


def fields_lines(rows: Iterable[dict[str, Any]]) -> list[str]:
    """One line per rendering, sorted by its key (file/label/order, the
    key cldr_agreement.py records under). A key is unique per rendering;
    a duplicate means the source was misread."""
    keyed: dict[str, dict[str, Any]] = {}
    for row in rows:
        key = f"{row['file']}/{row['label']}/{row['order']}"
        if key in keyed:
            raise ValueError(f"duplicate rendering {key}")
        keyed[key] = row
    return [json.dumps(keyed[k], ensure_ascii=False, sort_keys=True)
            for k in sorted(keyed)]


def write_corpus(rows: list[dict[str, Any]], corpus: Path, fields: Path) -> None:
    """Write the corpus file and the fields file, always together."""
    corpus.write_text("\n".join(corpus_lines(rows)) + "\n", encoding="utf-8")
    fields.write_text("\n".join(fields_lines(rows)) + "\n", encoding="utf-8")
