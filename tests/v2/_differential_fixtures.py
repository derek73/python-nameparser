"""Shared handles on the differential harness's own data.

Imported by tests/v2/test_ledger_guards.py and tests/v2/test_differential.py,
which both need to reach `tools/differential/` -- the ledgers, the
corpora, and compare.py itself. Neither is importable the ordinary way:
`tools/` is outside `testpaths` and is not a package, so compare.py is
loaded by path, and the ledgers and corpora are data files a Python
module could not import if it wanted to.

Not a conftest: these are constants and plain helpers, not fixtures in
pytest's sense, and two modules want them by name. Not a test module
either -- the guards that keep this data honest live next to the tests
that rely on it, in test_ledger_guards.py.
"""
import importlib.util
import json
import re
import tomllib
from pathlib import Path
from types import ModuleType

from nameparser import _policy

_TOOLS = Path(__file__).parents[2] / "tools" / "differential"

#: Every baseline's ledger, swept rather than named. #332 added a second
#: file whose four hand copies went unchecked because the pins below
#: named the 1.4 one by filename, and the count grows by one per
#: release -- see AGENTS.md's release step 8.
_LEDGERS = sorted(_TOOLS.glob("expected_since_*.toml"))

#: Every name the harness classifies, deduplicated. The ledgers exist
#: to explain diffs on THESE strings and no others, so "what does this
#: rule claim?" is answerable here without parsing anything -- a plain
#: regex search, no baseline wheel, no network.
#:
#: This is what the guards below check against, and it is why they hold
#: where four rounds of syntactic ones did not. Depth-0 pipes, nesting
#: levels and probe strings are all proxies for the question that
#: actually matters; a rule cannot widen its corpus reach and still
#: answer this one the same way, however it is spelled.
_CORPUS_NAMES = sorted({
    json.loads(line)
    for path in sorted(_TOOLS.glob("corpus*.jsonl"))
    for line in path.read_text(encoding="utf-8").splitlines() if line.strip()})


def _claimed(name_regex: str) -> list[str]:
    """Corpus names a rule's regex matches."""
    return [name for name in _CORPUS_NAMES if re.search(name_regex, name)]


def _unclassified_names() -> list[str]:
    """Corpus names carrying no codepoint _SCRIPT_RANGES classifies."""
    has_classified = _policy._script_matcher(*_policy._SCRIPT_RANGES)
    return [name for name in _CORPUS_NAMES if not has_classified(name)]


#: Built once. The expression this replaced sat inside a
#: comprehension's condition, so it rebuilt the script matcher AND
#: rescanned all 751 names per candidate name rather than per rule --
#: measured around 400x a frozenset lookup, machine-dependent. The
#: rescan was the cost; the rebuild alone is minor.
_UNCLASSIFIED_NAMES = frozenset(_unclassified_names())


def _rules(ledger: Path) -> list[dict]:
    """The [[change]] table of one ledger."""
    # .get, matching compare.py. The open cycle's ledger is created at
    # release with no `change` key at all -- an empty [[change]] array
    # cannot be appended to in TOML -- so an absent key IS the empty
    # ledger here, not a malformed file. What stops that leniency from
    # hiding a typo'd table header lives in tests/v2/test_differential.py:
    # every other ledger must be non-empty, and the open one may define
    # nothing but `change`.
    return tomllib.loads(
        ledger.read_text(encoding="utf-8")).get("change", [])


def load_compare() -> ModuleType:
    """compare.py, loaded by path.

    `tools/` is outside testpaths, and adding it would run
    --doctest-modules over the corpus builders, so the harness is
    imported this way rather than made importable. It has no
    import-time side effects: its main() is behind a __name__ guard.
    """
    spec = importlib.util.spec_from_file_location(
        "differential_compare", _TOOLS / "compare.py")
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module
