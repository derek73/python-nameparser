"""Stage: segment.

Consumes: tokens (role-None main stream), comma_offsets.
Produces: segments (runs of main-token indices), structure,
COMMA_STRUCTURE ambiguities for unrecognized extra segments.
Reads: Lexicon suffix vocabulary (via _vocab.is_suffix_lenient) --
the suffix-comma decision is definitionally vocabulary-dependent
(recorded plan deviation #3); Policy is not consulted here.

Decision (v1 parity): >=1 comma and every post-first segment entirely
lenient-suffix AND >1 word before the first comma -> SUFFIX_COMMA;
otherwise FAMILY_COMMA ("Family, Given ..."), with segments beyond the
second that are not lenient-suffix flagged COMMA_STRUCTURE (they are
still best-effort consumed as suffixes by assign, spec §5a).
"""
from __future__ import annotations

import bisect
import dataclasses

from nameparser._pipeline._state import ParseState, PendingAmbiguity, Structure
from nameparser._pipeline._vocab import is_suffix_lenient
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
    groups = [tuple(b) for b in buckets if b]
    if len(groups) <= 1:
        segs = tuple(groups) if groups else (tuple(main),)
        return dataclasses.replace(state, segments=segs,
                                   structure=Structure.NO_COMMA)

    def suffixy(seg: tuple[int, ...]) -> bool:
        return all(is_suffix_lenient(state.tokens[i].text, state.lexicon)
                   for i in seg)

    rest = groups[1:]
    if all(suffixy(s) for s in rest) and len(groups[0]) > 1:
        return dataclasses.replace(state, segments=tuple(groups),
                                   structure=Structure.SUFFIX_COMMA)
    ambiguities = list(state.ambiguities)
    for seg in groups[2:]:
        if not suffixy(seg):
            texts = " ".join(state.tokens[i].text for i in seg)
            ambiguities.append(PendingAmbiguity(
                AmbiguityKind.COMMA_STRUCTURE,
                f"segment {texts!r} beyond the recognized comma "
                f"structures; consumed as suffix best-effort",
                tuple(seg)))
    return dataclasses.replace(state, segments=tuple(groups),
                               structure=Structure.FAMILY_COMMA,
                               ambiguities=tuple(ambiguities))
