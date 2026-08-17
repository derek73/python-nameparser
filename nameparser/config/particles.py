from nameparser.config._invariants import assert_normalized
from nameparser.config.bound_given_names import BOUND_GIVEN_NAMES

#: The sub-set of :py:data:`PARTICLES` that are *never* a standalone given
#: name. Where one of these stands ALONE as the piece opening a name, that
#: name has no given name -- the whole thing is a surname (e.g. "de Mesnil"
#: -> family name "de Mesnil") -- and that reading holds under EVERY
#: ``name_order`` (#359). It is not scoped to the default order the way the
#: rest of the positional read is: ``name_order`` says which side of the
#: name the family sits on, and a word that can never be a given name
#: leaves it nothing to decide, so ``Policy(name_order=FAMILY_FIRST)``
#: reads "de Mesnil" as the family name too. What is asked about is the
#: opening *piece*, not the first word of the string: a particle that has
#: already chained onto the word behind it is part of that piece rather
#: than standing alone.
#: Opening the name is only the commonest shape. The rule enforcing it
#: (rules.md#P1; the pre-2.2 docstrings called it rule 1b) reaches a
#: member standing alone as a piece in
#: the given position too, folding it into the family beside it, so that
#: neither shape leaves a given name behind -- as long as there is another
#: name token to fold into. A bare "de" stays as it is. Where a chain is
#: reported as the given name anyway it is because the member is no
#: longer standing alone: under ``Policy(name_order=FAMILY_FIRST)`` the
#: given position of "Juan de la Vega" holds the whole three-token
#: chain, so the rule declines and given "de la Vega" stands. A title
#: in front is NOT such a case -- since #367 a title is transparent to
#: the leading-particle exception, so "Sir de Mesnil" leaves "de" a lone
#: piece and reads family "de Mesnil", exactly as the untitled form does.
#: Membership also decides the ambiguity report -- see
#: :py:data:`PARTICLES` below.
#: Curated to exclude anything that can be a given name in some culture
#: (`al`, `van`, `von`, `della`, `di`, `del`, `da`, `vander`, ...) and
#: anything that is also a bound given-name particle (`abu`). When unsure,
#: leave a word out: a missing member just means that name is not
#: auto-fixed, whereas a wrong member misparses a real person. Must stay a
#: subset of :py:data:`PARTICLES` and disjoint from
#: :py:data:`~nameparser.config.bound_given_names.BOUND_GIVEN_NAMES`.
NON_GIVEN_NAME_PARTICLES = frozenset({
    # Latin-script members. Every entry here is a grammatical particle --
    # an article, a preposition, or a patronymic marker -- and that is the
    # form a never-given record has to take. One attested bearer settles
    # the AMBIGUOUS side; no amount of searching settles absence, so what
    # is recorded is what the word IS rather than a failed search.
    #
    # The test is POSITIONAL (decisions.md#vocabulary-collisions C-i,
    # corrected 2026-08-17): membership asks whether the word is borne as
    # a name in the position this rule ACTS on -- leading, or alone in the
    # given role -- not whether a bearer exists anywhere. 'de' is why the
    # qualifier is needed: "De" is a borne Bengali/Odia surname, but a
    # TRAILING one, so it never meets the rule.
    #
    # A BARE entry, here or in PARTICLES below, means nobody has examined
    # it. Absence of a comment is the audit record.
    "'t",      # Dutch contraction of 'het' ("'t Hooft"): the article itself
    'af',      # Danish/Norwegian nobiliary "of"
    'auf',     # German "upon" ("auf der Heide")
    'av',      # Swedish/Norwegian "of"
    'bint',    # Arabic "daughter of"; native-script بنت below
    'de',      # French/Iberian/Italian "of". "De" IS a borne Bengali and
               # Odia surname -- trailing, so it never reaches this rule.
               # The case that forced C-i's positional qualifier.
    "de'",     # Italian elided "dei" ("de' Medici")
    'degli',   # Italian "of the", masc. pl.
    'dei',     # Italian "of the", masc. pl.
    'delle',   # Italian "of the", fem. pl.
    'delli',   # Italian "of the", regional variant of 'dei'
    'dello',   # Italian "of the", masc. sg.
    'dem',     # German dative article
    'der',     # German article ("von der Leyen")
    'dos',     # Portuguese "of the", masc. pl.
    'het',     # Dutch definite article
    'ibn',     # Arabic "son of"; native-script ابن below
    'op',      # Dutch "at/on" ("op den Berg")
    'ter',     # Dutch "at the" ("ter Horst")
    'vd',      # Dutch abbreviation of "van der". Also the British
               # Volunteer Decoration, a suffix acronym: two non-name
               # readings, so C-ii decides it on frequency and the Dutch
               # one wins (decisions.md#vocabulary-collisions).
    'vom',     # German "from the"
    'zu',      # German "at/to", nobiliary ("zu Guttenberg")

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
#: first piece of the NAME, its membership in this set or in
#: :py:data:`NON_GIVEN_NAME_PARTICLES` never entering into it. Leading
#: is read off the name rather than off the input (#367): a title is
#: not part of the name, so it is stepped over and "Dr. Van Johnson"
#: reads as the untitled "Van Johnson" does. One kind of word is not
#: stepped over, and this is the one place a title's vocabulary and
#: this one interact -- ``st``, ``do`` and ``freiherr`` are each BOTH
#: a title and a particle, so any of them could be the name's own
#: first piece and stops the scan, leaving a particle behind it
#: non-leading and free to chain ("Freiherr von Richthofen").
#: Where the pieces then land is again a later
#: question, and this is where membership decides something: a leading
#: :py:data:`NON_GIVEN_NAME_PARTICLES` member makes the whole name a
#: family name ("de la Vega") under every ``name_order``, because a word
#: that is never a given name leaves the order nothing to place. A
#: leading particle OUTSIDE that set could be either, so there
#: ``name_order`` decides after all: the default given-first order reads
#: it as the given name ("Van Johnson"), while either family-first order
#: splits the same chains-nothing grouping the other way round ("Van
#: Johnson" -> family "Van", given "Johnson").
#: What membership decides under ANY of the three orders is also the
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
