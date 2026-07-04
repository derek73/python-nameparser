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
}
