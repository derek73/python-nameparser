"""Property layer (core spec §7.3). Hypothesis is a dev dependency only.

The alphabet is punctuation-heavy on purpose: plain st.text() spreads
over all of Unicode, so commas, quotes, and delimiters almost never
appear and the interesting planes go unexercised. derandomize=True
keeps runs reproducible on shared CI runners -- this layer guards
against regressions; exploratory fuzzing happened during review.
"""
import dataclasses

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from nameparser import (
    DEFAULT_SCRIPT_ORDERS, FAMILY_FIRST, FAMILY_FIRST_GIVEN_LAST,
    GIVEN_FIRST, Lexicon, Parser, PatronymicRule, Policy, Script, parse,
)
from nameparser._lexicon import _VOCAB_FIELDS
from nameparser._pipeline import run
from nameparser._pipeline._state import ParseState
from nameparser._types import AmbiguityKind, Role

from .conftest import differential_corpus

_ALPHABET = st.sampled_from(
    'abcdefgh ABC 12 .,،，\'"()«»‏‏\U0001f600éñßЖ-')

_FORK_CORPUS = differential_corpus()


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


# ---------------------------------------------------------------- config
# Everything above fuzzes the INPUT STRING against the default
# configuration. That leaves 2.0's largest new surface -- Lexicon and
# Policy -- covered only by hand-written cases, which is backwards: the
# vocabulary and the switches are the parts a user is invited to
# change, so they are the parts most likely to be given a combination
# nobody tried.

# Deliberately mixed: real vocabulary, one-letter words that collide
# with initials, an interior period, and non-Latin entries. Nothing
# here normalizes to empty, which Lexicon rejects outright. No
# multi-word phrase: every field below except given_name_titles is
# matched one word at a time, so a multi-word draw in a per-word field
# would be a dead entry that trips Lexicon's multi-word warning.
# The CJK tail (#271) is what lets a drawn `surnames` set activate
# script_segment at all: hangul is the script segmented by default, so
# "김"/"남궁" are what make the stage fire (see _names_using, which
# supplies the unspaced token to fire it ON), and the Han rows ride
# along for script_orders -- Han segmentation is opt-in via
# locales.ZH, which these policies do not draw.
_VOCAB = st.sampled_from([
    "van", "de", "la", "bin", "abdul", "abu", "dr", "sir", "prof",
    "md", "jr", "iii", "esq", "ma", "do", "and", "y", "née", "geb",
    "a", "b", "ph.d", "عبد", "фон", "μεγα",
    "김", "남궁", "毛", "欧阳",
])

# given_name_titles is the one field matched as a space-joined run, so
# a multi-word phrase there is meaningful (not dead) and must not warn.
# Derived from _VOCAB rather than duplicated, so the two pools cannot
# drift apart.
_TITLE_VOCAB = st.one_of(_VOCAB, st.just("grand duke"))


def _fix_invariants(**fields: frozenset[str]) -> dict[str, frozenset[str]]:
    """Repair a random draw into a legal Lexicon instead of generating
    one legally.

    Drawing dependent subsets directly (particles_ambiguous from
    whatever particles happened to be drawn) makes the strategy tree
    deep and mostly rejects; intersecting after the fact keeps every
    draw usable and still reaches every shape. The five rules are
    Lexicon's own, restated here on purpose -- if one changes, this
    fails loudly rather than silently fuzzing a narrower space.
    """
    fields["particles_ambiguous"] &= fields["particles"]
    fields["suffix_acronyms_ambiguous"] &= fields["suffix_acronyms"]
    fields["suffix_words"] -= fields["suffix_acronyms_ambiguous"]
    # order matters: must run AFTER the suffix_words subtraction above,
    # or that later subtraction could re-orphan a tail this repair just
    # fixed
    fields["honorific_tails"] &= fields["suffix_words"]
    fields["bound_given_names"] -= (
        fields["particles"] - fields["particles_ambiguous"])
    return fields


# Derived, never listed: a new vocabulary field must be fuzzed the day
# it is added, and a hand-copied list would leave it silently unfuzzed
# -- the invisible gap this whole layer exists to prevent.
_SET_FIELDS = _VOCAB_FIELDS


@st.composite
def _lexicons(draw: st.DrawFn) -> Lexicon:
    fields = {name: draw(st.frozensets(
        _TITLE_VOCAB if name == "given_name_titles" else _VOCAB,
        max_size=5))
              for name in _SET_FIELDS}
    caps = draw(st.lists(st.tuples(_VOCAB, _VOCAB), max_size=3))
    return Lexicon(capitalization_exceptions=tuple(caps),
                   **_fix_invariants(**fields))


# script_orders' legal values are as restricted as name_order's (only
# the three exported orders, keyed by Script), so they are sampled
# rather than generated. The five cover the axes that matter: the
# shipped default, the full opt-out, one script alone, an order that
# disagrees with the default -- FAMILY_FIRST_GIVEN_LAST on hangul
# reads "김민준 수" differently from every other entry here, which is
# what makes a script table that is merely PRESENT distinguishable
# from one that is actually consulted -- and a table keyed on the kana
# license's carrier (#272). That last row is the only one whose key is
# reached INDIRECTLY: a mixed kanji+kana name resolves to HIRAGANA
# rather than to any script it is literally written in, and pointing
# the carrier back at GIVEN_FIRST makes a consulted table visibly
# different from the default it would otherwise agree with.
_SCRIPT_ORDER_TABLES = [
    DEFAULT_SCRIPT_ORDERS,
    (),
    ((Script.HAN, FAMILY_FIRST),),
    ((Script.HANGUL, FAMILY_FIRST_GIVEN_LAST),),
    ((Script.HIRAGANA, GIVEN_FIRST),),
]


@st.composite
def _policies(draw: st.DrawFn) -> Policy:
    pairs = st.sampled_from([("(", ")"), ('"', '"'), ("'", "'"),
                             ("[", "]"), ("«", "»")])
    nickname = draw(st.frozensets(pairs, max_size=2))
    # a pair may not sit in both buckets; Policy canonicalizes overlap
    # away, but constructing the contradiction is not what this fuzzes
    maiden = draw(st.frozensets(pairs, max_size=2)) - nickname
    return Policy(
        name_order=draw(st.sampled_from(
            [GIVEN_FIRST, FAMILY_FIRST, FAMILY_FIRST_GIVEN_LAST])),
        script_orders=draw(st.sampled_from(_SCRIPT_ORDER_TABLES)),
        # no max_size: Script has four members, so the unbounded draw
        # still reaches every subset -- including the empty one, which
        # is the documented segmentation opt-out, and the full one,
        # which turns on the Han and kana activation that only
        # locales.ZH and locales.JA turn on in shipped configuration
        segment_scripts=draw(st.frozensets(st.sampled_from(list(Script)))),
        patronymic_rules=draw(st.frozensets(
            st.sampled_from(list(PatronymicRule)), max_size=2)),
        middle_as_family=draw(st.booleans()),
        nickname_delimiters=nickname,
        maiden_delimiters=maiden,
        extra_suffix_delimiters=draw(
            st.frozensets(st.sampled_from(["/", ";", "|"]), max_size=2)),
        lenient_comma_suffixes=draw(st.booleans()),
        strip_emoji=draw(st.booleans()),
        strip_bidi=draw(st.booleans()),
    )


@st.composite
def _names_using(draw: st.DrawFn, lexicon: Lexicon) -> str:
    """Build the input out of the lexicon's OWN words.

    Fuzzing configuration while feeding unrelated text tests almost
    nothing: a randomly generated string essentially never contains a
    randomly generated vocabulary entry, so every configured set would
    sit unused and the parse would take the same path every time.
    """
    vocab = sorted({w for name in _SET_FIELDS
                    for w in getattr(lexicon, name)})
    # script_segment (#271, #308) holds the two halves a space-joined
    # name can never reach, and BOTH need their token derived from the
    # draw: waiting for a drawn entry and a matching literal to
    # coincide leaves the stage unexercised. The surname half splits an
    # unspaced token whose PREFIX is a drawn surname; the peel splits a
    # listed tail off the END of one. The peel's line was added after a
    # mutation pass asked the same question of it and instrumentation
    # answered: 14 fires across this file, every one under the DEFAULT
    # lexicon and none under a drawn one, because no generated token
    # ended in a drawn tail. Deriving it moves that off zero.
    # A Latin entry is useful input in its own right: it makes a
    # mixed-script token the surname half correctly declines, and for
    # the peel it is the one shape that reaches an ASCII tail at all --
    # the stage bails on a wholly-ASCII original, so the non-Latin stem
    # is what admits '민준jr'. Both fires observed under drawn lexicons
    # are of exactly that shape.
    # Neither derivation guarantees a fire on any given run: the piece
    # is one of ~30 in the pool, so it competes with the bare vocabulary
    # words, and a bare drawn surname standing earlier in the name takes
    # the surname site before the unspaced token can. Instrument before
    # concluding either half is exercised -- the counts above are what
    # that costs to find out, and the two halves are NOT in the same
    # state. Measured over this test's 250 examples: the peel fires
    # twice, the surname half ZERO times -- currently inert. Structural,
    # not luck: `w + "민준"` on a non-hangul surname is a MIXED-script
    # token, whose effective_script is None, so it can never be an
    # activated surname site at all; only a drawn HANGUL surname makes
    # one, and across the run exactly one such token was sampled
    # ('남궁민준'), into an example whose drawn policy had HANGUL out of
    # segment_scripts. Deriving the token was still the right move --
    # it took the half off structurally-unreachable -- but a fix worth
    # having would derive it in the script the policy activated.
    # sorted for the same reason `vocab` above is: frozenset iteration
    # order is not stable across runs, and an unsorted pool shifts
    # every index sampled_from draws -- which would defeat
    # derandomize=True on the whole strategy, not just this slice.
    unspaced = sorted(w + "민준" for w in lexicon.surnames)
    glued = sorted("민준" + w for w in lexicon.honorific_tails)
    # plain names and structure characters are always available, so the
    # pool is never empty even for an empty lexicon
    pieces = st.sampled_from(
        vocab + unspaced + glued + ["John", "Smith", "Q.", ",", "(", "'"])
    return " ".join(draw(st.lists(pieces, min_size=1, max_size=8)))


@given(_lexicons(), _policies(), st.data())
@settings(max_examples=250, deadline=None, derandomize=True)
def test_any_valid_config_still_parses_totally(
        lexicon: Lexicon, policy: Policy, data: st.DataObject) -> None:
    # Building the parser is part of the contract: a Lexicon and Policy
    # that each constructed must also combine.
    parser = Parser(lexicon=lexicon, policy=policy)
    text = data.draw(_names_using(lexicon))
    parsed = parser.parse(text)          # must not raise, ever
    # the anti-#100 invariant, under configuration rather than under
    # the default vocabulary: spans index the original exactly
    for token in parsed.tokens:
        assert token.span is not None
        assert token.text == parsed.original[
            token.span.start:token.span.end]
    # rendering is downstream of every config choice above
    assert isinstance(str(parsed), str)
    assert isinstance(parsed.capitalized().given, str)
    assert isinstance(parsed.initials(), str)


@given(_lexicons(), _policies())
@settings(max_examples=100, deadline=None, derandomize=True)
def test_config_values_are_hashable_and_reusable(
        lexicon: Lexicon, policy: Policy) -> None:
    # The docs promise these are frozen values: safe as dict keys, and
    # safe to build a parser from more than once.
    assert hash(lexicon) == hash(lexicon)
    assert {lexicon: 1, policy: 2}
    assert Parser(lexicon=lexicon, policy=policy) == Parser(
        lexicon=lexicon, policy=policy)


# Values a real caller plausibly passes by mistake: the bare string that
# iterates into characters, a mapping confused for a set, bytes, None,
# and entries that normalize to nothing.
_HOSTILE = st.sampled_from([
    None, 0, 1, True, "", "dr", "  ", ".", b"dr", ["dr", None],
    {"dr": "Dr"}, {1, 2}, [("a", "b")], [[]], object(),
])

# Same rule as _SET_FIELDS; test_policy.py already reflects this way.
_POLICY_FIELDS = tuple(f.name for f in dataclasses.fields(Policy))


@given(st.sampled_from(_SET_FIELDS + ("capitalization_exceptions",)),
       _HOSTILE)
@settings(max_examples=200, deadline=None, derandomize=True)
def test_bad_lexicon_field_fails_cleanly(field: str, value: object) -> None:
    """A rejected configuration must be a DOCUMENTED rejection.

    ValueError and TypeError are the contract; anything else means the
    bad value got past validation and blew up somewhere downstream,
    where the message no longer names the field the caller typed.
    """
    try:
        lexicon = Lexicon(**{field: value})     # type: ignore[arg-type]
    except (ValueError, TypeError):
        return
    # Accepted, so it has to survive an actual parse -- construction
    # succeeding while parsing dies is the same bug one stage later.
    Parser(lexicon=lexicon).parse("Dr. John de la Vega III")


@given(st.sampled_from(_POLICY_FIELDS), _HOSTILE)
@settings(max_examples=200, deadline=None, derandomize=True)
def test_bad_policy_field_fails_cleanly(field: str, value: object) -> None:
    try:
        policy = Policy(**{field: value})       # type: ignore[arg-type]
    except (ValueError, TypeError):
        return
    Parser(policy=policy).parse("Dr. John de la Vega III")
