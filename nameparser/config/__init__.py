"""The default vocabulary's data.

:mod:`~nameparser.config.surnames` is the one public module: the Korean
surname list unspaced hangul is divided on, a segmentation list outside
the per-word model. The rest of the vocabulary is written per word in
``nameparser/vocab/*.toml`` and compiled into private modules here,
which :class:`nameparser.Lexicon` reads; ask a lexicon what it holds
with :meth:`~nameparser.Lexicon.words` and
:meth:`~nameparser.Lexicon.readings_of`. Through 2.x this package also
held one re-exporting module per word list (``titles``, ``particles``,
``suffixes``, ...) and the compiled patterns in ``regexes``, removed in
3.0 (#1007, #1008), and the 1.x ``Constants`` configuration, removed in
3.0 too (decisions/3-0-reevaluations).
"""
