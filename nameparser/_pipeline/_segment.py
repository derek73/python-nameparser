"""Stage: segment.

Consumes: tokens (role-None main stream), comma_offsets, one_case
(where an earlier stage recorded it).
Produces: segments (runs of main-token indices; interior segments may
be EMPTY -- doubled commas keep their structural position), structure,
one_case where the comma form asked for it, COMMA_STRUCTURE
ambiguities for unrecognized extra segments, and SUFFIX_OR_NAME where
the comma decided a member of the ambiguous credential class.
Reads: Lexicon suffix vocabulary and Policy, both through
_vocab.is_wholly_suffix -- the suffix-comma decision is definitionally
vocabulary-dependent (decisions.md#C1), and the predicate
owns the rest (Policy.lenient_comma_suffixes picks the lenient or
strict token test; Policy.extra_suffix_delimiters gives v1
suffix_delimiter parity, a delimiter-core token being transparent);
and, since 2.4, Policy.unlisted_dotted_suffixes and
Policy.unlisted_caps_suffixes, both read through
_vocab.ambiguous_class_candidate alone -- is_wholly_suffix
deliberately does not see the by-shape class, dotted or caps (#516).
An unlisted dotted or all-caps token joins the ambiguous credential
class by SHAPE at this stage's own candidate test the same way a
listed member does; the caps half additionally needs `one_case` to
decide membership at all, which this stage's own lazy gate supplies.

Implements rules C1 and C2 of docs/design/rules.md, cited at the
decision site below; history in decisions.md#C1.
"""
from __future__ import annotations

import dataclasses

from nameparser._pipeline._pieces import own_words
from nameparser._pipeline._state import (
    ParseState, PendingAmbiguity, Structure, comma_bucket,
)
from nameparser._pipeline._vocab import (
    ambiguous_class_candidate, ambiguous_class_member, caps_shape_candidate,
    is_one_case, is_wholly_suffix, name_word_count,
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
        return dataclasses.replace(state, segments=segs,
                                   structure=Structure.NO_COMMA)

    # The case fact, asked LAZILY: only a comma form can turn on it
    # here, and only where the part after the first comma is a single
    # token -- the shape the ambiguous class comes in. A comma-less
    # name never reaches this and pays nothing; classify asks for
    # itself later where this did not (decisions.md#S2, and #429's
    # precedent for paying a predicate twice rather than plumbing a
    # field two sites would not otherwise share).
    one_case = state.one_case

    def case_class() -> bool:
        nonlocal one_case
        if one_case is None:
            # `own, _` rather than `[0]`: the second element is the
            # maiden clause's start index, which this stage has no use
            # for, and saying so by name is what stops a reader having
            # to go and look up what a bare subscript dropped.
            own, _ = own_words(state.tokens, state.comma_offsets,
                               state.lexicon.maiden_markers)
            one_case = is_one_case(own)
        return one_case

    def texts(seg: tuple[int, ...]) -> list[str]:
        return [state.tokens[i].text for i in seg]

    # Inlined rather than built on `texts` (measured, #289/#516's
    # eager-gate fix round): every comma parse calls `suffixy` at
    # least once, and a `texts(seg)` indirection costs a SECOND frame
    # on top of the comprehension's own -- on 3.11 a list comprehension
    # IS a frame (PEP 709 inlines it only from 3.12 on; see
    # tools/perf/call_count.py's docstring), so wrapping it in another
    # call doubles the cost every comma name pays, member or not.
    # `texts` still serves the two call sites that are not on this
    # path (name_word_count's pre-comma texts, and a flagged tail
    # segment's joined display).
    def suffixy(seg: tuple[int, ...]) -> bool:
        return is_wholly_suffix([state.tokens[i].text for i in seg],
                                state.lexicon, state.policy)

    def leaning_suffixy(seg: tuple[int, ...]) -> bool:
        return is_wholly_suffix([state.tokens[i].text for i in seg],
                                state.lexicon, state.policy,
                                one_case=case_class())

    def class_run(seg: tuple[int, ...]) -> bool:
        # Every token of the run joins the ambiguous credential class
        # BY SHAPE -- a candidate that is not a LISTED member, which is
        # the one half `is_wholly_suffix` cannot see (its own docstring
        # says so, and the blindness is what keeps a by-shape token out
        # of C1's legacy token-count disjunct). A tail segment is
        # consumed as suffix either way, so what this decides is only
        # whether the parse says it did not RECOGNIZE the segment -- and
        # a run the parse itself reads as a credential run by shape is
        # recognized. Without it, the narrow roman retirement
        # (rules.md#S3) moved 'R.A.I.', 'X.Y.I.' and 'J.u.n.i.o.r.' out
        # of the vocabulary verdict and into the shape class, and every
        # one of them gained a COMMA_STRUCTURE flag in a third segment
        # that 2.3 did not raise -- a report about the parser's own new
        # reading rather than about the name (review round, #289/#516).
        #
        # The LISTED half is deliberately excluded rather than folded
        # in: a listed member reaches this reading through the LEAN
        # (`leaning_suffixy`, above), and that is the whole of what
        # quiets it -- 'STEVEN HARDMAN, MD, DO, DDS' is written in one
        # case, leans nothing, and keeps its flag, which is the
        # recorded negative control for the lean's own effect here.
        # Admitting membership alone would silence it and leave the
        # control measuring nothing.
        #
        # Policy-sensitive by construction: with
        # `unlisted_dotted_suffixes` off the token is name material, is
        # no candidate, and the flag stands.
        return all(ambiguous_class_candidate(state.tokens[i].text,
                                             state.lexicon, state.policy)
                   and not ambiguous_class_member(state.tokens[i].text,
                                                  state.lexicon)
                   for i in seg)

    # rules.md#C1: "the name reads as trailing suffixes when the part
    # after the first comma is entirely suffix words and more than one
    # word precedes the comma; otherwise it reads as the listing form"
    # (v1 parity: only parts[1] decides, parser.py:1318; history:
    # decisions.md#C1)
    #
    # And for the AMBIGUOUS class the count is of NAME words, not of
    # words: 'Smith Jr., MA' is two tokens and one name, and the token
    # count hands its family to `given` (#289/#516). The listed and
    # dotted halves are asked only of a single-token part, that being
    # the shape either comes in; the caps half may come as a RUN of
    # more than one token ('LEED AP', below), and the answer reaches
    # all three -- one rule for the class rather than three.
    #
    # Membership is tested CASE-FREE first (`ambiguous_class_candidate`,
    # the listed set OR -- since 2.4 -- a by-shape member Policy
    # admits, #516): the structure decision below is itself
    # case-independent (item 5's count decides "whatever case the name
    # is written in"), so the case fact is worth forcing only once a
    # genuine candidate is found -- not on every comma name whose
    # post-comma part happens to be one token, which is what calling
    # the case-aware predicate with `case_class()` as an ARGUMENT did
    # (measured regression: the `own_words` -> `tag_marker_runs` walk
    # ran for `"Smith, John"` and `"John Smith, Jr."`, neither able to
    # reach the class at all). A genuine candidate still forces the
    # fact here, downstream of the structure decision that does not
    # need it, because assign's post-comma slot and its report do.
    #
    # The single-token test above is unchanged from #516's dotted
    # half: a LISTED or DOTTED class member is always exactly one
    # token (a bare word, or one glued acronym), so "the class comes
    # in one token" was never an artificial restriction for either of
    # those two halves.
    candidate = (len(groups[1]) == 1
                 and ambiguous_class_candidate(
                     state.tokens[groups[1][0]].text, state.lexicon,
                     state.policy))
    # The all-caps half (Policy.unlisted_caps_suffixes, #516) is the
    # FIRST shape this class can wear across more than one token --
    # 'LEED AP' is two separate all-caps words, not one glued acronym
    # -- and it is also the one membership test in this class that
    # NEEDS the case fact to even answer membership: 'XYZ' is only
    # credential-shaped where the name contrasts it. Gated on the
    # switch (default off, so a non-candidate comma name never even
    # enters this branch) and tried only where the single-token test
    # above already declined.
    #
    # The run is a property of the CAPS class ALONE (#516 review
    # round, F2 -- decided by the reviewer): `run_candidate` calls
    # `_vocab.caps_shape_candidate` directly, the branch of the class
    # that reads `one_case` at all, rather than the un-narrowed
    # `ambiguous_class_candidate` every token of the run was first
    # measured against (which also admits the listed and dotted
    # halves, already single-token classes by construction -- the
    # comment above -- so `all()` over more than one of THEM asks a
    # question the design never posed). A first draft called the
    # un-narrowed function per token; measured, it moved `'John
    # Smith, Ed Ma'` / `'John Smith, ma do'` / `'John Smith, X.Y.Z.
    # A.B.'` to a credential run neither the spec nor any case row
    # wants. `run_candidate(False)` asks, case-free, "if this name
    # turned out mixed, would EVERY token in the run join the CAPS
    # shape specifically" -- the same trick the single-token test
    # above uses, generalized over `all()`. Once that answers yes,
    # the real fact is `caps_shape_candidate`'s ONLY remaining
    # unknown for a run already confirmed shape-eligible case-free --
    # every other conjunct is independent of case -- so the real
    # verdict is `case_class() is False` directly, not a third `all()`
    # walk that could only ever reach the same answer (a quality-
    # review finding: the walk was provably redundant, not merely
    # cheap to skip).
    if not candidate and state.policy.unlisted_caps_suffixes and groups[1]:
        def run_candidate(one_case_try: bool | None) -> bool:
            return all(
                caps_shape_candidate(state.tokens[i].text, state.lexicon,
                                     state.policy, one_case_try)
                for i in groups[1])
        if run_candidate(False):
            candidate = case_class() is False
    # Computed only where `candidate` is true, alongside `case_class()`
    # -- the same lazy gate: a non-candidate comma name never counts
    # its pre-comma words either. Hoisted to a local because the
    # report below quotes the exact count rather than a hardcoded
    # "two" ('John Q. Public, MA' has three).
    pre_comma_names = None
    if candidate:
        case_class()
        pre_comma_names = name_word_count(texts(groups[0]), state.lexicon,
                                          state.policy)
    structure = (
        Structure.SUFFIX_COMMA
        if ((suffixy(groups[1]) and len(groups[0]) > 1)
            or (pre_comma_names is not None and pre_comma_names >= 2))
        else Structure.FAMILY_COMMA)
    ambiguities = list(state.ambiguities)
    if candidate and structure is Structure.SUFFIX_COMMA:
        # The first comma-path report of a READING in the library --
        # C2's structural flag, below, already reports on the comma
        # path, but it reports what the parse could not recognize, not
        # a fork it called. This is the existing kind: the parse
        # called a fork at this comma and the caller is told which way
        # it went. Emitted for the branch taken HERE only -- the flip.
        # Where the structure did not move, the reading of that token
        # is still open and `assign` takes it on the family-comma
        # path, so it reports there, and this DECISION is never
        # reported twice -- a second ambiguous token elsewhere is a
        # second fork and reports on its own
        # (mechanisms.md#AMBIGUITY-AT-THE-DECISION-SITE -- emitted
        # where the branch is taken, and this branch is taken here).
        # rules.md#C1's comma-quiet policy gains its exception for
        # this class and no other. `disp`/the index tuple cover the
        # WHOLE post-comma part, not just its first token -- for the
        # single-token member the listed and dotted halves come in,
        # that is the same text as before (join of one element is
        # that element); the caps half's run ('LEED AP') is the first
        # time this class reaches the comma form as more than one
        # token (#516). The single-token case takes the token's text
        # DIRECTLY rather than through the join -- measured, a
        # generator expression is its own frame on 3.11 regardless of
        # element count (unlike a list comprehension, which PEP 709
        # inlines only from 3.12), so the join alone cost every
        # REPORTING comma name (`John Smith, MA`, `John Smith, A.B.`,
        # `Davis Royce, Ed`) +2 frames at the DEFAULT policy, a path
        # this switch must not touch at all (#516 review round, F4).
        disp = (state.tokens[groups[1][0]].text if len(groups[1]) == 1
                else " ".join(state.tokens[i].text for i in groups[1]))
        ambiguities.append(PendingAmbiguity(
            AmbiguityKind.SUFFIX_OR_NAME,
            f"{disp!r} after the comma is also an "
            f"ordinary name word; the part before the comma holds "
            f"{pre_comma_names} name words, so it is read as a "
            f"credential run",
            groups[1]))
    # rules.md#C2: "a non-empty extra part that is not entirely suffix
    # words is flagged as a structural ambiguity rather than rejected"
    # -- parts[2:] are consumed as suffixes unconditionally either
    # way, so a non-suffix tail segment gets the COMMA_STRUCTURE
    # flag, not a structure veto. The lean reaches this reading too:
    # a tail of leaning credentials is a credential run, which is the
    # one place this design quiets a report rather than adding one.
    for seg in groups[2:]:
        # empty segments are consumed silently (v1 skips them without
        # comment); only non-empty non-suffix tails get flagged.
        # `suffixy(seg)` first: it is case-free and, by construction,
        # `leaning_suffixy` can only ADD a disjunct to it
        # (`is_wholly_suffix`'s credential-lean branch), never remove
        # one -- so a seg that already reads wholly suffix case-free
        # reads so case-aware too, and the case fact is worth forcing
        # only when the case-free answer was False (measured
        # regression: `leaning_suffixy` forced the fact for every tail
        # segment, suffix or not).
        # `class_run` last, for the same lazy reason and one step
        # further out: it is the only one of the three that walks the
        # by-shape class, and it is asked only of a run BOTH suffix
        # readings have already declined.
        if (seg and not suffixy(seg) and not leaning_suffixy(seg)
                and not class_run(seg)):
            texts_joined = " ".join(texts(seg))
            ambiguities.append(PendingAmbiguity(
                AmbiguityKind.COMMA_STRUCTURE,
                f"segment {texts_joined!r} beyond the recognized comma "
                f"structures; consumed as suffix best-effort",
                tuple(seg)))
    return dataclasses.replace(state, segments=tuple(groups),
                               structure=structure,
                               ambiguities=tuple(ambiguities),
                               one_case=one_case)
