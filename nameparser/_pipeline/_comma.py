"""Not a stage: rules/C1's decision, made by group at its head.

The comma's structure is decided ONCE, after classify has tagged every
word and before group joins any of them (#613): the part after the
first comma is read by `_pieces.segment_suffix_reading`, the one
reading a part that holds no name word gets, with the words C4's count
licenses as credentials behind a whole name. Where it reads as the
postnominal part its roles are set here, so no join in group and no
walk in assign can reach them, and the comma is a suffix comma when
the part before it is a whole name; otherwise the family comma
`segment` handed over stands, and assign reads the listing form.

Deciding in `segment`, before the tags existed, meant predicting what
later stages would do -- group's particle chain (#562's pair), assign's
reading of a run the capitals settle -- and assign re-deciding #296's
positional read with a second count; reading once and binding is
mechanisms.md#READ-WITHOUT-THEN-BIND.

Reads: Lexicon suffix, title, particle and ambiguous-class vocabulary
through the tags classify wrote and through _vocab.name_word_count and
_vocab.is_wholly_suffix; every Lexicon wordlist through
_vocab.caps_shape_candidate (to know an all-caps word is unlisted) and
_vocab.claimed_as_non_name (the name's contrast); Lexicon
.maiden_markers through _pieces.own_words, for the name's contrast;
Policy.lenient_comma_suffixes, Policy.extra_suffix_delimiters,
Policy.unlisted_caps_suffixes and Policy.unlisted_dotted_suffixes.
"""
from __future__ import annotations

import unicodedata
from collections.abc import Sequence

from nameparser._lexicon import Lexicon, _normalize
from nameparser._pipeline._pieces import (
    has_name_content, is_suffix_piece, is_title_piece, join_connectives,
    listed_lean, own_words, segment_suffix_reading,
)
from nameparser._pipeline._state import (
    AMBIGUOUS_ACRONYM_TAG, SHAPE_ACRONYM_TAG, ParseState, PendingAmbiguity,
    Structure, WorkToken, copy_with,
)
from nameparser._pipeline._vocab import (
    D, PH, ROMAN, caps_shape_candidate, claimed_as_non_name, delimiter_cores,
    composed_len, glued_stem, glues, is_caps_word, is_paired_initials,
    is_single_letter_numeral,
    is_trailing_numeral_suffix, is_wholly_suffix, name_word_count,
    surname_unit_facts, unit_ends, written_as_a_name,
)
from nameparser._policy import CapsSuffixes
from nameparser._types import AmbiguityKind, Role


def _pieces(seg: Sequence[int], tokens: Sequence[WorkToken],
            ) -> tuple[list[list[int]], list[set[str]]]:
    """One piece per token but the Ph./D. pair, which group's first
    merge builds -- the part as it stands before any join. Every piece
    a fresh list, as `merge_pieces` requires."""
    pieces: list[list[int]] = []
    ptags: list[set[str]] = []
    k = 0
    while k < len(seg):
        a = seg[k]
        if (k + 1 < len(seg) and PH.fullmatch(tokens[a].text)
                and D.fullmatch(tokens[seg[k + 1]].text)):
            pieces.append([a, seg[k + 1]])
            ptags.append({"suffix"})
            k += 2
        else:
            pieces.append([a])
            ptags.append(set())
            k += 1
    return pieces, ptags


def _reading_pieces(part: Sequence[int], tokens: Sequence[WorkToken],
                    ) -> tuple[list[list[int]], list[set[str]]]:
    """The part as the reading takes it: `_pieces`, then the one join it
    can hold."""
    pieces, ptags = _pieces(part, tokens)
    # The one join a postnominal part can hold, made here so the reading
    # sees it: rules/P3's connective joining its neighbours where the
    # neighbour it takes its kind from is a title, which makes the
    # joined part a title ('Mr. and Mrs.', 'Secretary of State', 'Dr.
    # and'), a run of connectives merging first as it does in the name
    # ('Minister of the Interior'). A LONE single-letter connective is
    # left as it stands, P3 or P8 reading it as a name word or an initial in
    # short names; one beside another connective is a member of their
    # run and joins with it ('Mr. y and Mrs.'). Any other join is not
    # made here: where no credential opens the part, a name word in it
    # makes it the given part; where one does, the run #603 opens takes
    # the connective as a word and reports it ('John Smith, PhD and
    # Dr.'). Group's own joins, the one loop since #617: its copy here
    # merged no run and joined 'Minister of the' alone.
    #
    # rules/P3: "A connective that is also generational vocabulary
    # joins only where a name word stands on each side of it" -- and in
    # a part read for credentials none does, so every such connective
    # is frozen here, where group freezes only the ones it finds without
    # a name word beside them ('Rovira, Dr. i i' keeps suffix 'i i'
    # rather than run-merging the pair into the title, #617); a
    # neighbour's join may still take one in ('Smith, Dr. and i' reads
    # title 'Dr. and i'), as `join_connectives` says.
    #
    # The same walk says whether there is anything to join, and a part
    # with no connective left free -- nearly every part -- skips the
    # shared loop, whose predicate calls cost two frames per word
    # ('Smith, John' paid two; #617's review).
    frozen: set[int] = set()
    free = False
    for i in part:
        tags = tokens[i].tags
        if "conjunction" in tags:
            if "vocab:suffix" in tags:
                frozen.add(i)
            else:
                free = True
    if free:
        join_connectives(pieces, ptags, tokens, letter_stays=True,
                         titles_only=True, frozen=frozen)
    return pieces, ptags


def _unclaimed_name_word(text: str, lexicon: Lexicon) -> bool:
    """A word written as a name and claimed by no wordlist as anything
    else -- #564's contrast word and rules/C12's veto, one question.
    The caller tests for a period first, in C: a word with one is an
    abbreviation or an initial, not a name word."""
    return (written_as_a_name(text)
            and not claimed_as_non_name(_normalize(text), lexicon))


def _name_contrast(state: ParseState, seg0: Sequence[int],
                   clause_at: int | None = None) -> bool:
    """#564 (Derek): the contrast the caps shape needs is the NAME's,
    and the name carries it only if one of its own words before the
    comma (no maiden clause, no delimited content, as `own_words`
    defines them) is written the way a name is written in mixed case
    -- a capital in it and its last letter lowercase
    (`written_as_a_name`) -- and is not claimed as a title, particle,
    connective, credential or generation (`claimed_as_non_name`); a
    word with a period is an abbreviation or an initial, not one. A
    lone capital ('de GAULLE C'), a lowercase-only word and a surname
    written in capitals with anything glued in front ("d'ESTAING",
    'FitzGERALD', 'McDONALD') all fail it, so such a record keeps its
    given name beside its lowercase particles, clauses and titles and
    beside a mixed-case credential ('LLOYD WEBBER, ANDREW PhD'). A part
    with no lowercase at all is settled in one C-level comparison.
    `clause_at` is `own_words`' clause index where the caller already
    holds it."""
    before = "".join([state.tokens[i].text for i in seg0])
    if before == before.upper():
        return False
    if clause_at is None:
        _, clause_at = own_words(state.tokens, state.comma_offsets,
                                 state.lexicon.maiden_markers)
    lex = state.lexicon
    return any(
        i < clause_at and (tok := state.tokens[i]).role is None
        and "." not in tok.text and _unclaimed_name_word(tok.text, lex)
        for i in seg0)


def _whole_name(seg0: Sequence[int], tokens: Sequence[WorkToken]) -> bool:
    """rules/C3's count before the comma for an unambiguous
    credential, read off classify's tags (the ambiguous class's count
    of NAME words, which leaves titles out, is
    `_vocab.name_word_count`'s, asked in `decide`): two or more units (a particle run and
    the name word it attaches to one unit, a connective join not, #575)
    holding a word that is not a suffix word -- a title counts, being a
    word to the count an unambiguous credential takes."""
    # rules/C3: "a particle run and the one name word it attaches to are
    # one word"
    pieces, ptags = _pieces(seg0, tokens)
    named: set[int] = set()
    for piece, tags in zip(pieces, ptags):
        if not is_suffix_piece(piece, tags, tokens):
            named.update(piece)
    if len(named) < 2:
        return False
    idx = list(seg0)
    names = 0
    start = 0
    for end in unit_ends([surname_unit_facts(tokens[i].tags, k == 0)
                          for k, i in enumerate(idx)], chain=False):
        if not named.isdisjoint(idx[start:end]):
            names += 1
            if names > 1:
                return True
        start = end
    return False


def _behind_a_generation(state: ParseState, seg0: Sequence[int],
                         p1: Sequence[list[int]], pt1: Sequence[set[str]],
                         tokens: Sequence[WorkToken], contrast: bool | None,
                         ) -> tuple[bool, ...] | None:
    """rules/C12's reading of the part after the comma, or None where
    the listing form stands: behind a whole name ending in a suffix
    word, or in a numeral the trailing fork reads as the generation,
    the part is the credential run, its titles (a word or a run a
    connective joins) reading as titles, unless a word of it is
    written as a name. The caller has tested the tag, or the numeral
    shape with `ROMAN`, as a cheap filter. The part's veto is asked
    first, being the cheap question and the one a listing with a given
    name answers ('Garcia Lopez Jr., Juan'). `contrast` is C6's answer
    where `decide` has already asked it, else None."""
    # two name words and the generation at least: exact, since
    # `_whole_name` needs two units in front ('Smith VI, AD')
    if len(seg0) < 3:
        return None
    lex = state.lexicon
    reading: list[bool] = []
    for p, pt in zip(p1, pt1):
        # a title reads as a title, a word or a run a connective joins
        # ('Mr. and Mrs.', a dual inside it included); a lone dual of
        # the title and the suffix vocabulary is the suffix here, the
        # slot being postnominal ('John Smith Jr., AD RA'): C13's two
        # predicates, asked in C13's order
        title = (not is_suffix_piece(p, pt, tokens)
                 and is_title_piece(p, pt, tokens))
        for i in p:
            tok = tokens[i]
            # rules/C12: "a word of it written as a name, or an
            # initial, keeps the listing form" -- unlisted, and a word
            # with a period is an abbreviation, as for the contrast;
            # paired initials are initials, as C5 keeps them ('J.A.')
            if "initial" in tok.tags or (
                    is_paired_initials(tok.text) if "." in tok.text
                    else _unclaimed_name_word(tok.text, lex)):
                return None
        reading.append(not title)
    last = tokens[seg0[-1]].text
    # a numeral by shape alone (VI to X) is the generation the trailing
    # fork reads, as the listed ones are (#610's class: 'VI' beside 'V'
    # and 'III'), and not one it reads as an initial's neighbour
    # ('John J VI, AD')
    if ("vocab:suffix-word" not in tokens[seg0[-1]].tags
            and not is_trailing_numeral_suffix(
                last, tokens[seg0[-2]].text, state.one_case)):
        return None
    # the generation set aside, the name's own words in front of it are
    # a whole name: 'Smith VI' is one word and a numeral, as 'Smith III'
    # is, and a maiden clause is no word of the name ('Jane nee Smith
    # Jr., AD' reads as 'Jane Jr., AD'; own_words, as for the contrast)
    _, clause_at = own_words(state.tokens, state.comma_offsets,
                             lex.maiden_markers)
    front = [i for i in seg0[:-1]
             if i < clause_at and tokens[i].role is None]
    if not _whole_name(front, tokens):
        return None
    # a one-letter numeral is the generation only where the name has a
    # word to spare for it, a title being none (rules/S10), and is no
    # evidence where the name reads it as a name word ('Dr. Smith V,
    # AD', whose title is a word to the count above but none here)
    if (len(last.rstrip(".")) == 1 and is_single_letter_numeral(last)
            and name_word_count([tokens[i].text for i in front], lex,
                                state.policy,
                                letters_one_case=state.one_case) < 2):
        return None
    if contrast is None:
        contrast = _name_contrast(state, seg0, clause_at)
    if not contrast:
        return None
    return tuple(reading)


def decide(state: ParseState) -> ParseState:
    """The structure of a comma form, and the postnominal part bound.
    Returns `state` unchanged where the listing form stands."""
    if (state.structure is not Structure.FAMILY_COMMA
            or len(state.segments) < 2):
        return state
    seg0, seg1 = state.segments[0], state.segments[1]
    # Nothing after the comma: nothing to read. An EMPTY part BEFORE it
    # is read on, being no whole name (`_whole_name` answers no), so
    # ', PhD' binds its credential under the family comma as 2.3.0 read
    # it; returning here on an empty head left the part to the listing
    # walk, which made 'PhD' the given name and ', Jr.' a title (#613's
    # PR review; empty surname fields in CSV data write exactly this)
    if not seg1:
        return state
    tokens = list(state.tokens)
    lex, pol = state.lexicon, state.policy
    # rules/C10: "a suffix delimiter parts the suffix words on each side
    # of it as a comma would" -- behind a whole name its cores are
    # no word of the reading, and leave as group drops them in a tail;
    # behind one name word the core is a word, v1 having applied the
    # delimiter to the suffix-comma form alone (C10's core-is-a-word
    # Accepted entry)
    cores = delimiter_cores(pol.extra_suffix_delimiters)
    whole: bool | None = None
    core_idx: list[int] = []
    # a loop, and the head counted only where a core stands alone: the
    # built-in ';' leaves `cores` non-empty for every policy (D15)
    if len(seg1) > 1:
        for i in seg1:
            if tokens[i].text in cores:
                core_idx.append(i)
        if core_idx:
            whole = _whole_name(seg0, tokens)
            if not whole:
                core_idx = []
    # a set for the membership test: a list scanned per token was
    # quadratic in the part (#613's PR review, 'MD / '*k under '/')
    core_set = frozenset(core_idx)
    part = [i for i in seg1 if i not in core_set] if core_idx else list(seg1)
    if not part:
        return state
    if pol.unlisted_dotted_suffixes:
        # rules/S3: "Paired initials are the exception [...] where S4
        # would count words to spare for them they are the name word
        # they are written as" -- classify holds the class tag back from
        # them, and at this comma C5 reads them instead (S3's Precedence
        # bullet), so they rejoin the class for C5's count. Shape-tagged
        # and untagged with the switch on is exactly that word
        # (classify's dotted branch), asked of the tags in C
        # (decisions/S3 (#864)).
        for i in part:
            tags = tokens[i].tags
            if (SHAPE_ACRONYM_TAG in tags
                    and AMBIGUOUS_ACRONYM_TAG not in tags):
                tokens[i] = copy_with(
                    tokens[i], tags=tags | {AMBIGUOUS_ACRONYM_TAG})
    p1, pt1 = _reading_pieces(part, tokens)
    anchored: list[int] = []
    absorbed: list[int] = []
    # A core in the part, standing alone or glued to a word or inside
    # one: either keeps the part from the listing form's early return,
    # and only a glued one reads behind any head, a core standing alone
    # being a word behind one name word (C10's Accepted bullet). The
    # shape tests below read a word with one glued at an end as the word
    # without it, as classify tags it ('MBBS;' as 'MBBS'). A loop, so
    # the listing form pays no frame for it.
    cored = glued = False
    texts: dict[int, str] = {}
    for i in part:
        text = texts[i] = tokens[i].text
        here = False
        for core in cores:
            if core in text:
                cored = True
                if text not in cores and glues(core):
                    here = glued = True
        if here:
            stem = glued_stem(text, cores)
            if stem is not None:
                texts[i] = stem
    # The words of the class in the part, and the unlisted all-caps
    # words the caps shape could admit: only a part holding one asks
    # the count, so 'Smith, John' and 'John Smith, PhD' never build it.
    maybe = [p[0] for p in p1 if len(p) == 1
             and (AMBIGUOUS_ACRONYM_TAG in (tags := tokens[p[0]].tags)
                  or ("vocab:suffix" not in tags
                      and (texts[p[0]].isalpha()
                           and texts[p[0]].isupper()
                           or not unicodedata.is_normalized(
                               "NFC", texts[p[0]])
                           and is_caps_word(texts[p[0]]))))]
    # rules/C8: "a part that is nothing but suffix words is the
    # credential run and reads as suffixes, whole" -- the reading below.
    # The part is read ONCE: here where it holds no word of the class,
    # after the count below where it does, with the words the count
    # licensed (a read here and a second after licensing threw the first
    # away, #613's /simplify). A part holding a word no vocabulary
    # claims as a suffix, and none of the class, is the given part: the
    # listing form stands. (a declared delimiter's core may sit inside a
    # word, 'RN/CRNA', which only the lenient fallback below reads)
    reading: tuple[bool, ...] | None = None
    # rules/C12's evidence, filtered by the tag and a C-level match so
    # the listing form pays no frame for it ('Smith, John' never calls
    # the helper)
    generation = bool(seg0) and (
        "vocab:suffix-word" in tokens[seg0[-1]].tags
        or ROMAN.match(tokens[seg0[-1]].text) is not None)
    behind_generation = listing = False
    contrast: bool | None = None
    if not maybe:
        reading = segment_suffix_reading(
            p1, pt1, tokens, pol.lenient_comma_suffixes, state.one_case,
            anchored, absorbed)
        # a word no vocabulary claims as a suffix: the listing form,
        # unless C12 reads it below, which skips C1's fallback for it
        listing = reading is None and not all(
            "suffix" in t or "vocab:suffix" in tokens[p[0]].tags
            for p, t in zip(p1, pt1))
        # a part holding a delimiter core ('MD;', 'MD ; PhD') is left
        # to C1's run test below, which reads a core alone as no word
        # and a word with one glued as the word without it (rules/C10)
        if cored:
            listing = False
        if listing and not generation:
            return state
    names = 0
    caps: set[int] = set()
    licensed: set[int] = set()
    run = False
    if maybe:
        names = name_word_count([tokens[i].text for i in seg0], lex, pol,
                                letters_one_case=state.one_case)
    if names >= 2:
        # rules/C6: "An unlisted all-caps word joins the ambiguous
        # credential class [...] only where the name carries the contrast"
        for i in maybe:
            text = texts[i]
            if SHAPE_ACRONYM_TAG in tokens[i].tags:
                # tagged by classify (EVERYWHERE); the dotted shape has
                # a period
                if "." not in text:
                    caps.add(i)
                continue
            if (AMBIGUOUS_ACRONYM_TAG not in tokens[i].tags
                    and pol.unlisted_caps_suffixes is not CapsSuffixes.OFF
                    and caps_shape_candidate(text, lex, pol, one_case=False)):
                if contrast is None:
                    contrast = _name_contrast(state, seg0)
                # a two-capital word is how initials are written: the
                # paired-initials rule below discards one nothing speaks
                # for, a lone one included ('John Smith, XY')
                if contrast:
                    caps.add(i)
        # rules/C4: "The same count reads a part of two or more words
        # as the credential run when every word of it is a suffix word
        # or a word of this class", none of them a single-letter numeral.
        # the words not of the class are asked as C1's suffix test asks
        # them, the lenient word test by default ('Ma B.')
        others: list[str] = []
        for p in p1:
            if len(p) == 1 and (AMBIGUOUS_ACRONYM_TAG in tokens[p[0]].tags
                                or p[0] in caps):
                licensed.add(p[0])
            else:
                # a loop, not a comprehension: a listcomp is a frame
                # per piece on 3.11
                for i in p:
                    others.append(tokens[i].text)
        run = (bool(licensed)
               and (not others or is_wholly_suffix(
                   others, lex, pol, letters_one_case=state.one_case))
               and not any(len(p) == 1
                           and is_single_letter_numeral(texts[p[0]])
                           for p in p1))
        if not run:
            licensed.clear()
        else:
            # rules/C5: "Paired initials are the exception to the [...]
            # count" -- "Only an unambiguous suffix word in front of
            # them that is not also title vocabulary, or another word
            # the class admits by its dotted shape standing in the same
            # part, makes them the credential run"
            shape = {i for i in licensed
                     if i in caps or SHAPE_ACRONYM_TAG in tokens[i].tags}
            # Where the first such suffix word stands, found once and
            # only when a pair asks: a pair is spoken for exactly when
            # it stands behind that word, so one scan answers every
            # pair. Asked per pair, the scan re-walked every word in
            # front of each one, quadratic in the part ('John Smith, ' +
            # 'RA '*k + 'G.J. '*k, the duals never ending it; #563's
            # shape, back in #613 and caught in review)
            speaker = -1
            for k, p in enumerate(p1):
                i = p[0]
                if len(p) != 1 or i not in licensed:
                    continue
                text = texts[i]
                if not (is_paired_initials(text)
                        or (i in caps and composed_len(text) == 2)):
                    continue
                if speaker < 0:
                    speaker = next(
                        (j for j in range(len(p1))
                         if is_suffix_piece(p1[j], pt1[j], tokens)
                         and not is_title_piece(p1[j], pt1[j], tokens)),
                        len(p1))
                # another shape word than this one: no set built per
                # pair (a copy of `shape` each time was quadratic in C)
                if not (speaker < k or len(shape) > 1
                        or (shape and i not in shape)):
                    licensed.discard(i)
                    caps.discard(i)
    if maybe:
        reading = segment_suffix_reading(
            p1, pt1, tokens, pol.lenient_comma_suffixes, state.one_case,
            anchored, absorbed, licensed)
    if not listing:
        if whole is None:
            whole = _whole_name(seg0, tokens)
        # rules/C1: "By default a recognized suffix word counts even
        # written like an initial" -- behind a whole name ('John Smith, V.')
        # rules/C10: "A delimiter glued to a suffix word parts it from
        # the next as a comma glued there would" -- the part "reads as
        # it does with a space in the delimiter's place", behind any
        # head, so 'Smith, MD; PhD' reads as 'Smith, MD PhD' does; behind
        # one that is not a whole name by the strict test, where "A
        # glued word written like an initial is the given name"
        # (decisions/C10, D15)
        if reading is None and (whole or glued) and is_wholly_suffix(
                [tokens[i].text for i in part], lex, pol, one_case=None,
                letters_one_case=state.one_case, strict=not whole):
            reading = (True,) * len(p1)
    # the words of the part C12 reads as suffixes, which its report
    # names: a title in the part, a word or a joined run, is no
    # credential it took
    taken: list[int] = []
    if reading is None and generation:
        reading = _behind_a_generation(state, seg0, p1, pt1, tokens,
                                       contrast)
        if reading is not None:
            behind_generation = True
            for p, suffix in zip(p1, reading):
                if not suffix:
                    continue
                for i in p:
                    taken.append(i)
                    text = texts[i]
                    # #564's marks on an unlisted all-caps word, as the
                    # caps shape writes them, so case repair keeps 'AD'
                    # (rules/R4); the C-level filter `maybe` uses first
                    if ("vocab:suffix" not in tokens[i].tags
                            and (text.isalpha() and text.isupper()
                                 or not unicodedata.is_normalized(
                                     "NFC", text) and is_caps_word(text))):
                        caps.add(i)
    if reading is None:
        return state
    # rules/C7: "that reading is final" -- the part is the postnominal
    # part, bound here whatever stands before the comma. The comma is a
    # suffix comma behind a whole name; behind one name word it stays
    # the family comma naming the family.
    ambiguities = list(state.ambiguities)
    for k, piece in enumerate(p1):
        role = Role.SUFFIX if reading[k] else Role.TITLE
        for i in piece:
            tags = tokens[i].tags
            if i in caps:
                # #564: the caps shape's marks, as classify writes them
                # EVERYWHERE, so case repair keeps 'XYZ' (rules/R4)
                tags = tags | {SHAPE_ACRONYM_TAG, AMBIGUOUS_ACRONYM_TAG}
            tokens[i] = copy_with(tokens[i], role=role, tags=tags)
    # rules/C11: "A decision either way at the comma C1 reads is reported;
    # for a run of words the decision is the flip to the credential
    # run, reported once over the whole part" -- its Then, which this
    # implements, with rules/C11's Then bullet "A run the count leaves
    # in the listing form reports as S7 reads the words in it" and
    # rules/C11's Except bullet "A flip in which no listed word of the
    # ambiguous credential class (C4) takes part is the exception and
    # is made in silence" -- "unless what said so is nothing but other
    # paired initials", the clause that bullet ends on
    # (decisions/C11 (#544)). A run whose every class word is listed and settled by
    # its capitals is read on that evidence, not flipped by the count.
    # A caps word bound above carries the class tags now, so membership
    # is the tag alone; a part with no word of the class has none, and
    # skips the bookkeeping (three list comprehensions, a frame each on
    # 3.11, on every bound part)
    members: list[int] = []
    listed: list[int] = []
    settled = pair_only = False
    if maybe:
        members = [p[0] for p in p1 if len(p) == 1
                   and AMBIGUOUS_ACRONYM_TAG in tokens[p[0]].tags]
        listed = [i for i in members
                  if SHAPE_ACRONYM_TAG not in tokens[i].tags]
        settled = (len(p1) > 1 and bool(members)
                   and len(listed) == len(members)
                   and all(listed_lean(tokens[i], state.one_case)
                           == "credential" for i in listed))
        member_set = frozenset(members)
        pairs = [k for k, p in enumerate(p1) if p[0] in member_set
                 and (is_paired_initials(texts[p[0]])
                      or (p[0] in caps
                      and composed_len(texts[p[0]]) == 2))]
        # spoken for by each other only: every class word a pair, and
        # only titles among the other words in front of the first
        pair_only = (len(pairs) >= 2 and len(pairs) == len(members)
                     and all(p[0] in member_set
                             or is_title_piece(p, pt, tokens)
                             for p, pt in zip(p1[:pairs[0]], pt1)))
    if behind_generation:
        # rules/C11: "A decision either way at the comma C1 reads is
        # reported" -- here the suffix word before the comma decided it,
        # not C4's count, which C12 does not consult
        ambiguities.append(PendingAmbiguity(
            AmbiguityKind.SUFFIX_OR_NAME,
            f"{' '.join(tokens[i].text for i in taken)!r} after the comma "
            f"follows {tokens[seg0[-1]].text!r}, so it is read as a "
            f"credential run; it may be a name", tuple(taken)))
    elif whole and run and ((listed and not settled) or caps or pair_only):
        if len(part) == 1:
            what = (f"{tokens[part[0]].text!r} after the comma is also an "
                    f"ordinary name word")
        else:
            what = (f"{' '.join(tokens[i].text for i in part)!r} after the "
                    f"comma holds a word that is also an ordinary name word")
        ambiguities.append(PendingAmbiguity(
            AmbiguityKind.SUFFIX_OR_NAME,
            f"{what}; the part before the comma holds {names} name words, "
            f"so it is read as a credential run", tuple(part)))
    elif len(p1[0]) == 1 and p1[0][0] in listed:
        # the first word after the comma reports as it always does,
        # naming the role bound above: the listing form binds a word
        # the reading declines as a title ('John, Si.', #793), and no
        # later rule moves a word of the emptied part
        i = p1[0][0]
        field = "a credential" if reading[0] else "a title"
        ambiguities.append(PendingAmbiguity(
            AmbiguityKind.SUFFIX_OR_NAME,
            f"{tokens[i].text!r} after the comma is also an ordinary name "
            f"word; read as {field}", (i,)))
    # rules/S7: "A member the company decides reports the fork as a
    # counted pick does" -- reported where it decided: a member the
    # anchor read as a credential after its own writing declined (#544)
    for k in anchored:
        i = p1[k][0]
        ambiguities.append(PendingAmbiguity(
            AmbiguityKind.SUFFIX_OR_NAME,
            f"{tokens[i].text!r} behind a credential after the comma is "
            f"also an ordinary name word; read as a credential", (i,)))
    # rules/C13: "A credential opening the part after a family comma
    # makes it the postnominal part however it goes on" -- each word it takes that
    # would have made it the given part, as #602's run reports them
    for k in absorbed:
        if has_name_content(p1[k], tokens):
            text = " ".join(tokens[i].text for i in p1[k])
            ambiguities.append(PendingAmbiguity(
                AmbiguityKind.SUFFIX_OR_NAME,
                f"{text!r} follows a credential, so it reads as part of the "
                f"suffix run; it may be a name word", tuple(p1[k])))
    # Every word of the part is bound above or dropped as a core, so the
    # segment hands group nothing to join -- emptied here, where the
    # binding is, as #601's take removes what it binds, rather than
    # filtered out again in group (#613's /simplify)
    return copy_with(state, tokens=tuple(tokens),
                     segments=state.segments[:1] + ((),)
                     + state.segments[2:],
                     structure=(Structure.SUFFIX_COMMA
                                if whole or behind_generation
                                else Structure.FAMILY_COMMA),
                     ambiguities=tuple(ambiguities),
                     dropped=tuple(state.dropped) + tuple(core_idx))
