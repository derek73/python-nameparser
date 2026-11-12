.. _getting-started:

Getting started
===============

Three steps, in the order most people need them: read one name, let a
list of names choose the settings, and compare names from several
sources. Each links to the page that covers it in full.

Install it with ``pip install nameparser``. It needs Python 3.11 or
later. The optional extra ``nameparser[ja]`` divides unspaced Japanese kanji names (:ref:`east-asian-names`).

Parse one name
--------------

:func:`~nameparser.parse` reads a name into seven fields: ``title``,
``given``, ``middle``, ``family``, ``suffix``, ``nickname`` and
``maiden``. Its result is a :class:`~nameparser.ParsedName`, which
cannot be changed after the parse:

.. doctest::

    >>> from nameparser import parse
    >>> juan = parse("Dr. Juan Q. Xavier de la Vega III")
    >>> juan.given, juan.family
    ('Juan', 'de la Vega')
    >>> juan.title, juan.middle, juan.suffix
    ('Dr.', 'Q. Xavier', 'III')
    >>> juan.render("{family}, {given}")
    'de la Vega, Juan'
    >>> juan.as_dict(include_empty=False)
    {'title': 'Dr.', 'given': 'Juan', 'middle': 'Q. Xavier', 'family': 'de la Vega', 'suffix': 'III'}

Parsing never raises on a string. Where a name has two readings and
nothing in the text chooses between them, the parser takes the likelier
one and reports the other on ``ambiguities``. ``Van`` opening a name is
a given name for the actor Van Johnson and the start of the family name
for President Van Buren, so the parser reports it:

.. doctest::

    >>> buren = parse("Van Buren")
    >>> buren.given, buren.family
    ('Van', 'Buren')
    >>> buren.ambiguities
    (Ambiguity('particle-or-given': 'Van'),)

Most names report nothing. A name that does is one to route to a
person for review. :doc:`usage` covers everything a parsed name gives
you, and :doc:`shapes` the forms of input it reads.

A list of names: let ``suggest`` choose the settings
-----------------------------------------------------

One name cannot show its order: ``Priem Jason`` and ``Jason Priem``
have the same shape. A list from one source can, because a source
writes every name the same way and many of its names carry evidence of
the order.

:meth:`Parser.suggest() <nameparser.Parser.suggest>` reads a list you
declare to be one group and returns a :class:`~nameparser.Suggestion`.
Parse the list's names with its ``parser``. ``suggest`` reads its
argument once, so pass a list, not a ``csv.reader`` you mean to parse
afterwards:

.. doctest::

    >>> from nameparser import Parser
    >>> listing = ["Priem Jason", "Kim Minjun", "Wang Xiaoming",
    ...            "Nguyen Anh", "Jason Priem"]
    >>> suggestion = Parser().suggest(listing)
    >>> suggestion.patch
    PolicyPatch(name_order=FAMILY_FIRST)
    >>> parse("Priem Jason").given
    'Priem'
    >>> suggestion.parser.parse("Priem Jason").given
    'Jason'

``patch`` holds the settings the list changed. Printing the suggestion
shows the evidence for each setting and the names that voted against
it. Check those by hand: the suggested parser misreads them, and
``suggestion.base`` is the parser you started from:

.. doctest::

    >>> print(suggestion)
    Suggested for 5 names (base: Parser(Lexicon(default), Policy())):
      name_order  FAMILY_FIRST  4 for, 1 against, 0 no evidence
          surname FAMILY_FIRST  3
          given-name FAMILY_FIRST  1
          given-name GIVEN_FIRST  1
      patronymic_rules  unchanged (none)  no evidence
      initials_as_family  unchanged (False)  no evidence
      disagreeing (1): Jason Priem

The evidence is in the names themselves: a common romanized Chinese,
Korean or Vietnamese surname, or a common given name that is rarely
a surname (``Mary``, not ``John``), at one end; a
family name written in capitals; a lowercase particle; initials after
the name, as a bibliography writes them. ``suggest`` decides three
settings from it, and leaves every other one as the parser you called
it on has it:

- **The name order** (:ref:`name-order`): given name first, or family
  name first.
- **A patronymic rule** (:class:`~nameparser.PatronymicRule`): East
  Slavic or Turkic, where at least five names, and more than four in
  five of the names that cast any vote, carry that patronymic.
- **Letters as the family name** (:ref:`initials-as-family`): where
  one run of letters ends at least two names, and at least half of the
  names that end in letters, as Nepal's ``B K`` and ``K C`` are family
  names written short (only on a base that reads given names first and
  keeps middle names apart).

Choose the language first
~~~~~~~~~~~~~~~~~~~~~~~~~

``suggest`` never chooses a language. A language pack does
(:doc:`locales`), so where you know the list's language, choose its
pack and call ``suggest`` on that parser. Told only the order, the
default reads this Spanish list's second family name as the given name;
the pack reads both family names and ``suggest`` adds the order:

.. doctest::

    >>> from nameparser import locales, parser_for
    >>> spanish_list = ["PÉREZ GARCÍA Juan", "López Ana", "Martínez Ruiz José"]
    >>> Parser().suggest(spanish_list).parser.parse("PÉREZ GARCÍA Juan").given
    'GARCÍA'
    >>> spanish = parser_for(locales.ES).suggest(spanish_list)
    >>> spanish.patch
    PolicyPatch(name_order=FAMILY_FIRST)
    >>> perez = spanish.parser.parse("PÉREZ GARCÍA Juan")
    >>> perez.given, perez.family
    ('Juan', 'PÉREZ GARCÍA')

Where it declines
~~~~~~~~~~~~~~~~~

Where too few names agree, ``suggest`` keeps the base parser's value.
An order needs at least two votes, more than two thirds of the names
whose order votes agree with each other. A name of one word casts none,
nor does a name with a comma, unless only post-nominals follow it
(``Zhang Wei, PhD``). Here only ``Mary`` votes (``John`` is also a
surname), one short:

.. doctest::

    >>> Parser().suggest(["Smith John", "Jones Mary"]).patch
    PolicyPatch()

Initials after the name vote only where at least three names end in
them and those are at least 60% of the list's names (a name with a
comma, or with nothing but titles, is not counted), so a short list of
bylines may get no order suggestion:

.. doctest::

    >>> Parser().suggest(["Smith J", "Jones M"]).patch
    PolicyPatch()
    >>> Parser().suggest(["Smith J", "Jones M", "Brown K"]).patch
    PolicyPatch(name_order=FAMILY_FIRST)

Where you know the order a list is written in, bylines included, set it
yourself with ``Policy(name_order=FAMILY_FIRST)`` (:ref:`name-order`).
:doc:`suggest` has the full rules, how many names each population took
to be read right, and the evidence it reports.

Names from several sources: ``matching``
----------------------------------------

Could ``John A. Smith`` in one source and ``J. Smith`` in another be
the same person? :meth:`Parser.matching() <nameparser.Parser.matching>`
builds a :class:`~nameparser.Matching` that answers field by field. Its ``keys()`` gives each name a few short strings to group
records by, so that you compare only the names that share one:

.. doctest::

    >>> matcher = Parser().matching()
    >>> sorted(matcher.keys("Jane A. de la Vega"))
    ['delavega;j', 'vega;j']

Its ``check()`` compares a pair and returns a
:class:`~nameparser.MatchResult` saying, for each field, how the two
compare:

.. doctest::

    >>> pair = matcher.check("John A. Smith", "J. Smith")
    >>> pair.consistent, pair["given"].outcome.value
    (True, 'initial')
    >>> matcher.check("Jane Smith", "John Smith").consistent
    False

Parse each source with the parser that reads it: ``check()`` compares
names as they were parsed, so two sources need not share an order. Read
with the default parser, the registry's ``Priem`` is a given name and
the pair does not match:

.. doctest::

    >>> registry = Parser().suggest(["Priem Jason", "Kim Minjun",
    ...                              "Wang Xiaoming", "Nguyen Anh"]).parser
    >>> matcher.check(registry.parse("Priem Jason"), parse("J. Priem")).consistent
    True
    >>> matcher.check("Priem Jason", "J. Priem").consistent
    False

A pair is consistent when every field compares in a way the matcher
accepts: by default the same name, an initial against its name, or a
middle name on one side only, among others. Some outcomes are opt-in
(``Bill`` against ``William``), and a name with no family name, such
as a lone ``Suharto``, gets no key and matches nothing, itself
included. It is not proof of the same person, so combine it with your own
evidence (dates, places, identifiers), and it is not transitive:
``J. Smith`` matches both ``John Smith`` and ``Jane Smith``. :doc:`matching` covers the outcomes it accepts and how
to accept more.

Where to go next
----------------

.. list-table::
   :header-rows: 1
   :widths: 45 25

   * - I want to…
     - Read
   * - get more out of a parsed name: aggregate views, strings, case, the guesses it reports, tokens, corrections, the command line
     - :doc:`usage`
   * - know what the parser does with a given input form
     - :doc:`shapes`
   * - read Chinese, Japanese or Korean names
     - :doc:`east-asian`
   * - understand how ``suggest`` decides
     - :doc:`suggest`
   * - join records from several sources
     - :doc:`matching`
   * - change which words the parser knows
     - :doc:`customize`
   * - change how the parser reads positions and punctuation
     - :doc:`policy`
   * - read names in a language I know
     - :doc:`locales`, :doc:`languages`
   * - understand how the parser works
     - :doc:`concepts`
   * - upgrade from 1.x or 2.x
     - :doc:`migrate`
