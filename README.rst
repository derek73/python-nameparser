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

Over 100 unit tests with example names. Should be unicode safe but it's fairly untested. Post a ticket and/or for names that fail and I will try to fix it. http://code.google.com/p/python-nameparser/issues/entry

HumanName instances will pass an equals (==) test if their lower case unicode
representations are the same.

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


Release Log
-----------

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

