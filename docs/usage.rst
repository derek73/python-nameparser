Using the HumanName Parser
==========================

Example
-------

.. doctest::
    :options: -ELLIPSIS, +NORMALIZE_WHITESPACE

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
    >>> name.full_name = 'Doe-Ray, Col. Jonathan "John" A. Harris III'
    >>> name.title
    u'Col.'
    >>> name.first
    u'Jonathan'
    >>> name.middle
    u'A. Harris'
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
        title: '' 
        first: 'Juan' 
        middle: 'Jason Alexander' 
        last: 'Velasquez y Garcia' 
        suffix: 'Jr.'
        nickname: ''
    ]>
    >>> name = HumanName("Dr. Juan Q. Xavier de la Vega III")
    >>> name2 = HumanName("de la vega, dr. juan Q. xavier III")
    >>> name == name2
    True
    >>> len(name)
    5
    >>> list(name)
    [u'Dr.', u'Juan', u'Q. Xavier', u'de la Vega', u'III']
    >>> name[1:-2]
    [u'Juan', u'Q. Xavier', u'de la Vega']
    >>> name = HumanName('bob v. de la macdole-eisenhower phd')
    >>> name.capitalize()
    >>> unicode(name)
    u'Bob V. de la MacDole-Eisenhower Ph.D.'
    >>> # Don't touch mixed case names
    >>> name = HumanName('Shirley Maclaine')
    >>> name.capitalize()
    >>> unicode(name) 
    u'Shirley Maclaine'


Capitalization Support
----------------------

The HumanName class can try to guess the correct capitalization of name
entered in all upper or lower case. 


    Capitalize the name.

    * bob v. de la macdole-eisenhower phd -> Bob V. de la MacDole-Eisenhower Ph.D.

.. doctest:: capitalize

    >>> name = HumanName("bob v. de la macdole-eisenhower phd")
    >>> name.capitalize()
    >>> unicode(name)
    u'Bob V. de la MacDole-Eisenhower Ph.D.'

It will not adjust the case of mixed case names.


Handling Nicknames
------------------

The content of parenthesis or double quotes in the name will be
available from the nickname attribute. (Added in v0.2.9)

.. doctest:: nicknames
    :options: +NORMALIZE_WHITESPACE

    >>> name = HumanName('Jonathan "John" A. Smith')
    >>> name
    <HumanName : [
    	title: '' 
    	first: 'Jonathan' 
    	middle: 'A.' 
    	last: 'Smith' 
    	suffix: ''
    	nickname: 'John'
    ]>


String Format
-------------

The format of the strings returned with ``unicode()`` can be adjusted
using standard python string formatting. The string's ``format()``
method will be passed a dictionary of names.

.. doctest:: string format

    >>> name = HumanName("Rev John A. Kenneth Doe III")
    >>> unicode(name)
    u'Rev John A. Kenneth Doe III'
    >>> name.string_format = "{last}, {title} {first} {middle}, {suffix}"
    >>> unicode(name)
    u'Doe, Rev John A. Kenneth, III'

