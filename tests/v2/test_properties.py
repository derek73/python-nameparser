"""Property layer (core spec §7.3). Hypothesis is a dev dependency only.

The alphabet is punctuation-heavy on purpose: plain st.text() spreads
over all of Unicode, so commas, quotes, and delimiters almost never
appear and the interesting planes go unexercised. derandomize=True
keeps runs reproducible on shared CI runners -- this layer guards
against regressions; exploratory fuzzing happened during review.
"""
import json
from pathlib import Path

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from nameparser import Lexicon, Policy, parse
from nameparser._pipeline import run
from nameparser._pipeline._state import ParseState
from nameparser._types import AmbiguityKind, Role

_ALPHABET = st.sampled_from(
    'abcdefgh ABC 12 .,،，\'"()«»‏‏\U0001f600éñßЖ-')

# Same one-JSON-name-per-line convention test_locales.py reads; see the
# note there on why tools/ is not imported.
_FORK_CORPUS = [
    json.loads(line)
    for line in (Path(__file__).parents[2] / "tools" / "differential"
                 / "corpus.jsonl").read_text().splitlines()
    if line.strip()
]


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


_NAME_ROLES = (Role.GIVEN, Role.MIDDLE, Role.FAMILY)


def _fork_count(state: ParseState) -> int:
    return sum(a.kind is AmbiguityKind.PARTICLE_OR_GIVEN
               for a in state.ambiguities)


def test_a_leading_ambiguous_particle_is_reported_once_and_only_once(
) -> None:
    """PARTICLE_OR_GIVEN is the one kind two stages emit: _group takes
    the particle branch when a title shifts the particle off index 0 and
    the chain claims something ("Dr. Van Johnson"), _assign takes the
    given branch when it stays a lone leading piece ("Van Johnson").
    Each reports the side it decides -- see the ParseState docstring --
    but they coordinate only through _group's `j > k + 1` guard, which
    mirrors _assign's reachability by hand. Nothing checked the mirror.

    The shape that separates them is the one real-name corpora have
    least reason to contain: a suffix straight after the particle, where
    the chain is a no-op and only _assign should speak. Generate it, over
    every ambiguous particle, so a vocabulary addition is covered too.

    Deliberately asserts the COUNT and not which stage spoke. Whether a
    given fork was decided by a vocabulary merge or by position is not
    recoverable from the finished parse -- 'Dr. aan Johnson Jr.' and
    'أبو بكر أحمد' end with the same roles and the same tags, and only
    one is a fork -- so any reconstruction here would have to
    re-implement _group rather than check it.
    """
    lex = Lexicon.default()
    # bound-given prefixes are excluded, not overlooked: 'abu' is both
    # an ambiguous particle and a bound given prefix, so whether it
    # forks depends on whether the bound join fired -- a second rule,
    # covered by the case corpus rather than by this sweep
    particles = sorted(lex.particles_ambiguous - lex.bound_given_names)
    assert particles, "no ambiguous particles to exercise"
    failures = []
    for particle in particles:
        for lead in ("", "Dr. ", "Dr. Ann "):
            for body in ("", "Johnson ", "Johnson Smith "):
                for tail in ("", "Jr.", "MD", "III"):
                    text = f"{lead}{particle} {body}{tail}".strip()
                    state = run(ParseState(original=text,
                                           lexicon=lex, policy=Policy()))
                    names = [t for t in state.tokens
                             if t.role in _NAME_ROLES]
                    # Leading = no name part precedes it. With a given
                    # name in front ("Dr. Ann van Johnson") the particle
                    # sits mid-name, where nothing has to choose -- the
                    # decision-not-a-word rule, so no report. And a lone
                    # name part is the whole name, not a coin flip.
                    leads = bool(names) and "vocab:particle-ambiguous" \
                        in names[0].tags
                    want = 1 if leads and len(names) >= 2 else 0
                    got = _fork_count(state)
                    if got != want:
                        failures.append(
                            f"{text!r}: {got} report(s), expected {want} "
                            f"({len(names)} name tokens, "
                            f"leading={leads})")
    assert not failures, (
        f"{len(failures)} shape(s) disagree:\n" + "\n".join(failures[:15]))


@pytest.mark.parametrize("text", _FORK_CORPUS)
def test_a_fork_is_never_reported_twice_on_a_real_name(text: str) -> None:
    state = run(ParseState(original=text, lexicon=Lexicon.default(),
                           policy=Policy()))
    assert _fork_count(state) <= 1


@given(st.text(alphabet=_ALPHABET, max_size=120))
@settings(max_examples=400, deadline=None, derandomize=True)
def test_particle_fork_is_never_double_reported(text: str) -> None:
    # The half of the invariant that needs no reconstruction: whatever
    # the two emitters decide, they must not both fire on one parse.
    state = run(ParseState(original=text, lexicon=Lexicon.default(),
                           policy=Policy()))
    assert _fork_count(state) <= 1, (
        f"{text!r} reported the same fork more than once")
