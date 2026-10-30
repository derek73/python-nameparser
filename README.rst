Name Parser
===========

|Build Status| |PyPI| |PyPI version| |Documentation| |License| |Downloads| |Codecov|

nameparser parses human names into seven fields — title, given, middle,
family, suffix, nickname, maiden. Results are immutable, configuration is
composable, and locale packs are opt-in.

📣 **nameparser 3.0 removes HumanName and the rest of the 1.x
compatibility layer.** ``HumanName``, ``Constants``, the shared
``CONSTANTS`` and ``nameparser.util`` are gone, along with the 1.x
names of the word lists; ``parse()`` and ``Parser`` are the
replacement. 2.8 is the last release that has them, and it warns at
each use 3.0 removes; `Coming from 1.x or 2.x`_ below says where to
start. The `release log
<https://nameparser.readthedocs.io/en/latest/release_log.html>`__ has
the details. Please `open an
issue <https://github.com/derek73/python-nameparser/issues>`__ for anything
that parses wrong.

Chinese, Japanese and Korean names written in their own scripts are read
family-first, unspaced Korean names are split against the census surname
list, and CJK honorifics are recognized. See `East Asian names
<https://nameparser.readthedocs.io/en/latest/usage.html#east-asian-names>`__.

Installation
------------

::

  pip install nameparser

Requires Python 3.11+.

Quick Start Example
--------------------

.. code-block:: python

    >>> from nameparser import parse
    >>> name = parse("Dr. Juan Q. Xavier de la Vega III (Doc Vega)")
    >>> name
    <ParsedName: [
        title: 'Dr.'
        given: 'Juan'
        middle: 'Q. Xavier'
        family: 'de la Vega'
        suffix: 'III'
        nickname: 'Doc Vega'
    ]>
    >>> name.family_base, name.family_particles
    ('Vega', 'de la')
    >>> name.given_names, name.surnames
    ('Juan Q. Xavier', 'Q. Xavier de la Vega')
    >>> name.render("{family}, {given}")
    'de la Vega, Juan'

    >>> parse("Jack MA").suffix                    # capitals mark a credential
    'MA'
    >>> parse("Jack Ma").family                    # and a surname
    'Ma'
    >>> parse("Jane Smith, PhD MA").suffix
    'PhD MA'

    >>> parse("김민준").family                     # Korean: unspaced, split on the census list
    '김'
    >>> parse("高橋 みなみ").family                 # Japanese: kanji with kana, family first
    '高橋'
    >>> parse("김민준씨").suffix                   # an honorific written against the name
    '씨'
    >>> parse("г-н Иван Петров").title             # Cyrillic title
    'г-н'
    >>> parse("محمد بن سلمان").family              # Arabic: بن chains onto the family name
    'بن سلمان'

    >>> from nameparser import locales, parser_for
    >>> chinese = parser_for(locales.ZH)           # Han text does not say which language
    >>> chinese.parse("毛泽东").family              # so splitting it is opt-in
    '毛'
    >>> russian = parser_for(locales.RU)
    >>> russian.parse("Сидоров Иван Петрович").family
    'Сидоров'
    >>> locales.available()
    ('cs', 'hr', 'ja', 'ne', 'ru', 'sk', 'sl', 'tr_az', 'zh')

Learn more
----------

* `Using the parser <https://nameparser.readthedocs.io/en/latest/usage.html>`__ — the full tour: input shapes, aggregates, rendering, comparison, ambiguities, tokens
* `Customizing the parser <https://nameparser.readthedocs.io/en/latest/customize.html>`__ — vocabulary, behavior, and presentation
* `Locale packs <https://nameparser.readthedocs.io/en/latest/locales.html>`__ — opt-in bundles for East Slavic patronymics, Turkic markers, and more
* There's also a CLI: ``python -m nameparser --json "Doe, John"``

Coming from 1.x or 2.x
----------------------

3.0 has no ``HumanName``: ``parse(text)`` reads the same seven fields,
named ``given`` and ``family`` where ``HumanName`` had ``first`` and
``last``, and a ``Lexicon`` and ``Policy`` handed to a ``Parser``
replace ``Constants``. Upgrade to 2.8 first and run your tests under
``python -W error::DeprecationWarning``: it stops at every use 3.0
removes except a read of the shared ``CONSTANTS`` and the imports
`Migrating to 3.0`_ lists, which 2.8 does not warn on, so search for
those too. A pickled ``HumanName`` or
``Constants`` does not load in 3.0; store ``parse(text).as_dict()`` or
the original string instead.
`Migrating to 3.0`_ maps ``HumanName``'s attributes and the
``Constants`` settings onto the 3.0 API.

.. _Migrating to 3.0: https://nameparser.readthedocs.io/en/latest/migrate.html

License
-------

LGPL licensed. See `LICENSE <https://github.com/derek73/python-nameparser/blob/master/LICENSE>`__
for details.

.. |Build Status| image:: https://github.com/derek73/python-nameparser/actions/workflows/python-package.yml/badge.svg
   :target: https://github.com/derek73/python-nameparser/actions/workflows/python-package.yml
.. |PyPI| image:: https://img.shields.io/pypi/v/nameparser.svg
   :target: https://pypi.org/project/nameparser/
.. |Documentation| image:: https://readthedocs.org/projects/nameparser/badge/?version=latest
   :target: http://nameparser.readthedocs.io/en/latest/?badge=latest
.. |PyPI version| image:: https://img.shields.io/pypi/pyversions/nameparser.svg
   :target: https://pypi.org/project/nameparser/
.. |License| image:: https://img.shields.io/pypi/l/nameparser.svg
   :target: https://pypi.org/project/nameparser/
.. |Downloads| image:: https://static.pepy.tech/badge/nameparser
   :target: https://pepy.tech/project/nameparser
.. |Codecov| image:: https://codecov.io/gh/derek73/python-nameparser/branch/master/graph/badge.svg
   :target: https://codecov.io/gh/derek73/python-nameparser
