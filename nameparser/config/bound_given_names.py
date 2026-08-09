from nameparser.config._invariants import assert_normalized

#: Bound Arabic given-name prefixes that attach to the following word to
#: form one given name (e.g. "abdul salam smith" → given name "abdul
#: salam"). They are never standalone names. The join is a group-stage
#: rule on the FIRST non-title piece, so it is not about roles -- it
#: fires whatever name_order later assigns. It reserves a piece for what
#: follows: three pieces that are neither title nor suffix in a main
#: segment, which is why two-word "abdul salam" stays given "abdul" plus
#: family "salam"; only two after a family comma, where the family name
#: is already fixed ("salam, abdul rahman" → given "abdul rahman").
#: Mirrors :py:data:`~nameparser.config.particles.PARTICLES`, which
#: chains onto the piece that follows it.
BOUND_GIVEN_NAMES: frozenset[str] = frozenset({
    'abdul',
    'abdel',
    'abdal',
    'abu',
    'abou',
    'umm',

    # #269 follow-up: the Arabic-script originals of the entries above.
    # Script writes "Abdul Rahman" as two words (عبد + الرحمن -- the
    # article attaches to the following word), so عبد alone covers the
    # abdul/abdel/abdal variants. Both kunya spellings ship, matching
    # the أبو/ابو prefix pair.
    'عبد',    # "abd" (servant of) -- عبد الرحمن -> given "عبد الرحمن"
    'أبو',    # "abu" (father of), hamza spelling
    'ابو',    # "abu", hamza-less spelling
    'أم',     # "umm" (mother of), hamza spelling
    'ام',     # "umm", hamza-less spelling
})


assert_normalized("BOUND_GIVEN_NAMES", BOUND_GIVEN_NAMES)
