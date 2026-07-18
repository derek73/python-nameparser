from nameparser.config.bound_first_names import BOUND_FIRST_NAMES

#: The sub-set of :py:data:`PREFIXES` that are *never* a standalone first name.
#: A name that *starts* with one of these has no first name -- the whole thing
#: is a surname (e.g. "de Mesnil" -> last name "de Mesnil"). Curated to exclude
#: anything that can be a given name in some culture (`al`, `van`, `von`,
#: `della`, `di`, `del`, `da`, `vander`, ...) and anything that is also a first
#: name prefix (`abu`). When unsure, leave a word out: a missing member just
#: means that name is not auto-fixed, whereas a wrong member misparses a real
#: person. Must stay a subset of :py:data:`PREFIXES` and disjoint from
#: :py:data:`~nameparser.config.bound_first_names.BOUND_FIRST_NAMES`.
NON_FIRST_NAME_PREFIXES = {
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
              # 'bin' is in PREFIXES but not in this set; that judgment
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

#: Name pieces that appear before a last name. Prefixes join to the piece
#: that follows them to make one new piece. They can be chained together, e.g
#: "von der" and "de la". Because they only appear in middle or last names,
#: they also signify that all following name pieces should be in the same name
#: part, for example, "von" will be joined to all following pieces that are not
#: prefixes or suffixes, allowing recognition of double last names when they
#: appear after a prefixes. So in "pennie von bergen wessels MD", "von" will
#: join with all following name pieces until the suffix "MD", resulting in the
#: correct parsing of the last name "von bergen wessels".
#:
#: Defined as a static union so every :py:data:`NON_FIRST_NAME_PREFIXES` member
#: is guaranteed to also be a prefix (and still join forward), with no drift --
#: mirroring ``TITLES = FIRST_NAME_TITLES | {...}`` in
#: :py:mod:`nameparser.config.titles`.
PREFIXES = NON_FIRST_NAME_PREFIXES | {
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
    # "Abu" as a given name, so this stays a PREFIXES-only member, not
    # NON_FIRST_NAME_PREFIXES.
    'أبو',
    'ابو',
}

# Guard the two invariants the docstring above promises, so a future edit that
# breaks them fails at import time instead of silently drifting until a test
# happens to catch it.
assert NON_FIRST_NAME_PREFIXES <= PREFIXES, \
    "NON_FIRST_NAME_PREFIXES must stay a subset of PREFIXES"
assert not (NON_FIRST_NAME_PREFIXES & BOUND_FIRST_NAMES), \
    "NON_FIRST_NAME_PREFIXES must stay disjoint from BOUND_FIRST_NAMES"
