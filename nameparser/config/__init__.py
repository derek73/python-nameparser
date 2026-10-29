"""The default vocabulary: one data module per word list.

The modules here (:mod:`~nameparser.config.titles`,
:mod:`~nameparser.config.particles`, ...) are the word lists
:meth:`nameparser.Lexicon.default` is built from, named for its fields
since 2.2 (#293). All but ``surnames.py`` re-export sets compiled from
the per-word TOML files in ``nameparser/vocab/`` (#737). Through 2.x
this package also held the 1.x ``Constants`` configuration, removed in
3.0; the data modules stay (decisions/3-0-reevaluations).
"""
