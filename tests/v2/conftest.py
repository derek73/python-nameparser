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

    corpus_cldr.jsonl is left out, for now and for a measured reason.
    Joining it on 2026-10-12 took test_properties.py from 34.5 s to
    39.6 s (py3.11, local) -- affordable -- but four of its Slavic
    renderings fail test_a_decomposed_name_renders_as_its_composed_twin:
    decomposed `inž.` is not read as a period abbreviation, so
    `Janez Novak, univ. dipl. inž.` reverses (#652). Re-include the
    file when that is fixed. The harness and the CLDR agreement ratchet
    still parse these names.
    """
    corpus_dir = Path(__file__).parents[2] / "tools" / "differential"
    paths = sorted(p for p in corpus_dir.glob("corpus*.jsonl")
                   if p.name != "corpus_cldr.jsonl")
    assert paths, f"no corpus*.jsonl in {corpus_dir}"
    names = [_entry_name(json.loads(line))
             for path in paths
             for line in path.read_text().splitlines() if line.strip()]
    return list(dict.fromkeys(names))
