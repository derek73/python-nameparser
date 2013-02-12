Name Parser
===========

A simple Python module for parsing human names into their individual components.

**Attributes**

    * HumanName.title
    * HumanName.first
    * HumanName.middle
    * HumanName.last
    * HumanName.suffix

Supports 3 comma placement variations for names of people in latin-based languages. 

    * Title Firstname Middle Middle Lastname Suffix
    * Lastname, Title Firstname Middle Middle[,] Suffix [, Suffix]
    * Title Firstname M Lastname, Suffix [, Suffix]

Examples:

    * Doe-Ray, Col. John A. Jérôme III
    * Dr. Juan Q. Xavier de la Vega II
    * Juan Q. Xavier Velasquez y Garcia, Jr.


Capitalization Support
----------------------

The HumanName class can try to guess the correct capitalization of name entered in all upper or lower case. It will not adjust the case of names entered in mixed case.

    * bob v. de la macdole-eisenhower phd -> Bob V. de la MacDole-Eisenhower Ph.D.

Over 100 unit tests with example names. Should be unicode safe but it's fairly untested. `Post a ticket <http://code.google.com/p/python-nameparser/issues/entry>`_ and/or for names that fail and I will try to fix it. 

HumanName instances will pass an equals (==) test if their lower case unicode
representations are the same.

Output Format
-------------

The format of the strings returned with ``unicode()`` can be adjusted using standard python string formatting. The string's ``format(1)`` method will be passed a dictionary of names.

::
    >>> name = HumanName("Rev John A. Kenneth Doe III")
    >>> unicode(name)
    "Rev John A. Kenneth Doe III"
    >>> name.string_format = "{last}, {title} {first} {middle}, {suffix}"
    >>> unicode(name)
    "Doe, Rev John A. Kenneth, III"

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
    >>> name.full_name = "Doe-Ray, Col. John A. Jérôme III"
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


Contributing via Google Code
----------------------------

Feel free to post new issues to the Google Code project. The easiest way to submit changes is to create a clone of the Google project and commit changes to your clone with mercurial. I'll happily pull changes that include tests from any clone. Create your clone here:

    http://code.google.com/p/python-nameparser/source/clones

Then checkout your clone:

    hg clone https://code.google.com/r/your-clone-name

Make your changes, add your tests, then push them to your clone. 

    hp push -b default

Then file a pull request in Google Code. To pull new changes from the canonical repository and apply them to your working directory:

    hg pull -u https://code.google.com/r/python-nameparser

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

    * 0.2.5 - Feb 11, 2013
        - Set logging handler to NullHandler
    * 0.2.4 - Feb 10, 2013
        - Adjust logging, don't set basicConfig. Fix #10 and #26.
        - Fix handling of single lower case initials that are also conjunctions, e.g. "john e smith". Re #11.
        - Fix handling of initials with no space separation, e.g. "E.T. Jones". Fix #11.
        - Do not remove period from first name, when present.
        - Remove 'ben' from PREFICES because it's more common as a name than a prefix.
        - Remove 'e' from PREFICES because it is handled as a conjunction.
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

