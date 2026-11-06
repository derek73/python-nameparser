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
start. 3.0 also configures a ``Lexicon`` `by reading
<https://nameparser.readthedocs.io/en/latest/customize.html#configuring-by-reading>`__
(``Lexicon.default().add("leed", kind="credential")``), renders a name
in the order it was written (``str(parse("김민준"))`` is ``'김민준'``),
and adds packs that choose the languages a parse reads. The `release log
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
    >>> name = parse("Dr. Juan Carlos García de la Vega III (Juanca)")
    >>> name
    <ParsedName: [
        title: 'Dr.'
        given: 'Juan'
        middle: 'Carlos García'
        family: 'de la Vega'
        suffix: 'III'
        nickname: 'Juanca'
    ]>
    >>> name.family_base, name.family_particles
    ('Vega', 'de la')

A Spanish name usually ends in two family names, the father's first and
the mother's second. Out of the box the parser reads one family name,
with the words between it and the given name as middle names. The
Spanish pack reads the two family names and gives each its own view:

.. code-block:: python

    >>> from nameparser import Parser, Policy, locales, parser_for
    >>> spanish = parser_for(locales.ES)
    >>> juan = spanish.parse("Dr. Juan Carlos García de la Vega III (Juanca)")
    >>> juan.middle, juan.family
    ('Carlos', 'García de la Vega')
    >>> juan.surname1, juan.surname2, juan.generation
    ('García', 'de la Vega', 'III')
    >>> juan.render("{family}, {given}")
    'García de la Vega, Juan'

Juan Carlos may also be one compound given name. Nothing in the text
says which, so reading it that way is a switch for data you know is
written so:

.. code-block:: python

    >>> compound = parser_for(locales.ES,
    ...                       base=Parser(policy=Policy(two_given_names=True)))
    >>> compound.parse("Juan Carlos García de la Vega").given
    'Juan Carlos'

Most packs choose languages, and a choice prefers the chosen
language's reading of a word the others read differently. ``Lady`` is a
British title and, across Latin America, a given name:

.. code-block:: python

    >>> parse("Lady Heidenreich").title
    'Lady'
    >>> spanish.parse("Lady Heidenreich").given
    'Lady'

A `strict choice
<https://nameparser.readthedocs.io/en/latest/locales.html#reading-one-language-only>`__
reads only the chosen languages' words and those every language
shares. Vietnamese written without its diacritics meets the Dutch
particle ``van``, which the strict choice drops:

.. code-block:: python

    >>> from nameparser import FAMILY_FIRST_GIVEN_LAST, Lexicon, Locale
    >>> ordered = Parser(policy=Policy(name_order=FAMILY_FIRST_GIVEN_LAST))
    >>> ordered.parse("Nguyen Van Anh").given     # van, Dutch, chains on
    'Van Anh'
    >>> vi = Locale(code="vi", lexicon=Lexicon.empty(),
    ...             languages=frozenset({"vi"}))
    >>> vietnamese = parser_for(vi, base=ordered, strict=True)
    >>> anh = vietnamese.parse("Nguyen Van Anh")
    >>> anh.family, anh.middle, anh.given
    ('Nguyen', 'Van', 'Anh')

More shapes the parser reads:

.. code-block:: python

    >>> parse("The Rt Hon Sir John Smith KCB MP").title    # a run of titles
    'The Rt Hon Sir'
    >>> parse("Dean Smith").given                   # alone, Dean is a given name
    'Dean'
    >>> parse("Associate Dean Jane Smith").title    # in a title phrase, a title
    'Associate Dean'
    >>> listed = parse("Smith, John V., Jr., MD, PhD")    # listing form
    >>> listed.middle, listed.generation, listed.credentials
    ('V.', 'Jr.', 'MD, PhD')
    >>> parse("Jack MA").suffix                    # capitals mark a credential
    'MA'
    >>> parse("Jack Ma").family                    # and a surname
    'Ma'
    >>> dutch = parse("Berg, Jan van der")          # Dutch index form, particles last
    >>> dutch.given, dutch.family
    ('Jan', 'van der Berg')
    >>> parse("Van Johnson").ambiguities           # a guess is reported
    (Ambiguity('particle-or-given': 'Van'),)
    >>> van = parse("Ludwig van Beethoven").tokens[1]
    >>> van.reading.languages                    # the vocabulary that read "van"
    ('nl',)

    >>> parse("김민준").family                     # Korean: unspaced, split on the census list
    '김'
    >>> parse("高橋 みなみ").family                 # Japanese: kanji with kana, family first
    '高橋'
    >>> parse("김민준씨").honorifics               # an honorific written against the name
    '씨'
    >>> parse("г-н Иван Петров").title             # Cyrillic title
    'г-н'
    >>> arabic = parse("محمد بن سلمان")            # Arabic: بن chains onto the family name
    >>> arabic.family, arabic.patronymic          # and marks it a patronymic
    ('بن سلمان', 'بن سلمان')

    >>> chinese = parser_for(locales.ZH)           # Han text does not say which language
    >>> chinese.parse("毛泽东").family              # so splitting it is opt-in
    '毛'
    >>> parse("Сидоров Иван Петрович").given       # read given-first by default
    'Сидоров'
    >>> russian = parser_for(locales.RU)           # the Russian pack reads the patronymic
    >>> ivan = russian.parse("Сидоров Иван Петрович")
    >>> ivan.given, ivan.patronymic, ivan.family
    ('Иван', 'Петрович', 'Сидоров')
    >>> locales.available()
    ('bn', 'cs', 'es', 'es_ar', 'ga', 'gd', 'hi', 'hr', 'ja', 'ne', 'pt', 'pt_br', 'ru', 'sk', 'sl', 'tr_az', 'zh')

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
replace ``Constants``. Upgrade to 2.8.2 first and run your tests under
``python -W error::DeprecationWarning``: it stops at every use 3.0
removes except a read of the shared ``CONSTANTS`` or of a ``Lexicon``
set field and the imports `Migrating to 3.0`_ lists, which 2.8.2 does
not warn on, so search for those too. A pickled ``HumanName`` or
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
