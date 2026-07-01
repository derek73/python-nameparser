Customizing the Parser with Your Own Configuration
==================================================

Recognition of titles, prefixes, suffixes and conjunctions is handled by
matching the lower case characters of a name piece with pre-defined sets
of strings located in :py:mod:`nameparser.config`. You can adjust
these predefined sets to help fine tune the parser for your dataset.

Changing the Parser Constants
-----------------------------

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
:py:class:`~nameparser.config.CONSTANTS` instance, depending on how you
instantiate the :py:class:`~nameparser.parser.HumanName` class (see below).



Editable attributes of nameparser.config.CONSTANTS
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

* :py:data:`~nameparser.config.TITLES` - Pieces that come before the name. Includes all `first_name_titles`. Cannot include things that may be first names.
* :py:data:`~nameparser.config.FIRST_NAME_TITLES` - Titles that, when followed by a single name, that name is a first name, e.g. "King David".
* :py:data:`~nameparser.config.SUFFIX_ACRONYMS` - Pieces that come at the end of the name that may or may not have periods separating the letters, e.g. "m.d.".
* :py:data:`~nameparser.config.SUFFIX_NOT_ACRONYMS` - Pieces that come at the end of the name that never have periods separating the letters, e.g. "Jr.".
* :py:data:`~nameparser.config.SUFFIX_ACRONYMS_AMBIGUOUS` - Acronym suffixes from ``SUFFIX_ACRONYMS`` that also plausibly work as a given-name nickname on their own, e.g. "JD", "Ed". When one of these appears alone in parenthesis or quotes (e.g. ``'JEFFREY (JD) BRICKEN'``), it's kept as a nickname rather than reclassified as a suffix, since that's the more common reading in ambiguous, delimiter-only context (see the "Nickname Handling" section in the usage guide).
* :py:data:`~nameparser.config.CONJUNCTIONS` - Connectors like "and" that join the preceding piece to the following piece.
* :py:data:`~nameparser.config.PREFIXES` - Connectors like "del" and "bin" that join to the following piece but not the preceding, similar to titles but can appear anywhere in the name.
* :py:data:`~nameparser.config.CAPITALIZATION_EXCEPTIONS` - Dictionary of pieces that do not capitalize the first letter, e.g. "Ph.D".
* :py:data:`~nameparser.config.REGEXES` - Regular expressions used to find words, initials, nicknames, etc.

Each set of constants comes with :py:func:`~nameparser.config.SetManager.add` and :py:func:`~nameparser.config.SetManager.remove` methods for tuning
the constants for your project. These methods automatically lower case and
remove punctuation to normalize them for comparison.

Adding Custom Nickname Delimiters
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

:py:meth:`~nameparser.parser.HumanName.parse_nicknames` recognizes three
built-in delimiters -- ``quoted_word``, ``double_quotes`` and
``parenthesis`` -- read from :py:attr:`~nameparser.config.Constants.regexes`,
so overriding e.g. ``CONSTANTS.regexes.parenthesis`` still works exactly as
before. To recognize an *additional* delimiter without overriding one of the
built-ins, add a pattern to
:py:obj:`~nameparser.config.Constants.extra_nickname_delimiters` (empty by
default) under any key, then re-run
:py:meth:`~nameparser.parser.HumanName.parse_full_name` to pick it up:

.. doctest::

    >>> import re
    >>> from nameparser import HumanName
    >>> hn = HumanName("Benjamin {Ben} Franklin", constants=None)
    >>> hn.nickname
    ''
    >>> hn.C.extra_nickname_delimiters['curly_braces'] = re.compile(r'\{(.*?)\}', re.U)
    >>> hn.parse_full_name()
    >>> hn.nickname
    'Ben'

Other editable attributes
~~~~~~~~~~~~~~~~~~~~~~~~~~

* :py:obj:`~nameparser.config.Constants.string_format` - controls output from `str()`
* :py:obj:`~nameparser.config.Constants.empty_attribute_default` - value returned by empty attributes, defaults to empty string
* :py:obj:`~nameparser.config.Constants.capitalize_name` - If set, applies :py:meth:`~nameparser.parser.HumanName.capitalize` to :py:class:`~nameparser.parser.HumanName` instance.
* :py:obj:`~nameparser.config.Constants.force_mixed_case_capitalization` - If set, forces the capitalization of mixed case strings when :py:meth:`~nameparser.parser.HumanName.capitalize` is called.
* :py:obj:`~nameparser.config.Constants.suffix_delimiter` - additional delimiter used to split suffix groups after comma-splitting, e.g. ``" - "`` for names like ``"Jane Smith, RN - CRNA"``. Defaults to ``None`` (disabled).
* :py:obj:`~nameparser.config.Constants.initials_separator` - string placed between consecutive initials within the same name group (after the delimiter). Defaults to ``" "``, so ``"A. K."``; set to ``""`` for compact ``"A.K."``.
* :py:obj:`~nameparser.config.Constants.patronymic_name_order` - If set, detects Russian formal-order names (``Surname GivenName Patronymic``) via a trailing East-Slavic patronymic suffix and rotates the parts to Western order (``first=GivenName``, ``middle=Patronymic``, ``last=Surname``). Opt-in; see subsection below.


Russian Formal Name Order
~~~~~~~~~~~~~~~~~~~~~~~~~

By default the parser treats all three-part names as ``First Middle Last``. For
Russian data in formal order (``Surname GivenName Patronymic``), enable
``patronymic_name_order``::

    >>> from nameparser import HumanName
    >>> from nameparser.config import Constants
    >>> C = Constants(patronymic_name_order=True)
    >>> hn = HumanName("Ivanov Ivan Ivanovich", constants=C)
    >>> hn.first, hn.middle, hn.last
    ('Ivan', 'Ivanovich', 'Ivanov')

Detection is anchored on a recognised East-Slavic patronymic suffix
(``-ovich``, ``-ovna``, ``-evich``, ``-evna``, ``-ichna``, and the irregular
forms ``-ilyich``, ``-kuzmich``, ``-lukich``, ``-fomich``, ``-fokich``; same
patterns in Cyrillic). A comma activates the parser's standard
Last, First Middle path, which already handles Russian formal order —
reordering is suppressed to avoid a double-transformation.

**Opt-in tradeoff:** when the flag is on, any name whose last token happens to
end in a patronymic suffix is reordered — including Western names with
patronymic-form surnames such as ``"David Michael Abramovich"``. Enable this
flag only when your data is predominantly Russian formal-order names.


Splitting last-name prefix particles
-------------------------------------

The :py:attr:`~nameparser.parser.HumanName.last_base` and
:py:attr:`~nameparser.parser.HumanName.last_prefixes` properties split the last
name at the boundary between leading prefix particles and the core surname.  They
use the same ``PREFIXES`` set, so adding a particle makes the split pick it up
automatically::

    >>> from nameparser import HumanName
    >>> from nameparser.config import CONSTANTS
    >>> CONSTANTS.prefixes.add('op')  # doctest: +ELLIPSIS
    SetManager({...})
    >>> HumanName("Jan op den Berg").last_base
    'Berg'
    >>> HumanName("Jan op den Berg").last_prefixes
    'op den'
    >>> CONSTANTS.prefixes.remove('op')  # doctest: +ELLIPSIS
    SetManager({...})

Note the ``remove`` call at the end — ``customize.rst`` examples share global
``CONSTANTS``, so mutations must be reversed to avoid affecting later examples.

Because ``last_base`` is a plain string property, sorting a list of names by
core surname (ignoring prefix particles like *van*, *de la*) is just a key
function::

    names = [
        HumanName("Vincent van Gogh"),
        HumanName("Juan de la Vega"),
        HumanName("John Smith"),
    ]
    sorted_names = sorted(names, key=lambda n: n.last_base.lower())
    # sort keys: 'gogh', 'smith', 'vega'  →  van Gogh, Smith, de la Vega

To sort by first name when two people share the same ``last_base``, add it as
a secondary key::

    sorted_names = sorted(names, key=lambda n: (n.last_base.lower(), n.first.lower()))

First-Name Prefixes
-------------------

``CONSTANTS.first_name_prefixes`` controls bound given-name prefixes that attach
to the following word to form one first name. By default it contains
``{'abdul', 'abdel', 'abdal', 'abu', 'abou', 'umm'}``.

Example::

    >>> from nameparser import HumanName
    >>> hn = HumanName("abdul salam ahmed salem")
    >>> hn.first, hn.middle, hn.last
    ('abdul salam', 'ahmed', 'salem')

To **disable** the feature entirely::

    >>> from nameparser.config import CONSTANTS
    >>> CONSTANTS.first_name_prefixes.clear()

To **add** a word (e.g. if your data uses ``mohamad`` as a bound prefix)::

    >>> CONSTANTS.first_name_prefixes.add('mohamad')

To **remove** a single entry::

    >>> CONSTANTS.first_name_prefixes.remove('umm')

You can also pass a custom set per ``Constants`` instance::

    >>> from nameparser.config import Constants
    >>> c = Constants(first_name_prefixes={'abu', 'umm'})
    >>> hn2 = HumanName("abu bakr al saud", constants=c)
    >>> hn2.first, hn2.last
    ('abu bakr', 'al saud')

Parser Customization Examples
-----------------------------

Removing a Title
~~~~~~~~~~~~~~~~

Take a look at the :py:mod:`nameparser.config` documentation to see what's
in the constants. Here's a quick walk through of some examples where you
might want to adjust them.

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
    SetManager({'right', ..., 'tax'})
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


If you don't want to detect any titles at all, you can remove all of them:

    >>> CONSTANTS.titles.clear()


Adding a Title
~~~~~~~~~~~~~~~~

You can also pass a ``Constants`` instance to ``HumanName`` on instantiation.

"Dean" is a common first name so it is not included in the default titles
constant. But in some contexts it is more common as a title. If you would
like "Dean" to be parsed as a title, simply add it to the titles constant.

You can pass multiple strings to both the :py:func:`~nameparser.config.SetManager.add`
and :py:func:`~nameparser.config.SetManager.remove`
methods and each string will be added or removed. Both functions
automatically normalize the strings for the parser's comparison method by
making them lower case and removing periods.

.. doctest::
    :options: +ELLIPSIS, +NORMALIZE_WHITESPACE

    >>> from nameparser import HumanName
    >>> from nameparser.config import Constants
    >>> constants = Constants()
    >>> constants.titles.add('dean', 'Chemistry')
    SetManager({'right', ..., 'tax'})
    >>> hn = HumanName("Assoc Dean of Chemistry Robert Johns", constants=constants)
    >>> hn
    <HumanName : [
      title: 'Assoc Dean of Chemistry'
      first: 'Robert'
      middle: ''
      last: 'Johns'
      suffix: ''
      nickname: ''
    ]>


Module-level Shared Configuration Instance
------------------------------------------

When you modify the configuration, by default this will modify the behavior all
HumanName instances. This could be a handy way to set it up for your entire
project, but it could also lead to some unexpected behavior because changing
the config on one instance could modify the behavior of another instance.

.. doctest:: module config
    :options: +ELLIPSIS, +NORMALIZE_WHITESPACE

    >>> from nameparser import HumanName
    >>> instance = HumanName("")
    >>> instance.C.titles.add('dean')
    SetManager({'right', ..., 'tax'})
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


If you'd prefer new instances to have their own config values, one shortcut is to pass
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
    SetManager({'right', ..., 'tax'})
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

Don't Remove Emojis
~~~~~~~~~~~~~~~~~~~

By default, all emojis are removed from the input string before the name is parsed.
You can turn this off by setting the ``emoji`` regex to ``False``.

.. doctest::

    >>> from nameparser import HumanName
    >>> from nameparser.config import Constants
    >>> constants = Constants()
    >>> constants.regexes.emoji = False
    >>> hn = HumanName("Sam 😊 Smith", constants=constants)
    >>> hn
    "Sam 😊 Smith"

Config Changes May Need Parse Refresh
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

The full name is parsed upon assignment to the ``full_name`` attribute or
instantiation. Sometimes after making changes to configuration or other inner
data after assigning the full name, the name will need to be re-parsed with the
:py:func:`~nameparser.parser.HumanName.parse_full_name()` method before you see
those changes with ``repr()``.


Adjusting names after parsing them
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Each attribute has a corresponding ordered list of name pieces. If you're doing
pre- or post-processing you may wish to manipulate these lists directly.
The strings returned by the attribute names just join these lists with spaces.


* o.title_list
* o.first_list
* o.middle_list
* o.last_list
* o.suffix_list
* o.nickname_list

::

  >>> hn = HumanName("Juan Q. Xavier Velasquez y Garcia, Jr.")
  >>> hn.middle_list
  ['Q.', 'Xavier']
  >>> hn.middle_list += ["Ricardo"]
  >>> hn.middle_list
  ['Q.', 'Xavier', 'Ricardo']


You can also replace any name bucket's contents by assigning a string or a list
directly to the attribute.

::

  >>> hn = HumanName("Dr. John A. Kenneth Doe")
  >>> hn.title = ["Associate","Professor"]
  >>> hn.suffix = "Md."
  >>> hn.suffix
  <HumanName : [
    title: 'Associate Processor'
    first: 'John'
    middle: 'A. Kenneth'
    last: 'Doe'
    suffix: 'Md.'
    nickname: ''
  ]>



