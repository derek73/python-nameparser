from nameparser.config._invariants import assert_normalized
from nameparser.config.bound_given_names import BOUND_GIVEN_NAMES

#: The sub-set of :py:data:`PARTICLES` that are *never* a standalone given
#: name. A name *starting* with one of these has no given name -- the
#: whole thing is a surname (e.g. "de Mesnil" -> family name "de Mesnil")
#: -- and that reading holds under EVERY ``name_order`` (#359). It is not
#: scoped to the default order the way the rest of the positional read is:
#: ``name_order`` says which side of the name the family sits on, and a
#: word that can never be a given name leaves it nothing to decide, so
#: ``Policy(name_order=FAMILY_FIRST)`` reads "de Mesnil" as the family
#: name too. Membership also decides the ambiguity report -- see
#: :py:data:`PARTICLES` below.
#: Curated to exclude anything that can be a given name in some culture
#: (`al`, `van`, `von`, `della`, `di`, `del`, `da`, `vander`, ...) and
#: anything that is also a bound given-name particle (`abu`). When unsure,
#: leave a word out: a missing member just means that name is not
#: auto-fixed, whereas a wrong member misparses a real person. Must stay a
#: subset of :py:data:`PARTICLES` and disjoint from
#: :py:data:`~nameparser.config.bound_given_names.BOUND_GIVEN_NAMES`.
NON_GIVEN_NAME_PARTICLES = frozenset({
    "'t",
    'af',
    'auf',
    'av',
    'bint',
    'de',
    "de'",
    'degli',
    'dei',
    'delle',
    'delli',
    'dello',
    'dem',
    'der',
    'dos',
    'het',
    'ibn',
    'op',
    'ter',
    'vd',
    'vom',
    'zu',

    # #269: Arabic native-script patronymic/clan particles. Unlike their
    # Latin transliterations, these live in a script namespace with no
    # collision against an unrelated Latin given name, so each is judged
    # on its own semantics rather than mirrored blindly:
    'بن',     # "bin"/"ibn" (son of) -- never a bare given name. Latin
              # 'bin' is in PARTICLES but not in this set; that judgment
              # is unchanged by adding the Arabic-script form.
    'بنت',    # "bint" (daughter of) -- mirrors Latin 'bint' above.
    'ابن',    # "ibn" (son of, alternate spelling) -- mirrors Latin
              # 'ibn' above.
    'آل',     # "aal" (family/clan of, e.g. "Al Saud") -- distinct from
              # the excluded definite article "ال" (#269 explicitly
              # excludes standalone "ال"); a clan prefix, never a bare
              # given name.

    # #269: Hebrew native-script patronymic particles -- same
    # reasoning as the Arabic ones above: no Latin-script collision,
    # and neither functions as a standalone given name in Hebrew usage.
    # Deferred under the collision rule: 'בר' (Aramaic son-of, as in
    # Bar-Lev) -- Bar is a common modern Israeli given name, and the
    # surname spelling is hyphenated anyway.
    'בן',     # "ben" (son of)
    'בת',     # "bat" (daughter of)
})

# Maintainer note, deliberately a plain comment ABOVE the `#:` run
# rather than inside it: `#:` would publish it into the API reference,
# where it is advice to nobody, and a plain comment placed *within* the
# run splits it -- autodoc then renders only the fragment below the
# split and silently drops everything above it. Frozen by construction
# (#293) -- `frozenset | set` returns a frozenset, the LEFT operand's
# type wins, so keep the frozenset first. Flipped, this silently yields
# a plain set again and unfreezes the constant.
#: Family-name particles: a particle joins to the piece that follows it
#: to make one new piece, and particles chain, e.g. "von der" and
#: "de la". A particle in a non-leading position also pulls the pieces
#: after it into the same one, up to the next particle run or suffix,
#: which is how a multi-word name piece is recognized. Where that piece
#: lands is a later question: in "pennie von bergen wessels MD", "von"
#: joins each following piece until the suffix "MD", giving the family
#: name "von bergen wessels", while the same chaining in "Smith, Juan
#: de la Cruz" gives the middle name "de la Cruz". A leading
#: particle is the exception and chains nothing: the chain skips the
#: first piece unconditionally, membership in this set or any other
#: never entering into it. Where the pieces then land is again a later
#: question, and this is where membership decides something: a leading
#: :py:data:`NON_GIVEN_NAME_PARTICLES` member makes the whole name a
#: family name ("de la Vega") under every ``name_order``, because a word
#: that is never a given name leaves the order nothing to place. A
#: leading particle OUTSIDE that set could be either, so there
#: ``name_order`` decides after all: the default given-first order reads
#: it as the given name ("Van Johnson"), while
#: ``Policy(name_order=FAMILY_FIRST)`` splits the same chains-nothing
#: grouping the other way round ("Van Johnson" -> family "Van", given
#: "Johnson"). What membership decides under EITHER order is also the
#: report: a leading particle outside
#: :py:data:`NON_GIVEN_NAME_PARTICLES` records a particle-or-given
#: ambiguity for the reading not taken, and one inside it records none.
#:
#: Defined as a static union so every :py:data:`NON_GIVEN_NAME_PARTICLES`
#: member is guaranteed to also be a particle (and still join forward),
#: with no drift -- mirroring ``TITLES = GIVEN_NAME_TITLES | {...}`` in
#: :py:mod:`nameparser.config.titles`.
PARTICLES = NON_GIVEN_NAME_PARTICLES | {
    'aan',
    'aen',
    'abu',
    'al',
    'bar',
    'bat',
    'bin',
    'bon',
    'da',
    'dal',
    'del',
    'dela',
    'della',
    'den',
    'di',
    'dí',
    'do',
    'du',
    'freiherr',
    'freiherrin',
    'heer',
    'la',
    'le',
    'mac',
    'mc',
    'san',
    'santa',
    'st',
    'ste',
    'te',
    'tho',
    'thoe',
    'van',
    'vande',
    'vander',
    'vel',
    'von',

    # #269: Arabic "abu" (father of), left ambiguous like its Latin
    # transliteration 'abu' above (both spellings): "Abu Bakr" reads
    # "Abu" as a given name, so this stays a PARTICLES-only member, not
    # NON_GIVEN_NAME_PARTICLES.
    'أبو',
    'ابو',
}

# Guard the two invariants the docstring above promises, so a future edit that
# breaks them fails at import time instead of silently drifting until a test
# happens to catch it.
assert NON_GIVEN_NAME_PARTICLES <= PARTICLES, \
    "NON_GIVEN_NAME_PARTICLES must stay a subset of PARTICLES"
assert not (NON_GIVEN_NAME_PARTICLES & BOUND_GIVEN_NAMES), \
    "NON_GIVEN_NAME_PARTICLES must stay disjoint from BOUND_GIVEN_NAMES"
assert_normalized("PARTICLES", PARTICLES)
