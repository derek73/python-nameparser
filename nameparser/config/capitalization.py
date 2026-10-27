# The words, and the vetting notes that stood beside them here, live in
# nameparser/vocab/*.toml: a mask is the
# `cased` property of the word's reading, one per word, and
# tools/vocab/build.py refuses one that does not spell its word's letters
# and digits (#459) before Lexicon ever sees it. Still a plain dict, the
# one vocabulary constant not frozen (AGENTS.md's vocabulary and
# configuration-layer section, "Neither dict was frozen").
from nameparser.config import _compiled

CAPITALIZATION_EXCEPTIONS = _compiled.CAPITALIZATION_EXCEPTIONS
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
``john smith edd`` repairs to ``EDD`` (decisions/vocabulary-exclusions,
CAPITALIZATION_EXCEPTIONS -- meng, edd, lac, ded). A
suffix the writer spelled in more than one case (``EdD``) needs no
entry either: repair keeps it as written unless forced. A caller's
OWN acronym -- one absent from ``suffix_acronyms`` -- depends on how
it is written. Written PLAINLY (``dclinpsy``) it parses as an ordinary
name word and repairs as one (``Dclinpsy``). Written DOTTED
(``d.clinpsy.``) it is a suffix by shape alone, with no vocabulary
entry needed to read it as one, and repairs in all capitals the same
as a listed acronym does (``D.CLINPSY.``). Either way, a caller who
wants a specific spelling needs a ``suffix_acronyms`` entry
(``Lexicon.add(suffix_acronyms={...})`` in the 2.0 API,
``constants.suffix_acronyms.add(...)`` in the v1 one) or a mask of
its own. The map also carries the Irish patronymic particles ``ó``,
``ní`` and ``ua`` (#604): case repair writes a particle in lowercase
(``de la Vega``), Irish writes these capitalized (``Liam Ó Murchú``),
and a mask outranks the particle lowercase (rules/R4).
"""
