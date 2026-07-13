"""Property layer (core spec §7.3). Hypothesis is a dev dependency only.

The alphabet is punctuation-heavy on purpose: plain st.text() spreads
over all of Unicode, so commas, quotes, and delimiters almost never
appear and the interesting planes go unexercised. derandomize=True
keeps runs reproducible on shared CI runners -- this layer guards
against regressions; exploratory fuzzing happened during review.
"""
from hypothesis import given, settings
from hypothesis import strategies as st

from nameparser import parse

_ALPHABET = st.sampled_from(
    'abcdefgh ABC .,،，\'"()«»‏‏\U0001f600éñßЖ-')


@given(st.text(alphabet=_ALPHABET, max_size=200))
@settings(max_examples=300, deadline=None, derandomize=True)
def test_parse_never_raises_on_str(text: str) -> None:
    parse(text)


@given(st.text(alphabet=_ALPHABET, max_size=200))
@settings(max_examples=300, deadline=None, derandomize=True)
def test_provenance_for_parser_produced_names(text: str) -> None:
    pn = parse(text)
    for t in pn.tokens:
        assert t.span is not None
        assert t.text == pn.original[t.span.start:t.span.end]


@given(st.text(alphabet=_ALPHABET, max_size=100))
@settings(max_examples=200, deadline=None, derandomize=True)
def test_capitalized_idempotent(text: str) -> None:
    once = parse(text).capitalized()
    assert once.capitalized() == once


@given(st.text(alphabet=_ALPHABET, max_size=100))
@settings(max_examples=200, deadline=None, derandomize=True)
def test_render_reparse_reaches_fixpoint(text: str) -> None:
    # render/reparse legitimately takes several rounds to stabilize on
    # comma-heavy input (each round can re-segment); the invariant is
    # BOUNDED CONVERGENCE, not one-step idempotence
    s = str(parse(text))
    for _ in range(10):
        nxt = str(parse(s))
        if nxt == s:
            break
        s = nxt
    assert str(parse(s)) == s, f"no fixpoint within 10 rounds: {s!r}"
