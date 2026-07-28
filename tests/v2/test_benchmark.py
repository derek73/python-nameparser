"""Perf smoke (core spec §7 tail): parse cost stays v1-comparable
(microseconds per name). Deliberately generous bound -- guards against
order-of-magnitude regressions, does not gate normal variance.

Two different things are measured here, and the distinction matters.
The thousand-names tests below bound ABSOLUTE cost on constant-size
input; the scaling test bounds GROWTH in input length. Neither
subsumes the other, and the absolute tests are structurally blind to a
complexity regression: their workload is a short name with no
delimiters, so a stage that goes quadratic in the number of delimiter
pairs stays far inside the one-second bound. Two such quadratics
(_extract's mask-overlap scan, ParsedName's token-subset check) shipped
and were caught in review rather than here -- hence the scaling test.
"""
import time

import pytest

from nameparser import parse


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
#   token count               all nine
#   piece count               unmatched_*, plain_tokens, commas, titles
#   SEGMENT count             commas ONLY -- deleting it leaves every
#                             segment-keyed regression unguarded
#   intra-piece accumulation  particles (one 799-token piece),
#                             conjunctions (800) -- the merge() quadratic
#   masked-span count         delimiter_pairs, quote_pairs (0 pieces:
#                             everything is consumed as a delimited run)
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
_MAX_RATIO = 6.0


def _best(text: str, repeats: int = 7) -> float:
    """Minimum of several runs: on a shared runner the mean carries the
    noise of whatever else is running, while the minimum approaches the
    true cost."""
    parse(text)                     # warm the default parser cache
    best = float("inf")
    for _ in range(repeats):
        start = time.perf_counter()
        parse(text)
        best = min(best, time.perf_counter() - start)
    return best


@pytest.mark.parametrize("unit", _SHAPES.values(), ids=list(_SHAPES))
def test_parse_cost_grows_no_worse_than_linearly(unit: str) -> None:
    small = _best(unit * _BASE)
    large = _best(unit * (_BASE * _FACTOR))
    ratio = large / small
    assert ratio < _MAX_RATIO, (
        f"{unit!r} x{_BASE} took {small * 1e3:.2f}ms, "
        f"x{_BASE * _FACTOR} took {large * 1e3:.2f}ms -- {ratio:.1f}x for "
        f"{_FACTOR}x the input, which is superlinear (linear is ~{_FACTOR})")
