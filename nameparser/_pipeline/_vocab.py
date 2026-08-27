"""Shared vocabulary predicates for pipeline stages.

Text-level tests used by more than one stage; piece-level ones live
in _pieces, the sibling layer over tokens-plus-tags. All take normalized-or-raw text
explicitly -- no state.

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

Layering: imports _lexicon, _types, and _policy only.
"""
from __future__ import annotations

import functools
import re
import unicodedata
from collections.abc import Callable, Iterable, Sequence

from nameparser._lexicon import Lexicon, _normalize, _title_key
from nameparser._policy import (Policy, Script, _JA_SCRIPTS, _NO_INITIALS,
                                _SCRIPT_RANGES, _script_matcher)

# Ported verbatim from v1 (nameparser/config/regexes.py "initial") minus
# its empty-string alternative -- WorkToken text is never empty. Kept in
# sync by hand; layering forbids importing the config package here.
# "Verbatim" is a promise about the PATTERN, not about the predicate:
# since #320 is_initial is this SHAPE test ANDed with a repertoire test
# (_in_initialless_script, below), so _INITIAL.fullmatch(text) and
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
_in_initialless_script = _script_matcher(*_NO_INITIALS, whole=False)


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
    return is_initial_shaped(text) and not _in_initialless_script(text)


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
# any of its period-separated chunks is suffix vocabulary"
def period_joined_vocab(text: str, lexicon: Lexicon) -> str | None:
    """v1's parse_pieces derivation for interior-period tokens
    ('Lt.Gov.', 'Msc.Ed.', and by the ANY rule 'Mr.Smith'): ANY title
    chunk makes the token a title (checked first, v1's continue); else
    ANY suffix chunk makes it a suffix. Chunk-level suffix membership
    is v1's is_suffix: bare ambiguous acronyms COUNT ('Msc.Ed.'
    derives via 'ed') -- the ambiguous period-gate applies to whole
    tokens only. Returns "title", "suffix", or None."""
    if not _PERIOD_NOT_AT_END.match(text):
        return None
    chunks = [_normalize(c) for c in text.split(".") if c]
    if any(c in lexicon.titles for c in chunks):
        return "title"
    if any(c in lexicon.suffix_acronyms or c in lexicon.suffix_words
           for c in chunks):
        return "suffix"
    return None


def is_wholly_suffix(texts: Sequence[str], lexicon: Lexicon,
                     policy: Policy) -> bool:
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
        return (predicate(text, lexicon)
                or period_joined_vocab(text, lexicon) == "suffix"
                or (bool(cores)
                    and splits_into_suffixes(text, cores, lexicon)))

    merged = list(texts)
    k = 0
    while k < len(merged) - 1:
        if PH.fullmatch(merged[k]) and D.fullmatch(merged[k + 1]):
            merged[k:k + 2] = ["phd"]
        else:
            k += 1
    return all(counts_as_suffix(t) for t in merged)


@functools.lru_cache(maxsize=128)
def _longest_marker(markers: frozenset[str]) -> int:
    """How many words the longest entry of `markers` spans -- the
    lookahead bound, computed from the vocabulary rather than fixed at a
    literal so a caller's four-word entry works and an all-single-word
    set leaves the common path at one lookup. Entries are stored
    space-joined with single separators, so the space count IS the word
    count. Cached on the (hashable) frozenset, like
    _extract._delimiter_chars: every token of every parse asks, and the
    answer changes only when the lexicon does.
    """
    return max((entry.count(" ") + 1 for entry in markers), default=0)


@functools.lru_cache(maxsize=128)
def _marker_heads(markers: frozenset[str]) -> frozenset[str]:
    """The first word of every entry -- the set a run can possibly open
    with. Derived from `markers` and used only inside the predicate
    below, so it is a fast path rather than a second answer: entries are
    already stored per-word folded, so an entry's first word is the same
    fold the lookup builds. Cached like _longest_marker, and for the
    same reason -- this is asked once per token of every parse."""
    return frozenset(entry.split(" ", 1)[0] for entry in markers)


def maiden_marker_head(word: str, markers: frozenset[str]) -> bool:
    """Could a maiden marker run START at `word`? A SUPERSET test: True
    means only that some entry opens with this word, never that a run
    matches -- maiden_marker_run is the answer.

    This is that predicate's own first test, not a second one: the
    predicate calls this function, so the two cannot drift. It is
    exported because a caller scanning a whole token stream needs to
    know whether assembling a candidate sequence is worth doing at all,
    and for almost every token it is not -- _classify's pass would
    otherwise walk structural boundaries once per token to build a
    lookahead the predicate discards on this very test.
    """
    return _normalize(word) in _marker_heads(markers)


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
    # Fast path, and the reason this stays affordable at one call per
    # token: no entry opens with this word, so no length can match. It
    # cannot hide a match -- every key the loop builds opens with
    # _normalize(words[0]) unless that word folds away, and a folded-away
    # first word fails the n-word test below for every n > 1 and is not
    # a stored entry for n == 1.
    #
    # The fold it does is the third on this token in a parse:
    # _classify._tags_for computes _normalize(text) and discards it,
    # and _classify's marker pass asks maiden_marker_head, which folds
    # again before calling this. Threading a normalized text through
    # would put an extra parameter on the one predicate every site
    # shares, and the measurement says the whole marker mechanism costs
    # about 1.6% of a parse with the folds as they are
    # (decisions.md's #434 entry). Left alone deliberately.
    if not words or not maiden_marker_head(words[0], markers):
        return 0
    for n in range(min(len(words), _longest_marker(markers)), 0, -1):
        key = _title_key(words[:n])
        # _title_key DROPS a word that folds away, so 'née' followed by
        # a lone '.' would key as 'née' and a one-word marker would
        # claim the period as part of its run. n words in, n words out:
        # anything else is not this key's n-word phrase.
        if key.count(" ") == n - 1 and key in markers:
            return n
    return 0


def _normalized_for_script(text: str) -> str | None:
    """The guard AND the NFC normalization single_script and
    effective_script's license path both need, single-sourced so they
    cannot drift: None for the two shapes neither ever classifies
    (empty, and the common all-ASCII Latin token -- skipped before
    normalizing, since ASCII is already NFC and every _SCRIPT_RANGES
    entry is non-ASCII regardless), else an NFC-normalized copy.

    NFC, not raw: NFD input decomposes precomposed katakana onto a
    base character plus a COMBINING mark (U+3099/U+309A, which sit in
    the HIRAGANA block, not katakana's), so classifying raw NFD text
    can hand a pure-katakana token the kana license by accident; NFD
    also decomposes Hangul syllables onto bare jamo (U+1100-U+11FF),
    entirely outside the HANGUL range, so raw NFD Korean input misses
    the shipped family-first order rule rather than merely misfiring.
    Normalizing first fixes both. This is classification-only and
    read-only: the returned copy is never what gets tokenized, so
    token text and spans stay exactly what the caller wrote.

    MATCHING (is_initial, suffix lookups, etc.) deliberately stays on
    raw text elsewhere in this module -- unlike script classification,
    NFD only ever costs a match there (a suffix word written NFD fails
    to match its NFC vocabulary entry), never wrong-matches, so the
    asymmetry is safe: one direction needs a fix, the other doesn't.
    """
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
