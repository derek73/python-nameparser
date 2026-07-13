"""Stage: group.

Consumes: tokens (classified), segments, structure.
Produces: pieces + piece_tags per segment (runs of token indices --
tokens are NEVER joined into strings: the anti-#100 invariant); maiden
tail tokens get role=MAIDEN; marker tokens land in dropped.
Reads: token tags (from classify); Policy is not consulted. The v1
"derived titles/prefixes" registration becomes piece_tags entries --
per-parse state that dissolves with the state (v1 kept per-parse sets
for the same reason).

Ports v1's join_on_conjunctions + prefix chains + _join_bound_first_name
plus two additions: the "Ph. D."-split merge (v1 fix_phd, recorded plan
deviation #1) and the maiden-marker consuming rule (#274: marker plus
following pieces until a suffix become maiden; the marker itself is
structural, like a delimiter char, and is dropped from assembly).
"""
from __future__ import annotations

import dataclasses
import re

from nameparser._pipeline._state import ParseState, Structure, WorkToken
from nameparser._types import Role

_PH = re.compile(r"^ph\.?$", re.IGNORECASE)
_D = re.compile(r"^d\.?$", re.IGNORECASE)

Piece = list[int]


def _is_title_piece(piece: Piece, ptags: set[str],
                    tokens: tuple[WorkToken, ...]) -> bool:
    if "title" in ptags:
        return True
    return len(piece) == 1 and "vocab:title" in tokens[piece[0]].tags


def _is_prefix_piece(piece: Piece, ptags: set[str],
                     tokens: tuple[WorkToken, ...]) -> bool:
    if "prefix" in ptags:
        return True
    return len(piece) == 1 and "particle" in tokens[piece[0]].tags


def _is_suffix_piece(piece: Piece, ptags: set[str],
                     tokens: tuple[WorkToken, ...]) -> bool:
    if "suffix" in ptags:
        return True
    if len(piece) != 1:
        return False
    tags = tokens[piece[0]].tags
    return "vocab:suffix" in tags and "initial" not in tags


def _is_conj_piece(piece: Piece, ptags: set[str],
                   tokens: tuple[WorkToken, ...]) -> bool:
    if "conjunction" in ptags:
        return True
    return len(piece) == 1 and "conjunction" in tokens[piece[0]].tags


def _is_rootname(piece: Piece, ptags: set[str],
                 tokens: tuple[WorkToken, ...]) -> bool:
    if len(piece) == 1 and "initial" in tokens[piece[0]].tags:
        return False
    return not (_is_title_piece(piece, ptags, tokens)
                or _is_prefix_piece(piece, ptags, tokens)
                or _is_suffix_piece(piece, ptags, tokens))


def _group_segment(seg: tuple[int, ...], additional: int,
                   tokens: tuple[WorkToken, ...],
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

    # ph-d merge first: "Ph." "D." adjacent -> one suffix piece (plan
    # deviation #1; v1 fix_phd did this by regex on the raw string)
    k = 0
    while k < len(pieces) - 1:
        a, b = pieces[k], pieces[k + 1]
        if (len(a) == 1 and len(b) == 1
                and _PH.fullmatch(tokens[a[0]].text)
                and _D.fullmatch(tokens[b[0]].text)):
            pieces[k:k + 2] = [a + b]
            merged = ptags[k] | ptags[k + 1] | {"suffix"}
            ptags[k:k + 2] = [merged]
        else:
            k += 1

    if len(pieces) + additional >= 3:
        total = sum(_is_rootname(p, t, tokens)
                    for p, t in zip(pieces, ptags)) + additional
        # contiguous conjunction runs merge first (v1: "of the")
        k = 0
        while k < len(pieces) - 1:
            if conj(k) and conj(k + 1):
                pieces[k:k + 2] = [pieces[k] + pieces[k + 1]]
                ptags[k:k + 2] = [ptags[k] | ptags[k + 1] | {"conjunction"}]
            else:
                k += 1
        # each conjunction joins its neighbors (v1 issue #11 carve-out:
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
            new_tags = set().union(*ptags[start:end])
            if title(neighbor):
                new_tags.add("title")
            if prefix(neighbor):
                new_tags.add("prefix")
            merged_piece = [i for p in pieces[start:end] for i in p]
            pieces[start:end] = [merged_piece]
            ptags[start:end] = [new_tags]
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
            merged_piece = [i for p in pieces[k:j] for i in p]
            merged_tags = set().union(*ptags[k:j]) - {"prefix"}
            pieces[k:j] = [merged_piece]
            ptags[k:j] = [merged_tags]
            k += 1
        # bound given names: first non-title piece joins the next when
        # enough rootname pieces remain (v1 reserve_last)
        first_name_k = next(
            (k for k in range(len(pieces)) if not title(k)), None)
        if (first_name_k is not None
                and first_name_k + 1 < len(pieces)
                and len(pieces[first_name_k]) == 1
                and "vocab:bound-given"
                in tokens[pieces[first_name_k][0]].tags):
            non_suffix = sum(1 for k in range(len(pieces))
                             if not title(k) and not suffix(k))
            if non_suffix >= 3:
                bg = first_name_k
                pieces[bg:bg + 2] = [pieces[bg] + pieces[bg + 1]]
                ptags[bg:bg + 2] = [ptags[bg] | ptags[bg + 1]]
    return pieces, ptags


def group(state: ParseState) -> ParseState:
    tokens = list(state.tokens)
    dropped = list(state.dropped)
    all_pieces: list[tuple[tuple[int, ...], ...]] = []
    all_ptags: list[tuple[frozenset[str], ...]] = []
    # v1 parity: additional_parts_count=1 applies only to FAMILY_COMMA
    # parts (parser.py:1333); the SUFFIX_COMMA pre-comma segment gets 0.
    additional = 1 if state.structure is Structure.FAMILY_COMMA else 0
    for seg in state.segments:
        pieces, ptags = _group_segment(seg, additional, tuple(tokens))
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
                    pieces[j], ptags[j], tuple(tokens)):
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
