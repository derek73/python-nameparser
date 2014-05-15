Name Parser
===========

A simple Python module for parsing human names into their individual
components. The HumanName class splits a name string up into name parts
based on placement in the string and matches against known name pieces
like titles. It joins name pieces on conjunctions and special prefixes to
last names like "del". Titles can be chained together and include conjunctions
to handle titles like "Asst Secretary of State". It can also try to 
correct capitalization.

It attempts the best guess that can be made with a simple, rule-based
approach. It's not perfect, but it gets you pretty far.

**Attributes**

* o.title
* o.first
* o.middle
* o.last
* o.suffix
* o.nickname

Supports 3 different comma placement variations in the input string.

* Title Firstname "Nickname" Middle Middle Lastname Suffix
* Lastname, Title Firstname (Nickname) Middle Middle[,] Suffix [, Suffix]
* Title Firstname M Lastname, Suffix [, Suffix]

**Examples of supported formats**

* Doe-Ray, Col. Jonathan "John" A. Jérôme III
* Dr. Juan Q. Xavier de la Vega II
* Juan Q. Xavier Velasquez y Garcia, Jr.

When there is ambiguity that cannot be resolved by a rule-based approach,
HumanName prefers to handle the most common cases correctly. For example,
"Dean" is not parsed as title because it is more common as a first name.

Unit Tests
------------

.. image:: https://travis-ci.org/derek73/python-nameparser.svg
   :target: https://travis-ci.org/derek73/python-nameparser

Over 100 unit tests with example names. 
`Start a New Issue <https://github.com/derek73/python-nameparser/issues>`_ 
for names that fail and I will try to fix it. Let me know if you have
any suggestions for ways the library could be easier to use or modify. 


Installation
------------

``pip install nameparser``

I usually push changes to `PyPi <https://pypi.python.org/pypi/nameparser>`_
pretty quickly. If you want to try out the latest code from GitHub you can
install with pip using the command below.

``pip install -e git+git://github.com/derek73/python-nameparser.git#egg=nameparser``

If you're looking for a web service, check out
`eyeseast's nameparse service <https://github.com/eyeseast/nameparse>`_, a
simple Heroku-friendly Flask wrapper for this module.

Usage
-----
::

    >>> from nameparser import HumanName
    >>> name = HumanName("Dr. Juan Q. Xavier de la Vega III")
    >>> name.title
    u'Dr.'
    >>> name.first
    u'Juan'
    >>> name.middle
    u'Q. Xavier'
    >>> name.last
    u'de la Vega'
    >>> name.suffix
    u'III'
    >>> name.full_name = 'Doe-Ray, Col. Jonathan "John" A. Jérôme III'
    >>> name.title
    u'Col.'
    >>> name.first
    u'John'
    >>> name.middle
    u'A. Jérôme'
    >>> name.last
    u'Doe-Ray'
    >>> name.suffix
    u'III'
    >>> name.nickname
    u'John'
    >>> name.full_name = "Juan Q. Xavier Velasquez y Garcia, Jr."
    >>> name.title
    u''
    >>> name.first
    u'Juan'
    >>> name.middle
    u'Q. Xavier'
    >>> name.last
    u'Velasquez y Garcia'
    >>> name.suffix
    u'Jr.'
    >>> name.middle = "Jason Alexander"
    >>> name.middle
    u'Jason Alexander'
    >>> name
    <HumanName : [
        Title: '' 
        First: 'Juan' 
        Middle: 'Jason Alexander' 
        Last: 'Velasquez y Garcia' 
        Suffix: 'Jr.'
        Nickname: ''
    ]>
    >>> name = HumanName("Dr. Juan Q. Xavier de la Vega III")
    >>> name2 = HumanName("de la vega, dr. juan Q. xavier III")
    >>> name == name2
    True
    >>> len(name)
    5
    >>> list(name)
    ['Dr.', 'Juan', 'Q. Xavier', 'de la Vega', 'III']
    >>> name[1:-1]
    [u'Juan', u'Q. Xavier', u'de la Vega']
    >>> name = HumanName('bob v. de la macdole-eisenhower phd')
    >>> name.capitalize()
    >>> unicode(name)
    u'Bob V. de la MacDole-Eisenhower Ph.D.'
    >>> # Don't touch good names
    >>> name = HumanName('Shirley Maclaine')
    >>> name.capitalize()
    >>> unicode(name) 
    u'Shirley Maclaine'


Capitalization Support
----------------------

The HumanName class can try to guess the correct capitalization of name
entered in all upper or lower case. It will not adjust the case of names
entered in mixed case.

    * bob v. de la macdole-eisenhower phd -> Bob V. de la MacDole-Eisenhower Ph.D.

Handling Nicknames
------------------

The content of parenthesis or double quotes in the name will be
available from the nickname attribute. (Added in v0.2.9)

Output Format
-------------

The format of the strings returned with ``unicode()`` can be adjusted
using standard python string formatting. The string's ``format()``
method will be passed a dictionary of names.

::

    >>> name = HumanName("Rev John A. Kenneth Doe III")
    >>> unicode(name)
    "Rev John A. Kenneth Doe III"
    >>> name.string_format = "{last}, {title} {first} {middle}, {suffix}"
    >>> unicode(name)
    "Doe, Rev John A. Kenneth, III"


HumanName instances will pass an equals (==) test if their lower case
unicode representations are the same. Nicknames and titles are not 
included in the equals test since they do not signify a different 
person.


Customizing the Parser with Your Own Constants
----------------------------------------------

Recognition of titles, prefixes, suffixes and conjunctions is provided
by matching the lower case characters of a name piece with pre-defined
sets located in nameparser.config_. Since everyone's data are a
little bit different, you can easily adjust these predefined sets to
help fine tune the parser for your dataset.

These constants are set at the module level using nameparser.config_.

.. _nameparser.config: https://github.com/derek73/python-nameparser/tree/master/nameparser/config

Predefined Variables
++++++++++++++++++++

These are available via ``from nameparser.config import constants`` or on the ``C`` 
attribute of a ``HumanName`` instance, e.g. ``hn.C``.

* **prefixes**:
  Parts that come before last names, e.g. 'del' or 'van'
* **titles**:
  Parts that come before the first names. Any strings included in
  here will never be considered a first name, so use with care.
* **suffixes**:
  Parts that appear after the last name, e.g. "Jr." or "MD"
* **conjunctions**:
  Parts that are used to join names together, e.g. "and", "y" and "&".
  "of" and "the" are also include to facilitate joining multiple titles,
  e.g. "President of the United States".
* **capitalization_exceptions**:
  Most parts should be capitalized by capitalizing the first letter.
  There are some exceptions, such as roman numbers used for suffixes.
  You can update this with a dictionary or a tuple. 
* **RE**: 
  Contains all the various regular expressions used in the parser.

Each of these predefined sets of variables (except ``RE``) includes ``add()``
and ``remove()`` methods for easy modification. They also inherit from ``set()``
so you can modify them with any methods that work on sets. ``RE`` is a tuple
but can be replaced with a dictionary if you need to modify it.

Any strings you add to the constants should be lower case and not include
periods. The ``add()`` and ``remove()`` method handles that for you
automatically, but other ``set()`` methods will not.

Parser Customization Examples
+++++++++++++++++++++++++++++

"Hon" is a common abbreviation for "Honorable", a title used when addressing
judges. It is also sometimes a first name. If your dataset contains more
"Hon"s than judges, you may wish to remove it from the titles constant so
that "Hon" can be parsed as a first name.

::

    >>> from nameparser import HumanName
    >>> hn = HumanName("Hon Solo")
    >>> hn
    <HumanName : [
    	Title: 'Hon' 
    	First: '' 
    	Middle: '' 
    	Last: 'Solo' 
    	Suffix: ''
    	Nickname: ''
    ]>
    >>> from nameparser.config import constants
    >>> constants.titles.remove('hon')
    >>> hn = HumanName("Hon Solo")
    >>> hn
    <HumanName : [
    	Title: '' 
    	First: 'Hon' 
    	Middle: '' 
    	Last: 'Solo' 
    	Suffix: ''
    	Nickname: ''
    ]>


"Dean" is a common first name, but sometimes it is more common as a title.
If you would like "Dean" to be parsed as a title, simply add it to the
titles constant. 

You can pass multiple strings to both the ``add()`` and ``remove()``
methods and each string will be added or removed.

::

    >>> from nameparser import HumanName
    >>> from nameparser.config import constants
    >>> constants.titles.add('dean', 'Chemistry')
    >>> hn = HumanName("Assoc Dean of Chemistry Robert Johns")
    >>> hn
    <HumanName : [
    	Title: 'Assoc Dean of Chemistry' 
    	First: 'Robert' 
    	Middle: '' 
    	Last: 'Johns' 
    	Suffix: ''
    	Nickname: ''
    ]>


Parser Customizations Are Module-Wide 
+++++++++++++++++++++++++++++

When you modify the configuration, by default this will modify the behavior all
HumanName instances. This could be a handy way to set it up for your entire
project, but it could also lead to some unexpected behavior because changing one
instance could modify the behavior of another instance.

::

    >>> from nameparser import HumanName
    >>> from nameparser.config import constants
    >>> constants.titles.add('dean')
    >>> hn = HumanName("Dean Robert Johns")
    >>> hn
    <HumanName : [
    	Title: 'Dean' 
    	First: 'Robert' 
    	Middle: '' 
    	Last: 'Johns' 
    	Suffix: ''
    	Nickname: ''
    ]>
    >>> hn2 = HumanName("Dean Robert Johns")
    >>> hn2
    <HumanName : [
    	Title: 'Dean' 
    	First: 'Robert' 
    	Middle: '' 
    	Last: 'Johns' 
    	Suffix: ''
    	Nickname: ''
    ]>


If you'd prefer new instances to have their own config values, you can pass
``None`` as the second argument (or ``constant`` keyword argument) when
instantiating ``HumanName``. The instance's constants can be accessed via its
``C`` attribute. 

Note that each instance always has a ``C`` attribute, but if you didn't pass
something falsey to the ``constants`` argument then you'd still be
modifying the module-level config values with the behavior described above.

::

    >>> hn = HumanName("Dean Robert Johns", None)
    >>> hn.C.titles.add('dean')
    >>> hn
    <HumanName : [
    	Title: 'Dean' 
    	First: 'Robert' 
    	Middle: '' 
    	Last: 'Johns' 
    	Suffix: ''
    	Nickname: ''
    ]>
    >>> hn2 = HumanName("Dean Robert Johns")
    >>> hn2
    <HumanName : [
    	Title: '' 
    	First: 'Dean' 
    	Middle: 'Robert' 
    	Last: 'Johns' 
    	Suffix: ''
    	Nickname: ''
    ]>


Contributing
------------

Please let me know if there are ways this library could be restructured to make
it easier for you to use in your projects. Read CONTRIBUTING.md_ for more info.

    https://github.com/derek73/python-nameparser

.. _CONTRIBUTING.md: https://github.com/derek73/python-nameparser/tree/master/CONTRIBUTING.md

Testing
+++++++

Run ``tests.py`` to see if your changes broke anything.

``./tests.py``

You can also pass a string as the first argument to see how a specific
name will be parsed.

::

    $ ./tests.py "Secretary of State Hillary Rodham-Clinton"
    <HumanName : [
    	Title: 'Secretary of State' 
    	First: 'Hillary' 
    	Middle: '' 
    	Last: 'Rodham-Clinton' 
    	Suffix: ''
    ]>
    


Naming Practices and Resources
------------------------------

    * US_Census_Surname_Data_2000_
    * Naming_practice_guide_UK_2006_
    * Wikipedia_Naming_conventions_
    * Wikipedia_List_Of_Titles_

.. _US_Census_Surname_Data_2000: http://www.census.gov/genealogy/www/data/2000surnames/index.html
.. _Naming_practice_guide_UK_2006: https://www.fbiic.gov/public/2008/nov/Naming_practice_guide_UK_2006.pdf
.. _Wikipedia_Naming_conventions: http://en.wikipedia.org/wiki/Wikipedia:Naming_conventions_(people)
.. _Wikipedia_List_Of_Titles: https://en.wikipedia.org/wiki/Title


Release Log
-----------

    * 0.3 - May ?, 2014
        - Refactor configuration to simplify modifications to constants
        - use unicode_literals to simplify Python 2 & 3 support.
    * 0.2.10 - May 6, 2014
        - If name is only a title and one part, assume it's a last name instead of a first name, with exceptions for some titles like 'Sir'. (`#7 <https://github.com/derek73/python-nameparser/issues/7>`_).
        - Add some judicial and other common titles. (#9) 
    * 0.2.9 - Apr 1, 2014
        - Add a new nickname attribute containing anything in parenthesis or double quotes (`Issue 33 <https://code.google.com/p/python-nameparser/issues/detail?id=33>`_).
    * 0.2.8 - Oct 25, 2013
        - Add support for Python 3.3+. Thanks to @corbinbs.
    * 0.2.7 - Feb 13, 2013
        - Fix bug with multiple conjunctions in title
        - add legal and crown titles
    * 0.2.6 - Feb 12, 2013
        - Fix python 2.6 import error on logging.NullHandler
    * 0.2.5 - Feb 11, 2013
        - Set logging handler to NullHandler
        - Remove 'ben' from PREFIXES because it's more common as a name than a prefix.
        - Deprecate BlankHumanNameError. Do not raise exceptions if full_name is empty string. 
    * 0.2.4 - Feb 10, 2013
        - Adjust logging, don't set basicConfig. Fix `Issue 10 <https://code.google.com/p/python-nameparser/issues/detail?id=10>`_ and `Issue 26 <https://code.google.com/p/python-nameparser/issues/detail?id=26>`_.
        - Fix handling of single lower case initials that are also conjunctions, e.g. "john e smith". Re `Issue 11 <https://code.google.com/p/python-nameparser/issues/detail?id=11>`_.
        - Fix handling of initials with no space separation, e.g. "E.T. Jones". Fix #11.
        - Do not remove period from first name, when present.
        - Remove 'e' from PREFIXES because it is handled as a conjunction.
        - Python 2.7+ required to run the tests. Mark known failures.
        - tests/test.py can now take an optional name argument that will return repr() for that name.
    * 0.2.3 - Fix overzealous "Mac" regex
    * 0.2.2 - Fix parsing error
    * 0.2.0 
        - Significant refactor of parsing logic. Handle conjunctions and prefixes before
          parsing into attribute buckets.
        - Support attribute overriding by assignment.
        - Support multiple titles. 
        - Lowercase titles constants to fix bug with comparison. 
        - Move documentation to README.rst, add release log.
    * 0.1.4 - Use set() in constants for improved speed. setuptools compatibility - sketerpot
    * 0.1.3 - Add capitalization feature - twotwo
    * 0.1.2 - Add slice support

