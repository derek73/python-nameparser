"""Stage: segment.

Consumes: tokens (role-None main stream), comma_offsets.
Produces: segments (runs of main-token indices; interior segments may
be EMPTY -- doubled commas keep their structural position), structure,
COMMA_STRUCTURE ambiguities for unrecognized extra segments.
Reads: Lexicon suffix vocabulary and Policy, both through
_vocab.is_wholly_suffix -- the suffix-comma decision is definitionally
vocabulary-dependent (decisions.md#C1), and the predicate
owns the rest (Policy.lenient_comma_suffixes picks the lenient or
strict token test; Policy.extra_suffix_delimiters gives v1
suffix_delimiter parity, a delimiter-core token being transparent).

Implements rules C1 and C2 of docs/design/rules.md, cited at the
decision site below; history in decisions.md#C1.
"""
from __future__ import annotations

import bisect
import dataclasses

from nameparser._pipeline._state import ParseState, PendingAmbiguity, Structure
from nameparser._pipeline._vocab import is_wholly_suffix
from nameparser._types import AmbiguityKind





def segment(state: ParseState) -> ParseState:
    main = [i for i, t in enumerate(state.tokens) if t.role is None]
    if not main:
        return dataclasses.replace(state, segments=(),
                                   structure=Structure.NO_COMMA)
    if not state.comma_offsets:
        return dataclasses.replace(state, segments=(tuple(main),),
                                   structure=Structure.NO_COMMA)
    buckets: list[list[int]] = [[] for _ in range(len(state.comma_offsets) + 1)]
    for i in main:
        # comma_offsets is sorted and no offset ever equals a token
        # start, so bisect_left counts the commas before this token
        start = state.tokens[i].span.start
        bucket = bisect.bisect_left(state.comma_offsets, start)
        buckets[bucket].append(i)
    groups = [tuple(b) for b in buckets]
    # v1 strips exactly ONE trailing comma as cosmetic (parser.py's
    # collapse_whitespace); every other empty bucket is STRUCTURAL and
    # keeps its position -- in 'Doe,, Jr.' the given segment is empty,
    # so 'Jr.' stays a tail suffix instead of masquerading as a lone
    # post-comma title (v1 parity, pinned live 2026-07-16)
    if len(groups) > 1 and not groups[-1]:
        groups.pop()
    if len(groups) <= 1:
        segs = tuple(groups) if groups and groups[0] else (tuple(main),)
        return dataclasses.replace(state, segments=segs,
                                   structure=Structure.NO_COMMA)

    def suffixy(seg: tuple[int, ...]) -> bool:
        return is_wholly_suffix([state.tokens[i].text for i in seg],
                                state.lexicon, state.policy)

    # rules.md#C1: "the name reads as trailing suffixes when the part
    # after the first comma is entirely suffix words and more than one
    # word precedes the comma; otherwise it reads as the listing form"
    # (v1 parity: only parts[1] decides, parser.py:1318; history:
    # decisions.md#C1)
    # rules.md#C2: "a non-empty extra part that is not entirely suffix
    # words is flagged as a structural ambiguity rather than rejected"
    # -- parts[2:] are consumed as suffixes unconditionally either
    # way, so a non-suffix tail segment gets the COMMA_STRUCTURE
    # flag, not a structure veto
    structure = (Structure.SUFFIX_COMMA
                 if suffixy(groups[1]) and len(groups[0]) > 1
                 else Structure.FAMILY_COMMA)
    ambiguities = list(state.ambiguities)
    for seg in groups[2:]:
        # empty segments are consumed silently (v1 skips them without
        # comment); only non-empty non-suffix tails get flagged
        if seg and not suffixy(seg):
            texts = " ".join(state.tokens[i].text for i in seg)
            ambiguities.append(PendingAmbiguity(
                AmbiguityKind.COMMA_STRUCTURE,
                f"segment {texts!r} beyond the recognized comma "
                f"structures; consumed as suffix best-effort",
                tuple(seg)))
    return dataclasses.replace(state, segments=tuple(groups),
                               structure=structure,
                               ambiguities=tuple(ambiguities))
