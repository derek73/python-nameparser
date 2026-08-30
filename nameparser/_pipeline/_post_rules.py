"""Stage: post_rules.

Consumes: tokens (roles assigned), plus pieces and structure -- the
particle fold reads the opening piece of segment 0, or of segment 1
under a family comma (#359), and P6's no-comma site reads the
TRAILING pieces of segment 0 (#365). structure was always read here,
for the rotation gate.
Produces: tokens with roles adjusted by the post rules, plus the
ambiguity P6's attachment reports for the fork it decides (#405).
Reads: Policy.patronymic_rules, Policy.middle_as_family;
Lexicon.given_name_titles.

Implements rules H1, M4, P1, P6, O1, O2, O3 and R2 of
docs/design/rules.md; each is cited at its code below. P6 is here at
TWO sites, one on each side of P1 -- see the comment at the first for
why neither can move to the other. H1/P1/O1/O2/P6's history lives in
docs/design/decisions.md.
"""
from __future__ import annotations

import dataclasses
import re

from nameparser._lexicon import _title_key
from nameparser._pipeline._assign import _name_positions
from nameparser._pipeline._state import (
    ParseState, PendingAmbiguity, Structure, WorkToken,
)
from nameparser._policy import PatronymicRule
from nameparser._types import (
    FOLDED_TAG, UNJOINED_TAG, AmbiguityKind, Role,
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


_NAME_ROLES = (Role.GIVEN, Role.MIDDLE, Role.FAMILY)

#: M4's two carve-outs, as the tags classify recorded them: a bound
#: given-name word is vocabulary claiming the word as a given name,
#: and `initial` is the shape claim. Neither is a predicate M4 owns.
_NEVER_FLIPPED = frozenset({"vocab:bound-given", "initial"})


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
        if any(tokens[i].role in _NAME_ROLES for i in piece):
            return piece
    return ()


def _retag(tokens: list[WorkToken], i: int, role: Role) -> None:
    tokens[i] = dataclasses.replace(tokens[i], role=role)


# rules.md#P2: "a particle joins the words after it into one name
# part, the join running until the next particle starts a group of
# its own, a trailing suffix begins"
# rules.md#P3: "the joined part is ONE name word wherever another
# rule counts them"
# rules.md#P5: "a recognized bound given-name word joins the word
# after it into one given name"
def _unit_end(tokens: list[WorkToken], idx: list[int], i: int) -> int:
    """One past the end of the unit starting at `idx[i]`.

    RECURSIVE, and that is the whole point: what a conjunction or a
    bound given-name word joins is the next UNIT, not the next word.
    Absorbing a single index instead strands a particle at the end of
    the unit, severed from the words it chains -- "de la Vega y la
    Vega" cut between `la` and `Vega`, reporting family
    "de la Vega y la", which is the same defect as a bare particle
    opening the given name, mirrored."""
    if "particle" in tokens[idx[i]].tags:
        j = i
        while j + 1 < len(idx) and "particle" in tokens[idx[j + 1]].tags:
            j += 1
        # ... then the words it joins, stopping where the next
        # particle starts a group of its own, at a suffix word (the
        # stop _group's chain uses), or at a conjunction, which the
        # shared loop below joins to the whole unit after it rather
        # than to the one word after it.
        while (j + 1 < len(idx)
               and "particle" not in tokens[idx[j + 1]].tags
               and "conjunction" not in tokens[idx[j + 1]].tags
               and "vocab:suffix" not in tokens[idx[j + 1]].tags):
            j += 1
        end = j + 1
    else:
        end = i + 1
        if "vocab:bound-given" in tokens[idx[i]].tags and end < len(idx):
            end = _unit_end(tokens, idx, end)
    while end + 1 < len(idx) and "conjunction" in tokens[idx[end]].tags:
        end = _unit_end(tokens, idx, end + 1)
    return end


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
    while i < len(idx):
        end = _unit_end(tokens, idx, i)
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


def _has_base(piece: tuple[int, ...], tokens: list[WorkToken]) -> bool:
    """Whether a PIECE holds a word no particle vocabulary claims --
    the base a particle can attach to. Callers pass a piece that
    already holds a name role, which is why the role is not re-asked
    here. No citation: R2 states "a particle needs a base to attach
    to" in an Accepted clause, and the excerpt test can only verify
    the part of a rule ahead of its first example."""
    return any("particle" not in tokens[i].tags for i in piece)


def _is_never_given_particle(token: WorkToken) -> bool:
    """Particle vocabulary that no culture uses as a given name -- the
    discriminator P1 and P6's no-comma site both key on, read off the
    tags classify recorded rather than re-asked of the lexicon."""
    return ("particle" in token.tags
            and "vocab:particle-ambiguous" not in token.tags)


def _is_lone_never_given_particle(site: tuple[int, ...],
                                  tokens: list[WorkToken]) -> bool:
    return len(site) == 1 and _is_never_given_particle(tokens[site[0]])


def post_rules(state: ParseState) -> ParseState:
    tokens = list(state.tokens)
    ambiguities = list(state.ambiguities)
    titles = _idx(tokens, Role.TITLE)
    givens = _idx(tokens, Role.GIVEN)
    middles = _idx(tokens, Role.MIDDLE)
    families = _idx(tokens, Role.FAMILY)

    # rules.md#H1: "a title followed by exactly one name word makes
    # that word the family name, whatever suffix, nickname or maiden
    # name stands beside it, unless the title is a given-name title,
    # which keeps it the given name" -- counting those three as
    # further name words is what emptied the family (#410)
    # (known gap: the guard tests which roles are unoccupied, it does
    # not count units -- decisions.md#H1) (v1 handle_firstnames)
    if titles and givens and not middles and not families:
        joined = _title_key(tokens[i].text for i in titles)
        if joined not in state.lexicon.given_name_titles:
            for i in givens:
                _retag(tokens, i, Role.FAMILY)
            # every rule below reads these lists; recompute after any
            # retag so no guard can inspect a name that has already
            # moved -- a stale index list is the bug shape #359 fixed
            givens = _idx(tokens, Role.GIVEN)
            middles = _idx(tokens, Role.MIDDLE)
            families = _idx(tokens, Role.FAMILY)

    # rules.md#M4: "a maiden name standing beside exactly one name
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
    # rules.md#P3 says a joined part is one name word wherever
    # another rule counts them, so the two disagree; widening moves
    # no corpus name and is not this change's to make
    # (decisions.md#M4).
    # rules.md#M4: "a word the vocabulary has claimed as a given name
    # keeps that reading, and so does a word written as an initial"
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

    # rules.md#P6: "a particle ending the name attaches to that
    # family name and is written before it" -- P6's other
    # precondition. A family comma names the family; so does a
    # declared family-first order, and the same Dutch listing is
    # written both ways: "Jong, Anke de" and "Jong Anke de" under
    # FAMILY_FIRST both give family "de Jong" (#365).
    #
    # NEVER-GIVEN vocabulary only, where the comma path takes
    # ambiguous particles too. P6 rests that on the comma leaving "no
    # signal that separates the two readings"; without one the
    # positional read is the signal, and P1 says what it decides --
    # "an ambiguous particle keeps whatever reading its position
    # gives it". That is what leaves the Vietnamese listing alone:
    # "Nguyen Thi Van" under family-first-given-last keeps given
    # "Van", P6's own example, where "Nguyen, Thi Van" loses it. The
    # cost is the Dutch flagship word: `van` is ambiguous vocabulary,
    # so "Beethoven Ludwig van" keeps middle "van" where the comma
    # form gives family "van Beethoven". The two forms agree for the
    # never-given half of the tussenvoegsel set and not for the rest.
    #
    # The suffix override is the comma path's alone for the same
    # reason -- a trailing `vd` or `mc` is a post-nominal until a
    # comma makes the tussenvoegsel commoner -- so the run is found
    # among the pieces that hold a NAME role, and a piece holding
    # none is walked past ("Berg Jan de Jr."). Not quite as the comma
    # path walks: its loop refuses to step over an all-particle piece,
    # which is how a suffix-roled `vd` stays part of the run there.
    #
    # THREE THINGS MUST REMAIN, and each was a defect in review
    # before it was a condition (decisions.md#P6, 2026-08-30):
    # a name word BESIDES the family, which is P6's own words-to-spare
    # test in the shape a positional read needs -- without it
    # "Jong de" attaches where "Jong, de" declines, and the two
    # writings of one listing disagree about word order; a BASE in the
    # piece that will be the family, since a family that is all
    # particles is not a family written beside anything -- without it
    # "van Berg Jan de" loses its given name outright, the leftover
    # collapsing to a single unit; and no SUFFIX WORD stranded at the
    # end, since assign left one in a name position only because the
    # particle followed it, and the re-layout does not re-run assign's
    # trailing peel -- without it "Berg Jan Jr. de" reports given
    # "Jr." under FAMILY_FIRST_GIVEN_LAST.
    #
    # Placed BEFORE P1, which is why P6 lands at two code sites. P1's
    # given-position site takes the same run under a family-first
    # order and takes it with the other reading -- the whole given
    # slot into the family, in written order, leaving no given name
    # ("Mesnil Garcia de" -> family "Mesnil Garcia de"). Attaching
    # first leaves it the runs this site declines, which is what
    # "Mesnil de" and "van der" still reach it for. The COMMA path
    # cannot move up here with it: it reads the roles P1 settles, for
    # the reason recorded at that site below.
    #
    # No structure test. A real family comma records no order, so
    # `state.order is not None` excludes it already; testing the
    # structure as well excludes only the comma that fixed NOTHING --
    # segment 1 holding no name word, assign reading segment 0
    # positionally (#296) -- where #365's symptom survives verbatim
    # ("Mesnil Garcia de, Dr."). Segment 0 is this site's for the same
    # reason, which is _leading_name_piece's rule read at `order is
    # not None`.
    #
    # What is left is a shorter name of the same order, and unlike
    # P1's fold the family is NOT among the pieces already placed, so
    # the remaining units take the positions _name_positions gives
    # them outright. At TWO of them that is family-then-given in
    # either family-first order, which is why the orders agree on
    # #365's shape; at three they differ again, and the declared
    # order is what decides given from middle.
    if (state.order is not None
            and state.order[0] is Role.FAMILY
            and state.pieces):
        seg = state.pieces[0]
        end = len(seg)
        while end and not any(tokens[i].role in _NAME_ROLES
                              for i in seg[end - 1]):
            end -= 1
        k = end
        while k and all(_is_never_given_particle(tokens[i])
                        for i in seg[k - 1]):
            k -= 1
        # The words-to-spare test is a name word ahead of the run,
        # and it must be one no particle vocabulary claims: what P6
        # attaches to is "the family written beside it", and a name
        # that is nothing but particles has no family written beside
        # anything. Without that second half the rule reorders inside
        # an all-particle name -- "van der" under a family-first
        # order attaching `der` to `van` and rendering "der van",
        # against words R2 reads as ordinary name words. Reordering
        # ordinary name words is not a thing any rule does.
        # P1's accepted "de" -> given="de" is the same test at one
        # piece.
        kept_pieces = [piece for piece in seg[:k]
                       if any(tokens[i].role in _NAME_ROLES for i in piece)]
        if (end > k and len(kept_pieces) > 1
                and _has_base(kept_pieces[0], tokens)
                and not all("vocab:suffix" in tokens[i].tags
                            for i in kept_pieces[-1])):
            for piece in seg[k:end]:
                for i in piece:
                    tokens[i] = dataclasses.replace(
                        tokens[i], role=Role.FAMILY,
                        tags=tokens[i].tags | {FOLDED_TAG})
            kept = [i for piece in seg[:k] for i in piece
                    if tokens[i].role in _NAME_ROLES]
            units = _units(tokens, kept)
            for unit, role in zip(units, _name_positions(
                    state.order, len(units))):
                for i in unit:
                    _retag(tokens, i, role)
            # recomputed for H1's reason, stated at H1: a stale index
            # list is the bug shape #359 fixed
            givens = _idx(tokens, Role.GIVEN)
            middles = _idx(tokens, Role.MIDDLE)
            families = _idx(tokens, Role.FAMILY)

    # rules.md#P1: "a never-given particle standing alone where the
    # given name would go — or opening the name — marks the name as
    # surname-only: the particle run and the name words it attaches
    # to are the family." (v1 handle_non_first_name_prefix; history:
    # decisions.md#P1)
    # How far the fold reaches depends on the order the name was READ
    # under (#395; decisions.md#P1, 2026-08-17): declaring a
    # family-first order asserts that what follows the family is not
    # more surname, which is the very question of where the run stops.
    # Under that declaration the run takes its own particles and ONE
    # name word; under the default order it keeps taking the rest of
    # the name, nothing having marked where the surname ends. The
    # narrowing is the LEADING site's alone: a particle
    # standing in the given slot keeps the old reach. Note what
    # actually holds the family-comma shape back, since it is NOT
    # that test -- "Smith, de Mesnil Juan" DOES fire the leading site,
    # segment 1 opening with the particle. It keeps the old reach
    # because assign records no order after a family comma, the comma
    # having already fixed the surname, so `order is None` here.
    # Anything that later gives that path an order turns the
    # narrowing on for it.
    # Code-local: a lone PIECE is the test at both sites, so a
    # particle group already chained forward is not a lone particle,
    # and rule H1 above cannot be what produces the fold's family
    # reading -- H1 is gated on `not families`.
    lead = _leading_name_piece(state, tokens)
    lead_fires = _is_lone_never_given_particle(lead, tokens)
    sites_fire = lead_fires or _is_lone_never_given_particle(
        tuple(givens), tokens)
    if len(givens) + len(middles) + len(families) > 1 and sites_fire:
        order = state.order
        if lead_fires and order is not None and order[0] is Role.FAMILY:
            # `state.order`, not policy.name_order: a script_orders
            # entry can put the family first under a given-first
            # policy, and the roles below have to match the read
            # assign actually made.
            # Minus what P6's site above already attached: the fold
            # lays out what is LEFT of the name, and a word another
            # rule has placed is not left. Without this the
            # redistribution hands the attached particle back to the
            # given slot it was taken out of ("de la Vega de" under a
            # family-first order). FOLDED_TAG is that site's alone
            # here -- O3's fold and P6's comma path both run later in
            # this stage.
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
    rotations_apply = state.structure is Structure.NO_COMMA
    # rules.md#O1: "a name of exactly three name words — titles,
    # suffixes and nicknames aside — whose last name word carries a
    # patronymic ending and whose middle name word does not reads as
    # family-first" (history: decisions.md#O1)
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
    # rules.md#O2: "a name of exactly four name words — titles,
    # suffixes and nicknames aside — ending in a standalone
    # patronymic marker reads family-first: the first name word is
    # the family name" (history: decisions.md#O2)
    if rotations_apply and PatronymicRule.TURKIC in rules and \
            len(givens) == 1 and len(middles) == 2 and len(families) == 1:
        tail = tokens[families[0]].text
        if _TURKIC.match(tail) or _TURKIC_CYR.match(tail):
            g, m1, m2, f = givens[0], middles[0], middles[1], families[0]
            _retag(tokens, m1, Role.GIVEN)
            _retag(tokens, m2, Role.MIDDLE)
            _retag(tokens, f, Role.MIDDLE)
            _retag(tokens, g, Role.FAMILY)
    # rules.md#P6: "a particle ending the name attaches to that family
    # name and is written before it" -- where a family comma has
    # already named the family, and provided at least one given word
    # remains (history: decisions.md#P6). The Dutch alphabetized
    # listing:
    # "Beethoven, Ludwig van" is how "Ludwig van Beethoven" is filed.
    #
    # Keyed on the token's VOCABULARY, not its assigned role, which is
    # what gives the attachment its stated precedence over S2. `vd`,
    # `mc` and `do` are the three words in both vocabularies; assign
    # reads a trailing `vd` or `mc` as a post-nominal, so those two
    # need the override. `do` is in the AMBIGUOUS acronym half, which
    # already leaves it a name word, so it attaches by the plain rule.
    # After a family comma the tussenvoegsel is the commoner reading.
    #
    # The words-to-spare guard is a piece test, not a count: every
    # trailing piece that is wholly particles attaches, and the run
    # must leave a GIVEN word ahead of it, so "Nguyen, Van" keeps its
    # only given word rather than being left with none. Only the
    # DEGENERATE Vietnamese listing is protected by that -- "Nguyen,
    # Thi Van" has a given word to spare, so `Van` attaches and the
    # given name is lost. rules.md#P6 records why that is accepted.
    #
    # mechanisms.md#FOLDED_TAG does the rest: tokens never move, so
    # the family view reads the tag and renders these before the base.
    if state.structure is Structure.FAMILY_COMMA and len(state.pieces) > 1:
        seg = state.pieces[1]
        # A post-nominal sits BEHIND the tussenvoegsel in this listing
        # ("Berg, Jan van Jr."), so the run is found by walking past a
        # trailing piece that holds no name -- but only one that is not
        # itself particle vocabulary, since `vd` arrives suffix-roled
        # and IS the run. Without this the same name parsed two ways on
        # whether a comma preceded the credential.
        end = len(seg)
        while (end
               and not any(tokens[i].role in _NAME_ROLES
                           for i in seg[end - 1])
               and not all("particle" in tokens[i].tags
                           for i in seg[end - 1])):
            end -= 1
        k = end
        while k and all("particle" in tokens[i].tags for i in seg[k - 1]):
            k -= 1
        # GIVEN alone, which is what P6 says ("provided at least one
        # given word remains"). Not `_NAME_ROLES`: P1's fold runs
        # earlier in this function and retags all of segment 1 to
        # FAMILY, so a test for "some name word remains" passes on
        # family text P1 just produced, and the rule then hoists the
        # particle in front of a base it never preceded ("Smith, de
        # Mesnil van" -> 'van Smith de Mesnil'). MIDDLE was in this
        # test until review found no input where it decides anything
        # -- 0 hits over 740,552 instrumented guard sites. The reason
        # is structural: the only rule that can leave a MIDDLE with no
        # GIVEN ahead of it in segment 1 is P1's family-first
        # redistribution, which is gated on `state.order`. On the
        # FAMILY_COMMA path assign records an order only where
        # segment 1 holds no name word (#296's positional read), and
        # a no-name segment holds no MIDDLE for the fold to leave
        # either. P6 runs only on that path, so the branch cannot be
        # reached from here.
        if k and any(tokens[i].role is Role.GIVEN
                     for piece in seg[:k] for i in piece):
            # A range, though only ever one piece today: grouping's
            # prefix chain makes a non-leading particle absorb what
            # follows, so a trailing run splits into several pieces
            # only where nothing ahead of it holds a given role --
            # the run opening the segment ("Berg, de van"), or only
            # titles ahead of it ("Berg, Sir de la", 8% of them). The
            # guard then declines either way. Measured over 95,180
            # generated multi-piece runs: `end - k` is never above 1
            # where the guard passes. Written as a range because the
            # guard, not this loop, is what bounds it.
            run = [i for piece in seg[k:end] for i in piece]
            # mechanisms.md#AMBIGUITY-AT-THE-DECISION-SITE: "Emit at
            # the site that takes the branch, not where an ambiguous
            # tag sits" -- this attachment is where the fork is
            # decided, so the report is raised here rather than in
            # assign, whose own emitter is scoped to the no-comma
            # shapes (#405).
            #
            # Two arms, keyed on what the attachment OVERRODE rather
            # than on what the words are, so each names a branch the
            # parse actually weighed. `declined_suffix` reads the role
            # assign gave the run, which is why both lists are built
            # BEFORE the re-roling loop below overwrites it.
            #
            # ORDERED, not asserted disjoint. The two cannot both hold
            # under the shipped vocabulary -- `vd` and `mc` are the
            # only words in both the particle and the unambiguous
            # suffix vocabularies, and neither is ambiguous particle
            # vocabulary -- but a caller's Lexicon may put one word in
            # both, and rules.md#A1 says parsing never fails on any
            # input, so this decides instead of raising. (Measured: an
            # assert here DID fire on `Berg, Jan zz` under a Lexicon
            # adding `zz` to particles_ambiguous and suffix_acronyms.)
            # The suffix arm wins because it names the reading the
            # parse actually took: assign had read the word as a
            # post-nominal, so the name-word reading was never on the
            # table for the attachment to decline.
            #
            # Both details name the ATTACHMENT and stop there. What
            # P6 decides is that the run joins the family the comma
            # named instead of standing on its own; how the joined
            # words then READ is R2's call, taken by the UNJOINED_TAG
            # loop at the end of this stage. The two can disagree:
            # `de la, Jan van` attaches `van` and leaves an
            # all-particle family, which R2 marks, so every other view
            # -- `family_base`, the initials, case repair -- reads
            # those words as ordinary name words ('Jan Van De La'
            # forced). A detail promising "read as the family's
            # particle" would contradict all three.
            ambiguous = [i for i in run
                         if "vocab:particle-ambiguous" in tokens[i].tags]
            declined_suffix = [i for i in run
                               if tokens[i].role is Role.SUFFIX]
            text = " ".join(tokens[i].text for i in run)
            if declined_suffix:
                ambiguities.append(PendingAmbiguity(
                    AmbiguityKind.SUFFIX_OR_NAME,
                    f"{text!r} written without periods is both a "
                    f"post-nominal and a family-name particle; after a "
                    f"family comma it joins the family the comma named "
                    f"rather than standing as a post-nominal",
                    tuple(run)))
            elif ambiguous:
                word = tokens[ambiguous[0]].text
                ambiguities.append(PendingAmbiguity(
                    AmbiguityKind.PARTICLE_OR_GIVEN,
                    f"{word!r} is both a family-name particle and an "
                    f"ordinary given name; after a family comma "
                    f"{text!r} joins the family the comma named "
                    f"rather than standing as a name word of its own",
                    tuple(run)))
            for i in run:
                tokens[i] = dataclasses.replace(
                    tokens[i], role=Role.FAMILY,
                    tags=tokens[i].tags | {FOLDED_TAG})

    # rules.md#O3: "every middle word joins the family name and is
    # rendered before it" (v1 handle_middle_name_as_last). v1
    # PREPENDED middle_list to last_list; mechanisms.md#FOLDED_TAG:
    # "tokens never move: a rule that needs different rendering order
    # tags the token, and the rendering views consult the tag"
    if state.policy.middle_as_family:
        for i in _idx(tokens, Role.MIDDLE):
            tokens[i] = dataclasses.replace(
                tokens[i], role=Role.FAMILY,
                tags=tokens[i].tags | {FOLDED_TAG})
    # rules.md#R2: "a name part whose every word is particle
    # vocabulary is a part where none of them is doing a particle's
    # work — nothing joins them to a name — so they read as ordinary
    # name words"
    #
    # Last in the stage, because every rule above can still move a
    # token between parts:
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
    for role in (Role.GIVEN, Role.MIDDLE, Role.FAMILY):
        part = _idx(tokens, role)
        if part and all("particle" in tokens[i].tags for i in part):
            for i in part:
                tokens[i] = dataclasses.replace(
                    tokens[i], tags=tokens[i].tags | {UNJOINED_TAG})
    return dataclasses.replace(state, tokens=tuple(tokens),
                               ambiguities=tuple(ambiguities))
