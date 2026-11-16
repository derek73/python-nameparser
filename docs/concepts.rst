How the parser works
====================

``parse()`` turns a name string into a
:class:`~nameparser.ParsedName`. This page explains the model behind
that call: how a string becomes tokens and tokens become fields, how
those tokens get their roles, where configuration lives and why it is
split the way it is, why parsers are plain values, and what happens
when a name is genuinely ambiguous. The task pages all build on these
five ideas.

From string to name
--------------------

Every parse follows the same path: the input string is split into
:class:`tokens <nameparser.Token>`, each token is assigned one of the seven roles — ``title``,
``given``, ``middle``, ``family``, ``suffix``, ``nickname``,
``maiden`` — and every string you read off the result is computed
from those tokens at read time.

.. doctest::

    >>> from nameparser import parse
    >>> vega = parse("Dr. Juan Q. Xavier de la Vega III")
    >>> for vega_tok in vega.tokens:
    ...     print(f"{vega_tok.text:7} {vega_tok.role.value}")
    Dr.     title
    Juan    given
    Q.      middle
    Xavier  middle
    de      family
    la      family
    Vega    family
    III     suffix
    >>> vega.family
    'de la Vega'

The name has eight tokens. ``de``, ``la`` and ``Vega`` each carry the
``family`` role, which is why ``vega.family`` returns ``"de la Vega"``:
the field is a view that joins the family-role tokens in order, not a
stored string.

Spans: where a token came from
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Each token also records where it came from. A :class:`~nameparser.Span` is a pair of
character positions bounding the token in the original string:

.. doctest::

    >>> vega.tokens[0].span
    Span(start=0, end=3)
    >>> vega.original[0:3]
    'Dr.'

Internally, spans let the pipeline refer to a token by position instead
of by text. A name can hold the same word twice, and a position cannot
be confused with a look-alike.

Tags: how a token was classified
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

:class:`Tokens <nameparser.Token>` also carry tags — a second, independent label alongside their
role, recording how a token was classified rather than what part of
the name it belongs to. Only a handful of them are part of the
stable API, collected in :data:`~nameparser.STABLE_TAGS`: ``particle``,
``conjunction``, ``initial``, and ``joined``.

.. doctest::

    >>> [vega_tok.text for vega_tok in vega.tokens if "particle" in vega_tok.tags]
    ['de', 'la']

Any tag written with a namespace prefix, like ``vocab:...``, is
provenance information for debugging how a token got classified. It
can change shape between releases, so if you need to branch on how a
token was classified, branch on role or on one of the stable tags
above, not on a namespaced one.

A parsed name is frozen
~~~~~~~~~~~~~~~~~~~~~~~

:class:`~nameparser.ParsedName` is frozen: there is no attribute
assignment, ever. If a parse is almost right and you want to fix one
field, you call ``.replace()``, which returns a new
:class:`~nameparser.ParsedName` with that field changed and everything
else — tokens, spans, the rest of the roles — carried over unchanged
(``replace()`` tokens carry no vocabulary classification;
:meth:`Parser.revise <nameparser.Parser.revise>` classifies the new
value the way a parse of that value on its own would).
``str()`` renders the default view; nothing about calling it mutates
the value you called it on.

The terms these pages use
~~~~~~~~~~~~~~~~~~~~~~~~~

Four words recur through the documentation, each naming something you
can inspect:

**role**
    The field a token belongs to, one of the seven members of
    :class:`~nameparser.Role`. Every token has exactly one, on
    ``Token.role``.

**tag**
    A label saying how a token was classified, on ``Token.tags``. A
    token has any number of them, and they do not depend on its role.

**reading**
    One way of reading a word. The vocabulary lists the readings a
    word *may* take (a title, a particle, a given name), which
    :meth:`Lexicon.readings_of() <nameparser.Lexicon.readings_of>`
    shows. A parse *takes* one of them for each word where it stands,
    on ``Token.reading`` (a :class:`~nameparser.Reading`). These pages
    also speak of the reading of a whole name, meaning the fields a
    parse gave it.

**ambiguity**
    A call the parse made that could legitimately have gone the other
    way, recorded on ``ParsedName.ambiguities`` with the reading it did
    not take (an :class:`~nameparser.Ambiguity`).

One name shows the last two. ``van`` may be read two ways, the parse
takes one, and it records the other:

.. doctest::

    >>> from nameparser import Lexicon
    >>> [van_reading.kind for van_reading in Lexicon.default().readings_of("van")]
    ['preposition', 'given']
    >>> van_quill = parse("Van Quill")
    >>> van_quill.tokens[0].reading.kind.value
    'name'
    >>> van_quill.ambiguities[0].alternative.kind.value
    'particle'

How roles are decided
---------------------

Roles are not assigned in one pass. Three things decide a word's role:
what the vocabulary says the word may be, where the word stands, and
how the word is written.

Vocabulary: what a word may be
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

The vocabulary is consulted first. It lists the words that are
something other than a plain name word: titles, particles,
conjunctions and post-nominal suffixes. Text set off by nickname or
maiden delimiters is set aside too, before position is asked anything
(:ref:`nicknames-and-maiden-names`).

A listed word takes its reading where a word of that kind stands, and
the listed words join their neighbours:

- **Titles chain**, so ``"Asst. Vice Chancellor"`` in front of a name
  is one title.
- **A title that is also a given name**, such as ``Dean``, is a title
  only inside such a phrase (``"Dean of Students"``).
- **Particles join forward**, so ``de la`` attaches to ``Vega``.

A listing is not a role, though. The same word can play different parts
in different places: ``Lt.`` is a title before a name and a post-nominal
after it, which is why the field names ``title`` and ``suffix`` are
really "pre-nominal" and "post-nominal".

.. doctest::

    >>> parse("Lt. Mara Quill").title
    'Lt.'
    >>> parse("Mara Quill, Lt.").suffix
    'Lt.'

Position: where a word stands
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Whatever the vocabulary has not claimed is assigned purely by where it
sits: the first unclaimed word is the given name, the last is the
family name, and anything between them is the middle name.

.. doctest::

    >>> quill = parse("Mara Lee Ann Quill")
    >>> quill.given, quill.middle, quill.family
    ('Mara', 'Lee Ann', 'Quill')

That is the default arrangement. What changes "first" and "last":

- **A comma between the family name and the given name**
  (``Quill, Mara``) puts the family name first, whatever order is set.
  A comma that only sets off suffixes leaves the order alone
  (:ref:`name-order`).
- ``name_order`` declares that your records write the family name
  first without a comma (:ref:`name-order`).
- ``script_orders`` reads a name family-first by the script it is
  written in, by default a name wholly in Han or Hangul, or in kanji
  and kana other than katakana alone
  (:ref:`east-asian-defaults`; :ref:`east-asian-names` has the
  conventions behind it and the transcribed names it leaves alone).
- ``two_family_names``, opt-in, reads two name words as the family
  name (:ref:`two-family-names`).
- ``two_given_names``, opt-in, gives the given name the middle name
  beside it (:ref:`two-given-names`).
- ``lone_name_word`` decides a name of one name word, which has no
  first and last to tell apart: the given name by default, under every
  ``name_order`` (:ref:`lone-name-word`, which also lists what decides
  the word before the setting is asked).
- ``patronymic_rules``, opt-in, reorder a name whose patronymic marks
  its parts, under the default order (:ref:`east-slavic-patronymics`,
  :ref:`turkic-patronymic-markers`, :ref:`patronymic-packs-family-first`).
- ``initials_as_family`` and ``capitals_as_family``, opt-in, read the
  family name from letters ending a name or from words written in
  capitals (:ref:`initials-as-family`, :ref:`capitals-as-family`).
- **The vocabulary answers before the order** in a few places: a
  particle that can never be a given name, opening the name, opens the
  surname under every order, and a lone name word beside a given-name
  title such as ``Sir`` is the given name
  (:ref:`order-vocabulary-first`).

Every field that changes how a name is arranged is a row of the table
in :doc:`policy`.

Writing: how a word is written
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

A few words are read by how they are written, which is neither a list
lookup nor position alone: the writing proposes a reading, and where
the word stands decides whether it lands. Two examples:

- **A period at the end of an unlisted word.** A word of two or more
  letters with a single period at its end, at the front of the
  given-name part, is a title though no list holds it
  (:ref:`abbreviated-titles`).
- **An unlisted acronym.** One written in periods (``X.Y.Z.``) is a
  credential behind a name that can spare it. One written in capitals
  (``XYZ``) is too, by default only right after a comma behind a full
  name (:ref:`unlisted-credentials` says exactly where).

.. doctest::

    >>> parse("Insp. Mara Quill").title
    'Insp.'
    >>> parse("Insp Mara Quill").given          # no period: a name word
    'Insp'
    >>> parse("Mara Quill X.Y.Z.").suffix
    'X.Y.Z.'
    >>> parse("Mara Quill, XYZ").suffix
    'XYZ'
    >>> parse("Mara Quill XYZ").family          # no comma: a name word
    'XYZ'

It never detects language
~~~~~~~~~~~~~~~~~~~~~~~~~

The parser never detects the language of a name. A name written in
Latin letters does not say which language it is in, and the same word
is a particle in one language and a given name in another, so a guess
would misread real people. The same word is read by where it stands
instead, in every name alike:

.. doctest::

    >>> parse("Mara van Quill").family          # between two names: a particle
    'van Quill'
    >>> parse("Van Quill").given                # opening the name: a given name
    'Van'

The second reading is one the parser cannot be sure of, and it says so
(`When two readings are both legitimate`_). A rule that belongs to one
language is something you turn on: a :class:`~nameparser.Lexicon` edit,
a :class:`~nameparser.Policy` field, or a locale pack (`Locale packs: a
declared language`_).

The one exception is a name in its native script, and only where the
script itself, rather than statistics about it, settles the convention:
a name written wholly in Han characters or Hangul is read family-first,
because every language written in those scripts orders names that way
(:ref:`east-asian-names`). The same name in Latin letters is read by
position like any other:

.. doctest::

    >>> parse("김민준").family
    '김'
    >>> parse("Kim Minjun").family
    'Minjun'

A whole list is a different question. :meth:`Parser.suggest()
<nameparser.Parser.suggest>` may detect a convention over a group of
names you declare to be one source. It says what it saw, and its answer
is configuration you apply: no parse changes by itself
(:ref:`suggest-settings`).

What follows from this
~~~~~~~~~~~~~~~~~~~~~~

That is the whole parser in outline, and it explains its
character. A word nameparser has never seen still gets a sensible role,
because position does not need to recognize anything. And nothing in a
parse is statistical: there is no model and no training data, so
the same input always parses the same way, and a parse that is wrong is
wrong reproducibly, which is what makes it fixable by configuration.

.. _config-containers:

Configuration lives in three containers
----------------------------------------

Every piece of nameparser configuration falls into exactly one of
three places, and which one is decided by a single question: what does
this setting vary with?

.. list-table::
   :header-rows: 1
   :widths: 22 22 34 22

   * - Varies by
     - Container
     - Holds
     - Example
   * - **language**
     - :class:`~nameparser.Lexicon` (:ref:`vocabulary-lexicon`)
     - The vocabulary, written as readings: what each word may be read
       as, each held in the file of the language whose names it occurs
       in.
     - Reading ``Dean`` as a title everywhere
   * - **data source or application**
     - :class:`~nameparser.Policy` (:doc:`policy`)
     - The behavior switches: name order, patronymic rules, delimiters,
       strip flags, where unlisted credentials are read. Anything that
       changes how words are arranged, not what words are recognized.
     - Nicknames in square brackets
   * - **output destination**
     - :ref:`Rendering arguments <rendering-arguments>`
     - The ``spec`` you pass to ``render(spec)``, or a keyword to
       ``initials()`` or ``capitalized()``.
     - "Family, Given" for one report

Each example, run. "Dean" is a common given name, so the default reads
it as a title only inside a title phrase; in some data it is more
common as a title. The right reading is a fact about the domain the
names come from, which makes it a :class:`~nameparser.Lexicon` entry:

.. doctest::

    >>> from nameparser import Parser
    >>> parse("Dean Quill").given
    'Dean'
    >>> dean_title = Parser(lexicon=Lexicon.default().remove("dean", kind="given"))
    >>> dean_title.parse("Dean Quill").title
    'Dean'

A CRM that wraps nicknames in square brackets instead of quotes is a
fact about that one data source's export format, not about the language
of the names in it, which makes it a :class:`~nameparser.Policy` field
(:ref:`brackets`):

.. doctest::

    >>> from nameparser import DEFAULT_NICKNAME_DELIMITERS, Policy
    >>> parse("Mara [Mimi] Quill").nickname
    ''
    >>> square = Parser(policy=Policy(
    ...     nickname_delimiters=DEFAULT_NICKNAME_DELIMITERS | {("[", "]")}))
    >>> square.parse("Mara [Mimi] Quill").nickname
    'Mimi'

One report wanting "Family, Given" while every other consumer of the
same parsed data wants "Given Family" is a fact about where the string
is going next, decided at the moment you render it. That makes it a
rendering argument, not something baked into how the name was parsed:

.. doctest::

    >>> mara = parse("Mara Quill")
    >>> str(mara), mara.render("{family}, {given}")
    ('Mara Quill', 'Quill, Mara')

1.x kept all three in one mutable configuration object; :doc:`migrate`
maps each of its attributes to its container.

Locale packs: a declared language
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Use a locale pack when you know which language or convention your
names follow and the default reads them another way (:doc:`locales`
says which names need one). The default lexicon reads every language's words at
once, which is why it serves data whose language nobody can declare.
Where you can declare it, a :class:`~nameparser.Locale` carries the
declaration, in up to three parts that
:func:`~nameparser.parser_for` applies together:

- **A choice of languages**, which selects among the shipped readings
  by the files they are written in (:ref:`choosing-languages`).
- **A lexicon fragment**, words of its own.
- **A policy patch**, the ``Policy`` fields the convention needs.

A **locale pack**, or pack, is a :class:`~nameparser.Locale` that
nameparser ships; :ref:`shipped-packs` lists them. The Spanish pack,
for one, reads two family names where the default reads a middle name:

.. doctest::

    >>> from nameparser import locales, parser_for
    >>> parse("Mara Brandt Quill").family
    'Quill'
    >>> parser_for(locales.ES).parse("Mara Brandt Quill").family
    'Brandt Quill'

Parsers are values
--------------------

``parse()`` is a convenience function over a module-level default
:class:`~nameparser.Parser`. You only need to build your own
:class:`~nameparser.Parser` (directly, or via
:func:`~nameparser.parser_for`) when you want non-default vocabulary
or behavior — and when you do, build it once and reuse it. Constructing
a :class:`~nameparser.Parser` validates its configuration up front, so
it's cheap but not free; parsing individual names is the hot path, and
a :class:`~nameparser.Parser` is designed to be called many times
without reconstruction.

:class:`~nameparser.Lexicon`, :class:`~nameparser.Policy`,
:class:`~nameparser.Parser`, and :class:`~nameparser.ParsedName` are
all frozen and hashable. That means they're safe to share across
threads without locking, safe to use as dict keys or cache keys, and
equality means exactly what it says — two :class:`~nameparser.Parser`
instances built from equal configuration are equal values, not merely
two objects that happen to behave the same. Every piece of
configuration is a frozen value — including the
module-level default parser itself.

.. doctest::

    >>> Parser() == Parser(), Parser() is Parser()
    (True, False)

Honest ambiguity
------------------

Parsing never raises
~~~~~~~~~~~~~~~~~~~~

Pass in any string and you get back a
:class:`~nameparser.ParsedName`, not an exception. The parser's job is
to make a reasonable call on real-world text, not to reject it: a
string with nothing in it to read gives a name with every field empty,
which is falsy, and anything else gets its best reading.

.. doctest::

    >>> bool(parse("???"))
    False
    >>> parse("12345").given
    '12345'

The single exception is code you supplied yourself: a
:data:`~nameparser.Segmenter` passed to ``Parser(segmenter=...)`` runs
inside the parse, and its own exceptions propagate rather than being
swallowed — a failure there is a bug in your callable, not a fact
about the name (:ref:`segmenter-contract`).

When two readings are both legitimate
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

A parse you disagree with is not always a bug. Some calls are
irreducibly ambiguous — both readings are legitimate, and no amount of
rule-tuning resolves them without breaking some other name. Those
surface as entries on ``ParsedName.ambiguities`` instead of being
silently guessed away.

The canonical example: a leading "Van" reads as a name of its own
rather than as the start of a surname — the right call for the actor
Van Johnson, the wrong one for a bare "Van Buren", and nothing in the
two-word shape distinguishes them — so the parse records a
``particle-or-given`` ambiguity alongside its answer:

.. doctest::

    >>> [amb.kind.value for amb in parse("Van Buren").ambiguities]
    ['particle-or-given']

You can inspect ``ambiguities`` to decide, case by case, whether your
data needs a second look (:ref:`parser-guesses`); each report also
names the reading it did not take (:ref:`reading-not-taken`).

An ambiguity records a decision, not a word
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

An ambiguity records a *decision*, not a word. The same token in a
different position may present no fork at all: ``do`` is in the
ambiguous post-nominal vocabulary, but in ``"Joao da Silva do Amaral
de Souza"`` it sits mid-name, where nothing has to choose between
readings — so nothing is recorded. At the end of a name there is a
choice to make, and it is:

.. doctest::

    >>> parse("Joao da Silva do Amaral de Souza").ambiguities
    ()
    >>> [amb.kind.value for amb in parse("Mara Lee Quill do").ambiguities]
    ['suffix-or-name']

What decides whether there was a decision:

- **A comma can settle the question before it arises.** ``"Ma, Jack"``
  fixes the family name, so the credential reading never comes up.
- **So can the writing.** ``"John Smith M.A."`` and, in a mixed-case
  name, ``"John Smith MA"`` are written as credentials, while
  ``"John Smith Ma"`` has to call it and says so
  (:ref:`credentials-also-surnames`).
- **A convention is a decision too.** A name of one name word has
  nothing to compare, so where nothing else decides the word, the field
  it lands in is reported as ``given-or-family``. :ref:`lone-name-word`
  lists what can decide it; the word's own vocabulary or shape can as
  well (a lone ``J.`` reports nothing). An input of nothing but titles can
  leave one last title word, which is read as the name for want of
  anything else (``"Dr. Prof."``) and reported as ``title-or-name``. A field the
  library merely had to pick is a field you can see it picked.
- **A title standing entirely alone reports nothing.** ``"Dr."``,
  ``"Sir"`` and ``"Prince of Wales"`` are all title and no name, so
  there is no reading to have doubted.

An empty list is not certainty
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

An empty ``ambiguities`` is not a certificate of certainty.
Reporting is deliberately partial: :class:`~nameparser.AmbiguityKind`
lists the forks worth flagging, and even those are not reported
everywhere they occur. What a comma buys is narrower than it looks —
it names which words are the surname, and stays quiet about that
much, but it leaves the rest of the name to be read as usual, so
``"Beethoven, Ludwig van"`` still reports the trailing ``van`` it had
to call. Coverage grows over releases. Treat a non-empty
``ambiguities`` as a signal to act on; do not read an empty one as a
guarantee.
