"""Every corpus check of a change, in sequence, with one summary.

What a parser change is measured with before its PR (AGENTS.md's
"Validating a new parsing rule"), run as one command rather than a
hand-written script per batch:

    uv run python tools/differential/measure.py --base ../master-checkout

The steps, in order, run one at a time so that no two contend for the
CPUs, each but cldr_agreement.py parallel inside itself (--jobs worker
processes):

1. the committed snapshot: snapshot.py, the check
   tests/v2/test_snapshot.py makes, printing every committed name that
   moved, grouped by field;
2. cldr_agreement.py, the CLDR and GND agreement records;
3. snapshot.py --local SOURCE --base, for every fetched local corpus;
4. local_agreement.py psc-individuals --base, where it is fetched;
5. local_corpora.py alike SOURCE --base, for every fetched corpus
   whose records pair two spellings of one person (ALIKE_SOURCES).

Only steps 3 to 5 read --base. Steps 1 and 2 compare the tree with the
records committed on its own branch, so once a branch has re-recorded
snapshot.jsonl (as it should once its moves are intended), step 1 says
"no moves" and the moves are in the PR's diff of that file instead; the
summary labels each step with what it compared against. A local corpus
that is not fetched gets no step, and the summary names it, and a run
in which no step read --base fails, since it measured nothing against
the base it was given.

A step that finds no move exits 0, one that finds moves 1, and anything
else is a failure the summary names. A tool refuses with
SystemExit("message"), which exits 1 like a move, so each step runs
through this script's --step wrapper, which turns a message exit or an
uncaught exception into exit 2: a broken step must not read as a
result.

Each step's output is written whole to its own file under --out (by
default a folder named for the time under the tools' cache, outside
the repository: a local corpus's moves are listed by name, and the
local corpora are never quoted). The summary, written beside them as
summary.txt and printed, keeps each step's unindented lines -- the
counts, the verdicts, the base and head lines, the attribution -- up to
SUMMARY_LINES of them, and none of the indented ones, which are where
the tools list names. An uncaught exception's message may hold a name,
so the wrapper prints its traceback indented and only its type flush
left.
"""
from __future__ import annotations

import argparse
import os
import subprocess
import sys
import time
from dataclasses import dataclass
from pathlib import Path

HERE = Path(__file__).resolve().parent
if str(HERE) not in sys.path:
    sys.path.append(str(HERE))
import corpus_build  # noqa: E402
import local_corpora  # noqa: E402

#: How many of a step's unindented lines the summary keeps: the first
#: HEAD_LINES (the attribution, the base and head lines) and the rest
#: from the end, where the tools print their verdicts.
SUMMARY_LINES = 12
HEAD_LINES = 4
#: Kept whatever the cap: a line saying part of a check was not read,
#: which "no moves" beside it would otherwise hide.
ALWAYS_KEPT = ("not measured", "not compared")
#: What a step's result is compared against, as the summary says it.
AGAINST_RECORD = "against this branch's committed record"
AGAINST_BASE = "against --base"


@dataclass(frozen=True)
class Step:
    label: str
    command: list[str]
    against: str = AGAINST_BASE


@dataclass(frozen=True)
class Done:
    step: Step
    code: int
    seconds: float
    output: str

    @property
    def status(self) -> str:
        return {0: "no moves", 1: "moves"}.get(self.code, f"FAILED (exit {self.code})")


def fetched(source: str) -> bool:
    """Whether `source` has been fetched into the cache: its step then
    runs, and refuses a damaged copy itself, naming the fetch."""
    return (local_corpora.directory(source, create=False) / local_corpora.META).exists()


def plan(base: Path, jobs: int) -> list[Step]:
    """The steps, in order, for the corpora fetched now, each run
    through --step (run_step())."""
    py = [sys.executable, str(HERE / "measure.py"), "--step"]
    tool = {name: str(HERE / f"{name}.py") for name in
            ("snapshot", "cldr_agreement", "local_agreement", "local_corpora")}
    j = ["--jobs", str(jobs)]
    steps = [Step("committed snapshot", [*py, tool["snapshot"], *j], AGAINST_RECORD),
             Step("CLDR and GND agreement", [*py, tool["cldr_agreement"]], AGAINST_RECORD)]
    sources = [s for s in sorted(local_corpora.SOURCES) if fetched(s)]
    steps += [Step(f"local snapshot {s}",
                   [*py, tool["snapshot"], "--local", s, "--base", str(base), *j])
              for s in sources]
    steps += [Step(f"agreement {s}", [*py, tool["local_agreement"], s, "--base", str(base), *j])
              for s in sources if s == local_corpora.PSC]
    steps += [Step(f"alike {s}", [*py, tool["local_corpora"], "alike", s, "--base",
                                  str(base), *j])
              for s in sources if s in local_corpora.ALIKE_SOURCES]
    return steps


def unmeasured() -> list[str]:
    """The local corpora plan() gives no step: those not fetched."""
    return [s for s in sorted(local_corpora.SOURCES) if not fetched(s)]


def run_step(tool: str, argv: list[str]) -> int:
    """Run `tool` as its own __main__ with `argv`, its exit code passed
    through where it is a number, and 2 where it exits with a message
    (a refusal) or raises: the code measure reads as a failure. A
    traceback is printed indented, below a flush-left line naming only
    the exception's type, since its message may hold a name."""
    import runpy
    import traceback
    sys.argv = [tool, *argv]
    try:
        runpy.run_path(tool, run_name="__main__")
    except SystemExit as exc:
        if exc.code is None or isinstance(exc.code, int):
            return exc.code or 0
        print(exc.code, file=sys.stderr)
        return 2
    except BaseException as exc:
        print(f"uncaught {type(exc).__name__}; its traceback, indented:", file=sys.stderr)
        for line in traceback.format_exc().splitlines():
            print(f"    {line}", file=sys.stderr)
        return 2
    return 0


def run(step: Step) -> Done:
    """`step` run from the checkout, its output read as bytes and decoded
    without newline translation, so that a carriage return in a name
    stays inside its line (digest)."""
    start = time.monotonic()
    done = subprocess.run(step.command, capture_output=True, cwd=HERE.parents[1])
    output = (done.stdout + done.stderr).decode("utf-8", errors="replace")
    return Done(step, done.returncode, time.monotonic() - start, output)


def digest(output: str) -> list[str]:
    """A step's unindented lines: the tools print counts and verdicts
    flush left and list names indented (snapshot.py's grouped moves,
    local_agreement.py's --list). Past SUMMARY_LINES, the first
    HEAD_LINES and the last of them, and every ALWAYS_KEPT line between.
    Cut at "\\n" only, never by str.splitlines(), which also cuts at a
    carriage return, U+2028 and the other line breaks a name can hold,
    and would bring the rest of that name to the left edge."""
    kept = [line for line in output.split("\n") if line.strip() and not line[0].isspace()]
    if len(kept) <= SUMMARY_LINES:
        return kept
    head, middle, tail = (kept[:HEAD_LINES], kept[HEAD_LINES:HEAD_LINES - SUMMARY_LINES],
                          kept[HEAD_LINES - SUMMARY_LINES:])
    shown = [line for line in middle if any(mark in line for mark in ALWAYS_KEPT)]
    return [*head, *shown, f"... {len(middle) - len(shown)} more lines", *tail]


def summary(results: list[Done], base: Path, skipped: list[str]) -> list[str]:
    lines = [f"measured {HERE.parents[1]}, {time.strftime('%Y-%m-%d %H:%M')}; "
             f"base: {base}", ""]
    for done in results:
        lines.append(f"== {done.step.label} ({done.step.against}): {done.status}, "
                     f"{done.seconds:.0f}s")
        lines += [f"   {line}" for line in digest(done.output)]
    failed = [d.step.label for d in results if d.code not in (0, 1)]
    lines += ["", f"{len(results)} steps, {sum(d.seconds for d in results):.0f}s; "
              + (f"failed: {', '.join(failed)}" if failed else "none failed")]
    if skipped:
        lines.append(f"not measured, not fetched: {', '.join(skipped)}")
    if not any(d.step.against == AGAINST_BASE for d in results):
        lines.append("no step read --base: no local corpus is fetched "
                     "(local_corpora.py fetch SOURCE)")
    return lines


def default_out() -> Path:
    return corpus_build.cache_dir("measure") / time.strftime("%Y%m%d-%H%M%S")


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--base", metavar="PATH",
                    help="the checkout the local-corpus steps measure against")
    ap.add_argument("--step", nargs=argparse.REMAINDER, help=argparse.SUPPRESS)
    ap.add_argument("--jobs", type=int, metavar="N", default=os.cpu_count() or 1,
                    help="worker processes inside each step (default: every CPU)")
    ap.add_argument("--out", type=Path, metavar="DIR",
                    help="where each step's output and the summary go (default: "
                         "a folder named for the time under the tools' cache)")
    args = ap.parse_args(argv)
    if args.step:
        return run_step(args.step[0], args.step[1:])
    if not args.base:
        ap.error("--base is required")
    from snapshot import REPO_ROOT, base_root
    base = base_root(args.base, REPO_ROOT)
    out = args.out or default_out()
    out.mkdir(parents=True, exist_ok=True)
    results = []
    for n, step in enumerate(plan(base, args.jobs), 1):
        print(f"[{n}] {step.label} ...", flush=True)
        done = run(step)
        (out / f"{n:02d}-{step.label.replace(' ', '-')}.txt").write_text(
            done.output, encoding="utf-8")
        print(f"    {done.status}, {done.seconds:.0f}s", flush=True)
        results.append(done)
    text = "\n".join(summary(results, base, unmeasured())) + "\n"
    (out / "summary.txt").write_text(text, encoding="utf-8")
    print(f"\n{text}\neach step's whole output is in {out}")
    failed = any(d.code not in (0, 1) for d in results)
    return 1 if failed or not any(d.step.against == AGAINST_BASE for d in results) else 0


if __name__ == "__main__":
    sys.exit(main())
