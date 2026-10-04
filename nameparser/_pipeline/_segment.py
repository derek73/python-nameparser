"""Stage: segment.

Consumes: tokens (role-None main stream), comma_offsets, one_case
(where an earlier stage recorded it).
Produces: segments (runs of main-token indices; interior segments may
be EMPTY -- doubled commas keep their structural position), structure,
one_case where the comma form asked for it, COMMA_STRUCTURE
ambiguities for unrecognized extra segments (a part of title and
suffix words is recognized, #603), and SUFFIX_OR_NAME where
the comma FLIPPED the structure for a member of the ambiguous
credential class, or for a run of suffix words holding one (#544).
The flip and nothing else: where the structure did
not move, the word's reading is still open and `assign` takes it on
the family-comma path, so it reports there.
Reads: Lexicon suffix vocabulary and Policy, both through
_vocab.is_wholly_suffix -- the suffix-comma decision is definitionally
vocabulary-dependent (decisions.md#C1), and the predicate
owns the rest (Policy.lenient_comma_suffixes picks the lenient or
strict token test; Policy.extra_suffix_delimiters gives v1
suffix_delimiter parity, a delimiter-core token being transparent);
Lexicon.maiden_markers DIRECTLY, for the own-words span the lazy case
gate takes (_pieces.own_words); Lexicon.titles DIRECTLY too, for
C2's test that a tail part is titles and suffixes (#603), with
_vocab.period_joined_vocab for a period-joined title; Lexicon
title and suffix vocabulary
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
stage's own lazy gate supplies. The #544 run test reads
_vocab.run_word_fold, _vocab.ambiguous_class_candidate (its "ask"
fallback), _vocab.ambiguous_class_member (the settled-lean check for
a member admitted through that "ask" fallback),
_vocab.is_single_letter_numeral, _vocab.ambiguous_lean and
_vocab.is_wholly_suffix (once, over the leftovers). `run_word_fold`
ANSWERS membership for a simple token outright (its own docstring
proves it agrees with `ambiguous_class_candidate` there); it is a
shortcut around a real predicate, not a condition gating a second
call to one.

Implements rules C1 and C2 of docs/design/rules.md, cited at the
decision site below; history in decisions.md#C1.
"""
from __future__ import annotations

from nameparser._lexicon import _normalize
from nameparser._pipeline._pieces import own_words
from nameparser._policy import CapsSuffixes
from nameparser._pipeline._state import (
    ParseState, PendingAmbiguity, Structure, comma_bucket, copy_with,
)
from nameparser._pipeline._vocab import (
    ambiguous_class_candidate, ambiguous_class_member, ambiguous_lean,
    period_joined_vocab,
    caps_shape_candidate, is_one_case, is_paired_initials,
    claimed_as_non_name, is_single_letter_numeral, is_wholly_suffix,
    written_as_a_name,
    name_word_count,
    surname_unit_count,
    run_word_fold,
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

    # The case fact, asked LAZILY: only a comma form can turn on it
    # here, and only where the part after the first comma is a single
    # token -- the shape the ambiguous class comes in. A comma-less
    # name never reaches this and pays nothing; classify asks for
    # itself later where this did not (decisions.md#S2, and #429's
    # precedent for paying a predicate twice rather than plumbing a
    # field two sites would not otherwise share).
    one_case = state.one_case

    # The own-words walk, once per parse: `case_class` reads the words
    # and `name_contrast` (#564) the clause boundary.
    # Inline in both rather than a third helper: a wrapper is a frame
    # every case-forcing comma name ('John Smith, MA') would pay.
    own_span: tuple[list[str], int] | None = None

    def case_class() -> bool:
        nonlocal one_case, own_span
        if one_case is None:
            if own_span is None:
                own_span = own_words(state.tokens, state.comma_offsets,
                                     state.lexicon.maiden_markers)
            one_case = is_one_case(own_span[0])
        return one_case

    def texts(seg: tuple[int, ...]) -> list[str]:
        return [state.tokens[i].text for i in seg]

    # #564 (Derek): the contrast the caps shape needs is the NAME's,
    # and the name carries it only if one of its own words before the
    # comma (no maiden clause, no delimited content, as `own_words`
    # defines them for `case_class` above) is written the way a name is
    # written in mixed case -- a capital in it and its last letter
    # lowercase (`written_as_a_name`) -- and is not claimed as a
    # title, particle, connective, credential or generation
    # (`claimed_as_non_name`); a word with a period is an abbreviation
    # or an initial, not one. A lone capital ('de GAULLE C'), a
    # lowercase-only word and a surname written in capitals with
    # anything glued in front ("d'ESTAING", 'FitzGERALD', 'McDONALD')
    # all fail it, so such a record keeps its given name beside its
    # lowercase particles, clauses and titles ('LLOYD ap RHYS', 'HAFEZ
    # al-ASSAD', 'LLOYD WEBBER née Smith') and beside a mixed-case
    # credential ('LLOYD WEBBER, ANDREW PhD').
    # Asked only once a caps word is in hand: a part with no lowercase
    # at all is settled in one C-level comparison; past that it is
    # linear in the words before the comma, about four frames a word
    # (the generator, the case test's call, and the own-words walk's
    # fold and marker test), plus a fold and a wordlist test where the
    # case test passes -- and constant in a word's letters.
    def name_contrast() -> bool:
        before = "".join([state.tokens[i].text for i in groups[0]])
        if before == before.upper():
            return False
        nonlocal own_span
        if own_span is None:
            own_span = own_words(state.tokens, state.comma_offsets,
                                 state.lexicon.maiden_markers)
        clause_at = own_span[1]
        lex = state.lexicon
        return any(
            i < clause_at and (tok := state.tokens[i]).role is None
            and "." not in tok.text and written_as_a_name(tok.text)
            and not claimed_as_non_name(_normalize(tok.text), lex)
            for i in groups[0])

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

    def titles_and_suffixes(seg: tuple[int, ...]) -> bool:
        # rules.md#C2: "a word of the title vocabulary there that is not
        # also suffix vocabulary is a title" -- at least one title
        # word, and every other word a suffix word
        # period_joined_vocab for 'Lt.Gov.', whose chunks group tags a
        # title and assign then reads as one
        titles = state.lexicon.titles
        rest = tuple(i for i in seg
                     if _normalize(t := state.tokens[i].text) not in titles
                     and period_joined_vocab(t, state.lexicon) != "title")
        return len(rest) < len(seg) and (not rest or suffixy(rest))

    # rules.md#C1: "the name reads as trailing suffixes when the part
    # after the first comma is entirely suffix words and more than one
    # word precedes the comma; otherwise it reads as the listing form"
    # (v1 parity: only parts[1] decides, parser.py:1318; history:
    # decisions.md#C1)
    #
    # And for the AMBIGUOUS class the count is of NAME words, not of
    # words: 'Smith Jr., MA' is two tokens and one name, and the token
    # count hands its family to `given` (#289/#516). One rule for the
    # whole class: the listed and dotted halves are asked of a
    # single-token part here, a member of either being always exactly
    # one token (a bare word, or one glued acronym), and of a RUN of
    # such tokens among suffix words by the #544 run test below, while
    # the caps half comes as a run of its own ('LEED AP', below).
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
    # Whether the flip reports: rules.md#C1, "A flip in which no listed
    # word of this class takes part is the exception and is made in
    # silence" -- set below by a listed word taking part, by the caps
    # run, or (run test) by paired initials spoken for only by each
    # other (#563).
    flip_reports = False
    if candidate:
        lone = state.tokens[groups[1][0]].text
        # For a word that passed the candidate test, LISTED is exactly
        # "no period": `ambiguous_class_member` declines any period,
        # and the dotted shape needs one. Asked inline -- a second
        # membership call cost every reporting comma name ('John
        # Smith, MA') two frames to learn what this already says.
        flip_reports = "." not in lone
        # rules.md#C1: "Paired initials are the exception to the
        # count" -- 'García Márquez, G.J.' has two words before the
        # comma and one surname. Alone in the part, nothing speaks
        # for them, so the structure stays the family comma and
        # assign reads and reports them as the given name (#563).
        if not flip_reports and is_paired_initials(lone):
            candidate = False
    # The all-caps half (Policy.unlisted_caps_suffixes, #516) is the
    # FIRST shape this class can wear across more than one token --
    # 'LEED AP' is two separate all-caps words, not one glued acronym
    # -- and the one membership test in this class that NEEDS the case
    # fact to answer membership at all: 'XYZ' is only credential-shaped
    # where the name contrasts it. Gated on the setting (on by default
    # since #564, behind the cheap conjuncts below) and tried only
    # where the single-token test above already declined.
    #
    # `caps_shape_candidate` directly, not the un-narrowed
    # `ambiguous_class_candidate`: the run is a property of the CAPS
    # class ALONE (#516 review round, F2), the other two halves being
    # single-token by construction, so `all()` over more than one of
    # THEM asks a question the design never posed: un-narrowed, a
    # listed or dotted run ('John Smith, Ed Ma') would pass as a CAPS
    # run through this switch, and such runs are the question of the
    # listed-and-dotted run test below, asked with the switch off too.
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
    #
    # #564: on by default (`CapsSuffixes.AFTER_COMMA`), so three cheap
    # C-level conjuncts go before the call: two or more words before
    # the comma, a necessary condition for the two NAME words the flip
    # needs (as at the run test below -- 'Smith, JOHN', the commonest
    # record format, never reaches the call); the first word written
    # in capitals at all, which every word of the run must be; and a
    # LONE two-letter word declined -- it is how a
    # person's initials are written, and two words before the comma
    # may be one surname ('García Márquez, MJ'), the case #563 decides
    # for the dotted 'M.J.' (rules.md#C1). A run holding a longer word
    # ('LEED AP') is not that shape.
    first = state.tokens[groups[1][0]].text if groups[1] else ""
    if (not candidate
            and state.policy.unlisted_caps_suffixes is not CapsSuffixes.OFF
            and len(groups[0]) >= 2
            and first.isalpha() and first.isupper()
            and first.lower() not in state.lexicon.suffix_acronyms
            and first.lower() not in state.lexicon.suffix_words
            and not (len(groups[1]) == 1 and len(first) < 3)
            and all((t := state.tokens[i].text).isalpha() and t.isupper()
                    and t.lower() not in state.lexicon.suffix_acronyms
                    and t.lower() not in state.lexicon.suffix_words
                    and caps_shape_candidate(t, state.lexicon, state.policy,
                                             one_case=False)
                    for i in groups[1])):
        candidate = name_contrast()
        flip_reports = candidate
    # rules.md#C1: "The same count reads a part of two or more words as
    # the credential run when every word of it is a suffix word or a
    # word of this class, at least one of them of this class" -- the
    # single-token rule above generalized to RUNS (#544): 'John Smith,
    # PhD MEng' is the credential run the single-token 'John Smith,
    # MEng' already is. A single-letter roman numeral, in any case,
    # voids the run for its SHAPE -- one letter is how a middle initial
    # is written, and S3 retired single-character vocabulary matches
    # for the same reason (`is_single_letter_numeral`) -- not for
    # being a generation: 'John Smith, III Ma' and 'John Smith, Jr Ma'
    # are runs. A title/suffix DUAL opening the part counts as the
    # suffix vocabulary it is: with a full name before the comma the
    # name is complete, and the legacy disjunct below already counts a
    # dual that way ('John Smith, MS MA'). The given part's leading
    # title run is where a dual reads as a title ('Smith, Ms Ma',
    # 'Smith, MD PhD Ma'), and that exclusion is
    # `_pieces.segment_suffix_reading`'s, one name word before the
    # comma never reaching the flip.
    #
    # Asked only where the flip is possible at all: two or more words
    # before the comma is a necessary condition for two NAME words
    # there, so 'Smith, J. Q.' and 'Smith, PhD MEng' never enter the
    # loop. Inside it, class membership is asked first and the suffix
    # predicate only of what is left, once, as a run. `run_word_fold`
    # answers a SIMPLE token -- ASCII, no interior period -- from the
    # vocabulary sets directly, at less cost than either real
    # predicate below; a member or a definite reject is settled
    # without calling them at all, and only a non-simple token, or one
    # `run_word_fold` defers, still takes the real predicate --
    # `ambiguous_class_candidate` for membership, `is_wholly_suffix`
    # once over the leftovers. A part holding a name word ('Doe Smith,
    # Jane Q. Public') breaks on that word's "reject" without entering
    # a Python frame for either predicate.
    if not candidate and len(groups[1]) >= 2 and len(groups[0]) >= 2:
        members: list[str] = []
        rest: list[str] = []
        settled = True
        # #563, rules.md#C1: "Only an unambiguous suffix word in front
        # of them that is not also title vocabulary, or another word
        # the class admits by its dotted shape standing in the same
        # part, makes them the credential run." `unspoken_pair`: the
        # FIRST pair has only class members ('Ed G.J.') or titles ('Ms
        # G.J.') in front of it. Only the first can change the answer
        # -- every later pair has the same words in front and more --
        # so the title scan runs once, not once per pair, which made
        # 'MD MD ... G.J. G.J. ...' quadratic.
        unspoken_pair = False
        any_listed = False
        caps_member = False
        caps_on = state.policy.unlisted_caps_suffixes is not CapsSuffixes.OFF
        shaped = 0
        pairs = 0
        lexicon = state.lexicon
        prev_particle = False
        for i in groups[1]:
            text = state.tokens[i].text
            fold = run_word_fold(text, lexicon, state.policy)
            is_member = (fold == "member"
                         or (fold == "ask" and ambiguous_class_candidate(
                             text, lexicon, state.policy)))
            # #564: an unlisted all-caps word is a member BY SHAPE too,
            # so a run mixing it with listed credentials ('PhD XYZ',
            # 'XYZ Jr.') reads as the all-caps run alone already does,
            # rather than more evidence for a credential producing a
            # name reading. `isupper()` first, in C; the predicate
            # declines every listed word, so it never re-admits one.
            # The C-level prechecks decline only what the predicate
            # would decline too (it needs `isalpha()`/`isupper()` and
            # excludes every wordlist, and a word whose `lower()` is a
            # listed entry is one of those), so a listed credential
            # ('MD', 'CPA') never pays for the call.
            caps = (not is_member and caps_on and text.isalpha()
                    and text.isupper()
                    and text.lower() not in lexicon.suffix_acronyms
                    and text.lower() not in lexicon.suffix_words
                    and caps_shape_candidate(text, lexicon, state.policy,
                                             one_case=False))
            if caps:
                is_member = caps_member = True
            if is_member:
                # LISTED is exactly "no period" for a listed or dotted
                # member, as at the single-token test above; a caps
                # member is by shape
                listed = "." not in text and not caps
                if listed:
                    any_listed = True
                else:
                    shaped += 1
                    # two capitals are paired initials undotted, read
                    # as #563 reads 'M.J.': 'García Márquez, MJ PhD'
                    # keeps given 'MJ' as 'De La Cruz, M.J. PhD' does
                    if is_paired_initials(text) or (caps and len(text) == 2):
                        pairs += 1
                        if pairs == 1 and all(
                                _normalize(w) in lexicon.titles
                                for w in rest):
                            unspoken_pair = True
                members.append(text)
                # the lean is the LISTED set's alone (S2): a member
                # admitted by shape ('X.Y.Z.') is read by the count
                settled = settled and listed and text.isupper()
            # "reject" first: a name word ends the run without the
            # numeral test's frame, and the numeral cannot be a
            # "reject" (it is suffix vocabulary, so it folds "defer")
            elif fold == "reject" or is_single_letter_numeral(text):
                break
            else:
                rest.append(text)
            # #562, rules.md#C1: "and so is a part holding two
            # particles side by side, which P2 joins into one particle
            # run that S2 leaves to no word's capitals" -- group chains
            # the pair, and the family-comma path can no longer promise
            # to read the part whole: it read 'PhD DO DO', 'PhD vd DO'
            # and 'MA vd vd' as name text. Where it did read the part
            # whole ('VD DO', 'MD DO DO'), the count flips it to the
            # same fields and reports the call, as any flip does.
            # Asked only while the run is still settled -- nothing
            # re-settles it -- with classify's own particle test, since
            # group's chain is what the capitals lose to.
            if settled:
                particle = _normalize(text) in lexicon.particles
                settled = not (particle and prev_particle)
                prev_particle = particle
        else:
            # Every word is a member or left to the suffix predicate.
            # A run whose every member the WRITING already settles as a
            # credential (capitals in a mixed-case name, S2's lean) is
            # not this rule's decision: the listing form reads such a
            # part wholly as the credential run and reports it as it
            # always did ('John Smith, PhD MA'), so it is left there --
            # no flip, no new report. `settled` (every member listed
            # and in capitals) is a necessary condition for that lean,
            # asked inline so a run with a Title-case member never
            # forces the case fact here; `ambiguous_lean` is what
            # answers.
            # "unless what said so is nothing but other paired
            # initials": every shape word a pair, the first unspoken.
            # Alone, the pair keeps the family comma; with others, the
            # run flips and reports.
            pair_only = unspoken_pair and pairs == shaped
            candidate = (bool(members)
                         and not (pair_only and shaped == 1)
                         and (not rest or is_wholly_suffix(
                             rest, lexicon, state.policy))
                         and not (settled and case_class() is False
                                  and all(ambiguous_lean(t, False)
                                          == "credential"
                                          for t in members))
                         # the caps shape needs the contrast, and it has
                         # to come from the NAME: beside a mixed-case
                         # credential the credential's own lowercase
                         # would supply it, and an all-caps record
                         # ('LLOYD WEBBER, ANDREW PhD') would lose its
                         # given name to it
                         and not (caps_member and not name_contrast()))
            # a caps member reports its flip as the all-caps run does
            flip_reports = candidate and (any_listed or pair_only
                                          or caps_member)
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
    # rules.md#C1's "more than one word precedes the comma" counts a
    # particle and the word it attaches to as one word (#575): v1's
    # token count split 'van der Berg, PhD' into given 'van', family
    # 'der Berg'. The token count stays first, so a one-token part
    # never builds the units.
    structure = (
        Structure.SUFFIX_COMMA
        if ((suffixy(groups[1]) and len(groups[0]) > 1
             and surname_unit_count(texts(groups[0]), state.lexicon) > 1)
            or (pre_comma_names is not None and pre_comma_names >= 2))
        else Structure.FAMILY_COMMA)
    ambiguities = list(state.ambiguities)
    if flip_reports and structure is Structure.SUFFIX_COMMA:
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
        # The quoted text and the index tuple cover the WHOLE post-comma part --
        # the same text as before for the single-token listed and
        # dotted halves (a join of one element is that element), while
        # the caps half's run ('LEED AP') is the first time this class
        # reaches the comma form as more than one token (#516). The
        # single-token case skips the join: measured, a generator
        # expression is its own frame on 3.11 regardless of element
        # count (unlike a list comprehension, which PEP 709 inlines
        # only from 3.12), so the join alone cost every REPORTING
        # comma name (`John Smith, MA`, `John Smith, Ed`, `Davis
        # Royce, Ed`) +2 frames at the DEFAULT policy, a path this
        # switch must not touch at all (#516 review round, F4).
        #
        # A RUN (#544) is named as holding such a word rather than
        # being one: in 'John Smith, PhD MEng' only 'MEng' is also a
        # name word.
        if len(groups[1]) == 1:
            what = (f"{state.tokens[groups[1][0]].text!r} after the "
                    f"comma is also an ordinary name word")
        else:
            what = (f"{' '.join(state.tokens[i].text for i in groups[1])!r}"
                    f" after the comma holds a word that is also an "
                    f"ordinary name word")
        ambiguities.append(PendingAmbiguity(
            AmbiguityKind.SUFFIX_OR_NAME,
            f"{what}; the part before the comma holds "
            f"{pre_comma_names} name words, so it is read as a "
            f"credential run",
            groups[1]))
    # rules.md#C2: "a non-empty extra part that is not entirely suffix
    # words is flagged as a structural ambiguity rather than rejected"
    # -- parts[2:] are consumed as suffixes either way, their title
    # words as titles (#603), so a tail segment that is neither gets
    # the COMMA_STRUCTURE flag, not a structure veto. The lean reaches this reading too:
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
            texts_joined = " ".join(texts(seg))
            ambiguities.append(PendingAmbiguity(
                AmbiguityKind.COMMA_STRUCTURE,
                f"segment {texts_joined!r} beyond the recognized comma "
                f"structures; consumed as suffix best-effort",
                tuple(seg)))
    return copy_with(state, segments=tuple(groups),
                     structure=structure,
                     ambiguities=tuple(ambiguities),
                     one_case=one_case)
