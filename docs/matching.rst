.. _matching-names:

Matching names across sources
=============================

``matches()`` asks whether two writings are the same name. Joining
records from several sources asks something looser: could these two
names belong to the same person? One source writes ``John A. Smith``,
another ``J. Smith``, a third ``JOHN SMITH JR.``. A name matcher
answers that question role by role, using the parse to know which
words are the family name, which are particles and which are initials,
and says *why* for every pair. It never scores a pair: combine its
answer with your own evidence (coauthors, institutions, identifiers)
and set your own thresholds.

The workflow is four steps:

#. Parse each source with its own :class:`~nameparser.Policy`, so two
   sources that write names in different orders each read correctly.
#. Build one :class:`~nameparser.Matching` from a parser with
   :meth:`Parser.matching() <nameparser.Parser.matching>`, and use it
   for both of the steps below.
#. Group the names by ``keys()``.
#. Within each group, ``check()`` each pair.

.. _matching-grouping-keys:

Grouping by key
---------------

``keys()`` gives each name a set of short strings, the family name's
words without their particles, and the whole family name joined (its
spaces and hyphens dropped, particles kept), each beside the given
name's first letter. A key is folded and writes ``ae``, ``oe``, ``ue``,
``aa`` and ``dj`` as their first letter, so ``Müller``, ``Mueller`` and
``Muller`` share one; a key is no spelling of the name, only a bucket.
Two names ``check()`` calls consistent always share a key, so grouping
by key loses no match, and a pair that shares no key need never be
checked:

.. doctest::

    >>> from collections import defaultdict
    >>> from nameparser import Parser
    >>> matcher = Parser().matching()
    >>> sorted(matcher.keys("Jane A. de la Vega"))
    ['delavega;j', 'vega;j']
    >>> groups = defaultdict(list)
    >>> for written in ["John A. Smith", "J. Smith", "Juan de la Vega", "Juan Vega"]:
    ...     for key in matcher.keys(written):
    ...         groups[key].append(written)
    >>> dict(sorted(groups.items()))
    {'delavega;j': ['Juan de la Vega'], 'smith;j': ['John A. Smith', 'J. Smith'], 'vega;j': ['Juan de la Vega', 'Juan Vega']}

A family name of several words gets a key for each, because a source
may cut a surname list short, and a hyphenated one a key for each half,
for the two joined and for the whole word, save a half that is a
particle (``Al-Saud`` keys ``saud``, ``alsaud`` and ``al-saud``, never
``al``):

.. doctest::

    >>> sorted(matcher.keys("Mary Smith-Jones"))
    ['jones;m', 'smith-jones;m', 'smith;m', 'smithjones;m']

A key only gathers candidates: ``Jane Smith`` shares ``smith;j`` with
``John Smith``, and ``check()`` is what tells them apart. A name with
no family name, such as a lone ``Suharto`` (read as a given name, see
:ref:`lone-name-word`), gets no key and is consistent with nothing by
default, since the family name must be present on both sides and
agree; the search for other readings
(:ref:`matching-other-readings`) reaches it through its family reading.
A list of such names against one that writes a given name too is
under :ref:`matching-given-one-side`, and a convention with no
inherited family name under
:ref:`matching-without-an-inherited-family-name`.

.. _matching-group-sizes:

How large the groups get
~~~~~~~~~~~~~~~~~~~~~~~~

A key is a family name and a given letter, so a common surname makes a
large group, and the pairs to check grow with the square of a group's
size: every Smith whose given name starts with J is in ``smith;j``.
It is the family names your data holds most of that set the cost.

Each outcome you accept beyond the default, save ``hyphenated-part``,
can add keys to a name, and the ``other_readings`` switch adds those
of each other reading it tries, so the groups grow in number and in
size
(:ref:`matching-accepting-more` says what each adds):

.. doctest::

    >>> from nameparser import Outcome
    >>> every_opt_in = Parser().matching(
    ...     accept=[o for o in Outcome if o is not Outcome.CONFLICT],
    ...     other_readings=True)
    >>> sorted(matcher.keys("Bill Smith"))
    ['smith;b']
    >>> sorted(every_opt_in.keys("Bill Smith"))
    ['s', 's;b', 's;w', 'smith', 'smith;b', 'smith;w']

.. _matching-rebuilding-keys:

Store the names, not their keys
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

A key is a bucket cut from a parse, by one nameparser version under one
matcher's settings, not an identifier. Each of these moves a name's
keys:

- **The parser.** The same text keys differently under a parser that
  reads it in another order, or with another lexicon.
- **The release.** A release that reads a name differently moves its
  keys.
- **The matcher's settings.** Accepting another outcome adds the keys
  it needs, and so does switching on ``other_readings``.

So store the names, build the keys again after upgrading nameparser or
changing the parser or the accepted outcomes, and compare only keys
built the same way:

.. doctest::

    >>> from nameparser import FAMILY_FIRST, Policy
    >>> sorted(matcher.keys("Kim Minjun"))
    ['minjun;k']
    >>> sorted(Parser(policy=Policy(name_order=FAMILY_FIRST)).matching().keys("Kim Minjun"))
    ['kim;m']

Checking a pair
---------------

``check()`` takes two strings, parsed with the matcher's parser, or
two :class:`~nameparser.ParsedName` objects, compared as they were
parsed. It returns a :class:`~nameparser.MatchResult`: ``consistent``,
and in ``roles`` one :class:`~nameparser.RoleMatch` per field in field
order, each with its :class:`~nameparser.Outcome`, the text on each
side, and which :class:`~nameparser.Side` carried more of it. A row is
read by its field's name or :class:`~nameparser.Role`
(``result["family"]``), and ``weakest`` is the weakest row's outcome:

.. doctest::

    >>> smiths = matcher.check("John A. Smith", "J. Smith")
    >>> smiths.consistent
    True
    >>> for row in smiths.roles:
    ...     print(row.role.value, row.outcome.value, repr(row.left), repr(row.right), row.more.value)
    title same '' '' neither
    given initial 'John' 'J.' left
    middle one-side 'A.' '' left
    family same 'Smith' 'Smith' neither
    suffix same '' '' neither
    nickname same '' '' neither
    maiden same '' '' neither
    >>> smiths["given"].outcome.value, smiths.weakest.value
    ('initial', 'one-side')

**Consistent means nothing in the two names contradicts the match**,
under the outcomes accepted. It does not mean the two are the same
person: ``J. Smith`` is consistent with half the Smiths in a phone
book. The table is what lets you tell ``John A. Smith`` / ``John
Smith`` (only a middle initial missing) from ``J. Smith`` / ``John A.
Smith`` (most of the given name missing too), though both are
consistent. A pair is inconsistent when a role's outcome is
``conflict``, or one you have not accepted:

.. doctest::

    >>> johns = matcher.check("John Smith Jr.", "John Smith Sr.")
    >>> johns.consistent, johns["suffix"].outcome.value
    (False, 'conflict')

A conflict is a result too, so a result has no truth value: ``if
matcher.check(a, b):`` raises ``TypeError`` rather than take the
branch for every pair. Test ``consistent``:

.. doctest::

    >>> if johns:
    ...     print("same person")
    Traceback (most recent call last):
        ...
    TypeError: a MatchResult has no truth value, got bool() of one whose consistent is False: ...

The check is symmetric: swapping the two names gives the same verdict
and the same table with ``left`` and ``right`` exchanged
(``MatchResult.mirrored()``). Each source keeps its own order, so
names parsed under different policies compare correctly:

.. doctest::

    >>> from nameparser import FAMILY_FIRST, Policy
    >>> family_first_source = Parser(policy=Policy(name_order=FAMILY_FIRST))
    >>> matcher.check(family_first_source.parse("Smith John"), "John A. Smith").consistent
    True

.. _matching-recipe:

Linking two lists
~~~~~~~~~~~~~~~~~

The four steps together, for two lists read by one parser: bucket each
list's records by key, pair the two sides of each bucket, and check each
pair once. Bucket the records by their row numbers, not their text, so
two records written alike stay two. Two names can share more than one
key (the two writings of ``de la Cruz`` below share ``cruz;m`` and
``delacruz;m``), so collect the pairs in a set before checking them:

.. doctest::

    >>> from itertools import product
    >>> registry = ["Okafor, Ngozi A.", "Maria de la Cruz", "Tomas Lindqvist",
    ...             "Lindqvist, Tove", "Ana Cruz", "Suharto"]
    >>> payroll = ["N. Okafor", "MARÍA DE LA CRUZ", "T. Lindqvist",
    ...            "Nkem Okafor", "Lindqvist, Tomas Jr.", "T. Lindqvist"]
    >>> by_key = defaultdict(lambda: ([], []))
    >>> for side, source in enumerate((registry, payroll)):
    ...     for row, written in enumerate(source):
    ...         for key in matcher.keys(written):
    ...             by_key[key][side].append(row)
    >>> candidates = sorted({pair for ours, theirs in by_key.values()
    ...                      for pair in product(ours, theirs)})
    >>> len(candidates), len(registry) * len(payroll)
    (9, 36)
    >>> for ours, theirs in candidates:
    ...     linked = matcher.check(registry[ours], payroll[theirs])
    ...     print(ours, theirs, registry[ours], "|", payroll[theirs], "|",
    ...           linked.consistent, linked.weakest.value)
    0 0 Okafor, Ngozi A. | N. Okafor | True one-side
    0 3 Okafor, Ngozi A. | Nkem Okafor | False conflict
    1 1 Maria de la Cruz | MARÍA DE LA CRUZ | True folded
    2 2 Tomas Lindqvist | T. Lindqvist | True initial
    2 4 Tomas Lindqvist | Lindqvist, Tomas Jr. | True generation-one-side
    2 5 Tomas Lindqvist | T. Lindqvist | True initial
    3 2 Lindqvist, Tove | T. Lindqvist | True initial
    3 4 Lindqvist, Tove | Lindqvist, Tomas Jr. | False conflict
    3 5 Lindqvist, Tove | T. Lindqvist | True initial

Nine of the 36 pairs shared a key and were checked, and two of the
nine are not consistent: a key only gathers candidates. ``Ana Cruz``
shares no key with any record on the other list and is never checked.
Neither is the lone ``Suharto``, which has no key under the default,
so the recipe never reaches it (:ref:`matching-other-readings`).

To find the duplicates inside one list, bucket its row numbers the same
way and pair each bucket with itself (``itertools.combinations(rows,
2)``), collecting the pairs in a set as here. The rows of a bucket are
in order, so each pair comes out once.

Where the two lists need different parsers, parse each with its own
and pass the :class:`~nameparser.ParsedName` objects to ``keys()`` and
``check()``, as in the example before this one.

Each ``T. Lindqvist`` came out consistent with two people. The matcher
does not choose between them, and the next section says why you should
not merge the three.

.. _matching-not-transitive:

Consistency is not transitive
-----------------------------

``J. Smith`` is consistent with ``John Smith`` and with ``Jane
Smith``, which are not consistent with each other:

.. doctest::

    >>> matcher.check("J. Smith", "John Smith").consistent
    True
    >>> matcher.check("J. Smith", "Jane Smith").consistent
    True
    >>> matcher.check("John Smith", "Jane Smith").consistent
    False

So do not merge records by chaining consistent pairs: a less specific
name joins people a more specific one keeps apart. ``RoleMatch.more``
tells you which side carried more of each role, so of a consistent
pair, one name is a less specific writing of the other when no role
has it carrying more:

.. doctest::

    >>> def less_specific(result):
    ...     return all(row.more.value != "left" for row in result.roles)
    >>> less_specific(matcher.check("J. Smith", "John A. Smith"))
    True
    >>> less_specific(matcher.check("John A. Smith", "J. Smith"))
    False

Link each record to its most specific consistent name rather than to
every name it is consistent with.

What the default accepts
------------------------

The default accepts the writing variants a hand-built comparison
usually forgives; the rest count as a conflict until you accept them
(:ref:`matching-accepting-more`). The table lists the outcomes in the
order ``check()`` ranks them, strongest first, and
:ref:`matching-reported-outcome` says which one a row reports.

.. list-table::
   :header-rows: 1
   :widths: 50 28 10

   * - Outcome
     - Example (left / right)
     - Default
   * - ``same``
     - | ``Smith`` /
       | ``Smith``
     - yes
   * - ``folded``: equal once case, accents, full stops and
       apostrophes are folded away, each joining hyphen is read as the
       hyphen-minus, and a letter a keyboard lacks is read as typed
       (:ref:`matching-fold`)
     - | ``María García`` /
       | ``MARIA GARCIA``
     - yes
   * - ``joined``: equal once folded and stripped of spaces and hyphens, save where both are initials alone
     - | ``Ignazio LaRussa`` /
       | ``Ignazio La Russa``
     - yes
   * - ``listed-spelling``: spellings the vocabulary lists as one
       (:ref:`matching-listed-spellings`)
     - | ``Wm. Smith`` /
       | ``William Smith``
     - yes
   * - ``particles-aside``: the family names, or the maiden names, agree without their particles
     - | ``Juan de la Vega`` /
       | ``Juan Vega``
     - yes
   * - ``part-of-other``: one family or maiden name's words are among the other's, or listed spellings of them, save where both are initials alone
     - | ``Ana de Melo Schmitt`` /
       | ``Ana de Melo Schmitt e Braga``
     - yes
   * - ``initial``: an initial against a name, outside the family
       name, and a given name of capitals against the names that spell
       it (:ref:`matching-initials`)
     - | ``J. Smith`` /
       | ``John Smith``
       |
       | ``JP Smith`` /
       | ``John Paul Smith``
     - yes
   * - ``initials-agree``: one role written in initials alone on both
       sides, the same initials in the same order
       (:ref:`matching-initials`)
     - | ``Jane Doe (née J.-P.)`` /
       | ``Jane Doe (née J. P.)``
     - yes
   * - ``one-side``: a middle name, nickname or maiden name on one side
       only (:ref:`matching-middle-names`)
     - | ``John A. Smith`` /
       | ``John Smith``
     - yes
   * - ``generation-one-side``: a generation on one side only
       (:ref:`matching-generations`)
     - | ``John Smith`` /
       | ``John Smith Jr.``
     - yes
   * - ``noted``: titles and credentials, which never conflict
       (:ref:`matching-generations`)
     - | ``Dr. John Smith`` /
       | ``John Smith, PhD``
     - yes
   * - ``alternate-spelling``: two given names the vocabulary lists as
       one name spelled two ways (:ref:`matching-alternate-spellings`)
     - | ``Yuliya Ivanova`` /
       | ``Iuliia Ivanova``
     - no
   * - ``familiar-form``: two given names the vocabulary lists as a
       familiar-form pair (:ref:`matching-familiar-forms`)
     - | ``Bill Smith`` /
       | ``William Smith``
     - no
   * - ``family-initial``: the family name written as an initial
       (:ref:`matching-family-initial`)
     - | ``John S.`` /
       | ``John Stallbaum``
     - no
   * - ``given-one-side``: a given name on one side only
       (:ref:`matching-given-one-side`)
     - | ``Mr. Smith`` /
       | ``John Smith``
     - no
   * - ``hyphenated-part``: a given name against the first half of
       a hyphenated one (:ref:`matching-hyphenated-part`)
     - | ``Hong Guo`` /
       | ``Hong-Yi Guo``
     - no
   * - ``across-roles``: a name in a different role on each side
       (:ref:`matching-across-roles`)
     - | ``J. Edgar Hoover`` /
       | ``Edgar Hoover``
     - no
   * - ``conflict``
     - | ``John Smith`` /
       | ``Jane Smith``
     - never

.. _matching-reported-outcome:

Which outcome a row reports
~~~~~~~~~~~~~~~~~~~~~~~~~~~

A row reports the strongest outcome that holds and is accepted, and
where none of those holding is accepted, the strongest that holds, so
an unaccepted one shows what the pair needed. ``alternate-spelling``,
``familiar-form``, ``family-initial``, ``given-one-side`` and
``hyphenated-part`` are reported in the table either way.
``across-roles`` is searched only where accepted, and each side's other
readings only where the search is switched on
(:ref:`matching-other-readings`): otherwise the table shows the names
as parsed, and ``Suharto`` / ``Suharto`` reads family ``conflict``.

.. _matching-comparing-outcomes:

Comparing two outcomes
~~~~~~~~~~~~~~~~~~~~~~

``Outcome.strength`` gives an outcome's rank as an ordinal, larger for
a stronger outcome and 0 for ``conflict``. Compare outcomes by it,
since ``<`` on an :class:`~nameparser.Outcome` compares the names as
strings (``folded`` sorts before ``same``), but never store one: the
values change when an outcome is added.

.. _matching-listed-spellings:

Listed spellings
~~~~~~~~~~~~~~~~

A listed spelling is read in the role's own kind of word: given names
for the given name, middle name and nickname, surnames and particles
for the family and maiden names, titles and suffixes for theirs. So
``Ma.`` (María written short) agrees with ``María`` as a given name,
while the surname Ma is another word, ``Ma, Jack`` / ``María, Jack``.

A short form that is also a name of its own, as ``Ma``, ``Jo`` (José)
and ``Jas`` (James) are, is read as its long form only written with its
period: ``Jo. Garcia`` / ``José Garcia`` agree, and ``Jo Garcia`` /
``José Garcia`` conflict, the bare ``Jo`` being the name Jo, while ``Wm
Smith`` and ``WM SMITH`` agree with ``William Smith``, ``Wm`` being no
name of its own.

A short form may stand for several spellings: ``Md``, ``Mohd`` and
``Moh``, Muhammad written short, agree with ``Muhammad``, ``Mohammad``,
``Mohammed`` and ``Mohamed`` and with each other, while two of the long
spellings agree at most as an ``alternate-spelling``.

A listed spelling is read with accents folded too, so ``Jo. Garcia`` /
``Jose Garcia`` agree as ``Jo.`` / ``José`` do. A listed spelling
counts inside a family name word by word as it does whole: with
``smyth`` added to a lexicon as a spelling of ``smith``, ``Ann de
Smyth`` / ``Ann Smith`` read ``particles-aside`` and ``Ann
Smyth-Jones`` / ``Ann Smith`` ``part-of-other``.

.. _matching-middle-names:

Middle names
~~~~~~~~~~~~

A middle name is compared word by word, in order, and takes the weakest
of its words' outcomes; where one side holds more words, the shorter
side's words need only agree, in order, with some of the longer side's,
the rest one-sided, so ``John Beth Smith`` / ``John Anne Beth Smith``
reads ``one-side``.

.. _matching-generations:

Generations, credentials and titles
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

A different generation conflicts (``Jr.`` / ``Sr.``), and a generation
on one side only reads ``generation-one-side`` whatever credentials
either side carries (``John Smith Jr.`` / ``John Smith, PhD``); a
credential or title never conflicts, so a career from ``Mr.`` to
``Dr.`` does not separate a person's records.

.. _matching-fold:

What the fold covers
~~~~~~~~~~~~~~~~~~~~

Two names read ``folded`` where they are equal once case, accents, full
stops and apostrophes (typed or typographic) are folded away, and each
hyphen the parser joins two names with (U+2010, the en dash and others)
read as the hyphen-minus wherever the parser reads the name alike,
which it does not for a credential joined by one (``MD‐PhD``). A letter
a keyboard lacks, written as one types it or as its standard
transcription, reads ``folded`` too (``Łukasz`` / ``Lukasz``,
``Müller`` / ``Mueller``). A zero-width non-joiner or joiner typed at
a word's edge is dropped too.

The fold drops accents only from Latin, Greek and Cyrillic letters; a
mark on another script's letter, such as a Devanagari vowel sign, is
spelling and stays.

.. _matching-initials:

Initials
~~~~~~~~

One role written in initials alone on both sides reads
``initials-agree`` where they are the same initials in the same order.
In a family or maiden name, spaces and hyphens are set aside (``Jane
Doe (née J.-P.)`` / ``Jane Doe (née J. P.)``), and a family or maiden
name of initials alone on both sides reads no other leniency, so ``J.
P., Ann`` / ``P. J., Ann`` and ``J., Ann`` / ``J. P., Ann`` conflict.
A letter in a script that writes no initials (Han, Hangul, kana, Thai,
Lao, Burmese, Arabic) is read as a word, not an initial, so ``ສ. ໃຈດີ``
/ ``ສົມຊາຍ ໃຈດີ`` conflicts.

Initials written joined into one word agree with the same letters
written apart as ``joined`` (``JP Smith`` / ``J.-P. Smith``).

A given name of two or three capitals reads as initials against the
names that spell it (``JP Smith`` / ``John Paul Smith``, given and
middle ``initial``) where all of these hold:

- **No middle name stands beside it.** ``JP A. Smith`` / ``John Paul
  Smith`` conflicts.
- **Its given or family name holds a lower-case letter.** A name
  written wholly in capitals is not read so: ``JP SMITH`` / ``JOHN PAUL
  SMITH`` conflicts.
- **The other side's given and middle names spell those letters
  exactly, in order**, a name for each letter. It is not read so
  against fewer or more names than letters (``JP Smith`` / ``John
  Smith``).
- **A capitals word on the other side counts as its own letters and
  spells none of them.** ``JR Paul Smith`` holds J, R and P, so ``JP
  Smith`` conflicts with it.
- **Reading it so makes the pair consistent.** ``JP Smith`` / ``John
  Paul Brown``, whose family names conflict, keeps its given row
  ``conflict``.

``J. P. Smith``, written apart, does agree with fewer or more names
than letters (``J. P. Smith`` / ``John Smith``, ``J. P. Smith`` /
``John Paul Robert Smith``), and with ``JP Smith``, so a pair can still
be consistent through ``J. P. Smith`` and not directly.

.. _matching-conflicts:

What stays a conflict
~~~~~~~~~~~~~~~~~~~~~

Typos (``Slvatore`` / ``Salvatore``) and transliterations (``Igor`` /
``Ihor``) are conflicts. A familiar form (``Peggy`` / ``Margaret``,
below) you have not accepted keeps the pair inconsistent though its row
reads ``familiar-form``.

The rows that kept a pair inconsistent are the ones whose outcome you
did not accept, and the table names their roles, so you can run your
own fuzzy comparison on those alone:

.. doctest::

    >>> peggy = matcher.check("Peggy Smith", "Margaret Smith")
    >>> [(r.role.value, r.outcome.value) for r in peggy.roles if r.outcome not in matcher.accept]
    [('given', 'familiar-form')]

.. _matching-accepting-more:

Accepting more
--------------

Find the pair your sources disagree on, and accept the outcome beside
it. Each has a cost, which its section gives in full:

.. list-table::
   :header-rows: 1
   :widths: 22 24 34 20

   * - Your pair
     - Accept or switch
     - Cost
     - Section
   * - | ``Bill`` /
       | ``William``
     - ``familiar-form``
     - A short name stands for several names and is often a name of
       its own
     - :ref:`matching-familiar-forms`
   * - | ``Yuliya`` /
       | ``Iuliia``
     - ``alternate-spelling``
     - People sometimes spell a name differently on purpose
     - :ref:`matching-alternate-spellings`
   * - | ``John S.`` /
       | ``John Stallbaum``
     - ``family-initial``
     - A key of one family letter, which gathers very large groups
     - :ref:`matching-family-initial`
   * - | ``Mr. Smith`` /
       | ``John Smith``
     - ``given-one-side``
     - A key of each family part alone, with no given letter
     - :ref:`matching-given-one-side`
   * - | ``Hong`` /
       | ``Hong-Yi``
     - ``hyphenated-part``
     - Half of a given name goes unread; no key added
     - :ref:`matching-hyphenated-part`
   * - | ``J. Edgar Hoover`` /
       | ``Edgar Hoover``
     - ``across-roles``
     - Given letters from the middle names and nickname, family keys
       from the maiden name
     - :ref:`matching-across-roles`
   * - | ``Suharto`` /
       | ``Suharto``
     - ``other_readings=True``
     - Keys for each other reading tried
     - :ref:`matching-other-readings`
   * - | ``Slvatore`` /
       | ``Salvatore``
       |
       | ``Igor`` /
       | ``Ihor``
     - nothing here
     - Run your own fuzzy comparison on the rows that conflict
     - :ref:`matching-conflicts`

``accept`` takes outcome names or :class:`~nameparser.Outcome`
members, and *replaces* the default set rather than adding to it, so
extend the default with the ``accept`` of a default matcher. The keys
follow what is accepted and the ``other_readings`` switch, so one
matcher's ``keys()`` and ``check()`` always agree; never group with one
matcher and check with another:

.. doctest::

    >>> Parser().matching(accept=matcher.accept | {"family-initial", "given-one-side"})
    Matching(default + family-initial, given-one-side)

An unknown outcome name raises ``ValueError`` listing the valid ones,
and ``conflict`` cannot be accepted.

.. _matching-familiar-forms:

Familiar forms
~~~~~~~~~~~~~~

Accept ``familiar-form`` when one source writes people by the short
names they go by and another by their full given names.

``familiar-form`` reads a short given name as standing for the longer
ones the vocabulary lists it under: ``Max`` for Maximilian and
Maxwell, ``Bill`` for William, ``Peggy`` for Margaret. It is read in the
given name, middle name and nickname, never the family name. A pair whose short name reads
as a title in front of a name is never compared as a given name, so it
stays inert while the title reading stands.

A pair is read whichever way the vocabulary wrote it, since the vocabulary
writes a pair on its shorter name, which is not always the familiar
form (``Charles`` / ``Charlie``), and a caller may write one either
way round, but never chained, so two longer names paired with one short name do not
agree with each other:

.. doctest::

    >>> with_familiar = Parser().matching(accept=matcher.accept | {"familiar-form"})
    >>> matcher.check("Bill Smith", "William Smith").consistent
    False
    >>> bill = with_familiar.check("Bill Smith", "William Smith")
    >>> bill.consistent, bill["given"].outcome.value
    (True, 'familiar-form')
    >>> matcher.check("Bill Smith", "William Smith")["given"].outcome.value
    'familiar-form'
    >>> with_familiar.check("Maximilian Smith", "Maxwell Smith").consistent
    False

A familiar form is outside the default because it is many-valued and
often a name of its own: ``Max`` is a given name in its own right, as
``Bill`` and ``Peggy`` are.

The keys follow: a name is keyed by the first
letters of the names it is paired with too, so ``Bill Smith`` meets
``William Smith`` in a group:

.. doctest::

    >>> sorted(matcher.keys("Bill Smith"))
    ['smith;b']
    >>> sorted(with_familiar.keys("Bill Smith"))
    ['smith;b', 'smith;w']

Where the shipped pairs come from
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

The shipped familiar forms, about twenty-three hundred pairs, are pairs
people wrote both ways for themselves: chiefly
ORCID's researchers and Brazil's election candidates (below), who wrote one in the given-name box and the other
in a published name, in many languages (``Peggy`` / ``Margaret``,
``Ricky`` / ``Richard``, ``Kasia`` / ``Katarzyna``, ``Kostas`` /
``Konstantinos``, ``Seun`` / ``Oluwaseun``), and a few common English
ones that US political donors and members of Congress gave as their
nicknames (``Betty`` / ``Elizabeth``).

Central and Eastern European and Balkan languages also have pairs from
Wikidata's people, each named one way in their name or nickname and
the other in their given name or birth name (``Erzsi`` / ``Erzsébet``,
``Jára`` / ``Jaroslav``). The Russian, Ukrainian, Belarusian,
Bulgarian and most Serbian ones are written in Cyrillic (``Женя`` /
``Евгений``), so a name romanized in Latin letters does not reach them.

Brazilian Portuguese has pairs from Brazil's election candidates, each
registering the name printed on the ballot beside the civil name, at
twenty candidates or more (``Paulinho`` / ``Paulo``, ``Cida`` /
``Aparecida``, ``Tião`` / ``Sebastião``, ``Biu`` / ``Severino``).
``docs/design/decisions/name-matching.md`` has how they were selected.

.. _matching-familiar-language-choice:

Which pairs a language choice keeps
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

Each pair is in the file of the languages written where its holders
work. A plain choice of languages (:ref:`choosing-languages`) keeps
every file's pairs, and a strict one (:ref:`strict-choice`) keeps its
own files' and the shared ones.

.. _matching-editing-familiar-forms:

Adding and removing pairs
^^^^^^^^^^^^^^^^^^^^^^^^^

The shipped pairs are a selection and have gaps, among them common
English pairs researchers rarely publish under (``Kathy`` /
``Catherine``, ``Lisa`` / ``Melissa``, ``Jeff`` / ``Geoffrey``) and
``Sepp`` / ``Josef``. Add your own with a ``familiar`` reading, which
extends the names the word's shipped readings list:

.. doctest::

    >>> from nameparser import Lexicon
    >>> kathy = Lexicon.default().add("kathy", kind="familiar", short_for=["catherine"])
    >>> mine = Parser(lexicon=kathy).matching(accept=matcher.accept | {"familiar-form"})
    >>> mine.check("Kathy Smith", "Catherine Smith").consistent, mine.check("Kathy Smith", "Katherine Smith").consistent
    (True, True)

To drop a pair you do not want, name it in a ``remove``. A pair is
stored on one of its two names and read both ways, so either name may
come first, and the other pairs of both names stay:

.. doctest::

    >>> no_alexis = Lexicon.default().remove("alex", kind="familiar", short_for=["alexis"])
    >>> cut_pair = Parser(lexicon=no_alexis).matching(accept=matcher.accept | {"familiar-form"})
    >>> with_familiar.check("Alex Smith", "Alexis Smith").consistent, cut_pair.check("Alex Smith", "Alexis Smith").consistent
    (True, False)
    >>> cut_pair.check("Alex Smith", "Alexander Smith").consistent
    True
    >>> alexis_first = Lexicon.default().remove("alexis", kind="familiar", short_for=["alex"])
    >>> Parser(lexicon=alexis_first).matching(accept=matcher.accept | {"familiar-form"}).check("Alex Smith", "Alexis Smith").consistent
    False

With no ``short_for``, ``remove(word, kind="familiar")`` drops every
pair naming the word, whichever name holds it: removing ``robert`` cuts
``Bob``, ``Rob`` and ``Robbie`` from ``Robert``, and each of those names
keeps its pairs with other names.

.. doctest::

    >>> no_robert = Lexicon.default().remove("robert", kind="familiar")
    >>> cut_word = Parser(lexicon=no_robert).matching(accept=matcher.accept | {"familiar-form"})
    >>> with_familiar.check("Bob Smith", "Robert Smith").consistent, cut_word.check("Bob Smith", "Robert Smith").consistent
    (True, False)

A name is compared as matching reads it, with case and accents folded,
so removing ``alex`` / ``alejandro`` also drops the pair the vocabulary
stores as ``Álex`` / ``Alejandro``. Edits apply in the order written: a
``remove`` drops a pair you added before it, and a pair added after it
stands, which is how to replace a word's names (``remove(word,
kind="familiar")``, then ``add``). An alternate spelling is removed the
same way, ``remove("sarah", kind="spelling", spelling_of=["sara"])`` or
``remove("sara", kind="spelling")``.

.. _matching-alternate-spellings:

Alternate spellings
~~~~~~~~~~~~~~~~~~~

Accept ``alternate-spelling`` when you know your sources write one
name several ways, as lists romanized from another script do.

``alternate-spelling`` reads two given names as one name spelled two
ways, by the person or by a romanization: ``Yuliya`` / ``Iuliia``,
``Aleksey`` / ``Alexey``, ``Saeed`` / ``Saeid``, ``Olga`` / ``Olha``. A
name romanized from another script is one name where that script spells
it alike (``Mariia`` / ``Mariya``, both ``Марія``), and a name written in
Latin letters in its own language is one name where that language uses
both spellings (``Sara`` / ``Sarah`` in English). A different spelling in
the source script (``Nataliia`` / ``Natalya``, ``Наталія`` / ``Наталья``)
or another language's form (``Lydia`` / ``Lidia``) is a translation,
which no outcome reads yet.

``alternate-spelling`` is read as a familiar form is, in the same
roles, either way round
and never chained:

.. doctest::

    >>> spelled = Parser().matching(accept=matcher.accept | {"alternate-spelling"})
    >>> matcher.check("Yuliya Ivanova", "Iuliia Ivanova").consistent
    False
    >>> yuliya = spelled.check("Yuliya Ivanova", "Iuliia Ivanova")
    >>> yuliya.consistent, yuliya["given"].outcome.value
    (True, 'alternate-spelling')

An alternate spelling is outside the default because people sometimes
spell a name
differently on purpose, to be told apart from someone of the same name,
so two spellings are evidence of a match only for a caller who knows
their sources write one name several ways.

The keys follow it where it is accepted, as they follow a familiar
form:

.. doctest::

    >>> sorted(matcher.keys("Iuliia Ivanova"))
    ['ivanova;i']
    >>> sorted(spelled.keys("Iuliia Ivanova"))
    ['ivanova;i', 'ivanova;y']

The shipped pairs, about three hundred, were selected with the
familiar forms, less the spellings a
keyboard forces, which the default reads ``folded`` (``Łukasz`` /
``Lukasz``, ``Jürgen`` / ``Juergen``, ``Srđan`` / ``Srdjan``, from
either side).

.. _matching-family-initial:

A family name written as an initial
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Accept ``family-initial`` when a source cuts the family name to its
initial.

The initial stands for a word on the
other side, so against another family name of initials alone it never
holds: ``J.-P., Ann`` / ``J., Ann`` conflicts under every setting.
Initials written together are one word, not initials alone, so
``J.P., Ann`` / ``J., Ann`` still reads ``family-initial``, and
``J.P., Ann`` / ``J. P., Ann`` ``joined``.

.. doctest::

    >>> with_family_initial = Parser().matching(accept=matcher.accept | {"family-initial"})
    >>> with_family_initial
    Matching(default + family-initial)
    >>> matcher.check("John S.", "John Stallbaum").consistent
    False
    >>> with_family_initial.check("John S.", "John Stallbaum").consistent
    True

A family initial is outside the default because its key, one letter of
the family name, gathers very large groups:

.. doctest::

    >>> sorted(matcher.keys("John Stallbaum"))
    ['stallbaum;j']
    >>> sorted(with_family_initial.keys("John Stallbaum"))
    ['s;j', 'stallbaum;j']

.. _matching-given-one-side:

A given name on one side only
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Accept ``given-one-side`` when a source writes some people with no
given name, by a title and a surname.

``given-one-side`` reads a given name against none, where the family
name is present on both sides and agrees:

.. doctest::

    >>> surname_only = Parser().matching(accept=matcher.accept | {"given-one-side"})
    >>> matcher.check("Mr. Smith", "John Smith").consistent
    False
    >>> mister = surname_only.check("Mr. Smith", "John Smith")
    >>> mister.consistent, mister["given"].outcome.value
    (True, 'given-one-side')

It is outside the default because of what it does to the keys: every
name with a family name gets each family part it is keyed by as a key
of its own, with no
given letter, so a group holds everyone of that surname.

.. doctest::

    >>> sorted(matcher.keys("John Smith"))
    ['smith;j']
    >>> sorted(surname_only.keys("John Smith"))
    ['smith', 'smith;j']

On its own it does not reach a name written as one word. A lone
``Smith`` is read as a given name (:ref:`lone-name-word`), so it has
no family name to agree and still conflicts. For a source of such
names, parse it with ``lone_name_word`` set to the family, or switch
on the other readings (:ref:`matching-other-readings`) beside the
outcome:

.. doctest::

    >>> surname_only.check("Smith", "John Smith").consistent
    False
    >>> Parser().matching(accept=surname_only.accept,
    ...                   other_readings=True).check("Smith", "John Smith").consistent
    True
    >>> family_word = Parser(policy=Policy(lone_name_word="family"))
    >>> surname_only.check(family_word.parse("Smith"), "John Smith").consistent
    True

.. _matching-hyphenated-part:

Half of a hyphenated given name
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Accept ``hyphenated-part`` when your sources write a two-part given
name with its hyphen in one place and, in another, cut to its first
part or with a space for the hyphen.

``hyphenated-part`` reads a given name of one word against the first
half of a hyphenated one, never the second half. A word of the middle
name is read the same way. With a space for the hyphen the second part
is a middle name, on one side only:

.. doctest::

    >>> with_halves = Parser().matching(accept=matcher.accept | {"hyphenated-part"})
    >>> matcher.check("Hong Guo", "Hong-Yi Guo").consistent
    False
    >>> halves = with_halves.check("Hong Guo", "Hong-Yi Guo")
    >>> halves.consistent, halves["given"].outcome.value
    (True, 'hyphenated-part')
    >>> with_halves.check("Yi Guo", "Hong-Yi Guo").consistent
    False
    >>> spaced = with_halves.check("Hong Yi Guo", "Hong-Yi Guo")
    >>> spaced.consistent, spaced["given"].outcome.value, spaced["middle"].outcome.value
    (True, 'hyphenated-part', 'one-side')

The two parts written as one word need no opt-in, and neither does a
hyphenated family name, whose half the default reads as
``part-of-other``:

.. doctest::

    >>> matcher.check("Hongyi Guo", "Hong-Yi Guo")["given"].outcome.value
    'joined'
    >>> matcher.check("Ann Vega", "Ann Vega-Ruiz")["family"].outcome.value
    'part-of-other'

It is outside the default because it agrees with half of the given
name missing. It adds no key: the first half starts with the letter
the keys are cut on, so the two names share a group already.

.. doctest::

    >>> with_halves.keys("Hong Guo") == matcher.keys("Hong Guo")
    True
    >>> sorted(matcher.keys("Hong Guo") & matcher.keys("Hong-Yi Guo"))
    ['guo;h']

.. _matching-across-roles:

A name in a different role on each side
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Accept ``across-roles`` when a source files people under the name
they go by: a middle name or a nickname used as the given name, or a
birth name used as the family name.

``across-roles`` compares a given name with each word of the other
name's middle name and with its nickname, and a family name with the
other's maiden name. It counts only a full name on both sides, never
an initial, and records each match it made in ``across``:

.. doctest::

    >>> with_across = Parser().matching(accept=matcher.accept | {"across-roles"})
    >>> matcher.check("J. Edgar Hoover", "Edgar Hoover").consistent
    False
    >>> hoover = with_across.check("J. Edgar Hoover", "Edgar Hoover")
    >>> hoover.consistent, hoover["given"].outcome.value
    (True, 'across-roles')
    >>> hoover.across[0].left_role.value, hoover.across[0].right_role.value, hoover.across[0].left
    ('middle', 'given', 'Edgar')
    >>> with_across.check("Jane Doe (née Smith)", "Jane Smith").consistent
    True

The middle word a match uses is taken out of the middle comparison,
and the middle words left are compared role to role.

It is outside the default because it moves a name between roles,
where the default accepts the writing variants of a name. Unlike the
other opt-in outcomes it is searched only where accepted, so the
default table shows the pair as a given ``conflict``
(:ref:`matching-reported-outcome`).

The keys follow: a name is keyed by the first letter of each middle
word and of its nickname beside its given name's, save one written in
initials alone, and by its maiden name as by its family name:

.. doctest::

    >>> sorted(matcher.keys("J. Edgar Hoover"))
    ['hoover;j']
    >>> sorted(with_across.keys("J. Edgar Hoover"))
    ['hoover;e', 'hoover;j']

A role read ``across-roles`` has the side carrying more that held both
the role and the role it was matched against, so ``J. Edgar Hoover``,
which holds a given initial beside the middle name the other uses as
its given name, is the more specific of the two
(:ref:`matching-not-transitive` defines ``less_specific``):

.. doctest::

    >>> less_specific(with_across.check("Edgar Hoover", "J. Edgar Hoover"))
    True
    >>> less_specific(with_across.check("J. Edgar Hoover", "Edgar Hoover"))
    False

.. _matching-other-readings:

Trying each side's other reading
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Switch on ``other_readings`` when your sources hold names the parser
has to guess at, such as a name of one word.

``other_readings=True``, a switch beside ``accept`` rather than an
outcome, tries each side's other reading where the names as parsed are
not consistent: one :ref:`ambiguity <parser-guesses>` at a time, its
words moved to the role its ``alternative`` names. Each row keeps its
own outcome under the other reading, so whatever else the pair needed
still shows, and ``left_alternative`` and ``right_alternative`` hold
the ambiguity whose other reading each side used, ``None`` for a side
read as parsed. A lone ``Suharto``, read as a given name, has the
family reading as its alternative:

.. doctest::

    >>> with_other_reading = Parser().matching(other_readings=True)
    >>> with_other_reading
    Matching(default + other-readings)
    >>> matcher.check("Suharto", "Suharto").consistent
    False
    >>> lone = with_other_reading.check("Suharto", "Suharto")
    >>> lone.consistent, lone["family"].outcome.value
    (True, 'same')
    >>> lone.left_alternative.kind.value, lone.left_alternative.alternative.role.value
    ('given-or-family', 'family')

An alternative that would move words into the title or the suffix is
not tried, so a given name cannot vanish into one of them to agree
with another.

The search is off by default, and the table then shows the names as
parsed. Where it is on, the keys follow: a name gets the keys of each
other reading the search tries, so the lone ``Suharto``, which has no
key by default, gets its family reading's:

.. doctest::

    >>> sorted(matcher.keys("Suharto"))
    []
    >>> sorted(with_other_reading.keys("Suharto"))
    ['suharto;']

.. _matching-accepting-less:

Accepting less
--------------

Since ``accept`` replaces the default set, a set with an outcome taken
out is a stricter matcher. The default outcomes that agree on the
least text are the ones to weigh: ``initial`` (a name against its
first letter), ``one-side`` and ``generation-one-side`` (a role
written on one side only) and ``part-of-other`` (a family name against
some of its words). ``same`` is always accepted.

.. doctest::

    >>> full_names_only = Parser().matching(accept=matcher.accept - {"initial"})
    >>> full_names_only
    Matching(default - initial)
    >>> matcher.check("J. Smith", "John Smith").consistent
    True
    >>> strict_pair = full_names_only.check("J. Smith", "John Smith")
    >>> strict_pair.consistent, strict_pair["given"].outcome.value
    (False, 'initial')

Dropping a default outcome leaves the keys as they are, so the groups
are the same and fewer of their pairs come out consistent:

.. doctest::

    >>> full_names_only.keys("J. Smith") == matcher.keys("J. Smith")
    True

To grade the consistent pairs rather than refuse some, keep the
default and filter on ``weakest``, comparing by ``Outcome.strength``
(:ref:`matching-comparing-outcomes`). This keeps a pair whose weakest
row is at least ``initial``, and so sets aside every pair with a row
ranked below it: a middle name, nickname, maiden name or generation on
one side only (``one-side``, ``generation-one-side``), a title or
credential (``noted``), or a role written in initials alone on both
sides (``initials-agree``):

.. doctest::

    >>> def at_least_initial(result):
    ...     return result.consistent and result.weakest.strength >= Outcome.INITIAL.strength
    >>> at_least_initial(matcher.check("J. Smith", "John Smith"))
    True
    >>> at_least_initial(matcher.check("John Smith", "John Smith Jr."))
    False
    >>> at_least_initial(matcher.check("John A. Smith", "John Smith"))
    False

.. _matching-without-an-inherited-family-name:

Names with no inherited family name
-----------------------------------

Some conventions have no inherited family name. An Ethiopian or
Eritrean name is the person's own name, then the father's, then often
the grandfather's, and where only two are written abroad the father's
name is filed as the surname. The parser reads by position, so the
father's name is the ``family`` of ``Dawit Bekele`` and the ``middle``
of ``Dawit Bekele Tesfaye``, whose family is the grandfather's. The
default matcher therefore keeps the two spellings of one person apart:

.. doctest::

    >>> matcher.check("Dawit Bekele Tesfaye", "Dawit Bekele")["family"].outcome.value
    'conflict'

For a list known to follow this convention, build the matcher from a
parser that folds the middle names into the family
(``middle_as_family``). The father's name is then part of the family on
both sides, so the two spellings are consistent and share a key, while a
different father, or a different grandfather behind the same father,
still conflicts:

.. doctest::

    >>> from nameparser import Policy
    >>> ethiopian_matcher = Parser(policy=Policy(middle_as_family=True)).matching()
    >>> dawit = ethiopian_matcher.check("Dawit Bekele Tesfaye", "Dawit Bekele")
    >>> dawit.consistent, dawit["family"].outcome.value
    (True, 'part-of-other')
    >>> sorted(ethiopian_matcher.keys("Dawit Bekele Tesfaye")
    ...        & ethiopian_matcher.keys("Dawit Bekele"))
    ['bekele;d']
    >>> ethiopian_matcher.check("Dawit Bekele", "Dawit Tesfaye").consistent
    False
    >>> ethiopian_matcher.check("Dawit Bekele Tesfaye", "Dawit Bekele Haile").consistent
    False

Keep the default parser for reading the fields: the fold reads the
grandfather's name into the family too, and on ORCID's Ethiopian
records, where holders filed their own names, it agrees with their
boxes about 21.5 points less often than the default does
(:issue:`1203`).

The matcher compares a family of several words regardless of order, and
the fold makes every such family several words, so two names consistent
under it are not always one person. A name whose father and grandfather
are written the other way round is consistent, and so, under either
matcher, is a two-word name whose second word is the other name's
grandfather:

.. doctest::

    >>> ethiopian_matcher.check("Dawit Bekele Tesfaye", "Dawit Tesfaye Bekele").consistent
    True
    >>> matcher.check("Dawit Bekele Tesfaye", "Dawit Tesfaye").consistent
    True

And use it only for such a list: it treats every middle name as part of
the family, so it also calls ``John Paul Smith`` and ``John Paul``
consistent, which the default matcher keeps apart:

.. doctest::

    >>> ethiopian_matcher.check("John Paul Smith", "John Paul").consistent
    True
    >>> matcher.check("John Paul Smith", "John Paul").consistent
    False

The fold has a cost the other way too. A father's name written as an
initial becomes part of the family, so the pair conflicts as a family
written with an initial (``family-initial``, which the default does not
accept), where the default matcher reads a middle initial and calls it
consistent. Accept ``family-initial`` on the folded matcher to restore
it:

.. doctest::

    >>> matcher.check("Dawit B. Tesfaye", "Dawit Bekele Tesfaye").consistent
    True
    >>> ethiopian_matcher.check("Dawit B. Tesfaye", "Dawit Bekele Tesfaye")["family"].outcome.value
    'family-initial'
    >>> Parser(policy=Policy(middle_as_family=True)).matching(
    ...     accept=ethiopian_matcher.accept | {"family-initial"}
    ... ).check("Dawit B. Tesfaye", "Dawit Bekele Tesfaye").consistent
    True

Neither matcher removes a title the vocabulary does not list: ``Ato``
reads as the given name, so ``Ato Dawit Bekele Tesfaye`` and
``Dawit Bekele`` conflict under both.
