"""Stage: group.

Consumes: tokens (classified), segments, structure.
Produces: pieces + piece_tags per segment (runs of token indices --
tokens are NEVER joined into strings: the anti-#100 invariant); maiden
tail tokens get role=MAIDEN; marker tokens land in dropped.
Reads: token tags (from classify), and Policy.extra_suffix_delimiters
for the tail-segment handling below -- no other Policy field. The v1
"derived titles/prefixes" registration becomes piece_tags entries --
per-parse state that dissolves with the state (v1 kept per-parse sets
for the same reason). Reads Policy.extra_suffix_delimiters: tail
segments drop delimiter-core tokens (v1 suffix_delimiter parity).

Ports v1's join_on_conjunctions + prefix chains + _join_bound_first_name
plus two additions: the "Ph. D."-split merge (v1 fix_phd, recorded plan
deviation #1) and the maiden-marker consuming rule (#274: marker plus
following pieces until a suffix become maiden; the marker itself is
structural, like a delimiter char, and is dropped from assembly).
"""
from __future__ import annotations

import dataclasses
from collections.abc import Sequence, Set
from enum import IntEnum

from nameparser._pipeline._state import ParseState, Structure, WorkToken
from nameparser._pipeline._vocab import D as _D
from nameparser._pipeline._vocab import PH as _PH
from nameparser._pipeline._vocab import delimiter_cores
from nameparser._types import Role

# the credential-pair regexes live in _vocab (shared with segment)

Piece = list[int]


class BoundJoin(IntEnum):
    """v1 _join_bound_first_name's reserve_last, as the three states it
    actually has. IntEnum: the value IS the non_suffix threshold, so
    the >= comparison below reads unchanged."""

    DISABLED = 0   # the FAMILY_COMMA family segment (v1 never joined it)
    LENIENT = 2    # FAMILY_COMMA's post-comma segment (reserve_last=False)
    STRICT = 3     # main segments (reserve_last=True: keep a family piece)


def _is_title_piece(piece: Sequence[int], ptags: Set[str],
                    tokens: Sequence[WorkToken]) -> bool:
    if "title" in ptags:
        return True
    return len(piece) == 1 and "vocab:title" in tokens[piece[0]].tags


def _is_prefix_piece(piece: Sequence[int], ptags: Set[str],
                     tokens: Sequence[WorkToken]) -> bool:
    if "prefix" in ptags:
        return True
    return len(piece) == 1 and "particle" in tokens[piece[0]].tags


def _is_suffix_piece(piece: Sequence[int], ptags: Set[str],
                     tokens: Sequence[WorkToken]) -> bool:
    if "suffix" in ptags:
        return True
    if len(piece) != 1:
        return False
    tags = tokens[piece[0]].tags
    return "vocab:suffix" in tags and "initial" not in tags


def _is_conj_piece(piece: Sequence[int], ptags: Set[str],
                   tokens: Sequence[WorkToken]) -> bool:
    if "conjunction" in ptags:
        return True
    return len(piece) == 1 and "conjunction" in tokens[piece[0]].tags


def _is_rootname(piece: Sequence[int], ptags: Set[str],
                 tokens: Sequence[WorkToken]) -> bool:
    if len(piece) == 1 and "initial" in tokens[piece[0]].tags:
        return False
    return not (_is_title_piece(piece, ptags, tokens)
                or _is_prefix_piece(piece, ptags, tokens)
                or _is_suffix_piece(piece, ptags, tokens))


def _group_segment(seg: tuple[int, ...], additional: int,
                   tokens: Sequence[WorkToken],
                   bound_join: BoundJoin = BoundJoin.STRICT,
                   ) -> tuple[list[Piece], list[set[str]]]:
    pieces: list[Piece] = [[i] for i in seg]
    ptags: list[set[str]] = [set() for _ in seg]

    def title(k: int) -> bool:
        return _is_title_piece(pieces[k], ptags[k], tokens)

    def prefix(k: int) -> bool:
        return _is_prefix_piece(pieces[k], ptags[k], tokens)

    def suffix(k: int) -> bool:
        return _is_suffix_piece(pieces[k], ptags[k], tokens)

    def conj(k: int) -> bool:
        return _is_conj_piece(pieces[k], ptags[k], tokens)

    def merge(lo: int, hi: int, add: Set[str] = frozenset(),
              drop: Set[str] = frozenset()) -> None:
        # pieces/ptags are parallel arrays; every merge must update
        # both in lockstep
        pieces[lo:hi] = [[i for piece in pieces[lo:hi] for i in piece]]
        ptags[lo:hi] = [(set().union(*ptags[lo:hi]) | add) - drop]

    # ph-d merge first: "Ph." "D." adjacent -> one suffix piece (plan
    # deviation #1; v1 fix_phd did this by regex on the raw string)
    k = 0
    while k < len(pieces) - 1:
        a, b = pieces[k], pieces[k + 1]
        if (len(a) == 1 and len(b) == 1
                and _PH.fullmatch(tokens[a[0]].text)
                and _D.fullmatch(tokens[b[0]].text)):
            merge(k, k + 2, add={"suffix"})
        else:
            k += 1

    if len(pieces) + additional >= 3:
        total = sum(_is_rootname(p, t, tokens)
                    for p, t in zip(pieces, ptags)) + additional
        # contiguous conjunction runs merge first (v1: "of the")
        k = 0
        while k < len(pieces) - 1:
            if conj(k) and conj(k + 1):
                merge(k, k + 2, add={"conjunction"})
            else:
                k += 1
        # each conjunction joins its neighbors (v1's Google Code issue 11
        # carve-out, the "john e smith" bug:
        # a single-letter alphabetic conjunction in a short name is more
        # likely an initial)
        k = 0
        while k < len(pieces):
            if not conj(k):
                k += 1
                continue
            text = " ".join(tokens[i].text for i in pieces[k])
            if len(text) == 1 and total < 4 and text.isalpha():
                k += 1
                continue
            start = max(0, k - 1)
            end = min(len(pieces), k + 2)
            neighbor = start if start < k else end - 1
            derived = set()
            if title(neighbor):
                derived.add("title")
            if prefix(neighbor):
                derived.add("prefix")
            merge(start, end, add=derived)
            k = start + 1
        # prefix chains: a non-leading prefix run absorbs everything to
        # the next prefix or suffix (v1's leading_first_name rule keeps
        # the first piece a name: "Van Johnson")
        k = 0
        while k < len(pieces):
            if k == 0 or not prefix(k):
                k += 1
                continue
            j = k + 1
            while j < len(pieces) and prefix(j):
                j += 1
            while j < len(pieces) and not prefix(j) and not suffix(j):
                j += 1
            merge(k, j, drop={"prefix"})
            k += 1
        # bound given names: the first non-title piece joins the next
        # ONCE (pairwise, v1 parity: 'Salem, Abdul Rahman Ahmed' keeps
        # Ahmed a middle name). BoundJoin encodes v1's reserve_last.
        first_name_k = next(
            (k for k in range(len(pieces)) if not title(k)), None)
        if (bound_join is not BoundJoin.DISABLED
                and first_name_k is not None
                and first_name_k + 1 < len(pieces)
                and len(pieces[first_name_k]) == 1
                and "vocab:bound-given"
                in tokens[pieces[first_name_k][0]].tags):
            non_suffix = sum(1 for k in range(len(pieces))
                             if not title(k) and not suffix(k))
            if non_suffix >= bound_join:
                merge(first_name_k, first_name_k + 2)
    return pieces, ptags


def group(state: ParseState) -> ParseState:
    tokens = list(state.tokens)
    dropped = list(state.dropped)
    all_pieces: list[tuple[tuple[int, ...], ...]] = []
    all_ptags: list[tuple[frozenset[str], ...]] = []
    # v1 parity: additional_parts_count=1 applies only to FAMILY_COMMA
    # parts (parser.py:1313, 1369); the SUFFIX_COMMA pre-comma segment
    # gets 0 (parser.py:1333).
    additional = 1 if state.structure is Structure.FAMILY_COMMA else 0
    # v1 expand_suffix_delimiter parity (#191): tail segments (wholly
    # consumed as suffixes by assign) drop delimiter-core tokens, the
    # same structural mechanism as the maiden marker below
    cores = delimiter_cores(state.policy.extra_suffix_delimiters)
    tail_start = {Structure.SUFFIX_COMMA: 1,
                  Structure.FAMILY_COMMA: 2}.get(state.structure)
    family_comma = state.structure is Structure.FAMILY_COMMA
    for seg_idx, seg in enumerate(state.segments):
        if family_comma:
            bound_join = (BoundJoin.LENIENT if seg_idx == 1
                          else BoundJoin.DISABLED)
        else:
            bound_join = BoundJoin.STRICT
        pieces, ptags = _group_segment(seg, additional, tokens,
                                       bound_join)
        if tail_start is not None and seg_idx >= tail_start:
            # v1 renders each tail COMMA SEGMENT as one suffix entry
            # ('Smith, V MD' -> suffix 'V MD'); a delimiter core inside
            # a segment separates entries and is dropped, but a segment
            # that IS only the core stays whole (v1 expand() splits
            # within a part, never erases a lone part). Continuation
            # tokens within an entry take the stable "joined" tag so
            # the suffix view space-joins them (the fix_phd mechanism).
            entry_open = False
            kept: list[int] = []
            for k in range(len(pieces)):
                is_core = (len(pieces[k]) == 1
                           and tokens[pieces[k][0]].text in cores
                           and len(pieces) > 1)
                if is_core:
                    dropped.extend(pieces[k])
                    entry_open = False
                    continue
                kept.append(k)
                for pos, i in enumerate(pieces[k]):
                    if entry_open or pos > 0:
                        tokens[i] = dataclasses.replace(
                            tokens[i], tags=tokens[i].tags | {"joined"})
                # piece-level state: the NEXT piece continues this entry
                entry_open = True
            if len(kept) != len(pieces):
                pieces = [pieces[k] for k in kept]
                ptags = [ptags[k] for k in kept]
        # continuation tokens of a suffix-merged piece (the ph-d merge)
        # carry the stable "joined" tag: the suffix string view joins
        # SUFFIX tokens with ", ", and the tag lets it heal the split
        for piece, piece_tags_ in zip(pieces, ptags):
            if "suffix" in piece_tags_ and len(piece) > 1:
                for i in piece[1:]:
                    tokens[i] = dataclasses.replace(
                        tokens[i], tags=tokens[i].tags | {"joined"})
        # maiden markers: a non-leading marker piece consumes following
        # pieces until a suffix; consumed tokens become MAIDEN, the
        # marker is dropped (#274)
        m = next(
            (k for k in range(1, len(pieces))
             if len(pieces[k]) == 1
             and "vocab:maiden-marker" in tokens[pieces[k][0]].tags),
            None)
        if m is not None:
            j = m + 1
            consumed: list[int] = []
            while j < len(pieces) and not _is_suffix_piece(
                    pieces[j], ptags[j], tokens):
                consumed.extend(pieces[j])
                j += 1
            if consumed:
                dropped.extend(pieces[m])
                for i in consumed:
                    tokens[i] = dataclasses.replace(
                        tokens[i], role=Role.MAIDEN)
                pieces[m:j] = []
                ptags[m:j] = []
        all_pieces.append(tuple(tuple(p) for p in pieces))
        all_ptags.append(tuple(frozenset(t) for t in ptags))
    return dataclasses.replace(
        state, tokens=tuple(tokens), pieces=tuple(all_pieces),
        piece_tags=tuple(all_ptags), dropped=tuple(dropped))
