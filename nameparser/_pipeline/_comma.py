"""Not a stage: rules.md#C1's decision, made by group at its head.

The comma's structure is decided ONCE, after classify has tagged every
word and before group joins any of them (#613): the part after the
first comma is read by `_pieces.segment_suffix_reading`, the one
reading a part that holds no name word gets, with the words C1's count
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
Policy.lenient_comma_suffixes, Policy.extra_suffix_delimiters and
Policy.unlisted_caps_suffixes.
"""
from __future__ import annotations

from collections.abc import Sequence

from nameparser._lexicon import _normalize
from nameparser._pipeline._pieces import (
    has_name_content, is_suffix_piece, join_connectives, listed_lean,
    own_words, segment_suffix_reading,
)
from nameparser._pipeline._state import (
    AMBIGUOUS_ACRONYM_TAG, SHAPE_ACRONYM_TAG, ParseState, PendingAmbiguity,
    Structure, WorkToken, copy_with,
)
from nameparser._pipeline._vocab import (
    D, PH, caps_shape_candidate, claimed_as_non_name, delimiter_cores,
    is_paired_initials, is_single_letter_numeral, is_wholly_suffix,
    name_word_count, surname_unit_facts, unit_ends, written_as_a_name,
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
    # sees it: rules.md#P3's connective joining its neighbours where the
    # neighbour it takes its kind from is a title, which makes the
    # joined part a title ('Mr. and Mrs.', 'Secretary of State', 'Dr.
    # and'), a run of connectives merging first as it does in the name
    # ('Minister of the Interior'). A LONE single-letter connective is
    # left as it stands, P3 reading it as a name word or an initial in
    # short names; one beside another connective is a member of their
    # run and joins with it ('Mr. y and Mrs.'). Any other join is not
    # made here: where no credential opens the part, a name word in it
    # makes it the given part; where one does, the run #603 opens takes
    # the connective as a word and reports it ('John Smith, PhD and
    # Dr.'). Group's own joins, the one loop since #617: its copy here
    # merged no run and joined 'Minister of the' alone.
    #
    # rules.md#P3: "A connective that is also generational vocabulary
    # joins only where a name word stands on each side of it" -- and in
    # a part read for credentials none does, so every such connective
    # is frozen here, where group freezes only the ones it finds without
    # a name word beside them ('Rovira, Dr. i i' keeps suffix 'i i'
    # rather than run-merging the pair into the title, #617). Frozen
    # means no join or run of its OWN: a neighbour's join may still take
    # it in, as in group ('Smith, Dr. and i' reads title 'Dr. and i').
    #
    # The same walk says whether there is anything to join, and a part
    # with no connective left free -- nearly every part -- skips the
    # shared loop, whose predicate calls cost a frame per word ('Smith,
    # John' paid two; #617's review).
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


def _name_contrast(state: ParseState, seg0: Sequence[int]) -> bool:
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
    with no lowercase at all is settled in one C-level comparison."""
    before = "".join([state.tokens[i].text for i in seg0])
    if before == before.upper():
        return False
    _, clause_at = own_words(state.tokens, state.comma_offsets,
                             state.lexicon.maiden_markers)
    lex = state.lexicon
    return any(
        i < clause_at and (tok := state.tokens[i]).role is None
        and "." not in tok.text and written_as_a_name(tok.text)
        and not claimed_as_non_name(_normalize(tok.text), lex)
        for i in seg0)


def _whole_name(seg0: Sequence[int], tokens: Sequence[WorkToken]) -> bool:
    """rules.md#C1's count before the comma for an unambiguous
    credential, read off classify's tags (the ambiguous class's count
    of NAME words, which leaves titles out, is
    `_vocab.name_word_count`'s, asked in `decide`): two or more units (a particle run and
    the name word it attaches to one unit, a connective join not, #575)
    holding a word that is not a suffix word -- a title counts, being a
    word to the count an unambiguous credential takes."""
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
    # rules.md#C1: "A delimiter the policy declares parts a trailing
    # suffix part as a comma would" -- behind a whole name its cores are
    # no word of the reading, and leave as group drops them in a tail;
    # behind one name word the core is a word, v1 having applied the
    # delimiter to the suffix-comma form alone (C1's Accepted entry)
    cores = delimiter_cores(pol.extra_suffix_delimiters)
    whole: bool | None = None
    core_idx: list[int] = []
    if cores and len(seg1) > 1:
        whole = _whole_name(seg0, tokens)
        if whole:
            core_idx = [i for i in seg1 if tokens[i].text in cores]
    # a set for the membership test: a list scanned per token was
    # quadratic in the part (#613's PR review, 'MD / '*k under '/')
    core_set = frozenset(core_idx)
    part = [i for i in seg1 if i not in core_set] if core_idx else list(seg1)
    if not part:
        return state
    p1, pt1 = _reading_pieces(part, tokens)
    anchored: list[int] = []
    absorbed: list[int] = []
    # The words of the class in the part, and the unlisted all-caps
    # words the caps shape could admit: only a part holding one asks
    # the count, so 'Smith, John' and 'John Smith, PhD' never build it.
    maybe = [p[0] for p in p1 if len(p) == 1
             and (AMBIGUOUS_ACRONYM_TAG in (tags := tokens[p[0]].tags)
                  or ("vocab:suffix" not in tags
                      and tokens[p[0]].text.isalpha()
                      and tokens[p[0]].text.isupper()))]
    # The part is read ONCE: here where it holds no word of the class,
    # after the count below where it does, with the words the count
    # licensed (a read here and a second after licensing threw the first
    # away, #613's /simplify). A part holding a word no vocabulary
    # claims as a suffix, and none of the class, is the given part: the
    # listing form stands. (a declared delimiter's core may sit inside a
    # word, 'RN/CRNA', which only the lenient fallback below reads)
    reading: tuple[bool, ...] | None = None
    if not maybe:
        reading = segment_suffix_reading(
            p1, pt1, tokens, pol.lenient_comma_suffixes, state.one_case,
            anchored, absorbed)
        if reading is None and not cores and not all(
                "suffix" in t or "vocab:suffix" in tokens[p[0]].tags
                for p, t in zip(p1, pt1)):
            return state
    names = 0
    caps: set[int] = set()
    licensed: set[int] = set()
    run = False
    if maybe:
        names = name_word_count([tokens[i].text for i in seg0], lex, pol)
    if names >= 2:
        # rules.md#C1: "An unlisted all-caps word joins the class in such
        # a part only where the name carries the contrast"
        contrast: bool | None = None
        for i in maybe:
            text = tokens[i].text
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
        # rules.md#C1: "The same count reads a part of two or more words
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
               and (not others or is_wholly_suffix(others, lex, pol))
               and not any(len(p) == 1
                           and is_single_letter_numeral(tokens[p[0]].text)
                           for p in p1))
        if not run:
            licensed.clear()
        else:
            # rules.md#C1: "Paired initials are the exception to the
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
            # 'MD '*k + 'G.J. '*k, the duals never ending it; #563's
            # shape, back in #613 and caught in review)
            speaker = -1
            for k, p in enumerate(p1):
                i = p[0]
                if len(p) != 1 or i not in licensed:
                    continue
                text = tokens[i].text
                if not (is_paired_initials(text)
                        or (i in caps and len(text) == 2)):
                    continue
                if speaker < 0:
                    speaker = next(
                        (j for j in range(len(p1))
                         if is_suffix_piece(p1[j], pt1[j], tokens)
                         and not (len(p1[j]) == 1
                                  and "vocab:title"
                                  in tokens[p1[j][0]].tags)),
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
    if whole is None:
        whole = _whole_name(seg0, tokens)
    # rules.md#C1: "By default a recognized suffix word counts even
    # written like an initial" -- behind a whole name ('John Smith, V.')
    if reading is None and whole and is_wholly_suffix(
            [tokens[i].text for i in part], lex, pol, one_case=None):
        reading = (True,) * len(p1)
    if reading is None:
        return state
    # The part is the postnominal part, bound here whatever stands
    # before the comma. The comma is a suffix comma behind a whole name;
    # behind one name word it stays the family comma naming the family.
    ambiguities = list(state.ambiguities)
    for k, piece in enumerate(p1):
        role = Role.SUFFIX if reading[k] else Role.TITLE
        for i in piece:
            tags = tokens[i].tags
            if i in caps:
                # #564: the caps shape's marks, as classify writes them
                # EVERYWHERE, so case repair keeps 'XYZ' (rules.md#R4)
                tags = tags | {SHAPE_ACRONYM_TAG, AMBIGUOUS_ACRONYM_TAG}
            tokens[i] = copy_with(tokens[i], role=role, tags=tags)
    # rules.md#C1: "A decision either way at this comma is reported;
    # for a run of words the decision is the flip to the credential
    # run, reported once over the whole part. A flip in which no listed
    # word of this class takes part is the exception and is made in
    # silence" -- "unless what said so is nothing but other paired
    # initials". A run whose every class word is listed and settled by
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
                 and (is_paired_initials(tokens[p[0]].text)
                      or (p[0] in caps and len(tokens[p[0]].text) == 2))]
        # spoken for by each other only: every class word a pair, and
        # only titles among the other words in front of the first
        pair_only = (len(pairs) >= 2 and len(pairs) == len(members)
                     and all(p[0] in member_set
                             or (len(p) == 1
                                 and "vocab:title" in tokens[p[0]].tags)
                             for p in p1[:pairs[0]]))
    if whole and run and ((listed and not settled) or caps or pair_only):
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
        # the first word after the comma reports as it always does
        i = p1[0][0]
        ambiguities.append(PendingAmbiguity(
            AmbiguityKind.SUFFIX_OR_NAME,
            f"{tokens[i].text!r} after the comma is also an ordinary name "
            f"word; read as a credential", (i,)))
    # rules.md#S2's company, reported where it decided: a member the
    # anchor read as a credential after its own writing declined (#544)
    for k in anchored:
        i = p1[k][0]
        ambiguities.append(PendingAmbiguity(
            AmbiguityKind.SUFFIX_OR_NAME,
            f"{tokens[i].text!r} behind a credential after the comma is "
            f"also an ordinary name word; read as a credential", (i,)))
    # rules.md#C1: "A credential opening the part makes it the
    # postnominal part however it goes on" -- each word it takes that
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
                     structure=(Structure.SUFFIX_COMMA if whole
                                else Structure.FAMILY_COMMA),
                     ambiguities=tuple(ambiguities),
                     dropped=tuple(state.dropped) + tuple(core_idx))
