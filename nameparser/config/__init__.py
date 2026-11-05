"""The default vocabulary's data.

Every module here is private, and :class:`nameparser.Lexicon` reads
them: the vocabulary written per word in ``nameparser/vocab/*.toml``,
compiled, and ``_ko_surnames``, the Korean surname list unspaced hangul
is divided on, a segmentation list outside the per-word model, which
``Lexicon.default().surnames`` holds. Ask a lexicon what it holds with
:meth:`~nameparser.Lexicon.words` and
:meth:`~nameparser.Lexicon.readings_of`. Through 2.x this package also
held one re-exporting module per word list (``titles``, ``particles``,
``suffixes``, ...) and the compiled patterns in ``regexes``, removed in
3.0 (#1007, #1008), the public ``surnames``, made private in 3.0, and the 1.x ``Constants`` configuration, removed in
3.0 too (decisions/3-0-reevaluations).
"""
