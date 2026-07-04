#: The sub-set of :py:data:`PREFIXES` that are *never* a standalone first name.
#: A name that *starts* with one of these has no first name -- the whole thing
#: is a surname (e.g. "de Mesnil" -> last name "de Mesnil"). Curated to exclude
#: anything that can be a given name in some culture (`al`, `van`, `von`,
#: `della`, `di`, `del`, `da`, `vander`, ...) and anything that is also a first
#: name prefix (`abu`). When unsure, leave a word out: a missing member just
#: means that name is not auto-fixed, whereas a wrong member misparses a real
#: person. Must stay a subset of :py:data:`PREFIXES` and disjoint from
#: :py:data:`~nameparser.config.first_name_prefixes.FIRST_NAME_PREFIXES`.
NON_FIRST_NAME_PREFIXES = set([
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
])

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
PREFIXES = NON_FIRST_NAME_PREFIXES | set([
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
])
