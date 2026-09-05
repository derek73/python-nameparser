"""Stage: script_segment (#271, #272, #308, #312).

Consumes: tokens, segments, structure, interpunct_offsets, segmenter.
Produces: tokens, by two independent splits into sub-slices -- a
listed honorific peeled off the END of the name's last
non-post-nominal token, in whichever of the name's runs that falls
(the tail token also carries this module's _PEELED_TAG), and the
first activated-script token of the name segment split into n+1 --
segments (index runs remapped past the insertions), ambiguities
(indices likewise remapped, plus a SEGMENTATION report when more than
one split was vocabulary-supported, or when a segmenter's answer
scored under the confidence floor).
Reads: Policy.segment_scripts, Lexicon.surnames,
Lexicon.honorific_tails, ParseState.segmenter, and Lexicon suffix
vocabulary through TWO predicates, which are NOT one another's
singular and plural. _vocab.is_suffix_strict asks whether a single
token is a post-nominal, initial veto included (the peel's scan-back
and the surname site). _vocab.is_wholly_suffix asks segment's own
suffix-comma question of a whole RUN, through the POLICY-selected
token test plus period_joined_vocab, delimiter handling and the
Ph./D. merge -- so the run predicate says yes both to tokens the
token predicate VETOES ("V.", "V", "I") and to tokens it never sees
as suffixes at all ("Msc.Ed.", "J.씨", which reach it through
period_joined_vocab). The initial-shaped words are the class #319 was
ABOUT, not the whole of the disagreement, and the extra routes listed
above are where the rest of it comes from;
test_is_wholly_suffix_is_not_the_plural_of_is_post_nominal pins the
"V." half. The run predicate is how the peel declines a run that is
not name text (#319), but only where the name's own run offers a
site, since a glued honorific is itself part of what makes a run read
as suffix-shaped; it owns two further Policy fields
(lenient_comma_suffixes picks the strict or lenient token test -- it
flips "田中さん, V." -- and extra_suffix_delimiters both counts a bare
delimiter-core token as a suffix and splits a token on a core, the
split being the half that flips "田中さん, Jr./V." under {"/"} and the
bare core the half that flips "田中さん, /").

Implements rules W1 (the vocabulary/segmenter division), W2 (the
glued-honorific peel) and W3 (the writer's divisions are respected)
of docs/design/rules.md, cited at their code below; the decision
chain (#308, #312, #319, the vetting bars, the measured
spaced-honorific trade) is decisions.md#W1, #W2 and #W3. Both splits make sub-slices of one token,
rewriting nothing -- spans still index the original exactly, so the
anti-#100 invariant holds by construction. The peel runs FIRST, so
suffix classification can claim the tail and the surname match or
segmenter consult sees the name rather than name-plus-honorific; its
ASCII bail sits above everything here, so a caller-added LATIN tail
fires only on a name carrying at least one non-ASCII character (see
the bail's own comment, and honorific_tails' field note).
"""
from __future__ import annotations

import dataclasses
import functools
from collections.abc import Sequence

from nameparser._pipeline._state import (
    ParseState, PendingAmbiguity, Structure, WorkToken,
)
from nameparser._pipeline._vocab import (
    effective_script, is_suffix_strict, is_wholly_suffix,
)
from nameparser._types import AmbiguityKind, Segmentation, Span

#: Marks the tail token the peel below MANUFACTURED, so the segmenter's
#: neighbour test can tell it from a token somebody wrote. Namespaced,
#: therefore unstable provenance rather than API (_types.STABLE_TAGS is
#: the whole stable set, and FOLDED_TAG is the precedent for a
#: structural marker carrying this prefix); it is vocabulary-derived
#: besides, since honorific_tails is what licensed the split. Emitter
#: and reader are both in this module, so unlike FOLDED_TAG it needs no
#: home in _types.
_PEELED_TAG = "vocab:peeled-honorific"

#: Segmenter answers scoring below this attach a SEGMENTATION report
#: (amendment 2026-07-29 section 3). Kept at the drafted 0.9 after
#: measuring namedivider 0.4.1 over 112 names (#272 Task 5), which
#: found a distribution the amendment did not anticipate: the scores
#: are BIMODAL, not clustered near 1. A rule-based division (the kana
#: boundary in 高橋みなみ, or a two-character name) scores exactly 1.0;
#: a kanji-statistics division scores a softmax over the candidate cut
#: positions, observed in 0.23-0.68 and driven more by name LENGTH
#: (median 0.61 at three characters, 0.37 at five -- the softmax is
#: over len-1 candidates) than by correctness: the wrong answers in
#: the sample scored 0.32/0.60/0.60/0.61, straddling the correct
#: median of 0.52. So no floor INSIDE that band separates error from
#: success, and the only cut the data supports is between a stated
#: certainty and a statistical guess -- which is what section 3's
#: epistemic argument asks for anyway. 0.9 sits in the empty gap
#: (0.68 to 1.0), far from both modes, and reads as "confident" for a
#: third-party segmenter with a calibrated score too. Consequence,
#: pinned by tests and stated so it can be checked: every
#: STATISTICALLY divided name carries a SEGMENTATION report, and every
#: RULE-divided one -- the kana boundary, a two-character name,
#: namedivider's specific-name rules -- carries none.
#: namedivider scores its own two-character rule 1.0, so this floor
#: keeps that division silent -- see locales/ja.py for why the
#: presumption is accepted as stated.
#: Not configurable in 2.x (YAGNI).
_SEGMENTER_CONFIDENCE_FLOOR = 0.9


def _remap(run: tuple[int, ...], split_at: int,
           added: int) -> tuple[int, ...]:
    """One segment run after token `split_at` split into `added` + 1
    pieces: the extra pieces join the run immediately after it, and
    every later index shifts by as many."""
    out: list[int] = []
    for j in run:
        if j == split_at:
            out.extend(range(split_at, split_at + added + 1))
        else:
            out.append(j + added if j > split_at else j)
    return tuple(out)


def _pieces(text: str, splits: tuple[int, ...]) -> tuple[str, ...]:
    """`text` cut at every offset in `splits`: n offsets, n+1 pieces."""
    cuts = (0, *splits, len(text))
    return tuple(text[a:b] for a, b in zip(cuts, cuts[1:]))


def _split(state: ParseState, i: int, splits: tuple[int, ...],
           detail: str | None, tail_tag: str | None = None) -> ParseState:
    """Cut token `i` at every offset in `splits`, recording `detail` as
    a SEGMENTATION report when there is one, and adding `tail_tag` to
    the LAST piece when there is one of those.

    The offsets arrive non-empty, ascending and interior whatever chose
    them. From a segmenter: non-empty is the caller's own check,
    strictly ascending with each >= 1 is Segmentation.__post_init__'s,
    and the last offset is < len(text) -- checked by the caller. From
    the vocabulary: the single offset is >= 1 and < len(text) by the
    range(cap, 0, -1) construction and its len-1 cap.

    The ONE split path: the vocabulary hit is the single-offset case
    and the segmenter's answer the general one, so neither can drift
    from the other's index arithmetic. `tail_tag` is part of keeping it
    one path: the piece is tagged HERE, where it is built, rather than
    by the caller, which would have to re-derive where its own tail
    landed after handing the index arithmetic off. Only the peel passes
    one, and the piece it wants is the last by construction -- the
    honorific it cut off the end; the surname path passes nothing and
    the default leaves it exactly as it was."""
    token = state.tokens[i]
    base = token.span.start
    parts: list[WorkToken] = []
    start = 0
    for piece in _pieces(token.text, splits):
        end = start + len(piece)
        parts.append(dataclasses.replace(
            token, text=piece, span=Span(base + start, base + end)))
        start = end
    if tail_tag is not None:
        parts[-1] = dataclasses.replace(
            parts[-1], tags=parts[-1].tags | {tail_tag})
    added = len(splits)
    tokens = state.tokens[:i] + tuple(parts) + state.tokens[i + 1:]
    # Every index the earlier stages recorded is now stale past the
    # split point: the segment runs group's own iteration rests on, and
    # the ambiguities from extract_delimited (resolved to indices by
    # tokenize) and segment. An ambiguity ON the split token keeps
    # pointing at the head.
    segments = tuple(_remap(run, i, added) for run in state.segments)
    ambiguities = tuple(
        dataclasses.replace(a, indices=tuple(
            j + added if j > i else j for j in a.indices))
        for a in state.ambiguities)
    if detail is not None:
        ambiguities += (PendingAmbiguity(
            AmbiguityKind.SEGMENTATION, detail,
            tuple(range(i, i + added + 1))),)
    return dataclasses.replace(state, tokens=tokens, segments=segments,
                               ambiguities=ambiguities)


@functools.lru_cache(maxsize=16)
def _longest_entry(entries: frozenset[str]) -> int:
    """The longest entry in a vocabulary, cached per-vocabulary rather
    than recomputed per parse (Lexicon is frozen and slotted, so it
    cannot carry a cached_property of its own). The frozenset is
    hashable and a process holds only a handful of distinct
    vocabularies -- the default one, plus one per constructed pack
    parser -- so maxsize=16 bounds pathological many-lexicon churn
    without ever evicting in normal use. Keyed by the frozenset VALUE,
    not by (lexicon, field): the two callers pass surnames and
    honorific_tails, but every lexicon that leaves KOREAN_SURNAMES
    alone shares one entry, so the count is distinct SETS rather than
    lexicons times fields.

    Callers must pass a NON-EMPTY vocabulary: max() of an empty set
    raises, and both call sites sit under a match guard that cannot
    reach it with one."""
    return max(map(len, entries))


def _is_post_nominal(state: ParseState, i: int) -> bool:
    """Whether token `i` is post-nominal VOCABULARY. Two of this
    stage's decisions ask it and neither is about script: an honorific
    is neither a surname SITE nor the token a glued honorific hangs off
    (#308).

    It answers a VOCABULARY question, not a positional one, and the two
    callers do not spend the answer the same way. In TRAILING position
    vocabulary and position agree, so the peel site steps over a True
    and goes on scanning. In LEADING position they disagree -- 양 is
    the family name there, whatever the suffix set says -- so the
    surname site reads a True as an ANSWER and declines, rather than as
    a token to step past.

    STRICT, not lenient: the initial veto applies, so "V." is not a
    post-nominal here though bare "v" is a suffix word. That agrees
    with what classify does with the same token downstream -- "V." is
    a middle initial -- and the difference is reachable under the
    default lexicon: "田中さん V." stops its scan-back at the initial
    and does not peel, while "田中さん II" steps over II and does. That
    pair is the case table's ja_honorific_glued_before_an_initial and
    ja_honorific_glued_before_a_roman_suffix, added because the clause
    could NAME the discriminating input while swapping in
    is_suffix_lenient still failed no test -- the shape a "unify the
    two suffix predicates" refactor would have walked straight past.

    Suffixes only, deliberately. Should a CJK entry ever join titles,
    the surname site would want it excluded while the peel site must
    not: a title never trails, so widening the peel's scan-back would
    move it off the real last name token. Split the predicate then, not
    before."""
    return is_suffix_strict(state.tokens[i].text, state.lexicon)


# rules.md#W2: "A part that is not name text — a post-nominal word
# standing on its own — is never the name's end: the split-off steps
# past it to the name word behind, and never dissects it." (history:
# decisions.md#W2)
# The scan-back below is that clause, and it needs no punctuation to
# fire. '김민준 박사님' steps past 박사님 to 김민준, finds no listed
# tail there and returns None -- so 박사님 is left whole for suffix
# classification rather than cut into 박사 + 님, which is what the
# same input gives when the step is removed. '선생님' is post-nominal
# entire with no name word behind it, so the scan yields no site at
# all and the token stays whole. Both are contract-tier corpus names
# and rules.md#W2 example lines; decisions.md#cjk-comma-demotion
# carries the forced-predicate measurement behind them.
def _peel_site(state: ParseState, flat: Sequence[int],
               tails: frozenset[str]) -> tuple[int, int] | None:
    """Where a peel would land in the token run `flat`: the index of the
    token to cut and the LENGTH of the listed tail to take off it, or
    None where that run offers no peel.

    Two callers, one answer, which is the point of naming it. The peel
    itself asks it once, of the runs it decided to scan. The gate above
    that decision asks it of segments[0] ALONE, to find out whether
    declining the second run would cost the only site. Sharing the scan
    with the peel rather than approximating it there is what makes the
    gate's answer mean what it says: a gate that merely looked for a
    token ENDING in a listed tail would count a token that is a tail
    entire, which the scan-back skips as a site -- "선생님, J.씨" would
    decline on a site the peel then cannot use, and lose the peel in
    exactly the way the gate exists to prevent. (Only the lone-token
    shape of that divergence is reachable from the gate, and the gate's
    own other conjunct is what makes that so: SUFFIX_COMMA wants BOTH
    a suffix-shaped second run and more than one word before the
    comma, and the gate is asked only where the first of those is
    already true -- so a run this call ever sees under FAMILY_COMMA
    failed on the second, and segments[0] holds at most one token. The
    word-count alone would not say that: "Dr 김민준, 지훈" has two
    words before the comma and is FAMILY_COMMA.)

    Callers must pass a NON-EMPTY `tails` -- _longest_entry's
    precondition, which the stage's own early return supplies."""
    i = next((j for j in reversed(flat)
              if not _is_post_nominal(state, j)), None)
    if i is None:
        # nothing but post-nominals, or no tokens at all
        return None
    text = state.tokens[i].text
    # range/cap construction identical to the surname match below, and
    # for the same two reasons: longest-first, and a len-1 cap that
    # makes the offset interior by construction (_split's contract).
    cap = min(_longest_entry(tails), len(text) - 1)
    for length in range(cap, 0, -1):
        if text[-length:] in tails:
            return i, length
    return None


# rules.md#W2: "a listed honorific glued to the end of the name's
# last name word splits off once and reads as a suffix." (history:
# decisions.md#W2)
# That the peel also reaches ACROSS a family comma is stated at
# rules.md#W3 instead, which is a tolerated rule since the
# 2026-09-01 comma demotion -- the crossing is what the parser does
# today, not something W2 promises. W3 also took, on 2026-09-05, the
# reading of a period a listing leaves behind
# (decisions.md#cjk-comma-demotion): a period on a SEPARATE
# post-nominal word rides into the suffix and moves nothing ('様.'
# is post-nominal-strict and the scan steps past it as it steps past
# '様'), while a period glued to the honorific's OWN token stands
# between the honorific and that token's end, so no listed tail
# matches, the peel declines, and the whole text reads as a title
# downstream ('田中さん.', '김민준씨.') -- measured 2026-09-05 and
# pinned by nothing, since neither string is a case row or a corpus
# line, so that reading can move with nothing reporting it. Neither
# is a promise; the step past the post-nominal word itself is W2's,
# above, and is.
def _peel_honorific_tail(state: ParseState) -> ParseState:
    """#308: split a listed honorific off the END of the name's last
    NON-POST-NOMINAL token -- 田中さん -> 田中 + さん -- and let
    the existing machinery do the rest. Suffix classification claims
    the tail downstream (every honorific_tails entry is a suffix word
    too, enforced by Lexicon), and the segmentation half below then
    sees the remainder rather than the glued whole, so 김민준씨 splits
    김 + 민준 and a configured segmenter is handed 山田太郎 rather
    than 山田太郎様.

    Scanning back over post-nominals rather than taking the last token
    outright does three things at once. An unrelated trailing suffix
    cannot hide the peel site, so "김민준씨 Jr." answers as the
    comma-written "Dr 김민준씨, Jr." does -- one name, two spellings,
    one parse. A token that IS a tail (씨, さん, and the nested 선생님,
    which the cap alone would peel to 선생 + 님) is skipped as a site
    and stays whole: every tail is a suffix word by the Lexicon
    invariant, which is what makes that guard hold, and the cap below
    only keeps the offset interior for _split. And the scan answers
    None rather than indexing anything, which two reachable inputs
    need: a name that is nothing but post-nominals ("씨"), and one
    whose name runs are empty (", , 씨" scopes to two empty ones).
    Nothing here rests on a structural gate landing first, then, which
    is what let #312 move both of the stage's gates below it.

    WHICH tokens are scanned is a separate decision, and the one a
    reader is likeliest to undo: the NAME's segment runs, flattened,
    and never state.tokens or every segment. The alternatives agree
    except where extract_delimited has already claimed a token or a
    comma has closed the name, both of which this stage can still see
    -- so "김민준씨 (Jimmy)" and "Dr 김민준씨, V." are the inputs that
    tell the three apart. See the note at the scan itself.

    That last token is the last of the NAME, which reaches into a
    maiden clause: maiden tokens are still main-stream here
    (extract_delimited has masked only bracketed content), so
    "김민준 née 박씨" peels 씨 off the MAIDEN name 박씨 and hands it to
    the person's suffix list -- "née Ms. Park". Intended rather than
    incidental in that direction: the honorific is the reader's
    regardless of which of her names it was glued to, and a
    name-final honorific is exactly what this peels. Since #312 that
    reach extends to FAMILY_COMMA along with the rest of the crossing
    -- "김, 민준 née 박씨" now routes 씨 to suffix, where before #312
    the stage returned at the family-comma gate above the peel and
    left it in maiden "박씨".

    The other direction is a LIMIT, stated rather than fixed: a maiden
    clause pushes the site off the person's own name, so "김민준씨 née
    박" does NOT peel and gives given "민준씨" -- the original bug,
    intact behind a marker. "김민준씨 née 박씨" shows both at once, two
    identical honorifics of which only the maiden's is routed. Chasing
    the marker into the site scan is scope creep for an uncommon input,
    and it could not be done here anyway: classify has not run, so the
    marker tokens carry no tag this stage could read.

    Longest-first, and ONE peel: a remainder that itself ends in a
    listed tail is accepted rather than chased. No SHIPPED input
    witnesses that any more -- 박사님 was the last one, and adding it
    is what removed the case: 김민준박사님 now gives up 박사님 entire,
    since longest-first reaches the whole honorific. The pin needs a
    tail whose remainder ends in a DIFFERENT tail, the two not
    themselves a listed entry, and no pair in the shipped vocabulary
    has that shape; the stage test test_one_peel_never_a_stack carries
    it on a synthetic lexicon, which is now its only witness. No
    script precondition on the remainder either, since the tail alone
    is the license: Andersonさん peels.

    Emits no ambiguity, unlike the surname fork below, though
    longest-first does CHOOSE here too -- 김선생님 gives 선생님 where
    님 also matches. The difference is what the runner-up is: a second
    matching surname is a competing READING of the name, which a
    caller may prefer, while a shorter tail leaves a remainder that is
    not a name at all (김선생), so there is nothing to adjudicate."""
    tails = state.lexicon.honorific_tails
    if not tails:
        return state
    # The NAME's runs, which is more than segments[0] but never every
    # segment. A comma is how a writer says which runs are the name: a
    # FAMILY comma splits the name itself across two of them ("김,
    # 민준씨" is (0,) and (1,)), and the honorific is as often glued to
    # the given name as to the family, so the peel has to cross that
    # boundary (#312). Every OTHER structure keeps the whole name in
    # segments[0], so no boundary has to be crossed to find the site
    # there -- which is why the asymmetry is the point rather than an
    # accident of two cases. Note that "the rest is post-nominals" is
    # true of the SUFFIX comma only: under NO_COMMA segment returns
    # exactly one run and any trailing post-nominal is INSIDE it
    # ("김민준씨 Jr." is one run of two tokens), which is why the
    # scan-back above steps over such a token rather than simply never
    # reaching it.
    # The second run is only NAME text when segment read it as one,
    # which the structure alone does not say: SUFFIX_COMMA also wants
    # more than one word before the comma, so a one-word part turns a
    # wholly suffix-shaped remainder into FAMILY_COMMA anyway ("田中さん,
    # V." is that input). So ask segment's own predicate instead of
    # inferring the answer from the structure it produced (#319).
    # is_wholly_suffix, NOT the plural of _is_post_nominal: the two
    # disagree on the initial-shaped suffix words ("V.", "V", "I"),
    # which is the class #319 was reported about, and on everything
    # the run predicate's extra routes reach and the token predicate
    # does not ("Msc.Ed." and "J.씨" by period_joined_vocab, both of
    # which this change also moves). Reaching into such a
    # run put the site on "V.", which ends in no listed tail, so the
    # peel silently abandoned and さん stayed glued to the family --
    # while "田中さん, PhD" peeled all along, because "PhD" satisfies
    # the strict test and the scan-back stepped over it. One credential,
    # two spellings, two answers FROM THE PEEL -- and the peel's answer
    # is the only one that moved: the peeled remainder is 田中 and lands
    # in family under every spelling, while where the CREDENTIAL lands
    # is assign's question and still differs ("PhD" a title, "V." a
    # given, "Ph. D." a suffix beside さん).
    # A junk tail is the worse shape of the same reach: in
    # "김민준씨, J.씨" the site lands on the junk "J.씨", so master
    # peeled THAT 씨 and left the person's own glued inside family
    # "김민준씨". Reachable only where the run is genuinely
    # suffix-shaped, which "J.씨" is by period_joined_vocab; a run of
    # ordinary name text is scanned on purpose, and a junk tail further
    # out than the second run is held off by the scope rule instead
    # ("Dr 김민준씨, Jr., 박씨" is SUFFIX_COMMA with 박씨 in a third
    # run, so it never reaches here at all).
    # An EMPTY second run stays in scope and contributes nothing:
    # is_wholly_suffix is False on it by its own contract (v1 read
    # "Doe,, Jr." as a family comma), which is the reading this line
    # wants anyway -- flattening an empty run adds no site.
    # Policy(lenient_comma_suffixes=False) keeps the old answer for the
    # INITIAL-shaped suffixes specifically, which is where the
    # strict/lenient gap lives: the knob drops this call to the strict
    # predicate too, so is_wholly_suffix(["V."]) is False, the run reads
    # as name text, it IS scanned, and the peel is abandoned on "V." as
    # before -- family "田中さん", given "V.". It is not a blanket
    # freeze of the old behavior, and "田中さん, Ph. D." is the input
    # that shows the difference: the Ph./D. merge folds that pair to a
    # form is_suffix_strict accepts, so the run is declined and the peel
    # fires under the strict knob as well.
    # Flattening the SEGMENTS rather than state.tokens is load-bearing
    # too: extracted nickname and maiden content is in tokens but in NO
    # segment, and scanning tokens would put the peel site on a
    # nickname ("김민준씨 (Jimmy)" -> the site becomes Jimmy and
    # nothing peels). ko_honorific_glued_given_nickname pins that.
    # And declining takes a SECOND condition: segments[0] must hold a
    # peel site of its own. is_wholly_suffix reaches period_joined_vocab,
    # which calls a run suffix-shaped when ANY period-chunk is suffix
    # VOCABULARY -- and every honorific tail is a suffix word by the
    # Lexicon invariant, so a glued honorific is itself the evidence.
    # The predicate is circular at THIS call site alone -- not because
    # segment asks it any earlier (nothing has peeled at either call)
    # but because segment SPENDS the answer differently: it reads the
    # run's shape and stops, the answer being the structure, while the
    # peel reads the same shape and then decides whether to go strip
    # the very honorific that produced it. "이, J.씨" reads as wholly suffix
    # only because of the 씨 the peel exists to remove, and declining a
    # run that holds the only site does not fall back to some other
    # site -- it loses the peel outright, and with it the given name,
    # which lands in suffix as "J.씨". Asking for a site in segments[0]
    # keeps the #319 answer wherever the peel has somewhere else to go
    # ("田中さん, V." still declines, さん is right there) and gives the
    # circular case back to master's reading. The two-honorific input
    # "김민준씨, J.씨" is where the choice is visible and deliberate:
    # both runs offer a site, so the decline stands and the person's own
    # 씨 is peeled rather than the junk one behind the comma.
    runs = state.segments[:1]
    if state.structure is Structure.FAMILY_COMMA:
        second = [state.tokens[j].text for j in state.segments[1]]
        if not (is_wholly_suffix(second, state.lexicon, state.policy)
                and _peel_site(state, state.segments[0], tails)):
            runs = state.segments[:2]
    site = _peel_site(state, [j for seg in runs for j in seg], tails)
    if site is None:
        return state
    i, length = site
    # The tail carries a tag because this stage MANUFACTURED it. The
    # segmenter's neighbour test below needs to tell it from a token
    # somebody wrote, and no vocabulary question can: the two spellings
    # put the same word in the same place, and only the provenance
    # differs.
    return _split(state, i, (len(state.tokens[i].text) - length,), None,
                  tail_tag=_PEELED_TAG)


def _split_surname_site(state: ParseState) -> ParseState:
    """The stage's other split: the first activated-script token of the
    name part is matched longest-first against Lexicon.surnames, and a
    hit splits it in two; where the vocabulary declines, an optional
    Parser(segmenter=...) is consulted instead.

    A sibling of _peel_honorific_tail rather than a continuation of it.
    The two answer different questions -- this one asks where a name
    divides into surname and given, the peel asks whether a token ends
    in a word that can never end a name -- which is why they carry
    different gates: the FAMILY comma and the 间隔号 gate this half
    alone (#312), and segment_scripts below gates it alone too. That
    is also why the stage entry below interleaves gates with its two
    calls rather than running one cascade."""
    scripts = state.policy.segment_scripts
    # an empty VOCABULARY deliberately does not bail here -- see below
    if not scripts:
        return state
    # segments[0] is the NAME part under both remaining structures
    # (everything, under NO_COMMA); later segments are suffixes. Its
    # members are main-stream token indices by construction, so
    # extracted nickname/maiden content is unreachable from here. For
    # this site that is merely tidy -- the first script-written token
    # is the same either way. It is the PEEL above that reads this run
    # load-bearingly, and in the two structures that reach here it
    # reads exactly this one, only backwards; the argument lives at
    # that scan.
    i = next((i for i in state.segments[0]
              if effective_script(state.tokens[i].text) in scripts), None)
    # A post-nominal in the surname's own position is not a site to
    # skip past but an answer: a surname LEADS, so if the leading
    # script-written token is an honorific there is no surname here to
    # find. Scanning ON would reach the given name, which is exactly
    # what the first-token rule exists to prevent -- 지 is a listed
    # surname, so "양 지훈" (양 is a surname AND a shipped honorific)
    # would have its own given name split in half. Declining also
    # covers the token the peel above manufactures, which is the first
    # and only script-written one in "Anderson선생님".
    if i is None or _is_post_nominal(state, i):
        return state
    token = state.tokens[i]
    text = token.text
    surnames = state.lexicon.surnames
    # A token that IS a surname never splits: a bare "남궁" must not
    # become 남 + 궁 just because the single-syllable surname also
    # matches -- there is nothing to split off, and a lone token's
    # role is the order resolution's call.
    if text in surnames:
        return state
    # Longest-first (compound-before-single falls out of it), capped
    # so the remainder is never empty. Direct membership, no
    # _normalize: the script gate admits only CJK text, which the
    # storage fold stores unchanged. An empty vocabulary skips the
    # match rather than bailing the stage (_longest_entry's max() has
    # nothing to take): a surname-less lexicon declines every token,
    # which is exactly the condition the segmenter is consulted on, so
    # an early bail would make a configured segmenter silently inert
    # under Lexicon.empty() -- the JA pack's own shape.
    matches: list[int] = []
    if surnames:
        cap = min(_longest_entry(surnames), len(text) - 1)
        matches = [length for length in range(cap, 0, -1)
                   if text[:length] in surnames]
    if matches:
        take = matches[0]
        detail = None
        if len(matches) > 1:
            # more than one vocabulary-supported split: longest-first
            # DECIDED a fork, and the deciding stage records it. A
            # single-match split chose nothing, so it stays silent --
            # a dictionary certainty and the statistical guess below
            # are different epistemic states, and these two emission
            # rules say so.
            chosen = " + ".join(map(repr, _pieces(text, (take,))))
            other = " + ".join(map(repr, _pieces(text, (matches[1],))))
            detail = (f"{text!r} splits as {chosen} on the longest "
                      f"surname; {other} also reads")
        return _split(state, i, (take,), detail)
    if state.segmenter is None:
        return state    # the first activated-script token decides
    # The segmenter's precondition, which the vocabulary has no twin of:
    # it is asked where an UNDIVIDED name divides, so it may only be
    # shown a token that is the whole name. Where the name part carries
    # a second script-written token the writer already drew this
    # stage's missing boundary -- "山田 太郎" is divided, and dividing
    # its family again yields 山 + 田 + 太郎 (namedivider answers for
    # any string, and scores a two-character one 1.0 by rule, so no
    # confidence check would catch it). The neighbour counts whatever
    # script it is written in, ACTIVATED or not -- effective_script is
    # merely non-None -- because a katakana or hangul neighbour is a
    # boundary its writer drew just as deliberately as a Han one: under
    # the JA pack "山田太郎 マイケル" declines, though katakana is in no
    # activation set. A Latin title or suffix is NOT such a boundary:
    # it says nothing about where the CJK name splits, so "Dr 阿明日,
    # Jr." still reaches the segmenter. Vocabulary keeps its own rule
    # -- a listed surname is a certainty about that exact string,
    # whoever else stands beside it.
    # The one neighbour that does not count is the one this stage
    # MANUFACTURED (#308): a glued 山田太郎様 has no writer-drawn
    # boundary anywhere, so the 様 the peel just cut off cannot be read
    # as one -- the precondition must see what the writer wrote, which
    # was a single undivided token. A SPACED 様 does count, and the
    # reason is weaker than "its writer drew that boundary and chose
    # to write 山田太郎 as a unit": in "山田太郎 様" the unit the writer
    # drew is the WHOLE NAME, honorific and all, so that story is false
    # for the very input it describes. What the code relies on is that
    # by POSITION a spaced honorific is indistinguishable from a spaced
    # name element, so the test conservatively counts it. Measured, the
    # trade is worth it: counting them keeps 佐藤 氏, 田中 様, 鈴木 先生
    # and 中村 教授 whole -- all four divide bare under the JA pack (佐
    # + 藤, 田 + 中, 鈴 + 木, 中 + 村) -- and costs the single division
    # 山田太郎 様. Four real surnames against one.
    # Provenance, not vocabulary: the two spellings put the same word
    # in the same place, and asking the suffix set instead cannot
    # separate them.
    if any(j != i and effective_script(state.tokens[j].text) is not None
           and _PEELED_TAG not in state.tokens[j].tags
           for j in state.segments[0]):
        return state
    # No try/except around the call: rules.md#A1's Accepted clause
    # ("a user-supplied segmenter's own error propagates"). The two
    # checks below are that same doctrine, curated,
    # and they are where the line this module draws is easiest to state:
    # a PROTOCOL VIOLATION BY THE SEGMENTER AUTHOR RAISES, while an
    # ADAPTER'S DEFENSE AGAINST ITS LIBRARY DECLINES. Both checks here
    # are the first kind -- a wrong answer TYPE and an answer indexing
    # past the token it was handed are stage-detectable bugs in
    # user-supplied code, inside the declared totality exception, so
    # they get the same treatment the callable's own exceptions get.
    # locales/ja.py is the second kind: its repertoire, length,
    # reconstruction and score guards all return None, because what
    # they defend against is namedivider answering a question nobody
    # asked it, which is a fact about the CONTENT, not a broken
    # protocol. Bounded like every message here: the type's NAME, never
    # its contents.
    answer = state.segmenter(text)
    if answer is not None and not isinstance(answer, Segmentation):
        # a duck-typed answer carrying a .splits of its own would
        # otherwise wander into the split path and surface as a
        # ValueError naming Token, pointing the reader at nameparser's
        # insides instead of at their segmenter
        raise TypeError(
            f"segmenter must return Segmentation or None, got "
            f"{type(answer).__name__}")
    if answer is None or not answer.splits:
        return state            # declined, or confidently one token
    # splits[-1] is the max -- Segmentation enforced ascending. The
    # upper bound is the half Segmentation cannot check, since it never
    # sees the text; an offset at or past the end would make an empty
    # piece. Declining silently here (as this did before the review)
    # made an off-by-one segmenter undebuggable: every answer it gave
    # vanished, and the parse merely looked unsegmented.
    if answer.splits[-1] >= len(text):
        raise ValueError(
            f"segmenter returned splits beyond the token: last offset "
            f"{answer.splits[-1]}, token length {len(text)}")
    conf = answer.confidence
    detail = None
    if conf is not None and conf < _SEGMENTER_CONFIDENCE_FLOOR:
        reading = " + ".join(map(repr, _pieces(text, answer.splits)))
        detail = (f"{text!r} splits as {reading} on a segmenter answer "
                  f"scoring {conf:.2f}, under the "
                  f"{_SEGMENTER_CONFIDENCE_FLOOR} confidence floor")
    return _split(state, i, answer.splits, detail)


# rules.md#W1: "an undivided word in the family position of a name
# written in an activated script divides after a recognized surname,
# the longest recognized surname first; where the vocabulary
# recognizes nothing, an optional segmenter may divide instead"
# rules.md#W3: "under a family comma the pre-comma text is the
# family by declaration and never divides, and the post-comma side
# is given text with no family to find" (history: decisions.md#W3)
def script_segment(state: ParseState) -> ParseState:
    if state.original.isascii():
        # spans index the original exactly (the anti-#100 invariant),
        # so an ASCII original has only ASCII tokens: nothing here is
        # in any script's ranges. It also short-circuits the PEEL,
        # which has no script gate of its own -- so a caller-configured
        # ASCII tail never fires, and one non-ASCII character anywhere
        # in the name switches it on. Correct for the CJK vocabulary
        # that ships, stated because honorific_tails is public: see
        # that field's own note. Latin orthography SPACES its
        # post-nominals ("John Smith PhD"), so the glued position this
        # peel exists for is a CJK one to begin with. What Latin does
        # glue is PREnominal and period-joined (Mr.Smith, Lt.Gov.),
        # which _vocab.period_joined_vocab classifies as one token
        # rather than splitting -- a different mechanism, and no peel
        # site either way. A glued Latin POST-nominal is spelled the
        # same way, so it reaches that same mechanism rather than
        # nothing: period_joined_vocab reads "Smith.Jr." as a title
        # ('jr' is title vocabulary as well as suffix vocabulary), and
        # where position allows, that wins -- "Smith.Jr. Anderson"
        # gives title "Smith.Jr.", family "Anderson". Whatever it
        # decides, this bail is what settles the question here: it
        # returns above all of it, so no ASCII input reaches the peel.
        return state
    if not state.segments:
        return state
    # #312: the peel runs in front of both gates below, because both
    # answer where a name divides into surname and given, and the peel
    # does not ask that. It asks whether a token ends in a word that
    # can never end a name, and a comma or a dot elsewhere in the
    # string does not change the answer. Placing it above the block
    # also keeps a future segmentation gate from silently capturing
    # it: a new gate lands with its siblings, below.
    state = _peel_honorific_tail(state)
    if state.structure is Structure.FAMILY_COMMA:
        return state    # the comma already drew the SURNAME boundary
    if state.interpunct_offsets:
        # #298: a 间隔号-divided name is a transcription -- its pieces
        # are syllable groups, not surname+given, so neither the
        # vocabulary nor the segmenter applies (codepoint-scoped: the
        # nakaguro records nothing and gates nothing, spec decision 5).
        # State-global like the FAMILY_COMMA gate above: a marker
        # anywhere in the name reads the WHOLE name as a transcription
        # listing, so even an un-dotted hangul token beside a dotted
        # one stays whole. Scoped to the surname split since #312: an
        # honorific glued to a transcription is still an honorific.
        return state
    return _split_surname_site(state)
