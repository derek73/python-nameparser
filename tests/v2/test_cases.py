"""Core runner over the shared case table. The facade
runner (migration plan) consumes the same CASES."""
from typing import Any

import pytest

from nameparser import Parser, Policy, Role, locales, parser_for
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


@pytest.mark.parametrize("order", _INVARIANT_ORDERS,
                         ids=lambda o: _ORDER_NAMES.get(o, "as-declared"))
@pytest.mark.parametrize("case", CASES, ids=lambda c: c.id)
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
    if case.locale is not None or (order is not None and case.policy):
        pytest.skip("row carries its own policy or locale")
    parser = (_parser_for_case(case) if order is None
              else Parser(policy=Policy(name_order=order)))
    pn = parser.parse(case.text)
    if not pn.family:
        return
    assert pn.family_base, (
        f"{case.text!r}: family={pn.family!r} but family_base is "
        f"empty (particles={pn.family_particles!r})")
    assert sorted(pn.family.split()) == sorted(
        (pn.family_particles + " " + pn.family_base).split()), (
        f"{case.text!r}: family={pn.family!r} is not partitioned by "
        f"particles={pn.family_particles!r} + base={pn.family_base!r}")


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
