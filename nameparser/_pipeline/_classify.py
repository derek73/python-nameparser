"""Stage: classify.

Consumes: tokens.
Produces: tokens with vocabulary tags added (text/span/role unchanged).
Reads: every Lexicon vocabulary field; no Policy FIELD is consulted
(is_initial does consult the _policy module's _NO_INITIALS constant,
which is not configuration -- nothing here varies by Policy value).

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

import bisect
import dataclasses

from nameparser._lexicon import _normalize
from nameparser._pipeline._state import (
    ParseState, PendingAmbiguity, WorkToken,
)
from nameparser._types import AmbiguityKind, Role
from nameparser._pipeline._vocab import (
    _longest_marker, is_initial, maiden_marker_head, maiden_marker_run,
    period_joined_vocab, suffix_as_written,
)




# rules.md#S2: "a trailing word of the suffix vocabulary reads as a
# suffix — generational forms and credential acronyms alike, and an
# ambiguous acronym written with its periods, one after each
# letter, counts unambiguously; a single trailing period is the
# abbreviation shape any word can wear and does not. A
# bare ambiguous acronym is consumed only when the name has words to
# spare"
def _tags_for(token: WorkToken, state: ParseState) -> frozenset[str]:
    lex = state.lexicon
    n = _normalize(token.text)
    tags = set(token.tags)
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
    if n in lex.conjunctions and not is_initial(token.text):
        # v1's is_conjunction excludes initials: 'e.' in 'john e. smith'
        # is a middle initial, not the Spanish conjunction 'e'
        tags.add("conjunction")
    if n in lex.bound_given_names:
        tags.add("vocab:bound-given")
    # maiden markers are NOT tagged here: an entry may be a phrase whose
    # words are not markers on their own, and this function sees one
    # token with no neighbours. _tag_marker_runs below does the whole
    # field, single words included, so there is one place that decides
    # it (mechanisms.md#ONE-PREDICATE-PER-QUESTION).
    if is_initial(token.text):
        tags.add("initial")
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


def _tag_marker_runs(tokens: tuple[WorkToken, ...],
                     state: ParseState) -> tuple[WorkToken, ...]:
    """Tag each maiden marker run: its head "vocab:maiden-marker", the
    rest "vocab:maiden-marker-cont".

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

    A run never crosses a STRUCTURAL boundary, and that is a rule about
    the tag rather than a guard on a consumer. This pass walks the whole
    span-sorted stream, delimited-clause tokens included, where group
    walks one segment -- and a segment is neither: _segment.py drops
    every token extract already gave a role, and buckets what is left by
    the commas before it. So a run half inside a bracketed clause is a
    run no piece walk can see whole, and letting it be tagged made
    'Anna z (domu) Nowak' read family 'Anna', maiden 'Nowak' -- the bare
    preposition eating the name, which is the exact damage the phrase
    entry exists to prevent. Refusing to tag it is what keeps
    _group._marker_run_pieces' "the next piece, always in `seen`" true;
    truncating the run instead would hand a proper PREFIX of the phrase
    to M2 as a whole marker, which is the same bug one word shorter.
    """
    markers = state.lexicon.maiden_markers
    # the lookahead the vocabulary actually needs; 0 for an empty set,
    # which skips the pass entirely
    cap = _longest_marker(markers)
    if not cap:
        return tokens
    texts = [t.text for t in tokens]
    out = list(tokens)
    # What "structurally contiguous" is, per token, as two parallel
    # lists so the walk below compares values rather than recomputing.
    # Role: tokenize gives every extracted clause's tokens the clause's
    # role and leaves the main stream None, so a role change IS a
    # clause edge. Bucket: the count of commas before the token's
    # start, which is exactly how _segment.py buckets a token into a
    # segment -- so two tokens agree here iff segment would put them in
    # one. `None` for the overwhelmingly common comma-free name, which
    # skips the bisect sweep entirely.
    commas = state.comma_offsets
    buckets = ([bisect.bisect_left(commas, t.span.start) for t in out]
               if commas else None)

    n_tokens = len(out)
    i = 0
    while i < n_tokens:
        # Bounded slice, not texts[i:]: a full-tail slice per token is
        # quadratic in the token count, and the predicate would ignore
        # everything past `cap` anyway. Bounded again at the first
        # structural boundary, so the predicate is asked over the words
        # that could form one run and answers longest-first WITHIN them
        # -- a two-word entry refused at a clause edge still leaves a
        # one-word entry starting there free to match. The walk is
        # skipped entirely for an all-single-word vocabulary, where cap
        # is 1 and no lookahead happens at all.
        # The predicate's own head test first: almost no token opens
        # any entry, and for those there is nothing to assemble. This
        # is the same function maiden_marker_run consults, so a token
        # skipped here is one the predicate would have refused anyway.
        if not maiden_marker_head(texts[i], markers):
            i += 1
            continue
        limit = 1
        if cap > 1:
            # Walk forward while nothing structural divides the tokens.
            # Compared against token i rather than pairwise, which is
            # the same walk: it stops at the first mismatch either way.
            role = out[i].role
            bucket = buckets[i] if buckets is not None else 0
            while (limit < cap and i + limit < n_tokens
                   and out[i + limit].role is role
                   and (buckets is None or buckets[i + limit] == bucket)):
                limit += 1
        run = maiden_marker_run(texts[i:i + limit], markers)
        if not run:
            i += 1
            continue
        for k in range(i, i + run):
            tag = ("vocab:maiden-marker" if k == i
                   else "vocab:maiden-marker-cont")
            out[k] = dataclasses.replace(out[k], tags=out[k].tags | {tag})
        i += run
    return tuple(out)


def classify(state: ParseState) -> ParseState:
    tokens = tuple(
        dataclasses.replace(t, tags=_tags_for(t, state))
        for t in state.tokens)
    tokens = _tag_marker_runs(tokens, state)
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
    return dataclasses.replace(state, tokens=tokens,
                               ambiguities=tuple(ambiguities))
