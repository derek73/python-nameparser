"""Perf smoke: parse cost stays v1-comparable
(microseconds per name). Deliberately generous bound -- guards against
order-of-magnitude regressions, does not gate normal variance.

Two different things are measured here, and the distinction matters.
The thousand-names tests below bound ABSOLUTE cost on constant-size
input; the scaling test bounds GROWTH in input length. Neither
subsumes the other, and the absolute tests are structurally blind to a
complexity regression: their workload is a short name with no
delimiters, so a stage that goes quadratic in the number of delimiter
pairs stays far inside the one-second bound. Three such quadratics
(_extract's mask-overlap scan, ParsedName's token-subset check, and
_group's #329 clause scan) were caught in review rather than here --
hence the scaling test.

The third is why _POLICY_SHAPES exists below: it was quadratic in a
shape the scaling test ALREADY had ("(a) "), and still went unseen,
because the stage is gated on an opt-in Policy field that bare parse()
leaves empty. A shape guards nothing if the default policy cannot
reach the code under it.
"""
import sys
import time
from collections.abc import Callable

import pytest

from nameparser import Parser, parse
from nameparser._policy import Policy


#: What one parse of the reference name is allowed to cost, counted in
#: Python frame entries rather than seconds (#475). A wall-clock bound
#: cannot separate a 1% change from a busy CI runner: the 1.0s version
#: of these tests failed four times across #466 and #474 at 1.01-1.08s
#: while master re-ran green each time, and three local measurement
#: methods disagreed with CI and with each other. Frame counts do not
#: move under load, and -- measured -- do not move under `pytest --cov`
#: either, though coverage costs 3x on the clock.
#:
#: PER INTERPRETER, because the count is not machine-independent: PEP
#: 709 inlined the comprehension frames 3.11 counts, and 3.13 added
#: others back. A version with no row here fails loudly with its own
#: number rather than passing unguarded -- recording it is the point.
#:
#: A BAND, not a ceiling. A ceiling with headroom is another threshold
#: that happens to break, which is the failure this replaced: the 2.2
#: cycle's +67 calls arrived across a dozen PRs at roughly five each,
#: and no ceiling loose enough to be safe can see five. The band is
#: +/-2%, so a single PR's worth of growth lands in a diff with a
#: reason beside it. A DROP is a signal too, and trips the same test.
#:
#: Raising or lowering a row is a decision to record in
#: decisions.md#parse-cost, not a maintenance chore. Recompute with
#: `uv run python tools/perf/call_count.py`, which is the harness every
#: number in that entry comes from.
#:
#: Measured 2026-08-31 on this tree with that harness. 3.11 and 3.14
#: are the two interpreters on the author's machine; 3.12, 3.13 and
#: 3.15 are CI's, seeded from a review measurement and confirmed by
#: the first green run -- a wrong seed fails with the real number.
_CALL_BASELINE = {
    (3, 11): {"parse": 410, "facade": 447},
    (3, 12): {"parse": 388, "facade": 425},
    (3, 13): {"parse": 406, "facade": 443},
    (3, 14): {"parse": 406, "facade": 443},
    (3, 15): {"parse": 406, "facade": 443},
}
_BAND = 0.02

#: The reference name is fixed WIDTH, not merely fixed: an incrementing
#: counter grows a digit and costs one more call when it does, which
#: made the first draft's "mean over n names" a function of n rather
#: than of the parser.
_REFERENCE = "Dr. Juan{i:04d} de la Vega III"


def _calls_per_parse(fn: Callable[[str], object], n: int = 50) -> float:
    """Mean Python frame entries for one parse of the reference name.

    `sys.setprofile` counts Python frame entries -- NOT C calls, and not
    the interpreter's own work inside one frame -- so this measures the
    work the parser does rather than how fast the machine did it. Per
    parse there are roughly 575 `c_call` events this cannot see.

    Deterministic for a given tree AND interpreter: verified identical
    across repeated calls, fresh processes, PYTHONHASHSEED values, and
    with or without coverage installed.
    """
    fn("warm up the caches")
    calls = 0

    def counter(frame: object, event: str, arg: object) -> None:
        nonlocal calls
        if event == "call":
            calls += 1

    sys.setprofile(counter)
    try:
        for i in range(n):
            fn(_REFERENCE.format(i=i))
    finally:
        sys.setprofile(None)
    return calls / n


def _check_budget(kind: str, fn: Callable[[str], object]) -> None:
    """Assert one entry point sits inside its band.

    Skips rather than clobbers when something else owns the profile
    slot: `sys.setprofile(None)` in the helper CLEARS the hook, and a
    maintainer profiling the parser -- the very workflow that produced
    decisions.md#parse-cost -- would otherwise get silently truncated
    data. Restoring is not an option: `sys.getprofile()` hands back a
    `Profile` object that `sys.setprofile()` then refuses.
    """
    if sys.getprofile() is not None:
        pytest.skip("a profile hook is already installed; this test owns it")
    version = sys.version_info[:2]
    if version not in _CALL_BASELINE:
        actual = _calls_per_parse(fn)
        pytest.fail(
            f"no call baseline for Python {version[0]}.{version[1]}; "
            f"{kind} measures {actual:.1f} here. Add the row to "
            f"_CALL_BASELINE and record it in decisions.md#parse-cost")
    baseline = _CALL_BASELINE[version][kind]
    actual = _calls_per_parse(fn)
    low, high = baseline * (1 - _BAND), baseline * (1 + _BAND)
    assert low <= actual <= high, (
        f"{kind} costs {actual:.1f} calls/name on Python "
        f"{version[0]}.{version[1]}, band {low:.0f}-{high:.0f} around a "
        f"baseline of {baseline}. Growth and shrinkage are both signals: "
        f"recompute with tools/perf/call_count.py, then either make it "
        f"cheaper or move the baseline deliberately -- see "
        f"decisions.md#parse-cost")


def test_parse_cost_stays_within_its_band() -> None:
    _check_budget("parse", parse)


def test_facade_cost_stays_within_its_band() -> None:
    # the legacy-API path (what all existing users call): snapshot
    # resolution must stay generation-cached, not rebuilt per instance.
    # Measured: defeating that cache costs 4826 calls against this
    # band, while taking only 0.93s per 1000 -- which the 1.0s
    # wall-clock test this replaced would have PASSED.
    from nameparser import HumanName

    _check_budget("facade", HumanName)


@pytest.mark.parametrize("kind,fn", [
    ("parse", parse),
    ("facade", lambda name: __import__("nameparser").HumanName(name)),
])
def test_a_thousand_names_still_parse_in_reasonable_time(
        kind: str, fn: Callable[[str], object]) -> None:
    """The order-of-magnitude backstop the call bands do not give.

    Frame counts cannot see work that happens without entering a Python
    frame: a compiled regex that starts backtracking emits no `call`
    event at all, and neither does a C-level structure turning
    quadratic. (A quadratic inside a comprehension or generator IS
    visible -- `call` fires once per generator resume.) Both entry
    points are covered, because both failures that motivated #475 were
    on the facade and the first draft of this replacement guarded only
    `parse`.

    The bound is loose enough that runner variance cannot reach it: the
    failures were at 1.01-1.08s against 1.0, and coverage costs about
    3x, so 5s leaves roughly 5x of margin on the CI runner that failed.
    """
    fn("warm up the caches")
    start = time.perf_counter()
    for i in range(1000):
        fn(_REFERENCE.format(i=i))
    elapsed = time.perf_counter() - start
    assert elapsed < 5.0, f"1000 {kind} parses took {elapsed:.2f}s"


# Pathological shapes: each repeats a unit that drives one stage's inner
# loop. Cheap per unit, so a superlinear stage shows up as growth rather
# than as a slow parse.
#
# What each DIMENSION is covered by, measured at _BASE. Several shapes
# differ only in a column you cannot see from the string, so measure
# before pruning one that looks redundant:
#
#   dimension                 covered by
#   token count               all ten
#   piece count               unmatched_*, plain_tokens, commas, titles
#   SEGMENT count             commas ONLY -- deleting it leaves every
#                             segment-keyed regression unguarded
#   intra-piece accumulation  particles (one 799-token piece),
#                             conjunctions (800) -- the merge() quadratic
#   masked-span count         delimiter_pairs, quote_pairs (0 pieces:
#                             everything is consumed as a delimited run)
#   NON-ASCII input           honorifics ONLY -- every other unit here is
#                             pure ASCII, so script_segment returns at
#                             its isascii() bail and neither the #308
#                             peel nor the #271 surname site is measured
#                             at all. A repeated 씨 is what walks the
#                             peel's site scan: every token is a
#                             post-nominal, so the scan-back crosses the
#                             whole run before declining
#   P5 reserve                bound_given ONLY -- the one unit whose
#                             first piece is a bound given-name word,
#                             so the reserve's per-piece question is
#                             asked over the whole run (#401)
_SHAPES = {
    "delimiter_pairs": "(a) ",      # extract: matched pairs -> masked spans
    "quote_pairs": '"a" ',          # extract: the open==close path
    "unmatched_opens": "( ",        # extract: the bulk unmatched-open sweep
    "unmatched_closes": ") ",       # extract: the unmatched-close sweep
    "plain_tokens": "a ",           # tokenize/assign: long token stream
    "commas": "a, ",                # segment: many comma segments
    "titles": "Dr. ",               # group: one long title chain
    "particles": "van ",            # group: the prefix-chain inner loop
    "conjunctions": "and ",         # group: merge() accumulating one piece
    "honorifics": "씨 ",             # script_segment: the peel's site scan
    "bound_given": "abdul ",        # group: the P5 reserve over every piece
}

_BASE = 800
_FACTOR = 4
# Calibrated, not guessed, and calibrated against the WEAKEST signal.
#
# A quadratic here is MIXED -- linear work dominates at small sizes and
# the quadratic term takes over slowly -- so the textbook 16x never
# appears at a testable size, different quadratics surface at different
# strengths, and the operating point matters more than the bound.
# Measured against the two real bugs this guards, per shape, ratio for
# 4x the input:
#
#   base   clean      _extract mask-overlap   _group merge re-flatten
#    200   3.9 - 4.3          7.7                     5.6
#    400   4.0 - 4.3          9.2                 6.3 - 6.6
#    800   4.0 - 4.4         >9.2                 7.9 - 8.1
#
# The bound must clear the weakest column, not the first one measured.
# An earlier version calibrated 6.5 against _extract alone and then
# gained the conjunction shape, whose signal is 6.3-6.6 at base 400 --
# the bound landed on the MEDIAN of the broken distribution and caught
# the regression it was added for about half the time. Raising the base
# separates the populations again rather than squeezing the bound into
# a gap that is not there: at 800 the bound has ~1.4x over the worst
# clean run (noise headroom on a shared runner) and ~1.3x under the
# weakest quadratic. Re-derive BOTH numbers when adding a shape.
# The tenth shape (honorifics) was measured into the clean column when
# it arrived: 4.0-4.3 at base 800 across repeated runs, inside the range
# the ASCII shapes already occupy, so neither number moved. The
# eleventh (bound_given, #401) arrived with its own quadratic in hand:
# the P5 reserve rebuilt assign's walk per piece and measured 13.2 at
# base 800 -- well outside the bound, which is why it was found in
# review rather than here, no earlier unit leading with a bound word.
# Computed once, the shape reads 4.2, inside the clean column; neither
# number moved.
_MAX_RATIO = 6.0


def _best(text: str, parse_: Callable[[str], object],
          repeats: int = 7) -> float:
    """Minimum of several runs: on a shared runner the mean carries the
    noise of whatever else is running, while the minimum approaches the
    true cost."""
    parse_(text)                    # warm the parser cache
    best = float("inf")
    for _ in range(repeats):
        start = time.perf_counter()
        parse_(text)
        best = min(best, time.perf_counter() - start)
    return best


def _assert_grows_linearly(unit: str,
                           parse_: Callable[[str], object]) -> None:
    small = _best(unit * _BASE, parse_)
    large = _best(unit * (_BASE * _FACTOR), parse_)
    ratio = large / small
    assert ratio < _MAX_RATIO, (
        f"{unit!r} x{_BASE} took {small * 1e3:.2f}ms, "
        f"x{_BASE * _FACTOR} took {large * 1e3:.2f}ms -- {ratio:.1f}x for "
        f"{_FACTOR}x the input, which is superlinear (linear is ~{_FACTOR})")


@pytest.mark.parametrize("unit", _SHAPES.values(), ids=list(_SHAPES))
def test_parse_cost_grows_no_worse_than_linearly(unit: str) -> None:
    _assert_grows_linearly(unit, parse)


# Shapes that need a NON-DEFAULT POLICY to reach the code they guard.
# Every _SHAPES entry runs bare parse(), and a stage gated on an opt-in
# Policy field is dead there -- #329's clause loop exits on its first
# line when maiden_delimiters is empty, so the quadratic it shipped
# with was invisible to all ten shapes above even though "(a) " was
# already one of them. The unit is the SAME string as delimiter_pairs;
# only the policy differs, which is the whole point.
#
# Calibrated like the others, per the note above: the #329 clause scan
# measured 14.1x at base 800 (against a 4.1x bare-policy control), and
# 4.3x once bisected -- inside the clean column, so _MAX_RATIO did not
# move. Every ratio in this file is for _FACTOR x the input, never per
# doubling; re-measuring the scan on another runner gave 11.2x against
# the same 4.2x control, which is the spread to expect here.
#
# Third element: a REACHABILITY probe, run before the measurement.
# "the shape must reach the code" is the whole premise of this table,
# and it is a premise about precedence, which moves -- route ( ) back
# to nickname and the parse below stops producing a maiden clause,
# leaving this test measuring a no-op at a comfortable 4.2x forever.
# That is the module docstring's failure mode one level up: a guard
# whose subject has quietly left the building. The probe is per shape
# because what "reached" means is per shape.
_POLICY_SHAPES: dict[str, tuple[str, Parser, Callable[[Parser], bool]]] = {
    "maiden_pairs": (
        "(a) ",
        Parser(policy=Policy(maiden_delimiters=frozenset({("(", ")")}))),
        # a maiden clause whose marker the #329 pass consumes: the
        # parenthesis pair must route to maiden AND the clause loop
        # must run for this to read "b" rather than "" or "née b"
        lambda p: p.parse("a (née b)").maiden == "b",
    ),
}


def test_shape_tables_are_not_empty() -> None:
    # pytest turns an EMPTY parametrize into a SKIP, not a failure, so
    # deleting the last entry of either table would retire its guard
    # into the skip count with nothing going red. _POLICY_SHAPES is
    # the nearer risk, holding only shapes whose stage a default parse
    # cannot reach at all -- so it gains an entry only when an opt-in
    # Policy field turns out to have a scaling cliff behind it.
    assert _SHAPES
    assert _POLICY_SHAPES


@pytest.mark.parametrize("unit,parser,reaches", _POLICY_SHAPES.values(),
                         ids=list(_POLICY_SHAPES))
def test_policy_gated_cost_grows_no_worse_than_linearly(
        unit: str, parser: Parser,
        reaches: Callable[[Parser], bool]) -> None:
    assert reaches(parser), "shape no longer reaches the gated stage"
    _assert_grows_linearly(unit, parser.parse)
