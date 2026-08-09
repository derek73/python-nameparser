import pytest

from nameparser._lexicon import Lexicon
from nameparser._pipeline import run
from nameparser._pipeline._state import ParseState
from nameparser._policy import FAMILY_FIRST, PatronymicRule, Policy
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


# --- rule 1b under name_order=FAMILY_FIRST (#359) ---------------------
# The fold keys on POSITION, not on the GIVEN role: a never-given
# particle keeps its particle whatever name_order says.

@pytest.mark.parametrize("text,family,given,suffix", [
    # the leading particle chains the rest of the name into the family
    ("de Mesnil", "de Mesnil", "", ""),
    ("de la Vega", "de la Vega", "", ""),
    # ... and the trailing suffix run is peeled before the rule looks,
    # comma or no comma (NO_COMMA and SUFFIX_COMMA both fold)
    ("de Mesnil MD", "de Mesnil", "", "MD"),
    ("De Mesnil, MD", "De Mesnil", "", "MD"),
])
def test_family_first_folds_leading_never_given_particle(
        text: str, family: str, given: str, suffix: str) -> None:
    out = _parsed(text, _FF)
    assert _by_role(out, Role.FAMILY) == family
    assert _by_role(out, Role.GIVEN) == given
    assert _by_role(out, Role.SUFFIX) == suffix


@pytest.mark.parametrize("text,family,given", [
    # a title makes the particle non-leading, so group already chained
    # it into one piece -- one name piece, wholly family under FF
    ("Mr. de Mesnil", "de Mesnil", ""),
    # a family comma has already fixed the family; the post-comma part
    # is the given name and must not be folded into it
    ("de Mesnil, Juan", "de Mesnil", "Juan"),
    # degenerate: nothing to fold, so no surname is invented
    ("de", "de", ""),
    # the leading piece is not a particle
    ("Juan de Mesnil", "Juan", "de Mesnil"),
    # 'van' is particles_ambiguous -- out of the rule's scope in EVERY
    # order, so FAMILY_FIRST still splits at the particle (#360)
    ("van Gogh", "van", "Gogh"),
])
def test_family_first_leading_particle_cases_that_do_not_fold(
        text: str, family: str, given: str) -> None:
    out = _parsed(text, _FF)
    assert _by_role(out, Role.FAMILY) == family
    assert _by_role(out, Role.GIVEN) == given


@pytest.mark.parametrize("text,title,given,middle,family,suffix", [
    ("de Mesnil", "", "", "", "de Mesnil", ""),
    ("de la Vega", "", "", "", "de la Vega", ""),
    ("de Mesnil MD", "", "", "", "de Mesnil", "MD"),
    ("De Mesnil, MD", "", "", "", "De Mesnil", "MD"),
    ("Mr. de Mesnil", "Mr.", "", "", "de Mesnil", ""),
    ("de Mesnil, Juan", "", "Juan", "", "de Mesnil", ""),
    ("de", "", "de", "", "", ""),
    ("Juan de Mesnil", "", "Juan", "", "de Mesnil", ""),
    ("van Gogh", "", "van", "", "Gogh", ""),
    # a family comma folds the post-comma part when IT opens with a
    # never-given particle -- long-standing behaviour, order-independent
    # (assign ignores name_order after a family comma), pinned here so
    # the re-key cannot quietly drop it
    ("Smith, de Mesnil", "", "", "", "Smith de Mesnil", ""),
    ("Smith, van Gogh", "", "van", "Gogh", "Smith", ""),
])
def test_default_order_is_unchanged_by_the_family_first_fold(
        text: str, title: str, given: str, middle: str, family: str,
        suffix: str) -> None:
    out = _parsed(text)
    assert _by_role(out, Role.TITLE) == title
    assert _by_role(out, Role.GIVEN) == given
    assert _by_role(out, Role.MIDDLE) == middle
    assert _by_role(out, Role.FAMILY) == family
    assert _by_role(out, Role.SUFFIX) == suffix


def test_family_comma_fold_is_order_independent() -> None:
    out = _parsed("Smith, de Mesnil", _FF)
    assert _by_role(out, Role.FAMILY) == "Smith de Mesnil"
    assert not _by_role(out, Role.GIVEN)


def test_lone_never_given_particle_in_given_position_folds() -> None:
    # The invariant is "never REPORTED as the given name", which the
    # opening-position test alone does not carry: under FAMILY_FIRST
    # the given position is the TRAILING piece, and a bare 'de' landing
    # there has to fold into the family beside it or the parse
    # contradicts the very set that says 'de' is never a given name.
    # Guarded here because a refactor that reads the rule as
    # leading-particle-only drops exactly this shape, silently and
    # under a non-default order (#359 review).
    out = _parsed("Mesnil de", _FF)
    assert _by_role(out, Role.FAMILY) == "Mesnil de"
    assert not _by_role(out, Role.GIVEN)
    # the default order reaches the invariant from the other side: the
    # particle is already the family, so there is nothing to repair
    default = _parsed("Mesnil de")
    assert _by_role(default, Role.GIVEN) == "Mesnil"
    assert _by_role(default, Role.FAMILY) == "de"


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
