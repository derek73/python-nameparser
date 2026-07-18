Getting started
===============

Requires Python 3.11+.  ``pip install nameparser``

Parse a name
------------

.. doctest::

    >>> from nameparser import parse
    >>> name = parse("Dr. Juan Q. Xavier de la Vega III")
    >>> name.given, name.family
    ('Juan', 'de la Vega')
    >>> name.title, name.middle, name.suffix
    ('Dr.', 'Q. Xavier', 'III')

A parsed name has seven fields: ``title``, ``given``, ``middle``,
``family``, ``suffix``, ``nickname``, and ``maiden``. Parsing never
raises; unparseable input yields a :class:`~nameparser.ParsedName` with
empty fields plus any ``ambiguities`` the parser noticed along the way
(see :doc:`concepts`).

Aggregate views
----------------

.. doctest::

    >>> name.given_names          # given + middle
    'Juan Q. Xavier'
    >>> name.family_base, name.family_particles   # family, split apart
    ('Vega', 'de la')

``surnames`` (``middle`` + ``family``) is the mirror-image aggregate.
The plural is the tell: ``given`` and ``family`` are single fields,
while ``given_names`` and ``surnames`` roll several fields together —
the same sense in which a passport form asks for your "given names" as
one blank that can hold more than one word.

Dicts and strings
------------------

.. doctest::

    >>> name.as_dict(include_empty=False)
    {'title': 'Dr.', 'given': 'Juan', 'middle': 'Q. Xavier', 'family': 'de la Vega', 'suffix': 'III'}
    >>> str(name)
    'Dr. Juan Q. Xavier de la Vega III'
    >>> name.render("{family}, {given}")
    'de la Vega, Juan'
    >>> name.initials()
    'J. Q. X. V.'

Fixing case
-----------

.. doctest::

    >>> str(parse("juan de la vega").capitalized())
    'Juan de la Vega'

Nicknames and maiden names
----------------------------

.. doctest::

    >>> parse("Jonathan 'Jack' Kennedy").nickname
    'Jack'
    >>> parse("Jane Smith née Jones").maiden
    'Jones'

Comparing names
----------------

``==`` is strict value equality — two :class:`~nameparser.ParsedName`
instances are equal only if every field matches exactly. For "is this
the same name, allowing for order and case?" use ``matches()`` or
``comparison_key()`` instead.

.. doctest::

    >>> parse("de la Vega, Juan").matches("Juan de la Vega")
    True
    >>> parse("JUAN DE LA VEGA").comparison_key() == parse("Juan de la Vega").comparison_key()
    True

Correcting a parse
--------------------

:class:`~nameparser.ParsedName` is immutable, so a correction is a new
value: ``replace()`` returns a copy with the given fields changed and
everything else carried over.

.. doctest::

    >>> name = parse("Juan de la Vega")
    >>> corrected = name.replace(title="Dr.")
    >>> str(corrected)
    'Dr. Juan de la Vega'
    >>> name.title
    ''

Command line
------------

::

    $ python -m nameparser --json "Doe, John"
    {"title": "", "given": "John", "middle": "", "family": "Doe", "suffix": "", "nickname": "", "maiden": ""}

Add ``--locale`` to parse with a locale pack (for example ``--locale
ru``); see :doc:`locales`.

Where next
----------

* :doc:`concepts` — how the parser works
* :doc:`customize` — your own vocabulary and behavior
* :doc:`locales` — locale packs
* :doc:`migrate` — coming from 1.x ``HumanName``
