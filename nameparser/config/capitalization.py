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
does not spell its key's letters and digits is a ``ValueError`` when
a ``Lexicon`` is built from it. An acronym the suffix vocabulary
already lists, written plainly or in dotted form, and a roman
numeral need no entry: case repair writes a suffix of either kind in
capitals by itself. A caller's OWN acronym -- one absent from
``suffix_acronyms`` -- depends on how it is written. Written
PLAINLY (``dphil``) it parses as an ordinary name word and repairs
as one (``Dphil``). Written DOTTED (``d.phil.``) it is a suffix by
shape alone, with no vocabulary entry needed to read it as one, and
repairs in all capitals the same as a listed acronym does
(``D.PHIL.``). Either way, a caller who wants a specific spelling
needs a ``suffix_acronyms`` entry (``Lexicon.add(suffix_acronyms=
{...})`` in the 2.0 API, ``constants.suffix_acronyms.add(...)`` in
the v1 one) or a mask of its own.
"""


# Keys only -- the values are case masks, cased on purpose.
assert_normalized("CAPITALIZATION_EXCEPTIONS", CAPITALIZATION_EXCEPTIONS)
