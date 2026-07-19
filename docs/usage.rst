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
(see `When the parser had to guess`_ below, and :doc:`concepts` for why
they exist).

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

Both fields appear in the default ``str()`` rendering — the nickname
quoted after the given name, the maiden name parenthesized after the
family name:

.. doctest::

    >>> str(parse("Jane (Janie) Smith née Jones"))
    'Jane "Janie" Smith (Jones)'

.. _maiden-roundtrip:

That default is built for display, and the two fields differ in what
survives it. The quoted nickname reparses as a nickname; the
parenthesized maiden name reparses as a *nickname* too, so a
parse-render-reparse round trip silently loses it:

.. doctest::

    >>> parse('Jane "Janie" Smith (Jones)').maiden
    ''
    >>> parse('Jane "Janie" Smith (Jones)').nickname
    'Janie Jones'

If the rendered string has to survive a reparse — storing names as text
and reading them back, for instance — render the marker explicitly
instead of relying on the default:

.. doctest::

    >>> name = parse("Jane Smith née Jones")
    >>> text = name.render("{given} {family} née {maiden}")
    >>> text
    'Jane Smith née Jones'
    >>> parse(text).maiden
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

When the parser had to guess
-----------------------------

Some names have no single correct reading. ``"Van Johnson"`` could be
the given name ``Van``, or the family-name particle ``van``. 2.0 takes
the more likely reading and *records* the choice on ``ambiguities``
rather than deciding silently:

.. doctest::

    >>> name = parse("Van Johnson")
    >>> name.given, name.family
    ('Van', 'Johnson')
    >>> for a in name.ambiguities:
    ...     print(a.kind.value, "-", a.detail)
    particle-or-given - leading 'Van' may be a family-name particle; read as a given name

:class:`~nameparser.AmbiguityKind` members are their own string values,
so branching on a kind needs no import:

.. doctest::

    >>> name.ambiguities[0].kind == "particle-or-given"
    True
    >>> [t.text for t in name.ambiguities[0].tokens]
    ['Van']

Most names report none. A non-empty ``ambiguities`` is a useful signal
for routing a record to human review instead of trusting it silently.

Tokens and spans
------------------

The seven fields are the convenient view. Underneath, each one is
backed by tokens carrying their exact offsets into the original string,
so you can always get back to the text a field came from:

.. doctest::

    >>> name = parse("Juan de la Vega")
    >>> for tok in name.tokens:
    ...     print(f"{tok.text!r:8} {tok.role.value:8} {tuple(tok.span)}")
    'Juan'   given    (0, 4)
    'de'     family   (5, 7)
    'la'     family   (8, 10)
    'Vega'   family   (11, 15)
    >>> tok = name.tokens[1]
    >>> name.original[tok.span.start:tok.span.end]
    'de'

``tokens_for()`` narrows that to a single role:

.. doctest::

    >>> from nameparser import Role
    >>> [t.text for t in name.tokens_for(Role.FAMILY)]
    ['de', 'la', 'Vega']

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
