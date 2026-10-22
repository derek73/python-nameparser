"""What the labeled-corpus builders share: the fetch, the cache, the files they write.

The builders (build_cldr_corpus.py, build_gnd_corpus.py,
build_wikidata_corpus.py and build_wikidata_native_corpus.py) each write
a corpus file and a fields file in the same formats; every one but CLDR
caches its raw responses outside the repository the same way. Every
builder's network fetch goes through `fetch_bytes`. Not a builder itself: it writes nothing on import, and has
no main().

A builder imports it by name, after appending its own directory to
sys.path: that directory is usually sys.path[0] when a builder runs as a
script, but not under -P or PYTHONSAFEPATH (which AGENTS.md recommends
for comparisons) nor when the tests load a builder by path. It is
appended rather than inserted so that it cannot shadow a stdlib or
installed module; the cost is that an earlier `corpus_build` on sys.path
would shadow this one, and none exists.
"""
from __future__ import annotations

import hashlib
import json
import os
import time
import urllib.request
from collections.abc import Callable, Iterable, Mapping
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


def fetch_bytes(url: str, *, user_agent: str, timeout: int, data: bytes | None = None,
                headers: Mapping[str, str] | None = None, delay: float = 0) -> bytes:
    """The response body of `url` (a POST when `data` is given), sent
    with the builder's User-Agent and any further `headers`, then
    `delay` seconds of sleep: a builder that fetches in a row passes
    one, so that it stays gentle on the source. Raises what urllib
    raises. Looks up `urllib.request.urlopen` at call time, which is
    what lets the tests answer every fetch from one stub."""
    request = urllib.request.Request(
        url, data=data, headers={"User-Agent": user_agent, **(headers or {})})
    with urllib.request.urlopen(request, timeout=timeout) as response:
        body: bytes = response.read()
    if delay:
        time.sleep(delay)
    return body


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


#: The line breaks str.splitlines() cuts at and json.dumps(...,
#: ensure_ascii=False) writes unescaped, as JSON escapes for a writer to
#: put in their place: a name pasted from a document can hold one, and
#: written raw it would cut its line in two for a reader that splits
#: lines (AGENTS.md's Gotchas, #801).
LINE_BREAKS = str.maketrans({"\x85": "\\u0085", "\u2028": "\\u2028",
                             "\u2029": "\\u2029"})


def corpus_lines(rows: Iterable[dict[str, Any]]) -> list[str]:
    """One harness line per distinct (text, shape), sorted for stable
    diffs: a bare JSON string, or {"name", "shape"} where a shape is set."""
    pairs: set[tuple[str, int | None]] = set()
    for row in rows:
        shape = row["shape"]
        if shape is not None and not isinstance(shape, int):
            raise TypeError(f"shape must be an int or None, not {shape!r}")
        pairs.add((str(row["text"]), shape))
    # An untagged line sorts before every tagged one of the same text, so
    # the order never rests on set iteration (shape 0 would tie with None).
    return [(json.dumps(text, ensure_ascii=False) if shape is None
             else json.dumps({"name": text, "shape": shape}, ensure_ascii=False)
             ).translate(LINE_BREAKS)
            for text, shape in sorted(pairs, key=lambda p: (p[0], -1 if p[1] is None else p[1]))]


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
    """Write the corpus file and the fields file. Both are built, then
    written to .part files, before either is renamed into place, so a
    refused row (a duplicate rendering, a bad shape) or a failed write
    leaves the committed pair as it was; only a crash between the two
    renames could leave them out of step."""
    texts = {corpus: "\n".join(corpus_lines(rows)) + "\n",
             fields: "\n".join(fields_lines(rows)) + "\n"}
    parts = {path: path.with_name(path.name + ".part") for path in texts}
    try:
        for path, text in texts.items():
            parts[path].write_text(text, encoding="utf-8")
    except BaseException:
        for part in parts.values():  # beside the committed files: never leave one
            part.unlink(missing_ok=True)
        raise
    for path, part in parts.items():
        os.replace(part, path)
