from nameparser.config._invariants import assert_normalized

CAPITALIZATION_EXCEPTIONS = {
    'bsc': 'BSc',
    'msc': 'MSc',
    'phd': 'PhD',
}
"""
Words whose case ``str.capitalize()`` gets wrong, each mapped to a
case MASK: the key's own letters and digits, each in the case it
should take. Case repair lays the mask over the word as it was
written and keeps every other character where the writer put it, so
``'phd': 'PhD'`` repairs ``phd`` to ``PhD`` and ``ph.d.`` to
``Ph.D.``. The mask's own punctuation marks where its letters are
joined into one run versus split apart, and is never written into
the word -- repair keeps the writer's own punctuation. A value that
does not spell its key's letters is a ``ValueError`` when a
``Lexicon`` is built from it. A credential acronym written all in
capitals and a roman numeral need no entry: case repair writes a
suffix of either kind in capitals by itself.
"""


# Keys only -- the values are case masks, cased on purpose.
assert_normalized("CAPITALIZATION_EXCEPTIONS", CAPITALIZATION_EXCEPTIONS)
