"""Stage: segment.

Consumes: tokens (role-None main stream), comma_offsets, one_case
(where an earlier stage recorded it).
Produces: segments (runs of main-token indices; interior segments may
be EMPTY -- doubled commas keep their structural position), structure,
one_case where the comma form asked for it, COMMA_STRUCTURE
ambiguities for unrecognized extra segments, and SUFFIX_OR_NAME where
the comma FLIPPED the structure for a member of the ambiguous
credential class. The flip and nothing else: where the structure did
not move, the word's reading is still open and `assign` takes it on
the family-comma path, so it reports there.
Reads: Lexicon suffix vocabulary and Policy, both through
_vocab.is_wholly_suffix -- the suffix-comma decision is definitionally
vocabulary-dependent (decisions.md#C1), and the predicate
owns the rest (Policy.lenient_comma_suffixes picks the lenient or
strict token test; Policy.extra_suffix_delimiters gives v1
suffix_delimiter parity, a delimiter-core token being transparent);
Lexicon.maiden_markers DIRECTLY, for the own-words span the lazy case
gate takes (_pieces.own_words); Lexicon title and suffix vocabulary
plus Policy.lenient_comma_suffixes again through _vocab.
name_word_count, which counts NAME words for the class's own comma
rule; and, since 2.4, Policy.unlisted_dotted_suffixes through
_vocab.ambiguous_class_candidate, and Policy.unlisted_caps_suffixes
DIRECTLY as this stage's own gate before the run test calls
_vocab.caps_shape_candidate -- which reads every Lexicon vocabulary
field in turn (_lexicon._VOCAB_FIELDS) to decide that an all-caps
word is UNLISTED. `is_wholly_suffix` deliberately sees neither
by-shape half, dotted or caps (#516). An unlisted dotted or all-caps
token joins the ambiguous credential class by SHAPE at this stage's
own candidate tests the same way a listed member does; the caps half
additionally needs `one_case` to decide membership at all, which this
stage's own lazy gate supplies.

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

    # rules.md#C1: "the name reads as trailing suffixes when the part
    # after the first comma is entirely suffix words and more than one
    # word precedes the comma; otherwise it reads as the listing form"
    # (v1 parity: only parts[1] decides, parser.py:1318; history:
    # decisions.md#C1)
    #
    # And for the AMBIGUOUS class the count is of NAME words, not of
    # words: 'Smith Jr., MA' is two tokens and one name, and the token
    # count hands its family to `given` (#289/#516). One rule for the
    # whole class: the listed and dotted halves are asked only of a
    # single-token part, a member of either being always exactly one
    # token (a bare word, or one glued acronym), while the caps half
    # may come as a RUN ('LEED AP', below).
    #
    # Membership is tested CASE-FREE first (`ambiguous_class_candidate`,
    # the listed set OR -- since 2.4 -- a by-shape member Policy
    # admits, #516): the structure decision below is itself
    # case-independent (item 5's count decides "whatever case the name
    # is written in"), so the case fact is worth forcing only once a
    # genuine candidate is found. Passing `case_class()` as an
    # ARGUMENT instead ran the `own_words` -> `tag_marker_runs` walk
    # for every comma name whose post-comma part is one token --
    # `"Smith, John"`, `"John Smith, Jr."`, neither able to reach the
    # class at all (measured regression).
    candidate = (len(groups[1]) == 1
                 and ambiguous_class_candidate(
                     state.tokens[groups[1][0]].text, state.lexicon,
                     state.policy))
    # The all-caps half (Policy.unlisted_caps_suffixes, #516) is the
    # FIRST shape this class can wear across more than one token --
    # 'LEED AP' is two separate all-caps words, not one glued acronym
    # -- and the one membership test in this class that NEEDS the case
    # fact to answer membership at all: 'XYZ' is only credential-shaped
    # where the name contrasts it. Gated on the switch (default off, so
    # a non-candidate comma name never enters this branch) and tried
    # only where the single-token test above already declined.
    #
    # `caps_shape_candidate` directly, not the un-narrowed
    # `ambiguous_class_candidate`: the run is a property of the CAPS
    # class ALONE (#516 review round, F2), the other two halves being
    # single-token by construction, so `all()` over more than one of
    # THEM asks a question the design never posed. Measured, the
    # un-narrowed call per token moved `'John Smith, Ed Ma'`, `'John
    # Smith, ma do'` and `'John Smith, X.Y.Z. A.B.'` to a credential
    # run neither the spec nor any case row wants.
    #
    # `one_case=False` asks the case-free question -- "if this name
    # turned out mixed, would EVERY token in the run join the CAPS
    # shape" -- the same trick the single-token test above uses,
    # generalized over `all()`. Every other conjunct of
    # `caps_shape_candidate` is case-independent, so for a run already
    # confirmed shape-eligible the fact itself is the only unknown
    # left, and the verdict is `case_class() is False` directly rather
    # than a second walk that could only reach the same answer (a
    # quality-review finding: the walk was provably redundant).
    if (not candidate and state.policy.unlisted_caps_suffixes and groups[1]
            and all(caps_shape_candidate(state.tokens[i].text,
                                         state.lexicon, state.policy,
                                         one_case=False)
                    for i in groups[1])):
        candidate = case_class() is False
    # Computed only where `candidate` is true, alongside `case_class()`
    # -- the same lazy gate: a non-candidate comma name never counts
    # its pre-comma words either. Hoisted to a local because the
    # report below quotes the exact count rather than a hardcoded
    # "two" ('John Q. Public, MA' has three).
    pre_comma_names = None
    if candidate:
        # forced here, downstream of the structure decision that does
        # not need it, because assign's post-comma slot and its report do
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
        # The first report of the comma's OWN structure call in the
        # library, and it is emitted for the branch taken HERE only --
        # the flip. Where the structure did not move, that token's
        # reading is still open and `assign` takes it on the
        # family-comma path, so it reports there; this DECISION is
        # never reported twice, and a second ambiguous token elsewhere
        # is a second fork reporting on its own
        # (mechanisms.md#AMBIGUITY-AT-THE-DECISION-SITE -- emitted
        # where the branch is taken, and this branch is taken here).
        # The neighbouring reports are other forks: C2's structural
        # flag below says what the parse could not RECOGNIZE, and P6's
        # attachment fork ("Berg, Jan vd", post_rules, since 2.3) is
        # the attachment. rules.md#C1's comma-quiet policy gains its
        # exception for this class and no other.
        #
        # `disp`/the index tuple cover the WHOLE post-comma part --
        # the same text as before for the single-token listed and
        # dotted halves (a join of one element is that element), while
        # the caps half's run ('LEED AP') is the first time this class
        # reaches the comma form as more than one token (#516). The
        # single-token case skips the join: measured, a generator
        # expression is its own frame on 3.11 regardless of element
        # count (unlike a list comprehension, which PEP 709 inlines
        # only from 3.12), so the join alone cost every REPORTING
        # comma name (`John Smith, MA`, `John Smith, A.B.`, `Davis
        # Royce, Ed`) +2 frames at the DEFAULT policy, a path this
        # switch must not touch at all (#516 review round, F4).
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
        if (seg and not suffixy(seg) and not suffixy(seg, case_class())
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
