"""Property layer (core spec §7.3). Hypothesis is a dev dependency only.

The alphabet is punctuation-heavy on purpose: plain st.text() spreads
over all of Unicode, so commas, quotes, and delimiters almost never
appear and the interesting planes go unexercised. derandomize=True
keeps runs reproducible on shared CI runners -- this layer guards
against regressions; exploratory fuzzing happened during review.
"""
from hypothesis import given, settings
from hypothesis import strategies as st

from nameparser import Lexicon, Policy, parse
from nameparser._pipeline import run
from nameparser._pipeline._state import ParseState

_ALPHABET = st.sampled_from(
    'abcdefgh ABC 12 .,،，\'"()«»‏‏\U0001f600éñßЖ-')


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


@given(st.text(alphabet=_ALPHABET, max_size=100))
@settings(max_examples=300, deadline=None, derandomize=True)
def test_every_original_char_is_accounted_for(text: str) -> None:
    # Reverse coverage (the dual of provenance): no character of the
    # input silently vanishes. Every char lies in a token span, a
    # masked delimited span, or is individually ignorable -- whitespace,
    # a structural comma, or a char the strip options remove. Checked on
    # the pre-assembly state because dropped/extracted tokens keep their
    # spans there.
    state = run(ParseState(original=text, lexicon=Lexicon.default(),
                           policy=Policy()))
    covered: set[int] = set()
    for tok in state.tokens:
        covered.update(range(tok.span.start, tok.span.end))
    for span in state.masked:
        covered.update(range(span.start, span.end))
    ignorable = {",", "،", "，", "\U0001f600", "‏"}
    for i, ch in enumerate(text):
        if i in covered or ch.isspace() or ch in ignorable:
            continue
        raise AssertionError(
            f"char {ch!r} at {i} in {text!r} is unaccounted for")
