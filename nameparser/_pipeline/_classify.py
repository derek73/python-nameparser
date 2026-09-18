"""Stage: classify.

Consumes: tokens, comma_offsets (with token roles, the two halves of
the structural-boundary test the marker pass applies -- see
_vocab.tag_marker_runs), and one_case where an earlier stage recorded
it -- segment writes it lazily where a comma form can turn it on
(#289/#516), so this read is the fallback for every other name.
Produces: tokens with vocabulary tags added (text/span/role unchanged),
plus ambiguities (SUFFIX_OR_NICKNAME, CONJUNCTION_OR_INITIAL) and
one_case -- whether the name's own words are written in one case,
recorded for the later stages that read it (#289/#516) and left alone
where an earlier stage already asked.
Reads: every Lexicon vocabulary field except surnames and
honorific_tails, which script_segment consumes upstream; and, since
2.4, Policy.unlisted_dotted_suffixes and Policy.unlisted_caps_suffixes,
which decide whether an UNLISTED dotted or all-caps token joins the
ambiguous credential class by SHAPE (#516). is_initial also consults
the _policy module's _NO_INITIALS constant, which is not
configuration -- nothing here varies by its value.

Tags emitted -- stable (API): "particle", "conjunction", "initial";
namespaced (unstable): "vocab:title", "vocab:given-title",
"vocab:suffix", "vocab:suffix-word", "vocab:suffix-ambiguous",
"vocab:particle-ambiguous", "vocab:bound-given", "vocab:maiden-marker",
"vocab:maiden-marker-cont"; and, in a namespace of its own,
"shape:acronym".
"vocab:maiden-marker" tags the HEAD of a maiden marker, which is a
whole marker whenever the marker is one word; the continuation tag
carries the rest of a PHRASE marker ("z domu"), so a site asking
"does a marker start here" reads the same tag it always did and a site
asking "where does it end" walks the continuations.
"vocab:suffix" means "counts as a suffix as written": unambiguous
suffix vocabulary, or an ambiguous acronym written with periods --
at the TAG level 'M.A.' gets "vocab:suffix" while 'Ma' gets only
"vocab:suffix-ambiguous"; what assign then does with a trailing
ambiguous tag is the rest of rule S2's statement (the
words-to-spare guard) and its Accepted consequences.
The initial veto is assign's job, not classify's: 'V' carries both
"vocab:suffix" and "initial".
"shape:acronym" is the one tag in the shape: namespace and it records
WHERE a class claim came from rather than what the vocabulary holds:
an unlisted token the writing makes credential-shaped. It rides
beside "vocab:suffix-ambiguous" where a Policy switch admits the
token to that class, and stands alone where the switch is off, which
is what lets the fork be reported without being taken.
"""
from __future__ import annotations

import dataclasses

from nameparser._lexicon import _normalize
from nameparser._pipeline._state import (
    SHAPE_ACRONYM_TAG, ParseState, PendingAmbiguity, WorkToken,
)
from nameparser._types import AmbiguityKind, Role
from nameparser._pipeline._vocab import (
    caps_shape_candidate, is_initial, is_one_case, period_joined_vocab,
    suffix_as_written, tag_marker_runs,
)
from nameparser._pipeline._pieces import own_words




# rules.md#S2: "a trailing word of the suffix vocabulary reads as a
# suffix — generational forms and credential acronyms alike, and an
# ambiguous acronym written with its periods, one after each
# letter, counts unambiguously; a single trailing period is the
# abbreviation shape any word can wear and does not. A
# bare ambiguous acronym is consumed only when the name has words to
# spare"
def _tags_for(token: WorkToken, n: str, state: ParseState,
              marker_tag: str | None, one_case_own: bool,
              one_case: bool) -> frozenset[str]:
    """`n` is _normalize(token.text), folded once by the caller and
    shared with the marker pass; `marker_tag` is what that pass decided
    for this token, or None. The marker DECISION is entirely
    `_vocab.tag_marker_runs`'; only the writing happens here, so the
    two tokens of a phrase are built once rather than replaced twice.

    `one_case_own` is true when the name's OWN words are written in one
    case AND this token is one of the name's own words -- a maiden clause
    and any delimited (nickname) content are not, so the fork never
    reads them either (rules.md#P3): a clause's words are not the
    name's own words, and appending one must not change how THIS token
    reads.

    `one_case` is the bare NAME-level fact alone -- P3's own-words
    span is not this question's business. #516's caps branch reads
    THIS, not `one_case_own`: a maiden clause's own words are outside
    `one_case_own`'s span by construction (`i < clause_at` fails for
    every one of them), so a token past the clause cut reads
    `one_case_own` as False regardless of whether the WHOLE name is
    written in one case -- 'JOHN SMITH NEE' flipped 'NEE' to a
    credential reading with the switch on, one case and all, because
    `not one_case_own` was true for it purely from being past the
    clause cut, never from the name's own writing (#516 review round,
    a second reviewer's finding). `single_letter_connective` below
    keeps `one_case_own`: that fork is genuinely about the OWN-WORDS
    span, and reads a clause's word as no evidence on purpose."""
    lex = state.lexicon
    tags = set(token.tags)
    if marker_tag is not None:
        tags.add(marker_tag)
    if n in lex.titles:
        tags.add("vocab:title")
    if n in lex.given_name_titles:
        tags.add("vocab:given-title")
    if suffix_as_written(n, token.text, lex):
        tags.add("vocab:suffix")
    if n in lex.suffix_words:
        tags.add("vocab:suffix-word")
    if n in lex.suffix_acronyms_ambiguous:
        tags.add("vocab:suffix-ambiguous")
    if n in lex.particles:
        tags.add("particle")
    if n in lex.particles_ambiguous:
        tags.add("vocab:particle-ambiguous")
    # rules.md#P3: "a single-letter connective reads as an initial
    # where the writing says so: written as a bare Latin capital in a
    # name that is not written wholly in one case, or — in a name
    # written wholly in one case, where nothing says so — where the
    # letter is one the vocabulary marks as reading both ways"
    # (#383/#479; history: decisions.md#P3)
    single_letter_connective = (len(token.text) == 1
                                and token.text.upper() != token.text.lower()
                                and n in lex.conjunctions)
    if single_letter_connective and one_case_own:
        # No case evidence, so the vocabulary decides. No namespaced
        # tag beside it: the emitted ambiguity IS the record of the
        # decision (mechanisms.md#MARK-DONT-STRIP is satisfied by the
        # report) -- mechanisms.md#AMBIGUITY-AT-THE-DECISION-SITE says
        # emit where the branch is taken, not where an ambiguous tag
        # sits, and a vocab: tag records MEMBERSHIP, not the branch
        # taken, so it is the wrong shape of record here.
        if n in lex.conjunctions_ambiguous:
            tags.add("initial")
        else:
            # a bare capital y joins here, where mixed case vetoes it
            tags.add("conjunction")
    else:
        # the mixed-case rule, unchanged. v1's is_conjunction excludes
        # initials: 'e.' in 'john e. smith' is a middle initial, not
        # the Spanish conjunction 'e'
        initial = is_initial(token.text)
        if n in lex.conjunctions and not initial:
            tags.add("conjunction")
        if initial:
            tags.add("initial")
    if n in lex.bound_given_names:
        tags.add("vocab:bound-given")
    # maiden markers are NOT tagged here: an entry may be a phrase whose
    # words are not markers on their own, and this function sees one
    # token with no neighbours. `_vocab.tag_marker_runs` does the whole
    # field, single words included, so there is one place that decides
    # it (mechanisms.md#ONE-PREDICATE-PER-QUESTION).
    # v1's period-joined derivation (parse_pieces): a token with a
    # period not at the end, ANY of whose period chunks is a title, is
    # a title as a whole ('Lt.Gov.', and by the ANY rule 'Mr.Smith');
    # else ANY suffix chunk makes it a suffix ('JD.CPA'). Title wins
    # (v1's continue). Skipped when the whole token already matched.
    if "vocab:title" not in tags and "vocab:suffix" not in tags:
        derived = period_joined_vocab(token.text, lex)
        if derived == "title":
            tags.add("vocab:title")
        elif derived == "suffix":
            tags.add("vocab:suffix")
        elif derived == "shape" and token.role is None:
            # #516: the word is not in the vocabulary, so the claim is
            # about the WRITING and says so -- SHAPE_ACRONYM_TAG beside
            # the membership tag rather than instead of it, because
            # `vocab:` records membership (see this module's tag
            # roster above) and the peel reads membership. The shape
            # tag goes on either way: with the switch off the parser
            # has still chosen the name reading over a credential one,
            # and that fork is reported. A token that already carries
            # a role is delimited content, decided by extract's escape
            # and never at the trailing slot -- 'Bridge (A.B)' is the
            # control that proves this guard load-bearing (without
            # it, the nickname reading of 'A.B' would gain a spurious
            # SUFFIX_OR_NICKNAME report below); 'Bridge (1.4)' cannot
            # exercise it on its own, since a digit chunk never
            # reaches the shape verdict at all (period_joined_vocab's
            # own alphabetic gate). This branch and
            # `_vocab.ambiguous_class_candidate` ask the SAME question
            # twice, of necessity -- `segment` runs before `classify`
            # and has no tags to read yet -- kept from drifting by
            # `test_classify.test_ambiguous_class_candidate_agrees_with_the_tag`
            # rather than by this sentence alone.
            tags.add(SHAPE_ACRONYM_TAG)
            if state.policy.unlisted_dotted_suffixes:
                tags.add("vocab:suffix-ambiguous")
        elif (state.policy.unlisted_caps_suffixes and token.role is None
                and caps_shape_candidate(token.text, lex, state.policy,
                                         one_case)):
            # #516's all-caps half, OPT-IN: an unlisted word written
            # in capitals inside a mixed-case name. The policy
            # conjunct comes FIRST and stays a plain attribute read --
            # False by default, so `caps_shape_candidate` is never
            # CALLED at the default, and sharing its body below costs
            # the default nothing (quality-review finding: the shape
            # test plus its eleven-list exclusion was spelled three
            # times over -- here, in `_vocab.ambiguous_class_candidate`,
            # and in `_segment.py`'s run test -- before this call
            # replaced all three; unlike the dotted branch above,
            # which stays inline because ITS caller has no such
            # cheap first conjunct to hide behind). `role is None`
            # stays here rather than moving into the shared predicate:
            # delimited content is decided by extract's escape, never
            # at the trailing slot, and this guard is what keeps a
            # bracketed nickname like 'Bridge (A.B)' out of the shape
            # class (see the sibling guard on the dotted branch,
            # above, for the fuller reasoning -- the same one applies
            # here). `caps_shape_candidate`'s own docstring carries
            # the eleven-list roster and what each measured entry
            # would have cost unfixed; not repeated here.
            tags.add(SHAPE_ACRONYM_TAG)
            tags.add("vocab:suffix-ambiguous")
    return frozenset(tags)


def classify(state: ParseState) -> ParseState:
    # One fold per token, shared by the marker pass and the vocabulary
    # tags -- the shape suffix_as_written already asks for ("n is
    # _normalize(text), passed in so callers normalize once").
    folded = [_normalize(t.text) for t in state.tokens]
    marker_tags = tag_marker_runs(state.tokens, state.comma_offsets,
                                  state.lexicon.maiden_markers, folded)
    # rules.md#P3 says a maiden marker, taken as one, and the words it
    # takes, are not among the name's own words -- so the span and its
    # clause cut are _pieces.own_words', shared with the site that
    # needs the same answer two stages earlier (#289/#516). The marker
    # map goes with it: this stage has already decided which tokens
    # are run HEADS, so the helper reads that decision rather than
    # walking the texts again, and classify's answer is the one it was
    # before the helper existed.
    own, clause_at = own_words(state.tokens, state.comma_offsets,
                               state.lexicon.maiden_markers, marker_tags)
    # ONE fact per parse, and it is recorded now (ParseState.one_case):
    # segment writes it first where a comma form could turn on it, and
    # a fact two stages decide apart is what recording it prevents
    # (decisions.md#S2).
    one_case = state.one_case
    if one_case is None:
        one_case = is_one_case(own)
    # The fork itself must not read a clause's words either, so the
    # `one_case and ...` argument below repeats `own`'s membership test
    # per token, and the fork and its emitter then agree with the case
    # class they consult. No extra frame -- it is one more boolean in a
    # comprehension that already walks every token.
    tokens = tuple(
        dataclasses.replace(
            t, tags=_tags_for(t, folded[i], state, marker_tags.get(i),
                              one_case_own=one_case and i < clause_at
                              and t.role is None, one_case=one_case))
        for i, t in enumerate(state.tokens))
    # Delimited content whose vocabulary cannot settle it: extract's
    # escape sends an UNambiguous suffix straight through ("(MBA)" ->
    # suffix) and keeps everything else as a nickname, so an AMBIGUOUS
    # acronym in there was a coin the parser had to call. Reported here
    # rather than at the escape itself, which runs before tokenize and
    # so has no token index to point at.
    ambiguities = list(state.ambiguities)
    for i, token in enumerate(tokens):
        if (token.role is Role.NICKNAME
                and "vocab:suffix-ambiguous" in token.tags):
            ambiguities.append(PendingAmbiguity(
                AmbiguityKind.SUFFIX_OR_NICKNAME,
                f"delimited {token.text!r} is also a post-nominal; read "
                f"as a nickname rather than a suffix",
                (i,)))
        # #383/#479: narrows the fork's own "initial" tag with the same
        # inputs the fork used, rather than re-deciding from scratch.
        # Only the casedness test is inherited from the tag --
        # `is_initial(token.text)` also tags a bare capital "initial"
        # in the fork's else branch, so the tag alone does not tell
        # this apart from that.
        #
        # Of the two clauses beside it, one is load-bearing and one is
        # not. `conjunctions_ambiguous` is IMPLIED by the others for a
        # fresh parse -- the contrapositive of what it looks like:
        # `is_initial` matches an ASCII capital only, so ONLY the
        # fork's branch can tag a bare LOWERCASE letter "initial"
        # ("jose e maria santos" tags a lowercase e), and it does so
        # only for a conjunctions_ambiguous member. So for a letter of
        # EITHER case, "initial" plus len 1 implies membership. It is
        # kept only because `_tags_for` starts from `set(token.tags)`, so
        # this clause is what keeps the emitter honest if a runner ever
        # hands classify tokens it did not build; no such path exists
        # today. `conjunctions` is the clause doing real work: it keeps
        # an orphan marker (a conjunctions_ambiguous entry no longer in
        # conjunctions) inert rather than reported (decisions.md#P3).
        # `i < clause_at and token.role is None` mirrors the fork's own
        # "own words" test above, for the same reason (rules.md#P3): a
        # clause's words were never eligible for the fork, so they must
        # never be eligible to report either. Emitted at the decision
        # site (mechanisms.md#AMBIGUITY-AT-THE-DECISION-SITE), per
        # token -- 'e and e' reports twice.
        if (one_case and "initial" in token.tags
                and len(token.text) == 1
                and folded[i] in state.lexicon.conjunctions_ambiguous
                and folded[i] in state.lexicon.conjunctions
                and i < clause_at and token.role is None):
            ambiguities.append(PendingAmbiguity(
                AmbiguityKind.CONJUNCTION_OR_INITIAL,
                f"{token.text!r} is both a connective and an initial; "
                f"the name is written in one case, so nothing marks "
                f"which, and it is read as an initial",
                (i,)))
    # The write rides the replace this stage already makes, so
    # recording the fact costs no frame of its own.
    return dataclasses.replace(state, tokens=tokens,
                               ambiguities=tuple(ambiguities),
                               one_case=one_case)
