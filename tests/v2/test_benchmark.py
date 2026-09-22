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
#   M2 clause VIEW            maiden_clause ONLY -- the one unit that
#                             reaches the #533 acronym fork, which
#                             needs a maiden marker AND a class member
#                             ending the string. 'MA nee ' has both
#                             words and reaches nothing: the peel
#                             stops at the trailing marker, so the
#                             ORDER inside the unit is the shape
#   connective RUN LENGTH     link_run ONLY -- P3's both-sides
#                             condition walks the run of connectives
#                             beside a link, and no other unit here
#                             puts two connectives in a row where one
#                             of them is GENERATIONAL vocabulary.
#                             'and ' is a run too, but no member of it
#                             is in the class, so the frozen loop's
#                             body never runs and the walk is never
#                             entered; the unit needs MIXED CASE as
#                             well, since a one-case name reads the
#                             marked letter as an initial and the
#                             frozen loop declines it on the tag
#                             ('i und ' reaches nothing, 'i Und '
#                             reaches everything)
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
    "maiden_clause": "nee MA ",     # group: M2's view over the segment
    "link_run": "i Und ",           # group: P3's both-sides walk (#397)
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
# The twelfth (maiden_clause, #533 review) arrived the same way, with
# its own quadratic in hand. M2's walk builds ONE view per take over
# the segment's own indices, and a rewrite that rebuilt those indices
# per piece -- behavior-identical, and it passed the whole suite --
# measures 8.3 at base 200, 10.4 at 400 and 12.2-12.6 at 800 against
# a clean 4.0-4.1 at every one of the three, repeated runs. So the
# signal is the strongest of the three quadratics on record and does
# not decide the bound; the shape reads 4.05-4.12 at base 800 across
# repeated runs, inside the clean column, and neither number moved.
# The thirteenth (link_run, #397 second review) arrived with its own
# quadratic in hand as well, and it is the one this shape was added
# FOR rather than one found by adding it: `_between_name_words` walked
# the run of connectives beside a link once per MEMBER of that run,
# so at commit b9ed1429 the shape measures 8.48 at base 100, 10.29 at
# 200 and 12.11 at 400 -- outside the bound at every one of them, and
# the second-strongest signal on record. Answered once per run
# (`_group._run_neighbours`) it reads 4.04 at base 200, 4.02 at 400
# and 4.02-4.19 at 800 across repeated runs, inside the clean column;
# neither number moved. The absolute cost is the shape's own price
# and is paid at the top of the clean range: 11.6ms at base 800
# against 48.7ms at 3200.
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


# The shapes above repeat a unit 800 times and measure the CLOCK. That
# pairing cannot guard a mutual recursion: #531's trailing-slot walk
# re-entered the predicate that owns it, so a run of k ambiguous
# credentials cost 2**k, and a run long enough to separate 2**k from
# k**2 on the clock does not finish -- 24 members measured 5.8s and
# 5.9s on two runs, 32 would be days. So this one counts FRAMES over a
# run of 8 against a run of 16, where the exponential is still cheap
# enough to profile (112ms at 16 UNDER the sys.setprofile hook this
# measures with, which is most of that figure: 23ms unprofiled) and
# already 168x.
#
# Frames are the right instrument here for the #475 reason and one
# more: the recursion IS frame entries, one per re-entry, so the count
# is the defect itself rather than a proxy for it. Measured on the
# unfixed tree before the fix landed: 2,347 frames at 8 and 394,671 at
# 16. On this tree (py3.11): 865 at 8, 1,497 at 16, 5,289 at 64.
#
# TWO ratios, ordered, because one pair cannot see both defects. At 2x
# the input a quadratic is NOT the textbook 4x -- the per-member linear
# work dominates at these sizes, and the per-member memo #531 first
# shipped, a genuine quadratic, measured 2.08x here against this tree's
# 1.73x. So the 8-vs-16 pair guards the EXPONENTIAL and nothing else,
# and a second pair at 4x the input separates quadratic from linear:
# 16-vs-64 measures 3.53x here, 3.33x at cc78c960 (the tree before the
# slot existed at all) and 7.42x with that memo. The ORDER is what
# keeps the larger pair usable: an exponential does not return from a
# run of 64, so the cheap pair is asserted first and the tree that
# would hang has already failed.
_RUN_SMALL = 8
_RUN_LARGE = 16
_RUN_HUGE = 64
#: 8 -> 16, the exponential's bound: 1.73x measured here against the
#: 168x of the recursion this was written for, so 6.0 leaves 3.5x of
#: headroom over the measurement and nothing short of a re-entrant walk
#: can reach it. It does NOT see a quadratic (2.08x, measured above),
#: which is what the second bound is for.
_RUN_MAX_RATIO = 6.0
#: 16 -> 64, the quadratic's bound: 3.53x measured here against the
#: memo version's 7.42x, so 5.0 sits ~1.4x over the measurement and
#: ~1.5x under the regression it is aimed at. Frame counts do not move
#: under load, so both margins are for a future shape change rather
#: than for runner noise.
_RUN_HUGE_MAX_RATIO = 5.0


def _frames_for(text: str) -> int:
    """Python frame entries for ONE parse of `text`.

    One parse, not a mean: this measures growth between two inputs, and
    the count is deterministic for a given (tree, interpreter) -- see
    `_calls_per_parse`, which takes a mean only because it reports an
    absolute figure against a 2% band.
    """
    parse("warm up the caches")
    calls = 0

    def counter(frame: object, event: str, arg: object) -> None:
        nonlocal calls
        if event == "call":
            calls += 1

    sys.setprofile(counter)
    try:
        parse(text)
    finally:
        sys.setprofile(None)
    return calls


def test_a_trailing_credential_run_does_not_cost_exponentially() -> None:
    if sys.getprofile() is not None:
        pytest.skip("a profile hook is already installed; this test owns it")
    small_text = "Doe, John " + "MA " * _RUN_SMALL
    large_text = "Doe, John " + "MA " * _RUN_LARGE
    huge_text = "Doe, John " + "MA " * _RUN_HUGE
    # REACHABILITY, for the reason _POLICY_SHAPES carries one: the walk
    # under measurement runs only where every member of the run reads
    # as a credential. Route these to MIDDLE instead and the guard
    # measures a walk that no longer happens, at a comfortable ratio,
    # forever. Asked of the longest run too: the run length is what
    # this varies, so "still a credential run" is a claim at each size.
    assert parse(small_text).suffix == " ".join(["MA"] * _RUN_SMALL)
    assert parse(huge_text).suffix == " ".join(["MA"] * _RUN_HUGE)
    small = _frames_for(small_text)
    large = _frames_for(large_text)
    ratio = large / small
    assert ratio < _RUN_MAX_RATIO, (
        f"a run of {_RUN_SMALL} credentials costs {small} frames and a run "
        f"of {_RUN_LARGE} costs {large} -- {ratio:.1f}x for 2x the input, "
        f"where this tree measures 1.7x and the exponential this guards "
        f"measured 168x. The trailing-slot walk in _assign.py has "
        f"re-entered the predicate that owns it (#531)")
    # Only now the long run: it is the pair that can see a QUADRATIC,
    # and it is also the one an exponential never returns from, which
    # the assertion above has already caught.
    huge = _frames_for(huge_text)
    huge_ratio = huge / large
    assert huge_ratio < _RUN_HUGE_MAX_RATIO, (
        f"a run of {_RUN_LARGE} credentials costs {large} frames and a run "
        f"of {_RUN_HUGE} costs {huge} -- {huge_ratio:.1f}x for 4x the "
        f"input, where this tree measures 3.5x and the per-member memo "
        f"#531 first shipped measured 7.4x. Something in _assign.py's "
        f"trailing slot is asking a walk per member again (#531)")


# The clause caller of the same walk, and a THIRD instrument for the
# same reason the one above needed a second: `_SHAPES` repeats a unit
# and nothing else, so it cannot express "a name word, a marker, then
# a long run" -- and a maiden clause needs exactly that prefix.
# Measured: `"nee i Und " * n` never reaches the clause link exception
# at all (the take declines, and b9ed1429 and this tree measure the
# identical 3.92/4.07/4.12 on it), which is the silent-no-op a
# reachability probe exists to catch. So this guard builds its own
# input and counts FRAMES, which the walk is made of and which do not
# move under load.
#
# One pair, not two: the defect here is a quadratic and there is no
# exponential to order it against, so the 16-vs-64 pair is the whole
# guard. Re-measured 2026-09-21 on py3.11 through this file's own
# `_frames_for`: 859 frames at 16 and 2,587 at 64 on this tree
# (3.01x), against 1,125 and 6,741 at b9ed1429 (5.99x), where
# `_between_name_words` walked the run once per member -- identical on
# three repeated runs at each end, frame counts being deterministic.
# One frame per link below the 875/2,651 this same helper read before
# `_between_name_words` answered both sides in one call. The pair
# first recorded here, 876/2,652, is one frame above that and does NOT
# reproduce: re-measured 2026-09-22 on py3.11, 6048eb5d -- the commit
# that wrote those two figures into this comment -- reads 875 and
# 2,651, which is the same pair 9fd84463 reads. So that recording came
# off another interpreter; it stays, with the py3.11 reading of its own
# tree now beside it.
_CLAUSE_RUN_SMALL = 16
_CLAUSE_RUN_LARGE = 64
#: 3.01x measured here against 5.99x at b9ed1429: 4.5 sits ~1.5x over
#: the measurement and ~1.3x under the regression. Frame counts are
#: deterministic for a given tree and interpreter, so both margins are
#: for a future shape change rather than for runner noise.
_CLAUSE_RUN_MAX_RATIO = 4.5


def _clause_run(members: int) -> str:
    """A maiden clause whose birth name is a RUN of links.

    Mixed case on purpose: written wholly in one case the letter reads
    as an initial (rules.md#P3's marked subset) and the clause's link
    exception is never asked, so the guard would measure nothing.
    """
    return "Jane Doe nee Puig " + "i " * members + "Soler"


def test_a_clause_link_run_does_not_cost_quadratically() -> None:
    if sys.getprofile() is not None:
        pytest.skip("a profile hook is already installed; this test owns it")
    small_text = _clause_run(_CLAUSE_RUN_SMALL)
    large_text = _clause_run(_CLAUSE_RUN_LARGE)
    # REACHABILITY, the probe every shape in this file carries: the
    # walk under measurement runs only while the clause KEEPS the run,
    # which is rules.md#M2's link exception. End the clause at the
    # first link instead and the guard measures a walk that no longer
    # happens, at a comfortable ratio, forever. Asked at both sizes,
    # the run length being what this varies.
    for text, members in ((small_text, _CLAUSE_RUN_SMALL),
                          (large_text, _CLAUSE_RUN_LARGE)):
        assert parse(text).maiden == " ".join(
            ["Puig"] + ["i"] * members + ["Soler"])
    small = _frames_for(small_text)
    large = _frames_for(large_text)
    ratio = large / small
    assert ratio < _CLAUSE_RUN_MAX_RATIO, (
        f"a clause holding {_CLAUSE_RUN_SMALL} links costs {small} frames "
        f"and one holding {_CLAUSE_RUN_LARGE} costs {large} -- "
        f"{ratio:.1f}x for 4x the input, where this tree measures 3.0x "
        f"and the per-member walk at b9ed1429 measured 6.0x. "
        f"_group.py's `_between_name_words` is walking the run per member "
        f"again (#397)")


# THE ABSOLUTE COST OF A LINK, which the ratio above cannot see: a
# change costing ONE MORE FRAME PER LINK moves both ends of the pair
# and leaves the ratio where it was. Re-splitting the #397 follow-up's
# fold is exactly that change -- 859/2,587 here against 875/2,651 at
# 9fd84463, +1 per link at each size -- and against THIS suite the
# pre-fold parser is green everywhere but here. Measured 2026-09-22 on
# py3.11: a copy of this tree carrying `git archive 9fd84463
# nameparser` in place of its own runs 9,652 passed, 324 skipped, 4
# xfailed and ONE failure, this test. So a link-bearing name gets a
# banded absolute pin, keyed by interpreter and banded like
# `_CALL_BASELINE` above.
#
# THE LONG RUN AND NOT THE SHORT ONE, and the arithmetic is the whole
# reason: +1 per link is 16 frames at `_CLAUSE_RUN_SMALL`, and 2% of
# 859 is 17.2, so the small end's band swallows the very regression
# this pin exists for (875 sits inside 842-876). At
# `_CLAUSE_RUN_LARGE` the same change is +64 against a 2% band of
# 51.7, and 2,651 sits outside 2,535-2,639. A tighter band on the
# short name would do it too and was not taken: the band is the one
# `_CALL_BASELINE` uses, and a bespoke one here would need its own
# argument every time the shape moved.
#
# ONE ROW, py3.11, and an unknown interpreter SKIPS rather than fails
# -- which is where this parts company with `_check_budget`, whose
# table carries every interpreter CI runs and so can afford to fail on
# a missing row. Only py3.11 is measurable in this working tree, and a
# figure nobody here ran is not a pin. The #537 reviewer reports 3.12
# at 835/2,563 and 3.13/3.14 at 882/2,706 for the 16/64 pair; those
# are NOT recorded below, because recording them would put a number
# under a band without a run behind it. Reproduce one on its own
# interpreter and add the row.
_LINK_BASELINE = {
    (3, 11): 2587,
}
#: The same +-2% `_CALL_BASELINE` uses, and for the same reason: frame
#: counts are deterministic for a given tree and interpreter, so the
#: band is headroom for a deliberate shape change rather than for
#: runner noise.
_LINK_BAND = 0.02


def test_a_link_costs_what_it_is_pinned_at() -> None:
    """The absolute frame cost of one link-bearing name.

    The ratio guard above cannot fail on a per-link constant, because
    a constant moves its two ends together. This one can, and it is
    the only thing in the suite that can.
    """
    if sys.getprofile() is not None:
        pytest.skip("a profile hook is already installed; this test owns it")
    version = sys.version_info[:2]
    if version not in _LINK_BASELINE:
        pytest.skip(
            f"no link baseline for Python {version[0]}.{version[1]}; "
            f"measure `_clause_run({_CLAUSE_RUN_LARGE})` on this "
            f"interpreter and add the row to _LINK_BASELINE")
    text = _clause_run(_CLAUSE_RUN_LARGE)
    # REACHABILITY, the probe every shape in this file carries: the
    # frames counted are the clause walk's, and they are only there
    # while the clause KEEPS the run (rules.md#M2's link exception).
    # End the clause at the first link and this measures a name that
    # no longer holds 64 links, comfortably inside the band forever.
    assert parse(text).maiden == " ".join(
        ["Puig"] + ["i"] * _CLAUSE_RUN_LARGE + ["Soler"])
    baseline = _LINK_BASELINE[version]
    actual = _frames_for(text)
    low, high = baseline * (1 - _LINK_BAND), baseline * (1 + _LINK_BAND)
    assert low <= actual <= high, (
        f"a maiden clause holding {_CLAUSE_RUN_LARGE} links costs "
        f"{actual} frames on Python {version[0]}.{version[1]}, band "
        f"{low:.0f}-{high:.0f} around a baseline of {baseline}. Growth "
        f"and shrinkage are both signals, and one frame per link is "
        f"enough to reach this band where the ratio guard above cannot "
        f"see it: check whether `_group._between_name_words` still "
        f"answers both sides of a link in one call, then move the "
        f"baseline deliberately (#397)")
