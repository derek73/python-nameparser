Customizing the Parser with Your Own Configuration
==================================================

Recognition of titles, prefixes, suffixes and conjunctions is provided by
matching the lower case characters of a name piece with pre-defined sets
of strings located in :py:mod:`nameparser.config`. You can easily adjust
these predefined sets to help fine tune the parser for your dataset.


Changing the Predefined Variables
+++++++++++++++++++++++++++++++++

There are a few ways to adjust the parser configuration depending on your
needs. The config is available in two places.

The first is via ``from nameparser.config import CONSTANTS``.

.. doctest::

    >>> from nameparser.config import CONSTANTS
    >>> CONSTANTS
    <Constants() instance>

The other is the ``C`` attribute of a ``HumanName`` instance, e.g.
``hn.C``.

.. doctest::

    >>> from nameparser import HumanName
    >>> hn = HumanName("Dean Robert Johns")
    >>> hn.C
    <Constants() instance>

Both places are usually a reference to the same shared module-level 
:py:class:`~nameparser.config.Constants` instance, depending on how you 
instantiate the :py:class:`~nameparser.parser.HumanName` class (see below).

Take a look at the :py:mod:`nameparser.config` documentation to see what's
in the constants. Here's a quick walk through of some examples where you
might want to adjust them.


Parser Customization Examples
+++++++++++++++++++++++++++++

"Hon" is a common abbreviation for "Honorable", a title used when
addressing judges, and is included in the default tiles constants. This
means it will never be considered a first name, because titles are the
pieces before first names. 

But "Hon" is also sometimes a first name. If your dataset contains more
"Hon"s than "Honorable"s, you may wish to remove it from the titles
constant so that "Hon" can be parsed as a first name.

.. doctest::
    :options: +ELLIPSIS, +NORMALIZE_WHITESPACE

    >>> from nameparser import HumanName
    >>> hn = HumanName("Hon Solo")
    >>> hn
    <HumanName : [
    	title: 'Hon' 
    	first: '' 
    	middle: '' 
    	last: 'Solo' 
    	suffix: ''
    	nickname: ''
    ]>
    >>> from nameparser.config import CONSTANTS
    >>> CONSTANTS.titles.remove('hon')
    SetManager(set([u'msgt', ..., u'adjutant']))
    >>> hn = HumanName("Hon Solo")
    >>> hn
    <HumanName : [
    	title: '' 
    	first: 'Hon' 
    	middle: '' 
    	last: 'Solo' 
    	suffix: ''
    	nickname: ''
    ]>


"Dean" is a common first name so it is not included in the default titles
constant. But in some contexts it is more common as a title. If you would
like "Dean" to be parsed as a title, simply add it to the titles constant.

You can pass multiple strings to both the ``add()`` and ``remove()``
methods and each string will be added or removed. Both functions
automatically normalize the strings for the parser's comparison method by
making them lower case and removing periods.

.. doctest::
    :options: +ELLIPSIS, +NORMALIZE_WHITESPACE

    >>> from nameparser import HumanName
    >>> from nameparser.config import CONSTANTS
    >>> CONSTANTS.titles.add('dean', 'Chemistry')
    SetManager(set([u'msgt', ..., u'adjutant']))
    >>> hn = HumanName("Assoc Dean of Chemistry Robert Johns")
    >>> hn
    <HumanName : [
    	title: 'Assoc Dean of Chemistry' 
    	first: 'Robert' 
    	middle: '' 
    	last: 'Johns' 
    	suffix: ''
    	nickname: ''
    ]>


Parser Customizations Are Module-Wide 
+++++++++++++++++++++++++++++++++++++

When you modify the configuration, by default this will modify the behavior all
HumanName instances. This could be a handy way to set it up for your entire
project, but it could also lead to some unexpected behavior because changing
the config on one instance could modify the behavior of another instance.

.. doctest:: module config
    :options: +ELLIPSIS, +NORMALIZE_WHITESPACE

    >>> from nameparser import HumanName
    >>> instance = HumanName("")
    >>> instance.C.titles.add('dean')
    SetManager(set([u'msgt', ..., u'adjutant']))
    >>> other_instance = HumanName("Dean Robert Johns")
    >>> other_instance # Dean parses as title
    <HumanName : [
    	title: 'Dean' 
    	first: 'Robert' 
    	middle: '' 
    	last: 'Johns' 
    	suffix: ''
    	nickname: ''
    ]>


If you'd prefer new instances to have their own config values, you can pass
``None`` as the second argument (or ``constant`` keyword argument) when
instantiating ``HumanName``. Each instance always has a ``C`` attribute, but if
you didn't pass something falsey to the ``constants`` argument then it's a
reference to the module-level config values with the behavior described above.

.. doctest:: module config
    :options: +ELLIPSIS, +NORMALIZE_WHITESPACE

    >>> from nameparser import HumanName
    >>> instance = HumanName("Dean Robert Johns")
    >>> instance.has_own_config
    False
    >>> instance.C.titles.add('dean')
    SetManager(set([u'msgt', ..., u'adjutant']))
    >>> other_instance = HumanName("Dean Robert Johns", None) # <-- pass None for per-instance config
    >>> other_instance
    <HumanName : [
    	title: '' 
    	first: 'Dean' 
    	middle: 'Robert' 
    	last: 'Johns' 
    	suffix: ''
    	nickname: ''
    ]>
    >>> other_instance.has_own_config
    True


Config Changes May Need Parse Refresh
+++++++++++++++++++++++++++++++++++++

The full name is parsed upon assignment to the ``full_name`` attribute or
instantiation. Sometimes after making changes to configuration or other inner 
data after assigning the full name, the name will need to be re-parsed with the
:py:func:`~nameparser.parser.HumanName.parse_full_name()` method before you see 
those changes with ``repr()``.

::

    >>> from nameparser import HumanName
    >>> from nameparser.config import CONSTANTS
    >>> hn = HumanName("Dean Robert Johns")
    >>> hn
    <HumanName : [
    	title: '' 
    	first: 'Dean' 
    	middle: 'Robert' 
    	last: 'Johns' 
    	suffix: ''
    	nickname: ''
    ]>
    >>> CONSTANTS.titles.add('dean')
    SetManager(set([u'msgt', ..., u'adjutant']))
    >>> hn
    <HumanName : [
    	title: '' 
    	first: 'Dean' 
    	middle: 'Robert' 
    	last: 'Johns' 
    	suffix: ''
    	nickname: ''
    ]>
    >>> hn.parse_full_name()
    >>> hn
    <HumanName : [
    	title: 'Dean' 
    	first: 'Robert' 
    	middle: '' 
    	last: 'Johns' 
    	suffix: ''
    	nickname: ''
    ]>


