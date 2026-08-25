"""Shared piece-level predicates for pipeline stages.

How a PIECE reads -- its tokens, plus the tags classify wrote on them
and the tags group derived for the piece -- where _vocab answers how a
WORD reads from text alone. Both are consulted by more than one
stage; the split is by what the question takes, not by
which stage happens to ask (mechanisms.md#ONE-PREDICATE-PER-QUESTION).
_vocab points here from its own side: "Text-level tests used by more
than one stage; piece-level ones live in _pieces, the sibling layer
over tokens-plus-tags."

Before this module those predicates lived in _group, not because
grouping owned them but because assign imported group and could not be
imported back, so group was the only place both stages could reach.
They arrived there that way across three PRs -- #424 brought
is_leading_title, leading_titles and trailing_start, #425 the peel
(peel_walk, peel_trailing), #429 segment_holds_no_name.
is_title_piece and is_suffix_piece are older than any of that: they
were group's from its first commit, and travel because the others
call them.

The import that forced all of it is the one #439 removed: assign no
longer names _group at all. What still holds is the rule that replaced
it, and tests/v2/test_layering.py is where it is written down -- a
piece predicate may not depend on a stage, in either direction.

The S2 trailing peel travels as the unit decisions.md describes --
peel_walk, peel_trailing and trailing_start together -- though only
the first two cross a stage boundary.

Layering: imports _state and _vocab only; _group and _assign import
it, and neither of the two it imports imports it back.

Naming follows _vocab's: inside an already-private module the leading
underscore marks module-PRIVATE, so the names other stages call are
bare and only the internals keep it (_PERIOD_ABBREV here). Getting that
backwards -- which this module did until the underscores came off --
costs a reader the one cheap way to tell a shared predicate from a
helper.
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
def is_title_piece(piece: Sequence[int], ptags: Set[str],
                    tokens: Sequence[WorkToken]) -> bool:
    if "title" in ptags:
        return True
    return len(piece) == 1 and "vocab:title" in tokens[piece[0]].tags


# Ported verbatim from v1 (nameparser/config/regexes.py
# "period_abbreviation") -- layering forbids the config import; keep
# in sync by hand (tests/v2/test_regex_sync.py). Out of assign since
# #424 and in the piece layer since #439: the test is assign's, and group's
# leading-particle scan and trailing-run walk must start where assign
# starts.
_PERIOD_ABBREV = re.compile(r'^[^\W\d_]{2,}\.$')


# rules.md#H2: "an abbreviation opening the part of the name that
# carries the given name — the whole name, or the part after a
# family comma — reads as a title even when unlisted"
# (history: decisions.md#H2)
def is_leading_title(piece: Sequence[int], ptags: Set[str],
                      tokens: Sequence[WorkToken]) -> bool:
    if is_title_piece(piece, ptags, tokens):
        return True
    return (len(piece) == 1
            and bool(_PERIOD_ABBREV.match(tokens[piece[0]].text)))


def leading_titles(pieces: Sequence[Sequence[int]],
                    ptags: Sequence[Set[str]],
                    tokens: Sequence[WorkToken]) -> int:
    """How many leading pieces assign peels as titles: the first
    non-title index. A title needs a following piece, unless the whole
    segment is one title (v1 parity). One definition, read by assign
    (which sets the roles) and by the chain's trailing-run walk; the
    leading-particle scan shares the predicate, is_leading_title,
    but stops at a title-and-particle word (P4, #367, #424)."""
    n = 0
    while n < len(pieces):
        if ((n + 1 < len(pieces) or len(pieces) == 1)
                and is_leading_title(pieces[n], ptags[n], tokens)):
            n += 1
            continue
        break
    return n


def is_suffix_piece(piece: Sequence[int], ptags: Set[str],
                     tokens: Sequence[WorkToken]) -> bool:
    if "suffix" in ptags:
        return True
    if len(piece) != 1:
        return False
    tags = tokens[piece[0]].tags
    return "vocab:suffix" in tags and "initial" not in tags


def segment_holds_no_name(pieces: Sequence[Sequence[int]],
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
    is_leading_title predicate the peel does, period-abbreviation
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
    ask is_suffix_piece per piece as well. What assuming otherwise cost
    is recorded at the one-entry join in group(), the caller that made
    the assumption.
    """
    return segment_suffix_reading(pieces, ptags, tokens) is not None


def _numeral_behind_the_initial_veto(piece: Sequence[int],
                                     tokens: Sequence[WorkToken]) -> bool:
    """Suffix vocabulary that is_suffix_piece refuses because it is
    also initial-shaped -- the roman numerals I, V and X.

    The veto is right where a numeral could be a middle initial, and
    wrong where it is describing the suffix in front of it, which is
    the only place this is asked from.
    """
    if len(piece) != 1:
        return False
    tags = tokens[piece[0]].tags
    return "vocab:suffix" in tags and "initial" in tags


def segment_suffix_reading(pieces: Sequence[Sequence[int]],
                           ptags: Sequence[Set[str]],
                           tokens: Sequence[WorkToken],
                           ) -> tuple[bool, ...] | None:
    """How each piece of a no-name segment reads: True a suffix, False
    a title. None when the segment holds a name word and so is not a
    credential run at all.

    ONE answer for three readers -- the no-name gate below, assign's
    router, and group's one-entry join -- because they must agree piece
    for piece. #429 shipped the inverse of its own fix by deriving that
    agreement twice (mechanisms.md#ONE-PREDICATE-PER-QUESTION).

    rules.md#S2's initial veto keeps a roman numeral out of a suffix
    reading, which is right after a NAME word: 'Smith, John V.' is a
    middle initial (#432). After a SUFFIX word the numeral is
    describing that suffix -- 'PSM I' is Professional Scrum Master
    level I -- so the run continues through it, period included, an
    initial there being no shape anyone writes (#430). A title resets
    that: what follows a bare title is not continuing a credential.
    """
    if not pieces:
        return None
    out: list[bool] = []
    after_suffix = False
    for k in range(len(pieces)):
        if is_suffix_piece(pieces[k], ptags[k], tokens):
            after_suffix = True
            out.append(True)
        elif after_suffix and _numeral_behind_the_initial_veto(
                pieces[k], tokens):
            out.append(True)
        elif is_leading_title(pieces[k], ptags[k], tokens):
            after_suffix = False
            out.append(False)
        else:
            return None
    return tuple(out)


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
def peel_walk(start: int, ptags: Sequence[Set[str]],
               skip: Set[int] = frozenset()) -> list[int]:
    """The indices peel_trailing walks: `start` to the segment's end,
    minus the group-flagged credential pieces (the Ph. D. merge),
    which assign reads as suffixes at any position, and minus `skip`
    -- a tail segment's delimiter cores, which are structure rather
    than words (the maiden walk's case, #424). Built here and nowhere
    else, so the walk's input cannot drift between assign and the
    group sites that read it: the numeral fork is a last-piece
    test that reads the piece before as rest[k - 2], which holds only
    over this list."""
    return [j for j in range(start, len(ptags))
            if j not in skip and "suffix" not in ptags[j]]


def trailing_start(start: int, pieces: Sequence[Sequence[int]],
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
    rest = peel_walk(start, ptags, skip)
    peeled = peel_trailing(rest, pieces, ptags, tokens)
    if numeral_only:
        return rest[-1] if peeled.numeral is not None else len(pieces)
    return rest[peeled.names] if peeled.names < len(rest) else len(pieces)


def peel_trailing(rest: Sequence[int], pieces: Sequence[Sequence[int]],
                   ptags: Sequence[Set[str]],
                   tokens: Sequence[WorkToken]) -> Peel:
    """The S2 trailing peel over `rest`, a peel_walk list. In the
    piece layer rather than in assign because group's bound-given
    reserve asks the same question of the view the join would leave
    (#425): one walk, so the reserve and the assignment cannot drift. Pure -- the ambiguities are
    returned for assign to report, in the order it always reported
    them."""
    picks: list[tuple[int, ...]] = []
    numeral: tuple[int, ...] | None = None
    k = len(rest)
    while k > 0:
        piece = pieces[rest[k - 1]]
        if is_suffix_piece(piece, ptags[rest[k - 1]], tokens):
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
