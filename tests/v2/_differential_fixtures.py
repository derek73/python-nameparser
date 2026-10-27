"""Shared handles on tools/differential/: its corpora and its modules.

Neither is importable the ordinary way: `tools/` is outside
`testpaths` and is not a package, so its modules are loaded by path,
and the corpora are data files.

Not a conftest: these are constants and plain helpers, not fixtures in
pytest's sense, and several modules want them by name.
"""
import importlib.util
import json
import shutil
import sys
import time
import urllib.request
from pathlib import Path
from types import ModuleType
from typing import Any

import pytest

_TOOLS = Path(__file__).parents[2] / "tools" / "differential"


def _entry_name(raw: object) -> str:
    """A corpus line's name, whichever format the line uses: a bare
    JSON string or an object carrying "name"."""
    if isinstance(raw, str):
        return raw
    assert isinstance(raw, dict) and isinstance(raw.get("name"), str), raw
    return raw["name"]


#: Corpus files _CORPUS_NAMES leaves out. corpus_cldr.jsonl
#: (2026-10-12): about 1,900 fictional CLDR renderings whose ground
#: truth the agreement ratchet in test_cldr_agreement.py enforces. The
#: tests reading _CORPUS_NAMES carry counts measured over the names the
#: corpora held before it arrived.
_UNMEASURED_CORPORA = frozenset({"corpus_cldr.jsonl"})

#: Every corpus name, deduplicated, except the files in
#: _UNMEASURED_CORPORA.
_CORPUS_NAMES = sorted({
    _entry_name(json.loads(line))
    for path in sorted(_TOOLS.glob("corpus*.jsonl"))
    if path.name not in _UNMEASURED_CORPORA
    for line in path.read_text(encoding="utf-8").splitlines() if line.strip()})


def load_tool(stem: str) -> ModuleType:
    """A module from tools/differential/, loaded by path.

    `tools/` is outside testpaths, and adding it would run
    --doctest-modules over the corpus builders, so these are imported
    this way rather than made importable. Each main() is behind a
    __name__ guard; the one import-time effect is that a corpus builder
    appends its own directory to sys.path to find corpus_build.py (and
    local_corpora.py its local_core and local_<source> modules, which it
    imports under their bare names: a test reaches those with
    importlib.import_module, never a second load by path)."""
    spec = importlib.util.spec_from_file_location(
        f"differential_{stem}", _TOOLS / f"{stem}.py")
    assert spec is not None and spec.loader is not None, stem
    module = importlib.util.module_from_spec(spec)
    # Registered before it runs: @dataclass looks the module up in
    # sys.modules to check string annotations, and fails on a module
    # loaded by path that is not in it (local_corpora.py's dataclasses).
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


class _Response:
    """What urllib.request.urlopen returns, as far as the build scripts read it."""

    def __init__(self, body: bytes) -> None:
        self.body = body

    def __enter__(self) -> "_Response":
        return self

    def __exit__(self, *exc: object) -> None:
        return None

    def read(self) -> bytes:
        return self.body


def own_cache(monkeypatch: pytest.MonkeyPatch,
              tmp_path_factory: pytest.TempPathFactory) -> Path:
    """Point the tools' cache at a fresh scratch folder and return it:
    what each local-corpus test module's autouse fixture does, so that a
    test that forgets to set a cache, or a guard that stops keeping a
    test's corpus out of it, writes there rather than into the
    developer's real cache."""
    path = tmp_path_factory.mktemp("cache")
    monkeypatch.setenv("NAMEPARSER_TOOLS_CACHE", str(path))
    return path


def plant_corpus(monkeypatch: pytest.MonkeyPatch, corpora: ModuleType, source: str,
                 records: list[dict[str, str]], date: str, unit: str,
                 detail: dict[str, Any] | None = None) -> None:
    """`records` fetched as `source`'s local corpus into the cache, with no
    network: through a Source carrying the real one's credit and corpus
    keys and nothing else, so that none of the real source's renew or
    check applies in this process. A child process loads the corpus
    under the real Source, whose check reads `detail`, the meta.json
    detail it pins, and which refuses a corpus of other keys."""
    real = corpora.SOURCES[source]
    monkeypatch.setitem(corpora.SOURCES, source, corpora.Source(
        real.credit, unit,
        lambda: corpora.Fetched(list(records), date, dict(detail or {})),
        corpus_keys=real.corpus_keys))
    corpora.fetch(source)


def serve(monkeypatch: pytest.MonkeyPatch, tmp_path: Path, body: bytes, *,
          requests: list[urllib.request.Request] | None = None,
          sleeps: list[float] | None = None) -> list[str]:
    """Answer every urlopen with `body` and skip every sleep, cache into
    `tmp_path`, and return the list each fetched URL is appended to: the
    build scripts' network, offline. `requests` and `sleeps`, when given,
    collect every Request sent and every sleep asked for."""
    monkeypatch.setenv("NAMEPARSER_TOOLS_CACHE", str(tmp_path))
    monkeypatch.setattr(time, "sleep", (sleeps if sleeps is not None else []).append)
    fetched: list[str] = []

    def urlopen(request: urllib.request.Request, timeout: int) -> _Response:
        fetched.append(request.full_url)
        if requests is not None:
            requests.append(request)
        return _Response(body)
    monkeypatch.setattr(urllib.request, "urlopen", urlopen)
    return fetched


#: Appended to a copied package's __init__.py, a change every reading
#: shows: each name is parsed with its words reversed.
_PLANTED = """

_planted_parse = Parser.parse
Parser.parse = lambda self, text: _planted_parse(self, " ".join(reversed(text.split())))
"""


def checkout_copy(at: Path, *, planted: bool = False) -> Path:
    """A checkout at `at` holding a copy of this one's nameparser/
    package, and `planted`, a change every reading shows: a base tree
    for --base, which a child process reads, so that a check across a
    planted copy proves the base was read from its own tree."""
    shutil.copytree(_TOOLS.parents[1] / "nameparser", at / "nameparser",
                    ignore=shutil.ignore_patterns("__pycache__"))
    if planted:
        with open(at / "nameparser" / "__init__.py", "a", encoding="utf-8") as f:
            f.write(_PLANTED)
    return at
