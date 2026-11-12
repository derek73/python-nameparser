"""Stage: script_segment (#271, #272, #308, #312).

Consumes: tokens, segments, structure, interpunct_offsets, segmenter,
one_case where segment recorded it, and comma_offsets, for the
own-words span `_one_case` asks the fact over where segment did not
(#613; the answer is not recorded, classify recording its own), and
original, for the peel's ASCII bail.
Produces: tokens, by four independent splits into sub-slices -- a
word of the part before any comma glued to the next at its full stop
divided there (rules/T8), with a SUFFIX_OR_NAME report where an
initial is cut from the word ending the name, a listed title peeled
off the START of the name's first word or the given part's (rules/W6), a
listed honorific peeled off the END of the name's last
non-post-nominal token, in whichever of the name's runs that falls
(the tail token also carries this module's _PEELED_TAG), and the
first activated-script token of the name segment split into n+1
(into its two surnames and, undivided, the given name behind them,
where a Han surname pair stands there, the second surname carrying
SURNAME_PAIR_TAG for post_rules, rules/W5) -- segments (index runs remapped past the insertions), ambiguities
(indices likewise remapped, plus a SEGMENTATION report when more than
one split was vocabulary-supported, or when a segmenter's answer
scored under the confidence floor).
Reads: the vocabulary `_vocab.glued_cuts` reads for T8 (Lexicon.titles,
titles_ambiguous, title_modifiers, title_styles, saint_particles,
given_name_abbreviations, suffix_acronyms and its ambiguous set,
suffix_words and its ambiguous set, credential_words, and
period_joined_vocab's), and Lexicon.suffix_words, suffix_acronyms and
titles DIRECTLY (the end-of-name report's tests), Policy.segment_scripts, Lexicon.surnames, Policy.script_orders
and Policy.name_order (the order W5's pair needs, rules/W4),
Lexicon.honorific_tails, Lexicon.glued_titles and Lexicon.titles (the
front peel's words and the titles a site steps past and never cuts),
ParseState.segmenter, Lexicon.maiden_markers
DIRECTLY (the own-words span `_one_case` takes, _pieces.own_words),
everything classify and `_comma.decide` read, through
`_postnominal_behind_a_whole_name` (the comma's own decision, asked of
a classified copy of the state, #613), and Lexicon suffix
vocabulary through TWO predicates, which are NOT one another's
singular and plural. _vocab.is_suffix_strict asks whether a single
token is a post-nominal, initial veto included (the peel's scan-back
and the surname site). _vocab.is_wholly_suffix asks C1's suffix
test of a whole RUN -- the one `_comma.decide` and segment's C2 flag
ask -- through the POLICY-selected
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

Implements rules T8 (a word glued at its full stop), W1 (the
vocabulary/segmenter division), W2 (the glued-honorific peel), W6 (the
glued-title peel), W3 (the
writer's divisions are respected) and W5's division (a Han surname
pair) of docs/design/rules/, cited at their code below; the decision
chain (#308, #312, #319, the vetting bars, the measured
spaced-honorific trade) is decisions/W1, #W2 and #W3, and T8's
decisions/T8. Every split makes sub-slices of one token, rewriting nothing -- spans still index
the original exactly, so the anti-#100 invariant holds by
construction. The script splits also match on the token's CORE, its
text.rstrip(FULL_STOPS) (#323) -- rstrip and never strip, because
both offsets are measured from the text's START, so the core has to
stay a prefix of the text for the offset the match yields to land
where the match did. The peel runs before the script splits, so suffix classification
can claim the tail and the surname match or segmenter consult sees
the name rather than name-plus-honorific; its ASCII bail sits above
every script split, T8's division alone running ahead of it, since
it divides glued words in any cased script, ASCII ones included, so
a caller-added LATIN tail
fires only on a name carrying at least one non-ASCII character (see
the bail's own comment, and honorific_tails' field note).
"""
from __future__ import annotations

import functools
import unicodedata
from collections.abc import Callable, Sequence

from nameparser._lexicon import FULL_STOPS, _normalize
import nameparser._pipeline._comma as _comma
from nameparser._pipeline._classify import classify
from nameparser._pipeline._state import (
    SURNAME_PAIR_TAG, ParseState, PendingAmbiguity, PendingReading,
    Structure, WorkToken, copy_with,
)
from nameparser._pipeline._vocab import (
    GLUED_SHAPE, dotted_title_end, effective_script,
    glued_cuts, glued_saint_cut, title_prefixes,
    is_initial_chunk, is_one_case,
    period_joined_vocab,
    is_suffix_strict, is_wholly_suffix, resolve_script_set,
)
from nameparser._pipeline._pieces import own_words
from nameparser._policy import Script
from nameparser._types import (
    AmbiguityKind, ReadingKind, ReadingSource, Role, Segmentation, Span,
)

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
    range(cap, 0, -1) construction and its len-1 cap. From T8's
    division: `_vocab.glued_cuts` appends each offset after a matched
    stop, so each is >= 2, ascending, and < len(text), a name following.

    The ONE split path: the vocabulary hit is the single-offset case,
    and the segmenter's answer and T8's division the general one, so
    none can drift from the others' index arithmetic. `tail_tag` is part of keeping it
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
        parts.append(copy_with(
            token, text=piece, span=Span(base + start, base + end)))
        start = end
    if tail_tag is not None:
        parts[-1] = copy_with(
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
        copy_with(a, indices=tuple(
            j + added if j > i else j for j in a.indices))
        for a in state.ambiguities)
    if detail is not None:
        ambiguities += (PendingAmbiguity(
            AmbiguityKind.SEGMENTATION, detail,
            tuple(range(i, i + added + 1))),)
    return copy_with(state, tokens=tokens, segments=segments,
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
    # rules/T4, #727: a bare lowercase letter in a name written in one
    # case is vetoed as its capital is; the case fact is asked only of
    # such a letter, so a CJK honorific (no case) never asks it
    text = state.tokens[i].text
    return is_suffix_strict(text, state.lexicon,
                            len(text) == 1 and text.islower()
                            and _one_case(state))


# rules/W2: "A part that is not name text — a post-nominal word
# standing on its own — is never the name's end: the split-off steps
# past it to the name word behind, and never dissects it." (history:
# decisions/W2)
# The scan-back below is that clause, and it needs no punctuation to
# fire. '김민준 박사님' steps past 박사님 to 김민준, finds no listed
# tail there and returns None -- so 박사님 is left whole for suffix
# classification rather than cut into 박사 + 님, which is what the
# same input gives when the step is removed. '선생님' is post-nominal
# entire with no name word behind it, so the scan yields no site at
# all and the token stays whole. Both are corpus names and
# rules/W2 example lines; decisions/cjk-comma-demotion
# carries the forced-predicate measurement behind them.
def _peel_site(state: ParseState, flat: Sequence[int],
               tails: frozenset[str]) -> tuple[int, int] | None:
    """Where a peel would land in the token run `flat`: the index of the
    token to cut and the OFFSET to cut it at (the listed tail, and any
    full stops riding behind it, are what comes off the end), or None
    where that run offers no peel.

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
    # The tail is matched on the token's core (#323): a stop glued after
    # the honorific ('김민준씨.', '田中さん.') stands between the listed
    # tail and the token's end and used to defeat the match. What the
    # text read instead depended on the stop: the ASCII spelling went to
    # a title downstream (H2's shape is ASCII-period-only), while a
    # fullwidth or ideographic stop left the whole text a lone name word
    # ('田中さん。' read given). The cut lands BEFORE the tail, so the
    # stops ride with the honorific piece and the token text is never
    # rewritten. TRAILING only: a leading stop is not between the name
    # and its honorific, and the offset returned below is the core's
    # length less the tail's, one subtraction.
    core = text.rstrip(FULL_STOPS)
    # range/cap construction identical to the surname match below, and
    # for the same two reasons: longest-first, and a len-1 cap that
    # makes the offset interior by construction (_split's contract). An
    # empty or one-character core caps below 1 and the loop is empty.
    cap = min(_longest_entry(tails), len(core) - 1)
    for length in range(cap, 0, -1):
        if core[-length:] in tails:
            return i, len(core) - length
    return None


# rules/W2: "a listed honorific glued to the end of the name's
# last name word splits off once and reads as a suffix." (history:
# decisions/W2)
# That the peel also reaches ACROSS a family comma is stated at
# rules/W3 instead, which is a tolerated rule since the
# 2026-09-01 comma demotion -- the crossing is what the parser does
# today, not something W2 promises. W3 also carries the reading of a
# period a listing leaves behind (decisions/cjk-comma-demotion,
# amended by decisions/cjk-full-stops): a period on a SEPARATE
# post-nominal word rides into the suffix and moves nothing ('様.'
# is post-nominal-strict and the scan steps past it as it steps past
# '様'), and since #323 a period glued to the honorific's OWN token
# rides with the honorific too -- _peel_site matches the tail through
# the trailing stop and cuts before it, so '田中さん.' divides where
# '田中さん' does, and '김민준씨.' where '김민준씨' does (both are
# case rows now; before 2026-09-10 they read as a title, measured
# 2026-09-05 and pinned by nothing, and for one commit of the #323
# branch the surname site read '김민준씨.' as 김 + 민준씨.). Neither
# reading is a promise; the step past the post-nominal word itself
# is W2's, above, and is.
def _one_case(state: ParseState) -> bool:
    """ParseState.one_case, asked here where no earlier stage did, as
    classify asks it: segment records the fact only where C2's flag
    asked for it (#613)."""
    if state.one_case is not None:
        return state.one_case
    return is_one_case(own_words(state.tokens, state.comma_offsets,
                                 state.lexicon._sets.maiden_markers)[0])


def _postnominal_behind_a_whole_name(state: ParseState) -> bool:
    """Whether the part after the comma is the postnominal part of a
    whole name, so the part before it is a name and not a surname --
    rules/C1's question, which group decides once the words are
    tagged (#613). This stage runs first, so it asks THAT decision, on
    the name as written: `_comma.decide` over a classified copy of the
    state, which is the one implementation of the question. A hand copy
    asked the vocabulary here until #613's /simplify pass, and was
    patched four times in review for drifting from decide (the ambiguous
    class's count, the numeral refusal, a suffix before the comma, the
    split 'Ph. D.'), each drift dividing a name decide then read as a
    family comma, or leaving whole one it read as a suffix comma.

    The copy costs a classify pass and a decision, so the callers ask
    only where the answer can change something: the peel once it has
    found a site, the division once there is a token it could divide
    (Latin and accented-Latin comma names never pay it)."""
    return (_comma.decide(classify(state)).structure
            is Structure.SUFFIX_COMMA)


def _peel_honorific_tail(state: ParseState,
                         postnominal: Callable[[], bool]) -> ParseState:
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
    tails = state.lexicon._sets.honorific_tails
    if not tails:
        return state
    # The NAME's runs: more than segments[0], never every segment. A
    # FAMILY comma splits the name across two runs and the honorific
    # glues to either side (#312); every other structure keeps the
    # name whole in segments[0], a trailing post-nominal under
    # NO_COMMA included, which the scan-back steps over. Flattening
    # SEGMENTS rather than state.tokens keeps the site off extracted
    # nickname and maiden content.
    #
    # rules/W3: "A part that is nothing but suffix words is not the
    # name's end: it is declined as the site, and the split-off falls
    # back to the part before the comma and takes the honorific there,
    # provided that part offers a site of its own."
    # The structure does not say whether segments[1] is name text, so
    # the run predicate is asked (`is_wholly_suffix`, not the plural of
    # `_is_post_nominal`, which vetoes an initial-shaped 'V.' and never
    # sees period_joined_vocab's 'J.씨'), with the case fact and policy
    # `_comma.decide` reads it with; an empty run is in
    # scope and adds no site. The second condition is there because
    # the predicate is circular at this site alone: a glued honorific
    # is itself suffix evidence. decisions/W2 (#319).
    site = _peel_site(state, state.segments[0], tails)
    if state.structure is Structure.FAMILY_COMMA:
        # Under a family comma both runs may be scanned. The comma's
        # decision is asked only where it can matter -- where scanning
        # one run and scanning both find different sites (#613's
        # /simplify: it is a classify pass and a decision)
        both = _peel_site(state, [j for seg in state.segments[:2]
                                  for j in seg], tails)
        if both != site and not postnominal():
            second = [state.tokens[j].text for j in state.segments[1]]
            # `one_case` is passed for the reason the field exists: the
            # credential lean is part of what "wholly suffix" MEANS since
            # #289, and a stage that asks the question without it gets a
            # different answer from `_comma.decide`, which reads the same
            # run with the fact in hand at group's head. Left out, 'Kim김민준씨, MA' read
            # 'MA' as name material, declined nothing, and scanned the
            # second run -- where the site is 'MA' itself, which carries no
            # listed tail -- so the person's own 씨 went unpeeled (family
            # 'Kim김민준씨') while 'Kim김민준씨, PhD' peeled it, one name in
            # two spellings parsed two ways (review round, #289/#516).
            # `segment` records the fact only where C2's flag asks for it,
            # so `_one_case` asks it here for every other name (#613).
            # the site test first: it is the cheaper half, and false
            # for every name whose part before the comma holds no glued
            # honorific, which spares those the case fact
            # one fact, asked for the lean and for the strict test's
            # initial veto alike (rules/T4, #727)
            if not (site is not None
                    and is_wholly_suffix(second, state.lexicon,
                                         state.policy,
                                         one_case=(case := _one_case(state)),
                                         letters_one_case=case)):
                site = both
    if site is None:
        return state
    i, offset = site
    # The tail carries a tag because this stage MANUFACTURED it. The
    # segmenter's neighbour test below needs to tell it from a token
    # somebody wrote, and no vocabulary question can: the two spellings
    # put the same word in the same place, and only the provenance
    # differs.
    return _split(state, i, (offset,), None, tail_tag=_PEELED_TAG)


#: The Thai vowels written after their consonant (U+0E30 to U+0E3A,
#: U+0E45), which no word opens with: where one follows a title, the
#: title's last letters belong to the word, so the peel falls back to a
#: shorter title ('นางสาวิตรี' is นาง + สาวิตรี) or keeps the word whole
#: ('นางิ', Nagi; 'นางาเซะ', Nagase), as it does behind a combining mark.
_AFTER_A_CONSONANT = frozenset(map(chr, (*range(0x0E30, 0x0E3B), 0x0E45)))


def _head_sites(state: ParseState) -> list[int]:
    """The tokens a glued title may open: the first word of the name and,
    after a family comma, the first word of the given part, each past
    any listed title written apart in front of it, alone or joined at its
    full stops ('รองศาสตราจารย์ นายแพทย์สมชาย', 'รศ.ดร. นายสมชาย')."""
    titles = state.lexicon._sets.titles
    runs = (state.segments[:2] if state.structure is Structure.FAMILY_COMMA
            else state.segments[:1])
    sites = []
    for run in runs:
        j = next((j for j in run
                  if not _all_titles(state.tokens[j].text, titles)), None)
        if j is not None:
            sites.append(j)
    return sites


def _all_titles(text: str, titles: frozenset[str]) -> bool:
    """Whether `text` is a listed title, whole or chunk by chunk between
    its full stops ('รองศาสตราจารย์', 'พ.อ.หญิง', 'รศ.ดร.'): a title
    written apart, which the site walk passes over; a word holding a
    name ('ดร.สมชาย') is a site, never passed over."""
    n = _normalize(text)
    if n in titles:
        return True
    chunks = [c for c in n.split(".") if c]
    return bool(chunks) and all(c in titles for c in chunks)


# rules/W6: "a title the vocabulary marks to peel, glued to the start of
# the name's first word, splits off once and reads as a title" (history:
# decisions/W6 (#317))
def _peel_title_head(state: ParseState) -> ParseState:
    """#317: split a listed title off the START of the name's first word
    -- นายสมชาย -> นาย + สมชาย -- the mirror of `_peel_honorific_tail`,
    licensed the same way: only a title written `attached` peels
    (`Lexicon.glued_titles`), the vocabulary carrying its own license.
    Longest first, ONE peel, and never off a word the vocabulary lists
    whole (`นายแพทย์`, which opens with `นาย`), nor where what is left
    opens with no letter, a Thai vowel written after its consonant
    (`_AFTER_A_CONSONANT`) taking the next shorter title instead. The head
    piece needs no tag: classify reads it as the listed title it is.

    T8's division ran on the word whole, before this peel, and found no
    chunk at its head (`อาจารย์ดร.สมชาย`), so a remainder still glued at
    a full stop (`ดร.สมชาย`) is divided here, as T8 divides the same
    word written apart; behind a family comma it stays whole, as T8
    leaves every word after a comma."""
    sets = state.lexicon._sets
    divide = False
    for i in reversed(_head_sites(state)):
        text = state.tokens[i].text
        low = text.lower()
        if len(low) != len(text):
            # a letter lowered into two: the offsets of `low` would not
            # be the text's
            continue
        cut, w = _peel_cut(low, state)
        if not cut:
            continue
        divide = divide or bool(state.segments and i in state.segments[0]
                                and GLUED_SHAPE.search(text, cut))
        state = _split(state, i, (cut,), None)
        if w in sets.title_modifiers:
            # a title only in a phrase peeled with its head behind it:
            # the head peels too, as written apart ('ว่าที่จ่าสิบตรีสมชาย',
            # 'ใจดี, ว่าที่ร.ท.วินัย')
            second, _ = _peel_cut(low[cut:], state)
            if second:
                state = _split(state, i + 1, (second,), None)
    return _divide_glued(state) if divide else state


def _peel_cut(low: str, state: ParseState) -> tuple[int, str]:
    """Where rules/W6's peel cuts the lower-cased word `low`, and the
    title it takes, or (0, '').

    Longest first; a title that would leave a Thai vowel or a mark at
    the opening falls back to the next shorter one ('นางสาวิตรี' is นาง +
    สาวิตรี), while one followed by anything else that opens no word peels
    nothing: a hyphen, a digit, the repetition mark ('นางสาว-สุดา',
    'นางสาวๆ')."""
    sets = state.lexicon._sets
    for w in _longest_first(sets.glued_titles):
        if len(w) >= len(low) or not low.startswith(w):
            continue
        end = len(w)
        if "." in w:
            # a title written short ends where T8 reads it end: past its
            # own stop, or behind a last chunk of two or more letters
            # (#1319: 'พล.ต.ต.สุรศักดิ์', 'พ.อ.หญิงวาสนา', never 'พ.ต.อ'
            # in 'พ.ต.อนุชา')
            e = dotted_title_end(low, 0, (w,))
            if e is None or e >= len(low):
                continue
            end = e
        elif low[end] == "." and end + 1 < len(low):
            end += 1
        if w in sets.title_modifiers and not low.startswith(
                title_prefixes(sets.titles), end):
            # a title only in a phrase (rules/H9) peels only with a
            # listed title behind it ('ว่าที่ร.ท.วินัย', 'ว่าที่ดร.สมชาย')
            continue
        nxt = low[end]
        if nxt in _AFTER_A_CONSONANT or unicodedata.category(nxt) == "Mn":
            continue
        return (end, w) if nxt.isalpha() and nxt != "\u0e46" else (0, "")
    return 0, ""


@functools.lru_cache(maxsize=16)
def _longest_first(heads: frozenset[str]) -> tuple[str, ...]:
    """The glued titles longest first, sorted once per vocabulary."""
    return tuple(sorted(heads, key=len, reverse=True))


def _split_candidate(state: ParseState) -> int | None:
    """The token `_split_surname_site` would try to divide, or None:
    asked on its own so a caller can learn cheaply that there is
    nothing to divide before asking anything costlier (#613's
    /simplify)."""
    scripts = state.policy.segment_scripts
    # an empty VOCABULARY deliberately does not bail here -- see below
    if not scripts:
        return None
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
        return None
    # A token that IS a surname never splits: a bare "남궁" must not
    # become 남 + 궁 just because the single-syllable surname also
    # matches -- there is nothing to split off, and a lone token's
    # role is the order resolution's call, stop or no stop. Asked here,
    # with the core the split reads (#323), so the comma gate in front
    # learns it before asking the comma's decision (#613's /simplify)
    if state.tokens[i].text.rstrip(FULL_STOPS) in state.lexicon._sets.surnames:
        return None
    return i


def _surname_pair(state: ParseState, i: int, core: str,
                  surnames: frozenset[str]) -> tuple[int, ...] | None:
    """rules/W5: "whose first two are each a listed single surname" --
    the offsets at which `_split` divides token `i` into its two
    surnames and, written undivided, the given name behind them: (1, 2)
    for four characters, (1,) for two with the given name after the
    space; or None where it holds no second single surname the family
    can take, by the length, script and order tests below (#845). Token
    `i`'s longest listed surname is its first character, so no listed
    compound opens it.

    Four characters written undivided, or two with a word of two
    written after the space: a Han given name is nearly always one or
    two characters, and a three-character name is nearly always a
    single surname before a two-character given name (李林伟, and
    `李林 伟` written with a stray space), the reason no married pair is
    listed as a compound.

    Only where the name will be read family-first, since only there is
    the first surname the family for the second to join: every word of
    the name segment but the post-nominals ending it written in the
    scripts assign's order resolution keys (rules/W4), resolving to an
    entry, or failing one, to a declared order, that puts the family
    first -- the resolution assign makes over its name pieces, asked of
    the words before titles are known. A word in another
    script, a Latin title included, keeps W1's division, which reads
    the same under any order, so the stage never cuts a name the order
    then reads otherwise. History: decisions/W5 (#845)."""
    # the length tests first: they are C-level, and refuse a
    # three-character token, the usual single surname and given name,
    # before the script walk below
    if core[1] not in surnames or len(core) not in (2, 4):
        return None
    run = state.segments[0]
    at = run.index(i)
    if len(core) == 2 and (
            at + 1 == len(run)
            or len(state.tokens[run[at + 1]].text.rstrip(FULL_STOPS)) != 2):
        return None
    # post-nominals ending the name, a peeled honorific among them, are
    # no name pieces of assign's, so they key no order (王李小明さん,
    # 王李小明 PhD); anything before them does
    end = len(run)
    while (end > at + 1
           and (_PEELED_TAG in state.tokens[run[end - 1]].tags
                or _is_post_nominal(state, run[end - 1]))):
        end -= 1
    found: set[Script] = set()
    for j in run[:end]:
        script = effective_script(state.tokens[j].text)
        if script is None:
            return None
        found.add(script)
    if resolve_script_set(found) is not Script.HAN:
        return None
    order = next((o for s, o in state.policy.script_orders
                  if s is Script.HAN), state.policy.name_order)
    if order[0] is Role.GIVEN:
        return None
    if len(core) == 4:
        return (1, 2)
    return None if _is_post_nominal(state, run[at + 1]) else (1,)


def _split_surname_pair(state: ParseState, i: int,
                        splits: tuple[int, ...]) -> ParseState:
    """Token `i` divided at `_surname_pair`'s cuts into its two surnames
    and, unspaced, the given name behind them, the second surname
    tagged for post_rules to read as the family's second unit. No
    report here: whether the pair is read is post_rules' decision,
    under the order the name is read in, so it reports there
    (mechanisms.md#AMBIGUITY-AT-THE-DECISION-SITE)."""
    state = _split(state, i, splits, None)
    second = state.tokens[i + 1]
    tokens = list(state.tokens)
    tokens[i + 1] = copy_with(second, tags=second.tags | {SURNAME_PAIR_TAG})
    return copy_with(state, tokens=tuple(tokens))


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
    i = _split_candidate(state)
    if i is None:
        return state
    token = state.tokens[i]
    text = token.text
    surnames = state.lexicon._sets.surnames
    # The vocabulary match reads the token's CORE (#323). Without it
    # the stop WAS the remainder: '김.' matched its own head and became
    # 김 + '.'; the stop rides with the remainder instead, so '김민준.'
    # divides as 김 + '민준.'. A leading stop never reaches THIS site --
    # the classification fold in front rstrips too
    # (_vocab._normalized_for_script) and hides such a token before it
    # arrives -- while the peel above has no such gate in front of it
    # and its own rstrip is what does the work there.
    core = text.rstrip(FULL_STOPS)
    # Longest-first (compound-before-single falls out of it), capped
    # so the remainder is never empty. Direct membership, no
    # _normalize: the script gate admits only CJK text, and a CJK
    # entry's stored form is its NFC composition with no case or
    # edge-stop change (#322) -- so an entry AUTHORED in NFD is
    # composed on the way in, raw NFD input matches nothing here, and
    # the name goes unsplit, the no-split NFD degradation that
    # decisions/W1's 2026-07-29 NFD bullet (ja amendment 1a) accepts. An empty vocabulary skips the match rather
    # than bailing the stage (_longest_entry's max() has nothing to
    # take): a surname-less lexicon declines every token, which is
    # exactly the condition the segmenter is consulted on, so an early
    # bail would make a configured segmenter silently inert under
    # Lexicon.empty() -- the JA pack's own shape.
    matches: list[int] = []
    if surnames:
        cap = min(_longest_entry(surnames), len(core) - 1)
        matches = [length for length in range(cap, 0, -1)
                   if core[:length] in surnames]
    if matches:
        take = matches[0]
        if take == 1:
            pair = _surname_pair(state, i, core, surnames)
            if pair is not None:
                return _split_surname_pair(state, i, pair)
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
    # it says nothing about where the CJK name splits, so "Dr 小明日,
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
    # a neighbour in an East Asian script, not a Cyrillic word, whose
    # classification keys only a declared order (#1237)
    if any(j != i and effective_script(state.tokens[j].text)
           not in (None, Script.CYRILLIC)
           and _PEELED_TAG not in state.tokens[j].tags
           for j in state.segments[0]):
        return state
    # No try/except around the call: rules/A1's Accepted clause
    # ("a user-supplied segmenter's own error, which propagates"). The
    # two checks below are that same doctrine, curated, and they are
    # where the line this module draws is easiest to state:
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
    # The CORE, not the raw token (#323): handed the raw token, a
    # segmenter answering len-1 would make the stop a piece of its own
    # ('田中太郎' + '。'), where against the core the trailing stops
    # ride with the last piece -- '山田太郎.' answered at 2 divides as
    # 山田 + '太郎.'.
    answer = state.segmenter(core)
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
    # The bound is the CORE's length, the string the segmenter was
    # actually handed: an offset it could not have derived from its own
    # input is the same author bug whether or not `text` is longer.
    if answer.splits[-1] >= len(core):
        raise ValueError(
            f"segmenter returned splits beyond the token: last offset "
            f"{answer.splits[-1]}, the segmenter was given "
            f"{len(core)} characters")
    conf = answer.confidence
    detail = None
    if conf is not None and conf < _SEGMENTER_CONFIDENCE_FLOOR:
        reading = " + ".join(map(repr, _pieces(text, answer.splits)))
        detail = (f"{text!r} splits as {reading} on a segmenter answer "
                  f"scoring {conf:.2f}, under the "
                  f"{_SEGMENTER_CONFIDENCE_FLOOR} confidence floor")
    return _split(state, i, answer.splits, detail)


# rules/T8: "the word reads as it does with a space there" -- the part
# before any comma, where the division acts (decisions/T8 (#1230, #1235))
def _divide_glued(state: ParseState) -> ParseState:
    """Every word of the part before the first comma divided where
    `_vocab.glued_cuts` finds a chunk read alone meeting a name, last
    word first, so the indices still to visit do not move."""
    head = state.segments[0]
    lexicon = state.lexicon
    # the words as written, before any of them divides: the report reads
    # the words after its own, which may have divided already
    texts = [state.tokens[j].text for j in head]
    for k in range(len(head) - 1, -1, -1):
        i = head[k]
        text = texts[k]
        # a C-level test first, so a word with no stop pays no frame
        if GLUED_SHAPE.search(text) is None:
            continue
        cuts = glued_cuts(text, lexicon)
        if not cuts:
            # rules/T8: "a saint particle glued to a name is one name
            # word" -- save as the last name word of the part behind
            # another, where it divides and the particle opens the
            # surname as written apart (rules/P10, 'Juan dela Cruz
            # Sta.Maria'; decisions/T8 (#1071))
            saint = glued_saint_cut(text, lexicon)
            if (saint is not None
                    and _a_name_before(texts[:k], state)
                    and _only_post_nominals(texts[k + 1:], state)
                    and _ends_with_the_family(state)):
                state = _split(state, i, (saint,), None)
            continue
        state = _split(state, i, cuts, None)
        if _ends_the_name(text, cuts, texts, k, state):
            # initials glued to the word ending the name, behind a word
            # to spare: S3 would have read the whole as a credential by
            # its shape, and the reading not taken is still that one
            # ('John Smith B.Eng', 'Ahmed Ali M.Hassan', 'John Smith
            # A.Brown PhD')
            state = copy_with(state, ambiguities=(
                *state.ambiguities, PendingAmbiguity(
                    AmbiguityKind.SUFFIX_OR_NAME,
                    f"{text!r} ending the name may be a credential "
                    f"written short; read as ",
                    (i + len(cuts),), field_tail="",
                    alternative=PendingReading(
                        ReadingKind.CREDENTIAL, ReadingSource.SHAPE,
                        Role.SUFFIX))))
    return state


def _only_post_nominals(texts: Sequence[str], state: ParseState) -> bool:
    """Whether every word in `texts` is suffix vocabulary, an acronym
    looked up without its stops ('Ph.D.' as 'phd'), up to a maiden
    marker, whose clause holds no word of the name ('Juan dela Cruz
    Sta.Maria née Jones'): what may follow the last name word of a
    part."""
    sets = state.lexicon._sets
    for j, later in enumerate(texts):
        n = _normalize(later)
        # a marker of one word or two ('née', 'z domu'), with a word after
        # it: a marker ending the text is no clause ('John Smith Sta.Ana
        # née' reads 'née' as a name word)
        if (n in sets.maiden_markers and j + 1 < len(texts)) or (
                j + 2 < len(texts) and f"{n} {_normalize(texts[j + 1])}"
                in sets.maiden_markers):
            return True
        if (n not in sets.suffix_words
                and n.replace(".", "") not in sets.suffix_acronyms):
            return False
    return True


def _a_name_before(texts: Sequence[str], state: ParseState) -> bool:
    """Whether the word right before a glued saint word is a name, the
    surname the particle cannot then be part of a title with: no title
    of any kind (listed, gated, a modifier or a style), no connective,
    nor titles glued at their stops; and no connective earlier in the
    part, which joins a title phrase or names ('Mr and Mrs St.Clair',
    'Dean of Students St.Clair', 'Associate Dean St.Clair' keep their
    word whole, rules/T8)."""
    if not texts:
        return False
    sets = state.lexicon._sets
    for before in texts:
        if _normalize(before) in sets.conjunctions:
            return False
    last = _normalize(texts[-1])
    if (last in sets.titles or last in sets.titles_ambiguous
            or last in sets.title_modifiers or last in sets.title_styles):
        return False
    return (period_joined_vocab(texts[-1], state.lexicon) != "title"
            or bool(glued_cuts(texts[-1], state.lexicon)))


def _ends_with_the_family(state: ParseState) -> bool:
    """Whether the part's last name word is the family's: before a
    family comma under every order, the comma naming the surname, and
    otherwise under an order that ends the name with the family (a
    suffix comma reads as no comma, `_postnominal_behind_a_whole_name`
    asking the comma as group will decide it)."""
    if (state.structure is Structure.FAMILY_COMMA
            and not _postnominal_behind_a_whole_name(state)):
        return True
    return state.policy.name_order[-1] is Role.FAMILY


def _a_word_to_spare(texts: Sequence[str], state: ParseState) -> bool:
    """Whether a word of `texts` is no unambiguous title, nor titles
    glued at their stops with no name after them ('Prof.Dr.'): a word
    of the name before the last one, which a title is not ('Mr.
    St.Clair', 'Dr. A.Smith')."""
    sets = state.lexicon._sets
    lexicon = state.lexicon
    return any(_normalize(before) not in sets.titles
               and (period_joined_vocab(before, lexicon) != "title"
                    or glued_cuts(before, lexicon))
               for before in texts)


def _ends_the_name(text: str, cuts: tuple[int, ...], texts: Sequence[str],
                   k: int, state: ParseState) -> bool:
    """Whether T8's division of `texts[k]` took the credential S3's
    shape read: initials (a letter, a run of them, a digraph) before a
    name that is no suffix word or acronym, which reports itself
    (rules/S11, 'Pedro M.Filho'); the last name word of the part, only
    post-nominals after it; a word before it that is no unambiguous
    title; and no family comma's surname, which S3 never read so, the
    comma asked here as group will decide it ('John Smith A.Brown,
    PhD' is a suffix comma, 'Smith A.Brown, John' a family one)."""
    sets = state.lexicon._sets
    starts = (0, *cuts[:-1])
    if not all(is_initial_chunk(text[a:b - 1])
               for a, b in zip(starts, cuts)):
        return False
    name = _normalize(text[cuts[-1]:])
    if name in sets.suffix_words or name in sets.suffix_acronyms:
        return False
    if not _only_post_nominals(texts[k + 1:], state):
        return False
    # a title, or titles glued at their stops with no name after them, is
    # no word to spare ('Prof.Dr. A.Brown' as 'Prof. Dr. A.Brown'); a
    # glued word that divides holds a name ('Dr.John J.Smith')
    if not _a_word_to_spare(texts[:k], state):
        return False
    return (state.structure is not Structure.FAMILY_COMMA
            or _postnominal_behind_a_whole_name(state))


# rules/W1: "an undivided word in the family position of a name
# written in an activated script divides after a recognized surname,
# the longest recognized surname first; where the vocabulary
# recognizes nothing, an optional segmenter may divide instead"
# rules/W3: "under a family comma the pre-comma text is the
# family by declaration and never divides, and the post-comma side
# is given text with no family to find" (history: decisions/W3)
def script_segment(state: ParseState) -> ParseState:
    if state.segments and GLUED_SHAPE.search(state.original):
        state = _divide_glued(state)
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
        # which T8's division above divides where a name follows the
        # stop, and _vocab.period_joined_vocab classifies as one token
        # where none does -- a different mechanism, and no peel site
        # either way. A glued Latin POST-nominal is spelled the
        # same way, so it reaches that same mechanism rather than
        # nothing: period_joined_vocab reads "Smith.Jr." by its shape,
        # 'smith' being no chunk that counts (#1131), and position
        # decides whether that reading lands -- "John Anderson
        # Smith.Jr." gives suffix "Smith.Jr.", reported, while
        # "Smith.Jr. Anderson" gives given "Smith.Jr.", family
        # "Anderson" (measured 2026-11-07). Whatever it decides, this
        # bail is what settles the question here: it
        # returns above all of it, so no ASCII input reaches the peel.
        return state
    if not state.segments:
        return state
    # The glued-title peel, the tail peel's mirror, runs in front of it
    # and of the gates below for the tail peel's reason, which follows.
    heads = state.lexicon._sets.glued_titles
    if heads:
        # the C-level test first, over the words a site can be, written
        # as a loop rather than any() over a generator, whose frames a
        # name holding no word that opens with a glued title would pay
        # (rules/W6)
        prefixes = tuple(heads)
        for run in state.segments[:2]:
            for j in run:
                if state.tokens[j].text.lower().startswith(prefixes):
                    state = _peel_title_head(state)
                    break
            else:
                continue
            break
    # #312: the peel runs in front of both gates below, because both
    # answer where a name divides into surname and given, and the peel
    # does not ask that. It asks whether a token ends in a word that
    # can never end a name, and a comma or a dot elsewhere in the
    # string does not change the answer. Placing it above the block
    # also keeps a future segmentation gate from silently capturing
    # it: a new gate lands with its siblings, below.
    # The comma's decision, asked lazily: the peel asks it only once it
    # has a site, the division below only once there is a token to
    # divide (#613's /simplify), each on the state it acts on.
    state = _peel_honorific_tail(
        state, lambda: _postnominal_behind_a_whole_name(state))
    if (state.structure is Structure.FAMILY_COMMA
            and (_split_candidate(state) is None
                 or not _postnominal_behind_a_whole_name(state))):
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
