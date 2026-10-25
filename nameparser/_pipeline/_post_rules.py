"""Stage: post_rules.

Consumes: tokens (roles assigned), plus pieces and structure -- the
particle fold reads the opening piece of segment 0, or of segment 1
under a family comma (#359). structure was always read here, for the
rotation gate. Also comma_offsets and dropped, which R1's entry pass
below reads to find the separators the writer typed (#436/#437).
Produces: tokens with roles adjusted by the post rules, the stable
"joined" tag on a post-nominal continuing the entry before it, and the
ambiguity P6's attachment reports at the end of a name read
family-first (#467) and after a comma with nothing before it -- after a
family comma that names a family, that attachment is assign's since
#613.
Reads: Policy.patronymic_rules, Policy.two_family_names,
Policy.name_order (O6 stands down where the script's order differs
from the declared one), Policy.middle_as_family,
Policy.extra_suffix_delimiters (R1's entry pass, for the delimiter
cores group drops); Lexicon.given_name_titles.

Implements rules H1, M4, P1, P6 (its no-comma site, and after a comma
naming no family), O1, O2, O6, O3 and R1 of docs/design/rules/;
each is cited at its code below, and H1/P1/O1/O2's history lives in
docs/design/decisions/. `suffix_entries` is the R1 entry pass as a
state-in/state-out function, for Parser.revise to run over a
forced-role sub-parse (#511); `post_rules` runs the same worker last.
"""
from __future__ import annotations

import re

from nameparser._lexicon import _run_addresses_by_given
from nameparser._pipeline._assign import (
    _attach_particle_tail, _name_positions,
)
from nameparser._pipeline._pieces import (
    is_lone_never_given_particle, particle_tail,
)
from nameparser._pipeline._state import (
    NAME_ROLES,
    ParseState, PendingAmbiguity, Structure,
    WorkToken, _NEVER_FLIPPED, comma_bucket, copy_with,
)
from nameparser._pipeline._vocab import delimiter_cores, unit_ends
from nameparser._policy import PatronymicRule
from nameparser._types import (
    FOLDED_TAG, UNJOINED_CONJUNCTION_TAG, UNJOINED_TAG, AmbiguityKind, Role,
)

# Ported verbatim from v1 (nameparser/config/regexes.py) -- layering
# forbids the config import; keep in sync by hand.
_EAST_SLAVIC = re.compile(
    r"(ovich|ovna|evich|evna|ichna|ilyich|kuzmich|lukich|fomich|fokich)$",
    re.I)
_EAST_SLAVIC_CYR = re.compile(
    r"(ович|овна|евич|евна|ична|ильич|кузьмич|лукич|фомич|фокич)$",
    re.I)
_TURKIC = re.compile(
    r"^(oglu|oğlu|ogly|ogli|o['’ʻ]g['’ʻ]li"
    r"|qizi|qızı|kizi|kyzy|gyzy|uly|uulu)$", re.I)
_TURKIC_CYR = re.compile(
    r"^(оглу|оглы|оғлу|ўғли|угли|кызы|гызы|қызы|қизи|улы|ұлы|уулу)$", re.I)


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
    # After assign, because it keys on Role.SUFFIX; last in post_rules
    # by convention only, since no rule here writes SUFFIX or a
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
            for between in range(previous + 1, current))
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


def _idx(tokens: list[WorkToken], role: Role) -> list[int]:
    return [i for i, t in enumerate(tokens) if t.role is role]


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
    first non-title piece, and at a fold site the first piece is the
    particle -- "ibn Awf abdul Rahman" reaches here as four separate
    pieces. The tag is the only witness in both cases.

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


#: The hyphens and the dashes that join two family names in one written
#: word (rules/O6): hyphen-minus, hyphen, non-breaking hyphen, figure
#: dash, en dash, minus sign (a word processor's substitute), and the
#: small and fullwidth hyphen-minus. The em dashes are punctuation
#: between words, not joiners, and are left out.
_HYPHENS = re.compile("[-\u2010\u2011\u2012\u2013\u2212\ufe63\uff0d]")


def _family_word_count(tokens: list[WorkToken], family: list[int]) -> int:
    """The family's name words as rules/O6 counts them: a particle run
    counts with the word it attaches to, a connective counts as
    nothing and a hyphen joins words without making them one, so "de
    la Vega" is one word and "Ortega y Gasset" and "García-López" two.
    A family of nothing but particles counts each of them, R2 reading
    them as ordinary name words."""
    words = sum(len([part for part in _HYPHENS.split(tokens[i].text)
                     if part])
                for i in family
                if "particle" not in tokens[i].tags
                and "conjunction" not in tokens[i].tags)
    return words or len(family)


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
    family = _idx(tokens, Role.FAMILY)
    others = sorted(_idx(tokens, Role.GIVEN) + _idx(tokens, Role.MIDDLE))
    if not family or _family_word_count(tokens, family) != 1:
        return
    # The rest in the units assign read them as, so a particle chain
    # (P2) or a bound given-name pair (P5) moves whole or not at all.
    units = _units(tokens, others)
    if len(units) < 2:
        return
    take = units[-1] if state.order[0] is Role.GIVEN else units[0]
    # What is taken must be ONE name word, counted as the family is, so
    # a hyphenated given name or a bound given-name pair (P5) stays put;
    # and a word a family name could be: not an initial, which writes a
    # given name (one written alone; "J.R." is taken), nor a lone dash
    # or other mark with no letter in it.
    if _family_word_count(tokens, take) != 1:
        return
    if len(take) == 1 and "initial" in tokens[take[0]].tags:
        return
    if not any(ch.isalpha() for i in take for ch in tokens[i].text):
        return
    if state.order[0] is Role.GIVEN:
        # given, middles..., family: the middle unit standing right
        # before the family joins it, and text order already renders
        # it first, so no role around it moves. A rotation that left
        # the name in another shape fails this test.
        if take[-1] > family[0] or any(
                tokens[i].role is not Role.MIDDLE for i in take):
            return
        for i in take:
            _retag(tokens, i, Role.FAMILY)
        return
    # family first: the unit after the family joins it, and what is
    # left is a shorter name of the same order, laid out as the P1
    # fold above lays its remainder -- one family already placed. A
    # particle P6 attached at the far end is family already and keeps
    # its place.
    if family[0] > units[0][0]:
        return
    for i in units[0]:
        _retag(tokens, i, Role.FAMILY)
    for unit, role in zip(units[1:], _name_positions(
            state.order, len(units))[1:]):
        for i in unit:
            _retag(tokens, i, role)


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
    asked by the fold's own predicate on the same piece. An ambiguous
    particle nothing settled, or a bare one with nothing to fold, is a
    word the order placed ('Sir Van', 'Sheik Abu Bakar' and 'Sir de'
    under FAMILY_FIRST; 'Sir von und zu', whose never-given 'zu' does
    not open it)."""
    if state.structure is Structure.FAMILY_COMMA:
        return any("particle" in tokens[i].tags for i in families)
    return len(families) > 1 and is_lone_never_given_particle(
        _leading_name_piece(state, tokens), tokens)


def post_rules(state: ParseState) -> ParseState:
    tokens = list(state.tokens)
    ambiguities = list(state.ambiguities)
    titles = _idx(tokens, Role.TITLE)
    givens = _idx(tokens, Role.GIVEN)
    middles = _idx(tokens, Role.MIDDLE)
    families = _idx(tokens, Role.FAMILY)

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
                state.lexicon.given_name_titles)):
        for i in givens:
            _retag(tokens, i, Role.FAMILY)
        # every rule below reads these lists; recompute after any
        # retag so no guard can inspect a name that has already
        # moved -- a stale index list is the bug shape #359 fixed
        givens = _idx(tokens, Role.GIVEN)
        middles = _idx(tokens, Role.MIDDLE)
        families = _idx(tokens, Role.FAMILY)
    # rules/H1: "a comma with no given name after it does not decide
    # the field, nor does a declared order" -- the other direction, for
    # the shapes assign reads as the family before H1 can see them
    # (#720): a family comma with no name word after it and one before
    # it, and the one name word of a name read family-first. The comma
    # named no given part, and the order places a word nothing else
    # decided (O5), so the title decides as it does in 'Sir John'
    # ('Elizabeth II, Queen' reads as 'Queen Elizabeth II'), unless
    # something else settled the word (_family_settled).
    elif (titles and families and not givens and not middles
            and not _family_settled(state, tokens, families)
            and _run_addresses_by_given(
                (tokens[i].text
                 for i in _addressing_run(titles, families[0])),
                state.lexicon.given_name_titles)):
        for i in families:
            _retag(tokens, i, Role.GIVEN)
        # recomputed for H1's reason, stated above
        givens = _idx(tokens, Role.GIVEN)
        families = _idx(tokens, Role.FAMILY)

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
    # rules/M4: "a word the vocabulary has claimed as a given name
    # keeps that reading, and so does a word read as an initial"
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
        givens = _idx(tokens, Role.GIVEN)
        middles = _idx(tokens, Role.MIDDLE)
        families = _idx(tokens, Role.FAMILY)

    # rules/P1: "the particle run and the name words it takes are
    # family, under every name order" -- its Then clause, for a
    # never-given particle opening the name; how many words the run
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
    # Code-local: a lone PIECE is the test, so a particle group
    # already chained forward is not a lone particle, and rule H1
    # above cannot be what produces the fold's family reading -- its
    # given -> family branch is gated on `not families`, and its family
    # -> given branch leaves the word this fold takes, asking the same
    # predicate (_family_settled).
    lead = _leading_name_piece(state, tokens)
    lead_fires = is_lone_never_given_particle(lead, tokens)
    if len(givens) + len(middles) + len(families) > 1 and lead_fires:
        order = state.order
        if lead_fires and order is not None and order[0] is Role.FAMILY:
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
        givens = _idx(tokens, Role.GIVEN)
        middles = _idx(tokens, Role.MIDDLE)
        families = _idx(tokens, Role.FAMILY)

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
        if (_EAST_SLAVIC.search(tail) or _EAST_SLAVIC_CYR.search(tail)) \
                and not (_EAST_SLAVIC.search(mid)
                         or _EAST_SLAVIC_CYR.search(mid)):
            g, m, f = givens[0], middles[0], families[0]
            _retag(tokens, m, Role.GIVEN)
            _retag(tokens, f, Role.MIDDLE)
            _retag(tokens, g, Role.FAMILY)
    # rules/O2: "a name of exactly four name words — titles,
    # suffixes and nicknames aside — ending in a standalone
    # patronymic marker reads family-first: the first name word is
    # the family name" (history: decisions/O2)
    if rotations_apply and PatronymicRule.TURKIC in rules and \
            len(givens) == 1 and len(middles) == 2 and len(families) == 1:
        tail = tokens[families[0]].text
        if _TURKIC.match(tail) or _TURKIC_CYR.match(tail):
            g, m1, m2, f = givens[0], middles[0], middles[1], families[0]
            _retag(tokens, m1, Role.GIVEN)
            _retag(tokens, m2, Role.MIDDLE)
            _retag(tokens, f, Role.MIDDLE)
            _retag(tokens, g, Role.FAMILY)
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
    mids = _idx(tokens, Role.MIDDLE)
    # O1 and O2 above retag between roles WITHOUT recomputing, so this
    # is the first consumer of a stale list -- the bug shape #359 fixed,
    # and every other retagging block in this stage recomputes for it.
    families = _idx(tokens, Role.FAMILY)
    names = _idx(tokens, Role.GIVEN) + mids + families
    if mids and families and state.order is not None:
        run: list[int] = []
        i = len(mids)
        while i and "particle" in tokens[mids[i - 1]].tags:
            i -= 1
            run.append(mids[i])
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
                    tuple(sorted(run))))
            for j in run:
                tokens[j] = copy_with(
                    tokens[j], role=Role.FAMILY,
                    tags=tokens[j].tags | {FOLDED_TAG})
            # recomputed for H1's reason, stated at H1: a stale index
            # list is the bug shape #359 fixed
            givens = _idx(tokens, Role.GIVEN)
            middles = _idx(tokens, Role.MIDDLE)
            families = _idx(tokens, Role.FAMILY)

    # rules/P6: "a particle ending the name attaches to that family
    # name" -- after a family comma with NOTHING before it. assign takes
    # the attachment wherever the comma names a family (#613); where it
    # names none, H1 and M4 above may make the given word the family
    # first, being gated on there being no family, and the attachment
    # has to read the name they left -- ', Mr. Jones vd' keeps family
    # 'Jones', suffix 'vd', as it read before #613 moved the site
    # (caught in PR review: assign's attachment ran ahead of H1 and read
    # given 'Jones', family 'vd'). The same helper, at the stage order
    # the old site had, so the reading is the old one exactly.
    if (state.structure is Structure.FAMILY_COMMA
            and len(state.pieces) > 1 and not state.pieces[0]):
        seg = state.pieces[1]
        k, end = particle_tail(seg, tokens)
        given_at = next((q for q in range(k) if any(
            tokens[i].role is Role.GIVEN for i in seg[q])), None)
        if given_at is not None:
            _attach_particle_tail(seg, tokens, given_at, k, end,
                                  ambiguities)

    if state.policy.two_family_names:
        _take_second_family_name(state, tokens)

    # rules/O3: "every middle word joins the family name and is
    # rendered before it" (v1 handle_middle_name_as_last). v1
    # PREPENDED middle_list to last_list; mechanisms.md#FOLDED_TAG:
    # "tokens never move: a rule that needs different rendering order
    # tags the token, and the rendering views consult the tag"
    if state.policy.middle_as_family:
        for i in _idx(tokens, Role.MIDDLE):
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
    for role in (Role.GIVEN, Role.MIDDLE, Role.FAMILY):
        part = _idx(tokens, role)
        all_particle = bool(part)
        conj: list[int] = []
        others = 0
        for i in part:
            tags = tokens[i].tags
            is_conj = "conjunction" in tags
            if is_conj:
                conj.append(i)
            if "particle" not in tags:
                all_particle = False
                if not is_conj:
                    others += 1
        if all_particle:
            for i in part:
                tokens[i] = copy_with(
                    tokens[i], tags=tokens[i].tags | {UNJOINED_TAG})
        elif conj and not others:
            # #461: nothing here for the connective to join. The `elif`
            # is deliberate -- where the part is all-particle R2's mark
            # already readmits every word, a word that is BOTH particle
            # and connective included, which is what keeps a caller's
            # `add(particles={"y"})` readings unchanged.
            for i in conj:
                tokens[i] = copy_with(
                    tokens[i],
                    tags=tokens[i].tags | {UNJOINED_CONJUNCTION_TAG})
    _mark_suffix_entries(tokens, state)
    return copy_with(state, tokens=tuple(tokens),
                     ambiguities=tuple(ambiguities))
