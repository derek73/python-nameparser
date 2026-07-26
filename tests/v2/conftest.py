"""Shared helpers for the tests/v2 package.

The parent suite's autouse `_isolate_constants` fixture
(tests/conftest.py) applies here ON PURPOSE: the v2 facade/shim tests
mutate the shared CONSTANTS singleton (tests/v2/test_config_shim.py),
so the snapshot/restore is wanted protection, not overhead. This
conftest once overrode the parent's dual-run fixture by name to skip
it -- that override went dead when the parent was renamed for #255,
and it was deleted rather than reconnected because its premise ("v2
code never reads shared CONSTANTS") had stopped being true.
"""
import json
from pathlib import Path


def differential_corpus() -> list[str]:
    """Every name the differential harness compares, from all of its
    corpus files.

    Globs `corpus*.jsonl` for the reason compare.py does: a corpus you
    have to ask for by name is one that stops being run. Two test
    modules had grown their own hard-coded `corpus.jsonl` loader, so
    both silently missed `corpus_issues.jsonl` -- 198 reported names,
    166 of them found nowhere else.

    tools/ is still not imported: it is a standalone uv-run script tree
    rather than a package, and the one-JSON-string-per-line format is
    cheaper to read than to make importable.
    """
    corpus_dir = Path(__file__).parents[2] / "tools" / "differential"
    paths = sorted(corpus_dir.glob("corpus*.jsonl"))
    assert paths, f"no corpus*.jsonl in {corpus_dir}"
    names = [json.loads(line)
             for path in paths
             for line in path.read_text().splitlines() if line.strip()]
    return list(dict.fromkeys(names))
