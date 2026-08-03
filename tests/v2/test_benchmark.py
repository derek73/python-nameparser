"""Perf smoke (core spec §7 tail): parse cost stays v1-comparable
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
import time
from collections.abc import Callable

import pytest

from nameparser import Parser, parse
from nameparser._policy import Policy


def test_parse_thousand_names_under_a_second() -> None:
    parse("warm up the default parser cache")
    start = time.perf_counter()
    for i in range(1000):
        parse(f"Dr. Juan{i} de la Vega III")
    elapsed = time.perf_counter() - start
    assert elapsed < 1.0, f"1000 parses took {elapsed:.2f}s"


def test_facade_thousand_names_under_a_second() -> None:
    # the legacy-API path (what all existing users call): snapshot
    # resolution must stay generation-cached, not rebuilt per instance
    from nameparser import HumanName

    HumanName("warm up the caches")
    start = time.perf_counter()
    for i in range(1000):
        HumanName(f"Dr. Juan{i} de la Vega III")
    elapsed = time.perf_counter() - start
    assert elapsed < 1.0, f"1000 facade parses took {elapsed:.2f}s"


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
# the ASCII shapes already occupy, so neither number moved.
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
# move.
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
    # into the skip count with nothing going red. _POLICY_SHAPES has
    # one entry and is the live risk.
    assert _SHAPES
    assert _POLICY_SHAPES


@pytest.mark.parametrize("unit,parser,reaches", _POLICY_SHAPES.values(),
                         ids=list(_POLICY_SHAPES))
def test_policy_gated_cost_grows_no_worse_than_linearly(
        unit: str, parser: Parser,
        reaches: Callable[[Parser], bool]) -> None:
    assert reaches(parser), "shape no longer reaches the gated stage"
    _assert_grows_linearly(unit, parser.parse)
