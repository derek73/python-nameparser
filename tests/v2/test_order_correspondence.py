"""The family-first/comma correspondence, as an executable invariant
(#469).

Form 4 (Title Family Given Middle Middle [Particle] [, Suffix] under
FAMILY_FIRST) is form 2 (Family [Suffix], Title Given (Nickname)
Middle Middle[,] Suffix [, Suffix]) with the comma removed and the
family inline -- the two notations quoted verbatim from
tools/differential/shapes.py. The pairs are GENERATED and asserted
equal, which consults no vocabulary and no rule -- so it catches a
rule that is WRONG, which review cannot.

Provenance (decisions.md#P6, the 2026-08-30 #467 entry): over ALL 70
particles x 3 families x 3 givens = 630 generated names, 0 of 630
agreed before the #467 change and 603 of 630 after. The 27 failures
are the particle-and-suffix trio -- vd, mc, do -- a real limit and
not noise (rules.md#P6, restated as a third bullet below); this
module's own parametrized sweep below excludes that trio on purpose
and covers 2 x 1 x 3 x 4 x 2 x 2 pairs of its own -- families,
givens, middles, particles, titles, suffixes -- a SEPARATE, smaller
count that must never be quoted as the 630 measurement or vice versa.
Written as the product rather than as a figure because the figure was
the thing that went stale: the tuples below are what decides it. decisions.md
#two-input-invariants recomputes the same correspondence a second
way -- a 6x6 spread of families and givens per particle rather than
3x3 -- and gets 67 of 70 particles agreeing on all 36 of their pairs,
the same trio failing all 36; its Recompute recipe is what this
file's negative-control test below runs. #466, the rejected
predecessor, has no comparable number on record; its defects are
qualitative -- it lost a given name outright on "van Berg Jan de"
and promoted a post-nominal into the given slot on "Berg Jan Jr.
de" (decisions.md#P6). An earlier draft of this module cited
"0/216 -> 216/216", which decisions.md#P6 explicitly retracts: that
number came from a script slicing the vocabulary
(`sorted(particles)[:14]`), which happened to exclude exactly vd, mc
and do -- the project's own example of a detector inheriting the
design's blind spot (decisions.md#P6 says: "A FIRST DRAFT OF THIS
ENTRY CLAIMED 216 of 216 ... Recompute over the WHOLE vocabulary,
never a sample").

Three limits, load-bearing (from #469 and #467). All three are now
restated in customize.rst's family-first section, alongside the
corrected 603/630 measurement:

- One shape written two ways, NOT comma-deletion in general. A name
  whose SHAPE changes when the comma goes (a title moving mid-name)
  is a different shape, not a counterexample, so no such pair is
  generated here.
- Form 5 has no comma twin: no comma format puts the given name
  last, which is why FAMILY_FIRST_GIVEN_LAST appears nowhere in this
  file.
- Where a word is both particle and suffix vocabulary, the two
  writings read it differently and the correspondence genuinely
  fails. It is the ASYMMETRY that breaks it, not a precedence
  applying to both sides: the attachment outranks the suffix reading
  on the COMMA side, which is the scope rules.md#P6 states it in, so
  `Ménil, Christophe vd` reads family `vd Ménil` while the
  family-first `Ménil Christophe vd` reads family `Ménil` and suffix
  `vd`. Not a bug, but rules.md#P6 stating it plainly:
  "the word is BOTH a particle and suffix vocabulary, this
  attachment outranks the suffix reading (S2): a trailing
  abbreviation after a family comma is the tussenvoegsel far more
  often than the decoration it collides with" -- and decisions.md
  #P6 calling it "a real limit, not noise". The parametrized
  vocabulary below deliberately excludes vd/mc/do; the negative
  control test owns them instead.

A mass failure here -- most or all pairs turning red, rather than a
handful -- means the correspondence itself has narrowed and rules.md
#P6 needs amending alongside this file, not that the vocabulary
needs shrinking to get back to green.
"""
import itertools
import unicodedata
from collections.abc import Iterator

import pytest

from nameparser import FAMILY_FIRST, ParsedName, Parser, Policy, Role, parse
from nameparser.config.particles import PARTICLES as _SHIPPED_PARTICLES

_FF = Parser(policy=Policy(name_order=FAMILY_FIRST))
_ROLES = tuple(r.value for r in Role)  # test_cases.py's idiom; declaration
                                        # order is canonical


def _reading(p: ParsedName) -> dict[str, object]:
    """The comparator shape tools/differential/compare.py uses: the
    seven role fields (never None -- ParsedName's role properties are
    typed `-> str`) plus the ambiguity-kind SET. decisions.md#P6
    (#405) records that this design's own repaired failure was
    exactly an ambiguity ASYMMETRY between two writings of one name,
    so a role-only comparison would miss the most fragile part of the
    correspondence. A set and not a sorted multiset, mirroring
    compare.py's own `sorted({a.kind.name for a in ...})` exactly --
    two occurrences of one kind are not a second thing to agree on."""
    out: dict[str, object] = {r: getattr(p, r) for r in _ROLES}
    out["_ambiguities"] = sorted({a.kind.name for a in p.ambiguities})
    return out


FAMILIES = ("Ménil", "Jong")  # Ménil pins the non-ASCII case
GIVENS = ("Christophe",)
MIDDLES = (None, "Marie", "Marie Louise")  # shape 4's notation names
                                            # Middle Middle; "Marie Louise"
                                            # is the one pair generating two
# never-given (de), ambiguous (van), and a multi-token run (van der).
# The multi-token member is not decoration: a last-particle-only walk
# once survived the whole suite on single-token fixtures alone, and
# tests/v2/pipeline/test_post_rules.py::test_a_multi_token_run_is_taken_whole
# is the pin that now owns that shape at the rule layer.
PARTICLES = (None, "de", "van", "van der")
TITLES = (None, "Dr.")
SUFFIXES = (None, "Jr.")


def _slug(s: str) -> str:
    """Turn an inline spelling into a bare pytest id: no quoting needed
    to select one case. Folded to ASCII -- pytest itself backslash-
    escapes a non-ASCII character in an id, which would make that
    claim false for Menil's accent."""
    ascii_s = unicodedata.normalize("NFKD", s).encode("ascii", "ignore")
    return ascii_s.decode("ascii").replace(" ", "_").translate(
        str.maketrans("", "", ".,"))


def _pairs() -> Iterator[tuple[str, str]]:
    """(comma spelling, family-first spelling) for every combination.
    The title moves position between the writings -- post-comma in
    form 2, leading in form 4 -- which is the part of the
    correspondence review keeps getting wrong, so it is generated
    rather than sampled."""
    for fam, giv, mid, part, title, suf in itertools.product(
            FAMILIES, GIVENS, MIDDLES, PARTICLES, TITLES, SUFFIXES):
        tail = " ".join(p for p in (giv, mid, part) if p)
        t = f"{title} " if title else ""
        comma = f"{fam}, {t}{tail}" + (f", {suf}" if suf else "")
        inline = f"{t}{fam} {tail}" + (f", {suf}" if suf else "")
        yield comma, inline


_PAIRS = list(_pairs())
_IDS = [_slug(inline) for _, inline in _PAIRS]


@pytest.mark.parametrize("comma, inline", _PAIRS, ids=_IDS)
def test_form_4_parses_as_its_comma_twin(comma: str, inline: str) -> None:
    a, b = parse(comma), _FF.parse(inline)
    got_a, got_b = _reading(a), _reading(b)
    assert got_a == got_b, (
        f"{comma!r} (default) and {inline!r} (FAMILY_FIRST) are one "
        f"shape written two ways and must agree")


# The recorded negative control (decisions.md#P6, decisions.md#two-
# input-invariants, rules.md#P6): the ONLY members of the shipped
# particle vocabulary where the correspondence fails are the words
# that are both particle and suffix vocabulary. Swept over the entire
# shipped vocabulary -- nameparser.config.particles.PARTICLES, the
# same source the invariant's own measurements drew from, never a
# hand copy -- rather than the small parametrized set above, so this
# is the test that would notice if a fourth word joined the trio.
#
# mechanisms.md#RECORDED-ROSTERS: "never re-derive the expectation
# from the same inputs the check reads, because a derivation from the
# same data always agrees with itself" -- a recorded literal, kept by
# hand and never computed from the vocabulary intersection below.
_EXPECTED_DISAGREEING_PARTICLES = frozenset({"do", "mc", "vd"})


def test_only_the_particle_suffix_trio_breaks_the_correspondence() -> None:
    # rules.md#P6 states the exception this sweep measures: "the word
    # is BOTH a particle and suffix vocabulary, this attachment
    # outranks the suffix reading (S2)"
    #
    # The shape is the minimal "Family Given Particle" -- one family,
    # one given -- rather than decisions.md#two-input-invariants' 6x6
    # spread, because that entry's own Recompute bullet says a spread
    # only matters to rule out families/givens that are THEMSELVES
    # particle vocabulary (the precondition asserted below); once
    # that is excluded, the failures partition on the particle word
    # alone; one point suffices.
    fam, giv = "Ménil", "Christophe"
    # mechanisms.md#VOCABULARY-OVERLAP-AS-PRECONDITION: "assert the
    # intersection as a precondition" -- inverted from the mechanism's
    # usual shape: what has to hold here is the intersection being
    # EMPTY, not populated. decisions.md#two-input-invariants records
    # that a particle-vocabulary family or given measures a different
    # shape and reports 0 of 70 rather than 67 of 70.
    assert not ({fam.lower(), giv.lower()} & _SHIPPED_PARTICLES), (
        f"{fam!r} or {giv!r} joined the shipped particle vocabulary; "
        f"this sweep measures the Family Given Particle shape and "
        f"needs a family/given that is not itself particle vocabulary "
        f"-- pick another pair")
    disagreeing = set()
    for p in _SHIPPED_PARTICLES:
        comma = f"{fam}, {giv} {p}"
        inline = f"{fam} {giv} {p}"
        got_a = _reading(parse(comma))
        got_b = _reading(_FF.parse(inline))
        if got_a != got_b:
            disagreeing.add(p)
    assert disagreeing == _EXPECTED_DISAGREEING_PARTICLES, (
        f"the particle vocabulary's disagreeing set changed: "
        f"got {sorted(disagreeing)}, expected "
        f"{sorted(_EXPECTED_DISAGREEING_PARTICLES)} -- this is a finding, "
        f"not a fixture to update blindly")
