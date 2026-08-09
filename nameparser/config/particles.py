from nameparser.config._invariants import assert_normalized
from nameparser.config.bound_given_names import BOUND_GIVEN_NAMES

#: The sub-set of :py:data:`PARTICLES` that are *never* a standalone given
#: name. A name that *starts* with one of these has no given name -- the
#: whole thing is a surname (e.g. "de Mesnil" -> family name "de Mesnil").
#: Curated to exclude anything that can be a given name in some culture
#: (`al`, `van`, `von`, `della`, `di`, `del`, `da`, `vander`, ...) and
#: anything that is also a bound given-name particle (`abu`). When unsure,
#: leave a word out: a missing member just means that name is not
#: auto-fixed, whereas a wrong member misparses a real person. Must stay a
#: subset of :py:data:`PARTICLES` and disjoint from
#: :py:data:`~nameparser.config.bound_given_names.BOUND_GIVEN_NAMES`.
NON_GIVEN_NAME_PARTICLES = {
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
}

#: Family-name particles: a particle joins to the piece that follows it
#: to make one new piece, and particles chain, e.g. "von der" and
#: "de la". A particle in a non-leading position also pulls the pieces
#: after it into the same one, up to the next particle run or suffix,
#: which is how a multi-word name piece is recognized. Where that piece
#: lands is a later question: in "pennie von bergen wessels MD", "von"
#: joins each following piece until the suffix "MD", giving the family
#: name "von bergen wessels", while the same chaining in "Smith, Juan
#: de la Cruz" gives the middle name "de la Cruz". A leading
#: particle is the exception and chains nothing, since it may be a given
#: name instead: one in :py:data:`NON_GIVEN_NAME_PARTICLES` makes the
#: whole name a family name ("de la Vega"), while one outside that set is
#: read as a given name ("Van Johnson") and records a particle-or-given
#: ambiguity for the reading not taken.
#:
#: Defined as a static union so every :py:data:`NON_GIVEN_NAME_PARTICLES`
#: member is guaranteed to also be a particle (and still join forward),
#: with no drift -- mirroring ``TITLES = FIRST_NAME_TITLES | {...}`` in
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
