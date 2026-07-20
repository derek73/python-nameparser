from nameparser.config._invariants import assert_normalized

#: Bound Arabic given-name prefixes that attach to the following word to form
#: one first name (e.g. "abdul salam" → first name "abdul salam"). They are
#: never standalone names. Join logic runs in the given-name region only,
#: mirroring :py:data:`~nameparser.config.prefixes.PREFIXES` for last names.
BOUND_FIRST_NAMES: set[str] = {
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
}


assert_normalized("BOUND_FIRST_NAMES", BOUND_FIRST_NAMES)
