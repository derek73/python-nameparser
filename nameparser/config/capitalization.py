from nameparser.config._invariants import assert_normalized

CAPITALIZATION_EXCEPTIONS = {
    'bsc': 'BSc',
    'msc': 'MSc',
    'phd': 'PhD',
    # Listed post-nominals whose conventional spelling is mixed case
    # (#459): without a mask the acronym repair writes each in
    # capitals. A mask applies wherever its word stands, so a word
    # borne as a name must not get one -- meng and edd are listed
    # acronyms that are, and stay out on purpose (decisions.md#R4's
    # Excluded block).
    'bt': 'Bt',
    'chfc': 'ChFC',
    'cpht': 'CPhT',
    'diplac': 'DiplAc',
    'dmin': 'DMin',
    'drph': 'DrPH',
    'dsc': 'DSc',
    'kt': 'Kt',
    'mdiv': 'MDiv',
    'pharmd': 'PharmD',
    'phc': 'PhC',
    'psyd': 'PsyD',
    'rph': 'RPh',
    'thd': 'ThD',
    'thm': 'ThM',
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
capitals by itself. The map carries most of the listed acronyms
whose conventional spelling is NOT all capitals (``DSc``, ``PsyD``,
``PharmD``), so ``psyd`` repairs to ``PsyD`` rather than ``PSYD``.
The exception is an acronym that is also a name word (``meng``,
``edd``): a mask applies in every role, so it gets none, and
``john smith edd`` repairs to ``EDD`` (decisions.md#R4's Excluded
block for CAPITALIZATION_EXCEPTIONS -- meng, edd, lac, ded). A
suffix the writer spelled in more than one case (``EdD``) needs no
entry either: repair keeps it as written unless forced. A caller's
OWN acronym -- one absent from ``suffix_acronyms`` -- depends on how
it is written. Written PLAINLY (``dphil``) it parses as an ordinary
name word and repairs as one (``Dphil``). Written DOTTED
(``d.phil.``) it is a suffix by shape alone, with no vocabulary
entry needed to read it as one, and repairs in all capitals the same
as a listed acronym does (``D.PHIL.``). Either way, a caller who
wants a specific spelling needs a ``suffix_acronyms`` entry
(``Lexicon.add(suffix_acronyms={...})`` in the 2.0 API,
``constants.suffix_acronyms.add(...)`` in the v1 one) or a mask of
its own.
"""


# Keys only -- the values are case masks, cased on purpose.
assert_normalized("CAPITALIZATION_EXCEPTIONS", CAPITALIZATION_EXCEPTIONS)
