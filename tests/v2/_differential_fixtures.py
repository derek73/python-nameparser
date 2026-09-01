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
#: file whose four hand copies went unchecked because the pins in
#: test_ledger_guards.py named the 1.4 one by filename, and the count grows by one per
#: release -- see AGENTS.md's release step 8.
_LEDGERS = sorted(_TOOLS.glob("expected_since_*.toml"))


def _entry_name(raw: object) -> str:
    """A corpus line's name, whichever format the line uses. Mirrors
    compare.py's _load_entries: a line is a bare JSON string or an
    object carrying "name"."""
    if isinstance(raw, str):
        return raw
    assert isinstance(raw, dict) and isinstance(raw.get("name"), str), raw
    return raw["name"]


#: Every name the harness classifies, deduplicated. The ledgers exist
#: to explain diffs on THESE strings and no others, so "what does this
#: rule claim?" is answerable here without parsing anything -- a plain
#: regex search, no baseline wheel, no network.
#:
#: This is what test_ledger_guards.py's corpus checks read, and why
#: they hold where four rounds of syntactic ones did not. Depth-0 pipes, nesting
#: levels and probe strings are all proxies for the question that
#: actually matters; a rule cannot widen its corpus reach and still
#: answer this one the same way, however it is spelled.
_CORPUS_NAMES = sorted({
    _entry_name(json.loads(line))
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


def _exclusions(ledger: Path) -> list[dict]:
    """The [[never]] table of one ledger.

    Same .get default as _rules and for the same reason: a ledger with
    no exclusions is the normal case, not a malformed file.
    """
    return tomllib.loads(
        ledger.read_text(encoding="utf-8")).get("never", [])


def load_tool(stem: str) -> ModuleType:
    """A module from tools/differential/, loaded by path.

    `tools/` is outside testpaths, and adding it would run
    --doctest-modules over the corpus builders, so these are imported
    this way rather than made importable. Two callers need it and
    wrote the same six lines each: test_differential.py for compare.py,
    test_ledger_guards.py for build_cjk_corpus.py.

    None of them has import-time side effects -- compare.py's main() is
    behind a __name__ guard, and build_cjk_corpus.py only defines
    functions -- so importing them to read a constant or call one
    function is safe.
    """
    spec = importlib.util.spec_from_file_location(
        f"differential_{stem}", _TOOLS / f"{stem}.py")
    assert spec is not None and spec.loader is not None, stem
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module
