Working with a parsed name
==========================

What a :class:`~nameparser.ParsedName` gives you once a name is
parsed: its fields and the views that combine them, strings and dicts,
case repair, comparison, the guesses it reports, its tokens, how to
correct it, and the command line. New to nameparser? Start with
:doc:`getting-started`.

Parse a name
------------

.. doctest::

    >>> from nameparser import parse
    >>> name = parse("Dr. Juan Q. Xavier de la Vega III")
    >>> name.given, name.family
    ('Juan', 'de la Vega')
    >>> name.title, name.middle, name.suffix
    ('Dr.', 'Q. Xavier', 'III')

A parsed name has seven fields, each a string, empty where the name has
no such part. The examples are the fields of
``Dr. Mara "Mimi" Lee Quill née Brandt, PhD``:

.. list-table::
   :header-rows: 1
   :widths: 18 60 22

   * - Field
     - Holds
     - Example
   * - ``title``
     - A title or form of address, usually written before the name
     - ``Dr.``
   * - ``given``
     - The given name
     - ``Mara``
   * - ``middle``
     - The name words that are neither the given name nor the family
       name
     - ``Lee``
   * - ``family``
     - The family name, with any particles (``de la Vega``)
     - ``Quill``
   * - ``suffix``
     - Words written after the name, such as a generation (``III``)
       or a credential
     - ``PhD``
   * - ``nickname``
     - A nickname written in quotes or parentheses
       (:ref:`nicknames-and-maiden-names`)
     - ``Mimi``
   * - ``maiden``
     - A birth name written after a marker such as ``née``
       (:ref:`nicknames-and-maiden-names`)
     - ``Brandt``

.. doctest::

    >>> all_seven = parse('Dr. Mara "Mimi" Lee Quill née Brandt, PhD')
    >>> all_seven.title, all_seven.given, all_seven.middle, all_seven.family
    ('Dr.', 'Mara', 'Lee', 'Quill')
    >>> all_seven.suffix, all_seven.nickname, all_seven.maiden
    ('PhD', 'Mimi', 'Brandt')

Parsing never raises; unparseable input yields a
:class:`~nameparser.ParsedName` with
empty fields plus any ``ambiguities`` the parser noticed along the way
(see `When the parser had to guess`_ below, and :doc:`concepts` for why
they exist). A name with no fields set is falsy, which is how you tell
"nothing parsed" from "parsed to something":

.. doctest::

    >>> bool(parse("")), bool(parse("   ")), bool(parse("John"))
    (False, False, True)

.. _aggregate-views:

Aggregate views
----------------

A view combines or splits the seven fields for one task: a form's
"given names" box, a sort key, the generation apart from the degrees.
Each is a property of the parsed name and a key of a ``render()`` spec,
and none changes a field. Each example below is from the name its
section parses.

.. list-table::
   :header-rows: 1
   :widths: 26 46 28

   * - View
     - What it holds
     - Example
   * - ``given_names``
     - ``given`` and ``middle`` together
       (:ref:`usage-given-names-and-surnames`)
     - ``Juan Q. Xavier``
   * - ``surnames``
     - ``middle`` and ``family`` together
       (:ref:`usage-given-names-and-surnames`)
     - ``Q. Xavier de la Vega``
   * - ``family_base``, ``family_particles``
     - The family name without its particles, and the particles
       (:ref:`usage-sorting-by-family-name`)
     - | ``Vega``
       | ``de la``
   * - ``generation``
     - The suffix words read as a generation
       (:ref:`usage-splitting-the-suffix`)
     - ``Jr.``
   * - ``honorifics``
     - A form of address written after the name
       (:ref:`usage-splitting-the-suffix`)
     - ``さん``
   * - ``credentials``
     - The rest of the suffix (:ref:`usage-splitting-the-suffix`)
     - ``MD, Esq.``
   * - ``patronymic``
     - The words that say whose child the bearer is, where a particle
       or a ``patronymic_rules`` rule marks them
       (:ref:`usage-finding-a-patronymic`)
     - ``bin Mohamad``
   * - ``surname1``, ``surname2``
     - The first family name and the second, where the family was read
       as two; elsewhere ``surname2`` is empty and ``surname1`` is the
       family, less any middle names folded into it
       (:ref:`usage-surname1-and-surname2`)
     - | ``García``
       | ``Márquez``
   * - ``surname1_base``, ``surname1_particles``
     - ``surname1`` split as ``family_base`` and ``family_particles``
       split the family (:ref:`usage-surname1-and-surname2`)
     - | ``Vega``
       | ``de la``

.. _usage-given-names-and-surnames:

Given names and surnames together
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

.. doctest::

    >>> name.given_names          # given + middle
    'Juan Q. Xavier'
    >>> name.surnames             # middle + family
    'Q. Xavier de la Vega'

``surnames`` (``middle`` + ``family``) is the mirror-image aggregate.
The plural is the tell: ``given`` and ``family`` are single fields,
while ``given_names`` and ``surnames`` roll several fields together —
the same sense in which a passport form asks for your "given names" as
one blank that can hold more than one word.

.. _usage-sorting-by-family-name:

Sorting by family name
~~~~~~~~~~~~~~~~~~~~~~

.. doctest::

    >>> name.family_base, name.family_particles   # family, split apart
    ('Vega', 'de la')

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

.. _usage-splitting-the-suffix:

Splitting the suffix: generation, credentials, honorifics
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

``generation`` and ``credentials`` split the suffix the way a name
form's "Jr., III" and "PhD, MD" boxes do: a generation numbers the
bearer among relatives of the same name, and every other word after
the name, a courtesy such as ``Esq.`` included, is a credential, save
a form of address written after the name (``さん``, ``씨``, ``先生``),
which is in ``honorifics``. Each joins its words as ``suffix`` does,
and ``suffix`` itself is unchanged:

.. doctest::

    >>> suffixed = parse("Smith, John, Jr., MD, Esq.")
    >>> suffixed.generation, suffixed.credentials, suffixed.suffix
    ('Jr.', 'MD, Esq.', 'Jr., MD, Esq.')
    >>> suffixed.render("{given} {family} {generation}")
    'John Smith Jr.'
    >>> addressed = parse("田中さん, PhD")
    >>> addressed.credentials, addressed.honorifics, addressed.suffix
    ('PhD', 'さん', 'さん, PhD')

.. _usage-finding-a-patronymic:

Finding a patronymic
~~~~~~~~~~~~~~~~~~~~

``patronymic`` names the words that say whose child the bearer is, a
particle such as ``bin`` with the parent's name after it, in whatever
field the parse put them, which keeps them. The view reads no position
itself, so a name written without the particle has none, unless the
parse ran a rule of ``Policy.patronymic_rules`` that read one, as the
``ru`` pack sets (:doc:`locales`):

.. doctest::

    >>> nasab = parse("Mahathir bin Mohamad")
    >>> nasab.patronymic, nasab.family
    ('bin Mohamad', 'bin Mohamad')
    >>> parse("Anwar Ibrahim").patronymic
    ''
    >>> from nameparser import locales, parser_for
    >>> parser_for(locales.RU).parse("Ivan Petrovich Sidorov").patronymic
    'Petrovich'

.. _usage-no-inherited-family-name:

What ``family`` holds where no family name is inherited
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Some conventions have no inherited family name. There ``family`` holds
the name the convention files a person under, the word that stands where
a surname would, and the name order (:ref:`name-order`) decides which
word that is. An Ethiopian
name is the person's own name, the father's and often the grandfather's,
so ``family`` is the grandfather's name where it is written and the
father's where it is not. Nothing in the name marks the father's name,
so ``patronymic`` stays empty:

.. doctest::

    >>> abiy = parse("Abiy Ahmed Ali")
    >>> abiy.middle, abiy.family, abiy.patronymic
    ('Ahmed', 'Ali', '')
    >>> parse("Abiy Ahmed").family
    'Ahmed'

To match the two spellings of one such name, see
:ref:`matching-without-an-inherited-family-name`.

.. _usage-surname1-and-surname2:

Two family names: ``surname1`` and ``surname2``
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

``surname2`` is the family's second name, where the parse read the
family as two: with ``two_family_names`` on
(:ref:`two-family-names`), as the ``es``, ``es_ar``, ``cs``, ``sk``,
``hr``, ``sl``, ``pt_br`` and ``pt_pt`` packs turn it on (:doc:`locales`), or for a Chinese name opening with
two surnames under ``zh`` (:ref:`east-asian-names`), and ``family``
keeps both. The family is divided by its own words, so the name written
with a family comma gives the same two, and so does a family opening
with a particle (``de la Vega`` then ``Ruiz``). Every other name has
none, a hyphenated family and one joined by ``y`` included:

.. doctest::

    >>> from nameparser import Parser, Policy
    >>> marquez = Parser(policy=Policy(two_family_names=True)).parse(
    ...     "Gabriel García Márquez")
    >>> marquez.family, marquez.surname1, marquez.surname2
    ('García Márquez', 'García', 'Márquez')
    >>> marquez_comma = Parser(policy=Policy(two_family_names=True)).parse(
    ...     "García Márquez, Gabriel")
    >>> marquez_comma.surname1, marquez_comma.surname2
    ('García', 'Márquez')
    >>> parse("Gabriel García Márquez").surname2
    ''

``surname1`` is the other one, the first of the two family names, with
``surname1_particles`` and ``surname1_base`` splitting it as
``family_particles`` and ``family_base`` split the whole family. Where
the family is read as one, they are the family's own views, but for any
middle names ``middle_as_family`` folds into it:

.. doctest::

    >>> vega = Parser(policy=Policy(two_family_names=True)).parse(
    ...     "Juan de la Vega del Valle")
    >>> vega.surname1, vega.surname1_particles, vega.surname1_base
    ('de la Vega', 'de la', 'Vega')
    >>> vega.family_base, vega.surname2
    ('Vega Valle', 'del Valle')
    >>> parse("Juan de la Vega").surname1_base
    'Vega'

Dicts and strings
------------------

A parsed name writes itself out three ways: ``as_dict()`` for a record,
``str()`` and ``render()`` for a string, and ``initials()``.

As a dict
~~~~~~~~~

``as_dict()`` gives the seven fields by name, and
``include_empty=False`` leaves out the empty ones. The views are not in
it:

.. doctest::

    >>> name.as_dict(include_empty=False)
    {'title': 'Dr.', 'given': 'Juan', 'middle': 'Q. Xavier', 'family': 'de la Vega', 'suffix': 'III'}

As a string, in another order
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

``str()`` writes the name whole, and ``render()`` takes a format spec
naming the fields and views you want, in the order you want them:

.. doctest::

    >>> str(name)
    'Dr. Juan Q. Xavier de la Vega III'
    >>> name.render("{family}, {given}")
    'de la Vega, Juan'

``str()``, like ``render()`` with no spec, lays the name out in the
order it was read in (:attr:`ParsedName.order
<nameparser.ParsedName.order>`) and keeps the separator written between
two words that stay side by side, normalized: nothing stays nothing,
any run of whitespace becomes one space, and a comma before a suffix
stays. Where the layout puts quotes or parentheses between two fields,
around a nickname or a maiden name, those stand between them instead.
A spec you pass renders exactly as written, in its own order:

.. doctest::

    >>> str(parse("김민준")), str(parse("John Smith, Jr."))
    ('김민준', 'John Smith, Jr.')
    >>> parse("김민준").render("{given} {family}")
    '민준 김'

:ref:`rendering-arguments` has more on specs, and on a string meant to
be parsed again.

As initials
~~~~~~~~~~~

``initials()`` gives the initials of the given, middle and family
names. Its ``spec`` chooses and orders those three groups,
``delimiter`` is written after each initial, and ``separator`` joins
the initials within one group (:ref:`rendering-arguments`):

.. doctest::

    >>> name.initials()
    'J. Q. X. V.'
    >>> name.initials(spec="{given} {family}")
    'J. V.'
    >>> name.initials(spec="{given}{middle}{family}", delimiter="", separator="")
    'JQXV'

A word in a script that writes no initials, such as Han, Hangul, kana,
Thai, Lao, Burmese or Arabic, gives none, and a word in another script
beside it still gives its own:

.. doctest::

    >>> parse("김민준").initials(), parse("أحمد علي").initials()
    ('', '')
    >>> parse("Ahmed علي").initials()
    'A.'

Initials written together in the name
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

This is how such a name is parsed, whatever you render from it.
A given name written as initials run together with full stops, in
capitals, reads as those initials: the first is the given name and the
rest are middle names, as they would be written apart, and ``str()``
keeps them as written:

.. doctest::

    >>> tolkien = parse("J.R.R. Tolkien")
    >>> tolkien.given, tolkien.middle, str(tolkien)
    ('J.', 'R.R.', 'J.R.R. Tolkien')
    >>> tolkien.initials()
    'J. R. R. T.'

Fixing case
-----------

Use ``capitalized()`` when your data arrives in one case, all capitals
or all lowercase. It returns a new parsed name with the case repaired:

.. doctest::

    >>> str(parse("TEO VAN BRANDT, PHD").capitalized())
    'Teo van Brandt, PhD'
    >>> str(parse("juan de la vega").capitalized())
    'Juan de la Vega'

A name whose words, its suffix aside, are written in more than one case
is left as it is, on the assumption that someone cased it on purpose;
pass ``force=True`` to repair it anyway:

.. doctest::

    >>> str(parse("Mara QUILL").capitalized())
    'Mara QUILL'
    >>> str(parse("Mara QUILL").capitalized(force=True))
    'Mara Quill'

:ref:`rendering-arguments` has the rules that decide what is touched,
and :ref:`case-exceptions` says how to give a word a casing of its own.

The no-argument form above uses the DEFAULT lexicon; for a name parsed
with a custom :class:`~nameparser.Parser`, call
:meth:`Parser.capitalized() <nameparser.Parser.capitalized>` so the
parser's own vocabulary decides the exceptions.

Comparing names
----------------

``matches()`` asks whether two writings are the same name: every field
the same, whatever the case, and whether written with a family comma
or without one. It
does not accept an initial for a name, so ``J. Smith`` does not match
``John Smith``. To join records from several sources, where one writes
the initial and another the name, use
:meth:`Parser.matching() <nameparser.Parser.matching>`
(:ref:`matching-names`):

.. doctest::

    >>> parse("de la Vega, Juan").matches("Juan de la Vega")
    True
    >>> parse("John Smith").matches("J. Smith")
    False
    >>> Parser().matching().check(parse("John Smith"), parse("J. Smith")).consistent
    True

``comparison_key()`` is the tuple ``matches()`` compares, one casefolded
string per field. Use it as a dictionary key, or to remove duplicates:

.. doctest::

    >>> parse("JUAN DE LA VEGA").comparison_key() == parse("Juan de la Vega").comparison_key()
    True
    >>> records = ["Mara Quill", "QUILL, MARA", "Teo Brandt"]
    >>> list({parse(r).comparison_key(): r for r in records}.values())
    ['QUILL, MARA', 'Teo Brandt']

``==`` is strict value equality — two :class:`~nameparser.ParsedName`
instances are equal only if every field matches exactly.

``matches()`` parses a str argument with
the DEFAULT parser; to compare against a string using a custom
:class:`~nameparser.Parser`'s vocabulary, call
:meth:`Parser.matches() <nameparser.Parser.matches>`.

.. _parser-guesses:

When the parser had to guess
-----------------------------

Some names have no single correct reading. A leading ``Van`` could be
a given name — it really is for the actor Van Johnson — or the start
of a family name, as it is for President Van Buren. Both are the same
shape, so no rule can tell them apart. The parser takes the more
likely reading and *records* the choice on ``ambiguities`` rather than
deciding silently:

.. doctest::

    >>> name = parse("Van Buren")
    >>> name.given, name.family
    ('Van', 'Buren')
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

.. _credentials-also-surnames:

Credentials that are also surnames
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

The post-nominals that double as ordinary surnames report an ambiguity
the same way, as ``suffix-or-name``. A bare acronym such as ``MA`` is
read by how it is written and, where the writing gives no signal (all
lowercase, or a name written wholly in one case), by the count of words
before it. A reading by the count, or by the lean to the surname that
any other cased spelling gives (``Jack Ma``), is recorded. Capitals in a name written in
more than one case settle it as the credential (``Jack MA``), as periods
do, so no ``suffix-or-name`` fork is reported:

.. doctest::

    >>> parse("Jack Ma").family, parse("Jack Ma").ambiguities
    ('Ma', (Ambiguity('suffix-or-name': 'Ma'),))
    >>> parse("JOHN SMITH MA").suffix
    'MA'
    >>> [a.kind.value for a in parse("JOHN SMITH MA").ambiguities]
    ['suffix-or-name']
    >>> parse("John Smith MA").ambiguities
    ()

A credential written as a word that is also a surname (``KC``, ``PC``,
``DL``) takes no lean from capitals: the count decides, and the fork is
reported:

.. doctest::

    >>> parse("John Smith KC").suffix, parse("John Smith KC").ambiguities
    ('KC', (Ambiguity('suffix-or-name': 'KC'),))

:ref:`ambiguous-words` has the full rules, including how a comma
changes them.

Two ``Policy`` switches read a word the vocabulary does not hold as a
credential from how it is written. ``unlisted_dotted_suffixes`` (on by
default) lets a token of two or more period-separated chunks read as
one, and ``unlisted_caps_suffixes`` an all-caps word (and after a
comma, a mixed-case one such as ``MRes``): by default only after a
comma behind a full name, and at the end of a name only on request,
since an all-caps surname is written there.
:ref:`unlisted-credentials` says where each applies and what it
reports:

.. doctest::

    >>> parse("John Smith X.Y.Z.").suffix, parse("John Smith, XYZ").suffix
    ('X.Y.Z.', 'XYZ')
    >>> parse("John Smith XYZ").family
    'XYZ'

A reading the vocabulary settles on its own is not a guess and reports
nothing — periods make ``M.A.`` unambiguously a credential:

.. doctest::

    >>> parse("John Smith M.A.").ambiguities
    ()

Titles that are also given names
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

A title that is also borne as a given name, such as ``Dean``, ``King``
or ``Major``, is a title only inside a title phrase, and
otherwise a name word (``Dean of Students`` is a title). Where it opens
the name and a phrase could have held it, the choice is recorded as
``title-or-name``:

.. doctest::

    >>> dean_smith = parse("Dean Smith")
    >>> dean_smith.given, [a.kind.value for a in dean_smith.ambiguities]
    ('Dean', ['title-or-name'])

:ref:`titles-also-given-names` covers the phrases and how to read such
a word as a title everywhere.

.. _reading-not-taken:

The reading it did not take
~~~~~~~~~~~~~~~~~~~~~~~~~~~

A report of a fork also says what the other reading was.
``Ambiguity.alternative`` is a :class:`~nameparser.Reading` with four
parts, these three and its ``languages`` (see :ref:`reading-taken`):

- **kind** — what the word would have been read as: a ``name``, an
  ``initial``, a ``credential``, a ``generation``, a ``particle``, a
  ``title`` and so on (:class:`~nameparser.ReadingKind`).
- **role** — the field the word would have landed in, with every other
  word of the name read as the parse read it.
- **source** — why that reading was there at all
  (:class:`~nameparser.ReadingSource`): ``vocabulary`` for a listed word,
  ``declared`` for a word the vocabulary also lists as a name, ``shape``
  for a roman numeral, dotted letters or a one-letter initial, and
  ``position`` for an ordinary
  word nothing lists, which is a name only by where it stands.

The source is what tells two reports of the same kind apart. ``MA`` is
listed as a surname as well as a credential, so its name reading is
declared; ``Jones`` behind a credential is taken into the credential run
by position alone:

.. doctest::

    >>> for text in ("JOHN SMITH MA", "John Smith PhD Jones", "Van Buren"):
    ...     alt = parse(text).ambiguities[0].alternative
    ...     print(f"{text}: {alt.kind.value} as {alt.role.value} ({alt.source.value})")
    JOHN SMITH MA: name as family (declared)
    John Smith PhD Jones: name as family (position)
    Van Buren: particle as family (vocabulary)

Check for ``None`` before reading one. Three sorts of report carry no
alternative:

- A report of a shape rather than a fork: ``comma-structure``,
  ``unbalanced-delimiter``, ``segmentation``.
- ``order``, whose other reading lays out the whole name rather than
  moving one word (its detail says it in words).
- One whose other reading no field could hold: a connective letter
  opening the name (``E SMITH JONES``) has no word before it to join.

.. note::

   The alternative is not compared: two names that differ only in it
   are equal. It was added in 2.7, and a ``ParsedName`` pickled by an
   earlier release loads with no alternative on its reports; its
   ``languages`` were added in 3.0.

.. _reading-taken:

The reading each word took
~~~~~~~~~~~~~~~~~~~~~~~~~~

Every token also says how the parse read it, whether or not
a fork was reported. ``Token.reading`` is a :class:`~nameparser.Reading`
with the same parts, its role the token's own field, and two flags
besides, ``first_surname`` and ``second_surname``, marking the words
``surname1`` and ``surname2`` hold where the family was read as two,
or had middle names folded into it (``middle_as_family``):

.. doctest::

    >>> for tok in parse("Dr. Juan de la Vega III").tokens:
    ...     print(f"{tok.text}: {tok.reading.kind.value} ({tok.reading.source.value})")
    Dr.: title (vocabulary)
    Juan: name (position)
    de: particle (vocabulary)
    la: particle (vocabulary)
    Vega: name (position)
    III: generation (vocabulary)

Where a fork was reported, the token's reading and the report's
alternative are the two readings the parse weighed. ``Jones`` behind a
credential was taken into the suffix by position, where it would
otherwise have been the family name:

.. doctest::

    >>> jones_run = parse("John Smith PhD Jones")
    >>> jones_run.tokens[-1].reading
    Reading('credential' as 'suffix', 'position')
    >>> jones_run.ambiguities[0].alternative
    Reading('name' as 'family', 'position')

A reading from the vocabulary also names the language files that list
the word that way, as BCP 47 tags in ``languages``: the files whose
reading is on in the parser's own ``Lexicon``, so a choice of languages
(:doc:`locales`) names the files it reads. A reading by shape or
position names none, and neither does a reading you add to your own
``Lexicon`` of a kind no file holds for that word; adding a kind a
file does hold turns that file's reading on, and names it:

.. doctest::

    >>> for tok in parse("Dr. Juan de la Vega III").tokens:
    ...     print(f"{tok.text}: {tok.reading.languages}")
    Dr.: ('mul',)
    Juan: ()
    de: ('ca', 'es', 'fil', 'fr', 'it', 'nl', 'pt', 'si')
    la: ('ca', 'es', 'fil', 'fr', 'it')
    Vega: ()
    III: ('mul',)

``mul`` is the file of words shared across languages on purpose.

A token the parse did not read has no reading: one that
:meth:`~nameparser.ParsedName.replace` or
:meth:`~nameparser.Parser.revise` builds.

.. note::

   Like the alternative, the reading is not compared, so it never makes
   two names unequal. It was added in 3.0 (:doc:`migrate` has what else
   changed), and a token loaded from a pickle written before 3.0 has
   none. The first parse in a process that meets a listed word loads
   the index of the language files, once.

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
value. There are two ways to make one: ``replace()`` splices the new
text in as written, and :meth:`Parser.revise()
<nameparser.Parser.revise>` reads it the way a parse would.

Use ``revise()`` unless you want the text taken literally. It knows the
new words as a parse would, so their particles, initials and case
repair work as they do in a parsed name. ``replace()`` keeps the words
you give it and knows nothing about them:

.. doctest::

    >>> bare = parse("Mara Quill")
    >>> bare.replace(family="van Quill").family_base
    'van Quill'
    >>> Parser().revise(bare, family="van Quill").family_base
    'Quill'

Splicing a value in with ``replace()``
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

``replace()`` returns a copy with the given fields changed. Untouched
fields keep their tokens (and ``original`` is preserved), with one
deliberate exception: an ambiguity that pointed into a replaced field
is dropped — correcting the field that was flagged clears the flag,
while correcting an unrelated field keeps it.

.. doctest::

    >>> name = parse("Juan de la Vega")
    >>> corrected = name.replace(title="Dr.")
    >>> str(corrected)
    'Dr. Juan de la Vega'
    >>> name.title
    ''
    >>> flagged = parse("Van Buren")
    >>> flagged.replace(given="Martin").ambiguities
    ()
    >>> [a.kind.value for a in flagged.replace(family="Harrison").ambiguities]
    ['particle-or-given']

What a spliced value loses
~~~~~~~~~~~~~~~~~~~~~~~~~~

Use ``revise()``, below, if you want the views in this table to work
on the new value. ``replace()`` splits values on whitespace into plain,
untagged
tokens — the vocabulary knowledge a parse would have about the new
text is not there. A token the parse never saw carries no decision to
honor, so each view falls back on what it can answer without one:

.. list-table::
   :header-rows: 1
   :widths: 24 46 30

   * - View
     - On a spliced field
     - Example
   * - :meth:`~nameparser.ParsedName.initials`
     - Every word contributes an initial, a particle included
     - ``J. d. l. V. S.``, not ``J. V. S.``
   * - ``family_particles``
     - Empty
     - ``''``, not ``de la``
   * - ``family_base``
     - The whole field
     - ``de la Vega Smith``, not ``Vega Smith``
   * - :meth:`~nameparser.ParsedName.capitalized`
     - Repairs what a word answers on its own, and misses the two
       things only a parse records, below
     - | ``xy.z.`` to ``Xy.Z.``, not ``XY.Z.``
       | ``de la`` kept, not ``De La``

.. doctest::

    >>> name.family_particles
    'de la'
    >>> replaced = name.replace(family="de la Vega Smith")
    >>> replaced.family_particles
    ''
    >>> replaced.family_base
    'de la Vega Smith'
    >>> replaced.initials()
    'J. d. l. V. S.'

``initials()`` takes no vocabulary at all, and ``family_particles`` and
``family_base`` are properties on the parsed name, which holds no
vocabulary of its own either. Of the parsed name's own views,
``capitalized()`` is the only one handed a vocabulary, and it still asks
the vocabulary what a word answers on its own:

- whether the word is a conjunction or an initial;
- whether the exceptions map holds a mask for it, which applies
  wherever the word stands;
- in the suffix, whether it is a listed credential acronym or a roman
  numeral, which is written in capitals.

.. doctest::

    >>> lowercase = parse("juan de la vega")
    >>> lowercase.replace(suffix="mba").capitalized().suffix
    'MBA'
    >>> lowercase.replace(suffix="vi").capitalized().suffix
    'VI'

It misses two things, each a fact the parse records and a spliced word
does not carry. A credential recognised only by its dotted shape is
repaired as an ordinary word. And whether a particle is acting as one
is a fact about the whole part, so a family set to ``de la`` stays
lowercase where the same words parsed are repaired to ``De La``:

.. doctest::

    >>> lowercase.replace(suffix="xy.z.").capitalized().suffix
    'Xy.Z.'
    >>> Parser().revise(lowercase, suffix="xy.z.").capitalized().suffix
    'XY.Z.'
    >>> name.replace(family="de la").capitalized(force=True).family
    'de la'
    >>> parse("Juan de la").capitalized(force=True).family
    'De La'

The views that read how the parse read each word are empty for a field
either method rewrote, ``revise()`` included: ``generation``,
``honorifics``, ``patronymic`` and ``surname2``. ``credentials`` then
holds every word of a rewritten suffix:

.. doctest::

    >>> junior = Parser().revise(parse("Teo Brandt"), suffix="Jr.")
    >>> junior.suffix, junior.generation, junior.credentials
    ('Jr.', '', 'Jr.')

Reading a value with ``Parser.revise()``
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

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

Choosing a locale
~~~~~~~~~~~~~~~~~

Add ``--locale`` to parse with a locale pack (for example ``--locale
ru``); see :doc:`locales`. What a code does depends on what holds it:

- **A pack's code** (``ru``) parses with that pack.
- **A code no pack has, that is a language whose vocabulary file holds
  readings** (``ko``) chooses that language alone.
- **A language whose file holds no reading a parse reads yet** (``hu``)
  needs ``--strict``.
- **A pack's language with a region or script subtag** (``zh-CN``,
  ``zh-Hant``) exits naming the pack to use.

``--strict`` reads only that language's words and the shared ones (see
:ref:`strict-choice`), and needs ``--locale``:

::

    $ python -m nameparser --locale ko --strict --json "Kim Do Hyun"
    {"title": "", "given": "Kim", "middle": "Do", "family": "Hyun", "suffix": "", "nickname": "", "maiden": ""}

Setting the name order
~~~~~~~~~~~~~~~~~~~~~~

``--order`` reads the name in another order
— ``given-first`` (the default), ``family-first`` or
``family-first-given-last``, the three ``Policy.name_order`` values —
and replaces any order a pack sets. A name written wholly in Han,
Hangul or kana keeps the order its script gives it, and a family comma
fixes the order whatever the flag:

::

    $ python -m nameparser --order family-first --json "Kovács János Péter"
    {"title": "", "given": "János", "middle": "Péter", "family": "Kovács", "suffix": "", "nickname": "", "maiden": ""}

Reading a one-word name as the family
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

``--lone-name-word`` takes ``given`` (the default) or ``family``, the
field a name of one name word reads as under every order
(:ref:`lone-name-word`):

::

    $ python -m nameparser --lone-name-word family --json "Anh"
    {"title": "", "given": "", "middle": "", "family": "Anh", "suffix": "", "nickname": "", "maiden": ""}

Policy switches
~~~~~~~~~~~~~~~

The ``Policy`` switches that turn a reading on or off have a flag each,
spelled as the field. Each has a ``--no-`` form, save
``--unlisted-caps-suffixes``, which takes ``off``, ``after-comma`` or
``everywhere``:

.. list-table::
   :header-rows: 1
   :widths: 45 55

   * - Flag
     - ``Policy`` field
   * - ``--two-given-names``
     - ``two_given_names`` (:ref:`two-given-names`)
   * - ``--two-family-names``
     - ``two_family_names`` (:ref:`two-family-names`)
   * - ``--middle-as-family``
     - ``middle_as_family``
   * - ``--initials-as-family``
     - ``initials_as_family`` (:ref:`initials-as-family`)
   * - ``--capitals-as-family``
     - ``capitals_as_family`` (:ref:`capitals-as-family`)
   * - ``--lenient-comma-suffixes``
     - ``lenient_comma_suffixes`` (:ref:`lenient-comma-suffixes`)
   * - ``--unlisted-dotted-suffixes``
     - ``unlisted_dotted_suffixes`` (:ref:`unlisted-credentials`)
   * - ``--unlisted-caps-suffixes``
     - ``unlisted_caps_suffixes`` (:ref:`unlisted-credentials`)

Like ``--order``, each replaces the setting of a pack
given with ``--locale``, keeping the pack's vocabulary, and one left
out keeps the pack's setting. ``es`` reads ``Maestra`` as a title,
which the default reads as a given name, and two family names, and the
flag turns only the second off:

::

    $ python -m nameparser --two-given-names --json "Juan Carlos García"
    {"title": "", "given": "Juan Carlos", "middle": "", "family": "García", "suffix": "", "nickname": "", "maiden": ""}
    $ python -m nameparser --locale es --no-two-family-names --json "Maestra Ana García López"
    {"title": "Maestra", "given": "Ana", "middle": "García", "family": "López", "suffix": "", "nickname": "", "maiden": ""}

Where next
----------

.. raw:: html

   <span id="east-asian-names"></span>

* :doc:`shapes` — the input forms the parser reads, and
  :doc:`east-asian` for Chinese, Japanese and Korean names
* :doc:`customize` and :doc:`policy` — your own vocabulary and behavior
* :doc:`getting-started` — the map of every page, by task
