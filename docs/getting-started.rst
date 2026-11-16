.. _getting-started:

Getting started
===============

Three steps, in the order most people need them: read one name, let a
list of names choose the settings, and compare names from several
sources. Each links to the page that covers it in full, and `When a
name is read wrong`_ says what to try when a reading does not suit your
data.

Install it with ``pip install nameparser``. It needs Python 3.11 or
later and no other package.

The parser reads a name by the position of its words and never guesses
its language. A Chinese, Japanese or Korean name written in its own
script is read family name first without configuration, save a name in
katakana alone, which keeps the order it is written in. Where such a
name is written with no space between its parts, a Korean one is
divided by default, a Chinese one by the ``zh`` pack, and a Japanese
one by the ``ja`` pack with a segmenter, which the optional extra
``nameparser[ja]`` installs (:ref:`splitting-unspaced-names`).

The conventions of one language, such as two family names in Spanish or
the patronymic in Russian, are packs you turn on when you know your
data's language: :doc:`locales` says whether your names need one.

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

For a column of names, build one :class:`~nameparser.Parser` and call
its ``parse`` on each:

.. doctest::

    >>> from nameparser import Parser
    >>> column = ["Dr. Ann Berg", "Ruiz, Marta", "Tom de la Cruz Jr."]
    >>> reader = Parser()
    >>> [reader.parse(text).family for text in column]
    ['Berg', 'Ruiz', 'de la Cruz']

A list of names: let ``suggest`` choose the settings
-----------------------------------------------------

One name often cannot show its order: in ``Taylor Morgan`` either word
could be the family name, and a reader cannot tell which any more than
the parser can. A list from one source can, because a source writes
every name the same way and many of its names carry evidence of the
order.

:meth:`Parser.suggest() <nameparser.Parser.suggest>` reads a list you
declare to be one group and returns a :class:`~nameparser.Suggestion`.
Parse the list's names with its ``parser``:

.. doctest::

    >>> listing = ["Taylor Morgan", "Kim Minjun", "Wang Xiaoming",
    ...            "Nguyen Anh", "Garcia Emily"]
    >>> suggestion = Parser().suggest(listing)
    >>> suggestion.patch
    PolicyPatch(name_order=FAMILY_FIRST)
    >>> parse("Taylor Morgan").given
    'Taylor'
    >>> suggestion.parser.parse("Taylor Morgan").given
    'Morgan'
    >>> [suggestion.parser.parse(text).family for text in listing]
    ['Taylor', 'Kim', 'Wang', 'Nguyen', 'Garcia']

``suggest`` reads its argument once, so pass it a list, not a
``csv.reader`` you mean to loop over again to parse the names.

``patch`` holds the settings the list changed. Printing the suggestion
shows the evidence for each setting and any names that voted against
it, and ``suggestion.base`` is the parser you started from:

.. doctest::

    >>> print(suggestion)
    Suggested for 5 names (base: Parser(Lexicon(default), Policy())):
      name_order  FAMILY_FIRST  4 for, 0 against, 1 no evidence
          surname FAMILY_FIRST  3
          given-name FAMILY_FIRST  2
      patronymic_rules  unchanged (none)  no evidence
      initials_as_family  unchanged (False)  no evidence
      capitals_as_family  unchanged (False)  5 for, 0 against, 0 no evidence

Each setting counts its names for and against the value the suggested
parser has: all five names are in mixed case with no word in capitals,
so they are evidence for leaving ``capitals_as_family`` off.

Four names vote for family first: ``Kim``, ``Wang`` and ``Nguyen`` by
the romanized surname in front, ``Garcia Emily`` by the common given
name at the end (``Garcia`` is not one of the surnames ``suggest``
reads). ``Wang Xiaoming`` carries both kinds, so the surname and
given-name rows count it once each.

``Taylor Morgan`` gives no evidence, so the suggested parser reads it
family first only because the rest of the list is written that way;
nothing in the name itself can confirm that reading. A name written the
other way round that carries evidence (``Emily Clark``) votes against
the list, and is the one to check by hand (see :ref:`a name that
disagrees <suggest-disagreeing>`).

What ``suggest`` decides
~~~~~~~~~~~~~~~~~~~~~~~~

The evidence is in the names themselves: a common romanized Chinese,
Korean or Vietnamese surname, or a common given name that is rarely
a surname (``Mary``, not ``James``), at one end; a
family name written in capitals; a lowercase particle; initials after
the name, as a bibliography writes them (:ref:`suggest-evidence`).

``suggest`` decides four settings from it, each only where enough of
the list's names carry its evidence, and leaves every other one as the
parser you called it on has it:

- **The name order** (:ref:`name-order`): given name first, or family
  name first (:ref:`suggest-deciding`).
- **A patronymic rule** (:class:`~nameparser.PatronymicRule`): East
  Slavic or Turkic, for a list whose names carry that patronymic
  (:ref:`suggest-patronymics`).
- **Letters as the family name** (:ref:`initials-as-family`): for a
  list whose names end in the same run of letters, as Nepal's ``B K``
  and ``K C`` are family names written short, and only on a base that
  reads given names first (:ref:`suggest-initials`).
- **Family names in capitals** (:ref:`capitals-as-family`): for a list
  that writes the family name in capitals of four letters or more
  (``Mary SMITH``) (:ref:`suggest-capitals`).

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

Where you know the order a list is written in, set it yourself with
``Policy(name_order=FAMILY_FIRST)`` (:ref:`name-order`): ``suggest``
is for a list whose conventions you do not know.

Where too few of a list's names agree, ``suggest`` keeps the base
parser's value rather than guess. Here only ``Mary`` votes (``James``
is also a surname), and one name does not decide a list:

.. doctest::

    >>> Parser().suggest(["Smith James", "Jones Mary"]).patch
    PolicyPatch()

So a short list may get no suggestion, a short list of bylines
included:

.. doctest::

    >>> Parser().suggest(["Smith J", "Jones M"]).patch
    PolicyPatch()

:ref:`suggest-limits` says how many names each kind of list took to be
read right, and :doc:`suggest` has the full rules and the evidence it
reports.

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
with the default parser, the registry's ``Taylor`` is a given name and
the pair does not match:

.. doctest::

    >>> registry = Parser().suggest(["Taylor Morgan", "Kim Minjun",
    ...                              "Wang Xiaoming", "Nguyen Anh"]).parser
    >>> matcher.check(registry.parse("Taylor Morgan"), parse("M. Taylor")).consistent
    True
    >>> matcher.check("Taylor Morgan", "M. Taylor").consistent
    False

A pair is consistent when every field compares in a way the matcher
accepts: by default the same name, an initial against its name, or a
middle name on one side only, among others. Some outcomes are opt-in
(``Bill`` against ``William``), and a name with no family name, such
as a lone ``Suharto``, gets no key and matches nothing, itself
included. Read the answer from ``consistent``: a result has no truth
value, so ``if matcher.check(a, b):`` raises ``TypeError``.

It is not proof of the same person, so combine it with your own
evidence (dates, places, identifiers). It is not transitive either:
``J. Smith`` matches both ``John Smith`` and ``Jane Smith``.
:doc:`matching` covers the outcomes it accepts and how to accept more.

When a name is read wrong
-------------------------

A reading that is wrong for your data is often a convention the parser
was not told about, such as the order a source writes its names in.
Try these in order:

#. **See whether the parser guessed.** ``ambiguities`` names the other
   reading where the text allowed two (:ref:`parser-guesses`).
#. **Let the list choose** where the names come from one source (`A
   list of names: let suggest choose the settings`_).
#. **Choose the language** where you know it: a pack reads its
   conventions (:doc:`locales`).
#. **Change one setting or one word**: a :class:`~nameparser.Policy`
   field says how positions and punctuation are read (:doc:`policy`),
   and a :class:`~nameparser.Lexicon` edit how one word is read
   (:doc:`customize`).

If the reading still looks wrong, `open an issue
<https://github.com/derek73/python-nameparser/issues>`__ with the name
and the reading you expected.

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
   * - see why a name was read the way it was
     - :ref:`parser-guesses`
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
