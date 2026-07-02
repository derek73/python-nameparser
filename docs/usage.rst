Using the HumanName Parser
==========================

Example Usage
-------------

Requires Python 3.10+.

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
    >>> name.last_base
    'Vega'
    >>> name.last_prefixes
    'de la'
    >>> name.family
    'Vega'
    >>> name.suffix
    'III'
    >>> name.surnames
    'Q. Xavier de la Vega'
    >>> name.given_names
    'Juan Q. Xavier'
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
the case of names entered in mixed case. To run capitalization on a
`HumanName` instance, pass the parameter `force=True`.

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

To apply capitalization to all `HumanName` instances, set
:py:attr:`~nameparser.config.Constants.capitalize_name` to `True`.

.. doctest:: capitalize_name
    :options: +NORMALIZE_WHITESPACE

    >>> from nameparser.config import CONSTANTS
    >>> CONSTANTS.capitalize_name = True
    >>> name = HumanName("bob v. de la macdole-eisenhower phd")
    >>> str(name)
    'Bob V. de la MacDole-Eisenhower Ph.D.'

To force the capitalization of mixed case strings on all `HumanName` instances,
set :py:attr:`~nameparser.config.Constants.force_mixed_case_capitalization` to `True`. 

.. doctest:: force_mixed_case_capitalization
    :options: +NORMALIZE_WHITESPACE

    >>> from nameparser.config import CONSTANTS
    >>> CONSTANTS.force_mixed_case_capitalization = True
    >>> name = HumanName('Shirley Maclaine')
    >>> name.capitalize()
    >>> str(name)
    'Shirley MacLaine'


Nickname Handling
------------------

The content of parenthesis or quotes in the name will be
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

Exception: content that looks like a suffix (a member of
:py:data:`~nameparser.config.SUFFIX_ACRONYMS` or
:py:data:`~nameparser.config.SUFFIX_NOT_ACRONYMS`, or anything ending in a
period) is treated as a suffix instead of a nickname, since that's usually
what's meant, e.g. a retired military title or a professional designation
written in parenthesis.

.. doctest:: nicknames
    :options: +NORMALIZE_WHITESPACE

    >>> name = HumanName('Andrew Perkins (MBA)')
    >>> name
    <HumanName : [
      title: ''
      first: 'Andrew'
      middle: ''
      last: 'Perkins'
      suffix: 'MBA'
      nickname: ''
    ]>

A few suffix acronyms, listed in
:py:data:`~nameparser.config.SUFFIX_ACRONYMS_AMBIGUOUS`, also work as common
given-name nicknames on their own (e.g. "JD", "Ed"). These stay nicknames
when found alone in parenthesis or quotes, since that's the more common
reading in that ambiguous context:

.. doctest:: nicknames
    :options: +NORMALIZE_WHITESPACE

    >>> name = HumanName('JEFFREY (JD) BRICKEN')
    >>> name
    <HumanName : [
      title: ''
      first: 'JEFFREY'
      middle: ''
      last: 'BRICKEN'
      suffix: ''
      nickname: 'JD'
    ]>

Leading Period-Abbreviation Titles
-----------------------------------

An unrecognized, multi-letter word ending in a period, appearing before the
first name, is treated as a title -- this covers military ranks and other
abbreviations that aren't in the built-in titles list. Single-letter
initials (``"J."``) and internal-period abbreviations (``"E.T."``) are not
affected, and the same word appearing after the first name is left as a
middle name.

.. doctest:: leading_period_titles
    :options: +NORMALIZE_WHITESPACE

    >>> name = HumanName("Major. Dona Smith")
    >>> name
    <HumanName : [
      title: 'Major.'
      first: 'Dona'
      middle: ''
      last: 'Smith'
      suffix: ''
      nickname: ''
    ]>
    >>> name = HumanName("J. Smith")
    >>> name.first
    'J.'
    >>> name.title
    ''

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

You can control the order and presence of any name fields by changing the
:py:attr:`~nameparser.config.Constants.string_format` attribute of the shared CONSTANTS instance.
Don't want to include nicknames in your output? No problem. Just omit that keyword from the 
`string_format` attribute.

.. doctest:: string format

  >>> from nameparser.config import CONSTANTS
  >>> CONSTANTS.string_format = "{title} {first} {last}"
  >>> name = HumanName("Dr. Juan Ruiz de la Vega III (Doc Vega)")
  >>> str(name)
  'Dr. Juan de la Vega'


Initials Support
----------------

The HumanName class can try to get the correct representation of initials.
Initials can be tricky as different format usages exist. 
To exclude any of the name parts from the initials, change the initials format string: 
:py:attr:`~nameparser.config.Constants.initials_format`
Three attributes exist for the format, `first`, `middle` and `last`. 

.. doctest:: initials format

  >>> from nameparser.config import CONSTANTS
  >>> CONSTANTS.initials_format = "{first} {middle}"
  >>> HumanName("Doe, John A. Kenneth, Jr.").initials()
  'J. A. K.'
  >>> HumanName("Doe, John A. Kenneth, Jr.", initials_format="{last}, {first}").initials()
  'D., J.'
  >>> CONSTANTS.initials_format = "{first} {middle} {last}"


Furthermore, the delimiter for the string output can be set through:
:py:attr:`~nameparser.config.Constants.initials_delimiter`

.. doctest:: initials delimiter

  >>> HumanName("Doe, John A. Kenneth, Jr.", initials_delimiter=";").initials()
  'J; A; K; D;'

The separator between consecutive initials *within* a name group (e.g. two middle
names) is controlled by :py:attr:`~nameparser.config.Constants.initials_separator`,
which defaults to ``" "``. Setting it to ``""`` removes that space within a group;
spacing *between* groups is still governed by ``initials_format``.

``initials_delimiter``, ``initials_separator``, and ``initials_format`` work together:

- ``initials_delimiter`` — appended *after* each individual initial (default ``"."``)
- ``initials_separator`` — placed *after* the delimiter between consecutive initials in the same group (default ``" "``), so with ``delimiter="."`` and ``separator=" "`` you get ``A. K.``
- ``initials_format`` — controls how the first, middle, and last groups are arranged

For example, to produce compact period-separated initials with no spaces:

.. doctest:: initials separator

  >>> HumanName("Doe, John A. Kenneth, Jr.", initials_separator="", initials_format="{first}{middle}{last}").initials()
  'J.A.K.D.'
  >>> HumanName("Doe, John A. Kenneth, Jr.", initials_delimiter="", initials_separator="", initials_format="{first}{middle}{last}").initials()
  'JAKD'

To get a list representation of the initials, use :py:meth:`~nameparser.HumanName.initials_list`.
This function is unaffected by :py:attr:`~nameparser.config.Constants.initials_format`

.. doctest:: list format

  >>> HumanName("Doe, John A. Kenneth, Jr.", initials_delimiter=";").initials_list()
  ['J', 'A', 'K', 'D']
    
