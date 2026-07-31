"""Stage: script_segment (#271, #272, #308).

Consumes: tokens, segments, structure, interpunct_offsets, segmenter.
Produces: tokens, by two independent splits into sub-slices -- a
listed honorific peeled off the END of the name part's last
non-post-nominal token, and the first activated-script token of the
name segment split into n+1 -- segments (index runs remapped past the
insertions), ambiguities (indices likewise remapped, plus a
SEGMENTATION report when more than one split was vocabulary-supported,
or when a segmenter's answer scored under the confidence floor).
Reads: Policy.segment_scripts, Lexicon.surnames,
Lexicon.honorific_tails, ParseState.segmenter.

Unspaced CJK names give tokenize no separator to find, so this stage
inserts the missing token boundary by vocabulary: the first token
written in an activated script is matched longest-first against
Lexicon.surnames, and a hit splits it in two. Compound-before-single
("夏侯惇" is 夏侯 + 惇, though 夏 is itself a surname) falls out of
longest-first. The split makes sub-slices of the one token, rewriting
nothing -- spans still index the original exactly, so the anti-#100
invariant holds by construction.

A second, independent split runs first (#308): a listed honorific
glued to the END of the name part's last non-post-nominal token is
peeled off as its own token -- 田中さん -> 田中 + さん -- so that
suffix classification can claim it and the surname match or segmenter
consult below sees the name rather than the name plus an honorific. It
is gated by the FAMILY comma and by 间隔号 but NOT by segment_scripts:
the vocabulary of tails is licensed by the entries themselves, each of
which can never end a name, so no per-script trust question arises. A
suffix comma does not gate it -- "Dr 김민준씨, Jr." peels within its
name part like any other.

Where the VOCABULARY declines -- no prefix matched -- an optional
Parser(segmenter=...) gets the token (#272 amendment 2026-07-29).
Vocabulary first, segmenter on decline, so parser_for(ZH, JA,
segmenter=...) composes MECHANICALLY: a listed surname is a
dictionary certainty and wins, and the segmenter takes what is left.
Composing is not a free lunch, and the docs qualify it where they
show the stack: the zh pack's own mis-split warning survives
unchanged, because a Japanese kanji name opening on a listed Chinese
surname never reaches the segmenter at all -- 高橋一郎 still splits
高 + 橋一郎 under ZH+JA, exactly as it does under ZH alone. The two
packs are corpus ALTERNATIVES, one per corpus; stacking them is for
genuinely mixed data that accepts that trade. Its Segmentation may
cut anywhere and any number of times, which is why the split path
below takes n cuts. One precondition guards it that the vocabulary
has no twin of: a segmenter answers where an UNDIVIDED name divides,
so it is consulted only when the gated token is the name part's ONLY
script-written one -- "山田 太郎" was divided by its writer and must
not have its family divided again (a Latin title or suffix draws no
such boundary either, and effective_script gates those out before the
test is reached). The neighbour test reads effective_script -- merely
non-None -- and exempts exactly one token: the tail the peel above
MANUFACTURED (#308), which is a boundary nobody drew. A SPACED
honorific is not exempt, and the distinction is provenance rather
than vocabulary: glued 山田太郎様 was written undivided, while "佐藤
氏" carries a boundary its writer typed. Not that the writer thereby
declared 佐藤 a unit -- in "山田太郎 様" the unit they drew is the
whole name -- but that at this position a spaced honorific cannot be
told apart from a spaced name ELEMENT, so the precondition counts it
rather than guess. The trade that buys is measured: counting spaced
honorifics keeps four real surnames whole (佐藤 氏, 田中 様, 鈴木
先生, 中村 教授, all four divided bare under the JA pack) and costs
the one division 山田太郎 様. A segmenter's own exceptions
PROPAGATE -- the single declared exception to parse totality (locales
spec section 4): a user-supplied callable's error is a user-code
error, not a content error.

Placed AFTER segment, on the comma doctrine that script-conditional
behavior is ignored where a comma already decides the family (the
rule script_orders follows): under FAMILY_COMMA the pre-comma text IS
the family by declaration, and splitting it would invent a boundary
the writer explicitly did not draw -- "남궁민수, 지훈" must render
family "남궁민수", not "남궁 민수". That doctrine is about the input's
structure, not the split's source, so it covers the segmenter
identically: the opt-out runs before either is consulted. The
post-comma side is given-name text, no surname site either, so that
structure opts out whole.
NO_COMMA and SUFFIX_COMMA still split, within segments[0] (the name
part) only. Running after segment costs the index remaps below;
running BEFORE it would have made the comma structure itself depend
on the split -- segment's suffix-comma rule needs more than one word
before the comma, so a pre-split "김민준, Jr." would have changed
structure on vocabulary alone. As written it stays FAMILY_COMMA,
which is why the SUFFIX_COMMA path needs a second word ("Dr 김민준,
Jr.") to be reachable at all.

Activation is per script because the AMBIGUITY is per script
(amendment 2026-07-27): HANGUL is on by default (hangul is
unambiguously Korean, and its surname set is closed and
default-shipped), while HAN is opt-in via locales.ZH -- a Chinese
surname list corrupts Japanese names ("高橋一郎" must not split as
高 + 橋一郎). Japanese divides through the segmenter path below under
locales.JA, not through this table's vocabulary.
The gate resolves each token through effective_script, the same
function order resolution uses, so kana-licensed composites (高橋みなみ
-> HIRAGANA) gate in under the JA pack's HIRAGANA entry while
pure-katakana tokens (-> KATAKANA, in no activation set by design --
they are predominantly transcribed foreign names) never do.
Only the FIRST activated-script token is considered, match or no
match: family-first traditions put the surname at the front of the
name, and a match deeper in the token stream would be a given name or
an ordinary word, not a surname site. Where that first token is one
the vocabulary reads as a POST-NOMINAL, the stage DECLINES rather than
looking further along: an honorific is not part of the name, and a
surname leads, so an honorific in the surname's own position means
there is no surname here to find. Deciding includes deciding that.
Looking further would reach the given name the rule already refuses to
touch -- "양 지훈" would split its own given name, 지 being listed too
-- while declining leaves the peel's manufactured tail intact, since
in "Anderson선생님" that tail is the first and only script-written
token (선생님 opens on the listed surname 선, and a spaced
"Anderson 선생님" was mis-split that way before the peel existed).
"""
from __future__ import annotations

import dataclasses
import functools

from nameparser._pipeline._state import (
    ParseState, PendingAmbiguity, Structure, WorkToken,
)
from nameparser._pipeline._vocab import effective_script, is_suffix_strict
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
           detail: str | None) -> ParseState:
    """Cut token `i` at every offset in `splits`, recording `detail` as
    a SEGMENTATION report when there is one.

    The offsets arrive non-empty, ascending and interior whatever chose
    them. From a segmenter: non-empty is the caller's own check,
    strictly ascending with each >= 1 is Segmentation.__post_init__'s,
    and the last offset is < len(text) -- checked by the caller. From
    the vocabulary: the single offset is >= 1 and < len(text) by the
    range(cap, 0, -1) construction and its len-1 cap.

    The ONE split path: the vocabulary hit is the single-offset case
    and the segmenter's answer the general one, so neither can drift
    from the other's index arithmetic."""
    token = state.tokens[i]
    base = token.span.start
    parts: list[WorkToken] = []
    start = 0
    for piece in _pieces(token.text, splits):
        end = start + len(piece)
        parts.append(dataclasses.replace(
            token, text=piece, span=Span(base + start, base + end)))
        start = end
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
    and does not peel, while "田中さん II" steps over II and does.
    Swapping in is_suffix_lenient fails no test; this clause is the
    record instead.

    Suffixes only, deliberately. Should a CJK entry ever join titles,
    the surname site would want it excluded while the peel site must
    not: a title never trails, so widening the peel's scan-back would
    move it off the real last name token. Split the predicate then, not
    before."""
    return is_suffix_strict(state.tokens[i].text, state.lexicon)


def _peel_honorific_tail(state: ParseState) -> ParseState:
    """#308: split a listed honorific off the END of the name part's
    last NON-POST-NOMINAL token -- 田中さん -> 田中 + さん -- and let
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
    only keeps the offset interior for _split. And segments[0] is
    reachable while empty -- a leading comma yields one -- so the scan
    that returns None where the outright index would raise removes an
    unpinned reliance on the FAMILY_COMMA gate landing first.

    WHICH run is scanned is a separate decision, and the one a reader
    is likeliest to undo: segments[0], never state.tokens. The two
    agree under NO_COMMA except where extract_delimited has already
    claimed a token, which is still in the stream here with only its
    role set -- so "김민준씨 (Jimmy)" is the input that tells them
    apart. See the note above the segment lookup in script_segment.

    That last token is the last of the NAME PART, which under NO_COMMA
    reaches into a maiden clause: maiden tokens are still main-stream
    here (extract_delimited has masked only bracketed content), so
    "김민준 née 박씨" peels 씨 off the MAIDEN name 박씨 and hands it to
    the person's suffix list -- "née Ms. Park". Intended rather than
    incidental in that direction: the honorific is the reader's
    regardless of which of her names it was glued to, and a
    name-part-final honorific is exactly what this peels.

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
    i = next((j for j in reversed(state.segments[0])
              if not _is_post_nominal(state, j)), None)
    if i is None:
        return state
    text = state.tokens[i].text
    # range/cap construction identical to the surname match below, and
    # for the same two reasons: longest-first, and a len-1 cap that
    # makes the offset interior by construction (_split's contract).
    cap = min(_longest_entry(tails), len(text) - 1)
    for length in range(cap, 0, -1):
        if text[-length:] in tails:
            state = _split(state, i, (len(text) - length,), None)
            # Tag the tail this stage just MANUFACTURED. The segmenter's
            # neighbour test below needs to tell it from a token
            # somebody wrote, and no vocabulary question can: the two
            # spellings put the same word in the same place, and only
            # the provenance differs.
            tail = state.tokens[i + 1]
            tokens = (state.tokens[:i + 1]
                      + (dataclasses.replace(
                          tail, tags=tail.tags | {_PEELED_TAG}),)
                      + state.tokens[i + 2:])
            return dataclasses.replace(state, tokens=tokens)
    return state


def script_segment(state: ParseState) -> ParseState:
    if state.original.isascii():
        # spans index the original exactly (the anti-#100 invariant),
        # so an ASCII original has only ASCII tokens: nothing here is
        # in any script's ranges. It also short-circuits the PEEL,
        # which has no script gate of its own -- so a caller-configured
        # ASCII tail never fires, and one non-ASCII character anywhere
        # in the name switches it on. Correct for the CJK vocabulary
        # that ships, stated because honorific_tails is public: see
        # that field's own note.
        return state
    if not state.segments:
        return state
    if state.structure is Structure.FAMILY_COMMA:
        return state            # the comma already drew the boundary
    if state.interpunct_offsets:
        # #298: a 间隔号-divided name is a transcription -- its pieces
        # are syllable groups, not surname+given, so neither the
        # vocabulary nor the segmenter applies (codepoint-scoped: the
        # nakaguro records nothing and gates nothing, spec decision 5).
        # State-global like the FAMILY_COMMA gate above: a marker
        # anywhere in the name reads the WHOLE name as a transcription
        # listing, so even an un-dotted hangul token beside a dotted
        # one stays whole.
        return state
    # #308: the honorific peel runs after the structural gates above
    # (a FAMILY-comma or dot-divided name opts out of this stage
    # whole; a suffix comma does not -- its name part still peels)
    # but BEFORE the activation gate below, and independently of it --
    # 田中さん must peel under the DEFAULT policy, where HAN is in no
    # activation set. The activation gate is about which
    # scripts a SURNAME VOCABULARY may be trusted to divide; the peel
    # asks nothing of the remainder, only whether the token ends in a
    # word that can never end a name.
    state = _peel_honorific_tail(state)
    scripts = state.policy.segment_scripts
    # an empty VOCABULARY deliberately does not bail here -- see below
    if not scripts:
        return state
    # segments[0] is the NAME part under both remaining structures
    # (everything, under NO_COMMA); later segments are suffixes. Its
    # members are main-stream token indices by construction, so
    # extracted nickname/maiden content is unreachable from here.
    # For the surname site that is merely tidy -- the first
    # script-written token is the same either way. For the PEEL above
    # it is load-bearing, and iterating state.tokens instead is a
    # silent regression rather than a refactor: extracted content is
    # still IN the token stream at this stage (only its role is set),
    # so "김민준씨 (Jimmy)" would give the scan-back Jimmy as its site,
    # which is no post-nominal to step over and ends in no tail, and
    # the peel would be lost. Pinned by the case row of that name.
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
    # No try/except around the call: the module docstring's totality
    # exception. The two checks below are that same doctrine, curated,
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
