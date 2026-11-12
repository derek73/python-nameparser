.. _getting-started:

Getting started
===============

Three steps, in the order most people need them: read one name, let a
list of names choose the settings, and compare names from several
sources. Each links to the page that covers it in full.

Install it with ``pip install nameparser``. It needs Python 3.11 or
later and nothing else. The one optional extra, ``nameparser[ja]``,
divides unspaced Japanese kanji names (:ref:`east-asian-names`).

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

A single name cannot always show how it was written. ``Priem Jason``
and ``Jason Priem`` have the same shape, and only a reader who knows
that ``Priem`` is a surname can tell which word is the family name. A
list of names from one source can show it, because a source usually
writes every name the same way (a registry family name first, a mailing
list family name last), and many of its names carry some evidence of
the order.

:meth:`Parser.suggest() <nameparser.Parser.suggest>` reads a list you
declare to be one group and returns a :class:`~nameparser.Suggestion`.
Its ``parser`` is a parser configured for the list:

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
shows the evidence for each setting it considered, and the names that
voted against the decision, which are the ones to check by hand:

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
Korean or Vietnamese surname, or a common given name, at one end; a
family name written in capitals; a lowercase particle; initials after
the name, as a bibliography writes them. ``suggest`` decides three
settings from it, and leaves every other one as the parser you called
it on has it:

- **The name order** (:ref:`name-order`): given name first, or family
  name first.
- **A patronymic rule** (:class:`~nameparser.PatronymicRule`): East
  Slavic or Turkic, where at least five names, and more than four in
  five of the names that vote, carry that patronymic.
- **Letters as the family name** (:ref:`initials-as-family`): where
  the list repeats the same letters at the end of its names, as Nepal's
  ``B K`` and ``K C`` are family names written short.

Choose the language first
~~~~~~~~~~~~~~~~~~~~~~~~~

``suggest`` never chooses a language. A language pack does
(:doc:`locales`), so where you know the list's language, choose its
pack and call ``suggest`` on that parser. This Spanish list writes the family
names first; the default parser, told only the order, reads the second
family name as the given name, while the Spanish pack reads the two
family names and ``suggest`` adds the order:

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

``suggest`` changes a setting only where enough names agree, and keeps
the base parser's value otherwise. It needs at least two names voting
for one order, and more than two thirds of the names that vote. A name
of one word casts no vote, and neither does a name with a comma, which
states its own order (unless only post-nominals follow the comma, as in
``Zhang Wei, PhD``). In this list only ``Mary``, a common given name,
votes, one vote short, so nothing is suggested:

.. doctest::

    >>> Parser().suggest(["Smith John", "Jones Mary"]).patch
    PolicyPatch()

Initials after the name vote only where at least three names, and 60%
of the list, end in them, so a short list of bylines may get no order
suggestion:

.. doctest::

    >>> Parser().suggest(["Smith J", "Jones M"]).patch
    PolicyPatch()
    >>> Parser().suggest(["Smith J", "Jones M", "Brown K"]).patch
    PolicyPatch(name_order=FAMILY_FIRST)

Where you know a list is bylines, set the order yourself with
``Policy(name_order=FAMILY_FIRST)`` (:ref:`name-order`).
:doc:`suggest` has the full rules, how many names each population took
to be read right, and the evidence it reports.

Names from several sources: ``matching``
----------------------------------------

Joining records from several sources asks whether two names could
belong to the same person. One source writes ``John A. Smith``, another
``J. Smith``. :meth:`Parser.matching() <nameparser.Parser.matching>`
builds a :class:`~nameparser.Matching` that answers this field by
field. Its ``keys()`` gives each name a few short strings to group
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

Parse each source with the parser that reads it. A registry written
family name first reads right under the parser ``suggest`` gave it, and
``check()`` compares the names as they were parsed, so the two sources
need not share an order. Read with the default parser, the registry's
``Priem`` is a given name and the pair does not match:

.. doctest::

    >>> registry = Parser().suggest(["Priem Jason", "Kim Minjun",
    ...                              "Wang Xiaoming", "Nguyen Anh"]).parser
    >>> matcher.check(registry.parse("Priem Jason"), parse("J. Priem")).consistent
    True
    >>> matcher.check("Priem Jason", "J. Priem").consistent
    False

A consistent pair is one where nothing in the two names contradicts
the match. That does not make them the same person: ``J. Smith`` is
consistent with many people. Combine the answer with your own
evidence, such as dates, places or identifiers. Consistency is not
transitive either, so ``J. Smith`` can match both ``John Smith`` and
``Jane Smith``. :doc:`matching` covers the outcomes it accepts and how
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
