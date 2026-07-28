from nameparser._lexicon import Lexicon
from nameparser._pipeline import run
from nameparser._pipeline._state import ParseState
from nameparser._policy import PatronymicRule, Policy
from nameparser._types import Role

_LEX = Lexicon(
    titles=frozenset({"mr", "sir"}),
    given_name_titles=frozenset({"sir"}),
    particles=frozenset({"de", "la", "van"}),
    particles_ambiguous=frozenset({"van"}),
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
