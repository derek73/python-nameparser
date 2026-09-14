"""Stage: classify.

Consumes: tokens, comma_offsets (with token roles, the two halves of
the structural-boundary test the marker pass applies -- see
_tag_marker_runs).
Produces: tokens with vocabulary tags added (text/span/role unchanged),
plus ambiguities (SUFFIX_OR_NICKNAME, CONJUNCTION_OR_INITIAL).
Reads: every Lexicon vocabulary field except surnames and
honorific_tails, which script_segment consumes upstream; no Policy
FIELD is consulted (is_initial does consult the _policy module's
_NO_INITIALS constant, which is not configuration -- nothing here
varies by Policy value).

Tags emitted -- stable (API): "particle", "conjunction", "initial";
namespaced (unstable): "vocab:title", "vocab:given-title",
"vocab:suffix", "vocab:suffix-word", "vocab:suffix-ambiguous",
"vocab:particle-ambiguous", "vocab:bound-given", "vocab:maiden-marker",
"vocab:maiden-marker-cont".
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
"""
from __future__ import annotations

import dataclasses
from collections.abc import Sequence

from nameparser._lexicon import _normalize
from nameparser._pipeline._state import (
    ParseState, PendingAmbiguity, WorkToken, comma_bucket,
)
from nameparser._types import AmbiguityKind, Role
from nameparser._pipeline._vocab import (
    _longest_marker, is_initial, is_one_case, maiden_marker_head,
    maiden_marker_run, period_joined_vocab, suffix_as_written,
)




# rules.md#S2: "a trailing word of the suffix vocabulary reads as a
# suffix — generational forms and credential acronyms alike, and an
# ambiguous acronym written with its periods, one after each
# letter, counts unambiguously; a single trailing period is the
# abbreviation shape any word can wear and does not. A
# bare ambiguous acronym is consumed only when the name has words to
# spare"
def _tags_for(token: WorkToken, n: str, state: ParseState,
              marker_tag: str | None, one_case_own: bool) -> frozenset[str]:
    """`n` is _normalize(token.text), folded once by the caller and
    shared with the marker pass; `marker_tag` is what that pass decided
    for this token, or None. The marker DECISION is entirely
    _tag_marker_runs'; only the writing happens here, so the two tokens
    of a phrase are built once rather than replaced twice.

    `one_case_own` is true when the name's OWN words are written in one
    case AND this token is one of the name's own words -- a maiden clause
    and any delimited (nickname) content are not, so the fork never
    reads them either (rules.md#P3): a clause's words are not the
    name's own words, and appending one must not change how THIS token
    reads."""
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
    # token with no neighbours. _tag_marker_runs below does the whole
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
    return frozenset(tags)


def _tag_marker_runs(state: ParseState,
                     folded: Sequence[str]) -> dict[int, str]:
    """Which tokens are maiden marker runs: index -> "vocab:maiden-marker"
    for a run's head, "vocab:maiden-marker-cont" for the rest.

    Returns the decision rather than rewriting the tokens; classify
    writes it into the one pass that builds them, so a marker token is
    not replaced twice. `folded` is _normalize per token, computed once
    for this pass and the vocabulary tags alike.

    The one sequence pass in this stage, and it has to be one: a marker
    entry may be a PHRASE whose words are not markers individually
    ('z', 'domu'), so no per-token membership test can find it.
    Left to right, longest first at each position, then skip past what
    the run claimed -- a second marker cannot start inside the first.

    This is where the tag is DECIDED for the two stages that read it
    afterwards. group runs later and asks its questions of these tags
    rather than re-deriving the run (the recorded-answer half of
    mechanisms.md#ONE-PREDICATE-PER-QUESTION); extract runs EARLIER,
    before tokens exist, so it calls the predicate itself over the
    clause's whitespace words.

    A tagged run is structurally contiguous, and the test is
    one-directional: a role change IS a clause edge, so no run spans
    one, but not every clause edge is a role change -- two ADJACENT
    clauses of the same role are indistinguishable here, and
    'Jane (z) (domu) Jones' does tag a run across them. Both consumers
    refuse that run for reasons of their own (the piece walk never sees
    role-bearing tokens at all; the clause drop is scoped to one
    clause's span), so no reading depends on it today, and the claim
    this pass can honestly make is the weaker one. What it does
    guarantee is what _group._marker_run_pieces needs: a run inside the
    MAIN stream stays inside one segment. Without it this pass walked
    the whole span-sorted stream while group walked one segment --
    _segment keeps only role-less tokens and buckets them by the commas
    before them -- so a run half inside a bracketed clause was tagged
    whole and consumed as a proper PREFIX of itself, and
    'Anna z (domu) Nowak' read family 'Anna', maiden 'Nowak': the bare
    preposition eating the name, which is the exact damage the phrase
    entry exists to prevent. Refusing to tag such a run is the fix;
    truncating it instead would hand M2 the same wrong prefix one word
    shorter.
    """
    markers = state.lexicon.maiden_markers
    # the lookahead the vocabulary actually needs; 0 for an empty set,
    # which skips the pass entirely
    cap = _longest_marker(markers)
    if not cap:
        return {}
    tokens = state.tokens
    n_tokens = len(tokens)
    # Deferred, not computed up front: only the contiguity walk reads
    # it, only a phrase vocabulary runs that walk, and only at a token
    # that opens an entry -- so a single-word vocabulary, and a
    # phrase vocabulary over a name holding no marker, never pay the
    # sweep at all.
    buckets: list[int] | None = None
    tags: dict[int, str] = {}
    i = 0
    while i < n_tokens:
        # The predicate's own head test first, over the fold the caller
        # already has: almost no token opens any entry, and for those
        # there is nothing to assemble. Same function maiden_marker_run
        # consults, so a token skipped here is one it would refuse.
        if not maiden_marker_head(folded[i], markers):
            i += 1
            continue
        # Bound the lookahead at the first structural boundary, so the
        # predicate is asked over the words that could form one run and
        # answers longest-first WITHIN them -- a two-word entry refused
        # at a clause edge still leaves a one-word entry starting there
        # free to match.
        limit = 1
        if cap > 1:
            if buckets is None:
                buckets = [comma_bucket(t.span.start, state.comma_offsets)
                           for t in tokens]
            role, bucket = tokens[i].role, buckets[i]
            while (limit < cap and i + limit < n_tokens
                   and tokens[i + limit].role is role
                   and buckets[i + limit] == bucket):
                limit += 1
        run = maiden_marker_run(
            [tokens[k].text for k in range(i, i + limit)], markers)
        if not run:
            i += 1
            continue
        tags[i] = "vocab:maiden-marker"
        for k in range(i + 1, i + run):
            tags[k] = "vocab:maiden-marker-cont"
        i += run
    return tags


def classify(state: ParseState) -> ParseState:
    # One fold per token, shared by the marker pass and the vocabulary
    # tags -- the shape suffix_as_written already asks for ("n is
    # _normalize(text), passed in so callers normalize once").
    folded = [_normalize(t.text) for t in state.tokens]
    marker_tags = _tag_marker_runs(state, folded)
    # rules.md#P3 says a maiden marker, taken as one, and the words it
    # takes, are not among the name's own words -- so clause_at is the
    # smallest index tagged as a marker HEAD, and everything from there
    # on is the clause. A plain loop, not a generator handed to min():
    # marker_tags is almost always empty, and its keys arrive in index
    # order (_tag_marker_runs walks left to right), so the first head a
    # forward walk finds is already the smallest. Filtering on the HEAD
    # tag specifically (never "-cont") is what makes that answer right
    # independent of _tag_marker_runs's insertion order too: every
    # matching entry is a clause start, so a min() over them in any
    # order would agree with this walk -- the walk just takes the
    # cheaper path given the order this dict happens to arrive in.
    clause_at = len(state.tokens)
    for i, tag in marker_tags.items():
        # A marker word already carrying a role arrived pre-set by
        # extract (WorkToken.role's docstring) -- it is the CLAUSE's
        # word, not a bare one opening a new clause, so it must not
        # move clause_at: a delimited/maiden clause's own marker
        # content is excluded from "own" by its role already, and
        # letting it also set clause_at truncates the OWN words that
        # follow the clause ("JUAN (NEE JONES) GARCIA Y LOPEZ"'s
        # trailing "GARCIA Y LOPEZ" is such own text).
        if tag == "vocab:maiden-marker" and state.tokens[i].role is None:
            clause_at = i
            break
    # ONE fact per parse, taken over the name's OWN words (rules.md#P3):
    # not a delimited clause's tokens, which arrive with `role` already
    # set by extract (WorkToken.role's docstring), and not the maiden
    # clause itself, which starts at clause_at. Appending a clause must
    # not flip the reading of words that did not change. Not stored on
    # ParseState: nothing downstream reads it today, and #289/#516 can
    # promote it the way `order` was recorded rather than recomputed.
    # is_one_case's own `Sequence` parameter is where the frame-cost
    # argument for handing it a built list lives (_vocab.py, #475).
    own = [t.text for t in state.tokens[:clause_at] if t.role is None]
    one_case = is_one_case(own)
    # The fork itself must not read a clause's words either, so the
    # `one_case and ...` argument below repeats `own`'s membership test
    # per token, and the fork and its emitter then agree with the case
    # class they consult. No extra frame -- it is one more boolean in a
    # comprehension that already walks every token.
    tokens = tuple(
        dataclasses.replace(
            t, tags=_tags_for(t, folded[i], state, marker_tags.get(i),
                              one_case and i < clause_at
                              and t.role is None))
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
    return dataclasses.replace(state, tokens=tokens,
                               ambiguities=tuple(ambiguities))
