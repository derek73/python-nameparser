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

.. raw:: html

   <span id="east-asian-names"></span>

East Asian names have a page of their own: :ref:`east-asian-names`.

.. _aggregate-views:

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

``patronymic`` names the words that say whose child the bearer is, a
particle such as ``bin`` with the parent's name after it, in whatever
field the parse put them, which keeps them. It reads no position, so a
name written without the particle has none:

.. doctest::

    >>> nasab = parse("Mahathir bin Mohamad")
    >>> nasab.patronymic, nasab.family
    ('bin Mohamad', 'bin Mohamad')
    >>> parse("Anwar Ibrahim").patronymic
    ''

``surname2`` is the family's second name, where the parse read the
family as two: with ``two_family_names`` on
(:ref:`two-family-names`), as the ``es``, ``es_ar``, ``cs`` and ``sk``
packs turn it on (:doc:`locales`), or for a Chinese name opening with
two surnames under ``zh`` (:ref:`east-asian-names`), and ``family``
keeps both. Every other name has none, a family comma's and a
hyphenated one included:

.. doctest::

    >>> from nameparser import Parser, Policy
    >>> marquez = Parser(policy=Policy(two_family_names=True)).parse(
    ...     "Gabriel García Márquez")
    >>> marquez.family, marquez.surname2
    ('García Márquez', 'Márquez')
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

.. doctest::

    >>> name.as_dict(include_empty=False)
    {'title': 'Dr.', 'given': 'Juan', 'middle': 'Q. Xavier', 'family': 'de la Vega', 'suffix': 'III'}
    >>> str(name)
    'Dr. Juan Q. Xavier de la Vega III'
    >>> name.render("{family}, {given}")
    'de la Vega, Juan'
    >>> name.initials()
    'J. Q. X. V.'

``str()``, like ``render()`` with no spec, lays the name out in the
order it was read in (:attr:`ParsedName.order
<nameparser.ParsedName.order>`) and keeps the separator written between
two words that stay side by side, normalized: nothing stays nothing,
any run of whitespace becomes one space, and a comma before a suffix
stays. A spec you pass renders exactly as written, in its own order:

.. doctest::

    >>> str(parse("김민준")), str(parse("John Smith, Jr."))
    ('김민준', 'John Smith, Jr.')
    >>> parse("김민준").render("{given} {family}")
    '민준 김'

A given name written as initials run together with full stops, in
capitals, reads as those initials: the first is the given name and the
rest are middle names, as they would be written apart, and ``str()``
keeps them as written (since 3.1):

.. doctest::

    >>> tolkien = parse("J.R.R. Tolkien")
    >>> tolkien.given, tolkien.middle, str(tolkien)
    ('J.', 'R.R.', 'J.R.R. Tolkien')
    >>> tolkien.initials()
    'J. R. R. T.'

Fixing case
-----------

.. doctest::

    >>> str(parse("juan de la vega").capitalized())
    'Juan de la Vega'

The no-argument form above uses the DEFAULT lexicon; for a name parsed
with a custom :class:`~nameparser.Parser`, call
:meth:`Parser.capitalized() <nameparser.Parser.capitalized>` so the
parser's own vocabulary decides the exceptions.

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
the same way.
Which reading a bare one gets depends on what the writing says:

- **Capitals** in a name written in more than one case lean to the
  credential, even with no words to spare (``Jack MA``). They settle it,
  as periods do, so nothing is reported.
- **Any other cased spelling** that is not wholly lowercase leans to
  the surname, even with words to spare (``Jack Ma``, ``John Smith Ma``).
- **No signal** — all lowercase, or a name written wholly in one
  case — leaves it to the count: the credential with two or more words
  before it, not counting a title or a nickname, the surname otherwise.

Where the writing leaves the choice to the parser, the choice is
recorded:

.. doctest::

    >>> parse("JOHN SMITH MA").suffix
    'MA'
    >>> [a.kind.value for a in parse("JOHN SMITH MA").ambiguities]
    ['suffix-or-name']
    >>> parse("John Smith MA").ambiguities
    ()
    >>> parse("Jack MA").suffix
    'MA'
    >>> parse("Jack Ma").family
    'Ma'
    >>> parse("John Smith Ma").family
    'Ma'

:ref:`ambiguous-words` has the full rules, including how a comma
changes them.

Two ``Policy`` switches extend the same class to words the vocabulary
does not hold. ``unlisted_dotted_suffixes`` (on by default) reads a
token of two or more period-separated chunks the same way —
``parse("John Smith X.Y.Z.").suffix`` is ``'X.Y.Z.'`` — and
``unlisted_caps_suffixes`` does the same for an unlisted all-caps word,
by default only after a comma behind a full name, where an all-caps
surname is never written — ``parse("John Smith, XYZ").suffix`` is
``'XYZ'`` — and at the end of a name only on request, since an
all-caps surname is written there. See :ref:`unlisted-credentials`
for both.

A reading the vocabulary settles on its own is not a guess and reports
nothing — periods make ``M.A.`` unambiguously a credential:

.. doctest::

    >>> parse("John Smith M.A.").ambiguities
    ()

Titles that are also given names
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

A title that is also borne as a given name, such as ``Dean``, ``King``
or ``Major``, is a title only inside a title phrase (since 2.7), and
otherwise a name word. Where it opens the name and a phrase could have
held it, the choice is recorded as ``title-or-name``:

.. doctest::

    >>> parse("Dean of Students Jane Smith").title
    'Dean of Students'
    >>> dean_smith = parse("Dean Smith")
    >>> dean_smith.given, [a.kind.value for a in dean_smith.ambiguities]
    ('Dean', ['title-or-name'])

:ref:`titles-also-given-names` covers the phrases and how to read such
a word as a title everywhere.

.. _reading-not-taken:

The reading it did not take
~~~~~~~~~~~~~~~~~~~~~~~~~~~

Since 2.7 a report of a fork also says what the other reading was.
``Ambiguity.alternative`` is a :class:`~nameparser.Reading` with three
parts, and since 3.0 a fourth, its ``languages`` (see
:ref:`reading-taken`):

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

A report of a shape rather than a fork — ``comma-structure``,
``unbalanced-delimiter``, ``segmentation`` — carries no alternative,
nor does ``order``, whose other reading lays out the whole name rather
than moving one word (its detail says it in words), and neither does
one whose other reading no field could hold: a
connective letter opening the name (``E SMITH JONES``) has no word
before it to join. Check for ``None`` before reading one.
The alternative is not compared: two names that differ only in it are
equal, as before 2.7, and a ``ParsedName`` pickled by an earlier
release loads with no alternative on its reports.

.. _reading-taken:

The reading each word took
~~~~~~~~~~~~~~~~~~~~~~~~~~

Since 3.0 every token also says how the parse read it, whether or not
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

``mul`` is the file of words shared across languages on purpose. The
first parse in a process that meets a listed word loads the index of
those files once: about a millisecond, or about 20 ms where Python
writes no bytecode cache (``PYTHONDONTWRITEBYTECODE``).

A token the parse did not read has no reading: one that
:meth:`~nameparser.ParsedName.replace` or
:meth:`~nameparser.Parser.revise` builds, and one loaded from a pickle
written before 3.0. Like the alternative, the reading is not compared,
so it never makes two names unequal.

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

``replace()`` splits values on whitespace into plain, untagged
tokens — the vocabulary knowledge a parse would have about the new
text is not there. A token the parse never saw carries no decision to
honor, so each view falls back on what it can answer without one:

- :meth:`~nameparser.ParsedName.capitalized` is handed a vocabulary,
  so it asks that whether a word is a conjunction or an initial, which
  a word answers on its own. Its other special cases never needed a
  reading: an exceptions-map mask applies wherever its word stands,
  and a listed credential acronym or a roman numeral is written in
  capitals wherever the field is the suffix, so ``replace(suffix="mba")``
  repairs to ``MBA`` and ``suffix="vi"`` to ``VI``. A credential
  recognised only by its dotted shape is the exception, since the shape
  is something the parse records. Particles are a second exception:
  whether a particle is acting as one is a fact about the whole part,
  and no word of a spliced field carries a reading to derive it from,
  so a family set to ``de la`` stays lowercase where the same words
  parsed are repaired to ``De La``.
- :meth:`~nameparser.ParsedName.initials` takes no vocabulary at all,
  so every word of a spliced field contributes an initial.
- ``family_particles`` and ``family_base`` are properties on the
  parsed name, which holds no vocabulary of its own either:
  ``family_particles`` empties and ``family_base`` takes the whole
  field.

Of the parsed name's own views, ``capitalized()`` is the only one
handed a vocabulary.

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
    >>> name.replace(family="de la").capitalized(force=True).family
    'de la'

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

Add ``--locale`` to parse with a locale pack (for example ``--locale
ru``); see :doc:`locales`. A code no pack has that is a language whose
vocabulary file holds readings (``--locale ko``) chooses that language
alone; one whose file holds no reading a parse reads yet (``hu``)
needs ``--strict``, and
a pack's language with a region or script subtag (``zh-CN``,
``zh-Hant``) exits naming the pack to use.
``--strict`` reads only that language's words and the shared ones (see
:ref:`strict-choice`), and needs ``--locale``:

::

    $ python -m nameparser --locale ko --strict --json "Kim Do Hyun"
    {"title": "", "given": "Kim", "middle": "Do", "family": "Hyun", "suffix": "", "nickname": "", "maiden": ""}

``--order`` reads the name in another order
— ``given-first`` (the default), ``family-first`` or
``family-first-given-last``, the three ``Policy.name_order`` values —
and replaces any order a pack sets. A name written wholly in Han,
Hangul or kana keeps the order its script gives it, and a family comma
fixes the order whatever the flag:

::

    $ python -m nameparser --order family-first --json "Kovács János Péter"
    {"title": "", "given": "János", "middle": "Péter", "family": "Kovács", "suffix": "", "nickname": "", "maiden": ""}

``--lone-name-word`` takes ``given`` (the default) or ``family``, the
field a name of one name word reads as under every order
(:ref:`lone-name-word`):

::

    $ python -m nameparser --lone-name-word family --json "Anh"
    {"title": "", "given": "", "middle": "", "family": "Anh", "suffix": "", "nickname": "", "maiden": ""}

The ``Policy`` switches that turn a reading on or off have a flag each,
spelled as the field: ``--two-given-names``, ``--two-family-names``,
``--middle-as-family``, ``--initials-as-family``,
``--lenient-comma-suffixes`` and ``--unlisted-dotted-suffixes``, each
with a ``--no-`` form, and
``--unlisted-caps-suffixes`` taking ``off``, ``after-comma`` or
``everywhere``. Like ``--order``, each replaces the setting of a pack
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

* :doc:`concepts` — how the parser works
* :doc:`customize` — your own vocabulary and behavior
* :doc:`locales` — locale packs
* :doc:`migrate` — coming from 1.x or 2.x ``HumanName``, which 3.0 removes
