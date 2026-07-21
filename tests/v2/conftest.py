"""Neutralize the v1 suite's autouse dual-run fixture for tests/v2.

tests/conftest.py runs every test twice (empty_attribute_default '' and
None) and deep-copy-snapshots the shared CONSTANTS around each test.
v2 code never reads shared CONSTANTS, so both behaviors are pure
overhead here. Overriding the fixture by name in this conftest replaces
the parametrized parent version for this directory.
"""
import json
from collections.abc import Iterator
from pathlib import Path

import pytest


@pytest.fixture(autouse=True)
def empty_attribute_default() -> Iterator[None]:
    yield


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
