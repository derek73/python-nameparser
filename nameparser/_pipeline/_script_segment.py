"""Stage: script_segment (#271).

Consumes: tokens, segments, structure.
Produces: tokens (the first activated-script token of the name
segment split in two), segments (index runs remapped past the
insertion), ambiguities (indices likewise remapped, plus a
SEGMENTATION report when more than one split was
vocabulary-supported).
Reads: Policy.segment_scripts, Lexicon.surnames.

Unspaced CJK names give tokenize no separator to find, so this stage
inserts the missing token boundary by vocabulary: the first token
written wholly in an activated script is matched longest-first against
Lexicon.surnames, and a hit splits it in two. Compound-before-single
("欧阳明" is 欧阳 + 明, though 欧 is itself a surname) falls out of
longest-first. The split makes two sub-slices of the one token,
rewriting nothing -- spans still index the original exactly, so the
anti-#100 invariant holds by construction.

Placed AFTER segment, on the comma doctrine that script-conditional
behavior is ignored where a comma already decides the family (the
rule script_orders follows): under FAMILY_COMMA the pre-comma text IS
the family by declaration, and splitting it would invent a boundary
the writer explicitly did not draw -- "남궁민수, 지훈" must render
family "남궁민수", not "남궁 민수". The post-comma side is given-name
text, no surname site either, so that structure opts out whole.
NO_COMMA and SUFFIX_COMMA still split, within segments[0] (the name
part) only. Running after segment costs the index remaps below;
running BEFORE it would have made the comma structure itself depend
on the split -- segment's suffix-comma rule needs more than one word
before the comma, so a pre-split "김민준, Jr." would have changed
structure on vocabulary alone. As written it stays FAMILY_COMMA,
which is why the SUFFIX_COMMA path needs a second word ("Dr 김민준,
Jr.") to be reachable at all.

Activation is per script because the AMBIGUITY is per script
(amendment 2026-07-27): HANGUL is on by default (hangul is
unambiguously Korean, and its surname set is closed and
default-shipped), while HAN is opt-in via locales.ZH -- a Chinese
surname list corrupts Japanese names ("高橋一郎" must not split as
高 + 橋一郎), which is #272's pluggable segmenter, not this table's.
Only the FIRST activated-script token is considered, match or no
match: family-first traditions put the surname at the front of the
name, and a match deeper in the token stream would be a given name or
an ordinary word, not a surname site.
"""
from __future__ import annotations

import dataclasses
import functools

from nameparser._pipeline._state import (
    ParseState, PendingAmbiguity, Structure,
)
from nameparser._pipeline._vocab import single_script
from nameparser._types import AmbiguityKind, Span


def _remap(run: tuple[int, ...], split_at: int) -> tuple[int, ...]:
    """One segment run after token `split_at` split in two: the second
    half joins the run immediately after it, and every later index
    shifts."""
    out: list[int] = []
    for j in run:
        if j == split_at:
            out.extend((split_at, split_at + 1))
        else:
            out.append(j + 1 if j > split_at else j)
    return tuple(out)


@functools.lru_cache(maxsize=8)
def _longest_entry(surnames: frozenset[str]) -> int:
    """The longest surname in a vocabulary, cached per-vocabulary
    rather than recomputed per parse (Lexicon is frozen and slotted,
    so it cannot carry a cached_property of its own). The frozenset is
    hashable and a process holds only a handful of distinct
    vocabularies -- the default one, plus one per constructed pack
    parser -- so maxsize=8 bounds pathological many-lexicon churn
    without ever evicting in normal use.

    Callers must pass a NON-EMPTY vocabulary: max() of an empty set
    raises, and the stage's own emptiness guard (`not surnames`) runs
    first, so the only call site cannot reach it."""
    return max(map(len, surnames))


def script_segment(state: ParseState) -> ParseState:
    scripts = state.policy.segment_scripts
    surnames = state.lexicon.surnames
    if not scripts or not surnames or not state.segments:
        return state
    if state.structure is Structure.FAMILY_COMMA:
        return state            # the comma already drew the boundary
    # segments[0] is the NAME part under both remaining structures
    # (everything, under NO_COMMA); later segments are suffixes. Its
    # members are main-stream token indices by construction, so
    # extracted nickname/maiden content is unreachable from here --
    # no input can produce it, so no test pins it.
    i = next((i for i in state.segments[0]
              if single_script(state.tokens[i].text) in scripts), None)
    if i is None:
        return state
    token = state.tokens[i]
    text = token.text
    # A token that IS a surname never splits: a bare "남궁" must not
    # become 남 + 궁 just because the single-syllable surname also
    # matches -- there is nothing to split off, and a lone token's
    # role is the order resolution's call.
    if text in surnames:
        return state
    # Longest-first (compound-before-single falls out of it), capped
    # so the remainder is never empty. Direct membership, no
    # _normalize: the script gate admits only CJK text, which the
    # storage fold stores unchanged.
    cap = min(_longest_entry(surnames), len(text) - 1)
    matches = [length for length in range(cap, 0, -1)
               if text[:length] in surnames]
    if not matches:
        return state    # the first activated-script token decides
    take = matches[0]
    cut = token.span.start + take
    head = dataclasses.replace(token, text=text[:take],
                               span=Span(token.span.start, cut))
    tail = dataclasses.replace(token, text=text[take:],
                               span=Span(cut, token.span.end))
    tokens = state.tokens[:i] + (head, tail) + state.tokens[i + 1:]
    # Every index the earlier stages recorded is now stale past the
    # split point: the segment runs group's own iteration rests on,
    # and the ambiguities from extract_delimited (resolved to indices
    # by tokenize) and segment. An ambiguity ON the split token keeps
    # pointing at the head.
    segments = tuple(_remap(run, i) for run in state.segments)
    ambiguities = tuple(
        dataclasses.replace(a, indices=tuple(
            j + 1 if j > i else j for j in a.indices))
        for a in state.ambiguities)
    if len(matches) > 1:
        # more than one vocabulary-supported split: longest-first
        # DECIDED a fork, and the deciding stage records it. A
        # single-match split chose nothing, so it stays silent.
        alt = matches[1]
        ambiguities += (PendingAmbiguity(
            AmbiguityKind.SEGMENTATION,
            f"{text!r} splits as {text[:take]!r} + {text[take:]!r} "
            f"on the longest surname; {text[:alt]!r} + "
            f"{text[alt:]!r} also reads",
            (i, i + 1)),)
    return dataclasses.replace(state, tokens=tokens, segments=segments,
                               ambiguities=ambiguities)
