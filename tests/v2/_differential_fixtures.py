"""Shared handles on tools/differential/: its corpora and its modules.

Neither is importable the ordinary way: `tools/` is outside
`testpaths` and is not a package, so its modules are loaded by path,
and the corpora are data files.

Not a conftest: these are constants and plain helpers, not fixtures in
pytest's sense, and several modules want them by name.
"""
import importlib.util
import json
from pathlib import Path
from types import ModuleType

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
    this way rather than made importable. None has import-time side
    effects: each main() is behind a __name__ guard."""
    spec = importlib.util.spec_from_file_location(
        f"differential_{stem}", _TOOLS / f"{stem}.py")
    assert spec is not None and spec.loader is not None, stem
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module
