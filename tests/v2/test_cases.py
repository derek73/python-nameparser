"""Core runner over the shared case table. The facade
runner (migration plan) consumes the same CASES."""
import functools
import re
from collections.abc import Iterator
from typing import Any

import pytest

from nameparser import ParsedName, Parser, Policy, Role, locales, parser_for
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
    """rules.md#R2's invariant: a particle needs a base to attach to,
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
#: segment's report on a part past the second comma names EVERY field
#: the part's words land in, as role names ("consumed as title and
#: suffix best-effort", #629), so it is checked for equality rather
#: than inclusion: a named field nothing landed in is as wrong as a
#: field left out.
_FIELDS_CLAIM = re.compile(r"\bconsumed as ([a-z]+(?: and [a-z]+)*) best-effort")


def _claims(detail: str) -> Iterator[tuple[str, frozenset[Role], bool]]:
    """The field claims in a report's detail: the phrase, the fields
    that make it true, and whether they must ALL be held."""
    if m := _FIELD_CLAIM.search(detail):
        yield m[0], _FIELD_CLAIMS[m[1]], False
    if m := _FIELDS_CLAIM.search(detail):
        yield m[0], frozenset(map(Role, m[1].split(" and "))), True


@pytest.mark.parametrize("case,order", _SWEPT_ROWS, ids=_SWEPT_IDS)
def test_a_report_names_the_field_its_word_lands_in(
        case: Case, order: tuple[Role, Role, Role] | None) -> None:
    """#626: a report's detail that names the field its word was read
    into names the field the word holds in the RESULT. Rules in
    post_rules move a word after assign reports it -- H1's move behind
    a title, P1's family-first fold, P6's attachment, and under opt-in
    policies the patronymic rotations and `middle_as_family`'s fold,
    which rows carrying those policies reach as declared -- and six of
    assign's reports were worded from the role at assign, so
    'Kim Min Do' under FAMILY_FIRST was told 'Do' was a middle name
    when it landed in the family. Assemble words them now.

    Checked over `_SWEPT_ROWS`, which the count test below walks too.

    Negative control, measured 2026-10-08: this test over master's
    parser (26cdb891) fails 14 parses, every one a report worded at
    assign -- nine title-or-name join reports saying 'given' of a unit
    H1 moved to the family behind a title (`Attorney General of
    Minnesota`, `John of Prince Prof.`, `St St née`, `Freiherr von
    Bishop X.Y.Z.` and five more rows, as declared), `Kim Min Do`
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

    Segment's report on a part past the second comma is read by
    `_FIELDS_CLAIM` and checked for equality (#629). Its control,
    measured 2026-10-10 over master's parser (bc243869) with this
    test: 6 failures, the two rows holding a title past the second
    comma (`John Smith, Jr., Freiherr von Richthofen` and `John
    Smith, Jr., and Secretary of State`) under all three orders,
    each told 'consumed as suffix'.
    """
    pn = _swept(case.id, order)
    for a in pn.ambiguities:
        landed = {t.role for t in a.tokens}
        for phrase, fields, every in _claims(a.detail):
            assert landed == fields if every else landed <= fields, (
                f"{case.text!r}: {a.kind.value} says {phrase!r} but its "
                f"tokens landed in {sorted(r.value for r in landed)}: "
                f"{a.detail!r}")


def test_the_field_sweep_sees_the_claims_it_checks() -> None:
    """The sweep above passes vacuously if no detail matches
    `_FIELD_CLAIM` -- an emitter reworded out of the list, or rows
    dropped -- so the count of claims it checks is recorded here.
    Move it deliberately when a row or a phrasing moves, never to 0."""
    claims = sum(
        1 for case, order in _SWEPT_ROWS
        for a in _swept(case.id, order).ambiguities
        for _ in _claims(a.detail))
    assert claims == 1180, (
        f"the field sweep checks {claims} claims, recorded as 1180 on "
        f"2026-10-10")


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
#: -- decisions.md#T3; this is family-first per
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
