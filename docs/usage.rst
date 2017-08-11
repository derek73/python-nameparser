Using the HumanName Parser
==========================

Example Usage
-------------

The examples use Python 3, but Python 2.6+ is supported.

.. doctest::
    :options: +NORMALIZE_WHITESPACE

    >>> from nameparser import HumanName
    >>> name = HumanName("Dr. Juan Q. Xavier de la Vega III")
    >>> name.title
    'Dr.'
    >>> name["title"]
    'Dr.'
    >>> name.first
    'Juan'
    >>> name.middle
    'Q. Xavier'
    >>> name.last
    'de la Vega'
    >>> name.suffix
    'III'
    >>> name.full_name = "Juan Q. Xavier Velasquez y Garcia, Jr."
    >>> name
    <HumanName : [
    	title: '' 
    	first: 'Juan' 
    	middle: 'Q. Xavier' 
    	last: 'Velasquez y Garcia' 
    	suffix: 'Jr.'
    	nickname: ''
    ]>
    >>> name.middle = "Jason Alexander"
    >>> name.middle
    'Jason Alexander'
    >>> name
    <HumanName : [
        title: '' 
        first: 'Juan' 
        middle: 'Jason Alexander' 
        last: 'Velasquez y Garcia' 
        suffix: 'Jr.'
        nickname: ''
    ]>
    >>> name.middle = ["custom","values"]
    >>> name.middle
    'custom values'
    >>> name.full_name = 'Doe-Ray, Jonathan "John" A. Harris'
    >>> name.as_dict()
    {'last': 'Doe-Ray', 'suffix': '', 'title': '', 'middle': 'A. Harris', 'nickname': 'John', 'first': 'Jonathan'}
    >>> name.as_dict(False) # add False to hide keys with empty values
    {'middle': 'A. Harris', 'nickname': 'John', 'last': 'Doe-Ray', 'first': 'Jonathan'}
    >>> name = HumanName("Dr. Juan Q. Xavier de la Vega III")
    >>> name2 = HumanName("de la vega, dr. juan Q. xavier III")
    >>> name == name2
    True
    >>> len(name)
    5
    >>> list(name)
    ['Dr.', 'Juan', 'Q. Xavier', 'de la Vega', 'III']
    >>> name[1:-2]
    ['Juan', 'Q. Xavier', 'de la Vega']


Capitalization Support
----------------------

The HumanName class can try to guess the correct capitalization of name
entered in all upper or lower case. By default, it will not adjust 
the case of names entered in mixed case. To run capitalization on all names
pass the parameter `force=True`.


    Capitalize the name.

    * bob v. de la macdole-eisenhower phd -> Bob V. de la MacDole-Eisenhower Ph.D.

.. doctest:: capitalize

    >>> name = HumanName("bob v. de la macdole-eisenhower phd")
    >>> name.capitalize()
    >>> str(name)
    'Bob V. de la MacDole-Eisenhower Ph.D.'
    >>> name = HumanName('Shirley Maclaine') # Don't change mixed case names
    >>> name.capitalize()
    >>> str(name)
    'Shirley Maclaine'
    >>> name.capitalize(force=True)
    >>> str(name) 
    'Shirley MacLaine'


Nickname Handling
------------------

The content of parenthesis or double quotes in the name will be
available from the nickname attribute.

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

Change the output string with string formatting
-----------------------------------------------

The string representation of a `HumanName` instance is controlled by its `string_format` attribute.
The default value, `"{title} {first} {middle} {last} {suffix} ({nickname})"`, includes parenthesis
around nicknames. Trailing commas and empty quotes and parenthesis are automatically removed if the
name has no nickname pieces.

You can change the default formatting for all `HumanName` instances by setting a new
:py:attr:`~nameparser.config.Constants.string_format` value on the shared
:py:class:`~nameparser.config.CONSTANTS` configuration instance.

.. doctest:: string format

  >>> from nameparser.config import CONSTANTS
  >>> CONSTANTS.string_format = "{title} {first} ({nickname}) {middle} {last} {suffix}"
  >>> name = HumanName('Robert Johnson')
  >>> str(name)
  'Robert Johnson'
  >>> name = HumanName('Robert "Rob" Johnson')
  >>> str(name)
  'Robert (Rob) Johnson'

You can control the order and presense of any name fields by changing the
:py:attr:`~nameparser.config.Constants.string_format` attribute of the shared CONSTANTS instance.
Don't want to include nicknames in your output? No problem. Just omit that keyword from the 
`string_format` attribute.

.. doctest:: string format

  >>> from nameparser.config import CONSTANTS
  >>> CONSTANTS.string_format = "{title} {first} {last}"
  >>> name = HumanName("Dr. Juan Ruiz de la Vega III (Doc Vega)")
  >>> str(name)
  'Dr. Juan de la Vega'


