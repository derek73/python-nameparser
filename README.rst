Name Parser
===========

|Build Status| |PyPI| |PyPI version| |Documentation| |License| |Downloads| |Codecov|

nameparser parses human names into seven fields — title, given, middle,
family, suffix, nickname, maiden. Results are immutable, configuration is
composable, and locale packs are opt-in.

📣 **nameparser 3.1 reads lists of names, not just one name at a
time.** ``Parser.suggest()`` reads a list from one source and returns a
parser configured for how it is written (its name order, its
patronymics, and family names written as letters or in capitals), and
``Parser.matching()``
groups and compares names from several sources. `Getting started
<https://nameparser.readthedocs.io/en/latest/getting-started.html>`__
takes you through both. 3.0 removed ``HumanName`` and the rest of the
1.x compatibility layer: `Coming from 1.x or 2.x`_ below says where to
start. The `release log
<https://nameparser.readthedocs.io/en/latest/release_log.html>`__ has
the details. Please `open an
issue <https://github.com/derek73/python-nameparser/issues>`__ for anything
that parses wrong.

Chinese, Japanese and Korean names written in their own scripts are read
family-first (save a name in katakana alone, often a transcribed foreign
name), unspaced Korean names are split against the census surname
list, and CJK honorifics are recognized. See `East Asian names
<https://nameparser.readthedocs.io/en/latest/east-asian.html>`__.

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

A language pack reads the conventions of a language you know your data
is in, such as two family names in Spanish or the patronymic in
Russian; see `Locale packs
<https://nameparser.readthedocs.io/en/latest/locales.html>`__ and
`Notes by language
<https://nameparser.readthedocs.io/en/latest/languages.html>`__.

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
    >>> locales.available()
    ('ar', 'bn', 'cs', 'es', 'es_ar', 'ga', 'gd', 'he', 'hi', 'hr', 'ja', 'mn', 'ne', 'pt', 'pt_br', 'ru', 'sk', 'sl', 'tr_az', 'vi', 'zh')

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

Learn more
----------

* `Getting started <https://nameparser.readthedocs.io/en/latest/getting-started.html>`__ — parse a name, let a list choose the settings, match names across sources
* `Working with a parsed name <https://nameparser.readthedocs.io/en/latest/usage.html>`__ — aggregate views, rendering, comparison, ambiguities, tokens, corrections
* `Names the parser reads <https://nameparser.readthedocs.io/en/latest/shapes.html>`__ — the input forms it reads without configuration
* `Settings for a list of names <https://nameparser.readthedocs.io/en/latest/suggest.html>`__ and `Matching names across sources <https://nameparser.readthedocs.io/en/latest/matching.html>`__ — the two list features in full
* `Customizing the parser <https://nameparser.readthedocs.io/en/latest/customize.html>`__ (vocabulary) and `Behavior: Policy <https://nameparser.readthedocs.io/en/latest/policy.html>`__ (behavior)
* `Locale packs <https://nameparser.readthedocs.io/en/latest/locales.html>`__ — opt-in bundles for East Slavic patronymics, Turkic markers, Spanish double surnames, and more
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
  already loaded it, loads the reading index, about two thirds of the cost:
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

Some of the vocabulary nameparser ships is derived from data published
under other licences, which apply to those parts:

- the familiar forms from Old Dominion University's nicknames list:
  Apache License 2.0, in ``LICENSE-nicknames``;
- ``locales.ES`` and ``locales.ES_AR``'s given names from Spain's
  Instituto Nacional de Estadística: Creative Commons Attribution 4.0,
  credited in ``nameparser/locales/_es_given_names.py`` and
  ``_es_ar_given_names.py``;
- part of ``locales.ZH``'s surnames from Taiwan's Ministry of the
  Interior: Open Government Data License, version 1, credited in
  ``nameparser/locales/zh.py``.

The package's licence expression is
``LGPL-2.1-or-later AND Apache-2.0 AND CC-BY-4.0 AND OGDL-Taiwan-1.0``.

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
