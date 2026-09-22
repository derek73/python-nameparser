"""Shared vocabulary predicates for pipeline stages.

Text-level tests used by more than one stage; piece-level ones live
in _pieces, the sibling layer over tokens-plus-tags. All take
normalized-or-raw text explicitly and no state, with the departures
named below.

is_wholly_suffix departs from that shape twice, deliberately. It is
RUN-level rather than text-level, because the question it answers is
genuinely about a run: the Ph./D. merge spans two tokens, so no
per-token predicate composed with all() can express it. And it takes
the Policy OBJECT, where delimiter_cores takes a pre-extracted
frozenset so its caller hands in one field rather than the config --
is_wholly_suffix needs TWO policy fields (lenient_comma_suffixes and
extra_suffix_delimiters), and threading both past every caller costs
more than the config parameter saves. Still no state: Policy is frozen
config, not pipeline state.

maiden_marker_run is run-level for the first of those reasons and not
the second: a maiden marker may be a PHRASE ('z domu'), so how far one
reaches is a question about a run of words that no per-word membership
test can answer, and the vocabulary reaches it as a plain frozenset
field like every other predicate here.

tag_marker_runs is the third departure, and the reason this module also
imports _state (WorkToken, comma_bucket): deciding which tokens open a
maiden-marker RUN needs each token's role and span, not its text alone,
because a run must not cross a role change or a comma. It moved here
from classify (#289/#516) so _pieces.own_words -- which may import
only _state and _vocab (tests/v2/test_layering.py) -- can call the
SAME function classify does rather than approximating it with a
text-only walk. Two callers building a map from the same tokens with
the same function cannot disagree, which a from-scratch approximation
could (measured: 'ANNA z Nowak, MD' flips the one-case verdict when
the approximation and the real run-completion test disagree on
whether 'z' opens a run that completes).

Layering: imports _lexicon, _policy, and _pipeline._state (WorkToken,
comma_bucket -- read-only, never a whole ParseState).
"""
from __future__ import annotations

import functools
import re
import unicodedata
from collections.abc import Callable, Iterable, Sequence
from typing import Literal

from nameparser._lexicon import (
    FULL_STOPS, Lexicon, _VOCAB_FIELDS, _normalize,
)
from nameparser._policy import (Policy, Script, _JA_SCRIPTS, _NO_INITIALS,
                                _SCRIPT_RANGES, _script_matcher)
from nameparser._pipeline._state import WorkToken, comma_bucket

# Ported verbatim from v1 (nameparser/config/regexes.py "initial") minus
# its empty-string alternative -- WorkToken text is never empty. Kept in
# sync by hand; layering forbids importing the config package here.
# "Verbatim" is a promise about the PATTERN, not about the predicate:
# since #320 is_initial is this SHAPE test ANDed with a repertoire test
# (in_initialless_script, below), so _INITIAL.fullmatch(text) and
# is_initial(text) are no longer the same question -- '씨.' answers yes
# to the first and no to the second. Call is_initial; the bare pattern
# is not the thing to ask. The narrowing lives in the predicate
# precisely so this copy can stay exactly as verbatim as it ever was
# -- REGEXES["initial"] is public v1 API and cannot narrow, and the
# only difference between the two remains the empty alternative noted
# above (config's `?`), which test_regex_sync splices back in.
_INITIAL = re.compile(r"^(\w\.|[A-Z])$")

# Ported verbatim from v1 (nameparser/config/regexes.py
# "period_not_at_end") -- layering forbids the config import; keep in
# sync by hand.
_PERIOD_NOT_AT_END = re.compile(r".*\..+$", re.I)

# The fix_phd credential pair ('Ph.' + 'D.' as adjacent tokens), shared
# by is_wholly_suffix below and group's merge (v1 extracted the
# credential pre-parse; the predicate and the stage must agree on the
# pattern).
PH = re.compile(r"^ph\.?$", re.IGNORECASE)
D = re.compile(r"^d\.?$", re.IGNORECASE)

# The codepoint table lives in _policy beside Script -- one copy
# importable from the pipeline and the locale packs alike; everything
# here DERIVES from it. (single_script's sweep was first written
# per-char on the _EMOJI_RANGES precedent in _tokenize.py, on the
# theory that a range test needs no regex; measured at token scale the
# compiled regex wins by 3-9x, and by roughly 70x on long tokens.)
# Derived, never hand-written -- even the class construction goes
# through the shared factory: one wholly-of predicate per script, in
# the table's key order -- the FIRST-covering-entry rule _classify
# documents.
_SCRIPT_MATCHERS: dict[Script, Callable[[str], bool]] = {
    script: _script_matcher(script, whole=True)
    for script in _SCRIPT_RANGES
}

# The whole-token matcher over _policy's _JA_SCRIPTS union, backing
# effective_script's kana license.
_wholly_ja = _script_matcher(*_JA_SCRIPTS, whole=True)

# The repertoire half of is_initial (_policy._NO_INITIALS), kept apart
# from _INITIAL's SHAPE half so the pattern itself stays v1-verbatim
# and its three copies stay pinned by tests/v2/test_regex_sync.py.
# contains-any, not whole=True: the shape half has already admitted the
# trailing period, so the text reaching here is '씨.' rather than '씨'
# and a wholly-of match would be False for every case this exists for.
# The second caller, is_title_shaped below, admits two or more
# characters, so contains-any there means one CJK character anywhere
# vetoes the whole word -- 'Kim김.' is refused as a title along with
# '田中.' -- and that is deliberate: a word carrying a script with no
# abbreviations is not wearing an abbreviation's period.
in_initialless_script = _script_matcher(*_NO_INITIALS, whole=False)


# H2's own shape, text-level: an unlisted period-marked abbreviation,
# two or more letters, one trailing period. Moved here from _pieces
# (#289/#516, quality-review finding) so _vocab.name_word_count can
# ask the SAME question _pieces.is_leading_title asks -- measured
# divergence before the move: 'Dr. Smith, Ed' (LISTED title 'Dr.') and
# 'Xyz. Smith, Ed' (UNLISTED, H2-shaped) both read family 'Dr.
# Smith'/'Xyz. Smith', given 'Ed' at the peel, because is_leading_title
# reads H2's shape and a bare `folded in lexicon.titles` lookup does
# not -- but name_word_count's OWN count disagreed: 'Xyz.' counted as
# a name word where 'Dr.' did not, so 'Xyz. Smith, Ed' alone flipped
# the comma structure to a credential run
# (mechanisms.md#ONE-PREDICATE-PER-QUESTION).
#
# Ported verbatim from v1 (nameparser/config/regexes.py
# "period_abbreviation") -- layering forbids the config import; keep
# in sync by hand (tests/v2/test_regex_sync.py, which reaches this
# object through `_pieces._PERIOD_ABBREV`, an IMPORT of this one, not
# a second definition -- the sync test's target name did not move).
_PERIOD_ABBREV = re.compile(r'^[^\W\d_]{2,}\.$')


# rules.md#H2: "an abbreviation opening the part of the name that
# carries the given name — the whole name, or the part after a
# family comma — reads as a title even when unlisted"
# (history: decisions.md#H2)
def is_title_shaped(text: str) -> bool:
    """Whether TEXT wears H2's shape alone -- vocabulary-free, the
    LISTED half being a separate lookup at each caller's own site
    (is_title_piece/lexicon.titles). `name_word_count` below is the
    only CALLER; `_pieces.is_leading_title` asks the same question
    but keeps this body inline, its path being hot (every leading
    piece of every parse) where this one is cold (comma names only)
    -- the measured figure lives at that inline copy and is not
    restated here, two homes for one measurement being how they come
    to disagree. Touch one, touch both:
    `test_pieces.test_is_title_shaped_and_is_leading_title_agree`
    runs both over the union of the two example tables, so the
    agreement is checked rather than asserted in prose
    (mechanisms.md#ONE-PREDICATE-PER-QUESTION).

    The shape reads a Latin convention: a period marks an
    abbreviation. Scripts with no initials have no period
    abbreviations either (_policy._NO_INITIALS, the #320 veto
    is_initial carries), so a CJK word wearing a period is a name
    word, not a title -- a lone '田中.' is the family name (#323).
    `_PERIOD_ABBREV` stays ASCII-period only: a word wearing '。' never
    matches it, and the veto is what makes the ASCII spelling agree.
    ASCII text can carry no _NO_INITIALS character (every range sits
    above U+3000), so the C-level test declines before the regex
    search runs -- four frames per unlisted-abbreviation opener per
    parse, this running four times per piece.
    """
    return (bool(_PERIOD_ABBREV.match(text))
            and (text.isascii() or not in_initialless_script(text)))


def is_initial_shaped(text: str) -> bool:
    """v1's is_an_initial verbatim: the SHAPE half alone -- one word
    character plus a period, or a bare ASCII capital.

    Callers asking whether a token is STRUCTURALLY part of an initial
    run want this; callers asking whether it can really stand in for a
    name want is_initial (#320). The two answers differ only inside
    _NO_INITIALS scripts, where '씨.' is initial-SHAPED but is not an
    initial -- see assign's roman-numeral fork, the shape caller, for
    what picking the wrong one costs."""
    return bool(_INITIAL.fullmatch(text))


# v1 regexes.py "roman_numeral", pinned by tests/v2/test_regex_sync.py.
_ROMAN = re.compile(r'^(X|IX|IV|V?I{0,3})$', re.I)


# rules.md#S2: "a trailing word of the suffix vocabulary reads as a
# suffix" -- the roman-numeral half of that rule, which the initial
# veto would otherwise take: V, I and X are suffix vocabulary AND bare
# capitals, and a bare capital inside a name is a middle initial.
def is_trailing_numeral_suffix(text: str, preceding: str) -> bool:
    """assign's roman-numeral fork, shared with group's bound-given
    reserve (#401): a FINAL single-token piece that is a roman numeral
    reads as the suffix when the piece before it does not look like
    part of an initial run. `preceding` is that piece's first token;
    the callers establish that `text` is last and that a name piece
    precedes it.

    is_initial_shaped, not is_initial: this asks whether the preceding
    piece looks like part of an initial run, which is a question
    about layout, and #320 narrowed the tag to initials that can
    really stand in for a name. Reading the tag here made '씨.' stop
    suppressing the fork and cost 'John 씨. V' its family name."""
    return (_ROMAN.match(text) is not None
            and not is_initial_shaped(preceding))


def is_initial(text: str) -> bool:
    """'A.' / 'j.' / bare capital -- v1's is_an_initial, narrowed to
    scripts that HAVE initials (#320). v1's \\w is Unicode-aware and
    matched CJK too, which made period-written CJK honorifics ('씨.')
    fail is_suffix_strict -- the veto in _is_suffix_strict_n, NOT the
    vocabulary: suffix_as_written has no veto, so classify tagged '씨.'
    'vocab:suffix' either way, and is_suffix_lenient took it either way
    too. Downstream of that one strict-test No, the glued honorific in
    a name carrying such a token went unpeeled ('田中さん 様.')."""
    return is_initial_shaped(text) and not in_initialless_script(text)


def is_one_case(texts: Sequence[str]) -> bool:
    """Whether a name is written wholly in ONE case -- all upper or all
    lower alike -- and so carries no case EVIDENCE about any letter in
    it (rules.md#P3, #383/#479). The caller passes the name's OWN
    words: a maiden marker's clause and any delimited (nickname)
    content are not among them, and appending one must not flip the
    reading of words that did not change.

    Mirrors the SHAPE of the comparison the R5 gate in
    `_render.capitalized` makes, not its SPAN: R5 joins every token,
    nickname and maiden content included, while classify's caller hands
    in only the name's own words (rules.md#P3's own-words doctrine, see
    above) -- so a clause-bearing name can be one-case to this function
    and mixed to R5 (measured: `'JUAN GARCIA Y LOPEZ née Jones'` is one
    case here, mixed there). Not shared by import today -- render is a
    layer this module does not reach into, and #492 is where the two
    spans are reconciled if they ever need to be.

    `Sequence`, not `Iterable`: the caller passes a list it already
    built rather than a fresh generator, so `is_one_case` costs one
    profiler frame per parse rather than one per token (#475).

    A CASELESS script answers True, harmlessly: `'محمد و علي'.upper()`
    is the string itself, so the comparison holds, and the only caller
    also requires a token whose own `upper()` and `lower()` differ --
    which a caseless letter's never do. So a caseless name never
    reaches the decision this gates, and "one case" is the honest
    verdict for text that has only one.
    """
    joined = " ".join(texts)
    return joined in (joined.upper(), joined.lower())


#: Which way the WRITING leans for a member of the ambiguous
#: credential class; None is no lean at all. Named so the two
#: predicates that answer it -- `ambiguous_lean` here and
#: `_pieces.listed_lean`, which wraps it -- carry the same three-value
#: type rather than a bare `str`. Under mypy's `strict_equality` that
#: makes a misspelled comparison (`== "credentail"`) an error at the
#: two call sites that branch on the answer, where a `str` return
#: leaves it silently False forever -- which is what the value is FOR:
#: `_pieces.peel_trailing` peels or declines on it.
#: `period_joined_vocab`'s own verdict is spelled inline for the same
#: reason; it has one caller shape and no wrapper to keep in step.
Lean = Literal["credential", "name"]


# #289's credential lean: rules.md#S2 records the words-to-spare count
# today; this predicate is the WRITING evidence that decides ahead of
# it, in a mixed-case name only (history: decisions.md#S2).
def ambiguous_lean(text: str, one_case: bool) -> Lean | None:
    """Which way the WRITING leans for a member of the ambiguous
    credential set: "credential", "name", or None for no lean at all.

    None is the fall-through to rules.md#S2's count, and it is the
    answer for three inputs. A name written wholly in one case says
    nothing about any word in it. A member written wholly in lower
    case says nothing either -- lower is how most of a mixed-case
    name is written, so it is not a contrast. And a CASELESS token
    ('씨', '毛') can be written against nothing, so neither test
    fires and the count decides, which is what keeps this rule out of
    a caseless script by construction.

    `one_case` is the recorded fact (ParseState.one_case), taken over
    the name's OWN words -- handed in rather than recomputed, because
    three sites read this and a fact two of them derived apart is the
    bug the field exists to prevent
    (mechanisms.md#ONE-PREDICATE-PER-QUESTION).

    The caller decides MEMBERSHIP: this answers only about the
    writing. Periods do not disturb either test, '.' having no case,
    so 'MA.' leans as 'MA' does -- the lean reads CASE, not periods,
    and the dotted spelling is the vocabulary's own question
    (suffix_as_written).
    """
    if one_case:
        return None
    if text.upper() == text.lower():     # caseless: no contrast to read
        return None
    if text.isupper():
        return "credential"
    if text.islower():
        return None
    return "name"


_DOTTED = re.compile(r"(?:[^\W\d_]\.)+")


def _dotted(text: str) -> bool:
    """Written with its periods: one after each letter ('M.A.',
    'J.D.'), the acronym's own spelling. A single trailing period
    ('Ma.', 'Ed.', 'Ms.') is the abbreviation shape any word can wear
    -- the honorific's, a name's -- and is not the gate's "written
    with periods" (rules.md#S2). Until #296's review the gate was
    "any period", and 'Smith, Ms.' passed it as the degree."""
    return _DOTTED.fullmatch(text) is not None


def suffix_as_written(n: str, text: str, lexicon: Lexicon) -> bool:
    """Counts as a suffix as written, with NO initial veto (the veto
    differs by caller): unambiguous suffix vocabulary, or an ambiguous
    acronym written with periods ('M.A.' yes, 'Ma' no). `n` is
    _normalize(text), passed in so callers normalize once.

    Single source for classify's "vocab:suffix" tag and the segment/
    assign predicates. The ambiguous subset is EXCLUDED from the plain
    membership test: in the real data suffix_acronyms_ambiguous is a
    subset of suffix_acronyms, and without the exclusion the period
    gate is dead code (bare 'Ed'/'Jd' would silently become suffixes).
    """
    # acronyms may be written with periods ('M.B.A.'): the ACRONYM
    # membership alone uses the period-free form (v1's is_suffix
    # removed periods only for the suffix_acronyms test); suffix WORDS
    # match on the plain normalized form
    a = n.replace(".", "")
    if a in lexicon.suffix_acronyms_ambiguous and _dotted(text):
        return True
    return (a in lexicon.suffix_acronyms
            and a not in lexicon.suffix_acronyms_ambiguous) \
        or n in lexicon.suffix_words


def _is_suffix_strict_n(n: str, text: str, lexicon: Lexicon) -> bool:
    if is_initial(text):
        # period-written ambiguous acronyms are exempt from the veto
        return _dotted(text) and \
            n.replace(".", "") in lexicon.suffix_acronyms_ambiguous
    return suffix_as_written(n, text, lexicon)


def is_suffix_strict(text: str, lexicon: Lexicon) -> bool:
    """v1's is_suffix: suffix_as_written with the initial veto ('V.' in
    'John V. Smith' is a middle initial, not roman five)."""
    return _is_suffix_strict_n(_normalize(text), text, lexicon)


def is_suffix_lenient(text: str, lexicon: Lexicon) -> bool:
    """v1's is_suffix_lenient: suffix_words accepted unconditionally,
    bypassing the initial veto -- only safe in unambiguous positions
    (after a comma)."""
    n = _normalize(text)
    return n in lexicon.suffix_words \
        or _is_suffix_strict_n(n, text, lexicon)


def delimiter_cores(policy_delimiters: frozenset[str]) -> frozenset[str]:
    """Configured suffix delimiters with surrounding whitespace
    stripped: ' - ' -> '-'. Whitespace-padded delimiters surface as
    standalone tokens; the stripped core is what tokenize produced."""
    return frozenset(d.strip() for d in policy_delimiters if d.strip())


def splits_into_suffixes(text: str, cores: frozenset[str],
                         lexicon: Lexicon) -> bool:
    """v1 expand_suffix_delimiter parity for delimiters WITHOUT
    whitespace ('RN/CRNA' with '/'): the token counts as a suffix when
    some core splits it into >=2 non-empty parts that are all suffixes.
    The token text is never rewritten (anti-#100): it takes Role.SUFFIX
    whole, which renders 'RN/CRNA' where v1 rendered 'RN, CRNA' -- the
    documented divergence, release-log classified."""
    for core in cores:
        if core in text:
            parts = [part for part in text.split(core) if part]
            if len(parts) >= 2 and all(
                    is_suffix_lenient(part, lexicon) for part in parts):
                return True
    return False


# rules.md#S3: "a word with interior periods reads as a suffix when
# any of its period-separated chunks is suffix vocabulary — except
# where every chunk the vocabulary matches is a single ASCII
# character, the roman numerals and the lone digit the vocabulary
# lists, which are about generations rather than credentials"
def period_joined_vocab(
        text: str, lexicon: Lexicon,
) -> Literal["title", "suffix", "shape"] | None:
    """v1's parse_pieces derivation for interior-period tokens
    ('Lt.Gov.', 'Msc.Ed.', and by the ANY rule 'Mr.Smith'): ANY title
    chunk makes the token a title (checked first, v1's continue); else
    ANY suffix chunk makes it a suffix. Chunk-level suffix membership
    is v1's is_suffix: bare ambiguous acronyms COUNT ('Msc.Ed.'
    derives via 'ed') -- the ambiguous period-gate applies to whole
    tokens only. Returns "title", "suffix", "shape", or None.

    "shape" is the third verdict and it is the absence of a claim
    worth acting on (#516): two or more chunks, EVERY one of them
    alphabetic, and nothing the vocabulary matches except -- possibly
    -- chunks that are a SINGLE ASCII CHARACTER. That exception is the
    roman-numeral accident retired narrowly: measured 2026-09-15 the
    one-character suffix vocabulary is {'2', 'i', 'v'} plus the glued
    CJK honorific tails, so 'John Smith R.A.I.' was reading as a
    generational suffix off the chunk 'i'. CHARACTER rather than
    LETTER because '2' is a digit and is in the set; ASCII because
    '씨' is the single character that must KEEP its claim ('J.씨'). A
    multi-character match still reads as it always did, so 'Msc.Ed.',
    'JD.CPA' and 'Lt.Gov.' are untouched -- the WIDE retirement, where
    any chunk match yields to the shape, was measured and rejected: it
    costs 'Doe, John Msc.Ed.' a real credential and re-routes the
    honorific peel of '김민준씨, J.씨' for nothing this design wants
    (decisions.md#S2).

    The ALPHABETIC requirement is a SEPARATE, narrower gate on the
    shape verdict alone (#516 review round, decided by the
    orchestrator): a bare digit chunk is not an acronym letter by any
    reading, so 'Smith, 1.4' and 'John Smith 1.4' do not join the
    class by shape -- the only PROTECTED digit control this design
    had was the delimited 'Bridge (1.4)', and 'Smith, 1.4' and its
    no-comma twin were the gap that control did not cover, since
    delimited content is excluded by a different mechanism (extract's
    escape) and digits reach THIS detector, never that one.
    '.isalpha()' is asked of EVERY chunk, not just the matched ones,
    so a mixed token like 'X.Y.2.' is not shape-admitted either -- one
    non-letter chunk is enough to say the writing is not spelling an
    acronym. Chunks the vocabulary itself matches are already
    alphabetic in the shipped lexicon, so this narrows only the
    previously-unclaimed "shape" answer, never the "suffix" one.

    The INITIALLESS-SCRIPT guard is a second, independent narrowing of
    the same verdict, on the same reasoning `is_title_shaped` already
    gives its own period-abbreviation inference (#323): a script with
    no period abbreviations at all has nothing for interior periods to
    ABBREVIATE, so a CJK word glued into period-separated single
    characters is not spelling an acronym either -- 'John Smith
    田.中.' and '김 민준 이.박.' stayed family at every release before
    this gate existed, and would otherwise have joined the ambiguous
    class by shape for the first time (measured regression, #516
    review round).

    What a "shape" verdict MEANS is the caller's question, not this
    one's: classify writes the tag, and Policy.unlisted_dotted_suffixes
    decides whether it is class membership.
    """
    if not _PERIOD_NOT_AT_END.match(text):
        return None
    chunks = [_normalize(c) for c in text.split(".") if c]
    if any(c in lexicon.titles for c in chunks):
        return "title"
    matched = [c for c in chunks
               if c in lexicon.suffix_acronyms or c in lexicon.suffix_words]
    if matched and not all(len(c) == 1 and c.isascii() for c in matched):
        return "suffix"
    if (len(chunks) >= 2 and all(c.isalpha() for c in chunks)
            and (text.isascii() or not in_initialless_script(text))):
        return "shape"
    return None


def ambiguous_class_member(text: str, lexicon: Lexicon) -> bool:
    """Whether TEXT is a member of the LISTED ambiguous credential
    class, ignoring case and policy entirely (#289/#516).

    The case-INDEPENDENT half of the comma form's own candidate test
    (`ambiguous_class_candidate`, below, which ALSO admits a by-shape
    member where Policy allows it) and of `is_wholly_suffix`'s
    credential-lean disjunct: membership by vocabulary never needs the
    case fact, only the lean does. That split is what lets the comma
    form's lazy gate ask membership FIRST and pay for `one_case` only
    where this says yes (measured regression, #289/#516: forcing the
    fact first ran `own_words` -> `tag_marker_runs` for every
    single-token-after-the-comma name, none of them able to reach the
    class at all).

    Membership is the listed set, bare: a whole-token vocabulary match
    is not in this class at all, being settled ('M.A.', 'Ph.D.',
    'A.B.C.').

    Cheaper than `suffix_as_written(n, text, lexicon) or ...` would be
    here, and provably the same answer for UNDOTTED text: the Lexicon
    invariant that an ambiguous acronym is never also a suffix WORD
    (`__post_init__`'s gate_bypassed check) and is never counted
    without periods once it IS one (`suffix_as_written`'s own
    exclusion) together kill that predicate's two disjuncts once text
    is known to hold no period. One frame (`_normalize`) on the common
    path that never reaches the class, where the general predicate
    cost at least two (mechanisms.md#ONE-PREDICATE-PER-QUESTION's cost
    clause).

    The '.' gate here is DELIBERATELY STRICTER than S2's own
    dotted-form test (`_dotted`, a period after EACH letter): '.'
    anywhere excludes membership, so a single TRAILING period ('MA.',
    'Ed.') is excluded here even though the LEAN still reads it as
    the bare acronym's case ('Smith, MA.' -> suffix 'MA.', measured).
    Not a contradiction: the two questions this answers -- the
    comma-form CANDIDATE test below and the credential-lean disjunct
    -- are never asked of those shapes, the TAG path
    (`vocab:suffix-ambiguous`, read directly by the trailing peel and
    the post-comma slot) and H2's leading-title shape test already
    carrying them where they need to go.
    """
    if "." in text:
        return False
    return _normalize(text) in lexicon.suffix_acronyms_ambiguous


# #516's all-caps half, ONE PREDICATE for the shape test and its
# WHOLE-VOCABULARY exclusion, shared by the three sites that each
# needed the identical question answered (classify's tag emission,
# `_segment.py`'s multi-token run test, and this module's own unit
# tests), where it had been spelled three times over (quality-review
# finding). The usual objection to sharing -- a call costing every
# default-policy parse a frame it cannot use -- does not apply: every
# caller's own first conjunct is `policy.unlisted_caps_suffixes`,
# False by default, so neither this call nor the loop inside it is
# ever reached at the default (confirmed against the 412/449 frame
# band and the default comma harness).
def caps_shape_candidate(text: str, lexicon: Lexicon, policy: Policy,
                         one_case: bool | None) -> bool:
    """Whether TEXT is an UNLISTED all-caps credential candidate: two
    or more alphabetic characters, no period (a period fails
    `isalpha()` outright, which is what excludes the dotted spelling
    here for free -- no separate '.' test needed), written in a name
    `one_case` says is mixed (`one_case is False`; `None`, "not
    established", declines exactly as if the name were one case).

    UNLISTED means in NO wordlist at all, not merely "no whole-token
    suffix vocabulary", and the roster is `_lexicon._VOCAB_FIELDS`
    itself rather than a list written out here -- checked directly
    against the lexicon rather than through a caller's tags (this
    function's own callers have none to read, `segment` running before
    `classify`). A hand-written roster is a second place to remember,
    and it had already gone wrong: it named eleven of the thirteen
    fields, leaving `surnames` and `honorific_tails` out, so
    `Lexicon.default().add(surnames={"dupont"})` still read
    `Jean Pierre DUPONT` as suffix `DUPONT` -- a caller listing a word
    as a SURNAME and getting it read as a credential is this switch's
    own worst failure, arriving through the one wordlist that says
    "this is a family name" (review round, #289/#516;
    `honorific_tails` was already excluded transitively, being a
    subset of `suffix_words` by Lexicon invariant, and joins the
    roster for completeness rather than for a behavior change).
    Measured, #516 review rounds: particles, ambiguous particles,
    conjunctions, bound-given heads, a maiden marker ('NEE'/'GEB') and
    a title all join the shape by capitalization alone if their field
    is left unchecked.

    `suffix_acronyms_ambiguous` is in the roster, which also makes
    this predicate stand in for `ambiguous_class_member` wherever a
    caller needs "and not already a LISTED member" (undotted text's
    only path into that function is the identical membership test) --
    `_segment.py`'s run test relies on exactly that rather than
    calling both.
    """
    if not (policy.unlisted_caps_suffixes and one_case is False
            and len(text) >= 2 and text.isalpha() and text.isupper()):
        return False
    n = _normalize(text)
    for field in _VOCAB_FIELDS:
        if n in getattr(lexicon, field):
            return False
    return True


# The comma form's own candidate test (rules.md#C1, decisions.md#S2).
def ambiguous_class_candidate(text: str, lexicon: Lexicon,
                              policy: Policy) -> bool:
    """Whether TEXT is a CANDIDATE for the ambiguous credential class
    at the comma form's own structure decision (`_segment.py`): the
    LISTED half (`ambiguous_class_member`, case-free) OR, where Policy
    admits it, the SHAPE an unlisted dotted token wears
    (`period_joined_vocab`'s third verdict, #516).

    Case-free throughout, and the CAPS half of the class is
    deliberately not here: its real site is `_segment.py`'s
    multi-token run test, which calls `caps_shape_candidate` directly
    because the run is a property of that shape alone. A second route
    through here existed briefly, behind an optional `one_case`
    parameter no production caller ever passed -- `segment` has
    nothing to hand in at its single-token test -- so the branch
    answered False for every name the library parsed and only the
    unit tests reached it (review-round finding, #289/#516). A dead
    second route is a place for the two to disagree, not a
    convenience.

    A period anywhere is the gate for even ASKING the shape question,
    checked before the shape's own two calls: `period_joined_vocab`
    already declines a period-free text, but a Python-level call is
    not free and a comma name's post-comma part usually has no period
    ("Smith, John") -- measured regression, #516 review round, fixed
    by hoisting the same cheap substring test `ambiguous_class_member`
    already makes for its own reason. Where a period IS present,
    `suffix_as_written` runs only after `period_joined_vocab` says
    "shape": a dotted whole-token match with no single-chunk
    vocabulary hit of its own ('A.B.C.', via 'abc') would otherwise
    read "shape" from this function's chunk-level view alone,
    oblivious to the WHOLE-token match `suffix_as_written` already
    settled -- the same precedence classify's own tag order gives it
    (`vocab:suffix` is set before `period_joined_vocab` is even
    consulted).

    A LISTED member spelled with its periods is excluded from the
    shape branch by the same test classify's own shape branch makes:
    a caller who puts a dotted entry in `suffix_acronyms_ambiguous`
    has said the word is a listed member of this class, and reading
    it by shape instead loses the case lean the listing asks for
    (review-round finding, #289/#516 -- `Jack A.B.` with 'a.b' listed).
    It cannot change the answer for the shipped vocabulary, whose
    ambiguous entries carry no period at all.

    This function and classify's tag emission (`_tags_for`'s
    `derived == "shape"` branch) still ask the SAME question twice, of
    necessity: `segment` runs before `classify` and has no tags to
    read yet, so the two stages cannot share the call. Kept from
    drifting by
    `test_classify.test_ambiguous_class_candidate_agrees_with_the_tag`,
    which asks both of the same texts, rather than by a sentence
    alone.
    """
    if ambiguous_class_member(text, lexicon):
        return True
    if "." in text:
        # `_normalize` stays behind the shape verdict, where it always
        # was: it is a call, and a dotted post-comma token that is not
        # acronym-shaped at all ('Jr.') must not pay for it.
        if not (policy.unlisted_dotted_suffixes
                and period_joined_vocab(text, lexicon) == "shape"):
            return False
        n = _normalize(text)
        return (n not in lexicon.suffix_acronyms_ambiguous
                and not suffix_as_written(n, text, lexicon))
    return False


def name_word_count(texts: Sequence[str], lexicon: Lexicon,
                    policy: Policy) -> int:
    """How many of these texts are NAME words -- not suffix
    vocabulary, not title vocabulary.

    rules.md#C1's count for the ambiguous class, and it is of names
    rather than of words because 'Smith Jr., MA' is two tokens and one
    name: counting tokens there flips the structure and hands the
    family to `given`, which no reading of that string wants
    (decisions.md#S2). The suffix half asks the POLICY-selected
    predicate, the same one is_wholly_suffix asks, so the two agree
    about what a suffix word is; the title half asks BOTH the listed
    lookup and H2's shape test (`is_title_shaped`) -- a bare
    `lexicon.titles` lookup here read 'Xyz.' as a name word where the
    leading peel reads it as a title, and that divergence is recorded
    once, at `is_title_shaped` itself
    (mechanisms.md#ONE-PREDICATE-PER-QUESTION).
    """
    predicate = (is_suffix_lenient if policy.lenient_comma_suffixes
                 else is_suffix_strict)
    n = 0
    for text in texts:
        if (predicate(text, lexicon) or _normalize(text) in lexicon.titles
                or is_title_shaped(text)):
            continue
        n += 1
    return n


def is_wholly_suffix(texts: Sequence[str], lexicon: Lexicon,
                     policy: Policy, one_case: bool | None = None) -> bool:
    """Every token in a RUN counts as a suffix -- segment's
    suffix-comma test, lifted out of it so the peel can ask the same
    question (#319).

    NOT the plural of _script_segment._is_post_nominal, which asks
    is_suffix_strict per token. This asks the POLICY-selected predicate
    (lenient by default), plus period_joined_vocab, delimiter
    transparency and the Ph./D. merge. 'V.' is the input that tells
    them apart: it satisfies this predicate but is not a post-nominal
    -- and reading one for the other IS the #319 bug.

    An EMPTY run is False, not vacuously True: v1's suffix-comma
    detection fails on an empty parts[1] ('John Smith,, MD' is a
    family-comma parse). The 'wholly' idiom agrees -- _script_matcher's
    whole=True requires non-empty too -- which is why the name is that
    one rather than all_suffixes, where Python's all([]) would promise
    the opposite.

    An adjacent Ph./D. pair counts as ONE unit (v1's fix_phd extracted
    the credential pre-parse, so 'Smith, Ph. D.' read as suffix-comma);
    keep in sync with group's _PH/_D merge.

    `one_case` is ParseState.one_case, and it admits the LEAN: a bare
    ambiguous acronym written in capitals inside a mixed-case name is
    a credential here, so 'Steven Hardman, MD, DO, DDS' reads its
    third segment as the credential run it is (#289). None -- the
    default, and what every caller with no state to ask has -- reads
    as no lean and is this predicate's behavior in every release
    before 2.4.

    Neither Policy.unlisted_dotted_suffixes NOR
    Policy.unlisted_caps_suffixes reaches this predicate: admitting a
    by-shape member here unconditionally (an earlier version of this
    docstring described exactly that, for the dotted half alone)
    bypassed both the lean AND the NAME-word count, and combined with
    C1's own legacy TOKEN-count disjunct in `_segment.py`
    (`suffixy(groups[1]) and len(groups[0]) > 1`) it flipped
    'Smith Jr., A.B.' to given 'Smith', suffix 'Jr., A.B.' with a
    self-contradicting report ("holds 1 name words, so it is read as
    a credential run") -- proved by mutation testing to be otherwise
    unreached: nothing but this predicate's own two unit tests
    depended on it, and 'John Smith, A.B.' still flips correctly
    through `pre_comma_names >= 2` alone (#516 review round). Neither
    by-shape class, dotted or caps, reaches the comma form through
    this predicate at all -- only through `_vocab.
    ambiguous_class_candidate`, which segment's structure decision and
    report both already consult (the caps half as a RUN test over it,
    #516's second review round).
    """
    if not texts:
        return False
    predicate = (is_suffix_lenient if policy.lenient_comma_suffixes
                 else is_suffix_strict)
    # v1 expand_suffix_delimiter parity (#206): a configured delimiter
    # is TRANSPARENT in the all-suffix tests -- v1 split the part string
    # on the delimiter before checking, so the delimiter never counted
    cores = delimiter_cores(policy.extra_suffix_delimiters)

    def counts_as_suffix(text: str) -> bool:
        if text in cores:
            return True
        if (one_case is not None
                and ambiguous_class_member(text, lexicon)
                and ambiguous_lean(text, one_case) == "credential"):
            return True
        return (predicate(text, lexicon)
                or period_joined_vocab(text, lexicon) == "suffix"
                or (bool(cores) and splits_into_suffixes(text, cores, lexicon)))

    merged = list(texts)
    k = 0
    while k < len(merged) - 1:
        if PH.fullmatch(merged[k]) and D.fullmatch(merged[k + 1]):
            merged[k:k + 2] = ["phd"]
        else:
            k += 1
    return all(counts_as_suffix(t) for t in merged)


# The two derived views of a marker vocabulary, cached per-vocabulary
# on _script_segment._longest_entry's precedent -- same function shape
# (a scalar derived from a vocabulary frozenset), same key space, and
# its reasoning for maxsize=16 carries over verbatim: a process holds
# the default vocabulary plus one per constructed pack parser, so 16
# bounds many-lexicon churn without ever evicting in normal use.
# (NOT _extract._delimiter_chars' precedent, which these once cited:
# that one is consulted once per parse, so it says nothing about a
# lookup on the per-token path.) Keying on the frozenset costs a
# cached hash, not a sweep of its contents.
@functools.lru_cache(maxsize=16)
def _longest_marker(markers: frozenset[str]) -> int:
    """How many words the longest entry of `markers` spans -- the
    lookahead bound, computed from the vocabulary rather than fixed at a
    literal so a caller's four-word entry works and an all-single-word
    set leaves the common path at one lookup. Entries are stored
    space-joined with single separators, so the space count IS the word
    count."""
    return max((entry.count(" ") + 1 for entry in markers), default=0)


@functools.lru_cache(maxsize=16)
def _marker_heads(markers: frozenset[str]) -> frozenset[str]:
    """The first word of every entry -- the set a run can possibly open
    with. Entries are already stored per-word folded, so an entry's
    first word is the same fold the lookup builds."""
    return frozenset(entry.split(" ", 1)[0] for entry in markers)


def maiden_marker_head(n: str, markers: frozenset[str]) -> bool:
    """Could a maiden marker run START here? `n` is _normalize(word),
    passed in so callers fold once -- suffix_as_written's shape exactly
    ("`n` is `_normalize(text)`, passed in so callers normalize once"),
    and with no raw-text sibling for the same reason it has none: every
    caller is on the per-token path and has the fold in hand already.

    A SUPERSET test. True means only that some entry opens with this
    word, never that a run matches -- maiden_marker_run is the answer,
    and it calls this function, so the two cannot drift. Exported
    because a caller scanning a whole token stream needs to know
    whether assembling a candidate sequence is worth doing at all, and
    for almost every token it is not: _classify's pass would otherwise
    walk structural boundaries once per token to build a lookahead the
    predicate discards on this very test.
    """
    return n in _marker_heads(markers)


def maiden_marker_run(words: Sequence[str], markers: frozenset[str]) -> int:
    """How many of `words` a maiden marker claims, longest first; 0 for
    none.

    Phrases are stored space-joined and per-word normalized (_title_key's
    storage rule), so the key is rebuilt the same way here -- normalizing
    the joined phrase instead would leave interior periods.

    `words` must be words that stand TOGETHER -- one clause's, or one
    segment's. This answers only what the vocabulary says about the
    sequence it is handed; whether a sequence is a sequence is the
    caller's, and classify's contiguity rule is where that is decided
    for the token stream.

    Longest first, so a caller configuring both 'geb' and 'geb von' gets
    the phrase where it matches and the bare word everywhere else. The
    one answer to "does a marker start here, and where does it end": the
    stages that can call it do (classify over token texts, extract over
    a clause's whitespace words), and the stage that runs after classify
    reads the tags classify recorded instead
    (mechanisms.md#ONE-PREDICATE-PER-QUESTION).
    """
    # Fast path first: no entry opens with this word, so no length can
    # match. It cannot hide a match -- every key the loop builds opens
    # with _normalize(words[0]) unless that word folds away, and a
    # folded-away first word fails the n-word test below for every
    # n > 1 and is not a stored entry for n == 1.
    if not words:
        return 0
    head = _normalize(words[0])
    if not maiden_marker_head(head, markers):
        return 0
    cap = min(len(words), _longest_marker(markers))
    # Fold each word ONCE, then key from a prefix. _title_key(words[:n])
    # per candidate length re-folds the whole prefix every time, which
    # is quadratic in cap and makes a one-word hit cost more than a
    # two-word one -- the longest key is always built and discarded
    # first, and all but one shipped entry is a single word. The join
    # below IS _title_key's body over pre-folded words (per-word fold,
    # empties dropped, space-joined); test_vocab pins that the two
    # agree, since this is a copy of a fold whose definition lives in
    # _lexicon.
    folded = [head] + [_normalize(w) for w in words[1:cap]]
    for n in range(cap, 0, -1):
        key = " ".join(filter(None, folded[:n]))
        # a word that folds away is DROPPED from the key, so 'née'
        # followed by a lone '.' would key as 'née' and a one-word
        # marker would claim the period as part of its run. n words in,
        # n words out: anything else is not this key's n-word phrase.
        if key.count(" ") == n - 1 and key in markers:
            return n
    return 0


def tag_marker_runs(tokens: Sequence[WorkToken], comma_offsets: Sequence[int],
                    markers: frozenset[str],
                    folded: Sequence[str] | None = None) -> dict[int, str]:
    """Which tokens are maiden marker runs: index -> "vocab:maiden-marker"
    for a run's head, "vocab:maiden-marker-cont" for the rest.

    Returns the decision rather than rewriting the tokens: a caller
    that writes tags into the one pass that builds them (classify)
    consults this map rather than deciding a run twice, so a marker
    token is never replaced twice; a caller that never writes tags at
    all (own_words) reads the same map for its span instead.

    Moved here from classify (#289/#516) so a caller outside classify
    -- _pieces.own_words, when it has no marker map yet -- can build
    the SAME map classify would, rather than approximating it with a
    text-only head test. `_pieces.py` may import only _state and
    _vocab (tests/v2/test_layering.py), so the one shared function
    both sites call has to live here, in the layer both can reach.

    `folded` is _normalize per token; classify has already built it
    for the vocabulary-tag pass and hands it over so this pass costs
    no second fold, and a caller with only tokens (own_words' self-
    built path) omits it and pays the fold here instead -- paid only
    on that path, never on classify's, so the reference name's frame
    count is unchanged (#289/#516).

    The one sequence pass in this stage, and it has to be one: a marker
    entry may be a PHRASE whose words are not markers individually
    ('z', 'domu'), so no per-token membership test can find it.
    Left to right, longest first at each position, then skip past what
    the run claimed -- a second marker cannot start inside the first.

    This is where the tag is DECIDED for the stages that read it
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
    # the lookahead the vocabulary actually needs; 0 for an empty set,
    # which skips the pass entirely
    cap = _longest_marker(markers)
    if not cap:
        return {}
    if folded is None:
        folded = [_normalize(t.text) for t in tokens]
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
                buckets = [comma_bucket(t.span.start, comma_offsets)
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


def _normalized_for_script(text: str) -> str | None:
    """The guard AND the two normalizations single_script and
    effective_script's license path both need, single-sourced so they
    cannot drift: trailing full stops are dropped (FULL_STOPS, #323),
    then None for the two shapes neither ever classifies (nothing
    left, and the common all-ASCII Latin token -- skipped before
    normalizing, since ASCII is already NFC and every _SCRIPT_RANGES
    entry is non-ASCII regardless), else an NFC-normalized copy.

    Trailing stops, not raw: a period glued to a script-written token
    ('양.', '太郎.') is not a character of any script, so classifying
    raw text handed the token no script at all, and three readers
    spent that None -- the surname site stepped past the family name
    onto the given name ('양. 지훈' cut 지훈 in half), the order rule
    fell back to positional ('양 지훈.' lost family-first), and the
    segmenter's neighbour precondition missed a writer-drawn boundary
    ('山田太郎 田中.' consulted the segmenter on 山田太郎 as if it stood
    alone). The scripts this classifies -- every _SCRIPT_RANGES entry,
    which today coincide with _policy._NO_INITIALS (#320), a
    coincidence _policy says a new member must not inherit -- have no
    initials and no period abbreviations, so a stop on such a token
    carries no information about the word; ASCII text is stripped too,
    but the guard below returns None for it regardless, so 'Smith.'
    never classifies. TRAILING only, matching the surname site's own
    rstrip in _script_segment (the same arithmetic, not a shared
    gate -- this fold decides only whether the surname site, the order
    rule and the segmenter ever see the token): a leading stop is not
    a shape any script writes before a name word, and HIDING such a
    token from those three readers -- no script, so no surname site,
    which is what the tree before #323 did -- is safer than admitting
    it. Admitted, '.김민준' classifies as hangul, becomes a surname
    site, is declined by the head match (which rstrips) and falls
    through to a configured segmenter, which answering offset 1
    divides it into the stop and the name. The peel is not gated by
    this fold; its own rstrip carries a leading-stop token, see
    _script_segment. The vocabulary fold alone reads BOTH edges
    (_lexicon._normalize): '.씨' is still the honorific, and a lookup
    divides nothing.

    NFC, not raw: NFD input decomposes precomposed katakana onto a
    base character plus a COMBINING mark (U+3099/U+309A, which sit in
    the HIRAGANA block, not katakana's), so classifying raw NFD text
    can hand a pure-katakana token the kana license by accident; NFD
    also decomposes Hangul syllables onto bare jamo (U+1100-U+11FF),
    entirely outside the HANGUL range, so raw NFD Korean input misses
    the shipped family-first order rule rather than merely misfiring.
    Normalizing first fixes both. Classification-only and read-only:
    the returned copy is never what gets tokenized, so token text and
    spans stay exactly what the caller wrote.

    Vocabulary MATCHING composes NFC too, since #322
    (_lexicon._normalize folds every lookup and every stored entry the
    same way), so an NFD suffix word reaches its NFC entry. What stays
    raw is SEGMENTATION -- the surname site's direct membership test
    and the peel's tail slice index the token's own text -- where NFD
    degrades to no-split, never to a wrong split (decisions.md#W1,
    the 2026-07-29 ja amendment).
    """
    text = text.rstrip(FULL_STOPS)
    if not text or text.isascii():
        return None
    return unicodedata.normalize("NFC", text)


def _classify(normalized: str) -> Script | None:
    """The FIRST _SCRIPT_MATCHERS entry covering all of `normalized`
    (already NFC, via _normalized_for_script), else None. Shared by
    both public classifiers so each of them normalizes exactly once."""
    for script, matcher in _SCRIPT_MATCHERS.items():
        if matcher(normalized):
            return script
    return None


def single_script(text: str) -> Script | None:
    """The one Script whose ranges cover EVERY char of `text`, else
    None (mixed-script text has no well-defined convention to apply;
    the caller falls back to the positional default). Classifies an
    NFC-normalized copy of `text` -- see _normalized_for_script.
    Callers wanting the kana-mixed license (a kanji+kana composite
    resolving to HIRAGANA) want effective_script, not this function."""
    normalized = _normalized_for_script(text)
    if normalized is None:
        return None
    return _classify(normalized)


def effective_script(text: str) -> Script | None:
    """single_script, extended by the kana license (#272 amendment):
    a MIXED token wholly within Han∪hiragana∪katakana is Japanese --
    it necessarily contains kana (pure Han is not mixed), cannot be
    Chinese, and is not a foreign transcription (those are
    katakana-only: マイケル has no kanji, but さくらエミ -- hiragana
    plus katakana -- is kana-only AND licensed) -- and resolves to the
    HIRAGANA carrier entry. Pure-katakana stays KATAKANA
    (single_script's answer): a lone katakana token is predominantly a
    transcribed foreign name, so nothing defaults on it."""
    # None for both shapes _wholly_ja could never match anyway (empty
    # text, or all-ASCII text): real work, not a leftover "if text"
    # guard, since the ASCII case is one a bare emptiness check would
    # let through. The single normalized copy then serves both the
    # single-script answer and the license below.
    normalized = _normalized_for_script(text)
    if normalized is None:
        return None
    script = _classify(normalized)
    if script is not None:
        return script
    if _wholly_ja(normalized):
        return Script.HIRAGANA
    return None


def resolve_script_set(scripts: Iterable[Script]) -> Script | None:
    """Generalizes effective_script's kana license from one token's
    CHARACTERS to a whole name's PIECES (#272): `scripts` is the
    effective_script of every name token, already resolved
    individually -- '高橋' (Han) and 'みなみ' (Hiragana) are two
    separately single-script pieces (split by a space, not mixed
    within one token), but together are exactly the repertoire
    effective_script licenses inside a single token (高橋みなみ). A
    single distinct script is returned as-is (the ordinary case,
    including a lone wholly-katakana name, which callers key with no
    table entry); more than one collapses to the HIRAGANA carrier
    when confined to Han/Hiragana/Katakana, the same set
    effective_script's license tests; any other mix (Han+Hangul, or
    no scripts at all -- an empty `scripts`) returns None -- the
    caller's cue to fall back to the positional default, exactly like
    effective_script's own None. A non-None result reports what was
    FOUND, not that a license fired: callers wanting to know whether
    the kana license specifically was the reason must compare the
    result against a specific Script (e.g. `is Script.HIRAGANA`), not
    just its truthiness -- a lone wholly-Han name also returns
    non-None here, licensing nothing."""
    found = frozenset(scripts)
    if len(found) <= 1:
        return next(iter(found), None)
    if found.issubset(_JA_SCRIPTS):
        return Script.HIRAGANA
    return None
