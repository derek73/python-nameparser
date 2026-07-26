Using the parser
================

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
they exist). A name with no fields set is falsy, which is how you tell
"nothing parsed" from "parsed to something":

.. doctest::

    >>> bool(parse("")), bool(parse("   ")), bool(parse("John"))
    (False, False, True)

Input shapes
-------------

Three arrangements are understood, and every piece of each is optional:

1. ``Title Given "Nickname" Middle Middle Family Suffix``
2. ``Family [Suffix], Title Given (Nickname) Middle Middle[,] Suffix [, Suffix]``
3. ``Title Given Middle Family [Suffix], Suffix [, Suffix]``

The last two differ in what the comma is doing. In form 2 it separates
the family name from the rest, so the family name comes first; in form
3 it only sets off suffixes, and the name before it is still
given-then-family:

.. doctest::

    >>> parse("de la Vega, Juan Q. Xavier III").family   # form 2
    'de la Vega'
    >>> parse("Doe Jr., John").suffix                    # form 2, suffix before the comma
    'Jr.'
    >>> parse("John Doe, Jr.").family                    # form 3
    'Doe'

For family-first input *without* a comma — common outside Europe — set
``name_order``; see :doc:`customize`.

Words that attach to their neighbors
--------------------------------------

Input shapes tell you where the fields sit. This tells you which words
merge into one field instead of standing alone — between them, that is
most of what decides a parse.

Most words stand alone. A few pull in a neighbor, and each kind pulls
into one particular field — so this table is also a map of which fields
get built by attachment rather than by position. Titles and suffixes
attach only to *adjacent words of their own kind* (a run of titles
chains into one, but a title never swallows a plain name); the rest
reach forward to pull in the next word, whatever it is. Follow a row's
name to its full vocabulary set:

.. list-table::
   :header-rows: 1
   :widths: 22 26 12 40

   * - Words
     - Attach to
     - Field
     - Example
   * - :mod:`Titles <nameparser.config.titles>`
     - adjacent titles
     - ``title``
     - ``Asst. Vice Chancellor John`` → ``Asst. Vice Chancellor``
   * - :mod:`Suffixes <nameparser.config.suffixes>`
     - adjacent suffixes
     - ``suffix``
     - ``John Smith PhD MD`` → ``PhD, MD``
   * - :mod:`Bound given names <nameparser.config.bound_first_names>`
     - the following word
     - ``given``
     - ``abdul salam ahmed`` → ``abdul salam``
   * - :mod:`Particles <nameparser.config.prefixes>`
     - the following surname
     - ``family``
     - ``Juan de la Vega`` → ``de la Vega``
   * - :mod:`Maiden markers <nameparser.config.maiden_markers>`
     - the following name
     - ``maiden``
     - ``Jane Smith née Jones`` → ``Jones``
   * - :mod:`Conjunctions <nameparser.config.conjunctions>`
     - the words on both sides
     - any
     - ``John and Jane Smith`` → ``John and Jane``

Conjunctions are the exception the last row names: they take the field
of whatever sits on both sides, so the same ``and`` pulls two given
names together as easily as two surnames:

.. doctest::

    >>> parse("John and Jane Smith").given
    'John and Jane'
    >>> parse("Juan de la Vega y Rodriguez").family
    'de la Vega y Rodriguez'

Position matters in exactly one place: the start of a name. A particle
there has no surname to attach to yet, so it either becomes the given
name or turns the whole name into a surname, depending on whether it is
one that can double as a given name:

.. doctest::

    >>> parse("van Gogh").given          # 'van' can be a given name
    'van'
    >>> parse("de Mesnil").given         # 'de' cannot
    ''
    >>> parse("de Mesnil").family
    'de Mesnil'

:doc:`customize` covers how to change which words are in each of these
sets, including which particles may double as given names.

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

``family_base`` is the one to sort on. Dutch and Belgian directories
file a name under the base surname and ignore the *tussenvoegsel* — the
``van``, ``de`` or ``van der`` in front of it — and the same convention
applies wherever particles are common:

.. doctest::

    >>> names = [parse(s) for s in
    ...          ["Vincent van Gogh", "Juan de la Vega", "John Smith"]]
    >>> [n.family_base for n in sorted(names, key=lambda n: n.family_base.lower())]
    ['Gogh', 'Smith', 'Vega']

Sorting on ``family`` instead files those under "d", "S" and "v", which
is the problem the split exists to solve:

.. doctest::

    >>> [n.family for n in sorted(names, key=lambda n: n.family.lower())]
    ['de la Vega', 'Smith', 'van Gogh']

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

The no-argument form above uses the DEFAULT lexicon; for a name parsed
with a custom :class:`~nameparser.Parser`, call
:meth:`Parser.capitalized() <nameparser.Parser.capitalized>` so the
parser's own vocabulary decides the exceptions.

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

Delimited content is not always a nickname. If what's inside is a known
suffix, or simply ends in a period, it is read as a suffix instead —
parenthesized credentials and retired ranks are far more common than
parenthesized nicknames that happen to be credentials:

.. doctest::

    >>> parse("Andrew Perkins (MBA)").suffix
    'MBA'
    >>> parse("Andrew Perkins (Ret.)").suffix
    'Ret.'

The exception to that exception is an *ambiguous* acronym — one that is
also a plausible name or set of initials. Standing alone inside
delimiters, it keeps the nickname reading:

.. doctest::

    >>> parse("JEFFREY (JD) BRICKEN").nickname
    'JD'

``JD`` is in ``suffix_acronyms_ambiguous``; see :doc:`customize` for
what that field marks and how to add to it.

.. _abbreviated-titles:

Titles you didn't configure
-----------------------------

A leading word that ends in a period is read as a title even when it is
in no vocabulary list, which is what lets unfamiliar ranks, honorifics
and abbreviations work without configuring anything:

.. doctest::

    >>> parse("Major. Dona Smith").title
    'Major.'
    >>> parse("Foo. Xyz. John Smith").title      # chains
    'Foo. Xyz.'

The rule is bounded in three ways, so it doesn't swallow ordinary
names. Single initials are left alone, so are abbreviations with
interior periods, and the rule only applies to the leading run — the
same word after the given name is a middle name:

.. doctest::

    >>> parse("J. Smith").given
    'J.'
    >>> parse("E.T. Jones").given
    'E.T.'
    >>> parse("John Major. Smith").middle
    'Major.'

Because this is structural rather than vocabulary-driven, emptying
``titles`` does not switch it off; see :doc:`customize`.

Comparing names
----------------

``==`` is strict value equality — two :class:`~nameparser.ParsedName`
instances are equal only if every field matches exactly. For "is this
the same name, allowing for order and case?" use ``matches()`` or
``comparison_key()`` instead. ``matches()`` parses a str argument with
the DEFAULT parser; to compare against a string using a custom
:class:`~nameparser.Parser`'s vocabulary, call
:meth:`Parser.matches() <nameparser.Parser.matches>`.

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

The post-nominals that double as ordinary surnames report the same way.
``MA`` after a full name is read as a credential, but after a single
given name it stays the surname — either way the choice is recorded:

.. doctest::

    >>> parse("John Smith MA").suffix
    'MA'
    >>> [a.kind.value for a in parse("John Smith MA").ambiguities]
    ['suffix-or-name']
    >>> parse("Jack MA").family
    'MA'

A reading the vocabulary settles on its own is not a guess and reports
nothing — periods make ``M.A.`` unambiguously a credential:

.. doctest::

    >>> parse("John Smith M.A.").ambiguities
    ()

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

A role's string name works too: ``name.tokens_for("family")``.

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

``replace()`` splits values on whitespace into plain, untagged
tokens — the vocabulary knowledge a parse would have about the new
text is not there. The views that depend on tags degrade: the parser
no longer knows ``de la`` are particles, so ``family_particles``
empties and the particles start contributing initials.

.. doctest::

    >>> name.family_particles
    'de la'
    >>> replaced = name.replace(family="de la Vega Smith")
    >>> replaced.family_particles
    ''
    >>> replaced.initials()
    'J. d. l. V. S.'

:meth:`Parser.revise() <nameparser.Parser.revise>` is the same
operation with each value classified by the parser's vocabulary, so
the correction behaves like a fresh parse of the corrected name
(which also means delimiters and marker words in the value are
consumed as they would be in a parse):

.. doctest::

    >>> from nameparser import Parser
    >>> parser = Parser()
    >>> revised = parser.revise(name, family="de la Vega Smith")
    >>> revised.family_particles
    'de la'
    >>> revised.initials()
    'J. V. S.'

``revise()`` has two siblings on :class:`~nameparser.Parser`:
:meth:`Parser.matches() <nameparser.Parser.matches>` and
:meth:`Parser.capitalized() <nameparser.Parser.capitalized>`. Those
two matter when you have built a custom parser — the
:class:`~nameparser.ParsedName` methods of the same names fall back
to the *default* configuration for str or omitted arguments.

Command line
------------

``python -m nameparser`` parses one name and prints what it found. It
is the quickest way to see how a particular string comes out — worth
reaching for when a name parsed unexpectedly and you want to check a
variation of it, or when trying a locale pack before wiring one into
code:

::

    $ python -m nameparser "dr. juan de la vega iii"
    Parsed:
    <ParsedName: [
        title: 'dr.'
        given: 'juan'
        family: 'de la vega'
        suffix: 'iii'
    ]>
    Capitalized:
    <ParsedName: [
        title: 'Dr.'
        given: 'Juan'
        family: 'de la Vega'
        suffix: 'III'
    ]>
    Initials: j. v.

``--json`` prints the fields as a single line instead, which is the
form to pipe somewhere:

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
