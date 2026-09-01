from nameparser.config._invariants import assert_normalized

#: Bound Arabic given-name prefixes that attach to the following word to
#: form one given name (e.g. "abdul salam smith" → given name "abdul
#: salam"). They are never standalone names. The join is a group-stage
#: rule on the FIRST non-title piece, so it is not about roles -- it
#: fires whatever name_order later assigns. It reserves a piece for what
#: follows: three pieces that are neither title nor suffix in a main
#: segment -- counting the bound word's OWN piece even where that word is
#: also suffix vocabulary, since it is the piece the rule has claimed
#: rather than one left to spare -- which is why two-word "abdul salam"
#: stays given "abdul" plus
#: family "salam"; only two after a family comma, where the family name
#: is already fixed ("salam, abdul rahman" → given "abdul rahman").
#: Mirrors :py:data:`~nameparser.config.particles.PARTICLES`, which
#: chains onto the piece that follows it.
BOUND_GIVEN_NAMES: frozenset[str] = frozenset({
    'abdul',
    'abdel',
    'abdal',
    # The bare transliteration, which abdul/abdel/abdal do not match:
    # "abd Allah Smith" -> given "abd Allah", and "Abd al-Rahman
    # Smith" likewise, al-Rahman being ONE token. The three-token
    # spelling "abd al rahman smith" is still not joined -- `al` is a
    # particle and chains forward -- and stays deferred, as it was
    # when this word was excluded. Same word as عبد below, which has
    # covered the Arabic-script side since #269 (shipped in 2.0).
    #
    # Collides with the postnominal ABD ("All But Dissertation"),
    # which stays in SUFFIX_ACRONYMS. Position decides at the two ends
    # -- a leading `abd` reads as a name, a trailing one as the
    # credential -- but not everywhere: in the given slot of a
    # family-comma name the credential still wins, so "Smith, Abd"
    # reports suffix 'Abd' and no given name, where "Smith, Abdul"
    # reports the given name. Recorded at decisions.md#P5.
    'abd',
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

# Star imports read __all__ and never the module __getattr__ -- see the
# note in prefixes.py. Without it `assert_normalized`, imported only for
# the invariant above, is bound by a star import as though it were
# vocabulary (#356).
__all__ = ["BOUND_GIVEN_NAMES"]
