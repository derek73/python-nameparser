Name Parser
===========

|Build Status| |PyPI| |PyPI version| |Documentation| |License| |Downloads| |Codecov|

nameparser parses human names into seven fields — title, given, middle,
family, suffix, nickname, maiden. Results are immutable, configuration is
composable, and locale packs are opt-in.

📣 **nameparser 3.0 removes HumanName and the rest of the 1.x
compatibility layer:**

* ``HumanName``, ``Constants``, the shared ``CONSTANTS`` and
  ``nameparser.util`` are gone, along with the 1.x names of the word
  lists; ``parse()`` and ``Parser`` are the replacement. 2.8 is the
  last release that has them, and it warns at each use 3.0 removes;
  `Coming from 1.x or 2.x`_ below says where to start.
* 3.0 also configures a ``Lexicon`` `by reading
  <https://nameparser.readthedocs.io/en/latest/customize.html#configuring-by-reading>`__
  (``Lexicon.default().add("leed", kind="credential")``), renders a
  name in the order it was written (``str(parse("김민준"))`` is
  ``'김민준'``), and adds packs that choose the languages a parse reads.

📣 **nameparser 3.1 adds two tools for working with lists of names:**

* ``Parser.suggest()`` reads a list from one source and returns a
  parser configured for how it is written: its name order, its
  patronymics, and family names written as letters or in capitals.
* ``Parser.matching()`` groups and compares names from several sources.

`Getting started
<https://nameparser.readthedocs.io/en/latest/getting-started.html>`__
takes you through both, and the `release log
<https://nameparser.readthedocs.io/en/latest/release_log.html>`__ has
the details. Please `open an issue
<https://github.com/derek73/python-nameparser/issues>`__ for anything
that parses wrong.

Installation
------------

::

  pip install nameparser

Requires Python 3.11+.

Getting started
---------------

**Parse one name** into its fields:

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

**Have a list of names from one source?** A single name often cannot show
which word is the family name (in ``Taylor Morgan`` either word could
be), but a list written one way can. ``suggest()`` reads the list and
returns a parser that reads it, with the evidence for each setting it
considered:

.. code-block:: python

    >>> from nameparser import Parser
    >>> listing = ["Taylor Morgan", "Kim Minjun", "Wang Xiaoming",
    ...            "Nguyen Anh", "Garcia Emily"]
    >>> suggestion = Parser().suggest(listing)
    >>> suggestion.patch
    PolicyPatch(name_order=FAMILY_FIRST)
    >>> suggestion.parser.parse("Taylor Morgan").given
    'Morgan'

``Taylor Morgan`` carries no evidence of its own; it is read family
first because the rest of the list is.

**Joining records from several sources?** ``matching()`` gives each
name keys to group records by, and checks a pair field by field:

.. code-block:: python

    >>> matcher = Parser().matching()
    >>> sorted(matcher.keys("Jane A. de la Vega"))
    ['delavega;j', 'vega;j']
    >>> pair = matcher.check("John A. Smith", "J. Smith")
    >>> pair.consistent, pair["given"].outcome.value
    (True, 'initial')
    >>> matcher.check("Jane Smith", "John Smith").consistent
    False

More shapes the parser reads
----------------------------

**Titles, suffixes and commas.** Runs of titles, listing forms and
credentials are read without configuration; a guess is reported, and a
word the vocabulary read says which languages' vocabulary it came from:

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

**Other scripts.** The default vocabulary reads titles, honorifics and
particles in several scripts besides Latin. Chinese, Japanese and
Korean names written in their own scripts are read family-first (save a
name in katakana alone, often a transcribed foreign name), unspaced
Korean names are split against the census surname list, and CJK
honorifics are recognized (see `East Asian names
<https://nameparser.readthedocs.io/en/latest/east-asian.html>`__). Thai
writes a salutation joined to the given name with no space, and the
parser splits it off, with no configuration (see `Thai names
<https://nameparser.readthedocs.io/en/latest/languages.html#thai-names>`__).

.. code-block:: python

    >>> parse("김민준").family                     # Korean: unspaced, split on the census list
    '김'
    >>> parse("高橋 みなみ").family                 # Japanese: kanji with kana, family first
    '高橋'
    >>> parse("김민준씨").honorifics               # an honorific written against the name
    '씨'
    >>> thai = parse("นายสมชาย ใจดี")              # Thai: the salutation is written joined to
    >>> thai.title, thai.given, thai.family       # the given name, and is split off it
    ('นาย', 'สมชาย', 'ใจดี')
    >>> parse("г-н Иван Петров").title             # Cyrillic title
    'г-н'
    >>> arabic = parse("محمد بن سلمان")            # Arabic: بن chains onto the family name
    >>> arabic.family, arabic.patronymic          # and marks it a patronymic
    ('بن سلمان', 'بن سلمان')
    >>> parse("طارق عبد العزيز").family           # عبد + a name of God is one name
    'عبد العزيز'
    >>> parse("نوال عبد هاشم").family             # هاشم is not one, so it stands alone
    'هاشم'

**Language packs.** The parser never guesses a name's language, so the
conventions of one language are opt-in: a pack reads them when you know
the language your data is in, such as two family names in Spanish or
the patronymic in Russian. See `Locale packs
<https://nameparser.readthedocs.io/en/latest/locales.html>`__ and
`Notes by language
<https://nameparser.readthedocs.io/en/latest/languages.html>`__.

.. code-block:: python

    >>> from nameparser import locales, parser_for
    >>> chinese = parser_for(locales.ZH)           # Han text does not say which language
    >>> chinese.parse("毛泽东").family              # so splitting it is opt-in
    '毛'
    >>> parse("Сидоров Иван Петрович").given       # read given-first by default
    'Сидоров'
    >>> russian = parser_for(locales.RU)           # the Russian pack reads the patronymic
    >>> ivan = russian.parse("Сидоров Иван Петрович")
    >>> ivan.given, ivan.patronymic, ivan.family
    ('Иван', 'Петрович', 'Сидоров')
    >>> locales.available()                        # every pack that ships
    ('ar', 'bn', 'cs', 'es', 'es_ar', 'ga', 'gd', 'he', 'hi', 'hr', 'ja', 'mn', 'ms', 'my', 'ne', 'nl', 'pt', 'pt_br', 'pt_pt', 'ru', 'sk', 'sl', 'tr_az', 'vi', 'zh')

When a reading is wrong for your data
-------------------------------------

Each reading comes from a word's readings in the vocabulary or from a
``Policy`` setting, and you can change both. Ask the vocabulary what a word
may be read as, then add or remove readings and hand the new ``Lexicon``
to a ``Parser``:

.. code-block:: python

    >>> from nameparser import Lexicon, Policy
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

If a name still reads wrong, please `open an issue
<https://github.com/derek73/python-nameparser/issues>`__ with the name
and the reading you expected.

Learn more
----------

* `Getting started <https://nameparser.readthedocs.io/en/latest/getting-started.html>`__ — parse a name, let a list choose the settings, match names across sources
* `Working with a parsed name <https://nameparser.readthedocs.io/en/latest/usage.html>`__ — aggregate views, rendering, comparison, ambiguities, tokens, corrections
* `Names the parser reads <https://nameparser.readthedocs.io/en/latest/shapes.html>`__ — the input forms it reads without configuration
* `Settings for a list of names <https://nameparser.readthedocs.io/en/latest/suggest.html>`__ and `Matching names across sources <https://nameparser.readthedocs.io/en/latest/matching.html>`__ — the two list features in full
* `Customizing the parser <https://nameparser.readthedocs.io/en/latest/customize.html>`__ (vocabulary) and `Behavior: Policy <https://nameparser.readthedocs.io/en/latest/policy.html>`__ (behavior)
* `Locale packs <https://nameparser.readthedocs.io/en/latest/locales.html>`__ — opt-in bundles for East Slavic patronymics, Turkic markers, Spanish double surnames, and more
* There's also a CLI: ``python -m nameparser --json "Doe, John"``

Coming from 1.x or 2.x
----------------------

3.0 has no ``HumanName``: ``parse(text)`` reads the same seven fields,
named ``given`` and ``family`` where ``HumanName`` had ``first`` and
``last``, and a ``Lexicon`` and ``Policy`` handed to a ``Parser``
replace ``Constants``. To find what your code has to change:

1. Upgrade to 2.8.2, which warns of most of what 3.0 removes.
2. Run your tests under ``python -W error::DeprecationWarning``. The run
   stops at each use 3.0 removes, except the ones 2.8.2 does not warn
   on.
3. Search your code by hand for those: a read of the shared
   ``CONSTANTS``, a read of a ``Lexicon`` set field, and the imports
   `Finding the sites`_ lists.

A pickled ``HumanName`` or ``Constants`` does not load in 3.0; store
``parse(text).as_dict()`` or the original string instead.
`Migrating to 3.0`_ maps ``HumanName``'s attributes and the
``Constants`` settings onto the 3.0 API.

.. _Migrating to 3.0: https://nameparser.readthedocs.io/en/latest/migrate.html
.. _Finding the sites: https://nameparser.readthedocs.io/en/latest/migrate.html#finding-the-sites

How well it reads names
-----------------------

These figures give a general idea of what to expect and of how much a
setting can change it. Each compares the parser's fields with the boxes
a name was filed in on one large public dataset, after folding case,
periods, commas and spacing. That is agreement with someone else's
convention and not ground truth, so they will differ for every dataset
and yours will probably match none of them.

* **US patent inventors**, at most 20,000 from each country, filed in a
  given-name and a family-name box:
  both agree for about 95% of names, and for about 98% outside Spanish-
  and Portuguese-speaking countries.
* **UK company filings**, typed into title, forename, middle-name and
  surname boxes: all four agree for about 97%.
* **Czech election candidates**, with degrees before and after the
  name: all four boxes agree for about 97%.
* **Choosing the language** closes most of the gap. Most of what the
  default misses is a convention rather than a misreading: it reads
  one family name, so for researchers in
  Spain it agrees with the two boxes of their ORCID record for about
  half of the names, and ``parser_for(locales.ES)`` for about 97%. The
  Spanish pack costs where people file a single surname: Argentine patent
  inventors agree for about 94% by default, 86% under ``ES`` and 93%
  under ``ES_AR``.

Speed and testing
-----------------

* **Pure Python, with no runtime dependencies.** Only the optional
  ``ja`` extra adds any: namedivider-python and what it brings (numpy,
  pandas, scipy and lightgbm among them), for dividing unspaced
  Japanese kanji names.
* **Build one Parser and reuse it.** The first parser for a choice of
  languages in a process costs tens of milliseconds, another choice
  after it under ten, and building the same choice again about one
  millisecond, some ten parses; a parse costs roughly a tenth of a
  millisecond on a recent laptop.
* **A parser can be shared.** Its ``Lexicon`` and ``Policy`` are frozen
  and a parse never writes to them, so one parser can be shared across
  threads without locking, and it pickles for ``multiprocessing``. A
  segmenter you supply has to be thread-safe and picklable too, and the
  ``ja`` extra's segmenter does not pickle.
* **Every interactive example runs.** Each one with a ``>>>`` prompt, in
  this README and in the documentation, is a doctest run in CI, beside
  a suite of tens of thousands of tests.

The measurements behind this section and the one above, with their
dates, counts and commands, are in the project's `record of README
figures`_.

.. _record of README figures: https://github.com/derek73/python-nameparser/blob/master/docs/design/decisions/readme-figures.md

License
-------

LGPL licensed. See `LICENSE <https://github.com/derek73/python-nameparser/blob/master/LICENSE>`__
for details.

The package's licence expression is ``LGPL-2.1-or-later``. The word
lists it ships are the project's own measurements over public data, and
the sources whose licences ask for credit are credited:

- ``locales.ES`` and ``locales.ES_AR``'s given names, measured on Spain's
  Instituto Nacional de Estadística census tables (Creative Commons
  Attribution 4.0), credited in ``nameparser/locales/_es_given_names.py``
  and ``_es_ar_given_names.py``;
- part of ``locales.ZH``'s surnames, selected from Taiwan's Ministry of
  the Interior surname ranking (Open Government Data License, version 1),
  credited in ``nameparser/locales/zh.py``.

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
