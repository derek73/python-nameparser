"""The case table's `parity` rows against the released 1.4.0 wheel.

    uv run python tools/differential/parity_check.py [--check] [--cases PATH]

A row of tests/v2/cases.py whose `classification` is "parity" (the
dataclass default) claims that nameparser 1.4.0 read its text as the
row expects. The suite runs every row against the TREE, so nothing
there checks that claim, and a row written against master and left on
the default passes for good (root AGENTS.md, Gotchas). This reads each
such row's text with 1.4.0's `HumanName`, installed fresh from PyPI
into a temporary folder, and lists the rows whose expected fields
1.4.0 does not give, with the field, the expected value and 1.4.0's.

What it compares, exactly:

- The seven fields, mapped from 1.4.0's attributes: title, given
  (`first`), middle, family (`last`), suffix, nickname and maiden. A
  field the row does not list is expected empty, as the suite reads
  it. Nothing else: not ambiguities, which 1.4.0 has none of, nor
  `initials()` or the case views.
- The suffix with its ", " joins read as spaces on both sides, and
  nothing else of its punctuation dropped. 1.4.0 renders a suffix of
  several words joined with ", " (`PhD, I.`) where the tree keeps the
  separators written in the name (`PhD I.`); the same words in the same
  order are the same reading, and a separator is how it renders. A
  comma that ends a word in only one of them (`Jr.,` against `Jr.`) is
  no join, and counts. A word moved into or out
  of the suffix, or reordered, still counts.
- Only the rows with neither a `policy` nor a `locale`. 1.4.0 has no
  `Policy`, so no switch on a row has a counterpart there to translate
  into; every such parity row is skipped, and the report gives their
  count. Such a row's `parity` stays unchecked here.

The rows are loaded from the cases file (by path: it is not
importable as a module of a package), and 1.4.0 is read in a child
process, generated into a temporary folder outside the checkout and
run by `uv run --no-project` with PYTHONPATH and PYTHONHOME stripped and
PYTHONSAFEPATH=1, which aborts unless the child reports version 1.4.0
from a file outside the checkout (compare.py's `_check_tell`). A child
answering from the tree would read every row as the suite does, and the
run would report no mismatch -- the null result a broken harness and a
clean table share. So every run also reads two planted rows: one whose
expectation 1.4.0 gives and one whose expectation it does not, and
aborts unless exactly the second is reported.

It needs the network or uv's cache for the wheel, so it is no CI test;
tests/v2/test_parity_check.py tests the mapping, the comparison and the
report against a stubbed baseline. It exits 0 whatever it finds, and 1
on a mismatch with --check.
"""
from __future__ import annotations

import argparse
import importlib.util
import json
import subprocess
import sys
import tempfile
from collections.abc import Callable, Iterable, Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from types import ModuleType
from typing import Any

HERE = Path(__file__).resolve().parent
REPO_ROOT = HERE.parents[1]
CASES = REPO_ROOT / "tests" / "v2" / "cases.py"
BASELINE = "1.4.0"

#: The case table's fields, in Role order, each with 1.4.0's attribute.
FIELDS = {"title": "title", "given": "first", "middle": "middle",
          "family": "last", "suffix": "suffix", "nickname": "nickname",
          "maiden": "maiden"}

#: The two rows every run reads beside the table's (ids no row can
#: take, being no identifier): 1.4.0 reads `John Smith` given 'John',
#: family 'Smith', so the first must match and the second be reported.
PLANTED_MATCH = "<planted: 1.4.0 gives this>"
PLANTED_WRONG = "<planted: 1.4.0 does not give this>"
_PLANTED = {PLANTED_MATCH: {"given": "John", "family": "Smith"},
            PLANTED_WRONG: {"given": "Smith", "family": "John"}}
_PLANTED_TEXT = "John Smith"


@dataclass(frozen=True)
class Row:
    """A parity row as compared: its id, text and expected fields, the
    seven of them, empty where the row lists none."""
    id: str
    text: str
    expect: Mapping[str, str]


@dataclass(frozen=True)
class Mismatch:
    row: Row
    #: field -> (expected, 1.4.0's), for each field that differs
    fields: Mapping[str, tuple[str, str]]


@dataclass(frozen=True)
class Result:
    mismatches: tuple[Mismatch, ...]
    compared: int
    #: ids of the parity rows carrying a policy or a locale
    skipped: tuple[str, ...]


def load_cases(path: Path = CASES) -> ModuleType:
    """tests/v2/cases.py, loaded by path. Registered in sys.modules
    before it runs, since @dataclass looks its module up there."""
    name = "parity_check_cases"
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec is not None and spec.loader is not None, path
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def select(cases: Iterable[Any]) -> tuple[list[Row], list[str]]:
    """The parity rows 1.4.0 can be asked about, and the ids of those
    it cannot: a row with a policy or a locale (the docstring says
    why). A row of any other classification is neither."""
    rows: list[Row] = []
    skipped: list[str] = []
    for case in cases:
        if case.classification != "parity":
            continue
        if case.policy is not None or case.locale is not None:
            skipped.append(case.id)
            continue
        rows.append(Row(case.id, case.text,
                        {f: case.expect.get(f, "") for f in FIELDS}))
    return rows, skipped


def from_v1(reading: Mapping[str, str]) -> dict[str, str]:
    """A 1.4.0 reading, keyed by its attribute names, as the seven
    fields; an attribute the reading lacks is empty."""
    return {field: reading.get(attr, "") or "" for field, attr in FIELDS.items()}


def suffix_words(text: str) -> tuple[str, ...]:
    """A suffix as its words in order, each ", " join read as a space:
    `PhD, I.` and `PhD I.` are one reading (the docstring says why),
    while a comma ending the suffix, or a word not followed by a space
    (`Jr.,`, `MD,PhD`), stays part of its word."""
    return tuple(text.replace(", ", " ").split())


def differ(row: Row, got: Mapping[str, str]) -> dict[str, tuple[str, str]]:
    """Each field whose expected value 1.4.0's reading `got` (the seven
    fields) does not give, with both values."""
    out = {}
    for field in FIELDS:
        want, have = row.expect[field], got.get(field, "")
        same = (suffix_words(want) == suffix_words(have) if field == "suffix"
                else want == have)
        if not same:
            out[field] = (want, have)
    return out


#: Reads texts and returns one 1.4.0 reading (keyed by its attribute
#: names) per text, in order: run_baseline, or a test's stub.
Reader = Callable[[Sequence[str]], list[dict[str, str]]]


def check(cases: Iterable[Any], read: Reader) -> Result:
    """Every parity row of `cases` that 1.4.0 can be asked about, read
    by `read`, with the planted rows; aborts unless the planted rows
    come back as planted -- the match matching and the wrong one
    reported -- since otherwise a run reporting nothing proves nothing."""
    rows, skipped = select(cases)
    planted = [Row(i, _PLANTED_TEXT, {f: e.get(f, "") for f in FIELDS})
               for i, e in _PLANTED.items()]
    every = rows + planted
    readings = read([r.text for r in every])
    if len(readings) != len(every):
        raise SystemExit(f"the baseline returned {len(readings)} readings "
                         f"for {len(every)} texts; aborted")
    found = []
    for row, reading in zip(every, readings):
        if (fields := differ(row, from_v1(reading))):
            found.append(Mismatch(row, fields))
    reported = {m.row.id for m in found} & set(_PLANTED)
    if reported != {PLANTED_WRONG}:
        raise SystemExit(
            f"the planted rows came back wrong (reported: "
            f"{sorted(reported) or 'none'}; expected only "
            f"{PLANTED_WRONG!r}): the baseline is not reading as 1.4.0 "
            f"does, so its answer for the table proves nothing. Aborted.")
    return Result(tuple(m for m in found if m.row.id not in _PLANTED),
                  len(rows), tuple(skipped))


_WORKER = '''\
# /// script
# requires-python = ">=3.9"
# dependencies = ["nameparser==@@VERSION@@"]
# ///
"""GENERATED by tools/differential/parity_check.py. Prints a version
tell, then one 1.4.0 reading per input line (a JSON string)."""
import json
import sys

import nameparser
from nameparser import HumanName

print(json.dumps({"__version__": nameparser.__version__,
                  "__file__": nameparser.__file__}), flush=True)
ATTRS = @@ATTRS@@
for line in sys.stdin:
    if not line.strip():
        continue
    name = HumanName(json.loads(line))
    print(json.dumps({a: getattr(name, a, "") or "" for a in ATTRS},
                     ensure_ascii=False), flush=True)
'''


def worker_source(version: str = BASELINE) -> str:
    return (_WORKER.replace("@@VERSION@@", version)
            .replace("@@ATTRS@@", repr(tuple(FIELDS.values()))))


def _compare() -> ModuleType:
    """compare.py beside this file, loaded by path for its version tell
    and its child environment, so the two harnesses hold one check."""
    spec = importlib.util.spec_from_file_location(
        "parity_check_compare", HERE / "compare.py")
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def worker_env(compare: ModuleType) -> dict[str, str]:
    """compare.py's child environment (PYTHONPATH and PYTHONHOME
    stripped), with PYTHONSAFEPATH=1 so the script's own folder is not
    on the path either."""
    env: dict[str, str] = compare._worker_env()
    env["PYTHONSAFEPATH"] = "1"
    return env


def run_baseline(texts: Sequence[str],
                 version: str = BASELINE) -> list[dict[str, str]]:
    """Each text read by the released `version`'s HumanName, in a child
    run from a temporary folder outside the checkout; aborts unless the
    child reports that version from outside the checkout."""
    compare = _compare()
    with tempfile.TemporaryDirectory() as tmp:
        script = Path(tmp) / "parity_worker.py"
        script.write_text(worker_source(version), encoding="utf-8")
        proc = subprocess.run(
            ["uv", "run", "--no-project", str(script)],
            input="".join(json.dumps(t, ensure_ascii=False) + "\n"
                          for t in texts),
            capture_output=True, text=True, cwd=tmp, env=worker_env(compare))
    if proc.returncode != 0:
        raise SystemExit(f"the {version} worker exited {proc.returncode}; "
                         f"aborted\n{proc.stderr}")
    lines = proc.stdout.split("\n")
    lines = [line for line in lines if line.strip()]
    if not lines:
        raise SystemExit(f"the {version} worker printed nothing; aborted")
    compare._check_tell(json.loads(lines[0]), version)
    return [json.loads(line) for line in lines[1:]]


def _line_of(row_id: str, source: str) -> int:
    """The line of `source` that first names `row_id` in quotes, or 0."""
    at = source.find(f'"{row_id}"')
    return source.count("\n", 0, at) + 1 if at >= 0 else 0


def report(result: Result, source: str = "") -> list[str]:
    """The run's report: each mismatching row with its line in the cases
    file (`source`), text and fields, then the counts."""
    out = []
    for m in result.mismatches:
        line = _line_of(m.row.id, source)
        where = f"cases.py:{line} " if line else ""
        out.append(f"{where}{m.row.id} {m.row.text!r}")
        for field, (want, have) in m.fields.items():
            out.append(f"    {field}: expected {want!r}, {BASELINE} {have!r}")
    out.append(f"{len(result.mismatches)} of {result.compared} parity rows "
               f"read otherwise under {BASELINE}")
    if result.skipped:
        out.append(f"{len(result.skipped)} parity rows carrying a policy or "
                   f"a locale skipped: {BASELINE} has no Policy to read "
                   f"them under")
    return out


def main(argv: Sequence[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--check", action="store_true",
                    help="exit 1 when a parity row reads otherwise")
    ap.add_argument("--cases", type=Path, default=CASES, metavar="PATH",
                    help="the cases file (default tests/v2/cases.py)")
    args = ap.parse_args(argv)
    result = check(load_cases(args.cases).CASES, run_baseline)
    print("\n".join(report(result, args.cases.read_text(encoding="utf-8"))))
    return 1 if args.check and result.mismatches else 0


if __name__ == "__main__":
    raise SystemExit(main())
