"""Shared handles on tools/differential/: its corpora and its modules.

Neither is importable the ordinary way: `tools/` is outside
`testpaths` and is not a package, so its modules are loaded by path,
and the corpora are data files.

Not a conftest: these are constants and plain helpers, not fixtures in
pytest's sense, and several modules want them by name.
"""
import importlib.util
import json
import time
import urllib.request
from pathlib import Path
from types import ModuleType

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
    appends its own directory to sys.path to find corpus_build.py."""
    spec = importlib.util.spec_from_file_location(
        f"differential_{stem}", _TOOLS / f"{stem}.py")
    assert spec is not None and spec.loader is not None, stem
    module = importlib.util.module_from_spec(spec)
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
