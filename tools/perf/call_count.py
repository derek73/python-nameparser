"""Count Python function calls for one parse, as tests/v2/test_benchmark.py
counts them.

WHY THIS IS IN THE TREE. #475 replaced a wall-clock benchmark with a
call-count budget, and the decision entry that justifies it quotes a
dozen numbers -- per interpreter, per module, per commit. The first
draft of that entry took them across several sessions with throwaway
scripts, on whichever interpreter was to hand, and published a table
that spliced one interpreter's "before" column onto another's "after".
Four of its eight module figures were wrong and its four stage figures
were off by 2x, none of it visible without the harness.

docs/design/AGENTS.md already asks for this: "Where an entry quotes
something that drifts, give the one-liner that recomputes it." This is
that one-liner. Every number in decisions.md#parse-cost comes from a
mode of this script, named beside it.

    uv run python tools/perf/call_count.py                 # both entry points
    uv run python tools/perf/call_count.py --modules       # calls by module
    uv run python tools/perf/call_count.py --stages        # ms per 1000, per stage
    uv run python tools/perf/call_count.py --against REF   # this tree vs a git ref

The interpreter is printed with every result and belongs beside any
number quoted from it: the count is deterministic for a given
(tree, interpreter), not across interpreters. Measured 2026-08-31,
one parse of the reference name: 407 on 3.11, 385 on 3.12, 403 on
3.13/3.14/3.15 -- PEP 709 inlined the comprehension frames 3.11
counts, and 3.13 added others back.
"""
from __future__ import annotations

import argparse
import subprocess
import sys
import tempfile
import time
from collections.abc import Callable
from pathlib import Path

#: The name every figure is quoted for. Fixed width on purpose: an
#: incrementing counter grows a digit and adds one call as it does, so
#: a mean over N names is a function of N rather than of the parser.
REFERENCE = "Dr. Juan{i:04d} de la Vega III"


def calls_for(fn: Callable[[str], object], n: int = 50) -> float:
    """Mean Python frame entries for one parse of the reference name."""
    fn("warm up the caches")
    calls = 0

    def counter(frame: object, event: str, arg: object) -> None:
        nonlocal calls
        if event == "call":
            calls += 1

    sys.setprofile(counter)
    try:
        for i in range(n):
            fn(REFERENCE.format(i=i))
    finally:
        sys.setprofile(None)
    return calls / n


def by_module(fn: Callable[[str], object], n: int = 500) -> dict[str, float]:
    """Calls per parse attributed to each nameparser module."""
    import cProfile
    import pstats

    fn("warm up the caches")
    pr = cProfile.Profile()
    pr.enable()
    for i in range(n):
        fn(REFERENCE.format(i=i))
    pr.disable()
    out: dict[str, float] = {}
    for (path, _, _), stat in pstats.Stats(pr).stats.items():
        if "nameparser" in path:
            mod = path.split("nameparser/")[-1]
            out[mod] = out.get(mod, 0) + stat[0] / n
    return out


def by_stage(n: int = 1000) -> dict[str, float]:
    """Milliseconds per 1000 parses, per pipeline stage.

    Wall-clock, so unlike the counts above this drifts with the
    machine; quote it as a dated snapshot or not at all.
    """
    from nameparser import Lexicon, Policy
    from nameparser._pipeline import STAGES
    from nameparser._pipeline._state import ParseState

    lex, pol = Lexicon.default(), Policy()
    names = [REFERENCE.format(i=i) for i in range(n)]
    for name in names[:50]:
        state = ParseState(original=name, policy=pol, lexicon=lex)
        for stage in STAGES:
            state = stage(state)
    total: dict[str, float] = {}
    for name in names:
        state = ParseState(original=name, policy=pol, lexicon=lex)
        for stage in STAGES:
            start = time.perf_counter()
            state = stage(state)
            total[stage.__name__] = (total.get(stage.__name__, 0)
                                     + time.perf_counter() - start)
    return {k: v * 1000 * (1000 / n) for k, v in total.items()}


def _in_ref(ref: str, mode: str) -> str:
    """Run this script's own measurement inside a checkout of `ref`."""
    with tempfile.TemporaryDirectory() as tmp:
        subprocess.run(f"git archive {ref} | tar -x -C {tmp}",
                       shell=True, check=True)
        me = Path(tmp) / "tools" / "perf" / "call_count.py"
        if not me.exists():                     # ref predates this script
            me.parent.mkdir(parents=True, exist_ok=True)
            me.write_text(Path(__file__).read_text(encoding="utf-8"),
                          encoding="utf-8")
        done = subprocess.run(
            [sys.executable, str(me)] + ([mode] if mode else []),
            cwd=tmp, capture_output=True, text=True)
        return done.stdout.strip() or done.stderr.strip()


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--modules", action="store_true")
    ap.add_argument("--stages", action="store_true")
    ap.add_argument("--against", metavar="REF",
                    help="also measure a git ref, in its own checkout")
    args = ap.parse_args()
    version = f"{sys.version_info.major}.{sys.version_info.minor}"

    sys.path.insert(0, str(Path.cwd()))
    from nameparser import HumanName, parse

    if args.modules:
        for mod, count in sorted(by_module(HumanName).items(),
                                 key=lambda kv: -kv[1]):
            print(f"py{version}  {count:7.1f}  {mod}")
    elif args.stages:
        for stage, ms in sorted(by_stage().items(), key=lambda kv: -kv[1]):
            print(f"py{version}  {ms:7.1f}ms per 1000  {stage}")
    else:
        print(f"py{version}  parse={calls_for(parse):.2f}  "
              f"facade={calls_for(HumanName):.2f}")
    if args.against:
        mode = ("--modules" if args.modules
                else "--stages" if args.stages else "")
        print(f"--- {args.against} ---")
        print(_in_ref(args.against, mode))


if __name__ == "__main__":
    main()
