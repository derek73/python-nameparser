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

Most packs choose languages, and a choice turns on the readings the
chosen language holds and the default leaves off. ``Lady`` is a British
title and, in Spanish-speaking Latin America, a given name; the Spanish
choice reads the given name, the title staying one inside a phrase:

.. code-block:: python

    >>> parse("Lady Heidenreich").title
    'Lady'
    >>> spanish.parse("Lady Heidenreich").given
    'Lady'
    >>> spanish.parse("Lady Justice Jane Smith").title
    'Lady Justice'

A `strict choice
<https://nameparser.readthedocs.io/en/latest/locales.html#reading-one-language-only>`__
reads only the chosen languages' words, the words every language
shares, and words written in a script other than Latin, so the English
title phrase is no longer one:

.. code-block:: python

    >>> strict = parser_for(locales.ES, strict=True)
    >>> strict.parse("Lady Justice Jane Smith").title
    ''

A pack can also take a reading out. Vietnamese written without its
diacritics meets the Dutch particle ``van``, which chains onto the given
name under a family-first order. The Vietnamese pack reads family-first
and removes the particle reading, so ``Van`` stays a middle name:

.. code-block:: python

    >>> from nameparser import FAMILY_FIRST_GIVEN_LAST
    >>> ordered = Parser(policy=Policy(name_order=FAMILY_FIRST_GIVEN_LAST))
    >>> ordered.parse("Nguyen Van Anh").given     # van, Dutch, chains on
    'Van Anh'
    >>> vietnamese = parser_for(locales.VI)
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
    >>> parse("طارق عبد العزيز").family           # عبد + a name of God is one name
    'عبد العزيز'
    >>> parse("نوال عبد هاشم").family             # هاشم is not one, so it stands alone
    'هاشم'

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
    ('bn', 'cs', 'es', 'es_ar', 'ga', 'gd', 'hi', 'hr', 'ja', 'ne', 'pt', 'pt_br', 'ru', 'sk', 'sl', 'tr_az', 'vi', 'zh')

When a reading is wrong for your data
-------------------------------------

Each reading comes from a word's readings in the vocabulary or from a
``Policy`` setting, and you can change both. Ask the vocabulary what a word
may be read as, then add or remove readings and hand the new ``Lexicon``
to a ``Parser``:

.. code-block:: python

    >>> from nameparser import Lexicon
    >>> [r.kind for r in Lexicon.default().readings_of("dean")]
    ['office', 'given', 'family']
    >>> deans = Lexicon.default().remove("dean", kind="given")    # Dean is always a title
    >>> Parser(lexicon=deans).parse("Dean Smith").title
    'Dean'
    >>> leed = Lexicon.default().add("leed", "ap", kind="credential")
    >>> Parser(lexicon=leed).parse("John Smith LEED AP").suffix
    'LEED AP'

A ``Policy`` says how positions are read, such as which name comes
first:

.. code-block:: python

    >>> from nameparser import FAMILY_FIRST
    >>> hungarian = Parser(policy=Policy(name_order=FAMILY_FIRST))
    >>> nagy = hungarian.parse("Nagy Ádám")
    >>> nagy.given, nagy.family
    ('Ádám', 'Nagy')

A ``Lexicon`` and a ``Policy`` are frozen, so each change returns a new
object and nothing is shared between parsers.

Learn more
----------

* `Using the parser <https://nameparser.readthedocs.io/en/latest/usage.html>`__ — the full tour: input shapes, aggregates, rendering, comparison, ambiguities, tokens
* `Customizing the parser <https://nameparser.readthedocs.io/en/latest/customize.html>`__ — vocabulary, behavior, and presentation
* `Locale packs <https://nameparser.readthedocs.io/en/latest/locales.html>`__ — opt-in bundles for East Slavic patronymics, Turkic markers, and more
* There's also a CLI: ``python -m nameparser --json "Doe, John"``

How well it reads names
-----------------------

Measured 2026-11-05 against the 3.0 development tree, by comparing each
reading with the boxes the name was filed in. That is agreement with
someone else's convention, not ground truth, after folding case,
periods, commas and spacing:

* **US patent inventors** (PatentsView, 657,991 distinct name-and-country
  records, split into two boxes by the filing attorney): both boxes agree
  for 94.7%, and for 98.0% outside Spanish- and Portuguese-speaking
  countries.
* **UK company filings** (people with significant control, 1,039,144
  records typed into title, forename, middle and surname boxes): all four
  agree for 96.8%.
* **Czech election candidates** (170,181, with degrees before and after
  the name): all four boxes agree for 97.0%, and for 97.5% with
  ``locales.CS``.

Most of what the default misses is a convention rather than a misreading.
It reads one family name, so a Spanish double surname comes out differently
from how its bearer files it. Choosing the language closes most of the gap:
for ORCID researchers in Spain, ``parser_for(locales.ES)`` lifts agreement
from 49.5% to 96.7% (Mexico 33.6% to 96.9%). The pack costs where people
file a single surname: Argentine patent inventors agree 93.8% by default,
86.2% under ``ES`` and 92.7% under ``ES_AR``.

Speed and testing
-----------------

* **About 90 µs a name**, some 11,000 names a second. Measured
  2026-11-07 against the 3.0 development tree, on an Apple M3 Pro, one
  core, Python 3.11, with one ``Parser`` reading the 7,106 entries of
  the committed `corpus snapshot`_ (6,897 distinct names, some read
  under more than one name order), the median of seven passes after a
  warm-up.
* **Linear in the input, on the shapes the scaling tests repeat.** The
  clock-timed ones ran 32 costly input shapes on 2026-11-07, each with
  its repeated part four times as long, and fail when the cost grows
  more than six times.
* **Pure Python, with no runtime dependencies.** Only the optional
  ``ja`` extra adds any: namedivider-python and what it brings (numpy,
  pandas, scipy and lightgbm among them), for dividing unspaced Japanese kanji names.
* **Build one Parser and reuse it.** The first parser for a choice of
  languages in a process compiles the choice and, unless a parse has
  already loaded it, the reading index, about two thirds of the cost:
  together tens of milliseconds the same day, several hundred parses.
  Another choice after it took a few milliseconds, and a later
  build of the same choice about 1 ms. Its ``Lexicon`` and
  ``Policy`` are frozen and a parse never writes to them, so one parser
  can be shared across threads without locking, and it pickles for
  ``multiprocessing``. A segmenter you supply has to be thread-safe and
  picklable too, and the ``ja`` extra's segmenter does not pickle.

And the tests that hold the readings in place:

* **40,256 tests** (collected 2026-11-07), run in CI on each of Python
  3.11 through 3.15, save the 25 that need the ``ja`` extra, which a job
  with the extra installed runs with the rest of the 39,652 tests then
  under ``tests/v2/``. Another job runs the suite from a source export
  without nameparser installed.
* **Every corpus name's reading is recorded** in the snapshot, and a
  test fails when the parser reads one differently, so a change that
  moves a reading lists every name it moved in its pull request.
* **Every interactive example runs.** Each one with a ``>>>`` prompt, in
  this README and in the documentation, is a doctest run in CI.
* **The parsing rules** are written down with examples the suite runs, in
  `docs/design/rules <https://github.com/derek73/python-nameparser/tree/master/docs/design/rules>`__.
  Where the parser is known to fall short of a rule, the example carries
  a ``deviates:`` marker naming its issue, and the suite fails once the
  gap closes until the marker comes off.

.. _corpus snapshot: https://github.com/derek73/python-nameparser/blob/master/tools/differential/README.md

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
