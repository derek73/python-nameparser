"""Stage: group.

Consumes: tokens (classified), segments, structure, extracted (the
role + inner span per delimited region, for the #329 pass below --
the only stage after tokenize that reads it).
Produces: pieces + piece_tags per segment (runs of token indices --
tokens are NEVER joined into strings: the anti-#100 invariant); maiden
tail tokens get role=MAIDEN; marker tokens land in dropped.
Reads: token tags (from classify), Lexicon.given_name_titles (the
P5 licence, #369), and Policy.extra_suffix_delimiters, whose
delimiter-core tokens tail segments drop (v1 suffix_delimiter parity)
-- no other Policy field. The v1 "derived titles/prefixes"
registration becomes piece_tags entries -- per-parse state that
dissolves with the state (v1 kept per-parse sets for the same reason).

Implements rules P2, P3, P4 and M2, and the
group half of M1 (#329: the marker dropped inside EXTRACTED maiden
content, which M2's pieces walk cannot reach because extract's
content never enters pieces); each is cited at its code below. Also
implements rule P5 (cited below at the bound-given join) and ports
the "Ph. D."-split merge (v1 fix_phd; decisions.md#phd-merge).

The piece-level predicates moved to _pieces in #439 -- the S2
trailing peel, the leading-title and title-piece tests, the
suffix-piece test, the no-name-segment test. Most are shared with
assign; is_title_piece and trailing_start are group's alone and
travelled because the shared ones call them. They had collected here
by import direction rather than by topic (assign imported group and
could not be imported back), which is the accumulation
mechanisms.md#ONE-PREDICATE-PER-QUESTION describes; group imports them
back like any other caller, and still does the work H3 and S2 describe
with them. What remains defined here is group's own: _is_prefix_piece,
_is_conj_piece, _is_rootname and _is_maiden_marker_piece.
"""
from __future__ import annotations

import bisect
import dataclasses
from collections.abc import Sequence, Set
from enum import IntEnum

from nameparser._lexicon import _title_key
from nameparser._pipeline._pieces import (
    is_leading_title, is_suffix_piece, is_title_piece,
    leading_titles, peel_trailing, peel_walk, segment_suffix_reading,
    trailing_start,
)
from nameparser._pipeline._state import (
    ParseState, PendingAmbiguity, Structure, WorkToken,
)
from nameparser._pipeline._vocab import D, PH
from nameparser._pipeline._vocab import delimiter_cores
from nameparser._types import AmbiguityKind, Role

# the credential-pair regexes live in _vocab, whose own
# is_wholly_suffix merges the same pair -- and since #319 that
# predicate has TWO callers to stay in sync with, segment's
# suffix-comma structure test and script_segment's decline of a
# wholly-suffix post-comma run, both of which see the merged reading

Piece = list[int]
#: What the marker pass took out of a segment: the marker piece (to be
#: dropped) and the maiden-name pieces (to take Role.MAIDEN).
MaidenTake = tuple[Piece, list[Piece]]


class BoundJoin(IntEnum):
    """v1 _join_bound_first_name's reserve_last, as the three states it
    actually has. IntEnum: the value IS the number of name pieces
    assign's peel must leave in the JOINED view for the join to stand
    (#425), so the >= comparison below reads unchanged. Post-comma no
    peel is run -- the pair alone is that one piece -- and DISABLED
    is a mode, never compared: as a threshold 0 would join everything,
    which is why the block is entered on identity first."""

    DISABLED = 0   # the FAMILY_COMMA family segment (v1 never joined it)
    LENIENT = 1    # FAMILY_COMMA's post-comma segment (reserve_last=False)
    STRICT = 2     # main segments (reserve_last=True: keep a family piece)


# rules.md#S2: "a trailing word of the suffix vocabulary reads as a
# suffix" -- group does not decide that; it stops before whatever
# trailing_start says the run is, so the chain and the maiden walk
# end where assign's peel begins (#424).
# rules.md#P2: "a particle joins the words after it into one name
# part, the join running until the next particle starts a group of
# its own, a trailing suffix begins" -- and on to the maiden marker
# (M2) or the name's end; the final group reads as the family name,
# earlier groups by position. (history: decisions.md#P2)
# rules.md#P4: "a particle in the name's leading position chains
# nothing: the words stay separate" (history: decisions.md#P2)
def _is_prefix_piece(piece: Sequence[int], ptags: Set[str],
                     tokens: Sequence[WorkToken]) -> bool:
    if "prefix" in ptags:
        return True
    return len(piece) == 1 and "particle" in tokens[piece[0]].tags


# rules.md#M2: "a recognized maiden marker standing after at least
# one name word takes the words after it" -- up to any suffix word,
# or the trailing numeral assign reads as the suffix, as the maiden
# name, the marker itself dropped
# (history: decisions.md#M2)
#
# A marker piece is a LONE marker -- M2's own "standing as a word of
# its own". The consumer runs before every join but the Ph. D. merge
# (see _group_segment), so a marker inside a wider piece is one the
# consumer left there: declined ("Jane van der Berg née" reads family
# 'van der Berg née'), or never examined (a leading marker, or a second
# marker behind the span it took). Matching inside joined pieces would
# re-read those.
#
# With the pass ahead of the joins no default-vocabulary input reaches
# the lone-piece half through the one caller left that sees joined
# pieces (P5's marker decline, marker(fk + 1)): a marker-headed wider
# piece needs a connective right after a declined marker, and a
# connective after a marker is a word the consumer takes. Measured at
# #420's review --
# dropping `len(piece) == 1` leaves the suite and a 337k-name sweep
# identical -- so it stays as the rule's definition, not as a guard a
# pin holds.
def _is_maiden_marker_piece(piece: Sequence[int],
                            tokens: Sequence[WorkToken]) -> bool:
    return (len(piece) == 1
            and "vocab:maiden-marker" in tokens[piece[0]].tags)


def _maiden_take(pieces: Sequence[Sequence[int]],
                 ptags: Sequence[Set[str]],
                 tokens: Sequence[WorkToken],
                 cores: Set[str]) -> list[int] | None:
    """The indices of the pieces the marker pass removes, the marker
    first, or None.

    Computed before any join (the Ph. D. merge aside), so "up to any
    trailing suffix" means the first suffix WORD after the marker: a
    connective beside that suffix cannot un-suffix it first. 'Jane
    Smith née Jr y Jones' declines where the joined reading took
    'Jr y Jones' as the maiden name, and 'Jane Smith née Jones Jr y
    Smith' takes only 'Jones'. The one reading the order costs; M2's
    Accepted row and decisions.md#M2 (#420) record it.

    A tail segment's delimiter cores (`cores`, empty elsewhere) are
    structure, not words, and group() drops them after the pass --
    before the pass moved ahead of the joins it dropped them first.
    So the walk steps over them: a core is neither a word the marker
    can take ('PhD née - Jones' read maiden '- Jones') nor the name
    word M2 needs ahead of the marker ('- née Jones' took 'Jones',
    leaving the core alone, which the drop then kept as the segment's
    only piece). They stay in place for the drop, which still sees
    the segment as written, which is why this returns indices rather
    than a slice.
    """
    seen = [k for k in range(len(pieces))
            if not (len(pieces[k]) == 1
                    and tokens[pieces[k][0]].text in cores)]
    m = next((v for v in range(1, len(seen))
              if _is_maiden_marker_piece(pieces[seen[v]], tokens)), None)
    if m is None:
        return None
    # "up to any trailing suffix": a suffix WORD anywhere after the
    # marker ends the maiden name, and so does the trailing numeral as
    # assign will read it, which the suffix-piece test does not see
    # (#424): 'John née Jones Smith V' took the V as maiden text. The
    # numeral only -- trailing_start says why the acronym fork is
    # left to assign here. Read from the MARKER, not after it: a
    # numeral straight after the marker then has the piece before it
    # the fork wants, and 'Jane Smith née V' declines like 'Jane Smith
    # née PhD' -- nothing after the marker but a suffix, so the marker
    # stays a word -- as 1.4.0 read it.
    skip = frozenset(range(len(pieces))) - frozenset(seen)
    trailing = trailing_start(seen[m], pieces, ptags, tokens, skip,
                               numeral_only=True)
    # The fork reads the piece before the numeral, and the take
    # REMOVES that piece: afterwards assign sees the piece before the
    # marker there, and if that is initial-shaped the fork will not
    # fire -- a walk that stopped anyway handed the V to the family
    # ('J. née Jones Smith V'). So the numeral must read as the suffix
    # as the take would leave the name too, and the question is asked
    # the way P5's reserve asks it (#425): the peel is run over the
    # VIEW the take would leave, not one condition of it -- the first
    # re-ask checked the preceding piece alone, and a title before the
    # marker ('Dr. née Jones Smith V') leaves the numeral as assign's
    # whole rest, where no fork fires at all (the code review).
    if trailing < len(pieces):
        left = [i for i in seen if i < seen[m] or i >= trailing]
        view = [pieces[i] for i in left]
        view_tags = [ptags[i] for i in left]
        if trailing_start(leading_titles(view, view_tags, tokens),
                           view, view_tags, tokens,
                           numeral_only=True) == len(view):
            trailing = len(pieces)
    j = m + 1
    while (j < len(seen) and seen[j] < trailing
           and not is_suffix_piece(pieces[seen[j]], ptags[seen[j]],
                                    tokens)):
        j += 1
    # j == m + 1 means nothing followed the marker but a suffix, so the
    # pass declines and the marker stays an ordinary word (rules.md#M2).
    return seen[m:j] if j > m + 1 else None


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
    return not (is_title_piece(piece, ptags, tokens)
                or _is_prefix_piece(piece, ptags, tokens)
                or is_suffix_piece(piece, ptags, tokens))


def _group_segment(seg: tuple[int, ...], additional: int,
                   tokens: Sequence[WorkToken],
                   bound_join: BoundJoin = BoundJoin.STRICT,
                   ambiguities: list[PendingAmbiguity] | None = None,
                   cores: Set[str] = frozenset(),
                   given_name_titles: Set[str] = frozenset(),
                   ) -> tuple[list[Piece], list[set[str]], MaidenTake | None]:
    pieces: list[Piece] = [[i] for i in seg]
    ptags: list[set[str]] = [set() for _ in seg]
    # Out-parameter, same shape as _assign_main: forks are reported
    # where they are decided. A caller that passes None (or a throwaway
    # list) suppresses reporting -- see group() for when that applies.
    if ambiguities is None:
        ambiguities = []

    def title(k: int) -> bool:
        return is_title_piece(pieces[k], ptags[k], tokens)

    def prefix(k: int) -> bool:
        return _is_prefix_piece(pieces[k], ptags[k], tokens)

    def suffix(k: int) -> bool:
        return is_suffix_piece(pieces[k], ptags[k], tokens)

    def conj(k: int) -> bool:
        return _is_conj_piece(pieces[k], ptags[k], tokens)

    def marker(k: int) -> bool:
        return _is_maiden_marker_piece(pieces[k], tokens)

    def joined_tags(lo: int, hi: int, add: Set[str] = frozenset(),
                    drop: Set[str] = frozenset()) -> set[str]:
        # the ONE definition of a merged piece's tags: merge() applies
        # it, and P5's reserve reads it to model the join it is
        # weighing (#425) -- so the view cannot drift from the merge.
        # A merged piece inherits every part's tags, so a site whose
        # product is not what its parts were drops what no longer
        # applies: the particle chain drops `prefix`, the bound join
        # `title` (a derived title tag on the pair would have assign
        # peel the given name as a leading title).
        return (set().union(*ptags[lo:hi]) | add) - drop

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
        ptags[lo:hi] = [joined_tags(lo, hi, add, drop)]

    # ph-d merge first: "Ph." "D." adjacent -> one suffix piece
    # (decisions.md#phd-merge; v1 fix_phd did this by regex on the
    # raw string)
    k = 0
    while k < len(pieces) - 1:
        a, b = pieces[k], pieces[k + 1]
        if (len(a) == 1 and len(b) == 1
                and PH.fullmatch(tokens[a[0]].text)
                and D.fullmatch(tokens[b[0]].text)):
            merge(k, k + 2, add={"suffix"})
        else:
            k += 1

    # rules.md#M2: "a recognized maiden marker standing after at least
    # one name word takes the words after it" -- up to any suffix
    # word, or the trailing numeral assign reads as the suffix, as the
    # maiden name, the marker itself dropped
    # (history: decisions.md#M2) -- the marker pass (#274), and it runs
    # BEFORE every join below. Each join rule asks a question about the
    # name -- how many words it has (P3's carve-out, P5's reserve),
    # what the word after a particle or a bound word is -- and the
    # marker and the maiden name are not part of that name: they leave.
    # Asked while they were still pieces, the count answered for a name
    # that would not exist ('juan y garcia nee jones' counted five, 'y'
    # joined, and the family was empty once the clause left: #418), and
    # a join could absorb the marker before the pass looked for a lone
    # one ('Jane van der Berg née y Jones' kept the marker in the
    # family: #412). Removing the pieces first makes both impossible by
    # construction, with no stop on the chain (#399, #417) and no
    # exclusion in the reserve (#411) left to keep in step.
    #
    # The tokens are not touched here: this function reads them and
    # returns what it took, and group() records the drop and the roles.
    taken: MaidenTake | None = None
    take = _maiden_take(pieces, ptags, tokens, cores)
    if take is not None:
        taken = (pieces[take[0]], [pieces[k] for k in take[1:]])
        for k in reversed(take):
            del pieces[k]
            del ptags[k]

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
        # A maiden marker the consumer took is already gone (the pass
        # above), so the chain cannot carry a maiden name into the
        # family the way "Ursula von der Leyen geb. Albrecht" once read
        # family 'von der Leyen geb. Albrecht' (#399). A marker still
        # here is one the consumer DECLINED -- nothing after it but a
        # suffix, or nothing at all -- and M2 says that is just a word,
        # so the chain takes it like any other: "Jane van der Berg née"
        # reads family 'van der Berg née'. Stopping at it instead
        # stranded it as a lone trailing piece that took the family
        # field (#399's review), and a stop gated on "will the consumer
        # take it" had to restate the consumer's condition and got it
        # wrong one suffix later (#417).
        #
        # The `, 0` fallback is inert by construction rather than a
        # default worth testing: it is reached only when every piece is
        # a title and none is a prefix, and the loop below merges
        # nothing unless some piece is a prefix.
        # `title(k)` alone missed H2's unlisted abbreviations, which
        # assign peels as titles all the same, so 'Xyz. van Johnson'
        # chained where 'Dr. van Johnson' did not (#424 found it
        # through the acronym fork: the chain had swallowed the given
        # word and left assign two pieces where the fork counted
        # three). The scan asks assign's own test.
        leading = next((k for k in range(len(pieces))
                        if not is_leading_title(pieces[k], ptags[k],
                                                 tokens)
                        or prefix(k)), 0)
        # rules.md#P2: "a trailing suffix begins" -- where it begins
        # is read by assign's peel over the pieces as they stand
        # (#424), once per segment and kept as a length from the end,
        # which the chain's merges ahead of it do not move -- except
        # where a particle that is suffix vocabulary too (vd, mc, do)
        # starts the run: the prefix run below takes it as a particle,
        # as P6 reads it after a comma, and 'John van Mc' keeps family
        # 'van Mc' (every baseline's reading). A suffix WORD stops the
        # chain wherever it stands, and the trailing
        # run -- the numeral, or the bare acronym with words to spare
        # -- stops it where the suffix-piece test alone did not ('John
        # van der Berg V' read family 'van der Berg V'). The chain
        # takes both forks, and asks again after its merges whether
        # the acronym still has the pieces the fork counted (below).
        name_start = leading_titles(pieces, ptags, tokens)
        tail = len(pieces) - trailing_start(name_start, pieces, ptags,
                                             tokens)
        def chain(tail: int) -> None:
            k = 0
            while k < len(pieces):
                if k == leading or not prefix(k):
                    k += 1
                    continue
                j = k + 1
                while j < len(pieces) and prefix(j):
                    j += 1
                while (j < len(pieces) - tail and not prefix(j)
                       and not suffix(j)):
                    j += 1
                # The other half of PARTICLE_OR_GIVEN. _assign reports the
                # fork when an ambiguous particle stays a lone leading piece
                # ("Van Johnson" -> given under the default order, family
                # under FAMILY_FIRST); the chain here takes the opposite
                # branch when the particle is not the name's leading piece.
                # A fork whose two sides are decided in different stages
                # needs an emitter in each.
                #
                # Narrow, and #367 is why. `all(is_leading_title(...))`
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
                        and all(is_leading_title(pieces[x], ptags[x],
                                                  tokens)
                                for x in range(k))):
                    i = pieces[k][0]
                    ambiguities.append(PendingAmbiguity(
                        AmbiguityKind.PARTICLE_OR_GIVEN,
                        f"{tokens[i].text!r} was chained onto the following "
                        f"name piece; it is also a given name in other "
                        f"names",
                        (i,)))
                merge(k, j, drop={"prefix"})
                k += 1

        # The peel was read over the pieces as they stand, and the
        # chain's own merges can change what it counts: behind a word
        # in both the title and particle vocabularies the scan above
        # stops where assign's title peel does not (P4, #367), so the
        # chain takes the name's first word, and the acronym the fork
        # counted with three pieces meets assign with two -- 'Freiherr
        # von Berg Ma' read given 'von Berg', family 'Ma' (1.4.0's
        # reading; the reviews found it behind the claim that the
        # merges leave the count alone). So the peel is asked again
        # over the pieces the chain leaves, and where it no longer
        # takes what the chain stopped before, the chain runs again
        # without that stop: what assign will not peel is a name word,
        # and the chain takes it. The numeral cannot flip (a chain
        # group is never initial-shaped), so the second run is the
        # acronym's alone, and rare; the snapshot is one copy per
        # segment with a trailing run, linear like the rest.
        if tail:
            kept = ([list(q) for q in pieces], [set(t) for t in ptags],
                    len(ambiguities))
            chain(tail)
            left = len(pieces) - trailing_start(
                leading_titles(pieces, ptags, tokens), pieces, ptags,
                tokens)
            if left < tail:
                pieces[:], ptags[:] = kept[0], kept[1]
                del ambiguities[kept[2]:]
                chain(left)
        else:
            chain(0)
        # rules.md#P5: "a recognized bound given-name word joins the
        # word after it into one given name" (history: decisions.md#P5)
        # -- bound given names: the first non-title piece joins the next
        # ONCE (pairwise, v1 parity: 'Salem, Abdul Rahman Ahmed' keeps
        # Ahmed a middle name). BoundJoin encodes v1's reserve_last.
        # "the first non-title piece" by assign's count (#424): group's
        # title test does not see H2's unlisted abbreviations, and
        # 'Xyz. abdul John Smith' joined nothing where 'Dr. abdul John
        # Smith' read given 'abdul John'.
        fk = leading_titles(pieces, ptags, tokens)
        if (bound_join is not BoundJoin.DISABLED
                and fk + 1 < len(pieces)
                and len(pieces[fk]) == 1
                and "vocab:bound-given" in tokens[pieces[fk][0]].tags):
            # P5 joins the bound word to "the word after it", and a
            # marker is not a name word -- it is the announcement that
            # another name follows. The only marker left by now is one
            # the consumer declined (nothing after it, or nothing but
            # a suffix), and the join must still not take it: 'Berg,
            # abdul nee PhD' read given 'abdul nee', and 'Berg, abdul
            # nee' clears the LENIENT reserve the same way. Measured
            # rather than assumed -- dropping this undid #411 on
            # exactly that row. Nor is a suffix piece (#421) --
            # rules.md#P5: "nor a word of the unambiguous suffix
            # vocabulary (S2), wherever position will then place it"
            # -- and declining it is also what keeps merge()'s tag
            # union from making the joined piece a suffix piece.
            if marker(fk + 1) or suffix(fk + 1):
                pass
            elif bound_join is BoundJoin.LENIENT:
                # post-comma the family is fixed and the pair is the
                # given whatever follows, so no peel is read
                # (decisions.md#P5, #423)
                merge(fk, fk + 2, drop={"title"})
            else:
                # rules.md#P5: "the join is tried on the pieces as it
                # would leave them, assign's trailing peel (S2) is read
                # over that, and the name words it leaves are the words
                # to spare" (history: decisions.md#P5). The view is what
                # merge() builds -- the same slice assignment, the same
                # joined_tags -- and the peel is assign's own, so the
                # reserve and the assignment cannot drift. And the join
                # changes no suffix reading -- rules.md#P5: "a word the
                # peel reads as a suffix unjoined must read so joined,
                # or the join declines" -- compared as the peeled
                # pieces themselves: 'abdul V' peels the V unjoined and
                # nothing joined, 'abdul Smith Ma' peels the acronym
                # unjoined and keeps it joined. Shapes pinned in
                # test_group.py.
                rest = peel_walk(fk, ptags)
                before = peel_trailing(rest, pieces, ptags, tokens)
                view, view_tags = list(pieces), list(ptags)
                view[fk:fk + 2] = [pieces[fk] + pieces[fk + 1]]
                view_tags[fk:fk + 2] = [joined_tags(fk, fk + 2,
                                                    drop={"title"})]
                view_rest = peel_walk(fk, view_tags)
                after = peel_trailing(view_rest, view, view_tags, tokens)
                same_suffixes = (
                    [tuple(view[j]) for j in view_rest[after.names:]]
                    == [tuple(pieces[j]) for j in rest[before.names:]])
                # A given-name title ahead of the bound word asserts
                # that a given name follows -- the assertion H1 reads
                # when it keeps "Sir John" a given name -- so behind
                # one there is no family to spare (#369). Keyed on the
                # WHOLE title run exactly as post_rules keys H1, so the
                # two rules cannot disagree about what one run asserts
                # (post_rules' run also takes H2's unlisted
                # abbreviations, which no given-name title key can
                # contain, so the runs match whenever the key does).
                # The licence lifts the reserve for two name WORDS: the
                # piece the join would take must be one word -- a
                # particle chain is the family name P2 built ('Sir
                # abdul van der Berg' keeps family 'van der Berg').
                licensed = (fk > 0 and len(pieces[fk + 1]) == 1
                            and _title_key(tokens[i].text
                                           for k in range(fk)
                                           for i in pieces[k])
                            in given_name_titles)
                reserve = BoundJoin.LENIENT if licensed else BoundJoin.STRICT
                if same_suffixes and after.names >= reserve:
                    # the pair is a given name whatever tag the word
                    # carried (rules.md#P5); joined_tags says why the
                    # title tag is dropped. Pinned in test_group.py.
                    merge(fk, fk + 2, drop={"title"})
    return pieces, ptags, taken


def group(state: ParseState) -> ParseState:
    tokens = list(state.tokens)
    dropped = list(state.dropped)
    ambiguities = list(state.ambiguities)
    all_pieces: list[tuple[tuple[int, ...], ...]] = []
    all_ptags: list[tuple[frozenset[str], ...]] = []
    # v1 parity: additional_parts_count=1 applies only to FAMILY_COMMA
    # parts; the SUFFIX_COMMA pre-comma segment gets 0.
    additional = 1 if state.structure is Structure.FAMILY_COMMA else 0
    # v1 expand_suffix_delimiter parity (#206): tail segments (wholly
    # consumed as suffixes by assign) drop delimiter-core tokens, the
    # same structural mechanism as the maiden marker (taken out in
    # _group_segment, recorded in `dropped` just below)
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
        tail = tail_start is not None and seg_idx >= tail_start
        seg_cores = cores if tail else frozenset()
        pieces, ptags, taken = _group_segment(
            seg, additional, tokens, bound_join,
            None if family_comma else ambiguities,
            seg_cores,
            state.lexicon.given_name_titles)
        # the marker is dropped and the maiden name's tokens become
        # MAIDEN (#274); which pieces those are was settled in
        # _group_segment, before the joins
        if taken is not None:
            marker_piece, maiden_pieces = taken
            dropped.extend(marker_piece)
            for piece in maiden_pieces:
                for i in piece:
                    tokens[i] = dataclasses.replace(
                        tokens[i], role=Role.MAIDEN)
        # rules.md#C1: "a part that is nothing but suffix words is the
        # credential run and reads as suffixes, whole" -- WHOLE is this
        # block's half of the rule, the routing being assign's.
        # One comma segment is one suffix entry. `tail` answers that by
        # INDEX, which is right wherever assign reads the segment as
        # suffixes for the same structural reason -- but not after a
        # ONE-WORD family comma, where segment 1 is a name slot that
        # assign re-reads by CONTENT: a segment of nothing but
        # credentials is the credential run, whole (#296/#325). group
        # asking the index while assign asked the content is what made
        # 'Smith, MD PhD' render 'MD, PhD' with a comma the writer
        # never typed, where the full-name 'John Smith, MD PhD' has
        # rendered 'MD PhD' since 1.4.0 (#429). Ask assign's own
        # predicate, over the pieces group just built.
        # `family_comma` is redundant by invariant and kept for
        # locality: segment() emits at most one segment for NO_COMMA, so
        # seg_idx == 1 already implies a comma, and under SUFFIX_COMMA
        # tail_start is 1, so `tail` short-circuits before this. Nothing
        # can pin it -- dropping it is an equivalent mutant over the
        # corpora and 65,725 generated inputs -- so it is documented
        # rather than tested.
        reading = (segment_suffix_reading(pieces, ptags, tokens)
                   if family_comma and seg_idx == 1 else None)
        one_entry = tail or reading is not None
        if one_entry:
            # v1 renders each tail COMMA SEGMENT as one suffix entry
            # ('Smith, V MD' -> suffix 'V MD'); a delimiter core inside
            # a segment separates entries and is dropped, but a segment
            # that IS only the core stays whole (v1 expand() splits
            # within a part, never erases a lone part). Continuation
            # tokens within an entry take the stable "joined" tag so
            # the suffix view space-joins them (the fix_phd mechanism).
            # Core dropping stays keyed on `tail` via seg_cores: the
            # #206 parity is a TAIL rule, and the one-entry join is the
            # only half that follows assign's content read.
            entry_open = False
            kept: list[int] = []
            for k in range(len(pieces)):
                is_core = (len(pieces[k]) == 1
                           and tokens[pieces[k][0]].text in seg_cores
                           and len(pieces) > 1)
                if is_core:
                    dropped.extend(pieces[k])
                    entry_open = False
                    continue
                kept.append(k)
                # Two different joins, and conflating them is what a
                # widened condition gets wrong. WITHIN a piece (pos > 0)
                # the tag renders a merged piece as one unit; the branch
                # is written role-blind because the merge is (the ph-d
                # pair reaches GIVEN as one element), though no
                # multi-token TITLE piece witnesses it -- none turned up
                # in 38,892 generated family-comma inputs. BETWEEN pieces it continues an ENTRY,
                # and only pieces that render into the same run may do
                # that. On a tail segment every kept piece does -- that
                # is what `tail` means -- but off it assign routes piece
                # by piece (_assign.py), so a title piece is not part of
                # the suffix entry -- and the reading that says which is
                # which is assign's own, computed once above rather than
                # re-derived here: is_suffix_piece alone refuses a
                # numeral continuing a credential run, which would
                # render 'Smith, PSM I' as 'PSM, I' (#430). Letting one continue the entry tags
                # a token the SUFFIX view never joins and the TITLE view
                # does: 'Smith, Rev. Dr.' collapsed title_list to
                # ['Rev. Dr.'], and after a pre-comma suffix the tag
                # glued across the writer's own comma ('Smith Jr., Mr.
                # Jr.' rendered suffix 'Jr. Jr.') -- the inverse of the
                # bug this block exists to fix.
                in_entry = tail or (reading is not None
                                    and reading[k])
                for pos, i in enumerate(pieces[k]):
                    if pos > 0 or (in_entry and entry_open):
                        tokens[i] = dataclasses.replace(
                            tokens[i], tags=tokens[i].tags | {"joined"})
                # Sticky across a piece that is not in the entry, so an
                # interleaved title does not split the run it sits in:
                # 'Smith, MD Dr. PhD' renders suffix 'MD PhD', not
                # 'MD, PhD'. A delimiter core still closes the entry
                # (above) -- that is the one thing that separates two.
                entry_open = entry_open or in_entry
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
