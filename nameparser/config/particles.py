# The words, and the vetting notes that stood beside them here, live in
# nameparser/vocab/*.toml: every particle reading states may_be_given,
# true for the ambiguous half and false for the never-given half, so the two
# partition PARTICLES by construction. tools/vocab/build.py compiles them
# into _compiled.py and runs the checks that were import-time asserts
# here -- a bound given name that is also a particle must be one that may
# be given, and an elided particle ships in both apostrophes (#700)
# (decisions/vocabulary-model).
from nameparser.config import _compiled

#: The sub-set of :py:data:`PARTICLES` that no culture uses as a standalone
#: given name. Where one of these stands ALONE as the piece opening a name, that
#: name has no given name -- the whole thing is a surname (e.g. "de Mesnil"
#: -> family name "de Mesnil") -- and that reading holds under EVERY
#: ``name_order`` (#359). It is not scoped to the default order the way the
#: rest of the positional read is: what settles it is that a particle
#: opening the name has the rest of the name to JOIN FORWARD TO, which
#: is evidence about the writing rather than about the word, so
#: ``Policy(name_order=FAMILY_FIRST)`` reads "de Mesnil" as the family
#: name too. Membership here does NOT mean the word can never be a
#: given name -- where position forces the reading it is one, and every
#: member of this set reports given "de"-style for a bare parse. What is asked about is the
#: opening *piece*, not the first word of the string: a particle that has
#: already chained onto the word behind it is part of that piece rather
#: than standing alone.
#: OPENING the name is the whole of that rule's subject (rules/P1;
#: the pre-2.2 docstrings called it rule 1b). A member standing alone
#: where a declared order puts the GIVEN name was a second site until
#: #467, and is not one now: that slot holds what the caller declared,
#: so ``Policy(name_order=FAMILY_FIRST)`` reads "Mesnil de" as family
#: "Mesnil", given "de". A member ENDING the name under a family-first
#: order is rules/P6's, which joins it to the family. A bare "de" stays as it is. Where a chain is
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
NON_GIVEN_NAME_PARTICLES = _compiled.NON_GIVEN_NAME_PARTICLES

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
#: this one interact -- ``st`` and ``freiherr`` are each BOTH a title
#: and a particle (``do`` was too, until #296), so either could be the name's own
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
#: Both sets are compiled from the same particle readings, the never-given
#: ones being those with ``may_be_given = false``, which is what guarantees every
#: :py:data:`NON_GIVEN_NAME_PARTICLES` member is also a particle (and
#: still joins forward), with no drift.
PARTICLES = _compiled.PARTICLES

# Star imports read __all__ and never the module __getattr__ -- see the
# note in prefixes.py. This module has no retired name of its own to
# serve; what __all__ buys here is the other half of that note's point,
# which the shim modules got in #354 and the destinations did not:
# without it a star import binds every module-level name, so a helper
# imported here lands in the caller's namespace as though it were
# vocabulary (#356) -- `_compiled` now, as `assert_normalized` and
# BOUND_GIVEN_NAMES did before the vocabulary moved to TOML.
# Source order, not alphabetical -- see the note in suffixes.py.
__all__ = ["NON_GIVEN_NAME_PARTICLES", "PARTICLES"]
