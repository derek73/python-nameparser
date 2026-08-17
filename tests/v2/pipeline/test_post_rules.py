import pytest

from nameparser._lexicon import Lexicon
from nameparser._pipeline import run
from nameparser._pipeline._state import ParseState
from nameparser._policy import (FAMILY_FIRST, FAMILY_FIRST_GIVEN_LAST,
                                PatronymicRule, Policy)
from nameparser._types import Role

_LEX = Lexicon(
    titles=frozenset({"mr", "sir"}),
    given_name_titles=frozenset({"sir"}),
    particles=frozenset({"de", "la", "van"}),
    particles_ambiguous=frozenset({"van"}),
    suffix_words=frozenset({"md"}),
)


def _parsed(text: str, policy: Policy | None = None) -> ParseState:
    return run(ParseState(original=text, lexicon=_LEX,
                          policy=policy or Policy()))


def _by_role(state: ParseState, role: Role) -> str:
    return " ".join(t.text for t in state.tokens if t.role is role)


def test_plain_title_with_single_name_swaps_to_family() -> None:
    out = _parsed("Mr. Johnson")
    assert _by_role(out, Role.FAMILY) == "Johnson"
    assert not _by_role(out, Role.GIVEN)


def test_given_name_title_keeps_given() -> None:
    out = _parsed("Sir Bob")
    assert _by_role(out, Role.GIVEN) == "Bob"
    assert not _by_role(out, Role.FAMILY)


def test_no_swap_when_more_fields_present() -> None:
    out = _parsed("Mr. John Johnson")
    assert _by_role(out, Role.GIVEN) == "John"
    assert _by_role(out, Role.FAMILY) == "Johnson"


_ES = Policy(patronymic_rules=frozenset({PatronymicRule.EAST_SLAVIC}))
_TK = Policy(patronymic_rules=frozenset({PatronymicRule.TURKIC}))


def test_east_slavic_rotation() -> None:
    out = _parsed("Сидоров Иван Петрович", _ES)
    assert _by_role(out, Role.GIVEN) == "Иван"
    assert _by_role(out, Role.MIDDLE) == "Петрович"
    assert _by_role(out, Role.FAMILY) == "Сидоров"


def test_east_slavic_needs_one_one_one() -> None:
    # four tokens: left unchanged (v1 parity)
    out = _parsed("Anna Maria Petrova Ivanovna", _ES)
    assert _by_role(out, Role.GIVEN) == "Anna"


def test_east_slavic_skips_comma_forms() -> None:
    # v1 parity: patronymic reorder never fires on comma input --
    # the comma already established the family
    out = _parsed("Abramovich, Roman Petrovich", _ES)
    assert _by_role(out, Role.FAMILY) == "Abramovich"
    assert _by_role(out, Role.GIVEN) == "Roman"


def test_east_slavic_skips_when_middle_is_also_patronymic() -> None:
    # v1 parity: given + patronymic + patronymic-derived surname
    # (Abramovich) must not rotate
    out = _parsed("Roman Petrovich Abramovich", _ES)
    assert _by_role(out, Role.GIVEN) == "Roman"
    assert _by_role(out, Role.MIDDLE) == "Petrovich"
    assert _by_role(out, Role.FAMILY) == "Abramovich"


def test_east_slavic_off_by_default() -> None:
    out = _parsed("Сидоров Иван Петрович")
    assert _by_role(out, Role.GIVEN) == "Сидоров"


def test_turkic_rotation() -> None:
    out = _parsed("Mammadova Aygun Ali kizi", _TK)
    assert _by_role(out, Role.GIVEN) == "Aygun"
    assert _by_role(out, Role.MIDDLE) == "Ali kizi"
    assert _by_role(out, Role.FAMILY) == "Mammadova"


def test_leading_never_given_particle_folds_into_family() -> None:
    # v1 handle_non_first_name_prefix: a leading particle that is never
    # a given name ('de') means the whole name is a surname
    out = _parsed("de la Vega")
    assert _by_role(out, Role.FAMILY) == "de la Vega"
    assert not _by_role(out, Role.GIVEN)


def test_leading_ambiguous_particle_stays_given() -> None:
    # 'van' is particles_ambiguous: the given reading stands (v1 parity)
    out = _parsed("van Gogh")
    assert _by_role(out, Role.GIVEN) == "van"
    assert _by_role(out, Role.FAMILY) == "Gogh"


def test_degenerate_bare_particle_stays_given() -> None:
    # v1's guard: with no middle or family, a bare 'de' keeps given='de'
    # rather than inventing a surname
    out = _parsed("de")
    assert _by_role(out, Role.GIVEN) == "de"
    assert not _by_role(out, Role.FAMILY)


_FF = Policy(name_order=FAMILY_FIRST)
_FFGL = Policy(name_order=FAMILY_FIRST_GIVEN_LAST)

#: Both family-first orders, since the rule is claimed of every one of
#: them and only one was ever parsed. They differ in where the given
#: name lands behind the family, which is exactly what the leading
#: shape must not depend on; the cases below fold identically under
#: both.
_FAMILY_FIRST = [pytest.param(_FF, id="FAMILY_FIRST"),
                 pytest.param(_FFGL, id="FAMILY_FIRST_GIVEN_LAST")]


# --- rule 1b under the family-first orders (#359) ---------------------
# The fold keys on POSITION, not on the GIVEN role: a never-given
# particle keeps its particle whatever name_order says.

@pytest.mark.parametrize("policy", _FAMILY_FIRST)
@pytest.mark.parametrize("text,family,given,suffix", [
    # the leading particle chains the rest of the name into the family
    ("de Mesnil", "de Mesnil", "", ""),
    ("de la Vega", "de la Vega", "", ""),
    # three pieces, so a name word survives the claim -- the only
    # no-comma corpus name that reaches it, and the one #390 moved
    ("de Mesnil Garcia", "de Mesnil", "Garcia", ""),
    # ... and the trailing suffix run is peeled before the rule looks,
    # comma or no comma (NO_COMMA and SUFFIX_COMMA both fold)
    ("de Mesnil MD", "de Mesnil", "", "MD"),
    ("De Mesnil, MD", "De Mesnil", "", "MD"),
])
def test_family_first_folds_leading_never_given_particle(
        policy: Policy, text: str, family: str, given: str,
        suffix: str) -> None:
    out = _parsed(text, policy)
    assert _by_role(out, Role.FAMILY) == family
    assert _by_role(out, Role.GIVEN) == given
    assert _by_role(out, Role.SUFFIX) == suffix


@pytest.mark.parametrize("policy", _FAMILY_FIRST)
def test_titles_are_peeled_before_the_leading_particle_claim(
        policy: Policy) -> None:
    # The claim reads the first NAME piece, not pieces[0]: a title in
    # front must not hide the particle behind it. assign gets this by
    # peeling titles before it counts name pieces (#390 moved the claim
    # there from post_rules, retiring the _leading_name_piece scan that
    # used to walk past non-name pieces). Without the peel the title is
    # piece 0, no claim fires, and the name splits by position.
    out = _parsed("Dr. de Mesnil", policy)
    assert _by_role(out, Role.TITLE) == "Dr."
    assert _by_role(out, Role.FAMILY) == "de Mesnil"
    assert not _by_role(out, Role.GIVEN)
    assert not _by_role(out, Role.MIDDLE)


@pytest.mark.parametrize("policy", _FAMILY_FIRST)
@pytest.mark.parametrize("text,family,given", [
    # a title makes the particle non-leading, so group already chained
    # it into one piece -- one name piece, wholly family under both
    # family-first orders
    ("Mr. de Mesnil", "de Mesnil", ""),
    # a family comma has already fixed the family; the post-comma part
    # is the given name and must not be folded into it
    ("de Mesnil, Juan", "de Mesnil", "Juan"),
    # degenerate: nothing to fold, so no surname is invented
    ("de", "de", ""),
    # the leading piece is not a particle
    ("Juan de Mesnil", "Juan", "de Mesnil"),
    # 'van' is particles_ambiguous -- out of the rule's scope in EVERY
    # order, so a family-first order still splits at the particle (#360)
    ("van Gogh", "van", "Gogh"),
])
def test_family_first_leading_particle_cases_that_do_not_fold(
        policy: Policy, text: str, family: str, given: str) -> None:
    out = _parsed(text, policy)
    assert _by_role(out, Role.FAMILY) == family
    assert _by_role(out, Role.GIVEN) == given


@pytest.mark.parametrize("text,title,given,middle,family,suffix", [
    ("de Mesnil", "", "", "", "de Mesnil", ""),
    ("de la Vega", "", "", "", "de la Vega", ""),
    ("de Mesnil Garcia", "", "Garcia", "", "de Mesnil", ""),
    # garbage in, garbage out: MD is suffix vocabulary sitting
    # mid-name, so the piece the particle attaches to is "MD".
    # Both readings of this input are garbage; pinned only so the
    # claim's reach is visible, never as a shape to design around
    ("Dr. de MD Mesnil", "Dr.", "Mesnil", "", "de MD", ""),
    ("de Mesnil MD", "", "", "", "de Mesnil", "MD"),
    ("De Mesnil, MD", "", "", "", "De Mesnil", "MD"),
    ("Mr. de Mesnil", "Mr.", "", "", "de Mesnil", ""),
    ("de Mesnil, Juan", "", "Juan", "", "de Mesnil", ""),
    ("de", "", "de", "", "", ""),
    ("Juan de Mesnil", "", "Juan", "", "de Mesnil", ""),
    ("van Gogh", "", "van", "", "Gogh", ""),
    # a family comma folds the post-comma part when IT opens with a
    # never-given particle -- long-standing behaviour, and rule 1b's
    # own doing: assign hands it the same roles in every order (the
    # comma already fixed the family), and both of 1b's sites then
    # agree, the opening piece of segment 1 and the lone given being
    # the same token. Pinned here so the re-key cannot quietly drop it
    ("Smith, de Mesnil", "", "", "", "Smith de Mesnil", ""),
    ("Smith, van Gogh", "", "van", "Gogh", "Smith", ""),
])
def test_leading_particle_claim_reads_alike_in_the_default_order(
        text: str, title: str, given: str, middle: str, family: str,
        suffix: str) -> None:
    out = _parsed(text)
    assert _by_role(out, Role.TITLE) == title
    assert _by_role(out, Role.GIVEN) == given
    assert _by_role(out, Role.MIDDLE) == middle
    assert _by_role(out, Role.FAMILY) == family
    assert _by_role(out, Role.SUFFIX) == suffix


@pytest.mark.parametrize("policy", _FAMILY_FIRST)
def test_family_comma_fold_is_order_independent(policy: Policy) -> None:
    out = _parsed("Smith, de Mesnil", policy)
    assert _by_role(out, Role.FAMILY) == "Smith de Mesnil"
    assert not _by_role(out, Role.GIVEN)


@pytest.mark.parametrize("policy", _FAMILY_FIRST)
def test_lone_never_given_particle_in_given_position_folds(
        policy: Policy) -> None:
    # The opening-position test alone does not carry the rule: under a
    # family-first order the given position is the TRAILING piece, and
    # a lone 'de' landing there has to fold into the family beside it
    # or the parse leaves the whole given name as a word the vocabulary
    # says is never a given name. Guarded here because a refactor that
    # reads the rule as leading-particle-only drops exactly this shape,
    # silently and under a non-default order (#359 review).
    out = _parsed("Mesnil de", policy)
    assert _by_role(out, Role.FAMILY) == "Mesnil de"
    assert not _by_role(out, Role.GIVEN)


def test_lone_never_given_particle_needs_no_repair_by_default() -> None:
    # the default order reaches the same rule from the other side: the
    # particle is already the family, so there is nothing to repair
    default = _parsed("Mesnil de")
    assert _by_role(default, Role.GIVEN) == "Mesnil"
    assert _by_role(default, Role.FAMILY) == "de"


# --- the whole never-given class, not just the fixture's 'de' ---------

_ALL_ORDERS = [pytest.param(Policy(), id="GIVEN_FIRST"), *_FAMILY_FIRST]


@pytest.mark.parametrize("policy", _ALL_ORDERS)
def test_no_never_given_particle_is_left_as_the_given_name(
        policy: Policy) -> None:
    """Every case above rides on the fixture lexicon's 'de'. The rule
    is claimed of the whole never-given class in every name_order, so
    sweep the live class rather than pinning another word or two of it
    -- a hardcoded handful would document those entries and catch
    nothing else in the set (AGENTS.md, "Prefer behavior tests over
    constant-content tests"). Derived from the lexicon, so an addition
    to NON_GIVEN_NAME_PARTICLES is swept the day it lands, and asserts
    nothing about which words are in the set.
    """
    lex = Lexicon.default()
    never_given = sorted(lex.particles - lex.particles_ambiguous)
    assert never_given, "no never-given particles to exercise"
    failures = []
    for particle in never_given:
        text = f"{particle} Mesnil"
        out = run(ParseState(original=text, lexicon=lex, policy=policy))
        given = _by_role(out, Role.GIVEN)
        family = _by_role(out, Role.FAMILY)
        if given or family != text:
            failures.append(
                f"{text!r}: given={given!r} family={family!r}")
    assert not failures, (
        f"{len(failures)} of {len(never_given)} left as a given name "
        f"or unfolded:\n" + "\n".join(failures[:15]))


def test_middle_as_family_folds_middles() -> None:
    # v1 handle_middle_name_as_last, opt-in: middles prepend to family
    out = _parsed("John Quincy Adams Smith",
                  Policy(middle_as_family=True))
    assert _by_role(out, Role.GIVEN) == "John"
    assert not _by_role(out, Role.MIDDLE)
    assert _by_role(out, Role.FAMILY) == "Quincy Adams Smith"


def test_middle_as_family_off_by_default() -> None:
    out = _parsed("John Quincy Adams Smith")
    assert _by_role(out, Role.MIDDLE) == "Quincy Adams"
