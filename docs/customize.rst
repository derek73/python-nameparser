Customizing the Parser with Your Own Configuration
==================================================

Recognition of titles, prefixes, suffixes and conjunctions is provided
by matching the lower case characters of a name piece with pre-defined
sets located in :py:mod:`nameparser.config`. Since everyone's data are a
little bit different, you can easily adjust these predefined sets to
help fine tune the parser for your dataset.


Changing the Predefined Variables
+++++++++++++++++++++++++++++++++

There are a few ways to adjust the parser configuration depending on your needs. 
The config is available via ``from nameparser.config import CONSTANTS`` or on the
``C`` attribute of a ``HumanName`` instance, e.g. ``hn.C``. Take a look 
at the :py:mod:`nameparser.config` documentation to get a better idea what they are
and how they are used, but here's a quick walk through.


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
    	title: 'Hon' 
    	first: '' 
    	middle: '' 
    	last: 'Solo' 
    	suffix: ''
    	nickname: ''
    ]>
    >>> from nameparser.config import CONSTANTS
    >>> CONSTANTS.titles.remove('hon') # doctest: +ELLIPSIS
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


"Dean" is a common first name, but sometimes it is more common as a title.
If you would like "Dean" to be parsed as a title, simply add it to the
titles constant. 

You can pass multiple strings to both the ``add()`` and ``remove()``
methods and each string will be added or removed.

::

    >>> from nameparser import HumanName
    >>> from nameparser.config import CONSTANTS
    >>> CONSTANTS.titles.add('dean', 'Chemistry') # doctest: +ELLIPSIS
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

::

    >>> from nameparser import HumanName
    >>> hn = HumanName("Dean Robert Johns")
    >>> hn.C.titles.add('dean') # doctest: +ELLIPSIS
    SetManager(set([u'msgt', ..., u'adjutant']))
    >>> hn
    <HumanName : [
    	title: 'Dean' 
    	first: 'Robert' 
    	middle: '' 
    	last: 'Johns' 
    	suffix: ''
    	nickname: ''
    ]>
    >>> hn2 = HumanName("Dean Robert Johns")
    >>> hn2
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

::

    >>> from nameparser import HumanName
    >>> hn = HumanName("Dean Robert Johns", None)
    >>> hn.C.titles.add('dean') # doctest: +ELLIPSIS
    SetManager(set([u'msgt', ..., u'adjutant']))
    >>> hn
    <HumanName : [
    	title: 'Dean' 
    	first: 'Robert' 
    	middle: '' 
    	last: 'Johns' 
    	suffix: ''
    	nickname: ''
    ]>
    >>> hn.has_own_config
    True
    >>> hn2 = HumanName("Dean Robert Johns")
    >>> hn2
    <HumanName : [
    	title: '' 
    	first: 'Dean' 
    	middle: 'Robert' 
    	last: 'Johns' 
    	suffix: ''
    	nickname: ''
    ]>
    >>> hn2.has_own_config
    False


Refreshing the Parse
++++++++++++++++++++

The full name is parsed upon assignment to the ``full_name`` attribute or
instantiation. Sometimes after making changes to configuration or other inner 
data after assigning the full name, the name will need to be re-parsed with the
:py:func:`~nameparser.parser.HumanName.parse_full_name()` method before you see 
those changes with ``repr()``.


    >>> from nameparser import HumanName
    >>> hn = HumanName("Dean Robert Johns")
    >>> hn
    <HumanName : [
    	title: 'Dean' 
    	first: 'Robert' 
    	middle: '' 
    	last: 'Johns' 
    	suffix: ''
    	nickname: ''
    ]>
    >>> hn.C.titles.add('dean') # doctest: +ELLIPSIS
    SetManager(set([u'msgt', ..., u'adjutant']))
    >>> hn
    <HumanName : [
    	title: 'Dean' 
    	first: 'Robert' 
    	middle: '' 
    	last: 'Johns' 
    	suffix: ''
    	nickname: ''
    ]>
    >>> hn.parse_full_name()
    >>> hn
    <HumanName : [
    	title: '' 
    	first: 'Dean' 
    	middle: 'Robert' 
    	last: 'Johns' 
    	suffix: ''
    	nickname: ''
    ]>


