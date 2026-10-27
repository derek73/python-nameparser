"""Core runner over the shared case table. The facade
runner (migration plan) consumes the same CASES."""
import functools
import re
from typing import Any

import pytest

from nameparser import (Ambiguity, AmbiguityKind, ParsedName, Parser, Policy, ReadingKind,
                        ReadingSource,
                        Role, Token, locales, parser_for)
from nameparser._pipeline._state import FIELD_READING, NAME_ROLES
from nameparser._policy import FAMILY_FIRST, FAMILY_FIRST_GIVEN_LAST

from .cases import CASES, Case

_ORDER_NAMES = {FAMILY_FIRST: "family-first",
                FAMILY_FIRST_GIVEN_LAST: "family-first-given-last"}

_FIELDS = tuple(r.value for r in Role)  # declaration order is canonical


def _parser_for_case(case: Case) -> Parser:
    if case.locale is not None:
        return parser_for(locales.get(case.locale))
    return Parser(policy=case.policy) if case.policy else Parser()


@pytest.mark.parametrize("case", CASES, ids=lambda c: c.id)
def test_case(case: Case) -> None:
    parser = _parser_for_case(case)
    pn = parser.parse(case.text)
    actual = {f: getattr(pn, f) for f in _FIELDS if getattr(pn, f)}
    assert actual == case.expect, f"{case.text!r} ({case.classification})"
    kinds = sorted(a.kind.value for a in pn.ambiguities)
    assert kinds == sorted(case.ambiguities), \
        f"{case.text!r} ({case.classification})"


#: The orders the invariant below is checked under. A case row carries
#: its own policy where it needs one; these are applied to every row
#: that does NOT, because the shapes this invariant is about are mostly
#: reached under a family-first order and the table has almost no rows
#: that declare one.
_INVARIANT_ORDERS = (None, FAMILY_FIRST, FAMILY_FIRST_GIVEN_LAST)

_CASES_BY_ID = {c.id: c for c in CASES}

#: The (row, order) pairs the order sweep checks: every row under each
#: order, a row with its own policy only as declared, and no locale row
#: (a pack's parser is not one of the three orders). Both invariants
#: below walk this one list.
_SWEPT_ROWS = [(case, order) for case in CASES for order in _INVARIANT_ORDERS
               if case.locale is None
               and not (order is not None and case.policy)]
_SWEPT_IDS = [f"{case.id}-"
              f"{'as-declared' if order is None else _ORDER_NAMES[order]}"
              for case, order in _SWEPT_ROWS]


@functools.cache
def _swept(case_id: str,
           order: tuple[Role, Role, Role] | None) -> ParsedName:
    """One parse per row and order, shared by every invariant the
    sweep checks (AGENTS.md: a new invariant over an existing grid
    joins that grid's walk)."""
    case = _CASES_BY_ID[case_id]
    parser = (_parser_for_case(case) if order is None
              else Parser(policy=Policy(name_order=order)))
    return parser.parse(case.text)


@pytest.mark.parametrize("case,order", _SWEPT_ROWS, ids=_SWEPT_IDS)
def test_the_family_partitions_into_particles_and_base(
        case: Case, order: tuple[Role, Role, Role] | None) -> None:
    """rules/R2's invariant: a particle needs a base to attach to,
    so a family made only of particles is a family whose words are not
    acting as particles -- and therefore a non-empty family always has
    a non-empty base.

    Asserted as a PARTITION, which is the stronger form: the family's
    words are exactly the particles' words plus the base's words. That
    catches over-marking as well as under-marking, where "the base is
    non-empty" catches only the second. Word multisets rather than
    strings, because the family renders in written order while the two
    views render particles first ("Vega, de la" is family 'Vega de la',
    particles 'de la', base 'Vega').
    """
    pn = _swept(case.id, order)
    if not pn.family:
        return
    assert pn.family_base, (
        f"{case.text!r}: family={pn.family!r} but family_base is "
        f"empty (particles={pn.family_particles!r})")
    assert sorted(pn.family.split()) == sorted(
        (pn.family_particles + " " + pn.family_base).split()), (
        f"{case.text!r}: family={pn.family!r} is not partitioned by "
        f"particles={pn.family_particles!r} + base={pn.family_base!r}")


_NAME_FIELDS = frozenset(NAME_ROLES)

#: Every way a report's detail names the field its word was read into,
#: mapped to the fields that make it true: assemble's FIELD_READING,
#: which words every report a later rule could move (#626), plus the
#: phrasings worded where the field is settled -- a comma's credential
#: reading, the suffix run's and the numeral fork's ("reads as part of
#: the suffix run", "a generational suffix"), H4's "the name", P6's
#: "joins the family". A report that names a READING rather than a
#: field ("read as an initial") is out of scope, as is any phrasing
#: not listed here: the count below is what notices the list going
#: stale.
_FIELD_CLAIMS: dict[str, frozenset[Role]] = {
    **{reading: frozenset({role}) for role, reading in FIELD_READING.items()},
    **dict.fromkeys(("a credential", "a generational suffix",
                     "part of the suffix run", "a post-nominal"),
                    frozenset({Role.SUFFIX})),
    "a name": _NAME_FIELDS, "the name": _NAME_FIELDS,
    "the family": frozenset({Role.FAMILY}),
}
_FIELD_CLAIM = re.compile(
    r"\b(?:reads? as|joins) ("
    + "|".join(map(re.escape, sorted(_FIELD_CLAIMS, key=len, reverse=True)))
    + r")\b")


@pytest.mark.parametrize("case,order", _SWEPT_ROWS, ids=_SWEPT_IDS)
def test_a_report_names_the_field_its_word_lands_in(
        case: Case, order: tuple[Role, Role, Role] | None) -> None:
    """#626: a report's detail that names the field its word was read
    into names the field the word holds in the RESULT. Rules in
    post_rules move a word after assign reports it -- H1's move behind
    a title, P1's family-first fold, P6's attachment, and under opt-in
    policies the patronymic rotations, O6's two family names and
    `middle_as_family`'s fold,
    which rows carrying those policies reach as declared -- and six of
    assign's reports were worded from the role at assign, so
    'Kim Min Do' under FAMILY_FIRST was told 'Do' was a middle name
    when it landed in the family. Assemble words them now.

    Checked over `_SWEPT_ROWS`, which the count test below walks too.

    Negative control, measured 2026-10-08 and re-measured 2026-10-10
    over the rows after #624 (which rewrote six of them): this test
    over master's parser (26cdb891) fails 14 parses, every one a report
    worded at assign -- nine title-or-name join reports saying 'given'
    of a unit H1 moved to the family behind a title (`Attorney General
    of Minnesota`, `John of Bishop Prof.`, `Freiherr St MA`, `Freiherr
    von Bishop X.Y.Z.` and five more rows, as declared; on 2026-10-08
    `St St née` stood where `Freiherr St John Smith MA` does), `Kim Min Do`
    under FAMILY_FIRST ('middle', family, P6), `de Kim Ma` under
    FAMILY_FIRST ('middle', given, P1), and the opt-in movers' rows as
    declared: `Van Ivan Petrovich` and `Van Ali Veli oglu` ('given',
    family, O1 and O2) and `Do Bishop Do` ('middle', family, O3). The
    sixth emitter, the comma report on a word after an empty head, is
    NOT in that count: master
    worded it 'the given name', a phrasing the tree no longer emits
    and so not one `_FIELD_CLAIMS` lists, and `, Ma Dr.` (H1 moving it
    to the family) is pinned instead by test_assign.py's verbatim
    detail. No row reached that shape until #626's review.

    #793's control, measured 2026-10-21: with the comma stage's
    listed-member report worded "read as a credential" again, this
    test fails 6 parses -- `John, Si.` and `John, Ma.` under each
    order, a word the listing form binds as a title.
    """
    pn = _swept(case.id, order)
    for a in pn.ambiguities:
        m = _FIELD_CLAIM.search(a.detail)
        if m is None:
            continue
        landed = {t.role for t in a.tokens}
        assert landed <= _FIELD_CLAIMS[m[1]], (
            f"{case.text!r}: {a.kind.value} says {m[0]!r} but its "
            f"tokens landed in {sorted(r.value for r in landed)}: "
            f"{a.detail!r}")


def test_the_field_sweep_sees_the_claims_it_checks() -> None:
    """The sweep above passes vacuously if no detail matches
    `_FIELD_CLAIM` -- an emitter reworded out of the list, or rows
    dropped -- so the count of claims it checks is recorded here.
    Move it deliberately when a row or a phrasing moves, never to 0."""
    claims = sum(
        _FIELD_CLAIM.search(a.detail) is not None
        for case, order in _SWEPT_ROWS
        for a in _swept(case.id, order).ambiguities)
    # 1156 -> 1159 on 2026-10-11: the JOHN PROF. MA row (one
    # suffix-or-name claim under each of the three orders); 1159 ->
    # 1162 on 2026-10-14: the Агриппина Младшая row (#661, one
    # given-or-family claim under each order); 1162 -> 1171 on
    # 2026-10-17: three #701 rows reporting suffix-or-name, under each
    # order; 1171 -> 1174 on 2026-10-17: the エリザベス二世 row (#707,
    # one given-or-family claim under each order); 1174 -> 1172 on
    # 2026-10-17: #718's re-pinned and added numeral rows (the lone
    # numeral rows lose their given-or-family claims; the 'John III'
    # row brings some back); 1172 -> 1191 on 2026-10-18:
    # #718's declined-numeral report, which names the field the letter
    # was read into, on those rows under each order; 1191 -> 1210 the
    # same day: the PR review's rows (the chain-taken, family-first,
    # lowercase and maiden-clause numerals); 1210 -> 1243 the same day:
    # #721's rows (#722); 1243 -> 1246 the same day: #727's
    # '田中さん v' row (one suffix-or-name claim under each order);
    # 1246 -> 1252 the same day: #656's two C12 rows behind a nickname
    # and a maiden clause (one suffix-or-name claim under each order);
    # 1252 -> 1255 the same day: the C12 row with a title in the part;
    # 1255 -> 1282 on 2026-10-21: #791's nine reporting rows (si and
    # chi), one suffix-or-name or given-or-family claim under each order;
    # 1282 -> 1302 the same day: the review's empty-head, caps and
    # family-first rows (two reports on 'Luo SI', and the family-first
    # rows, which carry their own policy and so claim under one order);
    # 1302 -> 1308 on 2026-10-21: #796's two case rows (Robert Capa,
    # John Smith CAPA), each claiming under the three orders;
    # 1308 -> 1314 the same day: #797's PA and John Pa rows, each
    # claiming one suffix-or-name report under the three orders;
    # 1314 -> 1341 the same day: #793's nine reporting rows ('John,
    # Si.', 'John, Ma.' and the #794 review's seven), one
    # suffix-or-name claim each under the three orders; 1341 -> 1353
    # on 2026-10-23: #848's four Ing rows, one suffix-or-name claim
    # each under the three orders; 1353 -> 1356 the same day: the
    # review's 'Novak, Ing.' row; 1356 -> 1359 the same day: the second
    # review's 'Novak, ING.' row; 1359 -> 1362 the same day: #853's
    # 'Uddin, Md Karim' row, one suffix-or-name claim under the three
    # orders; 1362 -> 1365 the same day: the review's 'Uddin, Mr Md
    # Karim' row, the same claim behind a title; 1365 -> 1368 on
    # 2026-10-24: the glued-semicolon row 'John Smith, MA; PhD', one
    # suffix-or-name claim under the three orders; 1368 -> 1396 the
    # same day: #864's paired-initials and gc rows, nine claiming one
    # suffix-or-name report under each order and the switch-off row,
    # which carries its own policy, under one; 1396 -> 1399 the same
    # day: the review's 'Jane Doe MA R.T.' row, one claim under each;
    # 1399 -> 1400 the same day: #754's 'Beethoven Ludwig Maria van'
    # row, which carries its own policy, one particle-or-given claim;
    # 1400 -> 1403 the same day: #835's particle row 'Doe, Jane van
    # Mrs', one particle-or-given claim under each order; 1403 -> 1406
    # the same day: #857's sa rows, after the word left every set (the
    # one reporting row, 'Smith, S.A.', claims under the orders it
    # reaches); 1406 -> 1415 the same day: the review's comma rows for
    # sa and the listed `ma` twins, three of them reporting; 1415 ->
    # 1445 the same day: #752's numeral rows (phase 2f) and the
    # 'Dr. Smith VI, John' row, which reports since, each claim under
    # the three orders; 1445 -> 1451 the same day: #752's two
    # joined-capitals rows that report (phase 2d), one suffix-or-name
    # claim under each order; 1451 -> 1493 the same day: #752's
    # generation-word rows (phase 2h, fils and the agnomens), the claims
    # their reports make under the three orders; 1493 -> 1508 the same
    # day: #890's five rows with a suffix word in front of an agnomen;
    # 1508 -> 1514 the same day: its numeral and capitals rows; 1514
    # -> 1517 the same day: its carried-member rows; 1517 -> 1520 the
    # same day: its joined-surname row; 1520 -> 1523 the same day: the
    # floor's fils rows; 1523 -> 1529 the same day: its comma rows;
    # 1529 -> 1568 the same day, #891 (phase 2e) merged over it: the
    # split-credential rows, two run rows and the particle-chain row
    # (9), the split credential's own report on nine rows (27) and the
    # opening-credential row (3), each claim under the three orders;
    # 1568 -> 1583 the same day: #752's title phrase rows (phase 2i), the
    # five that report a title read as a name, under the three orders;
    # 1583 -> 1592 on 2026-10-26: Derek's answers on #894, three rows
    # that report ('Sgt Marshal', 'Marshal Yanda', 'Grace Dean'), the
    # one that stopped ('SMITH, DEAN MR.') offset by 'Grace Smith';
    # 1592 -> 1586 the same day: 'Grace Smith' and 'Grace Dean Smith'
    # stopped reporting, no listed phrase holding 'grace'; 1586 -> 1592
    # the same day: 'Justice Smith' and 'Major Smith', which report.
    # 1568 -> 1310 the same day, #785 (phase 2g): a listed member its
    # capitals settle in a name of mixed case reports nothing, which
    # takes the claims of the rows that reported one (each under
    # the orders it reaches); its new rows add their run reports, and
    # the rows rewritten in one case or lower case to keep reaching
    # their emitter add theirs back; 1310 -> 1316 the same day, the
    # review's rows for the comma's opening word and the chain's stop;
    # 1316 -> 1318 on 2026-10-26, the narrowing's caps-switch numeral row;
    # 1318 -> 1321 the same day, its Ph./D. row.
    # 1321 + 24 = 1345 on 2026-10-26, #894 (phase 2i) merged over #895
    # (phase 2g): 2i's net change from 1568 (1592 - 1568), the two
    # changes moving disjoint claims.
    # 1345 -> 1366 on 2026-10-26, #810 (phase 2l): seven rows whose
    # bracketed member stays the nickname, one suffix-or-nickname or
    # given-or-family claim each under each order; 1366 -> 1369 the same
    # day, its review round: 'Jack (MA)' keeps N3's family and loses its
    # given-or-family claims (-3), 'John Smith (MA) VI' (+3) and the
    # dotted 'Jean (M.A) Smith', reported now (+3); 1369 -> 1381 the same
    # day, the twin reading (Derek): 'Jack (MA)' and 'Jack (M.A)' read
    # as 'Jack (PhD)' does, a given-or-family claim each (+6), and
    # 'John Smith (MA) née Jones' its two suffix-or-name claims (+6);
    # 1381 -> 1390 the same day, its review round's rows: a member
    # beside a dropped character (+3) and before 'Ma' (+6); 1390 -> 1384
    # the same day, one pass in place of the twin reading (Derek):
    # 'Jack (MA)' and 'Jack (M.A)' lose their given-or-family claims and
    # 'John Smith (MA) née Jones' its two suffix-or-name claims (-12),
    # and the two clauses a second pass would settle keep the nickname,
    # reported (+6); 1384 -> 1390 the same day, its review round's rows
    # for a leading period and a name of no word (+6); 1390 -> 1393 the
    # same day, #752 phase 2j's 'Nasreen Sultana, MBBS', the credential
    # behind two name words reported suffix-or-name under three orders;
    # 1393 -> 1396 on 2026-10-27, #892's ', Mr. Jones vd' reporting the
    # suffix-or-name P6's attachment decides, under three orders; 1396
    # -> 1403 the same day, the #916 review's rows (', Dr. Jones vd
    # Jr.' and ', Dr. Jones vd, PhD' under three orders, and ', Jane
    # van Jr.' under FAMILY_FIRST); 1403 -> 1412 the same day, #843's
    # three abbreviated-agnomen rows, one suffix-or-name claim each under
    # the three orders.
    assert claims == 1412, (
        f"the field sweep checks {claims} claims, recorded as 1412 on "
        f"2026-10-27")


#: The kinds that report a fork between two readings of a word, so carry
#: the reading not taken: three of the rest report a shape, and `order`
#: is reserved (#752 phase 2m).
_FORK_KINDS = frozenset(AmbiguityKind) - {
    AmbiguityKind.COMMA_STRUCTURE, AmbiguityKind.UNBALANCED_DELIMITER,
    AmbiguityKind.SEGMENTATION, AmbiguityKind.ORDER}

#: The field a non-name reading names by what it is.
_FIELD_OF_KIND = {
    **dict.fromkeys((ReadingKind.CREDENTIAL, ReadingKind.GENERATION,
                     ReadingKind.AGNOMEN, ReadingKind.POST_NOMINAL), Role.SUFFIX),
    ReadingKind.TITLE: Role.TITLE, ReadingKind.PARTICLE: Role.FAMILY,
}

#: A plain word of each kind the oracle below writes in place of the
#: referent, in the referent's case: a name word, an initial and a
#: connective no rule reads as anything else.
_STAND_INS = {ReadingKind.NAME: "Zork", ReadingKind.INITIAL: "Q",
              ReadingKind.CONJUNCTION: "y"}

#: (row, order) pairs whose stand-in reads differently from the
#: alternative because the stand-in changes a reading OTHER than the
#: referent's, which the alternative holds fixed: a word behind it
#: that the run or the numeral fork had read as a suffix becomes a name
#: word ('John Smith VI Jones'), a word in a given part's credential
#: run is absorbed as a particle never is ('Smith, John PhD de PhD
#: van'), and a
#: bracketed shape read as if written bare (rules/S1) has a stand-in
#: that stays bracketed ('Andrew Perkins (X.Y.Z.)'). Measured
#: 2026-10-26.
_STAND_IN_REREADS = {
    ("John Smith Pharm D Jones", None), ("John Smith Pharm D Jones", 2),
    ("Smith, John PhD de PhD van", None), ("Smith, John PhD de PhD van", 1),
    ("Smith, John PhD de PhD van", 2),
    ("Smith, John PhD Jr. de la", None), ("Smith, John PhD Jr. de la", 1),
    ("Smith, John PhD Jr. de la", 2),
    ("Andrew Perkins (X.Y.Z.)", None), ("Andrew Perkins (X.Y.Z.)", 1),
    ("Andrew Perkins (X.Y.Z.)", 2),
    ("John Smith VI Ma", None), ("John Smith VI Jones", None),
    ("John Smith VI Jones", 2),
}

#: Reports whose deferred field assign could not name: the particle the
#: chain took ends in a title a connective's join made ('Freiherr von
#: Berg Dr. and Ed. Prof.', where group's joins left no name piece), so
#: the alternative is withheld rather than guessed.
_NO_ALTERNATIVE = {("Freiherr von Berg Dr. and Ed. Prof.", o)
                   for o in (None, 1, 2)}


def _order_key(order: tuple[Role, Role, Role] | None) -> int | None:
    return None if order is None else _INVARIANT_ORDERS.index(order)


def _parser_for(case: Case | None,
                order: tuple[Role, Role, Role] | None) -> Parser:
    if case is not None and order is None:
        return _parser_for_case(case)
    return Parser(policy=Policy(name_order=order)) if order else Parser()


def _stand_in(parser: Parser, pn: ParsedName, a: Ambiguity,
              kind: ReadingKind) -> tuple[str, Role]:
    """The name with the report's referents replaced by `kind`'s plain
    word, written in their case, and the field that word lands in."""
    first, last = a.tokens[0].span, a.tokens[-1].span
    assert first is not None and last is not None
    written = pn.original[first.start:last.end]
    letters = [c for c in written if c.isalpha()]
    word = _STAND_INS[kind]
    if len(letters) > 1 and all(c.isupper() for c in letters):
        word = word.upper()
    elif letters and all(c.islower() for c in letters):
        word = word.lower()
    text = pn.original[:first.start] + word + pn.original[last.end:]
    landed = next(t.role for t in parser.parse(text).tokens
                  if t.span is not None and t.span.start == first.start)
    return text, landed


def _opens_its_part(pn: ParsedName, token: Token) -> bool:
    """No name word before `token` in its comma part."""
    assert token.span is not None
    for t in pn.tokens:
        if t.span is None or t.span.start >= token.span.start:
            break
        if "," in pn.original[t.span.end:token.span.start]:
            continue
        if t.role in _NAME_FIELDS:
            return False
    return True


def _check_alternatives(key: tuple[str, int | None], pn: ParsedName,
                        parser: Parser) -> None:
    for a in pn.ambiguities:
        alt = a.alternative
        if a.kind not in _FORK_KINDS:
            assert alt is None, (key, a)
            continue
        if key in _NO_ALTERNATIVE and alt is None:
            continue
        if (alt is None and a.kind is AmbiguityKind.CONJUNCTION_OR_INITIAL
                and _opens_its_part(pn, a.tokens[0])):
            # a connective with no word before it to join: no field
            continue
        assert alt is not None, f"{key[0]!r}: {a.kind.value} has none"
        if alt.kind in _FIELD_OF_KIND:
            assert alt.role is _FIELD_OF_KIND[alt.kind], (key, a, alt)
            continue
        if a.kind is AmbiguityKind.GIVEN_OR_FAMILY:
            # rules/O5's other convention, which no stand-in can reach
            assert {a.tokens[0].role, alt.role} == {Role.GIVEN,
                                                    Role.FAMILY}, (
                key, a, alt)
            continue
        if key in _STAND_IN_REREADS:
            continue
        text, landed = _stand_in(parser, pn, a, alt.kind)
        if landed is a.tokens[0].role:
            continue
        assert landed is alt.role, (
            f"{key[0]!r}: {a.kind.value} says its {alt.kind.value} "
            f"reading lands in {alt.role.value}, but {text!r} puts the "
            f"stand-in in {landed.value}")


@pytest.mark.parametrize("case,order", _SWEPT_ROWS, ids=_SWEPT_IDS)
def test_an_alternative_names_the_field_the_other_reading_gives(
        case: Case, order: tuple[Role, Role, Role] | None) -> None:
    """#752 phase 2m: every report of a fork carries the reading the
    parse did not take, and its role is the field the token would have
    had under it. A non-name reading names its field by what it is (a
    credential the suffix, a particle the family). A name reading is
    checked by an ORACLE: the referent is replaced by a plain word of
    the alternative's kind in its case ('Zork', 'Q', 'y') and the name
    parsed again under the same parser, where the stand-in must land in
    the alternative's field. The stand-in removes the word's own
    reading, not the position: where it still lands in the taken field
    the decision was the position's, which the oracle cannot undo, and
    the pair is not checked; the count test below records how many are.
    `_STAND_IN_REREADS` lists the pairs where the stand-in moves a
    NEIGHBOUR's reading too.

    Negative control, measured 2026-10-26: with the trailing peel's
    name alternative pinned to the family (`as_a_name`'s field in
    `_assign_main`), this test fails 63 parses, the family-first rows
    whose taken suffix would be the given or middle name; with
    `_name_alt` never deferring to the piece in front, 16 (15 before
    the first review's fixes, re-taken after them)."""
    _check_alternatives((case.text, _order_key(order)),
                        _swept(case.id, order), _parser_for(case, order))


#: Shapes no case row holds, each found by the first review of #752
#: phase 2m with a field named wrong: a numeral or credential with no
#: name word before it (the carve-out's name word uncounted), a numeral
#: behind a particle P6 then attached (read as a live chain), a bound
#: given name before a numeral with no family word left for its join,
#: and a particle P6 attached behind a particle chain (named from its
#: own field, not the chain's). The second review's six follow.
_REVIEW_SHAPES = ("PhD VI", "Jr VI", "III VI", "Smith, John van VI",
                  "John Smith van VI", "abdul VI", "Abu VI", "Dr. abdul VI",
                  "Smith, Freiherr von Berg van", "Juan de la Vega van",
                  # the second review's: a bound join that is no chain
                  # though `abu` is a particle, a given-name title that
                  # licenses the bound join, and a never-given particle
                  # opening the part, which P1 folds with the word
                  "Smith, Abu Mary van", "Smith, Abu Mary VI",
                  "Sir abdul VI", "Dr. mc VI", "de VI", "Smith, Dr. de VI",
                  # the PR review's: a given-name title licenses the
                  # bound join only from the leading run, as group asks
                  "abdul VI Sir.", "Sir Dr. abdul VI", "Dr. Sir abdul VI")


@pytest.mark.parametrize("order", _INVARIANT_ORDERS)
@pytest.mark.parametrize("text", _REVIEW_SHAPES)
def test_an_alternative_names_the_field_in_the_reviews_shapes(
        text: str, order: tuple[Role, Role, Role] | None) -> None:
    """The oracle above over `_REVIEW_SHAPES`. Negative controls,
    measured 2026-10-26: with the first review's fixes reverted this
    failed 34 of its then 48 parses, and with the second review's, 14;
    with `as_a_name`'s given-name-title licence asked of every title
    token rather than the leading run, as the PR review found it, 3 of
    its 57."""
    parser = _parser_for(None, order)
    pn = parser.parse(text)
    _check_alternatives((text, _order_key(order)), pn, parser)


_FF = FAMILY_FIRST
#: (text, policy fields) -> each report's (kind, alternative), the
#: alternative as (reading kind, role, source) or None. One row per
#: branch of `_vocab.suffix_reading` and `name_reading`, per emitter the
#: oracle above cannot check (a credential run's, whose stand-in is
#: read by the same run; a one-case connective's, whose stand-in is an
#: initial too), per `_resolve_deferred` branch, and per fold
#: `middle_as_family` makes in assemble.
_EXPECTED_ALTERNATIVES: dict[tuple[str, tuple[tuple[str, Any], ...]],
                             tuple[tuple[AmbiguityKind,
                                         tuple[ReadingKind, Role,
                                               ReadingSource] | None], ...]] = {
    # suffix_reading: agnomen, generation word, listed and shaped
    # numeral, other post-nominal word, listed and shaped credential
    ("Joao Neto", ()): ((AmbiguityKind.SUFFIX_OR_NAME, (
        ReadingKind.AGNOMEN, Role.SUFFIX, ReadingSource.VOCABULARY)),),
    ("Jean Fils", ()): ((AmbiguityKind.SUFFIX_OR_NAME, (
        ReadingKind.GENERATION, Role.SUFFIX, ReadingSource.VOCABULARY)),),
    ("John V", ()): ((AmbiguityKind.SUFFIX_OR_NAME, (
        ReadingKind.GENERATION, Role.SUFFIX, ReadingSource.VOCABULARY)),),
    ("John Smith Vi", ()): ((AmbiguityKind.SUFFIX_OR_NAME, (
        ReadingKind.GENERATION, Role.SUFFIX, ReadingSource.SHAPE)),),
    ("Esq Jr", ()): ((AmbiguityKind.SUFFIX_OR_NAME, (
        ReadingKind.POST_NOMINAL, Role.SUFFIX, ReadingSource.VOCABULARY)),),
    ("Jack Ma", ()): ((AmbiguityKind.SUFFIX_OR_NAME, (
        ReadingKind.CREDENTIAL, Role.SUFFIX, ReadingSource.VOCABULARY)),),
    ("Jack X.Y.Z.", ()): ((AmbiguityKind.SUFFIX_OR_NAME, (
        ReadingKind.CREDENTIAL, Role.SUFFIX, ReadingSource.SHAPE)),),
    ("(MA) John Smith", ()): ((AmbiguityKind.SUFFIX_OR_NICKNAME, (
        ReadingKind.CREDENTIAL, Role.SUFFIX, ReadingSource.VOCABULARY)),),
    # name_reading: an initial, a declared name, a word by position
    ("John Smith V", ()): ((AmbiguityKind.SUFFIX_OR_NAME, (
        ReadingKind.INITIAL, Role.FAMILY, ReadingSource.SHAPE)),),
    ("JOHN SMITH MA", ()): ((AmbiguityKind.SUFFIX_OR_NAME, (
        ReadingKind.NAME, Role.FAMILY, ReadingSource.DECLARED)),),
    ("John Smith PhD Jones", ()): ((AmbiguityKind.SUFFIX_OR_NAME, (
        ReadingKind.NAME, Role.FAMILY, ReadingSource.POSITION)),),
    ("Smith", ()): ((AmbiguityKind.GIVEN_OR_FAMILY, (
        ReadingKind.NAME, Role.FAMILY, ReadingSource.POSITION)),),
    ("Van Buren", ()): ((AmbiguityKind.PARTICLE_OR_GIVEN, (
        ReadingKind.PARTICLE, Role.FAMILY, ReadingSource.VOCABULARY)),),
    ("Freiherr von Berg MA", ()): ((AmbiguityKind.PARTICLE_OR_GIVEN, (
        ReadingKind.NAME, Role.GIVEN, ReadingSource.DECLARED)),),
    ("Dean Koontz", ()): ((AmbiguityKind.TITLE_OR_NAME, (
        ReadingKind.TITLE, Role.TITLE, ReadingSource.VOCABULARY)),),
    # the credential runs' emitters, behind a credential and after a
    # comma, the maiden clause's, and the split credential's (S12)
    ("Doe, John MA Smith", ()): ((AmbiguityKind.SUFFIX_OR_NAME, (
        ReadingKind.NAME, Role.MIDDLE, ReadingSource.POSITION)),),
    ("Dr. Smith Jr., AD", ()): ((AmbiguityKind.SUFFIX_OR_NAME, (
        ReadingKind.NAME, Role.GIVEN, ReadingSource.POSITION)),),
    ("JOHN SMITH, VD MA", ()): ((AmbiguityKind.SUFFIX_OR_NAME, (
        ReadingKind.NAME, Role.GIVEN, ReadingSource.POSITION)),),
    ("Smith, PhD Ma", ()): ((AmbiguityKind.SUFFIX_OR_NAME, (
        ReadingKind.NAME, Role.GIVEN, ReadingSource.DECLARED)),),
    ("JANE DOE NEE SMITH MA", ()): ((AmbiguityKind.SUFFIX_OR_NAME, (
        ReadingKind.NAME, Role.MAIDEN, ReadingSource.DECLARED)),),
    ("JOHN SMITH SAM E.", ()): ((AmbiguityKind.SUFFIX_OR_NAME, (
        ReadingKind.NAME, Role.FAMILY, ReadingSource.POSITION)),),
    # a one-case connective, lone and inside a joined piece, with and
    # without a family comma on either side, and opening the name; in a
    # three-word name P3 joins nothing, and the letter keeps its field,
    # where a family comma's surname is the third word that lets it join
    ("JOSE E MARIA SANTOS", ()): ((AmbiguityKind.CONJUNCTION_OR_INITIAL, (
        ReadingKind.CONJUNCTION, Role.GIVEN, ReadingSource.VOCABULARY)),),
    ("JOHN E SMITH", ()): ((AmbiguityKind.CONJUNCTION_OR_INITIAL, (
        ReadingKind.CONJUNCTION, Role.MIDDLE, ReadingSource.VOCABULARY)),),
    ("JOHN E SMITH", (("name_order", _FF),)): (
        (AmbiguityKind.CONJUNCTION_OR_INITIAL, (
            ReadingKind.CONJUNCTION, Role.GIVEN, ReadingSource.VOCABULARY)),),
    ("SMITH, JOHN E MARY", ()): ((AmbiguityKind.CONJUNCTION_OR_INITIAL, (
        ReadingKind.CONJUNCTION, Role.GIVEN, ReadingSource.VOCABULARY)),),
    ("MARIA DA SILVA E SOUZA", ()): ((AmbiguityKind.CONJUNCTION_OR_INITIAL, (
        ReadingKind.CONJUNCTION, Role.FAMILY, ReadingSource.VOCABULARY)),),
    ("SMITH, JOHN E MARY ANN", ()): ((AmbiguityKind.CONJUNCTION_OR_INITIAL, (
        ReadingKind.CONJUNCTION, Role.GIVEN, ReadingSource.VOCABULARY)),),
    ("SMITH E JONES, JOHN", ()): ((AmbiguityKind.CONJUNCTION_OR_INITIAL, (
        ReadingKind.CONJUNCTION, Role.FAMILY, ReadingSource.VOCABULARY)),),
    ("E SMITH JONES", ()): ((AmbiguityKind.CONJUNCTION_OR_INITIAL, None),),
    # middle_as_family folds a middle alternative as it folds the middle
    ("Doe, John MA Smith", (("middle_as_family", True),)): (
        (AmbiguityKind.SUFFIX_OR_NAME, (
            ReadingKind.NAME, Role.FAMILY, ReadingSource.POSITION)),),
    ("John Smith PhD Jones", (("name_order", _FF),)): (
        (AmbiguityKind.SUFFIX_OR_NAME, (
            ReadingKind.NAME, Role.MIDDLE, ReadingSource.POSITION)),),
    ("John Smith PhD Jones", (("name_order", _FF),
                              ("middle_as_family", True))): (
        (AmbiguityKind.SUFFIX_OR_NAME, (
            ReadingKind.NAME, Role.FAMILY, ReadingSource.POSITION)),),
}


@pytest.mark.parametrize("key", _EXPECTED_ALTERNATIVES,
                         ids=[f"{t}{dict(p)}" for t, p in
                              _EXPECTED_ALTERNATIVES])
def test_an_alternative_has_its_recorded_kind_role_and_source(
        key: tuple[str, tuple[tuple[str, Any], ...]]) -> None:
    """The reading kind and source are pinned only here and by the
    snapshot, so every branch that chooses them has a row."""
    text, fields = key
    pn = Parser(policy=Policy(**dict(fields))).parse(text)
    got = tuple(
        (a.kind, None if a.alternative is None else (
            a.alternative.kind, a.alternative.role, a.alternative.source))
        for a in pn.ambiguities)
    assert got == _EXPECTED_ALTERNATIVES[key]


def test_the_alternative_sweep_sees_the_fields_it_checks() -> None:
    """The oracle above skips a pair whose stand-in keeps the taken
    field, so a change that made every decision positional would pass
    it vacuously: the counts it checks and skips are recorded here."""
    checked = skipped = 0
    for case, order in _SWEPT_ROWS:
        if (case.text, _order_key(order)) in _STAND_IN_REREADS:
            continue
        pn = _swept(case.id, order)
        parser = _parser_for(case, order)
        for a in pn.ambiguities:
            alt = a.alternative
            if (alt is None or alt.kind not in _STAND_INS
                    or a.kind is AmbiguityKind.GIVEN_OR_FAMILY):
                continue
            _, landed = _stand_in(parser, pn, a, alt.kind)
            if landed is a.tokens[0].role:
                skipped += 1
            else:
                checked += 1
    # measured 2026-10-26: 435 stand-ins land in the alternative's
    # field, 296 keep the taken one; 435 -> 436 the same day, the first
    # review's fix to P6's report ('Anna van der Berg van mc' under
    # FAMILY_FIRST, a reread no longer); 296 -> 299 the same day, the
    # PR review's MARIA DA SILVA E SOUZA row under each order, a
    # connective whose stand-in is an initial too, so its field is
    # pinned in _EXPECTED_ALTERNATIVES instead; 299 -> 302 the same day,
    # master's 'Nasreen Sultana, MBBS' row (#903) under each order, a
    # comma credential run's report, whose stand-in the run reads too;
    # 436 -> 437 on 2026-10-27, #892's ', Jane van Jr.' row under
    # FAMILY_FIRST, a particle-or-given report P6's attachment decides;
    # 437 -> 443 the same day, #843's two abbreviated-agnomen rows read
    # as the suffix, each under the three orders
    assert (checked, skipped) == (443, 302), (checked, skipped)


def test_every_case_name_is_unique() -> None:
    """A repeated Case name silently shadows one row: pytest parametrizes
    the ids with a numeric suffix and the table reads as if both rows
    ran under one name. The review of PR #794 found
    comma_capital_si_is_a_suffix twice (the John Smith, SI row and the
    Wang, SI row, which carries a different reading), so this test is
    the check that would have caught it. Recorded negative control
    (2026-10-21): with the Wang, SI row renamed back to the duplicate,
    this test fails naming comma_capital_si_is_a_suffix."""
    names = [case.id for case in CASES]
    repeated = sorted({name for name in names if names.count(name) > 1})
    assert not repeated, f"Case names repeated in tests/v2/cases.py: {repeated}"


#: Case.__post_init__'s shape checks, each probed for the message that
#: identifies it. A row here is a Case that must fail to construct, not
#: one that ever joins CASES -- unlike test_case above, this exercises
#: the dataclass's own validation rather than the parser. One message
#: is shared by three rows and deliberately: the residue arm of the
#: purity check (2026-09-05) refuses every non-space ASCII character
#: the comma and Latin-letter arms do not, so its probes differ in the
#: character that trips it rather than in what they are told.
@pytest.mark.parametrize("kwargs, match", [
    pytest.param(
        dict(text="Beethoven, Ludwig van", shape=2, locale="nl_NL"),
        "needs the row's own policy",
        id="shape-plus-locale-has-no-order-to-check"),
    pytest.param(
        dict(text="田中さん, Jr. Ph. D.", shape=1),
        "cannot tag CJK text",
        id="cjk-text-is-corpus-cjk-jsonl-ground-not-a-shape"),
    pytest.param(
        dict(text="John Smith", shape=4),
        "declares no policy",
        id="family-first-shape-needs-a-family-first-policy"),
    pytest.param(
        dict(text="John Smith", shape=4,
             policy=Policy(name_order=FAMILY_FIRST_GIVEN_LAST)),
        "the row's policy declares FAMILY_FIRST_GIVEN_LAST",
        id="shape-order-disagrees-with-the-rows-own-policy"),
    pytest.param(
        dict(text="John Smith", shape=8),
        "unknown shape",
        id="shape-id-outside-the-inventory"),
    pytest.param(
        dict(text="田中太郎", shape=4,
             policy=Policy(name_order=FAMILY_FIRST)),
        "cannot tag CJK text",
        id="cjk-refusal-survives-a-matching-order"),
    pytest.param(
        dict(text="김민준, 지훈", shape=6),
        "refuses a comma",
        id="shape-6-refuses-a-comma"),
    pytest.param(
        dict(text="김민준 V", shape=6),
        "refuses a Latin letter",
        id="shape-6-refuses-a-latin-letter"),
    pytest.param(
        # The 2026-09-05 widening, and the text that motivated it: the
        # comma and Latin-letter arms above both said no of every
        # composed form anyone had written down, and this one carries
        # neither. It is a tolerated row today
        # (ja_honorific_with_a_period_no_comma); the tag it must not be
        # able to take back is what this probe holds.
        dict(text="田中さん 様.", shape=6),
        "refuses the ASCII",
        id="shape-6-refuses-a-trailing-period"),
    pytest.param(
        dict(text="김민준 2", shape=6),
        "refuses the ASCII",
        id="shape-6-refuses-a-digit"),
    pytest.param(
        # Refused for its parentheses, BEFORE the transcription test
        # this text would also fail -- the residue arm runs first, so
        # the message names the ASCII rather than the divider. The
        # nickname row this text belongs to (fix(#272)) stays contract
        # and untagged: the purity gate is a property of a SHAPE tag,
        # not of the corpus.
        dict(text="山田 太郎 (マイケル・ジャクソン)", shape=7),
        "refuses the ASCII",
        id="shape-7-refuses-ascii-parentheses"),
    pytest.param(
        dict(text="김민준·지훈", shape=6),
        "belongs to shape 7",
        id="shape-6-refuses-the-interpunct"),
    pytest.param(
        dict(text="マイケル・ジャクソン", shape=6),
        "belongs to shape 7",
        id="shape-6-refuses-the-nakaguro"),
    pytest.param(
        dict(text="マイケルジャクソン", shape=6),
        "belongs to shape 7",
        id="shape-6-refuses-wholly-katakana-text"),
    pytest.param(
        dict(text="John Smith", shape=6),
        "requires a classified codepoint",
        id="shape-6-requires-cjk-text"),
    pytest.param(
        dict(text="김민준", shape=7),
        r"requires U\+00B7 or wholly-katakana",
        id="shape-7-requires-a-divider-or-katakana"),
    pytest.param(
        dict(text="김민준, 지훈", shape=7),
        "refuses a comma",
        id="shape-7-refuses-a-comma-too"),
    pytest.param(
        dict(text="高橋・一郎", shape=7),
        r"requires U\+00B7 or wholly-katakana",
        id="shape-7-refuses-a-nakaguro-on-non-katakana-text"),
    pytest.param(
        dict(text="김민준", shape=6, locale="zh"),
        "carry neither policy nor locale",
        id="shape-6-refuses-a-locale"),
    pytest.param(
        # The other arm of the same `or`. The locale row above passes
        # with `self.policy is not None` deleted, so without this one
        # a shape-6 row could carry a policy fork -- the refusal's own
        # comment says a stray policy on shapes 6/7 would silently do
        # nothing, which is exactly why it must not be admitted.
        dict(text="김민준", shape=6, policy=Policy(middle_as_family=True)),
        "carry neither policy nor locale",
        id="shape-6-refuses-a-policy"),
    pytest.param(
        dict(text="김민준", shape=6, tolerated=True),
        "mutually exclusive with shape",
        id="tolerated-and-shape-are-mutually-exclusive"),
    pytest.param(
        dict(text="John Smith", tolerated=True),
        "tolerated requires CJK text",
        id="tolerated-requires-cjk-text"),
])
def test_case_construction_rejects_a_bad_shape_tag(
        kwargs: dict[str, Any], match: str) -> None:
    with pytest.raises(ValueError, match=match):
        Case(id="probe", expect={}, **kwargs)


#: The constructions the battery above proves nothing rejects: a pure
#: shape-6 row, a Han shape-6 row divided by a nakaguro that does NOT
#: mark it as source order (U+30FB is not a divider outside katakana
#: -- decisions/T3; this is family-first per
#: ja_nakaguro_han_takes_the_han_order), an interpunct-divided shape-7
#: row, a SPACED wholly-katakana shape-7 row (the subtler admission --
#: a transcription with no U+00B7 at all is still a shape, not a
#: demotion, as long as every non-space character is katakana), a
#: SPACED HONORIFIC written without the period the residue arm refuses
#: (the boundary the 2026-09-05 widening had to leave standing: what
#: the demoted text loses is its period, not its arrangement), and a
#: tolerated row built from the SAME text a shape probe above refuses
#: as a comma -- the boundary reading the pair as intended: what a
#: shape tag refuses, tolerated=True admits. Each must construct
#: cleanly -- the purity rule is a REFUSAL rule, not a requirement
#: that admits nothing.
@pytest.mark.parametrize("kwargs", [
    pytest.param(dict(text="김민준", shape=6), id="pure-shape-6-constructs"),
    pytest.param(dict(text="田中さん 様", shape=6),
                 id="spaced-honorific-without-a-period-constructs"),
    pytest.param(dict(text="高橋・一郎", shape=6),
                 id="han-nakaguro-shape-6-constructs"),
    pytest.param(dict(text="威廉·莎士比亚", shape=7),
                 id="interpunct-shape-7-constructs"),
    pytest.param(dict(text="マイケル ジャクソン", shape=7),
                 id="spaced-wholly-katakana-shape-7-constructs"),
    pytest.param(dict(text="김민준, 지훈", tolerated=True),
                 id="tolerated-accepts-the-comma-text-a-shape-tag-refuses"),
])
def test_case_construction_accepts_a_valid_shape_or_tolerated_tag(
        kwargs: dict[str, Any]) -> None:
    case = Case(id="probe", expect={}, **kwargs)
    if "shape" in kwargs:
        assert case.shape == kwargs["shape"]
    else:
        assert case.tolerated is True
