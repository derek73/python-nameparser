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

from ._differential_fixtures import _entry_name


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

    corpus_cldr.jsonl joins it since #652: decomposed (NFD) renderings
    of its Slavic names, `Janez Novak, univ. dipl. inž.`, read
    differently from their composed twins until the shape regexes
    learned combining marks, and the decomposed-twin property test
    (tests/v2/test_properties.py) is the corpus-wide guard. Recorded
    negative control, measured 2026-10-12 with 04cc0814's nameparser/
    and this file's corpus: that test fails with five non-hangul texts
    parsing differently decomposed -- four from corpus_cldr.jsonl
    (`g. Janez Peter Novak ml., univ. dipl. inž.` and three more
    Slavic renderings) and `Dr. inž. Janez Novak` from
    corpus_rules.jsonl, which #652 added. Joining the file took
    test_properties.py from 34.5 s to 39.6 s before the fix and it
    runs in 39.8 s after (py3.11, local).
    """
    corpus_dir = Path(__file__).parents[2] / "tools" / "differential"
    paths = sorted(corpus_dir.glob("corpus*.jsonl"))
    assert paths, f"no corpus*.jsonl in {corpus_dir}"
    names = [_entry_name(json.loads(line))
             for path in paths
             for line in path.read_text().splitlines() if line.strip()]
    return list(dict.fromkeys(names))
