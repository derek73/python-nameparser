"""Stage: group.

Consumes: tokens (classified), segments, structure, extracted (the
role + inner span per delimited region, for the #329 pass below --
the only stage after tokenize that reads it).
Produces: pieces + piece_tags per segment (runs of token indices --
tokens are NEVER joined into strings: the anti-#100 invariant); maiden
tail tokens get role=MAIDEN; marker tokens land in dropped.
Reads: token tags (from classify), and Policy.extra_suffix_delimiters
for the tail-segment handling below -- no other Policy field. The v1
"derived titles/prefixes" registration becomes piece_tags entries --
per-parse state that dissolves with the state (v1 kept per-parse sets
for the same reason). Reads Policy.extra_suffix_delimiters: tail
segments drop delimiter-core tokens (v1 suffix_delimiter parity).

Implements rules H3, P2, P3, P4 and M2 of docs/design/rules.md and the
group half of M1 (#329: the marker dropped inside EXTRACTED maiden
content, which M2's pieces walk cannot reach because extract's
content never enters pieces); each is cited at its code below. Also
implements rule P5 (cited below at the bound-given join) and ports
the "Ph. D."-split merge (v1 fix_phd; decisions.md#phd-merge).
"""
from __future__ import annotations

import bisect
import dataclasses
from collections.abc import Sequence, Set
from enum import IntEnum

from nameparser._pipeline._state import (
    ParseState, PendingAmbiguity, Structure, WorkToken,
)
from nameparser._pipeline._vocab import D as _D
from nameparser._pipeline._vocab import PH as _PH
from nameparser._pipeline._vocab import delimiter_cores
from nameparser._types import AmbiguityKind, Role

# the credential-pair regexes live in _vocab, whose own
# is_wholly_suffix merges the same pair -- and since #319 that
# predicate has TWO callers to stay in sync with, segment's
# suffix-comma structure test and script_segment's decline of a
# wholly-suffix post-comma run, both of which see the merged reading

Piece = list[int]


class BoundJoin(IntEnum):
    """v1 _join_bound_first_name's reserve_last, as the three states it
    actually has. IntEnum: the value IS the non_suffix threshold, so
    the >= comparison below reads unchanged."""

    DISABLED = 0   # the FAMILY_COMMA family segment (v1 never joined it)
    LENIENT = 2    # FAMILY_COMMA's post-comma segment (reserve_last=False)
    STRICT = 3     # main segments (reserve_last=True: keep a family piece)


# rules.md#H3: "successive title words at the start of the part
# carrying the given name chain into one title; a title word
# elsewhere in the name does not"
def _is_title_piece(piece: Sequence[int], ptags: Set[str],
                    tokens: Sequence[WorkToken]) -> bool:
    if "title" in ptags:
        return True
    return len(piece) == 1 and "vocab:title" in tokens[piece[0]].tags


# rules.md#P2: "a particle joins the words after it into one name
# part, the join running until the next particle starts a group of
# its own or the name ends. The final group reads as the family
# name; earlier groups read by position." (history: decisions.md#P2)
# rules.md#P4: "a particle in the name's leading position chains
# nothing: the words stay separate" (history: decisions.md#P2)
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


# rules.md#M2: "a recognized maiden marker standing after at least
# one name word takes the words after it — up to any trailing
# suffix — as the maiden name, and the marker itself is dropped"
# (history: decisions.md#M2)
#
# Shared deliberately with the prefix chain's stop (#399): a chain that
# stopped at something the consumer below would not then take would
# leave the marker stranded inside the family name, which is the very
# defect the stop exists to fix. One definition, so the two cannot
# disagree about what a marker piece is.
def _is_maiden_marker_piece(piece: Sequence[int],
                            tokens: Sequence[WorkToken]) -> bool:
    return (len(piece) == 1
            and "vocab:maiden-marker" in tokens[piece[0]].tags)


# rules.md#P3: "a recognized connective joins its neighbors into one
# name part, connective runs included — except a single-letter
# connective in a three-word name, which stays a name word, and a
# single-letter connective written as a bare Latin capital, which
# reads as an initial and never joins" (history: decisions.md#P3)
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
                   ambiguities: list[PendingAmbiguity] | None = None,
                   ) -> tuple[list[Piece], list[set[str]]]:
    pieces: list[Piece] = [[i] for i in seg]
    ptags: list[set[str]] = [set() for _ in seg]
    # Out-parameter, same shape as _assign_main: forks are reported
    # where they are decided. A caller that passes None (or a throwaway
    # list) suppresses reporting -- see group() for when that applies.
    if ambiguities is None:
        ambiguities = []

    def title(k: int) -> bool:
        return _is_title_piece(pieces[k], ptags[k], tokens)

    def prefix(k: int) -> bool:
        return _is_prefix_piece(pieces[k], ptags[k], tokens)

    def suffix(k: int) -> bool:
        return _is_suffix_piece(pieces[k], ptags[k], tokens)

    def conj(k: int) -> bool:
        return _is_conj_piece(pieces[k], ptags[k], tokens)

    def maiden_marker(k: int) -> bool:
        return _is_maiden_marker_piece(pieces[k], tokens)

    def merge(lo: int, hi: int, add: Set[str] = frozenset(),
              drop: Set[str] = frozenset()) -> None:
        # pieces/ptags are parallel arrays; every merge must update
        # both in lockstep.
        #
        # Extend the first piece IN PLACE rather than rebuilding the
        # merged list. The obvious spelling --
        #     pieces[lo:hi] = [[i for p in pieces[lo:hi] for i in p]]
        # -- re-flattens everything accumulated so far on every call, so
        # a chain that merges into the same piece n times copies
        # 1+2+...+n and the stage goes quadratic in the length of the
        # chain. A conjunction run ("and " * n) does exactly that: it
        # measured 2.4x-2.9x per doubling against the 2.0x every other
        # shape holds. No piece list is aliased outside this function
        # (each starts as a fresh [i], and the callers only read
        # pieces[k] before a merge), so mutating is safe; verified
        # identical token/role/tag/span/ambiguity output over 54,877
        # names. tests/v2/test_benchmark.py's "and " shape is the guard.
        #
        # Every call site passes lo < hi, and this REQUIRES it: with
        # lo >= hi the slice assignment would insert rather than
        # replace, putting a second reference to pieces[lo] into the
        # array, and the next merge to touch either index would extend
        # the same list twice. The old rebuild-a-fresh-list spelling
        # was harmless there. Keep the bound if you add a caller.
        combined = pieces[lo]
        for piece in pieces[lo + 1:hi]:
            combined.extend(piece)
        pieces[lo:hi] = [combined]
        ptags[lo:hi] = [(set().union(*ptags[lo:hi]) | add) - drop]

    # ph-d merge first: "Ph." "D." adjacent -> one suffix piece
    # (decisions.md#phd-merge; v1 fix_phd did this by regex on the
    # raw string)
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
        # each conjunction joins its neighbors, rules.md#P3: "except a
        # single-letter connective in a three-word name, which stays a
        # name word" (v1's Google Code issue 11 carve-out, the
        # "john e smith" bug). The threshold reads the ROOTNAME count,
        # so a conjunction that is also suffix vocabulary raises the
        # bar for itself -- #397 measures that on "i".
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
        #
        # "Leading" means the first piece of the NAME, not of the input
        # (#367): a title is not part of the name, so it must not decide
        # whether the name begins with a particle. Keyed on index 0, a
        # title displaced the particle and the chain fired, so identical
        # name text parsed two ways ("Van Johnson" -> given Van, family
        # Johnson; "Dr. Van Johnson" -> family "Van Johnson").
        #
        # "Title AND NOT prefix" rather than the plain "not a title" the
        # rule is stated as, and the difference is not academic: `st`,
        # `do` and `freiherr` are each BOTH a title and an ambiguous
        # particle, so the plain test skipped over the very piece the
        # exception exists to protect and "St John Smith" -- no title in
        # front of it at all -- collapsed from title St, given John,
        # family Smith into one given "St John Smith". A piece that
        # could be the name's own first piece stops the scan; only a
        # piece that can ONLY be a title is stepped over.
        #
        # Computed once, before the loop: every merge below starts at
        # some k at or past this index, so no merge can move it.
        #
        # Suffix pieces are deliberately NOT skipped, and the reason is
        # what skipping them WOULD do rather than what it would cost.
        # A credential written with spaces already parses without a
        # family name -- "Ph. D. Van Johnson" is given 'Van Johnson',
        # suffix 'Ph. D.', family '' -- and skipping the suffix piece
        # would actually give it one (given 'Van', family 'Johnson').
        # The shapes that decide it are the ones whose leading piece
        # lands in `given` instead: "Ph.D. Van Johnson", "II Van
        # Johnson" and "Msc.Ed. Van Johnson" each read given
        # 'Ph.D.'/'II'/'Msc.Ed.' with family 'Van Johnson', and
        # skipping the piece moves `Van` out of the family and into the
        # middle name (given 'Ph.D.', middle 'Van', family 'Johnson')
        # -- a worse reading, on three shapes, to fix none. "Jr. Van
        # Johnson", the shape that looks like it needs the skip,
        # classifies its leading piece as a TITLE and is already
        # covered here.
        #
        # A maiden marker stops the scan for a different reason than a
        # suffix does (#399): it is not a name word at all but the
        # boundary between two names, and the piece that consumes it
        # runs later in this same stage. Absorbing it took the maiden
        # name into the family with it -- "Ursula von der Leyen geb.
        # Albrecht" read family 'von der Leyen geb. Albrecht' where
        # "Ursula Leyen geb. Albrecht" reported maiden 'Albrecht'. Only
        # a NON-leading particle ever reached the marker, so a leading
        # single particle always worked (P4 chains nothing) while a
        # leading run of two did not, the second particle's own chain
        # firing.
        #
        # The `, 0` fallback is inert by construction rather than a
        # default worth testing: it is reached only when every piece is
        # a title and none is a prefix, and the loop below merges
        # nothing unless some piece is a prefix.
        leading = next((k for k in range(len(pieces))
                        if not title(k) or prefix(k)), 0)
        k = 0
        while k < len(pieces):
            if k == leading or not prefix(k):
                k += 1
                continue
            j = k + 1
            while j < len(pieces) and prefix(j):
                j += 1
            while (j < len(pieces) and not prefix(j) and not suffix(j)
                   and not maiden_marker(j)):
                j += 1
            # The other half of PARTICLE_OR_GIVEN. _assign reports the
            # fork when an ambiguous particle stays a lone leading piece
            # ("Van Johnson" -> given under the default order, family
            # under FAMILY_FIRST); the chain here takes the opposite
            # branch when the particle is not the name's leading piece.
            # A fork whose two sides are decided in different stages
            # needs an emitter in each.
            #
            # Narrow, and #367 is why. `all(title(x) for x in range(k))`
            # says every piece ahead of this one is a title, and the
            # loop skipped k == leading, so `leading` is STRICTLY
            # before k -- and being before k it is one of those titles,
            # while being `leading` it satisfies `not title or prefix`.
            # For both, it must be a prefix as well: a word in both
            # vocabularies (`st`, `do`, `freiherr` by default, or any
            # overlap a caller configures). A plain title alone can no
            # longer put a particle off the name's leading piece; it is
            # stepped over and _assign reports the fork instead.
            #
            # What that leaves is wider than one shape: any number of
            # plain title pieces, then a piece in BOTH vocabularies,
            # then any number of further titles, then the ambiguous
            # particle whose chain claims something. "Freiherr von
            # Richthofen" is the canonical spelling and the one
            # tests/v2/cases.py and tests/v2/test_parser.py lead with,
            # but "St Van Johnson", "Do St Johnson" (the chained
            # particle itself in both vocabularies) and "Dr. Do van
            # Johnson" (a plain title AHEAD of the both-vocabulary
            # word) all reach here too. What none of them can do is
            # dispense with the both-vocabulary WORD. The conjunction
            # merge is the only other way a piece acquires `title` or
            # `prefix`, and it cannot manufacture the pair: it derives
            # from ONE neighbor, which is the left one whenever there
            # is a left one, and its right operands are always fresh
            # pieces (the loop runs left to right, so nothing to the
            # right has been merged yet). Both tags therefore have to
            # come from the piece it extends, which bottoms out at a
            # lone token in both vocabularies.
            #
            # j > k + 1 is what makes this a DECISION rather than a
            # shape: when the next piece is a suffix the inner scan
            # never advances, merge(k, k+1) folds a piece into itself,
            # and the particle stays a lone leading piece -- nothing
            # was chained, and _assign reports that case instead.
            # Without this the two emitters both fire on the same token.
            # (Tag test first: it is a set lookup and almost no name has
            # an ambiguous particle, while title() is a call per piece.)
            if (j > k + 1
                    and "vocab:particle-ambiguous"
                    in tokens[pieces[k][0]].tags
                    and all(title(x) for x in range(k))):
                i = pieces[k][0]
                ambiguities.append(PendingAmbiguity(
                    AmbiguityKind.PARTICLE_OR_GIVEN,
                    f"{tokens[i].text!r} was chained onto the following "
                    f"name piece; it is also a given name in other "
                    f"names",
                    (i,)))
            merge(k, j, drop={"prefix"})
            k += 1
        # rules.md#P5: "a recognized bound given-name word joins the
        # word after it into one given name" (history: decisions.md#P5)
        # -- bound given names: the first non-title piece joins the next
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
            # first_name_k counts as a name piece even when it is
            # ALSO suffix vocabulary. The reserve asks whether enough
            # OTHER words are left to spare, and this piece is the one
            # the rule has already claimed as a name -- excluding it
            # made a dual-membership word silently un-joinable --
            # found while adding 'abd' ("All But Dissertation" as well
            # as عبد), which this had to be fixed for, though it is
            # not why the word was excluded. Same shape as the count
            # #397 describes.
            non_suffix = sum(1 for k in range(len(pieces))
                             if not title(k)
                             and (k == first_name_k or not suffix(k)))
            if non_suffix >= bound_join:
                merge(first_name_k, first_name_k + 2)
    return pieces, ptags


def group(state: ParseState) -> ParseState:
    tokens = list(state.tokens)
    dropped = list(state.dropped)
    ambiguities = list(state.ambiguities)
    all_pieces: list[tuple[tuple[int, ...], ...]] = []
    all_ptags: list[tuple[frozenset[str], ...]] = []
    # v1 parity: additional_parts_count=1 applies only to FAMILY_COMMA
    # parts; the SUFFIX_COMMA pre-comma segment gets 0.
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
        # Suppressed after a family comma for the same reason _assign
        # suppresses it there: the family name is already fixed, so
        # there is no fork left to report.
        pieces, ptags = _group_segment(
            seg, additional, tokens, bound_join,
            None if family_comma else ambiguities)
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
        # rules.md#M2: "a recognized maiden marker standing after at
        # least one name word takes the words after it — up to any
        # trailing suffix — as the maiden name, and the marker itself
        # is dropped" (history: decisions.md#M2)
        # maiden markers: a non-leading marker piece consumes following
        # pieces until a suffix; consumed tokens become MAIDEN, the
        # marker is dropped (#274)
        m = next((k for k in range(1, len(pieces))
                  if _is_maiden_marker_piece(pieces[k], tokens)),
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
    # rules.md#M1: "a leading recognized marker word inside a
    # multi-word clause being dropped; a one-word clause keeps its
    # word" — a marker inside EXTRACTED maiden content (#329).
    # classify tags
    # such a marker like any other token -- what the #274 rule above
    # lacks is not the TAG but the token: extract claims a delimited
    # clause and tokenize gives its tokens Role.MAIDEN up front, so
    # segment (main stream = role is None) leaves them out of every
    # segment, they never enter `pieces`, and a rule that walks pieces
    # cannot reach them.
    #
    # Scoped to the CLAUSE, via state.extracted (one role + inner span
    # per delimited region), rather than to a maiden token's
    # neighbours. Both reasons are load-bearing:
    #   * Role.MAIDEN is not proof of extraction -- the #274 rule above
    #     sets it too, on the bare form, earlier in this same function.
    #     A neighbour test would fire there and eat the 'Nee' out of
    #     "Jane Smith nee Nee Jones". Keying on extracted spans puts
    #     the bare path out of reach by construction.
    #   * Separate clauses are separate content. In "(Nee) (Jones)" the
    #     two land as one contiguous run of maiden tokens, so only the
    #     clause bound keeps the lone "(Nee)" intact.
    # Drop the clause's FIRST token only when the clause holds more
    # than one: `Nee` is a real surname (Irish Ni/Nee, and a Chinese
    # romanization), so a one-token "(Nee)" is a maiden name, not a
    # marker. FIRST token and no more, whatever the clause holds past
    # it: cases.py's maiden_marker_delimited_three_token_clause is the
    # row that bounds this in both directions, every other delimited
    # row having a two-token clause where the two readings agree.
    # Spans index the original string by the anti-#100
    # invariant, and script_segment only ever splits a token into
    # sub-slices, so containment stays exact.
    #
    # Bisect rather than scan the token list per clause: that is
    # quadratic in the number of delimited pairs, and "(a) " * 3200 --
    # 4x test_benchmark's base, NOT a doubling -- measured a 14.1x cost
    # against the 4.1x the same shape holds under a policy with no
    # maiden_delimiters. The control is what says which unit a ratio is
    # in: linear is ~4 for 4x the input and ~2 for a doubling, so a 4.1x
    # control cannot be per doubling. Re-measured 2026-08-03 at 11.2x
    # against 4.2x (3.2x against 2.1x per doubling) -- the separation
    # replicates, the exact ratio moves with the runner. Same idiom,
    # and the same reason, as _extract._overlaps and _tokenize's origin
    # resolution. test_benchmark's maiden_pairs shape is the guard.
    if any(role is Role.MAIDEN for role, _ in state.extracted):
        starts = [t.span.start for t in tokens]
        for role, clause in state.extracted:
            if role is not Role.MAIDEN:
                continue
            # first token starting at or after the clause opens; tokens
            # are span-sorted and group never reorders or resizes them
            first = bisect.bisect_left(starts, clause.start)
            # Testing the SECOND token's end proves BOTH are inside:
            # tokens do not overlap, so first.end <= second.start, and
            # bisect already put first.start at or after clause.start.
            # That is also the "more than one token" test, since the
            # tokens inside a clause are contiguous in index order.
            if (first + 1 < len(tokens)
                    and tokens[first + 1].span.end <= clause.end
                    and "vocab:maiden-marker" in tokens[first].tags):
                dropped.append(first)
    return dataclasses.replace(
        state, tokens=tuple(tokens), pieces=tuple(all_pieces),
        piece_tags=tuple(all_ptags), dropped=tuple(dropped),
        ambiguities=tuple(ambiguities))
