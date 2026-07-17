"""Stage: segment.

Consumes: tokens (role-None main stream), comma_offsets.
Produces: segments (runs of main-token indices; interior segments may
be EMPTY -- doubled commas keep their structural position), structure,
COMMA_STRUCTURE ambiguities for unrecognized extra segments.
Reads: Lexicon suffix vocabulary (via _vocab.is_suffix_lenient) --
the suffix-comma decision is definitionally vocabulary-dependent
(recorded plan deviation #3); reads Policy.lenient_comma_suffixes
to pick the lenient or strict predicate, and
Policy.extra_suffix_delimiters for v1 suffix_delimiter parity (a
delimiter-core token is transparent in the all-suffix tests).

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
from nameparser._pipeline._vocab import (
    delimiter_cores, is_suffix_lenient, is_suffix_strict,
    splits_into_suffixes,
)
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

    # lenient_comma_suffixes=False drops the post-comma test back to
    # the strict predicate (initial-shaped suffix words stop qualifying)
    predicate = (is_suffix_lenient if state.policy.lenient_comma_suffixes
                 else is_suffix_strict)
    # v1 expand_suffix_delimiter parity (#191): a configured delimiter
    # is TRANSPARENT in the all-suffix tests -- v1 split the part string
    # on the delimiter before checking, so the delimiter never counted
    cores = delimiter_cores(state.policy.extra_suffix_delimiters)

    def counts_as_suffix(text: str) -> bool:
        if text in cores:
            return True
        return predicate(text, state.lexicon) or (
            bool(cores)
            and splits_into_suffixes(text, cores, state.lexicon))

    def suffixy(seg: tuple[int, ...]) -> bool:
        # an EMPTY segment is not suffix-shaped: v1's suffix-comma
        # detection fails on an empty parts[1] ('John Smith,, MD' is a
        # family-comma parse)
        return bool(seg) and all(
            counts_as_suffix(state.tokens[i].text) for i in seg)

    rest = groups[1:]
    if all(suffixy(s) for s in rest) and len(groups[0]) > 1:
        return dataclasses.replace(state, segments=tuple(groups),
                                   structure=Structure.SUFFIX_COMMA)
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
                               structure=Structure.FAMILY_COMMA,
                               ambiguities=tuple(ambiguities))
