"""Stage: segment.

Consumes: tokens (role-None main stream), comma_offsets, one_case
(where an earlier stage recorded it).
Produces: segments (runs of main-token indices; interior segments may
be EMPTY -- doubled commas keep their structural position), structure
-- NO_COMMA, or FAMILY_COMMA for every comma form: whether the part
after the first comma is the postnominal part is decided at the head
of group once classify has tagged the words (#613, `_comma.decide`),
which may set SUFFIX_COMMA -- one_case where C2's flag asked for it,
and COMMA_STRUCTURE ambiguities for unrecognized extra segments (a
part of title and suffix words is recognized, #603).
Reads: for C2's flag on a part past the second comma only: Lexicon
suffix vocabulary and Policy through _vocab.is_wholly_suffix
(Policy.lenient_comma_suffixes picks the lenient or strict token test;
Policy.extra_suffix_delimiters makes a delimiter-core token
transparent), with the credential lean the lazy case gate supplies
(Lexicon.maiden_markers DIRECTLY, for the own-words span
_pieces.own_words takes); Policy.unlisted_dotted_suffixes through
_vocab.ambiguous_class_candidate and _vocab.ambiguous_class_member,
for a part of by-shape credentials; and Lexicon.titles DIRECTLY, with
_vocab.period_joined_vocab for a period-joined title, for a part of
titles and suffixes (#603).

Implements rule C2 of docs/design/rules.md, and C1's segmentation;
C1's decision is `_comma.decide`'s. History in decisions.md#C1.
"""
from __future__ import annotations

from nameparser._lexicon import _normalize
from nameparser._pipeline._pieces import own_words
from nameparser._pipeline._state import (
    ParseState, PendingAmbiguity, Structure, comma_bucket, copy_with,
)
from nameparser._pipeline._vocab import (
    ambiguous_class_candidate, ambiguous_class_member, period_joined_vocab,
    is_one_case, is_wholly_suffix,
)
from nameparser._types import AmbiguityKind





def segment(state: ParseState) -> ParseState:
    main = [i for i, t in enumerate(state.tokens) if t.role is None]
    if not main:
        return copy_with(state, segments=(),
                         structure=Structure.NO_COMMA)
    if not state.comma_offsets:
        return copy_with(state, segments=(tuple(main),),
                         structure=Structure.NO_COMMA)
    buckets: list[list[int]] = [[] for _ in range(len(state.comma_offsets) + 1)]
    for i in main:
        # _state.comma_bucket, not a local bisect: classify asks the
        # same question of the same offsets to keep a marker run inside
        # one segment, and the two must be one expression rather than
        # two that agree
        buckets[comma_bucket(state.tokens[i].span.start,
                             state.comma_offsets)].append(i)
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
        return copy_with(state, segments=segs,
                         structure=Structure.NO_COMMA)

    # The case fact, asked LAZILY: here only C2's flag on a part past
    # the second comma turns on it. A name that never asks pays nothing;
    # classify asks for itself later where this did not
    # (decisions.md#S2, and #429's precedent for paying a predicate
    # twice rather than plumbing a field two sites would not otherwise
    # share).
    one_case = state.one_case

    def case_class() -> bool:
        nonlocal one_case
        if one_case is None:
            one_case = is_one_case(own_words(
                state.tokens, state.comma_offsets,
                state.lexicon.maiden_markers)[0])
        return one_case

    # The texts are built inline rather than through a helper
    # (measured, #289/#516's eager-gate fix round): on 3.11 a list
    # comprehension IS a frame
    # (PEP 709 inlines it only from 3.12 on; see
    # tools/perf/call_count.py's docstring), so wrapping it in another
    # call doubles the cost of every tail segment asked.
    #
    # `case` is ParseState.one_case: None is the case-FREE reading,
    # which is what every caller on this path wants, and the tail
    # walk below passes `case_class()` for the leaning one. One
    # closure with a default rather than two whose bodies differ only
    # in that argument.
    def suffixy(seg: tuple[int, ...], case: bool | None = None) -> bool:
        return is_wholly_suffix([state.tokens[i].text for i in seg],
                                state.lexicon, state.policy, one_case=case)

    def class_run(seg: tuple[int, ...]) -> bool:
        # Every token of the run joins the ambiguous credential class
        # BY SHAPE -- a candidate that is not a LISTED member, which is
        # the one half `is_wholly_suffix` cannot see (its own docstring
        # says so, and the blindness is what keeps a by-shape token out
        # of C1's whole-name suffix fallback in `_comma.decide`). A tail
        # segment is consumed as suffix either way, so what this decides is only
        # whether the parse says it did not RECOGNIZE the segment -- and
        # a run the parse itself reads as a credential run by shape is
        # recognized. Without it, the narrow roman retirement
        # (rules.md#S3) moved 'R.A.I.', 'X.Y.I.' and 'J.u.n.i.o.r.' out
        # of the vocabulary verdict and into the shape class, and every
        # one of them gained a COMMA_STRUCTURE flag in a third segment
        # that 2.3 did not raise -- a report about the parser's own new
        # reading rather than about the name (review round, #289/#516).
        #
        # The LISTED half is excluded rather than folded in: a listed
        # member reaches this reading through the LEAN (the leaning
        # `suffixy` call below), and that is the whole of what quiets
        # it -- 'STEVEN HARDMAN, MD, DO, DDS' is written in one case,
        # leans nothing, and keeps its flag, the recorded negative
        # control for the lean's own effect here. Admitting membership
        # alone would silence it and leave the control measuring
        # nothing.
        #
        # Policy-sensitive by construction: with
        # `unlisted_dotted_suffixes` off the token is name material, is
        # no candidate, and the flag stands.
        return all(ambiguous_class_candidate(state.tokens[i].text,
                                             state.lexicon, state.policy)
                   and not ambiguous_class_member(state.tokens[i].text,
                                                  state.lexicon)
                   for i in seg)

    def titles_and_suffixes(seg: tuple[int, ...]) -> bool:
        # rules.md#C2: "a word of the title vocabulary there that is not
        # also suffix vocabulary is a title" -- at least one title
        # word, and every other word a suffix word
        # period_joined_vocab for 'Lt.Gov.', one token that classify
        # (not yet run) tags a title by this same call, and that assign
        # then reads as one; a word without a period cannot be one
        titles = state.lexicon.titles
        rest = tuple([i for i in seg
                      if _normalize(t := state.tokens[i].text) not in titles
                      and ("." not in t
                           or period_joined_vocab(t, state.lexicon)
                           != "title")])
        return len(rest) < len(seg) and (not rest or suffixy(rest))

    # rules.md#C1's decision is not this stage's since #613: every comma
    # form leaves here as the FAMILY comma -- the listing form, what a
    # comma means until the part after it has been read -- and group
    # decides at its head, once classify has tagged every word, whether
    # that part is the postnominal part (`_comma.decide`). Deciding here
    # meant predicting the later stages: group's particle chain (#562's
    # pair) and assign's reading of a run the capitals settle, with a
    # second count in assign besides. What stays here is the
    # segmentation and C2's flag on a part past the second comma.
    ambiguities = list(state.ambiguities)
    # rules.md#C2: "a non-empty extra part that is not entirely suffix
    # words is flagged as a structural ambiguity rather than rejected"
    # -- parts[2:] are consumed as suffixes either way, their title
    # words as titles (#603), so a tail segment that is neither all
    # suffix words nor title words beside suffix words gets the
    # COMMA_STRUCTURE flag, not a structure veto. The lean reaches this reading too:
    # a tail of leaning credentials is a credential run, which is the
    # one place this design quiets a report rather than adding one.
    for seg in groups[2:]:
        # empty segments are consumed silently (v1 skips them without
        # comment); only non-empty non-suffix tails get flagged.
        # The case-FREE `suffixy(seg)` first: by construction the
        # leaning call can only ADD a disjunct to it
        # (`is_wholly_suffix`'s credential-lean branch), never remove
        # one -- so a seg that already reads wholly suffix case-free
        # reads so case-aware too, and the case fact is worth forcing
        # only when the case-free answer was False (measured
        # regression: the leaning call forced the fact for every tail
        # segment, suffix or not).
        # `class_run` last, for the same lazy reason and one step
        # further out: it is the only one of the three that walks the
        # by-shape class, and it is asked only of a run BOTH suffix
        # readings have already declined.
        # #603: a part assign reads as titles and suffixes is
        # recognized too -- word by word, off the title vocabulary
        # (classify has not run yet), so a part holding a connective ('Secretary of State') keeps the
        # flag: knowing that group's title chain takes it would be a
        # model of group, the shape mechanisms.md's
        # READ-WITHOUT-THEN-BIND exists to remove. Last, as the
        # rarest reading.
        if (seg and not suffixy(seg) and not suffixy(seg, case_class())
                and not class_run(seg) and not titles_and_suffixes(seg)):
            texts_joined = " ".join([state.tokens[i].text for i in seg])
            ambiguities.append(PendingAmbiguity(
                AmbiguityKind.COMMA_STRUCTURE,
                f"segment {texts_joined!r} beyond the recognized comma "
                f"structures; consumed as suffix best-effort",
                tuple(seg)))
    return copy_with(state, segments=tuple(groups),
                     structure=Structure.FAMILY_COMMA,
                     ambiguities=tuple(ambiguities),
                     one_case=one_case)
