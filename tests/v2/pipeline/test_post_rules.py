import dataclasses
import sys

import pytest

from nameparser._lexicon import Lexicon
from nameparser._pipeline import run
from nameparser._pipeline._state import ParseState
from nameparser._policy import (FAMILY_FIRST, FAMILY_FIRST_GIVEN_LAST,
                                GIVEN_FIRST, PatronymicRule, Policy,
                                Script)
from nameparser._types import STABLE_TAGS, Role

# A reduced lexicon, the convention in every pipeline stage module: a
# stage test should not move when shipped vocabulary does. What it must
# NOT do is classify a word DIFFERENTLY from the shipped sets, which
# makes a test pass by parsing something other than the name it reads
# as -- `_assert_fixture_mirrors_shipped` below holds the line, and
# found three such words when it was written (#395): `dr` and `md` were
# absent while shipping as titles, and `la` sat in the never-given half
# while shipping as ambiguous.
_LEX = Lexicon(
    titles=frozenset({"mr", "sir", "dr", "md"}),
    given_name_titles=frozenset({"sir"}),
    particles=frozenset({"de", "der", "ibn", "la", "van"}),
    particles_ambiguous=frozenset({"la", "van"}),
    suffix_words=frozenset({"dr"}),
    suffix_acronyms=frozenset({"md"}),
    conjunctions=frozenset({"y"}),
    bound_given_names=frozenset({"abdul"}),
)


#: The non-namespaced tags a LEXICON can produce: STABLE_TAGS minus
#: the two that come from a token's SHAPE, which no lexicon controls.
#: Derived rather than listed so that a new stable tag cannot quietly
#: drop out of the comparison below -- STABLE_TAGS is itself pinned,
#: at tests/v2/test_types.py.
_VOCAB_TAGS = STABLE_TAGS - {"initial", "joined"}


def _fixture_mirrors_shipped(text: str, policy: Policy) -> str:
    """Empty unless `_LEX` classifies a word in `text` differently from
    the shipped sets. A reduced fixture is fine -- a MISCLASSIFYING one
    is not, because the test then reads one name and parses another,
    and passes for a reason its author never sees (#395; the three
    words it caught are named on `_LEX`)."""
    def vocab(lexicon: Lexicon) -> list[tuple[str, frozenset[str]]]:
        state = run(ParseState(original=text, lexicon=lexicon,
                               policy=policy))
        return [(t.text, frozenset(g for g in t.tags
                                   if g.startswith("vocab:")
                                   or g in _VOCAB_TAGS))
                for t in state.tokens]
    mine, shipped = vocab(_LEX), vocab(Lexicon.default())
    if len(mine) != len(shipped):
        return f"{text!r}: tokenizes differently under the shipped lexicon"
    return "; ".join(
        f"{word!r} is {sorted(ours) or 'plain'} here but "
        f"{theirs_word!r} {sorted(theirs) or 'plain'} in the shipped "
        f"sets" if word != theirs_word else
        f"{word!r} is {sorted(ours) or 'plain'} here but "
        f"{sorted(theirs) or 'plain'} in the shipped sets"
        for (word, ours), (theirs_word, theirs) in zip(mine, shipped)
        if (word, ours) != (theirs_word, theirs))


def _parsed(text: str, policy: Policy | None = None) -> ParseState:
    policy = policy or Policy()
    divergence = _fixture_mirrors_shipped(text, policy)
    assert not divergence, (
        f"{divergence}. Mirror the shipped classification in _LEX. A "
        f"test that needs the word classified some OTHER way builds "
        f"its own state with an explicit lexicon instead of calling "
        f"this helper, the way the vocabulary rows below do.")
    return run(ParseState(original=text, lexicon=_LEX, policy=policy))


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
    # three pieces: the run stops at 'Mesnil' and 'Garcia' is left to
    # the order (#395). The only no-comma corpus name that reaches
    # this rule, and the one #364 was closed on twice
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
def test_leading_piece_scan_skips_pieces_that_hold_no_name(
        policy: Policy) -> None:
    # `_leading_name_piece` walks PAST pieces carrying no name role
    # rather than reading piece 0. Without the skip the scan finds the
    # title and the name splits: family='de', given='MD'.
    #
    # An older version of this comment claimed the simpler
    # 'Mr de Mesnil' could not show the skip, its particle being
    # chained into one piece with 'Mesnil'. That was true before #367,
    # when a title displaced the particle out of the name's leading
    # position and the chain fired. It is not true now -- the pieces
    # are [Mr][de][Mesnil] and the simpler name fails the same way
    # under the same mutation. What this input adds is the narrowing
    # with a title present: the run stops after 'MD'. Not pinned here,
    # despite the scan supporting it: walking past MORE than one
    # non-name piece, which no fixture in this module produces.
    #
    # The title is deliberately UNDOTTED: a period makes any opening
    # abbreviation a title by shape (rules.md#H2), so a dotted one
    # would pass this test with the title vocabulary empty.
    out = _parsed("Mr de MD Mesnil", policy)
    assert _by_role(out, Role.TITLE) == "Mr"
    # 'MD' mid-name is a name word, so it is the ONE word the run
    # takes (#395); 'Mesnil' is left to the order. What the skip
    # decides is that the run is found at all -- without it the scan
    # stops on the title and the family is 'de' alone.
    assert _by_role(out, Role.FAMILY) == "de MD"
    assert _by_role(out, Role.GIVEN) == "Mesnil"
    assert not _by_role(out, Role.MIDDLE)


@pytest.mark.parametrize("policy", _FAMILY_FIRST)
@pytest.mark.parametrize("text,family,given", [
    # a title is transparent to the fold (#367 removed the title->
    # particle chain, so the pieces are [Mr.][de][Mesnil]), and with
    # one name word after the run there is nothing for the stop to
    # leave behind: wholly family under both family-first orders
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
    ("de Mesnil Garcia", "", "", "", "de Mesnil Garcia", ""),
    ("Mr de MD Mesnil", "Mr", "", "", "de MD Mesnil", ""),
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
def test_default_order_is_unchanged_by_the_family_first_fold(
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

@pytest.mark.parametrize("text,given,middle,family", [
    # #360's two measured misparses, now folded
    ("Mc Donald", "", "", "Mc Donald"),
    ("Ste Marie", "", "", "Ste Marie"),
    # the Spanish plural articles: 'de' leads, 'los' chains onto the
    # surname. Correct before #360 too, but by the whole-remainder sweep
    # rather than by knowing 'los' -- and the #390 fold narrowing
    # regressed it precisely because the vocabulary did not
    ("de los Santos", "", "", "de los Santos"),
    ("de las Casas", "", "", "de las Casas"),
    # 'das' mid-name chains FORWARD, which is the gain: family was
    # 'Neves' before #360, losing the particle
    ("Maria das Neves", "Maria", "", "das Neves"),
    # NEGATIVE CONTROL, and the reason C-i needs its positional
    # qualifier: 'Das' is a borne Bengali surname in TRAILING position,
    # where the leading-particle rule never reaches. Never-given 'das'
    # must leave these alone -- if this row moves, the qualifier is
    # wrong and the membership has to come back out.
    ("Anjali Das", "Anjali", "", "Das"),
    ("Bimal Das", "Bimal", "", "Das"),
])
def test_article_particles_fold_without_eating_trailing_surnames(
        text: str, given: str, middle: str, family: str) -> None:
    # The DEFAULT lexicon deliberately, not this module's reduced _LEX:
    # these rows are about which words the shipped vocabulary claims, so
    # a fixture that omits them would pass while proving nothing.
    out = run(ParseState(original=text, lexicon=Lexicon.default(),
                         policy=Policy()))
    assert _by_role(out, Role.GIVEN) == given
    assert _by_role(out, Role.MIDDLE) == middle
    assert _by_role(out, Role.FAMILY) == family


# --- #395: how far the run reaches under a family-first order -------

@pytest.mark.parametrize("policy", _FAMILY_FIRST)
@pytest.mark.parametrize("text,family,given,middle,suffix", [
    # one leftover -- where the two family-first orders still agree
    ("de la Cruz Juan", "de la Cruz", "Juan", "", ""),
    # a trailing suffix is peeled before the rule looks, so it is not
    # a leftover and cannot change where the run stops
    ("de la Cruz Juan MD", "de la Cruz", "Juan", "", "MD"),
    # ... nor can a leading title, which is not a name word either
    ("Mr de la Cruz Juan", "de la Cruz", "Juan", "", ""),
])
def test_family_first_run_stops_at_the_first_name_word(
        policy: Policy, text: str, family: str, given: str,
        middle: str, suffix: str) -> None:
    out = _parsed(text, policy)
    assert _by_role(out, Role.FAMILY) == family
    assert _by_role(out, Role.GIVEN) == given
    assert _by_role(out, Role.MIDDLE) == middle
    assert _by_role(out, Role.SUFFIX) == suffix


@pytest.mark.parametrize("policy", _FAMILY_FIRST)
@pytest.mark.parametrize("text,family,rest", [
    # the conjunction join is ONE name word (rules.md#P3), so the run
    # takes 'Vega y Santos' whole rather than stopping inside it
    ("de la Vega y Santos Juan", "de la Vega y Santos", "Juan"),
    # ... and the same clause applies to what is LEFT: 'Juan y Eva' is
    # one unit, so it lands in one field rather than being split
    ("de la Cruz Juan y Eva", "de la Cruz", "Juan y Eva"),
    # a bound given-name word and the word it completes are one unit
    # (rules.md#P5), so the fold cannot leave half of the pair behind
    ("ibn Awf abdul Rahman", "ibn Awf", "abdul Rahman"),
    # a particle in what is LEFT chains forward the same way it would
    # if the fold had never run (rules.md#P2). Handing its words out
    # separately would report given='van' -- a bare particle as the
    # given name, which is the reading P1 exists to forbid -- and
    # would disagree with the same tail parsed alone: 'Mesnil van
    # Berg Juan' gives given='van Berg Juan'
    ("de Mesnil van Berg Juan", "de Mesnil", "van Berg Juan"),
    # ... including a never-given particle, where the split output
    # would have been given='de'
    ("de Mesnil de Berg Juan", "de Mesnil", "de Berg Juan"),
    # ... and a two-particle chain
    ("de Mesnil van der Berg", "de Mesnil", "van der Berg"),
])
def test_the_run_counts_units_not_words(
        policy: Policy, text: str, family: str, rest: str) -> None:
    # one leftover unit, so both family-first orders put it in `given`
    out = _parsed(text, policy)
    assert _by_role(out, Role.FAMILY) == family
    assert _by_role(out, Role.GIVEN) == rest
    assert not _by_role(out, Role.MIDDLE)


def test_the_two_family_first_orders_differ_at_two_leftovers() -> None:
    # The only shape that tells them apart, and the reason
    # tests/v2/cases.py carries it: with one leftover both orders send
    # it to `given`, so nothing else in the suite distinguishes the
    # name_order argument to the leftover placement.
    ff = _parsed("de la Cruz Juan Carlos", Policy(name_order=FAMILY_FIRST))
    fgl = _parsed("de la Cruz Juan Carlos",
                  Policy(name_order=FAMILY_FIRST_GIVEN_LAST))
    assert _by_role(ff, Role.GIVEN) == "Juan"
    assert _by_role(ff, Role.MIDDLE) == "Carlos"
    assert _by_role(fgl, Role.GIVEN) == "Carlos"
    assert _by_role(fgl, Role.MIDDLE) == "Juan"
    assert _by_role(ff, Role.FAMILY) == _by_role(fgl, Role.FAMILY)


@pytest.mark.parametrize("policy", _FAMILY_FIRST)
@pytest.mark.parametrize("text,family", [
    # an AMBIGUOUS leading particle is out of the rule's scope in every
    # order: the fold never fires on it, so there is no run to stop.
    # Untouched by #395
    ("van Gogh Jan", "van"),
    # a family comma has already fixed the surname, so there is no
    # positional read for a declared order to narrow (state.order is
    # None on this path)
    ("Smith, de Mesnil", "Smith de Mesnil"),
    # the particle stands in the GIVEN slot rather than opening the
    # name -- the second fold site, and not a leading run
    ("Juan de", "Juan de"),
])
def test_shapes_the_stop_does_not_reach(
        policy: Policy, text: str, family: str) -> None:
    # the family alone: the rows above place their remaining words by
    # order, which is not what these rows are about -- what they pin
    # is that the family is not narrowed
    out = _parsed(text, policy)
    assert _by_role(out, Role.FAMILY) == family


def test_the_fixture_guard_fires(
        monkeypatch: pytest.MonkeyPatch) -> None:
    # The guard is a correctness check on the fixture, so it needs one
    # on itself: without this, deleting its body leaves the suite green
    # -- the same inertness it exists to prevent.
    assert not _fixture_mirrors_shipped("de la Cruz Juan", Policy())
    monkeypatch.setattr(sys.modules[__name__], "_LEX",
                        dataclasses.replace(
                            _LEX, particles=frozenset(),
                            particles_ambiguous=frozenset()))
    assert "'de'" in _fixture_mirrors_shipped("de la Cruz Juan",
                                              Policy())


def test_the_stop_reads_the_effective_order_not_the_policy() -> None:
    # Why ParseState.order exists. A script_orders entry overrides
    # name_order, so the two disagree -- and this is the direction that
    # matters: the policy says family-first, the SCRIPT says given-
    # first, and the read assign actually made is the given-first one.
    # Keying the stop on policy.name_order would narrow a name that was
    # never read family-first. Needs a custom lexicon (every shipped
    # particle is Latin, and Latin has no script_orders entry), so it
    # builds the state directly rather than going through _parsed.
    lex = Lexicon(particles=frozenset({"ノ"}))
    policy = Policy(name_order=FAMILY_FIRST,
                    script_orders=((Script.KATAKANA, GIVEN_FIRST),))
    out = run(ParseState(original="ノ クルス フアン カルロス",
                         lexicon=lex, policy=policy))
    assert out.order == GIVEN_FIRST
    assert _by_role(out, Role.FAMILY) == "ノ クルス フアン カルロス"
    assert not _by_role(out, Role.GIVEN)


@pytest.mark.parametrize("policy", _FAMILY_FIRST)
def test_a_suffix_comma_still_stops_the_run(policy: Policy) -> None:
    # SUFFIX_COMMA takes a different assign branch from NO_COMMA
    # (tail = 1), while the fold still reads segment 0
    out = _parsed("de la Cruz Juan Carlos, MD", policy)
    assert _by_role(out, Role.FAMILY) == "de la Cruz"
    assert _by_role(out, Role.SUFFIX) == "MD"
    assert {_by_role(out, Role.GIVEN),
            _by_role(out, Role.MIDDLE)} == {"Juan", "Carlos"}


def test_a_maiden_name_is_not_swept_into_the_run() -> None:
    # `name_idx` is givens + middles + families, and MAIDEN is
    # deliberately not among them: a regression there moves the maiden
    # name silently into the family
    out = _parsed("de la Cruz Juan Carlos (Vega)",
                  Policy(name_order=FAMILY_FIRST,
                         maiden_delimiters=frozenset({("(", ")")})))
    assert _by_role(out, Role.FAMILY) == "de la Cruz"
    assert _by_role(out, Role.MAIDEN) == "Vega"
    assert _by_role(out, Role.GIVEN) == "Juan"


def test_middle_as_family_folds_a_middle_the_old_reach_never_left() -> None:
    # O3 now has a middle to fold, which the greedy reach never left
    # it. In TOKEN order the family is 'de la Cruz Carlos'; the field
    # renders it 'Carlos de la Cruz', the folded word prepended (R1),
    # which is why this asserts roles rather than the rendered field
    out = _parsed("de la Cruz Juan Carlos",
                  Policy(name_order=FAMILY_FIRST, middle_as_family=True))
    assert _by_role(out, Role.GIVEN) == "Juan"
    assert not _by_role(out, Role.MIDDLE)
    assert _by_role(out, Role.FAMILY) == "de la Cruz Carlos"


@pytest.mark.parametrize("policy,given,middle", [
    (Policy(name_order=FAMILY_FIRST), "van Berg", "MD Juan"),
    (Policy(name_order=FAMILY_FIRST_GIVEN_LAST), "Juan", "van Berg MD"),
])
def test_a_suffix_word_mid_run_ends_the_chain(
        policy: Policy, given: str, middle: str) -> None:
    # `_units` stops a particle chain at a suffix word, which is the
    # stop _group's own chain uses (`not prefix(j) and not suffix(j)`).
    # Without it the whole leftover is ONE unit and lands in one field.
    # Three leftover units here, so this is also the only place the two
    # orders are pinned apart at a count other than two.
    out = _parsed("de Mesnil van Berg MD Juan", policy)
    assert _by_role(out, Role.FAMILY) == "de Mesnil"
    assert _by_role(out, Role.GIVEN) == given
    assert _by_role(out, Role.MIDDLE) == middle


@pytest.mark.parametrize("policy", _FAMILY_FIRST)
def test_a_bound_pair_survives_the_leading_particle_stop(
        policy: Policy) -> None:
    # The stop leaves the bound pair whole (rules.md#P5 via _units).
    # Asserted under a family-first order deliberately: in the DEFAULT
    # order the fold takes the whole name into the family, so the join
    # is invisible there and the assertion would pass with the join
    # broken.
    out = run(ParseState(original="de Mesnil abd Allah",
                         lexicon=Lexicon.default(), policy=policy))
    assert _by_role(out, Role.FAMILY) == "de Mesnil"
    assert _by_role(out, Role.GIVEN) == "abd Allah"
