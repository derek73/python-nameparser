"""Stage: post_rules.

Consumes: tokens (roles assigned), plus pieces and structure -- the
particle fold reads the opening piece of segment 0, or of segment 1
under a family comma (#359). structure was always read here, for the
rotation gate. Also comma_offsets and dropped, which R1's entry pass
below reads to find the separators the writer typed (#436/#437), and
extracted, one_case and original, which S1's set-apart pass reads,
settling S13's members with its own (#810, #792), original also read
by R1's entry pass for a comma a set-apart clause kept; and order,
the order assign read the name under, which H1, P1's fold, P6's
attachment, P10, O1, O2, O6 and O7 key on rather than
Policy.name_order (#395).
Produces: tokens with roles adjusted by the post rules (among them the
TITLE and SUFFIX roles of a set-apart clause's words, rules/S1, each
word's comma trimmed off its text and span, and the
SUFFIX role of a delimited member its writing settles after the name,
rules/S13, with the SUFFIX_OR_NICKNAME report on any other member left
a nickname), the stable
"joined" tag on a post-nominal continuing the entry before it, the
folded-middle tag on the words O3 folds and P6's no-comma attachment
joins to the family, with the attached tag on the latter (rules/R9
tells the two apart by it), the second-surname tag on each word of the
family's second unit where O6 reads two (rules/R10), the first-surname
tag on each word of the first unit, written by O6 where it reads two
and by O3 on the family it folds into otherwise (rules/R11), and the ambiguity P6's attachment reports at the end of a name read
family-first (#467) -- after a family comma, that attachment is
assign's since #613, and behind an empty part before the comma too
since #892.
Reads: Policy.patronymic_rules, Policy.two_family_names,
Policy.two_given_names, Policy.name_order (O6 and O7 stand down where
the script's order differs from the declared one),
Policy.middle_as_family,
Policy.extra_suffix_delimiters (R1's entry pass, for the delimiter
cores group drops); Lexicon.given_name_titles, Lexicon.given_names
(O6's veto), Lexicon.saint_particles (P10's saint clause; P10 runs
under every policy and reads Policy.patronymic_rules for its Turkic
guard), and
Lexicon.suffix_acronyms_ambiguous (a dotted member in a clause, which
carries no tag there, S13, through `_vocab.dotted_member`), and for S1's set-apart clause
Lexicon.suffix_words directly and, through `_vocab.set_apart_kind` and
`set_apart`, Lexicon.suffix_words_ambiguous, suffix_acronyms, titles,
title_modifiers, title_styles and after_given_titles.

Implements rules S1, S13, H1, M4, P1, P6 (its no-comma site), P10, O1, O2,
O6, O7, O3 and R1 of docs/design/rules/; each is cited at its code below, and
H1/P1/O1/O2's history lives in docs/design/decisions/.
`suffix_entries` is the R1 entry pass as a state-in/state-out
function, for Parser.revise to run over a forced-role sub-parse
(#511); `post_rules` runs the same worker last.
"""
from __future__ import annotations

import bisect
from collections.abc import Sequence

from nameparser._lexicon import Lexicon, _normalize, _run_addresses_by_given
from nameparser._pipeline._assign import (
    _name_alt, _name_pieces, _name_positions,
)
from nameparser._pipeline._pieces import (
    is_lone_never_given_particle, is_lowercase_ambiguous_particle,
    settled_by_case,
)
from nameparser._pipeline._state import (
    AMBIGUOUS_ACRONYM_TAG, ATTACHED_TAG, NAME_ROLES, PATRONYMIC_TAG,
    BOUND_PHRASE_TAG, PARTICLE_GIVEN_TAG, PAST_REACH_TAG, SHARED_NAME_TAG,
    FIRST_SURNAME_TAG, SECOND_SURNAME_TAG,
    ParseState, PendingAmbiguity, PendingReading, Structure,
    WorkToken, _NEVER_FLIPPED, comma_bucket, copy_with, reported_suffix_fork,
)
from nameparser._pipeline._vocab import (
    _HYPHENS, SetApartKind, delimiter_cores, dotted_member,
    has_patronymic_ending, is_initial, is_listed_given_name,
    is_patronymic_marker, reads_as_initials, set_apart, set_apart_kind,
    suffix_reading, unit_ends,
)
from nameparser._policy import PatronymicRule
from nameparser._types import (
    FOLDED_TAG, UNJOINED_CONJUNCTION_TAG, UNJOINED_TAG, AmbiguityKind, Role,
    Span,
)


#: The roles that are transparent to a run of post-nominals (R1's
#: entry pass below). These three roles render into fields other than
#: the name and the suffix, so a run of
#: post-nominals is not parted by them -- 'Smith, MD Dr. PhD',
#: 'Smith, MD "Doc" PhD' and 'Smith, MD nee Jones PhD' are each one
#: entry. GIVEN/MIDDLE/FAMILY are name words and part it.
_RENDERS_ELSEWHERE = frozenset({Role.TITLE, Role.NICKNAME, Role.MAIDEN})


def _rotations_apply(state: ParseState) -> bool:
    # Both patronymic rotations RESTORE the given-first reading a
    # family-first listing hides, so rules/O1's scope clause holds
    # them to the default order: a caller who declared family-first has
    # already said what the rotation would infer, and position decides
    # (decisions/O1, the 2026-09-07 entry on #384). `state.order`,
    # not policy.name_order, for the reason the P1 fold gives -- a
    # script_orders entry can override the policy, and the roles the
    # rotations read are the ones assign actually made. None means
    # assign positioned nothing: a family comma (which the NO_COMMA
    # test already excludes) or an early return with no name piece to
    # position, so there is no declaration to defer to and the
    # rotation's own shape test decides.
    return state.structure is Structure.NO_COMMA and (
        state.order is None or state.order[0] is Role.GIVEN)


def _mark_suffix_entries(tokens: list[WorkToken], state: ParseState) -> None:
    # In place over the caller's token list, as every other post rule
    # writes; suffix_entries() below is the state wrapper, and
    # decisions/R1 (#511) records why the pass has two spellings.
    # Reads dropped, comma_offsets and the policy off `state`, which
    # post_rules does not change, so the un-rebuilt state is current.
    #
    # rules/R1: "a run of post-nominals written with spaces renders
    # with spaces, and one written with commas keeps them"
    #
    # Two consecutive SUFFIX tokens are one entry iff they share a
    # comma bucket and nothing between them parts the run: a name word
    # or a dropped delimiter core parts it; a token whose role is in
    # _RENDERS_ELSEWHERE, or a dropped token that is not a core (the
    # marker of a bracketed maiden clause, 'Smith, MD (nee Jones)
    # PhD'), does not. comma_bucket and delimiter_cores
    # are segment's and group's own answers, called rather than copied
    # (mechanisms.md#ONE-PREDICATE-PER-QUESTION). decisions/R1
    # (#436/#437).
    #
    # After assign, because it keys on Role.SUFFIX; last in post_rules,
    # after S13's pass, the one rule here that writes SUFFIX (#810), and
    # by convention otherwise, since no other writes SUFFIX or a
    # _RENDERS_ELSEWHERE role. Recorded as a tag because a span-less
    # token (unpickled, or built by replace()) leaves the render
    # nothing to scan (mechanisms.md#MARK-DONT-STRIP). Every WorkToken
    # has a span, so `span.start` is read unguarded, and the
    # `i not in dropped` filter is belt-and-braces: a dropped token
    # never holds SUFFIX, and the filter keeps `suffixes` and the
    # `parted` scan agreeing on what a dropped index is.
    dropped = set(state.dropped)
    cores = delimiter_cores(state.policy.extra_suffix_delimiters)
    suffixes = [i for i, tok in enumerate(tokens)
                if tok.role is Role.SUFFIX and i not in dropped]
    for previous, current in zip(suffixes, suffixes[1:]):
        same_part = (comma_bucket(tokens[previous].span.start,
                                  state.comma_offsets)
                     == comma_bucket(tokens[current].span.start,
                                     state.comma_offsets))
        parted = any(
            tokens[between].text in cores if between in dropped
            else tokens[between].role not in _RENDERS_ELSEWHERE
            for between in range(previous + 1, current)) or (
            # rules/S1: "parts its words as a comma between them would"
            # -- a comma a set-apart clause kept on a word, which no
            # comma bucket holds and S1's pass trimmed off the word;
            # decisions/S1 (#792)
            state.original[tokens[previous].span.end:
                           tokens[previous].span.end + 1] == ","
            or state.original[tokens[previous].span.end:
                              tokens[current].span.start].replace(" ", "")
            == ",")
        if same_part and not parted:
            tokens[current] = copy_with(
                tokens[current], tags=tokens[current].tags | {"joined"})


def suffix_entries(state: ParseState) -> ParseState:
    """rules/R1's entry pass over a whole state, wrapping
    _mark_suffix_entries: tag a SUFFIX token "joined" when it
    continues the entry of the SUFFIX token before it. post_rules runs
    the worker last, over the roles assign settled; this wrapper exists
    for Parser.revise (#511), which runs it over a SUB-PARSE of a field
    value whose every non-dropped token it has forced to the named
    role, so a suffix value derives its entries from its own commas by
    the rule a whole name uses. The pass ADDS the tag and never removes
    one; a caller forcing roles keeps what the sub-parse marked, a
    within-piece mark being role-blind (decisions/R1, the #436
    DECLINED list) and every between-piece mark on a suffix value
    being one this pass sets again. Reads comma_offsets, dropped and
    Policy.extra_suffix_delimiters; writes the "joined" tag and
    nothing else."""
    tokens = list(state.tokens)
    _mark_suffix_entries(tokens, state)
    return copy_with(state, tokens=tuple(tokens))


def _positions(tokens: list[WorkToken],
               ) -> tuple[list[int], list[int], list[int], list[int]]:
    """The positions of the TITLE, GIVEN, MIDDLE and FAMILY tokens, in
    that order, each list ascending: the four roles post_rules' rules
    read as position lists, in one walk however many of them the caller
    wants."""
    # one plain loop, where a comprehension per role cost a frame of its
    # own on 3.11 beside the call's, and post_rules asks for the lists on
    # every parse (the parse-cost band, decisions/parse-cost, #1089)
    titles: list[int] = []
    givens: list[int] = []
    middles: list[int] = []
    families: list[int] = []
    by_role: dict[Role | None, list[int]] = {
        Role.TITLE: titles, Role.GIVEN: givens,
        Role.MIDDLE: middles, Role.FAMILY: families}
    for i, token in enumerate(tokens):
        part = by_role.get(token.role)
        if part is not None:
            part.append(i)
    return titles, givens, middles, families


def _leading_name_piece(state: ParseState,
                        tokens: list[WorkToken]) -> tuple[int, ...]:
    """The piece that OPENS the name, whatever role name_order gave it:
    the first piece holding a GIVEN, MIDDLE or FAMILY token, in the
    segment the positional read governs. Every piece holding none of
    those is walked past -- title and suffix pieces, but NICKNAME and
    MAIDEN as well, and anything assign left unroled -- and any number
    of them, not only a single leading title. The segment is 0, except
    under a family comma that fixed the surname, where the name
    continues in segment 1 -- assign records no order there. A family
    comma followed by no name word fixed nothing, and assign reads
    segment 0 positionally and records the order (#296's bundle), so
    the name is segment 0 again. Empty on either of two exits: that
    segment does not exist, or none of its pieces holds a name
    token."""
    seg = (1 if state.structure is Structure.FAMILY_COMMA
           and state.order is None else 0)
    if seg >= len(state.pieces):
        return ()
    for piece in state.pieces[seg]:
        if any(tokens[i].role in NAME_ROLES for i in piece):
            return piece
    return ()


def _retag(tokens: list[WorkToken], i: int, role: Role) -> None:
    tokens[i] = copy_with(tokens[i], role=role)


# rules/P2: "a particle joins the words after it into one name
# part, the join running until the next particle starts a group of
# its own, a trailing suffix begins"
# rules/P3: "the joined part is ONE name word wherever another
# rule counts them"
# rules/P5: "a recognized bound given-name word joins the word
# after it into one given name"
def _units(tokens: list[WorkToken], idx: list[int]) -> list[list[int]]:
    """`idx` split into the units other rules COUNT: one name word
    each, except where another rule has already made several words one
    name. Three do -- a particle and the words it chains, a
    conjunction-joined run, and a bound given-name word with the word
    it completes -- so `van der Berg` and `abdul Rahman` are each one
    unit and the fold cannot leave half of either behind.

    Read off the TAGS rather than the pieces, for two different
    reasons. A conjunction join grouping DID build and the prefix
    chain then swallowed: "de la Vega y Santos Juan" reaches this as
    [de][la Vega y Santos Juan], the ambiguous particle having chained
    forward over the join, so the join's own boundary is gone. (The
    leading particle keeps its piece -- it has to, or the fold's
    lone-piece site test would not fire at all.) The bound-given join grouping
    never built at all: P5 joins only where the bound word is the
    first non-title piece, save a listed two-word given name P12
    joins past the first name word (#694), and at a fold site the first piece
    is the particle -- "ibn Awf abdul Rahman" reaches here as four
    separate pieces. The tag is the only witness in both cases.

    The particle chain is what keeps this partition agreeing with the
    one `assign` reads off pieces: strip the folded run and `assign`
    gives the same tail one role, so the fold must not hand its words
    out separately."""
    units: list[list[int]] = []
    i = 0
    for end in unit_ends([tokens[k].tags for k in idx]):
        units.append(list(idx[i:end]))
        i = end
    return units


def _fold_reach(tokens: list[WorkToken], name_idx: list[int]) -> int:
    """How many of `name_idx` the fold takes: the particle run, plus
    the one name word it attaches to -- one UNIT, so a conjunction
    join goes whole ("de la Vega y Santos Juan" keeps Vega y Santos
    together). All of them when the name is nothing but particles."""
    i = 0
    while i < len(name_idx) and "particle" in tokens[name_idx[i]].tags:
        i += 1
    if i == len(name_idx):
        return i
    return i + len(_units(tokens, name_idx[i:])[0])




def _family_word_count(tokens: list[WorkToken], family: list[int],
                       hyphen_joins: bool = False) -> int:
    """The family's name words as rules/O6 counts them: a particle run
    counts with the word it attaches to, a connective counts as
    nothing and a hyphen joins words without making them one, so "de
    la Vega" is one word and "Ortega y Gasset" and "García-López" two.
    A family of nothing but particles counts each of them, R2 reading
    them as ordinary name words. `hyphen_joins` counts a hyphenated word
    as one, as the word O6 takes is counted (#959). A bound word counts
    with the word that completes it, the pair P12 joins being one name
    ('عبد الله', #694)."""
    # rules/P12: "the two words are one name unit past the first name word"
    # -- so the bound word counts with the word after it
    words = sum(1 if hyphen_joins
                else len([part for part in _HYPHENS.split(tokens[i].text)
                          if part])
                for i in family
                if "particle" not in tokens[i].tags
                and "conjunction" not in tokens[i].tags
                and BOUND_PHRASE_TAG not in tokens[i].tags)
    return words or len(family)


def _hyphenated_given(text: str, lexicon: Lexicon) -> bool:
    """A hyphenated word that writes given names, which the taken word's
    count (a hyphenated word counting as one) would otherwise let through
    (#959): every part of it a listed given name or an initial
    ("María-José" under the Spanish list, "M.-J.", "M.-José")."""
    parts = [part for part in _HYPHENS.split(text) if part]
    return len(parts) > 1 and all(is_initial(part) or is_listed_given_name(part, lexicon)
               for part in parts)


def _take_second_family_name(state: ParseState,
                             tokens: list[WorkToken]) -> None:
    # rules/O6: "the family name takes the name word beside it, so
    # the last two name words are the family" -- the first two under
    # a family-first order. In place, as every post rule writes.
    # History: decisions/O6 (#754).
    # An order a name's script set (W4) other than the declared one is
    # not the caller's declaration, and no script it keys writes two
    # family names as separate words. Where the two agree nothing here
    # tells them apart, and the rule reads the name (rules/O6 Accepted).
    if (state.structure is Structure.FAMILY_COMMA or state.order is None
            or state.order != state.policy.name_order):
        return
    _, given, middle, family = _positions(tokens)
    others = sorted(given + middle)
    if not family or _family_word_count(tokens, family) != 1:
        return
    # The rest in the units assign read them as, so a particle chain
    # (P2) or a bound given-name pair (P5) moves whole or not at all.
    units = _units(tokens, others)
    # rules/O6: "a particle chain after the family is cut where P1's
    # family-first fold cuts its own run" -- under a family-first order,
    # the given name the order declares after the chain left to the
    # order (decisions/O6, #1024); under the default order the chain
    # ends the name and stays whole
    if state.order[0] is not Role.GIVEN and units:
        cut = _fold_reach(tokens, units[0])
        if cut < len(units[0]):
            units[:1] = [units[0][:cut], *_units(tokens, units[0][cut:])]
    if len(units) < 2:
        return
    take = units[-1] if state.order[0] is Role.GIVEN else units[0]
    # What is taken must be ONE name word, so a bound given-name pair
    # (P5) stays put; rules/O6: "A hyphenated word counts as one when it
    # is the word taken" (decisions/O6, #959), where the family's own
    # hyphen counts two; and a word a family name could be: not an
    # initial, which writes a given name (one written alone; "J.R." is
    # taken), nor a lone dash or other mark with no letter in it.
    if _family_word_count(tokens, take, hyphen_joins=True) != 1:
        return
    if len(take) == 1 and "initial" in tokens[take[0]].tags:
        return
    if not any(ch.isalpha() for i in take for ch in tokens[i].text):
        return
    # rules/O6: "a listed given name stays where it is" -- the caller's
    # Lexicon.given_names (empty by default; locales.ES carries the
    # Spanish list, with the switch on) names a word only a given name is, under
    # either order. Only a unit of one token is asked: a word
    # behind a particle ("de Miguel") is a unit of two, a surname taken
    # as before. History: decisions/O6 (#959).
    # A hyphenated word writing given names stays too (#959).
    if len(take) == 1 and (
            is_listed_given_name(tokens[take[0]].text, state.lexicon)
            or _hyphenated_given(tokens[take[0]].text, state.lexicon)):
        return
    # rules/O6: "a name a community gives every member is no family
    # name of two" -- Kaur and Singh, on either side of the join, tagged
    # at classify from Lexicon.shared_names (decisions/O6, #704)
    if any(SHARED_NAME_TAG in tokens[i].tags for i in take + family):
        return
    # rules/O6: "a given name a particle completes stays where it is" --
    # given-first, the unit taken being the one beside a given name of
    # one word, a particle run and a word classify tags from
    # Lexicon.particle_given_names, in the shape rules/P10 reads; under a
    # family-first order the unit after the family completes no given
    # name (decisions/O6, #704)
    if (state.order[0] is Role.GIVEN and len(units) == 2
            and _one_given_word(tokens, units[0])
            and all(tokens[i].role is Role.GIVEN for i in units[0])
            and _completes_a_given_name(tokens, take, state.lexicon)):
        return
    if state.order[0] is Role.GIVEN:
        # given, middles..., family: the middle unit standing right
        # before the family joins it, and text order already renders
        # it first, so no role around it moves. A rotation that left
        # the name in another shape fails this test.
        if take[-1] > family[0] or any(
                tokens[i].role is not Role.MIDDLE for i in take):
            return
        _mark_surname(tokens, take, FIRST_SURNAME_TAG)
        _mark_surname(tokens, family, SECOND_SURNAME_TAG)
        return
    # family first: the unit after the family joins it, and what is
    # left is a shorter name of the same order, laid out as the P1
    # fold above lays its remainder -- one family already placed. A
    # particle P6 attached at the far end is family already and keeps
    # its place.
    if family[0] > units[0][0]:
        return
    # the unit taken joins the family as its second
    _mark_surname(tokens, family, FIRST_SURNAME_TAG)
    _mark_surname(tokens, units[0], SECOND_SURNAME_TAG)
    for unit, role in zip(units[1:], _name_positions(
            state.order, len(units))[1:]):
        for i in unit:
            _retag(tokens, i, role)


def _one_given_word(tokens: list[WorkToken], given: list[int]) -> bool:
    """Whether the given name is ONE word, as rules/O7 and P10 count it: O6's
    count, save that a bound given-name pair (P5) is two words though
    its bound word is also a particle the count passes over ('Abu
    Bakr')."""
    return (_family_word_count(tokens, given) == 1
            and not (len(given) > 1
                     and "vocab:bound-given" in tokens[given[0]].tags))


def _completes_a_given_name(tokens: list[WorkToken], unit: list[int],
                            lexicon: Lexicon) -> bool:
    """Whether `unit` is a particle run and ONE word written
    `after_particle` ('del Carmen'), the second of a compound given name
    as rules/P10 reads one; a run holding a saint particle ('Santa
    María') opens a surname instead."""
    n = 0
    while n < len(unit) and "particle" in tokens[unit[n]].tags:
        if _normalize(tokens[unit[n]].text) in lexicon._sets.saint_particles:
            return False
        n += 1
    return (0 < n == len(unit) - 1
            and PARTICLE_GIVEN_TAG in tokens[unit[-1]].tags)


def _given_phrase_middle(state: ParseState,
                         tokens: list[WorkToken]) -> None:
    # rules/P10: "the particle run and that word are a middle name" --
    # behind a lone given name of one word, read given-first with no
    # family comma, the family's opening particle run and the one word
    # after it, read off the tag classify gives a word of
    # Lexicon.particle_given_names, where a name word is left for the
    # family (decisions/P10, #704). In place, as every post rule writes.
    # A family comma reads the phrase as a middle already, and a
    # family-first order puts no family behind the given name.
    # Called only for a name holding a marked word (post_rules' loop).
    if (state.structure is Structure.FAMILY_COMMA or state.order is None
            or state.order[0] is not Role.GIVEN):
        return
    _, given, middle, family = _positions(tokens)
    # a given name no patronymic, shared name or mark, of one word, with
    # no middle between it and the family
    if (not given or not family or middle
            or family[0] < given[-1]
            or not _one_given_word(tokens, given)
            or any(PATRONYMIC_TAG in tokens[i].tags
                   or SHARED_NAME_TAG in tokens[i].tags for i in given)
            or not any(ch.isalpha() for i in given for ch in tokens[i].text)):
        return
    cut = _fold_reach(tokens, family)
    if cut >= len(family) or not _completes_a_given_name(
            tokens, family[:cut], state.lexicon):
        return
    # a name word left for the family: one with a letter that is no
    # connective standing alone ('María del Carmen y')
    if not any(any(ch.isalpha() for ch in tokens[i].text)
               and "conjunction" not in tokens[i].tags
               for i in family[cut:]):
        return
    # and no Turkic marker behind the phrase, whose father's name it
    # would be
    if (PatronymicRule.TURKIC in state.policy.patronymic_rules
            and is_patronymic_marker(tokens[family[cut]].text)):
        return
    for i in family[:cut]:
        _retag(tokens, i, Role.MIDDLE)


def _take_second_given_name(state: ParseState,
                            tokens: list[WorkToken]) -> None:
    # rules/O7: "the given name takes the middle unit beside it" --
    # O6's mirror, read after O6 has taken its word and before O3
    # folds what is left. In place, as every post rule writes.
    # History: decisions/O7 (#704).
    # A family comma leaves the given part laid out given-first; without
    # one, an order the script set (W4) is not the caller's, as for O6.
    if state.structure is Structure.FAMILY_COMMA:
        given_first = True
    elif state.order is None or state.order != state.policy.name_order:
        return
    else:
        given_first = state.order.index(Role.GIVEN) < state.order.index(
            Role.MIDDLE)
    _, given, middle, _ = _positions(tokens)
    # a given name already holding two words keeps what it has: a
    # hyphenated one, or a bound given-name pair (P5), counted as O6
    # counts the family
    if not given or not middle or not _one_given_word(tokens, given):
        return
    # the unit beside the given name: the positions lay a given-first
    # part out given, middles..., and FAMILY_FIRST_GIVEN_LAST's
    # middles..., given, so it is the first middle unit or the last
    units = _units(tokens, middle)
    take = units[0] if given_first else units[-1]
    # ONE name word, counted as O6 counts one, with a letter in it; an
    # initial is taken, since it writes a given name. A given name with
    # no letter in it is a mark or a number, nothing to complete.
    if (_family_word_count(tokens, take) != 1
            or not any(ch.isalpha() for i in take for ch in tokens[i].text)
            or not any(ch.isalpha() for i in given for ch in tokens[i].text)):
        return
    # a patronymic is no given name, on either side of the join: a
    # patronymic particle's run, its reading decided at classify (R9's
    # vocabulary arm), whether it is the unit taken or the given name
    # itself; a word an ending rule a policy turns on reads as one; and
    # a Turkic marker's father
    if any(PATRONYMIC_TAG in tokens[i].tags for i in take + given):
        return
    # rules/O7: "a name a community gives every member is no given
    # name" -- Kaur and Singh, on either side of the join, tagged at
    # classify from Lexicon.shared_names (decisions/O7, #704)
    if any(SHARED_NAME_TAG in tokens[i].tags for i in take + given):
        return
    rules = state.policy.patronymic_rules
    if rules:
        slavic = PatronymicRule.EAST_SLAVIC in rules
        turkic = PatronymicRule.TURKIC in rules
        after = take[-1] + 1
        if any(slavic and has_patronymic_ending(tokens[i].text)
               or turkic and is_patronymic_marker(tokens[i].text)
               for i in take) or (
                turkic and after < len(tokens)
                and is_patronymic_marker(tokens[after].text)):
            return
    for i in take:
        _retag(tokens, i, Role.GIVEN)


# rules/R10: "the family's second name unit, the one written second,
# makes the second-surname view" -- whichever of the two O6 took
# (decisions/R10, #754); and rules/R11: "the family's first name unit,
# the one written first, makes the first-surname view" -- the other one,
# marked in the same place (decisions/R11, #1022). It moves a unit into
# the family as it marks it, one copy per word (frame budget).
def _mark_surname(tokens: list[WorkToken], unit: list[int],
                  tag: str) -> None:
    for i in unit:
        tokens[i] = copy_with(tokens[i], role=Role.FAMILY,
                              tags=tokens[i].tags | {tag})


def _addressing_run(titles: list[int], name_word: int) -> list[int]:
    """The title run H1 asks about: the LEADING one where one stands,
    else the whole (trailing) run -- rules/H1 -- the run standing
    BEFORE the one name word being the run that addresses, and a run
    standing behind it deciding that word's field only when none
    stands before.

    Every title token is in the TITLE role by the time this runs, both
    ends of `Sir John Prof.` among them, so `titles` is not a run --
    keeping the two ends apart is what makes a trailing title
    TRANSPARENT (rules/H5): `Sir John Prof.` is `Sir John` plus a
    title, and reading both ends as one run keyed 'sir prof' made
    adding the title flip the name word's field (#489, #316).

    The split is at the NAME WORD, not at the first token of another
    role, and the difference is a nickname or a maiden name written
    among the titles. H1's own rationale says what stands beside the
    name word "does not make the name any longer, so it does not
    decide this reading", and that has to hold for WHICH run
    addresses as well as for how many words the name has: `Dr.
    'Smitty' Sir John` is one run written around a nickname and reads
    given 'John' as `Dr. Sir John` does, while `'Smitty' Dr. Jones
    Sir.` keeps family 'Jones' as `Dr. Jones Sir.` does. Splitting on
    the first non-title token got both wrong (measured 2026-09-09).

    Called only from inside H1's guard, after the role counts have
    short-circuited, so a name with both a given and a family never
    builds this list; `name_word` is the first GIVEN, or the first
    FAMILY in the direction #720 added. The given guard has proved it
    is the only name word there is; the family guard proves only that
    no given or middle stands beside it, which is where a comma or a
    declared order leaves one name word."""
    return [i for i in titles if i < name_word] or titles


def _family_settled(state: ParseState, tokens: list[WorkToken],
                    families: list[int]) -> bool:
    """Whether something other than the order placed this lone family
    word, so H1's family -> given direction leaves it (#720). After a
    comma a particle in it is settled -- rules/C3's "the comma settles
    P1's fork for a leading particle that could be a given name"
    ('van Gogh, Sir'); without one, P1's fold below takes a never-given
    particle opening the name with a word behind it ('Sir de Mesnil'),
    or under a family-first order a piece `_family_first_lead_folds`
    names ('Sir van Berg', rules/P11), asked by the fold's own
    predicates on the same piece. An ambiguous particle
    nothing settled, or a bare one with nothing to fold, is a
    word the order placed ('Sir Van', 'Sir Abu Bakar' and 'Sir de'
    under FAMILY_FIRST; 'Sir von und zu', whose never-given 'zu' does
    not open it)."""
    if state.structure is Structure.FAMILY_COMMA:
        return any("particle" in tokens[i].tags for i in families)
    if len(families) < 2:
        return False
    lead = _leading_name_piece(state, tokens)
    return (is_lone_never_given_particle(lead, tokens)
            or state.order is not None and state.order[0] is Role.FAMILY
            and _family_first_lead_folds(state, tokens, lead))


def _family_first_lead_folds(state: ParseState, tokens: list[WorkToken],
                             lead: Sequence[int],
                             reach: int | None = None) -> bool:
    """Whether rules/P1's fold takes `lead`, the piece opening the
    name, beside the lone never-given particle it takes under every
    order (asked inline by each caller first, sparing every parse a
    frame), and asked only under a family-first order: two more -- a lone ambiguous particle written
    in lower case in a name of mixed case (rules/P11, #670), and a
    particle chain a title-particle in front lets P2 build (rules/P4's
    Except, #828), cut after its particles and one name unit unless a
    suffix-or-name report names a word past that reach ('St de Mesnil
    Jean V'). A chain the reach already covers is left whole ('St Sir de
    Mesnil', 'St abu Bakar'). `reach` is `_fold_reach` over `lead`
    where the caller has it already."""
    # rules/P1: "a particle chain behind a title-particle is cut as the
    # run is" -- the chain clause; and rules/P11: "an ambiguous particle
    # written in lower case, in a name of mixed case, opens the name as
    # a never-given one does" -- the writing clause (decisions/P1 and
    # decisions/P11, #828, #670)
    if is_lowercase_ambiguous_particle(lead, tokens, state.one_case):
        return True
    if len(lead) < 2 or "particle" not in tokens[lead[0]].tags:
        return False
    if reach is None:
        reach = _fold_reach(tokens, list(lead))
    # a word past the reach a suffix-or-name report names was read
    # against the whole chain ('St de Mesnil Jean V', whose numeral had
    # no word to spare): the cut would strand it, so the chain stands
    return reach < len(lead) and not reported_suffix_fork(
        state.ambiguities, lead[reach:])


# rules/S1: "it is no nickname and no maiden name, and the words around
# it read as they would beside a nickname" -- the clause's words
# take their roles here, once the name's words are placed: extract has
# already lifted a clause wholly of unambiguous non-name words out of
# the name, and a member of the ambiguous class joins one only where
# its writing settles it after the name (rules/S13); decisions/S1
# (#792)
def _set_apart_clauses(state: ParseState,
                       tokens: list[WorkToken]) -> None:
    """Give each word of a delimited clause wholly of non-name words
    the role its vocabulary gives it: a title a title, a credential or
    generation the suffix, and a word that is both a title in front of
    the name's first word or in a name with no word of its own, and the
    suffix anywhere else. A clause extract set apart may still be
    declined here, keeping its pair's reading: titles alone behind a
    word read as a suffix, a credential written as initials before a
    name word of its comma part, or a member of the ambiguous class not
    after the name."""
    first_name = last_name = -1
    for i, t in enumerate(tokens):
        if t.role in NAME_ROLES:
            last_name = i
            if first_name < 0:
                first_name = i
    starts = [t.span.start for t in tokens]
    lex = state.lexicon
    # whether a name word stands after each token in its comma part,
    # built once on first need, so a name of many clauses stays linear
    ahead: list[bool] | None = None
    for _, clause in state.extracted:
        lo = bisect.bisect_left(starts, clause.start)
        hi = bisect.bisect_left(starts, clause.end)
        words = state.original[clause.start:clause.end].split()
        # every word one token of the clause, as extract read them
        if not words or hi - lo != len(words) or any(
                tokens[i].role not in (Role.NICKNAME, Role.MAIDEN)
                for i in range(lo, hi)):
            continue
        kinds: list[SetApartKind] = []
        member = False
        for i in range(lo, hi):
            token = tokens[i]
            kind = set_apart_kind(token.text, lex)
            if kind == "member" or kind is None \
                    and AMBIGUOUS_ACRONYM_TAG in token.tags \
                    and settled_by_case(token, state.one_case):
                kind, member = "suffix", True
            elif kind is None:
                break
            kinds.append(kind)
        else:
            # a member is settled after the name only (rules/S13), and
            # a credential written as initials before a name word of its
            # comma part stays the nickname
            if member and not 0 <= last_name < lo:
                continue
            # a name word after the clause in its comma part stands
            # behind the last name word, so a clause after the name skips
            # the walk; a title is never initials, asked inline
            if last_name >= hi and any(
                    kind != "title"
                    and reads_as_initials(w, kind, state.one_case, lex)
                    for w, kind in zip(words, kinds)):
                if ahead is None:
                    ahead = _name_ahead(state, tokens)
                if ahead[hi - 1]:
                    continue
            # the token in front of the clause
            if not set_apart(words, kinds, lo > 0
                             and tokens[lo - 1].role is Role.SUFFIX, lex):
                continue
            for i, kind in zip(range(lo, hi), kinds):
                title = kind == "title" or (
                    kind == "dual" and (first_name < 0 or i < first_name))
                # a comma the clause kept on its word (rules/N1) is no
                # part of a title or a suffix: the word's span is
                # trimmed, so its text stays the original slice, and
                # R1's entry pass reads the comma left between two
                # suffix words
                token = tokens[i]
                text = token.text.strip(",")
                start = token.span.start + token.text.index(text)
                tokens[i] = copy_with(
                    token, role=Role.TITLE if title else Role.SUFFIX,
                    text=text, span=Span(start, start + len(text)))


def _name_ahead(state: ParseState, tokens: list[WorkToken]) -> list[bool]:
    """For each token, whether a name word stands after it before the
    next comma: one walk from the end, each comma part's answer reset
    where the part changes."""
    ahead = [False] * len(tokens)
    seen = False
    part = None
    for i in range(len(tokens) - 1, -1, -1):
        here = comma_bucket(tokens[i].span.start, state.comma_offsets)
        if here != part:
            part, seen = here, False
        ahead[i] = seen
        if tokens[i].role in NAME_ROLES:
            seen = True
    return ahead


# rules/S13: "where the member's writing settles it as the credential,
# the way the rules that read the writing say a credential is written,
# it is no nickname but the suffix" -- the settling itself is
# `_set_apart_clauses`', which reads a lone member whose writing
# settles it after the name as a clause of one non-name word; what is
# left here is the report on a member it left the nickname
# (decisions/S13 (#810), decisions/S1 (#792))
def _report_delimited_members(tokens: list[WorkToken], lexicon: Lexicon,
                              ambiguities: list[PendingAmbiguity]) -> None:
    """Report the fork on every member of the ambiguous class left a
    nickname: `_set_apart_clauses`, run first, has made each member its
    writing settles after the name the suffix, so a member still a
    nickname is one it did not settle, a dotted member inside the name
    included. Reported here, where the clause is decided, rather than
    in extract, which has no token index to point at. A dotted member
    carries no tag in a clause (classify tags a shape only outside
    one), so it is found by its text, by `dotted_member` as the
    settling finds it, whatever else the vocabulary reads it as."""
    for i, token in enumerate(tokens):
        if token.role is not Role.NICKNAME:
            continue
        # the period asked first, at C level, so a nickname written
        # without one pays no frame
        if (AMBIGUOUS_ACRONYM_TAG in token.tags
                or "." in token.text and dotted_member(token.text, lexicon)):
            ambiguities.append(PendingAmbiguity(
                AmbiguityKind.SUFFIX_OR_NICKNAME,
                f"delimited {token.text!r} is also a post-nominal; read "
                f"as a nickname rather than a suffix",
                (i,), alternative=suffix_reading(token)))


def _unattached(state: ParseState, tokens: list[WorkToken],
                word: WorkToken, start: int) -> PendingReading:
    """The name reading of the particle run P6 attaches at the end of
    a name read family-first, which starts at token `start`: the field
    the positional read gave it, or the field of the name piece in
    front where that piece would take a name word in (`_name_alt`)."""
    role = tokens[start].role
    assert role is not None  # assign roled every name word
    # the run ends a name read family-first, so a name word stands in
    # front of it
    front, first = next(
        ((piece, k == 0) for seg_idx in range(len(state.pieces))
         for k, piece in enumerate(_name_pieces(state, tokens, seg_idx))
         if start - 1 in piece), (None, False))
    return _name_alt(word, role, front, tokens, first, False)


def post_rules(state: ParseState) -> ParseState:
    tokens = list(state.tokens)
    ambiguities = list(state.ambiguities)
    if state.extracted:
        _set_apart_clauses(state, tokens)
        _report_delimited_members(tokens, state.lexicon, ambiguities)
    titles, givens, middles, families = _positions(tokens)

    # rules/H1: "a title followed by exactly one name word makes
    # that word the family name, whatever suffix, nickname or maiden
    # name stands beside it, unless the title is a given-name title,
    # which keeps it the given name; a run of several titles addresses
    # as its last title does" -- counting suffix, nickname and maiden
    # as further name words is what emptied the family (#410)
    # (known gap: the guard tests which roles are unoccupied, it does
    # not count units -- decisions/H1) (v1 handle_firstnames)
    #
    # rules/H1: "a run of several titles addresses as its last
    # title does, and where a run stands BEFORE the one name word it
    # is the run that addresses, a run standing behind it deciding
    # that word's field only when none stands before" -- #489. WHICH
    # run that is, and why the two ends of a name are not one, are
    # _addressing_run's; its docstring carries the history.
    if (titles and givens and not middles and not families
            and not _run_addresses_by_given(
                (tokens[i].text
                 for i in _addressing_run(titles, givens[0])),
                state.lexicon._sets.given_name_titles)):
        for i in givens:
            _retag(tokens, i, Role.FAMILY)
        # every rule below reads these lists; recompute after any
        # retag so no guard can inspect a name that has already
        # moved -- a stale index list is the bug shape #359 fixed
        _, givens, middles, families = _positions(tokens)
    # rules/H1: "a comma with no given name after it does not decide
    # the field, nor does a declared order" -- the other direction, for
    # the shapes assign reads as the family before H1 can see them
    # (#720): a family comma with no name word after it and one before
    # it, and the one name word of a name read family-first. The comma
    # named no given part, and the order places a word nothing else
    # decided (O5), so the title decides as it does in 'Sir John'
    # ('John III, Sir' reads as 'Sir John III'), unless
    # something else settled the word (_family_settled).
    elif (titles and families and not givens and not middles
            and not _family_settled(state, tokens, families)
            and _run_addresses_by_given(
                (tokens[i].text
                 for i in _addressing_run(titles, families[0])),
                state.lexicon._sets.given_name_titles)):
        for i in families:
            _retag(tokens, i, Role.GIVEN)
        # recomputed for H1's reason, stated above
        _, givens, _, families = _positions(tokens)

    # rules/M4: "a maiden name standing beside exactly one name
    # word makes that word the family name, whatever suffix or
    # nickname stands beside it" (#445) -- the MAIDEN role, not a
    # marker: M1's configured pair produces one with no marker
    # anywhere ("Smith (Jones)" under maiden_delimiters), and the
    # rationale carries over unchanged, so the rule is keyed on the
    # maiden name as the statement is.
    #
    # H1's sibling, and placed under it so the interaction the rule
    # states is decidable by reading: where H1 fired, `givens` is
    # empty here and this cannot fire; where H1 declined because the
    # title addresses by given name, `titles` is what keeps this rule
    # off the same word. A titled name is H1's at both outcomes.
    #
    # Sibling EXCEPT in what it counts, and that is a known gap
    # rather than a boundary: this guard counts GIVEN tokens where
    # H1 counts nothing (it tests which roles are unoccupied), so a
    # name word another rule joined counts as several here and the
    # rule declines -- `Dr. Dean of Chemistry` reads family, while
    # `Dean of Chemistry née Jones` keeps given 'Dean of Chemistry'.
    # rules/P3 says a joined part is one name word wherever
    # another rule counts them, so the two disagree; widening moves
    # no corpus name and is not this change's to make
    # (decisions/M4).
    # rules/M4: "a bound given name keeps the reading its position
    # gives it, and so does a word read as an initial"
    # -- read off the tags classify already recorded rather than a
    # predicate of this rule's own, because this rule changes what
    # POSITION decided and must not reach what a word IS
    # (mechanisms.md#TWO-LAYER-ASSIGN).
    if (not titles and len(givens) == 1 and not middles and not families
            and any(t.role is Role.MAIDEN for t in tokens)
            and not (_NEVER_FLIPPED & tokens[givens[0]].tags)):
        _retag(tokens, givens[0], Role.FAMILY)
        # recomputed for H1's reason, stated at H1: a stale index list
        # is the bug shape #359 fixed
        _, givens, middles, families = _positions(tokens)

    # rules/P1: "the particle run and the name words it takes are
    # family, under every name order" -- its Then clause, for a
    # never-given particle opening the name and, under a family-first
    # order, the two pieces `_family_first_lead_folds` adds; how many words the run
    # takes is set by the order or a family comma, in P1's bullets and
    # below (v1 handle_non_first_name_prefix; decisions/P1)
    # How far the fold reaches depends on the order the name was READ
    # under (#395; decisions/P1, 2026-08-17): declaring a
    # family-first order asserts that what follows the family is not
    # more surname, which is the very question of where the run stops.
    # Under that declaration the run takes its own particles and ONE
    # name word; under the default order it keeps taking the rest of
    # the name, nothing having marked where the surname ends. Note what
    # actually holds the family-comma shape back, since it is NOT
    # that test -- "Smith, de Mesnil Jean" DOES fire the leading site,
    # segment 1 opening with the particle. It keeps the old reach
    # because assign records no order after a family comma, the comma
    # having already fixed the surname, so `order is None` here.
    # Anything that later gives that path an order turns the
    # narrowing on for it.
    # ONE site, the opening piece. A particle standing in the GIVEN
    # position was a second site until #467, and it was the parser
    # overriding a declaration rather than reading one: under a
    # family-first order that slot holds what the caller SAID is the
    # given name, and the never-given vocabulary supplies a default
    # where position leaves the question open, not a veto over an
    # answer position already gave. So "Menil de" under either
    # family-first order reports given "de" -- P6 takes the trailing
    # particle only where it landed in a MIDDLE, which means nothing.
    # Code-local: a lone PIECE is the test (`_family_first_lead_folds` names the two
    # pieces a family-first order adds), so a particle group already
    # chained forward is not a lone particle elsewhere, and rule H1
    # above cannot be what produces the fold's family reading -- its
    # given -> family branch is gated on `not families`, and its family
    # -> given branch leaves the word this fold takes, asking the same
    # predicate (_family_settled).
    lead = _leading_name_piece(state, tokens)
    family_first = state.order is not None and state.order[0] is Role.FAMILY
    reach = None
    if (family_first and len(lead) > 1
            and "particle" in tokens[lead[0]].tags):
        # the words past the fold's reach, marked for assemble's
        # alternatives whether or not the fold cuts there (#828)
        reach = _fold_reach(tokens, list(lead))
        for i in lead[reach:]:
            tokens[i] = copy_with(tokens[i],
                                  tags=tokens[i].tags | {PAST_REACH_TAG})
    lead_fires = (is_lone_never_given_particle(lead, tokens)
                  or family_first
                  and _family_first_lead_folds(state, tokens, lead, reach))
    if len(givens) + len(middles) + len(families) > 1 and lead_fires:
        order = state.order
        if order is not None and order[0] is Role.FAMILY:
            # `state.order`, not policy.name_order: a script_orders
            # entry can put the family first under a given-first
            # policy, and the roles below have to match the read
            # assign actually made.
            name_idx = sorted(givens + middles + families)
            cut = _fold_reach(tokens, name_idx)
            for i in name_idx[:cut]:
                _retag(tokens, i, Role.FAMILY)
            # What is left is a shorter name of the same order: one
            # family already placed, so drop that slot and lay the
            # rest out as _name_positions would for n + 1 pieces.
            rest = _units(tokens, name_idx[cut:])
            for unit, role in zip(rest, _name_positions(
                    order, len(rest) + 1)[1:]):
                for i in unit:
                    _retag(tokens, i, role)
        else:
            for i in givens + middles:
                _retag(tokens, i, Role.FAMILY)
        # downstream rules key on the role counts: recompute
        _, givens, middles, families = _positions(tokens)

    # v1 gates both rotations on `not self._had_comma`; the
    # middle_as_family fold below runs comma or not (v1 order:
    # patronymics first, then handle_middle_name_as_last)
    rules = state.policy.patronymic_rules
    rotations_apply = _rotations_apply(state)
    # rules/O1: "a name of exactly three name words — titles,
    # suffixes and nicknames aside — whose last name word carries a
    # patronymic ending and whose middle name word does not reads as
    # family-first" (history: decisions/O1)
    if rotations_apply and PatronymicRule.EAST_SLAVIC in rules and \
            len(givens) == 1 and len(middles) == 1 and len(families) == 1:
        tail = tokens[families[0]].text
        mid = tokens[middles[0]].text
        if has_patronymic_ending(tail) and not has_patronymic_ending(mid):
            g, m, f = givens[0], middles[0], families[0]
            _retag(tokens, m, Role.GIVEN)
            _retag(tokens, f, Role.MIDDLE)
            _retag(tokens, g, Role.FAMILY)
            # recomputed for H1's reason, stated at H1: a stale index
            # list is the bug shape #359 fixed
            _, givens, middles, families = _positions(tokens)
    # rules/O2: "a name of exactly four name words — titles,
    # suffixes and nicknames aside — ending in a standalone
    # patronymic marker reads family-first: the first name word is
    # the family name" (history: decisions/O2)
    if rotations_apply and PatronymicRule.TURKIC in rules and \
            len(givens) == 1 and len(middles) == 2 and len(families) == 1:
        tail = tokens[families[0]].text
        if is_patronymic_marker(tail):
            g, m1, m2, f = givens[0], middles[0], middles[1], families[0]
            _retag(tokens, m1, Role.GIVEN)
            _retag(tokens, m2, Role.MIDDLE)
            _retag(tokens, f, Role.MIDDLE)
            _retag(tokens, g, Role.FAMILY)
            # recomputed for H1's reason, stated at H1: a stale index
            # list is the bug shape #359 fixed
            _, givens, middles, families = _positions(tokens)
    # rules/P6: "a particle ending the name attaches to that family
    # name and is written before it" -- the no-comma site (#467).
    # A comma is not the only thing that names the family; a declared
    # family-first order does too, and the same listing is written
    # both ways ("Jong, Anke de" and "Jong Anke de" under
    # FAMILY_FIRST both give family "de Jong").
    #
    # Keyed on the SLOT the run landed in, not on its vocabulary.
    # MIDDLE is the one position that means nothing here: middles are
    # further given names, and a particle is not one. Only
    # FAMILY_FIRST puts a trailing piece there --
    # FAMILY_FIRST_GIVEN_LAST puts it in GIVEN, where the caller's own
    # declaration says it IS the given name, and P1's site above no
    # longer overrides that either.
    #
    # Which is why no vocabulary test appears here and none is wanted.
    # The comma path needs one because a comma cannot separate the
    # Dutch reading from the Vietnamese; the declared ORDER can, when
    # the caller declares the right one for the name: "Beethoven
    # Ludwig van" under FAMILY_FIRST gives family "van Beethoven"
    # though `van` is ambiguous vocabulary, and "Nguyen Thi Van" under
    # FAMILY_FIRST_GIVEN_LAST keeps given "Van" though the same word
    # is in the same set. (Under the WRONG order each loses: the
    # Vietnamese name read as FAMILY_FIRST gives family "Van Nguyen".
    # rules/P6 records that as accepted -- it is one order, not
    # both.) A never-given test here would have excluded every
    # ambiguous particle -- von, di, da, del, le and `van` itself,
    # the flagship word of the listing this rule is named for.
    #
    # NO RE-LAYOUT, and that is a property of ONE order rather than a
    # simplification: under FAMILY_FIRST the roles run family, given,
    # middle, middle..., so dropping a trailing MIDDLE leaves every
    # other piece's role untouched. It is not true of
    # FAMILY_FIRST_GIVEN_LAST (family, middle..., given) and not true
    # of the default order, which is why this site tests the order
    # rather than trusting the slot to imply it -- review found the
    # first draft firing on 52 default-order names, where a
    # conjunction stops a particle's forward chain and leaves it
    # standing in a middle ("Maria Luisa y de la Cruz"). An earlier
    # draft still (#466) removed a piece and re-laid the leftover out,
    # which lost a given name outright on "van Berg Jan de" and
    # promoted a post-nominal into the given slot on
    # "Berg Jan Jr. de"; neither is reachable without a re-layout.
    #
    # The family must still hold a base of its own -- R2's invariant,
    # that a non-empty family has a non-empty base, not a ban on
    # particle-before-particle. Without it "van Berg Jan de" reports
    # family 'de van', whose words R2 reads as ordinary name words,
    # and no rule reorders those. It does NOT stop a second particle
    # joining a family that merely OPENS with one: "de Mesnil Jan de"
    # gives 'de de Mesnil', which keeps its base and is accepted.
    # every retagging block above recomputes the lists, so they are
    # current here (a stale index list is the bug shape #359 fixed)
    names = givens + middles + families
    if middles and families and state.order is not None:
        run: list[int] = []
        i = len(middles)
        while i and "particle" in tokens[middles[i - 1]].tags:
            i -= 1
            run.append(middles[i])
        # ENDING the name is the rule's own word, and it is the whole
        # test: the trailing MIDDLE is not always the trailing NAME
        # word. Under FAMILY_FIRST_GIVEN_LAST the given name stands
        # behind the middles, and under the default order the family
        # does, so in both a middle that ends the name is impossible
        # and this declines without asking which order was declared.
        # Only FAMILY_FIRST can put a name's last word in a middle.
        #
        # A draft tested the SLOT alone and fired on 52 default-order
        # names, where a conjunction stops a particle's forward chain
        # and leaves it standing in a middle ("Maria Luisa y de la
        # Cruz"), and on 366 FAMILY_FIRST_GIVEN_LAST middles with the
        # given name still behind them. A later draft tested the order
        # as well; measured over 542,592 generated parses, that second
        # test never decides anything this one has not already decided,
        # so it is not here.
        trailing = bool(run) and max(run) == max(names)
        if trailing and any("particle" not in tokens[j].tags
                            for j in families):
            # mechanisms.md#AMBIGUITY-AT-THE-DECISION-SITE: "Emit at
            # the site that takes the branch, not where an ambiguous
            # tag sits". decisions/P6 (#405) settled that this
            # attachment reports the fork it decides, and the state it
            # fixed is the one this site would otherwise recreate --
            # `Beethoven, Ludwig van` reporting while `Beethoven Ludwig
            # van` under FAMILY_FIRST decides the identical fork in
            # silence. ONE arm here where the comma path has two: the
            # suffix reading stands without a comma, so no post-nominal
            # reading is ever overridden for this site to report.
            ambiguous = [j for j in run
                         if "vocab:particle-ambiguous" in tokens[j].tags]
            if ambiguous:
                word = tokens[ambiguous[0]].text
                text = " ".join(tokens[j].text for j in sorted(run))
                ambiguities.append(PendingAmbiguity(
                    AmbiguityKind.PARTICLE_OR_GIVEN,
                    f"{word!r} is both a family-name particle and an "
                    f"ordinary given name; ending a name read "
                    f"family-first, {text!r} joins the family that "
                    f"order named rather than standing as a name word "
                    f"of its own",
                    tuple(sorted(run)),
                    # the field the positional read gave it, which this
                    # attachment moves, unless the piece in front would
                    # take a name word in
                    alternative=_unattached(state, tokens,
                                            tokens[ambiguous[0]],
                                            min(run))))
            for j in run:
                tokens[j] = copy_with(
                    tokens[j], role=Role.FAMILY,
                    tags=tokens[j].tags | {FOLDED_TAG, ATTACHED_TAG})
            # recomputed for H1's reason, stated at H1: a stale index
            # list is the bug shape #359 fixed
            _, givens, middles, families = _positions(tokens)

    # every parse asks this, so a name holding no marked word pays one
    # plain loop and no call (the parse-cost band, decisions/parse-cost)
    for token in tokens:
        if PARTICLE_GIVEN_TAG in token.tags:
            _given_phrase_middle(state, tokens)
            break
    if state.policy.two_family_names:
        _take_second_family_name(state, tokens)
    if state.policy.two_given_names:
        _take_second_given_name(state, tokens)

    # rules/O3: "every middle word joins the family name and is
    # rendered before it" (v1 handle_middle_name_as_last). v1
    # PREPENDED middle_list to last_list; mechanisms.md#FOLDED_TAG:
    # "tokens never move: a rule that needs different rendering order
    # tags the token, and the rendering views consult the tag"
    if state.policy.middle_as_family:
        # walked again: P10, O6 and O7 above retag without updating the
        # lists
        _, _, middles, families = _positions(tokens)
        # rules/R11: "middle words folded into the family belong to
        # neither unit" -- where O6 marked no units the family before the
        # fold is the first, marked here so the views can leave the
        # folded words out; only a fold that moves a word pays for it
        # (decisions/R11, #1022). A family O6 split carries its marks
        # already; a loop, not a generator, which costs a frame
        if middles:
            for i in families:
                if FIRST_SURNAME_TAG in tokens[i].tags:
                    break
            else:
                _mark_surname(tokens, families, FIRST_SURNAME_TAG)
        for i in middles:
            tokens[i] = copy_with(
                tokens[i], role=Role.FAMILY,
                tags=tokens[i].tags | {FOLDED_TAG})
    # rules/R2: "a name part whose every word is particle
    # vocabulary is a part where none of them is doing a particle's
    # work — nothing joins them to a name — so they read as ordinary
    # name words"
    #
    # Last of the rules that MOVE a token, because every rule above
    # can still move one between parts:
    # P1's fold, P6's attachment and O3's fold all rewrite roles, and
    # this reads the roles they settle on.
    #
    # Marked, not untagged: `particle` is stable API and says the word
    # IS particle vocabulary wherever it lands, which stays true.
    #
    # All three roles for uniformity with the rule, not because all
    # three are observable: no view filters tags on GIVEN (initials
    # exempt that role outright), so restricting this loop to MIDDLE
    # and FAMILY moves 0 of 4,506 parses. The GIVEN arm is marked so a
    # future view reading the mark gets a consistent answer.
    #
    # rules/R3: "A part holding nothing else is a part where it is
    # joining nothing, and there it initials like any other name word"
    # -- #461's mark, decided HERE for the same reason R2's is: the
    # question is about the PART, and a view that re-derives a
    # part-level fact is how initials() and family_base came apart.
    #
    # ONE walk decides both marks -- a plain loop, not two generator
    # expressions: this runs per role on every parse and a genexp
    # costs a frame of its own (frame budget). An EMPTY role needs no
    # `continue` ahead of the walk, which is inert on one: measured
    # 2026-09-20, py3.11, one survived the whole suite and moved
    # neither frame count (parse=406.00 facade=443.00 either way).
    # `bool(part)` says the same thing about the R2 arm as
    # `_types._remarked`'s twin of this walk does.
    #
    # rules/R2: "A connective that is not also particle vocabulary,
    # standing between two words of the part, is set aside when the
    # part is asked whether every word is particle vocabulary" --
    # `between` is the part's own first and last word excluded, and a
    # set-aside connective is left unmarked, so it stays in the base,
    # initials nothing and keeps its case (decisions/R2, #939). A set,
    # since the marking loop asks it per word: a list made a part
    # alternating particle and connective quadratic (test_benchmark's
    # `connective_between_particles` row).
    _, givens, middles, families = _positions(tokens)
    for part in (givens, middles, families):
        all_particle = bool(part)
        conj: list[int] = []
        between: set[int] = set()
        others = 0
        last = len(part) - 1
        for n, i in enumerate(part):
            tags = tokens[i].tags
            is_conj = "conjunction" in tags
            if is_conj:
                conj.append(i)
            if "particle" not in tags:
                if is_conj and 0 < n < last:
                    between.add(i)
                    continue
                all_particle = False
                if not is_conj:
                    others += 1
        if all_particle:
            for i in part:
                if i not in between:
                    tokens[i] = copy_with(
                        tokens[i], tags=tokens[i].tags | {UNJOINED_TAG})
        elif conj and not others:
            # #461: nothing here for the connective to join. The `elif`
            # is deliberate -- where the part is all-particle R2's mark
            # already readmits every word but a connective it set aside,
            # a word that is BOTH particle and connective included
            # (never set aside, being a particle), which is what keeps
            # a caller's `add("y", kind="particle")` readings unchanged;
            # and it keeps this mark off a connective R2 set aside, which
            # joins the particles around it and initials nothing.
            for i in conj:
                tokens[i] = copy_with(
                    tokens[i],
                    tags=tokens[i].tags | {UNJOINED_CONJUNCTION_TAG})
    _mark_suffix_entries(tokens, state)
    return copy_with(state, tokens=tuple(tokens),
                     ambiguities=tuple(ambiguities))
