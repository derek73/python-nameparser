"""List the Lexicon and Policy fields each pipeline stage reads, by tracing.

Each stage module's docstring declares a ``Reads:`` line, and the release
checklist (root AGENTS.md, step 0) has it checked. A grep for
``lexicon._sets.<field>`` in a module sees only the reads written there
in that spelling: it misses a read through a ``sets = lexicon._sets``
alias and every read a stage makes through a helper in ``_vocab`` or
``_pieces``. This tool sees those, because it watches the reads happen:
it runs every row of tests/v2/cases.py through the stages one by one,
with the parse's ``Lexicon`` and ``Policy`` wrapped in proxies that
record each attribute read, and charges each read to the stage running.

    uv run python tools/stage_reads.py                  # every stage
    uv run python tools/stage_reads.py --stage classify # one stage

Each line is one read and one case text that made it: ``L.<field>`` a
vocabulary set read through ``Lexicon._sets``, ``L!<name>`` anything
else read off the lexicon (a method, a public field), ``P.<field>`` a
``Policy`` field. ``group/_comma.decide`` holds the reads of C1's
decision, which group calls and which has a ``Reads:`` line of its own;
``script_segment/_comma.decide`` the same decision asked by script
segmentation, which also runs classify on a trial state, so classify's
reads are charged to it too.

What it cannot see: a read no case row reaches (a trace is as wide as the
table), and a read inside a ``Lexicon`` method, which is charged to the
method's name. Compare its list against the header by reading both.
"""
from __future__ import annotations

import argparse
import functools
import sys
from collections import defaultdict
from collections.abc import Callable, Iterable, Iterator
from contextlib import contextmanager
from pathlib import Path
from types import ModuleType
from typing import Protocol

ROOT = Path(__file__).resolve().parents[1]


class CaseLike(Protocol):
    text: str
    policy: object
    locale: str | None


#: Reads, per stage: read -> the first case text that made it.
Reads = dict[str, dict[str, str]]


class _Recorder:
    def __init__(self) -> None:
        self.reads: Reads = defaultdict(dict)
        self.where = "?"
        self.text = ""

    def record(self, read: str) -> None:
        self.reads[self.where].setdefault(read, self.text)


class _SetsProxy:
    def __init__(self, real: object, recorder: _Recorder) -> None:
        object.__setattr__(self, "_real", real)
        object.__setattr__(self, "_recorder", recorder)

    def __getattr__(self, name: str) -> object:
        self._recorder.record(f"L.{name}")
        return getattr(self._real, name)


class _LexiconProxy:
    def __init__(self, real: object, recorder: _Recorder) -> None:
        object.__setattr__(self, "_real", real)
        object.__setattr__(self, "_recorder", recorder)
        object.__setattr__(self, "_proxy_sets",
                           _SetsProxy(getattr(real, "_sets"), recorder))

    def __getattr__(self, name: str) -> object:
        if name == "_sets":
            return self._proxy_sets
        if not name.startswith("__"):
            self._recorder.record(f"L!{name}")
        return getattr(self._real, name)


class _PolicyProxy:
    def __init__(self, real: object, recorder: _Recorder) -> None:
        object.__setattr__(self, "_real", real)
        object.__setattr__(self, "_recorder", recorder)

    def __getattr__(self, name: str) -> object:
        if not name.startswith("__"):
            self._recorder.record(f"P.{name}")
        return getattr(self._real, name)


@contextmanager
def _charged_apart(module: ModuleType, name: str,
                   recorder: _Recorder) -> Iterator[None]:
    """Charge the reads made inside `module.name` to `<stage>/<module>.name`."""
    real: Callable[..., object] = getattr(module, name)
    label = f"{module.__name__.rsplit('.', 1)[-1]}.{name}"

    @functools.wraps(real)
    def charged(*args: object, **kwargs: object) -> object:
        outer = recorder.where
        if not outer.endswith(f"/{label}"):  # decide calls itself
            recorder.where = f"{outer}/{label}"
        try:
            return real(*args, **kwargs)
        finally:
            recorder.where = outer

    setattr(module, name, charged)
    try:
        yield
    finally:
        setattr(module, name, real)


def trace(cases: Iterable[CaseLike],
          assembled: Callable[[object], None] | None = None) -> Reads:
    """Run each case through the stages and assemble, recording reads.

    `assembled`, where given, is handed each case's ParsedName, which is
    how a test holds the traced fold to `Parser.parse`."""
    from nameparser import Parser, locales, parser_for
    from nameparser._pipeline import STAGES, _comma
    from nameparser._pipeline._assemble import assemble
    from nameparser._pipeline._state import ParseState

    recorder = _Recorder()
    with _charged_apart(_comma, "decide", recorder):
        for case in cases:
            if case.locale:
                pack = getattr(locales,
                               case.locale.upper().replace("-", "_"))
                parser = parser_for(pack)
            else:
                parser = Parser(policy=case.policy) if case.policy else Parser()
            recorder.text = case.text
            state = ParseState(
                original=case.text,
                lexicon=_LexiconProxy(parser.lexicon, recorder),  # type: ignore[arg-type]
                policy=_PolicyProxy(parser.policy, recorder),  # type: ignore[arg-type]
                segmenter=parser.segmenter)
            for stage in STAGES:
                recorder.where = stage.__name__
                state = stage(state)
            recorder.where = "assemble"
            name = assemble(state)
            if assembled is not None:
                assembled(name)
    return {stage: dict(reads) for stage, reads in recorder.reads.items()}


def _cases() -> tuple[CaseLike, ...]:
    sys.path.insert(0, str(ROOT))
    from tests.v2.cases import CASES
    return CASES


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=__doc__.split("\n\n", 1)[0] if __doc__ else None)
    parser.add_argument("--stage", help="one stage's reads only "
                        "(its function name, e.g. classify)")
    args = parser.parse_args(argv)
    reads = trace(_cases())
    stages = sorted(reads)
    if args.stage:
        stages = [s for s in stages
                  if s == args.stage or s.startswith(f"{args.stage}/")]
        if not stages:
            parser.error(f"no reads charged to {args.stage!r}; "
                         f"the stages are {sorted(reads)}")
    for stage in stages:
        print(f"== {stage}")
        for read in sorted(reads[stage]):
            print(f"   {read:<40} e.g. {reads[stage][read]!r}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
