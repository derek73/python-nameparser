===========
Name Parser
===========

A simple Python module for parsing human names into their individual components.

**Attributes**

    * HumanName.title
    * HumanName.first
    * HumanName.middle
    * HumanName.last
    * HumanName.suffix
    

Works for a variety of common name formats for latin-based languages. 

    * Doe-Ray, Col. John A. Jérôme III
    * Dr. Juan Q. Xavier de la Vega II
    * Juan Q. Xavier Velasquez y Garcia, Jr.

Over 100 unit tests with example names. Should be unicode safe but it's fairly untested.

HumanName instances will pass an equals (==) test if their lower case unicode
representations are the same.

Usage
=====
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
    >>> name.parse_full_name()
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
    >>> name = HumanName("Juan Q. Xavier Velasquez y Garcia, Jr.")
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


Release Log
===========

    * 0.1.5 - Move documentation to README.rst, add release log
    * 0.1.4 - Use set() in constants for improved speed. setuptools compatibility - sketerpot
    * 0.1.3 - Add capitalization feature - twotwo
    * 0.1.2 - Add slice support