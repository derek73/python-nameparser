"""The 2.0 parse pipeline: pure stages folded over ParseState.

Stage names and ParseState are NOT public API. The stage list is data;
runners other than the plain fold (explain(), parse_all()) arrive in
2.x minors without changing any stage signature.

Layering: imports only nameparser._pipeline.* (enforced by
tests/v2/test_layering.py).
"""
from __future__ import annotations

from collections.abc import Callable

from nameparser._pipeline._assign import assign
from nameparser._pipeline._classify import classify
from nameparser._pipeline._extract import extract_delimited
from nameparser._pipeline._group import group
from nameparser._pipeline._post_rules import post_rules
from nameparser._pipeline._script_segment import script_segment
from nameparser._pipeline._segment import segment
from nameparser._pipeline._state import ParseState, copy_with
from nameparser._pipeline._tokenize import tokenize

#: The full eight-stage fold.
STAGES: tuple[Callable[[ParseState], ParseState], ...] = (
    extract_delimited, tokenize, segment, script_segment, classify,
    group, assign, post_rules,
)


def run(state: ParseState) -> ParseState:
    """Fold the stages over the initial state. Pure: each stage returns
    a new ParseState; parse is total over str input, so no stage may
    raise on the *content* of a name (malformed policy/config is a
    separate, allowed failure mode)."""
    # rules/S13: "it reads as a bracketed unambiguous credential does in
    # the same place" -- Then; the clauses are known only once the roles
    # are read, so the stages fold again from the initial state with
    # the settled clauses set, until a fold settles none it was not
    # given (decisions/S13 (#810)). A settled word joins the name's own
    # words, which can make a one-case name mixed and settle a second
    # clause; the set only grows and is bounded by the clauses, so the
    # loop ends, and a name with none settled folds once.
    while True:
        folded = state
        for stage in STAGES:
            folded = stage(folded)
        if folded.settled_clauses <= state.settled_clauses:
            return folded
        state = copy_with(state, settled_clauses=folded.settled_clauses)
