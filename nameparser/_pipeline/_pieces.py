"""Shared piece-level predicates for pipeline stages.

How a PIECE reads -- its tokens plus the tags the vocabulary layer left
on them -- where _vocab answers how a WORD reads. Both are consulted by
more than one stage; the split is by what the question takes, not by
which stage happens to ask (mechanisms.md#ONE-PREDICATE-PER-QUESTION).
_vocab says so from its own side: "Text-level tests used by more than
one stage; token/piece-level predicates live with their stage."

Before this module those predicates lived in _group, not because
grouping owned them but because assign imports group and cannot be
imported back, so group was the only place both stages could reach.
That is a fact about the import graph, and it had accumulated five
predicates across four PRs (#424, #425, #401/#421, #429).

The S2 trailing peel travels as the unit decisions.md describes it as --
_peel_walk, _peel_trailing and _trailing_start together -- though only
the first two cross a stage boundary.

Layering: imports _state and _vocab only, and nothing in the pipeline
imports it back.
"""
from __future__ import annotations

import re
from collections.abc import Sequence, Set
from typing import NamedTuple

from nameparser._pipeline._state import WorkToken
from nameparser._pipeline._vocab import is_trailing_numeral_suffix


# rules.md#H3: "successive title words at the start of the part
# carrying the given name chain into one title; a title word
# elsewhere in the name does not"
def _is_title_piece(piece: Sequence[int], ptags: Set[str],
                    tokens: Sequence[WorkToken]) -> bool:
    if "title" in ptags:
        return True
    return len(piece) == 1 and "vocab:title" in tokens[piece[0]].tags


# Ported verbatim from v1 (nameparser/config/regexes.py
# "period_abbreviation") -- layering forbids the config import; keep
# in sync by hand (tests/v2/test_regex_sync.py). Here rather than in
# assign since #424: the leading-title test is assign's, and group's
# leading-particle scan and trailing-run walk must start where assign
# starts.
_PERIOD_ABBREV = re.compile(r'^[^\W\d_]{2,}\.$')


# rules.md#H2: "an abbreviation opening the part of the name that
# carries the given name — the whole name, or the part after a
# family comma — reads as a title even when unlisted"
# (history: decisions.md#H2)
def _is_leading_title(piece: Sequence[int], ptags: Set[str],
                      tokens: Sequence[WorkToken]) -> bool:
    if _is_title_piece(piece, ptags, tokens):
        return True
    return (len(piece) == 1
            and bool(_PERIOD_ABBREV.match(tokens[piece[0]].text)))


def _leading_titles(pieces: Sequence[Sequence[int]],
                    ptags: Sequence[Set[str]],
                    tokens: Sequence[WorkToken]) -> int:
    """How many leading pieces assign peels as titles: the first
    non-title index. A title needs a following piece, unless the whole
    segment is one title (v1 parity). One definition, read by assign
    (which sets the roles) and by the chain's trailing-run walk; the
    leading-particle scan shares the predicate, _is_leading_title,
    but stops at a title-and-particle word (P4, #367, #424)."""
    n = 0
    while n < len(pieces):
        if ((n + 1 < len(pieces) or len(pieces) == 1)
                and _is_leading_title(pieces[n], ptags[n], tokens)):
            n += 1
            continue
        break
    return n


def _is_suffix_piece(piece: Sequence[int], ptags: Set[str],
                     tokens: Sequence[WorkToken]) -> bool:
    if "suffix" in ptags:
        return True
    if len(piece) != 1:
        return False
    tags = tokens[piece[0]].tags
    return "vocab:suffix" in tags and "initial" not in tags


def _segment_holds_no_name(pieces: Sequence[Sequence[int]],
                           ptags: Sequence[Set[str]],
                           tokens: Sequence[WorkToken]) -> bool:
    """The segment is titles and suffixes only ('John Smith, Dr.',
    'John Smith, Mr. Jr.') -- nothing in it is a name word.

    The FAMILY_COMMA rule "segment 0 is wholly the family name" rests on
    the writer having said where the family name ends. A comma followed
    by no name word said no such thing -- 'John Smith, Dr.' is 'Dr. John
    Smith' with the honorific moved, and 'John Smith, Mr. Jr.' the same
    with the postnominal along -- so the pre-comma name keeps its
    positional read instead of being merged. Uses the same
    _is_leading_title predicate the peel does, period-abbreviation
    inference included, so the two cannot disagree about what a title
    is; a suffix piece counts as what it is, so a mixed run like
    'Smith, Dr. Jr.' is a title and a postnominal, each read where it
    stands, and never a title run 'Dr. Jr.'. An empty segment
    ('Doe,, Jr.') holds no title to read by.

    TWO callers, asking it for different reasons, and the difference
    matters. assign uses it to decide whether the comma fixed the family
    name (above). group's one-entry join (#429) uses it to decide
    whether the segment is a credential run at all.

    True does NOT mean "every piece is a suffix" -- the title tolerance
    is the whole point, and a true segment can still hold pieces assign
    routes to TITLE, so a caller rendering the segment as one unit must
    ask _is_suffix_piece per piece as well. What assuming otherwise cost
    is recorded at the one-entry join in group(), the caller that made
    the assumption.
    """
    if not pieces:
        return False
    return all(_is_suffix_piece(pieces[k], ptags[k], tokens)
               or _is_leading_title(pieces[k], ptags[k], tokens)
               for k in range(len(pieces)))


class Peel(NamedTuple):
    """What assign's trailing peel made of a walk. `names` is a count
    of positions in the caller's `rest`: rest[:names] are the name
    pieces and rest[names:] the suffixes. The other two are pieces --
    token-index tuples, as PendingAmbiguity wants them -- and each is
    one token long: `numeral` is the piece the roman-numeral fork
    took (None when it did not fire; always the walk's last piece),
    `picks` the bare ambiguous acronyms the peel had to resolve, in
    peel order, either way (the last may sit at rest[names - 1])."""

    names: int
    numeral: tuple[int, ...] | None
    picks: tuple[tuple[int, ...], ...]


# rules.md#S2: "a trailing word of the suffix vocabulary reads as a
# suffix — generational forms and credential acronyms alike, and an
# ambiguous acronym written with its periods, one after each letter,
# counts unambiguously; a single trailing period is the abbreviation
# shape any word can wear and does not. A BARE ambiguous acronym is
# consumed only when the name has words to spare"
# (v1's are_suffixes tail rule, with the roman-numeral special)
def _peel_walk(start: int, ptags: Sequence[Set[str]],
               skip: Set[int] = frozenset()) -> list[int]:
    """The indices _peel_trailing walks: `start` to the segment's end,
    minus the group-flagged credential pieces (the Ph. D. merge),
    which assign reads as suffixes at any position, and minus `skip`
    -- a tail segment's delimiter cores, which are structure rather
    than words (the maiden walk's case, #424). Built here and nowhere
    else, so the walk's input cannot drift between assign and the
    three group sites that read it: the numeral fork is a last-piece
    test that reads the piece before as rest[k - 2], which holds only
    over this list."""
    return [j for j in range(start, len(ptags))
            if j not in skip and "suffix" not in ptags[j]]


def _trailing_start(start: int, pieces: Sequence[Sequence[int]],
                    ptags: Sequence[Set[str]], tokens: Sequence[WorkToken],
                    skip: Set[int] = frozenset(),
                    numeral_only: bool = False) -> int:
    """Where assign's trailing suffix run begins, read over the pieces
    as they stand from `start`: the index of the first piece the S2
    peel takes, or len(pieces) when it takes none (#424). What P2's
    chain and M2's walk stop before -- each had asked "is this a
    suffix?" with the suffix-piece test, which vetoes a bare 'V' as
    an initial (the #401 question), and so took a trailing numeral,
    or a bare acronym with words to spare, into the family or the
    maiden name.

    `numeral_only` is the maiden walk's reading: the bare-acronym
    fork counts pieces, and the walk removes the very pieces it
    counted, so an acronym peeled over the pieces as they stand may
    be the family of what is left ('John née Jones Smith Ma' read
    maiden 'Jones Smith', family 'Ma'). The numeral fork reads one
    piece, the one before the numeral, and _maiden_take re-asks it
    with the piece the take leaves there; the acronym is left to
    assign."""
    rest = _peel_walk(start, ptags, skip)
    peeled = _peel_trailing(rest, pieces, ptags, tokens)
    if numeral_only:
        return rest[-1] if peeled.numeral is not None else len(pieces)
    return rest[peeled.names] if peeled.names < len(rest) else len(pieces)


def _peel_trailing(rest: Sequence[int], pieces: Sequence[Sequence[int]],
                   ptags: Sequence[Set[str]],
                   tokens: Sequence[WorkToken]) -> Peel:
    """The S2 trailing peel over `rest`, a _peel_walk list. Housed
    here rather than in assign because assign imports group's piece
    predicates, and group's bound-given reserve asks the same question
    of the view the join would leave (#425): one walk, so the reserve
    and the assignment cannot drift. Pure -- the ambiguities are
    returned for assign to report, in the order it always reported
    them."""
    picks: list[tuple[int, ...]] = []
    numeral: tuple[int, ...] | None = None
    k = len(rest)
    while k > 0:
        piece = pieces[rest[k - 1]]
        if _is_suffix_piece(piece, ptags[rest[k - 1]], tokens):
            k -= 1
            continue
        # a final single letter that is a roman numeral, after a piece
        # that is not initial-shaped; the predicate's docstring carries
        # the is_initial_shaped reasoning (#320)
        if (k == len(rest) and k >= 2 and len(piece) == 1
                and is_trailing_numeral_suffix(
                    tokens[piece[0]].text,
                    tokens[pieces[rest[k - 2]][0]].text)):
            numeral = tuple(piece)
            k -= 1
            continue
        # A bare ambiguous acronym ("MA", not "M.A.") is a credential
        # only when peeling it still leaves a given AND a family name.
        # With two pieces, "one of them is a credential" is the less
        # likely reading, so it stays the family name -- "Jack MA" is a
        # person, "John Smith MA" is a person with a degree. This is
        # v1's reserve_last narrowed to the ambiguous set: 2.0
        # deliberately peels UNambiguous suffixes even when nothing is
        # left ("Smith PhD" -> suffix, a classified fix), because there
        # the vocabulary is not in doubt.
        bare_ambiguous = (len(piece) == 1
                          and "vocab:suffix-ambiguous" in tokens[piece[0]].tags)
        # k < 2 means it is the only piece left, which is not the fork
        # this reports.
        if bare_ambiguous and k >= 2:
            picks.append(tuple(piece))
            if k >= 3:            # peeling still leaves given + family
                k -= 1
                continue
        break
    return Peel(k, numeral, tuple(picks))
